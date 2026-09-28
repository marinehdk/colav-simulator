using UnityEngine;

namespace Sango
{
    /// <summary>摇晃姿态输出：PosOffsetM.X=横荡（右舷+，映射相机右向量）、Y=垂荡（上+）、
    /// Z 保留恒 0；RollDeg/PitchDeg = Unity 本地欧拉 Z/X 小角叠加量。</summary>
    public struct SwayPose
    {
        public Vector3 PosOffsetM;
        public float RollDeg;
        public float PitchDeg;
    }

    /// <summary>
    /// M4-B 海况相机摇晃纯核心（issue #87 批次 B 项 2）：Beaufort 0-9 表驱动的小幅位姿
    /// 摇晃（B0 全零；B6 明显可感；B9 上限仍可辨识 UI）。确定性：正弦基 + 固定相位，
    /// 禁随机——同 (beaufort, time) 逐位同输出。每帧驱动相机是 BridgeSway 适配器的职责
    /// （分层先例：CameraViews 纯解析 / CameraRig 薄壳）。
    /// </summary>
    public static class SeaStateSway
    {
        // ── 周期锚点 ─────────────────────────────────────────────────────────────
        /// <summary>横摇周期（秒）：真实桥楼/驾驶室横摇周期 8-12 s 量级（任务锚点），取中带 10 s。</summary>
        public const float RollPeriodSeconds = 10f;
        /// <summary>垂荡周期（秒）：垂荡/纵摇周期短于横摇（小型船舶 5-8 s 量级），取 6 s。</summary>
        public const float HeavePeriodSeconds = 6f;
        /// <summary>纵摇周期（秒）：同垂荡量级略快，取 5 s。</summary>
        public const float PitchPeriodSeconds = 5f;

        // 固定相位（弧度）：错开三轴峰值避免同拍共振观感；字面常量，改值即改观感锚点。
        const float k_RollPhase = 0f;
        const float k_PitchPhase = 0.9f;
        const float k_HeavePhase = 2.1f;
        const float k_LateralPhase = 1.4f;

        // ── 幅值表（峰值幅度，索引 = 整数蒲福级 0..9）──────────────────────────────
        // 量级依据（自定锚点，实机可调）：
        //   B0 风平浪静 = 全零（测试钉死）；
        //   B6（强风，Hs≈3 m）桥楼横摇峰值 1.0°（峰峰 2°）+ 垂荡 0.17 m —— 固定机位上
        //     明显可感的地平线起伏，但不干扰取景；
        //   B9（烈风，Hs≈7 m）横摇峰值 3.0° + 垂荡 0.40 m —— 上限仍可辨识 UI：
        //     3° 地平线倾角约为成人双目视场 (≈100°) 的 3%，屏上 HUD 为屏幕空间不受相机
        //     旋转影响，水平线倾斜 3° 不足以干扰文字/雷达读数。
        //   纵摇 ≈ 横摇 1/3（真实船模纵摇惯性远大于横摇、幅值显著小）；
        //   横荡幅值 ≈ 垂荡 2/3（与横摇同周期耦合）。
        //   表逐档单调（测试钉死），整数档间线性插值。
        static readonly float[] k_RollAmpDeg  = { 0f, 0.05f, 0.12f, 0.22f, 0.40f, 0.65f, 1.00f, 1.45f, 2.10f, 3.00f };
        static readonly float[] k_PitchAmpDeg = { 0f, 0.02f, 0.05f, 0.09f, 0.15f, 0.24f, 0.36f, 0.50f, 0.70f, 0.95f };
        static readonly float[] k_HeaveAmpM   = { 0f, 0.01f, 0.03f, 0.05f, 0.08f, 0.12f, 0.17f, 0.23f, 0.30f, 0.40f };
        static readonly float[] k_LateralAmpM = { 0f, 0.01f, 0.02f, 0.03f, 0.05f, 0.08f, 0.11f, 0.15f, 0.20f, 0.26f };

        /// <summary>
        /// 摇晃位姿：beaufort 钳 [0,9]（天气滑条上限 11，B10/11 按 B9 顶格），整数档表值
        /// 间线性插值；time 秒。B0 任意时刻全零；输出只含小幅叠加量（适配器叠加在
        /// CameraRig.ApplyPose 之后，不改基姿态语义）。
        /// </summary>
        public static SwayPose SwayOffset(float beaufort, float timeS)
        {
            float b = Mathf.Clamp(beaufort, 0f, 9f);
            int i0 = Mathf.Clamp((int)b, 0, k_RollAmpDeg.Length - 1);
            int i1 = Mathf.Min(i0 + 1, k_RollAmpDeg.Length - 1);
            float f = b - i0;

            float rollAmp = Mathf.Lerp(k_RollAmpDeg[i0], k_RollAmpDeg[i1], f);
            float pitchAmp = Mathf.Lerp(k_PitchAmpDeg[i0], k_PitchAmpDeg[i1], f);
            float heaveAmp = Mathf.Lerp(k_HeaveAmpM[i0], k_HeaveAmpM[i1], f);
            float lateralAmp = Mathf.Lerp(k_LateralAmpM[i0], k_LateralAmpM[i1], f);

            return new SwayPose
            {
                PosOffsetM = new Vector3(
                    lateralAmp * Mathf.Sin(2f * Mathf.PI * timeS / RollPeriodSeconds + k_LateralPhase),
                    heaveAmp * Mathf.Sin(2f * Mathf.PI * timeS / HeavePeriodSeconds + k_HeavePhase),
                    0f),
                RollDeg = rollAmp * Mathf.Sin(2f * Mathf.PI * timeS / RollPeriodSeconds + k_RollPhase),
                PitchDeg = pitchAmp * Mathf.Sin(2f * Mathf.PI * timeS / PitchPeriodSeconds + k_PitchPhase),
            };
        }
    }
}
