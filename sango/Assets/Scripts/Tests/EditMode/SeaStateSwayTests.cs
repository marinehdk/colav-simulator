using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M4-B 海况摇晃纯核心 EditMode 测试（issue #87 批次 B 项 2）：SeaStateSway worked
    /// examples——B0 全零 / 确定性 / 周期锚点（横摇 10 s = 桥楼 8-12 s 带中值、垂荡 6 s）/
    /// 量级锚点（B6 横摇峰值 1.0° 明显可感、B9 峰值 3.0° = UI 可读上限）/ 幅值随蒲福单调 /
    /// 整数档间线性插值 / &gt;B9 顶格。峰值采样点 t=2.5 s 是独立三角事实：横摇相位 0、
    /// 周期 10 s → sin(2π·2.5/10)=sin(π/2)=1（非回声实现，锚点常量以公开 const 读出）。
    /// </summary>
    public class SeaStateSwayTests
    {
        const float k_Tol = 1e-4f;

        [Test]
        public void Sway_BeaufortZero_AllZeroAtAnyTime()
        {
            foreach (float t in new[] { 0f, 1.7f, 13.3f, 100f })
            {
                var s = SeaStateSway.SwayOffset(0f, t);
                Assert.That(s.PosOffsetM.x, Is.EqualTo(0f).Within(k_Tol), $"B0 时刻 {t} 横荡零");
                Assert.That(s.PosOffsetM.y, Is.EqualTo(0f).Within(k_Tol), $"B0 时刻 {t} 垂荡零");
                Assert.That(s.PosOffsetM.z, Is.EqualTo(0f).Within(k_Tol), $"B0 时刻 {t} 纵向恒零");
                Assert.That(s.RollDeg, Is.EqualTo(0f).Within(k_Tol), $"B0 时刻 {t} roll 零");
                Assert.That(s.PitchDeg, Is.EqualTo(0f).Within(k_Tol), $"B0 时刻 {t} pitch 零");
            }
        }

        [Test]
        public void Sway_NegativeBeaufort_ClampedToZero()
        {
            var s = SeaStateSway.SwayOffset(-3f, 4.2f);
            Assert.That(s.RollDeg, Is.EqualTo(0f).Within(k_Tol), "负蒲福（非法输入）按 B0 处理");
        }

        [Test]
        public void Sway_Deterministic_SameInputsSameOutput()
        {
            var a = SeaStateSway.SwayOffset(6.3f, 12.34f);
            var b = SeaStateSway.SwayOffset(6.3f, 12.34f);
            Assert.That(a.RollDeg, Is.EqualTo(b.RollDeg), "同输入逐位同输出（禁随机）");
            Assert.That(a.PitchDeg, Is.EqualTo(b.PitchDeg));
            Assert.That(a.PosOffsetM.x, Is.EqualTo(b.PosOffsetM.x));
            Assert.That(a.PosOffsetM.y, Is.EqualTo(b.PosOffsetM.y));
        }

        [Test]
        public void Sway_RollPeriodAnchor_TenSeconds()
        {
            foreach (float t in new[] { 0.37f, 2.5f, 7.1f })
            {
                float r1 = SeaStateSway.SwayOffset(6f, t).RollDeg;
                float r2 = SeaStateSway.SwayOffset(6f, t + SeaStateSway.RollPeriodSeconds).RollDeg;
                Assert.That(r2, Is.EqualTo(r1).Within(k_Tol),
                    $"横摇周期 {SeaStateSway.RollPeriodSeconds} s（桥楼横摇 8-12 s 量级锚点）：t={t}");
            }
        }

        [Test]
        public void Sway_HeavePeriodAnchor_SixSeconds()
        {
            float h1 = SeaStateSway.SwayOffset(7f, 1.23f).PosOffsetM.y;
            float h2 = SeaStateSway.SwayOffset(7f, 1.23f + SeaStateSway.HeavePeriodSeconds).PosOffsetM.y;
            Assert.That(h2, Is.EqualTo(h1).Within(k_Tol), "垂荡周期 6 s 锚点");
        }

        [Test]
        public void Sway_MagnitudeAnchors_B6Perceptible_B9ReadableCap()
        {
            // t=2.5 s：横摇相位 0 + 周期 10 s → 正弦恰在峰值（独立三角事实）。
            float rollB6 = Mathf.Abs(SeaStateSway.SwayOffset(6f, 2.5f).RollDeg);
            Assert.That(rollB6, Is.EqualTo(1.0f).Within(k_Tol), "B6 横摇峰值锚点 1.0°（明显可感档）");
            Assert.That(rollB6, Is.GreaterThanOrEqualTo(0.8f), "B6 下限：固定机位上必须可感");

            float rollB9 = Mathf.Abs(SeaStateSway.SwayOffset(9f, 2.5f).RollDeg);
            Assert.That(rollB9, Is.EqualTo(3.0f).Within(k_Tol), "B9 横摇峰值锚点 3.0°（表顶格）");
            Assert.That(rollB9, Is.LessThanOrEqualTo(3.5f), "B9 上限：水平线倾角须保持 UI 可读");

            float heaveB9 = Mathf.Abs(SeaStateSway.SwayOffset(9f, PeakTime(SeaStateSway.HeavePeriodSeconds, 2.1f)).PosOffsetM.y);
            Assert.That(heaveB9, Is.EqualTo(0.40f).Within(1e-3f), "B9 垂荡峰值锚点 0.40 m");
        }

        [Test]
        public void Sway_AmplitudeMonotonicInBeaufort()
        {
            float prevRoll = -1f, prevHeave = -1f;
            for (float b = 0f; b <= 9f; b += 0.25f)
            {
                float maxRoll = 0f, maxHeave = 0f;
                for (float t = 0f; t < SeaStateSway.RollPeriodSeconds; t += 0.05f)
                {
                    var s = SeaStateSway.SwayOffset(b, t);
                    maxRoll = Mathf.Max(maxRoll, Mathf.Abs(s.RollDeg));
                    maxHeave = Mathf.Max(maxHeave, Mathf.Abs(s.PosOffsetM.y));
                }
                Assert.That(maxRoll, Is.GreaterThanOrEqualTo(prevRoll - k_Tol), $"蒲福 {b} 横摇峰值不得回退");
                Assert.That(maxHeave, Is.GreaterThanOrEqualTo(prevHeave - k_Tol), $"蒲福 {b} 垂荡峰值不得回退");
                prevRoll = maxRoll;
                prevHeave = maxHeave;
            }
        }

        [Test]
        public void Sway_InterpolatesBetweenIntegerTiers()
        {
            // 表值 B4=0.40 / B5=0.65（实现锚点表，测试读公开行为验证插值语义）：中点 0.525。
            float roll = Mathf.Abs(SeaStateSway.SwayOffset(4.5f, 2.5f).RollDeg);
            Assert.That(roll, Is.EqualTo(0.525f).Within(1e-3f), "小数蒲福 = 整数档线性插值（峰值采样）");
        }

        [Test]
        public void Sway_ClampsAboveBeaufortNine()
        {
            // 天气滑条上限 11 级：B10/B11 摇晃按 B9 顶格（表只到 9）。
            for (float t = 0f; t < 12f; t += 0.7f)
            {
                var at9 = SeaStateSway.SwayOffset(9f, t);
                var at11 = SeaStateSway.SwayOffset(11f, t);
                Assert.That(at11.RollDeg, Is.EqualTo(at9.RollDeg).Within(k_Tol), $"t={t} B11 == B9");
                Assert.That(at11.PosOffsetM.y, Is.EqualTo(at9.PosOffsetM.y).Within(k_Tol));
            }
        }

        /// <summary>相位 φ、周期 T 的正弦峰值时刻（独立算术：2πt/T+φ=π/2）。</summary>
        static float PeakTime(float periodS, float phaseRad)
        {
            return (Mathf.PI / 2f - phaseRad) * periodS / (2f * Mathf.PI);
        }
    }
}
