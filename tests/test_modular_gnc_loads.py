"""Comprehensive tests for vessel environmental loads, asset validation, and current de-duplication (Issue #50)."""

from __future__ import annotations

import math

import pytest

from colav_simulator.modular_gnc.configuration import (
    UnsupportedModuleCombinationError,
    normalize_ship_modules,
)
from colav_simulator.modular_gnc.contracts import (
    ApplicabilityDomain,
    AssetIntegrityError,
    AssetMetadata,
    AssetMissingError,
    AssetTrustLevel,
    CommandInput,
    CurrentReference,
    CurrentSample,
    CurrentStrategy,
    EnvironmentalLoads,
    EnvironmentTruth,
    MeanDriftSourceSample,
    NavigationState,
    OutOfDomainError,
    PlantState,
    VesselLoad,
    WaveFieldSample,
    WindSample,
)
from colav_simulator.modular_gnc.load_model import (
    DEFAULT_INFERRED_CURRENT_ASSET,
    DEFAULT_OCIMF_WIND_ASSET,
    DEFAULT_TABLE_CURRENT_ASSET,
    CurrentCoeffEntry,
    CurrentCoeffTableAsset,
    CurrentLoadModel,
    EnvironmentalLoadModel,
    VesselEnvironmentalParameters,
    WindCoeffEntry,
    WindCoeffTableAsset,
    WindLoadModel,
    world_ne_to_body_velocity,
)
from colav_simulator.modular_gnc.stack import ModularShipStack


@pytest.fixture
def standard_vessel_params() -> VesselEnvironmentalParameters:
    """Standard 45m vessel geometry parameters."""
    return VesselEnvironmentalParameters(
        length_between_perpendiculars_m=44.1,
        beam_m=8.0,
        draft_m=1.55,
        wind_frontal_area_m2=50.0,
        wind_lateral_area_m2=150.0,
        wind_z_center_m=3.0,
        wind_roll_moment_arm_m=3.0,
        air_density_kg_m3=1.225,
        water_depth_m=50.0,
        kg_m=2.0,
        current_roll_moment_arm_m=1.5,
        water_density_kg_m3=1025.0,
    )


def make_truth(
    wind_ne: tuple[float, float] = (0.0, 0.0),
    current_ne: tuple[float, float] = (0.0, 0.0),
) -> EnvironmentTruth:
    """Helper to construct EnvironmentTruth for testing."""
    return EnvironmentTruth(
        wind=WindSample(velocity_ne=wind_ne),
        current=CurrentSample(velocity_ne=current_ne, reference=CurrentReference.SURFACE),
        wave=WaveFieldSample(significant_height_m=0.0, peak_period_s=8.0, direction_to_rad=0.0),
        mean_drift=MeanDriftSourceSample(components=()),
        time_s=0.0,
        tick=0,
    )


# ---------------------------------------------------------------------------
# 1. Zero Loads Test
# ---------------------------------------------------------------------------


def test_zero_environmental_loads(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify zero wind and current velocity produce strictly zero vessel loads."""
    truth = make_truth(wind_ne=(0.0, 0.0), current_ne=(0.0, 0.0))
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
    )
    loads = model.compute_loads(truth, nav)

    assert loads.wind == VesselLoad.zero()
    assert loads.current == VesselLoad.zero()
    assert loads.total == VesselLoad.zero()
    assert loads.total.surge_n == 0.0
    assert loads.total.sway_n == 0.0
    assert loads.total.yaw_nm == 0.0
    assert loads.total.roll_nm == 0.0


# ---------------------------------------------------------------------------
# 2. Basis Tests (Single-Axis Physical Vectors)
# ---------------------------------------------------------------------------


def test_basis_head_wind(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify head wind against vessel heading North produces retarding surge force (Fx < 0)."""
    # Ship heading North (0 rad), wind blowing from North towards South: velocity_ne = (-10.0, 0.0)
    truth = make_truth(wind_ne=(-10.0, 0.0), current_ne=(0.0, 0.0))
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.NONE,
    )
    loads = model.compute_loads(truth, nav)

    # In OCIMF table: at 180 deg relative (wind from bow), cx is negative, cy is 0, cn is 0
    assert loads.wind.surge_n < 0.0  # retarding surge
    assert math.isclose(loads.wind.sway_n, 0.0, abs_tol=1e-9)
    assert math.isclose(loads.wind.yaw_nm, 0.0, abs_tol=1e-9)


