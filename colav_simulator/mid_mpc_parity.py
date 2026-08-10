"""Validation and loading for the frozen MASS-L3 Mid-MPC parity corpus."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping


FIXTURE_SCHEMA = "colav.mid_mpc_ipopt_parity.v1"
FROZEN_MASS_COMMIT = "ced58f8576f3772ef7c1bc72bb0f8b0368688b5a"
_TOLERANCE_KEYS = frozenset(
    {"objective_abs", "trajectory_abs", "diagnostic_abs"}
)
_PROVENANCE_KEYS = frozenset(
    {
        "source_repository",
        "source_commit",
        "oracle",
        "optimizer",
        "casadi_version",
        "ipopt_version",
        "exporter",
    }
)
_PREPARED_KEYS = frozenset({"p", "x0", "lbx", "ubx", "lbg", "ubg"})
_RAW_KEYS = frozenset({"x", "f", "g", "cpa_slack", "dir_slack"})


class MidMpcParityFixtureError(ValueError):
    """Raised when a parity fixture is malformed or has drifted provenance."""


@dataclass(frozen=True)
class MidMpcParityFixture:
    """One validated input/output observation from the frozen C++ oracle."""

    fixture_id: str
    provenance: Mapping[str, str]
    tolerances: Mapping[str, float]
    input: Mapping[str, Any]
    output: Mapping[str, Any]

    @property
    def source_commit(self) -> str:
        return self.provenance["source_commit"]


def _require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MidMpcParityFixtureError(f"{field} must be a JSON object")
    return value


def _require_fields(
    value: Mapping[str, Any], required: frozenset[str], field: str
) -> None:
    missing = required - value.keys()
    if missing:
        missing_path = ", ".join(f"{field}.{name}" for name in sorted(missing))
        raise MidMpcParityFixtureError(f"missing fields: {missing_path}")


def validate_mid_mpc_parity_record(record: object) -> MidMpcParityFixture:
    """Validate one decoded JSONL record against the frozen oracle contract."""

    root = _require_mapping(record, "fixture")
    if root.get("schema") != FIXTURE_SCHEMA:
        raise MidMpcParityFixtureError(
            f"schema must be {FIXTURE_SCHEMA!r}, got {root.get('schema')!r}"
        )

    fixture_id = root.get("fixture_id")
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        raise MidMpcParityFixtureError("fixture_id must be a non-empty string")

    provenance = _require_mapping(root.get("provenance"), "provenance")
    missing_provenance = _PROVENANCE_KEYS - provenance.keys()
    if missing_provenance:
        missing = ", ".join(sorted(missing_provenance))
        raise MidMpcParityFixtureError(f"provenance missing fields: {missing}")
    if provenance["source_commit"] != FROZEN_MASS_COMMIT:
        raise MidMpcParityFixtureError(
            "provenance.source_commit must equal frozen MASS-L3 commit "
            f"{FROZEN_MASS_COMMIT}"
        )
    for key in _PROVENANCE_KEYS:
        if not isinstance(provenance[key], str) or not provenance[key].strip():
            raise MidMpcParityFixtureError(
                f"provenance.{key} must be a non-empty string"
            )

    tolerances = _require_mapping(root.get("tolerances"), "tolerances")
    if set(tolerances) != _TOLERANCE_KEYS:
        raise MidMpcParityFixtureError(
            "tolerances must contain exactly: "
            + ", ".join(sorted(_TOLERANCE_KEYS))
        )
    parsed_tolerances: dict[str, float] = {}
    for key in sorted(_TOLERANCE_KEYS):
        value = tolerances[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MidMpcParityFixtureError(f"tolerances.{key} must be numeric")
        number = float(value)
        if not math.isfinite(number) or number <= 0.0:
            raise MidMpcParityFixtureError(
                f"tolerances.{key} must be finite and greater than zero"
            )
        parsed_tolerances[key] = number

    problem_input = _require_mapping(root.get("input"), "input")
    output = _require_mapping(root.get("output"), "output")
    if not problem_input:
        raise MidMpcParityFixtureError("input must not be empty")
    if not output:
        raise MidMpcParityFixtureError("output must not be empty")

    prepared = _require_mapping(output.get("prepared"), "output.prepared")
    _require_fields(prepared, _PREPARED_KEYS, "prepared")
    for key in _PREPARED_KEYS:
        if not isinstance(prepared[key], list):
            raise MidMpcParityFixtureError(f"prepared.{key} must be an array")

    raw = _require_mapping(output.get("raw"), "output.raw")
    _require_fields(raw, _RAW_KEYS, "raw")
    for key in ("x", "g"):
        if not isinstance(raw[key], list):
            raise MidMpcParityFixtureError(f"raw.{key} must be an array")
    for key in ("f", "cpa_slack", "dir_slack"):
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MidMpcParityFixtureError(f"raw.{key} must be numeric")
        if not math.isfinite(float(value)):
            raise MidMpcParityFixtureError(f"raw.{key} must be finite")
    if not (
        len(prepared["lbg"]) == len(prepared["ubg"]) == len(raw["g"])
    ):
        raise MidMpcParityFixtureError(
            "prepared lbg/ubg and raw.g must have equal lengths"
        )

    _require_mapping(output.get("row_layout"), "output.row_layout")

    return MidMpcParityFixture(
        fixture_id=fixture_id,
        provenance={key: str(provenance[key]) for key in _PROVENANCE_KEYS},
        tolerances=parsed_tolerances,
        input=problem_input,
        output=output,
    )


def load_mid_mpc_parity_corpus(path: str | Path) -> tuple[MidMpcParityFixture, ...]:
    """Load and validate a JSONL corpus, rejecting duplicate fixture ids."""

    corpus_path = Path(path)
    fixtures: list[MidMpcParityFixture] = []
    seen_ids: set[str] = set()
    with corpus_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                fixture = validate_mid_mpc_parity_record(record)
            except json.JSONDecodeError as exc:
                raise MidMpcParityFixtureError(
                    f"{corpus_path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            except MidMpcParityFixtureError as exc:
                raise MidMpcParityFixtureError(
                    f"{corpus_path}:{line_number}: {exc}"
                ) from exc
            if fixture.fixture_id in seen_ids:
                raise MidMpcParityFixtureError(
                    f"{corpus_path}:{line_number}: duplicate fixture_id "
                    f"{fixture.fixture_id!r}"
                )
            seen_ids.add(fixture.fixture_id)
            fixtures.append(fixture)

    if not fixtures:
        raise MidMpcParityFixtureError(f"{corpus_path}: corpus is empty")
    return tuple(fixtures)


__all__ = [
    "FIXTURE_SCHEMA",
    "FROZEN_MASS_COMMIT",
    "MidMpcParityFixture",
    "MidMpcParityFixtureError",
    "load_mid_mpc_parity_corpus",
    "validate_mid_mpc_parity_record",
]
