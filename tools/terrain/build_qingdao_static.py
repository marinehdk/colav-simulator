#!/usr/bin/env python3
"""Bake display-only Qingdao ENC geography and terrain.

Inputs: three S-57 cells and two GLO-30 public elevation tiles.
The seafloor is a constrained TIN over SOUNDG soundings, DEPCNT contour
vertices and the COALNE zero line, clamped into DEPARE DRVAL bands.
SLCONS shore works are exported as buffered footprints with type-based
width/height assumptions. Run with the project .venv Python. No navigation
qualification is implied.
"""

import hashlib
import json
import os
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from osgeo import gdal, ogr
from pyproj import Transformer
from scipy.ndimage import distance_transform_edt
from scipy.spatial import Delaunay, cKDTree
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

from gui_server.replay_artifacts import _draw_geometry

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "colav_simulator/data/qingdao_static"
UNITY = ROOT / "sango/Assets/Resources/Qingdao"
WORK = ROOT / "tmp/qingdao-static"

DEPTH_CONTOUR_BANDS_M = (0.0, 2.0, 5.0, 10.0, 20.0, 30.0, 50.0)
DEPTH_RANGE_M = 64.0
MIN_RING_AREA_M2 = 50.0  # sliver floor for exported mask rings (polygons and holes alike)
# Land-side intertidal band for the binary WaterMask overlay: wide soft band that
# absorbs the ENC ZOC B horizontal uncertainty, never a hard cut (plan P0-B).
WET_BAND_M = 50.0
# Seaward growth of the Clipping rings (phase-1 waterline softening, 2026-10-21):
# the imagery cut edge is pushed past the DEM zero-crossing so it lands below the
# HDRP water surface instead of baring DEM slope pixels along the shore. 30 m
# covers the TIN COALNE-constrained zero-crossing band (grid cell ~17.6 m) plus
# slope run-out; 60 m proved too wide — satellite shallow-water pixels surfaced
# above the waterline as a green strip (视觉修整、非实测).
CLIP_EXTENSION_M = 30.0
CATSLC_NAMES = {  # S-57 CATSLC enumeration, GDAL s57expectedinput.csv attribute 60
    1: "breakwater", 2: "groyne", 3: "mole", 4: "pier", 5: "promenade_pier",
    6: "wharf", 7: "training_wall", 8: "riprap", 9: "revetment", 10: "sea_wall",
    11: "landing_steps", 12: "ramp", 13: "slipway", 14: "fender",
    15: "solid_face_wharf", 16: "open_face_wharf",
}
SLCONS_WIDTH_M = {  # footprint width per type, 8-30 m assumption band (视觉修整)
    1: 30.0, 2: 15.0, 3: 25.0, 4: 20.0, 5: 12.0, 6: 20.0, 7: 15.0, 8: 10.0,
    9: 12.0, 10: 10.0, 11: 8.0, 12: 15.0, 13: 15.0, 14: 8.0, 15: 20.0, 16: 20.0,
    None: 10.0,
}
SLCONS_HEIGHT_M = {  # crest/deck elevation: 防波堤 8-12 / 码头面 +6 / 护岸 3-5
    1: 10.0, 3: 10.0, 4: 6.0, 5: 6.0, 6: 6.0, 15: 6.0, 16: 6.0, None: 4.0,
}
# P0-C shore-wave decal placement (plan §2 P0-C): bake 2-3 open-sea shore
# segments near the static camera presets. 港内安静水域不布: a segment is
# "quiet" when its waterward ray hits land (opposite shore, breakwater) or
# the water side does not face the offshore half-plane (the Yellow Sea is
# south of this window; Jiaozhou Bay interior points north/west and is
# sheltered even where its fetch exceeds the ray probe).
SHORE_FOAM_SEGMENT_M = 160.0  # placement chunk length (one decal each)
SHORE_FOAM_OPEN_PROBE_M = 12000.0
SHORE_FOAM_OFFSHORE_DOT = 0.5  # waterward normal · due-south >= 0.5
SHORE_FOAM_VIEW_RADIUS_M = 5000.0
SHORE_FOAM_VIEW_CONE_DEG = 75.0
SHORE_FOAM_MAX_DECALS = 3
SHORE_FOAM_CLUSTER_GAP_M = 1500.0
SHORE_FOAM_CROSS_SHORE_M = 64.0  # decal X extent = wave run-up band
SHORE_FOAM_MARGIN_M = 128.0
# Main viewpoints mirror QingdaoStaticScene.Camera presets (local x/z, yaw deg
# east of north). Keep both lists in sync when a preset moves.
SHORE_FOAM_VIEWPOINTS = (
    ("bridge", (-2000.0, -1800.0), 55.0),
    ("overlook", (-2300.0, -4100.0), 55.0),
)


