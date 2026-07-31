from types import SimpleNamespace

from colav_simulator.experiment.runner import _run_metrics


def test_run_metrics_separate_ship0_and_global_world_events() -> None:
    evaluation = SimpleNamespace(
        pair_results=[
            SimpleNamespace(
                ownship_id=0,
                target_id=1,
                minimum_distance_m=100.0,
                collision=False,
                collision_toc_s=None,
                collision_oracle_id="c2a",
            ),
            SimpleNamespace(
                ownship_id=1,
                target_id=2,
                minimum_distance_m=0.0,
                collision=True,
                collision_toc_s=12.0,
                collision_oracle_id="c2a",
            ),
        ],
        vessel_results=[
            SimpleNamespace(vessel_id=0, grounded=False, grounding_distance_m=50.0),
            SimpleNamespace(vessel_id=1, grounded=False, grounding_distance_m=60.0),
            SimpleNamespace(vessel_id=2, grounded=True, grounding_distance_m=0.0),
        ],
    )
    session = SimpleNamespace(
        ship_info={
            "Ship0": {"id": 0, "length": 12.0, "width": 4.0},
            "Ship1": {"id": 1, "length": 12.0, "width": 4.0},
            "Ship2": {"id": 2, "length": 12.0, "width": 4.0},
        },
        ship_list=[object(), object(), object()],
        frames=[
            {
                "Ship0": {
                    "active": True,
                    "colav": {
                        "planner": {
                            "solver_executed": True,
                            "sim_time": 5.0,
                            "algorithm_details": {
                                "maneuver_phase": "AVOID",
                                "selected_heading_increment_rad": 0.1,
                                "cross_track_error_m": 25.0,
                                "selected_speed_scale": 0.8,
                                "encounter_records": [{"encounter": "head_on"}],
                            },
                        }
                    },
                },
                "Ship1": {"active": True},
                "Ship2": {"active": True},
            },
            {
                "Ship0": {
                    "active": True,
                    "colav": {
                        "planner": {
                            "solver_executed": True,
                            "sim_time": 10.0,
                            "algorithm_details": {
                                "maneuver_phase": "RETURN",
                                "selected_heading_increment_rad": -0.1,
                                "cross_track_error_m": 5.0,
                                "selected_speed_scale": 1.0,
                                "encounter_records": [],
                            },
                        }
                    },
                },
                "Ship1": {"active": True},
                "Ship2": {"active": False},
            },
        ],
        step_times_ms=[2.0, 4.0, 8.0],
    )

    metrics = _run_metrics(evaluation, session, fallback_used=False)

    assert metrics["ship0_safety"]["collision_count"] == 0
    assert metrics["ship0_safety"]["grounded"] is False
    assert metrics["global_world_events"]["collision_count"] == 1
    assert metrics["global_world_events"]["grounding_count"] == 1
    assert metrics["traffic_load"]["configured_ship_count"] == 3
    assert metrics["traffic_load"]["maximum_active_ship_count"] == 3
    assert metrics["traffic_load"]["maximum_risk_target_count"] == 1
    assert metrics["traffic_load"]["step_time_ms_p95"] > metrics["traffic_load"]["step_time_ms_p50"]
    assert metrics["maneuver_quality_observations"]["steering_reversal_count"] == 1
    assert metrics["maneuver_quality_observations"]["phase_transitions"][-1]["phase"] == "RETURN"
