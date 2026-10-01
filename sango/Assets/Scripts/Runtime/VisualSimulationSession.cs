using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>Local visual-run control boundary; separate from backend session authority.</summary>
    public class VisualSimulationSession : MonoBehaviour
    {
        public VesselCatalog catalog;
        public WaterSurface water;
        public WeatherController weather;
        public CameraRig cameraRig;
        public RadarOverlay radar;
        public DetectionOverlay overlay;
        public FramePublisher publisher;
        public DetectionResultConsumer consumer;
        public Vector3 sceneOrigin;
        public GameObject[] originalVessels = Array.Empty<GameObject>();
        public GameObject[] realTerrainAndDecor = Array.Empty<GameObject>();
        public M8TileStreaming tileStreaming;
        readonly Dictionary<GameObject, bool> m_OriginalActive = new Dictionary<GameObject, bool>();

        readonly List<WaypointFollower> m_Actors = new List<WaypointFollower>();
        readonly List<Transform> m_Islands = new List<Transform>();
        Material m_IslandMaterial;
        GameObject m_World;
        VisualSimulationSettings m_Applied;
        Vector3[] m_InitialPositions;
        Quaternion[] m_InitialRotations;

        /// <summary>Number of active vessels; Actors retains vacant ID slots after removal.</summary>
        public int ActorCount { get { int count = 0; foreach (var actor in m_Actors) if (actor != null) count++; return count; } }
        public WaypointFollower Ego => m_Applied != null && m_Applied.egoId < m_Actors.Count ? m_Actors[m_Applied.egoId] : null;
        public IReadOnlyList<WaypointFollower> Actors => m_Actors;
        public IReadOnlyList<Transform> Islands => m_Islands;
        public VisualSimulationSettings AppliedSettings => m_Applied?.Copy();
        public string Status { get; private set; } = "Configure a local visual run.";
        public bool IsRunning { get; private set; }
        public bool ManualControl { get; private set; }
        float m_Throttle, m_Rudder;
        const string SceneSchema = "sango.visual-scene@1";
        const string Coordinates = "east=x;north=z;heading=degrees;backend-psi=positive-radians";

        public bool Apply(VisualSimulationSettings draft)
        {
            if (IsRunning) { Status = "Pause the current run before applying another setup."; return false; }
            var error = draft == null ? "Setup is missing." : draft.ValidationError();
            if (error != null) { Status = error; return false; }
            var entry = catalog != null ? catalog.GetEntry(draft.vesselClass) : null;
            if (entry?.prefab == null) { Status = "The selected vessel is not in the local catalog."; return false; }
            if (draft.targets != null) foreach (var target in draft.targets)
                if (target.enabled && catalog.GetEntry(target.vesselClass)?.prefab == null)
                { Status = $"Target {target.id}: vessel type is not in the local catalog."; return false; }

            var settings = draft.Copy();
            var replacement = new GameObject("Local visual vessels");
            replacement.transform.SetParent(transform, false);
            replacement.SetActive(false);
            var actors = new List<WaypointFollower>();
            var islands = new List<Transform>();
            for (int env = 0; env < settings.environmentCount; env++)
            {
                var center = sceneOrigin + new Vector3((env % 4) * settings.environmentSpacingM, 0f,
                    (env / 4) * settings.environmentSpacingM);
                if (settings.sceneMode == VisualSceneMode.Procedural && settings.generateIslands)
                {
                    if (m_IslandMaterial == null)
                    {
                        m_IslandMaterial = new Material(Shader.Find("HDRP/Lit"));
                        m_IslandMaterial.SetColor("_BaseColor", new Color(0.06f, 0.16f, 0.08f));
                        m_IslandMaterial.SetFloat("_Smoothness", 0.1f);
                        HDMaterial.ValidateMaterial(m_IslandMaterial);
                    }
                    var island = PerlinIslandGenerator.GenerateIsland(new IslandSettings {
                        seed = settings.seed + env, sizeRange = Vector2.one * settings.environmentSpacingM * 0.24f,
                        maxHeight = settings.islandHeightM, resolution = 48, material = m_IslandMaterial,
                        noiseOctaves = settings.islandOctaves, noiseScaleM = settings.islandScaleM,
                        edgeDepthM = settings.islandFalloffM, smoothA = settings.islandSmoothA, smoothB = settings.islandSmoothB,
                        persistence = settings.islandPersistence, lacunarity = settings.islandLacunarity,
                        noiseOffset = new Vector2(settings.islandOffsetX, settings.islandOffsetY)
                    });
                    island.transform.SetParent(replacement.transform, false);
                    island.transform.position = center;
                    islands.Add(island.transform);
                }
                for (int vessel = 0; vessel < settings.agentsPerEnvironment; vessel++)
                {
                    int id = env * settings.agentsPerEnvironment + vessel;
                    var fallback = DefaultVessel(settings, id);
                    var target = settings.TargetFor(id)?.Copy() ?? fallback;
                    if (!target.enabled) { actors.Add(null); continue; }
                    var actorEntry = catalog.GetEntry(target.vesselClass);
                    var offset = new Vector3(target.offsetMeters.x, 0f, target.offsetMeters.y);
                    float heading = target.headingDeg;
                    var ship = Instantiate(actorEntry.prefab, center + offset + Vector3.up * actorEntry.waterlineOffsetY,
                        Quaternion.Euler(0f, heading + actorEntry.bowYawDeg, 0f), replacement.transform);
                    ship.name = $"Vessel {id} ({actorEntry.vesselClass})";
                    var follower = ship.GetComponent<WaypointFollower>() ?? ship.AddComponent<WaypointFollower>();
                    follower.bowYawDegOffset = actorEntry.bowYawDeg;
                    follower.cruiseSpeedMps = target.speedMps;
                    follower.arrivalRadiusM = settings.arrivalDistanceM;
                    follower.currentVelocityMps = new Vector2(Mathf.Sin(settings.currentDirectionDeg * Mathf.Deg2Rad),
                        Mathf.Cos(settings.currentDirectionDeg * Mathf.Deg2Rad)) * settings.currentSpeedMps;
                    follower.useTravelBounds = settings.enclosures;
                    follower.travelBounds = new Rect(center.x - settings.environmentSpacingM * 0.5f,
                        center.z - settings.environmentSpacingM * 0.5f, settings.environmentSpacingM, settings.environmentSpacingM);
                    follower.demoHotkeysEnabled = false;
                    follower.autoStart = false;
                    follower.enabled = false; // This session dispatches the sole motion step; legacy standalone followers keep their own Update.
                    follower.loopWaypoints = target.loop;
                    if (target.motion == VisualTargetMotion.Straight)
                    {
                        var direction = new Vector2(Mathf.Sin(heading * Mathf.Deg2Rad), Mathf.Cos(heading * Mathf.Deg2Rad));
                        follower.waypoints = new[] { new Vector2(center.x + offset.x, center.z + offset.z) + direction * 10000f };
                        follower.loopWaypoints = false;
                    }
                    else if (target.motion == VisualTargetMotion.Stationary) follower.waypoints = Array.Empty<Vector2>();
                    else
                    {
                        var route = target.waypoints != null && target.waypoints.Length > 0 ? target.waypoints : fallback.waypoints;
                        follower.waypoints = new Vector2[route.Length];
                        for (int w = 0; w < route.Length; w++) follower.waypoints[w] = new Vector2(center.x, center.z) + route[w];
                    }
                    if (water != null)
                    {
                        var buoyancy = ship.AddComponent<VesselBuoyancy>();
                        buoyancy.waterSurface = water;
                        buoyancy.maxSamplesPerHull = id == settings.egoId ? 64 : 16;
                        if (weather != null)
                        {
                            var lights = ship.AddComponent<NavigationLights>(); lights.weather = weather; lights.bowYawDeg = actorEntry.bowYawDeg;
                            var wetness = ship.AddComponent<HullWaterlineDecals>(); wetness.bootTopBandHeightM = 0.25f;
                            if (id == settings.egoId || settings.environmentCount * settings.agentsPerEnvironment <= 2)
                            {
                                var wake = ship.AddComponent<WakeFoamRig>(); wake.water = water; wake.loaMeters = actorEntry.loaMeters;
                            }
                        }
                    }
                    actors.Add(follower);
                }
            }
            ReleaseIslandMeshes();
            if (m_World != null) { m_World.SetActive(false); DestroyOwned(m_World); }
            m_World = replacement;
            m_Actors.Clear();
            m_Actors.AddRange(actors);
            m_Islands.Clear();
            m_Islands.AddRange(islands);
            m_Applied = settings;
            ManualControl = false;
            m_InitialPositions = new Vector3[m_Actors.Count];
            m_InitialRotations = new Quaternion[m_Actors.Count];
            for (int i = 0; i < m_Actors.Count; i++)
            {
                if (m_Actors[i] == null) continue;
                m_InitialPositions[i] = m_Actors[i].transform.position;
                m_InitialRotations[i] = m_Actors[i].transform.rotation;
            }
            replacement.SetActive(true);
            SetOriginalSceneVisibility(settings.sceneMode == VisualSceneMode.RealStrait);
            SetEgo(settings.egoId);
            ConfigureSensors();
            if (weather != null) { weather.visualSpectrumStyle = settings.spectrumApproximation; weather.Apply(); }
            Status = $"Applied {settings.environmentCount} environment(s), {ActorCount} local vessels, ego {settings.egoId}.";
            return true;
        }

        public void StartRun()
        {
            if (m_Applied == null) { Status = "Apply a setup first."; return; }
            foreach (var actor in m_Actors)
                if (actor != null && actor.waypoints.Length > 0 && !actor.DemoRunning) actor.Toggle();
            IsRunning = true;
            Status = "Local waypoint navigation running (no collision-avoidance policy).";
        }

        public void PauseRun()
        {
            foreach (var actor in m_Actors) if (actor != null && actor.DemoRunning) actor.Toggle();
            IsRunning = false;
            Status = "Local visual run paused.";
        }

        public void ResetRun()
        {
            PauseRun();
            for (int i = 0; i < m_Actors.Count; i++)
            {
                if (m_Actors[i] == null) continue;
                m_Actors[i].transform.SetPositionAndRotation(m_InitialPositions[i], m_InitialRotations[i]);
                m_Actors[i].ResetToTransform();
            }
            Status = "Reset to the applied scene's initial vessel poses.";
        }

        public void Step(float dt)
        {
            if (!IsRunning || dt <= 0f || float.IsNaN(dt) || float.IsInfinity(dt)) return;
            foreach (var actor in m_Actors)
            {
                if (actor == null) continue;
                if (ManualControl && actor == Ego) actor.StepManual(dt, m_Throttle, m_Rudder);
                else if (actor.DemoRunning && !actor.IsArrived) actor.StepOnce(dt);
            }
        }

        void Update()
        {
            Step(Time.deltaTime);
            if (cameraRig == null || m_Applied == null || Ego == null) return;
            Transform nearest = null;
            float distance = m_Applied.truthAssistedCameraLock ? m_Applied.observationDistanceM * m_Applied.observationDistanceM : 0f;
            foreach (var actor in m_Actors)
            {
                if (actor == null || actor == Ego) continue;
                var offset = actor.transform.position - Ego.transform.position;
                if (offset.sqrMagnitude < distance)
                { nearest = actor.transform; distance = offset.sqrMagnitude; }
            }
            cameraRig.observationTarget = nearest;
        }

        public bool SetEgo(int id)
        {
            if (m_Applied == null || id < 0 || id >= m_Actors.Count || m_Actors[id] == null)
            { Status = "Select an active local vessel ID."; return false; }
            m_Applied.egoId = id;
            if (tileStreaming != null) tileStreaming.reference = Ego.transform;
            ManualControl = false;
            m_Throttle = m_Rudder = 0f;
            var others = new List<Transform>();
            foreach (var actor in m_Actors) if (actor != null && actor != Ego) others.Add(actor.transform);
            if (overlay != null) { overlay.ships = others.ToArray(); overlay.ClearLiveResult(); }
            if (radar != null)
            {
                radar.SetShips(Ego.transform, others.ToArray());
                radar.SetRange(m_Applied.radarRangeM);
                radar.SetSweepSpeed(m_Applied.radarRpm * 6f);
            }
            if (cameraRig != null)
            {
                var entry = catalog.GetEntry(GetVesselDefinition(id).vesselClass);
                cameraRig.followShip = Ego.transform;
                cameraRig.bridgeShipRelative = true;
                bool fcb = entry.vesselClass == VesselClass.Fcb45;
                cameraRig.bridgeMount = Mount(Ego.transform, "Bridge mount", new Vector3(0f,
                    (fcb ? 5.9f : Mathf.Max(3f, entry.loaMeters * 0.1f)) - entry.waterlineOffsetY,
                    fcb ? 9.4f : entry.loaMeters * 0.2f), entry.bowYawDeg);
                cameraRig.bowMount = Mount(Ego.transform, "Bow mount", new Vector3(0f,
                    (fcb ? 5.75f : Mathf.Max(2.5f, entry.loaMeters * 0.055f)) - entry.waterlineOffsetY,
                    fcb ? 14f : entry.loaMeters * 0.32f), entry.bowYawDeg);
                cameraRig.tacticalHeightM = Mathf.Max(160f, m_Applied.environmentSpacingM * 0.52f);
                cameraRig.SetView(m_Applied.onboardCamera ? CameraView.Bridge : CameraView.Chase);
                if (overlay != null) overlay.sourceCamera = cameraRig.controlledCamera;
            }
            return true;
        }

        void ConfigureSensors()
        {
            bool live = m_Applied.sensorMode == VisualSensorMode.YoloAndTruthRadar;
            if (publisher != null)
            {
                publisher.publishIntervalS = m_Applied.detectionIntervalS;
                publisher.confidenceThreshold = m_Applied.confidence;
                publisher.sourceCamera = cameraRig != null ? cameraRig.controlledCamera : Camera.main;
                if (Application.isPlaying) { if (live) publisher.StartPublishing(); else publisher.StopPublishing(); }
            }
            if (consumer != null && Application.isPlaying) { if (live) consumer.StartConsumer(); else consumer.StopConsumer(); }
            if (overlay != null) { overlay.enabled = true; overlay.visible = true; overlay.requireLive = live; overlay.ClearLiveResult(); }
        }

        void SetOriginalSceneVisibility(bool real)
        {
            foreach (var vessel in originalVessels)
            {
                if (vessel == null) continue;
                if (!m_OriginalActive.ContainsKey(vessel)) m_OriginalActive.Add(vessel, vessel.activeSelf);
                // Keep original geography/anchorage in real mode; replace only the scripted controllable demo vessels.
                vessel.SetActive(real && vessel.GetComponent<WaypointFollower>() == null && m_OriginalActive[vessel]);
            }
            foreach (var item in realTerrainAndDecor)
            {
                if (item == null) continue;
                if (!m_OriginalActive.ContainsKey(item)) m_OriginalActive.Add(item, item.activeSelf);
                item.SetActive(real && m_OriginalActive[item]);
            }
            if (tileStreaming != null) tileStreaming.enabled = real;
        }

        static Transform Mount(Transform ship, string name, Vector3 offsetMeters, float bowYaw)
        {
            var mount = ship.Find(name);
            if (mount == null) { mount = new GameObject(name).transform; mount.SetParent(ship, false); }
            var local = Quaternion.Euler(0f, -bowYaw, 0f) * offsetMeters;
            var scale = ship.lossyScale;
            mount.localPosition = new Vector3(local.x / scale.x, local.y / scale.y, local.z / scale.z);
            mount.localRotation = Quaternion.Euler(0f, -bowYaw, 0f);
            return mount;
        }

        public VisualTargetVessel GetVesselDefinition(int id)
        {
            if (m_Applied == null || id < 0 || id >= m_Actors.Count) return null;
            return m_Applied.TargetFor(id)?.Copy() ?? DefaultVessel(m_Applied, id);
        }

        static VisualTargetVessel DefaultVessel(VisualSimulationSettings settings, int id)
        {
            int slot = id % settings.agentsPerEnvironment;
            float extent = settings.environmentSpacingM * (settings.waypointMinFraction + settings.waypointMaxFraction) * 0.5f;
            float minimum = settings.environmentSpacingM * settings.waypointMinFraction;
            var definition = new VisualTargetVessel { id = id, vesselClass = settings.vesselClass,
                speedMps = settings.cruiseSpeedMps, motion = VisualTargetMotion.Waypoints };
            if (slot == 0)
            {
                definition.offsetMeters = new Vector2(0f, -Mathf.Min(100f, extent));
                definition.headingDeg = 0f;
                definition.waypoints = new[] { new Vector2(0f, extent), new Vector2(0f, -Mathf.Max(minimum, 100f)) };
            }
            else
            {
                int columns = Mathf.CeilToInt(Mathf.Sqrt(settings.agentsPerEnvironment - 1));
                int row = (slot - 1) / columns, column = (slot - 1) % columns;
                float x = columns == 1 ? -Mathf.Min(100f, extent) : Mathf.Lerp(-extent * 0.8f, extent * 0.8f, column / (float)(columns - 1));
                float z = Mathf.Min(150f, extent * 0.75f) + row * Mathf.Min(20f, extent * 0.04f);
                definition.offsetMeters = new Vector2(x, z);
                definition.headingDeg = 90f;
                definition.waypoints = new[] { new Vector2(extent, z), new Vector2(-extent, z) };
                if (settings.waypointPattern == VisualWaypointPattern.HeadOn)
                {
                    definition.offsetMeters = new Vector2((slot - 1) * 20f, extent);
                    definition.headingDeg = 180f;
                    definition.waypoints = new[] { new Vector2(definition.offsetMeters.x, -extent), definition.offsetMeters };
                }
                else if (settings.waypointPattern == VisualWaypointPattern.Crossing)
                {
                    definition.offsetMeters = new Vector2(-extent, extent * 0.5f + (slot - 1) * 15f);
                    definition.waypoints = new[] { new Vector2(extent, definition.offsetMeters.y), definition.offsetMeters };
                }
            }
            if (settings.waypointPattern == VisualWaypointPattern.Random)
            {
                var random = new System.Random(unchecked(settings.seed + id * 1031));
                definition.waypoints = new Vector2[4];
                for (int w = 0; w < definition.waypoints.Length; w++)
                {
                    float angle = (float)random.NextDouble() * Mathf.PI * 2f;
                    float radius = Mathf.Lerp(settings.waypointMinFraction, settings.waypointMaxFraction, (float)random.NextDouble()) * settings.environmentSpacingM;
                    definition.waypoints[w] = new Vector2(Mathf.Sin(angle), Mathf.Cos(angle)) * radius;
                }
                definition.offsetMeters = definition.waypoints[3];
                var direction = definition.waypoints[0] - definition.offsetMeters;
                definition.headingDeg = Mathf.Repeat(Mathf.Atan2(direction.x, direction.y) * Mathf.Rad2Deg, 360f);
            }
            if (settings.waypointPattern != VisualWaypointPattern.Random)
            {
                float maximum = settings.environmentSpacingM * settings.waypointMaxFraction;
                for (int i = 0; i < definition.waypoints.Length; i++)
                {
                    var point = definition.waypoints[i];
                    float radius = point.magnitude;
                    if (radius > 0f) definition.waypoints[i] = point * (Mathf.Clamp(radius, minimum, maximum) / radius);
                }
            }
            return definition;
        }

        public void SetManualControl(bool enabled)
        {
            ManualControl = enabled;
            m_Throttle = m_Rudder = 0f;
            Status = enabled ? "Manual kinematic helm: arrows accelerate/brake and turn." : "Local waypoint navigation selected.";
        }

        public void SetManualInput(float throttle, float rudder)
        {
            m_Throttle = float.IsNaN(throttle) || float.IsInfinity(throttle) ? 0f : Mathf.Clamp(throttle, -1f, 1f);
            m_Rudder = float.IsNaN(rudder) || float.IsInfinity(rudder) ? 0f : Mathf.Clamp(rudder, -1f, 1f);
        }

        public bool AddTarget(VisualTargetVessel target)
        {
            if (!CanEditTargets() || target == null) return false;
            var draft = m_Applied.Copy();
            int id = 0;
            while (id < m_Actors.Count && m_Actors[id] != null) id++;
            if (id >= 32) { Status = "The local scene already uses all 32 vessel slots."; return false; }
            if (id == m_Actors.Count) draft.agentsPerEnvironment++;
            var definition = target.Copy();
            definition.id = id;
            definition.enabled = true;
            ReplaceTarget(draft, definition);
            return Apply(draft);
        }

        public bool UpdateTarget(VisualTargetVessel target)
        {
            if (!CanEditTargets() || target == null || target.id < 0 || target.id >= m_Actors.Count || m_Actors[target.id] == null)
            { Status = "Select an active vessel to edit."; return false; }
            var draft = m_Applied.Copy();
            ReplaceTarget(draft, target.Copy());
            return Apply(draft);
        }

        public bool RemoveTarget(int id)
        {
            if (!CanEditTargets()) return false;
            if (id < 0 || id >= m_Actors.Count || m_Actors[id] == null || id == m_Applied.egoId)
            { Status = "Select an active target; choose another ego before removing the current ego."; return false; }
            var draft = m_Applied.Copy();
            var definition = draft.TargetFor(id)?.Copy() ?? new VisualTargetVessel { id = id, vesselClass = draft.vesselClass };
            definition.enabled = false;
            ReplaceTarget(draft, definition);
            return Apply(draft);
        }

        bool CanEditTargets()
        {
            if (IsRunning) { Status = "Pause before editing vessels."; return false; }
            if (m_Applied == null) { Status = "Apply a scene first."; return false; }
            if (m_Applied.environmentCount != 1)
            { Status = "Use a single environment for individual vessel editing; use setup counts for a grid."; return false; }
            return true;
        }

        static void ReplaceTarget(VisualSimulationSettings draft, VisualTargetVessel definition)
        {
            var targets = new List<VisualTargetVessel>(draft.targets ?? Array.Empty<VisualTargetVessel>());
            int index = targets.FindIndex(target => target.id == definition.id);
            if (index < 0) targets.Add(definition); else targets[index] = definition;
            draft.targets = targets.ToArray();
        }

        public string ExportSceneJson()
        {
            if (m_Applied == null) { Status = "Apply a scene before saving its definition."; return null; }
            return JsonUtility.ToJson(new VisualSceneDocument {
                schema_version = SceneSchema, coordinate_system = Coordinates,
                origin_world_m = sceneOrigin, settings = m_Applied.Copy()
            }, true);
        }

        public bool ImportSceneJson(string json)
        {
            if (IsRunning) { Status = "Pause the current run before loading another scene."; return false; }
            VisualSceneDocument document;
            try { document = JsonUtility.FromJson<VisualSceneDocument>(json); }
            catch (Exception error) { Status = "Invalid scene JSON: " + error.Message; return false; }
            if (document == null || document.schema_version != SceneSchema || document.coordinate_system != Coordinates || document.settings == null)
            { Status = "Unsupported or incomplete local scene definition."; return false; }
            var origin = document.origin_world_m;
            if (float.IsNaN(origin.x) || float.IsInfinity(origin.x) || float.IsNaN(origin.y) || float.IsInfinity(origin.y) ||
                float.IsNaN(origin.z) || float.IsInfinity(origin.z))
            { Status = "Scene origin must use finite metre coordinates."; return false; }
            var previousOrigin = sceneOrigin;
            sceneOrigin = origin;
            if (Apply(document.settings)) return true;
            sceneOrigin = previousOrigin;
            return false;
        }

        static void DestroyOwned(UnityEngine.Object value)
        {
            if (Application.isPlaying) Destroy(value); else DestroyImmediate(value);
        }

        void ReleaseIslandMeshes()
        {
            foreach (var island in m_Islands)
                if (island != null) DestroyOwned(island.GetComponent<MeshFilter>().sharedMesh);
        }

        void OnDestroy()
        {
            ReleaseIslandMeshes();
            if (m_IslandMaterial != null) DestroyOwned(m_IslandMaterial);
            foreach (var pair in m_OriginalActive) if (pair.Key != null) pair.Key.SetActive(pair.Value);
        }
    }
}
