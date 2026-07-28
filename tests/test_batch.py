from __future__ import annotations

import json
from pathlib import Path

from colav_simulator.core.colav.diagnostics import PlanStatus
from colav_simulator.experiment import ExperimentRunError, RunManifest, RunSpec, SessionState
from colav_simulator.experiment.batch import BatchRunner
from colav_simulator.experiment.contracts import RunOutcome


class FailingRunner:
    def run(self, spec: RunSpec) -> None:
        manifest = RunManifest.create(spec)
        manifest.state = SessionState.FAILED
        manifest.failure_status = PlanStatus.DEPENDENCY_UNAVAILABLE
        manifest.failure_reason = "test dependency unavailable"
        run_dir = Path(spec.output_root) / manifest.run_id
        run_dir.mkdir(parents=True)
        raise ExperimentRunError(manifest, run_dir)


class SkippingRunner:
    def run(self, spec: RunSpec) -> None:
        manifest = RunManifest.create(spec)
        manifest.state = SessionState.FAILED
        manifest.execution_outcome = RunOutcome.SKIPPED
        manifest.failure_status = PlanStatus.DEPENDENCY_UNAVAILABLE
        manifest.failure_reason = "test dependency unavailable"
        run_dir = Path(spec.output_root) / manifest.run_id
        run_dir.mkdir(parents=True)
        raise ExperimentRunError(manifest, run_dir)


def test_default_matrix_has_every_scenario_and_thirty_seeds() -> None:
    specs = BatchRunner.default_specs(["nominal"])
    assert len(specs) == 30 * 30
    assert {spec.seed for spec in specs} == set(range(30))
    assert len({spec.scenario_id for spec in specs}) == 30


def test_batch_keeps_failed_runs_in_all_reports(tmp_path: Path) -> None:
    batch_dir = BatchRunner(FailingRunner()).run(
        [RunSpec("head_on", algorithm_id="rlmpc", seed=4)],
        tmp_path,
    )
    records = json.loads((batch_dir / "records.json").read_text(encoding="utf-8"))
    summary = json.loads((batch_dir / "summary.json").read_text(encoding="utf-8"))
    failures = json.loads((batch_dir / "failed_runs.json").read_text(encoding="utf-8"))
    assert records[0]["status"] == "FAILED"
    assert records[0]["planner_statuses"] == {"DEPENDENCY_UNAVAILABLE": 1}
    assert summary[0]["run_count"] == 1
    assert summary[0]["failure_count"] == 1
    assert failures[0]["seed"] == 4
    assert (batch_dir / "records.csv").is_file()
    assert (batch_dir / "report.html").is_file()


def test_batch_separates_skipped_dependencies_from_algorithm_failures(tmp_path: Path) -> None:
    batch_dir = BatchRunner(SkippingRunner()).run(
        [RunSpec("head_on", algorithm_id="paper_mpc", seed=4)],
        tmp_path,
    )
    records = json.loads((batch_dir / "records.json").read_text(encoding="utf-8"))
    summary = json.loads((batch_dir / "summary.json").read_text(encoding="utf-8"))
    failures = json.loads((batch_dir / "failed_runs.json").read_text(encoding="utf-8"))
    skipped = json.loads((batch_dir / "skipped_runs.json").read_text(encoding="utf-8"))

    assert records[0]["status"] == "SKIPPED"
    assert summary[0]["failure_count"] == 0
    assert summary[0]["skip_count"] == 1
    assert failures == []
    assert skipped[0]["seed"] == 4
