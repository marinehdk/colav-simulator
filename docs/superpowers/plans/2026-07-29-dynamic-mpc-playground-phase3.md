# Dynamic MPC Playground Phase 3 实施计划

> 日期: 2026-07-29
> 状态: Phase 3 PASS
> 实施分支: `codex/colav-backend-algorithms`
> 审计基线 commit: `76588c2`
> 最终 working tree 回归: `214 passed, 2 skipped`
> Source Spec: `docs/superpowers/specs/2026-07-28-dynamic-mpc-playground-design.md`
> Phase 3 冻结裁决: VR-20 / VR-21 / VR-22 / VR-23

## 0. 结论

Phase 2 出口已满足，Phase 3 可开始详细实施。

当前 `reconstructed-evaluator-v1` 仅为 evidence-flow stub，不能作为论文 MPC
统一比较器。Phase 3 必须完成:

1. 论文兼容的 COLREG encounter/FSM/评分;
2. C²A 风格同步 footprint CCD first-TOC;
3. collision/grounding/fallback 硬门与连续评分、求解诊断分离;
4. 三套 CPA 收敛到同一实现和 signed TCPA 语义;
5. profile、公式、输入、输出、假设均可追溯;
6. VO、SB-MPC、Potočnik simplified MPC 在同一评价链生成可审计结果。

本计划不回炉 VR-20..23。现有代码与论文证据未发现要求重新打开冻结裁决的
矛盾。

## 1. Phase 3 完成定义

### 1.1 功能完成

每个正式 run 产生三层独立结果:

```text
RunResult
  ├── hard_gate
  │     ├── physical_collision
  │     ├── physical_grounding
  │     ├── fallback_used
  │     └── execution_failure
  ├── colreg_scores
  │     ├── Rule 8
  │     ├── Rule 13
  │     ├── Rule 14
  │     ├── Rule 15
  │     ├── Rule 16
  │     ├── Rule 17
  │     └── safety / delay / maneuver components
  └── diagnostics
        ├── task metrics
        ├── execution metrics
        └── solver metrics
```

硬门 `FAIL` 不可被高 score 抵消。评分失败不可伪造成零分。缺输入时使用
`NOT_EVALUATED` 并记录原因。

### 1.2 可验证完成

必须同时满足:

```bash
pytest tests/test_evaluator_profiles.py
pytest tests/test_unified_cpa.py
pytest tests/test_colreg_fsm_woerner.py
pytest tests/test_colreg_paper_scores.py
pytest tests/test_c2a_collision_oracle.py
pytest tests/test_grounding_oracle.py
pytest tests/test_three_layer_evaluator.py
pytest tests/test_phase3_evaluation_matrix.py
pytest
ruff check <Phase 3 touched Python files>
git diff --check
```

评价矩阵:

```text
algorithms:
  - VO
  - SB-MPC
  - potocnik_simplified_mpc

scenarios:
  - head_on
  - overtaking
  - overtaken
  - crossing_give_way
  - crossing_stand_on
  - paper_ccta2023_multiship

tracker:
  - God

seed:
  - 0

strict_no_fallback:
  - true

evaluator_profile:
  - ccta_2023_demo-v1
```

18 个 run 必须全部:

- 正常生成三层评价;
- 记录 evaluator/profile/formula/oracle 身份;
- pairwise encounter 有 FSM transition 证据;
- score 的原始量、分项、聚合可追溯;
- 无 evaluator exception 被静默吞掉;
- 保持对应 P2 raw G3 证据语义。

这里要求“可评价”，不预设三个算法全部得到高 COLREG score。不得为通过 P3
而调算法、放松 collision truth、修改论文阈值或隐藏不合规结果。

### 1.3 不在 Phase 3

- 不宣告 G4;
- 不做 covering array、三 seeds、置信区间或显著性检验;
- 不实现 subprocess Worker;
- 不实现 replay/Web 评价编辑器;
- 不发明 multi-ship 优先级;
- 不复现论文未公开的 confidential AIS 原始轨迹;
- 不声称恢复了已不可访问的原 `colav_evaluation_tool` 源码;
- 不把 functional/behavior-compatible reconstruction 写成 numerical reproduction。

