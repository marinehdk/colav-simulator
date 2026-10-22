using System;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// P1 3D 探测表现 · 盲区可视化（00-REPORT §4-3，任务书③；radar_view overlay 位）。
    /// 红色半透明件：①盲环 R_min 圈（ppi 描述子 blind_ring_m = h/tan(VBW/2)≈54 m，
    /// sensing.py blind_ring_m 属性——近程垂直波束盲区）；②盲扇区扇楔
    /// （blind_sectors_deg = [[center_rel_bow_deg, half_width_deg],…]，sensing.py:495/
    /// 1101 相对艏向扇区表，艉向驾驶室遮挡等）。几何钉在随艏向 yaw 的根节点上
    /// （ship frame：+z 艏/+x 右舷，WedgeLocalPoint），根每帧拷贝本船位姿
    /// （driver.OwnShipObject）——扇楔随艏向转、随船走。
    /// 数据缝已闭合（P1 接线，本批）：RadarPpiDescriptor 已带 blind_ring_m（envelope
    /// radar_ppi 键存活于全部 transports，main.py:2105）→ 只读订阅 onDescriptor 即得；
    /// blind_sectors_deg 嵌套数组（JsonUtility 不支持）→ ReceiveLoop 经
    /// RadarOverlayMath.ParseBlindSectors 从信封原文解析、RadarSpokeStream.onBlindSectors
    /// 变化广播 → 本组件 LazyWire 订阅直喂 ApplyBlindSectors（EditMode 直调口保留）。
    /// </summary>
    public class RadarBlindZones : MonoBehaviour
    {
        [Tooltip("P0 spoke 通道（缺省场景自找；onDescriptor 取 blind_ring_m/量程）")]
        public RadarSpokeStream stream;

        [Tooltip("twin 数据面驱动（缺省场景自找；OwnShipObject 位姿跟随）")]
        public TwinSessionDriver driver;

        [Tooltip("twin-bridge 服务（缺省场景自找；radar_view 门控源）")]
        public TwinBridgeService bridge;

        [Tooltip("无 bridge 时的开发直通（默认关——契约 §2 radar_view 默认 off）")]
        public bool showWithoutBridge;

        const float RootYM = 0.55f;        // 盘面层级：余辉盘 0.5 m 之上
        const float RingLocalYM = 0.05f;   // 环带再抬（与扇楔防 z-fight）
        const int RingSegments = 128;      // 环带圆周段
        const int WedgeSegments = 24;      // 扇楔弧向段（2° 以内弧弦差可忽略）
        const float RingWidthM = 6f;       // R_min 圈带宽（可视宽度，非物理语义）
        const float WedgeAlpha = 0.16f;    // 扇楔透明度（大面积低侵扰）
        const float RingAlpha = 0.5f;      // 环带透明度

        Transform m_Root;
        Mesh m_RingMesh;
        Material m_RingMaterial;
        float m_BlindRingM;
        float m_RangeM;
        bool m_DescriptorSeen;
        bool m_StreamHooked;

        readonly System.Collections.Generic.List<Mesh> m_WedgeMeshes = new System.Collections.Generic.List<Mesh>();
        readonly System.Collections.Generic.List<Material> m_WedgeMaterials = new System.Collections.Generic.List<Material>();
        float[][] m_Sectors;

        /// <summary>单行诊断（HUD/日志同款式）。</summary>
        public string Status =>
            "radar blind zones " + (m_DescriptorSeen
                ? $"R_min={m_BlindRingM:0.#}m range={m_RangeM:0.#}m sectors={(m_Sectors != null ? m_Sectors.Length : 0)}"
                : "no descriptor yet");

        void Update()
        {
            LazyWire();
            if (m_Root == null) return;
            TwinBridge.RadarViewEffect(bridge != null ? bridge.CurrentRadarView : TwinBridge.DefaultRadarView,
                out bool overlay, out _);
            m_Root.gameObject.SetActive(overlay || showWithoutBridge);

            // 根随本船（x/z + 艏向 yaw；y 固定盘面层级）——盲环/扇楔是随船几何。
            var own = driver != null ? driver.OwnShipObject : null;
            if (own != null)
                m_Root.SetPositionAndRotation(
                    new Vector3(own.transform.position.x, RootYM, own.transform.position.z),
                    Quaternion.Euler(0f, own.transform.eulerAngles.y, 0f));
        }

        void OnDestroy()
        {
            if (Application.isPlaying)
            {
                if (m_Root != null) Destroy(m_Root.gameObject);
                if (m_RingMesh != null) Destroy(m_RingMesh);
                if (m_RingMaterial != null) Destroy(m_RingMaterial);
                foreach (var mesh in m_WedgeMeshes) if (mesh != null) Destroy(mesh);
                foreach (var material in m_WedgeMaterials) if (material != null) Destroy(material);
            }
            else
            {
                if (m_Root != null) DestroyImmediate(m_Root.gameObject);
                if (m_RingMesh != null) DestroyImmediate(m_RingMesh);
                if (m_RingMaterial != null) DestroyImmediate(m_RingMaterial);
                foreach (var mesh in m_WedgeMeshes) if (mesh != null) DestroyImmediate(mesh);
                foreach (var material in m_WedgeMaterials) if (material != null) DestroyImmediate(material);
            }
            m_Root = null;
            m_RingMesh = null;
            m_RingMaterial = null;
            m_WedgeMeshes.Clear();
            m_WedgeMaterials.Clear();
        }

        void LazyWire()
        {
            if (m_StreamHooked) return;
            if (Time.frameCount % 30 != 0) return; // 未接线期场景检索节流
            if (stream == null) stream = FindFirstObjectByType<RadarSpokeStream>();
            if (driver == null) driver = FindFirstObjectByType<TwinSessionDriver>();
            if (bridge == null) bridge = FindFirstObjectByType<TwinBridgeService>();
            if (stream == null) return;
            stream.onDescriptor += OnDescriptor; // 只订阅一次（迟到订阅补课在下一行）
            stream.onBlindSectors += ApplyBlindSectors; // P1 live 接线：变化帧面直喂
            m_StreamHooked = true;
            if (stream.LatestDescriptor != null) OnDescriptor(stream.LatestDescriptor);
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
            var host = new GameObject("Radar blind zones");
            host.transform.SetParent(service.transform, false);
            var zones = host.AddComponent<RadarBlindZones>();
            zones.bridge = service;
            zones.driver = service.driver;
            Debug.Log("[Sango.RadarBlindZones] blind zones attached (radar_view overlay 位;默认隐藏)");
        }

        /// <summary>描述子到达：盲环半径/量程落位并（重）建几何。scan_period 等其余面归别家。</summary>
        void OnDescriptor(RadarPpiDescriptor descriptor)
        {
            if (descriptor == null || descriptor.spokes <= 0) return;
            float blindRing = descriptor.blind_ring_m > 0 ? (float)descriptor.blind_ring_m
                : RadarOverlayMath.BlindRingFallbackM;
            float range = descriptor.range_scale_nm > 0
                ? (float)descriptor.range_scale_nm * RadarOverlayMath.MetersPerNm : 0f;
            bool geometryDirty = !m_DescriptorSeen || !Mathf.Approximately(blindRing, m_BlindRingM)
                || !Mathf.Approximately(range, m_RangeM);
            m_BlindRingM = blindRing;
            m_RangeM = range;
            m_DescriptorSeen = true;
            if (geometryDirty) RebuildGeometry();
        }

        /// <summary>
        /// 盲扇区注入（[[center_rel_bow_deg, half_width_deg],…]；RadarOverlayMath.
        /// ParseBlindSectors 的产物或等形数组）。null/空 = 无扇区（后端默认
        /// blind_sectors_deg=()——FCB45 艉向遮挡实测回填属 P3，00-REPORT §7-1）。
        /// </summary>
        public void ApplyBlindSectors(float[][] sectors)
        {
            m_Sectors = sectors;
            RebuildGeometry();
        }

        /// <summary>
        /// 几何重建：根下两个子层——扇楔（0→量程，ship-local 扇形，弧向细分）+
        /// 盲环带（R_min±带宽/2 圆环）。红半透明 HDRP/Unlit（MeshObject 同款面）。
        /// 扇楔在缺省量程（range=0，descriptor 未达）时不出（半径无意义），
        /// 环带独立于量程可见。
        /// </summary>
        void RebuildGeometry()
        {
            EnsureRoot();
            ClearWedges();

            if (m_RangeM > 0 && m_Sectors != null)
            {
                foreach (var sector in m_Sectors)
                {
                    if (sector == null || sector.Length < 2 || sector[1] < 0f) continue;
                    var wedge = BuildWedgeMesh(sector[0], sector[1], m_RangeM);
                    m_WedgeMeshes.Add(wedge);
                    var wedgeMaterial = MakeOverlayMaterial(new Color(1f, 0.25f, 0.2f, WedgeAlpha));
                    m_WedgeMaterials.Add(wedgeMaterial);
                    SpawnRenderer($"blind wedge {sector[0]:0.#}±{sector[1]:0.#}°", wedge, wedgeMaterial);
                }
            }

            if (m_BlindRingM > 0)
            {
                if (m_RingMesh == null)
                {
                    m_RingMesh = new Mesh { name = "Radar blind ring" };
                    m_RingMaterial = MakeOverlayMaterial(new Color(1f, 0.3f, 0.25f, RingAlpha));
                    var ringGo = SpawnRenderer("blind ring", m_RingMesh, m_RingMaterial);
                    ringGo.transform.localPosition = new Vector3(0f, RingLocalYM, 0f);
                }
                WriteRingBand(m_RingMesh, m_BlindRingM, RingWidthM);
            }
        }

        void EnsureRoot()
        {
            if (m_Root != null) return;
            m_Root = new GameObject("Radar blind zones root").transform;
            m_Root.SetParent(transform, false);
        }

        /// <summary>扇楔 mesh：中心（本船）→ 量程扇形（ship-local，弧向 WedgeSegments 细分）。</summary>
        static Mesh BuildWedgeMesh(float centerRelBowDeg, float halfWidthDeg, float rangeM)
        {
            var mesh = new Mesh { name = $"Radar blind wedge {centerRelBowDeg:0.#}" };
            var vertices = new Vector3[(WedgeSegments + 2) * 2]; // 弧向 WedgeSegments+1 段（端点含边界）
            var triangles = new int[(WedgeSegments + 1) * 6];
            const float innerR = 0.01f; // 内缘近船心（非零防退化三角形）
            for (int i = 0; i <= WedgeSegments + 1; i++)
            {
                float t = Mathf.Clamp01((i - 0.5f) / WedgeSegments); // 端点内收半段（中心/边缘角不越界）
                float bearing = centerRelBowDeg - halfWidthDeg + t * 2f * halfWidthDeg;
                vertices[i * 2] = RadarOverlayMath.WedgeLocalPoint(bearing, innerR);
                vertices[i * 2 + 1] = RadarOverlayMath.WedgeLocalPoint(bearing, rangeM);
            }
            int tri = 0;
            for (int i = 0; i < WedgeSegments + 1; i++)
            {
                int a = i * 2, b = i * 2 + 1, c = (i + 1) * 2 + 1, d = (i + 1) * 2;
                triangles[tri++] = a; triangles[tri++] = d; triangles[tri++] = c;
                triangles[tri++] = a; triangles[tri++] = c; triangles[tri++] = b;
            }
            mesh.SetVertices(new System.Collections.Generic.List<Vector3>(vertices));
            mesh.SetTriangles(new System.Collections.Generic.List<int>(triangles), 0);
            mesh.RecalculateBounds();
            return mesh;
        }

        /// <summary>盲环带：R_min±width/2 圆环（RingSegments 段四边形带，ship-local）。</summary>
        static void WriteRingBand(Mesh mesh, float radiusM, float widthM)
        {
            var vertices = new Vector3[(RingSegments + 1) * 2];
            var triangles = new int[RingSegments * 6];
            float inner = Mathf.Max(0.1f, radiusM - widthM * 0.5f);
            float outer = radiusM + widthM * 0.5f;
            for (int i = 0; i <= RingSegments; i++)
            {
                float bearing = i * 360f / RingSegments;
                vertices[i * 2] = RadarOverlayMath.WedgeLocalPoint(bearing, inner);
                vertices[i * 2 + 1] = RadarOverlayMath.WedgeLocalPoint(bearing, outer);
            }
            int tri = 0;
            for (int i = 0; i < RingSegments; i++)
            {
                int a = i * 2, b = i * 2 + 1, c = (i + 1) * 2 + 1, d = (i + 1) * 2;
                triangles[tri++] = a; triangles[tri++] = d; triangles[tri++] = c;
                triangles[tri++] = a; triangles[tri++] = c; triangles[tri++] = b;
            }
            mesh.Clear();
            mesh.SetVertices(new System.Collections.Generic.List<Vector3>(vertices));
            mesh.SetTriangles(new System.Collections.Generic.List<int>(triangles), 0);
            mesh.RecalculateBounds();
        }

        GameObject SpawnRenderer(string childName, Mesh mesh, Material material)
        {
            var go = new GameObject(childName, typeof(MeshFilter), typeof(MeshRenderer));
            go.transform.SetParent(m_Root, false);
            go.GetComponent<MeshFilter>().sharedMesh = mesh;
            var renderer = go.GetComponent<MeshRenderer>();
            renderer.sharedMaterial = material;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
            return go;
        }

        void ClearWedges()
        {
            foreach (var mesh in m_WedgeMeshes) DestroyObject(mesh);
            foreach (var material in m_WedgeMaterials) DestroyObject(material);
            m_WedgeMeshes.Clear();
            m_WedgeMaterials.Clear();
            if (m_Root == null) return;
            for (int i = m_Root.childCount - 1; i >= 0; i--)
            {
                var child = m_Root.GetChild(i);
                if (child.name.StartsWith("blind wedge", StringComparison.Ordinal)) DestroyObject(child.gameObject);
            }
        }

        static Material MakeOverlayMaterial(Color color)
        {
            var material = new Material(Shader.Find("HDRP/Unlit"));
            material.SetColor("_UnlitColor", color);
            material.SetFloat("_BlendMode", 0);
            material.SetFloat("_TransparentZWrite", 0);
            material.SetFloat("_DoubleSidedEnable", 1);
            material.SetFloat("_EnableFogOnTransparent", 0);
            HDMaterial.SetSurfaceType(material, true);
            material.renderQueue = 3000;
            HDMaterial.ValidateMaterial(material);
            return material;
        }

        static void DestroyObject(UnityEngine.Object target)
        {
            if (target == null) return;
            if (Application.isPlaying) Destroy(target);
            else DestroyImmediate(target);
        }
    }
}
