"""Named offline probes over one recorded decision trace.

Each probe answers one recurring debugging question as structured JSON with
tick-anchored evidence, so no question ever requires re-running the
simulation. Reports are plain dicts: the CLI prints them, the SKILL reads
them, pytest asserts on them.
"""

from __future__ import annotations

from typing import Any

from colav_simulator.decision_replay import signals
from colav_simulator.decision_replay.bundle import TraceBundle

_EVENT_TARGET_KEYS = ("target_id", "to_target_id", "from_target_id")


def _event_matches_target(event: dict[str, Any], target_id: int | None) -> bool:
    if target_id is None:
        return True
    details = event.get("details") or {}
    for key in _EVENT_TARGET_KEYS:
        value = details.get(key)
        if value is not None and int(value) == target_id:
            return True
    return False


def startup_timeline(bundle: TraceBundle, *, seconds: float = 30.0, ship_index: int = 0) -> dict[str, Any]:
    """Reconstruct tick-by-tick what happened right after t=0 and why.

    Answers "why was the own ship silent / routeless for the first N seconds":
    control source per tick, planner cadence, first solve, handoff moment.
    """
    rows = []
    handoff_at: float | None = None
    first_solve: dict[str, Any] | None = None
    for frame in bundle.frames():
        t = signals.sim_time(frame)
        if t > seconds:
            break
        ship = signals.ship_of(frame, ship_index)
        planner = signals.planner_of(ship)
        threat = signals.threat_document(ship)
        row = {
            "seq": frame.get("sequence"),
            "t": round(t, 3),
            "control_source": signals.control_source(frame, ship_index),
            "planner": (planner or {}).get("algorithm_id"),
            "solver_executed": (planner or {}).get("solver_executed"),
            "solve_id": (planner or {}).get("solve_id"),
            "feasible": (planner or {}).get("feasible"),
            "status": (planner or {}).get("status"),
            "reason": (planner or {}).get("reason"),
            "primary": signals.primary_of(threat) if threat else None,
            "applied": signals.applied_reference(ship),
        }
        if handoff_at is None and row["control_source"] != "HISTORICAL_REFERENCE":
            handoff_at = t
        if (
            first_solve is None
            and planner is not None
            and planner.get("solver_executed")
            and row["control_source"] != "HISTORICAL_REFERENCE"
        ):
            first_solve = {"t": t, "seq": frame.get("sequence"), "solve_id": planner.get("solve_id")}
        rows.append(row)
    return {
        "run_id": bundle.run_id,
        "window_s": seconds,
        "first_control_transfer": handoff_at,
        "first_planner_solve": first_solve,
        "rows": rows,
        "events": [
            event
            for event in bundle.events()
            if (event.get("sim_time") or 0) <= seconds
            and event.get("type") not in {"planner_solved", "threat_lifecycle_active", "session_started"}
        ],
    }


def why_primary(bundle: TraceBundle, *, at: float | None = None, ship_index: int = 0) -> dict[str, Any]:
    """Who is primary at ``at`` and the evidence trail that put it there."""
    if at is None:
        at = signals.sim_time(bundle.frame(bundle.tick_count)) if bundle.tick_count else 0.0
    sequence = bundle.seq_at_time(at)
    if sequence == 0:
        return {"run_id": bundle.run_id, "at": at, "error": "NO_RECORDED_TICKS"}
    frame = bundle.frame(sequence)
    ship = signals.ship_of(frame, ship_index)
    threat = signals.threat_document(ship)
    if threat is None:
        planner = signals.planner_of(ship)
        return {
            "run_id": bundle.run_id,
            "at": at,
            "seq": frame.get("sequence"),
            "primary": None,
            "unavailable_reason": (planner or {}).get("reason")
            or ((planner or {}).get("algorithm_details") or {}).get("threat_management", {}).get("unavailable_reason")
            if planner
            else "NO_PLANNER_TRACE",
            "control_source": signals.control_source(frame, ship_index),
        }
    vectors = signals.vectors_of(threat)
    entries = []
    for entry in signals.schedule_entries(threat):
        key = signals.entry_key(entry)
        entries.append(
            {
                "key": list(key) if key else None,
                "context": entry.get("context"),
                "priority_reason": entry.get("priority_reason"),
                "vector": signals.vector_summary(vectors[key]) if key in vectors else None,
            }
        )
    switches = [
        event for event in bundle.events() if event.get("type") == "primary_switched" and (event.get("sim_time") or 0) <= at
    ]
    return {
        "run_id": bundle.run_id,
        "at": at,
        "seq": frame.get("sequence"),
        "primary": signals.primary_of(threat),
        "control_source": signals.control_source(frame, ship_index),
        "schedule_entries": entries,
        "conflict_unavailable_reasons": (threat.get("conflict_graph") or {}).get("unavailable_reasons")
        if isinstance(threat.get("conflict_graph"), dict)
        else None,
        "primary_switch_history": switches[-5:],
    }


