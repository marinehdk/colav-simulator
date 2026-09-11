"""Dimensional comparison of original published value contracts.

Unclassified data are compared exactly. No timing fitting, missing-field fill,
or change to the v1 SI acceptance tolerances is performed.
"""

from __future__ import annotations

import math
from typing import Any

from colav_simulator.original_gnc.validation import FIELD_RULES, FieldRule

EXACT = FieldRule("exact", discrete=True)
RATIO = FieldRule("1", 1e-12, 1e-10)
ANGLE = FIELD_RULES["heading_rad"]
DEGREES = FieldRule("deg", ANGLE.absolute * 180.0 / math.pi)


# Keep source contract branches together for audit against the frozen implementation.
def message_rule(message_type: str, port: str, path: tuple) -> FieldRule:  # noqa: C901, PLR0911, PLR0912
    """Resolve numerical units from the original message and publisher."""
    words = {part for part in path if isinstance(part, str)}
    if "stamp" in words or "layout" in words:
        return EXACT
    if message_type == "ship_interfaces/msg/RoutePlanStatus" and path[-1] in {
        "total_distance_m",
        "current_along_track_m",
        "first_changed_distance_ahead_m",
        "max_lateral_delta_m",
    }:
        return FIELD_RULES["north_m"]
    if message_type in {"ship_interfaces/msg/GeoPosition", "ship_interfaces/msg/RouteExecutionStatus"}:
        field = path[-1]
        if field.endswith("_mps"):
            return FIELD_RULES["surge_mps"]
        if field.endswith("_deg"):
            return DEGREES
        if field.endswith("_rads"):
            return FIELD_RULES["yaw_rate_radps"]
        if field.endswith("_deg_s"):
            return FieldRule("deg/s", FIELD_RULES["yaw_rate_radps"].absolute * 180.0 / math.pi, 1e-9)
        if field.endswith("_m") or field in {"x_ned", "y_ned"}:
            return FIELD_RULES["north_m"]
        if field in {"latitude", "longitude", "origin_lat", "origin_lon", "current_latitude", "current_longitude"}:
            return FieldRule("geographic degrees", 1e-11)
    if message_type == "ship_interfaces/msg/CurrentObservation":
        return {
            "speed_mps": FIELD_RULES["surge_mps"],
            "direction_deg": DEGREES,
            "measurement_depth_m": FIELD_RULES["north_m"],
            "speed_variance": FieldRule("m^2/s^2", 1e-12, 1e-10),
            "direction_variance": FieldRule("deg^2", 1e-12, 1e-10),
            "validity_duration_s": FieldRule("s", 1e-9),
        }.get(path[-1], EXACT)
    if message_type == "geometry_msgs/msg/WrenchStamped":
        if "force" in words:
            return FIELD_RULES["surge_n"]
        if "torque" in words:
            return FIELD_RULES["yaw_nm"]
    if message_type == "nav_msgs/msg/Odometry":
        if "covariance" in words:
            return EXACT
        if "position" in words:
            return FIELD_RULES["north_m"]
        if "orientation" in words:
            return FieldRule("quaternion", 1e-8)
        if "linear" in words:
            return FIELD_RULES["surge_mps"]
        if "angular" in words:
            return FIELD_RULES["yaw_rate_radps"]
    if message_type == "geometry_msgs/msg/PoseStamped":
        if "position" in words:
            return FIELD_RULES["north_m"]
        if "orientation" in words:
            return FieldRule("quaternion", 1e-8)
    if message_type == "nav_msgs/msg/Path":
        if port == "smoothed_waypoints_pub_":
            # Source publish block: z stores turn_angle_deg, orientation.z speed_override.
            if path[-2:] == ("position", "z"):
                return DEGREES
            if path[-2:] == ("orientation", "z"):
                return FIELD_RULES["surge_mps"]
        # Original guidance overloads z/ quaternion members with route metadata.
        # Geometric x/y use metres; all encoded metadata stay exact.
        if "position" in words and path[-1] in {"x", "y"}:
            return FIELD_RULES["north_m"]
    if message_type == "std_msgs/msg/Float64" and "data" in words:
        if port == "initial_route_yaw_pub_":
            return ANGLE
        if port == "heading_pub_":
            return DEGREES
        if "heading" in port:
            return ANGLE
        if "speed" in port:
            return FIELD_RULES["surge_mps"]
    if message_type == "std_msgs/msg/Float64MultiArray" and "data" in words:
        index = path[-1]
        if port == "cmd_pub_":
            return FIELD_RULES["surge_n"] if index % 2 == 0 else FIELD_RULES["rudder_rad"]
        if port == "health_pub_":
            return EXACT
        if port == "relative_flow_publisher_":
            return EXACT if index == 14 else DEGREES if index in {9, 13} else FIELD_RULES["surge_mps"]
        if port == "rudder_effectiveness_pub_":
            mapping = {
                0: FIELD_RULES["surge_mps"],
                1: DEGREES,
                2: ANGLE,
                3: RATIO,
                4: FieldRule("kN/rad", 1e-6, 1e-8),
                5: FieldRule("kN", 1e-6, 1e-8),
                6: FieldRule("kN.m", 1e-5, 1e-8),
                7: FieldRule("kN", 1e-6, 1e-8),
                8: FieldRule("kN", 1e-6, 1e-8),
                9: FieldRule("kN.m", 1e-5, 1e-8),
                10: EXACT,
            }
            return mapping.get(index, EXACT)
    return EXACT


