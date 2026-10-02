# GodTracker 退役审计（P3-S0，spec #90，2026-10-02）

状态：**只读审计**（未改任何运行时代码）。目的：为 S6 末「默认 tracker 翻转」（00-PLAN §5 裁决 1、
风险 R3 缓解）提供影响面清单、现状基线与翻转执行面。行号核对于本日 HEAD。
结论一句话：翻转 = **两个默认值 + 一个序列化不对称修复**，显式 `kf:` 场景（21/24）零影响；
风险集中在 gui_server 默认会话与无 tracker 段的 busy-water 场景。

---

## 1. 默认值与翻转点清单（Config 默认 `god_tracker=True` 的完整面）

### 1.1 运行时默认（2 处 + 1 处序列化不对称）

| # | 位置 | 现状 | 翻转动作（S6） |
|---|---|---|---|
| D1 | `colav_simulator/core/tracking/trackers.py:205` | `god_tracker: bool \| None = True`（tracker Config 数据类默认） | 改 `= False` |
| D2 | `gui_server/main.py:316` | `SessionCreateRequest.tracker_id: str = "god"`（8010 UI 默认会话走 registry `"god"`） | 改 `"kf"`（或 `"scenario_default"`） |
| D3 | `colav_simulator/core/tracking/trackers.py:212-213` | `to_dict`：`if self.god_tracker is not None: output_dict["god_tracker"] = ""` — **True/False 同写 `""`**；而 `from_dict` :224-225 见键即置 True ⇒ `False` 默认经存/取回环会**复活为 True** | `to_dict` 改 `if self.god_tracker:` 才写键（翻转前置修复，否则 D1 翻转被场景 dump 回环静默撤销） |

构建链（唯一分派点）：`TrackerBuilder.construct_tracker` `trackers.py:243-248`（kf→KF；god_tracker→GodTracker；
否则 KF）。ship 层缺省注入：`ship.py:92-95` —— 场景 ship **无 `tracker:` 段 ⇒ 显式 `trackers.Config()`**，
即吃 D1 默认（这是"场景默认走 God"的机制）；`ship.py:227/:249` 委派 builder。

### 1.2 god 语义的运行时消费分支（翻转后行为变化面）

| 位置 | 现状 | 翻转后 |
|---|---|---|
| `colav_simulator/experiment/runner.py:796` | `_executed_tracker_id`：scenario_default ⇒ `"god"` | ⇒ `"kf"`（manifest `executed_tracker` 标签变化；下游按标签断言处见 §2.2） |
| `colav_simulator/core/tracking/trackers.py:316-319` | GodTracker 直拷真值、协方差恒零阵 | KF：真估计+真协方差（消费方 web 协方差椭圆从"不可见"变"可见"——非破坏，加性真实度） |
| `trackers.py:353` / `:541` | NIS/置信占位 0.0（God/KF 同） | KF 路径 NIS 有限值（存在概率通道仍为 S5 面） |
| `gui_server/main.py:1666` | startup prewarm 显式 `tracker_id="god"` | 与 D2 同步改 |
| `viz/visualizer.py:425/:788/:893` | `isinstance(...GodTracker) or isinstance(...KF)` 同分支 | 零影响（两态已同构处理） |
| `integrations/registry.py:246-248` | `"god"`/`"kf"` 显式 tracker_id 构建 | 零影响（显式 id 不吃默认） |

### 1.3 场景文件面（活跃 scenarios/ 共 24 个）

- **21 个显式 `kf:`**（head_on、crossing_*、overtak*、paper_ccta2023_*、ais_*、rl_*、rlmpc_scenario_ms_channel* 等）
  —— 翻转零影响。
- **1 个显式 god**：`scenarios/rlmpc_scenario.yaml:58` `god_tracker: ""` —— 翻转后仍 God（显式压过默认，符合预期）。
- **2 个无 tracker 段**：`scenarios/romsdal_busy_water_16.yaml`、`scenarios/romsdal_busy_water_80_stress.yaml`
  —— **翻转即 God→KF**（这两文件是真实执行面；`tests/conftest.py:226` p1 harness 引用 busy_water_16 为
  multiship 验证场景）。
