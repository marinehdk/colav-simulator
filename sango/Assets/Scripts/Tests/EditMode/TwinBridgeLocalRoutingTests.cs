using System;
using System.Net.Sockets;
using System.Reflection;
using System.Threading;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M5 变体 B 服务路由（DESIGN 2026-10-12-dt-frame-delivery-2k §2 M5①）：useLocalChannel 时
    /// TwinBridgeService 的订阅/发送走 TwinBridgeLocalChannel（ActiveChannel），URS DataChannel
    /// 不参与。端到端：真 TCP 客户端模拟 GStreamer sender，hello → ready（含 video_profiles 上报，
    /// web 降档逻辑依赖）经回环往返。经反射驱动（TwinBridgeClockGuardTests 先例）。
    /// </summary>
    public class TwinBridgeLocalRoutingTests
    {
        const int k_Port = 18171;

        GameObject _go;
        Component _service;
        Component _channel;
        TcpClient _client;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("twin-bridge-local-routing");
            _service = _go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeService"));
            _channel = _go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeLocalChannel"));
            _channel.GetType().GetField("port", BindingFlags.Public | BindingFlags.Instance).SetValue(_channel, k_Port);
            var type = _service.GetType();
            type.GetField("localChannel").SetValue(_service, _channel);
            type.GetField("useLocalChannel").SetValue(_service, true);
        }

        [TearDown]
        public void TearDown()
        {
            _client?.Close();
            _service.GetType().GetMethod("StopBridge").Invoke(_service, null);
            _channel.GetType().GetMethod("StopServing").Invoke(_channel, null);
            if (_go != null) UnityEngine.Object.DestroyImmediate(_go);
        }

        void PumpChannel()
        {
            _channel.GetType().GetMethod("Pump", BindingFlags.Public | BindingFlags.Instance).Invoke(_channel, null);
        }

        bool WaitUntil(Func<bool> predicate, double timeoutS = 8.0)
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(timeoutS);
            while (DateTime.UtcNow < deadline)
            {
                PumpChannel();
                if (predicate()) return true;
                Thread.Sleep(20);
            }
            return false;
        }

        object GetField(string name) =>
            _service.GetType().GetField(name, BindingFlags.NonPublic | BindingFlags.Instance).GetValue(_service);

        /// <summary>读取客户端一行（'\n' 分界）；超时返回 null。</summary>
        string ReadLine(double timeoutS = 8.0)
        {
            var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(timeoutS);
            var stream = _client.GetStream();
            var buffer = new byte[4096];
            using var memory = new System.IO.MemoryStream();
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
        public void LocalChannel_RoutesHelloToReady()
        {
            _service.GetType().GetMethod("StartBridge").Invoke(_service, null);
            Assert.IsTrue((bool)GetField("m_BridgeUp"), "StartBridge 应在本地模式下开桥");

            _channel.GetType().GetMethod("StartServing").Invoke(_channel, null);
            _client = new TcpClient();
            _client.Connect("127.0.0.1", k_Port);
            _client.NoDelay = true;
            Assert.IsTrue(WaitUntil(() => (bool)_channel.GetType().GetProperty("IsConnected").GetValue(_channel)),
                "回环通道未连接");

            var hello = "{\"type\":\"hello\",\"protocol\":\"twin-bridge@1\",\"page\":\"editmode-test\"}\n";
            var bytes = System.Text.Encoding.UTF8.GetBytes(hello);
            _client.GetStream().Write(bytes, 0, bytes.Length);

            Assert.IsTrue(WaitUntil(() => (bool)GetField("m_Helloed")), "hello 未被 ActiveChannel 路由到 HandleJson");
            string ready = ReadLine();
            Assert.IsNotNull(ready, "ready 未经回环通道回程");
            StringAssert.Contains("\"type\":\"ready\"", ready);
            Debug.Log($"[test] ready via local channel: {ready}");
        }
    }
}
