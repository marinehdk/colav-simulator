using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M5 编目驱动的水面 decal 尺寸表（water-decal-spike-notes §7.1 正式化项 1）：
    /// 按 LOA 查表定艏波/尾迹 regionSize 与艏波幅度——替代 spike 期写死的 12×12 / 14×28 / 0.4 m
    /// （那组值是 12 m 小船量级）。纯函数无引擎写，EditMode 直测（WaterDecalSpeedGate 先例）。
    ///
    /// 约束（推导自 M4 提交值 + WaterDecal 区域预算）：
    /// - decal 区域（WaterSurface.decalRegionSize，锚在演示船）必须罩住两块 decal 的世界包围：
    ///   艏波中心 z = +loa/2 − 0.4·bow.y、尾迹中心 z = −0.4·wake.y，各 ±size/2 —— 本表让
    ///   region = clamp(loa·2.4, 64, 160)，尾迹 y 再按 0.9·y ≤ region/2 收口（V 尖顶 0.1 偏置）。
    /// - 12 m 档逐位复现 spike 提交值（bow 12×12 / wake 14×28 / amp 0.4 / region 64），M4 验收不回退。
    /// - 幅度随 √LOA 增长（同航速下长船 Froude 低、起波弱，但几何尺度大），钳 [0.4, 0.8] m。
    /// </summary>
    public static class WaterDecalSizing
    {
        /// <summary>一个船的完整 decal 尺寸参数（米）。</summary>
        public struct Sizing
        {
            public Vector2 decalRegionSize; // WaterSurface.decalRegionSize（区域锚演示船）
            public Vector2 bowRegionSize;   // 艏波 V 形区域
            public Vector2 wakeRegionSize;  // 尾迹泡沫区域
            public float bowAmplitudeM;     // 全强艏波抬升（适配器再按航速/Froude 缩放）
        }

        public static Sizing ForLoa(float loaMeters)
        {
            float loa = Mathf.Max(loaMeters, 1f);
            float region = Mathf.Clamp(loa * 2.4f, 64f, 160f);
            float bowSide = Mathf.Clamp(loa * 1.0f, 12f, 64f);
            float wakeX = Mathf.Clamp(loa * 7f / 6f, 14f, 56f);
            float wakeY = Mathf.Clamp(loa * 7f / 3f, 28f, region / 1.8f); // 0.9·y ≤ region/2 收口
            float amp = Mathf.Clamp(0.4f * Mathf.Sqrt(loa / 12f), 0.4f, 0.8f);
            return new Sizing
            {
                decalRegionSize = new Vector2(region, region),
                bowRegionSize = new Vector2(bowSide, bowSide),
                wakeRegionSize = new Vector2(wakeX, wakeY),
                bowAmplitudeM = amp,
            };
        }
    }
}
