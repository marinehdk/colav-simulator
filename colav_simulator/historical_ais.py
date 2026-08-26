"""Immutable, auditable ingestion of historical AIS source files.

This module deliberately stops at the dataset seam.  It does not reconstruct
historical actors or run a simulator.  A source row remains available beside
its normalized fact so that a derived value can always be traced back to the
content-addressed source evidence that produced it.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from shapely.geometry import Point

from colav_simulator.historical_serialization import jsonable as _jsonable
from colav_simulator.historical_serialization import semantic_hash as _sha256_json

try:
    from shapely import wkb, wkt
    from shapely.errors import GEOSException
except ImportError:  # pragma: no cover - project dependencies include shapely
    wkb = None
    wkt = None
    GEOSException = ValueError


SCHEMA_VERSION = "historical-ais.v1"
KNOT_TO_MPS = 0.514444
DEGREE_TO_RAD = math.pi / 180.0
ROT_DEGREE_PER_MINUTE_TO_RAD_PER_SECOND = DEGREE_TO_RAD / 60.0
SOURCE_CRS = "OGC:CRS84"
NORMALIZED_CRS = "EPSG:4326"
GEODETIC_DATUM = "WGS84"
UTC = timezone.utc
_ENTRY_DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")


class QualityFindingCode(str, Enum):
    """Machine-readable source and normalization quality findings."""

    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    NAIVE_TIMESTAMP_ASSUMED_UTC = "NAIVE_TIMESTAMP_ASSUMED_UTC"
    INVALID_COORDINATE = "INVALID_COORDINATE"
    INVALID_MMSI = "INVALID_MMSI"
    FIELD_UNAVAILABLE = "FIELD_UNAVAILABLE"
    FIELD_UNAVAILABLE_SENTINEL = "FIELD_UNAVAILABLE_SENTINEL"
    INVALID_SPEED = "INVALID_SPEED"
    INVALID_COURSE = "INVALID_COURSE"
    INVALID_HEADING = "INVALID_HEADING"
    INVALID_ROT = "INVALID_ROT"
    INVALID_DIMENSION = "INVALID_DIMENSION"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    CONFLICTING_DUPLICATE = "CONFLICTING_DUPLICATE"
    OBSERVATION_GAP = "OBSERVATION_GAP"


class QualitySeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class FieldAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class HistoricalAISSelection:
    """Immutable source predicates applied by :class:`HistoricalAISDatasetReader`.

    ``start_utc`` is inclusive and ``end_utc`` is exclusive.  Coordinates use
    WGS84 longitude/latitude order (the OGC:CRS84 axis order).  The selection
    itself is hashed and therefore forms part of the derived evidence identity.
    """

    start_utc: datetime | str | None = None
    end_utc: datetime | str | None = None
    mmsi: tuple[int, ...] = ()
    bbox: tuple[float, float, float, float] | None = None
    wkt: str | None = None
    entries: tuple[str, ...] = ()
    gap_threshold_s: float = 300.0

    def __post_init__(self) -> None:
        """Normalize and validate immutable selection values."""
        start = _coerce_utc(self.start_utc, allow_none=True)
        end = _coerce_utc(self.end_utc, allow_none=True)
        if start is not None and end is not None and end <= start:
            raise ValueError("end_utc must be later than start_utc")
        object.__setattr__(self, "start_utc", start)
        object.__setattr__(self, "end_utc", end)

        values = tuple(sorted({int(value) for value in self.mmsi}))
        if any(value < 0 for value in values):
            raise ValueError("mmsi selection values must be non-negative")
        object.__setattr__(self, "mmsi", values)

        if self.bbox is not None:
            if len(self.bbox) != 4:
                raise ValueError("bbox must be (min_lon, min_lat, max_lon, max_lat)")
            bbox = tuple(float(value) for value in self.bbox)
            min_lon, min_lat, max_lon, max_lat = bbox
            if not (
                all(math.isfinite(value) for value in bbox)
                and -180 <= min_lon <= max_lon <= 180
                and -90 <= min_lat <= max_lat <= 90
            ):
                raise ValueError("bbox must be a finite WGS84 longitude/latitude extent")
            object.__setattr__(self, "bbox", bbox)

        entries = tuple(sorted({str(value) for value in self.entries}))
        if any(not value for value in entries):
            raise ValueError("entries must not contain empty names")
        object.__setattr__(self, "entries", entries)
        if self.wkt is not None and not self.wkt.strip():
            raise ValueError("wkt must not be empty")
        if not math.isfinite(float(self.gap_threshold_s)) or self.gap_threshold_s <= 0:
            raise ValueError("gap_threshold_s must be positive and finite")
        object.__setattr__(self, "gap_threshold_s", float(self.gap_threshold_s))

    @property
    def start(self) -> datetime | None:
        return self.start_utc  # type: ignore[return-value]

    @property
    def end(self) -> datetime | None:
        return self.end_utc  # type: ignore[return-value]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "start_utc": _jsonable(self.start_utc),
            "end_utc": _jsonable(self.end_utc),
            "mmsi": list(self.mmsi),
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "wkt": self.wkt,
            "entries": list(self.entries),
            "gap_threshold_s": self.gap_threshold_s,
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalAISAttribution:
    """Provider and public-data limitations retained in every descriptor."""

    provider: str
    attribution: str
    nlod_license: str
    coverage_limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        """Freeze coverage metadata as a tuple."""
        object.__setattr__(self, "coverage_limitations", tuple(self.coverage_limitations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "attribution": self.attribution,
            "nlod_license": self.nlod_license,
            "coverage_limitations": list(self.coverage_limitations),
        }


@dataclass(frozen=True)
class HistoricalAISQualityFinding:
    """One typed finding; findings never silently disappear during filtering."""

    code: QualityFindingCode
    severity: QualitySeverity
    message: str
    entry_name: str | None = None
    row_indices: tuple[int, ...] = ()
    mmsi: int | None = None
    timestamp_utc: datetime | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize enum and mapping fields into immutable values."""
        code = self.code if isinstance(self.code, QualityFindingCode) else QualityFindingCode(self.code)
        severity = self.severity if isinstance(self.severity, QualitySeverity) else QualitySeverity(self.severity)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "row_indices", tuple(int(value) for value in self.row_indices))
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    @property
    def finding_type(self) -> str:
        return self.code.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "entry_name": self.entry_name,
            "row_indices": list(self.row_indices),
            "mmsi": self.mmsi,
            "timestamp_utc": _jsonable(self.timestamp_utc),
            "details": _jsonable(dict(self.details)),
        }


