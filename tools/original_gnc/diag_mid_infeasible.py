"""Diagnostic: run selected mid cells and dump the NLP whenever IPOPT reports infeasible.

Read-only for product sources; the solver wrapper only records evidence that the
regular artifact sink already persists for L4-rejected candidates.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from colav_simulator.cli import _load_algorithm_config  # noqa: E402
from colav_simulator.core.colav.mid_mpc.solver import MidMpcIpoptSolver  # noqa: E402
from colav_simulator.core.colav.threat_assessment import DomainQualification, ShipDomainProfile  # noqa: E402
from colav_simulator.experiment.contracts import RunSpec  # noqa: E402
from colav_simulator.experiment.runner import ExperimentRunner, ExperimentRunError  # noqa: E402

DUMP_DIR = Path("build/original_gnc-glibc-v8/diag-mid-infeasible")
CELLS = {
    "overtaking": ("rule13", "E0"),
    "paper_ccta2023_multiship": ("multiship", "E0"),
}

_original_solve = MidMpcIpoptSolver.solve
dump_count = 0


def _dump(prepared, problem, result) -> str:
    global dump_count
    dump_count += 1
    out = DUMP_DIR / f"infeasible-{dump_count:02d}"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "ipopt_return_status": result.ipopt_return_status,
        "status": str(result.status),
        "max_constraint_violation": result.max_constraint_violation,
        "lbg": prepared.lbg.tolist(),
        "ubg": prepared.ubg.tolist(),
        "lbx": prepared.lbx.tolist(),
        "ubx": prepared.ubx.tolist(),
        "x0": prepared.x0.tolist(),
        "g": result.raw_g.tolist(),
        "raw_x": result.raw_x.tolist(),
        "row_layout": result.row_layout.to_dict(),
        "heading_bounds_rad": list(problem.heading_bounds_rad),
        "speed_bounds_mps": list(problem.speed_bounds_mps),
        "row_schedule": {
            "course_bounds_rad": [
                [None if v is None else float(v) for v in bound]
                for bound in problem.row_schedule.course_bounds_rad
            ],
            "cpa_hard_from_k": problem.row_schedule.cpa_hard_from_k,
            "cpa_hard_windows": [
                [window.start_k, window.stop_k] for window in problem.row_schedule.cpa_hard_windows
            ],
            "direction_hard_window": None
            if problem.row_schedule.direction_hard_window is None
            else [problem.row_schedule.direction_hard_window.start_k, problem.row_schedule.direction_hard_window.stop_k],
            "min_alt_hard_window": None
            if problem.row_schedule.min_alt_hard_window is None
            else [problem.row_schedule.min_alt_hard_window.start_k, problem.row_schedule.min_alt_hard_window.stop_k],
            "prefix_softening": problem.row_schedule.prefix_softening,
            "terminal_rows_enabled": problem.row_schedule.terminal_rows_enabled,
        },
        "prefix_active_k": problem.prefix_active_k,
        "prefix_psi_rad": list(problem.prefix_psi_rad),
        "prefix_u_mps": list(problem.prefix_u_mps),
        "own_ship": {
            "psi_rad": problem.own_ship.psi_rad,
            "u_mps": problem.own_ship.u_mps,
            "x_m": problem.own_ship.x_m,
            "y_m": problem.own_ship.y_m,
        },
        "targets": [
            {"x_m": t.x_m, "y_m": t.y_m, "sog_mps": t.sog_mps, "cog_rad": t.cog_rad} for t in problem.targets
        ],
        "lateral_active": problem.lateral_active,
        "preferred_side": problem.preferred_side,
        "min_alteration_rad": problem.min_alteration_rad,
        "cpa_hard_m": problem.cpa_hard_m,
    }
    (out / "problem.json").write_text(json.dumps(payload, indent=1))
    return str(out)


def _patched_solve(self, problem, **kwargs):
    result = _original_solve(self, problem, **kwargs)
    if "Infeasible" in result.ipopt_return_status or "Invalid" in result.ipopt_return_status:
        path = _dump(result.prepared, problem, result)
        print(f"DIAG: dumped infeasible problem to {path}", flush=True)
    return result


MidMpcIpoptSolver.solve = _patched_solve


def run_selected(output: Path) -> None:
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[2]
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
    config = _load_algorithm_config(root / "config" / "mid_mpc_ipopt.yaml")
    for scenario, (rule, environment) in CELLS.items():
        from colav_simulator.original_gnc.configuration import ORIGINAL_OFF, ORIGINAL_ON

        stack = ORIGINAL_OFF if environment == "E0" else ORIGINAL_ON
        spec = RunSpec(
            scenario_id=scenario,
            validation_rule_id=rule,
            algorithm_id="mid_mpc_ipopt",
            tracker_id="god",
            ownship_gnc_stack_id=stack,
            seed=0,
            strict_no_fallback=True,
            terminate_on_collision_or_grounding=False,
            solve_period_s=5.0,
            deadline_mode="ENFORCE",
            algorithm_config=config,
            domain_profile=domain,
            output_root=str(output / f"mid_mpc_ipopt-{scenario}-{environment}"),
        )
        started = time.monotonic()
        try:
            run_result = runner.run(spec)
            print(json.dumps({"scenario": scenario, "outcome": str(run_result.manifest.outcome), "wall_s": time.monotonic() - started}), flush=True)
            run_result.session.close() if hasattr(run_result.session, "close") else None
        except ExperimentRunError as error:
            print(json.dumps({"scenario": scenario, "failure": str(error), "wall_s": time.monotonic() - started}), flush=True)
        except Exception as error:  # noqa: BLE001
            print(json.dumps({"scenario": scenario, "error": repr(error), "wall_s": time.monotonic() - started}), flush=True)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/original_gnc-glibc-v8/diag-mid-run")
    run_selected(out.resolve())
    print("sha of solver.py:", hashlib.sha256((Path(__file__).resolve().parents[2] / "colav_simulator/core/colav/mid_mpc/solver.py").read_bytes()).hexdigest()[:12])
