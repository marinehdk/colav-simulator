using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-B 浮力姿态缝 EditMode 测试（spec #81 Testing Decisions）：只打纯求解器
    /// BuoyancyAttitudeSolver，合成数据，无 WaterSurface/场景/prefab。
    /// 钉死的符号约定（与求解器 doc 注释、evidence m2b-build-log.md 一致）：
    ///   HeaveOffset + = 相对设计吃水向上；
    ///   RollDeg     = Unity 本地欧拉 Z，+ = 右舷(+X)上浮；
    ///   PitchDeg    = Unity 本地欧拉 X，+ = 艏(+Z)下俯（Unity 惯例，故艏抬升为负值）。
    /// 反字面回声纪律：符号断言的"独立事实"是本文件钉死的约定 + 场景构造的对称性
    /// （横摇工况沿 z 反对称 → 纵摇恒等 0；纵摇工况沿 x 反对称 → 横摇恒等 0），
    /// 不回声实现里的 gain/atan 公式。
    /// </summary>
    public class BuoyancyAttitudeSolverTests
    {
        // 采样网：±4 m 半宽 × ±10 m 半长（yaw-only 船体坐标，米），5×5 = 25 点。
        // 全部样点取在 y=0 水线高度 → 静水基线吃水 0，工况"水面高"即浸没激励。
        const float k_HalfBeam = 4f;
        const int k_Grid = 5;
        const float k_HalfLength = 10f;
        const float k_Slope = 0.2f; // 缓坡：roll/pitch 响应 ≈ 5.7°，远离默认钳制，隔离钳制测试
        const float k_ZeroTol = 1e-3f;

        static HullSample[] Grid(System.Func<float, float, float> waterHeight)
        {
            var samples = new HullSample[k_Grid * k_Grid];
            int i = 0;
            for (int iz = 0; iz < k_Grid; iz++)
            {
                for (int ix = 0; ix < k_Grid; ix++)
                {
                    float x = Mathf.Lerp(-k_HalfBeam, k_HalfBeam, ix / (float)(k_Grid - 1));
                    float z = Mathf.Lerp(-k_HalfLength, k_HalfLength, iz / (float)(k_Grid - 1));
                    samples[i++] = new HullSample
                    {
                        StarboardOffset = x,
                        ForwardOffset = z,
                        Submersion = waterHeight(x, z),   // 点在 y=0：浸没 = 水面高
                        BaselineSubmersion = 0f,          // 静水（0 m 水面）下的设计吃水
                    };
                }
            }
            return samples;
        }

        // ── 静海 ────────────────────────────────────────────────────────────────────
        [Test]
        public void Solve_LevelSea_ReturnsZeroAttitude()
        {
            var a = BuoyancyAttitudeSolver.Solve(Grid((x, z) => 0f), BuoyancyParams.Default);
            Assert.That(a.HeaveOffset, Is.EqualTo(0f).Within(k_ZeroTol), "calm sea must not heave");
            Assert.That(a.RollDeg, Is.EqualTo(0f).Within(k_ZeroTol), "calm sea must not roll");
            Assert.That(a.PitchDeg, Is.EqualTo(0f).Within(k_ZeroTol), "calm sea must not pitch");
        }

        // ── 右舷涌浪：水面沿 +X 线性抬升（右舷高）→ 右舷上浮（RollDeg>0），纵摇恒 0 ──
        [Test]
        public void Solve_StarboardSwell_RollsStarboardUp_WithZeroPitch()
        {
            var a = BuoyancyAttitudeSolver.Solve(Grid((x, z) => k_Slope * x), BuoyancyParams.Default);
            Assert.That(a.RollDeg, Is.GreaterThan(0f), "starboard-high water must roll starboard up (pinned convention)");
            Assert.That(a.RollDeg, Is.LessThan(45f), "gentle slope must stay far from clamps");
            Assert.That(a.PitchDeg, Is.EqualTo(0f).Within(k_ZeroTol), "port/starboard antisymmetry → pure roll");
            Assert.That(a.HeaveOffset, Is.EqualTo(0f).Within(k_ZeroTol), "antisymmetric swell averages to no heave");
        }

        // ── 艏艉涌浪：水面沿 +Z 线性抬升（艏高）→ 艏上浮 = PitchDeg<0（+ 为艏下俯），横摇恒 0 ──
        [Test]
        public void Solve_BowHighSwell_PitchesBowUp_WithZeroRoll()
        {
            var a = BuoyancyAttitudeSolver.Solve(Grid((x, z) => k_Slope * z), BuoyancyParams.Default);
            Assert.That(a.PitchDeg, Is.LessThan(0f), "bow-high water must pitch bow up, i.e. negative euler X (pinned convention)");
            Assert.That(a.PitchDeg, Is.GreaterThan(-45f), "gentle slope must stay far from clamps");
            Assert.That(a.RollDeg, Is.EqualTo(0f).Within(k_ZeroTol), "bow/stern antisymmetry → pure pitch");
            Assert.That(a.HeaveOffset, Is.EqualTo(0f).Within(k_ZeroTol), "antisymmetric swell averages to no heave");
        }

        // ── 整体水位抬升：均匀 +1 m → 上浮 +1 m（HeaveGain=1），无姿态 ───────────────
        [Test]
        public void Solve_UniformWaterRise_HeavesUpByRise_WithZeroAttitude()
        {
            var a = BuoyancyAttitudeSolver.Solve(Grid((x, z) => 1f), BuoyancyParams.Default);
            Assert.That(a.HeaveOffset, Is.EqualTo(1f).Within(k_ZeroTol), "unit rise with HeaveGain=1 must heave up one metre");
            Assert.That(a.RollDeg, Is.EqualTo(0f).Within(k_ZeroTol));
            Assert.That(a.PitchDeg, Is.EqualTo(0f).Within(k_ZeroTol));
        }

        // ── 极端涌浪：横摇/纵摇钳制在可行上限内（B11 也不许倾覆观感）────────────────
        [Test]
        public void Solve_ExtremeSwell_RespectsRollAndPitchClamps()
        {
            var p = BuoyancyParams.Default;
            var rollCase = BuoyancyAttitudeSolver.Solve(Grid((x, z) => 20f * x), p);
            Assert.That(Mathf.Abs(rollCase.RollDeg), Is.LessThanOrEqualTo(p.MaxRollDeg + k_ZeroTol));
            var pitchCase = BuoyancyAttitudeSolver.Solve(Grid((x, z) => 20f * z), p);
            Assert.That(Mathf.Abs(pitchCase.PitchDeg), Is.LessThanOrEqualTo(p.MaxPitchDeg + k_ZeroTol));
        }

        // ── 确定性：同输入两次求解逐位一致 ──────────────────────────────────────────
        [Test]
        public void Solve_SameInput_ProducesBitwiseIdenticalOutput()
        {
            var samples = Grid((x, z) => k_Slope * (x + z) + Mathf.Sin(z));
            var a1 = BuoyancyAttitudeSolver.Solve(samples, BuoyancyParams.Default);
            var a2 = BuoyancyAttitudeSolver.Solve(samples, BuoyancyParams.Default);
            Assert.That(a2.HeaveOffset, Is.EqualTo(a1.HeaveOffset));
            Assert.That(a2.RollDeg, Is.EqualTo(a1.RollDeg));
            Assert.That(a2.PitchDeg, Is.EqualTo(a1.PitchDeg));
        }

        // ── 计数重载：与全量重载逐位一致，且 count 尾部残留被忽略（持久缓冲契约）────
        [Test]
        public void Solve_CountOverload_MatchesFullArray_AndIgnoresTailBeyondCount()
        {
            var samples = Grid((x, z) => k_Slope * (x - z));
            var full = BuoyancyAttitudeSolver.Solve(samples, BuoyancyParams.Default);

            var withTail = new HullSample[samples.Length + 3];
            samples.CopyTo(withTail, 0);
            for (int i = samples.Length; i < withTail.Length; i++)
            {
                withTail[i] = new HullSample { StarboardOffset = 999f, ForwardOffset = -999f, Submersion = 999f, BaselineSubmersion = -999f };
            }
            var counted = BuoyancyAttitudeSolver.Solve(withTail, samples.Length, BuoyancyParams.Default);

            Assert.That(counted.HeaveOffset, Is.EqualTo(full.HeaveOffset));
            Assert.That(counted.RollDeg, Is.EqualTo(full.RollDeg));
            Assert.That(counted.PitchDeg, Is.EqualTo(full.PitchDeg));
        }

        [Test]
        public void Solve_EmptySamples_ReturnsZeroAttitude()
        {
            var a = BuoyancyAttitudeSolver.Solve(new HullSample[0], BuoyancyParams.Default);
            Assert.That(a.HeaveOffset, Is.EqualTo(0f));
            Assert.That(a.RollDeg, Is.EqualTo(0f));
            Assert.That(a.PitchDeg, Is.EqualTo(0f));
        }

        // ── 临界阻尼：阶跃收敛、无越冲（越界即船头点头的弹簧感，规格不许）──────────
        [Test]
        public void Damp_StepResponse_ConvergesWithoutOvershoot()
        {
            const float target = 1f;
            const float frequencyHz = 1f;
            const float dt = 1f / 60f;
            var s = new DampedScalar();
            float maxSeen = float.MinValue;
            for (int i = 0; i < 300; i++) // 5 s @60 fps，远超 1 Hz 临界阻尼整定时间
            {
                s = BuoyancyAttitudeSolver.Damp(s, target, frequencyHz, dt);
                if (s.Value > maxSeen) maxSeen = s.Value;
            }
            Assert.That(s.Value, Is.EqualTo(target).Within(0.01f), "must settle within 5 s at 1 Hz");
            Assert.That(maxSeen, Is.LessThanOrEqualTo(target + 0.02f), "critically damped step must not overshoot beyond bound");
        }

        [Test]
        public void Damp_SameInputSequence_ProducesBitwiseIdenticalTrajectory()
        {
            float[] Run()
            {
                var s = new DampedScalar();
                var path = new float[120];
                for (int i = 0; i < path.Length; i++)
                {
                    s = BuoyancyAttitudeSolver.Damp(s, Mathf.Sin(i * 0.1f), 0.8f, 1f / 60f);
                    path[i] = s.Value;
                }
                return path;
            }
            Assert.That(Run(), Is.EqualTo(Run()));
        }
    }
}
