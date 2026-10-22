using System;
using System.Collections.Generic;
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
        // DT 红区(不安全水域):后端 CDT 补集三角,平铺绝对 [east,north]×0.1m 数组
        // (6 数/三角形,hazard_count 个);对象数组会超数据通道消息上限(20261016)。
        public double[] hazard_xy;
        public int hazard_count;
        public TwinDisplayLine[] lines;
        public TwinDisplayTarget[] targets;
        public TwinDisplayPoint[] time_markers;
        public TwinDisplayDisc vo;
        public bool ships_visible, waypoints_visible, hazard_visible;
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
    // P1 本船水线角点（dt-ownship-mask）：本船 LOA×beam 水线矩形经 targets 同一
    // WorldToViewportPoint 数学投到归一化视口坐标。x/y 与 TwinScreenPoint 同域
    // （左上原点、y 向下，可越 [0,1]——部分出画仍给全多边形，出画角点仅标
    // in_frame=false、坐标不钳位）；depth=视空间米；in_frame=角点在画面与裁剪范围内。
    [Serializable] public class TwinOwnshipCorner
    {
        public float x, y, depth;
        public bool in_frame;
    }
    // P1 掩膜中继批记录（Unity → 后端 POST /api/viewport-ownship-polygon 请求体，
    // viewport_ownship_polygon@1）：situation_frame 只走 DataChannel 到浏览器、
    // 后端不可见，故按 ≤10Hz 把自上次 POST 以来的 (frame_id, polygon) 批捎带给后端。
    // polygon=空数组 = 该帧无掩膜（也要上报——检测端区分"明确无掩膜"与"帧未到"）。
    [Serializable] public class TwinOwnshipPolygonFrameEntry
    {
        public int frame_id;
        public TwinOwnshipCorner[] polygon;
    }
    [Serializable] public class TwinOwnshipPolygonReport
    {
        public string schema = "viewport_ownship_polygon@1";
        public string run_id;
        public double sim_time;
        public TwinBridgeCameraPose camera_pose;
        public TwinOwnshipPolygonFrameEntry[] frames;
        public string ToJson() => JsonUtility.ToJson(this);
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
        // P1（20261019）：本船水线多边形（0 或 4 角点，见 TwinOwnshipCorner）；
        // 空数组 = 无掩膜（本船不可解析/相机前方角点 <3，如桥眼位本船在身后），
        // 消费端（web/检测器）必须优雅跳过，不得当错误。旧消费端忽略未知字段。
        public TwinOwnshipCorner[] ownship_polygon;
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
        // P1 本船水线多边形：4 角点顺序恒 [艏左舷, 艏右舷, 艉右舷, 艉左舷]（规范船体系
        // +Z 艏/+X 右舷，世界系四角由 TwinSessionDriver.TryGetOwnShipWaterline 给出），
        // 经与 targets 投影同一 WorldToViewportPoint 数学投影。近轴前方的角点全保留
        // （出画不钳位——部分出画仍给全多边形，消费端 fillPoly/凸包自行裁剪，出画角点
        // in_frame=false）；相机身后角点丢弃。相机前方角点 <3（本船不可解析/大多在
        // 相机身后，如桥眼位）→ 空数组 = 无掩膜；camera=null（无相机场景）同样空数组。
        public static TwinOwnshipCorner[] OwnshipPolygon(
            Camera camera, Vector3 bowPort, Vector3 bowStarboard, Vector3 sternStarboard, Vector3 sternPort)
        {
            if (camera == null) return Array.Empty<TwinOwnshipCorner>();
            var world = new[] { bowPort, bowStarboard, sternStarboard, sternPort };
            var corners = new List<TwinOwnshipCorner>(4);
            foreach (var point in world)
            {
                var p = camera.WorldToViewportPoint(point);
                if (p.z <= camera.nearClipPlane) continue;
                corners.Add(new TwinOwnshipCorner {
                    x = p.x, y = 1 - p.y, depth = p.z,
                    in_frame = p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1 && p.z < camera.farClipPlane,
                });
            }
            return corners.Count >= 3 ? corners.ToArray() : Array.Empty<TwinOwnshipCorner>();
        }
    }
}