@dataclass(frozen=True)
class HistoricalAISEntryDigest:
    entry_name: str
    sha256: str
    uncompressed_bytes: int
    row_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_name": self.entry_name,
            "sha256": self.sha256,
            "uncompressed_bytes": self.uncompressed_bytes,
            "row_count": self.row_count,
        }


@dataclass(frozen=True)
class HistoricalAISSchemaField:
    source_field: str
    semantic_field: str | None
    raw_unit: str | None
    normalized_unit: str | None
    conversion: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_field": self.source_field,
            "semantic_field": self.semantic_field,
            "raw_unit": self.raw_unit,
            "normalized_unit": self.normalized_unit,
            "conversion": self.conversion,
        }


@dataclass(frozen=True)
class HistoricalAISDatasetDescriptor:
    """Immutable identity and quality summary for one selected dataset view."""

    provider: str
    format: str
    entries: tuple[str, ...]
    archive_sha256: str
    entry_digests: tuple[HistoricalAISEntryDigest, ...]
    schema_sha256: str
    selection_sha256: str
    normalized_sha256: str
    row_count: int
    normalized_row_count: int
    schema_fields: tuple[HistoricalAISSchemaField, ...]
    quality_findings: tuple[HistoricalAISQualityFinding, ...]
    source_crs: str = SOURCE_CRS
    normalized_crs: str = NORMALIZED_CRS
    geodetic_datum: str = GEODETIC_DATUM
    time_extent: tuple[datetime, datetime] | None = None
    spatial_extent: tuple[float, float, float, float] | None = None
    attribution: HistoricalAISAttribution = field(
        default_factory=lambda: HistoricalAISAttribution(
            provider="Kystverket",
            attribution="Kystverket HAIS",
            nlod_license="NLOD 2.0",
            coverage_limitations=(
                "Coverage is limited to reported AIS transmissions; small vessels may be absent "
                "due to privacy or equipment restrictions.",
            ),
        )
    )
    source_identity_unverified: bool = True
    schema_version: str = SCHEMA_VERSION
    descriptor_sha256: str = ""
    source_row_count: int = 0

    def __post_init__(self) -> None:
        """Freeze descriptor collections and calculate its identity digest."""
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "entry_digests", tuple(self.entry_digests))
        object.__setattr__(self, "schema_fields", tuple(self.schema_fields))
        object.__setattr__(self, "quality_findings", tuple(self.quality_findings))
        if self.time_extent is not None:
            object.__setattr__(self, "time_extent", tuple(self.time_extent))
        if self.spatial_extent is not None:
            object.__setattr__(self, "spatial_extent", tuple(float(value) for value in self.spatial_extent))
        if not self.descriptor_sha256:
            object.__setattr__(self, "descriptor_sha256", _sha256_json(self._identity_dict()))

    @property
    def raw_content_digest(self) -> str:
        return self.archive_sha256

    @property
    def raw_digest(self) -> str:
        return self.archive_sha256

    @property
    def archive_digest(self) -> str:
        return self.archive_sha256

    @property
    def entry_digest(self) -> tuple[HistoricalAISEntryDigest, ...]:
        return self.entry_digests

    @property
    def schema_digest(self) -> str:
        return self.schema_sha256

    @property
    def selection_digest(self) -> str:
        return self.selection_sha256

    @property
    def derived_digest(self) -> str:
        return self.normalized_sha256

    @property
    def content_digest(self) -> str:
        return self.descriptor_sha256

    @property
    def time_start_utc(self) -> datetime | None:
        return self.time_extent[0] if self.time_extent else None

    @property
    def time_end_utc(self) -> datetime | None:
        return self.time_extent[1] if self.time_extent else None

    @property
    def coverage_limitations(self) -> tuple[str, ...]:
        return self.attribution.coverage_limitations

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "format": self.format,
            "entries": list(self.entries),
            "archive_sha256": self.archive_sha256,
            "entry_digests": [item.to_dict() for item in self.entry_digests],
            "schema_sha256": self.schema_sha256,
            "selection_sha256": self.selection_sha256,
            "normalized_sha256": self.normalized_sha256,
            "row_count": self.row_count,
            "source_row_count": self.source_row_count,
            "normalized_row_count": self.normalized_row_count,
            "schema_fields": [item.to_dict() for item in self.schema_fields],
            "quality_findings": [item.to_dict() for item in self.quality_findings],
            "source_crs": self.source_crs,
            "normalized_crs": self.normalized_crs,
            "geodetic_datum": self.geodetic_datum,
            "time_extent": _jsonable(self.time_extent),
            "spatial_extent": self.spatial_extent,
            "attribution": self.attribution.to_dict(),
            "source_identity_unverified": self.source_identity_unverified,
        }

    def to_dict(self) -> dict[str, Any]:
        output = self._identity_dict()
        output["descriptor_sha256"] = self.descriptor_sha256
        return output


@dataclass(frozen=True)
class HistoricalAISRawFact:
    """Original source fields for one row, retained without normalization."""

    entry_name: str
    source_row_index: int
    values: Mapping[str, Any]
    row_sha256: str
    duplicate_version: int = 0

    def __post_init__(self) -> None:
        """Freeze source values so raw evidence cannot be mutated."""
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_name": self.entry_name,
            "source_row_index": self.source_row_index,
            "values": _jsonable(dict(self.values)),
            "row_sha256": self.row_sha256,
            "duplicate_version": self.duplicate_version,
        }

    @property
    def raw_fields(self) -> Mapping[str, Any]:
        return self.values


