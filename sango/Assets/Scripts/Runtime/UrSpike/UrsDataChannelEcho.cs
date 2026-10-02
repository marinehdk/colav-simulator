using System;
using System.Text;
using Unity.RenderStreaming;
using UnityEngine;

namespace Sango.UrSpike
{
    /// <summary>
    /// P2-S2 嵌入决策门 spike（spec #89）：URS 本地 DataChannel（local=true，label="spike-echo"），
    /// 双向 JSON echo——twin-bridge-v1 载体判据的实证组件。浏览器 → Unity：任意 JSON 文本；
    /// Unity 收到即原样回 {"type":"pong",...,"unityRecvUnixMs":...} 并经 onJson 事件交给
    /// UrsSpikeRuntime 派发控制命令。Unity → 浏览器：每秒广播 {"type":"clock","unityUnixMs":...}。
    /// 全部加性，不触碰既有场景语义。
    /// </summary>
    public class UrsDataChannelEcho : DataChannelBase
    {
        /// <summary>浏览器→Unity 收到的 JSON 原文（UrsSpikeRuntime 订阅派发）。</summary>
        public event Action<string> onJson;

        /// <summary>已收到的 JSON 消息计数（日志/证据用）。</summary>
        public int ReceivedCount { get; private set; }

        /// <summary>已发送（echo + clock）消息计数。</summary>
        public int SentCount { get; private set; }

        float m_LastClockSend;

        void Awake()
        {
            local = true;
            label = "spike-echo";
        }

        void Update()
        {
            if (!IsConnected)
                return;
            if (Time.unscaledTime - m_LastClockSend < 1f)
                return;
            m_LastClockSend = Time.unscaledTime;
            Send(Json($"{{\"type\":\"clock\",\"unityUnixMs\":{NowUnixMs()}}}"));
        }

        protected override void OnMessage(byte[] bytes)
        {
            ReceivedCount++;
            string json = Encoding.UTF8.GetString(bytes);
            long recvMs = NowUnixMs();
            // echo：原样回显 + Unity 接收时刻（浏览器端以 sendTs 差算应用层 RTT）
            string echo = Json($"{{\"type\":\"pong\",\"unityRecvUnixMs\":{recvMs},\"echo\":{json}}}");
            Send(echo);
            Debug.Log($"[URS-SPIKE] dc-recv #{ReceivedCount} t={recvMs} bytes={bytes.Length} payload={Truncate(json, 300)}");
            try
            {
                onJson?.Invoke(json);
            }
            catch (Exception e)
            {
                Debug.LogError($"[URS-SPIKE] dc-json dispatch error: {e}");
            }
        }

        /// <summary>发送方注入的单行 JSON（本组件只负责时间戳与计数，序列化在调用方）。</summary>
        string Json(string inner)
        {
            // inner 已是合法 JSON 文本；echo 场景下外层由本方法拼装，此函数保留单点出口便于日志埋点
            SentCount++;
            return inner;
        }

        internal static long NowUnixMs()
        {
            return (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds;
        }

        static string Truncate(string s, int max) => s.Length <= max ? s : s.Substring(0, max) + "…";
    }
}
