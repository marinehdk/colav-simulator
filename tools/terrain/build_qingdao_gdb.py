"""Build `data/enc/Qingdao_utm51.gpkg` for seacharts from the static-terrain chart.

The simulation core (seacharts ENC) reads Kartverket-style layers by name via
fiona (driver-agnostic): ``landareal`` (land polygons), ``dybdeareal`` (depth
areas with a ``minimumsdybde`` field), ``grunne`` (shoals with a ``dybde``
field) and shore labels ``skjer``/``torrfall``/``ikkekartlagtsjomaltomr``.
The Qingdao S-57 pipeline already emitted exactly equivalent depth-binned
polygons in ``colav_simulator/data/qingdao_static/chart.json`` (absolute
UTM 51N, bins [-5, 0, 2, 5, 10, 20, 30, 50]); this script re-packs them into
that schema (GeoPackage container — fiona's OpenFileGDB writer rejects the
EPSG:32651 SRS) so scenario YAMLs can use
``map_data_files: ["Qingdao_utm51.gpkg"]``.

Usage:  .venv/bin/python tools/terrain/build_qingdao_gdb.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import fiona
from fiona.crs import CRS

REPO = Path(__file__).resolve().parents[2]
CHART_JSON = REPO / "colav_simulator/data/qingdao_static/chart.json"
OUT_GPKG = REPO / "data/enc/Qingdao_utm51.gpkg"

CRS_UTM51N = CRS.from_epsg(32651)
POLYGON_SCHEMA = {"geometry": "Polygon", "properties": {"minimumsdybde": "float"}}
SHORE_SCHEMA = {"geometry": "Polygon", "properties": {}}


def iter_polygons(geometry: dict):
    """Yield (outer_ring, holes) polygons from a GeoJSON Polygon/MultiPolygon."""
    kind = geometry["type"]
    if kind == "Polygon":
        rings = geometry["coordinates"]
        yield rings[0], rings[1:]
    elif kind == "MultiPolygon":
        for rings in geometry["coordinates"]:
            yield rings[0], rings[1:]
    else:
        raise ValueError(f"unsupported geometry {kind}")


def write_layer(gpkg: Path, name: str, features: list[tuple[dict, dict]], schema: dict) -> None:
    with fiona.open(
        gpkg,
        "w",
        layer=name,
        driver="GPKG",
        schema=schema,
        crs=CRS_UTM51N,
    ) as sink:
        for geometry, properties in features:
            sink.write({"geometry": geometry, "properties": properties})
    print(f"  {name}: {len(features)} features")


def main() -> int:
    chart = json.loads(CHART_JSON.read_text())
    land: list[tuple[dict, dict]] = []
    depth_areas: list[tuple[dict, dict]] = []
    for feature in chart["features"]:
        props = feature["properties"]
        depth = float(props.get("depth_m", 0.0))
        for outer, holes in iter_polygons(feature["geometry"]):
            geometry = {"type": "Polygon", "coordinates": ([outer] if not holes else [outer, *holes])}
            if depth <= 0.0:
                # Land and drying (-5 m intertidal) areas are both zero-depth regions.
                land.append((geometry, {"minimumsdybde": depth}))
            else:
                depth_areas.append((geometry, {"minimumsdybde": depth}))

    if OUT_GPKG.exists():
        os.remove(OUT_GPKG)
    print(f"writing {OUT_GPKG}")
    write_layer(OUT_GPKG, "landareal", land, POLYGON_SCHEMA)
    write_layer(OUT_GPKG, "dybdeareal", depth_areas, POLYGON_SCHEMA)
    # Empty placeholder layers for the remaining Kartverket labels seacharts queries.
    write_layer(OUT_GPKG, "grunne", [], {"geometry": "Polygon", "properties": {"dybde": "float"}})
    for shore_label in ("skjer", "torrfall", "ikkekartlagtsjomaltomr"):
        write_layer(OUT_GPKG, shore_label, [], SHORE_SCHEMA)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
