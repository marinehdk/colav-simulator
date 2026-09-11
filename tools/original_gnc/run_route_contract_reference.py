"""Exercise original live route admission and expiry through its public ROS inputs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import run_native_reference as native
from geographiclib.geodesic import Geodesic
from rclpy.duration import Duration
from ship_interfaces.msg import AvoidancePlan


class ContractRecorder(native.Recorder):
    """Inject a fixed contract sequence after observing actual nominal admission."""

    def __init__(self, case: Any, directory: Path):
        super().__init__(case, directory)
        self.case = case
        self.directory = directory
        self.requests = (directory / "contract-requests.jsonl").open("w", buffering=1)
        self.avoidance = self.create_publisher(AvoidancePlan, "/colav/avoidance_plan", 20)
        self.contract_anchor_ns = None
        self.next_contract = 0
        self.contracts = [
            (2.0, "wrong_parent"),
            (4.0, "expired"),
            (6.0, "excess_speed"),
            (14.0, "near_intent"),
            (16.0, "legal_future"),
            (17.0, "duplicate_refresh"),
            (18.0, "wrong_revision"),
            (20.0, "missing_validity"),
            (22.0, "return_nominal"),
        ]
        self.contract_timer = self.create_timer(0.05, self.inject)

    # Keep source contract branches together for audit against the frozen implementation.
    def inject(self):  # noqa: PLR0912, PLR0915
        status = self.last.get("/route_planning/route_plan_status")
        geo = self.last.get("/ship/geo_position")
        if self.contract_anchor_ns is None:
            if status and status.get("accepted") and geo and geo.get("origin_locked"):
                self.contract_anchor_ns = self.get_clock().now().nanoseconds
            return
        if self.next_contract >= len(self.contracts):
            return
        elapsed, name = self.contracts[self.next_contract]
        now = self.get_clock().now()
        if (now.nanoseconds - self.contract_anchor_ns) * 1e-9 < elapsed:
            return
        self.next_contract += 1
        msg = AvoidancePlan()
        msg.header.stamp = now.to_msg()
        msg.header.frame_id = "map"
        msg.plan_id = "contract-" + name
        msg.parent_route_id = "original-" + self.case["case_id"]
        msg.parent_route_revision = 1
        msg.behavior_mode = "avoidance"
        msg.command_source = "original_gnc_contract_test"
        msg.valid_until = (now + Duration(seconds=10.0)).to_msg()
        msg.require_exact_heading = True
        msg.require_exact_speed = True
        msg.allow_degraded_execution = False
        origin = self.case["origin_wgs84"]
        points = [(0.0, 0.0), (2500.0, 80.0)]
        if name == "near_intent":
            n, e = geo["x_ned"], geo["y_ned"]
            points = [(n, e), (n + 120 * math.cos(0.2), e + 120 * math.sin(0.2))]
        for n, e in points:
            p = Geodesic.WGS84.Direct(
                origin["latitude_deg"], origin["longitude_deg"], math.degrees(math.atan2(e, n)), math.hypot(n, e)
            )
            msg.latitude.append(p["lat2"])
            msg.longitude.append(p["lon2"])
        heading = math.degrees(math.atan2(points[1][1] - points[0][1], points[1][0] - points[0][0])) % 360
        msg.command_heading_deg = [heading] * 2
        msg.command_speed_mps = [7.8] * 2
        msg.navigation_mode = ["cruise"] * 2
        if name == "wrong_parent":
            msg.parent_route_id = "not-the-active-mission"
        elif name == "expired":
            msg.valid_until = (now - Duration(seconds=1.0)).to_msg()
        elif name == "excess_speed":
            msg.command_speed_mps = [9.0, 9.0]
        elif name == "duplicate_refresh":
            msg.plan_id = "contract-legal_future"
        elif name == "wrong_revision":
            msg.parent_route_revision = 2
        elif name == "missing_validity":
            msg.valid_until.sec = 0
            msg.valid_until.nanosec = 0
        elif name == "return_nominal":
            msg.behavior_mode = "return_to_route"
        self.requests.write(
            json.dumps(
                {
                    "case": name,
                    "time_ns": now.nanoseconds,
                    "elapsed_since_nominal_admission_s": (now.nanoseconds - self.contract_anchor_ns) * 1e-9,
                    "message": native.message_to_ordereddict(msg),
                }
            )
            + "\n"
        )
        self.avoidance.publish(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["workspace", "case", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--domain", type=int, default=173)
    args = parser.parse_args()
    native.Recorder = ContractRecorder
    result = native.run(args.case, args.workspace, args.output, 36.0, args.domain)
    print(json.dumps({"failure": result["failure"], "message_counts": result["message_counts"]}, indent=2))
