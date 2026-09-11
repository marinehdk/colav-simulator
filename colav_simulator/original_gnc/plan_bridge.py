"""Approved planner-authority translation into unchanged original route contracts."""

from __future__ import annotations

import copy
import hashlib
import math
from collections.abc import Callable
from typing import Any

import numpy as np

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.modular_gnc.route_bridge import ProductRouteBridge
from colav_simulator.original_gnc.geometry import stamp
from colav_simulator.original_gnc.native import OriginalGncError
from colav_simulator.original_gnc.route_splice import (
    AVOIDANCE_MODE,
    FIRST_CHANGE_GATE_M,
    FIRST_CHANGE_MARGIN_M,
    LATERAL_ENVELOPE_M,
    MIN_SEGMENT_M,
    SEGMENT_FLOOR_M,
    ReferencePath,
    along_track_progress,
    blend_deviation_toward_reference,
    build_avoidance_route,
    first_change_distance_ahead,
    intent_line_deviation,
    max_lateral_delta,
    merge_short_segments,
)

# The VO solver re-solves internally every second; the frozen manager expires an
# avoidance plan whose valid_until has passed (active_route_manager maintenance)
# and answers expired arrivals with plan_expired. max() keeps slower planners
# (Fan-MPC) on their own period while giving every plan one live admission window.
_MIN_VALIDITY_S = 5.0
_RESUBMIT_INTERVAL_S = 10.0
# Held-tick command sampling differs from the solve tick by wrap-around noise at
# floating-point ULP scale (course remainder wrap). Exact-equality comparison
# declared a "new intent" every tick and rebuilt the splice against the freshly
# rotated mirror each time (fan-HO-E4: 22 splice generations in 50 s, 96.5 deg
# rejoin hooks). A held intent is only genuinely new when course or speed
# actually moved beyond these defensible thresholds.
INTENT_COURSE_TOLERANCE_RAD = math.radians(0.5)
INTENT_SPEED_TOLERANCE_MPS = 0.05

_ADDRESSABLE_PREFIXES = (
    "route update too frequent",
    "first changed waypoint",
    "dynamic route lateral offset exceeds limit",
    "reverse segment",
)
# Reject reasons emitted by the frozen active_route_manager's dynamic contract
# (kinematics, arbitration and plan lifecycle), coordinate_transform gates are
# geometry-addressable and classified below by topic and reason prefix.
_DYNAMIC_REASONS = frozenset(
    {
        "segment_too_short",
        "speed_exceeds_vessel_limit",
        "turn_radius_too_small",
        "yaw_rate_too_high",
        "decel_distance_not_enough",
        "heading_path_conflict",
        "avoidance_parent_route_version_mismatch",
        "plan_expired",
        "plan_valid_until_required",
        "invalid_avoidance_route",
        "heading_length_mismatch",
        "speed_length_mismatch",
        "invalid_command_heading",
        "projection_failed",
    }
)


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


def dynamic_encounter_active(algorithm: str, details: dict) -> bool:
    """Classify the planner evidence that shows a live DYNAMIC encounter.

    Static-hazard grid cells alone are not an encounter: they keep avoidance
    authority active (a deviation around the hazard is still executed) but must
    not tag long deviation stretches for the frozen 3.2 m/s guidance cap, which
    is leg-scoped on "avoidance" navigation modes (ship_guidance_node.cpp
    is_emergency_avoidance_mode). Only COLREG rule engagement, give-way/stand-on
    commitments (VO) or active encounters (Fan-MPC) count as dynamic.
    """
    if algorithm == "vo":
        return bool(
            details.get("active_rules") or details.get("give_way_commitment_active") or details.get("stand_on_hold_active")
        )
    if algorithm == "potocnik_colreg_fan_mpc":
        return bool(details.get("active_encounters"))
    raise OriginalGncError(f"No held-intent contract for {algorithm}")


def deviation_mode_policy(algorithm: str, details: dict) -> Callable[[int], list[str]]:
    """Tagging policy for deviation waypoints of one splice generation.

    Dynamic encounter generations keep the historic all-"avoidance" tagging.
    Static-hazard-only deviations tag only the entry leg: coordinate_transform's
    relaxed update tier needs one code-6 waypoint anywhere in the route
    (coordinate_transform_node.cpp navigation_mode_code==6), the whole-route
    turn-arc smoothing bypass keys off the same predicate, and the manager's
    non-emergency tier (behavior_mode "avoidance", active_route_manager_node.cpp
    873-875) is unaffected - while the leg-scoped 3.2 m/s cap then applies only
    at the deviation entry instead of the whole deviation stretch.
    """
    if dynamic_encounter_active(algorithm, details):
        return lambda count: [AVOIDANCE_MODE] * count
    return lambda count: [AVOIDANCE_MODE] + ["cruise"] * (count - 1) if count else []


