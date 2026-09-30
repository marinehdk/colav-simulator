# M8 批标准轴评审（Standards axis）

- 评审范围：`b03f43dd..dd41aaab`（effd36fb M8-A；dd41aaab M8-B），sango/ 代码增量
- 评审日期：2026-09-29
- 标尺：M4-M7 同类代码（M7BackdropMath / M7BMath / M7BackdropBuilder / M6StraitSceneBootstrapper / NavigationLightsSidelightSideTests / WeatherGUI.HandleHotkeys / FramePublisher）

## 结论：approve-with-fixes

分层、契约、测试风格、每帧分配、日志账本、注释、幂等七项惯例中六项完全合规；一项（Recorder 会话释放）有可指认违规，修一行级即可收口。

## 逐惯例对照

| 惯例 | 结论 | 证据 |
|---|---|---|
| 1. 纯函数/薄壳分层 | 合规 | M8ShotList.cs 全文件无 `using UnityEngine`（纯数据+纯函数，Runtime 直测）；判据在 M8TileStreamingPlan / M8StreamingChangeQueue（纯 C#，零引擎调用），M8TileStreaming MonoBehaviour 仅持状态与 SetActive 应用（:340-377 薄壳）；M8QualityProfile 仅用 Mathf/Rect 数学（同 M7BackdropMath 先例）；Recorder 类型只在 Editor 目录与测试 asmdef，Runtime 程序集零泄漏。WeatherGUI 增量走 HandleHotkeys 既有三段式（回调写参数源→应用→Update 镜像），与 atmo 下拉同款 |
| 2. 契约常量与方法名 | 合规 | M6StraitSceneBootstrapper.Build(:75)/BuildStraitPlayer(:441) 未改名未改语义，增量仅新增私有 WireQualityStreaming(:330)；M8RecordingRunner.RunFromCli 头注 :40 明示 `-executeMethod` 契约；常量单源（M8ShotList.RecordingFps/Width/Height/JpegQuality/CameraTag，Runner 与测试同读，测试 :205-221 断言行为非常量复读） |
| 3. 测试风格 | 合规 | 全合成 fixture：M8TileStreamingPlanTests.MakeTiles(:34-60) 合成 29 tile 网格（几何与 manifest 布局核对一致：近带 ±12 km、远带 ±30 km、交叠 = 中央 3×3），无场景存档实例；注入漂移触发断言路径（M8QualityProfileTests.Clone+注入 :30-55，同 M7BackdropMathTests ValidateDryLand 先例）；断言行为/几何：迟滞往返恰 2 次翻转(:158-174)、互斥、队列激活先于停用(:296-327)，钉死字面量仅作漂移锚（rect.xMin==18000f，同 LatLonToUtm_MatchesPyprojPins 先例）；测试名 Scenario 式、AAA 分段注释；HudVisibility/Recorder 测试经既有 TestReflection helper（W1/M6 review 已有，未重复造轮子） |
| 4. 每帧分配纪律 | 合规 | M8TileStreaming.Update(:340-377) 稳态零分配：缓冲 Awake 一次预分配(:268-281)，m_QueuedDesired 惰性仅首次重建/切档时 new(:366)，队列固定容量+插入排序(:157-212)，TryDequeue struct 出参；Plan.ComputeDesired 全入参出参零 new。HudVisibility 的 FindObjectsByType 仅事件驱动（H 键/Recorder），非热路径。同 M7 树卡引擎实例化 + census 日志先例口径 |
| 5. 日志账本 | 合规 | [Sango.M8]（画质/流送）与 [Sango.M8B]（出片）均循里程碑标签惯例（对照 [Sango.M7B]/[Sango.M4B]）；字段取证化：take start 带 name/dur/fps/out(:235)、take end 带 frames/dir(:276)、streaming wired 带 4/9/16 计数(M6StraitSceneBootstrapper:410-412)；fail-fast 均先 LogError 再 Exit(1) |
| 6. 注释密度与语言 | 合规 | 中文"为什么"注释密度对标 M7BackdropBuilder：M8QualityProfile 头注记录"不引入 ScriptableObject——Simplicity First"的决策；M8TileStreamingPlan 头注记录 2026-09-29 互斥裁决与 z-fight 硬伤；HullWaterlineDecals.cs:262-264 enableInstancing 注释引引擎源码行号（DecalSystem.cs:1116）说明黑帧根因；Recorder 时钟契约（captureDeltaTime 解耦/禁墙钟）两处成对记录。未发现"做了什么"废话注释 |
| 7. Resource 泄漏/幂等 | **一项违规** | HudVisibility Hide/Restore 幂等合规（IsHidden 双向闸 :30/:78，捕获-恢复对称，null 守卫 :83/:89/:95，先前失活对象不误恢复且有测试钉住 M8RecordingPlanTests:174/:184）；bootstrapper 重入安全合规（Build→NewScene 全量重建 :90-91，WireQualityStreaming 无条件建 GO 在全新场景内，同既有阶段先例）；**Recorder 会话未释放——见 F1** |

