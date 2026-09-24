using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-D 航行灯纯核心缝 EditMode 测试（spec #83 Testing Decisions）：只打
    /// NavigationLightsCore 两个纯函数，合成数据，无场景/灯/渲染。
    /// 钉死的约定（与 WeatherController.ApplySun 时刻语义、编目 prefab 艏向 +Z 一致）：
    ///   时刻 h∈[0,24]，太阳仰角 = 60·cos(π(h−12)/12)（钳 −18° 前的原始值）；
    ///   仰角 ≤ 0（地平线上恰好 0° 时直射日光已为 0，归夜侧）= 开灯；
    ///   本地空间 +Z = 艏、+X = 右舷（星板）、−X = 左舷（-port）、+Y = 上。
    /// 反字面回声纪律：期望值全部是手算 worked example（独立几何/三角事实），
    /// 不回声实现里的分数常量。
    /// </summary>
    public class NavigationLightsCoreTests
    {
        const float k_Tol = 1e-4f;

        // ── 缝 a：时刻 → 明灭 ─────────────────────────────────────────────────────────

        [Test]
        public void IsLightsOn_Noon_ReturnsOff()
        {
            Assert.That(NavigationLightsCore.IsLightsOn(12f), Is.False,
                "noon (sun 60 deg up) must be day: lights off");
        }

        [Test]
        public void IsLightsOn_SliderEnds_Midnight_ReturnsOn()
        {
            // 滑条两端 0 与 24 是同一 midnight：仰角 cos(±π) = −1 → −60° 深夜。
            Assert.That(NavigationLightsCore.IsLightsOn(0f), Is.True, "slider min 0h = midnight");
            Assert.That(NavigationLightsCore.IsLightsOn(24f), Is.True, "slider max 24h = midnight");
        }

        [Test]
        public void IsLightsOn_DuskPreset17h30_ReturnsOff()
        {
            // T 循环的"傍晚"档 17.5h：仰角 60·cos(82.5°) ≈ +7.8°，日落前（COLREGs 日落点灯）。
            Assert.That(NavigationLightsCore.IsLightsOn(17.5f), Is.False,
                "17.5h sun is ~7.8 deg above horizon: before sunset, lights still off");
        }

        [Test]
        public void IsLightsOn_HorizonBoundaries6hAnd18h_ReturnsOn()
        {
            // 6h/18h 仰角恰 0°：直射日光贡献为 0（WeatherController 强度 = 0.1 lux 地板），按夜侧开灯。
            Assert.That(NavigationLightsCore.IsLightsOn(6f), Is.True, "6h sun exactly on horizon = night side of threshold");
            Assert.That(NavigationLightsCore.IsLightsOn(18f), Is.True, "18h sun exactly on horizon = night side of threshold");
        }

        [Test]
        public void IsLightsOn_DayWindowInterior_ReturnsOff()
        {
            // 昼窗内部抽样：仰角 +1.6° / +60° / +1.6°。
            Assert.That(NavigationLightsCore.IsLightsOn(6.1f), Is.False, "6.1h sun ~1.6 deg up");
            Assert.That(NavigationLightsCore.IsLightsOn(17.9f), Is.False, "17.9h sun ~1.6 deg up");
        }

        [Test]
        public void IsLightsOn_NightOutsideDayWindow_ReturnsOn()
        {
            // 昼窗两侧抽样：仰角 −1.6° / −58.4°。
            Assert.That(NavigationLightsCore.IsLightsOn(5.9f), Is.True, "5.9h sun ~1.6 deg below horizon");
            Assert.That(NavigationLightsCore.IsLightsOn(18.1f), Is.True, "18.1h sun ~1.6 deg below horizon");
            Assert.That(NavigationLightsCore.IsLightsOn(1f), Is.True);
            Assert.That(NavigationLightsCore.IsLightsOn(23f), Is.True);
        }

        // ── 缝 b：hull 包围盒 → 锚点 ──────────────────────────────────────────────────
        // Worked example A：对称包围盒 center(0,5,0) size(10,10,60) → 半宽5/半高5/半长30。
        // 手算期望：port(−5, 7.5, 9) starboard(5, 7.5, 9) masthead(0, 10, 12) stern(0, 7.5, −30)。

        static Bounds ExampleA() => new Bounds(new Vector3(0f, 5f, 0f), new Vector3(10f, 10f, 60f));
        static Bounds ExampleB() => new Bounds(new Vector3(2f, 3f, -4f), new Vector3(8f, 6f, 40f));

        [Test]
        public void DeriveAnchors_Sidelights_AtExtremeSides_PortLeft_StarboardRight()
        {
            // 舷灯贴两舷极值、同高同纵位；port 在 −X（艏向 +Z 时的场景左侧），starboard 在 +X。
            var l = NavigationLightsCore.DeriveAnchors(ExampleA());
            Assert.That(l.PortSidelight.x, Is.EqualTo(-5f).Within(k_Tol), "port sidelight at -X extreme (left with bow +Z)");
            Assert.That(l.StarboardSidelight.x, Is.EqualTo(5f).Within(k_Tol), "starboard sidelight at +X extreme (right with bow +Z)");
            Assert.That(l.PortSidelight.y, Is.EqualTo(l.StarboardSidelight.y).Within(k_Tol), "sidelights share deck height");
            Assert.That(l.PortSidelight.z, Is.EqualTo(l.StarboardSidelight.z).Within(k_Tol), "sidelights share fore-aft station");
            Assert.That(l.PortSidelight.y, Is.EqualTo(7.5f).Within(k_Tol), "worked example: deck height = center + half height");
        }

        [Test]
        public void DeriveAnchors_Masthead_Centerline_Topmost_ForwardOfSidelights()
        {
            var l = NavigationLightsCore.DeriveAnchors(ExampleA());
            Assert.That(l.Masthead.x, Is.EqualTo(0f).Within(k_Tol), "masthead on centerline");
            Assert.That(l.Masthead.y, Is.EqualTo(10f).Within(k_Tol), "masthead at hull top (worked example)");
            Assert.That(l.Masthead.z, Is.EqualTo(12f).Within(k_Tol), "masthead over bow region (worked example)");
            Assert.That(l.Masthead.y, Is.GreaterThan(l.PortSidelight.y), "masthead elevated above sidelights");
            Assert.That(l.Masthead.z, Is.GreaterThan(l.PortSidelight.z), "masthead forward of sidelight station");
        }

        [Test]
        public void DeriveAnchors_SternLight_Centerline_AftExtreme()
        {
            var l = NavigationLightsCore.DeriveAnchors(ExampleA());
            Assert.That(l.SternLight.x, Is.EqualTo(0f).Within(k_Tol), "stern light on centerline");
            Assert.That(l.SternLight.z, Is.EqualTo(-30f).Within(k_Tol), "stern light at aft extreme (worked example)");
            Assert.That(l.SternLight.z, Is.LessThan(l.PortSidelight.z), "stern aft of sidelights");
            Assert.That(l.SternLight.y, Is.EqualTo(7.5f).Within(k_Tol), "stern light at deck height, not keel");
        }

        [Test]
        public void DeriveAnchors_OffCenterBounds_TracksCenterAndExtents()
        {
            // 非对称例 B center(2,3,−4) size(8,6,40)：期望 port(−2,4.5,2) starboard(6,4.5,2)
            // masthead(2,6,4) stern(2,4.5,−24) —— 布局随 center/extents 平移缩放，不设原点假设。
            var l = NavigationLightsCore.DeriveAnchors(ExampleB());
            // 逐分量断言：NUnit 的 Vector3 EqualTo.Within 走精确比较（epsilon 不逐分量生效），
            // 0.3f·20f 一类二进制分数必须用标量容差。
            Assert.That(l.PortSidelight.x, Is.EqualTo(-2f).Within(k_Tol));
            Assert.That(l.PortSidelight.y, Is.EqualTo(4.5f).Within(k_Tol));
            Assert.That(l.PortSidelight.z, Is.EqualTo(2f).Within(k_Tol));
            Assert.That(l.StarboardSidelight.x, Is.EqualTo(6f).Within(k_Tol));
            Assert.That(l.StarboardSidelight.y, Is.EqualTo(4.5f).Within(k_Tol));
            Assert.That(l.StarboardSidelight.z, Is.EqualTo(2f).Within(k_Tol));
            Assert.That(l.Masthead.x, Is.EqualTo(2f).Within(k_Tol));
            Assert.That(l.Masthead.y, Is.EqualTo(6f).Within(k_Tol));
            Assert.That(l.Masthead.z, Is.EqualTo(4f).Within(k_Tol));
            Assert.That(l.SternLight.x, Is.EqualTo(2f).Within(k_Tol));
            Assert.That(l.SternLight.y, Is.EqualTo(4.5f).Within(k_Tol));
            Assert.That(l.SternLight.z, Is.EqualTo(-24f).Within(k_Tol));
        }

        [Test]
        public void DeriveAnchors_ExtremeShips_KeepSideAttribution()
        {
            // 细长/扁平两个极端 hull：舷侧归性永不翻转（port 恒 −X、starboard 恒 +X、艉恒在艏之后）。
            var slender = NavigationLightsCore.DeriveAnchors(new Bounds(Vector3.zero, new Vector3(4f, 20f, 100f)));
            Assert.That(slender.PortSidelight.x, Is.LessThan(0f));
            Assert.That(slender.StarboardSidelight.x, Is.GreaterThan(0f));
            Assert.That(slender.SternLight.z, Is.LessThan(slender.Masthead.z));

            var stubby = NavigationLightsCore.DeriveAnchors(new Bounds(new Vector3(-7f, 1f, 3f), new Vector3(30f, 4f, 12f)));
            Assert.That(stubby.PortSidelight.x, Is.LessThan(0f));
            Assert.That(stubby.StarboardSidelight.x, Is.GreaterThan(0f));
            Assert.That(stubby.SternLight.z, Is.LessThan(stubby.Masthead.z));
        }
    }
}
