using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M6 review S3（2026-09-29）IMGUI 框锚缝测试：FpsProbe.ComputeBoxRect 纯函数
    /// （OnGUI 同源）。默认 TopLeft+margin(8,8) 必须逐像素复现 M1 原框 (8,8,560,116)；
    /// M6 用 BottomLeft 贴底，与 WeatherGUI 左上面板（anchored (20,-20)、380×640，
    /// WeatherGUI.cs:68-69 同源字面量）不再重叠。FpsProbe 在 Assembly-CSharp，经反射驱动。
    /// </summary>
    public class FpsProbeOverlayTests
    {
        static Rect ComputeBox(object anchor, Vector2 margin, float screenHeight)
        {
            var t = TestReflection.FindAssemblyCSharpType("Sango.FpsProbe");
            var anchorType = TestReflection.FindAssemblyCSharpType("Sango.FpsProbe+OverlayAnchor");
            var m = t.GetMethod("ComputeBoxRect", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static);
            return (Rect)m.Invoke(null, new[] { anchor, margin, screenHeight });
        }

        static object TopLeft => System.Enum.ToObject(TestReflection.FindAssemblyCSharpType("Sango.FpsProbe+OverlayAnchor"), 0);
        static object BottomLeft => System.Enum.ToObject(TestReflection.FindAssemblyCSharpType("Sango.FpsProbe+OverlayAnchor"), 1);

        [Test]
        public void ComputeBoxRect_DefaultTopLeft_IsM1LegacyRectPixelExact()
        {
            var r = ComputeBox(TopLeft, new Vector2(8f, 8f), 1440f);
            Assert.That(r, Is.EqualTo(new Rect(8f, 8f, 560f, 116f)), "默认锚 = M1 原框 (8,8,560,116) 逐像素不变（M1 零影响）");
        }

        [Test]
        public void ComputeBoxRect_BottomLeft_SticksToScreenBottomClearingWeatherGuiPanel()
        {
            // 闸门参考分辨率 1440p（M0 fps gate 口径）。
            var r = ComputeBox(BottomLeft, new Vector2(8f, 8f), 1440f);
            Assert.That(r.x, Is.EqualTo(8f).Within(0.01f));
            Assert.That(r.y, Is.EqualTo(1440f - 116f - 8f).Within(0.01f), "y = Screen.height − 框高 − 下边距（运行时取 Screen.height）");
            Assert.That(r.yMax, Is.EqualTo(1440f - 8f).Within(0.01f), "框底贴屏幕底边距 8 px");
            // WeatherGUI 面板纵向覆盖 ~[20, 660]（顶边距 20 + 高 640）；框顶 1316 在其下方 → 重叠消除。
            Assert.That(r.y, Is.GreaterThan(20f + 640f), "框顶在 WeatherGUI 面板底（~660）之下 = review S3 重叠消除");
        }
    }
}
