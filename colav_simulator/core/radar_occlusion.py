"""Terrain line-of-sight occlusion for radar sensor models (P3-S1, spec #90).

Loads the M6 Singapore-strait DEM (GEBCO+GLO-30 merged, EPSG:32648 UTM 48N,
``tmp/m6-data/dem``) or any GeoTIFF elevation/landmask raster and answers one
question per antenna-target pair: is the direct line of sight interrupted by
terrain? Blocked targets yield no radar measurement (milliampere-ch5 §4.3,
repo-sensor-seams §1.1 "陆地遮挡：无" gap).

Two blocking rules:
- ``mode="elevation"``: 3-D sight line over the elevation raster with a 4/3
  effective-earth-radius bulge correction (standard radar-horizon geometry,
  d(km) = 4.12 (sqrt(h1[m]) + sqrt(h2[m]))).
- ``mode="landmask"``: binary rule — any land cell on the 2-D path blocks.

Rasters are read lazily once and block-max-pooled (preserves ridges) to keep
the resident backend footprint small. Out-of-raster samples are treated as
open water (no data = no block), so sensors outside the DEM footprint stay
unoccluded instead of failing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from shapely import contains_xy

#: Effective-earth-radius factor for standard atmospheric refraction (k = 4/3).
REFRACTION_K = 4.0 / 3.0

#: Mean earth radius [m].
EARTH_RADIUS_M = 6371000.0


def enc_land_grid(enc: Any) -> TerrainGrid | None:
    """Rasterize the authoritative ENC land in its own projected frame.

    Landmask is opaque; it does not claim measured terrain elevations. Coverage
    is limited to the ENC bbox and stays explicit in shadow video metadata.
    """
    geometry = getattr(getattr(enc, "land", None), "geometry", None)
    bbox = getattr(enc, "bbox", None)
    if geometry is None or bbox is None or len(bbox) != 4:
        return None
    xmin, ymin, xmax, ymax = map(float, bbox)
    if not np.isfinite([xmin, ymin, xmax, ymax]).all() or xmin >= xmax or ymin >= ymax:
        raise ValueError("invalid ENC radar land extent")
    cell_size = max(25.0, (xmax - xmin) / 1024, (ymax - ymin) / 1024)
    columns = int(np.ceil((xmax - xmin) / cell_size))
    rows = int(np.ceil((ymax - ymin) / cell_size))
    east, north = np.meshgrid(xmin + (np.arange(columns) + 0.5) * cell_size, ymax - (np.arange(rows) + 0.5) * cell_size)
    return TerrainGrid(contains_xy(geometry, east, north).astype(float), xmin, ymax, cell_size, mode="landmask")


class TerrainGrid:
    """Downsampled elevation/landmask raster with radar line-of-sight queries.

    Attributes:
        elevation: (rows, cols) array; meters for ``mode="elevation"``, 0/1 for
            ``mode="landmask"``.
        origin_e: Easting of the raster top-left corner [m].
        origin_n: Northing of the raster top-left corner [m].
        cell_size: Post-downsample cell size [m] (square cells).
        mode: Blocking rule selector, ``"elevation"`` or ``"landmask"``.
    """

    def __init__(
        self,
        elevation: np.ndarray,
        origin_e: float,
        origin_n: float,
        cell_size: float,
        mode: str = "elevation",
    ) -> None:
        if elevation.ndim != 2:
            msg = f"elevation must be a 2-D array, got shape {elevation.shape}"
            raise ValueError(msg)
        if cell_size <= 0.0:
            msg = f"cell_size must be positive, got {cell_size}"
            raise ValueError(msg)
        if mode not in {"elevation", "landmask"}:
            msg = f"mode must be 'elevation' or 'landmask', got {mode!r}"
            raise ValueError(msg)
        self.elevation: np.ndarray = np.asarray(elevation, dtype=np.float64)
        self.origin_e: float = float(origin_e)
        self.origin_n: float = float(origin_n)
        self.cell_size: float = float(cell_size)
        self.mode: str = mode

    @classmethod
    def from_geotiff(
        cls,
        path: str | Path,
        downsample: int = 1,
        mode: str = "elevation",
        sea_level: float = 0.0,
    ) -> TerrainGrid:
        """Reads a GeoTIFF raster via GDAL and block-max-pools it by ``downsample``.

        Args:
            path: Path to a single-band GeoTIFF in a projected metric CRS
                (the M6 strait DEM is EPSG:32648 UTM 48N).
            downsample: Integer pooling factor; block maximum preserves ridges.
            mode: ``"elevation"`` (3-D LOS) or ``"landmask"`` (values > sea_level
                count as land and block in 2-D).
            sea_level: Elevation threshold separating land from water in the
                source raster (both modes).

        Returns:
            TerrainGrid ready for occlusion queries.
        """
        from osgeo import gdal  # noqa: PLC0415 (optional heavy dependency, imported on demand)

        gdal.UseExceptions()
        dataset = gdal.Open(str(path))
        if dataset is None:
            msg = f"Cannot open DEM raster: {path}"
            raise ValueError(msg)
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        array = band.ReadAsArray().astype(np.float64)
        geotransform = dataset.GetGeoTransform()
        dataset = None
        if nodata is not None:
            array = np.where(np.isclose(array, nodata), sea_level, array)
        factor = max(1, int(downsample))
        if factor > 1:
            rows, cols = array.shape
            array = array[: rows // factor * factor, : cols // factor * factor]
            array = array.reshape(rows // factor, factor, cols // factor, factor).max(axis=(1, 3))
        return cls(
            elevation=array,
            origin_e=geotransform[0],
            origin_n=geotransform[3],
            cell_size=abs(geotransform[1]) * factor,
            mode=mode,
        )

    def sample(self, east: float, north: float) -> float:
        """Samples the raster at (east, north); outside the raster = open water (0.0)."""
        col = int((east - self.origin_e) // self.cell_size)
        row = int((self.origin_n - north) // self.cell_size)
        rows, cols = self.elevation.shape
        if row < 0 or row >= rows or col < 0 or col >= cols:
            return 0.0
        return float(self.elevation[row, col])

    def is_land(self, east: float, north: float, sea_level: float = 0.0) -> bool:
        """Checks whether the sampled cell is land under the selected blocking rule."""
        return self.sample(east, north) > sea_level

    def line_of_sight_blocked(
        self,
        antenna_e: float,
        antenna_n: float,
        target_e: float,
        target_n: float,
        antenna_height_m: float,
        target_height_m: float,
        sea_level: float = 0.0,
    ) -> bool:
        """Determines whether terrain interrupts the antenna→target sight line.

        Marches the 2-D path at the raster cell size. For ``mode="elevation"``
        each interior sample compares terrain elevation against the sight line
        height including the k-factor earth-bulge term
        ``s (1-s) D^2 / (2 k R_earth)``. For ``mode="landmask"`` any land cell
        on the path blocks. The antenna and target endpoints are excluded so
        ownship/target cells cannot self-occlude.

        Args:
            antenna_e: Antenna easting [m].
            antenna_n: Antenna northing [m].
            target_e: Target easting [m].
            target_n: Target northing [m].
            antenna_height_m: Antenna height above the waterline [m].
            target_height_m: Target scattering-center height above waterline [m].
            sea_level: Land/water threshold of the source raster.

        Returns:
            True when the sight line is blocked by terrain.
        """
        delta_e = target_e - antenna_e
        delta_n = target_n - antenna_n
        distance = float(np.hypot(delta_e, delta_n))
        if distance <= self.cell_size:
            return False
        if self.mode == "landmask":
            steps = max(2, int(np.ceil(distance / self.cell_size)))
            fractions = np.linspace(0.0, 1.0, steps + 1)[1:-1]
            easts = antenna_e + fractions * delta_e
            norths = antenna_n + fractions * delta_n
            for east, north in zip(easts, norths, strict=True):
                if self.is_land(east, north, sea_level):
                    return True
            return False

        effective_radius = REFRACTION_K * EARTH_RADIUS_M
        bulge = distance**2 / (2.0 * effective_radius)
        steps = max(2, int(np.ceil(distance / self.cell_size)))
        fractions = np.linspace(0.0, 1.0, steps + 1)[1:-1]
        easts = antenna_e + fractions * delta_e
        norths = antenna_n + fractions * delta_n
        sight_heights = (
            antenna_height_m + (target_height_m - antenna_height_m) * fractions + bulge * fractions * (1.0 - fractions)
        )
        for east, north, sight_height in zip(easts, norths, sight_heights, strict=True):
            if self.sample(east, north) > sight_height + sea_level:
                return True
        return False


def load_occlusion_grid(
    dem_path: str | Path | None,
    downsample: int = 4,
    mode: str = "elevation",
    cache: dict[str, TerrainGrid] | None = None,
) -> TerrainGrid | None:
    """Loads (and caches) a TerrainGrid; returns None when no DEM is configured/available.

    Args:
        dem_path: GeoTIFF path or None. Missing/unreadable files degrade to None
            (no occlusion) — sensor models must stay functional without a DEM.
        downsample: Block pooling factor passed to :meth:`TerrainGrid.from_geotiff`.
        mode: ``"elevation"`` or ``"landmask"`` blocking rule.
        cache: Optional dict used as a path-keyed cache (share one grid across
            sensor instances).

    Returns:
        TerrainGrid or None.
    """
    if dem_path is None:
        return None
    key = f"{Path(dem_path).resolve()}::{mode}::{int(downsample)}"
    store = cache if cache is not None else {}
    if key in store:
        return store[key]
    try:
        grid = TerrainGrid.from_geotiff(dem_path, downsample=downsample, mode=mode)
    except Exception:  # noqa: BLE001 (any loader failure degrades to no occlusion)
        return None
    store[key] = grid
    return grid
