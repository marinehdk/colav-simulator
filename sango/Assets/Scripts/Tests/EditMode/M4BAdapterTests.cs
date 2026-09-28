using NUnit.Framework;
using Sango;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    /// <summary>
    /// M4-B 适配器薄壳 EditMode 测试（issue #87 批次 B）：HullWaterlineDecals 双投影器
    /// 构建/湿带驱动、NavigationLights 光弧驱动（灯片可见性 + 扇区因子）、BridgeSway
    /// 叠加语义（B0 恒等 / B6 可感 / 俯视档不受晃）。适配器在 Assembly-CSharp（Runtime 根
    /// 无 asmdef），经反射驱动（共享 TestReflection.FindAssemblyCSharpType，
    /// WaterDecalSpeedGateTests 先例）；DecalProjector/断言走 HDRP 公开 API。
    /// 手算几何：船根 y=−0.3（设计吃水）、立方船壳根局部 min(−1,0,−2)/max(1,1,2) →
    /// 水线局部 y=+0.3、吃水 0.3 m、干舷 0.7 m（s=1，模型单位=米）。
    /// </summary>
    public class M4BAdapterTests
    {
        GameObject _ship, _cube;

        [SetUp]
        public void SetUp()
        {
            _ship = new GameObject("m4b-test-ship");
            _ship.transform.position = new Vector3(0f, -0.3f, 0f); // 设计吃水位姿（静水 y=0）
            _cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.DestroyImmediate(_cube.GetComponent<Collider>());
            _cube.transform.SetParent(_ship.transform, false);
            _cube.transform.localPosition = new Vector3(0f, 0.5f, 0f);
            _cube.transform.localScale = new Vector3(2f, 1f, 4f); // 根局部包围盒 x±1, y 0..1, z±2
        }

        [TearDown]
        public void TearDown()
        {
            if (_ship != null) Object.DestroyImmediate(_ship);
        }

        // ── 项 1/4：HullWaterlineDecals ──────────────────────────────────────
        [Test]
        public void WaterlineDecals_BuildsTwoProjectors_WithDerivedWaterlineGeometry()
        {
            var decals = AddWaterlineDecals();

            Assert.That(ReadProp<bool>(decals, "RigBuilt"), Is.True, "rig 构建成功");
            var wet = ReadProp<DecalProjector>(decals, "WetnessProjector");
            var boot = ReadProp<DecalProjector>(decals, "BootTopProjector");
            Assert.That(wet, Is.Not.Null, "湿感投影器存在");
            Assert.That(boot, Is.Not.Null, "boot top 投影器存在（0.5 m < 干舷 0.7 m，可铺）");

            // 轴向契约：U/V 平面 = 局部 X/Y（盒手柄 X|Y），深度 = 局部 Z；ScaleInvariant。
            Assert.That(wet.scaleMode, Is.EqualTo(DecalScaleMode.ScaleInvariant), "size 即米（WaterDecal 同款约定）");
            Assert.That(wet.size.y, Is.EqualTo(1.2f).Within(1e-4f), "湿带盒高 = wetBandHeightM");
            Assert.That(wet.size.z, Is.GreaterThanOrEqualTo(4f), "深度轴（艏艉向）盖满 LOA");
            // 盒中心 = 水线 + 半带高（V 顶 = 盒顶 = 设计水线）。
            Assert.That(wet.transform.localPosition.y, Is.EqualTo(0.3f + 0.6f).Within(1e-4f), "湿带盒顶贴设计水线 y_local=0.3");

            Assert.That(boot.size.y, Is.EqualTo(0.5f).Within(1e-4f), "boot top 带高 = 请求 0.5（< 干舷 0.7 原样）");
            Assert.That(boot.transform.localPosition.y, Is.EqualTo(0.3f + 0.25f).Within(1e-4f), "boot top 带底贴设计水线");

            // 材质契约：湿感影响 BaseColor+Smoothness、boot top 只影响 BaseColor。
            Assert.That(wet.material.GetFloat("_AffectSmoothness"), Is.EqualTo(1f), "湿感带影响 smoothness");
            Assert.That(wet.material.GetFloat("_AffectAlbedo"), Is.EqualTo(1f), "湿感带影响 base color");
            Assert.That(boot.material.GetFloat("_AffectSmoothness"), Is.EqualTo(0f), "boot top 只改色不改光滑度");
            Assert.That(ReadProp<float>(decals, "DraftM"), Is.EqualTo(0.3f).Within(1e-4f), "吃水派生 0.3 m");
            Assert.That(ReadProp<float>(decals, "FreeboardM"), Is.EqualTo(0.7f).Within(1e-4f), "干舷派生 0.7 m");
        }

        [Test]
        public void WaterlineDecals_ExcursionDrivesBandY_ClampedByDepthRange()
        {
            var decals = AddWaterlineDecals();
            var wet = ReadProp<DecalProjector>(decals, "WetnessProjector");

            Invoke(decals, "ApplyWaterExcursion", 0.3f);
            Assert.That(ReadProp<float>(decals, "LastWetOffsetM"), Is.EqualTo(0.3f).Within(1e-4f), "常规升水原样传导");
            Assert.That(wet.transform.localPosition.y, Is.EqualTo(0.3f + 0.3f + 0.6f).Within(1e-4f), "投影器 y = 水线 + 偏移 + 半带高");

            Invoke(decals, "ApplyWaterExcursion", 10f);
            Assert.That(ReadProp<float>(decals, "LastWetOffsetM"), Is.EqualTo(0.7f).Within(1e-4f), "异常巨浪钳干舷");

            Invoke(decals, "ApplyWaterExcursion", -5f);
            Assert.That(ReadProp<float>(decals, "LastWetOffsetM"), Is.EqualTo(-0.3f).Within(1e-4f), "退水钳吃水");
        }

        // ── 项 3：NavigationLights 光弧驱动 ──────────────────────────────────
        [Test]
        public void NavigationLights_SectorArcs_HideLampsOutsideArc()
        {
            var navType = TestReflection.FindAssemblyCSharpType("Sango.NavigationLights");
            var nav = _ship.AddComponent(navType);
            navType.GetField("bowYawDeg").SetValue(nav, 0f);
            navType.GetMethod("BuildRig", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).Invoke(nav, null);
            Assert.That(ReadProp<bool>(nav, "RigBuilt"), Is.True, "rig 构建成功（立方船壳有 MeshFilter）");

            // 观察者在右舷前侧 30°：右舷灯/桅灯可见，左舷灯/艉灯弧外隐藏。
            Invoke(nav, "ApplyObservationBearing", 30f);
            Assert.That(LampFactor(nav, LampKind.StarboardSidelight), Is.EqualTo(1f).Within(1e-4f));
            Assert.That(LampFactor(nav, LampKind.Masthead), Is.EqualTo(1f).Within(1e-4f));
            Assert.That(LampFactor(nav, LampKind.PortSidelight), Is.EqualTo(0f).Within(1e-4f));
            Assert.That(LampFactor(nav, LampKind.SternLight), Is.EqualTo(0f).Within(1e-4f));
            Assert.That(QuadsEnabled("StarboardSidelight"), Is.True, "右舷灯片显示");
            Assert.That(QuadsEnabled("PortSidelight"), Is.False, "左舷灯片弧外整片隐藏");

            // 观察者在左舷前侧 330°：镜像成立。
            Invoke(nav, "ApplyObservationBearing", 330f);
            Assert.That(LampFactor(nav, LampKind.PortSidelight), Is.EqualTo(1f).Within(1e-4f));
            Assert.That(LampFactor(nav, LampKind.StarboardSidelight), Is.EqualTo(0f).Within(1e-4f));

            // 正艉：艉灯+桅灯盲区 → 艉灯独亮。
            Invoke(nav, "ApplyObservationBearing", 180f);
            Assert.That(LampFactor(nav, LampKind.SternLight), Is.EqualTo(1f).Within(1e-4f));
            Assert.That(LampFactor(nav, LampKind.Masthead), Is.EqualTo(0f).Within(1e-4f));
            Assert.That(QuadsEnabled("SternLight"), Is.True);
        }

        // ── 项 2：BridgeSway ─────────────────────────────────────────────────
        [Test]
        public void BridgeSway_BeaufortZero_Identity_BeaufortSix_Perceptible()
        {
            var camGo = new GameObject("m4b-test-cam", typeof(Camera));
            camGo.transform.position = new Vector3(0f, 12f, -40f);
            camGo.transform.rotation = Quaternion.Euler(-0.52f, 0f, 0f);
            var rigType = TestReflection.FindAssemblyCSharpType("Sango.CameraRig");
            var rig = camGo.AddComponent(rigType);
            var swayType = TestReflection.FindAssemblyCSharpType("Sango.BridgeSway");
            var sway = camGo.AddComponent(swayType);
            var weatherType = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            var weatherGo = new GameObject("m4b-test-weather");
            var weather = weatherGo.AddComponent(weatherType);
            try
            {
                swayType.GetField("weather").SetValue(sway, weather);
                swayType.GetField("rig").SetValue(sway, rig);

                // B0：恒等（位姿逐位不变）。
                weatherType.GetField("beaufort").SetValue(weather, 0f);
                Vector3 pos0 = camGo.transform.position;
                Quaternion rot0 = camGo.transform.rotation;
                Invoke(sway, "ApplySwayAt", 3.3f);
                Assert.That(camGo.transform.rotation == rot0, Is.True, "B0 旋转恒等");
                Assert.That(camGo.transform.position == pos0, Is.True, "B0 位置恒等");

                // B6：横摇峰值锚点 1.0°（t=2.5 s = 相位 0/周期 10 s 的正弦峰），可感位移。
                weatherType.GetField("beaufort").SetValue(weather, 6f);
                Invoke(sway, "ApplySwayAt", 2.5f);
                float tiltDeg = Quaternion.Angle(rot0, camGo.transform.rotation);
                Assert.That(tiltDeg, Is.InRange(0.8f, 1.3f), $"B6 峰值摇晃 ~1°（实测 {tiltDeg:F2}°）");
                Assert.That(Vector3.Distance(pos0, camGo.transform.position), Is.GreaterThan(0.01f), "B6 位置偏移可感");

                // 俯视战术档默认不受晃：CurrentView 切 TopDown 后恒等。
                rigType.GetProperty("CurrentView").SetValue(rig, CameraView.TopDown, null);
                camGo.transform.position = pos0;
                camGo.transform.rotation = rot0;
                Invoke(sway, "ApplySwayAt", 2.5f);
                Assert.That(camGo.transform.rotation == rot0, Is.True, "TopDown 档不受摇晃（UI 判读稳定）");
                Assert.That(camGo.transform.position == pos0, Is.True, "TopDown 档位置不变");
            }
            finally
            {
                Object.DestroyImmediate(camGo);
                Object.DestroyImmediate(weatherGo);
            }
        }

        // ── helpers ─────────────────────────────────────────────────────────

        Component AddWaterlineDecals()
        {
            var type = TestReflection.FindAssemblyCSharpType("Sango.HullWaterlineDecals");
            var comp = _ship.AddComponent(type);
            type.GetField("buoyancy").SetValue(comp, null);
            type.GetField("wetBandHeightM").SetValue(comp, 1.2f);
            type.GetField("bootTopBandHeightM").SetValue(comp, 0.5f);
            type.GetMethod("BuildProjectors").Invoke(comp, null);
            return comp;
        }

        static T ReadProp<T>(object obj, string name)
        {
            return (T)obj.GetType().GetProperty(name).GetValue(obj);
        }

        static void Invoke(object obj, string method, params object[] args)
        {
            obj.GetType().GetMethod(method).Invoke(obj, args);
        }

        static float LampFactor(Component nav, LampKind kind)
        {
            return (float)nav.GetType().GetMethod("LastLampFactor01").Invoke(nav, new object[] { kind });
        }

        bool QuadsEnabled(string lampName)
        {
            var lamp = _ship.transform.Find($"NavigationLightsRig/{lampName}");
            Assert.That(lamp, Is.Not.Null, $"灯对象 {lampName} 存在");
            var renderers = lamp.GetComponentsInChildren<MeshRenderer>();
            Assert.That(renderers.Length, Is.EqualTo(2), "交叉双面灯片");
            return renderers[0].enabled && renderers[1].enabled;
        }
    }
}
