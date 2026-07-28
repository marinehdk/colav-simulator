"""ICOLAV adapter for the official native SB-MPC implementation."""

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
    PlannerTrace,
    PlanStatus,
    validate_plan,
)
from colav_simulator.core.guidances import LOSGuidance, LOSGuidanceParams

OFFICIAL_REPOSITORY = "https://github.com/ntnu-itk-autonomous-ship-lab/psbmpc"
PYBIND_REPOSITORY = "https://github.com/ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc"
PYBIND_COMMIT = "367dad8809424b21c013512308de2a07bd184464"
CORE_COMMIT = "8b78d009d173db20af28e1a2a662417c8d893f12"


class OfficialSBMPCReference(ICOLAV):
    """Run the pinned official C++ SB-MPC as a differential reference."""

    def __init__(
        self,
        period: float = 5.0,
        speed_time_constant: float = 1.44,
        course_time_constant: float = 0.92,
        waypoint_acceptance_radius: float = 5.0,
        los_lookahead_distance: float = 66.0,
        los_integral_gain: float = 0.0,
        polygon_simplification: float = 2.0,
    ) -> None:
        try:
            import PSBMPCInterface as psbmpc  # noqa: PLC0415
        except ImportError as exc:
            raise ColavExecutionError(PlanStatus.DEPENDENCY_UNAVAILABLE, str(exc)) from exc

        self._lib = psbmpc
        self._period = period
        self._ship_model_parameters = (
            speed_time_constant,
            course_time_constant,
            waypoint_acceptance_radius,
            los_lookahead_distance,
            los_integral_gain,
        )
        self._polygon_simplification = polygon_simplification
        self._los = LOSGuidance(LOSGuidanceParams())
        self._solver = None
        self._params = None
        self._obstacle_predictor = None
        self._ship_dimensions: tuple[float, float] | None = None
        self._polygons: list[np.ndarray] = []
        self._enc_identity: int | None = None
        self._static_data_dirty = True
        self._last_run = -np.inf
        self._speed_offset = 1.0
        self._course_offset = 0.0
        self._command = np.zeros((9, 1))
        self._trajectory = np.zeros((9, 1))
        self._solve_id = 0
        self._diagnostics = PlanDiagnostics(
            requested_algorithm="sbmpc_reference",
            executed_algorithm="sbmpc_reference",
        )
        self._planner_trace = PlannerTrace("sbmpc_reference", 0, 0.0, False)

    def _initialize_solver(self, length: float, width: float) -> None:
        dimensions = (length, width)
        if self._solver is not None and dimensions == self._ship_dimensions:
            return
        try:
            ship = self._lib.KinematicShip(
                length,
                width,
                *self._ship_model_parameters,
            )
            self._params = self._lib.SBMPCParams()
            self._solver = self._lib.SBMPC(ship, self._params)
            self._obstacle_predictor = self._lib.ObstaclePredictor()
            self._ship_dimensions = dimensions
        except Exception as exc:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"SB-MPC initialization failed: {exc}") from exc

    def _extract_polygons(self, enc: senc.ENC | None, draft: float) -> list[np.ndarray]:
        if enc is None:
            if self._enc_identity is not None or self._polygons:
                self._polygons = []
                self._enc_identity = None
                self._static_data_dirty = True
            return self._polygons
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
        self._static_data_dirty = True
        return polygons

    def _predict_obstacles(
        self,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],
        ownship_state: np.ndarray,
    ) -> list[Any]:
        horizon = self._params.get_par_double(0)
        prediction_dt = self._params.get_par_double(1)
        obstacles = []
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
            obstacles.append(
                self._lib.TrackedObstacle(
                    augmented,
                    self._lib.flatten(np.asarray(covariance, dtype=float)),
                    False,
                    horizon,
                    prediction_dt,
                )
            )
        if not obstacles:
            return []
        return self._obstacle_predictor.sbmpc_call(
            obstacles,
            ownship_state,
            self._params,
            self._lib.PathPredictionShape.SMOOTH,
        )

    @staticmethod
    def _map_native_trajectory(raw_trajectory: np.ndarray, dt: float) -> np.ndarray:
        raw = np.asarray(raw_trajectory, dtype=float)
        if raw.ndim != 2 or raw.shape[0] != 4 or raw.shape[1] < 1:
            raise ColavExecutionError(
                PlanStatus.NUMERICAL_FAILURE,
                f"Native SB-MPC trajectory must have shape (4, N>=1), got {raw.shape}",
            )
        mapped = np.zeros((9, raw.shape[1]))
        mapped[0:3] = raw[0:3]
        mapped[3] = raw[3]
        if raw.shape[1] > 1:
            course = np.unwrap(raw[2])
            speed = raw[3]
            north_velocity = speed * np.cos(course)
            east_velocity = speed * np.sin(course)
            course_rate = np.gradient(course, dt)
            mapped[5] = course_rate
            mapped[6] = np.gradient(north_velocity, dt)
            mapped[7] = np.gradient(east_velocity, dt)
            mapped[8] = course_rate
        return validate_plan(mapped)

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
        started = time.perf_counter()
        self._initialize_solver(float(kwargs["os_length"]), float(kwargs["os_width"]))
        dt_sim = max(float(kwargs.get("dt", 0.5)), 1e-3)
        references = self._los.compute_references(waypoints, speed_plan, None, ownship_state, dt_sim)
        solver_executed = t - self._last_run >= self._period or t <= 1e-9

        if solver_executed:
            try:
                wind_speed = float(w.wind.get("speed", 0.0)) if w and w.wind else 0.0
                wind_direction = float(w.wind.get("direction", 0.0)) if w and w.wind else 0.0
                ownship_native = np.array(
                    [
                        ownship_state[0],
                        ownship_state[1],
                        ownship_state[2],
                        np.linalg.norm(ownship_state[3:5]),
                    ],
                    dtype=float,
                )
                polygons = self._extract_polygons(enc, float(kwargs["os_draft"]))
                obstacles = self._predict_obstacles(do_list, ownship_native)

                # The pinned pybind labels these final arguments in the opposite
                # order from the underlying C++ signature. Positional order here
                # follows SBMPC::calculate_optimal_offsets_py(new_static, disable).
                result = self._solver.calculate_optimal_offsets(
                    float(references[3, 0]),
                    float(references[2, 0]),
                    np.asarray(waypoints, dtype=float),
                    ownship_native,
                    wind_speed,
                    np.array([np.cos(wind_direction), np.sin(wind_direction)], dtype=float),
                    polygons,
                    obstacles,
                    self._static_data_dirty,
                    False,
                )
                self._speed_offset = float(result.u_opt)
                self._course_offset = float(result.chi_opt)
                prediction_dt = float(self._params.get_par_double(1))
                self._trajectory = self._map_native_trajectory(result.predicted_trajectory, prediction_dt)
                self._static_data_dirty = False
                self._last_run = t
                self._solve_id += 1
            except ColavExecutionError:
                raise
            except Exception as exc:
                self._diagnostics = PlanDiagnostics(
                    status=PlanStatus.NUMERICAL_FAILURE,
                    elapsed_ms=(time.perf_counter() - started) * 1000.0,
                    feasible=False,
                    reason=str(exc),
                    requested_algorithm="sbmpc_reference",
                    executed_algorithm="sbmpc_reference",
                )
                raise ColavExecutionError(PlanStatus.NUMERICAL_FAILURE, f"Official SB-MPC solve failed: {exc}") from exc

        references[2, 0] += self._course_offset
        references[3, 0] *= self._speed_offset
        self._command = validate_plan(references)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        provenance = {
            "implementation": "official_native_sbmpc",
            "repository": OFFICIAL_REPOSITORY,
            "python_binding_repository": PYBIND_REPOSITORY,
            "pybind_commit": PYBIND_COMMIT,
            "core_commit": CORE_COMMIT,
            "track_count": len(do_list),
            "polygon_count": len(self._polygons),
        }
        self._diagnostics = PlanDiagnostics(
            status=PlanStatus.SUCCESS,
            elapsed_ms=elapsed_ms,
            feasible=True,
            requested_algorithm="sbmpc_reference",
            executed_algorithm="sbmpc_reference",
            details=provenance,
        )
        self._planner_trace = PlannerTrace(
            algorithm_id="sbmpc_reference",
            solve_id=self._solve_id,
            sim_time=float(t),
            solver_executed=solver_executed,
            elapsed_ms=elapsed_ms,
            predicted_trajectory=self._trajectory,
            horizon_dt_s=float(self._params.get_par_double(1)),
            selected_command={
                "course_rad": float(self._command[2, 0]),
                "speed_mps": float(self._command[3, 0]),
                "course_offset_rad": self._course_offset,
                "speed_scale": self._speed_offset,
            },
            algorithm_details=provenance,
        )
        return self._command

    def reset(self) -> None:
        self._los.reset()
        self._solver = None
        self._params = None
        self._obstacle_predictor = None
        self._ship_dimensions = None
        self._polygons = []
        self._enc_identity = None
        self._static_data_dirty = True
        self._last_run = -np.inf
        self._speed_offset = 1.0
        self._course_offset = 0.0
        self._command = np.zeros((9, 1))
        self._trajectory = np.zeros((9, 1))
        self._solve_id = 0

    def get_current_plan(self) -> np.ndarray:
        return self._command

    def get_colav_data(self) -> dict[str, Any]:
        return {
            "planner": self._planner_trace.to_dict(),
            "diagnostics": self._diagnostics.to_dict(),
        }

    def get_diagnostics(self) -> PlanDiagnostics:
        return self._diagnostics

    def plot_results(self, ax_map: plt.Axes, enc: senc.ENC, plt_handles: dict, **kwargs: Any) -> dict:  # noqa: ARG002
        return plt_handles
