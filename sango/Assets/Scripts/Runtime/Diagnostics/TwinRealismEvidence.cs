using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>Opt-in rendered fixture. Never connects to or changes an Active Session.</summary>
    public sealed class TwinRealismEvidence : MonoBehaviour
    {
        [Serializable] public class Shot
        {
            public string name;
            public float seconds, fps, heave, pitch, foamPeak;
            public int width, height, wakeSamples, skyType;
            public string landscape;
            public int terrainMeshes, buildingMeshes;
        }
        [Serializable] public class Report
        {
            public string purpose = "Visual fixture only; no navigation or hydrodynamic acceptance";
            public List<Shot> shots = new List<Shot>();
        }
        string m_Output;
        TwinSessionDriver m_Driver;
        CameraRig m_Rig;
        WeatherController m_Weather;
        Vector3 m_Position;
        float m_Heading, m_Time, m_LastCapture;
        int m_Sequence, m_Frames, m_Shot;
        bool m_CoastOnly, m_BowOnly;
        readonly Report m_Report = new Report();
        float[] m_Times = { 2, 24, 36, 44, 49, 76, 106, 140 };
        string[] m_Names = { "idle", "straight-wake", "turn-wake", "bow-wave", "stopped-residual", "stopped-decayed", "coast-medium", "coast-near" };
        readonly TwinEnvironment m_Environment = new TwinEnvironment {
            enabled = true, wind_speed_mps = 11, wave_hs_m = 2.5f, wave_period_s = 5.5f,
            time_of_day_hours = 17.5f, cloud_cover = 0.1f, fog_distance_m = 8000,
            wave_development = 0.5f, wave_alignment = 0.7f, quality = "high",
            spectrum_style = "jonswap", atmosphere = "hazy_clear"
        };

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            var args = Environment.GetCommandLineArgs();
            int flag = Array.IndexOf(args, "--twin-realism-evidence");
            if (flag < 0 || flag + 1 >= args.Length) return;
            var probe = new GameObject("Twin realism evidence").AddComponent<TwinRealismEvidence>();
            probe.m_Output = Path.GetFullPath(args[flag + 1]);
            probe.m_CoastOnly = Array.IndexOf(args,"--twin-realism-coast") >= 0;
            probe.m_BowOnly = Array.IndexOf(args,"--twin-realism-bow") >= 0;
        }

        IEnumerator Start()
        {
            Directory.CreateDirectory(m_Output);
            HudVisibility.Hide();
            var session = FindFirstObjectByType<VisualSimulationSession>();
            if (session != null)
            {
                session.PauseRun();
                session.enabled = false;
                foreach (var ship in session.originalVessels)
                    if (ship != null && ship.GetComponent<WaypointFollower>() != null) ship.SetActive(false);
            }
            m_Weather = FindFirstObjectByType<WeatherController>();
            m_Rig = FindFirstObjectByType<CameraRig>();
            m_Driver = FindFirstObjectByType<TwinSessionDriver>();
            if (m_Driver == null || m_Weather == null || m_Rig == null)
            { Debug.LogError("[Sango.Realism] fixture wiring missing"); Application.Quit(1); yield break; }
            bool norway = m_Driver.geography != null;
            if (norway) { m_Position = new Vector3(-3000,0,-2450); m_Heading = 45; }
            if (m_CoastOnly)
            {
                m_Times = new float[] { 5,15,30,45,60,90,120,150 };
                m_Names = Array.ConvertAll(m_Times,t => "coast-" + t.ToString("000"));
            }
            if (m_BowOnly)
            {
                m_Times = new float[] { 2,5,8,12,16,20,24,28 };
                m_Names = Array.ConvertAll(m_Times,t => "bow-" + t.ToString("000"));
            }
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;
            Screen.SetResolution(2560, 1440, FullScreenMode.Windowed);
            var cameraData = m_Rig.controlledCamera.GetComponent<HDAdditionalCameraData>();
            cameraData.antialiasing = HDAdditionalCameraData.AntialiasingMode.TemporalAntialiasing;
            cameraData.customRenderingSettings = true;
            var settings = cameraData.renderingPathCustomFrameSettings;
            settings.SetEnabled(FrameSettingsField.WaterDecals, true);
            cameraData.renderingPathCustomFrameSettings = settings;
            var mask = cameraData.renderingPathCustomFrameSettingsOverrideMask;
            mask.mask[(uint)FrameSettingsField.WaterDecals] = true;
            cameraData.renderingPathCustomFrameSettingsOverrideMask = mask;
            yield return new WaitForSecondsRealtime(3);
            var landscape = FindFirstObjectByType<TwinCesiumLandscape>();
            float start = Time.realtimeSinceStartup + (!m_CoastOnly && !m_BowOnly && landscape != null && landscape.Status == "loading" ? 65 : 0);
            m_LastCapture = start;
            while (m_Shot < m_Times.Length)
            {
                m_Time = Mathf.Max(0,Time.realtimeSinceStartup - start);
                float dt = Time.unscaledDeltaTime;
                float speed = !m_CoastOnly && m_Time > 3 && m_Time < 46 ? 7.716f : 0;
                if (m_Time > 28 && m_Time < 40) m_Heading += dt * 3;
                var forward = Quaternion.Euler(0, m_Heading, 0) * Vector3.forward;
                m_Position += forward * speed * dt;
                m_Driver.OfferReplayFrame(new ColavTelemetry {
                    seq = ++m_Sequence, sim_time = m_Time, state = "RUNNING", environment = m_Environment,
                    playback = new ColavTelemetry.Playback { effective_multiplier = 1, requested_multiplier = 1 },
                    truth = new[] { new ColavTelemetry.ShipEntry { id = 0, length = 45, width = 8,
                        east = m_Position.x + (norway ? NorwayChartFrame.OriginEastM : 0),
                        north = m_Position.z + (norway ? NorwayChartFrame.OriginNorthM : 0), psi = m_Heading * Mathf.Deg2Rad,
                        sog = speed, u = speed, active = true, has_roll = true, roll_rad = 0 } }
                });
                var own = m_Driver.OwnShipObject;
                if (own != null)
                {
                    var pos = own.transform.position;
                    pos.y = own.GetComponentInChildren<BoatWaterDecals>().transform.position.y;
                    var rotation = Quaternion.Euler(0, m_Heading, 0);
                    Vector3 eye, aim;
                    if (m_CoastOnly || m_Time >= 107)
                    { eye = norway ? new Vector3(2700,45,-2200) : new Vector3(-2200,25,-2100); aim = norway ? new Vector3(3200,18,-1500) : new Vector3(-2300,12,-1300); }
                    else if (m_Time >= 77)
                    { eye = norway ? new Vector3(-3000,60,-2450) : new Vector3(-1500,60,-5000); aim = norway ? new Vector3(-3000,20,-450) : new Vector3(-1500,40,-1800); }
                    else if (m_BowOnly || m_Time >= 40 && m_Time < 46)
                    { eye = pos + rotation * new Vector3(18,14,32); aim = pos + rotation * new Vector3(0,0,14); }
                    else if (m_Time >= 28 && m_Time < 40)
                    { eye = pos + new Vector3(0, 240, -40); aim = pos - forward * 50; }
                    else
                    { eye = pos + rotation * new Vector3(72, 65, 105); aim = pos - forward * 45; }
                    var look = Quaternion.LookRotation(aim - eye).eulerAngles;
                    m_Rig.SetFreePose(eye, look.y, -Mathf.DeltaAngle(0, look.x), 50);
                }
                yield return new WaitForEndOfFrame();
                if (Time.realtimeSinceStartup < start) { m_LastCapture = Time.realtimeSinceStartup; continue; }
                m_Frames++;
                if (m_Time < m_Times[m_Shot] || own == null) continue;
                var trail = own.GetComponentInChildren<TwinWakeTrail>();
                var contact = own.GetComponentInChildren<BoatWaterDecals>();
                var attitude = own.GetComponent<VesselBuoyancy>().SmoothedAttitude;
                var sky = HDCamera.GetOrCreate(m_Rig.controlledCamera).volumeStack.GetComponent<VisualEnvironment>();
                m_Report.shots.Add(new Shot { name = m_Names[m_Shot], seconds = m_Time,
                    fps = m_Frames / (Time.realtimeSinceStartup - m_LastCapture),
                    width = Screen.width, height = Screen.height, wakeSamples = trail?.ActiveSamples ?? 0,
                    skyType = sky.skyType.value, foamPeak = contact?.BufferFoamMax ?? 0,
                    heave = attitude.x, pitch = attitude.z,
                    landscape = landscape?.Status, terrainMeshes = landscape?.TerrainMeshes ?? 0,
                    buildingMeshes = landscape?.BuildingMeshes ?? 0 });
                ScreenCapture.CaptureScreenshot(Path.Combine(m_Output, m_Names[m_Shot] + ".png"));
                m_LastCapture = Time.realtimeSinceStartup; m_Frames = 0; m_Shot++;
                File.WriteAllText(Path.Combine(m_Output, "report.json"), JsonUtility.ToJson(m_Report, true));
            }
            yield return new WaitForSecondsRealtime(1);
            Application.Quit();
        }
    }
}
