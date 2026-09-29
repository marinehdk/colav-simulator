using System.Linq;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M8 画质双档参数表 EditMode 测试（fixture 全合成，无场景实例）：①当前常量下构建期
    /// 断言通过；②断言触发路径（装饰组表漂移/渔排出宿主矩形/GO 名漂移注入即红）；
    /// ③High 档钉死 M7 终态语义、Low 档降档杠杆记录在案且两档互异；④装饰组静态索引
    /// 契约（计数/宿主 tile 与 M7BackdropMath 同源/渔排命名序）。
    /// </summary>
    public class M8QualityProfileTests
    {
        // ── ① 构建期断言：当前常量通过 ─────────────────────────────────────────────

        [Test]
        public void Validate_CurrentConstants_Passes()
        {
            var errors = M8QualityProfile.Validate();
            Assert.That(errors, Is.Empty, "当前常量应通过构建期断言: " + string.Join("; ", errors));
        }

        // ── ② 断言触发路径（注入被检表制造漂移）────────────────────────────────────

        [Test]
        public void Validate_CatchesTerminalHostTileDrift()
        {
            var hosts = (string[])M8QualityProfile.DecorationHostTiles.Clone();
            hosts[M8QualityProfile.GroupTuasCranes] = "far_r2c1_513"; // 漂移：Tuas 实际在 far_r2c0
            var errors = M8QualityProfile.Validate(M8QualityProfile.DecorationGoNames, hosts, null);
            Assert.That(errors, Is.Not.Empty, "宿主 tile 漂移必须被断言拦下");
            Assert.That(errors.Any(e => e.Contains("Tuas")), Is.True, "错误信息应定位 Tuas 组: " + string.Join("; ", errors));
        }

        [Test]
        public void Validate_CatchesFarmGoNameDrift()
        {
            var names = (string[])M8QualityProfile.DecorationGoNames.Clone();
            names[M8QualityProfile.GroupFishFarmFirst] = "M7B Fish Farm 9"; // 命名序漂移
            var errors = M8QualityProfile.Validate(names, M8QualityProfile.DecorationHostTiles, null);
            Assert.That(errors, Is.Not.Empty);
            Assert.That(errors.Any(e => e.Contains("M7B Fish Farm 9")), Is.True);
        }

        [Test]
        public void Validate_CatchesFishFarmOutsideHostTileRect()
        {
            // M7BMath 选点若漂进出 far_r3c4 宿主（如丢进被近带/隐藏 tile 压住的区域）→ 悬空渔排
            var sites = (Vector2[])M7BMath.FishFarmSites.Clone();
            sites[2] = new Vector2(5000f, -5000f); // 落近带中央 = 宿主矩形外
            var errors = M8QualityProfile.Validate(null, null, sites);
            Assert.That(errors, Is.Not.Empty);
            Assert.That(errors.Any(e => e.Contains("outside host tile")), Is.True, ": " + string.Join("; ", errors));
        }

        // ── ③ 档语义契约 ───────────────────────────────────────────────────────────

        [Test]
        public void TierContract_HighPinsM7Semantics_LowRecordsDowngrade()
        {
            // High = M7 终态：交叠隐藏/外环常开/出带 swap 接管；树预算 = M7 常量
            Assert.That(M8QualityProfile.HighOverlapStartsHidden, Is.True);
            Assert.That(M8QualityProfile.HighRingAlwaysOn, Is.True);
            Assert.That(M8QualityProfile.HighSwapsNearOutsideBand, Is.True);
            Assert.That(M8QualityProfile.TreeCardBudgetHigh, Is.EqualTo(M7BackdropMath.MaxTreeInstances));
            Assert.That(M8QualityProfile.TreeCardsPerFarTileHigh, Is.EqualTo(M7BackdropMath.MaxTreesPerFarTile));

            // Low 降档杠杆（记录在案）且与 High 互异
            Assert.That(M8QualityProfile.LowSwapsNearOutsideBand, Is.False, "Low 近带恒开");
            Assert.That(M8QualityProfile.LowFarTreeDistanceM, Is.LessThan(M8QualityProfile.HighFarTreeDistanceM));
            Assert.That(M8QualityProfile.LowFarHeightmapPixelError, Is.GreaterThanOrEqualTo(1f));
            Assert.That(M8QualityProfile.LowSunShadowsHard, Is.True);

            // 编排几何：4/9/16 = 29；迟滞带 sane
            Assert.That(M8QualityProfile.TotalTileCount, Is.EqualTo(29));
            Assert.That(M8QualityProfile.NearTileCount, Is.EqualTo(4));
            Assert.That(M8QualityProfile.OverlapTileCount, Is.EqualTo(9));
            Assert.That(M8QualityProfile.RingTileCount, Is.EqualTo(16));
            Assert.That(M8QualityProfile.RingEnterDistanceM, Is.GreaterThan(M8QualityProfile.NearBandHalfM));
            Assert.That(M8QualityProfile.RingEnterDistanceM, Is.LessThan(M8QualityProfile.RingExitDistanceM));
            Assert.That(M8QualityProfile.FarEngageOutsideM, Is.GreaterThan(0f));
            Assert.That(M8QualityProfile.NearReenterInsideM, Is.GreaterThan(0f));
        }

        // ── ④ 装饰组静态索引契约 ───────────────────────────────────────────────────

        [Test]
        public void DecorationGroups_StaticIndexContract()
        {
            Assert.That(M8QualityProfile.DecorationGoNames.Length, Is.EqualTo(M8QualityProfile.DecorationGroupCount));
            Assert.That(M8QualityProfile.DecorationHostTiles.Length, Is.EqualTo(M8QualityProfile.DecorationGroupCount));
            Assert.That(M8QualityProfile.DecorationGoNames.Distinct().Count(),
                Is.EqualTo(M8QualityProfile.DecorationGroupCount), "GO 名应唯一（场景查找依赖）");

            // 终端组宿主 = M7BackdropMath 布局字面量（单一真值，防表间漂移）
            Assert.That(M8QualityProfile.DecorationHostTiles[M8QualityProfile.GroupPasirPanjangCranes],
                Is.EqualTo(M7BackdropMath.PasirPanjang.tileName));
            Assert.That(M8QualityProfile.DecorationHostTiles[M8QualityProfile.GroupPasirPanjangYard],
                Is.EqualTo(M7BackdropMath.PasirPanjang.tileName));
            Assert.That(M8QualityProfile.DecorationHostTiles[M8QualityProfile.GroupTuasCranes],
                Is.EqualTo(M7BackdropMath.TuasPier.tileName));
            Assert.That(M8QualityProfile.DecorationHostTiles[M8QualityProfile.GroupTuasYard],
                Is.EqualTo(M7BackdropMath.TuasPier.tileName));

            // 渔排组：命名序 + 宿主 + M7BMath 组数一致
            Assert.That(M7BMath.FishFarmSites.Length, Is.EqualTo(5));
            for (int i = M8QualityProfile.GroupFishFarmFirst; i < M8QualityProfile.DecorationGroupCount; i++)
            {
                Assert.That(M8QualityProfile.DecorationGoNames[i],
                    Is.EqualTo($"M7B Fish Farm {i - M8QualityProfile.GroupFishFarmFirst:00}"));
                Assert.That(M8QualityProfile.DecorationHostTiles[i], Is.EqualTo(M8QualityProfile.FishFarmHostTile));
            }

            // 渔排宿主矩形几何：far_r3c4 = x[18000,30000] z[-18000,-6000]，全站位于内
            var rect = M8QualityProfile.FishFarmHostRect();
            Assert.That(rect.xMin, Is.EqualTo(18000f));
            Assert.That(rect.yMin, Is.EqualTo(-18000f));
            foreach (var s in M7BMath.FishFarmSites)
                Assert.That(rect.Contains(s), Is.True, $"渔排 ({s.x:F0},{s.y:F0}) 应在宿主 far_r3c4 内");
        }

        [Test]
        public void DropdownIndex_MapsToTierAndClamps()
        {
            Assert.That(M8QualityProfile.TierFromDropdownIndex(0), Is.EqualTo(M8QualityTier.High));
            Assert.That(M8QualityProfile.TierFromDropdownIndex(1), Is.EqualTo(M8QualityTier.Low));
            Assert.That(M8QualityProfile.TierFromDropdownIndex(-3), Is.EqualTo(M8QualityTier.High), "越界钳位");
            Assert.That(M8QualityProfile.TierFromDropdownIndex(7), Is.EqualTo(M8QualityTier.Low), "越界钳位");
            Assert.That((int)M8QualityTier.High, Is.EqualTo(0), "下拉序 = 枚举序 High/Low");
            Assert.That((int)M8QualityTier.Low, Is.EqualTo(1));
        }
    }
}
