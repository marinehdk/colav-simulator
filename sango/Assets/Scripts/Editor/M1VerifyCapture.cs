using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Sango.Editor
{
    /// <summary>
    /// M1 输入链路验证 + 证据采集（AX 菜单触发，避开 display topology 动荡下的 OS 层点击/截图）。
    /// Verify：进 Play → RaycastAll 探针 + 合成 IPointerClick 派发 → 断言 raycastTarget 修复与 TrackClickJump 生效
    ///         → 写 /tmp/sango-m1-input-verify.json → 自动退 Play。
    /// Capture：进 Play → 逐预设写 controller 公开字段（WeatherGUI.Update 镜像保持面板一致）→ 等水面收敛
    ///          → ScreenCapture.CaptureScreenshot → 覆盖 Beaufort 四档 / 昼夜 / 雾距 → 自动退 Play。
    /// 注意：合成事件不经过 OS 输入层，"真人鼠标可点"仍需人工复核一次。
    /// </summary>
    public static class M1VerifyCapture
    {
        const string k_VerifyStateKey = "sango.m1.verify.pending";
        const string k_CaptureStateKey = "sango.m1.capture.pending";
        const string k_ReportPath = "/tmp/sango-m1-input-verify.json";

        [MenuItem("Sango/M1/Verify UGUI Input Chain")]
        public static void Verify()
        {
            SessionState.SetBool(k_VerifyStateKey, true);
            EditorApplication.isPlaying = true; // 域重载后 InitializeOnLoadMethod 恢复泵
        }

        [MenuItem("Sango/M1/Capture M1 Evidence")]
        public static void Capture()
        {
            SessionState.SetBool(k_CaptureStateKey, true);
            EditorApplication.isPlaying = true;
        }

        // 面板 640 UI 单位高，停靠半高 Game view（~486px）装不下滑条区域且射线被裁剔——
        // 最大化 Game view 是验证/演示/截图的统一前置。（display topology 动荡下键盘/拖拽不可靠，走菜单。）
        [MenuItem("Sango/M1/Maximize Game View")]
        public static void MaximizeGameView()
        {
            foreach (var w in Resources.FindObjectsOfTypeAll<EditorWindow>())
            {
                if (w.titleContent.text != "Game") continue;
                try
                {
                    var prop = typeof(EditorWindow).GetProperty("maximized");
                    prop?.GetSetMethod(true)?.Invoke(w, new object[] { true });
                    w.Focus();
                    Debug.Log("[Sango.M1] game view maximized");
                    return;
                }
                catch (System.Exception e)
                {
                    Debug.LogError($"[Sango.M1] maximize failed: {e.GetType().Name} {e.Message}");
                    return;
                }
            }
            Debug.LogError("[Sango.M1] game view window not found");
        }

        [InitializeOnLoadMethod]
        static void ResumePendingRun()
        {
            // 前置：依赖进 Play 触发域重载来恢复协程泵。若工程开启 Enter Play Mode Options
            // 的"禁用域重载"，本恢复路径不会执行，Verify/Capture 会静默无输出。
            if (SessionState.GetBool(k_VerifyStateKey, false))
                new EditorPump(VerifySteps());
            else if (SessionState.GetBool(k_CaptureStateKey, false))
                new EditorPump(CaptureSteps());
        }

        // ── Verify ──────────────────────────────────────────────────────────────────────

        static IEnumerator VerifySteps()
        {
            var report = new Dictionary<string, object>();

            Canvas canvas = null;
            for (int i = 0; i < 1200; i++)
            {
                canvas = FindWeatherCanvas();
                if (Application.isPlaying && canvas != null) break;
                yield return null;
            }
            if (canvas == null)
            {
                report["verdict"] = "FAIL";
                report["reason"] = "play canvas not found within timeout";
                FinishVerify(report);
                yield break;
            }
            yield return null; // 再等一帧让 slider 布局完成

            var es = Object.FindFirstObjectByType<EventSystem>();
            var module = es != null ? es.currentInputModule : null;
            report["eventSystem"] = es != null ? es.name : null;
            report["inputModule"] = module != null ? module.GetType().Name : null;
            report["moduleEnabled"] = module != null && module.isActiveAndEnabled;

            // 射线探针：Beaufort 滑条 track 中心（ScreenSpaceOverlay 世界坐标即屏幕像素）
            var sliderGo = GameObject.Find("Panel/Beaufort 0-11 Slider");
            if (sliderGo == null) sliderGo = GameObject.Find("Beaufort 0-11 Slider");
            var rt = sliderGo != null ? sliderGo.GetComponent<RectTransform>() : null;
            if (rt == null)
            {
                report["verdict"] = "FAIL";
                report["reason"] = "beaufort slider not found";
                FinishVerify(report);
                yield break;
            }
            var corners = new Vector3[4];
            rt.GetWorldCorners(corners);
            var center = new Vector2(
                (corners[0].x + corners[3].x) * 0.5f,
                (corners[0].y + corners[1].y) * 0.5f);
            report["probePos"] = $"{(int)center.x},{(int)center.y}";

            // 运行时内省：判别"程序集陈旧（raycastTarget 仍 false）"vs"canvas 层射线失效"
            var bgT = sliderGo.transform.Find("Background");
            var bgImg = bgT != null ? bgT.GetComponent<Image>() : null;
            report["bgRaycastTarget"] = bgImg != null ? bgImg.raycastTarget.ToString() : "NO_BG";
            report["bgActiveInHierarchy"] = bgImg != null ? bgImg.gameObject.activeInHierarchy.ToString() : "NO_BG";
            report["screen"] = $"{Screen.width}x{Screen.height}";
            var scaler = canvas.GetComponent<CanvasScaler>();
            report["canvasScale"] = (scaler != null ? scaler.scaleFactor : -1f).ToString("F2");
            var allGraphics = canvas.GetComponentsInChildren<Graphic>(false);
            var raycastable = new List<string>();
            foreach (var g in allGraphics)
                if (g.raycastTarget && raycastable.Count < 12) raycastable.Add(g.name);
            report["graphicsTotal"] = allGraphics.Length;
            report["raycastableSample"] = raycastable;
            var gr = canvas.GetComponent<GraphicRaycaster>();
            if (gr != null)
            {
                var perCanvas = new List<RaycastResult>();
                gr.Raycast(new PointerEventData(es) { position = center }, perCanvas);
                report["graphicRaycasterHits"] = perCanvas.Count;
            }

            var ped = new PointerEventData(es) { position = center };
            var hits = new List<RaycastResult>();
            es.RaycastAll(ped, hits);
            var hitNames = new List<string>();
            foreach (var h in hits) hitNames.Add(h.gameObject.name);
            report["raycastHits"] = hits.Count;
            report["raycastHitNames"] = hitNames;

            // 合成点击：沿派发链找 IPointerClickHandler（TrackClickJump），直接执行
            bool clickFired = false;
            float before = 0f, after = 0f;
            if (hits.Count > 0)
            {
                var handlerGo = ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject);
                report["clickHandlerOn"] = handlerGo != null ? handlerGo.name : null;
                var controller = Object.FindFirstObjectByType<WeatherController>();
                if (handlerGo != null && controller != null)
                {
                    before = controller.beaufort;
                    ExecuteEvents.Execute<IPointerClickHandler>(handlerGo, ped,
                        (h, e) => h.OnPointerClick((PointerEventData)e));
                    after = controller.beaufort;
                    clickFired = Mathf.Abs(after - before) > 0.01f;
                }
            }
            report["clickChangedValue"] = clickFired;
            report["beaufortBefore"] = before;
            report["beaufortAfter"] = after;

            bool pass = hits.Count > 0 && clickFired && module is StandaloneInputModule && module.isActiveAndEnabled;
            report["verdict"] = pass ? "PASS" : "FAIL";
            FinishVerify(report);
        }

        static void FinishVerify(Dictionary<string, object> report)
        {
            SessionState.SetBool(k_VerifyStateKey, false);
            File.WriteAllText(k_ReportPath, MiniJson(report));
            Debug.Log($"[Sango.M1.verify] verdict={report["verdict"]} report={k_ReportPath}");
            EditorApplication.isPlaying = false;
        }

        static Canvas FindWeatherCanvas()
        {
            foreach (var c in Object.FindObjectsByType<Canvas>(FindObjectsSortMode.None))
                if (c.name == "WeatherCanvas") return c;
            return null;
        }

        // ── Capture ─────────────────────────────────────────────────────────────────────

        static IEnumerator CaptureSteps()
        {
            var dir = Path.Combine(Path.GetDirectoryName(Application.dataPath) ?? ".", "tmp/m1-shots");
            Directory.CreateDirectory(dir);

            WeatherController controller = null;
            for (int i = 0; i < 1200; i++)
            {
                controller = Object.FindFirstObjectByType<WeatherController>();
                if (Application.isPlaying && controller != null) break;
                yield return null;
            }
            if (controller == null)
            {
                Debug.Log("[Sango.M1.capture] FAIL: controller not found");
                SessionState.SetBool(k_CaptureStateKey, false);
                EditorApplication.isPlaying = false;
                yield break;
            }
            // 等面板建好（镜像生效）
            for (int i = 0; i < 600 && FindWeatherCanvas() == null; i++) yield return null;
            for (int i = 0; i < 30; i++) yield return null;

            // Beaufort 四档（固定机位，正午 + 默认云/雾）；谱档按映射表默认分配随级联动
            // （与 WeatherGUI.HandleHotkeys 一致，防重采证据与表格"谱档按行取"列矛盾）
            foreach (var b in new[] { 0f, 3f, 6f, 9f })
            {
                controller.timeOfDayHours = 12f;
                controller.cloudCover = 0.4f;
                controller.fogDistanceMeters = 3000f;
                yield return SetAndSettle(v => controller.beaufort = v, b);
                controller.spectrumTier = b <= 1f ? JsPmTier.Calm : b <= 4f ? JsPmTier.Moderate
                                        : b <= 7f ? JsPmTier.Rough : JsPmTier.VeryRough;
                yield return Shot($"{dir}/beaufort-b{b:0}.png");
            }

            // 昼夜对（B3）
            controller.beaufort = 3f;
            controller.cloudCover = 0.4f;
            controller.fogDistanceMeters = 3000f;
            yield return SetAndSettle(v => controller.timeOfDayHours = v, 12f);
            yield return Shot($"{dir}/time-noon.png");
            yield return SetAndSettle(v => controller.timeOfDayHours = v, 0f);
            yield return Shot($"{dir}/time-midnight.png");

            // 雾距对（B3 正午）
            controller.timeOfDayHours = 12f;
            yield return SetAndSettle(v => controller.fogDistanceMeters = v, 1000f);
            yield return Shot($"{dir}/fog-1000m.png");
            yield return SetAndSettle(v => controller.fogDistanceMeters = v, 8000f);
            yield return Shot($"{dir}/fog-8000m.png");

            Debug.Log($"[Sango.M1.capture] done -> {dir}");
            SessionState.SetBool(k_CaptureStateKey, false);
            EditorApplication.isPlaying = false;
        }

        // 写字段 → 等水面谱收敛（WeatherController.applyEveryFrame 每帧 Apply）
        static IEnumerator SetAndSettle(System.Action<float> set, float value)
        {
            set(value);
            for (int i = 0; i < 300; i++) yield return null; // ~3-5s 水面/天空过渡
        }

        static IEnumerator Shot(string path)
        {
            ScreenCapture.CaptureScreenshot(path, 1);
            for (int i = 0; i < 15; i++) yield return null; // 帧末才落盘，多等几帧
            Debug.Log($"[Sango.M1.capture] shot {Path.GetFileName(path)}");
        }

        // ── Standalone 播放器构建（Mono 后端：免 mac-il2cpp 模块下载）───────────────────
        // 编辑器 Game view 在本机晚间环境反复退化（背缓冲 2560x36 等），真播放器窗口
        // 不受编辑器 dock/topology 毒害，且是 M2 demo build 的彩排路径。
        [MenuItem("Sango/M1/Build Standalone Player (Mono)")]
        public static void BuildStandalonePlayer()
        {
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.runInBackground = true; // 播放器失焦（自动化采集）不停渲染
            var report = BuildPipeline.BuildPlayer(
                new[] { "Assets/Scenes/M1-Weather.unity" },
                "Builds/sango.app", // M2-F：demo 产物按 PLAN §5 M2 验收路径命名（双击可进四画面演示）
                BuildTarget.StandaloneOSX,
                BuildOptions.None);
            Debug.Log($"[Sango.M1] player build: {report.summary.result} " +
                      $"size={report.summary.totalSize / (1024 * 1024)}MB out={report.summary.outputPath}");
        }

        // M2-E1：遭遇场景独立播放器（单场景构建，scene 0 = M2E-Encounter）。与 M1 分开成 app：
        // M1 播放器流程（scene 0 = M1-Weather，历批验收路径）保持不变；M2-E 验收（orchestrator
        // 驱动）跑本 app——面板选模式 → Start → 会遇 → 轨迹/时间球/标签/比例尺 → Pause/2×。
        [MenuItem("Sango/M2/Build Encounter Standalone Player (Mono)")]
        public static void BuildEncounterStandalonePlayer()
        {
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.runInBackground = true;
            var report = BuildPipeline.BuildPlayer(
                new[] { "Assets/Scenes/M2E-Encounter.unity" },
                "Builds/M2E-Standalone.app",
                BuildTarget.StandaloneOSX,
                BuildOptions.None);
            Debug.Log($"[Sango.M2E] player build: {report.summary.result} " +
                      $"size={report.summary.totalSize / (1024 * 1024)}MB out={report.summary.outputPath}");
        }

        // ── 通用 ────────────────────────────────────────────────────────────────────────

        static string MiniJson(Dictionary<string, object> dict)
        {
            var sb = new StringBuilder("{");
            bool first = true;
            foreach (var kv in dict)
            {
                if (!first) sb.Append(",");
                first = false;
                sb.Append($"\"{kv.Key}\":");
                switch (kv.Value)
                {
                    case null: sb.Append("null"); break;
                    case string s: sb.Append($"\"{s}\""); break;
                    case bool b: sb.Append(b ? "true" : "false"); break;
                    case List<string> l:
                        sb.Append("[" + string.Join(",", l.ConvertAll(x => $"\"{x}\"")) + "]");
                        break;
                    default: sb.Append(kv.Value.ToString()); break;
                }
            }
            sb.Append("}");
            return sb.ToString();
        }
    }

    /// <summary>极简编辑器协程泵：EditorApplication.update 驱动 IEnumerator，null 即一 tick。</summary>
    internal class EditorPump
    {
        readonly IEnumerator m_Enumerator;
        public EditorPump(IEnumerator enumerator)
        {
            m_Enumerator = enumerator;
            EditorApplication.update += Pump;
        }
        void Pump()
        {
            if (!m_Enumerator.MoveNext())
                EditorApplication.update -= Pump;
        }
    }
}
