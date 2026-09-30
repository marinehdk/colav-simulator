using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M9-1 尾迹/艏波泡沫纯核心：High 档（M8QualityTier）粒子+ribbon 主视觉的强度曲线、
    /// 几何尺寸与档位谓词。纯静态、确定性（同输入逐位同输出）、无引擎写操作——每帧驱动
    /// （粒子发射率/材质 alpha/mesh 顶点）是 WakeFoamRig 适配器的职责（分层先例：
    /// WaterDecalSpeedGate / BoatWaterDecals，语义必须复用：速度门与 Froude 爬坡一律
    /// 委托 WaterDecalSpeedGate，本类只做组合，不另立曲线）。
    /// 强度语义（评审压分承接：艏部白线静态贴花 → 速度+Froude 双爬坡）：
    ///   - ribbon/水线泡沫 = 速度线性爬坡（SpeedFactor，尾迹泡沫在艉后持续存在，与
    ///     WaterDecalSpeedGate.WakeFoamIntensity 同曲线）；
    ///   - 艏部浪花发射率 = 速度线性爬坡 × Froude 因子（长船同航速起波晚，
    ///     WaterDecalSpeedGate.BowAmplitude 归一化复用）。
    /// </summary>
    public static class WakeFoamCore
    {
        // ── 档位谓词（M8 双档 L 键；消费 M8Quality.CurrentTier 静态记账值）─────────────
        // High = 粒子+ribbon 主视觉（decal 被 WakeFoamRig 压制）；Low = decal 保持现状
        // （低配帧率预算），本系统整树休眠零开销。

        /// <summary>当前档是否压制两块 WaterDecal（High = 关 decal，粒子+ribbon 接管）。</summary>
        public static bool DecalsSuppressed(M8QualityTier tier) => tier == M8QualityTier.High;

        /// <summary>当前档是否激活粒子+ribbon 主视觉。</summary>
        public static bool ParticlesActive(M8QualityTier tier) => tier == M8QualityTier.High;

        // ── 强度曲线（全部 ∈ [0,1]，低于速度阈值恒 0——静止/锢泊零发射）──────────────

        /// <summary>
        /// 速度线性爬坡因子 ∈ [0,1]：[阈值, 全强] 线性、超全强钳 1（委托
        /// WaterDecalSpeedGate.WakeFoamIntensity，与 Low 档 decal 泡沫同语义）。
        /// </summary>
        public static float SpeedFactor(float speedMps, float thresholdMps, float fullSpeedMps)
            => WaterDecalSpeedGate.WakeFoamIntensity(speedMps, thresholdMps, fullSpeedMps);

        /// <summary>
        /// Froude 因子 ∈ [0,1]：Fr = v/√(g·loaM) 在 [0.20, 0.45] 线性爬坡后钳 1（委托
        /// WaterDecalSpeedGate.BowAmplitude 基准幅 1 的归一化——同一 Froude 尺度：船越长
        /// 起波越晚，100 m 船 4 m/s（Fr≈0.128）艏浪发射恰为零）。
        /// </summary>
        public static float FroudeFactor(float speedMps, float thresholdMps, float loaM)
            => WaterDecalSpeedGate.BowAmplitude(speedMps, thresholdMps, loaM, 1f);

        /// <summary>
        /// 艏浪粒子发射率（粒子/秒，单侧）：maxRate × 速度爬坡 × Froude 因子——低速弱喷、
        /// 长船低 Fr 不喷（评审"艏部白线不随浪"的粒子端修复：发射率随航态连续变化）。
        /// </summary>
        public static float SprayEmissionRate(float speedMps, float thresholdMps, float fullSpeedMps,
                                              float loaM, float maxRatePerSide)
            => maxRatePerSide * SpeedFactor(speedMps, thresholdMps, fullSpeedMps)
                                 * FroudeFactor(speedMps, thresholdMps, loaM);

        // ── 几何尺寸（LOA 驱动；返回世界米）────────────────────────────────────────
        // 锚值：12 m 小船（编目 Small）/ 42 m FCB（hero）/ 100 m（编目 Large）。

        /// <summary>ribbon 半宽 = LOA × 0.06，钳 [0.75, 8] m（全宽 2×半宽：12 m→1.5、42 m→5.0、
        /// 100 m→12 m）。尾迹张角 ~10-15° 的观感近似（近场窄带，不含远场开角扩散）。</summary>
        public static float RibbonHalfWidthM(float loaM)
            => Mathf.Clamp(loaM * 0.06f, 0.75f, 8f);

        /// <summary>水线泡沫环径向宽 = 船宽 × 0.22，钳 [0.4, 2.5] m（贴壳一圈破碎沫带）。</summary>
        public static float RingWidthM(float beamM)
            => Mathf.Clamp(beamM * 0.22f, 0.4f, 2.5f);

        /// <summary>ribbon 位置历史采样间距 = LOA × 0.08，钳 [0.8, 4] m（距离驱动：粒状波峰
        /// 锁样，与航速无关；42 m 船满带 27 段 × 3.36 ≈ 91 m 尾迹）。</summary>
        public static float HistorySpacingM(float loaM)
            => Mathf.Clamp(loaM * 0.08f, 0.8f, 4f);

        /// <summary>ribbon 位置历史样本数（拓扑常量：顶点 = 2×此数，三角形 (此数-1)×2）。
        /// 28 样本 = 56 顶点/54 三角形，一排 draw call 内的克制预算（见 WakeFoamRig 头注）。</summary>
        public const int RibbonSampleCount = 28;
    }
}
