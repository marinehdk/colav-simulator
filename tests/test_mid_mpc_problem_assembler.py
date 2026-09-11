import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput, TrackedObstacle
from colav_simulator.core.colav.encounter_lifecycle import (
    CommitmentPhase,
    DecisionSnapshot,
    EncounterCycle,
    EncounterKind,
    EncounterLifecycle,
    Maneuverability,
    ObservationHealth,
    OwnshipObservation,
    OwnshipRole,
    PassingSide,
    PlannerOddProfile,
    RiskPhase,
    Rule17Stage,
    TargetObservation,
)
from colav_simulator.core.colav.horizon_encounter_plan import (
    HorizonEncounterPhase,
    HorizonEncounterPlan,
    TargetHorizonWindow,
)
from colav_simulator.core.colav.mid_mpc import MidMpcConfig
from colav_simulator.core.colav.mid_mpc.solver import _prepare, _row_layout
from colav_simulator.core.colav.mid_mpc_assembler import (
    AssemblyFailure,
    AssemblyFailureCode,
    AssemblyFrame,
    AssemblyProfile,
    AssemblyRequest,
    AssemblySuccess,
    CapabilitySnapshot,
    MidMpcAssemblyConfig,
    MidMpcProblemAssembler,
    RouteReference,
    _scheduled_corridor_threshold,
    _staged_route_references,
)
from colav_simulator.core.colav.rolling_plan import PlanRevisionReason, RollingPlanReference
from colav_simulator.core.tracking.trackers import TrackKey


def test_scheduled_corridor_can_be_reentered_at_the_declared_turn_rate(monkeypatch) -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    request = _request(planner_input, snapshot)
    n = request.config.horizon_steps
    corridor = 0.7
    plan = HorizonEncounterPlan(
        reference_time_s=5.0,
        times_s=np.arange(n + 1) * request.config.horizon_dt_s,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=corridor,
        phases=(HorizonEncounterPhase.PASS,) * (n + 1),
        recovery_from_k=None,
        target_windows=(
            TargetHorizonWindow(TrackKey(1, 1), 0, None, False, 200.0, 0.0, corridor_bearing_rad=corridor, passing_side=1),
        ),
        corridor_reference_rad=(corridor,) * (n + 1),
    )
    monkeypatch.setattr(
        "colav_simulator.core.colav.mid_mpc_assembler._compile_horizon_encounter_plan", lambda *args, **kwargs: plan
    )
    outcome = MidMpcProblemAssembler().assemble(request)
    assert isinstance(outcome, AssemblySuccess)
    bounds = outcome.problem.row_schedule.course_bounds_rad
    step = request.capability.rot_max_rad_s * request.config.horizon_dt_s
    assert bounds[0][0] <= step
    assert bounds[1][0] <= 2.0 * step
    assert bounds[2][0] == pytest.approx(corridor)


@pytest.mark.parametrize("side", [-1, 1])
@pytest.mark.parametrize("turns", [0, 1])
def test_late_hard_corridor_is_inside_solver_heading_envelope(monkeypatch, side: int, turns: int) -> None:
    planner_input = _planner_input()
    state = planner_input.ownship_state.copy()
    state[2] = turns * 2.0 * math.pi
    planner_input = replace(planner_input, ownship_state=state)
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    request = _request(planner_input, snapshot)
    n = request.config.horizon_steps
    corridor = side * 1.2
    plan = HorizonEncounterPlan(
        reference_time_s=5.0,
        times_s=np.arange(n + 1) * request.config.horizon_dt_s,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=0.0,
        phases=(HorizonEncounterPhase.MISSION,) * (n - 1) + (HorizonEncounterPhase.ALTER,) * 2,
        recovery_from_k=None,
        target_windows=(
            TargetHorizonWindow(
                TrackKey(1, 1),
                n - 1,
                None,
                False,
                200.0,
                0.2,
                action_start_k=n - 2,
                corridor_bearing_rad=corridor,
                passing_side=side,
            ),
        ),
        corridor_reference_rad=(0.0,) * (n - 1) + (corridor,) * 2,
    )
    monkeypatch.setattr(
        "colav_simulator.core.colav.mid_mpc_assembler._compile_horizon_encounter_plan", lambda *args, **kwargs: plan
    )
    outcome = MidMpcProblemAssembler().assemble(request)
    assert isinstance(outcome, AssemblySuccess)
    config = MidMpcConfig(horizon_steps=n, dt_s=request.config.horizon_dt_s, strict_slack_bounds=True)
    prepared = _prepare(
        config, outcome.problem, _row_layout(config, len(outcome.problem.targets), outcome.problem.audit_row_count)
    )
    assert np.all(prepared.lbx <= prepared.ubx)
    scheduled = outcome.problem.row_schedule.course_bounds_rad[-1]
    assert scheduled[0 if side > 0 else 1] == pytest.approx(state[2] + corridor)
    assert outcome.problem.rot_max_rad_s == request.capability.rot_max_rad_s


def test_assembler_returns_atomic_typed_failure_for_cycle_mismatch() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    mismatched = replace(snapshot, sim_time_s=10.0)

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, mismatched))

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.CYCLE_MISMATCH
    assert outcome.owner == "ASSEMBLER"
    assert outcome.problem is None
    assert outcome.identity["epoch"] == "test"
    assert outcome.identity["sequence"] == 1


@pytest.mark.parametrize("field", ["cycle_input_hash", "lifecycle_profile_hash"])
def test_assembler_rejects_snapshot_identity_hash_mismatch(field: str) -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    request = replace(_request(planner_input, snapshot), **{field: "0" * 64})

    outcome = MidMpcProblemAssembler().assemble(request)

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.CYCLE_MISMATCH
    assert outcome.problem is None


def test_assembler_rejects_non_enu_frame_before_problem_construction() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(replace(_request(planner_input, snapshot), frame=AssemblyFrame.NED))

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.INVALID_INPUT
    assert outcome.problem is None
    assert "ENU" in outcome.message


