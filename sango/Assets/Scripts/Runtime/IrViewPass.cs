using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// P3-S2 IR white-hot Custom Pass (spec #90; twin-bridge-v1 `sensor_mode`):
    /// renders the black-and-white thermal scope over the twin stream camera
    /// only — <see cref="Requested"/> + <see cref="TargetCamera"/> gate every
    /// frame, so the Demo-mode rendering path is untouched (hard boundary) and
    /// sensor_mode=eo disables the effect entirely (zero cost beyond one bool
    /// check per camera). sensor_mode=lidar is accepted and echoed by
    /// TwinBridgeService but renders nothing in S2 (point-cloud view = S3).
    /// </summary>
    public sealed class IrViewPass : CustomPass
    {
        /// <summary>Master gate (TwinBridgeService sensor_mode=ir toggles it).</summary>
        public static bool Requested;

        /// <summary>Scoped camera (the twin pixel-stream source; null = every camera).</summary>
        public static Camera TargetCamera;

        public const float DefaultGain = 1.6f;
        public const float DefaultGamma = 0.8f;

        private Material _material;

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
                Shader shader = Shader.Find("Hidden/Sango/IrWhiteHot");
                if (shader == null) shader = Resources.Load<Shader>("IrWhiteHot");
                if (shader != null) _material = CoreUtils.CreateEngineMaterial(shader);
                if (_material == null)
                    Debug.LogError("[Sango.IrViewPass] IrWhiteHot shader not found (expected Resources/IrWhiteHot.shader)");
            }
            if (_material != null)
            {
                _material.SetFloat("_IrGain", DefaultGain);
                _material.SetFloat("_IrGamma", DefaultGamma);
            }
        }

        protected override void Execute(CustomPassContext ctx)
        {
            if (!Requested || _material == null) return;
            if (TargetCamera != null && ctx.hdCamera.camera != TargetCamera) return;
            CoreUtils.DrawFullScreen(ctx.cmd, _material, shaderPassId: 0);
        }

        protected override void Cleanup()
        {
            CoreUtils.Destroy(_material);
            _material = null;
        }
    }
}
