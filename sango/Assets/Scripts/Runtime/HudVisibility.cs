using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M8-B HUD 集中隐藏（出片路径 + H 热键共用同一实现，M8-C 材料条件"HUD 全隐"——
    /// M7 修复批披露：Overlook 构图下 PP 天际线被 SIMULATION 面板遮挡）。覆盖三类 HUD：
    /// ① 全部激活 ScreenSpaceOverlay Canvas 整树 inactive（WeatherCanvas/SimulationCanvas/
    ///    AutonomousCanvas/RadarCanvas/EncounterCanvas 等，建 canvas 的组件 Update 均在父对象上，
    ///    失活 canvas 不影响热键继续响应）；② IMGUI 叠层静默（FpsProbe 常显框退 showOverlay、
    ///    DetectionOverlay 框退 visible——组件不禁用：M0 采集与 detection 命令继续工作，M5 出片
    ///    模式的验收仪器/交互面不随 HUD 一起死）；③ VectorArrows 世界空间箭头（show=false，
    ///    下一 Update 收树）。捕获-恢复制：Hide() 记录既有状态，Restore() 精确还原（先前已失活的
    ///    对象不会被误恢复）；HideNewOverlayCanvases() 增量收晚建 Overlay canvas。
    /// Recorder 路径由 M8RecordingHost 启录前 Hide、StopRecording 后 Restore 强制走此路径；
    /// M5 出片模式由 TwinHudHideCliFlag 自举（Hide + 周期增量补隐，见 TwinHudHideBootstrap）；
    /// 交互路径 = H 键（WeatherGUI.HandleHotkeys 消费；键位账本 2026-09-29 全仓 grep
    /// Input.GetKeyDown 复核：0-9/T/F/N/L/G/V/B/C/A/P/Q/E/Z/X/Space/R/±,./Enter(+keypad) 已占，H 空闲）。
    /// </summary>
    public static class HudVisibility
    {
        static readonly List<GameObject> s_HiddenCanvasObjects = new List<GameObject>();
        static readonly List<FpsProbe> s_SilencedProbes = new List<FpsProbe>();
        static readonly List<DetectionOverlay> s_HiddenDetectionOverlays = new List<DetectionOverlay>();
        static readonly List<VectorArrows> s_ArrowsShown = new List<VectorArrows>();

        /// <summary>当前是否处于隐藏态（热键 Toggle 与 Recorder 路径共读）。</summary>
        public static bool IsHidden { get; private set; }

        /// <summary>隐藏全部 HUD（幂等；重复调用无动作）。捕获既有状态供 Restore。</summary>
        public static void Hide()
        {
            if (IsHidden) return;
            IsHidden = true;

            var canvases = Object.FindObjectsByType<Canvas>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            for (int i = 0; i < canvases.Length; i++)
            {
                var go = canvases[i].gameObject;
                if (go.activeInHierarchy)
                {
                    s_HiddenCanvasObjects.Add(go);
                    go.SetActive(false);
                }
            }

            var probes = Object.FindObjectsByType<FpsProbe>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            for (int i = 0; i < probes.Length; i++)
            {
                if (probes[i].showOverlay)
                {
                    s_SilencedProbes.Add(probes[i]);
                    probes[i].showOverlay = false; // 仅退 IMGUI 框；M0 采集（LateUpdate+jsonl）继续——
                    // M5 出片模式的验收仪器依赖 [Sango.M0] 帧率行，不能随 HUD 一起静默。
                }
            }

            var detections = Object.FindObjectsByType<DetectionOverlay>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            for (int i = 0; i < detections.Length; i++)
            {
                if (detections[i].visible)
                {
                    s_HiddenDetectionOverlays.Add(detections[i]);
                    detections[i].visible = false; // 组件保持 enabled：键轮询/真值取用继续，且 M5
                    // 出片模式下 web 的 detection 命令仍可点亮（用户要的就是入画框）。
                }
            }

            var arrowsList = Object.FindObjectsByType<VectorArrows>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            for (int i = 0; i < arrowsList.Length; i++)
            {
                if (arrowsList[i].show)
                {
                    s_ArrowsShown.Add(arrowsList[i]);
                    arrowsList[i].show = false; // 组件 Update 下一帧收箭头树（录帧始于 Hide 之后 ≥1 帧，不入画）
                }
            }
        }

        /// <summary>还原 Hide 捕获的 HUD 状态（幂等；无捕获时不动作）。</summary>
        public static void Restore()
        {
            if (!IsHidden) return;
            IsHidden = false;

            for (int i = 0; i < s_HiddenCanvasObjects.Count; i++)
            {
                if (s_HiddenCanvasObjects[i] != null) s_HiddenCanvasObjects[i].SetActive(true);
            }
            s_HiddenCanvasObjects.Clear();

            for (int i = 0; i < s_SilencedProbes.Count; i++)
            {
                if (s_SilencedProbes[i] != null) s_SilencedProbes[i].showOverlay = true;
            }
            s_SilencedProbes.Clear();

            for (int i = 0; i < s_HiddenDetectionOverlays.Count; i++)
            {
                if (s_HiddenDetectionOverlays[i] != null) s_HiddenDetectionOverlays[i].visible = true;
            }
            s_HiddenDetectionOverlays.Clear();

            for (int i = 0; i < s_ArrowsShown.Count; i++)
            {
                if (s_ArrowsShown[i] != null) s_ArrowsShown[i].show = true;
            }
            s_ArrowsShown.Clear();
        }

        /// <summary>
        /// 增量补隐 Hide 之后新激活的 ScreenSpaceOverlay canvas（M5 出片自举：TwinSituationDisplay
        /// 等运行期才建的 HUD 面板兜底）。只收 Overlay 模式——ScreenSpaceCamera/World 模式不入此列
        /// （DT frame identity 等产品叠层随场景语义保留，且 ScreenSpaceCamera 在 legacy RT 采集下
        /// 本就入画，两路由画面语义一致）。幂等；与 Hide 共用捕获清单，Restore 统一还原。
        /// </summary>
        public static void HideNewOverlayCanvases()
        {
            IsHidden = true; // 与 Hide 共态:Restore 统一还原(H 键 Toggle 语义不受 Hide/HidNew 调用序影响)
            var canvases = Object.FindObjectsByType<Canvas>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            for (int i = 0; i < canvases.Length; i++)
            {
                var canvas = canvases[i];
                if (canvas.renderMode != RenderMode.ScreenSpaceOverlay || !canvas.gameObject.activeInHierarchy) continue;
                if (s_HiddenCanvasObjects.Contains(canvas.gameObject)) continue;
                s_HiddenCanvasObjects.Add(canvas.gameObject);
                canvas.gameObject.SetActive(false);
            }
        }

        /// <summary>H 键入口：隐藏态则还原，否则隐藏。</summary>
        public static void Toggle()
        {
            if (IsHidden) Restore();
            else Hide();
        }
    }

    /// <summary>
    /// M5 出片模式自举（SangoSeamConfig.TwinHudHideCliFlag）：场景加载后全量 Hide + 每 2s
    /// 增量补隐晚建 Overlay canvas（TwinSituationDisplay 等运行期创建的面板）。H 键仍可还原。
    /// </summary>
    public static class TwinHudHideBootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            if (System.Array.IndexOf(System.Environment.GetCommandLineArgs(), SangoSeamConfig.TwinHudHideCliFlag) < 0) return;
            var host = new GameObject("Twin hud hide sweep (bootstrap)");
            host.AddComponent<TwinHudHideSweep>();
            Debug.Log("[Sango.TwinBridge] hud hide bootstrap via " + SangoSeamConfig.TwinHudHideCliFlag);
        }
    }

    /// <summary>出片模式的周期补隐宿主（首帧全量 Hide，其后每 2s HideNewOverlayCanvases）。</summary>
    public class TwinHudHideSweep : MonoBehaviour
    {
        float m_NextSweep = -1f;

        void Update()
        {
            if (m_NextSweep < 0f)
            {
                m_NextSweep = Time.unscaledTime + 2f;
                HudVisibility.Hide();
                return;
            }
            if (Time.unscaledTime < m_NextSweep) return;
            m_NextSweep = Time.unscaledTime + 2f;
            HudVisibility.HideNewOverlayCanvases();
        }
    }
}
