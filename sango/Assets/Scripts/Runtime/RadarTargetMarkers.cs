using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using TMPro;

namespace Sango
{
    /// <summary>
    /// P1 3D 探测表现 · 检测/未检测目标区分（00-REPORT §4-2，任务书②；radar_view
    /// overlay 位）。数据 = 后端权威 radar_scans[*].display_returns（RadarScanPacket
    /// 一个 scan period 的滑窗，confidence=PD）——只标记"雷达检测到的目标"：
    /// 匹配到场景目标船的加绿色增强壳（船体 renderer 包络 ×1.15）+ TMP 标签
    /// （置信度/距离，EncounterView.CreateWorldLabel 同款世界标签）；量程内
    /// 未检测目标（盲环/盲扇区/遮挡/PD 未过）保持无标记——探测能力边界（距离/
    /// 方位/遮挡）由"有标记/无标记"一眼可读，不在 Unity 重推检测（00-REPORT §2.1
    /// 裁决 A：真相单一）。
    /// 数据缝已闭合（P1 接线，本批）：RadarScanEntry.display_returns 声明 + RadarSpokeStream.
    /// onDisplayReturns 广播（envelope hook 主线程帧面）→ 本组件 LazyWire 订阅直喂
    /// ApplyDisplayReturns；EditMode 直调口（ApplyScanJson）保留不变。门控 =
    /// radar_view overlay（同 RadarSurfaceOverlay）。
    /// </summary>
    public class RadarTargetMarkers : MonoBehaviour
    {
        [Tooltip("P0 spoke 通道（缺省场景自找；onDescriptor 取 scan_period 定过期窗）")]
        public RadarSpokeStream stream;

        [Tooltip("twin 数据面驱动（缺省场景自找；Anchor/OwnShipObject/船槽枚举）")]
        public TwinSessionDriver driver;

        [Tooltip("twin-bridge 服务（缺省场景自找；radar_view 门控源）")]
        public TwinBridgeService bridge;

        [Tooltip("无 bridge 时的开发直通（默认关——契约 §2 radar_view 默认 off）")]
        public bool showWithoutBridge;

        const float MatchRadiusM = 150f;     // 回波↔目标船匹配半径（NE 米制 + 量程尺度）
        const float SnapRadiusM = 60f;       // 滑窗重报吸附半径（同一目标跨窗续标）
        const float ShellInflate = 1.15f;    // 增强壳外扩（描边感，不遮船体细节）
        const float MarkerYM = 0.6f;         // 无船匹配壳的底面抬升（余辉盘 0.5 m 之上）
        const double ExpireFallbackS = 5.0;  // descriptor 未达时的回波过期窗
        const int VesselNamePrefixLength = 12; // "Twin vessel ".Length（TwinSessionDriver.EnsureSlot 命名）

        class Marker
        {
            public GameObject shell;
            public TextMeshProbe Label;      // TMP 世界标签（billboard）
            public Transform vessel;         // 匹配到的目标船（null = 自由壳）
            public Vector2 returnXz;         // 最近回波场景位（自由壳/失配回落位）
            public Vector3 freeSize = new Vector3(30f, 8f, 10f); // 无船匹配缺省壳
            public double lastSeenS;
            public float confidence;
        }

        /// <summary>TMP 世界标签薄封装（创建/更新/朝向相机）。</summary>
        class TextMeshProbe
        {
            public TextMeshPro text;

            public TextMeshProbe(Transform parent, string name)
            {
                var go = new GameObject(name, typeof(TextMeshPro)); // RequireComponent 自动加 MeshRenderer
                go.transform.SetParent(parent, false);
                text = go.GetComponent<TextMeshPro>();
                if (TMP_Settings.defaultFontAsset != null) text.font = TMP_Settings.defaultFontAsset;
                text.fontSize = 60f;
                text.color = new Color(0.55f, 1f, 0.7f);
                text.alignment = TextAlignmentOptions.Center;
                text.overflowMode = TextOverflowModes.Overflow;
                text.raycastTarget = false;
                text.rectTransform.sizeDelta = new Vector2(400f, 60f);
                go.transform.localScale = Vector3.one * 0.1f;
                go.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;
            }
        }

