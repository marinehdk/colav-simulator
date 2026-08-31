# COLAV-SIMULATOR Risk 模块：10 船场景 + VO 的真实机制

## 讲解目标

本 deck 只解释当前仓库中的 Risk / Threat Management 设计和实现，不把浏览器 UI 当作第二套算法。核心问题：在 `romsdal_busy_water_16` 的 10 个目标船 + VO 运行中，系统如何从每目标事实计算 Threat Vector，如何评价 Primary / Concurrent Required / Next / Monitor，如何保持滞回并切换目标，以及这些结果如何进入 VO、事件列表和 OpenBridge 卡片。

## 真实代码锚点

- `colav_simulator/experiment/busy_water.py`
  - `ACCEPTANCE_SCENARIO_ID = "romsdal_busy_water_16"`
  - `DEFAULT_SEED = 20250731`
  - `DEFAULT_TARGET_COUNT = 10`
  - `BUSY_WATER_DURATION_S = 1200.0`
  - fixed acceptance document uses `dt_sim = 0.1`; ownship + 10 targets.
  - scene roles in the fixed document: seven crossing-give-way entries, one head-on entry, two overtaking entries; nominal preflight may classify some geometry as clear or another encounter, so configured role is not runtime risk truth.
- `colav_simulator/core/colav/encounter_lifecycle.py`
  - `PlannerOddProfile.primary_switch_confirmation_s = 10.0`
  - `_advance_primary()` selects an eligible winner, immediately preempts for hard emergency or `Rule17 MUST_ACT`, otherwise holds a challenger until the physical-time confirmation expires.
  - `_primary_sort_components()` compares hard emergency, Rule 17, committed-active, current/predicted domain violation, future severity, completeness, lifecycle phase, positive TCPA, DCPA, range, then `TrackKey` identity/generation.
  - `AggregateDirective.required_targets` preserves concurrent obligations.
- `colav_simulator/core/colav/threat_assessment.py`
  - `ThreatPriorityClass`: `RESPONSE_TIME_EMERGENCY`, `RULE17_MUST_ACT`, `COMMITTED_ACTIVE`, `CURRENT_DOMAIN_VIOLATION`, `PREDICTED_DOMAIN_VIOLATION`, `FUTURE_SEVERITY`, `UNKNOWN`, `MONITOR`.
  - `ThreatDisplayClass`: `CLEAR`, `LOW`, `HIGH`, `UNKNOWN`.
  - `ThreatAssessment.evaluate()` creates immutable per-target vectors from frozen request facts.
  - `_assess_target()` computes relative geometry, canonical DCPA/TCPA, hull clearance, uncertainty, current/predicted domain facts, completeness and evidence references.
- `colav_simulator/core/colav/threat_management.py`
  - `ThreatManagementCoordinator` is the session-level authority: one Lifecycle + one threat account per own ship/session.
  - `_priority_fact()` marks hard emergency when hull clearance <= 0 or current domain violation plus forward TCPA <= `action_start_window_s`; emits current/predicted violation, future severity and completeness facts.
  - `_resolved_priority()` turns lifecycle + vector facts into the published priority class/key/reason.
  - `_build_schedule()` assigns mutually exclusive `CURRENT_PRIMARY`, `CONCURRENT_REQUIRED`, `NEXT`, `MONITOR`, `RELEASED` contexts and emits typed schedule transitions.
- `colav_simulator/core/colav/kuwata_vo_alg/kuwata_vo.py`
  - VO evaluates every target's polygon-expanded hard/preferred clearance domains and candidate velocity grid.
  - `_target_priority()` is an execution-layer driving-target ordering: imminent first, active risk next, committed next, then earliest TTC/TCPA, DCPA, distance, target id.
  - `_select_driving_target()` picks the VO driving target; `_select_overtaking_target()` preserves committed overtaking target continuity.
  - This internal target is not a replacement for canonical Risk Primary; it is an algorithm execution choice and must not become a browser-owned risk truth.
- `web_gui/modules/telemetry-projection.js`
  - `projectThreatVector()` preserves backend display class, schedule class, priority class/key, lifecycle, window and DCPA/TCPA.
  - `projectRisk()` sorts display by backend schedule context then backend priority key; it never recomputes CPA or ranks by `TS1/TS2/TS3` naming.