## 2. 现状审计

### 2.1 可复用基础

| 组件 | 当前能力 | Phase 3 用法 |
|---|---|---|
| `common/vessel_data.py` | 插值、Gaussian 平滑、COG unwrap、导数、机动检测、CPA/grounding 辅助 | 保留预处理入口，补 profile 参数与测试 |
| `evaluation/encounter.py` | `cpa()`、几何分类、stage、live monitor | 升级为 CPA/FSM 单一事实源 |
| `core/collision.py` | footprint adaptive boolean + conservative interval | 扩展 first-TOC，不推翻 P2 oracle |
| `evaluation/evaluator.py` | evaluation/result/persistence 流程已打通 | 改成兼容 façade，替换 stub 评分核心 |
| `experiment/runner.py` | run 后自动评价并写 artifact | 接 profile、hash、三层状态 |
| `experiment/persistence.py` | `evaluation.json`、HTML report | 扩展 schema，保留旧字段兼容 |

### 2.2 必须替换的 stub 行为

当前 evaluator 存在下列 P3 阻塞:

- `S_safety`、`S_r` 使用临时线性距离归一化，不是论文公式;
- detect/substantial turn 固定为 `5°/15°`;
- evaluator 自有 CPA 与 live CPA 语义不同;
- collision 仍存在中心距判断;
- stage 仅按 range 和 post-CPA 单调推进;
- encounter 分类缺 Woerner 双变量/阈值/FSM lock-on;
- grounding 异常被宽泛捕获并降为 `None`;
- 输出没有 profile hash、公式版本、first-TOC、FSM transition;
- `reconstructed-evaluator-v1` 不能证明论文数值复现。

### 2.3 评价器历史恢复边界

可确认的历史资产:

- 原 API 形态:
  `Evaluator()` / `set_enc()` / `set_vessel_data()` / `evaluate()` /
  `print_vessel_scores()`;
- 历史 `config/evaluator.yaml`;
- 当前 `VesselData` 中的预处理与机动检测实现;
- CCTA/Ocean Engineering 论文的参数、公式、输出表;
- 标准场景、Imazu 场景和历史轨迹格式。

不可确认:

- 原 Evaluator 类完整源码;
- 原单元测试与精确浮点 expected values;
- 论文 AIS 原始数据;
- 所有内部边界条件和异常策略。

因此本阶段交付名为:

```text
behavior-compatible evaluator reconstruction
```

只有完整输入、公式、配置和逐项 expected value 都可核对的测试单元，才标
`NUMERICALLY_VERIFIED`。

### 2.4 权威来源顺序

