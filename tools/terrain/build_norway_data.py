#!/usr/bin/env python3
"""Bake the current EPSG:25833 ENC surroundings from downloaded Kartverket data.

Run with a Python containing GDAL and numpy. Source rasters/vectors remain in tmp;
the manifest records their hashes. Water depths here are visual, never ENC soundings.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr

gdal.UseExceptions()
ogr.UseExceptions()
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tmp/norway-terrain/baked"
OUT.mkdir(parents=True, exist_ok=True)
overview = ROOT / "tmp/kartverket-norway-research/dtm25833-enc-domain-10m.tif"
near = ROOT / "tmp/norway-terrain/enc-near-2m.tif"
sources = [overview, near]
gmls = sorted((ROOT / "tmp/norway-terrain").glob("*-n50/*Arealdekke*.gml"))
assert len(gmls) == 3, "Alesund, Sula and Giske land-cover files are required"
X0, Y0, SIZE = 33000, 6950450, 18000
N, STEP = 6145, 18000 / 6144
BASE, RANGE = -80.0, 1000.0

dem = gdal.Warp("", [str(p) for p in sources], format="MEM", dstSRS="EPSG:25833",
                outputBounds=[X0-STEP/2, Y0-STEP/2, X0+SIZE+STEP/2, Y0+SIZE+STEP/2],
                width=N, height=N, resampleAlg="bilinear", outputType=gdal.GDT_Float32)
height = dem.ReadAsArray()
assert np.isfinite(height).all() and 600 < float(height.max()) < 900
cover = gdal.GetDriverByName("MEM").Create("", N, N, 1, gdal.GDT_Byte)
cover.SetGeoTransform(dem.GetGeoTransform())
cover.SetProjection(dem.GetProjection())
cover.GetRasterBand(1).Fill(0)
for path in gmls:
    vectors = ogr.Open(str(path))
    for name, value in [("Havflate", 3), ("Skog", 1), ("BymessigBebyggelse", 2),
                        ("Tettbebyggelse", 2), ("Industriområde", 2)]:
        layer = vectors.GetLayerByName(name)
        if layer is not None:
            layer.SetSpatialFilterRect(X0, Y0, X0+SIZE, Y0+SIZE)
            gdal.RasterizeLayer(cover, [1], layer, burn_values=[value])
classes = cover.ReadAsArray()
sea = (height <= 0) | ((classes == 3) & (height < 1))
# Underwater geometry is a tapered visual floor, explicitly not bathymetric truth.
land = gdal.GetDriverByName("MEM").Create("", N, N, 1, gdal.GDT_Byte)
land.SetGeoTransform(dem.GetGeoTransform())
land.GetRasterBand(1).WriteArray((~sea).astype(np.uint8))
distance = gdal.GetDriverByName("MEM").Create("", N, N, 1, gdal.GDT_Float32)
distance.SetGeoTransform(dem.GetGeoTransform())
gdal.ComputeProximity(land.GetRasterBand(1), distance.GetRasterBand(1), ["VALUES=1", "DISTUNITS=GEO"])
depth = np.minimum(distance.ReadAsArray() / 180, 1)
height[sea] = -80 * depth[sea]
classes[sea] = 3
assert BASE <= float(height.min()) and float(height.max()) < BASE+RANGE
encoded = np.rint((height-BASE) / RANGE * 65535).astype("<u2")
tiles = []
for row in range(3):
    for col in range(3):
        stride = 1  # Identical shared edge samples allow native Terrain neighbour stitching.
        crop = encoded[row*2048:row*2048+2049:stride, col*2048:col*2048+2049:stride]
        name = f"norway_r{row}c{col}"
        np.flipud(crop).tofile(OUT / f"{name}.raw")
        cover_crop = classes[row*2048:row*2048+2048:4, col*2048:col*2048+2048:4]
        np.flipud(cover_crop).tofile(OUT / f"{name}.cover")
        tiles.append({"name": name, "resolution": len(crop), "x": col*6000-9000,
                      "z": 3000-row*6000, "size": 6000, "baseY": BASE, "rangeY": RANGE})
# Shared vertices come from one grid even when adjacent tiles use different LODs.
for row in range(3):
    for col in range(2):
        a, b = tiles[row*3+col:row*3+col+2]
        aa = np.fromfile(OUT/f"{a['name']}.raw", dtype="<u2").reshape(a['resolution'], -1)[:, -1]
        bb = np.fromfile(OUT/f"{b['name']}.raw", dtype="<u2").reshape(b['resolution'], -1)[:, 0]
        assert np.array_equal(aa[::max(1,len(aa)//1024)], bb[::max(1,len(bb)//1024)])
manifest = {"crs": "EPSG:25833", "origin_e": 42000, "origin_n": 6959450,
            "row_order": "south_to_north", "height_range_m": [float(height.min()), float(height.max())],
            "height_datum": "Kartverket source vertical reference; visual sea level zero",
            "water_floor": "synthetic display floor, 0 to -80 m over 180 m; not navigation bathymetry",
            "source_resolutions_m": {"overview": 10, "enc_near": 2}, "tiles": tiles,
            "sources": [{"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                        for p in sources+gmls]}
(OUT/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
for east,north in [(39000,6957000),(40000,6958000),(39000,6959000)]:
    r,c = round((Y0+SIZE-north)/STEP),round((east-X0)/STEP)
    print("sample",east,north,round(float(height[r,c]),2),"land_cover",int(classes[r,c]))
print("baked",len(tiles),"tiles",manifest["height_range_m"],"sea_fraction",round(float(sea.mean()),3))

# Clip online landscape to actual N50 land. This excludes the providers' flat
# photographed sea and bounds tile streaming to the supported 18 km chart domain.
bounds = ogr.CreateGeometryFromWkt(
    f"POLYGON(({X0} {Y0},{X0+SIZE} {Y0},{X0+SIZE} {Y0+SIZE},{X0} {Y0+SIZE},{X0} {Y0}))")
sea_polygons = ogr.Geometry(ogr.wkbMultiPolygon)
for path in gmls:
    vectors = ogr.Open(str(path))
    layer = vectors.GetLayerByName("Havflate")
    layer.SetSpatialFilter(bounds)
    for feature in layer:
        clipped = feature.GetGeometryRef().Intersection(bounds)
        if clipped.GetGeometryName() == "POLYGON": sea_polygons.AddGeometry(clipped)
        elif clipped.GetGeometryName() == "MULTIPOLYGON":
            for polygon in clipped: sea_polygons.AddGeometry(polygon)
land = bounds.Difference(sea_polygons.UnionCascaded()).SimplifyPreserveTopology(4)
polygons = [land] if land.GetGeometryName() == "POLYGON" else list(land)
rings = [{"points": [{"x": round(x-42000,2), "y": round(y-6959450,2)}
                     for x,y,*_ in polygon.GetGeometryRef(0).GetPoints()[:-1]]}
         for polygon in polygons if polygon.GetArea() > 100]
mask = ROOT / "sango/Assets/Resources/NorwayLandMask.json"
mask.write_text(json.dumps({"source": "Kartverket N50 land outside Havflate; EPSG:25833; 4 m simplification",
                            "rings": rings}, separators=(",", ":"))+"\n")
print("land mask",len(rings),"polygons")
