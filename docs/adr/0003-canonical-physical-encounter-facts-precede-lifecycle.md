# Canonical Physical Encounter Facts Precede Lifecycle

> **Status**: accepted

At the start of each Threat Management Cycle, the Session/Runtime authority produces one immutable `Canonical PhysicalEncounterFacts` set from Ownship State and TrackSnapshot. It includes target identity (`TrackKey`/generation), observation health and age, relative position/velocity, range and bearings, signed TCPA, forward DCPA, validity or an unavailable reason, and current hull geometry facts. EncounterLifecycle and ThreatAssessment consume this same online fact set; the online chain must not recalculate equivalent CPA or geometry under different names.

## Boundary

The canonical facts describe the current online encounter evidence only. A candidate own-ship trajectory evaluated by the L4 Gate and a realized trajectory evaluated by the Independent Evaluator each retain their own facts and verdicts. Online CPA or geometry may not be presented as L4 candidate evidence or as a retrospective Evaluator verdict.

Legacy algorithms may consume the canonical facts and the shared ThreatManagementSnapshot, but their algorithm-specific observations are namespaced diagnostics and cannot become a competing canonical threat source.

## Considered Options

- **Canonical PhysicalEncounterFacts before Lifecycle (accepted)**: one cycle-start calculation supplies a stable physical basis to both Lifecycle and ThreatAssessment while preserving their different interpretations.
- **Lifecycle and ThreatAssessment each recalculate CPA/geometry (rejected)**: equivalent facts can drift in validity, signs, unavailable handling, hull assumptions, or units, creating parallel online truths.
- **Reuse online CPA as L4 or Evaluator evidence (rejected)**: current observation facts, candidate-plan trajectory facts, and realized-trajectory facts answer different questions and have different verdict owners.
- **Let legacy algorithms publish their own canonical physical facts (rejected)**: algorithm-specific implementations would fragment the online authority and make cross-algorithm Web/Evidence comparisons non-deterministic.

## Consequences

- The online chain has one physical-facts authority per cycle; Lifecycle and ThreatAssessment do not own duplicate CPA/geometry calculations.
- `validity` and `unavailable_reason` remain explicit; missing evidence cannot be converted to a safe numeric default.
- Formula/profile changes require versioned evidence and may change the canonical snapshot; they do not silently rewrite L4 or Evaluator history.
- L4 candidate safety and realized-trajectory evaluation remain independently auditable, even when they use related physical concepts.
