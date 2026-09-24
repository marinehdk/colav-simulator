using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-C 航运运动学缝 EditMode 测试（spec #82 Testing Decisions）：只打纯核心
    /// WaypointKinematics + 薄适配器 WaypointFollower.StepOnce，无场景/水面/Rigidbody。
    /// 钉死的坐标约定（web GUI scene-geography 先例，永不翻转）：
    ///   东 = +x，北 = +z，艏向 psi 弧度、rotation.y = +psi·Rad2Deg
    ///   → 艏向单位向量 = (sin psi, cos psi)：psi=0 朝北(+z)，psi=+π/2 朝东(+x)，
    ///   psi 增大 = 顺时针（俯视）= Unity rotation.y 增大。
    /// 反字面回声纪律：期望值全部来自本文件钉死的约定 + 独立几何事实
    /// （如"4 m/s 走 0.5 s 位移 2 m"），不回声实现里的 atan2/Clamp 公式。
    /// </summary>
    public class WaypointKinematicsTests
    {
        const float k_ZeroTol = 1e-4f;

        static WaypointKinematicsParams P(float cruise = 5f, float yawRateRad = 0.34906585f, float radius = 8f, float accel = 2f)
        {
            return new WaypointKinematicsParams
            {
                CruiseSpeedMps = cruise,
                MaxYawRateRadPerSec = yawRateRad,   // 20°/s（默认档）
                ArrivalRadiusM = radius,
                MaxAccelMps2 = accel,
            };
        }

        // ── 坐标约定（worked examples）────────────────────────────────────────────
        [Test]
        public void Step_PsiQuarterPiEast_MovesTwoMetersEast_NotNorth()
        {
            // psi=+π/2 按约定朝东(+x)；waypoint 远在正东 → 艏向不转；cruise=4 = 当前速 → 速度不变。
            var s = new VesselKinematicState { X = 0f, Z = 0f, Psi = Mathf.PI / 2f, Speed = 4f };
            var n = WaypointKinematics.Step(s, new Vector2(1000f, 0f), false, P(cruise: 4f), 0.5f);
            Assert.That(n.X, Is.EqualTo(2f).Within(k_ZeroTol), "4 m/s × 0.5 s 沿正东 = +2 m x");
            Assert.That(n.Z, Is.EqualTo(0f).Within(k_ZeroTol), "朝东航行北向坐标必须不动（约定：北=+z）");
            Assert.That(n.Psi, Is.EqualTo(Mathf.PI / 2f).Within(k_ZeroTol), "正东目标不打舵");
        }

        [Test]
        public void Step_PsiZeroNorth_MovesNorth_NotEast()
        {
            var s = new VesselKinematicState { X = 0f, Z = 0f, Psi = 0f, Speed = 4f };
            var n = WaypointKinematics.Step(s, new Vector2(0f, 1000f), false, P(cruise: 4f), 0.5f);
            Assert.That(n.Z, Is.EqualTo(2f).Within(k_ZeroTol), "psi=0 朝北(+z)（约定）");
            Assert.That(n.X, Is.EqualTo(0f).Within(k_ZeroTol), "朝北航行东向坐标必须不动（约定：东=+x）");
        }

        [Test]
        public void Step_FacingNorth_WaypointDueEast_TurnsPositive_NoSnap()
        {
            // 朝北(psi=0)，目标正东 → 按约定必须向 psi 正向转（俯视顺时针，rotation.y 增大），
            // 且一步只走 20°/s × 0.1 s = 2°，绝不一步跳到目标方位 90°。
            var s = new VesselKinematicState { X = 0f, Z = 0f, Psi = 0f, Speed = 0f };
            var n = WaypointKinematics.Step(s, new Vector2(100f, 0f), false, P(), 0.1f);
            Assert.That(n.Psi, Is.GreaterThan(0f), "东向目标 → psi 正向（约定：+ = 朝东转）");
            Assert.That(n.Psi, Is.EqualTo(0.0349066f).Within(1e-5f), "一步恰为 20°/s × 0.1 s = 2°");
            Assert.That(n.Psi, Is.LessThan(Mathf.PI / 2f), "有界角速度：一步不许贴到目标方位（no snap）");
            // 一步最大位移：首步速度至多 accel·dt = 0.2 → 位移 ≤ 0.2 × 0.1 s（独立物理上界，不起步瞬移）。
            float disp = Vector2.Distance(new Vector2(n.X, n.Z), new Vector2(s.X, s.Z));
            Assert.That(disp, Is.LessThanOrEqualTo(0.02f + 1e-5f), "首步位移有界（≤ accel·dt²）");
        }

        [Test]
        public void Step_HeadingDiffCrossingPi_TakesShortestWay()
        {
            // psi=+170°，目标方位 −170°（=190°）：最短路径 +20°（跨越 ±180 缝），不是 −340°。
            float psi = 170f * Mathf.Deg2Rad;
            var s = new VesselKinematicState { X = 0f, Z = 0f, Psi = psi, Speed = 0f };
            var n = WaypointKinematics.Step(s, new Vector2(Mathf.Sin(-170f * Mathf.Deg2Rad), Mathf.Cos(-170f * Mathf.Deg2Rad)), false, P(), 0.1f);
            Assert.That(n.Psi, Is.EqualTo(psi + 0.0349066f).Within(1e-5f), "跨 ±180 缝取 +20° 最短弧（2°/步）");
        }

        // ── 速度剖面 ─────────────────────────────────────────────────────────────
        [Test]
        public void Step_StationaryWaypointAhead_SpeedRampsToCruise_AtBoundedRate()
        {
            var s = new VesselKinematicState { X = 0f, Z = 0f, Psi = 0f, Speed = 0f };
            var p = P(cruise: 5f, accel: 2f);
            float prev = 0f;
            var cur = s;
            for (int i = 0; i < 60; i++) // 6 s：2 m/s² 起 5 m/s 需 2.5 s，之后稳态
            {
                cur = WaypointKinematics.Step(cur, new Vector2(0f, 500f), false, p, 0.1f);
                Assert.That(cur.Speed, Is.GreaterThanOrEqualTo(prev - 1e-6f), "中途目标远，速度只增不减");
                Assert.That(cur.Speed - prev, Is.LessThanOrEqualTo(0.2f + 1e-5f), "步加速度 ≤ 2 m/s² × 0.1 s");
                prev = cur.Speed;
            }
            Assert.That(cur.Speed, Is.EqualTo(5f).Within(1e-3f), "巡航档收敛到 cruise speed");
            Assert.That(cur.Z, Is.GreaterThan(0f), "朝北目标确实前进");
        }

        [Test]
        public void Step_FinalWaypoint_DeceleratesIntoArrival_AndPoseStopsChanging()
        {
            // 已巡航 5 m/s 直冲终点 (0,40)，R=8：减速带内必须降到低速，越过到达半径即停，
            // 且停稳后位姿逐位冻结（spec：clean end state，非 lerp 图标）。
            var p = P(cruise: 5f, radius: 8f, accel: 2f);
            var cur = new VesselKinematicState { X = 0f, Z = 0f, Psi = 0f, Speed = 5f };
            bool decelerated = false;
            for (int i = 0; i < 800; i++) // 40 s 上限，足够走完 40 m + 停稳
            {
                cur = WaypointKinematics.Step(cur, new Vector2(0f, 40f), true, p, 0.05f);
                float dist = Vector2.Distance(new Vector2(cur.X, cur.Z), new Vector2(0f, 40f));
                if (dist > 8.5f && dist < 20f) decelerated |= cur.Speed < 4.5f;
                if (dist <= 8f) break; // 进入到达半径：核心继续计算也应收敛到停
            }
            Assert.That(decelerated, Is.True, "进入到达半径前必须经历明显减速（deceleration into arrival）");
            Assert.That(cur.Speed, Is.EqualTo(0f).Within(0.5f), "到达半径边缘速度已接近零（不猛停）");
            for (int i = 0; i < 200 && cur.Speed > 0f; i++) // 余速收敛
            {
                cur = WaypointKinematics.Step(cur, new Vector2(0f, 40f), true, p, 0.05f);
            }
            Assert.That(cur.Speed, Is.EqualTo(0f).Within(1e-6f), "终点到达后速度归零");
            float stopDist = Vector2.Distance(new Vector2(cur.X, cur.Z), new Vector2(0f, 40f));
            Assert.That(stopDist, Is.LessThanOrEqualTo(8f + 1e-3f), "停船点在到达半径内");

            var frozen = cur;
            for (int i = 0; i < 50; i++)
            {
                cur = WaypointKinematics.Step(cur, new Vector2(0f, 40f), true, p, 0.05f);
                Assert.That(cur.X, Is.EqualTo(frozen.X), "停稳后 x 冻结");
                Assert.That(cur.Z, Is.EqualTo(frozen.Z), "停稳后 z 冻结");
                Assert.That(cur.Psi, Is.EqualTo(frozen.Psi), "停稳后 psi 冻结（到终点保艏向，不调头）");
                Assert.That(cur.Speed, Is.EqualTo(frozen.Speed), "停稳后速度保持 0");
            }
        }

        [Test]
        public void Step_FinalWaypointAlreadyInsideRadius_HoldsHeading_Decelerates()
        {
            // 终点已在到达半径内：不打舵（艏向冻结），只减速。
            var s = new VesselKinematicState { X = 0f, Z = 4f, Psi = 0f, Speed = 3f };
            var n = WaypointKinematics.Step(s, new Vector2(0f, 8f), true, P(radius: 8f, accel: 2f), 0.1f);
            Assert.That(n.Psi, Is.EqualTo(0f), "到达半径内保艏向");
            Assert.That(n.Speed, Is.EqualTo(2.8f).Within(1e-5f), "3 m/s − 2 m/s² × 0.1 s");
        }

        // ── 到达判定 ─────────────────────────────────────────────────────────────
        [Test]
        public void WithinArrival_BoundaryIsInclusive()
        {
            var at = new VesselKinematicState { X = 3f, Z = 4f, Psi = 0f, Speed = 0f }; // 距原点 5 m
            Assert.That(WaypointKinematics.WithinArrival(at, new Vector2(0f, 0f), 5f), Is.True, "恰在半径上 = 已到达（≤）");
            Assert.That(WaypointKinematics.WithinArrival(at, new Vector2(0f, 0f), 4.9f), Is.False, "半径外不算到达");
        }

        // ── 确定性（spec User Story 6：同输入逐位同输出）────────────────────────
        [Test]
        public void Step_TurnAndSpeed_BitwiseIdenticalAcrossRuns()
        {
            var p = P(cruise: 4.5f, yawRateRad: 0.4f, radius: 7f, accel: 1.7f);
            var wp = new Vector2(30f, 55f);
            var a = new VesselKinematicState { X = 0f, Z = 0f, Psi = 0.7f, Speed = 2.5f };
            var b = a;
            for (int i = 0; i < 137; i++)
            {
                a = WaypointKinematics.Step(a, wp, false, p, 0.033f);
                b = WaypointKinematics.Step(b, wp, false, p, 0.033f);
                Assert.That(b.X, Is.EqualTo(a.X), "逐位确定（x）");
                Assert.That(b.Z, Is.EqualTo(a.Z), "逐位确定（z）");
                Assert.That(b.Psi, Is.EqualTo(a.Psi), "逐位确定（psi）");
                Assert.That(b.Speed, Is.EqualTo(a.Speed), "逐位确定（speed）");
            }
        }
    }

    /// <summary>
    /// 薄适配器缝：StepOnce 只写 position.x/z 与 rotation.y（y/roll/pitch 归浮力，M2-B 契约），
    /// 到达半径内推进航点索引，终点到达即停。EditMode 直接手动步进，无 player loop。
    /// </summary>
    public class WaypointFollowerTests
    {
        [Test]
        public void StepOnce_WritesOnlyXZAndYaw_PreservesBuoyancyFields()
        {
            var go = new GameObject("follower");
            var f = go.AddComponent<WaypointFollower>();
            go.transform.position = new Vector3(10f, -0.33f, 20f); // y = 编目水线偏移量级
            go.transform.rotation = Quaternion.Euler(2f, 0f, 1f);  // 浮力已写的 pitch/roll
            f.waypoints = new[] { new Vector2(30f, 20f) };         // 正东

            f.StepOnce(0.1f);

            Assert.That(go.transform.position.y, Is.EqualTo(-0.33f).Within(1e-6f), "y 归浮力独占，跟随器永不写");
            Assert.That(go.transform.eulerAngles.x, Is.EqualTo(2f).Within(0.01f), "pitch 归浮力");
            Assert.That(go.transform.eulerAngles.z, Is.EqualTo(1f).Within(0.01f), "roll 归浮力");
            Assert.That(go.transform.position.z, Is.GreaterThan(20f), "x/z 平面确实前进了");
            Assert.That(go.transform.eulerAngles.y, Is.GreaterThan(0f), "正东目标 → rotation.y 正向（+psi·Rad2Deg 约定）");
            Assert.That(go.transform.eulerAngles.y, Is.LessThanOrEqualTo(2.01f), "一步 20°/s × 0.1 s = 2°（no snap）");
        }

        [Test]
        public void StepOnce_InsideArrivalRadius_AdvancesToNextWaypoint()
        {
            var go = new GameObject("follower");
            var f = go.AddComponent<WaypointFollower>();
            go.transform.position = new Vector3(10f, -0.33f, 20f); // 恰在航点 0 上
            f.waypoints = new[] { new Vector2(10f, 20f), new Vector2(40f, 20f) }; // 下一航点正东

            f.StepOnce(0.1f);

            Assert.That(f.ActiveWaypointIndex, Is.EqualTo(1), "到达半径内 → 推进到下一航点");
            Assert.That(f.IsArrived, Is.False, "中间航点到达不停车");
            Assert.That(go.transform.eulerAngles.y, Is.GreaterThan(0f), "已转向新航点（东向 → 正向转）");
        }

        [Test]
        public void StepOnce_FinalWaypointInsideRadius_ArrivesAndStops()
        {
            var go = new GameObject("follower");
            var f = go.AddComponent<WaypointFollower>();
            go.transform.position = new Vector3(10f, -0.33f, 24f); // 距终点 (10,30) 6 m < R 8
            f.waypoints = new[] { new Vector2(10f, 30f) };

            f.StepOnce(0.1f);
            Assert.That(f.IsArrived, Is.True, "终点到达半径内即到达");

            var pose = go.transform.position;
            var rot = go.transform.rotation;
            f.StepOnce(0.1f);
            f.StepOnce(0.1f);
            Assert.That(go.transform.position, Is.EqualTo(pose), "到达后位姿冻结");
            Assert.That(go.transform.rotation, Is.EqualTo(rot), "到达后姿态冻结");
            Assert.That(go.transform.position.y, Is.EqualTo(-0.33f).Within(1e-6f), "y 仍归浮力");
        }

        [Test]
        public void StepOnce_ShorterWaypointListSwappedMidRoute_NoThrow_ConsistentState()
        {
            // spec #82 User Story 3：航点表运行时可整体替换。中途换入更短的表
            // （旧活动索引越界）不许抛异常，且解析到一致状态：索引钳入新表范围、
            // 不误判到达、写回仍只碰 x/z/yaw。
            var go = new GameObject("follower");
            var f = go.AddComponent<WaypointFollower>();
            go.transform.position = new Vector3(0f, -0.33f, 0f);
            f.waypoints = new[] { new Vector2(0f, 5f), new Vector2(0f, 60f), new Vector2(40f, 60f) }; // wp0 在到达半径内
            f.StepOnce(0.1f);
            Assert.That(f.ActiveWaypointIndex, Is.EqualTo(1), "前置：已推进过航点 0");

            f.waypoints = new[] { new Vector2(0f, 20f) }; // 换短表：旧索引 1 越界
            Assert.DoesNotThrow(() => f.StepOnce(0.1f), "换短表后的下一步不许越界抛异常");
            Assert.That(f.ActiveWaypointIndex, Is.EqualTo(0), "活动索引钳制到新表范围");
            Assert.That(f.IsArrived, Is.False, "距新终点 ~20 m ≫ R 8，不得误判到达");
            Assert.That(go.transform.position.y, Is.EqualTo(-0.33f).Within(1e-6f), "y 仍归浮力");
        }
    }
}
