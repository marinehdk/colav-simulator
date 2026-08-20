"""Behavior-compatible reconstruction of Kuwata et al.'s 2011 VO planner.

The core implements the published local-planner structure: geometric velocity
obstacles, bounded target-velocity uncertainty, a COLREG rule selector with
hysteresis, and deterministic velocity-grid search. It is not a complete
implementation of COLREG Rules 2-19 or a vessel-dynamics optimizer.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from seacharts.enc import ENC
from shapely import affinity, geometry, ops
from shapely.geometry.base import BaseGeometry

import colav_simulator.common.math_functions as mf


class VOCOLREGSSituation(Enum):
    """COLREG encounter roles represented by the Kuwata rule selector."""

    HO = 0
    OT_ing = 1
    OT_en = 2
    CR_PS = 3
    CR_SS = 4


class OvertakingState(Enum):
    """Lifecycle for one Rule 13 overtaking target."""

    CLEAR = "CLEAR"
    COMMITTED = "COMMITTED"
    PASSED = "PASSED"


_REMOVED_CONFIG_KEYS = {
    "safety_buffer",
    "vo_violation_cost",
    "grounding_cost",
    "colregs_violation_cost",
}
_DYNAMICS_PREDICTION_STEP_S = 1.0
_DYNAMICS_INTEGRATION_MARGIN_M = 0.25


@dataclass
class VOParams:
    """Parameters for the 2011 Kuwata VO behavior reconstruction."""

    length_os: float = 10.0
    width_os: float = 5.0
    draft_os: float = 2.0
    planning_frequency: float = 1.0
    t_max: float = 120.0
    d_min: float = 100.0
    hard_hull_clearance_m: float = 50.0
    preferred_hull_clearance_m: float = 100.0

    speed_set_limits: list[float] = field(default_factory=lambda: [0.0, 10.0])
    speed_samples: int = 32
    heading_samples: int = 128

    w_ttc: float = 500.0
    w_velocity: float = 1.0
    wvo_ttc_scale: float = 0.25
    Q: np.ndarray = field(default_factory=lambda: np.eye(2))
    velocity_uncertainty_vertices_mps: list[list[float]] = field(
        default_factory=lambda: [[-1.2, -1.2], [-1.2, 1.2], [1.2, 1.2], [1.2, -1.2]]
    )
    uncertainty_edge_samples: int = 4

    colregs_hysteresis_steps: int = 3
    colregs_min_target_speed_mps: float = 0.5
    crossing_commitment_deadband_mps: float = 0.25
    give_way_release_distance_m: float = 150.0
    give_way_release_steps: int = 3
    crossing_passed_distance_m: float = 100.0
    crossing_confirmation_steps: int = 3
    stand_on_emergency_toc_s: float = 60.0
    overtaking_t_max_s: float = 240.0
    overtaking_min_starboard_rad: float = float(np.deg2rad(5.0))
    overtaking_speed_advantage_mps: float = 0.5
    overtaking_passed_lead_m: float = 50.0
    overtaking_passed_distance_m: float = 100.0
    overtaking_confirmation_steps: int = 3
    overtaking_rearm_distance_m: float = 300.0
    rule_heading_tolerance_rad: float = float(np.deg2rad(15.0))
    rule_crossing_heading_min_rad: float = float(np.deg2rad(15.0))
    rule_crossing_heading_max_rad: float = float(np.deg2rad(165.0))
    rule_bearing_min_rad: float = 0.0
    rule_bearing_max_rad: float = float(np.deg2rad(112.5))
    rule_cross_track_min_m: float = 0.0
    rule_cross_track_max_m: float = 20.0
    rule_along_track_min_m: float = 0.0

    static_hazard_layers: tuple[str, ...] = ("LAND", "SHORE", "OBSTRN", "UWTROC")
    static_query_range_m: float = 1000.0

    reconstruction_label: str = "kuwata_2011_behavior_compatible_reconstruction"

    def __post_init__(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """Validate and normalize public configuration values."""
        self.Q = np.asarray(self.Q, dtype=float)
        if self.Q.shape == (2,):
            self.Q = np.diag(self.Q)
        if self.Q.shape != (2, 2):
            raise ValueError("Q must be a 2x2 matrix or a two-element diagonal")
        if self.speed_samples < 2 or self.heading_samples < 4:
            raise ValueError("VO grid requires speed_samples >= 2 and heading_samples >= 4")
        if self.planning_frequency <= 0.0:
            raise ValueError("planning_frequency must be positive")
        if not 0.0 <= self.wvo_ttc_scale <= 1.0:
            raise ValueError("wvo_ttc_scale must be in [0, 1]")
        if self.colregs_hysteresis_steps < 1:
            raise ValueError("colregs_hysteresis_steps must be positive")
        if self.crossing_commitment_deadband_mps < 0.0:
            raise ValueError("crossing_commitment_deadband_mps must be non-negative")
        if self.hard_hull_clearance_m < 0.0:
            raise ValueError("hard_hull_clearance_m must be non-negative")
        if self.preferred_hull_clearance_m < self.hard_hull_clearance_m:
            raise ValueError(
                "preferred_hull_clearance_m must be greater than or equal to "
                "hard_hull_clearance_m"
            )
        if self.give_way_release_distance_m < 0.0:
            raise ValueError("give_way_release_distance_m must be non-negative")
        if self.give_way_release_steps < 1:
            raise ValueError("give_way_release_steps must be positive")
        if self.crossing_passed_distance_m < 0.0:
            raise ValueError("crossing_passed_distance_m must be non-negative")
        if self.crossing_confirmation_steps < 1:
            raise ValueError("crossing_confirmation_steps must be positive")
        if self.stand_on_emergency_toc_s <= 0.0:
            raise ValueError("stand_on_emergency_toc_s must be positive")
        if self.overtaking_t_max_s <= 0.0:
            raise ValueError("overtaking_t_max_s must be positive")
        if self.overtaking_min_starboard_rad < 0.0:
            raise ValueError("overtaking_min_starboard_rad must be non-negative")
        if self.overtaking_speed_advantage_mps < 0.0:
            raise ValueError("overtaking_speed_advantage_mps must be non-negative")
        if self.overtaking_passed_lead_m < 0.0 or self.overtaking_passed_distance_m < 0.0:
            raise ValueError("overtaking pass thresholds must be non-negative")
        if self.overtaking_confirmation_steps < 1:
            raise ValueError("overtaking_confirmation_steps must be positive")
        if self.overtaking_rearm_distance_m < 0.0:
            raise ValueError("overtaking_rearm_distance_m must be non-negative")
        vertices = np.asarray(self.velocity_uncertainty_vertices_mps, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) == 0:
            raise ValueError("velocity_uncertainty_vertices_mps must contain 2-D vertices")
        uncertainty_set = geometry.MultiPoint(vertices).convex_hull
        if not uncertainty_set.buffer(1e-12).covers(geometry.Point(0.0, 0.0)):
            raise ValueError("velocity uncertainty set W_B must contain the zero error")

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["Q"] = self.Q.tolist()
        output["static_hazard_layers"] = list(self.static_hazard_layers)
        return output

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VOParams:
        removed = sorted(_REMOVED_CONFIG_KEYS.intersection(data))
        if removed:
            keys = ", ".join(removed)
            raise ValueError(
                f"Removed VO configuration key(s): {keys}. "
                "Spatial safety buffers and finite violation penalties cannot be "
                "converted to Kuwata velocity uncertainty or hard constraints."
            )
        valid = set(cls.__dataclass_fields__)
        unknown = sorted(set(data) - valid)
        if unknown:
            raise ValueError(f"Unknown VO configuration key(s): {', '.join(unknown)}")
        values = dict(data)
        if "Q" in values:
            values["Q"] = np.asarray(values["Q"], dtype=float)
        if "static_hazard_layers" in values:
            values["static_hazard_layers"] = tuple(values["static_hazard_layers"])
        return cls(**values)


class VO:
    """Kuwata velocity-obstacle local planner."""

    def __init__(self, config: VOParams | None = None) -> None:  # noqa: PLR0915
        self._params = config or VOParams()
        self._poly_os = geometry.Polygon(
            [
                (-self._params.length_os / 2.0, -self._params.width_os / 2.0),
                (self._params.length_os / 2.0, -self._params.width_os / 2.0),
                (self._params.length_os / 2.0, self._params.width_os / 2.0),
                (-self._params.length_os / 2.0, self._params.width_os / 2.0),
            ]
        )
        self._speed_set = np.linspace(
            self._params.speed_set_limits[0],
            self._params.speed_set_limits[1],
            self._params.speed_samples,
        )
        self._heading_set = np.linspace(-np.pi, np.pi, self._params.heading_samples, endpoint=False)
        shape = (len(self._speed_set), len(self._heading_set))
        self._hard_constraint_mask = np.zeros(shape, dtype=bool)
        self._base_vo_mask = np.zeros(shape, dtype=bool)
        self._colregs_v1_mask_grid = np.zeros(shape, dtype=bool)
        self._crossing_commitment_mask = np.zeros(shape, dtype=bool)
        self._wvo_mask = np.zeros(shape, dtype=bool)
        self._preferred_clearance_mask = np.zeros(shape, dtype=bool)
        self._min_ttc = np.full(shape, np.inf)
        self._preferred_clearance_ttc = np.full(shape, np.inf)
        self._violation_costs = np.zeros(shape)
        self._total_costs = np.full(shape, np.inf)
        self._references = np.zeros((9, 1))
        self._rule_memory: dict[tuple[int, VOCOLREGSSituation], int] = {}
        self._give_way_rule_locks: dict[int, VOCOLREGSSituation] = {}
        self._give_way_release_counts: dict[int, int] = {}
        self._give_way_previous_distances: dict[int, float] = {}
        self._completed_give_way_targets: set[int] = set()
        self._give_way_rearm_counts: dict[int, int] = {}
        self._overtaking_states: dict[int, OvertakingState] = {}
        self._overtaking_completion_counts: dict[int, int] = {}
        self._overtaking_disengage_counts: dict[int, int] = {}
        self._overtaking_rearm_counts: dict[int, int] = {}
        self._overtaking_release_reasons: dict[int, str | None] = {}
        self._overtaking_entry_tcpa_s: dict[int, float] = {}
        self._overtaking_target_headings: dict[int, float] = {}
        self._overtaking_target_speeds: dict[int, float] = {}
        self._overtaking_metrics: dict[int, dict[str, float | None]] = {}
        self._overtaking_active_target_id: int | None = None
        self._overtaking_last_target_id: int | None = None
        self._overtaking_commitment_active = False
        self._overtaking_commitment_frame_heading: float | None = None
        self._overtaking_progress_relaxed = False
        self._target_heading_memory: dict[int, float] = {}
        self._active_rules: dict[int, set[VOCOLREGSSituation]] = {}
        self._matched_rules_current: set[VOCOLREGSSituation] = set()
        self._completed_crossing_targets: set[int] = set()
        self._crossing_completion_counts: dict[int, int] = {}
        self._crossing_previous_distances: dict[int, float] = {}
        self._initialized = False
        self._t_prev = 0.0
        self._plan_executed = False
        self._feasible = True
        self._selected_heading = 0.0
        self._selected_speed = 0.0
        self._objective: float | None = None
        self._dynamic_hazard_count = 0
        self._static_hazard_count = 0
        self._track_metrics: dict[int, dict[str, Any]] = {}
        self._target_count_current = 0
        self._reference_velocity_error_mps = 0.0
        self._reference_velocity = np.zeros(2)
        self._current_velocity = np.zeros(2)
        self._ownship_heading = 0.0
        self._crossing_commitment_active = False
        self._crossing_commitment_frame_heading: float | None = None
        self._give_way_commitment_active = False
        self._give_way_commitment_rules: set[VOCOLREGSSituation] = set()
        self._emergency_rule_relaxation = False
        self._stand_on_hold_active = False
        self._stand_on_emergency_active = False
        self._driving_target_id: int | None = None
        self._driving_rule: str | None = None
        self._expired_target_ids_last_solve: list[int] = []
        self._ownship_length_m = self._params.length_os
        self._ownship_width_m = self._params.width_os
        self._dynamics_prediction_active = False

    @property
    def plan_executed(self) -> bool:
        return self._plan_executed

    @property
    def feasible(self) -> bool:
        return self._feasible

    def get_current_plan(self) -> np.ndarray:
        return self._references

    def reset(self) -> None:
        self._initialized = False
        self._t_prev = 0.0
        self._plan_executed = False
        self._feasible = True
        self._references.fill(0.0)
        self._rule_memory.clear()
        self._give_way_rule_locks.clear()
        self._give_way_release_counts.clear()
        self._give_way_previous_distances.clear()
        self._completed_give_way_targets.clear()
        self._give_way_rearm_counts.clear()
        self._overtaking_states.clear()
        self._overtaking_completion_counts.clear()
        self._overtaking_disengage_counts.clear()
        self._overtaking_rearm_counts.clear()
        self._overtaking_release_reasons.clear()
        self._overtaking_entry_tcpa_s.clear()
        self._overtaking_target_headings.clear()
        self._overtaking_target_speeds.clear()
        self._overtaking_metrics.clear()
        self._overtaking_active_target_id = None
        self._overtaking_last_target_id = None
        self._overtaking_commitment_active = False
        self._overtaking_commitment_frame_heading = None
        self._overtaking_progress_relaxed = False
        self._target_heading_memory.clear()
        self._active_rules.clear()
        self._matched_rules_current.clear()
        self._completed_crossing_targets.clear()
        self._crossing_completion_counts.clear()
        self._crossing_previous_distances.clear()
        self._crossing_commitment_active = False
        self._crossing_commitment_frame_heading = None
        self._give_way_commitment_active = False
        self._give_way_commitment_rules.clear()
        self._emergency_rule_relaxation = False
        self._stand_on_hold_active = False
        self._stand_on_emergency_active = False
        self._driving_target_id = None
        self._driving_rule = None
        self._expired_target_ids_last_solve = []
        self._target_count_current = 0
        self._dynamics_prediction_active = False
        self._reset_grid()

    def _reset_grid(self) -> None:
        self._hard_constraint_mask.fill(False)
        self._base_vo_mask.fill(False)
        self._colregs_v1_mask_grid.fill(False)
        self._crossing_commitment_mask.fill(False)
        self._wvo_mask.fill(False)
        self._preferred_clearance_mask.fill(False)
        self._min_ttc.fill(np.inf)
        self._preferred_clearance_ttc.fill(np.inf)
        self._violation_costs.fill(0.0)
        self._total_costs.fill(np.inf)

    def plan(  # noqa: PLR0915
        self,
        t: float,
        v_ref: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list,
        enc: ENC | None = None,
        *,
        os_length: float | None = None,
        os_width: float | None = None,
        os_course_time_constant_s: float | None = None,
        os_speed_time_constant_s: float | None = None,
        os_max_turn_rate_radps: float | None = None,
    ) -> np.ndarray:
        if self._initialized and t - self._t_prev < 1.0 / self._params.planning_frequency:
            self._plan_executed = False
            return self._references

        self._initialized = True
        self._t_prev = t
        self._plan_executed = True
        self._reset_grid()

        p_os = np.asarray(ownship_state[0:2], dtype=float)
        psi_os = float(ownship_state[2])
        v_os = mf.Rmtrx2D(psi_os) @ np.asarray(ownship_state[3:5], dtype=float)
        self._reference_velocity = np.asarray(v_ref, dtype=float).copy()
        self._current_velocity = v_os.copy()
        self._ownship_heading = psi_os
        self._ownship_length_m = float(
            self._params.length_os if os_length is None else os_length
        )
        self._ownship_width_m = float(
            self._params.width_os if os_width is None else os_width
        )
        if self._ownship_length_m <= 0.0 or self._ownship_width_m <= 0.0:
            raise ValueError("Ownship length and width must be positive")
        poly_os = geometry.box(
            -self._ownship_length_m / 2.0,
            -self._ownship_width_m / 2.0,
            self._ownship_length_m / 2.0,
            self._ownship_width_m / 2.0,
        )
        poly_os_shape = affinity.rotate(poly_os, psi_os, origin=(0.0, 0.0), use_radians=True)
        poly_os_world = affinity.translate(poly_os_shape, p_os[0], p_os[1])
        static_poly_os = geometry.box(
            -max(self._ownship_length_m, self._params.length_os) / 2.0,
            -max(self._ownship_width_m, self._params.width_os) / 2.0,
            max(self._ownship_length_m, self._params.length_os) / 2.0,
            max(self._ownship_width_m, self._params.width_os) / 2.0,
        )
        static_poly_os_shape = affinity.rotate(
            static_poly_os,
            psi_os,
            origin=(0.0, 0.0),
            use_radians=True,
        )
        candidate_velocities = self._candidate_velocities()
        candidate_positions = self._predict_candidate_positions(
            p_os,
            psi_os,
            float(np.linalg.norm(v_os)),
            candidate_velocities,
            course_time_constant_s=os_course_time_constant_s,
            speed_time_constant_s=os_speed_time_constant_s,
            max_turn_rate_radps=os_max_turn_rate_radps,
        )
        self._dynamics_prediction_active = candidate_positions is not None
        uncertainty = self._uncertainty_samples()

        self._dynamic_hazard_count = 0
        self._track_metrics = {}
        self._target_count_current = len(do_list)
        self._matched_rules_current.clear()
        seen_target_ids: set[int] = set()
        for target in sorted(do_list, key=lambda item: int(item[0])):
            id_do, state_do, _covariance, length_do, width_do = target
            id_do = int(id_do)
            seen_target_ids.add(id_do)
            state_do = np.asarray(state_do, dtype=float)
            p_do = state_do[0:2]
            v_do = state_do[2:4]
            speed_do = float(np.linalg.norm(v_do))
            rule_cpa = self._cpa_metrics(p_os, v_os, p_do, v_do)
            self._track_metrics[id_do] = dict(rule_cpa)
            self._track_metrics[id_do]["rule_tcpa_s"] = rule_cpa["tcpa_s"]
            self._track_metrics[id_do]["rule_dcpa_m"] = rule_cpa["dcpa_m"]
            target_polygon, psi_do = self._target_polygon(
                id_do, p_do, v_do, float(length_do), float(width_do)
            )
            expanded = compute_minkowski_sum(target_polygon, compute_reflection(poly_os_shape))
            hard_clearance_domain = expanded.buffer(
                self._params.hard_hull_clearance_m,
                join_style=2,
            )
            preferred_clearance_domain = expanded.buffer(
                self._params.preferred_hull_clearance_m,
                join_style=2,
            )
            current_hull_clearance = float(poly_os_world.distance(target_polygon))
            first_toc = float(
                ray_polygon_ttc_grid(
                    expanded,
                    p_os,
                    (v_os - v_do).reshape(1, 1, 2),
                )[0, 0]
            )
            self._track_metrics[id_do]["first_toc_s"] = first_toc if np.isfinite(first_toc) else None
            preferred_domain_toc = float(
                ray_polygon_ttc_grid(
                    preferred_clearance_domain,
                    p_os,
                    (v_os - v_do).reshape(1, 1, 2),
                )[0, 0]
            )
            self._track_metrics[id_do]["current_hull_clearance_m"] = current_hull_clearance
            self._track_metrics[id_do]["hard_hull_clearance_m"] = (
                self._params.hard_hull_clearance_m
            )
            self._track_metrics[id_do]["preferred_hull_clearance_m"] = (
                self._params.preferred_hull_clearance_m
            )
            self._track_metrics[id_do]["hard_clearance_margin_m"] = (
                current_hull_clearance - self._params.hard_hull_clearance_m
            )
            self._track_metrics[id_do]["preferred_domain_toc_s"] = (
                preferred_domain_toc if np.isfinite(preferred_domain_toc) else None
            )
            geometry_matched_rules = self._determine_colregs_rules(
                p_os,
                psi_os,
                v_os,
                p_do,
                v_do,
            )
            crossing_rules = {
                VOCOLREGSSituation.CR_SS,
                VOCOLREGSSituation.CR_PS,
            }
            previous_rules = self._active_rules.get(id_do, set()).copy()
            matched_rules = set(geometry_matched_rules)
            crossing_completed = self._update_crossing_completion(
                target_id=id_do,
                previous_rules=previous_rules,
                p_os=p_os,
                p_do=p_do,
                v_do=v_do,
                cpa=rule_cpa,
            )
            if crossing_completed:
                matched_rules.difference_update(crossing_rules)
            elif VOCOLREGSSituation.CR_SS in previous_rules:
                matched_rules.difference_update(crossing_rules)
                matched_rules.add(VOCOLREGSSituation.CR_SS)
            shape_risk_eligible = bool(
                np.isfinite(preferred_domain_toc)
                and 0.0 <= preferred_domain_toc <= self._params.t_max
            )
            cpa_gate_eligible = (
                speed_do >= self._params.colregs_min_target_speed_mps
                and shape_risk_eligible
            )
            give_way_lock_eligible = (
                speed_do >= self._params.colregs_min_target_speed_mps
                and self._precollision_check(p_os, v_os, p_do, v_do)
            )
            overtaking_state = self._update_overtaking_state(
                target_id=id_do,
                geometry_rules=geometry_matched_rules,
                p_os=p_os,
                v_os=v_os,
                p_do=p_do,
                v_do=v_do,
                cpa=rule_cpa,
            )
            if overtaking_state is OvertakingState.COMMITTED:
                matched_rules.difference_update(set(VOCOLREGSSituation))
                matched_rules.add(VOCOLREGSSituation.OT_ing)
            elif overtaking_state is OvertakingState.PASSED:
                matched_rules.difference_update(set(VOCOLREGSSituation))
            self._matched_rules_current.update(matched_rules)
            matched_rules = self._apply_give_way_rule_lock(
                target_id=id_do,
                matched_rules=matched_rules,
                p_os=p_os,
                p_do=p_do,
                cpa=rule_cpa,
                can_enter=give_way_lock_eligible,
            )
            overtaking_committed = overtaking_state is OvertakingState.COMMITTED
            commitment_eligible = (
                overtaking_committed
                or
                id_do in self._give_way_rule_locks
                or (
                    VOCOLREGSSituation.CR_SS in matched_rules
                    and VOCOLREGSSituation.CR_SS in self._active_rules.get(id_do, set())
                )
            )
            eligible_rules = (
                matched_rules
                if cpa_gate_eligible or overtaking_committed or id_do in self._give_way_rule_locks
                else (
                    {VOCOLREGSSituation.CR_SS}
                    if commitment_eligible
                    else set()
                )
            )
            rules = self._update_colregs_rules(
                id_do=id_do,
                matched=eligible_rules,
                eligible=True,
            )
            self._track_metrics[id_do]["colregs_eligible"] = bool(eligible_rules)
            self._track_metrics[id_do]["cpa_gate_eligible"] = cpa_gate_eligible
            self._track_metrics[id_do]["commitment_eligible"] = commitment_eligible
            self._track_metrics[id_do]["crossing_completed"] = crossing_completed
            self._track_metrics[id_do]["crossing_release_count"] = self._crossing_completion_counts.get(id_do, 0)
            self._track_metrics[id_do]["stand_on_emergency"] = bool(
                VOCOLREGSSituation.CR_PS in (rules | geometry_matched_rules)
                and np.isfinite(first_toc)
                and first_toc <= self._params.stand_on_emergency_toc_s
            )
            self._track_metrics[id_do]["overtaking_state"] = overtaking_state.value
            self._track_metrics[id_do].update(self._overtaking_metrics.get(id_do, {}))
            self._track_metrics[id_do]["matched_rules"] = [
                rule.name
                for rule in sorted(geometry_matched_rules, key=lambda item: item.value)
            ]
            self._track_metrics[id_do]["effective_matched_rules"] = [
                rule.name for rule in sorted(matched_rules, key=lambda item: item.value)
            ]
            self._track_metrics[id_do]["active_rules"] = [
                rule.name for rule in sorted(rules, key=lambda item: item.value)
            ]
            locked_rule = self._give_way_rule_locks.get(id_do)
            self._track_metrics[id_do]["committed_rule"] = (
                VOCOLREGSSituation.OT_ing.name
                if overtaking_committed
                else (locked_rule.name if locked_rule is not None else None)
            )
            if speed_do >= self._params.colregs_min_target_speed_mps:
                self._target_heading_memory[id_do] = psi_do
            self._track_metrics[id_do]["dynamic_hazard_ignored"] = False
            self._apply_dynamic_hazard(
                expanded,
                p_os,
                p_do,
                v_do,
                candidate_velocities,
                uncertainty,
                rules,
                hard_clearance_domain=hard_clearance_domain,
                preferred_clearance_domain=(
                    preferred_clearance_domain if shape_risk_eligible else None
                ),
            )
            if candidate_positions is not None:
                self._apply_dynamics_clearance_domain(
                    candidate_positions,
                    p_do,
                    v_do,
                    target_length_m=float(length_do),
                    target_width_m=float(width_do),
                )
            self._dynamic_hazard_count += 1

        self._expire_missing_targets(seen_target_ids)
        self._select_driving_target()
        self._select_overtaking_target()
        static_hazards = self._extract_static_hazards(enc, p_os, static_poly_os_shape)
        self._static_hazard_count = len(static_hazards)
        for expanded in static_hazards:
            self._apply_base_vo(
                expanded,
                p_os,
                np.zeros(2),
                candidate_velocities,
                uncertainty=None,
            )

        self._apply_give_way_commitment(candidate_velocities, psi_os)
        heading, speed = self._compute_optimal_controls(np.asarray(v_ref, dtype=float), psi_os)
        self._references.fill(0.0)
        self._references[2, 0] = heading
        self._references[3, 0] = speed
        return self._references

    def _predict_candidate_positions(
        self,
        p_os: np.ndarray,
        psi_os: float,
        speed_os: float,
        candidates: np.ndarray,
        *,
        course_time_constant_s: float | None,
        speed_time_constant_s: float | None,
        max_turn_rate_radps: float | None,
    ) -> np.ndarray | None:
        dynamics = (
            course_time_constant_s,
            speed_time_constant_s,
            max_turn_rate_radps,
        )
        if all(value is None for value in dynamics):
            return None
        if any(value is None or value <= 0.0 for value in dynamics):
            raise ValueError("Ownship dynamics values must all be positive")

        prediction_step_s = _DYNAMICS_PREDICTION_STEP_S
        step_count = int(np.ceil(self._params.t_max / prediction_step_s))
        positions = np.empty((step_count + 1, *candidates.shape[:2], 2))
        positions[0] = p_os
        headings = np.full(candidates.shape[:2], psi_os)
        speeds = np.full(candidates.shape[:2], speed_os)
        commanded_headings = np.arctan2(candidates[..., 1], candidates[..., 0])
        commanded_speeds = np.linalg.norm(candidates, axis=-1)

        for step in range(step_count):
            directions = np.stack((np.cos(headings), np.sin(headings)), axis=-1)
            positions[step + 1] = (
                positions[step]
                + prediction_step_s * speeds[..., None] * directions
            )
            course_error = (
                commanded_headings - headings + np.pi
            ) % (2.0 * np.pi) - np.pi
            headings += prediction_step_s * np.clip(
                course_error / course_time_constant_s,
                -max_turn_rate_radps,
                max_turn_rate_radps,
            )
            speeds += (
                prediction_step_s
                * (commanded_speeds - speeds)
                / speed_time_constant_s
            )

        return positions

    def _apply_dynamics_clearance_domain(
        self,
        candidate_positions: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
        *,
        target_length_m: float,
        target_width_m: float,
    ) -> None:
        prediction_step_s = self._params.t_max / (candidate_positions.shape[0] - 1)
        times = prediction_step_s * np.arange(candidate_positions.shape[0])
        target_positions = p_do + times[:, None] * v_do
        relative_positions = candidate_positions - target_positions[:, None, None, :]
        segment_starts = relative_positions[:-1]
        segment_deltas = relative_positions[1:] - segment_starts
        segment_lengths_squared = np.einsum(
            "...i,...i->...",
            segment_deltas,
            segment_deltas,
        )
        closest_fractions = np.divide(
            -np.einsum("...i,...i->...", segment_starts, segment_deltas),
            segment_lengths_squared,
            out=np.zeros_like(segment_lengths_squared),
            where=segment_lengths_squared > 0.0,
        )
        closest_fractions = np.clip(closest_fractions, 0.0, 1.0)
        closest_positions = (
            segment_starts + closest_fractions[..., None] * segment_deltas
        )
        center_distances = np.linalg.norm(closest_positions, axis=-1)
        combined_hull_radius = 0.5 * np.hypot(
            self._ownship_length_m,
            self._ownship_width_m,
        ) + 0.5 * np.hypot(target_length_m, target_width_m)
        hard_center_distance = (
            combined_hull_radius
            + self._params.hard_hull_clearance_m
            + _DYNAMICS_INTEGRATION_MARGIN_M
        )
        violations = center_distances < hard_center_distance
        dynamics_hard = np.any(violations, axis=0)
        first_violation = np.argmax(violations, axis=0) * prediction_step_s
        dynamics_ttc = np.where(dynamics_hard, first_violation, np.inf)
        self._base_vo_mask |= dynamics_hard
        self._hard_constraint_mask |= dynamics_hard
        self._min_ttc = np.minimum(self._min_ttc, dynamics_ttc)
        self._violation_costs[self._hard_constraint_mask] = np.inf

    def _candidate_velocities(self) -> np.ndarray:
        speeds, headings = np.meshgrid(self._speed_set, self._heading_set, indexing="ij")
        return np.stack((speeds * np.cos(headings), speeds * np.sin(headings)), axis=-1)

    def _ensure_grid_shape(self) -> None:
        shape = (len(self._speed_set), len(self._heading_set))
        if self._hard_constraint_mask.shape == shape:
            return
        self._hard_constraint_mask = np.zeros(shape, dtype=bool)
        self._base_vo_mask = np.zeros(shape, dtype=bool)
        self._colregs_v1_mask_grid = np.zeros(shape, dtype=bool)
        self._crossing_commitment_mask = np.zeros(shape, dtype=bool)
        self._wvo_mask = np.zeros(shape, dtype=bool)
        self._preferred_clearance_mask = np.zeros(shape, dtype=bool)
        self._min_ttc = np.full(shape, np.inf)
        self._preferred_clearance_ttc = np.full(shape, np.inf)
        self._violation_costs = np.zeros(shape)
        self._total_costs = np.full(shape, np.inf)

    def _apply_give_way_rule_lock(
        self,
        *,
        target_id: int,
        matched_rules: set[VOCOLREGSSituation],
        p_os: np.ndarray,
        p_do: np.ndarray,
        cpa: dict[str, float | None],
        can_enter: bool,
    ) -> set[VOCOLREGSSituation]:
        lockable = (VOCOLREGSSituation.HO,)
        give_way_rules = {*lockable, VOCOLREGSSituation.CR_SS}
        locked_rule = self._give_way_rule_locks.get(target_id)
        distance = float(np.linalg.norm(p_do - p_os))
        if target_id in self._completed_give_way_targets:
            rearm_distance = max(
                2.0 * self._params.give_way_release_distance_m,
                2.0 * self._params.d_min,
            )
            rearm_candidate = not can_enter and distance >= rearm_distance
            rearm_count = self._give_way_rearm_counts.get(target_id, 0)
            rearm_count = rearm_count + 1 if rearm_candidate else 0
            self._give_way_rearm_counts[target_id] = rearm_count
            if rearm_count < self._params.give_way_release_steps:
                return matched_rules.difference(give_way_rules)
            self._completed_give_way_targets.discard(target_id)
            self._give_way_rearm_counts.pop(target_id, None)

        if locked_rule is not None:
            previous_distance = self._give_way_previous_distances.get(target_id, distance)
            moving_away = distance >= previous_distance - 1e-9
            tcpa = cpa["tcpa_s"]
            passed = bool(tcpa is not None and tcpa <= 0.0 and moving_away)
            release_candidate = not can_enter and passed
            release_count = self._give_way_release_counts.get(target_id, 0)
            release_count = release_count + 1 if release_candidate else 0
            self._give_way_release_counts[target_id] = release_count
            self._give_way_previous_distances[target_id] = distance
            if release_count >= self._params.give_way_release_steps:
                self._rule_memory.pop((target_id, locked_rule), None)
                self._give_way_rule_locks.pop(target_id, None)
                self._give_way_release_counts.pop(target_id, None)
                self._give_way_previous_distances.pop(target_id, None)
                self._completed_give_way_targets.add(target_id)
                self._give_way_rearm_counts[target_id] = 0
                return matched_rules.difference(give_way_rules)
            return matched_rules.difference(lockable) | {locked_rule}

        if can_enter:
            locked_rule = next((rule for rule in lockable if rule in matched_rules), None)
            if locked_rule is not None:
                self._give_way_rule_locks[target_id] = locked_rule
                self._give_way_release_counts[target_id] = 0
                self._give_way_previous_distances[target_id] = distance
        return matched_rules

    def _update_crossing_completion(
        self,
        *,
        target_id: int,
        previous_rules: set[VOCOLREGSSituation],
        p_os: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
        cpa: dict[str, float | None],
    ) -> bool:
        if target_id in self._completed_crossing_targets:
            return True
        distance = float(cpa["center_distance_m"] or 0.0)
        previous_distance = self._crossing_previous_distances.get(target_id, distance)
        self._crossing_previous_distances[target_id] = distance
        if VOCOLREGSSituation.CR_SS not in previous_rules:
            self._crossing_completion_counts[target_id] = 0
            return False
        speed = float(np.linalg.norm(v_do))
        if speed < self._params.colregs_min_target_speed_mps:
            self._crossing_completion_counts[target_id] = 0
            return False
        target_along = v_do / speed
        own_along_from_target = float((p_os - p_do) @ target_along)
        tcpa = cpa["tcpa_s"]
        passed_candidate = bool(
            tcpa is not None
            and tcpa <= 0.0
            and own_along_from_target <= 0.0
            and distance >= self._params.crossing_passed_distance_m
            and distance >= previous_distance - 1e-9
        )
        count = self._crossing_completion_counts.get(target_id, 0)
        count = count + 1 if passed_candidate else 0
        self._crossing_completion_counts[target_id] = count
        if count < self._params.crossing_confirmation_steps:
            return False
        self._completed_crossing_targets.add(target_id)
        self._active_rules.get(target_id, set()).discard(VOCOLREGSSituation.CR_SS)
        self._rule_memory.pop((target_id, VOCOLREGSSituation.CR_SS), None)
        return True

    def _target_priority(self, target_id: int) -> tuple[int, float, float, float, int]:
        metrics = self._track_metrics.get(target_id, {})
        tcpa = metrics.get("rule_tcpa_s")
        dcpa = metrics.get("rule_dcpa_m")
        distance = metrics.get("center_distance_m")
        toc = metrics.get("first_toc_s")
        positive_tcpa = float(tcpa) if tcpa is not None and tcpa >= 0.0 else float("inf")
        finite_toc = float(toc) if toc is not None and toc >= 0.0 else float("inf")
        finite_dcpa = float(dcpa) if dcpa is not None else float("inf")
        finite_distance = float(distance) if distance is not None else float("inf")
        committed = bool(metrics.get("committed_rule"))
        active_risk = bool(metrics.get("cpa_gate_eligible") and metrics.get("active_rules"))
        imminent = finite_toc <= self._params.stand_on_emergency_toc_s or finite_distance <= self._params.d_min
        tier = 0 if imminent else (1 if active_risk else (2 if committed else 3))
        return tier, min(finite_toc, positive_tcpa), finite_dcpa, finite_distance, target_id

    def _select_driving_target(self) -> None:
        if not self._track_metrics:
            self._driving_target_id = None
            self._driving_rule = None
            return
        self._driving_target_id = min(self._track_metrics, key=self._target_priority)
        metrics = self._track_metrics[self._driving_target_id]
        active = list(metrics.get("active_rules", ()))
        matched = list(metrics.get("effective_matched_rules", ()))
        self._driving_rule = active[0] if active else (matched[0] if matched else None)

    def _update_overtaking_state(  # noqa: PLR0915
        self,
        *,
        target_id: int,
        geometry_rules: set[VOCOLREGSSituation],
        p_os: np.ndarray,
        v_os: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
        cpa: dict[str, float | None],
    ) -> OvertakingState:
        target_speed = float(np.linalg.norm(v_do))
        if target_speed >= self._params.colregs_min_target_speed_mps:
            target_heading = float(np.arctan2(v_do[1], v_do[0]))
            target_along = np.array([np.cos(target_heading), np.sin(target_heading)])
            target_starboard = np.array([-target_along[1], target_along[0]])
            own_from_target = p_os - p_do
            along_track = float(own_from_target @ target_along)
            cross_track = float(own_from_target @ target_starboard)
            relative_speed = float((v_os - v_do) @ target_along)
            self._overtaking_target_headings[target_id] = target_heading
            self._overtaking_target_speeds[target_id] = target_speed
        else:
            along_track = 0.0
            cross_track = 0.0
            relative_speed = 0.0

        tcpa = cpa["tcpa_s"]
        dcpa = cpa["dcpa_m"]
        distance = float(cpa["center_distance_m"] or 0.0)
        risk_eligible = bool(
            target_speed >= self._params.colregs_min_target_speed_mps
            and tcpa is not None
            and 0.0 <= tcpa <= self._params.overtaking_t_max_s
            and dcpa is not None
            and dcpa <= self._params.d_min
        )
        state = self._overtaking_states.get(target_id, OvertakingState.CLEAR)
        if state is OvertakingState.CLEAR:
            if VOCOLREGSSituation.OT_ing in geometry_rules and risk_eligible:
                state = OvertakingState.COMMITTED
                self._overtaking_states[target_id] = state
                self._overtaking_completion_counts[target_id] = 0
                self._overtaking_disengage_counts[target_id] = 0
                self._overtaking_entry_tcpa_s[target_id] = float(tcpa)
                self._overtaking_release_reasons[target_id] = None
                self._overtaking_last_target_id = target_id
        elif state is OvertakingState.COMMITTED:
            passed_candidate = bool(
                along_track >= self._params.overtaking_passed_lead_m
                and distance >= self._params.overtaking_passed_distance_m
                and relative_speed > 0.0
                and tcpa is not None
                and tcpa <= 0.0
            )
            count = self._overtaking_completion_counts.get(target_id, 0)
            count = count + 1 if passed_candidate else 0
            self._overtaking_completion_counts[target_id] = count
            separated_candidate = bool(
                self._target_count_current > 1
                and not risk_eligible
                and tcpa is not None
                and tcpa <= 0.0
                and distance >= self._params.overtaking_rearm_distance_m
                and abs(cross_track) >= self._params.overtaking_rearm_distance_m
                and along_track < self._params.overtaking_passed_lead_m
            )
            disengage_count = self._overtaking_disengage_counts.get(target_id, 0)
            disengage_count = disengage_count + 1 if separated_candidate else 0
            self._overtaking_disengage_counts[target_id] = disengage_count
            if count >= self._params.overtaking_confirmation_steps:
                state = OvertakingState.PASSED
                self._overtaking_states[target_id] = state
                self._overtaking_rearm_counts[target_id] = 0
                self._overtaking_release_reasons[target_id] = "passed"
                self._rule_memory.pop((target_id, VOCOLREGSSituation.OT_ing), None)
                self._overtaking_last_target_id = target_id
                if self._overtaking_active_target_id == target_id:
                    self._overtaking_active_target_id = None
            elif disengage_count >= self._params.overtaking_confirmation_steps:
                state = OvertakingState.CLEAR
                self._overtaking_states[target_id] = state
                self._overtaking_completion_counts.pop(target_id, None)
                self._overtaking_disengage_counts.pop(target_id, None)
                self._overtaking_entry_tcpa_s.pop(target_id, None)
                self._overtaking_release_reasons[target_id] = "separated_without_pass"
                self._rule_memory.pop((target_id, VOCOLREGSSituation.OT_ing), None)
                self._overtaking_last_target_id = target_id
                if self._overtaking_active_target_id == target_id:
                    self._overtaking_active_target_id = None
        else:
            rearm_candidate = distance >= self._params.overtaking_rearm_distance_m and not risk_eligible
            count = self._overtaking_rearm_counts.get(target_id, 0)
            count = count + 1 if rearm_candidate else 0
            self._overtaking_rearm_counts[target_id] = count
            if count >= self._params.overtaking_confirmation_steps:
                state = OvertakingState.CLEAR
                self._overtaking_states[target_id] = state
                self._overtaking_completion_counts.pop(target_id, None)
                self._overtaking_disengage_counts.pop(target_id, None)
                self._overtaking_rearm_counts.pop(target_id, None)
                self._overtaking_entry_tcpa_s.pop(target_id, None)
                self._overtaking_release_reasons[target_id] = "rearmed"

        self._overtaking_metrics[target_id] = {
            "overtaking_along_track_m": along_track,
            "overtaking_cross_track_m": cross_track,
            "overtaking_relative_speed_mps": relative_speed,
            "overtaking_risk_eligible": risk_eligible,
        }
        return state

    def _select_overtaking_target(self) -> None:
        active = self._overtaking_active_target_id
        if active is not None and self._overtaking_states.get(active) is OvertakingState.COMMITTED:
            driving = self._driving_target_id
            if driving is None or driving == active or self._target_priority(active) <= self._target_priority(driving):
                return
            self._overtaking_active_target_id = None
            return
        committed = [
            target_id
            for target_id, state in self._overtaking_states.items()
            if state is OvertakingState.COMMITTED
        ]
        if not committed:
            self._overtaking_active_target_id = None
            return

        if self._driving_target_id is not None and self._driving_target_id not in committed:
            best_committed = min(committed, key=self._target_priority)
            if self._target_priority(self._driving_target_id) < self._target_priority(best_committed):
                self._overtaking_active_target_id = None
                return

        def priority(target_id: int) -> tuple[int, float, int]:
            tcpa = self._track_metrics.get(target_id, {}).get("rule_tcpa_s")
            if tcpa is not None and tcpa >= 0.0:
                return 0, float(tcpa), target_id
            return 1, float("inf"), target_id

        self._overtaking_active_target_id = min(committed, key=priority)
        self._overtaking_last_target_id = self._overtaking_active_target_id

    def _apply_give_way_commitment(self, candidates: np.ndarray, psi_os: float) -> None:
        was_active = self._give_way_commitment_active
        was_overtaking_active = self._overtaking_commitment_active
        give_way_rules = {
            VOCOLREGSSituation.HO,
            VOCOLREGSSituation.OT_ing,
            VOCOLREGSSituation.CR_SS,
        }
        self._give_way_commitment_rules = {
            rule
            for rules in self._active_rules.values()
            for rule in rules
            if rule in give_way_rules
        }
        self._give_way_commitment_active = bool(self._give_way_commitment_rules)
        self._crossing_commitment_active = VOCOLREGSSituation.CR_SS in self._give_way_commitment_rules
        self._overtaking_commitment_active = bool(
            self._overtaking_active_target_id is not None
            and self._overtaking_states.get(self._overtaking_active_target_id)
            is OvertakingState.COMMITTED
        )
        self._emergency_rule_relaxation = False
        if not self._give_way_commitment_active:
            self._crossing_commitment_frame_heading = None
            self._overtaking_commitment_frame_heading = None
            return

        if self._overtaking_commitment_active:
            if not was_overtaking_active or self._overtaking_commitment_frame_heading is None:
                self._overtaking_commitment_frame_heading = psi_os
            commitment_frame = self._overtaking_commitment_frame_heading
        else:
            self._overtaking_commitment_frame_heading = None
            if not was_active or self._crossing_commitment_frame_heading is None:
                self._crossing_commitment_frame_heading = psi_os
            commitment_frame = self._crossing_commitment_frame_heading
        body_velocities = candidates @ mf.Rmtrx2D(commitment_frame)
        if self._overtaking_commitment_active:
            candidate_progress = np.arctan2(
                np.sin(self._heading_set - commitment_frame),
                np.cos(self._heading_set - commitment_frame),
            )
            minimum_progress = self._params.overtaking_min_starboard_rad
            if was_overtaking_active:
                minimum_progress = max(
                    minimum_progress,
                    float(_wrap_angle(self._selected_heading - commitment_frame)),
                )
            commitment = candidate_progress[None, :] < minimum_progress - 1e-12
            commitment = np.broadcast_to(commitment, self._hard_constraint_mask.shape).copy()
            commitment |= body_velocities[..., 0] <= 0.0
        else:
            commitment = body_velocities[..., 1] < -self._params.crossing_commitment_deadband_mps
            commitment |= body_velocities[..., 0] <= 0.0
            if was_active:
                candidate_progress = np.arctan2(
                    np.sin(self._heading_set - commitment_frame),
                    np.cos(self._heading_set - commitment_frame),
                )
                previous_progress = _wrap_angle(self._selected_heading - commitment_frame)
                commitment |= candidate_progress[None, :] < previous_progress - 1e-12
        admissible_before_commitment = ~self._hard_constraint_mask
        self._crossing_commitment_mask = commitment
        self._hard_constraint_mask |= commitment
        if np.any(~self._hard_constraint_mask) or not np.any(admissible_before_commitment):
            return

        self._hard_constraint_mask = ~admissible_before_commitment
        self._crossing_commitment_mask.fill(False)
        self._emergency_rule_relaxation = True

    def _uncertainty_samples(self) -> np.ndarray:
        vertices = np.asarray(self._params.velocity_uncertainty_vertices_mps, dtype=float)
        if len(vertices) == 1:
            return vertices
        hull = geometry.MultiPoint(vertices).convex_hull
        if not isinstance(hull, geometry.Polygon):
            return np.unique(vertices, axis=0)
        coords = np.asarray(hull.exterior.coords[:-1], dtype=float)
        samples = [np.zeros(2)]
        count = self._params.uncertainty_edge_samples
        for start, end in zip(coords, np.roll(coords, -1, axis=0), strict=True):
            for fraction in np.linspace(0.0, 1.0, count, endpoint=False):
                samples.append(start + fraction * (end - start))
        return np.unique(np.asarray(samples), axis=0)

    def _target_polygon(
        self,
        target_id: int,
        p_do: np.ndarray,
        v_do: np.ndarray,
        length_do: float,
        width_do: float,
    ) -> tuple[geometry.Polygon, float]:
        speed = float(np.linalg.norm(v_do))
        if speed < self._params.colregs_min_target_speed_mps:
            remembered = self._target_heading_memory.get(target_id)
            if remembered is None:
                radius = 0.5 * float(np.hypot(length_do, width_do))
                return geometry.Point(*p_do).buffer(radius, quad_segs=8), 0.0
            psi_do = remembered
        else:
            psi_do = float(np.arctan2(v_do[1], v_do[0]))
        polygon = geometry.box(-length_do / 2.0, -width_do / 2.0, length_do / 2.0, width_do / 2.0)
        polygon = affinity.rotate(polygon, psi_do, origin=(0.0, 0.0), use_radians=True)
        return affinity.translate(polygon, p_do[0], p_do[1]), psi_do

    def _apply_dynamic_hazard(
        self,
        expanded: geometry.Polygon,
        p_os: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
        candidates: np.ndarray,
        uncertainty: np.ndarray,
        rules: set[VOCOLREGSSituation],
        *,
        hard_clearance_domain: geometry.Polygon | None = None,
        preferred_clearance_domain: geometry.Polygon | None = None,
    ) -> None:
        self._ensure_grid_shape()
        if hard_clearance_domain is None:
            self._apply_base_vo(expanded, p_os, v_do, candidates, uncertainty=None)
        else:
            self._apply_engineering_clearance_domains(
                hard_clearance_domain,
                preferred_clearance_domain,
                p_os,
                p_do,
                v_do,
                candidates,
            )

        if not (
            len(uncertainty) == 1 and np.allclose(uncertainty[0], 0.0)
        ):
            cone_radius = 4.0 * (
                self._params.speed_set_limits[1]
                + float(np.linalg.norm(v_do))
                + float(np.max(np.linalg.norm(uncertainty, axis=1)))
                + 1.0
            )
            velocity_obstacle = _truncated_velocity_obstacle(
                expanded,
                p_os,
                v_do,
                cone_radius,
            )
            uncertainty_hull = geometry.MultiPoint(uncertainty).convex_hull
            wvo_polygon = _minkowski_from_geometries(velocity_obstacle, uncertainty_hull)
            wvo = _points_in_convex_geometry(candidates, wvo_polygon)
            relative_candidates = (
                candidates[None, ...]
                - (v_do[None, :] + uncertainty)[:, None, None, :]
            )
            worst_ttc = np.min(
                ray_polygon_ttc_grid(expanded, p_os, relative_candidates),
                axis=0,
            )
            self._wvo_mask |= wvo & ~self._hard_constraint_mask
            self._min_ttc = np.minimum(self._min_ttc, worst_ttc)
        if rules.intersection(
            {VOCOLREGSSituation.HO, VOCOLREGSSituation.OT_ing, VOCOLREGSSituation.CR_SS}
        ):
            rel_position = p_do - p_os
            v1 = self._colregs_v1_mask(rel_position, candidates, v_do, uncertainty)
            self._colregs_v1_mask_grid |= v1
            self._hard_constraint_mask |= v1
        self._violation_costs[self._hard_constraint_mask] = np.inf
        self._violation_costs[self._wvo_mask & ~self._hard_constraint_mask] = 1.0

    def _apply_engineering_clearance_domains(
        self,
        hard_domain: geometry.Polygon,
        preferred_domain: geometry.Polygon | None,
        p_os: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
        candidates: np.ndarray,
    ) -> None:
        relative_position = p_do - p_os
        nominal_ttc = ray_polygon_ttc_grid(hard_domain, p_os, candidates - v_do)
        if hard_domain.covers(geometry.Point(*p_os)):
            relative_velocity = candidates - v_do
            nominal_hard = (
                np.einsum("...i,i->...", relative_velocity, relative_position) >= 0.0
            )
            nominal_ttc = np.full(self._min_ttc.shape, np.inf)
            nominal_ttc[nominal_hard] = 0.0
        else:
            nominal_hard = np.isfinite(nominal_ttc) & (
                nominal_ttc <= self._params.t_max
            )
            nominal_ttc = np.where(nominal_hard, nominal_ttc, np.inf)
        self._base_vo_mask |= nominal_hard
        self._hard_constraint_mask |= nominal_hard
        self._min_ttc = np.minimum(self._min_ttc, nominal_ttc)

        if preferred_domain is None:
            return
        if preferred_domain.covers(geometry.Point(*p_os)):
            relative_velocity = candidates - v_do
            preferred = (
                np.einsum("...i,i->...", relative_velocity, relative_position) >= 0.0
            )
            preferred_ttc = np.full(self._min_ttc.shape, np.inf)
            preferred_ttc[preferred] = 0.0
        else:
            preferred_ttc = ray_polygon_ttc_grid(
                preferred_domain,
                p_os,
                candidates - v_do,
            )
            preferred = np.isfinite(preferred_ttc) & (
                preferred_ttc <= self._params.t_max
            )
            preferred_ttc = np.where(preferred, preferred_ttc, np.inf)
        self._preferred_clearance_mask |= preferred
        self._preferred_clearance_ttc = np.minimum(
            self._preferred_clearance_ttc,
            preferred_ttc,
        )

    def _apply_base_vo(
        self,
        expanded: geometry.Polygon,
        p_os: np.ndarray,
        obstacle_velocity: np.ndarray,
        candidates: np.ndarray,
        uncertainty: np.ndarray | None,
    ) -> None:
        del uncertainty
        ttc = ray_polygon_ttc_grid(expanded, p_os, candidates - obstacle_velocity)
        base_vo = np.isfinite(ttc)
        self._base_vo_mask |= base_vo
        self._hard_constraint_mask |= base_vo
        self._min_ttc = np.minimum(self._min_ttc, ttc)

    @staticmethod
    def _colregs_v1_mask(
        rel_position: np.ndarray,
        candidates: np.ndarray,
        v_do: np.ndarray,
        uncertainty: np.ndarray,
    ) -> np.ndarray:
        v1, _v2, _v3 = VO._colregs_velocity_regions(
            rel_position,
            candidates,
            v_do,
            uncertainty,
        )
        return v1

    @staticmethod
    def _colregs_velocity_regions(
        rel_position: np.ndarray,
        candidates: np.ndarray,
        v_do: np.ndarray,
        uncertainty: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rel_velocity = (
            candidates[None, ...]
            - (v_do[None, :] + uncertainty)[:, None, None, :]
        )
        separating = np.einsum("...i,i->...", rel_velocity, rel_position) < 0.0
        cross_z = (
            rel_position[0] * rel_velocity[..., 1]
            - rel_position[1] * rel_velocity[..., 0]
        )
        v3_for_all = np.all(separating, axis=0)
        v1_for_any = np.any(cross_z < 0.0, axis=0)
        v1 = ~v3_for_all & v1_for_any
        v2 = ~v3_for_all & ~v1_for_any
        return v1, v2, v3_for_all

    def _compute_optimal_controls(  # noqa: PLR0915
        self,
        v_ref: np.ndarray,
        psi_os: float,
    ) -> tuple[float, float]:
        self._ensure_grid_shape()
        candidates = self._candidate_velocities()
        cost_reference = v_ref
        target_id = self._overtaking_active_target_id
        if target_id is not None and self._overtaking_commitment_active:
            target_heading = self._overtaking_target_headings[target_id]
            target_speed = self._overtaking_target_speeds[target_id]
            target_along = np.array([np.cos(target_heading), np.sin(target_heading)])
            progress_speed = max(
                float(np.linalg.norm(v_ref)),
                target_speed + self._params.overtaking_speed_advantage_mps,
            )
            cost_reference = progress_speed * target_along
        elif (
            self._give_way_commitment_active
            and self._crossing_commitment_frame_heading is not None
        ):
            reference_speed = float(np.linalg.norm(v_ref))
            if reference_speed > 1e-12:
                commitment_frame = self._crossing_commitment_frame_heading
                reference_heading = float(np.arctan2(v_ref[1], v_ref[0]))
                reference_progress = _wrap_angle(reference_heading - commitment_frame)
                committed_progress = _wrap_angle(self._selected_heading - commitment_frame)
                if reference_progress < committed_progress:
                    committed_heading = commitment_frame + committed_progress
                    cost_reference = reference_speed * np.array(
                        [np.cos(committed_heading), np.sin(committed_heading)]
                    )
        delta = candidates - cost_reference
        velocity_cost = np.einsum("...i,ij,...j->...", delta, self._params.Q, delta)
        ttc_cost = np.zeros_like(velocity_cost)
        finite_ttc = np.isfinite(self._min_ttc)
        ttc_cost[finite_ttc] = self._params.w_ttc / np.maximum(self._min_ttc[finite_ttc], 1e-9)
        wvo_only = self._wvo_mask & ~self._hard_constraint_mask
        ttc_cost[wvo_only] *= self._params.wvo_ttc_scale
        preferred_clearance_cost = np.zeros_like(velocity_cost)
        preferred = np.isfinite(self._preferred_clearance_ttc)
        preferred_clearance_cost[preferred] = self._params.w_ttc / np.maximum(
            self._preferred_clearance_ttc[preferred],
            1.0,
        )
        self._total_costs = (
            self._params.w_velocity * velocity_cost
            + ttc_cost
            + preferred_clearance_cost
        )
        self._total_costs[self._hard_constraint_mask] = np.inf
        self._overtaking_progress_relaxed = False
        if target_id is not None and self._overtaking_commitment_active:
            projected_speeds = candidates @ target_along
            feasible = np.isfinite(self._total_costs)
            preferred = feasible & (
                projected_speeds
                >= target_speed + self._params.overtaking_speed_advantage_mps
            )
            if np.any(preferred):
                self._total_costs[feasible & ~preferred] = np.inf
            else:
                self._overtaking_progress_relaxed = True

        current_index = self._nearest_velocity_index(self._current_velocity)
        reference_tracking_error = float(np.linalg.norm(self._current_velocity - v_ref))
        driving_metrics = self._track_metrics.get(self._driving_target_id, {})
        driving_rules = set(driving_metrics.get("active_rules", ())) | set(
            driving_metrics.get("effective_matched_rules", ())
        )
        stand_on_responsibility = (
            VOCOLREGSSituation.CR_PS.name in driving_rules
            and (
                self._target_count_current <= 1
                or reference_tracking_error <= self._params.crossing_commitment_deadband_mps
            )
        )
        self._stand_on_emergency_active = bool(driving_metrics.get("stand_on_emergency"))
        self._stand_on_hold_active = bool(
            stand_on_responsibility
            and not self._stand_on_emergency_active
            and not self._base_vo_mask[current_index]
            and not self._hard_constraint_mask[current_index]
        )
        flat_index = (
            int(np.ravel_multi_index(current_index, self._total_costs.shape))
            if self._stand_on_hold_active
            else int(np.argmin(self._total_costs))
        )
        minimum = float(self._total_costs.flat[flat_index])
        self._feasible = bool(np.isfinite(minimum))
        if not self._feasible:
            self._selected_heading = float(psi_os)
            self._selected_speed = 0.0
            self._objective = None
            self._reference_velocity_error_mps = float(np.linalg.norm(v_ref))
            return self._selected_heading, self._selected_speed
        if self._give_way_commitment_active:
            tied = np.flatnonzero(np.isclose(self._total_costs, minimum, rtol=1e-9, atol=1e-9))
            if tied.size > 1:
                headings = self._heading_set[np.unravel_index(tied, self._total_costs.shape)[1]]
                deltas = np.abs(
                    np.arctan2(
                        np.sin(headings - self._selected_heading),
                        np.cos(headings - self._selected_heading),
                    )
                )
                flat_index = int(tied[int(np.argmin(deltas))])
        i_speed, i_heading = np.unravel_index(flat_index, self._total_costs.shape)
        self._selected_heading = float(self._heading_set[i_heading])
        self._selected_speed = float(self._speed_set[i_speed])
        self._objective = minimum
        selected_velocity = self._selected_speed * np.array(
            [np.cos(self._selected_heading), np.sin(self._selected_heading)]
        )
        self._reference_velocity_error_mps = float(np.linalg.norm(selected_velocity - v_ref))
        return self._selected_heading, self._selected_speed

    def _nearest_velocity_index(self, velocity: np.ndarray) -> tuple[int, int]:
        speed = float(np.linalg.norm(velocity))
        heading = float(np.arctan2(velocity[1], velocity[0]))
        speed_index = int(np.argmin(abs(self._speed_set - speed)))
        heading_index = int(
            np.argmin(abs(_wrap_angle_array(self._heading_set - heading)))
        )
        return speed_index, heading_index

    def _precollision_check(
        self,
        p_os: np.ndarray,
        v_os: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
    ) -> bool:
        relative_position = p_do - p_os
        relative_velocity = v_do - v_os
        speed_squared = float(relative_velocity @ relative_velocity)
        if speed_squared <= 1e-12:
            t_cpa = 0.0
            d_cpa = float(np.linalg.norm(relative_position))
        else:
            t_cpa = -float(relative_position @ relative_velocity) / speed_squared
            d_cpa = float(np.linalg.norm(relative_position + t_cpa * relative_velocity))
        return 0.0 <= t_cpa <= self._params.t_max and d_cpa <= self._params.d_min

    @staticmethod
    def _cpa_metrics(
        p_os: np.ndarray,
        v_os: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
    ) -> dict[str, float | None]:
        relative_position = p_do - p_os
        relative_velocity = v_do - v_os
        speed_squared = float(relative_velocity @ relative_velocity)
        if speed_squared <= 1e-12:
            return {
                "tcpa_s": None,
                "dcpa_m": float(np.linalg.norm(relative_position)),
                "center_distance_m": float(np.linalg.norm(relative_position)),
            }
        t_cpa = -float(relative_position @ relative_velocity) / speed_squared
        d_cpa = float(np.linalg.norm(relative_position + t_cpa * relative_velocity))
        return {
            "tcpa_s": t_cpa,
            "dcpa_m": d_cpa,
            "center_distance_m": float(np.linalg.norm(relative_position)),
        }

    def _determine_colregs_rules(
        self,
        p_os: np.ndarray,
        psi_os: float,
        v_os: np.ndarray,
        p_do: np.ndarray,
        v_do: np.ndarray,
    ) -> set[VOCOLREGSSituation]:
        speed_do = float(np.linalg.norm(v_do))
        if speed_do < self._params.colregs_min_target_speed_mps:
            return set()
        psi_do = float(np.arctan2(v_do[1], v_do[0]))
        relative_body = mf.Rmtrx2D(psi_os).T @ (p_do - p_os)
        longitudinal, lateral = map(float, relative_body)
        heading_delta = _wrap_angle(psi_do - psi_os)
        bearing = float(np.arctan2(lateral, longitudinal))
        p = self._params
        rules: set[VOCOLREGSSituation] = set()

        same_course = abs(heading_delta) <= p.rule_heading_tolerance_rad
        opposite_course = abs(abs(heading_delta) - np.pi) <= p.rule_heading_tolerance_rad
        in_track_corridor = abs(lateral) <= p.rule_cross_track_max_m
        cpa = self._cpa_metrics(p_os, v_os, p_do, v_do)
        collision_course = bool(
            cpa["tcpa_s"] is not None
            and cpa["tcpa_s"] >= 0.0
            and cpa["dcpa_m"] <= p.d_min
        )
        if (
            opposite_course
            and (in_track_corridor or collision_course)
            and longitudinal >= p.rule_along_track_min_m
        ):
            rules.add(VOCOLREGSSituation.HO)
        if same_course and in_track_corridor:
            if longitudinal >= p.rule_along_track_min_m:
                rules.add(VOCOLREGSSituation.OT_ing)
            elif longitudinal <= -p.rule_along_track_min_m:
                rules.add(VOCOLREGSSituation.OT_en)

        abs_heading_delta = abs(heading_delta)
        tolerance = 1e-12
        crossing_heading = (
            p.rule_crossing_heading_min_rad - tolerance
            <= abs_heading_delta
            <= p.rule_crossing_heading_max_rad + tolerance
        )
        starboard_bearing = p.rule_bearing_min_rad <= bearing <= p.rule_bearing_max_rad
        port_bearing = -p.rule_bearing_max_rad <= bearing <= -p.rule_bearing_min_rad
        heading_bearing_condition = heading_delta >= bearing - np.pi - tolerance
        if (
            crossing_heading
            and starboard_bearing
            and lateral >= p.rule_cross_track_min_m
            and heading_bearing_condition
        ):
            rules.add(VOCOLREGSSituation.CR_SS)
        if (
            crossing_heading
            and port_bearing
            and lateral <= -p.rule_cross_track_min_m
        ):
            rules.add(VOCOLREGSSituation.CR_PS)
        return rules

    def _update_colregs_rules(
        self,
        id_do: int,
        matched: set[VOCOLREGSSituation],
        eligible: bool,
    ) -> set[VOCOLREGSSituation]:
        matched = matched if eligible else set()
        active: set[VOCOLREGSSituation] = set()
        for rule in VOCOLREGSSituation:
            key = (id_do, rule)
            if rule in matched:
                self._rule_memory[key] = 0
                active.add(rule)
                continue
            if key not in self._rule_memory:
                continue
            misses = self._rule_memory[key] + 1
            if misses >= self._params.colregs_hysteresis_steps:
                del self._rule_memory[key]
            else:
                self._rule_memory[key] = misses
                active.add(rule)
        self._active_rules[id_do] = active
        return active

    def _expire_missing_targets(self, seen: set[int]) -> None:
        missing = {target_id for target_id, _rule in self._rule_memory if target_id not in seen}
        missing.update(target_id for target_id in self._give_way_rule_locks if target_id not in seen)
        missing.update(target_id for target_id in self._overtaking_states if target_id not in seen)
        self._expired_target_ids_last_solve = sorted(missing)
        for target_id in missing:
            for key in [key for key in self._rule_memory if key[0] == target_id]:
                del self._rule_memory[key]
            self._active_rules.pop(target_id, None)
            self._completed_crossing_targets.discard(target_id)
            self._crossing_completion_counts.pop(target_id, None)
            self._crossing_previous_distances.pop(target_id, None)
            self._give_way_rule_locks.pop(target_id, None)
            self._give_way_release_counts.pop(target_id, None)
            self._give_way_previous_distances.pop(target_id, None)
            self._completed_give_way_targets.discard(target_id)
            self._give_way_rearm_counts.pop(target_id, None)
            self._overtaking_states.pop(target_id, None)
            self._overtaking_completion_counts.pop(target_id, None)
            self._overtaking_disengage_counts.pop(target_id, None)
            self._overtaking_rearm_counts.pop(target_id, None)
            self._overtaking_release_reasons.pop(target_id, None)
            self._overtaking_entry_tcpa_s.pop(target_id, None)
            self._overtaking_target_headings.pop(target_id, None)
            self._overtaking_target_speeds.pop(target_id, None)
            self._overtaking_metrics.pop(target_id, None)
            if self._overtaking_active_target_id == target_id:
                self._overtaking_active_target_id = None
            if self._overtaking_last_target_id == target_id:
                self._overtaking_last_target_id = None
            if self._driving_target_id == target_id:
                self._driving_target_id = None
                self._driving_rule = None

    def _determine_colregs_situation(
        self,
        p_os: np.ndarray,
        psi_os: float,
        p_do: np.ndarray,
        psi_do: float,
    ) -> VOCOLREGSSituation:
        """Compatibility helper returning one role for legacy callers."""
        body = mf.Rmtrx2D(psi_os).T @ (p_do - p_os)
        heading_delta = _wrap_angle(psi_do - psi_os)
        if abs(abs(heading_delta) - np.pi) <= self._params.rule_heading_tolerance_rad:
            return VOCOLREGSSituation.HO
        if abs(heading_delta) <= self._params.rule_heading_tolerance_rad:
            return VOCOLREGSSituation.OT_ing if body[0] >= 0.0 else VOCOLREGSSituation.OT_en
        return VOCOLREGSSituation.CR_SS if body[1] >= 0.0 else VOCOLREGSSituation.CR_PS

    def _update_violation_costs(
        self,
        situation: VOCOLREGSSituation,
        expanded_poly_do: geometry.Polygon,
        expanded_poly_do_buffered: geometry.Polygon,
        p_do: np.ndarray,
        v_do: np.ndarray,
        p_os: np.ndarray,
        v_os: np.ndarray,
        psi_os: float,
        enc: ENC | None = None,
        show_debug_plots: bool = False,
        poly_do: geometry.Polygon | None = None,
        poly_os: geometry.Polygon | None = None,
    ) -> None:
        """Legacy test hook mapped onto the hard-constraint implementation."""
        del expanded_poly_do_buffered, v_os, psi_os, enc, show_debug_plots, poly_do, poly_os
        candidates = self._candidate_velocities()
        self._apply_dynamic_hazard(
            expanded_poly_do,
            p_os,
            p_do,
            v_do,
            candidates,
            np.zeros((1, 2)),
            {situation},
        )

    def _compute_expanded_do_polygon(
        self,
        poly_os: geometry.Polygon,
        poly_do: geometry.Polygon,
    ) -> tuple[geometry.Polygon, geometry.Polygon]:
        expanded = compute_minkowski_sum(poly_do, compute_reflection(poly_os))
        return expanded, expanded

    def _check_if_ray_intersects_vo(
        self,
        vo: geometry.Polygon,
        p_os: np.ndarray,
        v_os: np.ndarray,
    ) -> bool:
        return bool(np.isfinite(ray_polygon_ttc_grid(vo, p_os, np.asarray(v_os).reshape(1, 1, 2))[0, 0]))

    def _extract_static_hazards(
        self,
        enc: ENC | None,
        p_os_ne: np.ndarray,
        poly_os_ne: geometry.Polygon,
    ) -> list[geometry.Polygon]:
        if enc is None:
            return []
        query_center_en = geometry.Point(float(p_os_ne[1]), float(p_os_ne[0]))
        query_area_en = query_center_en.buffer(self._params.static_query_range_m)
        attribute_by_layer = {
            "LAND": "land",
            "SHORE": "shore",
            "OBSTRN": "obstrn",
            "UWTROC": "uwtroc",
        }
        expanded: list[geometry.Polygon] = []
        reflected = compute_reflection(poly_os_ne)
        for layer_id in self._params.static_hazard_layers:
            attribute = attribute_by_layer.get(layer_id)
            if attribute is None:
                continue
            source = getattr(enc, attribute, None)
            source_geometry = getattr(source, "geometry", None)
            if not isinstance(source_geometry, BaseGeometry) or source_geometry.is_empty:
                continue
            clipped_en = source_geometry.intersection(query_area_en)
            if clipped_en.is_empty:
                continue
            clipped_ne = ops.transform(lambda x, y, *_z: (y, x), clipped_en)
            for polygon in _polygon_parts(clipped_ne):
                # Downstream TTC convexifies every connected obstacle, so
                # triangulating the same polygon first is redundant.
                expanded.append(compute_minkowski_sum(polygon, reflected))
        merged = ops.unary_union(expanded) if expanded else geometry.GeometryCollection()
        return sorted(
            _polygon_parts(merged),
            key=lambda poly: tuple(round(value, 9) for value in poly.bounds),
        )

    def get_debug_data(self) -> dict[str, Any]:
        active_rules = {
            str(target_id): [rule.name for rule in sorted(rules, key=lambda item: item.value)]
            for target_id, rules in sorted(self._active_rules.items())
            if rules
        }
        finite_ttc = self._min_ttc[np.isfinite(self._min_ttc) & ~self._hard_constraint_mask]
        speed_index = int(np.argmin(abs(self._speed_set - self._selected_speed)))
        heading_index = int(np.argmin(abs(self._heading_set - self._selected_heading)))
        current_speed_index, current_heading_index = self._nearest_velocity_index(
            self._current_velocity
        )
        selected_ttc = self._min_ttc[speed_index, heading_index]
        overtaking_target_id = self._overtaking_active_target_id
        if overtaking_target_id is None:
            overtaking_target_id = self._overtaking_last_target_id
        overtaking_state = self._overtaking_states.get(
            overtaking_target_id,
            OvertakingState.CLEAR,
        )
        overtaking_metrics = self._overtaking_metrics.get(overtaking_target_id, {})
        overtaking_release_count = (
            max(
                self._overtaking_completion_counts.get(overtaking_target_id, 0),
                self._overtaking_disengage_counts.get(overtaking_target_id, 0),
            )
            if overtaking_state is OvertakingState.COMMITTED
            else self._overtaking_rearm_counts.get(overtaking_target_id, 0)
        )
        return {
            "reconstruction_label": self._params.reconstruction_label,
            "feasible": self._feasible,
            "fallback": None if self._feasible else "stop_nonpaper_wrapper",
            "fallback_reason": None if self._feasible else "all_velocity_grid_candidates_inadmissible",
            "objective": self._objective,
            "selected_heading_rad": self._selected_heading,
            "selected_speed_mps": self._selected_speed,
            "dynamic_hazard_count": self._dynamic_hazard_count,
            "static_hazard_count": self._static_hazard_count,
            "active_rules": active_rules,
            "track_metrics": self._track_metrics,
            "base_vo_count": int(np.count_nonzero(self._base_vo_mask)),
            "colregs_v1_count": int(np.count_nonzero(self._colregs_v1_mask_grid)),
            "crossing_commitment_count": (
                int(np.count_nonzero(self._crossing_commitment_mask))
                if self._crossing_commitment_active
                else 0
            ),
            "give_way_commitment_count": int(np.count_nonzero(self._crossing_commitment_mask)),
            "hard_constraint_count": int(np.count_nonzero(self._hard_constraint_mask)),
            "wvo_only_count": int(np.count_nonzero(self._wvo_mask & ~self._hard_constraint_mask)),
            "preferred_clearance_count": int(
                np.count_nonzero(
                    self._preferred_clearance_mask & ~self._hard_constraint_mask
                )
            ),
            "feasible_candidate_count": int(np.count_nonzero(~self._hard_constraint_mask)),
            "selected_in_base_vo": bool(self._base_vo_mask[speed_index, heading_index]),
            "selected_in_colregs_v1": bool(self._colregs_v1_mask_grid[speed_index, heading_index]),
            "current_in_base_vo": bool(
                self._base_vo_mask[current_speed_index, current_heading_index]
            ),
            "stand_on_hold_active": self._stand_on_hold_active,
            "stand_on_emergency_active": self._stand_on_emergency_active,
            "driving_target_id": self._driving_target_id,
            "driving_rule": self._driving_rule,
            "expired_target_ids": self._expired_target_ids_last_solve,
            "selected_in_wvo_only": bool(
                self._wvo_mask[speed_index, heading_index]
                and not self._hard_constraint_mask[speed_index, heading_index]
            ),
            "selected_in_preferred_clearance": bool(
                self._preferred_clearance_mask[speed_index, heading_index]
                and not self._hard_constraint_mask[speed_index, heading_index]
            ),
            "hard_hull_clearance_m": self._params.hard_hull_clearance_m,
            "preferred_hull_clearance_m": self._params.preferred_hull_clearance_m,
            "ownship_length_m": self._ownship_length_m,
            "ownship_width_m": self._ownship_width_m,
            "dynamics_prediction_active": self._dynamics_prediction_active,
            "selected_ttc_s": float(selected_ttc) if np.isfinite(selected_ttc) else None,
            "reference_velocity_error_mps": self._reference_velocity_error_mps,
            "minimum_feasible_ttc_s": float(np.min(finite_ttc)) if finite_ttc.size else None,
            "grid_shape": [len(self._speed_set), len(self._heading_set)],
            "solve_period_s": 1.0 / self._params.planning_frequency,
            "crossing_commitment_active": self._crossing_commitment_active,
            "crossing_commitment_state": (
                "CR_SS_COMMITTED" if self._crossing_commitment_active else "CLEAR"
            ),
            "give_way_commitment_active": self._give_way_commitment_active,
            "give_way_commitment_rules": [
                rule.name for rule in sorted(self._give_way_commitment_rules, key=lambda item: item.value)
            ],
            "give_way_commitment_state": self._give_way_commitment_state(),
            "give_way_rule_locks": {
                str(target_id): rule.name
                for target_id, rule in sorted(self._give_way_rule_locks.items())
            },
            "completed_give_way_targets": sorted(self._completed_give_way_targets),
            "emergency_rule_relaxation": self._emergency_rule_relaxation,
            "overtaking_state": overtaking_state.value,
            "overtaking_target_id": overtaking_target_id,
            "overtaking_along_track_m": overtaking_metrics.get("overtaking_along_track_m"),
            "overtaking_cross_track_m": overtaking_metrics.get("overtaking_cross_track_m"),
            "overtaking_relative_speed_mps": overtaking_metrics.get(
                "overtaking_relative_speed_mps"
            ),
            "overtaking_progress_relaxed": self._overtaking_progress_relaxed,
            "overtaking_release_count": overtaking_release_count,
            "overtaking_release_reason": self._overtaking_release_reasons.get(
                overtaking_target_id
            ),
            "overtaking_entry_tcpa_s": self._overtaking_entry_tcpa_s.get(
                overtaking_target_id
            ),
        }

    def _give_way_commitment_state(self) -> str:
        if not self._give_way_commitment_rules:
            return "CLEAR"
        names = [
            rule.name for rule in sorted(self._give_way_commitment_rules, key=lambda item: item.value)
        ]
        return f"{'+'.join(names)}_COMMITTED"

    def get_decision_space_snapshot(self) -> dict[str, Any] | None:
        if not self._initialized:
            return None

        state_bits = (
            self._base_vo_mask.astype(np.uint8)
            | (self._wvo_mask.astype(np.uint8) << 1)
            | (self._colregs_v1_mask_grid.astype(np.uint8) << 2)
            | (self._crossing_commitment_mask.astype(np.uint8) << 3)
        )
        speed_index = int(np.argmin(abs(self._speed_set - self._selected_speed)))
        heading_index = int(np.argmin(abs(self._heading_set - self._selected_heading)))
        total_costs = [
            float(value) if np.isfinite(value) else None for value in self._total_costs.ravel()
        ]
        minimum_ttc = [
            float(value) if np.isfinite(value) else None for value in self._min_ttc.ravel()
        ]
        return {
            "schema": "vo_velocity_space.v1",
            "shape": [len(self._speed_set), len(self._heading_set)],
            "coordinate_frame": "earth_fixed_ne",
            "ownship_heading_rad": self._ownship_heading,
            "speed_candidates_mps": self._speed_set.tolist(),
            "heading_candidates_rad": self._heading_set.tolist(),
            "reference_velocity_ne_mps": self._reference_velocity.tolist(),
            "current_velocity_ne_mps": self._current_velocity.tolist(),
            "selected": {
                "speed_index": speed_index,
                "heading_index": heading_index,
                "speed_mps": self._selected_speed,
                "heading_rad": self._selected_heading,
                "total_cost": self._objective,
                "ttc_s": minimum_ttc[speed_index * len(self._heading_set) + heading_index],
            },
            "candidate_state_bits": state_bits.ravel().tolist(),
            "total_costs": total_costs,
            "minimum_ttc_s": minimum_ttc,
            "active_rules": self.get_debug_data()["active_rules"],
            "track_metrics": self._track_metrics,
            "crossing_commitment_active": self._crossing_commitment_active,
            "crossing_commitment_state": (
                "CR_SS_COMMITTED" if self._crossing_commitment_active else "CLEAR"
            ),
            "give_way_commitment_active": self._give_way_commitment_active,
            "give_way_commitment_rules": [
                rule.name for rule in sorted(self._give_way_commitment_rules, key=lambda item: item.value)
            ],
            "give_way_commitment_state": self._give_way_commitment_state(),
            "emergency_rule_relaxation": self._emergency_rule_relaxation,
        }

    def plot_current_velocity_grid(
        self,
        fig: plt.Figure,
        ax: plt.Axes,
        psi_os: float,
    ) -> list:
        del fig, psi_os
        candidates = self._candidate_velocities()
        colors = np.where(self._hard_constraint_mask, "tab:red", np.where(self._wvo_mask, "tab:orange", "tab:green"))
        handle = ax.scatter(candidates[..., 0], candidates[..., 1], c=colors.ravel(), s=4)
        return [handle]


def ray_polygon_ttc_grid(
    polygon: geometry.Polygon,
    origin: np.ndarray,
    velocities: np.ndarray,
) -> np.ndarray:
    """Return first-hit TTC for a convex polygon and a grid of ray velocities."""
    polygon = polygon.convex_hull
    if polygon.is_empty:
        return np.full(velocities.shape[:-1], np.inf)
    oriented = geometry.polygon.orient(polygon, sign=1.0)
    vertices = np.asarray(oriented.exterior.coords[:-1], dtype=float)
    flat = np.asarray(velocities, dtype=float).reshape(-1, 2)
    enter = np.zeros(len(flat))
    leave = np.full(len(flat), np.inf)
    valid = np.ones(len(flat), dtype=bool)
    for start, end in zip(vertices, np.roll(vertices, -1, axis=0), strict=True):
        edge = end - start
        outward = np.array([edge[1], -edge[0]])
        a = flat @ outward
        b = float((start - origin) @ outward)
        parallel = np.isclose(a, 0.0, atol=1e-12)
        valid &= ~(parallel & (b < 0.0))
        upper = a > 1e-12
        lower = a < -1e-12
        leave[upper] = np.minimum(leave[upper], b / a[upper])
        enter[lower] = np.maximum(enter[lower], b / a[lower])
    valid &= leave >= np.maximum(enter, 0.0)
    speed_zero = np.linalg.norm(flat, axis=1) <= 1e-12
    inside = polygon.covers(geometry.Point(float(origin[0]), float(origin[1])))
    valid[speed_zero] = inside
    enter[speed_zero & inside] = 0.0
    ttc = np.full(len(flat), np.inf)
    ttc[valid] = np.maximum(enter[valid], 0.0)
    return ttc.reshape(velocities.shape[:-1])


def compute_minkowski_sum(poly1: geometry.Polygon, poly2: geometry.Polygon) -> geometry.Polygon:
    """Compute convex polygon Minkowski sum."""
    points1 = np.asarray(poly1.convex_hull.exterior.coords[:-1], dtype=float)
    points2 = np.asarray(poly2.convex_hull.exterior.coords[:-1], dtype=float)
    sums = (points1[:, None, :] + points2[None, :, :]).reshape(-1, 2)
    return geometry.MultiPoint(sums).convex_hull


def _minkowski_from_geometries(first: BaseGeometry, second: BaseGeometry) -> BaseGeometry:
    first_points = _geometry_coordinates(first)
    second_points = _geometry_coordinates(second)
    sums = (first_points[:, None, :] + second_points[None, :, :]).reshape(-1, 2)
    return geometry.MultiPoint(sums).convex_hull


def _geometry_coordinates(value: BaseGeometry) -> np.ndarray:
    if isinstance(value, geometry.Point):
        return np.asarray(value.coords, dtype=float)
    if isinstance(value, geometry.LineString):
        return np.asarray(value.coords, dtype=float)
    if isinstance(value, geometry.Polygon):
        return np.asarray(value.exterior.coords[:-1], dtype=float)
    return np.vstack([_geometry_coordinates(item) for item in value.geoms])


def _truncated_velocity_obstacle(
    expanded_spatial_obstacle: geometry.Polygon,
    origin: np.ndarray,
    apex: np.ndarray,
    radius: float,
) -> geometry.Polygon:
    if expanded_spatial_obstacle.covers(geometry.Point(*origin)):
        return geometry.Point(*apex).buffer(radius)
    relative = np.asarray(expanded_spatial_obstacle.convex_hull.exterior.coords[:-1]) - origin
    angles = np.sort(np.arctan2(relative[:, 1], relative[:, 0]))
    wrapped = np.r_[angles, angles[0] + 2.0 * np.pi]
    gap_index = int(np.argmax(np.diff(wrapped)))
    start = wrapped[gap_index + 1]
    end = wrapped[gap_index] + 2.0 * np.pi
    first = apex + radius * np.array([np.cos(start), np.sin(start)])
    second = apex + radius * np.array([np.cos(end), np.sin(end)])
    return geometry.Polygon([apex, first, second]).convex_hull


def _points_in_convex_geometry(points: np.ndarray, value: BaseGeometry) -> np.ndarray:
    flat = points.reshape(-1, 2)
    if isinstance(value, geometry.Point):
        result = np.linalg.norm(flat - np.asarray(value.coords[0]), axis=1) <= 1e-12
    elif isinstance(value, geometry.LineString):
        start, end = np.asarray(value.coords[0]), np.asarray(value.coords[-1])
        segment = end - start
        length_squared = float(segment @ segment)
        if length_squared <= 1e-12:
            result = np.linalg.norm(flat - start, axis=1) <= 1e-12
        else:
            parameter = np.clip(((flat - start) @ segment) / length_squared, 0.0, 1.0)
            projection = start + parameter[:, None] * segment
            result = np.linalg.norm(flat - projection, axis=1) <= 1e-12
    else:
        polygon = geometry.polygon.orient(value.convex_hull, sign=1.0)
        vertices = np.asarray(polygon.exterior.coords[:-1], dtype=float)
        result = np.ones(len(flat), dtype=bool)
        for start, end in zip(vertices, np.roll(vertices, -1, axis=0), strict=True):
            edge = end - start
            outward = np.array([edge[1], -edge[0]])
            result &= (flat - start) @ outward <= 1e-10
    return result.reshape(points.shape[:-1])


def compute_minowski_sum(poly1: geometry.Polygon, poly2: geometry.Polygon) -> geometry.Polygon:
    """Backward-compatible alias for the historical misspelling."""
    return compute_minkowski_sum(poly1, poly2)


def compute_reflection(poly: geometry.Polygon) -> geometry.Polygon:
    """Reflect a footprint about the reference point at the origin."""
    return affinity.scale(poly, xfact=-1.0, yfact=-1.0, origin=(0.0, 0.0))


def _wrap_angle(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _wrap_angle_array(angle: np.ndarray) -> np.ndarray:
    return (angle + np.pi) % (2.0 * np.pi) - np.pi


def _polygon_parts(value: BaseGeometry) -> Iterable[geometry.Polygon]:
    if isinstance(value, geometry.Polygon):
        yield value
    elif isinstance(value, geometry.MultiPolygon):
        yield from value.geoms
    elif isinstance(value, geometry.GeometryCollection):
        for item in value.geoms:
            yield from _polygon_parts(item)


def plot_vo_situation(
    expanded_poly_do: geometry.Polygon,
    expanded_poly_do_buffered: geometry.Polygon,
    poly_os: geometry.Polygon,
    v_os: np.ndarray,
    poly_do: geometry.Polygon,
    v_do: np.ndarray,
    fig: plt.Figure | None = None,
    ax: plt.Axes | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot spatial VO construction for debugging."""
    if fig is None or ax is None:
        fig, ax = plt.subplots()
    for polygon, color, label in (
        (poly_os, "tab:blue", "ownship"),
        (poly_do, "tab:red", "target"),
        (expanded_poly_do, "tab:orange", "expanded target"),
    ):
        x, y = polygon.exterior.xy
        ax.plot(x, y, color=color, label=label)
    if not expanded_poly_do_buffered.equals(expanded_poly_do):
        x, y = expanded_poly_do_buffered.exterior.xy
        ax.plot(x, y, color="tab:purple", label="uncertainty envelope")
    origin = np.asarray(poly_os.centroid.coords[0])
    ax.quiver(*origin, *v_os, color="tab:blue")
    ax.quiver(*np.asarray(poly_do.centroid.coords[0]), *v_do, color="tab:red")
    ax.axis("equal")
    ax.legend()
    return fig, ax
