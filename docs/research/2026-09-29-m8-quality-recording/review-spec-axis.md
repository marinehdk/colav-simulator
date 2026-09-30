# M8 批规格轴评审（Spec axis）— b03f43dd..dd41aaab

- 日期：2026-09-29 ｜ 评审员：spec-axis ｜ 只读评审（未运行 Unity、未改代码文件）
- 范围：`b03f43dd..dd41aaab`（`effd36fb` M8-A quality tiers + tile streaming；`dd41aaab` M8-B recorder pipeline + HUD-off）
- 规格来源：handoff `/var/folders/.../T/sango-m8-handoff-20260929.md` §3（已确认存在）；`docs/research/2026-09-29-m8b-recorder-linux-pipeline.md`；`docs/research/2026-09-29-m8c-three-vote-protocol.md` §3
- 方法：`git show`/`git diff` 逐提交审 + 全仓 grep 键位账本独立复核 + 场景 YAML 对象级比对 + 测试属性静态计数

## 结论：approve-with-fixes

两批与派发规格逐条对照全部命中，无 high 级违反。工程纪律六项（直提 main / 场景同批回存 / HDRPDefaultResources·M1·M2E·VolumeProfile 未 add / 键位账本注释 / EditMode +17+7 / bootstrapper 契约方法未动）全部 verified。4 条 low findings 均为有档可查的解释性偏差或死常量，1 条 medium 为批次自报的验证挂账（swap 路径实机证据），不阻塞合并。

## 逐条规格对照表

### M8-A（handoff §3 M8-A，1-3 项）

| 规格点 | 结论 | 证据 |
|---|---|---|
| Mac 低配档（邻域 tile+装饰降档） | verified | `sango/Assets/Scripts/Runtime/Vessels/M8QualityProfile.cs:41-60`（Low：近带恒开 + 外环逐 tile 迟滞 latch 13km/16km + treeDistance 2000→1500/detail 40/pixelError 6/软→硬影）；装饰组随宿主 tile（`M8TileStreaming.cs:135-140`） |
| a4000 全质档 | verified | `M8QualityProfile.cs:47-53`（High = M7 终态钉死：近带 4 亮/交叠 9 隐藏/外环 16 常开/树距基线回写零漂移 `M8TileStreaming.cs:302-338`） |
| 两档参数表化 | deviation(low) | 代码静态常量表而非规格所列 "ScriptableObject 或 bootstrapper 注入"；取舍在码有档（`M8QualityProfile.cs:13-16`"不引入 ScriptableObject 资产——Simplicity First"）；场景引用表仍由 bootstrapper 构建期注入（`M6StraitSceneBootstrapper.cs` `WireQualityStreaming`） |
| 构建期断言档位契约 | verified | `M8QualityProfile.cs:127-189` `Validate()`（两档互异/装饰表对 M7BackdropMath 字面量/渔排 ⊂ 宿主矩形/迟滞 sanity）+ `WireQualityStreaming` throw（tile 计数 4/9/16、近带 bbox=±12km、装饰组逐一解析） |
| 远景环 9 inactive tile 流送接棒（M6 遗留） | verified | 交叠 9 = `M8StreamGroup.Overlap`（bootstrapper 按 `FarTileUnderNearBand` 分组）；High 档参考点出带 >2km 整组接管、近带让位、互斥防 z-fight（`M8TileStreaming.cs:97-141`）；分帧 ≤1 SetActive/帧（`M8StreamingChangeQueue`，`M8TileStreaming.cs:149-213`） |
| Mac 档 fps 闸门 ≥30 保住 | verified(证据在批外) | 设计侧：分帧预算+零稳态分配；实测侧：`docs/research/2026-09-29-m8-quality-recording/m8a-acceptance.md:20-21`（干净协议 High 60.0×6、Low 60.0×5 连读）——该验收档在工作区未随批提交，见 finding F5 |
| 质量档位进面板（QualityGUI 或 WeatherGUI 扩展） | verified | `WeatherGUI.cs` diff：Quality (M8) High/Low 下拉 + 回调写 `M8Quality` 静态源 → `streamer.ApplyTier` → Update 镜像；L 键循环 `WeatherGUI.cs:221-225` |

### M8-B（研究档技术契约 + 三票制 §3 镜头脚本契约）

