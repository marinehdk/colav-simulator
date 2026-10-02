using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P3 残留清零批 F10：TwinBridgeService.HandleClock 对非有限 playhead_s（NaN/±Inf）的拒绝闸
    /// （spec #89 收尾）。web 端 JSON 无法表达非有限数，此路只可能来自不合契约的客户端——
    /// 拒绝（不进钳位/回退 seek 判定，防 m_Playhead 被污染让计量/对拍全失真）并计 malformed。
    /// TwinBridgeService 在 Assembly-CSharp（Runtime 根无 asmdef），经反射驱动
    /// （CameraRigFreePoseTests / TwinSogVisualDriveTests 先例）；命令 DTO 在 Sango.Vessels 直接引用。
    /// </summary>
    public class TwinBridgeClockGuardTests
    {
        GameObject _go;
        Component _service;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("twin-bridge-clock-guard");
            _service = _go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeService"));
            var type = _service.GetType();
            // 最小 replay 会话态：span [0,40]、playhead 已在 5、无已喂帧（不触发回退 seek 分支）。
            type.GetField("m_Mode", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .SetValue(_service, "replay");
            type.GetField("m_SpanStart", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .SetValue(_service, 0.0);
            type.GetField("m_SpanEnd", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .SetValue(_service, 40.0);
            type.GetField("m_Playhead", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .SetValue(_service, 5.0);
            type.GetField("m_LastOfferedSim", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .SetValue(_service, double.NegativeInfinity);
        }

        [TearDown]
        public void TearDown()
        {
            if (_go != null) Object.DestroyImmediate(_go);
        }

        void SendClock(double playhead, double rate, string state)
        {
            _service.GetType()
                .GetMethod("HandleClock", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .Invoke(_service, new object[] { new TwinBridgeCommand { type = "clock", playhead_s = playhead, rate = rate, state = state } });
        }

        double Playhead => (double)_service.GetType()
            .GetField("m_Playhead", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
            .GetValue(_service);

        string PlayState => (string)_service.GetType()
            .GetField("m_PlayState", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
            .GetValue(_service);

        double Rate => (double)_service.GetType()
            .GetField("m_Rate", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
            .GetValue(_service);

        int Malformed => (int)_service.GetType()
            .GetProperty("MalformedClockCount").GetValue(_service);

        [Test]
        public void NonFinitePlayhead_RejectedCounted_StateUntouched()
        {
            Assert.That(Malformed, Is.EqualTo(0));

            SendClock(double.NaN, 1.0, "PLAYING");
            Assert.That(Malformed, Is.EqualTo(1), "NaN 计 malformed");
            Assert.That(Playhead, Is.EqualTo(5.0).Within(1e-9), "NaN 不进钳位，playhead 不被污染");
            Assert.That(PlayState, Is.EqualTo("PAUSED"), "拒绝时 state 不切换");

            SendClock(double.PositiveInfinity, 5.0, "PLAYING");
            Assert.That(Malformed, Is.EqualTo(2), "+Inf 同拒");
            Assert.That(Rate, Is.EqualTo(1.0).Within(1e-9), "拒绝时 rate 不被改写");

            SendClock(double.NegativeInfinity, 1.0, "PAUSED");
            Assert.That(Malformed, Is.EqualTo(3), "−Inf 同拒");
            Assert.That(Playhead, Is.EqualTo(5.0).Within(1e-9));
        }

        [Test]
        public void FinitePlayhead_StillApplies_AfterRejections()
        {
            SendClock(double.NaN, 1.0, "PLAYING");
            Assert.That(Malformed, Is.EqualTo(1));

            SendClock(12.5, 2.0, "PLAYING");
            Assert.That(Playhead, Is.EqualTo(12.5).Within(1e-9), "有限值照常应用（span 内不钳位）");
            Assert.That(Rate, Is.EqualTo(2.0).Within(1e-9));
            Assert.That(PlayState, Is.EqualTo("PLAYING"));
            Assert.That(Malformed, Is.EqualTo(1), "正常 clock 不计 malformed");

            SendClock(999.0, 1.0, "PLAYING"); // 超出 span → 钳到 40
            Assert.That(Playhead, Is.EqualTo(40.0).Within(1e-9), "钳位语义原样");
        }
    }
}
