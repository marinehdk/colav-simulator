using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// Finite visual wake history deposited in world space. Native water renders
    /// its displacement and foam; this is a wave/propwash appearance model, not CFD.
    /// </summary>
    public sealed class TwinWakeTrail : MonoBehaviour
    {
        struct Sample
        {
            public WaterDecal decal;
            public Vector3 position, forward;
            public float born, speed;
            public bool active;
        }

        const float Lifetime = 32f;
        Sample[] m_Samples;
        Material[] m_Materials;
        GameObject m_World;
        int m_Next;
        float m_Loa, m_Beam, m_Spacing;
        Vector3 m_LastEmission, m_LastPosition;
        bool m_HavePosition, m_HaveEmission;
        public int ActiveSamples { get; private set; }
        public float OldestAge { get; private set; }

        public void Initialize(float loa, float beam, bool primary)
        {
            var source = Resources.Load<Material>("TwinWakeTrail");
            if (source == null) { Debug.LogError("[Sango.Wake] TwinWakeTrail material missing"); return; }
            m_Loa = Mathf.Max(loa, 1);
            m_Beam = Mathf.Max(beam, 1);
            m_Spacing = Mathf.Clamp(loa * 0.06f, 1.5f, 6f);
            m_World = new GameObject("Twin wake history");
            m_Materials = new Material[4];
            for (int i = 0; i < m_Materials.Length; i++)
            {
                m_Materials[i] = new Material(source);
                m_Materials[i].SetFloat("_Seed", 7.3f + i * 13.7f);
            }
            m_Samples = new Sample[primary ? 96 : 12];
            for (int i = 0; i < m_Samples.Length; i++)
            {
                var go = new GameObject("Wake sample " + i);
                go.transform.SetParent(m_World.transform, false);
                var decal = go.AddComponent<WaterDecal>();
                decal.material = m_Materials[i % m_Materials.Length];
                decal.scaleMode = DecalScaleMode.ScaleInvariant;
                decal.resolution = new Vector2Int(128, 128);
                decal.updateMode = CustomRenderTextureUpdateMode.OnLoad;
                decal.RequestUpdate();
                decal.enabled = false;
                m_Samples[i].decal = decal;
            }
        }

        // Explicit time/pose inputs make pause, turns and seek discontinuities testable.
        public void Advance(float now, float dt, Vector3 stern, Vector3 forward, float speed, Vector3 current)
        {
            if (m_Samples == null) return;
            stern.y = 0;
            forward.y = 0;
            forward.Normalize();
            if (m_HavePosition && Vector3.Distance(stern, m_LastPosition) > Mathf.Max(30f, m_Loa * 2))
                Clear();
            m_LastPosition = stern;
            m_HavePosition = true;
            if (speed > 0.5f && (!m_HaveEmission || Vector3.Distance(stern, m_LastEmission) >= m_Spacing))
            {
                ref var sample = ref m_Samples[m_Next];
                sample.position = stern;
                sample.forward = forward;
                sample.born = now;
                sample.speed = speed;
                sample.active = true;
                m_Next = (m_Next + 1) % m_Samples.Length;
                m_LastEmission = stern;
                m_HaveEmission = true;
            }
            ActiveSamples = 0;
            OldestAge = 0;
            for (int i = 0; i < m_Samples.Length; i++)
            {
                ref var sample = ref m_Samples[i];
                if (!sample.active) continue;
                float age = now - sample.born;
                if (age < 0 || age >= Lifetime)
                {
                    sample.active = false;
                    sample.decal.enabled = false;
                    continue;
                }
                sample.position += new Vector3(current.x, 0, current.z) * Mathf.Max(dt, 0);
                // Outward travel widens the envelope; old samples retain their own
                // direction through a turn instead of rotating with the current hull.
                float width = m_Beam * 1.1f + age * sample.speed;
                float fade = 0.50f * Mathf.Exp(-age / 20f)
                    * (1 - Mathf.SmoothStep(0, 1, Mathf.InverseLerp(16f, Lifetime, age)));
                float energy = Mathf.Clamp01(sample.speed * sample.speed / (9.81f * m_Loa) * 6);
                sample.decal.enabled = true;
                sample.decal.transform.SetPositionAndRotation(sample.position, Quaternion.LookRotation(sample.forward));
                sample.decal.regionSize = new Vector2(width, m_Spacing * 3.5f);
                sample.decal.surfaceFoamDimmer = energy * fade;
                sample.decal.deepFoamDimmer = energy * fade * 0.25f;
                sample.decal.amplitude = energy * Mathf.Exp(-age / 14f) * 0.5f;
                ActiveSamples++;
                OldestAge = Mathf.Max(OldestAge, age);
            }
        }

        public void Clear()
        {
            if (m_Samples != null)
                for (int i = 0; i < m_Samples.Length; i++)
                { m_Samples[i].active = false; m_Samples[i].decal.enabled = false; }
            m_HavePosition = m_HaveEmission = false;
            ActiveSamples = 0;
            OldestAge = 0;
        }

        void OnDisable() { if (m_World != null) m_World.SetActive(false); }
        void OnEnable() { if (m_World != null) m_World.SetActive(true); }
        void OnDestroy()
        {
            if (m_Materials != null) foreach (var material in m_Materials) Release(material);
            Release(m_World);
        }
        static void Release(Object value)
        {
            if (value == null) return;
            if (Application.isPlaying) Destroy(value); else DestroyImmediate(value);
        }
    }
}
