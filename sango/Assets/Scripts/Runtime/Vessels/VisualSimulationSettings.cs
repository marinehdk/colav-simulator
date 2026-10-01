using System;
using UnityEngine;

namespace Sango
{
    public enum VisualSceneMode { RealStrait, Procedural }
    public enum VisualWaypointPattern { ForwardEncounter, Random, HeadOn, Crossing }
    public enum VisualSensorMode { GroundTruth, YoloAndTruthRadar }
    public enum VisualTargetMotion { Stationary, Straight, Waypoints }

    [Serializable]
    public class VisualSceneDocument
    {
        public string schema_version;
        public string coordinate_system;
        public Vector3 origin_world_m;
        public VisualSimulationSettings settings;
    }

    [Serializable]
    public class VisualTargetVessel
    {
        public int id = 1;
        public bool enabled = true;
        public VesselClass vesselClass = VesselClass.Tug;
        public Vector2 offsetMeters = new Vector2(-100f, 150f);
        public float headingDeg = 90f, speedMps = 4f;
        public VisualTargetMotion motion = VisualTargetMotion.Waypoints;
        public Vector2[] waypoints = Array.Empty<Vector2>();
        public bool loop = true;

        public VisualTargetVessel Copy()
        {
            var copy = (VisualTargetVessel)MemberwiseClone();
            copy.waypoints = waypoints == null ? null : (Vector2[])waypoints.Clone();
            return copy;
        }
    }

    [Serializable]
    public class VisualSimulationSettings
    {
        public VisualSceneMode sceneMode = VisualSceneMode.RealStrait;
        public int environmentCount = 1;
        public int agentsPerEnvironment = 2;
        public float environmentSpacingM = 500f;
        public bool enclosures;
        public float currentSpeedMps;
        public float currentDirectionDeg;
        public int spectrumApproximation = 1;
        public bool generateIslands;
        public float islandScaleM = 50f;
        public float islandHeightM = 15f;
        public float islandFalloffM = 5f;
        public int islandOctaves = 4;
        public float islandSmoothA = 2f, islandSmoothB = 2f;
        public float islandPersistence = 0.5f, islandLacunarity = 2.5f;
        public float islandOffsetX = 1337f, islandOffsetY = 1337f;
        public int seed = 42;
        public float arrivalDistanceM = 15f;
        public bool showWaypoints = true;
        public float waypointMinFraction = 0.25f, waypointMaxFraction = 0.4f;
        public VisualWaypointPattern waypointPattern = VisualWaypointPattern.ForwardEncounter;
        public VesselClass vesselClass = VesselClass.Fcb45;
        public int egoId;
        public bool onboardCamera = true;
        public VisualSensorMode sensorMode = VisualSensorMode.GroundTruth;
        public float detectionIntervalS = 0.125f, confidence = 0.25f;
        public float observationDistanceM = 300f;
        public bool truthAssistedCameraLock = true;
        public float radarRangeM = 500f, radarRpm = 60f;
        public float cruiseSpeedMps = 4f;
        public VisualTargetVessel[] targets = Array.Empty<VisualTargetVessel>();

        public VisualSimulationSettings Copy()
        {
            var copy = (VisualSimulationSettings)MemberwiseClone();
            if (targets != null)
            {
                copy.targets = new VisualTargetVessel[targets.Length];
                for (int i = 0; i < targets.Length; i++) copy.targets[i] = targets[i]?.Copy();
            }
            return copy;
        }

        public VisualTargetVessel TargetFor(int id)
        {
            if (targets != null) foreach (var target in targets) if (target != null && target.id == id) return target;
            return null;
        }

