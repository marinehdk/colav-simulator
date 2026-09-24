using System.Collections;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace Sango.Editor
{
    /// <summary>
    /// M2-D R2 spike 探针（spec #83，time-boxed）：渲染主相机 → 回读水面补丁像素 →
    /// 航行灯 ON vs OFF 的亮度数值对比，裁定 HDRP Water 对本地点光的镜面响应是否
    /// 在演示机位下可读（真实反射）或需要假 streak 兜底。判据（预先声明，写进报告）：
    /// 近船补丁 (meanOn − meanOff) ≥ 3× 远处对照补丁漂移 且 相对提升 ≥ +50% → real，否则 fallback。
    /// 采集路径：HDRP RenderPipeline.SubmitRenderRequest(StandardRequest) 同步渲染到 ARGBHalf RT
    /// （batchmode 无 Game view 也可用）；失败则回落 ScreenCapture 截屏纹理（LDR，需窗口化编辑器）。
    /// Perf 变体：挂 M0 既有 FpsProbe（1 s 窗 jsonl），正午/午夜各采 12 s 平均 fps。
    /// 泵模式同 M1VerifyCapture（SessionState + 域重载恢复）；注意 EditorPump 是裸 MoveNext——
    /// 嵌套 IEnumerator 不支持，wall-time 等待一律内联自旋循环。
    /// </summary>
    public static class M2DLightsProbe
    {
        const string k_SpikePendingKey = "sango.m2d.spike.pending";
        const string k_PerfPendingKey = "sango.m2d.perf.pending";
        const string k_ScenePath = "Assets/Scenes/M1-Weather.unity";
        const string k_SpikeReportPath = "/tmp/sango-m2d-spike.json";
        const string k_PerfReportPath = "/tmp/sango-m2d-perf.json";
        const float k_SettleSeconds = 3f;
        const float k_PerfWindowSeconds = 12f;

        [MenuItem("Sango/M2D/Run Water Reflection Spike")]
        public static void RunSpike()
        {
            EditorSceneManager.OpenScene(k_ScenePath);
            SessionState.SetBool(k_SpikePendingKey, true);
            EditorApplication.isPlaying = true;
        }

        [MenuItem("Sango/M2D/Run Night Perf Probe")]
        public static void RunPerf()
        {
            EditorSceneManager.OpenScene(k_ScenePath);
            SessionState.SetBool(k_PerfPendingKey, true);
            EditorApplication.isPlaying = true;
        }

        [InitializeOnLoadMethod]
        static void ResumePendingRun()
        {
            if (SessionState.GetBool(k_SpikePendingKey, false))
                new EditorPump(SpikeSteps());
            else if (SessionState.GetBool(k_PerfPendingKey, false))
                new EditorPump(PerfSteps());
        }

        // ── Spike ──────────────────────────────────────────────────────────────────────

        static IEnumerator SpikeSteps()
        {
            var report = new StringBuilder("{");
            WeatherController controller = null;
            Camera camera = null;
            NavigationLights[] lights = null;
            for (int i = 0; i < 1200 && (controller == null || camera == null || lights == null || lights.Length == 0); i++)
            {
                if (Application.isPlaying)
                {
                    controller = Object.FindFirstObjectByType<WeatherController>();
                    camera = Camera.main;
                    lights = Object.FindObjectsByType<NavigationLights>(FindObjectsSortMode.None);
                }
                yield return null;
            }
            if (controller == null || camera == null || lights == null || lights.Length == 0)
            {
                report.Append("\"verdict\":\"FAIL\",\"reason\":\"scene objects not found in play mode\"}");
                FinishSpike(report);
                yield break;
            }

            // 夜 + 静海（平滑水面 = 最强镜面读数）；fog/云走默认（3000 m / 0.4）。
            controller.beaufort = 0f;
            controller.spectrumTier = JsPmTier.Calm;
            controller.timeOfDayHours = 0f;
            for (float t0 = Time.realtimeSinceStartup; Time.realtimeSinceStartup - t0 < k_SettleSeconds;)
            {
                yield return null;
            }

            // 观测点（世界系 y=0 水面）：演示近船（小渔船）向相机一侧两档距离 + 远处对照补丁。
            var small = lights[0];
            foreach (var l in lights)
            {
                if (l.name.Contains("Small")) small = l;
            }
            var shipPos = small.transform.position;
            var toCam = new Vector3(camera.transform.position.x - shipPos.x, 0f,
                                    camera.transform.position.z - shipPos.z).normalized;
            var shipWater = new Vector3(shipPos.x, 0f, shipPos.z);
            var pNear1 = shipWater + toCam * 10f;
            var pNear2 = shipWater + toCam * 30f;
            // 拖尾补丁：直接取桅灯拖尾 quad 的实时世界位姿（UpdateStreaks 逐帧摆放），
            // 手估偏移会落进船体/水面混合区（小船拖尾仅 ~5 m 长）。
            var rigRoot = small.transform.Find("NavigationLightsRig");
            var streakT = rigRoot != null ? rigRoot.Find("Masthead.Streak") : null;
            var pStreak = streakT != null ? streakT.position : shipWater + toCam * 2.5f;
            var pControl = shipWater + new Vector3(-toCam.z, 0f, toCam.x) * 80f;
            report.Append($"\"ship\":\"{small.name}\",\"near1\":\"{V3(pNear1)}\",\"near2\":\"{V3(pNear2)}\",\"streak\":\"{V3(pStreak)}\",\"control\":\"{V3(pControl)}\",");

            // ON 采集（暖身渲染一帧丢弃，避开首渲 shader 编译卡顿；暖身回读即弃）。
            WarmupRender(camera);
            var (lumOn, w, h, okOn, pathOn) = CaptureLuminance(camera);
            var meanOn = SamplePatches(camera, lumOn, w, h, pNear1, pNear2, pStreak, pControl);
            report.Append($"\"capture\":\"{pathOn}\",");
            report.Append($"\"on\":{Json(meanOn)},");
            if (!okOn)
            {
                report.Append("\"verdict\":\"FAIL\",\"reason\":\"render request + screen capture both failed\"}");
                FinishSpike(report);
                yield break;
            }

            // OFF 采集：禁用 rig 子树（组件 disabled 不隐藏子物体，双保险）。
            foreach (var l in lights)
            {
                l.enabled = false;
                var rig = l.transform.Find("NavigationLightsRig");
                if (rig != null) rig.gameObject.SetActive(false);
            }
            for (float t0 = Time.realtimeSinceStartup; Time.realtimeSinceStartup - t0 < 0.5f;)
            {
                yield return null;
            }
            var (lumOff, _, _, _, _) = CaptureLuminance(camera);
            var meanOff = SamplePatches(camera, lumOff, w, h, pNear1, pNear2, pStreak, pControl);
            report.Append($"\"off\":{Json(meanOff)},");

            float dNear1 = meanOn.near1.mean - meanOff.near1.mean;
            float dNear2 = meanOn.near2.mean - meanOff.near2.mean;
            float dStreak = meanOn.streak.mean - meanOff.streak.mean;
            float dControl = meanOn.control.mean - meanOff.control.mean;
            float noise = Mathf.Max(Mathf.Abs(dControl), 1e-6f);
            float rel1 = dNear1 / Mathf.Max(meanOff.near1.mean, 1e-6f);
            float rel2 = dNear2 / Mathf.Max(meanOff.near2.mean, 1e-6f);
            bool real = (dNear1 >= 3f * noise && rel1 >= 0.5f) || (dNear2 >= 3f * noise && rel2 >= 0.5f);
            // 可见性用同帧对比度（跨帧 Δ 全被曝光适应漂移污染——control 补丁自己都漂 ±60%）：
            // 拖尾补丁比同机位开阔水面补丁亮 ≥50% 即视为可读。
            float streakContrast = meanOn.streak.mean / Mathf.Max(meanOn.near1.mean, 1e-6f);
            bool streakVisible = streakContrast >= 1.5f;
            bool blackRender = meanOff.near1.mean < 1e-6f && meanOff.control.mean < 1e-6f;

            // 全帧增量（补丁采样对拖尾这种小目标会混进船体/水面像素，改用全帧统计）：
            // 噪声门 = 3×全帧 |ΔL| 中位数（灯只动少数像素，中位数≈全局漂移/曝光适应），
            // changedFrac = 超门像素占比。灯系可见 ⇔ 占比显著 > 0。
            long sumAbs = 0;
            var absSamples = new System.Collections.Generic.List<float>();
            int n = lumOn.Length;
            for (int i = 0; i < n; i++)
            {
                float d = Mathf.Abs(lumOn[i] - lumOff[i]);
                sumAbs += (long)(d * 1e6f);
                if ((i & 31) == 0) absSamples.Add(d); // 1/32 抽样估中位数
            }
            absSamples.Sort();
            float median = absSamples[absSamples.Count / 2];
            float gate = Mathf.Max(3f * median, 1e-5f);
            int changed = 0;
            for (int i = 0; i < n; i++)
            {
                if (Mathf.Abs(lumOn[i] - lumOff[i]) > gate) changed++;
            }
            float changedFrac = changed / (float)n;
            float meanAbs = sumAbs / (float)n * 1e-6f;
            report.Append($"\"delta\":{{\"near1\":{F(dNear1)},\"near2\":{F(dNear2)},\"streak\":{F(dStreak)},\"control\":{F(dControl)}}},");
            report.Append($"\"relGain\":{{\"near1\":{F(rel1)},\"near2\":{F(rel2)}}},");
            report.Append($"\"frame\":{{\"changedFrac\":{F(changedFrac)},\"gate\":{F(gate)},\"meanAbsDelta\":{F(meanAbs)},\"streakContrastOn\":{F(streakContrast)}}},");
            report.Append($"\"criterion\":\"real if near delta >= 3x control drift AND rel gain >= 50%; streak visible if same-frame contrast >= 1.5\",");
            report.Append($"\"verdict\":\"{(blackRender ? "INCONCLUSIVE_BLACK_RENDER" : real ? "REAL" : streakVisible || changedFrac > 0.001f ? "FALLBACK_STREAK_VISIBLE" : "FALLBACK_STREAK_NOT_VISIBLE")}\"}}");

            FinishSpike(report);
        }

        static void FinishSpike(StringBuilder report)
        {
            string json = report.ToString();
            File.WriteAllText(k_SpikeReportPath, json);
            Debug.Log($"[Sango.M2D.spike] report={k_SpikeReportPath} {json}");
            SessionState.SetBool(k_SpikePendingKey, false);
            EditorApplication.isPlaying = false;
            EditorApplication.Exit(0); // CLI 化：-executeMethod 调用后自动退编辑器
        }

        // ── Perf（窗口化编辑器：游戏视图真实渲染才有 fps 可言；batchmode 无渲染帧）─────────

        static IEnumerator PerfSteps()
        {
            WeatherController controller = null;
            for (int i = 0; i < 1200 && controller == null; i++)
            {
                if (Application.isPlaying) controller = Object.FindFirstObjectByType<WeatherController>();
                yield return null;
            }
            if (controller == null)
            {
                File.WriteAllText(k_PerfReportPath, "{\"verdict\":\"FAIL\",\"reason\":\"no controller\"}");
                Debug.Log("[Sango.M2D.perf] FAIL: no controller");
                EditorApplication.isPlaying = false;
                EditorApplication.Exit(0);
                yield break;
            }

            // M0 既有采集仪：FpsProbe 每秒聚合写 Logs/fps-report.jsonl（工程根，不入库）。
            var fpsProbe = Object.FindFirstObjectByType<FpsProbe>() ?? controller.gameObject.AddComponent<FpsProbe>();
            controller.beaufort = 3f;
            controller.spectrumTier = JsPmTier.Moderate;
            controller.fogDistanceMeters = 3000f;

            controller.timeOfDayHours = 12f;
            for (float t0 = Time.realtimeSinceStartup; Time.realtimeSinceStartup - t0 < k_SettleSeconds;)
            {
                yield return null;
            }
            int noonMark = JsonlLineCount();
            for (float t0 = Time.realtimeSinceStartup; Time.realtimeSinceStartup - t0 < k_PerfWindowSeconds;)
            {
                yield return null;
            }
            float noonFps = JsonlAvgFps(noonMark);

            controller.timeOfDayHours = 0f;
            for (float t0 = Time.realtimeSinceStartup; Time.realtimeSinceStartup - t0 < k_SettleSeconds;)
            {
                yield return null;
            }
            int nightMark = JsonlLineCount();
            for (float t0 = Time.realtimeSinceStartup; Time.realtimeSinceStartup - t0 < k_PerfWindowSeconds;)
            {
                yield return null;
            }
            float nightFps = JsonlAvgFps(nightMark);

            string json = $"{{\"res\":\"{Screen.width}x{Screen.height}\",\"noon_fps\":{F(noonFps)},\"night_fps\":{F(nightFps)},\"window_s\":{F(k_PerfWindowSeconds)}}}";
            File.WriteAllText(k_PerfReportPath, json);
            Debug.Log($"[Sango.M2D.perf] {json}");
            EditorApplication.isPlaying = false;
            EditorApplication.Exit(0);
        }

        static string JsonlPath() =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Logs", "fps-report.jsonl"));

        static int JsonlLineCount()
        {
            try
            {
                var lines = File.ReadAllLines(JsonlPath());
                int n = 0;
                foreach (var line in lines)
                {
                    if (line.Contains("\"fps\"")) n++;
                }
                return n;
            }
            catch { return 0; }
        }

        static float JsonlAvgFps(int startLine)
        {
            try
            {
                var lines = File.ReadAllLines(JsonlPath());
                float sum = 0f;
                int n = 0;
                for (int i = startLine; i < lines.Length; i++)
                {
                    int idx = lines[i].IndexOf("\"fps\":", System.StringComparison.Ordinal);
                    if (idx < 0) continue;
                    var val = lines[i].Substring(idx + 6).Split(',')[0];
                    if (float.TryParse(val, NumberStyles.Float, CultureInfo.InvariantCulture, out var fps))
                    {
                        sum += fps;
                        n++;
                    }
                }
                return n > 0 ? sum / n : -1f;
            }
            catch { return -1f; }
        }

        // ── 采集 ───────────────────────────────────────────────────────────────────────

        static void WarmupRender(Camera camera)
        {
            var rt = RenderTexture.GetTemporary(640, 360, 24, RenderTextureFormat.ARGBHalf);
            try
            {
                RenderPipeline.SubmitRenderRequest(camera, new RenderPipeline.StandardRequest { destination = rt });
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"[Sango.M2D.spike] warmup render failed: {e.GetType().Name} {e.Message}");
            }
            RenderTexture.ReleaseTemporary(rt);
        }

        // 渲染一帧 → 逐像素 Rec.709 亮度数组（HDR 线性；batchmode 走 Render Request，
        // 失败回落 Game view 截屏纹理的 LDR 亮度）。
        static (float[] lum, int w, int h, bool ok, string path) CaptureLuminance(Camera camera)
        {
            Texture2D tex = null;
            string path = "render-request";
            var rt = RenderTexture.GetTemporary(1280, 720, 24, RenderTextureFormat.ARGBHalf);
            try
            {
                // StandardRequest 嵌套在 RenderPipeline 内（UnityEngine.CoreModule）。
                RenderPipeline.SubmitRenderRequest(camera, new RenderPipeline.StandardRequest { destination = rt });
                tex = Readback(rt);
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"[Sango.M2D.spike] SubmitRenderRequest failed: {e.GetType().Name} {e.Message} — falling back to screen capture");
            }
            finally
            {
                RenderTexture.ReleaseTemporary(rt);
            }

            // 回落：Game view 截屏纹理（LDR，需窗口化编辑器真实渲染）。
            if (tex == null)
            {
                path = "screen-capture";
                tex = ScreenCapture.CaptureScreenshotAsTexture();
                if (tex == null) return (null, 0, 0, false, path);
            }

            var pixels = tex.GetPixels();
            var lum = new float[pixels.Length];
            for (int i = 0; i < pixels.Length; i++)
            {
                lum[i] = 0.2126f * pixels[i].r + 0.7152f * pixels[i].g + 0.0722f * pixels[i].b;
            }
            int w = tex.width, h = tex.height;
            Object.DestroyImmediate(tex);
            return (lum, w, h, true, path);
        }

        static Texture2D Readback(RenderTexture rt)
        {
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGBAFloat, false);
            tex.ReadPixels(new Rect(0f, 0f, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            return tex;
        }

        // 四个观测补丁（世界点 → 视口像素，25×25 块平均/最大亮度）。
        static PatchMeans SamplePatches(Camera camera, float[] lum, int w, int h, Vector3 pNear1, Vector3 pNear2, Vector3 pStreak, Vector3 pControl)
        {
            return new PatchMeans
            {
                near1 = PatchLuminance(camera, lum, w, h, pNear1),
                near2 = PatchLuminance(camera, lum, w, h, pNear2),
                streak = PatchLuminance(camera, lum, w, h, pStreak),
                control = PatchLuminance(camera, lum, w, h, pControl),
            };
        }

        // 世界水面点 → 视口像素，取 25×25 块的 Rec.709 平均/最大亮度。
        static PatchLum PatchLuminance(Camera camera, float[] lum, int w, int h, Vector3 world)
        {
            var vp = camera.WorldToViewportPoint(world);
            int cx = Mathf.Clamp((int)(vp.x * w), 13, w - 14);
            int cy = Mathf.Clamp((int)(vp.y * h), 13, h - 14);
            float sum = 0f, maxL = 0f;
            const int half = 12;
            int n = 0;
            for (int y = cy - half; y <= cy + half; y++)
            for (int x = cx - half; x <= cx + half; x++)
            {
                float l = lum[y * w + x];
                sum += l;
                if (l > maxL) maxL = l;
                n++;
            }
            return new PatchLum
            {
                mean = sum / n,
                max = maxL,
            };
        }

        struct PatchLum
        {
            public float mean;
            public float max;
        }

        struct PatchMeans
        {
            public PatchLum near1;
            public PatchLum near2;
            public PatchLum streak;
            public PatchLum control;
        }

        static string Json(PatchMeans m) =>
            $"{{\"near1\":{{\"mean\":{F(m.near1.mean)},\"max\":{F(m.near1.max)}}}," +
            $"\"near2\":{{\"mean\":{F(m.near2.mean)},\"max\":{F(m.near2.max)}}}," +
            $"\"streak\":{{\"mean\":{F(m.streak.mean)},\"max\":{F(m.streak.max)}}}," +
            $"\"control\":{{\"mean\":{F(m.control.mean)},\"max\":{F(m.control.max)}}}}}";

        static string F(float v) => v.ToString("R", CultureInfo.InvariantCulture);
        static string V3(Vector3 v) => $"({v.x:F1},{v.y:F1},{v.z:F1})";
    }
}
