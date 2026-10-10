using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// Speed-gated HDRP bow deformation and foam injection. Demo retains the original
    /// decal settings. Twin adds porous stern/hull-contact sources in the water buffer;
    /// it never renders an independent white surface mesh or owns navigation physics.
    /// </summary>
    [DefaultExecutionOrder(150)] // Contact sampling follows visual buoyancy (100).
    public class BoatWaterDecals : MonoBehaviour
    {
        [Tooltip("艏波变形 decal（船艏子物体，场景构建器注入）。")]
        public WaterDecal bowDecal;

        [Tooltip("尾迹泡沫 decal（船体中后部子物体，场景构建器注入）。")]
        public WaterDecal wakeDecal;

        [Tooltip("航速真值来源（无则恒 0：decal 禁用）。")]
        public WaypointFollower follower;
        public System.Func<float> twinSpeedMps;
        public System.Func<Vector3> twinCurrentVelocity;
        public bool twinSurfaceWake;
        public WaterSurface twinWater;
        public float beamMeters = 8f;
        public float ContactEntryMps { get; private set; }
        public float ContactFoam01 { get; private set; }
        Material m_FoamMaterial;
        Material m_BowMaterial;
        Texture2D m_FoamTexture;
        readonly WaterDecal[] m_ContactDecals = new WaterDecal[8];
        readonly float[] m_PreviousImmersion = new float[8];
        readonly Vector3[] m_BowContact = new Vector3[2];
        TwinWakeTrail m_Trail;
        bool m_HaveContact;
        float m_NextDiagnostic;
        bool m_Primary, m_ReadbackPending;
        public float BufferFoamMax { get; private set; }
        public float PropwashFoam01 => wakeDecal != null && wakeDecal.enabled ? wakeDecal.surfaceFoamDimmer : 0;
        public Vector3 BowContactPoint(int side) => m_HaveContact ? m_BowContact[side] : transform.position;

        WaterSearchParameters m_ContactSearch;


        [Tooltip("启用阈值（m/s）：低于此航速（静止/锢泊）decal 禁用。")]
        public float speedThresholdMps = 0.5f;

        [Tooltip("全强航速（m/s）：尾迹泡沫/艏波幅度线性爬坡到此为 1。")]
        public float fullEffectSpeedMps = 5f;

        [Tooltip("艏波幅度基准（米，全强 Fr=0.45 以上）：12 m 小船量级 ~0.4 m。")]
        public float bowAmplitudeM = 0.4f;

        [Tooltip("船长 LOA（米）：艏波按 Froude 数 Fr=v/√(g·LOA) 爬坡的尺度分母（默认 12 = 编目 Small）。")]
        public float loaMeters = 12f;

        [Tooltip("尾迹泡沫强度乘子 ∈ [0,1]（Simulation 面板 M4 滑条实时驱动；1 = 全强）。")]
        public float wakeFoamIntensity = 1f;

        /// <summary>
        /// 以给定航速驱动两块 decal（公开 = EditMode 可测缝，先例 WaypointFollower.StepOnce）：
        /// enabled = 门限谓词；艏波幅度走 Froude 曲线（长船起波晚，WaterDecalSpeedGate.BowAmplitude），
        /// 泡沫 dimmer = 线性爬坡 × 面板强度乘子——低速弱尾迹、全速全强。
        /// </summary>
        public void ApplySpeed(float speedMps)
        {
            bool enabled = WaterDecalSpeedGate.ShouldEnableDecals(speedMps, speedThresholdMps);
            float ramp = WaterDecalSpeedGate.WakeFoamIntensity(speedMps, speedThresholdMps, fullEffectSpeedMps);
            if (bowDecal != null)
            {
                bowDecal.enabled = enabled;
                bowDecal.amplitude = WaterDecalSpeedGate.BowAmplitude(speedMps, speedThresholdMps, loaMeters, bowAmplitudeM);
                if (twinSurfaceWake) bowDecal.surfaceFoamDimmer = ramp
                    * Mathf.Clamp01(bowDecal.amplitude / Mathf.Max(bowAmplitudeM,0.01f));
            }
            if (wakeDecal != null)
            {
                wakeDecal.enabled = enabled;
                wakeDecal.surfaceFoamDimmer = ramp * wakeFoamIntensity;
                if (twinSurfaceWake) wakeDecal.deepFoamDimmer = ramp * 0.12f;
            }
        }

        /// <summary>Inject foam into HDRP water, never draw a separate surface plane.</summary>
        public void ConfigureTwinWater(WaterSurface surface, float beam, bool primary = false)
        {
            twinSurfaceWake = true;
            m_Primary = primary;
            twinWater = surface;
            beamMeters = Mathf.Max(beam, 1f);
            var source = Resources.Load<Material>("TwinWakeFoam");
            if (source == null || wakeDecal == null) return;
            m_FoamMaterial = new Material(source) { name = "Twin water foam injection" };
            m_FoamTexture = BuildFoamTexture();
            m_FoamMaterial.SetTexture("_Foam_Texture", m_FoamTexture);
            wakeDecal.material = m_FoamMaterial;
            wakeDecal.updateMode = CustomRenderTextureUpdateMode.OnLoad;
            wakeDecal.RequestUpdate();
            // Short propeller-wash source. HDRP preserves deposited foam in world space.
            float washLength = Mathf.Clamp(loaMeters * 0.4f, 4f, 20f);
            wakeDecal.regionSize = new Vector2(beamMeters * 0.65f, washLength);
            wakeDecal.transform.localPosition = new Vector3(0, 0, -loaMeters * 0.48f - washLength * 0.35f);
            wakeDecal.deepFoamDimmer = 0.15f;
            var bowSource = Resources.Load<Material>("TwinWakeTrail");
            if (bowDecal != null && bowSource != null)
            {
                m_BowMaterial = new Material(bowSource) { name = "Twin displaced bow wave" };
                m_BowMaterial.SetFloat("_Bow", 1f);
                float length = loaMeters * 0.7f;
                m_BowMaterial.SetVector("_Region", new Vector4(beamMeters * 4, length, 0, 0));
                bowDecal.material = m_BowMaterial;
                bowDecal.regionSize = new Vector2(beamMeters * 4, length);
                bowDecal.transform.localRotation = Quaternion.identity;
                bowDecal.transform.localPosition = new Vector3(0, 0, loaMeters * 0.5f - length * 0.5f);
                bowDecal.deepFoamDimmer = 0.1f;
                bowDecal.updateMode = CustomRenderTextureUpdateMode.OnLoad;
                bowDecal.RequestUpdate();
            }
            var stations = new[] { 0.44f, 0.30f, 0.10f, -0.22f };
            var halfWidths = new[] { 0.25f, 0.48f, 0.57f, 0.57f };
            for (int index = 0; index < m_ContactDecals.Length; index++)
            {
                int side = index % 2, station = index / 2;
                var go = new GameObject(side == 0 ? "Port hull wave contact" : "Starboard hull wave contact");
                go.transform.SetParent(transform, false);
                go.transform.localPosition = new Vector3((side == 0 ? -1 : 1) * beamMeters * halfWidths[station], 0, loaMeters * stations[station]);
                var decal = go.AddComponent<WaterDecal>();
                decal.material = m_FoamMaterial;
                decal.updateMode = CustomRenderTextureUpdateMode.OnLoad;
                decal.RequestUpdate();
                decal.scaleMode = DecalScaleMode.ScaleInvariant;
                decal.regionSize = new Vector2(beamMeters * 0.3f, Mathf.Clamp(loaMeters * 0.16f, 2f, 9f));
                decal.surfaceFoamDimmer = decal.deepFoamDimmer = 0;
                m_ContactDecals[index] = decal;
            }
            m_Trail = gameObject.AddComponent<TwinWakeTrail>();
            m_Trail.Initialize(loaMeters, beamMeters, primary);
            m_ContactSearch.error = 0.02f;
            m_ContactSearch.maxIterations = 8;
            // Own bow deformation must not feed back into contact/buoyancy excitation.
            m_ContactSearch.includeDeformation = false;
        }

        static Texture2D BuildFoamTexture()
        {
            const int size = 128;
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, true, true)
            { name = "Twin porous foam source", wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear };
            var pixels = new Color[size * size];
            for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float u = (x + 0.5f) / size, v = (y + 0.5f) / size;
                float radius = Mathf.Sqrt(Mathf.Pow((u - 0.5f) * 2, 2) + Mathf.Pow((v - 0.5f) * 2, 2));
                float edge = 1 - Mathf.SmoothStep(0, 1, Mathf.InverseLerp(0.4f, 1, radius));
                float noise = Mathf.PerlinNoise(u * 19 + 12.3f, v * 23 + 4.7f);
                float patch = Mathf.PerlinNoise(u * 6 + 2.1f, v * 8 + 9.4f);
                // R = surface foam, G = deep foam (HDRP Water Decal contract).
                float foam = edge * Mathf.Lerp(0.45f, 1f, noise) * Mathf.Lerp(0.5f, 1, patch);
                pixels[y * size + x] = new Color(foam, foam * 0.2f, 0, 1);
            }
            texture.SetPixels(pixels); texture.Apply(true, true);
            return texture;
        }

        void LateUpdate()
        {
            if (!twinSurfaceWake || twinWater == null || m_ContactDecals[0] == null) return;
            float entry = 0, contact = 0;
            float speed = twinSpeedMps?.Invoke() ?? 0f;
            float speedContact = WaterDecalSpeedGate.WakeFoamIntensity(speed, speedThresholdMps, fullEffectSpeedMps);
            for (int index = 0; index < m_ContactDecals.Length; index++)
            {
                var decal = m_ContactDecals[index];
                var point = decal.transform.position; // actual waterline after heave/pitch/roll
                m_ContactSearch.startPositionWS = m_ContactSearch.targetPositionWS = point;
                bool ok = twinWater.ProjectPointOnWaterSurface(m_ContactSearch, out var result);
                float immersion = ok ? result.projectedPositionWS.y - point.y : 0;
                float entering = ok && m_HaveContact && Time.deltaTime > 0
                    ? Mathf.Max(0, (immersion - m_PreviousImmersion[index]) / Time.deltaTime) : 0;
                m_PreviousImmersion[index] = immersion;
                float wet = Mathf.Clamp01((immersion + 0.35f) / 0.7f);
                float intensity = ok ? Mathf.Clamp01(speedContact * wet * 0.75f + Mathf.Max(0, immersion) * 0.35f + entering * 0.3f) : 0;
                decal.surfaceFoamDimmer = intensity * 1f;
                decal.deepFoamDimmer = intensity * 0.16f;
                if (index < 2) m_BowContact[index] = ok ? (Vector3)result.projectedPositionWS : point;
                entry = Mathf.Max(entry, entering);
                contact = Mathf.Max(contact, intensity);
            }
            m_HaveContact = true;
            ContactEntryMps = Mathf.Min(entry, 5f);
            ContactFoam01 = contact;
            m_Trail.Advance(Time.time, Time.deltaTime, transform.TransformPoint(new Vector3(0, 0, -loaMeters * 0.48f)),
                transform.forward, speed, twinCurrentVelocity?.Invoke() ?? Vector3.zero);
            if (Time.unscaledTime >= m_NextDiagnostic)
            {
                m_NextDiagnostic = Time.unscaledTime + 10;
                if (m_Primary && !m_ReadbackPending && SystemInfo.supportsAsyncGPUReadback)
                {
                    var buffer = twinWater.GetFoamBuffer(out var area);
                    if (buffer != null)
                    {
                        m_ReadbackPending = true;
                        UnityEngine.Rendering.AsyncGPUReadback.Request(buffer, 0, TextureFormat.RGBAFloat, request =>
                        {
                            if (this == null) return;
                            m_ReadbackPending = false;
                            if (request.hasError) return;
                            float peak = 0; int covered = 0;
                            var pixels = request.GetData<Color>();
                            foreach (var pixel in pixels) { peak = Mathf.Max(peak, pixel.r); if (pixel.r > 0.01f) covered++; }
                            BufferFoamMax = peak;
                            var camera = Camera.main;
                            bool cameraDecals = camera != null && UnityEngine.Rendering.HighDefinition.HDCamera.GetOrCreate(camera).frameSettings.IsEnabled(FrameSettingsField.WaterDecals);
                            Debug.Log($"[Sango.WaterContact.Buffer] peak={peak:F3} covered={covered} size={buffer.width}x{buffer.height} area={area} camera_decals={cameraDecals}");
                        });
                    }
                    else Debug.Log("[Sango.WaterContact.Buffer] unavailable");
                }
                Debug.Log($"[Sango.WaterContact] {transform.parent.name} speed={twinSpeedMps?.Invoke():F2} " +
                    $"propwash={PropwashFoam01:F3} contact={contact:F3} entry={ContactEntryMps:F2} " +
                    $"affects_foam={m_FoamMaterial.GetFloat("_AffectFoam"):F0} foam_pass={m_FoamMaterial.FindPass("Foam")}");
            }
        }

        void OnDestroy()
        {
            if (Application.isPlaying) { Destroy(m_FoamMaterial); Destroy(m_FoamTexture); Destroy(m_BowMaterial); }
            else { DestroyImmediate(m_FoamMaterial); DestroyImmediate(m_FoamTexture); DestroyImmediate(m_BowMaterial); }
        }

        void Update()
        {
            ApplySpeed(twinSpeedMps != null ? twinSpeedMps() : follower != null ? follower.SpeedMps : 0f);
        }
    }
}
