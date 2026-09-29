using System.Globalization;

namespace Sango
{
    /// <summary>
    /// M8-B 镜头脚本核心（纯数据 + 纯函数，无引擎调用——EditMode 直测，Sango.Vessels 程序集）。
    /// 九段与 M8-C 三票制材料清单逐行对齐（docs/research/2026-09-29-m8c-three-vote-protocol.md §3）：
    /// 五机位日间各段（Bridge/Bow/Chase/TopDown/Overlook，HazyClear 正午）+ 大气三档连续段
    /// （bridge-atmo：HazyClear→Cumulonimbus→Thunderstorm 程序化切换，N 键同源 NextAtmosphereTier）
    /// + 夜航三段（h=0，号灯/浮标灯由 NavigationLightsCore.IsLightsOn 随时刻自动点亮）。
    /// 消费方：Sango.Editor.M8RecordingRunner（RecorderController 逐段驱动）。
    /// 时钟契约：录制时间轴只读 Time.time——Recorder Constant 60 自动设
    /// Time.captureDeltaTime=1/60（渲染与游戏时间解耦，研究档 Q2），业务代码禁读墙钟。
    /// </summary>
    public static class M8ShotList
    {
        // ── 录制契约常量（Runner 据此构建 RecorderControllerSettings——单源；测试断言同值）──
        public const int RecordingFps = 60;         // Constant 播放（Time.captureDeltaTime=1/60 由 Recorder 自设）
        public const int RecordingWidth = 1920;     // 1080p60（M8-C 材料固定条件）
        public const int RecordingHeight = 1080;
        public const int JpegQuality = 95;          // Image Sequence JPEG（跨机一致格式；成片 ffmpeg 转 H.264）
        public const string CameraTag = "MainCamera"; // Recorder TaggedCamera 源（HDRP 下 ActiveCamera 不可靠，研究档 Q1）；M6 主相机 tag 同款，零场景改动

        /// <summary>段首静置秒（M8-C 材料条件：每段静置 3s 后开始有效内容——机位过渡 1s/大气过渡 3s 落在此窗内）。</summary>
        public const float SettleSeconds = 3f;

        // ── 大气三档连续段节奏（M8-C 表 #6：60s，每档 18s 含 3s 过渡；末档 Thunderstorm 保持到段尾）──
        public const string AtmoSegmentName = "bridge-atmo";
        public const float AtmoTierHoldSeconds = 18f;

        /// <summary>昼/夜时刻锚（M8-C：日段默认正午；夜段 T×2 至 h=0——号灯可见）。</summary>
        public const float DayHours = 12f;
        public const float NightHours = 0f;

        /// <summary>单个镜头段（不可变值）。</summary>
        public struct Shot
        {
            public string Name;                  // 片段名（成片 m8c-&lt;name&gt;.mp4 命名源）
            public CameraView View;              // 机位（CameraRig.SetView 消费）
            public M7BMath.AtmosphereTier Tier;  // 起始大气档
            public float TimeOfDayHours;         // 0 = 夜航
            public float DurationSeconds;        // 段时长（含段首静置）
            public bool StartDemo;               // 起段时 Toggle() 主船自航（G 键同源；九段全 true：日段内容要求自航、夜段尾迹可读性、atmo 段保持场景常动）
        }

        /// <summary>
        /// 三票制九段清单（顺序 = M8-C §3 表行序；机位/大气/时刻/时长逐行同源）。
        /// 夜段大气保持默认 HazyClear——M8-C 表夜段只改时刻（T×2 至 h=0），不改大气档。
        /// </summary>
        public static readonly Shot[] ThreeVoteNine =
        {
            new Shot { Name = "bridge-day",     View = CameraView.Bridge,   Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = DayHours,   DurationSeconds = 15f, StartDemo = true },
            new Shot { Name = "bow-day",        View = CameraView.Bow,      Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = DayHours,   DurationSeconds = 15f, StartDemo = true },
            new Shot { Name = "chase-day",      View = CameraView.Chase,    Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = DayHours,   DurationSeconds = 15f, StartDemo = true },
            new Shot { Name = "topdown-day",    View = CameraView.TopDown,  Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = DayHours,   DurationSeconds = 15f, StartDemo = true },
            new Shot { Name = "overlook-day",   View = CameraView.Overlook, Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = DayHours,   DurationSeconds = 15f, StartDemo = true },
            new Shot { Name = AtmoSegmentName,  View = CameraView.Bridge,   Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = DayHours,   DurationSeconds = 60f, StartDemo = true },
            new Shot { Name = "bridge-night",   View = CameraView.Bridge,   Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = NightHours, DurationSeconds = 15f, StartDemo = true },
            new Shot { Name = "chase-night",    View = CameraView.Chase,    Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = NightHours, DurationSeconds = 15f, StartDemo = true },
            new Shot { Name = "overlook-night", View = CameraView.Overlook, Tier = M7BMath.AtmosphereTier.HazyClear, TimeOfDayHours = NightHours, DurationSeconds = 15f, StartDemo = true },
        };

        /// <summary>大气档切换指令（段内局部时刻 + 目标档；消费方调 WeatherController.ApplyAtmosphereTier）。</summary>
        public struct TierSwitch
        {
            public float AtLocalSeconds;
            public M7BMath.AtmosphereTier Tier;
        }

