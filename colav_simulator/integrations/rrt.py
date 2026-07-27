"""Strict ENC-aware RRT* ICOLAV adapter."""

from __future__ import annotations

import time
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seacharts.enc as senc

import colav_simulator.common.map_functions as mapf
from colav_simulator.behavior_generator import PQRRTStarParams
from colav_simulator.core import stochasticity
from colav_simulator.core.colav.colav_interface import ICOLAV
from colav_simulator.core.colav.diagnostics import (
    ColavExecutionError,
    PlanDiagnostics,
    PlanStatus,
    validate_plan,
)
from colav_simulator.core.guidances import LOSGuidance, LOSGuidanceParams
from colav_simulator.core.models import KinematicCSOGParams


class RRTStarColav(ICOLAV):
    """Plan once against the real ENC, then track the resulting RRT* path."""

    def __init__(
        self,
        max_time: float = 3.0,
        max_nodes: int = 3000,
        max_iter: int = 12000,
        goal_radius: float = 100.0,
        hazard_buffer: float = 5.0,
        seed: int = 0,
    ) -> None:
        try:
            import rrt_star_lib  # noqa: PLC0415
        except ImportError as exc:
            raise ColavExecutionError(PlanStatus.DEPENDENCY_UNAVAILABLE, str(exc)) from exc
        params = PQRRTStarParams(
            max_time=max_time,
            max_nodes=max_nodes,
            max_iter=max_iter,
            goal_radius=goal_radius,
        )
        model = KinematicCSOGParams(
            name="KinematicCSOG",
            draft=0.5,
            length=15.0,
            width=4.0,
            T_chi=6.0,
            T_U=6.0,
            r_max=np.deg2rad(10.0),
            U_min=0.0,
            U_max=15.0,
        )
        los_params = LOSGuidanceParams(K_p=0.035, R_a=25.0)
        self._rrt = rrt_star_lib.PQRRTStar(los_params, model, params)
        self._los = LOSGuidance(los_params)
        self._hazard_buffer = hazard_buffer
        self._seed = seed
        self._initialized = False
        self._last_t = 0.0
        self._waypoints = np.zeros((3, 0))
        self._trajectory = np.zeros((6, 0))
        self._inputs = np.zeros((3, 0))
        self._references = np.zeros((9, 1))
        self._diagnostics = PlanDiagnostics(
            requested_algorithm="rrt",
            executed_algorithm="rrt",
        )

    @staticmethod
    def _parse_solution(solution: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        times = solution.get("times", [])
        states = solution.get("states", [])
        inputs = solution.get("inputs", [])
        waypoints = solution.get("waypoints", [])
        if not times or not states or not waypoints:
            raise ColavExecutionError(PlanStatus.INFEASIBLE, "RRT returned no path")
        path = np.asarray(waypoints, dtype=float).T
        if path.shape[1] == 1:
            path = np.repeat(path, 2, axis=1)
        return path, np.asarray(states, dtype=float).T, np.asarray(inputs, dtype=float).T

    @staticmethod
    def _goal(
        goal_state: np.ndarray | None,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
    ) -> np.ndarray:
        if goal_state is not None and np.asarray(goal_state).size == 6:
            return np.asarray(goal_state, dtype=float)
        if waypoints.ndim != 2 or waypoints.shape[1] < 1:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, "RRT requires goal_state or waypoints")
        delta = waypoints[:, -1] - (waypoints[:, -2] if waypoints.shape[1] > 1 else ownship_state[:2])
        course = float(np.arctan2(delta[1], delta[0]))
        speed = float(speed_plan[-1]) if speed_plan.size else float(ownship_state[3])
        return np.array([waypoints[0, -1], waypoints[1, -1], course, speed, 0.0, 0.0])

    def plan(
        self,
        t: float,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],  # noqa: ARG002
        enc: senc.ENC | None = None,
        goal_state: np.ndarray | None = None,
        w: stochasticity.DisturbanceData | None = None,  # noqa: ARG002
        **kwargs: Any,
    ) -> np.ndarray:
        if enc is None:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, "RRT requires an ENC")
        start = time.perf_counter()
        try:
            if not self._initialized:
                min_depth = mapf.find_minimum_depth(float(kwargs["os_draft"]), enc)
                hazards = mapf.extract_relevant_grounding_hazards_as_union(
                    min_depth,
                    enc,
                    buffer=self._hazard_buffer,
                    show_plots=False,
                )
                triangulation = mapf.create_safe_sea_triangulation(enc, min_depth, show_plots=False)
                self._rrt.reset(self._seed)
                self._rrt.transfer_bbox(enc.bbox)
                self._rrt.transfer_enc_hazards(hazards[0])
                self._rrt.transfer_safe_sea_triangulation(triangulation)
                self._rrt.set_goal_state(self._goal(goal_state, waypoints, speed_plan, ownship_state).tolist())
                solution = self._rrt.grow_towards_goal(
                    ownship_state=ownship_state.tolist(),
                    U_d=float(ownship_state[3]),
                    initialized=False,
                    return_on_first_solution=False,
                    verbose=False,
                )
                self._waypoints, self._trajectory, self._inputs = self._parse_solution(solution)
                self._initialized = True

            dt = max(float(t - self._last_t), float(kwargs.get("dt", 0.0)), 1e-3)
            self._references = self._los.compute_references(
                self._waypoints[:2, :],
                self._waypoints[2, :],
                None,
                ownship_state,
                dt,
            )
            self._last_t = t
            self._diagnostics = PlanDiagnostics(
                status=PlanStatus.SUCCESS,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                feasible=True,
                requested_algorithm="rrt",
                executed_algorithm="rrt",
                details={"nodes": int(self._rrt.get_num_nodes()), "waypoints": int(self._waypoints.shape[1])},
            )
            return validate_plan(self._references)
        except ColavExecutionError as exc:
            self._diagnostics = PlanDiagnostics(
                status=exc.status,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                feasible=False,
                reason=str(exc),
                requested_algorithm="rrt",
                executed_algorithm="rrt",
            )
            raise
        except Exception as exc:
            self._diagnostics = PlanDiagnostics(
                status=PlanStatus.NUMERICAL_FAILURE,
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                feasible=False,
                reason=str(exc),
                requested_algorithm="rrt",
                executed_algorithm="rrt",
            )
            raise ColavExecutionError(PlanStatus.NUMERICAL_FAILURE, f"RRT failed: {exc}") from exc

    def reset(self) -> None:
        self._rrt.reset(self._seed)
        self._los.reset()
        self._initialized = False
        self._last_t = 0.0
        self._waypoints = np.zeros((3, 0))
        self._trajectory = np.zeros((6, 0))
        self._inputs = np.zeros((3, 0))
        self._references = np.zeros((9, 1))

    def get_current_plan(self) -> np.ndarray:
        if not self._trajectory.size:
            return self._references
        plan = np.zeros((9, self._trajectory.shape[1]))
        plan[:6, :] = self._trajectory
        return plan

    def get_colav_data(self) -> dict[str, Any]:
        return {
            "predicted_trajectory": self.get_current_plan(),
            "diagnostics": self._diagnostics.to_dict(),
        }

    def get_diagnostics(self) -> PlanDiagnostics:
        return self._diagnostics

    def plot_results(self, ax_map: plt.Axes, enc: senc.ENC, plt_handles: dict, **kwargs: Any) -> dict:  # noqa: ARG002
        return plt_handles
