using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-E2 雷达几何（纯函数，spec #85 Testing Decisions）。坐标约定与 WaypointKinematics 同源：
    /// 东 = +x，北 = +z。方位角自北顺时针（北 0°、东 90°、南 180°、西 270°）。
    /// 雷达盘北向上：blip 归一化坐标 (右 = 东，上 = 北)，模长 ≤ 1 在盘内。
    /// </summary>
    public static class RadarMath
    {
        /// <summary>方位角（度，0..360，自北顺时针）：from → to。</summary>
        public static float BearingDeg(Vector2 fromXz, Vector2 toXz)
        {
            var d = toXz - fromXz;
            if (d.sqrMagnitude < 1e-12f) return 0f;
            float deg = Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg; // atan2(东, 北)：北=0、东=+90
            return Mathf.Repeat(deg, 360f);
        }

        /// <summary>平面距离（米）。</summary>
        public static float RangeM(Vector2 fromXz, Vector2 toXz)
        {
            return Vector2.Distance(fromXz, toXz);
        }

        /// <summary>目标是否在雷达量程内（边界含：恰在量程上算在内）。</summary>
        public static bool InRange(Vector2 fromXz, Vector2 toXz, float rangeM)
        {
            return (toXz - fromXz).sqrMagnitude <= rangeM * rangeM;
        }

        /// <summary>
        /// 北向上雷达盘上的归一化 blip 坐标：x = 东分量/量程（右），y = 北分量/量程（上）。
        /// 模长 ≤ 1 = 盘内；盘外 blip 由调用方隐藏（InRange 判定）。
        /// </summary>
        public static Vector2 BlipNormalized(Vector2 ownXz, Vector2 targetXz, float rangeM)
        {
            var d = targetXz - ownXz;
            return new Vector2(d.x / rangeM, d.y / rangeM);
        }
    }
}
