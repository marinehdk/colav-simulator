# COLAV-SIMULATOR：Predictive Multi-Target Threat Management

## 一句话主旨

COLAV-SIMULATOR 用一套后端威胁真相，把多船预测、威胁排布、避碰计划影响、历史 AIS 反事实验证串成可解释闭环。

## 读者与目标

面向需要理解系统工作流的算法、仿真、前端和验证人员。读者不必先熟悉代码，但需要在看完后能回答：

- 每个目标的威胁是怎样从在线观测算出来的？
- 为什么某一艘船是 Current Primary，其他船为什么仍然不能被忽略？
- Threat Window、Current / Concurrent / Next / Monitor、Conflict Cluster 分别解决什么问题？
- 预测威胁如何进入 Encounter Lifecycle、Aggregate Directive、Horizon Encounter Plan 和 Mid-MPC？
- 历史 AIS 如何变成可复现的 Replay / Counterfactual Benchmark？
- 前端 OpenBridge 显示的事实来自哪里，哪些结论仍有验收边界？

## 证据基线与范围边界

本讲解基于两个已读取的设计/实现来源：

- PRD 对话中的完整设计：`Predictive Multi-Target Threat Management` + `Historical AIS Counterfactual Benchmark`。
- 独立 worktree `/Users/marine/Code/.worktrees/Colav-Simulator/predictive-threat-historical-ais` 当前源码、Spec、真实窗口 manifest 与 OpenBridge workbench。

当前实现快照：branch `codex/predictive-threat-historical-ais`，HEAD `db7509a`，目标 worktree 仍有 UI 验收相关未提交修改；因此本 deck 区分“已落地的后端/数据契约”和“前端最后一轮投影收口”。

数据范围必须分层表达：

- 用户提供 HAIS archive：23 个 daily Parquet，约 1.3 GiB；原始统计约 51,522,509 行、约 1,226 个 MMSI。它是可扩展数据源，不等于当前已完成的全量场景。
- 当前真实 acceptance window：`hais_2026-07-01.snappy.parquet`，UTC `12:00:00–12:01:00`，WGS84 BBox `[6.05, 62.44, 6.17, 62.50]`。
- 选取 4 个 MMSI 作为 source selection provenance，但当前发布的 runtime actors 只有 3 艘，另有 1 个 source-selected MMSI 没有静默提升为 runtime actor。
- 当前窗口证据：24 source rows、24 normalized rows、98 retained quality findings；3 艘船均有尺寸 provenance；ENC `romsdal-expanded` 资格化且 preflight PASS。

## 为什么需要 Predictive Multi-Target Threat Management

只有 DCPA/TCPA/range 仍回答不了四个关键问题：

1. 目标什么时候进入工程 Ship Domain，而不是只在 CPA 时刻才报警？
2. 多个目标中谁是当前关注焦点，哪些目标是当前必须同时满足的约束？
3. 目标 A 的避碰动作会不会让目标 B 变成后续冲突？
4. 为什么 Primary 发生切换，如何避免一周期抖动导致 UI、Planner 和操作者反复跳焦点？

因此 Threat Management 不是增加一个 Risk Score，也不是建立第二套 COLREG FSM。它是一个 session 级、planner-agnostic 的 canonical threat account：每个 cycle 只发布一份 immutable `ThreatManagementSnapshot`，供 Lifecycle、Planner、Evidence 和 Web projection 共同消费。

## 总体功能架构

```text
Ownship State + TrackSnapshot + Prediction Evidence
                         │
                         ▼
       Canonical PhysicalEncounterFacts（每目标一份）
       range / relative velocity / DCPA / signed TCPA
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
    EncounterLifecycle          ThreatAssessment.evaluate()
    role / risk / commitment    Ship Domain / TDV / TDE / Vector
    Primary / release / Rule17  prediction / health / completeness
            └────────────┬────────────┘
                         ▼
             ThreatManagementCoordinator
       priority → rolling schedule → events → graph/clusters
                         │
            ┌────────────┼──────────────┐
            ▼            ▼              ▼
     Aggregate Directive  L4/accepted   Web/Evidence
     required targets     plan receipt   projection/replay
            │
            ▼
      Horizon Encounter Plan → Mid-MPC / COLAV control
```