def test_assembler_binds_targets_deterministically_and_emits_81_point_predictions() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    first_track = planner_input.tracks[0]
    second_track = replace(
        first_track,
        target_id=2,
        state_enu=np.array([1200.0, 200.0, -5.0, 0.0]),
    )
    two_track_input = replace(planner_input, tracks=(second_track, first_track))
    second_decision = replace(snapshot.targets[0], key=TrackKey(2, 1))
    two_target_snapshot = replace(
        snapshot,
        targets=(second_decision, snapshot.targets[0]),
        directive=replace(snapshot.directive, required_targets=(TrackKey(2, 1), TrackKey(1, 1))),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(two_track_input, two_target_snapshot))
    reordered = MidMpcProblemAssembler().assemble(
        _request(replace(two_track_input, tracks=tuple(reversed(two_track_input.tracks))), two_target_snapshot)
    )

    assert isinstance(outcome, AssemblySuccess)
    assert isinstance(reordered, AssemblySuccess)
    assert outcome.selected_target_keys == (TrackKey(1, 1), TrackKey(2, 1))
    assert outcome.request_hash == reordered.request_hash
    assert outcome.problem_hash == reordered.problem_hash
    assert len(outcome.target_predictions) == 2
    assert outcome.target_predictions[0].times_s.shape == (81,)
    assert outcome.target_predictions[0].times_s[[0, -1]].tolist() == [0.0, 400.0]
    assert outcome.grid.control_intervals == 80
    assert outcome.grid.state_samples == 81
    assert outcome.grid.duration_s == 400.0
    assert outcome.horizon_encounter_plan.times_s.shape == (81,)
    assert outcome.horizon_encounter_plan.solver_consumed is True
    assert outcome.preparation.seed.source == "DETERMINISTIC_COLD_START"
    assert outcome.preparation.prefix.active_intervals == 0
    assert outcome.preparation.slack.cpa_bounds == (0.0, 0.0)
    assert outcome.preparation.slack.direction_bounds == (0.0, 0.0)
    assert outcome.preparation.formulation_id.endswith("ced58f8576f3772ef7c1bc72bb0f8b0368688b5a")
    assert outcome.request_hash
    assert _request(two_track_input, two_target_snapshot).capability.limitations == ("NO_LIVE_PLANT_OR_GNC_ENVELOPE",)


def test_request_hash_covers_ownship_dimensions_used_by_clearance_compilation() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    baseline = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))
    wider = MidMpcProblemAssembler().assemble(
        _request(replace(planner_input, ownship_width_m=planner_input.ownship_width_m + 2.0), snapshot)
    )

    assert isinstance(baseline, AssemblySuccess)
    assert isinstance(wider, AssemblySuccess)
    assert baseline.request_hash != wider.request_hash
    assert baseline.problem_hash != wider.problem_hash


def test_assembler_admits_active_committed_target_after_required_slots() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    eligible_only = replace(
        snapshot,
        directive=replace(snapshot.directive, required_targets=()),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, eligible_only))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.selected_target_keys == (TrackKey(1, 1),)
    assert tuple(window.key for window in outcome.horizon_encounter_plan.target_windows) == (TrackKey(1, 1),)


def test_assembler_graph_bakes_uncommitted_candidate_for_l4_all_track_safety() -> None:
    planner_input = _planner_input()
    snapshot = EncounterLifecycle().step(_cycle(planner_input, sequence=0, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))

    assert isinstance(outcome, AssemblySuccess)
    assert snapshot.targets[0].risk.value == "CANDIDATE"
    assert snapshot.directive.required_targets == ()
    assert outcome.selected_target_keys == (TrackKey(1, 1),)
    assert outcome.problem.lateral_active is False
    assert outcome.problem.prefix_active_k == 1
    assert outcome.problem.prefix_psi_rad == (planner_input.ownship_state[2],)
    activation = outcome.activation_plan.targets[0]
    assert outcome.activation_plan.global_cpa_hard_from_k == math.floor(activation.cpa_hard_from_s / outcome.grid.dt_s)
    assert outcome.problem.row_schedule.cpa_hard_windows[0].start_k == activation.cpa_hard_from_k
    assert outcome.problem.row_schedule.direction_hard_window is None


def test_assembler_compiles_full_horizon_stand_on_course_authority() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    stand_on_decision = replace(
        snapshot.targets[0],
        role=OwnshipRole.STAND_ON,
        risk=RiskPhase.ACTIVE,
        commitment=CommitmentPhase.NONE,
        passing_side=PassingSide.NONE,
        rule17=Rule17Stage.STAND_ON,
        baseline_course_rad=0.0,
        required_course_change_rad=0.0,
    )
    stand_on_snapshot = replace(
        snapshot,
        targets=(stand_on_decision,),
        directive=replace(
            snapshot.directive,
            required_targets=(),
            passing_side=PassingSide.NONE,
            minimum_course_change_rad=0.0,
        ),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, stand_on_snapshot))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.problem.heading_bounds_rad == pytest.approx((-math.radians(5.0), math.radians(5.0)))
    assert outcome.problem.prefix_active_k == 1
    assert outcome.problem.row_schedule.cpa_hard_from_k == 80
    assert outcome.problem.row_schedule.cpa_hard_windows[0].start_k == 80
    assert outcome.problem.row_schedule.cpa_hard_windows[0].stop_k == 80


def test_assembler_releases_safe_completed_target_from_optimizer_graph() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    released = replace(
        snapshot.targets[0],
        risk=RiskPhase.RELEASED,
        route_recovery_allowed=True,
        recovery_guard_active=False,
    )
    released_snapshot = replace(
        snapshot,
        targets=(released,),
        directive=replace(snapshot.directive, required_targets=()),
    )
    safe_input = replace(
        planner_input,
        tracks=(replace(planner_input.tracks[0], state_enu=np.array([1000.0, 1000.0, -7.0, 0.0])),),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(safe_input, released_snapshot))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.selected_target_keys == ()
    assert outcome.problem.targets == ()