# Keep source contract branches together for audit against the frozen implementation.
def compare_outputs(expected: list[dict], actual: list[dict], asset_hashes: dict[str, str] | None = None) -> dict:  # noqa: C901, PLR0915
    """Return the first difference and per-unit maximum numerical errors."""
    maxima: dict[str, float] = {}
    checked = 0
    asset_hashes = asset_hashes or {}

    # Keep source contract branches together for audit against the frozen implementation.
    def walk(left: Any, right: Any, path: tuple, message_type: str, port: str) -> dict | None:  # noqa: C901, PLR0911, PLR0912
        nonlocal checked
        if left is None or right is None:
            return {"kind": "null_message_value", "path": path}
        if isinstance(left, dict):
            if not isinstance(right, dict) or left.keys() != right.keys():
                return {"kind": "field_set", "path": path}
            # Diagnostic KeyValue stores numeric telemetry in strings. Interpret
            # only the explicit original numerical keys, never reason/mode IDs.
            key = left.get("key")
            if (
                message_type == "diagnostic_msgs/msg/DiagnosticArray"
                and set(left) == {"key", "value"}
                and key == right.get("key")
            ):
                if key == "source_csv":
                    checked += 1
                    left_hash, right_hash = asset_hashes.get(left["value"]), asset_hashes.get(right["value"])
                    if left_hash is None or right_hash is None or left_hash != right_hash:
                        return {"kind": "asset_identity", "path": path, "expected": left["value"], "actual": right["value"]}
                    return None
                rule = None
                if key in {"requested_fx_n", "requested_fy_n", "achieved_fx_n", "achieved_fy_n"}:
                    rule = FIELD_RULES["surge_n"]
                elif key in {"requested_mz_nm", "achieved_mz_nm"}:
                    rule = FIELD_RULES["yaw_nm"]
                elif key == "side_thruster_policy_speed_mps":
                    rule = FIELD_RULES["surge_mps"]
                elif key == "normalized_error":
                    rule = FieldRule("1 (six-decimal display)", 1e-6)
                if rule is not None:
                    return number(float(left["value"]), float(right["value"]), path + ("value",), rule)
            for key in left:
                difference = walk(left[key], right[key], path + (key,), message_type, port)
                if difference:
                    return difference
            return None
        if isinstance(left, list):
            if not isinstance(right, list) or len(left) != len(right):
                return {"kind": "array_length", "path": path}
            for index, (a, b) in enumerate(zip(left, right, strict=True)):
                difference = walk(a, b, path + (index,), message_type, port)
                if difference:
                    return difference
            return None
        if isinstance(left, float) and isinstance(right, (int, float)) and not isinstance(right, bool):
            rule = message_rule(message_type, port, path)
            return number(left, right, path, rule)
        if message_type == "diagnostic_msgs/msg/DiagnosticArray" and path[-1:] == ("level",):
            # ROS Python's byte field is a one-character string; the native
            # value contract uses uint8_t. Compare the same categorical byte.
            left = ord(left) if isinstance(left, str) and len(left) == 1 else left
        checked += 1
        if type(left) is not type(right) or left != right:
            return {"kind": "exact_value", "path": path, "expected": left, "actual": right}
        return None

    def number(left: float, right: float, path: tuple, rule: FieldRule) -> dict | None:
        nonlocal checked
        checked += 1
        if not math.isfinite(left) or not math.isfinite(right):
            return {"kind": "nonfinite", "path": path}
        delta = right - left
        error = abs(math.remainder(delta, 2 * math.pi) if rule.circular else delta)
        maxima[rule.unit] = max(maxima.get(rule.unit, 0.0), error)
        tolerance = 0.0 if rule.discrete else rule.absolute + rule.relative * abs(left)
        if error > tolerance:
            return {
                "kind": "numerical",
                "path": path,
                "expected": left,
                "actual": right,
                "error": error,
                "tolerance": tolerance,
                "unit": rule.unit,
            }
        return None

    if len(expected) != len(actual):
        difference = {"kind": "output_count", "expected": len(expected), "actual": len(actual)}
    else:
        difference = None
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if left["port"] != right["port"] or left["message"]["type"] != right["message"]["type"]:
                difference = {"kind": "output_identity", "index": index}
                break
            difference = walk(
                left["message"]["fields"], right["message"]["fields"], (), left["message"]["type"], left["port"]
            )
            if difference:
                difference = {"index": index, "port": left["port"], **difference}
                break
    return {
        "passed": difference is None,
        "fields_checked": checked,
        "max_error_by_unit": maxima,
        "first_difference": difference,
    }
