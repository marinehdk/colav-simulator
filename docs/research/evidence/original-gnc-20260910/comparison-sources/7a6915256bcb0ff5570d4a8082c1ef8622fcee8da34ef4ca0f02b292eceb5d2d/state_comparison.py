"""Unit contracts for read-only internal states of the original GNC kernels."""

from __future__ import annotations

import json
from typing import Any

from colav_simulator.original_gnc.validation import FIELD_RULES, FieldRule, compare_trace


def flatten(value: Any, path: tuple = ()) -> dict[tuple, Any]:
    """Retain array indices and field names without filling absent state."""
    result = {}
    if isinstance(value, dict):
        result[path + (None,)] = "object"
        for key, item in value.items():
            result.update(flatten(item, path + (key,)))
    elif isinstance(value, list):
        result[path + (None,)] = f"array:{len(value)}"
        for index, item in enumerate(value):
            result.update(flatten(item, path + (index,)))
    else:
        result[path] = value
    return result


# Keep source contract branches together for audit against the frozen implementation.
def state_rule(module: str, path: tuple, value: Any) -> FieldRule:  # noqa: C901, PLR0911, PLR0912
    """Declare state units from original update equations, not observed errors."""
    if not isinstance(value, float):
        return FieldRule("discrete", discrete=True)
    first, last = path[0], path[-1]
    if module in {"wind_engine_node", "current_engine_node", "wave_engine_node"}:
        if last in {"sim_time_s", "spectrum_tz_s"}:
            return FieldRule("s", 1e-9, 1e-10)
        if last in {"u_avg_mps", "target_sigma_mps", "amplitude_mps", "fluctuation_u_mps", "fluctuation_v_mps"}:
            return FIELD_RULES["surge_mps"]
        if last in {"amplitude_m", "spectrum_hs_m", "spectrum_depth_m"}:
            return FIELD_RULES["north_m"]
        if last == "phase_rad":
            return FIELD_RULES["heading_rad"]
        if last == "direction_fluctuation_deg":
            return FieldRule("deg", FIELD_RULES["heading_rad"].absolute * 180.0 / 3.141592653589793)
        if last in {"frequency_hz", "omega_radps", "k_per_m", "depth_correction_ratio"}:
            return FieldRule(
                {"frequency_hz": "Hz", "omega_radps": "rad/s", "k_per_m": "1/m", "depth_correction_ratio": "1"}[last],
                1e-12,
                1e-10,
            )
    if last in {"last_force_n", "cmd_force_n", "actual_force_n"}:
        return FIELD_RULES["surge_n"]
    if last in {"last_angle_rad", "cmd_angle_rad", "actual_angle_rad", "previous_rudder_rad"}:
        return FIELD_RULES["rudder_rad"]
    if last in {"health_score", "f_mass", "f_drag"}:
        return FieldRule("1", 1e-12, 1e-10)
    if module == "ship_dynamics_node":
        if first == "eta":
            return FIELD_RULES["north_m"] if last < 2 else FIELD_RULES["heading_rad"]
        if first == "nu":
            return FIELD_RULES["surge_mps"] if last < 2 else FIELD_RULES["yaw_rate_radps"]
        if first in {"tau_thruster", "tau_env"}:
            return FIELD_RULES["surge_n"] if last < 2 else FIELD_RULES["yaw_nm"]
    if module == "ship_control_node":
        if first == "integrals":
            return FieldRule("rad.s" if last == 2 else "m" if last == 3 else "m.s", 1e-8, 1e-9)
        if first == "previous_errors":
            return (
                FIELD_RULES["heading_rad"]
                if last == 2
                else FIELD_RULES["surge_mps"]
                if last == 3
                else FIELD_RULES["north_m"]
            )
        if first == "previous_derivatives":
            return FIELD_RULES["yaw_rate_radps"] if last == 2 else FIELD_RULES["surge_mps"]
    if module == "ship_guidance_node":
        if first == "integral_e":
            return FieldRule("m.s", 1e-8, 1e-9)
        if first == "previous_e":
            return FIELD_RULES["north_m"]
        if first == "previous_heading":
            return FIELD_RULES["heading_rad"]
    if module == "thrust_allocation_node":
        if first == "previous_tau":
            return FieldRule("kN.m", 1e-5, 1e-8) if last == 2 else FieldRule("kN", 1e-6, 1e-8)
        if first == "policy_speed_mps":
            return FIELD_RULES["surge_mps"]
    if first in {"north_m", "east_m"}:
        return FIELD_RULES["north_m"]
    if first in {"origin_lat", "origin_lon"}:
        return FieldRule("geographic degrees", 1e-11)
    raise ValueError(f"Internal state requires an explicit unit rule: {module}.{path}")


def compare_state(module: str, expected: dict, actual: dict) -> dict:
    """Compare every available observed state, with exact field coverage."""
    left, right = flatten(expected), flatten(actual)
    if not expected or left.keys() != right.keys():
        return {"passed": False, "first_difference": {"kind": "state_field_coverage"}}
    for path in left:
        if left[path] is None or right[path] is None:
            return {"passed": False, "first_difference": {"kind": "null_state_value", "path": path}}
    names = {path: json.dumps(path, separators=(",", ":")) for path in left}
    rules = {names[path]: state_rule(module, path, value) for path, value in left.items()}
    reference = {"event": module, "tick": 0, **{names[path]: value for path, value in left.items()}}
    embedded = {"event": module, "tick": 0, **{names[path]: value for path, value in right.items()}}
    return compare_trace([reference], [embedded], rules)
