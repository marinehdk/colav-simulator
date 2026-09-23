using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;
using UnityEngine.UI;

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

        Text _windReadout;
        Text _beaufortValue, _windDirValue, _timeValue, _cloudValue, _fogValue;
        Font _font;
        float _cursorY;
        RectTransform _panel;

        const float PanelWidth = 380f;
        const float ValueRowHeight = 26f; // 标签行高
        const float SliderHeight = 46f;   // 标签行 + 滑条行的总步进

        void Awake()
        {
            if (controller == null) controller = GetComponent<WeatherController>();
            _font = LoadBuiltinFont();
            BuildUI();
            if (controller != null)
            {
                controller.Apply();
                RefreshReadout();
            }
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
                controller.beaufort = Mathf.Round(v * 10f) / 10f; // 0.1 步进
                if (beaufortSlider != null) beaufortSlider.SetValueWithoutNotify(controller.beaufort);
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
                controller.fogDistanceMeters = Mathf.Round(v);
                if (fogSlider != null) fogSlider.SetValueWithoutNotify(controller.fogDistanceMeters);
                OnAnyChanged();
            }, out fogSlider);

            _cursorY -= ValueRowHeight;
            CreateRowLabel("Spectrum tier (JS-PM approx)");
            _cursorY -= ValueRowHeight;
            var tierNames = new[] { "Calm", "Moderate", "Rough", "VeryRough" };
            CreateDropdown(_panel, "TierDropdown", tierNames, controller != null ? (int)controller.spectrumTier : 1, i =>
            {
                if (controller == null) return;
                controller.spectrumTier = (JsPmTier)i;
                OnAnyChanged();
            });

            _panel.sizeDelta = new Vector2(PanelWidth, -_cursorY + 12f);
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

        static void EnsureEventSystem()
        {
            if (EventSystem.current != null)
            {
                Debug.Log($"[Sango.M1] EventSystem exists: {EventSystem.current.name}");
                return;
            }
            // StandaloneInputModule 在 com.unity.ugui 包内（Runtime/UGUI/EventSystem/InputModules/）；
            // 工程未装 com.unity.inputsystem，走旧输入模块即可。
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

        static RectTransform NewRect(string name, Transform parent)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            return rt;
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

        static Image NewImage(string name, Transform parent, Color color)
        {
            var rt = NewRect(name, parent);
            var img = rt.gameObject.AddComponent<Image>();
            img.color = color; // 无 sprite：纯色矩形
            img.raycastTarget = false;
            return img;
        }

        static void Stretch(RectTransform rt, float left, float top, float right, float bottom)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(left, bottom);
            rt.offsetMax = new Vector2(right, -top);
        }
    }
}
