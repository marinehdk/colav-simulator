using UnityEngine;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// 主桅顶 X 波段雷达天线挂点（00-REPORT §3 A案定案；P1 桅顶实体装配）。
    /// 单行平行表 — 刻意不进 <see cref="MastCameraTable.Mounts"/>：相机表是像素
    /// 标定族（observations 端点钉死的 sensor_id {2,3,4} 词汇），雷达行会破坏
    /// parity 枚举。后端镜像 = ``colav_simulator/core/mast_cameras.py`` 的
    /// RADAR_* 常量；两侧只可同改（parity 钉在 tests/test_observations_endpoint.py，
    /// 字面量双钉）。mount 词汇 mast_top_xband = sensor-model-v1 §3 冻结项，
    /// 也是后端 RadarXParams.mount_id 默认值（后端 antenna_height_m=12.0 是馈源
    /// 口径参数，与本实体挂点 12.98 各自独立，00-REPORT §3 依据③）。
    /// </summary>
    public static class RadarAntennaMount
    {
        /// <summary>挂点 id（sensor-model-v1 §3；后端 MOUNT_ID_RADAR_X_DEFAULT 同串）。</summary>
        public const string MountId = "mast_top_xband";

        /// <summary>桅顶高度（FBX 实测空气干舷工程口径 12.98 m；FBX 属性 12.9 m，两口径均已记录，以工程口径为准）。</summary>
        public const float HeightM = 12.98f;

        /// <summary>舯前 +2.1 m（桅中心线；MastCameraTable.MastForwardOffsetM 同源）。</summary>
        public const float ForwardOffsetM = 2.1f;

        /// <summary>右舷偏移 0（桅中心线）。</summary>
        public const float StarboardOffsetM = 0f;

        // ── HALO24 24 寸罩体包络（官方手册 988-12307-003：Ø610×225 mm；程序化实体尺寸据此） ──
        public const float RadomeDiameterM = 0.61f;
        public const float RadomeHeightM = 0.225f;

        /// <summary>罩体下半圆柱段高（程序化近似拆分：圆柱 + 扁球冠；冠极向高 = 总高 − 本值）。</summary>
        public const float RadomeCylinderHeightM = 0.15f;

        /// <summary>罩体上扁球冠极向高（0.225 − 0.15 = 0.075 m）。</summary>
        public static float RadomeCapHeightM => RadomeHeightM - RadomeCylinderHeightM;

        /// <summary>默认转速 24 rpm（≡ 2.5 s/圈；后端 RadarXParams.rpm 默认，HALO24 远档）。</summary>
        public const float ScanRpmDefault = 24f;

        /// <summary>挂点 ship-local 位置（ship frame: +z 艏/+x 右舷/+y 上、原点舯部水线 — MastCameraTable.LocalPosition 同约定）。</summary>
        public static Vector3 LocalPosition => new Vector3(StarboardOffsetM, HeightM, ForwardOffsetM);

        /// <summary>给定 vessel 世界位姿的挂点世界坐标（纯函数；EditMode 钉数学）。</summary>
        public static Vector3 WorldPosition(Vector3 vesselPosition, Quaternion vesselRotation)
            => vesselPosition + vesselRotation * LocalPosition;

        /// <summary>每转周期（秒）= 60/rpm；24 rpm ⇒ 2.5 s（rpm ≤ 0 = 不转）。</summary>
        public static float ScanPeriodS(float rpm) => rpm > 0f ? 60f / rpm : float.PositiveInfinity;

        /// <summary>
        /// 扫掠相位 [0,2π)：frac(simTime/周期)×2π — 与 web PPI sweepAzimuthRad
        /// （radar-ppi.js，((t/p)%1+1)%1×2π）同式同源 sim_time，负时刻正回卷。
        /// </summary>
        public static float SweepPhaseRad(float simTimeS, float rpm)
        {
            float period = ScanPeriodS(rpm);
            if (period <= 0f || float.IsInfinity(period)) return 0f;
            return Mathf.Repeat(simTimeS / period, 1f) * 2f * Mathf.PI;
        }

        /// <summary>相位 → 天线本地 yaw 角（度；Unity Euler y 正 = 自上顺时针 = 自艏向右舷，MastCameraTable 方位同惯例）。</summary>
        public static float SweepYawDeg(float simTimeS, float rpm) => SweepPhaseRad(simTimeS, rpm) * Mathf.Rad2Deg;
    }
}
