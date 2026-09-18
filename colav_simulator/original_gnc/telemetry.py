"""Read-only display projection of original GNC state and source parameters."""

from __future__ import annotations

import math
from typing import Any


def _sample_time(message: dict | None, epoch: int) -> float | None:
    if not message or "header" not in message:
        return None
    stamp = message["header"]["stamp"]
    return (stamp["sec"] * 1_000_000_000 + stamp["nanosec"] - epoch) / 1_000_000_000


def speed_contract(ship: Any) -> dict:
    """Keep requested, admitted, controlled and measured speeds distinct."""
    stack = ship.stack
    manager = stack.latest.get("/gnc/route_execution_status") or {}
    velocity_active = bool(stack.states["active_route_manager_node"].get("active_velocity_intent"))
    velocity = (stack.latest.get("/gnc/velocity_execution_status") or {}) if velocity_active else {}
    planner = (ship._legacy._colav.get_colav_data().get("planner") or {}) if ship._legacy._colav is not None else {}
    plant = stack.states["ship_dynamics_node"]

    def finite(value: Any) -> float | None:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return float(value)
        return None

    speeds = [float(value) for value in ship.speed_plan]
    uniform = bool(speeds) and all(abs(value - speeds[0]) < 1e-9 for value in speeds)
    admitted = manager.get("accepted") and not manager.get("rejected") and (
        manager.get("stage_snapshot_valid") or manager.get("execution_state") == "VELOCITY_INTENT_ACCEPTED"
    )
    published_at = getattr(ship, "_speed_setpoint_time_ns", None)
    return {
        "input_kind": "velocity_intent" if velocity_active else "route_plan",
        "mode": velocity.get("behavior_mode") or manager.get("current_navigation_mode") or None,
        "state": velocity.get("state") or manager.get("execution_state") or None,
        "mission_speed_mps": speeds[0] if uniform else None,
        "mission_speed_plan_mps": speeds,
        "planner_speed_mps": finite((planner.get("selected_command") or {}).get("speed_mps")),
        "planner_sample_time_s": planner.get("sim_time"),
        "admitted_speed_mps": finite(manager.get("applied_speed_mps")) if admitted else None,
        "admission_sample_time_s": _sample_time(manager, stack.epoch_ns),
        "guidance_surge_mps": finite((stack.latest.get("/control/speed_setpoint") or {}).get("data")),
        "guidance_sample_time_s": (published_at - stack.epoch_ns) / 1e9 if published_at is not None else None,
        "actual_speed_mps": math.hypot(plant["nu"][0], plant["nu"][1]),
        "sample_time_s": stack.elapsed_s,
        "policy": ship.execution_speed_policy,
        "limiting_reasons": list(velocity.get("limiting_reasons") or []) if velocity_active else
        ([manager["reason"]] if manager.get("degraded") or manager.get("rejected") else []),
        "intent_id": velocity.get("intent_id") if velocity_active else manager.get("plan_id"),
        "valid_until": velocity.get("valid_until") if velocity_active else None,
    }


