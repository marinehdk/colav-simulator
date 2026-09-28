using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Sango
{
    /// <summary>
    /// 四个运行时构建 UGUI 面板（WeatherGUI / EncounterPanel / SimulationPanel /
    /// AutonomousControlPanel）逐字重复的静态小件收编（第四份拷贝时挂账，本次偿还）。
    /// 只收编四处完全同构的函数；布局/行为耦合的构建函数（CreateLabel 绑各面板 _font、
    /// CreateSlider/CreateDropdown/CreateButton 尺寸与行为各异——TrackClickJump、
    /// 行高 30vs34 等）仍留各自面板，不做参数化合并。各面板经 `using static` 引用，
    /// 调用点零改动、行为零变化。落位 Assembly-CSharp：四个使用方全在该程序集
    /// （Assets/Scripts/Runtime/ 无 asmdef 覆盖），Sango.Vessels 是仿真数学程序集不放 UI。
    /// </summary>
    public static class UiBuildHelpers
    {
        // Unity 6000 内置字体资源名 LegacyRuntime.ttf（Arial.ttf 已于 2022+ 移除，留兜底）。
        public static Font LoadBuiltinFont()
        {
            Font f = null;
            try { f = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { }
            if (f == null) { try { f = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { } }
            return f;
        }

        public static void EnsureEventSystem()
        {
            if (EventSystem.current != null) return;
            // StandaloneInputModule 在 com.unity.ugui 包内（Runtime/UGUI/EventSystem/InputModules/）；
            // 工程未装 com.unity.inputsystem，走旧输入模块即可。
            new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
        }

        public static RectTransform NewRect(string name, Transform parent)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            return rt;
        }

        public static Image NewImage(string name, Transform parent, Color color)
        {
            var rt = NewRect(name, parent);
            var img = rt.gameObject.AddComponent<Image>();
            img.color = color; // 无 sprite：纯色矩形
            // raycastTarget 必须开：EventSystem 射线命中 raycastable Graphic 才派发指针事件，
            // 滑条 Background/Fill/Handle 全经此处创建，全关 = 滑条对鼠标完全失聪（M1-C UGUI 事故根因）
            img.raycastTarget = true;
            return img;
        }

        public static void Stretch(RectTransform rt, float left, float top, float right, float bottom)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(left, bottom);
            rt.offsetMax = new Vector2(right, -top);
        }
    }
}