def target_chain(
    bundle: TraceBundle,
    target_id: int,
    *,
    t0: float | None = None,
    t1: float | None = None,
    ship_index: int = 0,
) -> dict[str, Any]:
    """Per-tick evidence rows for one target: tracker input, threat output, events."""
    rows = []
    for frame in bundle.frames():
        t = signals.sim_time(frame)
        if t0 is not None and t < t0:
            continue
        if t1 is not None and t > t1:
            break
        ship = signals.ship_of(frame, ship_index)
        threat = signals.threat_document(ship)
        track = signals.track_states(ship).get(target_id)
        row: dict[str, Any] = {
            "seq": frame.get("sequence"),
            "t": round(t, 3),
            "track": track,
            "vector": None,
        }
        if threat is not None:
            vectors = signals.vectors_of(threat)
            for (vector_target, _generation), vector in vectors.items():
                if vector_target == target_id:
                    row["vector"] = signals.vector_summary(vector)
                    break
            for entry in signals.schedule_entries(threat):
                key = signals.entry_key(entry)
                if key and key[0] == target_id:
                    row["context"] = entry.get("context")
                    break
        rows.append(row)
    return {
        "run_id": bundle.run_id,
        "target_id": target_id,
        "rows": rows,
        "events": [event for event in bundle.events() if _event_matches_target(event, target_id)],
    }


def planner_timeline(bundle: TraceBundle, *, ship_index: int = 0) -> dict[str, Any]:
    """Solve cadence and health transitions across the whole run."""
    solves = []
    last_solve_id: int | None = None
    transitions = []
    previous_ok: bool | None = None
    for frame in bundle.frames():
        ship = signals.ship_of(frame, ship_index)
        planner = signals.planner_of(ship)
        if planner is None:
            continue
        solve_id = planner.get("solve_id")
        fresh = planner.get("solver_executed") and solve_id != last_solve_id
        if fresh:
            last_solve_id = solve_id
            failure_code = (planner.get("algorithm_details") or {}).get("failure_code")
            ok = planner.get("feasible") is True and not failure_code
            solves.append(
                {
                    "seq": frame.get("sequence"),
                    "t": planner.get("sim_time", signals.sim_time(frame)),
                    "solve_id": solve_id,
                    "feasible": planner.get("feasible"),
                    "status": planner.get("status"),
                    "failure_code": failure_code,
                    "reason": planner.get("reason"),
                    "elapsed_ms": planner.get("elapsed_ms"),
                    "objective": planner.get("objective"),
                    "selected_command": planner.get("selected_command"),
                    "applied": signals.applied_reference(ship),
                }
            )
            if previous_ok is not None and ok != previous_ok:
                transitions.append(
                    {
                        "t": planner.get("sim_time", signals.sim_time(frame)),
                        "solve_id": solve_id,
                        "kind": "recovered" if ok else "failed",
                        "reason": planner.get("reason"),
                        "failure_code": failure_code,
                    }
                )
            previous_ok = ok
    return {"run_id": bundle.run_id, "solve_count": len(solves), "transitions": transitions, "solves": solves}


_RISK_EVENT_TYPES = {
    "risk_level_changed",
    "threat_escalated",
    "threat_clearing",
    "threat_released",
    "colregs_changed",
    "avoidance_action_started",
    "avoidance_action_ended",
    "observation_degraded",
    "observation_recovered",
    "algorithm_handoff",
}


def risk_transitions(bundle: TraceBundle, *, target_id: int | None = None) -> list[dict[str, Any]]:
    """Canonical risk/lifecycle/role transitions, optionally filtered to one target."""
    return [
        event
        for event in bundle.events()
        if event.get("type") in _RISK_EVENT_TYPES and _event_matches_target(event, target_id)
    ]


