# Dynamic MPC Playground Phase 1 实施计划

> 日期: 2026-07-28
> 状态: 待确认、未执行
> 分支: `codex/colav-backend-algorithms`
> 基线 commit: `ba47a8f8cc48d17a665f01f1447a9bf79a4dfd28`
> Source Spec: `docs/superpowers/specs/2026-07-28-dynamic-mpc-playground-design.md`

## 1. Phase 1 目标

让内置 `VO` 与 `SB-MPC` 在以下完整动态场景中通过
`G3DisplayPredicate-v1`:

| Rule | 场景 | 角色 |
|---|---|---|
| Rule 13 | `overtaking` | OT_ing,本船追越 |
| Rule 13 | `overtaken` | OT_en,本船被追越 |
| Rule 14 | `head_on` | HO |
| Rule 15 | `crossing_give_way` | CR_GW |
| Rule 15 | `crossing_stand_on` | CR_SO |
| Multi-ship | `paper_ccta2023_multiship` | 1 OS + 3 TS |

新规则使用 `God` tracker。Rule 14 保留现有 `God/KF` 回归。
Phase 1 只证明动态避碰 G3,不宣称 Rule 17 profile compliance、G4
统计结论或精确 footprint CCD。

## 2. 不可移动的 GATE

### 2.1 Raw evidence 先于 capability promotion

执行顺序固定:

1. nominal threat PASS;
2. VO/SB-MPC raw G3 PASS;
3. sim clock/ENC identity PASS;
4. 才修改 capability grade 与 `verified_combinations`;
5. capability API/Web PASS;
6. 全量回归 PASS。

`algorithm_readiness_grade`、`scenario_readiness_grade`、
`verified_combinations` 均不得作为步骤 1-3 的输入。

### 2.2 G3DisplayPredicate-v1

每个候选 cell 必须同时满足:

1. nominal 与 candidate 使用相同 scenario、seed、tracker、ENC、`dt_sim`
   和完整 `t_end`;
2. nominal 至少威胁一个 active target:truth 最小中心距不大于双方矩形
   footprint 外接圆半径和,或存在 collision event;
3. `requested_algorithm == executed_algorithm`;
4. `strict_no_fallback=true`,`fallback_used=false`;
5. 至少一次 `solver_executed=true`;
6. 每次真实 solve 的 prediction 均为 finite `9xN`,`N>=1`;
7. 以 `time_limit` 或 `goal_reached` 正常结束;
8. 无 collision、grounding、run failure;
9. 对每个 active target:
   `min_center_distance > 0.5*hypot(L_os,W_os) + 0.5*hypot(L_ts,W_ts)`;
10. 公共 sim-time 样本上:
    `max(abs(wrap(psi_candidate-psi_nominal))) >= 2 deg`
    或 `max(abs(U_candidate-U_nominal)) >= 0.5 m/s`。

CR_SO 通过时只标记“可观察动态避碰 G3”。

### 2.3 禁止通过方式

- 不降低 2 deg、0.5 m/s 或 footprint 外接圆门槛;
- 不缩短正式 gate 的 scenario `t_end`;
- 不把 runtime 中心距 collision boolean 当 footprint 安全证明;
- 不启用 fallback 或把 nominal command 伪装成 solver output;
- 不先写 G3 catalog 再借 catalog 放行 raw runs;
- 不自动叉乘 rule/scenario/algorithm/tracker;
- 不把 generator class defaults 当作实际 generation witness;
- 不在 P1 引入 Woerner/Eriksen FSM、C²A、G4 multi-seed。

## 3. 验收矩阵

### 3.1 正式 G3 cell

固定 `seed=0`,`strict_no_fallback=true`,
`terminate_on_collision_or_grounding=false`。

| Scenario | Nominal threat | VO | SB-MPC | Tracker |
|---|---:|---:|---:|---|
| `head_on` | required | G3 required | G3 required | God |
| `overtaking` | required | G3 required | G3 required | God |
| `overtaken` | required | G3 required | G3 required | God |
| `crossing_give_way` | required | G3 required | G3 required | God |
| `crossing_stand_on` | required | G3 required | G3 required | God |
| `paper_ccta2023_multiship` | required | G3 required | G3 required | God |

合计:6 个 nominal threat run + 12 个 candidate G3 cell。

### 3.2 Rule 14 回归 cell

`head_on × {nominal,vo,sbmpc} × KF` 保持现有可运行/证据契约。
新 Rule 13/15/multi-ship 不扩到 KF。

