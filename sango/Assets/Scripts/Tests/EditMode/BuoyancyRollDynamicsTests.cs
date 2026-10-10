using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// 档位 1+2 横摇动力学（2026-10-10 dt-sea-realism）：
    /// ① DampUnderdamped 欠阻尼二阶横摇——阶跃过冲（谐摇放大）与理论量级/峰值时间吻合，
    ///    位确定性、退化分支（ζ≥1 临界无过冲、period≤0 吸附、dt≤0 原样）；
    /// ② BlendRoll 混叠——后端包络 + 增益×视觉振荡、无后端纯视觉、1.35×钳制保底。
    /// </summary>
    public class BuoyancyRollDynamicsTests
    {
        const float k_Dt = 0.05f;

        [Test]
        public void UnderdampedStepOvershootsBeyondTarget()
        {
            var s = new DampedScalar { Value = 0f, Velocity = 0f };
            float peak = 0f;
            for (int i = 0; i < 2000; i++) // 100 s ≫ 固有周期 9 s
            {
                s = BuoyancyAttitudeSolver.DampUnderdamped(s, 10f, 9f, 0.12f, k_Dt);
                peak = Mathf.Max(peak, s.Value);
            }
            Assert.That(peak, Is.GreaterThan(15.5f), "ζ=0.12 阶跃应过冲（理论放大 1+exp(-ζπ/√(1-ζ²)) ≈1.68×）");
            Assert.That(peak, Is.LessThan(17.5f), "过冲不应偏离理论量级（理论峰值 16.84 ± 容差）");
        }

        [Test]
        public void UnderdampedPeakTimeMatchesHalfNaturalPeriod()
        {
            var s = new DampedScalar { Value = 0f, Velocity = 0f };
            float peakTime = -1f, peak = -1f;
            for (int i = 1; i <= 600; i++)
            {
                s = BuoyancyAttitudeSolver.DampUnderdamped(s, 10f, 9f, 0.12f, k_Dt);
                if (s.Value > peak) { peak = s.Value; peakTime = i * k_Dt; }
            }
            // 理论首峰 ≈ π/ω_d = (T/2)/√(1-ζ²) ≈ 4.53 s；欠阻尼修正后仍在半周期量级。
            Assert.That(peakTime, Is.InRange(3.5f, 5.5f), "首峰时间应落在半固有周期量级（±20%）");
        }

        [Test]
        public void SameInputSequenceProducesBitwiseIdenticalTrajectory()
        {
            var a = new DampedScalar { Value = 0.3f, Velocity = -0.2f };
            var b = a;
            for (int i = 0; i < 500; i++)
            {
                float target = Mathf.Sin(i * 0.11f) * 8f;
                a = BuoyancyAttitudeSolver.DampUnderdamped(a, target, 9f, 0.12f, k_Dt);
                b = BuoyancyAttitudeSolver.DampUnderdamped(b, target, 9f, 0.12f, k_Dt);
                if (i % 97 == 0) Assert.That(a.Value, Is.EqualTo(b.Value), "位确定性（回放复用前提）");
            }
            Assert.That(a.Value, Is.EqualTo(b.Value));
        }

        [Test]
        public void CriticalDampingFallbackHasNoOvershoot()
        {
            var s = new DampedScalar { Value = 0f, Velocity = 0f };
            float peak = 0f;
            for (int i = 0; i < 2000; i++)
            {
                s = BuoyancyAttitudeSolver.DampUnderdamped(s, 10f, 9f, 1f, k_Dt);
                peak = Mathf.Max(peak, s.Value);
            }
            Assert.That(peak, Is.LessThanOrEqualTo(10f + 1e-3f), "ζ≥1 退回临界阻尼：阶跃无过冲");
        }

        [Test]
        public void NonPositivePeriodSnapsToTarget()
        {
            var s = BuoyancyAttitudeSolver.DampUnderdamped(
                new DampedScalar { Value = 5f, Velocity = 2f }, 8f, 0f, 0.12f, k_Dt);
            Assert.That(s.Value, Is.EqualTo(8f), "period≤0 视为配置错误，直接吸附目标");
            Assert.That(s.Velocity, Is.EqualTo(0f));
        }

        [Test]
        public void NonPositiveDtReturnsStateUnchanged()
        {
            var before = new DampedScalar { Value = 1.7f, Velocity = -0.4f };
            var after = BuoyancyAttitudeSolver.DampUnderdamped(before, 9f, 9f, 0.12f, 0f);
            Assert.That(after.Value, Is.EqualTo(before.Value));
            Assert.That(after.Velocity, Is.EqualTo(before.Velocity));
        }

        [Test]
        public void BlendRollWithoutBackendUsesPureVisualRoll()
        {
            Assert.That(BuoyancyAttitudeSolver.BlendRoll(null, 4.5f, 0.6f, 12f), Is.EqualTo(4.5f));
        }

        [Test]
        public void BlendRollAddsScaledOscillationToBackendEnvelope()
        {
            // 后端包络 3°，视觉振荡 -5°，增益 0.6 → 3 - 3 = 0°（权威包络语义保留，振荡可控叠加）。
            Assert.That(BuoyancyAttitudeSolver.BlendRoll(3f, -5f, 0.6f, 12f), Is.EqualTo(3f + 0.6f * -5f).Within(1e-5f));
        }

        [Test]
        public void BlendRollClampsBeyondGuardCeiling()
        {
            float ceiling = 1.35f * 12f;
            Assert.That(BuoyancyAttitudeSolver.BlendRoll(30f, 10f, 1f, 12f), Is.EqualTo(ceiling).Within(1e-5f));
            Assert.That(BuoyancyAttitudeSolver.BlendRoll(-30f, -10f, 1f, 12f), Is.EqualTo(-ceiling).Within(1e-5f));
        }

        [Test]
        public void BlendRollGainIsClampedUnitRange()
        {
            // 增益超 1 按钮钳到 1（防 Inspector 外部写入失控）。
            Assert.That(BuoyancyAttitudeSolver.BlendRoll(1f, 5f, 99f, 12f), Is.EqualTo(6f).Within(1e-5f));
        }
    }
}
