from __future__ import annotations

import json

import pytest
from conftest import P1RunHarness


@pytest.mark.parametrize("algorithm_id", ("vo", "sbmpc"))
def test_multiship_god_cells_pass_raw_g3(
    p1_run_harness: P1RunHarness,
    algorithm_id: str,
) -> None:
    result = p1_run_harness.compare("paper_ccta2023_multiship", algorithm_id)

    assert len(result.metrics["candidate_clearance"]) == 3
    assert result.passed, json.dumps(result.to_dict(), indent=2, sort_keys=True)
