from __future__ import annotations

import json
from pathlib import Path

from colav_simulator.core.colav.diagnostics import PlanStatus
from colav_simulator.core.colav.threat_assessment import DomainQualification, ShipDomainProfile
from colav_simulator.experiment import ExperimentRunError, RunManifest, RunSpec, SessionState
from colav_simulator.experiment.batch import BatchRunner
from colav_simulator.experiment.contracts import RunOutcome


def _qualified_profile() -> ShipDomainProfile:
    return ShipDomainProfile(
        profile_id="batch-domain",
        version="v1",
        fore_m=300.0,
        aft_m=100.0,
        port_m=120.0,
        starboard_m=180.0,
        parameter_source="test-fixture",
        assumptions=("engineering-envelope-only",),
        qualification=DomainQualification.QUALIFIED,
    )


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


def test_default_matrix_contains_only_product_scenarios_and_thirty_seeds() -> None:
    specs = BatchRunner.default_specs(["vo"])
    assert len(specs) == 6 * 30
    assert {spec.seed for spec in specs} == set(range(30))
    assert len({spec.scenario_id for spec in specs}) == 6
    assert all(spec.validation_rule_id for spec in specs)


def test_batch_keeps_failed_runs_in_all_reports(tmp_path: Path) -> None:
    batch_dir = BatchRunner(FailingRunner()).run(
        [RunSpec("head_on", validation_rule_id="rule14", algorithm_id="vo", tracker_id="god", seed=4)],
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
        [RunSpec("head_on", validation_rule_id="rule14", algorithm_id="vo", tracker_id="god", seed=4)],
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


def test_batch_default_specs_preserve_explicit_mid_mpc_domain_profile() -> None:
    profile = _qualified_profile()

    specs = BatchRunner.default_specs(
        ["mid_mpc_ipopt"],
        seeds=[0],
        domain_profile=profile.to_dict(),
    )

    assert specs
    assert all(spec.domain_profile == profile for spec in specs)
