using UnityEngine;

namespace Sango
{
    /// <summary>Twin 场景锚点：UTM 全域 east/north 大数（米）减去后的局部原点（P2-S1 spec #89）。</summary>
    public struct TwinAnchor
    {
        /// <summary>锚点东向（米，UTM 48N/33 域全域值）。</summary>
        public double EastM;

        /// <summary>锚点北向（米）。</summary>
        public double NorthM;

        /// <summary>静态字段原点（如 replay context enc.origin_*；live compact 静态字段无原点）。</summary>
        public static TwinAnchor FromOrigin(double eastM, double northM)
            => new TwinAnchor { EastM = eastM, NorthM = northM };

        /// <summary>首帧本船锚（truth[0]；live compact-v1 静态字段无原点，S0 实证走本路）。</summary>
        public static TwinAnchor FromShip(ColavTelemetry.ShipEntry ownship)
            => new TwinAnchor { EastM = ownship.east, NorthM = ownship.north };

        /// <summary>全域 east/north → 锚定局部 east/north（米；double 内做减法防大数吞小数）。</summary>
        public Vector2 ToLocal(double eastM, double northM)
            => new Vector2((float)(eastM - EastM), (float)(northM - NorthM));
    }

    /// <summary>
    /// Twin truth → Unity 场景位姿映射（P2-S1 spec #89；纯函数）。
    /// 坐标约定与 CameraViews/WaypointKinematics 同源（PHASE1-PLAN 冻结）：
    /// east → +x、north → +z；艏向 psi（rad，北偏东顺时针）→ rotation.y = +psi·Rad2Deg；
    /// 艏向单位向量 = (sin h, 0, cos h)。psi=π/2（90°，朝东）→ rotation.y=90°、艏向 = +东 ——
    /// PHASE1-PLAN 冻结的首日验收动作（S0 发现 3 顺延至本段）。
    /// </summary>
    public static class TwinPose
    {
        /// <summary>本船/目标场景位置：truth east/north 减锚点后 (east→x, 0, north→z)。</summary>
        public static Vector3 ScenePosition(ColavTelemetry.ShipEntry ship, TwinAnchor anchor)
        {
            var local = anchor.ToLocal(ship.east, ship.north);
            return new Vector3(local.x, 0f, local.y);
        }

        /// <summary>艏向角（度）：rotation.y = +psi·Rad2Deg（北偏东顺时针，Unity yaw 同手性）。</summary>
        public static float YawDegrees(float psiRad) => psiRad * Mathf.Rad2Deg;

        /// <summary>艏向单位向量：(sin h, 0, cos h)，h 自北顺时针（度）。psi=90° → (1,0,0)=+东。</summary>
        public static Vector3 HeadingVector(float yawDeg)
        {
            float rad = yawDeg * Mathf.Deg2Rad;
            return new Vector3(Mathf.Sin(rad), 0f, Mathf.Cos(rad));
        }

        /// <summary>
        /// 两接受帧间同一船的线性插值（spec #89 帧间线性插值；alpha 由调用方按渲染
        /// sim_time 计算并钳位 [0,1]——越界钳位即 "不外推"）。动态量插值：east/north/u/v/sog
        /// 线性、psi 角度插值（LerpAngle 度制防 ±π 回绕，psi 域含负值如对遇 -3π/4）；
        /// 静态量 id/mmsi/length/width/active 取 b 帧（新快照权威）。
        /// </summary>
        public static ColavTelemetry.ShipEntry LerpEntries(ColavTelemetry.ShipEntry a, ColavTelemetry.ShipEntry b, float alpha)
        {
            float t = Mathf.Clamp01(alpha);
            return new ColavTelemetry.ShipEntry
            {
                id = b.id,
                mmsi = b.mmsi,
                length = b.length,
                width = b.width,
                east = Mathf.Lerp(a.east, b.east, t),
                north = Mathf.Lerp(a.north, b.north, t),
                psi = Mathf.LerpAngle(a.psi * Mathf.Rad2Deg, b.psi * Mathf.Rad2Deg, t) * Mathf.Deg2Rad,
                u = Mathf.Lerp(a.u, b.u, t),
                v = Mathf.Lerp(a.v, b.v, t),
                r = Mathf.Lerp(a.r, b.r, t),
                sog = Mathf.Lerp(a.sog, b.sog, t),
                cog = Mathf.LerpAngle(a.cog * Mathf.Rad2Deg, b.cog * Mathf.Rad2Deg, t) * Mathf.Deg2Rad,
                active = b.active,
            };
        }

        /// <summary>
        /// 渲染插值 alpha：(renderSim − t_prev)/(t_latest − t_prev)，钳位 [0,1]（不外推）。
        /// 帧距 ≤ 0（退化）返回 1（吸附最新帧）。
        /// </summary>
        public static float InterpolationAlpha(double renderSimTime, double prevSimTime, double latestSimTime)
        {
            double gap = latestSimTime - prevSimTime;
            if (gap <= 0.0) return 1f;
            return Mathf.Clamp01((float)((renderSimTime - prevSimTime) / gap));
        }
    }
}