def explain_tick(bundle: TraceBundle, at: float, *, ship_index: int = 0, context_s: float = 5.0) -> dict[str, Any]:
    """Full crosshair of one tick: own ship, planner I/O, every target, nearby events."""
    sequence = bundle.seq_at_time(at)
    if sequence == 0:
        return {"run_id": bundle.run_id, "at": at, "error": "NO_RECORDED_TICKS"}
    frame = bundle.frame(sequence)
    ship = signals.ship_of(frame, ship_index)
    threat = signals.threat_document(ship)
    vectors = signals.vectors_of(threat) if threat else {}
    track_states = signals.track_states(ship)
    targets = []
    for target_id, track in sorted(track_states.items()):
        entry = {"target_id": target_id, "track": track}
        for (vector_target, _generation), vector in vectors.items():
            if vector_target == target_id:
                entry["vector"] = signals.vector_summary(vector)
                break
        targets.append(entry)
    t = signals.sim_time(frame)
    return {
        "run_id": bundle.run_id,
        "seq": frame.get("sequence"),
        "t": t,
        "control_source": signals.control_source(frame, ship_index),
        "ownship": {
            "csog_state": ship.get("csog_state"),
            "state": ship.get("state"),
            "references": ship.get("references"),
            "input": ship.get("input"),
            "waypoints": ship.get("waypoints"),
            "speed_plan": ship.get("speed_plan"),
        },
        "planner": _planner_brief(ship),
        "primary": signals.primary_of(threat) if threat else None,
        "schedule_entries": [
            {
                "key": list(key) if (key := signals.entry_key(entry)) else None,
                "context": entry.get("context"),
                "priority_reason": entry.get("priority_reason"),
            }
            for entry in (signals.schedule_entries(threat) if threat else [])
        ],
        "targets": targets,
        "diagnostics": (ship.get("colav") or {}).get("diagnostics"),
        "events_window": [event for event in bundle.events() if abs((event.get("sim_time") or 0) - t) <= context_s],
    }


def _planner_brief(ship: dict[str, Any]) -> dict[str, Any] | None:
    planner = signals.planner_of(ship)
    if planner is None:
        return None
    brief = dict(planner)
    brief.pop("predicted_trajectory", None)
    brief.pop("target_predictions", None)
    return brief


def compare_runs(bundle_a: TraceBundle, bundle_b: TraceBundle, *, ship_index: int = 0) -> dict[str, Any]:
    """First behavioral divergence between two recorded runs, plus event diff."""
    first_divergence: dict[str, Any] | None = None
    compared = 0
    frames_b = bundle_b.frames()
    for frame_a in bundle_a.frames():
        frame_b = next(frames_b, None)
        if frame_b is None:
            break
        compared += 1
        ship_a = signals.ship_of(frame_a, ship_index)
        ship_b = signals.ship_of(frame_b, ship_index)
        for path, value_a, value_b in (
            ("references", ship_a.get("references"), ship_b.get("references")),
            ("state", ship_a.get("state"), ship_b.get("state")),
        ):
            if not _close(value_a, value_b):
                first_divergence = {
                    "seq": frame_a.get("sequence"),
                    "t": signals.sim_time(frame_a),
                    "path": path,
                    "a": value_a,
                    "b": value_b,
                }
                break
        if first_divergence:
            break
    events_a = [(event.get("type"), event.get("sim_time")) for event in bundle_a.events()]
    events_b = [(event.get("type"), event.get("sim_time")) for event in bundle_b.events()]
    only_a = [event for event in events_a if event not in events_b][:20]
    only_b = [event for event in events_b if event not in events_a][:20]
    return {
        "run_a": bundle_a.run_id,
        "run_b": bundle_b.run_id,
        "ticks_compared": compared,
        "first_divergence": first_divergence,
        "events_only_in_a": only_a,
        "events_only_in_b": only_b,
        "identical": first_divergence is None and not only_a and not only_b,
    }


def _close(value_a: Any, value_b: Any, tol: float = 1.0e-6) -> bool:
    if isinstance(value_a, list) and isinstance(value_b, list):
        return len(value_a) == len(value_b) and all(
            _close(item_a, item_b, tol) for item_a, item_b in zip(value_a, value_b, strict=True)
        )
    if isinstance(value_a, (int, float)) and isinstance(value_b, (int, float)):
        return abs(float(value_a) - float(value_b)) <= tol
    return value_a == value_b
