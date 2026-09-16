"""Native guidance must localize turn limits and retain the braking envelope."""

import json
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.geometry import RouteFrame
from colav_simulator.original_gnc.native import NativeModule


@pytest.mark.parametrize("exact", [False, True])
def test_native_turn_limit_does_not_cap_straight_route_suffix(exact):
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Native GNC build required")
    fixture = json.loads((Path(__file__).parent / "fixtures/original_gnc/mid-overtaking-route-5s.json").read_text())
    points = np.array([[0, 1000, 1000, 3000, 5000], [0, 0, 200, 200, 200]], dtype=float)
    lat, lon = RouteFrame(0, 0).geographic(points)
    request = {
        **fixture["active"],
        "plan_id": "local-turn",
        "parent_route_id": fixture["nominal"]["route_id"],
        "parent_route_revision": 1,
        "latitude": lat,
        "longitude": lon,
        "command_speed_mps": [8.0] * 5,
        "navigation_mode": ["avoidance"] * 4 + ["cruise"],
        "command_heading_deg": [],
        "require_exact_speed": exact,
        "require_exact_heading": False,
        "allow_degraded_execution": True,
        "valid_until": {"sec": 2_000_000_100, "nanosec": 0},
    }
    with NativeModule(
        config.build_directory, "active_route_manager_node", config.parameters()["active_route_manager_node"]
    ) as manager:
        manager.invoke("nominal_route_callback", fixture["nominal"], 2_000_000_000_000_000_000)
        result = manager.invoke("avoidance_plan_callback", request, 2_000_000_001_000_000_000)
    outputs = [entry["message"]["fields"] for entry in result["outputs"]]
    routes = [message for message in outputs if "speed_limit_mps" in message]
    if exact:
        assert not routes
        assert any(message.get("rejected") and message.get("reason") == "yaw_rate_too_high" for message in outputs)
        return
    assert len(routes) == 1
    speeds = np.array(routes[0]["speed_limit_mps"])
    assert speeds[1] < 4.2 and speeds[2] < 4.2
    assert speeds[3] == 8.0  # 2km clear outgoing leg can recover cruise speed
    projected = np.vstack(
        ((np.array(lat) - lat[0]) * 111320, (np.array(lon) - lon[0]) * 111320 * np.cos(np.radians(lat[0])))
    )
    lengths = np.linalg.norm(np.diff(projected), axis=0)
    assert np.all(speeds[:-1] ** 2 <= speeds[1:] ** 2 + 2 * 0.08 * lengths + 1e-9)