        /// <summary>
        /// 段内大气切换时刻表（纯函数）。bridge-atmo = 起始档 + 每满 AtmoTierHoldSeconds 顺推一档
        /// （M7BMath.NextAtmosphereTier = N 键循环语义单源）；其余段 = 起始档一次应用。
        /// 消费方在段首应用全部 AtLocalSeconds==0 项，其余到点应用。
        /// </summary>
        public static TierSwitch[] TierSchedule(in Shot shot)
        {
            if (shot.Name != AtmoSegmentName)
                return new[] { new TierSwitch { AtLocalSeconds = 0f, Tier = shot.Tier } };

            // bridge-atmo：档数 = ceil(duration/hold) 封顶 3（60/18 → 3 档，末档保持到段尾）
            var s = new[]
            {
                new TierSwitch { AtLocalSeconds = 0f,                            Tier = shot.Tier },
                new TierSwitch { AtLocalSeconds = AtmoTierHoldSeconds,           Tier = M7BMath.NextAtmosphereTier(shot.Tier) },
                new TierSwitch { AtLocalSeconds = 2f * AtmoTierHoldSeconds,      Tier = M7BMath.NextAtmosphereTier(M7BMath.NextAtmosphereTier(shot.Tier)) },
            };
            return s;
        }

        /// <summary>全片总时长（秒）。</summary>
        public static float TotalDuration(Shot[] shots)
        {
            float total = 0f;
            for (int i = 0; i < shots.Length; i++) total += shots[i].DurationSeconds;
            return total;
        }

        /// <summary>段前缀累计时长（段 index 之前各段时长和）。</summary>
        public static float PrefixDuration(Shot[] shots, int index)
        {
            float prefix = 0f;
            for (int i = 0; i < index && i < shots.Length; i++) prefix += shots[i].DurationSeconds;
            return prefix;
        }

        /// <summary>
        /// 段推进纯函数：录制时间 t → 段索引。t&lt;0 按段 0（未起录容错）；t ≥ 总时长 → −1（全片结束）。
        /// </summary>
        public static int SegmentIndexAt(Shot[] shots, float t)
        {
            if (t < 0f) t = 0f;
            float acc = 0f;
            for (int i = 0; i < shots.Length; i++)
            {
                acc += shots[i].DurationSeconds;
                if (t < acc) return i;
            }
            return -1;
        }

        /// <summary>段推进纯函数：t → 段索引 + 段内局部时刻（当前段 Shot 一并带出；全片结束返回 false）。</summary>
        public static bool TryStateAt(Shot[] shots, float t, out SegmentState state)
        {
            int index = SegmentIndexAt(shots, t);
            if (index < 0)
            {
                state = default;
                return false;
            }
            state = new SegmentState
            {
                Index = index,
                Shot = shots[index],
                SecondsInto = t - PrefixDuration(shots, index),
            };
            return true;
        }

        public struct SegmentState
        {
            public int Index;
            public Shot Shot;
            public float SecondsInto;
        }

        // ── 运行参数解析（a4000 按段跑：环境变量 M8_SHOT/M8_SECONDS → 段索引/时长覆盖）──────

        /// <summary>解析后的运行参数（Runner 消费）。AllShots=true 时 ShotIndex 无效。</summary>
        public struct RunParams
        {
            public bool AllShots;
            public int ShotIndex;
            public float SecondsOverride; // ≤0 = 不覆盖（用表内时长）
        }

        /// <summary>
        /// 参数化解析（纯函数，Invariant 文化为 a4000/本机脚本契约）。
        /// shotSpec：空/"all" = 九段连录；段名（大小写不敏感）或 0-8 序号 = 单段；未知值报错并列出合法名。
        /// secondsSpec：空 = 不覆盖；&gt;0 数值 = 覆盖段时长（冒烟/验证段用）。
        /// </summary>
        public static bool TryParseRunParams(string shotSpec, string secondsSpec, out RunParams p, out string error)
        {
            p = default;
            error = null;

            if (string.IsNullOrEmpty(shotSpec) || shotSpec.ToLowerInvariant() == "all")
            {
                p.AllShots = true;
            }
            else
            {
                int byName = -1;
                for (int i = 0; i < ThreeVoteNine.Length; i++)
                {
                    if (string.Equals(ThreeVoteNine[i].Name, shotSpec, System.StringComparison.OrdinalIgnoreCase))
                    {
                        byName = i;
                        break;
                    }
                }
                if (byName >= 0)
                {
                    p.ShotIndex = byName;
                }
                else if (int.TryParse(shotSpec, NumberStyles.Integer, CultureInfo.InvariantCulture, out int idx))
                {
                    if (idx < 0 || idx >= ThreeVoteNine.Length)
                    {
                        error = $"shot index {idx} out of [0,{ThreeVoteNine.Length - 1}]";
                        return false;
                    }
                    p.ShotIndex = idx;
                }
                else
                {
                    error = $"unknown shot '{shotSpec}' — valid: all | " + string.Join(" | ", ShotNames());
                    return false;
                }
            }

            if (!string.IsNullOrEmpty(secondsSpec))
            {
                if (!float.TryParse(secondsSpec, NumberStyles.Float, CultureInfo.InvariantCulture, out float sec) || sec <= 0f)
                {
                    error = $"invalid M8_SECONDS '{secondsSpec}' — must be > 0";
                    return false;
                }
                p.SecondsOverride = sec;
            }
            return true;
        }

        /// <summary>段名表（错误提示与测试同源）。</summary>
        public static string[] ShotNames()
        {
            var names = new string[ThreeVoteNine.Length];
            for (int i = 0; i < ThreeVoteNine.Length; i++) names[i] = ThreeVoteNine[i].Name;
            return names;
        }
    }
}
