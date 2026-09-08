"""Numerical regression for two captured multi-ship solver stalls."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.mid_mpc import MidMpcConfig, MidMpcIpoptSolver, MidMpcStatus
from colav_simulator.core.colav.mid_mpc.models import (
    MidMpcHardWindow,
    MidMpcOwnShip,
    MidMpcPrimalWarmStart,
    MidMpcProblem,
    MidMpcRouteFrame,
    MidMpcRouteObjective,
    MidMpcRowSchedule,
    MidMpcStaticField,
    MidMpcTarget,
)


@pytest.mark.parametrize("case_index", [0, 1, 2, 3, 4, 5])
def test_captured_cs_problem_converges_without_restoration_stall(case_index: int) -> None:
    document = json.loads((Path(__file__).parent / "fixtures/mid_mpc_ipopt/slow_multiship.json").read_text())
    with gzip.open(Path(__file__).parent / "fixtures/mid_mpc_ipopt/chart_feasible_seed.json.gz", "rt") as stream:
        document["cases"].append(json.load(stream))
    with gzip.open(Path(__file__).parent / "fixtures/mid_mpc_ipopt/single_chart_warm_seed.json.gz", "rt") as stream:
        document["cases"].append(json.load(stream))
    case = document["cases"][case_index]
    values = case["problem"]
    if values.get("static_field") is not None:
        values["static_field"] = MidMpcStaticField(**values["static_field"])
    schedule = values.pop("row_schedule")
    schedule["cpa_hard_windows"] = tuple(MidMpcHardWindow(**w) for w in schedule["cpa_hard_windows"])
    for field in ("direction_hard_window", "min_alt_hard_window"):
        if schedule[field] is not None:
            schedule[field] = MidMpcHardWindow(**schedule[field])
    problem = MidMpcProblem(
        **{k: v for k, v in values.items() if k not in {"own_ship", "route_frame", "route_objective", "targets"}},
        own_ship=MidMpcOwnShip(**values["own_ship"]),
        route_frame=MidMpcRouteFrame(**values["route_frame"]),
        route_objective=MidMpcRouteObjective(**values["route_objective"]),
        targets=tuple(MidMpcTarget(**t) for t in values["targets"]),
        row_schedule=MidMpcRowSchedule(**schedule),
    )
    solver = MidMpcIpoptSolver(MidMpcConfig(**case["config"]))
    solver.prewarm_capacity(case.get("target_capacity", 3))
    warm_start = MidMpcPrimalWarmStart(**case["warm_start"]) if "warm_start" in case else None
    result = solver.solve(problem, primal_warm_start=warm_start)
    assert result.status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}
    assert result.ipopt_iterations < (10 if problem.static_field is not None else 40)
    assert result.optimization_quality_passed
    assert result.max_constraint_violation < 1e-4
    assert result.max_decision_bound_violation < 1e-7
    assert result.raw_cpa_slack == 0.0
    assert result.raw_dir_slack == 0.0
    assert np.isfinite(result.raw_x).all()
    if problem.static_field is None:
        assert result.graph_cache_hit
    else:
        repeated = solver.solve(problem, primal_warm_start=warm_start)
        assert repeated.graph_cache_hit
        assert repeated.ipopt_iterations < 10
    speed_rows = slice(
        result.row_layout.speed_rate.start, result.row_layout.speed_rate.start + result.row_layout.speed_rate.count
    )
    assert np.min(result.raw_g[speed_rows]) >= -1e-6
    for i, target in enumerate(problem.targets):
        if not target.crossing_astern_required:
            assert np.isneginf(result.prepared.lbg[result.row_layout.rule.start + i])
        else:
            assert result.prepared.lbg[result.row_layout.rule.start + i] == 0.0
