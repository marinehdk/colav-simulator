"""Raw-evidence gate for the versioned G3 display capability."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from colav_simulator.evaluation.encounter import wrap_angle

PREDICATE_VERSION = "G3DisplayPredicate-v1"
HEADING_ACTION_THRESHOLD_RAD = np.deg2rad(2.0)
SPEED_ACTION_THRESHOLD_MPS = 0.5


@dataclass(frozen=True)
class G3DisplayResult:
    """Auditable result of one nominal-versus-candidate G3 comparison."""

    passed: bool
    checks: dict[str, bool]
    metrics: dict[str, Any]
    reasons: tuple[str, ...]
    predicate_version: str = PREDICATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_g3_display(  # noqa: PLR0913
    *,
    nominal_frames: list[dict[str, Any]],
    candidate_frames: list[dict[str, Any]],
    nominal_events: list[dict[str, Any]],
    candidate_events: list[dict[str, Any]],
    nominal_manifest: Any,
    candidate_manifest: Any,
    ship_info: dict[str, dict[str, Any]],
    expected_algorithm: str,
    dt_sim: float,
) -> G3DisplayResult:
    """Evaluate G3 from raw run evidence without consulting capability grades."""
    nominal_times = _frame_times(nominal_frames)
    candidate_times = _frame_times(candidate_frames)
    clock_ok = _valid_clock(nominal_times, dt_sim) and _valid_clock(candidate_times, dt_sim)

    nominal_clearance = _minimum_clearance_by_target(nominal_frames, ship_info)
    candidate_clearance = _minimum_clearance_by_target(candidate_frames, ship_info)
    nominal_collision = _has_event(nominal_events, "collision")
    nominal_threat = nominal_collision or any(
        item["minimum_distance_m"] <= item["required_clearance_m"] for item in nominal_clearance.values()
    )
    all_targets_observed = bool(candidate_clearance) and set(candidate_clearance) == {
        key for key in ship_info if key != "Ship0"
    }
    footprint_safe = all_targets_observed and all(
        item["minimum_distance_m"] > item["required_clearance_m"] for item in candidate_clearance.values()
    )

    requested = str(_manifest_value(candidate_manifest, "requested_algorithm", "")).lower()
    executed = str(_manifest_value(candidate_manifest, "executed_algorithm", "")).lower()
    fallback_used = bool(_manifest_value(candidate_manifest, "fallback_used", False)) or _frame_fallback_used(
        candidate_frames
    )
    identity_ok = requested == executed == expected_algorithm.lower()

    descriptor_document = _manifest_value(candidate_manifest, "algorithm_descriptor")
    is_custom_plugin = isinstance(descriptor_document, dict)
    solve_count, valid_solve_plans, all_success_statuses = _solve_evidence(
        candidate_frames,
        min_columns=2 if is_custom_plugin else 1,
    )
    custom_identity_complete = not is_custom_plugin or _custom_identity_complete(
        descriptor_document,
        expected_algorithm,
    )
    formal_execution = not is_custom_plugin or (
        not bool(_manifest_value(candidate_manifest, "diagnostic_only", False))
        and str(
            getattr(
                _manifest_value(candidate_manifest, "execution_outcome", ""),
                "value",
                _manifest_value(candidate_manifest, "execution_outcome", ""),
            )
        ).upper()
        == "COMPLETED"
    )
    footprint_oracle = not is_custom_plugin or (
        _manifest_value(candidate_manifest, "collision_oracle_id") == "footprint-adaptive-v1"
        and _positive_float(_manifest_value(candidate_manifest, "ccd_step_tolerance_m", 0.0))
    )
    terminal_types = {str(event.get("type")) for event in candidate_events}
    state = _manifest_value(candidate_manifest, "state", "")
    state_value = getattr(state, "value", state)
    normal_termination = (
        str(state_value) == "FINISHED"
        and "session_finished" in terminal_types
        and bool({"time_limit", "goal_reached"} & terminal_types)
    )
    no_hard_failure = (
        not bool({"collision", "grounding", "run_failed", "session_failed"} & terminal_types)
        and not _manifest_value(candidate_manifest, "failure_status")
    )

    same_run_inputs = (
        _manifest_value(nominal_manifest, "scenario_hash")
        == _manifest_value(candidate_manifest, "scenario_hash")
        and _manifest_value(nominal_manifest, "enc_hash")
        == _manifest_value(candidate_manifest, "enc_hash")
        and bool(_manifest_value(nominal_manifest, "enc_hash"))
        and _manifest_value(nominal_manifest, "seeds") == _manifest_value(candidate_manifest, "seeds")
    )

    max_heading_delta_rad, max_speed_delta_mps, aligned_samples = _action_delta(
        nominal_frames,
        candidate_frames,
    )
    observable_action = bool(
        aligned_samples > 0
        and (
            max_heading_delta_rad >= HEADING_ACTION_THRESHOLD_RAD
            or max_speed_delta_mps >= SPEED_ACTION_THRESHOLD_MPS
        )
    )

    checks = {
        "same_run_inputs": same_run_inputs,
        "clock_valid": clock_ok,
        "nominal_threat": nominal_threat,
        "algorithm_identity": identity_ok,
        "no_fallback": not fallback_used,
        "real_solve": solve_count > 0,
        "finite_9xn_plans": valid_solve_plans,
        "success_only": not is_custom_plugin or all_success_statuses,
        "formal_execution": formal_execution,
        "complete_plugin_identity": custom_identity_complete,
        "footprint_collision_oracle": footprint_oracle,
        "normal_termination": normal_termination,
        "no_hard_failure": no_hard_failure,
        "all_targets_observed": all_targets_observed,
        "footprint_clearance": footprint_safe,
        "observable_action": observable_action,
    }
    reasons = tuple(name for name, passed in checks.items() if not passed)
    metrics = {
        "expected_algorithm": expected_algorithm.lower(),
        "solve_count": solve_count,
        "aligned_action_samples": aligned_samples,
        "max_heading_delta_deg": float(np.rad2deg(max_heading_delta_rad)),
        "max_speed_delta_mps": max_speed_delta_mps,
        "nominal_clearance": nominal_clearance,
        "candidate_clearance": candidate_clearance,
        "candidate_terminal_events": sorted(terminal_types),
    }
    return G3DisplayResult(
        passed=not reasons,
        checks=checks,
        metrics=metrics,
        reasons=reasons,
    )


def _manifest_value(manifest: Any, name: str, default: Any = None) -> Any:
    if isinstance(manifest, dict):
        return manifest.get(name, default)
    return getattr(manifest, name, default)


def _frame_times(frames: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray(
        [
            float(frame["Ship0"]["timestamp"])
            for frame in frames
            if frame.get("Ship0") and "timestamp" in frame["Ship0"]
        ],
        dtype=float,
    )


def _valid_clock(times: np.ndarray, dt_sim: float) -> bool:
    if times.size == 0 or not np.all(np.isfinite(times)):
        return False
    if times.size == 1:
        return True
    deltas = np.diff(times)
    tolerance = max(1e-9, abs(dt_sim) * 1e-6)
    return bool(np.all(deltas > 0.0) and np.allclose(deltas, dt_sim, rtol=0.0, atol=tolerance))


def _minimum_clearance_by_target(
    frames: list[dict[str, Any]],
    ship_info: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    if "Ship0" not in ship_info:
        return {}
    own_radius = _circumscribed_radius(ship_info["Ship0"])
    output: dict[str, dict[str, float]] = {}
    for target_key, target_info in ship_info.items():
        if target_key == "Ship0":
            continue
        distances = []
        for frame in frames:
            own = frame.get("Ship0")
            target = frame.get(target_key)
            if not own or not target or not bool(target.get("active", True)):
                continue
            delta = _position_ne(target) - _position_ne(own)
            distance = float(np.linalg.norm(delta))
            if np.isfinite(distance):
                distances.append(distance)
        if distances:
            output[target_key] = {
                "minimum_distance_m": min(distances),
                "required_clearance_m": own_radius + _circumscribed_radius(target_info),
            }
    return output


def _circumscribed_radius(info: dict[str, Any]) -> float:
    return 0.5 * float(np.hypot(float(info["length"]), float(info["width"])))


def _position_ne(ship: dict[str, Any]) -> np.ndarray:
    if "csog_state" in ship:
        return np.asarray(ship["csog_state"][:2], dtype=float)
    return np.asarray([ship["north"], ship["east"]], dtype=float)


def _has_event(events: list[dict[str, Any]], event_type: str) -> bool:
    return any(event.get("type") == event_type for event in events)


def _frame_fallback_used(frames: list[dict[str, Any]]) -> bool:
    for frame in frames:
        own = frame.get("Ship0") or {}
        diagnostics = own.get("colav", {}).get("diagnostics", {})
        if diagnostics.get("fallback_used"):
            return True
    return False


def _solve_evidence(
    frames: list[dict[str, Any]],
    *,
    min_columns: int,
) -> tuple[int, bool, bool]:
    solve_count = 0
    all_valid = True
    all_success = True
    for frame in frames:
        own = frame.get("Ship0") or {}
        planner = own.get("colav", {}).get("planner", {})
        if planner:
            all_success = all_success and str(planner.get("status", "SUCCESS")) == "SUCCESS"
        if not planner.get("solver_executed"):
            continue
        solve_count += 1
        prediction = np.asarray(planner.get("predicted_trajectory"))
        all_valid = (
            all_valid
            and prediction.ndim == 2
            and prediction.shape[0] == 9
            and prediction.shape[1] >= min_columns
            and bool(np.all(np.isfinite(prediction)))
        )
    return solve_count, all_valid, all_success


def _custom_identity_complete(descriptor_document: dict[str, Any], expected_algorithm: str) -> bool:
    descriptor = descriptor_document.get("descriptor")
    build_identity = descriptor_document.get("build_identity")
    if not isinstance(descriptor, dict) or not isinstance(build_identity, dict):
        return False
    values = tuple(build_identity.values())
    return (
        str(descriptor.get("algorithm_id", "")).lower() == expected_algorithm.lower()
        and bool(values)
        and all(bool(value) and value != "UNKNOWN" for value in values)
    )


def _positive_float(value: Any) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(numeric) and numeric > 0.0)


def _action_delta(
    nominal_frames: list[dict[str, Any]],
    candidate_frames: list[dict[str, Any]],
) -> tuple[float, float, int]:
    nominal = _ownship_motion(nominal_frames)
    candidate = _ownship_motion(candidate_frames)
    if nominal[0].size == 0 or candidate[0].size == 0:
        return 0.0, 0.0, 0
    within_nominal = (candidate[0] >= nominal[0][0]) & (candidate[0] <= nominal[0][-1])
    candidate_times = candidate[0][within_nominal]
    if candidate_times.size == 0:
        return 0.0, 0.0, 0
    nominal_heading = np.interp(candidate_times, nominal[0], np.unwrap(nominal[1]))
    nominal_speed = np.interp(candidate_times, nominal[0], nominal[2])
    candidate_heading = candidate[1][within_nominal]
    candidate_speed = candidate[2][within_nominal]
    heading_delta = np.abs(wrap_angle(candidate_heading - nominal_heading))
    speed_delta = np.abs(candidate_speed - nominal_speed)
    return float(np.max(heading_delta)), float(np.max(speed_delta)), int(candidate_times.size)


def _ownship_motion(frames: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    samples = []
    for frame in frames:
        own = frame.get("Ship0")
        if not own:
            continue
        if "csog_state" in own:
            csog = np.asarray(own["csog_state"], dtype=float)
            heading = float(csog[3])
            speed = float(csog[2])
        else:
            heading = float(own["psi"])
            speed = float(np.hypot(float(own["u"]), float(own.get("v", 0.0))))
        samples.append((float(own["timestamp"]), heading, speed))
    if not samples:
        empty = np.asarray([], dtype=float)
        return empty, empty, empty
    values = np.asarray(samples, dtype=float)
    return values[:, 0], values[:, 1], values[:, 2]
