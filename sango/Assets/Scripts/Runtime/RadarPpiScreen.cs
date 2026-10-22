using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;
using static Sango.UiBuildHelpers;

namespace Sango
{
    /// <summary>
    /// 独立 PPI 雷达屏(00-REPORT §5 表现层件 2 / §6 P2;radar_view "ppi" 位,契约 §2 2026-10-21
    /// 演进):RenderTexture PPI(单 pass 极坐标→笛卡尔 shader,Resources/RadarPpi.shader)
    /// + UGUI 控制面板(SimulationPanel 族惯例:运行时构建、legacy Text、零场景资产依赖)。
    /// 数据源 = P0 RadarSpokeStream(只读消费:Latest 帧 + LatestDescriptor),与 web
    /// radar-ppi.js 同一份 checkpoint——逐 spoke 可对拍即本屏保真验收手段(00-REPORT §5)。
    /// v1 元素(任务书清单,web 已有能力对齐):spoke raster 余辉(0.97/帧,shader 按
    /// sim_time 年龄表达)+ 旋转扫描线(sim_time 相位,RadarSpokeDecoder.SweepPhaseRad)
    /// + 量程环 1/3·2/3·满 + 30° 方位刻度(刻度盘纹理)+ heading marker + 目标 blip
    /// (SNR 亮度 = CFAR excess 归一)+ CFAR 检测点(显示级 CA-CFAR,RadarPpiMath.CaCfarRows
    /// ——结构镜像后端 radar_video.py ca_cfar,分片执行防单帧超支)+ VRM×2/EBL×2(滑条
    /// 可调,数值联动)+ GAIN/SEA/RAIN 显示门限滑条(键名/公式镜像 web radar-video.js
    /// raster():97-98)+ HU/NU 显示模式。显式 backlog 不做:尾迹/MARPA/AIS 叠标/警报/
    /// CU·TM 运动模式/量程档切换(00-REPORT §5 表其余行)。
    /// 开关语义:radar_view 命令(web→Unity 桥)与面板本地按钮共写同一可见位,后写者胜
    /// ——桥侧轮询 TwinBridgeService.CurrentRadarView(公共只读属性),只在值变化时应用,
    /// 故本地切换不会被轮询回翻,下一次 bridge 命令再收回。TwinBridgeService.ApplyRadarView
    /// 的 P0 桩接线归通道任务所有,本屏不越界改它。
    /// 自举:--sango-twin-bridge(-local) 旗标(与 TwinBridgeService.Bootstrap 同门)才建屏,
    /// 默认隐藏(radar_view 默认 off)——Demo/非 twin 场景零变化。
    /// </summary>
    public class RadarPpiScreen : MonoBehaviour
    {
        [Tooltip("P0 spoke 通道(只读消费 Latest/LatestDescriptor;空=运行期懒找 TwinSessionDriver 建的实例)")]
        public RadarSpokeStream stream;

        [Tooltip("twin 桥服务(radar_view 开关轮询源;空=运行期懒找)")]
        public TwinBridgeService bridge;

        [Tooltip("会话驱动(渲染钟 RenderSimTime/锚点 Anchor/本船槽位 OwnShipObject;空=运行期懒找)")]
        public TwinSessionDriver driver;

        // ── 显示参数(键名镜像 web radar-ppi.js controls:gain/sea/rain/headingUp)────────

        /// <summary>GAIN 显示增益(web 键 gain;滑条 −20..20,raster 公式 gain·2)。</summary>
        public double gain;

        /// <summary>SEA 海杂波抑制(web 键 sea;滑条 0..100,抑制 sea·0.6·e^(−r/1800))。</summary>
        public double sea;

        /// <summary>RAIN 雨杂波抑制(web 键 rain;滑条 0..100,抑制 rain·0.3)。</summary>
        public double rain;

        /// <summary>VRM1/VRM2 距离(海里;0 = 隐藏,web vrmNm 同语义)。</summary>
        public double vrm1Nm, vrm2Nm;

        /// <summary>EBL1/EBL2 真方位(度,自北顺时针;web eblDeg 同语义)。</summary>
        public double ebl1Deg, ebl2Deg;

        /// <summary>HU/NU 显示模式(web headingUp 键;CU 为 backlog 不做)。</summary>
        public bool headingUp;

        /// <summary>CFAR 检测点叠层(web detections 键;默认 off 同 web)。</summary>
        public bool cfarDots;

        /// <summary>CA-CFAR 参数(Halo24Profile 默认:radar_video.py pfa/guard_cells/training_cells_per_side 同值)。</summary>
        public const double CfarPfa = 1e-4;
        public const int CfarGuardCells = 3, CfarTrainingCells = 12;

        /// <summary>检测上限(后端 RadarXParams.max_measurements_per_scan 默认 400 同值)。</summary>
        public const int DetectionCap = 400;

        const string k_ShaderName = "Sango/Twin/RadarPpi";
        const float k_DiscUiSize = 460f;      // 盘 UI 边长(正方形,盘缘到边)
        const int k_VideoRtSize = 512;        // 视频 RT 分辨率
        const int k_DialTexSize = 512;        // 刻度盘纹理边长
        const int k_RowsPerSlice = 256;       // CFAR 单帧分片行数(2M 单元分 8 片,单帧预算保险)
        const double k_DefaultScanPeriodS = 2.5;  // RadarXParams 24 rpm 默认(RadarAntennaMount.ScanRpmDefault 同源)
        const float k_PanelWidth = 340f;

        // ── 帧消费与 CFAR 流水(数据面公共入口,EditMode 直调)──────────────────────

        RadarSpokeFrame m_Frame;
        bool[] m_CfarMask;
        double[] m_CfarThreshold;
        int m_CfarRow;
        bool m_CfarDone;
        int m_CfarFound;
        readonly List<RadarPpiDetection> m_Detections = new List<RadarPpiDetection>();

        // ── 渲染资源 ────────────────────────────────────────────────────────────────

        Texture2D m_RasterTex, m_RowTimesTex, m_RowDeltaTex;
        float[] m_RowTimesScratch, m_RowDeltaScratch;
        RenderTexture m_VideoRt;
        Material m_Material;
        Sprite m_DialSprite, m_RingSprite;
        Texture2D m_DialTexture, m_RingTexture;
        RadarSpokeFrame m_UploadedFrame;

        // ── 可见位(radar_view 桥与本地按钮共写)────────────────────────────────────

        string m_AppliedRadarView = TwinBridge.DefaultRadarView;

        /// <summary>屏幕当前可见位(面板 SCREEN 按钮与 radar_view 命令共写,后写者胜)。</summary>
        public bool ScreenVisible { get; private set; }

