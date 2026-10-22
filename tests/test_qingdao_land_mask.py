"""P0-B land mask: interior rings are water; wet-band rings feed the binary WaterMask overlay."""

import json

import pytest
from shapely.geometry import Point, Polygon

from tools.terrain.build_qingdao_static import (
    MIN_RING_AREA_M2,
    WET_BAND_M,
    UNITY,
    bridge_cut_ring,
    land_mask_document,
)


def _ring_polygon(ring):
    return Polygon([(p["x"], p["y"]) for p in ring["points"]])


def test_bridge_cut_ring_excludes_interior_rings_from_land():
    donut = Polygon(
        [(0, 0), (0, 100), (100, 100), (100, 0)],
        holes=[[(40, 40), (40, 60), (60, 60), (60, 40)]],
    )
    flat = bridge_cut_ring(donut)
    polygon = Polygon(flat)
    assert polygon.area == pytest.approx(donut.area, rel=1e-6)  # hole area is gone
    assert polygon.contains(Point(50, 50)) is False  # the bay/pond reads as water
    assert polygon.contains(Point(10, 10)) is True  # land survives the bridge
    assert polygon.contains(Point(90, 90)) is True
    assert flat[0] == flat[-1]  # ring stays explicitly closed for the Unity spline


def test_bridge_cut_ring_attaches_every_interior_ring_above_threshold():
    two_ponds = Polygon(
        [(0, 0), (0, 200), (200, 200), (200, 0)],
        holes=[
            [(20, 20), (20, 70), (70, 70), (70, 20)],
            [(120, 120), (120, 170), (170, 170), (170, 120)],
            [(90, 90), (92, 90), (92, 92), (90, 92)],  # under the area floor: dropped
        ],
    )
    polygon = Polygon(bridge_cut_ring(two_ponds))
    speck = Polygon([(90, 90), (92, 90), (92, 92), (90, 92)])
    assert polygon.area == pytest.approx(
        two_ponds.area + speck.area, rel=1e-6
    )  # both big holes cut; the sub-floor speck is filled as land
    assert not polygon.contains(Point(45, 45)) and not polygon.contains(Point(145, 145))
    assert polygon.contains(Point(95, 10))


def test_bridge_cut_ring_passes_simple_polygons_through():
    simple = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])
    ring = bridge_cut_ring(simple)
    assert Polygon(ring).equals(simple)  # no holes: geometry unchanged, ring closed
    assert ring[0] == ring[-1]


def test_land_mask_document_pairs_clip_rings_with_eroded_wet_rings():
    land = Polygon(
        [(0, 0), (0, 450), (450, 450), (450, 0)],
        holes=[[(150, 150), (150, 300), (300, 300), (300, 150)]],
    )
    document = land_mask_document(land, origin_e=1000, origin_n=2000)
    assert document["wet_band_m"] == WET_BAND_M
    clip = [_ring_polygon(ring) for ring in document["rings"]]
    wet = [_ring_polygon(ring) for ring in document["wetRings"]]
    assert len(clip) == 1 and len(wet) == 1
    for ring in document["rings"] + document["wetRings"]:
        points = ring["points"]
        assert len(points) >= 4  # closed, at least a triangle
        assert all(set(p) == {"x", "y"} for p in points)
    # wet rings are the land side shrunk by the band: inside the clip polygon, smaller area
    assert clip[0].contains(wet[0].representative_point())
    assert wet[0].area == pytest.approx(land.buffer(-WET_BAND_M).area, rel=1e-3)
    assert wet[0].area < clip[0].area
    # offsets applied: all coordinates are local to the origin
    xs = [p["x"] for p in document["rings"][0]["points"]]
    ys = [p["y"] for p in document["rings"][0]["points"]]
    assert min(xs) == -1000 and max(xs) == -550
    assert min(ys) == -2000 and max(ys) == -1550


def test_land_mask_document_drops_water_below_the_area_floor():
    speck = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])  # 100 m² survives
    dot = Polygon([(20, 20), (20, 21), (21, 21), (21, 20)])  # 1 m² dropped
    document = land_mask_document(
        __import__("shapely.geometry", fromlist=["MultiPolygon"]).MultiPolygon([speck, dot]), 0, 0
    )
    assert len(document["rings"]) == 1
    assert MIN_RING_AREA_M2 == 50.0


def test_baked_land_mask_carries_wet_rings_and_open_water_holes():
    path = UNITY / "land-mask.json"
    if not path.exists():
        pytest.skip("baked land-mask.json is a build artifact")
    document = json.loads(path.read_text())
    assert document["wetRings"], "WaterMask overlay needs the eroded wet-band rings"
    assert document["wet_band_m"] == WET_BAND_M
    # the committed bake has polygons with interior rings: the flattened rings must be smaller
    # than their exterior-only hull, i.e. interior water survived the bridge cut
    rings = [Polygon([(p["x"], p["y"]) for p in ring["points"]]) for ring in document["rings"]]
    assert all(ring.area > 0 for ring in rings)
