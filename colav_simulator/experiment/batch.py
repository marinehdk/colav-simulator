"""Batch experiment matrices and failure-preserving summaries."""

from __future__ import annotations

import html
import json
import math
import time
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from colav_simulator.core.colav.diagnostics import ColavExecutionError
from colav_simulator.experiment.capabilities import PRODUCT_CAPABILITY_POLICY
from colav_simulator.experiment.contracts import RunOutcome, RunSpec
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner

STANDARD_SCENARIOS = [
    "head_on",
    "crossing_give_way",
    "crossing_stand_on",
    "overtaking",
    "overtaken",
]
PAPER_SCENARIOS = ["paper_ccta2023_head_on", "paper_ccta2023_multiship"]
IMAZU_SCENARIOS = [f"imazu_cases/imazu{index:02d}" for index in range(1, 23)]
AIS_SCENARIOS = ["ais_scenario1"]


@dataclass
class BatchRecord:
    scenario_id: str
    algorithm_id: str
    tracker_id: str
    seed: int
    status: str
    run_id: str | None
    run_dir: str | None
    failure_reason: str | None
    fallback_used: bool
    wall_time_s: float
    collision_count: int | None
    grounding_count: int | None
    pair_count: int | None
    metrics: dict[str, float]
    planner_statuses: dict[str, int]