def test_basis_tail_wind(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify tail wind (apparent angle 0 deg) produces expected surge force per frozen source mock table."""
    # Ship heading North (0 rad), wind blowing from South towards North: velocity_ne = (10.0, 0.0)
    truth = make_truth(wind_ne=(10.0, 0.0), current_ne=(0.0, 0.0))
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.NONE,
    )
    loads = model.compute_loads(truth, nav)

    # In bundled mock OCIMF table from frozen source env_engines, apparent angle 0 deg has Cx = -0.60
    # Expected Fx = 0.5 * 1.225 * 100 * (-0.60) * 50.0 = -1837.5 N (< 0.0)
    assert loads.wind.surge_n < 0.0
    assert math.isclose(loads.wind.surge_n, -1837.5, rel_tol=1e-6)
    assert math.isclose(loads.wind.sway_n, 0.0, abs_tol=1e-9)
    assert math.isclose(loads.wind.yaw_nm, 0.0, abs_tol=1e-9)


def test_basis_beam_wind(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify beam wind produces dominant sway force and roll moment."""
    # Ship heading North (0 rad), wind blowing East towards Starboard: velocity_ne = (0.0, 10.0)
    truth = make_truth(wind_ne=(0.0, 10.0), current_ne=(0.0, 0.0))
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.NONE,
    )
    loads = model.compute_loads(truth, nav)

    assert loads.wind.sway_n > 0.0  # Starboard force
    assert loads.wind.roll_nm < 0.0  # Roll moment opposes starboard force (negative torque)
    assert loads.total == loads.wind


# ---------------------------------------------------------------------------
# 3. Mirror Tests (Direction Sign Parity)
# ---------------------------------------------------------------------------


