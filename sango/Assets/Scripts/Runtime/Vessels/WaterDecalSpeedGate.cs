using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M4 水面 decal 速度门限纯核心（spike）：静态/锢泊（航速低于阈值）时艏波+尾迹 decal 禁用，
    /// 起航后启用；尾迹泡沫强度随航速线性爬坡到全强。纯静态、确定性（同输入逐位同输出）、
    /// 无引擎写操作——WaterDecal.enabled / surfaceFoamDimmer 的每帧驱动是 BoatWaterDecals
    /// 适配器的职责（分层先例：WaypointKinematics / NavigationLightsCore）。
    /// </summary>
    public static class WaterDecalSpeedGate
    {
        /// <summary>decal 是否启用：航速 ≥ 阈值（含等号——恰在阈值上不算"低于阈值"）。</summary>
        public static bool ShouldEnableDecals(float speedMps, float thresholdMps)
        {
            return speedMps >= thresholdMps;
        }

        /// <summary>
        /// 尾迹泡沫强度 ∈ [0,1]：低于启用阈值恒 0；[阈值, 全强速度] 线性爬坡；超过全强钳 1。
        /// fullSpeedMps ≤ thresholdMps 时退化为阶跃（阈值以上即全强）。
        /// </summary>
        public static float WakeFoamIntensity(float speedMps, float thresholdMps, float fullSpeedMps)
        {
            if (speedMps <= thresholdMps) return 0f;
            float span = fullSpeedMps - thresholdMps;
            if (span <= 0f) return 1f;
            return Mathf.Clamp01((speedMps - thresholdMps) / span);
        }

        // Froude 艏波锚点（船舶原理通用分区，M4-A 正式化 spike §7-3 承接）：
        //   Fr < 0.20 低速区——兴波微弱，艏波抬升可视为 0；
        //   0.20–0.45 中速过渡区——艏波随 Fr 近线性增长；
        //   ≈0.45–0.50 兴波阻力峰（hump）前缘——排水量船艏波最盛，钳制全幅；
        //   Fr > 0.5 跨临界区排水量船不可达，恒钳 1。
        // 锚点与 spike 全强档对齐的核验：12 m 小船巡航 5 m/s → Fr = 5/√(9.81×12) ≈ 0.461，
        // 恰过 0.45 钳制点 → 默认参数下巡航即全幅（spike notes §3 验收观感不变）。
        public const float BowFroudeRampStart = 0.20f;
        public const float BowFroudeFull = 0.45f;
        const float k_Gravity = 9.81f;

        /// <summary>
        /// 艏波幅度（米）：低于启用阈值恒 0（静止/锢泊）；以上按 Froude 数 Fr = v/√(g·loaM)
        /// 从 BowFroudeRampStart 线性爬坡到 BowFroudeFull 后钳 baseAmpM——同一 Fr 同一归一幅度，
        /// 船越长起波越晚（100 m 船 5 m/s 时 Fr≈0.16 仍近零艏波）。
        /// loaM ≤ 0 防御退化：Froude 分母非法，阈值以上阶跃全幅（WakeFoamIntensity 退化先例）。
        /// </summary>
        public static float BowAmplitude(float speedMps, float thresholdMps, float loaM, float baseAmpM)
        {
            if (speedMps <= thresholdMps) return 0f;
            if (loaM <= 0f) return baseAmpM;
            float froude = speedMps / Mathf.Sqrt(k_Gravity * loaM);
            float t = (froude - BowFroudeRampStart) / (BowFroudeFull - BowFroudeRampStart);
            return baseAmpM * Mathf.Clamp01(t);
        }
    }
}
