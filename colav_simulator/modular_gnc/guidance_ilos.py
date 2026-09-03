"""Clean integral line-of-sight (ILOS) guidance module (Issue #57, GNC S5).

Scope contract (Issue #57 AC1/AC2): this module contains ONLY route projection,
along-route progress, lookahead course law, signed cross-track error, cross-track
integral state, course/speed reference output, an explicit speed ceiling, reset,
and per-call trace. Route geometry/smoothing, speed policy, terminal policy, and
environment compensation stay outside the module: environmental effects enter the
stack through the EnvironmentField and load-model seams, never through guidance.

Conventions: NE world frame, SI units, right-positive angles (TS-03..TS-05). The
signed cross-track error is positive when the vessel is to the right of the route
direction of travel. The course reference is a course-over-ground angle chi_d in
[-pi, pi], matching the legacy kinematic reference channel (values[2]).

Route lifecycle semantics: the module consumes accepted TrackedRoute contracts
whose validity interval is enforced upstream by the command latch. A change in
route identity (route_id or revision) is treated as a reference discontinuity and
rejected by zeroing the integral state before the new route is tracked; no
cross-route state is ever carried over.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from colav_simulator.modular_gnc.contracts import (
    ControlTask,
    DirectReference,
    FloatArray,
    NavigationState,
    TrackedRoute,
    _finite_scalar,
    _non_bool_int,
)
from colav_simulator.modular_gnc.controller import wrap_to_pi

_SNAPSHOT_SCHEMA_VERSION = "integral-line-of-sight.snapshot.v1"


@dataclass(frozen=True)
class ILOSConfig:
    """Immutable, validated ILOS guidance parameters.

    Parameters:
        lookahead_distance_m: Lookahead distance Delta > 0; proportional ILOS gain
            is K_p = 1 / Delta.
        integral_gain: Integral gain K_i >= 0 applied to the integrated signed
            cross-track error.
        max_integral_cross_track_error_m: Symmetric saturation bound (> 0) on the
            integrated cross-track error (explicit, traced clamp).
        integral_error_threshold_m: Leak-through threshold (>= 0): the integral
            only accumulates while |cross-track error| is within this bound.
        max_speed_mps: Explicit speed ceiling (> 0) applied to the route speed.
    """

    lookahead_distance_m: float = 50.0
    integral_gain: float = 0.0001
    max_integral_cross_track_error_m: float = 1000.0
    integral_error_threshold_m: float = 50.0
    max_speed_mps: float = 10.0

    def __post_init__(self) -> None:
        """Validate parameter presence, finiteness, and sign bounds."""
        lookahead = _finite_scalar("lookahead_distance_m", self.lookahead_distance_m)
        if lookahead <= 0.0:
            raise ValueError(f"lookahead_distance_m must be positive, got {lookahead}")
        integral_gain = _finite_scalar("integral_gain", self.integral_gain)
        if integral_gain < 0.0:
            raise ValueError(f"integral_gain must be non-negative, got {integral_gain}")
        max_integral = _finite_scalar("max_integral_cross_track_error_m", self.max_integral_cross_track_error_m)
        if max_integral <= 0.0:
            raise ValueError(f"max_integral_cross_track_error_m must be positive, got {max_integral}")
        threshold = _finite_scalar("integral_error_threshold_m", self.integral_error_threshold_m)
        if threshold < 0.0:
            raise ValueError(f"integral_error_threshold_m must be non-negative, got {threshold}")
        max_speed = _finite_scalar("max_speed_mps", self.max_speed_mps)
        if max_speed <= 0.0:
            raise ValueError(f"max_speed_mps must be positive, got {max_speed}")

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> ILOSConfig:
        """Construct ILOSConfig from a normalized registry parameter mapping."""
        kwargs: dict[str, Any] = {}
        for key in (
            "lookahead_distance_m",
            "integral_gain",
            "max_integral_cross_track_error_m",
            "integral_error_threshold_m",
            "max_speed_mps",
        ):
            if key in params:
                kwargs[key] = params[key]
        return cls(**kwargs)


@dataclass(frozen=True)
class ILOSGuidanceTrace:
    """Immutable per-call trace of the ILOS guidance law (Issue #57 AC1)."""

    tick: int
    dt_s: float
    integration_dt_s: float
    route_id: str
    revision: int
    segment_index: int
    progress_m: float
    cross_track_error_m: float
    integral_cross_track_error_m: float
    integral_updated: bool
    route_state_reset: bool
    course_reference_rad: float
    route_speed_mps: float
    speed_ceiling_mps: float
    speed_reference_mps: float
    speed_ceiling_applied: bool

    def __post_init__(self) -> None:
        """Validate tick, dt bounds, revision, booleans, and freeze scalars."""
        object.__setattr__(self, "tick", _non_bool_int("tick", self.tick))
        dt = _finite_scalar("dt_s", self.dt_s)
        if dt <= 0.0:
            raise ValueError(f"dt_s must be positive, got {dt}")
        object.__setattr__(self, "dt_s", dt)
        integration_dt = _finite_scalar("integration_dt_s", self.integration_dt_s)
        if integration_dt < 0.0:
            raise ValueError(f"integration_dt_s must be non-negative, got {integration_dt}")
        object.__setattr__(self, "integration_dt_s", integration_dt)
        object.__setattr__(self, "revision", _non_bool_int("revision", self.revision))
        object.__setattr__(self, "segment_index", _non_bool_int("segment_index", self.segment_index))
        for name in (
            "progress_m",
            "cross_track_error_m",
            "integral_cross_track_error_m",
            "course_reference_rad",
            "route_speed_mps",
            "speed_ceiling_mps",
            "speed_reference_mps",
        ):
            object.__setattr__(self, name, _finite_scalar(name, getattr(self, name)))
        for name in ("integral_updated", "route_state_reset", "speed_ceiling_applied"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be bool, got {type(value).__name__}")


@dataclass(frozen=True)
class ILOSGuidanceSnapshot:
    """Deterministic snapshot of guidance-local state for pause/resume and replay."""

    schema_version: str
    integral_cross_track_error_m: float
    active_segment: int
    last_route_id: str | None
    last_revision: int | None
    last_update_tick: int | None
    latest_trace: ILOSGuidanceTrace | None

    def __post_init__(self) -> None:
        """Validate snapshot schema version and frozen scalars."""
        if self.schema_version != _SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot schema_version: {self.schema_version}")
        object.__setattr__(
            self, "integral_cross_track_error_m", _finite_scalar("integral_cross_track_error_m",
                                                                 self.integral_cross_track_error_m)
        )
        object.__setattr__(self, "active_segment", _non_bool_int("active_segment", self.active_segment))
        if self.last_revision is not None:
            object.__setattr__(self, "last_revision", _non_bool_int("last_revision", self.last_revision))
        if self.last_update_tick is not None:
            object.__setattr__(self, "last_update_tick", _non_bool_int("last_update_tick", self.last_update_tick))


class IntegralLineOfSightGuidance:
    """Clean ILOS guidance over an explicit TrackedRoute contract.

    Deterministic and route-lifecycle aware: the only mutable state is the
    cross-track integral and the observed route identity / update tick, all of
    which participate in reset/snapshot/restore. Route validity, acceptance, and
    task capability are enforced upstream (command latch, facade); a route that
    reaches this module is accepted and inside its validity interval.
    """

    supported_tasks: frozenset[ControlTask] = frozenset({ControlTask.TRANSIT})

    def __init__(self, config: ILOSConfig | None = None) -> None:
        """Initialize with validated configuration and zero guidance state."""
        self._config = ILOSConfig() if config is None else config
        self._reset_state()

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> IntegralLineOfSightGuidance:
        """Construct guidance from a normalized registry parameter mapping."""
        return cls(ILOSConfig.from_params(params))

    @property
    def config(self) -> ILOSConfig:
        """Return the immutable guidance configuration."""
        return self._config

    @property
    def latest_trace(self) -> ILOSGuidanceTrace | None:
        """Return the latest per-call guidance trace."""
        return self._latest_trace

    def reset(self) -> None:
        """Idempotently clear integral state, route identity, and trace."""
        self._reset_state()

    def snapshot(self) -> ILOSGuidanceSnapshot:
        """Capture complete guidance state for deterministic restoration."""
        return ILOSGuidanceSnapshot(
            schema_version=_SNAPSHOT_SCHEMA_VERSION,
            integral_cross_track_error_m=self._integral,
            active_segment=self._active_segment,
            last_route_id=self._last_route_id,
            last_revision=self._last_revision,
            last_update_tick=self._last_update_tick,
            latest_trace=self._latest_trace,
        )

    def restore(self, snapshot: ILOSGuidanceSnapshot) -> None:
        """Restore exact guidance state from a snapshot."""
        if not isinstance(snapshot, ILOSGuidanceSnapshot):
            raise TypeError(f"snapshot must be ILOSGuidanceSnapshot, got {type(snapshot).__name__}")
        self._integral = snapshot.integral_cross_track_error_m
        self._active_segment = snapshot.active_segment
        self._last_route_id = snapshot.last_route_id
        self._last_revision = snapshot.last_revision
        self._last_update_tick = snapshot.last_update_tick
        self._latest_trace = snapshot.latest_trace

    def compute_reference(
        self,
        tick: int,
        route: TrackedRoute,
        navigation: NavigationState,
        dt_s: float,
    ) -> DirectReference:
        """Compute the ILOS course/speed reference for one guidance invocation."""
        if not isinstance(route, TrackedRoute):
            raise TypeError(f"route must be TrackedRoute, got {type(route).__name__}")
        if not isinstance(navigation, NavigationState):
            raise TypeError(f"navigation must be NavigationState, got {type(navigation).__name__}")
        dt = _finite_scalar("dt_s", dt_s)
        if dt <= 0.0:
            raise ValueError(f"dt_s must be positive, got {dt}")
        tick_int = _non_bool_int("tick", tick)

        segment_index, progress_m, cross_track_error, alpha = self._project(route, navigation)

        route_state_reset = self._reject_route_discontinuity(route)
        integration_dt = self._elapsed_seconds(tick_int, dt)
        integral_updated = abs(cross_track_error) <= self._config.integral_error_threshold_m and integration_dt > 0.0
        if integral_updated:
            self._integral += cross_track_error * integration_dt
            self._integral = math.copysign(
                min(abs(self._integral), self._config.max_integral_cross_track_error_m), self._integral
            )

        proportional = cross_track_error / self._config.lookahead_distance_m
        chi_r = math.atan2(-(proportional + self._config.integral_gain * self._integral), 1.0)
        course_reference = wrap_to_pi(alpha + chi_r)

        route_speed = float(route.speed_mps[segment_index])
        speed_reference = min(route_speed, self._config.max_speed_mps)
        speed_ceiling_applied = route_speed > self._config.max_speed_mps

        values = np.zeros(9, dtype=np.float64)
        values[2] = course_reference
        values[3] = speed_reference
        reference = DirectReference(values, latched_tick=tick_int, task=route.task)

        self._latest_trace = ILOSGuidanceTrace(
            tick=tick_int,
            dt_s=dt,
            integration_dt_s=integration_dt,
            route_id=route.route_id,
            revision=route.revision,
            segment_index=segment_index,
            progress_m=progress_m,
            cross_track_error_m=cross_track_error,
            integral_cross_track_error_m=self._integral,
            integral_updated=integral_updated,
            route_state_reset=route_state_reset,
            course_reference_rad=course_reference,
            route_speed_mps=route_speed,
            speed_ceiling_mps=self._config.max_speed_mps,
            speed_reference_mps=speed_reference,
            speed_ceiling_applied=speed_ceiling_applied,
        )
        self._last_update_tick = tick_int
        return reference

    def _reset_state(self) -> None:
        """Reset all mutable guidance state to deterministic defaults."""
        self._integral = 0.0
        self._active_segment = 0
        self._last_route_id: str | None = None
        self._last_revision: int | None = None
        self._last_update_tick: int | None = None
        self._latest_trace: ILOSGuidanceTrace | None = None

    def _reject_route_discontinuity(self, route: TrackedRoute) -> bool:
        """Zero integral state on route identity change; return whether a reset fired."""
        reset = (
            self._last_route_id is not None
            and (route.route_id != self._last_route_id or route.revision != self._last_revision)
        )
        if reset:
            self._integral = 0.0
            self._active_segment = 0
            self._last_update_tick = None
        self._last_route_id = route.route_id
        self._last_revision = route.revision
        return reset

    def _elapsed_seconds(self, tick: int, dt_s: float) -> float:
        """Return simulation seconds elapsed since the previous guidance call."""
        if self._last_update_tick is None:
            return 0.0
        elapsed_ticks = tick - self._last_update_tick
        if elapsed_ticks < 0:
            raise ValueError(f"guidance tick {tick} moved backwards from {self._last_update_tick}")
        return elapsed_ticks * dt_s

    def _project(
        self,
        route: TrackedRoute,
        navigation: NavigationState,
    ) -> tuple[int, float, float, float]:
        """Project the vessel onto the route polyline.

        Returns (segment_index, progress_m, signed cross-track error, segment
        course angle alpha). The projection is the nearest point over the
        candidate segments with clamped segment parameter (first segment wins
        exact ties). The active segment cursor starts at the first segment and
        advances monotonically: it moves past a segment whose end projection is
        reached (t >= 1) or to a strictly nearer later segment. This is the
        threshold-free analogue of waypoint-segment switching and prevents the
        corner stagnation where both segments project onto the shared waypoint.
        The cursor never moves backward within one route identity and resets on
        route switch/revision. Progress is the arc length from the first
        waypoint; the cross-track error is right-positive relative to the
        direction of travel.
        """
        waypoints = route.waypoints_ne_m
        n_segments = waypoints.shape[1] - 1
        x_n = navigation.north_m
        x_e = navigation.east_m
        cursor = min(self._active_segment, n_segments - 1)

        best_index = -1
        while True:
            best_index = -1
            best_dist_sq = math.inf
            best_t = 0.0
            for index in range(cursor, n_segments):
                start_n = float(waypoints[0, index])
                start_e = float(waypoints[1, index])
                delta_n = float(waypoints[0, index + 1]) - start_n
                delta_e = float(waypoints[1, index + 1]) - start_e
                length_sq = delta_n * delta_n + delta_e * delta_e
                if length_sq <= 0.0:
                    continue
                t = ((x_n - start_n) * delta_n + (x_e - start_e) * delta_e) / length_sq
                t = min(1.0, max(0.0, t))
                proj_n = start_n + t * delta_n
                proj_e = start_e + t * delta_e
                dist_sq = (x_n - proj_n) * (x_n - proj_n) + (x_e - proj_e) * (x_e - proj_e)
                if dist_sq < best_dist_sq:
                    best_index = index
                    best_dist_sq = dist_sq
                    best_t = t
            if best_index < 0:
                raise ValueError("route has no segment with positive length to project onto")
            if best_index == cursor and best_t >= 1.0 and cursor < n_segments - 1:
                cursor += 1
                continue
            break

        self._active_segment = max(cursor, best_index)

        alpha = math.atan2(float(waypoints[1, best_index + 1]) - float(waypoints[1, best_index]),
                           float(waypoints[0, best_index + 1]) - float(waypoints[0, best_index]))
        progress = self._progress_at(waypoints, best_index, best_t)
        start_n = float(waypoints[0, best_index])
        start_e = float(waypoints[1, best_index])
        delta_n = float(waypoints[0, best_index + 1]) - start_n
        delta_e = float(waypoints[1, best_index + 1]) - start_e
        proj_n = start_n + best_t * delta_n
        proj_e = start_e + best_t * delta_e
        cross_track_error = -(x_n - proj_n) * math.sin(alpha) + (x_e - proj_e) * math.cos(alpha)
        return best_index, progress, cross_track_error, alpha

    @staticmethod
    def _progress_at(waypoints: FloatArray, segment_index: int, t: float) -> float:
        """Return arc length from the first waypoint to the projection point."""
        progress = 0.0
        for index in range(segment_index):
            delta_n = float(waypoints[0, index + 1]) - float(waypoints[0, index])
            delta_e = float(waypoints[1, index + 1]) - float(waypoints[1, index])
            progress += math.hypot(delta_n, delta_e)
        delta_n = float(waypoints[0, segment_index + 1]) - float(waypoints[0, segment_index])
        delta_e = float(waypoints[1, segment_index + 1]) - float(waypoints[1, segment_index])
        return progress + t * math.hypot(delta_n, delta_e)
