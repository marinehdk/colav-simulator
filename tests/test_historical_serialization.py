from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

import pytest

from colav_simulator.historical_serialization import angle_delta, canonical_json, semantic_hash


class _GoldenKind(str, Enum):
    OBSERVED = "observed"


def test_historical_canonical_json_preserves_golden_special_values() -> None:
    value = {
        "bytes": b"\x00\xff",
        "date": date(2026, 7, 1),
        "datetime": datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        "decimal": Decimal("1.230"),
        "enum": _GoldenKind.OBSERVED,
        "memory": memoryview(b"\x01\x02"),
    }
    expected = (
        '{"bytes":{"__bytes_hex__":"00ff"},"date":"2026-07-01",'
        '"datetime":"2026-07-01T12:00:00+00:00","decimal":"1.230",'
        '"enum":"observed","memory":{"__bytes_hex__":"0102"}}'
    )

    assert canonical_json(value) == expected
    assert semantic_hash(value) == hashlib.sha256(expected.encode("utf-8")).hexdigest()


def test_angle_delta_has_stable_wrapped_boundary() -> None:
    assert angle_delta(math.pi, -math.pi) == 0.0
    assert angle_delta(-math.pi, math.pi) == 0.0
    assert angle_delta(math.radians(179.0), math.radians(-179.0)) == pytest.approx(math.radians(-2.0))
    assert angle_delta(math.radians(-179.0), math.radians(179.0)) == pytest.approx(math.radians(2.0))
