"""Read-only GNC instrument projection from the executing ownship stack."""

from __future__ import annotations

import math
from typing import Any

from colav_simulator.modular_gnc.allocator import KNOWN_ACTUATOR_LAYOUT_ASSETS
from colav_simulator.modular_gnc.fcb45_actuation import LAYOUT_ID, FCB45ActuationParameters


# Preserve the existing modular projection while dispatching original-backend telemetry.
def balance_telemetry(session: Any) -> dict[str, Any] | None:  # noqa: C901, PLR0912
    """Expose measured simulation state, delivered actuation and active limits.

    No forecast provider or weather operating envelope exists in the stack.
    Unavailable channels remain null, including all physical actuators in an
    ideal-force stack. Sampling here never advances the model or its RNG.
    """
    ships = getattr(session, "ship_list", ())
    if not ships:
        return None
    original_reader = getattr(ships[0], "original_balance_telemetry", None)
    if callable(original_reader):
        return original_reader()
    if getattr(ships[0], "modular_stack_config", None) is None:
        return None
    stack = ships[0].stack
    config = stack.config
    modules = stack.modules
    plant = modules.plant_state()
    truth = modules.environment_truth()
    actuator = modules.actuator_trace()
    allocator = modules.allocator_solution()
    controller = config.modules.get("controller")
    allocator_config = config.modules.get("allocator")
    actuator_config = config.modules.get("actuator")
    layout_id = allocator_config.parameters.get("layout_asset_id") if allocator_config else None
    layout = KNOWN_ACTUATOR_LAYOUT_ASSETS.get(layout_id)
    physical = None
    if layout_id == LAYOUT_ID and actuator_config is not None:
        physical = FCB45ActuationParameters(**actuator_config.parameters.get("fcb45_parameters", {}))

    environment: dict[str, Any] = {
        "status": "OFF" if "environment" not in config.modules else "UNAVAILABLE",
        "sample_time_s": None,
        "wind_speed_mps": None,
        "wind_from_deg": None,
        "current_speed_mps": None,
        "current_to_deg": None,
        "wave_hs_m": None,
        "wave_tp_s": None,
        "wave_to_deg": None,
        "forecast": None,
        "forecast_status": "UNAVAILABLE",
    }
    if truth is not None:
        environment.update(
            status="AVAILABLE",
            sample_time_s=truth.time_s,
            wind_speed_mps=truth.wind.speed_mps,
            wind_from_deg=(math.degrees(truth.wind.direction_to_rad) + 180.0) % 360.0,
            current_speed_mps=truth.current.speed_mps,
            current_to_deg=math.degrees(truth.current.direction_to_rad),
            wave_hs_m=truth.wave.significant_height_m,
            wave_tp_s=truth.wave.peak_period_s,
            wave_to_deg=math.degrees(truth.wave.direction_to_rad),
        )

    constraints = []

    def limit(label: str, value: float, unit: str, source: str) -> None:
        constraints.append({"label": label, "value": value, "unit": unit, "source": source})

    if controller:
        params = controller.parameters
        if params.get("reference_shaper_enable"):
            limit(
                "Heading reference ROT",
                math.degrees(params["heading_rate_limit_rad_s"]) * 60,
                "°/min",
                "controller.heading_rate_limit_rad_s",
            )
        for index, axis in enumerate(("Surge", "Sway", "Yaw")):
            for bound, key in (("min", "min_output"), ("max", "max_output")):
                if key in params:
                    limit(
                        f"PID {axis} {bound}",
                        params[key][index] / 1000,
                        "kN·m" if index == 2 else "kN",
                        f"controller.{key}[{index}]",
                    )
    if physical:
        for label, key, scale, unit in (
            ("Max rudder angle", "rudder_angle_limit_rad", 180 / math.pi, "°"),
            ("Max rudder rate", "rudder_rate_rad_s", 180 / math.pi, "°/s"),
            ("Main thrust rate", "main_rate_n_s", 0.001, "kN/s"),
            ("Bow thrust rate", "bow_rate_n_s", 0.001, "kN/s"),
            ("Bow derating starts", "bow_derate_start_mps", 1, "m/s STW"),
            ("Bow lockout", "bow_lockout_mps", 1, "m/s STW"),
            ("Bow unlock below", "bow_unlock_mps", 1, "m/s STW"),
        ):
            limit(label, getattr(physical, key) * scale, unit, f"actuator.fcb45_parameters.{key}")

    propulsion = []
    if layout:
        for spec in layout.actuators:
            key = spec.actuator_id
            angles = getattr(actuator, "rudder_angles_rad", {})
            requested_angles = getattr(actuator, "rudder_requested_angles_rad", {})
            propulsion.append(
                {
                    "id": key,
                    "kind": spec.kind,
                    "actual_n": actuator.actuator_outputs_n.get(key) if actuator else None,
                    "command_n": actuator.actuator_commands_n.get(key) if actuator else None,
                    "angle_deg": math.degrees(angles[key]) if key in angles else None,
                    "command_angle_deg": math.degrees(requested_angles[key]) if key in requested_angles else None,
                    "min_force_n": spec.min_force_n,
                    "max_force_n": spec.max_force_n,
                    "max_angle_deg": math.degrees(physical.rudder_angle_limit_rad) if physical else None,
                    "rate_limited": key in actuator.rate_limited_actuators if actuator else False,
                    "health": allocator.actuator_health.get(key) if allocator else None,
                }
            )
    return {
        "config_hash": config.config_hash,
        "tick": stack.tick,
        "roll_deg": math.degrees(plant.roll_rad) if "ROLL_4DOF" in plant.capabilities else None,
        "roll_rate_deg_s": math.degrees(plant.roll_rate_radps) if "ROLL_4DOF" in plant.capabilities else None,
        "environment": environment,
        "propulsion": propulsion,
        "propulsion_status": "IDEAL" if actuator_config is None else "AVAILABLE" if actuator else "WAITING",
        "actuator_time_s": actuator.time_s if actuator else None,
        "bow_authority": getattr(actuator, "bow_authority", None),
        "constraints": constraints,
        "weather_limits": None,
    }
