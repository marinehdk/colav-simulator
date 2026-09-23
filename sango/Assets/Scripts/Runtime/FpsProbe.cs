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
        public static FpsProbe Instance { get; private set; }

        const string k_LogDir = "Logs";
        const string k_LogFile = "fps-report.jsonl";
        const float k_WindowSeconds = 1f;
        const int k_ConsoleLogEveryNWindows = 10; // 每 10 秒往 Console 打一行 SummaryLine

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

        void Awake()
        {
            Instance = this;
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

            var box = new Rect(8f, 8f, 560f, 116f);
            GUI.Box(box, GUIContent.none);

            string l1 = string.Format(
                CultureInfo.InvariantCulture, "fps: {0:F1}    frame avg/max: {1:F2} / {2:F2} ms",
                LastFps, LastFrameMsAvg, LastFrameMsMax);
            string l2 = string.Format(
                CultureInfo.InvariantCulture, "water queries/frame: {0} (failed {1})    query ms/frame: {2:F2}",
                LastQueriesPerFrame, TriangleBuoyancyProbe.FrameFailedQueries, LastQueryMsPerFrame);
            string l3 = "gate: >= 30 fps @1440p (Script Interactions ON + 6-ship per-triangle queries)";

            GUI.Label(new Rect(16f, 14f, box.width - 16f, 30f), l1, m_Style);
            GUI.Label(new Rect(16f, 46f, box.width - 16f, 30f), l2, m_Style);
            GUI.Label(new Rect(16f, 78f, box.width - 16f, 30f), l3, m_Style);
        }
    }
}
