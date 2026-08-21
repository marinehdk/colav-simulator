from __future__ import annotations

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import DeadlineMode, FactoryContext
from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.core.tracking.trackers import TrackKey, TrackSnapshot, TrackStatus
from colav_simulator.integrations import mid_mpc_ipopt


def test_mid_mpc_uses_injected_runtime_threat_coordinator_and_native_solver() -> None:
    coordinator = ThreatManagementCoordinator()
    adapter = mid_mpc_ipopt.create(
        context=FactoryContext(
            requested_algorithm="mid_mpc_ipopt",
            algorithm_seed=0,
            scenario_id="runtime-threat-authority",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
            threat_management_coordinator=coordinator,
        ),
        horizon_steps=4,
        horizon_dt_s=5.0,
        solve_period_s=5.0,
        deadline_s=20.0,
    )
    target = TrackSnapshot(
        key=TrackKey(1, 1),
        state=np.array([800.0, 0.0, -4.0, 0.0]),
        covariance=np.zeros((4, 4)),
        length_m=30.0,
        width_m=7.0,
        observed_at_s=0.0,
        generated_at_s=0.0,
        status=TrackStatus.UPDATED,
        source="test",
    )

    adapter.plan(
        0.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [target],
        dt=1.0,
        os_length=15.0,
        os_model_name="Viknes",
        os_controller_name="FLSC",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )

    snapshot = coordinator.last_snapshot
    assert snapshot is not None
    trace = adapter.get_colav_data()["planner"]
    assert trace["algorithm_details"]["solver_backend"] == "ipopt"
    assert trace["algorithm_details"]["threat_management"]["semantic_hash"] == snapshot.semantic_hash

    adapter.plan(
        5.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [target],
        dt=1.0,
        os_length=15.0,
        os_model_name="Viknes",
        os_controller_name="FLSC",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )

    assert coordinator.last_snapshot is not None
    assert coordinator.last_snapshot.provenance["accepted_plan_applied_sequence"] == 1
