"""Issue #67 slice 2: acceptance-only algorithm spacing profiles (config/).

The Issue #67 acceptance gate needs a nominal ownship-target centre distance
of at least 180 m (4 x 44.1 m Lpp). These checks pin the acceptance profile
files and their derivation, and guard that the shipped defaults stay at their
published 150 m values.
"""

from __future__ import annotations

import math

import pytest
from conftest import PROJECT_ROOT

from colav_simulator.cli import _load_algorithm_config
from colav_simulator.core.colav.colav_interface import VOWrapper
from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import VOParams
from colav_simulator.integrations.registry import IntegrationRegistry

VO_PROFILE = _load_algorithm_config(PROJECT_ROOT / "config/acceptance_issue67_vo.yaml")
FAN_MPC_PROFILE = _load_algorithm_config(PROJECT_ROOT / "config/acceptance_issue67_fan_mpc.yaml")
MID_MPC_PROFILE = _load_algorithm_config(PROJECT_ROOT / "config/acceptance_issue67_mid_mpc.yaml")

# Viknes footprint: the scenario family's model params are the geometry the
# VO planner sees at runtime (ownship legacy model params + viknes targets).
VIKNES_LENGTH_M = 8.45
VIKNES_WIDTH_M = 2.71
VO_INTEGRATION_MARGIN_M = 0.25


def _vo_params() -> VOParams:
    return VOParams.from_dict(VO_PROFILE["vo"])


def test_vo_acceptance_profile_keeps_hard_floor_at_least_190m_centre_distance() -> None:
    params = _vo_params()

    combined_hull_radius_m = 0.5 * (
        math.hypot(VIKNES_LENGTH_M, VIKNES_WIDTH_M)
        + math.hypot(VIKNES_LENGTH_M, VIKNES_WIDTH_M)
    )
    hard_floor_m = combined_hull_radius_m + params.hard_hull_clearance_m + VO_INTEGRATION_MARGIN_M

    # Nominal spacing target 190 m: 10 m above the 180 m acceptance gate.
    assert hard_floor_m >= 190.0
    assert params.preferred_hull_clearance_m >= params.hard_hull_clearance_m


def test_vo_acceptance_profile_changes_only_the_spacing_parameter_face() -> None:
    params = _vo_params()
    defaults = VOParams()

    changed = {
        name
        for name in ("length_os", "width_os", "d_min", "hard_hull_clearance_m", "preferred_hull_clearance_m")
        if getattr(params, name) != getattr(defaults, name)
    }
    assert params.to_dict() == {**defaults.to_dict(), **{name: getattr(params, name) for name in changed}}
    assert changed == {
        "length_os",
        "width_os",
        "d_min",
        "hard_hull_clearance_m",
        "preferred_hull_clearance_m",
    }
    # FCB45 footprint identity for static-hazard inflation.
    assert (params.length_os, params.width_os) == (44.1, 8.0)
    # CPA classification aligned with the acceptance distance.
    assert params.d_min == 190.0


def test_vo_acceptance_profile_builds_through_the_registry() -> None:
    algorithm = IntegrationRegistry().build_algorithm("vo", VO_PROFILE)

    assert isinstance(algorithm, VOWrapper)
    assert algorithm._vo._params.hard_hull_clearance_m == 182.0
    assert algorithm._vo._params.preferred_hull_clearance_m == 190.0
    assert algorithm._vo._params.d_min == 190.0


def test_fan_mpc_acceptance_profile_differs_from_shipped_only_in_collision_distance() -> None:
    shipped = _load_algorithm_config(PROJECT_ROOT / "config/potocnik_colreg_fan_mpc.yaml")

    assert FAN_MPC_PROFILE["kwargs"]["collision_distance_m"] == 190.0
    assert shipped["kwargs"]["collision_distance_m"] == 150.0
    acceptance_diff = {
        key: value
        for key, value in FAN_MPC_PROFILE["kwargs"].items()
        if shipped["kwargs"].get(key) != value
    }
    assert acceptance_diff == {"collision_distance_m": 190.0}


def test_mid_mpc_acceptance_profile_differs_from_shipped_only_in_cpa_safe() -> None:
    shipped = _load_algorithm_config(PROJECT_ROOT / "config/mid_mpc_ipopt.yaml")

    assert MID_MPC_PROFILE["kwargs"]["cpa_safe_m"] == 190.0
    assert shipped["kwargs"]["cpa_safe_m"] == 150.0
    acceptance_diff = {
        key: value
        for key, value in MID_MPC_PROFILE["kwargs"].items()
        if shipped["kwargs"].get(key) != value
    }
    assert acceptance_diff == {"cpa_safe_m": 190.0}


def test_acceptance_profiles_keep_factory_and_lock_identity() -> None:
    assert FAN_MPC_PROFILE["factory"] == "colav_simulator.integrations.potocnik_colreg_mpc:create"
    assert MID_MPC_PROFILE["factory"] == "colav_simulator.integrations.mid_mpc_ipopt:create"
    assert "factory" not in VO_PROFILE
    assert str(VO_PROFILE["dependency_lock"]).endswith("uv.lock")


if __name__ == "__main__":
    pytest.main([__file__])
