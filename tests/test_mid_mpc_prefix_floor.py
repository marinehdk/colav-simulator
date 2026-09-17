"""Retained-prefix direction floor and pinned-geometry CPA guard."""

import hashlib
import json
import math
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from test_mid_mpc_problem_assembler import _cycle, _planner_input, _request

from colav_simulator.core.colav.encounter_lifecycle import DecisionSnapshot, EncounterLifecycle
from colav_simulator.core.colav.horizon_encounter_plan import TargetPrediction
from colav_simulator.core.colav.mid_mpc.models import (
    MidMpcConfig,
    MidMpcHardWindow,
    MidMpcOwnShip,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRouteObjective,
    MidMpcRowSchedule,
    MidMpcStatus,
    MidMpcTarget,
)
from colav_simulator.core.colav.mid_mpc.solver import MidMpcIpoptSolver, _row_bounds, _row_layout
from colav_simulator.core.colav.mid_mpc_arrival import navigation_capture_error
from colav_simulator.core.colav.mid_mpc_assembler import (
    AssemblyFailure,
    AssemblySuccess,
    CapabilitySnapshot,
    MidMpcAssemblyConfig,
    MidMpcProblemAssembler,
    _discard_contract_conflicting_prefix,
    _discard_cpa_conflicting_prefix,
    _discard_stub_prefix,
    _is_discard_stub,
)
from colav_simulator.core.colav.retained_route import (
    RetainedPrefixPlan,
    RetainedRouteConstraint,
    _convergence_speeds,
    compile_execution_route,
    compile_spliced_execution_route,
    degraded_stub_prefix,
)
from colav_simulator.core.tracking.trackers import TrackKey
from colav_simulator.integrations.mid_mpc_ipopt import _published_execution_route


def _prefix_floor_problem() -> MidMpcProblem:
    """A pinned prefix committed deep on the disfavored side of the route line.

    Two rate-feasible beats join the measured heading, then 38 beats at
    -30 deg dive the lateral to -665 m, and a rate-feasible ramp ends the
    prefix climbing at +15 deg. With the direction rows anchored to the
    current offset (0 m) the free suffix cannot climb back inside the
    horizon even at the heading cap; anchored to the prefix profile minimum
    it is feasible at every knot.
    """
    join = (0.0, math.radians(-15.0))
    ramp = (math.radians(-17.5), math.radians(-5.0), math.radians(5.0), math.radians(15.0))
    prefix_psi = join + (math.radians(-30.0),) * 38 + ramp
    return MidMpcProblem(
        own_ship=MidMpcOwnShip(psi_rad=0.0, u_mps=7.0),
        route_bearing_rad=0.0,
        planned_speed_mps=7.0,
        heading_bounds_rad=(math.radians(-45.0), math.radians(20.0)),
        speed_bounds_mps=(0.0, 8.0),
        cpa_safe_m=150.0,
        cpa_hard_m=100.0,
        rot_max_rad_s=math.radians(3.0),
        decel_max_mps2=0.08,
        lateral_active=True,
        preferred_side=1,
        starboard_asymmetry_active=False,
        min_alteration_rad=0.0,
        route_frame=MidMpcRouteFrame((0.0, 0.0), (0.0, 1.0), 0.0, 1000.0, 1.0),
        route_objective=MidMpcRouteObjective(
            mission_bearing_rad=0.0,
            avoidance_corridor_bearing_rad=0.0,
            heading_reference_rad=(0.0,) * 80,
            lateral_reference_m=(0.0,) * 80,
            avoidance_active_until_k=0,
        ),
        row_schedule=MidMpcRowSchedule(
            prefix_softening=True,
            cpa_hard_windows=(MidMpcHardWindow(0, 80),),
            direction_hard_window=MidMpcHardWindow(0, 80),
            min_alt_hard_window=MidMpcHardWindow(0, 80),
        ),
        prefix_active_k=len(prefix_psi),
        prefix_psi_rad=prefix_psi,
        prefix_u_mps=(7.0,) * len(prefix_psi),
        targets=(MidMpcTarget(x_m=1.0e6, y_m=1.0e6, cog_rad=0.0, sog_mps=0.0),),
    )


def test_solver_accepts_pinned_prefix_deeper_than_the_direction_anchor():
    config = MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)
    result = MidMpcIpoptSolver(config).solve(_prefix_floor_problem())
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.max_constraint_violation < 1e-3
    assert result.accepted_by_quality_gate


def test_direction_floor_ratchets_to_the_committed_prefix_profile():
    config = MidMpcConfig(horizon_steps=80, strict_slack_bounds=True)
    prefix_psi = (math.radians(-30.0),) * 6
    problem = replace(
        _prefix_floor_problem(),
        prefix_active_k=6,
        prefix_psi_rad=prefix_psi,
        prefix_u_mps=(7.0,) * 6,
    )
    layout = _row_layout(config, 1, 0)
    lbg, _, _ = _row_bounds(config, problem, layout)
    span = layout.direction
    expected = 0.0
    cy = 0.0
    for course in prefix_psi:
        expected = min(expected, cy)
        cy += 7.0 * config.dt_s * math.sin(course)
    assert expected == pytest.approx(-87.5, abs=1e-9)
    # With prefix_softening the pinned beats are vacuous-open and the ratchet
    # floor holds exactly on every row the hard window leaves finite.
    np.testing.assert_array_equal(lbg[span.start : span.start + 6], np.full(6, -np.inf))
    np.testing.assert_array_equal(lbg[span.start + 6 : span.start + span.count], np.full(span.count - 6, expected))


