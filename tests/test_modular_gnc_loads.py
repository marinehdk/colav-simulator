"""Comprehensive tests for vessel environmental loads, asset validation, and current de-duplication (Issue #50)."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np
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
    DirectReference,
    EnvironmentalLoads,
    EnvironmentTruth,
    FailureCode,
    MeanDriftSourceSample,
    NavigationState,
    OutOfDomainError,
    PlantState,
    VesselLoad,
    WaveComponent,
    WaveFieldSample,
    WaveLoadMode,
    WindSample,
)
from colav_simulator.modular_gnc.load_model import (
    DEFAULT_INFERRED_CURRENT_ASSET,
    DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    DEFAULT_OCIMF_WIND_ASSET,
    DEFAULT_TABLE_CURRENT_ASSET,
    CurrentCoeffEntry,
    CurrentCoeffTableAsset,
    CurrentLoadModel,
    EnvironmentalLoadModel,
    FirstOrderWaveLoadModel,
    InferredWaveResponseAsset,
    MeanDriftLoadModel,
    VesselEnvironmentalParameters,
    WaveDriftEntry,
    WaveDriftTableAsset,
    WaveRaoEntry,
    WaveRaoTableAsset,
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


def test_table_asset_rejects_non_increasing_headings() -> None:
    """Verify table assets reject unordered or duplicate heading/angle entries."""
    meta = DEFAULT_TABLE_CURRENT_ASSET.metadata

    # Duplicate angles
    with pytest.raises(ValueError, match="strictly increasing"):
        CurrentCoeffTableAsset(
            metadata=meta,
            table=(
                CurrentCoeffEntry(0.0, 0.1, 0.0, 0.0),
                CurrentCoeffEntry(0.0, 0.1, 0.0, 0.0),
            ),
        )

    # Decreasing angles
    with pytest.raises(ValueError, match="strictly increasing"):
        CurrentCoeffTableAsset(
            metadata=meta,
            table=(
                CurrentCoeffEntry(90.0, 0.1, 0.0, 0.0),
                CurrentCoeffEntry(45.0, 0.1, 0.0, 0.0),
            ),
        )

    # Wind table duplicate angles
    with pytest.raises(ValueError, match="strictly increasing"):
        WindCoeffTableAsset(
            metadata=DEFAULT_OCIMF_WIND_ASSET.metadata,
            table=(
                WindCoeffEntry(50.0, 0.1, 0.0, 0.0),
                WindCoeffEntry(50.0, 0.2, 0.0, 0.0),
            ),
        )


def test_current_table_interpolation_fallback_ccy() -> None:
    """Verify CurrentCoeffTableAsset.interpolate correctly accesses ccy on fallback path."""
    meta = DEFAULT_TABLE_CURRENT_ASSET.metadata
    # Custom table starting at 30 deg; querying at 10 deg triggers the fallback path
    table = (
        CurrentCoeffEntry(30.0, 0.15, 0.25, 0.05, 0.01),
        CurrentCoeffEntry(180.0, -0.15, 0.0, 0.0, 0.0),
    )
    asset = CurrentCoeffTableAsset(metadata=meta, table=table)
    ccx, ccy, cmz, cmx = asset.interpolate(10.0)
    assert math.isclose(ccx, 0.15)
    assert math.isclose(ccy, 0.25)
    assert math.isclose(cmz, 0.05)
    assert math.isclose(cmx, 0.01)


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


def test_contracts_nested_deep_freeze_and_aliasing() -> None:
    """Verify deep-freeze on AssetMetadata and EnvironmentalLoads prevents nested mutation and aliasing."""
    raw_prov = {"author": {"name": "Alice", "team": "GNC"}, "tags": ["baseline", "v1"]}
    raw_unc = {"bounds": {"lower": 0.01, "upper": 0.05}, "list": [1, 2]}
    meta = AssetMetadata(
        asset_id="tank_test_asset_v2",
        asset_type="current_coeff_table",
        trust_level=AssetTrustLevel.CALIBRATED,
        source_type="tank_test",
        sha256="d" * 64,
        license="Proprietary",
        provenance=raw_prov,
        uncertainty=raw_unc,
    )

    # Rejection of nested mutation
    with pytest.raises(TypeError):
        meta.provenance["author"]["name"] = "Bob"
    with pytest.raises(TypeError):
        meta.uncertainty["bounds"]["lower"] = 0.02
    assert isinstance(meta.provenance["tags"], tuple)

    # Aliasing isolation
    raw_prov["author"]["name"] = "Charlie"
    raw_prov["tags"].append("v2")
    assert meta.provenance["author"]["name"] == "Alice"
    assert meta.provenance["tags"] == ("baseline", "v1")

    # EnvironmentalLoads details deep-freeze
    raw_details = {"status": {"active": True}, "sub_list": [10, 20]}
    loads = EnvironmentalLoads.from_components(details=raw_details)
    with pytest.raises(TypeError):
        loads.details["status"]["active"] = False
    assert isinstance(loads.details["sub_list"], tuple)

    raw_details["status"]["active"] = False
    assert loads.details["status"]["active"] is True


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
# 10. Benchmark Parity Tests (with frozen external baseline)
# ---------------------------------------------------------------------------

FROZEN_SOURCE_TREE = "L4-5_source_only_20260824_v2"
FROZEN_BENCHMARK_RELATIVE_PATH = "src/environment/env_engines/data/benchmarks/env_model_baseline_v1.json"
FROZEN_BENCHMARK_ID = "env_model_baseline_v1"
FROZEN_BENCHMARK_SCHEMA_VERSION = "env_model_baseline.v1"
FROZEN_BENCHMARK_SHA256 = "66672967bd34a46d399c66e159c53775ac0f9de4df4983270289e118f6a148d3"


def test_benchmark_wind_beam_10ms_parity() -> None:
    """Verify exact numerical parity with frozen baseline case 'wind_beam_10ms_v1'.

    Source: L4-5_source_only_20260824_v2 / env_model_baseline_v1.json
    SHA-256: 66672967bd34a46d399c66e159c53775ac0f9de4df4983270289e118f6a148d3
    Case ID: wind_beam_10ms_v1 (model: wind, asset: wind_ocimf_embedded_mock_v1)
    Inputs: wind_speed=10.0 m/s, wind_dir=90.0 deg (to East), heading=0.0 deg,
            frontal_area=450.0 m2, lateral_area=1500.0 m2, lpp=270.0 m,
            z_center=15.0 m, air_rho=1.225 kg/m3.
    Expected: force_x=5512.5 N, force_y=73500.0 N, torque_x=-1102500.0 Nm, torque_z=0.0 Nm.
    """
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
    """Verify exact numerical parity with frozen baseline case 'current_beam_inferred_1p2ms_v1'.

    Source: L4-5_source_only_20260824_v2 / env_model_baseline_v1.json
    SHA-256: 66672967bd34a46d399c66e159c53775ac0f9de4df4983270289e118f6a148d3
    Case ID: current_beam_inferred_1p2ms_v1 (model: current, asset: current_coeffs_mock_v1)
    Inputs: apparent_speed=1.2 m/s, apparent_dir=90.0 deg, draft=6.0 m,
            depth=50.0 m, lpp=80.0 m, beam=15.0 m, kg=4.0 m, water_rho=1025.0 kg/m3.
    Expected: force_x ~ 0.0 N, force_y=247968.0 N, torque_x=495936.0 Nm, torque_z=283392.0 Nm.
    """
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


def test_stack_integration_with_wave_load_mode() -> None:
    """Verify ModularShipStack executes with wave_mode='both' and computes wave loads in StackOutput."""
    config = normalize_ship_modules(
        {
            "modules": {
                "plant": {"identity": "pass_through_plant"},
                "guidance": {"identity": "pass_through_guidance"},
                "controller": {"identity": "pass_through_controller"},
                "environment": {
                    "identity": "analytic_environment_field",
                    "parameters": {
                        "wave_significant_height_m": 2.5,
                        "wave_peak_period_s": 8.0,
                        "wave_num_components": 16,
                    },
                },
                "load_model": {
                    "identity": "standard_environmental_load",
                    "parameters": {
                        "wave_mode": "both",
                    },
                },
            }
        }
    )

    stack = ModularShipStack.from_config(config, episode_seed=123, dt_s=0.1)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=123)

    out = stack.step(CommandInput.none(0), dt_s=0.1)
    assert out.failure is None
    assert out.environmental_loads is not None
    assert out.environmental_loads.wave_first_order != VesselLoad.zero()
    assert out.environmental_loads.wave_mean_drift != VesselLoad.zero()
    assert out.environmental_loads.details["wave_mode"] == "both"
    assert out.environmental_loads.details["first_order_components_count"] == 16
    assert out.environmental_loads.details["mean_drift_components_count"] == 16


def test_stack_out_of_domain_maps_to_typed_failure_code() -> None:
    """Verify ModularShipStack maps OutOfDomainError to FailureCode.OUT_OF_DOMAIN."""
    config = normalize_ship_modules(
        {
            "modules": {
                "plant": {"identity": "pass_through_plant"},
                "guidance": {"identity": "pass_through_guidance"},
                "controller": {"identity": "pass_through_controller"},
                "environment": {
                    "identity": "analytic_environment_field",
                    "parameters": {
                        "wind_velocity_ne": [-50.0, 0.0],  # Within 60 m/s limit at surge=0
                    },
                },
                "load_model": {
                    "identity": "standard_environmental_load",
                },
            }
        }
    )

    stack = ModularShipStack.from_config(config, dt_s=0.1)
    nav0 = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stack.reset(nav0, seed=42)

    # Step 0: Command ship to surge forward at 20 m/s into the -50 m/s wind
    ref_vals = np.zeros(9)
    ref_vals[3] = 20.0
    cmd0 = CommandInput.direct(0, DirectReference(values=ref_vals, latched_tick=0))
    step0 = stack.step(cmd0, dt_s=0.1)
    assert step0.failure is None

    # Step 1: Apparent wind speed is 70 m/s, exceeding 60 m/s asset domain
    step1 = stack.step(CommandInput.none(1), dt_s=0.1)
    assert step1.failure is not None
    assert step1.failure.code == FailureCode.OUT_OF_DOMAIN
    assert step1.failure.phase == "environment"
    assert step1.failure.details["exception_type"] == "OutOfDomainError"


# ---------------------------------------------------------------------------
# 12. First-Order Wave Load Model Tests (Issue #51, VR-09..11, TS-09/13/14/17/23)
# ---------------------------------------------------------------------------


def test_first_order_wave_zero_amplitude(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify zero wave amplitude produces strictly zero first-order wave loads."""
    empty_wave = WaveFieldSample(significant_height_m=0.0, peak_period_s=8.0, direction_to_rad=0.0, components=())
    load_empty = FirstOrderWaveLoadModel.calculate(
        wave=empty_wave,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=1.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    assert load_empty == VesselLoad.zero()

    comp_zero = WaveComponent(amplitude_m=0.0, omega_radps=0.8, phase_rad=0.0, direction_to_rad=0.0)
    wave_zero = WaveFieldSample(significant_height_m=0.0, peak_period_s=8.0, direction_to_rad=0.0, components=(comp_zero,))
    load_zero = FirstOrderWaveLoadModel.calculate(
        wave=wave_zero,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=2.5,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    assert load_zero == VesselLoad.zero()


def test_first_order_wave_single_harmonic_analytic(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify single regular harmonic wave response oscillates at encounter frequency."""
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=9.0, direction_to_rad=0.0, components=(comp,))

    # At stationary (u=0, v=0) and following sea (heading=0), omega_e = omega = 0.7 rad/s
    t0 = 0.0
    load_t0 = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=t0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    # Quarter-period: t1 = pi / (2 * 0.7) -> cos(0.7 * t1) = 0
    t1 = math.pi / (2.0 * 0.7)
    load_t1 = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=t1,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    # Full-period: t2 = 2 * pi / 0.7 -> cos(0.7 * t2) = 1
    t2 = 2.0 * math.pi / 0.7
    load_t2 = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=t2,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )

    # Surge force should be maximum at t0, zero at t1, and maximum at t2
    assert load_t0.surge_n > 0.0
    assert math.isclose(load_t1.surge_n, 0.0, abs_tol=1e-4)
    assert math.isclose(load_t0.surge_n, load_t2.surge_n, rel_tol=1e-6)


def test_first_order_wave_multiple_components_superposition(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Verify multiple wave components sum linearly (harmonic superposition principle)."""
    comp1 = WaveComponent(amplitude_m=0.8, omega_radps=0.5, phase_rad=0.2, direction_to_rad=0.1)
    comp2 = WaveComponent(amplitude_m=1.2, omega_radps=0.9, phase_rad=0.8, direction_to_rad=0.3)

    wave1 = WaveFieldSample(significant_height_m=1.6, peak_period_s=12.0, direction_to_rad=0.1, components=(comp1,))
    wave2 = WaveFieldSample(significant_height_m=2.4, peak_period_s=7.0, direction_to_rad=0.3, components=(comp2,))
    wave_both = WaveFieldSample(
        significant_height_m=2.88, peak_period_s=7.0, direction_to_rad=0.2, components=(comp1, comp2)
    )

    t = 4.25
    load1 = FirstOrderWaveLoadModel.calculate(
        wave=wave1,
        heading_rad=0.2,
        surge_mps=3.0,
        sway_mps=0.5,
        stage_time_s=t,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    load2 = FirstOrderWaveLoadModel.calculate(
        wave=wave2,
        heading_rad=0.2,
        surge_mps=3.0,
        sway_mps=0.5,
        stage_time_s=t,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    load_both = FirstOrderWaveLoadModel.calculate(
        wave=wave_both,
        heading_rad=0.2,
        surge_mps=3.0,
        sway_mps=0.5,
        stage_time_s=t,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )

    expected_sum = load1 + load2
    assert math.isclose(load_both.surge_n, expected_sum.surge_n, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load_both.sway_n, expected_sum.sway_n, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load_both.yaw_nm, expected_sum.yaw_nm, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(load_both.roll_nm, expected_sum.roll_nm, rel_tol=1e-9, abs_tol=1e-6)


def test_first_order_wave_pure_stage_time_forcing(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify stage-time forcing is a pure function with no side effects or discrete state advance."""
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.6, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=10.0, direction_to_rad=0.0, components=(comp,))

    # Repeated calls with identical inputs return bit-identical outputs
    res1 = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.1,
        surge_mps=2.0,
        sway_mps=0.0,
        stage_time_s=3.7,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    res2 = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.1,
        surge_mps=2.0,
        sway_mps=0.0,
        stage_time_s=3.7,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    assert res1 == res2


def test_first_order_wave_encounter_frequency_doppler(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify encounter frequency Doppler shift: head seas have higher encounter frequency than following seas."""
    omega = 0.8
    comp_north = WaveComponent(amplitude_m=1.0, omega_radps=omega, phase_rad=0.0, direction_to_rad=0.0)  # Wave travels North
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.0, components=(comp_north,))

    # Ship heading South (pi) -> head sea (heading into wave)
    # omega_e_head = omega - k * (u * cos(0 - pi)) = omega + k * u > omega
    # Ship heading North (0) -> following sea (heading with wave)
    # omega_e_following = omega - k * (u * cos(0 - 0)) = omega - k * u < omega
    dt = 0.05
    # Measure rate of change of phase: d/dt(cos(omega_e * t)) at t=0 is 0, but curvature d2/dt2 is -omega_e^2
    l_head_0 = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=math.pi,
        surge_mps=5.0,
        sway_mps=0.0,
        stage_time_s=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    l_head_dt = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=math.pi,
        surge_mps=5.0,
        sway_mps=0.0,
        stage_time_s=dt,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    diff_head = abs(l_head_dt.surge_n - l_head_0.surge_n)

    l_foll_0 = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.0,
        surge_mps=5.0,
        sway_mps=0.0,
        stage_time_s=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    l_foll_dt = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.0,
        surge_mps=5.0,
        sway_mps=0.0,
        stage_time_s=dt,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    diff_foll = abs(l_foll_dt.surge_n - l_foll_0.surge_n)

    # For small dt, 1 - cos(omega_e * dt) ~ 0.5 * omega_e^2 * dt^2.
    # Since omega_e_head > omega_e_following, diff_head > diff_foll!
    assert diff_head > diff_foll


def test_first_order_wave_mirror_symmetry_and_antisymmetry(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Verify left/right mirror symmetry: surge symmetric, sway/roll/yaw anti-symmetric."""
    # Starboard beam sea: gamma = pi/2; Port beam sea: gamma = -pi/2
    comp_starboard = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=math.pi / 2.0)
    comp_port = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=3.0 * math.pi / 2.0)

    wave_stbd = WaveFieldSample(
        significant_height_m=2.0, peak_period_s=9.0, direction_to_rad=math.pi / 2.0, components=(comp_starboard,)
    )
    wave_port = WaveFieldSample(
        significant_height_m=2.0, peak_period_s=9.0, direction_to_rad=3.0 * math.pi / 2.0, components=(comp_port,)
    )

    t = 1.5
    load_stbd = FirstOrderWaveLoadModel.calculate(
        wave=wave_stbd,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=t,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    load_port = FirstOrderWaveLoadModel.calculate(
        wave=wave_port,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=t,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )

    # Surge is symmetric: Fx(gamma) == Fx(-gamma)
    assert math.isclose(load_stbd.surge_n, load_port.surge_n, abs_tol=1e-6)
    # Sway is anti-symmetric: Fy(gamma) == -Fy(-gamma)
    assert math.isclose(load_stbd.sway_n, -load_port.sway_n, rel_tol=1e-9, abs_tol=1e-6)
    # Roll is anti-symmetric: Mx(gamma) == -Mx(-gamma)
    assert math.isclose(load_stbd.roll_nm, -load_port.roll_nm, rel_tol=1e-9, abs_tol=1e-6)
    # Yaw is anti-symmetric: Mz(gamma) == -Mz(-gamma)
    assert math.isclose(load_stbd.yaw_nm, -load_port.yaw_nm, rel_tol=1e-9, abs_tol=1e-6)


def test_first_order_wave_tabular_rao_asset(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify WaveRaoTableAsset creation, integrity, and tabular interpolation."""
    entries = (
        WaveRaoEntry(0.5, 0.0, 1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        WaveRaoEntry(1.0, 0.0, 2000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        WaveRaoEntry(0.5, 90.0, 0.0, 0.0, 5000.0, 0.1, 10000.0, 0.2, 20000.0, 0.3),
        WaveRaoEntry(1.0, 90.0, 0.0, 0.0, 8000.0, 0.1, 15000.0, 0.2, 30000.0, 0.3),
    )
    raw_rows = [
        (
            e.omega_radps,
            e.heading_deg,
            e.surge_amp_n_per_m,
            e.surge_phase_rad,
            e.sway_amp_n_per_m,
            e.sway_phase_rad,
            e.roll_amp_nm_per_m,
            e.roll_phase_rad,
            e.yaw_amp_nm_per_m,
            e.yaw_phase_rad,
        )
        for e in entries
    ]
    payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
    sha = hashlib.sha256(payload).hexdigest()

    meta = AssetMetadata(
        asset_id="rao_table_mock_v1",
        asset_type="wave_rao_table",
        trust_level=AssetTrustLevel.MOCK,
        source_type="mock",
        sha256=sha,
        license="MIT",
        applicability_domain=ApplicabilityDomain(
            heading_range_deg=(0.0, 360.0),
            speed_range_mps=(0.0, 20.0),
            custom_bounds={"omega_radps": (0.4, 1.2)},
        ),
    )
    asset = WaveRaoTableAsset(metadata=meta, table=entries)
    assert asset.verify_integrity()

    comp = WaveComponent(amplitude_m=2.0, omega_radps=0.5, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=4.0, peak_period_s=12.0, direction_to_rad=0.0, components=(comp,))

    load = FirstOrderWaveLoadModel.calculate(
        wave=wave,
        heading_rad=0.0,
        surge_mps=0.0,
        sway_mps=0.0,
        stage_time_s=0.0,
        params=standard_vessel_params,
        asset=asset,
    )
    # amp = 2.0, surge_amp = 1000.0 -> Fx = 2000.0 N at t=0
    assert math.isclose(load.surge_n, 2000.0, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# 13. Second-Order Wave Mean-Drift Load Model Tests (Issue #51, VR-09..11)
# ---------------------------------------------------------------------------


def test_mean_drift_wave_zero_amplitude(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify zero wave produces strictly zero second-order mean-drift load."""
    drift_sample_empty = MeanDriftSourceSample(components=())
    load_empty = MeanDriftLoadModel.calculate(
        wave=drift_sample_empty,
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    assert load_empty == VesselLoad.zero()

    comp_zero = WaveComponent(amplitude_m=0.0, omega_radps=0.8, phase_rad=0.0, direction_to_rad=0.0)
    drift_sample_zero = MeanDriftSourceSample(components=(comp_zero,))
    load_zero = MeanDriftLoadModel.calculate(
        wave=drift_sample_zero,
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    assert load_zero == VesselLoad.zero()


def test_mean_drift_wave_energy_quadratic_scaling(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify mean drift force scales quadratically with wave amplitude (A^2 energy dependence)."""
    comp1 = WaveComponent(amplitude_m=1.0, omega_radps=0.8, phase_rad=0.0, direction_to_rad=math.pi / 4.0)
    comp2 = WaveComponent(amplitude_m=2.0, omega_radps=0.8, phase_rad=0.0, direction_to_rad=math.pi / 4.0)

    load1 = MeanDriftLoadModel.calculate(
        wave=MeanDriftSourceSample(components=(comp1,)),
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    load2 = MeanDriftLoadModel.calculate(
        wave=MeanDriftSourceSample(components=(comp2,)),
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )

    # Doubling amplitude (1.0 -> 2.0) must quadruple force (4x)
    assert math.isclose(load2.surge_n, 4.0 * load1.surge_n, rel_tol=1e-9)
    assert math.isclose(load2.sway_n, 4.0 * load1.sway_n, rel_tol=1e-9)
    assert math.isclose(load2.yaw_nm, 4.0 * load1.yaw_nm, rel_tol=1e-9)
    assert math.isclose(load2.roll_nm, 4.0 * load1.roll_nm, rel_tol=1e-9)


def test_mean_drift_wave_time_mean_stability(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify second-order mean drift load is time-mean steady (invariant under stage time)."""
    comp = WaveComponent(amplitude_m=1.5, omega_radps=0.7, phase_rad=0.0, direction_to_rad=math.pi / 3.0)
    drift_sample = MeanDriftSourceSample(components=(comp,))

    load_a = MeanDriftLoadModel.calculate(
        wave=drift_sample,
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    load_b = MeanDriftLoadModel.calculate(
        wave=drift_sample,
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    assert load_a == load_b


def test_mean_drift_wave_mirror_symmetry_and_antisymmetry(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Verify mean drift mirror symmetry: surge symmetric, sway/roll/yaw anti-symmetric."""
    comp_stbd = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=math.pi / 3.0)
    comp_port = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=5.0 * math.pi / 3.0)

    load_stbd = MeanDriftLoadModel.calculate(
        wave=MeanDriftSourceSample(components=(comp_stbd,)),
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    load_port = MeanDriftLoadModel.calculate(
        wave=MeanDriftSourceSample(components=(comp_port,)),
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )

    assert math.isclose(load_stbd.surge_n, load_port.surge_n, rel_tol=1e-9)
    assert math.isclose(load_stbd.sway_n, -load_port.sway_n, rel_tol=1e-9)
    assert math.isclose(load_stbd.yaw_nm, -load_port.yaw_nm, rel_tol=1e-9)
    assert math.isclose(load_stbd.roll_nm, -load_port.roll_nm, rel_tol=1e-9)


def test_mean_drift_wave_tabular_asset(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify WaveDriftTableAsset creation, integrity, and interpolation."""
    entries = (
        WaveDriftEntry(0.5, 0.0, 500.0, 0.0, 0.0, 0.0),
        WaveDriftEntry(1.0, 0.0, 1000.0, 0.0, 0.0, 0.0),
        WaveDriftEntry(0.5, 90.0, 0.0, 2000.0, 5000.0, 1000.0),
        WaveDriftEntry(1.0, 90.0, 0.0, 4000.0, 10000.0, 2000.0),
    )
    raw_rows = [
        (e.omega_radps, e.heading_deg, e.c_dx_n_per_m2, e.c_dy_n_per_m2, e.c_dn_nm_per_m2, e.c_dk_nm_per_m2) for e in entries
    ]
    payload = json.dumps(raw_rows, separators=(",", ":")).encode("utf-8")
    sha = hashlib.sha256(payload).hexdigest()

    meta = AssetMetadata(
        asset_id="drift_table_mock_v1",
        asset_type="wave_drift_table",
        trust_level=AssetTrustLevel.MOCK,
        source_type="mock",
        sha256=sha,
        license="MIT",
        applicability_domain=ApplicabilityDomain(heading_range_deg=(0.0, 360.0), custom_bounds={"omega_radps": (0.4, 1.2)}),
    )
    asset = WaveDriftTableAsset(metadata=meta, table=entries)
    assert asset.verify_integrity()

    comp = WaveComponent(amplitude_m=2.0, omega_radps=0.5, phase_rad=0.0, direction_to_rad=0.0)
    load = MeanDriftLoadModel.calculate(
        wave=MeanDriftSourceSample(components=(comp,)),
        heading_rad=0.0,
        params=standard_vessel_params,
        asset=asset,
    )
    # A^2 = 4.0, c_dx = 500.0 -> Fx = 2000.0 N
    assert math.isclose(load.surge_n, 2000.0, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# 14. Strict Asset Validation, Domains & Error Handling (TS-17, TS-23, VR-10)
# ---------------------------------------------------------------------------


def test_wave_asset_missing_error(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify missing wave asset raises explicit AssetMissingError; no silent fallback."""
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.0, components=(comp,))

    with pytest.raises(AssetMissingError, match="Wave response asset is required"):
        FirstOrderWaveLoadModel.calculate(
            wave=wave,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            stage_time_s=0.0,
            params=standard_vessel_params,
            asset=None,
        )

    with pytest.raises(AssetMissingError, match="Wave drift asset is required"):
        MeanDriftLoadModel.calculate(
            wave=MeanDriftSourceSample(components=(comp,)),
            heading_rad=0.0,
            params=standard_vessel_params,
            asset=None,
        )


def test_wave_asset_integrity_tampering_rejected(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify tampered wave asset hash raises AssetIntegrityError."""
    tampered_meta = AssetMetadata(
        asset_id="tampered_wave_asset",
        asset_type="wave_response_inferred",
        trust_level=AssetTrustLevel.INFERRED,
        source_type="inferred",
        sha256="0" * 64,
        license="MIT",
    )
    tampered_asset = InferredWaveResponseAsset(metadata=tampered_meta)
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.0, components=(comp,))

    with pytest.raises(AssetIntegrityError, match="Integrity check failed"):
        FirstOrderWaveLoadModel.calculate(
            wave=wave,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            stage_time_s=0.0,
            params=standard_vessel_params,
            asset=tampered_asset,
        )


def test_wave_asset_out_of_domain_rejected(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify out-of-domain wave inputs raise OutOfDomainError; no silent clipping."""
    comp_out = WaveComponent(amplitude_m=50.0, omega_radps=10.0, phase_rad=0.0, direction_to_rad=0.0)  # omega=10.0 > 5.0
    wave_out = WaveFieldSample(significant_height_m=100.0, peak_period_s=2.0, direction_to_rad=0.0, components=(comp_out,))

    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        FirstOrderWaveLoadModel.calculate(
            wave=wave_out,
            heading_rad=0.0,
            surge_mps=0.0,
            sway_mps=0.0,
            stage_time_s=0.0,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        )

    with pytest.raises(OutOfDomainError, match="outside applicability domain"):
        MeanDriftLoadModel.calculate(
            wave=MeanDriftSourceSample(components=(comp_out,)),
            heading_rad=0.0,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        )


def test_wave_inferred_assets_cannot_be_falsely_validated() -> None:
    """Verify InferredWaveResponseAsset and InferredWaveDriftAsset cannot have VALIDATED_FOR_VESSEL trust level."""
    with pytest.raises(ValueError, match="mock/inferred assets never become validated"):
        AssetMetadata(
            asset_id="fake_validated_wave",
            asset_type="wave_response_inferred",
            trust_level=AssetTrustLevel.VALIDATED_FOR_VESSEL,
            source_type="inferred",
            sha256="c" * 64,
            license="MIT",
        )


# ---------------------------------------------------------------------------
# 15. EnvironmentalLoadModel Wave Modes Integration (VR-09..11, TS-09/13/14)
# ---------------------------------------------------------------------------


def test_load_model_modes_isolation_and_diagnostics(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify WaveLoadMode OFF, FIRST_ORDER, MEAN_DRIFT, and BOTH isolate modes and report diagnostics."""
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(0.0, 0.0)),
        current=CurrentSample(velocity_ne=(0.0, 0.0)),
        wave=WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.0, components=(comp,)),
        mean_drift=MeanDriftSourceSample(components=(comp,)),
        time_s=0.5,
        tick=5,
    )
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # 1. Mode OFF: wave loads are strictly zero
    m_off = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.OFF,
    )
    loads_off = m_off.compute_loads(truth, nav)
    assert loads_off.wave_first_order == VesselLoad.zero()
    assert loads_off.wave_mean_drift == VesselLoad.zero()
    assert loads_off.details["wave_mode"] == "off"
    assert loads_off.details["first_order_components_count"] == 0
    assert loads_off.details["mean_drift_components_count"] == 0

    # 2. Mode FIRST_ORDER: only first-order is computed; mean-drift is zero
    m_1st = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.FIRST_ORDER,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
    )
    loads_1st = m_1st.compute_loads(truth, nav)
    assert loads_1st.wave_first_order != VesselLoad.zero()
    assert loads_1st.wave_mean_drift == VesselLoad.zero()
    assert loads_1st.details["wave_mode"] == "first_order"
    assert loads_1st.details["first_order_components_count"] == 1
    assert loads_1st.details["mean_drift_components_count"] == 0

    # 3. Mode MEAN_DRIFT: only mean-drift is computed; first-order is zero
    m_drift = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.MEAN_DRIFT,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    loads_drift = m_drift.compute_loads(truth, nav)
    assert loads_drift.wave_first_order == VesselLoad.zero()
    assert loads_drift.wave_mean_drift != VesselLoad.zero()
    assert loads_drift.details["wave_mode"] == "mean_drift"
    assert loads_drift.details["first_order_components_count"] == 0
    assert loads_drift.details["mean_drift_components_count"] == 1

    # 4. Mode BOTH: both are computed
    m_both = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    loads_both = m_both.compute_loads(truth, nav)
    assert loads_both.wave_first_order == loads_1st.wave_first_order
    assert loads_both.wave_mean_drift == loads_drift.wave_mean_drift
    assert loads_both.details["wave_mode"] == "both"
    assert loads_both.details["first_order_components_count"] == 1
    assert loads_both.details["mean_drift_components_count"] == 1


def test_load_model_mode_missing_asset_fails_in_init(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify EnvironmentalLoadModel fails at init if required wave asset for mode is missing."""
    with pytest.raises(AssetMissingError, match="First-order wave response asset is required"):
        EnvironmentalLoadModel(vessel_params=standard_vessel_params, wave_mode=WaveLoadMode.FIRST_ORDER)

    with pytest.raises(AssetMissingError, match="Wave mean-drift asset is required"):
        EnvironmentalLoadModel(vessel_params=standard_vessel_params, wave_mode=WaveLoadMode.MEAN_DRIFT)

    with pytest.raises(AssetMissingError, match="First-order wave response asset is required"):
        EnvironmentalLoadModel(
            vessel_params=standard_vessel_params,
            wave_mode=WaveLoadMode.BOTH,
            wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
        )


def test_load_total_exact_summation_with_waves(standard_vessel_params: VesselEnvironmentalParameters) -> None:
    """Verify EnvironmentalLoads explicitly sums wind + current + wave_first_order + wave_mean_drift."""
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.0, direction_to_rad=0.0)
    truth = EnvironmentTruth(
        wind=WindSample(velocity_ne=(10.0, 0.0)),
        current=CurrentSample(velocity_ne=(0.0, 1.0)),
        wave=WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.0, components=(comp,)),
        mean_drift=MeanDriftSourceSample(components=(comp,)),
        time_s=1.0,
        tick=10,
    )
    nav = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    model = EnvironmentalLoadModel(
        vessel_params=standard_vessel_params,
        current_strategy=CurrentStrategy.EXTERNAL_CURRENT_LOAD,
        wave_mode=WaveLoadMode.BOTH,
        wave_first_order_asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        wave_mean_drift_asset=DEFAULT_INFERRED_WAVE_DRIFT_ASSET,
    )
    loads = model.compute_loads(truth, nav)

    expected_total = loads.wind + loads.current + loads.wave_first_order + loads.wave_mean_drift
    assert math.isclose(loads.total.surge_n, expected_total.surge_n, rel_tol=1e-9)
    assert math.isclose(loads.total.sway_n, expected_total.sway_n, rel_tol=1e-9)
    assert math.isclose(loads.total.yaw_nm, expected_total.yaw_nm, rel_tol=1e-9)
    assert math.isclose(loads.total.roll_nm, expected_total.roll_nm, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# 16. Stage-Time Forcing dt/2 Quadrature Convergence Probe & Replay
# ---------------------------------------------------------------------------


def test_wave_stage_time_forcing_dt_half_convergence_probe(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Verify numerical quadrature of stage-time wave forcing converges at O(dt^2) as dt -> dt/2.

    Explicit claim ceiling: This test verifies purely the numerical time-discretization
    and sampling consistency of stage-time forcing F_w(t) under trapezoidal quadrature.
    It does NOT implement or verify continuous plant dynamics or RK4 integration (#52).
    """
    comp = WaveComponent(amplitude_m=1.0, omega_radps=0.8, phase_rad=0.2, direction_to_rad=0.1)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.1, components=(comp,))

    # Exact integral of F_x(t) = F_0 * cos(omega_e * t + phi) over [0, T]
    # Let's numerically integrate F_x(t) from t=0 to T=4.0 s using trapezoid rule with dt and dt/2
    T = 4.0

    def integrate_forcing(n_steps: int) -> float:
        dt = T / float(n_steps)
        total = 0.0
        for i in range(n_steps + 1):
            t = i * dt
            w = 0.5 if i in (0, n_steps) else 1.0
            load_val = FirstOrderWaveLoadModel.calculate(
                wave=wave,
                heading_rad=0.1,
                surge_mps=2.0,
                sway_mps=0.0,
                stage_time_s=t,
                params=standard_vessel_params,
                asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
            )
            total += w * load_val.surge_n * dt
        return total

    # Trapezoid rule error should decrease by ~4x (O(dt^2)) when doubling steps from 40 to 80
    i_coarse = integrate_forcing(40)
    i_fine = integrate_forcing(80)
    i_reference = integrate_forcing(1000)

    err_coarse = abs(i_coarse - i_reference)
    err_fine = abs(i_fine - i_reference)

    # Ratio of errors should be close to 4.0 for O(dt^2) convergence
    ratio = err_coarse / max(err_fine, 1e-12)
    assert 3.8 < ratio < 4.2


def test_wave_loads_replay_and_order_independence(
    standard_vessel_params: VesselEnvironmentalParameters,
) -> None:
    """Verify identical queries in any order yield bit-identical wave load results."""
    comp1 = WaveComponent(amplitude_m=1.0, omega_radps=0.7, phase_rad=0.1, direction_to_rad=0.2)
    comp2 = WaveComponent(amplitude_m=0.5, omega_radps=1.1, phase_rad=0.5, direction_to_rad=0.8)
    wave = WaveFieldSample(significant_height_m=2.0, peak_period_s=8.0, direction_to_rad=0.4, components=(comp1, comp2))

    t_eval = [0.1, 0.5, 1.2, 3.8]

    # Forward order
    loads_fwd = [
        FirstOrderWaveLoadModel.calculate(
            wave=wave,
            heading_rad=0.3,
            surge_mps=3.0,
            sway_mps=0.2,
            stage_time_s=t,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        )
        for t in t_eval
    ]

    # Reverse order
    loads_rev = [
        FirstOrderWaveLoadModel.calculate(
            wave=wave,
            heading_rad=0.3,
            surge_mps=3.0,
            sway_mps=0.2,
            stage_time_s=t,
            params=standard_vessel_params,
            asset=DEFAULT_INFERRED_WAVE_RESPONSE_ASSET,
        )
        for t in reversed(t_eval)
    ]

    assert loads_fwd == list(reversed(loads_rev))