## Findings

### F1（中）RecorderController 与 Recorder 设置 ScriptableObject 全程不 Dispose/Destroy

- **where**：sango/Assets/Scripts/Editor/M8RecordingRunner.cs:229（`m_Controller = new RecorderController(settings)`）、:271-282（EndTake 仅 `StopRecording()`，无 Dispose）、:86/:98（BuildTakeSettings `CreateInstance<RecorderControllerSettings>` / `<ImageRecorderSettings>`，Runner 路径从不 DestroyImmediate）
- **what**：`RecorderController : IDisposable`（官方 CommandLineRecorder 样例即 `using` 包裹）；AllShots 模式 9 段连录时每段 EndTake 后旧 controller 未释放即被 BeginTake 覆盖，连同每段两个 Recorder 设置 SO 逐段累积。对照同仓 FramePublisher.cs:82/:150 的 Dispose 纪律；测试侧反例倒是做对了（M8RecordingPlanTests.cs:225-229 finally 先捕获再逐个 DestroyImmediate）
- **severity**：中。宿主仅存活于 Play Mode 且流程末尾 Exit(0)，进程退出兜底回收，故无跨机/长期泄漏；但违背本批自述惯例（"Recorder session 释放"），且 AllShots 9 段内录制会话与设置 SO 持续驻留。修法：EndTake `StopRecording()` 后 `m_Controller.Dispose()` 置空，settings 一并 `Object.DestroyImmediate`（每段一段 `using`/try-finally 即可）

### F2（低）M8_SCENE 环境变量未入头注契约清单

- **where**：sango/Assets/Scripts/Editor/M8RecordingRunner.cs:54-55（读 `M8_SCENE`）vs 头注 :24-25（参数清单只列 M8_SHOT/M8_SECONDS/M8_OUT）
- **what**：头注是 batchmode 契约的文档面；`M8_SCENE` 已实现为可覆盖场景路径（DefaultScenePath :34 兜底）却缺席清单，a4000 脚本作者按头注拼环境变量会漏掉该项
- **severity**：低。一行头注补记即可

## 不构成 findings 的核对项（报备）

- `M8ShotList.TryParseRunParams` :166 `ToLowerInvariant()` 与 :175 `OrdinalIgnoreCase` 大小写处理并存——CLI 路径非热路径，风格层不报
- `M8RecordingHost.OnEnable` 静态订阅 QuitWatchStatic 无 OnDisable 对称解绑——自摘逻辑 :323 覆盖且注释成文，静态处理器进程生命周期内无害
- `CountRingActive`（M8TileStreamingPlanTests.cs:81-87）从索引 4 起计数含 overlap 位——Low 档 overlap 恒灭前提下计数语义成立，命名略宽但行为断言正确
- fail-fast `Exit(1)` 路径（:196-200、:264-268）跳过 HudVisibility.Restore——进程即退，无观测面
