using System.IO;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P2-S1 管线集成测试：真实录制 compact-v1 帧过 seq 闸门 → 锚定 → 位姿全链（spec #89）。
    /// fixture = Assets/Tests/Fixtures/telemetry-sample.json（真 WS 快照，M3 录制，
    /// provenance 见 evidence m3-build-log.md；S0 对拍确认与 compact-v1-frames.jsonl 同形）。
    /// 期望值来自录制事实：本船 t east≈39632.9978/north≈6957632.9978、ψ=π/4、对遇几何。
    /// </summary>
    public class TwinPipelineFixtureTests
    {
        const string k_FixtureRelPath = "Tests/Fixtures/telemetry-sample.json";

        static ColavTelemetry LoadRealFrame()
        {
            string path = Path.Combine(Application.dataPath, k_FixtureRelPath);
            Assert.That(File.Exists(path), Is.True, $"fixture 缺失：{path}");
            return ColavTelemetry.FromJson(File.ReadAllText(path));
        }

        [Test]
        public void RealCompactFrame_PassesGateAndAnchors()
        {
            var frame = LoadRealFrame();
            Assert.That(TwinEnvelope.IsValidCompact(frame), Is.True, "真帧过信封闸");

            var clock = new TwinClock();
            Assert.That(clock.OnFrame(frame.sim_time, 0.0, frame.playback.effective_multiplier),
                Is.EqualTo(TwinFrameSync.First));

            var anchor = TwinAnchor.FromShip(frame.truth[0]);
            Assert.That(anchor.EastM, Is.EqualTo(39632.9978).Within(0.5));
            Assert.That(anchor.NorthM, Is.EqualTo(6957632.9978).Within(0.5));
            // P3-12：锚点变换 = 减锚 + 登记平移——首帧本船落 M6 登记落点（海峡水面），
            // 目标保持对遇相对几何（场景 (0,0) 直落语义已退役，批 1 台账）。
            var landing = M6TwinGeo.LandingM;
            var ownScene = TwinPose.ScenePosition(frame.truth[0], anchor);
            Assert.That(ownScene.x, Is.EqualTo(landing.x).Within(0.5f));
            Assert.That(ownScene.z, Is.EqualTo(landing.y).Within(0.5f));

            // 对遇几何（录制事实）：目标在本船东北向 ~1735.8m 处。
            var targetLocal = TwinPose.ScenePosition(frame.truth[1], anchor);
            Assert.That(targetLocal.x - ownScene.x, Is.EqualTo(1735.834f).Within(0.5f));
            Assert.That(targetLocal.z - ownScene.z, Is.EqualTo(1735.834f).Within(0.5f));
        }

        [Test]
        public void RealCompactFrame_OwnshipHeading45()
        {
            var frame = LoadRealFrame();
            var own = frame.truth[0];
            float yaw = TwinPose.YawDegrees(own.psi);
            Assert.That(yaw, Is.EqualTo(45f).Within(0.01f), "录制本船 ψ=π/4 → rotation.y=45°");
            var heading = TwinPose.HeadingVector(yaw);
            Assert.That(heading.x, Is.EqualTo(0.70710678f).Within(1e-4f), "东北向单位向量东分量");
            Assert.That(heading.z, Is.EqualTo(0.70710678f).Within(1e-4f), "东北向单位向量北分量");
        }

        [Test]
        public void SeqResendFlow_DedupedThenClockSmooth()
        {
            // S0 实序 [0,1,1,1,1,2,...] 重发模式：同 JSON 帧重放 → dup 丢、新 seq 走时钟。
            var frame = LoadRealFrame();
            var resent = ColavTelemetry.FromJson(JsonUtility.ToJson(frame));
            var clock = new TwinClock();
            int lastSeq = -1, dup = 0, accepted = 0;
            double wall = 0.0;
            foreach (var f in new[] { frame, resent, resent })
            {
                if (TwinFrameGate.Classify(f.seq, lastSeq) == TwinFrameDecision.Duplicate) { dup++; continue; }
                clock.OnFrame(f.sim_time, wall, f.playback.effective_multiplier);
                lastSeq = f.seq;
                accepted++;
                wall += 0.05;
            }
            Assert.That(dup, Is.EqualTo(2), "同 seq 重发全数丢弃");
            Assert.That(accepted, Is.EqualTo(1));
            Assert.That(clock.LastFrameSimTime, Is.EqualTo(26.5).Within(1e-6));
        }
    }
}
