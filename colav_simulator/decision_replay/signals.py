"""Typed accessors over recorded frames.

This module is the single owner of payload key names. When the simulator
reshapes a payload, only this file changes; probes and consumers are
unaffected. All functions are pure reads over decoded JSON records.
"""

from __future__ import annotations

import math
from typing import Any

HALT_MODE = "HISTORICAL_REFERENCE"


def ship_of(frame: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """One ship payload from a decoded frame."""
    return frame.get("payload", {}).get(f"Ship{index}", {}) or {}


def sim_time(frame: dict[str, Any]) -> float:
    """Simulation time of one decoded frame."""
    return float(frame.get("sim_time", 0.0))


def planner_of(ship: dict[str, Any]) -> dict[str, Any] | None:
    """Planner trace document for one ship, or None when absent."""
    colav = ship.get("colav") or {}
    planner = colav.get("planner")
    return planner if isinstance(planner, dict) and planner else None


def counterfactual_mode(ship: dict[str, Any]) -> str | None:
    """Counterfactual phase carried in algorithm_details, or None."""
    planner = planner_of(ship)
    if planner is None:
        return None
    details = planner.get("algorithm_details") or {}
    mode = details.get("counterfactual_mode")
    return str(mode) if mode is not None else None


def control_source(frame: dict[str, Any], index: int = 0) -> str:
    """Who commanded the own ship this tick: the historical reference or the algorithm."""
    ship = ship_of(frame, index)
    mode = counterfactual_mode(ship)
    if mode == HALT_MODE:
        return "HISTORICAL_REFERENCE"
    planner = planner_of(ship)
    if planner is None:
        return "UNKNOWN"
    return str(planner.get("algorithm_id", "UNKNOWN"))


def threat_document(ship: dict[str, Any]) -> dict[str, Any] | None:
    """Canonical threat management document carried by the planner, or None."""
    """Canonical threat management document carried by the planner this tick."""
    planner = planner_of(ship)
    if planner is None:
        return None
    details = planner.get("algorithm_details") or {}
    document = details.get("threat_management")
    if isinstance(document, dict) and document.get("status") != "UNAVAILABLE":
        return document
    return None


def schedule_of(threat_document: dict[str, Any]) -> dict[str, Any] | None:
    """Threat schedule section of a threat document."""
    schedule = threat_document.get("schedule")
    return schedule if isinstance(schedule, dict) else None


def primary_of(threat_document: dict[str, Any]) -> dict[str, int] | None:
    """Current primary track key as {target_id, generation}, or None."""
    schedule = schedule_of(threat_document)
    if schedule is None:
        return None
    primary = schedule.get("current_primary")
    if isinstance(primary, dict) and "target_id" in primary:
        return {"target_id": int(primary["target_id"]), "generation": int(primary.get("generation", 0))}
    return None


def schedule_entries(threat_document: dict[str, Any]) -> list[dict[str, Any]]:
    """Schedule entries of a threat document."""
    schedule = schedule_of(threat_document)
    if schedule is None:
        return []
    entries = schedule.get("entries")
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


def entry_key(entry: dict[str, Any]) -> tuple[int, int] | None:
    """Track key (target_id, generation) of one schedule entry."""
    key = entry.get("key")
    if isinstance(key, dict) and "target_id" in key:
        return int(key["target_id"]), int(key.get("generation", 0))
    if "target_id" in entry:
        return int(entry["target_id"]), int(entry.get("generation", 0))
    return None


def vectors_of(threat_document: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    """Threat vectors keyed by (target_id, generation)."""
    vectors = {}
    for vector in threat_document.get("vectors") or []:
        if not isinstance(vector, dict):
            continue
        key = vector.get("key") or vector
        if isinstance(key, dict) and "target_id" in key:
            vectors[(int(key["target_id"]), int(key.get("generation", 0)))] = vector
    return vectors


def vector_summary(vector: dict[str, Any]) -> dict[str, Any]:
    """Comparable scalar summary of one threat vector."""
    lifecycle = vector.get("lifecycle") or {}
    lifecycle = lifecycle.get("to_dict", lifecycle) if isinstance(lifecycle, dict) else {}
    risk = lifecycle.get("risk")
    if isinstance(risk, dict):
        risk = risk.get("value", risk)
    return {
        "dcpa_m": vector.get("dcpa_m"),
        "tcpa_s": vector.get("tcpa_forward_s", vector.get("tcpa_s")),
        "range_m": vector.get("range_m"),
        "display_class": _enum_text(vector.get("display_class")),
        "priority_class": _enum_text(vector.get("priority_class")),
        "priority_reason": vector.get("priority_reason"),
        "observation_health": _enum_text(vector.get("observation_health")),
        "lifecycle_risk": _enum_text(risk),
        "encounter": _enum_text(lifecycle.get("encounter")),
        "role": _enum_text(lifecycle.get("role")),
        "commitment": _enum_text(lifecycle.get("commitment")),
        "avoidance_action_active": vector.get("avoidance_action_active"),
        "uncertainty_radius_m": vector.get("uncertainty_radius_m"),
    }


def _enum_text(value: Any) -> Any:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def waypoints_of(ship: dict[str, Any]) -> list[list[float]] | None:
    """Mission route waypoints (2 x n [N; E] rows), or None when absent."""
    waypoints = ship.get("waypoints")
    return waypoints if isinstance(waypoints, list) and waypoints else None


def algorithm_details(ship: dict[str, Any]) -> dict[str, Any]:
    """Planner algorithm_details document, or an empty dict."""
    planner = planner_of(ship)
    details = (planner or {}).get("algorithm_details")
    return details if isinstance(details, dict) else {}


def lifecycle_targets(ship: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-target lifecycle decisions (risk/commitment/recovery) this tick."""
    lifecycle = algorithm_details(ship).get("lifecycle") or {}
    targets = lifecycle.get("targets")
    return [target for target in targets if isinstance(target, dict)] if isinstance(targets, list) else []


def committed_target_ids(ship: dict[str, Any]) -> list[int]:
    """Target ids holding the route hostage: COMMITTED and ACTIVE or PAST_CLEAR."""
    return sorted(
        int(target["target_id"])
        for target in lifecycle_targets(ship)
        if target.get("commitment") == "COMMITTED" and target.get("risk") in {"ACTIVE", "PAST_CLEAR"}
    )


def route_recovery_allowed(ship: dict[str, Any]) -> bool:
    """Whether any target's lifecycle currently allows returning to the route."""
    return any(bool(target.get("route_recovery_allowed")) for target in lifecycle_targets(ship))


def applied_reference(ship: dict[str, Any]) -> dict[str, float | None]:
    """Course/speed reference actually applied this tick."""
    references = ship.get("references")
    if not isinstance(references, list) or len(references) < 4:
        return {"course_rad": None, "speed_mps": None}
    return {"course_rad": float(references[2]), "speed_mps": float(references[3])}


def track_states(ship: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Tracker output keyed by target_id."""
    """Tracker output keyed by target_id: estimate, generation, NIS."""
    labels = ship.get("do_labels") or []
    estimates = ship.get("do_estimates") or []
    generations = ship.get("do_generations") or []
    nises = ship.get("do_NISes") or []
    tracks: dict[int, dict[str, Any]] = {}
    for position, label in enumerate(labels):
        try:
            target_id = int(label)
        except (TypeError, ValueError):
            continue
        estimate = estimates[position] if position < len(estimates) else None
        speed = math.hypot(estimate[2], estimate[3]) if isinstance(estimate, list) and len(estimate) >= 4 else None
        course = math.atan2(estimate[3], estimate[2]) if speed else None
        tracks[target_id] = {
            "generation": generations[position] if position < len(generations) else None,
            "estimate": estimate,
            "nis": nises[position] if position < len(nises) else None,
            "speed_mps": speed,
            "course_rad": course,
        }
    return tracks


def planner_solve_rows(frame: dict[str, Any], index: int = 0) -> list[dict[str, Any]]:
    """Compact per-tick planner facts: cadence, feasibility, applied reference."""
    ship = ship_of(frame, index)
    planner = planner_of(ship)
    if planner is None:
        return [
            {
                "sequence": frame.get("sequence"),
                "sim_time": sim_time(frame),
                "planner": None,
                "control_source": control_source(frame, index),
                "applied": applied_reference(ship),
            }
        ]
    details = planner.get("algorithm_details") or {}
    threat = threat_document(ship)
    row = {
        "sequence": frame.get("sequence"),
        "sim_time": planner.get("sim_time", sim_time(frame)),
        "planner": planner.get("algorithm_id"),
        "solve_id": planner.get("solve_id"),
        "solver_executed": planner.get("solver_executed"),
        "feasible": planner.get("feasible"),
        "status": planner.get("status"),
        "reason": planner.get("reason"),
        "elapsed_ms": planner.get("elapsed_ms"),
        "selected_command": planner.get("selected_command"),
        "applied": applied_reference(ship),
        "control_source": control_source(frame, index),
        "primary": primary_of(threat) if threat else None,
        "counterfactual_mode": details.get("counterfactual_mode"),
    }
    return [row]
