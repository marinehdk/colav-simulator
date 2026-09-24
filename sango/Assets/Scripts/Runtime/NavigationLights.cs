using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// M2-D 航行灯引擎适配器（spec #83）薄壳：OnEnable 从本船 hull 包围盒派生四灯锚点
    /// （纯核心 NavigationLightsCore，同 VesselBuoyancy 的 MeshFilter 收集法，mesh Read/Write
    /// 已由 pipeline v3 保证），建 交叉双面自发光灯片 + 小范围点光源 的运行时 rig；
    /// 每帧按 WeatherController 时刻过纯阈值函数刷明灭。昼态 = renderer+light 全禁用，
    /// 零光晕（spec 验收 5）。无新键位：状态跟随既有 T 循环/时刻滑条（spec 验收 4）。
    /// 场景重建时零序列化负担（rig 纯运行时构建，bootstrapper 只挂组件）。
    /// </summary>
    public class NavigationLights : MonoBehaviour
    {
        [Tooltip("时刻真值源（场景构建器注入；空则恒灭并告警一次）。")]
        public WeatherController weather;

        [Tooltip("编目 prefab 根烘焙的艏向修正 yaw（原生艏 → +Z；Medium=180 其余 0）。根局部空间是原生轴，锚点推导需此值映射，否则 −Z 原生艏的船会被静默镜像。")]
        public float bowYawDeg = 0f;

        [Header("Night-tuned params (recorded in evidence m2d-build-log.md)")]
        [Tooltip("舷灯/艉灯点光范围 m（场景尺度：数十米）。")]
        public float sidelightRangeM = 50f;
        [Tooltip("桅灯点光范围 m（最远可见灯）。")]
        public float mastheadRangeM = 80f;
        [Tooltip("点光强度（HDRP 点光默认单位流明）。")]
        public float sidelightIntensityLm = 300f;
        public float mastheadIntensityLm = 600f;
        public float sternIntensityLm = 200f;
        [Tooltip("灯片自发光亮度（HDR 无关值，Unlit 颜色 ×nits）。")]
        public float lampEmissiveNits = 12f;
        [Tooltip("灯片边长 = LOA × 此分数（Small ≈0.36 m / Medium ≈1.8 m）。")]
        public float lampSizeFractionOfLoa = 0.03f;
        [Header("Water streaks (R2 fallback — see Docs/lighting-notes.md)")]
        [Tooltip("假反射拖尾：HDRP Water 对本地点光的镜面响应数值上存在但不可读（R2 spike，evidence m2d-build-log.md），按 spec 落兜底。")]
        public float streakNits = 3f;
        [Tooltip("拖尾不透明度（叠加混合的 SrcAlpha）。")]
        public float streakAlpha = 0.55f;
        [Tooltip("拖尾长度 = LOA × 此分数 + 基长，钳 [4, 30] m。")]
        public float streakLengthFractionOfLoa = 0.45f;
        [Tooltip("拖尾基长 m（并入长度公式）。")]
        public float streakBaseLengthM = 3f;

        Transform m_RigRoot;          // 全部灯对象挂此子树（昼夜开关整树 SetActive）
        Transform[] m_Streaks;        // 水面拖尾（每灯一条；世界位姿逐帧朝相机拉长）
        Vector3[] m_StreakAnchors;    // 对应灯锚点（根局部）
        float[] m_StreakHalfLenM;     // 拖尾世界半长（localScale 已被根缩放换算，半长须存世界值）
        float m_WaterLocalY;          // 构建时的水面高度换算到根局部 y
        bool? m_LastLoggedState;

        const string k_RigName = "NavigationLightsRig";
        const string k_LogTag = "[Sango.M2D]";

        /// <summary>rig 是否已构建（OnEnable 失败如无 hull mesh 时为 false）。</summary>
        public bool RigBuilt => m_RigRoot != null;

        void OnEnable()
        {
            BuildRig();
            m_LastLoggedState = null; // 重启用（域重载/手动）重记一条状态行
        }

        void Update()
        {
            bool on = weather != null && NavigationLightsCore.IsLightsOn(weather.timeOfDayHours);
            ApplyState(on);
            if (on) UpdateStreaks();
        }

        /// <summary>
        /// 拖尾水面位姿（夜态每帧）：锚点跟船（TransformPoint 带浮力姿态），长轴水平对准
        /// 相机方向、从灯位向相机一侧延伸（倒影几何），法线朝上（Euler −90° 绕 X）。
        /// </summary>
        void UpdateStreaks()
        {
            var cam = Camera.main;
            if (cam == null || m_Streaks == null) return;
            var camPos = cam.transform.position;
            for (int i = 0; i < m_Streaks.Length; i++)
            {
                var anchorWorld = transform.TransformPoint(m_StreakAnchors[i]);
                var toCam = camPos - anchorWorld;
                toCam.y = 0f;
                float len = toCam.magnitude;
                if (len < 1e-3f) continue;
                toCam /= len;
                float yawDeg = Mathf.Atan2(toCam.x, toCam.z) * Mathf.Rad2Deg;
                var t = m_Streaks[i];
                float halfLen = m_StreakHalfLenM[i];
                t.SetPositionAndRotation(
                    anchorWorld + new Vector3(toCam.x, 0f, toCam.z) * halfLen,
                    Quaternion.Euler(-90f, yawDeg, 0f));
            }
        }

        // ── rig 构建 ───────────────────────────────────────────────────────────────────
        // 锚点在根局部空间（编目 prefab 艏向 +Z 已烘焙，根缩放 1），灯对象作为根子物体
        // 直接 localPosition = 锚点——船动/转艏/浮力姿态全由根 Transform 带动，零每帧同步。

        void BuildRig()
        {
            m_RigRoot = transform.Find(k_RigName);
            if (m_RigRoot != null) return; // 幂等：域重载不重建（场景对象随 play 退出自动消失）

            // hull 包围盒合并（filter局部 → 根局部），收集法同 VesselBuoyancy.OnEnable。
            var own = GetComponent<MeshFilter>();
            var filters = own != null ? new[] { own } : GetComponentsInChildren<MeshFilter>(false);
            var rootInverse = transform.worldToLocalMatrix;
            var bounds = new Bounds();
            bool any = false;
            int nullMesh = 0;
            foreach (var filter in filters)
            {
                var mesh = filter != null ? filter.sharedMesh : null;
                if (mesh == null) { nullMesh++; continue; }
                var filterToRoot = rootInverse * filter.transform.localToWorldMatrix;
                var b = mesh.bounds; // 包围盒不依赖 triangles，无需 Read/Write
                foreach (var corner in Corners(b))
                {
                    var p = filterToRoot.MultiplyPoint3x4(corner);
                    if (!any) { bounds = new Bounds(p, Vector3.zero); any = true; }
                    else bounds.Encapsulate(p);
                }
            }
            if (!any)
            {
                Debug.LogWarning($"{k_LogTag} {name}: no usable hull mesh (filters={filters.Length} nullMesh={nullMesh}) — navigation lights disabled.", this);
                enabled = false;
                return;
            }

            var layout = NavigationLightsCore.DeriveAnchors(bounds, bowYawDeg);
            float loa = bounds.size.z; // 艏向 +Z：LOA = 包围盒 z 边
            float lampSize = Mathf.Max(0.15f, loa * lampSizeFractionOfLoa);

            m_RigRoot = new GameObject(k_RigName).transform;
            m_RigRoot.SetParent(transform, false);

            // R2 兜底拖尾：贴水面的叠加混合长条，逐帧朝相机方向拉长（Update 重排世界位姿）。
            // 编目 prefab 根 transform 含烘焙统一缩放（局部单位 ≠ 米，M2-B 同坑）：
            // 世界尺寸一律经 lossyScale 换算，水面世界 y=0.25 m 反解局部 y。
            float s = Mathf.Max(transform.lossyScale.x, 1e-4f);
            m_WaterLocalY = (0.25f - transform.position.y) / s;
            var anchors = new (string name, Vector3 anchor, Color color)[]
            {
                ("PortSidelight", layout.PortSidelight, new Color(1f, 0.12f, 0.08f)),
                ("StarboardSidelight", layout.StarboardSidelight, new Color(0.15f, 1f, 0.25f)),
                ("Masthead", layout.Masthead, new Color(1f, 0.98f, 0.92f)),
                ("SternLight", layout.SternLight, new Color(1f, 0.98f, 0.92f)),
            };
            float streakLength = Mathf.Clamp(loa * streakLengthFractionOfLoa + streakBaseLengthM, 4f, 30f); // 世界 m（loa 是局部值，但比例量级一致，钳制保底）
            float streakWidth = Mathf.Max(0.5f, lampSize * 4f * s); // 世界 m = 灯片世界边长 ×4
            m_Streaks = new Transform[anchors.Length];
            m_StreakAnchors = new Vector3[anchors.Length];
            m_StreakHalfLenM = new float[anchors.Length];
            for (int i = 0; i < anchors.Length; i++)
            {
                var streak = GameObject.CreatePrimitive(PrimitiveType.Quad);
                Object.Destroy(streak.GetComponent<Collider>());
                streak.name = $"{anchors[i].name}.Streak";
                streak.transform.SetParent(m_RigRoot, false);
                streak.GetComponent<MeshRenderer>().sharedMaterial = StreakMaterial(anchors[i].color, streakNits, streakAlpha);
                m_Streaks[i] = streak.transform;
                m_StreakAnchors[i] = new Vector3(anchors[i].anchor.x, m_WaterLocalY, anchors[i].anchor.z);
                streak.transform.localScale = new Vector3(streakWidth / s, streakLength / s, 1f); // 世界米 / 根缩放
                m_StreakHalfLenM[i] = streakLength * 0.5f;
            }

            BuildLamp("PortSidelight", layout.PortSidelight, new Color(1f, 0.12f, 0.08f), lampSize, sidelightRangeM, sidelightIntensityLm);
            BuildLamp("StarboardSidelight", layout.StarboardSidelight, new Color(0.15f, 1f, 0.25f), lampSize, sidelightRangeM, sidelightIntensityLm);
            BuildLamp("Masthead", layout.Masthead, new Color(1f, 0.98f, 0.92f), lampSize, mastheadRangeM, mastheadIntensityLm);
            BuildLamp("SternLight", layout.SternLight, new Color(1f, 0.98f, 0.92f), lampSize, sidelightRangeM, sternIntensityLm);

            Debug.Log($"{k_LogTag} {name}: rig built bowYaw={bowYawDeg:0}° loa={loa:F1}m lamp={lampSize:F2}m streak={streakLength:F1}x{streakWidth:F1}m " +
                      $"port={layout.PortSidelight} stbd={layout.StarboardSidelight} mast={layout.Masthead} stern={layout.SternLight}", this);
        }

        /// <summary>
        /// HDRP/Unlit 透明叠加（additive）材质：SrcAlpha·颜色 + Dst（alpha 控制观感强度）。
        /// HDRP 17.3 Unlit 表面/混合档（Runtime/Material/Unlit/Unlit.shader + UnlitData.hlsl）：
        /// _SurfaceType=1 + _SURFACE_TYPE_TRANSPARENT、_BlendMode=2 + _BLEND_MODE_ADD，
        /// 透明渲染队列，关 ZWrite。
        /// </summary>
        static Material StreakMaterial(Color color, float nits, float alpha)
        {
            var mat = new Material(Shader.Find("HDRP/Unlit"));
            mat.SetColor("_UnlitColor", new Color(color.r * nits, color.g * nits, color.b * nits, alpha));
            mat.SetFloat("_SurfaceType", 1f);
            mat.SetFloat("_BlendMode", 2f); // HDRP BlendMode: 0 Alpha / 1 Premultiplied / 2 Additive / 3 Multiply
            mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            mat.EnableKeyword("_BLEND_MODE_ADD");
            mat.SetFloat("_SrcBlend", (float)UnityEngine.Rendering.BlendMode.SrcAlpha);
            mat.SetFloat("_DstBlend", (float)UnityEngine.Rendering.BlendMode.One);
            mat.SetFloat("_ZWrite", 0f);
            mat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            return mat;
        }

        void BuildLamp(string lampName, Vector3 localAnchor, Color color, float size, float rangeM, float intensityLm)
        {
            var lamp = new GameObject(lampName).transform;
            lamp.SetParent(m_RigRoot, false);
            lamp.localPosition = localAnchor;

            // 灯片：交叉双面十字（0°/90°），水平全向可读，免 billboard/双面材质 shader 折腾。
            var mat = new Material(Shader.Find("HDRP/Unlit")) { color = color * lampEmissiveNits };
            for (int i = 0; i < 2; i++)
            {
                var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
                Object.Destroy(quad.GetComponent<Collider>()); // 灯片非碰撞体
                quad.name = $"{lampName}.Quad{i}";
                quad.transform.SetParent(lamp, false);
                quad.transform.localPosition = Vector3.zero;
                quad.transform.localRotation = Quaternion.Euler(0f, i * 90f, 0f);
                quad.transform.localScale = new Vector3(size, size, 1f);
                quad.GetComponent<MeshRenderer>().sharedMaterial = mat;
            }

            // 点光：HDRP 本地光（水面对其镜面反射 = R2 spike 对象），无阴影（4 灯×2 船 廉价）。
            var lightGo = new GameObject($"{lampName}.Light");
            lightGo.transform.SetParent(lamp, false);
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Point;
            light.color = color;
            light.range = rangeM;
            light.intensity = intensityLm; // HDRP 点光默认单位流明
            light.shadows = LightShadows.None;
            lightGo.AddComponent<HDAdditionalLightData>();
        }

        static IEnumerable<Vector3> Corners(Bounds b)
        {
            for (int xi = 0; xi < 2; xi++)
            for (int yi = 0; yi < 2; yi++)
            for (int zi = 0; zi < 2; zi++)
            {
                yield return new Vector3(
                    xi == 0 ? b.min.x : b.max.x,
                    yi == 0 ? b.min.y : b.max.y,
                    zi == 0 ? b.min.z : b.max.z);
            }
        }

        // ── 昼夜状态 ───────────────────────────────────────────────────────────────────

        void ApplyState(bool on)
        {
            if (m_RigRoot == null) return;
            if (m_LastLoggedState != on) // 仅翻转/首帧记行（真机夜态烟测的日志证据）
            {
                float h = weather != null ? weather.timeOfDayHours : -1f;
                Debug.Log($"{k_LogTag} {name}: navigation lights {(on ? "ON" : "OFF")} at h={h:F1}");
                m_LastLoggedState = on;
            }
            if (m_RigRoot.gameObject.activeSelf == on) return;
            m_RigRoot.gameObject.SetActive(on); // 整树开关 = 灯片不画、点光不参与，昼态零光晕
        }
    }
}
