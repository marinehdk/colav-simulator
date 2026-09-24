"""Capture-side writers for sealed replay chart artifacts."""

from __future__ import annotations

import gzip
import json
import logging
import math
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from shapely.geometry import Point

from colav_simulator.common import map_functions as mapf
from colav_simulator.experiment.persistence import jsonable
from gui_server.replay import (
    NAVIGATION_PROFILE_FILENAME,
    NAVIGATION_PROFILE_SCHEMA,
    STATIC_CONTEXT_FILENAME,
    STATIC_CONTEXT_SCHEMA,
)

if TYPE_CHECKING:
    from colav_simulator.experiment.runner import PreparedRun


log = logging.getLogger(__name__)


def _enc_depth_bin_at(enc: Any, *, east: float, north: float) -> float | None:
    """Return the deepest charted minimum-depth bin covering a UTM position."""
    point = Point(float(east), float(north))
    for depth in sorted(enc.seabed, key=float, reverse=True):
        geometry = enc.seabed[depth].geometry
        if geometry is not None and not geometry.is_empty and geometry.covers(point):
            return float(depth)
    return None


def persist_navigation_profile(run_dir: Path, enc: Any, enc_hash: str) -> Path:
    """Derive a depth bin for each sealed ownship frame using its exact ENC."""
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / 'manifest.json').read_text(encoding='utf-8'))
    index = json.loads((run_dir / 'decision' / 'index.json').read_text(encoding='utf-8'))
    if not enc_hash or manifest.get('enc_hash') != enc_hash or not index.get('frames_sha256'):
        raise ValueError('Replay ENC or trace identity mismatch')
    frames_path = run_dir / 'decision' / 'frames.jsonl.gz'
    if not frames_path.is_file():
        frames_path = run_dir / 'decision' / 'frames.jsonl'
    opener = gzip.open if frames_path.suffix == '.gz' else open
    samples = []
    with opener(frames_path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            frame = json.loads(line)
            state = (frame.get('payload', {}).get('Ship0') or {}).get('state') or []
            depth = None
            if len(state) >= 2 and all(isinstance(value, (int, float)) and math.isfinite(value) for value in state[:2]):
                depth = _enc_depth_bin_at(enc, north=state[0], east=state[1])
            samples.append([frame['sequence'], depth])
    if len(samples) != index.get('tick_count'):
        raise ValueError('Replay depth profile does not cover the sealed trace')
    document = {
        'schema_version': NAVIGATION_PROFILE_SCHEMA,
        'run_id': run_dir.name,
        'enc_hash': enc_hash,
        'frames_sha256': index['frames_sha256'],
        'source': 'ENC_MATCHED_DERIVED',
        'samples': samples,
    }
    path = run_dir / NAVIGATION_PROFILE_FILENAME
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    temporary.write_text(json.dumps(document, separators=(',', ':')), encoding='utf-8')
    os.replace(temporary, path)
    return path


def ensure_navigation_profile(run_dir: Path) -> Path:
    """Backfill an older sealed Run only from its unchanged local ENC source."""
    from colav_simulator.common import paths  # noqa: PLC0415
    from colav_simulator.experiment.runner import _enc_hash  # noqa: PLC0415
    from colav_simulator.scenario_config import ScenarioConfig  # noqa: PLC0415
    from colav_simulator.scenario_generator import ScenarioGenerator  # noqa: PLC0415

    run_dir = Path(run_dir)
    path = run_dir / NAVIGATION_PROFILE_FILENAME
    manifest = json.loads((run_dir / 'manifest.json').read_text(encoding='utf-8'))
    index = json.loads((run_dir / 'decision' / 'index.json').read_text(encoding='utf-8'))
    if path.is_file():
        document = json.loads(path.read_text(encoding='utf-8'))
        if (document.get('enc_hash') == manifest.get('enc_hash')
                and document.get('frames_sha256') == index.get('frames_sha256')
                and document.get('schema_version') == NAVIGATION_PROFILE_SCHEMA
                and document.get('run_id') == run_dir.name
                and len(document.get('samples', [])) == index.get('tick_count')):
            return path
    episode = json.loads((run_dir / 'episode.json').read_text(encoding='utf-8'))
    raw = episode['config']
    sources = tuple(raw['map_data_files'])
    enc_root = paths.enc_data.resolve()
    if not sources or any(not Path(source).resolve().is_relative_to(enc_root) for source in sources):
        raise ValueError('Replay ENC source is outside the configured chart directory')
    # Bypass the runner's path-only cache: chart files may change after the
    # original Run, and a stale digest must never qualify derived depth.
    actual_hash = _enc_hash.__wrapped__(sources)
    if actual_hash != manifest.get('enc_hash'):
        raise ValueError('Replay ENC source has changed since capture')
    config = ScenarioConfig.from_dict({key: value for key, value in raw.items() if value is not None})
    enc = ScenarioGenerator(seed=episode.get('seed'))._configure_enc(config)
    return persist_navigation_profile(run_dir, enc, actual_hash)


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