核心 authority 边界：

- `ThreatManagementCoordinator`：每个 Own Ship、每个 Active Session 唯一实例；持有唯一 Encounter Lifecycle 和 threat account。
- `ThreatAssessment`：纯派生，消费冻结输入，不能 mutate Lifecycle、不能调用 solver、不能接受计划。
- `EncounterLifecycle`：唯一 Primary、role、commitment、passing side、Rule 17、release 和 stateful hysteresis authority。
- L4 hard hull/swept clearance 与 Independent Evaluator：独立安全 authority，不被 Ship Domain 或 Threat Index 替代。
- Web / OpenBridge：只投影后端 canonical snapshot，不在浏览器重新计算 CPA、Domain、Primary、schedule、cluster 或 verdict。

## 一次 cycle 如何计算单目标 Threat Vector

### 1. 固定输入事实

Cycle 开始冻结 ownship、target TrackKey/generation、observation health/age、profile、prediction 和 accepted-plan receipt。若已有 canonical `PhysicalEncounterFacts`，Lifecycle 与 ThreatAssessment 共同消费，避免同一 CPA/geometry 在两个模块重复计算。

### 2. 相对运动与经典几何

对目标 i：

```text
r = p_target − p_own
v_rel = v_target − v_own
range = ||r||
closing_speed = −(r · v_rel) / range
signed_TCPA = −(r · v_rel) / ||v_rel||²
forward_TCPA = max(0, signed_TCPA)
DCPA = ||r + forward_TCPA · v_rel||
```

如果相对速度接近 0，不能伪造 TCPA；输出 typed `RELATIVE_MOTION_UNDEFINED`。如果观测过期、coasting、generation mismatch 或不可用，输出 `UNKNOWN / UNAVAILABLE`，不能把缺数据当作 CLEAR。

### 3. 加入带版本和 provenance 的 Ship Domain

V1 使用 off-centred elliptical engineering domain。Profile 固定：`fore_m / aft_m / port_m / starboard_m`、单位、版本、参数来源、假设、uncertainty policy 和 qualification state。它不是 COLREG 法定距离，也不是 L4 hard safety。

把 target 相对 ownship heading 分解为 forward / starboard 坐标，并加入观测不确定性半径：

```text
a = (fore + aft) / 2 + uncertainty_radius
b = (port + starboard) / 2 + uncertainty_radius
c = (fore − aft) / 2
domain_scale = sqrt(((forward − c) / a)² + (starboard / b)²)
```

解释：`scale < 1` 表示进入 Domain，`scale ≈ 1` 表示 tangent，`scale > 1` 表示在 Domain 外。Profile 未资格化、尺寸缺失、协方差缺失、观测不可用时，Domain 事实必须是 typed `UNQUALIFIED / UNKNOWN`，不得静默套用默认船体。

### 4. 预测 horizon 与 Threat Window

用明确 provenance 的目标轨迹预测（当前支持 constant velocity 等显式 basis），在 horizon 每个时间点计算 Domain scale 序列；从 scale=1 边界插值得到：

- `TDV`：Time to Domain Violation，首次进入时间；
- `peak`：horizon 内最深暴露时刻；
- `TDE`：Time to Domain Exit，离开时间；
- `horizon_min_scale`：预测期间最小 Domain scale；
- completeness 与 unavailable reason。

Threat Window 是对未来暴露的解释，不是执行脚本。没有预测时窗口仍存在，但边界 typed unavailable。

### 5. Threat Vector 的完整字段

每个 TrackKey 独立保存：range、closing speed、DCPA、signed/forward TCPA、hull clearance、current/predicted Domain facts、uncertainty、prediction basis、observation health、claim completeness、lifecycle role/risk/commitment、priority class/reason、Threat Window 和 evidence hashes。

