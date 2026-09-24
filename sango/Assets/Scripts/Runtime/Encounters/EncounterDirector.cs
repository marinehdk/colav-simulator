using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-E1 遭遇导演（spec #84）：装载会遇模式 → 用运行时航点 API（WaypointFollower.waypoints
    /// + cruiseSpeedMps + ResetToTransform）驱动两船；拥有仿真时钟（累积缩放 dt，暂停/倍速只作用
    /// 于此时钟——天气/浮力照常）；运行中追加轨迹点 + 按 TrackClock 节拍落时间球。
    /// 纯编排、零运动代码：位移全部来自既有 WaypointKinematics（经 follower.StepOnce(simDt)）。
    /// 跟随器由场景构建器置 enabled=false（自身 Update 关闭），本导演是唯一驱动方。
    /// </summary>
    public class EncounterDirector : MonoBehaviour
    {
        [Tooltip("本船跟随器（Medium liner，enabled=false：由本导演按仿真步长驱动）。")]
        public WaypointFollower ownFollower;
        [Tooltip("目标船跟随器（Large cargo，enabled=false）。")]
        public WaypointFollower targetFollower;
        [Tooltip("本船根 Transform（重摆位用）。")]
        public Transform ownShip;
        [Tooltip("目标船根 Transform。")]
        public Transform targetShip;
        [Tooltip("俯视正交相机（模式切换按 ExtentM 重设视野）。")]
        public Camera topCamera;

        [Tooltip("时间球间隔（仿真秒）。")]
        public float ballIntervalSeconds = 10f;

        /// <summary>当前模式（面板选择）。</summary>
        public EncounterType Type { get; private set; }
        /// <summary>当前模式的完整几何（面板描述/调试读数用）。</summary>
        public EncounterPattern Pattern { get; private set; }
        /// <summary>仿真是否运行（false = 暂停/未开始）。</summary>
        public bool Running { get; private set; }
        /// <summary>时间倍率（1/2/4，只作用于仿真时钟）。</summary>
        public float TimeScale { get; private set; } = 1f;
        /// <summary>仿真时钟（秒，累积缩放 dt）。</summary>
        public float SimTime { get; private set; }

        EncounterView _view;
        int _ownBalls, _targetBalls;

        // 单帧仿真步上限：掉帧尖峰不许把一步推进半条船（运动学数值稳定优先，慢于此按慢放处理）。
        const float k_MaxStepSeconds = 0.1f;

        void Awake()
        {
            ApplyPattern(EncounterType.HeadOn);
        }

        /// <summary>装载/切换模式：算几何 → 摆船 → 换表 → 清轨迹/球/时钟，进暂停态。</summary>
        public void ApplyPattern(EncounterType type)
        {
            Type = type;
            Pattern = EncounterGeometry.Build(type, EncounterGeometry.DefaultArea);
            Running = false;
            SimTime = 0f;
            _ownBalls = _targetBalls = 0;
            PlaceShip(ownShip, ownFollower, Pattern.Own);
            PlaceShip(targetShip, targetFollower, Pattern.Target);
            if (topCamera != null)
            {
                var p = topCamera.transform.position;
                topCamera.transform.position = new Vector3(0f, p.y, 0f); // 场域中心 = 原点
                topCamera.orthographicSize = Pattern.ExtentM;
            }
            if (_view == null) _view = EncounterView.Create(transform);
            _view.Setup(Pattern);
            Debug.Log($"[Sango.M2E] pattern {type}: own '{Pattern.Own.Label}' spawn {Pattern.Own.SpawnXZ} " +
                      $"hdg {Pattern.Own.HeadingDeg:0}° {Pattern.Own.CruiseSpeedMps:0.#} m/s wps[{Pattern.Own.Waypoints.Length}] | " +
                      $"target '{Pattern.Target.Label}' spawn {Pattern.Target.SpawnXZ} hdg {Pattern.Target.HeadingDeg:0}° " +
                      $"{Pattern.Target.CruiseSpeedMps:0.#} m/s wps[{Pattern.Target.Waypoints.Length}] | extent {Pattern.ExtentM:0}m");
        }

        // 重摆位：x/z 按生成位姿，y 保持水线基线（浮力 OnEnable 基线不变）；
        // 根 yaw = 航向 + 烘焙艏向（放置层组合约定，渲染艏 = 航向）。
        static void PlaceShip(Transform ship, WaypointFollower f, in EncounterRole role)
        {
            var p = ship.position;
            ship.position = new Vector3(role.SpawnXZ.x, p.y, role.SpawnXZ.y);
            ship.rotation = Quaternion.Euler(0f, role.HeadingDeg + f.bowYawDegOffset, 0f);
            f.waypoints = role.Waypoints;
            f.cruiseSpeedMps = role.CruiseSpeedMps;
            f.ResetToTransform();
        }

        /// <summary>Start/Pause 按钮：暂停⇄运行；完局（任一船已到终点）后再按 = 先重摆再起跑。</summary>
        public void ToggleRun()
        {
            if (!Running && (ownFollower.IsArrived || targetFollower.IsArrived))
            {
                ApplyPattern(Type); // 完局重跑
            }
            Running = !Running;
            Debug.Log($"[Sango.M2E] {(Running ? "run" : "pause")} at sim t={SimTime:F1}s");
        }

        /// <summary>时间倍率循环 1× → 2× → 4× → 1×。</summary>
        public void CycleTimeScale()
        {
            TimeScale = TimeScale >= 4f ? 1f : TimeScale * 2f;
            Debug.Log($"[Sango.M2E] time scale ×{TimeScale:0}");
        }

        /// <summary>Reset：回到当前模式初始几何，清轨迹/球/时钟，暂停。</summary>
        public void ResetEncounter() => ApplyPattern(Type);

        void Update()
        {
            if (!Running) return;
            float simDt = Mathf.Min(Time.deltaTime, k_MaxStepSeconds) * TimeScale;
            SimTime += simDt;
            ownFollower.StepOnce(simDt);
            targetFollower.StepOnce(simDt);
            _view.AppendTrack(0, ownShip.position);
            _view.AppendTrack(1, targetShip.position);
            // 时间球对账：应落球数比已落多几颗就补几颗（首个恰在 N，随后每 N 一个）。
            int due = TrackClock.BallsDue(SimTime, ballIntervalSeconds);
            while (_ownBalls < due) { _view.DropBall(0, ownShip.position); _ownBalls++; }
            while (_targetBalls < due) { _view.DropBall(1, targetShip.position); _targetBalls++; }
        }
    }
}
