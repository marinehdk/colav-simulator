using UnityEngine;

namespace Sango
{
    /// <summary>
    /// 单个船体浸没采样点：yaw-only 船体坐标系下的水平偏移与浸没深度（米）。
    /// 由引擎适配器（VesselBuoyancy）按 M0 probe 模式逐三角质心采样填充；
    /// 纯数据，求解器不接触任何引擎水面 API。
    /// </summary>
    public struct HullSample
    {
        /// <summary>右舷(+X)方向水平偏移（米，yaw-only 船体系）。</summary>
        public float StarboardOffset;

        /// <summary>艏(+Z)方向水平偏移（米，yaw-only 船体系）。</summary>
        public float ForwardOffset;

        /// <summary>当前浸没深度 = 水面高 − 点高（+ = 点在水下）。</summary>
        public float Submersion;

        /// <summary>
        /// 静水基线浸没深度（米，+ = 设计吃水下入水）。引擎无关：求解器只按"当前浸没 − 基线浸没"
        /// 取激励；基线值由适配器按挂载时设计位姿的样点世界高度推导（静水 y=0：baseline = −designWorld.y），
        /// 不直接引用编目字段。
        /// </summary>
        public float BaselineSubmersion;
    }

    /// <summary>求解参数：增益为"波浪坡角响应比例"，钳制为可行姿态上限。</summary>
    public struct BuoyancyParams
    {
        /// <summary>升沉增益（1 = 跟随局部平均水面）。</summary>
        public float HeaveGain;

        /// <summary>横摇增益（0.5 = 取波浪坡角的一半）。</summary>
        public float RollGain;

        /// <summary>纵摇增益。</summary>
        public float PitchGain;

        /// <summary>横摇钳制上限（度，对称）。</summary>
        public float MaxRollDeg;

        /// <summary>纵摇钳制上限（度，对称）。</summary>
        public float MaxPitchDeg;

        /// <summary>
        /// 横摇固有周期（秒）。二阶横摇动力学（DampUnderdamped）：45 m 船典型 8-10 s。
        /// ≤0 视为配置错误，退回临界阻尼 Damp（不卡死姿态）。
        /// </summary>
        public float RollNaturalPeriodS;

        /// <summary>
        /// 横摇阻尼比：实船典型 0.05-0.15（欠阻尼，波频激励谐摇放大 1/(2ζ) 量级）。
        /// ≥1 退回临界阻尼（无过冲）。
        /// </summary>
        public float RollDampingRatio;

        public static BuoyancyParams Default => new BuoyancyParams
        {
            HeaveGain = 1f,
            RollGain = 0.75f,
            PitchGain = 0.75f,
            MaxRollDeg = 12f,
            MaxPitchDeg = 8f,
            RollNaturalPeriodS = 9f,
            RollDampingRatio = 0.12f,
        };
    }

    /// <summary>
    /// 求解输出（M2-B 姿态目标）。钉死符号约定：
    ///   HeaveOffset：+ = 相对设计吃水向上（米）；
    ///   RollDeg：Unity 本地欧拉 Z，+ = 右舷(+X)上浮；
    ///   PitchDeg：Unity 本地欧拉 X，+ = 艏(+Z)下俯（Unity 正 X 欧拉压艏，故艏抬升输出负值）。
    /// </summary>
    public struct BuoyancyAttitude
    {
        public float HeaveOffset;
        public float RollDeg;
        public float PitchDeg;
    }

    /// <summary>临界阻尼标量弹簧状态。</summary>
    public struct DampedScalar
    {
        public float Value;
        public float Velocity;
    }

    /// <summary>
    /// M2-B 纯浮力姿态求解器（spec #81）：输入 = 逐采样浸没数据（含吃水基线），
    /// 输出 = 升沉偏移 + 横摇/纵摇角。无状态、确定性、不引用引擎水面 API——
    /// 单点真值，供回放/对齐复用。引擎查询是 VesselBuoyancy 适配器的职责。
    /// </summary>
    public static class BuoyancyAttitudeSolver
    {
        const float k_Rad2Deg = 57.29578f;

        /// <summary>
        /// 纯求解：浸没激励 → 姿态目标。每样点取浸没激励 e_i = Submersion − BaselineSubmersion
        /// （静水下 e≡0 → 全零姿态，B0 稳如磐石）。
        ///   升沉 = HeaveGain × mean(e)（整体水位抬升直接上浮，短峰经船体均值自然衰减）；
        ///   横摇/纵摇 = 对 e 的去均值场做沿 +X / +Z 的最小二乘坡度，取坡角（atan）× 增益，
        ///   后按对称上限钳制。无状态；同输入逐位同输出。
        /// </summary>
        /// <summary>全量求解：等价 <see cref="Solve(HullSample[],int,in BuoyancyParams)"/> 以 samples.Length 为 count。</summary>
        public static BuoyancyAttitude Solve(HullSample[] samples, in BuoyancyParams p)
        {
            return Solve(samples, samples?.Length ?? 0, p);
        }