        public string ValidationError()
        {
            if (environmentCount < 1 || environmentCount > 16 || agentsPerEnvironment < 1 ||
                agentsPerEnvironment > 32 || (long)environmentCount * agentsPerEnvironment > 32)
                return "Use 1..16 environments and at most 32 vessels in total.";
            if (sceneMode == VisualSceneMode.RealStrait && environmentCount != 1)
                return "Real Strait has one geographic environment; use Procedural for a grid.";
            if (!Enum.IsDefined(typeof(VisualSceneMode), sceneMode) ||
                !Enum.IsDefined(typeof(VisualWaypointPattern), waypointPattern) ||
                !Enum.IsDefined(typeof(VisualSensorMode), sensorMode)) return "Select a supported scene, route and sensor mode.";
            if (egoId < 0 || egoId >= environmentCount * agentsPerEnvironment) return "Ego ID is outside the configured vessel list.";
            if (TargetFor(egoId)?.enabled == false) return "The selected ego vessel is removed; select an active ID.";
            if (targets != null && targets.Length > 32) return "At most 32 per-vessel definitions are supported.";
            var ids = new System.Collections.Generic.HashSet<int>();
            if (targets != null) foreach (var target in targets)
            {
                if (target == null || target.id < 0 || target.id >= environmentCount * agentsPerEnvironment || !ids.Add(target.id))
                    return "Each target needs a unique ID within the configured vessel list.";
                if (!Enum.IsDefined(typeof(VisualTargetMotion), target.motion) ||
                    !InRange(target.offsetMeters.x, -5000f, 5000f) || !InRange(target.offsetMeters.y, -5000f, 5000f) ||
                    !InRange(target.headingDeg, 0f, 360f) || !InRange(target.speedMps, 0f, 15f))
                    return $"Target {target.id}: use finite position, heading 0..360 and speed 0..15 m/s.";
                if (target.waypoints != null) foreach (var wp in target.waypoints)
                {
                    if (!InRange(wp.x, -10000f, 10000f) || !InRange(wp.y, -10000f, 10000f))
                        return $"Target {target.id}: waypoints must be finite local metre coordinates.";
                    if (enclosures && (Mathf.Abs(wp.x) > environmentSpacingM * 0.5f || Mathf.Abs(wp.y) > environmentSpacingM * 0.5f))
                        return $"Target {target.id}: waypoint is outside the enclosed environment.";
                }
                if (enclosures && (Mathf.Abs(target.offsetMeters.x) > environmentSpacingM * 0.5f || Mathf.Abs(target.offsetMeters.y) > environmentSpacingM * 0.5f))
                    return $"Target {target.id}: initial pose is outside the enclosure.";
                if (enclosures && target.motion == VisualTargetMotion.Straight)
                    return $"Target {target.id}: use an enclosed waypoint route instead of unlimited straight travel.";
            }
            if (!InRange(environmentSpacingM, 200f, 3000f)) return "Environment spacing must be 200..3000 m.";
            if (!InRange(waypointMinFraction, 0.05f, 1.5f) || !InRange(waypointMaxFraction, 0.05f, 1.5f) ||
                waypointMaxFraction <= waypointMinFraction) return "Waypoint maximum must exceed minimum (0.05..1.5 spacing fractions).";
            if (enclosures && waypointMaxFraction > 0.45f) return "Enclosed waypoint distances must fit within 0.45 of spacing.";
            if (!InRange(arrivalDistanceM, 1f, 100f) || !InRange(cruiseSpeedMps, 0.5f, 15f)) return "Use arrival distance 1..100 m and speed 0.5..15 m/s.";
            if (!InRange(currentSpeedMps, 0f, 3f) || !InRange(currentDirectionDeg, 0f, 360f)) return "Use current 0..3 m/s and direction 0..360 degrees.";
            if (spectrumApproximation < 0 || spectrumApproximation > 2) return "Select one of the three HDRP visual spectrum approximations.";
            if (!InRange(detectionIntervalS, 0.1f, 2f) || !InRange(confidence, 0.01f, 1f) ||
                !InRange(observationDistanceM, 10f, 2000f)) return "Use detection interval 0.1..2 s, confidence 0.01..1 and observation distance 10..2000 m.";
            if (!InRange(radarRangeM, 200f, 2000f) || !InRange(radarRpm, 2.5f, 120f)) return "Use radar range 200..2000 m and sweep 2.5..120 RPM.";
            if (sceneMode == VisualSceneMode.Procedural && generateIslands &&
                (!InRange(islandScaleM, 10f, 200f) || !InRange(islandHeightM, 1f, 60f) ||
                 !InRange(islandFalloffM, 1f, 30f) || islandOctaves < 1 || islandOctaves > 8 ||
                 !InRange(islandSmoothA, 1f, 6f) || !InRange(islandSmoothB, 1f, 6f) ||
                 !InRange(islandPersistence, 0.1f, 1f) || !InRange(islandLacunarity, 1f, 4f) ||
                 !InRange(islandOffsetX, -10000f, 10000f) || !InRange(islandOffsetY, -10000f, 10000f)))
                return "Island settings are outside the supported visual-generation budget.";
            return null;
        }

        static bool InRange(float value, float min, float max) => !float.IsNaN(value) && !float.IsInfinity(value) && value >= min && value <= max;
    }
}