def scene_frame():
    """Shared UTM window: an 18 km square centred on the Qingdao pilot area."""
    project = Transformer.from_crs(4326, 32651, always_xy=True)
    origin_e, origin_n = project.transform(120.295, 36.045)
    origin_e, origin_n = round(origin_e), round(origin_n)
    extent = 18000
    bounds = box(origin_e - extent / 2, origin_n - extent / 2, origin_e + extent / 2, origin_n + extent / 2)
    return project, origin_e, origin_n, extent, bounds


def open_cell(path):
    """Open an S-57 cell with sounding-splitting so 3D multipoints become points."""
    os.environ["OGR_S57_OPTIONS"] = "SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=ON"
    return ogr.Open(str(path))


def enc_cells():
    return sorted((ROOT / "data/ais/qingdao-enc/QDWJenc20230410").glob("*.000"))


def shorework_dimensions(catslc, elevation_m=None):
    """Type-based width/height assumption (plan D1=A); a recorded elevation wins."""
    width = SLCONS_WIDTH_M.get(catslc, 10.0)
    if elevation_m is not None:
        return width, float(elevation_m), "recorded"
    return width, SLCONS_HEIGHT_M.get(catslc, 4.0), "assumed"


def _oriented(coords, ccw):
    """Closed ring coordinates re-traversed in the requested orientation."""
    points = list(coords[:-1]) if coords[0] == coords[-1] else list(coords)
    signed = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))
    if (signed < 0) == ccw:
        points.reverse()
    points.append(points[0])
    return points


def bridge_cut_ring(polygon, min_hole_area_m2=MIN_RING_AREA_M2):
    """Flatten interior rings into one hole-free perimeter via zero-width bridges.

    CesiumPolygonRasterOverlay unions single-ring polygons, so an interior ring
    (an enclosed bay or pond) can only be excluded from land by attaching it to
    the exterior with a degenerate bridge. The native earcut triangulation tiles
    exactly the land area; the bridge itself covers no area, so the two mask
    channels (this polygon ring and the gdal land raster below) stay consistent.
    """
    ring = _oriented(polygon.exterior.coords, ccw=True)
    if not polygon.interiors:
        return ring
    ring = ring[:-1]
    holes = sorted((Polygon(interior) for interior in polygon.interiors), key=lambda hole: -hole.area)
    for hole in holes:
        if hole.area < min_hole_area_m2:
            continue
        inner = _oriented(hole.exterior.coords, ccw=False)[:-1]
        a, b = min(
            ((ia, ib) for ia in range(len(ring)) for ib in range(len(inner))),
            key=lambda ij: (ring[ij[0]][0] - inner[ij[1]][0]) ** 2 + (ring[ij[0]][1] - inner[ij[1]][1]) ** 2,
        )
        ring = ring[: a + 1] + inner[b:] + inner[: b + 1] + ring[a:]
        ring.append(ring[0])
    return ring


def land_mask_document(land, origin_e, origin_n):
    """Unity land-mask: hole-free clip rings plus eroded wet-band rings (WaterMask overlay).

    Clip rings grow the landline seaward by CLIP_EXTENSION_M (mitre joins keep
    the digitised quay corners crisp) so the imagery cut edge sits underwater;
    wet rings still erode the true landline by WET_BAND_M.
    """
    def local(points):
        return [{"x": e - origin_e, "y": n - origin_n} for e, n in points]

    grown = land.buffer(CLIP_EXTENSION_M, join_style=2, mitre_limit=2.0).buffer(0)
    polygons = list(grown.geoms) if hasattr(grown, "geoms") else [grown]
    rings = [
        {"points": local(bridge_cut_ring(poly))}
        for poly in polygons
        if poly.area > MIN_RING_AREA_M2
    ]
    eroded = land.buffer(-WET_BAND_M).buffer(0)
    wet_polygons = list(eroded.geoms) if hasattr(eroded, "geoms") else ([eroded] if not eroded.is_empty else [])
    wet_rings = [
        {"points": local(bridge_cut_ring(poly))}
        for poly in wet_polygons
        if poly.area > MIN_RING_AREA_M2
    ]
    return {
        "wet_band_m": WET_BAND_M,
        "clip_extension_m": CLIP_EXTENSION_M,
        "note": "interior rings are water (zero-width bridges); clip rings grow land "
                "seaward by clip_extension_m so the imagery cut edge sits below the "
                "water surface (phase-1 waterline softening); wetRings erode land by "
                "wet_band_m so the binary WaterMask overlay marks a soft intertidal band "
                "inside the ENC landline (视觉修整、非实测)",
        "rings": rings,
        "wetRings": wet_rings,
    }


