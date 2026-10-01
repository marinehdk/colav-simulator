using UnityEngine;
using UnityEngine.UI;
using static Sango.UiBuildHelpers;

namespace Sango
{
    /// <summary>
    /// M2-E2 雷达覆盖层（spec #85 Story 3，plan §3 决策 13 的真值 blip 版）：屏幕右下角圆形盘，
    /// 北向上（encounter 俯视同款海图方向）。盘面 = 运行时生成纹理（量程环 1/2 与满量程 +
    /// 十字刻线 + 外缘），扫描线 = 细长条 Image 绕盘心旋转（角度自北顺时针），blip = 其他船
    /// 当前真值位置（RadarMath.BlipNormalized；出量程隐藏），盘心点 = 本船（own-centered）。
    /// 量程/转速面板驱动（SimulationPanel 滑条即时生效），Q/E 调量程、Z/X 调转速（键位账本：
    /// 0-9/T/F 天气、G demo、C 相机、V 矢量——Q/E/Z/X 空闲）。
    /// 无真实信号处理/地杂波（spec Out of Scope）。顺带承担 overlays fps 采样（story 8，
    /// 每 10 s 一行日志供真机闸门取证）。
    /// </summary>
    public class RadarOverlay : MonoBehaviour
    {
        [Tooltip("本船 Transform（盘心；空 = 原点）。")]
        public Transform ownShip;

        [Tooltip("其他船 Transform 列表（真值 blip；出量程隐藏）。")]
        public Transform[] otherShips = System.Array.Empty<Transform>();

        /// <summary>当前量程（米）。SimulationPanel 滑条 / Q/E 修改。</summary>
        public float RangeM { get; private set; } = 600f;

        /// <summary>扫描转速（度/秒）。SimulationPanel 滑条 / Z/X 修改。</summary>
        public float SweepSpeedDegPerSec { get; private set; } = 45f;

        // 量程/转速档位（面板滑条与 Q/E、Z/X 共用同一钳制）。
        public const float RangeMinM = 200f, RangeMaxM = 2000f, RangeStepM = 100f;
        public const float SweepMinDegPerSec = 15f, SweepMaxDegPerSec = 720f, SweepStepDegPerSec = 15f;

        const int k_DiscPixels = 256;         // 生成纹理边长
        const float k_DiscUiSize = 280f;      // 盘 UI 直径
        const float k_TexRadius = 120f;       // 纹理内盘半径（半边 128，留 8px 外缘）
        const float k_BlipSize = 10f;

        RectTransform m_DiscRect;
        RectTransform m_Sweep;
        Image[] m_Blips;
        Text m_Readout;
        float m_SweepAngle;
        int m_FpsFrames;
        float m_FpsAccum;

        float UiRadius => k_DiscUiSize * 0.5f * (k_TexRadius / (k_DiscPixels * 0.5f)); // 纹理半径 → UI 半径

        void Awake()
        {
            Application.runInBackground = true; // 采集/演示失焦不停渲染（WeatherGUI 同款）
            BuildUI();
        }

        void Update()
        {
            HandleHotkeys();

            m_SweepAngle = Mathf.Repeat(m_SweepAngle + SweepSpeedDegPerSec * Time.deltaTime, 360f);
            if (m_Sweep != null) m_Sweep.localRotation = Quaternion.Euler(0f, 0f, -m_SweepAngle); // 顺时针（屏幕系取负）
            UpdateBlips();
            UpdateReadout();

            // overlays fps 采样（10 s 滑窗均值，story 8 闸门 ≥30 fps 的日志证据）。
            m_FpsFrames++;
            m_FpsAccum += Time.unscaledDeltaTime;
            if (m_FpsAccum >= 10f)
            {
                Debug.Log($"[Sango.M2E2] overlays fps (10 s avg) = {m_FpsFrames / m_FpsAccum:F1} (gate >= 30)");
                m_FpsFrames = 0;
                m_FpsAccum = 0f;
            }
        }

        // ── 面板驱动接口（SimulationPanel 滑条即时生效；键位走同一入口）────────────────

        public void SetRange(float meters)
        {
            RangeM = Mathf.Clamp(meters, RangeMinM, RangeMaxM);
            Debug.Log($"[Sango.M2E2] radar range -> {RangeM:0} m");
        }

        public void SetSweepSpeed(float degPerSec)
        {
            SweepSpeedDegPerSec = Mathf.Clamp(degPerSec, SweepMinDegPerSec, SweepMaxDegPerSec);
            Debug.Log($"[Sango.M2E2] radar sweep speed -> {SweepSpeedDegPerSec:0} deg/s");
        }

        public void SetShips(Transform ego, Transform[] targets)
        {
            ownShip = ego;
            otherShips = targets ?? System.Array.Empty<Transform>();
            if (m_DiscRect == null) return;
            if (m_Blips != null) foreach (var blip in m_Blips) if (blip != null)
            {
                if (Application.isPlaying) Destroy(blip.gameObject); else DestroyImmediate(blip.gameObject);
            }
            BuildBlips();
        }

