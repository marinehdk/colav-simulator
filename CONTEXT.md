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
