from __future__ import annotations

from types import SimpleNamespace

from colav_simulator.historical_compare import (
    HistoricalBenchmarkComparator,
    HistoricalBenchmarkCompareRequest,
    HistoricalBenchmarkTrajectory,
    HistoricalCompareStatus,
)


def _trajectory(points: tuple[tuple[float, float], ...]) -> HistoricalBenchmarkTrajectory:
    return HistoricalBenchmarkTrajectory(
        timestamps_s=tuple(float(index) for index in range(len(points))),
        positions_xy=points,
        courses_rad=tuple(0.0 for _ in points),
        speeds_mps=tuple(1.0 for _ in points),
    )


def test_compare_returns_typed_incomplete_when_human_and_evaluator_are_missing() -> None:
    outcome = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest(
            case_digest="case-a",
            dataset_digest="dataset-a",
            t0_s=1.0,
            counterfactual=HistoricalBenchmarkTrajectory(
                timestamps_s=(0.0, 1.0, 2.0),
                positions_xy=((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)),
            ),
            human_reference=None,
            evaluation=None,
        )
    )

    assert outcome.status is HistoricalCompareStatus.INCOMPLETE
    assert outcome.domains.human_similarity.status == "NOT_AVAILABLE"
    assert outcome.domains.safety.status == "NOT_AVAILABLE"
    assert outcome.domains.colreg.status == "NOT_AVAILABLE"
    assert outcome.to_dict()["lineage"]["case_digest"] == "case-a"


def test_compare_keeps_independent_fail_verdict_when_human_trajectory_is_similar() -> None:
    evaluation = SimpleNamespace(
        hard_gate=SimpleNamespace(outcome="FAIL", checks=[]),
        pair_results=[],
        vessel_results=[],
        aggregate={"minimum_distance_m": 4.0, "collision_count": 1, "grounding_count": 0},
        evaluator_profile_id="test-evaluator",
        evaluator_profile_hash="evaluator-hash",
        evaluator_id="evaluator",
        schema_version="2.0",
    )
    human = _trajectory(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)))
    counterfactual = _trajectory(((0.0, 0.0), (1.0, 0.1), (2.0, -0.1), (3.0, 0.0)))

    outcome = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest(
            case_digest="case-b",
            dataset_digest="dataset-b",
            t0_s=1.0,
            counterfactual=counterfactual,
            human_reference=human,
            human_reference_artifact_digest=human.trajectory_digest,
            case_human_reference_artifact_digest=human.trajectory_digest,
            evaluation=evaluation,
        )
    )

    assert outcome.status is HistoricalCompareStatus.COMPLETE
    assert outcome.domains.safety.independent_verdict == "FAIL"
    assert outcome.domains.colreg.independent_verdict == "FAIL"
    assert outcome.domains.human_similarity.advisory is True
    assert outcome.domains.human_similarity.position_rmse_m is not None
    assert outcome.domains.human_similarity.position_rmse_m < 0.1
    assert outcome.overall_assurance_verdict == "FAIL"


def test_compare_keeps_independent_pass_verdict_when_human_trajectory_is_dissimilar() -> None:
    evaluation = SimpleNamespace(
        hard_gate=SimpleNamespace(outcome="PASS", checks=[]),
        pair_results=[],
        vessel_results=[],
        aggregate={"minimum_distance_m": 400.0, "collision_count": 0, "grounding_count": 0},
        evaluator_profile_id="test-evaluator",
        evaluator_profile_hash="evaluator-hash",
        evaluator_id="evaluator",
        schema_version="2.0",
    )
    human = _trajectory(((0.0, 0.0), (1.0, 10.0), (2.0, 20.0), (3.0, 30.0)))
    outcome = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest(
            case_digest="case-c",
            dataset_digest="dataset-c",
            t0_s=1.0,
            counterfactual=_trajectory(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))),
            human_reference=human,
            human_reference_artifact_digest=human.trajectory_digest,
            case_human_reference_artifact_digest=human.trajectory_digest,
            evaluation=evaluation,
        )
    )

    assert outcome.status is HistoricalCompareStatus.COMPLETE
    assert outcome.overall_assurance_verdict == "PASS"
    assert outcome.domains.safety.independent_verdict == "PASS"
    assert outcome.domains.colreg.independent_verdict == "PASS"
    assert outcome.domains.human_similarity.position_rmse_m is not None
    assert outcome.domains.human_similarity.position_rmse_m > 10.0


