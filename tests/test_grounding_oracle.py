from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import MultiPolygon, Point, Polygon

from colav_simulator.common.map_functions import (
    extract_relevant_grounding_hazards_as_union,
    extract_typed_grounding_hazards,
)


def fixture_enc() -> SimpleNamespace:
    land_with_hole = Polygon(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        holes=[[(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)]],
    )
    safe_depth = Polygon([(-20.0, -20.0), (20.0, -20.0), (20.0, 20.0), (-20.0, 20.0)])
    return SimpleNamespace(
        land=SimpleNamespace(geometry=MultiPolygon([land_with_hole])),
        shore=SimpleNamespace(geometry=MultiPolygon()),
        seabed={
            0: SimpleNamespace(geometry=safe_depth),
            10: SimpleNamespace(geometry=safe_depth),
        },
    )


def test_polygon_interiors_remain_navigable_after_hazard_extraction() -> None:
    enc = fixture_enc()
    hazards = extract_relevant_grounding_hazards_as_union(10, enc)
    assert hazards[0].contains(Point(2.0, 2.0))
    assert not hazards[0].contains(Point(5.0, 5.0))


def test_chart_layers_and_quality_evidence_are_not_conflated() -> None:
    hazards = extract_typed_grounding_hazards(10, fixture_enc())
    layers = {layer.layer_id: layer for layer in hazards.layers}
    assert layers["LAND"].source_status == "AVAILABLE"
    assert layers["SHORE"].source_status == "AVAILABLE"
    assert layers["DEPARE_SHALLOW"].source_status == "DERIVED_FROM_SEABED"
    assert layers["UNSARE"].source_status == "UNAVAILABLE_SOURCE"
    assert hazards.coverage_status == "UNAVAILABLE_SOURCE"
    assert hazards.quality_status == "UNAVAILABLE_SOURCE"
