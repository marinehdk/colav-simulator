"""Resolved actuator dynamics fidelity profile (Issue #59, S6.2, TS-22, G9).

One discrete-phase owner for per-actuator force rate limiting and transport
delay. Force limits, command saturation, effectiveness, and failures remain
owned by the data-driven allocator (Issue #58): this module never clips or
re-scales allocator commands, and it rejects commands outside the declared
per-actuator force limits instead of silently repairing them, so actuator
dynamics enforcement has exactly one owner per concern (Issue #59 AC4).

Rate and delay parameters are declared per actuator id with full coverage of
one immutable actuator layout asset and are content-hashed (TS-27), so the
ideal and resolved fidelity profiles carry separate identity, config hash,
and trace evidence (Issue #59 AC1). The resolved profile advances once per
due tick as a discrete phase; actuator discrete state is never advanced
inside RK stages (TS-14, VR-11). State is per-instance (per ship/episode)
with deterministic reset/snapshot/restore (TS-15).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from colav_simulator.modular_gnc.allocator import KNOWN_ACTUATOR_LAYOUT_ASSETS
from colav_simulator.modular_gnc.contracts import (
    ActuatorDynamicsTrace,
    ControlTask,
    _finite_scalar,
    _non_bool_int,
)

FloatArray = NDArray[np.float64]

ACTUATOR_IDENTITY = "resolved_actuator_dynamics"
_FIDELITY_PROFILE = "resolved"
_PARAM_KEYS = frozenset({"layout_asset_id", "rate_limit_n_per_s", "delay_ticks"})


def _actuator_dynamics_content_sha256(
    layout_asset_id: str,
    rate_limit_n_per_s: Mapping[str, float],
    delay_ticks: Mapping[str, int],
) -> str:
    """Return canonical content SHA-256 for resolved actuator dynamics parameters (TS-27)."""
    canonical = {
        "fidelity_profile": _FIDELITY_PROFILE,
        "actuator_identity": ACTUATOR_IDENTITY,
        "layout_asset_id": layout_asset_id,
        "rate_limit_n_per_s": dict(rate_limit_n_per_s),
        "delay_ticks": dict(delay_ticks),
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ResolvedActuatorDynamicsConfig:
    """Immutable resolved actuator dynamics configuration (TS-22, TS-27).

    Rate limits and transport delays are declared per actuator id with full
    coverage of exactly one known layout asset; partial coverage would hide an
    ideal pass-through assumption and is rejected (no silent fallback).
    """

    layout_asset_id: str
    rate_limit_n_per_s: Mapping[str, float]
    delay_ticks: Mapping[str, int]
    config_hash: str = ""

    def __deepcopy__(self, memo: dict[int, Any]) -> ResolvedActuatorDynamicsConfig:
        """Reuse the immutable configuration during episode cloning."""
        memo[id(self)] = self
        return self

    def __post_init__(self) -> None:
        """Validate full-coverage declarations and compute the content hash."""
        if not isinstance(self.layout_asset_id, str) or not self.layout_asset_id:
            raise ValueError("layout_asset_id must be a non-empty string")
        if self.layout_asset_id not in KNOWN_ACTUATOR_LAYOUT_ASSETS:
            raise ValueError(
                f"unknown actuator layout asset id: {self.layout_asset_id} "
                f"(known: {sorted(KNOWN_ACTUATOR_LAYOUT_ASSETS)})"
            )
        actuator_ids = KNOWN_ACTUATOR_LAYOUT_ASSETS[self.layout_asset_id].actuator_ids()

        rates = self._validated_mapping("rate_limit_n_per_s", actuator_ids)
        delays = self._validated_mapping("delay_ticks", actuator_ids)
        validated_rates: dict[str, float] = {}
        validated_delays: dict[str, int] = {}
        for actuator_id in actuator_ids:
            rate = rates[actuator_id]
            if isinstance(rate, bool) or not isinstance(rate, (int, float)):
                raise TypeError(f"rate_limit_n_per_s[{actuator_id}] must be a number, got {type(rate).__name__}")
            rate_value = float(rate)
            if not math.isfinite(rate_value) or rate_value <= 0.0:
                raise ValueError(f"rate_limit_n_per_s[{actuator_id}] must be a positive finite number, got {rate!r}")
            validated_rates[actuator_id] = rate_value

            delay = delays[actuator_id]
            if isinstance(delay, bool) or not isinstance(delay, int):
                raise TypeError(f"delay_ticks[{actuator_id}] must be an integer, got {type(delay).__name__}")
            if delay < 0:
                raise ValueError(f"delay_ticks[{actuator_id}] must be non-negative, got {delay}")
            validated_delays[actuator_id] = int(delay)

        object.__setattr__(self, "rate_limit_n_per_s", MappingProxyType(validated_rates))
        object.__setattr__(self, "delay_ticks", MappingProxyType(validated_delays))
        if not self.config_hash:
            object.__setattr__(
                self,
                "config_hash",
                _actuator_dynamics_content_sha256(self.layout_asset_id, validated_rates, validated_delays),
            )

    def _validated_mapping(self, name: str, actuator_ids: tuple[str, ...]) -> Mapping[str, Any]:
        """Return the raw parameter mapping validated for full actuator coverage."""
        raw = getattr(self, name)
        if not isinstance(raw, Mapping):
            raise TypeError(f"{name} must be a mapping keyed by actuator id, got {type(raw).__name__}")
        expected = set(actuator_ids)
        actual = set(raw)
        missing = sorted(expected - actual)
        if missing:
            raise ValueError(f"{name} must declare every layout actuator; missing: {missing}")
        unknown = sorted(actual - expected)
        if unknown:
            raise ValueError(f"{name} declares actuators outside layout {self.layout_asset_id}: {unknown}")
        return raw

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> ResolvedActuatorDynamicsConfig:
        """Construct a config from normalized module parameters (strict keys)."""
        if not isinstance(params, Mapping):
            raise TypeError(f"params must be a mapping, got {type(params).__name__}")
        unknown = sorted(set(params) - set(_PARAM_KEYS))
        if unknown:
            raise ValueError(f"unsupported resolved_actuator_dynamics parameters: {unknown}")
        missing = sorted(set(_PARAM_KEYS) - set(params))
        if missing:
            raise ValueError(f"missing required resolved_actuator_dynamics parameters: {missing}")
        return cls(
            layout_asset_id=params["layout_asset_id"],
            rate_limit_n_per_s=dict(params["rate_limit_n_per_s"]),
            delay_ticks=dict(params["delay_ticks"]),
        )


@dataclass(frozen=True)
class ResolvedActuatorDynamicsSnapshot:
    """Immutable actuator dynamics state: delivered force and in-transit delay lines."""

    current_force_n: Mapping[str, float]
    delay_queues_n: Mapping[str, tuple[float, ...]]

    def __post_init__(self) -> None:
        """Freeze snapshot mappings."""
        object.__setattr__(self, "current_force_n", MappingProxyType(dict(self.current_force_n)))
        object.__setattr__(
            self,
            "delay_queues_n",
            MappingProxyType({key: tuple(value) for key, value in self.delay_queues_n.items()}),
        )


class ResolvedActuatorDynamics:
    """Deterministic per-actuator rate limiter and transport delay (single dynamics owner).

    Each tick the allocator's clipped commands are approached at the declared
    per-actuator force rate limit, then held in a per-actuator delay line for
    exactly delay_ticks. Rate-limited actuators and pending delay depth are
    reported explicitly in the trace (no hidden clipping, AC4/AC3). Achieved
    generalized load projects the actual delivered forces through the nominal
    asset geometry scaled by the allocator's current health, strictly 3DOF
    [X, Y, N]; no roll channel exists (RA-12, VR-16).
    """

    def __init__(self, config: ResolvedActuatorDynamicsConfig) -> None:
        """Bind the config to its known layout asset and initialize zero state."""
        if not isinstance(config, ResolvedActuatorDynamicsConfig):
            raise TypeError(f"config must be ResolvedActuatorDynamicsConfig, got {type(config).__name__}")
        self._config = config
        self._asset = KNOWN_ACTUATOR_LAYOUT_ASSETS[config.layout_asset_id]
        self._ids = self._asset.actuator_ids()
        self._matrix = self._asset.effectiveness_matrix()
        self._limits = {
            spec.actuator_id: (spec.min_force_n, spec.max_force_n) for spec in self._asset.actuators
        }
        self._current_force: dict[str, float] = dict.fromkeys(self._ids, 0.0)
        self._delay_queues: dict[str, deque[float]] = {actuator_id: deque() for actuator_id in self._ids}
        self._latest_trace: ActuatorDynamicsTrace | None = None

    @property
    def identity(self) -> str:
        """Return the resolved actuator dynamics module identity."""
        return ACTUATOR_IDENTITY

    @property
    def fidelity_profile(self) -> str:
        """Return the fidelity profile owned by this module."""
        return _FIDELITY_PROFILE

    @property
    def config_hash(self) -> str:
        """Return the content hash of the bound dynamics configuration."""
        return self._config.config_hash

    @property
    def asset_id(self) -> str:
        """Return the bound layout asset id."""
        return self._config.layout_asset_id

    @property
    def supported_tasks(self) -> frozenset[ControlTask]:
        """Return actuator task capability: dynamics apply to every load task."""
        return frozenset(ControlTask)

    @classmethod
    def from_params(cls, params: Mapping[str, Any]) -> ResolvedActuatorDynamics:
        """Construct a ResolvedActuatorDynamics from normalized module parameters."""
        return cls(ResolvedActuatorDynamicsConfig.from_params(params))

    def reset(self) -> None:
        """Restore zero delivered force and empty delay lines (deterministic, idempotent)."""
        self._current_force = dict.fromkeys(self._ids, 0.0)
        self._delay_queues = {actuator_id: deque() for actuator_id in self._ids}
        self._latest_trace = None

    def snapshot(self) -> ResolvedActuatorDynamicsSnapshot:
        """Capture actuator-owned discrete state."""
        return ResolvedActuatorDynamicsSnapshot(
            current_force_n=dict(self._current_force),
            delay_queues_n={actuator_id: tuple(queue) for actuator_id, queue in self._delay_queues.items()},
        )

    def restore(self, snapshot: ResolvedActuatorDynamicsSnapshot) -> None:
        """Restore actuator-owned discrete state for the same bound layout."""
        if not isinstance(snapshot, ResolvedActuatorDynamicsSnapshot):
            raise TypeError(f"snapshot must be ResolvedActuatorDynamicsSnapshot, got {type(snapshot).__name__}")
        if set(snapshot.current_force_n) != set(self._ids) or set(snapshot.delay_queues_n) != set(self._ids):
            raise ValueError(f"actuator dynamics snapshot actuator ids mismatch for layout {self.asset_id}")
        restored_queues: dict[str, deque[float]] = {}
        for actuator_id in self._ids:
            queue = tuple(float(v) for v in snapshot.delay_queues_n[actuator_id])
            if len(queue) > self._config.delay_ticks[actuator_id]:
                raise ValueError(
                    f"delay queue for '{actuator_id}' exceeds configured delay_ticks "
                    f"({len(queue)} > {self._config.delay_ticks[actuator_id]})"
                )
            restored_queues[actuator_id] = deque(queue)
        self._current_force = {
            actuator_id: float(snapshot.current_force_n[actuator_id]) for actuator_id in self._ids
        }
        self._delay_queues = restored_queues
        self._latest_trace = None

    def _validate_commands(self, commands_n: Mapping[str, float]) -> dict[str, float]:
        """Validate command coverage, finiteness, and allocator-owned force limits (AC4)."""
        if not isinstance(commands_n, Mapping):
            raise TypeError(f"commands_n must be a mapping, got {type(commands_n).__name__}")
        if set(commands_n) != set(self._ids):
            unknown = sorted(set(commands_n) - set(self._ids))
            missing = sorted(set(self._ids) - set(commands_n))
            raise ValueError(
                f"actuator commands must cover exactly the layout actuators "
                f"(missing: {missing}, unknown: {unknown})"
            )
        validated: dict[str, float] = {}
        for actuator_id in self._ids:
            command = commands_n[actuator_id]
            if isinstance(command, bool) or not isinstance(command, (int, float)):
                raise TypeError(f"command for '{actuator_id}' must be a number, got {type(command).__name__}")
            value = float(command)
            if not math.isfinite(value):
                raise ValueError(f"command for '{actuator_id}' must be finite, got {value}")
            low, high = self._limits[actuator_id]
            if not low <= value <= high:
                raise ValueError(
                    f"command for '{actuator_id}' ({value} N) violates allocator-owned force limits "
                    f"[{low}, {high}] N; force limits are owned by the allocator (Issue #59 AC4)"
                )
            validated[actuator_id] = value
        return validated

    @staticmethod
    def _validate_health(actuator_health: Mapping[str, float], actuator_ids: tuple[str, ...]) -> None:
        """Validate that the allocator-provided health covers the layout within [0, 1]."""
        if not isinstance(actuator_health, Mapping) or set(actuator_health) != set(actuator_ids):
            raise ValueError("actuator_health must cover exactly the layout actuators")
        for actuator_id in actuator_ids:
            health = actuator_health[actuator_id]
            if (
                isinstance(health, bool)
                or not isinstance(health, (int, float))
                or not math.isfinite(float(health))
                or not 0.0 <= float(health) <= 1.0
            ):
                raise ValueError(f"actuator_health[{actuator_id}] must be within [0, 1], got {health!r}")

    def apply(
        self,
        commands_n: Mapping[str, float],
        actuator_health: Mapping[str, float],
        tick: int,
        time_s: float,
        dt_s: float,
    ) -> ActuatorDynamicsTrace:
        """Advance one due tick of rate limiting and delay; return explicit evidence.

        Effectiveness and failure scaling remain owned by the allocator's health
        state (Issue #58); the allocator's current health is applied here only
        when projecting delivered forces into the achieved generalized load, so
        the effectiveness model keeps a single owner and semantics (AC2, AC4).
        """
        self._validate_health(actuator_health, self._ids)
        validated = self._validate_commands(commands_n)
        tick_int = _non_bool_int("tick", tick)
        time_float = _finite_scalar("time_s", time_s)
        dt = _finite_scalar("dt_s", dt_s)
        if dt <= 0.0:
            raise ValueError(f"dt_s must be positive, got {dt}")

        outputs: dict[str, float] = {}
        pending: dict[str, int] = {}
        rate_limited: list[str] = []
        for actuator_id in self._ids:
            command = validated[actuator_id]
            current = self._current_force[actuator_id]
            gap = command - current
            step = self._config.rate_limit_n_per_s[actuator_id] * dt
            if abs(gap) <= step:
                target = command
            else:
                target = current + math.copysign(step, gap)
                rate_limited.append(actuator_id)
            queue = self._delay_queues[actuator_id]
            queue.append(target)
            if len(queue) > self._config.delay_ticks[actuator_id]:
                delivered = queue.popleft()
            else:
                delivered = 0.0
            self._current_force[actuator_id] = target
            outputs[actuator_id] = delivered
            pending[actuator_id] = len(queue)

        delivered_vector = np.fromiter(
            (outputs[actuator_id] for actuator_id in self._ids), dtype=np.float64, count=len(self._ids)
        )
        health_vector = np.fromiter(
            (float(actuator_health[actuator_id]) for actuator_id in self._ids), dtype=np.float64, count=len(self._ids)
        )
        achieved = (self._matrix * health_vector) @ delivered_vector
        trace = ActuatorDynamicsTrace(
            fidelity_profile=_FIDELITY_PROFILE,
            actuator_identity=ACTUATOR_IDENTITY,
            config_hash=self._config.config_hash,
            tick=tick_int,
            time_s=time_float,
            dt_s=dt,
            actuator_commands_n=dict(validated),
            actuator_outputs_n=outputs,
            rate_limited_actuators=tuple(sorted(rate_limited)),
            pending_delay_ticks=pending,
            achieved_load=(float(achieved[0]), float(achieved[1]), float(achieved[2])),
        )
        self._latest_trace = trace
        return trace

    def latest_trace(self) -> ActuatorDynamicsTrace | None:
        """Return the latest per-tick trace."""
        return self._latest_trace
