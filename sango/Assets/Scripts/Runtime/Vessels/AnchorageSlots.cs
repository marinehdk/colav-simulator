using UnityEngine;

namespace Sango
{
    /// <summary>一个锚泊槽位：船型档 + 锚位 + 锚泊艏向。</summary>
    [System.Serializable]
    public struct AnchorageSlot
    {
        public VesselClass vesselClass;
        public Vector2 xz;       // 锚位（东=x, 北=z, 米）
        public float headingDeg; // 锚泊艏向（面向离岛一侧）

        public AnchorageSlot(VesselClass vesselClass, Vector2 xz, float headingDeg)
        {
            this.vesselClass = vesselClass;
            this.xz = xz;
            this.headingDeg = headingDeg;
        }
    }

    /// <summary>
    /// M5 锚地槽位表 + 清障谓词（纯数据/纯函数，Sango.Vessels 可直测；AnchorageFleet/M1SceneBootstrapper 消费）。
    /// 槽位与航线是离线验证字面量（2026-09-29，对 seed-42 岛群实测岸线盘做排斥搜索的解，
    /// 验证与裁决记录 docs/research/2026-09-29-m5-fleet-import/m5-audit.md）；EditMode 测试
    /// 用 PerlinIslandGenerator 重生成同参岛群（确定性）+ 本文件谓词复验不变量——改岛 seed/
    /// count/sizeRange 或挪槽位，测试即红。
    ///
    /// 排斥约束（裕量口径）：
    /// - 槽位 vs 岛：中心距 ≥ 岸线盘半径(0.8R) + 半船体对角 + 12 m；
    /// - 槽位 vs demo 航线：≥ 50 m；槽位 vs 静态泊位：≥ 70 m；槽位两两：半对角和 + 60 m；
    /// - demo 航线：42×12.6 m FCB 船体矩形（4 角点、5 m 采样）全程在全部岛岸线盘外（最差 6 m 裕量）。
    /// </summary>
    public static class AnchorageSlots
    {
        // demo 航线（G 键航线字面量；起点 = hero 泊位 (30,-12) 不在表内，见 M1SceneBootstrapper）
        public static readonly Vector2[] DemoRoute =
        {
            new Vector2(52f, -36f),
            new Vector2(72f, -64f),
            new Vector2(30f, -78f),
            new Vector2(-6f, -50f),
        };

        // 静态泊位（hero FCB / 渔船配角 / Kenney Medium），槽位排斥圈用
        public static readonly Vector2[] StaticBerths =
        {
            new Vector2(30f, -12f),
            new Vector2(-16f, -28f),
            new Vector2(30f, 90f),
        };

        // 槽位表（按占用成本升序：小船在前，密度滑条从便宜档开始填充）。
        public static readonly AnchorageSlot[] Defaults =
        {
            new AnchorageSlot(VesselClass.Tug,             new Vector2(144f, -140f), 210f),
            new AnchorageSlot(VesselClass.FishingTrawler,  new Vector2(60f,  -176f), 210f),
            new AnchorageSlot(VesselClass.FcbPc3,          new Vector2(144f, -248f), 210f),
            new AnchorageSlot(VesselClass.CargoGeneral,    new Vector2(264f, -68f),  210f),
            new AnchorageSlot(VesselClass.CargoContainer,  new Vector2(312f, -260f), 200f),
            new AnchorageSlot(VesselClass.TankerLng,       new Vector2(420f,  200f), 200f), // 东远水：与杂货槽 310 m ≥ 半对角和+60（首版 (380,64) 175 m 违规，AnchorageSlotsTests 拦下）
            new AnchorageSlot(VesselClass.Tanker,          new Vector2(160f,  600f), 200f),
        };

