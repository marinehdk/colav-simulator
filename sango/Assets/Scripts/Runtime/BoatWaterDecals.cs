using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// M4 船波 decal 引擎适配器薄壳（spike）：每帧读航速真值 → 纯核心 WaterDecalSpeedGate →
    /// 写两块 WaterDecal（艏波变形 + 尾迹泡沫）。速度来源 WaypointFollower.SpeedMps
    /// （G 键 demo 同一真值；无跟随器时视作 0 = 禁用）。只写 enabled/amplitude/surfaceFoamDimmer
    /// 三个组件字段——regionSize/材质归场景构建器所有，适配器永不触碰。
    /// 分层先例：VesselBuoyancy（适配器）/ BuoyancyAttitudeSolver（纯核心）。
    /// </summary>
    public class BoatWaterDecals : MonoBehaviour
    {
        [Tooltip("艏波变形 decal（船艏子物体，场景构建器注入）。")]
        public WaterDecal bowDecal;

        [Tooltip("尾迹泡沫 decal（船体中后部子物体，场景构建器注入）。")]
        public WaterDecal wakeDecal;

        [Tooltip("航速真值来源（无则恒 0：decal 禁用）。")]
        public WaypointFollower follower;

        [Tooltip("启用阈值（m/s）：低于此航速（静止/锢泊）decal 禁用。")]
        public float speedThresholdMps = 0.5f;

        [Tooltip("全强航速（m/s）：尾迹泡沫/艏波幅度线性爬坡到此为 1。")]
        public float fullEffectSpeedMps = 5f;

        [Tooltip("艏波幅度基准（米，全强 Fr=0.45 以上）：12 m 小船量级 ~0.4 m。")]
        public float bowAmplitudeM = 0.4f;

        [Tooltip("船长 LOA（米）：艏波按 Froude 数 Fr=v/√(g·LOA) 爬坡的尺度分母（默认 12 = 编目 Small）。")]
        public float loaMeters = 12f;

        [Tooltip("尾迹泡沫强度乘子 ∈ [0,1]（Simulation 面板 M4 滑条实时驱动；1 = 全强）。")]
        public float wakeFoamIntensity = 1f;

        /// <summary>
        /// 以给定航速驱动两块 decal（公开 = EditMode 可测缝，先例 WaypointFollower.StepOnce）：
        /// enabled = 门限谓词；艏波幅度走 Froude 曲线（长船起波晚，WaterDecalSpeedGate.BowAmplitude），
        /// 泡沫 dimmer = 线性爬坡 × 面板强度乘子——低速弱尾迹、全速全强。
        /// </summary>
        public void ApplySpeed(float speedMps)
        {
            bool enabled = WaterDecalSpeedGate.ShouldEnableDecals(speedMps, speedThresholdMps);
            float ramp = WaterDecalSpeedGate.WakeFoamIntensity(speedMps, speedThresholdMps, fullEffectSpeedMps);
            if (bowDecal != null)
            {
                bowDecal.enabled = enabled;
                bowDecal.amplitude = WaterDecalSpeedGate.BowAmplitude(speedMps, speedThresholdMps, loaMeters, bowAmplitudeM);
            }
            if (wakeDecal != null)
            {
                wakeDecal.enabled = enabled;
                wakeDecal.surfaceFoamDimmer = ramp * wakeFoamIntensity;
            }
        }

        void Update()
        {
            ApplySpeed(follower != null ? follower.SpeedMps : 0f);
        }
    }
}
