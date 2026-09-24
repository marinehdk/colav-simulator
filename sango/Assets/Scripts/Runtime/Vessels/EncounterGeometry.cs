using UnityEngine;

namespace Sango
{
    /// <summary>遭遇类型（spec #84：三选一脚本化会遇模式；COLREGs 决策逻辑属于 phase 2）。</summary>
    public enum EncounterType
    {
        /// <summary>对遇：reciprocal 艏向、右行车道、左舷对左舷通过。</summary>
        HeadOn,
        /// <summary>交叉：target 自 own 右舷驶来（rule-15 让路/直航舷角）。</summary>
        Crossing,
        /// <summary>追越：同向总轨迹、own 自 target 艉后追上。</summary>
        Overtaking,
    }

    /// <summary>遭遇场域（米）：LengthM 沿南北主轴（+z），WidthM 沿东西（+x）。</summary>
    public struct EncounterArea
    {
        public float LengthM;
        public float WidthM;
    }

    /// <summary>单船遭遇角色：生成位姿 + 航点表 + 巡航速度（驱动现有 WaypointFollower 用）。</summary>
    public struct EncounterRole
    {
        /// <summary>生成点（米，东=x，北=z）。</summary>
        public Vector2 SpawnXZ;
        /// <summary>艏向（度，0 = 北，顺时针）。放置层按 heading + 烘焙艏向组合根 yaw。</summary>
        public float HeadingDeg;
        /// <summary>巡航速度（m/s）。</summary>
        public float CruiseSpeedMps;
        /// <summary>有序航点表（米，东=x，北=z）；终点即停。</summary>
        public Vector2[] Waypoints;
        /// <summary>角色显示名（面板/标签用，如 "OWN LINER"）。</summary>
        public string Label;
    }

    /// <summary>一场遭遇的完整脚本：两船角色 + 建议相机半视野（米）。</summary>
    public struct EncounterPattern
    {
        public EncounterType Type;
        public EncounterArea Area;
        /// <summary>本船角色（Medium liner：直航船/追越船）。</summary>
        public EncounterRole Own;
        /// <summary>目标船角色（Large cargo：让路船/被追越船）。</summary>
        public EncounterRole Target;
        /// <summary>俯视相机建议正交半视野（米，覆盖全几何 + 余量）。</summary>
        public float ExtentM;
    }

    /// <summary>
    /// M2-E1 遭遇几何纯核心（spec #84 Implementation Decisions）：(type, area) → 两船生成位姿
    /// + 航点表。确定性、无引擎 API，EditMode 可测；COLREGs 形态（对遇左舷对左舷 / 交叉自右舷 /
    /// 追越自艉后）由测试 worked examples 钉死，会遇全程按真实 WaypointFollower 运动学仿真无碰撞
    /// （by construction，测试钉死 ≥125 m = 1.25× Large LOA）。
    /// own = Medium liner（cruise 5–6 m/s），target = Large cargo（cruise 3–4 m/s）。
    /// </summary>
    public static class EncounterGeometry
    {
        /// <summary>缺省场域：900 × 300 m（两船 60/100 m、对遇/交叉全程约 100–200 s 演示）。</summary>
        public static EncounterArea DefaultArea => new EncounterArea { LengthM = 900f, WidthM = 300f };

        public static EncounterPattern Build(EncounterType type, in EncounterArea area)
        {
            float halfL = area.LengthM * 0.5f;
            switch (type)
            {
                case EncounterType.HeadOn:
                {
                    // 对遇（worked example）：own 北行走东车道、target 南行走西车道（右行规则）
                    // → 最近会遇点互在对方左舷 = port-to-port，间距 = 2·lane = 200 m。
                    float lane = area.WidthM / 3f; // 100 m @300 → 会遇间距 200 m
                    return new EncounterPattern
                    {
                        Type = type,
                        Area = area,
                        Own = Role("OWN LINER", new Vector2(lane, -halfL), 0f, 5f, new[] { new Vector2(lane, halfL) }),
                        Target = Role("TARGET CARGO", new Vector2(-lane, halfL), 180f, 4f, new[] { new Vector2(-lane, -halfL) }),
                        ExtentM = halfL + 70f,
                    };
                }
                case EncounterType.Crossing:
                {
                    // 交叉（rule-15 形态）：own 北行直航（stand-on，target 在 own 右舷）；target 自东
                    // 西行横越（give-way），横越车道在 own 前方 crossZ。
                    // crossZ = 7L/18（≈350 m @900）：两直线航段最近会遇间距 ≈148 m ≥ 125 m 裕度
                    // （worked example：d²(t) 极小点 t≈141 s 处 Δ≈(−116, +93)；仿真测试钉死）。
                    float crossZ = area.LengthM * 7f / 18f;
                    return new EncounterPattern
                    {
                        Type = type,
                        Area = area,
                        Own = Role("OWN LINER", new Vector2(0f, -halfL), 0f, 5f, new[] { new Vector2(0f, halfL) }),
                        Target = Role("TARGET CARGO", new Vector2(halfL, crossZ), 270f, 4f, new[] { new Vector2(-halfL, crossZ) }),
                        ExtentM = halfL + 70f,
                    };
                }
                case EncounterType.Overtaking:
                {
                    // 追越（rule-13 形态）：双双北行同总轨迹；target 在前（慢 3 m/s），own 自艉后
                    // 6 m/s 追上，经东舷平行车道（lane = W/2 = 150 m）通过后在车道上终点减速。
                    // 并行段全时间间距 ≥ 150 m；追越会遇点 z≈0.69L（target 仍在航，动态追越；
                    // 仿真测试钉死）。不设并回腿：对仍在航的慢船并回必然收窄间距（几何上无
                    // 碰撞自由的并回时机属于 phase 2 决策逻辑）。
                    float lane = area.WidthM * 0.5f;
                    float targetStartZ = area.LengthM * 0.25f;
                    float laneEntryZ = area.LengthM / 3f;
                    float laneExitZ = area.LengthM * 7f / 9f;
                    return new EncounterPattern
                    {
                        Type = type,
                        Area = area,
                        Own = Role("OWN LINER", new Vector2(0f, -area.LengthM / 6f), 0f, 6f,
                            new[] { new Vector2(lane, laneEntryZ), new Vector2(lane, laneExitZ) }),
                        Target = Role("TARGET CARGO", new Vector2(0f, targetStartZ), 0f, 3f,
                            new[] { new Vector2(0f, laneExitZ) }),
                        ExtentM = area.LengthM * 0.8f, // 追越全程更长（720 m @900）
                    };
                }
                default:
                    return new EncounterPattern { Type = type, Area = area };
            }
        }

        static EncounterRole Role(string label, Vector2 spawn, float headingDeg, float cruise, Vector2[] waypoints)
        {
            return new EncounterRole
            {
                Label = label,
                SpawnXZ = spawn,
                HeadingDeg = headingDeg,
                CruiseSpeedMps = cruise,
                Waypoints = waypoints,
            };
        }
    }
}