def test_released_contact_remains_an_obstacle_for_a_reachable_terminal_stop() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    released = replace(
        snapshot.targets[0], risk=RiskPhase.RELEASED, route_recovery_allowed=True, recovery_guard_active=False
    )
    snapshot = replace(snapshot, targets=(released,), directive=replace(snapshot.directive, required_targets=()))
    data = replace(
        planner_input,
        tracks=(replace(planner_input.tracks[0], state_enu=np.array([-800.0, 0.0, 2.0, 0.0])),),
        ownship_state=np.array([0.0, 0.0, 0.0, 0.1, 0.0, 0.0]),
        waypoints_enu_m=np.array([[0.0, 100.0], [0.0, 0.0]]),
    )
    request = _request(data, snapshot)
    request = replace(request, route=replace(request.route, mission_waypoints_ne_m=((0.0, 0.0), (100.0, 0.0))))
    outcome = MidMpcProblemAssembler().assemble(request)
    assert isinstance(outcome, AssemblySuccess)
    assert outcome.selected_target_keys == (released.key,)
    assert outcome.problem.row_schedule.cpa_hard_windows[0].start_k < request.config.horizon_steps
    assert snapshot.targets[0].risk is RiskPhase.RELEASED


@pytest.mark.parametrize("risk", [RiskPhase.CLEAR, RiskPhase.RELEASED])
def test_assembler_retains_non_obligated_target_with_mission_route_reentry(risk: RiskPhase) -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    released = replace(
        snapshot.targets[0],
        risk=risk,
        route_recovery_allowed=True,
        recovery_guard_active=False,
    )
    released_snapshot = replace(
        snapshot,
        targets=(released,),
        directive=replace(snapshot.directive, required_targets=()),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, released_snapshot))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.selected_target_keys == (TrackKey(1, 1),)
    assert outcome.problem.row_schedule.cpa_hard_windows[0].start_k == 0


def test_assembler_compensates_frozen_timing_with_ownship_step_displacement() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))

    assert isinstance(outcome, AssemblySuccess)
    own_radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    target = planner_input.tracks[0]
    target_radius = 0.5 * math.hypot(target.length_m, target.width_m)
    expected = 50.0 + own_radius + target_radius + 8.0 * 5.0
    assert outcome.effective_cpa_hard_m == pytest.approx(expected)


def test_assembler_compiles_required_cpa_activation_from_physical_time() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.activation_plan.targets[0].key == TrackKey(1, 1)
    # Activation is the earlier of the linear TCPA staging and the knot where
    # a clearance violation becomes physically possible (P2 mid fix: a
    # maneuvering ownship can create the encounter before the current-velocity
    # TCPA; seam-01 head_on staged the hard window at k=51 while the candidate
    # closed to 42 m at k=34).
    assert outcome.activation_plan.targets[0].cpa_hard_from_s == pytest.approx(55.0)
    assert outcome.activation_plan.targets[0].cpa_hard_from_k == 11
    assert outcome.problem.row_schedule.cpa_hard_from_k == 11


def test_strict_assembler_compiles_finite_hard_windows_from_horizon_phases() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))

    assert isinstance(outcome, AssemblySuccess)
    schedule = outcome.problem.row_schedule
    target_window = outcome.horizon_encounter_plan.target_windows[0]
    # Hard CPA coverage is inclusive of the first recovery knot: the recovery
    # prediction was already breached exactly at its stop knot (overtaking-E0
    # witness at k=59), so the window keeps one knot of executed evidence.
    expected_stop = (
        outcome.grid.control_intervals
        if target_window.recovery_from_k is None
        else target_window.recovery_from_k + 1
    )
    expected_start = outcome.activation_plan.targets[0].cpa_hard_from_k
    assert tuple((window.start_k, window.stop_k) for window in schedule.cpa_hard_windows) == (
        (expected_start, min(expected_stop, outcome.grid.control_intervals)),
    )
    assert schedule.direction_hard_window is not None
    assert schedule.direction_hard_window.stop_k == outcome.grid.control_intervals
    assert schedule.min_alt_hard_window is not None
    # Heading-authority windows release at the recovery knot itself; only the
    # CPA clearance coverage gains the inclusive recovery knot.
    assert schedule.min_alt_hard_window.stop_k == (
        outcome.grid.control_intervals
        if target_window.recovery_from_k is None
        else target_window.recovery_from_k
    )


def test_strict_assembler_keeps_clear_bystander_inside_physical_safety_domain() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    active = snapshot.targets[0]
    bystander_key = TrackKey(3, 1)
    bystander_track = replace(
        planner_input.tracks[0],
        target_id=bystander_key.target_id,
        state_enu=np.array([1200.0, 500.0, -2.0, 0.0]),
    )
    bystander = replace(
        active,
        key=bystander_key,
        role=OwnshipRole.NONE,
        risk=RiskPhase.CLEAR,
        commitment=CommitmentPhase.NONE,
        passing_side=PassingSide.NONE,
        baseline_course_rad=None,
        required_course_change_rad=0.0,
        action_start_deadline_s=None,
        action_achievement_deadline_s=None,
    )
    multiship_input = replace(planner_input, tracks=(planner_input.tracks[0], bystander_track))
    multiship_snapshot = replace(snapshot, targets=(active, bystander))

    outcome = MidMpcProblemAssembler().assemble(_request(multiship_input, multiship_snapshot))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.selected_target_keys == (active.key, bystander_key)
    bystander_index = outcome.selected_target_keys.index(bystander_key)
    bystander_window = outcome.problem.row_schedule.cpa_hard_windows[bystander_index]
    bystander_activation = outcome.activation_plan.targets[bystander_index]
    assert bystander_window.start_k == bystander_activation.cpa_hard_from_k
    assert bystander_window.start_k < outcome.grid.control_intervals
    assert bystander_window.stop_k == outcome.grid.control_intervals


