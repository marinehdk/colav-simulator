"""S10 FCB45 three-main plus two-rudder actuator layout asset tests."""

from __future__ import annotations

import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.allocator import (
    KNOWN_ACTUATOR_LAYOUT_ASSETS,
    actuator_layout_content_sha256,
)
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.contracts import AssetTrustLevel

LAYOUT_ID = "fcb45_main_rudder_actuator_layout_v1"
ACTUATOR_IDS = (
    "main_thruster_port",
    "main_thruster_center",
    "main_thruster_starboard",
    "rudder_port",
    "rudder_starboard",
)


def test_main_rudder_layout_is_registered_and_content_hash_is_stable() -> None:
    assert LAYOUT_ID in KNOWN_ACTUATOR_LAYOUT_ASSETS
    asset = KNOWN_ACTUATOR_LAYOUT_ASSETS[LAYOUT_ID]
    assert asset.metadata.sha256 == actuator_layout_content_sha256(asset.actuators)
    assert asset.verify_integrity()
    assert asset.actuator_ids() == ACTUATOR_IDS
    assert asset.metadata.trust_level != AssetTrustLevel.VALIDATED_FOR_VESSEL
    assert asset.metadata.provenance["validated_for_vessel"] is False
    assert "deviation_ledger" in asset.metadata.provenance
    assert isinstance(asset.metadata.provenance["deviation_ledger"], tuple)


def test_main_rudder_geometry_limits_and_effectiveness() -> None:
    asset = KNOWN_ACTUATOR_LAYOUT_ASSETS[LAYOUT_ID]
    mains = asset.actuators[:3]
    assert all(spec.kind == "main" for spec in mains)
    assert all(spec.position_body_m[0] == pytest.approx(-18.094) for spec in mains)
    assert [spec.position_body_m[1] for spec in mains] == [-3.0, 0.0, 3.0]
    assert all(spec.min_force_n == -135.0e3 and spec.max_force_n == 135.0e3 for spec in mains)
    rudders = asset.actuators[3:]
    assert [spec.actuator_id for spec in rudders] == ["rudder_port", "rudder_starboard"]
    assert all(spec.kind == "rudder" for spec in rudders)
    assert [spec.position_body_m for spec in rudders] == [(-19.594, -3.0), (-19.594, 3.0)]
    assert all(spec.orientation_body_rad == pytest.approx(-0.5 * math.pi) for spec in rudders)
    assert all(spec.min_force_n == -180.0e3 and spec.max_force_n == 180.0e3 for spec in rudders)

    matrix = asset.effectiveness_matrix()
    assert matrix.shape == (3, 5)
    np.testing.assert_allclose(matrix[:, 3:], [[0.0, 0.0], [-1.0, -1.0], [19.594, 19.594]], atol=1e-9)
    assert not np.any(matrix[1, :3])


def test_main_rudder_layout_appears_in_catalog_axis() -> None:
    layouts = list_stack_catalog()["module_axes"]["actuation"]["layouts"]
    entry = next(item for item in layouts if item["layout_asset_id"] == LAYOUT_ID)
    assert entry["display_name"] == "FCB45 main + rudder layout"
    assert entry["identity"] == "data_driven_allocator"
    assert entry["expected_effect"]