| 规格点 | 结论 | 证据 |
|---|---|---|
| com.unity.recorder 5.1.7 | verified | `sango/Packages/manifest.json`（`"com.unity.recorder": "5.1.7"`）+ `packages-lock.json`（version 5.1.7, depth 0, registry） |
| RecorderController 仅 Play Mode | verified | 宿主在 `PlayModeStateChange.EnteredPlayMode` 时机创建（`M8RecordingRunner.cs:121-149` `M8RecordingBoot`）；`PrepareRecording/StartRecording` 均在 Play Mode 宿主内（`M8RecordingRunner.cs:229-231`）；脚本在 `Assets/Scripts/Editor/`（编辑器程序集，研究档 §Q1 要求） |
| Constant 60fps 自动 captureDeltaTime | verified | `M8RecordingRunner.cs:87-88`（`FrameRatePlayback.Constant` + `FrameRate=60`，注释明示 Recorder 自设 captureDeltaTime=1/60）；业务侧只读 `Time.time`（`M8RecordingRunner.cs:232,249`），全文件无墙钟读取 |
| 禁 CapFrameRate | verified | `M8RecordingRunner.cs:89` `controllerSettings.CapFrameRate = false` |
| TaggedCamera（HDRP） | verified | `M8RecordingRunner.cs:93-94`（`ImageSource.TaggedCamera` + `CameraTag="MainCamera"`；复用 M6 主相机既有 tag，零场景改动） |
| Image Sequence JPEG + ffmpeg | verified | `M8RecordingRunner.cs:100-102`（JPEG、quality 95、`OutputFile`+Frame 通配）；ffmpeg 转码命令与 ffprobe 实测（1920×1080/60fps/12.0167s/721 帧）在 `docs/research/evidence/m8b-recorder-20260929/README.md`；验证段 mp4 已随批提交 |
| 九段镜头脚本对齐三票制 §3 | verified(逐行) | `M8ShotList.cs:50-61` 与 §3 表逐行一致：9 段名/机位（Bridge/Bow/Chase/TopDown/Overlook×日 + atmo=Bridge + 夜 Bridge/Chase/Overlook）/时长（5×15+60+3×15=180s，测试钉死 `M8RecordingPlanTests.cs:24-52`）/时段（日 12h、夜 h=0）/大气（日 HazyClear、atmo 三档连录 18s 步进 `M8ShotList.cs:75-88`）。内容要求项见 findings F1/F2 |
| HUD-off：出片路径强制 off+演示热键 | verified | 录制宿主启录前 `HudVisibility.Hide()`、结束 `Restore()`（`M8RecordingRunner.cs:185,293`）；H 热键 `WeatherGUI.cs:226-231`；覆盖 Canvas 树 inactive + FpsProbe/DetectionOverlay 禁用 + VectorArrows 收箭（`HudVisibility.cs:28-105`）；实拍证据 `m8b-overlook-hud-hidden.jpg`（验收档） |
| batchmode -executeMethod 入口+单段参数化 | verified | `-executeMethod Sango.Editor.M8RecordingRunner.RunFromCli`（`M8RecordingRunner.cs:41-63`）；`M8_SHOT=all\|段名\|序号`、`M8_SECONDS`、`M8_OUT` 环境变量（`M8ShotList.cs:161-211` 解析纯函数）；evidence README 给出完整复跑命令行 |

### M8ShotList 九段 vs 三票制 §3 表逐行

| §3 行 | 片段名 | 机位 | 时段/大气 | 时长 | 结论 |
|---|---|---|---|---|---|
| 1 | bridge-day | Bridge | HazyClear | 15s | ✓（`M8ShotList.cs:52`） |
| 2 | bow-day | Bow | HazyClear | 15s | ✓（:53） |
| 3 | chase-day | Chase | HazyClear | 15s | ✓（:54） |
| 4 | topdown-day | TopDown | HazyClear | 15s | ✓（:55） |
| 5 | overlook-day | Overlook | HazyClear | 15s | ✓（:56） |
| 6 | bridge-atmo | Bridge | N 循环三档 | 60s（每档 18s 含过渡） | ✓（:57；档切换 0/18/36s，末档 24s 到段尾——解释性偏差 F3） |
| 7 | bridge-night | Bridge | h=0 | 15s | ✓（:58；直接置 timeOfDayHours=0 = T×2 终点等价） |
| 8 | chase-night | Chase | h=0 | 15s | ✓（:59） |
| 9 | overlook-night | Overlook | h=0 | 15s | ✓（:60） |
| 固定条件 | HUD 全隐 / 1080p / ≥30fps / 每段静置 3s | — | — | — | HUD/1080p verified（契约常量 `M8ShotList.cs:17-25` + 测试）；"静置 3s"实现为过渡窗解释，`SettleSeconds` 死常量——F1 |

### 工程纪律（两批共同）

