"""Rerun a planner subset of the frozen product matrix and summarize it.

Same RunSpec as ``run_product_campaign.py`` (seed 0, strict_no_fallback,
5 s solve period, ENFORCE deadline, P1 engineering domain for Mid-MPC only);
only the planner set is selectable so a planner-track fix can be re-evaluated
without re-executing the other planners' cells.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.core.colav.threat_assessment import DomainQualification, ShipDomainProfile
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner
from colav_simulator.original_gnc.adapter import RUNTIME_SOURCE_FINGERPRINTS
from colav_simulator.original_gnc.configuration import ORIGINAL_OFF, ORIGINAL_ON
from tools.original_gnc.summarize_product_campaign import file_sha256, planner_timing

SCENARIOS = ("head_on", "crossing_give_way", "overtaking", "paper_ccta2023_multiship")
ALGORITHMS = ("vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt")
RULES = dict(zip(SCENARIOS, ("rule14", "rule15", "rule13", "multiship"), strict=True))


def run(output: Path, algorithms: tuple[str, ...]) -> dict:
    """Persist every attempt; execution, admission and safety remain separate."""
    if output.exists():
        raise FileExistsError(output)
    unknown = sorted(set(algorithms) - set(ALGORITHMS))
    if unknown:
        raise ValueError(f"Unknown planner ids: {unknown}")
    output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[2]
    for relative, expected in RUNTIME_SOURCE_FINGERPRINTS.items():
        raw = (root / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError(f"Loaded runtime differs from campaign source snapshot: {relative}")
        path = output / "runtime-source" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (output / "runtime-source/manifest.json").write_text(json.dumps(RUNTIME_SOURCE_FINGERPRINTS, indent=2))
    runner = ExperimentRunner(root)
    domain = ShipDomainProfile(
        profile_id="p1-mid-mpc-domain",
        version="v1",
        fore_m=300.0,
        aft_m=100.0,
        port_m=120.0,
        starboard_m=180.0,
        parameter_source="P1 test fixture engineering envelope",
        assumptions=("test-only engineering envelope",),
        qualification=DomainQualification.QUALIFIED,
    )
    results = []
    for environment, stack in (("E0", ORIGINAL_OFF), ("E4", ORIGINAL_ON)):
        for algorithm in algorithms:
            config_path = root / "config" / f"{algorithm}.yaml"
            config = _load_algorithm_config(config_path) if config_path.exists() else {}
            for scenario in SCENARIOS:
                case_id = f"{algorithm}-{scenario}-{environment}"
                spec = RunSpec(
                    scenario_id=scenario,
                    validation_rule_id=RULES[scenario],
                    algorithm_id=algorithm,
                    tracker_id="god",
                    ownship_gnc_stack_id=stack,
                    seed=0,
                    strict_no_fallback=True,
                    terminate_on_collision_or_grounding=False,
                    solve_period_s=5.0,
                    deadline_mode="ENFORCE",
                    algorithm_config=config,
                    domain_profile=domain if algorithm == "mid_mpc_ipopt" else None,
                    output_root=str(output / case_id),
                )
                started = time.monotonic()
                result = {
                    "case_id": case_id,
                    "spec": spec.to_dict(),
                    "algorithm_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest()
                    if config_path.exists()
                    else None,
                }
                try:
                    run_result = runner.run(spec)
                    result.update(
                        {
                            "run_dir": str(run_result.run_dir),
                            "manifest": run_result.manifest.to_dict(),
                            "evaluation": run_result.evaluation.to_dict(),
                        }
                    )
                    run_result.session.close() if hasattr(run_result.session, "close") else None
                except ExperimentRunError as error:
                    result.update(
                        {"run_dir": str(error.run_dir), "manifest": error.manifest.to_dict(), "failure": str(error)}
                    )
                except Exception as error:  # noqa: BLE001 - every attempt is persisted
                    result["failure"] = repr(error)
                result["wall_s"] = time.monotonic() - started
                results.append(result)
                (output / f"{case_id}.json").write_text(json.dumps(result, indent=2, default=str))
                print(
                    json.dumps(
                        {
                            "case_id": case_id,
                            "failure": result.get("failure"),
                            "run_dir": result.get("run_dir"),
                            "wall_s": result["wall_s"],
                        }
                    ),
                    flush=True,
                )
    report = {
        "scope": "planner-subset rerun of the product matrix; execution and safety assessed separately",
        "algorithms": list(algorithms),
        "cases": results,
    }
    (output / "campaign.json").write_text(json.dumps(report, indent=2, default=str))
    return report


def summarize(campaign: Path, output: Path) -> dict:
    """Per-cell execution, admission, activation latency and physical safety."""
    cases = json.loads((campaign / "campaign.json").read_text())["cases"]
    rows = []
    for case in cases:
        run_dir = case.get("run_dir")
        if run_dir is None:
            rows.append({"case_id": case["case_id"], "failure": case.get("failure"), "execution_outcome": "NOT_RUN"})
            continue
        run_path = Path(run_dir)
        manifest = json.loads((run_path / "manifest.json").read_text())
        bundle = json.loads((run_path / "original-gnc.json").read_text())
        evaluation = json.loads((run_path / "evaluation.json").read_text())
        events = [json.loads(line) for line in (run_path / "events.jsonl").read_text().splitlines()]
        epoch = next(row["time_ns"] for row in bundle["requested_plans"] if row["kind"] == "nominal")
        requests = [row for row in bundle["requested_plans"] if row["kind"] == "avoidance"]
        identifiers = {row["message"]["plan_id"] for row in requests}
        forwarded, accepted = set(), set()
        first_accepted_ns = None
        manager_reasons = Counter()
        for event in bundle["execution_events"]:
            fields = event.get("message", {}).get("fields", {})
            identifier = fields.get("route_id", fields.get("plan_id"))
            if identifier not in identifiers:
                continue
            if event.get("topic") == "/gnc/active_route":
                forwarded.add(identifier)
            elif event.get("topic") == "/route_planning/route_plan_status" and fields["accepted"]:
                accepted.add(identifier)
                first_accepted_ns = (
                    event["time_ns"] if first_accepted_ns is None else min(first_accepted_ns, event["time_ns"])
                )
            elif event.get("topic") == "/gnc/route_execution_status":
                manager_reasons[fields["reason"]] += 1
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
        threat_entered = next((row["sim_time"] for row in events if row["type"] == "threat_entered"), None)
        first_request_s = (min(row["time_ns"] for row in requests) - epoch) / 1e9 if requests else None
        first_accepted_s = (first_accepted_ns - epoch) / 1e9 if first_accepted_ns is not None else None
        plant_time = bundle["final_source_states"]["ship_dynamics_node"]["last_time_ns"]
        rows.append(
            {
                "case_id": case["case_id"],
                "run_directory": str(run_path),
                "execution_outcome": manifest["execution_outcome"],
                "failure": case.get("failure"),
                "simulation_time_s": (plant_time - epoch) / 1e9,
                "wall_s": case["wall_s"],
                "library_sha256": bundle["build"]["library_sha256"],
                "avoidance_publications": len(requests),
                "unique_avoidance_ids": len(identifiers),
                "manager_forwarded_ids": len(forwarded),
                "coordinate_accepted_ids": len(accepted),
                "manager_status_reasons": dict(manager_reasons),
                "evaluation_status": evaluation["evaluation_status"],
                "hard_gate": evaluation["hard_gate"]["outcome"],
                "minimum_hull_clearance_m": clearance,
                "goal_reached": any(row["type"] == "goal_reached" for row in events),
                "threat_entered_s": threat_entered,
                "first_avoidance_request_s": first_request_s,
                "first_accepted_avoidance_s": first_accepted_s,
                "detect_to_accepted_s": (
                    first_accepted_s - threat_entered
                    if first_accepted_s is not None and threat_entered is not None
                    else None
                ),
                "last_planner_status": planner.get("status"),
                "last_planner_feasible": planner.get("feasible"),
                "vo_infeasible_candidate_fallback_label": details.get("fallback"),
                "vo_planning_horizon_s": details.get("planning_horizon_s"),
                "vo_selection_held_terminal": details.get("selection_held"),
                "fan_ownship_response_model": details.get("ownship_response_model"),
                "planner_call_timing": planner_timing(run_path, bundle.get("last_planner", {})),
                "artifact_sha256": {
                    name: file_sha256(run_path / name)
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
        "schema": "original-gnc.product-acceptance-summary.subset.v1",
        "case_count": len(rows),
        "execution_completed": sum(row.get("execution_outcome") == "COMPLETED" for row in rows),
        "execution_failed": sum(row.get("execution_outcome") != "COMPLETED" for row in rows),
        "hard_gate_passed": sum(row.get("hard_gate") == "PASS" for row in rows),
        "goal_and_hard_gate_passed": sum(bool(row.get("goal_reached")) and row.get("hard_gate") == "PASS" for row in rows),
        "scope": (
            "Completed runs, physical safety, original route admission, activation latency "
            "and goal arrival are separate claims"
        ),
        "cases": rows,
    }
    output.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--algorithms", default="vo,potocnik_colreg_fan_mpc")
    parser.add_argument("--summary", type=Path, default=None, help="Summary JSON path (default: <output>/summary.json)")
    args = parser.parse_args()
    algorithms = tuple(item.strip() for item in args.algorithms.split(",") if item.strip())
    run(args.output, algorithms)
    summary = summarize(args.output, args.summary or args.output / "summary.json")
    print(json.dumps({key: value for key, value in summary.items() if key != "cases"}, indent=2))
