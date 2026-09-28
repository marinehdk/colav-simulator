using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using static Sango.UiBuildHelpers;

namespace Sango
{
    /// <summary>
    /// M2-E1 遭遇面板（WeatherGUI idiom：深色半透明 UGUI 运行时构建、legacy uGUI Text、
    /// 零场景资产依赖）。屏幕右上角（天气面板占左上）：模式选择（dropdown）、Start/Pause、
    /// 时间倍率循环（1×/2×/4×）、Reset、仿真时钟读数。
    /// 键位（验收/演示正式输入，CUA 鼠标点击在本机不可靠——坐标被忽略、事件落在物理光标，
    /// 与 M1 结论同源；键位在本类 Update 处理，不经 WeatherGUI）：
    ///   Space = Start ⇄ Pause · R = Reset · 1/2/3 = 选模式（对遇/交叉/追越）· X = 倍率循环。
    /// 冲突处理：同屏 WeatherGUI 的数字键 0-9（直设蒲福级）由 bootstrapper 关闭
    /// （WeatherGUI.digitHotkeysEnabled=false），1/2/3 归本面板、T/F 仍归天气；
    /// G 为 per-instance 门控、遭遇船未启用。键鼠状态经 Update 镜像同步（dropdown 选中项、
    /// Start⇄Pause、×N、时钟读数）。
    /// </summary>
    public class EncounterPanel : MonoBehaviour
    {
        [Tooltip("拖 EncounterDirector 引用；留空则取同对象上的组件")]
        public EncounterDirector director;

        Text _patternDesc, _timeText, _runText, _speedText;
        Dropdown _patternDropdown;
        Font _font;
        float _cursorY;
        RectTransform _panel;

        const float k_PanelWidth = 400f;

        static readonly string[] k_PatternOptions =
        {
            "Head-on (port-to-port)",
            "Crossing (give-way from stbd)",
            "Overtaking (from astern)",
        };

        void Awake()
        {
            Application.runInBackground = true; // 采集/演示时失焦不停渲染（WeatherGUI 同款）
            if (director == null) director = GetComponent<EncounterDirector>();
            _font = LoadBuiltinFont();
            BuildUI();
            MirrorState();
        }

