"""Immutable data contracts for the Mid-MPC IPOPT core."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class MidMpcStatus(StrEnum):
    CONVERGED = "Converged"
    FEASIBLE_NONOPTIMAL = "FeasibleNonOptimal"
    TIMEOUT = "Timeout"
    INFEASIBLE = "Infeasible"
    NUMERICAL_FAILURE = "NumericalFailure"


@dataclass(frozen=True)
class MidMpcConfig:
    horizon_steps: int = 18
    dt_s: float = 5.0
    w_colreg: float = 30.0
    w_dist: float = 10.0
    w_vel: float = 1.0
    w_route: float = 3.0
    w_slack_l1: float = 100_000.0
    w_slack_l2: float = 100.0
    w_dir_slack_l1: float = 100_000.0
    w_dir_slack_l2: float = 100.0
    zeta: float = 0.005
    pwt_outer_m: float = 11_112.0
    t_discount_s: float = 100.0
    cpa_slack_enabled: bool = True
    dir_slack_enabled: bool = True
    strict_slack_bounds: bool = False
    max_wall_time_s: float = 15.0
    continuous_cpa_enabled: bool = False
    max_targets: int = 16
    k_asym: float = 50.0
    asym_tau: float = 0.0873
    terminal_tau: float = 0.5
    terminal_l_min_m: float = 30.0
    terminal_l_max_m: float = 400.0

    def __post_init__(self) -> None:
        """Validate frozen NLP dimensions and finite tuning values."""
        if not 2 <= self.horizon_steps <= 120:
            raise ValueError("horizon_steps must be in [2, 120]")
        if self.max_targets != 16:
            raise ValueError("max_targets must remain 16 for frozen parameter parity")
        numeric = tuple(
            float(getattr(self, name))
            for name in (
                "dt_s",
                "w_colreg",
                "w_dist",
                "w_vel",
                "w_route",
                "w_slack_l1",
                "w_slack_l2",
                "w_dir_slack_l1",
                "w_dir_slack_l2",
                "zeta",
                "pwt_outer_m",
                "t_discount_s",
                "k_asym",
                "asym_tau",
                "terminal_tau",
                "terminal_l_min_m",
                "terminal_l_max_m",
                "max_wall_time_s",
            )
        )
        if not np.isfinite(numeric).all() or self.dt_s <= 0.0 or self.max_wall_time_s <= 0.0:
            raise ValueError("Mid-MPC config values and time limits must be finite and positive")
        if self.continuous_cpa_enabled:
            raise ValueError("continuous CPA midpoint rows are disabled in the frozen core")
        if self.strict_slack_bounds and not (self.cpa_slack_enabled and self.dir_slack_enabled):
            raise ValueError("strict slack bounds require the frozen two-slack graph")


@dataclass(frozen=True)
class MidMpcOwnShip:
    psi_rad: float
    u_mps: float
    x_m: float = 0.0
    y_m: float = 0.0

    def __post_init__(self) -> None:
        """Validate the own-ship state."""
        _require_finite(self.psi_rad, self.u_mps, self.x_m, self.y_m)


@dataclass(frozen=True)
class MidMpcRouteFrame:
    origin_m: tuple[float, float]
    normal: tuple[float, float]
    bearing_rad: float
    lateral_scale_m: float
    weight: float

    def __post_init__(self) -> None:
        """Normalize and validate the route frame."""
        origin = _pair(self.origin_m, "origin_m")
        normal = _pair(self.normal, "normal")
        _require_finite(*origin, *normal, self.bearing_rad, self.lateral_scale_m, self.weight)
        if self.lateral_scale_m <= 0.0:
            raise ValueError("lateral_scale_m must be positive")
        object.__setattr__(self, "origin_m", origin)
        object.__setattr__(self, "normal", normal)


@dataclass(frozen=True)
class MidMpcTarget:
    x_m: float
    y_m: float
    cog_rad: float
    sog_mps: float

    def __post_init__(self) -> None:
        """Validate one constant-velocity target state."""
        _require_finite(
            self.x_m,
            self.y_m,
            self.cog_rad,
            self.sog_mps,
        )


@dataclass(frozen=True)
class MidMpcRowSchedule:
    """Adapter-decided activation schedule for fixed NLP row classes."""

    prefix_softening: bool = False
    cpa_hard_from_k: int = 0
    direction_hard_from_k: int = 0
    min_alt_hard_from_k: int = 0
    terminal_rows_enabled: bool = False

    def __post_init__(self) -> None:
        """Validate non-negative activation indices."""
        indices = (
            self.cpa_hard_from_k,
            self.direction_hard_from_k,
            self.min_alt_hard_from_k,
        )
        if min(indices) < 0:
            raise ValueError("row schedule indices must be non-negative")


@dataclass(frozen=True)
class MidMpcProblem:
    own_ship: MidMpcOwnShip
    route_bearing_rad: float
    planned_speed_mps: float
    heading_bounds_rad: tuple[float, float]
    speed_bounds_mps: tuple[float, float]
    cpa_safe_m: float
    cpa_hard_m: float
    rot_max_rad_s: float
    decel_max_mps2: float
    lateral_active: bool
    preferred_side: int
    starboard_asymmetry_active: bool
    min_alteration_rad: float
    route_frame: MidMpcRouteFrame
    row_schedule: MidMpcRowSchedule = MidMpcRowSchedule()
    audit_row_count: int = 0
    prefix_active_k: int = 0
    prefix_psi_rad: tuple[float, ...] = ()
    prefix_u_mps: tuple[float, ...] = ()
    targets: tuple[MidMpcTarget, ...] = ()

    def __post_init__(self) -> None:
        """Normalize the pure optimizer input."""
        if not isinstance(self.own_ship, MidMpcOwnShip):
            raise TypeError("own_ship must be MidMpcOwnShip")
        if not isinstance(self.route_frame, MidMpcRouteFrame):
            raise TypeError("route_frame must be MidMpcRouteFrame")
        if not isinstance(self.row_schedule, MidMpcRowSchedule):
            raise TypeError("row_schedule must be MidMpcRowSchedule")
        heading = _ordered_pair(self.heading_bounds_rad, "heading_bounds_rad")
        speed = _ordered_pair(self.speed_bounds_mps, "speed_bounds_mps")
        prefix_psi = tuple(float(value) for value in self.prefix_psi_rad)
        prefix_u = tuple(float(value) for value in self.prefix_u_mps)
        targets = tuple(self.targets)
        _require_finite(
            self.route_bearing_rad,
            self.planned_speed_mps,
            *heading,
            *speed,
            self.cpa_safe_m,
            self.cpa_hard_m,
            self.rot_max_rad_s,
            self.decel_max_mps2,
            self.min_alteration_rad,
            *prefix_psi,
            *prefix_u,
        )
        if self.preferred_side not in (-1, 0, 1):
            raise ValueError("preferred_side must be -1, 0, or 1")
        if self.audit_row_count < 0:
            raise ValueError("audit_row_count must be non-negative")
        if self.prefix_active_k < 0:
            raise ValueError("prefix_active_k must be non-negative")
        if len(prefix_psi) < self.prefix_active_k or len(prefix_u) < self.prefix_active_k:
            raise ValueError("active prefix requires one heading and speed per step")
        if not all(isinstance(target, MidMpcTarget) for target in targets):
            raise TypeError("targets must contain MidMpcTarget values")
        object.__setattr__(self, "heading_bounds_rad", heading)
        object.__setattr__(self, "speed_bounds_mps", speed)
        object.__setattr__(self, "prefix_psi_rad", prefix_psi)
        object.__setattr__(self, "prefix_u_mps", prefix_u)
        object.__setattr__(self, "targets", targets)


@dataclass(frozen=True)
class MidMpcPreparedProblem:
    p: np.ndarray
    x0: np.ndarray
    lbx: np.ndarray
    ubx: np.ndarray
    lbg: np.ndarray
    ubg: np.ndarray

    def __post_init__(self) -> None:
        """Copy prepared vectors into immutable arrays."""
        for name in ("p", "x0", "lbx", "ubx", "lbg", "ubg"):
            object.__setattr__(self, name, _readonly_vector(getattr(self, name)))


@dataclass(frozen=True)
class MidMpcTrajectoryPoint:
    x_m: float
    y_m: float
    psi_rad: float
    u_mps: float
    t_s: float


@dataclass(frozen=True)
class MidMpcObjectiveComponents:
    colreg: float
    heading: float
    speed: float
    route: float
    asymmetry: float
    terminal: float
    cpa_slack: float
    direction_slack: float

    @property
    def total(self) -> float:
        """Return the weighted objective reconstructed from its terms."""
        return sum(vars(self).values())


@dataclass(frozen=True)
class MidMpcRowSpan:
    start: int
    count: int


@dataclass(frozen=True)
class MidMpcRowLayout:
    rot: MidMpcRowSpan
    speed_rate: MidMpcRowSpan
    prefix_psi: MidMpcRowSpan
    prefix_u: MidMpcRowSpan
    cpa: MidMpcRowSpan
    direction: MidMpcRowSpan
    min_alt: MidMpcRowSpan
    terminal: MidMpcRowSpan
    rule: MidMpcRowSpan
    zone: MidMpcRowSpan

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {name: {"start": span.start, "count": span.count} for name, span in vars(self).items()}


@dataclass(frozen=True)
class MidMpcResult:
    status: MidMpcStatus
    native_status: MidMpcStatus
    ipopt_return_status: str
    ipopt_iterations: int
    elapsed_ms: float
    objective_total: float
    seed_objective_total: float
    seed_max_constraint_violation: float
    objective_improvement: float
    decision_change_norm: float
    optimization_quality_passed: bool
    accepted_by_quality_gate: bool
    accepted_candidate_source: str
    accepted_iteration: int | None
    objective_components: MidMpcObjectiveComponents
    cpa_slack: float
    trajectory: tuple[MidMpcTrajectoryPoint, ...]
    prepared: MidMpcPreparedProblem
    raw_x: np.ndarray
    raw_f: float
    raw_g: np.ndarray
    raw_cpa_slack: float
    raw_dir_slack: float
    terminal_raw_x: np.ndarray
    terminal_raw_f: float
    terminal_raw_g: np.ndarray
    continuous_cpa_min_m: float
    continuous_cpa_violated: bool
    active_row_indices: tuple[int, ...]
    tight_row_indices: tuple[int, ...]
    max_constraint_violation: float
    max_decision_bound_violation: float
    row_layout: MidMpcRowLayout

    def __post_init__(self) -> None:
        """Normalize result enums, tuples, and diagnostic arrays."""
        object.__setattr__(self, "status", MidMpcStatus(self.status))
        object.__setattr__(self, "native_status", MidMpcStatus(self.native_status))
        object.__setattr__(self, "trajectory", tuple(self.trajectory))
        object.__setattr__(self, "raw_x", _readonly_vector(self.raw_x))
        object.__setattr__(self, "raw_g", _readonly_vector(self.raw_g))
        object.__setattr__(self, "terminal_raw_x", _readonly_vector(self.terminal_raw_x))
        object.__setattr__(self, "terminal_raw_g", _readonly_vector(self.terminal_raw_g))


def _readonly_vector(value: object) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True).reshape(-1)
    return np.frombuffer(array.tobytes(), dtype=array.dtype)


def _pair(value: tuple[float, float], name: str) -> tuple[float, float]:
    result = tuple(float(item) for item in value)
    if len(result) != 2:
        raise ValueError(f"{name} must contain exactly two values")
    return result  # type: ignore[return-value]


def _ordered_pair(value: tuple[float, float], name: str) -> tuple[float, float]:
    result = _pair(value, name)
    if result[0] > result[1]:
        raise ValueError(f"{name} lower bound must not exceed upper bound")
    return result


def _require_finite(*values: float) -> None:
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Mid-MPC inputs must be finite")
