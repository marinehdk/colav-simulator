"""Run frozen route/environment cases on the assembled local original GNC."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

from geographiclib.geodesic import Geodesic

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.stack import NativeStack


def run_case(case_path: Path, build: Path, source: Path, output: Path, *, plant_rate_hz: float | None = None) -> dict:  # noqa: PLR0915
    """Keep source case inputs and stop policy; record full original outputs."""
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    case = json.loads(case_path.read_text())
    config = OriginalGncConfig(source, build)
    roots, assets, policy = config.source_assets()
    parameters = config.parameters()
    if plant_rate_hz is not None:
        if not math.isfinite(plant_rate_hz) or plant_rate_hz <= 0:
            raise ValueError("Sensitivity-test plant frequency must be finite and positive")
        parameters["ship_dynamics_node"]["update_rate"]["value"] = plant_rate_hz

    def set_value(module: str, name: str, value: Any):
        parameters[module][name]["value"] = value

    initial = case["initial"]
    for name, key in [
        ("initial_position.x", "north_m"),
        ("initial_position.y", "east_m"),
        ("initial_position.yaw", "heading_rad"),
        ("initial_velocity.u", "surge_mps"),
        ("initial_velocity.v", "sway_mps"),
        ("initial_velocity.r", "yaw_rate_radps"),
    ]:
        set_value("ship_dynamics_node", name, initial[key])
    set_value("ship_dynamics_node", "water_depth", case["water_depth_m"])
    set_value("ship_dynamics_node", "auto_initial_yaw_from_route", case["auto_initial_yaw_from_route"])
    env = case["original_launch_environment"]
    for prefix, module, mapping in [
        (
            "wind",
            "wind_engine_node",
            {"wind_u10": "u10", "wind_direction": "wind_direction", "wind_direction_is_from": "wind_direction_is_from"},
        ),
        (
            "current",
            "current_engine_node",
            {
                "current_speed": "v_tide_surf",
                "current_direction": "dir_tide",
                "current_direction_is_from": "current_direction_is_from",
                "current_random_seed_enable": "current_random_seed_enable",
                "current_seed": "current_seed",
            },
        ),
        (
            "wave",
            "wave_engine_node",
            {
                "wave_Hs": "Hs",
                "wave_Tz": "Tz",
                "wave_direction_is_from": "wave_direction_is_from",
                "wave_random_seed_enable": "wave_random_seed_enable",
                "wave_seed": "wave_seed",
            },
        ),
    ]:
        for key, parameter in mapping.items():
            set_value(module, parameter, env[key])
        set_value("force_aggregator_node", "require_" + prefix + "_load", env["enable_" + prefix])
    set_value("wave_engine_node", "direction_rad", math.radians(env["wave_direction"]))
    enabled = tuple(name for name in ("wind", "current", "wave") if env["enable_" + name])
    counts = {}
    started = time.monotonic()
    stopped_on = "duration"
    with gzip.open(output / "topic-observations.jsonl.gz", "wt", compresslevel=3) as stream:

        def capture(event: Any):
            if event["event"] != "publish":
                return
            topic = event["topic"]
            counts[topic] = counts.get(topic, 0) + 1
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")

        with NativeStack(
            build, parameters, roots, policy, enabled_environment=enabled, asset_paths=assets, trace=capture
        ) as stack:
            origin = case["origin_wgs84"]
            route = {
                "header": {"stamp": {"sec": stack.time_ns // 1_000_000_000, "nanosec": 0}, "frame_id": ""},
                "route_id": "original-" + case["case_id"],
                "route_revision": 1,
                "route_type": "nominal",
                "latitude": [],
                "longitude": [],
                "speed_limit_mps": case["speed_limit_mps"],
                "navigation_mode": case["navigation_mode"],
            }
            for point in case["waypoints"]:
                n, e = point["north_m"], point["east_m"]
                geo = Geodesic.WGS84.Direct(
                    origin["latitude_deg"], origin["longitude_deg"], math.degrees(math.atan2(e, n)), math.hypot(n, e)
                )
                route["latitude"].append(geo["lat2"])
                route["longitude"].append(geo["lon2"])
            (output / "published-route.json").write_text(json.dumps(route, indent=2))
            (output / "parameters.json").write_text(json.dumps(parameters, indent=2))
            (output / "manifest.json").write_text(
                json.dumps(
                    {
                        "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
                        "source_manifest_sha256": json.loads((build / "build-manifest.json").read_text())[
                            "source_manifest_sha256"
                        ],
                        "build": json.loads((build / "build-manifest.json").read_text()),
                        "epoch_ns": stack.epoch_ns,
                        "scheduler": "source-periods-registration-order-breadth-first-v1",
                        "enabled_environment": enabled,
                        "numerical_sensitivity_variant": {"plant_rate_hz": plant_rate_hz} if plant_rate_hz else None,
                    },
                    indent=2,
                )
            )
            initial_state = stack.states["ship_dynamics_node"]
            stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", route)
            while stack.elapsed_s < case["max_duration_s"]:
                stack.advance(min(0.02, case["max_duration_s"] - stack.elapsed_s))
                through = case["observation"]["through_distance_m"]
                if through is not None and stack.states["ship_dynamics_node"]["eta"][0] >= through:
                    stopped_on = "through_distance"
                    break
            result = {
                "case_id": case["case_id"],
                "duration_s": stack.elapsed_s,
                "elapsed_wall_s": time.monotonic() - started,
                "initial_state": initial_state,
                "states": stack.states,
                "last_messages": stack.latest,
                "message_counts": counts,
                "stopped_on": stopped_on,
                "full_case_run": True,
                "failure": None,
                "scope": "embedded free closed-loop execution; comparison and task performance judged separately",
            }
            (output / "summary.json").write_text(json.dumps(result, indent=2))
    return {"case_id": case["case_id"], "duration_s": result["duration_s"], "elapsed_wall_s": result["elapsed_wall_s"]}


def run(cases: Any, build: Path, source: Path, output: Path, workers: int):
    """Freeze runtime code and execute each unchanged case in a fresh process."""
    output.mkdir(parents=True, exist_ok=True)
    runtime_root = Path(__file__).resolve().parents[2]
    snapshot = output / "runtime-source"
    identity = {}
    for directory in ("colav_simulator/original_gnc", "tools/original_gnc"):
        for path in (runtime_root / directory).rglob("*.py"):
            relative = path.relative_to(runtime_root)
            raw = path.read_bytes()
            target = snapshot / relative
            if target.exists() and target.read_bytes() != raw:
                raise ValueError(f"Campaign runtime changed: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            identity[str(relative)] = hashlib.sha256(raw).hexdigest()
    (snapshot / "manifest.json").write_text(json.dumps(identity, indent=2))
    manifest = json.loads((cases / "manifest.json").read_text())
    futures = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for case in manifest["cases"]:
            directory = output / case["case_id"]
            if (directory / "summary.json").exists():
                continue
            futures[pool.submit(run_case, cases / case["file"], build, source, directory)] = case["case_id"]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception as error:
                result = {"case_id": futures[future], "failure": repr(error)}
            with (output / "campaign-events.jsonl").open("a") as stream:
                stream.write(json.dumps(result) + "\n")
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["cases", "build", "source", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--workers", type=int, default=2)
    a = p.parse_args()
    run(a.cases.resolve(), a.build.resolve(), a.source.resolve(), a.output.resolve(), a.workers)
