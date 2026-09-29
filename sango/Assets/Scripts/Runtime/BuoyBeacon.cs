using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// M7-B 浮标夜灯（B1）：复用 NavigationLights 光弧工艺的小光点版——交叉双面自发光
    /// 灯片（HDRP/Unlit）+ 小范围点光源，灯质节奏由纯函数 M7BMath.BuoyLightIntensity 驱动
    /// （快闪/群闪/长闪区分标种）。昼夜语义与船号灯同一阈值 NavigationLightsCore.IsLightsOn
    /// （日落后亮灯）。场景重建零序列化负担（rig 运行时构建，bootstrapper 只挂组件注入）。
    /// </summary>
    public class BuoyBeacon : MonoBehaviour
    {
        [Tooltip("时刻真值源（空则恒亮并告警一次——浮标灯无昼夜跟随语义时按常亮处理）。")]
        public WeatherController weather;

        [Tooltip("灯质节奏（M7BMath.PatternFor 按标种注入）。")]
        public M7BMath.BuoyBlinkPattern pattern = M7BMath.BuoyBlinkPattern.QuickFlash;

        [Tooltip("灯色（IALA A：左舷红/右舷绿/方位与安全水域白）。")]
        public Color color = new Color(1f, 0.98f, 0.92f);

        [Tooltip("灯片自发光亮度（HDR 无关值，Unlit 颜色 ×nits）。")]
        public float lampEmissiveNits = 40f;

        [Tooltip("点光范围 m（浮标小光点档，远小于船桅灯）。")]
        public float lightRangeM = 300f;

        [Tooltip("点光强度（流明）。")]
        public float lightIntensityLm = 1200f;

        [Tooltip("灯片边长 m（十字交叉双面）。")]
        public float lampSizeM = 0.8f;

        [Tooltip("灯位本地偏移（浮体顶上方）。")]
        public Vector3 lampLocalOffset = new Vector3(0f, 5f, 0f);

        Transform m_RigRoot;
        Material m_Emissive;
        Light m_PointLight;
        bool m_WarnedNoWeather;

        const string k_RigName = "BuoyBeaconRig";

        void OnEnable()
        {
            if (Application.isPlaying) BuildRig(); // rig 纯运行时构建（NavigationLights 同契约：场景零序列化负担）
            m_WarnedNoWeather = false;
        }

        void BuildRig()
        {
            m_RigRoot = transform.Find(k_RigName);
            if (m_RigRoot == null)
            {
                m_RigRoot = new GameObject(k_RigName).transform;
                m_RigRoot.SetParent(transform, false);
                m_RigRoot.localPosition = lampLocalOffset;

                // 灯片：交叉双面十字（0°/90°），全向可读（NavigationLights.BuildLamp 同工艺）
                m_Emissive = new Material(Shader.Find("HDRP/Unlit")) { color = color * lampEmissiveNits };
                for (int i = 0; i < 2; i++)
                {
                    var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
                    DestroyCollider(quad.GetComponent<Collider>());
                    quad.name = $"Beacon.Quad{i}";
                    quad.transform.SetParent(m_RigRoot, false);
                    quad.transform.localPosition = Vector3.zero;
                    quad.transform.localRotation = Quaternion.Euler(0f, i * 90f, 0f);
                    quad.transform.localScale = new Vector3(lampSizeM, lampSizeM, 1f);
                    quad.GetComponent<MeshRenderer>().sharedMaterial = m_Emissive;
                }

                var lightGo = new GameObject("Beacon.Light");
                lightGo.transform.SetParent(m_RigRoot, false);
                m_PointLight = lightGo.AddComponent<Light>();
                m_PointLight.type = LightType.Point;
                m_PointLight.color = color;
                m_PointLight.range = lightRangeM;
                m_PointLight.intensity = lightIntensityLm;
                m_PointLight.shadows = LightShadows.None;
                lightGo.AddComponent<HDAdditionalLightData>();
            }
            else
            {
                // 域重载（Play 中重编译）后非序列化字段丢失：从既有 rig 重捕获
                var quad0 = m_RigRoot.Find("Beacon.Quad0");
                if (quad0 != null) m_Emissive = quad0.GetComponent<MeshRenderer>().sharedMaterial;
                var lightT = m_RigRoot.Find("Beacon.Light");
                if (lightT != null) m_PointLight = lightT.GetComponent<Light>();
            }
        }

        void Update()
        {
            if (m_RigRoot == null || m_Emissive == null || m_PointLight == null) return;
            bool on = true;
            if (weather == null)
            {
                if (!m_WarnedNoWeather)
                {
                    m_WarnedNoWeather = true;
                    Debug.LogWarning($"[Sango.M7B] {name}: no WeatherController injected — beacon stays lit (no day/night follow).", this);
                }
            }
            else
            {
                on = NavigationLightsCore.IsLightsOn(weather.timeOfDayHours);
            }

            float f = on ? M7BMath.BuoyLightIntensity(pattern, Time.time) : 0f;
            m_Emissive.color = color * (lampEmissiveNits * f);
            m_PointLight.intensity = lightIntensityLm * f;
            m_PointLight.enabled = f > 0.01f;
        }

        // 与 NavigationLights.DestroyCollider 同坑：编辑器态须 DestroyImmediate
        static void DestroyCollider(Component collider)
        {
            if (collider == null) return;
            if (Application.isPlaying) Object.Destroy(collider);
            else Object.DestroyImmediate(collider);
        }
    }
}
