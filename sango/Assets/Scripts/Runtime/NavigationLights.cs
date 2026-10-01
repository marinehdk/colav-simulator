using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// M2-D 航行灯引擎适配器（spec #83）薄壳：OnEnable 从本船 hull 包围盒派生四灯锚点
    /// （纯核心 NavigationLightsCore，同 VesselBuoyancy 的 MeshFilter 收集法，mesh Read/Write
    /// 已由 pipeline v3 保证），建 圆形双面自发光灯片 + 小范围点光源 的运行时 rig；
    /// 每帧按 WeatherController 时刻过纯阈值函数刷明灭。昼态 = renderer+light 全禁用，
    /// 零光晕（spec 验收 5）。无新键位：状态跟随既有 T 循环/时刻滑条（spec 验收 4）。
    /// 场景重建时零序列化负担（rig 纯运行时构建，bootstrapper 只挂组件）。
    /// M4-B（issue #87 批次 B 项 3）：夜态另按 Rule 21 光弧纯函数
    /// NavigationLightsCore.SectorIntensity 驱动三型四灯的角向分布（观察者=主相机的
    /// 相对方位）：弧外灯片隐藏+点光归零，Annex I 1°-3° 过渡带内线性衰减。
    /// 假反射 streak 与灯色不变（只改角向分布）。
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
        [Tooltip("灯片世界边长 = LOA × 此分数，钳在 0.14–0.28 m。")]
        public float lampSizeFractionOfLoa = 0.004f;
        [Header("Water streaks (R2 fallback — see Docs/lighting-notes.md)")]
        [Tooltip("假反射拖尾：HDRP Water 对本地点光的镜面响应数值上存在但不可读（R2 spike，evidence m2d-build-log.md），按 spec 落兜底。")]
        public float streakNits = 3f;
        [Tooltip("拖尾不透明度（叠加混合的 SrcAlpha）。")]
        public float streakAlpha = 0.55f;
        [Tooltip("拖尾长度 = LOA × 此分数 + 基长，钳 [4, 30] m。")]
        public float streakLengthFractionOfLoa = 0.45f;
        [Tooltip("拖尾基长 m（并入长度公式）。")]
        public float streakBaseLengthM = 3f;
        [Header("COLREG sector arcs (M4-B — Rule 21 / Annex I)")]
        [Tooltip("扇区边界过渡带（度）：Annex I §9 允许 1-3°，默认 3 = 最柔合法过渡。")]
        public float sectorFalloffDeg = NavigationLightsCore.SectorFalloffDeg;

        Transform m_RigRoot;          // 全部灯对象挂此子树（昼夜开关整树 SetActive）
        Transform[] m_Streaks;        // 水面拖尾（每灯一条；世界位姿逐帧朝相机拉长）
        Vector3[] m_StreakAnchors;    // 对应灯锚点（根局部）
        float[] m_StreakHalfLenM;     // 拖尾世界半长（localScale 已被根缩放换算，半长须存世界值）
        float m_WaterLocalY;          // 构建时的水面高度换算到根局部 y
        bool? m_LastLoggedState;
        bool m_WarnedNoWeather;       // weather 缺失一次性告警（OnEnable 重置）

        // M4-B 光弧驱动：每灯注册（自发光材质/点光/灯片渲染器）+ 最近一次扇区因子。
        struct LampEntry
        {
            public LampKind Kind;
            public Color BaseColor;
            public float BaseLumens;
            public Material Emissive;     // 圆形双面灯片材质
            public Light PointLight;
            public MeshRenderer[] Quads;  // 灯片渲染器（弧外整片隐藏，防黑点残影）
        }
        readonly System.Collections.Generic.List<LampEntry> m_Lamps = new System.Collections.Generic.List<LampEntry>();
        readonly List<Material> m_OwnedMaterials = new List<Material>(8);
        float[] m_LastSectorFactors;

        const string k_RigName = "NavigationLightsRig";
        const string k_LogTag = "[Sango.M2D]";

        /// <summary>rig 是否已构建（OnEnable 失败如无 hull mesh 时为 false）。</summary>
        public bool RigBuilt => m_RigRoot != null;

        void OnEnable()
        {
            BuildRig();
            m_LastLoggedState = null; // 重启用（域重载/手动）重记一条状态行
            m_WarnedNoWeather = false;
        }

        void OnDestroy()
        {
            foreach (var material in m_OwnedMaterials)
                if (material != null)
                {
                    if (Application.isPlaying) Destroy(material); else DestroyImmediate(material);
                }
            m_OwnedMaterials.Clear();
        }

        void Update()
        {
            if (weather == null)
            {
                if (!m_WarnedNoWeather) // 一次性告警（同 hull-mesh 缺失告警模式），不刷屏
                {
                    m_WarnedNoWeather = true;
                    Debug.LogWarning($"{k_LogTag} {name}: no WeatherController injected — navigation lights stay off (day semantics).", this);
                }
                ApplyState(false);
                return;
            }
            bool on = NavigationLightsCore.IsLightsOn(weather.timeOfDayHours);
            ApplyState(on);
            if (on)
            {
                UpdateStreaks();
                // M4-B：观察者（主相机）相对方位 → Rule 21 光弧衰减。无相机（headless/
                // 采集场景）保持全强度：角向分布只服务于"看灯的人"。
                var cam = Camera.main;
                if (cam != null) ApplyObservationBearing(ObserverRelativeBearing(cam.transform.position));
            }
        }

        /// <summary>
        /// 观察者在艏舷角坐标（0=正艏，顺时针=右舷正，[0,360)）的相对方位：船渲染艏向
        /// （root.rotation × 原生艏向量，同 M1SceneBootstrapper 放置自证的映射）到
        /// 船→观察者水平向量的带符号角。
        /// </summary>
        float ObserverRelativeBearing(Vector3 observerWorldPos)
        {
            // native = R(−bowYawDeg)·(0,0,1)（NavigationLightsCore.DeriveAnchors 同约定）：
            // 只写 z 分量会在 yaw=±90° 退化成零向量；编目现仅 0/180（sinθ=0）故历史路径无恙。
            var yawRad = bowYawDeg * Mathf.Deg2Rad;
            var nativeBow = new Vector3(-Mathf.Sin(yawRad), 0f, Mathf.Cos(yawRad));
            var bow = transform.rotation * nativeBow;
            var toObserver = observerWorldPos - transform.position;
            toObserver.y = 0f;
            float signed = Vector3.SignedAngle(bow, toObserver, Vector3.up); // + = 观察者在右舷
            return Mathf.Repeat(signed, 360f);
        }

        /// <summary>
        /// 按相对方位刷四灯角向分布（公开 = EditMode 可测缝）：弧内因子 1（灯片显示、点光
        /// 基准强度），过渡带内线性衰减（自发光/点光同乘因子），弧外灯片整片隐藏、点光归零。
        /// 只改强度/可见性，灯色、点光范围、假反射 streak 均不变。
        /// </summary>
        public void ApplyObservationBearing(float relBearingDeg)
        {
            if (LampsNotRegistered()) return;
            for (int i = 0; i < m_Lamps.Count; i++)
            {
                var lamp = m_Lamps[i];
                var (start, end) = NavigationLightsCore.GetArc(lamp.Kind);
                float f = NavigationLightsCore.SectorIntensity(relBearingDeg, start, end, sectorFalloffDeg);
                m_LastSectorFactors[i] = f;
                lamp.Emissive.SetColor("_UnlitColor", new Color(lamp.BaseColor.r * lampEmissiveNits * f,
                    lamp.BaseColor.g * lampEmissiveNits * f, lamp.BaseColor.b * lampEmissiveNits * f, 1f));
                lamp.PointLight.intensity = lamp.BaseLumens * f;
                bool visible = f > 0.02f;
                lamp.PointLight.enabled = f > 0.01f;
                var quads = lamp.Quads;
                for (int q = 0; q < quads.Length; q++)
                {
                    quads[q].enabled = visible;
                    var cam = Camera.main;
                    if (cam != null)
                        quads[q].transform.rotation = Quaternion.LookRotation(cam.transform.position - quads[q].transform.position, Vector3.up);
                }
            }
        }

        /// <summary>最近一次 ApplyObservationBearing 给该灯的扇区因子 ∈ [0,1]（测试/观测口）。</summary>
        public float LastLampFactor01(LampKind kind)
        {
            if (LampsNotRegistered()) return -1f;
            for (int i = 0; i < m_Lamps.Count; i++)
            {
                if (m_Lamps[i].Kind == kind) return m_LastSectorFactors[i];
            }
            return -1f;
        }

        bool LampsNotRegistered()
        {
            return m_Lamps == null || m_Lamps.Count == 0 || m_LastSectorFactors == null || m_LastSectorFactors.Length != m_Lamps.Count;
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
                anchorWorld.y = 0.035f;
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
            float rootScale = Mathf.Max(transform.lossyScale.x, 1e-4f);
            float lampSize = Mathf.Clamp(loa * rootScale * lampSizeFractionOfLoa, 0.14f, 0.28f) / rootScale;

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
                DestroyCollider(streak.GetComponent<Collider>());
                streak.name = $"{anchors[i].name}.Streak";
                streak.transform.SetParent(m_RigRoot, false);
                var streakMaterial = StreakMaterial(anchors[i].color, streakNits, streakAlpha);
                m_OwnedMaterials.Add(streakMaterial);
                streak.GetComponent<MeshRenderer>().sharedMaterial = streakMaterial;
                m_Streaks[i] = streak.transform;
                m_StreakAnchors[i] = new Vector3(anchors[i].anchor.x, m_WaterLocalY, anchors[i].anchor.z);
                streak.transform.localScale = new Vector3(streakWidth / s, streakLength / s, 1f); // 世界米 / 根缩放
                m_StreakHalfLenM[i] = streakLength * 0.5f;
            }

            BuildLamp(LampKind.PortSidelight, "PortSidelight", layout.PortSidelight, new Color(1f, 0.12f, 0.08f), lampSize, sidelightRangeM, sidelightIntensityLm);
            BuildLamp(LampKind.StarboardSidelight, "StarboardSidelight", layout.StarboardSidelight, new Color(0.15f, 1f, 0.25f), lampSize, sidelightRangeM, sidelightIntensityLm);
            BuildLamp(LampKind.Masthead, "Masthead", layout.Masthead, new Color(1f, 0.98f, 0.92f), lampSize, mastheadRangeM, mastheadIntensityLm);
            BuildLamp(LampKind.SternLight, "SternLight", layout.SternLight, new Color(1f, 0.98f, 0.92f), lampSize, sidelightRangeM, sternIntensityLm);
            m_LastSectorFactors = new float[m_Lamps.Count];

            // M7 review L1：单位口径标注——loa/port/stbd/mast/stern 为网格根局部原生单位，
            // ×根缩放 = 世界米（防 937.8 误读成米；FcbHoubei 实际 ×0.0448 ≈ 42 m）。
            Debug.Log($"{k_LogTag} {name}: rig built bowYaw={bowYawDeg:0}° loa={loa:F1} (mesh-local units ×root scale {s:F4} = {loa * s:F1} m world) " +
                      $"lamp={lampSize:F2}m streak={streakLength:F1}x{streakWidth:F1}m " +
                      $"port={layout.PortSidelight} stbd={layout.StarboardSidelight} mast={layout.Masthead} stern={layout.SternLight} (anchors mesh-local units)", this);
        }

        /// <summary>
        /// HDRP/Unlit 透明叠加（additive）材质：SrcAlpha·颜色 + Dst（alpha 控制观感强度）。
        /// HDRP 17.3 Unlit 表面/混合档（Runtime/Material/Unlit/Unlit.shader + UnlitData.hlsl）：
        /// _SurfaceType=1 + _SURFACE_TYPE_TRANSPARENT、_BlendMode=2 + _BLEND_MODE_ADD，
        /// 透明渲染队列，关 ZWrite。
        /// </summary>
        static Material StreakMaterial(Color color, float nits, float alpha)
        {
            var prototype = Resources.Load<Material>("SurfaceFoam");
            var mat = prototype != null ? new Material(prototype) : new Material(Shader.Find("HDRP/Unlit"));
            mat.SetTexture("_UnlitColorMap", WakeFoamTexture.WakeStrip());
            mat.SetColor("_UnlitColor", new Color(color.r * nits, color.g * nits, color.b * nits, alpha));
            mat.SetFloat("_SurfaceType", 1f);
            mat.SetFloat("_BlendMode", 2f); // HDRP BlendMode: 0 Alpha / 1 Premultiplied / 2 Additive / 3 Multiply
            mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            mat.EnableKeyword("_BLEND_MODE_ADD");
            mat.SetFloat("_SrcBlend", (float)UnityEngine.Rendering.BlendMode.SrcAlpha);
            mat.SetFloat("_DstBlend", (float)UnityEngine.Rendering.BlendMode.One);
            mat.SetFloat("_ZWrite", 0f);
            mat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            HDMaterial.ValidateMaterial(mat);
            mat.SetShaderPassEnabled("DepthForwardOnly", false);
            mat.SetShaderPassEnabled("MotionVectors", false);
            return mat;
        }

        void BuildLamp(LampKind kind, string lampName, Vector3 localAnchor, Color color, float size, float rangeM, float intensityLm)
        {
            var lamp = new GameObject(lampName).transform;
            lamp.SetParent(m_RigRoot, false);
            lamp.localPosition = localAnchor;

            // Circular, physical-sized light aperture. RGB carries radiance; alpha never gets multiplied by nits.
            var mat = StreakMaterial(color, lampEmissiveNits, 1f);
            m_OwnedMaterials.Add(mat);
            mat.SetTexture("_UnlitColorMap", LampSpotTexture.GetShared());
            mat.SetFloat("_CullMode", 0f);
            mat.SetFloat("_CullModeForward", 0f);
            mat.SetFloat("_DoubleSidedEnable", 1f);
            mat.EnableKeyword("_DOUBLESIDED_ON");
            HDMaterial.ValidateMaterial(mat);
            mat.SetShaderPassEnabled("DepthForwardOnly", false);
            mat.SetShaderPassEnabled("MotionVectors", false);
            var quads = new MeshRenderer[1];
            for (int i = 0; i < 1; i++)
            {
                var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
                DestroyCollider(quad.GetComponent<Collider>()); // 灯片非碰撞体
                quad.name = $"{lampName}.Quad{i}";
                quad.transform.SetParent(lamp, false);
                quad.transform.localPosition = Vector3.zero;
                quad.transform.localRotation = Quaternion.Euler(0f, i * 90f, 0f);
                quad.transform.localScale = new Vector3(size, size, 1f);
                quads[i] = quad.GetComponent<MeshRenderer>();
                quads[i].sharedMaterial = mat;
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

            // M4-B：登记光弧驱动句柄（角向分布每帧由 ApplyObservationBearing 刷）。
            m_Lamps.Add(new LampEntry
            {
                Kind = kind,
                BaseColor = color,
                BaseLumens = intensityLm,
                Emissive = mat,
                PointLight = light,
                Quads = quads,
            });
        }

        /// <summary>
        /// 去 Collider：Play 用延迟 Destroy（批末合并），EditMode（BuildRig 可被测试直调）
        /// 用 DestroyImmediate——Object.Destroy 在编辑器态会记 "may not be called from edit
        /// mode" 错误并使 EditMode 测试红（UTF 对 LogError 默认判失败）。
        /// </summary>
        static void DestroyCollider(Component collider)
        {
            if (collider == null) return;
            if (Application.isPlaying) Object.Destroy(collider);
            else Object.DestroyImmediate(collider);
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