- `web_gui/app.js`
  - Risk cards render `PRIMARY`, `REQUIRED`, `NEXT`, `MONITOR`, `SAFE`, `AVOIDING`, and `UNKNOWN` from projected backend fields.
  - event presentation exposes `Primary SWITCHED`, `Threat`, `Risk state`, `Avoidance`, `schedule`, observation, and COLREG transitions.
- `CONTEXT.md` and ADRs 0001–0005
  - define one canonical authority per threat fact, immutable cycle snapshots, schedule semantics and the boundary between Risk, Planner, L4 hard safety, Evaluator and Web.

## 10 船场景事实

| Fact | Current value |
|---|---:|
| Scenario id | `romsdal_busy_water_16` |
| Ownship + targets | 1 + 10 |
| Seed | `20250731` |
| Simulation dt | `0.1 s` |
| Scenario duration | `1200 s` |
| Target routes | single-pass route traffic in a fixed acceptance document |
| Algorithm example | `vo` + `god` tracker |
| Important identity rule | `TS1…TS10` is identity only, never priority |

The fixed YAML has target IDs and configured encounter roles. Static `preflight_document()` reports nominal probe points around TS2 ≈ 90.5 s, TS1 ≈ 110.3 s, TS4 ≈ 148.1 s, TS3 ≈ 186.4 s, TS5 ≈ 243.2 s, TS6 ≈ 278.6 s, TS7 ≈ 292.9 s, TS10 ≈ 348.8 s, TS9 ≈ 376.4 s, TS8 ≈ 390.1 s. These are scenario configuration / nominal geometry evidence, not a claim that Risk will switch exactly at those seconds. Runtime switching is driven by each cycle's canonical facts, windows, lifecycle and hysteresis.

## One cycle, one authority

```text
Ownship State + TrackSnapshot + Prediction Evidence
        ↓ freeze
Canonical PhysicalEncounterFacts (one per TrackKey)
        ├─ ThreatAssessment → ThreatVector / ThreatWindow
        └─ EncounterLifecycle → role / risk / commitment / Rule17 / Primary
        ↓ join in ThreatManagementCoordinator
Priority facts → schedule → typed events → conflict graph/cluster
        ├─ AggregateDirective → VO / Horizon Plan / control
        ├─ Web projection → Risk cards / route mode / event list
        └─ Evidence → audit / evaluator / replay
```

The browser consumes the immutable backend projection. It must not recalculate DCPA/TCPA, domain entry, target score, Primary or schedule.

## Per-target evaluation

For target `i`, freeze:

```text
r = p_target − p_own
v_rel = v_target − v_own
range = ||r||
signed_TCPA = −(r · v_rel) / ||v_rel||²
forward_TCPA = max(0, signed_TCPA)
DCPA = ||r + forward_TCPA · v_rel||
```

Then attach hull clearance, dimensions, covariance/uncertainty, observation health/age, TrackKey/generation, prediction basis, domain facts, completeness, lifecycle references and profile/evidence hashes. Relative motion undefined, stale/unusable observations, missing dimensions/profile or missing prediction become typed `UNKNOWN` / `UNAVAILABLE`; they are never silently converted to `CLEAR`.

## Domain and window

An off-centred ellipse plus uncertainty radius provides anticipatory exposure. The normalized domain scale is evaluated now and across the target prediction horizon. `scale < 1` means inside; `scale ≈ 1` tangent; `scale > 1` outside. The resulting window carries `TDV` (entry), peak exposure and `TDE` (exit), plus prediction basis and completeness. Ship Domain is an engineering threat interpretation, not the L4 swept-hull safety gate.

## What “score” means

Risk has no single weighted 0–100 safety score used for control. It publishes typed, lexicographic evidence:

```text
hard emergency
→ Rule17 MUST_ACT
→ committed + ACTIVE
→ current domain violation
→ predicted domain violation
→ future severity
→ evidence completeness
→ lifecycle phase
→ positive TCPA / DCPA / range
→ TrackKey + generation (deterministic tie-break)
```

