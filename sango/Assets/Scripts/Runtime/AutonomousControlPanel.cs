using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Sango
{
    /// <summary>
    /// M2-E2 Autonomous Control 按钮（spec #85 Story 3，画面 4）：把 WaypointFollower 的 G 键
    /// demo 语义做成可点击按钮——点击 ⇄ follower.Toggle()，标签逐帧镜像运行态
    /// （Start ⇄ Pause）。屏幕左下角小面板（四角布局：天气左上 / Simulation 右上 /
    /// 本面板左下 / 雷达右下）。键位：G（既有，per-instance 门控在 follower）+
    /// A（本面板重复键，键位账本：0-9/T/F/G/C/V/Q/E/Z/X 均已占用，A 空闲）。
    /// </summary>
    public class AutonomousControlPanel : MonoBehaviour
    {
        [Tooltip("demo 跟随器（M1 演示船）。")]
        public WaypointFollower follower;

        Text _runLabel;
        Font _font;

        void Awake()
        {
            Application.runInBackground = true; // 采集/演示失焦不停渲染（WeatherGUI 同款）
            _font = LoadBuiltinFont();
            BuildUI();
        }

        static Font LoadBuiltinFont()
        {
            Font f = null;
            try { f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { }
            if (f == null) { try { f = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { } }
            return f;
        }

        void BuildUI()
        {
            var canvasGo = new GameObject("AutonomousCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;

            var root = NewRect("AutoRoot", canvasGo.transform);
            root.anchorMin = root.anchorMax = root.pivot = new Vector2(0f, 0f);
            root.anchoredPosition = new Vector2(20f, 20f);
            root.sizeDelta = new Vector2(300f, 118f);
            var bg = root.gameObject.AddComponent<Image>();
            bg.color = new Color(0f, 0f, 0f, 0.7f);

            var title = CreateLabel(root, "Title", "AUTONOMOUS CONTROL", 17, TextAnchor.MiddleLeft, new Color(0.75f, 0.95f, 0.8f));
            var trt = title.rectTransform;
            trt.anchorMin = trt.anchorMax = trt.pivot = new Vector2(0f, 1f);
            trt.anchoredPosition = new Vector2(14f, -8f);
            trt.sizeDelta = new Vector2(272f, 22f);

            var btnRt = NewRect("RunButton", root);
            btnRt.anchorMin = btnRt.anchorMax = btnRt.pivot = new Vector2(0f, 1f);
            btnRt.anchoredPosition = new Vector2(14f, -36f);
            btnRt.sizeDelta = new Vector2(272f, 44f);
            var btnImg = btnRt.gameObject.AddComponent<Image>();
            btnImg.color = new Color(0.16f, 0.22f, 0.30f, 0.95f);
            btnImg.raycastTarget = true; // EventSystem 射线命中 raycastable Graphic 才派发（M1-C 事故纪律）
            var btn = btnRt.gameObject.AddComponent<Button>();
            btn.targetGraphic = btnImg;
            var colors = btn.colors;
            colors.highlightedColor = new Color(0.26f, 0.36f, 0.50f, 0.95f);
            colors.pressedColor = new Color(0.10f, 0.14f, 0.20f, 0.95f);
            btn.colors = colors;
            btn.onClick.AddListener(ToggleDemo);
            _runLabel = CreateLabel(btnRt, "RunLabel", "Start", 18, TextAnchor.MiddleCenter, Color.white);
            _runLabel.rectTransform.anchorMin = Vector2.zero;
            _runLabel.rectTransform.anchorMax = Vector2.one;
            _runLabel.rectTransform.offsetMin = new Vector2(4f, 4f);
            _runLabel.rectTransform.offsetMax = new Vector2(-4f, -4f);

            var hint = CreateLabel(root, "Hint", "G / A toggle · route: berth -> archipelago loop", 13, TextAnchor.MiddleLeft, new Color(0.6f, 0.65f, 0.7f));
            var hrt = hint.rectTransform;
            hrt.anchorMin = hrt.anchorMax = hrt.pivot = new Vector2(0f, 1f);
            hrt.anchoredPosition = new Vector2(14f, -86f);
            hrt.sizeDelta = new Vector2(272f, 18f);
        }

        // 键鼠同路：A 键与按钮都走 Toggle → 同一标签镜像（EncounterPanel 纪律）。
        // A 键不直接调 follower.Toggle() 而经本面板，保证日志/镜像单一路径。
        void Update()
        {
            if (Input.GetKeyDown(KeyCode.A)) ToggleDemo();
            if (_runLabel != null && follower != null)
                _runLabel.text = follower.DemoRunning ? "Pause" : "Start";
        }

        void ToggleDemo()
        {
            if (follower == null) return;
            follower.Toggle();
            Debug.Log($"[Sango.M2E2] autonomous control -> {(follower.DemoRunning ? "RUNNING" : "STOPPED")} (A/button; G unchanged)");
        }

        // ── uGUI 小件（WeatherGUI 同款最小件）────────────────────────────────────────

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
    }
}
