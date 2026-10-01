using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// M4-B 水线工艺引擎适配器薄壳（issue #87 批次 B 项 1/4）：两块 HDRP DecalProjector
    /// （mesh decal，非 WaterDecal）以船体包围盒定尺寸，投影到船壳上——
    ///   ① 湿感带：自作竖向渐变贴图（上透明下湿），影响 BaseColor+Smoothness，带顶 y 每帧
    ///      由纯核心 HullWaterlineCore.WetBandUpperOffsetM 驱动（复用 VesselBuoyancy 既有
    ///      CPU 水高查询的解算结果 target−smoothed heave，零新增水面查询，H2 纪律）；
    ///   ② boot top 静态暗红防污带：设计吃水线上缘向上，高 = BootTopBandHeightM 钳型深。
    /// 轴向契约（HDRP 17.3 源码钉死）：DecalProjector 纹理 U=局部 X、V=局部 +Y、深度=局部 Z
    /// （DecalProjectorEditor.cs:168 盒手柄 X|Y 平面；DecalSystem.Jobs.cs resolveDecalSize
    /// (x,z,y) 换轴 + resolveRotation Rx(−90°)）——恒等本地旋转下 V 即根局部竖直轴（yaw-only
    /// 根 → 世界竖直），竖向渐变直接映射为水平湿带，U 无关（渐变沿 U 恒定）。
    /// 贴图/材质运行时生成（同 NavigationLights rig 纪律：零序列化资产、场景重建零负担）。
    /// </summary>
    [DefaultExecutionOrder(120)] // VesselBuoyancy(100) 之后：读其当帧已平滑的 heave
    public class HullWaterlineDecals : MonoBehaviour
    {
        [Tooltip("浮力姿态真值源：湿带偏移 = buoyancy.TargetAttitude.y − SmoothedAttitude.y（水面相对船体的高度）。空 = 静水偏移 0。")]
        public VesselBuoyancy buoyancy;

        [Header("Wetness band")]
        [Tooltip("湿带投影盒高（米）：盒顶 = 当前水面，盒内上 ~40% 渐变到透明。")]
        public float wetBandHeightM = 1.2f;

        [Tooltip("湿面反照率（暗化色）。")]
        public Color wetAlbedo = new Color(0.13f, 0.16f, 0.20f);

        [Tooltip("湿面 smoothness（无 MaskMap 时的标量通道，DBuffer 直接替换目标值）。")]
        [Range(0f, 1f)] public float wetSmoothness = 0.9f;

        [Tooltip("湿感总强度（HDRP _DecalBlend）。")]
        [Range(0f, 1f)] public float wetBlend = 0.85f;

        [Header("Boot top band (static)")]
        [Tooltip("boot top 暗红带高（米，钳到设计水线以上型深）：0 = 不铺。")]
        public float bootTopBandHeightM = 0.8f;

        [Tooltip("防污漆暗红色。")]
        public Color bootTopColor = new Color(0.42f, 0.10f, 0.08f);

        [Tooltip("boot top 不透明度（_DecalBlend）。")]
        [Range(0f, 1f)] public float bootTopBlend = 0.95f;

        const string k_LogTag = "[Sango.M4B]";
        const int k_TexWidth = 4;
        const int k_TexHeight = 64;

        Transform m_RigRoot;
        DecalProjector m_Wetness;
        DecalProjector m_BootTop;
        Material m_WetMat, m_BootMat;
        Texture2D m_WetTex, m_BootTex;
        float m_DesignRootWorldY; // 构建时根世界 y（设计吃水位姿，静水 y=0）
        float m_WaterlineLocalY;  // 设计水线在根局部的 y（模型单位）
        float m_LossyScale = 1f;
        float m_DraftM, m_FreeboardM; // 设计水线到包围盒底/顶（米；顶含桅等上层建筑——只作退化钳制界）
        float m_LastWetOffsetM;

        /// <summary>rig 是否已构建。</summary>
        public bool RigBuilt => m_RigRoot != null;
        /// <summary>湿感投影器（测试/实机观测口）。</summary>
        public DecalProjector WetnessProjector => m_Wetness;
        /// <summary>boot top 投影器（未铺 = null）。</summary>
        public DecalProjector BootTopProjector => m_BootTop;
        /// <summary>最近一次 WetBandUpperOffsetM 输出（米）。</summary>
        public float LastWetOffsetM => m_LastWetOffsetM;
        /// <summary>设计水线到包围盒底（米）。</summary>
        public float DraftM => m_DraftM;
        /// <summary>设计水线到包围盒顶（米，含上层建筑）。</summary>
        public float FreeboardM => m_FreeboardM;

        void OnEnable()
        {
            BuildProjectors();
        }

        void OnDestroy()
        {
            if (m_WetMat != null) Destroy(m_WetMat);
            if (m_BootMat != null) Destroy(m_BootMat);
            if (m_WetTex != null) Destroy(m_WetTex);
            if (m_BootTex != null) Destroy(m_BootTex);
        }

        void LateUpdate()
        {
            // 水面相对船体的高度（米）= 目标平均水面高 − 船体已平滑升沉（两者都由 VesselBuoyancy
            // 的既有 CPU 水高查询产生，本组件零新增查询）。查询全废（batchmode 等）时两者同为 0。
            float excursion = buoyancy != null
                ? buoyancy.TargetAttitude.x - buoyancy.SmoothedAttitude.x
                : 0f;
            ApplyWaterExcursion(excursion);
        }

        /// <summary>
        /// 以"水面相对设计水线的高度（米）"驱动湿带（公开 = EditMode 可测缝，先例
        /// BoatWaterDecals.ApplySpeed）：偏移经纯核心钳型深后写投影器局部 y。
        /// </summary>
        public void ApplyWaterExcursion(float waterHeightAboveDesignM)
        {
            if (m_Wetness == null) return;
            m_LastWetOffsetM = HullWaterlineCore.WetBandUpperOffsetM(waterHeightAboveDesignM, 0f, m_DraftM, m_FreeboardM);
            float localY = m_WaterlineLocalY + (m_LastWetOffsetM + wetBandHeightM * 0.5f) / m_LossyScale;
            m_Wetness.transform.localPosition = new Vector3(m_Wetness.transform.localPosition.x, localY, m_Wetness.transform.localPosition.z);
        }

        // ── rig 构建（幂等）─────────────────────────────────────────────────────

        /// <summary>
        /// 收集船体包围盒（收集法同 NavigationLights，包络不依赖 mesh Read/Write）→ 派生
        /// 水线/吃水/干舷 → 建两块 DecalProjector。设计位姿假设：构建时船在设计吃水
        /// （静水世界 y=0），同 VesselBuoyancy.OnEnable 的基线捕获。
        /// </summary>
        public void BuildProjectors()
        {
            if (m_RigRoot != null) return; // 幂等：域重载不重建

            // M9 守卫：播放器构建里 HDRP/Decal 若未被任何资产引用会被 strip（Shader.Find=null），
            // new Material(null) 每帧 ArgumentNullException（实机 Player.log 51-58 实证）。
            // 湿感/boot-top 贴花属观感件，缺失时整组件干净降级，编辑器态不受影响。
            if (Shader.Find("HDRP/Decal") == null)
            {
                Debug.LogWarning($"{k_LogTag} {name}: HDRP/Decal shader not in build — waterline decals disabled (player build strip).", this);
                enabled = false;
                return;
            }

            var bounds = CollectHullBounds();
            if (!bounds.HasValue)
            {
                Debug.LogWarning($"{k_LogTag} {name}: no usable hull mesh — waterline decals disabled.", this);
                enabled = false;
                return;
            }
            var b = bounds.Value;

            m_LossyScale = Mathf.Max(transform.lossyScale.y, 1e-4f); // 烘焙统一缩放：局部单位 × s = 米
            m_DesignRootWorldY = transform.position.y;
            m_WaterlineLocalY = (0f - m_DesignRootWorldY) / m_LossyScale;
            m_DraftM = -(m_DesignRootWorldY + b.min.y * m_LossyScale);       // 设计水线(0) 到盒底
            m_FreeboardM = m_DesignRootWorldY + b.max.y * m_LossyScale;      // 设计水线 到 盒顶（含桅）

            m_RigRoot = new GameObject("WaterlineDecalsRig").transform;
            m_RigRoot.SetParent(transform, false);

            float coverX = b.size.x * m_LossyScale * 1.25f + 0.2f; // 投影盒水平余量：盖满船宽/LOA
            float coverZ = b.size.z * m_LossyScale * 1.15f + 0.2f;

            // ① 湿感带（动态 y，见 ApplyWaterExcursion）。
            m_WetTex = MakeWetnessGradient(wetAlbedo);
            m_WetMat = MakeDecalMaterial(m_WetTex, wetBlend, affectSmoothness: true, wetSmoothness, drawOrder: 1);
            m_Wetness = CreateProjector("Wetness Decal", new Vector3(coverX, wetBandHeightM, coverZ),
                m_WaterlineLocalY + wetBandHeightM * 0.5f / m_LossyScale, b, m_WetMat);

            // ② boot top 静态暗红带：设计吃水线上缘向上，高钳型深。
            float bandH = HullWaterlineCore.BootTopBandHeightM(bootTopBandHeightM, m_FreeboardM);
            if (bandH > 0.05f)
            {
                m_BootTex = MakeBootTopBand(bootTopColor);
                m_BootMat = MakeDecalMaterial(m_BootTex, bootTopBlend, affectSmoothness: false, 0f, drawOrder: 0);
                m_BootTop = CreateProjector("Boot Top Decal", new Vector3(coverX, bandH, coverZ),
                    m_WaterlineLocalY + bandH * 0.5f / m_LossyScale, b, m_BootMat);
            }

            Debug.Log($"{k_LogTag} {name}: waterline decals built — wetness band {wetBandHeightM:F1} m (smoothness {wetSmoothness:0.00}) " +
                      $"+ boot top {(m_BootTop != null ? $"{bandH:F2} m" : "skipped")}, waterline local y={m_WaterlineLocalY:F2}, " +
                      $"draft {m_DraftM:F2} m / freeboard(guard) {m_FreeboardM:F2} m", this);
        }

        DecalProjector CreateProjector(string goName, Vector3 sizeM, float localY, Bounds b, Material mat)
        {
            var go = new GameObject(goName);
            go.transform.SetParent(m_RigRoot, false);
            go.transform.localPosition = new Vector3(b.center.x, localY, b.center.z);
            go.transform.localRotation = Quaternion.identity; // V=根局部+Y（竖向渐变），深度=根局部 Z（艏艉向）
            var decal = go.AddComponent<DecalProjector>();
            decal.material = mat;
            decal.scaleMode = DecalScaleMode.ScaleInvariant; // size 即米，不被 prefab 根烘焙缩放放大（WaterDecal 同款）
            decal.size = sizeM;
            decal.pivot = Vector3.zero; // 盒中心 = transform 位（V 顶 = localY + size.y/2）
            return decal;
        }

        Bounds? CollectHullBounds()
        {
            var own = GetComponent<MeshFilter>();
            var filters = own != null ? new[] { own } : GetComponentsInChildren<MeshFilter>(false);
            var rootInverse = transform.worldToLocalMatrix;
            var bounds = new Bounds();
            bool any = false;
            foreach (var filter in filters)
            {
                var mesh = filter != null ? filter.sharedMesh : null;
                if (mesh == null) continue;
                bool effectMesh = false;
                for (var parent = filter.transform; parent != null && parent != transform; parent = parent.parent)
                    if (parent.name == "NavigationLightsRig" || parent.name == "WakeFoamRig" || parent.name == "WaterlineDecalsRig")
                    { effectMesh = true; break; }
                if (effectMesh) continue;
                var filterToRoot = rootInverse * filter.transform.localToWorldMatrix;
                var bb = mesh.bounds; // 包围盒不依赖 triangles，无需 Read/Write
                for (int xi = 0; xi < 2; xi++)
                for (int yi = 0; yi < 2; yi++)
                for (int zi = 0; zi < 2; zi++)
                {
                    var p = filterToRoot.MultiplyPoint3x4(new Vector3(
                        xi == 0 ? bb.min.x : bb.max.x,
                        yi == 0 ? bb.min.y : bb.max.y,
                        zi == 0 ? bb.min.z : bb.max.z));
                    if (!any) { bounds = new Bounds(p, Vector3.zero); any = true; }
                    else bounds.Encapsulate(p);
                }
            }
            return any ? bounds : (Bounds?)null;
        }

        // ── 运行时贴图/材质（同 NavigationLights.StreakMaterial 纪律：Shader.Find + 直制）──

        /// <summary>
        /// 湿感渐变（sRGB，4×64）：底行(v=0)全湿 → 顶 40% 平滑衰减到全透明。
        /// v=1 映射投影盒顶（= 当前水面），透明沿 v 升高而上移 = "上透明下湿"。
        /// </summary>
        static Texture2D MakeWetnessGradient(Color wet)
        {
            var tex = NewDecalTexture();
            var px = new Color[k_TexWidth * k_TexHeight];
            for (int y = 0; y < k_TexHeight; y++)
            {
                float v = y / (float)(k_TexHeight - 1); // v=0 盒底 → 1 盒顶
                float a = 1f - SmoothStep(0.6f, 1f, v);
                var c = new Color(wet.r, wet.g, wet.b, a);
                for (int x = 0; x < k_TexWidth; x++) px[y * k_TexWidth + x] = c;
            }
            tex.SetPixels(px);
            tex.Apply(false, true);
            return tex;
        }

        /// <summary>boot top 红带（sRGB，4×64）：上下 5-8% 行软边，中间实色（漆线柔和但基本清晰）。</summary>
        static Texture2D MakeBootTopBand(Color red)
        {
            var tex = NewDecalTexture();
            var px = new Color[k_TexWidth * k_TexHeight];
            for (int y = 0; y < k_TexHeight; y++)
            {
                float v = y / (float)(k_TexHeight - 1);
                float a = SmoothStep(0f, 0.05f, v) * (1f - SmoothStep(0.90f, 0.98f, v));
                var c = new Color(red.r, red.g, red.b, a);
                for (int x = 0; x < k_TexWidth; x++) px[y * k_TexWidth + x] = c;
            }
            tex.SetPixels(px);
            tex.Apply(false, true);
            return tex;
        }

        static Texture2D NewDecalTexture()
        {
            var tex = new Texture2D(k_TexWidth, k_TexHeight, TextureFormat.RGBA32, false, false);
            tex.wrapMode = TextureWrapMode.Clamp;
            tex.filterMode = FilterMode.Bilinear;
            return tex;
        }

        /// <summary>
        /// HDRP/Decal 材质（Decal.shader 属性面见 PKG Runtime/Material/Decal/Decal.shader:5-46；
        /// 影响通道读材质浮点，无关键字要求——DecalSystem.InitializeMaterialValues GetFloat 路径）：
        /// 只影响 BaseColor（+可选 Smoothness 标量，无 MaskMap 时 _Smoothness 直用，
        /// DecalSystem.cs:607），法线/AO/金属恒不影响（湿面不改材质结构）。
        /// </summary>
        static Material MakeDecalMaterial(Texture2D map, float blend, bool affectSmoothness, float smoothness, int drawOrder)
        {
            var template = Resources.Load<Material>("WaterlineDecal");
            var mat = template != null ? new Material(template) : new Material(Shader.Find("HDRP/Decal"));
            mat.enableInstancing = true; // HDRP DecalSystem.RenderIntoDBuffer 无条件走 DrawMeshInstanced
                                         // （DecalSystem.cs:1116，单实例也走）——不开启 = DBuffer 抛
                                         // InvalidOperationException、整帧 RenderGraph 中止（黑帧）。
                                         // M4_BowWave/M4_WakeFoam 资产侧同修（M8-B 批）。
            mat.SetTexture("_BaseColorMap", map);
            mat.SetColor("_BaseColor", Color.white);
            mat.SetFloat("_DecalBlend", blend);
            mat.SetFloat("_AffectAlbedo", 1f);
            mat.SetFloat("_AffectNormal", 0f);
            mat.SetFloat("_AffectAO", 0f);
            mat.SetFloat("_AffectMetal", 0f);
            mat.SetFloat("_AffectSmoothness", affectSmoothness ? 1f : 0f);
            mat.SetFloat("_Smoothness", smoothness);
            mat.SetFloat("_DrawOrder", drawOrder);
            HDMaterial.ValidateMaterial(mat);
            return mat;
        }

        static float SmoothStep(float a, float b, float t)
        {
            float x = Mathf.Clamp01((t - a) / (b - a));
            return x * x * (3f - 2f * x);
        }
    }
}
