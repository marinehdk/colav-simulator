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
