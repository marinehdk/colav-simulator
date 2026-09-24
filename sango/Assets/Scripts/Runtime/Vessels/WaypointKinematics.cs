using UnityEngine;

namespace Sango
{
    /// <summary>
    /// 航运运动学状态（spec #82 相位 2 接缝的坐标载体）。钉死约定（web GUI scene-geography 先例）：
    /// 东 = +x，北 = +z，艏向 psi 弧度、rotation.y = +psi·Rad2Deg；艏向单位向量 = (sin psi, cos psi)。
    /// 只有这四个字段——回放/对齐的位姿真值载体，不掺引擎类型。
    /// </summary>
    public struct VesselKinematicState
    {
        /// <summary>东向位置（米）。</summary>
        public float X;
        /// <summary>北向位置（米）。</summary>
        public float Z;
        /// <summary>艏向（弧度）：0 = 北(+z)，+π/2 = 东(+x)。</summary>
        public float Psi;
        /// <summary>前进速度（m/s，沿艏向）。</summary>
        public float Speed;
    }

    /// <summary>跟随参数（小 craft、几十米场景尺度默认档）。</summary>
    public struct WaypointKinematicsParams
    {
        /// <summary>巡航速度（m/s）。</summary>
        public float CruiseSpeedMps;

        /// <summary>最大转艏角速度（rad/s，对称）。</summary>
        public float MaxYawRateRadPerSec;

        /// <summary>到达半径（米）：进入即推进航点；终点进入即停。</summary>
        public float ArrivalRadiusM;

        /// <summary>加/减速度上限（m/s²，对称）。</summary>
        public float MaxAccelMps2;

        public static WaypointKinematicsParams Default => new WaypointKinematicsParams
        {
            CruiseSpeedMps = 5f,
            MaxYawRateRadPerSec = 20f * Mathf.Deg2Rad,
            ArrivalRadiusM = 8f,
            MaxAccelMps2 = 2f,
        };
    }

    /// <summary>
    /// M2-C 3-DOF 航运运动学纯核心（spec #82）：有界角速度转艏 + 有界加减速巡航 + 终点减速入位。
    /// 纯静态、确定性（同输入逐位同输出）、无引擎 API——单点真值供回放/对齐复用；
    /// 引擎读写是 WaypointFollower 适配器的职责。
    /// 坐标约定（永不翻转）：东 = +x，北 = +z，psi 弧度，艏向单位向量 = (sin psi, cos psi)，
    /// rotation.y = +psi·Rad2Deg（psi 增大 = 俯视顺时针 = Unity rotation.y 增大）。
    /// </summary>
    public static class WaypointKinematics
    {
        // 终点减速带长度（到达半径的倍数）：减速带 ≈ [R−δ, 3R]，速度目标在半径内 δ=0.5 m 处归零。
        // δ 的作用：离散步进下"目标速度恰在边界 R 处为 0"会让船在毫米外渐进 stall（步进位移 < 浮点分辨率，
        // 永不跨入 R → 到达永不触发）；零速点内移 δ 后停船点确定落在半径内（误差 ≪ δ）。
        const float k_StopInsideMarginM = 0.5f;

        // 默认档（cruise 5, R 8）下精确跟踪减速剖面所需最大减速度 = cruise²/(2·2R) ≈ 0.78 m/s²
        // < 默认 MaxAccelMps2 = 2，即默认参数下减速充分、入位残余速度≈0（推导见 evidence m2c-build-log.md）。
        const float k_DecelRangeArrivalRadii = 2f;

        /// <summary>水平距离 ≤ 到达半径（含边界）。</summary>
        public static bool WithinArrival(in VesselKinematicState s, Vector2 waypoint, float arrivalRadiusM)
        {
            float dx = waypoint.x - s.X;
            float dz = waypoint.y - s.Z;
            return dx * dx + dz * dz <= arrivalRadiusM * arrivalRadiusM;
        }

        /// <summary>角差规约到 [−π, π)（Mathf.Repeat 语义；±π 处映射到 −π），取最短转向弧（跨 ±180 缝取短边）。</summary>
        static float WrapPi(float a)
        {
            return Mathf.Repeat(a + Mathf.PI, 2f * Mathf.PI) - Mathf.PI;
        }

        /// <summary>
        /// 单步推进（dt≤0 原样返回）：
        ///   速度目标 = 巡航值；终点腿按距离剖面减速——target = cruise·clamp01((dist−(R−δ))/2R)，
        ///   零速点在到达半径内 δ=0.5 m 处（离散步进下停船点确定落在半径内，见常量注释）；
        ///   速度以 MaxAccelMps2 有界逼近目标（MoveTowards）。
        ///   转艏 = 艏向以 MaxYawRateRadPerSec 有界捕捉目标方位（方位 = atan2(Δx, Δz)，约定钉死）；
        ///   终点在到达半径内：保艏向（不调头不打舵）、目标速度 0（减速入位）。
        ///   位移沿新艏向积分：x += sin(psi)·v·dt，z += cos(psi)·v·dt。
        /// 无状态；同输入逐位同输出。
        /// </summary>
        public static VesselKinematicState Step(in VesselKinematicState s, Vector2 waypoint, bool isFinal,
            in WaypointKinematicsParams p, float dt)
        {
            if (dt <= 0f) return s;

            float dx = waypoint.x - s.X;
            float dz = waypoint.y - s.Z;
            float dist = Mathf.Sqrt(dx * dx + dz * dz);
            bool arrivedFinal = isFinal && dist <= p.ArrivalRadiusM;

            // 速度：巡航值，终点腿减速入位（零速点半径内 δ），到达半径内直接目标 0；有界加减速逼近。
            float targetSpeed = p.CruiseSpeedMps;
            if (arrivedFinal)
            {
                targetSpeed = 0f;
            }
            else if (isFinal)
            {
                targetSpeed = p.CruiseSpeedMps * Mathf.Clamp01(
                    (dist - (p.ArrivalRadiusM - k_StopInsideMarginM)) /
                    (k_DecelRangeArrivalRadii * p.ArrivalRadiusM));
            }
            var n = s;
            n.Speed = Mathf.MoveTowards(s.Speed, targetSpeed, p.MaxAccelMps2 * dt);

            // 艏向：有界角速度捕捉方位；终点到达半径内保艏向。
            if (!arrivedFinal)
            {
                float bearing = Mathf.Atan2(dx, dz); // 约定：方位自北顺时针，atan2(东分量, 北分量)
                float maxTurn = p.MaxYawRateRadPerSec * dt;
                n.Psi = s.Psi + Mathf.Clamp(WrapPi(bearing - s.Psi), -maxTurn, maxTurn);
            }

            // 位移沿新艏向（速度 0 时逐位不动 → 停稳即冻结）。
            n.X = s.X + Mathf.Sin(n.Psi) * n.Speed * dt;
            n.Z = s.Z + Mathf.Cos(n.Psi) * n.Speed * dt;
            return n;
        }
    }
}
