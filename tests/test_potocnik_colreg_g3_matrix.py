from __future__ import annotations

import json

import pytest
from conftest import PROJECT_ROOT, P1RunHarness

from colav_simulator.cli import _load_algorithm_config

ALGORITHM_ID = "potocnik_colreg_fan_mpc"
ALGORITHM_CONFIG = _load_algorithm_config(PROJECT_ROOT / "config/potocnik_colreg_fan_mpc.yaml")


@pytest.mark.parametrize(
    "scenario_id",
    (
        "head_on",
        "overtaking",
        "overtaken",
        "crossing_give_way",
        "crossing_stand_on",
        "paper_ccta2023_multiship",
    ),
)
def test_colreg_fan_mpc_passes_raw_g3_safety_matrix(
    p1_run_harness: P1RunHarness,
    scenario_id: str,
) -> None:
    result = p1_run_harness.compare(
        scenario_id,
        ALGORITHM_ID,
        algorithm_config=ALGORITHM_CONFIG,
        solve_period_s=5.0,
    )

    assert result.passed, json.dumps(result.to_dict(), indent=2, sort_keys=True)
