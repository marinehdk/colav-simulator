"""COLREG-aware executable extension of the Potočnik fan MPC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from shapely import distance as geometry_distance
from shapely import intersects as geometry_intersects
from shapely import linestrings
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    CustomMPCAdapter,
    ExecutionProfile,
    FactoryContext,
    MPCSolution,
    PlannerInput,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, FailureSource, PlanStatus
from colav_simulator.evaluation.encounter import classify_geometry
from colav_simulator.integrations.potocnik_mpc import (
    PAPER_COLREG_ZONE_M,
    UPSTREAM_COMMIT,
    PotocnikMPCParams,
)

__version__ = f"colreg-fan.1+{UPSTREAM_COMMIT[:12]}"
_GIVE_WAY: Final = frozenset({"head_on", "crossing_give_way", "overtaking"})
_STAND_ON: Final = frozenset({"crossing_stand_on", "overtaken"})


@dataclass(frozen=True)
class PotocnikColregParams(PotocnikMPCParams):
    """Execution, safety, and controller-side COLREG policy parameters."""

    minimum_colreg_turn_deg: float = 5.0
    course_response_time_constant_s: float = 8.0
    speed_response_time_constant_s: float = 10.0
    max_yaw_rate_deg_s: float = 3.0
    max_speed_rate_mps2: float = 0.3
    speed_scales: tuple[float, ...] = (1.0, 0.75, 0.5, 0.25)
    static_clearance_m: float = 20.0
    static_influence_distance_m: float = 200.0
    static_clearance_weight: float = 1.0
    route_lookahead_m: float = 200.0
    trajectory_continuity_weight: float = 2.0

    def __post_init__(self) -> None:
        """Validate the enhanced controller profile."""
        super().__post_init__()
        positive = (
            self.minimum_colreg_turn_deg,
            self.course_response_time_constant_s,
            self.speed_response_time_constant_s,
            self.max_yaw_rate_deg_s,
            self.max_speed_rate_mps2,
            self.static_clearance_m,
            self.static_influence_distance_m,
            self.static_clearance_weight,
            self.route_lookahead_m,
            self.trajectory_continuity_weight,
        )
        if not np.isfinite(positive).all() or min(positive) <= 0.0:
            raise ValueError("COLREG response and static-clearance parameters must be positive")
        if (
            not self.speed_scales
            or not np.isfinite(self.speed_scales).all()
            or min(self.speed_scales) <= 0.0
            or max(self.speed_scales) > 1.0
            or tuple(sorted(self.speed_scales, reverse=True)) != self.speed_scales
        ):
            raise ValueError("speed_scales must be a descending tuple in (0, 1]")
        if 1.0 not in self.speed_scales:
            raise ValueError("speed_scales must include 1.0")


@dataclass(frozen=True)
class _Policy:
    encounters: tuple[dict, ...]
    give_way_targets: tuple[int, ...]
    crossing_give_way_targets: tuple[int, ...]
    stand_on_targets: tuple[int, ...]
    starboard_required: bool


@dataclass(frozen=True)
class _Selection:
    index: int
    score: float
    route_score: float
    continuity_score: float
    trajectory_continuity_score: float
    clearance_score: float
    static_clearance_score: float
    reversal_penalty: float
    relaxations: tuple[str, ...]


class PotocnikColregFanMPC:
    """Fan rollout with executable controls, continuous safety, and COLREG policy."""

    def __init__(self, params: PotocnikColregParams) -> None:
        self.params = params
        self.solve_count = 0
        self._previous_command_course: float | None = None
        self._previous_trajectory: np.ndarray | None = None
        self._previous_solve_time_s: float | None = None
        self._maneuver_sign = 0
        self._maneuver_course: float | None = None
        self._maneuver_phase = "TRACK"
        self._encounter_state: dict[int, str] = {}
        self._clear_solves = 0
        self._stand_on_course: float | None = None
        self._hazard_cache_key: tuple[int, float] | None = None
        self._hazard_geometry: BaseGeometry | None = None
        self._heading_increments = np.linspace(
            -np.deg2rad(params.max_heading_increment_deg),
            np.deg2rad(params.max_heading_increment_deg),
            params.candidate_count,
        )

    def reset(self) -> None:
        self.solve_count = 0
        self._previous_command_course = None
        self._previous_trajectory = None
        self._previous_solve_time_s = None
        self._maneuver_sign = 0
        self._maneuver_course = None
        self._maneuver_phase = "TRACK"
        self._encounter_state.clear()
        self._clear_solves = 0
        self._stand_on_course = None
        self._hazard_cache_key = None
        self._hazard_geometry = None

    def solve(self, planner_input: PlannerInput) -> MPCSolution:  # noqa: PLR0915
        self.solve_count += 1
        ownship = planner_input.ownship_state
        goal_ne, target_course, cross_track_error_m, route_target_index = _route_guidance(
            ownship[:2],
            planner_input.waypoints_enu_m,
            self.params.route_lookahead_m,
        )
        route_speed_mps = float(planner_input.speed_plan_mps[min(route_target_index, planner_input.speed_plan_mps.size - 1)])
        policy = self._encounter_policy(planner_input)
        self._update_maneuver_phase(policy, cross_track_error_m, ownship[2], target_course)

        command_course_center = float(ownship[2]) if self._previous_command_course is None else self._previous_command_course
        speed_scales = np.repeat(
            np.asarray(self.params.speed_scales),
            self.params.candidate_count,
        )
        candidates, controls = self._generate_candidate_bundle(
            ownship,
            route_speed_mps * np.asarray(self.params.speed_scales),
            planner_input.dt_sim_s,
            command_course_center=command_course_center,
        )
        increments = np.tile(self._heading_increments, len(self.params.speed_scales))

        target_predictions = self._target_predictions(planner_input)
        minimum_clearance, dynamic_feasible, footprint_feasible = self._dynamic_feasibility(
            candidates,
            target_predictions,
            planner_input,
        )
        static_feasible, minimum_static_clearance, static_active = self._static_feasibility(
            candidates,
            planner_input,
        )
        nominal_index = self.params.candidate_count // 2
        nominal_feasible = bool(dynamic_feasible[nominal_index] and static_feasible[nominal_index])
        if policy.stand_on_targets and not policy.give_way_targets and self._stand_on_course is not None:
            reference_error = np.abs(_wrap_angle(controls[:, 2, 0] - self._stand_on_course))
            reference_candidates = (
                dynamic_feasible
                & static_feasible
                & np.isclose(speed_scales, 1.0)
                & (reference_error <= self._heading_grid_tolerance())
            )
            nominal_feasible = bool(np.any(reference_candidates))
        feasible = dynamic_feasible & static_feasible
        feasible_indices = np.flatnonzero(feasible)
        dynamic_buffer_recovery = False
        if feasible_indices.size == 0:
            feasible = footprint_feasible & static_feasible
            feasible_indices = np.flatnonzero(feasible)
            dynamic_buffer_recovery = bool(feasible_indices.size)
            if feasible_indices.size == 0:
                raise ColavExecutionError(
                    PlanStatus.INFEASIBLE,
                    "Potočnik COLREG fan MPC found no continuously footprint-safe trajectory",
                    source=FailureSource.ALGORITHM,
                    details={
                        "candidate_count": int(candidates.shape[0]),
                        "collision_distance_m": self.params.collision_distance_m,
                        "static_constraint_active": static_active,
                    },
                )
        pass_astern = self._pass_astern_candidates(
            candidates,
            target_predictions,
            policy.crossing_give_way_targets,
        )
        selection = self._select_candidate(
            controls=controls,
            speed_scales=speed_scales,
            feasible_indices=feasible_indices,
            minimum_clearance=minimum_clearance,
            minimum_static_clearance=minimum_static_clearance,
            pass_astern=pass_astern,
            policy=policy,
            ownship_course=float(ownship[2]),
            target_course=target_course,
            nominal_feasible=nominal_feasible,
            candidates=candidates,
            sim_time_s=planner_input.sim_time_s,
            route_speed_mps=route_speed_mps,
        )
        selected_index = selection.index
        selected = candidates[selected_index]
        selected_controls = controls[selected_index]
        command = selected_controls[:, 0].copy()
        selected_increment = float(increments[selected_index])
        self._record_policy_state(policy, selected_increment, float(command[2]))
        self._previous_command_course = float(command[2])
        self._previous_trajectory = selected.copy()
        self._previous_solve_time_s = planner_input.sim_time_s

        selected_clearance = float(minimum_clearance[selected_index])
        selected_static_clearance = float(minimum_static_clearance[selected_index])
        selected_scale = float(speed_scales[selected_index])
        encounters = [item["encounter"] for item in policy.encounters if item["encounter"] != "clear"]
        policy_relaxations = list(selection.relaxations)
        if dynamic_buffer_recovery:
            policy_relaxations.insert(0, "dynamic_safety_buffer_recovery")
        constraints = {
            "dynamic_collision": {
                "clearance_semantics": "continuous_center_distance_with_footprint_radii",
                "required_hull_clearance_m": self.params.collision_distance_m,
                "minimum_predicted_center_clearance_m": (selected_clearance if np.isfinite(selected_clearance) else None),
            },
            "static_grounding": {
                "active": static_active,
                "required_hull_clearance_m": self.params.static_clearance_m,
                "minimum_predicted_hull_clearance_m": (
                    selected_static_clearance if np.isfinite(selected_static_clearance) else None
                ),
            },
            "colreg_policy": {
                "encounters": encounters,
                "give_way_targets": list(policy.give_way_targets),
                "stand_on_targets": list(policy.stand_on_targets),
                "starboard_required": policy.starboard_required,
                "pass_astern_required": bool(policy.crossing_give_way_targets),
                "selected_passes_astern": bool(pass_astern[selected_index]),
                "relaxations": policy_relaxations,
                "semantics": "controller_side_geometry_policy_not_legal_compliance_proof",
            },
            "heading_increment": {
                "limit_rad": float(np.deg2rad(self.params.max_heading_increment_deg)),
                "minimum_colreg_action_rad": float(np.deg2rad(self.params.minimum_colreg_turn_deg)),
                "selected_rad": selected_increment,
                "maximum_command_change_rad": float(np.deg2rad(self.params.max_command_change_deg)),
            },
            "planning_zone": {
                "distance_m": self.params.colreg_zone_distance_m,
                "semantics": "paper_colreg_zone_reference",
            },
        }
        details = {
            "paper": "Potočnik 2025 JMSE 13(7):1246",
            "upstream_commit": UPSTREAM_COMMIT,
            "formulation": "colreg_aware_executable_fan_mpc",
            "paper_reference_algorithm_id": "potocnik_simplified_mpc",
            "candidate_count": int(candidates.shape[0]),
            "base_heading_candidate_count": self.params.candidate_count,
            "candidate_heading_increments_rad": increments.tolist(),
            "candidate_speed_scales": speed_scales.tolist(),
            "candidate_feasible": feasible.tolist(),
            "candidate_dynamic_feasible": dynamic_feasible.tolist(),
            "candidate_footprint_feasible": footprint_feasible.tolist(),
            "candidate_static_feasible": static_feasible.tolist(),
            "candidate_minimum_clearance_m": _finite_list(minimum_clearance),
            "candidate_minimum_static_clearance_m": _finite_list(minimum_static_clearance),
            "selected_candidate_index": selected_index,
            "selected_heading_increment_rad": selected_increment,
            "selected_speed_scale": selected_scale,
            "selection_score": selection.score,
            "route_score": selection.route_score,
            "continuity_score": selection.continuity_score,
            "trajectory_continuity_score": selection.trajectory_continuity_score,
            "clearance_score": selection.clearance_score,
            "static_clearance_score": selection.static_clearance_score,
            "reversal_penalty": selection.reversal_penalty,
            "goal_ne_m": goal_ne.tolist(),
            "prediction_steps": self.params.prediction_steps,
            "prediction_step_s": self.params.horizon_dt_s,
            "solve_period_s": self.params.solve_period_s,
            "solve_count": self.solve_count,
            "nominal_candidate_feasible": nominal_feasible,
            "active_encounters": encounters,
            "encounter_records": list(policy.encounters),
            "maneuver_turn_sign": self._maneuver_sign,
            "maneuver_phase": self._maneuver_phase,
            "maneuver_course_rad": self._maneuver_course,
            "cross_track_error_m": cross_track_error_m,
            "control_trajectory_semantics": "held_course_speed_reference",
            "continuous_collision_check": True,
            "static_constraint_active": static_active,
            "dynamic_safety_buffer_recovery": dynamic_buffer_recovery,
        }
        return MPCSolution(
            control_reference=command.reshape(9, 1),
            predicted_trajectory=selected,
            control_trajectory=selected_controls,
            horizon_dt_s=self.params.horizon_dt_s,
            objective=selection.score,
            iterations=int(candidates.shape[0]),
            feasible=True,
            constraints=constraints,
            target_predictions=tuple(target_predictions),
            algorithm_details=details,
        )

    def _generate_candidate_bundle(  # noqa: PLR0915
        self,
        ownship: np.ndarray,
        command_speed_mps: float | np.ndarray,
        dt_sim_s: float,
        *,
        command_course_center: float | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        horizon = self.params.prediction_steps + 1
        command_speeds = np.atleast_1d(np.asarray(command_speed_mps, dtype=float))
        count = self.params.candidate_count * command_speeds.size
        heading_increments = np.tile(self._heading_increments, command_speeds.size)
        desired_speeds = np.repeat(command_speeds, self.params.candidate_count)
        candidates = np.zeros((count, 9, horizon), dtype=float)
        controls = np.zeros_like(candidates)
        candidates[:, :6, 0] = ownship
        headings = np.full(count, float(ownship[2]))
        speeds = np.full(count, float(np.hypot(ownship[3], ownship[4])))
        north = np.full(count, float(ownship[0]))
        east = np.full(count, float(ownship[1]))
        if command_course_center is None:
            command_course_center = float(ownship[2])
        command_headings = _wrap_angle(command_course_center + heading_increments)
        increments = heading_increments.copy()
        controls[:, 2, 0] = command_headings
        controls[:, 3, 0] = desired_speeds
        for sample in range(1, horizon):
            if sample > 1:
                increments *= self.params.heading_increment_decay
                command_headings = _wrap_angle(command_headings + increments)
            controls[:, 2, sample] = command_headings
            controls[:, 3, sample] = desired_speeds

        integration_steps = max(1, int(np.ceil(self.params.horizon_dt_s / dt_sim_s)))
        integration_dt_s = self.params.horizon_dt_s / integration_steps
        yaw_limit = np.deg2rad(self.params.max_yaw_rate_deg_s) * integration_dt_s
        speed_limit = self.params.max_speed_rate_mps2 * integration_dt_s
        course_response = 1.0 - np.exp(-integration_dt_s / self.params.course_response_time_constant_s)
        speed_response = 1.0 - np.exp(-integration_dt_s / self.params.speed_response_time_constant_s)
        for step in range(1, horizon):
            yaw_rates = np.zeros(count)
            speed_rates = np.zeros(count)
            desired_course = controls[:, 2, step - 1]
            desired_speed = controls[:, 3, step - 1]
            for _ in range(integration_steps):
                heading_step = np.clip(
                    course_response * _wrap_angle(desired_course - headings),
                    -yaw_limit,
                    yaw_limit,
                )
                speed_step = np.clip(
                    speed_response * (desired_speed - speeds),
                    -speed_limit,
                    speed_limit,
                )
                midpoint_heading = _wrap_angle(headings + 0.5 * heading_step)
                midpoint_speed = np.maximum(0.0, speeds + 0.5 * speed_step)
                north += midpoint_speed * np.cos(midpoint_heading) * integration_dt_s
                east += midpoint_speed * np.sin(midpoint_heading) * integration_dt_s
                headings = _wrap_angle(headings + heading_step)
                speeds = np.maximum(0.0, speeds + speed_step)
                yaw_rates = heading_step / integration_dt_s
                speed_rates = speed_step / integration_dt_s
            candidates[:, 0, step] = north
            candidates[:, 1, step] = east
            candidates[:, 2, step] = headings
            candidates[:, 3, step] = speeds
            candidates[:, 5, step] = yaw_rates
            candidates[:, 6, step] = speed_rates * np.cos(headings)
            candidates[:, 7, step] = speed_rates * np.sin(headings)
            candidates[:, 8, step] = yaw_rates
        controls[:, 0:2, :] = candidates[:, 0:2, :]
        return candidates, controls

    def _encounter_policy(self, planner_input: PlannerInput) -> _Policy:  # noqa: PLR0912
        ownship = planner_input.ownship_state
        own_velocity = _own_velocity_ne(ownship)
        records = []
        give_way = []
        crossing_give_way = []
        stand_on = []
        seen_ids = set()
        for track in planner_input.tracks:
            seen_ids.add(track.target_id)
            relative = track.state_enu[:2] - ownship[:2]
            distance = float(np.linalg.norm(relative))
            detected, dcpa, tcpa, signed_tcpa, bearing = classify_geometry(
                ownship[:2],
                own_velocity,
                track.state_enu[:2],
                track.state_enu[2:4],
                planner_input.ownship_length_m,
                track.length_m,
            )
            previous = self._encounter_state.get(track.target_id, "clear")
            if detected != "clear":
                encounter = detected
            elif previous != "clear" and signed_tcpa > 0.0 and distance <= self.params.colreg_zone_distance_m:
                encounter = previous
            else:
                encounter = "clear"
            if encounter == "clear":
                self._encounter_state.pop(track.target_id, None)
            else:
                self._encounter_state[track.target_id] = encounter
            if encounter in _GIVE_WAY:
                give_way.append(track.target_id)
            if encounter == "crossing_give_way":
                crossing_give_way.append(track.target_id)
            if encounter in _STAND_ON:
                stand_on.append(track.target_id)
            records.append(
                {
                    "target_id": track.target_id,
                    "encounter": encounter,
                    "detected_geometry": detected,
                    "distance_m": distance,
                    "dcpa_m": dcpa,
                    "tcpa_s": tcpa,
                    "signed_tcpa_s": signed_tcpa,
                    "relative_bearing_deg": bearing,
                }
            )
        for target_id in set(self._encounter_state) - seen_ids:
            self._encounter_state.pop(target_id, None)
        active = {item["encounter"] for item in records}
        if stand_on:
            if self._stand_on_course is None:
                self._stand_on_course = float(ownship[2])
        elif self._maneuver_phase == "TRACK":
            self._stand_on_course = None
        return _Policy(
            encounters=tuple(records),
            give_way_targets=tuple(give_way),
            crossing_give_way_targets=tuple(crossing_give_way),
            stand_on_targets=tuple(stand_on),
            starboard_required=bool(active & {"head_on", "crossing_give_way", "overtaking"}),
        )

    def _dynamic_feasibility(
        self,
        candidates: np.ndarray,
        targets: list[dict],
        planner_input: PlannerInput,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        count = candidates.shape[0]
        if not targets:
            return (
                np.full(count, np.inf),
                np.ones(count, dtype=bool),
                np.ones(count, dtype=bool),
            )
        own_radius = 0.5 * float(np.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m))
        target_ne = np.stack([np.vstack((target["north_m"], target["east_m"])) for target in targets])
        clearance = _batched_continuous_minimum_distance(candidates[:, :2], target_ne)
        target_radii = np.asarray([0.5 * np.hypot(target["length_m"], target["width_m"]) for target in targets])
        required = self.params.collision_distance_m + own_radius + target_radii
        minimum = np.min(clearance, axis=0)
        feasible = np.all(clearance >= required[:, None], axis=0)
        footprint_feasible = np.all(
            clearance >= (own_radius + target_radii)[:, None],
            axis=0,
        )
        return minimum, feasible, footprint_feasible

    def _pass_astern_candidates(
        self,
        candidates: np.ndarray,
        targets: list[dict],
        target_ids: tuple[int, ...],
    ) -> np.ndarray:
        passes = np.ones(candidates.shape[0], dtype=bool)
        target_id_set = set(target_ids)
        for target in targets:
            if target["target_id"] not in target_id_set:
                continue
            velocity = np.asarray(target["velocity_ne_mps"], dtype=float)
            speed = float(np.linalg.norm(velocity))
            if speed <= 1e-6:
                continue
            target_ne = np.vstack((target["north_m"], target["east_m"]))
            closest_relative = _relative_position_at_continuous_cpa(candidates[:, :2], target_ne)
            passes &= (closest_relative @ (velocity / speed)) <= 0.0
        return passes

    def _static_feasibility(
        self,
        candidates: np.ndarray,
        planner_input: PlannerInput,
    ) -> tuple[np.ndarray, np.ndarray, bool]:
        count = candidates.shape[0]
        feasible = np.ones(count, dtype=bool)
        minimum = np.full(count, np.inf)
        if planner_input.enc is None:
            return feasible, minimum, False
        hazard = self._grounding_hazard(planner_input)
        if hazard is None or hazard.is_empty:
            return feasible, minimum, True
        radius = 0.5 * float(np.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m))
        east = candidates[:, 1, :]
        north = candidates[:, 0, :]
        margin = radius + self.params.static_clearance_m
        local_box = box(
            float(np.min(east)) - margin,
            float(np.min(north)) - margin,
            float(np.max(east)) + margin,
            float(np.max(north)) + margin,
        )
        local_hazard = hazard.intersection(local_box)
        if local_hazard.is_empty:
            return feasible, minimum, True
        exclusion = local_hazard.buffer(margin)
        centerlines = linestrings(np.stack((east, north), axis=-1))
        minimum = np.maximum(0.0, geometry_distance(centerlines, local_hazard) - radius)
        feasible = ~geometry_intersects(centerlines, exclusion)
        return feasible, minimum, True

    def _grounding_hazard(self, planner_input: PlannerInput) -> BaseGeometry | None:
        enc = planner_input.enc
        if enc is None:
            return None
        cache_key = (id(enc), planner_input.ownship_draft_m)
        if cache_key == self._hazard_cache_key:
            return self._hazard_geometry
        from colav_simulator.common.map_functions import (  # noqa: PLC0415
            extract_relevant_grounding_hazards_as_union,
            find_minimum_depth,
        )

        minimum_depth = find_minimum_depth(planner_input.ownship_draft_m, enc)
        hazards = extract_relevant_grounding_hazards_as_union(minimum_depth, enc)
        self._hazard_cache_key = cache_key
        self._hazard_geometry = hazards[0] if hazards else None
        return self._hazard_geometry

    def _select_candidate(  # noqa: C901, PLR0912, PLR0913, PLR0915
        self,
        *,
        controls: np.ndarray,
        speed_scales: np.ndarray,
        feasible_indices: np.ndarray,
        minimum_clearance: np.ndarray,
        minimum_static_clearance: np.ndarray,
        pass_astern: np.ndarray,
        policy: _Policy,
        ownship_course: float,
        target_course: float,
        nominal_feasible: bool,
        candidates: np.ndarray,
        sim_time_s: float,
        route_speed_mps: float,
    ) -> _Selection:
        selection = feasible_indices.copy()
        relaxations = []
        route_offsets = _wrap_angle(controls[:, 2, 0] - target_course)
        substantial = np.abs(route_offsets) >= np.deg2rad(self.params.minimum_colreg_turn_deg) - 1e-12
        if policy.give_way_targets:
            if policy.starboard_required:
                compliant = selection[route_offsets[selection] > 0.0]
            elif self._maneuver_sign:
                compliant = selection[np.sign(route_offsets[selection]) == self._maneuver_sign]
            else:
                compliant = selection[substantial[selection]]
            if self._maneuver_course is None:
                compliant = compliant[substantial[compliant]]
            if compliant.size:
                selection = compliant
            else:
                relaxations.append("minimum_colreg_action")
            if policy.crossing_give_way_targets:
                astern = selection[pass_astern[selection]]
                if astern.size:
                    selection = astern
                else:
                    relaxations.append("pass_astern")
        stand_on_reference_active = (
            not policy.give_way_targets
            and bool(policy.stand_on_targets)
            and nominal_feasible
            and self._stand_on_course is not None
        )
        stand_on_emergency_active = (
            not policy.give_way_targets
            and bool(policy.stand_on_targets)
            and not nominal_feasible
            and self._stand_on_course is not None
        )
        if stand_on_reference_active:
            selection = selection[np.isclose(speed_scales[selection], 1.0)]
        elif policy.stand_on_targets and not policy.give_way_targets:
            relaxations.append("stand_on_emergency_override")

        reference_course = ownship_course if self._previous_command_course is None else self._previous_command_course
        course_change = np.abs(_wrap_angle(controls[selection, 2, 0] - reference_course))
        rate_limited = selection[course_change <= np.deg2rad(self.params.max_command_change_deg) + 1e-12]
        if rate_limited.size:
            selection = rate_limited
        else:
            relaxations.append("command_rate_limit_emergency")

        if stand_on_emergency_active:
            stand_on_error = np.abs(_wrap_angle(controls[selection, 2, 0] - self._stand_on_course))
            selection = selection[np.isclose(stand_on_error, np.min(stand_on_error))]
        highest_executable_speed_scale = float(np.max(speed_scales[selection]))
        selection = selection[np.isclose(speed_scales[selection], highest_executable_speed_scale)]
        if stand_on_reference_active:
            stand_on_error = np.abs(_wrap_angle(controls[selection, 2, 0] - self._stand_on_course))
            selection = selection[np.isclose(stand_on_error, np.min(stand_on_error))]
        elif self._maneuver_phase == "RETURN" and not policy.give_way_targets and not policy.stand_on_targets:
            return_error = np.abs(_wrap_angle(controls[selection, 2, 0] - target_course))
            selection = selection[np.isclose(return_error, np.min(return_error))]
        scoring_course = self._stand_on_course if stand_on_reference_active or stand_on_emergency_active else target_course
        route_score = np.abs(_wrap_angle(controls[selection, 2, 0] - scoring_course))
        route_score += 0.25 * (1.0 - speed_scales[selection])
        continuity_score = np.zeros(selection.size)
        if self._previous_command_course is not None:
            continuity_score = np.abs(_wrap_angle(controls[selection, 2, 0] - self._previous_command_course))
        trajectory_continuity_score = self._trajectory_continuity_score(
            candidates[selection],
            sim_time_s,
            route_speed_mps,
        )
        reversal = np.zeros(selection.size)
        if self._maneuver_sign:
            reversal[np.sign(route_offsets[selection]) == -self._maneuver_sign] = 1.0
        selected_clearance = minimum_clearance[selection]
        clearance_score = np.zeros(selection.size)
        finite = np.isfinite(selected_clearance)
        clearance_score[finite] = np.clip(
            1.0 - selected_clearance[finite] / (2.0 * self.params.collision_distance_m),
            0.0,
            1.0,
        )
        selected_static = minimum_static_clearance[selection]
        static_score = np.zeros(selection.size)
        finite_static = np.isfinite(selected_static)
        static_score[finite_static] = np.clip(
            1.0 - selected_static[finite_static] / self.params.static_influence_distance_m,
            0.0,
            1.0,
        )
        continuity_weight = (
            self.params.continuity_weight if self._maneuver_phase == "AVOID" else min(0.25, self.params.continuity_weight)
        )
        trajectory_continuity_weight = (
            self.params.trajectory_continuity_weight
            if self._maneuver_phase == "AVOID"
            else min(0.25, self.params.trajectory_continuity_weight)
        )
        score = (
            route_score
            + continuity_weight * continuity_score
            + trajectory_continuity_weight * trajectory_continuity_score
            + self.params.clearance_weight * clearance_score
            + self.params.static_clearance_weight * static_score
            + self.params.reversal_weight * reversal
        )
        best = int(np.argmin(score))
        return _Selection(
            index=int(selection[best]),
            score=float(score[best]),
            route_score=float(route_score[best]),
            continuity_score=float(continuity_score[best]),
            trajectory_continuity_score=float(trajectory_continuity_score[best]),
            clearance_score=float(clearance_score[best]),
            static_clearance_score=float(static_score[best]),
            reversal_penalty=float(reversal[best]),
            relaxations=tuple(relaxations),
        )

    def _trajectory_continuity_score(
        self,
        candidates: np.ndarray,
        sim_time_s: float,
        route_speed_mps: float,
    ) -> np.ndarray:
        if self._previous_trajectory is None or self._previous_solve_time_s is None:
            return np.zeros(candidates.shape[0])
        elapsed_s = max(0.0, sim_time_s - self._previous_solve_time_s)
        shift = max(1, int(round(elapsed_s / self.params.horizon_dt_s)))
        overlap = min(
            4,
            candidates.shape[2],
            self._previous_trajectory.shape[1] - shift,
        )
        if overlap <= 0:
            return np.zeros(candidates.shape[0])
        previous = self._previous_trajectory[:2, shift : shift + overlap]
        deviation = np.linalg.norm(candidates[:, :2, :overlap] - previous[None, :, :], axis=1)
        normalization = max(
            self.params.collision_distance_m,
            route_speed_mps * self.params.horizon_dt_s * overlap,
            1.0,
        )
        return np.mean(deviation, axis=1) / normalization

    def _update_maneuver_phase(
        self,
        policy: _Policy,
        cross_track_error_m: float,
        ownship_course: float,
        target_course: float,
    ) -> None:
        if policy.give_way_targets:
            self._maneuver_phase = "AVOID"
            return
        if self._maneuver_phase == "AVOID":
            self._maneuver_phase = "RETURN"
        if self._maneuver_phase != "RETURN":
            return
        course_error = abs(float(_wrap_angle(ownship_course - target_course)))
        capture_distance = max(self.params.static_clearance_m, 0.1 * self.params.route_lookahead_m)
        if abs(cross_track_error_m) <= capture_distance and course_error <= np.deg2rad(self.params.minimum_colreg_turn_deg):
            self._maneuver_phase = "TRACK"

    def _record_policy_state(
        self,
        policy: _Policy,
        selected_increment: float,
        selected_course: float,
    ) -> None:
        if policy.starboard_required:
            self._maneuver_sign = 1
            if self._maneuver_course is None:
                self._maneuver_course = selected_course
            self._clear_solves = 0
        elif policy.give_way_targets:
            if not self._maneuver_sign and abs(selected_increment) >= np.deg2rad(0.25):
                self._maneuver_sign = int(np.sign(selected_increment))
            if self._maneuver_course is None:
                self._maneuver_course = selected_course
            self._clear_solves = 0
        else:
            self._clear_solves += 1
            if self._clear_solves >= 2:
                self._maneuver_sign = 0
                self._maneuver_course = None

    def _heading_grid_tolerance(self) -> float:
        if self.params.candidate_count <= 1:
            return np.deg2rad(0.25)
        spacing = 2.0 * np.deg2rad(self.params.max_heading_increment_deg) / (self.params.candidate_count - 1)
        return 0.5 * spacing + 1e-12

    def _target_predictions(self, planner_input: PlannerInput) -> list[dict]:
        times = np.arange(self.params.prediction_steps + 1, dtype=float) * self.params.horizon_dt_s
        output = []
        for track in planner_input.tracks:
            north = track.state_enu[0] + track.state_enu[2] * times
            east = track.state_enu[1] + track.state_enu[3] * times
            output.append(
                {
                    "target_id": track.target_id,
                    "north_m": north.tolist(),
                    "east_m": east.tolist(),
                    "velocity_ne_mps": track.state_enu[2:4].tolist(),
                    "length_m": track.length_m,
                    "width_m": track.width_m,
                    "prediction_model": "constant_velocity",
                }
            )
        return output


def create(
    *,
    context: FactoryContext,
    prediction_steps: int = 20,
    candidate_count: int = 45,
    horizon_dt_s: float = 5.0,
    solve_period_s: float = 5.0,
    deadline_s: float = 0.5,
    max_heading_increment_deg: float = 10.0,
    heading_increment_decay: float = 0.95,
    collision_distance_m: float = 150.0,
    colreg_zone_distance_m: float = PAPER_COLREG_ZONE_M,
    continuity_weight: float = 4.0,
    clearance_weight: float = 4.0,
    reversal_weight: float = 2.0,
    max_command_change_deg: float = 5.0,
    minimum_colreg_turn_deg: float = 5.0,
    course_response_time_constant_s: float = 8.0,
    speed_response_time_constant_s: float = 10.0,
    max_yaw_rate_deg_s: float = 3.0,
    max_speed_rate_mps2: float = 0.3,
    speed_scales: tuple[float, ...] = (1.0, 0.75, 0.5, 0.25),
    static_clearance_m: float = 20.0,
    static_influence_distance_m: float = 200.0,
    static_clearance_weight: float = 1.0,
    route_lookahead_m: float = 200.0,
    trajectory_continuity_weight: float = 2.0,
) -> CustomMPCAdapter:
    """Build the enhanced algorithm under its separate stable identity."""
    params = PotocnikColregParams(
        prediction_steps=prediction_steps,
        candidate_count=candidate_count,
        horizon_dt_s=horizon_dt_s,
        solve_period_s=solve_period_s,
        deadline_s=deadline_s,
        max_heading_increment_deg=max_heading_increment_deg,
        heading_increment_decay=heading_increment_decay,
        collision_distance_m=collision_distance_m,
        colreg_zone_distance_m=colreg_zone_distance_m,
        continuity_weight=continuity_weight,
        clearance_weight=clearance_weight,
        reversal_weight=reversal_weight,
        max_command_change_deg=max_command_change_deg,
        minimum_colreg_turn_deg=minimum_colreg_turn_deg,
        course_response_time_constant_s=course_response_time_constant_s,
        speed_response_time_constant_s=speed_response_time_constant_s,
        max_yaw_rate_deg_s=max_yaw_rate_deg_s,
        max_speed_rate_mps2=max_speed_rate_mps2,
        speed_scales=tuple(speed_scales),
        static_clearance_m=static_clearance_m,
        static_influence_distance_m=static_influence_distance_m,
        static_clearance_weight=static_clearance_weight,
        route_lookahead_m=route_lookahead_m,
        trajectory_continuity_weight=trajectory_continuity_weight,
    )
    solver = PotocnikColregFanMPC(params)
    descriptor = AlgorithmDescriptor(
        algorithm_id=context.requested_algorithm,
        version=__version__,
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="bounded_course_speed_response_fan",
        horizon_dt=params.horizon_dt_s,
        horizon_steps=params.prediction_steps + 1,
        objective_terms=(
            "waypoint_alignment",
            "command_continuity",
            "trajectory_continuity",
            "dynamic_clearance",
            "static_clearance",
            "maneuver_reversal",
        ),
        constraint_terms=(
            "continuous_dynamic_clearance",
            "optional_enc_grounding_clearance",
            "head_on_starboard",
            "crossing_give_way_starboard_pass_astern",
            "stand_on_course_speed",
            "early_substantial_action",
            "command_rate_limit",
            "avoid_return_track_state",
        ),
        solver="exhaustive_course_speed_fan_filter",
        seed_policy="deterministic_no_rng",
        execution_profile=ExecutionProfile(
            solve_period_s=params.solve_period_s,
            deadline_s=params.deadline_s,
            requires_enc=False,
        ),
    )
    return CustomMPCAdapter(
        descriptor=descriptor,
        solve=solver.solve,
        reset=solver.reset,
        context=context,
    )


def _continuous_minimum_distance(own_ne: np.ndarray, target_ne: np.ndarray) -> np.ndarray:
    return _batched_continuous_minimum_distance(own_ne, target_ne[None, ...])[0]


def _batched_continuous_minimum_distance(
    own_ne: np.ndarray,
    targets_ne: np.ndarray,
) -> np.ndarray:
    relative = targets_ne[:, None, :, :] - own_ne[None, ...]
    starts = relative[..., :-1]
    changes = relative[..., 1:] - starts
    denominator = np.sum(changes * changes, axis=2)
    tau = np.divide(
        -np.sum(starts * changes, axis=2),
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 1e-12,
    )
    tau = np.clip(tau, 0.0, 1.0)
    closest = starts + changes * tau[:, :, None, :]
    return np.min(np.linalg.norm(closest, axis=2), axis=2)


def _relative_position_at_continuous_cpa(
    own_ne: np.ndarray,
    target_ne: np.ndarray,
) -> np.ndarray:
    relative = own_ne - target_ne[None, :, :]
    starts = relative[:, :, :-1]
    changes = relative[:, :, 1:] - starts
    denominator = np.sum(changes * changes, axis=1)
    tau = np.divide(
        -np.sum(starts * changes, axis=1),
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 1e-12,
    )
    tau = np.clip(tau, 0.0, 1.0)
    closest = starts + changes * tau[:, None, :]
    distances = np.linalg.norm(closest, axis=1)
    interval = np.argmin(distances, axis=1)
    return closest[np.arange(own_ne.shape[0]), :, interval]


def _own_velocity_ne(ownship: np.ndarray) -> np.ndarray:
    heading = float(ownship[2])
    return np.array(
        [
            ownship[3] * np.cos(heading) - ownship[4] * np.sin(heading),
            ownship[3] * np.sin(heading) + ownship[4] * np.cos(heading),
        ]
    )


def _route_guidance(
    position_ne: np.ndarray,
    waypoints_ne: np.ndarray,
    lookahead_m: float,
) -> tuple[np.ndarray, float, float, int]:
    if waypoints_ne.shape[1] < 2:
        goal = waypoints_ne[:, 0].copy()
        delta = goal - position_ne
        return goal, float(np.arctan2(delta[1], delta[0])), 0.0, 0

    starts = waypoints_ne[:, :-1].T
    ends = waypoints_ne[:, 1:].T
    vectors = ends - starts
    lengths = np.linalg.norm(vectors, axis=1)
    valid = lengths > 1e-9
    along = np.zeros(lengths.size)
    along[valid] = np.sum((position_ne - starts[valid]) * vectors[valid], axis=1) / lengths[valid] ** 2
    projections = starts + np.clip(along, 0.0, 1.0)[:, None] * vectors
    segment = int(np.argmin(np.linalg.norm(projections - position_ne, axis=1)))
    if not valid[segment]:
        goal = ends[segment].copy()
        delta = goal - position_ne
        return goal, float(np.arctan2(delta[1], delta[0])), 0.0, segment + 1

    unit = vectors[segment] / lengths[segment]
    projection_distance = float(np.clip(along[segment], 0.0, 1.0) * lengths[segment])
    capture_distance = min(lengths[segment], projection_distance + lookahead_m)
    goal = starts[segment] + capture_distance * unit
    delta = goal - position_ne
    target_course = float(np.arctan2(delta[1], delta[0]))
    cross_track = float(unit[0] * (position_ne[1] - starts[segment, 1]) - unit[1] * (position_ne[0] - starts[segment, 0]))
    return goal, target_course, cross_track, segment + 1


def _finite_list(values: np.ndarray) -> list[float | None]:
    return [float(value) if np.isfinite(value) else None for value in values]


def _wrap_angle(value: float | np.ndarray) -> float | np.ndarray:
    return np.arctan2(np.sin(value), np.cos(value))