def test_unknown_active_safety_target_without_commitment_baseline_keeps_hold_policy() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    active = replace(
        snapshot.targets[0],
        encounter=EncounterKind.UNKNOWN,
        role=OwnshipRole.UNKNOWN,
        risk=RiskPhase.ACTIVE,
        commitment=CommitmentPhase.NONE,
        passing_side=PassingSide.NONE,
        baseline_course_rad=None,
        required_course_change_rad=0.0,
        route_recovery_allowed=False,
    )
    safety_only = replace(
        snapshot,
        targets=(active,),
        directive=replace(
            snapshot.directive,
            required_targets=(active.key,),
            passing_side=PassingSide.NONE,
            minimum_course_change_rad=0.0,
        ),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, safety_only))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.problem.route_objective is not None
    assert outcome.problem.route_objective.avoidance_corridor_bearing_rad == pytest.approx(planner_input.ownship_state[2])


def test_route_recovery_conflict_activates_cpa_rows_before_turning_back() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    recovery_target = replace(
        snapshot.targets[0],
        risk=RiskPhase.PAST_CLEAR,
        route_recovery_allowed=True,
        recovery_guard_active=True,
        action_achieved=True,
    )
    recovery_snapshot = replace(snapshot, targets=(recovery_target,))

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, recovery_snapshot))

    assert isinstance(outcome, AssemblySuccess)
    target_window = outcome.horizon_encounter_plan.target_windows[0]
    assert target_window.route_recovery_allowed_at_start is True
    assert target_window.minimum_predicted_route_dcpa_m < target_window.recovery_clearance_m
    assert outcome.problem.row_schedule.cpa_hard_windows[0].start_k == 0


def test_route_recovery_wait_holds_current_course_until_rejoin_is_safe() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    recovery_target = replace(
        snapshot.targets[0],
        risk=RiskPhase.PAST_CLEAR,
        route_recovery_allowed=True,
        recovery_guard_active=True,
        action_achieved=True,
    )
    recovery_snapshot = replace(snapshot, targets=(recovery_target,))
    current_heading = math.radians(30.0)
    off_route_input = replace(
        planner_input,
        ownship_state=np.array([0.0, 200.0, current_heading, 7.0, 0.0, 0.0]),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(off_route_input, recovery_snapshot))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.horizon_encounter_plan.recovery_from_k not in {None, 0}
    assert outcome.horizon_encounter_plan.phases[0] is HorizonEncounterPhase.PASS
    assert outcome.horizon_encounter_plan.avoidance_corridor_bearing_rad == pytest.approx(current_heading)


def test_rolling_plan_authority_does_not_alter_recovery_timing() -> None:
    """Rolling plans are continuity authority only: swept-path evidence owns recovery timing.

    The removed rolling-plan anchor deferred `recovery_from_k` to the accepted
    plan's `recovery_at_s`; each acceptance then re-published a deferral ~one
    corridor ahead, so recovery never approached (livelock) and could even be
    forced where the swept-path check found no safe recovery step.
    """
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    recovery_target = replace(
        snapshot.targets[0],
        risk=RiskPhase.PAST_CLEAR,
        route_recovery_allowed=True,
        recovery_guard_active=True,
        action_achieved=True,
    )
    recovery_snapshot = replace(snapshot, targets=(recovery_target,))
    request = _request(planner_input, recovery_snapshot)
    rolling_plan = RollingPlanReference(
        active=True,
        revision_reason=PlanRevisionReason.CONTINUITY_PRESERVED,
        accepted_at_s=0.0,
        current_time_s=planner_input.sim_time_s,
        recovery_at_s=15.0,
        heading_reference_rad=(0.0,) * request.config.horizon_steps,
        speed_reference_mps=(7.0,) * request.config.horizon_steps,
        objective_weight=(100.0,) * request.config.horizon_steps,
        overlap_intervals=request.config.horizon_steps,
    )

    with_rolling = MidMpcProblemAssembler().assemble(replace(request, rolling_plan=rolling_plan))
    without_rolling = MidMpcProblemAssembler().assemble(replace(request, rolling_plan=None))

    assert isinstance(with_rolling, AssemblySuccess)
    assert isinstance(without_rolling, AssemblySuccess)
    evidence_plan = without_rolling.horizon_encounter_plan
    continuity_plan = with_rolling.horizon_encounter_plan
    assert continuity_plan.recovery_from_k == evidence_plan.recovery_from_k
    assert continuity_plan.phases == evidence_plan.phases
    assert continuity_plan.target_windows == evidence_plan.target_windows


def test_recover_first_reference_anchors_first_step_on_own_heading() -> None:
    config = MidMpcAssemblyConfig()
    steps = config.horizon_steps
    current_heading = math.radians(30.0)
    mission = 0.0
    plan = HorizonEncounterPlan(
        reference_time_s=365.0,
        times_s=np.arange(steps + 1, dtype=float) * config.horizon_dt_s,
        mission_route_bearing_rad=mission,
        avoidance_corridor_bearing_rad=current_heading,
        phases=(HorizonEncounterPhase.RECOVER,) * (steps + 1),
        target_windows=(),
        recovery_from_k=0,
    )
    references, lateral = _staged_route_references(
        plan,
        RouteReference(
            anchor_ne_m=(0.0, 0.0),
            bearing_rad=mission,
            mission_leg_bearing_rad=mission,
            planned_speed_mps=7.0,
        ),
        ownship_position_ne_m=(0.0, 200.0),
        ownship_heading_rad=current_heading,
        planned_speed_mps=7.0,
        dt_s=config.horizon_dt_s,
        rot_max_rad_s=config.rot_max_rad_s,
        heading_window_rad=config.heading_window_rad,
    )

    max_step = config.rot_max_rad_s * config.horizon_dt_s
    # The first reference must sit strictly inside the rot envelope: anchoring
    # it exactly on the boundary makes the interior-point seed start on the
    # active constraint and IPOPT crawls the barrier for dozens of iterations.
    assert references[0] == pytest.approx(current_heading)
    assert references[1] != pytest.approx(current_heading)
    assert references[-1] == pytest.approx(mission, abs=0.05)
    ladder = np.abs(np.diff(np.r_[current_heading, np.array(references)]))
    assert float(np.max(ladder)) <= max_step + 1.0e-9
    assert len(lateral) == steps


