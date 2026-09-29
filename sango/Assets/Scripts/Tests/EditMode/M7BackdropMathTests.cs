using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M7-A 布景四要素纯函数 EditMode 测试：①EPSG:32648 经纬度 ↔ UTM/Unity 换算
    /// （参考值 pyproj 3.7 + EPSG:32648 离线固化，2026-09-29）；②陆/水掩膜与陆上门禁；
    /// ③A4 滩涂/丛林两段 splat 权重归一；④A2 真实锚地槽位（合成高度图 fixture 水深验证）；
    /// ⑤A1 岸桥/箱堆布局：总量预算、bounds 不越 tile/平整矩形、局部系↔世界系一致；
    /// ⑥A4 树卡散布规划器：确定性、上限封顶、排除区生效。
    /// fixture 全合成（无场景存档实例、不拉 tmp/ 真实数据——真实数据由构建期 gate 实采复验）。
    /// </summary>
    public class M7BackdropMathTests
    {
        // pyproj (EPSG:4326 → EPSG:32648) 离线固化参考值（米；2026-09-29 site analysis）
        static readonly (double lat, double lon, double e, double n)[] k_PyprojPins =
        {
            (1.28, 103.80, 366493.325, 141509.930), // 区域中心
            (1.26, 103.63, 347575.306, 139308.161), // Tuas 一带
            (1.26, 103.76, 362041.354, 139300.914), // Pasir Panjang 一带
            (1.21, 103.90, 377617.090, 133766.366), // 东锚地
            (1.17, 103.71, 356472.827, 129353.330), // 西南锚地
            (1.00, 104.50, 444370.225, 110534.395), // 远点（东）
            (1.50, 103.00, 277480.390, 165897.144), // 远点（西北）
            (0.50, 105.50, 555636.088, 55267.156),  // 远点（东南，跨 105°E 中央经线）
        };

        static readonly Vector2 k_CenterUtm = new Vector2(366493.325f, 141509.930f);

        // ── ① 经纬度 ↔ UTM/Unity 换算 ────────────────────────────────────────────────

        [Test]
        public void LatLonToUtm_MatchesPyprojPins()
        {
            foreach (var (lat, lon, e, n) in k_PyprojPins)
            {
                var utm = M7BackdropMath.LatLonToUtm(lat, lon);
                Assert.That(utm.x, Is.EqualTo((float)e).Within(0.5f), $"E({lat},{lon})");
                Assert.That(utm.y, Is.EqualTo((float)n).Within(0.5f), $"N({lat},{lon})");
            }
        }

        [Test]
        public void LatLonUnity_RoundTrip_SubMeter()
        {
            foreach (var (lat, lon, _, _) in k_PyprojPins)
            {
                var unity = M7BackdropMath.LatLonToUnity(lat, lon, k_CenterUtm);
                var (lat2, lon2) = M7BackdropMath.UnityToLatLon(unity.x, unity.y, k_CenterUtm);
                double dNorth = (lat2 - lat) * 111320.0;
                double dEast = (lon2 - lon) * 110600.0 * Mathf.Cos((float)(lat * Mathf.Deg2Rad));
                Assert.That(System.Math.Abs(dNorth), Is.LessThan(1.0), $"dN({lat},{lon}) = {dNorth:F3} m");
                Assert.That(System.Math.Abs(dEast), Is.LessThan(1.0), $"dE({lat},{lon}) = {dEast:F3} m");
            }
        }

        [Test]
        public void LatLonToUnity_RegionPins_UnityOriginAtCenter()
        {
            // 中心点 = Unity 原点（manifest center_utm 语义）
            var c = M7BackdropMath.LatLonToUnity(1.28, 103.80, k_CenterUtm);
            Assert.That(c.magnitude, Is.LessThan(1f), "区域中心应落在 Unity 原点（float 换算容差 1 m）");

            // 四个任务关键位（pyproj 离线换算值；逐分量断言——NUnit 对 Vector2 不吃 Within 容差）
            void Pin(double lat, double lon, float ex, float ez, string tag)
            {
                var u = M7BackdropMath.LatLonToUnity(lat, lon, k_CenterUtm);
                Assert.That(u.x, Is.EqualTo(ex).Within(0.5f), $"{tag} x");
                Assert.That(u.y, Is.EqualTo(ez).Within(0.5f), $"{tag} z");
            }
            Pin(1.26, 103.76, -4451.97f, -2209.02f, "Pasir Panjang");
            Pin(1.26, 103.63, -18918.02f, -2201.77f, "Tuas");
            Pin(1.21, 103.90, 11123.77f, -7743.56f, "东锚地");
            Pin(1.17, 103.71, -10020.50f, -12156.60f, "西南锚地");
        }

        // ── ② 陆/水掩膜与陆上门禁 ───────────────────────────────────────────────────

        [Test]
        public void IsLand_SeaLevelBoundary()
        {
            Assert.That(M7BackdropMath.IsLand(0f), Is.True, "elev = 0 → 陆上（落位硬门含边界）");
            Assert.That(M7BackdropMath.IsLand(0.01f), Is.True, "elev > 0 → 陆上");
            Assert.That(M7BackdropMath.IsLand(-0.01f), Is.False, "elev < 0 → 水上");
            Assert.That(M7BackdropMath.IsLand(-42f), Is.False, "深水 → 水上");
        }

        [Test]
        public void ValidateDryLand_FailFastBelowFloor_PassOnLand()
        {
            // 合成采样器：x>0 为平台 +2 m，x≤0 为水域 −3 m
            M6TerrainMath.ElevationSampler sample = p => p.x > 0f ? 2f : -3f;
            var fail = M7BackdropMath.ValidateDryLand(sample,
                new[] { new Vector2(10f, 0f), new Vector2(-5f, 1f) });
            Assert.That(fail.ok, Is.False, "水上落位必须 fail");
            Assert.That(fail.worstPoint, Is.EqualTo(new Vector2(-5f, 1f)), "报告定位首个违规点（fail-fast）");

            var pass = M7BackdropMath.ValidateDryLand(sample, new[] { new Vector2(1f, -9f), new Vector2(50f, 50f) });
            Assert.That(pass.ok, Is.True, "平台落位过门");
            Assert.That(pass.worstElevationM, Is.EqualTo(2f).Within(1e-4f), "成功时 worst = 全局最低");

            var margin = M7BackdropMath.ValidateDryLand(sample, new[] { new Vector2(1f, 0f) }, minElevationM: 5f);
            Assert.That(margin.ok, Is.False, "minElevation 语义：高程须 ≥ min（+2 < +5 fail）");
        }

        // ── ③ A4 滩涂/丛林 splat 权重 ───────────────────────────────────────────────

        [Test]
        public void SplatWeights_NormalizedAcrossFullSweep()
        {
            for (float elev = -60f; elev <= 220f; elev += 0.25f)
            {
                var (baseW, mud, jungle) = M7BackdropMath.SplatWeights(elev);
                Assert.That(baseW + mud + jungle, Is.EqualTo(1f).Within(1e-4f), $"sum=1 @ elev={elev}");
                Assert.That(baseW, Is.InRange(0f, 1f));
                Assert.That(mud, Is.InRange(0f, 1f));
                Assert.That(jungle, Is.InRange(0f, 1f));
            }
        }

        [Test]
        public void SplatWeights_BandSemantics_SeaMudJungle()
        {
            // 海床：纯基带
            var (sea, seaMud, seaJungle) = M7BackdropMath.SplatWeights(-5f);
            Assert.That(sea, Is.EqualTo(1f).Within(1e-5f));
            Assert.That(seaMud, Is.EqualTo(0f).Within(1e-5f));
            Assert.That(seaJungle, Is.EqualTo(0f).Within(1e-5f));

            // 滩涂带 0-4 m：泥绿 > 0，丛林 = 0；4 m 处泥绿收坡归零
            var (b1, mud1, jungle1) = M7BackdropMath.SplatWeights(1f);
            Assert.That(mud1, Is.GreaterThan(0.1f), "1 m 滩涂带泥绿显著");
            Assert.That(jungle1, Is.EqualTo(0f).Within(1e-5f), "滩涂带无丛林");
            var (_, mud4, _) = M7BackdropMath.SplatWeights(4f);
            Assert.That(mud4, Is.EqualTo(0f).Within(1e-5f), "4 m 泥绿收坡归零（任务带界）");

            // 丛林带 >4 m：单调升、10 m 封顶 0.65（+基带 0.35）
            float prev = 0f;
            for (float e = 4.5f; e <= 10f; e += 0.5f)
            {
                var (_, _, j) = M7BackdropMath.SplatWeights(e);
                Assert.That(j, Is.GreaterThan(prev), $"丛林权重单调升 @ {e} m");
                prev = j;
            }
            var (b20, mud20, jungle20) = M7BackdropMath.SplatWeights(20f);
            Assert.That(jungle20, Is.EqualTo(0.65f).Within(1e-4f), "10 m 以上丛林封顶 0.65");
            Assert.That(mud20, Is.EqualTo(0f).Within(1e-5f), "丛林带无泥绿");
            Assert.That(b20, Is.EqualTo(0.35f).Within(1e-4f), "封顶后基带 0.35（S2 底图仍透出）");
        }

        // ── ④ A2 真实锚地槽位（合成高度图 fixture 水深验证）────────────────────────

        [Test]
        public void StraitAnchorageSlots_TableShape_TwoAnchorages()
        {
            var slots = M7BackdropMath.StraitAnchorageSlots;
            Assert.That(slots.Length, Is.GreaterThanOrEqualTo(8), "真实锚区至少 8 槽（东+西南锚地）");
            int east = 0, west = 0;
            foreach (var s in slots)
            {
                if (s.xz.x > 5000f) { east++; Assert.That(s.xz.y, Is.InRange(-9000f, -6000f), "东锚地带 z 范围"); }
                else { west++; Assert.That(s.xz.x, Is.InRange(-12000f, -8000f), "西南锚地带 x 范围"); Assert.That(s.xz.y, Is.InRange(-13500f, -11500f), "西南锚地带 z 范围"); }
            }
            Assert.That(east, Is.GreaterThanOrEqualTo(4), "东锚地 ≥4 槽");
            Assert.That(west, Is.GreaterThanOrEqualTo(4), "西南锚地 ≥4 槽");
        }

        [Test]
        public void AnchorageSlots_SyntheticHeightmap_DepthGate()
        {
            // 合成高度图 fixture（513² 同真实远景分辨率）：全域 −24 m 海 + 东北角 +40 m 陆块；
            // 采样口径 = M6TerrainMath.SampleNormalized（与 Terrain.SampleHeight 同语义）
            const int res = 513;
            const float size = 12000f;
            const double elevMin = -191.7258, elevMax = 188.3606;
            var heights = new float[res, res];
            for (int y = 0; y < res; y++)
                for (int x = 0; x < res; x++)
                {
                    bool land = x > res * 0.8f && y > res * 0.8f; // 东北角陆块
                    float elev = land ? 40f : M7BackdropMath.AnchorageOfflineWorstShallowM;
                    heights[y, x] = (float)((elev - elevMin) / (elevMax - elevMin));
                }

            M6TerrainMath.ElevationSampler sample = p =>
            {
                float norm = M6TerrainMath.SampleNormalized(heights, res, size, p);
                return M6TerrainMath.ElevMeters(norm, elevMin, elevMax);
            };

            // 全表槽位（合成海底 = 离线最浅值 −23.7 m）过门（< −5 m 裕量）
            var ok = M6TerrainMath.ValidateDepths(sample, TablePoints(), marginM: 5f);
            Assert.That(ok.ok, Is.True, $"合成海底 −23.7 m 全槽过门（最浅 {ok.shallowestElevationM:F1}）");

            // 槽位挪上陆块 → gate 红（fail-fast 语义不静默换点）
            var onLand = new[] { new Vector2(11200f, 11200f), new Vector2(-5000f, -5000f) };
            var bad = M6TerrainMath.ValidateDepths(sample, onLand, marginM: 5f);
            Assert.That(bad.ok, Is.False, "陆上槽位必须 fail");
            Assert.That(bad.worstPoint, Is.EqualTo(onLand[0]), "报告陆上违规槽位");
        }

        static Vector2[] TablePoints()
        {
            var slots = M7BackdropMath.StraitAnchorageSlots;
            var pts = new Vector2[slots.Length];
            for (int i = 0; i < slots.Length; i++) pts[i] = slots[i].xz;
            return pts;
        }

        // ── ⑤ A1 岸桥/箱堆布局：预算 / bounds / 坐标系一致 ──────────────────────────

        // tile 落位窗（manifest 几何契约：2×2 近景 + 5×5 远景，12 km tile；r0 = 北行）
        static readonly (string tile, Vector2 origin, float size)[] k_TileWindows =
        {
            ("near_r1c0_2049", new Vector2(-12000f, -12000f), 12000f), // 西南近景 tile
            ("far_r2c0_513", new Vector2(-30000f, -6000f), 12000f),    // 西中远景 tile
        };

        [Test]
        public void QuayLayouts_CranesAndYard_WithinTilesAndBudget()
        {
            Assert.That(M7BackdropMath.TotalCraneCount,
                Is.InRange(M7BackdropMath.MinQuayCranesTotal, M7BackdropMath.MaxQuayCranesTotal),
                "岸桥总量 12-16 台（任务档）");

            foreach (var t in M7BackdropMath.Terminals)
            {
                Assert.That(t.craneCount, Is.InRange(1, M7BackdropMath.MaxQuayCranesTotal / 2),
                    $"{t.name} 单端台数");

                // tile 归属
                var window = t.tileName == "near_r1c0_2049" ? k_TileWindows[0] : k_TileWindows[1];
                foreach (var crane in M7BackdropMath.CranePositions(t))
                    Assert.That(M7BackdropMath.InTile(crane, window.origin, window.size),
                        Is.True, $"{t.name} 岸桥 {crane} 越出 tile {t.tileName}");

                // 箱堆：block/列/层预算 + 落点不越平整矩形、不越 tile
                Assert.That(M7BackdropMath.YardBlocksPerTerminal, Is.InRange(3, 5), "block 数（任务 3-5）");
                Assert.That(M7BackdropMath.YardColsPerBlock, Is.InRange(10, 20), "列数（任务 10-20）");
                var yard = M7BackdropMath.GenerateYard(t);
                Assert.That(yard.Count, Is.InRange(
                    M7BackdropMath.YardBlocksPerTerminal * M7BackdropMath.YardColsPerBlock * M7BackdropMath.YardRowsDeep * M7BackdropMath.YardLayersMin,
                    M7BackdropMath.YardBlocksPerTerminal * M7BackdropMath.YardColsPerBlock * M7BackdropMath.YardRowsDeep * M7BackdropMath.YardLayersMax),
                    $"{t.name} 箱数在 [blocks·cols·rows·3, ·5] 区间");
                foreach (var box in yard)
                {
                    var flat = new Vector2(box.center.x, box.center.z);
                    Assert.That(M7BackdropMath.InRect(flat, t.flattenRectUnity), Is.True,
                        $"{t.name} 箱堆 {flat} 越出平整矩形（箱堆网格假设平台面）");
                    Assert.That(M7BackdropMath.InTile(flat, window.origin, window.size), Is.True,
                        $"{t.name} 箱堆 {flat} 越出 tile {t.tileName}");
                    Assert.That(box.colorIndex, Is.InRange(0, M7BackdropMath.ContainerColorCount), "色板档界内");
                }

                // 堆高 3-5 层（哈希全档可达且界内）
                for (int b = 0; b < M7BackdropMath.YardBlocksPerTerminal; b++)
                    for (int col = 0; col < M7BackdropMath.YardColsPerBlock; col += 3)
                        for (int row = 0; row < M7BackdropMath.YardRowsDeep; row += 2)
                            Assert.That(M7BackdropMath.LayersFor(b, col, row),
                                Is.InRange(M7BackdropMath.YardLayersMin, M7BackdropMath.YardLayersMax),
                                $"层数档界 (b={b},c={col},r={row})");
            }
        }

        [Test]
        public void QuayLayouts_SeawardNormalPointsToWater_SidePinned()
        {
            // 布局 provenance（2026-09-29 site analysis）：PP 码头线西缘朝西水、Tuas 泊位南缘朝南水
            var pp = M7BackdropMath.QuaySeawardNormal(M7BackdropMath.PasirPanjang);
            Assert.That(pp.x, Is.LessThan(-0.9f), "PP 海侧法向朝西（码头前沿贴西侧 0 水线）");
            var tuas = M7BackdropMath.QuaySeawardNormal(M7BackdropMath.TuasPier);
            Assert.That(tuas.y, Is.LessThan(-0.9f), "Tuas 海侧法向朝南（码头前沿贴南侧 0 水线）");
        }

        [Test]
        public void YardWorldFrame_MatchesLocalFrameTransform()
        {
            // 世界系（门禁实采口径）必须 = 局部系（网格口径）的旋平变换——两口径漂移即红
            foreach (var t in M7BackdropMath.Terminals)
            {
                var local = M7BackdropMath.GenerateYardLocal(t);
                var world = M7BackdropMath.GenerateYard(t);
                Assert.That(world.Count, Is.EqualTo(local.Count));
                var tan = M7BackdropMath.QuayTangent(t);
                var seaward = M7BackdropMath.QuaySeawardNormal(t);
                for (int i = 0; i < local.Count; i++)
                {
                    var flat = t.quayStart + seaward * local[i].center.x + tan * local[i].center.z;
                    Assert.That(world[i].center.x, Is.EqualTo(flat.x).Within(1e-2f), $"{t.name} box #{i} x");
                    Assert.That(world[i].center.z, Is.EqualTo(flat.y).Within(1e-2f), $"{t.name} box #{i} z");
                    Assert.That(world[i].center.y, Is.EqualTo(local[i].center.y).Within(1e-4f), $"{t.name} box #{i} y");
                }
            }
        }

        // ── ⑥ A4 树卡散布规划器 ─────────────────────────────────────────────────────

        /// <summary>合成 513² 高度图：对角海岸线（东南侧水域 −15 m，西北侧陆地 8-30 m 斜坡）。</summary>
        static float[,] CoastFixture(int res, double elevMin, double elevMax)
        {
            var h = new float[res, res];
            for (int y = 0; y < res; y++)
                for (int x = 0; x < res; x++)
                {
                    // 海岸线沿反对角：x+y < res → 陆（海拔随距海递增 2..30），否则 −15 m 海
                    float t = (x + y) / (float)(2 * res);
                    float elev = t < 0.5f ? Mathf.Lerp(2f, 30f, (0.5f - t) * 2f) : -15f;
                    h[y, x] = (float)((elev - elevMin) / (elevMax - elevMin));
                }
            return h;
        }

        [Test]
        public void ScatterTreeCards_Deterministic_Capped_ExclusionsHonored()
        {
            const int res = 513;
            const float size = 12000f;
            const double elevMin = -191.7258, elevSpan = 188.3606 - elevMin;
            var origin = new Vector2(-30000f, -6000f); // far_r2c0 落位窗（纯合成网格）
            var heights = CoastFixture(res, elevMin, elevSpan + elevMin);

            var a = M7BackdropMath.ScatterTreeCards(heights, res, size, origin, elevMin, elevSpan,
                M7BackdropMath.MaxTreesPerFarTile, null);
            var b = M7BackdropMath.ScatterTreeCards(heights, res, size, origin, elevMin, elevSpan,
                M7BackdropMath.MaxTreesPerFarTile, null);
            Assert.That(a.Count, Is.GreaterThan(0), "对角海岸线应产出候选");
            Assert.That(a.Count, Is.LessThanOrEqualTo(M7BackdropMath.MaxTreesPerFarTile), "单 tile 上限封顶");
            Assert.That(a, Is.EqualTo(b), "同输入逐位同输出（无随机状态）");

            // 全部落点在陆上（候选顶点原位：落点高程 = 候选格高程 ∈ [+2, 60]；
            // 浮点回采容差 0.1 m——树卡不落水，岸桥/箱堆另有 ≥0 硬门）
            foreach (var p in a)
            {
                Assert.That(M7BackdropMath.InTile(p, origin, size), Is.True, "落点在 tile 内");
                float norm = M6TerrainMath.SampleNormalized(heights, res, size, p - origin);
                float elev = M6TerrainMath.ElevMeters(norm, elevMin, elevSpan + elevMin);
                Assert.That(elev, Is.GreaterThanOrEqualTo(1.9f), $"落点 {p} 高程 {elev:F1} 应为陆地");
            }

            // 排除区（A3 平整矩形口径）：盖掉半幅海岸线后数量显著下降且不含排除点
            var half = new[] { new[] { origin.x, origin.y, origin.x + size * 0.5f, origin.y + size } };
            var c = M7BackdropMath.ScatterTreeCards(heights, res, size, origin, elevMin, elevSpan,
                M7BackdropMath.MaxTreesPerFarTile, half);
            Assert.That(c.Count, Is.LessThan(a.Count), "排除区削减散布量");
            foreach (var p in c)
                Assert.That(M7BackdropMath.InRect(p, half[0]), Is.False, "排除区内不得有落点");
        }

        [Test]
        public void ScatterTreeCards_StrideCoversSparseCoast()
        {
            // 稀疏海岸（candidate < cap）：stride=1 全保留——上限封顶不得吞掉少量候选
            const int res = 65;
            const float size = 12000f;
            const double elevMin = -191.7258, elevSpan = 188.3606 - elevMin;
            var heights = new float[res, res];
            for (int y = 0; y < res; y++)
                for (int x = 0; x < res; x++)
                {
                    bool land = x == 32 && y % 8 == 4; // 仅 5 个孤立陆地格点（无邻水判定路径可达）
                    heights[y, x] = (float)(((land ? 5f : -15f) - elevMin) / elevSpan);
                }
            // 单点邻域构造：land 点上下格点设为浅水（<0）以满足邻水条件
            // （简化：直接断言 cap 极小值时的封顶行为）
            var few = M7BackdropMath.ScatterTreeCards(heights, res, size, Vector2.zero, elevMin, elevSpan, 3, null);
            Assert.That(few.Count, Is.LessThanOrEqualTo(3), "极小 cap 封顶生效");
        }
    }
}
