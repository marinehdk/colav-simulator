using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace Sango.Editor
{
    /// <summary>
    /// M2-B 浮力查询开销采样（spec #81 perf 证据）：batchmode 进 Play，10 s 窗口每 1 s 采一次
    /// VesselBuoyancy 帧级静态统计（查询数/失败/耗时）与各船实例姿态，汇总一行落 Console 后退 Play。
    /// 查询数是静态量与海况无关；耗时用于对照 M0 锚点（144 q/frame ≈ 0.42 ms，见 m0-notes.md §2）。
    /// batchmode: -executeMethod Sango.Editor.BuoyancyPerfProbe.RunSample（跑完自行 Exit(0)）。
    /// 活跃标志走 SessionState：进/退 Play 各有域重载，普通静态会被抹掉。
    /// </summary>
    [InitializeOnLoad]
    public static class BuoyancyPerfProbe
    {
        const string k_ScenePath = "Assets/Scenes/M1-Weather.unity";
        const string k_ActiveKey = "Sango.BuoyancyPerfProbe.Active";
        const float k_WindowSeconds = 10f;
        const float k_SampleIntervalSeconds = 1f;

        static double s_PlayStart;
        static double s_NextSample;
        readonly static List<string> s_Samples = new List<string>();

        static BuoyancyPerfProbe()
        {
            // 域重载会清静态订阅（进/退 Play 各一次），InitializeOnLoad 静态构造里重挂。
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
            EditorApplication.update += OnUpdate;
        }

        [MenuItem("Sango/M2/Buoyancy Perf Sample (10 s)")]
        public static void RunSample()
        {
            SessionState.SetBool(k_ActiveKey, true);
            s_Samples.Clear();
            EditorApplication.OpenScene(k_ScenePath);
            EditorApplication.EnterPlaymode();
        }

        static void OnPlayModeChanged(PlayModeStateChange state)
        {
            if (!SessionState.GetBool(k_ActiveKey, false)) return;
            if (state == PlayModeStateChange.EnteredPlayMode)
            {
                s_PlayStart = EditorApplication.timeSinceStartup;
                s_NextSample = s_PlayStart + k_SampleIntervalSeconds;
            }
            else if (state == PlayModeStateChange.EnteredEditMode)
            {
                SessionState.EraseBool(k_ActiveKey);
                if (Application.isBatchMode) EditorApplication.Exit(0);
            }
        }

        static void OnUpdate()
        {
            if (!SessionState.GetBool(k_ActiveKey, false) || !EditorApplication.isPlaying) return;
            double now = EditorApplication.timeSinceStartup;
            if (now < s_NextSample) return;
            s_NextSample += k_SampleIntervalSeconds;

            var ships = Object.FindObjectsByType<VesselBuoyancy>(FindObjectsSortMode.None);
            var sb = new System.Text.StringBuilder($"[Sango.M2] t={now - s_PlayStart:F1}s queries={VesselBuoyancy.FrameQueries} failed={VesselBuoyancy.FrameFailedQueries} query_ms={VesselBuoyancy.FrameQueryMs:F3}");
            foreach (var ship in ships)
            {
                var a = ship.SmoothedAttitude;
                sb.Append($"  | {ship.name}: samples={ship.SampleCount} heave={a.x:F2}m roll={a.y:F2}° pitch={a.z:F2}° baseline={ship.DraftBaselineY:F2}m");
            }
            s_Samples.Add(sb.ToString());

            if (now - s_PlayStart >= k_WindowSeconds && Application.isBatchMode)
            {
                Debug.Log("[Sango.M2] buoyancy perf sample done:\n" + string.Join("\n", s_Samples));
                EditorApplication.ExitPlaymode(); // 回 EnteredEditMode 后 Exit(0)
            }
        }
    }
}
