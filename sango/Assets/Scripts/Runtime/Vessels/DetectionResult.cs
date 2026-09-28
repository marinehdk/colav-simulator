using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子④：检测框回传契约（phase-2 后端 POST 回 Unity 的 schema，spec #86）。
    /// 冻结文档：sango/Docs/contracts/detection-result-v1.md —— 字段名与 JSON 形状以该文档为准，
    /// 本类是其 C# 镜像（JsonUtility 兼容，plain serializable）。
    /// 框坐标语义：box_xyxy = [x0, y0, x1, y1] 像素坐标，原点画面左上、y 向下（YOLO/视觉惯例）。
    /// 回环测试：DetectionResultRoundTripTests（serialize→deserialize→serialize 无损）。
    /// </summary>
    [Serializable]
    public class DetectionResult
    {
        /// <summary>来源帧序号（FrameMetadata.frame_seq 对齐）。</summary>
        public int frame_seq;

        /// <summary>来源帧时间（秒，帧发布时刻；与 FrameMetadata.frame_time_s 对齐）。</summary>
        public double frame_time_s;

        /// <summary>检测源标识（如 "yolo-a4000"；phase-1 真值路径用 "ground-truth"）。</summary>
        public string source;

        /// <summary>检测框列表（可为空数组 = 无检测）。</summary>
        public Box[] detections;

        /// <summary>单个检测框。</summary>
        [Serializable]
        public class Box
        {
            /// <summary>[x0, y0, x1, y1] 像素坐标（左上原点，y 向下）。</summary>
            public float[] box_xyxy;

            /// <summary>类别 id（YOLO 类索引）。</summary>
            public int class_id;

            /// <summary>类别名（如 "ship"）。</summary>
            public string class_name;

            /// <summary>置信度 [0,1]；真值框恒 1。</summary>
            public float confidence;
        }

        public string ToJson()
        {
            return JsonUtility.ToJson(this);
        }

        public static DetectionResult FromJson(string json)
        {
            return JsonUtility.FromJson<DetectionResult>(json);
        }
    }
}