Threat Index（若 UI 显示 0–100）只能是 `display_only`；Planner、L4、Evaluator 和 capability gate 不得使用它当安全门。

## 如何排布多船威胁

### Primary 是焦点，不是唯一目标

Threat Management 把目标分成互斥 schedule context：

- `CURRENT_PRIMARY`：Encounter Lifecycle 当前唯一焦点；
- `CONCURRENT_REQUIRED`：Lifecycle / Aggregate Directive 当前必须同时满足的目标；
- `NEXT`：预测上即将形成责任或窗口的后续目标；
- `MONITOR`：保留观测与证据，但当前没有 Planner obligation；
- `RELEASED / HISTORICAL`：已释放但保留的历史证据。

因此 Primary ≠ Only Target。Primary 切换不会删除其他 required targets；Aggregate Directive 仍把 required targets 作为多目标约束集合送给 Planner。

### Primary 选择是词典序，而不是加权平均

固定优先级：

```text
1 response-time / hard-clearance emergency
2 Rule 17 MUST_ACT
3 committed + ACTIVE
4 current Domain violation
5 predicted Domain violation / earliest meaningful entry
6 future severity + evidence completeness
7 TrackKey + generation deterministic tie-break
```

如果新 challenger 只是短暂变危险，不立即切换。默认 ODD 里 Primary switch confirmation 为 10 s physical-time hysteresis；当前 hard emergency 或 Rule 17 `MUST_ACT` 可以立即 preempt，并记录 `PRIMARY_*` reason。generation change、release、session reset 和 rearm 都要清理旧 switching context。

### Rolling Schedule 不是固定的 A→B→C 脚本

每次滚动 horizon 都重新计算 Window 和 membership。因为 ownship 为 A 改变 heading 后，B/C 的相对速度、DCPA、TDV/TDE 会变化。Schedule 只描述当前关注/约束/后续暴露，不把未来顺序硬编码成执行脚本。

### Conflict Graph 与 Conflict Cluster

两类 typed edge：

- `DIRECT_WINDOW_OVERLAP`：不同目标 Threat Window 在版本化 gap rule 下时间重叠；
- `PLAN_INDUCED_CONFLICT`：有 baseline ownship prediction + 新鲜 L4 accepted/committed plan receipt，且该 accepted plan 使另一个目标产生新 Domain violation、显著提前进入或有版本化 material worsening。

Raw solver candidate、stale cache、GUI 折线或同周期 candidate 都不能构成 plan-induced evidence。Graph 只用 typed witness、prediction basis、input/profile/plan hashes；connected components 形成 deterministic Conflict Cluster，输入顺序变化不应改变 cluster identity。缺少 accepted plan 时，graph 可以报告 direct edges，但 plan-induced 结论必须 typed unavailable。

## 从威胁到 Planner / Mid-MPC

Threat Management 不直接输出舵角。典型闭环是：

1. Coordinator 发布 Lifecycle + Threat Snapshot。
2. Aggregate Directive 给出 required targets、passing side、minimum course change、speed bounds。
3. Horizon Encounter Plan 将多目标生命周期承诺投影到 `MISSION → ALTER → PASS → RECOVER` phases；每个 target 有 action-complete、recovery-from-k 和 minimum predicted route DCPA。
4. Planner 产生 candidate；L4 plan acceptance 独立检查 continuous/swept hull clearance。
5. 只有 accepted plan receipt 在下一 cycle 生效，避免同周期 candidate 反馈形成第二套真相。
6. Accepted plan 进入下一轮 conflict analysis；Rolling Plan 对前缀/有界/ advisory 区间做 continuity gate，必要时 typed revision。
7. 下一周期重新冻结 physical facts、重新评估、重新排布。

## Historical AIS 为什么不是“导入 CSV”

Historical AIS Counterfactual Benchmark 与 online Threat Management 共用 canonical observation、prediction、evidence 和 Web projection，但增加一条严格的 truth/provenance 链：