        // 船体尺寸表（米；LOA 与编目归一化一致，梁为实船量级估值——清障保守口径用）
        public static float LoaOf(VesselClass vesselClass) => vesselClass switch
        {
            VesselClass.Tanker => 300f,
            VesselClass.TankerLng => 300f,
            VesselClass.CargoContainer => 150f,
            VesselClass.CargoGeneral => 120f,
            VesselClass.Tug => 32f,
            VesselClass.FishingTrawler => 25f,
            VesselClass.FcbHoubei => 42f,
            VesselClass.FcbPc3 => 55f,
            _ => 100f, // Kenney Large/Medium/Small 兜底（不入锚地槽位表）
        };

        public static float BeamOf(VesselClass vesselClass) => vesselClass switch
        {
            VesselClass.Tanker => 49f,
            VesselClass.TankerLng => 49f,
            VesselClass.CargoContainer => 25f,
            VesselClass.CargoGeneral => 20f,
            VesselClass.Tug => 11f,
            VesselClass.FishingTrawler => 8f,
            VesselClass.FcbHoubei => 12.6f,
            VesselClass.FcbPc3 => 11f,
            _ => 20f,
        };

        /// <summary>船体矩形 4 角点（Unity 艏向约定：heading 0 = +Z，forward=(sin h, cos h)，right=(cos h, −sin h)）。</summary>
        public static Vector2[] HullCorners(Vector2 center, float headingDeg, float loa, float beam)
        {
            float h = headingDeg * Mathf.Deg2Rad;
            float s = Mathf.Sin(h), c = Mathf.Cos(h);
            float hl = loa * 0.5f, hb = beam * 0.5f;
            return new[]
            {
                new Vector2(center.x + s * hl + c * hb, center.y + c * hl - s * hb),
                new Vector2(center.x + s * hl - c * hb, center.y + c * hl + s * hb),
                new Vector2(center.x - s * hl + c * hb, center.y - c * hl - s * hb),
                new Vector2(center.x - s * hl - c * hb, center.y - c * hl + s * hb),
            };
        }

        /// <summary>点（x,z）对全部岛岸线盘的最小裕量（米；负 = 在盘内）。</summary>
        public static float ShoreMargin(Vector2 point, Vector2[] islandCenters, float[] islandShoreRadii)
        {
            float worst = float.MaxValue;
            for (int i = 0; i < islandCenters.Length; i++)
            {
                worst = Mathf.Min(worst, Vector2.Distance(point, islandCenters[i]) - islandShoreRadii[i]);
            }
            return worst;
        }

        /// <summary>航段（含船体转角矩形、逐米采样）全程对全部岛岸线盘的最小裕量（米）。</summary>
        public static float RouteShoreMargin(Vector2 from, Vector2 to, float loa, float beam, Vector2[] islandCenters, float[] islandShoreRadii)
        {
            float heading = Mathf.Atan2(to.x - from.x, to.y - from.y) * Mathf.Rad2Deg;
            float length = Vector2.Distance(from, to);
            int steps = Mathf.Max(1, Mathf.CeilToInt(length));
            float worst = float.MaxValue;
            for (int k = 0; k <= steps; k++)
            {
                var center = Vector2.Lerp(from, to, k / (float)steps);
                foreach (var corner in HullCorners(center, heading, loa, beam))
                {
                    worst = Mathf.Min(worst, ShoreMargin(corner, islandCenters, islandShoreRadii));
                }
            }
            return worst;
        }

        /// <summary>点到折线（航线）的最小距离。</summary>
        public static float DistanceToPolyline(Vector2 point, Vector2[] polyline)
        {
            float best = float.MaxValue;
            for (int i = 0; i + 1 < polyline.Length; i++)
            {
                best = Mathf.Min(best, DistanceToSegment(point, polyline[i], polyline[i + 1]));
            }
            return best;
        }

        public static float DistanceToSegment(Vector2 point, Vector2 a, Vector2 b)
        {
            var ab = b - a;
            float l2 = ab.sqrMagnitude;
            if (l2 < 1e-6f) return Vector2.Distance(point, a);
            float t = Mathf.Clamp01(Vector2.Dot(point - a, ab) / l2);
            return Vector2.Distance(point, a + t * ab);
        }
    }
}