        readonly List<Marker> m_Markers = new List<Marker>();
        Transform m_Root;
        Material m_ShellMaterial;
        double m_ExpireS = ExpireFallbackS;
        int m_SizeRefreshFrame = -1;
        bool m_StreamHooked;

        /// <summary>单行诊断（HUD/日志同款式）。</summary>
        public int MarkerCount => m_Markers.Count;

        void Update()
        {
            LazyWire();
            if (m_Root == null) return;
            TwinBridge.RadarViewEffect(bridge != null ? bridge.CurrentRadarView : TwinBridge.DefaultRadarView,
                out bool overlay, out _);
            m_Root.gameObject.SetActive(overlay || showWithoutBridge);

            double simNow = driver != null ? driver.RenderSimTime : double.NaN;
            var camera = Camera.main;
            int frame = Time.frameCount;
            bool refreshSizes = frame - m_SizeRefreshFrame >= 30; // 壳尺寸 0.5 s 档（包络重取）
            if (refreshSizes) m_SizeRefreshFrame = frame;
            for (int i = m_Markers.Count - 1; i >= 0; i--)
            {
                var marker = m_Markers[i];
                if (marker.shell == null) { m_Markers.RemoveAt(i); continue; }
                if (!double.IsNaN(simNow) && simNow - marker.lastSeenS > m_ExpireS)
                {
                    DestroyObject(marker.shell);
                    if (marker.Label?.text != null) DestroyObject(marker.Label.text.gameObject);
                    m_Markers.RemoveAt(i);
                    continue;
                }
                // 匹配船跟随（检测节律 2.5 s/转，壳随船动）；无船壳停在回波位。
                Bounds bounds;
                if (marker.vessel != null && TryVesselBounds(marker.vessel, out bounds, refreshSizes))
                {
                    marker.shell.transform.position = bounds.center;
                    marker.shell.transform.localScale = Vector3.Max(bounds.extents * 2f * ShellInflate, Vector3.one);
                }
                else
                {
                    marker.shell.transform.position = new Vector3(marker.returnXz.x,
                        MarkerYM + marker.freeSize.y * 0.5f, marker.returnXz.y);
                    marker.shell.transform.localScale = marker.freeSize;
                }
                if (marker.Label?.text != null)
                {
                    var labelTransform = marker.Label.text.transform;
                    labelTransform.position = marker.shell.transform.position
                        + Vector3.up * (marker.shell.transform.localScale.y * 0.5f + 3f);
                    if (camera != null) // billboard：正面（TMP +z 面）朝向相机 = 可读不镜像
                        labelTransform.rotation = Quaternion.LookRotation(camera.transform.position - labelTransform.position);
                }
            }
        }

        void OnDestroy()
        {
            if (m_Root == null) return;
            if (Application.isPlaying) Destroy(m_Root.gameObject);
            else DestroyImmediate(m_Root.gameObject);
            m_Root = null;
            m_Markers.Clear();
            if (m_ShellMaterial != null) DestroyObject(m_ShellMaterial);
            m_ShellMaterial = null;
        }

