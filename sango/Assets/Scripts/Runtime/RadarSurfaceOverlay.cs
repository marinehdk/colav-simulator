using System;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// P1 3D 探测表现 · 水面 spoke 余辉盘（00-REPORT §4-1，任务书①；radar_view overlay 位）。
    /// 只读消费 P0 通道：<see cref="RadarSpokeStream.onRevolution"/>（整转 raster + 行源
    /// row_origins_ne_m）→ CPU 按转重建极坐标环形扇面 mesh（360 方位段 × 48 径向带，
    /// 顶点 = 行源 NE + 方位/距离 → RadarOverlayMath.DiscVertexWorld，逐行行源 = 每 spoke
    /// 采集时刻天线位，本船平移期盘面按行平移不拖影，web radar-video.js raster() 同语义）
    /// + 极坐标纹理（spokes×bins，RadarOverlayMath.RasterPixel 单色绿映射、RowFresh 行龄门）
    /// → 贴水面 y+0.5 m。圈龄衰减：最新圈 alpha=1、上一圈 0.45（RevolutionAlpha；
    /// Revolutions 环形容量 2 之外无残像）。
    /// 门控 = twin-bridge radar_view overlay（bridge.CurrentRadarView → TwinBridge.
    /// RadarViewEffect 纯函数，契约 §2 默认 off；数据面恒活与开关正交）。量程/维度
    /// 直接用帧上 envelope 回填值（RadarSpokeFrame.rangeM）。
    /// P1 波束扫掠楔（00-REPORT §4-4）：盘面第三件——当前 spoke 方位低透明度扇形，
    /// 相位 = RadarAntennaMount.SweepYawDeg(driver.RenderSimTime, 60/scan_period)，
    /// 与 web PPI sweepAzimuthRad、桅顶罩体旋转（RadarAntennaSpin 同函数同源 clock）
    /// 及盘纹理最新亮行同源 sim_time——"与水面盘扫线同步"即本面验收。
    /// </summary>
    public class RadarSurfaceOverlay : MonoBehaviour
    {
        [Tooltip("P0 spoke 通道（缺省场景自找；只读订阅 onRevolution/onDescriptor）")]
        public RadarSpokeStream stream;

        [Tooltip("twin 数据面驱动（缺省场景自找；Anchor 供绝对 NE→场景投影）")]
        public TwinSessionDriver driver;

        [Tooltip("twin-bridge 服务（缺省场景自找；radar_view 门控源）")]
        public TwinBridgeService bridge;

        [Tooltip("无 bridge 时的开发直通（默认关——契约 §2 radar_view 默认 off）")]
        public bool showWithoutBridge;

        const int AngularSegments = 360;    // 1°/段（H 波束 3.9° 的 1/4，弧度足够）
        const int RadialBands = 48;
        const float WaterClearanceM = 0.5f; // 任务书：贴本船 NE 水面 y+0.5 m
        const float ScanPeriodFallbackS = 2.5f; // 24 rpm 后端默认（descriptor 未达时的行龄门缺省）
        const float BeamHalfWidthDeg = 2f;  // 扫掠楔半角（H 波束 3.9°/2 示意）
        const float BeamAlpha = 0.22f;      // 扫掠楔透明度（低侵扰示意件）

        Transform m_Root;
        Mesh m_CurrentMesh, m_PreviousMesh;
        Texture2D m_CurrentTexture, m_PreviousTexture;
        Material m_CurrentMaterial, m_PreviousMaterial;
        Color32[] m_PixelBuffer;
        double m_ScanPeriodS = ScanPeriodFallbackS;
        bool m_StreamHooked;

        // 波束扫掠楔（3 顶点单三角，每帧全量覆写；容器复用免每帧分配）
        Mesh m_BeamMesh;
        Texture2D m_BeamTexture;
        Material m_BeamMaterial;
        MeshRenderer m_BeamRenderer;
        readonly System.Collections.Generic.List<Vector3> m_BeamVertices = new System.Collections.Generic.List<Vector3>(3);

        /// <summary>单行诊断（HUD/日志同款式）。</summary>
        public string Status =>
            "radar disc " + (m_CurrentMesh != null
                ? $"segs={AngularSegments}x{RadialBands} revs@y={WaterClearanceM:0.0}m"
                : "no revolution yet");

        void Update()
        {
            LazyWire();
            RefreshVisibility();
            // 会话重建/无数据：环形清空（RadarSpokeStream.Latest null）即撤盘，
            // 旧会话残圈不滞留（rebuild 后同维度新圈自然重建）。
            if (m_CurrentMesh != null && stream != null && stream.Latest == null) ClearGenerations();
            UpdateSweepBeam();
        }

        void OnDestroy() => ClearGenerations();

        /// <summary>惰性接线（场景自找，30 帧重试；EditMode 直调路径不依赖）——找到即订阅，幂等。</summary>
        void LazyWire()
        {
            if (m_StreamHooked) return;
            if (Time.frameCount % 30 != 0) return; // 未接线期场景检索节流
            if (stream == null) stream = FindFirstObjectByType<RadarSpokeStream>();
            if (driver == null) driver = FindFirstObjectByType<TwinSessionDriver>();
            if (bridge == null) bridge = FindFirstObjectByType<TwinBridgeService>();
            if (stream == null) return;
            stream.onRevolution += OnRevolution;
            stream.onDescriptor += OnDescriptor;
            m_StreamHooked = true;
        }

        void OnDescriptor(RadarPpiDescriptor descriptor)
        {
            if (descriptor != null && descriptor.scan_period_s > 0) m_ScanPeriodS = descriptor.scan_period_s;
        }

        /// <summary>radar_view overlay 门（每帧便宜查询；纯函数效果面在 TwinBridge）。</summary>
        void RefreshVisibility()
        {
            if (m_Root == null) return;
            TwinBridge.RadarViewEffect(bridge != null ? bridge.CurrentRadarView : TwinBridge.DefaultRadarView,
                out bool overlay, out _);
            m_Root.gameObject.SetActive(overlay || showWithoutBridge);
        }

        /// <summary>
        /// 一转到达：量程无效（envelope 未回填）或锚点未定则跳过；当前圈 = 本转
        /// raster，上一圈 = P0 环形里真正的旧转（广播时 Revolutions=[旧,新]，非本转
        /// 引用者）——两代各用各的行源/维度重建，材质 alpha 1 / 0.45（RevolutionAlpha
        /// 圈龄衰减，真数据余辉不虚构）。EditMode/测试可直调（不依赖 Update 接线）。
        /// </summary>
        public void OnRevolution(RadarSpokeFrame frame)
        {
            if (frame == null || frame.raster == null || frame.rangeM <= 0) return;
            TwinAnchor? anchor = driver != null ? driver.Anchor : null;
            if (!anchor.HasValue) return;
            EnsureRoot();

            RadarSpokeFrame previous = null;
            if (stream != null)
                foreach (var revolution in stream.Revolutions)
                    if (revolution != null && !ReferenceEquals(revolution, frame)) previous = revolution;
            if (previous != null && previous.raster != null && previous.rangeM > 0)
                BuildGeneration(previous, anchor.Value, m_PreviousMesh, m_PreviousTexture,
                    m_PreviousMaterial, RadarOverlayMath.RevolutionAlpha(1));
            else
                m_PreviousMesh.Clear(); // 首转（无旧转）或旧转量程未回填：上一圈位留空
            BuildGeneration(frame, anchor.Value, m_CurrentMesh, m_CurrentTexture, m_CurrentMaterial, 1f);
        }

        void EnsureRoot()
        {
            if (m_Root != null) return;
            m_Root = new GameObject("Radar surface overlay root").transform;
            m_Root.SetParent(transform, false);
            m_CurrentMesh = new Mesh { name = "Radar disc current" };
            m_PreviousMesh = new Mesh { name = "Radar disc previous" };
            m_CurrentTexture = new Texture2D(1, 1, TextureFormat.RGBA32, false);
            m_PreviousTexture = new Texture2D(1, 1, TextureFormat.RGBA32, false);
            m_CurrentMaterial = MakeDiscMaterial();
            m_PreviousMaterial = MakeDiscMaterial();
            SpawnRenderer("disc current", m_CurrentMesh, m_CurrentTexture, m_CurrentMaterial);
            SpawnRenderer("disc previous", m_PreviousMesh, m_PreviousTexture, m_PreviousMaterial);

            // 波束扫掠楔（§4-4）：1×1 白纹理 + 纯色 α（同盘面 HDRP/Unlit 管道）
            m_BeamMesh = new Mesh { name = "Radar sweep beam" };
            m_BeamTexture = new Texture2D(1, 1, TextureFormat.RGBA32, false);
            m_BeamTexture.SetPixel(0, 0, Color.white);
            m_BeamTexture.Apply(false, false);
            m_BeamMaterial = MakeDiscMaterial();
            m_BeamMaterial.SetColor("_UnlitColor", new Color(1f, 1f, 1f, BeamAlpha));
            var beamGo = new GameObject("disc sweep beam", typeof(MeshFilter), typeof(MeshRenderer));
            beamGo.transform.SetParent(m_Root, false);
            beamGo.GetComponent<MeshFilter>().sharedMesh = m_BeamMesh;
            m_BeamRenderer = beamGo.GetComponent<MeshRenderer>();
            m_BeamRenderer.sharedMaterial = m_BeamMaterial;
            m_BeamRenderer.shadowCastingMode = ShadowCastingMode.Off;
            m_BeamRenderer.receiveShadows = false;
            m_BeamRenderer.enabled = false; // 量程/本船就绪前不画
        }

        /// <summary>
        /// P1 波束扫掠楔（00-REPORT §4-4）：当前 spoke 方位低透明度扇形。
        /// 相位 = SweepYawDeg(RenderSimTime, 60/scan_period)——与 web PPI
        /// sweepAzimuthRad/桅顶罩体旋转同源 sim_time；世界方位 = 艏向 + 扫掠相位
        /// （自艏顺时针，WedgeLocalPoint 同手性）。量程未知/无本船/未同步（NaN）
        /// 隐藏——不虚构扫掠。3 顶点每帧覆写（容器复用，零分配）。
        /// </summary>
        void UpdateSweepBeam()
        {
            if (m_BeamMesh == null || m_BeamRenderer == null) return;
            // radar_view 非 overlay 态（root 已被 RefreshVisibility 熄灭）：不写顶点
            if (m_Root != null && !m_Root.gameObject.activeSelf) { m_BeamRenderer.enabled = false; return; }
            var own = driver != null ? driver.OwnShipObject : null;
            var frame = stream != null ? stream.Latest : null;
            if (own == null || frame == null || frame.rangeM <= 0)
            {
                m_BeamRenderer.enabled = false;
                return;
            }
            double sim = driver.RenderSimTime;
            if (double.IsNaN(sim))
            {
                m_BeamRenderer.enabled = false;
                return;
            }
            float rpm = m_ScanPeriodS > 0 ? 60f / (float)m_ScanPeriodS : Vessels.Mast.RadarAntennaMount.ScanRpmDefault;
            float bearing = own.transform.eulerAngles.y
                + Vessels.Mast.RadarAntennaMount.SweepYawDeg((float)sim, rpm);
            float radA = (bearing - BeamHalfWidthDeg) * Mathf.Deg2Rad;
            float radB = (bearing + BeamHalfWidthDeg) * Mathf.Deg2Rad;
            var center = new Vector3(own.transform.position.x, WaterClearanceM, own.transform.position.z);
            float range = (float)frame.rangeM;
            m_BeamVertices.Clear();
            m_BeamVertices.Add(center);
            m_BeamVertices.Add(center + new Vector3(Mathf.Sin(radA), 0f, Mathf.Cos(radA)) * range);
            m_BeamVertices.Add(center + new Vector3(Mathf.Sin(radB), 0f, Mathf.Cos(radB)) * range);
            m_BeamMesh.SetVertices(m_BeamVertices);
            m_BeamMesh.SetTriangles(new[] { 0, 1, 2 }, 0);
            m_BeamMesh.RecalculateBounds();
            m_BeamRenderer.enabled = true;
        }

        /// <summary>
        /// 一代盘重建：极坐标顶点（方位段 × 径向带 → 行源 NE + 偏移 → 场景，y=+0.5）+
        /// UV（u=方位/2π、v=距离/量程 → 纹理 row/col）+ 纹理像素（RasterPixel/RowFresh）。
        /// mesh/texture/material 由调用方持有（世代滚动复用），顶点全量覆写。
        /// </summary>
        void BuildGeneration(RadarSpokeFrame frame, TwinAnchor anchor, Mesh mesh, Texture2D texture,
            Material material, float alpha)
        {
            int spokes = frame.spokes, bins = frame.bins;
            EnsureTexture(texture, spokes, bins);

            // 纹理：行主序 raster（row=方位、col=距离 bin）→ x=row、y=bin 的 RGBA32。
            int pixels = spokes * bins;
            if (m_PixelBuffer == null || m_PixelBuffer.Length != pixels) m_PixelBuffer = new Color32[pixels];
            double[] rowTimes = frame.rowTimesS;
            for (int row = 0; row < spokes; row++)
            {
                bool fresh = rowTimes != null && rowTimes.Length == spokes
                    ? RadarOverlayMath.RowFresh(rowTimes[row], frame.tS, m_ScanPeriodS)
                    : true; // 无行时间元数据（维度门已弃）→ 不加额外门，raster 本体已钉
                int rowBase = row * bins;
                for (int bin = 0; bin < bins; bin++)
                {
                    byte value = frame.raster[rowBase + bin];
                    m_PixelBuffer[rowBase + bin] = fresh ? RadarOverlayMath.RasterPixel(value) : new Color32(0, 0, 0, 0);
                }
            }
            texture.SetPixels32(m_PixelBuffer);
            texture.Apply(false, false);

            // mesh：顶点/UV 全量覆写（IndexFormat.UInt32 一次到位，防 65k 顶点档切换）。
            int vertsX = AngularSegments + 1, vertsY = RadialBands + 1;
            var vertices = new Vector3[vertsX * vertsY];
            var uvs = new Vector2[vertsX * vertsY];
            var triangles = new int[AngularSegments * RadialBands * 6];
            var origins = frame.rowOriginsNeM;
            for (int i = 0; i < vertsX; i++)
            {
                double bearing = i * 2.0 * Math.PI / AngularSegments;
                int row = RadarOverlayMath.BearingRow(bearing, spokes);
                // 行源缺该行（维度短表）→ 锚点即本船首帧位（降级放置，不脑补外推）。
                double originN = origins != null && row < origins.Length ? origins[row][0] : anchor.NorthM;
                double originE = origins != null && row < origins.Length ? origins[row][1] : anchor.EastM;
                float u = (float)i / AngularSegments;
                for (int j = 0; j < vertsY; j++)
                {
                    float v = (float)j / RadialBands;
                    double range = v * frame.rangeM;
                    vertices[i * vertsY + j] = RadarOverlayMath.DiscVertexWorld(
                        anchor, originN, originE, bearing, range, WaterClearanceM);
                    uvs[i * vertsY + j] = new Vector2(u, v);
                }
            }
            int tri = 0;
            for (int i = 0; i < AngularSegments; i++)
            {
                for (int j = 0; j < RadialBands; j++)
                {
                    int a = i * vertsY + j, b = (i + 1) * vertsY + j, c = (i + 1) * vertsY + j + 1, d = i * vertsY + j + 1;
                    triangles[tri++] = a; triangles[tri++] = d; triangles[tri++] = c;
                    triangles[tri++] = a; triangles[tri++] = c; triangles[tri++] = b;
                }
            }
            mesh.Clear();
            mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.SetVertices(vertices);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(triangles, 0);
            mesh.RecalculateBounds();
            material.SetColor("_UnlitColor", new Color(1f, 1f, 1f, alpha)); // 白×纹理=绿;alpha=圈龄衰减
        }

        void SpawnRenderer(string childName, Mesh mesh, Texture2D texture, Material material)
        {
            material.SetTexture("_UnlitColorMap", texture);
            material.EnableKeyword("_UNLIT_COLOR_MAP");
            var go = new GameObject(childName, typeof(MeshFilter), typeof(MeshRenderer));
            go.transform.SetParent(m_Root, false);
            go.GetComponent<MeshFilter>().sharedMesh = mesh;
            var renderer = go.GetComponent<MeshRenderer>();
            renderer.sharedMaterial = material;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
        }

        static Material MakeDiscMaterial()
        {
            // TwinSituationDisplay.MeshObject 同款 HDRP/Unlit 透明面（运行时零资产依赖）。
            var material = new Material(Shader.Find("HDRP/Unlit"));
            material.SetFloat("_BlendMode", 0);
            material.SetFloat("_TransparentZWrite", 0);
            material.SetFloat("_DoubleSidedEnable", 1);
            material.SetFloat("_EnableFogOnTransparent", 0);
            HDMaterial.SetSurfaceType(material, true);
            material.renderQueue = 3000;
            HDMaterial.ValidateMaterial(material);
            return material;
        }

        static void EnsureTexture(Texture2D texture, int spokes, int bins)
        {
            if (texture.width == spokes && texture.height == bins) return;
            texture.Resize(spokes, bins, TextureFormat.RGBA32, false);
            texture.wrapMode = TextureWrapMode.Repeat; // 方位 seam（u=1 → 行 0）回卷采样
            texture.filterMode = FilterMode.Bilinear;
            texture.Apply(false, false);
        }

        void ClearGenerations()
        {
            if (Application.isPlaying)
            {
                if (m_Root != null) Destroy(m_Root.gameObject);
                if (m_CurrentMesh != null) Destroy(m_CurrentMesh);
                if (m_PreviousMesh != null) Destroy(m_PreviousMesh);
                if (m_CurrentTexture != null) Destroy(m_CurrentTexture);
                if (m_PreviousTexture != null) Destroy(m_PreviousTexture);
                if (m_CurrentMaterial != null) Destroy(m_CurrentMaterial);
                if (m_PreviousMaterial != null) Destroy(m_PreviousMaterial);
                if (m_BeamMesh != null) Destroy(m_BeamMesh);
                if (m_BeamTexture != null) Destroy(m_BeamTexture);
                if (m_BeamMaterial != null) Destroy(m_BeamMaterial);
            }
            else
            {
                if (m_Root != null) DestroyImmediate(m_Root.gameObject);
                if (m_CurrentMesh != null) DestroyImmediate(m_CurrentMesh);
                if (m_PreviousMesh != null) DestroyImmediate(m_PreviousMesh);
                if (m_CurrentTexture != null) DestroyImmediate(m_CurrentTexture);
                if (m_PreviousTexture != null) DestroyImmediate(m_PreviousTexture);
                if (m_CurrentMaterial != null) DestroyImmediate(m_CurrentMaterial);
                if (m_PreviousMaterial != null) DestroyImmediate(m_PreviousMaterial);
                if (m_BeamMesh != null) DestroyImmediate(m_BeamMesh);
                if (m_BeamTexture != null) DestroyImmediate(m_BeamTexture);
                if (m_BeamMaterial != null) DestroyImmediate(m_BeamMaterial);
            }
            m_Root = null;
            m_CurrentMesh = m_PreviousMesh = null;
            m_CurrentTexture = m_PreviousTexture = null;
            m_CurrentMaterial = m_PreviousMaterial = null;
            m_BeamMesh = null;
            m_BeamTexture = null;
            m_BeamMaterial = null;
            m_BeamRenderer = null;
        }

        // ── 自举(--sango-twin-bridge 族旗标;RadarPpiScreen.Bootstrap 同门) ────────

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            var args = Environment.GetCommandLineArgs();
            bool enabled = Array.IndexOf(args, SangoSeamConfig.TwinBridgeCliFlag) >= 0
                || Array.IndexOf(args, SangoSeamConfig.TwinBridgeLocalCliFlag) >= 0;
            if (!enabled) return;
            var service = FindFirstObjectByType<TwinBridgeService>();
            if (service == null) return; // 场景未预接线:PPI 屏侧已告警语义,本组件静默跳过
            var host = new GameObject("Radar surface overlay");
            host.transform.SetParent(service.transform, false);
            var overlay = host.AddComponent<RadarSurfaceOverlay>();
            overlay.bridge = service;
            overlay.driver = service.driver;
            Debug.Log("[Sango.RadarSurface] surface overlay attached (radar_view overlay 位;默认隐藏)");
        }
    }
}
