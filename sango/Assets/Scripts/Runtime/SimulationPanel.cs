using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.Rendering.HighDefinition;
using UnityEngine.UI;

namespace Sango
{
    /// <summary>
    /// M2-E2 Simulation 面板（spec #85 Story 5/6，WeatherGUI idiom：深色半透明 UGUI 运行时
    /// 构建、legacy Text、零场景资产依赖）。屏幕右上角（天气面板左上）：
    ///   - 岛屿数量 / 岛屿缩放：面板字段，Enter（或 Apply 按钮）才重建（spec 明示 Apply 语义）；
    ///     映射 = IslandRebuild（count 直传、scale × sizeRange/clusterRadius、seed 恒 42 确定性）。
    ///   - 雷达量程 / 扫描转速：滑条拖动即时生效（雷达是装饰层，不必走重建）。
    ///   - 船模预览：render-texture 相机 + 远角编目 prefab 实例，慢旋（render-texture 方案，
    ///     spec 首选档；超时兜底的类名圆盘未启用）。
    ///   - Environment count / agents-per-env：占位行（plan phase-2 字段——非功能，带标注）。
    /// 键位（正式输入，CUA 鼠标不可靠；无 0-9/T/F/G/C/V/Q/E/Z/X 冲突）：
    ///   -/= 岛数 ∓1 · ,/. 缩放 ∓0.25（仅字段，待 Apply） · Enter = Apply · P = 循环预览档位。
    /// 预览旋转仅鼠标拖拽域外自动旋，无需键位（旋转是观感，档位切换才是控制）。
    /// </summary>
    public class SimulationPanel : MonoBehaviour
    {
        [Tooltip("雷达覆盖层引用（量程/转速滑条即时驱动）。")]
        public RadarOverlay radar;

        [Tooltip("船只编目（预览按档位取 prefab/水线/LOA）。")]
        public VesselCatalog catalog;

        [Tooltip("岛群中心（重建根节点摆放位；M1 = (0,0,180)）。")]
        public Vector3 islandCenter = new Vector3(0f, 0f, 180f);

        [Tooltip("岛群基线设置（场景构建器注入 M1 常数 + 岛体材质；Apply 时经 IslandRebuild 映射）。")]
        public IslandSettings islandBaseline;

        // 待应用的岛屿参数（Enter/Apply 才生效；面板滑条与 -/= ,/. 键同写这里）。
        int m_Count = 5;
        float m_Scale = 1f;

        Text _countValue, _scaleValue;
        Slider _countSlider, _scaleSlider, _rangeSlider, _sweepSlider;
        Text _applyStatus;
        Font _font;
        RectTransform _panel;

        // 船模预览：远角舞台 + 专用相机 + RT。
        VesselClass m_SelectedClass = VesselClass.Small;
        GameObject m_PreviewModel;
        Camera m_PreviewCamera;
        RenderTexture m_PreviewRt;
        RawImage m_PreviewImage;
        Text m_PreviewName;

        // 预览舞台：远离岛群（撒点 ≤ ~0.5 km）与两船，专相机 far clip 裁掉一切远景。
        static readonly Vector3 k_StagePos = new Vector3(5000f, 0f, 5000f);
        const float k_PreviewRotateDegPerSec = 30f;

        const float k_PanelWidth = 400f;

        static readonly VesselClass[] k_Classes = { VesselClass.Small, VesselClass.Medium, VesselClass.Large };
        static readonly string[] k_ClassNames = { "Small", "Medium", "Large" };

        void Awake()
        {
            Application.runInBackground = true; // 采集/演示失焦不停渲染（WeatherGUI 同款）
            _font = LoadBuiltinFont();
            BuildUI();
        }

        void Start()
        {
            SelectClass(m_SelectedClass); // 预览初档（Start：catalog 注入完成、Awake 时序无关）
        }