def test_mission_reference_uses_future_waypoint_turn_inside_horizon() -> None:
    config = MidMpcAssemblyConfig()
    plan = HorizonEncounterPlan(
        reference_time_s=5.0,
        times_s=np.arange(config.horizon_steps + 1, dtype=float) * config.horizon_dt_s,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=0.0,
        phases=(HorizonEncounterPhase.MISSION,) * (config.horizon_steps + 1),
        target_windows=(),
        recovery_from_k=0,
    )
    route = RouteReference(
        anchor_ne_m=(0.0, 0.0),
        bearing_rad=0.0,
        mission_leg_bearing_rad=0.0,
        planned_speed_mps=5.0,
        mission_waypoints_ne_m=((0.0, 0.0), (100.0, 0.0), (100.0, 500.0)),
    )

    references, _ = _staged_route_references(
        plan,
        route,
        ownship_position_ne_m=(0.0, 0.0),
        ownship_heading_rad=0.0,
        planned_speed_mps=5.0,
        dt_s=config.horizon_dt_s,
        rot_max_rad_s=config.rot_max_rad_s,
        heading_window_rad=config.heading_window_rad,
    )

    assert max(references[:10]) > math.radians(45.0)
    assert references[-1] == pytest.approx(math.pi / 2, abs=0.05)


def test_avoidance_corridor_delays_but_does_not_erase_future_waypoint_turn() -> None:
    config = MidMpcAssemblyConfig()
    recover_from_k = 15
    plan = HorizonEncounterPlan(
        reference_time_s=5.0,
        times_s=np.arange(config.horizon_steps + 1, dtype=float) * config.horizon_dt_s,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=0.0,
        phases=(HorizonEncounterPhase.PASS,) * recover_from_k
        + (HorizonEncounterPhase.RECOVER,) * (config.horizon_steps + 1 - recover_from_k),
        target_windows=(),
        recovery_from_k=recover_from_k,
    )
    route = RouteReference(
        anchor_ne_m=(0.0, 0.0),
        bearing_rad=0.0,
        mission_leg_bearing_rad=0.0,
        planned_speed_mps=5.0,
        mission_waypoints_ne_m=((0.0, 0.0), (100.0, 0.0), (100.0, 500.0)),
    )

    references, _ = _staged_route_references(
        plan,
        route,
        ownship_position_ne_m=(0.0, 0.0),
        ownship_heading_rad=0.0,
        planned_speed_mps=5.0,
        dt_s=config.horizon_dt_s,
        rot_max_rad_s=config.rot_max_rad_s,
        heading_window_rad=config.heading_window_rad,
    )

    assert references[:recover_from_k] == pytest.approx((0.0,) * recover_from_k)
    assert max(references[recover_from_k:]) > math.radians(45.0)
    assert references[-1] == pytest.approx(math.pi / 2, abs=0.05)


def test_structural_signature_stays_fixed_when_only_row_bounds_change() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    near = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))
    far_input = replace(
        planner_input,
        tracks=(replace(planner_input.tracks[0], state_enu=np.array([1000.0, 5000.0, -7.0, 0.0])),),
    )
    far = MidMpcProblemAssembler().assemble(_request(far_input, snapshot))

    assert isinstance(near, AssemblySuccess)
    assert isinstance(far, AssemblySuccess)
    assert near.problem.row_schedule != far.problem.row_schedule
    assert near.preparation.structural_signature == far.preparation.structural_signature


def test_missing_required_target_returns_typed_binding_failure() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(_request(replace(planner_input, tracks=()), snapshot))

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.TARGET_BINDING_MISSING
    assert outcome.problem is None


def test_missing_required_decision_returns_typed_binding_failure() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, replace(snapshot, targets=())))

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.TARGET_BINDING_MISSING
    assert outcome.problem is None


def test_activation_uses_resolved_capability_not_config_default() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    request = _request(planner_input, snapshot)
    request = replace(
        request,
        capability=replace(request.capability, rot_max_rad_s=math.radians(0.5)),
    )

    outcome = MidMpcProblemAssembler().assemble(request)

    assert isinstance(outcome, AssemblySuccess)
    expected_k = math.ceil(snapshot.directive.minimum_course_change_rad / (math.radians(0.5) * 5.0)) - 1
    assert outcome.problem.row_schedule.min_alt_hard_from_k == expected_k
    assert outcome.problem.rot_max_rad_s == math.radians(0.5)


def test_assembler_fails_closed_before_silently_truncating_seventeen_required_targets() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    overloaded = replace(
        snapshot,
        directive=replace(
            snapshot.directive,
            required_targets=tuple(TrackKey(target_id, 1) for target_id in range(1, 18)),
        ),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, overloaded))

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.CAPACITY_EXCEEDED
    assert outcome.problem is None


def test_assembler_binds_exactly_sixteen_required_targets_without_truncation() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    source_track = planner_input.tracks[0]
    source_decision = snapshot.targets[0]
    keys = tuple(TrackKey(target_id, 1) for target_id in range(1, 17))
    tracks = tuple(
        replace(
            source_track,
            target_id=key.target_id,
            state_enu=np.array([1000.0 + 10.0 * key.target_id, 0.0, -7.0, 0.0]),
        )
        for key in keys
    )
    decisions = tuple(replace(source_decision, key=key) for key in keys)
    request = _request(
        replace(planner_input, tracks=tracks),
        replace(
            snapshot,
            targets=decisions,
            directive=replace(snapshot.directive, required_targets=keys),
        ),
    )

    outcome = MidMpcProblemAssembler().assemble(request)

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.selected_target_keys == keys
    assert len(outcome.problem.targets) == 16
    assert len(outcome.target_predictions) == 16