`PrimaryPriorityFact` is evidence, not a scalar score. `ThreatPriorityClass` and `priority_key/reason` explain why a target won. A hard emergency cannot be diluted by averaging it with benign dimensions.

## Why targets do not flap

At cycle `t`, Lifecycle keeps the current Primary if a new challenger has not stayed best for `10 s` physical time. It emits `PRIMARY_CHALLENGER` / `HYSTERESIS_PENDING`; the challenger and remaining seconds are visible evidence. A hard response-time emergency or `Rule17 MUST_ACT` preempts immediately. Once confirmed, the transition emits `PRIMARY_SWITCH_CONFIRMED`; release/rearm emits its own typed event. TrackKey generation changes and session reset clear old switching context.

## Schedule semantics

- `CURRENT_PRIMARY`: current explanation and focus, exactly one.
- `CONCURRENT_REQUIRED`: active lifecycle/aggregate directive obligation; remains in the planner set even when another target is Primary.
- `NEXT`: predicted domain exposure or future obligation, not yet current focus.
- `MONITOR`: visible/evidence-retained, no current planner obligation.
- `RELEASED`: lifecycle released but retained for audit/history.

This is a rolling projection, not a fixed `A → B → C` script. After each ownship action, all target vectors/windows/schedule contexts are recomputed.

## VO execution boundary

Risk says what is threatening and which obligations must remain represented. VO then evaluates all dynamic targets against expanded hard/preferred clearance domains and candidate velocities, applies COLREG locks/commitments, and chooses a feasible heading/speed. VO's `_target_priority()` selects an execution-layer driving target for its candidate grid. That target can differ from the presentation Primary in edge cases; the shared contract must expose the distinction rather than let either side invent a second risk state.

## Typical 10-target VO switching story

1. `t=0`: all TS1–TS10 enter the same cycle. IDs are stable identity; schedule initially separates monitor/next/required according to facts, not lexical order.
2. A target's predicted window reaches the domain before current DCPA becomes alarming. Its vector becomes `PREDICTED_DOMAIN_VIOLATION`; Lifecycle may hold it as challenger while the current Primary remains stable.
3. After 10 s confirmation, the challenger becomes `CURRENT_PRIMARY`; the card moves to the top because backend schedule context changed, not because it is TS1.
4. If another target is already committed or has an active Rule17 duty, it moves/remains `CONCURRENT_REQUIRED`; it stays in the VO target set and aggregate directive while the Primary card changes.
5. If a hard hull-clearance / response-time condition or Rule17 `MUST_ACT` appears, the new target preempts immediately and the event list records the reason.
6. VO applies the directive and candidate-velocity constraints. When the action is achieved, display class changes `LOW → HIGH` (`MONITOR → AVOIDING` in UI wording); the schedule still decides whether the target is current, required, next or released.
7. As a target passes, its lifecycle moves toward release/rearm. Its evidence remains in the journal; another target can become Primary only after its own evidence wins the same lexicographic comparison/hysteresis gate.
8. Any accepted plan is evidence for the next cycle. Conflict graph analysis can distinguish direct window overlap from plan-induced worsening; raw candidate paths do not rewrite Risk truth.

## UI / evidence interpretation

The right sidebar should be read as:

```text
top card        = backend CURRENT_PRIMARY
red/high card   = canonical HIGH / avoidance action active
yellow/low card = canonical LOW / candidate or monitor exposure
green card      = canonical CLEAR
other cards     = REQUIRED / NEXT / MONITOR / RELEASED by schedule
event list      = backend operational transitions, not every solver heartbeat
```

Left ROUTE mode and right card action state must be projections of the same backend lifecycle/threat facts. A card order change is meaningful only with `Primary SWITCHED`, schedule transition or priority evidence; TS labels alone explain nothing.

## Acceptance boundary

This deck explains mechanism and decision evidence. It does not claim that a fixed 10-target scene proves global all-vessel safety, that nominal preflight is runtime Risk, or that a UI card is independent verification. G3 tuple evidence, real VO execution, L4 hard clearance and evaluator results remain separate evidence layers.