        // Unity 6000 内置字体资源名 LegacyRuntime.ttf（Arial.ttf 已于 2022+ 移除，留兜底）。
        static Font LoadBuiltinFont()
        {
            Font f = null;
            try { f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { }
            if (f == null) { try { f = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { } }
            return f;
        }

        void BuildUI()
        {
            var canvasGo = new GameObject("SimulationCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;

            EnsureEventSystem();

            _panel = NewRect("Panel", canvasGo.transform);
            _panel.anchorMin = _panel.anchorMax = _panel.pivot = new Vector2(1f, 1f);
            _panel.anchoredPosition = new Vector2(-20f, -20f);
            _panel.sizeDelta = new Vector2(k_PanelWidth, 640f);
            var panelImage = _panel.gameObject.AddComponent<Image>();
            panelImage.color = new Color(0f, 0f, 0f, 0.7f);

            float y = -18f;
            var title = CreateLabel(_panel, "Title", "SANGO SIMULATION", 24, TextAnchor.MiddleLeft, Color.white);
            AnchorTop(title.rectTransform, 16f, y, k_PanelWidth - 32f, 30f);
            y -= 40f;

            // ── 岛屿（Apply 门控）───────────────────────────────────────────────────────
            y = SectionLabel(y, "ISLANDS  (Apply rebuilds, seed 42 kept)");

            _countValue = CreateLabel(_panel, "CountValue", "", 16, TextAnchor.MiddleRight, new Color(0.75f, 0.85f, 0.95f));
            AnchorTop(_countValue.rectTransform, k_PanelWidth - 216f, y, 200f, 22f);
            var countLabel = CreateLabel(_panel, "CountLabel", "Island count", 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            AnchorTop(countLabel.rectTransform, 16f, y, 260f, 22f);
            y -= 30f;
            _countSlider = CreateSlider("IslandCount", 1f, 15f, m_Count, true, v =>
            {
                m_Count = Mathf.RoundToInt(v);
                RefreshPendingLabels();
                Debug.Log($"[Sango.M2E2] island count pending={m_Count} (press Apply / Enter)");
            });
            PlaceSlider((RectTransform)_countSlider.transform, y);
            y -= 46f;

            _scaleValue = CreateLabel(_panel, "ScaleValue", "", 16, TextAnchor.MiddleRight, new Color(0.75f, 0.85f, 0.95f));
            AnchorTop(_scaleValue.rectTransform, k_PanelWidth - 216f, y, 200f, 22f);
            var scaleLabel = CreateLabel(_panel, "ScaleLabel", "Island scale (x)", 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            AnchorTop(scaleLabel.rectTransform, 16f, y, 260f, 22f);
            y -= 30f;
            _scaleSlider = CreateSlider("IslandScale", IslandRebuild.ScaleMin, IslandRebuild.ScaleMax, m_Scale, false, v =>
            {
                m_Scale = Mathf.Round(v * 100f) / 100f;
                RefreshPendingLabels();
                Debug.Log($"[Sango.M2E2] island scale pending={m_Scale:0.00} (press Apply / Enter)");
            });
            PlaceSlider((RectTransform)_scaleSlider.transform, y);
            y -= 46f;

            // ── 雷达（即时生效）────────────────────────────────────────────────────────
            y = SectionLabel(y, "RADAR  (live)");

            _rangeSlider = CreateSlider("RadarRange", RadarOverlay.RangeMinM, RadarOverlay.RangeMaxM,
                radar != null ? radar.RangeM : 600f, true, v =>
                {
                    if (radar != null) radar.SetRange(v);
                });
            y = LabeledSlider(y, "Radar range (m)", _rangeSlider);

            _sweepSlider = CreateSlider("RadarSweep", RadarOverlay.SweepMinDegPerSec, RadarOverlay.SweepMaxDegPerSec,
                radar != null ? radar.SweepSpeedDegPerSec : 45f, true, v =>
                {
                    if (radar != null) radar.SetSweepSpeed(v);
                });
            y = LabeledSlider(y, "Sweep speed (deg/s)", _sweepSlider);

            // ── 船模预览 ───────────────────────────────────────────────────────────────
            y = SectionLabel(y, "SHIP MODEL PREVIEW  (P cycles)");

            float[] xs = { 16f, 140f, 264f };
            for (int i = 0; i < k_Classes.Length; i++)
            {
                var cls = k_Classes[i];
                CreateButton($"Class.{k_ClassNames[i]}", k_ClassNames[i], xs[i], y, 112f, 36f, () => SelectClass(cls));
            }
            y -= 44f;

            var previewRect = NewRect("Preview", _panel);
            previewRect.anchorMin = previewRect.anchorMax = previewRect.pivot = new Vector2(0f, 1f);
            previewRect.anchoredPosition = new Vector2(16f, y);
            previewRect.sizeDelta = new Vector2(200f, 150f);
            // RawImage 自身即底板 Graphic（uGUI 一 GameObject 一 Graphic：再叠 Image 会抛异常，
            // 真机烟测 2026-09-24 实证）：无 texture 时按 color 画纯色底，texture 到位后转白显 RT。
            m_PreviewImage = previewRect.gameObject.AddComponent<RawImage>();
            m_PreviewImage.raycastTarget = false;
            m_PreviewImage.color = new Color(0.05f, 0.08f, 0.10f, 0.9f);
            // HDRP 渲染到 RT 的垂直翻转惯例：uv 反转一次（否则船倒立）——EnsurePreviewStage 里设。
            m_PreviewImage.uvRect = new Rect(0f, 0f, 1f, 1f);
            m_PreviewName = CreateLabel(_panel, "PreviewName", "", 16, TextAnchor.MiddleLeft, new Color(1f, 0.84f, 0.35f));
            AnchorTop(m_PreviewName.rectTransform, 232f, y, k_PanelWidth - 248f, 40f);
            y -= 158f;

            // ── Apply + 占位字段 + 键位提示 ────────────────────────────────────────────
            CreateButton("ApplyButton", "Apply", 16f, y, k_PanelWidth - 32f, 44f, ApplyNow);
            y -= 54f;
            _applyStatus = CreateLabel(_panel, "ApplyStatus", "", 14, TextAnchor.MiddleLeft, new Color(0.6f, 0.9f, 0.65f));
            AnchorTop(_applyStatus.rectTransform, 16f, y, k_PanelWidth - 32f, 18f);
            y -= 26f;

            var ph = CreateLabel(_panel, "Placeholders",
                "environment count: 1 (phase 2) · agents/env: 1 (phase 2)", 13,
                TextAnchor.MiddleLeft, new Color(0.55f, 0.58f, 0.62f));
            AnchorTop(ph.rectTransform, 16f, y, k_PanelWidth - 32f, 18f);
            y -= 24f;

            var hint1 = CreateLabel(_panel, "Hint1", "C camera · V vectors · A/G demo", 13, TextAnchor.MiddleLeft, new Color(0.6f, 0.65f, 0.7f));
            AnchorTop(hint1.rectTransform, 16f, y, k_PanelWidth - 32f, 18f);
            y -= 20f;
            var hint2 = CreateLabel(_panel, "Hint2", "-/= count · ,/. scale · Enter apply", 13, TextAnchor.MiddleLeft, new Color(0.6f, 0.65f, 0.7f));
            AnchorTop(hint2.rectTransform, 16f, y, k_PanelWidth - 32f, 18f);
            y -= 20f;
            var hint3 = CreateLabel(_panel, "Hint3", "P model · Q/E radar range · Z/X sweep", 13, TextAnchor.MiddleLeft, new Color(0.6f, 0.65f, 0.7f));
            AnchorTop(hint3.rectTransform, 16f, y, k_PanelWidth - 32f, 18f);

            _panel.sizeDelta = new Vector2(k_PanelWidth, -y + 12f);
            RefreshPendingLabels();
        }

        float SectionLabel(float y, string text)
        {
            var l = CreateLabel(_panel, "Section." + text, text, 15, TextAnchor.MiddleLeft, new Color(0.55f, 0.75f, 0.9f));
            AnchorTop(l.rectTransform, 16f, y, k_PanelWidth - 32f, 20f);
            return y - 28f;
        }

        float LabeledSlider(float y, string text, Slider slider)
        {
            var l = CreateLabel(_panel, text + " Label", text, 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            AnchorTop(l.rectTransform, 16f, y, 260f, 22f);
            PlaceSlider((RectTransform)slider.transform, y - 30f); // Slider 自身 RectTransform 无包装属性
            return y - 76f;
        }

        static void AnchorTop(RectTransform rt, float x, float y, float w, float h)
        {
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(w, h);
        }

        static void PlaceSlider(RectTransform rt, float y)
        {
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.sizeDelta = new Vector2(-40f, 26f);
            rt.anchoredPosition = new Vector2(0f, y);
        }

        void RefreshPendingLabels()
        {
            if (_countValue != null) _countValue.text = $"{m_Count}";
            if (_scaleValue != null) _scaleValue.text = $"x{m_Scale:0.00}";
            if (_countSlider != null) _countSlider.SetValueWithoutNotify(m_Count);
            if (_scaleSlider != null) _scaleSlider.SetValueWithoutNotify(m_Scale);
        }

        // ── Apply：重建岛群（仅 Islands 根；船/天气不动）+ 雷达参数收权 ────────────────

        public void ApplyNow()
        {
            var settings = IslandRebuild.MapToSettings(islandBaseline, m_Count, m_Scale);
            var old = GameObject.Find("Islands");
            if (old != null) Destroy(old);
            var root = PerlinIslandGenerator.GenerateIslands(settings);
            root.transform.position = islandCenter;
            if (radar != null)
            {
                radar.SetRange(_rangeSlider != null ? _rangeSlider.value : radar.RangeM);
                radar.SetSweepSpeed(_sweepSlider != null ? _sweepSlider.value : radar.SweepSpeedDegPerSec);
            }
            if (_applyStatus != null) _applyStatus.text = $"applied: {settings.count} islands x{m_Scale:0.00} @ t+{Time.frameCount}f";
            Debug.Log($"[Sango.M2E2] islands rebuilt: count={settings.count} scale={m_Scale:0.00} " +
                      $"sizeRange=({settings.sizeRange.x:0}-{settings.sizeRange.y:0}m) cluster={settings.clusterRadius:0}m seed={settings.seed}");
        }

        // ── 键位（-/= 岛数、,/. 缩放、Enter Apply、P 预览档）─────────────────────────

        void Update()
        {
            HandleHotkeys();
            MirrorRadar();
        }

        // 键位冲突账本：0-9/T/F 天气、G demo、C 相机、V 矢量、Q/E/Z/X 雷达。
        // Minus/Equals/Comma/Period/Return/P 空闲。Enter 另防 UI 焦点双触发（EncounterPanel 同款）。
        void HandleHotkeys()
        {
            var es = EventSystem.current;
            if (es != null && es.currentSelectedGameObject != null) es.SetSelectedGameObject(null);

            if (Input.GetKeyDown(KeyCode.Minus) || Input.GetKeyDown(KeyCode.KeypadMinus))
            {
                m_Count = Mathf.Clamp(m_Count - 1, (int)IslandRebuild.CountMin, 15);
                RefreshPendingLabels();
                Debug.Log($"[Sango.M2E2] island count pending={m_Count} (press Apply / Enter)");
            }
            if (Input.GetKeyDown(KeyCode.Equals) || Input.GetKeyDown(KeyCode.KeypadPlus))
            {
                m_Count = Mathf.Clamp(m_Count + 1, (int)IslandRebuild.CountMin, 15);
                RefreshPendingLabels();
                Debug.Log($"[Sango.M2E2] island count pending={m_Count} (press Apply / Enter)");
            }
            if (Input.GetKeyDown(KeyCode.Comma))
            {
                m_Scale = Mathf.Clamp(m_Scale - 0.25f, IslandRebuild.ScaleMin, IslandRebuild.ScaleMax);
                RefreshPendingLabels();
                Debug.Log($"[Sango.M2E2] island scale pending={m_Scale:0.00} (press Apply / Enter)");
            }
            if (Input.GetKeyDown(KeyCode.Period))
            {
                m_Scale = Mathf.Clamp(m_Scale + 0.25f, IslandRebuild.ScaleMin, IslandRebuild.ScaleMax);
                RefreshPendingLabels();
                Debug.Log($"[Sango.M2E2] island scale pending={m_Scale:0.00} (press Apply / Enter)");
            }
            if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter))
            {
                ApplyNow();
            }
            if (Input.GetKeyDown(KeyCode.P))
            {
                int next = (System.Array.IndexOf(k_Classes, m_SelectedClass) + 1) % k_Classes.Length;
                SelectClass(k_Classes[next]);
                Debug.Log($"[Sango.M2E2] preview class -> {k_ClassNames[next]} (P)");
            }
        }

        // 雷达值被 Q/E/Z/X（RadarOverlay 侧）或 Apply 收权后，滑条逐帧镜像回读（WeatherGUI 纪律）。
        void MirrorRadar()
        {
            if (radar == null) return;
            if (_rangeSlider != null) _rangeSlider.SetValueWithoutNotify(radar.RangeM);
            if (_sweepSlider != null) _sweepSlider.SetValueWithoutNotify(radar.SweepSpeedDegPerSec);
        }

        // ── 船模预览：render-texture 相机 + 远角慢旋实例 ─────────────────────────────

        public void SelectClass(VesselClass cls)
        {
            m_SelectedClass = cls;
            if (catalog == null) return;
            var entry = catalog.GetEntry(cls);
            if (entry?.prefab == null)
            {
                Debug.LogWarning($"[Sango.M2E2] no catalog prefab for {cls} — preview unchanged");
                return;
            }

            EnsurePreviewStage();

            if (m_PreviewModel != null) Destroy(m_PreviewModel);
            m_PreviewModel = Instantiate(entry.prefab, k_StagePos + new Vector3(0f, entry.waterlineOffsetY, 0f), Quaternion.identity);
            m_PreviewModel.name = $"PreviewModel.{cls}";

            // 取景：距离随 LOA（Large 100 m ↔ Small 12 m 同框率），略俯视。
            float d = entry.loaMeters * 2.2f + 8f;
            var camPos = k_StagePos + new Vector3(0f, entry.loaMeters * 0.45f + 4f, -d);
            m_PreviewCamera.transform.position = camPos;
            m_PreviewCamera.transform.rotation = Quaternion.LookRotation(
                k_StagePos + new Vector3(0f, entry.loaMeters * 0.2f + 2f, 0f) - camPos, Vector3.up);

            if (m_PreviewName != null) m_PreviewName.text = $"{cls} · LOA {entry.loaMeters:0} m";
        }

        void EnsurePreviewStage()
        {
            if (m_PreviewCamera != null) return;
            var camGo = new GameObject("PreviewCamera", typeof(Camera), typeof(HDAdditionalCameraData));
            m_PreviewCamera = camGo.GetComponent<Camera>();
            m_PreviewCamera.fieldOfView = 30f;
            m_PreviewCamera.nearClipPlane = 1f;
            m_PreviewCamera.farClipPlane = 1200f; // 舞台远距 7 km：岛群/两船全在 far 外
            m_PreviewCamera.cullingMask = ~0;
            m_PreviewRt = new RenderTexture(256, 256, 24);
            m_PreviewCamera.targetTexture = m_PreviewRt;
            if (m_PreviewImage != null)
            {
                m_PreviewImage.texture = m_PreviewRt;
                m_PreviewImage.color = Color.white; // texture 到位：取消底板暗色 tint
                m_PreviewImage.uvRect = new Rect(0f, 1f, 1f, -1f); // HDRP RT 垂直翻转修正
            }
            Debug.Log("[Sango.M2E2] ship-model preview stage built (render-texture camera @ far corner)");
        }

        void UpdatePreviewModel()
        {
            if (m_PreviewModel != null)
                m_PreviewModel.transform.Rotate(0f, k_PreviewRotateDegPerSec * Time.deltaTime, 0f, Space.World);
        }

        void LateUpdate() => UpdatePreviewModel();

        void OnDestroy()
        {
            if (m_PreviewRt != null) { m_PreviewRt.Release(); Destroy(m_PreviewRt); }
        }

        // ── uGUI 构建辅助（WeatherGUI/EncounterPanel 同款最小件，第三份本地拷贝）────────

        static void EnsureEventSystem()
        {
            if (EventSystem.current != null) return;
            new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
        }

        static RectTransform NewRect(string name, Transform parent)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            return rt;
        }

        Text CreateLabel(Transform parent, string name, string content, int fontSize, TextAnchor align, Color color)
        {
            var rt = NewRect(name, parent);
            var text = rt.gameObject.AddComponent<Text>();
            text.font = _font;
            text.text = content;
            text.fontSize = fontSize;
            text.color = color;
            text.alignment = align;
            text.horizontalOverflow = HorizontalWrapMode.Overflow;
            text.verticalOverflow = VerticalWrapMode.Overflow;
            text.raycastTarget = false;
            return text;
        }

        Slider CreateSlider(string name, float min, float max, float value, bool wholeNumbers, UnityAction<float> onChanged)
        {
            var rt = NewRect(name, _panel);

            var bg = NewImage("Background", rt, new Color(1f, 1f, 1f, 0.14f));
            bg.rectTransform.anchorMin = Vector2.zero;
            bg.rectTransform.anchorMax = Vector2.one;
            bg.rectTransform.offsetMin = new Vector2(0f, 9f);
            bg.rectTransform.offsetMax = new Vector2(0f, -9f);

            var fillArea = NewRect("Fill Area", rt);
            fillArea.anchorMin = Vector2.zero;
            fillArea.anchorMax = Vector2.one;
            fillArea.offsetMin = new Vector2(6f, 10f);
            fillArea.offsetMax = new Vector2(-6f, -10f);
            var fill = NewImage("Fill", fillArea, new Color(0.30f, 0.55f, 0.85f, 0.9f));
            fill.rectTransform.anchorMin = Vector2.zero;
            fill.rectTransform.anchorMax = new Vector2(0f, 1f);
            fill.rectTransform.sizeDelta = Vector2.zero;

            var handleArea = NewRect("Handle Slide Area", rt);
            handleArea.anchorMin = Vector2.zero;
            handleArea.anchorMax = Vector2.one;
            handleArea.offsetMin = new Vector2(6f, 0f);
            handleArea.offsetMax = new Vector2(-6f, 0f);
            var handle = NewImage("Handle", handleArea, new Color(0.95f, 0.97f, 1f));
            handle.rectTransform.anchorMin = new Vector2(0f, 0f);
            handle.rectTransform.anchorMax = new Vector2(0f, 1f);
            handle.rectTransform.sizeDelta = new Vector2(12f, 0f);

            var slider = rt.gameObject.AddComponent<Slider>();
            slider.fillRect = fill.rectTransform;
            slider.handleRect = handle.rectTransform;
            slider.targetGraphic = handle;
            slider.direction = Slider.Direction.LeftToRight;
            slider.minValue = min;
            slider.maxValue = max;
            slider.wholeNumbers = wholeNumbers;
            slider.value = Mathf.Clamp(value, min, max);
            slider.onValueChanged.AddListener(onChanged);
            return slider;
        }

        void CreateButton(string name, string label, float x, float y, float w, float h, UnityAction onClick)
        {
            var rt = NewRect(name, _panel);
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(w, h);
            var img = rt.gameObject.AddComponent<Image>();
            img.color = new Color(0.16f, 0.22f, 0.30f, 0.95f);
            img.raycastTarget = true; // EventSystem 射线命中 raycastable Graphic 才派发（M1-C 事故纪律）
            var btn = rt.gameObject.AddComponent<Button>();
            btn.targetGraphic = img;
            var colors = btn.colors;
            colors.highlightedColor = new Color(0.26f, 0.36f, 0.50f, 0.95f);
            colors.pressedColor = new Color(0.10f, 0.14f, 0.20f, 0.95f);
            btn.colors = colors;
            btn.onClick.AddListener(onClick);
            var t = CreateLabel(rt, name + " Label", label, 16, TextAnchor.MiddleCenter, Color.white);
            t.rectTransform.anchorMin = Vector2.zero;
            t.rectTransform.anchorMax = Vector2.one;
            t.rectTransform.offsetMin = new Vector2(4f, 4f);
            t.rectTransform.offsetMax = new Vector2(-4f, -4f);
        }

        static Image NewImage(string name, Transform parent, Color color)
        {
            var rt = NewRect(name, parent);
            var img = rt.gameObject.AddComponent<Image>();
            img.color = color;
            img.raycastTarget = true;
            return img;
        }
    }
}