def test_assembler_fails_when_lifecycle_speed_directive_exceeds_capability() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    incompatible = replace(
        snapshot,
        directive=replace(snapshot.directive, speed_bounds_mps=(9.0, 10.0)),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, incompatible))

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.CORE_CAPABILITY_MISMATCH
    assert outcome.problem is None


def test_assembler_maps_persistent_lifecycle_commitment_without_business_state() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    assembly = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))

    assert isinstance(assembly, AssemblySuccess)
    assert len(assembly.problem.targets) == 1
    assert assembly.problem.lateral_active is True
    assert assembly.problem.preferred_side == 1
    assert assembly.problem.min_alteration_rad == snapshot.targets[0].required_course_change_rad
    assert assembly.problem.row_schedule.direction_hard_from_k == 0
    assert assembly.problem.speed_bounds_mps == snapshot.directive.speed_bounds_mps
    assert assembly.selected_target_keys == (TrackKey(1, 1),)
    target_radius = 0.5 * math.hypot(planner_input.tracks[0].length_m, planner_input.tracks[0].width_m)
    own_radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    assert assembly.horizon_encounter_plan.target_windows[0].recovery_clearance_m == pytest.approx(
        150.0 + own_radius + target_radius
    )


def test_assembler_retains_committed_corridor_after_first_alteration_is_achieved() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    committed = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    required_change = committed.targets[0].required_course_change_rad
    achieved_cycle = _cycle(planner_input, sequence=2, sim_time_s=10.0)
    achieved_cycle = replace(
        achieved_cycle,
        ownship=replace(
            achieved_cycle.ownship,
            velocity_ne_mps=np.array([7.0 * math.cos(required_change), 7.0 * math.sin(required_change)]),
            heading_rad=required_change,
        ),
    )
    snapshot = lifecycle.step(achieved_cycle)

    assembly = MidMpcProblemAssembler().assemble(_request(replace(planner_input, sim_time_s=10.0), snapshot))

    assert isinstance(assembly, AssemblySuccess)
    assert snapshot.targets[0].action_achieved is True
    assert assembly.problem.lateral_active is False
    assert assembly.problem.route_bearing_rad == required_change
    assert assembly.horizon_encounter_plan.mission_route_bearing_rad == 0.0
    assert assembly.horizon_encounter_plan.avoidance_corridor_bearing_rad == required_change
    assert assembly.horizon_encounter_plan.solver_consumed is True
    assert assembly.horizon_encounter_plan.phases[0] is HorizonEncounterPhase.PASS
    assert HorizonEncounterPhase.RECOVER in assembly.horizon_encounter_plan.phases
    assert assembly.problem.route_objective is not None
    assert assembly.problem.route_objective.mission_bearing_rad == 0.0
    assert assembly.problem.route_objective.avoidance_corridor_bearing_rad == required_change
    assert assembly.problem.route_objective.avoidance_active_until_k == assembly.horizon_encounter_plan.phases.index(
        HorizonEncounterPhase.RECOVER
    )
    recovery_k = assembly.problem.route_objective.avoidance_active_until_k
    assert assembly.problem.route_objective.heading_reference_rad[recovery_k - 1] == pytest.approx(required_change)
    assert assembly.problem.route_objective.heading_reference_rad[recovery_k] != pytest.approx(required_change)
    assert assembly.problem.route_objective.heading_reference_rad[-1] == 0.0
    assert min(assembly.problem.route_objective.heading_reference_rad) >= assembly.problem.heading_bounds_rad[0]
    assert max(assembly.problem.route_objective.heading_reference_rad) <= assembly.problem.heading_bounds_rad[1]
    lateral_reference = assembly.problem.route_objective.lateral_reference_m
    assert max(abs(value) for value in lateral_reference) > 1.0
    assert abs(lateral_reference[-1]) < max(abs(value) for value in lateral_reference)
    assert assembly.problem.route_frame.bearing_rad == 0.0


def test_mass_parity_keeps_frozen_problem_while_horizon_plan_remains_advisory() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    strict_request = _request(planner_input, snapshot)

    strict = MidMpcProblemAssembler().assemble(strict_request)
    parity = MidMpcProblemAssembler().assemble(replace(strict_request, profile=AssemblyProfile.MASS_PARITY))

    assert isinstance(strict, AssemblySuccess)
    assert isinstance(parity, AssemblySuccess)
    assert strict.problem.route_objective is not None
    assert parity.problem.route_objective is None
    assert parity.problem.route_frame.bearing_rad == parity.problem.route_bearing_rad
    assert strict.horizon_encounter_plan.solver_consumed is True
    assert parity.horizon_encounter_plan.solver_consumed is False
    assert parity.horizon_encounter_plan.phases == strict.horizon_encounter_plan.phases
    assert parity.preparation.slack.cpa_bounds == (0.0, None)


def test_assembler_rejects_direction_facts_the_frozen_core_cannot_represent() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    inconsistent = replace(
        snapshot,
        directive=replace(snapshot.directive, passing_side=PassingSide.NONE),
    )

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, inconsistent))

    assert isinstance(outcome, AssemblyFailure)
    assert outcome.code is AssemblyFailureCode.CORE_CAPABILITY_MISMATCH


def test_assembler_maps_stop_directive_to_zero_speed_reference() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    stopped = replace(
        snapshot,
        directive=replace(
            snapshot.directive,
            passing_side=PassingSide.NONE,
            minimum_course_change_rad=0.0,
            speed_bounds_mps=(0.0, 7.0),
            stop_required=True,
        ),
    )

    assembly = MidMpcProblemAssembler().assemble(_request(planner_input, stopped))

    assert isinstance(assembly, AssemblySuccess)
    assert assembly.problem.planned_speed_mps == 0.0
    assert assembly.problem.speed_bounds_mps == (0.0, 7.0)
    assert assembly.problem.lateral_active is False