def test_direction_floor_ignores_absent_prefix():
    config = MidMpcConfig(horizon_steps=80, strict_slack_bounds=True)
    problem = replace(
        _prefix_floor_problem(),
        own_ship=MidMpcOwnShip(psi_rad=0.0, u_mps=7.0, x_m=0.0, y_m=-100.0),
        prefix_active_k=0,
        prefix_psi_rad=(),
        prefix_u_mps=(),
    )
    lbg, _, _ = _row_bounds(config, problem, _row_layout(config, 1, 0))
    span = _row_layout(config, 1, 0).direction
    np.testing.assert_array_equal(lbg[span.start : span.start + span.count], np.full(span.count, -100.0))


def _retained_assembly(
    state_enu: np.ndarray,
    points: tuple[tuple[float, float], ...] = ((0.0, 0.0), (5000.0, 0.0)),
    *,
    steps: int = 2,
) -> AssemblySuccess:
    original = _planner_input()
    own = replace(
        original,
        tracks=(replace(original.tracks[0], state_enu=state_enu),),
        execution_route_constraint=RetainedRouteConstraint(
            "accepted", points, (7.0,) * len(points), ("cruise",) * len(points), 160.0, 32.0, 480.0
        ),
    )
    lifecycle = EncounterLifecycle()
    snapshot = None
    for sequence, sim_time_s in enumerate((0.0, 5.0)[-steps:]):
        snapshot = lifecycle.step(_cycle(own, sequence=sequence, sim_time_s=sim_time_s))
    assembled = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(assembled, AssemblySuccess)
    return assembled


def test_assembler_discards_retained_prefix_when_pinned_geometry_violates_cpa():
    assembled = _retained_assembly(np.array([300.0, 0.0, -7.0, 0.0]))
    stub = assembled.execution_prefix
    assert stub is not None and _is_discard_stub(stub)
    assert assembled.problem.prefix_active_k == 0
    # The retained corridor stays: it caps the optimized recovery arc inside
    # the GNC admission envelope on the discard beat too.
    assert assembled.problem.route_constraint_limit_m == 480.0
    assert len(assembled.problem.route_constraint_points_m) >= 2
    # A safety discard leaves the row schedule untouched: the immediate
    # locked-side recovery staging is reserved for contract discards.
    assert assembled.problem.row_schedule.course_bounds_rad == ()
    # Discarding unsafe geometry preserves the confirmed alteration duty.
    window = assembled.problem.row_schedule.min_alt_hard_window
    assert window is not None
    assert window.start_k == assembled.problem.row_schedule.min_alt_hard_from_k
    assert window.stop_k > window.start_k


def test_assembler_degrades_unreachable_retained_compile_to_stub():
    # v10: GNC schedules (terminal slowdown, turn pre-brake, stop window)
    # pin the mirror at or past the motion envelope in unknown phases. An
    # unreachable retained compile is a schedule effect, not a contract
    # error: the beat degrades to the discard-stub exit — free re-solve plus
    # spliced publication — instead of failing the session as INVALID_INPUT.
    original = _planner_input()
    own = replace(
        original,
        ownship_state=np.array([35.0, 2.0, 0.0, 2.0, 0.0, 0.0]),
        execution_route_constraint=RetainedRouteConstraint(
            "accepted",
            ((0.0, 0.0), (250.0, 0.0), (5000.0, 0.0)),
            (0.0, 0.0, 0.0),
            ("cruise",) * 3,
            160.0,
            32.0,
            480.0,
            execution_speed_mps=(0.0,) * 3,
        ),
    )
    lifecycle = EncounterLifecycle()
    snapshot = None
    for sequence, sim_time_s in enumerate((0.0, 5.0)):
        snapshot = lifecycle.step(_cycle(own, sequence=sequence, sim_time_s=sim_time_s))
    assembled = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(assembled, AssemblySuccess)
    stub = assembled.execution_prefix
    assert stub is not None and _is_discard_stub(stub)
    assert assembled.problem.prefix_active_k == 0
    # The witness is observable, not silent: the degraded beat records the
    # unreachable reason for the replay artifact.
    assert assembled.retained_degraded is not None and "unreachable" in assembled.retained_degraded
    # The retained corridor survives as the admission substrate, anchored at
    # the measured position.
    assert stub.points_ne_m == ((35.0, 2.0),)
    assert stub.navigation_modes == ("avoidance",)
    assert len(stub.corridor_points_m) >= 2


def test_assembler_still_surfaces_true_retained_contract_errors(monkeypatch):
    # Only the unreachable family degrades. A contract/data error from the
    # retained compile (misconfigured envelope) keeps failing loudly instead
    # of degrading into a stub that would silently hide the bug.
    def broken_compile(*args, **kwargs):
        raise ValueError("Retained-route minimum speed must lie within the vessel envelope")

    monkeypatch.setattr("colav_simulator.core.colav.mid_mpc_assembler.compile_retained_prefix", broken_compile)
    original = _planner_input()
    own = replace(
        original,
        execution_route_constraint=RetainedRouteConstraint(
            "accepted", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
        ),
    )
    lifecycle = EncounterLifecycle()
    snapshot = None
    for sequence, sim_time_s in enumerate((0.0, 5.0)):
        snapshot = lifecycle.step(_cycle(own, sequence=sequence, sim_time_s=sim_time_s))
    assembled = MidMpcProblemAssembler().assemble(_request(own, snapshot))
    assert isinstance(assembled, AssemblyFailure)
    assert assembled.code.value == "INVALID_INPUT"
    assert "envelope" in assembled.message


def test_assembler_keeps_cpa_safe_retained_prefix_before_commitment():
    # CANDIDATE phase: no committed obligation exists yet, so a CPA-safe
    # retained prefix is kept untouched.
    assembled = _retained_assembly(np.array([3000.0, 0.0, -7.0, 0.0]), steps=1)
    assert assembled.execution_prefix is not None
    assert assembled.problem.prefix_active_k > 0
    assert assembled.problem.route_constraint_limit_m == 480.0
    # Preserve the acknowledged prefix; the free suffix may hold or follow
    # the observed starboard side without a committed minimum alteration.
    bounds = assembled.problem.row_schedule.course_bounds_rad
    prefix_count = assembled.problem.prefix_active_k
    assert bounds[:prefix_count] == ((None, None),) * prefix_count
    assert bounds[prefix_count:] == ((assembled.problem.own_ship.psi_rad, None),) * (80 - prefix_count)
    assert assembled.problem.row_schedule.min_alt_hard_window is None


