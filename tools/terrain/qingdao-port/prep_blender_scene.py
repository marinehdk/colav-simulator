#!/usr/bin/env python3
"""Prep real-data assets for the Qianwan port Blender scene.

Inputs: Resources/Qingdao heights.bytes + shoreworks.json + land-mask.json,
Tianditu img_w tiles (z15, whole 18 km window).
Outputs (tools/terrain/qingdao-port/): terrain+quay OBJs (UTM-local metres,
Z up, UVs into the mosaic), qianwan_mosaic.png, placement.json (berth
transform + crane table), scene_data.npz.
"""
import json
import math
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from osgeo import osr
from PIL import Image
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[3]
Q = ROOT / "sango/Assets/Resources/Qingdao"
OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)
TDT = "a1cc795b4ba23ee7cdcad36c185c8d3f"
Z = 15

manifest = json.loads((Q / "terrain.json").read_text())
N = manifest["resolution"]  # 1025
SIZE = manifest["size_m"]
OE, ON = manifest["origin_e"], manifest["origin_n"]
raw = np.fromfile(Q / "heights.bytes", dtype="<u2").reshape(N, N)
h = manifest["base_y"] + raw.astype(np.float64) * (manifest["range_y"] / 65535.0)
# File rows run south->north (build_qingdao_static.py meshgrid+flipud; Unity
# SetHeights keeps row 0 south), columns west->east.
STEP = SIZE / (N - 1)
SUB = 4  # 1025 -> 257 samples (~70 m cells)
hs = h[::SUB, ::SUB]
ns = hs.shape[0]
xs = (np.arange(ns) * SUB) * STEP - SIZE / 2
ys = (np.arange(ns) * SUB) * STEP - SIZE / 2
XX, YY = np.meshgrid(xs, ys)

# --- Web Mercator tile math + UTM51N -> WGS84 -------------------------------
sr = osr.SpatialReference()
sr.ImportFromEPSG(32651)
sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tgt = osr.SpatialReference()
tgt.ImportFromEPSG(4326)
tgt.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(sr, tgt)


def to_latlon(east, north):
    lon, lat, _ = tr.TransformPoint(float(east), float(north))
    return lon, lat


