using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M7-B 海峡浮标/动目标/大气档/渔排纯函数 EditMode 测试（合成 fixture，不拉 tmp/ 真实数据
    /// ——真实数据由构建期 Terrain.SampleHeight 门禁实采复验，口径同 M7BackdropMathTests）：
    /// ①B1 浮标布局契约（计数窗/种别齐全/落位唯一/在区域内）+ 水深门禁咬合；
    /// ②灯质节奏（快闪/群闪/长闪曲线：周期性、脉冲计数、值域）；
    /// ③B2 渡轮/拖轮航线契约（往返回文/端点钉值/闭环半径窗）+ 逐点水深门禁（含
    ///   "绕岛群西缘改道"回归锚——合成岛摆在 DEM 实证岛群位置上，字面航线必须仍过门）；
    /// ④B3 大气三档 preset 契约（视程/雨开关/过渡时长窗）+ 档位循环状态机；
    /// ⑤B4 渔排落位契约（5 组/组间距/Batam 北浅水带）+ [-8,-2] 深度窗验证；
    /// ⑥系留微摇摆纯函数（幅值界/确定性/相位生效）。
    /// </summary>
    public class M7BMathTests
    {
        static readonly Vector2 k_CenterUtm = new Vector2(366493.325f, 141509.930f); // manifest center_utm

        // ── ① B1 浮标布局契约 ───────────────────────────────────────────────────────

        [Test]
        public void ChannelBuoys_CountWindowsAndKindsComplete()
        {
            Assert.That(M7BMath.ChannelBuoys.Length, Is.EqualTo(M7BMath.MainChannelBuoyCount + M7BMath.ApproachBuoyCount),
                "浮标总数 = 主航道带 + 航道口两账合计");

            int main = 0, approach = 0;
            var kinds = new Dictionary<M7BMath.IalaBuoyKind, int>();
            foreach (var b in M7BMath.ChannelBuoys)
            {
                if (b.approach) approach++; else main++;
                kinds.TryGetValue(b.kind, out int n);
                kinds[b.kind] = n + 1;
            }
            Assert.That(main, Is.InRange(6, 10), "主航道 TSS 边界带 6-10 座（任务窗）");
            Assert.That(approach, Is.InRange(2, 4), "近锚地航道口 2-4 座（任务窗）");

            Assert.That(kinds[M7BMath.IalaBuoyKind.PortHandCan], Is.GreaterThanOrEqualTo(1), "红罐（左舷/进港）在列");
            Assert.That(kinds[M7BMath.IalaBuoyKind.StarboardCone], Is.GreaterThanOrEqualTo(1), "绿锥（右舷/进港）在列");
            Assert.That(kinds[M7BMath.IalaBuoyKind.NorthCardinal], Is.EqualTo(1), "北方位标恰 1 座");
            Assert.That(kinds[M7BMath.IalaBuoyKind.SouthCardinal], Is.EqualTo(1), "南方位标恰 1 座");
            Assert.That(kinds[M7BMath.IalaBuoyKind.SafeWater], Is.EqualTo(1), "安全水域标恰 1 座");
        }

        [Test]
        public void ChannelBuoys_UniquePositionsInsideRegion()
        {
            for (int i = 0; i < M7BMath.ChannelBuoys.Length; i++)
            {
                var a = M7BMath.ChannelBuoys[i].xz;
                Assert.That(Mathf.Abs(a.x), Is.LessThanOrEqualTo(30000f), $"buoy {i} x 在远景带内");
                Assert.That(Mathf.Abs(a.y), Is.LessThanOrEqualTo(30000f), $"buoy {i} z 在远景带内");
                for (int j = i + 1; j < M7BMath.ChannelBuoys.Length; j++)
                    Assert.That(Vector2.Distance(a, M7BMath.ChannelBuoys[j].xz), Is.GreaterThan(1f),
                        $"buoy {i}/{j} 落位不重合");
            }
        }

        [Test]
        public void ChannelBuoys_DepthGate_BitesOnSyntheticIsland()
        {
            // 合成 fixture：全域深水 −50 m → 13 座全部过门
            M6TerrainMath.ElevationSampler deep = _ => -50f;
            var pts = new Vector2[M7BMath.ChannelBuoys.Length];
            for (int i = 0; i < pts.Length; i++) pts[i] = M7BMath.ChannelBuoys[i].xz;
            var pass = M6TerrainMath.ValidateDepths(deep, pts, 0f);
            Assert.That(pass.ok, Is.True, "合成深水 fixture：全部浮标点位高程 < 0");
            Assert.That(pass.samples, Is.EqualTo(pts.Length));

            // 合成岛摆在首座浮标脚下 → fail-fast 报告该浮标点位（门禁咬合，不静默）
            var trap = M7BMath.ChannelBuoys[0].xz;
            M6TerrainMath.ElevationSampler island = p => (p - trap).magnitude < 50f ? 5f : -50f;
            var fail = M6TerrainMath.ValidateDepths(island, pts, 0f);
            Assert.That(fail.ok, Is.False, "浮标落位高程 ≥ 0 必须触发门禁");
            Assert.That(fail.worstPoint, Is.EqualTo(trap), "报告定位违规浮标本身");
        }

        [Test]
        public void BuoyLightPatterns_ColorAndRhythmByKind()
        {
            Assert.That(M7BMath.PatternFor(M7BMath.IalaBuoyKind.PortHandCan), Is.EqualTo(M7BMath.BuoyBlinkPattern.QuickFlash));
            Assert.That(M7BMath.PatternFor(M7BMath.IalaBuoyKind.StarboardCone), Is.EqualTo(M7BMath.BuoyBlinkPattern.QuickFlash));
            Assert.That(M7BMath.PatternFor(M7BMath.IalaBuoyKind.NorthCardinal), Is.EqualTo(M7BMath.BuoyBlinkPattern.GroupFlash3));
            Assert.That(M7BMath.PatternFor(M7BMath.IalaBuoyKind.SouthCardinal), Is.EqualTo(M7BMath.BuoyBlinkPattern.GroupFlash3));
            Assert.That(M7BMath.PatternFor(M7BMath.IalaBuoyKind.SafeWater), Is.EqualTo(M7BMath.BuoyBlinkPattern.LongFlash));

            var red = M7BMath.LightColorFor(M7BMath.IalaBuoyKind.PortHandCan);
            Assert.That(red.r, Is.GreaterThan(0.5f), "左舷灯红");
            Assert.That(red.g, Is.LessThan(0.3f), "左舷灯非绿");
            var green = M7BMath.LightColorFor(M7BMath.IalaBuoyKind.StarboardCone);
            Assert.That(green.g, Is.GreaterThan(0.5f), "右舷灯绿");
            var white = M7BMath.LightColorFor(M7BMath.IalaBuoyKind.SafeWater);
            Assert.That(white.r, Is.GreaterThan(0.8f), "安全水域灯白");
            Assert.That(white.g, Is.GreaterThan(0.8f), "安全水域灯白");
        }

        // ── ② 灯质节奏曲线 ──────────────────────────────────────────────────────────

        [Test]
        public void BuoyLightIntensity_QuickFlash_OnePulsePerSecond()
        {
            Assert.That(M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.QuickFlash, 0.05f), Is.EqualTo(1f), "脉冲头部亮");
            Assert.That(M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.QuickFlash, 0.5f), Is.EqualTo(0f), "周期后半灭");
            for (float t = 0f; t < 3f; t += 0.1f)
            {
                float a = M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.QuickFlash, t);
                float b = M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.QuickFlash, t + M7BMath.QuickFlashPeriodS);
                Assert.That(a, Is.EqualTo(b), $"周期 {M7BMath.QuickFlashPeriodS}s 平移不变 @t={t}");
                Assert.That(a, Is.InRange(0f, 1f));
            }
        }

        [Test]
        public void BuoyLightIntensity_GroupFlash3_ThreePulsesPerPeriod()
        {
            int rising = 0;
            float prev = 0f;
            for (float t = 0f; t < M7BMath.GroupFlash3PeriodS; t += 0.01f)
            {
                float v = M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.GroupFlash3, t);
                Assert.That(v, Is.InRange(0f, 1f));
                if (prev <= 0f && v > 0f) rising++;
                prev = v;
            }
            Assert.That(rising, Is.EqualTo(3), "群闪 = 每周期 3 个短脉冲（方位标节奏）");
        }

        [Test]
        public void BuoyLightIntensity_LongFlash_OneWidePulsePerPeriod()
        {
            Assert.That(M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.LongFlash, 1.0f), Is.EqualTo(1f), "长闪头部 2 s 亮");
            Assert.That(M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.LongFlash, 5.0f), Is.EqualTo(0f), "长闪尾部灭");
            int rising = 0;
            float prev = 0f;
            for (float t = 0f; t < M7BMath.LongFlashPeriodS; t += 0.01f)
            {
                float v = M7BMath.BuoyLightIntensity(M7BMath.BuoyBlinkPattern.LongFlash, t);
                if (prev <= 0f && v > 0f) rising++;
                prev = v;
            }
            Assert.That(rising, Is.EqualTo(1), "长闪 = 每周期 1 个脉冲（安全水域标节奏）");
        }

        // ── ③ B2 渡轮/拖轮航线契约 + 水深门禁 ────────────────────────────────────────

        [Test]
        public void FerryWaypoints_RoundTripPalindromeAndPinnedEndpoints()
        {
            var wps = M7BMath.FerryWaypoints();
            Assert.That(wps.Length, Is.GreaterThanOrEqualTo(2 * 6 - 1), "往返 = 出程 + 回程（去重首尾）");
            for (int i = 0; i < wps.Length; i++)
                Assert.That(wps[i], Is.EqualTo(wps[wps.Length - 1 - i]), $"回程逐点逆序（回文）@i={i}");
            Assert.That(wps[wps.Length - 1], Is.EqualTo(wps[0]), "末点 = 首点（往返闭环）");

            // 北端点 = 任务钉值 1.25N 103.79E 的 Unity 原位（pyproj 钉值换算走 M7BackdropMath）
            var northPinned = M7BackdropMath.LatLonToUnity(1.25, 103.79, k_CenterUtm);
            Assert.That(M7BMath.FerryNorthTerminal.x, Is.EqualTo(northPinned.x).Within(1f), "北端点 x（1 m 换算容差）");
            Assert.That(M7BMath.FerryNorthTerminal.y, Is.EqualTo(northPinned.y).Within(1f), "北端点 z");

            // 南端点 = 1.13N 104.02E（DEM 上为 Batam 岛体 +13.5 m）沿 104.02E 经线的最近可航水域：
            // 钉经线（±0.01°）且离岸（纬度 < 1.13 的岛北约 0.07°）
            var (southLat, southLon) = M7BackdropMath.UnityToLatLon(M7BMath.FerrySouthOffshore.x, M7BMath.FerrySouthOffshore.y, k_CenterUtm);
            Assert.That(System.Math.Abs(southLon - 104.02), Is.LessThan(0.01), "南端点钉 104.02E 经线");
            Assert.That(southLat, Is.GreaterThan(1.15), "南端点在海上（岛北离岸点，非岛体 1.13N）");
        }

        [Test]
        public void FerryRoute_DepthGate_DeepFixturePassesAndSyntheticIslandBites()
        {
            M6TerrainMath.ElevationSampler deep = _ => -50f;
            var ferry = M6TerrainMath.ValidateRoute(deep, M7BMath.FerryWaypoints(), M7BMath.RouteSampleStepM, 0f);
            Assert.That(ferry.ok, Is.True, "深水 fixture：渡轮全程逐点 < 0");
            Assert.That(ferry.samples, Is.GreaterThan(500), $"往返 ~56 km @100 m 步长采样数（实得 {ferry.samples}）");

            // 合成岛摆在实际岛群（Bukom/Sudong 西缘，DEM 实证 x[3000,7000] z[-7600,-3400]）——
            // 改道后的字面航线必须仍过门（直连旧线在这里被 DEM 证伪 +6.6 m，此断言钉住改道）。
            M6TerrainMath.ElevationSampler cluster = p =>
                (p.x >= 3000f && p.x <= 7000f && p.y >= -7600f && p.y <= -3400f) ? 5f : -50f;
            var avoid = M6TerrainMath.ValidateRoute(cluster, M7BMath.FerryWaypoints(), M7BMath.RouteSampleStepM, 0f);
            Assert.That(avoid.ok, Is.True, "字面航线绕开实际岛群位置（改道回归锚）");

            // 门禁咬合：岛压到航路上（via2 附近）→ fail 并报航路上的点
            var via2 = new Vector2(12000f, -8600f);
            M6TerrainMath.ElevationSampler laneTrap = p => (p - via2).magnitude < 80f ? 3f : -50f;
            var bite = M6TerrainMath.ValidateRoute(laneTrap, M7BMath.FerryWaypoints(), M7BMath.RouteSampleStepM, 0f);
            Assert.That(bite.ok, Is.False, "航路点高程 ≥ 0 必须触发门禁");
            Assert.That((bite.worstPoint - via2).magnitude, Is.LessThan(120f), "报告定位航路上违规采样");
        }

        [Test]
        public void TugLoop_ClosedLoopInTaskRadiusWindow()
        {
            var wps = M7BMath.TugLoopWaypoints();
            Assert.That(wps.Length, Is.EqualTo(9), "正八边形 8 航点 + 首点重复闭合");
            Assert.That(wps[8], Is.EqualTo(wps[0]), "末点 = 首点（闭环）");
            Assert.That(M7BMath.TugLoopRadiusM, Is.InRange(2000f, 4000f), "任务窗：锚地周边半径 2-4 km");
            float side = 2f * M7BMath.TugLoopRadiusM * Mathf.Sin(Mathf.PI / 8f);
            for (int i = 0; i < 8; i++)
            {
                Assert.That(Vector2.Distance(wps[i], M7BMath.TugLoopCenter),
                    Is.EqualTo(M7BMath.TugLoopRadiusM).Within(0.5f), $"航点 {i} 在圆上");
                Assert.That(Vector2.Distance(wps[i], wps[i + 1]), Is.EqualTo(side).Within(1f), $"边 {i} 等长");
            }

            M6TerrainMath.ElevationSampler deep = _ => -50f;
            var pass = M6TerrainMath.ValidateRoute(deep, wps, M7BMath.RouteSampleStepM, 0f);
            Assert.That(pass.ok, Is.True, "深水 fixture：拖轮闭环逐点 < 0");

            var trap = wps[2];
            M6TerrainMath.ElevationSampler island = p => (p - trap).magnitude < 60f ? 2f : -50f;
            var fail = M6TerrainMath.ValidateRoute(island, wps, M7BMath.RouteSampleStepM, 0f);
            Assert.That(fail.ok, Is.False, "闭环点高程 ≥ 0 必须触发门禁");
        }

        // ── ④ B3 大气三档 preset 契约 + 循环状态机 ──────────────────────────────────

        [Test]
        public void AtmospherePresets_TierContract()
        {
            var hazy = M7BMath.AtmospherePresetFor(M7BMath.AtmosphereTier.HazyClear);
            var cumulo = M7BMath.AtmospherePresetFor(M7BMath.AtmosphereTier.Cumulonimbus);
            var storm = M7BMath.AtmospherePresetFor(M7BMath.AtmosphereTier.Thunderstorm);

            // 浓霾晴（默认档）：视程 ≥ 8 km（M6 雾距 8000 基础上档化）、无雨、不压暗
            Assert.That(hazy.fogDistanceM, Is.GreaterThanOrEqualTo(8000f), "浓霾晴视程 ≥ 8 km");
            Assert.That(hazy.rain, Is.False, "晴档无雨");
            Assert.That(hazy.exposureCompensationEv, Is.EqualTo(0f), "晴档无曝光补偿");
            Assert.That(hazy.sunDimFactor, Is.EqualTo(1f), "晴档不压太阳");
            Assert.That(hazy.cloudCover, Is.LessThan(0.5f), "晴档少云");

            // 积雨云：中档视程（介于雷暴与晴之间）、云量增大、变暗、无雨
            Assert.That(cumulo.fogDistanceM, Is.GreaterThan(storm.fogDistanceM), "积雨云视程 > 雷暴");
            Assert.That(cumulo.fogDistanceM, Is.LessThan(hazy.fogDistanceM), "积雨云视程 < 晴档（中档）");
            Assert.That(cumulo.cloudCover, Is.GreaterThan(hazy.cloudCover), "云量增大");
            Assert.That(cumulo.exposureCompensationEv, Is.LessThan(hazy.exposureCompensationEv), "变暗（负 EV 补偿）");
            Assert.That(cumulo.sunDimFactor, Is.LessThan(hazy.sunDimFactor), "太阳压暗");
            Assert.That(cumulo.rain, Is.False, "积雨云档无雨");

            // 雷暴雨幡：浓雾 + 最暗 + 雨
            Assert.That(storm.fogDistanceM, Is.LessThan(cumulo.fogDistanceM), "雷暴 = 三档最浓雾");
            Assert.That(storm.rain, Is.True, "雷暴开雨");
            Assert.That(storm.rainRate, Is.GreaterThan(0f), "雨发射率有效");
            Assert.That(storm.exposureCompensationEv, Is.LessThan(cumulo.exposureCompensationEv), "三档最暗");
            Assert.That(storm.cloudCover, Is.GreaterThan(cumulo.cloudCover), "云量最大");

            foreach (var p in new[] { hazy, cumulo, storm })
                Assert.That(p.transitionSeconds, Is.InRange(2f, 4f), "档间过渡 2-4 s（任务窗）");
        }

        [Test]
        public void NextAtmosphereTier_CyclesAllThree()
        {
            Assert.That(M7BMath.NextAtmosphereTier(M7BMath.AtmosphereTier.HazyClear),
                Is.EqualTo(M7BMath.AtmosphereTier.Cumulonimbus));
            Assert.That(M7BMath.NextAtmosphereTier(M7BMath.AtmosphereTier.Cumulonimbus),
                Is.EqualTo(M7BMath.AtmosphereTier.Thunderstorm));
            Assert.That(M7BMath.NextAtmosphereTier(M7BMath.AtmosphereTier.Thunderstorm),
                Is.EqualTo(M7BMath.AtmosphereTier.HazyClear), "循环回默认档（V 键热键状态机）");
        }

        // ── ⑤ B4 渔排落位契约 + 深度窗 ──────────────────────────────────────────────

        [Test]
        public void FishFarmSites_FiveGroupsSpreadInShallowBand()
        {
            Assert.That(M7BMath.FishFarmSites.Length, Is.EqualTo(M7BMath.FishFarmCount), "渔排恰 5 组");
            for (int i = 0; i < M7BMath.FishFarmSites.Length; i++)
            {
                var a = M7BMath.FishFarmSites[i];
                Assert.That(a.x, Is.GreaterThanOrEqualTo(12000f), $"组 {i} 在东部（Batam 侧）水域");
                Assert.That(a.y, Is.LessThanOrEqualTo(-10000f), $"组 {i} 在南部近岸带");
                for (int j = i + 1; j < M7BMath.FishFarmSites.Length; j++)
                    Assert.That(Vector2.Distance(a, M7BMath.FishFarmSites[j]), Is.GreaterThanOrEqualTo(300f),
                        $"组 {i}/{j} 间距 ≥ 300 m（不重叠）");
            }
            Assert.That(M7BMath.FishFarmFootprints().Length, Is.EqualTo(M7BMath.FishFarmCount * 5), "脚印 = 每组中心+四角");
        }

        [Test]
        public void FishFarmSites_ShallowBandGate_Bites()
        {
            var footprints = M7BMath.FishFarmFootprints();
            M6TerrainMath.ElevationSampler midBand = _ => -5f;
            var pass = M7BMath.ValidateShallowBand(midBand, footprints);
            Assert.That(pass.ok, Is.True, "合成 −5 m fixture：全部脚印落 2-8 m 窗");

            foreach (var e in new[] { -1f, -10f })
            {
                M6TerrainMath.ElevationSampler outOfBand = _ => e;
                var fail = M7BMath.ValidateShallowBand(outOfBand, footprints);
                Assert.That(fail.ok, Is.False, $"高程 {e} m 出窗必须 fail（渔排任务窗 2-8 m）");
            }

            // 逐点窗界咬合：仅一个角出窗也 fail 且报该角
            var trapped = footprints[3];
            M6TerrainMath.ElevationSampler mixed = p => p == trapped ? -0.5f : -5f;
            var bite = M7BMath.ValidateShallowBand(mixed, footprints);
            Assert.That(bite.ok, Is.False, "单个脚印角点出窗即 fail（fail-fast）");
            Assert.That(bite.worstPoint, Is.EqualTo(trapped), "报告定位违规角点");
        }

        // ── ⑥ 系留微摇摆 ────────────────────────────────────────────────────────────

        [Test]
        public void MooredRaftSway_BoundedDeterministicPhaseAware()
        {
            for (float t = 0f; t <= 20f; t += 0.1f)
            {
                foreach (float phase in new[] { 0f, 1.3f, 2.7f })
                {
                    var (roll, pitch, heave) = M7BMath.MooredRaftSway(t, phase);
                    Assert.That(Mathf.Abs(roll), Is.LessThanOrEqualTo(M7BMath.FarmSwayRollDeg + 1e-4f), $"roll 界 @t={t}");
                    Assert.That(Mathf.Abs(pitch), Is.LessThanOrEqualTo(M7BMath.FarmSwayPitchDeg + 1e-4f), $"pitch 界 @t={t}");
                    Assert.That(Mathf.Abs(heave), Is.LessThanOrEqualTo(M7BMath.FarmSwayHeaveM + 1e-5f), $"heave 界 @t={t}");
                }
            }
            var a = M7BMath.MooredRaftSway(3.7f, 0.9f);
            var b = M7BMath.MooredRaftSway(3.7f, 0.9f);
            Assert.That(a.rollDeg, Is.EqualTo(b.rollDeg), "确定性：同 (t, phase) 逐位同输出");
            Assert.That(a.heaveM, Is.EqualTo(b.heaveM), "确定性：同 (t, phase) 逐位同输出");

            float maxRoll = 0f, maxRollOther = 0f;
            for (float t = 0f; t < M7BMath.FarmSwayRollPeriodS; t += 0.05f)
            {
                maxRoll = Mathf.Max(maxRoll, Mathf.Abs(M7BMath.MooredRaftSway(t, 0f).rollDeg));
                maxRollOther = Mathf.Max(maxRollOther, Mathf.Abs(M7BMath.MooredRaftSway(t, 2.1f).rollDeg));
            }
            Assert.That(maxRoll, Is.GreaterThan(M7BMath.FarmSwayRollDeg * 0.9f), "摆幅到达量级（非常量）");
            Assert.That(maxRollOther, Is.GreaterThan(M7BMath.FarmSwayRollDeg * 0.9f), "任意相位均达量级（组间错相不灭摆）");
        }
    }
}
