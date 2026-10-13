using System;
using System.IO;
using System.Net.Sockets;
using System.Reflection;
using System.Threading;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M5（DESIGN 2026-10-12-dt-frame-delivery-2k §2 M5①）本地桥适配器 TwinBridgeLocalChannel
    /// 的回环收发/分帧/重连接管语义。组件在 Assembly-CSharp（Runtime 根无 asmdef），经反射驱动
    /// （TwinBridgeClockGuardTests 先例）；真 TCP 回环（127.0.0.1:18170，测试专用端口）。
    /// </summary>
    public class TwinBridgeLocalChannelTests
    {
        const int k_Port = 18170;

        GameObject _go;
        Component _channel;
        TcpClient _client;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("twin-bridge-local-channel");
            _channel = _go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeLocalChannel"));
            SetField("port", k_Port);
        }

        [TearDown]
        public void TearDown()
        {
            _client?.Close();
            Invoke("StopServing");
            if (_go != null) UnityEngine.Object.DestroyImmediate(_go);
        }

        void SetField(string name, object value) =>
            _channel.GetType().GetField(name, BindingFlags.Public | BindingFlags.Instance).SetValue(_channel, value);

        object GetProp(string name) =>
            _channel.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance).GetValue(_channel);

        object Invoke(string name)
        {
            var method = _channel.GetType().GetMethod(name, BindingFlags.Public | BindingFlags.Instance);
            return method != null ? method.Invoke(_channel, null) : null;
        }

        void Subscribe(string eventName, Action handler)
        {
            _channel.GetType().GetEvent(eventName, BindingFlags.Public | BindingFlags.Instance)
                .AddEventHandler(_channel, handler);
        }

        void Subscribe(string eventName, Action<string> handler)
        {
            _channel.GetType().GetEvent(eventName, BindingFlags.Public | BindingFlags.Instance)
                .AddEventHandler(_channel, handler);
        }

        /// <summary> Pump + 小睡轮询，直到谓词成立或超时（秒）。 </summary>
        bool WaitUntil(Func<bool> predicate, double timeoutS = 5.0)
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(timeoutS);
            while (DateTime.UtcNow < deadline)
            {
                Invoke("Pump");
                if (predicate()) return true;
                Thread.Sleep(20);
            }
            return false;
        }

        void ConnectClient()
        {
            _client = new TcpClient();
            _client.Connect("127.0.0.1", k_Port);
            _client.NoDelay = true;
        }

        void SendToChannel(params byte[] bytes) => _client.GetStream().Write(bytes, 0, bytes.Length);

        string ReadLineFromClient(double timeoutS = 5.0)
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(timeoutS);
            var stream = _client.GetStream();
            var buffer = new byte[4096];
            using var memory = new MemoryStream();
            while (DateTime.UtcNow < deadline)
            {
                while (stream.DataAvailable)
                {
                    int read = stream.Read(buffer, 0, buffer.Length);
                    if (read <= 0) break;
                    memory.Write(buffer, 0, read);
                    var bytes = memory.ToArray();
                    int newline = Array.IndexOf(bytes, (byte)'\n');
                    if (newline >= 0)
                        return System.Text.Encoding.UTF8.GetString(bytes, 0, newline);
                }
                Thread.Sleep(10);
            }
            return null;
        }

        [Test]
        public void StartServing_AcceptsAndOpens()
        {
            bool opened = false;
            Subscribe("onOpened", () => opened = true);
            Invoke("StartServing");
            ConnectClient();
            Assert.IsTrue(WaitUntil(() => opened), "onOpened 未在连接后派发（主线程 Pump 语义）");
            Assert.IsTrue((bool)GetProp("IsConnected"));
        }

        [Test]
        public void InboundLine_RaisesOnJsonOnMainThread()
        {
            var received = new System.Collections.Generic.List<string>();
            Subscribe("onJson", json => received.Add(json));
            Invoke("StartServing");
            ConnectClient();
            Assert.IsTrue(WaitUntil(() => (bool)GetProp("IsConnected")), "连接未建立");

            SendToChannel(System.Text.Encoding.UTF8.GetBytes("{\"type\":\"hello\"}\n"));
            Assert.IsTrue(WaitUntil(() => received.Count == 1), "入站 JSON 未派发");
            Assert.AreEqual("{\"type\":\"hello\"}", received[0]);
            Assert.AreEqual(1, (int)GetProp("ReceivedCount"));
        }

        [Test]
        public void InboundSplitAcrossPackets_AssemblesIntoSingleMessage()
        {
            var received = new System.Collections.Generic.List<string>();
            Subscribe("onJson", json => received.Add(json));
            Invoke("StartServing");
            ConnectClient();
            Assert.IsTrue(WaitUntil(() => (bool)GetProp("IsConnected")));

            var bytes = System.Text.Encoding.UTF8.GetBytes("{\"type\":\"clock\",\"play");
            SendToChannel(bytes);
            Invoke("Pump");
            Assert.IsEmpty(received, "半条消息不得提前派发");

            SendToChannel(System.Text.Encoding.UTF8.GetBytes("head_s\":1}\n{\"type\":\"pick\"}\n"));
            Assert.IsTrue(WaitUntil(() => received.Count == 2), "补齐后两条消息应先后派发");
            Assert.AreEqual("{\"type\":\"clock\",\"playhead_s\":1}", received[0]);
            Assert.AreEqual("{\"type\":\"pick\"}", received[1]);
        }

        [Test]
        public void SendJson_WritesNewlineFramedUtf8ToSocket()
        {
            Invoke("StartServing");
            ConnectClient();
            Assert.IsTrue(WaitUntil(() => (bool)GetProp("IsConnected")));

            _channel.GetType().GetMethod("SendJson", BindingFlags.Public | BindingFlags.Instance)
                .Invoke(_channel, new object[] { "{\"type\":\"ready\"}" });
            string line = ReadLineFromClient();
            Assert.AreEqual("{\"type\":\"ready\"}", line);
            Assert.AreEqual(1, (int)GetProp("SentCount"));
        }

        [Test]
        public void SendJson_WithoutConnection_IsDroppedSilently()
        {
            Invoke("StartServing");
            _channel.GetType().GetMethod("SendJson", BindingFlags.Public | BindingFlags.Instance)
                .Invoke(_channel, new object[] { "{\"type\":\"state\"}" });
            Invoke("Pump");
            Assert.AreEqual(0, (int)GetProp("SentCount"), "未连接发送应丢弃（DataChannelBase 同语义）");
        }

        [Test]
        public void SecondConnection_TakesOver_AndFiresClosedThenOpened()
        {
            int opened = 0, closed = 0;
            Subscribe("onOpened", () => opened++);
            Subscribe("onClosed", () => closed++);
            Invoke("StartServing");
            ConnectClient();
            Assert.IsTrue(WaitUntil(() => opened == 1), "首连接未 open");

            var second = new TcpClient();
            second.Connect("127.0.0.1", k_Port);
            Assert.IsTrue(WaitUntil(() => opened == 2 && closed == 1),
                "后到者接管：旧连接 close + 新连接 open（防 sender 重启后半开滞留）");
            Assert.IsTrue((bool)GetProp("IsConnected"));
            second.Close();
        }

        [Test]
        public void ClientDisconnect_FiresClosedOnPump()
        {
            int closed = 0;
            Subscribe("onClosed", () => closed++);
            Invoke("StartServing");
            ConnectClient();
            Assert.IsTrue(WaitUntil(() => (bool)GetProp("IsConnected")));

            _client.Close();
            _client = null;
            Assert.IsTrue(WaitUntil(() => closed == 1), "对端断开未派发 onClosed（DetachDataPlane 钩子）");
            Assert.IsFalse((bool)GetProp("IsConnected"));
        }
    }
}
