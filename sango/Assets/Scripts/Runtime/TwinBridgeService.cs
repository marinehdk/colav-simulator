using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// twin-bridge-v1 编排服务（P2-S3 spec #89；契约 sango/Docs/contracts/twin-bridge-v1.md）。
    /// web 页面（唯一 UI 编排权威）经 URS DataChannel（<see cref="TwinBridgeChannel"/>）发命令，
    /// 本类解析并驱动：<see cref="TwinSessionDriver"/>（attach/detach 数据面）、<see cref="CameraRig"/>
    /// （预设）、<see cref="WeatherController"/>（主题档）、<see cref="DetectionOverlay"/>（检测开关）；
    /// 回产 ready/attached/state(~1Hz)/error。遥测不走桥（00-REPORT §4 原则 1/2）：
    /// replay 模式 Unity 自拉 window REST 喂 <see cref="TwinSessionDriver.OfferReplayFrame"/>
    /// （S1 管线零分支复用）；live 模式 = driver.StartTwin（WS compact-v1 + S3 重连）。
    /// - replay 泵线程模型同 TwinSessionDriver：后台线程 REST 取数（TwinRest）→ ConcurrentQueue →
    ///   主线程按 web playhead 计量喂帧（meter：sim_time ≤ playhead 才喂，倍率写进
    ///   playback.effective_multiplier 由 TwinClock 消费）。回退 seek = 重建（清船重喂，契约 §4 REBUILD）。
    /// - 默认关闸 runtimeEnabled=false（FramePublisher/TwinSessionDriver 同款）；播放器命令行带
    ///   SangoSeamConfig.TwinBridgeCliFlag（--sango-twin-bridge）时 AfterSceneLoad 自举（场景需预接线）。
    /// </summary>
    public class TwinBridgeService : MonoBehaviour
    {
        [Tooltip("运行期开关；默认关（零开销）。Play 中勾选/取消即启停")]
        public bool runtimeEnabled = false;

        [Tooltip("twin-bridge 通道（场景预接线；URS Broadcast.streams 需含本组件）")]
        public TwinBridgeChannel channel;

        [Tooltip("数据面驱动（场景预接线；缺省自举创建并接 catalog/water）")]
        public TwinSessionDriver driver;

        [Tooltip("相机预设目标（缺省场景查找）")]
        public CameraRig cameraRig;

        [Tooltip("主题档目标（缺省场景查找）")]
        public WeatherController weather;

        [Tooltip("检测开关目标（缺省场景查找，无则创建）")]
        public DetectionOverlay overlay;

        [Tooltip("P3-S2 桅杆机位族（缺省场景查找，无则在桥对象上创建）")]
        public Vessels.Mast.MastSensorRig mastRig;

        [Tooltip("replay 取数单窗跨度（秒；≤后端 MAX_WINDOW_SPAN_S=120）")]
        public double replayFetchSpanS = 60.0;

        [Tooltip("replay 前瞻保持量（秒）：取数覆盖到 playhead + horizon")]
        public double replayHorizonS = 30.0;

        /// <summary>计量容差（秒）：sim_time ≤ playhead + eps 即喂（10Hz clock 下 ≤1 tick 超前）。</summary>
        const double MeterEpsS = 0.02;

        /// <summary>回退 seek 判定容差（秒）：playhead 落后最后已喂帧超过即重建。</summary>
        const double RebuildEpsS = 0.25;

        /// <summary>state 心跳周期（秒，契约 ~1Hz）。</summary>
        const double StateIntervalS = 1.0;

        /// <summary>后端 window 跨度上限（gui_server/replay.py MAX_WINDOW_SPAN_S；只读常量镜像）。</summary>
        const double MaxServerWindowSpanS = 120.0;

        /// <summary>replay 取数失败退避重试上限档（超出按 TwinReconnectPolicy 封顶）。</summary>
        const int MaxFetchBackoffAttempt = 3;

        // ── attach 会话态（主线程独占写） ────────────────────────────────────────
        string m_RunId;
        string m_Mode;
        string m_BackendBase;
        double m_SpanStart, m_SpanEnd; // attach.replay + descriptor 播放窗钳位
        bool m_Helloed;
        bool m_AttachedSent;
        string m_CurrentPreset = "bridge";
        string m_DetectionSource = "truth";
        bool m_DetectionEnabled;
        // P3-S2 sensor_mode（契约 §2/§8；默认 eo，state 回显）
        string m_SensorMode = TwinBridge.DefaultSensorMode;
        FramePublisher m_FeedPublisher; // 桅杆馈送改接（rig attach 后一次性）

        // clock 消息面（DataChannel 回调主线程写、泵/状态读；fetch 线程只读 playhead——
        // C# 禁 volatile double，跨线程取值允许一个 tick 的陈旧，泵按 100ms 轮询无碍）
        double m_Playhead;
        double m_Rate = 1.0;
        volatile string m_PlayState = "PAUSED";

        // replay 泵（fetch 线程 → 主线程）
        Thread m_FetchThread;
        CancellationTokenSource m_Cancel;
        ConcurrentQueue<ReplayFrame> m_WindowQueue;
        readonly List<ReplayFrame> m_Pending = new List<ReplayFrame>(); // 主线程独占；window 内 sim_time 升序
        ReplayStaticContext m_Context;
        readonly object m_FetchLock = new object();
        double m_FetchedTo; // 已取数推进到的 sim_time（fetch 线程写/主线程 seek 时重置）
        double m_LastOfferedSim = double.NegativeInfinity;
        volatile bool m_RebuildRequested;
        volatile bool m_FetchFailed;      // 最近一次取数失败（state.stream=down 依据）
        bool m_FetchErrorReported;        // 失败连击期间 error 只报一次
        int m_FetchFailStreak;

        // state 心跳
        double m_LastStateSentUnixS;
        float m_FpsSmoothed = -1f;
        bool m_WasLiveConnected;
        bool m_BridgeUp;

        /// <summary>clock.playhead_s 非有限值拒绝计数（F10 诊断；DataChannel 回调主线程独占写）。</summary>
        int m_MalformedClockCount;

        /// <summary>当前挂接的 run（探针/诊断；未挂 null）。</summary>
        public string AttachedRunId => m_RunId;

        /// <summary>当前相机预设词汇（bridge state.camera 同源）。</summary>
        public string CurrentPreset => m_CurrentPreset;

        /// <summary>HandleClock 拒绝的非有限 playhead 计数（探针/诊断用）。</summary>
        public int MalformedClockCount => m_MalformedClockCount;

        // ── 启停 ────────────────────────────────────────────────────────────────

        /// <summary>开桥（幂等）：接线 + 订阅通道。</summary>
        public void StartBridge()
        {
            runtimeEnabled = true;
            if (m_BridgeUp) return;
            EnsureWiring();
            if (channel == null)
            {
                Debug.LogError("[Sango.TwinBridge] no TwinBridgeChannel wired — build the SangoTwin scene (TwinBridgeSceneBuilder)");
                runtimeEnabled = false;
                return;
            }
            channel.onJson += HandleJson;
            channel.onOpened += HandleChannelOpened;
            m_BridgeUp = true;
            Debug.Log("[Sango.TwinBridge] service started");
        }

        /// <summary>停桥：退 detach 语义（数据面停、船清空）+ 退订。</summary>
        public void StopBridge()
        {
            runtimeEnabled = false;
            if (!m_BridgeUp) return;
            m_BridgeUp = false;
            if (channel != null)
            {
                channel.onJson -= HandleJson;
                channel.onOpened -= HandleChannelOpened;
            }
            DetachDataPlane();
            // P3-S2: 停桥回默认 eo 渲染态（IR pass 关 + 温度 tag 恢复，Demo 零残留）。
            m_SensorMode = TwinBridge.DefaultSensorMode;
            ApplySensorMode();
            Debug.Log("[Sango.TwinBridge] service stopped");
        }

        /// <summary>补齐可选引用（场景预接线缺失时按名查找；沿 TwinSessionDriver 自举工艺）。</summary>
        public void EnsureWiring()
        {
            if (channel == null) channel = GetComponent<TwinBridgeChannel>();
            if (cameraRig == null) cameraRig = FindFirstObjectByType<CameraRig>();
            if (weather == null) weather = FindFirstObjectByType<WeatherController>();
            if (driver == null)
            {
                driver = FindFirstObjectByType<TwinSessionDriver>();
                if (driver == null)
                {
                    driver = new GameObject("Twin session driver").AddComponent<TwinSessionDriver>();
                    var session = FindFirstObjectByType<VisualSimulationSession>();
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
                }
            }
            if (overlay == null)
            {
                overlay = FindFirstObjectByType<DetectionOverlay>();
                if (overlay == null) overlay = new GameObject("Detection overlay (bridge)").AddComponent<DetectionOverlay>();
            }
            if (mastRig == null)
            {
                mastRig = FindFirstObjectByType<Vessels.Mast.MastSensorRig>();
                if (mastRig == null) mastRig = new GameObject("Mast sensor rig").AddComponent<Vessels.Mast.MastSensorRig>();
            }
            EnsureIrPassVolume();
            driver.autoReconnect = true; // 契约 §5：数据面断线自动重连（bridge 托管态）
        }

        /// <summary>
        /// IR 白热 Custom Pass 体积自举（P3-S2）：SangoTwin 场景由 BuildTwinScene 预烘焙
        /// （Editor 面）；场景缺体积时（旧构建/手工场景）运行期补建——同一静态闸
        /// IrViewPass（默认 Requested=false = 零渲染成本），Demo 路径零影响。
        /// </summary>
        void EnsureIrPassVolume()
        {
            var volumes = FindObjectsByType<UnityEngine.Rendering.HighDefinition.CustomPassVolume>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            foreach (var volume in volumes)
                foreach (var pass in volume.customPasses)
                    if (pass is Vessels.Mast.IrViewPass) return; // 已有（场景预烘焙或先前自举）
            var volumeGo = new GameObject("Twin IR WhiteHot Pass (bootstrap)");
            var irVolume = volumeGo.AddComponent<UnityEngine.Rendering.HighDefinition.CustomPassVolume>();
            irVolume.isGlobal = true;
            irVolume.injectionPoint = UnityEngine.Rendering.HighDefinition.CustomPassInjectionPoint.BeforePostProcess;
            irVolume.priority = 10;
            irVolume.AddPassOfType(typeof(Vessels.Mast.IrViewPass));
            Debug.Log("[Sango.TwinBridge] IR white-hot pass volume bootstrapped at runtime");
        }

        void Update()
        {
            if (runtimeEnabled && !m_BridgeUp) StartBridge();
            else if (!runtimeEnabled && m_BridgeUp) StopBridge();
            if (!m_BridgeUp) return;

            if (m_FpsSmoothed < 0f) m_FpsSmoothed = 60f;
            else if (Time.unscaledDeltaTime > 0f) m_FpsSmoothed = Mathf.Lerp(m_FpsSmoothed, 1f / Time.unscaledDeltaTime, 0.1f);

            DrainFetchErrors();
            PumpReplay();
            GatePausedClock();
            PollLiveAttached();
            AttachMastRigWhenOwnShipReady();
            SendStateHeartbeat();
        }

        /// <summary>
        /// P3-S2 桅杆机位族挂载 + 馈送改接（own-ship 槽位出现后一次完成）：rig 随
        /// 本船位姿（继承姿态），FramePublisher 源相机改接前向 EO 机位
        /// （mast_ptz_eo，任务书"默认源=EO 前向机位"；观测契约 mount_id 引用键），
        /// 捕获分辨率随标定表栅格 640×480。
        /// </summary>
        void AttachMastRigWhenOwnShipReady()
        {
            if (mastRig == null || driver == null) return;
            if (!mastRig.Attached)
            {
                var ownShip = driver.OwnShipObject;
                if (ownShip == null) return;
                if (!mastRig.Attach(ownShip.transform))
                {
                    Debug.LogWarning("[Sango.TwinBridge] mast rig attach failed (own ship present but feed mount missing)");
                    return;
                }
                Debug.Log($"[Sango.TwinBridge] mast rig attached to {ownShip.name} mounts={mastRig.BuiltMountCount} feed={mastRig.feedMountId}");
            }
            if (m_FeedPublisher == null) m_FeedPublisher = FindFirstObjectByType<FramePublisher>();
            if (m_FeedPublisher != null && m_FeedPublisher.sourceCamera != mastRig.FeedCamera)
            {
                m_FeedPublisher.sourceCamera = mastRig.FeedCamera;
                m_FeedPublisher.mountId = mastRig.feedMountId;
                m_FeedPublisher.overrideCaptureSize = new Vector2Int(Vessels.Mast.MastCameraTable.FeedWidthPx, Vessels.Mast.MastCameraTable.FeedHeightPx);
                Debug.Log($"[Sango.TwinBridge] frame feed rewired -> {mastRig.feedMountId} ({Vessels.Mast.MastCameraTable.FeedWidthPx}x{Vessels.Mast.MastCameraTable.FeedHeightPx})");
            }
        }

        /// <summary>
        /// replay 非 PLAYING 态（PAUSED/ENDED）：渲染钟恒锚到 web playhead——TwinClock 无暂停概念，
        /// 不锚则渲染 sim 按墙钟漂移（web 时钟权威，契约 §2）。PLAYING 交还帧驱动。
        /// </summary>
        void GatePausedClock()
        {
            if (m_Mode != "replay" || !m_AttachedSent || m_PlayState == "PLAYING") return;
            if (driver == null) return;
            driver.AnchorReplayClock(ClampSpan(m_Playhead), m_Rate);
        }

        void OnDestroy() => StopBridge();

        // ── 消息面（web → Unity；DataChannel 回调在主线程） ─────────────────────

        void HandleChannelOpened() => Debug.Log("[Sango.TwinBridge] bridge channel open; awaiting hello");

        void HandleJson(string json)
        {
            TwinBridgeCommand cmd;
            try
            {
                cmd = TwinBridgeCommand.FromJson(json);
            }
            catch (Exception)
            {
                SendError(TwinBridge.ErrorBadMessage, "unparseable JSON");
                return;
            }
            if (cmd == null || string.IsNullOrEmpty(cmd.type))
            {
                SendError(TwinBridge.ErrorBadMessage, "missing type");
                return;
            }
            // 契约 §1：hello 之前的其它命令静默丢弃（防半开连接脏命令）
            if (!m_Helloed && cmd.type != "hello") return;

            switch (cmd.type)
            {
                case "hello": HandleHello(cmd); break;
                case "attach": HandleAttach(cmd); break;
                case "detach": DetachDataPlane(); break;
                case "clock": HandleClock(cmd); break;
                case "camera": HandleCamera(cmd); break;
                case "camera_free": HandleCameraFree(cmd); break;
                case "theme": HandleTheme(cmd); break;
                case "detection": HandleDetection(cmd); break;
                case "sensor_mode": HandleSensorMode(cmd); break; // P3-S2（契约 §2/§8 演进，spec #90）
                default:
                    SendError(TwinBridge.ErrorBadMessage, $"unknown type '{cmd.type}'");
                    break;
            }
        }

        void HandleHello(TwinBridgeCommand cmd)
        {
            if (cmd.protocol != TwinBridge.Protocol)
            {
                SendError(TwinBridge.ErrorUnsupportedProtocol, $"protocol '{cmd.protocol}' != '{TwinBridge.Protocol}'");
                return;
            }
            m_Helloed = true;
            Send(new TwinBridgeReady
            {
                build = Application.version,
                scene = gameObject.scene.IsValid() ? gameObject.scene.name : Application.productName,
            });
            Debug.Log($"[Sango.TwinBridge] hello (page={cmd.page}) -> ready");
        }

        void HandleAttach(TwinBridgeCommand cmd)
        {
            if (string.IsNullOrEmpty(cmd.run_id) || string.IsNullOrEmpty(cmd.mode))
            {
                SendError(TwinBridge.ErrorBadMessage, "attach requires run_id and mode");
                return;
            }
            if (!TwinBridge.IsValidMode(cmd.mode))
            {
                SendError(TwinBridge.ErrorUnsupportedMode, $"mode '{cmd.mode}' not in [{string.Join(",", TwinBridge.ModesSupported)}]");
                return;
            }
            if (cmd.mode == "replay")
            {
                if (cmd.replay == null || cmd.replay.t_end <= cmd.replay.t_start)
                {
                    SendError(TwinBridge.ErrorBadMessage, "replay attach requires replay:{t_start<t_end}");
                    return;
                }
                if (string.IsNullOrEmpty(cmd.backend_base))
                {
                    SendError(TwinBridge.ErrorBadMessage, "replay attach requires backend_base");
                    return;
                }
            }
            // 幂等重挂：同参数静默接受；新 attach 一律替换旧（契约 §2）
            DetachDataPlane();
            m_RunId = cmd.run_id;
            m_Mode = cmd.mode;
            m_BackendBase = string.IsNullOrEmpty(cmd.backend_base) ? SangoSeamConfig.TwinBackendBase : cmd.backend_base;
            m_SpanStart = cmd.replay != null ? cmd.replay.t_start : 0.0;
            m_SpanEnd = cmd.replay != null ? cmd.replay.t_end : 0.0;
            m_Helloed = true; // attach 隐含 hello 已完成（HandleJson 门控保证次序）
            m_Playhead = m_SpanStart;
            m_Rate = 1.0;
            m_PlayState = "PAUSED";
            m_AttachedSent = false;
            m_LastOfferedSim = double.NegativeInfinity;
            m_CurrentPreset = cameraRig != null ? PresetOf(cameraRig.CurrentView) : "bridge";
            Debug.Log($"[Sango.TwinBridge] attach run={m_RunId} mode={m_Mode} backend={m_BackendBase}");

            if (m_Mode == "live")
            {
                driver.backendBase = m_BackendBase;
                driver.sessionId = m_RunId; // live：run 即活跃会话 id；后端 404 时 ReceiveLoop 报错退避
                driver.StartTwin();
            }
            else
            {
                StartReplayFetch();
            }
        }

        /// <summary>detach 语义（契约 §2/§4）：数据面停、船清空、attached 失效（桥保持；
        /// hello 属桥通道生命周期不随 detach 清除——通道 open 期间 close viewer → 换 run
        /// attach 同通道必须幂等可用，web 换 run 不重发 hello）。</summary>
        void DetachDataPlane()
        {
            StopReplayFetch();
            if (driver != null) driver.StopTwin();
            m_RunId = null;
            m_Mode = null;
            m_AttachedSent = false;
            m_PlayState = "PAUSED";
            m_FetchFailed = false;
            m_FetchErrorReported = false;
            m_FetchFailStreak = 0;
            m_LastOfferedSim = double.NegativeInfinity;
        }

        void HandleClock(TwinBridgeCommand cmd)
        {
            if (m_Mode != "replay") return; // 契约 §2：live 模式 web 不发 clock；发也不消费
            // F10：非有限 playhead（NaN/Inf，非 web 端 JSON 合法输出，防御性拒绝）不进钳位/重建
            // 判定——否则 NaN 污染 m_Playhead 让计量/对拍全失真。拒绝并计 malformed（诊断计数）。
            if (double.IsNaN(cmd.playhead_s) || double.IsInfinity(cmd.playhead_s))
            {
                m_MalformedClockCount++;
                Debug.LogWarning($"[Sango.TwinBridge] clock rejected: playhead_s {cmd.playhead_s} not finite (#{m_MalformedClockCount})");
                return;
            }
            double playhead = ClampSpan(cmd.playhead_s);
            double rate = Mathf.Clamp((float)cmd.rate, 0.1f, 20f);
            string state = cmd.state ?? "PAUSED";
            // 回退 seek → 重建（契约 §4 REBUILD）：清船重喂，新 seq 序列仍单调（闸门接受）
            if (m_LastOfferedSim > double.NegativeInfinity && playhead < m_LastOfferedSim - RebuildEpsS)
            {
                m_RebuildRequested = true;
                Debug.LogWarning($"[Sango.TwinBridge] backward seek {m_LastOfferedSim:0.00} -> {playhead:0.00}; rebuild");
            }
            m_Playhead = playhead;
            m_Rate = rate;
            m_PlayState = state;
        }

        void HandleCamera(TwinBridgeCommand cmd)
        {
            if (!TwinBridge.IsValidPreset(cmd.preset))
            {
                SendError(TwinBridge.ErrorBadMessage, $"unknown preset '{cmd.preset}'");
                return;
            }
            m_CurrentPreset = cmd.preset;
            if (cameraRig != null && TryMapPreset(cmd.preset, out CameraView view))
            {
                cameraRig.SetView(view);
                Debug.Log($"[Sango.TwinBridge] camera -> {view} (preset {cmd.preset})");
            }
        }

        /// <summary>
        /// camera_free（P2-S4 契约 §8 演进记录；Cesium↔Twin 分屏主从联动 spike，单向
        /// Cesium 主→Twin 从，web 侧默认关）：web 把 CesiumJS 相机位姿折算成全域 UTM 米发来，
        /// Unity 侧减 attached.anchor 得场景坐标（TwinPose 同一原点锚定语义），CameraRig.SetFreePose
        /// 直贴位姿——离散事件不插值不锁步（阶段硬边界 §8.3）。pitch 负=俯（CameraPose 语义沿用）；
        /// 之后任何 camera 预设消息收回控制权（SetView 清自由位姿）。
        /// </summary>
        void HandleCameraFree(TwinBridgeCommand cmd)
        {
            if (cmd.pos == null || cmd.fov_deg <= 0.0 || cmd.fov_deg > 170.0)
            {
                SendError(TwinBridge.ErrorBadMessage, "camera_free requires pos and fov_deg in (0,170]");
                return;
            }
            if (cameraRig == null) return;
            if (driver == null || !driver.Anchor.HasValue)
            {
                SendError(TwinBridge.ErrorBadMessage, "camera_free requires an attached data plane (anchor)");
                return;
            }
            var anchor = driver.Anchor.Value;
            var position = new Vector3(
                (float)(cmd.pos.east - anchor.EastM),
                Mathf.Clamp((float)cmd.pos.height_m, -50f, 5000f),
                (float)(cmd.pos.north - anchor.NorthM));
            m_CurrentPreset = TwinBridge.CameraFreePreset; // state.camera 回显 free（契约 §3 注）
            cameraRig.SetFreePose(position, (float)cmd.yaw_deg, (float)cmd.pitch_deg,
                Mathf.Clamp((float)cmd.fov_deg, 10f, 120f));
            Debug.Log($"[Sango.TwinBridge] camera_free east={cmd.pos.east:0.#} north={cmd.pos.north:0.#} " +
                      $"h={cmd.pos.height_m:0.#} yaw={cmd.yaw_deg:0.#} pitch={cmd.pitch_deg:0.#} fov={cmd.fov_deg:0.#}");
        }

        void HandleTheme(TwinBridgeCommand cmd)
        {
            if (!TwinBridge.IsValidTheme(cmd.value))
            {
                SendError(TwinBridge.ErrorBadMessage, $"unknown theme '{cmd.value}'");
                return;
            }
            if (weather != null)
            {
                weather.timeOfDayHours = ThemeHours(cmd.value);
                weather.Apply();
                Debug.Log($"[Sango.TwinBridge] theme {cmd.value} -> {weather.timeOfDayHours:0.#}h");
            }
        }

        void HandleDetection(TwinBridgeCommand cmd)
        {
            bool yolo = cmd.source == "yolo";
            if (!yolo && cmd.source != "truth")
            {
                SendError(TwinBridge.ErrorBadMessage, $"unknown detection source '{cmd.source}'");
                return;
            }
            m_DetectionEnabled = cmd.enabled;
            m_DetectionSource = cmd.source;
            if (overlay != null)
            {
                overlay.visible = cmd.enabled;
                overlay.requireLive = cmd.enabled && yolo; // truth = 真值路径；yolo = live 优先（契约 §2）
                Debug.Log($"[Sango.TwinBridge] detection enabled={cmd.enabled} source={cmd.source}");
            }
        }

        /// <summary>
        /// sensor_mode（P3-S2，契约 §2/§8 演进；spec #90）：主视口传感器模式——
        /// eo=默认正常渲染 / ir=流相机 IR pass（黑白热像+温度 tag）/ lidar=本段
        /// 占位（接受+state 回显，点云渲染留 S3，UI pending 态明示）。
        /// 与 camera 预设正交叠加（不改 CameraRig 状态，契约 §2）。
        /// </summary>
        void HandleSensorMode(TwinBridgeCommand cmd)
        {
            if (!TwinBridge.IsValidSensorMode(cmd.value))
            {
                SendError(TwinBridge.ErrorBadMessage, $"unknown sensor_mode '{cmd.value}'");
                return;
            }
            m_SensorMode = cmd.value;
            ApplySensorMode();
            Debug.Log($"[Sango.TwinBridge] sensor_mode -> {cmd.value}");
        }

        /// <summary>sensor_mode → 渲染效果（状态机效果面 = TwinBridge.SensorModeEffect 纯函数）。</summary>
        void ApplySensorMode()
        {
            TwinBridge.SensorModeEffect(m_SensorMode, out bool irActive, out bool lidarPending);
            var streamCamera = Camera.main;
            Vessels.Mast.IrViewPass.SetActive(irActive, streamCamera);
            if (irActive) Vessels.Mast.ThermalTagApplier.Apply();
            else Vessels.Mast.ThermalTagApplier.Revert();
            if (lidarPending)
                Debug.Log("[Sango.TwinBridge] sensor_mode=lidar accepted (echoed in state); point-cloud view lands in S3");
        }

        // ── replay 泵：后台取数 + 主线程计量喂帧 ────────────────────────────────

        void StartReplayFetch()
        {
            m_WindowQueue = new ConcurrentQueue<ReplayFrame>();
            m_Pending.Clear();
            lock (m_FetchLock) m_FetchedTo = m_SpanStart;
            m_Cancel = new CancellationTokenSource();
            var thread = new Thread(ReplayFetchLoop) { IsBackground = true, Name = "Sango.TwinBridge.replay" };
            m_FetchThread = thread;
            thread.Start();
        }

        void StopReplayFetch()
        {
            if (m_Cancel != null) { try { m_Cancel.Cancel(); } catch (ObjectDisposedException) { } }
            // F9 守卫：线程仍阻塞在 token WaitHandle 上时（Join 超时窗口）Dispose 会向后台线程
            // 抛 ObjectDisposedException（同 run 幂等重挂时还会借 m_RunId==runId 串成假
            // REPLAY_FETCH_FAILED）——Dispose 延后到确认线程退场（下次 Stop 收尾，最坏 GC 兜底）。
            bool fetchThreadSettled = true;
            if (m_FetchThread != null)
            {
                if (m_FetchThread.IsAlive && !m_FetchThread.Join(2000))
                {
                    Debug.LogWarning("[Sango.TwinBridge] fetch thread did not exit within 2s");
                    fetchThreadSettled = false;
                }
                if (fetchThreadSettled) m_FetchThread = null;
            }
            if (m_Cancel != null && fetchThreadSettled) { m_Cancel.Dispose(); m_Cancel = null; }
            m_WindowQueue = null;
            m_Pending.Clear();
            m_Context = null;
        }

        /// <summary>后台线程：descriptor 播放性检查 → context（ENC 原点锚）→ window 滚动取数。</summary>
        void ReplayFetchLoop()
        {
            CancellationToken cancellation = m_Cancel.Token;
            string runId = m_RunId; // 代际快照：新 attach/detach 后旧线程退出
            try
            {
                // descriptor：播放性（RUN_NOT_PLAYABLE）+ INCOMPLETE 时播放端钳位 trusted_t_end
                var descriptor = JsonUtility.FromJson<ReplayDescriptorSubset>(
                    TwinRest.Get(m_BackendBase, $"/api/runs/{runId}/replay"));
                string replayState = descriptor?.replay?.state ?? "UNAVAILABLE";
                bool seekable = descriptor?.capabilities?.seekable != false;
                bool playable = (replayState == "READY" && seekable) || (replayState == "INCOMPLETE" && seekable);
                if (!playable)
                {
                    EnqueueFetchError(TwinBridge.ErrorRunNotPlayable, $"replay state {replayState} is not playable");
                    return;
                }
                double spanEnd = replayState == "INCOMPLETE" && descriptor.replay.trusted_t_end > 0
                    ? Math.Min(m_SpanEnd, descriptor.replay.trusted_t_end)
                    : m_SpanEnd;

                // context：ENC 原点 = attached.anchor（S1 原点锚定语义）；ships 静态尺寸
                var context = ReplayWindowAdapter.ContextFromJson(
                    TwinRest.Get(m_BackendBase, $"/api/runs/{runId}/replay/context"));
                if (context == null || context.enc == null)
                {
                    EnqueueFetchError(TwinBridge.ErrorReplayFetchFailed, "replay context missing enc bounds");
                    return;
                }
                m_Context = context;
                Debug.Log($"[Sango.TwinBridge] context ok run={runId} origin=({context.enc.origin_east_m:0.#},{context.enc.origin_north_m:0.#}) ships={context.ships?.Length ?? 0}");

                double span = Math.Min(replayFetchSpanS, MaxServerWindowSpanS);
                int idleWaitMs = 100;
                while (!cancellation.IsCancellationRequested && m_RunId == runId)
                {
                    double horizon = ClampSpan(m_Playhead + replayHorizonS);
                    double fetchedTo;
                    lock (m_FetchLock) fetchedTo = m_FetchedTo;
                    if (fetchedTo >= horizon - 1e-6)
                    {
                        if (cancellation.WaitHandle.WaitOne(idleWaitMs)) break;
                        continue;
                    }
                    double from = fetchedTo;
                    double to = Math.Min(spanEnd, fetchedTo + span);
                    if (to <= from)
                    {
                        lock (m_FetchLock) m_FetchedTo = spanEnd; // 播放窗已到头
                        continue;
                    }
                    try
                    {
                        string json = TwinRest.Get(m_BackendBase,
                            $"/api/runs/{runId}/replay/window?from={from.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture)}" +
                            $"&to={to.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture)}");
                        var document = ReplayWindowAdapter.WindowFromJson(json);
                        int queued = 0;
                        if (document?.frames != null)
                            foreach (var frame in document.frames)
                                if (frame != null && m_WindowQueue != null) { m_WindowQueue.Enqueue(frame); queued++; }
                        lock (m_FetchLock) m_FetchedTo = Math.Max(m_FetchedTo, to);
                        OnFetchSuccess();
                        Debug.Log($"[Sango.TwinBridge] window [{from:0.#},{to:0.#}) frames={queued} fetchedTo={m_FetchedTo:0.#}");
                    }
                    catch (Exception error)
                    {
                        if (!OnFetchFailure(ClassifyBackendError(error, runId), error.Message, cancellation)) return;
                    }
                }
            }
            catch (Exception error)
            {
                if (m_RunId == runId)
                    EnqueueFetchError(ClassifyBackendError(error, runId), error.Message);
            }
        }

        /// <summary>主线程：取数成功 → 复位失败连击；恢复后 attached 重发由 PumpReplay 常规路径承担。</summary>
        void OnFetchSuccess()
        {
            m_FetchFailed = false;
            m_FetchErrorReported = false;
            m_FetchFailStreak = 0;
        }

        /// <summary>主线程可见的失败标记 + 节流报错 + 退避等待；false = 取消退出。</summary>
        bool OnFetchFailure(string code, string message, CancellationToken cancellation)
        {
            m_FetchFailed = true;
            m_FetchFailStreak++;
            if (!m_FetchErrorReported)
            {
                EnqueueFetchError(code, message);
                m_FetchErrorReported = true;
            }
            double backoffS = TwinReconnectPolicy.DelaySeconds(Math.Min(m_FetchFailStreak - 1, MaxFetchBackoffAttempt));
            Debug.LogWarning($"[Sango.TwinBridge] fetch failed ({code}): {message}; retry in {backoffS:0.#}s");
            return !cancellation.WaitHandle.WaitOne(TimeSpan.FromSeconds(backoffS));
        }

        void EnqueueFetchError(string code, string message)
        {
            m_ErrorQueue ??= new ConcurrentQueue<TwinBridgeError>();
            m_ErrorQueue.Enqueue(new TwinBridgeError { code = code, message = TruncateMessage(message) });
        }

        ConcurrentQueue<TwinBridgeError> m_ErrorQueue;

        /// <summary>主线程：fetch 线程产生的错误码出队上桥（契约 §4；节流在入队侧）。</summary>
        void DrainFetchErrors()
        {
            if (m_ErrorQueue == null) return;
            while (m_ErrorQueue.TryDequeue(out var error))
                SendJson(error.ToJson());
        }

        /// <summary>主线程：按 web playhead 计量喂帧（sim_time ≤ playhead + eps）。</summary>
        void PumpReplay()
        {
            if (m_Mode != "replay" || m_WindowQueue == null) return;

            if (m_RebuildRequested)
            {
                m_RebuildRequested = false;
                m_Pending.Clear();
                lock (m_FetchLock) m_FetchedTo = Math.Max(m_SpanStart, m_Playhead);
                m_LastOfferedSim = double.NegativeInfinity;
                m_AttachedSent = false; // 契约 §4：REBUILD（回退 seek/会话重建）后 attached 重发
                driver.StopTwin(); // 清船 + 时钟复位；下一帧 First 锚定（重建语义）
            }

            while (m_WindowQueue.TryDequeue(out var frame))
                if (frame != null) m_Pending.Add(frame);

            if (!m_AttachedSent && m_Context != null)
                SendAttached(anchorEast: m_Context.enc.origin_east_m, anchorNorth: m_Context.enc.origin_north_m);

            double target = ClampSpan(m_Playhead);
            // 前向跳越取数覆盖：丢弃过期缓冲，取数从新 playhead 重铺（船由 TwinClock Resync 吸附）
            double fetchedTo;
            lock (m_FetchLock) fetchedTo = m_FetchedTo;
            if (target > fetchedTo + replayHorizonS)
            {
                m_Pending.Clear();
                lock (m_FetchLock) m_FetchedTo = target;
            }

            int offered = 0;
            while (m_Pending.Count > 0)
            {
                var frame = m_Pending[0];
                if (frame.sim_time > target + MeterEpsS) break; // 未到播放位置（帧序有序，其后必未到）
                m_Pending.RemoveAt(0);
                if (frame.sim_time < target - RebuildEpsS) continue; // 过期残余（重建竞态窗口）直接弃
                var telemetry = ReplayWindowAdapter.ToTelemetry(frame, m_Context);
                if (telemetry == null) continue;
                telemetry.playback.effective_multiplier = m_Rate; // sealed 倍率由 web clock 控制（契约 §2）
                if (driver.OfferReplayFrame(telemetry))
                {
                    m_LastOfferedSim = frame.sim_time;
                    offered++;
                }
            }
            if (offered > 0 && m_FetchErrorReported && !m_FetchFailed)
                m_FetchErrorReported = false; // 自愈后允许下一轮失败再报
        }

        double ClampSpan(double simTime) => Math.Max(m_SpanStart, Math.Min(m_SpanEnd, simTime));

        // ── live attached 重发（重连恢复，契约 §5） ─────────────────────────────

        void PollLiveAttached()
        {
            if (m_Mode != "live" || driver == null) return;
            bool connected = driver.IsLiveConnected;
            if (connected && !m_WasLiveConnected)
                Debug.Log("[Sango.TwinBridge] live data plane connected");
            m_WasLiveConnected = connected;
            if (m_AttachedSent && !connected)
                m_AttachedSent = false; // 断线：恢复后重发 attached（契约 §5）
            if (!m_AttachedSent && connected && driver.Anchor.HasValue)
                SendAttached(driver.Anchor.Value.EastM, driver.Anchor.Value.NorthM);
        }

        // ── Unity → web 出站 ────────────────────────────────────────────────────

        void SendAttached(double anchorEast, double anchorNorth)
        {
            m_AttachedSent = true;
            // F8：replay 在 context 取到后即发 attached（槽位未建，SlotCount 恒 0）——契约 §6 样例
            // 语义 = 该 run 船数，上报 context.ships 静态面；live 无 context，维持已挂槽位数（契约 §3）。
            int ships = m_Mode == "replay"
                ? (m_Context?.ships?.Length ?? 0)
                : (driver != null ? driver.SlotCount : 0);
            Send(new TwinBridgeAttached
            {
                run_id = m_RunId,
                mode = m_Mode,
                anchor = new TwinBridgeAnchor { east = anchorEast, north = anchorNorth },
                ships = ships,
                camera = m_CurrentPreset,
            });
            Debug.Log($"[Sango.TwinBridge] attached run={m_RunId} mode={m_Mode} anchor=({anchorEast:0.#},{anchorNorth:0.#}) ships={ships}");
        }

        void SendStateHeartbeat()
        {
            if (channel == null || !channel.IsConnected || string.IsNullOrEmpty(m_Mode)) return;
            double nowUnixS = (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
            if (nowUnixS - m_LastStateSentUnixS < StateIntervalS) return;
            m_LastStateSentUnixS = nowUnixS;

            var state = new TwinBridgeState { fps = Math.Round(m_FpsSmoothed * 10.0) / 10.0, camera = m_CurrentPreset, sensor_mode = m_SensorMode };
            if (driver != null)
            {
                state.frame_seq = driver.LastSeq;
                double sim = driver.RenderSimTime;
                if (!double.IsNaN(sim))
                {
                    state.sim_time = sim;
                    // playhead 仅 replay 有义；live 无 web 时钟锚，(sim-0)×1000 恒失真 → 恒报 0
                    state.clock_skew_ms = m_Mode == "replay"
                        ? Math.Max(-60000, Math.Min(60000, (sim - m_Playhead) * 1000.0))
                        : 0.0;
                }
            }
            bool down = m_FetchFailed || (m_Mode == "live" && driver != null && !driver.IsLiveConnected);
            bool stalled = m_Mode == "replay" && m_PlayState == "PLAYING"
                           && m_LastOfferedSim > double.NegativeInfinity
                           && Math.Abs(m_LastOfferedSim - m_Playhead) > Math.Max(1.0, m_Rate);
            state.stream = new TwinBridgeStreamHealth
            {
                state = down ? "down" : stalled ? "degraded" : "ok",
                latency_ms = Math.Abs(state.clock_skew_ms),
            };
            state.detection = new TwinBridgeDetectionState
            {
                source = m_DetectionSource,
                enabled = m_DetectionEnabled, // F7：死字段接线（契约 §8 演进只加字段）——心跳回显 web 既有开关态
                live = overlay != null && overlay.HasFreshLiveResult,
            };
            Send(state);
        }

        void SendError(string code, string message)
        {
            Debug.LogWarning($"[Sango.TwinBridge] error {code}: {message}");
            Send(new TwinBridgeError { code = code, message = TruncateMessage(message) });
        }

        void Send(TwinBridgeReady message) => SendJson(message.ToJson());
        void Send(TwinBridgeAttached message) => SendJson(message.ToJson());
        void Send(TwinBridgeState message) => SendJson(message.ToJson());
        void Send(TwinBridgeError message) => SendJson(message.ToJson());

        void SendJson(string json)
        {
            if (channel == null || !channel.IsConnected) return;
            channel.SendJson(json);
        }

        // ── 词汇映射（契约 §2/§3） ──────────────────────────────────────────────

        static bool TryMapPreset(string preset, out CameraView view)
        {
            switch (preset)
            {
                case "bridge": view = CameraView.Bridge; return true;
                case "bow": view = CameraView.Bow; return true;
                case "chase": view = CameraView.Chase; return true;
                case "top": view = CameraView.TopDown; return true;
                case "overlook": view = CameraView.Overlook; return true;
                default: view = CameraView.Bridge; return false;
            }
        }

        static string PresetOf(CameraView view)
        {
            switch (view)
            {
                case CameraView.Bow: return "bow";
                case CameraView.Chase: return "chase";
                case CameraView.TopDown: return "top";
                case CameraView.Overlook: return "overlook";
                default: return "bridge";
            }
        }

        static float ThemeHours(string theme)
        {
            switch (theme)
            {
                case "dusk": return 17.5f;
                case "night": return 0f;
                default: return 12f;
            }
        }

        static string ClassifyBackendError(Exception error, string runId)
        {
            string text = error?.Message ?? "";
            if (text.Contains("HTTP 404")) return TwinBridge.ErrorRunNotFound;
            if (text.Contains("Unable to connect") || text.Contains("Connection refused") || text.Contains("timeout")
                || text.Contains("ConnectionError") || text.Contains("HttpRequestException") || text.Contains("No connection"))
                return TwinBridge.ErrorBackendUnreachable;
            return TwinBridge.ErrorReplayFetchFailed;
        }

        static string TruncateMessage(string message)
        {
            if (string.IsNullOrEmpty(message)) return "";
            return message.Length <= 200 ? message : message.Substring(0, 200) + "…";
        }

        // ── descriptor 播放性子集（replay 响应，只声明 twin 消费字段） ───────────

        [Serializable]
        class ReplayDescriptorSubset
        {
            public string run_id;
            public ReplayFactsSubset replay;
            public ReplayCapabilitiesSubset capabilities;
        }

        [Serializable]
        class ReplayFactsSubset
        {
            public string state;
            public double t_start;
            public double t_end;
            public double trusted_t_end;
        }

        [Serializable]
        class ReplayCapabilitiesSubset
        {
            public bool seekable;
        }

        // ── CLI 自举：--sango-twin-bridge = bridge 总闸（场景预接线；默认关闸零变化） ──

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), SangoSeamConfig.TwinBridgeCliFlag) < 0) return;
            var service = FindFirstObjectByType<TwinBridgeService>();
            if (service == null)
            {
                Debug.LogError("[Sango.TwinBridge] " + SangoSeamConfig.TwinBridgeCliFlag +
                               " set but no TwinBridgeService in scene — build the SangoTwin scene first");
                return;
            }
            service.EnsureWiring();
            service.runtimeEnabled = true;
            Debug.Log("[Sango.TwinBridge] enabled via " + SangoSeamConfig.TwinBridgeCliFlag);
        }
    }
}
