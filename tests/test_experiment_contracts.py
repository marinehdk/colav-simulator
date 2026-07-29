from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus, validate_plan
from colav_simulator.experiment import (
    ExperimentRunError,
    ExperimentRunner,
    RunManifest,
    RunOutcome,
    RunSpec,
    SeedBundle,
    SessionState,
)
from colav_simulator.experiment.persistence import EvidenceWriter, jsonable


def test_seed_bundle_is_stable_and_separated() -> None:
    first = SeedBundle.derive(42)
    second = SeedBundle.derive(42)
    assert first == second
    assert len({first.scenario, first.sensor, first.tracker, first.algorithm}) == 4


def test_run_spec_validation_and_round_trip() -> None:
    spec = RunSpec("head_on", algorithm_id="SBMPC", tracker_id="KF", seed=7, dt=0.5)
    assert RunSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()
    assert spec.algorithm_id == "sbmpc"
    with pytest.raises(ValueError):
        RunSpec("", seed=0)
    with pytest.raises(ValueError):
        RunSpec("head_on", dt=0.0)


def test_icolav_plan_contract() -> None:
    valid = np.zeros((9, 2))
    assert validate_plan(valid) is not None
    with pytest.raises(ColavExecutionError) as shape_error:
        validate_plan(np.zeros((8, 2)))
    assert shape_error.value.status == PlanStatus.NUMERICAL_FAILURE
    with pytest.raises(ColavExecutionError):
        validate_plan(np.full((9, 1), np.nan))


def test_jsonable_rejects_nonstandard_nonfinite_numbers() -> None:
    assert jsonable({"infinite": float("inf"), "missing": np.nan}) == {
        "infinite": None,
        "missing": None,
    }


def test_runner_writes_complete_evidence_bundle(tmp_path: Path) -> None:
    runner = ExperimentRunner()
    result = runner.run(
        RunSpec(
            "paper_ccta2023_multiship",
            seed=3,
            t_end=0.2,
            output_root=str(tmp_path),
        )
    )
    assert result.manifest.state == SessionState.FINISHED
    assert result.manifest.fallback_used is False
    expected = {
        "manifest.json",
        "episode.json",
        "trajectory.parquet",
        "events.jsonl",
        "evaluation.json",
        "report.html",
    }
    assert expected.issubset({path.name for path in result.run_dir.iterdir()})
    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    assert manifest["episode_hash"]
    assert manifest["spec_hash"]
    assert manifest["simulation_config_hash"]
    assert manifest["trajectory_hash"]
    assert manifest["evaluator_profile_id"] == "ccta_2023_demo-v1"
    assert manifest["evaluator_profile_hash"]
    assert manifest["formula_set_id"] == "ocean-engineering-2023-v1"
    assert manifest["evaluation_collision_oracle_id"] == "c2a-rect2d-v1"
    assert manifest["evaluation_schema_version"] == "2.0"
    assert manifest["scenario_provenance"]["reconstructed"] is True
    inspection = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, pyarrow.parquet as pq, sys; "
                "table=pq.read_table(sys.argv[1]); "
                "print(json.dumps({'columns': table.column_names, 'rows': table.num_rows}))"
            ),
            str(result.run_dir / "trajectory.parquet"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    trajectory = json.loads(inspection.stdout)
    assert {"sim_time", "ship_id", "north_m", "east_m", "tracks_json", "colav_json"}.issubset(trajectory["columns"])
    assert trajectory["rows"] == 8
    replay = runner.replay(result.run_dir, tmp_path / "replays")
    assert replay.manifest.replay_verified is True
    assert replay.manifest.episode_hash == result.manifest.episode_hash
    assert replay.manifest.trajectory_hash == result.manifest.trajectory_hash


def test_pause_does_not_advance_time(tmp_path: Path) -> None:
    prepared = ExperimentRunner().prepare(
        RunSpec(
            "paper_ccta2023_multiship",
            t_end=0.2,
            output_root=str(tmp_path),
        )
    )
    prepared.session.start()
    prepared.session.pause()
    time_before = prepared.session.simulator.t
    assert prepared.session.state == SessionState.PAUSED
    assert prepared.session.simulator.t == time_before
    prepared.session.step_once()
    assert prepared.session.state == SessionState.PAUSED
    assert prepared.session.simulator.t > time_before


def test_failed_algorithm_run_keeps_complete_evidence_bundle(tmp_path: Path) -> None:
    with pytest.raises(ExperimentRunError) as failure:
        ExperimentRunner().run(
            RunSpec(
                "paper_ccta2023_multiship",
                algorithm_id="missing_algorithm",
                t_end=0.2,
                output_root=str(tmp_path),
            )
        )
    manifest = failure.value.manifest
    assert manifest.state == SessionState.FAILED
    assert manifest.failure_status == PlanStatus.INVALID_INPUT
    assert {
        "manifest.json",
        "episode.json",
        "trajectory.parquet",
        "events.jsonl",
        "evaluation.json",
        "report.html",
    }.issubset(path.name for path in failure.value.run_dir.iterdir())


def test_deadline_off_marks_manifest_diagnostic_only() -> None:
    spec = RunSpec("head_on", deadline_mode="off")
    manifest = RunManifest.create(spec)

    assert spec.deadline_mode == "OFF"
    assert manifest.diagnostic_only is True
    assert manifest.diagnostic_only_reasons == ["deadline_mode=OFF"]


def test_dependency_failure_persists_skipped_not_evaluated_evidence(tmp_path: Path) -> None:
    manifest = RunManifest.create(RunSpec("head_on", algorithm_id="paper_mpc"))
    writer = EvidenceWriter(tmp_path / manifest.run_id)

    ExperimentRunner.persist_failure(
        manifest,
        writer,
        ColavExecutionError(
            PlanStatus.DEPENDENCY_UNAVAILABLE,
            "solver package unavailable",
        ),
        [],
    )

    stored_manifest = json.loads((writer.run_dir / "manifest.json").read_text(encoding="utf-8"))
    evaluation = json.loads((writer.run_dir / "evaluation.json").read_text(encoding="utf-8"))
    event = json.loads((writer.run_dir / "events.jsonl").read_text(encoding="utf-8"))
    assert manifest.execution_outcome == RunOutcome.SKIPPED
    assert stored_manifest["execution_outcome"] == "SKIPPED"
    assert stored_manifest["reproduction_status"] == "not_evaluated"
    assert evaluation["evaluation_status"] == "NOT_EVALUATED"
    assert evaluation["hard_gate"]["outcome"] == "FAIL"
    assert evaluation["failure_status"] == PlanStatus.DEPENDENCY_UNAVAILABLE
    assert event["type"] == "run_skipped"
