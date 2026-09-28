using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M3 缝钉子①投影纯函数测试（spec #86 Testing Decisions：DetectionOverlay projection math
    /// as pure functions）。钉死坐标系换算：viewport（0..1，y 上）→ 像素 xyxy（左上原点、y 下、
    /// 与 box_xyxy 同域）+ 外扩 + 出屏钳制 + 置信度标签 "1.0 (gt)"。
    /// 期望值来自独立几何事实（手worked 屏幕中心/边缘换算），不回声实现。
    /// </summary>
    public class OverlayProjectionTests
    {
        const int kW = 1000;
        const int kH = 500;
        const float k_PosTol = 1e-3f;

        [Test]
        public void CenteredViewportBox_MapsToCenteredPixelBox_NoVerticalFlipDrift()
        {
            // viewport 中央象限 (0.25..0.75)² → 像素 (250..750, 125..375)，中心 = 屏幕中心。
            var r = OverlayProjection.ViewportBoxToPixelRect(new Vector2(0.25f, 0.25f), new Vector2(0.75f, 0.75f), kW, kH, 0f);
            Assert.That(r.xMin, Is.EqualTo(250f).Within(k_PosTol));
            Assert.That(r.xMax, Is.EqualTo(750f).Within(k_PosTol));
            Assert.That(r.center.x, Is.EqualTo(kW * 0.5f).Within(k_PosTol));
            Assert.That(r.center.y, Is.EqualTo(kH * 0.5f).Within(k_PosTol), "居中框中心 = 屏幕中心（y 翻转无漂移）");
            Assert.That(r.yMin, Is.EqualTo(125f).Within(k_PosTol));
            Assert.That(r.yMax, Is.EqualTo(375f).Within(k_PosTol));
        }

        [Test]
        public void ViewportTopBox_MapsToPixelTop_YAxisFlipped()
        {
            // viewport 顶部条带 (y 0.9..1.0) → 像素顶部条带 (y 0..50)：y 轴翻转。
            var r = OverlayProjection.ViewportBoxToPixelRect(new Vector2(0f, 0.9f), new Vector2(1f, 1f), kW, kH, 0f);
            Assert.That(r.yMin, Is.EqualTo(0f).Within(k_PosTol));
            Assert.That(r.yMax, Is.EqualTo(50f).Within(k_PosTol), "viewport 上缘 → 像素 y≈0（GUI 左上原点）");
        }

        [Test]
        public void Margin_ExpandsBoxOnAllSides()
        {
            var tight = OverlayProjection.ViewportBoxToPixelRect(new Vector2(0.4f, 0.4f), new Vector2(0.6f, 0.6f), kW, kH, 0f);
            var padded = OverlayProjection.ViewportBoxToPixelRect(new Vector2(0.4f, 0.4f), new Vector2(0.6f, 0.6f), kW, kH, 10f);
            Assert.That(padded.xMin, Is.EqualTo(tight.xMin - 10f).Within(k_PosTol));
            Assert.That(padded.xMax, Is.EqualTo(tight.xMax + 10f).Within(k_PosTol));
            Assert.That(padded.yMin, Is.EqualTo(tight.yMin - 10f).Within(k_PosTol));
            Assert.That(padded.yMax, Is.EqualTo(tight.yMax + 10f).Within(k_PosTol));
        }

        [Test]
        public void OffscreenBox_ClampsToScreenBounds()
        {
            // 半出屏框（viewport x -0.1..0.1）→ 负像素钳到 0，不出负坐标框。
            var r = OverlayProjection.ViewportBoxToPixelRect(new Vector2(-0.1f, 0f), new Vector2(0.1f, 1f), kW, kH, 0f);
            Assert.That(r.xMin, Is.EqualTo(0f).Within(k_PosTol), "出屏部分钳到屏幕左缘");
            Assert.That(r.xMax, Is.EqualTo(100f).Within(k_PosTol));
            Assert.That(r.height, Is.EqualTo(kH).Within(k_PosTol), "全高框不因钳制缩水");
        }

        [Test]
        public void ConfidenceLabel_GroundTruthIsOnePointZeroGt()
        {
            Assert.That(OverlayProjection.ConfidenceLabel(1f, true), Is.EqualTo("1.0 (gt)"), "spec 演示标签字面量");
            Assert.That(OverlayProjection.ConfidenceLabel(0.87f, false), Is.EqualTo("0.87"));
            Assert.That(OverlayProjection.ConfidenceLabel(1f, false), Is.EqualTo("1.0"));
        }
    }
}
