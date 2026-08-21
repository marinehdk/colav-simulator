from __future__ import annotations

import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_case import (
    HistoricalAISAlgorithmBinding,
    HistoricalAISCase,
    HistoricalAISCaseBuilder,
    HistoricalAISCaseBuildRequest,
    HistoricalAISCompareBinding,
    HistoricalAISDiscoveryProfile,
    HistoricalAISEvaluationBinding,
    HistoricalAISHumanReferenceBinding,
)
from colav_simulator.historical_compare import (
    HistoricalBenchmarkComparator,
    HistoricalBenchmarkCompareRequest,
    HistoricalBenchmarkTrajectory,
)
from colav_simulator.historical_counterfactual import (
    HistoricalAISCounterfactualRunner,
    HistoricalAISCounterfactualRunRequest,
)
from colav_simulator.historical_enc import ENCRegionProfile
from colav_simulator.historical_replay import HistoricalReplayRequest
from colav_simulator.historical_serialization import semantic_hash

UTC = timezone.utc


def _case(
    tmp_path: Path,
    enc_profile: ENCRegionProfile,
    *,
    post_t0_reference: str = "7.0012,61.9994,10,180",
    human_reference_artifact_digest: str = "fixture-human-reference",
) -> HistoricalAISCase:
    source = tmp_path / "counterfactual.csv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,180,40,8\n"
        f"2026-07-01T00:00:30Z,123456789,{post_t0_reference},40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:30Z,223456789,7.0082,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    dataset = HistoricalAISDatasetReader(source).read(selection)
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
            ),
            t0_utc=datetime(2026, 7, 1, 0, 0, 20, tzinfo=UTC),
            human_reference_binding=HistoricalAISHumanReferenceBinding(
                artifact_digest=human_reference_artifact_digest,
                sample_count=1,
            ),
            algorithm_binding=HistoricalAISAlgorithmBinding("nominal", semantic_hash({})),
            evaluation_binding=HistoricalAISEvaluationBinding(
                "evaluator",
                "ccta_2023_demo-v1",
                semantic_hash({"profile_id": "ccta_2023_demo-v1"}),
            ),
            compare_binding=HistoricalAISCompareBinding(alignment_profile_digest="alignment-digest"),
        )
    )
    assert outcome.success is True
    assert outcome.case is not None
    return outcome.case


