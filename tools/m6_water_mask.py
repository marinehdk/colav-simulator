#!/usr/bin/env python3
"""Bake the M6 scene water/terrain mask into sango/Assets/Scripts/Runtime/Vessels/Twin/M6WaterMask.cs.

P3-12 twin-scene georeferencing (#91): geo_fit coverage classification needs a
runtime-queryable water mask of the M6 strait scene without loading DEM RAWs
into the player. This tool reads tmp/m6-data/manifest.json (EPSG:32648, center
= Unity scene origin) and the per-tile u16 RAW heightmaps, samples elevation at
each mask cell center, and emits a run-length-encoded 2-bit grid:

    cell value: 0 = outside terrain coverage, 1 = land (elev >= 0), 2 = water (elev < 0)

Tile paint order = far band first, near band second: far tiles overlapping the
near band are SetActive(false) in the built scene (M6StraitSceneBootstrapper
coverage-semantics ruling), so near-band data wins wherever both exist — same
as the rendered terrain.

Usage:
    python3 tools/m6_water_mask.py            # write M6WaterMask.cs
    python3 tools/m6_water_mask.py --verify   # print elevation/mask at known points, no write

The generator is the provenance for the baked constant; re-run after any M6
terrain pipeline refresh (tools/terrain/m6_pipeline.sh).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "tmp/m6-data/manifest.json"
OUT = REPO / "sango/Assets/Scripts/Runtime/Vessels/Twin/M6WaterMask.cs"

STEP_M = 200          # mask cell size (coastline fidelity vs source weight)
EXTENT_M = 30000      # manifest far extent = +/-30 km around scene origin
COUNT = (2 * EXTENT_M) // STEP_M  # 300 cells per axis


def load_tiles() -> list[tuple[float, float, float, float, np.ndarray]]:
    manifest = json.loads(MANIFEST.read_text())
    cx, cy = manifest["center_utm"]
    tiles = []
    for band_key in ("far", "near"):  # far first, near overwrites (hidden far under near)
        band = manifest[band_key]
        for tile in band["tiles"]:
            raw = np.fromfile(REPO / tile["path_raw"], dtype="<u2")
            raw = raw.reshape(band["tile_px"], band["tile_px"])
            elev = band["elev_min"] + raw.astype(np.float64) * (
                band["elev_max"] - band["elev_min"]) / 65535.0
            x0, y0, x1, y1 = tile["utm_bounds"]
            tiles.append((x0 - cx, y0 - cy, x1 - cx, y1 - cy, elev))
    return tiles


def bake(tiles) -> np.ndarray:
    grid = np.zeros((COUNT, COUNT), dtype=np.uint8)  # 0 = outside
    half = EXTENT_M
    for x0, y0, x1, y1, elev in tiles:
        xs = np.arange(-half + STEP_M / 2, half, STEP_M)
        zs = np.arange(-half + STEP_M / 2, half, STEP_M)
        ci = np.where((xs > x0) & (xs < x1))[0]
        rj = np.where((zs > y0) & (zs < y1))[0]
        if ci.size == 0 or rj.size == 0:
            continue
        h, w = elev.shape
        cs = np.clip(((xs[ci] - x0) / (x1 - x0) * (w - 1)).astype(int), 0, w - 1)
        rs = np.clip(((y1 - zs[rj]) / (y1 - y0) * (h - 1)).astype(int), 0, h - 1)
        sub = elev[np.ix_(rs, cs)]
        grid[np.ix_(rj, ci)] = np.where(sub < 0, 2, 1).astype(np.uint8)
    # zs ascending = row 0 is southernmost; the consumer contract (and the RAW
    # heightmap row order) is row 0 = northernmost — flip to match.
    return grid[::-1].copy()


def encode_rle(grid: np.ndarray) -> str:
    rows = []
    for row in grid:
        runs: list[str] = []
        value, count = int(row[0]), 1
        for v in row[1:]:
            v = int(v)
            if v == value:
                count += 1
            else:
                runs.append(f"{value}:{count}")
                value, count = v, 1
        runs.append(f"{value}:{count}")
        rows.append(",".join(runs))
    return ";".join(rows)


def verify(grid: np.ndarray) -> None:
    half = EXTENT_M
    points = {
        "scene origin (0,0) = region center, batch-1 landing (land)": (0, 0),
        "hero berth (-1500,-5000) (water)": (-1500, -5000),
        "twin landing (21000,-5000) (water, active far-ring tile x>=18km)": (21000, -5000),
        "landing + replay box NE corner (26000,2000) (water)": (26000, 2000),
        "Batam NW coast (~7000,-13000) (water/land coast mix)": (7000, -13000),
    }
    for name, (x, z) in points.items():
        c = int((x + half) // STEP_M)
        r = int((half - z) // STEP_M)
        v = int(grid[r, c]) if 0 <= r < COUNT and 0 <= c < COUNT else 0
        print(f"  {v}  {name}")
    water = int((grid == 2).sum()); land = int((grid == 1).sum())
    print(f"  cells: water={water} land={land} outside={COUNT*COUNT-water-land}")


def main() -> int:
    grid = bake(load_tiles())
    if "--verify" in sys.argv:
        verify(grid)
        return 0
    rle = encode_rle(grid)
    source = f'''// M6WaterMask — baked water/terrain mask of the M6 strait scene (P3-12, spec #91).
//
// GENERATED FILE — do not edit by hand; regenerate with:
//     python3 tools/m6_water_mask.py
// Provenance: tmp/m6-data/manifest.json (EPSG:32648, center_utm = scene origin,
// see M6TerrainPipeline.ManifestPath) + per-tile u16 RAW heightmaps, sampled at
// cell centers by tools/m6_water_mask.py. Tile paint order far->near mirrors the
// built scene (far tiles under the near band are inactive — coverage-semantics
// ruling in M6StraitSceneBootstrapper). Consumer: M6TwinGeo (geo_fit coverage
// classification for twin sessions); Demo path never touches this data.
namespace Sango
{{
    public static class M6WaterMask
    {{
        /// <summary>Cell size in meters (mask resolution).</summary>
        public const float StepM = {STEP_M}f;

        /// <summary>Mask west/south edge in scene meters (grid spans [-ExtentM, ExtentM) squared).</summary>
        public const float ExtentM = {EXTENT_M}f;

        /// <summary>Cells per axis (ExtentM*2 / StepM).</summary>
        public const int Count = {COUNT};

        /// <summary>Cell value vocabulary (M6TwinGeo.MaskCell).</summary>
        public const byte Outside = 0;
        public const byte Land = 1;
        public const byte Water = 2;

        /// <summary>RLE grid: rows top (north, +z) to bottom joined by ';', runs "value:count" joined by ','.
        /// Row 0 = northernmost cells (same row order as the RAW heightmaps).</summary>
        public const string RowsRle =
            "{rle}";

        /// <summary>Scene (x,z) meters -> cell value (0 outside / 1 land / 2 water).</summary>
        public static byte Sample(float x, float z)
        {{
            int col = (int)((x + ExtentM) / StepM);
            int row = (int)((ExtentM - z) / StepM);
            if (col < 0 || col >= Count || row < 0 || row >= Count) return Outside;
            int index = col; // walk this row's runs by column offset (each row holds Count cells)
            foreach (var run in RowsRle.Split(';')[row].Split(','))
            {{
                var parts = run.Split(':');
                int count = int.Parse(parts[1]);
                if (index < count) return byte.Parse(parts[0]);
                index -= count;
            }}
            return Outside; // malformed row (generator bug) degrades to outside, never to water
        }}
    }}
}}
'''
    OUT.write_text(source)
    print(f"wrote {OUT.name}: {len(rle)} RLE chars, {COUNT}x{COUNT} cells @{STEP_M} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
