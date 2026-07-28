from __future__ import annotations

import json

import pytest
from conftest import P1RunHarness


@pytest.mark.parametrize(
    "scenario_id",
    (
        "overtaking",
        "overtaken",
        "crossing_give_way",
        "crossing_stand_on",
    ),
)
@pytest.mark.parametrize("algorithm_id", ("vo", "sbmpc"))
def test_rule13_15_god_cells_pass_raw_g3(
    p1_run_harness: P1RunHarness,
    scenario_id: str,
    algorithm_id: str,
) -> None:
    result = p1_run_harness.compare(scenario_id, algorithm_id)

    assert result.passed, json.dumps(result.to_dict(), indent=2, sort_keys=True)
