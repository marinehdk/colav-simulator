using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// P3-S3 LiDAR point-cloud view (spec #90; twin-bridge-v1 `sensor_mode=lidar`
    /// 真实现 replacing the S2 accept-and-echo placeholder): a fullscreen
    /// CustomPass on the twin stream camera that re-renders the camera's own
    /// depth field as the 16-line point lattice over the deep-dark backdrop
    /// (render-graph-native CustomPassLoadCameraDepth — same camera, no
    /// cross-camera matrices/textures; the debugging ledger in
    /// LidarPointCloud.shader records why cross-camera plumbing stayed
    /// invisible on Metal). Gates follow the IrViewPass precedent (static
    /// Requested/TargetCamera checked every frame) so the Demo rendering path
    /// is untouched. Point data never leaves Unity (hard boundary: the backend
    /// LidarContactSensor is an independent synthetic model). The lattice math
    /// lives in <see cref="LidarPattern"/>/<see cref="LidarNoise"/>
    /// (EditMode-tested; the shader is a thin port).
    /// </summary>
    public sealed class LidarViewPass : CustomPass
    {
        /// <summary>Master gate (TwinBridgeService sensor_mode=lidar toggles it).</summary>
        public static bool Requested { get; private set; }

        /// <summary>Scoped camera (the twin pixel-stream source; null = every camera).</summary>
        public static Camera TargetCamera { get; private set; }

        /// <summary>10 Hz noise/pattern seed (LidarPattern.FramePeriodS rollover).</summary>
        public static int FrameSeed { get; private set; }

        private static float _lastFrameTime = -1f;
        private static Material _material;

        private const string ShaderName = "Hidden/Sango/LidarPointCloud";

        /// <summary>Mirror of the shader pass table (LidarPointCloud.shader).</summary>
        internal const int PassPoints = 0;

        /// <summary>Mode switch (idempotent).</summary>
        public static void SetActive(bool active, Camera targetCamera)
        {
            Requested = active;
            TargetCamera = active ? targetCamera : null;
        }

        protected override void Setup(ScriptableRenderContext renderContext, CommandBuffer cmd)
        {
            if (_material == null)
            {
                // Resources path keeps the shader in player builds (Shader.Find only
                // resolves shaders the build actually references).
                Shader shader = Shader.Find(ShaderName);
                if (shader == null) shader = Resources.Load<Shader>("LidarPointCloud");
                if (shader != null) _material = CoreUtils.CreateEngineMaterial(shader);
                if (_material == null)
                {
                    Debug.LogError($"[Sango.LidarViewPass] {ShaderName} not found (expected Resources/LidarPointCloud.shader)");
                    return;
                }
            }
            _material.SetFloat("_LidarChannelCount", LidarPattern.ChannelCount);
            _material.SetFloat("_LidarChannelSpanDeg", LidarPattern.ChannelSpanDeg);
            _material.SetFloat("_LidarMaxRange", LidarPattern.MaxRangeM);
            _material.SetFloat("_LidarRangeSigmaBase", LidarNoise.RangeSigmaBaseM);
            _material.SetFloat("_LidarRangeSigmaRise", LidarNoise.RangeSigmaRisePerM);
            _material.SetFloat("_LidarAttenPerM", LidarNoise.AtmosphereAttenuationPerM);
            _material.SetFloat("_LidarDropRate", LidarNoise.DropoffGeneralRate);
            _material.SetFloat("_LidarDropLimit", LidarNoise.DropoffIntensityLimit);
            _material.SetFloat("_LidarZeroIntensity", LidarNoise.DropoffZeroIntensity);
            _material.SetVector("_LidarRampHeights", new Vector4(LidarNoise.RampHeightMinM, LidarNoise.RampHeightMaxM, 0f, 0f));
        }

        protected override void Execute(CustomPassContext ctx)
        {
            if (!Requested || _material == null) return;
            if (TargetCamera != null && ctx.hdCamera.camera != TargetCamera) return;
            // Roll the 10 Hz noise seed (wall-clock; visual cadence only).
            float now = Time.unscaledTime;
            if (_lastFrameTime < 0f || now - _lastFrameTime >= LidarPattern.FramePeriodS)
            {
                _lastFrameTime = now;
                FrameSeed++;
            }
            // All per-frame values ride as MATERIAL properties: shader globals set
            // from Update do not bind inside the render-graph custom pass on Metal.
            var rayCamera = ctx.hdCamera.camera;
            float width = Mathf.Max(1f, ctx.hdCamera.actualWidth);
            float height = Mathf.Max(1f, ctx.hdCamera.actualHeight);
            _material.SetMatrix(PropRayCamLocalToWorld, rayCamera.transform.localToWorldMatrix);
            _material.SetVector(PropRayCamPos, rayCamera.transform.position);
            float tanHalfV = Mathf.Tan(rayCamera.fieldOfView * 0.5f * Mathf.Deg2Rad);
            float aspect = rayCamera.aspect > 0.01f ? rayCamera.aspect : width / height;
            _material.SetVector(PropRayTanHalfFov, new Vector4(tanHalfV * aspect, tanHalfV, 0f, 0f));
            _material.SetFloat(PropSeed, FrameSeed);
            _material.SetFloat(PropPointSpacingPx, PointSpacingPx);
            _material.SetVector(PropScreenSize, new Vector4(width, height, 0f, 0f));
            CoreUtils.DrawFullScreen(ctx.cmd, _material, shaderPassId: PassPoints);
        }

        /// <summary>Screen-space cell size in pixels (lattice pitch).</summary>
        internal const float PointSpacingPx = 5f;

        private static readonly int PropRayCamLocalToWorld = Shader.PropertyToID("_RayCamLocalToWorld");
        private static readonly int PropRayCamPos = Shader.PropertyToID("_RayCamPos");
        private static readonly int PropRayTanHalfFov = Shader.PropertyToID("_RayTanHalfFov");
        private static readonly int PropSeed = Shader.PropertyToID("_LidarSeed");
        private static readonly int PropPointSpacingPx = Shader.PropertyToID("_LidarPointSpacingPx");
        private static readonly int PropScreenSize = Shader.PropertyToID("_LidarScreenSize");

        protected override void Cleanup()
        {
            CoreUtils.Destroy(_material);
            _material = null;
        }
    }
}
