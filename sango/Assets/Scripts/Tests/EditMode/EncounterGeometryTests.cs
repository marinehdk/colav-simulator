using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-E1 遭遇几何缝 EditMode 测试（spec #84 Testing Decisions）。只打纯核心
    /// EncounterGeometry / TrackClock + 真实消费路径 WaypointFollower.StepOnce，无场景/水面。
    /// 钉死的坐标约定（与 WaypointKinematicsTests 同源）：东 = +x，北 = +z，艏向度数自北顺时针。
    /// 反字面回声纪律：期望值全部来自 COLREGs 会遇形态的独立几何事实
    /// （对遇左舷对左舷、交叉让路船自右舷来、追越自艉后来）+ 编目 LOA 推出的安全裕度，
    /// 不回声实现里的 lane offset / spawn 常量。
    /// 船档分配（spec Implementation Decisions）：own = Medium liner（烘焙艏向 180°），
    /// target = Large cargo（烘焙艏向 0°）——碰撞仿真按此设 follower.bowYawDegOffset。
    /// </summary>
    public class EncounterGeometryTests
    {
        const float k_AngleTolDeg = 1f;
        // 独立真值：1.25 × Large LOA（编目 100 m）＝全航程最小会遇间距下限。
        const float k_SafeSeparationM = 125f;
        // 生成间距下限：开场即"远距汇入"的演示观感（场域长 900 m 的 1/3 量级）。
        const float k_MinSpawnSeparationM = 300f;
        const float k_SimStepSeconds = 0.1f;
        const int k_SimStepCap = 8000; // 800 s：最长航线（crossing target ≈225 s）的 3 倍余量

        static readonly EncounterArea k_Area = EncounterGeometry.DefaultArea;

        static readonly (EncounterType type, string name)[] k_AllTypes =
        {
            (EncounterType.HeadOn, "head-on"),
            (EncounterType.Crossing, "crossing"),
            (EncounterType.Overtaking, "overtaking"),
        };

        // ── 对遇：艏向互逆 + 最近会遇点 target 在 own 左舷（port-to-port）──────────────
        [Test]
        public void HeadOn_HeadingsReciprocal_TargetOnOwnPortSideAtClosestApproach()
        {
            var p = EncounterGeometry.Build(EncounterType.HeadOn, k_Area);

            // worked example：own 北行走东车道、target 南行走西车道（右行规则 → 左舷对左舷）。
            Assert.That(p.Own.HeadingDeg, Is.EqualTo(0f).Within(k_AngleTolDeg), "own 北行（约定：0 = +z）");
            Assert.That(p.Target.HeadingDeg, Is.EqualTo(180f).Within(k_AngleTolDeg), "target 南行与 own 互逆");
            Assert.That(p.Own.SpawnXZ.x, Is.GreaterThan(p.Target.SpawnXZ.x), "北行船走东车道（右行规则的前置事实）");

            // 最近会遇点（两条直线航段的最近点对）：target 必须落在 own 左舷侧。
            ClosestPoints(
                p.Own.SpawnXZ, p.Own.Waypoints[p.Own.Waypoints.Length - 1],
                p.Target.SpawnXZ, p.Target.Waypoints[p.Target.Waypoints.Length - 1],
                out var ownCp, out var targetCp);
            var delta = targetCp - ownCp;
            var starboard = StarboardDir(p.Own.HeadingDeg);
            float lateral = Vector2.Dot(starboard, delta);
            Assert.That(lateral, Is.LessThan(-50f),
                $"最近会遇点 target 须在 own 左舷（右舷分量 {lateral:F1} m 必须 < 0 = port-to-port 通过）");
            Assert.That(delta.magnitude, Is.GreaterThanOrEqualTo(k_SafeSeparationM),
                "最近会遇间距不低于安全裕度");
        }

        // ── 交叉：spawn 时 target 在 own 右舷舷角（rule-15 让路船自右舷来）──────────────
        [Test]
        public void Crossing_TargetBearsOnOwnStarboardHandAtSpawn()
        {
            var p = EncounterGeometry.Build(EncounterType.Crossing, k_Area);

            float bearing = BearingDeg(p.Own.SpawnXZ, p.Target.SpawnXZ);
            float rel = Wrap180(bearing - p.Own.HeadingDeg);
            Assert.That(rel, Is.GreaterThan(5f).And.LessThan(85f),
                $"target 方位 {rel:F1}°（相对 own 艏向）必须在右舷正横前后（0–90°舷角 = starboard hand）");

            // 交叉舷角：两艏向接近正交（60–120°），读得出"横越"而非追越/对遇。
            float aspect = Mathf.Abs(Mathf.DeltaAngle(p.Own.HeadingDeg, p.Target.HeadingDeg));
            Assert.That(aspect, Is.GreaterThan(60f).And.LessThan(120f), "交叉态势两艏向接近正交");
        }

        // ── 追越：同向总轨迹、own 自 target 艉后追上、own 更快 ─────────────────────────
        [Test]
        public void Overtaking_OwnAsternFasterOnSameGeneralTrack()
        {
            var p = EncounterGeometry.Build(EncounterType.Overtaking, k_Area);

            Assert.That(p.Own.CruiseSpeedMps, Is.GreaterThan(p.Target.CruiseSpeedMps), "追越船 own 更快");

            // target 在 own 前方（艏向 ±45° 内）；own 在 target 艉后（>135°，rule-13 的 22.5° 艉角限度内）。
            float targetBearing = Wrap180(BearingDeg(p.Own.SpawnXZ, p.Target.SpawnXZ) - p.Own.HeadingDeg);
            Assert.That(targetBearing, Is.GreaterThan(-45f).And.LessThan(45f), "target 在 own 正前扇区（own 自后方接近）");
            float ownBearingFromTarget = Wrap180(BearingDeg(p.Target.SpawnXZ, p.Own.SpawnXZ) - p.Target.HeadingDeg);
            Assert.That(Mathf.Abs(ownBearingFromTarget), Is.GreaterThan(135f), "own 在 target 艉后扇区（自艉后追越）");

            // 同一总轨迹：两艏向同向（±45° 内）。
            float headingDiff = Mathf.Abs(Mathf.DeltaAngle(p.Own.HeadingDeg, p.Target.HeadingDeg));
            Assert.That(headingDiff, Is.LessThan(45f), "同向总轨迹（艏向差小）");
        }

        // ── 全类型：航点表有限、有序、步距合理 ────────────────────────────────────────
        [Test]
        public void AllTypes_WaypointListsFiniteOrderedReasonablySpaced(
            [Values(EncounterType.HeadOn, EncounterType.Crossing, EncounterType.Overtaking)] EncounterType type)
        {
            var p = EncounterGeometry.Build(type, k_Area);
            foreach (var (role, roleName) in new[] { (p.Own, "own"), (p.Target, "target") })
            {
                Assert.That(role.Waypoints, Is.Not.Null, $"{type}/{roleName}: 航点表非空引用");
                Assert.That(role.Waypoints.Length, Is.InRange(1, 8), $"{type}/{roleName}: 航点数有限且精炼");
                for (int i = 0; i < role.Waypoints.Length; i++)
                {
                    Assert.That(float.IsFinite(role.Waypoints[i].x) && float.IsFinite(role.Waypoints[i].y),
                        Is.True, $"{type}/{roleName}: 航点 {i} 有限值");
                    if (i == 0) continue;
                    float spacing = Vector2.Distance(role.Waypoints[i - 1], role.Waypoints[i]);
                    Assert.That(spacing, Is.GreaterThanOrEqualTo(25f),
                        $"{type}/{roleName}: 相邻航点步距 ≥25 m（到达半径 8 m 的 3 倍，有序不抖动）");
                }
            }
        }

        // ── 全类型：spawn 间距 ≥ 安全下限 ────────────────────────────────────────────
        [Test]
        public void AllTypes_SpawnSeparationAtLeastSafeMinimum(
            [Values(EncounterType.HeadOn, EncounterType.Crossing, EncounterType.Overtaking)] EncounterType type)
        {
            var p = EncounterGeometry.Build(type, k_Area);
            float d = Vector2.Distance(p.Own.SpawnXZ, p.Target.SpawnXZ);
            Assert.That(d, Is.GreaterThanOrEqualTo(k_MinSpawnSeparationM), $"{type}: 开场间距 {d:F0} m 过近");
        }

        // ── 全类型：真实跟随器全航程仿真碰撞自由（by construction）且双双到终点 ────────
        [Test]
        public void AllTypes_KinematicsRunCollisionFree_BothShipsArrive(
            [Values(EncounterType.HeadOn, EncounterType.Crossing, EncounterType.Overtaking)] EncounterType type)
        {
            var p = EncounterGeometry.Build(type, k_Area);
            var own = MakeFollower(p.Own, bowYawDegOffset: 180f);  // Medium liner：烘焙艏向 180°
            var target = MakeFollower(p.Target, bowYawDegOffset: 0f); // Large cargo：+Z 原生艏

            float minSep = float.MaxValue;
            bool bothArrived = false;
            for (int i = 0; i < k_SimStepCap; i++)
            {
                own.StepOnce(k_SimStepSeconds);
                target.StepOnce(k_SimStepSeconds);
                minSep = Mathf.Min(minSep, Vector2.Distance(
                    new Vector2(own.transform.position.x, own.transform.position.z),
                    new Vector2(target.transform.position.x, target.transform.position.z)));
                if (own.IsArrived && target.IsArrived)
                {
                    bothArrived = true;
                    break;
                }
            }

            Assert.That(bothArrived, Is.True, $"{type}: 两船都在仿真上限内到达各自终点（几何可走完）");
            Assert.That(minSep, Is.GreaterThanOrEqualTo(k_SafeSeparationM),
                $"{type}: 全航程最小间距 {minSep:F1} m < 安全裕度 {k_SafeSeparationM} m —— 几何必须 by construction 无碰撞");
        }

        // ── 确定性（spec User Story 7：同输入可复现）────────────────────────────────
        [Test]
        public void Build_SameInput_BitwiseIdenticalPattern()
        {
            var a = EncounterGeometry.Build(EncounterType.Crossing, k_Area);
            var b = EncounterGeometry.Build(EncounterType.Crossing, k_Area);
            Assert.That(b.Own.SpawnXZ, Is.EqualTo(a.Own.SpawnXZ), "spawn 逐位相同");
            Assert.That(b.Own.HeadingDeg, Is.EqualTo(a.Own.HeadingDeg), "艏向逐位相同");
            Assert.That(b.Own.CruiseSpeedMps, Is.EqualTo(a.Own.CruiseSpeedMps), "航速逐位相同");
            Assert.That(b.Own.Waypoints, Is.EqualTo(a.Own.Waypoints), "own 航点表逐位相同");
            Assert.That(b.Target.Waypoints, Is.EqualTo(a.Target.Waypoints), "target 航点表逐位相同");
        }

        // ── 时间球节拍（spec：每 N 秒一个 marker，首个恰在 N）────────────────────────
        [TestCase(0f, 10f, ExpectedResult = 0)]
        [TestCase(9.9f, 10f, ExpectedResult = 0)]
        [TestCase(10f, 10f, ExpectedResult = 1)]
        [TestCase(19.9f, 10f, ExpectedResult = 1)]
        [TestCase(25f, 10f, ExpectedResult = 2)]
        [TestCase(100f, 10f, ExpectedResult = 10)]
        [TestCase(10f, 0f, ExpectedResult = 0)]   // 退化 interval：永不落球
        [TestCase(10f, -5f, ExpectedResult = 0)]
        public int TrackClock_BallsDue_IsPureStepFunctionOfSimTime(float simTime, float interval)
        {
            return TrackClock.BallsDue(simTime, interval);
        }

        // ── helpers ─────────────────────────────────────────────────────────────────
        static WaypointFollower MakeFollower(EncounterRole role, float bowYawDegOffset)
        {
            var go = new GameObject($"follower-{role.Label}");
            go.transform.position = new Vector3(role.SpawnXZ.x, -1f, role.SpawnXZ.y);
            // 放置层组合约定（M2-E 修复）：rotation.y = 航向 + 烘焙艏向。
            go.transform.rotation = Quaternion.Euler(0f, role.HeadingDeg + bowYawDegOffset, 0f);
            var f = go.AddComponent<WaypointFollower>();
            f.bowYawDegOffset = bowYawDegOffset;
            f.cruiseSpeedMps = role.CruiseSpeedMps;
            f.waypoints = role.Waypoints;
            return f;
        }

        /// <summary>方位角（度，自北顺时针 [0,360)）。</summary>
        static float BearingDeg(Vector2 from, Vector2 to)
        {
            float d = Mathf.Atan2(to.x - from.x, to.y - from.y) * Mathf.Rad2Deg;
            return d < 0f ? d + 360f : d;
        }

        static float Wrap180(float a)
        {
            a = Mathf.Repeat(a + 180f, 360f) - 180f;
            return a;
        }

        /// <summary>右舷单位向量：艏向 h（度）→ (cos h, −sin h)。h=0 北行 → 东(1,0)。</summary>
        static Vector2 StarboardDir(float headingDeg)
        {
            float r = headingDeg * Mathf.Deg2Rad;
            return new Vector2(Mathf.Cos(r), -Mathf.Sin(r));
        }

        /// <summary>两条线段最近点对（标准 clamped 参数法）。</summary>
        static void ClosestPoints(Vector2 a0, Vector2 a1, Vector2 b0, Vector2 b1,
            out Vector2 cpA, out Vector2 cpB)
        {
            var d1 = a1 - a0;
            var d2 = b1 - b0;
            var r = a0 - b0;
            float A = Vector2.Dot(d1, d1);
            float E = Vector2.Dot(d2, d2);
            float F = Vector2.Dot(d2, r);
            float s, t;
            if (A <= 1e-9f && E <= 1e-9f) { cpA = a0; cpB = b0; return; }
            if (A <= 1e-9f) { s = 0f; t = Mathf.Clamp01(F / E); }
            else
            {
                float C = Vector2.Dot(d1, r);
                if (E <= 1e-9f) { t = 0f; s = Mathf.Clamp01(-C / A); }
                else
                {
                    float B = Vector2.Dot(d1, d2);
                    float denom = A * E - B * B;
                    s = denom > 1e-9f ? Mathf.Clamp01((B * F - C * E) / denom) : 0f;
                    t = (B * s + F) / E;
                    if (t < 0f) { t = 0f; s = Mathf.Clamp01(-C / A); }
                    else if (t > 1f) { t = 1f; s = Mathf.Clamp01((B - C) / A); }
                }
            }
            cpA = a0 + d1 * s;
            cpB = b0 + d2 * t;
        }
    }
}
