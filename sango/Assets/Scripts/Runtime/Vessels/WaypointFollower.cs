using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-C 航点跟随引擎适配器（spec #82）薄壳：每帧读位姿 → 纯核心 WaypointKinematics.Step → 写回。
    /// 只写 position.x/z 与 rotation.y——y/roll/pitch 永不触碰（M2-B 浮力合成契约的另一面）。
    /// 航点表运行时可设（encounter 场景脚本化）；demo 由 G 键启停（ WeatherGUI 占 0-9/T/F，G 空闲）。
    /// 无 Rigidbody/PhysX，纯运动学。
    /// </summary>
    public class WaypointFollower : MonoBehaviour
    {
        [Tooltip("航点表（东=x, 北=z, 米）。运行时可整体替换；空表/空引用 = 不动。")]
        public Vector2[] waypoints;

        [Tooltip("巡航速度（m/s）。小渔船演示档：12 m 船 ~10 kn 量级。")]
        public float cruiseSpeedMps = 5f;

        [Tooltip("最大转艏角速度（度/秒）。小 craft 灵活档。")]
        public float maxYawRateDegPerSec = 20f;

        [Tooltip("到达半径（米）：中间航点进入即推进；终点进入即减速停船。")]
        public float arrivalRadiusM = 8f;

        [Tooltip("加/减速度上限（m/s²，对称）。")]
        public float maxAccelMps2 = 2f;

        bool m_Initialized;   // 惰性首帧：从 transform 捕获初始位姿（速度 0）
        bool m_DemoRunning;   // G 键暂停/恢复（硬暂停：不步进，浮力照常）
        bool m_Arrived;       // 终点到达：彻底停步，位姿冻结
        int m_Index;          // 当前活动航点
        VesselKinematicState m_State;

        /// <summary>当前活动航点索引（到达半径内推进后 +1）。</summary>
        public int ActiveWaypointIndex => m_Index;

        /// <summary>终点已到达（位姿冻结；再次 Toggle 从当前位置重跑全程）。</summary>
        public bool IsArrived => m_Arrived;

        /// <summary>demo 是否在跑（G 键启停）。</summary>
        public bool DemoRunning => m_DemoRunning;

        WaypointKinematicsParams Params => new WaypointKinematicsParams
        {
            CruiseSpeedMps = cruiseSpeedMps,
            MaxYawRateRadPerSec = maxYawRateDegPerSec * Mathf.Deg2Rad,
            ArrivalRadiusM = arrivalRadiusM,
            MaxAccelMps2 = maxAccelMps2,
        };

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.G)) Toggle(); // G 空闲键位（WeatherGUI 占 0-9/T/F）
            if (m_DemoRunning && !m_Arrived) StepOnce(Time.deltaTime);
        }

        /// <summary>G 键 demo 启停：未跑/已到达 → 从当前位置重跑全程；跑动中 → 硬暂停；暂停中 → 恢复。</summary>
        public void Toggle()
        {
            if (!m_Initialized || m_Arrived)
            {
                m_Index = 0;
                m_Arrived = false;
                m_Initialized = false; // 重跑：从当前 transform 位姿、速度 0 重新起跑
                m_DemoRunning = true;
            }
            else
            {
                m_DemoRunning = !m_DemoRunning;
            }
        }

        /// <summary>推进一帧（引擎无关，EditMode 测试直接调用）。</summary>
        public void StepOnce(float dt)
        {
            if (waypoints == null || waypoints.Length == 0) return;
            if (!m_Initialized)
            {
                var pos = transform.position;
                m_State = new VesselKinematicState
                {
                    X = pos.x,
                    Z = pos.z,
                    Psi = transform.eulerAngles.y * Mathf.Deg2Rad, // 钉死约定：rotation.y = +psi·Rad2Deg
                    Speed = 0f,
                };
                m_Initialized = true;
            }
            if (m_Arrived) return;

            // 到达半径内推进航点（可连跳多个近点）；终点除外（终点到达 = 停船）。
            while (m_Index < waypoints.Length - 1 &&
                   WaypointKinematics.WithinArrival(m_State, waypoints[m_Index], arrivalRadiusM))
            {
                m_Index++;
            }

            bool final = m_Index == waypoints.Length - 1;
            if (!(final && WaypointKinematics.WithinArrival(m_State, waypoints[m_Index], arrivalRadiusM)))
            {
                m_State = WaypointKinematics.Step(m_State, waypoints[m_Index], final, Params, dt);
                if (final && WaypointKinematics.WithinArrival(m_State, waypoints[m_Index], arrivalRadiusM))
                {
                    m_State.Speed = 0f;
                    m_Arrived = true;
                }
            }
            else
            {
                m_State.Speed = 0f;
                m_Arrived = true;
            }
            WriteTransform();
        }

        // 合成契约：只写 x/z/yaw；y/roll/pitch 是 VesselBuoyancy 的独占写（M2-B）。
        void WriteTransform()
        {
            var pos = transform.position;
            pos.x = m_State.X;
            pos.z = m_State.Z;
            transform.position = pos;
            var eul = transform.eulerAngles;
            transform.rotation = Quaternion.Euler(eul.x, m_State.Psi * Mathf.Rad2Deg, eul.z);
        }
    }
}
