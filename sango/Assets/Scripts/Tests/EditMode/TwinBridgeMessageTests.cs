using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// twin-bridge-v1 契约回环测试（P2-S3 spec #89；沿 DetectionResultRoundTripTests 工艺：
    /// serialize→deserialize→serialize 无损，期望值来自契约文档字面量，不回声实现）。
    /// 契约：sango/Docs/contracts/twin-bridge-v1.md（§6 样例 = 本文件冻结字面量，
    /// 与 tests/web_gui/twin-view.test.mjs 同源对拍）。
    /// </summary>
    public class TwinBridgeMessageTests
    {
        // ── 契约 §6 冻结样例字面量 ────────────────────────────────────────────

        const string k_AttachSample = TwinBridgeCommand.ContractAttachSample;

        const string k_ClockSample =
            "{\"type\":\"clock\",\"playhead_s\":12.5,\"rate\":1,\"state\":\"PLAYING\"}";

        const string k_CameraSample = "{\"type\":\"camera\",\"preset\":\"top\"}";

        const string k_ThemeSample = "{\"type\":\"theme\",\"value\":\"night\"}";

        const string k_DetectionSample = "{\"type\":\"detection\",\"enabled\":true,\"source\":\"truth\"}";

        const string k_HelloSample = "{\"type\":\"hello\",\"protocol\":\"twin-bridge@1\",\"page\":\"s3-probe\"}";

        const string k_AttachedSample =
            "{\"type\":\"attached\",\"run_id\":\"3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb\",\"mode\":\"replay\"," +
            "\"anchor\":{\"east\":544302.5,\"north\":6323000.25},\"ships\":3,\"camera\":\"bridge\"}";

        const string k_StateSample =
            "{\"type\":\"state\",\"fps\":30.5,\"frame_seq\":41,\"sim_time\":12.4,\"clock_skew_ms\":35," +
            "\"stream\":{\"state\":\"ok\",\"latency_ms\":35},\"detection\":{\"source\":\"truth\",\"live\":false}," +
            "\"camera\":\"bridge\"}";

        const string k_ErrorSample = "{\"type\":\"error\",\"code\":\"RUN_NOT_FOUND\",\"message\":\"backend 404\"}";

        // ── web→Unity：契约样例反序列化 ──────────────────────────────────────

        [Test]
        public void AttachSample_DeserializesToDocumentedFields()
        {
            var cmd = TwinBridgeCommand.FromJson(k_AttachSample);
            Assert.That(cmd, Is.Not.Null);
            Assert.That(cmd.type, Is.EqualTo("attach"));
            Assert.That(cmd.run_id, Is.EqualTo("3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb"));
            Assert.That(cmd.mode, Is.EqualTo("replay"));
            Assert.That(cmd.backend_base, Is.EqualTo("http://127.0.0.1:8010"));
            Assert.That(cmd.replay, Is.Not.Null);
            Assert.That(cmd.replay.t_start, Is.EqualTo(0.1).Within(1e-9));
            Assert.That(cmd.replay.t_end, Is.EqualTo(40.0).Within(1e-9));
            Assert.That(cmd.replay.trusted_t_end, Is.EqualTo(40.0).Within(1e-9));
        }

        [Test]
        public void ClockSample_DeserializesToDocumentedFields()
        {
            var cmd = TwinBridgeCommand.FromJson(k_ClockSample);
            Assert.That(cmd.type, Is.EqualTo("clock"));
            Assert.That(cmd.playhead_s, Is.EqualTo(12.5).Within(1e-9));
            Assert.That(cmd.rate, Is.EqualTo(1.0).Within(1e-9));
            Assert.That(cmd.state, Is.EqualTo("PLAYING"));
        }

        [Test]
        public void ControlSamples_DeserializeTypeAndValue()
        {
            var camera = TwinBridgeCommand.FromJson(k_CameraSample);
            Assert.That(camera.type, Is.EqualTo("camera"));
            Assert.That(camera.preset, Is.EqualTo("top"));

            var theme = TwinBridgeCommand.FromJson(k_ThemeSample);
            Assert.That(theme.type, Is.EqualTo("theme"));
            Assert.That(theme.value, Is.EqualTo("night"));

            var detection = TwinBridgeCommand.FromJson(k_DetectionSample);
            Assert.That(detection.type, Is.EqualTo("detection"));
            Assert.That(detection.enabled, Is.True);
            Assert.That(detection.source, Is.EqualTo("truth"));

            var hello = TwinBridgeCommand.FromJson(k_HelloSample);
            Assert.That(hello.type, Is.EqualTo("hello"));
            Assert.That(hello.protocol, Is.EqualTo("twin-bridge@1"));
            Assert.That(hello.page, Is.EqualTo("s3-probe"));
        }

        [Test]
        public void LiveAttach_MissingReplaySpan_ZeroInstance()
        {
            var cmd = TwinBridgeCommand.FromJson(
                "{\"type\":\"attach\",\"run_id\":\"r1\",\"mode\":\"live\",\"backend_base\":\"http://127.0.0.1:8010\"}");
            Assert.That(cmd.mode, Is.EqualTo("live"));
            // JsonUtility 语义（钉死）：嵌套类键缺失 = 零值实例而非 null；
            // zero span 满足 t_end <= t_start，service 对 replay attach 会以 BAD_MESSAGE 拒绝。
            Assert.That(cmd.replay, Is.Not.Null);
            Assert.That(cmd.replay.t_end, Is.EqualTo(0.0).Within(1e-9));
            Assert.That(cmd.replay.t_end <= cmd.replay.t_start, Is.True);
        }

        // ── web→Unity：信封回环（serialize→deserialize→serialize 逐位无损） ──

        [Test]
        public void Attach_Loopback_StringStable()
        {
            var original = new TwinBridgeCommand
            {
                type = "attach",
                run_id = "3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb",
                mode = "replay",
                backend_base = "http://127.0.0.1:8010",
                replay = new TwinBridgeReplaySpan { t_start = 0.1, t_end = 40.0, trusted_t_end = 40.0 },
            };
            var once = JsonUtility.ToJson(original);
            var back = TwinBridgeCommand.FromJson(once);
            var twice = JsonUtility.ToJson(back);
            Assert.That(twice, Is.EqualTo(once), "attach 信封 serialize→deserialize→serialize 逐位无损");
        }

        [Test]
        public void Clock_Loopback_StringStable()
        {
            var original = new TwinBridgeCommand { type = "clock", playhead_s = 12.5, rate = 2.5, state = "PLAYING" };
            var once = JsonUtility.ToJson(original);
            var back = TwinBridgeCommand.FromJson(once);
            Assert.That(back.playhead_s, Is.EqualTo(12.5).Within(1e-9));
            Assert.That(back.rate, Is.EqualTo(2.5).Within(1e-9));
            Assert.That(back.state, Is.EqualTo("PLAYING"));
        }

        // ── Unity→web：样例反序列化 + 回环 ───────────────────────────────────

        [Test]
        public void AttachedSample_DeserializesToDocumentedFields()
        {
            var msg = TwinBridgeAttached.FromJson(k_AttachedSample);
            Assert.That(msg, Is.Not.Null);
            Assert.That(msg.type, Is.EqualTo("attached"));
            Assert.That(msg.run_id, Is.EqualTo("3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb"));
            Assert.That(msg.mode, Is.EqualTo("replay"));
            Assert.That(msg.anchor, Is.Not.Null);
            Assert.That(msg.anchor.east, Is.EqualTo(544302.5).Within(1e-6));
            Assert.That(msg.anchor.north, Is.EqualTo(6323000.25).Within(1e-6));
            Assert.That(msg.ships, Is.EqualTo(3));
            Assert.That(msg.camera, Is.EqualTo("bridge"));
        }

        [Test]
        public void StateSample_DeserializesToDocumentedFields()
        {
            var msg = TwinBridgeState.FromJson(k_StateSample);
            Assert.That(msg.type, Is.EqualTo("state"));
            Assert.That(msg.fps, Is.EqualTo(30.5).Within(1e-9));
            Assert.That(msg.frame_seq, Is.EqualTo(41));
            Assert.That(msg.sim_time, Is.EqualTo(12.4).Within(1e-9));
            Assert.That(msg.clock_skew_ms, Is.EqualTo(35.0).Within(1e-9));
            Assert.That(msg.stream.state, Is.EqualTo("ok"));
            Assert.That(msg.stream.latency_ms, Is.EqualTo(35.0).Within(1e-9));
            Assert.That(msg.detection.source, Is.EqualTo("truth"));
            Assert.That(msg.detection.live, Is.False);
            Assert.That(msg.camera, Is.EqualTo("bridge"));
        }

        [Test]
        public void State_Loopback_StringStable()
        {
            var original = new TwinBridgeState
            {
                fps = 30.5,
                frame_seq = 41,
                sim_time = 12.4,
                clock_skew_ms = 35.0,
                stream = new TwinBridgeStreamHealth { state = "ok", latency_ms = 35.0 },
                detection = new TwinBridgeDetectionState { source = "truth", live = false },
                camera = "top",
            };
            var once = original.ToJson();
            var back = TwinBridgeState.FromJson(once);
            var twice = back.ToJson();
            Assert.That(twice, Is.EqualTo(once), "state serialize→deserialize→serialize 逐位无损");
        }

        [Test]
        public void ReadyAndError_SerializeContractShapes()
        {
            var ready = new TwinBridgeReady { build = "1.0", scene = "SangoTwin" };
            Assert.That(ready.ToJson(), Does.Contain("\"type\":\"ready\""));
            Assert.That(ready.ToJson(), Does.Contain("\"protocol\":\"twin-bridge@1\""));
            Assert.That(ready.ToJson(), Does.Contain("\"modes_supported\":[\"live\",\"replay\"]"));

            var error = new TwinBridgeError { code = TwinBridge.ErrorRunNotFound, message = "backend 404" };
            var round = TwinBridgeError.FromJson(error.ToJson());
            Assert.That(round.code, Is.EqualTo("RUN_NOT_FOUND"));
            Assert.That(round.message, Is.EqualTo("backend 404"));
        }

        // ── 宽松演进：未知字段忽略 + 空文档容忍（契约 §1） ────────────────────

        [Test]
        public void UnknownFields_Tolerated_OnBothDirections()
        {
            var cmd = TwinBridgeCommand.FromJson(
                "{\"type\":\"clock\",\"playhead_s\":1,\"rate\":1,\"state\":\"PLAYING\",\"future_field\":{\"x\":1}}");
            Assert.That(cmd.type, Is.EqualTo("clock"));
            Assert.That(cmd.playhead_s, Is.EqualTo(1.0).Within(1e-9));

            var state = TwinBridgeState.FromJson(
                "{\"type\":\"state\",\"future_field\":7}");
            Assert.That(state, Is.Not.Null);
            Assert.That(state.frame_seq, Is.EqualTo(-1), "缺字段 = 类型默认（web 侧宽松消费对称）");
        }

        // ── 词汇表谓词 ────────────────────────────────────────────────────────

        [Test]
        public void Vocabulary_Validators_MatchContract()
        {
            Assert.That(TwinBridge.IsValidMode("replay"), Is.True);
            Assert.That(TwinBridge.IsValidMode("live"), Is.True);
            Assert.That(TwinBridge.IsValidMode("twin"), Is.False);
            foreach (var preset in new[] { "bridge", "bow", "chase", "top", "overlook" })
                Assert.That(TwinBridge.IsValidPreset(preset), Is.True);
            Assert.That(TwinBridge.IsValidPreset("TopDown"), Is.False, "词汇为 web 侧小写预设名");
            Assert.That(TwinBridge.IsValidTheme("day"), Is.True);
            Assert.That(TwinBridge.IsValidTheme("night"), Is.True);
            Assert.That(TwinBridge.IsValidTheme("dusk"), Is.True);
            Assert.That(TwinBridge.IsValidTheme("dark"), Is.False);
        }

        // ── 重连退避（契约 §5：1s/2s/5s 封顶） ───────────────────────────────

        [Test]
        public void ReconnectBackoff_OneTwoFiveCapped()
        {
            Assert.That(TwinReconnectPolicy.DelaySeconds(0), Is.EqualTo(1.0).Within(1e-9));
            Assert.That(TwinReconnectPolicy.DelaySeconds(1), Is.EqualTo(2.0).Within(1e-9));
            Assert.That(TwinReconnectPolicy.DelaySeconds(2), Is.EqualTo(5.0).Within(1e-9));
            Assert.That(TwinReconnectPolicy.DelaySeconds(3), Is.EqualTo(5.0).Within(1e-9), "封顶 5s");
            Assert.That(TwinReconnectPolicy.DelaySeconds(99), Is.EqualTo(TwinReconnectPolicy.MaxDelaySeconds).Within(1e-9));
            Assert.That(TwinReconnectPolicy.DelaySeconds(-1), Is.EqualTo(1.0).Within(1e-9), "负数 attempt 钳 0");
        }
    }
}
