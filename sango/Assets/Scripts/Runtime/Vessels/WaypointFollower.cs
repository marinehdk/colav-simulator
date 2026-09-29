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
        [Tooltip("航点表（东=x, 北=z, 米）。运行时可整体替换（M2-E 遭遇脚本）：赋值即钳制活动索引到新表范围，防换短表越界；原地改元素不改长度。")]
        [SerializeField]
        Vector2[] m_Waypoints;

        /// <summary>
        /// 航点表（运行时可整体替换）。赋值即解析进度一致性：活动索引钳入 [0, len−1]（空表归 0）。
        /// 已到达态不被赋值清除——到达后换表再按 G 即从当前位置重跑新表（Toggle 语义）。
        /// </summary>
        public Vector2[] waypoints
        {
            get => m_Waypoints;
            set
            {
                m_Waypoints = value;
                int len = m_Waypoints?.Length ?? 0;
                if (m_Index >= len) m_Index = Mathf.Max(0, len - 1);
            }
        }

        [Tooltip("响应 G 键启停 demo（默认 false）：每个实例各持开关，M2-E 多跟随器互不串扰；仅 M1 演示船接线为 true。")]
        public bool demoHotkeysEnabled = false;

        [Tooltip("Play 进入即自动 Toggle 起跑（M7-B 渡轮/拖轮常动目标；默认 false，M1/M2E 演示仍走 G 键，行为零变化）。")]
        public bool autoStart = false;

        [Tooltip("烘焙艏向补偿（度，M2-E）：prefab 根原生艏 ≠ +Z 的档位（Medium 180）。导航艏向 psi 写回为 rotation.y = psi + 本值；初始化捕获反解 psi = euler.y − 本值。默认 0 = M1/M2-C 行为逐位不变。")]
        public float bowYawDegOffset = 0f;

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

        /// <summary>当前速度（m/s，运动学状态真值；初始化前为 0）。M2-E2 矢量箭头消费（spec #85）。</summary>
        public float SpeedMps => m_State.Speed;

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

        void Start()
        {
            if (autoStart) Toggle(); // M7-B 常动目标：Play 即起跑（G 键暂停/恢复语义不变）
        }

        void Update()
        {
            if (demoHotkeysEnabled && Input.GetKeyDown(KeyCode.G)) Toggle(); // G 空闲键位（WeatherGUI 占 0-9/T/F）；按实例门控
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

        /// <summary>
        /// M2-E1 reset 缝：清运行状态（索引/到达/初始化/速度 0）。reset 流程 = 先摆位姿、
        /// 换航点表，再调本方法；下一次 StepOnce 即从当前 transform 位姿重新初始化起跑。
        /// 与 Toggle 不同：不改变运行态语义、可从任意状态强制重置（EncounterDirector reset 用）。
        /// </summary>
        public void ResetToTransform()
        {
            m_Initialized = false;
            m_Arrived = false;
            m_DemoRunning = false;
            m_Index = 0;
            m_State = default;
        }

        /// <summary>推进一帧（引擎无关，EditMode 测试直接调用）。</summary>
        public void StepOnce(float dt)
        {
            int len = waypoints?.Length ?? 0;
            if (len == 0) return;
            if (m_Index >= len) m_Index = len - 1; // 消费点兜底钳制（防旁路 setter 的换表路径）
            if (!m_Initialized)
            {
                var pos = transform.position;
                m_State = new VesselKinematicState
                {
                    X = pos.x,
                    Z = pos.z,
                    // M2-E1：反解烘焙艏向补偿——导航艏向 psi = 根 euler.y − bowYawDegOffset
                    // （放置层组合约定 rotation.y = heading + offset；offset 0 时与旧契约逐位一致）。
                    Psi = (transform.eulerAngles.y - bowYawDegOffset) * Mathf.Deg2Rad,
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
        // M2-E1：yaw 写回组合烘焙艏向补偿（rotation.y = psi·Rad2Deg + offset），渲染艏 = 导航艏向；
        // offset 0（默认/Small/Large）时数值与旧契约逐位一致。
        void WriteTransform()
        {
            var pos = transform.position;
            pos.x = m_State.X;
            pos.z = m_State.Z;
            transform.position = pos;
            var eul = transform.eulerAngles;
            transform.rotation = Quaternion.Euler(eul.x, m_State.Psi * Mathf.Rad2Deg + bowYawDegOffset, eul.z);
        }
    }
}
