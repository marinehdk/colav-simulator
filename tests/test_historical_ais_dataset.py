from __future__ import annotations

import math
import subprocess
import sys
import zipfile
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from colav_simulator.historical_ais import (
    HistoricalAISDatasetReader,
    HistoricalAISSelection,
    QualityFindingCode,
)

UTC = timezone.utc


def _write_csv(path: Path, rows: str) -> Path:
    path.write_text(rows, encoding="utf-8")
    return path


def _write_parquet_pair(first: Path, second: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from datetime import datetime; from decimal import Decimal; "
                "import pyarrow as pa; import pyarrow.parquet as pq; "
                "table = pa.table({'date_time_utc': pa.array([datetime(2026, 7, 1, 0, 0), "
                "datetime(2026, 7, 1, 0, 1)], type=pa.timestamp('ns')), "
                "'mmsi': pa.array([123456789, 222222222], type=pa.int64()), "
                "'longitude': pa.array([7.1, 9.0]), 'latitude': pa.array([62.0, 62.0]), "
                "'speed_over_ground': pa.array([10.0, 2.0]), "
                "'course_over_ground': pa.array([90.0, 180.0]), "
                "'true_heading': pa.array([91, 181], type=pa.int16()), "
                "'rate_of_turn': pa.array([0, 0], type=pa.int8()), "
                "'draft': pa.array([Decimal('4.0'), Decimal('2.0')], type=pa.decimal128(10, 2)), "
                "'ais_class': pa.array(['A', 'A']), 'data_source': pa.array(['G', 'G'])}); "
                "pq.write_table(table, sys.argv[1]); "
                "pq.write_table(table.replace_schema_metadata({b'geo': b'crs=OGC:CRS84'}), sys.argv[2])"
            ),
            str(first),
            str(second),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_compact_offline_fixture_is_schema_valid() -> None:
    fixture = Path(__file__).parent / "fixtures" / "historical_ais_compact.csv"

    result = HistoricalAISDatasetReader(fixture).read()

    assert result.descriptor.source_row_count == 2
    assert len(result.observations) == 2
    assert result.observations[0].normalized.length_m == pytest.approx(40)
    assert result.observations[1].normalized.length_m is None


def test_csv_read_exposes_immutable_descriptor_raw_and_normalized_facts(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "compact.csv",
        "BaseDateTime,MMSI,LON,LAT,SOG,COG,Heading,Status,Length,Width,Draft\n"
        "2026-07-01T00:00:02Z,123456789,7.2,62.1,10,90,91,0,40,8,4\n"
        "2026-07-01T00:00:01Z,123456789,7.1,62.0,5,180,181,0,,,\n",
    )

    result = HistoricalAISDatasetReader(source).read(
        HistoricalAISSelection(
            start_utc="2026-07-01T00:00:00Z",
            end_utc="2026-07-01T00:00:03Z",
            mmsi=(123456789,),
            bbox=(7.0, 61.9, 7.3, 62.2),
        )
    )

    assert result.descriptor.provider == "Kystverket"
    assert result.descriptor.format == "csv"
    assert result.descriptor.source_crs == "OGC:CRS84"
    assert result.descriptor.normalized_crs == "EPSG:4326"
    assert result.descriptor.geodetic_datum == "WGS84"
    assert len(result.descriptor.archive_sha256) == 64
    assert len(result.descriptor.schema_sha256) == 64
    assert len(result.descriptor.selection_sha256) == 64
    assert result.descriptor.attribution.nlod_license == "NLOD 2.0"
    assert result.descriptor.source_identity_unverified is True
    assert result.descriptor.coverage_limitations

    assert [item.normalized.timestamp_utc for item in result.observations] == [
        datetime(2026, 7, 1, 0, 0, 1, tzinfo=UTC),
        datetime(2026, 7, 1, 0, 0, 2, tzinfo=UTC),
    ]
    first = result.observations[0]
    assert first.raw.values["SOG"] == "5"
    assert first.normalized.sog_mps == pytest.approx(5 * 0.514444)
    assert first.normalized.cog_rad == pytest.approx(math.pi)
    assert first.normalized.heading_rad == pytest.approx(math.radians(181))
    assert first.normalized.length_m is None
    assert {"length_m", "width_m", "draft_m"}.issubset(first.normalized.unavailable_fields)
    dimensioned = result.observations[1].normalized
    assert dimensioned.length_m == pytest.approx(40)
    assert dimensioned.width_m == pytest.approx(8)
    assert dimensioned.draft_m == pytest.approx(4)
    assert first.normalized.source_crs == "OGC:CRS84"
    assert first.normalized.coordinate_axis_order == "longitude_latitude"
    assert first.normalized.conversion_provenance["sog_mps"] == "knots_to_mps"
    assert first.normalized.conversion_provenance["cog_rad"] == "degrees_to_radians"

    with pytest.raises(FrozenInstanceError):
        result.descriptor.provider = "other"  # type: ignore[misc]
    assert result.descriptor.raw_content_digest == result.descriptor.archive_sha256
    assert result.descriptor.normalized_sha256


