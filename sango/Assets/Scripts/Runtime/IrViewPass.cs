using System.Threading;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// P3-S2 IR white-hot Custom Pass (spec #90; twin-bridge-v1 `sensor_mode`),
    /// P2 IR realism round (survey 2026-10-19-sitaw-ir-latency-realism §4
    /// checklist): renders the black-and-white thermal scope over the twin
    /// stream camera only — <see cref="Requested"/> + <see cref="TargetCamera"/>
    /// gate every frame, so the Demo-mode rendering path is untouched (hard
    /// boundary) and sensor_mode=eo disables the effect entirely (zero cost
    /// beyond one bool check per camera). sensor_mode=lidar is accepted and
    /// echoed by TwinBridgeService but renders nothing here (point-cloud view =
    /// LidarViewPass). P2 adds: polarity (ir_blackhot inverts the display
    /// mapping), 640×512 sensor raster, NETD/FPN noise, AGC breathing and
    /// hot-source halo (all inside IrWhiteHot.shader); this pass feeds
    /// polarity/time/horizon uniforms per frame and runs the AGC mean servo —
    /// camera color → 240×135 → 16×9 downsample blit chain + AsyncGPUReadback
    /// (576 B/frame) → main-thread EMA (τ≈0.8s) → <c>_IrAgcMean</c> uniform.
    /// The servo replaces the previous per-pixel 9-tap mean (review: ~18.7M
    /// redundant LOADs/frame at 1080p and one-frame gain jumps when a hot
    /// source covered a tap).
    /// </summary>
    public sealed class IrViewPass : CustomPass
    {
        /// <summary>Master gate (TwinBridgeService sensor_mode=ir* toggles it).</summary>
        public static bool Requested;

        /// <summary>Scoped camera (the twin pixel-stream source; null = every camera).</summary>
        public static Camera TargetCamera;

        /// <summary>Black-hot polarity (sensor_mode=ir_blackhot; white-hot default).</summary>
        public static bool BlackHot;

        /// <summary>
        /// Tier-faithful static calibration: with gain 1.0 every IrTemperature
        /// tier survives the 0.8-gamma ramp as its own level (Exhaust→1.00,
        /// EngineRoom→0.88, Hull→0.57, Deck→0.43, Sea→0.20, Sky→0.09); the AGC
        /// breathes ±25% around it. The P3-S2 night calibration 1.6 saturated
        /// EngineRoom/Hull on its own, and stacked with an unclamped AGC it
        /// collapsed the six tiers into three (review finding) — the AGC home
        /// point now does the night lift instead (AgcTarget ≈ SeaGray).
        /// </summary>
        public const float DefaultGain = 1.0f;
        public const float DefaultGamma = 0.8f;

        /// <summary>Sensor raster (Boson-class 640×512; MastCameraTable IR mounts).</summary>
        public const int SensorWidthPx = 640;
        public const int SensorHeightPx = 512;

        /// <summary>
        /// AGC servo home point (pre-ramp scene mean): the canonical night
        /// sea/sky frame is dominated by tagged Sea 0.15 / Sky 0.05 → unity
        /// gain there; brighter land frames ease the gain down, darker frames
        /// up — both clamped 0.8-1.25 in the shader (tier separation holds).
        /// </summary>
        public const float AgcTarget = 0.15f;

        private Material _material;

        // ── AGC mean servo state ──────────────────────────────────────────────
        private RTHandle m_MeanHalf;   // 240×135 intermediate (1/8 of 1080p-class)
        private RTHandle m_MeanTiny;   // 16×9  readback target (UNorm: linear luma as-is)
        private readonly object m_MeanLock = new object();
        private float m_MeanRaw = AgcTarget;      // latest completed readback (worker thread writes)
        private float m_MeanSmoothed = AgcTarget; // EMA state (main thread only)
        // P2 评审 nit：工作线程回调写 false、主线程读写（m_MeanRaw 有锁而它没有）——
        // volatile 保可见性；最坏漏一拍读回，AGC 只是慢一拍更新，不影响正确性。
        private volatile bool m_ReadbackPending;

        public static void SetActive(bool active, Camera targetCamera, bool blackHot = false)
        {
            Requested = active;
            TargetCamera = active ? targetCamera : null;
            BlackHot = active && blackHot;
        }

        // Horizon math lives at IrTemperature.HorizonScreenY (Sango.Vessels) so
        // the EditMode tests can reach it — this file compiles into
        // Assembly-CSharp (CustomPass subclass outside the Sango.Vessels
        // asmdef, LidarViewPass precedent), which the test assembly cannot
        // reference.

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
                _material.SetVector("_IrSensorRes", new Vector4(SensorWidthPx, SensorHeightPx, 0f, 0f));
                _material.SetFloat("_IrAgcTarget", AgcTarget);
            }
            if (m_MeanHalf == null)
                m_MeanHalf = RTHandles.Alloc(240, 135, colorFormat: UnityEngine.Experimental.Rendering.GraphicsFormat.R8G8B8A8_UNorm,
                    filterMode: FilterMode.Bilinear, name: "IrAgcMeanHalf");
            if (m_MeanTiny == null)
                m_MeanTiny = RTHandles.Alloc(16, 9, colorFormat: UnityEngine.Experimental.Rendering.GraphicsFormat.R8G8B8A8_UNorm,
                    filterMode: FilterMode.Bilinear, name: "IrAgcMeanTiny");
        }

        protected override void Execute(CustomPassContext ctx)
        {
            if (!Requested || _material == null) return;
            if (TargetCamera != null && ctx.hdCamera.camera != TargetCamera) return;
            var camera = ctx.hdCamera.camera;
            // P2 评审修复（重大）：Unity Euler 正 x = 俯（Rx(+90)·(0,0,1)=(0,−1,0)，
            // CameraRig.ApplyPose 根因注释），HorizonScreenY 域约定负=俯——之前把
            // Unity euler x 直传等于符号反转（chase 档 Unity x=+26.6 算成仰 →
            // _IrHorizonY=0.066，真实 0.934，83% 画面被 shader 天空温度 lerp 压平）。
            // 经纯函数 seam 归一化+取负，符号由 EditMode（PitchFromUnityEulerX）锁定。
            float pitchDeg = IrTemperature.PitchFromUnityEulerX(camera.transform.eulerAngles.x);
            _material.SetFloat("_IrPolarity", BlackHot ? 1f : 0f);
            _material.SetFloat("_IrTime", Application.isPlaying ? Time.unscaledTime : 0f);
            _material.SetFloat("_IrHorizonY", IrTemperature.HorizonScreenY(pitchDeg, camera.fieldOfView));
            _material.SetFloat("_IrAgcMean", DriveAgcServo(ctx));
            CoreUtils.DrawFullScreen(ctx.cmd, _material, shaderPassId: 0);
        }

        /// <summary>
        /// AGC mean servo step: (1) enqueue the downsample blit chain for the
        /// NEXT readback (the readback issued now returns the previous frame's
        /// content — GPU queue order, one frame of lag the EMA absorbs);
        /// (2) integrate the latest completed raw mean toward the EMA (τ = 0.8s,
        /// main-thread only). Failure modes degrade to the neutral home point
        /// (unity gain): readback errors keep the last mean, black/unread
        /// frames (RT not yet blitted) are ignored.
        /// </summary>
        float DriveAgcServo(CustomPassContext ctx)
        {
            if (m_MeanHalf != null && m_MeanTiny != null)
            {
                HDUtils.BlitCameraTexture(ctx.cmd, ctx.cameraColorBuffer, m_MeanHalf, 0, true);
                HDUtils.BlitCameraTexture(ctx.cmd, m_MeanHalf, m_MeanTiny, 0, true);
                if (!m_ReadbackPending)
                {
                    m_ReadbackPending = true;
                    AsyncGPUReadback.Request(m_MeanTiny, 0, request =>
                    {
                        m_ReadbackPending = false;
                        if (request.hasError || !request.done) return;
                        var pixels = request.GetData<Color32>();
                        if (pixels.Length == 0) return;
                        double sum = 0.0;
                        for (int i = 0; i < pixels.Length; i++)
                        {
                            var p = pixels[i];
                            sum += (p.r * 0.2126 + p.g * 0.7152 + p.b * 0.0722) / 255.0;
                        }
                        float mean = (float)(sum / pixels.Length);
                        if (mean > 1e-4f)
                        {
                            lock (m_MeanLock) m_MeanRaw = mean;
                        }
                    });
                }
            }
            float raw;
            lock (m_MeanLock) raw = m_MeanRaw;
            m_MeanSmoothed = IrTemperature.AgcStep(m_MeanSmoothed, raw, Application.isPlaying ? Time.unscaledDeltaTime : 0f);
            return m_MeanSmoothed;
        }

        protected override void Cleanup()
        {
            CoreUtils.Destroy(_material);
            _material = null;
            m_MeanHalf?.Release();
            m_MeanTiny?.Release();
            m_MeanHalf = null;
            m_MeanTiny = null;
        }
    }
}
