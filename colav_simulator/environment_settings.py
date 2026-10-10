"""Session-owned physical environment and DT appearance settings."""

from __future__ import annotations

import copy
import math
from typing import Any

# Wind/waves/current directions are compass bearings FROM north, clockwise.
FIELDS = [
    ("wind_speed_mps", "风速 U10", "风浪流", 6.0, 0, 35, "m/s"),
    ("wind_from_deg", "风向（来自）", "风浪流", 45.0, 0, 360, "°"),
    ("current_speed_mps", "流速", "风浪流", 0.3, 0, 5, "m/s"),
    ("current_from_deg", "流向（来自）", "风浪流", 90.0, 0, 360, "°"),
    ("wave_hs_m", "有效波高 Hs", "风浪流", 0.5, 0, 10, "m"),
    ("wave_period_s", "波浪周期", "风浪流", 6.0, 1, 25, "s"),
    ("wave_from_deg", "浪向（来自）", "风浪流", 90.0, 0, 360, "°"),
    ("time_of_day_hours", "日照时间", "天气与光照", 12.0, 0, 24, "h"),
    ("cloud_cover", "云量", "天气与光照", 0.4, 0, 1, ""),
    ("fog_distance_m", "能见度", "天气与光照", 3000.0, 100, 8000, "m"),
    ("wave_development", "波浪发展度", "天气与光照", 0.5, 0, 1, ""),
    ("wave_alignment", "浪向集中度", "天气与光照", 0.7, 0, 1, ""),
    ("precipitation_intensity", "降水强度", "降水与画面", 0.5, 0, 1, ""),
]
CHOICES = {
    "spectrum_style": ("波谱外观（近似）", "天气与光照", "jonswap", ["pm", "jonswap", "tma"]),
    "atmosphere": ("大气预设", "天气与光照", "hazy_clear", ["hazy_clear", "cumulonimbus", "thunderstorm"]),
    "quality": ("DT 渲染质量", "降水与画面", "high", ["high", "low"]),
}
ATMOSPHERE_PRESETS = {
    "hazy_clear": {"cloud_cover": 0.35, "fog_distance_m": 8000, "rain_enabled": False, "thunder_enabled": False},
    "cumulonimbus": {"cloud_cover": 0.8, "fog_distance_m": 4000, "rain_enabled": False, "thunder_enabled": False},
    "thunderstorm": {"cloud_cover": 0.95, "fog_distance_m": 1500, "rain_enabled": True, "thunder_enabled": True},
}

BOOLS = {"rain_enabled": "雨", "snow_enabled": "雪", "thunder_enabled": "雷电", "wet_lens_enabled": "湿镜头"}


def settings_schema() -> list[dict[str, Any]]:
    """Publish the same ranges/defaults used by session validation."""
    fields = [
        {"key": k, "label": label, "group": group, "default": default, "min": lo, "max": hi, "unit": unit, "type": "number"}
        for k, label, group, default, lo, hi, unit in FIELDS
    ]
    fields += [
        {"key": k, "label": label, "group": group, "default": default, "options": options, "type": "select"}
        for k, (label, group, default, options) in CHOICES.items()
    ]
    fields += [
        {"key": k, "label": label, "group": "降水与画面", "default": False, "type": "boolean"} for k, label in BOOLS.items()
    ]
    next(f for f in fields if f["key"] == "atmosphere")["presets"] = copy.deepcopy(ATMOSPHERE_PRESETS)
    return fields


def normalize_settings(value: dict | None) -> dict:
    """Reject unknown, non-finite and out-of-range values; fill documented defaults."""
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("environment_settings must be an object")
    schema = settings_schema()
    unknown = set(value) - {f["key"] for f in schema}
    if unknown:
        raise ValueError(f"Unknown environment settings: {sorted(unknown)}")
    result = {}
    for f in schema:
        v = value.get(f["key"], f["default"])
        if f["type"] == "number":
            if (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or not f["min"] <= v <= f["max"]
            ):
                raise ValueError(f"{f['key']} must be finite in [{f['min']}, {f['max']}]")
            v = float(v)
        elif f["type"] == "boolean":
            if not isinstance(v, bool):
                raise ValueError(f"{f['key']} must be boolean")
        elif v not in f["options"]:
            raise ValueError(f"Invalid {f['key']}")
        result[f["key"]] = v
    return result


def original_parameters(parameters: dict, settings: dict | None) -> dict:
    """Override original environmental initialization only; frozen source stays intact."""
    result = copy.deepcopy(parameters)
    if settings is None:
        return result
    s = normalize_settings(settings)
    mapping = {
        "wind_engine_node": {
            "u10": s["wind_speed_mps"],
            "wind_direction": s["wind_from_deg"],
            "wind_direction_is_from": True,
        },
        "current_engine_node": {
            "v_tide_surf": s["current_speed_mps"],
            "dir_tide": s["current_from_deg"],
            "v_circ_surf": 0.0,
            "v_wind_surf": 0.0,
            "current_direction_is_from": True,
        },
        "wave_engine_node": {
            "Hs": s["wave_hs_m"],
            "Tz": s["wave_period_s"],
            "direction_rad": math.radians(s["wave_from_deg"]),
            "wave_direction_is_from": True,
        },
    }
    for module, values in mapping.items():
        for key, value in values.items():
            result[module][key]["value"] = value
    return result


def modular_environment(config: dict, settings: dict) -> dict:
    """Configure the admitted analytic field using FROM-to-NE direction conversion."""
    result = copy.deepcopy(config)
    field = result["modules"].get("environment")
    if field is None:
        return result
    s = normalize_settings(settings)

    def vector(speed: float, bearing: float) -> list[float]:
        angle = math.radians(bearing)
        return [-speed * math.cos(angle), -speed * math.sin(angle)]

    field.setdefault("parameters", {}).update(
        wind_velocity_ne=vector(s["wind_speed_mps"], s["wind_from_deg"]),
        current_velocity_ne=vector(s["current_speed_mps"], s["current_from_deg"]),
        wave_significant_height_m=s["wave_hs_m"],
        wave_peak_period_s=s["wave_period_s"],
        wave_direction_to_rad=math.radians((s["wave_from_deg"] + 180) % 360),
    )
    return result
