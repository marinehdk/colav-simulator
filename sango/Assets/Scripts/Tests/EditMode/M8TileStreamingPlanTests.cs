using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M8 tile 流送判据 EditMode 测试：合成 29 tile 网格 fixture（几何 = manifest 实际布局：
    /// 近带 2×2 ±12 km、远带 5×5 ±30 km、交叠 = 中央 3×3），纯函数断言——
    /// ①High 档近带内 = M7 终态（近亮/交叠灭/外环亮）；②出带 swap 互斥 + 回程迟滞；
    /// ③迟滞往返恰两次翻转、边界抖动不翻；④Low 档近带恒开/交叠恒灭/外环邻域 latch；
    /// ⑤分帧队列每帧 ≤1 次变更、激活先于停用、重建去重；⑥装饰组随宿主 tile。
    /// </summary>
    public class M8TileStreamingPlanTests
    {
        const int TileCount = 29;
        const int DecoCount = 9;
        // fixture 布局索引（远带 row-major 排布 r0..r4）
        const int NearPP = 2;   // near_r1c0（Pasir Panjang 宿主）
        const int FarTuas = 14; // far_r2c0（Tuas 宿主）
        const int FarFarm = 23; // far_r3c4（渔排宿主）
        const int FirstRingFar = 4;

        static readonly Vector2 k_HeroBerth = new Vector2(-1500f, -5000f);
        static readonly Vector2[] k_RouteWaypoints =
        {
            new Vector2(5200f, -11400f),
            new Vector2(7200f, -11200f),
            new Vector2(9500f, -8800f),
        };

        /// <summary>合成 29 tile 网格（布局同 manifest：near 2×2 ±12 km / far 5×5 ±30 km，
        /// 交叠 = 远带中央 3×3；行序同 manifest——r0 在北 z+，far_r2c0 = Tuas 宿主）。</summary>
        static M8StreamingTile[] MakeTiles()
        {
            var tiles = new M8StreamingTile[TileCount];
            int i = 0;
            for (int r = 0; r < 2; r++)
                for (int c = 0; c < 2; c++)
                    tiles[i++] = new M8StreamingTile
                    {
                        tileName = $"near_r{r}c{c}",
                        xmin = -12000f + c * 12000f, zmin = 0f - r * 12000f,
                        xmax = 12000f - (1 - c) * 12000f, zmax = 12000f - r * 12000f,
                        group = M8StreamGroup.Near,
                    };
            for (int r = 0; r < 5; r++)
                for (int c = 0; c < 5; c++)
                {
                    bool overlap = r >= 1 && r <= 3 && c >= 1 && c <= 3;
                    tiles[i++] = new M8StreamingTile
                    {
                        tileName = $"far_r{r}c{c}",
                        xmin = -30000f + c * 12000f, zmin = 18000f - r * 12000f,
                        xmax = -18000f + c * 12000f, zmax = 30000f - r * 12000f,
                        group = overlap ? M8StreamGroup.Overlap : M8StreamGroup.Ring,
                    };
                }
            return tiles;
        }

        static M8DecorationGroup[] MakeDecorations()
        {
            var groups = new M8DecorationGroup[DecoCount];
            int[] hosts = { NearPP, NearPP, FarTuas, FarTuas, FarFarm, FarFarm, FarFarm, FarFarm, FarFarm };
            for (int i = 0; i < DecoCount; i++)
                groups[i] = new M8DecorationGroup { hostTileName = "fixture", hostTileIndex = hosts[i] };
            return groups;
        }

        static (bool[] desired, M8StreamingLatches latches) Compute(M8QualityTier tier, Vector2 refXZ,
            M8StreamingLatches latches)
        {
            var tiles = MakeTiles(); // 每次新建防串场（纯读取，廉价）
            var decos = MakeDecorations();
            var desired = new bool[TileCount + DecoCount];
            M8TileStreamingPlan.ComputeDesired(tiles, decos, tier, refXZ, ref latches, desired);
            return (desired, latches);
        }

        static int CountRingActive(bool[] desired)
        {
            int n = 0;
            for (int i = FirstRingFar; i < TileCount; i++)
                if (desired[i]) n++;
            return n;
        }

        // ── ① High 档近带内 = M7 终态语义 ──────────────────────────────────────────

        [Test]
        public void High_NearBand_StraitPositions_MatchM7Terminal()
        {
            // 泊位 + G 航路 + 东/西南锚地（西南锚地 z 出带 156 m，< 2 km 迟滞仍守 NEAR）
            var positions = new System.Collections.Generic.List<Vector2> { k_HeroBerth };
            positions.AddRange(k_RouteWaypoints);
            positions.Add(new Vector2(10136f, -7751f));  // 东锚地
            positions.Add(new Vector2(12070f, -8377f));  // 东锚地东缘（出带 70 m）
            positions.Add(new Vector2(-10020f, -12156f)); // 西南锚地（出带 156 m）

            foreach (var p in positions)
            {
                var (desired, latches) = Compute(M8QualityTier.High, p, M8StreamingLatches.CreateInitial(16));
                Assert.That(latches.nearBandEngaged, Is.True, $"({p.x:F0},{p.y:F0}) 应守 NEAR（迟滞内）");
                for (int i = 0; i < 4; i++)
                    Assert.That(desired[i], Is.True, $"({p.x:F0},{p.y:F0}) near tile {i} 应亮（M7 终态）");
                for (int i = 4; i < TileCount; i++)
                {
                    bool expect = MakeTiles()[i].group == M8StreamGroup.Ring;
                    Assert.That(desired[i], Is.EqualTo(expect),
                        $"({p.x:F0},{p.y:F0}) tile {i} 期望态错（交叠灭/外环亮）");
                }
                for (int i = 0; i < DecoCount; i++)
                    Assert.That(desired[TileCount + i], Is.True, $"({p.x:F0},{p.y:F0}) 装饰组 {i} 应亮");
            }
        }

        // ── ② 出带 swap 互斥 + 回程迟滞 ────────────────────────────────────────────

        [Test]
        public void High_FarEngage_SwapExclusive_AndReenterHolds()
        {
            var latches = M8StreamingLatches.CreateInitial(16);

            // 出带 3 km → FAR：近带整组让位、交叠 9 整组接管（互斥，绝不同亮）
            var (far, l2) = Compute(M8QualityTier.High, new Vector2(15000f, 0f), latches);
            Assert.That(l2.nearBandEngaged, Is.False, "出带 3 km 应切 FAR");
            for (int i = 0; i < 4; i++) Assert.That(far[i], Is.False, "FAR 态近带应让位");
            for (int i = 4; i < TileCount; i++)
            {
                var g = MakeTiles()[i].group;
                if (g == M8StreamGroup.Overlap) Assert.That(far[i], Is.True, "FAR 态交叠 tile 应接管");
                else Assert.That(far[i], Is.True, "FAR 态外环应保持亮");
            }
            // 装饰组随宿主：PP（近带宿主）灭，Tuas/渔排（外环宿主）亮
            Assert.That(far[TileCount + 0], Is.False, "PP 岸桥随近带宿主灭（防悬空）");
            Assert.That(far[TileCount + 1], Is.False);
            Assert.That(far[TileCount + 2], Is.True, "Tuas 岸桥随外环宿主亮");
            Assert.That(far[TileCount + 4], Is.True, "渔排随外环宿主亮");

            // 回程：带缘外 400 m（出带 -400 → 未过 -500 回程门）保持 FAR
            var (hold, l3) = Compute(M8QualityTier.High, new Vector2(-11600f, 0f), l2);
            Assert.That(l3.nearBandEngaged, Is.False, "带缘外 400 m 应保持 FAR（迟滞回程）");
            Assert.That(hold[0], Is.False);

            // 回带内 600 m → NEAR 恢复
            var (back, l4) = Compute(M8QualityTier.High, new Vector2(-11400f, 0f), l3);
            Assert.That(l4.nearBandEngaged, Is.True, "带内 600 m 应换回 NEAR");
            for (int i = 0; i < 4; i++) Assert.That(back[i], Is.True);
            for (int i = 4; i < TileCount; i++)
                if (MakeTiles()[i].group == M8StreamGroup.Overlap)
                    Assert.That(back[i], Is.False, "NEAR 恢复后交叠 tile 应灭（互斥）");
        }

        // ── ③ 迟滞防抖 ─────────────────────────────────────────────────────────────

        [Test]
        public void Hysteresis_OutAndBack_FlipsExactlyTwice()
        {
            var latches = M8StreamingLatches.CreateInitial(16);
            int flips = 0;
            bool last = latches.nearBandEngaged;
            for (int x = -11000; x <= 14100; x += 100)
            {
                (_, latches) = Compute(M8QualityTier.High, new Vector2(x, 0f), latches);
                if (latches.nearBandEngaged != last) { flips++; last = latches.nearBandEngaged; }
            }
            for (int x = 14100; x >= -11600; x -= 100)
            {
                (_, latches) = Compute(M8QualityTier.High, new Vector2(x, 0f), latches);
                if (latches.nearBandEngaged != last) { flips++; last = latches.nearBandEngaged; }
            }
            Assert.That(flips, Is.EqualTo(2), "往返一次恰 NEAR→FAR→NEAR 两次翻转");
        }

        [Test]
        public void Hysteresis_EdgeJitter_DoesNotFlip()
        {
            // NEAR 态在出带 0..1.9 km 抖动（< 2 km 门）不翻
            var latches = M8StreamingLatches.CreateInitial(16);
            var xs = new[] { 11500f, 13900f, 12000f, 12100f, 11800f };
            for (int k = 0; k < 10; k++)
                foreach (var x in xs)
                {
                    (_, latches) = Compute(M8QualityTier.High, new Vector2(x, 0f), latches);
                    Assert.That(latches.nearBandEngaged, Is.True, $"NEAR 态 x={x} 抖动不应翻转");
                }

            // 强制 FAR 后在回程带（带内 0..500 m 抖动）不翻
            (_, latches) = Compute(M8QualityTier.High, new Vector2(20000f, 0f), latches);
            Assert.That(latches.nearBandEngaged, Is.False);
            var back = new[] { -11500f, -11700f, -11900f, -11600f, -11501f }; // 带内 100..500 m
            for (int k = 0; k < 10; k++)
                foreach (var x in back)
                {
                    (_, latches) = Compute(M8QualityTier.High, new Vector2(x, 0f), latches);
                    Assert.That(latches.nearBandEngaged, Is.False, $"FAR 态 x={x} 抖动不应翻转（回程门 500 m）");
                }
        }

        // ── ④ Low 档：近带恒开 / 交叠恒灭 / 外环邻域 latch ─────────────────────────

        [Test]
        public void Low_AtBerth_NearOn_OverlapOff_RingPruned()
        {
            var (desired, latches) = Compute(M8QualityTier.Low, k_HeroBerth, M8StreamingLatches.CreateInitial(16));
            for (int i = 0; i < 4; i++) Assert.That(desired[i], Is.True, "Low 近带恒开");
            for (int i = 4; i < TileCount; i++)
                if (MakeTiles()[i].group == M8StreamGroup.Overlap)
                    Assert.That(desired[i], Is.False, "Low 交叠恒灭（与近带互斥）");
            // 泊位南侧带（far_r4c1-3）距 13 km：初始 latch 亮态 + ≤16 km 出带门 → 守亮（合法邻域）
            Assert.That(desired[25], Is.True, "南侧 r4c1（13 km）应守亮（latch hold）");
            Assert.That(desired[26], Is.True);
            Assert.That(desired[27], Is.True);
            Assert.That(CountRingActive(desired), Is.EqualTo(3), "泊位邻域仅南侧带 3 块");
            Assert.That(CountRingActive(desired), Is.LessThanOrEqualTo(M8QualityProfile.LowMaxActiveRingTiles));

            // 装饰组：PP 随近带亮；Tuas/渔排宿主（r2c0/r3c4，均 >16 km）随宿主裁剪
            Assert.That(desired[TileCount + 0], Is.True);
            Assert.That(desired[TileCount + 1], Is.True);
            Assert.That(desired[TileCount + 2], Is.False, "Tuas 装饰随外环宿主裁剪");
            Assert.That(desired[TileCount + 4], Is.False, "渔排随外环宿主裁剪");
            Assert.That(latches.nearBandEngaged, Is.True);
        }

        [Test]
        public void Low_RingLatch_EnterExitHold_NoFlicker()
        {
            // 沿 z=0 西行：r2c0（fixture 索引 14）距离 13 km 亮、16 km 灭、带间保持
            var latches = M8StreamingLatches.CreateInitial(16);
            int flips = 0;
            bool last = true; // 初始 latch = 亮（M7 初始语义），x=-1000 距 17 km 首帧即灭
            var expected = new[] { false, true, true, false, false, true }; // 灭/亮/保/灭/保/亮
            int e = 0;
            var xs = new[] { -1000f, -5000f, -3000f, -1900f, -3000f, -5000f };
            foreach (var x in xs)
            {
                var (desired, l2) = Compute(M8QualityTier.Low, new Vector2(x, 0f), latches);
                latches = l2;
                bool now = desired[FarTuas];
                if (now != last) { flips++; last = now; }
                Assert.That(now, Is.EqualTo(expected[e]), $"x={x}: r2c0 latch 期望 {expected[e]}");
                e++;
            }
            Assert.That(flips, Is.EqualTo(4), "往返序列恰 灭/亮/灭/亮 四次翻转（带间保持防抖）");
        }

        [Test]
        public void Low_RingActiveCount_BoundedAcrossSweep()
        {
            var latches = M8StreamingLatches.CreateInitial(16);
            for (int x = -24000; x <= 24000; x += 8000)
                for (int z = -24000; z <= 24000; z += 8000)
                {
                    var (desired, l2) = Compute(M8QualityTier.Low, new Vector2(x, z), latches);
                    latches = l2;
                    Assert.That(CountRingActive(desired), Is.LessThanOrEqualTo(M8QualityProfile.LowMaxActiveRingTiles),
                        $"({x},{z}) 外环激活数超 Low 上限");
                }
        }

        // ── ⑤ 分帧队列 ─────────────────────────────────────────────────────────────

        [Test]
        public void ChangeQueue_DrainsOnePerFrame_AndDedupes()
        {
            var tiles = MakeTiles();
            var decos = MakeDecorations();
            int count = TileCount + DecoCount;
            var queue = new M8StreamingChangeQueue(count);
            var actual = new bool[count]; // 全灭初始
            var desired = new bool[count];
            var latches = M8StreamingLatches.CreateInitial(16);
            var dist = new float[count];

            M8TileStreamingPlan.ComputeDesired(tiles, decos, M8QualityTier.High, k_HeroBerth, ref latches, desired);
            FillDist(tiles, decos, k_HeroBerth, dist);
            queue.Rebuild(desired, actual, dist);
            Assert.That(queue.Pending, Is.EqualTo(29),
                "High@泊位自全灭：近 4 + 外环 16 + 装饰 9 亮（交叠 9 维持灭）= 29 变更");

            int applied = 0;
            while (queue.TryDequeue(out var change))
            {
                actual[change.index] = change.activate; // 模拟组件每帧 ≤1 次 SetActive
                applied++;
            }
            Assert.That(applied, Is.EqualTo(29), "逐帧出队恰 29 次完成");
            for (int i = 0; i < count; i++) Assert.That(actual[i], Is.EqualTo(desired[i]), $"位 {i} 终态一致");

            queue.Rebuild(desired, actual, dist); // 收敛后重建 = 零待办（去重）
            Assert.That(queue.Pending, Is.EqualTo(0), "收敛态重建应零变更");
        }

        [Test]
        public void ChangeQueue_ActivationsBeforeDeactivations()
        {
            var tiles = MakeTiles();
            var decos = MakeDecorations();
            int count = TileCount + DecoCount;
            var queue = new M8StreamingChangeQueue(count);
            var actual = new bool[count];
            for (int i = 0; i < TileCount; i++)
                actual[i] = tiles[i].group != M8StreamGroup.Overlap; // M7 终态初始：近带/外环亮、交叠灭
            for (int i = 0; i < DecoCount; i++) actual[TileCount + i] = true;
            var desired = new bool[count];
            var latches = M8StreamingLatches.CreateInitial(16);
            var dist = new float[count];

            M8TileStreamingPlan.ComputeDesired(tiles, decos, M8QualityTier.High, new Vector2(15000f, 0f), ref latches, desired);
            FillDist(tiles, decos, new Vector2(15000f, 0f), dist);
            queue.Rebuild(desired, actual, dist);

            int activations = 0, deactivations = 0;
            bool sawDeactivation = false;
            while (queue.TryDequeue(out var change))
            {
                if (change.activate)
                {
                    Assert.That(sawDeactivation, Is.False, "激活应排在全部停用之前");
                    activations++;
                }
                else { sawDeactivation = true; deactivations++; }
            }
            Assert.That(activations, Is.EqualTo(9), "交叠 9 接管 = 9 次激活");
            Assert.That(deactivations, Is.EqualTo(6), "近带 4 + PP 装饰 2 = 6 次停用");
        }

        static void FillDist(M8StreamingTile[] tiles, M8DecorationGroup[] decos, Vector2 refXZ, float[] dist)
        {
            for (int i = 0; i < tiles.Length; i++)
                dist[i] = M8TileStreamingPlan.RectDistanceXZ(refXZ, tiles[i].xmin, tiles[i].zmin, tiles[i].xmax, tiles[i].zmax);
            for (int i = 0; i < decos.Length; i++)
                dist[tiles.Length + i] = dist[decos[i].hostTileIndex];
        }

        // ── ⑥ 装饰组随宿主 tile ────────────────────────────────────────────────────

        [Test]
        public void DecorationFollowsHostTile_AcrossTiersAndPositions()
        {
            var tiles = MakeTiles();
            var decos = MakeDecorations();
            var desired = new bool[TileCount + DecoCount];
            var latches = M8StreamingLatches.CreateInitial(16);
            foreach (var tier in new[] { M8QualityTier.High, M8QualityTier.Low })
            {
                for (int x = -24000; x <= 24000; x += 8000)
                    for (int z = -24000; z <= 24000; z += 8000)
                    {
                        M8TileStreamingPlan.ComputeDesired(tiles, decos, tier, new Vector2(x, z), ref latches, desired);
                        for (int i = 0; i < DecoCount; i++)
                            Assert.That(desired[TileCount + i], Is.EqualTo(desired[decos[i].hostTileIndex]),
                                $"{tier} ({x},{z}) 装饰组 {i} 应随宿主 tile");
                    }
            }
        }
    }
}
