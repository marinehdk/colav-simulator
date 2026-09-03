"""Mid-MPC accepted rolling routes to modular ILOS: receipt-to-route bridge (Issue #63).

Seams under test:
- ``MidMpcRouteBridge.current_route`` — the only translation seam between the
  Mid-MPC accepted-plan lifecycle and the modular ``TrackedRoute`` contract.
- Expiry/acceptance enforcement stays with the command latch (reused, not
  re-created); the bridge only emits honest receipt semantics.

The consumed artifact is pinned per the S7.0 audit (issue list #1): the bridge
reads the ``accepted_plan_receipt`` inside the planner trace
``algorithm_details`` — the L4-accepted plan — and never the prediction grid.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from colav_simulator.core.colav.threat_assessment import OwnshipThreatPrediction
from colav_simulator.core.colav.threat_management import AcceptedPlanReceipt
from colav_simulator.core.tracking.trackers import TrackKey
from colav_simulator.modular_gnc.command_latch import CommandLatch
from colav_simulator.modular_gnc.contracts import CommandInput, ControlTask, FailureCode, NavigationState
from colav_simulator.modular_gnc.guidance_ilos import ILOSConfig, IntegralLineOfSightGuidance
from colav_simulator.modular_gnc.route_bridge import MidMpcRouteBridge

DT_S = 0.1


def _prediction(
    *,
    north_m: tuple[float, ...] = (0.0, 50.0, 100.0),
    east_m: tuple[float, ...] = (0.0, 0.0, 0.0),
    speed_mps: tuple[float, ...] = (4.0, 4.0, 4.0),
    heading_rad: float = 0.0,
    dt_s: float = 5.0,
    reference_time_s: float = 0.0,
) -> OwnshipThreatPrediction:
    samples = len(north_m)
    return OwnshipThreatPrediction(
        times_s=np.arange(samples, dtype=float) * dt_s,
        states_enu=np.column_stack(
            (
                north_m,
                east_m,
                [speed * np.cos(heading_rad) for speed in speed_mps],
                [speed * np.sin(heading_rad) for speed in speed_mps],
            )
        ),
        basis="ACCEPTED_PLAN",
        model="mid_mpc_prediction_evidence",
        source="L4_ACCEPTED_PLAN",
        target_keys=(TrackKey(1, 1),),
        reference_time_s=reference_time_s,
    )


def _receipt_document(
    *,
    accepted_sequence: int = 7,
    accepted_at_s: float = 0.0,
    valid_until_s: float = 5.0,
    prediction: OwnshipThreatPrediction | None = None,
) -> dict[str, Any]:
    prediction = prediction or _prediction()
    receipt = AcceptedPlanReceipt.issue(
        accepted_sequence=accepted_sequence,
        accepted_at_s=accepted_at_s,
        valid_until_s=valid_until_s,
        accepted_prediction=prediction,
        target_keys=(TrackKey(1, 1),),
        prediction_hash=prediction.semantic_hash,
    )
    return receipt.to_dict()


def _details(
    receipt: dict[str, Any],
    *,
    revision_reason: str | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {"trajectory_source": "fresh_ipopt_solve"}
    if revision_reason is not None:
        details["rolling_plan"] = {"reference": {"revision_reason": revision_reason}}
    details["accepted_plan_receipt"] = receipt
    return details


def _planner_data(details: dict[str, Any]) -> dict[str, Any]:
    return {"planner": {"algorithm_id": "mid_mpc_ipopt", "algorithm_details": details}}


def _bridge() -> MidMpcRouteBridge:
    return MidMpcRouteBridge(dt_s=DT_S)


def test_missing_accepted_receipt_fails_without_route_or_fallback() -> None:
    bridge = _bridge()

    for planner_data in ({}, {"planner": {}}, {"planner": {"algorithm_details": {}}}, None):
        decision = bridge.current_route(tick=0, planner_data=planner_data)

        assert decision.route is None
        assert decision.failure is not None
        assert decision.failure.code is FailureCode.REJECTED_ROUTE
        assert decision.failure.phase == "route_bridge"


def test_accepted_receipt_maps_to_tracked_route_with_receipt_semantics() -> None:
    bridge = _bridge()
    receipt = _receipt_document()

    decision = bridge.current_route(tick=0, planner_data=_planner_data(_details(receipt)))

    assert decision.failure is None
    route = decision.route
    assert route is not None
    assert route.route_id.startswith("mid-mpc-")
    assert route.revision == 0
    assert route.accepted is True
    assert route.valid_from_tick == 0
    assert route.valid_until_tick == 50  # valid_until_s 5.0 at dt 0.1
    np.testing.assert_array_equal(route.waypoints_ne_m, np.array([[0.0, 50.0, 100.0], [0.0, 0.0, 0.0]]))
    np.testing.assert_array_equal(route.speed_mps, np.array([4.0, 4.0, 4.0]))
    assert route.task is ControlTask.TRANSIT


def test_held_receipt_reemits_identical_route_on_every_hold_tick() -> None:
    bridge = _bridge()
    first = bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))

    held_middle = bridge.current_route(tick=25, planner_data=_planner_data(_details(_receipt_document())))
    held_last = bridge.current_route(tick=49, planner_data=_planner_data(_details(_receipt_document())))

    assert held_middle.failure is None
    assert held_last.failure is None
    assert held_middle.route == first.route
    assert held_last.route == first.route


def test_continuity_preserved_roll_keeps_route_identity_and_rolls_geometry() -> None:
    bridge = _bridge()
    first = bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))
    rolled_receipt = _receipt_document(
        accepted_sequence=8,
        accepted_at_s=5.0,
        valid_until_s=10.0,
        prediction=_prediction(north_m=(200.0, 250.0, 300.0), reference_time_s=5.0),
    )

    rolled = bridge.current_route(
        tick=50,
        planner_data=_planner_data(_details(rolled_receipt, revision_reason="CONTINUITY_PRESERVED")),
    )

    assert rolled.failure is None
    assert rolled.route is not None
    assert rolled.route.route_id == first.route.route_id
    assert rolled.route.revision == first.route.revision
    assert rolled.route is not first.route
    np.testing.assert_array_equal(rolled.route.waypoints_ne_m, np.array([[200.0, 250.0, 300.0], [0.0, 0.0, 0.0]]))
    assert rolled.route.valid_from_tick == 50
    assert rolled.route.valid_until_tick == 100


@pytest.mark.parametrize("revision_reason", ["COLREG_AUTHORITY_CHANGED", "MISSION_ROUTE_CHANGED"])
def test_identity_change_reason_increments_revision_instead_of_rejecting(revision_reason: str) -> None:
    bridge = _bridge()
    first = bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))
    changed_receipt = _receipt_document(
        accepted_sequence=8,
        accepted_at_s=5.0,
        valid_until_s=10.0,
        prediction=_prediction(north_m=(200.0, 250.0, 300.0), reference_time_s=5.0),
    )

    changed = bridge.current_route(
        tick=50,
        planner_data=_planner_data(_details(changed_receipt, revision_reason=revision_reason)),
    )

    assert changed.failure is None
    assert changed.route is not None
    assert changed.route.route_id == first.route.route_id
    assert changed.route.revision == first.route.revision + 1


def test_missing_rolling_plan_document_is_treated_as_explicit_discontinuity() -> None:
    bridge = _bridge()
    first = bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))
    next_receipt = _receipt_document(
        accepted_sequence=8,
        accepted_at_s=5.0,
        valid_until_s=10.0,
        prediction=_prediction(north_m=(200.0, 250.0, 300.0), reference_time_s=5.0),
    )

    changed = bridge.current_route(tick=50, planner_data=_planner_data(_details(next_receipt)))

    assert changed.failure is None
    assert changed.route is not None
    assert changed.route.route_id == first.route.route_id
    assert changed.route.revision == first.route.revision + 1


def test_receipt_sequence_regression_fails_structurally() -> None:
    bridge = _bridge()
    bridge.current_route(
        tick=0,
        planner_data=_planner_data(_details(_receipt_document(accepted_sequence=8))),
    )

    regressed = bridge.current_route(
        tick=50,
        planner_data=_planner_data(_details(_receipt_document(accepted_sequence=7))),
    )

    assert regressed.route is None
    assert regressed.failure is not None
    assert regressed.failure.code is FailureCode.OUT_OF_ORDER_INPUT


def test_duplicate_sequence_with_new_receipt_fails_structurally() -> None:
    bridge = _bridge()
    bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document(accepted_sequence=7))))
    duplicate = _receipt_document(
        accepted_sequence=7,
        accepted_at_s=0.0,
        valid_until_s=5.0,
        prediction=_prediction(north_m=(10.0, 60.0, 110.0)),
    )

    decision = bridge.current_route(tick=1, planner_data=_planner_data(_details(duplicate)))

    assert decision.route is None
    assert decision.failure is not None
    assert decision.failure.code is FailureCode.DUPLICATE_INPUT


def test_tampered_receipt_body_fails_structurally() -> None:
    bridge = _bridge()
    receipt = _receipt_document()
    tampered = {**receipt, "valid_until_s": 99.0}

    decision = bridge.current_route(tick=0, planner_data=_planner_data(_details(tampered)))

    assert decision.route is None
    assert decision.failure is not None
    assert decision.failure.code is FailureCode.REJECTED_ROUTE


def test_receipt_expiry_stays_with_command_latch_not_the_bridge() -> None:
    bridge = _bridge()
    decision = bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))
    route = decision.route
    assert route is not None
    latch = CommandLatch(controller_period_ticks=1)

    inside = latch.consume(CommandInput.route(50, route))
    expired = latch.consume(CommandInput.route(51, route))

    assert inside.failure is None
    assert expired.failure is not None
    assert expired.failure.code is FailureCode.EXPIRED_ROUTE


def test_bridge_snapshot_restore_replay_is_deterministic() -> None:
    original = _bridge()
    original.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))
    rolled_receipt = _receipt_document(
        accepted_sequence=8,
        accepted_at_s=5.0,
        valid_until_s=10.0,
        prediction=_prediction(north_m=(200.0, 250.0, 300.0), reference_time_s=5.0),
    )
    original.current_route(
        tick=50,
        planner_data=_planner_data(_details(rolled_receipt, revision_reason="CONTINUITY_PRESERVED")),
    )
    next_receipt = _receipt_document(
        accepted_sequence=9,
        accepted_at_s=10.0,
        valid_until_s=15.0,
        prediction=_prediction(north_m=(400.0, 450.0, 500.0), reference_time_s=10.0),
    )

    snapshot = original.snapshot()
    expected = original.current_route(
        tick=100,
        planner_data=_planner_data(_details(next_receipt, revision_reason="CONTINUITY_PRESERVED")),
    )

    restored = _bridge()
    restored.restore(snapshot)
    replay = restored.current_route(
        tick=100,
        planner_data=_planner_data(_details(next_receipt, revision_reason="CONTINUITY_PRESERVED")),
    )

    assert replay == expected
    assert replay.route is not None
    assert replay.route.revision == snapshot.revision


def test_bridge_reset_returns_to_initial_identity_state() -> None:
    bridge = _bridge()
    bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))
    bridge.current_route(
        tick=50,
        planner_data=_planner_data(
            _details(
                _receipt_document(
                    accepted_sequence=8,
                    accepted_at_s=5.0,
                    valid_until_s=10.0,
                    prediction=_prediction(north_m=(200.0, 250.0, 300.0), reference_time_s=5.0),
                ),
                revision_reason="COLREG_AUTHORITY_CHANGED",
            )
        ),
    )

    bridge.reset()
    fresh = bridge.current_route(tick=0, planner_data=_planner_data(_details(_receipt_document())))

    assert fresh.failure is None
    assert fresh.route is not None
    assert fresh.route.revision == 0


def test_route_speeds_exceeding_ceiling_are_capped_by_ilos_downstream() -> None:
    bridge = _bridge()
    receipt = _receipt_document(
        prediction=_prediction(speed_mps=(20.0, 20.0, 20.0)),
    )
    decision = bridge.current_route(tick=0, planner_data=_planner_data(_details(receipt)))
    route = decision.route
    assert route is not None
    np.testing.assert_array_equal(route.speed_mps, np.array([20.0, 20.0, 20.0]))

    guidance = IntegralLineOfSightGuidance(
        ILOSConfig(lookahead_distance_m=50.0, integral_gain=0.0, max_speed_mps=10.0)
    )
    guidance.compute_reference(0, route, NavigationState(0.0, 0.0, 0.0, 4.0, 0.0, 0.0), DT_S)

    assert guidance.latest_trace is not None
    assert guidance.latest_trace.route_speed_mps == pytest.approx(20.0)
    assert guidance.latest_trace.speed_ceiling_applied is True
    assert guidance.latest_trace.speed_reference_mps == pytest.approx(10.0)