def test_assembler_keeps_compliant_retained_prefix_under_commitment():
    # COMMITTED on the starboard side with a retained route already easing
    # onto a +38.7 deg leg: the prefix never crosses the baseline and the
    # release heading already exceeds the required alteration.
    points = ((0.0, 0.0), (300.0, 240.0), (2800.0, 240.0))
    assembled = _retained_assembly(np.array([3000.0, 0.0, -7.0, 0.0]), points)
    assert assembled.execution_prefix is not None
    assert assembled.problem.prefix_active_k > 0
    assert assembled.problem.row_schedule.course_bounds_rad == ()


def test_assembler_discards_contract_conflicting_prefix_and_stages_starboard_recovery():
    # COMMITTED starboard with a retained route easing onto a -21.8 deg leg:
    # the prefix dives against the locked side, so it is discarded into the
    # transport stub (pinning stripped, retained corridor kept) and the beat
    # stages the immediate recovery - k=1 holds the baseline side, the
    # substantial-alteration window advances to its rot-feasible beat, and
    # the seed inherits the locked side through the same course box.
    points = ((0.0, 0.0), (300.0, -120.0), (2800.0, -120.0))
    assembled = _retained_assembly(np.array([3000.0, 0.0, -7.0, 0.0]), points)
    stub = assembled.execution_prefix
    assert stub is not None and _is_discard_stub(stub)
    assert stub.constraint.points_ne_m == points
    assert assembled.problem.prefix_active_k == 0
    assert assembled.problem.route_constraint_limit_m == 480.0
    assert len(assembled.problem.route_constraint_points_m) >= 2
    schedule = assembled.problem.row_schedule
    bounds = schedule.course_bounds_rad
    assert len(bounds) == 80
    assert bounds[0] == (None, None)
    assert bounds[1] == (0.0, None)
    window = schedule.min_alt_hard_window
    assert window is not None
    assert window.start_k == 2
    assert window.stop_k >= window.start_k


_MARGIN_CAPABILITY = CapabilitySnapshot(
    heading_window_rad=math.radians(45.0),
    speed_bounds_mps=(0.0, 8.0),
    rot_max_rad_s=math.radians(3.0),
    decel_max_mps2=0.3,
)


def _margin_prefix(beats: int = 10) -> RetainedPrefixPlan:
    """A straight pinned run at 7 m/s: 35 m per beat, 350 m at release."""
    constraint = RetainedRouteConstraint(
        "accepted", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
    )
    return RetainedPrefixPlan(
        constraint,
        ((0.0, 0.0), (5000.0, 0.0)),
        (7.0, 7.0),
        ("cruise", "cruise"),
        (0.0,) * beats,
        (7.0,) * beats,
        0.0,
        2,
        ((0.0, 0.0), (2000.0, 0.0)),
    )


def _margin_prediction(north_m: float, velocity_ne_mps: tuple[float, float], east_m: float = 0.0) -> TargetPrediction:
    times = np.arange(11, dtype=float) * 5.0
    return TargetPrediction(
        key=TrackKey(1, 1),
        reference_time_s=5.0,
        velocity_ne_mps=velocity_ne_mps,
        times_s=times,
        north_m=north_m + velocity_ne_mps[0] * times,
        east_m=east_m + velocity_ne_mps[1] * times,
        position_uncertainty_m=np.zeros(times.shape),
    )


def test_guard_discards_prefix_when_release_point_margin_cannot_rebuild_clearance():
    # Pinned beats hold 110 m off the stationary contact ahead, but the
    # straight continuation runs into it: the meet sits at zero distance
    # and the three rate-turn beats left before it rebuild only ~59 m of
    # the missing 100 m margin. The discard returns the transport stub so
    # the planner can still publish a GNC execution route.
    prefix = _margin_prefix()
    guard = _discard_cpa_conflicting_prefix(
        prefix,
        (_margin_prediction(460.0, (0.0, 0.0)),),
        100.0,
        _planner_input(),
        MidMpcAssemblyConfig(),
        _MARGIN_CAPABILITY,
    )
    assert guard is not None and _is_discard_stub(guard)
    assert guard.constraint is prefix.constraint
    assert guard.points_ne_m == ((0.0, 0.0),)
    assert guard.route_speed_mps == (7.0,)
    # GNC admission protocol: the discard beat declares the avoidance
    # maneuver class so the 500 m avoidance envelope replaces the 100 m
    # cruise update guard.
    assert guard.navigation_modes == ("avoidance",)
    assert guard.course_rad == ()
    assert guard.speed_mps == ()
    assert guard.incoming_course_rad == 0.0
    assert guard.retained_point_count == 1
    # The retained corridor survives the discard: it is the mechanism that
    # keeps the rewritten route inside the GNC admission envelope.
    assert guard.corridor_points_m == ((0.0, 0.0), (2000.0, 0.0))


def test_guard_keeps_prefix_when_release_point_margin_rebuilds_clearance():
    # Same geometry, meet 550 m past release: fifteen rate-turn beats at the
    # conservative speed cap open far more than the missing 100 m margin.
    prefix = _margin_prefix()
    guard = _discard_cpa_conflicting_prefix(
        prefix,
        (_margin_prediction(900.0, (0.0, 0.0)),),
        100.0,
        _planner_input(),
        MidMpcAssemblyConfig(),
        _MARGIN_CAPABILITY,
    )
    assert guard is prefix


