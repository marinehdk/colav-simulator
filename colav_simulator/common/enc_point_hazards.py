"""Read Kartverket point reefs omitted by seacharts' polygon-only layers.

Kartverket defines Grunne as S-57 UWTROC; Skjer uses the dataset's
high-water reference. Depths use chart datum; missing depths remain hazards.
The ENC instance owns a fixed source snapshot; no runtime file polling.
"""

from __future__ import annotations

import math
from functools import lru_cache

import fiona
import pyproj
from seacharts.utils.files import resolve_file_path
from shapely import ops
from shapely.geometry import GeometryCollection, box, shape
from shapely.geometry.base import BaseGeometry


def chart_point_hazards(enc: object, minimum_depth_m: float) -> dict[str, tuple[BaseGeometry, str]]:
    """Load immutable local source points once per ENC, filter depth per vessel."""
    scope = getattr(getattr(enc, "_environment", None), "scope", None)
    if scope is None or not getattr(scope, "files", None):
        return {}
    cache = getattr(enc, "_colav_point_hazards", None)
    if cache is None:
        target_crs = pyproj.CRS.from_epsg(25800 + int(enc.utm_zone))
        bounds = tuple(map(float, enc.bbox))
        records: dict[str, list[tuple[BaseGeometry, float | None]]] = {}
        for name in scope.files:
            path = resolve_file_path(name)
            if not path.exists():
                raise ValueError(f"ENC point-hazard source is missing: {path}")
            available = {layer.lower(): layer for layer in fiona.listlayers(path)}
            for canonical, layer_id in (("grunne", "UWTROC"), ("skjer", "SKJER")):
                if canonical not in available:
                    continue
                selected = records.setdefault(layer_id, [])
                with fiona.open(path, layer=available[canonical]) as source:
                    if not source.crs:
                        raise ValueError(f"ENC point-hazard source has no CRS: {path}")
                    source_crs = pyproj.CRS.from_user_input(source.crs)
                    forward = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
                    inverse = pyproj.Transformer.from_crs(target_crs, source_crs, always_xy=True)
                    source_bounds = inverse.transform_bounds(*bounds, densify_pts=21)
                    for feature in source.filter(bbox=source_bounds):
                        if feature.geometry is None:
                            raise ValueError("ENC point hazard has no geometry")
                        geometry = ops.transform(forward.transform, shape(feature.geometry))
                        if not box(*bounds).intersects(geometry):
                            continue
                        depth = feature.properties.get("dybde") if canonical == "grunne" else None
                        selected.append((geometry, None if depth is None else float(depth)))
        cache = {name: tuple(values) for name, values in records.items()}
        enc._colav_point_hazards = cache
    return {
        layer_id: (
            _depth_filtered_geometry(records, float(minimum_depth_m)),
            "KARTVERKET_GRUNNE_DEPTH_FILTERED" if layer_id == "UWTROC" else "KARTVERKET_SKJER",
        )
        for layer_id, records in cache.items()
    }


@lru_cache(maxsize=32)
def _depth_filtered_geometry(
    records: tuple[tuple[BaseGeometry, float | None], ...],
    minimum_depth_m: float,
) -> BaseGeometry:
    selected = [
        geometry for geometry, depth in records if depth is None or not math.isfinite(depth) or depth <= minimum_depth_m
    ]
    return ops.unary_union(selected) if selected else GeometryCollection()
