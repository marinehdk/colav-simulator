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

**Product Capability Policy**:
The explicit allowlist for integrations exposed by the product Config/API surface: VO, Fan-MPC, and Mid-MPC with the God tracker. It is separate from the registry, which may retain legacy builders for internal Historical Replay and evaluator fixtures.
_Avoid_: Every registered integration is selectable

**Product-Selectable Exact Tuple**:
An Exact Tuple that passes the Product Capability Policy and has verified or explicitly experimental evidence for the selected Rule and Scenario.
_Avoid_: Globally available algorithm, registry entry

**Internal Legacy Tuple**:
An exact tuple retained for Historical Replay, evaluator baselines, or compatibility tests but rejected by product session validation and omitted from selectable capability evidence.
_Avoid_: User-selectable capability

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

**Operational Event**:
A backend-owned, operator-relevant transition copied from Session, canonical Threat Management, Encounter Lifecycle, or material planner health. Repeated successful solves and per-step heartbeats remain raw audit evidence, not Operational Events.
_Avoid_: Browser-derived risk event, solver heartbeat

**Operational Event Journal**:
The bounded current-Session history delivered in each telemetry envelope so reconnecting consumers recover the same event identity, time, content, and order.
_Avoid_: Browser-local history, per-frame event delta

**Timeline Limitations**:
The Operational Event Journal and projection timeline retain the latest 1000 core events; raw audit artifacts may contain additional solver cadence, and Session Replacement clears the timeline.
_Avoid_: Unbounded audit log, browser Risk state machine
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
_Avoid_: Unaccepted candidate trajectory, GUI trajectory, direct encounter

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

**Algorithm Handoff**:
The one-way atomic transfer of Counterfactual Ownship control from Historical Reference motion to the selected algorithm when the canonical Encounter Lifecycle first reaches `ACTIVE`. Control is not returned during that Active Session.
_Avoid_: Fixed T0, first predicted threat, current-domain emergency, historical rejoin

**Shadow Ownship**:
The immutable Historical Reference continuation displayed beside Counterfactual Ownship after Algorithm Handoff. It is comparison-only and never participates in tracking, Threat Management, Planner input, control, collision detection, or realized counterfactual evaluation.
_Avoid_: Second own ship, ghost obstacle, planner target

**Shadow Deviation**:
The same-time planar separation between Counterfactual Ownship and Shadow Ownship after Algorithm Handoff. It is comparison evidence, not a safety clearance or navigation error.
_Avoid_: Cross-track error, DCPA, hull clearance

**Shadow Comparison**:
The backend-owned, same-time comparison between Counterfactual Ownship and Shadow Ownship, including motion divergence and separately scoped realized-clearance summaries. It does not issue an Independent Evaluator verdict or assume either trajectory is preferable.
_Avoid_: Counterfactual safety verdict, browser comparison engine, human optimality claim

**Historical Playback Origin**:
The first source instant at which every required runtime actor has a valid reconstructed state; it maps to simulation elapsed time zero while retaining absolute AIS UTC identity. Earlier selected observations may serve as reconstruction lookback but are not playable frames.
_Avoid_: Dataset selection start, first archive row, extrapolated start

**Live Counterfactual Session**:
An ordinary Active Session that advances Historical Actors, canonical Threat Management, and the selected algorithm together on each runtime tick. Its Deployment telemetry is produced online rather than replayed from a precomputed algorithm run.
_Avoid_: Cached result playback, pre-rendered counterfactual, benchmark replay

**Historical Display Qualification**:
Pre-publication evidence that a bounded Historical AIS window naturally reaches the required canonical Encounter Lifecycle phases, including `ACTIVE`, without forced activation or altered safety thresholds. An unqualified window cannot enter the product scenario catalog.
_Avoid_: Runtime fallback, scenario-specific trigger, algorithm PASS

**Traffic Context Target**:
A published Historical Actor that remains present in the same bounded time-space as the qualifying encounter and stays visible regardless of whether its lifecycle is `ACTIVE`, `MONITOR`, or `CLEAR`.
_Avoid_: Decorative vessel, risk-filtered contact, Shadow Ownship

**Assumed Historical Hull**:
A versioned `85m x 16m`, `3m` draft physical profile assigned to a Historical Actor whose source-provenanced dimensions are unavailable. The assumption is visible and participates in tracking, Threat Management, planning, Ship Domain, and collision evaluation exactly as declared.
_Avoid_: Display-only size, proven vessel dimensions, invisible planner fallback

**Historical Interpolation Segment**:
An endpoint-exact linear UTM position and velocity reconstruction between two observed AIS reports no more than `300s` apart, accepted only when the segment remains inside qualified navigable ENC water.
_Avoid_: Spline-smoothed route, land-avoiding invented path, ghost extrapolation

**Ownship-Follow View**:
The default Historical AIS chart view centered on the currently controlled Ownship with a `6NM` total horizontal span. After Algorithm Handoff it follows Counterfactual Ownship while Shadow Ownship remains comparison context.
_Avoid_: Full qualified ENC extent, target-centred view, synthetic-route fit

**Historical Algorithm Qualification**:
Full-window evidence that one selected algorithm accepts every admitted Historical Target and completes the Live Counterfactual Session without target pruning or fallback. Only qualified algorithm/scene tuples may enter the product catalog.
_Avoid_: Registry availability, partial target run, capacity fallback

**Historical Reference Route**:
The three-point route sealed before execution from factual Ownship AIS: playback start, the observed point with maximum perpendicular deviation from the start-to-final chord, and the final observed point. It is declared scenario route geometry; runtime Shadow updates, timestamps, target futures, and future control values remain outside Planner authority.
_Avoid_: Runtime Shadow feedback, synthetic 10km waypoint, target future leakage

**Local Moving Traffic Set**:
The Historical AIS runtime subset containing Ownship and the three user-accepted moving contacts in the encounter water area. All 35 bounded source contacts remain in Dataset lineage, but stationary/harbour contacts are excluded before runtime actor, tracker, Threat, Planner, and display assembly.
_Avoid_: Display-only pruning, hidden planner targets, deleting source AIS evidence

**Recovery Complete**:
The post-encounter state in which all relevant targets are `RELEASED` and Counterfactual Ownship remains within `100m` cross-track and `5deg` course error of the nearest leg of the Historical Reference Route for the final continuous `30s`.
_Avoid_: Threat release alone, one recovered tick, Shadow rejoin
