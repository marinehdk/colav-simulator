using System;
using System.Linq;
using NUnit.Framework;
using Sango;
using UnityEditor.Recorder;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M8-C 三票 round 1 根因修复（出片内容驱动缺口）EditMode 测试：
    /// ①段前就绪窗纯判据——自航速度达标（80% 巡航线 + 巡航 ≤0 防御）；
    /// ②过渡完成判据——与 M7BMath preset transitionSeconds 单源对齐（三档统一 3 s）；
    /// ③TAA 帧判据 + 就绪窗超时 fail-safe 判据边界；
    /// ④pre-roll 不进录制时长的时序断言——九段真实 RecorderControllerSettings 时间区间
    ///   = RecordedDuration（表内时长/M8_SECONDS 覆盖），反射构建真实配置（Runner 在
    ///   Assembly-CSharp-Editor，经 TestReflection.FindLoadedType，M8RecordingPlanTests 先例）；
    /// ⑤段状态目标完备性——每段时刻/大气档协议对齐、TierSchedule[0] 即段目标、过渡时长
    ///   必在 fail-safe 超时窗内（就绪窗可达完成，不靠超时放行）。
    /// </summary>
    public class M8ShotReadinessTests
    {
        // ── ① 速度就绪判据 ───────────────────────────────────────────────────────────

        [Test]
        public void SpeedReady_EightyPercentCruiseBoundary_DegenerateCruiseFails()
        {
            const float cruise = 8f; // M6 海峡主角船巡航（WaypointFollower.cruiseSpeedMps）
            float line = cruise * M8ShotList.ReadySpeedFraction;
            Assert.That(line, Is.EqualTo(6.4f).Within(1e-4f), "达标线 = 8 × 0.8 = 6.4 m/s");
            Assert.That(M8ShotList.SpeedReady(6.39f, cruise), Is.False, "线下不就绪");
            Assert.That(M8ShotList.SpeedReady(6.4f, cruise), Is.True, "等号就绪（≥ 语义）");
            Assert.That(M8ShotList.SpeedReady(9f, cruise), Is.True, "超巡航恒就绪");

            // 防御：巡航 ≤ 0 = 无巡航契约，静止船不得假通过（必须落到超时日志，不静默出片）
            Assert.That(M8ShotList.SpeedReady(0f, 0f), Is.False);
            Assert.That(M8ShotList.SpeedReady(5f, 0f), Is.False, "巡航 0 时速度值不参判");
            Assert.That(M8ShotList.SpeedReady(5f, -1f), Is.False);

            // decal 速度门相容：80% 巡航稳在 M4 门限（0.5 m/s）与全强（5 m/s）之上——尾迹清晰可见
            Assert.That(line, Is.GreaterThan(0.5f).And.GreaterThan(5f), "达标线应过 decal 全强速度");
        }

        // ── ② 过渡完成判据（与 preset transitionSeconds 单源）─────────────────────────

        [Test]
        public void TransitionSettled_ElapsedWindow_AlignedWithPresetTransitionSeconds()
        {
            // 三档 preset 过渡时长即判据的时间窗单源（M8ShotList 不复刻数值）
            foreach (M7BMath.AtmosphereTier tier in Enum.GetValues(typeof(M7BMath.AtmosphereTier)))
            {
                var p = M7BMath.AtmospherePresetFor(tier);
                Assert.That(p.transitionSeconds, Is.EqualTo(3f).Within(1e-4f), $"{tier} 过渡 3 s");
                Assert.That(M8ShotList.TransitionSettled(p.transitionSeconds - 0.01f, p.transitionSeconds), Is.False, $"{tier} 过渡未完不就绪");
                Assert.That(M8ShotList.TransitionSettled(p.transitionSeconds, p.transitionSeconds), Is.True, $"{tier} elapsed ≥ 过渡时长即就绪（等号）");
            }
            // 退化：过渡时长 ≤ 0 = 即时完成
            Assert.That(M8ShotList.TransitionSettled(0f, 0f), Is.True);
            Assert.That(M8ShotList.TransitionSettled(0f, -1f), Is.True);
        }

        // ── ③ TAA 帧判据 + 超时 fail-safe 判据 ───────────────────────────────────────

        [Test]
        public void FramesSettledAndReadyTimeout_Boundaries()
        {
            Assert.That(M8ShotList.FramesSettled(M8ShotList.TaaSettleFrames - 1), Is.False, "差 1 帧不就绪");
            Assert.That(M8ShotList.FramesSettled(M8ShotList.TaaSettleFrames), Is.True, "等号就绪（≥30 渲染帧）");
            Assert.That(M8ShotList.FramesSettled(M8ShotList.TaaSettleFrames + 100), Is.True);

            Assert.That(M8ShotList.ReadyWindowExpired(M8ShotList.ReadyTimeoutSeconds - 0.01f), Is.False, "窗内仍等待");
            Assert.That(M8ShotList.ReadyWindowExpired(M8ShotList.ReadyTimeoutSeconds), Is.True, "超时放行（fail-safe，batchmode 不挂死）");
            Assert.That(M8ShotList.ReadyTimeoutSeconds, Is.GreaterThan(3f), "超时窗必须容得下 3 s 大气过渡");
        }

        // ── ④ pre-roll 不进录制时长（时序断言：真实 Recorder 区间 = RecordedDuration）──

        [Test]
        public void RecordedDuration_PreRollExcluded_RecorderTimeIntervalMatchesTable()
        {
            var shots = M8ShotList.ThreeVoteNine;
            float total = 0f;
            for (int i = 0; i < shots.Length; i++)
            {
                var shot = shots[i];
                Assert.That(M8ShotList.RecordedDuration(shot, 0f), Is.EqualTo(shot.DurationSeconds).Within(1e-4f),
                    $"{shot.Name} 无覆盖时录制时长 = 表内时长（pre-roll 不进）");
                Assert.That(M8ShotList.RecordedDuration(shot, 5f), Is.EqualTo(5f).Within(1e-4f),
                    $"{shot.Name} M8_SECONDS 覆盖优先");
                total += M8ShotList.RecordedDuration(shot, 0f);
            }
            Assert.That(total, Is.EqualTo(M8ShotList.TotalDuration(shots)).Within(1e-3f), "全片录制时长不含就绪窗");
            Assert.That(total, Is.EqualTo(180f).Within(1e-3f), "5×15 + 60 + 3×15 = 180（协议档注记不变）");

            // 真实 RecorderControllerSettings 时间区间断言（九段逐一）：[0, RecordedDuration]。
            // 区间存于私有序列化字段 m_StartTime/m_EndTime（recorder 子项的 StartTime/EndTime 由
            // internal ApplyGlobalSetting 播发——反射读 controller settings 源字段，契约直读）。
            var runner = TestReflection.FindLoadedType("Sango.Editor.M8RecordingRunner");
            var build = runner.GetMethod("BuildTakeSettings");
            var startField = typeof(RecorderControllerSettings).GetField("m_StartTime", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            var endField = typeof(RecorderControllerSettings).GetField("m_EndTime", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            Assert.That(startField, Is.Not.Null, "RecorderControllerSettings.m_StartTime 字段在（recorder 包 5.1.7）");
            Assert.That(endField, Is.Not.Null, "RecorderControllerSettings.m_EndTime 字段在");
            foreach (var shot in shots)
            {
                float duration = M8ShotList.RecordedDuration(shot, 0f);
                var settings = (RecorderControllerSettings)build.Invoke(null, new object[] { $"out/{shot.Name}_", duration });
                try
                {
                    float start = (float)startField.GetValue(settings);
                    float end = (float)endField.GetValue(settings);
                    Assert.That(start, Is.EqualTo(0f).Within(1e-4f), $"{shot.Name} 区间起点 0");
                    Assert.That(end - start, Is.EqualTo(duration).Within(1e-4f),
                        $"{shot.Name} 录制区间 = 表内时长——就绪窗等待不折算进录制时间轴");
                }
                finally
                {
                    var toClean = settings.RecorderSettings.ToList(); // 先捕获（销毁后不可枚举）
                    UnityEngine.Object.DestroyImmediate(settings);
                    foreach (var r in toClean)
                        UnityEngine.Object.DestroyImmediate(r);
                }
            }
        }

        // ── ⑤ 段状态目标完备性（时刻/大气档协议对齐 + 段首应用即目标 + 过渡可达完成）────

        [Test]
        public void SegmentStateTargets_Complete_TransitionReachableWithinTimeoutWindow()
        {
            var shots = M8ShotList.ThreeVoteNine;
            for (int i = 0; i < shots.Length; i++)
            {
                var shot = shots[i];

                // 时刻目标协议：日段/atmo 段 = 正午 12，夜段 = 0（号灯阈值生效即可见）
                float expectHours = i >= 6 ? M8ShotList.NightHours : M8ShotList.DayHours;
                Assert.That(shot.TimeOfDayHours, Is.EqualTo(expectHours), $"{shot.Name} 时刻目标漂移");

                // 大气档目标合法 + 段首切换即目标档（TierSchedule[0] 是 Runner 起段实际应用值）
                Assert.That(Enum.IsDefined(typeof(M7BMath.AtmosphereTier), shot.Tier), Is.True, $"{shot.Name} 大气档未定义");
                var schedule = M8ShotList.TierSchedule(shot);
                Assert.That(schedule.Length, Is.GreaterThanOrEqualTo(1));
                Assert.That(schedule[0].AtLocalSeconds, Is.EqualTo(0f), $"{shot.Name} 目标档在段首应用");
                Assert.That(schedule[0].Tier, Is.EqualTo(shot.Tier), $"{shot.Name} 段首应用档 = 段目标档");

                // 过渡必在 fail-safe 窗内可达完成——夜段一致性不靠超时放行
                float transition = M7BMath.AtmospherePresetFor(schedule[0].Tier).transitionSeconds;
                Assert.That(transition, Is.LessThan(M8ShotList.ReadyTimeoutSeconds), $"{shot.Name} 过渡窗超出就绪超时窗");
            }
        }
    }
}