def _planner_input() -> PlannerInput:
    return PlannerInput(
        sim_time_s=5.0,
        dt_sim_s=0.5,
        waypoints_enu_m=np.array([[0.0, 5000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([7.0, 7.0]),
        ownship_state=np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]),
        tracks=(
            TrackedObstacle(
                target_id=1,
                state_enu=np.array([1000.0, 0.0, -7.0, 0.0]),
                covariance=np.zeros((4, 4)),
                length_m=30.0,
                width_m=7.0,
                observed_at_s=5.0,
                age_s=0.0,
                generation=1,
                status="updated",
                source="god",
                generated_at_s=5.0,
            ),
        ),
        enc=None,
        goal_state=None,
        disturbance=None,
        algorithm_seed=0,
        ownship_length_m=15.0,
        ownship_width_m=4.0,
    )


def _cycle(planner_input: PlannerInput, *, sequence: int, sim_time_s: float) -> EncounterCycle:
    track = planner_input.tracks[0]
    return EncounterCycle(
        epoch="test",
        sequence=sequence,
        sim_time_s=sim_time_s,
        ownship=OwnshipObservation(
            position_ne_m=planner_input.ownship_state[:2],
            velocity_ne_mps=np.array([7.0, 0.0]),
            heading_rad=0.0,
            length_m=15.0,
            width_m=4.0,
            maneuverability=Maneuverability(math.radians(3.0), 0.3, (0.0, 8.0)),
        ),
        targets=(
            TargetObservation(
                key=TrackKey(1, 1),
                state_enu=track.state_enu,
                covariance=track.covariance,
                length_m=track.length_m,
                width_m=track.width_m,
                observed_at_s=sim_time_s,
                generated_at_s=sim_time_s,
                health=ObservationHealth.UPDATED,
                source="god",
            ),
        ),
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        profile=PlannerOddProfile(),
    )


def _request(planner_input: PlannerInput, snapshot: DecisionSnapshot) -> AssemblyRequest:
    config = MidMpcAssemblyConfig()
    return AssemblyRequest(
        planner_input=planner_input,
        snapshot=snapshot,
        cycle_input_hash=snapshot.input_hash,
        lifecycle_profile_hash=snapshot.profile_hash,
        route=RouteReference(
            anchor_ne_m=(0.0, 0.0),
            bearing_rad=0.0,
            mission_leg_bearing_rad=0.0,
            planned_speed_mps=7.0,
        ),
        capability=CapabilitySnapshot(
            heading_window_rad=config.heading_window_rad,
            speed_bounds_mps=config.speed_bounds_mps,
            rot_max_rad_s=config.rot_max_rad_s,
            decel_max_mps2=config.decel_max_mps2,
        ),
        config=config,
        profile=AssemblyProfile.COLAV_STRICT,
    )


def test_polyline_horizon_allows_reachable_next_leg_heading() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    snapshot = replace(
        snapshot,
        targets=(),
        directive=replace(
            snapshot.directive, required_targets=(), passing_side=PassingSide.NONE, minimum_course_change_rad=0.0
        ),
    )
    planner_input = replace(planner_input, tracks=(), ownship_state=np.array([150.0, 300.0, 1.5 * math.pi, 7.0, 0.0, 0.0]))
    request = replace(
        _request(planner_input, snapshot),
        route=RouteReference(
            anchor_ne_m=(0.0, 300.0),
            bearing_rad=1.5 * math.pi,
            mission_leg_bearing_rad=-math.pi / 2,
            planned_speed_mps=7.0,
            mission_waypoints_ne_m=((0.0, 1000.0), (0.0, 0.0), (3000.0, 0.0)),
        ),
    )
    outcome = MidMpcProblemAssembler().assemble(request)
    assert isinstance(outcome, AssemblySuccess)
    references = outcome.problem.route_objective.heading_reference_rad
    assert abs(math.atan2(math.sin(references[-1]), math.cos(references[-1]))) < 0.01
    assert references[0] >= planner_input.ownship_state[2]
    assert max(references) <= outcome.problem.heading_bounds_rad[1] + 1e-9
    assert min(references) >= outcome.problem.heading_bounds_rad[0] - 1e-9


def test_active_target_safety_stays_enabled_when_current_motion_has_no_cpa() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    # The encounter duty persists after turning away; future course changes can
    # still approach the contact even though current-motion CPA is outside range.
    planner_input = replace(planner_input, ownship_state=np.array([0.0, 0.0, np.pi, 7.0, 0.0, 0.0]))
    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))
    assert isinstance(outcome, AssemblySuccess)
    assert outcome.activation_plan.targets[0].cpa_hard_from_k < outcome.grid.control_intervals


def _head_on_plan_with_recovery(monkeypatch, recovery_from_k: int | None) -> tuple[AssemblyRequest, object]:
    """Assemble the default head-on fixture under a pinned horizon plan."""
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))
    request = _request(planner_input, snapshot)
    n = request.config.horizon_steps
    plan = HorizonEncounterPlan(
        reference_time_s=5.0,
        times_s=np.arange(n + 1) * request.config.horizon_dt_s,
        mission_route_bearing_rad=0.0,
        avoidance_corridor_bearing_rad=0.0,
        phases=(HorizonEncounterPhase.PASS,) * (n + 1),
        recovery_from_k=recovery_from_k,
        target_windows=(
            TargetHorizonWindow(
                TrackKey(1, 1),
                n - 1,
                recovery_from_k,
                False,
                200.0,
                0.0,
            ),
        ),
        corridor_reference_rad=(),
    )
    monkeypatch.setattr(
        "colav_simulator.core.colav.mid_mpc_assembler._compile_horizon_encounter_plan", lambda *args, **kwargs: plan
    )
    return request, MidMpcProblemAssembler().assemble(request)


