using System;
using System.Text;
using Unity.RenderStreaming;
using UnityEngine;
using Unity.WebRTC;

namespace Sango
{
    /// <summary>
    /// twin-bridge 消息面（M5 变体 B 抽象）：TwinBridgeService 只依赖此接口——
    /// 载体可以是 URS RTCDataChannel（<see cref="TwinBridgeChannel"/>，legacy-urs 路由）
    /// 或本机回环 TCP（<see cref="TwinBridgeLocalChannel"/>，gst-xvfb 路由，GStreamer sender
    /// 转发）。语义契约：单 UTF-8 JSON 文本帧、事件回调均在 Unity 主线程。
    /// </summary>
    public interface ITwinBridgeChannel
    {
        /// <summary>web→Unity JSON 原文（主线程回调）。</summary>
        event Action<string> onJson;

        /// <summary>通道 open（每连接一次；重连重发 hello/attach 的钩子）。</summary>
        event Action onOpened;

        /// <summary>通道 close。</summary>
        event Action onClosed;

        /// <summary>当前是否有活跃连接（state 心跳与发送门控）。</summary>
        bool IsConnected { get; }

        /// <summary>已收 JSON 消息计数（日志/探针证据）。</summary>
        int ReceivedCount { get; }

        /// <summary>已发送消息计数。</summary>
        int SentCount { get; }

        /// <summary>发送一条 JSON 文本帧（未连接时丢弃，与 DataChannelBase 行为一致）。</summary>
        void SendJson(string json);
    }

    /// <summary>
    /// twin-bridge-v1 载体（P2-S3 spec #89；契约 sango/Docs/contracts/twin-bridge-v1.md §1）：
    /// URS DataChannel label="twin-bridge"（Unity 侧 local 创建，浏览器 onAddChannel 接收），
    /// 单个 UTF-8 JSON 文本帧双向传递，可靠有序。
    /// 与 spike 的 UrsDataChannelEcho 区别：无 echo、无 clock 广播——消息语义全部上收
    /// <see cref="TwinBridgeService"/>；本组件只做字节 ↔ 文本、计数与生命周期事件。
    /// 线程注意：com.unity.webrtc 回调编组回 Unity 主线程（onJson/状态发送均在主线程）。
    /// </summary>
    public class TwinBridgeChannel : DataChannelBase, ITwinBridgeChannel
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

        public override void SetChannel(string connectionId, RTCDataChannel channel)
        {
            if (channel != null && ConnectionId == connectionId && ReferenceEquals(Channel,channel)) return;
            if (channel == null && !string.IsNullOrEmpty(ConnectionId) && ConnectionId != connectionId) return;
            base.SetChannel(connectionId,channel);
            if (channel == null) { onClosed?.Invoke(); return; }
            // Broadcast can overlap peers on this component. Retain callback
            // ownership so queued messages from an older peer cannot rebind it.
            channel.OnMessage -= OnMessage;
            channel.OnMessage += bytes => DispatchMessage(connectionId,channel,bytes);
        }

        void DispatchMessage(string connectionId, RTCDataChannel sender, byte[] bytes)
        {
            if (ConnectionId == connectionId && ReferenceEquals(Channel,sender)) OnMessage(bytes);
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
            if (ConnectionId != connectionId) return;
            base.OnOpen(connectionId);
            Debug.Log($"[Sango.TwinBridge] channel OPEN conn={connectionId} label={label}");
            onOpened?.Invoke();
        }

        protected override void OnClose(string connectionId)
        {
            bool current = string.IsNullOrEmpty(ConnectionId) || ConnectionId == connectionId;
            base.OnClose(connectionId);
            if (!current) return;
            Debug.Log($"[Sango.TwinBridge] channel CLOSE conn={connectionId}");
            onClosed?.Invoke();
        }
    }
}
