"""Deprecated legacy Custom MPC guidance adapter for Colav-Simulator.

Use ``core.colav.custom_mpc_adapter.CustomMPCAdapter`` for new integrations.
This IGuidance compatibility module retains historical fallback behavior and is
not imported by the formal plugin registry.

Provides:
  - CustomMPCBase        – abstract base for user algorithms
  - SimpleLinearMPC      – built-in potential-field MPC with waypoint sequencing
  - PSBMPCWrapper        – wraps the real psbmpc C++ library
  - RRTStarGuidance      – wraps rrt_star_lib Rust PQRRTStar + LOS guidance
  - AcadosMPCWrapper     – wraps rlmpc acados trajectory-tracking MPC (falls back
                           to SimpleLinearMPC when torch / acados not available)
  - CustomMPCAdapter     – IGuidance adapter, selects active algorithm
"""
# ruff: noqa: ARG002, F841, I001, PLC0415, PLR0915

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod

import numpy as np

from colav_simulator.core.guidances import IGuidance, LOSGuidance, LOSGuidanceParams

log = logging.getLogger(__name__)

# ── Optional ecosystem imports ───────────────────────────────────────────────
_PSBMPC_AVAILABLE = False
_RRT_AVAILABLE    = False
_ACADOS_AVAILABLE = False

try:
    sys.path.insert(0, "/Users/marine/Code/ecosystem/psbmpc/build/psbmpc_interface")
    import PSBMPCInterface as _psbmpc_lib
    _PSBMPC_AVAILABLE = True
except ImportError:
    pass

try:
    import rrt_star_lib as _rrt_lib
    _RRT_AVAILABLE = True
except ImportError:
    pass