        // ── 键位（Q/E 量程、Z/X 转速；每次键入都有日志行，键位账本见类注）─────────────

        void HandleHotkeys()
        {
            if (Input.GetKeyDown(KeyCode.Q)) SetRange(RangeM - RangeStepM);
            if (Input.GetKeyDown(KeyCode.E)) SetRange(RangeM + RangeStepM);
            if (Input.GetKeyDown(KeyCode.Z)) SetSweepSpeed(SweepSpeedDegPerSec - SweepStepDegPerSec);
            if (Input.GetKeyDown(KeyCode.X)) SetSweepSpeed(SweepSpeedDegPerSec + SweepStepDegPerSec);
        }

        /// <summary>真值 blip：其他船归一化盘面坐标 → 盘上位置；出量程隐藏。</summary>
        void UpdateBlips()
        {
            if (m_Blips == null) return;
            var own = ownShip != null
                ? new Vector2(ownShip.position.x, ownShip.position.z)
                : Vector2.zero;
            for (int i = 0; i < m_Blips.Length; i++)
            {
                var blip = m_Blips[i];
                if (blip == null) continue;
                var t = otherShips[i];
                if (t == null) { blip.gameObject.SetActive(false); continue; }
                var txz = new Vector2(t.position.x, t.position.z);
                if (!RadarMath.InRange(own, txz, RangeM))
                {
                    blip.gameObject.SetActive(false); // 出量程 = 无回波（真值显示不做衰减边瓣）
                    continue;
                }
                var norm = RadarMath.BlipNormalized(own, txz, RangeM); // (右=东, 上=北)
                blip.gameObject.SetActive(true);
                blip.rectTransform.anchoredPosition = norm * UiRadius;
            }
        }

        void UpdateReadout()
        {
            if (m_Readout != null) m_Readout.text = $"RNG {RangeM:0} m · SWE {SweepSpeedDegPerSec:0}°/s";
        }

        // ── UI 构建（WeatherGUI idiom：运行时 UGUI、legacy Text、零资产依赖）────────────

