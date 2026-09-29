using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    /// <summary>
    /// M7-B 大气三档 WeatherController 侧 EditMode 测试（WeatherFogOverrideTests 同款反射
    /// 口径：WeatherController 在 Assembly-CSharp，测试 asmdef 不引用预定义程序集）。
    /// 覆盖：①默认档字段初始化器（HazyClear + 零补偿/不压暗/无雨）；②ApplyAtmosphereTier
    /// → AdvanceAtmosphereTransition(dt) 显式 dt 可测缝（Time.time 编辑器态不前进）；
    /// ③过渡完成后 Apply() 把 Fog.maxFogDistance 与 Exposure.compensation 以 .Override 口径
    /// 写进合成 Volume（HDRP 公开 API 断言）。
    /// </summary>
    public class M7BAtmosphereControllerTests
    {
        GameObject _volumeGo, _controllerGo;

        [TearDown]
        public void TearDown()
        {
            if (_controllerGo != null) Object.DestroyImmediate(_controllerGo);
            if (_volumeGo != null) Object.DestroyImmediate(_volumeGo);
        }

        (System.Type ctrlType, Component ctrl) MakeController()
        {
            var t = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            _controllerGo = new GameObject("m7b-test-controller");
            return (t, (Component)_controllerGo.AddComponent(t));
        }

        [Test]
        public void FieldInitializers_DefaultTierHazyClear_NoDimmingNoRain()
        {
            var (t, ctrl) = MakeController();
            var tier = t.GetField("atmosphereTier").GetValue(ctrl);
            Assert.That(System.Convert.ToInt32(tier), Is.EqualTo(0), "默认档 = HazyClear（浓霾晴）");
            Assert.That((float)t.GetField("exposureCompensationEv").GetValue(ctrl), Is.EqualTo(0f), "默认零补偿");
            Assert.That((float)t.GetField("sunDimFactor").GetValue(ctrl), Is.EqualTo(1f), "默认不压太阳");
            Assert.That((float)t.GetField("rainRate").GetValue(ctrl), Is.EqualTo(0f), "默认无雨");
            Assert.That((bool)t.GetProperty("AtmosphereTransitioning").GetValue(ctrl), Is.False,
                "初始无过渡（字段即当前值，首次 ApplyAtmosphereTier 才起动画）");
        }

        [Test]
        public void ApplyAtmosphereTier_Thunderstorm_TransitionsToPresetAndWritesOverrides()
        {
            var (t, ctrl) = MakeController();

            // 合成 Global Volume：Fog + Exposure（M6 profile 同款 override 组合）
            _volumeGo = new GameObject("m7b-test-volume");
            var volume = _volumeGo.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.sharedProfile = ScriptableObject.CreateInstance<VolumeProfile>();
            volume.sharedProfile.Add<Fog>();
            volume.sharedProfile.Add<Exposure>();
            t.GetField("globalVolume").SetValue(ctrl, volume);

            // 当前值 = 晴档（M6 海峡默认雾距 8000），切雷暴档
            t.GetField("fogDistanceMeters").SetValue(ctrl, 8000f);
            t.GetField("cloudCover").SetValue(ctrl, 0.35f);
            var tierType = t.GetField("atmosphereTier").FieldType; // Sango.M7BMath.AtmosphereTier
            t.GetField("atmosphereTier").SetValue(ctrl, System.Enum.ToObject(tierType, 2));

            t.GetMethod("ApplyAtmosphereTier").Invoke(ctrl, null);
            Assert.That((bool)t.GetProperty("AtmosphereTransitioning").GetValue(ctrl), Is.True, "切档后过渡进行中");
            Assert.That((float)t.GetField("fogDistanceMeters").GetValue(ctrl), Is.EqualTo(8000f),
                "过渡未推进前当前值不动（从当前值起 lerp）");

            bool still = true;
            int steps = 0;
            while (still && steps < 20)
            {
                still = (bool)t.GetMethod("AdvanceAtmosphereTransition").Invoke(ctrl, new object[] { 0.5f });
                steps++;
            }
            Assert.That(steps, Is.EqualTo(6), "3 s 过渡按 0.5 s 步进恰 6 步走完（第 6 步返回 false）");
            Assert.That((bool)t.GetProperty("AtmosphereTransitioning").GetValue(ctrl), Is.False, "过渡结束");

            float fog = (float)t.GetField("fogDistanceMeters").GetValue(ctrl);
            float cloud = (float)t.GetField("cloudCover").GetValue(ctrl);
            float ev = (float)t.GetField("exposureCompensationEv").GetValue(ctrl);
            float dim = (float)t.GetField("sunDimFactor").GetValue(ctrl);
            float rain = (float)t.GetField("rainRate").GetValue(ctrl);
            Assert.That(fog, Is.EqualTo(1500f).Within(0.5f), "雷暴档目标视程 1500 m");
            Assert.That(cloud, Is.EqualTo(0.95f).Within(0.005f), "雷暴档目标云量 0.95");
            Assert.That(ev, Is.EqualTo(-1.6f).Within(0.01f), "雷暴档目标补偿 −1.6 EV");
            Assert.That(dim, Is.EqualTo(0.30f).Within(0.005f), "雷暴档太阳 ×0.30");
            Assert.That(rain, Is.EqualTo(9000f).Within(1f), "雷暴档雨发射率");

            // 再推一帧：已结束不越界（当前值钉在目标）
            bool after = (bool)t.GetMethod("AdvanceAtmosphereTransition").Invoke(ctrl, new object[] { 1f });
            Assert.That(after, Is.False, "结束后 Advance 返回 false");
            Assert.That((float)t.GetField("fogDistanceMeters").GetValue(ctrl), Is.EqualTo(fog).Within(0.001f), "结束后当前值不再变化");

            // Apply()：Fog/Exposure 全部 .Override 口径写入（WeatherFogOverrideTests 同断言面）
            t.GetMethod("Apply").Invoke(ctrl, null);
            Assert.That(volume.profile.TryGet<Fog>(out var fogOverride), Is.True);
            Assert.That(fogOverride.maxFogDistance.overrideState, Is.True, "雾距 overrideState");
            Assert.That(fogOverride.maxFogDistance.value, Is.EqualTo(1500f).Within(0.5f), "雾距 = 过渡后的当前值");
            Assert.That(volume.profile.TryGet<Exposure>(out var exposure), Is.True);
            Assert.That(exposure.compensation.overrideState, Is.True, "曝光补偿 overrideState（HDRP 只认 overrideState）");
            Assert.That(exposure.compensation.value, Is.EqualTo(-1.6f).Within(0.01f), "曝光补偿 = 过渡后的当前值");
        }

        [Test]
        public void ApplyAtmosphereTier_HazyClearKeepsSunContract_UnchangedWhenFactorOne()
        {
            // 回归锚：sunDimFactor=1（晴档/默认）时 ApplySun 输出与 M1 旧契约一致；
            // M1 模型 h=12 → 仰角 60° → dayFactor=sin60°²=0.75 → 75000 lux 量级
            var (t, ctrl) = MakeController();
            var sunGo = new GameObject("m7b-test-sun");
            var light = sunGo.AddComponent<Light>();
            light.type = LightType.Directional;
            t.GetField("sunLight").SetValue(ctrl, light);
            t.GetField("timeOfDayHours").SetValue(ctrl, 12f); // 正午
            t.GetField("sunDimFactor").SetValue(ctrl, 1f);

            t.GetMethod("Apply").Invoke(ctrl, null);
            float dayFactor = Mathf.Pow(Mathf.Sin(60f * Mathf.Deg2Rad), 2f);
            float expected = Mathf.Lerp(0.1f, 100000f, dayFactor);
            Assert.That(light.intensity, Is.EqualTo(expected).Within(1f), "sunDimFactor=1 时与 M1 契约公式一致");

            t.GetField("sunDimFactor").SetValue(ctrl, 0.5f);
            t.GetMethod("Apply").Invoke(ctrl, null);
            Assert.That(light.intensity, Is.EqualTo(expected * 0.5f).Within(1f), "压暗档按乘子缩放直射");
            Object.DestroyImmediate(sunGo);
        }
    }
}
