"""Issue #67 stack B acceptance matrix: OT/HO/CS x VO/Fan-MPC/Mid-MPC.

Each cell injects the FCB45 ownship GNC stack
(fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid, ideal actuator)
plus the acceptance spacing profile (config/acceptance_issue67_*.yaml) and
must satisfy the Issue #67 gate with spec-sourced thresholds:

- goal reached, no collision and no grounding events;
- whole-encounter ownship-target minimum centre distance >= 180 m
  (4 x 44.1 m Lpp);
- return-voyage max |XTE| against the original route <= 50 m;
- route-line crossings within the return window <= 2 (no S-shaped sawtooth).

t_end is extended to 1200 s: the longest ownship route (overtaking,
6727 m at 8 m/s = 841 s straight-line) cannot reach its goal inside the
scenario's 600 s default once avoidance detours are included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import PROJECT_ROOT, P1RunHarness

from colav_simulator.cli import _load_algorithm_config

if TYPE_CHECKING:
    from colav_simulator.experiment.runner import RunResult

ACCEPTANCE_STACK_ID = "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid"
ACCEPTANCE_T_END_S = 1200.0
MIN_ENCOUNTER_CENTER_DISTANCE_M = 180.0  # 4 x 44.1 m Lpp (Issue #67).
MAX_RETURN_XTE_M = 50.0
MAX_ROUTE_CROSSINGS = 2

ACCEPTANCE_PROFILES = {
    "vo": _load_algorithm_config(PROJECT_ROOT / "config/acceptance_issue67_vo.yaml"),
    "potocnik_colreg_fan_mpc": _load_algorithm_config(
        PROJECT_ROOT / "config/acceptance_issue67_fan_mpc.yaml"
    ),
    "mid_mpc_ipopt": _load_algorithm_config(PROJECT_ROOT / "config/acceptance_issue67_mid_mpc.yaml"),
}
ACCEPTANCE_SOLVE_PERIODS = {
    "vo": None,
    "potocnik_colreg_fan_mpc": 5.0,
    "mid_mpc_ipopt": 5.0,
}
SCENARIO_IDS = ("overtaking", "head_on", "crossing_give_way")
ALGORITHM_IDS = ("vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt")


def run_acceptance_cell(
    harness: P1RunHarness,
    scenario_id: str,
    algorithm_id: str,
) -> RunResult:
    return harness.run(
        scenario_id,
        algorithm_id,
        "god",
        algorithm_config=ACCEPTANCE_PROFILES[algorithm_id],
        solve_period_s=ACCEPTANCE_SOLVE_PERIODS[algorithm_id],
        ownship_gnc_stack_id=ACCEPTANCE_STACK_ID,
        t_end=ACCEPTANCE_T_END_S,
    )


def cell_metrics(result: RunResult) -> dict[str, float | int | None]:
    voyage = result.evaluation.voyage
    return_voyage = voyage["return_voyage"]
    return {
        "min_center_distance_m": voyage["encounter"]["min_target_center_distance_m"],
        "max_abs_xte_m": None if return_voyage is None else return_voyage["max_abs_xte_m"],
        "route_crossings": None if return_voyage is None else return_voyage["route_crossings"],
    }


def assert_acceptance_cell(result: RunResult) -> None:
    events = {event["type"] for event in result.session.events}
    assert "goal_reached" in events, sorted(events)
    assert not {"collision", "grounding", "run_failed", "session_failed"} & events, sorted(events)

    assert result.manifest.state.value == "FINISHED"
    assert result.manifest.execution_outcome.value == "COMPLETED"
    assert result.manifest.fallback_used is False
    assert result.manifest.requested_algorithm == result.manifest.executed_algorithm

    voyage = result.evaluation.voyage
    assert voyage["encounter"]["min_target_center_distance_m"] is not None
    assert voyage["encounter"]["min_target_center_distance_m"] >= MIN_ENCOUNTER_CENTER_DISTANCE_M

    return_voyage = voyage["return_voyage"]
    assert return_voyage is not None, "runner must feed the ownship mission route to the evaluator"
    assert return_voyage["sample_count"] > 0
    assert return_voyage["max_abs_xte_m"] is not None
    assert return_voyage["max_abs_xte_m"] <= MAX_RETURN_XTE_M
    assert return_voyage["route_crossings"] is not None
    assert return_voyage["route_crossings"] <= MAX_ROUTE_CROSSINGS


def test_smoke_vo_head_on_acceptance_cell(p1_run_harness: P1RunHarness) -> None:
    result = run_acceptance_cell(p1_run_harness, "head_on", "vo")
    assert_acceptance_cell(result)


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
@pytest.mark.parametrize("algorithm_id", ALGORITHM_IDS)
def test_acceptance_matrix_cell(
    p1_run_harness: P1RunHarness,
    algorithm_id: str,
    scenario_id: str,
) -> None:
    result = run_acceptance_cell(p1_run_harness, scenario_id, algorithm_id)
    assert_acceptance_cell(result)
