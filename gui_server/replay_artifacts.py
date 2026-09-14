"""Capture-side writers for sealed replay chart artifacts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from colav_simulator.common import map_functions as mapf
from colav_simulator.experiment.persistence import jsonable
from gui_server.replay import STATIC_CONTEXT_FILENAME, STATIC_CONTEXT_SCHEMA

if TYPE_CHECKING:
    from colav_simulator.experiment.runner import PreparedRun


log = logging.getLogger(__name__)


def _draw_geometry(ax: Any, geometry: Any, color: str, alpha: float = 1.0) -> None:
    if geometry is None or geometry.is_empty:
        return
    polygons = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    for polygon in polygons:
        if not hasattr(polygon, "exterior"):
            continue
        xy = np.asarray(polygon.exterior.coords)
        ax.fill(xy[:, 0], xy[:, 1], color=color, alpha=alpha, linewidth=0)


def _local_polygon_coordinates(
    geometry: Any,
    origin_e: float,
    origin_n: float,
) -> list[list[list[list[float]]]]:
    """Serialize ENC polygons as local [north, east] rings for the Web canvas."""
    if geometry is None or geometry.is_empty:
        return []
    polygons = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    output = []
    for polygon in polygons:
        if not hasattr(polygon, "exterior"):
            continue
        rings = [polygon.exterior, *polygon.interiors]
        output.append(
            [
                [[float(north - origin_n), float(east - origin_e)] for east, north in ring.coords]
                for ring in rings
            ]
        )
    return output


def render_enc(prepared: PreparedRun) -> Path:
    """Render the exact ENC object used by one prepared simulation."""
    enc = prepared.session.enc
    width, height = enc.size
    figure_width = 8.0
    figure_height = max(3.0, figure_width * height / max(width, 1.0))
    figure = Figure(figsize=(figure_width, figure_height), dpi=128)
    FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    axis.set_facecolor("#9fc7cf")
    palette = {
        0: "#8ebbc5",
        1: "#99c5cb",
        2: "#a6cfd2",
        5: "#b6d9d7",
        10: "#c6e0da",
        20: "#d7e8df",
    }
    for depth in sorted(enc.seabed.keys(), reverse=True):
        _draw_geometry(axis, enc.seabed[depth].geometry, palette.get(depth, "#dceae3"))
    _draw_geometry(axis, enc.shore.geometry, "#9ca68a")
    _draw_geometry(axis, enc.land.geometry, "#69745f")
    e_min, n_min, e_max, n_max = enc.bbox
    axis.set_xlim(e_min, e_max)
    axis.set_ylim(n_min, n_max)
    axis.set_aspect("equal", adjustable="box")
    axis.axis("off")
    figure.subplots_adjust(0, 0, 1, 1)
    path = prepared.run_dir / "enc.png"
    figure.savefig(path, transparent=False, pad_inches=0)
    return path


def build_enc_navigation_area(prepared: PreparedRun | None) -> dict[str, Any]:
    """Freeze the safe-water projection derived from the prepared ENC."""
    if prepared is None or not prepared.session.ship_list:
        return {}
    session = prepared.session
    enc = session.enc
    origin_e, origin_n = enc.origin
    draft = float(session.ship_list[0].draft)
    minimum_depth = mapf.find_minimum_depth(draft, enc)
    safe_water = mapf.extract_safe_sea_area(
        minimum_depth,
        mapf.bbox_to_polygon(enc.bbox),
        enc,
        show_plots=False,
    )
    return {
        "schema_version": "1.0",
        "coordinate_frame": "local_north_east_m",
        "utm_zone": int(enc.utm_zone),
        "vessel_draft_m": draft,
        "minimum_depth_m": float(minimum_depth),
        "safe_water": {
            "type": "MultiPolygon",
            "polygons": _local_polygon_coordinates(safe_water, float(origin_e), float(origin_n)),
        },
    }


def persist_static_context(prepared: PreparedRun, enc_navigation_area: dict[str, Any]) -> None:
    """Persist immutable chart facts for the sealed replay read path."""
    try:
        enc = prepared.session.enc
        origin_e, origin_n = enc.origin
        document = {
            "schema_version": STATIC_CONTEXT_SCHEMA,
            "scenario_id": prepared.spec.scenario_id,
            "enc": {
                "origin_east_m": float(origin_e),
                "origin_north_m": float(origin_n),
                "width_m": float(enc.size[0]),
                "height_m": float(enc.size[1]),
                "utm_zone": int(enc.utm_zone),
            },
            "enc_navigation_area": jsonable(enc_navigation_area) or None,
            "ships": [
                {
                    "id": int(ship.id),
                    "mmsi": int(ship.mmsi),
                    "length_m": float(ship.length),
                    "width_m": float(ship.width),
                }
                for ship in prepared.session.ship_list
            ],
        }
        (prepared.run_dir / STATIC_CONTEXT_FILENAME).write_text(
            json.dumps(document),
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError, AttributeError):
        log.exception("Could not persist static replay context for run %s", prepared.manifest.run_id)