def test_guard_keeps_prefix_when_the_release_meet_clears_the_hard_margin():
    # Abeam contact at release: the straight continuation never closes, the
    # required rebuild is negative and no turn budget is needed.
    prefix = _margin_prefix()
    guard = _discard_cpa_conflicting_prefix(
        prefix,
        (_margin_prediction(350.0, (0.0, 0.0), east_m=300.0),),
        100.0,
        _planner_input(),
        MidMpcAssemblyConfig(),
        _MARGIN_CAPABILITY,
    )
    assert guard is prefix


def _committed_snapshot(**decision_overrides: object) -> DecisionSnapshot:
    """The two-cycle fixture snapshot with its head-on commitment, overridden."""
    original = _planner_input()
    own = replace(
        original,
        tracks=(replace(original.tracks[0], state_enu=np.array([3000.0, 0.0, -7.0, 0.0])),),
    )
    lifecycle = EncounterLifecycle()
    lifecycle.step(_cycle(own, sequence=0, sim_time_s=0.0))
    snapshot = lifecycle.step(_cycle(own, sequence=1, sim_time_s=5.0))
    decision = replace(snapshot.targets[0], **decision_overrides)
    return replace(snapshot, targets=(decision,))


def _contract_guard(
    snapshot: DecisionSnapshot, prefix: RetainedPrefixPlan
) -> tuple[RetainedPrefixPlan | None, object]:
    return _discard_contract_conflicting_prefix(
        prefix, snapshot, _planner_input(), _MARGIN_CAPABILITY, MidMpcAssemblyConfig()
    )


def test_contract_guard_keeps_prefix_when_rate_ramp_reaches_the_deadline():
    # A 4-beat straight prefix releases at +20 s; the 10 s left to the +30 s
    # achievement deadline carries a 30 deg rate ramp, enough for the
    # 20.05 deg requirement.
    snapshot = _committed_snapshot(required_course_change_rad=0.35)
    prefix = _margin_prefix(beats=4)
    kept, recovery = _contract_guard(snapshot, prefix)
    assert kept is prefix
    assert recovery is None


def test_contract_guard_discards_prefix_when_rate_ramp_misses_the_deadline():
    # The same release geometry cannot gather the 34.4 deg requirement.
    snapshot = _committed_snapshot(required_course_change_rad=0.6)
    kept, recovery = _contract_guard(snapshot, _margin_prefix(beats=4))
    assert kept is not None and _is_discard_stub(kept)
    assert recovery is not None
    assert recovery.side == 1
    assert recovery.baseline_course_rad == 0.0


def test_contract_guard_discards_prefix_that_turns_against_the_locked_side():
    # Early beats ease onto a -11.5 deg leg against the starboard lock; even
    # though the release ramp could still cover a small requirement, the
    # locked-side predicate (observed-state floor) is already violated.
    constraint = RetainedRouteConstraint(
        "accepted", ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), 160.0, 32.0, 480.0
    )
    prefix = RetainedPrefixPlan(
        constraint,
        ((0.0, 0.0), (5000.0, 0.0)),
        (7.0, 7.0),
        ("cruise", "cruise"),
        (0.0, math.radians(-11.5), math.radians(-20.0), math.radians(-20.0)),
        (7.0,) * 4,
        0.0,
        2,
        (),
    )
    snapshot = _committed_snapshot(required_course_change_rad=0.1)
    kept, recovery = _contract_guard(snapshot, prefix)
    assert kept is not None and _is_discard_stub(kept)
    assert recovery is not None
    assert recovery.side == 1


def test_contract_guard_ignores_achieved_obligations():
    # An achieved commitment carries no unmet duty: the prefix survives even
    # a geometry that would miss the deadline.
    snapshot = _committed_snapshot(required_course_change_rad=0.6, action_achieved=True)
    prefix = _margin_prefix(beats=4)
    kept, recovery = _contract_guard(snapshot, prefix)
    assert kept is prefix
    assert recovery is None


_SPLICE_POINTS = ((0.0, 0.0), (500.0, 0.0), (1000.0, 0.0), (1500.0, 0.0), (2000.0, 0.0), (2000.0, 2000.0))


def _splice_stub() -> RetainedPrefixPlan:
    """A discard stub over a bending retained route, anchored at the origin."""
    constraint = RetainedRouteConstraint(
        "accepted",
        _SPLICE_POINTS,
        (7.0,) * len(_SPLICE_POINTS),
        ("cruise",) * len(_SPLICE_POINTS),
        160.0,
        32.0,
        480.0,
    )
    prefix = RetainedPrefixPlan(
        constraint,
        ((0.0, 0.0), (5000.0, 0.0)),
        (7.0, 7.0),
        ("cruise", "cruise"),
        (),
        (),
        0.0,
        1,
        ((0.0, 0.0), (2000.0, 0.0)),
    )
    return _discard_stub_prefix(prefix, _planner_input())


def _starboard_rollout(depth_m: float, *, separated: bool = True) -> np.ndarray:
    """Synthetic native rollout for the bending retained route.

    Runs the retained line, separates starboard to depth_m alongside it, and
    settles back before the route bends east.
    """
    predicted = np.zeros((9, 16))
    predicted[0, :] = 70.0 * np.arange(16)
    if separated:
        predicted[1, 6:11] = (120.0, 260.0, depth_m, 260.0, 120.0)
    predicted[2, 1:] = 0.0
    predicted[3, 1:] = 7.0
    return predicted


def _max_line_perpendicular_m(points: np.ndarray, reference: np.ndarray) -> float:
    """The GNC gate metric: nearest infinite-segment line distance per point."""
    legs = np.diff(reference, axis=0)
    lengths = np.linalg.norm(legs, axis=1)
    return max(
        float(
            np.min(
                np.abs(legs[:, 0] * (point[1] - reference[:-1, 1]) - legs[:, 1] * (point[0] - reference[:-1, 0]))
                / lengths
            )
        )
        for point in points
    )


