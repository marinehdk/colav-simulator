using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>Opt-in standalone acceptance capture. Uses real rendering and wall time, never Recorder's fixed clock.</summary>
    public class StageOneVerification : MonoBehaviour
    {
        [Serializable]
        public class Window
        {
            public string name;
            public int width, height, frames, failedQueries;
            public int maxWaterQueries;
            public long receivedDetectionResults;
            public int liveFrames;
            public float maxBuoyancyCpuMs, beaufort, simulationWindKmh, band0, band1;
            public double seconds, fps;
            public float waterMin, waterMax;
            public Vector3 targetMin, targetMax, smoothedMin, smoothedMax;
            public bool wetnessBuilt;
        }
        [Serializable]
        public class Report { public string unityVersion; public bool passed; public string[] failures; public Window[] windows; }

        readonly List<Window> m_Windows = new List<Window>();
        string m_Output;
        WeatherController m_Weather;
        CameraRig m_Camera;
        VesselBuoyancy m_Buoyancy;
        WaypointFollower m_Follower;
        bool m_VerifyDetector;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            var args = Environment.GetCommandLineArgs();
            int flag = Array.IndexOf(args, "--sango-verify");
            if (flag < 0) return;
            if (flag + 1 >= args.Length) { Debug.LogError("[Sango.Verify] missing output directory"); return; }
            var host = new GameObject("Stage one verification").AddComponent<StageOneVerification>();
            host.m_Output = Path.GetFullPath(args[flag + 1]);
        }

        IEnumerator Start()
        {
            Directory.CreateDirectory(m_Output);
            m_Weather = FindFirstObjectByType<WeatherController>();
            m_Camera = FindFirstObjectByType<CameraRig>();
            m_Buoyancy = GameObject.Find("VesselFcb45")?.GetComponent<VesselBuoyancy>();
            if (m_Buoyancy == null || m_Weather == null || m_Camera == null)
            { Debug.LogError("[Sango.Verify] M6 hero/weather/camera missing"); Application.Quit(1); yield break; }
            m_Follower = m_Buoyancy.GetComponent<WaypointFollower>();
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            Screen.SetResolution(2560, 1440, FullScreenMode.Windowed);
            HudVisibility.Hide();
            m_VerifyDetector = Array.IndexOf(Environment.GetCommandLineArgs(), SangoSeamConfig.PublisherCliFlag) >= 0;
            if (m_VerifyDetector)
            {
                var overlay = FindFirstObjectByType<DetectionOverlay>();
                overlay.enabled = true;
                overlay.visible = true;
            }
            yield return new WaitForSecondsRealtime(8f);
            m_Camera.SetView(CameraView.Chase);
            yield return new WaitForSecondsRealtime(2f);
            yield return Measure("high-1440p", 12f);
            foreach (int bft in new[] { 0, 3, 6, 9 })
            {
                m_Weather.beaufort = bft;
                m_Weather.spectrumTier = bft <= 1 ? JsPmTier.Calm : bft <= 4 ? JsPmTier.Moderate : bft <= 7 ? JsPmTier.Rough : JsPmTier.VeryRough;
                m_Weather.Apply();
                yield return new WaitForSecondsRealtime(5f);
                yield return Measure("buoyancy-B" + bft, 6f);
                ScreenCapture.CaptureScreenshot(Path.Combine(m_Output, "buoyancy-B" + bft + ".png"));
                yield return new WaitForEndOfFrame();
            }
            m_Weather.beaufort = 3f; m_Weather.spectrumTier = JsPmTier.Moderate; m_Weather.Apply();
            if (!m_Follower.DemoRunning) m_Follower.Toggle();
            yield return new WaitForSecondsRealtime(5f);
            yield return Measure("high-moving-1440p", 12f);
            foreach (var view in new[] { CameraView.Bridge, CameraView.Bow, CameraView.Chase, CameraView.TopDown, CameraView.Overlook })
            {
                m_Camera.SetView(view);
                yield return new WaitForSecondsRealtime(3f);
                ScreenCapture.CaptureScreenshot(Path.Combine(m_Output, "day-" + view + ".png"));
                yield return new WaitForEndOfFrame();
            }
            m_Weather.timeOfDayHours = 0f; m_Weather.Apply();
            foreach (var view in new[] { CameraView.Bridge, CameraView.Chase, CameraView.Overlook })
            {
                m_Camera.SetView(view);
                yield return new WaitForSecondsRealtime(4f);
                ScreenCapture.CaptureScreenshot(Path.Combine(m_Output, "night-" + view + ".png"));
                yield return new WaitForEndOfFrame();
            }
            m_Weather.timeOfDayHours = 12f; m_Weather.Apply();
            M8Quality.SetTierFromDropdownIndex(1);
            yield return new WaitForSecondsRealtime(3f);
            yield return Measure("low-1440p", 12f);
            var failures = new List<string>();
            foreach (var window in m_Windows)
            {
                if (window.width != 2560 || window.height != 1440) failures.Add(window.name + ": actual resolution is not 1440p");
                if (window.failedQueries != 0 || float.IsInfinity(window.waterMin) || float.IsInfinity(window.waterMax))
                    failures.Add(window.name + ": water queries failed");
                if ((window.name.StartsWith("high-") || window.name == "low-1440p") && window.fps < 30.0)
                    failures.Add(window.name + ": fps below 30");
                if (m_VerifyDetector && (window.receivedDetectionResults == 0 || window.liveFrames == 0))
                    failures.Add(window.name + ": detector return was not observed");
            }
            File.WriteAllText(Path.Combine(m_Output, "report.json"), JsonUtility.ToJson(
                new Report { unityVersion = Application.unityVersion, windows = m_Windows.ToArray(),
                    passed = failures.Count == 0, failures = failures.ToArray() }, true));
            Debug.Log("[Sango.Verify] complete " + m_Output);
            Application.Quit(failures.Count == 0 ? 0 : 1);
        }

        IEnumerator Measure(string label, float duration)
        {
            var window = new Window { name = label, width = Screen.width, height = Screen.height,
                waterMin = float.PositiveInfinity, waterMax = float.NegativeInfinity,
                targetMin = Vector3.one * float.PositiveInfinity, targetMax = Vector3.one * float.NegativeInfinity,
                smoothedMin = Vector3.one * float.PositiveInfinity, smoothedMax = Vector3.one * float.NegativeInfinity };
            double start = Time.realtimeSinceStartupAsDouble;
            var water = m_Weather.waterSurface;
            var wake = m_Buoyancy.GetComponent<WakeFoamRig>();
            var consumer = FindFirstObjectByType<DetectionResultConsumer>();
            var overlay = FindFirstObjectByType<DetectionOverlay>();
            long initialRx = consumer != null ? consumer.RxCount : 0;
            window.beaufort = m_Weather.beaufort;
            window.simulationWindKmh = water.largeWindSpeed;
            window.band0 = water.largeBand0Multiplier;
            window.band1 = water.largeBand1Multiplier;
            while (Time.realtimeSinceStartupAsDouble - start < duration)
            {
                yield return new WaitForEndOfFrame();
                window.frames++;
                window.failedQueries += VesselBuoyancy.FrameFailedQueries;
                window.maxWaterQueries = Mathf.Max(window.maxWaterQueries, VesselBuoyancy.FrameQueries + (wake != null ? wake.LastWaterQueries : 0));
                window.maxBuoyancyCpuMs = Mathf.Max(window.maxBuoyancyCpuMs, (float)VesselBuoyancy.FrameQueryMs);
                if (overlay != null && overlay.HasFreshLiveResult) window.liveFrames++;
                window.targetMin = Vector3.Min(window.targetMin, m_Buoyancy.TargetAttitude);
                window.targetMax = Vector3.Max(window.targetMax, m_Buoyancy.TargetAttitude);
                window.smoothedMin = Vector3.Min(window.smoothedMin, m_Buoyancy.SmoothedAttitude);
                window.smoothedMax = Vector3.Max(window.smoothedMax, m_Buoyancy.SmoothedAttitude);
                var position = m_Buoyancy.transform.position;
                var search = new WaterSearchParameters { startPositionWS = new float3(position.x, 0f, position.z),
                    targetPositionWS = new float3(position.x, 0f, position.z), error = 0.01f, maxIterations = 8 };
                if (water.ProjectPointOnWaterSurface(search, out var result))
                {
                    window.waterMin = Mathf.Min(window.waterMin, result.projectedPositionWS.y);
                    window.waterMax = Mathf.Max(window.waterMax, result.projectedPositionWS.y);
                }
            }
            window.seconds = Time.realtimeSinceStartupAsDouble - start;
            window.fps = window.frames / window.seconds;
            window.wetnessBuilt = m_Buoyancy.GetComponent<HullWaterlineDecals>()?.RigBuilt ?? false;
            window.receivedDetectionResults = consumer != null ? consumer.RxCount - initialRx : 0;
            m_Windows.Add(window);
            File.WriteAllText(Path.Combine(m_Output, "report.json"), JsonUtility.ToJson(
                new Report { unityVersion = Application.unityVersion, windows = m_Windows.ToArray() }, true));
            Debug.Log("[Sango.Verify] " + JsonUtility.ToJson(window));
        }
    }
}
