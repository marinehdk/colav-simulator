from __future__ import annotations

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import DeadlineMode, FactoryContext
from colav_simulator.core.colav.threat_assessment import (
    ConflictEdgeType,
    OwnshipThreatPrediction,
    PredictionBasis,
    ShipDomainProfile,
)
from colav_simulator.core.colav.threat_management import AcceptedPlanReceipt, ThreatManagementCoordinator
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
    assert snapshot.vectors[0].prediction_basis is PredictionBasis.CONSTANT_VELOCITY
    assert "BASELINE_UNAVAILABLE" not in {reason.value for reason in snapshot.conflict_graph.unavailable_reasons}
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
    receipt = coordinator.last_snapshot.accepted_plan_receipt
    assert receipt is not None
    assert receipt.accepted_prediction is not None
    assert receipt.accepted_prediction.coordinate_frame == "ENU"
    assert receipt.accepted_prediction.prediction_hash == receipt.prediction_hash
    assert receipt.accepted_prediction.evidence_semantic_hash
    assert receipt.evidence_semantic_hash == receipt.accepted_prediction.evidence_semantic_hash
    assert receipt.domain_profile_hash == coordinator.domain_profile.profile_hash


def test_mid_mpc_runtime_publishes_plan_induced_conflict_from_next_cycle_receipt() -> None:
    profile = ShipDomainProfile(
        profile_id="runtime-qualified-domain",
        version="1",
        fore_m=300.0,
        aft_m=100.0,
        port_m=120.0,
        starboard_m=180.0,
        parameter_source="runtime-test-fixture",
        assumptions=("engineering-envelope-only",),
    )
    coordinator = ThreatManagementCoordinator(domain_profile=profile)
    adapter = mid_mpc_ipopt.create(
        context=FactoryContext(
            requested_algorithm="mid_mpc_ipopt",
            algorithm_seed=0,
            scenario_id="route",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
            threat_management_coordinator=coordinator,
        ),
        horizon_steps=4,
        horizon_dt_s=5.0,
        solve_period_s=5.0,
        deadline_s=20.0,
    )
    driver_key = TrackKey(1, 1)
    affected_key = TrackKey(2, 1)

    def tracked(key: TrackKey, state: np.ndarray, time_s: float) -> TrackSnapshot:
        return TrackSnapshot(
            key=key,
            state=state,
            covariance=np.zeros((4, 4)),
            length_m=30.0,
            width_m=7.0,
            observed_at_s=time_s,
            generated_at_s=time_s,
            status=TrackStatus.UPDATED,
            source="test",
        )

    waypoints = np.array([[0.0, 500.0], [0.0, 0.0]])
    speed_plan = np.array([4.0, 4.0])
    ownship = np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0])
    common_kwargs = {
        "dt": 1.0,
        "os_length": 15.0,
        "os_model_name": "Viknes",
        "os_controller_name": "FLSC",
        "os_max_turn_rate_radps": np.deg2rad(3.0),
    }
    adapter.plan(
        0.0,
        waypoints,
        speed_plan,
        ownship,
        [],
        **common_kwargs,
    )
    accepted_prediction = OwnshipThreatPrediction(
        times_s=np.array([0.0, 5.0, 10.0, 15.0, 20.0]),
        states_enu=np.array(
            [
                [0.0, 0.0, 20.0, 30.0],
                [100.0, 150.0, 20.0, 30.0],
                [200.0, 300.0, 20.0, 30.0],
                [300.0, 450.0, 20.0, 30.0],
                [400.0, 600.0, 20.0, 30.0],
            ]
        ),
        basis="ACCEPTED_PLAN",
        source="l4-receipt-fixture",
        target_keys=(driver_key, affected_key),
        reference_time_s=0.0,
        evidence_semantic_hash="runtime-accepted-evidence",
    )
    coordinator.publish_accepted_plan(
        AcceptedPlanReceipt(
            receipt_hash="accepted-plan-conflict",
            accepted_sequence=0,
            accepted_at_s=0.0,
            valid_until_s=30.0,
            accepted_prediction=accepted_prediction,
            plan_target=driver_key,
            target_keys=(driver_key, affected_key),
            prediction_hash=accepted_prediction.semantic_hash,
            acceptance_hash="l4-accepted",
            domain_profile_hash=profile.profile_hash,
            evidence_semantic_hash="runtime-accepted-evidence",
        )
    )
    adapter.plan(
        5.0,
        waypoints,
        speed_plan,
        ownship,
        [
            tracked(driver_key, np.array([960.0, 0.0, -4.0, 0.0]), 5.0),
            tracked(affected_key, np.array([400.0, 600.0, 0.0, 0.0]), 5.0),
        ],
        **common_kwargs,
    )

    graph = coordinator.last_snapshot.conflict_graph
    assert graph.unavailable_reasons == (), tuple(reason.value for reason in graph.unavailable_reasons)
    assert any(edge.edge_type is ConflictEdgeType.PLAN_INDUCED_CONFLICT for edge in graph.edges), graph.to_dict()