def test_zip_daily_parquet_selection_reads_only_selected_entry_and_supports_wkt(tmp_path: Path) -> None:
    first = tmp_path / "hais_2026-07-01.snappy.parquet"
    second = tmp_path / "hais_2026-07-02.snappy.parquet"
    _write_parquet_pair(first, second)
    archive = tmp_path / "hais.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(first, first.name)
        bundle.write(second, second.name)

    result = HistoricalAISDatasetReader(archive).read(
        HistoricalAISSelection(
            start_utc=datetime(2026, 7, 1, tzinfo=UTC),
            end_utc=datetime(2026, 7, 1, 0, 2, tzinfo=UTC),
            wkt="POLYGON ((7 61, 8 61, 8 63, 7 63, 7 61))",
        )
    )

    assert result.descriptor.format == "parquet"
    assert result.descriptor.entries == ("hais_2026-07-01.snappy.parquet",)
    assert len(result.descriptor.entry_digests) == 1
    assert len(result.observations) == 1
    assert result.observations[0].normalized.mmsi == 123456789
    assert result.observations[0].normalized.sog_mps == pytest.approx(10 * 0.514444)
    assert result.observations[0].normalized.draft_m == pytest.approx(4.0)


def test_quality_findings_keep_duplicates_and_type_unavailable_sentinels(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "quality.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,true_heading,rate_of_turn\n"
        "2026-07-01T00:00:00,123456789,7,62,10,90,91,0\n"
        "2026-07-01T00:00:00,123456789,7,62,10,90,91,0\n"
        "2026-07-01T00:00:00,123456789,7.1,62,10,90,91,0\n"
        "2026-07-01T00:10:00,123456789,181,95,102.3,360,511,-128\n",
    )

    result = HistoricalAISDatasetReader(source).read(HistoricalAISSelection(gap_threshold_s=300))
    codes = {finding.code for finding in result.descriptor.quality_findings}

    assert QualityFindingCode.EXACT_DUPLICATE in codes
    assert QualityFindingCode.CONFLICTING_DUPLICATE in codes
    assert QualityFindingCode.OBSERVATION_GAP in codes
    assert QualityFindingCode.INVALID_COORDINATE in codes
    assert QualityFindingCode.FIELD_UNAVAILABLE_SENTINEL in codes
    assert [item.raw.duplicate_version for item in result.observations[:2]] == [0, 1]
    sentinel = result.observations[-1].normalized
    assert sentinel.sog_mps is None
    assert sentinel.cog_rad is None
    assert sentinel.heading_rad is None
    assert sentinel.rot_radps is None
    assert {"sog_mps", "cog_rad", "heading_rad", "rot_radps"}.issubset(sentinel.unavailable_fields)


def test_source_digest_changes_when_one_source_byte_changes(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "source.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground\n"
        "2026-07-01T00:00:00Z,123456789,7,62,1,0\n",
    )
    reader = HistoricalAISDatasetReader(source)
    first = reader.read(HistoricalAISSelection()).descriptor
    source.write_bytes(source.read_bytes().replace(b",1,0", b",2,0"))
    second = reader.read(HistoricalAISSelection()).descriptor

    assert first.archive_sha256 != second.archive_sha256
    assert first.normalized_sha256 != second.normalized_sha256
    assert first.descriptor_sha256 != second.descriptor_sha256


def test_legacy_semicolon_csv_uses_the_same_normalized_contract(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "legacy.csv",
        "mmsi;date_time_utc;lat;lon;sog;cog\n123456789;2026-07-01T00:00:00Z;62;7;2;90\n",
    )

    result = HistoricalAISDatasetReader(source).read()

    assert result.descriptor.format == "csv"
    assert len(result.observations) == 1
    assert result.observations[0].normalized.sog_mps == pytest.approx(2 * 0.514444)


def test_negative_speed_is_retained_as_typed_quality_failure(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "negative-speed.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground\n2026-07-01T00:00:00Z,123456789,7,62,-1\n",
    )

    result = HistoricalAISDatasetReader(source).read()

    assert result.observations[0].normalized.sog_mps is None
    assert QualityFindingCode.INVALID_SPEED in {finding.code for finding in result.descriptor.quality_findings}