        /// <summary>最近一转的 CFAR 检测(blip/CFAR 点共用一源,空 = 尚无解码转)。</summary>
        public IReadOnlyList<RadarPpiDetection> Detections => m_Detections;

        /// <summary>CFAR 聚类发现的簇总数(截断前;后端 count 同语义,诊断面)。</summary>
        public int CfarFoundClusters => m_CfarFound;

        // ── UI 引用 ────────────────────────────────────────────────────────────────

        Font _font;
        GameObject m_CanvasRoot;
        RectTransform m_Disc;
        RawImage m_VideoImage;
        RectTransform m_Sweep, m_HeadingPivot, m_NorthPivot;
        Image m_HeadingMarker;
        readonly Image[] m_VrmRings = new Image[2];
        readonly RectTransform[] m_EblLines = new RectTransform[2];
        readonly List<Image> m_Blips = new List<Image>();
        readonly List<Image> m_Dots = new List<Image>();
        Text m_Status, m_Readout, m_Vrm1Value, m_Vrm2Value, m_Ebl1Value, m_Ebl2Value;
        readonly Image[] m_ModeButtons = new Image[2];
        Image m_CfarButton;
        Text m_ScreenButtonLabel;

        float UiRadius => k_DiscUiSize * 0.5f; // 盘缘即 RawImage 半宽(视频盘/刻度盘同缘)

        // ── 自举(--sango-twin-bridge 族旗标;TwinBridgeService.Bootstrap 同门)────────

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            var args = Environment.GetCommandLineArgs();
            bool enabled = Array.IndexOf(args, SangoSeamConfig.TwinBridgeCliFlag) >= 0
                || Array.IndexOf(args, SangoSeamConfig.TwinBridgeLocalCliFlag) >= 0;
            if (!enabled) return;
            var service = FindFirstObjectByType<TwinBridgeService>();
            if (service == null) return; // 场景未预接线:service 侧已告警,本屏静默跳过
            var host = new GameObject("Twin radar PPI screen");
            host.transform.SetParent(service.transform, false);
            var screen = host.AddComponent<RadarPpiScreen>();
            screen.bridge = service;
            screen.driver = service.driver;
            Debug.Log("[Sango.RadarPpi] ppi screen attached (radar_view ppi/both 位;默认隐藏,radar_view 命令/面板按钮开)");
        }

        void Awake()
        {
            Application.runInBackground = true; // 采集/演示失焦不停渲染(RadarOverlay/SimulationPanel 同款)
            _font = LoadBuiltinFont();
            BuildUI();
        }

        void Update()
        {
            PollRadarView();
            if (!ScreenVisible) return;
            BindSceneRefs();
            RadarSpokeFrame frame = stream != null ? stream.Latest : null;
            if (frame != null && !ReferenceEquals(frame, m_Frame)) TakeRevolution(frame);
            if (!m_CfarDone) CfarSliceStep();
            RenderFrame(frame);
        }

        // ── radar_view 轮询与可见位 ─────────────────────────────────────────────────

        void PollRadarView()
        {
            if (bridge == null && Time.frameCount % 60 == 0) bridge = FindFirstObjectByType<TwinBridgeService>();
            if (bridge == null) return;
            string current = bridge.CurrentRadarView;
            if (current != m_AppliedRadarView) ApplyRadarView(current);
        }

        /// <summary>
        /// radar_view 词汇 → 屏幕可见位(效果面 = TwinBridge.RadarViewEffect 纯函数;
        /// ppi/both 开,off/overlay 关)。EditMode 可直调(UI 未建时只动状态位)。
        /// </summary>
        public void ApplyRadarView(string radarView)
        {
            m_AppliedRadarView = radarView;
            TwinBridge.RadarViewEffect(radarView, out _, out bool ppi);
            SetScreenVisible(ppi);
        }

        /// <summary>设置可见位(桥命令/面板按钮共入;UI 已建时同步 canvas 激活态)。</summary>
        public void SetScreenVisible(bool visible)
        {
            if (ScreenVisible == visible) return;
            ScreenVisible = visible;
            if (m_CanvasRoot != null) m_CanvasRoot.SetActive(visible);
            if (m_ScreenButtonLabel != null) m_ScreenButtonLabel.text = visible ? "SCREEN ON" : "SCREEN OFF";
            Debug.Log($"[Sango.RadarPpi] screen {(visible ? "on" : "off")} (radar_view={m_AppliedRadarView})");
        }

        void BindSceneRefs()
        {
            if (Time.frameCount % 60 != 0) return; // 惰性绑定低频重试(雷达流/驱动均晚于本屏出现)
            if (stream == null) stream = FindFirstObjectByType<RadarSpokeStream>();
            if (driver == null) driver = FindFirstObjectByType<TwinSessionDriver>();
            if (bridge == null) bridge = FindFirstObjectByType<TwinBridgeService>();
        }

        // ── 帧消费与 CFAR 分片流水(纯数据面,EditMode 直调)─────────────────────────

        /// <summary>
        /// 接收一转解码产物(P0 通道 Latest;运行期 Update 自动调,EditMode 测试直调):
        /// 重置 CFAR 流水(掩膜/门限缓冲按维度复用)+ 清空检测。栅格纹理上传留渲染路径
        /// (EditMode 无渲染依赖)。
        /// </summary>
        public void TakeRevolution(RadarSpokeFrame frame)
        {
            if (frame == null || frame.raster == null || frame.spokes < 1 || frame.bins < 1) return;
            m_Frame = frame;
            int cells = checked(frame.spokes * frame.bins);
            if (m_CfarMask == null || m_CfarMask.Length != cells)
            {
                m_CfarMask = new bool[cells];
                m_CfarThreshold = new double[cells];
            }
            m_CfarRow = 0;
            m_CfarDone = false;
            m_Detections.Clear();
        }

        /// <summary>
        /// CFAR 分片步进:每次调用处理 ≤ k_RowsPerSlice 行(单帧预算保险);末片完成后
        /// 聚类出检测。返回流水是否完成(无帧恒 true)。
        /// </summary>
        public bool CfarSliceStep()
        {
            if (m_Frame == null || m_CfarDone) return true;
            int rowEnd = Math.Min(m_CfarRow + k_RowsPerSlice, m_Frame.spokes);
            RadarPpiMath.CaCfarRows(m_Frame.raster, m_Frame.spokes, m_Frame.bins, m_CfarRow, rowEnd,
                CfarPfa, CfarGuardCells, CfarTrainingCells, m_CfarMask, m_CfarThreshold);
            m_CfarRow = rowEnd;
            if (m_CfarRow >= m_Frame.spokes)
            {
                m_CfarFound = RadarPpiMath.ClusterDetections(m_Frame.raster, m_CfarMask, m_CfarThreshold,
                    m_Frame.spokes, m_Frame.bins, m_Frame.rowOriginsNeM, m_Frame.rowBearingsRad,
                    ResolveScaleM(m_Frame.rangeM, stream != null ? stream.LatestDescriptor : null),
                    DetectionCap, m_Detections);
                m_CfarDone = true;
            }
            return m_CfarDone;
        }

