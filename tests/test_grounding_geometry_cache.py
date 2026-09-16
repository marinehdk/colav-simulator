"""Reuse chart unions without masking changed chart/depth geometry."""

from dataclasses import replace

import shapely
from shapely import from_wkb
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry

from colav_simulator.common import map_functions as maps


def test_equal_chart_layers_reuse_union_but_changed_geometry_does_not(monkeypatch):
    layers = (
        maps.GroundingHazardLayer("LAND", box(0, 0, 5, 5), "AVAILABLE"),
        maps.GroundingHazardLayer("UWTROC", Point(8, 8), "AVAILABLE"),
    )
    hazards = maps.GroundingHazardSet(5, layers, "AVAILABLE", "AVAILABLE")
    maps._combined_hazard_geometry.cache_clear()
    union = maps.ops.unary_union
    calls = []

    def counted(geometries) -> BaseGeometry:
        calls.append(1)
        return union(geometries)

    monkeypatch.setattr(maps.ops, "unary_union", counted)
    expected = union([layer.geometry for layer in layers]).wkb
    assert hazards.combined_geometry.wkb == expected
    recreated = replace(hazards, layers=tuple(replace(layer, geometry=from_wkb(layer.geometry.wkb)) for layer in layers))
    assert recreated.combined_geometry.wkb == expected
    assert len(calls) == 1
    changed = replace(hazards, minimum_depth_m=10, layers=(replace(layers[0], geometry=box(0, 0, 10, 10)),))
    assert changed.combined_geometry.covers(Point(9, 9))
    assert not hazards.combined_geometry.covers(Point(9, 9))
    assert len(calls) == 2


def test_chart_union_preserves_source_precision_model():
    geometry = shapely.set_precision(box(0, 0, 8, 8), 2.0)
    layer = maps.GroundingHazardLayer("LAND", geometry, "AVAILABLE")
    hazards = maps.GroundingHazardSet(5, (layer,), "AVAILABLE", "AVAILABLE")
    expected = maps.ops.unary_union([geometry])
    assert hazards.combined_geometry.wkb == expected.wkb
    assert shapely.get_precision(hazards.combined_geometry) == shapely.get_precision(expected)
    floating = replace(hazards, layers=(replace(layer, geometry=from_wkb(geometry.wkb)),))
    assert shapely.get_precision(floating.combined_geometry) == 0.0