def classify_rejection(feedback: dict) -> dict:
    """Split frozen rejections into bridge-addressable geometry vs dynamic contract causes."""
    reason = str(feedback.get("reason", ""))
    topic = feedback.get("topic", "")
    if reason in _DYNAMIC_REASONS:
        classification = "DYNAMIC"
    elif topic == "/route_planning/route_plan_status" or reason.startswith(_ADDRESSABLE_PREFIXES):
        classification = "ADDRESSABLE"
    else:
        classification = "DYNAMIC"
    return {"class": classification, "reason": reason, "topic": topic}


def _intent_deviation_m(points: np.ndarray, intent: np.ndarray, start: int, length: int) -> float:
    """Max distance between submitted deviation waypoints and the planner intent path."""
    if length < 1 or intent.size == 0:
        return 0.0
    submitted = points[:, start : start + length]
    if submitted.shape[1] == intent.shape[1]:
        return float(np.max(np.linalg.norm(submitted - intent, axis=0)))
    return float(max(min(np.linalg.norm(intent - point[:, None], axis=0)) for point in submitted.T))


def _manager_min_leg_m(latitudes: list, longitudes: list) -> float:
    """Mirror active_route_manager's leg metric (equirectangular, route-origin)."""
    if len(latitudes) < 2:
        return math.inf
    lat0, lon0 = float(latitudes[0]), float(longitudes[0])
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = meters_per_deg_lat * math.cos(math.radians(lat0))
    norths = [(float(latitude) - lat0) * meters_per_deg_lat for latitude in latitudes]
    easts = [(float(longitude) - lon0) * meters_per_deg_lon for longitude in longitudes]
    return min(
        math.hypot(norths[index + 1] - norths[index], easts[index + 1] - easts[index])
        for index in range(len(norths) - 1)
    )


class ReferenceMirror:
    """Adapter-side mirror of coordinate_transform's last accepted feedback path.

    The frozen node rotates ``last_feedback_path_`` on every accepted RoutePlan
    (coordinate_transform_node.cpp ~977-981) including the manager's
    internal_return_to_route publications, and ignores duplicates and
    rejections. Rejections and IGNORED_DUPLICATE never rotate the reference.

    Two invariants beyond verbatim rotation:

    - The splice reference (``path``) merges sub-floor legs: the manager's
      internal return routes open with a 1.5-5.5 m head leg, and a splice that
      inherits it is rejected segment_too_short forever (vo-OT-E0 t=273). The
      verbatim geometry stays in ``frozen_points`` for the frozen
      first-changed admission math, which coordinate_transform evaluates
      against the unmerged path it actually holds.
    - Speeds of bridge-submitted plans are kept as submitted: the manager's
      apply_speed_degradation clamps the published speed_limit_mps (turn
      radius, yaw rate), and absorbing the clamp ratcheted route speeds down
      to 0.59 m/s across generations. Degradation is execution-time only.
    """

    def __init__(self, ship: Any, nominal_only: bool = False):
        self.ship = ship
        self.path: ReferencePath | None = None
        self.frozen_points: np.ndarray | None = None
        self.route_type: str | None = None
        self.route_id: str | None = None
        self._nominal_only = nominal_only
        self._cursor = 0
        self._pending: dict[str, dict] = {}

    def refresh(self) -> None:
        events = self.ship._events
        for event in events[self._cursor :]:
            if event.get("event") != "publish":
                continue
            fields = (event.get("message") or {}).get("fields") or {}
            topic = event.get("topic")
            if topic == "/gnc/active_route":
                if fields.get("route_id"):
                    self._pending[fields["route_id"]] = fields
            elif topic == "/route_planning/route_plan_status" and fields.get("status") in {
                "ACCEPTED",
                "ACCEPTED_WITH_WARNINGS",
            }:
                route = self._pending.get(fields.get("route_id"))
                if route is not None:
                    self._absorb(route)
        self._cursor = len(events)

    def _absorb(self, route: dict) -> None:
        if self._nominal_only and route.get("route_type") != "nominal":
            return
        latitudes = list(route.get("latitude") or [])
        longitudes = list(route.get("longitude") or [])
        if len(latitudes) < 2 or len(latitudes) != len(longitudes):
            return
        points = self.ship.frame.northeast(latitudes, longitudes)
        speeds = self._reference_speeds(route, len(latitudes))
        modes = [str(value) for value in (route.get("navigation_mode") or [])]
        speeds += [0.0] * (len(latitudes) - len(speeds))
        modes += ["cruise"] * (len(latitudes) - len(modes))
        merged, keep = merge_short_segments(points, min_segment_m=SEGMENT_FLOOR_M)
        self.frozen_points = points
        self.path = ReferencePath(
            points=merged,
            speeds=[speeds[index] for index in keep],
            modes=[modes[index] for index in keep],
            latitudes=[latitudes[index] for index in keep],
            longitudes=[longitudes[index] for index in keep],
        )
        self.route_type = route.get("route_type")
        self.route_id = route.get("route_id")

    def _reference_speeds(self, route: dict, count: int) -> list[float]:
        """Published limits, except bridge-submitted plans keep their own speeds."""
        plan_id = route.get("route_id")
        for row in reversed(getattr(self.ship, "_requested_plans", []) or []):
            message = row.get("message") or {}
            if row.get("kind") == "avoidance" and message.get("plan_id") == plan_id:
                submitted = [float(value) for value in (message.get("command_speed_mps") or [])]
                if len(submitted) == count:
                    return submitted
                break
        return [float(value) for value in (route.get("speed_limit_mps") or [])]