        void BuildUI()
        {
            var canvasGo = new GameObject("RadarCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;

            // 右下角簇，但横向避让 Simulation 面板列（验收修正 2026-09-24：1600×900 下面板
            // 底行（Apply）压住本盘 "RADAR" 标题——同一 1920×1080 参考系内两面板分列即
            // 分辨率无关不重叠）：Simulation 面板占 x ∈ [1500,1900]，本盘宽 304，右缘挪到
            // x=1480（anchoredPosition.x = −460），占 x ∈ [1176,1480]。
            var root = NewRect("RadarRoot", canvasGo.transform);
            root.anchorMin = root.anchorMax = root.pivot = new Vector2(1f, 0f);
            root.anchoredPosition = new Vector2(-460f, 20f);
            root.sizeDelta = new Vector2(k_DiscUiSize + 24f, k_DiscUiSize + 92f);

            var title = CreateLabel(root, "Title", "TRUTH RADAR", 18, TextAnchor.MiddleLeft, new Color(0.75f, 0.95f, 0.8f));
            var trt = title.rectTransform;
            trt.anchorMin = trt.anchorMax = trt.pivot = new Vector2(1f, 1f);
            trt.anchoredPosition = new Vector2(-12f, -6f);
            trt.sizeDelta = new Vector2(200f, 24f);

            // 盘面：生成纹理（环 + 刻线 + 外缘一体），北向上。
            m_DiscRect = NewRect("Disc", root);
            m_DiscRect.anchorMin = m_DiscRect.anchorMax = new Vector2(1f, 1f);
            m_DiscRect.pivot = new Vector2(0.5f, 0.5f);
            m_DiscRect.anchoredPosition = new Vector2(-(k_DiscUiSize + 24f) / 2f, -k_DiscUiSize / 2f - 34f);
            m_DiscRect.sizeDelta = new Vector2(k_DiscUiSize, k_DiscUiSize);
            var disc = m_DiscRect.gameObject.AddComponent<Image>();
            disc.sprite = MakeDiscSprite();
            disc.raycastTarget = false;

            // 扫描线：细长条，pivot 在盘心一端，绕 z 旋转（-角度 = 屏幕顺时针）。
            m_Sweep = NewRect("Sweep", m_DiscRect);
            m_Sweep.anchorMin = m_Sweep.anchorMax = new Vector2(0.5f, 0.5f);
            m_Sweep.pivot = new Vector2(0f, 0.5f);
            m_Sweep.anchoredPosition = Vector2.zero;
            m_Sweep.sizeDelta = new Vector2(UiRadius, 3f);
            var sweepImg = m_Sweep.gameObject.AddComponent<Image>();
            sweepImg.color = new Color(0.45f, 1f, 0.6f, 0.9f);
            sweepImg.raycastTarget = false;

            // 盘心本船点。
            var own = NewRect("OwnDot", m_DiscRect);
            own.anchorMin = own.anchorMax = new Vector2(0.5f, 0.5f);
            own.sizeDelta = new Vector2(8f, 8f);
            var ownImg = own.gameObject.AddComponent<Image>();
            ownImg.color = new Color(0.95f, 1f, 0.98f);
            ownImg.raycastTarget = false;

            // 其他船 blip（真值位置逐帧刷）。
            BuildBlips();

            // 北标记（盘顶）。
            var north = CreateLabel(m_DiscRect, "North", "N", 18, TextAnchor.MiddleCenter, new Color(0.6f, 1f, 0.7f));
            var nrt = north.rectTransform;
            nrt.anchorMin = nrt.anchorMax = new Vector2(0.5f, 1f);
            nrt.pivot = new Vector2(0.5f, 0f);
            nrt.anchoredPosition = new Vector2(0f, -2f);
            nrt.sizeDelta = new Vector2(24f, 22f);

            // 读数行（盘下）。
            m_Readout = CreateLabel(root, "Readout", "", 17, TextAnchor.MiddleRight, new Color(0.75f, 0.95f, 0.8f));
            var rrt = m_Readout.rectTransform;
            rrt.anchorMin = rrt.anchorMax = rrt.pivot = new Vector2(1f, 1f);
            rrt.anchoredPosition = new Vector2(-12f, -k_DiscUiSize - 46f);
            rrt.sizeDelta = new Vector2(k_DiscUiSize + 12f, 22f);

            var hint = CreateLabel(root, "Hint", "Q/E range · Z/X sweep", 13, TextAnchor.MiddleRight, new Color(0.55f, 0.62f, 0.58f));
            var hrt = hint.rectTransform;
            hrt.anchorMin = hrt.anchorMax = hrt.pivot = new Vector2(1f, 1f);
            hrt.anchoredPosition = new Vector2(-12f, -k_DiscUiSize - 68f);
            hrt.sizeDelta = new Vector2(k_DiscUiSize + 12f, 18f);
        }

        void BuildBlips()
        {
            m_Blips = new Image[otherShips.Length];
            for (int i = 0; i < m_Blips.Length; i++)
            {
                var b = NewRect($"Blip.{i}", m_DiscRect);
                b.anchorMin = b.anchorMax = new Vector2(0.5f, 0.5f);
                b.sizeDelta = new Vector2(k_BlipSize, k_BlipSize);
                var image = b.gameObject.AddComponent<Image>();
                image.color = new Color(1f, 0.45f, 0.15f);
                image.raycastTarget = false;
                m_Blips[i] = image;
            }
        }

        /// <summary>
        /// 盘面纹理一体生成：暗绿半透明盘 + 半量程/满量程环 + 十字刻线 + 亮外缘（2 px 抗锯齿近似）。
        /// 北向上、右=东（纹理 +x 右 +y 上与 UI 一致）。
        /// </summary>
        static Sprite MakeDiscSprite()
        {
            int size = k_DiscPixels;
            float half = size * 0.5f;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            var cClear = new Color(0f, 0f, 0f, 0f);
            var cBase = new Color(0.03f, 0.09f, 0.05f, 0.82f);
            var cRing = new Color(0.30f, 0.95f, 0.45f, 0.9f);
            var cCross = new Color(0.20f, 0.60f, 0.30f, 0.35f);
            var cRim = new Color(0.35f, 0.95f, 0.50f, 1f);
            var pixels = new Color[size * size];
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = x + 0.5f - half;
                    float dy = y + 0.5f - half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    var c = cClear;
                    if (r <= k_TexRadius)
                    {
                        c = cBase;
                        bool ring = Mathf.Abs(r - k_TexRadius * 0.5f) < 1.5f || Mathf.Abs(r - k_TexRadius) < 1.5f;
                        bool cross = Mathf.Abs(dx) < 1f || Mathf.Abs(dy) < 1f;
                        if (ring) c = cRing;
                        else if (cross) c = cCross;
                    }
                    else if (r <= k_TexRadius + 3f)
                    {
                        c = cRim; // 亮外缘（量程边界视觉强调）
                    }
                    pixels[y * size + x] = c;
                }
            }
            tex.SetPixels(pixels);
            tex.filterMode = FilterMode.Bilinear;
            tex.Apply(false, true);
            return Sprite.Create(tex, new Rect(0f, 0f, size, size), new Vector2(0.5f, 0.5f), size);
        }

        // ── uGUI 小件：NewRect/LoadBuiltinFont 已收编 UiBuildHelpers（W1 review，同命名空间直用；本面板无交互件）

        static Text CreateLabel(Transform parent, string name, string content, int fontSize, TextAnchor align, Color color)
        {
            var rt = NewRect(name, parent);
            var text = rt.gameObject.AddComponent<Text>();
            text.font = LoadBuiltinFont();
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
