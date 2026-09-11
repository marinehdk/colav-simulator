"""Unit-aware, fail-closed comparison for independently recorded GNC traces."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldRule:
    unit: str
    absolute: float = 0.0
    relative: float = 0.0
    circular: bool = False
    discrete: bool = False

    def __post_init__(self) -> None:
        """Reject undefined units and tolerances that could create false passes."""
        if not self.unit or any(not math.isfinite(v) or v < 0.0 for v in (self.absolute, self.relative)):
            raise ValueError("Comparison rules require a unit and finite non-negative tolerances")


# v1 acceptance rules, fixed before producing migration results. Internal
# integrators must get an explicit rule with their actual units before use.
FIELD_RULES = {
    "north_m": FieldRule("m", 1e-6, 1e-10),
    "east_m": FieldRule("m", 1e-6, 1e-10),
    "surge_mps": FieldRule("m/s", 1e-8, 1e-9),
    "sway_mps": FieldRule("m/s", 1e-8, 1e-9),
    "heading_rad": FieldRule("rad", 1e-8, circular=True),
    "roll_rad": FieldRule("rad", 1e-8, circular=True),
    "rudder_rad": FieldRule("rad", 1e-8),
    "yaw_rate_radps": FieldRule("rad/s", 1e-9, 1e-9),
    "roll_rate_radps": FieldRule("rad/s", 1e-9, 1e-9),
    "surge_n": FieldRule("N", 1e-3, 1e-8),
    "sway_n": FieldRule("N", 1e-3, 1e-8),
    "yaw_nm": FieldRule("N.m", 1e-2, 1e-8),
    "roll_nm": FieldRule("N.m", 1e-2, 1e-8),
    "mode": FieldRule("enum", discrete=True),
    "segment_index": FieldRule("index", discrete=True),
    "allocation_level": FieldRule("enum", discrete=True),
    "accepted": FieldRule("bool", discrete=True),
    "reason": FieldRule("enum", discrete=True),
}


def compare_trace(  # noqa: PLR0912
    reference: Sequence[Mapping[str, Any]],
    embedded: Sequence[Mapping[str, Any]],
    rules: Mapping[str, FieldRule],
) -> dict[str, Any]:
    """Compare records at their exact event keys; never fill missing fields.

    ``event`` is a stable callback identity and ``tick`` the original internal
    update index. Native asynchronous topic captures must first be converted by
    a separately validated replay driver; this is not a time-alignment fitter.
    """
    if not rules:
        raise ValueError("At least one explicit field rule is required")
    errors: list[dict[str, Any]] = []
    if not reference or not embedded:
        errors.append({"kind": "empty_trace"})
    if len(reference) != len(embedded):
        errors.append({"kind": "record_count", "reference": len(reference), "embedded": len(embedded)})
    stats = {name: {"checked": 0, "finite_numeric": 0, "missing": 0, "failed": 0, "max_abs_error": 0.0} for name in rules}
    squared_errors = dict.fromkeys(rules, 0.0)
    for index, (left, right) in enumerate(zip(reference, embedded, strict=False)):
        for key in ("event", "tick"):
            if key not in left or key not in right or type(left[key]) is not type(right[key]) or left[key] != right[key]:
                errors.append(
                    {
                        "kind": "event_identity",
                        "index": index,
                        "field": key,
                        "reference": left.get(key),
                        "embedded": right.get(key),
                    }
                )
        for name, rule in rules.items():
            stat = stats[name]
            if name not in left or name not in right or left[name] is None or right[name] is None:
                stat["missing"] += 1
                errors.append({"kind": "missing_field", "index": index, "field": name})
                continue
            a, b = left[name], right[name]
            stat["checked"] += 1
            if rule.discrete:
                if type(a) is not type(b) or a != b:
                    stat["failed"] += 1
                    errors.append(
                        {"kind": "discrete_difference", "index": index, "field": name, "reference": a, "embedded": b}
                    )
                continue
            if (
                isinstance(a, bool)
                or isinstance(b, bool)
                or not isinstance(a, (int, float))
                or not isinstance(b, (int, float))
                or not math.isfinite(a)
                or not math.isfinite(b)
            ):
                stat["failed"] += 1
                errors.append({"kind": "nonfinite_or_nonnumeric", "index": index, "field": name})
                continue
            delta = float(b) - float(a)
            stat["finite_numeric"] += 1
            error = abs(math.remainder(delta, 2 * math.pi) if rule.circular else delta)
            tolerance = rule.absolute + rule.relative * abs(float(a))
            stat["max_abs_error"] = max(stat["max_abs_error"], error)
            squared_errors[name] += error * error
            if error > tolerance:
                stat["failed"] += 1
                errors.append(
                    {
                        "kind": "numerical_difference",
                        "index": index,
                        "field": name,
                        "reference": a,
                        "embedded": b,
                        "absolute_error": error,
                        "tolerance": tolerance,
                        "unit": rule.unit,
                    }
                )
    for name, stat in stats.items():
        valid = stat["finite_numeric"]
        stat["rmse"] = None if not valid or rules[name].discrete else math.sqrt(squared_errors[name] / valid)
    return {
        "schema": "original-gnc.trace-comparison.v1",
        "passed": not errors,
        "reference_records": len(reference),
        "embedded_records": len(embedded),
        "field_rules": {
            name: {
                "unit": rule.unit,
                "absolute": rule.absolute,
                "relative": rule.relative,
                "circular": rule.circular,
                "discrete": rule.discrete,
            }
            for name, rule in rules.items()
        },
        "fields": stats,
        "error_count": len(errors),
        "first_difference": errors[0] if errors else None,
    }
