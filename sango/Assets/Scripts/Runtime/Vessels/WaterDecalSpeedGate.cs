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
    }
}