        void LazyWire()
        {
            if (Time.frameCount % 30 == 0) // 未接线期场景检索节流
            {
                if (stream == null) stream = FindFirstObjectByType<RadarSpokeStream>();
                if (driver == null) driver = FindFirstObjectByType<TwinSessionDriver>();
                if (bridge == null) bridge = FindFirstObjectByType<TwinBridgeService>();
            }
            if (stream != null && !m_StreamHooked)
            {
                m_StreamHooked = true;
                stream.onDisplayReturns += ApplyDisplayReturns; // P1 live 接线：滑窗帧面直喂
            }
            if (stream != null && m_ExpireS == ExpireFallbackS && stream.LatestDescriptor != null
                && stream.LatestDescriptor.scan_period_s > 0)
                m_ExpireS = stream.LatestDescriptor.scan_period_s; // 过期窗 = display 滑窗寿命
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
            var host = new GameObject("Radar target markers");
            host.transform.SetParent(service.transform, false);
            var markers = host.AddComponent<RadarTargetMarkers>();
            markers.bridge = service;
            markers.driver = service.driver;
            Debug.Log("[Sango.RadarMarkers] target markers attached (radar_view overlay 位;默认隐藏)");
        }

        /// <summary>
        /// scan JSON 注入（{"display_returns":[…]}，radar_scans[*] 子集形状）：
        /// RadarDisplayScanDocument 经 JsonUtility 解析（covariance 嵌套数组静默跳过）。
        /// live 接线缝（见类注）；EditMode 直调同口。
        /// </summary>
        public void ApplyScanJson(string scanJson)
        {
            if (string.IsNullOrEmpty(scanJson)) return;
            var document = JsonUtility.FromJson<RadarDisplayScanDocument>(scanJson);
            if (document == null || document.display_returns == null) return;
            double latest = double.NegativeInfinity;
            foreach (var item in document.display_returns)
                if (item != null && item.t_s > latest) latest = item.t_s;
            ApplyDisplayReturns(document.display_returns, latest);
        }

        /// <summary>
        /// display_returns 滑窗投影：绝对 NE → 场景（RadarOverlayMath.ReturnWorldPosition）
        /// → 最近目标船匹配（NearestVesselIndex，本船 id=0 除外）→ 增强壳/标签；
        /// 跨窗吸附（SnapRadiusM）保标记稳定。锚点未定（driver.Anchor null）静默跳过。
        /// </summary>
        public void ApplyDisplayReturns(RadarDisplayReturn[] returns, double frameTimeS)
        {
            TwinAnchor? anchor = driver != null ? driver.Anchor : null;
            if (returns == null || returns.Length == 0 || !anchor.HasValue) { PruneAll(); return; }
            EnsureRoot();

            var vessels = CollectTargetVessels();
            var vesselXz = new Vector2[vessels.Count];
            for (int i = 0; i < vessels.Count; i++) vesselXz[i] = VesselXz(vessels[i]);

            foreach (var item in returns)
            {
                if (item == null) continue;
                Vector3 world = RadarOverlayMath.ReturnWorldPosition(anchor.Value, item.north_m, item.east_m, MarkerYM);
                var xz = new Vector2(world.x, world.z);
                Marker marker = FindSnapMarker(xz);
                if (marker == null)
                {
                    marker = new Marker { lastSeenS = frameTimeS };
                    marker.shell = BuildShell(marker, xz);
                    marker.Label = new TextMeshProbe(marker.shell.transform, "Marker label");
                    m_Markers.Add(marker);
                }
                marker.lastSeenS = frameTimeS;
                marker.confidence = item.confidence;
                marker.returnXz = xz;
                int vesselIndex = RadarOverlayMath.NearestVesselIndex(xz, vesselXz, MatchRadiusM);
                marker.vessel = vesselIndex >= 0 ? vessels[vesselIndex] : null;
                float rangeM = RangeFromOwnshipM(xz);
                marker.Label.text.text = RadarOverlayMath.MarkerLabelText(item.confidence, rangeM);
            }
        }

        void PruneAll()
        {
            foreach (var marker in m_Markers)
            {
                if (marker.shell != null) DestroyObject(marker.shell);
                if (marker.Label?.text != null) DestroyObject(marker.Label.text.gameObject);
            }
            m_Markers.Clear();
        }

