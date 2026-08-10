"""Validation and loading for the frozen MASS-L3 Mid-MPC parity corpus."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FIXTURE_SCHEMA = "colav.mid_mpc_ipopt_parity.v1"
FROZEN_MASS_COMMIT = "ced58f8576f3772ef7c1bc72bb0f8b0368688b5a"
_TOLERANCE_KEYS = frozenset({"objective_abs", "trajectory_abs", "diagnostic_abs"})
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
_NORMALIZED_KEYS = frozenset(
    {
        "lateral_active",
        "preferred_side",
        "starboard_asymmetry_active",
        "row_schedule",
        "audit_row_count",
    }
)
_ROW_SCHEDULE_KEYS = frozenset(
    {
        "prefix_softening",
        "cpa_hard_from_k",
        "direction_hard_from_k",
        "min_alt_hard_from_k",
        "terminal_rows_enabled",
    }
)
_OBJECTIVE_COMPONENT_KEYS = frozenset(
    {
        "colreg",
        "heading",
        "speed",
        "route",
        "asymmetry",
        "terminal",
        "cpa_slack",
        "direction_slack",
    }
)


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


def _require_fields(value: Mapping[str, Any], required: frozenset[str], field: str) -> None:
    missing = required - value.keys()
    if missing:
        missing_path = ", ".join(f"{field}.{name}" for name in sorted(missing))
        raise MidMpcParityFixtureError(f"missing fields: {missing_path}")


def _validate_provenance(value: object) -> dict[str, str]:
    provenance = _require_mapping(value, "provenance")
    _require_fields(provenance, _PROVENANCE_KEYS, "provenance")
    if provenance["source_commit"] != FROZEN_MASS_COMMIT:
        raise MidMpcParityFixtureError(f"provenance.source_commit must equal frozen MASS-L3 commit {FROZEN_MASS_COMMIT}")
    for key in _PROVENANCE_KEYS:
        if not isinstance(provenance[key], str) or not provenance[key].strip():
            raise MidMpcParityFixtureError(f"provenance.{key} must be a non-empty string")
    return {key: str(provenance[key]) for key in _PROVENANCE_KEYS}


def _validate_tolerances(value: object) -> dict[str, float]:
    tolerances = _require_mapping(value, "tolerances")
    if set(tolerances) != _TOLERANCE_KEYS:
        raise MidMpcParityFixtureError("tolerances must contain exactly: " + ", ".join(sorted(_TOLERANCE_KEYS)))

    parsed: dict[str, float] = {}
    for key in sorted(_TOLERANCE_KEYS):
        value = tolerances[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MidMpcParityFixtureError(f"tolerances.{key} must be numeric")
        number = float(value)
        if not math.isfinite(number) or number <= 0.0:
            raise MidMpcParityFixtureError(f"tolerances.{key} must be finite and greater than zero")
        parsed[key] = number
    return parsed


def _validate_prepared_output(output: Mapping[str, Any]) -> Mapping[str, Any]:
    prepared = _require_mapping(output.get("prepared"), "output.prepared")
    _require_fields(prepared, _PREPARED_KEYS, "prepared")
    for key in _PREPARED_KEYS:
        if not isinstance(prepared[key], list):
            raise MidMpcParityFixtureError(f"prepared.{key} must be an array")
    return prepared


def _validate_raw_output(output: Mapping[str, Any]) -> Mapping[str, Any]:
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
    return raw


def _validate_objective_components(output: Mapping[str, Any]) -> None:
    components = _require_mapping(output.get("objective_components"), "output.objective_components")
    _require_fields(components, _OBJECTIVE_COMPONENT_KEYS, "objective_components")
    for key in _OBJECTIVE_COMPONENT_KEYS:
        value = components[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MidMpcParityFixtureError(f"objective_components.{key} must be numeric")
        if not math.isfinite(float(value)):
            raise MidMpcParityFixtureError(f"objective_components.{key} must be finite")


def _validate_output(value: object) -> Mapping[str, Any]:
    output = _require_mapping(value, "output")
    if not output:
        raise MidMpcParityFixtureError("output must not be empty")

    prepared = _validate_prepared_output(output)
    raw = _validate_raw_output(output)
    _validate_objective_components(output)
    if not (len(prepared["lbg"]) == len(prepared["ubg"]) == len(raw["g"])):
        raise MidMpcParityFixtureError("prepared lbg/ubg and raw.g must have equal lengths")
    _require_mapping(output.get("row_layout"), "output.row_layout")
    return output


def _validate_problem_input(problem_input: Mapping[str, Any]) -> None:
    problem = _require_mapping(problem_input.get("problem"), "input.problem")
    normalized = _require_mapping(problem.get("normalized"), "input.problem.normalized")
    _require_fields(normalized, _NORMALIZED_KEYS, "normalized")
    row_schedule = _require_mapping(normalized.get("row_schedule"), "normalized.row_schedule")
    _require_fields(row_schedule, _ROW_SCHEDULE_KEYS, "normalized.row_schedule")


def validate_mid_mpc_parity_record(record: object) -> MidMpcParityFixture:
    """Validate one decoded JSONL record against the frozen oracle contract."""
    root = _require_mapping(record, "fixture")
    if root.get("schema") != FIXTURE_SCHEMA:
        raise MidMpcParityFixtureError(f"schema must be {FIXTURE_SCHEMA!r}, got {root.get('schema')!r}")

    fixture_id = root.get("fixture_id")
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        raise MidMpcParityFixtureError("fixture_id must be a non-empty string")

    provenance = _validate_provenance(root.get("provenance"))
    tolerances = _validate_tolerances(root.get("tolerances"))

    problem_input = _require_mapping(root.get("input"), "input")
    if not problem_input:
        raise MidMpcParityFixtureError("input must not be empty")
    _validate_problem_input(problem_input)
    output = _validate_output(root.get("output"))

    return MidMpcParityFixture(
        fixture_id=fixture_id,
        provenance=provenance,
        tolerances=tolerances,
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
                raise MidMpcParityFixtureError(f"{corpus_path}:{line_number}: invalid JSON: {exc.msg}") from exc
            except MidMpcParityFixtureError as exc:
                raise MidMpcParityFixtureError(f"{corpus_path}:{line_number}: {exc}") from exc
            if fixture.fixture_id in seen_ids:
                raise MidMpcParityFixtureError(f"{corpus_path}:{line_number}: duplicate fixture_id {fixture.fixture_id!r}")
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
