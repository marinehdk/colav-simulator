"""Versioned ENC region qualification and fail-closed preflight contracts.

The module owns chart coverage evidence for historical AIS cases.  It does not
change simulator ``map_size`` or decide whether a vessel is legally safe.  A
profile only authorizes a case when its source, projection, derived chart
cache, and qualification state agree.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import fiona
from pyproj import Transformer
from shapely import wkb
from shapely.geometry import LineString, Point, box, shape
from shapely.ops import unary_union
from shapely.prepared import prep

from colav_simulator.historical_serialization import semantic_hash as _sha256_json

ENC_REGION_SCHEMA_VERSION = "enc-region.v1"
ENC_CACHE_SCHEMA_VERSION = "enc-cache.v1"
WGS84_CRS = "EPSG:4326"
ROMSDAL_SIMULATION_CRS = "EPSG:25833"
ROMSDAL_UTM_ZONE = 33
ROMSDAL_EXPANDED_PROJECTED_EXTENT = (33500.0, 6945450.0, 63500.0, 6985450.0)
ROMSDAL_SMALL_PROJECTED_EXTENT = (38500.0, 6955450.0, 43500.0, 6960450.0)

__all__ = [
    "ENC_CACHE_SCHEMA_VERSION",
    "ENC_REGION_SCHEMA_VERSION",
    "ENCPreflightRequest",
    "ENCPreflightResult",
    "ENCPreflightStatus",
    "ENCQualificationState",
    "ENCRegionProfile",
    "ENCCacheIdentity",
    "ENCLayerIdentity",
    "ENCSimulationProjection",
    "ENCSourceIdentity",
    "ROMSDAL_EXPANDED_PROJECTED_EXTENT",
    "ROMSDAL_SMALL_PROJECTED_EXTENT",
    "build_expanded_romsdal_profile",
    "build_small_romsdal_profile",
]


class ENCQualificationState(str, Enum):
    """Qualification state of one immutable chart region profile."""

    QUALIFIED = "QUALIFIED"
    INCOMPLETE = "INCOMPLETE"
    UNQUALIFIED = "UNQUALIFIED"
    STALE = "STALE"


class ENCPreflightStatus(str, Enum):
    """Outcome of checking selected positions against one profile."""

    PASS = "PASS"
    OUTSIDE_COVERAGE = "OUTSIDE_COVERAGE"
    UNQUALIFIED = "UNQUALIFIED"
    CRS_MISMATCH = "CRS_MISMATCH"
    INVALID_REQUEST = "INVALID_REQUEST"


@dataclass(frozen=True)
class ENCSourceIdentity:
    """Content identity and CRS metadata for a chart source."""

    provider: str
    source_name: str
    source_digest: str
    source_crs: str
    format: str
    source_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "source_name": self.source_name,
            "source_digest": self.source_digest,
            "source_crs": self.source_crs,
            "format": self.format,
            "source_version": self.source_version,
        }


@dataclass(frozen=True)
class ENCSimulationProjection:
    """Explicit WGS84-to-simulation CRS transformation contract."""

    input_crs: str
    simulation_crs: str
    utm_zone: int
    axis_order: str = "longitude_latitude"

    def __post_init__(self) -> None:
        """Validate the projection axis and UTM zone."""
        if not 1 <= int(self.utm_zone) <= 60:
            raise ValueError("utm_zone must be in the range 1..60")
        if self.axis_order != "longitude_latitude":
            raise ValueError("ENC projections require longitude_latitude axis order")
        object.__setattr__(self, "utm_zone", int(self.utm_zone))

    def project_wgs84(self, position: tuple[float, float]) -> tuple[float, float]:
        """Project one ``(longitude, latitude)`` WGS84 point."""
        transformer = _transformer(WGS84_CRS, self.simulation_crs)
        easting, northing = transformer.transform(float(position[0]), float(position[1]))
        return float(easting), float(northing)

    def to_wgs84(self, position: tuple[float, float]) -> tuple[float, float]:
        """Inverse-project one simulation point into WGS84 longitude/latitude."""
        transformer = _transformer(self.simulation_crs, WGS84_CRS)
        longitude, latitude = transformer.transform(float(position[0]), float(position[1]))
        return float(longitude), float(latitude)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_crs": self.input_crs,
            "simulation_crs": self.simulation_crs,
            "utm_zone": self.utm_zone,
            "axis_order": self.axis_order,
        }


@dataclass(frozen=True)
class ENCLayerIdentity:
    """One source/preprocessing layer retained in qualification evidence."""

    layer_id: str
    source_layer: str
    feature_count: int
    geometry_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "source_layer": self.source_layer,
            "feature_count": self.feature_count,
            "geometry_digest": self.geometry_digest,
        }


@dataclass(frozen=True)
class ENCCacheIdentity:
    """Version and source binding for derived coverage/hazard preprocessing."""

    cache_id: str
    preprocessing_version: str
    source_digest: str
    artifact_digest: str
    status: str = "CURRENT"
    artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ENC_CACHE_SCHEMA_VERSION,
            "cache_id": self.cache_id,
            "preprocessing_version": self.preprocessing_version,
            "source_digest": self.source_digest,
            "artifact_digest": self.artifact_digest,
            "status": self.status,
            "artifact_path": self.artifact_path,
        }


@dataclass(frozen=True)
class ENCPreflightRequest:
    """Selected AIS positions and optional route to check against a profile."""

    positions: tuple[tuple[str, float, float], ...]
    input_crs: str = WGS84_CRS
    route_points: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        """Normalize selected positions and route coordinates."""
        normalized: list[tuple[str, float, float]] = []
        for observation_id, longitude, latitude in self.positions:
            normalized.append((str(observation_id), float(longitude), float(latitude)))
        object.__setattr__(self, "positions", tuple(normalized))
        object.__setattr__(self, "route_points", tuple(tuple(map(float, point)) for point in self.route_points))


@dataclass(frozen=True)
class ENCPreflightResult:
    """Typed, immutable result consumed by a HistoricalAISCase builder."""

    profile_id: str
    profile_digest: str
    status: ENCPreflightStatus
    checked_observation_ids: tuple[str, ...] = ()
    outside_observation_ids: tuple[str, ...] = ()
    hazard_observation_ids: tuple[str, ...] = ()
    uncovered_observation_ids: tuple[str, ...] = ()
    navigability_observation_ids: tuple[str, ...] = ()
    failure_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalize enum and immutable result collections."""
        status = self.status if isinstance(self.status, ENCPreflightStatus) else ENCPreflightStatus(self.status)
        object.__setattr__(self, "status", status)
        for name in (
            "checked_observation_ids",
            "outside_observation_ids",
            "hazard_observation_ids",
            "uncovered_observation_ids",
            "navigability_observation_ids",
            "failure_codes",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    @property
    def all_positions_contained(self) -> bool:
        """Whether every selected position is inside profile supported extent."""
        return not self.outside_observation_ids

    @property
    def qualified(self) -> bool:
        """Whether this request is authorized for an ENC-backed case."""
        return self.status is ENCPreflightStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_digest": self.profile_digest,
            "status": self.status.value,
            "checked_observation_ids": list(self.checked_observation_ids),
            "outside_observation_ids": list(self.outside_observation_ids),
            "hazard_observation_ids": list(self.hazard_observation_ids),
            "uncovered_observation_ids": list(self.uncovered_observation_ids),
            "navigability_observation_ids": list(self.navigability_observation_ids),
            "failure_codes": list(self.failure_codes),
            "all_positions_contained": self.all_positions_contained,
        }