def flag_sounding_spikes(points, radius_m=600.0, min_neighbours=4, deviation_m=20.0, mad_factor=3.0):
    """Isolated-outlier rule for chart soundings; contour constraints are never flagged."""
    tree = cKDTree(points[:, :2])
    flagged = np.zeros(len(points), bool)
    for i, (x, y, z) in enumerate(points):
        hood = [j for j in tree.query_ball_point([x, y], radius_m) if j != i]
        if len(hood) < min_neighbours:
            continue
        neighbour_z = points[hood, 2]
        median = np.median(neighbour_z)
        deviation = abs(z - median)
        mad = np.median(np.abs(neighbour_z - median))
        flagged[i] = deviation > deviation_m and deviation > mad_factor * mad
    return flagged


def build_constrained_tin(points):
    """Delaunay TIN over soundings + contour + shoreline mass points (UTM metres)."""
    nodes = np.unique(np.round(np.asarray(points, float), 2), axis=0)
    return Delaunay(nodes[:, :2]), nodes


def sample_tin(tri, nodes, xy):
    """Linear TIN elevation at UTM points; NaN outside the triangulated hull."""
    xy = np.asarray(xy, float)
    simplex = tri.find_simplex(xy)
    elevation = np.full(len(xy), np.nan)
    inside = simplex >= 0
    s = simplex[inside]
    t = tri.transform[s]
    bary = np.einsum("ijk,ik->ij", t[:, :2, :], xy[inside] - t[:, 2, :])
    weights = np.concatenate([bary, 1.0 - bary.sum(axis=1, keepdims=True)], axis=1)
    elevation[inside] = np.einsum("ij,ij->i", weights, nodes[tri.simplices[s], 2])
    return elevation


def nearest_hold(values):
    """Fill NaN cells with the nearest sampled ENC value (display-only extrapolation)."""
    holes = ~np.isfinite(values)
    if not holes.any():
        return values
    indices = distance_transform_edt(holes, return_distances=False, return_indices=True)
    return values[tuple(indices)]


def _rasterize_mask(geometry, geotransform, size):
    vectors = ogr.GetDriverByName("Memory").CreateDataSource("")
    layer = vectors.CreateLayer("g", geom_type=ogr.wkbMultiPolygon)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(ogr.CreateGeometryFromJson(json.dumps(mapping(geometry))))
    layer.CreateFeature(feature)
    mask = gdal.GetDriverByName("MEM").Create("", size, size, 1, gdal.GDT_Byte)
    mask.SetGeoTransform(geotransform)
    gdal.RasterizeLayer(mask, [1], layer, burn_values=[1])
    return mask.ReadAsArray().astype(bool)


def clamp_depth_areas(floor, features, geotransform, is_land):
    """Confine TIN interpolation to each DEPARE DRVAL band; land cells stay untouched."""
    floor = floor.copy()
    cells = touched = 0
    for feature in features:
        drval1, drval2 = float(feature["drval1"]), float(feature["drval2"])
        if drval2 < drval1:
            continue
        inside = _rasterize_mask(shape(feature["geometry"]), geotransform, floor.shape[0])
        band = inside & ~is_land & np.isfinite(floor)
        if not band.any():
            continue
        clamped = np.clip(floor[band], -drval2, -drval1)  # depth band -> elevation band
        cells += int((clamped != floor[band]).sum())
        floor[band] = clamped
        touched += 1
    return floor, {"features_clamped": touched, "cells_clamped": cells}