## 4. 实施顺序

### Task 0:冻结边界并整理现有 WIP

**文件**

- `docs/superpowers/specs/2026-07-28-dynamic-mpc-playground-design.md`
- `docs/superpowers/plans/2026-07-28-dynamic-mpc-playground-phase1.md`
- 当前 worktree 中全部未提交 P1 草稿

**步骤**

1. 记录 `git status --short` 和 `git diff --stat`;
2. 逐项把现有草稿归入后续 Task,不把任何草稿视为已验收;
3. 不改、不丢用户无关改动;
4. 先提交已确认 Spec 与 Plan,建立代码实施前文档 checkpoint。

**完成条件**

- 文档与代码变更边界可区分;
- Phase 1 代码仍未获得 G3 promotion。

### Task 1:实现可复用 raw G3 predicate

**新增**

- `colav_simulator/experiment/g3_gate.py`
- `tests/test_g3_display_predicate.py`

**实现**

1. 新增 `G3DisplayResult`,输出 `passed/checks/metrics/reasons`;
2. 从 raw frames、events、manifest、ship dimensions 计算:
   - nominal threat;
   - 每个 target 的最小中心距与外接圆阈值;
   - requested/executed/fallback/termination;
   - solve count 与所有真实 solve 的 `9xN` finite 状态;
   - 公共 sim clock 上的 heading/speed nominal delta;
3. 角度比较统一 `wrap_angle`;
4. nominal 与 candidate 时间轴不完全相同时,只对 nominal 在 candidate
   范围内线性插值;禁止外推;
5. predicate 不读取 readiness grade 或 capability catalog。

**测试**

- nominal 无威胁 -> FAIL;
- fallback、无真实 solve、8xN、NaN、collision、grounding -> 各自 FAIL;
- 任一 multi-target clearance 不足 -> FAIL;
- 安全但无可观察动作 -> FAIL;
- heading 或 speed 任一达到阈值 -> PASS;
- 不同 ENC hash、非单调 clock、clock 间隔异常 -> FAIL。

**Gate**

```bash
uv run pytest tests/test_g3_display_predicate.py -q
```

### Task 2:标准场景速度与威胁性合规

**修改**

- `scenarios/crossing_give_way.yaml`
- `scenarios/crossing_stand_on.yaml`
- `scenarios/overtaking.yaml`
- `scenarios/overtaken.yaml`
- `tests/test_scenario_speed_compliance.py`

**实现**

1. 对 5 个标准场景及 multi-ship 的每条船构造实际 model;
2. 审计 initial `csog_state[2]` 与全部 `speed_plan`;
3. 只修复超出 Viknes `[U_min,U_max]` 的四个场景;
4. 保持 OT_ing 本船更快、OT_en 目标船更快;
5. 修后重新计算 signed TCPA/DCPA;
6. 断言 CPA 落在 `(t_start,t_end)`,nominal 仍满足 threat predicate;
7. multi-ship 使用其 KinematicCSOG `U_max=15 m/s`,不套 Viknes 上限。

**Gate**

```bash
uv run pytest tests/test_scenario_speed_compliance.py -q
```

### Task 3:修复 P1 Rule 13 角色分类

**修改**

- `colav_simulator/evaluation/encounter.py`
- `colav_simulator/experiment/contracts.py`
- `colav_simulator/experiment/runner.py`
- `tests/test_rule13_15_encounter_classification.py`

**实现**

1. 保持 head-on `15 deg`、abaft-beam `112.5 deg`;
2. 同时计算:
   - target 相对 ownship 的 bearing;
   - ownship 相对 target 的 contact bearing;
   - 双方速度大小;
3. contact 在 target 船尾且 ownship 更快 -> `overtaking`;
4. target 在 ownship 船尾且 target 更快 -> `overtaken`;
5. Rule 13 判断先于 crossing,避免标准追越落入 Rule 15;
6. `RULE_BY_ENCOUNTER` 增加 `overtaken -> rule13`;
7. manifest 增加 `encounter_profile_id="legacy-g3-v1"`;
8. 保持 `classify_geometry` 公共五元 tuple;
9. 验证 post-CPA 为 `clear`,timeline/monitor 可进入 stage 3。

**Gate**

```bash
uv run pytest tests/test_rule13_15_encounter_classification.py -q
uv run pytest tests/test_evaluator.py tests/test_web_api.py -q
```

### Task 4:验证真实 scenario_generator coverage

