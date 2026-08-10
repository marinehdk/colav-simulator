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
        "output": {"status": "Converged", "trajectory": []},
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


def test_frozen_cpp_corpus_is_valid_and_reviewable() -> None:
    fixtures = load_mid_mpc_parity_corpus(CORPUS_PATH)

    assert {fixture.fixture_id for fixture in fixtures} == {
        "route_speed_cold",
    }
    assert all(fixture.source_commit == FROZEN_MASS_COMMIT for fixture in fixtures)
