using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// twin-bridge-v1 契约 DTO（P2-S3 spec #89；契约文档 sango/Docs/contracts/twin-bridge-v1.md）。
    /// web 页面（唯一 UI 编排权威）↔ Unity sango 控制+状态通道，载体 = URS DataChannel 单个
    /// UTF-8 JSON 文本帧（twin-bridge-v1.md §1）。
    /// - web→Unity：形状各异但字段面小，JsonUtility 无多态/无字典 → 单一信封类
    ///   <see cref="TwinBridgeCommand"/> 承载全部 type 的字段面，Parse 后按 type 分派；
    ///   未知字段 JsonUtility 静默忽略（契约 §1：演进只加不减）。
    /// - Unity→web：Ready/Attached/State/Error 各自 ToJson（JsonUtility 恒写全字段，契约 §6 注）。
    /// - 样例字面量 = 契约 §6 冻结样例（EditMode 与 web 测试同源对拍，沿 detection-return-v1 工艺）。
    /// </summary>
    public static class TwinBridge
    {
        /// <summary>协议版本（hello.protocol / ready.protocol；不匹配回 UNSUPPORTED_PROTOCOL）。</summary>
        public const string Protocol = "twin-bridge@1";

        /// <summary>URS DataChannel label（契约 §1 冻结）。</summary>
        public const string ChannelLabel = "twin-bridge";

        /// <summary>支持的 attach 模式（契约 §2）。</summary>
        public static readonly string[] ModesSupported = { "live", "replay", "static" };

        /// <summary>camera 预设词汇（契约 §2，词序 = CameraView 枚举序）。</summary>
        public static readonly string[] CameraPresets = { "bridge", "bow", "chase", "top", "overlook" };

        /// <summary>
        /// camera_free 后 state.camera/attached.camera 的回显词汇（P2-S4 演进条款新增，契约 §8）：
        /// 分屏联动 spike 的自由位姿生效中；任何 camera 预设消息收回控制权。
        /// </summary>
        public const string CameraFreePreset = "free";

        /// <summary>theme 词汇 → WeatherController.timeOfDayHours（契约 §2：day=12, dusk=17.5, night=0）。</summary>
        public static readonly string[] ThemeValues = { "day", "dusk", "night" };

        /// <summary>
        /// sensor_mode 词汇（P3-S0 契约 §2/§8 演进新增，spec #90）：主孪生视口传感器模式——
        /// eo=可见光（默认）/ ir=黑白热像 / lidar=点云视角；雷达 PPI/AIS 为 web 面板态不经此桥。
        /// P2 IR realism 轮演进（只加不减）：ir_whitehot/ir_blackhot 显式极性（survey
        /// 2026-10-19-sitaw-ir-latency-realism §4 #1，M232 white hot/black hot）；
        /// ir 保留为白热别名（冻结样例与旧 web 兼容）。
        /// </summary>
        public static readonly string[] SensorModes = { "eo", "ir", "ir_whitehot", "ir_blackhot", "lidar" };

        /// <summary>白热显式值（P2 IR realism；ir 为其别名）。</summary>
        public const string IrWhiteHotMode = "ir_whitehot";

        /// <summary>黑热显式值（P2 IR realism；同一负像数据的反转显示映射）。</summary>
        public const string IrBlackHotMode = "ir_blackhot";

        /// <summary>sensor_mode 默认值（契约 §3 state 回显：驾驶舱视角默认可见光）。</summary>
        public const string DefaultSensorMode = "eo";

        /// <summary>
        /// radar_view 词汇（2026-10-21 P0 契约 §2/§8 演进新增，00-REPORT §2.2）：雷达
        /// 表现层开关——off=表现全关（默认）/ overlay=3D 探测表现（P1 水面 spoke 余辉盘+
        /// 盲区可视化）/ ppi=独立雷达屏（P2 全要素 PPI）/ both=两者同开。只控 Unity 渲染
        /// 呈现：数据面（envelope radar_scans + checkpoint REST，RadarSpokeStream）恒活，
        /// 与本开关正交。命令字段面 = mode（契约 §2，区别于 sensor_mode 的 value）。
        /// </summary>
        public static readonly string[] RadarViewValues = { "off", "overlay", "ppi", "both" };

        /// <summary>radar_view 默认值（契约 §2：旧 web 不发本命令即 off 态）。</summary>
        public const string DefaultRadarView = "off";

        public static bool IsValidMode(string mode)
        {
            foreach (var candidate in ModesSupported) if (candidate == mode) return true;
            return false;
        }

        public static bool IsValidPreset(string preset)
        {
            foreach (var candidate in CameraPresets) if (candidate == preset) return true;
            return false;
        }

        public static bool IsValidTheme(string value)
        {
            foreach (var candidate in ThemeValues) if (candidate == value) return true;
            return false;
        }

        public static bool IsValidSensorMode(string value)
        {
            foreach (var candidate in SensorModes) if (candidate == value) return true;
            return false;
        }

        public static bool IsValidRadarView(string value)
        {
            foreach (var candidate in RadarViewValues) if (candidate == value) return true;
            return false;
        }

        /// <summary>
        /// radar_view 表现层效果查询（纯函数，EditMode 可测；SensorModeEffect 同款静态
        /// 查询面）：overlay = 3D 水面探测盘（P1 接线），ppi = 独立雷达屏（P2 接线）。
        /// P0 阶段效果面即词汇判定——表现层消费口落地前仅作状态镜像/探针面。
        /// </summary>
        public static void RadarViewEffect(string radarView, out bool overlayActive, out bool ppiActive)
        {
            overlayActive = radarView == "overlay" || radarView == "both";
            ppiActive = radarView == "ppi" || radarView == "both";
        }

        /// <summary>
        /// True when a sensor_mode value selects the IR channel (ir alias or an
        /// explicit polarity value) — shared by the effect table and web-side
        /// vocabulary mirrors.
        /// </summary>
        public static bool IsIrMode(string sensorMode)
            => sensorMode == "ir" || sensorMode == IrWhiteHotMode || sensorMode == IrBlackHotMode;

        /// <summary>
        /// sensor_mode 渲染/语义效果（P3-S2 接线，spec #90；P3-S3 起为真实现表；
        /// P2 IR realism 加极性输出。纯函数，EditMode 可测）：eo = 默认正常渲染；
        /// ir/ir_whitehot = 流相机开 IR 白热 pass（黑白热像 + 温度 tag）；
        /// ir_blackhot = 同 pass 极性反转（blackHot=true）；lidar = 流相机开点云视角
        /// （P3-S3：深色背景 + mast_lidar 深度 16 线点云）。任何模式都不改相机预设
        /// （正交叠加，契约 §2）。
        /// </summary>
        public static void SensorModeEffect(string sensorMode, out bool irRenderActive, out bool lidarRenderActive, out bool blackHot)
        {
            irRenderActive = IsIrMode(sensorMode);
            lidarRenderActive = sensorMode == "lidar";
            blackHot = sensorMode == IrBlackHotMode;
        }

        /// <summary>错误码表（契约 §4 冻结）。</summary>
        public const string ErrorBadMessage = "BAD_MESSAGE";
        public const string ErrorUnsupportedMode = "UNSUPPORTED_MODE";
        public const string ErrorUnsupportedProtocol = "UNSUPPORTED_PROTOCOL";
        public const string ErrorBackendUnreachable = "BACKEND_UNREACHABLE";
        public const string ErrorRunNotFound = "RUN_NOT_FOUND";
        public const string ErrorRunNotPlayable = "RUN_NOT_PLAYABLE";
        public const string ErrorReplayFetchFailed = "REPLAY_FETCH_FAILED";
        public const string ErrorRebuild = "REBUILD";
    }

    /// <summary>web→Unity 命令信封：全部 type 的字段面并集（解析容错见 TwinBridge 类注）。</summary>
    [Serializable]
    public class TwinBridgeCommand
    {
        public string type;
        // hello
        public string protocol;
        public string page;
        // attach
        public string run_id;
        public string mode;
        public string backend_base;
        public TwinBridgeReplaySpan replay;
        // clock
        public double playhead_s;
        public double rate = 1.0;
        public string state;
        // camera / theme / detection
        public string preset;
        public string value;
        public bool enabled;
        public string source;
        // camera_free（P2-S4 契约 §8 演进记录新增，只加字段）：pos 为相机锚点全域 UTM 米
        // （与 attached.anchor 同一框架，Unity 侧减锚得场景坐标）；pitch 负=俯；fov 垂直向度。
        public TwinBridgeFreePose pos;
        public double yaw_deg;
        public double pitch_deg;
        public double fov_deg;
        // DT read-only presentation and frame-specific picking.
        public TwinSituationMessage presentation;
        public string target_key;
        public int frame_id;
        public float x, y;
        // presentation_shard(20261016):大 presentation 分片(数据通道消息 ~64KB 上限,
        // gst webrtcbin 侧超限即断链)——web 按 (run_id,seq) 拆片,Unity 侧重组。
        public int seq;
        public int index, total;
        public string part;

        /// <summary>契约 §6 attach 样例字面量（冻结；EditMode/web 测试对拍同源）。</summary>
        public const string ContractAttachSample =
            "{\"type\":\"attach\",\"run_id\":\"3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb\",\"mode\":\"replay\"," +
            "\"backend_base\":\"http://127.0.0.1:8010\"," +
            "\"replay\":{\"t_start\":0.1,\"t_end\":40,\"trusted_t_end\":40}}";

        public static TwinBridgeCommand FromJson(string json) => JsonUtility.FromJson<TwinBridgeCommand>(json);
    }

    /// <summary>camera_free.pos 子对象（P2-S4 演进）：相机锚点全域 UTM 米 + 高度（米，
    /// 椭球零视觉约定，与 ENC 网格 h=0 同一视觉基准）。JsonUtility 语义同 replay：键缺失 = 零值实例。</summary>
    [Serializable]
    public class TwinBridgeFreePose
    {
        public double east;
        public double north;
        public double height_m;
    }

    /// <summary>attach.replay 子对象（replay 模式必带，秒）。JsonUtility 语义：键缺失时给
    /// 零值实例（非 null）——live/ replay 分派以 mode 字段为准（TwinBridgeService.HandleAttach）。</summary>
    [Serializable]
    public class TwinBridgeReplaySpan
    {
        public double t_start;
        public double t_end;
        public double trusted_t_end;
    }

    /// <summary>Unity→web `ready`（契约 §3/§6）。</summary>
    [Serializable]
    public class TwinBridgeReady
    {
        public string type = "ready";
        public string protocol = TwinBridge.Protocol;
        public string build;
        public string scene;
        public string[] modes_supported = TwinBridge.ModesSupported;
        public string[] video_profiles;
        public string situation_sync = "frame-marker@1";

        public string ToJson() => JsonUtility.ToJson(this);

        public static TwinBridgeReady FromJson(string json) => JsonUtility.FromJson<TwinBridgeReady>(json);
    }

    /// <summary>attached.anchor：数据面原点锚定值（全域 UTM 米；S1 交付语义 TwinAnchor）。</summary>
    [Serializable]
    public class TwinBridgeAnchor
    {
        public double east;
        public double north;
    }

    /// <summary>Unity→web `attached`（数据面就绪；重连恢复后重发，契约 §3/§5）。</summary>
    [Serializable]
    public class TwinBridgeAttached
    {
        public string type = "attached";
        public string run_id;
        public string mode;
        public TwinBridgeAnchor anchor = new TwinBridgeAnchor();
        public int ships;
        public string camera = "bridge";

        public string ToJson() => JsonUtility.ToJson(this);

        public static TwinBridgeAttached FromJson(string json) => JsonUtility.FromJson<TwinBridgeAttached>(json);
    }

    /// <summary>state.stream 子对象（契约 §3：ok/degraded/down + latency_ms，未知为 0）。</summary>
    [Serializable]
    public class TwinBridgeStreamHealth
    {
        public string state = "down";
        public double latency_ms;
    }

    /// <summary>state.detection 子对象（契约 §3；enabled = P3 演进只加字段，§8 台账）。</summary>
    [Serializable]
    public class TwinBridgeDetectionState
    {
        public string source = "truth";
        public bool enabled;
        public bool live;
    }

    [Serializable]
    public class TwinBridgeCameraPose : TwinBridgeFreePose
    {
        public double yaw_deg;
        public double pitch_deg;
        public double fov_deg;
    }

    /// <summary>Unity→web `state`（~1Hz 心跳；契约 §3/§6）。sensor_mode = P3-S0 演进只加字段
    /// （契约 §8 台账）：主视口传感器模式回显，默认 eo（JsonUtility 恒写全字段——旧 web 宽松消费零影响）。
    /// geo_fit = P3-12 演进只加字段（契约 §8 台账）：M6 场景覆盖度判定回显
    /// inside|partial|outside，空串 = 尚无数据面帧（旧 web 宽松消费零影响）。</summary>
    [Serializable]
    public class TwinBridgeMotion
    {
        public float visual_heave_m, visual_pitch_deg, roll_deg;
        public float propwash_foam, wave_contact_foam, bow_entry_mps, native_foam_peak;
        public string roll_source;
    }

    [Serializable]
    public class TwinBridgeVideoState
    {
        public int render_width, render_height, capture_width, capture_height;
        public string profile, antialiasing, graphics_api, gpu, codec, encoder;
        public bool dynamic_resolution;
        public float render_scale, taa_sharpen;
    }

    [Serializable] public class TwinBridgeLandscapeState
    {
        public bool ready;
        public bool displayable;
        public string state;
        public float progress, terrain_load;
        public long cache_bytes;
        public int meshes_created, preload_views;
        public long cache_budget_bytes, mesh_memory_bytes, texture_memory_bytes, process_rss_bytes;
        public int meshes_resident;
        public bool refining;
        public float extent_m;
    }

    [Serializable]
    public class TwinBridgeState
    {
        public string type = "state";
        public TwinBridgeVideoState video;
        public double fps;
        public int frame_seq = -1;
        public double sim_time;
        public double clock_skew_ms;
        public TwinBridgeStreamHealth stream = new TwinBridgeStreamHealth();
        public TwinBridgeDetectionState detection = new TwinBridgeDetectionState();
        public string camera = "bridge";
        public string sensor_mode = TwinBridge.DefaultSensorMode;
        public string radar_view = TwinBridge.DefaultRadarView; // 2026-10-21 P0 演进只加字段（契约 §8）：雷达表现层模式回显，默认 off（sensor_mode 同惯例）
        public string geo_fit = "";
        public TwinBridgeCameraPose camera_pose;
        public TwinBridgeLandscapeState landscape;
        public bool presentation_buffering;
        public TwinBridgeMotion motion;

        public string ToJson() => JsonUtility.ToJson(this);

        public static TwinBridgeState FromJson(string json) => JsonUtility.FromJson<TwinBridgeState>(json);
    }

    /// <summary>Unity→web `error`（契约 §4 码表；REBUILD 为信息性非错误）。</summary>
    [Serializable]
    public class TwinBridgeError
    {
        public string type = "error";
        public string code;
        public string message;

        public string ToJson() => JsonUtility.ToJson(this);

        public static TwinBridgeError FromJson(string json) => JsonUtility.FromJson<TwinBridgeError>(json);
    }
}