def balance(ship: Any) -> dict:
    """Expose original delivered forces/angles; never advance kernels or random state."""
    stack = ship.stack
    parameters = ship._parameters
    plant = stack.states["ship_dynamics_node"]
    allocation = stack.states["thrust_allocation_node"]

    def parameter(module: str, name: str) -> Any:
        return parameters[module][name]["value"]

    environment = {
        "status": "OFF",
        "sample_time_s": None,
        "wind_speed_mps": None,
        "wind_from_deg": None,
        "current_speed_mps": None,
        "current_to_deg": None,
        "wave_hs_m": None,
        "wave_tp_s": None,
        "wave_tz_s": None,
        "wave_to_deg": None,
        "forecast": None,
        "forecast_status": "UNAVAILABLE",
    }
    if ship.configuration.environment:
        current = stack.latest.get("/env/effective_current")
        wave = stack.states.get("wave_engine_node", {})
        wind_direction = parameter("wind_engine_node", "wind_direction")
        wave_direction = math.degrees(parameter("wave_engine_node", "direction_rad"))
        environment.update(
            status="AVAILABLE" if "/env/total_load" in stack.latest else "WAITING",
            sample_time_s=_sample_time(stack.latest.get("/env/total_load"), stack.epoch_ns),
            wind_speed_mps=parameter("wind_engine_node", "u10"),
            wind_from_deg=(wind_direction + (0 if parameter("wind_engine_node", "wind_direction_is_from") else 180)) % 360,
            current_speed_mps=current["speed_mps"] if current else None,
            current_to_deg=(current["direction_deg"] + (180 if current["direction_convention"] == 1 else 0)) % 360
            if current
            else None,
            wave_hs_m=wave.get("spectrum_hs_m") if wave.get("spectrum_initialized") else None,
            wave_tz_s=wave.get("spectrum_tz_s") if wave.get("spectrum_initialized") else None,
            wave_to_deg=(wave_direction + (180 if parameter("wave_engine_node", "wave_direction_is_from") else 0)) % 360,
            wind_sample_kind="original_configured_U10",
            wave_period_kind="Tz",
        )
    propulsion = []
    for actuator, health in zip(plant["actuators"], allocation["actuators"], strict=True):
        name = actuator["name"]
        rudder = parameter("thrust_allocation_node", name + ".is_rudder")
        kind = "rudder" if rudder else "tunnel_thruster" if name in {"tb1", "tb2"} else "main"
        maximum = parameter("thrust_allocation_node", name + ".max_thrust_kN") * 1000.0
        propulsion.append(
            {
                "id": name,
                "kind": kind,
                "actual_n": actuator["actual_force_n"],
                "command_n": actuator["cmd_force_n"],
                "angle_deg": math.degrees(actuator["actual_angle_rad"]),
                "command_angle_deg": math.degrees(actuator["cmd_angle_rad"]),
                "min_force_n": -maximum,
                "max_force_n": maximum,
                "max_angle_deg": math.degrees(parameter("thrust_allocation_node", name + ".max_angle")) if rudder else None,
                "force_limit_kind": "original_declared_nominal_limit",
                "rate_limited": None,
                "health": health["health_score"] if health["healthy"] else 0.0,
            }
        )
    constraints = []
    for label, module, key, scale, unit in [
        ("Max rudder angle", "thrust_allocation_node", "r1.max_angle", 180 / math.pi, "°"),
        ("Max rudder rate", "ship_dynamics_node", "thrusters.r1.angle_rate_limit", 180 / math.pi, "°/s"),
        ("Main thrust rate", "ship_dynamics_node", "thrusters.t1.thrust_rate_limit", 0.001, "kN/s"),
        ("Bow thrust rate", "ship_dynamics_node", "thrusters.tb1.thrust_rate_limit", 0.001, "kN/s"),
        ("Bow lockout", "thrust_allocation_node", "side_thruster_lockout_speed_mps", 1, "m/s"),
        ("Bow unlock below", "thrust_allocation_node", "side_thruster_unlock_speed_mps", 1, "m/s"),
        ("Route update interval", "coordinate_transform_node", "min_route_update_interval_s", 1, "s"),
        ("Future route change distance", "coordinate_transform_node", "min_future_update_distance_m", 1, "m"),
    ]:
        constraints.append(
            {"label": label, "value": parameter(module, key) * scale, "unit": unit, "source": module + "." + key}
        )
    bridge = ship._plan_bridge.last_outcome if ship._plan_bridge else None
    feedback = bridge.get("feedback", []) if bridge else [stack.latest.get("/route_planning/route_plan_status", {})]
    admission = next(
        (item for item in feedback if item.get("rejected") or item.get("accepted") is False),
        feedback[-1] if feedback else {},
    )
    admission_status = (
        "Rejected"
        if admission.get("rejected") or admission.get("accepted") is False
        else "Limited"
        if admission.get("degraded")
        else "Accepted"
        if admission.get("accepted")
        else "Awaiting feedback"
    )
    return {
        "backend_kind": "original_gnc",
        "config_hash": ship._parameter_hash,
        "tick": round(stack.elapsed_s / ship._dt_s),
        "roll_deg": math.degrees(plant["eta"][2]),
        "roll_rate_deg_s": math.degrees(plant["nu"][2]),
        "environment": environment,
        "propulsion": propulsion,
        "propulsion_status": "AVAILABLE",
        "actuator_time_s": _sample_time(stack.latest.get("/ship/odometry"), stack.epoch_ns),
        "bow_authority": float(allocation["side_thruster_allowed"]),
        "constraints": constraints,
        "route_admission": {"status": admission_status, "reason": admission.get("reason", "")},
        "speed_contract": speed_contract(ship),
        "weather_limits": None,
    }
