using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M8-B HUD 集中隐藏（出片路径 + H 热键共用同一实现，M8-C 材料条件"HUD 全隐"——
    /// M7 修复批披露：Overlook 构图下 PP 天际线被 SIMULATION 面板遮挡）。覆盖三类 HUD：
    /// ① 全部激活 ScreenSpaceOverlay Canvas 整树 inactive（WeatherCanvas/SimulationCanvas/
    ///    AutonomousCanvas/RadarCanvas/EncounterCanvas 等，建 canvas 的组件 Update 均在父对象上，
    ///    失活 canvas 不影响热键继续响应）；② IMGUI 叠层组件禁用（FpsProbe 常显框、
    ///    DetectionOverlay B 键框）；③ VectorArrows 世界空间箭头（show=false，下一 Update 收树）。
    /// 捕获-恢复制：Hide() 记录既有状态，Restore() 精确还原（先前已失活的对象不会被误恢复）。
    /// Recorder 路径由 M8RecordingHost 启录前 Hide、StopRecording 后 Restore 强制走此路径；
    /// 交互路径 = H 键（WeatherGUI.HandleHotkeys 消费；键位账本 2026-09-29 全仓 grep
    /// Input.GetKeyDown 复核：0-9/T/F/N/L/G/V/B/C/A/P/Q/E/Z/X/Space/R/±,./Enter(+keypad) 已占，H 空闲）。
    /// </summary>
    public static class HudVisibility
    {
        static readonly List<GameObject> s_HiddenCanvasObjects = new List<GameObject>();
        static readonly List<Behaviour> s_DisabledBehaviours = new List<Behaviour>();
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
                if (probes[i].enabled)
                {
                    s_DisabledBehaviours.Add(probes[i]);
                    probes[i].enabled = false; // IMGUI OnGUI 随组件禁用停止绘制
                }
            }

            var detections = Object.FindObjectsByType<DetectionOverlay>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            for (int i = 0; i < detections.Length; i++)
            {
                if (detections[i].enabled)
                {
                    s_DisabledBehaviours.Add(detections[i]);
                    detections[i].enabled = false;
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

            for (int i = 0; i < s_DisabledBehaviours.Count; i++)
            {
                if (s_DisabledBehaviours[i] != null) s_DisabledBehaviours[i].enabled = true;
            }
            s_DisabledBehaviours.Clear();

            for (int i = 0; i < s_ArrowsShown.Count; i++)
            {
                if (s_ArrowsShown[i] != null) s_ArrowsShown[i].show = true;
            }
            s_ArrowsShown.Clear();
        }

        /// <summary>H 键入口：隐藏态则还原，否则隐藏。</summary>
        public static void Toggle()
        {
            if (IsHidden) Restore();
            else Hide();
        }
    }
}
