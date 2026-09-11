"""Approved planner-authority translation into unchanged original route contracts."""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.modular_gnc.route_bridge import ProductRouteBridge
from colav_simulator.original_gnc.geometry import stamp
from colav_simulator.original_gnc.native import OriginalGncError


def avoidance_constraints_active(algorithm: str, details: dict) -> bool:
    """Use planner-owned constraint/lifecycle evidence; never reclassify encounters."""
    if algorithm == "vo":
        required = {
            "hard_constraint_count",
            "active_rules",
            "give_way_commitment_active",
            "stand_on_hold_active",
            "static_hazard_count",
        }
        if not required <= details.keys():
            raise OriginalGncError("VO trace is missing its constraint/lifecycle evidence")
        return bool(
            details["hard_constraint_count"]
            or details["active_rules"]
            or details["give_way_commitment_active"]
            or details["stand_on_hold_active"]
            or details["static_hazard_count"]
        )
    if algorithm == "potocnik_colreg_fan_mpc":
        required = {"active_encounters", "static_constraint_active", "dynamic_safety_buffer_recovery"}
        if not required <= details.keys():
            raise OriginalGncError("Fan-MPC trace is missing its constraint/lifecycle evidence")
        return bool(
            details["active_encounters"] or details["static_constraint_active"] or details["dynamic_safety_buffer_recovery"]
        )
    raise OriginalGncError(f"No held-intent contract for {algorithm}")


