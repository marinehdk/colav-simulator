using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Threading;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// P2-S1 Twin 数据面驱动（spec #89；00-REPORT.md §6 P2-S1）：消费 Colav 后端
    /// compact-v1 遥测驱动船舶，与 SimulationWorkbench 的 Demo 模式并列成开关。
    /// - 开关（"启动参数或面板"二选一取启动参数）：默认关闸 runtimeEnabled=false（Update
    ///   仅一次布尔比较，先例 FramePublisher/DetectionResultConsumer）；播放器命令行带
    ///   SangoSeamConfig.TwinCliFlag（--sango-twin）时 AfterSceneLoad 自举开闸。
    ///   开闸路径不改 Demo 任何行为：不调 VisualSimulationSession.Apply/StartRun，不删不改既有组件。
    /// - 线程模型同 DetectionResultConsumer：后台线程 REST 建会话/启动 + ClientWebSocket 收包
    ///   （.NET 内置，无新第三方包）→ JsonUtility 解析（后台线程可用）→ ConcurrentQueue 入队 →
    ///   主线程排空消费。
    /// - 主线程管线（纯核心全在 Sango.Vessels/Twin/，EditMode 可测）：
    ///   TwinFrameGate seq 去重（同 seq 重发丢弃）/倒退重建（清船、清锚点、时钟重置）→
    ///   TwinClock 软对齐（effective_multiplier 倍率、大跳重同步）→ 首帧本船锚定
    ///   （TwinAnchor，UTM 全域大数减原点，S0 发现 2）→ TwinPose 位姿（east→+x、north→+z、
    ///   rotation.y=+psi·Rad2Deg）写船槽；帧间以渲染插值 sim_time 线性插值（LerpEntries，
    ///   越界钳位不外推）。
    /// - 船槽：TwinShipFactory 按 truth.length 就实测 LOA 最近匹配 VesselCatalog 条目，
    ///   prefab + VesselBuoyancy（水引用可选）。sog 记录在槽（SogMps，供矢量/尾迹强度）；
    ///   VectorArrows/WakeFoamRig 与 WaypointFollower(Demo) 耦合，Twin 侧接线留 P2-S3/S4
    ///   （遗留，见交付说明）。
    /// </summary>
    public class TwinSessionDriver : MonoBehaviour
    {
        [Tooltip("运行期开关；默认关（Demo 行为零变化）。Play 中勾选/取消即启停")]
        public bool runtimeEnabled = false;

        [Tooltip("后端基址（gui_server 本机常驻，00-REPORT.md §2.2）")]
        public string backendBase = SangoSeamConfig.TwinBackendBase;

        [Tooltip("会话 id；空 = 自建（CreateSession+Start）。attach 已有会话时不重复 start")]
        public string sessionId = "";

        [Tooltip("自建会话参数面（与 evidence/p2s0_capture.py 同键）")]
        public string validationRuleId = "rule14";
        public string scenarioId = "head_on";
        public string algorithmId = "vo";
        public string trackerId = "god";

        [Tooltip("数据面断线自动重连（P2-S3 留尾收口：退避 1s/2s/5s 封顶，TwinReconnectPolicy）。默认关 = S1 行为零变化；TwinBridgeService 开启")]
        public bool autoReconnect = false;

        [Tooltip("船槽 prefab 来源（自举时取场景 VisualSimulationSession.catalog）")]
        public VesselCatalog catalog;

        [Tooltip("水引用（VesselBuoyancy 用；空 = 船位 y 只按水线偏移）")]
        public UnityEngine.Rendering.HighDefinition.WaterSurface water;
        public NorwayTerrain geography;

        /// <summary>队列积压上限：主线程长期不取用时丢最旧（DetectionResultConsumer 同款）。</summary>
        const int QueueCap = 64;

        /// <summary>诊断日志周期（秒；CameraRig 5s 诊断行同款工艺，spec #91 前置批 P3-11 验证面）。</summary>
        const float DiagIntervalS = 5f;

        sealed class TwinSlot
        {
            public GameObject Ship;
            public VesselCatalog.Entry Entry;
            public float LengthMeters;
            public float BeamMeters;
            public float SogMps;
            public float WaterSpeedMps;
            public float? RollDeg;
        }

        readonly Dictionary<int, TwinSlot> m_Slots = new Dictionary<int, TwinSlot>();
        ConcurrentQueue<ColavTelemetry> m_Inbox;
        Thread m_Thread;
        CancellationTokenSource m_Cancel;
        volatile bool m_Running;

        TwinClock m_Clock = new TwinClock();
        readonly TwinLivePresentation m_LivePresentation = new TwinLivePresentation();
        TwinAnchor? m_Anchor;
        ColavTelemetry m_Prev, m_Latest;
        bool m_CanInterpolate;
        double m_LastPresentedSim = double.NaN;
        GameObject m_FoamRegionRoot;
        Transform m_PreviousFoamAnchor;
        int m_LastSeq = -1;
        public TwinEnvironment LiveEnvironment { get; private set; }
        WeatherController m_Weather;
        string m_WeatherSignature;
        CameraRig m_CameraRig; // 槽位视觉接线用（TopDown 矢量隐藏语义）；查找一次缓存

        // P3-12 地理配准观测面：接受帧船位的场景坐标包络（±x/±z 极值，锚点变换后）
        // → M6TwinGeo.ClassifyFit 出 geo_fit。观测驱动（ENC 设计域 live 侧不可知）。
        Vector2 m_SceneMin, m_SceneMax;
        bool m_HasExtent;
        string m_GeoFit = "";
        M6TwinGeo.FitReport m_FitReport;
        float m_LastLoggedWaterFrac = -1f;

        long m_RxCount;
        int m_AcceptedCount, m_DuplicateCount, m_RebuildCount, m_MalformedCount, m_UnslottedCount;

        /// <summary>后台线程收到的合法 compact 帧累计（诊断/探针对账）。</summary>
        public long RxCount => Interlocked.Read(ref m_RxCount);
        /// <summary>seq 闸门接受的快照数（去重后）。</summary>
        public int AcceptedCount => m_AcceptedCount;
        /// <summary>同 seq 重发丢弃数（S0 实证步间 ~10Hz 重发）。</summary>
        public int DuplicateCount => m_DuplicateCount;
        /// <summary>seq 倒退触发的会话重建次数。</summary>
        public int RebuildCount => m_RebuildCount;
        /// <summary>信封损坏/剥除不符丢弃数。</summary>
        public int MalformedCount => m_MalformedCount;
        /// <summary>编目匹配失败跳过的船（次）。</summary>
        public int UnslottedCount => m_UnslottedCount;
        /// <summary>连接使用的会话 id（自建后回填；未连接为 null）。</summary>
        public string ConnectedSessionId => m_ConnectedSessionId;
        volatile string m_ConnectedSessionId;

        /// <summary>live WS 是否处于已连接态（重连等待期为 false；bridge state.stream 用）。</summary>
        public bool IsLiveConnected => m_SocketUp;
        volatile bool m_SocketUp;

        /// <summary>最近接受帧 seq（bridge state 消息 frame_seq 用；未收帧 -1）。</summary>
        public int LastSeq => m_LastSeq;

        /// <summary>当前船槽数（bridge attached.ships 用）。</summary>
        public int SlotCount => m_Slots.Count;

        public float OwnShipLengthM => m_Latest?.truth != null && m_Latest.truth.Length > 0 ? m_Latest.truth[0].length : 45f;

        public GameObject ShipObject(int id) =>
            m_Slots.TryGetValue(id, out var slot) && slot.Ship != null ? slot.Ship : null;

        /// <summary>首帧锚定原点（bridge attached.anchor 用；未锚定 null）。</summary>
        public TwinAnchor? Anchor => m_Anchor;

        /// <summary>
        /// geo_fit 词汇（P3-12，twin-bridge-v1 §3/§8；bridge state.geo_fit 用）：
        /// inside = 会话观测包络落在 M6 水面且 DEM 覆盖内 / partial = 混入陆域 /
        /// outside = DEM 覆盖外开阔海面 / "" = 尚无接受帧。
        /// </summary>
        public string GeoFit => m_GeoFit;

        /// <summary>最近一次 geo_fit 判定的分数面（诊断/探针证据；未判定 Fit=null）。</summary>
        public M6TwinGeo.FitReport FitReport => m_FitReport;

        /// <summary>
        /// 本船（truth[0]）槽位 GameObject（P3-S2：桅杆机位族宿主；未挂槽 null）。
        /// 头号槽位 = truth[0]（首帧锚定同序），桅杆挂点随其位姿（继承姿态一次）。
        /// </summary>
        public GameObject OwnShipObject =>
            m_Latest != null && m_Latest.truth != null && m_Latest.truth.Length > 0
            && m_Slots.TryGetValue(m_Latest.truth[0].id, out var ownSlot) && ownSlot.Ship != null
                ? ownSlot.Ship
                : null;

        /// <summary>渲染插值 sim_time（未同步 NaN；bridge state 消息 sim_time 用）。</summary>
        public double RenderSimTime => SamplePoseTime(Time.realtimeSinceStartupAsDouble);
        public bool LiveBuffering => runtimeEnabled && m_LivePresentation.Buffering;

        double SamplePoseTime(double now) => runtimeEnabled ? m_LivePresentation.Sample(now) : m_Clock.Sample(now);

        /// <summary>
        /// replay 暂停门控（P2-S3；twin-bridge-v1 §2 "PAUSED 时钟权威在 web"）：渲染钟直接锚到
        /// web playhead——TwinClock 本身无暂停概念（锚点+墙钟×倍率恒推进），sealed 回放暂停时
        /// 由 TwinBridgeService 持续调用本方法，渲染 sim 恒等 playhead 不漂移。
        /// </summary>
        public void AnchorReplayClock(double simTime, double multiplier)
        {
            m_Clock.Reset();
            m_Clock.OnFrame(simTime, Time.realtimeSinceStartupAsDouble, multiplier);
        }

        /// <summary>单行诊断（HUD/日志同款式）。</summary>
        public string Status
        {
            get
            {
                double renderSim = SamplePoseTime(Time.realtimeSinceStartupAsDouble);
                string own = "";
                if (m_Latest != null && m_Latest.truth != null && m_Latest.truth.Length > 0 && m_Anchor.HasValue)
                {
                    var position = TwinPose.ScenePosition(m_Latest.truth[0], m_Anchor.Value);
                    own = $" own=({position.x:0.0},{position.z:0.0})m psi={TwinPose.YawDegrees(m_Latest.truth[0].psi):0}°";
                }
                return $"twin {(m_Running ? "CONNECTED" : "OFF")} session={ConnectedSessionId ?? sessionId} " +
                       $"rx={RxCount} acc={m_AcceptedCount} dup={m_DuplicateCount} rb={m_RebuildCount} " +
                       $"bad={m_MalformedCount} slots={m_Slots.Count} sim={(double.IsNaN(renderSim) ? 0.0 : renderSim):0.00}s" + own;
            }
        }

        /// <summary>开启 Twin 数据面（幂等：线程已在跑则忽略）。</summary>
        public void StartTwin()
        {
            runtimeEnabled = true;
            if (m_Thread != null && m_Thread.IsAlive) return;
            if (m_Inbox == null) m_Inbox = new ConcurrentQueue<ColavTelemetry>(); // sealed 喂帧口可能已建
            m_Cancel = new CancellationTokenSource();
            m_Running = true;
            m_Thread = new Thread(ReceiveLoop) { IsBackground = true, Name = "Sango.TwinSessionDriver" };
            m_Thread.Start();
            Debug.Log("[Sango.Twin] session driver starting (" + (string.IsNullOrEmpty(sessionId) ? "auto-create" : "attach " + sessionId) + ")");
        }

        /// <summary>停收包线程并清船槽（回默认关闸态）。</summary>
        public void StopTwin()
        {
            runtimeEnabled = false;
            m_Running = false;
            if (m_Cancel != null) { try { m_Cancel.Cancel(); } catch (ObjectDisposedException) { } }
            // F9 守卫（TwinBridgeService.StopReplayFetch 同款）：Join 超时窗口里线程可能仍阻塞在
            // token WaitHandle 上，立即 Dispose 会向后台线程抛 ObjectDisposedException——延后到
            // 确认线程退场再 Dispose（下次 Stop 收尾，最坏 GC 兜底）。
            bool receiveThreadSettled = true;
            if (m_Thread != null)
            {
                if (m_Thread.IsAlive && !m_Thread.Join(2000))
                {
                    Debug.LogWarning("[Sango.Twin] receive thread did not exit within 2s");
                    receiveThreadSettled = false;
                }
                if (receiveThreadSettled) m_Thread = null;
            }
            if (m_Cancel != null && receiveThreadSettled) { m_Cancel.Dispose(); m_Cancel = null; }
            m_Inbox = null;
            m_SocketUp = false;
            ClearSlots();
            m_Prev = m_Latest = null;
            m_Anchor = null;
            m_Clock.Reset();
            m_LivePresentation.Reset();
            m_LastSeq = -1;
            m_CanInterpolate = false;
            ResetGeoFit();
        }

        void OnDisable() => StopTwin();
        void OnDestroy() => StopTwin();

        /// <summary>Inspector 勾选同步 + 消费：对齐 FramePublisher.Update 闸/消费模式。</summary>
        void Update()
        {
            if (runtimeEnabled && (m_Thread == null || !m_Thread.IsAlive)) StartTwin();
            else if (!runtimeEnabled && m_Thread != null) StopTwin();
            if (m_Inbox == null) return;
            double now = Time.realtimeSinceStartupAsDouble;
            DrainInbox(now);
            ApplyPoses(now);
            LogDiagnostic();
        }

        float m_LastDiagLog = -999f;

        /// <summary>
        /// 低频诊断行（spec #91 前置批 P3-11 验证面）：槽位数 + 每船场景坐标/艏向/地形高程
        /// （P3-12 e= 字段：M6TwinGeo.ElevationAt 实采，负值 = 船在水面；无地形=开阔海面
        /// 时省略段）——探针从 Player.log 对拍 WS truth（数据 → 槽位位姿正确性）与"船在
        /// 水面"断言的唯一现场证据（槽位 GameObject 无调试通道；CameraRig 5s census 同款工艺）。
        /// </summary>
        void LogDiagnostic()
        {
            if (Time.unscaledTime - m_LastDiagLog < DiagIntervalS) return;
            m_LastDiagLog = Time.unscaledTime;
            ClassifyGeoFit();
            if (m_Latest?.truth == null || !m_Anchor.HasValue) return;
            var ships = string.Join(" ", System.Linq.Enumerable.Select(m_Latest.truth, ship =>
            {
                if (ship == null) return "";
                var position = TwinPose.ScenePosition(ship, m_Anchor.Value);
                float elevation = geography != null ? geography.ElevationAt(position) : M6TwinGeo.ElevationAt(position);
                string elevSegment = float.IsNaN(elevation) ? "" : $",e{elevation:0.0}m";
                return $"id{ship.id}=({position.x:0.0},{position.z:0.0}m,ψ{TwinPose.YawDegrees(ship.psi):0}°{elevSegment})";
            }));
            Debug.Log($"[Sango.Twin] diag slots={m_Slots.Count} sim={RenderSimTime:0.0}s {ships}");
        }

        /// <summary>接受帧船位 → 场景坐标包络累积（P3-12 geo_fit 观测面；锚点变换后）。</summary>
        void AccumulateExtent(ColavTelemetry frame)
        {
            if (frame?.truth == null || !m_Anchor.HasValue) return;
            foreach (var ship in frame.truth)
            {
                if (ship == null) continue;
                var local = m_Anchor.Value.ToLocal(ship.east, ship.north);
                if (!m_HasExtent)
                {
                    m_SceneMin = m_SceneMax = local;
                    m_HasExtent = true;
                }
                else
                {
                    m_SceneMin = new Vector2(Mathf.Min(m_SceneMin.x, local.x), Mathf.Min(m_SceneMin.y, local.y));
                    m_SceneMax = new Vector2(Mathf.Max(m_SceneMax.x, local.x), Mathf.Max(m_SceneMax.y, local.y));
                }
            }
        }

        /// <summary>
        /// geo_fit 判定（诊断节拍复用，≤0.2 Hz）：观测包络 → M6TwinGeo.ClassifyFit。
        /// 首次判定/词汇或分数变化落一行 geo 登记日志（探针解析面：anchor/landing/fit/分数）。
        /// </summary>
        void ClassifyGeoFit()
        {
            if (!m_HasExtent) return;
            m_FitReport = geography != null ? geography.ClassifyFit(m_SceneMin, m_SceneMax) : M6TwinGeo.ClassifyFit(m_SceneMin, m_SceneMax);
            string previous = m_GeoFit;
            m_GeoFit = m_FitReport.Fit;
            bool fractionsMoved = Mathf.Abs(m_FitReport.WaterFraction - m_LastLoggedWaterFrac) > 0.01f;
            if (m_GeoFit != previous || fractionsMoved)
            {
                m_LastLoggedWaterFrac = m_FitReport.WaterFraction;
                var landing = m_Anchor?.LandingM ?? Vector2.zero;
                Debug.Log($"[Sango.Twin] geo anchor=({m_Anchor?.EastM ?? 0:0.#},{m_Anchor?.NorthM ?? 0:0.#}) " +
                          $"landing=({landing.x:0},{landing.y:0}) fit={m_GeoFit} " +
                          $"water={m_FitReport.WaterFraction:0.000} terrain={m_FitReport.TerrainFraction:0.000} " +
                          $"extent=[{m_SceneMin.x:0},{m_SceneMin.y:0}..{m_SceneMax.x:0},{m_SceneMax.y:0}]m");
            }
        }

        void ResetGeoFit()
        {
            m_HasExtent = false;
            m_GeoFit = "";
            m_FitReport = default;
            m_LastLoggedWaterFrac = -1f;
        }

        /// <summary>
        /// sealed 回放喂帧口（spec #89 实现内容 4）：ReplayWindowAdapter 归一产物直接进
        /// 同一条 seq 闸门/时钟/锚定/位姿管线（与 live 唯一分叉 = 不过 WS 信封闸，
        /// 以 truth 非空为守卫）。回放节奏（window 拉取/倍率）由调用方掌控，本类只管呈现。
        /// </summary>
        public bool OfferReplayFrame(ColavTelemetry adapted)
        {
            if (adapted == null || adapted.truth == null || adapted.truth.Length == 0) return false;
            if (m_Inbox == null) m_Inbox = new ConcurrentQueue<ColavTelemetry>();
            m_Inbox.Enqueue(adapted);
            return true;
        }

        // ── 后台线程：REST 建会话/attach + WS 收包 ─────────────────────────────────

        void ReceiveLoop()
        {
            CancellationToken cancellation = m_Cancel.Token;
            var inbox = m_Inbox; // 线程持有本地引用（DetectionResultConsumer 同款，收尾竞态不炸）
            try
            {
                string id = sessionId;
                if (string.IsNullOrEmpty(id))
                {
                    id = TwinRest.CreateSession(backendBase, validationRuleId, scenarioId, algorithmId, trackerId);
                    TwinRest.StartSession(backendBase, id);
                }
                m_ConnectedSessionId = id;
                // P2-S3 留尾收口：autoReconnect=true 时断线按 1s/2s/5s 封顶退避重连（TwinReconnectPolicy，
                // twin-bridge-v1.md §5）；默认 false = S1 行为零变化（断线关闸等人为重开）。
                // P2-S4 B：attempt 状态机收进 TwinReconnectPolicy.ReconnectSequence（EditMode 模拟可测）。
                var reconnect = new TwinReconnectPolicy.ReconnectSequence();
                while (m_Running)
                {
                    using (var socket = new ClientWebSocket())
                    {
                        socket.ConnectAsync(new Uri(TwinWs.CompactUrl(backendBase, id)), cancellation).GetAwaiter().GetResult();
                        m_SocketUp = true;
                        int priorAttempts = reconnect.Attempt;
                        reconnect.OnConnected();
                        Debug.Log("[Sango.Twin] connected " + TwinWs.CompactUrl(backendBase, id) +
                                  (priorAttempts > 0 ? $" (reconnect #{priorAttempts})" : ""));
                        while (m_Running)
                        {
                            string json = TwinWs.ReceiveText(socket, cancellation);
                            if (json == null) break; // 服务端关闭 / 停止取消
                            var frame = ColavTelemetry.FromJson(json);
                            if (!TwinEnvelope.IsValidCompact(frame)) { m_MalformedCount++; continue; }
                            Interlocked.Increment(ref m_RxCount);
                            while (inbox.Count >= QueueCap && inbox.TryDequeue(out _)) { }
                            inbox.Enqueue(frame);
                        }
                    }
                    m_SocketUp = false;
                    var decision = reconnect.OnDisconnected(m_Running, autoReconnect);
                    if (!decision.Reconnect) break;
                    Debug.LogWarning($"[Sango.Twin] connection lost; reconnect in {decision.DelaySeconds:0.#}s (attempt {reconnect.Attempt})");
                    if (cancellation.WaitHandle.WaitOne(TimeSpan.FromSeconds(decision.DelaySeconds))) break; // 停止取消即刻收线程
                }
            }
            catch (Exception error)
            {
                if (m_Running)
                    Debug.LogError($"[Sango.Twin] receive loop exited: {error.GetType().Name} {error.Message}");
            }
            finally
            {
                m_Running = false;
                m_SocketUp = false;
                runtimeEnabled = false; // Update 闸不再重试，直至人为重新开闸（FramePublisher 同款）
            }
        }

        // ── 主线程：seq 闸门 → 时钟 → 锚定 → 位姿 ─────────────────────────────────

        void DrainInbox(double now)
        {
            while (m_Inbox.TryDequeue(out var frame))
            {
                if (frame.environment != null)
                {
                    LiveEnvironment = frame.environment;
                    string signature = JsonUtility.ToJson(frame.environment);
                    if (signature != m_WeatherSignature)
                    {
                        if (m_Weather == null) m_Weather = FindFirstObjectByType<WeatherController>();
                        TwinEnvironmentVisuals.Apply(m_Weather, frame.environment);
                        m_WeatherSignature = signature;
                    }
                }
                TwinFrameDecision decision = TwinFrameGate.Classify(frame.seq, m_LastSeq);
                if (decision == TwinFrameDecision.Duplicate)
                {
                    // Heartbeats can carry rate/pause changes at the same seq.
                    if (runtimeEnabled) m_LivePresentation.ObservePlayback(frame, now);
                    m_DuplicateCount++; continue;
                }
                if (decision == TwinFrameDecision.Rebuild)
                {
                    // seq 倒退 = 会话重建（spec #89）：清船、清锚点、时钟重置，重 attach 语义。
                    int regressedFrom = m_LastSeq;
                    m_RebuildCount++;
                    ClearSlots();
                    m_Prev = m_Latest = null;
                    m_Anchor = null;
                    m_Clock.Reset();
                    m_LivePresentation.Reset();
                    m_LastSeq = -1;
                    m_CanInterpolate = false;
                    ResetGeoFit();
                    Debug.LogWarning($"[Sango.Twin] seq regression {regressedFrom} -> {frame.seq}; session rebuilt");
                }
                ColavTelemetry previous = m_Latest;
                if (runtimeEnabled) m_LivePresentation.Offer(frame, now);
                var sync = m_Clock.OnFrame(frame.sim_time, now,
                    frame.playback != null ? frame.playback.effective_multiplier : m_LivePresentation.Rate);
                m_CanInterpolate = sync == TwinFrameSync.Smooth && previous != null;
                m_Prev = m_CanInterpolate ? previous : null;
                m_Latest = frame;
                m_LastSeq = frame.seq;
                if (!m_Anchor.HasValue) m_Anchor = geography != null ? geography.Anchor : TwinAnchor.FromShip(frame.truth[0]);
                AccumulateExtent(frame);
                m_AcceptedCount++;
            }
        }

        void ApplyPoses(double now)
        {
            if (m_Latest == null || m_Latest.truth == null || !m_Anchor.HasValue) return;
            double renderSim = SamplePoseTime(now);
            ColavTelemetry previousFrame = m_CanInterpolate ? m_Prev : null;
            ColavTelemetry renderFrame = m_Latest;
            if (runtimeEnabled && !m_LivePresentation.Bracket(now, out previousFrame, out renderFrame, out renderSim)) return;
            if (double.IsNaN(renderSim)) return;
            bool advancing = TwinWaterMotion.IsAdvancing(m_LastPresentedSim, renderSim,
                runtimeEnabled ? m_Latest.state : null);
            m_LastPresentedSim = renderSim;
            foreach (var ship in renderFrame.truth)
            {
                if (ship == null) continue;
                TwinSlot slot = EnsureSlot(ship);
                if (slot == null) continue;
                var entry = ship;
                if (previousFrame != null && previousFrame.truth != null)
                {
                    var previous = FindById(previousFrame.truth, ship.id);
                    if (previous != null)
                    {
                        float alpha = TwinPose.InterpolationAlpha(renderSim, previousFrame.sim_time, renderFrame.sim_time);
                        entry = TwinPose.LerpEntries(previous, ship, alpha);
                    }
                }
                var position = TwinPose.ScenePosition(entry, m_Anchor.Value) + Vector3.up * slot.Entry.waterlineOffsetY;
                slot.Ship.transform.SetPositionAndRotation(position,
                    Quaternion.Euler(0f, TwinPose.YawDegrees(entry.psi) + slot.Entry.bowYawDeg, 0f));
                if (slot.Ship.activeSelf != entry.active) slot.Ship.SetActive(entry.active);
                var forward = TwinPose.HeadingVector(TwinPose.YawDegrees(entry.psi));
                var starboard = new Vector3(forward.z, 0, -forward.x);
                var throughWater = forward * entry.u + starboard * entry.v - (LiveEnvironment?.CurrentVelocity ?? Vector3.zero);
                slot.SogMps = entry.sog;
                slot.WaterSpeedMps = advancing ? throughWater.magnitude : 0f;
                if (m_FoamRegionRoot != null && slot.Ship == OwnShipObject &&
                    TwinWaterMotion.RegionNeedsRecenter(m_FoamRegionRoot.transform.position, position, water.decalRegionSize))
                    m_FoamRegionRoot.transform.position = new Vector3(position.x, 0, position.z);
                slot.RollDeg = entry.has_roll ? entry.roll_rad * Mathf.Rad2Deg : (float?)null; // 供矢量/尾迹强度消费（遗留：见类头注）
            }
        }

        TwinSlot EnsureSlot(ColavTelemetry.ShipEntry ship)
        {
            if (m_Slots.TryGetValue(ship.id, out var existing) && existing.Ship != null)
            {
                // 同 id 尺寸变化（重建后新场景）→ 换槽；TwinShipFactory 按长选型（宽度信息冗余校验略）。
                if (Mathf.Approximately(existing.LengthMeters, ship.length)) return existing;
                DestroySlot(existing);
                m_Slots.Remove(ship.id);
            }
            var entry = TwinShipFactory.Select(catalog, ship.length);
            if (entry == null)
            {
                m_UnslottedCount++;
                if (m_UnslottedCount == 1 || m_UnslottedCount % 100 == 0)
                    Debug.LogWarning($"[Sango.Twin] no catalog entry for length {ship.length:0.#}m (ship {ship.id})");
                return null;
            }
            var position = TwinPose.ScenePosition(ship, m_Anchor.Value) + Vector3.up * entry.waterlineOffsetY;
            var shipObject = Instantiate(entry.prefab, position,
                Quaternion.Euler(0f, TwinPose.YawDegrees(ship.psi) + entry.bowYawDeg, 0f), transform);
            shipObject.SetActive(false);
            shipObject.name = $"Twin vessel {ship.id} ({entry.vesselClass})";
            if (water != null)
            {
                var buoyancy = shipObject.AddComponent<VesselBuoyancy>();
                buoyancy.waterSurface = water;
                buoyancy.bowYawDeg = entry.bowYawDeg;
                buoyancy.maxSamplesPerHull = ship.id == 0 ? 64 : 16; // VisualSimulationSession.Apply 同分档
            }
            var slot = new TwinSlot { Ship = shipObject, Entry = entry, LengthMeters = ship.length, BeamMeters = ship.width };
            m_Slots[ship.id] = slot;
            WireTwinVisuals(slot, entry);
            shipObject.SetActive(ship.active);
            return slot;
        }

        /// <summary>
        /// P2-S4 D 收口（类头注遗留）：槽位船接速度矢量 + 尾迹，驱动源 = Twin 会话 sog
        /// （ApplyPoses 逐帧写 slot.SogMps）。Demo 路径零变化——VectorArrows/WakeFoamRig 的
        /// twinSpeedMps 外部源只在本方法注入（Demo 船组件由场景预接线走 follower 路径原样）；
        /// 槽位船随 StopTwin/ClearSlots 销毁，组件同灭。船 id==0 本船采样档与其余一致（S1 分档原样）。
        /// </summary>
        void WireTwinVisuals(TwinSlot slot, VesselCatalog.Entry entry)
        {
            if (m_CameraRig == null) m_CameraRig = FindFirstObjectByType<CameraRig>();
            var arrows = slot.Ship.AddComponent<VectorArrows>();
            arrows.cameraRig = m_CameraRig;
            arrows.twinSpeedMps = () => slot.SogMps;
            arrows.twinActive = () => runtimeEnabled && slot.Ship != null && slot.Ship.activeInHierarchy;
            arrows.twinBowYawOffsetDeg = entry.bowYawDeg;
            var buoyancy = slot.Ship.GetComponent<VesselBuoyancy>();
            if (buoyancy != null) buoyancy.twinRollDeg = () => slot.RollDeg;
            if (m_Weather == null) m_Weather = FindFirstObjectByType<WeatherController>();
            var lights = slot.Ship.GetComponent<NavigationLights>() ?? slot.Ship.AddComponent<NavigationLights>();
            lights.weather = m_Weather;
            lights.bowYawDeg = entry.bowYawDeg;
            // Canonical +Z bow rig is independent of prefab authoring yaw/scale.
            var surfaceRoot = new GameObject("Twin surface interaction");
            surfaceRoot.transform.SetParent(slot.Ship.transform, false);
            surfaceRoot.transform.localRotation = Quaternion.Euler(0, -entry.bowYawDeg, 0);
            surfaceRoot.transform.localScale = Vector3.one / Mathf.Max(slot.Ship.transform.lossyScale.x, 1e-3f);
            surfaceRoot.transform.localPosition = new Vector3(0, -slot.Entry.waterlineOffsetY / Mathf.Max(slot.Ship.transform.lossyScale.x, 1e-3f), 0);
            var gate = surfaceRoot.AddComponent<BoatWaterDecals>();
            gate.loaMeters = entry.loaMeters;
            gate.bowAmplitudeM = WaterDecalSizing.ForLoa(entry.loaMeters).bowAmplitudeM;
            gate.twinSpeedMps = () => slot.WaterSpeedMps;
            gate.twinCurrentVelocity = () => LiveEnvironment?.CurrentVelocity ?? Vector3.zero;
            var sizing = WaterDecalSizing.ForLoa(entry.loaMeters);
            foreach (bool bow in new[] { true, false })
            {
                var go = new GameObject(bow ? "Twin bow wave" : "Twin wake foam");
                go.transform.SetParent(surfaceRoot.transform, false);
                var size = bow ? sizing.bowRegionSize : sizing.wakeRegionSize;
                go.transform.localPosition = new Vector3(0, 0, (bow ? entry.loaMeters * 0.5f : 0) - size.y * 0.4f);
                go.transform.localRotation = Quaternion.Euler(0, 180, 0);
                var decal = go.AddComponent<UnityEngine.Rendering.HighDefinition.WaterDecal>();
                decal.material = Resources.Load<Material>(bow ? "TwinBowWave" : "TwinWakeFoam");
                decal.scaleMode = UnityEngine.Rendering.HighDefinition.DecalScaleMode.ScaleInvariant;
                decal.regionSize = size;
                decal.surfaceFoamDimmer = bow ? 0.25f : 0;
                if (bow) gate.bowDecal = decal; else gate.wakeDecal = decal;
            }
            gate.ConfigureTwinWater(water, slot.BeamMeters, slot.Ship == OwnShipObject);
            if (water != null && slot.Ship == OwnShipObject)
            {
                water.deformation = water.foam = true;
                // HDRP 17.3's reprojection branch does not rebind the graphics foam target.
                // Keep the region stable during ordinary motion; reproject only near its edge.
                m_PreviousFoamAnchor = water.decalRegionAnchor;
                m_FoamRegionRoot = new GameObject("Twin foam region");
                m_FoamRegionRoot.transform.position = surfaceRoot.transform.position;
                water.decalRegionAnchor = m_FoamRegionRoot.transform;
                float wakeRegion = Mathf.Clamp(entry.loaMeters * 12f, 256f, 768f);
                water.decalRegionSize = new Vector2(wakeRegion, wakeRegion);
                water.deformationRes = UnityEngine.Rendering.HighDefinition.WaterSurface.WaterDecalRegionResolution.Resolution512;
                water.foamResolution = UnityEngine.Rendering.HighDefinition.WaterSurface.WaterDecalRegionResolution.Resolution1024;
                water.foamPersistenceMultiplier = 0.75f;
                water.foamCurrentInfluence = 1f;
                water.foamTextureTiling = 0.5f;
            }
            var wake = slot.Ship.AddComponent<WakeFoamRig>();
            wake.decals = gate;
            wake.twinSurfaceWake = true;
            wake.twinContactEntryMps = () => gate.ContactEntryMps;
            wake.water = water;
            wake.loaMeters = entry.loaMeters;
            wake.twinSpeedMps = () => slot.WaterSpeedMps;
            wake.twinWaveHsM = () => LiveEnvironment?.enabled == true ? LiveEnvironment.wave_hs_m : 0f;
            wake.twinCurrentVelocity = () => LiveEnvironment?.CurrentVelocity ?? Vector3.zero;
            // P3-S2 (spec #90): 槽位船进热目标分级注册表——sensor_mode=ir 时
            // ThermalTagApplier 按材质名温度档改写，EO 恢复；随槽位销毁自动失效。
            Vessels.Mast.ThermalTagApplier.Register(slot.Ship);
        }

        void ClearSlots()
        {
            m_LastPresentedSim = double.NaN;
            if (m_FoamRegionRoot != null)
            {
                if (water != null && water.decalRegionAnchor == m_FoamRegionRoot.transform)
                    water.decalRegionAnchor = m_PreviousFoamAnchor;
                if (Application.isPlaying) Destroy(m_FoamRegionRoot); else DestroyImmediate(m_FoamRegionRoot);
                m_FoamRegionRoot = null;
                m_PreviousFoamAnchor = null;
            }
            foreach (var pair in m_Slots)
                if (pair.Value.Ship != null) Destroy(pair.Value.Ship);
            m_Slots.Clear();
        }

        void DestroySlot(TwinSlot slot)
        {
            if (slot.Ship != null) Destroy(slot.Ship);
        }

        static ColavTelemetry.ShipEntry FindById(ColavTelemetry.ShipEntry[] ships, int id)
        {
            foreach (var ship in ships)
                if (ship != null && ship.id == id) return ship;
            return null;
        }

        // ── CLI 自举：--sango-twin = Twin 模式开关（Demo 行为零变化） ─────────────

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), SangoSeamConfig.TwinCliFlag) < 0) return;
            var session = FindFirstObjectByType<VisualSimulationSession>();
            var driver = new GameObject("Twin session driver").AddComponent<TwinSessionDriver>();
            if (session != null)
            {
                driver.catalog = session.catalog;
                driver.water = session.water;
            }
            if (driver.catalog == null)
            {
                var candidates = Resources.FindObjectsOfTypeAll<VesselCatalog>();
                if (candidates.Length > 0) driver.catalog = candidates[0];
            }
            driver.runtimeEnabled = true;
            Debug.Log("[Sango.Twin] enabled via " + SangoSeamConfig.TwinCliFlag + "; demo untouched");
        }
    }
}
