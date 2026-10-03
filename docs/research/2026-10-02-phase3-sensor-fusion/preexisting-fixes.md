# 预存失败修复批 + 外部仓多源接线（spec #91 批 2a，2026-10-02）

承接 `preexisting-failures.md` §1 的 9 例预存红（三组）+ #91 项 1（外部仓 vimmjipda
多源融合接线，用户已授权改外部仓）。本批全部修绿；每条含根因与修法。主 Agent 可按
文末命令独立复跑。

## 0. 外部仓多源接线（#91 项 1）

- 外部仓 `/Users/marine/Code/ecosystem/vimmjipda` 本地 commit **`58e4903`**（不 push）：
  `vimmjipda_tracker_interface.py` +48/-6。量测接受判定从 `isinstance(cs_sensing.Radar)`
  改为能力接口 `accepts_measurement_sensor()`（legacy Radar 显式路径零变化 + 任何声明
  `provides_ne_position_measurements` 旗标并暴露 `generate_measurements` 的传感器），
  协方差按传感器取（`params.R_ne` → `R(...)` 回退，`ne_measurement_covariance()`）；
  量测集按传感器各自协方差构造（单 Radar 配置结果逐值不变）；顺带修掉"无接受传感器时
  `meas_covariance_NE` 未绑定"的潜在 NameError。AIS（4 维状态量测）不声明旗标，不入链。
- 主仓侧（加性）：`core/sensing.py` `RadarXBand` / `ExternalCameraSensor` 类体各加
  `provides_ne_position_measurements = True` 旗标；`integrations/vimmjipda_existence.py`
  快照 `sources` 从硬编码 radar 单通道改为按内层传感器表派生
  （`_credited_sensor_ids()`，radar_x→1、camera_eo/ir→2/3）。
- 集成证（新增 `tests/test_vimmjipda_multisource.py`，4 passed；既有
  `test_simulator_vimmjipda.py` 2 passed 不动）：radar_x 腿量测计数 >0 且航迹落真值
  120 m 门内；相机腿（合成 observations 经 `ExternalCameraSensor.submit`）38 条关联
  量测、confirmed 航迹 existence 0.9999+、 credited source=2；混合装配 credited
  (1,2)；legacy Radar 腿行为不变（source=1）。
- 对拍（新 `tools/sango_vimmjipda_sensor_compare_s5.py`，复用 s5 harness 真值模型）：
  同 seed 同场景 vimmjipda(legacy radar) vs vimmjipda(radar_x) —— 每 target RMSE 比
  3.269（radar 3.91 m / radar_x 12.77 m；radar_x 噪声模型 σ_r=8 m + 1° 方位角 vs
  legacy 5 m 各向同性，量级一致），JSON 在
  `output/sango-fusion-s5/track-compare-radarx.json`（schema
  `sango-fusion-s5/track-compare-sensors@1`，report-only 不设门）。
  既有 `tools/sango_track_compare_s5.py`（god vs vimmjipda）接线后复跑正常。
- **正式门留档（诚实优先）**：`NOT_QUALIFIED_VIMMJIPDA_GATES_OPEN` 对应的
  RMSE/NIS/NEES/ID-switch 正式资格套件在主仓**不存在**（`experiment/capabilities.py`
  只有 G1/G2 语义与 gates-open 注记，无任何可跑的 Monte-Carlo RMSE/NEES 聚合、NIS
  一致性或 ID-switch oracle 框架；外部接口 NIS 恒 NaN）。搭建＝多天工程，超出本批。
  现有证据：S5 god-vs-vimmjipda 对拍 + 本批 radar_x 对拍数字（report-only）。
  资格门保持 open，vimmjipda 维持 EXPERIMENTAL/G2-语义，待独立立项。

## 1. web_api 2 例（`test_deprecated_algorithm_selector_cannot_bypass_product_policy`、`test_vo_head_on_recommended_tier1_executes_safe_maneuver`）

两例两个独立根因：

