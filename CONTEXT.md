# Colav-Simulator Validation

Language for assembling and running maritime collision-avoidance validation sessions.

## Language

**Validation Draft**:
An editable proposed configuration for one validation run. It is distinct from the specification owned by the current session.
_Avoid_: Active configuration, applied configuration

**Run Specification**:
An immutable configuration snapshot submitted to create a validation session.
_Avoid_: Draft, live configuration

**Exact Tuple**:
A Rule, Scenario, Algorithm, and Tracker combination recognized by the capability catalog as one indivisible execution choice.
_Avoid_: Cartesian product, independent selections

**Verified Tuple**:
An Exact Tuple backed by the catalog's verified capability evidence. Its evidence applies to that tuple, not to every use of its Algorithm or Tracker.
_Avoid_: Globally validated algorithm

**Experimental Tuple**:
An Exact Tuple permitted for experimental execution without the evidence claim of a Verified Tuple.
_Avoid_: Verified, G3 qualified

**Active Session**:
The system's single current validation session and its authoritative Run Specification.
_Avoid_: Current Draft, concurrent run

**Session Authority**:
A confirmed view of which Active Session the system currently owns, including confirmed absence. It is distinct from transport connectivity and lifecycle state.
_Avoid_: WebSocket status, connection state

**Telemetry Connection**:
The delivery status of the live snapshot stream for an Active Session. Losing it does not by itself invalidate Session Authority or change the Session state.
_Avoid_: Session failure, no session

**Session Replacement**:
An atomic change from one Active Session identity to another after Create, Reset, or Replay.
_Avoid_: Reset state transition, in-place replay

**Telemetry Envelope**:
A raw, versioned snapshot received for one Active Session before navigation, risk, planner, or evidence interpretation.
_Avoid_: View state, evaluation result

**Telemetry Projection**:
The derived read-only view of one Telemetry Envelope, owned by the projection module and rebuilt only when the envelope identity changes. It never talks to the network or the DOM.
_Avoid_: View model, controller state

**Projection Sections**:
The six interpretation sections of a Telemetry Projection — navigation, sensor, risk, planner, outcome, timeline — plus the read-only raw envelope reference. Sections stay independent; absent facts stay null instead of being invented.
_Avoid_: Merged safety flag, single risk score

**Planner Phase**:
Whether the current frame carried a real solver execution (`SOLVE`) or repeats the last frozen solve (`HOLD`). Nominal guidance counts as SOLVE without a solver run.
_Avoid_: Solver success, feasibility

**Display Selection Policy**:
The rule that planner diagnostics display the latest real SOLVE while it exists and otherwise the current frame's planner dict.
_Avoid_: Latest frame, newest planner

**Position Source**:
Which origin a displayed target position came from: `tracker` (tracker estimate) or `truth` (ground-truth state).
_Avoid_: Estimated flag, sensor blend

**Derived Event**:
A timeline event produced by the projection's own state machines (COLREGs change, DCPA level crossing) rather than delivered in the envelope.
_Avoid_: Backend event, lifecycle event

**Timeline Limitations**:
The standing constraints of the projection timeline: lifecycle events never appear in telemetry, history only covers observed snapshots, and Session Replacement clears it.
_Avoid_: Full run log, event history
# Collision Avoidance Planning

Colav-Simulator separates mission-following intent from temporary collision-avoidance intent across a rolling prediction horizon.

## Language

**Mission Route**:
The intended voyage route that remains authoritative before and after an encounter.
_Avoid_: Committed route, avoidance route

**Avoidance Corridor**:
A temporary passing-side course commitment used while an encounter remains active.
_Avoid_: Mission route, return route

**Horizon Encounter Plan**:
An immutable projection of alter, pass, and recover phases over one MPC prediction horizon. It predicts future phases without changing the authoritative encounter lifecycle.
_Avoid_: Current encounter state, solver trajectory

**Hard Row Window**:
A half-open control-interval range compiled from encounter phases into `lbg`/`ubg`. Windows change constraint activation without changing CasADi graph shape or decision dimension.
_Avoid_: Solver graph topology, lifecycle state

**Rolling Plan**:
The most recent accepted executable prediction, shifted onto the current absolute time axis and used as continuity authority for the next solve while its route, targets, capability, and safety assumptions remain valid.
_Avoid_: Warm start, current solver candidate, frozen mission route

**Plan Revision**:
An accepted departure from the Rolling Plan justified by changed safety, COLREG authority, target identity, Mission Route, or capability evidence.
_Avoid_: Solver churn, unexplained re-optimization

