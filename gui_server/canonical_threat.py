"""Canonical backend threat projection shared by Live telemetry and Sealed Run Replay.

Extracted verbatim from ``gui_server.main`` (ticket #71) so the live stream and
the replay window project the adapter-published threat document through ONE
canonical function — no second risk interpretation layer. The module imports
only the standard library, keeping the sealed replay read path free of
simulator/planner runtime.

The optional ``normalize`` hook preserves the live path's ``jsonable``
detachment of runtime dataclasses/arrays; the replay read path passes stored
JSON documents (where normalization is a pure deep copy).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

THREAT_PROJECTION_SCHEMA = "colav.threat-management.projection@1"

Normalize = Callable[[Any], Any]


def _native_detach(value: Any) -> Any:
    return copy.deepcopy(value)


def threat_unavailable(
    reason: str = "THREAT_SNAPSHOT_UNAVAILABLE", *, normalize: Normalize | None = None
) -> dict[str, Any]:
    """Typed canonical UNAVAILABLE document; no implicit zero/available facts."""
    detach = normalize or _native_detach
    return {
        "schema_version": THREAT_PROJECTION_SCHEMA,
        "status": "UNAVAILABLE",
        "snapshot": None,
        "vectors": detach([]),
        "schedule": None,
        "conflicts": None,
        "conflict_graph": None,
        "unavailable_reason": reason,
    }


def canonical_threat_projection(
    colav_data: dict[str, Any],
    planner: dict[str, Any],
    *,
    normalize: Normalize | None = None,
) -> dict[str, Any]:
    """Project only a canonical backend threat document for consumers."""
    detach = normalize or _native_detach
    candidate = (
        planner.get("threat_management")
        or planner.get("algorithm_details", {}).get("threat_management")
        or colav_data.get("threat_management")
    )
    if not isinstance(candidate, dict):
        return threat_unavailable(normalize=normalize)
    snapshot = candidate.get("snapshot")
    if snapshot is None and "vectors" in candidate:
        snapshot = candidate
    vectors = snapshot.get("vectors", []) if isinstance(snapshot, dict) else []
    schedule = candidate.get("schedule")
    if schedule is None and isinstance(snapshot, dict):
        schedule = snapshot.get("schedule")
    conflicts = candidate.get("conflicts", candidate.get("conflict_graph"))
    if conflicts is None and isinstance(snapshot, dict):
        conflicts = snapshot.get("conflicts", snapshot.get("conflict_graph"))
    available = candidate.get("status") == "AVAILABLE" or isinstance(snapshot, dict)
    graph = detach(conflicts) if isinstance(conflicts, (dict, list)) else None
    return {
        "schema_version": THREAT_PROJECTION_SCHEMA,
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "snapshot": detach(snapshot) if isinstance(snapshot, dict) else None,
        "vectors": detach(vectors) if isinstance(vectors, list) else [],
        "schedule": detach(schedule) if isinstance(schedule, dict) else None,
        "conflicts": graph,
        "conflict_graph": graph,
        "unavailable_reason": None if available else candidate.get("unavailable_reason", "THREAT_SNAPSHOT_UNAVAILABLE"),
    }
