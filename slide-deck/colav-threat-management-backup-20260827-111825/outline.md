# Slide Deck Outline

**Topic**: COLAV-SIMULATOR 的 Predictive Multi-Target Threat Management：威胁计算、排布与 Historical AIS Counterfactual 完整工作流
**Style**: sango-ai
**Dimensions**: paper + warm + editorial + dense
**Audience**: General readers
**Language**: zh
**Slide Count**: 18 slides
**Generated**: 2026-08-24
**skip_outline_review**: true
**skip_prompt_review**: true

---

<STYLE_INSTRUCTIONS>
Design Aesthetic: Clean 2D technical briefing with vintage blueprint aesthetic, aged cream paper texture, and bilingual explanatory text boxes. Dense information organized with clear visual hierarchy and multiple labeled callouts. Use a maritime engineering notebook feel: precise black outlines, restrained nautical symbols, and small English technical tokens inside Chinese annotations.

Background:
  Texture: Subtle aged paper texture with light creases and faint blueprint/grid traces.
  Base Color: Aged Cream (#F5F0E6).

Typography:
  Headlines: Bold display lettering in dark maroon (#5D3A3A), main titles in bracketed uppercase English tokens or strong Simplified Chinese narrative headlines.
  Labels: Clean sans-serif Simplified Chinese callout labels with compact bilingual technical tokens.
  Body: Clean geometric sans-serif, Near Black (#1A1A1A), readable at presentation scale.

Color Palette:
  Primary Text: Dark Maroon (#5D3A3A) - narrative headlines and section emphasis.
  Background: Aged Cream (#F5F0E6) - full-slide paper field.
  Accent 1: Teal (#2F7373) - canonical facts, safe flow, target trajectories, and approved evidence.
  Accent 2: Warm Brown (#8B7355) - secondary annotations, history, chart context, and provenance.
  Tertiary: Maroon (#722F37) - danger, priority, domain entry, and caution callouts.
  Outline: Deep Charcoal (#2D2D2D) - all diagrams, borders, axes, and vessel silhouettes.

Visual Elements:
  - Isometric/2D technical illustrations with black outlines, no photorealistic imagery.
  - 3-5 explanatory text boxes per slide; use short Chinese labels and English technical tokens.
  - Simplified top-down vessel silhouettes, compass arrows, ellipse domains, timeline ticks, and graph nodes.
  - Faded thematic background patterns: nautical chart contours, coordinate axes, ledger stamps, and evidence seals.
  - Split or triptych layouts for comparisons, authority boundaries, and workflow modes.

Density Guidelines:
  - Content per slide: Dense information organized with clear visual hierarchy; keep one main message and 3-5 callouts.
  - Whitespace: Balanced but compact; use framed panels and generous outer margins, never wall-of-text.

Style Rules:
  Do: Include substantive content, use Simplified Chinese callout labels, retain aged cream paper texture, keep all diagrams crisp, and make scope limitations visible.
  Don't: Use photorealistic renders, glossy gradients, decorative logos, slide numbers, page numbers, footers, or claims broader than the qualified evidence scope.
</STYLE_INSTRUCTIONS>

---

## Slide 1 of 18

**Type**: Cover
**Filename**: 01-slide-cover.png

// NARRATIVE GOAL
Set the central promise: one threat truth connects prediction, scheduling, control, and benchmark evidence.

// KEY CONTENT
Headline: `COLAV-SIMULATOR`
Sub-headline: `Predictive Multi-Target Threat Management`
Support line: `从威胁计算、动态排布，到 Historical AIS Counterfactual 完整闭环`

// VISUAL
Top-down maritime technical scene on aged paper: one ownship at center, two target vessels ahead, an elliptical Ship Domain, curved predicted tracks, a teal rolling schedule ribbon, and a maroon conflict cluster node. Small inset labels: `Threat Vector`, `TDV / TDE`, `Current / Next`, `T0`, `Compare`.

// LAYOUT
Layout: title-hero
Large title left-center; technical nautical diagram right; small maroon/teal callouts around the diagram; clean breathing room.

---

## Slide 2 of 18

**Type**: Content
**Filename**: 02-slide-why-dcpa-tcpa-not-enough.png

// NARRATIVE GOAL
Show why the old mental model “one target + one risk score” breaks in dense traffic.

// KEY CONTENT
Headline: `DCPA/TCPA 只能回答“会不会靠近”，还回答不了“谁先处理、谁会被影响”`
Body:
- Domain entry may happen before CPA becomes alarming.
- Primary focus cannot erase concurrent obligations.
- Avoiding A can create a later conflict with B.

// VISUAL
Split screen. Left: a simple DCPA/TCPA ruler with a target still outside CPA threshold but already touching a large forward domain. Right: three vessel paths where an ownship turn around A bends toward B. Use maroon question marks as small technical callouts, not decorative icons.

// LAYOUT
Layout: split-screen
Left “current metrics”; right “multi-target consequence”; central arrow `需要统一威胁账本`.

---

## Slide 3 of 18

**Type**: Content
**Filename**: 03-slide-baseline-and-scope.png

// NARRATIVE GOAL
Separate what exists, what is now validated, and what is not yet a full-archive claim.

// KEY CONTENT
Headline: `当前实现已经有骨架；验收范围仍然必须被锁住`
Body:
- Existing primitives: Encounter Lifecycle, Primary, horizon prediction, aggregate directive, AIS, ENC, evaluator, OpenBridge projection.
- Real acceptance window: 1 minute, 3 runtime actors, `romsdal-expanded` ENC.
- Full archive: 23 daily Parquet / 51.5M rows / ~1,226 MMSI — expansion source, not current acceptance.

// VISUAL
Three stacked evidence cards with stamps: `已有骨架`, `当前证明`, `未来扩展`. Include large numbers `23 days`, `51,522,509 rows`, `1,226 MMSI`, with a bold scope fence around `1 min / 3 actors`.

// LAYOUT
Layout: three-columns
Use three vertical cards: Runtime foundation, Qualified window, Expansion boundary; place a warm-brown caution strip under archive statistics.

---

## Slide 4 of 18

**Type**: Content
**Filename**: 04-slide-end-to-end-authority.png

// NARRATIVE GOAL
Give the audience the whole architecture before explaining individual calculations.

// KEY CONTENT
Headline: `一次 cycle 只发布一份 ThreatManagementSnapshot`
Body:
- `PhysicalEncounterFacts → ThreatAssessment → Lifecycle → Schedule / Graph`
- `Aggregate Directive → Horizon Encounter Plan → Mid-MPC / L4 acceptance`
- `Web / Evidence` consume the same snapshot; browser never creates truth.

// VISUAL
Layered left-to-right pipeline on a blueprint-like paper field. Highlight `ThreatManagementCoordinator` as a central teal framed authority. Separate lanes for `online threat`, `planner/L4`, `evaluator`, and `web projection`, connected only through immutable snapshots and accepted receipts.

// LAYOUT
Layout: hierarchical-layers
Four horizontal layers with authority badges; use maroon brackets around “sole authority” components and brown dashed boundaries around consumers.

---

## Slide 5 of 18

**Type**: Content
**Filename**: 05-slide-canonical-physical-facts.png

// NARRATIVE GOAL
Explain the first non-negotiable step: freeze one physical truth per target before deriving semantics.

// KEY CONTENT
Headline: `先冻结事实，再解释威胁`
Body:
- Ownship + TrackKey/generation + health/age + covariance.
- Relative position/velocity, range, DCPA, signed TCPA, forward TCPA, hull geometry.
- Lifecycle and ThreatAssessment consume the same fact; no duplicate CPA formulas.

// VISUAL
Central ownship/target coordinate sketch with vectors `r` and `v_rel`, surrounded by a fact-card ledger. Show `TrackKey = (target_id, generation)` and a small “UNKNOWN ≠ CLEAR” stamp. Use teal for valid facts, maroon for unavailable branches.

// LAYOUT
Layout: hub-spoke
Central coordinate geometry; five spokes to identity, motion, health, uncertainty, and provenance hash.

---

## Slide 6 of 18

**Type**: Content
**Filename**: 06-slide-threat-vector-calculation.png

// NARRATIVE GOAL
Make the per-target Threat Vector computation concrete and readable.

// KEY CONTENT
Headline: `每一艘目标船，都生成一条可审计 Threat Vector`
Body:
- `range = ||r||`, `v_rel = v_target − v_own`
- `signed_TCPA = −(r·v_rel)/||v_rel||²`, `DCPA = ||r + TCPA+·v_rel||`
- Add `hull clearance`, `health`, `prediction basis`, `completeness`, and evidence references.

// VISUAL
Large formula block on left, top-down relative-motion diagram on right. Below, a compact vector card with labeled fields: `DCPA`, `TCPA`, `Domain`, `TDV`, `TDE`, `Health`, `Evidence`. Use clean charcoal strokes and teal/maroon highlights.

// LAYOUT
Layout: split-screen
Formula and assumptions left; vector card and geometry right; include typed branch `RELATIVE_MOTION_UNDEFINED` in a brown note.

---

## Slide 7 of 18

**Type**: Content
**Filename**: 07-slide-ship-domain-threat-window.png

// NARRATIVE GOAL
Show how anticipatory Domain geometry becomes a time window, without pretending it is hard safety.

// KEY CONTENT
Headline: `把“未来会进入危险区”变成可解释时间窗`
Body:
- Off-centred ellipse: `fore / aft / port / starboard + uncertainty radius`.
- `scale < 1` = inside; `scale ≈ 1` = tangent; `scale > 1` = outside.
- `TDV → peak exposure → TDE`; missing profile/prediction becomes typed `UNKNOWN / UNQUALIFIED`.

// VISUAL
Left: off-centred ellipse around ownship with forward offset and uncertainty halo. Right: teal/maroon time-series curve of normalized Domain scale crossing horizontal `1.0` boundary, with entry `TDV`, minimum `peak`, exit `TDE`. Brown warning panel: `Ship Domain ≠ L4 hard clearance`.

// LAYOUT
Layout: two-columns
Geometry panel left; time window panel right; use a maroon vertical line for Domain entry and teal for exit.

---

## Slide 8 of 18

**Type**: Content
**Filename**: 08-slide-lexicographic-primary.png

// NARRATIVE GOAL
Explain both priority ranking and why Primary does not flap.

// KEY CONTENT
Headline: `Primary 不是最高分；它是有理由、可滞回的当前焦点`
Body:
- Priority ladder: emergency → `MUST_ACT` → committed active → current/predicted Domain violation → future severity → deterministic tie-break.
- No weighted average can dilute a hard emergency.
- Default physical-time hysteresis: 10 s; emergency / `Rule17 MUST_ACT` may preempt.

// VISUAL
Vertical maroon-to-teal priority ladder with seven rungs. At bottom, two target tokens `A` and `B` show `challenger pending 0–10s`; a red emergency arrow bypasses hysteresis. Add one label: `EncounterLifecycle = sole Primary authority`.

// LAYOUT
Layout: hierarchical-layers
Ladder dominates center; small right-side timeline demonstrates stable → challenger → confirmed switch.

---

## Slide 9 of 18

**Type**: Content
**Filename**: 09-slide-rolling-threat-schedule.png

// NARRATIVE GOAL
Make multi-target threat arrangement understandable as mutually exclusive semantic contexts.

// KEY CONTENT
Headline: `Threat Schedule 把“焦点”和“义务”分开`
Body:
- `CURRENT_PRIMARY`: current focus.
- `CONCURRENT_REQUIRED`: must satisfy together.
- `NEXT`: future threat; `MONITOR`: visible but no current obligation.
- Each rolling horizon recomputes membership; never a fixed `A → B → C` script.

// VISUAL
Four-lane horizontal schedule: Current Primary, Concurrent Required, Next, Monitor. Three vessel tokens move between lanes over two cycle snapshots, with arrows marked `rolling update`. Keep one target in Current and two in different downstream lanes to show non-exclusive focus.

// LAYOUT
Layout: linear-progression
Two time slices left-to-right; use teal for current obligation, warm brown for next/monitor, maroon for escalation event.

---

## Slide 10 of 18

**Type**: Content
**Filename**: 10-slide-conflict-graph-cluster.png

// NARRATIVE GOAL
Explain direct multi-target overlap versus plan-induced conflict and why provenance matters.

// KEY CONTENT
Headline: `真正危险的不只是一条船，而是威胁之间的连通关系`
Body:
- Direct edge: `DIRECT_WINDOW_OVERLAP` from overlapping Threat Windows.
- Plan-induced edge requires baseline + fresh accepted plan receipt + before/after witness.
- Connected components become deterministic `Conflict Cluster`; raw candidate / GUI path never qualifies.

// VISUAL
Graph diagram with three target nodes `A`, `B`, `C`. Show A–B direct overlap edge; B–C plan-induced edge with a receipt/hash seal; enclose all three in one teal cluster boundary. Beside it, a crossed-out raw solver candidate card.

// LAYOUT
Layout: hub-spoke
Graph centered; two evidence callouts on right: `typed witness` and `accepted-plan provenance`.

---

## Slide 11 of 18

**Type**: Content
**Filename**: 11-slide-threat-to-mid-mpc.png

// NARRATIVE GOAL
Clarify the boundary between threat interpretation, plan generation, hard safety, and the next cycle.

// KEY CONTENT
Headline: `Threat Management 不替 Planner 舵；它定义必须满足的约束`
Body:
- Lifecycle + schedule → Aggregate Directive: required targets, passing side, minimum course change, speed bounds.
- Horizon Encounter Plan projects `MISSION → ALTER → PASS → RECOVER`.
- Candidate → L4 accepted receipt; receipt applies next cycle, then conflict analysis rolls again.

// VISUAL
Four-stage conveyor: `Threat Snapshot` → `Aggregate Directive` → `Horizon Encounter Plan` → `Mid-MPC / L4`. Show a rejected raw candidate below and an accepted receipt crossing into the next cycle. Use teal for accepted flow, maroon for rejected/stale flow.

// LAYOUT
Layout: linear-progression
Use a looping arrow from accepted receipt back to the next `cycle`.

---

## Slide 12 of 18

**Type**: Content
**Filename**: 12-slide-hais-data-foundation.png

// NARRATIVE GOAL
Reframe Historical AIS as immutable, quality-aware dataset evidence rather than a CSV upload.

// KEY CONTENT
Headline: `Historical AIS 的第一步不是导入，而是建立不可变身份`
Body:
- HAIS GeoParquet: entry / archive / schema / selection / normalized digests.
- Predicate selection precedes full materialization; raw and normalized tracks coexist.
- Invalid values, duplicates, gaps, and unavailable fields remain typed quality findings.

// VISUAL
Large zip/archive card on left with `23 daily Parquet / 1.3 GiB`; a filter funnel in center (`UTC + MMSI + BBox`); right-side descriptor ledger with five digest stamps and a maroon quality-findings stack labeled `98 in current window`.

// LAYOUT
Layout: funnel
Archive wide at left, narrowing selection in center, immutable descriptor and normalized rows at right.

---

## Slide 13 of 18

**Type**: Content
**Filename**: 13-slide-actors-enc-dimensions.png

// NARRATIVE GOAL
Show how raw AIS becomes usable world truth with explicit chart and hull provenance.

// KEY CONTENT
Headline: `Actor、海图、尺寸，三条 provenance 缺一不可`
Body:
- Historical Actor preserves source row refs and only interpolates within a versioned gap policy.
- `ENCRegionProfile` binds CRS, extent, hazards, navigability, cache and qualification; current profile `romsdal-expanded` is `QUALIFIED`.
- Missing dimensions fail closed; no zero beam and no silent default hull.

// VISUAL
Triptych: Raw AIS observation → Historical Actor timeline → ENC chart + dimension registry. Show three vessel cards with `84.6×16.0`, `59.2×10.8`, `32.0×8.8 m`, plus a large `QUALIFIED` chart stamp and a crossed-out `default dimensions` card.

// LAYOUT
Layout: three-columns
Keep each provenance layer visually isolated, joined by thin teal arrows.

---

## Slide 14 of 18

**Type**: Content
**Filename**: 14-slide-t0-replay-counterfactual.png

// NARRATIVE GOAL
Explain the two workflow modes and the future-leakage invariant.

// KEY CONTENT
Headline: `T0 把“历史事实”与“算法行为”切成两段`
Body:
- Historical Replay: all actors playback; no COLAV algorithm.
- Counterfactual: before T0 playback; after T0 only Reference Vessel enters normal COLAV control.
- Human Reference after T0 is Compare-only; it never enters RunSpec, Planner, Guidance, prediction, or control.

// VISUAL
Horizontal timeline with `T0` vertical maroon cut. Before T0, three teal history tracks. After T0, Reference Vessel track changes to a teal control loop labeled `mid_mpc_ipopt`; two surrounding tracks remain brown playback. Human trajectory appears in a separate dashed Compare lane with a lock icon.

// LAYOUT
Layout: linear-progression
Use two stacked mode badges at top: `REPLAY` and `COUNTERFACTUAL`; bottom warning band states `post-T0 Human Reference = Compare-only`.

---

## Slide 15 of 18

**Type**: Content
**Filename**: 15-slide-romsdal-scene-setup.png

// NARRATIVE GOAL
Introduce the complete real multi-ship scene used for the walkthrough.

// KEY CONTENT
Headline: `Romsdal 真实窗口：一张海图、三艘 runtime actors、两个模式`
Body:
- Scene ID: `hais_romsdal_20260701_120000_120100`.
- Window: `12:00:00–12:01:00 UTC`; T0 `12:00:30`; BBox WGS84 `[6.05, 62.44, 6.17, 62.50]`.
- Reference `VALDERØY`; targets `FREYJA` and `PELAGIA HORDAFOR`.

// VISUAL
Top-down simplified Romsdal ENC chart: three distinct vessel silhouettes with names and MMSI, teal ownship route, brown historical target tracks, elliptical threat halos, small compass and BBox frame. Show a side panel with `24 rows / 3 actors / ENC PASS`.

// LAYOUT
Layout: image-caption
Map-like technical illustration dominates; right-bottom caption card lists scene identity and scope fence.

---

## Slide 16 of 18

**Type**: Content
**Filename**: 16-slide-multi-ship-cycle-story.png

// NARRATIVE GOAL
Walk through one full multi-ship cycle from source state to evidence.

// KEY CONTENT
Headline: `同一场景中，系统如何连续处理两条目标威胁`
Body:
- Freeze physical facts → calculate two vectors → Lifecycle chooses Primary with hysteresis.
- Schedule separates Current / Concurrent / Next; overlapping windows form one cluster.
- Mid-MPC controls only VALDERØY; next cycle re-evaluates after accepted receipt.

// VISUAL
Six-step numbered storyboard on a nautical chart strip: `1 Freeze`, `2 Vector`, `3 Primary`, `4 Schedule`, `5 Cluster`, `6 Recede`. Use two target rows with changing statuses and a circular arrow back to `next cycle`. Highlight “Primary ≠ Only Target” in a maroon callout.

// LAYOUT
Layout: winding-roadmap
Curved route through six stations, with small target icons and evidence seals at each station.

---

## Slide 17 of 18

**Type**: Content
**Filename**: 17-slide-openbridge-evidence-acceptance.png

// NARRATIVE GOAL
Connect backend authority to the OpenBridge UI and show what counts as acceptance evidence.

// KEY CONTENT
Headline: `OpenBridge 显示事实；验收显示证据；两者都不越权`
Body:
- `Deployment → MONITOR`: canonical Threat snapshot, Primary, DCPA/TCPA, schedule, cluster, planner state.
- `Scenario → Historical AIS`: source, window, actors, T0, ENC and limitations.
- `Evaluation → Benchmark`: stages, fallback, leakage, determinism, five Compare domains.
- Current proof scope: `fallback=false`, `2 / 2 / 1`, evaluator `PASS`, determinism `mismatches=[]`; only qualified three-actor window.

// VISUAL
OpenBridge-like 2D shell mockup with three framed regions: Monitor, Historical AIS scene, Benchmark evidence. Include evidence badges `CASE SUCCESS`, `LEAKAGE PASS_CONTRACT`, `COMPARE COMPLETE`, `SCOPE = 3 ACTORS`. Add a small brown note: `frontend final browser projection still closing`.

// LAYOUT
Layout: dashboard
Large central monitor panel, two smaller evidence cards, one explicit scope boundary card.

---

## Slide 18 of 18

**Type**: Back Cover
**Filename**: 18-slide-back-cover.png

// NARRATIVE GOAL
Close with the five principles and a concrete next action.

// KEY CONTENT
Headline: `把每一次避碰，都变成可解释、可复现、带范围的证据`
Body:
- One snapshot. One authority.
- Primary is focus, not exclusivity.
- Prediction is evidence, not control.
- T0 blocks future leakage.
- Acceptance always names its window, actors, and ODD.
Call to action: `下一步：用 dedicated Historical AIS workflow 扩展新窗口；每个窗口重新做 dimensions + ENC + T0 + deterministic rerun。`

// VISUAL
Minimal but rich closing blueprint: a sealed evidence ledger connected to a small three-vessel route, teal loop returning to a next-cycle arrow, and maroon scope bracket around `qualified window`. One large maroon statement, five small teal/brown principle labels.

// LAYOUT
Layout: quote-callout
Large closing statement left; five compact principle tags and a next-step arrow right; no thank-you text.
