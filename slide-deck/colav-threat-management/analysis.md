# Slide Deck Analysis

## Topic

COLAV-SIMULATOR 的 Predictive Multi-Target Threat Management：威胁计算、排布与 Historical AIS Counterfactual 完整工作流

## Core message

COLAV-SIMULATOR 用单一威胁真相，把多船预测、动态排布和可复现实验串成闭环。

## Supporting points

1. Threat Vector 从 canonical physical facts 出发，融合 DCPA/TCPA、off-centred Ship Domain、TDV/TDE、预测完整性与 evidence provenance。
2. Encounter Lifecycle 保持唯一 Primary/Role/Rule17 authority；Threat Schedule 用 Current Primary、Concurrent Required、Next、Monitor 分离焦点与义务。
3. Accepted-plan provenance + Conflict Graph/Cluster 解释“避让 A 是否制造 B”，同时与 L4 hard safety、Independent Evaluator 解耦。
4. HAIS 从 immutable Dataset 经过 Actor reconstruction、ENC qualification、T0 handoff，进入正常 Simulator chain 和独立 Compare。
5. Romsdal 三船真实窗口证明当前已支持范围，同时明确 23 天/约 1,226 MMSI 全 archive 与前端最后一轮验收边界。

## Audience matrix

| Question | Analysis |
|---|---|
| Primary reader | General technical readers: algorithm, simulation, frontend, V&V collaborators |
| Existing belief | Threat may be understood as a risk score; AIS may be understood as import-only |
| Desired decision | Adopt the single-authority, rolling schedule, typed-evidence architecture and use the correct acceptance workflow |
| Main barriers | DCPA/TCPA vocabulary, Primary vs all targets, T0 leakage boundary, current three-actor scope |
| Convincing evidence | Source code contracts, canonical Spec, real acceptance manifest, API/WS/OpenBridge projection, explicit limitations |

## Content classification

- Technical architecture explainer
- Algorithm/data pipeline walkthrough
- Product/UI acceptance guide
- One real multi-ship scenario story

## Visual opportunity map

| Content | Priority | Visual treatment |
|---|---|---|
| End-to-end architecture | Must visualize | Layered pipeline / authority map |
| Threat Vector calculation | Must visualize | Relative-motion geometry + ellipse + horizon scale curve |
| Priority and schedule | Must visualize | Lexicographic ladder + four-lane schedule |
| Conflict graph/cluster | Must visualize | Nodes, direct overlap edge, plan-induced edge, connected component |
| Historical AIS benchmark | Must visualize | Dataset-to-Compare flow + T0 timeline |
| Real Romsdal window | Must visualize | ENC map-like nautical scene with three vessels and timeline |
| Evidence boundary | Should visualize | PASS cards with explicit scope fence |
| Code/status caveats | Text plus callout | “backend landed / UI acceptance still closing” badge |

## Narrative flow

1. Hook: “DCPA/TCPA 之后，还要回答什么？”
2. Context: current system has the primitives, missing unified authority and reproducibility.
3. Architecture: one coordinator, one snapshot, separated authorities.
4. How: calculate vector → window → priority → schedule → graph → planner.
5. Why: primary is focus, not exclusivity; rolling schedule avoids fixed A→B→C script.
6. Benchmark: immutable HAIS → case → T0 → normal closed loop → compare.
7. Story: Romsdal three-actor window end to end.
8. Close: five principles + acceptance boundary / next use.

## Visual style recommendation

- Preset: `sango-ai` (from project EXTEND.md and Chinese technical briefing signal)
- Dimensions: paper + warm + editorial + dense
- Palette: aged cream `#F5F0E6`, maroon `#5D3A3A`, near black `#1A1A1A`, teal `#2F7373`, warm brown `#8B7355`, deep charcoal `#2D2D2D`
- Use clean 2D technical illustrations, blueprint-like callouts, simple nautical top-down shapes, clear Chinese labels and English technical tokens.
- Avoid photorealistic renders, glossy gradients, generic stock-ship imagery and decorative logos.

## Slide-count recommendation

18 slides: enough room for formula, schedule semantics, conflict graph, historical workflow and one full real-data scenario without turning every slide into code.

## Call to action

After reading, the team should use `ThreatManagementSnapshot` as the single source of runtime threat truth, use the dedicated Historical AIS workflow for benchmark acceptance, and report results only within the qualified window/actor scope.

## Current-state caveat

The implementation worktree currently points to `db7509a` with uncommitted UI test/fixture changes while the referenced task is active. The deck should say backend/data contracts and the real three-actor evidence are implemented, while the last browser projection acceptance is still being closed. Do not label the full frontend or the entire HAIS archive as fully accepted.