**修改**

- `tests/test_scenario_generator_rule1315_coverage.py`
- 仅在真实 witness 暴露实现缺陷时修改
  `colav_simulator/scenario_generator.py`

**实现**

1. 用 `Config.from_file(config/scenario_generator.yaml)` 加载运行配置;
2. 分别用 OT_ing/OT_en/CR_GW/CR_SO scenario config;
3. 固定并记录每个 role 的 seed;
4. 通过 `ScenarioGenerator.generate()` 的真实 `generate_episode` 路径生成;
5. 对实际生成 ship states 断言:
   - 角色分类正确;
   - model speed bounds 合规;
   - signed TCPA > 0;
   - DCPA 不大于运行配置阈值;
   - bearing 距 15 deg/112.5 deg 边界有 guard band;
6. discovery 阶段可扫描 seed;验收测试只能使用固定 seed,不得运行时搜索
   “直到成功”。

**Gate**

```bash
uv run pytest tests/test_scenario_generator_rule1315_coverage.py -q
```

### Task 5:修复阻塞 VO 行为的已确认计算缺陷

**新增/修改**

- `tests/test_kuwata_vo_regression.py`
- `colav_simulator/core/colav/kuwata_vo_alg/kuwata_vo.py`

**实现**

1. 先写候选速度向量单元测试;
2. `_compute_optimal_controls` 的 north/east 分量均使用
   `candidate_speed`,禁止 y 分量误用 loop speed offset;
3. 先写 moving-target VO ray 单元测试;
4. VO intersection 使用 candidate 与 target 的相对速度
   `v_os_new-v_do`,不是 candidate absolute velocity;
5. 补 HO/OT_ing/OT_en/CR 两侧 situation 回归;
6. 不预先调 `VOParams`;只有 raw cell 仍失败且证据指向参数时,单独记录
   failure、增加回归测试后再做最小参数修改。

**SB-MPC 约束**

- 不预设 SB-MPC 需要修改;
- 只有某个正式 cell 失败时才定位 `SBMPC.cost_func`/wrapper/trace;
- 禁止通过放宽 G3 predicate 或改变场景角色解决算法失败。

**Gate**

```bash
uv run pytest tests/test_kuwata_vo_regression.py tests/test_rule14_planner_trace.py -q
```

### Task 6:建立完整 standard-scene raw G3 矩阵

**新增/修改**

- `tests/conftest.py`
- `tests/test_rule13_15_g3_matrix.py`
- `tests/test_rule14_planner_trace.py`

**实现**

1. module/session scoped fixture 对每个 scene 只运行一次 nominal;
2. raw gate run 不设置 `validation_rule_id`,绕开未 promotion catalog;
3. candidate 使用 `algorithm_id=vo/sbmpc`,`tracker_id=god`;
4. 完整运行 scenario 原始 `t_end`,保存独立 temp output root;
5. 每个 cell 调 Task 1 predicate;
6. failure message 输出 scenario/algorithm、失败 check、最小距离、footprint
   threshold、最大 heading/speed delta、solve count、termination;
7. Rule 14 增加 God raw G3 回归;KF 保留现有契约回归;
8. 失败处理顺序:
   - 先检查场景/单位/clock;
   - 再检查 requested/executed/fallback/trace;
   - 再检查算法几何与 cost;
   - 最后才考虑有证据的局部参数修正。

**Gate**

```bash
uv run pytest tests/test_rule13_15_g3_matrix.py -q
uv run pytest tests/test_rule14_planner_trace.py -q
```

所有 `VO/SB-MPC × HO/OT_ing/OT_en/CR_GW/CR_SO × God` cell 必须 PASS。

### Task 7:建立 multi-ship raw G3 与 clock/ENC 门

**新增/修改**

- `tests/test_multiship_g3.py`
- `tests/test_p1_clock_enc_contract.py`
- `colav_simulator/experiment/contracts.py`
- `colav_simulator/experiment/runner.py`

**实现**

1. multi-ship nominal/VO/SB-MPC 跑完整 500 s;
2. 对 3 个 active target 分别计算全时域 minimum clearance;
3. candidate 对全部 target 通过外接圆安全门;
4. 至少一个 target 引发可观察动作;
5. `RunManifest` 与 `episode.json` 增加相同 `enc_hash`;
6. ENC hash 对 source path 集合排序,递归 hash 文件相对路径与内容;
7. frame timestamp 严格单调,相邻差为 `dt_sim`;
8. planner solve time/event time 必须落入同一 session clock;
9. nominal/candidate 的 scenario hash、ENC hash、seed bundle 相同。

