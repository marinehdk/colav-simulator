using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    /// <summary>
    /// 天气雾距 Volume 参数 overrideState 缝 EditMode 测试（雾距滑条 no-op 修复回归锚）。
    /// 根因：ApplyCloudsAndFog 走 .value 赋值只写 m_Value 不置 overrideState
    /// （core VolumeParameter.cs:182-186），HDRP 体积混合只认 overrideState=True 的参数
    /// （Override 实现 :234-238）——运行时 census 逐字证据 fogEn=True(ovr=False)，
    /// 即雾参数全部未生效。修法同 1297f610 曝光修复口径：一律 .Override()。
    /// WeatherController 在 Assembly-CSharp（Assets/Scripts/Runtime/ 无 asmdef 覆盖，
    /// asmdef 无法引用预定义程序集），故经反射驱动；Fog 断言直接走 HDRP 公开 API。
    /// 合成 Global Volume + 独立运行时 profile，零场景依赖。
    /// </summary>
    public class WeatherFogOverrideTests
    {
        GameObject _volumeGo, _controllerGo;

        [TearDown]
        public void TearDown()
        {
            if (_controllerGo != null) Object.DestroyImmediate(_controllerGo);
            if (_volumeGo != null) Object.DestroyImmediate(_volumeGo);
        }

        [Test]
        public void Apply_FogDistance_SetsOverrideStateAndValue()
        {
            // 编排：合成 Global Volume + 仅含 Fog 的 profile；水面/太阳留空
            // （Apply 空引用安全：ApplyWater/ApplySun 前置 return，WeatherController.Apply）。
            _volumeGo = new GameObject("fog-test-volume");
            var volume = _volumeGo.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.sharedProfile = ScriptableObject.CreateInstance<VolumeProfile>();
            volume.sharedProfile.Add<Fog>();

            var ctrlType = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            _controllerGo = new GameObject("fog-test-controller");
            var controller = (MonoBehaviour)_controllerGo.AddComponent(ctrlType);
            ctrlType.GetField("globalVolume").SetValue(controller, volume);
            ctrlType.GetField("fogDistanceMeters").SetValue(controller, 1234f);

            ctrlType.GetMethod("Apply").Invoke(controller, null);

            Assert.That(volume.profile.TryGet<Fog>(out var fog), Is.True, "运行时 profile 含 Fog override");
            Assert.That(fog.enabled.overrideState, Is.True, "雾总开关 overrideState（census fogEn=True(ovr=False) 根因位）");
            Assert.That(fog.enableVolumetricFog.overrideState, Is.True, "体积雾子开关 overrideState");
            Assert.That(fog.maxFogDistance.overrideState, Is.True, "雾距 overrideState（滑条 no-op 根因位）");
            Assert.That(fog.maxFogDistance.value, Is.EqualTo(1234f), "雾距滑条值写入 maxFogDistance");
            Assert.That(fog.meanFreePath.overrideState, Is.True, "散射自由程 overrideState");
            Assert.That(fog.meanFreePath.value, Is.EqualTo(1234f), "自由程起调值 = 1× 雾距");
            Assert.That(fog.maximumHeight.overrideState, Is.True, "雾层顶高 overrideState");
        }

        // ── M6 review S2（2026-09-29）：海峡默认雾距 8000、M1 默认 3000 不变 ──────────
        [Test]
        public void FogDistance_FieldInitializer_StaysM1Default3000()
        {
            var ctrlType = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            _controllerGo = new GameObject("fog-default-controller");
            var controller = _controllerGo.AddComponent(ctrlType);
            Assert.That((float)ctrlType.GetField("fogDistanceMeters").GetValue(controller), Is.EqualTo(3000f),
                "字段初始化器 = M1 默认 3000（S2 只在 M6 bootstrapper 注入覆盖，不动 M1 语义）");
        }

        [Test]
        public void M6Bootstrapper_InjectsStraitDefaultFog8000()
        {
            // Sango.Editor.M6StraitSceneBootstrapper 在 Assembly-CSharp-Editor（asmdef 不引用，
            // EditMode 域已加载）——const k_DefaultFogDistanceM = BuildScene 注入
            // weather.fogDistanceMeters 的唯一来源，钉住 8000（F 键 A/B 实证的亮度主因档）。
            var bootType = TestReflection.FindLoadedType("Sango.Editor.M6StraitSceneBootstrapper");
            var f = bootType.GetField("k_DefaultFogDistanceM", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
            Assert.That(f, Is.Not.Null, "M6 bootstrapper 有海峡默认雾距常量");
            Assert.That((float)f.GetValue(null), Is.EqualTo(8000f), "海峡默认雾距 8000 m（开阔海峡档）");
        }
    }
}