@dataclass(frozen=True)
class HistoricalAISNormalizedFact:
    """Simulator-facing SI/radian fact with explicit unavailable fields."""

    timestamp_utc: datetime | None
    mmsi: int | None
    longitude_deg: float | None
    latitude_deg: float | None
    sog_mps: float | None
    cog_rad: float | None
    heading_rad: float | None
    rot_radps: float | None
    length_m: float | None = None
    width_m: float | None = None
    draft_m: float | None = None
    source_crs: str = SOURCE_CRS
    normalized_crs: str = NORMALIZED_CRS
    coordinate_axis_order: str = "longitude_latitude"
    unavailable_fields: tuple[str, ...] = ()
    field_status: Mapping[str, str] = field(default_factory=dict)
    conversion_provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze status and conversion mappings."""
        object.__setattr__(self, "unavailable_fields", tuple(self.unavailable_fields))
        object.__setattr__(self, "field_status", MappingProxyType(dict(self.field_status)))
        object.__setattr__(self, "conversion_provenance", MappingProxyType(dict(self.conversion_provenance)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": _jsonable(self.timestamp_utc),
            "mmsi": self.mmsi,
            "longitude_deg": self.longitude_deg,
            "latitude_deg": self.latitude_deg,
            "sog_mps": self.sog_mps,
            "cog_rad": self.cog_rad,
            "heading_rad": self.heading_rad,
            "rot_radps": self.rot_radps,
            "length_m": self.length_m,
            "width_m": self.width_m,
            "draft_m": self.draft_m,
            "source_crs": self.source_crs,
            "normalized_crs": self.normalized_crs,
            "coordinate_axis_order": self.coordinate_axis_order,
            "unavailable_fields": list(self.unavailable_fields),
            "field_status": dict(self.field_status),
            "conversion_provenance": dict(self.conversion_provenance),
        }

    @property
    def lon_deg(self) -> float | None:
        return self.longitude_deg

    @property
    def lat_deg(self) -> float | None:
        return self.latitude_deg

    @property
    def speed_mps(self) -> float | None:
        return self.sog_mps

    @property
    def course_rad(self) -> float | None:
        return self.cog_rad


@dataclass(frozen=True)
class HistoricalAISObservation:
    """One auditable raw/normalized pair."""

    raw: HistoricalAISRawFact
    normalized: HistoricalAISNormalizedFact

    @property
    def source_entry(self) -> str:
        return self.raw.entry_name

    @property
    def source_row_index(self) -> int:
        return self.raw.source_row_index

    @property
    def raw_fact(self) -> HistoricalAISRawFact:
        return self.raw

    @property
    def normalized_fact(self) -> HistoricalAISNormalizedFact:
        return self.normalized

    def to_dict(self) -> dict[str, Any]:
        return {"raw": self.raw.to_dict(), "normalized": self.normalized.to_dict()}


@dataclass(frozen=True)
class HistoricalAISReadResult:
    """Public result of one dataset selection."""

    descriptor: HistoricalAISDatasetDescriptor
    observations: tuple[HistoricalAISObservation, ...]

    def __post_init__(self) -> None:
        """Freeze the observation sequence."""
        object.__setattr__(self, "observations", tuple(self.observations))

    @property
    def normalized_observations(self) -> tuple[HistoricalAISObservation, ...]:
        return self.observations

    @property
    def dataset_descriptor(self) -> HistoricalAISDatasetDescriptor:
        return self.descriptor

    def __iter__(self) -> Iterator[Any]:
        """Allow ergonomic descriptor/observation tuple unpacking."""
        yield self.descriptor
        yield self.observations


class HistoricalAISDatasetReader:
    """Read CSV, Parquet, or a ZIP containing daily Parquet/CSV entries.

    ZIP handling materializes only selected entries into a temporary file so
    that Arrow can seek in Parquet metadata.  It never extracts the archive as
    a whole and never writes source content into the repository.
    """

    def __init__(
        self,
        source: str | Path,
        *,
        provider: str = "Kystverket",
        source_identity_unverified: bool = True,
        coverage_limitations: Sequence[str] | None = None,
    ) -> None:
        self.source = Path(source).expanduser()
        if not self.source.is_file():
            raise FileNotFoundError(self.source)
        self.provider = provider
        self.source_identity_unverified = bool(source_identity_unverified)
        self.coverage_limitations = tuple(
            coverage_limitations
            or (
                "Coverage is limited to reported AIS transmissions; small vessels may be absent "
                "due to privacy or equipment restrictions.",
            )
        )

    def read(self, selection: HistoricalAISSelection | None = None) -> HistoricalAISReadResult:
        """Read and normalize the selected source rows through the public seam."""
        selection = selection or HistoricalAISSelection()
        archive_sha256 = _sha256_file(self.source)
        selected_entries = self._select_entries(selection)
        if not selected_entries:
            raise ValueError("selection did not identify any readable AIS entries")

        rows: list[tuple[str, int, dict[str, Any]]] = []
        entry_digests: list[HistoricalAISEntryDigest] = []
        schema_documents: list[dict[str, Any]] = []
        has_geometry = False

        with tempfile.TemporaryDirectory(prefix="historical-ais-") as temporary:
            for entry_name, entry_source in selected_entries:
                entry_path, entry_sha256, entry_bytes = self._materialize_entry(entry_source, temporary)
                if _is_parquet(entry_name):
                    entry_rows, schema = _read_parquet_rows(entry_path, selection)
                else:
                    entry_rows, schema = _read_csv_rows(entry_path)
                schema_documents.append(schema)
                has_geometry = has_geometry or "geometry" in {_field_key(key) for key in schema["fields"]}
                entry_digests.append(
                    HistoricalAISEntryDigest(
                        entry_name=entry_name,
                        sha256=entry_sha256,
                        uncompressed_bytes=entry_bytes,
                        row_count=len(entry_rows),
                    )
                )
                for row_index, row in enumerate(entry_rows):
                    rows.append((entry_name, row_index, row))

        observations, quality_findings = _normalize_rows(rows, selection)
        observations = _sort_observations(observations)
        quality_findings = tuple(sorted(quality_findings, key=_finding_sort_key))
        schema_fields = _schema_fields(schema_documents)
        schema_sha256 = _sha256_json(
            {
                "schema_version": SCHEMA_VERSION,
                "fields": [item.to_dict() for item in schema_fields],
                "arrow_schemas": schema_documents,
            }
        )
        normalized_sha256 = _sha256_json([item.to_dict() for item in observations])
        time_extent = _time_extent(observations)
        spatial_extent = _spatial_extent(observations)
        attribution = HistoricalAISAttribution(
            provider=self.provider,
            attribution=f"{self.provider} HAIS",
            nlod_license="NLOD 2.0",
            coverage_limitations=self.coverage_limitations,
        )
        descriptor = HistoricalAISDatasetDescriptor(
            provider=self.provider,
            format="geoparquet"
            if has_geometry and any(_is_parquet(name) for name, _ in selected_entries)
            else ("parquet" if any(_is_parquet(name) for name, _ in selected_entries) else "csv"),
            entries=tuple(name for name, _ in selected_entries),
            archive_sha256=archive_sha256,
            entry_digests=tuple(entry_digests),
            schema_sha256=schema_sha256,
            selection_sha256=selection.digest,
            normalized_sha256=normalized_sha256,
            row_count=len(observations),
            source_row_count=len(rows),
            normalized_row_count=len(observations),
            schema_fields=schema_fields,
            quality_findings=quality_findings,
            time_extent=time_extent,
            spatial_extent=spatial_extent,
            attribution=attribution,
            source_identity_unverified=self.source_identity_unverified,
        )
        return HistoricalAISReadResult(descriptor=descriptor, observations=observations)

    def _select_entries(self, selection: HistoricalAISSelection) -> list[tuple[str, Any]]:
        suffix = self.source.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(self.source) as archive:
                names = [
                    info.filename
                    for info in archive.infolist()
                    if not info.is_dir() and (_is_parquet(info.filename) or _is_csv(info.filename))
                ]
                selected_names = [name for name in names if _entry_selected(name, selection)]
                if selection.entries:
                    selected_names = [name for name in selected_names if name in selection.entries]
                return [(name, (self.source, name)) for name in sorted(selected_names)]
        if not (_is_parquet(self.source.name) or _is_csv(self.source.name)):
            raise ValueError(f"unsupported AIS source format: {self.source}")
        if selection.entries and self.source.name not in selection.entries:
            return []
        return [(self.source.name, self.source)]

    def _materialize_entry(self, entry_source: Any, temporary: str) -> tuple[Path, str, int]:
        if isinstance(entry_source, tuple):
            archive_path, entry_name = entry_source
            target = Path(temporary) / Path(entry_name).name
            digest = hashlib.sha256()
            size = 0
            with zipfile.ZipFile(archive_path) as archive, archive.open(entry_name) as source, target.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    output.write(chunk)
            return target, digest.hexdigest(), size
        path = Path(entry_source)
        return path, _sha256_file(path), path.stat().st_size


_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("date_time_utc", "datetime_utc", "timestamp_utc", "timestamp", "basedatetime", "time"),
    "mmsi": ("mmsi",),
    "longitude": ("longitude", "lon", "x"),
    "latitude": ("latitude", "lat", "y"),
    "geometry": ("geometry", "geom", "shape"),
    "sog": ("speed_over_ground", "sog", "speed"),
    "cog": ("course_over_ground", "cog", "course"),
    "heading": ("true_heading", "heading", "hdg"),
    "rot": ("rate_of_turn", "rot", "turn_rate"),
    "length": ("length", "vessel_length", "length_m"),
    "width": ("width", "vessel_width", "breadth", "width_m"),
    "draft": ("draft", "draft_m"),
}


def _normalize_rows(
    rows: Sequence[tuple[str, int, dict[str, Any]]], selection: HistoricalAISSelection
) -> tuple[tuple[HistoricalAISObservation, ...], tuple[HistoricalAISQualityFinding, ...]]:
    observations: list[HistoricalAISObservation] = []
    findings: list[HistoricalAISQualityFinding] = []
    for entry_name, row_index, row in rows:
        raw = HistoricalAISRawFact(
            entry_name=entry_name,
            source_row_index=row_index,
            values=row,
            row_sha256=_sha256_json(row),
        )
        normalized, row_findings = _normalize_row(raw)
        findings.extend(row_findings)
        if _selected_normalized(normalized, selection):
            observations.append(HistoricalAISObservation(raw=raw, normalized=normalized))

    observations, duplicate_findings = _version_duplicates(observations)
    findings.extend(duplicate_findings)
    findings.extend(_gap_findings(observations, selection.gap_threshold_s))
    return tuple(observations), tuple(findings)


def _normalize_row(
    raw: HistoricalAISRawFact,
) -> tuple[HistoricalAISNormalizedFact, tuple[HistoricalAISQualityFinding, ...]]:
    row = raw.values
    findings: list[HistoricalAISQualityFinding] = []
    timestamp_raw = _lookup(row, "timestamp")
    timestamp, timestamp_status = _normalize_timestamp(timestamp_raw, raw, findings)
    mmsi_raw = _lookup(row, "mmsi")
    mmsi, mmsi_status = _normalize_mmsi(mmsi_raw, raw, findings)
    longitude_raw = _lookup(row, "longitude")
    latitude_raw = _lookup(row, "latitude")
    if longitude_raw is None or latitude_raw is None:
        geometry = _lookup(row, "geometry")
        longitude_raw, latitude_raw = _geometry_coordinates(geometry)
    longitude, longitude_status = _normalize_coordinate(longitude_raw, "longitude_deg", raw, findings, -180, 180)
    latitude, latitude_status = _normalize_coordinate(latitude_raw, "latitude_deg", raw, findings, -90, 90)
    sog, sog_status = _normalize_measurement(
        _lookup(row, "sog"),
        "sog_mps",
        raw,
        findings,
        sentinel=102.3,
        invalid_code=QualityFindingCode.INVALID_SPEED,
        minimum=0.0,
    )
    if sog is not None:
        sog *= KNOT_TO_MPS
    cog, cog_status = _normalize_measurement(
        _lookup(row, "cog"),
        "cog_rad",
        raw,
        findings,
        sentinel=360.0,
        invalid_code=QualityFindingCode.INVALID_COURSE,
        minimum=0.0,
        maximum=360.0,
    )
    if cog is not None:
        cog *= DEGREE_TO_RAD
    heading, heading_status = _normalize_measurement(
        _lookup(row, "heading"),
        "heading_rad",
        raw,
        findings,
        sentinel=511.0,
        invalid_code=QualityFindingCode.INVALID_HEADING,
        minimum=0.0,
        maximum=360.0,
    )
    if heading is not None:
        heading *= DEGREE_TO_RAD
    rot, rot_status = _normalize_measurement(
        _lookup(row, "rot"),
        "rot_radps",
        raw,
        findings,
        sentinel=-128.0,
        invalid_code=QualityFindingCode.INVALID_ROT,
        minimum=-128.0,
        maximum=127.0,
    )
    if rot is not None:
        rot *= ROT_DEGREE_PER_MINUTE_TO_RAD_PER_SECOND
    length, length_status = _normalize_dimension(_lookup(row, "length"), "length_m", raw, findings)
    width, width_status = _normalize_dimension(_lookup(row, "width"), "width_m", raw, findings)
    draft, draft_status = _normalize_dimension(_lookup(row, "draft"), "draft_m", raw, findings)

    field_status = {
        "timestamp_utc": timestamp_status,
        "mmsi": mmsi_status,
        "longitude_deg": longitude_status,
        "latitude_deg": latitude_status,
        "sog_mps": sog_status,
        "cog_rad": cog_status,
        "heading_rad": heading_status,
        "rot_radps": rot_status,
        "length_m": length_status,
        "width_m": width_status,
        "draft_m": draft_status,
    }
    unavailable_fields = tuple(
        name for name, status in field_status.items() if status == FieldAvailability.UNAVAILABLE.value
    )
    return (
        HistoricalAISNormalizedFact(
            timestamp_utc=timestamp,
            mmsi=mmsi,
            longitude_deg=longitude,
            latitude_deg=latitude,
            sog_mps=sog,
            cog_rad=cog,
            heading_rad=heading,
            rot_radps=rot,
            length_m=length,
            width_m=width,
            draft_m=draft,
            unavailable_fields=unavailable_fields,
            field_status=field_status,
            conversion_provenance={
                "sog_mps": "knots_to_mps",
                "cog_rad": "degrees_to_radians",
                "heading_rad": "degrees_to_radians",
                "rot_radps": "degrees_per_minute_to_radians_per_second",
                "length_m": "source_dimension_meters_no_conversion",
                "width_m": "source_dimension_meters_no_conversion",
                "draft_m": "source_dimension_meters_no_conversion",
            },
        ),
        tuple(findings),
    )


def _normalize_timestamp(
    value: Any, raw: HistoricalAISRawFact, findings: list[HistoricalAISQualityFinding]
) -> tuple[datetime | None, str]:
    if value is None or value == "":
        findings.append(
            _finding(
                QualityFindingCode.FIELD_UNAVAILABLE, "timestamp_utc is unavailable", raw, details={"field": "timestamp_utc"}
            )
        )
        return None, FieldAvailability.UNAVAILABLE.value
    try:
        if isinstance(value, datetime):
            parsed = value
        elif hasattr(value, "to_pydatetime"):
            parsed = value.to_pydatetime()
        elif isinstance(value, str):
            text = value.strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
        else:
            raise ValueError("timestamp must be an ISO string or datetime")
        if parsed.tzinfo is None:
            findings.append(
                _finding(QualityFindingCode.NAIVE_TIMESTAMP_ASSUMED_UTC, "naive timestamp interpreted as UTC", raw)
            )
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return parsed, FieldAvailability.AVAILABLE.value
    except (TypeError, ValueError, OverflowError) as exc:
        findings.append(_finding(QualityFindingCode.INVALID_TIMESTAMP, f"invalid timestamp: {exc}", raw))
        return None, FieldAvailability.INVALID.value


def _normalize_mmsi(
    value: Any, raw: HistoricalAISRawFact, findings: list[HistoricalAISQualityFinding]
) -> tuple[int | None, str]:
    if value is None or value == "":
        findings.append(
            _finding(QualityFindingCode.FIELD_UNAVAILABLE, "mmsi is unavailable", raw, details={"field": "mmsi"})
        )
        return None, FieldAvailability.UNAVAILABLE.value
    try:
        if isinstance(value, bool):
            raise ValueError("boolean is not an MMSI")
        number = int(value)
        if float(value) != number or number < 100_000_000 or number > 999_999_999:
            raise ValueError("MMSI must be a nine-digit integer")
        return number, FieldAvailability.AVAILABLE.value
    except (TypeError, ValueError, OverflowError):
        findings.append(_finding(QualityFindingCode.INVALID_MMSI, "invalid MMSI", raw, details={"value": value}))
        return None, FieldAvailability.INVALID.value


def _normalize_coordinate(
    value: Any,
    field_name: str,
    raw: HistoricalAISRawFact,
    findings: list[HistoricalAISQualityFinding],
    minimum: float,
    maximum: float,
) -> tuple[float | None, str]:
    if value is None or value == "":
        findings.append(
            _finding(
                QualityFindingCode.FIELD_UNAVAILABLE, f"{field_name} is unavailable", raw, details={"field": field_name}
            )
        )
        return None, FieldAvailability.UNAVAILABLE.value
    try:
        number = float(value)
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise ValueError("outside WGS84 coordinate range")
        return number, FieldAvailability.AVAILABLE.value
    except (TypeError, ValueError, OverflowError):
        findings.append(
            _finding(
                QualityFindingCode.INVALID_COORDINATE,
                f"invalid {field_name}",
                raw,
                details={"field": field_name, "value": value},
            )
        )
        return None, FieldAvailability.INVALID.value


def _normalize_measurement(
    value: Any,
    field_name: str,
    raw: HistoricalAISRawFact,
    findings: list[HistoricalAISQualityFinding],
    *,
    sentinel: float,
    invalid_code: QualityFindingCode,
    minimum: float | None = None,
    maximum: float | None = None,
) -> tuple[float | None, str]:
    if value is None or value == "":
        findings.append(
            _finding(
                QualityFindingCode.FIELD_UNAVAILABLE, f"{field_name} is unavailable", raw, details={"field": field_name}
            )
        )
        return None, FieldAvailability.UNAVAILABLE.value
    try:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite value")
        if math.isclose(number, sentinel, rel_tol=0.0, abs_tol=1e-9):
            findings.append(
                _finding(
                    QualityFindingCode.FIELD_UNAVAILABLE_SENTINEL,
                    f"{field_name} contains an AIS unavailable sentinel",
                    raw,
                    details={"field": field_name, "sentinel": sentinel},
                )
            )
            return None, FieldAvailability.UNAVAILABLE.value
        if minimum is not None and number < minimum or maximum is not None and number > maximum:
            raise ValueError("outside AIS range")
        return number, FieldAvailability.AVAILABLE.value
    except (TypeError, ValueError, OverflowError):
        findings.append(_finding(invalid_code, f"invalid {field_name}", raw, details={"field": field_name, "value": value}))
        return None, FieldAvailability.INVALID.value


def _normalize_dimension(
    value: Any,
    field_name: str,
    raw: HistoricalAISRawFact,
    findings: list[HistoricalAISQualityFinding],
) -> tuple[float | None, str]:
    """Retain source dimensions without inventing defaults for missing values."""
    if value is None or value == "":
        findings.append(
            _finding(
                QualityFindingCode.FIELD_UNAVAILABLE, f"{field_name} is unavailable", raw, details={"field": field_name}
            )
        )
        return None, FieldAvailability.UNAVAILABLE.value
    try:
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError("dimension must be finite and non-negative")
        return number, FieldAvailability.AVAILABLE.value
    except (TypeError, ValueError, OverflowError):
        findings.append(
            _finding(
                QualityFindingCode.INVALID_DIMENSION,
                f"invalid {field_name}",
                raw,
                details={"field": field_name, "value": value},
            )
        )
        return None, FieldAvailability.INVALID.value


def _selected_normalized(value: HistoricalAISNormalizedFact, selection: HistoricalAISSelection) -> bool:
    if selection.start_utc is not None and (value.timestamp_utc is None or value.timestamp_utc < selection.start_utc):
        return False
    if selection.end_utc is not None and (value.timestamp_utc is None or value.timestamp_utc >= selection.end_utc):
        return False
    if selection.mmsi and value.mmsi not in selection.mmsi:
        return False
    if selection.bbox is not None:
        if value.longitude_deg is None or value.latitude_deg is None:
            return False
        min_lon, min_lat, max_lon, max_lat = selection.bbox
        if not min_lon <= value.longitude_deg <= max_lon or not min_lat <= value.latitude_deg <= max_lat:
            return False
    if selection.wkt is not None:
        if value.longitude_deg is None or value.latitude_deg is None or wkt is None:
            return False
        try:
            geometry = wkt.loads(selection.wkt)
            if not geometry.covers(_point(value.longitude_deg, value.latitude_deg)):
                return False
        except (GEOSException, TypeError, ValueError):
            raise ValueError("selection wkt is invalid") from None
    return True


def _version_duplicates(
    observations: Sequence[HistoricalAISObservation],
) -> tuple[list[HistoricalAISObservation], list[HistoricalAISQualityFinding]]:
    versioned = list(observations)
    grouped: dict[tuple[datetime | None, int | None], list[tuple[int, HistoricalAISObservation]]] = {}
    for index, observation in enumerate(versioned):
        key = (observation.normalized.timestamp_utc, observation.normalized.mmsi)
        if key[0] is not None and key[1] is not None:
            grouped.setdefault(key, []).append((index, observation))
    findings: list[HistoricalAISQualityFinding] = []
    versions: dict[tuple[str, int], int] = {}
    for key, group in grouped.items():
        items = [item for _, item in group]
        digests = {item.raw.row_sha256 for item in items}
        if len(items) > 1:
            if any(sum(item.raw.row_sha256 == digest for item in items) > 1 for digest in digests):
                findings.append(
                    HistoricalAISQualityFinding(
                        code=QualityFindingCode.EXACT_DUPLICATE,
                        severity=QualitySeverity.WARNING,
                        message="exact duplicate AIS rows retained with versions",
                        entry_name=group[0][1].raw.entry_name,
                        row_indices=tuple(item.raw.source_row_index for item in items),
                        mmsi=key[1],
                        timestamp_utc=key[0],
                        details={"unique_row_digests": len(digests), "retained_rows": len(items)},
                    )
                )
            if len(digests) > 1:
                findings.append(
                    HistoricalAISQualityFinding(
                        code=QualityFindingCode.CONFLICTING_DUPLICATE,
                        severity=QualitySeverity.WARNING,
                        message="conflicting AIS rows share timestamp and MMSI",
                        entry_name=group[0][1].raw.entry_name,
                        row_indices=tuple(item.raw.source_row_index for item in items),
                        mmsi=key[1],
                        timestamp_utc=key[0],
                        details={"unique_row_digests": len(digests), "retained_rows": len(items)},
                    )
                )
        for index, item in sorted(group, key=lambda current: (current[1].raw.entry_name, current[1].raw.source_row_index)):
            version_key = (item.raw.row_sha256, item.normalized.mmsi or -1)
            versions[version_key] = versions.get(version_key, 0)
            current_version = versions[version_key]
            versions[version_key] += 1
            versioned[index] = replace(item, raw=replace(item.raw, duplicate_version=current_version))
    return versioned, findings


def _gap_findings(observations: Sequence[HistoricalAISObservation], threshold_s: float) -> list[HistoricalAISQualityFinding]:
    by_mmsi: dict[int, list[HistoricalAISObservation]] = {}
    for item in observations:
        if item.normalized.mmsi is not None and item.normalized.timestamp_utc is not None:
            by_mmsi.setdefault(item.normalized.mmsi, []).append(item)
    findings: list[HistoricalAISQualityFinding] = []
    for mmsi, values in by_mmsi.items():
        ordered = sorted(values, key=lambda item: item.normalized.timestamp_utc or datetime.min.replace(tzinfo=UTC))
        for previous, current in zip(ordered, ordered[1:], strict=False):
            previous_time = previous.normalized.timestamp_utc
            current_time = current.normalized.timestamp_utc
            if previous_time is None or current_time is None:
                continue
            gap_s = (current_time - previous_time).total_seconds()
            if gap_s > threshold_s:
                findings.append(
                    HistoricalAISQualityFinding(
                        code=QualityFindingCode.OBSERVATION_GAP,
                        severity=QualitySeverity.WARNING,
                        message="AIS observation gap exceeds configured threshold",
                        entry_name=current.raw.entry_name,
                        row_indices=(previous.raw.source_row_index, current.raw.source_row_index),
                        mmsi=mmsi,
                        timestamp_utc=current_time,
                        details={"gap_s": gap_s, "threshold_s": threshold_s},
                    )
                )
    return findings


def _read_parquet_rows(path: Path, selection: HistoricalAISSelection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read one Parquet entry in a process isolated from the map stack.

    ``pyarrow.dataset`` and the GIS stack can load conflicting native
    libraries in one interpreter.  Keep Arrow out of the runtime process and
    exchange only stdlib JSON values through temporary files.  The worker
    still applies the predicates before materializing rows, so ZIP reads stay
    bounded to the requested data.
    """
    with tempfile.TemporaryDirectory(prefix="historical-ais-worker-") as temporary:
        request_path = Path(temporary) / "request.json"
        response_path = Path(temporary) / "response.json"
        request_path.write_text(
            json.dumps(
                {
                    "path": str(path),
                    "selection": _selection_worker_payload(selection),
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "colav_simulator.historical_ais_parquet_worker",
                    str(request_path),
                    str(response_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=300.0,
                cwd=Path(__file__).resolve().parents[1],
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("Historical AIS Parquet worker exceeded its 300 second limit") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "no worker diagnostics"
            raise RuntimeError(f"Historical AIS Parquet worker failed with exit code {completed.returncode}: {detail}")
        if not response_path.is_file():
            raise RuntimeError("Historical AIS Parquet worker exited without a response")
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
            rows = [_worker_decode(row) for row in response["rows"]]
            schema = response["schema"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Historical AIS Parquet worker returned an invalid response") from exc
        if not isinstance(rows, list) or not isinstance(schema, dict):
            raise RuntimeError("Historical AIS Parquet worker returned an invalid response shape")
        return rows, schema


def _read_parquet_rows_in_process(
    path: Path, selection: HistoricalAISSelection
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read Parquet using Arrow; called only by the isolated worker."""
    import pyarrow as pa  # noqa: PLC0415
    import pyarrow.dataset as ds  # noqa: PLC0415

    dataset = ds.dataset(path, format="parquet")
    schema = dataset.schema
    expression: Any = None
    names = set(schema.names)
    timestamp_field = _first_source_name(names, "timestamp")
    mmsi_field = _first_source_name(names, "mmsi")
    longitude_field = _first_source_name(names, "longitude")
    latitude_field = _first_source_name(names, "latitude")
    if selection.mmsi and mmsi_field:
        expression = ds.field(mmsi_field).isin(list(selection.mmsi))
    if selection.bbox and longitude_field and latitude_field:
        min_lon, min_lat, max_lon, max_lat = selection.bbox
        spatial = (ds.field(longitude_field) >= min_lon) & (ds.field(longitude_field) <= max_lon)
        spatial = spatial & (ds.field(latitude_field) >= min_lat) & (ds.field(latitude_field) <= max_lat)
        expression = spatial if expression is None else expression & spatial
    if (
        timestamp_field
        and (selection.start_utc is not None or selection.end_utc is not None)
        and pa.types.is_timestamp(schema.field(timestamp_field).type)
    ):
        field_type = schema.field(timestamp_field).type
        start_value = _arrow_timestamp(selection.start_utc, field_type) if selection.start_utc else None
        end_value = _arrow_timestamp(selection.end_utc, field_type) if selection.end_utc else None
        temporal = None
        if start_value is not None:
            temporal = ds.field(timestamp_field) >= start_value
        if end_value is not None:
            upper = ds.field(timestamp_field) < end_value
            temporal = upper if temporal is None else temporal & upper
        expression = temporal if expression is None else expression & temporal
    scanner = dataset.scanner(filter=expression, batch_size=65_536)
    rows: list[dict[str, Any]] = []
    for batch in scanner.to_batches():
        rows.extend(batch.to_pylist())
    return rows, {"fields": schema.names, "types": [str(schema.field(name).type) for name in schema.names]}


def _read_csv_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(8192)
        stream.seek(0)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.DictReader(stream, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"CSV source has no header: {path}")
        rows = [dict(row) for row in reader]
    return rows, {
        "fields": list(reader.fieldnames),
        "types": ["string"] * len(reader.fieldnames),
        "delimiter": delimiter,
    }


def _schema_fields(documents: Sequence[dict[str, Any]]) -> tuple[HistoricalAISSchemaField, ...]:
    names: set[str] = set()
    for document in documents:
        names.update(document.get("fields", ()))
    output: list[HistoricalAISSchemaField] = []
    mappings = {
        "timestamp": ("timestamp_utc", "UTC", "UTC", "timestamp_to_utc"),
        "mmsi": ("mmsi", None, None, "identity"),
        "longitude": ("longitude_deg", "degrees", "degrees", "WGS84_axis_explicit"),
        "latitude": ("latitude_deg", "degrees", "degrees", "WGS84_axis_explicit"),
        "sog": ("sog_mps", "knots", "m/s", "knots_to_mps"),
        "cog": ("cog_rad", "degrees", "radians", "degrees_to_radians"),
        "heading": ("heading_rad", "degrees", "radians", "degrees_to_radians"),
        "rot": ("rot_radps", "degrees_per_minute", "radians_per_second", "degrees_per_minute_to_radians_per_second"),
        "length": ("length_m", "meters", "meters", "source_dimension_meters_no_conversion"),
        "width": ("width_m", "meters", "meters", "source_dimension_meters_no_conversion"),
        "draft": ("draft_m", "meters", "meters", "source_dimension_meters_no_conversion"),
    }
    for source_field in sorted(names, key=lambda value: (value.lower(), value)):
        semantic = _field_key(source_field)
        mapping = mappings.get(semantic)
        output.append(
            HistoricalAISSchemaField(
                source_field=source_field,
                semantic_field=mapping[0] if mapping else ("geometry" if semantic == "geometry" else None),
                raw_unit=mapping[1] if mapping else None,
                normalized_unit=mapping[2] if mapping else None,
                conversion=mapping[3] if mapping else None,
            )
        )
    return tuple(output)


def _sort_observations(observations: Sequence[HistoricalAISObservation]) -> tuple[HistoricalAISObservation, ...]:
    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.normalized.timestamp_utc is None,
                item.normalized.timestamp_utc or datetime.max.replace(tzinfo=UTC),
                item.normalized.mmsi if item.normalized.mmsi is not None else -1,
                item.raw.entry_name,
                item.raw.source_row_index,
            ),
        )
    )


def _finding_sort_key(finding: HistoricalAISQualityFinding) -> tuple[Any, ...]:
    return (
        finding.timestamp_utc is None,
        finding.timestamp_utc or datetime.max.replace(tzinfo=UTC),
        finding.entry_name or "",
        finding.row_indices,
        finding.code.value,
    )


def _time_extent(observations: Sequence[HistoricalAISObservation]) -> tuple[datetime, datetime] | None:
    values = [item.normalized.timestamp_utc for item in observations if item.normalized.timestamp_utc is not None]
    return (min(values), max(values)) if values else None  # type: ignore[arg-type]


def _spatial_extent(observations: Sequence[HistoricalAISObservation]) -> tuple[float, float, float, float] | None:
    values = [
        (item.normalized.longitude_deg, item.normalized.latitude_deg)
        for item in observations
        if item.normalized.longitude_deg is not None and item.normalized.latitude_deg is not None
    ]
    if not values:
        return None
    longitudes, latitudes = zip(*values, strict=True)
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def _entry_selected(name: str, selection: HistoricalAISSelection) -> bool:
    if not (selection.start_utc or selection.end_utc):
        return True
    match = _ENTRY_DATE_RE.search(Path(name).name)
    if match is None:
        return True
    entry_day = date.fromisoformat(match.group("date"))
    entry_start = datetime.combine(entry_day, datetime.min.time(), tzinfo=UTC)
    entry_end = entry_start + timedelta(days=1)
    if selection.start_utc is not None and entry_end <= selection.start_utc:
        return False
    if selection.end_utc is not None and entry_start >= selection.end_utc:
        return False
    return True


def _selection_worker_payload(selection: HistoricalAISSelection) -> dict[str, Any]:
    return {
        "start_utc": selection.start_utc.isoformat() if selection.start_utc is not None else None,
        "end_utc": selection.end_utc.isoformat() if selection.end_utc is not None else None,
        "mmsi": list(selection.mmsi),
        "bbox": list(selection.bbox) if selection.bbox is not None else None,
        "wkt": selection.wkt,
        "entries": list(selection.entries),
        "gap_threshold_s": selection.gap_threshold_s,
    }


def _worker_encode(value: Any) -> Any:
    """Encode Arrow row values without losing source-type distinctions."""
    if isinstance(value, datetime):
        return {"__historical_ais_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__historical_ais_type__": "date", "value": value.isoformat()}
    if isinstance(value, bytes):
        return {"__historical_ais_type__": "bytes", "value": value.hex()}
    if isinstance(value, memoryview):
        return {"__historical_ais_type__": "bytes", "value": value.tobytes().hex()}
    if isinstance(value, Decimal):
        return {"__historical_ais_type__": "decimal", "value": str(value)}
    if isinstance(value, float) and not math.isfinite(value):
        return {"__historical_ais_type__": "float", "value": repr(value)}
    if isinstance(value, Mapping):
        return {str(key): _worker_encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_worker_encode(item) for item in value]
    if hasattr(value, "item"):
        return _worker_encode(value.item())
    return value


def _worker_decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_worker_decode(item) for item in value]
    if not isinstance(value, Mapping):
        return value
    marker = value.get("__historical_ais_type__")
    if marker == "datetime":
        return datetime.fromisoformat(str(value["value"]))
    if marker == "date":
        return date.fromisoformat(str(value["value"]))
    if marker == "bytes":
        return bytes.fromhex(str(value["value"]))
    if marker == "decimal":
        return Decimal(str(value["value"]))
    if marker == "float":
        return float(str(value["value"]))
    return {str(key): _worker_decode(item) for key, item in value.items()}


def _arrow_timestamp(value: datetime | None, field_type: Any) -> Any:
    import pyarrow as pa  # noqa: PLC0415

    if value is None:
        return None
    if pa.types.is_string(field_type) or pa.types.is_large_string(field_type):
        return pa.scalar(value.isoformat().replace("+00:00", "Z"), type=field_type)
    candidate = value
    if pa.types.is_timestamp(field_type) and field_type.tz is None:
        candidate = value.replace(tzinfo=None)
    return pa.scalar(candidate, type=field_type)


def _materialized_row_value(row: Mapping[str, Any], semantic: str) -> Any:
    return _lookup(row, semantic)


def _lookup(row: Mapping[str, Any], semantic: str) -> Any:
    aliases = _FIELD_ALIASES[semantic]
    candidates = {_field_key(key): key for key in row}
    for alias in aliases:
        key = candidates.get(_field_key(alias))
        if key is not None:
            return row[key]
    return None


def _first_source_name(names: set[str], semantic: str) -> str | None:
    normalized = {_field_key(name): name for name in names}
    for alias in _FIELD_ALIASES[semantic]:
        if _field_key(alias) in normalized:
            return normalized[_field_key(alias)]
    return None


def _field_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _geometry_coordinates(value: Any) -> tuple[Any, Any]:
    if value is None or wkb is None:
        return None, None
    try:
        if isinstance(value, memoryview):
            value = value.tobytes()
        geometry = wkb.loads(value)
        return geometry.x, geometry.y
    except (TypeError, ValueError, AttributeError):
        return None, None


def _point(longitude: float, latitude: float) -> Any:
    return Point(longitude, latitude)


def _finding(
    code: QualityFindingCode,
    message: str,
    raw: HistoricalAISRawFact,
    *,
    details: Mapping[str, Any] | None = None,
) -> HistoricalAISQualityFinding:
    return HistoricalAISQualityFinding(
        code=code,
        severity=QualitySeverity.WARNING
        if code not in {QualityFindingCode.NAIVE_TIMESTAMP_ASSUMED_UTC, QualityFindingCode.FIELD_UNAVAILABLE}
        else QualitySeverity.INFO,
        message=message,
        entry_name=raw.entry_name,
        row_indices=(raw.source_row_index,),
        details=details or {},
    )


def _coerce_utc(value: datetime | str | None, *, allow_none: bool = False) -> datetime | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError("UTC datetime is required")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise TypeError("UTC value must be a datetime, ISO string, or None")
    if parsed.tzinfo is None:
        raise ValueError("selection UTC datetime must be timezone-aware")
    return parsed.astimezone(UTC)


def _is_parquet(name: str) -> bool:
    return str(name).lower().endswith((".parquet", ".parquet.snappy"))


def _is_csv(name: str) -> bool:
    return str(name).lower().endswith((".csv", ".csv.gz"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


# Public vocabulary aliases retained so callers can use either the concise
# seam names or the fully-qualified Historical AIS contract names.
HistoricalAISDatasetSelection = HistoricalAISSelection
HistoricalAISDatasetReadResult = HistoricalAISReadResult
QualityFinding = HistoricalAISQualityFinding

__all__ = [
    "FieldAvailability",
    "HistoricalAISAttribution",
    "HistoricalAISDatasetDescriptor",
    "HistoricalAISDatasetReadResult",
    "HistoricalAISDatasetReader",
    "HistoricalAISEntryDigest",
    "HistoricalAISNormalizedFact",
    "HistoricalAISObservation",
    "HistoricalAISQualityFinding",
    "HistoricalAISRawFact",
    "HistoricalAISReadResult",
    "HistoricalAISSchemaField",
    "HistoricalAISSelection",
    "HistoricalAISDatasetSelection",
    "QualityFinding",
    "QualityFindingCode",
    "QualitySeverity",
]