@dataclass(frozen=True)
class ENCRegionProfile:
    """Versioned chart region authority for HistoricalAISCase preflight."""

    profile_id: str
    profile_version: str
    source: ENCSourceIdentity
    projection: ENCSimulationProjection
    supported_extent_wgs84: tuple[float, float, float, float]
    supported_extent_projected: tuple[float, float, float, float]
    hazard_layers: tuple[ENCLayerIdentity, ...]
    navigability_layers: tuple[ENCLayerIdentity, ...]
    cache: ENCCacheIdentity
    qualification_state: ENCQualificationState
    qualification_reasons: tuple[str, ...]
    provenance: Mapping[str, str]
    coverage_geometry_wkb: bytes = b""
    hazard_geometry_wkb: bytes = b""
    navigability_geometry_wkb: bytes = b""
    schema_version: str = ENC_REGION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Normalize immutable profile collections and compute identity."""
        state = (
            self.qualification_state
            if isinstance(self.qualification_state, ENCQualificationState)
            else ENCQualificationState(self.qualification_state)
        )
        object.__setattr__(self, "qualification_state", state)
        object.__setattr__(self, "supported_extent_wgs84", _extent(self.supported_extent_wgs84))
        object.__setattr__(self, "supported_extent_projected", _extent(self.supported_extent_projected))
        object.__setattr__(self, "hazard_layers", tuple(self.hazard_layers))
        object.__setattr__(self, "navigability_layers", tuple(self.navigability_layers))
        object.__setattr__(self, "qualification_reasons", tuple(self.qualification_reasons))
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    @property
    def profile_digest(self) -> str:
        """Content identity for this profile and its qualification evidence."""
        return _sha256_json(self._identity_dict())

    def contains_projected(self, position: tuple[float, float]) -> bool:
        """Return whether a projected point is inside the supported extent."""
        min_x, min_y, max_x, max_y = self.supported_extent_projected
        x, y = position
        return min_x <= x <= max_x and min_y <= y <= max_y

    def preflight(self, request: ENCPreflightRequest) -> ENCPreflightResult:
        """Check selected WGS84 AIS positions and optional route fail-closed."""
        checked_ids = tuple(item[0] for item in request.positions)
        if request.input_crs != self.projection.input_crs:
            return self._result(
                ENCPreflightStatus.CRS_MISMATCH,
                checked_ids=checked_ids,
                failures=("CRS_MISMATCH",),
            )
        if not request.positions:
            return self._result(
                ENCPreflightStatus.INVALID_REQUEST,
                failures=("EMPTY_SELECTION",),
            )

        valid_ids: list[str] = []
        longitudes: list[float] = []
        latitudes: list[float] = []
        invalid_ids: list[str] = []
        for observation_id, longitude, latitude in request.positions:
            if not (
                math.isfinite(longitude)
                and math.isfinite(latitude)
                and -180.0 <= longitude <= 180.0
                and -90.0 <= latitude <= 90.0
            ):
                invalid_ids.append(observation_id)
                continue
            valid_ids.append(observation_id)
            longitudes.append(longitude)
            latitudes.append(latitude)
        if invalid_ids:
            return self._result(
                ENCPreflightStatus.INVALID_REQUEST,
                checked_ids=checked_ids,
                failures=("INVALID_COORDINATE",),
            )
        projected_x, projected_y = _transformer(WGS84_CRS, self.projection.simulation_crs).transform(
            longitudes,
            latitudes,
        )
        projected = [
            (observation_id, (float(easting), float(northing)))
            for observation_id, easting, northing in zip(valid_ids, projected_x, projected_y, strict=True)
        ]

        outside_ids = tuple(
            observation_id for observation_id, position in projected if not self.contains_projected(position)
        )
        if outside_ids:
            return self._result(
                ENCPreflightStatus.OUTSIDE_COVERAGE,
                checked_ids=checked_ids,
                outside_ids=outside_ids,
                failures=("OUTSIDE_COVERAGE",),
            )
        if self._route_is_outside(request.route_points):
            return self._result(
                ENCPreflightStatus.OUTSIDE_COVERAGE,
                checked_ids=checked_ids,
                failures=("ROUTE_OUTSIDE_COVERAGE",),
            )

        profile_failures = self._qualification_failures()
        if profile_failures:
            return self._result(
                ENCPreflightStatus.UNQUALIFIED,
                checked_ids=checked_ids,
                failures=profile_failures,
            )

        geometry_result = self._preflight_geometry(request, checked_ids, projected)
        if geometry_result is not None:
            return geometry_result
        return self._result(ENCPreflightStatus.PASS, checked_ids=checked_ids)

    def preflight_historical_ais(self, read_result: Any) -> ENCPreflightResult:
        """Adapt a :class:`HistoricalAISReadResult` to the public preflight seam."""
        positions = []
        for observation in read_result.observations:
            normalized = observation.normalized
            positions.append(
                (
                    f"{observation.raw.entry_name}:{observation.raw.source_row_index}",
                    float("nan") if normalized.longitude_deg is None else normalized.longitude_deg,
                    float("nan") if normalized.latitude_deg is None else normalized.latitude_deg,
                )
            )
        return self.preflight(
            ENCPreflightRequest(
                positions=tuple(positions),
                input_crs=read_result.descriptor.normalized_crs,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        result = self._identity_dict()
        result["provenance"] = dict(self.provenance)
        result["profile_digest"] = self.profile_digest
        return result

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "source": self.source.to_dict(),
            "projection": self.projection.to_dict(),
            "supported_extent_wgs84": self.supported_extent_wgs84,
            "supported_extent_projected": self.supported_extent_projected,
            "hazard_layers": [item.to_dict() for item in self.hazard_layers],
            "navigability_layers": [item.to_dict() for item in self.navigability_layers],
            "cache": self.cache.to_dict(),
            "qualification_state": self.qualification_state.value,
            "qualification_reasons": self.qualification_reasons,
            "provenance": {key: value for key, value in self.provenance.items() if key != "source_path"},
            "coverage_geometry_sha256": _sha256_bytes(self.coverage_geometry_wkb),
            "hazard_geometry_sha256": _sha256_bytes(self.hazard_geometry_wkb),
            "navigability_geometry_sha256": _sha256_bytes(self.navigability_geometry_wkb),
        }

    def _qualification_failures(self) -> tuple[str, ...]:
        if self.qualification_state is ENCQualificationState.INCOMPLETE:
            failures = ("PROFILE_INCOMPLETE",)
        elif self.qualification_state is ENCQualificationState.STALE:
            failures = ("PROFILE_STALE",)
        elif self.qualification_state is ENCQualificationState.UNQUALIFIED:
            failures = ("PROFILE_UNQUALIFIED",)
        else:
            failures = ()
        if self.source.source_crs != self.projection.simulation_crs:
            failures += ("SOURCE_CRS_MISMATCH",)
        if self.cache.source_digest != self.source.source_digest or self.cache.status != "CURRENT":
            failures += ("STALE_CACHE",)
        return failures

    def _route_is_outside(self, route_points: Sequence[tuple[float, float]]) -> bool:
        projected_route = tuple(self.projection.project_wgs84(point) for point in route_points)
        return any(not self.contains_projected(point) for point in projected_route)

    def _preflight_geometry(
        self,
        request: ENCPreflightRequest,
        checked_ids: tuple[str, ...],
        projected: Sequence[tuple[str, tuple[float, float]]],
    ) -> ENCPreflightResult | None:
        coverage = _load_geometry(self.coverage_geometry_wkb)
        hazard = _load_geometry(self.hazard_geometry_wkb)
        navigability = _load_geometry(self.navigability_geometry_wkb)
        coverage_predicate = prep(coverage) if coverage is not None else None
        hazard_predicate = prep(hazard) if hazard is not None else None
        navigability_predicate = prep(navigability) if navigability is not None else None
        uncovered_ids = tuple(
            observation_id
            for observation_id, position in projected
            if coverage_predicate is None or not coverage_predicate.covers(Point(position))
        )
        hazard_ids = tuple(
            observation_id
            for observation_id, position in projected
            if hazard_predicate is not None and hazard_predicate.covers(Point(position))
        )
        navigability_ids = tuple(
            observation_id
            for observation_id, position in projected
            if navigability_predicate is not None
            and observation_id not in hazard_ids
            and not navigability_predicate.covers(Point(position))
        )
        route_has_hazard = _route_intersects_hazard(request.route_points, self.projection, hazard)
        failures = tuple(
            code
            for code, present in (
                ("COVERAGE_UNKNOWN", bool(uncovered_ids)),
                ("HAZARD_INTERSECTION", bool(hazard_ids)),
                ("NAVIGABILITY_UNKNOWN", bool(navigability_ids)),
                ("ROUTE_HAZARD_INTERSECTION", route_has_hazard),
            )
            if present
        )
        if not failures:
            return None
        return self._result(
            ENCPreflightStatus.UNQUALIFIED,
            checked_ids=checked_ids,
            hazard_ids=hazard_ids,
            uncovered_ids=uncovered_ids,
            navigability_ids=navigability_ids,
            failures=failures,
        )

    def _result(
        self,
        status: ENCPreflightStatus,
        *,
        checked_ids: Sequence[str] = (),
        outside_ids: Sequence[str] = (),
        hazard_ids: Sequence[str] = (),
        uncovered_ids: Sequence[str] = (),
        navigability_ids: Sequence[str] = (),
        failures: Sequence[str] = (),
    ) -> ENCPreflightResult:
        return ENCPreflightResult(
            profile_id=self.profile_id,
            profile_digest=self.profile_digest,
            status=status,
            checked_observation_ids=tuple(checked_ids),
            outside_observation_ids=tuple(outside_ids),
            hazard_observation_ids=tuple(hazard_ids),
            uncovered_observation_ids=tuple(uncovered_ids),
            navigability_observation_ids=tuple(navigability_ids),
            failure_codes=tuple(failures),
        )


def build_expanded_romsdal_profile(
    source_path: str | Path | None = None,
    *,
    projected_extent: tuple[float, float, float, float] = ROMSDAL_EXPANDED_PROJECTED_EXTENT,
) -> ENCRegionProfile:
    """Build a qualified profile from the local More-og-Romsdal FileGDB.

    The source is inspected and the selected chart geometry is preprocessed
    before ``QUALIFIED`` is emitted.  Missing source/layers/coverage produce an
    explicit ``INCOMPLETE`` profile instead of a permissive fallback.
    """
    path = Path(source_path) if source_path is not None else _default_romsdal_source()
    try:
        return _build_profile_from_source(path, projected_extent, profile_id="romsdal-expanded")
    except Exception as exc:  # pragma: no cover - exercised by deployment failures
        return _incomplete_profile(
            path,
            projected_extent,
            f"SOURCE_INSPECTION_ERROR:{type(exc).__name__}",
            profile_id="romsdal-expanded",
        )


def build_small_romsdal_profile(source_path: str | Path | None = None) -> ENCRegionProfile:
    """Build the legacy 5 x 5 km Romsdal fixture as its own profile identity."""
    path = Path(source_path) if source_path is not None else _default_romsdal_source()
    try:
        return _build_profile_from_source(path, ROMSDAL_SMALL_PROJECTED_EXTENT, profile_id="romsdal-small")
    except Exception as exc:  # pragma: no cover - exercised by deployment failures
        return _incomplete_profile(
            path,
            ROMSDAL_SMALL_PROJECTED_EXTENT,
            f"SOURCE_INSPECTION_ERROR:{type(exc).__name__}",
            profile_id="romsdal-small",
        )


def _build_profile_from_source(
    path: Path,
    projected_extent: tuple[float, float, float, float],
    *,
    profile_id: str,
) -> ENCRegionProfile:
    if not path.exists() or not path.is_dir():
        return _incomplete_profile(path, projected_extent, "SOURCE_MISSING", profile_id=profile_id)
    source_digest = _sha256_directory(path)
    layer_names = tuple(sorted(fiona.listlayers(path)))
    metadata: dict[str, ENCLayerIdentity] = {}
    source_crs = "UNKNOWN"
    for layer_name in layer_names:
        with fiona.open(path, layer=layer_name) as source:
            if source_crs == "UNKNOWN" and source.crs:
                source_crs = source.crs.to_string()
            metadata[layer_name] = ENCLayerIdentity(
                layer_id=layer_name.upper(),
                source_layer=layer_name,
                feature_count=len(source),
                geometry_digest="",
            )

    required = (
        "dataavgrensning",
        "datakvalitet",
        "dybdeareal",
        "ikkekartlagtsjomaltomr",
        "landareal",
        "skjer",
        "torrfall",
    )
    missing = tuple(name for name in required if name not in metadata)
    clip = box(*projected_extent)

    def read_layer_union(layer_name: str, *, point_buffer_m: float = 0.0) -> tuple[Any, int, str]:
        geometries = []
        with fiona.open(path, layer=layer_name) as source:
            for feature in source.filter(bbox=projected_extent):
                geometry = shape(feature["geometry"])
                if point_buffer_m and geometry.geom_type in {"Point", "MultiPoint"}:
                    geometry = geometry.buffer(point_buffer_m)
                geometry = geometry.intersection(clip)
                if not geometry.is_empty:
                    geometries.append(geometry)
        union = unary_union(geometries) if geometries else box(0, 0, 0, 0)
        return union, len(geometries), _sha256_bytes(union.wkb)

    if missing:
        return _incomplete_profile(
            path,
            projected_extent,
            *tuple(f"MISSING_LAYER:{name}" for name in missing),
            source_digest=source_digest,
            source_crs=source_crs,
            metadata=metadata,
            profile_id=profile_id,
        )

    water, water_count, water_digest = read_layer_union("dybdeareal")
    land, land_count, land_digest = read_layer_union("landareal")
    shore, shore_count, shore_digest = read_layer_union("torrfall")
    skerries, skerry_count, skerry_digest = read_layer_union("skjer", point_buffer_m=5.0)
    unsurveyed, unsurveyed_count, unsurveyed_digest = read_layer_union("ikkekartlagtsjomaltomr")
    _, quality_count, _ = read_layer_union("datakvalitet")
    hazards = unary_union((land, shore, skerries, unsurveyed))
    coverage = unary_union((water, hazards))
    navigability = water.difference(hazards)
    gap_area = clip.difference(coverage).area
    layer_counts = {
        "DEPARE": water_count,
        "LAND": land_count,
        "SHORE": shore_count,
        "SKERRY": skerry_count,
        "UNSURVEYED": unsurveyed_count,
        "QUALITY": quality_count,
    }
    cache_payload = {
        "schema_version": ENC_CACHE_SCHEMA_VERSION,
        "preprocessing_version": "enc-preprocess.v1",
        "source_digest": source_digest,
        "extent": projected_extent,
        "layers": layer_counts,
        "geometry_digests": {
            "water": water_digest,
            "land": land_digest,
            "shore": shore_digest,
            "skerry": skerry_digest,
            "unsurveyed": unsurveyed_digest,
        },
    }
    cache = ENCCacheIdentity(
        cache_id=f"{profile_id}-{_sha256_json(cache_payload)[:16]}",
        preprocessing_version="enc-preprocess.v1",
        source_digest=source_digest,
        artifact_digest=_sha256_json(cache_payload),
    )
    reasons: list[str] = []
    if source_crs != ROMSDAL_SIMULATION_CRS:
        reasons.append(f"SOURCE_CRS_MISMATCH:{source_crs}")
    if not all(layer_counts[name] > 0 for name in ("DEPARE", "LAND", "SHORE", "QUALITY")):
        reasons.append("EMPTY_REQUIRED_PREPROCESS_LAYER")
    if gap_area > max(1e-3, clip.area * 1e-9):
        reasons.append(f"COVERAGE_GAP_M2:{gap_area:.6f}")
    if water.is_empty or navigability.is_empty:
        reasons.append("NAVIGABILITY_UNAVAILABLE")
    source = ENCSourceIdentity(
        provider="Kartverket",
        source_name=path.name,
        source_digest=source_digest,
        source_crs=source_crs,
        format="FileGDB",
    )
    projection = ENCSimulationProjection(
        input_crs=WGS84_CRS,
        simulation_crs=ROMSDAL_SIMULATION_CRS,
        utm_zone=ROMSDAL_UTM_ZONE,
    )
    return ENCRegionProfile(
        profile_id=profile_id,
        profile_version="1.0.0",
        source=source,
        projection=projection,
        supported_extent_wgs84=_projected_extent_to_wgs84(projected_extent, projection),
        supported_extent_projected=projected_extent,
        hazard_layers=(
            ENCLayerIdentity("LAND", "landareal", metadata["landareal"].feature_count, land_digest),
            ENCLayerIdentity("SHORE", "torrfall", metadata["torrfall"].feature_count, shore_digest),
            ENCLayerIdentity("SKERRY", "skjer", metadata["skjer"].feature_count, skerry_digest),
            ENCLayerIdentity(
                "UNSURVEYED", "ikkekartlagtsjomaltomr", metadata["ikkekartlagtsjomaltomr"].feature_count, unsurveyed_digest
            ),
        ),
        navigability_layers=(ENCLayerIdentity("DEPARE", "dybdeareal", metadata["dybdeareal"].feature_count, water_digest),),
        cache=cache,
        qualification_state=ENCQualificationState.QUALIFIED if not reasons else ENCQualificationState.INCOMPLETE,
        qualification_reasons=tuple(reasons),
        provenance={
            "source_path": path.as_posix(),
            "source_layers": ",".join(layer_names),
            "coverage_gap_m2": f"{gap_area:.6f}",
            "processing": "fiona+bbox+shapely-unary-union",
        },
        coverage_geometry_wkb=coverage.wkb,
        hazard_geometry_wkb=hazards.wkb,
        navigability_geometry_wkb=navigability.wkb,
    )


def _incomplete_profile(
    path: Path,
    projected_extent: tuple[float, float, float, float],
    *reasons: str,
    source_digest: str = "UNAVAILABLE",
    source_crs: str = "UNKNOWN",
    metadata: Mapping[str, ENCLayerIdentity] | None = None,
    profile_id: str = "romsdal-expanded",
) -> ENCRegionProfile:
    source = ENCSourceIdentity(
        provider="Kartverket",
        source_name=path.name,
        source_digest=source_digest,
        source_crs=source_crs,
        format="FileGDB",
    )
    projection = ENCSimulationProjection(
        input_crs=WGS84_CRS,
        simulation_crs=ROMSDAL_SIMULATION_CRS,
        utm_zone=ROMSDAL_UTM_ZONE,
    )
    cache = ENCCacheIdentity(
        cache_id="UNAVAILABLE",
        preprocessing_version="enc-preprocess.v1",
        source_digest=source_digest,
        artifact_digest="UNAVAILABLE",
        status="MISSING",
    )
    metadata = metadata or {}
    return ENCRegionProfile(
        profile_id=profile_id,
        profile_version="1.0.0",
        source=source,
        projection=projection,
        supported_extent_wgs84=_projected_extent_to_wgs84(projected_extent, projection),
        supported_extent_projected=projected_extent,
        hazard_layers=tuple(metadata.values()),
        navigability_layers=(),
        cache=cache,
        qualification_state=ENCQualificationState.INCOMPLETE,
        qualification_reasons=tuple(reasons) or ("QUALIFICATION_NOT_PROVEN",),
        provenance={"source_path": path.as_posix()},
    )


def _default_romsdal_source() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "enc" / "More_og_Romsdal_utm33.gdb"


def _projected_extent_to_wgs84(
    extent: tuple[float, float, float, float], projection: ENCSimulationProjection
) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = extent
    corners = [projection.to_wgs84((x, y)) for x, y in ((min_x, min_y), (min_x, max_y), (max_x, min_y), (max_x, max_y))]
    return (
        min(point[0] for point in corners),
        min(point[1] for point in corners),
        max(point[0] for point in corners),
        max(point[1] for point in corners),
    )


def _route_intersects_hazard(
    route_points: Sequence[tuple[float, float]], projection: ENCSimulationProjection, hazard: Any
) -> bool:
    if hazard is None or len(route_points) < 2:
        return False
    route = LineString([projection.project_wgs84(point) for point in route_points])
    return bool(route.intersects(hazard))


def _load_geometry(value: bytes) -> Any | None:
    return wkb.loads(value) if value else None


@lru_cache(maxsize=16)
def _transformer(source_crs: str, target_crs: str) -> Transformer:
    return Transformer.from_crs(source_crs, target_crs, always_xy=True)


def _extent(values: Sequence[float]) -> tuple[float, float, float, float]:
    if len(values) != 4:
        raise ValueError("extent must be (min_x, min_y, max_x, max_y)")
    extent = tuple(float(value) for value in values)
    min_x, min_y, max_x, max_y = extent
    if not all(math.isfinite(value) for value in extent) or min_x > max_x or min_y > max_y:
        raise ValueError("extent must be finite and ordered")
    return extent


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest() if value else "UNAVAILABLE"


def _sha256_directory(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(str(file_path.stat().st_size).encode("ascii"))
        with file_path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()
