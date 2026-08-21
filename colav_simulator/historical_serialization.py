"""Canonical serialization shared by Historical AIS evidence contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


def jsonable(value: Any) -> Any:  # noqa: PLR0911
    """Project Historical evidence values onto one deterministic JSON domain."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        raw = value if isinstance(value, bytes) else value.tobytes()
        return {"__bytes_hex__": raw.hex()}
    if isinstance(value, Enum):
        return jsonable(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if hasattr(value, "to_dict"):
        return jsonable(value.to_dict())
    if hasattr(value, "item"):
        return jsonable(value.item())
    if hasattr(value, "tolist"):
        return jsonable(value.tolist())
    return str(value)


def canonical_json(value: Any) -> str:
    """Serialize Historical evidence using stable keys and separators."""
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))


def semantic_hash(value: Any) -> str:
    """Return SHA-256 over canonical Historical JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


__all__ = ["canonical_json", "jsonable", "semantic_hash"]