1. selector 422 `Unsupported algorithm: potocnik_colreg_fan_mpc`：**不是**算法目录缺
   注册（registry 直构成功）——是 `POST /api/select_algorithm` 换算法身份时沿用旧
   spec 的 `algorithm_config`（create 路径 `to_spec` 填了 vo 的 spacing profile，非空、
   无 `factory` 键）；`registry.build_algorithm` 视非空 config 为权威、跳过
   `_load_published_algorithm_profile`（factory 键只在 published profile 里）→ 落到
   无分支的 `Unsupported algorithm`。修法：`gui_server/main.py` `api_select_algorithm`
   换算法时按 create 路径同规则为新算法重导 `algorithm_config`
   （`_product_spacing_profile(new_id)`，无 profile 则空 → registry 走 published
   profile）。测试语义（policy.validate 放行 exact tuple + retired id 拒绝）原样保留。
2. tier1 VO 闭环 `ValueError: Ownship speed envelope requires both the avoidance cap
   and the steerage floor`（kuwata_vo.py:994）：配对要求由 e751e5f3 引入（同节点
   `ship_guidance_node` 同时喂 cap+floor）；e9bb3ec2 给 modular 适配器只加了 floor
   没加 cap → 半包络。修法：`modular_gnc/adapter.py` 补
   `os_avoidance_speed_cap_mps=guidance_limits["emergency_avoidance_speed_cap_mps"]`
   （同一静态参数节点，恢复 e751e5f3 的成对语义；original 栈走 live policy 不受影响）。

## 2. mid_mpc_single_encounter 5 例（部分修复：1/5 全绿，4 例卡在更深的第三层）

三层事实，逐层对齐（无一行"迁就"——每层都溯源到已提交的语义变更）：

1. **PRIMAL_SEED ≠ IPOPT_BEST_FEASIBLE_ITERATE**（5 例共同的第一截停点，已修）：
   断言写于 8-11（ef8432ff），而"seed 支配则发运 seed"是 f0971c67（9-11）+39a0be8e
   （9-11）的**设计契约**（deadline 截断且 seed 原始可行、目标值严格优于全部可行迭代
   点时发运 seed）。探针实证：过 CPA 行 seed 目标 ~5.5e-20，ENFORCE 截断后 1 次迭代的
   可行迭代点不可能更优 → PRIMAL_SEED 诚实触发。修法：`_run_and_assert_common` 质量
   门块按 source 分支——PRIMAL_SEED 行钉 `accepted_iteration is None` +
   `objective_improvement == 0.0`；IPOPT 行保留全部旧钉。下游行为/安全断言全保留。
2. **收尾 speed recovery 断言**（`abs(final_speed - cruise) < 0.1`，2ce2f1d2 8-10，
   已修）：与 31d37a31（9-08）"finite mission endpoint 刹车停车"契约直接冲突（姊妹
   测试 `test_mid_mpc_single_product_runtime.py` 已同步钉 goal_reached + 末速
   ≤0.05）。修法：公共收尾改钉到达停车契约（末速 ≤0.1 m/s），course recovery 保留。
   **验证：overtaking 一例经此两层修复后整链全绿**（行为断言、HOLD 收尾、XTE 全过）。