def read_enc_bathymetry():
    """SOUNDG/DEPCNT/COALNE mass points, DEPARE bands and datum inside the scene window."""
    project, _, _, _, bounds = scene_frame()
    soundings, contours, shoreline, depare = [], [], [], []
    bands, dropped_bands, vdat, duni = set(), set(), set(), set()
    for path in enc_cells():
        ds = open_cell(path)
        meta = ds.GetLayerByName("DSID").GetNextFeature()
        vdat.add(meta.GetField("DSPM_VDAT"))
        duni.add(meta.GetField("DSPM_DUNI"))
        for feature in ds.GetLayerByName("SOUNDG"):
            geometry = feature.GetGeometryRef()
            depth = feature.GetField("DEPTH")
            if geometry is None or depth is None:
                continue
            geo = transform(project.transform, shape(json.loads(geometry.ExportToJson())))
            if not bounds.intersects(geo):
                continue
            soundings.append((geo.x, geo.y, -float(depth)))
        for feature in ds.GetLayerByName("DEPCNT"):
            geometry = feature.GetGeometryRef()
            value = feature.GetField("VALDCO")
            if geometry is None or value is None:
                continue
            geo = transform(project.transform, shape(json.loads(geometry.ExportToJson()))).intersection(bounds)
            if geo.is_empty:
                continue
            depth = float(value)
            if depth not in DEPTH_CONTOUR_BANDS_M:
                dropped_bands.add(depth)
                continue
            bands.add(depth)
            for line in getattr(geo, "geoms", [geo]):
                for x, y in np.asarray(line.coords):
                    contours.append((x, y, -depth))
        for feature in ds.GetLayerByName("COALNE"):
            geometry = feature.GetGeometryRef()
            if geometry is None:
                continue
            geo = transform(project.transform, shape(json.loads(geometry.ExportToJson()))).intersection(bounds)
            if geo.is_empty:
                continue
            for line in getattr(geo, "geoms", [geo]):
                for x, y in np.asarray(line.coords):
                    shoreline.append((x, y, 0.0))
        for feature in ds.GetLayerByName("DEPARE"):
            geometry = feature.GetGeometryRef()
            drval1, drval2 = feature.GetField("DRVAL1"), feature.GetField("DRVAL2")
            if geometry is None or drval1 is None or drval2 is None:
                continue
            geo = transform(project.transform, shape(json.loads(geometry.ExportToJson()))).intersection(bounds)
            if geo.is_empty or not geo.geom_type.endswith("Polygon"):
                continue
            depare.append({"geometry": mapping(geo), "drval1": float(drval1), "drval2": float(drval2)})
    if len(vdat) != 1 or len(duni) != 1:
        raise ValueError(f"conflicting ENC datums: VDAT={vdat} DUNI={duni}")
    return {
        "soundings": np.array(soundings).reshape(-1, 3),
        "contours": np.array(contours).reshape(-1, 3),
        "shoreline": np.array(shoreline).reshape(-1, 3),
        "contour_bands": sorted(bands),
        "dropped_bands": sorted(dropped_bands),
        "depare": depare,
        "vdat": vdat.pop(),
        "duni": duni.pop(),
    }


def read_shoreworks():
    """SLCONS export table: type-width buffered line footprints plus area footprints."""
    project, origin_e, origin_n, _, bounds = scene_frame()
    works = []
    for path in enc_cells():
        ds = open_cell(path)
        layer = ds.GetLayerByName("SLCONS")
        fields = {layer.GetLayerDefn().GetFieldDefn(i).GetName() for i in range(layer.GetLayerDefn().GetFieldCount())}
        for feature in layer:
            geometry = feature.GetGeometryRef()
            if geometry is None:
                continue
            geo = transform(project.transform, shape(json.loads(geometry.ExportToJson()))).intersection(bounds)
            if geo.is_empty:
                continue
            catslc = feature.GetField("CATSLC")
            catslc = int(catslc) if catslc is not None else None
            elevation = None
            for field in ("LNDELV", "TOPMAR", "HEIGHT"):  # none are set on these cells today
                if field in fields and feature.IsFieldSet(field):
                    elevation = feature.GetField(field)
                    break
            width, height, basis = shorework_dimensions(catslc, elevation)
            if geo.geom_type.endswith("LineString"):
                footprint = geo.buffer(width / 2)
                kind, length = "line", geo.length
            elif geo.geom_type.endswith("Polygon"):
                footprint, kind, length, width = geo, "area", None, None
            else:
                continue
            parts = list(getattr(footprint, "geoms", [footprint]))
            for part_i, part in enumerate(parts):
                works.append({
                    "id": f"{path.stem}-{feature.GetFID()}" + (f"-{part_i}" if len(parts) > 1 else ""),
                    "kind": kind,
                    "type": CATSLC_NAMES.get(catslc, "unspecified_shoreline"),
                    "catslc": catslc,
                    "width_m": width,
                    "height_m": height,
                    "elevation_basis": basis,
                    "length_m": round(length, 1) if length is not None else None,
                    "ring": [[x - origin_e, y - origin_n] for x, y in part.exterior.coords],
                })
    return works