def test_cpa_hard_window_starts_when_a_violation_becomes_physically_possible(monkeypatch) -> None:
    """Cover the maneuver-controllable encounter with the hard CPA window.

    Not only the current-velocity TCPA (head_on seam-01: staged at k=51 while
    the accepted candidate closed to 42 m at k=34).
    """
    request, outcome = _head_on_plan_with_recovery(monkeypatch, recovery_from_k=None)

    assert isinstance(outcome, AssemblySuccess)
    windows = outcome.problem.row_schedule.cpa_hard_windows
    assert len(windows) == 1
    target = request.planner_input.tracks[0]
    closing_radps = 7.0 + 7.0
    effective_hard = outcome.problem.cpa_hard_m
    gap = float(np.linalg.norm(target.state_enu[:2])) - effective_hard
    violation_possible_s = gap / closing_radps
    assert windows[0].start_k <= math.ceil(violation_possible_s / request.config.horizon_dt_s)
    assert windows[0].start_k < windows[0].stop_k


def test_inverted_cpa_window_falls_back_to_hard_until_horizon(monkeypatch) -> None:
    """Never emit an empty window from an inverted recovery prediction.

    A recovery prediction earlier than the activation staging must not produce
    an empty (start_k == stop_k) window: safety must not evaporate in the
    disagreement; rows beyond true clearance stay trivially satisfied.
    """
    request, outcome = _head_on_plan_with_recovery(monkeypatch, recovery_from_k=1)

    assert isinstance(outcome, AssemblySuccess)
    windows = outcome.problem.row_schedule.cpa_hard_windows
    assert len(windows) == 1
    n = request.config.horizon_steps
    assert windows[0].start_k < windows[0].stop_k, "empty hard window would leave the encounter unconstrained"
    assert windows[0].stop_k == n


def test_hard_cpa_window_covers_the_first_recovery_knot(monkeypatch) -> None:
    """The recovery prediction was breached exactly at its stop knot (OT-E0).

    Hard CPA coverage must include the first recovery knot: the exclusive
    window released the clearance row one knot before the executed closest
    approach and the candidate rode the gap to a negative hull clearance.
    Hard coverage may only grow, so this is +1 over the predicted stop.
    """
    request, outcome = _head_on_plan_with_recovery(monkeypatch, recovery_from_k=30)

    assert isinstance(outcome, AssemblySuccess)
    windows = outcome.problem.row_schedule.cpa_hard_windows
    assert len(windows) == 1
    assert windows[0].start_k < 30
    assert windows[0].stop_k == 31


def test_degenerate_recovery_prediction_keeps_full_horizon_fallback(monkeypatch) -> None:
    """A recovery prediction at or before activation keeps the hard fallback.

    The inclusive stop must not weaken the seam-01 guard: when the recovery
    prediction precedes the activation knot the prediction is nonsense and
    the window stays hard until the horizon end.
    """
    request, outcome = _head_on_plan_with_recovery(monkeypatch, recovery_from_k=11)

    assert isinstance(outcome, AssemblySuccess)
    activation_start = outcome.activation_plan.targets[0].cpa_hard_from_k
    windows = outcome.problem.row_schedule.cpa_hard_windows
    assert activation_start == 11
    assert len(windows) == 1
    assert windows[0].stop_k == request.config.horizon_steps


def test_scheduled_corridor_reentry_clamp_is_symmetric_across_sides() -> None:
    """Port and starboard re-entry share one rate-aware construction.

    The multiship seam NLP went Infeasible_Problem_Detected because the
    corridor re-entry clamp was rate-aware on the starboard side only; the
    mirrored port corridor demanded a heading the rot envelope did not allow
    while the measured heading sat outside the corridor.
    """
    own_psi = 0.0
    step = 0.05 * 5.0
    for side, bound_tightens in ((1, min), (-1, max)):
        corridor = side * 0.7  # unreachable inside one rot step from psi=0
        thresholds = [
            _scheduled_corridor_threshold(
                own_psi_rad=own_psi,
                corridor_bearing_rad=corridor,
                passing_side=side,
                required_course_change_rad=0.05,
                action_complete_k=1,
                knot=k,
                prefix_hold_k=0,
                rot_max_rad_s=0.05,
                horizon_dt_s=5.0,
            )
            for k in range(4)
        ]
        # Rate-limited return: never demand more than the envelope allows.
        assert thresholds[0] == pytest.approx(side * step)
        assert thresholds[1] == pytest.approx(side * 2.0 * step)
        # The original hard corridor remains once it is reachable.
        assert thresholds[2] == pytest.approx(corridor)
        assert thresholds[3] == pytest.approx(corridor)
        # Mirror symmetry across sides.
        mirrored = [
            _scheduled_corridor_threshold(
                own_psi_rad=own_psi,
                corridor_bearing_rad=-corridor,
                passing_side=-side,
                required_course_change_rad=0.05,
                action_complete_k=1,
                knot=k,
                prefix_hold_k=0,
                rot_max_rad_s=0.05,
                horizon_dt_s=5.0,
            )
            for k in range(4)
        ]
        assert mirrored == [-value for value in thresholds]


def test_prefix_hold_keeps_first_knot_rotation_budget_at_zero() -> None:
    """A prefix hold pins knot 0 on the measured heading: zero rotation budget.

    With hold_first_interval the first knot is fixed on the measured heading,
    so a corridor bound at knot 0 must admit it on both sides; the previous
    (k + 1) envelope allowed one full step at knot 0 and made the pinned NLP
    infeasible whenever the corridor sat further than zero rotation away.
    """
    own_psi = 0.3
    for side in (1, -1):
        threshold = _scheduled_corridor_threshold(
            own_psi_rad=own_psi,
            corridor_bearing_rad=own_psi + side * 0.7,
            passing_side=side,
            required_course_change_rad=0.05,
            action_complete_k=1,
            knot=0,
            prefix_hold_k=1,
            rot_max_rad_s=0.05,
            horizon_dt_s=5.0,
        )
        assert threshold == pytest.approx(own_psi)
        first_free = _scheduled_corridor_threshold(
            own_psi_rad=own_psi,
            corridor_bearing_rad=own_psi + side * 0.7,
            passing_side=side,
            required_course_change_rad=0.05,
            action_complete_k=1,
            knot=1,
            prefix_hold_k=1,
            rot_max_rad_s=0.05,
            horizon_dt_s=5.0,
        )
        assert first_free == pytest.approx(own_psi + side * 0.05 * 5.0)
