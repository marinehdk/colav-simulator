"""P0-D ENC bathymetry TIN and P1-A SLCONS export are display-grade, never navigation."""

import json

import numpy as np
import pytest
from shapely.geometry import box, mapping

from tools.terrain.build_qingdao_static import (
    CATSLC_NAMES,
    DEPTH_CONTOUR_BANDS_M,
    ROOT,
    UNITY,
    build_constrained_tin,
    clamp_depth_areas,
    flag_sounding_spikes,
    nearest_hold,
    read_enc_bathymetry,
    read_shoreworks,
    sample_tin,
    shorework_dimensions,
)

ENC = ROOT / "data/ais/qingdao-enc/QDWJenc20230410"
requires_enc = pytest.mark.skipif(not ENC.exists(), reason="ENC cells are local-only source data")


def test_tin_reproduces_constraints_and_interpolates_linearly():
    points = np.array([[0.0, 0.0, -10.0], [100.0, 0.0, -20.0], [0.0, 100.0, -5.0], [100.0, 100.0, -15.0]])
    tri, nodes = build_constrained_tin(points)
    sampled = sample_tin(tri, nodes, np.array([[0.0, 0.0], [100.0, 100.0], [50.0, 50.0]]))
    assert sampled[:2] == pytest.approx([-10.0, -15.0])
    assert sampled[2] == pytest.approx(-12.5)


def test_tin_is_nan_outside_hull_and_nearest_hold_fills():
    points = np.array([[0.0, 0.0, -3.0], [100.0, 0.0, -9.0], [0.0, 100.0, -6.0]])
    tri, nodes = build_constrained_tin(points)
    assert np.isnan(sample_tin(tri, nodes, np.array([[400.0, 400.0]])))[0]
    grid = np.array([[1.0, np.nan, np.nan], [np.nan, np.nan, np.nan]])
    filled = nearest_hold(grid)
    assert np.isfinite(filled).all()
    assert filled.min() == 1.0 and filled.max() == 1.0


def test_spike_rule_flags_isolated_outlier_but_keeps_graded_channel():
    flat = np.array([[x * 80.0, (x % 2) * 60.0, -10.0] for x in range(12)])
    spike = np.array([[400.0, 100.0, -52.0]])
    graded = np.array([[float(x) * 60.0, y * 120.0, -5.0 - x * 1.6] for x in range(11) for y in range(2)])
    flagged = flag_sounding_spikes(np.vstack([flat, spike]))
    assert flagged[flat.shape[0]]  # the lone -52 m outlier goes
    assert not flagged[: flat.shape[0]].any()
    assert not flag_sounding_spikes(graded).any()  # a real graded slope stays


def _clamp_grid():
    size = 64
    geotransform = (0.0, 10.0, 0.0, 630.0, 0.0, -10.0)
    z = np.linspace(-2.0, -30.0, size * size).reshape(size, size)
    is_land = np.zeros((size, size), bool)
    is_land[:, -4:] = True
    is_land[-1, :] = True  # south edge centres fall outside the box(0, 0, 630, 630) feature
    return z, is_land, geotransform, size


def test_depth_area_clamp_confines_interpolation_to_drval_band_and_skips_land():
    z, is_land, geotransform, size = _clamp_grid()
    feature = {"geometry": mapping(box(0, 0, 630, 630)), "drval1": 5.0, "drval2": 10.0}
    clamped, stats = clamp_depth_areas(z, [feature], geotransform, is_land)
    sea = ~is_land
    assert clamped[sea].min() >= -10.0 - 1e-6
    assert clamped[sea].max() <= -5.0 + 1e-6
    assert stats["features_clamped"] == 1
    outside_band = (z < -10.0) | (z > -5.0)
    assert stats["cells_clamped"] == int((outside_band & sea).sum())
    assert np.array_equal(clamped[is_land], z[is_land])  # land keeps GLO-30 values


@pytest.mark.parametrize("catslc", sorted(CATSLC_NAMES))
def test_shorework_dimensions_stay_inside_the_plan_bands(catslc):
    width, height, basis = shorework_dimensions(catslc)
    assert 8.0 <= width <= 30.0
    if catslc in (1, 3):  # breakwater / mole
        assert 8.0 <= height <= 12.0
    elif catslc in (4, 5, 6, 15, 16):  # pier / wharf decks
        assert height == 6.0
    else:  # revetment-class works
        assert 3.0 <= height <= 5.0
    assert basis == "assumed"


def test_shorework_dimensions_prefer_recorded_elevation_when_present():
    width, height, basis = shorework_dimensions(6, elevation_m=12.5)
    assert height == 12.5
    assert basis.startswith("recorded")
    assert width == shorework_dimensions(6)[0]
    width_none, height_none, basis_none = shorework_dimensions(None)
    assert 8.0 <= width_none <= 30.0 and 3.0 <= height_none <= 5.0 and basis_none == "assumed"


@requires_enc
def test_enc_bathymetry_reads_seven_bands_and_msl_datum():
    bathy = read_enc_bathymetry()
    assert bathy["contour_bands"] == list(DEPTH_CONTOUR_BANDS_M)
    assert bathy["vdat"] == 3 and bathy["duni"] == 1  # MSL, metres
    assert bathy["soundings"].ndim == 2 and bathy["soundings"].shape[1] == 3
    assert len(bathy["soundings"]) > 400
    assert len(bathy["contours"]) > 5000 and len(bathy["shoreline"]) > 500
    assert bathy["depare"]


@requires_enc
def test_shoreworks_export_covers_lines_and_areas_with_required_fields():
    features = read_shoreworks()
    lines = [f for f in features if f["kind"] == "line"]
    areas = [f for f in features if f["kind"] == "area"]
    assert lines and areas  # 18 km window holds both classes
    for feature in features:
        assert {"id", "type", "kind", "width_m", "height_m", "elevation_basis", "ring"} <= set(feature)
        assert len(feature["ring"]) >= 4
        assert 3.0 <= feature["height_m"] <= 12.0
    for line in lines:
        assert 8.0 <= line["width_m"] <= 30.0
        assert line["length_m"] > 0
        expected = line["length_m"] * line["width_m"]
        area = _ring_area(line["ring"])
        assert 0.2 * expected < area < 3.0 * expected  # buffered footprint, not the raw centreline


def _ring_area(ring):
    ring = np.asarray(ring, float)
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def test_baked_manifest_declares_enc_water_floor_and_datum():
    manifest = json.loads((UNITY / "terrain.json").read_text())
    floor = manifest["water_floor"]
    assert isinstance(floor, dict)
    assert "CN436123" in floor["source"]
    assert "VDAT=3" in floor["vertical_datum"] and "mean sea level" in floor["vertical_datum"]
    assert "EGM2008" in floor["vertical_datum"]
    assert manifest["min_height_m"] < -40  # real seafloor goes below the old synthetic floor
    assert manifest["min_height_m"] >= -64
    grid = manifest["depth_grid"]
    assert grid["file"] == "depths.bytes"
    assert (UNITY / grid["file"]).stat().st_size == manifest["resolution"] ** 2 * 2


def test_baked_shoreworks_table_registers_the_visual_only_assumption():
    document = json.loads((UNITY / "shoreworks.json").read_text())
    assert document["assumption"] == "视觉修整、非实测"
    assert document["features"]
    for feature in document["features"]:
        assert feature["width_m"] is None or 8.0 <= feature["width_m"] <= 30.0
        assert 3.0 <= feature["height_m"] <= 12.0
        assert feature["type"]
