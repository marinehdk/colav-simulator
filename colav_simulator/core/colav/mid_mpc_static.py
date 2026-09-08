"""ENC geometry compilation and original-source evidence for Mid-MPC."""

from __future__ import annotations

import base64
import hashlib
import math
from functools import lru_cache

import numpy as np
import shapely
from shapely.geometry.base import BaseGeometry

from colav_simulator.common.map_functions import GroundingHazardSet, extract_typed_grounding_hazards
from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput
from colav_simulator.core.colav.mid_mpc.models import MidMpcStaticField

STATIC_HULL_CLEARANCE_M = 1.0
_GRID_SPACING_M = 20.0


def static_execution_context(planner_input: PlannerInput) -> dict:
    """Freeze original chart evidence for L4 to check independently."""
    hazards = static_hazards(planner_input)
    return {
        "static_context_required": hazards is not None,
        "static_geometry_wkb_hex": None if hazards is None else hazards.combined_geometry.wkb_hex,
        "static_start_ne_m": tuple(map(float, planner_input.ownship_state[:2])),
        "static_layer_status": ()
        if hazards is None
        else tuple((layer.layer_id, layer.source_status) for layer in hazards.layers),
    }


def static_hazards(planner_input: PlannerInput) -> GroundingHazardSet | None:
    """Use typed chart hazards, rejecting insufficient depth data explicitly."""
    enc = planner_input.enc
    if enc is None:
        return None
    try:
        bins = sorted(depth for depth in enc.seabed if float(depth) >= planner_input.ownship_draft_m)
        if not bins:
            raise ValueError("ENC has no depth bin adequate for ownship draft")
        return extract_typed_grounding_hazards(bins[0], enc)
    except (AttributeError, KeyError, TypeError) as exc:
        raise ValueError("ENC static hazard geometry is unavailable") from exc


def compile_static_field(planner_input: PlannerInput) -> MidMpcStaticField | None:
    """Compile one chart-wide field reused throughout the vessel's voyage."""
    hazards = static_hazards(planner_input)
    if hazards is None:
        return None
    geometry = hazards.combined_geometry
    if not geometry.is_valid:
        raise ValueError("ENC static hazard geometry is invalid")
    if geometry.is_empty:
        return None
    radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    east_min, north_min, east_max, north_max = geometry.bounds
    bounds = (
        (math.floor(east_min / _GRID_SPACING_M) - 1) * _GRID_SPACING_M,
        (math.floor(north_min / _GRID_SPACING_M) - 1) * _GRID_SPACING_M,
        (math.ceil(east_max / _GRID_SPACING_M) + 1) * _GRID_SPACING_M,
        (math.ceil(north_max / _GRID_SPACING_M) + 1) * _GRID_SPACING_M,
    )
    nodes = ((bounds[2] - bounds[0]) / _GRID_SPACING_M + 1) * ((bounds[3] - bounds[1]) / _GRID_SPACING_M + 1)
    if nodes > 1_000_000:
        raise ValueError("ENC static field exceeds one million grid nodes; use a bounded chart region")
    return _distance_field(
        geometry.wkb,
        bounds,
        radius,
        tuple((layer.layer_id, layer.source_status) for layer in hazards.layers),
    )


@lru_cache(maxsize=4)
def _distance_field(
    wkb: bytes,
    bounds: tuple[float, ...],
    radius: float,
    layer_status: tuple[tuple[str, str], ...],
) -> MidMpcStaticField:
    geometry = shapely.from_wkb(wkb)
    east_min, north_min, east_max, north_max = bounds
    north = np.arange(north_min, north_max + 0.5 * _GRID_SPACING_M, _GRID_SPACING_M)
    east = np.arange(east_min, east_max + 0.5 * _GRID_SPACING_M, _GRID_SPACING_M)
    nn, ee = np.meshgrid(north, east, indexing="ij")
    points = shapely.points(ee.ravel(order="F"), nn.ravel(order="F"))
    # Index individual boundary segments. Full-chart distance calls scan every
    # shoreline vertex for every grid point; indexed segments retain exactness.
    tree = shapely.STRtree(_distance_primitives(geometry))
    indices, nearest = tree.query_nearest(points, return_distance=True, all_matches=False)
    distances = np.empty(len(points))
    distances[indices[0]] = nearest
    area = shapely.union_all([part for part in shapely.get_parts(geometry) if part.geom_type in {"Polygon", "MultiPolygon"}])
    shapely.prepare(area)
    interior = shapely.contains(area, points)
    # Point/line reef features have no interior; their ordinary distance still
    # admits the same Lipschitz interpolation and swept-segment lower bounds.
    if np.any(interior):
        distances[interior] *= -1.0
    return MidMpcStaticField(
        north_min_m=north_min,
        east_min_m=east_min,
        spacing_m=_GRID_SPACING_M,
        north_count=len(north),
        east_count=len(east),
        distance_f64le_b64=base64.b64encode(np.asarray(distances, dtype="<f8").tobytes()).decode("ascii"),
        hull_radius_m=radius,
        clearance_m=STATIC_HULL_CLEARANCE_M,
        source_hash=hashlib.sha256(wkb).hexdigest(),
        layer_status=layer_status,
    )


def _distance_primitives(geometry: BaseGeometry) -> list[BaseGeometry]:
    """Boundary segments and isolated features of an already-unioned hazard."""
    if geometry.geom_type == "Polygon":
        rings = (geometry.exterior, *geometry.interiors)
        return [segment for ring in rings for segment in _distance_primitives(ring)]
    if geometry.geom_type in {"LineString", "LinearRing"}:
        coordinates = np.asarray(geometry.coords)[:, :2]
        return list(shapely.linestrings(np.stack((coordinates[:-1], coordinates[1:]), axis=1)))
    if geometry.geom_type == "Point":
        return [geometry]
    return [part for child in geometry.geoms for part in _distance_primitives(child)]