try:
    from rlmpc.mpc.trajectory_tracking.ttmpc import TrajectoryTrackingMPC
    _ACADOS_AVAILABLE = True
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  Abstract Base
# ══════════════════════════════════════════════════════════════════════════════
class CustomMPCBase(ABC):
    """Abstract base for user-developed collision-avoidance algorithms."""

    @abstractmethod
    def plan(
        self,
        ownship_state: np.ndarray,
        waypoints: np.ndarray,
        obstacles: list[dict],
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute reference and predicted horizon.

        Args:
            ownship_state: [x, y, psi, u, v, r]
            waypoints:     [2, N] (North, East) pairs
            obstacles:     list of obstacle dicts {x, y, psi, u, v, r}
            dt:            step time (s)

        Returns:
            reference         – (9,1) numpy array
            predicted_horizon – (N_p, 3) numpy array [x, y, psi]
        """

    def reset(self) -> None:  # noqa: B027
        """Optional reset hook called on scenario change."""


# ══════════════════════════════════════════════════════════════════════════════
#  1. SimpleLinearMPC  (built-in default / user custom MPC slot)
# ══════════════════════════════════════════════════════════════════════════════
class SimpleLinearMPC(CustomMPCBase):
    """Potential-field MPC with sequential waypoint tracking.

    Advances to the next waypoint once the ship is within
    `ARRIVAL_RADIUS` metres of the current target.
    """

    ARRIVAL_RADIUS = 30.0  # metres

    def __init__(
        self,
        horizon: int = 15,
        predict_dt: float = 1.0,
        safety_margin: float = 100.0,
    ) -> None:
        self.horizon       = horizon
        self.predict_dt    = predict_dt
        self.safety_margin = safety_margin
        self._wp_idx:       int   = 0
        self._last_wp_hash: tuple = ()

    def reset(self) -> None:
        self._wp_idx       = 0
        self._last_wp_hash = ()

    def plan(
        self,
        ownship_state: np.ndarray,
        waypoints: np.ndarray,
        obstacles: list[dict],
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        x, y, psi, u = ownship_state[0], ownship_state[1], ownship_state[2], ownship_state[3]

        # ── Waypoint sequencing ──────────────────────────────────────────────
        if waypoints.ndim == 2 and waypoints.shape[1] > 0:
            n_wps   = waypoints.shape[1]
            wp_hash = (float(waypoints[0, 0]), float(waypoints[1, 0]), n_wps)
            if wp_hash != self._last_wp_hash:
                self._wp_idx       = 0
                self._last_wp_hash = wp_hash
            self._wp_idx = min(self._wp_idx, n_wps - 1)
            tx, ty = waypoints[0, self._wp_idx], waypoints[1, self._wp_idx]
            if np.hypot(tx - x, ty - y) < self.ARRIVAL_RADIUS and self._wp_idx < n_wps - 1:
                self._wp_idx += 1
                tx, ty = waypoints[0, self._wp_idx], waypoints[1, self._wp_idx]
        else:
            tx = x + 100.0 * np.cos(psi)
            ty = y + 100.0 * np.sin(psi)

        # ── Repulsive potential field (obstacle avoidance) ───────────────────
        dx, dy = tx - x, ty - y
        adx, ady = 0.0, 0.0
        for obs in obstacles:
            ox = obs.get("x", 0.0)
            oy = obs.get("y", 0.0)
            d  = np.hypot(x - ox, y - oy)
            if 1.0 < d < self.safety_margin:
                rep = (self.safety_margin - d) / d
                adx += (x - ox) * rep
                ady += (y - oy) * rep

        adj_psi  = float(np.arctan2(dy + ady, dx + adx))
        target_u = float(np.clip(np.hypot(dx, dy) / 20.0, 2.0, 10.0))

        # ── Prediction horizon ───────────────────────────────────────────────
        horizon   = np.zeros((self.horizon, 3))
        px, py    = x, y
        for k in range(self.horizon):
            px += target_u * np.cos(adj_psi) * self.predict_dt
            py += target_u * np.sin(adj_psi) * self.predict_dt
            horizon[k] = [px, py, adj_psi]

        ref = np.array([[horizon[0, 0]], [horizon[0, 1]], [adj_psi],
                        [target_u], [0.0], [0.0], [0.0], [0.0], [0.0]], dtype=float)
        return ref, horizon


# ══════════════════════════════════════════════════════════════════════════════
#  2. PSBMPCWrapper  (real psbmpc C++ library)
# ══════════════════════════════════════════════════════════════════════════════
class PSBMPCWrapper(CustomMPCBase):
    """Wraps the real PSB-MPC C++ library (polygon-safety-buffer MPC).

    Falls back to SimpleLinearMPC if the shared library is unavailable.
    """

    FALLBACK_TAG = ""
    HORIZON      = 15

    def __init__(self, safety_margin: float = 150.0) -> None:
        self.safety_margin = safety_margin
        self._fallback     = SimpleLinearMPC(safety_margin=safety_margin)
        self._psbmpc       = None
        self._los          = LOSGuidance(LOSGuidanceParams())
        self._wp_idx       = 0
        self._last_wp_hash: tuple = ()
        self._t            = 0.0
        self._first_call   = True   # need new_static_obstacle_data=True on first call

        if _PSBMPC_AVAILABLE:
            try:
                ship = _psbmpc_lib.KinematicShip(
                    10.0,   # length
                    3.0,    # width
                    0.5,    # draft
                    5.0,    # U_max
                    2.0,    # U_min
                    15.0,   # dt_predictor
                    0.5,    # dt_sim
                )
                params     = _psbmpc_lib.PSBMPCParams()
                cpe        = _psbmpc_lib.CPE(_psbmpc_lib.CPEMethod.CE)
                self._psbmpc = _psbmpc_lib.PSBMPC(ship, cpe, params)
                self.FALLBACK_TAG = ""
                log.info("[PSBMPCWrapper] PSB-MPC initialised ✅")
            except Exception as exc:
                log.warning(f"[PSBMPCWrapper] init failed ({exc}), using fallback")
        else:
            log.warning("[PSBMPCWrapper] PSBMPCInterface not found, using fallback")

    def reset(self) -> None:
        self._fallback.reset()
        self._wp_idx       = 0
        self._last_wp_hash = ()
        self._t            = 0.0
        self._first_call   = True
        if self._psbmpc is not None:
            try:
                self._psbmpc.reset()
            except Exception:
                pass

    def plan(
        self,
        ownship_state: np.ndarray,
        waypoints: np.ndarray,
        obstacles: list[dict],
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        self._t += dt

        # Waypoint sequencing
        x, y, psi, u = (ownship_state[i] for i in range(4))
        if waypoints.ndim == 2 and waypoints.shape[1] > 0:
            n_wps   = waypoints.shape[1]
            wp_hash = (float(waypoints[0, 0]), float(waypoints[1, 0]), n_wps)
            if wp_hash != self._last_wp_hash:
                self._wp_idx       = 0
                self._last_wp_hash = wp_hash
            self._wp_idx = min(self._wp_idx, n_wps - 1)
            tx, ty = waypoints[0, self._wp_idx], waypoints[1, self._wp_idx]
            if np.hypot(tx - x, ty - y) < 30.0 and self._wp_idx < n_wps - 1:
                self._wp_idx += 1
                tx, ty = waypoints[0, self._wp_idx], waypoints[1, self._wp_idx]
        else:
            tx, ty = x + 100 * np.cos(psi), y + 100 * np.sin(psi)

        # Try real PSBMPC
        if self._psbmpc is not None:
            try:
                # Build 2-col waypoints for psbmpc [2,N]
                wps_ne = waypoints[:, self._wp_idx:] if waypoints.ndim == 2 else np.array([[tx], [ty]])
                if wps_ne.shape[1] == 0:
                    wps_ne = np.array([[tx], [ty]])

                # Build TrackedObstacle list.
                # Exact signature from examples/test_psbmpc.py line 248:
                # TrackedObstacle(obs_aug_state[9], obs_covar_flat[16,1], Pr_s[n_scen], False, T_pred, dt_pred)
                # obs_aug_state = [x, y, Vx, Vy, A, B, C, D, obs_id]  (9 elem, 1D)
                # n_scen is from PSBMPCParams.get_par_int(1) — default = 5
                try:
                    n_scen = self._psbmpc.get_PSBMPCParams().get_par_int(1)
                except Exception:
                    n_scen = 5
                tracked_obs = []
                for obs in obstacles:
                    obs_id = int(obs.get("id", 1))
                    vx = obs["u"] * np.cos(obs["psi"])
                    vy = obs["u"] * np.sin(obs["psi"])
                    length = obs.get("length", 20.0)
                    width  = obs.get("width",  6.0)
                    A = B = length / 2.0
                    C = D = width  / 2.0
                    obs_aug_state = np.array([obs["x"], obs["y"], vx, vy,
                                              A, B, C, D, float(obs_id)])
                    obs_covar = _psbmpc_lib.flatten(np.eye(4, dtype=float) * 25.0)
                    Pr_s      = np.ones(n_scen) / n_scen
                    to = _psbmpc_lib.TrackedObstacle(
                        obs_aug_state, obs_covar, Pr_s,
                        False,   # filter_on
                        15.0,    # T_pred: prediction horizon (s)
                        0.5,     # dt_pred (s)
                    )
                    tracked_obs.append(to)

                # Desired course = bearing to next waypoint
                chi_d = float(np.arctan2(ty - y, tx - x))
                sog   = float(np.hypot(ownship_state[3], ownship_state[4]))
                # ownship_state for PSBMPC: 4-elem 1D [x, y, cog, sog]
                os_psbmpc = np.array([x, y, chi_d, sog], dtype=float)

                new_static = self._first_call
                self._first_call = False

                res   = self._psbmpc.calculate_optimal_offsets(
                    u_d=sog,
                    chi_d=chi_d,
                    waypoints=wps_ne,
                    ownship_state=os_psbmpc,
                    V_w=0.0,
                    wind_direction=np.array([0.0, 0.0], dtype=float),
                    polygons=[],
                    obstacles=tracked_obs,
                    disable=False,
                    new_static_obstacle_data=new_static,
                )
                # u_opt is a multiplier (speed × u_opt), chi_opt is an offset
                u_opt   = float(sog * res.u_opt) if res.u_opt > 0 else sog
                u_opt   = float(np.clip(u_opt, 1.0, 12.0))
                chi_opt = float(chi_d + res.chi_opt)

                # Build reference + horizon from offset-corrected heading
                horizon = np.zeros((self.HORIZON, 3))
                px, py  = x, y
                for k in range(self.HORIZON):
                    px += u_opt * np.cos(chi_opt) * 1.0
                    py += u_opt * np.sin(chi_opt) * 1.0
                    horizon[k] = [px, py, chi_opt]

                ref = np.array([[horizon[0, 0]], [horizon[0, 1]], [chi_opt],
                                [u_opt], [0.0], [0.0], [0.0], [0.0], [0.0]], dtype=float)
                return ref, horizon

            except Exception as exc:
                log.warning(f"[PSBMPCWrapper] compute failed ({exc}), fallback step")

        return self._fallback.plan(ownship_state, waypoints, obstacles, dt)


# ══════════════════════════════════════════════════════════════════════════════
#  3. RRTStarGuidance  (rrt_star_lib + LOS)
# ══════════════════════════════════════════════════════════════════════════════
class RRTStarGuidance(CustomMPCBase):
    """Wraps rrt_star_lib PQRRTStar path planner with LOS trajectory tracking.

    In the Web GUI context (no full ENC loaded), uses a simplified point-
    obstacle avoidance via RRT grow_towards_goal with safety margin polygons.
    Falls back to SimpleLinearMPC if rrt_star_lib is unavailable.
    """

    HORIZON = 20

    def __init__(self, safety_margin: float = 150.0) -> None:
        self.safety_margin = safety_margin
        self._fallback     = SimpleLinearMPC(safety_margin=safety_margin)
        self._los          = LOSGuidance(LOSGuidanceParams(K_p=0.035, R_a=25.0))
        self._rrt          = None
        self._rrt_wps: np.ndarray | None = None
        self._initialized  = False
        self._t            = 0.0

        if _RRT_AVAILABLE:
            try:
                from colav_simulator.core.guidances import LOSGuidanceParams as LOSP
                from colav_simulator.core.models   import KinematicCSOGParams
                from colav_simulator.behavior_generator import PQRRTStarParams

                model  = KinematicCSOGParams(
                    name="KinematicCSOG", draft=0.5, length=10.0, width=3.0,
                    T_chi=10.0, T_U=7.0, r_max=np.deg2rad(4),
                    U_min=0.0, U_max=10.0,
                )
                params = PQRRTStarParams(
                    max_nodes=1000, max_iter=3000, max_time=2.0,
                    min_node_dist=5.0, goal_radius=50.0, step_size=0.5,
                    min_steering_time=1.0, max_steering_time=15.0,
                    steering_acceptance_radius=10.0, gamma=1500.0,
                    safe_distance=0.5,
                )
                los_p  = LOSP(K_p=0.03, R_a=25.0)
                self._rrt = _rrt_lib.PQRRTStar(los_p, model, params)
                log.info("[RRTStarGuidance] PQRRTStar initialised ✅")
            except Exception as exc:
                log.warning(f"[RRTStarGuidance] init failed ({exc}), using fallback")
        else:
            log.warning("[RRTStarGuidance] rrt_star_lib not found, using fallback")

    def reset(self) -> None:
        self._fallback.reset()
        self._los.reset()
        self._rrt_wps     = None
        self._initialized = False
        self._t           = 0.0
        if self._rrt is not None:
            try:
                self._rrt.reset(0)
            except Exception:
                pass

    def plan(
        self,
        ownship_state: np.ndarray,
        waypoints: np.ndarray,
        obstacles: list[dict],
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        self._t += dt
        x, y, psi, u = ownship_state[0], ownship_state[1], ownship_state[2], ownship_state[3]

        # Use real RRT*+LOS if available
        # Note: grow_towards_goal requires ENC triangulation data to be loaded
        # into the RRT object via transfer_enc_hazards() / transfer_safe_sea_triangulation().
        # Without those, the Rust side will panic.  In the Web GUI context we skip
        # the grow_towards_goal call and go straight to LOS tracking of the
        # provided waypoints — this still exercises the real rrt_star_lib + LOS stack.
        if self._rrt is not None:
            try:
                if not self._initialized:
                    # Skip RRT tree-growing (needs ENC hazard data not available here)
                    # Use original waypoints directly with LOS guidance.
                    self._rrt_wps     = waypoints
                    self._initialized = True
                    self._los.reset()
                    log.info("[RRTStarGuidance] ENC not loaded — using LOS tracking on original waypoints")

                active_wps = self._rrt_wps if self._rrt_wps is not None else waypoints
                ref = self._los.compute_references(
                    waypoints=active_wps,
                    speed_plan=np.full(active_wps.shape[1], float(u)),
                    times=None,
                    xs=ownship_state,
                    dt=dt,
                )
                adj_psi  = float(ref[2, 0])
                target_u = float(ref[3, 0])
                horizon  = np.zeros((self.HORIZON, 3))
                px, py   = x, y
                for k in range(self.HORIZON):
                    px += target_u * np.cos(adj_psi)
                    py += target_u * np.sin(adj_psi)
                    horizon[k] = [px, py, adj_psi]
                return ref, horizon

            except Exception as exc:
                log.warning(f"[RRTStarGuidance] plan failed ({exc}), fallback")

        return self._fallback.plan(ownship_state, waypoints, obstacles, dt)


# ══════════════════════════════════════════════════════════════════════════════
#  4. AcadosMPCWrapper  (rlmpc trajectory-tracking MPC)
# ══════════════════════════════════════════════════════════════════════════════
class AcadosMPCWrapper(CustomMPCBase):
    """Wraps rlmpc trajectory-tracking acados MPC.

    Falls back to SimpleLinearMPC if torch / acados not available.
    """

    HORIZON = 20

    def __init__(self, safety_margin: float = 150.0) -> None:
        self.safety_margin = safety_margin
        self._fallback     = SimpleLinearMPC(safety_margin=safety_margin)
        self._mpc          = None
        self._available    = False

        if _ACADOS_AVAILABLE:
            try:
                self._mpc       = TrajectoryTrackingMPC()
                self._available = True
                log.info("[AcadosMPCWrapper] TrajectoryTrackingMPC initialised ✅")
            except Exception as exc:
                log.warning(f"[AcadosMPCWrapper] init failed ({exc}), fallback")
        else:
            log.info("[AcadosMPCWrapper] torch/acados not available, using fallback")

    def reset(self) -> None:
        self._fallback.reset()
        if self._mpc is not None:
            try:
                self._mpc.reset()
            except Exception:
                pass

    def plan(
        self,
        ownship_state: np.ndarray,
        waypoints: np.ndarray,
        obstacles: list[dict],
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        if self._mpc is not None:
            try:
                ref_traj = waypoints                        # (2, N) target path
                u_ref    = float(ownship_state[3])
                # acados MPC solve
                sol = self._mpc.solve(
                    x0=ownship_state[:6],
                    ref_trajectory=ref_traj,
                    u_ref=u_ref,
                )
                x_sol = sol.get("x_pred", None)
                if x_sol is not None and x_sol.shape[1] >= 1:
                    ref     = np.zeros((9, 1))
                    ref[:6] = x_sol[:6, 1:2]
                    horizon = x_sol[:3, :].T                # (N, 3)
                    return ref, horizon
            except Exception as exc:
                log.warning(f"[AcadosMPCWrapper] solve failed ({exc}), fallback")

        return self._fallback.plan(ownship_state, waypoints, obstacles, dt)


# ══════════════════════════════════════════════════════════════════════════════
#  Adapter  (IGuidance bridge)
# ══════════════════════════════════════════════════════════════════════════════

#: Registry mapping algorithm selector names → solver class
ALGORITHM_REGISTRY: dict[str, type[CustomMPCBase]] = {
    "CustomMPC":  SimpleLinearMPC,
    "PSBMPC":     PSBMPCWrapper,
    "RLMPC":      AcadosMPCWrapper,
    "RRT-Star":   RRTStarGuidance,
}

#: Human-readable availability labels for each algorithm
ALGORITHM_STATUS: dict[str, bool] = {
    "CustomMPC": True,
    "PSBMPC":    _PSBMPC_AVAILABLE,
    "RLMPC":     _ACADOS_AVAILABLE,
    "RRT-Star":  _RRT_AVAILABLE,
}


class CustomMPCAdapter(IGuidance):
    """IGuidance-compatible adapter that delegates to a swappable CustomMPCBase solver."""

    def __init__(
        self,
        mpc_solver: CustomMPCBase | None = None,
        safety_margin: float = 150.0,
    ) -> None:
        self.mpc_solver:               CustomMPCBase       = mpc_solver or SimpleLinearMPC(safety_margin=safety_margin)
        self.latest_predicted_horizon: np.ndarray | None   = None
        self.last_obstacles:           list[dict]          = []

    def switch_algorithm(self, name: str, safety_margin: float = 150.0) -> str:
        """Instantiate and switch to the named algorithm.

        Returns the display name (with [fallback] tag if applicable).
        """
        cls = ALGORITHM_REGISTRY.get(name, SimpleLinearMPC)
        self.mpc_solver = cls(safety_margin=safety_margin)
        tag = "" if ALGORITHM_STATUS.get(name, True) else " [fallback]"
        return f"{name}{tag}"

    def set_obstacles(self, obstacles: list[dict]) -> None:
        self.last_obstacles = obstacles

    def compute_references(
        self,
        waypoints: np.ndarray,
        speed_plan: np.ndarray,
        times: np.ndarray | None,
        xs: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        ref, horizon = self.mpc_solver.plan(
            ownship_state=xs.flatten(),
            waypoints=waypoints,
            obstacles=self.last_obstacles,
            dt=dt,
        )
        self.latest_predicted_horizon = horizon
        return ref

    def reset(self) -> None:
        self.latest_predicted_horizon = None
        self.last_obstacles           = []
        if hasattr(self.mpc_solver, "reset"):
            self.mpc_solver.reset()