def read_coastline() -> list[LineString]:
    """COALNE LineStrings in the scene window (UTM metres, structure preserved)."""
    project, _, _, _, bounds = scene_frame()
    lines: list[LineString] = []
    for path in enc_cells():
        ds = open_cell(path)
        for feature in ds.GetLayerByName("COALNE"):
            geometry = feature.GetGeometryRef()
            if geometry is None:
                continue
            geo = transform(project.transform, shape(json.loads(geometry.ExportToJson()))).intersection(bounds)
            if geo.is_empty:
                continue
            for line in getattr(geo, "geoms", [geo]):
                if line.geom_type == "LineString":
                    lines.append(line)
    return lines


def _chunk_line(line: LineString, max_len: float) -> list[LineString]:
    count = max(1, int(np.ceil(line.length / max_len)))
    return [
        LineString([line.interpolate(i / count, normalized=True), line.interpolate((i + 1) / count, normalized=True)])
        for i in range(count)
    ]


def _water_normal(land: BaseGeometry, mid: Point, perpendicular: np.ndarray) -> np.ndarray | None:
    """Unit perpendicular on the water side, or None when both sides are land."""
    for sign in (1.0, -1.0):
        normal = perpendicular * sign
        probe = Point(mid.x + normal[0] * 40.0, mid.y + normal[1] * 40.0)
        if not land.covers(probe):
            return normal
    return None


def _chunk_tangent(segment: LineString) -> np.ndarray | None:
    """Unit direction along the segment around its midpoint, or None if degenerate."""
    q1 = segment.interpolate(max(0.0, segment.length / 2 - 25.0))
    q2 = segment.interpolate(min(segment.length, segment.length / 2 + 25.0))
    direction = np.array([q2.x - q1.x, q2.y - q1.y])
    length = np.linalg.norm(direction)
    if length < 1e-6:
        return None
    return direction / length


def _chunk_view(mid: Point, origin_e: float, origin_n: float) -> list[tuple[str, float]]:
    """Static camera presets covering the chunk.

    Returns (preset name, distance in m) pairs for each preset whose radius
    and view cone contain the chunk midpoint.
    """
    view: list[tuple[str, float]] = []
    for name, (vx, vz), yaw_deg in SHORE_FOAM_VIEWPOINTS:
        rel = np.array([mid.x - origin_e - vx, mid.y - origin_n - vz])
        dist = float(np.linalg.norm(rel))
        if dist > SHORE_FOAM_VIEW_RADIUS_M:
            continue
        axis = np.array([np.sin(np.radians(yaw_deg)), np.cos(np.radians(yaw_deg))])
        if dist < 1.0 or float(rel @ axis) / dist >= np.cos(np.radians(SHORE_FOAM_VIEW_CONE_DEG)):
            view.append((name, dist))
    return view


def _shore_foam_candidates(
    land: BaseGeometry, coastline: list[LineString], origin_e: float, origin_n: float
) -> list[tuple[int, int, LineString, Point, np.ndarray, list[tuple[str, float]]]]:
    """Qualifying chunks: open-sea water side, offshore half-plane, preset coverage."""
    south = np.array([0.0, -1.0])
    candidates = []
    for line_index, line in enumerate(coastline):
        for chunk_index, segment in enumerate(_chunk_line(line, SHORE_FOAM_SEGMENT_M)):
            mid = segment.interpolate(segment.length / 2)
            tangent = _chunk_tangent(segment)
            if tangent is None:
                continue
            water = _water_normal(land, mid, np.array([-tangent[1], tangent[0]]))
            if water is None:
                continue
            # start the probe off the shoreline: the chunk midpoint lies on the
            # land boundary, so a ray from there would always "hit" land.
            probe = Point(mid.x + water[0] * 40.0, mid.y + water[1] * 40.0)
            ray = LineString([
                (probe.x, probe.y),
                (probe.x + water[0] * SHORE_FOAM_OPEN_PROBE_M, probe.y + water[1] * SHORE_FOAM_OPEN_PROBE_M),
            ])
            if not ray.intersection(land).is_empty:
                continue  # sheltered: opposite shore or breakwater within the probe
            if float(water @ south) < SHORE_FOAM_OFFSHORE_DOT:
                continue  # bay/estuary interior (water not on the open-sea side)
            view = _chunk_view(mid, origin_e, origin_n)
            if not view:
                continue
            candidates.append((line_index, chunk_index, segment, mid, water, view))
    return candidates


