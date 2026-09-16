"""A route refresh must target the next waypoint on the occupied segment."""

import json
from pathlib import Path

import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.native import NativeModule


def test_route_refresh_does_not_target_the_already_passed_waypoint():
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    stamp = 2_000_000_000_000_000_000
    header = {"frame_id": "odom", "stamp": {"sec": 2_000_000_000, "nanosec": 0}}
    zero = {"x": 0.0, "y": 0.0, "z": 0.0}
    odom = {
        "header": header,
        "child_frame_id": "base_link",
        "pose": {"covariance": [0.0] * 36, "pose": {"position": {**zero, "x": 150.0}, "orientation": {**zero, "w": 1.0}}},
        "twist": {"covariance": [0.0] * 36, "twist": {"linear": {**zero, "x": 4.0}, "angular": zero}},
    }
    path = {
        "header": header,
        "poses": [
            {
                "header": header,
                "pose": {"position": {"x": x, "y": 0.0, "z": 10.0}, "orientation": {"x": 0.0, "z": 8.0, "y": 1.0, "w": 1.0}},
            }
            for x in (0.0, 100.0, 200.0, 300.0)
        ],
    }
    with NativeModule(config.build_directory, "ship_guidance_node", config.parameters()["ship_guidance_node"]) as module:
        module.invoke("odom_callback", odom, stamp)
        result = module.invoke("path_callback", path, stamp)
        assert result["state"]["segment_index"] == 2


def test_frozen_late_recovery_selects_the_occupied_segment():
    data = json.loads((Path(__file__).parent / "fixtures/original_gnc/recovery-guidance-index.json").read_text())
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native build required")
    with NativeModule(config.build_directory, "ship_guidance_node", config.parameters()["ship_guidance_node"]) as module:
        module.invoke("odom_callback", data["odometry"], data["time_ns"])
        result = module.invoke("path_callback", data["path"], data["time_ns"])
        assert result["state"]["segment_index"] == data["expected_target_index"] == 189
