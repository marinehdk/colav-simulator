using System.Collections.Generic;
using UnityEngine;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// P3-S2 桅杆传感器机位族 (spec #90; twin-bridge-v1 sensor_mode 载体): builds
    /// the <see cref="MastCameraTable"/> mount family under a vessel root —
    /// ship-local transforms inherit the vessel attitude exactly once per frame
    /// (FCB45 挂载工艺，M9 桥楼/艏锚点同源). Only the feed mount's Camera is
    /// enabled (rendering into its target texture for the FramePublisher YOLO
    /// feed); the remaining mounts are attitude carriers (disabled cameras, no
    /// render cost) ready for per-mount publishing (IR 第二端口留后续段).
    /// EditMode-testable math lives in <see cref="MastCameraTable"/>; this class
    /// is the engine-thin shell (CameraRig 工艺).
    /// </summary>
    public class MastSensorRig : MonoBehaviour
    {
        [Tooltip("机位族宿主船根（空 = 运行期由 TwinBridgeService 接线 own-ship 槽位）")]
        public Transform vesselRoot;

        [Tooltip("馈送机位 id（FramePublisher 默认源；SangoSeamConfig 常量工艺的运行期面）")]
        public string feedMountId = MastCameraTable.FeedMountId;

        private readonly Dictionary<string, Camera> _cameras = new Dictionary<string, Camera>();
        private RenderTexture _feedTarget;

        /// <summary>Feed-mount camera (null until <see cref="Attach"/> succeeds).</summary>
        public Camera FeedCamera { get; private set; }

        /// <summary>Rig attached to a vessel root with a live feed (P3-11: also requires the
        /// parent rewrite to have actually landed — Unity silently refuses cyclic SetParent).</summary>
        public bool Attached => FeedCamera != null && vesselRoot != null && transform.parent == vesselRoot;

        /// <summary>Built mount count (diagnostics/tests).</summary>
        public int BuiltMountCount => _cameras.Count;

        /// <summary>
        /// Parents the rig under the vessel root and builds every mount of the
        /// table. Idempotent: re-attach to a new vessel rebuilds the family.
        /// P3-11 (spec #91 前置批): rejects a cyclic target — when the rig shares a
        /// GameObject with the slot factory (TwinBridgeSceneBuilder 旧烘焙), the vessel
        /// slot is a child of the rig transform and SetParent would be a cycle that
        /// Unity silently refuses (verified on 6000.3.24f1: no exception, hierarchy
        /// unchanged) — the rig then renders from the stale world pose forever. The
        /// refusal now fails loudly instead of reporting a phantom attach; re-bake the
        /// scene (rig on its own child GameObject) to fix the wiring.
        /// </summary>
        public bool Attach(Transform target)
        {
            if (target == null) return false;
            if (vesselRoot == target && FeedCamera != null) return true;
            if (target.IsChildOf(transform))
            {
                // P3-11：目标在 rig 自身子树内（rig 与槽位工厂同 GO 的旧烘焙）——SetParent
                // 是环，Unity 6000.3.24f1 静默拒绝（实证：无异常无日志、层级不变）。显式拒绝
                // 并保留现场（不 Detach——共享 GO 上 Detach 会顺带毁掉子树里的槽位船）。
                Debug.LogError($"[Sango.MastRig] attach refused: target '{target.name}' is inside the rig's own " +
                               "subtree (rig shares a GameObject with the slot factory). Rebuild the SangoTwin scene " +
                               "(TwinBridgeSceneBuilder puts the rig on a dedicated child GameObject).");
                return false;
            }
            Detach();
            vesselRoot = target;
            transform.SetParent(vesselRoot, worldPositionStays: false);
            if (transform.parent != vesselRoot)
            {
                // 防御兜底：环检查之外的任何静默拒绝（未来 Unity 行为变化）不再假报成功。
                Debug.LogError($"[Sango.MastRig] attach failed: Unity refused parenting under '{target.name}'");
                vesselRoot = null;
                return false;
            }
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
            foreach (var mount in MastCameraTable.Mounts) BuildMount(mount);
            bool feedOk = TryGetCamera(feedMountId, out var feedCamera);
            FeedCamera = feedOk ? feedCamera : null;
            return FeedCamera != null && ConfigureFeedTarget();
        }

        /// <summary>
        /// Removes the rig from the vessel and destroys the mount hierarchy + feed target.
        /// P3-11: destroys only the mount holders this rig built — never the transform's
        /// whole child set (shared-GO bakes host the twin slot ships as siblings; the old
        /// child wipe massacred them right after the first attach, forcing a slot rebuild).
        /// </summary>
        public void Detach()
        {
            FeedCamera = null;
            foreach (var camera in _cameras.Values)
                if (camera != null)
                {
                    var holder = camera.gameObject;
                    if (Application.isPlaying) Destroy(holder);
                    else DestroyImmediate(holder);
                }
            _cameras.Clear();
            if (_feedTarget != null)
            {
                _feedTarget.Release();
                if (Application.isPlaying) Destroy(_feedTarget);
                else DestroyImmediate(_feedTarget);
                _feedTarget = null;
            }
            transform.SetParent(null, worldPositionStays: false);
            vesselRoot = null;
        }

        public bool TryGetCamera(string mountId, out Camera camera) => _cameras.TryGetValue(mountId, out camera) && camera != null;

        private void BuildMount(in MastMount mount)
        {
            var holder = new GameObject(mount.MountId);
            holder.transform.SetParent(transform, worldPositionStays: false);
            holder.transform.localPosition = MastCameraTable.LocalPosition(mount);
            holder.transform.localRotation = MastCameraTable.LocalRotation(mount);
            var camera = holder.AddComponent<Camera>();
            camera.enabled = false; // attitude carrier; only the feed renders
            if (mount.Channel == MastSensorChannel.Lidar)
            {
                // P3-S3 LiDAR depth camera: pinhole profile = the LidarPattern
                // mapping (32° vertical FOV, 640×184 target ⇒ 90° horizontal),
                // far clip = the 100 m sensor range clip (free range gating).
                // Rendering is driven by LidarViewPass only in sensor_mode=lidar.
                camera.fieldOfView = LidarPattern.DepthCameraFovDeg;
                camera.nearClipPlane = 0.5f;
                camera.farClipPlane = LidarPattern.MaxRangeM;
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = Color.black;
            }
            else
            {
                camera.fieldOfView = mount.HFovDeg;
                camera.nearClipPlane = 0.3f;
                camera.farClipPlane = 20000f;
                camera.clearFlags = CameraClearFlags.Skybox;
            }
            _cameras[mount.MountId] = camera;
        }

        private bool ConfigureFeedTarget()
        {
            if (FeedCamera == null) return false;
            if (!MastCameraTable.TryGet(feedMountId, out var mount)) return false;
            _feedTarget = new RenderTexture(mount.FrameWidthPx, mount.FrameHeightPx, 24, RenderTextureFormat.ARGB32)
            {
                name = $"{feedMountId}.feed",
            };
            _feedTarget.Create();
            FeedCamera.targetTexture = _feedTarget;
            FeedCamera.enabled = true; // renders into the target each frame; CameraCaptureBridge captures it
            return true;
        }

        private void OnDestroy() => Detach();
    }
}
