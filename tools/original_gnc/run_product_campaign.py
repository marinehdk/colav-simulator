"""Exercise the original backend through real product preparation and planners."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.core.colav.threat_assessment import DomainQualification, ShipDomainProfile
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner
from colav_simulator.original_gnc.adapter import RUNTIME_SOURCE_FINGERPRINTS
from colav_simulator.original_gnc.configuration import ORIGINAL_OFF, ORIGINAL_ON

SCENARIOS = ("head_on", "crossing_give_way", "overtaking", "paper_ccta2023_multiship")
ALGORITHMS = ("vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt")


def run(output: Path) -> dict:
    """Persist every attempt; execution, admission and safety remain separate."""
    if output.exists():
        raise FileExistsError(output)
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
    # Same explicit engineering envelope as the existing P1 algorithm suite.
    # It qualifies that test domain, not the original vessel response model.
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
        for algorithm in ALGORITHMS:
            config_path = root / "config" / f"{algorithm}.yaml"
            config = _load_algorithm_config(config_path) if config_path.exists() else {}
            for scenario in SCENARIOS:
                case_id = f"{algorithm}-{scenario}-{environment}"
                case_root = output / case_id
                rule = dict(zip(SCENARIOS, ("rule14", "rule15", "rule13", "multiship"), strict=True))[scenario]
                spec = RunSpec(
                    scenario_id=scenario,
                    validation_rule_id=rule,
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
                    output_root=str(case_root),
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
                except Exception as error:
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
    report = {"scope": "actual product integration; each execution and safety result assessed separately", "cases": results}
    (output / "campaign.json").write_text(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