def test_discard_stub_compiles_a_valid_execution_route_document():
    # The discard stub publishes through the splice compiler now: with no
    # separated maneuver in the rollout the retained reference itself is the
    # route, verbatim, so the GNC index-wise gate never sees a change.
    stub = _splice_stub()
    document = _published_execution_route(
        stub,
        _starboard_rollout(350.0, separated=False),
        arrival_boundary=None,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
        mission_arrival=((2000.0, 0.0), (2000.0, 2000.0), 105.0),
        mission_waypoints=((0.0, 0.0), (2000.0, 0.0), (2000.0, 2000.0)),
        ownship_position=(0.0, 0.0),
        decisions=(),
    )
    assert document["schema_version"] == "colav.mid-mpc.execution-route@1"
    assert document["prefix_intervals"] == 0
    assert document["retained_point_count"] == len(_SPLICE_POINTS)
    assert document["reference_id"] == "accepted"
    assert document["reference_hash"] == stub.constraint.semantic_hash
    np.testing.assert_allclose(np.asarray(document["points_ne_m"]), np.asarray(_SPLICE_POINTS), atol=1e-9)
    # The geometry is verbatim; the re-profiled speeds converge to planned
    # and brake to the steerage floor inside the final-approach window.
    assert len(document["speed_mps"]) == len(document["navigation_modes"]) == len(_SPLICE_POINTS)
    assert document["navigation_modes"] == ["cruise"] * len(_SPLICE_POINTS)
    assert min(document["speed_mps"]) >= 3.0 - 1e-9
    assert max(document["speed_mps"]) == pytest.approx(7.0, abs=0.2)
    assert document["speed_mps"][-1] == pytest.approx(3.0, abs=0.1)
    payload = {key: value for key, value in document.items() if key != "geometry_hash"}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == document["geometry_hash"]


def test_discard_stub_splices_replay_head_avoidance_arc_and_retained_tail():
    stub = _splice_stub()
    document = compile_spliced_execution_route(stub, _starboard_rollout(350.0))
    points = np.asarray(document["points_ne_m"])
    reference = np.asarray(_SPLICE_POINTS)
    assert document["schema_version"] == "colav.mid-mpc.execution-route@1"
    assert document["reference_id"] == "accepted"
    assert document["reference_hash"] == stub.constraint.semantic_hash
    assert document["prefix_intervals"] == 0
    head = document["retained_point_count"]
    # The head replays the retained reference verbatim from the origin, so
    # the GNC first-change index lands on the inserted arc, not on index 0.
    np.testing.assert_allclose(points[:head], reference[:head], atol=1.0)
    assert document["speed_mps"][:head] == [7.0] * head
    assert document["navigation_modes"][:head] == ["cruise"] * head
    modes = document["navigation_modes"]
    arc = [index for index, mode in enumerate(modes) if mode == "avoidance"]
    assert arc and arc[0] == head and arc[-1] == len(modes) - 4
    # The arc depth is the predicted excursion, not an invented one, and the
    # whole route stays inside the 500 m avoidance lateral guard.
    assert float(points[arc, 1].max()) == pytest.approx(350.0, abs=1.0)
    assert _max_line_perpendicular_m(points, reference) < 500.0
    # The first changed point sits at least one avoidance-lookahead ahead of
    # the measured position (here: the replayed head already covers it).
    changed = int(np.argmax(np.linalg.norm(points[: len(reference)] - reference, axis=1) > 1.0))
    assert changed == head and points[changed][0] >= 150.0
    # The tail follows the retained vertices, original modes and speeds, to
    # the original endpoint.
    np.testing.assert_allclose(points[len(modes) - 3 :], reference[3:], atol=1e-9)
    assert document["speed_mps"][len(modes) - 3 :] == [7.0] * 3
    assert document["navigation_modes"][len(modes) - 3 :] == ["cruise"] * 3
    assert document["points_ne_m"][-1] == (2000.0, 2000.0)
    # Arrival authorization is unchanged: an uncleared encounter stops the
    # published tail at the shared arrival-region boundary.
    truncated = compile_spliced_execution_route(
        stub, _starboard_rollout(350.0), arrival_boundary=((2000.0, 2000.0), 105.0)
    )
    assert truncated["points_ne_m"][-1] == (2000.0, 0.0)


def test_splice_caps_geometry_inside_the_gnc_avoidance_envelope():
    # A 700 m predicted excursion is the maneuver, not the published
    # substrate: the bulge depth caps inside the 500 m avoidance guard so
    # admission never rejects the route — the corridor still bounds the
    # solver's own excursion (v18 T11: a deep early avoidance prediction
    # raised instead of publishing).
    document = compile_spliced_execution_route(_splice_stub(), _starboard_rollout(700.0))
    route = np.asarray(document["points_ne_m"])
    reference = np.asarray(_splice_stub().constraint.points_ne_m)
    assert _max_line_perpendicular_m(route, reference) < 500.0


def test_ipopt_compile_dispatches_discard_stubs_to_the_spliced_geometry():
    stub = _splice_stub()
    predicted = _starboard_rollout(350.0)
    spliced = _published_execution_route(
        stub,
        predicted,
        arrival_boundary=None,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
        mission_arrival=((2000.0, 0.0), (2000.0, 2000.0), 105.0),
        mission_waypoints=((0.0, 0.0), (2000.0, 0.0), (2000.0, 2000.0)),
        ownship_position=(0.0, 0.0),
        decisions=(),
    )
    assert spliced["navigation_modes"].count("avoidance") > 0
    # A retained prefix with pinned beats keeps the pinned-head compilation.
    retained = _margin_prefix()
    suffix = np.zeros((9, 13))
    suffix[0, :] = 500.0 * np.arange(13)
    suffix[3, 1:] = 7.0
    active = (SimpleNamespace(risk=SimpleNamespace(value="ACTIVE")),)
    assert _published_execution_route(
        retained,
        suffix,
        arrival_boundary=None,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
        mission_arrival=((0.0, 0.0), (5000.0, 0.0), 105.0),
        mission_waypoints=((0.0, 0.0), (5000.0, 0.0)),
        ownship_position=(0.0, 0.0),
        decisions=active,
    ) == compile_execution_route(retained, suffix)


