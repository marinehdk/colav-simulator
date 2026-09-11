"""Write the approved fourteen routes and five original-environment profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def route_cases() -> list[dict]:
    """Expand the approved route groups into explicit paired inputs."""
    straight = [(0.0, 0.0), (2500.0, 0.0)]
    rows = [
        ("R01", straight, 0.0, 0.0),
        ("R02-plus", straight, 15.0, 0.0),
        ("R02-minus", straight, -15.0, 0.0),
        ("R03-plus", straight, 0.0, math.radians(5.0)),
        ("R03-minus", straight, 0.0, math.radians(-5.0)),
        ("R04", [(0, 0), (10000, 0)], 0.0, 0.0),
        ("R05", [(0, 0), (1500, 0), (1500, -1500)], 0.0, 0.0),
        ("R06", [(0, 0), (1500, 0), (1500, 1500)], 0.0, 0.0),
        ("R07", [(0, 0), (1200, 0), (2200, 800), (3200, -800), (4400, 0)], 0.0, 0.0),
        ("R08", [(0, 0), (1600, 0), (1600, 1200), (0, 1200)], 0.0, 0.0),
        ("R09", [(0, 0), (1600, 0), (1600, 1600), (0, 1600), (0, 0)], 0.0, 0.0),
        (
            "R10",
            [(500 * math.sin(math.radians(a)), 500 * (1 - math.cos(math.radians(a)))) for a in range(0, 91, 10)]
            + [(500, 2000)],
            0.0,
            0.0,
        ),
        ("R11", [(0, 0), (800, 0), (1600, 0), (2400, 0), (3200, 0), (4000, 0)], 0.0, 0.0),
        ("R12", [(0, 0), (2000, 0)], 0.0, 0.0),
    ]
    cases = []
    for name, points, offset, heading in rows:
        speeds = [2.0, 4.0, 7.8, 4.0, 1.0, 1.0] if name == "R11" else [7.8] * len(points)
        length = sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False))
        duration = max(900.0, 3 * length / (2.0 if name == "R11" else 7.8) + 300)
        modes = ["cruise"] * len(points)
        if name == "R12":
            modes[-1] = "dp_hold"
        cases.append(
            {
                "schema": "original-gnc.route-case.v1",
                "route_case_id": name,
                "waypoints": [{"north_m": float(p[0]), "east_m": float(p[1])} for p in points],
                "speed_limit_mps": speeds,
                "navigation_mode": modes,
                "initial": {
                    "north_m": 0.0,
                    "east_m": offset,
                    "heading_rad": heading,
                    "surge_mps": 2.0 if name == "R11" else 7.8,
                    "sway_mps": 0.0,
                    "yaw_rate_radps": 0.0,
                    "roll_rad": 0.0,
                    "roll_rate_radps": 0.0,
                },
                "auto_initial_yaw_from_route": not name.startswith("R03"),
                "origin_wgs84": {"latitude_deg": 58.0, "longitude_deg": 6.0},
                "water_depth_m": 20.0,
                "max_duration_s": math.ceil(duration),
                "observation": {
                    "through_distance_m": 2000.0 if name == "R01" else None,
                    "hold_window_s": 60.0 if name == "R12" else 0.0,
                },
            }
        )
    return cases


def environments() -> dict[str, dict]:
    """Use original launch argument names and explicit from-direction units."""
    calm = {
        "enable_wind": False,
        "enable_current": False,
        "enable_wave": False,
        "wind_u10": 0.0,
        "wind_direction": 90.0,
        "wind_direction_is_from": True,
        "current_speed": 0.0,
        "current_direction": 90.0,
        "current_direction_is_from": True,
        "wave_Hs": 0.0,
        "wave_Tz": 6.0,
        "wave_direction": 90.0,
        "wave_direction_is_from": True,
        "current_random_seed_enable": False,
        "current_seed": 20240618,
        "wave_random_seed_enable": False,
        "wave_seed": 20240618,
    }
    return {
        "E0": calm,
        "E1": {**calm, "enable_wind": True, "wind_u10": 8.0},
        "E2": {**calm, "enable_current": True, "current_speed": 0.4},
        "E3": {**calm, "enable_wave": True, "wave_Hs": 0.5},
        "E4": {
            **calm,
            "enable_wind": True,
            "wind_u10": 6.0,
            "wind_direction": 45.0,
            "enable_current": True,
            "current_speed": 0.3,
            "enable_wave": True,
            "wave_Hs": 0.5,
        },
    }


def write_cases(output: Path) -> dict:
    """Freeze case contents without overwriting different prior inputs."""
    output.mkdir(parents=True, exist_ok=True)
    files = []
    for route in route_cases():
        for environment_id, environment in environments().items():
            case_id = f"{route['route_case_id']}-{environment_id}"
            case = {
                **route,
                "case_id": case_id,
                "environment_id": environment_id,
                "original_launch_environment": environment,
            }
            content = (json.dumps(case, indent=2, sort_keys=True) + "\n").encode()
            path = output / f"{case_id}.json"
            if path.exists() and path.read_bytes() != content:
                raise FileExistsError(f"Refusing to change an already frozen case: {path}")
            path.write_bytes(content)
            files.append({"case_id": case_id, "file": path.name, "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {"schema": "original-gnc.case-manifest.v1", "cases": files}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"output": str(args.output), "case_count": len(write_cases(args.output)["cases"])}))
