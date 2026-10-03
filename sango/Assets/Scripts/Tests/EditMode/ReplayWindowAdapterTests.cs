using System.IO;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P2-S1 sealed 回放适配层测试（spec #89；纯映射）。
    /// fixture = 真 REST 响应裁剪件（Assets/Tests/Fixtures/）：
    /// - replay-window-sample.json：GET /api/runs/745d63fd…/replay/window?from=10&amp;to=12
    ///   （READY 密封 run，head_on，2026-09-23 录制；2026-10-02 抓取）。裁剪：只留 frames[0..1]，
    ///   每船 payload 只留 id/mmsi/state/csog_state/turn_rate/active；provenance 见文件内字段。
    /// - replay-context-sample.json：同 run /replay/context 全文（enc 原点 + ships 静态尺寸）。
    /// 形状参照 gui_server/replay.py window() 与 web_gui/modules/replay-source.js localShips()：
    /// payload.ShipN.state = [north, east, psi, u, v, r]，csog_state = [north, east, sog, cog]，
    /// length/width 只在 context.ships。期望值全部来自录制事实，不回声实现。
    /// </summary>
    public class ReplayWindowAdapterTests
    {
        const string k_FixtureDir = "Tests/Fixtures";

        static string ReadFixture(string name)
        {
            string path = Path.Combine(Application.dataPath, k_FixtureDir, name);
            Assert.That(File.Exists(path), Is.True, $"fixture 缺失：{path}");
            return File.ReadAllText(path);
        }

        static (ReplayWindowDocument window, ReplayStaticContext context) Load()
        {
            return (ReplayWindowAdapter.WindowFromJson(ReadFixture("replay-window-sample.json")),
                    ReplayWindowAdapter.ContextFromJson(ReadFixture("replay-context-sample.json")));
        }

        [Test]
        public void Fixtures_AreRealSealedResponses()
        {
            var (window, context) = Load();
            Assert.That(window.schema_version, Is.EqualTo("colav.run-replay.window@1"));
            Assert.That(window.run_id, Does.StartWith("745d63fd"));
            Assert.That(window.frames, Is.Not.Null);
            Assert.That(window.frames.Length, Is.EqualTo(2), "裁剪件只留 2 帧（帧距 0.5s 供插值断言）");
            Assert.That(context.schema_version, Is.EqualTo("colav.run-replay.context@1"));
            Assert.That(context.enc.origin_east_m, Is.EqualTo(37000.0).Within(1e-9));
            Assert.That(context.ships.Length, Is.EqualTo(2));
        }

        [Test]
        public void ToTelemetry_MapsNeOrderStateToCompactTruth()
        {
            var (window, context) = Load();
            var frame = window.frames[0];
            var telemetry = ReplayWindowAdapter.ToTelemetry(frame, context);

            Assert.That(telemetry.seq, Is.EqualTo(frame.sequence), "sequence 即 compact seq");
            Assert.That(telemetry.sim_time, Is.EqualTo(10.0).Within(1e-9));
            Assert.That(telemetry.state, Is.EqualTo("RUNNING"));
            Assert.That(telemetry.playback.effective_multiplier, Is.EqualTo(1.0).Within(1e-9),
                "sealed 回放按 1× 采样（compact 的 effective_multiplier 属 live 调度）");
            Assert.That(telemetry.truth.Length, Is.EqualTo(2), "Ship0/Ship1 两槽");

            var own = telemetry.truth[0];
            Assert.That(own.id, Is.EqualTo(0));
            Assert.That(own.mmsi, Is.EqualTo(100));
            // state = [north, east, psi, u, v, r]（NE 序；帧 21 录制事实）。
            Assert.That(own.north, Is.EqualTo(6957549.216f).Within(0.01f));
            Assert.That(own.east, Is.EqualTo(39548.201f).Within(0.01f));
            Assert.That(own.psi, Is.EqualTo(0.7781188f).Within(1e-5f), "psi rad 北偏东");
            Assert.That(own.u, Is.EqualTo(6.8834353f).Within(1e-4f));
            Assert.That(own.v, Is.EqualTo(-0.08693168f).Within(1e-4f));
            Assert.That(own.r, Is.EqualTo(-0.0014072482f).Within(1e-7f));
            // csog_state[2]/[3] = sog/cog。
            Assert.That(own.sog, Is.EqualTo(6.8839842f).Within(1e-4f));
            Assert.That(own.cog, Is.EqualTo(0.7654903f).Within(1e-4f));
            // length/width 只来自 context.ships。
            Assert.That(own.length, Is.EqualTo(44.1f).Within(1e-4f));
            Assert.That(own.width, Is.EqualTo(8.0f).Within(1e-4f));
            Assert.That(own.active, Is.True);

            var target = telemetry.truth[1];
            Assert.That(target.id, Is.EqualTo(1));
            Assert.That(target.length, Is.EqualTo(8.45f).Within(1e-4f), "尺寸按 id 自 context 补齐");
            Assert.That(target.width, Is.EqualTo(2.71f).Within(1e-4f));
        }

        [Test]
        public void AdaptedFrames_FlowThroughTwinPipeline()
        {
            // 归一目标：适配产物直接进 seq 闸门 + 锚定 + 位姿管线（与 live 同一条路，零分支）。
            var (window, context) = Load();
            var first = ReplayWindowAdapter.ToTelemetry(window.frames[0], context);
            var second = ReplayWindowAdapter.ToTelemetry(window.frames[1], context);

            Assert.That(TwinEnvelope.IsValidCompact(first), Is.False,
                "适配产物无 compact transport 信封（走驱动管线时不过信封闸；驱动消费路径以 seq/sim_time 为准）");

            var clock = new TwinClock();
            Assert.That(clock.OnFrame(first.sim_time, 0.0, first.playback.effective_multiplier), Is.EqualTo(TwinFrameSync.First));
            Assert.That(clock.OnFrame(second.sim_time, 0.5, second.playback.effective_multiplier), Is.EqualTo(TwinFrameSync.Smooth),
                "帧距 0.5s 与 multiplier 1× 预测重合 → 平滑");

            var anchor = TwinAnchor.FromShip(first.truth[0]);
            var ownLocal = TwinPose.ScenePosition(first.truth[0], anchor);
            // P3-12：首帧本船锚定到登记落点（减锚 + M6 登记平移；原点直落语义已退役）。
            var landing = M6TwinGeo.LandingM;
            Assert.That(ownLocal, Is.EqualTo(new Vector3(landing.x, 0f, landing.y)).Within(0.01f), "首帧本船锚定到 geo 落点");
            var targetLocal = TwinPose.ScenePosition(first.truth[1], anchor);
            Assert.That(targetLocal.x, Is.GreaterThan(landing.x), "目标在本船东侧（head_on 对遇几何）");
            Assert.That(TwinPose.InterpolationAlpha(10.25, first.sim_time, second.sim_time), Is.EqualTo(0.5f).Within(1e-4f));
        }

        [Test]
        public void Slots_SkipNullsInIndexOrder_AndShortStateSkipsEntry()
        {
            var frame = new ReplayFrame
            {
                sequence = 7,
                sim_time = 3.5,
                state = "RUNNING",
                payload = new ReplayShipPayload
                {
                    Ship1 = new ReplayShipSlot { id = 1, state = new[] { 1.0, 2.0, 0.5 } },
                    Ship0 = new ReplayShipSlot { id = 0, state = new[] { 9.0, 8.0, 1.5 } },
                    Ship2 = new ReplayShipSlot { id = 2 }, // state 缺失 = 证据不全，跳过不脑补
                },
            };
            var slots = frame.Slots();
            Assert.That(slots.Length, Is.EqualTo(3), "Slot() 只按非空枚举，序无关绑定");
            var telemetry = ReplayWindowAdapter.ToTelemetry(frame, null);
            Assert.That(telemetry.seq, Is.EqualTo(7));
            Assert.That(telemetry.truth.Length, Is.EqualTo(2), "短 state 船跳过");
            Assert.That(telemetry.truth[0].id, Is.EqualTo(0), "truth 按 ShipN 槽位序（JsonUtility 按名绑定，JSON 文本序无关）");
            Assert.That(telemetry.truth[1].id, Is.EqualTo(1));
            Assert.That(telemetry.truth[0].east, Is.EqualTo(8f).Within(1e-5f), "Ship0 state=[north,east,psi] NE 序");
            Assert.That(telemetry.truth[0].north, Is.EqualTo(9f).Within(1e-5f));
            Assert.That(telemetry.truth[1].east, Is.EqualTo(2f).Within(1e-5f));
            Assert.That(telemetry.truth[1].north, Is.EqualTo(1f).Within(1e-5f));
            Assert.That(telemetry.truth[0].length, Is.EqualTo(0f), "无 context 时尺寸留 0（调用方按编目重配）");
        }
    }
}