def latlon_to_px(lon, lat, z):
    n = 1 << z
    x = (lon + 180.0) / 360.0 * n
    r = math.radians(lat)
    y = (1.0 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2.0 * n
    return x * 256.0, y * 256.0


corners = [
    to_latlon(OE - SIZE / 2, ON - SIZE / 2),
    to_latlon(OE + SIZE / 2, ON + SIZE / 2),
]
px0, py1 = latlon_to_px(*corners[0], Z)  # SW: min x, max y(px)
px1, py0 = latlon_to_px(*corners[1], Z)  # NE
min_px, max_px = int(px0 // 256) * 256, math.ceil(px1 / 256) * 256
min_py, max_py = int(py0 // 256) * 256, math.ceil(py1 / 256) * 256
W, H = max_px - min_px, max_py - min_py
cols = range(min_px // 256, max_px // 256)
rows = range(min_py // 256, max_py // 256)
print(f"mosaic {W}x{H}px, tiles {len(cols)}x{len(rows)}")


def fetch(tile):
    c, r = tile
    url = (
        f"https://t0.tianditu.gov.cn/img_w/wmts?tk={TDT}&request=GetTile&version=1.0.0"
        f"&service=WMTS&format=tiles&layer=img&style=default&tilematrixset=w"
        f"&tilematrix={Z}&tilerow={r}&tilecol={c}"
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = resp.read()
            img = Image.open(__import__("io").BytesIO(data)).convert("RGB")
            if img.size == (256, 256):
                return c, r, img
        except Exception:
            pass
    return c, r, None


mosaic_path = OUT / "qianwan_mosaic.png"
if mosaic_path.exists() and (OUT / "scene_data.npz").exists():
    print("mosaic cached, skipping fetch")
    mosaic = Image.open(mosaic_path)
else:
    tiles = list((c, r) for r in rows for c in cols)
    mosaic = Image.new("RGB", (W, H), (90, 110, 120))
    bad = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for c, r, img in ex.map(fetch, tiles):
            if img is None:
                bad += 1
                continue
            mosaic.paste(img, (c * 256 - min_px, r * 256 - min_py))
    print(f"tiles ok={len(tiles)-bad} bad={bad}")
    mosaic.save(mosaic_path)

# Per-sample UVs: image y=0 is north; v=0 is Blender image bottom.
gx = XX + OE
gy = YY + ON
uv = np.empty((ns, ns, 2))
for i in range(ns):
    for j in range(ns):
        lon, lat = to_latlon(gx[i, j], gy[i, j])
        px, py = latlon_to_px(lon, lat, Z)
        uv[i, j, 0] = (px - min_px) / W
        uv[i, j, 1] = 1.0 - (py - min_py) / H
np.savez(OUT / "scene_data.npz", height=hs, x=xs, y=ys, uv=uv)

# --- Quay volumes from the SLCONS bake (all wharf/re vetment features) ------
sw = json.loads((Q / "shoreworks.json").read_text())


def trimesh_export(features, name):
    faces_v, faces_f, faces_uv = [], [], []
    for f in features:
        ring = f.get("ring") or []
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid or poly.area < 200:
            continue
        top = float(f.get("height_m") or 6.0)
        base = top - float(f.get("width_m") or 10.0) * 0.8 - 4.0  # skirt into the bed
        n = len(ring)
        # walls
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            vs = [len(faces_v), len(faces_v) + 1, len(faces_v) + 2, len(faces_v) + 3]
            faces_v += [(a[0], a[1], top), (b[0], b[1], top), (b[0], b[1], base), (a[0], a[1], base)]
            faces_f.append((vs[0], vs[1], vs[2], vs[3]))
            for p in (a, b):
                lon, lat = to_latlon(p[0] + OE, p[1] + ON)
                px, py = latlon_to_px(lon, lat, Z)
                faces_uv.append(((px - min_px) / W, 1.0 - (py - min_py) / H))
        # top cap (fan)
        center = list(poly.centroid.coords[0])
        lon, lat = to_latlon(center[0] + OE, center[1] + ON)
        px, py = latlon_to_px(lon, lat, Z)
        faces_uv.append(((px - min_px) / W, 1.0 - (py - min_py) / H))
        ci = len(faces_v)
        faces_v.append((center[0], center[1], top))
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            faces_f.append((ci, len(faces_v), len(faces_v) + 1))
            faces_v += [(a[0], a[1], top), (b[0], b[1], top)]
            lon, lat = to_latlon(a[0] + OE, a[1] + ON)
            pa = latlon_to_px(lon, lat, Z)
            lon, lat = to_latlon(b[0] + OE, b[1] + ON)
            pb = latlon_to_px(lon, lat, Z)
            faces_uv.append(((pa[0] - min_px) / W, 1.0 - (pa[1] - min_py) / H))
            faces_uv.append(((pb[0] - min_px) / W, 1.0 - (pb[1] - min_py) / H))
    if not faces_v:
        return 0
    with open(OUT / f"{name}.obj", "w") as fh:
        for i, (v, t) in enumerate(zip(faces_v, [None] + faces_uv)):
            if i == 0:
                continue
        fh.write(f"mtllib {name}.mtl\nusemtl satellite\n")
        # interleave: v then vt is messy because walls wrote 4 verts/2 uv —
        # rebuild cleanly below instead.
    return len(faces_v)


# Simpler + correct OBJ writer (single pass, per-feature rebuild)
def export_obj(features, name):
    verts, uvs, faces = [], [], []
    for f in features:
        ring = f.get("ring") or []
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid or poly.area < 200:
            continue
        top = float(f.get("height_m") or 6.0)
        base = top - float(f.get("width_m") or 10.0) * 0.8 - 4.0
        pts = list(ring)
        n = len(pts)

        def uv_of(p):
            lon, lat = to_latlon(p[0] + OE, p[1] + ON)
            px, py = latlon_to_px(lon, lat, Z)
            return ((px - min_px) / W, 1.0 - (py - min_py) / H)

        ring_idx = []
        for p in pts:
            verts.append((p[0], p[1], top))
            uvs.append(uv_of(p))
            ring_idx.append(len(verts) - 1)
        for p in pts:  # second ring at base (own uv copy)
            verts.append((p[0], p[1], base))
            uvs.append(uv_of(p))
        for k in range(n):
            a0, b0 = ring_idx[k], ring_idx[(k + 1) % n]
            faces.append((a0 + 1, b0 + 1, b0 + n + 1, a0 + n + 1))
        cx, cy = list(poly.centroid.coords[0])
        verts.append((cx, cy, top))
        uvs.append(uv_of((cx, cy)))
        ci = len(verts)
        for k in range(n):
            faces.append((ci, ring_idx[k] + 1, ring_idx[(k + 1) % n] + 1))
    with open(OUT / f"{name}.obj", "w") as fh:
        fh.write(f"mtllib {name}.mtl\nusemtl satellite\n")
        for v in verts:
            fh.write(f"v {v[0]:.2f} {v[1]:.2f} {v[2]:.2f}\n")
        for t in uvs:
            fh.write(f"vt {t[0]:.6f} {t[1]:.6f}\n")
        for f in faces:
            fh.write("f " + " ".join(f"{a}/{a}" for a in f) + "\n")
    (OUT / f"{name}.mtl").write_text(
        f"newmtl satellite\nKa 1 1 1\nKd 1 1 1\nmap_Kd qianwan_mosaic.png\n"
    )
    return len(features)


quays = [f for f in sw["features"] if f["kind"] == "line" and f.get("type") == "wharf"]
revets = [f for f in sw["features"] if f["kind"] == "line" and f.get("type") != "wharf"]
areas = [f for f in sw["features"] if f["kind"] != "line"]
print("quays", export_obj(quays, "quays"), "| revets", export_obj(revets, "revets"),
      "| areas", export_obj(areas, "shore_areas"))

# --- Berth placement for the crane rig (spike params, real coords) ----------
lm = json.loads((Q / "land-mask.json").read_text())
land = [Polygon([(p["x"], p["y"]) for p in r["points"]]) for r in lm["rings"]]
land_u = land[0]
for p in land[1:]:
    land_u = land_u.union(p)


def is_land(x: float, y: float) -> bool:
    """Point-in-polygon test against the united land rings."""
    return land_u.contains(Point(x, y))


seg = [f for f in sw["features"] if f.get("id") == "CN436123-3739"][0]
ring = seg["ring"]
c = np.mean(ring, axis=0)
u, s, vt = np.linalg.svd(np.array(ring) - c, full_matrices=False)
axis, nrm = vt[0], vt[1]
side = (np.array(ring) - c) @ nrm
face = np.array(ring)[side < 0]
t = (face - c) @ axis
order = np.argsort(t)
face = face[order]
t = t[order]
mid_t = (t[0] + t[-1]) / 2
p0 = face[np.searchsorted(t, mid_t - 250)]
p1 = face[np.searchsorted(t, mid_t + 250)]
d = p1 - p0
L = float(np.hypot(*d))
yaw = math.degrees(math.atan2(d[0], d[1]))  # from +Y(north) toward +X(east)
# spike frame: berth along +X, water toward +Y. Water side test:
perp = np.array([-d[1], d[0]]) / L
probe = (p0 + p1) / 2 + perp * 30
water_left = not is_land(*probe)
json.dump(
    {"p0": p0.tolist(), "p1": p1.tolist(), "length": L, "yaw_deg": yaw,
     "water_left": water_left, "mid": ((p0 + p1) / 2).tolist()},
    open(OUT / "placement.json", "w"), indent=2)
print("berth:", p0.round(1).tolist(), p1.round(1).tolist(), f"L={L:.0f} yaw={yaw:.1f} water_left={water_left}")
print("done")
