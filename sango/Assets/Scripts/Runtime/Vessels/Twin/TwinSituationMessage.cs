using System;
using UnityEngine;

namespace Sango
{
    // Read-only display geometry. Never changes the session clock, ship state or threat authority.
    [Serializable] public class TwinSituationMessage
    {
        public string run_id;
        public int seq;
        public double sim_time;
        public TwinDisplayPoint[] ribbon, waypoints;
        public TwinDisplayLine[] lines;
        public TwinDisplayTarget[] targets;
        public TwinDisplayPoint[] time_markers;
        public TwinDisplayDisc vo;
        public bool ships_visible, waypoints_visible;
        // dt-sensor-overlay 契约：YOLO 检测（web 侧已按图层/per-target 门控裁剪；图层开关不发 Unity）。
        public TwinDisplayDetection[] detections;
    }
    [Serializable] public class TwinDisplayPoint
    {
        public double east, north;
        public string label;
    }
    [Serializable] public class TwinDisplayTarget : TwinDisplayPoint
    {
        public string id, key;
        public bool truth;
        public float length, width;
        // IPDA 存在概率；-1 = 未知/god（web 侧哨兵），旧消息缺字段 → 0f（仅帧 echo，无渲染后果）。
        public float existence;
    }
    // Georef 检测（dt-sensor-overlay 契约 B 段；字段名 JsonUtility 逐字匹配，故用 length/width 而非 length_m）。
    [Serializable] public class TwinDisplayDetection : TwinDisplayPoint
    {
        public float length, width;
        public float confidence;
        public string class_name;
        public int sensor_id;
        public string key;
        public string track_key;   // "" = 无关联（JsonUtility 无法 round-trip null string）
    }
    [Serializable] public class TwinDisplayLine
    {
        public string id, color;
        public float width;
        public bool dashed;
        public TwinDisplayPoint[] points;
    }
    [Serializable] public class TwinDisplayDisc
    {
        public double east, north;
        public float radius;
        public string png;
    }
    [Serializable] public class TwinScreenPoint
    {
        public string id, key, label;
        public float x, y, depth, left, top, width, height;
        public bool visible;
        // targets 帧 echo IPDA existence（-1=未知/god）；waypoints/time_markers 恒 0，消费端不得读。
        public float existence;
    }
    // C 段帧回包检测投影（TwinScreenDetection 继承屏幕点字段；id/label 恒空，key = det_id）。
    [Serializable] public class TwinScreenDetection : TwinScreenPoint
    {
        public float confidence;
        public string class_name;
        public int sensor_id;
        public string track_key;
    }
    [Serializable] public class TwinSituationFrame
    {
        public string type = "situation_frame", run_id, camera;
        public int frame_id, source_seq, telemetry_seq, width, height;
        public double sim_time;
        public float camera_yaw;
        public TwinBridgeCameraPose camera_pose;
        public TwinBridgeLandscapeState landscape;
        public TwinScreenPoint[] targets, waypoints, time_markers;
        public TwinScreenDetection[] detections;
        public string ToJson() => JsonUtility.ToJson(this);
    }
    [Serializable] public class TwinSituationPick
    {
        public string type = "situation_pick", run_id, key, id;
        public int frame_id;
        public string ToJson() => JsonUtility.ToJson(this);
    }

    public static class TwinSituationMath
    {
        public const int MarkerWidth = 256, MarkerHeight = 16;
        public static uint MarkerBits(int frame)
        {
            int value = frame & 65535;
            int check = ((value >> 8) ^ value ^ 0x5A) & 255;
            return 0xD3000000u | ((uint)value << 8) | (uint)check;
        }
        // A click uses the bounds of the video frame the operator actually saw.
        public static TwinScreenPoint Pick(TwinSituationFrame frame, float x, float y)
        {
            if (frame?.targets == null || !Finite(x) || !Finite(y) || x < 0 || x > 1 || y < 0 || y > 1) return null;
            TwinScreenPoint result = null;
            foreach (var point in frame.targets)
            {
                if (!point.visible || point.depth <= 0) continue;
                float padX = 12f / Mathf.Max(1, frame.width), padY = 12f / Mathf.Max(1, frame.height);
                if (x < point.left - padX || x > point.left + point.width + padX ||
                    y < point.top - padY || y > point.top + point.height + padY) continue;
                if (result == null || point.depth < result.depth) result = point;
            }
            return result;
        }
        public static bool Finite(double value) => !double.IsNaN(value) && !double.IsInfinity(value);
    }
}
