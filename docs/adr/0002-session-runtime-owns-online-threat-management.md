# Session Runtime Owns Online Threat Management

> **Status**: accepted

One Session/Runtime-level `ThreatManagementCoordinator` owns online Threat Management for one own ship in one Active Session, with exactly one Encounter Lifecycle inside that authority. The Planner, Web, and Evidence consumers use the same immutable `ThreatManagementSnapshot`; the Planner does not create a second Lifecycle, and a plan accepted during cycle N is eligible only as input evidence for cycle N+1. This keeps one coherent online account without making the coordinator the L4 Gate or the Independent Evaluator.

## Cycle Order

1. Freeze the current Tracker/Observation facts, prior Lifecycle state, profiles, and any accepted-plan evidence already available at the start of the cycle.
2. Advance the coordinator's sole Encounter Lifecycle and derive one `ThreatManagementSnapshot`.
3. Let Planner, Web, and Evidence consume that same snapshot; the Planner may produce a candidate plan.
4. Evaluate the candidate through the independent L4 Gate. If accepted, publish its receipt after the current snapshot and make it eligible only for the next cycle.
5. Keep post-run Safety/COLREG assessment in the Independent Evaluator; it does not rewrite the online snapshot.

## Considered Options

- **Session/Runtime coordinator (accepted)**: gives one own ship and Active Session one online threat authority while preserving independent downstream safety and evaluation authorities.
- **Planner-owned online authority (rejected)**: would encourage a second Lifecycle or same-cycle plan feedback, allowing Planner-specific integrations to publish competing threat facts.
- **GUI-owned authority (rejected)**: would make rendering, browser refresh, and display fallbacks part of safety semantics and would recreate the existing divergence between server and browser risk logic.
- **One giant coordinator including L4 and Independent Evaluator (rejected)**: would collapse online prediction, executable-plan acceptance, and retrospective scoring into one self-certifying boundary.

## Consequences

- One Active Session has one online Lifecycle and one canonical `ThreatManagementSnapshot` per cycle.
- Planner, Web, and Evidence cannot silently disagree about current threat facts, ordering, or conflict membership.
- Accepted-plan evidence has a one-cycle boundary; same-cycle circular feedback is disallowed, and stale/unavailable plan evidence must remain explicit.
- Legacy algorithms may consume the canonical snapshot and publish namespaced diagnostics, but may not publish a competing canonical threat result.
- L4 Gate and Independent Evaluator remain separate authorities. Their failures or disagreements are evidence owned by those authorities, not rewritten by Threat Management.
- Session Replacement starts a new runtime authority and identity; prior snapshots remain historical evidence.