        // ── 几何/时间解析(纯函数面,EditMode 直测)───────────────────────────────────

        /// <summary>量程链:视频帧 range_m → 描述子 range_scale_nm×1852 → web 默认 6 nm
        /// (radar-ppi.js buildPpiModel resolvedScaleNm 同链;帧值 = 后端 active_range_m,
        /// 与描述子档一致,链式回退为容错)。</summary>
        public static double ResolveScaleM(double frameRangeM, RadarPpiDescriptor descriptor)
            => frameRangeM > 0 ? frameRangeM
            : descriptor != null && descriptor.range_scale_nm > 0 ? descriptor.range_scale_nm * RadarPpiMath.NmPerM
            : 6.0 * RadarPpiMath.NmPerM;

        /// <summary>
        /// 本船会话 NE = 锚点 + (场景位 − 登记平移)(TwinPose.ScenePosition 的逆变换;
        /// east→x、north→z,锚点域大数减法在 double 域完成)。
        /// </summary>
        public static void OwnNeFromScene(Vector3 scenePos, TwinAnchor anchor, out double northM, out double eastM)
        {
            northM = anchor.NorthM + (scenePos.z - anchor.LandingM.y);
            eastM = anchor.EastM + (scenePos.x - anchor.LandingM.x);
        }

        /// <summary>
        /// 行差打包(每行 本船NE − 行源NE,double 运算后落 float——7e6 级大数减法必须在
        /// CPU double 域完成,GPU float 直算会吞位):RGFloat 纹理通道序 R=北差、G=东差
        /// (shader _RowDelta 同序)。行源缺行 → 0(该行视频由行时间门另弃)。
        /// </summary>
        public static void ComputeRowDeltas(double ownNorthM, double ownEastM, double[][] rowOriginsNeM, float[] deltas)
        {
            int rows = deltas.Length / 2;
            for (int r = 0; r < rows; r++)
            {
                double[] origin = rowOriginsNeM != null && r < rowOriginsNeM.Length ? rowOriginsNeM[r] : null;
                deltas[2 * r] = origin != null ? (float)(ownNorthM - origin[0]) : 0f;
                deltas[2 * r + 1] = origin != null ? (float)(ownEastM - origin[1]) : 0f;
            }
        }

        double ResolveSimTime(RadarSpokeFrame frame)
        {
            double sim = driver != null ? driver.RenderSimTime : double.NaN;
            if (double.IsNaN(sim)) sim = frame != null ? frame.tS : 0.0;
            return sim;
        }

        void ResolveOwnPose(RadarSpokeFrame frame, out double ownNorthM, out double ownEastM, out double headingDeg)
        {
            GameObject ship = driver != null ? driver.OwnShipObject : null;
            TwinAnchor? anchor = driver != null ? driver.Anchor : null;
            if (ship != null && anchor.HasValue)
            {
                OwnNeFromScene(ship.transform.position, anchor.Value, out ownNorthM, out ownEastM);
                headingDeg = ship.transform.eulerAngles.y; // TwinPose:rotation.y = +psi·Rad2Deg(北偏东顺时针)
                return;
            }
            // 回退:无驱动/锚点/本船槽位时以行源[0]为原点参考(静止近似,NU 相对显示)
            double[] origin = frame != null && frame.rowOriginsNeM != null && frame.rowOriginsNeM.Length > 0
                ? frame.rowOriginsNeM[0] : null;
            ownNorthM = origin != null ? origin[0] : 0.0;
            ownEastM = origin != null ? origin[1] : 0.0;
            headingDeg = 0.0;
        }

        // ── 渲染路径(仅运行期可见时执行)───────────────────────────────────────────

        void RenderFrame(RadarSpokeFrame frame)
        {
            double simTime = ResolveSimTime(frame);
            RadarPpiDescriptor descriptor = stream != null ? stream.LatestDescriptor : null;
            double scanPeriod = descriptor != null && descriptor.scan_period_s > 0
                ? descriptor.scan_period_s : k_DefaultScanPeriodS;
            double scaleM = ResolveScaleM(frame != null ? frame.rangeM : 0.0, descriptor);
            ResolveOwnPose(frame, out double ownN, out double ownE, out double headingDeg);
            double rotation = RadarPpiMath.DisplayRotationRad(headingUp, headingDeg * Math.PI / 180.0);

            bool videoValid = frame != null && frame.raster != null
                && frame.rowTimesS != null && frame.rowTimesS.Length == frame.spokes
                && frame.rowOriginsNeM != null && frame.rowOriginsNeM.Length == frame.spokes;
            EnsureGraphics(frame, videoValid); // 无帧也建材质/RT(底色+扫描线常显,web surface 同语义)
            if (m_Material == null || m_VideoRt == null) return; // shader 缺失等:保状态,弃渲染
            if (videoValid)
            {
                UploadRaster(frame);
                UploadRowTextures(frame, ownN, ownE);
            }
            m_Material.SetFloat("_Spokes", frame != null ? frame.spokes : 2048);
            m_Material.SetFloat("_Bins", frame != null ? frame.bins : 1024);
            m_Material.SetFloat("_VideoRangeM", (float)scaleM);
            m_Material.SetFloat("_ScaleM", (float)scaleM);
            m_Material.SetFloat("_Rotation", (float)rotation);
            m_Material.SetFloat("_SimTime", (float)simTime);
            m_Material.SetFloat("_ScanPeriod", (float)scanPeriod);
            m_Material.SetFloat("_Gain", (float)gain);
            m_Material.SetFloat("_Sea", (float)sea);
            m_Material.SetFloat("_Rain", (float)rain);
            m_Material.SetFloat("_SweepRad",
                (float)RadarSpokeDecoder.SweepPhaseRad(simTime, scanPeriod));
            m_Material.SetFloat("_VideoValid", videoValid ? 1f : 0f);
            Graphics.Blit(m_RasterTex != null ? m_RasterTex : Texture2D.blackTexture, m_VideoRt, m_Material);

            UpdateOverlayUi(frame, simTime, scanPeriod, scaleM, rotation, ownN, ownE, headingDeg);
        }

