using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>Camera-local visual snow, wet lens and lightning. No calibrated optical/meteorological model.</summary>
    public class CameraWeatherEffects : MonoBehaviour
    {
        ParticleSystem m_Snow;
        Transform m_Lens;
        Material m_SnowMaterial, m_LensMaterial;
        Texture2D m_DropTexture;
        Light m_Flash;
        bool m_Thunder;
        float m_Intensity;

        void EnsureEffects()
        {
            if (m_Snow != null) return;
            var snow = new GameObject("Visual snow", typeof(ParticleSystem));
            snow.transform.SetParent(transform, false); snow.transform.localPosition = new Vector3(0, 9, 8);
            m_Snow = snow.GetComponent<ParticleSystem>();
            var main = m_Snow.main;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startLifetime = 6f; main.startSpeed = 0f; main.startSize = new ParticleSystem.MinMaxCurve(0.025f, 0.075f);
            main.maxParticles = 1800; main.startColor = new Color(0.85f, 0.92f, 1f, 0.75f);
            var velocity = m_Snow.velocityOverLifetime; velocity.enabled = true; velocity.space = ParticleSystemSimulationSpace.World;
            velocity.x = 0.4f; velocity.y = -2.8f; velocity.z = 0.2f;
            var shape = m_Snow.shape; shape.shapeType = ParticleSystemShapeType.Box; shape.scale = new Vector3(35, 8, 40);
            m_SnowMaterial = Material();
            var renderer = snow.GetComponent<ParticleSystemRenderer>(); renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.sharedMaterial = m_SnowMaterial;
            var emission = m_Snow.emission; emission.rateOverTime = 0f;

            m_Lens = new GameObject("Wet lens visual").transform; m_Lens.SetParent(transform, false);
            m_DropTexture = new Texture2D(64, 64, TextureFormat.RGBA32, false);
            var pixels = new Color[64 * 64];
            for (int y = 0; y < 64; y++) for (int x = 0; x < 64; x++)
            {
                float r = new Vector2((x - 31.5f) / 31.5f, (y - 31.5f) / 31.5f).magnitude;
                float rim = Mathf.Exp(-Mathf.Pow((r - 0.78f) * 13f, 2f));
                pixels[y * 64 + x] = new Color(0.65f, 0.8f, 0.85f, r < 1f ? rim * 0.12f + Mathf.Max(0, 0.5f - r) * 0.05f : 0f);
            }
            m_DropTexture.SetPixels(pixels); m_DropTexture.Apply(false, true);
            m_LensMaterial = Material(); m_LensMaterial.SetTexture("_UnlitColorMap", m_DropTexture);
            m_LensMaterial.EnableKeyword("_UNLIT_COLOR_MAP"); HDMaterial.ValidateMaterial(m_LensMaterial);
            for (int i = 0; i < 14; i++)
            {
                var drop = GameObject.CreatePrimitive(PrimitiveType.Quad);
                drop.name = "Lens droplet " + i; drop.transform.SetParent(m_Lens, false);
                Destroy(drop.GetComponent<Collider>());
                drop.GetComponent<MeshRenderer>().sharedMaterial = m_LensMaterial;
            }
            m_Lens.gameObject.SetActive(false);
            var flash = new GameObject("Visual lightning", typeof(Light)); flash.transform.SetParent(transform, false);
            m_Flash = flash.GetComponent<Light>(); m_Flash.type = LightType.Directional; m_Flash.shadows = LightShadows.None;
            flash.AddComponent<HDAdditionalLightData>(); m_Flash.color = new Color(0.72f, 0.82f, 1f); m_Flash.enabled = false;
        }

        static Material Material()
        {
            var template = Resources.Load<Material>("SurfaceFoam");
            var material = template != null ? new Material(template) : new Material(Shader.Find("HDRP/Unlit"));
            material.SetColor("_UnlitColor", Color.white);
            material.SetFloat("_SurfaceType", 1f); material.SetFloat("_BlendMode", 0f);
            HDMaterial.ValidateMaterial(material);
            material.SetShaderPassEnabled("DepthForwardOnly", false); material.SetShaderPassEnabled("MotionVectors", false);
            return material;
        }

        public void Configure(bool snow, bool wetLens, bool thunder, float intensity)
        {
            if (m_Snow == null && !snow && !wetLens && !thunder) return;
            EnsureEffects();
            var emission = m_Snow.emission; emission.rateOverTime = snow ? Mathf.Clamp01(intensity) * 240f : 0f;
            m_Lens.gameObject.SetActive(wetLens);
            m_Thunder = thunder; m_Intensity = Mathf.Clamp01(intensity);
        }

        void LateUpdate()
        {
            if (m_Snow == null) return;
            var camera = GetComponent<Camera>();
            if (m_Lens.gameObject.activeSelf && camera != null)
            {
                float distance = camera.nearClipPlane + 0.1f;
                float halfHeight = Mathf.Tan(camera.fieldOfView * Mathf.Deg2Rad * 0.5f) * distance;
                for (int i = 0; i < m_Lens.childCount; i++)
                {
                    float x = Mathf.Repeat(i * 0.618034f, 1f) * 2f - 1f;
                    float y = Mathf.Repeat(i * 0.381966f + 0.6f - Time.time * 0.012f, 1f) * 2f - 1f;
                    var drop = m_Lens.GetChild(i);
                    drop.localPosition = new Vector3(x * halfHeight * camera.aspect, y * halfHeight, distance);
                    drop.localRotation = Quaternion.identity;
                    drop.localScale = Vector3.one * halfHeight * (0.045f + (i % 4) * 0.016f);
                }
            }
            m_Flash.enabled = m_Thunder && Mathf.Repeat(Time.time, 9f) < 0.14f;
            if (m_Flash.enabled) m_Flash.intensity = 500f + m_Intensity * 1800f;
        }

        void OnDestroy()
        {
            if (m_SnowMaterial != null) Destroy(m_SnowMaterial);
            if (m_LensMaterial != null) Destroy(m_LensMaterial);
            if (m_DropTexture != null) Destroy(m_DropTexture);
        }
    }
}