**Gate**

```bash
uv run pytest tests/test_multiship_g3.py -q
uv run pytest tests/test_p1_clock_enc_contract.py -q
```

### Task 8:raw G3 全绿后 promotion capability

**修改**

- `colav_simulator/experiment/capabilities.py`
- `tests/test_p1_capability_api.py`
- `tests/test_web_api.py`
- `web_gui/app.js`

**实现**

1. 增加单一精确表:
   `VERIFIED_COMBINATIONS[(rule,scenario,algorithm,tracker)] = evidence`;
2. 表内只加入已通过 Task 6/7 的组合;
3. `annotate_scenario`、`_rule_document`、`_integration_document`、
   `validate` 均从精确表过滤;
4. 删除 `supported_rules × supported_scenarios` 自动叉乘;
5. `verified_combinations` 输出四个 ID 与
   `predicate_version="G3DisplayPredicate-v1"`;
6. `latest_evidence` 记录 seed、termination、min clearance、action delta、
   solve count、profile ID;不只记录 grade;
7. Rule 13/15/multi-ship 只暴露 God 组合;
8. Rule 14 保留已验证 God/KF 组合;
9. Web 在 rule、scenario、algorithm、tracker 任一变化时按精确 tuple
   禁用未验证选项;
10. 保留 legacy `/api/algorithms` dependency-status endpoint;不把它扩展为
    capability matrix。

**API 负向测试**

- Rule 13 + crossing scene -> 422;
- Rule 15 + overtaking scene -> 422;
- Rule 13/15/multi-ship + KF -> 422;
- 未验证 algorithm/scenario 组合 -> 422;
- G3 global grade 不得让未列出的 tuple selectable。

**Gate**

```bash
uv run pytest tests/test_p1_capability_api.py tests/test_web_api.py -q
```

### Task 9:Phase 1 总出口

按 Spec 固定顺序:

```bash
uv run pytest tests/test_scenario_speed_compliance.py -q
uv run pytest tests/test_rule13_15_encounter_classification.py -q
uv run pytest tests/test_rule13_15_g3_matrix.py -q
uv run pytest tests/test_scenario_generator_rule1315_coverage.py -q
uv run pytest tests/test_multiship_g3.py -q
uv run pytest tests/test_p1_capability_api.py -q
uv run pytest tests/test_rule14_planner_trace.py -q
uv run pytest tests/test_p1_clock_enc_contract.py -q
uv run pytest -q
uv run ruff check colav_simulator tests
git diff --check
```

再启动本地服务验证:

```bash
uv run uvicorn gui_server.main:app --host 127.0.0.1 --port 8010
```

检查:

- `/api/capabilities?validation_rule_id=rule13`;
- `/api/capabilities?validation_rule_id=rule14`;
- `/api/capabilities?validation_rule_id=rule15`;
- `/api/capabilities?validation_rule_id=multiship`;
- Web 规则/场景/算法/tracker 联动;
- telemetry 中 requested/executed/fallback/planner solve 证据。

## 5. Commit 切分

1. `docs: approve playground spec and phase 1 plan`
2. `test: define raw G3 display predicate`
3. `fix: normalize P1 scenarios and Rule 13 roles`
4. `test: prove configured Rule 13 and 15 generation`
5. `fix: correct VO candidate and relative-velocity costs`
6. `test: gate VO and SB-MPC across COLREG scenarios`
7. `feat: record P1 clock and ENC identity evidence`
8. `feat: promote only verified P1 capability tuples`

每个 commit 只在自身 focused tests 通过后产生。最终 commit 后重跑 Task 9。

## 6. Phase 1 完成定义

仅当以下条件全部成立,才可宣布 P1 完成:

- 12/12 God candidate G3 cells PASS;
- 6/6 nominal threat scenes PASS;
- multi-ship 3/3 target clearance checks PASS;
- Rule 14 God/KF 无回归;
- 0 fallback、0 invalid plan、0 collision、0 grounding、0 failed run;
- exact capability tuples 与 raw evidence 一致;
- 8 个 Spec P1 gate tests 全 PASS;
- 全量 pytest 无新失败;
- Web 只展示可执行且已验证组合。

任何单一 cell 失败:P1 整体保持未完成;不得只提升通过的算法全局 grade 后宣告
Phase 1 成功。
