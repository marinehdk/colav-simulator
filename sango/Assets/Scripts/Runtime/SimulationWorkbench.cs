using System;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;
using static Sango.UiBuildHelpers;

namespace Sango
{
    /// <summary>Operator setup and scene-authoring UI over the public local visual-run boundary.</summary>
    public class SimulationWorkbench : MonoBehaviour
    {
        public VisualSimulationSession session;
        public SimulationPanel preview;
        public WeatherGUI legacyWeather;
        public AutonomousControlPanel legacyControl;
        VisualSimulationSettings m_Draft = new VisualSimulationSettings();
        VisualTargetVessel m_Target = new VisualTargetVessel();
        Canvas m_Canvas;
        RectTransform m_Setup, m_TargetEditor, m_Hud, m_Weather;
        Text m_Status, m_RunStatus, m_TargetStatus;
        RawImage m_Preview;
        Font m_Font;
        string m_SceneName = "local-scene";
        string m_RouteText = "";
        bool m_ShowSettings = true;
        int m_RosterPage;
        bool m_TargetInitialized;
        GUIStyle m_NavigationLabel;

        public bool SettingsVisible => m_ShowSettings;
        public VisualSimulationSettings Draft => m_Draft.Copy();

        void Start()
        {
            if (session == null) session = GetComponent<VisualSimulationSession>();
            m_Font = LoadBuiltinFont();
            EnsureEventSystem();
            var root = new GameObject("WorkbenchCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            root.transform.SetParent(transform, false);
            m_Canvas = root.GetComponent<Canvas>();
            m_Canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            m_Canvas.sortingOrder = 150;
            var scaler = root.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            BuildHud();
            BuildWeather();
            BuildSetup();
            HideLegacyPanels();
            SetRadarVisible(false);
        }

        void HideLegacyPanels()
        {
            if (legacyWeather != null) foreach (var canvas in legacyWeather.GetComponentsInChildren<Canvas>(true)) canvas.gameObject.SetActive(false);
            if (preview != null) foreach (var canvas in preview.GetComponentsInChildren<Canvas>(true)) canvas.gameObject.SetActive(false);
            if (legacyControl != null) legacyControl.gameObject.SetActive(false);
        }

        RectTransform Panel(string name, float width, float height)
        {
            var rect = NewRect(name, m_Canvas.transform);
            rect.anchorMin = rect.anchorMax = rect.pivot = new Vector2(0.5f, 0.5f);
            rect.sizeDelta = new Vector2(width, height);
            rect.gameObject.AddComponent<Image>().color = new Color(0.015f, 0.03f, 0.045f, 0.92f);
            return rect;
        }

        void BuildSetup()
        {
            if (m_Setup != null) { m_Setup.gameObject.SetActive(false); Destroy(m_Setup.gameObject); }
            m_Setup = Panel("Simulation Setup", 1500f, 900f);
            Label(m_Setup, "SIMULATION  /  LOCAL SCENE SETUP", 28, 26, 18, 1000, 42, Color.white);
            Button(m_Setup, "Back to view", 1250, 20, 220, () => ShowSettings(false));
            var left = new Column(this, m_Setup, 26, 78, 455);
            left.Heading("ENVIRONMENT & WAYPOINTS");
            left.Choice("Scene", new[] { "Real Strait", "Procedural experiment" }, (int)m_Draft.sceneMode,
                i => { m_Draft.sceneMode = (VisualSceneMode)i; BuildSetup(); });
            left.Number("Environments (1..16)", m_Draft.environmentCount, v => m_Draft.environmentCount = Mathf.RoundToInt(v), m_Draft.sceneMode == VisualSceneMode.Procedural);
            left.Number("Generated slots / environment", m_Draft.agentsPerEnvironment, v => m_Draft.agentsPerEnvironment = Mathf.RoundToInt(v));
            left.Number("Spacing [m]", m_Draft.environmentSpacingM, v => m_Draft.environmentSpacingM = v);
            left.Check("Travel enclosures", m_Draft.enclosures, v => m_Draft.enclosures = v);
            left.Number("Current drift [m/s]", m_Draft.currentSpeedMps, v => m_Draft.currentSpeedMps = v);
            left.Number("Current direction [deg]", m_Draft.currentDirectionDeg, v => m_Draft.currentDirectionDeg = v);
            left.Choice("Spectrum (HDRP approximation)", new[] { "PM-like", "JONSWAP-like", "TMA-like" }, m_Draft.spectrumApproximation, i => m_Draft.spectrumApproximation = i);
            left.Heading("WAYPOINTS");
            left.Number("Arrival distance [m]", m_Draft.arrivalDistanceM, v => m_Draft.arrivalDistanceM = v);
            left.Check("Show waypoint markers", m_Draft.showWaypoints, v => m_Draft.showWaypoints = v);
            left.Number("Minimum spawn / spacing", m_Draft.waypointMinFraction, v => m_Draft.waypointMinFraction = v);
            left.Number("Maximum spawn / spacing", m_Draft.waypointMaxFraction, v => m_Draft.waypointMaxFraction = v);
            left.Choice("Route pattern", Enum.GetNames(typeof(VisualWaypointPattern)), (int)m_Draft.waypointPattern, i => m_Draft.waypointPattern = (VisualWaypointPattern)i);
            left.Number("Seed", m_Draft.seed, v => m_Draft.seed = Mathf.RoundToInt(v));

            var middle = new Column(this, m_Setup, 523, 78, 455);
            middle.Heading("PROCEDURAL ISLANDS");
            bool procedural = m_Draft.sceneMode == VisualSceneMode.Procedural;
            middle.Check("Generate island / environment", m_Draft.generateIslands, v => m_Draft.generateIslands = v, procedural);
            middle.Number("Noise scale [m]", m_Draft.islandScaleM, v => m_Draft.islandScaleM = v, procedural);
            middle.Number("Height multiplier [m]", m_Draft.islandHeightM, v => m_Draft.islandHeightM = v, procedural);
            middle.Number("Edge depth [m]", m_Draft.islandFalloffM, v => m_Draft.islandFalloffM = v, procedural);
            middle.Number("Octaves", m_Draft.islandOctaves, v => m_Draft.islandOctaves = Mathf.RoundToInt(v), procedural);
            middle.Number("Smooth A", m_Draft.islandSmoothA, v => m_Draft.islandSmoothA = v, procedural);
            middle.Number("Smooth B", m_Draft.islandSmoothB, v => m_Draft.islandSmoothB = v, procedural);
            middle.Number("Persistence", m_Draft.islandPersistence, v => m_Draft.islandPersistence = v, procedural);
            middle.Number("Lacunarity", m_Draft.islandLacunarity, v => m_Draft.islandLacunarity = v, procedural);
            middle.Number("Offset X", m_Draft.islandOffsetX, v => m_Draft.islandOffsetX = v, procedural);
            middle.Number("Offset Y", m_Draft.islandOffsetY, v => m_Draft.islandOffsetY = v, procedural);
            middle.Heading("DESIGNATED EGO & SENSORS");
            middle.Number("Ego ID", m_Draft.egoId, v => m_Draft.egoId = Mathf.RoundToInt(v));
            middle.Check("Onboard camera", m_Draft.onboardCamera, v => m_Draft.onboardCamera = v);
            middle.Choice("Sensors", new[] { "Ground truth awareness", "YOLO + truth radar (no fusion)" }, (int)m_Draft.sensorMode, i => m_Draft.sensorMode = (VisualSensorMode)i);
            middle.Number("Detection interval [s]", m_Draft.detectionIntervalS, v => m_Draft.detectionIntervalS = v);
            middle.Number("Confidence threshold", m_Draft.confidence, v => m_Draft.confidence = v);
            middle.Number("Truth-assisted camera range [m]", m_Draft.observationDistanceM, v => m_Draft.observationDistanceM = v);
            middle.Check("Truth-assisted target camera lock", m_Draft.truthAssistedCameraLock, v => m_Draft.truthAssistedCameraLock = v);
            middle.Number("Radar range [m]", m_Draft.radarRangeM, v => m_Draft.radarRangeM = v);
            middle.Number("Radar sweep [RPM]", m_Draft.radarRpm, v => m_Draft.radarRpm = v);

            var right = new Column(this, m_Setup, 1020, 78, 455);
            right.Heading("VESSEL SELECTION");
            var entries = session.catalog.entries.Where(e => e != null && e.prefab != null).ToArray();
            var names = entries.Select(e => $"{e.vesselClass}  /  {e.loaMeters:0}m").ToArray();
            right.Choice("Default vessel", names, Mathf.Max(0, Array.FindIndex(entries, e => e.vesselClass == m_Draft.vesselClass)),
                i => { m_Draft.vesselClass = entries[i].vesselClass; if (preview != null) preview.SelectClass(m_Draft.vesselClass); });
            var image = Rect(m_Setup, "Vessel preview", 1020, right.Y, 455, 125);
            m_Preview = image.gameObject.AddComponent<RawImage>();
            m_Preview.color = Color.white;
            m_Preview.raycastTarget = false;
            m_Preview.uvRect = new Rect(0f, 0f, 1f, 1f);
            right.Y += 140;
            if (preview != null) { preview.SelectClass(m_Draft.vesselClass); preview.SetPreviewActive(true); }
            right.Note("Uses existing licensed catalog models. Selection changes the actual run on Apply.", 52);
            right.Number("Default cruise [m/s]", m_Draft.cruiseSpeedMps, v => m_Draft.cruiseSpeedMps = v);
            right.Action("Apply scene", () => ApplyDraft());
            right.Action("Apply & start local waypoint navigation", () => { if (!ApplyDraft()) return; session.StartRun(); ShowSettings(false); });
            right.Action("Edit / add target vessels", OpenTargets);
            right.Action("Pause / resume", ToggleRun);
            right.Action("Reset applied scene", session.ResetRun);
            right.String("Scene name", m_SceneName, v => m_SceneName = v);
            right.Action("Save scene definition", SaveScene);
            right.Action("Load scene definition", LoadScene);
            right.Action("New setup draft", () => { m_Draft = new VisualSimulationSettings(); BuildSetup(); });
            right.Note("Local waypoint demo. No collision-avoidance policy or radar fusion.", 40);
            m_Status = Label(m_Setup, "", 16, 26, 846, 1440, 44, new Color(0.4f, 1f, 0.62f));
            m_Setup.gameObject.SetActive(m_ShowSettings);
        }

        public bool ApplyDraft()
        {
            foreach (var input in m_Setup.GetComponentsInChildren<InputField>(true))
                if (input.characterValidation == InputField.CharacterValidation.Decimal &&
                    !float.TryParse(input.text, NumberStyles.Float, CultureInfo.InvariantCulture, out _))
                { m_FileStatus = "Enter a valid number in " + input.name; return false; }
            bool applied = session.Apply(m_Draft);
            if (applied) { m_Draft = session.AppliedSettings; m_TargetInitialized = false; BuildSetup(); }
            return applied;
        }

        public void ShowSettings(bool visible)
        {
            m_ShowSettings = visible;
            if (m_Setup != null) m_Setup.gameObject.SetActive(visible);
            if (m_TargetEditor != null) m_TargetEditor.gameObject.SetActive(false);
            if (preview != null) preview.SetPreviewActive(visible);
            SetRadarVisible(!visible);
        }

        void SetRadarVisible(bool visible)
        {
            if (session.overlay != null) session.overlay.suppressDisplay = !visible;
            if (session.radar != null) foreach (var canvas in session.radar.GetComponentsInChildren<Canvas>(true)) canvas.gameObject.SetActive(visible);
        }

        void ToggleRun() { if (session.IsRunning) session.PauseRun(); else session.StartRun(); }

        void BuildHud()
        {
            m_Hud = NewRect("Run HUD", m_Canvas.transform);
            m_Hud.anchorMin = Vector2.zero; m_Hud.anchorMax = Vector2.one;
            m_Hud.offsetMin = m_Hud.offsetMax = Vector2.zero;
            Button(m_Hud, "Simulation setup", 20, 20, 190, () => { m_Draft = session.AppliedSettings ?? m_Draft; BuildSetup(); ShowSettings(true); });
            Button(m_Hud, "Start / pause", 230, 20, 160, ToggleRun);
            Button(m_Hud, "Manual / waypoint", 410, 20, 210, () => session.SetManualControl(!session.ManualControl));
            Button(m_Hud, "Camera", 640, 20, 110, () => session.cameraRig.CycleView());
            Button(m_Hud, "Targets", 770, 20, 110, OpenTargets);
            Button(m_Hud, "Weather", 900, 20, 120, () => m_Weather.gameObject.SetActive(!m_Weather.gameObject.activeSelf));
            Button(m_Hud, "Detection", 1040, 20, 130, () => { if (session.overlay != null) session.overlay.visible = !session.overlay.visible; });
            m_RunStatus = Label(m_Hud, "", 16, 20, 64, 1100, 42, Color.white);
        }

        void BuildWeather()
        {
            if (session.weather == null) return;
            var weather = session.weather;
            m_Weather = Rect(m_Hud, "Runtime weather controls", 20, 115, 730, 535);
            m_Weather.gameObject.AddComponent<Image>().color = new Color(0.015f, 0.03f, 0.045f, 0.9f);
            var left = new Column(this, m_Weather, 14, 14, 340);
            left.Heading("WEATHER / LIGHTING");
            left.Number("Time [0..24 h]", weather.timeOfDayHours, v => { weather.timeOfDayHours = Mathf.Clamp(v, 0, 24); weather.Apply(); });
            left.Number("Beaufort [0..11]", weather.beaufort, v => weather.BeginUserGradeTransition(Mathf.Clamp(v, 0, 11)));
            left.Number("Cloud cover [0..1]", weather.cloudCover, v => { weather.cloudCover = Mathf.Clamp01(v); weather.Apply(); });
            left.Number("Fog visibility [100..8000 m]", weather.fogDistanceMeters, v => weather.BeginUserGradeTransition(targetFogMeters: Mathf.Clamp(v, 100, 8000)));
            left.Number("Wind direction [deg]", weather.windDirectionDeg, v => { weather.windDirectionDeg = Mathf.Repeat(v, 360); weather.Apply(); });
            left.Number("Wave direction [deg]", weather.waveDirectionDeg < 0 ? weather.windDirectionDeg : weather.waveDirectionDeg, v => { weather.waveDirectionDeg = Mathf.Repeat(v, 360); weather.Apply(); });
            left.Number("Wave development [0..1]", weather.waveDevelopment, v => { weather.waveDevelopment = Mathf.Clamp01(v); weather.Apply(); });
            left.Number("Wave alignment [0..1]", weather.waveAlignment, v => { weather.waveAlignment = Mathf.Clamp01(v); weather.Apply(); });
            left.Note("HDRP spectral appearance controls; visual approximation, not a certified PM/JONSWAP/TMA model.", 70);
            var right = new Column(this, m_Weather, 382, 14, 330);
            right.Heading("PRECIPITATION / VIEW");
            right.Check("Independent rain", weather.rainEnabled, v => { weather.precipitationOverride = true; weather.rainEnabled = v; weather.Apply(); });
            right.Check("Snow (visual)", weather.snowEnabled, v => { weather.snowEnabled = v; weather.Apply(); });
            right.Check("Thunder / lightning (visual)", weather.thunderEnabled, v => { weather.thunderEnabled = v; weather.Apply(); });
            right.Check("Wet lens (visual approximation)", weather.wetLensEnabled, v => { weather.wetLensEnabled = v; weather.Apply(); });
            right.Number("Precipitation intensity [0..1]", weather.precipitationIntensity, v => { weather.precipitationIntensity = Mathf.Clamp01(v); weather.Apply(); });
            right.Choice("Atmosphere preset", new[] { "Hazy clear", "Cumulonimbus", "Thunderstorm" }, (int)weather.atmosphereTier,
                i => { weather.precipitationOverride = false; weather.atmosphereTier = (M7BMath.AtmosphereTier)i; weather.ApplyAtmosphereTier(); });
            right.Choice("Quality", new[] { "High", "Low" }, M8Quality.DropdownIndex, i => M8Quality.SetTierFromDropdownIndex(i));
            right.Note("0..9 sea · T daylight · F fog · N atmosphere · L quality. Arrow keys operate the ego in manual mode.", 66);
            right.Action("Close weather controls", () => m_Weather.gameObject.SetActive(false));
            m_Weather.gameObject.SetActive(false);
        }

        void OpenTargets()
        {
            if (session.AppliedSettings == null) { ApplyDraft(); if (session.AppliedSettings == null) return; }
            session.PauseRun();
            if (!m_TargetInitialized)
            {
                int id = Enumerable.Range(0, session.Actors.Count).FirstOrDefault(i => session.Actors[i] != null && session.Actors[i] != session.Ego);
                m_Target = session.GetVesselDefinition(id);
                m_RouteText = RouteText(m_Target.waypoints);
                m_TargetInitialized = true;
            }
            ShowSettings(false);
            if (m_TargetEditor != null) { m_TargetEditor.gameObject.SetActive(false); Destroy(m_TargetEditor.gameObject); }
            m_TargetEditor = Panel("Target vessels", 1300, 790);
            SetRadarVisible(false);
            Label(m_TargetEditor, "SCENE VESSELS  /  TYPE, POSE & MOTION", 26, 25, 18, 1030, 38, Color.white);
            Button(m_TargetEditor, "Back", 1110, 18, 160, () => { m_TargetEditor.gameObject.SetActive(false); ShowSettings(true); });
            var list = new Column(this, m_TargetEditor, 25, 85, 350);
            list.Heading("STABLE LOCAL IDs");
            int pages = Mathf.Max(1, Mathf.CeilToInt(session.Actors.Count / 10f));
            m_RosterPage = Mathf.Clamp(m_RosterPage, 0, pages - 1);
            for (int id = m_RosterPage * 10; id < Mathf.Min(session.Actors.Count, (m_RosterPage + 1) * 10); id++)
            {
                if (session.Actors[id] == null) continue;
                int selected = id;
                var definition = session.GetVesselDefinition(id);
                list.Action($"{id}  {definition.vesselClass}" + (session.Ego == session.Actors[id] ? "  [EGO]" : ""),
                    () => { m_Target = session.GetVesselDefinition(selected); m_RouteText = RouteText(m_Target.waypoints); OpenTargets(); });
            }
            list.Note($"Page {m_RosterPage + 1}/{pages}", 24);
            list.Action("Previous IDs", () => { m_RosterPage = Mathf.Max(0, m_RosterPage - 1); OpenTargets(); });
            list.Action("Next IDs", () => { m_RosterPage = Mathf.Min(pages - 1, m_RosterPage + 1); OpenTargets(); });
            var form = new Column(this, m_TargetEditor, 420, 85, 405);
            form.Heading($"VESSEL {m_Target.id}");
            var classes = session.catalog.entries.Where(e => e != null && e.prefab != null).Select(e => e.vesselClass).ToArray();
            form.Choice("Vessel type", classes.Select(c => c.ToString()).ToArray(), Mathf.Max(0, Array.IndexOf(classes, m_Target.vesselClass)), i => m_Target.vesselClass = classes[i]);
            form.Number("Initial east offset [m]", m_Target.offsetMeters.x, v => m_Target.offsetMeters.x = v);
            form.Number("Initial north offset [m]", m_Target.offsetMeters.y, v => m_Target.offsetMeters.y = v);
            form.Number("Initial heading [deg]", m_Target.headingDeg, v => m_Target.headingDeg = v);
            form.Number("Speed [m/s]", m_Target.speedMps, v => m_Target.speedMps = v);
            form.Choice("Motion", Enum.GetNames(typeof(VisualTargetMotion)), (int)m_Target.motion, i => m_Target.motion = (VisualTargetMotion)i);
            form.Check("Loop waypoint route", m_Target.loop, v => m_Target.loop = v);
            form.String("Waypoints: E,N; E,N ...", m_RouteText, v => m_RouteText = v);
            form.Note("Offsets and waypoints are local metres relative to the environment centre. Empty waypoint list uses the selected preset.", 70);
            var commands = new Column(this, m_TargetEditor, 875, 85, 390);
            commands.Heading("APPLY WHILE PAUSED");
            commands.Action("Update selected vessel", () => { if (ParseRoute()) { session.UpdateTarget(m_Target); RefreshTargets(); } });
            commands.Action("Add target with these settings", () => { if (ParseRoute()) { session.AddTarget(m_Target); RefreshTargets(); } });
            commands.Action("Remove selected target", () => { session.RemoveTarget(m_Target.id); RefreshTargets(); });
            commands.Action("Designate selected vessel EGO", () => { session.SetEgo(m_Target.id); RefreshTargets(); });
            commands.Note("Single-environment scenes support individual add/remove. A grid uses setup counts. Removing a target preserves other IDs.", 90);
            m_TargetStatus = Label(m_TargetEditor, "", 16, 420, 660, 840, 75, Color.white);
        }

        void RefreshTargets() { m_Draft = session.AppliedSettings; OpenTargets(); }
        bool ParseRoute()
        {
            foreach (var input in m_TargetEditor.GetComponentsInChildren<InputField>(true))
                if (input.characterValidation == InputField.CharacterValidation.Decimal &&
                    !float.TryParse(input.text, NumberStyles.Float, CultureInfo.InvariantCulture, out _))
                { m_FileStatus = "Enter a valid number in " + input.name; return false; }
            try
            {
                m_Target.waypoints = string.IsNullOrWhiteSpace(m_RouteText) ? Array.Empty<Vector2>() : m_RouteText.Split(';').Select(p => {
                    var xy = p.Split(','); if (xy.Length != 2) throw new FormatException("Each waypoint needs east,north.");
                    return new Vector2(float.Parse(xy[0], CultureInfo.InvariantCulture), float.Parse(xy[1], CultureInfo.InvariantCulture));
                }).ToArray();
                return true;
            }
            catch (Exception error) when (error is FormatException || error is OverflowException)
            { m_FileStatus = "Route format: finite east,north;east,north (metres)."; return false; }
        }
        static string RouteText(Vector2[] route) => route == null ? "" : string.Join(";", route.Select(p => p.x.ToString("0.##", CultureInfo.InvariantCulture) + "," + p.y.ToString("0.##", CultureInfo.InvariantCulture)));

        string m_FileStatus = "";
        public string SceneFolder => Path.Combine(Application.persistentDataPath, "scenes");
        string ScenePath()
        {
            if (string.IsNullOrWhiteSpace(m_SceneName) || m_SceneName.Any(c => !char.IsLetterOrDigit(c) && c != '-' && c != '_'))
                throw new ArgumentException("Scene name uses letters, digits, '-' or '_'.");
            return Path.Combine(SceneFolder, m_SceneName + ".json");
        }
        void SaveScene()
        {
            try { var json = session.ExportSceneJson(); if (json == null) return; Directory.CreateDirectory(SceneFolder); File.WriteAllText(ScenePath(), json); m_FileStatus = "Saved " + ScenePath(); }
            catch (Exception error) { m_FileStatus = error.Message; }
        }
        void LoadScene()
        {
            try { if (session.ImportSceneJson(File.ReadAllText(ScenePath()))) { m_Draft = session.AppliedSettings; m_TargetInitialized = false; BuildSetup(); } m_FileStatus = "Load: " + session.Status; }
            catch (Exception error) { m_FileStatus = error.Message; }
        }

        void Update()
        {
            if (m_Status != null) m_Status.text = session.Status + (string.IsNullOrEmpty(m_FileStatus) ? "" : "\n" + m_FileStatus);
            if (m_TargetStatus != null) m_TargetStatus.text = session.Status + "\n" + m_FileStatus;
            if (m_Preview != null && preview != null) m_Preview.texture = preview.PreviewTexture;
            if (m_RunStatus != null)
                m_RunStatus.text = $"{(session.IsRunning ? "RUNNING" : "PAUSED")}  /  {(session.ManualControl ? "Manual helm" : "Local waypoints")}  /  {session.ActorCount} vessels  /  speed {(session.Ego != null ? session.Ego.SpeedMps : 0f):0.0} m/s\n{session.Status}";
            if (!m_ShowSettings && (m_TargetEditor == null || !m_TargetEditor.gameObject.activeSelf))
            {
                if (Input.GetKeyDown(KeyCode.G)) ToggleRun();
                if (session.ManualControl) session.SetManualInput(Input.GetAxisRaw("Vertical"), Input.GetAxisRaw("Horizontal"));
            }
        }

        void OnGUI()
        {
            if (m_ShowSettings || (m_TargetEditor != null && m_TargetEditor.gameObject.activeSelf) || session == null || session.Ego == null) return;
            var settings = session.AppliedSettings;
            if (settings == null || !settings.showWaypoints) return;
            if (m_NavigationLabel == null) m_NavigationLabel = new GUIStyle(GUI.skin.label) { fontSize = 17, fontStyle = FontStyle.Bold };
            var ego = session.Ego;
            float heading = Mathf.Repeat(ego.transform.eulerAngles.y - ego.bowYawDegOffset, 360f);
            var previous = GUI.color;
            GUI.color = new Color(0.25f, 0.6f, 1f);
            GUI.Label(new Rect(Screen.width * 0.42f, 110f, 350f, 28f), $"Velocity  ↑  {ego.SpeedMps:0.0} m/s / {heading:0}°", m_NavigationLabel);
            if (ego.waypoints != null && ego.waypoints.Length > 0 && session.cameraRig != null)
            {
                var target = ego.waypoints[Mathf.Clamp(ego.ActiveWaypointIndex, 0, ego.waypoints.Length - 1)];
                var point = new Vector3(target.x, 0.1f, target.y);
                var offset = point - ego.transform.position;
                float relative = Mathf.DeltaAngle(heading, Mathf.Atan2(offset.x, offset.z) * Mathf.Rad2Deg);
                GUI.color = new Color(0.2f, 1f, 0.3f);
                GUI.Label(new Rect(Screen.width * 0.58f, 110f, 350f, 28f), $"Waypoint  {(relative < -5 ? "←" : relative > 5 ? "→" : "↑")}  {offset.magnitude:0} m", m_NavigationLabel);
                var camera = session.cameraRig.controlledCamera;
                if (camera != null)
                {
                    var screen = camera.WorldToScreenPoint(point);
                    if (screen.z > 0 && screen.x >= 0 && screen.x <= Screen.width && screen.y >= 0 && screen.y <= Screen.height)
                        GUI.Label(new Rect(screen.x - 50, Screen.height - screen.y - 25, 160, 28), "WP " + (ego.ActiveWaypointIndex + 1), m_NavigationLabel);
                }
            }
            GUI.color = previous;
        }

        RectTransform Rect(Transform parent, string name, float x, float y, float width, float height)
        {
            var rect = NewRect(name, parent);
            rect.anchorMin = rect.anchorMax = rect.pivot = new Vector2(0, 1);
            rect.anchoredPosition = new Vector2(x, -y); rect.sizeDelta = new Vector2(width, height);
            return rect;
        }
        Text Label(Transform parent, string content, int size, float x, float y, float width, float height, Color color)
        {
            var text = Rect(parent, content, x, y, width, height).gameObject.AddComponent<Text>();
            text.font = m_Font; text.text = content; text.fontSize = size; text.color = color; text.raycastTarget = false;
            text.alignment = TextAnchor.MiddleLeft; return text;
        }
        void Button(Transform parent, string label, float x, float y, float width, UnityEngine.Events.UnityAction action)
        {
            var rect = Rect(parent, label, x, y, width, 32);
            var image = rect.gameObject.AddComponent<Image>(); image.color = new Color(0.08f, 0.2f, 0.21f, 0.96f);
            var button = rect.gameObject.AddComponent<Button>(); button.targetGraphic = image; button.onClick.AddListener(action);
            Label(rect, label, 16, 10, 0, width - 20, 32, Color.white);
        }

        sealed class Column
        {
            readonly SimulationWorkbench view;
            readonly Transform parent;
            readonly float x, width;
            public float Y;
            public Column(SimulationWorkbench view, Transform parent, float x, float y, float width) { this.view = view; this.parent = parent; this.x = x; this.width = width; Y = y; }
            public void Heading(string text) { view.Label(parent, text, 18, x, Y, width, 28, Color.white); Y += 32; }
            public void Note(string text, float height) { view.Label(parent, text, 14, x, Y, width, height, new Color(0.6f, 0.75f, 0.8f)); Y += height + 8; }
            public void Action(string text, UnityEngine.Events.UnityAction callback) { view.Button(parent, text, x, Y, width, callback); Y += 40; }
            public void Number(string label, float value, Action<float> changed, bool enabled = true)
            {
                var field = String(label, value.ToString("0.###", CultureInfo.InvariantCulture), text => { if (float.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out var v)) changed(v); }, enabled);
                field.characterValidation = InputField.CharacterValidation.Decimal;
            }
            public InputField String(string label, string value, Action<string> changed, bool enabled = true)
            {
                view.Label(parent, label, 15, x, Y, width * 0.62f, 30, enabled ? new Color(0.8f, 0.88f, 0.9f) : Color.gray);
                var rect = view.Rect(parent, label + " input", x + width * 0.63f, Y, width * 0.37f, 28);
                var image = rect.gameObject.AddComponent<Image>(); image.color = new Color(0.02f, 0.08f, 0.1f, 1f);
                var field = rect.gameObject.AddComponent<InputField>(); field.targetGraphic = image; field.interactable = enabled;
                var text = view.Label(rect, value ?? "", 16, 7, 0, width * 0.37f - 14, 28, new Color(0.2f, 1f, 0.45f));
                field.textComponent = text; field.text = value ?? ""; field.onEndEdit.AddListener(v => changed(v)); Y += 33;
                return field;
            }
            public void Check(string label, bool value, Action<bool> changed, bool enabled = true)
            {
                view.Label(parent, label, 15, x, Y, width - 50, 30, enabled ? new Color(0.8f, 0.88f, 0.9f) : Color.gray);
                var rect = view.Rect(parent, label + " toggle", x + width - 35, Y + 3, 24, 24);
                var image = rect.gameObject.AddComponent<Image>(); image.color = new Color(0.1f, 0.2f, 0.2f);
                var mark = NewImage("Check", rect, new Color(0.1f, 1f, 0.25f)); Stretch(mark.rectTransform, 4, 4, -4, -4);
                var toggle = rect.gameObject.AddComponent<Toggle>(); toggle.targetGraphic = image; toggle.graphic = mark;
                toggle.isOn = value; toggle.interactable = enabled; toggle.onValueChanged.AddListener(v => changed(v)); Y += 33;
            }
            public void Choice(string label, string[] options, int value, Action<int> changed)
            {
                view.Label(parent, label, 15, x, Y, width, 24, new Color(0.8f, 0.88f, 0.9f)); Y += 25;
                var rect = view.Rect(parent, label + " dropdown", x, Y, width, 28);
                var bg = rect.gameObject.AddComponent<Image>(); bg.color = new Color(0.02f, 0.08f, 0.1f);
                var caption = view.Label(rect, "", 15, 8, 0, width - 16, 28, new Color(0.2f, 1f, 0.45f));
                var template = NewRect("Template", rect); template.anchorMin = new Vector2(0, 0); template.anchorMax = new Vector2(1, 0);
                template.pivot = new Vector2(0.5f, 1); template.sizeDelta = new Vector2(0, Mathf.Min(250, options.Length * 30 + 8));
                template.gameObject.AddComponent<Image>().color = new Color(0.02f, 0.07f, 0.1f, 0.98f);
                var viewport = NewRect("Viewport", template); Stretch(viewport, 4, 4, -4, -4); viewport.gameObject.AddComponent<RectMask2D>();
                var content = NewRect("Content", viewport); content.anchorMin = new Vector2(0, 1); content.anchorMax = Vector2.one;
                content.pivot = new Vector2(0.5f, 1); content.sizeDelta = new Vector2(0, options.Length * 30);
                var item = view.Rect(content, "Item", 0, 0, width - 8, 30);
                var itemBg = item.gameObject.AddComponent<Image>(); itemBg.color = new Color(0.1f, 0.3f, 0.27f);
                var itemToggle = item.gameObject.AddComponent<Toggle>(); itemToggle.targetGraphic = itemBg;
                var itemLabel = view.Label(item, "", 15, 8, 0, width - 24, 30, Color.white);
                var scroll = template.gameObject.AddComponent<ScrollRect>(); scroll.content = content; scroll.viewport = viewport; scroll.horizontal = false;
                var dropdown = rect.gameObject.AddComponent<Dropdown>(); dropdown.targetGraphic = bg; dropdown.captionText = caption;
                dropdown.itemText = itemLabel; dropdown.template = template;
                dropdown.options = options.Select(o => new Dropdown.OptionData(o)).ToList(); dropdown.value = Mathf.Clamp(value, 0, options.Length - 1);
                dropdown.RefreshShownValue(); dropdown.onValueChanged.AddListener(i => changed(i)); template.gameObject.SetActive(false); Y += 34;
            }
        }

    }
}