def test_counterfactual_run_spec_contains_reference_history_only_through_t0(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    case = _case(
        tmp_path,
        qualified_historical_enc_profile,
        human_reference_artifact_digest="human-reference-a",
    )
    request = HistoricalAISCounterfactualRunRequest(
        case=case,
        run_spec=RunSpec(
            scenario_id="simple_planning_example",
            algorithm_id="nominal",
            tracker_id="god",
            t_end=30.0,
            terminate_on_collision_or_grounding=False,
            output_root=str(tmp_path / "run"),
        ),
        human_reference_artifact_digest="human-reference-a",
    )

    spec = request.to_run_spec()
    reference_actor = next(
        actor for actor in spec.historical_replay["actor_set"]["actors"] if actor["mmsi"] == case.reference_mmsi
    )

    assert spec.historical_replay["mode"] == "COUNTERFACTUAL"
    assert spec.historical_replay["dataset_descriptor_digest"] == case.dataset_digest
    assert spec.historical_replay["runtime_actor_set_digest"] == spec.historical_replay["actor_set"]["semantic_digest"]
    assert spec.historical_replay["case_runtime_digest"] == case.runtime_digest
    assert (
        len(
            {
                spec.historical_replay["dataset_descriptor_digest"],
                spec.historical_replay["runtime_actor_set_digest"],
                spec.historical_replay["case_runtime_digest"],
            }
        )
        == 3
    )
    assert all(datetime.fromisoformat(sample["timestamp_utc"]) <= case.t0_utc for sample in reference_actor["samples"])
    assert "human-reference-a" not in spec.to_dict().__repr__()
    replay_request = HistoricalReplayRequest.from_dict(spec.historical_replay)
    assert replay_request.evidence.mode == "COUNTERFACTUAL"
    assert replay_request.evidence.counterfactual is True
    assert replay_request.evidence.case_digest == case.case_digest
    assert replay_request.evidence.dataset_descriptor_digest == case.dataset_digest
    assert replay_request.evidence.runtime_actor_set_digest == spec.historical_replay["runtime_actor_set_digest"]


def test_human_reference_digest_does_not_change_counterfactual_run_spec(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    first_case = _case(
        tmp_path / "first",
        qualified_historical_enc_profile,
        human_reference_artifact_digest="human-a",
    )
    second_case = _case(
        tmp_path / "second",
        qualified_historical_enc_profile,
        human_reference_artifact_digest="human-b",
    )
    base = RunSpec(
        scenario_id="simple_planning_example",
        algorithm_id="nominal",
        tracker_id="god",
        t_end=30.0,
        output_root=str(tmp_path / "run"),
    )
    first = HistoricalAISCounterfactualRunRequest(first_case, base).to_run_spec()
    second = HistoricalAISCounterfactualRunRequest(second_case, base).to_run_spec()

    assert first.to_dict() == second.to_dict()


def test_counterfactual_rejects_human_reference_not_frozen_in_case(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    case = _case(
        tmp_path,
        qualified_historical_enc_profile,
        human_reference_artifact_digest="human-a",
    )

    with pytest.raises(ValueError, match="frozen Human Reference"):
        HistoricalAISCounterfactualRunRequest(
            case,
            RunSpec(scenario_id="simple_planning_example"),
            "human-b",
        )


def test_post_t0_human_reference_changes_compare_only_not_runtime_or_commands(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    base_case = _case(tmp_path, qualified_historical_enc_profile)
    samples = base_case.reference_actor.samples
    first_human = HistoricalBenchmarkTrajectory(
        timestamps_s=tuple(sample.time_s for sample in samples),
        positions_xy=tuple(sample.state_vxvy[:2] for sample in samples),
        courses_rad=tuple(math.atan2(sample.state_vxvy[3], sample.state_vxvy[2]) for sample in samples),
        speeds_mps=tuple(math.hypot(sample.state_vxvy[2], sample.state_vxvy[3]) for sample in samples),
        source="HUMAN_REFERENCE",
    )
    changed_positions = (
        *first_human.positions_xy[:-1],
        (first_human.positions_xy[-1][0] + 500.0, first_human.positions_xy[-1][1]),
    )
    second_human = replace(first_human, positions_xy=changed_positions, trajectory_digest="")
    first_case = replace(
        base_case,
        human_reference_binding=HistoricalAISHumanReferenceBinding(first_human.trajectory_digest, len(samples)),
        build_digest="",
        runtime_digest="",
    )
    second_case = replace(
        base_case,
        human_reference_binding=HistoricalAISHumanReferenceBinding(second_human.trajectory_digest, len(samples)),
        build_digest="",
        runtime_digest="",
    )
    base = RunSpec(
        scenario_id="simple_planning_example",
        algorithm_id="nominal",
        tracker_id="god",
        t_end=30.0,
        terminate_on_collision_or_grounding=False,
        output_root=str(tmp_path / "runs"),
    )
    first_request = HistoricalAISCounterfactualRunRequest(first_case, base)
    second_request = HistoricalAISCounterfactualRunRequest(second_case, base)

    assert first_case.build_digest != second_case.build_digest
    assert first_case.runtime_digest == second_case.runtime_digest
    assert first_request.run_spec_digest == second_request.run_spec_digest
    assert first_request.to_run_spec().to_dict() == second_request.to_run_spec().to_dict()

    first = HistoricalAISCounterfactualRunner().run(first_request)
    second = HistoricalAISCounterfactualRunner().run(second_request)
    assert first.success is True and second.success is True
    assert first.result is not None and second.result is not None

    def runtime_oracle(result: object) -> tuple[object, object, object]:
        frames = result.session.frames
        canonical = lambda value: json.dumps(  # noqa: E731
            value,
            sort_keys=True,
            default=lambda item: item.tolist() if hasattr(item, "tolist") else str(item),
        )
        planner_inputs = tuple(canonical(frame["Ship0"].get("do_estimates")) for frame in frames)
        commands = tuple(canonical(frame["Ship0"].get("planner", {}).get("selected_command")) for frame in frames)
        trajectory = tuple(tuple(frame["Ship0"]["csog_state"]) for frame in frames)
        return planner_inputs, commands, trajectory

    assert runtime_oracle(first.result) == runtime_oracle(second.result)
    assert first.result.manifest.trajectory_hash == second.result.manifest.trajectory_hash
    assert first.result.evaluation.to_dict() == second.result.evaluation.to_dict()
    first_threat = first.result.session.threat_management_coordinator.last_snapshot
    second_threat = second.result.session.threat_management_coordinator.last_snapshot
    assert (first_threat is None) is (second_threat is None)
    if first_threat is not None and second_threat is not None:
        assert first_threat.semantic_hash == second_threat.semantic_hash

    first_compare = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest.from_counterfactual_run(
            first_case,
            first.result,
            human_reference=first_human,
        )
    )
    second_compare = HistoricalBenchmarkComparator().compare(
        HistoricalBenchmarkCompareRequest.from_counterfactual_run(
            second_case,
            second.result,
            human_reference=second_human,
        )
    )
    assert first_compare.compare_digest != second_compare.compare_digest


def test_counterfactual_session_handoffs_at_t0_and_keeps_targets_on_history(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    case = _case(tmp_path, qualified_historical_enc_profile)
    request = HistoricalAISCounterfactualRunRequest(
        case=case,
        run_spec=RunSpec(
            scenario_id="simple_planning_example",
            algorithm_id="nominal",
            tracker_id="god",
            t_end=30.0,
            terminate_on_collision_or_grounding=False,
            output_root=str(tmp_path / "run"),
        ),
    )
    prepared = HistoricalAISCounterfactualRunner().prepare(request)

    snapshots = {}
    for _ in range(21):
        snapshot = prepared.session.step_once()
        if snapshot.sim_time in {19.0, 20.0}:
            snapshots[snapshot.sim_time] = snapshot.payload

    assert "historical_counterfactual" not in snapshots[19.0]["Ship0"]
    assert snapshots[20.0]["Ship0"]["historical_counterfactual"]["mode"] == "COUNTERFACTUAL_REALIZED"
    assert snapshots[20.0]["Ship0"]["historical_counterfactual"]["human_reference_in_runtime"] is False
    assert snapshots[20.0]["Ship1"]["historical_actor_truth"]["sample_kind"] in {"observed", "interpolated"}
    state_t0 = snapshots[20.0]["Ship0"]["csog_state"]
    historical_t0 = case.reference_actor.sample_at(case.t0_candidate.time_s)
    assert historical_t0 is not None
    assert state_t0[0] == pytest.approx(historical_t0.state_vxvy[0], abs=1e-6)
    assert state_t0[1] == pytest.approx(historical_t0.state_vxvy[1], abs=1e-6)
    assert state_t0[2] == pytest.approx(math.hypot(historical_t0.state_vxvy[2], historical_t0.state_vxvy[3]), abs=1e-6)


def test_counterfactual_reference_remains_active_after_t0(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    case = _case(tmp_path, qualified_historical_enc_profile)
    request = HistoricalAISCounterfactualRunRequest(
        case=case,
        run_spec=RunSpec(
            scenario_id="simple_planning_example",
            algorithm_id="nominal",
            tracker_id="god",
            t_end=30.0,
            terminate_on_collision_or_grounding=False,
            output_root=str(tmp_path / "run"),
        ),
    )
    prepared = HistoricalAISCounterfactualRunner().prepare(request)

    snapshots = []
    for _ in range(26):
        snapshots.append(prepared.session.step_once())

    post_t0 = [snapshot.payload["Ship0"] for snapshot in snapshots if snapshot.sim_time > 20.0]
    assert post_t0
    assert all(item["historical_counterfactual"]["mode"] == "COUNTERFACTUAL_REALIZED" for item in post_t0)


def test_counterfactual_run_seals_typed_mode_and_compare_only_human_reference(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    case = _case(
        tmp_path,
        qualified_historical_enc_profile,
        human_reference_artifact_digest="human-reference-digest",
    )
    request = HistoricalAISCounterfactualRunRequest(
        case=case,
        run_spec=RunSpec(
            scenario_id="simple_planning_example",
            algorithm_id="nominal",
            tracker_id="god",
            t_end=30.0,
            terminate_on_collision_or_grounding=False,
            output_root=str(tmp_path / "run"),
        ),
        human_reference_artifact_digest="human-reference-digest",
    )

    outcome = HistoricalAISCounterfactualRunner().run(request)

    assert outcome.success is True
    assert outcome.human_reference_status == "AVAILABLE"
    assert outcome.result is not None
    assert outcome.result.manifest.historical_execution_mode == "COUNTERFACTUAL"
    assert outcome.result.manifest.historical_reference_artifact_digest == "human-reference-digest"
    assert "human-reference-digest" not in outcome.result.manifest.spec.__repr__()
