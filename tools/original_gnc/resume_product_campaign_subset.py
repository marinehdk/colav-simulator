"""Resume a product-campaign-subset bundle: run only the missing cells.

The subset runner refuses an existing output directory (fresh-bundle
invariant, runtime-source pinning), so an interrupted campaign previously
had to rerun from scratch. This driver reuses run()'s cell loop against an
existing bundle while skipping cases whose JSON already exists — same
RunSpec, same fingerprint checks, no other behavior change.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import tools.original_gnc.run_product_campaign_subset as subset


def main(output_dir: str, algorithms: tuple[str, ...]) -> None:
    """Run only the missing cells of an existing subset bundle, in place."""
    output = Path(output_dir)
    if not (output / "runtime-source/manifest.json").exists():
        raise SystemExit(f"not an existing subset bundle: {output}")
    root = Path(__file__).resolve().parents[2]

    from colav_simulator.cli import _load_algorithm_config  # noqa: PLC0415
    from colav_simulator.core.colav.threat_assessment import DomainQualification, ShipDomainProfile  # noqa: PLC0415
    from colav_simulator.experiment.contracts import RunSpec  # noqa: PLC0415
    from colav_simulator.experiment.runner import ExperimentRunError, ExperimentRunner  # noqa: PLC0415
    from colav_simulator.original_gnc.configuration import ORIGINAL_OFF, ORIGINAL_ON  # noqa: PLC0415

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
    done = []
    for environment, stack in (("E0", ORIGINAL_OFF), ("E4", ORIGINAL_ON)):
        for algorithm in algorithms:
            config_path = root / "config" / f"{algorithm}.yaml"
            config = _load_algorithm_config(config_path) if config_path.exists() else {}
            for scenario in subset.SCENARIOS:
                case_id = f"{algorithm}-{scenario}-{environment}"
                if (output / f"{case_id}.json").exists():
                    continue
                spec = RunSpec(
                    scenario_id=scenario,
                    validation_rule_id=subset.RULES[scenario],
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
                result = {"case_id": case_id, "spec": spec.to_dict()}
                try:
                    run_result = runner.run(spec)
                    result.update(
                        {
                            "run_dir": str(run_result.run_dir),
                            "manifest": run_result.manifest.to_dict(),
                            "evaluation": run_result.evaluation.to_dict(),
                        }
                    )
                except ExperimentRunError as error:
                    result.update(
                        {"run_dir": str(error.run_dir), "manifest": error.manifest.to_dict(), "failure": str(error)}
                    )
                except Exception as error:  # noqa: BLE001 - every attempt is persisted
                    result["failure"] = repr(error)
                result["wall_s"] = time.monotonic() - started
                done.append(result)
                (output / f"{case_id}.json").write_text(json.dumps(result, indent=2, default=str))
                print(
                    json.dumps({"case_id": case_id, "failure": result.get("failure"), "wall_s": result["wall_s"]}),
                    flush=True,
                )
    print(json.dumps({"resumed_cells": len(done), "bundle": str(output)}), flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--algorithms", default="vo")
    args = parser.parse_args()
    main(args.output, tuple(a.strip() for a in args.algorithms.split(",") if a.strip()))
    # keep import parity for hash pins
    _ = hashlib