class OriginalPlanBridge:
    """Keep accepted Mid routes and approved 120 m VO/Fan intent lines distinct."""

    def __init__(self, ship: Any, dt_s: float):
        self.ship = ship
        self.dt_s = dt_s
        self._mid = ProductRouteBridge(ship._legacy, dt_s)
        self._heading = None
        self._geometry = None
        self._algorithm = None
        self._intent_generation = 0
        self._last_solve_time = None
        self._last_submission = None
        self.last_outcome = None

    def _base(self, algorithm: str, plan_id: str, valid_until_ns: int) -> dict:
        return {
            "header": {"stamp": stamp(self.ship.stack.time_ns), "frame_id": "map"},
            "plan_id": plan_id,
            "parent_route_id": self.ship._nominal_id,
            "parent_route_revision": self.ship._nominal_revision,
            "behavior_mode": "avoidance",
            "command_source": algorithm,
            "latitude": [],
            "longitude": [],
            "command_speed_mps": [],
            "command_heading_deg": [],
            "navigation_mode": [],
            "valid_until": stamp(valid_until_ns),
            "require_exact_heading": True,
            "require_exact_speed": True,
            "allow_degraded_execution": False,
            "has_return_to_route_point": False,
            "return_latitude": 0.0,
            "return_longitude": 0.0,
        }

    def _deliver(self, request: dict, identity: dict) -> None:
        before = len(self.ship._events)
        self.ship._requested_plans.append(
            {
                "kind": "avoidance",
                "time_ns": self.ship.stack.time_ns,
                "identity": copy.deepcopy(identity),
                "message": copy.deepcopy(request),
            }
        )
        self.ship.stack.publish("/colav/avoidance_plan", "ship_interfaces/msg/AvoidancePlan", request)
        feedback = [
            e["message"]["fields"]
            for e in self.ship._events[before:]
            if e.get("topic") in {"/gnc/route_execution_status", "/route_planning/route_plan_status"}
        ]
        rejected = any(f.get("rejected") is True or f.get("accepted") is False for f in feedback)
        degraded = any(f.get("degraded") is True for f in feedback)
        self.last_outcome = {
            "plan_id": request["plan_id"],
            "time_ns": self.ship.stack.time_ns,
            "accepted": bool(feedback) and not rejected and not degraded,
            "rejected": rejected,
            "degraded": degraded,
            "feedback": copy.deepcopy(feedback),
        }
        self.ship._events.append(
            {"sequence": len(self.ship._events), "event": "bridge_result", **copy.deepcopy(self.last_outcome)}
        )

    def _return_nominal(self, algorithm: str) -> None:
        state = self.ship.stack.states["active_route_manager_node"]
        if state["active_avoidance"]:
            request = self._base(algorithm, f"{algorithm}-return-to-nominal", self.ship.stack.time_ns)
            request["behavior_mode"] = "return_to_route"
            self._deliver(request, {"authority": "original_nominal_guidance", "reason": "planner_constraints_clear"})
        self._heading = None
        self._geometry = None
        self._last_submission = None

    # Keep source contract branches together for audit against the frozen implementation.
    def submit(self, t: float) -> None:  # noqa: PLR0915
        """Translate the current accepted authority without extending its validity."""
        reader = getattr(self.ship._legacy._colav, "get_route_authority", None)
        data = reader() if callable(reader) else self.ship._legacy.get_colav_data()
        planner = data.get("planner", {})
        algorithm = planner.get("algorithm_id")
        details = planner.get("algorithm_details", {})
        if not planner.get("feasible", False):
            raise ColavExecutionError(
                PlanStatus.INFEASIBLE,
                "An infeasible planner result cannot become an original GNC plan",
                details=copy.deepcopy(planner),
            )
        command = planner.get("selected_command", {})
        heading, speed = command.get("course_rad"), command.get("speed_mps")
        if (
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (heading, speed))
            or speed < 0
        ):
            raise OriginalGncError("Accepted planner command requires finite course and nonnegative speed")
        if algorithm in {"vo", "potocnik_colreg_fan_mpc"}:
            if planner.get("solver_executed") is True:
                self._last_solve_time = t
            if not avoidance_constraints_active(algorithm, details):
                self._return_nominal(algorithm)
                return
            period = details.get("solve_period_s")
            if (
                isinstance(period, bool)
                or not isinstance(period, (int, float))
                or not math.isfinite(period)
                or period <= 0
                or self._last_solve_time is None
            ):
                raise OriginalGncError("Held intent has no verified solve time/period")
            valid_until_s = self._last_solve_time + period
            if self._heading != heading or self._algorithm != algorithm:
                origin = self.ship.state[:2].copy()
                length = 2.0 * self.ship._parameters["ship_guidance_node"]["lookahead_distance"]["value"]
                self._geometry = np.column_stack(
                    (origin, origin + length * np.array([math.cos(heading), math.sin(heading)]))
                )
                self._intent_generation += 1
            self._heading, self._algorithm = heading, algorithm
            geometry = self._geometry
            plan_id = f"{algorithm}-held-intent-{self._intent_generation}"
            speeds = np.full(2, speed)
            headings = [math.degrees(heading) % 360.0] * 2
            identity = {
                "algorithm": algorithm,
                "solve_id": planner.get("solve_id"),
                "authority": "held_course_speed_intent",
                "geometry": "fixed_anchor_2x_source_lookahead",
                "length_m": float(np.linalg.norm(geometry[:, 1] - geometry[:, 0])),
                "planner_speed_semantics": "SOG",
                "source_speed_semantics": "original_route_speed_limit",
                "source_heading_field_semantics": "original_route_bearing_consistency_gate",
            }
        elif algorithm == "mid_mpc_ipopt":
            decision = self._mid.current_route(tick=round(t / self.dt_s), planner_data=data)
            if decision.failure is not None or decision.route is None:
                raise OriginalGncError(f"Mid-MPC accepted route unavailable: {decision.failure}")
            route = decision.route
            receipt = details["accepted_plan_receipt"]
            plan_id = "mid-mpc-" + receipt["receipt_hash"][:24]
            geometry = route.waypoints_ne_m
            speeds = route.speed_mps
            # Accepted prediction geometry is a route. It is not a sequence of
            # body-heading commands, so retain only its geometric authority.
            headings = []
            valid_until_s = route.valid_until_tick * self.dt_s
            identity = {
                "algorithm": algorithm,
                "authority": "accepted_mid_mpc_receipt",
                "receipt_hash": receipt["receipt_hash"],
                "accepted_sequence": receipt["accepted_sequence"],
                "planner_speed_semantics": "accepted_command_speed",
                "source_speed_semantics": "original_route_speed_limit",
            }
        else:
            raise OriginalGncError(f"Planner not supported by the original GNC bridge: {algorithm}")
        if valid_until_s <= t:
            raise OriginalGncError("Accepted planner authority has expired; it cannot be extended by the bridge")
        signature = (plan_id, float(speed), valid_until_s)
        if signature == self._last_submission:
            return
        deadline_ns = self.ship.stack.epoch_ns + round((valid_until_s - self.ship._planner_time_origin) * 1e9)
        request = self._base(algorithm, plan_id, deadline_ns)
        request["latitude"], request["longitude"] = self.ship.frame.geographic(geometry)
        request["command_speed_mps"] = np.asarray(speeds, dtype=float).tolist()
        request["command_heading_deg"] = headings
        request["require_exact_heading"] = bool(headings)
        request["navigation_mode"] = ["cruise"] * geometry.shape[1]
        self._deliver(request, identity)
        self._last_submission = signature
