# Slide Deck Analysis

## Topic

COLAV-SIMULATOR Risk 模块机制：10 船场景 + VO 的目标评价、Primary 切换与闭环证据

## Core message

Risk 不是单一分数，而是后端统一事实驱动的多目标优先级与滚动调度。

## Audience matrix

| Question | Analysis |
|---|---|
| Primary reader | Experts/professionals：算法、仿真、Risk、前端和验证人员 |
| Existing belief | 可能把 DCPA/TCPA、红黄绿和 TS 编号当成完整风险排序 |
| Desired decision | 用 Threat Management 的 canonical snapshot 解释每次卡片排序、Primary 切换和 VO 执行边界 |
| Main barriers | Risk 向量不是标量分数；Primary 不是唯一目标；VO driving target 与 Risk Primary 不能混淆；配置事件时间不等于运行切换时间 |
| Convincing evidence | 当前源码、ADR/CONTEXT 术语、固定 10-target 场景参数、typed priority key/reason、10 s hysteresis、backend projection 字段 |

## Supporting points

1. 每 cycle 从 `PhysicalEncounterFacts` 生成可审计 Threat Vector / Threat Window。
2. Primary 使用词典序证据和物理时间滞回；硬紧急和 Rule 17 MUST_ACT 可抢占。
3. Threat Schedule 保留 Concurrent Required、Next、Monitor，避免多船焦点覆盖义务。
4. VO 对所有目标评估速度候选，但其执行层 driving target 不替代 Risk 的跨模块语义权威。
5. 10 船 VO 场景用真实参数、配置事件点和典型切换流程说明“何时切、为什么切、为何不切”。

## Content classification

- Technical architecture explainer
- Decision-logic walkthrough
- Multi-target simulation scenario story
- UI/evidence interpretation guide

## Scope guard

- 当前场景 `romsdal_busy_water_16` 有 10 个目标船、1 艘本船，不把名称中的 `16` 解读成当前目标数量。
- `preflight_document()` 的 nominal encounter 结果只用于说明配置与预检，不冒充实测 Risk transitions。
- Deck 说明机制和可解释证据，不把单次 VO 运行扩展为全船队安全证明。
- 保留旧 deck 到 `colav-threat-management-backup-20260827-111825/`；新 deck 完全使用新目录。

## Visual opportunity map

| Slide group | Visual treatment |
|---|---|
| 1–4 | Cover、误区、系统分层、单 cycle authority pipeline |
| 5–8 | 相对运动几何、Threat Vector、Domain Window、typed priority ladder |
| 9–12 | Primary hysteresis、Schedule 四泳道、Conflict Graph、Risk → VO boundary |
| 13–16 | 10-target scene map、target ledger、runtime timeline、target-switch decision cards |
| 17–19 | VO candidate grid、UI projection/event list、evidence separation |
| 20 | Synthesis / operational checklist |

## Narrative flow

1. 用“为什么不是 DCPA/TCPA 最大者就一定是 Primary”开场。
2. 先建立一 cycle 一快照和 canonical fact → vector → lifecycle/schedule 结构。
3. 展开真实判定：domain/window、priority classes、sort components、10 s hysteresis。
4. 明确 Risk 与 VO 的边界，避免把两种 target selection 当成一套模糊分数。
5. 将固定 10-target 场景参数映射到典型时序：monitor/next → challenger → primary/required → emergency preemption → avoidance/release。
6. 用 UI 和证据链收尾，说明卡片顺序、颜色、事件和验收边界。

## Style

- Preset: `sango-ai`
- Dimensions: paper + warm + editorial + dense
- Palette: aged cream `#F5F0E6`, maroon `#5D3A3A`, near black `#1A1A1A`, teal `#2F7373`, warm brown `#8B7355`, deep charcoal `#2D2D2D`
- Visual language: clean 2D technical briefing, vintage blueprint/paper, top-down nautical diagrams, concise Chinese labels with English code tokens.
- Avoid: photorealistic ships, glossy gradients, generic dashboard art, browser-owned risk claims, fabricated numeric runtime transitions.

## Final choices

- Audience: Experts/professionals
- Language: zh
- Slides: 20
- Outline review: yes
- Prompt review: no
- Image backend: Codex `imagegen` per user preference and skill priority
