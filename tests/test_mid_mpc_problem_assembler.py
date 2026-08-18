import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput, TrackedObstacle
from colav_simulator.core.colav.encounter_lifecycle import (
    CommitmentPhase,
    DecisionSnapshot,
    EncounterCycle,
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
from colav_simulator.core.colav.horizon_encounter_plan import HorizonEncounterPhase
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
)
from colav_simulator.core.colav.rolling_plan import PlanRevisionReason, RollingPlanReference
from colav_simulator.core.tracking.trackers import TrackKey


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
    assert outcome.activation_plan.targets[0].cpa_hard_from_s == pytest.approx(61.4285714286)
    assert outcome.activation_plan.targets[0].cpa_hard_from_k == 12
    assert outcome.problem.row_schedule.cpa_hard_from_k == 12


def test_strict_assembler_compiles_finite_hard_windows_from_horizon_phases() -> None:
    planner_input = _planner_input()
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(planner_input, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(planner_input, sequence=1, sim_time_s=5.0))

    outcome = MidMpcProblemAssembler().assemble(_request(planner_input, snapshot))

    assert isinstance(outcome, AssemblySuccess)
    schedule = outcome.problem.row_schedule
    target_window = outcome.horizon_encounter_plan.target_windows[0]
    expected_stop = (
        outcome.grid.control_intervals if target_window.recovery_from_k is None else target_window.recovery_from_k
    )
    expected_start = outcome.activation_plan.targets[0].cpa_hard_from_k
    assert tuple((window.start_k, window.stop_k) for window in schedule.cpa_hard_windows) == (
        (expected_start, max(expected_start, expected_stop)),
    )
    assert schedule.direction_hard_window is not None
    assert schedule.direction_hard_window.stop_k == outcome.grid.control_intervals
    assert schedule.min_alt_hard_window is not None
    assert schedule.min_alt_hard_window.stop_k == expected_stop


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


def test_recovery_window_keeps_accepted_absolute_rolling_plan_time() -> None:
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

    outcome = MidMpcProblemAssembler().assemble(replace(request, rolling_plan=rolling_plan))

    assert isinstance(outcome, AssemblySuccess)
    assert outcome.horizon_encounter_plan.recovery_from_k == 2
    assert all(window.recovery_from_k == 2 for window in outcome.horizon_encounter_plan.target_windows)


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
