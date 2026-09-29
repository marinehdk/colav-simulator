using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using Sango;
using UnityEditor;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M6 地形数据契约 EditMode 测试（RAW 解码/换算/manifest 模型/网格布局/水深采样/
    /// TerrainData 构建契约）。fixture = Assets/Tests/Fixtures 合成件（33² u16 小端 RAW +
    /// 2×2 近景 / 5×5 远景 manifest JSON，字段名与真实 tmp/m6-data/manifest.json 同构）。
    /// M5 F1 教训：TerrainData 断言走 fresh 构建路径（new TerrainData + SetHeights），
    /// 不吃场景存档实例。真实数据的消费链由 M6TerrainPipeline/M6StraitSceneBootstrapper
    /// 构建期 fail-fast 门（水深验证）覆盖，不在此拉真实 RAW（测试与 tmp/ 解耦）。
    /// </summary>
    public class M6TerrainModelTests
    {
        const string k_ManifestFixture = "Tests/Fixtures/m6-manifest-fixture.json";
        const string k_RawFixture = "Tests/Fixtures/m6-tile-33x33.raw";
        const int k_Res = 33;

        readonly List<Object> m_Spawned = new List<Object>();

        [TearDown]
        public void TearDown()
        {
            // 逆序销毁：先场景对象（Terrain GO）再其依赖的 TerrainData，避免悬挂引用告警
            for (int i = m_Spawned.Count - 1; i >= 0; i--)
                if (m_Spawned[i] != null) Object.DestroyImmediate(m_Spawned[i]);
            m_Spawned.Clear();
        }

        static string FixturePath(string rel) => Path.Combine(Application.dataPath, rel);

        static M6Manifest LoadFixtureManifest()
        {
            string path = FixturePath(k_ManifestFixture);
            Assert.That(File.Exists(path), Is.True, $"fixture 缺失：{path}");
            return M6Manifest.Parse(File.ReadAllText(path));
        }

        static byte[] LoadFixtureRaw()
        {
            string path = FixturePath(k_RawFixture);
            Assert.That(File.Exists(path), Is.True, $"fixture 缺失：{path}");
            return File.ReadAllBytes(path);
        }

        // ── RAW 解码：小端 + 行序北上（垂直翻转）────────────────────────────────────

        [Test]
        public void ReadU16Grid_LittleEndianRoundTrip()
        {
            // 已知值编码为小端字节流（低字节在前），2×2 网格读回必须逐位相等
            var values = new ushort[] { 0x0000, 0x0001, 0x0100, 0xBEEF };
            var bytes = new byte[values.Length * 2];
            for (int i = 0; i < values.Length; i++)
            {
                bytes[i * 2] = (byte)(values[i] & 0xFF);
                bytes[i * 2 + 1] = (byte)(values[i] >> 8);
            }
            var grid = M6TerrainMath.ReadU16GridLittleEndian(bytes, 2); // res = 网格边长（res² 样值）
            Assert.That(grid[0, 0], Is.EqualTo(0x0000), "u16 #0（小端：低字节在前）");
            Assert.That(grid[0, 1], Is.EqualTo(0x0001), "u16 #1");
            Assert.That(grid[1, 0], Is.EqualTo(0x0100), "u16 #2（0x0100 小端 = 00 01，字节序硬证）");
            Assert.That(grid[1, 1], Is.EqualTo(0xBEEF), "u16 #3");
        }

        [Test]
        public void DecodeNormalizedHeights_VerticalFlipsNorthRowFirst()
        {
            // fixture RAW：row r 值 = r*1000+c（row 0 = 最北行）；解码后 heights[y,x]
            // 的 y=0 是最南行 → RAW 末行（r=32）必须落到 heights[0,*]
            var heights = M6TerrainMath.DecodeNormalizedHeights(LoadFixtureRaw(), k_Res);
            for (int c = 0; c < k_Res; c += 8)
            {
                Assert.That(heights[0, c], Is.EqualTo((32 * 1000 + c) / 65535f).Within(1e-6f),
                    $"heights[0,{c}] 应 = RAW 北端行 r=32（翻转）");
                Assert.That(heights[k_Res - 1, c], Is.EqualTo((0 * 1000 + c) / 65535f).Within(1e-6f),
                    $"heights[{k_Res - 1},{c}] 应 = RAW row 0（最北 → 最南行落位）");
            }
        }

        [Test]
        public void DecodeNormalizedHeights_NormalizedEndpoints()
        {
            // 2×2：RAW row0 = [0, 1]（北行），row1 = [256, 65535]（南行）；翻转后 heights row0 = RAW row1
            var bytes = new byte[] { 0x00, 0x00, 0x01, 0x00, 0x00, 0x01, 0xFF, 0xFF };
            var heights = M6TerrainMath.DecodeNormalizedHeights(bytes, 2);
            Assert.That(heights[0, 0], Is.EqualTo(256 / 65535f).Within(1e-6f), "南行 ← RAW row1[0]：u16=256 → 256/65535");
            Assert.That(heights[0, 1], Is.EqualTo(1f).Within(1e-6f), "南行：u16=65535 → 归一化 1");
            Assert.That(heights[1, 0], Is.EqualTo(0f).Within(1e-6f), "北行 ← RAW row0[0]：u16=0 → 0");
            Assert.That(heights[1, 1], Is.EqualTo(1 / 65535f).Within(1e-6f), "u16=1 → 1/65535");
        }

        [Test]
        public void DecodeNormalizedHeights_WrongSizeThrows()
        {
            Assert.That(() => M6TerrainMath.DecodeNormalizedHeights(new byte[10], k_Res),
                Throws.ArgumentException, "长度 ≠ res²×2 必须显式失败（ENVI u16 BSQ 契约）");
        }

        // ── u16 → 米换算（elev_m = min + u16/65535*(max-min)，海面下为负）────────────

        [Test]
        public void ElevMeters_FromU16_EndpointsAndMidpoint()
        {
            const double min = -191.5692, max = 188.4488; // 真实近景带 scale（notes.md 规格表）
            Assert.That(M6TerrainMath.ElevMetersFromU16(0, min, max), Is.EqualTo(-191.5692).Within(1e-3), "u16=0 → elev_min");
            Assert.That(M6TerrainMath.ElevMetersFromU16(65535, min, max), Is.EqualTo(188.4488).Within(1e-3), "u16=65535 → elev_max");
            Assert.That(M6TerrainMath.ElevMetersFromU16(32768, min, max),
                Is.EqualTo((min + max) / 2.0).Within((max - min) / 65535.0 + 1e-3), "中值 → 带中点（半格量化容差）");
        }

        [Test]
        public void ElevMeters_SeaLevelSplit()
        {
            const double min = -10.0, max = 30.0; // fixture 近景带
            // u16 = 49152 (0.75) → 20 m（水上）；u16 = 16384 (0.25) → 0 m；u16 = 8192 → −5 m
            Assert.That(M6TerrainMath.ElevMetersFromU16(49152, min, max), Is.GreaterThan(0f), "0.75 → 陆上正值");
            Assert.That(M6TerrainMath.ElevMetersFromU16(8192, min, max), Is.EqualTo(-5f).Within(0.01), "0.25 以下 → 海面下负值");
        }

        // ── manifest 模型解析（字段名即契约）────────────────────────────────────────

        [Test]
        public void ManifestParse_FixtureContract()
        {
            var m = LoadFixtureManifest();
            Assert.That(m.epsg, Is.EqualTo(32648), "EPSG:32648（UTM 48N）");
            Assert.That(m.center_utm, Is.Not.Null.And.Length.EqualTo(2), "center_utm = [E,N]");
            Assert.That(m.center_utm[0], Is.EqualTo(100000f).Within(0.01f));
            Assert.That(m.center_utm[1], Is.EqualTo(200000f).Within(0.01f));
            Assert.That(m.near, Is.Not.Null);
            Assert.That(m.far, Is.Not.Null);
            Assert.That(m.near.tiles.Length, Is.EqualTo(4), "近景 2×2");
            Assert.That(m.far.tiles.Length, Is.EqualTo(25), "远景 5×5");
            Assert.That(m.near.tile_px, Is.EqualTo(33), "tile_px（=2^n+1 顶点格，真实带 2049/513）");
            Assert.That(m.near.tile_size_m, Is.EqualTo(100f).Within(1e-3f), "tile_size_m（真实带 12000）");
            Assert.That(m.near.grid, Is.EqualTo(new[] { 2, 2 }));
            Assert.That(m.near.elev_min, Is.EqualTo(-10.0).Within(1e-6), "带内共用 u16 scale");
            Assert.That(m.near.elev_max, Is.EqualTo(30.0).Within(1e-6));
            var t = m.near.tiles[0];
            Assert.That(t.name, Is.EqualTo("near_r0c0_33"), "tile 命名 {tier}_r{row}c{col}_{px}（row 0 = 最北行）");
            Assert.That(t.utm_bounds, Is.Not.Null.And.Length.EqualTo(4), "utm_bounds = [xmin,ymin,xmax,ymax]");
            Assert.That(t.path_raw, Does.StartWith("tmp/"), "path 仓库根相对（V7 同口径）");
            // s2 等未声明字段静默跳过不炸（ColavTelemetry 纪律）
        }

        // ── tile 网格布局：bounds 无缝无重叠、Unity 原点 = 区域中心 ───────────────────

        [Test]
        public void LayoutFor_UnityOriginAtCenter()
        {
            var m = LoadFixtureManifest();
            var center = new Vector2(m.center_utm[0], m.center_utm[1]);
            var t = m.near.tiles[0]; // r0c0：西北角 tile
            var layout = M6TerrainMath.LayoutFor(t, m.near, center);
            Assert.That(layout.originXZ.x, Is.EqualTo(t.utm_bounds[0] - center.x).Within(1e-3f), "origin.x = xmin − center");
            Assert.That(layout.originXZ.y, Is.EqualTo(t.utm_bounds[1] - center.y).Within(1e-3f), "origin.y = ymin − center（tile 西南角）");
            Assert.That(layout.sizeMeters, Is.EqualTo(m.near.tile_size_m));
            Assert.That(layout.heightmapResolution, Is.EqualTo(m.near.tile_px));
            Assert.That(layout.elevMin, Is.EqualTo(m.near.elev_min).Within(1e-6));
            Assert.That(layout.elevSpan, Is.EqualTo(m.near.elev_max - m.near.elev_min).Within(1e-6), "terrainData.size.y = 带高程全量程");
        }

        [Test]
        public void NearGrid_SeamsShared_NoGapsNoOverlap()
        {
            var m = LoadFixtureManifest();
            BandTilesSeamless(m.near);
        }

        [Test]
        public void FarGrid_CoversExtent_NoGapsNoOverlap()
        {
            var m = LoadFixtureManifest();
            BandTilesSeamless(m.far);
        }

        static void BandTilesSeamless(M6Band band)
        {
            float sum = 0f;
            float xmin = float.MaxValue, ymin = float.MaxValue, xmax = float.MinValue, ymax = float.MinValue;
            foreach (var t in band.tiles)
            {
                float w = t.utm_bounds[2] - t.utm_bounds[0];
                float h = t.utm_bounds[3] - t.utm_bounds[1];
                Assert.That(w, Is.EqualTo(band.tile_size_m).Within(0.5f), $"{t.name} 宽 = tile_size_m");
                Assert.That(h, Is.EqualTo(band.tile_size_m).Within(0.5f), $"{t.name} 高 = tile_size_m");
                sum += w * h;
                xmin = Mathf.Min(xmin, t.utm_bounds[0]); ymin = Mathf.Min(ymin, t.utm_bounds[1]);
                xmax = Mathf.Max(xmax, t.utm_bounds[2]); ymax = Mathf.Max(ymax, t.utm_bounds[3]);
            }
            // 两两无重叠（相邻 tile 共享 1 px 边 = 面积交 0）
            for (int i = 0; i < band.tiles.Length; i++)
                for (int j = i + 1; j < band.tiles.Length; j++)
                    Assert.That(M6TerrainMath.OverlapAreaM2(band.tiles[i].utm_bounds, band.tiles[j].utm_bounds),
                        Is.EqualTo(0f).Within(0.5f),
                        $"{band.tiles[i].name} × {band.tiles[j].name} 不得重叠");
            // 并集 = extent（无缺口）：面积和 = extent 面积 且 包络 = extent
            float extentArea = (band.extent_utm[2] - band.extent_utm[0]) * (band.extent_utm[3] - band.extent_utm[1]);
            Assert.That(sum, Is.EqualTo(extentArea).Within(1f), "tile 面积和 = 带面积（无缝无重叠）");
            Assert.That(xmin, Is.EqualTo(band.extent_utm[0]).Within(0.5f));
            Assert.That(ymin, Is.EqualTo(band.extent_utm[1]).Within(0.5f));
            Assert.That(xmax, Is.EqualTo(band.extent_utm[2]).Within(0.5f));
            Assert.That(ymax, Is.EqualTo(band.extent_utm[3]).Within(0.5f));
        }

        [Test]
        public void FarTileUnderNearBand_FixtureOverlapSet()
        {
            var m = LoadFixtureManifest();
            var under = new HashSet<string>();
            foreach (var t in m.far.tiles)
                if (M6TerrainMath.FarTileUnderNearBand(t, m.near.extent_utm))
                    under.Add(t.name);
            // 近景带 [99850,199850]-[100050,200050] 压住远景网格内部 2×2=4 块；
            // 边界相触（r1/r4 行、c0/c4 列）面积=0 不算（真实数据网格半 tile 偏移 → 交叠 9 块，
            // 编排者 2026-09-29 裁决覆盖语义——见 M6TerrainMath.FarTileUnderNearBand 注释）。
            Assert.That(under, Is.EquivalentTo(new[]
            {
                "far_r2c1_33", "far_r2c2_33",
                "far_r3c1_33", "far_r3c2_33",
            }));
        }

        // ── 水深采样纯函数 ───────────────────────────────────────────────────────────

        [Test]
        public void SampleNormalized_BilinearExactOnLinearRamp()
        {
            // 线性斜面 heights[y,x] = (x + y)/(2*(res-1))：任意内点双线性插值应精确复现
            var heights = new float[k_Res, k_Res];
            for (int y = 0; y < k_Res; y++)
                for (int x = 0; x < k_Res; x++)
                    heights[y, x] = (x + y) / (2f * (k_Res - 1));
            foreach (var local in new[] { new Vector2(50f, 0f), new Vector2(0f, 50f), new Vector2(25f, 75f), new Vector2(62.5f, 12.5f) })
            {
                float expected = (local.x + local.y) / (2f * 100f); // size=100
                Assert.That(M6TerrainMath.SampleNormalized(heights, k_Res, 100f, local),
                    Is.EqualTo(expected).Within(1e-4f), $"local {local}");
            }
        }

        [Test]
        public void ValidateDepths_FailFastOnLand_PassOnDeep()
        {
            // 合成地形：东北象限是 +5 m 岛，其余 −20 m 海
            M6TerrainMath.ElevationSampler sampler = p => (p.x > 0f && p.y > 0f) ? 5f : -20f;
            var fail = M6TerrainMath.ValidateDepths(sampler, new[] { new Vector2(-10f, -10f), new Vector2(10f, 10f) });
            Assert.That(fail.ok, Is.False, "岛上位必须 fail");
            Assert.That(fail.worstPoint, Is.EqualTo(new Vector2(10f, 10f)), "报告定位违规点（fail-fast 不静默换点）");

            var pass = M6TerrainMath.ValidateDepths(sampler, new[] { new Vector2(-10f, -10f), new Vector2(10f, -10f) }, marginM: 5f);
            Assert.That(pass.ok, Is.True, "深水位 + 5 m 裕量应过门（−20 < −5）");

            var marginFail = M6TerrainMath.ValidateDepths(sampler, new[] { new Vector2(-10f, -10f) }, marginM: 25f);
            Assert.That(marginFail.ok, Is.False, "裕量 25 m 时 −20 m 不达标：margin 语义 = 高程须 < −margin");
        }

        [Test]
        public void ValidateRoute_SamplesSegments_CatchesIslandCrossing()
        {
            M6TerrainMath.ElevationSampler sampler = p => (p.x > 0f && p.y > 0f) ? 5f : -20f;
            // 深水全程（第三象限）：过门 + 采样数 ≥ ceil(总长/步)+1
            var deep = new[] { new Vector2(-100f, -100f), new Vector2(-10f, -10f) };
            var pass = M6TerrainMath.ValidateRoute(sampler, deep, 7f);
            Assert.That(pass.ok, Is.True);
            Assert.That(pass.samples, Is.GreaterThanOrEqualTo(Mathf.CeilToInt(90f * Mathf.Sqrt(2f) / 7f) + 1),
                "逐段插值采样覆盖（步长 7 m）");

            // 穿岛航线（x<0 → x>0 横穿岛盘）：fail 且报告落在岛上的采样点
            var crossing = new[] { new Vector2(-100f, 50f), new Vector2(100f, 50f) };
            var fail = M6TerrainMath.ValidateRoute(sampler, crossing, 10f);
            Assert.That(fail.ok, Is.False, "穿岛航线必须 fail（防搁浅 fail-fast）");
            Assert.That(fail.worstPoint.x, Is.GreaterThan(0f), "违规点在岛象限");
        }

        // ── TerrainData 构建契约（fresh 构建路径：fixture RAW → SetHeights → SampleHeight）──

        [Test]
        public void TerrainDataFreshBuild_SetHeightsSamplingMatchesElevMeters()
        {
            var m = LoadFixtureManifest();
            double elevMin = m.near.elev_min, elevMax = m.near.elev_max;
            float size = m.near.tile_size_m;
            var heights = M6TerrainMath.DecodeNormalizedHeights(LoadFixtureRaw(), k_Res);

            // fresh 构建（非场景存档实例）：M6TerrainPipeline.BuildBand 同款赋值序列
            var data = new TerrainData { heightmapResolution = k_Res, size = new Vector3(size, (float)(elevMax - elevMin), size) };
            m_Spawned.Add(data);
            data.SetHeights(0, 0, heights);

            var go = Terrain.CreateTerrainGameObject(data);
            m_Spawned.Add(go);
            var origin = new Vector3(500f, (float)elevMin, -200f); // 任意世界位（y=elevMin → 世界 y=真实高程）
            go.transform.position = origin;

            // 顶点格抽样：世界高程 = SampleHeight + terrain.position.y（**实证**：Terrain.SampleHeight
            // 返回高度图数据高 0..size.y，不含 transform.position.y 偏移——本测试首跑红抓出，
            // M6StraitSceneBootstrapper.BuildSampler 同口径），必须 = ElevMeters(归一化)
            var terrain = go.GetComponent<Terrain>();
            foreach (var (gx, gz) in new[] { (0, 0), (16, 16), (32, 32), (5, 27), (32, 0) })
            {
                var world = new Vector3(origin.x + gx * (size / (k_Res - 1)), 0f, origin.z + gz * (size / (k_Res - 1)));
                float expected = M6TerrainMath.ElevMeters(heights[gz, gx], elevMin, elevMax);
                Assert.That(terrain.SampleHeight(world) + go.transform.position.y,
                    Is.EqualTo(expected).Within(0.02 * (elevMax - elevMin)),
                    $"格点 (x={gx},z={gz})：SetHeights 采样 ↔ u16 换算（含 elevMin 锚定与翻转行序）");
            }

            // 海面语义抽验：fixture RAW row32（最南行）值域 32000..32032 → 0.49 ~ 12.9 m 陆上；
            // 归一化 < 0.25 的格点高程必须为负（海面 y=0 之下）
            int negatives = 0;
            for (int y = 0; y < k_Res; y++)
                for (int x = 0; x < k_Res; x++)
                    if (M6TerrainMath.ElevMeters(heights[y, x], elevMin, elevMax) < 0f) negatives++;
            Assert.That(negatives, Is.GreaterThan(0), "带 scale [−10,30] 下 u16<49152 的格点应为水下");
        }
    }
}
