# Slide Deck Outline

**Topic**: COLAV-SIMULATOR Risk 模块：10 船场景 + VO 的目标评价、Primary 切换与闭环证据
**Style**: sango-ai
**Dimensions**: paper + warm + editorial + dense
**Audience**: Experts/professionals
**Language**: zh
**Slide Count**: 20 slides
**Generated**: 2026-08-27 11:30
**skip_outline_review**: false
**skip_prompt_review**: true

---

<STYLE_INSTRUCTIONS>
Design Aesthetic: Clean 2D technical briefing with vintage blueprint aesthetic, aged cream paper texture, and bilingual explanatory text boxes. Dense but readable engineering diagrams explain one decision per slide, with real code tokens as anchors.

Background:
  Texture: Subtle aged paper texture with light creases, faint coordinate grid, nautical chart contours, and ledger marks.
  Base Color: Aged Cream (#F5F0E6).

Typography:
  Headlines: Bold display lettering in dark maroon (#5D3A3A), all-caps English code tokens or strong Simplified Chinese narrative headlines.
  Labels: Clean sans-serif Simplified Chinese callouts with compact English identifiers such as TrackKey, TDV, Primary and VO.
  Body: Clean geometric sans-serif, Near Black (#1A1A1A), large enough for dense technical diagrams and formulas.

Color Palette:
  Primary Text: Dark Maroon (#5D3A3A) - narrative headlines, hard decisions, and section emphasis.
  Background: Aged Cream (#F5F0E6) - paper field and breathing room.
  Accent 1: Teal (#2F7373) - canonical facts, accepted flow, safe/monitor evidence, and target trajectories.
  Accent 2: Warm Brown (#8B7355) - prediction context, configuration, provenance, and secondary labels.
  Tertiary: Maroon (#722F37) - emergency, current threat, preemption, and caution.
  Outline: Deep Charcoal (#2D2D2D) - diagrams, axes, vessel silhouettes, formulas, and boundaries.

Visual Elements:
  - Clean 2D top-down vessels, relative-motion arrows, off-centred ellipse domains, timeline windows, priority ladders, and graph nodes.
  - Technical paper texture with light grid, dimension lines, evidence stamps, and restrained nautical chart contours.
  - Teal/maroon/warm-brown semantic colors; no traffic-light ambiguity without a legend.
  - Real code anchors in small monospace labels: `threat_assessment.py`, `encounter_lifecycle.py`, `threat_management.py`, `kuwata_vo.py`, `telemetry-projection.js`.
  - Use concise Chinese labels; never render long paragraphs, fake numeric telemetry, or decorative logos.

Density Guidelines:
  - Content per slide: one decision or mechanism, 3-5 short callouts, one dominant diagram.
  - Whitespace: balanced and compact; reserve clear margins and avoid text over diagrams.

Style Rules:
  Do: use substantive current-source concepts, label evidence boundaries, keep identity separate from priority, and make arrows/data ownership explicit.
  Don't: use photorealistic ships, glossy gradients, generic dashboard art, fabricated runtime transitions, scalar-risk shortcuts, slide numbers, footers, or logos.
</STYLE_INSTRUCTIONS>

---

## Slide 1 of 20

**Type**: Cover
**Filename**: 01-slide-cover.png

// NARRATIVE GOAL
Set the promise: one backend Risk truth connects ten targets, VO execution, UI and evidence.

// KEY CONTENT
Headline: `RISK 不是一个分数`
Sub-headline: `10 船场景 + VO：从目标事实到 Primary 切换的完整业务链`
Support line: `Canonical facts → Threat Vector → Lifecycle → Schedule → VO → Evidence`

// VISUAL
Top-down technical sea chart on aged cream paper. Ownship centered, ten small numbered target vessels distributed around it, curved prediction traces, one teal canonical snapshot spine, a maroon Primary ring, four schedule lanes, and a small VO candidate fan. Labels: `romsdal_busy_water_16`, `10 targets`, `1200 s`, `one authority`.

// LAYOUT
Layout: title-hero
Large Chinese title left; compact bilingual system diagram right; no decorative photo.

---

## Slide 2 of 20

**Type**: Content
**Filename**: 02-slide-identity-is-not-priority.png

// NARRATIVE GOAL
Break the common false assumption that TS1 is more important than TS2.

// KEY CONTENT
Headline: `TS1、TS2、TS10 只是身份；优先级来自证据`
Body:
- `TrackKey = (target_id, generation)` identifies one observation lineage.
- Card order follows backend schedule context + priority key.
- No lexical order, no browser distance sort, no hidden “TS1 first” rule.

// VISUAL
Ten target tokens labeled TS1–TS10 in a scattered chart. Cross out a fake vertical TS-number queue. Beside it, show a teal backend queue reordered as `CURRENT_PRIMARY → CONCURRENT_REQUIRED → NEXT → MONITOR`, with small priority-key brackets.

// LAYOUT
Layout: binary-comparison
Left “identity”; right “decision evidence”; central maroon arrow `not the same thing`.

---

## Slide 3 of 20

**Type**: Content
**Filename**: 03-slide-one-cycle-one-authority.png

// NARRATIVE GOAL
Establish ownership before formulas: every cycle publishes one immutable threat account.

// KEY CONTENT
Headline: `一次 cycle，只发布一份 ThreatManagementSnapshot`
Body:
- Freeze `Ownship State + TrackSnapshot + Prediction Evidence`.
- `ThreatAssessment` is pure derivation; `EncounterLifecycle` owns stateful meaning.
- Web, VO inputs, event journal and evidence consume the same snapshot.

// VISUAL
Layered horizontal authority pipeline. Center frame `ThreatManagementCoordinator` contains `PhysicalEncounterFacts`, `Threat Vector`, `Lifecycle`, `Schedule`, `Conflict Graph`; downstream lanes point to VO, Web and Evidence. Dashed boundary around consumers; maroon stamp `single source`.

// LAYOUT
Layout: hierarchical-layers
Four layers with arrows and clear ownership labels.

---

## Slide 4 of 20

**Type**: Content
**Filename**: 04-slide-cycle-pipeline.png

// NARRATIVE GOAL
Show the end-to-end business chain in one readable view.

// KEY CONTENT
Headline: `先冻结事实，再解释，再排布，再执行`
Body:
- `PhysicalEncounterFacts → ThreatAssessment / Lifecycle`
- `Priority → Schedule / Events / Conflict Graph`
- `AggregateDirective → VO → next cycle`

// VISUAL
Six numbered stations around a circular rolling arrow: ① facts, ② vector/window, ③ lifecycle, ④ priority/schedule, ⑤ VO candidate, ⑥ accepted evidence. A loop returns to ①; a small note says `accepted plan applies next cycle`.

// LAYOUT
Layout: circular-flow
Central loop, six stations, minimal text.

---

## Slide 5 of 20

**Type**: Content
**Filename**: 05-slide-physical-facts.png

// NARRATIVE GOAL
Explain the non-negotiable per-target input ledger.

// KEY CONTENT
Headline: `每艘目标先变成一条可追溯事实`
Body:
- `TrackKey / generation / health / age / covariance`
- `relative position / relative velocity / range / DCPA / signed TCPA`
- `hull geometry + dimensions + prediction provenance`

// VISUAL
Ownship-target coordinate sketch with `r` and `v_rel` arrows. Around it, a ledger card with the fields above and a hash seal. Teal valid rows; warm-brown degraded rows; maroon `UNKNOWN ≠ CLEAR` marker.

// LAYOUT
Layout: hub-spoke
Geometry hub with five evidence spokes.

---

## Slide 6 of 20

**Type**: Content
**Filename**: 06-slide-threat-vector-geometry.png

// NARRATIVE GOAL
Make the target evaluation math concrete without pretending it is a single risk score.

// KEY CONTENT
Headline: `Threat Vector 同时保存“现在、未来、证据完整度”`
Body:
- `r = p_target − p_own`, `v_rel = v_target − v_own`
- `signed_TCPA = −(r·v_rel)/||v_rel||²`; `DCPA` uses forward TCPA
- Append `hull clearance`, health, uncertainty, prediction basis and completeness.

// VISUAL
Left formula panel with large clean equations. Right target vector card: `DCPA`, `TCPA`, `Range`, `Hull`, `Health`, `Prediction`, `Completeness`, `Evidence hash`. A typed branch below reads `RELATIVE_MOTION_UNDEFINED → UNKNOWN`.

// LAYOUT
Layout: split-screen
Formula left; vector ledger right; use charcoal strokes and teal highlights.

---

## Slide 7 of 20

**Type**: Content
**Filename**: 07-slide-domain-threat-window.png

// NARRATIVE GOAL
Explain why Risk can act before a scary CPA snapshot.

// KEY CONTENT
Headline: `把“未来会进入危险区”变成 TDV—peak—TDE`
Body:
- Off-centred Ship Domain + uncertainty radius gives anticipatory exposure.
- `scale < 1` inside; `≈ 1` tangent; `> 1` outside.
- Missing profile, dimensions, covariance or prediction stays typed unavailable.

// VISUAL
Ownship inside an off-centred ellipse with a predicted target path crossing it. Beside it, a domain-scale curve crossing `1.0`, marked `TDV`, `peak`, `TDE`; brown boundary note `Ship Domain ≠ L4 hard safety`.

// LAYOUT
Layout: two-columns
Geometry left; time-window curve right.

---

## Slide 8 of 20

**Type**: Content
**Filename**: 08-slide-lexicographic-priority.png

// NARRATIVE GOAL
Answer the user’s “有没有量化评分” question precisely.

// KEY CONTENT
Headline: `有量化证据，但不是一个会稀释紧急性的总分`
Body:
- Priority classes: emergency → Rule17 MUST_ACT → committed active → current/predicted domain → future severity → unknown/monitor.
- `PrimaryPriorityFact` stores boolean/numeric evidence and reason.
- Final tie-break: positive TCPA, DCPA, range, `TrackKey`/generation.

// VISUAL
Tall maroon-to-teal lexicographic ladder with each class as a rung. A side-by-side weighted-average scale is crossed out because emergency cannot be averaged away. Small code anchor: `_primary_sort_components()`.

// LAYOUT
Layout: hierarchical-layers
Ladder dominates center; evidence fields in a right column.

---

## Slide 9 of 20

**Type**: Content
**Filename**: 09-slide-primary-hysteresis.png

// NARRATIVE GOAL
Explain stable target switching and immediate preemption.

// KEY CONTENT
Headline: `Primary 切换有滞回；硬紧急可以抢占`
Body:
- New winner becomes `PRIMARY_CHALLENGER`, not immediate switch.
- Default confirmation: `10 s` physical time.
- `hard emergency` or `Rule17 MUST_ACT` → immediate preempt; every transition is typed evidence.

// VISUAL
Horizontal timeline: current TS2 stable, TS7 challenger starts, a 10-second bracket, then `PRIMARY_SWITCH_CONFIRMED`. A red emergency arrow jumps over the bracket. Event labels: `HYSTERESIS_PENDING`, `PREEMPT_RULE17_MUST_ACT`.

// LAYOUT
Layout: linear-progression
Timeline centered with current/challenger lanes.

---

## Slide 10 of 20

**Type**: Content
**Filename**: 10-slide-schedule-contexts.png

// NARRATIVE GOAL
Show why Primary does not erase other obligations.

// KEY CONTENT
Headline: `Primary 是焦点，不是唯一约束`
Body:
- `CURRENT_PRIMARY`: one current focus.
- `CONCURRENT_REQUIRED`: active obligation remains in directive/VO target set.
- `NEXT / MONITOR / RELEASED`: rolling future, evidence-only, and retained history.

// VISUAL
Four wide schedule lanes with TS2 in Primary, TS4/TS7 in Required, TS8 in Next, TS1/TS3/TS5/TS6/TS9/TS10 in Monitor. Arrows show a rolling update; no TS-number ordering.

// LAYOUT
Layout: linear-progression
Four lanes across two cycle snapshots.

---

## Slide 11 of 20

**Type**: Content
**Filename**: 11-slide-conflict-graph.png

// NARRATIVE GOAL
Explain how the system notices that avoiding one target can affect another.

// KEY CONTENT
Headline: `多船风险还要看“威胁之间的连通关系”`
Body:
- `DIRECT_WINDOW_OVERLAP`: target windows overlap in time.
- `PLAN_INDUCED_CONFLICT`: fresh accepted plan worsens another target against a baseline.
- Typed witnesses/hashes form deterministic conflict clusters; raw GUI paths do not.

// VISUAL
Three target nodes A/B/C. A–B solid teal direct-overlap edge; B–C dashed maroon plan-induced edge with accepted-plan receipt/hash seal; all enclosed in one cluster boundary. Cross out stale candidate.

// LAYOUT
Layout: hub-spoke
Graph centered, provenance callouts right.

---

## Slide 12 of 20

**Type**: Content
**Filename**: 12-slide-risk-to-vo-boundary.png

// NARRATIVE GOAL
Separate Risk semantics from VO control execution.

// KEY CONTENT
Headline: `Risk 规定必须满足什么；VO 决定可执行的航向和速度`
Body:
- Risk/Lifecycle/Schedule → `AggregateDirective` with required targets and commitments.
- VO evaluates all dynamic targets, expanded hard/preferred domains and candidate velocities.
- VO driving target is execution-layer choice, not a second browser-owned Risk Primary.

// VISUAL
Two-lane pipeline: upper lane Risk `snapshot → directive`; lower lane VO `target polygons → candidate grid → heading/speed`. A vertical boundary says `planner-agnostic authority`; a loop returns accepted evidence to next cycle.

// LAYOUT
Layout: hierarchical-layers
Risk upper, VO lower, shared boundary center.

---

## Slide 13 of 20

**Type**: Content
**Filename**: 13-slide-10ship-scene-setup.png

// NARRATIVE GOAL
Anchor the explanation in the requested fixed 10-target VO scene.

// KEY CONTENT
Headline: `romsdal_busy_water_16：1 艘本船 + 10 艘目标`
Body:
- `seed 20250731` · `dt 0.1 s` · `t_end 1200 s`
- Fixed acceptance document: seven crossing-give-way, one head-on, two overtaking configurations.
- `TS1…TS10` remain identity; runtime Risk still comes from current facts.

// VISUAL
Wide nautical chart with ownship route and ten target tracks around it. A compact evidence card shows `10 targets`, `0.1 s`, `1200 s`, `VO + god`. Warm-brown note: `configured encounter ≠ runtime Risk`.

// LAYOUT
Layout: dashboard
Map 60%; metric/evidence cards 40%.

---

## Slide 14 of 20

**Type**: Content
**Filename**: 14-slide-t0-target-ledger.png

// NARRATIVE GOAL
Show what happens at T0 before any target is promoted.

// KEY CONTENT
Headline: `T0：十个目标一起评估，先分层，不先按编号排队`
Body:
- Every TS gets one physical fact, vector, window, lifecycle reference and priority key.
- Typical initial split: `MONITOR` for evidence-only, `NEXT` for predicted windows, `REQUIRED` for active duties.
- No domain/prediction evidence → `UNKNOWN`, never fake green.

// VISUAL
A ten-row ledger with columns `TS`, `DCPA`, `TCPA`, `Domain`, `Completeness`, `Schedule`. Highlight three rows with different semantic colors; an arrow feeds four schedule lanes. Avoid fabricated exact values; use `backend snapshot` labels.

// LAYOUT
Layout: split-screen
Ledger left, schedule lanes right.

---

## Slide 15 of 20

**Type**: Content
**Filename**: 15-slide-runtime-timeline.png

// NARRATIVE GOAL
Connect the fixed scene’s nominal configured time points to rolling runtime decisions without overstating them.

// KEY CONTENT
Headline: `时间点只是窗口线索；切换由每个 cycle 的证据决定`
Body:
- Nominal preflight probes: TS2 ≈ 90 s, TS1 ≈ 110 s, TS4 ≈ 148 s, TS3 ≈ 186 s.
- Later configured probes: TS5/TS6/TS7 ≈ 243/279/293 s; TS10/TS9/TS8 ≈ 349/376/390 s.
- These are not fixed A→B→C commands; actual `TDV`, lifecycle and hysteresis decide.

// VISUAL
Long 0–420 s timeline with target labels at nominal probe marks. Overlay a separate rolling-window band and a large brown stamp `configuration evidence ≠ runtime transition`. Teal arrows show recalculation after every ownship action.

// LAYOUT
Layout: linear-progression
Timeline full width, notes above/below.

---

## Slide 16 of 20

**Type**: Content
**Filename**: 16-slide-switch-example.png

// NARRATIVE GOAL
Walk through one representative target switch with all evidence fields.

// KEY CONTENT
Headline: `示意：TS2 先成为焦点，TS7 只有证据赢过才会切换`
Body:
- TS2: current primary because its lifecycle/priority key wins now.
- TS7: predicted/current domain or Rule17 evidence makes it challenger; 10 s hold prevents one-cycle flap.
- Hard emergency/MUST_ACT bypasses hold; otherwise switch event records decisive factor.

// VISUAL
Three snapshots `cycle k / k+1 / k+N`: TS2 current, TS7 challenger with countdown, TS7 confirmed primary. Include a compact decision card with `winning_class`, `decisive_factor`, `switch_reason`, `preempted`.

// LAYOUT
Layout: three-columns
Each cycle snapshot as a framed panel; arrows show only evidence-driven transition.

---

## Slide 17 of 20

**Type**: Content
**Filename**: 17-slide-required-and-release.png

// NARRATIVE GOAL
Show a target becoming non-primary without disappearing from control or evidence.

// KEY CONTENT
Headline: `Primary 换了，Concurrent Required 不能丢`
Body:
- TS4 remains `CONCURRENT_REQUIRED` while TS7 is current focus.
- VO receives required target set and evaluates all target domains together.
- After pass/release, TS4 moves to `RELEASED`; event journal keeps the transition.

// VISUAL
Flow of one target card: `CURRENT_PRIMARY → CONCURRENT_REQUIRED → RELEASED`, while another card becomes Primary. A translucent “still in VO set” bracket stays around Required. Teal accepted path; maroon action path.

// LAYOUT
Layout: winding-roadmap
One target lifecycle path with side obligation lane.

---

## Slide 18 of 20

**Type**: Content
**Filename**: 18-slide-vo-candidate-grid.png

// NARRATIVE GOAL
Make the VO execution decision visible and distinguish it from Risk ranking.

// KEY CONTENT
Headline: `VO 对十个目标都做约束；只把最紧迫者作为 driving target`
Body:
- Expanded target polygons create hard/preferred clearance domains.
- Candidate velocity grid is filtered by dynamic hazards, COLREG locks and commitments.
- `_target_priority()` orders imminent → active → committed → TTC/TCPA/DCPA/range; selected heading/speed becomes the next telemetry frame.

// VISUAL
Left top-down candidate velocity fan with forbidden maroon regions and teal feasible region. Right mini table compares `Risk Primary`, `Concurrent Required`, `VO driving target`; a clear warning says `three different roles, one shared evidence chain`.

// LAYOUT
Layout: split-screen
Candidate grid left; role comparison right.

---

## Slide 19 of 20

**Type**: Content
**Filename**: 19-slide-ui-evidence-projection.png

// NARRATIVE GOAL
Show how operators see the same backend decision and how events explain movement.

// KEY CONTENT
Headline: `右侧卡片和事件列表，只投影 Risk 的决定`
Body:
- Card order: backend schedule context → backend priority key; target name never ranks.
- Colors: `CLEAR` safe, `LOW` monitor/candidate, `HIGH` avoiding, `UNKNOWN` unavailable.
- Events: `PRIMARY SWITCHED`, `Threat`, `Risk state`, `Avoidance`, schedule and observation transitions.

// VISUAL
Mock OpenBridge right sidebar: top card `PRIMARY TS7`, below `REQUIRED TS4`, `NEXT TS8`, `MONITOR TS1…`; event list shows `Primary SWITCHED`, `HYSTERESIS_PENDING`, `Avoidance ACTIVE`. Left inset maps exact source files `telemetry-projection.js` and `app.js`.

// LAYOUT
Layout: split-screen
Sidebar projection right; source/semantic legend left.

---

## Slide 20 of 20

**Type**: Back Cover
**Filename**: 20-slide-back-cover.png

// NARRATIVE GOAL
Leave an operational checklist for interpreting and validating Risk behavior.

// KEY CONTENT
Headline: `看 Risk，不问“谁是 TS1”；要问“哪条证据赢了”`
Body:
- Verify one canonical snapshot and its provenance.
- Explain Primary with class, priority key, decisive factor, switch reason and hysteresis/preemption.
- Keep Risk, VO execution, L4 hard safety and Evaluator as separate evidence layers.
Call-to-action: `调试下一次切换：先查 backend snapshot，再查 schedule event，最后查 VO candidate。`

// VISUAL
Clean closing diagram: one immutable snapshot feeds four labeled gates `Risk`, `VO`, `L4`, `Evidence`; a maroon question mark over TS labels and a teal check over `reason + provenance + time`. Strong breathing room.

// LAYOUT
Layout: quote-callout
Large memorable line; compact four-gate diagram below.