def _decayed_splice_stub() -> RetainedPrefixPlan:
    """A discard stub over the decayed mirror speed profile.

    Mirrors the v7 frame's GNC terminal schedule (4.0→3.11 with steerage
    3.0, F postmortem §4).
    """
    constraint = RetainedRouteConstraint(
        "accepted",
        _SPLICE_POINTS,
        (4.0, 3.5, 3.2, 3.11, 3.11, 3.11),
        ("cruise",) * len(_SPLICE_POINTS),
        160.0,
        32.0,
        480.0,
    )
    prefix = RetainedPrefixPlan(
        constraint,
        ((0.0, 0.0), (5000.0, 0.0)),
        (7.0, 7.0),
        ("cruise", "cruise"),
        (),
        (),
        0.0,
        1,
        (),
    )
    return _discard_stub_prefix(prefix, _planner_input())


def test_splice_tail_reprofiles_to_planned_speed_with_steerage_floor():
    # R1: the splice tail no longer inherits the decayed mirror speeds. From
    # the separation point the profile converges to the planned cruise under
    # the accel/decel envelope, and the final-approach window brakes back to
    # the steerage floor — never below it, so the mirrored execution speed
    # cannot collapse the retained forecast band again.
    rollout = _starboard_rollout(350.0)
    rollout[3, 0] = 3.2
    document = compile_spliced_execution_route(
        _decayed_splice_stub(),
        rollout,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
    )
    head = document["retained_point_count"]
    speeds = document["speed_mps"]
    # The head before the bend keeps the mirrored schedule; the profile seed
    # at the bend vertex is the measured speed.
    assert speeds[0] == 4.0
    assert speeds[1] == pytest.approx(3.2, abs=0.1)
    tail = speeds[head:]
    assert tail[0] < 7.0 + 1e-9
    assert max(tail) == pytest.approx(7.0, abs=0.2)
    assert min(tail) >= 3.0 - 1e-9
    assert tail[-1] == pytest.approx(3.0, abs=0.1)
    assert tail[-1] < tail[-2]


def test_convergence_bend_speeds_keep_band_slack_above_steerage():
    # F-B (v9): a curvature limit published exactly at the steerage floor is
    # written back into the mirror and re-enters the forecast as a zero-width
    # band. The bend floor carries the band slack; the curvature bound stays
    # the upper limit of the published speed.
    speeds = _convergence_speeds(
        5.0,
        [(0.0, 0.0), (100.0, 0.0), (100.0, 30.0), (100.0, 1000.0)],
        planned_mps=7.0,
        accel_mps2=0.3,
        decel_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        floor_mps=3.0,
    )
    assert speeds[0] == 5.0
    # The bend leg carries the slack; the final-approach brake still lands
    # on the steerage floor at the route end (clamp-covered by F-A).
    assert speeds[2] == pytest.approx(3.3, abs=1e-9)
    assert speeds[2] > 3.0 + 1e-9
    assert speeds[3] == pytest.approx(3.0, abs=1e-9)


def test_splice_terminates_at_the_arrival_entry_when_the_mirror_overshoots():
    # v11 (T1630.5): the mirror runs ~654 m past the goal while predicted —
    # L4-captured to enter the shared arrival region — reaches the circle
    # first. The splice terminates at the entry point instead of following
    # the mirror past the goal: no bulge can rejoin beyond the effective
    # terminus, and a benign degraded beat (predicted along the route,
    # GNC stop-window schedule) publishes exactly this shape — replayed
    # head plus mirror-to-entry.
    points = ((0.0, 0.0), (2000.0, 0.0), (2000.0, 2654.0))
    constraint = RetainedRouteConstraint(
        "accepted", points, (7.0,) * 3, ("cruise",) * 3, 160.0, 32.0, 480.0
    )
    prefix = RetainedPrefixPlan(
        constraint,
        ((0.0, 0.0), (5000.0, 0.0)),
        (7.0, 7.0),
        ("cruise", "cruise"),
        (),
        (),
        0.0,
        1,
        (),
    )
    stub = _discard_stub_prefix(prefix, _planner_input())
    predicted = np.zeros((9, 41))
    predicted[0, :21] = 100.0 * np.arange(21)
    predicted[0, 21:] = 2000.0
    predicted[1, 21:] = 100.0 * np.arange(20)
    predicted[2, 1:] = 0.0
    predicted[3, 1:] = 7.0
    document = compile_spliced_execution_route(
        stub,
        predicted,
        arrival_boundary=((2000.0, 2000.0), 105.0),
        mission_arrival=((2000.0, 0.0), (2000.0, 2000.0), 105.0),
    )
    assert document["schema_version"] == "colav.mid-mpc.execution-route@1"
    assert document["reference_hash"] == stub.constraint.semantic_hash
    # The route ends at the predicted arrival-region entry, never at the
    # mirrored overshoot endpoint.
    assert document["points_ne_m"][-1] == (2000.0, 1900.0)
    assert (2000.0, 2654.0) not in document["points_ne_m"]
    assert document["retained_point_count"] == 2
    assert document["navigation_modes"] == ["cruise"] * len(document["navigation_modes"])
    assert _max_line_perpendicular_m(np.asarray(document["points_ne_m"]), np.asarray(points)) < 500.0
    payload = {key: value for key, value in document.items() if key != "geometry_hash"}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == document["geometry_hash"]


