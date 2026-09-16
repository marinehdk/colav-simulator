"""Expanded evaluation must preserve the captured native-GNC NLP solution."""

import gzip
import json
from pathlib import Path

import casadi as ca
import numpy as np

from colav_simulator.core.colav.mid_mpc import models
from colav_simulator.core.colav.mid_mpc import solver as solver_module


def test_native_gnc_slow_input_expansion_preserves_double_precision_solution(monkeypatch):
    path = Path(__file__).parent / "fixtures/mid_mpc_ipopt/original_gnc_slow_chart.json.gz"
    with gzip.open(path, "rt") as stream:
        case = json.load(stream)
    values = case["problem"]
    for key, cls in (
        ("own_ship", models.MidMpcOwnShip),
        ("route_frame", models.MidMpcRouteFrame),
        ("route_objective", models.MidMpcRouteObjective),
        ("static_field", models.MidMpcStaticField),
    ):
        values[key] = cls(**values[key])
    values["targets"] = tuple(models.MidMpcTarget(**target) for target in values["targets"])
    schedule = values["row_schedule"]
    schedule["cpa_hard_windows"] = tuple(models.MidMpcHardWindow(**window) for window in schedule["cpa_hard_windows"])
    for key in ("direction_hard_window", "min_alt_hard_window"):
        if schedule[key] is not None:
            schedule[key] = models.MidMpcHardWindow(**schedule[key])
    values["row_schedule"] = models.MidMpcRowSchedule(**schedule)
    problem = models.MidMpcProblem(**values)
    config = models.MidMpcConfig(**case["config"])
    warm = models.MidMpcPrimalWarmStart(**case["warm_start"])
    expanded = solver_module.MidMpcIpoptSolver(config).solve(problem, primal_warm_start=warm)
    original_nlpsol = solver_module.ca.nlpsol

    def unexpanded(name, plugin, nlp, options) -> ca.Function:
        assert options["expand"] is True
        return original_nlpsol(name, plugin, nlp, {**options, "expand": False})

    monkeypatch.setattr(solver_module.ca, "nlpsol", unexpanded)
    original = solver_module.MidMpcIpoptSolver(config).solve(problem, primal_warm_start=warm)
    assert expanded.status == original.status == models.MidMpcStatus.FEASIBLE_NONOPTIMAL
    assert expanded.ipopt_iterations == original.ipopt_iterations
    assert expanded.optimization_quality_passed and original.optimization_quality_passed
    np.testing.assert_array_equal(expanded.raw_x, original.raw_x)
    np.testing.assert_array_equal(expanded.raw_g, original.raw_g)
    assert expanded.raw_f == original.raw_f
    assert expanded.max_constraint_violation < 1e-6
    assert expanded.max_decision_bound_violation == 0.0
    assert expanded.raw_cpa_slack == expanded.raw_dir_slack == 0.0
