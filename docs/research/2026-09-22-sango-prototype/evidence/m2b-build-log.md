# M2-B build log — per-triangle buoyancy attitude (spec #81)

2026-09-24 · branch `main` (local only, no push) · Unity 6000.3.24f1 + HDRP 17.3.0, Mac M3 arm64 batchmode.
前置：M2-A（#80）船模编目/prefab 未动，`pipelineVersion` 保持 2（场景重建日志无 "vessel assets built" 行 = `EnsureBuilt` 零开销跳过，编目未重建）。

## Gates

| Gate | Command | Result |
|---|---|---|
| EditMode suite（红） | `-runTests -testPlatform EditMode -testResults m2b-tests-red.xml` | exit 0（测试进程），**30 total / 26 pass / 4 fail**，TDD 红成立 |
| EditMode suite（绿，Gate 1） | 同上（stub → 实现） | exit 0，**30 total / 30 pass / 0 fail**（21 条 M2-A 既有 + 9 条新增） |
| Headless scene rebuild（Gate 2） | `-executeMethod Sango.Editor.M1SceneBootstrapper.Build` | **exit 0**，`[Sango.M1] scene written`；场景 YAML 含 2 个 `VesselBuoyancy`（waterSurface 已注入，默认字段 0.8/10/6/64 序列化） |
| Mono standalone player（Gate 3） | `-executeMethod Sango.Editor.M1VerifyCapture.BuildStandalonePlayer` | **exit 0**，`Succeeded size=182MB out=Builds/M1-Standalone.app` |

红轮失败清单（对 stub 断言，非编译失败）：
`Solve_StarboardSwell_RollsStarboardUp_WithZeroPitch`、`Solve_BowHighSwell_PitchesBowUp_WithZeroRoll`、`Solve_UniformWaterRise_HeavesUpByRise_WithZeroAttitude`、`Damp_StepResponse_ConvergesWithoutOvershoot`。
（`Solve_LevelSea_*`/`Solve_EmptySamples_*`/`*_BitwiseIdentical*` 对 stub 恒真——护栏型，绿灯后仍有效。）

## Solver（Sango.Vessels.BuoyancyAttitudeSolver，纯静态、无引擎水面 API）

API：`Solve(HullSample[] samples, in BuoyancyParams p) -> BuoyancyAttitude`；`Damp(DampedScalar, target, frequencyHz, dt)`。

- 输入样点：`{StarboardOffset(+X), ForwardOffset(+Z), Submersion, BaselineSubmersion}`（米）。浸没激励 `e_i = Submersion − BaselineSubmersion`；静水下 e≡0 → 零姿态（B0 稳如磐石）。
- 升沉 = `HeaveGain × mean(e)`；横摇/纵摇 = 去均值 e 场沿 +X/+Z 的最小二乘坡度 → `atan(坡度)×增益` → 对称钳制。退化护栏：样点横向/纵向展开趋零时该轴姿态归零。
- 阻尼：临界阻尼标量弹簧，半隐式欧拉，ω=2πf；dt≤0 保持，f≤0 吸附目标。

**钉死符号约定**（求解器 doc 注释、测试文件头、本文件三处一致）：
- `HeaveOffset`：+ = 相对设计吃水向上。
- `RollDeg`：Unity 本地欧拉 Z，**+ = 右舷(+X)上浮**。
- `PitchDeg`：Unity 本地欧拉 X，**+ = 艏(+Z)下俯**（Unity 正 X 欧拉压艏；艏上涌输出负值）。

**钳制默认值与依据**：MaxRollDeg=10、MaxPitchDeg=6（对称）。大型船舶涌浪中横摇观感超过 ~10° 即失真（货轮/邮轮常态涌浪横摇个位数度），纵摇更小；B11 极端浪况下钳制保证无倾覆观感（spec "no capsizing visuals"）。增益 HeaveGain=1（跟随局部平均水面）、RollGain=PitchGain=0.5（取波浪坡角一半，船舶惯性大于水）。升沉不钳制但经临界阻尼平滑（spec 原文）。平滑频率默认 0.8 Hz（≈1.5 s 整定，Damp_StepResponse 5 s 内收敛到 ±0.01、越冲 ≤0.02 有测试守着）。

