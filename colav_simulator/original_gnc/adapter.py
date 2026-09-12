"""Independent IShip adapter whose only motion integrator is the original GNC."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from colav_simulator.common import miscellaneous_helper_methods as mhm
from colav_simulator.core.colav.diagnostics import validate_plan
from colav_simulator.core.ship import Config, IShip, Ship
from colav_simulator.original_gnc import qualification as response_qualification_rule
from colav_simulator.original_gnc.configuration import SOURCE_MANIFEST_SHA256, OriginalGncConfig
from colav_simulator.original_gnc.geometry import RouteFrame, nominal_route
from colav_simulator.original_gnc.native import OriginalGncError
from colav_simulator.original_gnc.plan_bridge import OriginalPlanBridge
from colav_simulator.original_gnc.stack import NativeStack
from colav_simulator.original_gnc.telemetry import balance

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCE_FINGERPRINTS = {
    str(path.relative_to(_PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in [
        *Path(__file__).parent.glob("*.py"),
        *[
            _PROJECT_ROOT / name
            for name in (
                "colav_simulator/core/ship.py",
                "colav_simulator/core/colav/custom_mpc_adapter.py",
                "colav_simulator/experiment/runner.py",
                "colav_simulator/experiment/contracts.py",
                "colav_simulator/experiment/persistence.py",
            )
        ],
    ]
}
_RUNTIME_SHA256 = hashlib.sha256(json.dumps(RUNTIME_SOURCE_FINGERPRINTS, sort_keys=True).encode()).hexdigest()


class OriginalGncShipAdapter(IShip):
    """Reuse framework planner/tracker/telemetry services, retaining original GNC authority."""

    def __init__(self, services: Ship, configuration: OriginalGncConfig, dt_s: float):
        if not math.isfinite(dt_s) or dt_s <= 0:
            raise ValueError("Original GNC requires a positive simulation step")
        if services.state.shape != (6,) or not np.isfinite(services.state).all():
            raise ValueError("Original GNC requires a finite initialized vessel state")
        self._legacy = services
        self.configuration = configuration
        self._dt_s = dt_s
        self._parameters = configuration.parameters()
        self._response_approximation = configuration.response_approximation()
        self._package_roots, self._asset_paths, self._policy_config = configuration.source_assets()
        self._stack = None
        self._plan_bridge = None
        self._seed = 0
        self._nominal_revision = 1
        self._nominal_id = f"original-gnc-mission-{services.id}"
        self._events = []
        self._requested_plans = []
        self._planner_time_origin = None
        self._initial_csog = np.array(
            [services.state[0], services.state[1], math.hypot(services.state[3], services.state[4]), services.state[2]]
        )
        waypoints = services.waypoints
        anchor = waypoints[:, 0] if waypoints.ndim == 2 and waypoints.shape[1] else self._initial_csog[:2]
        self.frame = RouteFrame(float(anchor[0]), float(anchor[1]))
        self._legacy._input = np.zeros(3)
        self._legacy._references = np.zeros((9, 1))
        self._start_stack()

    @classmethod
    def from_config(cls, config: Config, dt_s: float) -> OriginalGncShipAdapter:
        """Build an opt-in original backend without selecting any modular stack."""
        services_config = copy.copy(config)
        services_config.original_gnc = None
        services_config.ship_modules = None
        services = Ship(mmsi=config.mmsi, identifier=config.id, config=services_config)
        return cls(services, config.original_gnc, dt_s)

    def _start_stack(self) -> None:
        if self._stack is not None:
            self._stack.close()
        parameters = copy.deepcopy(self._parameters)
        north, east = self.frame.source_position(float(self._initial_csog[0]), float(self._initial_csog[1]))
        values = {
            "initial_position.x": north,
            "initial_position.y": east,
            "initial_position.yaw": float(self._initial_csog[3]),
            "initial_velocity.u": float(self._initial_csog[2]),
            "initial_velocity.v": 0.0,
            "initial_velocity.r": 0.0,
        }
        for key, value in values.items():
            parameters["ship_dynamics_node"][key]["value"] = value
        self._kernel_parameters = copy.deepcopy(parameters)
        self._events = []
        self._requested_plans = []
        self._planner_time_origin = None
        self._stack = NativeStack(
            self.configuration.build_directory,
            parameters,
            self._package_roots,
            self._policy_config,
            enabled_environment=("wind", "current", "wave") if self.configuration.environment else (),
            asset_paths=self._asset_paths,
            trace=self._capture,
        )
        self._build_identity = self.stack.modules["ship_dynamics_node"].manifest
        self._executed_module_names = [*self.stack.modules, "propulsion_policy_node", *self.stack.observers]
        self._parameter_hash = hashlib.sha256(
            json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._sync_state()
        if self.waypoints.ndim == 2 and self.waypoints.shape[1] >= 2:
            self._publish_nominal()

    def _capture(self, event: dict) -> None:
        if event["event"] == "publish" and event["topic"] in {
            "/gnc/active_route",
            "/gnc/internal_waypoints",
            "/gnc/route_execution_status",
            "/route_planning/route_plan_status",
        }:
            self._events.append({"sequence": len(self._events), **copy.deepcopy(event)})

    def _sync_state(self) -> None:
        state = self._stack.states["ship_dynamics_node"]
        eta, nu = state["eta"], state["nu"]
        self._legacy._state = np.array(
            [eta[0] + self.frame.north_m, eta[1] + self.frame.east_m, eta[3], nu[0], nu[1], nu[3]]
        )
        command = self._stack.latest.get("/cmd_tau")
        if command:
            self._legacy._input = np.array(
                [command["wrench"]["force"]["x"], command["wrench"]["force"]["y"], command["wrench"]["torque"]["z"]]
            )

    def _publish_nominal(self) -> None:
        route = nominal_route(
            self.frame, self.waypoints, self.speed_plan, self._nominal_id, self._nominal_revision, self._stack.time_ns
        )
        self._requested_plans.append({"kind": "nominal", "time_ns": self._stack.time_ns, "message": copy.deepcopy(route)})
        self._stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", route)
        self._sync_state()

    def __deepcopy__(self, memo: dict) -> OriginalGncShipAdapter:
        """Rebuild initial episode templates without copying opaque native handles."""
        if self.stack.elapsed_s != 0 or self._plan_bridge is not None:
            raise OriginalGncError("An active original GNC requires recorded-event replay; opaque state cannot be copied")
        clone = type(self).__new__(type(self))
        memo[id(self)] = clone
        for key, value in self.__dict__.items():
            if key not in {"_stack", "_plan_bridge", "_events", "_requested_plans"}:
                setattr(clone, key, copy.deepcopy(value, memo))
        clone._plan_bridge = None
        clone._events = []
        clone._requested_plans = []
        clone._stack = NativeStack(
            clone.configuration.build_directory,
            clone._kernel_parameters,
            clone._package_roots,
            clone._policy_config,
            enabled_environment=("wind", "current", "wave") if clone.configuration.environment else (),
            asset_paths=clone._asset_paths,
            trace=clone._capture,
        )
        for request in self._requested_plans:
            if request["time_ns"] != self.stack.epoch_ns or request["kind"] != "nominal":
                clone.close()
                raise OriginalGncError("Only initial nominal-route templates can be cloned")
            clone.stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", request["message"])
        clone._requested_plans = copy.deepcopy(self._requested_plans, memo)
        clone._sync_state()
        return clone

    # The framework interface fixes these parameter names; execution ownership stays explicit.
    def forward(self, dt: float, w: Any = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # noqa: ARG002
        """Advance only the source GNC; original environmental models own its loads."""
        self._stack.advance(dt)
        self._sync_state()
        if self._legacy._colav is None:
            self._legacy._references = self.applied_reference.reshape(9, 1)
        return self.state, self._legacy._input, self._legacy._references[:, 0]

    def track_obstacles(self, t: float, dt: float, true_do_states: list) -> tuple[list, list]:
        """Use the original executed velocity when feeding framework sensors/tracker."""
        return self._legacy._tracker.track(t, dt, true_do_states, mhm.convert_state_to_vxvy_state(self.csog_state))

    def plan(self, t: float, dt: float, do_list: list, enc: Any = None, w: Any = None) -> np.ndarray:
        """Run the chosen planner against source truth and submit its accepted authority."""
        if self._legacy._colav is None:
            self._legacy._references = self.applied_reference.reshape(9, 1)
            return self._legacy._references
        if self._planner_time_origin is None:
            self._planner_time_origin = t - self._stack.elapsed_s
        if self._plan_bridge is None:
            self._plan_bridge = OriginalPlanBridge(self, self._dt_s)
        self._legacy._references = validate_plan(
            self._legacy._colav.plan(
                t,
                self.waypoints,
                self.speed_plan,
                self.state,
                do_list,
                enc,
                self.goal_state,
                w,
                os_length=self.length,
                os_width=self.width,
                os_draft=self.draft,
                os_model_name="original_gnc_20260824_v2",
                os_controller_name="original_ship_control_20260824_v2",
                os_course_time_constant_s=self._response_approximation["course"]["time_constant_s"],
                os_speed_time_constant_s=self._response_approximation["speed"]["time_constant_s"],
                os_max_turn_rate_radps=self.max_turn_rate,
                os_avoidance_speed_cap_mps=self.avoidance_speed_cap,
                os_min_steerage_speed_mps=self.min_steerage_speed,
                os_max_speed_mps=self.max_speed,
                dt=dt,
            )
        )
        self._plan_bridge.submit(t)
        return self._legacy._references

    def reset(self, seed: int | None) -> None:
        """Recreate all original states; reset only framework sensing and planning services."""
        self._seed = 0 if seed is None else seed
        self._legacy._tracker.reset()
        for sensor in self._legacy._sensors:
            sensor.reset(seed)
        if self._legacy._colav is not None:
            self._legacy._colav.reset()
        self._plan_bridge = None
        self._start_stack()

    def set_initial_state(self, csog_state: np.ndarray, t_start: float | None = None) -> None:
        """Apply an explicit new initial condition by starting fresh original kernels."""
        state = np.asarray(csog_state, dtype=float)
        if state.shape != (4,) or not np.isfinite(state).all():
            raise ValueError("Initial COG/SOG state must have four finite values")
        self._initial_csog = state.copy()
        self._legacy.set_initial_state(state, t_start)
        self._plan_bridge = None
        self._start_stack()

    def set_nominal_plan(self, waypoints: np.ndarray, speed_plan: np.ndarray) -> None:
        """Submit mission updates through the original route manager without resetting motion."""
        self._legacy.set_nominal_plan(waypoints, speed_plan)
        self._nominal_revision += 1
        if self._stack.elapsed_s == 0 and not self._requested_plans:
            self.frame = RouteFrame(float(waypoints[0, 0]), float(waypoints[1, 0]))
            self._start_stack()
            return
        self._publish_nominal()

    def set_id(self, identifier: int) -> None:
        self._legacy.set_id(identifier)

    def set_goal_state(self, state: np.ndarray) -> None:
        self._legacy.set_goal_state(state)

    def set_remote_actor_predicted_trajectory(self, trajectory: np.ndarray) -> None:
        self._legacy.set_remote_actor_predicted_trajectory(trajectory)

    # The framework interface fixes these parameter names; execution ownership stays explicit.
    def set_references(self, references: np.ndarray) -> None:  # noqa: ARG002
        raise OriginalGncError(
            "Original GNC accepts route/avoidance contracts; direct control references cannot bypass its guidance"
        )

    def set_tracker(self, tracker: Any) -> None:
        self._legacy.set_tracker(tracker)

    def set_colav_system(self, colav: Any) -> None:
        self._legacy.set_colav_system(colav)
        self._plan_bridge = None

    # The framework interface fixes these parameter names; execution ownership stays explicit.
    def set_controller(self, controller: Any) -> None:  # noqa: ARG002
        raise OriginalGncError("The frozen original GNC owns its controller")

    def get_colav_data(self) -> dict:
        return self._legacy.get_colav_data()

    def get_colav_decision_space(self) -> dict | None:
        return self._legacy.get_colav_decision_space()

    def set_colav_data(self, data: dict) -> None:
        self._legacy.set_colav_data(data)

    def get_do_track_information(self) -> tuple[list, list]:
        return self._legacy.get_do_track_information()

    def plot_colav_results(self, ax_map: Any, enc: Any, plt_handles: dict, remote_actor: bool = False, **kwargs) -> dict:
        return self._legacy.plot_colav_results(ax_map, enc, plt_handles, remote_actor, **kwargs)

    def transfer_vessel_ais_data(
        # The framework interface fixes these parameter names; execution ownership stays explicit.
        self,
        vessel: Any,  # noqa: ARG002
        use_ais_trajectory: bool = True,  # noqa: ARG002
        t_start: float | None = None,  # noqa: ARG002
        t_end: float | None = None,  # noqa: ARG002
    ) -> None:
        raise OriginalGncError("Historical AIS playback cannot replace the original GNC motion state")

    def get_sim_data(self, t: float, timestamp_0: int) -> dict:
        """Expose actual source state, application feedback and independent identity."""
        data = self._legacy.get_sim_data(t, timestamp_0)
        if data["active"]:
            data["csog_state"] = self.csog_state
        data["turn_rate"] = self.turn_rate
        data["original_gnc"] = {
            "stack_id": self.configuration.stack_id,
            "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "parameter_sha256": self._parameter_hash,
            "time_ns": self._stack.time_ns,
            "state_8d": self.original_state.tolist(),
            "applied_reference": self.applied_reference.tolist(),
            "route_event_count": len(self._events),
            "requested_plan_count": len(self._requested_plans),
            "execution_status": copy.deepcopy(self._stack.latest.get("/gnc/route_execution_status")),
            "route_plan_status": copy.deepcopy(self._stack.latest.get("/route_planning/route_plan_status")),
        }
        data["original_gnc"]["bridge_outcome"] = copy.deepcopy(self._plan_bridge.last_outcome) if self._plan_bridge else None
        data["original_gnc"]["bridge_admission"] = (
            copy.deepcopy(self._plan_bridge.admission_metrics) if self._plan_bridge else None
        )
        return data

    def original_gnc_evidence(self) -> dict:
        """Return executing build identity without importing another stack's qualification."""
        build = self._build_identity
        return {
            "backend_kind": "original_gnc",
            "stack_id": self.configuration.stack_id,
            "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "library_sha256": build["library_sha256"],
            "python_runtime_sha256": _RUNTIME_SHA256,
            "parameter_sha256": self._parameter_hash,
            "acceptance_level": "EXPERIMENTAL_ORIGINAL_SOURCE",
            "response_qualification": response_qualification_rule.verdict_string(self._response_approximation),
            "response_approximation_sha256": self._response_approximation["artifact_sha256"],
            "environment_enabled": self.configuration.environment,
            "scenario_acceptance": "separately_evaluated",
        }

    def original_balance_telemetry(self) -> dict:
        """Read original actuation and environment values for the instrument panel."""
        return balance(self)

    def original_gnc_bundle(self) -> dict:
        """Preserve raw requests and every admission result with the executing build."""
        return {
            "schema": "original-gnc.run-bundle.v1",
            "identity": self.original_gnc_evidence(),
            "build": self._build_identity,
            "python_runtime_sources_sha256": dict(RUNTIME_SOURCE_FINGERPRINTS),
            "parameters": copy.deepcopy(self._kernel_parameters),
            "response_approximation": copy.deepcopy(self._response_approximation),
            "executed_modules": self._executed_module_names,
            "frame": {
                "north_m": self.frame.north_m,
                "east_m": self.frame.east_m,
                "latitude_deg": self.frame.latitude_deg,
                "longitude_deg": self.frame.longitude_deg,
            },
            "requested_plans": self.requested_plans,
            "last_planner": copy.deepcopy(self._legacy.get_colav_data()),
            "execution_events": self.execution_events,
            "final_state_8d": self.original_state.tolist(),
            "final_source_states": copy.deepcopy(self.stack.states),
            "last_outputs": copy.deepcopy(self.stack.latest),
        }

    def get_ship_info(self) -> dict:
        return {
            "id": self.id,
            "mmsi": self.mmsi,
            "length": self.length,
            "width": self.width,
            "draft": self.draft,
            "max_speed": self.max_speed,
            "min_speed": self.min_speed,
            "max_turn_rate": self.max_turn_rate,
        }

    @property
    def state(self) -> np.ndarray:
        return self._legacy.state

    @property
    def original_state(self) -> np.ndarray:
        state = self._stack.states["ship_dynamics_node"]
        return np.array([*state["eta"], *state["nu"]], dtype=float)

    @property
    def csog_state(self) -> np.ndarray:
        state = self.state
        speed = math.hypot(state[3], state[4])
        course = state[2] + math.atan2(state[4], state[3]) if speed > 1e-9 else state[2]
        return np.array([state[0], state[1], speed, math.remainder(course, 2 * math.pi)])

    @property
    def applied_reference(self) -> np.ndarray:
        heading = self._stack.latest.get("/control/heading_setpoint", {}).get("data", self.state[2])
        speed = self._stack.latest.get("/control/speed_setpoint", {}).get("data", 0.0)
        return np.array([self.state[0], self.state[1], heading, speed, 0.0, 0.0, 0.0, 0.0, 0.0])

    @property
    def length(self) -> float:
        return self._parameters["ship_dynamics_node"]["vessel.Lpp"]["value"]

    @property
    def width(self) -> float:
        return self._parameters["ship_dynamics_node"]["vessel.B"]["value"]

    @property
    def draft(self) -> float:
        return self._parameters["ship_dynamics_node"]["vessel.d"]["value"]

    @property
    def max_speed(self) -> float:
        return self._parameters["ship_guidance_node"]["max_transit_speed"]["value"]

    @property
    def min_speed(self) -> float:
        return 0.0

    @property
    def max_turn_rate(self) -> float:
        return math.radians(self._parameters["active_route_manager_node"]["max_yaw_rate_deg_s"]["value"])

    @property
    def avoidance_speed_cap(self) -> float:
        """Frozen guidance surge cap on avoidance-tagged legs (ship_guidance_node.cpp ~5970)."""
        return float(self._parameters["ship_guidance_node"]["emergency_avoidance_speed_cap_mps"]["value"])

    @property
    def min_steerage_speed(self) -> float:
        return float(self._parameters["ship_guidance_node"]["minimum_steerage_speed"]["value"])

    @property
    def speed(self) -> float:
        return float(self.csog_state[2])

    @property
    def course(self) -> float:
        return float(self.csog_state[3])

    @property
    def heading(self) -> float:
        return float(self.state[2])

    @property
    def turn_rate(self) -> float:
        return float(self.state[5])

    @property
    def stack(self) -> NativeStack:
        return self._stack

    @property
    def execution_events(self) -> list[dict]:
        return copy.deepcopy(self._events)

    @property
    def requested_plans(self) -> list[dict]:
        return copy.deepcopy(self._requested_plans)

    def close(self) -> None:
        if self._stack is not None:
            self._stack.close()

    def __getattr__(self, name: str) -> Any:
        """Delegate framework services while explicit methods own execution."""
        return getattr(object.__getattribute__(self, "_legacy"), name)