        Marker FindSnapMarker(Vector2 xz)
        {
            Marker best = null;
            float bestSq = SnapRadiusM * SnapRadiusM;
            foreach (var marker in m_Markers)
            {
                if (marker.shell == null) continue;
                var markerXz = new Vector2(marker.shell.transform.position.x, marker.shell.transform.position.z);
                float distSq = (markerXz - xz).sqrMagnitude;
                if (distSq <= bestSq) { bestSq = distSq; best = marker; }
            }
            return best;
        }

        GameObject BuildShell(Marker marker, Vector2 xz)
        {
            var shell = GameObject.CreatePrimitive(PrimitiveType.Cube);
            StripCollider(shell);
            shell.name = "Radar detection shell";
            shell.transform.SetParent(m_Root, false);
            shell.transform.position = new Vector3(xz.x, MarkerYM + marker.freeSize.y * 0.5f, xz.y);
            shell.transform.localScale = marker.freeSize;
            var renderer = shell.GetComponent<MeshRenderer>();
            if (m_ShellMaterial == null) m_ShellMaterial = MakeShellMaterial();
            renderer.sharedMaterial = m_ShellMaterial;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
            renderer.receiveShadows = false;
            return shell;
        }

        /// <summary>twin 船槽枚举（只读）：driver 下 "Twin vessel {id} …" 命名（EnsureSlot 工艺），id=0 本船除外。</summary>
        List<Transform> CollectTargetVessels()
        {
            var vessels = new List<Transform>();
            if (driver == null) return vessels;
            foreach (Transform child in driver.transform)
            {
                if (!TryParseVesselId(child.name, out int id) || id == 0) continue;
                vessels.Add(child);
            }
            return vessels;
        }

        static bool TryParseVesselId(string name, out int id)
        {
            id = -1;
            int start = name.StartsWith("Twin vessel ", StringComparison.Ordinal) ? VesselNamePrefixLength : -1;
            if (start < 0) return false;
            int end = start;
            while (end < name.Length && char.IsDigit(name[end])) end++;
            return end > start && int.TryParse(name.Substring(start, end - start), out id);
        }

        static Vector2 VesselXz(Transform vessel) => new Vector2(vessel.position.x, vessel.position.z);

        bool TryVesselBounds(Transform vessel, out Bounds bounds, bool refresh)
        {
            bounds = default;
            if (vessel == null) return false;
            if (!refresh && m_VesselBoundsCache.TryGetValue(vessel, out bounds)) return true;
            bool any = false;
            var encapsulated = new Bounds();
            foreach (var renderer in vessel.GetComponentsInChildren<Renderer>())
            {
                if (!any) { encapsulated = renderer.bounds; any = true; }
                else encapsulated.Encapsulate(renderer.bounds);
            }
            if (!any) return false;
            bounds = encapsulated;
            m_VesselBoundsCache[vessel] = bounds;
            return true;
        }

        readonly Dictionary<Transform, Bounds> m_VesselBoundsCache = new Dictionary<Transform, Bounds>();

        float RangeFromOwnshipM(Vector2 returnXz)
        {
            var own = driver != null ? driver.OwnShipObject : null;
            if (own == null) return 0f;
            return Vector2.Distance(returnXz, VesselXz(own.transform));
        }

        void EnsureRoot()
        {
            if (m_Root != null) return;
            m_Root = new GameObject("Radar target markers root").transform;
            m_Root.SetParent(transform, false);
        }

        static Material MakeShellMaterial()
        {
            // 绿色增强壳：HDRP/Unlit 透明（TwinSituationDisplay.MeshObject 同款面设置）。
            var material = new Material(Shader.Find("HDRP/Unlit"));
            material.SetColor("_UnlitColor", new Color(0.25f, 1f, 0.5f, 0.28f));
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
            if (Application.isPlaying) Destroy(target);
            else DestroyImmediate(target);
        }

        static void StripCollider(GameObject primitive)
        {
            var collider = primitive.GetComponent<Collider>();
            if (collider == null) return;
            DestroyObject(collider);
        }
    }
}
