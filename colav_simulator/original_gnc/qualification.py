"""Explicit trajectory-basis qualification rule for measured response models.

Honesty gate for the original GNC backend's predictor claim (diagnostic policy:
docs/research/2026-09-11-original-gnc-diagnostic-policy.md). A channel qualifies
only when its closed-loop trajectory R^2 reaches TRAJECTORY_R_SQUARED_THRESHOLD
on the active maneuvering window. Derivative-basis R^2 stays in the artifact as
legacy evidence and is not the qualification basis: finite-difference
accelerations are structure-limited and cannot express predictor quality.

The verdict is always computed here from the numbers in the artifact. The
artifact's own ``qualification`` label is documentation and is never trusted by
code; tests pin the label to this computed verdict.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

TRAJECTORY_R_SQUARED_THRESHOLD = 0.90

_CHANNELS = ("course", "speed")
_QUALIFIED = "QUALIFIED_FIRST_ORDER_TRAJECTORY_APPROXIMATION"
_UNQUALIFIED = "UNQUALIFIED_TRAJECTORY_APPROXIMATION"
_ARTIFACT = Path(__file__).with_name("data") / "response_approximation.json"


def load_document() -> dict:
    """Load the packaged measured-response artifact with its content hash."""
    document = json.loads(_ARTIFACT.read_text())
    document["artifact_sha256"] = hashlib.sha256(_ARTIFACT.read_bytes()).hexdigest()
    return document


def channel_qualified(channel: dict) -> bool:
    """One channel qualifies on the trajectory basis at or above the threshold."""
    value = channel.get("trajectory_r_squared")
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= TRAJECTORY_R_SQUARED_THRESHOLD


def evaluate(document: dict) -> tuple[bool, tuple[str, ...]]:
    """Return (qualified, failing_channels) for the measured artifact."""
    failures = tuple(name for name in _CHANNELS if not channel_qualified(document.get(name) or {}))
    return not failures, failures


def verdict_string(document: dict) -> str:
    """Human-readable verdict label; callers must branch on evaluate(), not this string."""
    qualified, _ = evaluate(document)
    return _QUALIFIED if qualified else _UNQUALIFIED