def test_compare_marks_absolute_time_coverage_gap_incomplete_without_backfill() -> None:
    human = _trajectory(((0.0, 0.0), (1.0, 0.0)))
    counterfactual = HistoricalBenchmarkTrajectory(
        timestamps_s=(10.0, 11.0),
        positions_xy=((0.0, 0.0), (1.0, 0.0)),
    )
    outcome = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest(
            case_digest="case-gap",
            dataset_digest="dataset-gap",
            t0_s=0.0,
            counterfactual=counterfactual,
            human_reference=human,
            human_reference_artifact_digest=human.trajectory_digest,
            case_human_reference_artifact_digest=human.trajectory_digest,
            evaluation=None,
        )
    )

    assert outcome.status is HistoricalCompareStatus.INCOMPLETE
    assert outcome.domains.human_similarity.status == "INCOMPLETE"
    assert outcome.domains.human_similarity.unavailable_reason == "INSUFFICIENT_ABSOLUTE_TIME_OVERLAP"


def test_compare_digest_is_deterministic_for_same_lineage_and_metrics() -> None:
    human = _trajectory(((0.0, 0.0), (1.0, 0.5), (2.0, 0.0)))
    request = HistoricalBenchmarkCompareRequest(
        case_digest="case-deterministic",
        dataset_digest="dataset-deterministic",
        t0_s=1.0,
        counterfactual=_trajectory(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))),
        human_reference=human,
        human_reference_artifact_digest=human.trajectory_digest,
        case_human_reference_artifact_digest=human.trajectory_digest,
        evaluation=None,
    )

    first = HistoricalBenchmarkComparator().compare(request)
    second = HistoricalBenchmarkComparator().compare(request)

    assert first.compare_digest == second.compare_digest
    assert first.to_dict() == second.to_dict()


def test_compare_fails_closed_when_human_artifact_differs_from_case_binding() -> None:
    human = _trajectory(((0.0, 0.0), (1.0, 0.5), (2.0, 0.0)))
    outcome = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest(
            case_digest="case-mismatch",
            dataset_digest="dataset-mismatch",
            runtime_actor_set_digest="runtime-actors-mismatch",
            t0_s=1.0,
            counterfactual=_trajectory(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))),
            human_reference=human,
            human_reference_artifact_digest=human.trajectory_digest,
            case_human_reference_artifact_digest="different-human-artifact",
            evaluation=None,
        )
    )

    assert outcome.status is HistoricalCompareStatus.INVALID_REQUEST
    assert outcome.message == "HUMAN_REFERENCE_BINDING_MISMATCH"


def test_compare_fails_closed_when_run_and_case_lineage_disagree() -> None:
    outcome = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest(
            case_digest="case-a",
            dataset_digest="dataset-a",
            runtime_actor_set_digest="runtime-actors-a",
            run_dataset_descriptor_digest="dataset-a",
            run_runtime_actor_set_digest="runtime-actors-a",
            run_case_runtime_digest="case-b",
            t0_s=1.0,
            counterfactual=_trajectory(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))),
            human_reference=None,
            evaluation=None,
        )
    )

    assert outcome.status is HistoricalCompareStatus.INVALID_REQUEST
    assert outcome.message == "CASE_LINEAGE_MISMATCH"


def test_trajectory_session_projection_keeps_absolute_timestamps_and_kinematics() -> None:
    trajectory = HistoricalBenchmarkTrajectory.from_session_frames(
        [
            {"Ship0": {"timestamp": 0.0, "csog_state": [10.0, 20.0, 3.0, 0.1]}},
            {"Ship0": {"timestamp": 1.0, "csog_state": [13.0, 20.0, 3.0, 0.1]}},
        ],
        source="COUNTERFACTUAL_REALIZED",
    )

    assert trajectory.timestamps_s == (0.0, 1.0)
    assert trajectory.positions_xy == ((10.0, 20.0), (13.0, 20.0))
    assert trajectory.courses_rad == (0.1, 0.1)
    assert trajectory.speeds_mps == (3.0, 3.0)
