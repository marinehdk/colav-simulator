using System;
using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M7-B 海峡浮标/动目标/大气档/渔排纯函数集（EditMode 全覆盖；消费方
    /// Sango.Editor.M7BSceneBuilder 与运行时 BuoyBeacon/WeatherController/WeatherGUI）。
    /// 坐标约定与 M6TerrainMath/M7BackdropMath 一致：manifest center_utm = Unity 原点，
    /// +X=东、+Z=北、海面 y=0。经纬度换算直接复用 M7BackdropMath（pyproj 钉值测试在其侧）。
    /// 落位 provenance（2026-09-29，tmp/m7b/site_analysis.py + route_probe.py 对
    /// tmp/m6-data RAW 离线实采，构建期 Terrain.SampleHeight 门禁复验）：
    /// ①浮标 13 座 = 主航道带 10（M6 k_StraitRoute 深水走廊两侧 ±300-500 m：侧向标
    ///   3 红 + 3 绿 + 北/南方位标各 1）+ 锚地航道口 3（绿侧标/红侧标/安全水域标），
    ///   全部海床 < 0（实采 −55 至 −135 m——海峡 TSS 本就是深水航道，浮标链长不设上限，
    ///   "贴近水面"指浮标体浮于 y≈0，非海床深度窗）；
    /// ②渡轮线 巴淡岛北岸 ↔ 新加坡西南 往返：北端点 = 任务钉值 1.25N 103.79E 原位；
    ///   南端 = 任务钉值 1.13N 104.02E（陆地内 +13.5 m，Batam 岛体）沿 104.02E 经线向
    ///   北取最近可航水域 (1.2005N 104.0193E, −8.5 m)——端点语义 = 离岸起航点，同
    ///   M6 k_StraitRoute "起点 = 泊位不在表内" 口径；中途经停点绕 Bukom/Sudong 岛群
    ///   西缘深水走廊（直连线在 DEM 上横穿岛群西端 +6.6 m，被 100 m 逐点采样证伪后改道）；
    /// ③拖轮作业圈 = 东锚地南侧 (10800,−9200) r=2000 m 闭环（任务 2-4 km 档；
    ///   圆周最浅 −8.1 m；r=3000 档实测 −7.2 m 已贴浅滩、SW 锚地两档圆均撞岸，弃）；
    /// ④渔排 5 组 = Batam 北侧近岸浅水（1.15-1.19N 103.93-104.00E），实采中心+四角
    ///   全部落在 [−8,−2] m 深度窗（任务 2-8 m）。
    /// </summary>
    public static class M7BMath
    {
        // ── B1 IALA A 区浮标 ────────────────────────────────────────────────────────

        /// <summary>IALA A 区浮标种别（任务：红罐左舷/绿锥右舷进港 + 北/南方位标 + 安全水域标）。</summary>
        public enum IalaBuoyKind
        {
            PortHandCan,   // 侧向标·左舷（进港）：红罐（圆柱浮体+无顶标）
            StarboardCone, // 侧向标·右舷（进港）：绿锥（锥形浮体或罐+单锥顶标）
            NorthCardinal, // 方位标·北：黑黄双锥顶标（两尖朝上），标名"北"= 其北侧为可航水域
            SouthCardinal, // 方位标·南：黄黑双锥顶标（两尖朝下）
            SafeWater,     // 安全水域标：红白竖条+红球顶标
        }

        /// <summary>灯质节奏（任务：快闪/群闪区分；纯函数 BuoyLightIntensity 驱动）。</summary>
        public enum BuoyBlinkPattern
        {
            QuickFlash,   // Q：周期 1 s 单短闪（侧向标）
            GroupFlash3,  // Q(3)+LFl 语义近似：10 s 内 3 短闪（方位标）
            LongFlash,    // LFl：8 s 内 1 长闪（安全水域标）
        }

        /// <summary>浮标落位（xz = Unity 米；approach = 近锚地航道口带，与主航道带分账计数）。</summary>
        public struct BuoySite
        {
            public IalaBuoyKind kind;
            public Vector2 xz;
            public bool approach;
        }

        /// <summary>主航道 TSS 边界带浮标数（任务 6-10；本表 8 侧向 + 2 方位 = 10）。</summary>
        public const int MainChannelBuoyCount = 10;
        /// <summary>近锚地航道口浮标数（任务 2-4；本表 3）。</summary>
        public const int ApproachBuoyCount = 3;

        /// <summary>
        /// 浮标落位表（确定性字面量；provenance 见类头注。侧向标按"自东向西进港"惯例：
        /// 左舷红罐置航道南缘、右舷绿锥置北缘；主航道带 = M6 k_StraitRoute 深水走廊两侧
        /// ±300-500 m；方位标对置走廊横断面南北两端；航道口 3 座守东锚地西入口）。
        /// </summary>
        public static readonly BuoySite[] ChannelBuoys =
        {
            // 主航道带（西段 5200,-11400 → 7200,-11200；东段 7200,-11200 → 9500,-8800）
            new BuoySite { kind = IalaBuoyKind.PortHandCan,   xz = new Vector2(5730f, -11649f) },
            new BuoySite { kind = IalaBuoyKind.StarboardCone, xz = new Vector2(5670f, -11051f) },
            new BuoySite { kind = IalaBuoyKind.PortHandCan,   xz = new Vector2(6730f, -11549f) },
            new BuoySite { kind = IalaBuoyKind.StarboardCone, xz = new Vector2(6670f, -10951f) },
            new BuoySite { kind = IalaBuoyKind.PortHandCan,   xz = new Vector2(7992f, -10808f) },
            new BuoySite { kind = IalaBuoyKind.StarboardCone, xz = new Vector2(7558f, -10392f) },
            new BuoySite { kind = IalaBuoyKind.PortHandCan,   xz = new Vector2(8567f, -10208f) },
            new BuoySite { kind = IalaBuoyKind.StarboardCone, xz = new Vector2(8133f, -9792f) },
            new BuoySite { kind = IalaBuoyKind.NorthCardinal, xz = new Vector2(6170f, -11001f) },
            new BuoySite { kind = IalaBuoyKind.SouthCardinal, xz = new Vector2(6250f, -11798f) },
            // 近锚地航道口（东锚地西入口，S2 底图锚泊船群带）
            new BuoySite { kind = IalaBuoyKind.StarboardCone, xz = new Vector2(9500f, -8200f),  approach = true },
            new BuoySite { kind = IalaBuoyKind.PortHandCan,   xz = new Vector2(10200f, -8600f), approach = true },
            new BuoySite { kind = IalaBuoyKind.SafeWater,     xz = new Vector2(11000f, -9000f), approach = true },
        };

        /// <summary>种别 → 灯质（侧向快闪 / 方位群闪 / 安全水域长闪）。</summary>
        public static BuoyBlinkPattern PatternFor(IalaBuoyKind kind)
        {
            switch (kind)
            {
                case IalaBuoyKind.PortHandCan:
                case IalaBuoyKind.StarboardCone:
                    return BuoyBlinkPattern.QuickFlash;
                case IalaBuoyKind.NorthCardinal:
                case IalaBuoyKind.SouthCardinal:
                    return BuoyBlinkPattern.GroupFlash3;
                default:
                    return BuoyBlinkPattern.LongFlash;
            }
        }

        /// <summary>种别 → 灯色（IALA A：左舷红 / 右舷绿 / 方位与安全水域白）。</summary>
        public static Color LightColorFor(IalaBuoyKind kind)
        {
            switch (kind)
            {
                case IalaBuoyKind.PortHandCan: return new Color(1f, 0.12f, 0.08f);
                case IalaBuoyKind.StarboardCone: return new Color(0.15f, 1f, 0.25f);
                default: return new Color(1f, 0.98f, 0.92f);
            }
        }

        // 闪灯曲线锚点（秒）：脉冲宽度统一 0.12 s（远处小光点可读即可）
        public const float QuickFlashPeriodS = 1.0f;
        public const float GroupFlash3PeriodS = 10.0f;
        public const float GroupFlash3PulseCount = 3f;
        public const float LongFlashPeriodS = 8.0f;
        public const float LongFlashWidthS = 2.0f;
        const float k_PulseWidthS = 0.12f;

        /// <summary>
        /// 浮标灯强度 ∈ [0,1]（确定性纯函数，同 t 逐位同输出；BuoyBeacon 每帧消费）。
        /// QuickFlash：1 s 周期头部 0.12 s 亮；GroupFlash3：10 s 周期内在 0/1/2 s 处
        /// 3 个 0.12 s 短闪；LongFlash：8 s 周期内头部 2 s 长亮。
        /// </summary>
        public static float BuoyLightIntensity(BuoyBlinkPattern pattern, float timeS)
        {
            float period, phase, width;
            switch (pattern)
            {
                case BuoyBlinkPattern.QuickFlash:
                    period = QuickFlashPeriodS; phase = Mathf.Repeat(timeS, period); width = k_PulseWidthS;
                    return phase < width ? 1f : 0f;
                case BuoyBlinkPattern.GroupFlash3:
                    period = GroupFlash3PeriodS; phase = Mathf.Repeat(timeS, period); width = k_PulseWidthS;
                    for (int i = 0; i < (int)GroupFlash3PulseCount; i++)
                        if (phase >= i && phase < i + width) return 1f;
                    return 0f;
                default: // LongFlash
                    period = LongFlashPeriodS; phase = Mathf.Repeat(timeS, period);
                    return phase < LongFlashWidthS ? 1f : 0f;
            }
        }

        // ── B2 渡轮/拖轮航线 ────────────────────────────────────────────────────────

        /// <summary>航路构建期验证采样步（米；M6 k_RouteSampleStepM 同值口径）。</summary>
        public const float RouteSampleStepM = 100f;

        /// <summary>拖轮作业圈中心（东锚地南侧开阔水域；provenance 见类头注）。</summary>
        public static readonly Vector2 TugLoopCenter = new Vector2(10800f, -9200f);
        /// <summary>拖轮作业圈半径（任务 2-4 km；r=3000 档实测贴浅滩弃用）。</summary>
        public const float TugLoopRadiusM = 2000f;
        /// <summary>拖轮闭环航点数（45° 步进；末点 = 首点闭合成环）。</summary>
        public const int TugLoopWaypointCount = 8;

        /// <summary>
        /// 拖轮闭环航点：绕 TugLoopCenter 半径 TugLoopRadiusM 的正八边形，
        /// 末点重复首点（WaypointFollower loopWaypoints 循环消费：一圈闭环即回首点续跑）。
        /// </summary>
        public static Vector2[] TugLoopWaypoints()
        {
            var pts = new Vector2[TugLoopWaypointCount + 1];
            for (int k = 0; k <= TugLoopWaypointCount; k++)
            {
                float a = (k % TugLoopWaypointCount) * (360f / TugLoopWaypointCount) * Mathf.Deg2Rad;
                pts[k] = TugLoopCenter + TugLoopRadiusM * new Vector2(Mathf.Sin(a), Mathf.Cos(a));
            }
            return pts;
        }

        // 渡轮线字面量（provenance 见类头注；往返 = 出程 + 回程逆序，回文数组）
        static readonly Vector2 k_FerrySouth = new Vector2(24400f, -8800f);   // Batam 北岸离岸点 (1.2005N 104.0193E)
        static readonly Vector2 k_FerryVia1 = new Vector2(18000f, -9000f);
        static readonly Vector2 k_FerryVia2 = new Vector2(12000f, -8600f);
        static readonly Vector2 k_FerryVia3 = new Vector2(4000f, -8400f);
        static readonly Vector2 k_FerryVia4 = new Vector2(600f, -6900f);
        static readonly Vector2 k_FerryVia5 = new Vector2(-900f, -5200f);
        static readonly Vector2 k_FerryNorth = new Vector2(-1114f, -3316f);   // 1.25N 103.79E 原位

        /// <summary>
        /// 渡轮往返航点：南（巴淡北岸离岸）→ 北（新加坡西南 1.25N 103.79E）→ 南，
        /// 回程逐点逆序复用同一深水走廊；末点 = 首点（WaypointFollower loopWaypoints
        /// 循环消费：一圈往返即回首点续跑，长会话常动不冻结）。
        /// </summary>
        public static Vector2[] FerryWaypoints()
        {
            var out_ = new[]
            {
                k_FerrySouth, k_FerryVia1, k_FerryVia2, k_FerryVia3, k_FerryVia4, k_FerryVia5, k_FerryNorth,
            };
            var pts = new Vector2[out_.Length * 2 - 1];
            for (int i = 0; i < out_.Length; i++) pts[i] = out_[i];
            for (int i = 0; i < out_.Length - 1; i++) pts[out_.Length + i] = out_[out_.Length - 2 - i];
            return pts;
        }

        /// <summary>渡轮南端离岸起航点（端点语义 provenance 见类头注）。</summary>
        public static Vector2 FerrySouthOffshore => k_FerrySouth;
        /// <summary>渡轮北端点（任务钉值 1.25N 103.79E 的 Unity 原位）。</summary>
        public static Vector2 FerryNorthTerminal => k_FerryNorth;

        // ── B3 大气三档 ─────────────────────────────────────────────────────────────

        /// <summary>大气档（N 键/面板下拉循环；preset 契约见 AtmospherePresetFor）。</summary>
        public enum AtmosphereTier
        {
            HazyClear = 0,    // 浓霾晴（默认档）
            Cumulonimbus = 1, // 积雨云
            Thunderstorm = 2, // 雷暴雨幡
        }

        /// <summary>大气档参数（WeatherController 档间 lerp 的目标值；数值 provenance 见各字段注）。</summary>
        public struct AtmospherePreset
        {
            public float fogDistanceM;            // 视程（Fog.maxFogDistance/meanFreePath 目标）
            public float cloudCover;              // 云量 0-1（→ HDRP 云预设四档量化，WeatherController 现行映射）
            public float exposureCompensationEv;  // Exposure.compensation 目标（自动曝光的确定性压暗杠杆）
            public float sunDimFactor;            // 直射太阳强度乘子（天空/海面直射观感）
            public bool rain;                     // 雨粒子开关
            public float rainRate;                // 雨粒子发射率（粒子/秒；rain=false 时忽略）
            public float transitionSeconds;       // 档间平滑过渡时长（任务 2-4 s）
        }

        /// <summary>雷暴雨档雨粒子发射率（粒子/秒； RainFall.SetRate 消费）。</summary>
        public const float ThunderstormRainRate = 9000f;

        /// <summary>
        /// 档 → preset（确定性纯函数）：
        /// 浓霾晴 = M6 海峡默认雾距 8000 m（≥8 km 任务线）+ 少云 + 无补偿；
        /// 积雨云 = 中档视程 4000 m + 云量 0.80（→ Stormy 云预设档）+ −0.8 EV + 太阳 ×0.55；
        /// 雷暴雨幡 = 浓雾 1500 m + 云量 0.95 + −1.6 EV + 太阳 ×0.30 + 雨。
        /// 三档过渡时长统一 3 s（任务 2-4 s 窗中值）。
        /// </summary>
        public static AtmospherePreset AtmospherePresetFor(AtmosphereTier tier)
        {
            switch (tier)
            {
                case AtmosphereTier.Cumulonimbus:
                    return new AtmospherePreset
                    {
                        fogDistanceM = 4000f,
                        cloudCover = 0.80f,
                        exposureCompensationEv = -0.8f,
                        sunDimFactor = 0.55f,
                        rain = false,
                        rainRate = 0f,
                        transitionSeconds = 3f,
                    };
                case AtmosphereTier.Thunderstorm:
                    return new AtmospherePreset
                    {
                        fogDistanceM = 1500f,
                        cloudCover = 0.95f,
                        exposureCompensationEv = -1.6f,
                        sunDimFactor = 0.30f,
                        rain = true,
                        rainRate = ThunderstormRainRate,
                        transitionSeconds = 3f,
                    };
                default:
                    return new AtmospherePreset
                    {
                        fogDistanceM = 8000f,
                        cloudCover = 0.35f,
                        exposureCompensationEv = 0f,
                        sunDimFactor = 1f,
                        rain = false,
                        rainRate = 0f,
                        transitionSeconds = 3f,
                    };
            }
        }

        /// <summary>档位循环状态机：HazyClear → Cumulonimbus → Thunderstorm → HazyClear（N 键消费）。</summary>
        public static AtmosphereTier NextAtmosphereTier(AtmosphereTier tier)
            => (AtmosphereTier)(((int)tier + 1) % 3);

        // ── B4 渔排 ─────────────────────────────────────────────────────────────────

        /// <summary>渔排组数（任务：5 组）。</summary>
        public const int FishFarmCount = 5;
        /// <summary>渔排浅水深度窗（任务 2-8 m；海面 y=0 口径下高程 ∈ [−8,−2]）。</summary>
        public const float FishFarmMinDepthM = 2f;
        public const float FishFarmMaxDepthM = 8f;
        /// <summary>单组渔排脚印半尺寸（米；中心 ±(20,14) 盒，四角进深度窗）。</summary>
        public const float FarmHalfLengthM = 20f;
        public const float FarmHalfWidthM = 14f;

        /// <summary>渔排 5 组中心落位（Batam 北侧近岸浅水；provenance 见类头注）。
        /// x 全部 &gt; 18000：落 M6 覆盖语义下仍激活的远景 tile（far_r3c4），避开被近景带
        /// 压住的隐藏 tile（far_r3c3 一带海床不渲染——渔排会浮在"无底洞"上）。</summary>
        public static readonly Vector2[] FishFarmSites =
        {
            new Vector2(18354f, -13550f),
            new Vector2(19467f, -13274f),
            new Vector2(20580f, -12446f),
            new Vector2(21137f, -11617f),
            new Vector2(21693f, -10511f),
        };

        /// <summary>全部渔排脚印采样点（每组中心 + 四角；构建期/测试的深度窗验证输入）。</summary>
        public static Vector2[] FishFarmFootprints()
        {
            var pts = new Vector2[FishFarmSites.Length * 5];
            int i = 0;
            foreach (var s in FishFarmSites)
            {
                pts[i++] = s;
                pts[i++] = new Vector2(s.x - FarmHalfLengthM, s.y - FarmHalfWidthM);
                pts[i++] = new Vector2(s.x + FarmHalfLengthM, s.y - FarmHalfWidthM);
                pts[i++] = new Vector2(s.x - FarmHalfLengthM, s.y + FarmHalfWidthM);
                pts[i++] = new Vector2(s.x + FarmHalfLengthM, s.y + FarmHalfWidthM);
            }
            return pts;
        }

        /// <summary>
        /// 浅水深度窗验证（fail-fast，与 M6TerrainMath.ValidateDepths 同款报告语义）：
        /// 所有点高程 ∈ [−maxDepthM, −minDepthM]（渔排 2-8 m 窗）；失败时定位首个违规点。
        /// </summary>
        public struct ShallowBandReport
        {
            public bool ok;
            public float worstElevationM;   // 失败 = 首个违规点高程；成功 = 全窗最浅高程
            public Vector2 worstPoint;
            public int samples;
        }

        public static ShallowBandReport ValidateShallowBand(M6TerrainMath.ElevationSampler sample, Vector2[] points)
        {
            var report = new ShallowBandReport { ok = true, worstElevationM = float.MinValue, samples = points.Length };
            foreach (var p in points)
            {
                float e = sample(p);
                if (e > -FishFarmMinDepthM || e < -FishFarmMaxDepthM)
                {
                    report.ok = false;
                    report.worstElevationM = e;
                    report.worstPoint = p;
                    return report; // fail fast：首个违规即停
                }
                if (e > report.worstElevationM) { report.worstElevationM = e; report.worstPoint = p; }
            }
            return report;
        }

        // ── 渔排系留微摇摆（确定性纯函数；FishFarmSway 每帧消费）──────────────────

        /// <summary>摇摆幅值锚点：横摇 1.2° / 纵摇 0.8° / 垂荡 0.12 m（系留渔排小可感档）。</summary>
        public const float FarmSwayRollDeg = 1.2f;
        public const float FarmSwayPitchDeg = 0.8f;
        public const float FarmSwayHeaveM = 0.12f;
        /// <summary>摇摆周期（秒）：横摇 8 / 纵摇 6.5 / 垂荡 6（错相防同拍）。</summary>
        public const float FarmSwayRollPeriodS = 8f;
        public const float FarmSwayPitchPeriodS = 6.5f;
        public const float FarmSwayHeavePeriodS = 6f;

        /// <summary>系留渔排微摇摆位姿（确定性；phase 按组错开，同 (t, phase) 逐位同输出）。</summary>
        public static (float rollDeg, float pitchDeg, float heaveM) MooredRaftSway(float timeS, float phase)
        {
            float roll = FarmSwayRollDeg * Mathf.Sin(2f * Mathf.PI * timeS / FarmSwayRollPeriodS + phase);
            float pitch = FarmSwayPitchDeg * Mathf.Sin(2f * Mathf.PI * timeS / FarmSwayPitchPeriodS + phase + 0.9f);
            float heave = FarmSwayHeaveM * Mathf.Sin(2f * Mathf.PI * timeS / FarmSwayHeavePeriodS + phase + 2.1f);
            return (roll, pitch, heave);
        }
    }
}
