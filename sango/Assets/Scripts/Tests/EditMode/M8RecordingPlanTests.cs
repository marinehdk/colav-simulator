using System.Linq;
using NUnit.Framework;
using Sango;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Input;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M8-B 出片管线 EditMode 测试（fixture 全合成，无场景实例）：①九段镜头脚本与三票制
    /// 材料清单逐行对齐；②段推进纯函数（边界/全段覆盖/越界）；③大气档切换指令映射
    /// （bridge-atmo 三步 vs 单段一档，NextAtmosphereTier 单源）；④段参数化解析；
    /// ⑤HUD 集中隐藏（canvas inactive / 捕获-还原对称；HudVisibility 在 Assembly-CSharp，
    /// asmdef 不引用预定义程序集——经共享 TestReflection 反射驱动）；⑥Recorder 配置契约
    /// （Constant 60 / CapFrameRate off / JPEG / 1080p / TaggedCamera——Runner 在
    /// Assembly-CSharp-Editor，经 TestReflection.FindLoadedType 反射构建真实
    /// RecorderControllerSettings 后断言，非常量复读）。
    /// </summary>
    public class M8RecordingPlanTests
    {
        // ── ① 九段完整性（M8-C §3 材料清单）─────────────────────────────────────────

        [Test]
        public void ThreeVoteNine_MatchesThreeVoteMaterialList()
        {
            var shots = M8ShotList.ThreeVoteNine;
            Assert.That(shots.Length, Is.EqualTo(9), "三票制材料 = 九段");

            var expectNames = new[] { "bridge-day", "bow-day", "chase-day", "topdown-day", "overlook-day", "bridge-atmo", "bridge-night", "chase-night", "overlook-night" };
            var expectViews = new[] { CameraView.Bridge, CameraView.Bow, CameraView.Chase, CameraView.TopDown, CameraView.Overlook, CameraView.Bridge, CameraView.Bridge, CameraView.Chase, CameraView.Overlook };
            var expectDur = new[] { 15f, 15f, 15f, 15f, 15f, 60f, 15f, 15f, 15f };
            for (int i = 0; i < 9; i++)
            {
                Assert.That(shots[i].Name, Is.EqualTo(expectNames[i]), $"段 {i} 名次漂移");
                Assert.That(shots[i].View, Is.EqualTo(expectViews[i]), $"{shots[i].Name} 机位漂移");
                Assert.That(shots[i].DurationSeconds, Is.EqualTo(expectDur[i]), $"{shots[i].Name} 时长漂移");
                Assert.That(shots[i].StartDemo, Is.True, $"{shots[i].Name} 应起航（自航/尾迹/常动目标）");
            }

            // 日段正午 / 夜段 h=0（号灯由 NavigationLightsCore.IsLightsOn 随时刻自动点亮）；夜段大气不动（表只改时刻）
            for (int i = 0; i < 6; i++)
                Assert.That(shots[i].TimeOfDayHours, Is.EqualTo(M8ShotList.DayHours), $"{shots[i].Name} 应为日段正午");
            for (int i = 6; i < 9; i++)
            {
                Assert.That(shots[i].TimeOfDayHours, Is.EqualTo(M8ShotList.NightHours), $"{shots[i].Name} 应为夜航 h=0");
                Assert.That(shots[i].Tier, Is.EqualTo(M7BMath.AtmosphereTier.HazyClear), $"{shots[i].Name} 夜段不改大气档");
            }
            Assert.That(M8ShotList.TotalDuration(shots), Is.EqualTo(180f).Within(1e-4f), "5×15 + 60 + 3×15 = 180");
        }

        // ── ② 段推进纯函数 ───────────────────────────────────────────────────────────

        [Test]
        public void SegmentAdvancement_BoundarySwitches_PastEndAndNegative()
        {
            var shots = M8ShotList.ThreeVoteNine;
            // 段边界：右开区间（t=15 落段 1，t=165 越过全片）
            Assert.That(M8ShotList.SegmentIndexAt(shots, 0f), Is.EqualTo(0));
            Assert.That(M8ShotList.SegmentIndexAt(shots, 14.99f), Is.EqualTo(0));
            Assert.That(M8ShotList.SegmentIndexAt(shots, 15f), Is.EqualTo(1));
            Assert.That(M8ShotList.SegmentIndexAt(shots, 74.99f), Is.EqualTo(4));
            Assert.That(M8ShotList.SegmentIndexAt(shots, 75f), Is.EqualTo(5), "bridge-atmo 起点");
            Assert.That(M8ShotList.SegmentIndexAt(shots, 134.99f), Is.EqualTo(5));
            Assert.That(M8ShotList.SegmentIndexAt(shots, 135f), Is.EqualTo(6), "bridge-night 起点");
            Assert.That(M8ShotList.SegmentIndexAt(shots, 150f), Is.EqualTo(7), "chase-night 起点");
            Assert.That(M8ShotList.SegmentIndexAt(shots, 179.99f), Is.EqualTo(8));
            Assert.That(M8ShotList.SegmentIndexAt(shots, 180f), Is.EqualTo(-1), "全片结束");
            Assert.That(M8ShotList.SegmentIndexAt(shots, -5f), Is.EqualTo(0), "负 t 容错归段 0");
            Assert.That(M8ShotList.TryStateAt(shots, 180f, out _), Is.False, "越界 TryStateAt = false");
        }

        [Test]
        public void SegmentAdvancement_FullTimelineCover_StateConsistent()
        {
            var shots = M8ShotList.ThreeVoteNine;
            float total = M8ShotList.TotalDuration(shots);
            int visited = 0;
            for (float t = 0f; t < total; t += 0.5f)
            {
                Assert.That(M8ShotList.TryStateAt(shots, t, out var s), Is.True, $"t={t} 应在片内");
                Assert.That(s.Index, Is.InRange(0, 8));
                Assert.That(s.Shot.Name, Is.EqualTo(M8ShotList.ThreeVoteNine[s.Index].Name));
                Assert.That(s.SecondsInto, Is.InRange(0f, s.Shot.DurationSeconds));
                visited++;
            }
            Assert.That(visited, Is.EqualTo(360), "0..180 步 0.5 全覆盖");
        }

        // ── ③ 大气档切换指令映射 ─────────────────────────────────────────────────────

        [Test]
        public void TierSchedule_AtmoSegmentThreeStep_OthersSingleShot()
        {
            var atmo = M8ShotList.ThreeVoteNine[5];
            Assert.That(atmo.Name, Is.EqualTo(M8ShotList.AtmoSegmentName));
            var schedule = M8ShotList.TierSchedule(atmo);
            Assert.That(schedule.Length, Is.EqualTo(3), "三档连续：HazyClear→Cumulonimbus→Thunderstorm");
            Assert.That(schedule[0].AtLocalSeconds, Is.EqualTo(0f));
            Assert.That(schedule[0].Tier, Is.EqualTo(M7BMath.AtmosphereTier.HazyClear));
            Assert.That(schedule[1].AtLocalSeconds, Is.EqualTo(M8ShotList.AtmoTierHoldSeconds), "每档 18s 含 3s 过渡（M8-C 表 #6）");
            Assert.That(schedule[1].Tier, Is.EqualTo(M7BMath.AtmosphereTier.Cumulonimbus));
            Assert.That(schedule[2].AtLocalSeconds, Is.EqualTo(2f * M8ShotList.AtmoTierHoldSeconds));
            Assert.That(schedule[2].Tier, Is.EqualTo(M7BMath.AtmosphereTier.Thunderstorm));
            // 循环语义与 N 键单源（M7BMath.NextAtmosphereTier）
            Assert.That(M7BMath.NextAtmosphereTier(schedule[0].Tier), Is.EqualTo(schedule[1].Tier));

            var day = M8ShotList.ThreeVoteNine[0];
            var single = M8ShotList.TierSchedule(day);
            Assert.That(single.Length, Is.EqualTo(1), "非 atmo 段 = 起始档一次应用");
            Assert.That(single[0].AtLocalSeconds, Is.EqualTo(0f));
            Assert.That(single[0].Tier, Is.EqualTo(day.Tier));
        }

        // ── ④ 段参数化解析 ───────────────────────────────────────────────────────────

        [Test]
        public void RunParams_ParseNameIndexAll_OverrideAndErrors()
        {
            Assert.That(M8ShotList.TryParseRunParams(null, null, out var all, out var err), Is.True, err);
            Assert.That(all.AllShots, Is.True, "空 = 九段连录");

            Assert.That(M8ShotList.TryParseRunParams("all", null, out var a2, out err), Is.True, err);
            Assert.That(a2.AllShots, Is.True);

            Assert.That(M8ShotList.TryParseRunParams("bridge-day", null, out var byName, out err), Is.True, err);
            Assert.That(byName.AllShots, Is.False);
            Assert.That(byName.ShotIndex, Is.EqualTo(0));

            Assert.That(M8ShotList.TryParseRunParams("BRIDGE-NIGHT", null, out _, out err), Is.True, err); // 大小写不敏感

            Assert.That(M8ShotList.TryParseRunParams("8", null, out var byIdx, out err), Is.True, err);
            Assert.That(byIdx.ShotIndex, Is.EqualTo(8));

            Assert.That(M8ShotList.TryParseRunParams("9", null, out _, out var err9), Is.False, "序号越界报错");
            Assert.That(err9, Does.Contain("out of [0,8]"));

            Assert.That(M8ShotList.TryParseRunParams("nope", null, out _, out var errName), Is.False, "未知段名报错");
            Assert.That(errName, Does.Contain("bridge-day").And.Contain("overlook-night"), "错误列出合法段名");

            Assert.That(M8ShotList.TryParseRunParams("chase-day", "5", out var overridden, out err), Is.True, err);
            Assert.That(overridden.SecondsOverride, Is.EqualTo(5f).Within(1e-5f), "验证段时长覆盖");

            foreach (var bad in new[] { "0", "-1", "x" })
            {
                Assert.That(M8ShotList.TryParseRunParams("chase-day", bad, out _, out var errSec), Is.False, $"M8_SECONDS '{bad}' 应报错");
                Assert.That(errSec, Does.Contain("M8_SECONDS"));
            }
        }

        // ── ⑤ HUD 集中隐藏（HudVisibility 在 Assembly-CSharp——经反射驱动）───────────

        [Test]
        public void HudVisibility_HideAllCanvasesInactive_RestoreSymmetric()
        {
            var hud = TestReflection.FindAssemblyCSharpType("Sango.HudVisibility");

            var c1 = new GameObject("M8TestCanvas1", typeof(Canvas));
            var c2 = new GameObject("M8TestCanvas2", typeof(Canvas));
            var child = new GameObject("M8TestCanvas1Child");
            child.transform.SetParent(c1.transform, false); // 整树失活语义：子对象随 canvas 走
            var preInactive = new GameObject("M8TestCanvasInactive", typeof(Canvas));
            preInactive.SetActive(false); // 先前已失活的 canvas 不得被 Restore 误恢复

            try
            {
                hud.GetMethod("Hide").Invoke(null, null);
                try
                {
                    Assert.That((bool)hud.GetProperty("IsHidden").GetValue(null), Is.True);
                    Assert.That(c1.activeInHierarchy, Is.False, "canvas 1 应整树失活");
                    Assert.That(child.activeInHierarchy, Is.False, "canvas 子对象应随树失活");
                    Assert.That(c2.activeInHierarchy, Is.False, "canvas 2 应失活");
                    Assert.That(preInactive.activeSelf, Is.False, "先前失活的 canvas 不参与捕获");
                }
                finally
                {
                    hud.GetMethod("Restore").Invoke(null, null);
                }

                Assert.That((bool)hud.GetProperty("IsHidden").GetValue(null), Is.False);
                Assert.That(c1.activeInHierarchy, Is.True, "Restore 应还原 canvas 1");
                Assert.That(c2.activeInHierarchy, Is.True, "Restore 应还原 canvas 2");
                Assert.That(preInactive.activeSelf, Is.False, "Restore 不得误恢复先前失活对象");
            }
            finally
            {
                Object.DestroyImmediate(c1);
                Object.DestroyImmediate(c2);
                Object.DestroyImmediate(preInactive);
            }
        }

        // ── ⑥ Recorder 配置契约（Runner 在 Assembly-CSharp-Editor——反射构建真实配置）──

        [Test]
        public void RecorderTakeSettings_Contract_Constant60Jpeg1080pCapOff()
        {
            var runner = TestReflection.FindLoadedType("Sango.Editor.M8RecordingRunner");
            var settings = (RecorderControllerSettings)runner
                .GetMethod("BuildTakeSettings")
                .Invoke(null, new object[] { "out/m8b-test_", 12f });
            try
            {
                Assert.That(settings.FrameRatePlayback, Is.EqualTo(FrameRatePlayback.Constant), "出片一律 Constant（Variable = 墙钟错位）");
                Assert.That(settings.FrameRate, Is.EqualTo(60f).Within(1e-4f), "1080p60 契约");
                Assert.That(settings.CapFrameRate, Is.False, "CapFrameRate 必须关（墙钟限速 = 时间轴错位根源）");

                var recorders = settings.RecorderSettings.ToList();
                Assert.That(recorders.Count, Is.EqualTo(1), "单录制器（Image Sequence）");
                var seq = (ImageRecorderSettings)recorders[0];
                Assert.That(seq.Enabled, Is.True);
                Assert.That(seq.OutputFormat, Is.EqualTo(ImageRecorderSettings.ImageRecorderOutputFormat.JPEG));
                Assert.That(seq.JpegQuality, Is.EqualTo(M8ShotList.JpegQuality));
                Assert.That(seq.OutputFile, Does.EndWith("_<Frame>"), "帧号通配（0000 起 4 位）");

                var cam = (CameraInputSettings)seq.imageInputSettings;
                Assert.That(cam.Source, Is.EqualTo(ImageSource.TaggedCamera), "HDRP 下 ActiveCamera 不可靠");
                Assert.That(cam.CameraTag, Is.EqualTo("MainCamera"));
                Assert.That(cam.OutputWidth, Is.EqualTo(1920));
                Assert.That(cam.OutputHeight, Is.EqualTo(1080));
            }
            finally
            {
                var toClean = settings.RecorderSettings.ToList(); // 先捕获（销毁后不可枚举）
                Object.DestroyImmediate(settings);
                foreach (var r in toClean)
                    Object.DestroyImmediate(r);
            }
        }
    }
}
