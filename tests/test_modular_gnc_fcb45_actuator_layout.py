"""FCB45 actuator layout asset: geometry, catalog registration, closed loop (s9c R3).

The s9c spec's Implementation Decisions promise an FCB45 actuator layout asset
extracted from the colleague's vendor ``ship_config.yaml``: 3 main thrusters
(+/-135 kN) at x = -18.094 m, y = -3/0/+3 m, and 2 bow tunnel thrusters
(+/-20 kN) at x = +21.906/+23.406 m, y = 0.  The allocator task space stays
strictly [X, Y, N] -- the roll channel is rejected by existing allocator
semantics (RA-12, VR-16), so no roll row exists by construction.

The layout registers as a selectable allocator-axis candidate; the recommended
stacks (acceptance default: ideal generalized forces) are pinned unchanged.
Per-actuator rate limits: ResolvedActuatorDynamics supports per-actuator
``rate_limit_n_per_s``, so the vendor-motivated values are mains 200 kN/s and
tunnel thrusters 50 kN/s (the catalog's own resolved scaffolds keep the
neutral 1e9 N/s pass-through rates).
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.actuator_dynamics import ResolvedActuatorDynamicsConfig
from colav_simulator.modular_gnc.allocator import KNOWN_ACTUATOR_LAYOUT_ASSETS, ActuatorLayoutAsset
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import AssetTrustLevel, CommandInput, DirectReference, NavigationState
from colav_simulator.modular_gnc.stack import ModularShipStack

LAYOUT_ID = "fcb45_actuator_layout_v1"
MAIN_FORCE_N = 135.0e3
TUNNEL_FORCE_N = 20.0e3
MAIN_X_M = -18.094
TUNNEL_X_M = (21.906, 23.406)
MAIN_Y_M = (-3.0, 0.0, 3.0)
ACTUATOR_IDS = (
    "main_thruster_port",
    "main_thruster_center",
    "main_thruster_starboard",
    "bow_tunnel_thruster_aft",
    "bow_tunnel_thruster_forward",
)
# Vendor-motivated per-actuator rate limits (mains 200 kN/s, tunnels 50 kN/s).
FCB45_RATE_LIMITS_N_PER_S = {
    "main_thruster_port": 200.0e3,
    "main_thruster_center": 200.0e3,
    "main_thruster_starboard": 200.0e3,
    "bow_tunnel_thruster_aft": 50.0e3,
    "bow_tunnel_thruster_forward": 50.0e3,
}
SERVICE_SPEED_MPS = 7.8
SETTLE_S = 100.0
ROUTE_LENGTH_M = 3000.0
MAX_TRANSIT_S = 450.0  # ideal baseline is 384.7 s; bound absorbs actuator lag
DT_S = 0.1
MAX_XTE_M = 10.0
MIN_SURGE_MPS = 5.0

IDEAL_RECOMMENDATIONS = {
    "pass_through_plant": "pass_through_plant+pass_through_guidance+pass_through_controller",
    "generic_3dof_plant": "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
    "generic_roll_4dof_plant": "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
    "fcb45_3dof_plant": "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
    "fcb45_roll_4dof_plant": "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
}


def _asset() -> ActuatorLayoutAsset:
    return KNOWN_ACTUATOR_LAYOUT_ASSETS[LAYOUT_ID]


def _catalog_entry(stack_id: str) -> dict:
    for entry in list_stack_catalog()["stacks"]:
        if entry["stack_id"] == stack_id:
            return entry
    raise AssertionError(f"stack {stack_id!r} not listed in catalog")


class TestFCB45LayoutAssetGeometry:
    def test_layout_asset_is_registered_and_integrity_holds(self) -> None:
        assert LAYOUT_ID in KNOWN_ACTUATOR_LAYOUT_ASSETS
        assert _asset().metadata.asset_id == LAYOUT_ID
        assert _asset().verify_integrity()
        assert _asset().actuator_ids() == ACTUATOR_IDS

    def test_three_mains_with_vendor_geometry_and_limits(self) -> None:
        mains = [spec for spec in _asset().actuators if spec.kind == "main"]
        assert len(mains) == 3
        for spec in mains:
            assert spec.position_body_m[0] == pytest.approx(MAIN_X_M, abs=1e-6)
            assert spec.position_body_m[1] in [pytest.approx(y, abs=1e-6) for y in MAIN_Y_M]
            assert spec.orientation_body_rad == 0.0
            assert spec.min_force_n == -MAIN_FORCE_N
            assert spec.max_force_n == MAIN_FORCE_N

    def test_two_bow_tunnel_thrusters_with_vendor_geometry_and_limits(self) -> None:
        tunnels = [spec for spec in _asset().actuators if spec.kind == "tunnel_thruster"]
        assert len(tunnels) == 2
        for spec in tunnels:
            assert spec.position_body_m[0] in [pytest.approx(x, abs=1e-6) for x in TUNNEL_X_M]
            assert spec.position_body_m[1] == 0.0
            assert spec.orientation_body_rad == pytest.approx(0.5 * math.pi)
            assert spec.min_force_n == -TUNNEL_FORCE_N
            assert spec.max_force_n == TUNNEL_FORCE_N

    def test_effectiveness_matrix_is_strictly_3dof_and_fully_actuated(self) -> None:
        matrix = _asset().effectiveness_matrix()
        assert matrix.shape == (3, 5)  # no roll row: roll channel rejected (RA-12)
        # Main thrusters push along x: yaw arms come from the y offset (N = -y*Fx).
        # Tunnels push along y: yaw arms are the x lever (N = x*Fy).
        assert matrix[0, 0] == pytest.approx(1.0)
        assert matrix[1, 0] == 0.0
        assert matrix[2, 0] == pytest.approx(-MAIN_Y_M[0])  # port main at y=-3 -> +3 arm
        assert matrix[2, 1] == pytest.approx(0.0)  # center main on the x axis
        assert matrix[2, 2] == pytest.approx(-MAIN_Y_M[2])  # starboard main at y=+3 -> -3 arm
        assert matrix[1, 3] == pytest.approx(1.0)
        assert matrix[2, 3] == pytest.approx(TUNNEL_X_M[0])
        assert matrix[1, 4] == pytest.approx(1.0)
        assert matrix[2, 4] == pytest.approx(TUNNEL_X_M[1])
        assert not matrix[1, :3].any()  # mains generate no sway force
        assert np.linalg.matrix_rank(matrix) == 3  # fully actuated in [X, Y, N]

    def test_vendor_calibrated_provenance_is_explicit(self) -> None:
        metadata = _asset().metadata
        assert metadata.trust_level == AssetTrustLevel.CALIBRATED
        assert "ship_config.yaml" in str(metadata.provenance)
        assert metadata.provenance["validated_for_vessel"] is False


class TestFCB45LayoutCatalogRegistration:
    def test_layout_is_a_selectable_actuation_axis_candidate(self) -> None:
        layouts = list_stack_catalog()["module_axes"]["actuation"]["layouts"]
        entry = next((e for e in layouts if e["layout_asset_id"] == LAYOUT_ID), None)
        assert entry is not None, "FCB45 layout must appear in the actuation layout axis"
        assert entry["drive_nature"] == "fully actuated"
        assert entry["identity"] == "data_driven_allocator"

    @pytest.mark.parametrize("plant", ["fcb45_3dof_plant", "fcb45_roll_4dof_plant"])
    @pytest.mark.parametrize("with_actuator", [False, True])
    def test_fcb45_plant_stacks_bind_the_layout_and_reassemble(self, plant: str, with_actuator: bool) -> None:
        stack_id = (
            f"{plant}+pass_through_guidance+fcb45_marine_pid"
            f"+data_driven_allocator[{LAYOUT_ID}]"
            + (f"+resolved_actuator_dynamics[{LAYOUT_ID}]" if with_actuator else "")
        )
        entry = _catalog_entry(stack_id)
        modules = entry["config"]["modules"]
        assert modules["allocator"]["parameters"]["layout_asset_id"] == LAYOUT_ID
        if with_actuator:
            assert modules["actuator"]["identity"] == "resolved_actuator_dynamics"
        else:
            assert "actuator" not in modules
        stack = ModularShipStack.from_config(normalize_ship_modules(entry["config"]), dt_s=DT_S)
        assert "TRANSIT" in {task.name for task in stack.modules.supported_tasks}

    def test_recommendations_and_default_stack_stay_ideal(self) -> None:
        catalog = list_stack_catalog()
        assert catalog["default_stack_id"] == IDEAL_RECOMMENDATIONS["pass_through_plant"]
        assert catalog["recommended_stack_ids_by_plant"] == IDEAL_RECOMMENDATIONS


class TestFCB45LayoutResolvedActuatorRates:
    def test_resolved_dynamics_accept_per_actuator_vendor_rates(self) -> None:
        config = ResolvedActuatorDynamicsConfig(
            layout_asset_id=LAYOUT_ID,
            rate_limit_n_per_s=dict(FCB45_RATE_LIMITS_N_PER_S),
            delay_ticks=dict.fromkeys(ACTUATOR_IDS, 0),
        )
        mains = {k: v for k, v in config.rate_limit_n_per_s.items() if "main" in k}
        tunnels = {k: v for k, v in config.rate_limit_n_per_s.items() if "tunnel" in k}
        assert set(config.rate_limit_n_per_s) == set(ACTUATOR_IDS)
        assert set(mains.values()) == {200.0e3}
        assert set(tunnels.values()) == {50.0e3}

    def test_resolved_dynamics_reject_partial_rate_coverage(self) -> None:
        partial = dict(FCB45_RATE_LIMITS_N_PER_S)
        partial.pop("main_thruster_center")
        with pytest.raises(ValueError, match="must declare every layout actuator"):
            ResolvedActuatorDynamicsConfig(
                layout_asset_id=LAYOUT_ID,
                rate_limit_n_per_s=partial,
                delay_ticks=dict.fromkeys(ACTUATOR_IDS, 0),
            )


class TestFCB45LayoutClosedLoopSmoke:
    @staticmethod
    def _smoke_stack() -> ModularShipStack:
        """Tier1 plant + allocator + resolved actuator with vendor rates, via facade."""
        entry = _catalog_entry("fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid")
        # Deep-copy: the entry belongs to the lru_cached catalog document.
        config = copy.deepcopy(entry["config"])
        config["modules"]["allocator"] = {
            "identity": "data_driven_allocator",
            "parameters": {"layout_asset_id": LAYOUT_ID},
        }
        config["modules"]["actuator"] = {
            "identity": "resolved_actuator_dynamics",
            "parameters": {
                "layout_asset_id": LAYOUT_ID,
                "rate_limit_n_per_s": dict(FCB45_RATE_LIMITS_N_PER_S),
                "delay_ticks": dict.fromkeys(ACTUATOR_IDS, 0),
            },
        }
        config["overrides"] = {"scheduler": {"controller_period_ticks": 1}}
        return ModularShipStack.from_config(normalize_ship_modules(config), dt_s=DT_S)

    def test_straight_tracking_does_not_degrade_through_allocation(self) -> None:
        """3000 m calm-straight leg must complete with the XTE gate intact."""
        stack = self._smoke_stack()
        stack.reset(NavigationState(0.0, 0.0, 0.0, SERVICE_SPEED_MPS, 0.0, 0.0), seed=11)
        values = np.zeros(9)
        values[3] = SERVICE_SPEED_MPS

        total_ticks = int((SETTLE_S + MAX_TRANSIT_S) / DT_S)
        settle_ticks = int(SETTLE_S / DT_S)
        max_xte = 0.0
        min_surge = SERVICE_SPEED_MPS
        saw_allocator_layout = False
        for tick in range(total_ticks):
            out = stack.step(CommandInput.direct(tick, DirectReference(values, tick)), dt_s=DT_S)
            assert out.failure is None, f"facade failure at tick {tick}: {out.failure}"
            nav = out.navigation
            max_xte = max(max_xte, abs(nav.east_m))
            min_surge = min(min_surge, nav.surge_mps)
            trace = out.actuator_trace
            if trace is not None:
                assert set(trace.actuator_outputs_n) == set(ACTUATOR_IDS)
            # The resolved actuator owns the achieved-load channel in this stack;
            # the allocator solution surfaces on the module seam.
            solution = stack.modules.allocator_solution()
            if solution is not None and solution.layout_asset_id == LAYOUT_ID:
                saw_allocator_layout = True
            if tick == settle_ticks - 1:
                north_start_m = nav.north_m  # the 3000 m leg starts here, not in settle
            elif tick >= settle_ticks and nav.north_m - north_start_m >= ROUTE_LENGTH_M:
                assert saw_allocator_layout, "allocator solutions must carry the FCB45 layout id"
                assert max_xte <= MAX_XTE_M
                assert min_surge >= MIN_SURGE_MPS
                return
        raise AssertionError(
            f"smoke transit did not cover {ROUTE_LENGTH_M} m within {MAX_TRANSIT_S} s "
            f"(reached {nav.north_m - north_start_m:.1f} m)"
        )
