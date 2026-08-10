from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from colav_simulator.mid_mpc_parity import (
    FIXTURE_SCHEMA,
    FROZEN_MASS_COMMIT,
    MidMpcParityFixtureError,
    load_mid_mpc_parity_corpus,
)


CORPUS_PATH = Path(__file__).parent / "fixtures" / "mid_mpc_ipopt" / "v1.jsonl"


def _fixture_record() -> dict[str, object]:
    return {
        "schema": FIXTURE_SCHEMA,
        "fixture_id": "route_speed_cold",
        "provenance": {
            "source_repository": (
                "https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation"
            ),
            "source_commit": FROZEN_MASS_COMMIT,
            "oracle": "mass_l3_mid_mpc_cpp",
            "optimizer": "CasADi/IPOPT",
            "casadi_version": "3.7.2",
            "ipopt_version": "3.14.11",
            "exporter": "tools/mid_mpc_ipopt_oracle/export_oracle.sh",
        },
        "tolerances": {
            "objective_abs": 1e-5,
            "trajectory_abs": 1e-6,
            "diagnostic_abs": 1e-6,
        },
        "input": {"config": {"N": 4, "dt": 5.0}, "problem": {"targets": []}},
        "output": {
            "status": "Converged",
            "ipopt_return_status": "Solve_Succeeded",
            "ipopt_iterations": 1,
            "objective_total": 0.0,
            "cpa_slack": 0.0,
            "continuous_cpa_min_m": "Infinity",
            "continuous_cpa_violated": False,
            "trajectory": [],
            "prepared": {
                "p": [],
                "x0": [],
                "lbx": [],
                "ubx": [],
                "lbg": [],
                "ubg": [],
            },
            "raw": {
                "x": [],
                "f": 0.0,
                "g": [],
                "cpa_slack": 0.0,
                "dir_slack": 0.0,
            },
            "row_layout": {},
        },
    }


def _write_jsonl(path: Path, *records: dict[str, object]) -> None:
    path.write_text(
        "".join(json.dumps(record, allow_nan=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_loads_valid_fixture_with_frozen_provenance(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(corpus_path, _fixture_record())

    fixtures = load_mid_mpc_parity_corpus(corpus_path)

    assert len(fixtures) == 1
    assert fixtures[0].fixture_id == "route_speed_cold"
    assert fixtures[0].source_commit == FROZEN_MASS_COMMIT
    assert fixtures[0].tolerances["trajectory_abs"] == 1e-6


def test_rejects_fixture_from_another_source_commit(tmp_path: Path) -> None:
    record = _fixture_record()
    record["provenance"]["source_commit"] = "0" * 40  # type: ignore[index]
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(corpus_path, record)

    with pytest.raises(MidMpcParityFixtureError, match="source_commit"):
        load_mid_mpc_parity_corpus(corpus_path)


def test_rejects_unknown_fixture_schema(tmp_path: Path) -> None:
    record = _fixture_record()
    record["schema"] = "colav.mid_mpc_ipopt_parity.v2"
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(corpus_path, record)

    with pytest.raises(MidMpcParityFixtureError, match="schema"):
        load_mid_mpc_parity_corpus(corpus_path)


@pytest.mark.parametrize("invalid", [0.0, -1e-6, math.nan, math.inf])
def test_rejects_non_positive_or_non_finite_tolerance(
    tmp_path: Path, invalid: float
) -> None:
    record = _fixture_record()
    record["tolerances"]["trajectory_abs"] = invalid  # type: ignore[index]
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(corpus_path, record)

    with pytest.raises(MidMpcParityFixtureError, match="trajectory_abs"):
        load_mid_mpc_parity_corpus(corpus_path)


def test_rejects_duplicate_fixture_ids(tmp_path: Path) -> None:
    record = _fixture_record()
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(corpus_path, record, record)

    with pytest.raises(MidMpcParityFixtureError, match="duplicate fixture_id"):
        load_mid_mpc_parity_corpus(corpus_path)


def test_rejects_fixture_missing_raw_direction_slack(tmp_path: Path) -> None:
    record = _fixture_record()
    del record["output"]["raw"]["dir_slack"]  # type: ignore[index]
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(corpus_path, record)

    with pytest.raises(MidMpcParityFixtureError, match="raw.dir_slack"):
        load_mid_mpc_parity_corpus(corpus_path)


def test_frozen_cpp_corpus_is_valid_and_reviewable() -> None:
    fixtures = load_mid_mpc_parity_corpus(CORPUS_PATH)

    assert {fixture.fixture_id for fixture in fixtures} == {
        "active_prefix_k2",
        "close_target_cpa_slack",
        "crossing_starboard",
        "head_on_starboard",
        "multi_target_row_order",
        "overtaking_port",
        "route_speed_cold",
        "stand_on_hold",
    }
    assert all(fixture.source_commit == FROZEN_MASS_COMMIT for fixture in fixtures)


def test_dynamic_fixtures_export_prepared_arrays_and_raw_solver_diagnostics() -> None:
    fixtures = {
        fixture.fixture_id: fixture
        for fixture in load_mid_mpc_parity_corpus(CORPUS_PATH)
    }

    for fixture_id, fixture in fixtures.items():
        prepared = fixture.output["prepared"]
        raw = fixture.output["raw"]
        assert set(prepared) == {"p", "x0", "lbx", "ubx", "lbg", "ubg"}
        assert set(raw) >= {"x", "f", "g", "cpa_slack", "dir_slack"}
        assert len(prepared["lbg"]) == len(prepared["ubg"]) == len(raw["g"])
        assert raw["f"] == pytest.approx(
            fixture.output["objective_total"],
            abs=fixture.tolerances["objective_abs"],
        ), fixture_id


def test_dynamic_fixture_rows_encode_requested_activation_families() -> None:
    fixtures = {
        fixture.fixture_id: fixture
        for fixture in load_mid_mpc_parity_corpus(CORPUS_PATH)
    }

    for fixture_id in ("head_on_starboard", "crossing_starboard"):
        fixture = fixtures[fixture_id]
        direction = fixture.output["row_layout"]["direction"]
        first = direction["start"]
        assert fixture.output["prepared"]["lbg"][first] == 0
        assert fixture.input["problem"]["preferred_direction"] == "Starboard"

    stand_on = fixtures["stand_on_hold"]
    first_direction = stand_on.output["row_layout"]["direction"]["start"]
    assert stand_on.output["prepared"]["lbg"][first_direction] == "-Infinity"
    assert stand_on.output["prepared"]["ubg"][first_direction] == "Infinity"

    overtaking = fixtures["overtaking_port"]
    assert overtaking.input["problem"]["preferred_direction"] == "Port"

    slack = fixtures["close_target_cpa_slack"]
    assert slack.output["raw"]["cpa_slack"] > 0
    assert slack.output["cpa_slack"] > 0

    prefix = fixtures["active_prefix_k2"]
    prefix_psi = prefix.output["row_layout"]["prefix_psi"]
    for row in range(prefix_psi["start"], prefix_psi["start"] + 2):
        assert prefix.output["prepared"]["lbg"][row] == 0
        assert prefix.output["prepared"]["ubg"][row] == 0

    multi = fixtures["multi_target_row_order"]
    assert len(multi.input["problem"]["targets"]) == 2
    assert multi.output["row_layout"]["cpa"]["count"] == (
        multi.input["config"]["N"] * 2
    )
