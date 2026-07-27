"""Strict ICOLAV adapter for the official PSB-MPC Python binding."""

from __future__ import annotations

import time
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seacharts.enc as senc

import colav_simulator.common.map_functions as mapf
from colav_simulator.core import stochasticity
from colav_simulator.core.colav.colav_interface import ICOLAV
from colav_simulator.core.colav.diagnostics import (
    ColavExecutionError,
    PlanDiagnostics,
    PlanStatus,
    validate_plan,
)
from colav_simulator.core.guidances import LOSGuidance, LOSGuidanceParams


class PSBMPCColav(ICOLAV):
    """Execute PSB-MPC with real tracks and ENC polygons.

    Dependency or solver failures are surfaced as errors. This adapter never
    substitutes another planner.
    """

    def __init__(
        self,
        period: float = 5.0,
        prediction_dt: float = 0.5,
        prediction_horizon: float = 15.0,
        polygon_simplification: float = 2.0,
    ) -> None:
        try:
            import PSBMPCInterface as psbmpc  # noqa: PLC0415
        except ImportError as exc:
            raise ColavExecutionError(PlanStatus.DEPENDENCY_UNAVAILABLE, str(exc)) from exc

        self._lib = psbmpc
        self._period = period
        self._prediction_dt = prediction_dt
        self._prediction_horizon = prediction_horizon
        self._polygon_simplification = polygon_simplification
        self._los = LOSGuidance(LOSGuidanceParams())
        self._solver = None
        self._ship_dimensions: tuple[float, float, float] | None = None
        self._polygons: list[np.ndarray] = []
        self._enc_identity: int | None = None
        self._last_run = -np.inf
        self._speed_offset = 1.0
        self._course_offset = 0.0
        self._trajectory = np.zeros((9, 1))
        self._diagnostics = PlanDiagnostics(
            requested_algorithm="psbmpc",
            executed_algorithm="psbmpc",
        )

    def _initialize_solver(self, length: float, width: float, draft: float, dt_sim: float) -> None:
        dimensions = (length, width, draft)
        if self._solver is not None and dimensions == self._ship_dimensions:
            return
        try:
            ship = self._lib.KinematicShip(
                length,
                width,
                draft,
                15.0,
                0.0,
                self._prediction_horizon,
                dt_sim,
            )
            params = self._lib.PSBMPCParams()
            cpe = self._lib.CPE(self._lib.CPEMethod.CE)
            self._solver = self._lib.PSBMPC(ship, cpe, params)
            self._ship_dimensions = dimensions
        except Exception as exc:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"PSB-MPC initialization failed: {exc}") from exc

    def _extract_polygons(self, enc: senc.ENC, draft: float) -> list[np.ndarray]:
        if self._enc_identity == id(enc):
            return self._polygons
        min_depth = mapf.find_minimum_depth(draft, enc)
        hazards = mapf.extract_relevant_grounding_hazards_as_union(min_depth, enc, buffer=2.0)
        polygons: list[np.ndarray] = []
        for hazard in hazards:
            simplified = hazard.simplify(self._polygon_simplification, preserve_topology=True)
            geometries = simplified.geoms if hasattr(simplified, "geoms") else [simplified]
            for polygon in geometries:
                if polygon.is_empty or not hasattr(polygon, "exterior"):
                    continue
                coordinates = np.asarray(polygon.exterior.coords, dtype=float)
                polygons.append(coordinates[:, ::-1].copy())
        self._polygons = polygons
        self._enc_identity = id(enc)
        return polygons

    def _tracked_obstacles(self, do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]]) -> list[Any]:
        try:
            n_scenarios = self._solver.get_PSBMPCParams().get_par_int(1)
        except Exception:
            n_scenarios = 5
        tracked = []
        for identifier, state, covariance, length, width in do_list:
            augmented = np.array(
                [
                    state[0],
                    state[1],
                    state[2],
                    state[3],
                    length / 2.0,
                    length / 2.0,
                    width / 2.0,
                    width / 2.0,
                    float(identifier),
                ],
                dtype=float,
            )
            flat_covariance = self._lib.flatten(np.asarray(covariance, dtype=float))
            probabilities = np.full(n_scenarios, 1.0 / n_scenarios)
            tracked.append(
                self._lib.TrackedObstacle(
                    augmented,
                    flat_covariance,
                    probabilities,
                    False,
                    self._prediction_horizon,
                    self._prediction_dt,
                )
            )
        return tracked

    def plan(
        self,
        t: float,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],
        enc: senc.ENC | None = None,
        goal_state: np.ndarray | None = None,  # noqa: ARG002
        w: stochasticity.DisturbanceData | None = None,
        **kwargs: Any,
    ) -> np.ndarray:
        if enc is None:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, "PSB-MPC requires an ENC")
        start = time.perf_counter()
        dt_sim = max(float(kwargs.get("dt", self._prediction_dt)), 1e-3)
        self._initialize_solver(
            float(kwargs["os_length"]),
            float(kwargs["os_width"]),
            float(kwargs["os_draft"]),
            dt_sim,
        )
        references = self._los.compute_references(waypoints, speed_plan, None, ownship_state, dt_sim)
        if t - self._last_run >= self._period or t <= 1e-9:
            try:
                wind_speed = float(w.wind.get("speed", 0.0)) if w and w.wind else 0.0
                wind_direction = float(w.wind.get("direction", 0.0)) if w and w.wind else 0.0
                result = self._solver.calculate_optimal_offsets(
                    u_d=float(references[3, 0]),
                    chi_d=float(references[2, 0]),
                    waypoints=waypoints,
                    ownship_state=np.array(
                        [ownship_state[0], ownship_state[1], ownship_state[2], ownship_state[3]],
                        dtype=float,
                    ),
                    V_w=wind_speed,
                    wind_direction=np.array(
                        [np.cos(wind_direction), np.sin(wind_direction)],
                        dtype=float,
                    ),
                    polygons=self._extract_polygons(enc, float(kwargs["os_draft"])),
                    obstacles=self._tracked_obstacles(do_list),
                    new_static_obstacle_data=t <= 1e-9,
                    disable=False,
                )
                self._speed_offset = float(result.u_opt)
                self._course_offset = float(result.chi_opt)
                raw_trajectory = np.asarray(result.predicted_trajectory)
                if raw_trajectory.size:
                    self._trajectory = raw_trajectory
                self._last_run = t
            except Exception as exc:
                self._diagnostics = PlanDiagnostics(
                    status=PlanStatus.NUMERICAL_FAILURE,
                    elapsed_ms=(time.perf_counter() - start) * 1000.0,
                    feasible=False,
                    reason=str(exc),
                    requested_algorithm="psbmpc",
                    executed_algorithm="psbmpc",
                )
                raise ColavExecutionError(PlanStatus.NUMERICAL_FAILURE, f"PSB-MPC solve failed: {exc}") from exc
        references[2, 0] += self._course_offset
        references[3, 0] *= self._speed_offset
        self._diagnostics = PlanDiagnostics(
            status=PlanStatus.SUCCESS,
            elapsed_ms=(time.perf_counter() - start) * 1000.0,
            feasible=True,
            requested_algorithm="psbmpc",
            executed_algorithm="psbmpc",
            details={"polygon_count": len(self._polygons), "track_count": len(do_list)},
        )
        return validate_plan(references)

    def reset(self) -> None:
        self._los.reset()
        if self._solver is not None:
            self._solver.reset()
        self._last_run = -np.inf
        self._speed_offset = 1.0
        self._course_offset = 0.0
        self._trajectory = np.zeros((9, 1))

    def get_current_plan(self) -> np.ndarray:
        return self._trajectory

    def get_colav_data(self) -> dict[str, Any]:
        return {
            "predicted_trajectory": self._trajectory,
            "diagnostics": self._diagnostics.to_dict(),
        }

    def get_diagnostics(self) -> PlanDiagnostics:
        return self._diagnostics

    def plot_results(self, ax_map: plt.Axes, enc: senc.ENC, plt_handles: dict, **kwargs: Any) -> dict:  # noqa: ARG002
        return plt_handles
