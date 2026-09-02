"""Modular ILOS executes only accepted Mid-MPC rolling routes (Issue #63).

End-to-end coverage of the tracked-route seam: the accepted-plan receipt of a
real Mid-MPC solve (fast-horizon convention of ``tests/test_mid_mpc_ipopt_integration.py``:
horizon_steps=4, horizon_dt_s=5.0, deadline_mode=OFF) crosses the route bridge,
becomes a ``TrackedRoute``, drives the modular stack's ILOS guidance phase, and
keeps direct references mutually exclusive. The legacy planner path itself is
untouched and stays environment-truth-fed; the modular facade consumes only the
accepted receipt.
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.core import ship
from colav_simulator.core.colav.custom_mpc_adapter import CustomMPCAdapter, DeadlineMode, FactoryContext
from colav_simulator.core.colav.threat_assessment import OwnshipThreatPrediction
from colav_simulator.core.colav.threat_management import AcceptedPlanReceipt
from colav_simulator.core.tracking.trackers import TrackKey, TrackSnapshot, TrackStatus
from colav_simulator.integrations.registry import IntegrationRegistry
from colav_simulator.modular_gnc.adapter import ModularShipAbort, ModularShipAdapter
from colav_simulator.modular_gnc.contracts import ControlTask, NavigationState
from colav_simulator.modular_gnc.guidance_ilos import IntegralLineOfSightGuidance
from colav_simulator.modular_gnc.passthrough_modules import PassThroughModules
from colav_simulator.modular_gnc.route_bridge import MidMpcRouteBridge
from colav_simulator.modular_gnc.stack import ModularShipStack

ALGORITHM_ID = "mid_mpc_ipopt"
_MID_MPC_KWARGS = {
    "horizon_steps": 4,
    "horizon_dt_s": 5.0,
    "solve_period_s": 5.0,
    "deadline_s": 20.0,
}


def _plan_prediction(*, north_m: tuple[float, ...]) -> OwnshipThreatPrediction:
    samples = len(north_m)
    return OwnshipThreatPrediction(
        times_s=np.arange(samples, dtype=float) * 5.0,
        states_enu=np.column_stack((north_m, np.zeros(samples), np.full(samples, 4.0), np.zeros(samples))),
        target_keys=(TrackKey(1, 1),),
    )


def _receipt_document(
    *,
    accepted_at_s: float = 0.0,
    valid_until_s: float = 5.0,
    north_m: tuple[float, ...] = (0.0, 50.0),
) -> dict:
    prediction = _plan_prediction(north_m=north_m)
    return AcceptedPlanReceipt.issue(
        accepted_sequence=1,
        accepted_at_s=accepted_at_s,
        valid_until_s=valid_until_s,
        accepted_prediction=prediction,
        target_keys=(TrackKey(1, 1),),
        prediction_hash=prediction.semantic_hash,
    ).to_dict()


def _trace(receipt_document: dict) -> dict:
    details = {"trajectory_source": "fresh_ipopt_solve", "accepted_plan_receipt": receipt_document}
    return {"planner": {"algorithm_id": ALGORITHM_ID, "algorithm_details": details}}


def _ship_config() -> ship.Config:
    return ship.Config.from_dict(
        {
            "id": 4,
            "mmsi": 44,
            "csog_state": [0.0, 0.0, 0.0, 4.0],
            "waypoints": [[0.0, 500.0], [0.0, 0.0]],
            "speed_plan": [4.0, 4.0],
            "guidance": {"los": {}},
            "ship_modules": {
                "preset": "legacy_equivalent",
                "overrides": {"scheduler": {"controller_period_ticks": 1, "guidance_period_ticks": 1}},
                "modules": {
                    "plant": {"identity": "pass_through_plant", "parameters": {}},
                    "guidance": {"identity": "integral_line_of_sight", "parameters": {}},
                    "controller": {"identity": "pass_through_controller", "parameters": {}},
                },
            },
        }
    )


def _modules() -> PassThroughModules:
    return PassThroughModules(guidance=IntegralLineOfSightGuidance())


def _adapter(
    *,
    modules: PassThroughModules | None = None,
    route_source: MidMpcRouteBridge | None = None,
) -> ModularShipAdapter:
    config = _ship_config()
    stack = ModularShipStack(config.ship_modules, modules or _modules())
    return ModularShipAdapter.from_legacy_config(config, stack, route_source=route_source)


def test_route_authority_drives_ilos_and_stays_mutually_exclusive_with_direct() -> None:
    receipt = _receipt_document()
    modules = _modules()
    adapter = _adapter(modules=modules, route_source=MidMpcRouteBridge(dt_s=0.1))
    adapter.reset(seed=3)
    adapter._legacy.set_colav_data(_trace(receipt))

    for _ in range(3):
        state, _, applied = adapter.forward(0.1)
        assert state.shape == (6,)
        assert applied.shape == (9,)

    consumptions = modules.route_consumptions
    assert [(tick, revision) for tick, _, revision in consumptions] == [(0, 0), (1, 0), (2, 0)]
    guidance_trace = modules.snapshot().held_guidance_trace
    assert guidance_trace is not None
    assert guidance_trace.route_id == consumptions[0][1]
    assert guidance_trace.speed_reference_mps == pytest.approx(4.0)
    # Mutual exclusion: no direct reference was ever latched while the route
    # authority was active (CommandInput contract, enforced at the facade).
    _, last_direct_source_tick, pending_direct, held_direct, pending_route = adapter.stack.snapshot(
    ).module_snapshots[1]
    assert last_direct_source_tick == -1
    assert pending_direct is None
    assert held_direct is None
    assert pending_route is not None


def test_missing_receipt_aborts_and_never_falls_back_to_direct_reference() -> None:
    adapter = _adapter(route_source=MidMpcRouteBridge(dt_s=0.1))
    adapter.reset(seed=1)
    references = np.zeros((9, 1))
    references[2, 0] = 0.3
    references[3, 0] = 4.0
    adapter.set_references(references)  # direct column exists but must never be consumed

    with pytest.raises(ModularShipAbort, match="REJECTED_ROUTE"):
        adapter.forward(0.1)


def test_expired_route_window_aborts_through_structured_expiry() -> None:
    receipt = _receipt_document(valid_until_s=0.5)  # covers ticks 0..5 at dt 0.1, then expires
    adapter = _adapter(route_source=MidMpcRouteBridge(dt_s=0.1))
    adapter.reset(seed=2)
    adapter._legacy.set_colav_data(_trace(receipt))

    for _ in range(6):
        adapter.forward(0.1)
    with pytest.raises(ModularShipAbort, match="EXPIRED_ROUTE"):
        adapter.forward(0.1)


def test_adapter_reset_clears_route_bridge_translation_state() -> None:
    receipt = _receipt_document()
    modules = _modules()
    adapter = _adapter(modules=modules, route_source=MidMpcRouteBridge(dt_s=0.1))
    adapter.reset(seed=5)
    adapter._legacy.set_colav_data(_trace(receipt))
    adapter.forward(0.1)
    before_reset = modules.route_consumptions

    adapter.reset(seed=5)
    adapter.forward(0.1)

    assert before_reset == ((0, before_reset[0][1], 0),)
    assert modules.route_consumptions == before_reset


@pytest.fixture(scope="module")
def mid_mpc() -> CustomMPCAdapter:
    adapter = IntegrationRegistry().build_algorithm(
        ALGORITHM_ID,
        {"factory": "colav_simulator.integrations.mid_mpc_ipopt:create", "kwargs": dict(_MID_MPC_KWARGS)},
        factory_context=FactoryContext(
            ALGORITHM_ID,
            0,
            scenario_id="modular_route_bridge",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
        ),
    )
    assert isinstance(adapter, CustomMPCAdapter)
    return adapter


def _head_on_snapshot(t: float, *, north_m: float = 2000.0) -> TrackSnapshot:
    return TrackSnapshot(
        key=TrackKey(1, 1),
        state=np.array([north_m, 0.0, -7.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=8.45,
        width_m=3.0,
        observed_at_s=t,
        generated_at_s=t,
        status=TrackStatus.UPDATED,
        source="modular-route-bridge",
    )


def _mid_mpc_plan(
    planner: CustomMPCAdapter,
    t: float,
    *,
    ownship: np.ndarray | None = None,
    target_north_m: float = 2000.0,
) -> np.ndarray:
    return planner.plan(
        t,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]) if ownship is None else ownship,
        [_head_on_snapshot(t, north_m=target_north_m)],
        dt=1.0,
        os_length=15.0,
        os_model_name="Viknes",
        os_controller_name="FLSC",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )


def test_accepted_mid_mpc_routes_drive_ilos_across_solve_boundary(mid_mpc: CustomMPCAdapter) -> None:
    bridge = MidMpcRouteBridge(dt_s=1.0)
    _mid_mpc_plan(mid_mpc, 0.0)

    first = bridge.current_route(tick=0, planner_data=mid_mpc.get_colav_data())

    assert first.failure is None
    route = first.route
    assert route is not None
    assert route.accepted is True
    assert route.revision == 0
    assert route.valid_from_tick == 0
    assert route.valid_until_tick == 5  # decision-period expiry mapped to ticks
    receipt = mid_mpc.get_diagnostics().details["accepted_plan_receipt"]
    prediction = np.asarray(receipt["accepted_prediction"]["states_enu"], dtype=float)
    np.testing.assert_allclose(route.waypoints_ne_m, prediction[:, :2].T)
    np.testing.assert_allclose(route.speed_mps, np.hypot(prediction[:, 2], prediction[:, 3]), rtol=0.0, atol=1e-12)
    assert route.task is ControlTask.TRANSIT
    # Ground-truth frame check: the ownship starts at the origin heading north,
    # so the accepted plan's first interval must advance north, not east.
    assert route.waypoints_ne_m[0, 1] > route.waypoints_ne_m[0, 0]

    guidance = IntegralLineOfSightGuidance()
    guidance.compute_reference(0, route, NavigationState(0.0, 0.0, 0.0, 4.0, 0.0, 0.0), 1.0)
    assert guidance.latest_trace is not None
    assert guidance.latest_trace.route_id == route.route_id

    # Second solve at t=5: the canonical COLREG authority hash changed (S7.0
    # audit issue #8, lifecycle as designed), so the bridge must express the
    # new accepted plan as a route revision — never reject it and never keep
    # the old identity silently.
    _mid_mpc_plan(mid_mpc, 5.0, ownship=np.array([20.0, 0.0, 0.0, 4.0, 0.0, 0.0]), target_north_m=1965.0)
    revision_reason = mid_mpc.get_diagnostics().details["rolling_plan"]["reference"]["revision_reason"]
    second = bridge.current_route(tick=5, planner_data=mid_mpc.get_colav_data())

    assert revision_reason == "COLREG_AUTHORITY_CHANGED"
    assert second.failure is None
    rolled = second.route
    assert rolled is not None
    assert rolled.route_id == route.route_id
    assert rolled.revision == route.revision + 1
    assert rolled.valid_from_tick == 5
    assert rolled.valid_until_tick == 10

    rolled_reference = guidance.compute_reference(5, rolled, NavigationState(20.0, 0.0, 0.0, 4.0, 0.0, 0.0), 1.0)
    assert rolled_reference.values[2] == pytest.approx(guidance.latest_trace.course_reference_rad)
    assert guidance.latest_trace.route_state_reset is True  # identity change zeroed integral state
