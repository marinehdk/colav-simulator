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

        /// <summary>队列积压上限：主线程长期不取用时丢最旧（DetectionResultConsumer 同款）。</summary>
        const int QueueCap = 64;

        sealed class TwinSlot
        {
            public GameObject Ship;
            public VesselCatalog.Entry Entry;
            public float LengthMeters;
            public float SogMps;
        }

        readonly Dictionary<int, TwinSlot> m_Slots = new Dictionary<int, TwinSlot>();
        ConcurrentQueue<ColavTelemetry> m_Inbox;
        Thread m_Thread;
        CancellationTokenSource m_Cancel;
        volatile bool m_Running;

        TwinClock m_Clock = new TwinClock();
        TwinAnchor? m_Anchor;
        ColavTelemetry m_Prev, m_Latest;
        bool m_CanInterpolate;
        int m_LastSeq = -1;
        CameraRig m_CameraRig; // 槽位视觉接线用（TopDown 矢量隐藏语义）；查找一次缓存

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

        /// <summary>首帧锚定原点（bridge attached.anchor 用；未锚定 null）。</summary>
        public TwinAnchor? Anchor => m_Anchor;

        /// <summary>渲染插值 sim_time（未同步 NaN；bridge state 消息 sim_time 用）。</summary>
        public double RenderSimTime => m_Clock.Sample(Time.realtimeSinceStartupAsDouble);

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
                double renderSim = m_Clock.Sample(Time.realtimeSinceStartupAsDouble);
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
            if (m_Thread != null)
            {
                if (m_Thread.IsAlive && !m_Thread.Join(2000))
                    Debug.LogWarning("[Sango.Twin] receive thread did not exit within 2s");
                m_Thread = null;
            }
            if (m_Cancel != null) { m_Cancel.Dispose(); m_Cancel = null; }
            m_Inbox = null;
            m_SocketUp = false;
            ClearSlots();
            m_Prev = m_Latest = null;
            m_Anchor = null;
            m_Clock.Reset();
            m_LastSeq = -1;
            m_CanInterpolate = false;
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
                TwinFrameDecision decision = TwinFrameGate.Classify(frame.seq, m_LastSeq);
                if (decision == TwinFrameDecision.Duplicate) { m_DuplicateCount++; continue; }
                if (decision == TwinFrameDecision.Rebuild)
                {
                    // seq 倒退 = 会话重建（spec #89）：清船、清锚点、时钟重置，重 attach 语义。
                    int regressedFrom = m_LastSeq;
                    m_RebuildCount++;
                    ClearSlots();
                    m_Prev = m_Latest = null;
                    m_Anchor = null;
                    m_Clock.Reset();
                    m_LastSeq = -1;
                    m_CanInterpolate = false;
                    Debug.LogWarning($"[Sango.Twin] seq regression {regressedFrom} -> {frame.seq}; session rebuilt");
                }
                ColavTelemetry previous = m_Latest;
                var sync = m_Clock.OnFrame(frame.sim_time, now,
                    frame.playback != null ? frame.playback.effective_multiplier : 1.0);
                m_CanInterpolate = sync == TwinFrameSync.Smooth && previous != null; // Resync/First 跨跳不插值
                m_Prev = m_CanInterpolate ? previous : null;
                m_Latest = frame;
                m_LastSeq = frame.seq;
                if (!m_Anchor.HasValue) m_Anchor = TwinAnchor.FromShip(frame.truth[0]);
                m_AcceptedCount++;
            }
        }

        void ApplyPoses(double now)
        {
            if (m_Latest == null || m_Latest.truth == null || !m_Anchor.HasValue) return;
            double renderSim = m_Clock.Sample(now);
            if (double.IsNaN(renderSim)) return;
            foreach (var ship in m_Latest.truth)
            {
                if (ship == null) continue;
                TwinSlot slot = EnsureSlot(ship);
                if (slot == null) continue;
                var entry = ship;
                if (m_CanInterpolate && m_Prev != null && m_Prev.truth != null)
                {
                    var previous = FindById(m_Prev.truth, ship.id);
                    if (previous != null)
                    {
                        float alpha = TwinPose.InterpolationAlpha(renderSim, m_Prev.sim_time, m_Latest.sim_time);
                        entry = TwinPose.LerpEntries(previous, ship, alpha);
                    }
                }
                var position = TwinPose.ScenePosition(entry, m_Anchor.Value) + Vector3.up * slot.Entry.waterlineOffsetY;
                slot.Ship.transform.SetPositionAndRotation(position,
                    Quaternion.Euler(0f, TwinPose.YawDegrees(entry.psi) + slot.Entry.bowYawDeg, 0f));
                if (slot.Ship.activeSelf != entry.active) slot.Ship.SetActive(entry.active);
                slot.SogMps = entry.sog; // 供矢量/尾迹强度消费（遗留：见类头注）
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
            shipObject.name = $"Twin vessel {ship.id} ({entry.vesselClass})";
            if (water != null)
            {
                var buoyancy = shipObject.AddComponent<VesselBuoyancy>();
                buoyancy.waterSurface = water;
                buoyancy.maxSamplesPerHull = ship.id == 0 ? 64 : 16; // VisualSimulationSession.Apply 同分档
            }
            var slot = new TwinSlot { Ship = shipObject, Entry = entry, LengthMeters = ship.length };
            m_Slots[ship.id] = slot;
            WireTwinVisuals(slot, entry);
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
            var wake = slot.Ship.AddComponent<WakeFoamRig>();
            wake.water = water;
            wake.loaMeters = entry.loaMeters;
            wake.twinSpeedMps = () => slot.SogMps;
        }

        void ClearSlots()
        {
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
