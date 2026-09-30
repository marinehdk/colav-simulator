using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    /// <summary>
    /// M9-2 夜景光照链 EditMode 测试（评审三票命中点：夜空不暗 / 号灯方核 / 天气切档断崖）。
    /// NightGradeCore / LampSpotTexture / WeatherController（M9-2 新缝）均在 Assembly-CSharp
    /// （Runtime/NightGrade/ 无 asmdef 覆盖，同 WeatherFogOverrideTests 口径经反射驱动）；
    /// HDRP Exposure 断言走公开 API。worked examples 全手算锚值（反字面回声纪律）：
    /// 夜间补偿曲线（仰角 0/-3/-6/-18 → 0/-1.5/-3/-3）、光斑衰减（r=0.625 → exp(−2.25)）、
    /// billboard 边长（0.36 m / core 0.25 → 0.72 m）、拖尾层级（300/600 lm → 0.775）、
    /// 渐变中点（3→9 B 档 2.5 s 走一半 → 6.0，smoothstep(0.5)=0.5）。
    /// </summary>
    public class NightGradeCoreTests
    {
        const float k_Tol = 1e-4f;
        // 常量经反射取（核心 const 编在 Assembly-CSharp，测试侧解耦字面量；readonly 非 const 因编译期不可达）
        static readonly float k_Fade = (float)TestReflection.FindAssemblyCSharpType("Sango.NightGradeCore").GetField("NightEvFadeDeg").GetValue(null);
        static readonly float k_Floor = (float)TestReflection.FindAssemblyCSharpType("Sango.NightGradeCore").GetField("NightFloorEv").GetValue(null);

        static float CoreF(string method, params object[] args)
        {
            var core = TestReflection.FindAssemblyCSharpType("Sango.NightGradeCore");
            return (float)core.GetMethod(method).Invoke(null, args);
        }

        // ── ① 夜间补偿曲线（NightGradeCore.NightCompensationEv）──────────────────────
        [Test]
        public void NightCompensation_DayElevations_ExactlyZero()
        {
            // 白天契约：仰角 ≥ 0 恒返 0f（消费方跳过加法，compensation 与旧契约逐位一致）。
            Assert.That(CoreF("NightCompensationEv", 60f, k_Fade, k_Floor), Is.EqualTo(0f), "正午 +60° 零补偿");
            Assert.That(CoreF("NightCompensationEv", 7.8f, k_Fade, k_Floor), Is.EqualTo(0f), "傍晚档 17.5h（+7.8°）零补偿");
            Assert.That(CoreF("NightCompensationEv", 0f, k_Fade, k_Floor), Is.EqualTo(0f), "地平线恰 0° 零补偿（渐入起点）");
        }

        [Test]
        public void NightCompensation_TwilightBand_LinearRamp()
        {
            // 手算：−3° = 半带 → −1.5 EV；−6° = 满带 → −3 EV 地板。
            Assert.That(CoreF("NightCompensationEv", -3f, k_Fade, k_Floor), Is.EqualTo(-1.5f).Within(k_Tol), "半带 −3° → 半幅");
            Assert.That(CoreF("NightCompensationEv", -6f, k_Fade, k_Floor), Is.EqualTo(k_Floor).Within(k_Tol), "满带 −6° → 地板");
            Assert.That(CoreF("NightCompensationEv", -1.5f, k_Fade, k_Floor), Is.EqualTo(-0.75f).Within(k_Tol), "1/4 带 → 1/4 幅");
        }

        [Test]
        public void NightCompensation_DeepNight_ClampedAtFloor()
        {
            // ApplySun 钳底 −18°（h=0/24 深夜）→ 地板 −3 EV。
            Assert.That(CoreF("NightCompensationEv", -18f, k_Fade, k_Floor), Is.EqualTo(k_Floor).Within(k_Tol));
        }

        [Test]
        public void NightCompensation_MonotonicNonDecreasingDarkness()
        {
            float prev = 0f;
            for (float elev = 0f; elev >= -6.5f; elev -= 0.5f)
            {
                float ev = CoreF("NightCompensationEv", elev, k_Fade, k_Floor);
                Assert.That(ev, Is.LessThanOrEqualTo(prev + k_Tol), $"仰角 {elev}° 补偿须单调不升（越夜越暗）");
                prev = ev;
            }
        }

        // ── ② 光斑径向衰减 + ③ billboard 尺寸（NightGradeCore）───────────────────────
        [Test]
        public void LampSpotFalloff_CoreFlat_ThenExponentialHalo()
        {
            float core = (float)TestReflection.FindAssemblyCSharpType("Sango.NightGradeCore").GetField("LampSpotCoreRadius01").GetValue(null);
            float decay = (float)TestReflection.FindAssemblyCSharpType("Sango.NightGradeCore").GetField("LampSpotHaloDecay").GetValue(null);

            Assert.That(CoreF("LampSpotFalloff", 0f, core, decay), Is.EqualTo(1f), "圆心 = 亮核满强");
            Assert.That(CoreF("LampSpotFalloff", core, core, decay), Is.EqualTo(1f), "核边仍满强（连续无台阶）");
            Assert.That(CoreF("LampSpotFalloff", 0.625f, core, decay), Is.EqualTo(Mathf.Exp(-decay * 0.5f)).Within(k_Tol),
                "r=0.625 = 核外半程 → exp(−decay·0.5) = exp(−2.25)");
            Assert.That(CoreF("LampSpotFalloff", 1f, core, decay), Is.EqualTo(Mathf.Exp(-decay)).Within(k_Tol),
                "r=1 边缘 → exp(−decay) ≈ 0.011 收边");
            Assert.That(CoreF("LampSpotFalloff", 1.5f, core, decay), Is.EqualTo(Mathf.Exp(-decay)).Within(k_Tol),
                "贴图角落 r=√2 钳 [0,1] 不回弹");
            float prev = 1f;
            for (float r = 0f; r <= 1.01f; r += 0.05f)
            {
                float v = CoreF("LampSpotFalloff", r, core, decay);
                Assert.That(v, Is.LessThanOrEqualTo(prev + k_Tol), $"r={r:F2} 衰减单调不增");
                prev = v;
            }
        }

        [Test]
        public void BillboardEdge_KeepsCoreDiameterEqualToLegacyQuad()
        {
            // 观感尺寸守恒：亮核圆直径（edge × 2·core）= 原方片边长。
            Assert.That(CoreF("BillboardEdgeM", 1f, 0.25f), Is.EqualTo(2f).Within(k_Tol), "1 m 灯片 / core 0.25 → 2 m billboard");
            Assert.That(CoreF("BillboardEdgeM", 0.36f, 0.25f), Is.EqualTo(0.72f).Within(k_Tol), "Small 船 0.36 m 灯片 → 0.72 m");
            float edge = CoreF("BillboardEdgeM", 1.8f, 0.25f);
            Assert.That(edge * 2f * 0.25f, Is.EqualTo(1.8f).Within(k_Tol), "Medium 船核圆直径还原 1.8 m");
        }

        // ── ④ 拖尾点光层级（NightGradeCore.StreakNightFactor）────────────────────────
        [Test]
        public void StreakNightFactor_FollowsLumenHierarchy()
        {
            Assert.That(CoreF("StreakNightFactor", 600f, 600f), Is.EqualTo(1f).Within(k_Tol), "桅灯（最亮）全强");
            Assert.That(CoreF("StreakNightFactor", 300f, 600f), Is.EqualTo(0.775f).Within(k_Tol), "舷灯 300/600 → 0.55+0.45·0.5");
            Assert.That(CoreF("StreakNightFactor", 200f, 600f), Is.EqualTo(0.70f).Within(k_Tol), "艉灯 200/600 → 0.55+0.45·(1/3)");
            Assert.That(CoreF("StreakNightFactor", 900f, 600f), Is.EqualTo(1f).Within(k_Tol), "比例 > 1 钳满幅");
        }

        // ── LampSpotTexture（程序化贴图）────────────────────────────────────────────
        [Test]
        public void LampSpotTexture_CenterLit_CornerFaded_SharedInstance()
        {
            var tex = (Texture2D)TestReflection.FindAssemblyCSharpType("Sango.LampSpotTexture")
                .GetMethod("GetShared").Invoke(null, null);
            Assert.That(tex.width, Is.EqualTo(128), "128² 固定尺寸");
            var center = tex.GetPixel(64, 64);
            Assert.That(center.a, Is.EqualTo(1f).Within(k_Tol), "圆心 alpha 满");
            Assert.That(center.r, Is.EqualTo(1f).Within(k_Tol), "RGB 恒白（灯色由材质承载）");
            var corner = tex.GetPixel(0, 0);
            Assert.That(corner.a, Is.LessThanOrEqualTo(8f / 255f), "角落 alpha ≤ exp(−4.5)·255 ≈ 3");
            var again = (Texture2D)TestReflection.FindAssemblyCSharpType("Sango.LampSpotTexture")
                .GetMethod("GetShared").Invoke(null, null);
            Assert.That(ReferenceEquals(tex, again), Is.True, "会话级共享单张");
        }

        // ── WeatherController：夜间曝光地板写入（.Override 口径）──────────────────────
        GameObject _volumeGo, _controllerGo, _sunGo;

        [TearDown]
        public void TearDown()
        {
            if (_controllerGo != null) Object.DestroyImmediate(_controllerGo);
            if (_volumeGo != null) Object.DestroyImmediate(_volumeGo);
            if (_sunGo != null) Object.DestroyImmediate(_sunGo);
        }

        (System.Type type, Component ctrl) MakeControllerWithSunAndExposure()
        {
            var t = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            _controllerGo = new GameObject("m92-test-controller");
            var ctrl = (Component)_controllerGo.AddComponent(t);

            _volumeGo = new GameObject("m92-test-volume");
            var volume = _volumeGo.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.sharedProfile = ScriptableObject.CreateInstance<VolumeProfile>();
            volume.sharedProfile.Add<Exposure>();
            t.GetField("globalVolume").SetValue(ctrl, volume);

            _sunGo = new GameObject("m92-test-sun", typeof(Light));
            _sunGo.GetComponent<Light>().type = LightType.Directional;
            t.GetField("sunLight").SetValue(ctrl, _sunGo.GetComponent<Light>());
            return (t, ctrl);
        }

        [Test]
        public void Apply_Noon_ExposureCompensationUnchanged()
        {
            var (t, ctrl) = MakeControllerWithSunAndExposure();
            t.GetField("timeOfDayHours").SetValue(ctrl, 12f); // 正午 +60°

            t.GetMethod("Apply").Invoke(ctrl, null);

            var volume = _volumeGo.GetComponent<Volume>();
            Assert.That(volume.profile.TryGet<Exposure>(out var exposure), Is.True);
            Assert.That(exposure.compensation.overrideState, Is.True, "overrideState 口径不变");
            Assert.That(exposure.compensation.value, Is.EqualTo(0f), "白天与旧契约逐位一致（默认零补偿）");
            Assert.That((float)t.GetProperty("LastNightCompensationEv").GetValue(ctrl), Is.EqualTo(0f), "夜间因子观测口 = 0");
        }

        [Test]
        public void Apply_DeepNight_FloorCompensationApplied()
        {
            var (t, ctrl) = MakeControllerWithSunAndExposure();
            t.GetField("timeOfDayHours").SetValue(ctrl, 0f); // 深夜（仰角钳 −18°）

            t.GetMethod("Apply").Invoke(ctrl, null);

            var volume = _volumeGo.GetComponent<Volume>();
            Assert.That(volume.profile.TryGet<Exposure>(out var exposure), Is.True);
            Assert.That(exposure.compensation.value, Is.EqualTo(k_Floor).Within(1e-3f), "深夜补偿 = 地板 −3 EV");
            Assert.That((float)t.GetProperty("LastNightCompensationEv").GetValue(ctrl), Is.EqualTo(k_Floor).Within(1e-3f));
        }

        [Test]
        public void Apply_Night_AddsOnTopOfAtmosphereTierEv()
        {
            var (t, ctrl) = MakeControllerWithSunAndExposure();
            t.GetField("timeOfDayHours").SetValue(ctrl, 0f);
            t.GetField("exposureCompensationEv").SetValue(ctrl, -1.6f); // 雷暴档 −1.6 EV 之上的夜间加码

            t.GetMethod("Apply").Invoke(ctrl, null);

            var volume = _volumeGo.GetComponent<Volume>();
            Assert.That(volume.profile.TryGet<Exposure>(out var exposure), Is.True);
            Assert.That(exposure.compensation.value, Is.EqualTo(-4.6f).Within(1e-3f), "−1.6（档）+ −3（夜地板）= −4.6 EV");
        }

        // ── WeatherController：用户切档渐变（BeginUserGradeTransition / 同轨推进）──────
        [Test]
        public void BeginUserGradeTransition_MidpointIsHalfway()
        {
            // smoothstep(0.5) = 0.5：3→9 B 档、3000→8000 m 雾，2.5 s 走到一半 = 正中。
            var t = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            _controllerGo = new GameObject("m92-test-controller");
            var ctrl = _controllerGo.AddComponent(t);
            t.GetField("beaufort").SetValue(ctrl, 3f);
            t.GetField("fogDistanceMeters").SetValue(ctrl, 3000f);

            t.GetMethod("BeginUserGradeTransition").Invoke(ctrl, new object[] { (float?)9f, (float?)8000f, 2.5f });
            Assert.That((bool)t.GetProperty("AtmosphereTransitioning").GetValue(ctrl), Is.True, "起过渡");

            t.GetMethod("AdvanceAtmosphereTransition").Invoke(ctrl, new object[] { 1.25f });
            Assert.That((float)t.GetField("beaufort").GetValue(ctrl), Is.EqualTo(6f).Within(1e-3f), "风档中点 6.0");
            Assert.That((float)t.GetField("fogDistanceMeters").GetValue(ctrl), Is.EqualTo(5500f).Within(1e-3f), "雾距中点 5500");

            bool still = (bool)t.GetMethod("AdvanceAtmosphereTransition").Invoke(ctrl, new object[] { 1.25f });
            Assert.That(still, Is.False, "走完退出过渡");
            Assert.That((float)t.GetField("beaufort").GetValue(ctrl), Is.EqualTo(9f).Within(1e-3f), "风档终点 = 目标");
            Assert.That((float)t.GetField("fogDistanceMeters").GetValue(ctrl), Is.EqualTo(8000f).Within(1e-3f), "雾距终点 = 目标");
        }

        [Test]
        public void BeginUserGradeTransition_UnspecifiedChannelsStayPinned()
        {
            var t = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            _controllerGo = new GameObject("m92-test-controller");
            var ctrl = _controllerGo.AddComponent(t);
            t.GetField("beaufort").SetValue(ctrl, 3f);
            t.GetField("fogDistanceMeters").SetValue(ctrl, 3000f);

            t.GetMethod("BeginUserGradeTransition").Invoke(ctrl, new object[] { null, (float?)8000f, 2.5f }); // 只动雾（F 键形态）
            t.GetMethod("AdvanceAtmosphereTransition").Invoke(ctrl, new object[] { 1.25f });

            Assert.That((float)t.GetField("beaufort").GetValue(ctrl), Is.EqualTo(3f).Within(1e-3f), "未指定风档钉当前值（不跳变）");
            Assert.That((float)t.GetField("fogDistanceMeters").GetValue(ctrl), Is.EqualTo(5500f).Within(1e-3f), "雾距渐变推进");
        }

        [Test]
        public void ApplyAtmosphereTier_KeepsBeaufortPinned_RunnerPathUnhijacked()
        {
            // 回归锚：N 键/出片机 ApplyAtmosphereTier 不动风（from==to）——M8RecordingRunner
            // 确定性路径（直设 timeOfDayHours + ApplyAtmosphereTier）行为不变。
            var t = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            _controllerGo = new GameObject("m92-test-controller");
            var ctrl = _controllerGo.AddComponent(t);
            t.GetField("beaufort").SetValue(ctrl, 5f);
            var tierType = t.GetField("atmosphereTier").FieldType;
            t.GetField("atmosphereTier").SetValue(ctrl, System.Enum.ToObject(tierType, 2)); // Thunderstorm

            t.GetMethod("ApplyAtmosphereTier").Invoke(ctrl, null);
            bool still = true;
            int steps = 0;
            while (still && steps < 20)
                still = (bool)t.GetMethod("AdvanceAtmosphereTransition").Invoke(ctrl, new object[] { 0.5f });

            Assert.That((float)t.GetField("beaufort").GetValue(ctrl), Is.EqualTo(5f).Within(1e-3f), "大气档切换全程风档钉住");
            Assert.That((float)t.GetField("fogDistanceMeters").GetValue(ctrl), Is.EqualTo(1500f).Within(0.5f), "雷暴雾距照常过渡（M7-B 契约不变）");
        }
    }
}
