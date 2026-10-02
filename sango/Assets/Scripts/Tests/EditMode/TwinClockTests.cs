using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P2-S1 TwinClock 软对齐时钟测试（spec #89；纯逻辑、墙钟注入）。
    /// 钉死：首帧锚定 / 正常帧距平滑重锚 / 倍率缩放渲染时间 / 大跳（&gt;2×帧距）重同步 /
    /// 帧距倒退防御性重同步 / 阈值下限防抖 / 未同步 Sample=NaN。
    /// 帧距 0.5s = head_on 求解步（S0 实证，evidence/p2s0-notes.md）。
    /// </summary>
    public class TwinClockTests
    {
        const double Tolerance = 1e-9;

        [Test]
        public void FirstFrame_AnchorsDirectly()
        {
            var clock = new TwinClock();
            Assert.That(clock.OnFrame(0.0, 100.0, 1.0), Is.EqualTo(TwinFrameSync.First));
            Assert.That(clock.Synced, Is.True);
            Assert.That(clock.Sample(100.0), Is.EqualTo(0.0).Within(Tolerance));
        }

        [Test]
        public void Sample_AdvancesByMultiplier()
        {
            var clock = new TwinClock();
            clock.OnFrame(10.0, 100.0, 0.5); // effective_multiplier 0.5 = 后端 realtime_limited
            Assert.That(clock.Sample(101.0), Is.EqualTo(10.5).Within(Tolerance));
            // 正常帧距（predicted=10.5, |11−10.5|=0.5 ≤ 2×1.0）→ Smooth，倍率换 2×。
            Assert.That(clock.OnFrame(11.0, 101.0, 2.0), Is.EqualTo(TwinFrameSync.Smooth));
            Assert.That(clock.Sample(101.25), Is.EqualTo(11.5).Within(Tolerance));
        }

        [Test]
        public void SmoothStep_AtSolverFrameDistance()
        {
            var clock = new TwinClock();
            clock.OnFrame(0.0, 100.0, 1.0);
            // 求解步 0.5s、到达即重锚：predicted=0.5 与 sim_time=0.5 重合 → Smooth。
            Assert.That(clock.OnFrame(0.5, 100.5, 1.0), Is.EqualTo(TwinFrameSync.Smooth));
            Assert.That(clock.OnFrame(1.0, 101.0, 1.0), Is.EqualTo(TwinFrameSync.Smooth));
        }

        [Test]
        public void StallBeyondLead_Resyncs()
        {
            var clock = new TwinClock();
            clock.OnFrame(0.0, 100.0, 1.0);
            clock.OnFrame(0.5, 100.5, 1.0);
            // 墙钟已走 4.55s 而 sim 只进 0.5s：predicted=5.05，偏差 4.55 > 2×0.5 → 大跳重同步。
            Assert.That(clock.OnFrame(1.0, 105.05, 1.0), Is.EqualTo(TwinFrameSync.Resync));
            // 重同步即重锚：Sample 从新帧出发，不跨跳外推。
            Assert.That(clock.Sample(105.05), Is.EqualTo(1.0).Within(Tolerance));
        }

        [Test]
        public void ZeroGapSameSimAcrossSeqs_IsSmooth()
        {
            var clock = new TwinClock();
            clock.OnFrame(0.0, 100.0, 1.0);
            // S0 实证：seq N 首帧仍带上帧 sim_time（seq 先进 sim 后动）——gap=0 不得误判重同步。
            Assert.That(clock.OnFrame(0.0, 100.1, 1.0), Is.EqualTo(TwinFrameSync.Smooth));
            Assert.That(clock.OnFrame(0.5, 100.54, 1.0), Is.EqualTo(TwinFrameSync.Smooth));
        }

        [Test]
        public void SimTimeRegressions_ResyncDefensively()
        {
            var clock = new TwinClock();
            clock.OnFrame(1.0, 100.0, 1.0);
            // seq 未倒退但 sim_time 回退（防御路径，正常由 seq 闸门先行重建）。
            Assert.That(clock.OnFrame(0.5, 100.5, 1.0), Is.EqualTo(TwinFrameSync.Resync));
        }

        [Test]
        public void ResyncLead_HasJitterFloor()
        {
            var clock = new TwinClock();
            clock.OnFrame(0.0, 100.0, 1.0);
            // 帧距 0.1s → 2×帧距=0.2s，抬到下限 0.25s：偏差 0.12 不重同步。
            Assert.That(clock.OnFrame(0.1, 100.22, 1.0), Is.EqualTo(TwinFrameSync.Smooth));
            // 偏差 |0.2 − (0.1 + 0.38×1)| = 0.28 > 0.25 → 重同步。
            Assert.That(clock.OnFrame(0.2, 100.60, 1.0), Is.EqualTo(TwinFrameSync.Resync));
        }

        [Test]
        public void InvalidMultiplierKeepsPrevious()
        {
            var clock = new TwinClock();
            clock.OnFrame(0.0, 100.0, 2.0);
            clock.OnFrame(0.5, 100.25, double.NaN); // predicted=0.5，NaN 不改倍率 → Smooth
            Assert.That(clock.Multiplier, Is.EqualTo(2.0).Within(Tolerance));
            clock.OnFrame(1.0, 100.5, -1.0);
            Assert.That(clock.Multiplier, Is.EqualTo(2.0).Within(Tolerance));
            Assert.That(clock.Sample(100.75), Is.EqualTo(1.5).Within(Tolerance)); // 锚点 1.0 + 0.25s×2×
        }

        [Test]
        public void Sample_UnsyncedIsNaN_AndResetClears()
        {
            var clock = new TwinClock();
            Assert.That(double.IsNaN(clock.Sample(0.0)), Is.True, "未同步不得外推");
            clock.OnFrame(5.0, 100.0, 1.0);
            clock.Reset();
            Assert.That(clock.Synced, Is.False);
            Assert.That(double.IsNaN(clock.Sample(100.0)), Is.True);
            Assert.That(clock.OnFrame(5.0, 100.0, 1.0), Is.EqualTo(TwinFrameSync.First), "重建后走首帧路径");
        }
    }
}
