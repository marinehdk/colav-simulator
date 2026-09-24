using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-E2 岛屿重建参数传播缝 EditMode 测试（spec #85 Testing Decisions）。
    /// 面板映射（documented mapping，IslandRebuild 头注同源）：count 直传、
    /// scale → sizeRange·scale + clusterRadius·scale、seed 恒定（同一群岛等比缩放，确定性）。
    /// 独立真值 = M1 场景构建常数（5 岛 / seed 42 / 直径 80-240 / 撒点半径 260），
    /// 不回声实现里的 Clamp 调用。
    /// </summary>
    public class IslandRebuildTests
    {
        // ── 基线 = M1 场景常数 ───────────────────────────────────────────────────────
        [Test]
        public void M1Baseline_MatchesSceneBuildConstants()
        {
            var b = IslandRebuild.M1Baseline();
            Assert.That(b.count, Is.EqualTo(5), "M1 = 5 岛");
            Assert.That(b.seed, Is.EqualTo(42), "M1 种子 42");
            Assert.That(b.sizeRange, Is.EqualTo(new Vector2(80f, 240f)), "M1 岛直径 80-240 m");
            Assert.That(b.clusterRadius, Is.EqualTo(260f), "M1 撒点半径 260 m");
            Assert.That(b.maxHeight, Is.EqualTo(45f), "M1 最大山高 45 m");
            Assert.That(b.resolution, Is.EqualTo(96), "M1 网格分辨率 96");
        }

        // ── 映射：count 直传、scale 只动尺寸与撒点盘、seed 不变 ─────────────────────
        [Test]
        public void MapToSettings_CountDirect_ScaleMultipliesSizeAndCluster_SeedKept()
        {
            var mapped = IslandRebuild.MapToSettings(IslandRebuild.M1Baseline(), 8, 2f);
            Assert.That(mapped.count, Is.EqualTo(8), "count 直传");
            Assert.That(mapped.sizeRange, Is.EqualTo(new Vector2(160f, 480f)), "直径 80-240 × 2");
            Assert.That(mapped.clusterRadius, Is.EqualTo(520f), "撒点半径 260 × 2（同比放大保密度）");
            Assert.That(mapped.seed, Is.EqualTo(42), "seed 不随面板变（同一群岛等比缩放，确定性）");
            Assert.That(mapped.maxHeight, Is.EqualTo(45f), "竖向尺度不随 scale 变（约定缝只动横向三处）");
            Assert.That(mapped.resolution, Is.EqualTo(96), "分辨率不随面板变");
        }

        [Test]
        public void MapToSettings_IdentityAtScaleOne()
        {
            var baseline = IslandRebuild.M1Baseline();
            var mapped = IslandRebuild.MapToSettings(baseline, 5, 1f);
            Assert.That(mapped.count, Is.EqualTo(baseline.count));
            Assert.That(mapped.sizeRange, Is.EqualTo(baseline.sizeRange));
            Assert.That(mapped.clusterRadius, Is.EqualTo(baseline.clusterRadius), "scale=1 → 与基线逐位一致（M1 默认面板态零扰动）");
        }

        // ── 钳制（面板滑条外的旁路输入兜底）─────────────────────────────────────────
        [Test]
        public void MapToSettings_ClampsCountAndScale()
        {
            var low = IslandRebuild.MapToSettings(IslandRebuild.M1Baseline(), 0, 0.1f);
            Assert.That(low.count, Is.GreaterThanOrEqualTo(1), "count 下钳 ≥ 1（0 岛 = 空场景）");
            Assert.That(low.sizeRange.x, Is.GreaterThan(0f), "scale 下钳后尺寸仍为正");

            var high = IslandRebuild.MapToSettings(IslandRebuild.M1Baseline(), 99, 10f);
            Assert.That(high.count, Is.LessThanOrEqualTo(24), "count 上钳（生成时间/顶点预算）");
            Assert.That(high.sizeRange, Is.EqualTo(new Vector2(240f, 720f)), "scale 上钳 3 → 直径 80-240 × 3");
            Assert.That(high.clusterRadius, Is.EqualTo(780f), "scale 上钳 3 → 撒点半径 260 × 3");
        }
    }
}