def test_splice_rewrites_a_disk_grazing_tail_onto_the_mission_line():
    # H (v12): the mirror grazes the arrival disk 100 m off the mission
    # final leg; any route that keeps that offset through the disk fails
    # QUALITY_NAVIGATION_CAPTURE (>20 m) forever after — candidates cannot
    # reshape the mirror, so the rejection deadlocks. Before publishing, the
    # splice self-checks the capture metric and rewrites the tail: prune
    # before the disk, rejoin the mission line outside it, and enter along
    # the line (capture exactly 0).
    own = replace(_planner_input(), ownship_state=np.array([0.0, 100.0, 0.0, 7.0, 0.0, 0.0]))
    points = ((0.0, 100.0), (1000.0, 100.0), (2000.0, 100.0), (3000.0, 100.0), (4000.0, 100.0))
    constraint = RetainedRouteConstraint(
        "accepted", points, (7.0,) * 5, ("cruise",) * 5, 160.0, 32.0, 480.0
    )
    prefix = RetainedPrefixPlan(
        constraint, ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), (), (), 0.0, 1, ()
    )
    stub = _discard_stub_prefix(prefix, own)
    predicted = np.zeros((9, 31))
    predicted[0, :] = 100.0 * np.arange(31)
    predicted[1, :] = 100.0
    predicted[2, 1:] = 0.0
    predicted[3, 1:] = 7.0
    mission_arrival = ((0.0, 0.0), (3000.0, 0.0), 105.0)
    document = compile_spliced_execution_route(
        stub, predicted, arrival_boundary=None, mission_arrival=mission_arrival
    )
    mission = (mission_arrival[0], mission_arrival[1])
    route = np.asarray(document["points_ne_m"])

    assert navigation_capture_error(route[:, 0], route[:, 1], mission, 105.0) == pytest.approx(0.0, abs=1e-9)
    assert _max_line_perpendicular_m(route, np.asarray(points)) < 500.0
    # The route ends on the mission line, inside the disk, at the goal.
    assert document["points_ne_m"][-1] == (3000.0, 0.0)
    assert (3000.0, 100.0) not in document["points_ne_m"]
    # The rejoin happens outside the standoff before the disk.
    assert (2000.0, 0.0) in document["points_ne_m"]


def test_splice_benign_route_passes_the_same_capture_self_check():
    # A benign route that already enters the disk on the mission line passes
    # the self-check untouched: no rewrite, and the terminus is the
    # predicted arrival entry.
    own = replace(_planner_input(), ownship_state=np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0]))
    points = ((0.0, 0.0), (1000.0, 0.0), (2000.0, 0.0), (3000.0, 0.0), (4000.0, 0.0))
    constraint = RetainedRouteConstraint(
        "accepted", points, (7.0,) * 5, ("cruise",) * 5, 160.0, 32.0, 480.0
    )
    prefix = RetainedPrefixPlan(
        constraint, ((0.0, 0.0), (5000.0, 0.0)), (7.0, 7.0), ("cruise", "cruise"), (), (), 0.0, 1, ()
    )
    stub = _discard_stub_prefix(prefix, own)
    predicted = np.zeros((9, 31))
    predicted[0, :] = 100.0 * np.arange(31)
    predicted[2, 1:] = 0.0
    predicted[3, 1:] = 7.0
    mission_arrival = ((0.0, 0.0), (3000.0, 0.0), 105.0)
    document = compile_spliced_execution_route(
        stub, predicted, arrival_boundary=None, mission_arrival=mission_arrival
    )
    route = np.asarray(document["points_ne_m"])
    mission = (mission_arrival[0], mission_arrival[1])
    assert navigation_capture_error(route[:, 0], route[:, 1], mission, 105.0) == pytest.approx(0.0, abs=1e-9)
    assert document["points_ne_m"][-1] == (2900.0, 0.0)
    assert (4000.0, 0.0) not in document["points_ne_m"]


def test_folded_mirror_beat_compiles_and_solves_directly():
    # v13 T1771 end to end: the folded mirror used to pin a constant rot
    # violation at the seam and die INFEASIBLE. The sampled interception now
    # turns the seam through the transition arc inside the rot envelope, the
    # full course pins (never a partial pin — see the T264.5 truncation
    # shadow), and the beat solves.
    assembled = _retained_assembly(
        np.array([3000.0, 1500.0, -7.0, 0.0]), ((0.0, 0.0), (230.0, 0.0), (310.0, -80.0), (4000.0, -80.0))
    )
    assert assembled.retained_degraded is None
    assert assembled.execution_prefix is not None and assembled.execution_prefix.course_rad
    result = MidMpcIpoptSolver(MidMpcConfig(horizon_steps=80, strict_slack_bounds=True, max_wall_time_s=15)).solve(
        assembled.problem
    )
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}


