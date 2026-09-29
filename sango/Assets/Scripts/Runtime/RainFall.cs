using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M7-B 雨 VFX（B3 雷暴雨幡档；M1 挂账的雨落此）：相机挂载的粒子雨。发射器跟相机
    /// （本组件所在 Transform），粒子世界系模拟（不随相机旋转/移动拖尾），匀速下落长条
    /// 拉伸片（HDRP/Unlit 透明）。发射率由 WeatherController.rainRate 驱动（SetRate），
    /// 0 = 全关（无粒子、无绘制开销）。
    /// </summary>
    public class RainFall : MonoBehaviour
    {
        [Tooltip("雨滴下落速度 m/s。")]
        public float fallSpeedMps = 9f;

        [Tooltip("发射盒半尺寸 m（相机周身雨柱范围）。")]
        public Vector3 boxHalfExtentsM = new Vector3(28f, 6f, 28f);

        [Tooltip("雨滴颜色（半透明淡蓝白）。")]
        public Color rainColor = new Color(0.75f, 0.85f, 0.95f, 0.32f);

        [Tooltip("雨滴长度 m（速度拉伸前的片长）。")]
        public float dropLengthM = 0.45f;

        ParticleSystem m_Ps;
        Material m_DropMat;

        void Awake()
        {
            BuildRain();
        }

        void BuildRain()
        {
            if (m_Ps != null) return; // 幂等（域重载不重建）

            m_DropMat = new Material(Shader.Find("HDRP/Unlit"));
            m_DropMat.SetColor("_UnlitColor", rainColor);
            m_DropMat.SetFloat("_SurfaceType", 1f);
            m_DropMat.SetFloat("_BlendMode", 0f); // HDRP BlendMode 0 = Alpha
            m_DropMat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m_DropMat.SetFloat("_SrcBlend", (float)UnityEngine.Rendering.BlendMode.SrcAlpha);
            m_DropMat.SetFloat("_DstBlend", (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            m_DropMat.SetFloat("_ZWrite", 0f);
            m_DropMat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;

            m_Ps = gameObject.AddComponent<ParticleSystem>();
            var main = m_Ps.main;
            main.simulationSpace = ParticleSystemSimulationSpace.World; // 发射器跟相机走，雨滴留世界系
            main.startLifetime = 1.4f;
            main.startSpeed = 0f;                                       // 速度全走 velocity-over-life（匀速直落）
            main.startSize3D = true;
            main.startSizeX = 0.03f;
            main.startSizeY = dropLengthM;
            main.startSizeZ = 0.03f;
            main.maxParticles = 4000;
            main.gravityModifier = 0f;
            main.loop = true;

            var vel = m_Ps.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.y = -fallSpeedMps;

            var shape = m_Ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = boxHalfExtentsM * 2f;

            var emission = m_Ps.emission;
            emission.rateOverTime = 0f; // SetRate 打开（默认关：晴档零开销）

            var renderer = GetComponent<ParticleSystemRenderer>();
            renderer.material = m_DropMat;
            renderer.renderMode = ParticleSystemRenderMode.Stretch;
            renderer.velocityScale = 0.06f; // 拉伸沿下落方向拉长雨丝
            renderer.lengthScale = 0f;
            renderer.alignment = ParticleSystemRenderSpace.View;
            renderer.sortingFudge = -10f;
        }

        /// <summary>设置发射率（粒子/秒）；0 = 停发（存量粒子自然落尽）。WeatherController.Apply 每帧驱动。</summary>
        public void SetRate(float particlesPerSecond)
        {
            if (m_Ps == null) BuildRain();
            var emission = m_Ps.emission;
            emission.rateOverTime = Mathf.Max(0f, particlesPerSecond);
        }
    }
}
