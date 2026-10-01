using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using static Sango.UiBuildHelpers;

namespace Sango
{
    /// <summary>
    /// M1 天气面板：UGUI 运行时构建（不依赖 prefab/场景 UI 资产）。Awake 建 Canvas/Panel/滑条并接线，
    /// 改动即调 WeatherController.Apply()。深色半透明面板（黑 70% 纯色矩形；圆角需 9-slice sprite，后调）。
    /// Text 实现：用 legacy uGUI Text，不用 TextMeshPro。依据：工程 manifest 仅含 com.unity.ugui 2.0.0
    /// （内嵌 TMP 运行时，Unity.TextMeshPro.asmdef autoReferenced=true，PackageCache/com.unity.ugui@b996e7548785/Runtime/TMP/），
    /// 但 TMP 需先导入 TMP Essentials 资产（TMP Settings/默认字体），工程尚未导入；legacy Text + 内置字体零依赖可跑。
    /// M2 可升 TMP（issue #79 技术栈定案含 TMP）。
    /// </summary>
    public class WeatherGUI : MonoBehaviour
    {
        [Tooltip("拖 WeatherController 引用；留空则取同对象上的组件")]
        public WeatherController controller;

        [Tooltip("数字键 0-9 直设蒲福级（M1 场景默认开）。M2-E 遭遇场景同屏挂 EncounterPanel（1/2/3 选模式），由该场景 bootstrapper 关闭数字档避免一键双义；T/F 时刻/雾距预设不受影响。")]
        public bool digitHotkeysEnabled = true;

        Text _windReadout;
        Text _beaufortValue, _windDirValue, _timeValue, _cloudValue, _fogValue;
        Font _font;
        float _cursorY;
        RectTransform _panel;
        Slider[] _sliders;   // [beaufort, windDir, time, cloud, fog]，Update 镜像用
        Dropdown _tierDropdown;
        Dropdown _atmoDropdown; // M7-B 大气档（N 键循环镜像）
        Dropdown _qualityDropdown; // M8 画质档（L 键循环镜像；无 M8 streamer 的场景切档仅记账）

        const float PanelWidth = 380f;
        const float ValueRowHeight = 26f; // 标签行高
        const float SliderHeight = 46f;   // 标签行 + 滑条行的总步进

        void Awake()
        {
            // 证据/演示采集时播放器窗口不在前台（CUA 自动化拿不到焦点），失焦也要继续渲染。
            Application.runInBackground = true;
            if (controller == null) controller = GetComponent<WeatherController>();
            _font = LoadBuiltinFont();
            BuildUI();
            if (controller != null)
            {
                controller.Apply();
                RefreshReadout();
            }
        }