1. Ocean Engineering 2023:
   [Safety and COLREG evaluation for marine collision avoidance algorithms](https://doi.org/10.1016/j.oceaneng.2023.115991)
   为 Rules 8/13-17、Stage 1-4、score/penalty 公式主来源;
2. Hagen thesis Chapter 5:
   [Topics on Marine Collision Avoidance](https://hdl.handle.net/11250/3030310)
   用于公式推导和边界交叉核对;
3. CCTA 2023:
   [A simulator-based framework for testing and evaluating maritime collision avoidance algorithms](https://torarnj.folk.ntnu.no/colav_simulator.pdf)
   用于 Simulator 接口、案例与历史输出;
4. Ocean Engineering 2024:
   [Grounding hazard considerations in evaluation of COLREGS collision avoidance algorithms](https://doi.org/10.1016/j.oceaneng.2024.118204)
   用于 grounding compensation;
5. Tang/Kim/Manocha 2009:
   [C2A: Controlled Conservative Advancement for Continuous Collision Detection of Polygonal Models](https://doi.org/10.1109/ROBOT.2009.5152234)
   用于 first-TOC Conservative Advancement;
6. 历史 `colav-simulator` commit `844718b4...` 中的
   `config/evaluator.yaml` 和 `tests/test_simulation_and_evaluation.py`
   用于 profile/API 行为兼容。

来源冲突时:

- 数学公式以 Ocean Engineering 2023 为主;
- API/config 兼容以历史代码资产为主;
- Spec VR-20..23 的工程边界优先;
- 无法裁决项进入 `reconstruction_assumption`，不自行融合。

## 3. 冻结评价 Profile

### 3.1 Profile 集合

实现三个不可变、版本化 profile:

| profile_id | 来源 | 用途 |
|---|---|---|
| `ccta_2023_demo-v1` | 历史 `evaluator.yaml` | 当前 Playground 场景矩阵默认 profile |
| `oe2023_simulated-v1` | Ocean Engineering 2023 simulated case 参数表 | 论文分项公式/案例核对 |
| `ship_length_scaled-v1` | Spec 冻结的 Fujii/Namgung 椭圆船域策略 | 独立尺度敏感性 profile，不称论文复现 |

Ocean Engineering 的 range 参数被论文明确列为 adjustable，并按 simulated、
AIS-1、AIS-2 case 分别设置。因此不制造一个无来源的
`oe2023_open_water-default`。Table 8/10 参数保存在 golden fixture，不冒充通用
默认值。

2024 grounding compensation 作为后续扩展槽位:

```text
grounding_policy_id = chart-geometric-footprint-v1
grounding_compensation_status = NOT_EVALUATED
```

原因:冻结 Spec 明确 V1 只声明 `chart_geometric_clearance`。2024 方法还要求
give-way alternative ellipses、stand-on tactical-diameter search area，不得用简单
clearance 分数冒充论文 compensation。

### 3.2 Profile 内容

每个 profile 至少包含:

```yaml
schema_version: evaluator-profile-v1
profile_id: oe2023_simulated-v1
source_refs: []
sampling:
  interval_s: 2.0
  gaussian_sigma_samples: 2.0
stages:
  stage2_entry_m: 1900.0
  stage3_entry_m: 700.0
  stage4_entry_m: 200.0
safety:
  preferred_m: 200.0
  minimum_m: 100.0
  near_miss_m: 50.0
  collision_m: 35.0
encounter:
  alpha_crit_13_deg: 45.0
  alpha_crit_14_deg: 13.0
  alpha_crit_15_deg: 10.0
  overtaking_sector_deg: [112.5, 247.5]
maneuver:
  moving_speed_mps: 2.0
  acceleration_mps2: 0.05
  course_rate_deg_s: 0.6
  detectable_turn_deg: 2.0
  apparent_turn_deg: 30.0
weights: {}
```

所有角度在配置中明确单位；进入计算核心后转换为 rad。

### 3.3 Profile 约束

- 配置解析后 frozen;
- 非法阈值顺序 fail-fast;
- profile canonical JSON 计算 SHA-256;
- profile ID、hash、source refs 写 manifest/evaluation;
- 不允许运行时无记录覆盖单个阈值;
- 如允许实验覆盖，生成新的 effective profile hash;
- CCTA 与 OE 参数不得混合成无来源的“最佳参数”;
- `ship_length_scaled-v1` 的输出明确标 `NOT_PAPER_REPRODUCTION`;
- 历史 YAML 的数值/注释冲突保留 `reconstruction_assumption`，不静默猜测。

### 3.4 兼容 API

新 façade 支持:

```python
evaluator = Evaluator(profile="ccta_2023_demo-v1")
evaluator.set_enc(enc)
evaluator.set_vessel_data(vessels)
result = evaluator.evaluate()
```

保留当前调用:

```python
result = evaluator.evaluate(vessels, enc)
```

两种入口必须生成相同 canonical result。`runner.py` 最终显式写入
`ccta_2023_demo-v1`，不依赖隐式 default。

## 4. 统一 CPA 契约

### 4.1 一个模块，两种合法计算

“统一 CPA”不等于把所有场景都错误替换为匀速外推。

需要区分:

1. `instantaneous_cpa`: 当前状态下 constant-velocity CPA，用于 live risk/FSM;
2. `trajectory_cpa`: 已执行同步轨迹上的实际 CPA，用于事后 safety score。

两者都由 `evaluation/encounter.py` 提供，使用同一符号、单位和结果对象。

### 4.2 CPAResult

```python
CPAResult(
    dcpa_m: float,
    tcpa_signed_s: float,
    tcpa_forward_s: float,
    relative_position_at_cpa_ne_m: tuple[float, float],
    method: str,
    status: str,
)
```

语义:

- `tcpa_signed_s < 0`: 已过 CPA;
- `tcpa_signed_s == 0`: 当前 CPA 或退化;
- `tcpa_forward_s = max(0, tcpa_signed_s)`;
- 低相对速度返回显式 `STATIONARY_RELATIVE`，不返回 NaN;
- 输入/输出全部 SI/rad/NE;
- 旧 tuple `cpa()` 暂保留兼容 wrapper，内部只调用新实现。

### 4.3 迁移范围

以下调用全部迁移:

- live `EncounterMonitor`;
- evaluator 初始 CPA;
- stage/FSM risk checks;
- common CPA helper;
- pairwise report;
- G3/evaluation 诊断。

删除重复公式前，先用 characterization tests 锁定差异。旧 helper 如有上游公开
API 价值，保留 deprecated wrapper，不复制数学。

## 5. Pairwise COLREG FSM

### 5.1 状态

按 VR-22 实现:

```text
SF  safe/free
OT  overtaking
HO  head-on
GW  crossing give-way
SO  crossing stand-on
EM  emergency/in-extremis
```

多船场景为 `Ship0 × target_i` 独立 FSM。全局聚合只列出各 pair，不生成未经
来源支持的目标优先级。

### 5.2 输入变量

每个采样时刻计算:

- relative bearing `alpha`;
- relative course/pose angle `beta`;
- range;
- signed TCPA;
- DCPA;
- range rate;
- current stage;
- give-way/stand-on role;
- profile thresholds。

几何分类不得只看 bearing。stage 不得只看 range。

### 5.3 转移规则

实现要求:

- 只从 `SF` 进入稳定 encounter 状态;
- entry/exit 使用不同阈值形成 hysteresis;
- Stage 2 首次稳定分类后 rule lock-on;
- 临界角附近不逐帧 HO/GW/SO 漂移;
- exit 经过 safe 条件后回 `SF`;
- `EM` 只允许从 `GW/HO` 进入;
- `EM` 要求 positive signed TCPA 与 critical-time 条件;
- Rule 17 按 Stage 2/3/4 区分 keep-course/speed、may-act、must-act;
- 每次 transition 保存 previous/new/reason/inputs/profile hash。

### 5.4 Woerner profile

正式默认:

```text
alpha_crit_13 = 45 deg
alpha_crit_14 = 13 deg
alpha_crit_15 = 10 deg
```

port-to-port pose reward 使用冻结公式:

```text
R = 0.5(sin(alpha)+1) * 0.5(sin(beta)+1) * R_max
```

所有公式实现附稳定 `formula_id`，例如:

```text
woerner-2016-eq4.12
eriksen-2020-eq9-15
oe2023-rule16-delay
```

## 6. 论文兼容评分核心

### 6.1 预处理

固定流水:

```text
raw VesselData
  -> coordinate/unit validation
  -> common time interval
  -> interpolation
  -> COG unwrap
  -> Gaussian smoothing
  -> first derivatives
  -> maneuver intervals
  -> pairwise stage/FSM timeline
  -> scores/penalties
```

预处理参数全部来自 profile。原始轨迹不覆盖；processed series 单独保存 hash。

### 6.2 分项

至少实现:

| 分组 | 输出 |
|---|---|
| Safety | `S_r`、姿态分项、`S_theta`、`S_safety` |
| Rule 8 | 动作及时性、明显程度、连续监测证据 |
| Rule 13 | overtaking side/clearance score |
| Rule 14 | starboard action、port-to-port passing score |
| Rule 15 | give-way action、ahead crossing penalty |
| Rule 16 | early/substantial action、`P_delay` |
| Rule 17 | Stage 2/3 keep-course/speed 与 Stage 4 emergency action |

每个 metric 保存:

```text
metric_id
value
status
formula_id
profile_fields
source_interval
raw_components
assumptions
```

值域要求:

- score/penalty: `[0,1]`;
- 不适用: `NOT_APPLICABLE`;
- 输入缺失: `NOT_EVALUATED`;
- 公式异常: evaluator `ERROR`，不可写零。

### 6.3 聚合

聚合顺序:

```text
sample evidence
  -> pair + rule component
  -> pair result
  -> Ship0 result
  -> run aggregate
```

多船 aggregate:

- 保留每个 pair;
- safety 可报告 worst pair/minimum;
- rule score 报 per-rule/per-pair 与显式统计;
- 不用平均值隐藏单个失败 pair;
- 不把 OS-target pair 结论外推为 all-vessel global safety。

### 6.4 复现状态

每个指标携带:

```text
NUMERICALLY_VERIFIED
BEHAVIOR_COMPATIBLE
RECONSTRUCTION_ASSUMPTION
UNVERIFIED_SOURCE_DATA
```

run 级 reproduction status 取最弱必需证据，不以部分 golden cell 推高整份
评价。

## 7. C²A First-TOC Oracle

### 7.1 Collision truth

定义:

```text
physical_collision =
  两船矩形 physical footprint 在同步连续时间首次相交
```

- 不加 safety-domain buffer;
- 不用中心距;
- 不只检查 simulator 离散 timestamp;
- 返回 first time of contact，而非仅 boolean;
- heading 用 shortest-angle 连续插值;
- 使用 P2 adaptive oracle 作为保守回退/交叉验证。

### 7.2 工程算法

实现 Tang/Kim/Manocha Conservative Advancement 的 2D rectangle specialization:

1. 在当前同步时间求两个 footprint 的 separation distance;
2. 用相对平移速度与角速度/corner radius 计算 motion upper bound;
3. 按 `distance / motion_bound` 保守推进;
4. 发现接触后 bracket;
5. 对 bracket 二分求 first-TOC;
6. 到 tolerance/max-iteration 仍不确定时返回 conservative contact interval;
7. 禁止不确定状态默认无碰撞。

结果:

```python
TOCResult(
    collided: bool,
    toc_s: float | None,
    bracket_s: tuple[float, float] | None,
    status: str,
    iterations: int,
    distance_tolerance_m: float,
    time_tolerance_s: float,
    oracle_id: str,
)
```

实现命名为 `c2a-rect2d-v1`。不声称复制原论文完整 3D BVH/C++ 实现。

### 7.3 必测 case

- 静止分离;
- 静止重叠;
- 正面直线解析 TOC;
- 高速 tunneling;
- crossing;
- rotating rectangle corner contact;
- shortest-angle wrap;
- grazing/non-contact;
- exact endpoint contact;
- 三档 tolerance 收敛;
- 与超密采样/解析结果交叉核对;
- P2 boolean 与 P3 first-TOC 的 collided 结论一致。

## 8. Grounding Oracle 与 ENC 语义

### 8.1 三个概念分离

```text
safety_domain
chart_geometric_clearance
operational_UKC
```

Phase 3:

- collision truth 只用 physical footprint;
- grounding truth 用 physical footprint + typed chart hazards;
- V1 只实现/声明 chart geometric clearance;
- operational UKC 保持 `NOT_EVALUATED`;
- 不把 safety domain 当物理船体。

### 8.2 Hazard 分类

修复:

- DEPARE 与 UNSARE 分离;
- shore/land 不折叠进 UNSARE;
- M_QUAL、M_COVR 作为 quality/coverage evidence，不作为实体障碍;
- Polygon interiors 保留;
- grunne/浅点进入 seabed hazard 流;
- 每船按 draft/min-depth 构造独立 hazard set;
- footprint+sweep 与 hazard geometry 做同步 first-TOC。

coverage/quality 不足时:

- 不伪造 `grounding=false`;
- 返回 `UNKNOWN_COVERAGE`/`NOT_EVALUATED`;
- hard gate 与 report 明确显示证据不足。

### 8.3 2024 grounding compensation 扩展边界

Phase 3 只完成:

- open-water COLREG score 原值;
- physical grounding footprint+sweep hard gate;
- chart geometric clearance;
- `grounding_compensation_status=NOT_EVALUATED`。

不在 V1 用 clearance 比例替代 2024 论文的 alternative-path/tactical-diameter
compensation。完整 2024 profile 后续单独实施、单独 golden test；任何
compensation 均不得抵消 physical grounding FAIL。

## 9. 三层结果契约

### 9.1 HardGate

```text
outcome: PASS | SOFT | FAIL
checks:
  physical_collision
  physical_grounding
  fallback_used
  run_completion
  planner_terminal_status
```

规则:

- collision/grounding/fallback/non-completed run -> `FAIL`;
- `TIMEOUT_FEASIBLE` 且执行结果可行 -> 可为 `SOFT`;
- required truth unknown -> 不得 `PASS`;
- score 不参与 hard outcome。

### 9.2 ScoreLayer

```text
profile_id/profile_hash
formula_set_id/formula_set_hash
pair_results
ship0_results
aggregate
reproduction_status
```

### 9.3 DiagnosticLayer

按 VR-23:

| 组 | 代表指标 |
|---|---|
| Task | goal progress、cross-track、collision/grounding truth、COLREG scores |
| Execution | requested/executed algorithm、fallback、planner statuses、deadline/hold |
| Solver | solve time、iterations、objective、constraint violation、feasibility |

算法未提供的 solver 字段标 `NOT_AVAILABLE`，不填零。

### 9.4 资格语义

Phase 3 只更新:

```text
gate = PASS/SOFT/FAIL
qualification = G0/G1/G2/G3
evaluation_status = COMPLETE/PARTIAL/ERROR
```

不得写 G4。G4 仅 P4 canonical + multi-seed + statistics 后生成。

## 10. Artifact 与审计

### 10.1 Manifest 新字段

```text
evaluator_id
evaluator_version
evaluator_profile_id
evaluator_profile_hash
formula_set_id
formula_set_hash
collision_oracle_id
collision_oracle_config_hash
grounding_policy_id
preprocessing_hash
evaluation_schema_version
```

### 10.2 `evaluation.json`

升级到 additive `evaluation-v2`:

- 保留 v1 消费者使用的顶层字段;
- 新增 `hard_gate/scores/diagnostics/evidence`;
- pair ID 稳定;
- 所有时间索引可映射回 truth/planner/event;
- 保存 first-TOC bracket 与 FSM transitions;
- 不内嵌完整重复 trajectory，保存相对 artifact path + hash。

### 10.3 Report

HTML 至少显示:

- hard gate 最先显示;
- profile/formula/oracle identity;
- per-pair encounter timeline;
- Rules 8/13-17 分项;
- minimum distance、DCPA、signed TCPA、first-TOC;
- reconstruction assumptions;
- solver diagnostics;
- `NOT_EVALUATED` 原因。

## 11. 测试证据等级

### 11.1 L1 公式单元

使用手工可算输入验证:

- range piecewise boundaries;
- pose score signs/quadrants;
- score/penalty clamp;
- maneuver thresholds;
- Stage 2/3/4 boundary;
- Rule 17 三阶段;
- profile rad/deg 转换。

### 11.2 L2 历史行为兼容

验证:

- 历史 YAML 每个字段映射;
- stateful Evaluator API;
- `VesselData` 预处理输出;
- historical scenario 输入格式;
- CCTA profile 不被 OE default 覆盖。

### 11.3 L3 论文 Golden Ledger

建立“公式 -> profile 字段 -> 输入证据 -> expected cell -> 状态”台账。

使用:

- CCTA Tables I/II;
- Ocean Engineering Tables 7/9/11;
- Hagen thesis Chapter 5。

限制:

- 有完整输入的 cell 才做严格数值断言;
- 只有论文输出、缺原始 AIS 的 cell 标 `UNVERIFIED_SOURCE_DATA`;
- 不从最终总分反推并伪造轨迹;
- 不只断言总分，必须断言分项;
- tolerance 按数据精度/论文表格舍入明确记录。

### 11.4 L4 工程场景矩阵

VO/SB-MPC/Potočnik × 六场景重新执行。不能复用旧 evaluation.json，因为
profile/oracle/hash 已变化。

输出一份 Phase 3 evidence matrix:

| algorithm | scenario | hard gate | encounter | rule score status | G3 retained | artifact |
|---|---|---|---|---|---|---|

P3 接受算法真实得到的高/低分；只要求评价完整、规则正确、证据可追溯。

## 12. TDD 实施顺序

### Task 0:冻结基线与来源台账

修改/新增:

- `docs/evaluation/phase3-source-ledger.md`
- `docs/evaluation/phase3-reconstruction-boundaries.md`

测试/检查:

- 记录当前 full pytest;
- 保存历史 config 原文 hash;
- 保存论文 DOI/表/公式定位;
- 列出所有 reconstruction assumption。

Gate:

- 每个将实现的参数、公式、边界均有来源或显式 assumption。

### Task 1:Profile + 结果 schema

修改/新增:

- `colav_simulator/evaluation/profiles.py`
- `colav_simulator/evaluation/results.py`
- `config/evaluator/*.yaml`
- `tests/test_evaluator_profiles.py`

Gate:

- 三 profile parse/hash/freeze PASS;
- 参数冲突/单位错误 fail-fast;
- v1/v2 serialization compatibility PASS。

### Task 2:统一 CPA

修改:

- `colav_simulator/evaluation/encounter.py`
- CPA 旧 helper 调用方
- `tests/test_unified_cpa.py`

Gate:

- signed TCPA、low-relative-speed、post-CPA、trajectory CPA 全部 PASS;
- live/evaluator 不再各自实现 CPA 数学。

### Task 3:COLREG FSM

修改/新增:

- `colav_simulator/evaluation/encounter.py`
- `colav_simulator/evaluation/colreg_fsm.py`
- `tests/test_colreg_fsm_woerner.py`

Gate:

- SF/OT/HO/GW/SO/EM 转移;
- entry/exit hysteresis;
- lock-on;
- EM positive-TCPA 限制;
- Rule 17 Stage 2/3/4;
- 临界角抖动回归 PASS。

### Task 4:预处理与论文评分

修改/新增:

- `colav_simulator/common/vessel_data.py`
- `colav_simulator/evaluation/scoring.py`
- `tests/test_colreg_paper_scores.py`
- `tests/fixtures/evaluation/`

Gate:

- Rules 8/13-17 分项;
- safety/range/pose/delay;
- golden ledger 可执行项 PASS;
- confidential input 缺口显式，不伪造 PASS。

### Task 5:C²A collision first-TOC

修改:

- `colav_simulator/core/collision.py`
- `tests/test_c2a_collision_oracle.py`

Gate:

- 解析/密采样/adversarial cases PASS;
- first-TOC 收敛;
- P2/P3 boolean 一致;
- 不确定结果保守。

### Task 6:Grounding/ENC

修改:

- `colav_simulator/common/map_functions.py`
- `colav_simulator/core/collision.py`
- `tests/test_grounding_oracle.py`

Gate:

- polygon holes 保留;
- DEPARE/UNSARE/shore/quality/coverage 分层;
- per-vessel draft hazards;
- footprint+sweep first-TOC;
- unknown coverage 不误报 PASS。

### Task 7:三层 Evaluator façade

修改:

- `colav_simulator/evaluation/evaluator.py`
- `colav_simulator/evaluation/__init__.py`
- `tests/test_three_layer_evaluator.py`

Gate:

- hard/score/diagnostic 独立;
- hard FAIL 不被 score 抵消;
- stateful/current API 一致;
- evaluator exception 结构化;
- no blanket exception swallowing。

### Task 8:Runner/persistence/report

修改:

- `colav_simulator/experiment/contracts.py`
- `colav_simulator/experiment/runner.py`
- `colav_simulator/experiment/persistence.py`
- 相关 API/report tests

Gate:

- identity/hash 完整写入;
- evaluation-v2 round trip;
- failed/partial result 可持久化;
- HTML 显示三层与 assumptions。

### Task 9:Phase 3 算法矩阵

新增:

- `tests/test_phase3_evaluation_matrix.py`
- `docs/evaluation/phase3-evidence-matrix.md`

Gate:

- 18 个 candidate run 全部评价完成;
- VO/SB/Potočnik requested==executed;
- strict-no-fallback;
- raw G3 语义保持;
- pairwise FSM/score/oracle artifact 可追溯。

### Task 10:全量验收

执行:

```bash
pytest
ruff check <Phase 3 touched Python files>
git diff --check
```

人工抽查:

- head-on × SB-MPC;
- crossing give-way × VO;
- crossing stand-on × Potočnik;
- multi-ship × 三算法。

抽查必须能从 report 追到:

```text
raw truth -> CPA -> FSM transition -> stage -> score component
          -> hard gate -> aggregate -> manifest identity
```

## 13. Commit 切片

建议小 commit:

1. `docs: freeze phase 3 evaluator evidence ledger`
2. `feat: add versioned evaluator profiles`
3. `refactor: unify signed CPA calculations`
4. `feat: add pairwise COLREG encounter FSM`
5. `feat: reconstruct paper-compatible COLREG scoring`
6. `feat: add C2A rectangle first-contact oracle`
7. `fix: preserve typed ENC grounding hazards`
8. `feat: separate evaluator gate score diagnostics`
9. `feat: persist phase 3 evaluation evidence`
10. `test: validate phase 3 algorithm matrix`

每个 commit:

- 只包含对应任务;
- targeted tests PASS;
- 不混入前端/main dirty work;
- 不改 Phase 1/2 capability 声明，除非新硬事实要求自动降级。

## 14. 风险与控制

| 风险 | 控制 |
|---|---|
| 原 evaluator 源码不可用 | 行为兼容重建；公式/假设/状态逐项标注 |
| 论文 profile 高度敏感 | 命名 profile + hash；禁止混参 |
| AIS 输入 confidential | 缺输入 cell 不宣称数值复现 |
| FSM 临界角漂移 | hysteresis + lock-on + transition trace |
| actual CPA 与 CV CPA 混用 | 两种 method，共享 typed contract |
| C²A 不收敛 | iteration/tolerance/bracket 状态；保守结论；dense cross-check |
| ENC coverage 不完整 | UNKNOWN/NOT_EVALUATED，不误报无 grounding |
| multi-ship 平均掩盖单 pair | per-pair 结果 + worst-pair 聚合 |
| 旧消费者 schema 破坏 | additive v2 + serialization compatibility test |
| 评价分数反向驱动算法调参 | P3 不改算法；先呈现真实结果 |
| G3 被误解为 COLREG 合规 | G3、hard gate、rule score 分字段展示 |

## 15. Phase 3 最终 GATE

Phase 3 只有在以下全部成立时完成:

- [x] 三个 evaluator profile 固定、可 hash、可追溯;
- [x] CPA 单一实现，signed TCPA 全链一致;
- [x] Woerner/Eriksen pairwise FSM 完成;
- [x] Rules 8/13-17 分项评分完成;
- [x] C²A rectangle first-TOC 完成;
- [x] collision/grounding 均为 footprint+sweep truth;
- [x] ENC hazard/coverage/quality 分层;
- [x] hard gate / score / diagnostic 三层独立;
- [x] `evaluation-v2` 与 manifest 身份完整;
- [x] paper golden ledger 对可验证 cell 通过;
- [x] 不可验证 cell 显式标记，不伪造 reproduction;
- [x] VO/SB/Potočnik × 六场景评价矩阵完成;
- [x] raw G3 与 COLREG score 不混为一谈;
- [x] full pytest PASS: `214 passed, 2 skipped`;
- [x] Ruff PASS;
- [x] `git diff --check` PASS;
- [x] 无 G4 声明。
