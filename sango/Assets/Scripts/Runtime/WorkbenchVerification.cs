using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.UI;

namespace Sango
{
    /// <summary>Opt-in native end-to-end acceptance of the operator control boundary and onboard other-vessel perception.</summary>
    public class WorkbenchVerification : MonoBehaviour
    {
        [Serializable]
        public class Window
        {
            public string name;
            public int width, height, frames, liveFrames, nonemptyFrames, targetMatchedFrames, failedWaterQueries;
            public long receivedResults;
            public double seconds, fps;
            public double startTimeS, endTimeS;
            public float timeOfDayHours, beaufort, cloudCover, fogDistanceM;
            public bool rain, snow, wetLens, truthAssistedCameraLock;
            public float egoDistanceM, targetDistanceM, bestTargetIou;
        }
        [Serializable] public class Report
        {
            public bool passed;
            public string[] failures;
            public Window[] windows;
            public string model = "yolov8n / COCO boat / local CPU";
        }
        string m_Out;
        VisualSimulationSession m_Session;
        SimulationWorkbench m_View;
        readonly List<Window> m_Windows = new List<Window>();
        readonly List<string> m_Failures = new List<string>();
        bool m_Live;
        bool m_RecordVideo;
        bool m_UiOnly;
        bool m_FixedCamera;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            var args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "--sango-workbench-verify");
            if (index < 0) return;
            if (index + 1 >= args.Length) { UnityEngine.Debug.LogError("Missing workbench evidence directory"); Application.Quit(1); return; }
            var verifier = new GameObject("Workbench native acceptance").AddComponent<WorkbenchVerification>();
            verifier.m_Out = Path.GetFullPath(args[index + 1]);
            verifier.m_Live = Array.IndexOf(args, "--sango-publisher") >= 0;
            verifier.m_RecordVideo = Array.IndexOf(args, "--sango-workbench-video") >= 0;
            verifier.m_UiOnly = Array.IndexOf(args, "--sango-workbench-ui-only") >= 0;
            verifier.m_FixedCamera = Array.IndexOf(args, "--sango-workbench-fixed-camera") >= 0;
        }

        IEnumerator Start()
        {
            Directory.CreateDirectory(m_Out);
            QualitySettings.vSyncCount = 0; Application.targetFrameRate = -1;
            Screen.SetResolution(2560, 1440, FullScreenMode.Windowed);
            yield return new WaitForSecondsRealtime(4f);
            m_Session = FindFirstObjectByType<VisualSimulationSession>();
            m_View = FindFirstObjectByType<SimulationWorkbench>();
            if (m_Session == null || m_View == null) { UnityEngine.Debug.LogError("Workbench scene wiring missing"); Application.Quit(1); yield break; }
            ScreenCapture.CaptureScreenshot(Path.Combine(m_Out, "setup.png"));
            yield return new WaitForEndOfFrame();
            var setup = new VisualSimulationSettings {
                sceneMode = VisualSceneMode.Procedural, vesselClass = VesselClass.Fcb45,
                sensorMode = m_Live ? VisualSensorMode.YoloAndTruthRadar : VisualSensorMode.GroundTruth,
                confidence = 0.25f, detectionIntervalS = 0.125f,
                truthAssistedCameraLock = !m_FixedCamera,
                targets = new[] { new VisualTargetVessel { id = 1, vesselClass = VesselClass.Tug,
                    offsetMeters = new Vector2(-60f, 100f), speedMps = 3.5f, headingDeg = 90f,
                    waypoints = new[] { new Vector2(120f, 100f), new Vector2(-120f, 100f) } } }
            };
            if (!m_Session.Apply(setup)) { Fail("Apply", m_Session.Status); Finish(); yield break; }
            File.WriteAllText(Path.Combine(m_Out, "scene.json"), m_Session.ExportSceneJson());
            yield return VerifyAuthoringButtons();
            if (m_UiOnly) { yield return VerifyScaling(); Finish(); yield break; }
            m_View.ShowSettings(false);
            m_Session.StartRun();
            yield return new WaitForSecondsRealtime(7f);
            foreach (var condition in new[] { "day", "dusk", "night", "fog", "rain", "rough-sea" })
            {
                Configure(condition);
                m_Session.ResetRun(); m_Session.StartRun();
                yield return new WaitForSecondsRealtime(5f);
                yield return Measure(condition, 12f);
                ScreenCapture.CaptureScreenshot(Path.Combine(m_Out, condition + ".png"));
                yield return new WaitForEndOfFrame();
            }
            m_Session.PauseRun();
            var json = m_Session.ExportSceneJson();
            if (!m_Session.ImportSceneJson(json) || m_Session.ActorCount != 2) Fail("Reload", m_Session.Status);
            if (m_RecordVideo) yield return RecordVideos();
            yield return VerifyScaling();
            Finish();
        }

        IEnumerator VerifyAuthoringButtons()
        {
            string original = m_Session.ExportSceneJson();
            ClickButton("Targets");
            yield return null;
            ScreenCapture.CaptureScreenshot(Path.Combine(m_Out, "target-editor.png"));
            yield return new WaitForEndOfFrame();
            EditNumber("Initial east offset [m] input", "75");
            EditNumber("Initial north offset [m] input", "180");
            EditNumber("Speed [m/s] input", "2");
            ClickButton("Add target with these settings");
            yield return null;
            if (m_Session.ActorCount != 3) Fail("GUI add", "Target button did not create a third vessel");
            ClickButton("2  Tug");
            yield return null;
            EditNumber("Speed [m/s] input", "5");
            ClickButton("Update selected vessel");
            yield return null;
            if (m_Session.GetVesselDefinition(2)?.speedMps != 5f) Fail("GUI edit", "Edited target speed did not apply");
            ClickButton("Remove selected target");
            yield return null;
            if (m_Session.ActorCount != 2) Fail("GUI remove", "Target removal did not preserve two active vessels");
            if (!m_Session.ImportSceneJson(original)) Fail("GUI reset", m_Session.Status);
            ClickButton("Back");
            yield return null;
            EditNumber("Scene name input", "aeolus-acceptance-20261001");
            ClickButton("Save scene definition");
            yield return null;
            ClickButton("Load scene definition");
            yield return null;
            if (m_Session.ActorCount != 2) Fail("GUI load", "Saved scene failed to reload via UI binding");
            File.WriteAllText(Path.Combine(m_Out, "authoring-buttons.json"), "{\"invocation\":\"native Unity public Button.onClick and InputField.onEndEdit; separate from OS mouse validation\",\"add_edit_remove_save_load\":true,\"actor_count\":" + m_Session.ActorCount + "}");
            ScreenCapture.CaptureScreenshot(Path.Combine(m_Out, "setup-after-authoring.png"));
            yield return new WaitForEndOfFrame();
        }

        void ClickButton(string name)
        {
            var button = m_View.GetComponentsInChildren<Button>(true).FirstOrDefault(b => b.gameObject.activeInHierarchy && b.name == name);
            if (button == null) { Fail("GUI button", "Missing active button: " + name); return; }
            button.onClick.Invoke();
        }

        void EditNumber(string name, string value)
        {
            var input = m_View.GetComponentsInChildren<InputField>(true).FirstOrDefault(i => i.gameObject.activeInHierarchy && i.name == name);
            if (input == null) { Fail("GUI input", "Missing field: " + name); return; }
            input.text = value; input.onEndEdit.Invoke(value);
        }

        IEnumerator RecordVideos()
        {
            // Deliberately after FPS windows: screenshot JPEG recording is not real-time performance evidence.
            foreach (var condition in new[] { "day", "dusk", "night", "fog", "rain", "rough-sea" })
            {
                Configure(condition); m_Session.ResetRun(); m_Session.StartRun();
                yield return new WaitForSecondsRealtime(5f);
                string directory = Path.Combine(m_Out, "video-frames", condition);
                Directory.CreateDirectory(directory);
                using (var log = new StreamWriter(Path.Combine(directory, "capture.jsonl")))
                {
                    var timer = Stopwatch.StartNew();
                    int frame = 0;
                    while (timer.Elapsed.TotalSeconds < 8f)
                    {
                        yield return new WaitForEndOfFrame();
                        double time = Time.timeAsDouble;
                        var texture = ScreenCapture.CaptureScreenshotAsTexture();
                        if (texture == null) { Fail(condition, "Screen recording did not produce a frame"); break; }
                        File.WriteAllBytes(Path.Combine(directory, $"{frame:D4}.jpg"), ImageConversion.EncodeToJPG(texture, 70));
                        Destroy(texture);
                        var result = m_Session.overlay.CurrentLiveResult;
                        log.WriteLine("{\"capture_time_s\":" + time.ToString("R", System.Globalization.CultureInfo.InvariantCulture) +
                            ",\"status\":\"" + m_Session.overlay.DetectionStatus + "\",\"live_result\":" +
                            (result != null ? JsonUtility.ToJson(result) : "null") + "}");
                        frame++;
                        yield return new WaitForSecondsRealtime(0.125f);
                    }
                }
            }
            m_Session.PauseRun();
        }

        void Configure(string condition)
        {
            var weather = m_Session.weather;
            weather.timeOfDayHours = condition == "night" ? 0f : condition == "dusk" ? 17.5f : 12f;
            weather.beaufort = condition == "rough-sea" ? 6f : 3f;
            weather.spectrumTier = condition == "rough-sea" ? JsPmTier.Rough : JsPmTier.Moderate;
            weather.cloudCover = condition == "rain" ? 0.85f : 0.4f;
            weather.fogDistanceMeters = condition == "fog" ? 350f : 8000f;
            weather.precipitationOverride = true; weather.rainEnabled = condition == "rain";
            weather.snowEnabled = false; weather.wetLensEnabled = condition == "rain"; weather.thunderEnabled = false;
            weather.Apply();
        }

        IEnumerator Measure(string name, float duration)
        {
            var window = new Window { name = name, width = Screen.width, height = Screen.height,
                startTimeS = Time.timeAsDouble, timeOfDayHours = m_Session.weather.timeOfDayHours,
                beaufort = m_Session.weather.beaufort, cloudCover = m_Session.weather.cloudCover,
                fogDistanceM = m_Session.weather.fogDistanceMeters, rain = m_Session.weather.rainEnabled,
                snow = m_Session.weather.snowEnabled, wetLens = m_Session.weather.wetLensEnabled,
                truthAssistedCameraLock = m_Session.AppliedSettings.truthAssistedCameraLock };
            var egoStart = m_Session.Ego.transform.position;
            var target = m_Session.Actors[1];
            var targetStart = target.transform.position;
            long rx = m_Session.consumer != null ? m_Session.consumer.RxCount : 0;
            var timer = Stopwatch.StartNew();
            while (timer.Elapsed.TotalSeconds < duration)
            {
                yield return null;
                window.frames++;
                window.failedWaterQueries += VesselBuoyancy.FrameFailedQueries;
                var overlay = m_Session.overlay;
                if (overlay.HasFreshLiveResult)
                {
                    window.liveFrames++;
                    var live = overlay.CurrentLiveResult;
                    if (live.detections.Length > 0) window.nonemptyFrames++;
                    var truth = overlay.ProvideGroundTruth(live.frame_seq, live.frame_time_s);
                    float best = 0f;
                    foreach (var detected in live.detections) foreach (var box in truth.detections)
                        best = Mathf.Max(best, Iou(detected.box_xyxy, box.box_xyxy));
                    window.bestTargetIou = Mathf.Max(window.bestTargetIou, best);
                    if (best >= 0.3f) window.targetMatchedFrames++;
                }
            }
            timer.Stop();
            window.endTimeS = Time.timeAsDouble;
            window.seconds = timer.Elapsed.TotalSeconds; window.fps = window.frames / window.seconds;
            window.egoDistanceM = Vector3.Distance(egoStart, m_Session.Ego.transform.position);
            window.targetDistanceM = Vector3.Distance(targetStart, target.transform.position);
            window.receivedResults = (m_Session.consumer != null ? m_Session.consumer.RxCount : 0) - rx;
            m_Windows.Add(window);
            if (window.width != 2560 || window.height != 1440) Fail(name, "Resolution is not actual 1440p");
            if (window.fps < 30.0) Fail(name, "Wall-clock FPS below 30");
            if (window.failedWaterQueries != 0) Fail(name, "Water queries failed");
            if (window.egoDistanceM < 5f || window.targetDistanceM < 5f) Fail(name, "Both ego and other target must move");
            if (m_Live && (window.receivedResults == 0 || window.liveFrames == 0)) Fail(name, "No fresh real inference return");
            if (m_Live && name == "day" && window.targetMatchedFrames < 10) Fail(name, "Daytime onboard target detections not established");
            UnityEngine.Debug.Log("[Sango.Workbench] " + JsonUtility.ToJson(window));
            WriteReport(false);
        }

        IEnumerator VerifyScaling()
        {
            m_Session.PauseRun();
            var settings = new VisualSimulationSettings { sceneMode = VisualSceneMode.Procedural,
                environmentCount = 16, agentsPerEnvironment = 2, vesselClass = VesselClass.Fcb45,
                truthAssistedCameraLock = false, sensorMode = VisualSensorMode.GroundTruth };
            if (!m_Session.Apply(settings) || m_Session.ActorCount != 32) { Fail("32 actors", m_Session.Status); yield break; }
            m_View.ShowSettings(false); Configure("day"); m_Session.StartRun();
            yield return new WaitForSecondsRealtime(5f);
            int frames = 0, failedQueries = 0;
            var timer = Stopwatch.StartNew();
            while (timer.Elapsed.TotalSeconds < 5f) { yield return null; frames++; failedQueries += VesselBuoyancy.FrameFailedQueries; }
            timer.Stop(); m_Session.PauseRun();
            File.WriteAllText(Path.Combine(m_Out, "scaling-32.json"), "{\"actors\":" + m_Session.ActorCount +
                ",\"environments\":16,\"width\":" + Screen.width + ",\"height\":" + Screen.height +
                ",\"failed_water_queries\":" + failedQueries + ",\"fps\":" +
                (frames / timer.Elapsed.TotalSeconds).ToString("R", System.Globalization.CultureInfo.InvariantCulture) + "}");
            if (failedQueries != 0) Fail("32 actors", "Water query failures at maximum actor count");
            ScreenCapture.CaptureScreenshot(Path.Combine(m_Out, "scaling-32.png"));
            yield return new WaitForEndOfFrame();
        }

        static float Iou(float[] a, float[] b)
        {
            float width = Mathf.Max(0f, Mathf.Min(a[2], b[2]) - Mathf.Max(a[0], b[0]));
            float height = Mathf.Max(0f, Mathf.Min(a[3], b[3]) - Mathf.Max(a[1], b[1]));
            float area = width * height;
            float union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area;
            return union > 0f ? area / union : 0f;
        }
        void Fail(string step, string reason) => m_Failures.Add(step + ": " + reason);
        void WriteReport(bool final) => File.WriteAllText(Path.Combine(m_Out, "report.json"), JsonUtility.ToJson(new Report {
            passed = final && m_Failures.Count == 0, failures = m_Failures.ToArray(), windows = m_Windows.ToArray()
        }, true));
        void Finish() { WriteReport(true); Application.Quit(m_Failures.Count == 0 ? 0 : 1); }
    }
}
