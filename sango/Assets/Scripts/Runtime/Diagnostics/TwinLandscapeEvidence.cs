using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Sango
{
    // Opt-in, isolated GPU acceptance fixture. Does not connect to an Active Session.
    public sealed class TwinLandscapeEvidence : MonoBehaviour
    {
        [Serializable] class Shot
        {
            public string name;
            public float seconds, progress, fps;
            public int newMeshes;
            public long rssBytes;
        }
        [Serializable] class Report { public string warmup, mask, shader; public bool hasMask; public string[] keywords; public Color[] maskColors; public float warmupSeconds; public List<Shot> shots = new List<Shot>(); }
        string m_Output;
        bool m_MaskOnly;
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            var args = Environment.GetCommandLineArgs(); int i = Array.IndexOf(args,"--twin-landscape-evidence");
            if (i < 0 || i + 1 >= args.Length) return;
            foreach (var stream in FindObjectsByType<Unity.RenderStreaming.SignalingManager>(FindObjectsSortMode.None)) { stream.Stop(); stream.enabled = false; }
            var probe = new GameObject("Landscape cache evidence").AddComponent<TwinLandscapeEvidence>();
            probe.m_Output = Path.GetFullPath(args[i+1]);
            probe.m_MaskOnly = Array.IndexOf(args,"--twin-landscape-mask-only") >= 0;
        }
        IEnumerator Start()
        {
            Directory.CreateDirectory(m_Output);
            HudVisibility.Hide();
            var session = FindFirstObjectByType<VisualSimulationSession>();
            if (session != null) { session.PauseRun(); session.enabled = false; }
            var bridge = FindFirstObjectByType<TwinBridgeService>();
            if (bridge != null) bridge.runtimeEnabled = false;
            var landscape = FindFirstObjectByType<TwinCesiumLandscape>();
            var rig = FindFirstObjectByType<CameraRig>();
            if (landscape == null || rig?.controlledCamera == null) { Application.Quit(1); yield break; }
            rig.bridgeMount = rig.bowMount = null;
            Screen.SetResolution(1920,1080,FullScreenMode.Windowed);
            Application.targetFrameRate = 30; QualitySettings.vSyncCount = 0;
            var own = new Vector3(2700,0,-2200);
            var route = new[] { own, new Vector3(3200,0,-1500), new Vector3(4200,0,-1500) };
            var eyes = new[] { new Vector3(2700,45,-2200), new Vector3(3100,120,-1850), new Vector3(2700,45,-2200) };
            var aim = new Vector3(3200,18,-1500);
            Action<Vector3> view = eye => { var rotation = Quaternion.LookRotation(aim-eye).eulerAngles;
                rig.SetFreePose(eye,rotation.y,-Mathf.DeltaAngle(0,rotation.x),50); };
            view(eyes[0]); yield return new WaitForSecondsRealtime(2);
            if (m_MaskOnly)
            {
                var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
                quad.transform.SetPositionAndRotation(rig.controlledCamera.transform.position + rig.controlledCamera.transform.forward * 5,
                    rig.controlledCamera.transform.rotation);
                quad.transform.localScale = Vector3.one * 3;
                var material = new Material(Resources.Load<Material>("TwinCesiumLandscapeMaterial") ?? Resources.Load<Material>("CesiumUnlitTilesetMaterial"));
                material.SetColor("_baseColorFactor",Color.red);
                material.SetTexture("_baseColorTexture",Texture2D.whiteTexture);
                material.SetFloat("_AlphaCutoffEnable",1); material.EnableKeyword("_ALPHATEST_ON");
                quad.GetComponent<MeshRenderer>().sharedMaterial = material;
                var colors = new Color[4];
                for (int i = 0; i < 4; i++)
                {
                    material.SetColor("_baseColorFactor",new Color(1,0,0,i == 2 ? 0 : 1));
                    material.SetTexture("_overlayTexture_Clipping",i == 0 ? Texture2D.whiteTexture : Texture2D.blackTexture);
                    yield return new WaitForSecondsRealtime(1);
                    yield return new WaitForEndOfFrame();
                    var screenshot = ScreenCapture.CaptureScreenshotAsTexture();
                    colors[i] = screenshot.GetPixel(screenshot.width/2,screenshot.height/2);
                    File.WriteAllBytes(Path.Combine(m_Output,new[] { "mask-white.png", "mask-black.png", "alpha-zero.png", "alpha-one.png" }[i]),screenshot.EncodeToPNG());
                    Destroy(screenshot);
                }
                bool passed = Vector3.Distance(new Vector3(colors[0].r,colors[0].g,colors[0].b),new Vector3(colors[1].r,colors[1].g,colors[1].b)) > .15f;
                File.WriteAllText(Path.Combine(m_Output,"report.json"),JsonUtility.ToJson(new Report { mask=passed ? "passed" : "failed",maskColors=colors,shader=material.shader.name,hasMask=material.HasProperty("_overlayTexture_Clipping"),keywords=material.shaderKeywords },true));
                Application.Quit(passed ? 0 : 2); yield break;
            }
            float start = Time.unscaledTime;
            while (!landscape.Describe().ready && landscape.Describe().state != "failed" && Time.unscaledTime-start < 605)
            { landscape.PrepareViews("landscape-fixture",own,0,route); yield return null; }
            var report = new Report { warmup = landscape.Describe().state, warmupSeconds = Time.unscaledTime-start };
            File.WriteAllText(Path.Combine(m_Output,"report.json"),JsonUtility.ToJson(report,true));
            if (!landscape.Describe().ready) { Application.Quit(2); yield break; }
            for (int i = 0; i < eyes.Length; i++)
            {
                view(eyes[i]); float began = Time.unscaledTime, settled = -1; int frames = 0, meshes = landscape.TerrainMeshes;
                while (Time.unscaledTime-began < 120)
                {
                    landscape.PrepareViews("landscape-fixture",own,0,route); frames++;
                    if (landscape.TerrainLoad >= 99) { if (settled < 0) settled = Time.unscaledTime; }
                    else settled = -1;
                    if (settled >= 0 && Time.unscaledTime-settled >= 2) break;
                    yield return null;
                }
                yield return new WaitForEndOfFrame();
                string name = new[] { "coast-first", "island-near", "coast-return" }[i];
                report.shots.Add(new Shot { name=name, seconds=Time.unscaledTime-began, progress=landscape.TerrainLoad,
                    fps=frames/Mathf.Max(.01f,Time.unscaledTime-began),newMeshes=landscape.TerrainMeshes-meshes,
                    rssBytes=System.Diagnostics.Process.GetCurrentProcess().WorkingSet64 });
                ScreenCapture.CaptureScreenshot(Path.Combine(m_Output,name+".png"));
                File.WriteAllText(Path.Combine(m_Output,"report.json"),JsonUtility.ToJson(report,true));
                yield return new WaitForSecondsRealtime(1);
            }
            Application.Quit();
        }
    }
}
