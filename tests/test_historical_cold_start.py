from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import DeadlineMode, FactoryContext
from colav_simulator.core.tracking.trackers import TrackKey, TrackSnapshot, TrackStatus
from colav_simulator.experiment.persistence import BoundedArtifactSink, EvidenceWriter
from colav_simulator.experiment.runner import _scenario_target_count
from colav_simulator.integrations import IntegrationRegistry


def test_counterfactual_actor_set_counts_targets_for_realtime_prewarm() -> None:
    spec = SimpleNamespace(
        scenario_override=None,
        historical_replay={
            "ownship_actor_id": 1,
            "actor_set": {
                "actors": [
                    {"actor_id": 0},
                    {"actor_id": 1},
                    {"actor_id": 2},
                ]
            },
        },
    )

    assert _scenario_target_count(spec) == 2


def test_first_multitarget_plan_uses_prepared_graph_and_commits_under_deadline(tmp_path) -> None:
    spec = SimpleNamespace(
        scenario_override=None,
        historical_replay={
            "ownship_actor_id": 0,
            "actor_set": {"actors": [{"actor_id": 0}, {"actor_id": 1}, {"actor_id": 2}]},
        },
    )
    target_count = _scenario_target_count(spec)
    writer = EvidenceWriter(tmp_path / "run")
    sink = BoundedArtifactSink(writer)
    adapter = IntegrationRegistry().build_algorithm(
        "mid_mpc_ipopt",
        {
            "factory": "colav_simulator.integrations.mid_mpc_ipopt:create",
            "kwargs": {
                "horizon_steps": 4,
                "horizon_dt_s": 5.0,
                "solve_period_s": 5.0,
                "deadline_s": 20.0,
            },
        },
        factory_context=FactoryContext(
            "mid_mpc_ipopt",
            0,
            scenario_id="paper_ccta2023_multiship",
            tracker_id="god",
            scenario_target_count=target_count,
            deadline_mode=DeadlineMode.ENFORCE,
            artifact_sink=sink,
        ),
    )
    snapshots = [
        TrackSnapshot(
            key=TrackKey(target_id, 1),
            state=state,
            covariance=np.eye(4),
            length_m=40.0,
            width_m=8.0,
            observed_at_s=0.0,
            generated_at_s=0.0,
            status=TrackStatus.UPDATED,
            source="cold-start-test",
        )
        for target_id, state in (
            (11, np.array([3_000.0, 0.0, -4.0, 0.0])),
            (12, np.array([1_000.0, -1_000.0, 0.0, 4.0])),
        )
    ]

    adapter.plan(
        0.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        snapshots,
        dt=1.0,
        os_length=15.0,
        os_model_name="KinematicCSOG",
        os_controller_name="PassThroughCS",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )
    trace = adapter.get_colav_data()["planner"]
    sink.close(timeout_s=2.0)

    assert trace["algorithm_details"]["graph_cache_hit"] is True
    assert trace["algorithm_details"]["graph_build_elapsed_ms"] == 0.0
    assert trace["algorithm_details"]["strict_total_deadline"] is True
    assert trace["algorithm_details"]["commit_elapsed_ms"] < 20_000.0
    assert adapter.get_diagnostics().fallback_used is False
