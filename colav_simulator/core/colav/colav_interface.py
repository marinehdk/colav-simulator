"""colav_interface.py.

Summary:
Contains the interface used by all COLAV planning algorithms that
wants to be run with the COLAV simulator.

To add a new COLAV planning algorithm internally to the simulator:

1: Import necessary algorithm modules in this file.
2: Add the algorithm name as a type to the COLAVType enum.
3: Add the algorithm as an optional entry to the LayerConfig class.
4: Create a new wrapper class for your COLAV algorithm, which implements
   (inherits as this is python) the ICOLAV interface. It should take in a Config
   object as input.
5: Add an entry in the COLAVBuilder class, which builds it from config if the
   type matches. See an example for the Kuwata VO and SBMPC below.
6: Add configuration support for the algorithm by expanding the `colav` entry
   under `schemas/scenario.yaml` in the `ship_list` section.

Alternatively (AND EASIER), to be able to use a third-party COLAV planning algorithm:

1: Import this module in your own code.
2: Create a wrapper class for your COLAV algorithm that implements the ICOLAV interface.
3: Provide your third-party algorithm to the simulator at run-time (see Simulator class in simulator.py).

Author: Trym Tengesdal
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import matplotlib.pyplot as plt
import numpy as np
import seacharts.enc as senc

import colav_simulator.common.config_parsing as cp
import colav_simulator.common.math_functions as mf
import colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo as kvo
import colav_simulator.core.colav.sbmpc.sbmpc as sb_mpc
import colav_simulator.core.guidances as guidance
from colav_simulator.core import stochasticity
from colav_simulator.core.colav.diagnostics import PlanDiagnostics, PlannerTrace, PlanStatus


class COLAVType(Enum):
    """Enum for the different COLAV algorithms currently compatible with the simulator."""

    VO = 0  # Kuwata VO, with LOS guidance to provide velocity references.
    SBMPC = 1  # SB-MPC, provide trajectory offsets


@dataclass
class LayerConfig:
    """Configuration class for the parameters of a single layer/algorithm.

    In the COLAV planning hierarchy, each layer represents a specific COLAV
    algorithm, and the parameters are specific to the algorithm. For example
    with three layers:

    - The first layer will be a static obstacle collision-free planner, run
      e.g. only at the start of the mission.
    - The second layer is a mid-level MPC-based COLAV system, that can handle
      both static and dynamic obstacles (and the COLREGS).
    - The third layer is a lower level reactive VO-based COLAV, that handles
      emergency maneuvers and close encounters if the mid-level planner fails.

    NOTE: This class is typically only used when you want to configure the
          COLAV system parameters from a scenario file. However, an easier
          option is to configure the COLAV system externally, and pass the
          COLAV object to the simulator at run-time (see examples/dummy_planner.py
          for an example of this). This is recommended if you want to use a
          third-party COLAV algorithm.
    """

    vo: kvo.VOParams | None = field(default_factory=lambda: kvo.VOParams())
    los: guidance.LOSGuidanceParams | None = None
    sbmpc: sb_mpc.SBMPCParams | None = None

    @classmethod
    def from_dict(cls, config_dict: dict) -> "LayerConfig":  # noqa: D102
        config = LayerConfig()
        if "vo" in config_dict:
            config.vo = kvo.VOParams.from_dict(config_dict["vo"])

        if "los" in config_dict:
            config.los = cp.convert_settings_dict_to_dataclass(guidance.LOSGuidanceParams, config_dict["los"])

        if "sbmpc" in config_dict:
            config.sbmpc = cp.convert_settings_dict_to_dataclass(sb_mpc.SBMPCParams, config_dict["sbmpc"])

        return config

    def to_dict(self) -> dict:  # noqa: D102
        config_dict = {}

        if self.vo is not None:
            config_dict["vo"] = self.vo.to_dict()

        if self.los is not None:
            config_dict["los"] = self.los.to_dict()

        if self.sbmpc is not None:
            config_dict["sbmpc"] = self.sbmpc.to_dict()

        return config_dict


@dataclass
class Config:
    """Configuration class for managing COLAV system parameters for all considered layers in the COLAV hierarchy."""

    name: COLAVType = COLAVType.VO
    layer1: LayerConfig = field(default_factory=lambda: LayerConfig())
    layer2: LayerConfig | None = None
    layer3: LayerConfig | None = None

    @classmethod
    def from_dict(cls, config_dict: dict) -> "Config":  # noqa: D102
        config = Config(name=COLAVType[config_dict["name"]], layer1=LayerConfig.from_dict(config_dict["layer1"]))

        if "layer2" in config_dict:
            config.layer2 = LayerConfig.from_dict(config_dict["layer2"])

        if "layer3" in config_dict:
            config.layer3 = LayerConfig.from_dict(config_dict["layer3"])

        return config

    def to_dict(self) -> dict:  # noqa: D102
        config_dict = {"name": self.name.name, "layer1": self.layer1.to_dict()}

        if self.layer2 is not None:
            config_dict["layer2"] = self.layer2.to_dict()

        if self.layer3 is not None:
            config_dict["layer3"] = self.layer3.to_dict()

        return config_dict


class ICOLAV(ABC):
    def get_diagnostics(self) -> PlanDiagnostics:
        """Return normalized diagnostics for the latest planner invocation."""
        return PlanDiagnostics(
            requested_algorithm=self.__class__.__name__,
            executed_algorithm=self.__class__.__name__,
        )

    def get_decision_space_snapshot(self) -> dict | None:
        """Return an optional dense planner visualization snapshot."""
        return None

    @abstractmethod
    def plan(
        self,
        t: float,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],
        enc: senc.ENC | None = None,
        goal_state: np.ndarray | None = None,  # noqa: ARG002
        w: stochasticity.DisturbanceData | None = None,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> np.ndarray:
        """Main COLAV planning function.

        Args:
            t (float): The current time since the start of the simulation.
            waypoints (np.ndarray): The waypoints to follow, typically used for
                COLAV planners assuming a nominal path/trajectory as input.
                Dimensions: [2, N] composed of the waypoint NE coordinates.
            speed_plan (np.ndarray): Reference speeds at each waypoint, typically
                used for COLAV planners assuming a nominal path/trajectory as
                input.
            ownship_state (np.ndarray): The ownship state [x, y, psi, u, v, r]^T.
                Used as start state in case of high level planners.
            do_list (list[tuple[int, np.ndarray, np.ndarray, float, float]]): List
                of dynamic obstacles in the vicinity of the ship, on the format
                (ID, state, covariance, length, width). The state is on the
                format [x, y, Vx, Vy]^T.
            enc (senc.ENC | None): The relevant Electronic Navigational Chart
                (ENC) for static obstacle info.
            goal_state (np.ndarray | None): The goal state [x, y, psi, u, v, r]^T,
                typically used for high level COLAV planners where no nominal
                path/trajectory is assumed.
            w (stochasticity.DisturbanceData | None): The stochastic disturbance
                data.
            **kwargs: Additional arguments to the COLAV planning algorithm, e.g.
                the own-ship length.

        Returns:
            np.ndarray: The planned poses, velocities and accelerations
                (vstacked as a 9 x N array, N >= 1 being the number of samples)
                from the COLAV planning algorithm. Must be compatible with the
                control system you are using.
        """

    @abstractmethod
    def reset(self):
        """Resets the COLAV planning algorithm to its initial state."""

    @abstractmethod
    def get_current_plan(self) -> np.ndarray:
        """Returns the current planned trajectory.

        Returns:
            np.ndarray: The most recent planned poses, velocities and
                accelerations (vstacked as a 9 x N array, N >= 1 being the
                number of samples) over the COLAV planning horizon (if any).
                Must be compatible with the control system you are using.
        """

    @abstractmethod
    def get_colav_data(self) -> dict:
        """Returns the plotting data relevant for the COLAV planning algorithm.

        This includes e.g. the predicted trajectory, considered obstacles,
        optimal inputs etc. Used for plotting and logging.

        Returns:
            dict: The relevant data used in the COLAV planning algorithm.
        """

    @abstractmethod
    def plot_results(
        self,
        ax_map: plt.Axes,
        enc: senc.ENC,
        plt_handles: dict,
        **kwargs,  # noqa: ARG002
    ) -> dict:
        """Plots the COLAV planning algorithm results data.

        E.g. the predicted trajectory, considered obstacles, optimal inputs
        etc.

        Args:
            ax_map (plt.Axes): Map axes to plot on.
            enc (senc.ENC): ENC object.
            plt_handles (dict): Dictionary of plot handles.
            **kwargs: Additional keyword arguments.

        Returns:
            dict: Dictionary of plot handles.
        """


class VOWrapper(ICOLAV):
    """The VO wrapper is a Kuwata VO-based reactive COLAV planning system.

    Where LOS-guidance is used to provide velocity references.
    """

    def __init__(self, config: Config, **kwargs) -> None:  # noqa: ARG002
        if config.layer1.vo is None:
            msg = "Kuwata VO must be on the first layer for the VO wrapper."
            raise ValueError(msg)
        self._vo = kvo.VO(config.layer1.vo)

        if not (config.layer2 and config.layer2.los is not None):
            msg = "LOS guidance must be on the second layer for the VO wrapper."
            raise ValueError(msg)
        self._los = guidance.LOSGuidance(config.layer2.los)

        self._t_prev = 0.0
        self._initialized = False
        self._diagnostics = PlanDiagnostics(
            requested_algorithm="vo",
            executed_algorithm="vo",
        )
        self._solve_id = 0
        self._planner_trace = PlannerTrace("vo", 0, 0.0, False)
        self._decision_space_solve_id = 0
        self._decision_space_sim_time = 0.0

    def reset(self):
        """Resets the VO-COLAV to its initial state."""
        self._t_prev = 0.0
        self._initialized = False
        self._vo.reset()
        self._los.reset()
        self._solve_id = 0
        self._planner_trace = PlannerTrace("vo", 0, 0.0, False)
        self._decision_space_solve_id = 0
        self._decision_space_sim_time = 0.0
        self._diagnostics = PlanDiagnostics(
            requested_algorithm="vo",
            executed_algorithm="vo",
        )

    def plan(
        self,
        t: float,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],
        enc: senc.ENC | None = None,
        goal_state: np.ndarray | None = None,  # noqa: ARG002
        w: stochasticity.DisturbanceData | None = None,  # noqa: ARG002
        **kwargs,
    ) -> np.ndarray:
        started = time.perf_counter()
        if not self._initialized:
            self._t_prev = t
            self._initialized = True

        references = self._los.compute_references(waypoints, speed_plan, None, ownship_state, t - self._t_prev)
        self._t_prev = t
        course_ref = references[2, 0]
        speed_ref = references[3, 0]
        vel_ref = np.array([speed_ref * np.cos(course_ref), speed_ref * np.sin(course_ref)])
        plan = self._vo.plan(
            t,
            vel_ref,
            ownship_state,
            do_list,
            enc,
            os_length=kwargs.get("os_length"),
            os_width=kwargs.get("os_width"),
            os_course_time_constant_s=kwargs.get("os_course_time_constant_s"),
            os_speed_time_constant_s=kwargs.get("os_speed_time_constant_s"),
            os_max_turn_rate_radps=kwargs.get("os_max_turn_rate_radps"),
        )
        solver_executed = self._vo.plan_executed
        if solver_executed:
            self._solve_id += 1
            self._decision_space_solve_id = self._solve_id
            self._decision_space_sim_time = float(t)
        debug = self._vo.get_debug_data()
        feasible = self._vo.feasible
        status = PlanStatus.SUCCESS if feasible else PlanStatus.INFEASIBLE
        reason = None if feasible else "fallback=stop_nonpaper_wrapper"
        trace_plan = plan.copy()
        trace_plan[0:2, 0] = ownship_state[0:2]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._diagnostics = PlanDiagnostics(
            status=status,
            elapsed_ms=elapsed_ms,
            feasible=feasible,
            objective=debug["objective"],
            reason=reason,
            requested_algorithm="vo",
            executed_algorithm="vo",
            fallback_used=not feasible,
            details={
                "track_count": len(do_list),
                "dynamic_hazard_count": debug["dynamic_hazard_count"],
                "static_hazard_count": debug["static_hazard_count"],
                "active_rules": debug["active_rules"],
                "track_metrics": debug["track_metrics"],
                "base_vo_count": debug["base_vo_count"],
                "colregs_v1_count": debug["colregs_v1_count"],
                "crossing_commitment_count": debug["crossing_commitment_count"],
                "hard_constraint_count": debug["hard_constraint_count"],
                "wvo_only_count": debug["wvo_only_count"],
                "preferred_clearance_count": debug["preferred_clearance_count"],
                "feasible_candidate_count": debug["feasible_candidate_count"],
                "selected_in_base_vo": debug["selected_in_base_vo"],
                "selected_in_colregs_v1": debug["selected_in_colregs_v1"],
                "current_in_base_vo": debug["current_in_base_vo"],
                "stand_on_hold_active": debug["stand_on_hold_active"],
                "selected_in_wvo_only": debug["selected_in_wvo_only"],
                "selected_in_preferred_clearance": debug[
                    "selected_in_preferred_clearance"
                ],
                "hard_hull_clearance_m": debug["hard_hull_clearance_m"],
                "preferred_hull_clearance_m": debug[
                    "preferred_hull_clearance_m"
                ],
                "ownship_length_m": debug["ownship_length_m"],
                "ownship_width_m": debug["ownship_width_m"],
                "selected_ttc_s": debug["selected_ttc_s"],
                "reference_velocity_error_mps": debug["reference_velocity_error_mps"],
                "minimum_feasible_ttc_s": debug["minimum_feasible_ttc_s"],
                "crossing_commitment_active": debug["crossing_commitment_active"],
                "crossing_commitment_state": debug["crossing_commitment_state"],
                "emergency_rule_relaxation": debug["emergency_rule_relaxation"],
                "overtaking_state": debug["overtaking_state"],
                "overtaking_target_id": debug["overtaking_target_id"],
                "overtaking_along_track_m": debug["overtaking_along_track_m"],
                "overtaking_cross_track_m": debug["overtaking_cross_track_m"],
                "overtaking_relative_speed_mps": debug["overtaking_relative_speed_mps"],
                "overtaking_progress_relaxed": debug["overtaking_progress_relaxed"],
                "overtaking_release_count": debug["overtaking_release_count"],
                "overtaking_entry_tcpa_s": debug["overtaking_entry_tcpa_s"],
                "solve_period_s": debug["solve_period_s"],
                "fallback": debug["fallback"],
                "fallback_reason": debug["fallback_reason"],
                "solver_executed": solver_executed,
                "solve_id": self._solve_id,
            },
        )
        self._planner_trace = PlannerTrace(
            algorithm_id="vo",
            solve_id=self._solve_id,
            sim_time=float(t),
            solver_executed=solver_executed,
            status=status,
            feasible=feasible,
            reason=reason,
            elapsed_ms=elapsed_ms,
            objective=debug["objective"],
            predicted_trajectory=trace_plan,
            selected_command={
                "course_rad": float(plan[2, 0]),
                "speed_mps": float(plan[3, 0]),
            },
            algorithm_details=debug,
        )
        return plan

    def get_diagnostics(self) -> PlanDiagnostics:
        return self._diagnostics

    def get_decision_space_snapshot(self) -> dict | None:
        snapshot = self._vo.get_decision_space_snapshot()
        if snapshot is None or self._decision_space_solve_id < 1:
            return None
        return {
            **snapshot,
            "solve_id": self._decision_space_solve_id,
            "sim_time_s": self._decision_space_sim_time,
        }

    def get_current_plan(self) -> np.ndarray:
        return self._vo.get_current_plan()

    def get_colav_data(self) -> dict:
        return {
            "planner": self._planner_trace.to_dict(),
            "vo": self._vo.get_debug_data(),
        }

    def plot_results(self, ax_map: plt.Axes, enc: senc.ENC, plt_handles: dict, **kwargs) -> dict:  # noqa: ARG002
        return plt_handles


class SBMPCWrapper(ICOLAV):
    """SBMPC is here implemented as a COLAV planning algorithm that provides trajectory offsets to the nominal LOS guidance.

    NOTE: No land consideration is added in this implementation.
    """

    def __init__(
        self,
        config: Config = Config(
            name=COLAVType.SBMPC,
            layer1=LayerConfig(sbmpc=sb_mpc.SBMPCParams()),
            layer2=LayerConfig(los=guidance.LOSGuidanceParams()),
        ),
        **kwargs,  # noqa: ARG002
    ) -> None:
        if config.layer1.sbmpc is None:
            msg = "SBMPC must be on the first layer for the SBMPC wrapper."
            raise ValueError(msg)
        self._sbmpc = sb_mpc.SBMPC(config.layer1.sbmpc)

        if config.layer2.los is None:
            msg = "LOS guidance must be on the second layer for the SBMPC wrapper."
            raise ValueError(msg)
        self._los = guidance.LOSGuidance(config.layer2.los)

        self._t_prev = 0.0
        self._initialized = False
        self._t_run_sbmpc_last = 0.0
        self._speed_os_best = 1.0
        self._course_os_best = 0.0
        self._course_command = 0.0
        self._overtaking_commitment_active = False
        self._overtaking_recovery_active = False
        self._overtaking_recovery_base_course = 0.0
        self._diagnostics = PlanDiagnostics(
            requested_algorithm="sbmpc",
            executed_algorithm="sbmpc",
        )
        self._solve_id = 0
        self._planner_trace = PlannerTrace("sbmpc", 0, 0.0, False)

    def reset(self):
        """Resets the SBMPC-COLAV to its initial state."""
        self._t_prev = 0.0
        self._initialized = False
        self._t_run_sbmpc_last = 0.0
        self._speed_os_best = 1.0
        self._course_os_best = 0.0
        self._course_command = 0.0
        self._overtaking_commitment_active = False
        self._overtaking_recovery_active = False
        self._overtaking_recovery_base_course = 0.0
        self._sbmpc.reset()
        self._los.reset()
        self._solve_id = 0
        self._planner_trace = PlannerTrace("sbmpc", 0, 0.0, False)
        self._diagnostics = PlanDiagnostics(
            requested_algorithm="sbmpc",
            executed_algorithm="sbmpc",
        )

    def plan(
        self,
        t: float,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        ownship_state: np.ndarray,
        do_list: list[tuple[int, np.ndarray, np.ndarray, float, float]],
        enc: senc.ENC | None = None,
        goal_state: np.ndarray | None = None,  # noqa: ARG002
        w: stochasticity.DisturbanceData | None = None,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> np.ndarray:
        started = time.perf_counter()
        if not self._initialized or t < 0.0001:
            self._t_prev = t
            self._initialized = True

        references = self._los.compute_references(waypoints, speed_plan, None, ownship_state, t - self._t_prev)
        self._t_prev = t
        course_ref = references[2, 0]
        speed_ref = references[3, 0]
        if self._solve_id == 0:
            self._course_command = course_ref
        solver_executed = t - self._t_run_sbmpc_last >= 5.0
        if solver_executed:
            self._speed_os_best, self._course_os_best = self._sbmpc.get_optimal_ctrl_offset(
                speed_ref, course_ref, ownship_state, do_list, enc
            )
            candidate_course_command = self._sbmpc.get_course_command(
                self._course_os_best
            )
            debug = self._sbmpc.get_debug_data()
            commitment_active = bool(
                debug["overtaking_commitment_target_ids"]
            )
            if self._overtaking_commitment_active and not commitment_active:
                self._overtaking_recovery_active = True
            if commitment_active:
                self._overtaking_recovery_active = False
                self._overtaking_recovery_base_course = float(
                    debug["course_base_rad"]
                )
            if self._overtaking_recovery_active:
                course_delta = mf.wrap_angle_to_pmpi(
                    candidate_course_command - self._course_command
                )
                max_recovery_step = np.deg2rad(15.0)
                applied_delta = np.clip(
                    course_delta, -max_recovery_step, max_recovery_step
                )
                self._course_command = mf.wrap_angle_to_pmpi(
                    self._course_command + applied_delta
                )
                nominal_base_error = abs(
                    mf.wrap_angle_to_pmpi(
                        course_ref - self._overtaking_recovery_base_course
                    )
                )
                if (
                    nominal_base_error <= np.deg2rad(5.0)
                    and abs(course_delta) <= max_recovery_step
                ):
                    self._overtaking_recovery_active = False
            else:
                self._course_command = candidate_course_command
            self._overtaking_commitment_active = commitment_active
            self._t_run_sbmpc_last = t
            # print(
            #     f"[SBMPC] Course output: {np.rad2deg(course_ref + self._course_os_best)} | "
            #     f"Best course offset: {np.rad2deg(self._course_os_best)} | "
            #     f"Nominal course ref: {np.rad2deg(course_ref)} | "
            #     f"Speed output: {speed_ref * self._speed_os_best} | "
            #     f"Best speed offset: {self._speed_os_best} | "
            #     f"Nominal speed ref: {speed_ref}"
            # )
        references[2, 0] = self._course_command
        references[3, 0] = speed_ref * self._speed_os_best
        if solver_executed:
            self._solve_id += 1
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        debug = self._sbmpc.get_debug_data()
        self._diagnostics = PlanDiagnostics(
            status=PlanStatus.SUCCESS,
            elapsed_ms=elapsed_ms,
            feasible=True,
            objective=debug["objective"],
            requested_algorithm="sbmpc",
            executed_algorithm="sbmpc",
            details={
                "solver_executed": solver_executed,
                "solve_id": self._solve_id,
                "track_count": len(do_list),
                "speed_scale": float(self._speed_os_best),
                "course_offset_rad": float(self._course_os_best),
                "overtaking_recovery_active": self._overtaking_recovery_active,
            },
        )
        algorithm_details = {
            key: value
            for key, value in debug.items()
            if key not in {"prediction", "prediction_dt_s", "target_predictions", "objective", "constraints"}
        }
        self._planner_trace = PlannerTrace(
            algorithm_id="sbmpc",
            solve_id=self._solve_id,
            sim_time=float(t),
            solver_executed=solver_executed,
            elapsed_ms=elapsed_ms,
            objective=debug["objective"],
            predicted_trajectory=debug["prediction"],
            horizon_dt_s=float(debug["prediction_dt_s"]),
            selected_command={
                "course_rad": float(references[2, 0]),
                "speed_mps": float(references[3, 0]),
                "course_offset_rad": float(self._course_os_best),
                "speed_scale": float(self._speed_os_best),
                "candidate_course_rad": float(
                    self._sbmpc.get_course_command(self._course_os_best)
                ),
                "overtaking_recovery_active": self._overtaking_recovery_active,
            },
            target_predictions=debug["target_predictions"],
            constraints=debug["constraints"],
            algorithm_details=algorithm_details,
        )
        return references

    def get_diagnostics(self) -> PlanDiagnostics:
        return self._diagnostics

    def get_current_plan(self) -> np.ndarray:
        return self._planner_trace.predicted_trajectory

    def get_colav_data(self) -> dict:
        trace = self._planner_trace.to_dict()
        return {
            "predicted_trajectory": trace["predicted_trajectory"],
            "planner": trace,
        }

    def plot_results(self, ax_map: plt.Axes, enc: senc.ENC, plt_handles: dict, **kwargs) -> dict:  # noqa: ARG002
        return plt_handles


class COLAVBuilder:
    @classmethod
    def construct_colav(cls, config: Config | None = None) -> ICOLAV | None:
        """Builds a colav system from the configuration and the default ones provided in this project.

        ..if specified.

        Args:
            config (Config | None): COLAV configuration. Defaults to None.

        Returns:
            ICOLAV | None: The COLAV system (if any config), e.g. Kuwata VO.
        """
        if config and config.name == COLAVType.VO:
            return VOWrapper(config)
        elif config and config.name == COLAVType.SBMPC:
            return SBMPCWrapper(config)
        else:
            return None
