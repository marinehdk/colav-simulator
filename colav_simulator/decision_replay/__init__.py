"""Offline decision-replay harness.

Record one headless run with full per-tick decision evidence, then answer
every per-tick decision question offline without re-running the simulation.

    from colav_simulator.decision_replay import TraceBundle, probes
    bundle = TraceBundle("runs/<run_id>")
    probes.startup_timeline(bundle, seconds=30)
    probes.why_primary(bundle, at=7.0)
"""

from __future__ import annotations

from typing import Any

from colav_simulator.decision_replay.bundle import TraceBundle

__all__ = [  # noqa: F822 — lazily resolved by __getattr__ below
    "TraceBundle",
    "RecordResult",
    "record",
    "startup_timeline",
    "why_primary",
    "target_chain",
    "planner_timeline",
    "risk_transitions",
    "explain_tick",
    "compare_runs",
]

# Ticket #71: the probes/recorder submodules pull the simulator/planner
# runtime, while the bundle reader is stdlib-only and shared with the sealed
# replay read path. They stay importable under the package API (PEP 562 lazy
# attributes) so "replay reads import no simulator runtime" is structural
# rather than conventional.
_LAZY_EXPORTS = {
    "RecordResult": ("colav_simulator.decision_replay.recorder", "RecordResult"),
    "record": ("colav_simulator.decision_replay.recorder", "record"),
    "startup_timeline": ("colav_simulator.decision_replay.probes", "startup_timeline"),
    "why_primary": ("colav_simulator.decision_replay.probes", "why_primary"),
    "target_chain": ("colav_simulator.decision_replay.probes", "target_chain"),
    "planner_timeline": ("colav_simulator.decision_replay.probes", "planner_timeline"),
    "risk_transitions": ("colav_simulator.decision_replay.probes", "risk_transitions"),
    "explain_tick": ("colav_simulator.decision_replay.probes", "explain_tick"),
    "compare_runs": ("colav_simulator.decision_replay.probes", "compare_runs"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        from importlib import import_module  # noqa: PLC0415 — lazy import is the point

        module_name, attribute = _LAZY_EXPORTS[name]
        return getattr(import_module(module_name), attribute)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