- **生成型场景 dump**：episode 生成把 tracker 烘进文件（`ship.py:161` → `scenarios/saved/**/…yaml` 出现
  `god_tracker: ''`，如 `scenarios/saved/rlmpc_scenario_ms_channel/…:260` 起）—— 翻转前已存的 dump 永远 God；
  **D3 不修则翻转后新 dump 也会回环复活 God**。

## 2. 测试影响面

### 2.1 直接构造 GodTracker（翻转免疫，无需改）

- `tests/test_god_tracker_lifecycle.py`（4 tests，`GodTracker([])` 直构）
- `tests/test_tracker_snapshot_contract.py`（2 tests，直构 + TrackKey 排序金样）
- `tests/test_kuwata_vo_static_closed_loop.py:86/:166`（`trackers=[(0, GodTracker())]` 显式注入）

### 2.2 经场景默认吃 God 的面（翻转后需回归的门）

- `tests/conftest.py:234` `p1_run_harness`（G3 验收：head_on/crossing/overtak* —— 均显式 kf，免疫）；
  `:226` busy_water_16 → multiship rule（**无 tracker 段，翻转改变被测 tracker**）。
- `tests/test_busy_water_scenarios.py`（16 tests）—— 静态校验 `romsdal_busy_water_{16,80_stress}.yaml`
  文档结构，不跑 tracker；翻转后文件内容不变 ⇒ 预期免疫（若无 tracker 断言）。
- manifest/标签类：`tests/test_experiment_contracts.py`（13 tests）—— 若断言 `executed_tracker=="god"`
  需同步；已 grep：无 `"god"` 字面断言（仅 runner 侧生成）。
- 翻转日回归闸（S6 执行，全量）：
  `pytest tests/ -q`（2384+ 项）+ web `node --test tests/web_gui/*.test.mjs` + EditMode 全绿。

### 2.3 pytest 相关子集现状基线（2026-10-02，翻转前）

命令：`.venv/bin/python -m pytest tests/ -q -k "sensor or tracker or observation or compact or transport"`

```
49 collected / 47 passed / 2 skipped / 2335 deselected（11.37s）
（+ 本段新增契约测试后：+38 = tests/test_sensor_model_v1_contract.py 20 + tests/test_observations_v1_contract.py 18）
```

skipped 2 项 = 依赖 vimmjipda 外部集成的跳过路径（registry capability G1，`experiment/capabilities.py:190-196`
"仅 0.2s 烟雾测试；RMSE/NIS/NEES/ID-switch 门未关"）——S5 贯通面，与本翻转无耦合。

## 3. 翻转方案建议（S6 执行面）

1. **顺序**：先修 D3（`to_dict` 只在 `god_tracker is True` 时写键）→ 加回归单测
   （`Config(god_tracker=False).to_dict()` 不含键、回环保持 False）→ 跑 §2.3 子集 → 翻 D1 → 全量回归 → 翻 D2。
2. **D1 翻转形态**：`god_tracker: bool | None = False`（显式 False，语义清楚；`None` 走 else 分支等效但可读性差）。
   Config 项名不变（YAML schema `colav_simulator/schemas/scenario.yaml:490-496` `god_tracker`/`kf` 互斥结构不动，
   旧场景文件全兼容）。
3. **回退开关**：翻转本身可逆（D1/D2 是两个常量）；运行时回退 = 场景显式 `god_tracker: ""` 或
   `SessionCreateRequest.tracker_id="god"`（8010 UI 算法下拉已有 tracker 选择）——不需新增开关项；
   god 类保留为诊断通道（00-PLAN R3："god 留诊断"）。
4. **验收口径**（对拍容差，S6 定义）：同场景 god vs 融合航迹对拍以 sensor-model-v1 §5 确认航迹为
   融合侧、GodTracker 快照为对照侧；位置容差 ≤ KF P_0 对角（≈7m 1σ 量级）起步，NIS 有限性为断路检查。

## 4. 溯源

- 机制链：`ship.py:92-95`（缺省注入 Config()）→ `trackers.py:205`（默认 True）→ `:243-248`（分派）。
- 场景证据：`scenarios/rlmpc_scenario.yaml:58`；`scenarios/saved/rlmpc_scenario_ms_channel/*.yaml:260`。
- 服务端证据：`gui_server/main.py:316/:1666`。
- 关联调研：`repo-sensor-seams.md` §1.2/§4（GodTracker 绕过 + 注入端点前置条件）、00-PLAN §5 裁决 1。
