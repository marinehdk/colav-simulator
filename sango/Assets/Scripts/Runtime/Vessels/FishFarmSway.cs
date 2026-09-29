using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M7-B 渔排系留微摇摆（B4）薄壳：每帧读纯函数 M7BMath.MooredRaftSway（确定性正弦、
    /// 组间错相）写 roll/pitch/heave 小幅叠加。只写姿态欧拉 Z/X 与 y——x/z/yaw 永不触碰
    /// （渔排系留不动位）。分层先例：SeaStateSway 纯核心 + BridgeSway 薄壳。
    /// </summary>
    public class FishFarmSway : MonoBehaviour
    {
        [Tooltip("组间错相（度；Update 内 ×Deg2Rad 转弧度——M7 review 修正：原 Tooltip 误标弧度，字段名/语义/构建期注入均为度）。")]
        public float phaseDeg = 0f;

        Vector3 m_BasePosition;
        Quaternion m_BaseRotation;
        bool m_Captured;

        void OnEnable() => m_Captured = false; // 域重载/重摆后重捕基位姿

        void Update()
        {
            if (!m_Captured)
            {
                m_BasePosition = transform.position;
                m_BaseRotation = transform.rotation;
                m_Captured = true;
            }
            var (rollDeg, pitchDeg, heaveM) = M7BMath.MooredRaftSway(Time.time, phaseDeg * Mathf.Deg2Rad);
            transform.rotation = m_BaseRotation * Quaternion.Euler(pitchDeg, 0f, rollDeg);
            transform.position = m_BasePosition + Vector3.up * heaveM;
        }
    }
}
