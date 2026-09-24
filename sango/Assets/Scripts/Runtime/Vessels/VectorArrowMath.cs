using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-E2 桥楼矢量箭头端点数学（纯函数，spec #85 Testing Decisions）。
    /// 坐标约定与 WaypointKinematics 同源：东 = +x，北 = +z，艏向角自北顺时针，
    /// 艏向单位向量 = (sin h, 0, cos h)。
    /// 速度箭头：长度 ∝ 速度，比例因子 VelocityMetersPerMps = 2 m/(m/s)（documented scale factor）；
    /// 速度 ≈ 0 时保底 stub 长 VelocityStubLengthM = 1.5 m（running-but-stationary 时箭头仍可读——
    /// idle 行为：demo 未跑时整树隐藏（VectorArrows 组件职责），跑动中零速显示 stub）。
    /// 航点箭头：定长 WaypointArrowLengthM = 10 m 指向活动航点方位；恰在航点上（零距退化）时
    /// 回退艏向。
    /// </summary>
    public static class VectorArrowMath
    {
        public const float VelocityMetersPerMps = 2f;
        public const float VelocityStubLengthM = 1.5f;
        public const float WaypointArrowLengthM = 10f;

        /// <summary>速度箭头长度（米）：max(stub, 速度 × 比例因子)。</summary>
        public static float VelocityArrowLengthM(float speedMps)
        {
            return Mathf.Max(VelocityStubLengthM, speedMps * VelocityMetersPerMps);
        }

        /// <summary>速度箭头端点：origin + 艏向单位向量 × 长度（y 保持 origin.y）。</summary>
        public static Vector3 VelocityArrowTip(Vector3 origin, float headingDeg, float speedMps)
        {
            float rad = headingDeg * Mathf.Deg2Rad;
            var fwd = new Vector3(Mathf.Sin(rad), 0f, Mathf.Cos(rad));
            return origin + fwd * VelocityArrowLengthM(speedMps);
        }

        /// <summary>
        /// 航点箭头端点：origin + unit(航点 − origin) × 定长（y 保持）；origin 恰在航点上时
        /// unit 退化 → 回退 fallbackHeadingDeg 艏向（定长不变——它是航向指针，不是速度标量）。
        /// </summary>
        public static Vector3 WaypointArrowTip(Vector3 origin, Vector2 activeWaypointXz, float fallbackHeadingDeg)
        {
            var to = new Vector2(activeWaypointXz.x - origin.x, activeWaypointXz.y - origin.z);
            if (to.sqrMagnitude < 1e-8f)
            {
                float rad = fallbackHeadingDeg * Mathf.Deg2Rad;
                return origin + new Vector3(Mathf.Sin(rad), 0f, Mathf.Cos(rad)) * WaypointArrowLengthM;
            }
            return origin + new Vector3(to.x / to.magnitude, 0f, to.y / to.magnitude) * WaypointArrowLengthM;
        }
    }
}
