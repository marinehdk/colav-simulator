using NUnit.Framework;
using Sango;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    /// <summary>
    /// M4 水面 decal 速度门限缝 EditMode 测试（spike）：纯核心 WaterDecalSpeedGate +
    /// 薄适配器 BoatWaterDecals.ApplySpeed，无场景/水面（先例 WaypointKinematicsTests）。
    /// 钉死的判定约定（M4 spike）：
    ///   低于阈值（静止/锢泊）→ 两块 decal 禁用、泡沫强度 0；
    ///   阈值以上 → 启用，泡沫/艏波幅度随航速线性爬坡到全强速度后钳 1。
    /// BoatWaterDecals 在 Assembly-CSharp（Runtime 根无 asmdef），经反射驱动
    /// （先例 WeatherFogOverrideTests.FindAssemblyCSharpType）；WaterDecal 断言走 HDRP 公开 API。
    /// </summary>
    public class WaterDecalSpeedGateTests
    {
        GameObject _boat, _bowGo, _wakeGo;

        [SetUp]
        public void SetUp()
        {
            _boat = new GameObject("gate-test-boat");
            _bowGo = new GameObject("bow");
            _bowGo.transform.SetParent(_boat.transform, false);
            _wakeGo = new GameObject("wake");
            _wakeGo.transform.SetParent(_boat.transform, false);
        }

        [TearDown]
        public void TearDown()
        {
            if (_boat != null) Object.DestroyImmediate(_boat);
        }

        // ── 纯核心：门限谓词（worked examples）──────────────────────────────────
        [Test]
        public void ShouldEnableDecals_BelowThreshold_False()
        {
            Assert.That(WaterDecalSpeedGate.ShouldEnableDecals(0f, 0.5f), Is.False, "静止必须禁用");
            Assert.That(WaterDecalSpeedGate.ShouldEnableDecals(0.49f, 0.5f), Is.False, "0.49 m/s 仍低于 0.5 阈值");
            Assert.That(WaterDecalSpeedGate.ShouldEnableDecals(-1f, 0.5f), Is.False, "倒车值同禁用（防御）");
        }

        [Test]
        public void ShouldEnableDecals_AtOrAboveThreshold_True()
        {
            Assert.That(WaterDecalSpeedGate.ShouldEnableDecals(0.5f, 0.5f), Is.True, "恰在阈值不算低于阈值");
            Assert.That(WaterDecalSpeedGate.ShouldEnableDecals(5f, 0.5f), Is.True, "巡航 5 m/s 启用");
        }

        // ── 纯核心：泡沫强度爬坡 ────────────────────────────────────────────────
        [Test]
        public void WakeFoamIntensity_BelowThresholdZero_AtFullSpeedOne()
        {
            Assert.That(WaterDecalSpeedGate.WakeFoamIntensity(0f, 0.5f, 5f), Is.EqualTo(0f), "静止零泡沫");
            Assert.That(WaterDecalSpeedGate.WakeFoamIntensity(0.5f, 0.5f, 5f), Is.EqualTo(0f), "阈值点上仍 0（爬坡从阈值以上开始）");
            Assert.That(WaterDecalSpeedGate.WakeFoamIntensity(5f, 0.5f, 5f), Is.EqualTo(1f), "全强速度恰为 1");
            Assert.That(WaterDecalSpeedGate.WakeFoamIntensity(9f, 0.5f, 5f), Is.EqualTo(1f), "超过全强钳 1");
        }

        [Test]
        public void WakeFoamIntensity_MidpointIsHalf()
        {
            // [0.5, 5] 中点 = 2.75 m/s → 0.5（独立算术事实，不回声实现）
            Assert.That(WaterDecalSpeedGate.WakeFoamIntensity(2.75f, 0.5f, 5f), Is.EqualTo(0.5f).Within(1e-5f));
        }

        [Test]
        public void WakeFoamIntensity_DegenerateSpan_StepAboveThreshold()
        {
            // fullSpeed ≤ threshold：阈值以上阶跃全强（不除零）
            Assert.That(WaterDecalSpeedGate.WakeFoamIntensity(0.4f, 0.5f, 0.5f), Is.EqualTo(0f));
            Assert.That(WaterDecalSpeedGate.WakeFoamIntensity(0.6f, 0.5f, 0.5f), Is.EqualTo(1f));
        }

        // ── 适配器薄壳：ApplySpeed 驱动两块 decal ────────────────────────────────
        [Test]
        public void ApplySpeed_MooredDisablesBothDecals()
        {
            var (adapter, bow, wake) = CreateWired();
            InvokeApplySpeed(adapter, 0f);
            Assert.That(bow.enabled, Is.False, "静止时艏波 decal 禁用");
            Assert.That(wake.enabled, Is.False, "静止时尾迹 decal 禁用");
            Assert.That(wake.surfaceFoamDimmer, Is.EqualTo(0f), "静止泡沫 dimmer 0");
        }

        [Test]
        public void ApplySpeed_CruiseEnablesAndScalesBySpeed()
        {
            var (adapter, bow, wake) = CreateWired(0.4f);
            InvokeApplySpeed(adapter, 5f);
            Assert.That(bow.enabled, Is.True, "巡航时艏波 decal 启用");
            Assert.That(wake.enabled, Is.True, "巡航时尾迹 decal 启用");
            Assert.That(bow.amplitude, Is.EqualTo(0.4f).Within(1e-5f), "全强航速艏波幅度 = 基准 0.4 m");
            Assert.That(wake.surfaceFoamDimmer, Is.EqualTo(1f), "全强航速泡沫 dimmer 1");

            InvokeApplySpeed(adapter, 2.75f); // 中点 → 幅度/泡沫减半
            Assert.That(bow.amplitude, Is.EqualTo(0.2f).Within(1e-5f), "中点航速艏波幅度减半");
            Assert.That(wake.surfaceFoamDimmer, Is.EqualTo(0.5f).Within(1e-5f), "中点航速泡沫 dimmer 0.5");
        }

        [Test]
        public void ApplySpeed_NullDecals_NoThrow()
        {
            // 编目缺失/构建器没接上的防御路径：空引用不抛
            var adapterType = FindAssemblyCSharpType("Sango.BoatWaterDecals");
            var adapterGo = new GameObject("gate-test-adapter-bare");
            var adapter = (MonoBehaviour)adapterGo.AddComponent(adapterType);
            Assert.DoesNotThrow(() => InvokeApplySpeed(adapter, 5f));
            Object.DestroyImmediate(adapterGo);
        }

#pragma warning disable IDE0051 // 适配器字段名反射查（编译期不可见）
        (MonoBehaviour adapter, WaterDecal bow, WaterDecal wake) CreateWired(float bowAmp = 0.4f)
        {
            var adapterType = FindAssemblyCSharpType("Sango.BoatWaterDecals");
            var adapterComp = (MonoBehaviour)_boat.AddComponent(adapterType);
            adapterType.GetField("bowDecal").SetValue(adapterComp, _bowGo.AddComponent<WaterDecal>());
            adapterType.GetField("wakeDecal").SetValue(adapterComp, _wakeGo.AddComponent<WaterDecal>());
            adapterType.GetField("bowAmplitudeM").SetValue(adapterComp, bowAmp);
            var bow = _bowGo.GetComponent<WaterDecal>();
            var wake = _wakeGo.GetComponent<WaterDecal>();
            bow.enabled = true;
            wake.enabled = true; // 预置启用，验证禁用路径会真关
            return (adapterComp, bow, wake);
        }

        static void InvokeApplySpeed(MonoBehaviour adapter, float speedMps)
        {
            adapter.GetType().GetMethod("ApplySpeed").Invoke(adapter, new object[] { speedMps });
        }
#pragma warning restore IDE0051

        static System.Type FindAssemblyCSharpType(string fullName)
        {
            foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
            {
                if (asm.GetName().Name != "Assembly-CSharp") continue;
                var t = asm.GetType(fullName);
                Assert.That(t, Is.Not.Null, $"Assembly-CSharp 缺类型 {fullName}");
                return t;
            }
            Assert.Fail("Assembly-CSharp 程序集未加载");
            return null;
        }
    }
}