## Threat Management

**Canonical Authority**:
The one authority for one kind of domain fact. A canonical authority may be consumed by other contexts, but its fact is not reinterpreted as a competing truth elsewhere.
_Avoid_: One global risk score, shared mutable truth

**Physical Encounter Facts**:
The single online fact set produced at the start of each Threat Management Cycle from Ownship State and TrackSnapshot. It carries TrackKey/generation, observation health/age, relative position/velocity, range and bearings, signed TCPA, forward DCPA, validity or unavailable reason, and current hull geometry facts for shared consumption.
_Avoid_: COLREG role, risk phase, L4 candidate trajectory, Evaluator realized trajectory, safety verdict

**Encounter Lifecycle**:
The stateful interpretation of one own ship's encounter duties over time, including encounter kind, role, risk phase, commitment, Rule 17 stage, release, and rearm.
_Avoid_: Threat score, retrospective evaluation

**Threat Assessment**:
The interpretation of current and predicted encounter facts into domain exposure, threat windows, priority reasons, schedule membership, and conflict relationships.
_Avoid_: Encounter Lifecycle, hard safety verdict, independent evaluation

**Threat Management Cycle**:
A single coherent assessment interval for one own ship and one Active Session, from frozen current facts through one canonical threat account. A plan accepted during the interval becomes available as evidence in the next cycle, not as feedback into the same cycle.
_Avoid_: Solver iteration, GUI refresh, independent evaluation run

**Threat Management Snapshot**:
The immutable canonical account of one Threat Management Cycle, including current and predicted threat facts, lifecycle references, schedule, conflicts, and provenance for all consumers.
_Avoid_: Control command, L4 verdict, historical comparison

**Threat Vector**:
The independent per-target description of threat evidence, including physical, domain, prediction, observation-health, and lifecycle references.
_Avoid_: Scalar risk score, COLREG decision

**Ship Domain**:
An engineering safety envelope around a vessel whose shape and extent are defined by an explicit profile and assumptions.
_Avoid_: COLREG statutory limit, hard collision gate

**Threat Window**:
The predicted time interval in which a target enters, reaches, and leaves a defined threat condition, together with its prediction basis and completeness.
_Avoid_: Fixed maneuver schedule, instantaneous DCPA

**Threat Schedule**:
A rolling view that separates the current primary focus, concurrent required targets, future next threats, and monitor targets.
_Avoid_: Exclusive target list, executable control plan

**Primary Threat**:
The current focus used to explain or prioritize an encounter while other required targets remain active obligations.
_Avoid_: Only Target, sole safety constraint

**Concurrent Required Target**:
A target whose current lifecycle duty or safety obligation must remain represented while another target is primary.
_Avoid_: Display-only contact, optional target

**Next Threat**:
A target whose predicted threat window warrants future attention but has not become a current required obligation.
_Avoid_: Committed maneuver, guaranteed future collision

**Monitor Target**:
A tracked target retained for observation and evidence even though no current or near-term action obligation is established.
_Avoid_: Proven safe target, discarded target

**Direct Conflict**:
A conflict relationship supported by the targets' own predicted threat windows or safety domains.
_Avoid_: Plan-induced conflict

**Plan-Induced Conflict**:
A conflict that appears or materially worsens only when a trustworthy accepted own-ship plan is compared with an explicit baseline.
_Avoid_: Unaccepted solver candidate, GUI trajectory, direct encounter

**Conflict Cluster**:
A deterministic group of targets connected by typed conflict relationships.
_Avoid_: Opaque risk-score bucket, arbitrary visual grouping

**Hard Safety Gate**:
An independent safety condition whose failure cannot be neutralized by averaging it with benign threat dimensions.
_Avoid_: Advisory domain score, human-similarity measure

**Accepted Plan**:
An own-ship prediction that has passed the applicable execution and safety authority and may be used as plan evidence.
_Avoid_: Solver candidate, stale cached trajectory

**Independent Evaluator**:
The authority that assesses realized trajectories and events for Safety and COLREG behavior independently of the Planner's threat interpretation.
_Avoid_: Planner self-check, browser risk engine

**Observation Health**:
The quality and freshness of target evidence, separate from whether the target is currently threatening.
_Avoid_: CLEAR risk state, permission to forget a duty

**Historical Actor**:
A vessel reconstructed from historical AIS for a replay or counterfactual environment, distinct from the runtime tracker estimate presented to the Planner.
_Avoid_: Planner future knowledge, Human Reference trajectory
