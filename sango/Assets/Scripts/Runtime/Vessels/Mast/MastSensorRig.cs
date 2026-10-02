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

        /// <summary>Feed-mount world pose at the last attach (diagnostics).</summary>
        public bool Attached => FeedCamera != null;

        /// <summary>Built mount count (diagnostics/tests).</summary>
        public int BuiltMountCount => _cameras.Count;

        /// <summary>
        /// Parents the rig under the vessel root and builds every mount of the
        /// table. Idempotent: re-attach to a new vessel rebuilds the family.
        /// </summary>
        public bool Attach(Transform target)
        {
            if (target == null) return false;
            if (vesselRoot == target && FeedCamera != null) return true;
            Detach();
            vesselRoot = target;
            transform.SetParent(vesselRoot, worldPositionStays: false);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
            foreach (var mount in MastCameraTable.Mounts) BuildMount(mount);
            bool feedOk = TryGetCamera(feedMountId, out var feedCamera);
            FeedCamera = feedOk ? feedCamera : null;
            return FeedCamera != null && ConfigureFeedTarget();
        }

        /// <summary>Removes the rig from the vessel and destroys the mount hierarchy + feed target.</summary>
        public void Detach()
        {
            FeedCamera = null;
            _cameras.Clear();
            if (_feedTarget != null)
            {
                _feedTarget.Release();
                Destroy(_feedTarget);
                _feedTarget = null;
            }
            for (int i = transform.childCount - 1; i >= 0; i--)
            {
                var child = transform.GetChild(i).gameObject;
                if (Application.isPlaying) Destroy(child);
                else DestroyImmediate(child);
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
            camera.fieldOfView = mount.HFovDeg;
            camera.nearClipPlane = 0.3f;
            camera.farClipPlane = 20000f;
            camera.clearFlags = CameraClearFlags.Skybox;
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
