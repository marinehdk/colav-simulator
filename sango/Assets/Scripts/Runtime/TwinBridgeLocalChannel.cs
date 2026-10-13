using System;
using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M5 gst 路由本地桥适配器（DESIGN 2026-10-12-dt-frame-delivery-2k §2 M5①；变体 B）：
    /// <see cref="TwinBridgeChannel"/> 的孪生组件——把 TwinBridgeService 的消息面从
    /// URS RTCDataChannel 换到本机回环 TCP 服务端（127.0.0.1:<see cref="port"/>，GStreamer
    /// sender 为唯一对端，转发 twin-bridge DataChannel 字节）。帧语义对齐：单 UTF-8 JSON
    /// 文本帧、'\n' 分界；onOpened 每连接一次（sender 重连 = web 重发 hello/attach 的钩子）。
    /// 事件与计数全部在 Unity 主线程结算（Pump；TwinBridgeChannel 借 com.unity.webrtc
    /// 编组回主线程，本组件自持队列实现同款约定）。
    /// 载体选 TCP 而非设计的 UDS：sender 在 gst-base 容器（--network host）内，UDS 需给
    /// 容器补宿主 socket 目录卷；回环 TCP 与 sender↔webapp（127.0.0.1:8081）同模式，
    /// 零容器改动。多客户端策略 = 后到者接管（sender 重启旧连接必死，防半开连接滞留）。
    /// </summary>
    [DefaultExecutionOrder(-50)] // 先于 TwinBridgeService.Update 结算入站命令（同帧生效）
    public class TwinBridgeLocalChannel : MonoBehaviour, ITwinBridgeChannel
    {
        public event Action<string> onJson;
        public event Action onOpened;
        public event Action onClosed;

        [Tooltip("回环监听端口（TWIN_BRIDGE_PORT env 覆盖；与 sender --bridge-port 同源）")]
        public int port = SangoSeamConfig.TwinBridgeLocalPort;

        public int ReceivedCount { get; private set; }
        public int SentCount { get; private set; }
        public bool IsConnected
        {
            get { lock (m_StateLock) return m_Client != null && m_Client.Connected; }
        }

        readonly object m_StateLock = new object();
        ConcurrentQueue<Action> m_Dispatch = new ConcurrentQueue<Action>();
        ConcurrentQueue<string> m_Outbound = new ConcurrentQueue<string>();
        readonly AutoResetEvent m_WakeWriter = new AutoResetEvent(false);
        TcpListener m_Listener;
        TcpClient m_Client;
        NetworkStream m_Stream;
        Thread m_AcceptThread;
        Thread m_WriterThread;
        volatile bool m_Running;

        void Awake()
        {
            string envPort = Environment.GetEnvironmentVariable("TWIN_BRIDGE_PORT");
            if (int.TryParse(envPort, out int parsed) && parsed > 0 && parsed < 65536) port = parsed;
        }

        void OnEnable()
        {
            if (Application.isPlaying) StartServing();
        }

        void OnApplicationQuit() => StopServing();

        void OnDestroy() => StopServing();

        void Update() => Pump();

        /// <summary>启动回环监听（播放模式 OnEnable 自动；EditMode 测试显式调用）。幂等。</summary>
        public void StartServing()
        {
            if (m_Running) return;
            m_Running = true;
            m_Listener = new TcpListener(IPAddress.Loopback, port);
            m_Listener.Start();
            m_AcceptThread = new Thread(AcceptLoop) { IsBackground = true, Name = "Sango.TwinBridge.local.accept" };
            m_AcceptThread.Start();
            m_WriterThread = new Thread(WriterLoop) { IsBackground = true, Name = "Sango.TwinBridge.local.writer" };
            m_WriterThread.Start();
            Debug.Log($"[Sango.TwinBridge] local channel serving on 127.0.0.1:{port}");
        }

        /// <summary>停服 + 断开当前连接（幂等；半开连接由 sender 侧重连接管兜底）。</summary>
        public void StopServing()
        {
            if (!m_Running) return;
            m_Running = false;
            try { m_Listener.Stop(); } catch (Exception) { /* 已停 */ }
            lock (m_StateLock)
            {
                if (m_Client != null) { try { m_Client.Close(); } catch (Exception) { } m_Client = null; m_Stream = null; }
            }
            m_WakeWriter.Set();
            if (m_AcceptThread != null && m_AcceptThread.IsAlive && !m_AcceptThread.Join(500)) { } // 后台线程，超时放行
            if (m_WriterThread != null && m_WriterThread.IsAlive && !m_WriterThread.Join(500)) { }
            m_AcceptThread = null;
            m_WriterThread = null;
        }

        /// <summary>主线程结算：连接事件 + 入站 JSON 出队派发。Update 自动；测试可直接调。</summary>
        public void Pump()
        {
            while (m_Dispatch.TryDequeue(out var dispatch))
            {
                try { dispatch(); }
                catch (Exception e) { Debug.LogError($"[Sango.TwinBridge] local dispatch error: {e}"); }
            }
        }

        public void SendJson(string json)
        {
            if (!IsConnected) return;
            SentCount++;
            m_Outbound.Enqueue(json);
            m_WakeWriter.Set();
        }

        void AcceptLoop()
        {
            while (m_Running)
            {
                TcpClient client;
                try { client = m_Listener.AcceptTcpClient(); }
                catch (Exception) { break; } // Stop() 关监听 = 退场
                client.NoDelay = true;
                client.SendTimeout = 250;
                TcpClient old;
                lock (m_StateLock)
                {
                    old = m_Client;
                    m_Client = client;
                    m_Stream = client.GetStream();
                }
                if (old != null) { try { old.Close(); } catch (Exception) { } }
                var reader = new Thread(() => ReadLoop(client)) { IsBackground = true, Name = "Sango.TwinBridge.local.read" };
                reader.Start();
                if (old != null)
                {
                    // 接管 = 旧 epoch 收尾（DetachDataPlane 钩子）→ 新 epoch 开场；FIFO 保序
                    m_Dispatch.Enqueue(() =>
                    {
                        Debug.Log("[Sango.TwinBridge] local channel CLOSE (superseded by new connection)");
                        onClosed?.Invoke();
                    });
                }
                m_Dispatch.Enqueue(() =>
                {
                    Debug.Log($"[Sango.TwinBridge] local channel OPEN (127.0.0.1:{port})" +
                              (old != null ? " (replaced stale connection)" : ""));
                    onOpened?.Invoke();
                });
            }
        }

        void ReadLoop(TcpClient client)
        {
            var buffer = new byte[8192];
            var accumulator = new MemoryStreamChunked();
            try
            {
                var stream = client.GetStream();
                while (m_Running)
                {
                    int read = stream.Read(buffer, 0, buffer.Length);
                    if (read <= 0) break;
                    accumulator.Append(buffer, read);
                    string line;
                    while ((line = accumulator.TakeLine()) != null)
                    {
                        if (line.Length == 0) continue;
                        var json = line;
                        m_Dispatch.Enqueue(() =>
                        {
                            ReceivedCount++;
                            onJson?.Invoke(json);
                        });
                    }
                }
            }
            catch (Exception) { /* EOF/重置：走下方所有权判定 */ }
            bool wasCurrent = false;
            lock (m_StateLock)
            {
                if (ReferenceEquals(m_Client, client)) { m_Client = null; m_Stream = null; wasCurrent = true; }
            }
            if (wasCurrent)
                m_Dispatch.Enqueue(() =>
                {
                    Debug.Log("[Sango.TwinBridge] local channel CLOSE");
                    onClosed?.Invoke();
                });
        }

        void WriterLoop()
        {
            while (m_Running)
            {
                m_WakeWriter.WaitOne(500);
                while (m_Outbound.TryDequeue(out var json))
                {
                    NetworkStream stream;
                    lock (m_StateLock) stream = m_Stream;
                    if (stream == null) continue; // 无连接：丢弃（与 DataChannelBase 未连接语义一致）
                    try
                    {
                        var bytes = Encoding.UTF8.GetBytes(json + "\n");
                        stream.Write(bytes, 0, bytes.Length);
                        stream.Flush();
                    }
                    catch (Exception) { /* 对端僵死：读线程判所有权后触发 onClosed */ }
                }
            }
        }

        /// <summary>面向行分帧的增量缓冲（类名避免与 System.IO.MemoryStream 混淆的内部助手）。</summary>
        class MemoryStreamChunked
        {
            byte[] m_Data = new byte[4096];
            int m_Length;

            public void Append(byte[] source, int count)
            {
                if (m_Length + count > m_Data.Length)
                {
                    var grown = new byte[Math.Max(m_Data.Length * 2, m_Length + count)];
                    Buffer.BlockCopy(m_Data, 0, grown, 0, m_Length);
                    m_Data = grown;
                }
                Buffer.BlockCopy(source, 0, m_Data, m_Length, count);
                m_Length += count;
            }

            /// <summary>取出一条完整 '\n' 行（不含换行）；无完整行返回 null。</summary>
            public string TakeLine()
            {
                int newline = Array.IndexOf(m_Data, (byte)'\n', 0, m_Length);
                if (newline < 0) return null;
                string line = Encoding.UTF8.GetString(m_Data, 0, newline);
                int rest = m_Length - newline - 1;
                Buffer.BlockCopy(m_Data, newline + 1, m_Data, 0, rest);
                m_Length = rest;
                return line;
            }
        }
    }
}