def test_degraded_beat_publishes_through_the_splice_path():
    # v14/v15: a folded mirror never trims its pin — the released free beats
    # would start from the avoidance-arc depth against the direction floor
    # (the T264.5 truncation shadow, seed violation 51.1) — so the beat
    # degrades whole to the stub exit, and the stub publishes through the
    # splice path: replayed mirror head, splice geometry, no pinned beats.
    constraint = RetainedRouteConstraint(
        "mission",
        ((0.0, 0.0), (230.0, 0.0), (310.0, 80.0), (4000.0, 80.0)),
        (7.0,) * 4,
        ("cruise",) * 4,
        160.0,
        32.0,
        480.0,
    )
    state = np.array([0.0, 0.0, 0.0, 7.0, 0.0, 0.0])
    plan = degraded_stub_prefix(
        constraint, state, knot_trim_reason="knot_trim: mirror fold at the pin seam exceeds the rot envelope"
    )
    predicted = _starboard_rollout(350.0)
    document = _published_execution_route(
        plan,
        predicted,
        arrival_boundary=None,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
        mission_arrival=((230.0, 0.0), (4000.0, 80.0), 105.0),
        mission_waypoints=((0.0, 0.0), (230.0, 0.0), (310.0, 80.0), (4000.0, 80.0)),
        ownship_position=(0.0, 0.0),
        decisions=(SimpleNamespace(risk=SimpleNamespace(value="ACTIVE")),),
    )
    assert document["schema_version"] == "colav.mid-mpc.execution-route@1"
    assert document["prefix_intervals"] == 0
    reference = np.asarray(constraint.points_ne_m)
    route = np.asarray(document["points_ne_m"])
    np.testing.assert_allclose(
        route[: document["retained_point_count"]], reference[: document["retained_point_count"]], atol=1.0
    )
    assert _max_line_perpendicular_m(route, reference) < 500.0
    assert document["points_ne_m"][-1] == (4000.0, 80.0)


def test_handback_publishes_the_mission_route_after_encounter_release():
    # A (v13): past encounter release, rolling the mirror-splice chain has no
    # remaining value — the mission route is published directly, with
    # avoidance codes so the 500 m tier covers the stale S-shaped mirror.
    mission = ((0.0, 0.0), (1500.0, 0.0), (3000.0, 0.0))
    decisions = (SimpleNamespace(risk=SimpleNamespace(value="RELEASED")),)
    document = _published_execution_route(
        _splice_stub(),
        _starboard_rollout(350.0),
        arrival_boundary=None,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
        mission_arrival=((1500.0, 0.0), (3000.0, 0.0), 105.0),
        mission_waypoints=mission,
        ownship_position=(1500.0, 0.0),
        decisions=decisions,
    )
    assert document["points_ne_m"] == [tuple(point) for point in mission]
    assert document["navigation_modes"] == ["avoidance"] * len(mission)
    assert document["speed_mps"] == [7.0] * len(mission)
    assert document["reference_hash"] == _splice_stub().constraint.semantic_hash
    assert document["prediction_basis"].startswith("mission handback")
    route = np.asarray(document["points_ne_m"])
    mission_pts = (mission[0], mission[-1])
    assert navigation_capture_error(route[:, 0], route[:, 1], mission_pts, 105.0) == pytest.approx(0.0, abs=1e-9)
    # The stale mirror sits well inside the 500 m avoidance tier of the
    # mission line, so the handback passes the dynamic gate.
    assert _max_line_perpendicular_m(route, np.asarray(_SPLICE_POINTS)) < 500.0


def test_handback_skipped_while_a_target_is_still_active():
    active = (SimpleNamespace(risk=SimpleNamespace(value="ACTIVE")),)
    document = _published_execution_route(
        _splice_stub(),
        _starboard_rollout(350.0),
        arrival_boundary=None,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
        mission_arrival=((1500.0, 0.0), (3000.0, 0.0), 105.0),
        mission_waypoints=((0.0, 0.0), (1500.0, 0.0), (3000.0, 0.0)),
        ownship_position=(1500.0, 0.0),
        decisions=active,
    )
    assert document["prediction_basis"].startswith("retained-reference splice")


def test_handback_skipped_while_outside_the_mission_corridor():
    released = (SimpleNamespace(risk=SimpleNamespace(value="RELEASED")),)
    document = _published_execution_route(
        _splice_stub(),
        _starboard_rollout(350.0),
        arrival_boundary=None,
        planned_speed_mps=7.0,
        accel_max_mps2=0.3,
        decel_max_mps2=0.3,
        rot_max_rad_s=math.radians(3.0),
        steerage_speed_mps=3.0,
        mission_arrival=((1500.0, 0.0), (3000.0, 0.0), 105.0),
        mission_waypoints=((0.0, 0.0), (1500.0, 0.0), (3000.0, 0.0)),
        ownship_position=(1500.0, 600.0),
        decisions=released,
    )
    assert document["prediction_basis"].startswith("retained-reference splice")


def test_splice_tail_without_profile_parameters_keeps_the_mirrored_speeds():
    # Without the capability evidence the splice stays on the mirrored
    # profile: head vertices verbatim, arc at the bend speed, tail at the
    # retained vertices' speeds.
    document = compile_spliced_execution_route(_decayed_splice_stub(), _starboard_rollout(350.0))
    speeds = document["speed_mps"]
    modes = document["navigation_modes"]
    arc_end = modes.index("cruise", modes.index("avoidance"))
    assert speeds[:2] == [4.0, 3.5]
    assert set(speeds[2:arc_end]) == {3.5}
    assert speeds[arc_end:] == [3.11, 3.11, 3.11]


def test_splice_tail_always_ends_on_the_retained_vertices():
    # The tail follows the retained vertices to the retained endpoint under
    # any arrival boundary: a goal-directed approach leg would leave the
    # 500 m avoidance envelope whenever the mirrored endpoint diverges from
    # the goal (v8 closed loop died on exactly that self-check), and the
    # non-fatal capture-gate rejections are preferable to an inadmissible
    # route. The arrival stop merely truncates before the shared region.
    document = compile_spliced_execution_route(
        _splice_stub(), _starboard_rollout(350.0), arrival_boundary=((2000.0, 1000.0), 105.0)
    )
    points = document["points_ne_m"]
    assert (2000.0, 1000.0) not in points
    assert points[-1] == (2000.0, 0.0)
    assert _max_line_perpendicular_m(np.asarray(points), np.asarray(_SPLICE_POINTS)) < 500.0
    # Without an active encounter the retained endpoint is kept verbatim.
    document = compile_spliced_execution_route(_splice_stub(), _starboard_rollout(350.0))
    assert document["points_ne_m"][-1] == (2000.0, 2000.0)