## 引擎适配器（VesselBuoyancy，Assembly-CSharp 薄壳）

- 采样复用 M0 probe 模式：hull 三角质心 → `ProjectPointOnWaterSurface`（error 0.01 / 8 iterations / outputNormal=false / 结构体复用）。
- **抽样上限 `maxSamplesPerHull=64`**：FBX 实测三角总数 Small 711 / Medium 8388（Large 3180，未进场景）。全采将达 9.1k 查询/帧 ≈ M0 锚点（144 q ≈ 0.42 ms）的 63 倍 ≈ 推断 26 ms/帧，直接否决。按 spec Further Notes 的"hull-sample reduction 需带证据决策"，证据即上表三角数；步进抽样保持空间均匀分布。实际抽样 Medium 64 + Small 60 = **124 查询/帧**（stride=⌈tri/64⌉）。
- 只碰 y/roll/pitch：根 y = 基线 + 平滑 heave；旋转重建为 `Euler(pitch, 当前yaw, roll)`。x/z/yaw 只读不写（后续 waypoint 批次可独占）。
- 吃水基线 = OnEnable 时根 y（PlaceCatalogShip 的 `waterlineOffsetY`）：实测 Medium −1.29 m / Small −0.33 m，静海他动归零。
- 查询全败帧保持上帧姿态（用残缺数据解算会污染求解器）。
- 每 10s 一行 `[VesselBuoyancy]` 观测日志（FpsProbe 的 [Sango.M0] 同款纪律），播放器运行日志可自证查询健康度。

## Perf 对照 M0 锚点

| 量 | M0 锚点（m0-notes §2） | M2-B |
|---|---|---|
| 查询数/帧 | 144（6 船×24 三角，failed 0） | **124**（64+60，2 船）— 低于锚点 |
| 查询耗时/帧 | 0.42–0.62 ms（实测，GUI editor） | batchmode 实测 0.023 ms 无效（见下）；按 M0 单查询成本 2.9 µs 线性折算 **推断 ≈ 0.36 ms/帧**（124 × 2.9 µs），标注为推断非实测 |

**batchmode 局限（如实记录）**：batchmode Play 无渲染帧 → HDRP 水面 CPU 回读永不就绪 → `ProjectPointOnWaterSurface` 全部返回 false（124/124 failed，耗时 0.023 ms 是失败快速路径，不作耗时证据）。这同时验证了失败路径：两船姿态保持零、停在设计水线、无 NaN、无报错。查询成功时的耗时证据留待播放器运行：`[VesselBuoyancy]` 10s 日志行的 `query_ms` 字段即实测值（真机有渲染帧，M0 同 API 同参数在 GUI 下 failed=0）。M0 亦实测过查询成本与分辨率无关（m0-notes §3.1），单查询成本稳定性有据。

## 偏离 spec 说明

1. **非全量逐三角查询**：spec Implementation Decisions 写"queries happen only at hull triangle centroids, same as the M0 probe"——仍然只在三角质心查询，但按 64/船步进抽样而非全量；决策依据 = 实测三角数（上文），且 Further Notes 明文预留 sample reduction（其例为 5 点，此处 64 点远保守）。宁可记录也不静默全采烧掉 26 ms。
2. **样本量 Small=60 非 64**：stride=⌈711/64⌉=12 → 711/12=60 点，均匀步进的固有取整，无影响。

## 交给编排 agent 的视觉验收清单

1. B0：两船纹丝不动（零姿态 + 静水），水线与 M2-A 截图一致（吃水基线未变）。
2. B6/B9：两船随浪可见升沉 + 轻微横摇/纵摇；涌浪过船体时不再明显穿模；100 m 货轮观感沉稳（0.8 Hz 临界阻尼），12 m 渔船响应相对更轻快。
3. 极端 B11：船不倾覆（roll ≤ 10°、pitch ≤ 6° 钳制）。
4. 船位与艏向不漂：Small (14,−6) yaw 20°、Medium (30,90) yaw −35° 全程保持（浮力只动 y/r/p）。
5. 播放器日志（`~/Library/Logs/.../Player.log`）每 10s 有 `[VesselBuoyancy] ... failed 0` 行 = 查询在真机生效；若 failed>0 请回报（batchmode 局限之外的异常）。
