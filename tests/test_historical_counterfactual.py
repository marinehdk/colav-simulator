from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import pytest

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_case import (
    HistoricalAISCase,
    HistoricalAISCaseBuilder,
    HistoricalAISCaseBuildRequest,
    HistoricalAISDiscoveryProfile,
)
from colav_simulator.historical_counterfactual import (
    HistoricalAISCounterfactualRunner,
    HistoricalAISCounterfactualRunRequest,
)
from colav_simulator.historical_enc import ENCRegionProfile
from colav_simulator.historical_replay import HistoricalReplayRequest


def _case(tmp_path: Path, enc_profile: ENCRegionProfile) -> HistoricalAISCase:
    source = tmp_path / "counterfactual.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,180,40,8\n"
        "2026-07-01T00:00:30Z,123456789,7.0012,61.9994,10,180,40,8\n"
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
        )
    )
    assert outcome.success is True
    assert outcome.case is not None
    return outcome.case


def test_counterfactual_run_spec_contains_reference_history_only_through_t0(
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
        human_reference_artifact_digest="human-reference-a",
    )

    spec = request.to_run_spec()
    reference_actor = next(
        actor for actor in spec.historical_replay["actor_set"]["actors"] if actor["mmsi"] == case.reference_mmsi
    )

    assert spec.historical_replay["mode"] == "COUNTERFACTUAL"
    assert all(datetime.fromisoformat(sample["timestamp_utc"]) <= case.t0_utc for sample in reference_actor["samples"])
    assert "human-reference-a" not in spec.to_dict().__repr__()
    replay_request = HistoricalReplayRequest.from_dict(spec.historical_replay)
    assert replay_request.evidence.mode == "COUNTERFACTUAL"
    assert replay_request.evidence.counterfactual is True
    assert replay_request.evidence.case_digest == case.case_digest


def test_human_reference_digest_does_not_change_counterfactual_run_spec(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    case = _case(tmp_path, qualified_historical_enc_profile)
    base = RunSpec(
        scenario_id="simple_planning_example",
        algorithm_id="nominal",
        tracker_id="god",
        t_end=30.0,
        output_root=str(tmp_path / "run"),
    )
    first = HistoricalAISCounterfactualRunRequest(case, base, "human-a").to_run_spec()
    second = HistoricalAISCounterfactualRunRequest(case, base, "human-b").to_run_spec()

    assert first.to_dict() == second.to_dict()


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
        human_reference_artifact_digest="human-reference-digest",
    )

    outcome = HistoricalAISCounterfactualRunner().run(request)

    assert outcome.success is True
    assert outcome.human_reference_status == "AVAILABLE"
    assert outcome.result is not None
    assert outcome.result.manifest.historical_execution_mode == "COUNTERFACTUAL"
    assert outcome.result.manifest.historical_reference_artifact_digest == "human-reference-digest"
    assert "human-reference-digest" not in outcome.result.manifest.spec.__repr__()
