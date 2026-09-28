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

            var ctrlType = FindAssemblyCSharpType("Sango.WeatherController");
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
