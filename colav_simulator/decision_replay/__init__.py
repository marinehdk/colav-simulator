"""Offline decision-replay harness.

Record one headless run with full per-tick decision evidence, then answer
every per-tick decision question offline without re-running the simulation.

    from colav_simulator.decision_replay import TraceBundle, probes
    bundle = TraceBundle("runs/<run_id>")
    probes.startup_timeline(bundle, seconds=30)
    probes.why_primary(bundle, at=7.0)
"""

from __future__ import annotations

from colav_simulator.decision_replay.bundle import TraceBundle
from colav_simulator.decision_replay.probes import (
    compare_runs,
    explain_tick,
    planner_timeline,
    risk_transitions,
    startup_timeline,
    target_chain,
    why_primary,
)
from colav_simulator.decision_replay.recorder import RecordResult, record

__all__ = [
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
