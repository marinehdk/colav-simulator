using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子②：帧元数据 + 组装纯函数（spec #86 Testing Decisions："FramePublisher encode-path
    /// （frame metadata assembly）without a socket"）。发布器每帧发 3 段 ZMQ multipart：
    /// [topic "sango.frame"] [本结构 JSON] [JPEG 字节]。线上协议文档：sango/Docs/contracts/frame-publisher-v1.md。
    /// EditMode 只测组装与 JSON 往返，绝不建 socket。
    /// </summary>
    [Serializable]
    public class FrameMetadata
    {
        /// <summary>发布器内单调递增帧号（DetectionResult.frame_seq 与之对齐）。</summary>
        public int frame_seq;

        /// <summary>发布时刻（秒，Time.time）。</summary>
        public double frame_time_s;

        /// <summary>帧宽/高（像素）。</summary>
        public int width;
        public int height;

        /// <summary>第 3 段 JPEG 字节数（接收端完整性核对）。</summary>
        public int jpeg_bytes;

        /// <summary>发布源标识（"sango"）。</summary>
        public string source;
        /// <summary>Optional inference request; old senders fall back to detector CLI confidence.</summary>
        public float confidence_threshold = 0.25f;

        // ── P3-S2 机位族演进（spec #90；twin-bridge sensor_mode 载体段，只加字段） ──
        /// <summary>
        /// 桅杆机位标识（observations-v1 §3 契约引用键；空 = 旧桥楼馈送未标机位）。
        /// JsonUtility 对旧发送端缺字段给零值，接收端宽松消费（契约只加字段）。
        /// </summary>
        public string mount_id = "";
        /// <summary>
        /// 当帧位姿快照（P3-S2 写档：旁路进 FrameMetadata——方案 (a) 契约以
        /// (mount_id, frame_seq, frame_time_s) 三元组为引用、后端取权威 ownship
        /// 状态还原位姿，故本快照仅诊断/对账用，非 georef 权威输入）。
        /// 坐标 = Unity 场景系（东=+x、北=+z；**未加 attached.anchor**——发布器
        /// 不知数据面锚点；与后端对账时由消费方补锚）。yaw = 北向东顺时针度。
        /// </summary>
        public double pose_east_m;
        public double pose_north_m;
        public double pose_yaw_deg;
    }

    public static class FramePublisherCore
    {
        /// <summary>组装一帧元数据（纯函数，无副作用；P3-S2 前签名，既有测试/调用不动）。</summary>
        public static FrameMetadata BuildMetadata(int frameSeq, double frameTimeS, int width, int height, int jpegBytes, string source)
        {
            return BuildMetadata(frameSeq, frameTimeS, width, height, jpegBytes, source, "", 0.0, 0.0, 0.0);
        }

        /// <summary>组装一帧元数据（P3-S2 机位族：mount_id + 位姿快照；只加参数重载）。</summary>
        public static FrameMetadata BuildMetadata(int frameSeq, double frameTimeS, int width, int height, int jpegBytes,
            string source, string mountId, double poseEastM, double poseNorthM, double poseYawDeg)
        {
            return new FrameMetadata
            {
                frame_seq = frameSeq,
                frame_time_s = frameTimeS,
                width = width,
                height = height,
                jpeg_bytes = jpegBytes,
                source = source,
                mount_id = mountId ?? "",
                pose_east_m = poseEastM,
                pose_north_m = poseNorthM,
                pose_yaw_deg = poseYawDeg,
            };
        }

        /// <summary>元数据 → JSON（multipart 第 2 段的线上形状）。</summary>
        public static string MetadataToJson(FrameMetadata metadata)
        {
            return JsonUtility.ToJson(metadata);
        }
    }
}
