using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M4-B 海况相机摇晃引擎适配器薄壳（issue #87 批次 B 项 2）：桥楼/Chase 机位附加小幅
    /// 位姿摇晃，幅度由纯核心 SeaStateSway.SwayOffset(beaufort, time) 表驱动（B0 全零）。
    /// 叠加纪律：在 CameraRig.ApplyPose 之后执行（DefaultExecutionOrder 150 > CameraRig 0
    /// / VesselBuoyancy 100），只对相机 transform 做增量叠加——ApplyPose 每帧全量重写基姿态，
    /// 本类零累积、不改 CameraRig 本体语义。横荡沿相机右向量、垂荡沿世界 up；roll/pitch 以
    /// 相机本地欧拉 Z/X 小角旋转（水平线倾角 = roll）。
    /// </summary>
    [DefaultExecutionOrder(150)]
    public class BridgeSway : MonoBehaviour
    {
        [Tooltip("海况真值源（Beaufort 滑条）；空 = 不摇晃。")]
        public WeatherController weather;

        [Tooltip("相机 rig（读 CurrentView 决定哪些机位受摇晃）；空 = 视作 Bridge。")]
        public CameraRig rig;

        [Tooltip("桥楼固定机位受摇晃（无船体运动反馈的机位 = 摇晃主要受益者）。")]
        public bool swayBridgeView = true;
        [Tooltip("Chase 追随机位受摇晃。")]
        public bool swayChaseView = true;
        [Tooltip("艏视角不受摇晃（机位由船位姿解算，浮力姿态已带起伏，再叠加会双份）。")]
        public bool swayBowView = false;
        [Tooltip("俯视战术档不受摇晃（UI/战术判读稳定性优先）。")]
        public bool swayTopDownView = false;

        Camera m_Cam;

        void LateUpdate()
        {
            ApplySwayAt(Time.time);
        }

        /// <summary>
        /// 在给定时刻叠加一帧摇晃（公开 = EditMode 可测缝，先例 BoatWaterDecals.ApplySpeed）。
        /// B0（或 weather 缺失/机位未启用）恒零偏移 = 相机位姿逐位不变。
        /// </summary>
        public void ApplySwayAt(float timeSeconds)
        {
            if (weather == null) return;
            if (m_Cam == null) m_Cam = GetComponent<Camera>();
            if (m_Cam == null) return;

            var view = rig != null ? rig.CurrentView : CameraView.Bridge;
            bool on = view == CameraView.Bridge ? swayBridgeView
                   : view == CameraView.Chase ? swayChaseView
                   : view == CameraView.Bow ? swayBowView
                   : swayTopDownView;
            if (!on) return;

            var sway = SeaStateSway.SwayOffset(weather.beaufort, timeSeconds);
            var t = m_Cam.transform;
            t.position += t.right * sway.PosOffsetM.x + Vector3.up * sway.PosOffsetM.y;
            t.rotation = t.rotation * Quaternion.Euler(sway.PitchDeg, 0f, sway.RollDeg);
        }
    }
}
