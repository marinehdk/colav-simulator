using System.Collections.Generic;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// Stage-one visual wake: world-space propeller wash plus diverging Kelvin-envelope arms,
    /// small bow spray and a water-conforming hull foam ring. It is not a CFD/resistance model.
    /// High uses scene-lit transparent foam; Low retains the existing WaterDecal speed gate.
    /// Budget: 128×6 ribbon vertices / 762 triangles, 48 ring vertices / 48 triangles,
    /// <=144 spray particles. Moving High performs at most 817 water queries per update;
    /// stopped/Low performs none. LastWaterQueries exposes the real budget for acceptance.
    /// Vertex buffers and sampling history are reused; owned Mesh/Material objects are released.
    /// </summary>
    [DefaultExecutionOrder(200)] // 晚于 VesselBuoyancy(100)：采样/环 y 用本帧浮力后位姿
    public class WakeFoamRig : MonoBehaviour
    {
        [Tooltip("航速真值来源（G 键 demo 同一真值；空则恒 0 = 零发射）。")]
        public WaypointFollower follower;

        [Tooltip("HDRP Water Surface（水高查询；空则退化为 y=0 静水面）。")]
        public WaterSurface water;

        [Tooltip("Low 档 decal 适配器（High 档被本组件压制；空则跳过压制）。")]
        public BoatWaterDecals decals;

        [Tooltip("船长 LOA（米，世界尺度，编目值）：Froude 分母与 ribbon/采样几何的尺度源。")]
        public float loaMeters = 12f;

        [Tooltip("启用阈值（m/s）：与 BoatWaterDecals.speedThresholdMps 同值同语义（复用 WaterDecalSpeedGate 谓词）。")]
        public float speedThresholdMps = 0.5f;

        [Tooltip("全强航速（m/s）：速度爬坡到此为 1（与 decal 门同锚）。")]
        public float fullEffectSpeedMps = 5f;

        [Tooltip("强度乘子 ∈ [0,1]（Simulation 面板尾迹滑条实时驱动；High/Low 两档共用一个滑条）。")]
        public float intensityMultiplier = 1f;

        // ── 预算常量（头注"预算"节的代码锚；粒子总量 = 2 × PerSide）──────────────────
        public const int MaxSprayParticlesPerSide = 72; // ≥ 55/s × 1.1 s 寿命，满发不饿死
        public const float MaxSprayRatePerSide = 55f;   // 粒子/秒·侧（巡航满发活粒子 ~60/侧）

        const string k_RigName = "WakeFoamRig";             // 船子树（喷口 + 水线环）
        const string k_WorldRootName = "WakeFoam.World";    // 场景根子树（世界系 ribbon）
        const string k_RibbonName = "WakeRibbon";
        const string k_RingName = "WaterlineFoamRing";
        const string k_LogTag = "[Sango.M9]";
        const float k_SurfaceWorldY = 0.06f;   // 泡沫层基线世界高度（水面微上方防 z-fight）
        const float k_RibbonTailWidth = 0.22f; // 尾端宽度收窄比例（艉柱处 1）
        const int k_RingSegments = 24;         // 水线环分段（48 顶点拓扑静态）
        const float k_TeleportResetFactor = 12f; // 单帧位移超此倍数采样距 = 传送，重置历史

        // ── 构建态（全部构建期分配；Update 路径零 new）────────────────────────────────
        Transform m_RigRoot;
        Transform m_WorldRoot;
        Transform m_Ring;
        Mesh m_RibbonMesh;
        MeshRenderer m_RibbonRenderer;
        MeshRenderer m_RingRenderer;
        Mesh m_RingMesh;
        Vector3[] m_RingBaseVertices, m_RingVertexCache;
        readonly ParticleSystem.EmissionModule[] m_SprayEmission = new ParticleSystem.EmissionModule[2];
        Material m_SprayMaterial, m_RibbonMaterial, m_RingMaterial;

        // ribbon 位置历史（世界坐标，y = 推进瞬间锁存的浪高）；顶点缓存复用避免每帧分配。
        readonly Vector3[] m_History = new Vector3[WakeFoamCore.RibbonSampleCount];
        readonly List<Vector3> m_VertexCache = new List<Vector3>(WakeFoamCore.RibbonSampleCount * 2);
        Vector3 m_LastPushPos;
        Vector3 m_LastPerp = Vector3.right;
        bool m_HavePush;

        // 水面查询结构体复用（VesselBuoyancy 同款 probe 模式：只初始化一次）。
        WaterSearchParameters m_SearchParams;
        WaterSearchResult m_SearchResult;

        float m_WaterLocalY;      // 泡沫层基线世界高度换算到船根局部 y（烘焙缩放折算，NavigationLights 同坑）
        float m_RootScaleInv = 1f;
        float m_RibbonSpacingM;
        float m_HullCenterX;      // 艉柱/中线根局部坐标（BuildRig 定型，运行期只读）
        float m_HullMinZ;

        // ── EditMode 观测口（先例 NavigationLights.RigBuilt / LastLampFactor01）─────────
        public bool RigBuilt => m_RigRoot != null;
        public float LastSprayRatePerSide => m_LastSprayRate;
        public float LastWakeIntensity01 => m_LastWakeIntensity;
        public float LastRingAlpha01 => m_LastRingAlpha;
        float m_LastSprayRate, m_LastWakeIntensity, m_LastRingAlpha;
        public int LastWaterQueries { get; private set; }

        void OnEnable()
        {
            BuildRig();
        }

        void LateUpdate()
        {
            float speed = follower != null ? follower.SpeedMps : 0f;
            ApplySpeed(speed);
            ApplyDecalSuppression();
        }

        void OnDisable()
        {
            if (m_RigRoot != null) m_RigRoot.gameObject.SetActive(false); // 组件禁用整树熄灭（防孤儿泡沫）
            if (m_WorldRoot != null) m_WorldRoot.gameObject.SetActive(false);
        }

        void OnDestroy()
        {
            // 运行时构建物收口：船子树随本 GO 自灭；世界系 ribbon 树挂场景根须显式销毁
            // （编辑器态 DestroyImmediate 防 "may not be called" 红测，NavigationLights 同款分支）。
            if (m_WorldRoot != null)
            {
                if (Application.isPlaying) Destroy(m_WorldRoot.gameObject);
                else DestroyImmediate(m_WorldRoot.gameObject);
            }
            DestroyOwned(m_RibbonMesh);
            DestroyOwned(m_RingMesh);
            DestroyOwned(m_SprayMaterial);
            DestroyOwned(m_RibbonMaterial);
            DestroyOwned(m_RingMaterial);
        }

        static void DestroyOwned(Object resource)
        {
            if (resource == null) return;
            if (Application.isPlaying) Destroy(resource); else DestroyImmediate(resource);
        }

        /// <summary>
        /// 每帧驱动（公开 = EditMode 可测缝，先例 BoatWaterDecals.ApplySpeed）：档位谓词开关
        /// 整树 → 纯核心算强度/发射率 → 粒子发射率 + ribbon/环材质 alpha + ribbon 几何推进。
        /// 曲线/尺寸/谓词一律出自 WakeFoamCore 纯函数，适配器只做引擎写。
        /// </summary>
        public void ApplySpeed(float speedMps)
        {
            LastWaterQueries = 0;
            if (!RigBuilt) return;
            bool active = WakeFoamCore.ParticlesActive(M8Quality.CurrentTier);
            if (m_RigRoot.gameObject.activeSelf != active) m_RigRoot.gameObject.SetActive(active);
            if (m_WorldRoot.gameObject.activeSelf != active) m_WorldRoot.gameObject.SetActive(active);
            if (!active)
            {
                m_LastSprayRate = 0f;
                m_LastWakeIntensity = 0f;
                m_LastRingAlpha = 0f;
                return; // Low 档：decal 归 BoatWaterDecals，本 rig 零写零绘制
            }

            float clamp01Multiplier = Mathf.Clamp01(intensityMultiplier);
            m_SprayMaterial.SetColor(k_FoamColor, new Color(0.75f, 0.78f, 0.82f, 0.6f));
            float wake = WakeFoamCore.SpeedFactor(speedMps, speedThresholdMps, fullEffectSpeedMps) * clamp01Multiplier;
            float sprayRate = WakeFoamCore.SprayEmissionRate(speedMps, speedThresholdMps, fullEffectSpeedMps,
                                                             loaMeters, MaxSprayRatePerSide) * clamp01Multiplier;
            m_LastSprayRate = sprayRate;
            m_LastWakeIntensity = wake;
            m_LastRingAlpha = wake;

            m_SprayEmission[0].rateOverTime = sprayRate;
            m_SprayEmission[1].rateOverTime = sprayRate;

            // 泡沫带/环：速度爬坡 × 面板乘子 → additive alpha（rgb 亮度恒定，只动强度）。
            SetFoamAlpha(m_RibbonMaterial, wake, k_RibbonBaseAlpha);
            SetFoamAlpha(m_RingMaterial, wake, k_RingBaseAlpha);
            m_RibbonRenderer.enabled = wake > 0.001f; // 零强度不提交 draw（静止/锢泊零开销）
            m_RingRenderer.enabled = wake > 0.001f;

            if (wake <= 0.001f) { m_HavePush = false; return; }

            UpdateRibbon();
            UpdateRingHeight();
        }

        /// <summary>
        /// High 档压制两块 WaterDecal（公开 = EditMode 可测缝）：必须晚于 BoatWaterDecals.Update
        /// （其每帧按速度门重写 enabled）——本类 LateUpdate + 执行序 200 保证确定后写。
        /// Low 档不写：decal 语义完整归还 BoatWaterDecals（速度门谓词原样）。
        /// </summary>
        public void ApplyDecalSuppression()
        {
            if (decals == null) return;
            if (!WakeFoamCore.DecalsSuppressed(M8Quality.CurrentTier)) return;
            if (decals.bowDecal != null) decals.bowDecal.enabled = false;
            if (decals.wakeDecal != null) decals.wakeDecal.enabled = false;
        }

        // ── rig 构建 ───────────────────────────────────────────────────────────────────

        void BuildRig()
        {
            if (m_RigRoot != null) return; // 幂等（域重载/重启用不重建）

            // 编辑器态无生命周期回调（非 ExecuteAlways，OnDestroy 不触发）：EditMode 上一
            // 构建遗留的同名世界树先收口，保证 k_WorldRootName 场景内唯一（测试经
            // GameObject.Find 按名定位，重复树会使命中漂移）。在幂等守卫之后——此刻本 rig
            // 的树尚未建，Find 命中的必是遗留树；运行期由 OnDestroy 收口，此分支不生效。
            if (!Application.isPlaying)
            {
                var stale = GameObject.Find(k_WorldRootName);
                if (stale != null) DestroyImmediate(stale);
            }

            // hull 包围盒合并到根局部（收集法同 NavigationLights.BuildRig；包围盒不依赖
            // triangles，无需 Read/Write）。艏向 +Z：艏柱 = max.z、艉柱 = min.z。
            var own = GetComponent<MeshFilter>();
            var filters = own != null ? new[] { own } : GetComponentsInChildren<MeshFilter>(false);
            var rootInverse = transform.worldToLocalMatrix;
            var bounds = new Bounds();
            bool any = false;
            int excludedForeign = 0;
            foreach (var filter in filters)
            {
                var mesh = filter != null ? filter.sharedMesh : null;
                if (mesh == null) continue;
                // M9 修复：剔除兄弟 rig 子树（NavigationLightsRig 的 30m 拖尾 quad 会把 hull
                // AABB 吹大 ~2×，水线环随之膨胀成超船巨环——实机 overlook 视角实证）。
                // 两棵 rig 树都是运行时命名构建，按祖先名剔除精确且零维护。
                bool foreignRig = false;
                for (var t = filter.transform; t != null && t != transform; t = t.parent)
                {
                    var n = t.name;
                    if (n == k_RigName || n == k_WorldRootName || n == "NavigationLightsRig")
                    {
                        foreignRig = true;
                        break;
                    }
                }
                if (foreignRig) { excludedForeign++; continue; }
                var filterToRoot = rootInverse * filter.transform.localToWorldMatrix;
                var b = mesh.bounds;
                for (int xi = 0; xi < 2; xi++)
                for (int yi = 0; yi < 2; yi++)
                for (int zi = 0; zi < 2; zi++)
                {
                    var p = filterToRoot.MultiplyPoint3x4(new Vector3(
                        xi == 0 ? b.min.x : b.max.x,
                        yi == 0 ? b.min.y : b.max.y,
                        zi == 0 ? b.min.z : b.max.z));
                    if (!any) { bounds = new Bounds(p, Vector3.zero); any = true; }
                    else bounds.Encapsulate(p);
                }
            }
            if (!any)
            {
                Debug.LogWarning($"{k_LogTag} {name}: no usable hull mesh — wake foam rig disabled.", this);
                enabled = false;
                return;
            }

            // 编目 prefab 根含烘焙统一缩放（局部单位 ≠ 米，M2-B 同坑）：世界尺寸经 lossyScale 折算。
            float s = Mathf.Max(transform.lossyScale.x, 1e-4f);
            m_RootScaleInv = 1f / s;
            m_WaterLocalY = (k_SurfaceWorldY - transform.position.y) * m_RootScaleInv;
            m_HullCenterX = bounds.center.x;
            m_HullMinZ = bounds.min.z;
            float beamWorldM = bounds.size.x * s;
            m_RibbonSpacingM = WakeFoamCore.HistorySpacingM(loaMeters);

            m_RigRoot = new GameObject(k_RigName).transform;
            m_RigRoot.SetParent(transform, false);

            var blob = WakeFoamTexture.RadialSoftBlob();

            // ① 艏浪：左右各一 Cone 粒子系，V 形外张（±yaw）+ 上抛（pitch），世界系模拟。
            m_SprayMaterial = FoamMaterial(blob, 1f);
            for (int i = 0; i < 2; i++) BuildSprayEmitter(i, bounds);

            // ② 艉迹 ribbon：世界系顶点（采样点锁浪高），静态拓扑 + 每帧只写位置。
            m_RibbonMaterial = FoamMaterial(WakeFoamTexture.WakeStrip(), 0f);
            BuildRibbon();

            // ③ 水线泡沫环：船子树椭圆环（跟船零同步成本），y 逐帧贴水面。
            m_RingMaterial = FoamMaterial(WakeFoamTexture.HullFoamStrip(), 0f);
            BuildRing(bounds, beamWorldM);

            // 水面查询参数一次初始化（VesselBuoyancy 同款 probe 常量）。
            m_SearchParams.error = 0.01f;
            m_SearchParams.maxIterations = 8;
            m_SearchParams.outputNormal = false;

            Debug.Log($"{k_LogTag} {name}: wake foam rig built loa={loaMeters:F0} m beam={beamWorldM:F1} m " +
                      $"hullBounds(local)=({bounds.size.x:F1}x{bounds.size.y:F1}x{bounds.size.z:F1}) center=({bounds.center.x:F0},{bounds.center.y:F0},{bounds.center.z:F0}) " +
                      $"filters={filters.Length} excludedForeign={excludedForeign} scale={s:F4} " +
                      $"spray 2×{MaxSprayParticlesPerSide} particles (rate ≤{MaxSprayRatePerSide:0}/s·side), " +
                      $"ribbon {WakeFoamCore.RibbonSampleCount} samples @ {m_RibbonSpacingM:0.0#} m, ring {k_RingSegments} segs; " +
                      $"tier High = particles+ribbon (decal suppressed), Low = decal");
        }

        void BuildSprayEmitter(int side, Bounds bounds)
        {
            var go = new GameObject(side == 0 ? "BowSpray.Port" : "BowSpray.Starboard");
            go.transform.SetParent(m_RigRoot, false);
            go.transform.localPosition = new Vector3(bounds.center.x, m_WaterLocalY, bounds.max.z); // 艏柱
            // Cone 默认朝局部 +Z：pitch 上抛 + yaw 外张（0=左舷 / 1=右舷）= V 形两臂。
            go.transform.localRotation = Quaternion.Euler(-12f, side == 0 ? -28f : 28f, 0f);

            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.simulationSpace = ParticleSystemSimulationSpace.World; // 喷出后留水面，不随船拖走
            main.startLifetime = 1.1f;
            main.startSpeed = Mathf.Clamp(loaMeters * 0.22f, 2f, 9f);  // 抛出初速随船级
            main.startSize = Mathf.Clamp(loaMeters * 0.035f, 0.25f, 1.2f);
            main.startColor = new Color(1f, 1f, 1f, 0.6f);
            main.maxParticles = MaxSprayParticlesPerSide;              // 预算锚（头注）
            main.gravityModifier = 0.5f;                               // 小幅艏浪抛起后落水
            main.loop = true;

            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 10f;
            shape.radius = Mathf.Max(0.05f, loaMeters * 0.015f);

            var emission = ps.emission;
            emission.rateOverTime = 0f; // 默认零发射（ApplySpeed 每帧按速度/Froude 驱动）

            // 粒子先扬后碎（renderer 侧缩放，与顶色通路无关）：末段缩近零 = "软消亡"，
            // 规避 HDRP/Unlit 不保证采样粒子顶色导致的消失 pop。
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0f, 0.7f, 1f, 0.15f));

            var renderer = go.GetComponent<ParticleSystemRenderer>();
            renderer.sharedMaterial = m_SprayMaterial;
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.alignment = ParticleSystemRenderSpace.View;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
            renderer.sortingFudge = 0f;

            m_SprayEmission[side] = emission; // 模块句柄缓存（struct，复用免每帧取）
        }

        void BuildRibbon()
        {
            m_WorldRoot = new GameObject(k_WorldRootName).transform; // 挂场景根：顶点世界系，不随船/缩放
            var go = new GameObject(k_RibbonName);
            go.transform.SetParent(m_WorldRoot, false);
            m_RibbonMesh = new Mesh { name = "WakeRibbon.Mesh" };
            m_RibbonMesh.MarkDynamic(); // Dynamic water-conforming geometry.

            int n = WakeFoamCore.RibbonSampleCount;
            var verts = new Vector3[n * 6];
            var uvs = new Vector2[n * 6];
            var tris = new int[(n - 1) * 18];
            for (int i = 0; i < n; i++)
            {
                float v = i / (n - 1f);
                for (int strip = 0; strip < 3; strip++)
                {
                    uvs[i * 6 + strip * 2] = new Vector2(0f, v);
                    uvs[i * 6 + strip * 2 + 1] = new Vector2(1f, v);
                }
            }
            for (int i = 0; i < n - 1; i++)
            {
                for (int strip = 0; strip < 3; strip++)
                {
                    int o = i * 18 + strip * 6, p = i * 6 + strip * 2;
                    tris[o] = p; tris[o + 1] = p + 1; tris[o + 2] = p + 6;
                    tris[o + 3] = p + 1; tris[o + 4] = p + 7; tris[o + 5] = p + 6;
                }
            }
            m_RibbonMesh.vertices = verts; // 拓扑与 UV 一次定型；位置每帧 SetVertices（缓存 list）
            m_RibbonMesh.uv = uvs;
            for (int i = 0; i < tris.Length; i += 3) (tris[i + 1], tris[i + 2]) = (tris[i + 2], tris[i + 1]);
            m_RibbonMesh.triangles = tris;
            m_VertexCache.AddRange(verts); // 容量一次到位（后续只覆写，零分配）

            var filter = go.AddComponent<MeshFilter>();
            filter.sharedMesh = m_RibbonMesh;
            m_RibbonRenderer = go.AddComponent<MeshRenderer>();
            m_RibbonRenderer.sharedMaterial = m_RibbonMaterial;
            m_RibbonRenderer.shadowCastingMode = ShadowCastingMode.Off;
            m_RibbonRenderer.receiveShadows = false;
            m_RibbonRenderer.enabled = false; // 首帧零强度不画
        }

        void BuildRing(Bounds bounds, float beamWorldM)
        {
            var go = new GameObject(k_RingName);
            go.transform.SetParent(m_RigRoot, false);
            float halfLoa = bounds.size.z * 0.5f;
            float halfBeam = bounds.size.x * 0.5f;
            float widthLocal = WakeFoamCore.RingWidthM(beamWorldM) * m_RootScaleInv;
            // 内缘椭圆略放出血贴壳（箱形包围盒近似真壳：艏艉 3%/舷侧 12%），外缘加沫带宽。
            float ai = halfLoa * 1.03f, bi = halfBeam * 1.12f;
            float ao = ai + widthLocal, bo = bi + widthLocal;

            var verts = new Vector3[k_RingSegments * 2];
            var uvs = new Vector2[k_RingSegments * 2];
            var tris = new int[k_RingSegments * 6];
            for (int i = 0; i < k_RingSegments; i++)
            {
                float u = i / (float)k_RingSegments;
                float theta = u * 2f * Mathf.PI;
                float cos = Mathf.Cos(theta), sin = Mathf.Sin(theta);
                // M9 修复：椭圆轴 X=beam（bi/bo 短轴）、Z=LOA（ai/ao 长轴）——原实现两轴装反
                // （长轴横贯 beam），实机追拍视角环呈 2.5× 船宽的横椭圆实证。
                verts[i * 2] = new Vector3(bounds.center.x + bi * cos, 0f, bounds.center.z + ai * sin);
                verts[i * 2 + 1] = new Vector3(bounds.center.x + bo * cos, 0f, bounds.center.z + ao * sin);
                uvs[i * 2] = new Vector2(u, 0f);     // v=0 内缘浓 → v=1 外缘散
                uvs[i * 2 + 1] = new Vector2(u, 1f);
            }
            for (int i = 0; i < k_RingSegments; i++)
            {
                int j = (i + 1) % k_RingSegments; // 首尾闭合（strip 贴图 u=0/1 alpha=0，接缝无缝）
                int o = i * 6, p = i * 2, q = j * 2;
                tris[o] = p; tris[o + 1] = p + 1; tris[o + 2] = q;
                tris[o + 3] = p + 1; tris[o + 4] = q + 1; tris[o + 5] = q;
            }
            var mesh = new Mesh { name = "WaterlineFoamRing.Mesh" };
            m_RingMesh = mesh;
            m_RingBaseVertices = verts;
            m_RingVertexCache = new Vector3[verts.Length];
            mesh.vertices = verts;
            mesh.uv = uvs;
            for (int i = 0; i < tris.Length; i += 3) (tris[i + 1], tris[i + 2]) = (tris[i + 2], tris[i + 1]);
            mesh.triangles = tris;
            mesh.RecalculateNormals();
            mesh.RecalculateBounds(); // 静态几何，包围盒一次

            var filter = go.AddComponent<MeshFilter>();
            filter.sharedMesh = mesh;
            m_RingRenderer = go.AddComponent<MeshRenderer>();
            m_RingRenderer.sharedMaterial = m_RingMaterial;
            m_RingRenderer.shadowCastingMode = ShadowCastingMode.Off;
            m_RingRenderer.receiveShadows = false;
            m_RingRenderer.enabled = false;
            go.transform.localPosition = new Vector3(0f, m_WaterLocalY, 0f);
            m_Ring = go.transform;
        }

        // ── 每帧几何/水高 ───────────────────────────────────────────────────────────────

        /// <summary>
        /// ribbon 推进 + 顶点重排：艉柱世界点距离采样（HistorySpacingM），采样点锁存推进瞬间
        /// 浪高（历史带真实水面起伏，非平面近似）；艉端样本每帧刷新浪高（近艉段连续跟浪）；
        /// 大跳（传送/G 重跑）全量重置防跨图拉线。顶点：逐样本横向展开（垂直于历史切向），
        /// 宽度沿艉后收窄（1 → k_RibbonTailWidth）。
        /// </summary>
        void UpdateRibbon()
        {
            var sternWorld = transform.TransformPoint(new Vector3(m_HullCenterX, m_WaterLocalY, m_HullMinZ));
            TryQueryWaterY(ref sternWorld); // 失败保持船体高度估计（无水面/查询退化路径）

            if (!m_HavePush)
            {
                for (int i = 0; i < m_History.Length; i++) m_History[i] = sternWorld;
                m_LastPushPos = sternWorld;
                m_HavePush = true;
            }
            else
            {
                float moved = Vector3.Distance(sternWorld, m_LastPushPos);
                if (moved > m_RibbonSpacingM * k_TeleportResetFactor)
                {
                    for (int i = 0; i < m_History.Length; i++) m_History[i] = sternWorld; // 传送重置
                    m_LastPushPos = sternWorld;
                }
                else if (moved >= m_RibbonSpacingM)
                {
                    for (int i = m_History.Length - 1; i > 0; i--) m_History[i] = m_History[i - 1]; // 队首进新点
                    m_History[0] = sternWorld;
                    m_LastPushPos = sternWorld;
                }
                else
                {
                    m_History[0].y = sternWorld.y; // 未满采样距也逐帧刷新艉端浪高（近艉段跟浪）
                }
            }

            // 顶点重排（56 次 Vector3 写，零分配）：i=0 艉柱（新）→ i=N-1 最老（尾端）。
            int n = m_History.Length;
            float halfW = WakeFoamCore.RibbonHalfWidthM(loaMeters);
            float distanceBehind = 0f;
            var previousCenter = sternWorld;
            for (int i = 0; i < n; i++)
            {
                var prev = m_History[i > 0 ? i - 1 : 0];
                var next = m_History[i < n - 1 ? i + 1 : n - 1];
                var dir = next - prev;
                float len = Mathf.Sqrt(dir.x * dir.x + dir.z * dir.z);
                if (len > 1e-5f)
                {
                    m_LastPerp.Set(dir.z / len, 0f, -dir.x / len); // 水平左法向（up × dir 归一）
                }
                var center = i == 0 ? sternWorld : m_History[i - 1];
                distanceBehind += Vector3.Distance(center, previousCenter);
                previousCenter = center;
                float age = i / (n - 1f);
                float w = halfW * Mathf.Lerp(1f, 1.5f, age);
                m_VertexCache[i * 6] = center - m_LastPerp * w;
                m_VertexCache[i * 6 + 1] = center + m_LastPerp * w;
                float arm = WakeFoamCore.KelvinArmOffsetM(distanceBehind, halfW);
                float crestHalfWidth = Mathf.Lerp(0.25f, 0.8f, age);
                for (int side = 0; side < 2; side++)
                {
                    var armCenter = center + m_LastPerp * arm * (side == 0 ? -1f : 1f);
                    int index = i * 6 + 2 + side * 2;
                    m_VertexCache[index] = armCenter - m_LastPerp * crestHalfWidth;
                    m_VertexCache[index + 1] = armCenter + m_LastPerp * crestHalfWidth;
                }
            }
            // Each edge must follow the current water too; a single height per broad strip produces clipped dashed plates.
            for (int vertex = 0; vertex < m_VertexCache.Count; vertex++)
            {
                var point = m_VertexCache[vertex];
                if (TryQueryWaterY(ref point)) point.y += 0.075f;
                m_VertexCache[vertex] = point;
            }
            m_RibbonMesh.SetVertices(m_VertexCache);
            m_RibbonMesh.RecalculateNormals();
            m_RibbonMesh.RecalculateBounds(); // 世界系顶点：包围盒随形状走（768 顶点）
        }

        /// <summary>水线环逐帧贴水面：根局部 y = 基线局部 y +（查询浪高 − 基线世界高）/根缩放。</summary>
        void UpdateRingHeight()
        {
            if (m_Ring == null) return;
            var position = transform.position;
            position.y = 0f;
            m_Ring.SetPositionAndRotation(position, Quaternion.Euler(0f, transform.eulerAngles.y, 0f));
            for (int i = 0; i < m_RingBaseVertices.Length; i++)
            {
                var point = m_Ring.TransformPoint(m_RingBaseVertices[i]);
                TryQueryWaterY(ref point);
                    point.y += 0.075f;
                m_RingVertexCache[i] = m_Ring.InverseTransformPoint(point);
            }
            m_RingMesh.vertices = m_RingVertexCache;
            m_RingMesh.RecalculateNormals();
            m_RingMesh.RecalculateBounds();
        }

        /// <summary>查询世界点的浪高并写回 y（空水面/查询失败保持原 y = 船体高度估计）。</summary>
        bool TryQueryWaterY(ref Vector3 world)
        {
            if (water == null) return false;
            m_SearchParams.startPositionWS = new float3(world.x, world.y, world.z);
            m_SearchParams.targetPositionWS = m_SearchParams.startPositionWS;
            LastWaterQueries++;
            if (!water.ProjectPointOnWaterSurface(m_SearchParams, out m_SearchResult)) return false;
            world.y = m_SearchResult.projectedPositionWS.y;
            return true;
        }

        // ── 材质小件 ───────────────────────────────────────────────────────────────────

        const float k_RibbonBaseAlpha = 0.48f;
        const float k_RingBaseAlpha = 0.24f;
        static readonly Vector3 k_FoamTint = new Vector3(0.92f, 0.96f, 1.0f); // 泡沫冷白
        static readonly int k_FoamColor = Shader.PropertyToID("_BaseColor");

        void SetFoamAlpha(Material mat, float intensity01, float baseAlpha)
        {
            if (mat == null) return;
            mat.SetColor(k_FoamColor, new Color(
                k_FoamTint.x * 0.82f, k_FoamTint.y * 0.82f,
                k_FoamTint.z * 0.82f, baseAlpha * intensity01));
        }

        /// <summary>Scene-lit alpha foam: no opaque depth writes or specular reflection at zero coverage.</summary>
        static Material FoamMaterial(Texture2D map, float baseAlpha)
        {
            var prototype = Resources.Load<Material>("LitFoam");
            var mat = prototype != null ? new Material(prototype) : new Material(Shader.Find("HDRP/Lit"));
            mat.SetTexture("_BaseColorMap", map);
            mat.SetColor(k_FoamColor, new Color(0.75f, 0.78f, 0.82f, baseAlpha));
            mat.SetFloat("_SurfaceType", 1f);
            mat.SetFloat("_BlendMode", 0f);
            mat.SetFloat("_Metallic", 0f);
            mat.SetFloat("_Smoothness", 0.15f);
            mat.SetFloat("_EnableBlendModePreserveSpecularLighting", 0f);
            mat.SetFloat("_ReceivesSSRTransparent", 0f);
            mat.SetFloat("_ZWrite", 0f);
            mat.SetFloat("_CullMode", 0f); // Off（俯/仰视双面可见）
            mat.SetFloat("_DoubleSidedEnable", 1f);
            mat.renderQueue = (int)RenderQueue.Transparent;
            HDMaterial.ValidateMaterial(mat);
            mat.SetShaderPassEnabled("DepthForwardOnly", false);
            mat.SetShaderPassEnabled("DepthOnly", false);
            mat.SetShaderPassEnabled("TransparentDepthPrepass", false);
            mat.SetShaderPassEnabled("TransparentDepthPostpass", false);
            mat.SetShaderPassEnabled("MotionVectors", false);
            return mat;
        }
    }
}
