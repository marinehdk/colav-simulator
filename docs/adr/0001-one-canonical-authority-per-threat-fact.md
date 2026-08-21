# One Canonical Authority per Threat Fact

> **Status**: accepted

Colav-Simulator will assign one canonical authority to each kind of threat-related fact: Tracker/Observation for current evidence, Encounter Lifecycle for stateful COLREG duties and Planner Primary, Backend Threat Assessment for online predictive threat facts and schedule, Plan Acceptance/L4 for executable hard safety, Independent Evaluator for realized Safety/COLREG assessment, and Web only for projection. We explicitly retain the L4 Gate and Independent Evaluator as separate authorities because executable-plan safety and retrospective behavior assessment answer different questions; combining them with online threat interpretation would permit planner self-certification and blur failure ownership. We reject a monolithic ThreatAssessment that also performs online control acceptance or offline evaluation, and reject parallel EncounterMonitor/browser risk engines because they would create competing risk, ordering, and verdict sources.

## Consequences

- A disagreement is reported as typed evidence or an unavailable fact; it is not silently resolved by a second score or fallback.
- Primary focus does not remove Lifecycle-required targets from planner obligations.
- Ship Domain and Threat Index facts remain separate from hard hull-clearance/L4 verdicts.
- Legacy `EncounterMonitor` may remain as diagnostic evidence, but it is not a canonical Planner or Web threat source.

## Rejected Alternatives

- One giant ThreatAssessment owning lifecycle, online threat management, L4 acceptance, and retrospective evaluation: rejected because it couples state, prediction, execution safety, and scoring, and allows self-certification.
- Browser/server-local risk engines in parallel with backend facts: rejected because DCPA/TCPA ordering, distance thresholds, and Primary selection can diverge.