def _pick_shore_cluster(
    candidates: list[tuple[int, int, LineString, Point, np.ndarray, list[tuple[str, float]]]],
) -> list[tuple[int, int, LineString, Point, np.ndarray, list[tuple[str, float]]]]:
    """Contiguous qualifying run whose water most camera presets cover; capped."""
    by_line: dict[int, list[tuple[int, int, LineString, Point, np.ndarray, list[tuple[str, float]]]]] = {}
    for row in candidates:
        by_line.setdefault(row[0], []).append(row)
    best: tuple[tuple[int, float], list] | None = None
    for rows in by_line.values():
        rows.sort(key=lambda r: r[1])
        clusters, cluster = [], [rows[0]]
        for row in rows[1:]:
            if cluster[-1][3].distance(row[3]) <= SHORE_FOAM_CLUSTER_GAP_M:
                cluster.append(row)
            else:
                clusters.append(cluster)
                cluster = [row]
        clusters.append(cluster)
        for members in clusters:
            viewpoints = {name for row in members for name, _ in row[5]}
            score = (len(viewpoints), -min(dist for row in members for _, dist in row[5]))
            if best is None or score > best[0]:
                best = (score, members)
    if best is None:
        return []
    return sorted(best[1], key=lambda r: min(d for _, d in r[5]))[:SHORE_FOAM_MAX_DECALS]


def shore_foam_document(land: BaseGeometry, coastline: list[LineString], origin_e: float, origin_n: float) -> dict:
    """Shore-wave decal placement table (plan P0-C, 视觉修整、非实测).

    Quiet water is intentionally unplaced: a chunk qualifies only when its
    waterward ray clears land over the probe distance (excludes basins and
    coasts behind breakwaters) and the water side faces the offshore
    half-plane (due south — the open Yellow Sea side of this window).
    Selection then shrinks to at most SHORE_FOAM_MAX_DECALS chunks of the
    best-covered cluster near the static camera presets (self-declared
    fallback: everything else, including all Jiaozhou-bay/port waters, stays
    unplaced). Decal local +X is landward (waves run up toward the shore).
    """
    chosen = _pick_shore_cluster(_shore_foam_candidates(land, coastline, origin_e, origin_n))
    decals = []
    for _, _, segment, mid, water, _ in chosen:
        landward = -water
        # Unity Euler(0, yaw, 0) maps local +X to (cos yaw, 0, -sin yaw); solving
        # that for the landward direction gives yaw = atan2(-north, east).
        yaw = float(np.degrees(np.arctan2(-landward[1], landward[0])))
        decals.append({
            "x": round(mid.x - origin_e, 1),
            "z": round(mid.y - origin_n, 1),
            "yaw_deg": round(yaw, 1),
            "size_x": SHORE_FOAM_CROSS_SHORE_M,
            "size_z": round(float(segment.length), 1),
        })
    if decals:
        xs = [d["x"] - d["size_x"] / 2.0 for d in decals] + [d["x"] + d["size_x"] / 2.0 for d in decals]
        zs = [d["z"] - d["size_z"] / 2.0 for d in decals] + [d["z"] + d["size_z"] / 2.0 for d in decals]
        region = max(max(xs) - min(xs), max(zs) - min(zs)) + 2 * SHORE_FOAM_MARGIN_M
        anchor = ((max(xs) + min(xs)) / 2.0, (max(zs) + min(zs)) / 2.0)
        region = float(np.ceil(region / 128.0) * 128.0)
    else:
        region, anchor = 0.0, (0.0, 0.0)
    return {
        "schema": "qingdao-shorefoam.v1",
        "crs": "EPSG:32651",
        "origin_e": origin_e,
        "origin_n": origin_n,
        "assumption": "视觉修整、非实测",
        "note": "2-3 open-sea shore segments near the static camera presets; quiet "
                "harbour/bay water is intentionally unplaced (self-declared fallback); "
                "foam look is unverified on the remote player",
        "anchor_x": round(anchor[0], 1),
        "anchor_z": round(anchor[1], 1),
        "region_size_m": region,
        "decals": decals,
    }


