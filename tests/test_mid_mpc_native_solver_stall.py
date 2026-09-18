"""Frozen real-GNC Three-Ship T224.2: identical NLP and iterate admission."""

import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from colav_simulator.core.colav.mid_mpc import models
from colav_simulator.core.colav.mid_mpc import solver as solver_module
from colav_simulator.core.colav.retained_route import RetainedRouteConstraint
from colav_simulator.core.colav.threat_management import TrackKey
from colav_simulator.integrations.mid_mpc_ipopt import _recovery_iterate_filter


def test_frozen_native_three_ship_stall_preserves_admission_without_hundreds_of_iterations(monkeypatch):
    path = Path(__file__).parent / "fixtures/mid_mpc_ipopt/three_ship_native_stall.json.gz"
    case = json.loads(gzip.decompress(path.read_bytes()))
    values = case["problem"]
    for key, cls in (
        ("own_ship", models.MidMpcOwnShip),
        ("route_frame", models.MidMpcRouteFrame),
        ("route_objective", models.MidMpcRouteObjective),
        ("static_field", models.MidMpcStaticField),
    ):
        if values.get(key) is not None:
            values[key] = cls(**values[key])
    values["targets"] = tuple(models.MidMpcTarget(**target) for target in values["targets"])
    schedule = values["row_schedule"]
    schedule["cpa_hard_windows"] = tuple(models.MidMpcHardWindow(**window) for window in schedule["cpa_hard_windows"])
    for key in ("direction_hard_window", "min_alt_hard_window"):
        if schedule[key] is not None:
            schedule[key] = models.MidMpcHardWindow(**schedule[key])
    values["row_schedule"] = models.MidMpcRowSchedule(**schedule)
    problem = models.MidMpcProblem(**values)
    own = case["ownship"]
    data = SimpleNamespace(
        execution_route_constraint=RetainedRouteConstraint(**own["execution_route_constraint"]),
        ownship_state=np.array(own["state"]),
        waypoints_enu_m=np.array(case["route"]["mission_waypoints_ne_m"]).T,
        ownship_length_m=own["length_m"],
        tracks=tuple(SimpleNamespace(**track) for track in case["tracks"]),
    )
    assembly = SimpleNamespace(
        problem=problem,
        grid=SimpleNamespace(control_intervals=80, dt_s=5.0),
        horizon_encounter_plan=SimpleNamespace(
            recovery_from_k=case["recovery_from_k"],
            target_windows=tuple(SimpleNamespace(key=TrackKey(**key)) for key in case["staged_keys"]),
        ),
    )
    check = _recovery_iterate_filter(data, assembly)
    # Replay the exact post-preparation problem, including its repaired seed.
    monkeypatch.setattr(
        solver_module,
        "_prepare",
        lambda *args: models.MidMpcPreparedProblem(**{key: np.array(value) for key, value in case["prepared"].items()}),
    )
    monkeypatch.setattr(solver_module, "_repair_infeasible_seed", lambda *args, **kwargs: None)
    solver = solver_module.MidMpcIpoptSolver(
        models.MidMpcConfig(
            horizon_steps=80,
            dt_s=5.0,
            strict_slack_bounds=True,
            max_wall_time_s=60.0,
        )
    )
    solver.prewarm_capacity(3, static_field=problem.static_field)
    result = solver.solve(problem, iterate_filter=check)
    assert result.status in (models.MidMpcStatus.CONVERGED, models.MidMpcStatus.FEASIBLE_NONOPTIMAL)
    assert result.graph_cache_hit
    assert result.optimization_quality_passed and check(result.raw_x)
    assert result.accepted_candidate_source != "PRIMAL_SEED"
    assert result.max_constraint_violation < 1e-7
    assert result.max_decision_bound_violation < 1e-7
    assert result.raw_cpa_slack == result.raw_dir_slack == 0.0
    assert result.ipopt_iterations < 40