        void EnsureGraphics(RadarSpokeFrame frame, bool videoValid)
        {
            if (m_Material == null)
            {
                // Resources 路径保 player 构建可含(LidarViewPass.Setup 同工艺注释)
                Shader shader = Shader.Find(k_ShaderName);
                if (shader == null) shader = Resources.Load<Shader>("RadarPpi");
                if (shader == null)
                {
                    Debug.LogError($"[Sango.RadarPpi] {k_ShaderName} not found (expected Resources/RadarPpi.shader)");
                    return;
                }
                m_Material = new Material(shader);
            }
            if (m_VideoRt == null)
            {
                m_VideoRt = new RenderTexture(k_VideoRtSize, k_VideoRtSize, 0, RenderTextureFormat.ARGB32);
                m_VideoRt.Create();
                if (m_VideoImage != null)
                {
                    m_VideoImage.texture = m_VideoRt;
                    m_VideoImage.color = Color.white; // texture 到位:取消底板暗色 tint(SimulationPanel 预览同款)
                }
            }
            if (!videoValid || frame == null) return;
            int spokes = frame.spokes, bins = frame.bins;
            if (m_RasterTex == null || m_RasterTex.width != bins || m_RasterTex.height != spokes)
            {
                if (m_RasterTex != null) Destroy(m_RasterTex);
                m_RasterTex = new Texture2D(bins, spokes, TextureFormat.R8, false, true) // linear:数据纹理
                    { filterMode = FilterMode.Bilinear, wrapMode = TextureWrapMode.Clamp };
                m_UploadedFrame = null;
            }
            if (m_RowTimesTex == null || m_RowTimesTex.width != spokes)
            {
                if (m_RowTimesTex != null) Destroy(m_RowTimesTex);
                m_RowTimesTex = new Texture2D(spokes, 1, TextureFormat.RFloat, false, true)
                    { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
                m_RowTimesScratch = new float[spokes];
                m_UploadedFrame = null;
            }
            if (m_RowDeltaTex == null || m_RowDeltaTex.width != spokes)
            {
                if (m_RowDeltaTex != null) Destroy(m_RowDeltaTex);
                m_RowDeltaTex = new Texture2D(spokes, 1, TextureFormat.RGFloat, false, true)
                    { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
                m_RowDeltaScratch = new float[spokes * 2];
            }
        }

        /// <summary>栅格上传(新转一次;R8 行主序字节直入,u=bin、v=row 与 shader 同序;
        /// 行时间随转上传,−1 = 未采集行,shader 同判)。float 纹理载荷经 BlockCopy 落
        /// byte[](LoadRawTextureData 的 byte[] 重载在全部 scripting profile 恒在)。</summary>
        void UploadRaster(RadarSpokeFrame frame)
        {
            if (ReferenceEquals(m_UploadedFrame, frame)) return;
            m_RasterTex.LoadRawTextureData(frame.raster);
            m_RasterTex.Apply(false, false);
            for (int r = 0; r < frame.spokes; r++)
                m_RowTimesScratch[r] = (float)frame.rowTimesS[r];
            UploadFloats(m_RowTimesTex, m_RowTimesScratch, ref m_RowTimesBytes);
            m_UploadedFrame = frame;
        }

        /// <summary>行差上传(每帧:本船在动;行源静态,差量随帧)。</summary>
        void UploadRowTextures(RadarSpokeFrame frame, double ownNorthM, double ownEastM)
        {
            ComputeRowDeltas(ownNorthM, ownEastM, frame.rowOriginsNeM, m_RowDeltaScratch);
            UploadFloats(m_RowDeltaTex, m_RowDeltaScratch, ref m_RowDeltaBytes);
        }

        byte[] m_RowTimesBytes, m_RowDeltaBytes; // 精确长度 byte 缓冲(维度变化时才重建)

        static void UploadFloats(Texture2D texture, float[] values, ref byte[] buffer)
        {
            int byteCount = values.Length * 4;
            if (buffer == null || buffer.Length != byteCount) buffer = new byte[byteCount];
            System.Buffer.BlockCopy(values, 0, buffer, 0, byteCount);
            texture.LoadRawTextureData(buffer);
            texture.Apply(false, false);
        }

        // ── UGUI 构建(SimulationPanel 族惯例:运行时构建、legacy Text、零资产依赖)────

        void BuildUI()
        {
            var canvasGo = new GameObject("RadarPpiCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            canvasGo.transform.SetParent(transform, false);
            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            m_CanvasRoot = canvasGo;
            EnsureEventSystem();

            // 底中簇:盘 (0.5,0) 偏移 (−300,+30) → 参考系 x∈[430,890];控制列偏移 (+150,+30)
            // → x∈[940,1280] —— 右缘避让 SimulationPanel(1500..1900)与 RadarOverlay(1176..1480)
            // 的同一 1920×1080 参考系分列惯例(RadarOverlay.BuildUI 注同源)。
            m_Disc = NewRect("Disc", canvasGo.transform);
            m_Disc.anchorMin = m_Disc.anchorMax = m_Disc.pivot = new Vector2(0.5f, 0f);
            m_Disc.anchoredPosition = new Vector2(-300f, 30f);
            m_Disc.sizeDelta = new Vector2(k_DiscUiSize, k_DiscUiSize);

            m_VideoImage = m_Disc.gameObject.AddComponent<RawImage>();
            m_VideoImage.raycastTarget = false;
            m_VideoImage.color = new Color(0.05f, 0.08f, 0.10f, 0.92f); // 无视频时底板(SimulationPanel 预览同款)

            var dial = NewRect("Dial", m_Disc);
            Stretch(dial, 0f, 0f, 0f, 0f); // 与盘同 rect(拉伸铺满)
            var dialImage = dial.gameObject.AddComponent<Image>();
            m_DialSprite = MakeDialSprite();
            dialImage.sprite = m_DialSprite;
            dialImage.raycastTarget = false;

            // 扫描线:细长条 pivot 在盘心一端,绕 z 旋转(−角 = 屏幕顺时针;RadarOverlay 同款)。
            m_Sweep = NewRect("Sweep", m_Disc);
            m_Sweep.anchorMin = m_Sweep.anchorMax = new Vector2(0.5f, 0.5f);
            m_Sweep.pivot = new Vector2(0f, 0.5f);
            m_Sweep.anchoredPosition = Vector2.zero;
            m_Sweep.sizeDelta = new Vector2(UiRadius, 3f);
            var sweepImg = m_Sweep.gameObject.AddComponent<Image>();
            sweepImg.color = new Color(0.45f, 1f, 0.6f, 0.9f);
            sweepImg.raycastTarget = false;

            // heading marker(MSC.192 5.14.2):盘缘内侧短线,显示角 = 艏向 − 显示旋转(HU 恒向上)。
            m_HeadingPivot = NewRect("HeadingPivot", m_Disc);
            m_HeadingPivot.anchorMin = m_HeadingPivot.anchorMax = m_HeadingPivot.pivot = new Vector2(0.5f, 0.5f);
            m_HeadingPivot.sizeDelta = Vector2.zero;
            var hm = NewRect("HeadingMarker", m_HeadingPivot);
            hm.anchorMin = hm.anchorMax = hm.pivot = new Vector2(0.5f, 1f);
            hm.anchoredPosition = new Vector2(0f, -2f);
            hm.sizeDelta = new Vector2(2f, 16f);
            m_HeadingMarker = hm.gameObject.AddComponent<Image>();
            m_HeadingMarker.color = new Color(1f, 0.95f, 0.6f, 0.95f);
            m_HeadingMarker.raycastTarget = false;

            // 北标记(MSC.192 5.14.2 north mark;HU 下随显示旋转绕盘)。
            m_NorthPivot = NewRect("NorthPivot", m_Disc);
            m_NorthPivot.anchorMin = m_NorthPivot.anchorMax = m_NorthPivot.pivot = new Vector2(0.5f, 0.5f);
            m_NorthPivot.sizeDelta = Vector2.zero;
            var north = CreateLabel(m_NorthPivot, "North", "N", 18, TextAnchor.MiddleCenter, new Color(0.6f, 1f, 0.7f));
            north.rectTransform.anchorMin = north.rectTransform.anchorMax = north.rectTransform.pivot = new Vector2(0.5f, 0f);
            north.rectTransform.anchoredPosition = new Vector2(0f, UiRadius + 4f);
            north.rectTransform.sizeDelta = new Vector2(24f, 22f);

            // VRM×2(环)与 EBL×2(线)——web #E6B94D 同色。
            m_RingSprite = MakeRingSprite();
            for (int i = 0; i < 2; i++)
            {
                var vrm = NewRect($"Vrm.{i + 1}", m_Disc);
                vrm.anchorMin = vrm.anchorMax = vrm.pivot = new Vector2(0.5f, 0.5f);
                vrm.gameObject.SetActive(false);
                var vrmImage = vrm.gameObject.AddComponent<Image>();
                vrmImage.sprite = m_RingSprite;
                vrmImage.color = new Color(0.902f, 0.725f, 0.302f, 0.95f);
                vrmImage.raycastTarget = false;
                m_VrmRings[i] = vrmImage;

                var ebl = NewRect($"Ebl.{i + 1}", m_Disc);
                ebl.anchorMin = ebl.anchorMax = new Vector2(0.5f, 0.5f);
                ebl.pivot = new Vector2(0f, 0.5f);
                ebl.anchoredPosition = Vector2.zero;
                ebl.sizeDelta = new Vector2(UiRadius, 2f);
                ebl.gameObject.SetActive(false);
                var eblImage = ebl.gameObject.AddComponent<Image>();
                eblImage.color = new Color(0.902f, 0.725f, 0.302f, 0.9f);
                eblImage.raycastTarget = false;
                m_EblLines[i] = ebl;
            }

            BuildPanel(canvasGo.transform);

            m_CanvasRoot.SetActive(ScreenVisible);
            RefreshReadout(0.0, k_DefaultScanPeriodS, ResolveScaleM(0.0, null));
        }

        void BuildPanel(Transform canvas)
        {
            var panel = NewRect("Panel", canvas);
            panel.anchorMin = panel.anchorMax = panel.pivot = new Vector2(0.5f, 0f);
            panel.anchoredPosition = new Vector2(150f, 30f);
            panel.sizeDelta = new Vector2(k_PanelWidth, 640f);
            var panelImage = panel.gameObject.AddComponent<Image>();
            panelImage.color = new Color(0f, 0f, 0f, 0.7f);

            float y = -18f;
            var title = CreateLabel(panel, "Title", "X-BAND RADAR PPI", 22, TextAnchor.MiddleLeft, Color.white);
            AnchorTop(title.rectTransform, 16f, y, k_PanelWidth - 32f, 28f);
            y -= 34f;

            m_Status = CreateLabel(panel, "Status", "radar stream idle", 13, TextAnchor.MiddleLeft,
                new Color(0.6f, 0.9f, 0.65f));
            AnchorTop(m_Status.rectTransform, 16f, y, k_PanelWidth - 32f, 18f);
            y -= 24f;

            // 模式/叠层/屏开关按钮排(HU-NU web heading 键镜像;CFAR web detections 键镜像;
            // 内宽 308 → 74×4 + 4×3 间隙)。
            var nuButton = CreateButton(panel, "NuButton", "NU", 16f, y, 74f, () => SetHeadingUp(false));
            var huButton = CreateButton(panel, "HuButton", "HU", 94f, y, 74f, () => SetHeadingUp(true));
            m_ModeButtons[0] = nuButton;
            m_ModeButtons[1] = huButton;
            var cfarButton = CreateButton(panel, "CfarButton", "CFAR", 172f, y, 74f, () => SetCfarDots(!cfarDots));
            m_CfarButton = cfarButton;
            CreateScreenButton(panel, 250f, y, 74f);
            y -= 46f;

            y = SectionLabel(panel, y, "DISPLAY CONTROLS  (web key mirror)");

            var gainSlider = CreateSlider(panel, "Gain", -20f, 20f, 0f, true,
                v => { gain = Mathf.RoundToInt(v); RefreshReadoutOnly(); });
            y = LabeledSlider(panel, y, "GAIN  (gain)", gainSlider);

            var seaSlider = CreateSlider(panel, "Sea", 0f, 100f, 0f, true,
                v => { sea = Mathf.RoundToInt(v); });
            y = LabeledSlider(panel, y, "SEA   (sea)", seaSlider);

            var rainSlider = CreateSlider(panel, "Rain", 0f, 100f, 0f, true,
                v => { rain = Mathf.RoundToInt(v); });
            y = LabeledSlider(panel, y, "RAIN  (rain)", rainSlider);

            y = SectionLabel(panel, y, "VRM / EBL  (linked readout)");

            m_Vrm1Value = AddValueLabel(panel, y);
            var vrm1 = CreateSlider(panel, "Vrm1", 0f, 24f, 0f, false, v => { vrm1Nm = Mathf.Round(v * 20f) / 20f; RefreshVrmLabels(); });
            y = LabeledSlider(panel, y, "VRM1", vrm1);
            m_Vrm2Value = AddValueLabel(panel, y);
            var vrm2 = CreateSlider(panel, "Vrm2", 0f, 24f, 0f, false, v => { vrm2Nm = Mathf.Round(v * 20f) / 20f; RefreshVrmLabels(); });
            y = LabeledSlider(panel, y, "VRM2", vrm2);
            m_Ebl1Value = AddValueLabel(panel, y);
            var ebl1 = CreateSlider(panel, "Ebl1", 0f, 359f, 0f, true, v => { ebl1Deg = Mathf.RoundToInt(v); RefreshReadoutOnly(); });
            y = LabeledSlider(panel, y, "EBL1", ebl1);
            m_Ebl2Value = AddValueLabel(panel, y);
            var ebl2 = CreateSlider(panel, "Ebl2", 0f, 359f, 0f, true, v => { ebl2Deg = Mathf.RoundToInt(v); RefreshReadoutOnly(); });
            y = LabeledSlider(panel, y, "EBL2", ebl2);

            m_Readout = CreateLabel(panel, "Readout", "", 13, TextAnchor.MiddleLeft, new Color(0.75f, 0.85f, 0.95f));
            AnchorTop(m_Readout.rectTransform, 16f, y, k_PanelWidth - 32f, 40f);
            y -= 46f;

            var hint = CreateLabel(panel, "Hint",
                "trails / MARPA / AIS / alarms = backlog", 13, TextAnchor.MiddleLeft, new Color(0.55f, 0.58f, 0.62f));
            AnchorTop(hint.rectTransform, 16f, y, k_PanelWidth - 32f, 18f);
            y -= 20f;

            panel.sizeDelta = new Vector2(k_PanelWidth, -y + 12f);
            RefreshVrmLabels();
            RefreshModeButtons();
        }

        Text AddValueLabel(RectTransform panel, float y)
        {
            var label = CreateLabel(panel, "Value", "", 15, TextAnchor.MiddleRight, new Color(0.75f, 0.85f, 0.95f));
            AnchorTop(label.rectTransform, k_PanelWidth - 156f, y, 140f, 22f);
            return label;
        }

        void SetHeadingUp(bool value)
        {
            headingUp = value;
            RefreshModeButtons();
            RefreshReadoutOnly();
            Debug.Log($"[Sango.RadarPpi] display mode -> {(value ? "HU" : "NU")} (web headingUp 键镜像)");
        }

        void SetCfarDots(bool value)
        {
            cfarDots = value;
            RefreshModeButtons();
            Debug.Log($"[Sango.RadarPpi] CFAR dots layer -> {(value ? "on" : "off")} (web detections 键镜像)");
        }

        void RefreshModeButtons()
        {
            if (m_ModeButtons[0] != null)
                m_ModeButtons[0].color = headingUp
                    ? new Color(0.16f, 0.22f, 0.30f, 0.95f)
                    : new Color(0.30f, 0.55f, 0.85f, 0.95f);
            if (m_ModeButtons[1] != null)
                m_ModeButtons[1].color = headingUp
                    ? new Color(0.30f, 0.55f, 0.85f, 0.95f)
                    : new Color(0.16f, 0.22f, 0.30f, 0.95f);
            if (m_CfarButton != null)
                m_CfarButton.color = cfarDots
                    ? new Color(0.30f, 0.55f, 0.85f, 0.95f)
                    : new Color(0.16f, 0.22f, 0.30f, 0.95f);
        }

        void CreateScreenButton(RectTransform panel, float x, float y, float width)
        {
            var button = CreateButton(panel, "ScreenButton", "SCREEN OFF", x, y, width, () => SetScreenVisible(!ScreenVisible));
            m_ScreenButtonLabel = button.GetComponentInChildren<Text>();
        }

        // ── 逐帧 UI 刷新 ────────────────────────────────────────────────────────────

        void UpdateOverlayUi(RadarSpokeFrame frame, double simTime, double scanPeriod, double scaleM,
            double rotation, double ownN, double ownE, double headingDeg)
        {
            double sweep = RadarPpiMath.SweepDisplayAngleRad(simTime, scanPeriod, rotation);
            if (m_Sweep != null)
                m_Sweep.localRotation = Quaternion.Euler(0f, 0f, -(float)(sweep * Mathf.Rad2Deg));

            double headingDisplay = RadarPpiMath.WrapPositive(headingDeg * Math.PI / 180.0 - rotation);
            if (m_HeadingPivot != null)
                m_HeadingPivot.localRotation = Quaternion.Euler(0f, 0f, -(float)(headingDisplay * Mathf.Rad2Deg));

            if (m_NorthPivot != null)
                m_NorthPivot.localRotation = Quaternion.Euler(0f, 0f, (float)(rotation * Mathf.Rad2Deg)); // 北显示方位 = −旋转 → pivot 取 +旋转

            double scaleNm = scaleM / RadarPpiMath.NmPerM;
            var vrmNm = new[] { vrm1Nm, vrm2Nm };
            var eblDeg = new[] { ebl1Deg, ebl2Deg };
            for (int i = 0; i < 2; i++)
            {
                var ring = m_VrmRings[i];
                if (ring != null)
                {
                    bool visible = RadarPpiMath.VrmVisible(vrmNm[i], scaleNm);
                    ring.gameObject.SetActive(visible);
                    if (visible)
                    {
                        float size = (float)(RadarPpiMath.VrmRadiusFraction(vrmNm[i], scaleNm) * k_DiscUiSize);
                        ring.rectTransform.sizeDelta = new Vector2(size, size);
                    }
                }
                var ebl = m_EblLines[i];
                if (ebl != null)
                {
                    bool visible = eblDeg[i] > 0;
                    ebl.gameObject.SetActive(visible);
                    if (visible)
                    {
                        double angle = RadarPpiMath.EblDisplayAngleRad(eblDeg[i], rotation);
                        ebl.localRotation = Quaternion.Euler(0f, 0f, -(float)(angle * Mathf.Rad2Deg));
                    }
                }
            }

            UpdateBlips(frame, simTime, scanPeriod, scaleM, rotation, ownN, ownE);

            if (m_Status != null)
                m_Status.text = stream != null ? stream.Status : "no spoke stream (waiting for radar session)";
            RefreshReadout(rotation, scanPeriod, scaleM);
        }

        void UpdateBlips(RadarSpokeFrame frame, double simTime, double scanPeriod, double scaleM,
            double rotation, double ownN, double ownE)
        {
            // 年龄门:整转过期(> 1.1 圈)隐藏——web raster 年龄门同系数。
            bool fresh = frame != null && simTime - frame.tS <= scanPeriod * RadarPpiMath.AgeGateRevolutions;
            int shown = 0;
            if (fresh)
            {
                for (int i = 0; i < m_Detections.Count; i++)
                {
                    var detection = m_Detections[i];
                    if (!RadarPpiMath.BlipDisplayNormalized(detection.NorthM - ownN, detection.EastM - ownE,
                        scaleM, rotation, out double n, out double e)) continue;
                    var position = new Vector2((float)e, (float)n) * UiRadius;
                    float intensity = (float)detection.Intensity;
                    // 目标 blip:亮度/半径随 SNR 代理(web draw:374-375 同式:2+2.5·intensity / α=0.35+0.6·intensity)
                    Image blip = EnsurePooled(m_Blips, shown, "Blip");
                    blip.gameObject.SetActive(true);
                    blip.rectTransform.anchoredPosition = position;
                    float size = 3f + 4f * intensity;
                    blip.rectTransform.sizeDelta = new Vector2(size, size);
                    blip.color = new Color(0.224f, 0.851f, 0.541f, 0.35f + 0.6f * intensity);
                    if (cfarDots)
                    {
                        Image dot = EnsurePooled(m_Dots, shown, "CfarDot");
                        dot.gameObject.SetActive(true);
                        dot.rectTransform.anchoredPosition = position;
                        dot.rectTransform.sizeDelta = new Vector2(3f, 3f);
                        dot.color = new Color(0.9f, 1f, 0.95f, 0.8f);
                    }
                    shown++;
                }
            }
            HidePool(m_Blips, fresh ? shown : 0);
            HidePool(m_Dots, cfarDots && fresh ? shown : 0);
        }

        Image EnsurePooled(List<Image> pool, int index, string name)
        {
            while (pool.Count <= index)
            {
                var rect = NewRect($"{name}.{pool.Count}", m_Disc);
                rect.anchorMin = rect.anchorMax = new Vector2(0.5f, 0.5f);
                rect.sizeDelta = new Vector2(4f, 4f);
                var image = rect.gameObject.AddComponent<Image>();
                image.raycastTarget = false;
                pool.Add(image);
            }
            return pool[index];
        }

        static void HidePool(List<Image> pool, int from)
        {
            for (int i = from; i < pool.Count; i++)
                if (pool[i] != null) pool[i].gameObject.SetActive(false);
        }

        void RefreshVrmLabels()
        {
            if (m_Vrm1Value != null) m_Vrm1Value.text = VrmText(vrm1Nm);
            if (m_Vrm2Value != null) m_Vrm2Value.text = VrmText(vrm2Nm);
        }

        static string VrmText(double vrmNm)
            => vrmNm > 0 ? $"{vrmNm:0.00} nm · {vrmNm * RadarPpiMath.NmPerM:0} m" : "off";

        void RefreshEblLabels(double rotation)
        {
            if (m_Ebl1Value != null) m_Ebl1Value.text = EblText(ebl1Deg, rotation);
            if (m_Ebl2Value != null) m_Ebl2Value.text = EblText(ebl2Deg, rotation);
        }

        static string EblText(double eblDeg, double rotation)
        {
            if (eblDeg <= 0) return "off";
            double relative = RadarPpiMath.WrapPositive(eblDeg * Math.PI / 180.0 - rotation) * 180.0 / Math.PI;
            return $"{eblDeg:000}°T" + (rotation != 0 ? $" · {relative:000}°R" : "");
        }

        void RefreshReadoutOnly() => RefreshReadout(m_LastRotationRad, m_LastScanPeriodS, m_LastScaleM);

        double m_LastRotationRad, m_LastScanPeriodS, m_LastScaleM;

        void RefreshReadout(double rotation, double scanPeriod, double scaleM)
        {
            m_LastRotationRad = rotation;
            m_LastScanPeriodS = scanPeriod;
            m_LastScaleM = scaleM;
            if (m_Readout == null) return;
            double scaleNm = scaleM / RadarPpiMath.NmPerM;
            double rpm = scanPeriod > 0 ? 60.0 / scanPeriod : 0.0;
            m_Readout.text =
                $"SCALE {scaleNm:0.##} nm ({scaleM:0} m) · {rpm:0} RPM · blips {m_Detections.Count}\n" +
                $"VRM1 {VrmText(vrm1Nm)} · VRM2 {VrmText(vrm2Nm)}\n" +
                $"EBL1 {EblText(ebl1Deg, rotation)} · EBL2 {EblText(ebl2Deg, rotation)}";
            RefreshEblLabels(rotation);
        }

        // ── 运行时生成纹理(RadarOverlay.MakeDiscSprite 同工艺)────────────────────

        /// <summary>刻度盘纹理:量程环 1/3·2/3·满 + 十字刻线 + 30° 方位刻度(90° 加长)
        /// + 亮盘缘——web draw:334-353 元素集,北向上(+x 右 +y 上与 UI 一致)。</summary>
        Sprite MakeDialSprite()
        {
            int size = k_DialTexSize;
            float half = size * 0.5f;
            float radius = half - 1f;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            var clear = new Color(0f, 0f, 0f, 0f);
            var ring = new Color(0.118f, 0.302f, 0.227f, 0.9f);    // web --ppi-grid #1E4D3A
            var cross = new Color(0.118f, 0.302f, 0.227f, 0.45f);
            var rim = new Color(0.118f, 0.302f, 0.227f, 1f);
            var pixels = new Color[size * size];
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = x + 0.5f - half;
                    float dy = y + 0.5f - half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    var c = clear;
                    if (r <= radius)
                    {
                        bool onRing = Mathf.Abs(r - radius) < 1.5f
                            || Mathf.Abs(r - radius * (2f / 3f)) < 1.25f
                            || Mathf.Abs(r - radius * (1f / 3f)) < 1.25f;
                        if (onRing) c = ring;
                        else if (Mathf.Abs(dx) < 1f || Mathf.Abs(dy) < 1f) c = cross; // 十字
                        else
                        {
                            // 30° 方位刻度:90° 整倍加长(web :348 inner = radius − (deg%90==0 ? 8 : 4) 同分档)
                            float az = Mathf.Atan2(dx, dy) * Mathf.Rad2Deg; // 自北顺时针(+y 北 +x 东)
                            float azDeg = Mathf.Repeat(az, 30f);
                            float distToTick = Mathf.Min(azDeg, 30f - azDeg) * Mathf.Deg2Rad * Mathf.Max(r, 1f);
                            bool cardinal = Mathf.Abs(Mathf.Repeat(az + 15f, 90f) - 15f) < 0.01f;
                            float inner = radius - (cardinal ? 10f : 5f);
                            if (r >= inner && distToTick < 1f) c = ring;
                        }
                    }
                    else if (r <= radius + 2f) c = rim;
                    pixels[y * size + x] = c;
                }
            }
            tex.SetPixels(pixels);
            tex.filterMode = FilterMode.Bilinear;
            tex.Apply(false, true);
            m_DialTexture = tex;
            return Sprite.Create(tex, new Rect(0f, 0f, size, size), new Vector2(0.5f, 0.5f), size);
        }

        /// <summary>VRM 环 sprite(白色细环,Image 着色 #E6B94D;直径 = 分率 × 盘径)。</summary>
        Sprite MakeRingSprite()
        {
            const int size = 128;
            float half = size * 0.5f;
            float radius = half - 2f;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
            var pixels = new Color[size * size];
            for (int y = 0; y < size; y++)
            {
                for (int x = 0; x < size; x++)
                {
                    float dx = x + 0.5f - half;
                    float dy = y + 0.5f - half;
                    float r = Mathf.Sqrt(dx * dx + dy * dy);
                    pixels[y * size + x] = Mathf.Abs(r - radius) < 2f ? Color.white : new Color(0f, 0f, 0f, 0f);
                }
            }
            tex.SetPixels(pixels);
            tex.filterMode = FilterMode.Bilinear;
            tex.Apply(false, true);
            m_RingTexture = tex;
            return Sprite.Create(tex, new Rect(0f, 0f, size, size), new Vector2(0.5f, 0.5f), size);
        }

        void OnDestroy()
        {
            if (m_VideoRt != null) { m_VideoRt.Release(); Destroy(m_VideoRt); }
            if (m_RasterTex != null) Destroy(m_RasterTex);
            if (m_RowTimesTex != null) Destroy(m_RowTimesTex);
            if (m_RowDeltaTex != null) Destroy(m_RowDeltaTex);
            if (m_Material != null) Destroy(m_Material);
            if (m_DialTexture != null) Destroy(m_DialTexture);
            if (m_RingTexture != null) Destroy(m_RingTexture);
        }

        // ── uGUI 构建辅助(SimulationPanel 同款最小件;同构小件在 UiBuildHelpers)────

        Text CreateLabel(Transform parent, string name, string content, int fontSize, TextAnchor align, Color color)
        {
            var rt = NewRect(name, parent);
            var text = rt.gameObject.AddComponent<Text>();
            text.font = _font;
            text.text = content;
            text.fontSize = fontSize;
            text.color = color;
            text.alignment = align;
            text.horizontalOverflow = HorizontalWrapMode.Overflow;
            text.verticalOverflow = VerticalWrapMode.Overflow;
            text.raycastTarget = false;
            return text;
        }

        float SectionLabel(RectTransform panel, float y, string text)
        {
            var label = CreateLabel(panel, "Section." + text, text, 15, TextAnchor.MiddleLeft, new Color(0.55f, 0.75f, 0.9f));
            AnchorTop(label.rectTransform, 16f, y, k_PanelWidth - 32f, 20f);
            return y - 28f;
        }

        float LabeledSlider(RectTransform panel, float y, string text, Slider slider)
        {
            var label = CreateLabel(panel, text + " Label", text, 16, TextAnchor.MiddleLeft, new Color(0.92f, 0.94f, 0.96f));
            AnchorTop(label.rectTransform, 16f, y, 200f, 22f);
            PlaceSlider((RectTransform)slider.transform, y - 30f);
            return y - 72f;
        }

        static void AnchorTop(RectTransform rt, float x, float y, float w, float h)
        {
            rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(0f, 1f);
            rt.anchoredPosition = new Vector2(x, y);
            rt.sizeDelta = new Vector2(w, h);
        }

        static void PlaceSlider(RectTransform rt, float y)
        {
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.sizeDelta = new Vector2(-40f, 26f);
            rt.anchoredPosition = new Vector2(0f, y);
        }

        Slider CreateSlider(RectTransform panel, string name, float min, float max, float value, bool wholeNumbers,
            UnityAction<float> onChanged)
        {
            var rt = NewRect(name, panel);

            var background = NewImage("Background", rt, new Color(1f, 1f, 1f, 0.14f));
            background.rectTransform.anchorMin = Vector2.zero;
            background.rectTransform.anchorMax = Vector2.one;
            background.rectTransform.offsetMin = new Vector2(0f, 9f);
            background.rectTransform.offsetMax = new Vector2(0f, -9f);

            var fillArea = NewRect("Fill Area", rt);
            fillArea.anchorMin = Vector2.zero;
            fillArea.anchorMax = Vector2.one;
            fillArea.offsetMin = new Vector2(6f, 10f);
            fillArea.offsetMax = new Vector2(-6f, -10f);
            var fill = NewImage("Fill", fillArea, new Color(0.30f, 0.55f, 0.85f, 0.9f));
            fill.rectTransform.anchorMin = Vector2.zero;
            fill.rectTransform.anchorMax = new Vector2(0f, 1f);
            fill.rectTransform.sizeDelta = Vector2.zero;

            var handleArea = NewRect("Handle Slide Area", rt);
            handleArea.anchorMin = Vector2.zero;
            handleArea.anchorMax = Vector2.one;
            handleArea.offsetMin = new Vector2(6f, 0f);
            handleArea.offsetMax = new Vector2(-6f, 0f);
            var handle = NewImage("Handle", handleArea, new Color(0.95f, 0.97f, 1f));
            handle.rectTransform.anchorMin = new Vector2(0f, 0f);
            handle.rectTransform.anchorMax = new Vector2(0f, 1f);
            handle.rectTransform.sizeDelta = new Vector2(12f, 0f);

            var slider = rt.gameObject.AddComponent<Slider>();
            slider.fillRect = fill.rectTransform;
            slider.handleRect = handle.rectTransform;
            slider.targetGraphic = handle;
            slider.direction = Slider.Direction.LeftToRight;
            slider.minValue = min;
            slider.maxValue = max;
            slider.wholeNumbers = wholeNumbers;
            slider.value = Mathf.Clamp(value, min, max);
            slider.onValueChanged.AddListener(onChanged);
            return slider;
        }

        Image CreateButton(RectTransform panel, string name, string label, float x, float y, float width, UnityAction onClick)
        {
            var rt = NewRect(name, panel);
            AnchorTop(rt, x, y, width, 36f);
            var img = rt.gameObject.AddComponent<Image>();
            img.color = new Color(0.16f, 0.22f, 0.30f, 0.95f);
            img.raycastTarget = true; // EventSystem 射线命中 raycastable Graphic 才派发指针事件(M1-C 事故纪律)
            var button = rt.gameObject.AddComponent<Button>();
            button.targetGraphic = img;
            var colors = button.colors;
            colors.highlightedColor = new Color(0.26f, 0.36f, 0.50f, 0.95f);
            colors.pressedColor = new Color(0.10f, 0.14f, 0.20f, 0.95f);
            button.colors = colors;
            button.onClick.AddListener(onClick);
            var text = CreateLabel(rt, name + " Label", label, 15, TextAnchor.MiddleCenter, Color.white);
            text.rectTransform.anchorMin = Vector2.zero;
            text.rectTransform.anchorMax = Vector2.one;
            text.rectTransform.offsetMin = new Vector2(2f, 4f);
            text.rectTransform.offsetMax = new Vector2(-2f, -4f);
            return img;
        }
    }
}