class BatchRunner:
    def __init__(self, runner: ExperimentRunner | None = None) -> None:
        self.runner = runner or ExperimentRunner()

    def run(self, specs: Iterable[RunSpec], output_root: Path) -> Path:
        batch_dir = output_root / f"batch-{uuid.uuid4()}"
        batch_dir.mkdir(parents=True, exist_ok=False)
        records: list[BatchRecord] = []
        for spec in specs:
            run_spec = replace(spec, output_root=str(batch_dir / "runs"))
            started = time.perf_counter()
            try:
                result = self.runner.run(run_spec)
                aggregate = result.evaluation.aggregate
                metrics = {
                    key: float(value)
                    for key, value in aggregate.items()
                    if isinstance(value, (int, float)) and key not in {"pair_count", "collision_count", "grounding_count"}
                }
                records.append(
                    BatchRecord(
                        scenario_id=spec.scenario_id,
                        algorithm_id=spec.algorithm_id,
                        tracker_id=spec.tracker_id,
                        seed=spec.seed,
                        status="SUCCESS",
                        run_id=result.manifest.run_id,
                        run_dir=str(result.run_dir),
                        failure_reason=None,
                        fallback_used=result.manifest.fallback_used,
                        wall_time_s=time.perf_counter() - started,
                        collision_count=int(aggregate.get("collision_count", 0)),
                        grounding_count=int(aggregate.get("grounding_count", 0)),
                        pair_count=int(aggregate.get("pair_count", 0)),
                        metrics=metrics,
                        planner_statuses=self._planner_statuses(result.session.frames),
                    )
                )
            except Exception as exc:
                manifest = exc.manifest if isinstance(exc, ExperimentRunError) else None
                records.append(
                    BatchRecord(
                        scenario_id=spec.scenario_id,
                        algorithm_id=spec.algorithm_id,
                        tracker_id=spec.tracker_id,
                        seed=spec.seed,
                        status=(
                            "SKIPPED"
                            if manifest and manifest.execution_outcome == RunOutcome.SKIPPED
                            else "FAILED"
                        ),
                        run_id=manifest.run_id if manifest else None,
                        run_dir=str(exc.run_dir) if isinstance(exc, ExperimentRunError) else None,
                        failure_reason=str(exc),
                        fallback_used=manifest.fallback_used if manifest else False,
                        wall_time_s=time.perf_counter() - started,
                        collision_count=None,
                        grounding_count=None,
                        pair_count=None,
                        metrics={},
                        planner_statuses={manifest.failure_status or "UNKNOWN": 1} if manifest else {"UNKNOWN": 1},
                    )
                )
            self._write_records(batch_dir, records)
        self._write_summary(batch_dir, records)
        self._write_report(batch_dir, records)
        return batch_dir

    @staticmethod
    def _planner_statuses(frames: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for frame in frames:
            for key, ship in frame.items():
                if not key.startswith("Ship") or not ship:
                    continue
                status = ship.get("colav", {}).get("diagnostics", {}).get("status")
                if status:
                    counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def default_specs(
        algorithms: Iterable[str],
        seeds: Iterable[int] = range(30),
        tracker_id: str = PRODUCT_CAPABILITY_POLICY.default_tracker_id,
    ) -> list[RunSpec]:
        scenarios = [*STANDARD_SCENARIOS, *PAPER_SCENARIOS, *IMAZU_SCENARIOS, *AIS_SCENARIOS]
        seed_values = tuple(seeds)
        tracker_id = tracker_id.strip().lower()
        output: list[RunSpec] = []
        for algorithm in algorithms:
            algorithm_id = algorithm.strip().lower()
            PRODUCT_CAPABILITY_POLICY.require_integrations(algorithm_id, tracker_id)
            for scenario in scenarios:
                try:
                    rule_id = PRODUCT_CAPABILITY_POLICY.infer_rule(scenario, algorithm_id, tracker_id)
                except ColavExecutionError:
                    # The default product matrix contains only scenarios with
                    # one published exact tuple. Unsupported legacy/catalog
                    # scenarios remain available through explicit specs.
                    continue
                output.extend(
                    RunSpec(
                        scenario_id=scenario,
                        validation_rule_id=rule_id,
                        algorithm_id=algorithm_id,
                        tracker_id=tracker_id,
                        seed=seed,
                    )
                    for seed in seed_values
                )
        return output

    @staticmethod
    def _write_records(batch_dir: Path, records: list[BatchRecord]) -> None:
        documents = [asdict(record) for record in records]
        (batch_dir / "records.json").write_text(json.dumps(documents, indent=2), encoding="utf-8")
        flat = []
        for record in documents:
            metrics = record.pop("metrics")
            flat.append({**record, **metrics})
        pd.DataFrame(flat).to_csv(batch_dir / "records.csv", index=False)

    @staticmethod
    def _write_summary(batch_dir: Path, records: list[BatchRecord]) -> None:
        groups: dict[tuple[str, str], list[BatchRecord]] = {}
        for record in records:
            groups.setdefault((record.algorithm_id, record.scenario_id), []).append(record)
        summaries = []
        for (algorithm, scenario), group in groups.items():
            successful = [record for record in group if record.status == "SUCCESS"]
            metric_names = sorted({key for record in successful for key in record.metrics})
            metrics = {}
            for name in metric_names:
                values = np.array([record.metrics[name] for record in successful if name in record.metrics], dtype=float)
                if not values.size:
                    continue
                standard_error = float(np.std(values, ddof=1) / math.sqrt(values.size)) if values.size > 1 else 0.0
                metrics[name] = {
                    "mean": float(np.mean(values)),
                    "ci95_low": float(np.mean(values) - 1.96 * standard_error),
                    "ci95_high": float(np.mean(values) + 1.96 * standard_error),
                    "n": int(values.size),
                }
            summaries.append(
                {
                    "algorithm_id": algorithm,
                    "scenario_id": scenario,
                    "run_count": len(group),
                    "success_count": len(successful),
                    "failure_count": sum(record.status == "FAILED" for record in group),
                    "skip_count": sum(record.status == "SKIPPED" for record in group),
                    "fallback_count": sum(record.fallback_used for record in group),
                    "collision_count": sum(record.collision_count or 0 for record in successful),
                    "grounding_count": sum(record.grounding_count or 0 for record in successful),
                    "metrics": metrics,
                }
            )
        (batch_dir / "summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
        failures = [asdict(record) for record in records if record.status == "FAILED"]
        skipped = [asdict(record) for record in records if record.status == "SKIPPED"]
        (batch_dir / "failed_runs.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")
        (batch_dir / "skipped_runs.json").write_text(json.dumps(skipped, indent=2), encoding="utf-8")

    @staticmethod
    def _write_report(batch_dir: Path, records: list[BatchRecord]) -> None:
        total = len(records)
        failed = sum(record.status == "FAILED" for record in records)
        skipped = sum(record.status == "SKIPPED" for record in records)
        fallback = sum(record.fallback_used for record in records)
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(record.algorithm_id)}</td>"
            f"<td>{html.escape(record.scenario_id)}</td>"
            f"<td>{record.seed}</td>"
            f"<td>{html.escape(record.status)}</td>"
            f"<td>{record.wall_time_s:.3f}</td>"
            f"<td>{html.escape(record.failure_reason or '')}</td>"
            "</tr>"
            for record in records
        )
        document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>COLAV Batch Report</title>
<style>body{{font:14px system-ui;margin:32px;color:#17202a}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccd1d1;padding:7px;text-align:left}}th{{background:#eef2f3}}</style>
</head><body><h1>COLAV Batch Report</h1>
<p>Runs {total} · failures {failed} · skipped {skipped} · fallbacks {fallback}</p>
<table><thead><tr><th>Algorithm</th><th>Scenario</th><th>Seed</th><th>Status</th>
<th>Wall time (s)</th><th>Failure</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
        (batch_dir / "report.html").write_text(document, encoding="utf-8")
