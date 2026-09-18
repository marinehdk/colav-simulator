"""Full Stack T700: preserve all hard rows while finding a chart-safe cold start."""

import gzip
import json
from pathlib import Path

from colav_simulator.core.colav.mid_mpc import models as m
from colav_simulator.core.colav.mid_mpc.solver import MidMpcIpoptSolver


def test_full_stack_chart_problem_has_optimizer_candidate_without_native_route_packet():
    path = Path(__file__).parent / "fixtures/mid_mpc_ipopt/three_ship_full_stack_t700.json.gz"
    values = json.loads(gzip.decompress(path.read_bytes()))
    for key, cls in (
        ("own_ship", m.MidMpcOwnShip),
        ("route_frame", m.MidMpcRouteFrame),
        ("route_objective", m.MidMpcRouteObjective),
        ("static_field", m.MidMpcStaticField),
    ):
        if values.get(key) is not None:
            values[key] = cls(**values[key])
    values["targets"] = tuple(m.MidMpcTarget(**target) for target in values["targets"])
    schedule = values["row_schedule"]
    schedule["cpa_hard_windows"] = tuple(m.MidMpcHardWindow(**window) for window in schedule["cpa_hard_windows"])
    for key in ("direction_hard_window", "min_alt_hard_window"):
        if schedule[key] is not None:
            schedule[key] = m.MidMpcHardWindow(**schedule[key])
    values["row_schedule"] = m.MidMpcRowSchedule(**schedule)
    problem = m.MidMpcProblem(**values)
    assert problem.static_field is not None
    assert problem.route_constraint_limit_m is None and not problem.timed_execution
    result = MidMpcIpoptSolver(m.MidMpcConfig(horizon_steps=80, dt_s=5, strict_slack_bounds=True)).solve(problem)
    assert result.status in (m.MidMpcStatus.CONVERGED, m.MidMpcStatus.FEASIBLE_NONOPTIMAL)
    assert result.max_constraint_violation < 1e-7
    assert result.max_decision_bound_violation < 1e-7
    assert result.raw_cpa_slack == result.raw_dir_slack == 0
    assert result.accepted_candidate_source == "IPOPT_BEST_FEASIBLE_ITERATE"
