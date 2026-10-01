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
    }

    public static class FramePublisherCore
    {
        /// <summary>Normalize top-origin GPU rows to the image encoder's bottom-origin input; preserve columns and RGBA channels.</summary>
        public static void FlipRgbaRows(byte[] pixels, int rowBytes, int height, byte[] rowScratch)
        {
            for (int top = 0, bottom = height - 1; top < bottom; top++, bottom--)
            {
                Buffer.BlockCopy(pixels, top * rowBytes, rowScratch, 0, rowBytes);
                Buffer.BlockCopy(pixels, bottom * rowBytes, pixels, top * rowBytes, rowBytes);
                Buffer.BlockCopy(rowScratch, 0, pixels, bottom * rowBytes, rowBytes);
            }
        }

        /// <summary>组装一帧元数据（纯函数，无副作用）。</summary>
        public static FrameMetadata BuildMetadata(int frameSeq, double frameTimeS, int width, int height, int jpegBytes, string source)
        {
            return new FrameMetadata
            {
                frame_seq = frameSeq,
                frame_time_s = frameTimeS,
                width = width,
                height = height,
                jpeg_bytes = jpegBytes,
                source = source,
            };
        }

        /// <summary>元数据 → JSON（multipart 第 2 段的线上形状）。</summary>
        public static string MetadataToJson(FrameMetadata metadata)
        {
            return JsonUtility.ToJson(metadata);
        }
    }
}