        /// <summary>
        /// 计数求解：只消费 samples 前 count 个样点（尾部残留被忽略）。
        /// 供引擎适配器复用持久缓冲（热循环零分配）；count≤0 或 samples 为空返回零姿态。
        /// </summary>
        public static BuoyancyAttitude Solve(HullSample[] samples, int count, in BuoyancyParams p)
        {
            var attitude = default(BuoyancyAttitude);
            if (samples == null || count <= 0) return attitude;

            int n = Mathf.Min(count, samples.Length);
            float sum = 0f;
            for (int i = 0; i < n; i++) sum += samples[i].Submersion - samples[i].BaselineSubmersion;
            float meanExcursion = sum / n;
            attitude.HeaveOffset = p.HeaveGain * meanExcursion;

            // 去均值一阶矩/二阶矩（去均值与升沉解耦：整体水位抬升只产生 heave，不产生假坡度）。
            float xNum = 0f, zNum = 0f, xDen = 0f, zDen = 0f, maxX2 = 0f, maxZ2 = 0f;
            for (int i = 0; i < n; i++)
            {
                float e = samples[i].Submersion - samples[i].BaselineSubmersion - meanExcursion;
                float x = samples[i].StarboardOffset;
                float z = samples[i].ForwardOffset;
                xNum += x * e;
                zNum += z * e;
                xDen += x * x;
                zDen += z * z;
                if (x * x > maxX2) maxX2 = x * x;
                if (z * z > maxZ2) maxZ2 = z * z;
            }

            // 退化护栏：样点横向/纵向展开趋零（如全部共线）则坡度无定义，姿态归零。
            float xSpread = n * maxX2;
            float zSpread = n * maxZ2;
            float rollDeg = xSpread > 1e-6f ? p.RollGain * Mathf.Atan(xNum / xDen) * k_Rad2Deg : 0f;
            float pitchDeg = zSpread > 1e-6f ? p.PitchGain * Mathf.Atan(zNum / zDen) * k_Rad2Deg : 0f;

            // 水面右舷高（坡度>0）→ 右舷上浮 → RollDeg>0（钉死约定）；
            // 水面艏高（坡度>0）→ 艏上浮 → Unity 正 X 欧拉是压艏 → 输出取负（钉死约定）。
            attitude.RollDeg = Mathf.Clamp(rollDeg, -p.MaxRollDeg, p.MaxRollDeg);
            attitude.PitchDeg = Mathf.Clamp(-pitchDeg, -p.MaxPitchDeg, p.MaxPitchDeg);
            return attitude;
        }

        /// <summary>
        /// 临界阻尼标量弹簧闭式解（ω = 2πf）：长渲染帧也保持稳定，阶跃无越冲。
        /// dt≤0 原样返回；frequencyHz≤0 视为配置错误，直接吸附目标（不卡死姿态）。
        /// </summary>
        public static DampedScalar Damp(DampedScalar s, float target, float frequencyHz, float dt)
        {
            if (dt <= 0f) return s;
            if (frequencyHz <= 0f) return new DampedScalar { Value = target, Velocity = 0f };
            float omega = 2f * Mathf.PI * frequencyHz;
            float offset = s.Value - target;
            float decay = Mathf.Exp(-omega * dt);
            float motion = (s.Velocity + omega * offset) * dt;
            s.Value = target + (offset + motion) * decay;
            s.Velocity = (s.Velocity - omega * motion) * decay;
            return s;
        }

        /// <summary>
        /// 欠阻尼二阶横摇动力学（2026-10-10 dt-sea-realism 档位 2）：以 (固有周期, 阻尼比) 描述的
        /// 二阶系统精确离散化（状态转移矩阵，长渲染帧数值稳定），替代横摇的临界阻尼 Damp——
        /// 临界阻尼阶跃无越冲，给不出实船横摇的谐摇放大与相位滞后；欠阻尼（ζ≈0.05-0.15）在波频
        /// 激励附近自然过冲（放大 1/(2ζ) 量级），量级依据实船横摇阻尼比典型值。
        /// naturalPeriodS≤0 或 ζ≥1（用户配置过阻尼意图）退回临界阻尼 Damp；dt≤0 原样返回。
        /// </summary>
        public static DampedScalar DampUnderdamped(DampedScalar s, float target,
            float naturalPeriodS, float dampingRatio, float dt)
        {
            if (dt <= 0f) return s;
            if (naturalPeriodS <= 0f) return new DampedScalar { Value = target, Velocity = 0f };
            if (dampingRatio >= 1f) return Damp(s, target, 1f / naturalPeriodS, dt);
            float zeta = Mathf.Max(0.01f, dampingRatio); // ζ→0 时 ω_d→0 触发 sin(x)/x 极限，钳下限防退化
            float wn = 2f * Mathf.PI / naturalPeriodS;
            float wd = wn * Mathf.Sqrt(1f - zeta * zeta);
            float o = s.Value - target;
            float v = s.Velocity;
            float decay = Mathf.Exp(-zeta * wn * dt);
            float c = Mathf.Cos(wd * dt);
            float sn = Mathf.Sin(wd * dt) / wd;
            s.Value = target + decay * (o * c + (v + zeta * wn * o) * sn);
            s.Velocity = decay * (v * c - (wn * wn * o + zeta * wn * v) * sn);
            return s;
        }

        /// <summary>
        /// 档位 1 横摇混叠（2026-10-10 dt-sea-realism）：后端权威横摇 = 慢变包络（语义不动，传感器
        /// 证据链仍以遥测为准），视觉欠阻尼振荡按增益叠加其上，恢复"浪-姿耦合"观感——两源频段可分
        /// （后端包络慢变 vs 波频振荡 5-12 s 周期）。无后端值（本地演示/证据夹具）走纯视觉。
        /// 叠加结果按 maxRollDeg×1.35 钳制保底（观感倾覆保护，含后端值超钳场景）。
        /// 纯函数：EditMode 直测（BuoyancyRollDynamicsTests）。
        /// </summary>
        public static float BlendRoll(float? backendRollDeg, float visualRollDeg, float gain, float maxRollDeg)
        {
            float roll = backendRollDeg.HasValue ? backendRollDeg.Value + Mathf.Clamp01(gain) * visualRollDeg : visualRollDeg;
            return Mathf.Clamp(roll, -1.35f * maxRollDeg, 1.35f * maxRollDeg);
        }
    }
}