| 规格点 | 结论 | 证据 |
|---|---|---|
| 直提 main | verified | 两提交均在 main（`git branch --contains` = main），range 内 0 merge commit，HEAD=main=dd41aaab |
| 场景回存同批（M6-Strait.unity 随批） | verified | 两提交均含 `M6-Strait.unity`；M8-A 净变更=恰 +1 GO +1 MonoBehaviour（对象计数 85→86 GO / 60→61 Mono，名集 diff 仅 +`M8 Tile Streaming`），与提交声明一致；M8-B 场景 delta 为全量 fileID 重掷+重排序，名集/类分布/对象计数逐项相等（零净对象变更） |
| 永不提交 sango/Assets/HDRPDefaultResources/* | verified | 两提交 name-status 均无；工作区仍留置为未提交噪声（`git status`，符合 handoff §7 惯例） |
| M1/M2E 场景与 VolumeProfile 未 add | verified | 两提交均无 M1-Weather.unity / M2E-Encounter.unity / *GlobalVolumeProfile.asset（M8-A 提交信息并明示 M6-GlobalVolumeProfile 纯字段重排不入批） |
| 热键新增加全仓账本核对注释 | verified | `WeatherGUI.cs:221-231`（L、H 两处带账本注释）；本次独立 `git grep Input.GetKeyDown` @dd41aaab 复核：已占键=0-9/T/F/N/G/V/B/C/A/P/Q/E/Z/X/Space/R/±=,./Enter+keypad，**L、H 确为空闲新增，无冲突** |
| EditMode 测试 308→325(+17 M8-A)、325→332(+7 M8-B) | verified(静态) | `[Test]` 计数：M8QualityProfileTests 7 + M8TileStreamingPlanTests 10 = +17；M8RecordingPlanTests 7 = +7；无 `[TestCase]` 多参；308+17+7=332 与两批声明一致（套件实跑未复验——本评审不运行 Unity，批次自报 325/325、332/332 全绿） |
| bootstrapper batchmode 契约方法不许改 | verified | `git show effd36fb` 对 `M6StraitSceneBootstrapper.cs` 纯增量（零删行）；`Build`(:75)/`BuildStraitPlayer`(:441) 原样 |

## Findings

| # | where | what | evidence | severity |
|---|---|---|---|---|
| F1 | `sango/Assets/Scripts/Runtime/Vessels/M8ShotList.cs:25` + `M8RecordingRunner.cs:216-223` | `SettleSeconds=3f` 声明后全仓无消费者（grep 仅此一处）；三票制 §3 固定条件"每段静置 3s 后开始有效内容"被实现为"机位过渡 1s/大气过渡 3s 落在前 3s 窗内"（`M8ShotList.cs:24` 注释自述），起录即 Toggle 自航+切机位，并非先静置后内容。二选一收口：真正延迟 3s 起内容，或删常量并把该解释回写三票制档 | 声明处唯一出现；Runner t=0 即 ApplyTier/SetView/Toggle | low |
| F2 | `M8ShotList.cs:52-60`、`M8RecordingRunner.cs:222-223` | §3 内容要求列未脚本化：row1"一次 15° 转向"、row2"擦舷通过浮标"、row5"渡轮/拖轮入画"无调度或断言，仅 `StartDemo=true`（G 自航）被强制；内容依赖 M6 固定航线涌现，批内未取证 15s 窗内是否真出现 15° 转向 | 九段定义只有名/机位/档/时刻/时长/StartDemo 六字段 | low |
| F3 | `M8ShotList.cs:75-88` | bridge-atmo 档切换 0/18/36s → 末档 Thunderstorm 实持 24s，§3 写"每档 18s"（3×18=54s 与 60s 总长自相矛盾）；实现取"末档保持到段尾"并在注释有档（:80）。属规格自身不自洽下的合理解释，建议回写协议档钉死 | `TierSchedule` 三项 `AtLocalSeconds` 0/18/36 | low |
| F4 | `M8QualityProfile.cs:13-16` | 两档参数表化为代码静态常量，非派发规格所列 "ScriptableObject 或 bootstrapper 注入" 两形态；取舍有档（Simplicity First）且构建期断言覆盖契约，属已声明偏差——评审接受，记录在案 | 文件头注释明示不引入 SO 资产 | low |
| F5 | `docs/research/2026-09-29-m8-quality-recording/m8a-acceptance.md:20-21,29` | fps 闸门 ≥30 的双档实测（High 60×6/Low 60×5）与 swap 挂账均在**未提交**验收档里（不在被审 range 内）；且 swap 路径（船出近带 >2km 交叠 9 接管）无实机证据——12s 验证段行程 ≈60-120m 触不到 2km 出带，验收档自记"挂账：M8-B … 顺带取证"，M8-B 验收档未见该取证落账。EditMode 17 项合成 fixture 已背书逻辑，缺运行时一行 `[Sango.M8]` 日志证据 | m8a-acceptance.md:29 挂账原文；git status 显示 m8a/m8b-acceptance.md 未跟踪 | medium |
| F6 | `sango/Assets/Scenes/M6-Strait.unity`（dd41aaab） | M8-B 场景 delta 9202 行为 bootstrapper 重建式回存导致的**全量 fileID 重掷**，非普通 resave；已验证名集恒等、类分布恒等（86 GO/86 Transform/61 Mono/29 Tile/15 PrefabInstance…）、净对象零变更。属性级漂移因 ID 重掷不可穷尽 diff——纪律（场景同批）满足，风险提示记录 | 对象级比对（名集/锚集/类计数三口径） | low |

## 复核命令备忘

```bash
git diff b03f43dd..dd41aaab --stat
git show effd36fb -- sango/Assets/Scripts/Editor/M6StraitSceneBootstrapper.cs   # 纯增量核验
git grep -n "GetKeyDown" dd41aaab -- 'sango/Assets/Scripts'                     # 键位账本复核
# 场景对象级比对：git show <rev>:sango/Assets/Scenes/M6-Strait.unity 落临时文件后
#   比对 m_Name 集合、^--- !u!<class> 锚计数
```