        void BuildUI()
        {
            var canvasGo = new GameObject("WeatherCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;

            EnsureEventSystem();

            // 深色半透明面板：屏幕左上角
            _panel = NewRect("Panel", canvasGo.transform);
            _panel.anchorMin = _panel.anchorMax = _panel.pivot = new Vector2(0f, 1f);
            _panel.anchoredPosition = new Vector2(20f, -20f);
            _panel.sizeDelta = new Vector2(PanelWidth, 640f);
            var panelImage = _panel.gameObject.AddComponent<Image>();
            panelImage.color = new Color(0f, 0f, 0f, 0.7f); // 黑 70%（圆角视觉后调）

            _cursorY = -18f;
            TopLabel("Title", "SANGO WEATHER", 24, TextAnchor.MiddleLeft, Color.white);
            _cursorY -= 44f;
            _windReadout = TopLabel("WindReadout", "wind -- m/s", 22, TextAnchor.MiddleLeft, new Color(1f, 0.84f, 0.35f));
            _cursorY -= 40f;

            // 滑条回调先落 controller 字段再 Apply；SetValueWithoutNotify 防止重入
            Slider beaufortSlider = null;
            _beaufortValue = CreateSliderRow("Beaufort 0-11", 0f, 11f, controller != null ? controller.beaufort : 3f, false, v =>
            {
                if (controller == null) return;
                controller.BeginUserGradeTransition(targetBeaufort: Mathf.Round(v * 10f) / 10f);
                OnAnyChanged();
            }, out beaufortSlider);

            Slider windDirSlider = null;
            _windDirValue = CreateSliderRow("Wind direction (deg)", 0f, 360f, controller != null ? controller.windDirectionDeg : 30f, true, v =>
            {
                if (controller == null) return;
                controller.windDirectionDeg = Mathf.Round(v);
                if (windDirSlider != null) windDirSlider.SetValueWithoutNotify(controller.windDirectionDeg);
                OnAnyChanged();
            }, out windDirSlider);

            Slider timeSlider = null;
            _timeValue = CreateSliderRow("Time of day (h)", 0f, 24f, controller != null ? controller.timeOfDayHours : 12f, false, v =>
            {
                if (controller == null) return;
                controller.timeOfDayHours = Mathf.Round(v * 10f) / 10f; // 0.1 h = 6 min
                if (timeSlider != null) timeSlider.SetValueWithoutNotify(controller.timeOfDayHours);
                OnAnyChanged();
            }, out timeSlider);

            Slider cloudSlider = null;
            _cloudValue = CreateSliderRow("Cloud cover", 0f, 1f, controller != null ? controller.cloudCover : 0.4f, false, v =>
            {
                if (controller == null) return;
                controller.cloudCover = Mathf.Round(v * 100f) / 100f;
                if (cloudSlider != null) cloudSlider.SetValueWithoutNotify(controller.cloudCover);
                OnAnyChanged();
            }, out cloudSlider);

            Slider fogSlider = null;
            _fogValue = CreateSliderRow("Fog distance (m)", 100f, 8000f, controller != null ? controller.fogDistanceMeters : 3000f, true, v =>
            {
                if (controller == null) return;
                controller.BeginUserGradeTransition(targetFogMeters: Mathf.Round(v));
                OnAnyChanged();
            }, out fogSlider);

            _cursorY -= ValueRowHeight;
            CreateRowLabel("Spectrum tier (JS-PM approx)");
            _cursorY -= ValueRowHeight;
            var tierNames = new[] { "Calm", "Moderate", "Rough", "VeryRough" };
            _tierDropdown = CreateDropdown(_panel, "TierDropdown", tierNames, controller != null ? (int)controller.spectrumTier : 1, i =>
            {
                if (controller == null) return;
                controller.spectrumTier = (JsPmTier)i;
                controller.BeginUserGradeTransition();
                OnAnyChanged();
            });

            // M7-B 大气三档（浓霾晴/积雨云/雷暴雨幡）：下拉选择 + N 键循环（HandleHotkeys）。
            _cursorY -= ValueRowHeight;
            CreateRowLabel("Atmosphere (M7-B)");
            _cursorY -= ValueRowHeight;
            var atmoNames = new[] { "Hazy clear", "Cumulonimbus", "Thunderstorm" };
            _atmoDropdown = CreateDropdown(_panel, "AtmoDropdown", atmoNames,
                controller != null ? (int)controller.atmosphereTier : 0, i =>
            {
                if (controller == null) return;
                controller.atmosphereTier = (M7BMath.AtmosphereTier)i;
                controller.ApplyAtmosphereTier();
                controller.Apply();
                RefreshReadout();
            });

            // M8 画质双档（High = M7 终态基线 / Low = 性能降档）：下拉选择 + L 键循环。
            // 大气三档同款三段式：回调写参数源（M8Quality 静态 API → streamer.ApplyTier）
            // → 应用 → Update 镜像回读。无 streamer 的场景（M1/M2E）只翻静态记账值。
            _cursorY -= ValueRowHeight;
            CreateRowLabel("Quality (M8)");
            _cursorY -= ValueRowHeight;
            _qualityDropdown = CreateDropdown(_panel, "QualityDropdown", new[] { "High", "Low" },
                M8Quality.DropdownIndex, i =>
            {
                M8Quality.SetTierFromDropdownIndex(i);
                Debug.Log($"[Sango.M8] GUI quality -> {M8Quality.CurrentTier}");
            });

            _sliders = new[] { beaufortSlider, windDirSlider, timeSlider, cloudSlider, fogSlider };
            _panel.sizeDelta = new Vector2(PanelWidth, -_cursorY + 12f);
        }

        // 键盘驾驶（演示 + 自动化采集共用）：数字键 0-9 直设蒲福级 B0-B9；
        // T 循环时刻预设（正午/傍晚/深夜），F 循环雾距预设（3000/1000/8000m）。
        // 面板经 Update 镜像自动同步；为什么需要：自动化 harness 无法移动物理光标
        // （CGEvent 只在当前光标位置派发），键盘事件是唯一可编程精确输入通路。
        static readonly float[] k_TimePresets = { 12f, 17.5f, 0f };
        static readonly float[] k_FogPresets = { 3000f, 1000f, 8000f };
        int _timePresetIdx, _fogPresetIdx;

        void HandleHotkeys()
        {
            if (controller == null) return;
            if (digitHotkeysEnabled) // M2-E：遭遇场景关数字档（1/2/3 归 EncounterPanel 选模式）
            {
                for (int k = 0; k <= 9; k++)
                {
                    if (Input.GetKeyDown((KeyCode)((int)KeyCode.Alpha0 + k)))
                    {
                        // 文档默认分配（beaufort-water-mapping.md）：B0-1 Calm、B2-4 Moderate、B5-7 Rough、B8-11 VeryRough
                        controller.spectrumTier = k <= 1 ? JsPmTier.Calm : k <= 4 ? JsPmTier.Moderate
                                                : k <= 7 ? JsPmTier.Rough : JsPmTier.VeryRough;
                        // M9-2：风档切档改目标态 + 2.5 s 渐变（直设 beaufort = 风/浪/桥摇一并跳变的断崖；
                        // spectrumTier 离散枚举仍即时生效，主导量风速随轨渐变）
                        controller.BeginUserGradeTransition(targetBeaufort: k);
                        controller.Apply();
                        RefreshReadout();
                        Debug.Log($"[Sango.M1] hotkey beaufort=B{k} tier={controller.TierName()}");
                    }
                }
            }
            if (Input.GetKeyDown(KeyCode.T)) // 时刻预设直设（M8RecordingRunner 同源确定性路径——时刻永不渐变）
            {
                _timePresetIdx = (_timePresetIdx + 1) % k_TimePresets.Length;
                controller.timeOfDayHours = k_TimePresets[_timePresetIdx];
                controller.Apply();
                RefreshReadout();
                Debug.Log($"[Sango.M1] hotkey time={k_TimePresets[_timePresetIdx]}h");
            }
            if (Input.GetKeyDown(KeyCode.F))
            {
                _fogPresetIdx = (_fogPresetIdx + 1) % k_FogPresets.Length;
                controller.BeginUserGradeTransition(targetFogMeters: k_FogPresets[_fogPresetIdx]); // M9-2：雾距切档 2.5 s 渐变
                controller.Apply();
                RefreshReadout();
                Debug.Log($"[Sango.M1] hotkey fog={k_FogPresets[_fogPresetIdx]}m");
            }
            if (Input.GetKeyDown(KeyCode.N)) // M7-B 大气档循环（M7 review 修复：V 已被 VectorArrows
            {                                // M2-E2 无门控占用——同帧两功能齐翻；改 N（全工程空闲，键位账本 0-9/T/F/G/C/B/A/P/Q/E/Z/X/Space/R/±,./Enter/V 已占））
                                             // M9-2 注：本路径 ApplyAtmosphereTier 已是目标态 + preset 3 s smoothstep
                                             //（雾/曝光/云量随轨渐变）；本次补的是 digits/F 直设通道的断崖。
                                             // 云预设四档量化为 HDRP Simple 模式离散行为，残留跳变见 backlog。
                controller.atmosphereTier = M7BMath.NextAtmosphereTier(controller.atmosphereTier);
                controller.ApplyAtmosphereTier();
                controller.Apply();
                RefreshReadout();
                Debug.Log($"[Sango.M1] hotkey atmosphere={controller.atmosphereTier}");
            }
            if (Input.GetKeyDown(KeyCode.L)) // M8 画质档循环（M8 键位账本核对 2026-09-29：
            {                                // 全仓 grep Input.GetKeyDown：0-9/T/F/N/G/V/B/C/A/P/Q/E/Z/X/Space/R/±,./Enter(+keypad) 已占，L 空闲）
                M8Quality.CycleTier();
                Debug.Log($"[Sango.M8] hotkey quality -> {M8Quality.CurrentTier}");
            }
            if (Input.GetKeyDown(KeyCode.H)) // M8-B HUD 集中隐藏/还原（HudVisibility；出片与演示共用）。
            {                                // 键位账本 2026-09-29 复核（M8-B 批再 grep 全仓 Input.GetKeyDown）：
                                             // 0-9/T/F/N/L/G/V/B/C/A/P/Q/E/Z/X/Space/R/±,./Enter(+keypad) 已占，H 空闲。
                HudVisibility.Toggle();
                Debug.Log($"[Sango.M8] hotkey hud -> {(HudVisibility.IsHidden ? "hidden" : "shown")} (H)");
            }
        }

        // applyEveryFrame 下 controller 公开字段是唯一真值源（Inspector/后续脚本可绕 GUI 直改）。
        // 每帧镜像回 UI：SetValueWithoutNotify 与 Text/Dropdown setter 对等值均 no-op，无回调风暴；
        // 拖动路径先写 controller 再由本镜像回读，天然收敛。映射表截图（精确 B0/3/6/9）走
        // Inspector 输入 + 此镜像，GUI 点 track 精度不足。
        void Update()
        {
            HandleHotkeys();
            if (controller == null || !controller.applyEveryFrame) return;
            if (_sliders != null)
            {
                _sliders[0].SetValueWithoutNotify(controller.beaufort);
                _sliders[1].SetValueWithoutNotify(controller.windDirectionDeg);
                _sliders[2].SetValueWithoutNotify(controller.timeOfDayHours);
                _sliders[3].SetValueWithoutNotify(controller.cloudCover);
                _sliders[4].SetValueWithoutNotify(controller.fogDistanceMeters);
            }
            if (_tierDropdown != null && (int)controller.spectrumTier != _tierDropdown.value)
            {
                _tierDropdown.SetValueWithoutNotify((int)controller.spectrumTier);
                _tierDropdown.RefreshShownValue();
            }
            if (_atmoDropdown != null && (int)controller.atmosphereTier != _atmoDropdown.value)
            {
                _atmoDropdown.SetValueWithoutNotify((int)controller.atmosphereTier);
                _atmoDropdown.RefreshShownValue();
            }
            if (_qualityDropdown != null && (int)M8Quality.CurrentTier != _qualityDropdown.value)
            {
                _qualityDropdown.SetValueWithoutNotify((int)M8Quality.CurrentTier);
                _qualityDropdown.RefreshShownValue();
            }
            RefreshReadout();
        }

        void OnAnyChanged()
        {
            if (controller == null) return;
            controller.Apply();
            RefreshReadout();
        }

        /// <summary>顶部风速读数：数值来自 controller.Apply() 后的 LastWindSpeedMs，与映射表同源（M1 验收条款 2）。</summary>
        void RefreshReadout()
        {
            _windReadout.text = $"wind {controller.LastWindSpeedMs:F1} m/s   (B{controller.beaufort:0.#} {controller.TierName()})";
            _beaufortValue.text = $"{controller.beaufort:0.0} -> {WeatherController.BeaufortToWindSpeedMs(controller.beaufort):F1} m/s";
            _windDirValue.text = $"{controller.windDirectionDeg:0} deg";
            _timeValue.text = $"{controller.timeOfDayHours:0.0} h";
            _cloudValue.text = $"{controller.cloudCover:0.00}";
            _fogValue.text = $"{controller.fogDistanceMeters:0} m";
        }

        // ── uGUI 构建辅助 ───────────────────────────────────────────────────────────────
        // 逐字同构小件（NewRect/NewImage/Stretch/LoadBuiltinFont）已收编 UiBuildHelpers
        // （using static 引入，调用点零改动）。本类保留的 EnsureEventSystem 带证据日志
        // （M1 采集账本），与共享静默版不同构；其余布局耦合函数见共享类头注。

        static void EnsureEventSystem()
        {
            if (EventSystem.current != null)
            {
                Debug.Log($"[Sango.M1] EventSystem exists: {EventSystem.current.name}");
                return;
            }
            var es = new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
            Debug.Log($"[Sango.M1] EventSystem created: {es != null}");
        }

        /// <summary>
        /// UGUI Slider 原生不响应 track 点击（只拖 handle）；演示需要点按跳值。
        /// 点击处 → 沿 slider 方向归一化 → 直接写 value。
        /// </summary>
        class TrackClickJump : MonoBehaviour, IPointerClickHandler
        {
            public Slider slider;
            public void OnPointerClick(PointerEventData e)
            {
                if (slider == null || slider.direction != Slider.Direction.LeftToRight) return;
                var cam = e.pressEventCamera;
                if (!RectTransformUtility.ScreenPointToLocalPointInRectangle(
                        transform as RectTransform, e.position, cam, out var local)) return;
                var rt = transform as RectTransform;
                float t = Mathf.Clamp01((local.x - rt.rect.xMin) / rt.rect.width);
                float v = Mathf.Lerp(slider.minValue, slider.maxValue, t);
                Debug.Log($"[Sango.M1] track click -> value={v:F2}");
                slider.value = v;
            }
        }

        /// <summary>面板内顶部横向拉伸的文本行（y 为自面板顶向下的偏移，写 _cursorY）。</summary>
        Text TopLabel(string name, string content, int fontSize, TextAnchor align, Color color)
        {
            var t = CreateLabel(_panel, name, content, fontSize, align, color);
            var rt = t.rectTransform;
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.sizeDelta = new Vector2(-32f, fontSize + 8f);
            rt.anchoredPosition = new Vector2(0f, _cursorY);
            return t;
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

        Text CreateSliderRow(string labelText, float min, float max, float value, bool wholeNumbers,
            UnityAction<float> onChanged, out Slider slider)
        {
            CreateRowLabel(labelText);
            var valueLabel = CreateLabel(_panel, labelText + " Value", "", 16, TextAnchor.MiddleRight, new Color(0.75f, 0.85f, 0.95f));
            var vrt = valueLabel.rectTransform;
            vrt.anchorMin = vrt.anchorMax = vrt.pivot = new Vector2(1f, 1f);
            vrt.anchoredPosition = new Vector2(-16f, _cursorY);
            vrt.sizeDelta = new Vector2(200f, 22f);
            _cursorY -= ValueRowHeight;

            slider = CreateSlider(_panel, labelText + " Slider", min, max, value, wholeNumbers, onChanged);
            _cursorY -= SliderHeight - ValueRowHeight;
            return valueLabel;
        }

        void CreateRowLabel(string labelText)
        {
            var label = CreateLabel(_panel, labelText, labelText, 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            var rt = label.rectTransform;
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(16f, _cursorY);
            rt.sizeDelta = new Vector2(260f, 22f);
        }

        Slider CreateSlider(Transform parent, string name, float min, float max, float value, bool wholeNumbers, UnityAction<float> onChanged)
        {
            var rt = NewRect(name, parent);
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.sizeDelta = new Vector2(-40f, 26f);
            rt.anchoredPosition = new Vector2(0f, _cursorY);

            // 无 sprite 纯色块结构（uGUI Image 无 sprite 即白色矩形着色）
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
            fill.rectTransform.anchorMax = new Vector2(0f, 1f); // Slider 运行时改 anchorMax.x
            fill.rectTransform.sizeDelta = Vector2.zero;

            var handleArea = NewRect("Handle Slide Area", rt);
            handleArea.anchorMin = Vector2.zero;
            handleArea.anchorMax = Vector2.one;
            handleArea.offsetMin = new Vector2(6f, 0f);
            handleArea.offsetMax = new Vector2(-6f, 0f);
            var handle = NewImage("Handle", handleArea, new Color(0.95f, 0.97f, 1f));
            handle.rectTransform.anchorMin = new Vector2(0f, 0f); // Slider 运行时改 x 双锚
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
            // track 点击跳值：挂在 Background（全 track 覆盖、raycastTarget 开启）
            var jump = bg.gameObject.AddComponent<TrackClickJump>();
            jump.slider = slider;
            slider.onValueChanged.AddListener(v => Debug.Log($"[Sango.M1] {name} onValueChanged={v:F2}"));
            return slider;
        }

        Dropdown CreateDropdown(Transform parent, string name, string[] options, int value, UnityAction<int> onChanged)
        {
            var rt = NewRect(name, parent);
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(16f, _cursorY);
            rt.sizeDelta = new Vector2(PanelWidth - 32f, 30f);
            var ddBg = rt.gameObject.AddComponent<Image>();
            ddBg.color = new Color(1f, 1f, 1f, 0.10f);

            var caption = CreateLabel(rt, "Label", "", 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            Stretch(caption.rectTransform, 12f, 3f, -36f, -3f);

            // 最小可用 Dropdown 模板：Template(默认 inactive) > Viewport(RectMask2D) > Content > Item(Toggle+Label)
            var template = NewRect("Template", rt);
            template.anchorMin = new Vector2(0f, 1f);
            template.anchorMax = Vector2.one;
            template.pivot = new Vector2(0.5f, 1f);
            template.anchoredPosition = new Vector2(0f, -30f);
            template.sizeDelta = new Vector2(0f, options.Length * 32f + 8f);
            var tplImage = template.gameObject.AddComponent<Image>();
            tplImage.color = new Color(0.08f, 0.09f, 0.11f, 0.97f);
            template.gameObject.SetActive(false);

            var viewport = NewRect("Viewport", template);
            Stretch(viewport, 4f, 4f, -4f, -4f);
            viewport.gameObject.AddComponent<RectMask2D>();

            var content = NewRect("Content", viewport);
            content.anchorMin = new Vector2(0f, 1f);
            content.anchorMax = Vector2.one;
            content.pivot = new Vector2(0.5f, 1f);
            content.anchoredPosition = Vector2.zero;
            content.sizeDelta = new Vector2(0f, options.Length * 32f);

            var item = NewRect("Item", content);
            item.anchorMin = new Vector2(0f, 1f);
            item.anchorMax = Vector2.one;
            item.pivot = new Vector2(0.5f, 1f);
            item.sizeDelta = new Vector2(0f, 32f);
            var itemBg = NewImage("Item Background", item, new Color(0.25f, 0.55f, 0.85f, 0.30f));
            Stretch(itemBg.rectTransform, 2f, 2f, -2f, -2f);
            var toggle = item.gameObject.AddComponent<Toggle>();
            toggle.targetGraphic = itemBg;
            toggle.isOn = false;

            var itemLabel = CreateLabel(item, "Item Label", "", 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            Stretch(itemLabel.rectTransform, 10f, 3f, -10f, -3f);

            var scroll = template.gameObject.AddComponent<ScrollRect>();
            scroll.content = content;
            scroll.viewport = viewport;
            scroll.horizontal = false;
            scroll.movementType = ScrollRect.MovementType.Clamped;
            scroll.scrollSensitivity = 16f;

            var dropdown = rt.gameObject.AddComponent<Dropdown>();
            dropdown.targetGraphic = ddBg;
            dropdown.captionText = caption;
            dropdown.itemText = itemLabel;
            dropdown.template = template;
            foreach (var opt in options) dropdown.options.Add(new Dropdown.OptionData(opt));
            dropdown.value = Mathf.Clamp(value, 0, options.Length - 1);
            dropdown.RefreshShownValue();
            dropdown.onValueChanged.AddListener(onChanged);
            return dropdown;
        }

    }
}
