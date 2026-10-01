using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M9-1 尾迹泡沫纯核心 EditMode 测试：档位谓词（High/Low 双档语义）、强度曲线
    /// （速度爬坡 × Froude 双因子）、ribbon/环几何尺寸（LOA 驱动）。语义复用契约钉死：
    /// SpeedFactor/FroudeFactor 必须与 WaterDecalSpeedGate 同曲线（委托不重写）。
    /// WakeFoamCore 在 Assembly-CSharp（Runtime 根无 asmdef），经反射驱动（共享
    /// TestReflection.FindAssemblyCSharpType，WaterDecalSpeedGateTests 先例）。
    /// 手算锚值（独立算术，非回声实现）：√(9.81×12)=10.84988，Fr(5,12)=0.4608、
    /// Fr(4,12)=0.36867、Fr(2,12)=0.18433、Fr(4,100)=0.12771；
    /// 几何：12×0.06=0.72→钳 0.75、42×0.06=2.52、100×0.08=8→钳 4、12×0.22=2.64→钳 2.5。
    /// </summary>
    public class WakeFoamCoreTests
    {
        static System.Reflection.MethodInfo Core(string name)
            => TestReflection.FindAssemblyCSharpType("Sango.WakeFoamCore").GetMethod(name);

        static float CallF(string name, params object[] args)
            => (float)Core(name).Invoke(null, args);

        static bool CallB(string name, object arg)
            => (bool)Core(name).Invoke(null, new[] { arg });

        // ── 档位谓词（M8 双档 L 键；High = 粒子+ribbon / Low = decal）───────────────
        [Test]
        public void TierPredicates_HighActivatesParticlesAndSuppressesDecals_LowMirrors()
        {
            Assert.That(CallB("DecalsSuppressed", M8QualityTier.High), Is.True, "High 档压制 decal");
            Assert.That(CallB("DecalsSuppressed", M8QualityTier.Low), Is.False, "Low 档 decal 保持现状");
            Assert.That(CallB("ParticlesActive", M8QualityTier.High), Is.True, "High 档粒子+ribbon 激活");
            Assert.That(CallB("ParticlesActive", M8QualityTier.Low), Is.False, "Low 档 rig 休眠");
        }

        // ── 速度爬坡因子（与 WaterDecalSpeedGate.WakeFoamIntensity 同曲线的复用契约）──
        [Test]
        public void SpeedFactor_MatchesWaterDecalSpeedGateSemantics()
        {
            Assert.That(CallF("SpeedFactor", 0f, 0.5f, 5f), Is.EqualTo(0f), "静止零强度");
            Assert.That(CallF("SpeedFactor", 0.49f, 0.5f, 5f), Is.EqualTo(0f), "阈值以下恒 0");
            Assert.That(CallF("SpeedFactor", 2.75f, 0.5f, 5f), Is.EqualTo(0.5f).Within(1e-5f), "[0.5,5] 中点 = 0.5");
            Assert.That(CallF("SpeedFactor", 5f, 0.5f, 5f), Is.EqualTo(1f), "全强速度恰为 1");
            Assert.That(CallF("SpeedFactor", 9f, 0.5f, 5f), Is.EqualTo(1f), "超全强钳 1");
        }

        // ── Froude 因子（与 WaterDecalSpeedGate.BowAmplitude 归一化同曲线的复用契约）──
        [Test]
        public void FroudeFactor_RampsFromFroude020To045_LongBoatRampsLater()
        {
            Assert.That(CallF("FroudeFactor", 2f, 0.5f, 12f), Is.EqualTo(0f).Within(1e-6f),
                "12 m 船 2 m/s Fr=0.1843 < 0.20 起点 → 0");
            Assert.That(CallF("FroudeFactor", 4f, 0.5f, 12f), Is.EqualTo(0.6747f).Within(1e-3f),
                "Fr(4,12)=0.36867 → (0.36867-0.20)/0.25 = 0.6747");
            Assert.That(CallF("FroudeFactor", 5f, 0.5f, 12f), Is.EqualTo(1f).Within(1e-6f),
                "Fr=0.4608 恰过 0.45 钳制点 → 1");
            Assert.That(CallF("FroudeFactor", 4f, 0.5f, 100f), Is.EqualTo(0f).Within(1e-6f),
                "100 m 船 4 m/s Fr=0.1277 → 0（长船起波晚）");
            Assert.That(CallF("FroudeFactor", 5f, 0.5f, 0f), Is.EqualTo(1f),
                "loa≤0 防御退化：阈值以上阶跃全强（BowAmplitude 退化先例）");
        }

        // ── 艏浪发射率：速度 × Froude 双爬坡（评审"白线不随浪"的粒子端修复锚）────────
        [Test]
        public void SprayEmissionRate_SpeedTimesFroude_MooredZero()
        {
            Assert.That(CallF("SprayEmissionRate", 0f, 0.5f, 5f, 12f, 100f), Is.EqualTo(0f), "静止零发射");
            // 2.75 m/s：速度 0.5 × Froude (0.25346-0.20)/0.25=0.21383 → 100×0.5×0.21383 = 10.69
            Assert.That(CallF("SprayEmissionRate", 2.75f, 0.5f, 5f, 12f, 100f), Is.EqualTo(10.69f).Within(1e-2f),
                "中速双因子手算锚值");
            Assert.That(CallF("SprayEmissionRate", 5f, 0.5f, 5f, 12f, 100f), Is.EqualTo(100f).Within(1e-4f),
                "全强双因子饱和 = maxRate");
            Assert.That(CallF("SprayEmissionRate", 4f, 0.5f, 5f, 100f, 100f), Is.EqualTo(0f).Within(1e-6f),
                "长船低 Fr 艏浪不发射（Froude 门）");
        }

        // ── 几何尺寸（LOA 驱动，钳制护栏）───────────────────────────────────────────
        [Test]
        public void RibbonHalfWidthM_ScalesWithLoa_Clamped()
        {
            Assert.That(CallF("RibbonHalfWidthM", 12f), Is.EqualTo(0.75f).Within(1e-5f), "12 m 船钳下限（0.72→0.75）");
            Assert.That(CallF("RibbonHalfWidthM", 42f), Is.EqualTo(2.52f).Within(1e-4f), "42 m hero：全宽 5.04 m");
            Assert.That(CallF("RibbonHalfWidthM", 100f), Is.EqualTo(6f).Within(1e-4f), "100 m 船全宽 12 m");
            Assert.That(CallF("RibbonHalfWidthM", 0f), Is.EqualTo(0.75f).Within(1e-5f), "非法 LOA 落下限");
        }

        [Test]
        public void RingWidthM_ScalesWithBeam_Clamped()
        {
            Assert.That(CallF("RingWidthM", 12f), Is.EqualTo(0.8f).Within(1e-5f), "foam band upper bound");
            Assert.That(CallF("RingWidthM", 3f), Is.EqualTo(0.24f).Within(1e-4f), "narrow small-vessel foam band");
            Assert.That(CallF("RingWidthM", 0f), Is.EqualTo(0.2f).Within(1e-5f), "degenerate beam lower bound");
        }

        [Test]
        public void HistorySpacingM_ScalesWithLoa_Clamped()
        {
            Assert.That(CallF("HistorySpacingM", 12f), Is.EqualTo(0.25f).Within(1e-4f), "small vessel sampling lower bound");
            Assert.That(CallF("HistorySpacingM", 42f), Is.EqualTo(0.63f).Within(1e-4f), "sub-metre wave sampling");
            Assert.That(CallF("HistorySpacingM", 100f), Is.EqualTo(1f).Within(1e-4f), "large vessel sampling upper bound");
        }

        [Test]
        public void RibbonSampleCount_FixedTopologyBudget()
        {
            // 拓扑常量：顶点 2×28 = 56、三角形 (28-1)×2 = 54（预算注释见 WakeFoamRig 头注）
            var value = TestReflection.FindAssemblyCSharpType("Sango.WakeFoamCore")
                .GetField("RibbonSampleCount").GetValue(null);
            Assert.That(value, Is.EqualTo(128));
        }
    }
}