```text
HAIS GeoParquet
 → immutable Dataset Descriptor
 → raw + normalized observations
 → Historical Actor reconstruction
 → versioned dimensions + qualified ENC
 → Published HistoricalAISCase
 → Historical Replay
 → T0 handoff
 → Counterfactual Run
 → Independent Evaluation
 → Human vs COLAV Compare
 → Evidence / deterministic rerun
```

### Dataset 读取与质量

Reader 先按 entry/time/MMSI/BBox predicate 选择，再 materialize。Raw bytes、entry digest、schema digest、selection digest 和 normalized digest 都进入 Descriptor。Normalization 明确 UTC、WGS84、SOG/COG/heading/ROT 单位；invalid timestamp/coordinate/speed/course、duplicate、long gap、field unavailable/sentinel 作为 typed quality findings 保留。

### Historical Actor 与正常 Simulator chain

Reconstructor 把每艘船的 normalized AIS 样本转成 projected world sample，保留 raw row refs；允许在版本化最大 gap 内插值，长 gap 不外推。Historical Actor 通过普通 Ship/Sensor/Tracker/Session 接口进入 Simulator。Replay 船只播放当前 world sample，不把未来轨迹直接暴露给 Planner。

### ENC qualification 与尺寸 provenance

`ENCRegionProfile` 绑定 source、CRS、supported extent、hazard/navigability layers、cache identity、qualification evidence。`romsdal-expanded` 对当前窗口 preflight PASS；扩大窗口不能靠改 `map_size`，必须重新做 coverage/geometry/layer qualification。

HAIS 本身不可靠提供尺寸时，不能使用零宽度或默认船体。当前三艘船的 formal Ship Domain dimensions 来自 named/versioned SDIR measurement provenance：

| Runtime role | MMSI / name | Length × beam |
|---|---|---:|
| Reference Vessel | `259189000 / VALDERØY` | 32.0 m × 8.8 m |
| Target | `257252000 / FREYJA` | 84.6 m × 16.0 m |
| Target | `258764000 / PELAGIA HORDAFOR` | 59.2 m × 10.8 m |

## 完整多船复杂场景：Romsdal 真实 AIS 窗口

### 场景身份

`hais_romsdal_20260701_120000_120100`，一个不可变 scene descriptor、两个 workflow modes：

- `HISTORICAL_REPLAY`：三艘船全部按历史 AIS 回放，不运行 COLAV，用来验证 Dataset、Reconstruction、ENC、Sensor/Tracker 与 Replay lineage。
- `COUNTERFACTUAL`：T0 前三艘保持历史回放；T0 后只有 Reference Vessel `VALDERØY` 交给正常 `mid_mpc_ipopt` 闭环；`FREYJA` 与 `PELAGIA HORDAFOR` 继续历史 playback；post-T0 Human Reference 只进入 Compare。

### 时间线

```text
12:00:00  Dataset selection / reconstruct / ENC preflight
12:00:00–12:00:30  三艘 Historical Actor 进入 normal Sensor/Tracker chain
12:00:30  T0：VALDERØY 在 frozen historical state 原子 handoff
T0+      Threat cycle 计算两条 target Threat Vector
          Lifecycle 维持唯一 Primary + required obligations
          Schedule / Window / Conflict Cluster rolling update
          mid_mpc_ipopt 只控制 VALDERØY；其他两船仍 playback
Run end  Independent Evaluator → Compare domains → sealed evidence
Rerun    比较 semantic graph/schedule/trajectory hashes
```

### 这一场景中每周期会发生什么