class OriginalPlanBridge:
    """Translate accepted planner authority into admitted original GNC routes."""

    def __init__(self, ship: Any, dt_s: float):
        self.ship = ship
        self.dt_s = dt_s
        self._mid = ProductRouteBridge(ship._legacy, dt_s)
        self._mirror = ReferenceMirror(ship)
        self._nominal = ReferenceMirror(ship, nominal_only=True)
        self._heading = None
        self._speed = None
        self._geometry = None
        self._line_diagnostics: dict | None = None
        self._candidate: dict | None = None
        self._candidate_generation = 0
        self._algorithm = None
        self._intent_generation = 0
        self._lateral_blend = 1.0
        self._last_solve_time = None
        self._last_submission = None
        self._last_submission_time = None
        self._mid_plan_id = None
        self._mid_revision = None
        self.last_outcome = None
        self.admission_metrics = {
            "submitted": 0,
            "coordinate_accepted": 0,
            "accepted": 0,
            "degraded": 0,
            "rejected": 0,
            "rejected_addressable": 0,
            "rejected_dynamic": 0,
            "ignored_duplicate": 0,
            "holds": 0,
        }

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
            "require_exact_heading": False,
            "require_exact_speed": False,
            "allow_degraded_execution": True,
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
        feedback = []
        for event in self.ship._events[before:]:
            if event.get("event") == "publish" and event.get("topic") in {
                "/gnc/route_execution_status",
                "/route_planning/route_plan_status",
            }:
                item = copy.deepcopy(event["message"]["fields"])
                item["topic"] = event["topic"]
                feedback.append(item)
        rejected = any(f.get("rejected") is True or f.get("accepted") is False for f in feedback)
        degraded = any(f.get("degraded") is True for f in feedback)
        ignored = any(f.get("status") == "IGNORED_DUPLICATE" for f in feedback)
        coordinate_accepted = any(
            f.get("topic") == "/route_planning/route_plan_status" and f.get("accepted") is True for f in feedback
        )
        classifications = [
            classify_rejection(f) for f in feedback if f.get("rejected") is True or f.get("accepted") is False
        ]
        if rejected:
            outcome = f"REJECTED_{classifications[0]['class']}" if classifications else "REJECTED"
        elif degraded:
            outcome = "EXECUTING_WITH_LIMIT"
        elif feedback:
            outcome = "ADMITTED_DUPLICATE" if ignored else "ADMITTED"
        else:
            outcome = "NO_FEEDBACK"
        metrics = self.admission_metrics
        metrics["submitted"] += 1
        metrics["rejected"] += int(rejected)
        metrics["degraded"] += int(degraded and not rejected)
        metrics["ignored_duplicate"] += int(ignored)
        metrics["accepted"] += int(feedback and not rejected)
        metrics["coordinate_accepted"] += int(coordinate_accepted)
        metrics["rejected_addressable"] += sum(c["class"] == "ADDRESSABLE" for c in classifications)
        metrics["rejected_dynamic"] += sum(c["class"] == "DYNAMIC" for c in classifications)
        self.last_outcome = {
            "plan_id": request["plan_id"],
            "time_ns": self.ship.stack.time_ns,
            "accepted": bool(feedback) and not rejected and not degraded,
            "rejected": rejected,
            "degraded": degraded,
            "outcome": outcome,
            "classification": classifications,
            "metrics": copy.deepcopy(metrics),
            "feedback": feedback,
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
        self._speed = None
        self._geometry = None
        self._line_diagnostics = None
        self._candidate = None
        self._candidate_generation = 0
        self._lateral_blend = 1.0
        self._last_submission = None
        self._last_submission_time = None

    def _record_hold(self, reason: str, detail: dict | None = None) -> None:
        """Telemeter every intent the bridge cannot admit; silent drops are forbidden.

        vo-OT-E0 after t=273 dropped every VO intent without a trace while the
        ship ran an unadmitted route into a closing target until the planner
        went infeasible.
        """
        metrics = self.admission_metrics
        metrics["holds"] = metrics.get("holds", 0) + 1
        reasons = metrics.setdefault("hold_reasons", {})
        reasons[reason] = reasons.get(reason, 0) + 1
        event = {
            "sequence": len(self.ship._events),
            "event": "bridge_hold",
            "time_ns": self.ship.stack.time_ns,
            "reason": reason,
        }
        if detail:
            event.update(copy.deepcopy(detail))
        self.ship._events.append(event)

    def _reference(self) -> ReferencePath:
        self._mirror.refresh()
        if self._mirror.path is None:
            raise OriginalGncError("No accepted reference route is available for the avoidance splice")
        return self._mirror.path

    def _nominal_reference(self) -> ReferencePath:
        """The mission route reference; deviation rejoins land on it, never on a splice."""
        self._nominal.refresh()
        if self._nominal.path is not None:
            return self._nominal.path
        return self._reference()

    def _mirror_holds_own_route(self) -> bool:
        """True when the last rotated reference is one of this bridge's own plans.

        Our own accepted submissions rotate the frozen reference by definition;
        that is not an external rotation, so the latched splice stays valid.
        Internal returns, nominal updates and any third-party acceptance do
        invalidate it.
        """
        own = {
            row.get("message", {}).get("plan_id")
            for row in getattr(self.ship, "_requested_plans", [])
            if row.get("kind") == "avoidance"
        }
        return self._mirror.route_id in own

    def _intent_deviation(
        self, algorithm: str, heading: float, speed: float, reference: ReferencePath
    ) -> tuple[np.ndarray, bool, bool]:
        """Hold the same physical intent line while course and authority are held.

        A held intent is only new when the course moved beyond
        INTENT_COURSE_TOLERANCE_RAD (wrap-aware) or the authority changed;
        sampling noise no longer spawns a generation. Commanded speed changes
        ride the latched splice (they never move the line) and are reported so
        the submitted speeds can be refreshed in place.
        """
        course_moved = (
            self._heading is None or abs(math.remainder(heading - self._heading, 2 * math.pi)) > INTENT_COURSE_TOLERANCE_RAD
        )
        speed_moved = self._speed is None or abs(speed - self._speed) > INTENT_SPEED_TOLERANCE_MPS
        new_generation = course_moved or self._algorithm != algorithm or self._geometry is None
        if new_generation:
            self._intent_generation += 1
            self._lateral_blend = 1.0
            deviation, diagnostics = intent_line_deviation(self.ship.state[:2], heading, reference)
            self._geometry = deviation
            self._line_diagnostics = diagnostics
        self._heading, self._algorithm, self._speed = heading, algorithm, speed
        return self._geometry, new_generation, speed_moved

    def _split_lateral_offset(self, deviation: np.ndarray, reference: ReferencePath, fresh: bool) -> np.ndarray:
        """Split lateral offsets beyond the frozen 500 m gate across successive updates."""
        lateral = max_lateral_delta(deviation, reference.points)
        if not math.isfinite(lateral) or lateral <= LATERAL_ENVELOPE_M:
            self._lateral_blend = 1.0
            return deviation
        if fresh or self._lateral_blend >= 1.0:
            self._lateral_blend = min(1.0, 0.9 * LATERAL_ENVELOPE_M / lateral)
        else:
            self._lateral_blend = min(1.0, self._lateral_blend + 0.5)
        return blend_deviation_toward_reference(deviation, reference.points, self._lateral_blend)

    def _mid_deviation(self, path: np.ndarray, reference: ReferencePath) -> tuple[np.ndarray, list[int]] | None:
        """Deviation columns from the first waypoint at the splice margin.

        Returns None when no accepted-plan waypoint reaches FIRST_CHANGE_MARGIN_M
        ahead of the ship along the reference (give-way standby or standoff
        geometry). The frozen manager answers such an update with a
        first-changed-waypoint rejection and keeps executing the active route,
        so the bridge holds the active route for this tick instead of raising;
        manager-owned expiry still governs the admitted route's lifecycle.
        """
        ref = reference.points
        ship_along = along_track_progress(self.ship.state[:2], ref)
        ahead = [along_track_progress(path[:, index], ref) - ship_along for index in range(path.shape[1])]
        first = next((index for index, value in enumerate(ahead) if value >= FIRST_CHANGE_MARGIN_M), None)
        if first is None:
            return None
        filtered = path[:, first:]
        merged, keep = merge_short_segments(filtered)
        return merged, [first + index for index in keep]

    # Keep source contract branches together for audit against the frozen implementation.
    def submit(self, t: float) -> None:  # noqa: PLR0912, PLR0915
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
        reference = self._reference()
        candidate = None
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
            # Widened from the VO internal 1 s window so each held intent keeps one
            # live admission window at the manager; never extended past the last
            # verified solve (design P1.5).
            valid_until_s = self._last_solve_time + max(period, _MIN_VALIDITY_S)
            nominal = self._nominal_reference()
            geometry, fresh_geometry, speed_moved = self._intent_deviation(algorithm, heading, speed, reference)
            deviation_speeds = np.full(geometry.shape[1], speed)
            # Hold the admitted splice for a held intent: rebuilding it against
            # the mirror (which this very route rotated) is not idempotent.
            # A mirror that no longer matches the held candidate means something
            # else rotated the accepted route (manager validity-expiry internal
            # return, nominal update), so the splice is rebuilt against it.
            rotated = (
                self._candidate is not None
                and self._mirror.path.latitudes != self._candidate["reference_latitudes"]
                and not self._mirror_holds_own_route()
            )
            policy = deviation_mode_policy(algorithm, details)
            candidate, hold = self._held_candidate(
                reference, nominal, geometry, deviation_speeds, speed, fresh_geometry, rotated, speed_moved, policy
            )
            if candidate is None:
                self._record_hold(
                    hold or "no_candidate",
                    {
                        "algorithm": algorithm,
                        "generation": self._intent_generation,
                        "line": copy.deepcopy(self._line_diagnostics),
                    },
                )
                return
            plan_id = f"{algorithm}-held-intent-{self._candidate_generation}"
            identity = {
                "algorithm": algorithm,
                "solve_id": planner.get("solve_id"),
                "authority": "held_course_speed_intent",
                "geometry": "reference_splice_intent_line",
                "length_m": float(np.linalg.norm(geometry[:, -1] - geometry[:, 0])),
                "planner_speed_semantics": "SOG",
                "source_speed_semantics": "original_route_speed_limit",
                "source_heading_field_semantics": "omitted_route_geometry_is_authority",
                "splice": {
                    "generation": self._candidate_generation,
                    "line": copy.deepcopy(self._line_diagnostics),
                    "lateral_blend_fraction": self._lateral_blend,
                },
            }
        elif algorithm == "mid_mpc_ipopt":
            decision = self._mid.current_route(tick=round(t / self.dt_s), planner_data=data)
            if decision.failure is not None or decision.route is None:
                raise OriginalGncError(f"Mid-MPC accepted route unavailable: {decision.failure}")
            route = decision.route
            receipt = details["accepted_plan_receipt"]
            # CONTINUITY_PRESERVED rolls keep the plan identity; a revision change
            # (reference discontinuity) starts a new generation.
            fresh_geometry = self._mid_plan_id is None or route.revision != self._mid_revision
            if fresh_geometry:
                self._mid_plan_id = "mid-mpc-" + receipt["receipt_hash"][:24]
                self._mid_revision = route.revision
                self._lateral_blend = 1.0
            plan_id = self._mid_plan_id
            raw = np.asarray(route.waypoints_ne_m, dtype=float)
            deviation = self._mid_deviation(raw, reference)
            if deviation is None:
                self._record_hold("short_of_splice_margin", {"algorithm": algorithm, "continuity_revision": route.revision})
                return  # accepted plan never reaches the splice margin: hold the active route this tick
            geometry, source_indices = deviation
            speeds = np.asarray(route.speed_mps, dtype=float)[source_indices]
            geometry = self._split_lateral_offset(geometry, reference, fresh_geometry)
            deviation_speeds = [float(value) for value in speeds]
            # Mid routes roll continuously inside one continuity revision: rebuild
            # every tick, never latch (the held-intent latch is VO/Fan-only).
            candidate = self._build_candidate(reference, reference, geometry, deviation_speeds, None)
            if not candidate["gate_clean"]:
                self._record_hold("unadmittable_splice", {"algorithm": algorithm, "continuity_revision": route.revision})
                return  # unadmittable splice: hold the current route this tick
            # Accepted prediction geometry is a route. It is not a sequence of
            # body-heading commands, so retain only its geometric authority.
            valid_until_s = route.valid_until_tick * self.dt_s
            identity = {
                "algorithm": algorithm,
                "authority": "accepted_mid_mpc_receipt",
                "receipt_hash": receipt["receipt_hash"],
                # colav.mid_mpc.receipt@1 calls the authority cycle "sequence";
                # the canonical accepted-plan-receipt schema calls it
                # "accepted_sequence" (same tolerant read as threat management).
                "accepted_sequence": receipt.get("accepted_sequence", receipt.get("sequence")),
                "continuity_revision": route.revision,
                "planner_speed_semantics": "accepted_command_speed",
                "source_speed_semantics": "original_route_speed_limit",
                "splice": {"lateral_blend_fraction": self._lateral_blend},
            }
        else:
            raise OriginalGncError(f"Planner not supported by the original GNC bridge: {algorithm}")
        if valid_until_s <= t:
            raise OriginalGncError("Accepted planner authority has expired; it cannot be extended by the bridge")
        signature_payload = (
            np.ascontiguousarray(candidate["points"], dtype=float).tobytes()
            + np.asarray(candidate["speeds"], dtype=float).tobytes()
            + ",".join(candidate["modes"]).encode()
        )
        signature = (plan_id, hashlib.sha256(signature_payload).hexdigest(), valid_until_s)
        if signature == self._last_submission and (
            self._last_submission_time is None or t - self._last_submission_time < _RESUBMIT_INTERVAL_S
        ):
            return
        deadline_ns = self.ship.stack.epoch_ns + round((valid_until_s - self.ship._planner_time_origin) * 1e9)
        request = self._base(algorithm, plan_id, deadline_ns)
        request["latitude"] = candidate["latitudes"]
        request["longitude"] = candidate["longitudes"]
        request["command_speed_mps"] = [float(value) for value in candidate["speeds"]]
        # Route geometry is the sole heading authority: the frozen 20 deg
        # per-segment heading gate cannot hold across a mixed reference splice.
        request["command_heading_deg"] = []
        request["require_exact_heading"] = False
        request["navigation_mode"] = list(candidate["modes"])
        identity["splice"] = {
            **identity.get("splice", {}),
            "first_change_ahead_m": candidate["first_change_ahead_m"],
            "first_change_ahead_frozen_m": candidate.get("first_change_ahead_frozen_m"),
            "max_lateral_delta_m": candidate["max_lateral_delta_m"],
            "min_interior_turn_deg": candidate["min_interior_turn_deg"],
            "min_new_segment_m": candidate["min_new_segment_m"],
            "prefix_length": candidate["prefix_length"],
            "rejoin_index": candidate["rejoin_index"],
            "rejoin_reference": "nominal_mission",
            "intent_deviation_m": candidate["intent_deviation_m"],
        }
        self._deliver(request, identity)
        self._last_submission = signature
        self._last_submission_time = t

    def _held_candidate(
        self,
        reference: ReferencePath,
        nominal: ReferencePath,
        geometry: np.ndarray,
        deviation_speeds: np.ndarray,
        speed: float | None,
        fresh_geometry: bool,
        rotated: bool,
        speed_moved: bool,
        mode_policy: Callable[[int], list[str]] | None,
    ) -> tuple[dict | None, str | None]:
        """Rebuild the latched splice only when the rebuild stays admittable.

        A splice the frozen chain would reject (reverse segment, short leg,
        first changed waypoint inside the 150 m gate) must never be published
        or latched: rejections do not rotate the mirror, so resubmitting
        rejected geometry only storms the gate. Hold the previous route this
        tick instead (and telemeter the hold); the next solve re-evaluates, and
        manager expiry still owns the avoidance lifecycle. Commanded speed
        changes ride the latched splice without moving its geometry.
        """
        hold = None
        if fresh_geometry or rotated or self._candidate is None or self._lateral_blend < 1.0:
            built = self._build_candidate(reference, nominal, geometry, deviation_speeds, mode_policy)
            if built["gate_clean"]:
                self._candidate = built
                self._candidate_generation = self._intent_generation
            else:
                hold = "unadmittable_splice"
        elif speed_moved and self._candidate is not None and speed is not None:
            self._apply_deviation_speed(self._candidate, speed)
        return self._candidate, hold

    def _apply_deviation_speed(self, candidate: dict, speed: float) -> None:
        """Refresh the deviation legs' commanded speed in place; geometry is untouched."""
        start, stop = candidate.get("deviation_slice", (0, 0))
        candidate["speeds"][start:stop] = [speed] * (stop - start)

    def _build_candidate(
        self,
        reference: ReferencePath,
        nominal: ReferencePath,
        geometry: np.ndarray,
        deviation_speeds: list,
        mode_policy: Callable[[int], list[str]] | None,
    ) -> dict:
        """Splice the deviation into the reference and attach the route contract arrays."""
        candidate = build_avoidance_route(
            reference,
            self.ship.state[:2],
            geometry,
            deviation_speeds,
            rejoin_reference=nominal,
            deviation_mode_policy=mode_policy,
        )
        k = candidate["prefix_length"]
        j = candidate["rejoin_index"]
        tail_start = candidate["points"].shape[1] - (nominal.points.shape[1] - j)
        candidate["deviation_slice"] = (k, tail_start)
        candidate["intent_deviation_m"] = _intent_deviation_m(candidate["points"], geometry, k, tail_start - k)
        candidate["latitudes"], candidate["longitudes"] = self._compose_coordinates(reference, nominal, candidate)
        candidate["reference_latitudes"] = list(reference.latitudes) if reference.latitudes is not None else None
        # The frozen node compares submissions against its own unmerged
        # last_feedback_path_; a re-anchored (sanitized) reference shifts the
        # candidate indices, so verify the first changed waypoint on the exact
        # frozen geometry before admitting.
        if self._mirror.frozen_points is not None:
            ahead = first_change_distance_ahead(candidate["points"], self._mirror.frozen_points, self.ship.state[:2])
            candidate["first_change_ahead_frozen_m"] = ahead
            if math.isfinite(ahead) and ahead < FIRST_CHANGE_GATE_M:
                candidate["gate_clean"] = False
        # The manager measures legs with its own equirectangular projection over
        # the route's first waypoint (111320 m/deg, cos(lat0) easting), and
        # behavior_mode "avoidance" is its NON-emergency tier (30 m gate), so a
        # 30.0 m geodesic leg can measure 29.97 there and be rejected. Re-check
        # the exact frozen metric on the coordinates actually submitted.
        candidate["gate_clean"] = bool(
            candidate["gate_clean"]
            and _manager_min_leg_m(candidate["latitudes"], candidate["longitudes"]) >= MIN_SEGMENT_M
        )
        return candidate

    def _compose_coordinates(self, reference: ReferencePath, nominal: ReferencePath, candidate: dict) -> tuple[list, list]:
        """Prefix verbatim from the accepted reference, tail from the mission route."""
        k = candidate["prefix_length"]
        j = candidate["rejoin_index"]
        tail_start = candidate["points"].shape[1] - (nominal.points.shape[1] - j)
        deviation = candidate["points"][:, k:tail_start]
        latitudes, longitudes = self.ship.frame.geographic(deviation)
        if reference.latitudes is None or nominal.latitudes is None:
            all_latitudes, all_longitudes = self.ship.frame.geographic(candidate["points"])
            return all_latitudes, all_longitudes
        return (
            [*reference.latitudes[:k], *latitudes, *nominal.latitudes[j:]],
            [*reference.longitudes[:k], *longitudes, *nominal.longitudes[j:]],
        )