def main() -> None:  # noqa: PLR0915
    """Build the small runtime dataset from independently retained source files."""
    gdal.UseExceptions()
    ogr.UseExceptions()
    OUT.mkdir(parents=True, exist_ok=True)
    UNITY.mkdir(parents=True, exist_ok=True)
    project, origin_e, origin_n, extent, bounds = scene_frame()
    cells = enc_cells()
    lands, depths = [], []
    for path in cells:
        ds = open_cell(path)
        for layer_name in ("LNDARE", "DEPARE"):
            layer = ds.GetLayerByName(layer_name)
            for feature in layer:
                geometry = feature.GetGeometryRef()
                if geometry is None:
                    continue
                geo = transform(project.transform, shape(json.loads(geometry.ExportToJson())))
                geo = geo.intersection(bounds)
                if geo.is_empty:
                    continue
                if layer_name == "LNDARE":
                    lands.append(geo)
                else:
                    depth = feature.GetField("DRVAL1")
                    depths.append(
                        {"type": "Feature", "geometry": mapping(geo.simplify(3)), "properties": {"depth_m": depth}}
                    )
    land = unary_union(lands).buffer(0)
    chart = {
        "type": "FeatureCollection",
        "features": [*depths, {"type": "Feature", "geometry": mapping(land.simplify(2)), "properties": {"kind": "land"}}],
    }
    (OUT / "chart.json").write_text(json.dumps(chart, separators=(",", ":")))
    figure = Figure(figsize=(10, 10), dpi=128)
    figure.set_facecolor("#8ebbc5")
    FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    axis.set_facecolor("#8ebbc5")
    _draw_geometry(axis, land.buffer(35), "#9ca68a")
    _draw_geometry(axis, land, "#69745f")
    axis.set_xlim(bounds.bounds[0], bounds.bounds[2])
    axis.set_ylim(bounds.bounds[1], bounds.bounds[3])
    axis.set_aspect("equal")
    axis.axis("off")
    figure.subplots_adjust(0, 0, 1, 1)
    figure.savefig(OUT / "chart.png", pad_inches=0)

    region = {
        "scene_id": "qingdao",
        "crs": "EPSG:32651",
        "origin_e": origin_e,
        "origin_n": origin_n,
        "size_m": extent,
        "longitude": 120.295,
        "latitude": 36.045,
        "source": "Qingdao Port S-57: CN436122, CN436123, CN436134",
    }
    (OUT / "region.json").write_text(json.dumps(region, indent=2) + "\n")
    mask_document = land_mask_document(land, origin_e, origin_n)
    (UNITY / "land-mask.json").write_text(json.dumps(mask_document, separators=(",", ":")))

    # GLO-30 is a DSM, not a surveyed bare-earth model. ENC supplies the seafloor.
    tiles = [WORK / "N35E120.tif", WORK / "N36E120.tif"]
    resolution = 1025
    step = extent / (resolution - 1)
    xmin, ymin, xmax, ymax = bounds.bounds
    raster = gdal.Warp(
        "",
        [str(p) for p in tiles],
        format="MEM",
        dstSRS="EPSG:32651",
        outputBounds=[xmin - step / 2, ymin - step / 2, xmax + step / 2, ymax + step / 2],
        width=resolution,
        height=resolution,
        resampleAlg="bilinear",
    )
    heights = raster.ReadAsArray()
    if not np.isfinite(heights).all() or heights.min() <= -100:
        raise ValueError("DEM gaps are not accepted")
    vectors = ogr.GetDriverByName("Memory").CreateDataSource("")
    layer = vectors.CreateLayer("land", geom_type=ogr.wkbMultiPolygon)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(ogr.CreateGeometryFromJson(json.dumps(mapping(land))))
    layer.CreateFeature(feature)
    mask = gdal.GetDriverByName("MEM").Create("", resolution, resolution, 1, gdal.GDT_Byte)
    mask.SetGeoTransform(raster.GetGeoTransform())
    mask.SetProjection(raster.GetProjection())
    gdal.RasterizeLayer(mask, [1], layer, burn_values=[1])
    is_land = mask.ReadAsArray().astype(bool)

    bathy = read_enc_bathymetry()
    spikes = flag_sounding_spikes(bathy["soundings"])
    tri, nodes = build_constrained_tin(np.vstack([bathy["soundings"][~spikes], bathy["contours"], bathy["shoreline"]]))
    axis_m = np.arange(resolution) * step
    grid_e, grid_n = np.meshgrid(xmin + axis_m, ymax - axis_m)
    floor = sample_tin(tri, nodes, np.column_stack([grid_e.ravel(), grid_n.ravel()]))
    floor = nearest_hold(floor.reshape(resolution, resolution))
    floor, clamped = clamp_depth_areas(floor, bathy["depare"], raster.GetGeoTransform(), is_land)
    heights[~is_land] = floor[~is_land]  # display-grade ENC seafloor, never navigation depth
    heights[is_land] = np.maximum(heights[is_land], 1)
    base, vertical_range = -64.0, 256.0
    raw = np.flipud(np.rint((heights - base) / vertical_range * 65535).astype("<u2"))
    raw.tofile(UNITY / "heights.bytes")
    water_depth = np.where(is_land, 0.0, np.clip(-floor, 0.0, DEPTH_RANGE_M))
    np.flipud(np.rint(water_depth / DEPTH_RANGE_M * 65535).astype("<u2")).tofile(UNITY / "depths.bytes")

    works = read_shoreworks()
    lines = sum(1 for work in works if work["kind"] == "line")
    areas = sum(1 for work in works if work["kind"] == "area")
    (UNITY / "shoreworks.json").write_text(json.dumps(
        {
            "schema": "qingdao-shoreworks.v1",
            "crs": "EPSG:32651",
            "origin_e": origin_e,
            "origin_n": origin_n,
            "assumption": "视觉修整、非实测",
            "note": "width and height are type-based assumptions (plan D1=A); "
                    "LNDELV/TOPMAR/HEIGHT are unset on these cells; display only, never navigation",
            "features": works,
        },
        separators=(",", ":"),
    ))

    shore_foam = shore_foam_document(land, read_coastline(), origin_e, origin_n)
    (UNITY / "shorefoam.json").write_text(json.dumps(shore_foam, separators=(",", ":")))

    manifest = {
        "schema": "qingdao-terrain.v1",
        "longitude": 120.2949968072661,
        "latitude": 36.04500104524274,
        "cesium_scale": 1.000328760649243,
        "cesium_yaw": 1.5924629537512613,
        "sea_correction": [
            4.396238379993443e-8,
            -3.6678826103347887e-9,
            7.825015164862066e-8,
            1.915490348030886e-11,
            7.859444311115284e-8,
        ],
        "resolution": resolution,
        "origin_e": origin_e,
        "origin_n": origin_n,
        "size_m": extent,
        "base_y": base,
        "range_y": vertical_range,
        "min_height_m": float(heights.min()),
        "max_height_m": float(heights.max()),
        "crs": "EPSG:32651",
        "source_resolution_m": 30,
        "water_floor": {
            "source": "ENC S-57 SOUNDG + DEPCNT (VALDCO 0/2/5/10/20/30/50 m) + COALNE 0 m, "
                      "constrained TIN sampled onto this 1025² grid; cells CN436122/CN436123/CN436134",
            "vertical_datum": "ENC DSPM_VDAT=3 = mean sea level (DSPM_DUNI=1 metres) vs GLO-30 EGM2008; "
                              "the display zero plane treats the two as equal without a measured offset",
            "coverage": "sea cells beyond the ENC triangulation hold the nearest ENC edge value; "
                        "no GEBCO outer tail in this bake",
            "quality": "chart-generalised display interpolation (ZOC B: depth ±1 m + 2%, horizontal ±50 m); "
                       "never navigation depth",
            "spikes_removed": int(spikes.sum()),
            "depare_cells_clamped": clamped["cells_clamped"],
        },
        "depth_grid": {
            "file": "depths.bytes",
            "base_m": 0.0,
            "range_m": DEPTH_RANGE_M,
            "value": "positive-down water depth in metres, uint16 flipped like heights.bytes; "
                     "land and drying cells are 0",
        },
        "shoreworks": {
            "file": "shoreworks.json",
            "lines": lines,
            "areas": areas,
            "assumption": "视觉修整、非实测",
        },
        "shore_foam": {
            "file": "shorefoam.json",
            "decals": len(shore_foam["decals"]),
            "region_size_m": shore_foam["region_size_m"],
            "assumption": "视觉修整、非实测",
            "note": "open-sea COALNE chunks near the static camera presets only; "
                    "quiet harbour/bay water intentionally unplaced; foam look unverified",
        },
        "sources": [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in tiles + cells],
        "credits": "Copernicus DEM GLO-30 (DSM), accessed 2026-10-16 via AWS Open Data; "
                   "https://registry.opendata.aws/copernicus-dem/; "
                   "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018; "
                   "provided under COPERNICUS by the European Union and ESA; all rights reserved.",
    }
    if manifest["max_height_m"] >= base + vertical_range:
        raise ValueError("DEM exceeds the encoded height range")
    (UNITY / "terrain.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Baked {len(depths)} depth areas, {resolution}² DSM: {heights.min():.1f}..{heights.max():.1f}m; "
        f"seafloor TIN {int((~spikes).sum())}/{len(spikes)} soundings, bands {bathy['contour_bands']}, "
        f"DRVAL clamped {clamped['cells_clamped']} cells; shoreworks {lines} lines + {areas} areas"
    )


if __name__ == "__main__":
    main()
