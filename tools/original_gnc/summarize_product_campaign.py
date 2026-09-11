"""Separate execution, original route admission, solver evidence and scenario safety."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq


def file_sha256(path: Path) -> str:
    """Hash large persisted trajectories without loading them into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def planner_timing(run: Path, last_planner: dict) -> dict:
    """Deduplicate successful solve IDs; keep terminal failure-call cost separate."""
    times = []
    seen = set()
    columns = ["ship_id", "planner_solve_id", "planner_solver_executed", "colav_json"]
    for batch in pq.ParquetFile(run / "trajectory.parquet").iter_batches(batch_size=128, columns=columns):
        for row in batch.to_pylist():
            if row["ship_id"] != 0 or not row["planner_solver_executed"] or row["planner_solve_id"] in seen:
                continue
            document = json.loads(row["colav_json"])
            elapsed = document.get("diagnostics", {}).get("elapsed_ms")
            if elapsed is not None:
                times.append(float(elapsed))
                seen.add(row["planner_solve_id"])
    return {
        "successful_call_samples": len(times),
        "maximum_ms": max(times) if times else None,
        "median_ms": statistics.median(times) if times else None,
        "p95_ms": statistics.quantiles(times, n=20, method="inclusive")[-1]
        if len(times) > 1
        else times[0]
        if times
        else None,
        "terminal_call_ms": last_planner.get("diagnostics", {}).get("elapsed_ms"),
        "scope": (
            "Planner API wall time, deduplicated by actual solve ID; "
            "includes algorithm/acceptance overhead, not only optimizer time"
        ),
    }


def summarize(campaign: Path, output: Path) -> dict:
    """Use persisted product artifacts, including failed and unassessed runs."""
    cases = json.loads((campaign / "campaign.json").read_text())["cases"]
    if len(cases) != 24:
        raise ValueError("The frozen product matrix must contain all 24 attempts")
    rows = []
    for case in cases:
        run = Path(case["run_dir"])
        manifest = json.loads((run / "manifest.json").read_text())
        bundle = json.loads((run / "original-gnc.json").read_text())
        evaluation = json.loads((run / "evaluation.json").read_text())
        events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
        requests = [row for row in bundle["requested_plans"] if row["kind"] == "avoidance"]
        identifiers = {row["message"]["plan_id"] for row in requests}
        forwarded = set()
        accepted = set()
        coordinate_reasons = Counter()
        manager_reasons = Counter()
        for event in bundle["execution_events"]:
            fields = event.get("message", {}).get("fields", {})
            identifier = fields.get("route_id", fields.get("plan_id"))
            if identifier not in identifiers:
                continue
            if event.get("topic") == "/gnc/active_route":
                forwarded.add(identifier)
            elif event.get("topic") == "/route_planning/route_plan_status":
                coordinate_reasons[fields["reason"]] += 1
                if fields["accepted"]:
                    accepted.add(identifier)
            elif event.get("topic") == "/gnc/route_execution_status":
                manager_reasons[fields["reason"]] += 1
        mid_artifacts = []
        for path in sorted((run / "artifacts/mid_mpc").glob("*.json.gz")):
            raw = gzip.decompress(path.read_bytes())
            digest = hashlib.sha256(raw).hexdigest()
            if path.name != digest + ".json.gz":
                raise ValueError(f"Changed solver artifact: {path}")
            artifact = json.loads(raw)
            solver = artifact["solver_stage"]["solver"]
            mid_artifacts.append(
                {
                    "path": str(path),
                    "sha256": digest,
                    "solver": {
                        key: solver.get(key)
                        for key in (
                            "iterations",
                            "accepted_iteration",
                            "ipopt_return_status",
                            "native_status",
                            "status",
                            "accepted_candidate_source",
                            "max_constraint_violation",
                            "optimization_quality_passed",
                        )
                    },
                    "l4_accepted": artifact["acceptance"]["accepted"],
                }
            )
        checks = evaluation["hard_gate"].get("checks", [])
        clearance = next(
            (
                row["evidence"].get("minimum_hull_clearance_m")
                for row in checks
                if row["check_id"] == "minimum_hull_clearance"
            ),
            None,
        )
        planner = bundle.get("last_planner", {}).get("planner", {})
        details = planner.get("algorithm_details", {})
        goal = any(row["type"] == "goal_reached" for row in events)
        epoch = next(row["time_ns"] for row in bundle["requested_plans"] if row["kind"] == "nominal")
        plant_time = bundle["final_source_states"]["ship_dynamics_node"]["last_time_ns"]
        rows.append(
            {
                "case_id": case["case_id"],
                "run_directory": str(run),
                "execution_outcome": manifest["execution_outcome"],
                "state": manifest["state"],
                "fallback_used": manifest["fallback_used"],
                "failure": case.get("failure"),
                "simulation_time_s": (plant_time - epoch) / 1e9,
                "wall_s": case["wall_s"],
                "library_sha256": bundle["build"]["library_sha256"],
                "avoidance_publications": len(requests),
                "unique_avoidance_ids": len(identifiers),
                "manager_forwarded_ids": len(forwarded),
                "coordinate_accepted_ids": len(accepted),
                "coordinate_status_reasons": dict(coordinate_reasons),
                "manager_status_reasons": dict(manager_reasons),
                "evaluation_status": evaluation["evaluation_status"],
                "hard_gate": evaluation["hard_gate"]["outcome"],
                "minimum_hull_clearance_m": clearance,
                "goal_reached": goal,
                "aggregate": evaluation.get("aggregate"),
                "voyage": evaluation.get("voyage"),
                "planner_summary_solver_executed": planner.get("solver_executed"),
                "fan_candidate_count": details.get("candidate_count"),
                "vo_grid_shape": details.get("grid_shape"),
                "vo_infeasible_candidate_fallback_label": details.get("fallback"),
                "mid_solver_artifacts": mid_artifacts,
                "planner_call_timing": planner_timing(run, bundle.get("last_planner", {})),
                "artifact_sha256": {
                    name: file_sha256(run / name)
                    for name in (
                        "manifest.json",
                        "original-gnc.json",
                        "evaluation.json",
                        "events.jsonl",
                        "trajectory.parquet",
                    )
                },
            }
        )
    report = {
        "schema": "original-gnc.product-acceptance-summary.v1",
        "case_count": len(rows),
        "execution_completed": sum(row["execution_outcome"] == "COMPLETED" for row in rows),
        "execution_failed": sum(row["execution_outcome"] != "COMPLETED" for row in rows),
        "hard_gate_passed": sum(row["hard_gate"] == "PASS" for row in rows),
        "goal_and_hard_gate_passed": sum(row["goal_reached"] and row["hard_gate"] == "PASS" for row in rows),
        "fallback_used_count": sum(row["fallback_used"] for row in rows),
        "scope": (
            "Completed runs, physical safety, COLREG scores, original route admission and goal arrival are separate claims"
        ),
        "cases": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.campaign, args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))
