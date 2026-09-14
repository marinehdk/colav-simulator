"""Run the same finite velocity-input sequence on native or independent ROS kernels."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.geometry import RouteFrame, nominal_route, stamp
from colav_simulator.original_gnc.stack import NativeStack

parser = argparse.ArgumentParser()
for key in ["source", "build", "output"]:
    parser.add_argument("--" + key, type=Path, required=True)
parser.add_argument("--reference-drivers", type=Path)
parser.add_argument("--environment", action="store_true")
a = parser.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
if a.reference_drivers:
    os.environ.update(ROS_DOMAIN_ID="189", ROS_LOCALHOST_ONLY="1")
    import rclpy  # noqa: PLC0415
    import source_kernel_proxies as proxies  # noqa: PLC0415

    from colav_simulator.original_gnc import stack as scheduling  # noqa: PLC0415

    rclpy.init()
    proxies.SETTINGS.update(source=a.source, drivers=a.reference_drivers, output=a.output / "nodes", domain=189)
    scheduling.NativeModule = proxies.CppSourceKernel
    scheduling.NativePolicy = proxies.SourcePolicy
    scheduling.NativeObserver = proxies.SourceObserver
cfg = OriginalGncConfig(a.source.resolve(), a.build.resolve(), a.environment)
roots, assets, policy = cfg.source_assets()
params = cfg.parameters()
for k, v in {
    "initial_position.x": 0.0,
    "initial_position.y": 0.0,
    "initial_position.yaw": 0.0,
    "initial_velocity.u": 5.0,
    "initial_velocity.v": 0.0,
    "initial_velocity.r": 0.0,
}.items():
    params["ship_dynamics_node"][k]["value"] = v
records = []
publications = []


def capture(event: dict) -> None:
    """Record the complete C++ publication stream for independent comparison."""
    if event.get("event") == "publish" and "port" in event:
        publications.append(json.loads(json.dumps(event)))


with NativeStack(
    cfg.build_directory,
    params,
    roots,
    policy,
    enabled_environment=("wind", "current", "wave") if a.environment else (),
    asset_paths=assets,
    trace=capture,
) as s:
    frame = RouteFrame(0, 0)
    s.publish(
        "/route_planning/route_plan",
        "ship_interfaces/msg/RoutePlan",
        nominal_route(frame, np.array([[0.0, 10000.0], [0.0, 0.0]]), np.array([8.0, 8.0]), "mission", 1, s.time_ns),
    )
    commands = {
        11: ("cruise", 0.1, 8.0, 20),
        18: ("avoidance", 0.2, 7.0, 20),
        25: ("emergency_avoidance", 0.2, 3.2, 20),
        30: ("avoidance", 0.1, 7.0, 20),
        36: ("avoidance", 0.1, 0.0, 10),
        40: ("return_to_route", 0.0, 0.0, 10),
        44: ("avoidance", 0.1, 6.0, 2),
        50: ("return_to_route", 0.0, 0.0, 10),
    }
    for i in range(110):
        t = i * 0.5
        if t in commands:
            mode, course, speed, duration = commands[t]
            req = {
                "header": {"stamp": stamp(s.time_ns), "frame_id": "map"},
                "intent_id": "case-" + str(int(t)),
                "parent_route_id": "mission",
                "parent_route_revision": 1,
                "behavior_mode": mode,
                "command_source": "reference-test",
                "course_rad": course,
                "speed_mps": speed,
                "speed_reference": "SOG",
                "valid_until": stamp(s.time_ns + round(duration * 1e9)),
            }
            s.publish("/colav/velocity_intent", "ship_interfaces/msg/VelocityIntent", req)
        s.advance(0.5)
        records.append(
            json.loads(
                json.dumps(
                    {
                        "t": t + 0.5,
                        "states": s.states,
                        "outputs": {
                            k: v
                            for k, v in s.latest.items()
                            if k
                            in [
                                "/control/speed_setpoint",
                                "/control/heading_setpoint",
                                "/gnc/velocity_execution_status",
                                "/gnc/route_execution_status",
                            ]
                        },
                    }
                )
            )
        )
(a.output / "samples.json").write_text(json.dumps(records))
(a.output / "cpp-outputs.json").write_text(json.dumps(publications))
if a.reference_drivers:
    if "liboriginal_gnc" in Path("/proc/self/maps").read_text():
        raise RuntimeError("Reference process loaded the embedded native library")
    rclpy.shutdown()
print("samples", len(records), "reference", bool(a.reference_drivers), flush=True)
