using System.Globalization;
using System.IO;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M0 fps 采集：每秒聚合平均 fps / 帧时间均值与最大值 / 每帧水高查询次数与查询耗时占比，
    /// OnGUI 实时显示并追加 JSON Lines 到 工程根 Logs/fps-report.jsonl。
    /// </summary>
    [DefaultExecutionOrder(200)] // 晚于 TriangleBuoyancyProbe(100) 的 LateUpdate，读取完整帧内统计
    public class FpsProbe : MonoBehaviour
    {
        /// <summary>IMGUI 框屏幕锚角（review S3 2026-09-29：默认 TopLeft+margin(8,8) = M1 原位；
        /// BottomLeft = 贴屏幕底边，M6 避让 WeatherGUI 左上面板）。</summary>
        public enum OverlayAnchor { TopLeft, BottomLeft }

        public static FpsProbe Instance { get; private set; }

        const string k_LogDir = "Logs";
        const string k_LogFile = "fps-report.jsonl";
        const float k_WindowSeconds = 1f;
        const int k_ConsoleLogEveryNWindows = 10; // 每 10 秒往 Console 打一行 SummaryLine
        const float k_BoxWidth = 560f;
        const float k_BoxHeight = 116f;

        [Tooltip("IMGUI 框锚角。TopLeft = M1 原位；BottomLeft = 贴屏幕底边（M6 避让 WeatherGUI 左上面板）。")]
        public OverlayAnchor anchor = OverlayAnchor.TopLeft;
        [Tooltip("锚角到屏幕边距（像素）。")]
        public Vector2 screenMargin = new Vector2(8f, 8f);

        float m_WindowStart = -1f;
        int m_Frames;
        double m_FrameMsSum;
        float m_FrameMsMax;
        int m_Windows;

        GUIStyle m_Style;

        public float LastFps { get; private set; }
        public float LastFrameMsAvg { get; private set; }
        public float LastFrameMsMax { get; private set; }
        public int LastQueriesPerFrame { get; private set; }
        public double LastQueryMsPerFrame { get; private set; }

        [Tooltip("M0 闸门补测专用：Play 2s 后请求固定 2560x1440 backbuffer。普通运行（M1 GUI 交互/截图/录屏、播放器构建）必须保持 false——display topology 动荡下 SetResolution 会把 Game view 退化成幽灵尺寸（实测 2560x36），UGUI 面板下半对射线失联。")]
        public bool requestFixedResolution = false;

        void Awake()
        {
            Instance = this;
            StartCoroutine(RequestFixedRes());
        }

        // M0 复审补测：进 Play 后请求固定 2560x1440 backbuffer（Editor 下 Screen.SetResolution
        // 会 resize Game 视图；是否生效以 jsonl res 字段实测为准，不生效则如实记录实际值）。
        System.Collections.IEnumerator RequestFixedRes()
        {
            if (!requestFixedResolution) yield break;
            yield return new WaitForSecondsRealtime(2f);
            Screen.SetResolution(2560, 1440, FullScreenMode.Windowed);
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void Update()
        {
            float frameMs = Time.unscaledDeltaTime * 1000f;
            m_Frames++;
            m_FrameMsSum += frameMs;
            if (frameMs > m_FrameMsMax) m_FrameMsMax = frameMs;

            if (m_WindowStart < 0f) m_WindowStart = Time.unscaledTime;
        }

        void LateUpdate()
        {
            float elapsed = Time.unscaledTime - m_WindowStart;
            if (elapsed < k_WindowSeconds) return;
            m_WindowStart = Time.unscaledTime;

            LastFps = m_Frames / Mathf.Max(elapsed, 1e-4f);
            LastFrameMsAvg = m_Frames > 0 ? (float)(m_FrameMsSum / m_Frames) : 0f;
            LastFrameMsMax = m_FrameMsMax;
            LastQueriesPerFrame = TriangleBuoyancyProbe.FrameQueries;
            LastQueryMsPerFrame = TriangleBuoyancyProbe.FrameQueryMs;

            WriteJsonLine();
            if (++m_Windows % k_ConsoleLogEveryNWindows == 0)
            {
                Debug.Log($"[Sango.M0] {SummaryLine()}");
            }

            m_Frames = 0;
            m_FrameMsSum = 0.0;
            m_FrameMsMax = 0f;
        }

        void WriteJsonLine()
        {
            // 工程根 Logs/（不入库，.gitignore 覆盖 [Ll]ogs/）。
            string dir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", k_LogDir));
            string path = Path.Combine(dir, k_LogFile);
            try
            {
                Directory.CreateDirectory(dir);
                // 显式 ToString 而非 string.Format：复合格式串尾部 {5:F3}}} 在 .NET 解析下曾输出字面 "F3"。
                // InvariantCulture：避免小数点被本地化成逗号破坏 JSON。
                string I(double v, string f) => v.ToString(f, CultureInfo.InvariantCulture);
                // res = 实际渲染 backbuffer（闸门条件 1440p 的直接证据，随每行落盘）
                string line = "{\"t\":" + I(Time.unscaledTimeAsDouble, "F2")
                    + ",\"res\":\"" + Screen.width + "x" + Screen.height + "\""
                    + ",\"fps\":" + I(LastFps, "F2")
                    + ",\"frame_ms_avg\":" + I(LastFrameMsAvg, "F3")
                    + ",\"frame_ms_max\":" + I(LastFrameMsMax, "F3")
                    + ",\"queries_per_frame\":" + LastQueriesPerFrame
                    + ",\"query_ms_per_frame\":" + I(LastQueryMsPerFrame, "F3") + "}";
                File.AppendAllText(path, line + "\n");
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"[Sango.M0] failed to write {path}: {e.Message}");
            }
        }

        /// <summary>单行汇总，供日志/证据记录。</summary>
        public static string SummaryLine()
        {
            if (Instance == null) return "FpsProbe: no instance in scene";
            return string.Format(
                CultureInfo.InvariantCulture,
                "fps={0:F1} frame_ms_avg={1:F2} frame_ms_max={2:F2} queries_per_frame={3} query_ms_per_frame={4:F2}",
                Instance.LastFps, Instance.LastFrameMsAvg, Instance.LastFrameMsMax,
                Instance.LastQueriesPerFrame, Instance.LastQueryMsPerFrame);
        }

        /// <summary>
        /// IMGUI 框矩形（纯函数，EditMode 可测缝）。BottomLeft 的 y 在调用侧传运行时
        /// Screen.height（序列化只存锚角+边距，不存绝对像素——分辨率无关）。
        /// </summary>
        public static Rect ComputeBoxRect(OverlayAnchor anchor, Vector2 margin, float screenHeight)
        {
            float y = anchor == OverlayAnchor.BottomLeft ? screenHeight - k_BoxHeight - margin.y : margin.y;
            return new Rect(margin.x, y, k_BoxWidth, k_BoxHeight);
        }

        void OnGUI()
        {
            if (m_Style == null)
            {
                m_Style = new GUIStyle(GUI.skin.label)
                {
                    fontSize = 20,
                    fontStyle = FontStyle.Bold,
                };
                m_Style.normal.textColor = Color.white;
            }

            var box = ComputeBoxRect(anchor, screenMargin, Screen.height);
            GUI.Box(box, GUIContent.none);

            string l1 = string.Format(
                CultureInfo.InvariantCulture, "fps: {0:F1}    frame avg/max: {1:F2} / {2:F2} ms",
                LastFps, LastFrameMsAvg, LastFrameMsMax);
            string l2 = string.Format(
                CultureInfo.InvariantCulture, "water queries/frame: {0} (failed {1})    query ms/frame: {2:F2}",
                LastQueriesPerFrame, TriangleBuoyancyProbe.FrameFailedQueries, LastQueryMsPerFrame);
            string l3 = "gate: >= 30 fps @1440p (Script Interactions ON + 6-ship per-triangle queries)";

            // 框内相对偏移 (8,6)/(8,38)/(8,70)：默认锚下与旧绝对坐标 (16,14)/(16,46)/(16,78) 逐像素一致。
            GUI.Label(new Rect(box.x + 8f, box.y + 6f, box.width - 16f, 30f), l1, m_Style);
            GUI.Label(new Rect(box.x + 8f, box.y + 38f, box.width - 16f, 30f), l2, m_Style);
            GUI.Label(new Rect(box.x + 8f, box.y + 70f, box.width - 16f, 30f), l3, m_Style);
        }
    }
}
