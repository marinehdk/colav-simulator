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
        public static readonly string[] ModesSupported = { "live", "replay" };

        /// <summary>camera 预设词汇（契约 §2，词序 = CameraView 枚举序）。</summary>
        public static readonly string[] CameraPresets = { "bridge", "bow", "chase", "top", "overlook" };

        /// <summary>
        /// camera_free 后 state.camera/attached.camera 的回显词汇（P2-S4 演进条款新增，契约 §8）：
        /// 分屏联动 spike 的自由位姿生效中；任何 camera 预设消息收回控制权。
        /// </summary>
        public const string CameraFreePreset = "free";

        /// <summary>theme 词汇 → WeatherController.timeOfDayHours（契约 §2：day=12, dusk=17.5, night=0）。</summary>
        public static readonly string[] ThemeValues = { "day", "dusk", "night" };

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

    /// <summary>Unity→web `state`（~1Hz 心跳；契约 §3/§6）。</summary>
    [Serializable]
    public class TwinBridgeState
    {
        public string type = "state";
        public double fps;
        public int frame_seq = -1;
        public double sim_time;
        public double clock_skew_ms;
        public TwinBridgeStreamHealth stream = new TwinBridgeStreamHealth();
        public TwinBridgeDetectionState detection = new TwinBridgeDetectionState();
        public string camera = "bridge";

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
