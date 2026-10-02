using System;
using System.Text;
using Unity.RenderStreaming;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// twin-bridge-v1 载体（P2-S3 spec #89；契约 sango/Docs/contracts/twin-bridge-v1.md §1）：
    /// URS DataChannel label="twin-bridge"（Unity 侧 local 创建，浏览器 onAddChannel 接收），
    /// 单个 UTF-8 JSON 文本帧双向传递，可靠有序。
    /// 与 spike 的 UrsDataChannelEcho 区别：无 echo、无 clock 广播——消息语义全部上收
    /// <see cref="TwinBridgeService"/>；本组件只做字节 ↔ 文本、计数与生命周期事件。
    /// 线程注意：com.unity.webrtc 回调编组回 Unity 主线程（onJson/状态发送均在主线程）。
    /// </summary>
    public class TwinBridgeChannel : DataChannelBase
    {
        /// <summary>web→Unity JSON 原文（主线程回调；TwinBridgeService 订阅派发）。</summary>
        public event Action<string> onJson;

        /// <summary>通道 open（每连接一次；重连重发 hello/attach 的钩子）。</summary>
        public event Action onOpened;

        /// <summary>通道 close。</summary>
        public event Action onClosed;

        /// <summary>已收 JSON 消息计数（日志/探针证据）。</summary>
        public int ReceivedCount { get; private set; }

        /// <summary>已发送消息计数。</summary>
        public int SentCount { get; private set; }

        void Awake()
        {
            local = true;
            label = TwinBridge.ChannelLabel;
        }

        public void SendJson(string json)
        {
            if (!IsConnected) return;
            SentCount++;
            Send(json);
        }

        protected override void OnMessage(byte[] bytes)
        {
            ReceivedCount++;
            string json = Encoding.UTF8.GetString(bytes);
            try
            {
                onJson?.Invoke(json);
            }
            catch (Exception e)
            {
                Debug.LogError($"[Sango.TwinBridge] dispatch error: {e}");
            }
        }

        protected override void OnOpen(string connectionId)
        {
            base.OnOpen(connectionId);
            Debug.Log($"[Sango.TwinBridge] channel OPEN conn={connectionId} label={label}");
            onOpened?.Invoke();
        }

        protected override void OnClose(string connectionId)
        {
            base.OnClose(connectionId);
            Debug.Log($"[Sango.TwinBridge] channel CLOSE conn={connectionId}");
            onClosed?.Invoke();
        }
    }
}
