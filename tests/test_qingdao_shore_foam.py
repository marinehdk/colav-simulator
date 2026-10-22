"""P0-C shore-wave decal placement bake (plan §2 P0-C, 2026-10-19).

Synthetic-geometry tests for the placement table: quiet water stays unplaced,
only offshore-facing coast near the static camera presets is selected, the
decal yaw points local +X landward, and the decal region covers every entry.
"""

import numpy as np
import pytest
from shapely.geometry import LineString, Polygon, box

from tools.terrain.build_qingdao_static import shore_foam_document

ORIGIN_E, ORIGIN_N = 256315.0, 3992326.0


def south_coast_line(origin_e=ORIGIN_E, origin_n=ORIGIN_N):
    """A straight coast at local z=-4400 running east-west, water to the south."""
    z = origin_n - 4400.0
    return LineString([(origin_e - 1200.0, z), (origin_e + 1200.0, z)])


def south_coast_land(origin_e=ORIGIN_E, origin_n=ORIGIN_N):
    """Land filling everything north of the south coast (water = open sea south)."""
    z = origin_n - 4400.0
    return Polygon([
        (origin_e - 9000.0, z), (origin_e + 9000.0, z),
        (origin_e + 9000.0, z + 17000.0), (origin_e - 9000.0, z + 17000.0),
    ])


def test_open_south_coast_near_viewpoint_is_placed_with_bounded_count():
    doc = shore_foam_document(south_coast_land(), [south_coast_line()], ORIGIN_E, ORIGIN_N)
    assert doc["schema"] == "qingdao-shorefoam.v1"
    assert 1 <= len(doc["decals"]) <= 3, "plan shrinks placement to 2-3 main-view segments"
    for entry in doc["decals"]:
        assert entry["size_x"] > 0 and entry["size_z"] > 0
        # near the overlook preset (-2300, -4100), never on the far side of the window
        assert abs(entry["x"] + 2300.0) < 3000.0 and abs(entry["z"] + 4100.0) < 3000.0


def test_quiet_enclosed_basin_coast_is_never_placed():
    # A U-shaped breakwater enclosing a basin: the coast inside faces water,
    # but the waterward ray hits the breakwall — 港内安静水域不布.
    ox, oz = ORIGIN_E - 2300.0, ORIGIN_N - 4100.0  # overlook preset local, in UTM
    basin_wall = Polygon([
        (ox - 400.0, oz - 200.0), (ox + 400.0, oz - 200.0),
        (ox + 400.0, oz + 600.0), (ox - 400.0, oz + 600.0),
        (ox - 400.0, oz + 200.0), (ox - 300.0, oz + 200.0),
        (ox - 300.0, oz + 500.0), (ox + 300.0, oz + 500.0),
        (ox + 300.0, oz - 100.0), (ox - 400.0, oz - 100.0),
    ])
    land = basin_wall
    coast = LineString([(ox - 300.0, oz + 480.0), (ox + 300.0, oz + 480.0)])
    doc = shore_foam_document(land, [coast], ORIGIN_E, ORIGIN_N)
    assert doc["decals"] == []


def test_bay_interior_north_facing_coast_is_never_placed():
    # Coast whose water side points north into a >12 km channel: the ray gate
    # alone would pass it, the offshore (south half-plane) gate must reject it.
    z = ORIGIN_N - 4400.0
    land = Polygon([  # land south of the coast line: water stretches north 15 km
        (ORIGIN_E - 9000.0, z), (ORIGIN_E + 9000.0, z),
        (ORIGIN_E + 9000.0, z - 8000.0), (ORIGIN_E - 9000.0, z - 8000.0),
    ])
    coast = LineString([(ORIGIN_E - 1200.0, z), (ORIGIN_E + 1200.0, z)])
    doc = shore_foam_document(land, [coast], ORIGIN_E, ORIGIN_N)
    assert doc["decals"] == []


def test_decal_yaw_points_local_x_landward():
    doc = shore_foam_document(south_coast_land(), [south_coast_line()], ORIGIN_E, ORIGIN_N)
    assert doc["decals"], "fixture must yield at least one placement"
    for entry in doc["decals"]:
        # water due south -> landward = +north (scene +z); Unity yaw maps local
        # +X to (cos yaw, 0, -sin yaw), so landward north means yaw = -90 deg.
        assert entry["yaw_deg"] == pytest.approx(-90.0, abs=1.0)


def test_region_covers_every_decal():
    doc = shore_foam_document(south_coast_land(), [south_coast_line()], ORIGIN_E, ORIGIN_N)
    half = doc["region_size_m"] / 2.0
    for entry in doc["decals"]:
        assert abs(entry["x"] - doc["anchor_x"]) + entry["size_x"] / 2.0 <= half + 1e-6
        assert abs(entry["z"] - doc["anchor_z"]) + entry["size_z"] / 2.0 <= half + 1e-6


def test_no_qualifying_coast_yields_empty_schema():
    empty = Polygon()  # no land at all -> water side undefined, nothing placed
    doc = shore_foam_document(empty, [south_coast_line()], ORIGIN_E, ORIGIN_N)
    assert doc["decals"] == []
    assert doc["assumption"] == "视觉修整、非实测"
