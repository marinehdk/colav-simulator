using System.Reflection;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Editor
{
    /// <summary>
    /// M0 复审强制补测的配置入口（m0-notes.md §3/§7 转办清单）：
    /// 1) 把当前 Quality 档显式绑定 SangoHDRP asset（档名如实记录——指名画质档的证据要求）；
    /// 2) 反射注册 Game 视图固定分辨率 "Sango 1440p"（2560x1440）并选中——Unity 无公开
    ///    GameViewSize API（GameViewSizes/GameViewSize 均 internal，UnityEditor.dll），
    ///    反射路径为社区通行做法；失败则回退 GUI 手选并如实记录。
    /// 菜单 Sango/M1/Setup Quality & GameView，或 batch -executeMethod Sango.Editor.M1QualitySetup.Run。
    /// </summary>
    public static class M1QualitySetup
    {
        [MenuItem("Sango/M1/Setup Quality & GameView")]
        public static void Run() => RunInternal();

        public static void RunInternal()
        {
            BindQualitySlot();
            RegisterGameViewSize();
        }

        static void BindQualitySlot()
        {
            var names = QualitySettings.names;
            var log = $"[Sango.M1] Quality slots: [{string.Join(", ", names)}], active={QualitySettings.GetQualityLevel()}";
            var hdrp = GraphicsSettings.defaultRenderPipeline as HDRenderPipelineAsset;
            if (hdrp == null)
            {
                hdrp = AssetDatabase.LoadAssetAtPath<HDRenderPipelineAsset>("Assets/Settings/SangoHDRP.asset");
            }
            if (hdrp == null)
            {
                Debug.LogError("[Sango.M1] no HDRP asset found at default pipeline or Assets/Settings/SangoHDRP.asset");
                return;
            }
            // 当前 active 档显式绑定 HDRP asset（null 虽也跟随 default，但复审要求"指名画质档"成立：
            // 档名 + 显式引用都要落在 ProjectSettings 里）
            QualitySettings.renderPipeline = hdrp;
            EditorUtility.SetDirty(hdrp);
            var current = names.Length > 0 ? names[QualitySettings.GetQualityLevel()] : "?";
            Debug.Log(log + $" — bound '{current}' -> {hdrp.name} (water={hdrp.currentPlatformRenderPipelineSettings.supportWater})");
        }

        static void RegisterGameViewSize()
        {
            const int w = 2560, h = 1440;
            const string label = "Sango 1440p";
            try
            {
                var asm = typeof(UnityEditor.Editor).Assembly;
                var gvSizesType = asm.GetType("UnityEditor.GameViewSizes");
                var gameViewSizeType = asm.GetType("UnityEditor.GameViewSize");
                var sizeTypeType = asm.GetType("UnityEditor.GameViewSizeType");
                if (gvSizesType == null || gameViewSizeType == null || sizeTypeType == null)
                {
                    Debug.LogError("[Sango.M1] GameViewSizes internal types not found; fall back to GUI selection");
                    return;
                }

                var instanceProp = gvSizesType.GetProperty("instance", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                object instance = instanceProp?.GetValue(null);
                string diag = $"instance(prop)={instance != null}";
                if (instance == null)
                {
                    foreach (var f in gvSizesType.GetFields(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
                        diag += $" | field:{f.Name}({f.FieldType.Name})";
                    foreach (var p in gvSizesType.GetProperties(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
                        diag += $" | prop:{p.Name}({p.PropertyType.Name})";
                    Debug.Log("[Sango.M1] GameViewSizes diag: " + diag);
                    return;
                }

                // currentGroup (GameViewSizeGroupBase) — Standalone 组即桌面档
                var group = gvSizesType
                    .GetProperty("currentGroup", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                    ?.GetValue(instance);
                if (group == null) { Debug.LogError("[Sango.M1] GameViewSizes.currentGroup null"); return; }

                var groupType = group.GetType();
                var bsizes = groupType.GetField("m_Custom", BindingFlags.NonPublic | BindingFlags.Instance)
                             ?? groupType.GetField("s_Custom", BindingFlags.NonPublic | BindingFlags.Instance);
                var existing = bsizes?.GetValue(group) as System.Collections.IEnumerable;
                int idx = 0, found = -1, count = 0;
                if (existing != null)
                {
                    foreach (var s in existing)
                    {
                        var sLabel = s.GetType().GetProperty("displayText", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(s) as string
                                     ?? s.GetType().BaseType?.GetProperty("displayText", BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(s) as string;
                        if (sLabel != null && sLabel.Contains(label)) { found = idx; }
                        idx++; count++;
                    }
                }

                if (found < 0)
                {
                    // new GameViewSize(GameViewSizeType.FixedResolution, w, h, label)
                    var sizeTypeEnum = System.Enum.GetValues(sizeTypeType); // [0]=AspectRatio [1]=FixedResolution 常见排序，按名字取
                    object fixedRes = null;
                    foreach (var v in sizeTypeEnum) if (v.ToString() == "FixedResolution") fixedRes = v;
                    var sizeObj = System.Activator.CreateInstance(gameViewSizeType, fixedRes, w, h, label);
                    groupType.GetMethod("AddCustomSize", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                             ?.Invoke(group, new[] { sizeObj });
                    found = count;
                    Debug.Log($"[Sango.M1] GameView size added: {label} ({w}x{h}) at index {found}");
                }
                else
                {
                    Debug.Log($"[Sango.M1] GameView size already present: {label} at index {found}");
                }

                // 选中它
                gvSizesType.GetProperty("selectedSizeIndex", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                    ?.SetValue(instance, found);
                Debug.Log($"[Sango.M1] GameView size selected: {label}");
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[Sango.M1] GameView size registration failed (GUI fallback): {e.GetType().Name} {e.Message}");
            }
        }
    }
}
