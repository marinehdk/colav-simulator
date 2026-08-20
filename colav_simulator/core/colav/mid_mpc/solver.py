"""CasADi 3.7.2 IPOPT implementation of the frozen MASS-L3 Mid-MPC NLP."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from enum import IntEnum
from typing import cast

import casadi as ca
import numpy as np

from colav_simulator.core.colav.mid_mpc.models import (
    MidMpcConfig,
    MidMpcHardWindow,
    MidMpcObjectiveComponents,
    MidMpcOwnShip,
    MidMpcPreparedProblem,
    MidMpcPrimalWarmStart,
    MidMpcProblem,
    MidMpcResult,
    MidMpcRouteFrame,
    MidMpcRouteObjective,
    MidMpcRowLayout,
    MidMpcRowSpan,
    MidMpcStatus,
    MidMpcTarget,
    MidMpcTrajectoryPoint,
)

_TARGET_STRIDE = 5
_FROZEN_PREFIX_CAPACITY = 18
# IPOPT's first target-free interior iterate may temporarily raise the tiny mission objective.
_TARGET_FREE_OBJECTIVE_CEILING = 0.03
_TARGET_FREE_RELATIVE_REGRESSION = 0.05


class _P(IntEnum):
    PSI0 = 0
    U0 = 1
    X0 = 2
    Y0 = 3
    ROUTE_BEARING = 4
    PLANNED_SPEED = 5
    CPA_SAFE = 10
    ROT_MAX = 11
    OWN_PSI = 12
    ASYMMETRY_ACTIVE = 13
    ROUTE_ORIGIN_X = 14
    ROUTE_ORIGIN_Y = 15
    ROUTE_NORMAL_X = 16
    ROUTE_NORMAL_Y = 17
    LATERAL_SCALE = 19
    ROUTE_WEIGHT = 20
    PREFIX_ACTIVE_K = 21
    PREFERRED_SIDE = 22
    MIN_ALTERATION = 23
    LATERAL_ACTIVE = 24
    DECEL_MAX = 25
    PREFIX_PSI = 26


class _T(IntEnum):
    X = 0
    Y = 1
    COG = 2
    SOG = 3
    WEIGHT = 4


class MidMpcIpoptSolver:
    """Pure Mid-MPC optimizer with no sensing, encounter, or route policy."""

    def __init__(self, config: MidMpcConfig = MidMpcConfig()) -> None:
        self._config = config
        self._graph_cache: dict[tuple[bool, int | None, float | None], _Graph] = {}

    def prewarm(self) -> None:
        """Build the capacity-one strict graph so the first tick pays no JIT stall."""
        self.prewarm_capacity(1)

    def prewarm_capacity(self, target_capacity: int) -> None:
        """Build one strict graph at a scenario's full target capacity.

        The nlpsol construction for a ten-target graph costs seconds inside
        the first solve's deadline; a scenario-level capacity hint lets the
        first multiship cycle hit the graph cache instead, and the single
        graph also serves every smaller track count for the whole session.
        """
        if not self._config.strict_slack_bounds:
            return
        capacity = max(1, min(int(target_capacity), self._config.max_targets))
        graph_key = (True, None, None)
        cached = self._graph_cache.get(graph_key)
        if cached is not None and cached.target_capacity >= capacity and cached.audit_capacity >= capacity:
            return
        n = self._config.horizon_steps
        shell = MidMpcProblem(
            own_ship=MidMpcOwnShip(psi_rad=0.0, u_mps=5.0, x_m=0.0, y_m=0.0),
            route_bearing_rad=0.0,
            planned_speed_mps=5.0,
            heading_bounds_rad=(-1.0, 1.0),
            speed_bounds_mps=(0.0, 8.0),
            cpa_safe_m=150.0,
            cpa_hard_m=50.0,
            rot_max_rad_s=0.05,
            decel_max_mps2=0.3,
            lateral_active=False,
            preferred_side=1,
            starboard_asymmetry_active=False,
            min_alteration_rad=0.0,
            route_frame=MidMpcRouteFrame(
                origin_m=(0.0, 0.0),
                normal=(0.0, 1.0),
                bearing_rad=0.0,
                lateral_scale_m=1000.0,
                weight=1.0,
            ),
            route_objective=MidMpcRouteObjective(
                mission_bearing_rad=0.0,
                avoidance_corridor_bearing_rad=0.0,
                heading_reference_rad=(0.0,) * n,
                lateral_reference_m=(0.0,) * n,
                avoidance_active_until_k=0,
            ),
            targets=(MidMpcTarget(x_m=1.0e6, y_m=1.0e6, cog_rad=0.0, sog_mps=0.0),) * capacity,
            audit_row_count=capacity,
        )
        self._graph_cache[graph_key] = _build_graph(self._config, shell)

    def solve(  # noqa: PLR0915 - keeps one solver call and its evidence atomic
        self,
        problem: MidMpcProblem,
        *,
        primal_warm_start: MidMpcPrimalWarmStart | None = None,
        wall_time_s: float | None = None,
    ) -> MidMpcResult:
        _validate_target_capacity(problem, self._config.max_targets)
        _validate_route_objective(problem, self._config.horizon_steps)
        started_at = time.perf_counter()
        graph_key = (
            problem.route_objective is not None,
            None if self._config.strict_slack_bounds else min(problem.prefix_active_k, self._config.horizon_steps),
            None if self._config.strict_slack_bounds else problem.cpa_hard_m,
        )
        graph = self._graph_cache.get(graph_key)
        graph_cache_hit = bool(
            graph is not None
            and graph.target_capacity >= len(problem.targets)
            and graph.audit_capacity >= problem.audit_row_count
        )
        if not graph_cache_hit:
            graph_build_started = time.perf_counter()
            graph = _build_graph(self._config, problem)
            self._graph_cache[graph_key] = graph
            graph_build_elapsed_ms = (time.perf_counter() - graph_build_started) * 1_000.0
        else:
            graph_build_elapsed_ms = 0.0
        if graph is None:
            raise RuntimeError("Mid-MPC graph cache resolution failed")
        preparation_started = time.perf_counter()
        prepared = _prepare(self._config, problem, graph.row_layout)
        if primal_warm_start is not None:
            reuse_stop_k = (
                self._config.horizon_steps
                if problem.route_objective is None
                else problem.route_objective.avoidance_active_until_k
            )
            prepared = _apply_primal_warm_start(
                prepared,
                primal_warm_start,
                self._config,
                reuse_stop_k=reuse_stop_k,
            )
        if self._config.strict_slack_bounds and problem.targets and primal_warm_start is None:
            # Cold seeds only: a warm-started rolling projection that sits on
            # hard rows mid-encounter carries accepted plan geometry that a
            # uniform offset ramp would discard.
            repaired = _repair_infeasible_seed(graph, prepared, problem, self._config)
            if repaired is not None:
                prepared = repaired
        seed_components = _flat(graph.objective_components(prepared.x0, prepared.p))
        seed_objective_total = float(np.sum(seed_components))
        seed_g = _flat(graph.constraints(prepared.x0, prepared.p))
        seed_max_constraint_violation = _constraint_diagnostics(
            seed_g,
            prepared.lbg,
            prepared.ubg,
        )[2]
        strict_tolerances = (
            _strict_primal_tolerances(self._config, graph.row_layout, prepared) if self._config.strict_slack_bounds else None
        )
        seed_primal_feasible = _prepared_primal_feasible(
            prepared.x0,
            seed_g,
            prepared,
            tolerances=strict_tolerances,
        )
        quality_required_improvement = (
            _target_free_required_improvement(seed_objective_total)
            if self._config.strict_slack_bounds and not problem.targets and problem.route_objective is not None
            else None
        )
        graph.iteration_callback.arm(
            quality_seed_objective=(
                seed_objective_total
                if self._config.strict_slack_bounds and (problem.targets or problem.route_objective is not None)
                else None
            ),
            quality_required_improvement=quality_required_improvement,
            quality_stop_on_feasible=self._config.strict_slack_bounds and not seed_primal_feasible,
            quality_lbx=prepared.lbx,
            quality_ubx=prepared.ubx,
            quality_lbg=prepared.lbg,
            quality_ubg=prepared.ubg,
            quality_tolerances=strict_tolerances,
        )
        preparation_elapsed_ms = (time.perf_counter() - preparation_started) * 1_000.0
        callback_wall_limit = graph.iteration_callback._max_wall_time_s
        if wall_time_s is not None:
            graph.iteration_callback._max_wall_time_s = min(callback_wall_limit, float(wall_time_s))
        try:
            ipopt_started = time.perf_counter()
            result = graph.solver(
                x0=prepared.x0,
                p=prepared.p,
                lbx=prepared.lbx,
                ubx=prepared.ubx,
                lbg=prepared.lbg,
                ubg=prepared.ubg,
            )
        finally:
            graph.iteration_callback._max_wall_time_s = callback_wall_limit
        stats = graph.solver.stats()
        ipopt_elapsed_ms = (time.perf_counter() - ipopt_started) * 1_000.0
        terminal_raw_x = _flat(result["x"])
        terminal_raw_g = _flat(result["g"])
        terminal_raw_f = float(result["f"])
        raw_x = terminal_raw_x
        raw_g = terminal_raw_g
        raw_f = terminal_raw_f
        accepted_candidate_source = "IPOPT_TERMINAL"
        accepted_iteration: int | None = None
        elapsed_ms = (time.perf_counter() - started_at) * 1_000.0
        return_status = str(stats.get("return_status", ""))
        ipopt_iterations = int(stats.get("iter_count", 0))
        native_status = _strict_status(return_status)
        if native_status is MidMpcStatus.TIMEOUT:
            incumbent = _best_feasible_iteration(
                graph.iteration_callback.iterates,
                graph,
                prepared,
                tolerances=strict_tolerances,
            )
            if incumbent is not None:
                accepted_iteration, raw_x, raw_f, raw_g = incumbent
                accepted_candidate_source = "IPOPT_BEST_FEASIBLE_ITERATE"
        status = native_status
        objective_improvement = seed_objective_total - raw_f
        decision_change_norm = float(np.linalg.norm(raw_x - prepared.x0))
        raw_primal_feasible = _prepared_primal_feasible(
            raw_x,
            raw_g,
            prepared,
            tolerances=strict_tolerances,
        )
        optimization_quality_passed = _optimization_quality_passed(
            strict=self._config.strict_slack_bounds,
            return_status=return_status,
            iterations=ipopt_iterations,
            seed_objective=seed_objective_total,
            final_objective=raw_f,
            seed_primal_feasible=seed_primal_feasible,
            final_primal_feasible=raw_primal_feasible,
            decision_change_norm=decision_change_norm,
            controlled_quality_stop=graph.iteration_callback.quality_stop_requested,
            accepted_iteration=accepted_iteration,
            required_improvement=quality_required_improvement,
        )
        accepted_by_quality_gate = (
            native_status is MidMpcStatus.TIMEOUT
            and graph.iteration_callback.quality_stop_requested
            and raw_primal_feasible
            and optimization_quality_passed
            and accepted_candidate_source == "IPOPT_BEST_FEASIBLE_ITERATE"
        )
        if accepted_by_quality_gate:
            status = MidMpcStatus.FEASIBLE_NONOPTIMAL
        if status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL} and (
            not raw_primal_feasible or not optimization_quality_passed
        ):
            status = MidMpcStatus.NUMERICAL_FAILURE

        n = self._config.horizon_steps
        cpa_index = 2 * n
        dir_index = cpa_index + int(self._config.cpa_slack_enabled)
        raw_cpa_slack = float(raw_x[cpa_index]) if self._config.cpa_slack_enabled else 0.0
        raw_dir_slack = float(raw_x[dir_index]) if self._config.dir_slack_enabled else 0.0
        trajectory = _trajectory(raw_x, self._config)
        continuous_cpa_min_m, continuous_cpa_violated = _continuous_cpa(trajectory, problem)
        component_values = _flat(graph.objective_components(raw_x, prepared.p))
        objective_components = MidMpcObjectiveComponents(*map(float, component_values))
        active_rows, tight_rows, max_violation = _constraint_diagnostics(raw_g, prepared.lbg, prepared.ubg)
        decision_bound_violation = _maximum_bound_violation(raw_x, prepared.lbx, prepared.ubx)
        return MidMpcResult(
            status=status,
            native_status=native_status,
            ipopt_return_status=return_status,
            ipopt_iterations=ipopt_iterations,
            elapsed_ms=elapsed_ms,
            graph_build_elapsed_ms=graph_build_elapsed_ms,
            preparation_elapsed_ms=preparation_elapsed_ms,
            ipopt_elapsed_ms=ipopt_elapsed_ms,
            graph_cache_hit=graph_cache_hit,
            objective_total=raw_f,
            seed_objective_total=seed_objective_total,
            seed_max_constraint_violation=seed_max_constraint_violation,
            objective_improvement=objective_improvement,
            decision_change_norm=decision_change_norm,
            optimization_quality_passed=optimization_quality_passed,
            accepted_by_quality_gate=accepted_by_quality_gate,
            accepted_candidate_source=accepted_candidate_source,
            accepted_iteration=accepted_iteration,
            objective_components=objective_components,
            cpa_slack=max(0.0, raw_cpa_slack) if math.isfinite(raw_cpa_slack) else 0.0,
            trajectory=trajectory,
            prepared=prepared,
            raw_x=raw_x,
            raw_f=raw_f,
            raw_g=raw_g,
            raw_cpa_slack=raw_cpa_slack,
            raw_dir_slack=raw_dir_slack,
            terminal_raw_x=terminal_raw_x,
            terminal_raw_f=terminal_raw_f,
            terminal_raw_g=terminal_raw_g,
            continuous_cpa_min_m=continuous_cpa_min_m,
            continuous_cpa_violated=continuous_cpa_violated,
            active_row_indices=active_rows,
            tight_row_indices=tight_rows,
            max_constraint_violation=max_violation,
            max_decision_bound_violation=decision_bound_violation,
            row_layout=graph.row_layout,
        )


def _validate_target_capacity(problem: MidMpcProblem, max_targets: int) -> None:
    if len(problem.targets) > max_targets:
        raise ValueError(f"Mid-MPC supports at most {max_targets} targets")


def _validate_route_objective(problem: MidMpcProblem, horizon_steps: int) -> None:
    if problem.route_objective is None:
        return
    if (
        len(problem.route_objective.heading_reference_rad) != horizon_steps
        or len(problem.route_objective.lateral_reference_m) != horizon_steps
    ):
        raise ValueError("staged route objective must provide heading and lateral references per control interval")


class _Graph:
    def __init__(
        self,
        solver: ca.Function,
        objective_components: ca.Function,
        constraints: ca.Function,
        row_layout: MidMpcRowLayout,
        iteration_callback: _IterationCallback,
        target_capacity: int,
        audit_capacity: int,
    ) -> None:
        self.solver = solver
        self.objective_components = objective_components
        self.constraints = constraints
        self.row_layout = row_layout
        self.iteration_callback = iteration_callback
        self.target_capacity = target_capacity
        self.audit_capacity = audit_capacity


class _IterationCallback(ca.Callback):
    def __init__(
        self,
        nx: int,
        ng: int,
        np_: int,
        *,
        clock: Callable[[], float] = time.perf_counter,
        max_wall_time_s: float = 20.0,
    ) -> None:
        self._dimensions = (nx, ng, np_)
        self._clock = clock
        self._max_wall_time_s = max_wall_time_s
        self._started_at: float | None = None
        self._callback_count = 0
        self._quality_seed_objective: float | None = None
        self._quality_required_improvement: float | None = None
        self._quality_stop_on_feasible = False
        self._quality_bounds: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None
        self._quality_tolerances: tuple[np.ndarray, np.ndarray] | None = None
        self.quality_stop_requested = False
        self.iterates: list[tuple[int, np.ndarray, float]] = []
        ca.Callback.__init__(self)
        self.construct("mid_mpc_iter_callback", {})

    def arm(
        self,
        *,
        quality_seed_objective: float | None = None,
        quality_required_improvement: float | None = None,
        quality_stop_on_feasible: bool = False,
        quality_lbx: np.ndarray | None = None,
        quality_ubx: np.ndarray | None = None,
        quality_lbg: np.ndarray | None = None,
        quality_ubg: np.ndarray | None = None,
        quality_tolerances: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> None:
        self._started_at = self._clock()
        self._callback_count = 0
        self._quality_seed_objective = quality_seed_objective
        self._quality_required_improvement = quality_required_improvement
        self._quality_stop_on_feasible = quality_stop_on_feasible
        bounds = (quality_lbx, quality_ubx, quality_lbg, quality_ubg)
        self._quality_bounds = (
            None
            if any(value is None for value in bounds)
            else cast(tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], bounds)
        )
        self._quality_tolerances = quality_tolerances
        self.quality_stop_requested = False
        self.iterates = []

    def get_n_in(self) -> int:
        return 6

    def get_n_out(self) -> int:
        return 1

    def get_name_in(self, index: int) -> str:
        return ("x", "f", "g", "lam_x", "lam_g", "lam_p")[index]

    def get_name_out(self, _index: int) -> str:
        return "abort"

    def get_sparsity_in(self, index: int) -> ca.Sparsity:
        nx, ng, np_ = self._dimensions
        return ca.Sparsity.dense((nx, 1, ng, nx, ng, np_)[index], 1)

    def get_sparsity_out(self, _index: int) -> ca.Sparsity:
        return ca.Sparsity.scalar()

    def eval(self, arguments: list[ca.DM]) -> list[ca.DM]:
        self._callback_count += 1
        if len(arguments) >= 2:
            self.iterates.append(
                (
                    self._callback_count - 1,
                    _flat(arguments[0]),
                    float(_flat(arguments[1])[0]),
                )
            )
        if len(arguments) >= 3 and self._quality_seed_objective is not None and self._quality_bounds is not None:
            values = _flat(arguments[0])
            objective = float(_flat(arguments[1])[0])
            constraints = _flat(arguments[2])
            lbx, ubx, lbg, ubg = self._quality_bounds
            x_tolerance, g_tolerance = self._quality_tolerances if self._quality_tolerances is not None else (1.0e-3, 1.0e-3)
            required_improvement = (
                self._quality_required_improvement
                if self._quality_required_improvement is not None
                else max(1.0e-6, abs(self._quality_seed_objective) * 1.0e-8)
            )
            self.quality_stop_requested = bool(
                self._callback_count > 1
                and (self._quality_stop_on_feasible or self._quality_seed_objective - objective >= required_improvement)
                and _primal_feasible(values, lbx, ubx, tolerance=x_tolerance)
                and _primal_feasible(constraints, lbg, ubg, tolerance=g_tolerance)
            )
        elapsed_s = 0.0 if self._started_at is None else self._clock() - self._started_at
        return [ca.DM(float(elapsed_s > self._max_wall_time_s or self.quality_stop_requested))]


def _build_graph(  # noqa: PLR0912, PLR0915
    config: MidMpcConfig, problem: MidMpcProblem
) -> _Graph:
    n = config.horizon_steps
    if config.strict_slack_bounds:
        target_capacity = max(len(problem.targets), 1)
        audit_capacity = max(problem.audit_row_count, 1)
    else:
        target_capacity = len(problem.targets)
        audit_capacity = problem.audit_row_count
    prefix_capacity = max(n, _FROZEN_PREFIX_CAPACITY)
    prefix_u_start = int(_P.PREFIX_PSI) + prefix_capacity
    target_start = prefix_u_start + prefix_capacity
    parameter_dim = target_start + config.max_targets * _TARGET_STRIDE
    cpa_hard_index: int | None = None
    if config.strict_slack_bounds:
        cpa_hard_index = parameter_dim
        parameter_dim += 1
    route_objective_start = parameter_dim
    staged_route_objective = problem.route_objective is not None
    if staged_route_objective:
        parameter_dim += 5 * n + 1
    rule_parameters_start: int | None = None
    if config.strict_slack_bounds:
        rule_parameters_start = parameter_dim
        parameter_dim += 2 * config.max_targets
    dt = ca.DM(config.dt_s)
    psi = ca.MX.sym("psi", n)
    speed = ca.MX.sym("u", n)
    sigma_cpa = ca.MX.sym("cpa_slack") if config.cpa_slack_enabled else None
    sigma_dir = ca.MX.sym("dir_slack") if config.dir_slack_enabled else None
    p = ca.MX.sym("p", parameter_dim)
    decisions = [psi, speed]
    if sigma_cpa is not None:
        decisions.append(sigma_cpa)
    if sigma_dir is not None:
        decisions.append(sigma_dir)
    x = ca.vertcat(*decisions)

    route_bearing = p[_P.ROUTE_BEARING]
    route_reference = (
        p[route_objective_start : route_objective_start + n] if staged_route_objective else ca.repmat(route_bearing, n, 1)
    )
    lateral_reference = p[route_objective_start + n : route_objective_start + 2 * n] if staged_route_objective else None
    avoidance_active_until = p[route_objective_start + 2 * n] if staged_route_objective else ca.DM(n)
    continuity_start = route_objective_start + 2 * n + 1
    continuity_heading = p[continuity_start : continuity_start + n] if staged_route_objective else ca.DM.zeros(n)
    continuity_speed = p[continuity_start + n : continuity_start + 2 * n] if staged_route_objective else ca.DM.zeros(n)
    continuity_weight = p[continuity_start + 2 * n : continuity_start + 3 * n] if staged_route_objective else ca.DM.zeros(n)
    planned_speed = p[_P.PLANNED_SPEED]
    distance_error = psi - route_reference
    velocity_error = speed - ca.repmat(planned_speed, n, 1)
    distance_cost = ca.dot(distance_error, distance_error)
    velocity_cost = ca.dot(velocity_error, velocity_error)
    route_cost = _route_cost(psi, speed, p, config.dt_s, lateral_reference)
    pref_dir = p[_P.PREFERRED_SIDE]
    give_way_role = p[_P.LATERAL_ACTIVE]
    objective_terminal_cross_track = _terminal_cross_track(psi, speed, p, config.dt_s)
    wrong_side = -pref_dir * objective_terminal_cross_track / p[_P.LATERAL_SCALE]
    tau = ca.DM(config.terminal_tau)
    terminal_max = ca.DM(config.terminal_l_max_m)
    terminal_lower = tau * ca.log(ca.DM(1.0) + ca.exp(wrong_side / tau))
    z_pos = (objective_terminal_cross_track - terminal_max) / p[_P.LATERAL_SCALE]
    z_neg = (-objective_terminal_cross_track - terminal_max) / p[_P.LATERAL_SCALE]
    terminal_upper = tau * (ca.log(ca.DM(1.0) + ca.exp(z_pos / tau)) + ca.log(ca.DM(1.0) + ca.exp(z_neg / tau)))
    terminal_legacy_gate = ca.if_else(avoidance_active_until >= ca.DM(n), ca.DM(1.0), ca.DM(0.0))
    terminal_cost = terminal_legacy_gate * (
        give_way_role * terminal_lower + give_way_role * pref_dir * pref_dir * terminal_upper
    )
    colreg_cost = _colreg_cost(
        psi,
        speed,
        p,
        config,
        avoidance_active_until=avoidance_active_until if staged_route_objective else None,
    )
    asym_sum = ca.MX(0.0)
    for k in range(n):
        avoidance_gate = ca.if_else(ca.DM(k) < avoidance_active_until, ca.DM(1.0), ca.DM(0.0))
        asym_sum += (
            avoidance_gate
            * ca.DM(config.asym_tau)
            * ca.log(ca.DM(1.0) + ca.exp((route_bearing - psi[k]) / ca.DM(config.asym_tau)))
        )
    asym_cost = p[_P.ASYMMETRY_ACTIVE] * ca.DM(config.k_asym) * asym_sum
    colreg_term = ca.DM(config.w_colreg) * colreg_cost
    heading_term = ca.DM(config.w_dist) * distance_cost
    speed_term = ca.DM(config.w_vel) * velocity_cost
    route_term = ca.DM(config.w_route) * route_cost
    continuity_heading_error = ca.atan2(
        ca.sin(psi - continuity_heading),
        ca.cos(psi - continuity_heading),
    )
    continuity_speed_error = speed - continuity_speed
    continuity_term = ca.dot(
        continuity_weight,
        ca.power(continuity_heading_error, 2) + ca.DM(0.1) * ca.power(continuity_speed_error, 2),
    )
    objective = colreg_term + heading_term + speed_term + route_term + asym_cost + terminal_cost + continuity_term
    cpa_slack_term = ca.MX(0.0)
    direction_slack_term = ca.MX(0.0)
    if sigma_cpa is not None:
        cpa_slack_term = ca.DM(config.w_slack_l1) * sigma_cpa + ca.DM(config.w_slack_l2) * sigma_cpa * sigma_cpa
        objective += cpa_slack_term
    if sigma_dir is not None:
        direction_slack_term = (
            ca.DM(config.w_dir_slack_l1) * sigma_dir + ca.DM(config.w_dir_slack_l2) * sigma_dir * sigma_dir
        )
        objective += direction_slack_term

    rows: list[ca.MX] = []
    rot_step = p[_P.ROT_MAX] * dt
    rows.extend([rot_step - (psi[0] - p[_P.OWN_PSI])])
    rows.append(rot_step - (psi[1:] - psi[:-1]))
    rows.extend([rot_step + (psi[0] - p[_P.OWN_PSI])])
    rows.append(rot_step + (psi[1:] - psi[:-1]))
    decel_step = p[_P.DECEL_MAX] * dt
    speed_delta = speed - ca.vertcat(p[_P.U0], speed[:-1])
    if config.strict_slack_bounds:
        rows.append(decel_step - ca.fabs(speed_delta))
    else:
        rows.append(decel_step + speed_delta)
    rows.extend(psi[k] - p[_P.PREFIX_PSI + k] for k in range(n))
    rows.extend(speed[k] - p[prefix_u_start + k] for k in range(n))
    rows.extend(
        _cpa_rows(
            psi,
            speed,
            sigma_cpa,
            p,
            config,
            problem,
            target_capacity=target_capacity,
            cpa_hard_index=cpa_hard_index,
        )
    )
    constraint_cross_track = _cross_track_all(psi, speed, p, config.dt_s)
    dir_slack = sigma_dir if sigma_dir is not None else 0.0
    rows.extend(pref_dir * constraint_cross_track[k] + dir_slack for k in range(n))
    rows.extend(pref_dir * (psi[k] - p[_P.OWN_PSI]) - p[_P.MIN_ALTERATION] + dir_slack for k in range(n))
    constraint_terminal_cross_track = _terminal_cross_track(psi, speed, p, config.dt_s)
    rows.extend(
        (
            pref_dir * constraint_terminal_cross_track - config.terminal_l_min_m,
            constraint_terminal_cross_track + config.terminal_l_max_m,
            config.terminal_l_max_m - constraint_terminal_cross_track,
        )
    )
    if rule_parameters_start is None:
        rows.extend(ca.MX(0.0) for _index in range(audit_capacity))
    else:
        rows.extend(
            _crossing_astern_rows(
                psi,
                speed,
                p,
                config,
                rule_parameters_start=rule_parameters_start,
                audit_capacity=audit_capacity,
            )
        )
    g = ca.vertcat(*rows)

    options = {
        "ipopt.max_iter": 5000,
        "ipopt.tol": 1.0e-4,
        "ipopt.acceptable_iter": 0,
        "ipopt.print_level": 0,
        "ipopt.linear_solver": "mumps",
        "ipopt.hessian_approximation": "limited-memory",
        "ipopt.limited_memory_max_history": 50,
        "ipopt.max_cpu_time": config.max_wall_time_s,
        "ipopt.bound_push": 1.0e-4,
        "ipopt.bound_frac": 1.0e-4,
        "ipopt.mu_strategy": "adaptive",
        "ipopt.constr_viol_tol": 1.0e-3,
        "ipopt.acceptable_constr_viol_tol": 1.0e-2,
        "print_time": False,
    }
    row_layout = _row_layout(config, target_capacity, audit_capacity)
    nlp = {"x": x, "p": p, "f": objective, "g": g}
    iteration_callback = _IterationCallback(
        int(x.numel()),
        int(g.numel()),
        int(p.numel()),
        max_wall_time_s=config.max_wall_time_s,
    )
    options["iteration_callback"] = iteration_callback
    options["iteration_callback_step"] = 1
    options["iteration_callback_ignore_errors"] = True
    if config.strict_slack_bounds:
        options.update(
            {
                "ipopt.bound_relax_factor": 0.0,
                "ipopt.honor_original_bounds": "yes",
                "ipopt.mu_strategy": "monotone",
                "ipopt.mu_init": 1.0e-3,
            }
        )
    solver = ca.nlpsol("mid_mpc_solver", "ipopt", nlp, options)
    component_function = ca.Function(
        "mid_mpc_objective_components",
        [x, p],
        [
            ca.vertcat(
                colreg_term,
                heading_term,
                speed_term,
                route_term,
                asym_cost,
                terminal_cost,
                cpa_slack_term,
                direction_slack_term,
                continuity_term,
            )
        ],
    )
    constraint_function = ca.Function("mid_mpc_constraints", [x, p], [g])
    return _Graph(
        solver,
        component_function,
        constraint_function,
        row_layout,
        iteration_callback,
        target_capacity,
        audit_capacity,
    )


def _cross_track_all(psi: ca.MX, speed: ca.MX, p: ca.MX, dt_s: float) -> list[ca.MX]:
    dt = ca.DM(dt_s)
    cx = p[_P.X0]
    cy = p[_P.Y0]
    values: list[ca.MX] = []
    for k in range(psi.numel()):
        values.append(
            (cx - p[_P.ROUTE_ORIGIN_X]) * p[_P.ROUTE_NORMAL_X] + (cy - p[_P.ROUTE_ORIGIN_Y]) * p[_P.ROUTE_NORMAL_Y]
        )
        cx += speed[k] * dt * ca.cos(psi[k])
        cy += speed[k] * dt * ca.sin(psi[k])
    return values


def _crossing_astern_rows(
    psi: ca.MX,
    speed: ca.MX,
    p: ca.MX,
    config: MidMpcConfig,
    *,
    rule_parameters_start: int,
    audit_capacity: int,
) -> list[ca.MX]:
    dt = ca.DM(config.dt_s)
    positions: list[tuple[ca.MX, ca.MX]] = [(p[_P.X0], p[_P.Y0])]
    own_x = p[_P.X0]
    own_y = p[_P.Y0]
    for k in range(config.horizon_steps):
        own_x += speed[k] * dt * ca.cos(psi[k])
        own_y += speed[k] * dt * ca.sin(psi[k])
        positions.append((own_x, own_y))
    target_start = int(_P.PREFIX_PSI) + 2 * max(config.horizon_steps, _FROZEN_PREFIX_CAPACITY)
    rows: list[ca.MX] = []
    for target_index in range(audit_capacity):
        if target_index >= config.max_targets:
            rows.append(ca.MX(0.0))
            continue
        base = target_start + target_index * _TARGET_STRIDE
        rule_base = rule_parameters_start + 2 * target_index
        active = p[rule_base]
        margin_m = p[rule_base + 1]
        target_north_speed = p[base + _T.SOG] * ca.cos(p[base + _T.COG])
        target_east_speed = p[base + _T.SOG] * ca.sin(p[base + _T.COG])
        best_distance_squared: ca.MX | None = None
        best_projection = ca.MX(0.0)
        for k in range(config.horizon_steps):
            start_time_s = ca.DM(k * config.dt_s)
            end_time_s = ca.DM((k + 1) * config.dt_s)
            target_start_x = p[base + _T.X] + target_north_speed * start_time_s
            target_start_y = p[base + _T.Y] + target_east_speed * start_time_s
            target_end_x = p[base + _T.X] + target_north_speed * end_time_s
            target_end_y = p[base + _T.Y] + target_east_speed * end_time_s
            relative_start_x = target_start_x - positions[k][0]
            relative_start_y = target_start_y - positions[k][1]
            relative_delta_x = (target_end_x - positions[k + 1][0]) - relative_start_x
            relative_delta_y = (target_end_y - positions[k + 1][1]) - relative_start_y
            denominator = relative_delta_x * relative_delta_x + relative_delta_y * relative_delta_y
            fraction = ca.if_else(
                denominator > ca.DM(1.0e-18),
                ca.fmin(
                    ca.fmax(
                        -(relative_start_x * relative_delta_x + relative_start_y * relative_delta_y) / denominator,
                        ca.DM(0.0),
                    ),
                    ca.DM(1.0),
                ),
                ca.DM(0.0),
            )
            relative_x = relative_start_x + fraction * relative_delta_x
            relative_y = relative_start_y + fraction * relative_delta_y
            distance_squared = relative_x * relative_x + relative_y * relative_y
            projection = relative_x * ca.cos(p[base + _T.COG]) + relative_y * ca.sin(p[base + _T.COG])
            if best_distance_squared is None:
                best_distance_squared = distance_squared
                best_projection = projection
            else:
                closer = distance_squared < best_distance_squared
                best_distance_squared = ca.if_else(closer, distance_squared, best_distance_squared)
                best_projection = ca.if_else(closer, projection, best_projection)
        rows.append(active * (best_projection - margin_m))
    return rows


def _route_cost(
    psi: ca.MX,
    speed: ca.MX,
    p: ca.MX,
    dt_s: float,
    lateral_reference: ca.MX | None = None,
) -> ca.MX:
    dt = ca.DM(dt_s)
    cx = p[_P.X0]
    cy = p[_P.Y0]
    cost = ca.MX(0.0)
    terminal = ca.MX(0.0)
    for k in range(psi.numel()):
        cross_track = (cx - p[_P.ROUTE_ORIGIN_X]) * p[_P.ROUTE_NORMAL_X] + (cy - p[_P.ROUTE_ORIGIN_Y]) * p[_P.ROUTE_NORMAL_Y]
        reference = ca.DM(0.0) if lateral_reference is None else lateral_reference[k]
        scaled = (cross_track - reference) / p[_P.LATERAL_SCALE]
        cost = cost + scaled * scaled
        if k == psi.numel() - 1:
            terminal = cross_track
        cx = cx + speed[k] * dt * ca.cos(psi[k])
        cy = cy + speed[k] * dt * ca.sin(psi[k])
    terminal_reference = ca.DM(0.0) if lateral_reference is None else lateral_reference[psi.numel() - 1]
    terminal_scaled = (terminal - terminal_reference) / p[_P.LATERAL_SCALE]
    return p[_P.ROUTE_WEIGHT] * (cost + ca.DM(2.0) * terminal_scaled * terminal_scaled)


def _terminal_cross_track(psi: ca.MX, speed: ca.MX, p: ca.MX, dt_s: float) -> ca.MX:
    dt = ca.DM(dt_s)
    cx = p[_P.X0]
    cy = p[_P.Y0]
    for k in range(psi.numel() - 1):
        cx = cx + speed[k] * dt * ca.cos(psi[k])
        cy = cy + speed[k] * dt * ca.sin(psi[k])
    return (cx - p[_P.ROUTE_ORIGIN_X]) * p[_P.ROUTE_NORMAL_X] + (cy - p[_P.ROUTE_ORIGIN_Y]) * p[_P.ROUTE_NORMAL_Y]


def _colreg_cost(
    psi: ca.MX,
    speed: ca.MX,
    p: ca.MX,
    config: MidMpcConfig,
    *,
    avoidance_active_until: ca.MX | None = None,
) -> ca.MX:
    dt = ca.DM(config.dt_s)
    zeta = ca.DM(config.zeta)
    own_x = p[_P.X0]
    own_y = p[_P.Y0]
    positions: list[tuple[ca.MX, ca.MX]] = []
    for k in range(config.horizon_steps):
        own_x += speed[k] * dt * ca.cos(psi[k])
        own_y += speed[k] * dt * ca.sin(psi[k])
        positions.append((own_x, own_y))
    cost = ca.MX(0.0)
    prefix_capacity = max(config.horizon_steps, _FROZEN_PREFIX_CAPACITY)
    target_start = int(_P.PREFIX_PSI) + 2 * prefix_capacity
    for target_index in range(config.max_targets):
        base = target_start + target_index * _TARGET_STRIDE
        target_dx = p[base + _T.SOG] * ca.cos(p[base + _T.COG])
        target_dy = p[base + _T.SOG] * ca.sin(p[base + _T.COG])
        for k, (current_x, current_y) in enumerate(positions):
            phase_gate = (
                ca.DM(1.0)
                if avoidance_active_until is None
                else ca.if_else(ca.DM(k) < avoidance_active_until, ca.DM(1.0), ca.DM(0.0))
            )
            time_s = k * config.dt_s
            dx = current_x - (p[base + _T.X] + target_dx * time_s)
            dy = current_y - (p[base + _T.Y] + target_dy * time_s)
            distance = ca.sqrt(dx * dx + dy * dy + ca.DM(1.0))
            discount = math.exp(-time_s / config.t_discount_s)
            cost += phase_gate * p[base + _T.WEIGHT] * ca.DM(discount) * ca.exp(-zeta * (distance - p[_P.CPA_SAFE]))
    return cost / ca.DM(max(1, config.max_targets * config.horizon_steps))


def _cpa_rows(
    psi: ca.MX,
    speed: ca.MX,
    sigma_cpa: ca.MX | None,
    p: ca.MX,
    config: MidMpcConfig,
    problem: MidMpcProblem,
    *,
    target_capacity: int,
    cpa_hard_index: int | None,
) -> list[ca.MX]:
    rows: list[ca.MX] = []
    dt = ca.DM(config.dt_s)
    own_x: ca.MX = ca.MX(0.0)
    own_y: ca.MX = ca.MX(0.0)
    prefix_k = (
        p[_P.PREFIX_ACTIVE_K] if config.strict_slack_bounds else ca.DM(min(problem.prefix_active_k, config.horizon_steps))
    )
    cpa_hard = p[cpa_hard_index] if cpa_hard_index is not None else ca.DM(problem.cpa_hard_m)
    prefix_capacity = max(config.horizon_steps, _FROZEN_PREFIX_CAPACITY)
    target_start = int(_P.PREFIX_PSI) + 2 * prefix_capacity
    for k in range(config.horizon_steps):
        own_x += speed[k] * dt * ca.cos(psi[k])
        own_y += speed[k] * dt * ca.sin(psi[k])
        for target_index in range(target_capacity):
            base = target_start + target_index * _TARGET_STRIDE
            time_s = k * config.dt_s
            target_north_speed = p[base + _T.SOG] * ca.cos(p[base + _T.COG])
            target_east_speed = p[base + _T.SOG] * ca.sin(p[base + _T.COG])
            target_x = p[base + _T.X] + target_north_speed * time_s
            target_y = p[base + _T.Y] + target_east_speed * time_s
            dx = own_x - target_x
            dy = own_y - target_y
            row = dx * dx + dy * dy - cpa_hard * cpa_hard
            if sigma_cpa is not None:
                row += ca.if_else(ca.DM(k) >= prefix_k, sigma_cpa, ca.DM(0.0))
            rows.append(row)
    return rows


_SEED_REPAIR_STEP_RAD = math.radians(2.5)
_SEED_REPAIR_MAX_STEPS = 18


def _repair_infeasible_seed(
    graph: _Graph,
    prepared: MidMpcPreparedProblem,
    problem: MidMpcProblem,
    config: MidMpcConfig,
) -> MidMpcPreparedProblem | None:
    """Bend a row-infeasible cold seed clear of every hard row.

    A cold seed cruising straight down the route can sit on a far-horizon
    rendezvous with a slow target; IPOPT then spends dozens of iterations
    restoring primal feasibility inside the deadline (the tenship t=0
    cold-start stall). Scan uniform heading offsets in rising magnitude
    and keep the first candidate whose seed satisfies every finite row;
    the candidates are re-ramped inside the rot envelope, heading bounds,
    and active prefix, so only far-horizon row feasibility changes. When
    no offset clears every row (for example CPA clearance conflicts with
    a crossing-astern audit), apply the offset with the smallest worst
    row violation instead, but only when it at least halves the baseline;
    otherwise return None and leave the original seed untouched.
    """
    baseline = _max_row_violation(graph, prepared.x0, prepared)
    if baseline <= 1.0e-9:
        return None
    best_x0: np.ndarray | None = None
    best_violation = baseline
    for step_index in range(1, _SEED_REPAIR_MAX_STEPS + 1):
        magnitude = _SEED_REPAIR_STEP_RAD * step_index
        for sign in (-1.0, 1.0):
            candidate = _ramped_offset_seed(prepared.x0, problem, config, sign * magnitude)
            violation = _max_row_violation(graph, candidate, prepared)
            if violation <= 1.0e-9:
                return _reseeded(prepared, candidate)
            if violation < best_violation:
                best_violation = violation
                best_x0 = candidate
    if best_x0 is not None and best_violation < 0.5 * baseline:
        return _reseeded(prepared, best_x0)
    return None


def _reseeded(prepared: MidMpcPreparedProblem, x0: np.ndarray) -> MidMpcPreparedProblem:
    return MidMpcPreparedProblem(
        p=prepared.p,
        x0=x0,
        lbx=prepared.lbx,
        ubx=prepared.ubx,
        lbg=prepared.lbg,
        ubg=prepared.ubg,
    )


def _ramped_offset_seed(seed: np.ndarray, problem: MidMpcProblem, config: MidMpcConfig, delta_rad: float) -> np.ndarray:
    n = config.horizon_steps
    x0 = seed.copy()
    psi = x0[:n]
    heading_step = problem.rot_max_rad_s * config.dt_s
    start_k = min(problem.prefix_active_k, n)
    previous = float(psi[start_k - 1]) if start_k else problem.own_ship.psi_rad
    for k in range(start_k, n):
        target = float(np.clip(psi[k] + delta_rad, *problem.heading_bounds_rad))
        target_delta = math.atan2(math.sin(target - previous), math.cos(target - previous))
        previous = float(
            np.clip(previous + np.clip(target_delta, -heading_step, heading_step), *problem.heading_bounds_rad)
        )
        psi[k] = previous
    return x0


def _max_row_violation(graph: _Graph, x0: np.ndarray, prepared: MidMpcPreparedProblem) -> float:
    values = _flat(graph.constraints(x0, prepared.p))
    return float(np.max(np.maximum(prepared.lbg - values, values - prepared.ubg)))


def _prepare(config: MidMpcConfig, problem: MidMpcProblem, layout: MidMpcRowLayout) -> MidMpcPreparedProblem:
    p = _pack_parameters(config, problem)
    n = config.horizon_steps
    x_dimension = 2 * n + int(config.cpa_slack_enabled) + int(config.dir_slack_enabled)
    x0 = np.zeros(x_dimension)
    speed_seed = (
        problem.own_ship.u_mps
        if problem.own_ship.u_mps > 0.1
        else problem.planned_speed_mps
        if problem.planned_speed_mps > 0.1
        else 5.14
    )
    x0[:n] = problem.own_ship.psi_rad
    x0[n : 2 * n] = speed_seed
    if config.strict_slack_bounds:
        route_delta = math.atan2(
            math.sin(problem.route_bearing_rad - problem.own_ship.psi_rad),
            math.cos(problem.route_bearing_rad - problem.own_ship.psi_rad),
        )
        heading_target = float(
            np.clip(
                problem.own_ship.psi_rad + route_delta,
                *problem.heading_bounds_rad,
            )
        )
        if problem.lateral_active and problem.preferred_side:
            seed_change = min(
                max(abs(route_delta), problem.min_alteration_rad) + math.radians(10.0),
                max(
                    abs(problem.heading_bounds_rad[0] - problem.own_ship.psi_rad),
                    abs(problem.heading_bounds_rad[1] - problem.own_ship.psi_rad),
                ),
            )
            heading_target = float(
                np.clip(
                    problem.own_ship.psi_rad + math.copysign(seed_change, problem.preferred_side),
                    *problem.heading_bounds_rad,
                )
            )
        heading_step = problem.rot_max_rad_s * config.dt_s
        for k in range(n):
            x0[k] = problem.own_ship.psi_rad + float(
                np.clip(
                    heading_target - problem.own_ship.psi_rad,
                    -heading_step * (k + 1),
                    heading_step * (k + 1),
                )
            )
        if problem.route_objective is not None:
            previous_heading = problem.own_ship.psi_rad
            for k, reference in enumerate(problem.route_objective.heading_reference_rad):
                target_heading = (
                    heading_target
                    if problem.lateral_active and k < problem.route_objective.avoidance_active_until_k
                    else reference
                )
                target_delta = math.atan2(
                    math.sin(target_heading - previous_heading),
                    math.cos(target_heading - previous_heading),
                )
                previous_heading = float(
                    np.clip(
                        previous_heading + np.clip(target_delta, -heading_step, heading_step),
                        *problem.heading_bounds_rad,
                    )
                )
                x0[k] = previous_heading
        speed_target = float(np.clip(problem.planned_speed_mps, *problem.speed_bounds_mps))
        if speed_target < problem.own_ship.u_mps:
            for k in range(n):
                x0[n + k] = max(
                    speed_target,
                    problem.own_ship.u_mps - problem.decel_max_mps2 * config.dt_s * (k + 1),
                )
        else:
            x0[n : 2 * n] = speed_target
        _apply_continuity_seed(x0, problem, config, heading_step)
    prefix_k = min(problem.prefix_active_k, n)
    x0[:prefix_k] = problem.prefix_psi_rad[:prefix_k]
    x0[n : n + prefix_k] = problem.prefix_u_mps[:prefix_k]

    lbx = np.empty(x_dimension)
    ubx = np.empty(x_dimension)
    lbx[:n], ubx[:n] = problem.heading_bounds_rad
    lbx[n : 2 * n], ubx[n : 2 * n] = problem.speed_bounds_mps
    lbx[2 * n :] = 0.0
    ubx[2 * n :] = np.inf
    if config.strict_slack_bounds and not problem.targets and prefix_k:
        lbx[:prefix_k] = ubx[:prefix_k] = problem.prefix_psi_rad[:prefix_k]
        lbx[n : n + prefix_k] = ubx[n : n + prefix_k] = problem.prefix_u_mps[:prefix_k]
    lbg, ubg, cpa_hard_from = _row_bounds(config, problem, layout)
    if config.cpa_slack_enabled and not config.strict_slack_bounds:
        x0[2 * n] = _cpa_slack_seed(config, problem, x0, cpa_hard_from)
    if config.strict_slack_bounds:
        ubx[2 * n :] = 0.0
    return MidMpcPreparedProblem(p=p, x0=x0, lbx=lbx, ubx=ubx, lbg=lbg, ubg=ubg)


def _apply_continuity_seed(
    seed: np.ndarray,
    problem: MidMpcProblem,
    config: MidMpcConfig,
    heading_step: float,
) -> None:
    objective = problem.route_objective
    if objective is None or not any(objective.continuity_weight):
        return
    previous_heading = problem.own_ship.psi_rad
    for k, weight in enumerate(objective.continuity_weight):
        if weight <= 0.0:
            previous_heading = float(seed[k])
            continue
        target_heading = objective.continuity_heading_reference_rad[k]
        target_delta = math.atan2(
            math.sin(target_heading - previous_heading),
            math.cos(target_heading - previous_heading),
        )
        previous_heading = float(
            np.clip(
                previous_heading + np.clip(target_delta, -heading_step, heading_step),
                *problem.heading_bounds_rad,
            )
        )
        seed[k] = previous_heading
        seed[config.horizon_steps + k] = float(
            np.clip(
                objective.continuity_speed_reference_mps[k],
                *problem.speed_bounds_mps,
            )
        )


def _apply_primal_warm_start(
    prepared: MidMpcPreparedProblem,
    warm: MidMpcPrimalWarmStart,
    config: MidMpcConfig,
    *,
    reuse_stop_k: int,
) -> MidMpcPreparedProblem:
    n = config.horizon_steps
    if warm.course_rad.size != n:
        raise ValueError("warm-start grid must match the frozen solver horizon")
    seed = prepared.x0.copy()
    source_times = warm.accepted_at_s + (np.arange(n, dtype=float) + 1.0) * warm.dt_s
    query_times = warm.current_time_s + (np.arange(n, dtype=float) + 1.0) * config.dt_s
    reusable = (query_times <= source_times[-1] + 1.0e-9) & (np.arange(n) < reuse_stop_k)
    if np.any(reusable):
        unwrapped = np.unwrap(warm.course_rad)
        seed[:n][reusable] = np.interp(query_times[reusable], source_times, unwrapped)
        seed[n : 2 * n][reusable] = np.interp(query_times[reusable], source_times, warm.speed_mps)
    seed = np.clip(seed, prepared.lbx, prepared.ubx)
    if config.strict_slack_bounds:
        seed[2 * n :] = 0.0
    return MidMpcPreparedProblem(
        p=prepared.p,
        x0=seed,
        lbx=prepared.lbx,
        ubx=prepared.ubx,
        lbg=prepared.lbg,
        ubg=prepared.ubg,
    )


def _pack_parameters(config: MidMpcConfig, problem: MidMpcProblem) -> np.ndarray:
    prefix_capacity = max(config.horizon_steps, _FROZEN_PREFIX_CAPACITY)
    prefix_u_start = int(_P.PREFIX_PSI) + prefix_capacity
    target_start = prefix_u_start + prefix_capacity
    parameter_dim = target_start + config.max_targets * _TARGET_STRIDE
    cpa_hard_index: int | None = None
    if config.strict_slack_bounds:
        cpa_hard_index = parameter_dim
        parameter_dim += 1
    route_objective_start = parameter_dim
    if problem.route_objective is not None:
        parameter_dim += 5 * config.horizon_steps + 1
    rule_parameters_start: int | None = None
    if config.strict_slack_bounds:
        rule_parameters_start = parameter_dim
        parameter_dim += 2 * config.max_targets
    p = np.zeros(parameter_dim)
    p[_P.PSI0 : _P.Y0 + 1] = (
        problem.own_ship.psi_rad,
        problem.own_ship.u_mps,
        problem.own_ship.x_m,
        problem.own_ship.y_m,
    )
    p[_P.ROUTE_BEARING : _P.OWN_PSI + 1] = (
        problem.route_bearing_rad,
        problem.planned_speed_mps,
        *problem.heading_bounds_rad,
        *problem.speed_bounds_mps,
        problem.cpa_safe_m,
        problem.rot_max_rad_s,
        problem.own_ship.psi_rad,
    )
    p[_P.ASYMMETRY_ACTIVE] = float(problem.starboard_asymmetry_active)
    p[_P.ROUTE_ORIGIN_X : _P.ROUTE_WEIGHT + 1] = (
        *problem.route_frame.origin_m,
        *problem.route_frame.normal,
        problem.route_frame.bearing_rad,
        problem.route_frame.lateral_scale_m,
        problem.route_frame.weight,
    )
    prefix_k = min(problem.prefix_active_k, config.horizon_steps)
    p[_P.PREFIX_ACTIVE_K] = prefix_k
    p[_P.PREFERRED_SIDE] = problem.preferred_side
    p[_P.MIN_ALTERATION] = problem.min_alteration_rad
    p[_P.LATERAL_ACTIVE] = float(problem.lateral_active)
    p[_P.DECEL_MAX] = problem.decel_max_mps2 if problem.decel_max_mps2 > 1.0e-6 else 0.08
    if cpa_hard_index is not None:
        p[cpa_hard_index] = problem.cpa_hard_m
    p[_P.PREFIX_PSI : _P.PREFIX_PSI + prefix_k] = problem.prefix_psi_rad[:prefix_k]
    p[prefix_u_start : prefix_u_start + prefix_k] = problem.prefix_u_mps[:prefix_k]
    for index, target in enumerate(problem.targets[: config.max_targets]):
        base = target_start + index * _TARGET_STRIDE
        distance = math.hypot(
            target.x_m - problem.own_ship.x_m,
            target.y_m - problem.own_ship.y_m,
        )
        span = max(config.pwt_outer_m - problem.cpa_safe_m, 1.0)
        weight = min(max((config.pwt_outer_m - distance) / span, 0.0), 1.0)
        p[base : base + _TARGET_STRIDE] = (
            target.x_m,
            target.y_m,
            target.cog_rad,
            target.sog_mps,
            weight,
        )
        if rule_parameters_start is not None and target.crossing_astern_required:
            rule_base = rule_parameters_start + 2 * index
            p[rule_base : rule_base + 2] = (
                1.0,
                target.crossing_astern_margin_m,
            )
    if problem.route_objective is not None:
        p[route_objective_start : route_objective_start + config.horizon_steps] = (
            problem.route_objective.heading_reference_rad
        )
        p[route_objective_start + config.horizon_steps : route_objective_start + 2 * config.horizon_steps] = (
            problem.route_objective.lateral_reference_m
        )
        p[route_objective_start + 2 * config.horizon_steps] = problem.route_objective.avoidance_active_until_k
        continuity_start = route_objective_start + 2 * config.horizon_steps + 1
        p[continuity_start : continuity_start + config.horizon_steps] = (
            problem.route_objective.continuity_heading_reference_rad
        )
        p[continuity_start + config.horizon_steps : continuity_start + 2 * config.horizon_steps] = (
            problem.route_objective.continuity_speed_reference_mps
        )
        p[continuity_start + 2 * config.horizon_steps : continuity_start + 3 * config.horizon_steps] = (
            problem.route_objective.continuity_weight
        )
    return p


def _row_layout(config: MidMpcConfig, target_capacity: int, audit_capacity: int) -> MidMpcRowLayout:
    n = config.horizon_steps
    target_rows = n * target_capacity
    rule_rows = audit_capacity
    rot = MidMpcRowSpan(0, 2 * n)
    speed_rate = MidMpcRowSpan(rot.start + rot.count, n)
    prefix_psi = MidMpcRowSpan(speed_rate.start + speed_rate.count, n)
    prefix_u = MidMpcRowSpan(prefix_psi.start + prefix_psi.count, n)
    cpa = MidMpcRowSpan(prefix_u.start + prefix_u.count, target_rows)
    direction = MidMpcRowSpan(cpa.start + cpa.count, n)
    min_alt = MidMpcRowSpan(direction.start + direction.count, n)
    terminal = MidMpcRowSpan(min_alt.start + min_alt.count, 3)
    rule = MidMpcRowSpan(terminal.start + terminal.count, rule_rows)
    zone = MidMpcRowSpan(rule.start + rule.count, 0)
    return MidMpcRowLayout(
        rot=rot,
        speed_rate=speed_rate,
        prefix_psi=prefix_psi,
        prefix_u=prefix_u,
        cpa=cpa,
        direction=direction,
        min_alt=min_alt,
        terminal=terminal,
        rule=rule,
        zone=zone,
    )


def _row_bounds(
    config: MidMpcConfig,
    problem: MidMpcProblem,
    layout: MidMpcRowLayout,
) -> tuple[np.ndarray, np.ndarray, int]:
    total = layout.zone.start
    lbg = np.zeros(total)
    ubg = np.full(total, np.inf)
    n = config.horizon_steps
    prefix_k = min(problem.prefix_active_k, n)
    for span in (layout.prefix_psi, layout.prefix_u):
        lbg[span.start : span.start + span.count] = -np.inf
        ubg[span.start : span.start + span.count] = np.inf
        lbg[span.start : span.start + prefix_k] = 0.0
        ubg[span.start : span.start + prefix_k] = 0.0

    schedule = problem.row_schedule
    _apply_rule_bounds(
        lbg,
        ubg,
        layout.direction,
        schedule.direction_hard_window,
        legacy_from_k=schedule.direction_hard_from_k,
        legacy_enabled=problem.lateral_active,
        horizon_steps=n,
    )
    _apply_rule_bounds(
        lbg,
        ubg,
        layout.min_alt,
        schedule.min_alt_hard_window,
        legacy_from_k=schedule.min_alt_hard_from_k,
        legacy_enabled=problem.lateral_active,
        horizon_steps=n,
    )
    cpa_hard_from = _apply_cpa_bounds(lbg, ubg, problem, layout, prefix_k, n)
    if prefix_k and schedule.prefix_softening:
        _soften_prefix(lbg, ubg, layout.direction, prefix_k)
        _soften_prefix(lbg, ubg, layout.min_alt, prefix_k)
    if not schedule.terminal_rows_enabled:
        lbg[layout.terminal.start : layout.terminal.start + 3] = -np.inf
        ubg[layout.terminal.start : layout.terminal.start + 3] = np.inf
    _soften_prefix(lbg, ubg, layout.rule, layout.rule.count)
    lbg[layout.rule.start : layout.rule.start + problem.audit_row_count] = 0.0
    ubg[layout.rule.start : layout.rule.start + problem.audit_row_count] = np.inf
    return lbg, ubg, cpa_hard_from


def _soften_prefix(lbg: np.ndarray, ubg: np.ndarray, span: MidMpcRowSpan, count: int) -> None:
    lbg[span.start : span.start + count] = -np.inf
    ubg[span.start : span.start + count] = np.inf


def _apply_hard_window(
    lbg: np.ndarray,
    ubg: np.ndarray,
    span: MidMpcRowSpan,
    window: MidMpcHardWindow,
    horizon_steps: int,
) -> None:
    _soften_prefix(lbg, ubg, span, span.count)
    start_k = min(window.start_k, horizon_steps)
    stop_k = max(start_k, min(window.stop_k, horizon_steps))
    lbg[span.start + start_k : span.start + stop_k] = 0.0
    ubg[span.start + start_k : span.start + stop_k] = np.inf


def _apply_rule_bounds(
    lbg: np.ndarray,
    ubg: np.ndarray,
    span: MidMpcRowSpan,
    window: MidMpcHardWindow | None,
    *,
    legacy_from_k: int,
    legacy_enabled: bool,
    horizon_steps: int,
) -> None:
    if window is not None:
        _apply_hard_window(lbg, ubg, span, window, horizon_steps)
        return
    softened = min(legacy_from_k, horizon_steps) if legacy_enabled else horizon_steps
    _soften_prefix(lbg, ubg, span, softened)


def _apply_cpa_bounds(
    lbg: np.ndarray,
    ubg: np.ndarray,
    problem: MidMpcProblem,
    layout: MidMpcRowLayout,
    prefix_k: int,
    horizon_steps: int,
) -> int:
    target_capacity = layout.cpa.count // horizon_steps
    _soften_prefix(lbg, ubg, layout.cpa, layout.cpa.count)
    windows = problem.row_schedule.cpa_hard_windows
    if not windows:
        hard_from = min(problem.row_schedule.cpa_hard_from_k, horizon_steps)
        for k in range(max(prefix_k, hard_from), horizon_steps):
            start = layout.cpa.start + k * target_capacity
            lbg[start : start + len(problem.targets)] = 0.0
            ubg[start : start + len(problem.targets)] = np.inf
        return hard_from
    if len(windows) != len(problem.targets):
        raise ValueError("one CPA hard window is required per target")
    active_starts: list[int] = []
    for target_index, window in enumerate(windows):
        start_k = max(prefix_k, min(window.start_k, horizon_steps))
        stop_k = max(start_k, min(window.stop_k, horizon_steps))
        if start_k < stop_k:
            active_starts.append(start_k)
        for k in range(start_k, stop_k):
            row = layout.cpa.start + k * target_capacity + target_index
            lbg[row] = 0.0
            ubg[row] = np.inf
    return min(active_starts, default=horizon_steps)


def _cpa_slack_seed(
    config: MidMpcConfig,
    problem: MidMpcProblem,
    x0: np.ndarray,
    cpa_hard_from: int,
) -> float:
    first_hard = max(min(problem.prefix_active_k, config.horizon_steps), cpa_hard_from)
    own_x = 0.0
    own_y = 0.0
    required = 0.0
    n = config.horizon_steps
    for k in range(n):
        own_x += x0[n + k] * config.dt_s * math.cos(x0[k])
        own_y += x0[n + k] * config.dt_s * math.sin(x0[k])
        if k < first_hard:
            continue
        for target in problem.targets:
            time_s = k * config.dt_s
            target_x = target.x_m + target.sog_mps * math.cos(target.cog_rad) * time_s
            target_y = target.y_m + target.sog_mps * math.sin(target.cog_rad) * time_s
            required = max(required, problem.cpa_hard_m - math.hypot(own_x - target_x, own_y - target_y))
    return max(0.0, required) + (1.0e-3 if required > 0.0 else 0.0)


def _trajectory(raw_x: np.ndarray, config: MidMpcConfig) -> tuple[MidMpcTrajectoryPoint, ...]:
    n = config.horizon_steps
    x_m = 0.0
    y_m = 0.0
    result: list[MidMpcTrajectoryPoint] = []
    for k in range(n):
        heading = float(raw_x[k])
        speed = float(raw_x[n + k])
        result.append(
            MidMpcTrajectoryPoint(
                x_m=x_m,
                y_m=y_m,
                psi_rad=heading,
                u_mps=speed,
                t_s=k * config.dt_s,
            )
        )
        x_m += speed * config.dt_s * math.cos(heading)
        y_m += speed * config.dt_s * math.sin(heading)
    return tuple(result)


def _continuous_cpa(trajectory: tuple[MidMpcTrajectoryPoint, ...], problem: MidMpcProblem) -> tuple[float, bool]:
    if len(trajectory) < 2 or not problem.targets or problem.cpa_hard_m <= 0.0:
        return math.inf, False
    minimum = math.inf
    violated = False
    for target in problem.targets:
        target_north_speed = target.sog_mps * math.cos(target.cog_rad)
        target_east_speed = target.sog_mps * math.sin(target.cog_rad)
        first = trajectory[0]
        previous_x = first.x_m - (target.x_m + target_north_speed * first.t_s)
        previous_y = first.y_m - (target.y_m + target_east_speed * first.t_s)
        for point in trajectory[1:]:
            current_x = point.x_m - (target.x_m + target_north_speed * point.t_s)
            current_y = point.y_m - (target.y_m + target_east_speed * point.t_s)
            segment_x = current_x - previous_x
            segment_y = current_y - previous_y
            segment_squared = segment_x * segment_x + segment_y * segment_y
            closest_x = previous_x
            closest_y = previous_y
            if segment_squared > 1.0e-12:
                fraction = min(
                    max(
                        -(previous_x * segment_x + previous_y * segment_y) / segment_squared,
                        0.0,
                    ),
                    1.0,
                )
                closest_x += fraction * segment_x
                closest_y += fraction * segment_y
            distance = math.hypot(closest_x, closest_y)
            minimum = min(minimum, distance)
            violated = violated or distance < problem.cpa_hard_m
            previous_x = current_x
            previous_y = current_y
    return minimum, violated


def _strict_status(return_status: str) -> MidMpcStatus:
    if return_status == "Solve_Succeeded":
        return MidMpcStatus.CONVERGED
    if return_status == "Solved_To_Acceptable_Level":
        return MidMpcStatus.FEASIBLE_NONOPTIMAL
    if return_status in ("Maximum_CpuTime_Exceeded", "User_Requested_Stop"):
        return MidMpcStatus.TIMEOUT
    if return_status in ("Infeasible_Problem_Detected", "Restoration_Failed"):
        return MidMpcStatus.INFEASIBLE
    return MidMpcStatus.NUMERICAL_FAILURE


def _optimization_quality_passed(
    *,
    strict: bool,
    return_status: str,
    iterations: int,
    seed_objective: float,
    final_objective: float,
    seed_primal_feasible: bool,
    final_primal_feasible: bool,
    decision_change_norm: float,
    controlled_quality_stop: bool,
    accepted_iteration: int | None,
    required_improvement: float | None = None,
) -> bool:
    if not strict:
        return True
    if not math.isfinite(seed_objective) or not math.isfinite(final_objective):
        return False
    if return_status == "Solve_Succeeded":
        return True
    acceptable_exit = return_status == "Solved_To_Acceptable_Level"
    controlled_exit = return_status == "User_Requested_Stop" and controlled_quality_stop
    if not (acceptable_exit or controlled_exit):
        return False
    if controlled_exit:
        if iterations < 1:
            return False
        if not seed_primal_feasible:
            return final_primal_feasible and accepted_iteration is not None and decision_change_norm > 1.0e-6
        required_improvement = (
            required_improvement if required_improvement is not None else max(1.0e-6, abs(seed_objective) * 1.0e-8)
        )
        return (
            final_primal_feasible
            and accepted_iteration is not None
            and accepted_iteration >= 1
            and (required_improvement < 0.0 or decision_change_norm > 1.0e-6)
            and seed_objective - final_objective >= required_improvement
        )
    if iterations < 2:
        return False
    if not seed_primal_feasible:
        return final_primal_feasible and decision_change_norm > 1.0e-6
    required_improvement = (
        required_improvement if required_improvement is not None else max(1.0e-6, abs(seed_objective) * 1.0e-8)
    )
    return final_primal_feasible and (
        seed_objective - final_objective >= required_improvement or decision_change_norm >= 1.0e-3
    )


def _target_free_required_improvement(seed_objective: float) -> float:
    objective_ceiling = max(
        _TARGET_FREE_OBJECTIVE_CEILING,
        seed_objective * (1.0 + _TARGET_FREE_RELATIVE_REGRESSION),
    )
    return seed_objective - objective_ceiling


def _best_feasible_iteration(
    iterates: list[tuple[int, np.ndarray, float]],
    graph: _Graph,
    prepared: MidMpcPreparedProblem,
    *,
    tolerances: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[int, np.ndarray, float, np.ndarray] | None:
    x_tolerance, g_tolerance = tolerances if tolerances is not None else (1.0e-3, 1.0e-3)
    feasible: list[tuple[int, np.ndarray, float, np.ndarray]] = []
    for iteration, values, objective in iterates:
        if iteration < 1 or not _primal_feasible(
            values,
            prepared.lbx,
            prepared.ubx,
            tolerance=x_tolerance,
        ):
            continue
        constraints = _flat(graph.constraints(values, prepared.p))
        if _primal_feasible(
            constraints,
            prepared.lbg,
            prepared.ubg,
            tolerance=g_tolerance,
        ):
            feasible.append((iteration, values, objective, constraints))
    return min(feasible, key=lambda item: item[2], default=None)


def _prepared_primal_feasible(
    values: np.ndarray,
    constraints: np.ndarray,
    prepared: MidMpcPreparedProblem,
    *,
    tolerances: tuple[np.ndarray, np.ndarray] | None = None,
) -> bool:
    x_tolerance, g_tolerance = tolerances if tolerances is not None else (1.0e-3, 1.0e-3)
    return _primal_feasible(
        values,
        prepared.lbx,
        prepared.ubx,
        tolerance=x_tolerance,
    ) and _primal_feasible(
        constraints,
        prepared.lbg,
        prepared.ubg,
        tolerance=g_tolerance,
    )


def _strict_primal_tolerances(
    config: MidMpcConfig,
    row_layout: MidMpcRowLayout,
    prepared: MidMpcPreparedProblem,
) -> tuple[np.ndarray, np.ndarray]:
    x_tolerance = np.full(prepared.x0.size, 1.0e-4)
    x_tolerance[: 2 * config.horizon_steps] = 1.0e-6
    if config.cpa_slack_enabled:
        x_tolerance[2 * config.horizon_steps] = 1.0e-7
    if config.dir_slack_enabled:
        x_tolerance[2 * config.horizon_steps + int(config.cpa_slack_enabled)] = 1.0e-7
    g_tolerance = np.full(prepared.lbg.size, 1.0e-6)
    one_sided = np.isfinite(prepared.lbg) ^ np.isfinite(prepared.ubg)
    g_tolerance[one_sided] = 1.0e-3
    cpa = slice(row_layout.cpa.start, row_layout.cpa.start + row_layout.cpa.count)
    g_tolerance[cpa] = np.maximum(g_tolerance[cpa], 1.0e-4)
    return x_tolerance, g_tolerance


def _constraint_diagnostics(
    values: np.ndarray, lower: np.ndarray, upper: np.ndarray
) -> tuple[tuple[int, ...], tuple[int, ...], float]:
    active = tuple(
        index
        for index, (low, high) in enumerate(zip(lower, upper, strict=True))
        if math.isfinite(low) or math.isfinite(high)
    )
    tight = tuple(
        index
        for index in active
        if (math.isfinite(lower[index]) and abs(values[index] - lower[index]) <= 1.0e-3)
        or (math.isfinite(upper[index]) and abs(values[index] - upper[index]) <= 1.0e-3)
    )
    maximum = max(
        (
            max(
                lower[index] - values[index] if math.isfinite(lower[index]) else 0.0,
                values[index] - upper[index] if math.isfinite(upper[index]) else 0.0,
                0.0,
            )
            for index in active
        ),
        default=0.0,
    )
    return active, tight, maximum


def _primal_feasible(
    values: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    tolerance: float | np.ndarray = 1.0e-3,
) -> bool:
    bound_scale = np.maximum(
        np.where(np.isfinite(lower), np.abs(lower), 0.0),
        np.where(np.isfinite(upper), np.abs(upper), 0.0),
    )
    allowed = tolerance + 1.0e-10 * bound_scale
    return bool(np.isfinite(values).all() and np.all(values >= lower - allowed) and np.all(values <= upper + allowed))


def _maximum_bound_violation(values: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    return float(
        max(
            np.max(np.where(np.isfinite(lower), lower - values, 0.0), initial=0.0),
            np.max(np.where(np.isfinite(upper), values - upper, 0.0), initial=0.0),
            0.0,
        )
    )


def _flat(value: ca.DM) -> np.ndarray:
    return np.asarray(value, dtype=float).reshape(-1, order="F")
