using System;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;

namespace Sango
{
    /// <summary>
    /// Twin compact-v1 WS 传输helper（P2-S1 spec #89）：URL 组装 + 阻塞收一帧文本。
    /// ClientWebSocket（.NET 内置，无第三方包）；只在后台线程使用（连接/收包均阻塞），
    /// 停止经 CancellationToken 取消（ReceiveAsync 抛 OperationCanceledException 收线程，
    /// 先例 DetectionResultConsumer 线程模型）。
    /// 端点 = ws://…/ws/sessions/{id}?transport=compact-v1（gui_server/main.py:2180）。
    /// </summary>
    public static class TwinWs
    {
        /// <summary>
        /// 单帧文本上限：首帧 static_included 含 enc safe_water 多边形，S0 实测 483,590 B
        /// （evidence/compact-v1-frames.jsonl 首行），后续帧 ~16 KB；1 MiB 留更大场景余量，
        /// 仅作失控消息兜底。
        /// </summary>
        public const int MaxFrameBytes = 1024 * 1024;

        public static string CompactUrl(string backendBase, string sessionId)
        {
            var baseUri = new Uri(backendBase);
            var wsScheme = baseUri.Scheme == "https" ? "wss" : "ws";
            var builder = new UriBuilder(baseUri)
            {
                Scheme = wsScheme,
                Path = $"/ws/sessions/{sessionId}",
                Query = "transport=compact-v1",
            };
            return builder.Uri.ToString();
        }

        /// <summary>
        /// 阻塞收一条完整文本消息；取消/连接关闭返回 null（调用方收线程）。
        /// 消息分段（EndOfMessage=false）在本地缓冲拼接，超 MaxFrameBytes 判损坏返回 null。
        /// </summary>
        public static string ReceiveText(ClientWebSocket socket, CancellationToken cancellation)
        {
            var buffer = new byte[64 * 1024];
            using (var sink = new MemoryStream())
            {
                while (true)
                {
                    ArraySegment<byte> segment = new ArraySegment<byte>(buffer);
                    WebSocketReceiveResult result;
                    try { result = socket.ReceiveAsync(segment, cancellation).GetAwaiter().GetResult(); }
                    catch (OperationCanceledException) { return null; }
                    if (result.MessageType == WebSocketMessageType.Close) return null;
                    if (sink.Length + result.Count > MaxFrameBytes) return null;
                    sink.Write(buffer, 0, result.Count);
                    if (result.EndOfMessage) return Encoding.UTF8.GetString(sink.ToArray());
                }
            }
        }
    }
}