def test_mirror_starboard_port_wind(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify starboard beam wind (+90 deg) and port beam wind (-90 deg) mirror sway and roll signs."""
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    model = EnvironmentalLoadModel(vessel_params=standard_vessel_params, current_strategy=CurrentStrategy.NONE)

    # Starboard wind (blowing East: +ve ve)
    truth_stbd = make_truth(wind_ne=(0.0, 10.0))
    loads_stbd = model.compute_loads(truth_stbd, nav)

    # Port wind (blowing West: -ve ve)
    truth_port = make_truth(wind_ne=(0.0, -10.0))
    loads_port = model.compute_loads(truth_port, nav)

    # Sway force and roll moment must be equal and opposite
    assert math.isclose(loads_stbd.wind.sway_n, -loads_port.wind.sway_n, rel_tol=1e-6)
    assert math.isclose(loads_stbd.wind.roll_nm, -loads_port.wind.roll_nm, rel_tol=1e-6)


def test_mirror_starboard_port_current(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify starboard current (+90 deg) and port current (-90 deg) mirror sway and yaw signs."""
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
        enable_wind=False,
    )

    # Starboard current (+ve ve)
    truth_stbd = make_truth(current_ne=(0.0, 1.0))
    loads_stbd = model.compute_loads(truth_stbd, nav)

    # Port current (-ve ve)
    truth_port = make_truth(current_ne=(0.0, -1.0))
    loads_port = model.compute_loads(truth_port, nav)

    assert math.isclose(loads_stbd.current.sway_n, -loads_port.current.sway_n, rel_tol=1e-6)
    assert math.isclose(loads_stbd.current.yaw_nm, -loads_port.current.yaw_nm, rel_tol=1e-6)
    assert math.isclose(loads_stbd.current.roll_nm, -loads_port.current.roll_nm, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# 4. Isolation Tests (Wind-Only vs Current-Only)
# ---------------------------------------------------------------------------


def test_isolation_wind_only(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify that when current is inactive/zero, total load equals wind load exactly."""
    truth = make_truth(wind_ne=(10.0, 5.0), current_ne=(0.0, 0.0))
    nav = NavigationState(0.0, 0.0, math.pi / 4, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
    )
    loads = model.compute_loads(truth, nav)

    assert loads.current == VesselLoad.zero()
    assert loads.wind != VesselLoad.zero()
    assert loads.total == loads.wind

    # Also verify with enable_current=False under motion
    nav_moving = NavigationState(0.0, 0.0, math.pi / 4, 2.0, 0.5, 0.0)
    model_no_current = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        enable_current=False,
    )
    loads_no_current = model_no_current.compute_loads(truth, nav_moving)
    assert loads_no_current.current == VesselLoad.zero()
    assert loads_no_current.total == loads_no_current.wind


def test_isolation_current_only(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify that when wind is inactive/zero, total load equals current load exactly."""
    truth = make_truth(wind_ne=(0.0, 0.0), current_ne=(0.5, 0.5))
    nav = NavigationState(0.0, 0.0, math.pi / 4, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
    )
    loads = model.compute_loads(truth, nav)

    assert loads.wind == VesselLoad.zero()
    assert loads.current != VesselLoad.zero()
    assert loads.total == loads.current

    # Also verify with enable_wind=False under motion
    nav_moving = NavigationState(0.0, 0.0, math.pi / 4, 2.0, 0.5, 0.0)
    model_no_wind = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
        enable_wind=False,
    )
    loads_no_wind = model_no_wind.compute_loads(truth, nav_moving)
    assert loads_no_wind.wind == VesselLoad.zero()
    assert loads_no_wind.total == loads_no_wind.current


# ---------------------------------------------------------------------------
# 5. Explicit Summation Tests
# ---------------------------------------------------------------------------


def test_explicit_summation(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify wind and current loads are reported separately and sum explicitly (acceptance requirement)."""
    truth = make_truth(wind_ne=(12.0, 4.0), current_ne=(0.8, -0.3))
    nav = NavigationState(0.0, 0.0, 0.5, 2.0, 0.1, 0.01)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
    )
    loads = model.compute_loads(truth, nav)

    # Must have non-zero wind and current loads
    assert loads.wind != VesselLoad.zero()
    assert loads.current != VesselLoad.zero()

    # Exact component-wise sum
    assert math.isclose(loads.total.surge_n, loads.wind.surge_n + loads.current.surge_n, rel_tol=1e-9)
    assert math.isclose(loads.total.sway_n, loads.wind.sway_n + loads.current.sway_n, rel_tol=1e-9)
    assert math.isclose(loads.total.yaw_nm, loads.wind.yaw_nm + loads.current.yaw_nm, rel_tol=1e-9)
    assert math.isclose(loads.total.roll_nm, loads.wind.roll_nm + loads.current.roll_nm, rel_tol=1e-9)


def test_environmental_loads_rejects_inconsistent_total() -> None:
    """Verify EnvironmentalLoads dataclass rejects non-matching total load."""
    w = VesselLoad(100.0, 200.0, 300.0, 50.0)
    c = VesselLoad(10.0, 20.0, 30.0, 5.0)
    wrong_total = VesselLoad(999.0, 220.0, 330.0, 55.0)

    with pytest.raises(ValueError, match="total load .* does not match explicit sum"):
        EnvironmentalLoads(wind=w, current=c, total=wrong_total)


# ---------------------------------------------------------------------------
# 6. Current De-Duplication Contract Tests
# ---------------------------------------------------------------------------


def test_current_relative_damping_produces_zero_external_load(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Verify current_relative_damping strategy results in strictly zero external current load (spec L105)."""
    truth = make_truth(wind_ne=(0.0, 0.0), current_ne=(1.0, 1.0))
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.CURRENT_RELATIVE_DAMPING,
    )
    loads = model.compute_loads(truth, nav)

    assert loads.current == VesselLoad.zero()
    assert loads.total == VesselLoad.zero()


def test_configuration_rejects_both_current_strategies() -> None:
    """Verify configuration normalization strictly rejects duplicate current strategy."""
    raw_config = {
        "modules": {
            "plant": {"identity": "pass_through_plant"},
            "guidance": {"identity": "pass_through_guidance"},
            "controller": {"identity": "pass_through_controller"},
            "load_model": {
                "identity": "standard_environmental_load",
                "parameters": {
                    "current_relative_damping": True,
                    "external_current_load": True,
                },
            },
        }
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="mutually exclusive"):
        normalize_ship_modules(raw_config)


def test_configuration_rejects_duplicate_strategy_string() -> None:
    """Verify configuration normalization rejects invalid current_strategy value."""
    raw_config = {
        "modules": {
            "plant": {"identity": "pass_through_plant"},
            "guidance": {"identity": "pass_through_guidance"},
            "controller": {"identity": "pass_through_controller"},
            "load_model": {
                "identity": "standard_environmental_load",
                "parameters": {
                    "current_strategy": "both",
                },
            },
        }
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="mutually exclusive"):
        normalize_ship_modules(raw_config)


def test_configuration_rejects_cross_module_current_conflict() -> None:
    """Verify configuration normalization rejects plant current_relative_damping with load_model external_current_load."""
    raw_config = {
        "modules": {
            "plant": {
                "identity": "pass_through_plant",
                "parameters": {"current_relative_damping": True},
            },
            "guidance": {"identity": "pass_through_guidance"},
            "controller": {"identity": "pass_through_controller"},
            "load_model": {
                "identity": "standard_environmental_load",
                "parameters": {"current_strategy": "external_current_load"},
            },
        }
    }
    with pytest.raises(UnsupportedModuleCombinationError, match="cannot combine"):
        normalize_ship_modules(raw_config)


def test_runtime_rejection_of_conflicting_current_strategy() -> None:
    """Verify EnvironmentalLoadModel.from_params rejects conflicting current strategy at runtime."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        EnvironmentalLoadModel.from_params(
            {
                "current_relative_damping": True,
                "external_current_load": True,
            }
        )


# ---------------------------------------------------------------------------
# 7. Asset Absence Tests
# ---------------------------------------------------------------------------


def test_missing_wind_asset_fails() -> None:
    """Verify WindLoadModel raises AssetMissingError when wind asset is None."""
    wind = WindSample(velocity_ne=(10.0, 0.0))
    params = VesselEnvironmentalParameters(44.1, 8.0, 1.55, 50.0, 150.0)

    with pytest.raises(AssetMissingError, match="Wind coefficient asset is required"):
        WindLoadModel.calculate(
            wind=wind,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            params=params,
            asset=None,
        )


def test_missing_current_asset_with_external_load_fails() -> None:
    """Verify CurrentLoadModel raises AssetMissingError when current asset is None under EXTERNAL_CURRENT_LOAD."""
    current = CurrentSample(velocity_ne=(1.0, 0.0))
    params = VesselEnvironmentalParameters(44.1, 8.0, 1.55, 50.0, 150.0)

    with pytest.raises(AssetMissingError, match="Current asset is required"):
        CurrentLoadModel.calculate(
            current=current,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            params=params,
            strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
            asset=None,
        )


# ---------------------------------------------------------------------------
# 8. Asset Domain & Integrity Tests
# ---------------------------------------------------------------------------


def test_out_of_domain_wind_fails() -> None:
    """Verify WindLoadModel raises OutOfDomainError when apparent wind speed exceeds declared domain."""
    wind = WindSample(velocity_ne=(100.0, 0.0))  # Exceeds 60 m/s limit of DEFAULT_OCIMF_WIND_ASSET
    params = VesselEnvironmentalParameters(44.1, 8.0, 1.55, 50.0, 150.0)

    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        WindLoadModel.calculate(
            wind=wind,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            params=params,
            asset=DEFAULT_OCIMF_WIND_ASSET,
        )


def test_out_of_domain_current_fails() -> None:
    """Verify CurrentLoadModel raises OutOfDomainError when current speed exceeds declared domain."""
    current = CurrentSample(velocity_ne=(10.0, 0.0))  # Exceeds 5.0 m/s limit of default current asset
    params = VesselEnvironmentalParameters(44.1, 8.0, 1.55, 50.0, 150.0)

    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        CurrentLoadModel.calculate(
            current=current,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            params=params,
            strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
            asset=DEFAULT_INFERRED_CURRENT_ASSET,
        )


def test_tampered_asset_hash_fails_integrity() -> None:
    """Verify asset with tampered content hash fails integrity check and calculation."""
    # Create asset with incorrect sha256
    tampered_meta = AssetMetadata(
        asset_id="tampered_wind_v1",
        asset_type="wind_coeff_table",
        trust_level=AssetTrustLevel.MOCK,
        source_type="mock",
        sha256="0" * 64,  # Invalid hash
        license="MIT",
    )
    tampered_asset = WindCoeffTableAsset(
        metadata=tampered_meta,
        table=DEFAULT_OCIMF_WIND_ASSET.table,
    )
    assert not tampered_asset.verify_integrity()

    wind = WindSample(velocity_ne=(10.0, 0.0))
    params = VesselEnvironmentalParameters(44.1, 8.0, 1.55, 50.0, 150.0)
    with pytest.raises(AssetIntegrityError, match="Integrity check failed"):
        WindLoadModel.calculate(
            wind=wind,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            params=params,
            asset=tampered_asset,
        )


def test_current_asset_cmx_mutation_fails_integrity() -> None:
    """Verify that mutating only cmx in current table asset invalidates sha256 integrity."""
    orig = DEFAULT_TABLE_CURRENT_ASSET
    assert orig.verify_integrity()

    # Mutate ONLY cmx in the first entry
    mutated_entries = list(orig.table)
    first = mutated_entries[0]
    mutated_entries[0] = CurrentCoeffEntry(
        heading_deg=first.heading_deg,
        ccx=first.ccx,
        ccy=first.ccy,
        cmz=first.cmz,
        cmx=first.cmx + 0.05,
    )
    mutated_asset = CurrentCoeffTableAsset(metadata=orig.metadata, table=tuple(mutated_entries))
    assert not mutated_asset.verify_integrity()



# ---------------------------------------------------------------------------
# 9. Asset Trust & Validation Impossibility (TS-23, VR-10, ALT-25)
# ---------------------------------------------------------------------------


def test_mock_asset_cannot_become_validated() -> None:
    """Verify mock assets are structurally incapable of being marked VALIDATED_FOR_VESSEL."""
    with pytest.raises(ValueError, match="mock/inferred assets never become validated"):
        AssetMetadata(
            asset_id="fake_validated_mock",
            asset_type="wind_coeff_table",
            trust_level=AssetTrustLevel.VALIDATED_FOR_VESSEL,
            source_type="mock",
            sha256="a" * 64,
            license="MIT",
        )


def test_inferred_asset_cannot_become_validated() -> None:
    """Verify inferred assets are structurally incapable of being marked VALIDATED_FOR_VESSEL."""
    with pytest.raises(ValueError, match="mock/inferred assets never become validated"):
        AssetMetadata(
            asset_id="fake_validated_inferred",
            asset_type="current_coeff_table",
            trust_level=AssetTrustLevel.VALIDATED_FOR_VESSEL,
            source_type="inferred",
            sha256="b" * 64,
            license="MIT",
        )


def test_valid_calibrated_asset_creation() -> None:
    """Verify calibrated or validated asset can be created when source_type is legitimate."""
    meta = AssetMetadata(
        asset_id="tank_test_asset_v1",
        asset_type="current_coeff_table",
        trust_level=AssetTrustLevel.VALIDATED_FOR_VESSEL,
        source_type="tank_test",
        sha256="c" * 64,
        license="Proprietary",
    )
    assert meta.trust_level == AssetTrustLevel.VALIDATED_FOR_VESSEL
    assert meta.source_type == "tank_test"


@pytest.mark.parametrize("bad_angle", [float("nan"), float("inf"), float("-inf"), "45.0", True])
def test_asset_angle_normalization_rejects_nonfinite(bad_angle: Any) -> None:
    """Verify WindCoeffEntry, CurrentCoeffEntry, and InferredCurrentAsset reject nonfinite/invalid angles."""
    with pytest.raises((TypeError, ValueError)):
        WindCoeffEntry(angle_deg=bad_angle, cx=0.1, cy=0.2, cn=0.01)

    with pytest.raises((TypeError, ValueError)):
        CurrentCoeffEntry(heading_deg=bad_angle, ccx=0.1, ccy=0.2, cmz=0.01)

    with pytest.raises((TypeError, ValueError)):
        DEFAULT_OCIMF_WIND_ASSET.interpolate(bad_angle)

    with pytest.raises((TypeError, ValueError)):
        DEFAULT_TABLE_CURRENT_ASSET.interpolate(bad_angle)

    with pytest.raises((TypeError, ValueError)):
        DEFAULT_INFERRED_CURRENT_ASSET.evaluate(bad_angle)



# ---------------------------------------------------------------------------
# 10. Benchmark Parity Tests (with env_model_baseline_v1.json)
# ---------------------------------------------------------------------------


def test_benchmark_wind_beam_10ms_parity() -> None:
    """Verify exact numerical parity with env_model_baseline_v1.json wind_beam_10ms_v1 case."""
    # From env_model_baseline_v1.json:
    # wind_speed_mps: 10.0, wind_direction_deg_to: 90.0, heading_deg: 0.0
    # frontal_area: 450.0, lateral_area: 1500.0, lpp: 270.0, z_center: 15.0, air_rho: 1.225
    # Expected: force_x = 5512.5, force_y = 73500.0, torque_x = -1102500.0, torque_z = 0.0
    wind = WindSample(velocity_ne=(0.0, 10.0))  # 90 deg to-direction = East
    params = VesselEnvironmentalParameters(
        length_between_perpendiculars_m=270.0,
        beam_m=35.0,
        draft_m=10.0,
        wind_frontal_area_m2=450.0,
        wind_lateral_area_m2=1500.0,
        wind_z_center_m=15.0,
        air_density_kg_m3=1.225,
    )

    load = WindLoadModel.calculate(
        wind=wind,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        params=params,
        asset=DEFAULT_OCIMF_WIND_ASSET,
    )

    assert math.isclose(load.surge_n, 5512.5, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load.sway_n, 73500.0, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load.roll_nm, -1102500.0, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load.yaw_nm, 0.0, rel_tol=1e-9, abs_tol=1e-6)


def test_benchmark_current_beam_inferred_1p2ms_parity() -> None:
    """Verify exact numerical parity with env_model_baseline_v1.json current_beam_inferred_1p2ms_v1 case."""
    # From env_model_baseline_v1.json:
    # apparent_current_speed_mps: 1.2, apparent_current_direction_deg: 90.0
    # draft: 6.0, depth: 50.0, lpp: 80.0, beam: 15.0, kg: 4.0, water_rho: 1025.0
    # Expected: force_x ~ 0.0, force_y = 247968.0, torque_x = 495936.0, torque_z = 283392.0
    current = CurrentSample(velocity_ne=(0.0, 1.2))  # 90 deg to-direction
    params = VesselEnvironmentalParameters(
        length_between_perpendiculars_m=80.0,
        beam_m=15.0,
        draft_m=6.0,
        wind_frontal_area_m2=100.0,
        wind_lateral_area_m2=300.0,
        water_depth_m=50.0,
        kg_m=4.0,
        water_density_kg_m3=1025.0,
    )

    load = CurrentLoadModel.calculate(
        current=current,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        params=params,
        strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
        asset=DEFAULT_INFERRED_CURRENT_ASSET,
    )

    assert math.isclose(load.surge_n, 0.0, abs_tol=1e-6)
    assert math.isclose(load.sway_n, 247968.0, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load.roll_nm, 495936.0, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load.yaw_nm, 283392.0, rel_tol=1e-9, abs_tol=1e-6)


def test_world_ne_to_body_velocity_transformations() -> None:
    """Verify TS-01/TS-03/TS-07 NE world to body velocity conversion."""
    # North wind (blowing North: vn=10, ve=0), heading North (0 rad) -> vx_body=10, vy_body=0
    vx, vy = world_ne_to_body_velocity((10.0, 0.0), 0.0)
    assert math.isclose(vx, 10.0)
    assert math.isclose(vy, 0.0)

    # North wind, heading East (pi/2 rad) -> vx_body=0, vy_body=-10 (blowing toward Port / -y)
    vx, vy = world_ne_to_body_velocity((10.0, 0.0), math.pi / 2)
    assert math.isclose(vx, 0.0, abs_tol=1e-9)
    assert math.isclose(vy, -10.0, abs_tol=1e-9)

    # East wind (vn=0, ve=10), heading North (0 rad) -> vx_body=0, vy_body=10 (blowing toward Starboard / +y)
    vx, vy = world_ne_to_body_velocity((0.0, 10.0), 0.0)
    assert math.isclose(vx, 0.0)
    assert math.isclose(vy, 10.0)


@pytest.mark.parametrize("bad_val", ["yes", "0", 0, 1, None])
def test_environmental_load_model_rejects_non_bool_flags(
    standard_vessel_params: VesselEnvironmentalParameters, bad_val: Any
) -> None:
    """Verify EnvironmentalLoadModel and from_params reject non-exact bool flags."""
    with pytest.raises(TypeError, match="must be an exact bool"):
        EnvironmentalLoadModel(standard_vessel_params, enable_wind=bad_val)

    with pytest.raises(TypeError, match="must be an exact bool"):
        EnvironmentalLoadModel(standard_vessel_params, enable_current=bad_val)

    with pytest.raises(TypeError, match="must be an exact bool"):
        EnvironmentalLoadModel.from_params({"enable_wind": bad_val})

    with pytest.raises(TypeError, match="must be an exact bool"):
        EnvironmentalLoadModel.from_params({"enable_current": bad_val})

    with pytest.raises(TypeError, match="must be an exact bool"):
        EnvironmentalLoadModel.from_params({"current_relative_damping": bad_val})

    with pytest.raises(TypeError, match="must be an exact bool"):
        EnvironmentalLoadModel.from_params({"external_current_load": bad_val})


@pytest.mark.parametrize("bad_num", ["44.1", float("nan"), float("inf"), float("-inf")])
def test_vessel_parameters_reject_invalid_numerics(bad_num: Any) -> None:
    """Verify VesselEnvironmentalParameters rejects string numbers and non-finite values."""
    with pytest.raises((TypeError, ValueError)):
        VesselEnvironmentalParameters(
            length_between_perpendiculars_m=bad_num,
            beam_m=8.0,
            draft_m=1.55,
            wind_frontal_area_m2=50.0,
            wind_lateral_area_m2=150.0,
        )


def test_compute_loads_with_plant_state(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify compute_loads accepts PlantState truth."""
    truth = make_truth(wind_ne=(10.0, 0.0))
    # PlantState values: [N, E, psi, u, v, r]
    plant = PlantState([100.0, 200.0, 0.0, 5.0, 0.0, 0.0], frozenset({"PLANAR_3DOF"}))
    model = EnvironmentalLoadModel(vessel_params=standard_vessel_params)
    loads = model.compute_loads(truth, plant)
    assert loads.wind != VesselLoad.zero()


def test_tabular_current_asset_calculation(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify tabular current coefficient asset calculation."""
    current = CurrentSample(velocity_ne=(0.0, 1.0))
    load = CurrentLoadModel.calculate(
        current=current,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        params=standard_vessel_params,
        strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
        asset=DEFAULT_TABLE_CURRENT_ASSET,
    )
    assert load.sway_n > 0.0
    assert load.surge_n == 0.0 or math.isclose(load.surge_n, 0.0, abs_tol=1e-6)


def test_applicability_domain_bounds_checking() -> None:
    """Verify ApplicabilityDomain checking logic."""
    domain = ApplicabilityDomain(
        heading_range_deg=(0.0, 180.0),
        speed_range_mps=(0.0, 25.0),
        draft_range_m=(1.0, 10.0),
        custom_bounds={"froude": (0.0, 0.5)},
    )
    assert domain.contains(heading_deg=90.0, speed_mps=15.0, draft_m=5.0, froude=0.3)
    assert not domain.contains(heading_deg=270.0)
    assert not domain.contains(speed_mps=30.0)
    assert not domain.contains(draft_m=0.5)
    assert not domain.contains(froude=0.8)


# ---------------------------------------------------------------------------
# 11. Facade & Stack Integration Tests
# ---------------------------------------------------------------------------


def test_stack_integration_with_load_model() -> None:
    """Verify ModularShipStack executes with load_model, populates StackOutput, and supports snapshot/restore."""
    config = normalize_ship_modules(
        {
            "modules": {
                "plant": {"identity": "pass_through_plant"},
                "guidance": {"identity": "pass_through_guidance"},
                "controller": {"identity": "pass_through_controller"},
                "environment": {
                    "identity": "analytic_environment_field",
                    "parameters": {
                        "wind_velocity_ne": [10.0, 0.0],
                        "current_velocity_ne": [0.0, 1.0],
                    },
                },
                "load_model": {
                    "identity": "standard_environmental_load",
                    "parameters": {
                        "current_strategy": "external_current_load",
                    },
                },
            }
        }
    )

    stack = ModularShipStack.from_config(config, dt_s=0.1)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=42)

    step0 = stack.step(CommandInput.none(0), dt_s=0.1)
    assert step0.failure is None
    assert step0.environmental_loads is not None
    assert step0.environmental_loads.wind != VesselLoad.zero()
    assert step0.environmental_loads.current != VesselLoad.zero()
    assert step0.environmental_loads.total != VesselLoad.zero()

    # Snapshot and restore repeatability
    snap = stack.snapshot()
    step1 = stack.step(CommandInput.none(1), dt_s=0.1)

    stack.restore(snap)
    step1_replay = stack.step(CommandInput.none(1), dt_s=0.1)

    assert step1.environmental_loads == step1_replay.environmental_loads
    assert step1.plant == step1_replay.plant
