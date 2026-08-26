from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from colav_simulator.historical_acceptance import (
    HistoricalAcceptanceStatus,
    HistoricalAISAcceptanceHarness,
    HistoricalAISAcceptanceRequest,
    HistoricalAISDimensionRecord,
    HistoricalAISDimensionRegistry,
    HistoricalRealWindowSelection,
)
from colav_simulator.historical_ais import HistoricalAISSelection
from colav_simulator.historical_enc import ENCRegionProfile

UTC = timezone.utc


def test_acceptance_harness_blocks_missing_source_dimensions_without_defaults(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "kystverket-window.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,10,90\n"
        "2026-07-01T00:00:05Z,123456789,7.0005,62.0,10,90\n"
        "2026-07-01T00:00:10Z,123456789,7.001,62.0,10,90\n"
        "2026-07-01T00:00:20Z,123456789,7.002,62.0,10,90\n"
        "2026-07-01T00:00:00Z,223456789,7.01,62.0,10,270\n"
        "2026-07-01T00:00:05Z,223456789,7.0095,62.0,10,270\n"
        "2026-07-01T00:00:10Z,223456789,7.009,62.0,10,270\n"
        "2026-07-01T00:00:20Z,223456789,7.008,62.0,10,270\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    window = HistoricalRealWindowSelection(
        source_name=source.name,
        archive_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        entry_name=source.name,
        selection=selection,
        reference_mmsi=123456789,
        selected_mmsi=(123456789, 223456789),
        enc_profile_id="case-test",
    )
    outcome = HistoricalAISAcceptanceHarness().run(
        HistoricalAISAcceptanceRequest(
            source=source,
            window=window,
            enc_profile=qualified_historical_enc_profile,
        )
    )

    assert outcome.status is HistoricalAcceptanceStatus.BLOCKED
    assert "DIMENSIONS_UNAVAILABLE" in outcome.blocker_codes
    assert outcome.manifest["dimensions"]["default_dimensions_used"] is False
    assert outcome.manifest["lineage"]["run_digest"] is None


def test_one_minute_real_window_manifest_cannot_qualify_ten_minute_replacement() -> None:
    manifest_path = Path(__file__).parent / "fixtures" / "historical_ais_real_window_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["acceptance_status"] == "SUPERSEDED"
    assert manifest["blocker_code"] == "TEN_MINUTE_REQUALIFICATION_PENDING"
    assert manifest["superseded_by_scenario_id"] == "hais_romsdal_20260701_120007_121007"
    assert manifest["source"]["selection"]["end_utc"] == "2026-07-01T12:01:00+00:00"
    assert manifest["source"]["archive_sha256"] == "d303d719cebaf0238c54b9e27f2a40b4414b26e3189b49cb84fbad4086b3f3d7"
    assert manifest["lineage"]["run_digest"]
    assert manifest["lineage"]["evaluation_digest"]
    assert manifest["lineage"]["compare_digest"] == manifest["compare"]["compare_digest"]
    assert (
        len(
            {
                manifest["dataset"]["descriptor_sha256"],
                manifest["case"]["runtime_actor_set_digest"],
                manifest["case"]["case_digest"],
            }
        )
        == 3
    )
    assert manifest["sealed_evidence"]["run_manifest_sha256"]
    assert manifest["sealed_evidence"]["evaluation_artifact_sha256"]
    assert manifest["determinism"]["status"] == "PASS"
    assert manifest["determinism"]["mismatches"] == []
    assert len(manifest["runs"]) == 2
    assert manifest["runs"][0]["run_id"] != manifest["runs"][1]["run_id"]
    assert all(
        manifest["runs"][0][field] == manifest["runs"][1][field] for field in manifest["determinism"]["compared_fields"]
    )
    assert manifest["runs"][0]["threat_graph_evidence_hash"] != manifest["runs"][1]["threat_graph_evidence_hash"]
    assert manifest["runs"][0]["threat_graph_semantic_hash"] == manifest["runs"][1]["threat_graph_semantic_hash"]
    assert manifest["lineage"]["compare_digest"] == manifest["compare"]["compare_digest"]
    assert manifest_path.stat().st_size < 12_000


