using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M5 出片模式（DESIGN 2026-10-12-dt-frame-delivery-2k §2 M5②）的 HudVisibility 语义：
    /// FpsProbe 只静默 IMGUI（M0 采集继续）、DetectionOverlay 只退 visible（detection 命令继续）、
    /// HideNewOverlayCanvases 增量收晚建 Overlay canvas 且不动 ScreenSpaceCamera 产品叠层。
    /// HudVisibility/FpsProbe/DetectionOverlay 均在 Assembly-CSharp（Runtime 根无 asmdef），
    /// 经反射驱动（TwinBridgeClockGuardTests 先例）。
    /// </summary>
    public class TwinHudVisibilityTests
    {
        static readonly System.Type s_Hud = TestReflection.FindAssemblyCSharpType("Sango.HudVisibility");

        static void HudInvoke(string method) =>
            s_Hud.GetMethod(method, BindingFlags.Public | BindingFlags.Static).Invoke(null, null);

        static bool HudHidden => (bool)s_Hud.GetProperty("IsHidden", BindingFlags.Public | BindingFlags.Static).GetValue(null);

        [SetUp]
        public void SetUp() => HudInvoke("Restore"); // 静态捕获态隔离（前测残留防护）

        [TearDown]
        public void TearDown() => HudInvoke("Restore");

        [Test]
        public void Hide_SilencesFpsProbeOverlayButKeepsComponentEnabled()
        {
            var go = new GameObject("fps-probe");
            var probe = go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.FpsProbe"));
            var showOverlay = probe.GetType().GetField("showOverlay");
            showOverlay.SetValue(probe, true);
            try
            {
                HudInvoke("Hide");
                Assert.IsFalse((bool)showOverlay.GetValue(probe), "IMGUI 框应退场（showOverlay=false）");
                Assert.IsTrue(((Behaviour)probe).enabled, "组件不得禁用——M0 采集（[Sango.M0] 帧率行）必须继续");
                Assert.IsTrue(HudHidden);
                HudInvoke("Restore");
                Assert.IsTrue((bool)showOverlay.GetValue(probe), "Restore 精确还原 showOverlay");
            }
            finally { Object.DestroyImmediate(go); }
        }

        [Test]
        public void Hide_HidesDetectionOverlayBoxesButKeepsCommandSurface()
        {
            var go = new GameObject("detection-overlay");
            var overlay = go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.DetectionOverlay"));
            var visible = overlay.GetType().GetField("visible");
            visible.SetValue(overlay, true);
            try
            {
                HudInvoke("Hide");
                Assert.IsFalse((bool)visible.GetValue(overlay), "检测框应退场（visible=false）");
                Assert.IsTrue(((Behaviour)overlay).enabled, "组件保持 enabled——web detection 命令仍可点亮");
                HudInvoke("Restore");
                Assert.IsTrue((bool)visible.GetValue(overlay));
            }
            finally { Object.DestroyImmediate(go); }
        }

        [Test]
        public void HideNewOverlayCanvases_HidesLateOverlayCanvas_ExemptsNonOverlay()
        {
            var debug = new GameObject("debug-canvas");
            debug.AddComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay; // 裸建默认 WorldSpace
            HudInvoke("Hide");
            Assert.IsFalse(debug.activeSelf, "Hide 收走场景内 Overlay canvas");

            // 豁免分支（!= ScreenSpaceOverlay → skip）：EditMode 下 Canvas.renderMode 运行时 setter
            // 不可靠（SSCamera 赋值读回 Overlay、裸建读 WorldSpace），用裸建 canvas（WorldSpace，
            // 与产品 ScreenSpaceCamera 叠层 TwinSituationDisplay 走同一豁免分支）作测试内构造。
            var product = new GameObject("product-canvas");
            var productCanvas = product.AddComponent<Canvas>();
            var late = new GameObject("late-canvas");
            late.AddComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
            HudInvoke("HideNewOverlayCanvases");
            Assert.IsFalse(late.activeSelf, "晚建 Overlay canvas 应被增量补隐");
            Assert.IsTrue(product.activeSelf,
                $"非 Overlay（renderMode={productCanvas.renderMode}）产品叠层不得入隐藏面");

            HudInvoke("Restore");
            Assert.IsTrue(debug.activeSelf, "Restore 还原 Hide 捕获的 canvas");
            Assert.IsTrue(late.activeSelf, "Restore 还原增量补隐的 canvas（共用捕获清单）");
            Assert.IsTrue(product.activeSelf);

            Object.DestroyImmediate(debug);
            Object.DestroyImmediate(product);
            Object.DestroyImmediate(late);
        }

        [Test]
        public void HideNewOverlayCanvases_IsIdempotentPerCanvas()
        {
            var canvas = new GameObject("canvas");
            var canvasComponent = canvas.AddComponent<Canvas>();
            canvasComponent.renderMode = RenderMode.ScreenSpaceOverlay; // 裸 AddComponent 默认 WorldSpace,须显式 Overlay
            try
            {
                HudInvoke("HideNewOverlayCanvases");
                Assert.IsFalse(canvas.activeSelf);
                HudInvoke("Restore");
                Assert.IsTrue(canvas.activeSelf);
                // Restore 后再次补隐仍可捕获（捕获清单已清）
                HudInvoke("HideNewOverlayCanvases");
                Assert.IsFalse(canvas.activeSelf);
            }
            finally { UnityEngine.Object.DestroyImmediate(canvas); }
        }
    }
}