        void BuildUI()
        {
            var canvasGo = new GameObject("EncounterCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;

            EnsureEventSystem();

            // 深色半透明面板：屏幕右上角（WeatherGUI 占左上）
            _panel = NewRect("Panel", canvasGo.transform);
            _panel.anchorMin = _panel.anchorMax = _panel.pivot = new Vector2(1f, 1f);
            _panel.anchoredPosition = new Vector2(-20f, -20f);
            _panel.sizeDelta = new Vector2(k_PanelWidth, 380f);
            var panelImage = _panel.gameObject.AddComponent<Image>();
            panelImage.color = new Color(0f, 0f, 0f, 0.7f);

            _cursorY = -18f;
            var title = TopLabel("Title", "SANGO ENCOUNTER", 24, TextAnchor.MiddleLeft, Color.white);
            title.rectTransform.anchoredPosition = new Vector2(16f, _cursorY);
            _cursorY -= 46f;

            CreateRowLabel("Encounter pattern");
            _cursorY -= 34f;
            _patternDropdown = CreateDropdown(_panel, "PatternDropdown", k_PatternOptions, 0, _ => { });
            // dropdown 回调直连 director（语义同 WeatherGUI 滑条：先改状态再镜像）
            _patternDropdown.onValueChanged.AddListener(i =>
            {
                if (director != null) director.ApplyPattern((EncounterType)i);
                MirrorState();
            });
            _cursorY -= 40f; // dropdown 本体高 34 + 间隙 6：描述行自占一行，不与选中项标题重叠

            _patternDesc = CreateLabel(_panel, "PatternDesc", "", 15, TextAnchor.UpperLeft, new Color(0.75f, 0.85f, 0.95f));
            var drt = _patternDesc.rectTransform;
            drt.anchorMin = new Vector2(0f, 1f);
            drt.anchorMax = new Vector2(1f, 1f);
            drt.pivot = new Vector2(0.5f, 1f);
            drt.anchoredPosition = new Vector2(0f, _cursorY);
            drt.sizeDelta = new Vector2(-32f, 58f);
            _cursorY -= 66f;

            // 按钮行：Start/Pause | Speed | Reset
            _runText = CreateButton("RunButton", "Start", 16f, 120f, () =>
            {
                if (director != null) director.ToggleRun();
                MirrorState();
            });
            _speedText = CreateButton("SpeedButton", "x1", 144f, 88f, () =>
            {
                if (director != null) director.CycleTimeScale();
                MirrorState();
            });
            CreateButton("ResetButton", "Reset", 240f, 144f, () =>
            {
                if (director != null) director.ResetEncounter();
                MirrorState();
            });
            _cursorY -= 60f;

            _timeText = CreateLabel(_panel, "SimTime", "t = 0 s", 20, TextAnchor.MiddleLeft, new Color(1f, 0.84f, 0.35f));
            var trt = _timeText.rectTransform;
            trt.anchorMin = new Vector2(0f, 1f);
            trt.pivot = new Vector2(0f, 1f);
            trt.anchoredPosition = new Vector2(16f, _cursorY);
            trt.sizeDelta = new Vector2(k_PanelWidth - 32f, 26f);
            _cursorY -= 40f;

            var hint = CreateLabel(_panel, "Hint", "Space start/pause · R reset · 1/2/3 pattern · X speed", 14, TextAnchor.MiddleLeft, new Color(0.6f, 0.65f, 0.7f));
            var hrt = hint.rectTransform;
            hrt.anchorMin = new Vector2(0f, 1f);
            hrt.pivot = new Vector2(0f, 1f);
            hrt.anchoredPosition = new Vector2(16f, _cursorY);
            hrt.sizeDelta = new Vector2(k_PanelWidth - 32f, 20f);

            _panel.sizeDelta = new Vector2(k_PanelWidth, -_cursorY + 12f);
        }

        // 每帧镜像 director 状态（WeatherGUI applyEveryFrame 镜像同款纪律）+ 键盘热键。
        // 键位是验收/演示的正式输入（CUA 鼠标在本机不可靠）；键鼠同路：都改 director 状态，
        // 再经同一 MirrorState 回读面板（dropdown 选中项、Start⇄Pause、×N、时钟）。
        void Update()
        {
            if (director == null) return;
            HandleHotkeys();
            MirrorState();
        }

        // 键位冲突账本：同屏 WeatherGUI 占 T/F（数字 0-9 在遭遇场景被 bootstrapper 关闭，
        // 1/2/3 归本面板）；G 是 per-instance 门控且遭遇船未启用。Space/R/X 无主。
        // Space 另有 UI 焦点双触发坑：鼠标点过按钮后该按钮持有 UI 焦点，StandaloneInputModule
        // 会把 Space/Enter 再派发给它 —— 每帧清空选中，保证 Space 只走本处理器。
        void HandleHotkeys()
        {
            var es = EventSystem.current;
            if (es != null && es.currentSelectedGameObject != null) es.SetSelectedGameObject(null);

            if (Input.GetKeyDown(KeyCode.Space))
            {
                director.ToggleRun();
                Debug.Log($"[Sango.M2E] hotkey Space -> {(director.Running ? "run" : "pause")} t={director.SimTime:F1}s");
            }
            if (Input.GetKeyDown(KeyCode.R))
            {
                director.ResetEncounter();
                Debug.Log("[Sango.M2E] hotkey R -> reset");
            }
            for (int i = 0; i < k_PatternOptions.Length; i++)
            {
                if (Input.GetKeyDown((KeyCode)((int)KeyCode.Alpha1 + i)))
                {
                    var type = (EncounterType)i;
                    director.ApplyPattern(type);
                    Debug.Log($"[Sango.M2E] hotkey {(i + 1)} -> pattern {type}");
                }
            }
            if (Input.GetKeyDown(KeyCode.X))
            {
                director.CycleTimeScale();
                Debug.Log($"[Sango.M2E] hotkey X -> timescale x{director.TimeScale:0}");
            }
        }

        void MirrorState()
        {
            if (director == null) return;
            if (_runText != null) _runText.text = director.Running ? "Pause" : "Start";
            if (_speedText != null) _speedText.text = $"x{director.TimeScale:0}";
            if (_timeText != null)
            {
                _timeText.text = director.Running
                    ? $"t = {director.SimTime:F0} s"
                    : $"t = {director.SimTime:F0} s  (paused)";
            }
            if (_patternDropdown != null && (int)director.Type != _patternDropdown.value)
            {
                _patternDropdown.SetValueWithoutNotify((int)director.Type);
                _patternDropdown.RefreshShownValue();
            }
            if (_patternDesc != null && director.Pattern.Own.Waypoints != null)
            {
                _patternDesc.text = Describe(director.Pattern);
            }
        }

        static string Describe(in EncounterPattern p)
        {
            return $"own liner {p.Own.CruiseSpeedMps:0.#} m/s from ({p.Own.SpawnXZ.x:0},{p.Own.SpawnXZ.y:0}) hdg {p.Own.HeadingDeg:0}°\n" +
                   $"target cargo {p.Target.CruiseSpeedMps:0.#} m/s from ({p.Target.SpawnXZ.x:0},{p.Target.SpawnXZ.y:0}) hdg {p.Target.HeadingDeg:0}°";
        }

        // ── uGUI 构建辅助（WeatherGUI 同款最小件；同构小件收编 UiBuildHelpers，using static 引入）──

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

        Text CreateRowLabel(string labelText)
        {
            var label = CreateLabel(_panel, labelText + " Row", labelText, 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            var rt = label.rectTransform;
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(16f, _cursorY);
            rt.sizeDelta = new Vector2(280f, 22f);
            return label;
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

        /// <summary>建按钮（底板 + Button + 居中标签）；返回标签 Text 供运行时改字（Start⇄Pause 等）。</summary>
        Text CreateButton(string name, string label, float x, float w, UnityAction onClick)
        {
            var rt = NewRect(name, _panel);
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(x, _cursorY);
            rt.sizeDelta = new Vector2(w, 44f);
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
            var t = CreateLabel(rt, name + " Label", label, 18, TextAnchor.MiddleCenter, Color.white);
            var trt = t.rectTransform;
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.offsetMin = new Vector2(4f, 4f);
            trt.offsetMax = new Vector2(-4f, -4f);
            return t;
        }

        Dropdown CreateDropdown(Transform parent, string name, string[] options, int value, UnityAction<int> onChanged)
        {
            var rt = NewRect(name, parent);
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(16f, _cursorY);
            rt.sizeDelta = new Vector2(k_PanelWidth - 32f, 34f);
            var ddBg = rt.gameObject.AddComponent<Image>();
            ddBg.color = new Color(1f, 1f, 1f, 0.10f);
            ddBg.raycastTarget = true;

            var caption = CreateLabel(rt, "Label", "", 17, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            Stretch(caption.rectTransform, 12f, 3f, -36f, -3f);

            // 最小可用 Dropdown 模板（WeatherGUI 同款）：Template(默认 inactive) > Viewport(RectMask2D) > Content > Item(Toggle+Label)
            var template = NewRect("Template", rt);
            template.anchorMin = new Vector2(0f, 1f);
            template.anchorMax = Vector2.one;
            template.pivot = new Vector2(0.5f, 1f);
            template.anchoredPosition = new Vector2(0f, -34f);
            template.sizeDelta = new Vector2(0f, options.Length * 34f + 8f);
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
            content.sizeDelta = new Vector2(0f, options.Length * 34f);

            var item = NewRect("Item", content);
            item.anchorMin = new Vector2(0f, 1f);
            item.anchorMax = Vector2.one;
            item.pivot = new Vector2(0.5f, 1f);
            item.sizeDelta = new Vector2(0f, 34f);
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