def test_acceptance_harness_requires_bindings_with_scoped_dimension_registry(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "registry-window.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,10,90\n"
        "2026-07-01T00:00:05Z,123456789,7.0005,62.0,10,90\n"
        "2026-07-01T00:00:10Z,123456789,7.001,62.0,10,90\n"
        "2026-07-01T00:00:20Z,123456789,7.002,62.0,10,90\n"
        "2026-07-01T00:00:00Z,223456789,7.01,62.0,10,270\n"
        "2026-07-01T00:00:05Z,223456789,7.0095,62.0,10,270\n"
        "2026-07-01T00:00:10Z,223456789,7.009,62.0,10,270\n"
        "2026-07-01T00:00:20Z,223456789,7.008,62.0,10,270\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    window = HistoricalRealWindowSelection(
        source_name=source.name,
        archive_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        entry_name=source.name,
        selection=selection,
        reference_mmsi=123456789,
        selected_mmsi=(123456789, 223456789),
        enc_profile_id="case-test",
        dimension_registry_id="test-window-dimensions",
        t0_utc="2026-07-01T00:00:10+00:00",
    )
    registry = HistoricalAISDimensionRegistry(
        registry_id="test-window-dimensions",
        registry_version="1.0.0",
        scope="test-window-only",
        retrieved_at_utc="2026-08-21T00:00:00Z",
        source_note="test source note",
        source_note_sha256="note-sha256",
        records=(
            HistoricalAISDimensionRecord(
                mmsi=123456789,
                length_m=40.0,
                width_m=8.0,
                provenance="test measurement certificate",
                source_digest="source-a",
                imo=9000001,
                measurement_date="2020-01-01",
                effective_date="2020-01-02",
                journal_date="2020-01-02",
                retrieved_at_utc="2026-08-21T00:00:00Z",
                effective_as_of_t0=True,
            ),
            HistoricalAISDimensionRecord(
                mmsi=223456789,
                length_m=35.0,
                width_m=7.0,
                provenance="test measurement certificate",
                source_digest="source-b",
                imo=9000002,
                measurement_date="2020-01-01",
                effective_date="2020-01-02",
                journal_date="2020-01-02",
                retrieved_at_utc="2026-08-21T00:00:00Z",
                effective_as_of_t0=True,
            ),
        ),
    )
    outcome = HistoricalAISAcceptanceHarness().run(
        HistoricalAISAcceptanceRequest(
            source=source,
            window=window,
            enc_profile=qualified_historical_enc_profile,
            dimension_registry=registry,
        )
    )

    assert outcome.status is HistoricalAcceptanceStatus.BLOCKED
    assert outcome.blocker_codes == ("BINDINGS_UNAVAILABLE",)
    assert outcome.case_outcome is not None and outcome.case_outcome.case is None
    assert outcome.manifest["dimensions"]["registry_digest"] == registry.digest

    for invalid_record in (
        replace(registry.records[0], effective_as_of_t0=False),
        replace(registry.records[0], measurement_date="2026-07-02"),
        replace(registry.records[0], effective_date="2026-07-02"),
    ):
        invalid_registry = replace(registry, records=(invalid_record, registry.records[1]))
        blocked = HistoricalAISAcceptanceHarness().run(
            HistoricalAISAcceptanceRequest(
                source=source,
                window=window,
                enc_profile=qualified_historical_enc_profile,
                dimension_registry=invalid_registry,
            )
        )
        assert blocked.status is HistoricalAcceptanceStatus.BLOCKED
        assert blocked.blocker_codes == ("DIMENSION_PROVENANCE_INVALID",)