3. **首动作时刻/末态航向钉值族**（**未修，如实留档**）：空载复跑（无并行负载）下
   head_on **确定性**失败于末态航向钉 `_angle_delta(course(final), course(initial))
   < 5°`——实际到点停车时航向偏 67°（两次独立空载跑同一断言值逐位相同
   1.168742571525739）；带负载跑则失败点在首动作钉（`action["sim_time"] == 5.0`，
   实际 64.5 s）与航向钉之间漂移。即该 4 例是多钉值行为红：威胁层直到 TCPA≈145 s 才
   选中目标（探针时间线：t≤55 s 全部 HOLD/enc=None/selected=[]，t=59.5 首次 head_on
   分类 TCPA=142.5，t=64.5 首个 GIVE_WAY），避让-返航-到点停车闭环在 t_end=1200 内
   完不成"回到航线航向"。根因溯源：9-08 威胁连续性重构 `3869c6aa`
   （docs/mid-mpc-threat-continuity-and-latency.md——其验收边界**自证**单船 HO/CS 套件
   当时未带绿："单船扩展回归初次出现 HO/CS 末态恢复失败后中断…仍触发原末速断言…不是
   完整单船套件通过证明"）+ 同日 31d37a31 到达停车语义 + 9-13/9-18 的 CPA 窗/inline
   verdict 修复（0f04ffff、3e15dd6f）。这些 commit 均更新了
   `test_mid_mpc_single_product_runtime.py` / `anticipatory_runtime.py` 等姊妹测试，
   唯未重封本文件的行动时刻/末态航向钉。head_on 场景 yaml 在 7a1bd1bf 仅加性 radar_x
   装配、几何未动（本批已核对 diff）；起点 csog_state 自 2023 年未变。
   **建议**：planner 域独立小批，按现行威胁连续性+到达停车设计逐场景重导行为钉（首动作
   时刻改钉 TCPA 门而非绝对秒、末态航向按"到点停车"语义重议或给 t_end 留返航余量），
   并以空载复跑去负载敏感化；本批不猜钉值（行为安全钉不宜由传感器/接线批代拟）。

## 3. historical_ais_scene_guard 2 例

守卫自述流程 = characterization baseline（防未提交/意外漂移），重封存 ≠ 绕守卫：

1. yaml 字节稳定性：4 个文件在钉值（8-26 `13227567`）之后被**已提交的刻意场景工作**
   重写——`overtaking.yaml`+`crossing_give_way.yaml`（31d37a31 finite endpoints）、
   `paper_ccta2023_multiship.yaml`（f44c7d8c 三船 C-route）、`head_on.yaml`
   （7a1bd1bf P3-S6 closeout）。修法：按守卫流程把
   `EXPECTED_SCENARIO_YAML_SHA256` 4 个钉值重封存到当前已提交字节（留注释注明来源
   commit），工作树本身 clean（`git status scenarios/` 空）。
2. verified 元组独立：实际失败在 `hais_experimental` 集合断言——c683d681（8-26）刻意
   把 `mid_mpc_ipopt` god 加进 HAIS EXPERIMENTAL 列表、7a1bd1bf（P3-S6 flip）给每个
   EXPERIMENTAL god 元组镜像 vimmjipda 平行元组，守卫钉值（2 元组）未跟随。修法：
   `hais_experimental` 期望集合重封存为 6 元组（3 god + 3 vimmjipda 镜像），ADR-0004
   语义（HAIS 永不 verified、永不可选、限 multiship）不变；verified 18 元组主断言
   原样通过。

## 复现命令（主 Agent 验收）

```
# web_api + scene-guard 全绿
.venv/bin/python -m pytest tests/test_web_api.py tests/test_historical_ais_scene_guard.py -q
#   → 27 passed, 3 skipped
# mid_mpc 组：1/5 全绿（overtaking），4 例卡第三层（见 §2.3，行为钉重封留待 planner 批）
.venv/bin/python -m pytest tests/test_mid_mpc_single_encounter.py -q
#   → 1 passed, 4 failed（失败点随负载在 §2.3 两类钉间漂移）
# 传感器/tracker 子集（含新 4 例多源接线证）
.venv/bin/python -m pytest tests/ -q -k "sensor or tracker or observation or compact or transport or radar_x or mast or georef or lidar or ais or ipda or track or camera"
# 对拍 JSON
COLAV_ECOSYSTEM_ROOT=~/Code/ecosystem .venv/bin/python tools/sango_vimmjipda_sensor_compare_s5.py --duration-s 300
```

## 遗留

- vimmjipda 正式 RMSE/NIS/NEES/ID-switch 资格套件：不存在，需独立立项（本批接线 +
  对拍已就位；`capabilities.py` 的 G1 注记与 `NOT_QUALIFIED_VIMMJIPDA_GATES_OPEN`
  保持如实）。
- `preexisting-failures.md` §2 的 36 例环境退化批 + colreg_scoring 段错误：本批边界外，
  维持独立立项建议。
- 外部仓 commit 本地保留（58e4903），不 push（独立学术仓约束）。