1. Ownship `VALDERØY` 与两艘 target 的当前状态和 TrackKey 被固定；每条 target 都计算 range、DCPA/TCPA、Domain scale、TDV/TDE、observation health 和 evidence refs。
2. Encounter Lifecycle 根据 role/risk/commitment/Rule17 维持 Primary；若另一目标暂时更危险但未超过 10 s confirmation，不因一周期噪声跳焦点；若硬 emergency/MUST_ACT 则立即 preempt。
3. 如果一个目标是当前 Primary，另一个已 committed 或 recovery guard active，它们分别进入 `CURRENT_PRIMARY` 与 `CONCURRENT_REQUIRED`；如果只是未来窗口，则进入 `NEXT`；可见但不构成 obligation 的目标留在 `MONITOR`。
4. 两个 target 的 Threat Windows 重叠时，Conflict Graph 产生 `DIRECT_WINDOW_OVERLAP`，connected component 得到一个 cluster。只有新鲜 accepted plan receipt 且能证明 before/after worsening 时，才额外生成 `PLAN_INDUCED_CONFLICT`。
5. Aggregate Directive 将 required targets 一起送给 Horizon Encounter Plan / Mid-MPC；Primary 只决定当前解释焦点，不能让另一艘 required target 从优化约束中消失。
6. Run 完成后，Independent Evaluator 独立判断 realized Safety/COLREG；Compare 分开输出 Safety、COLREG、Maneuver、Efficiency、Human Similarity，Similarity 只能 advisory。

### 当前真实窗口的已封存证据

- `case.status=SUCCESS`；`run.mode=COUNTERFACTUAL`；requested/executed algorithm 均为 `mid_mpc_ipopt`；`fallback_used=false`。
- `threat`：2 vectors、2 schedule contexts、1 conflict cluster；graph semantic hash 有独立 evidence hash。
- `leakage.status=PASS_CONTRACT`；Human Reference digest 不在 RunSpec；Nominal Intent 严格使用 `< T0` 样本。
- Independent Evaluator：`COMPLETE`、`gate=PASS`、collision 0、grounding 0、minimum distance 2284.76 m、`S_safety=1.0`。
- Compare：`COMPLETE`，五个 domain 均有状态，overall assurance verdict `PASS`。
- Determinism：semantic fields 比较 `mismatches=[]`；两次 run 的 run-envelope hash 可以不同，但 semantic plan/graph/schedule identity 保持可比。

这些结果只证明当前 qualified three-actor window，不能外推为 23 日全 archive、1,226 MMSI、全海域或全 ODD 的安全证明。

## OpenBridge 前端如何呈现

OpenBridge 复用当前 shell 的 `Config / Deployment / Evaluation / Scenario / Algorithm` workfaces：

- `Deployment → MONITOR` 显示 canonical Threat snapshot：Current Primary、DCPA/TCPA、schedule class、priority reason、window、conflict graph、planner state。
- `Scenario → Historical AIS` 显示 dataset archive/entry、UTC window、BBox、selected/published actor count、MMSI、Reference Vessel、T0、ENC qualification、rows/quality findings、coverage limitation。
- `Evaluation → Historical AIS Benchmark` 选择 Replay / Counterfactual，并显示 Dataset → Case → Replay/Counterfactual → Evaluation → Compare stages、fallback、threat counts、leakage、determinism、五域 Compare。
- 新 AIS 场景只走 dedicated `/api/historical/scenarios`；既有 `/api/scenarios` 与 Rule 13/14/15/legacy multiship exact tuples 保持不变。
- REST/WS workflow snapshot 是唯一 UI 数据源；浏览器不执行 threat semantics。

当前状态应如实标注：Threat projection 已能在 Deployment/Monitor 观察；Historical AIS dedicated workbench、catalog、REST/WS 已落地，当前 worktree 仍在收口真实 browser projection defects，最后一轮前端全量 acceptance 不应提前宣称 green。

## 记住这五条

1. **单一威胁真相**：一次 cycle 一份 snapshot，所有消费者共享。
2. **Primary 不是唯一目标**：焦点、并发约束、后续威胁、监视对象必须分开。
3. **预测不是执行**：Threat Window/Cluster 解释未来，Planner/L4/Control 保持独立 authority。
4. **历史 Benchmark 必须防未来泄漏**：T0 后 Human Reference 只能 Compare-only。
5. **验收必须带范围**：当前证明是 qualified Romsdal three-actor window，不是全 archive 或全 ODD 证明。
