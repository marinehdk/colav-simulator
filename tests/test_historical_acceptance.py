from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
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


def test_real_window_manifest_is_compact_and_records_latest_real_pass() -> None:
    manifest_path = Path(__file__).parent / "fixtures" / "historical_ais_real_window_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["acceptance_status"] == "PASS"
    assert manifest["blocker_code"] is None
    assert manifest["dimensions"]["default_dimensions_used"] is False
    assert manifest["dimensions"]["registry_applied"] is True
    assert manifest["dimensions"]["effective_dimensioned_actor_count"] == 3
    assert manifest["dimensions"]["explicit_overrides"] == []
    assert manifest["dimensions"]["source_audit"]["status"] == "CONFIRMED_FIRST_PARTY"
    assert manifest["discovery"]["multi_ship"] is True
    assert manifest["discovery"]["authority"] == "DISCOVERY_ONLY"
    assert manifest["enc_preflight"]["status"] == "PASS"
    assert manifest["case"]["status"] == "SUCCESS"
    assert manifest["run"]["fallback_used"] is False
    assert manifest["run"]["requested_algorithm"] == manifest["run"]["executed_algorithm"]
    assert manifest["leakage"]["human_reference_digest_in_run_spec"] is False
    assert manifest["leakage"]["nominal_intent_strict_pre_t0_only"] is True
    assert manifest["threat"]["vector_count"] == 2
    assert manifest["threat"]["schedule_context_count"] == 2
    assert manifest["threat"]["cluster_count"] == 0
    assert manifest["threat"]["gate"] == "PASS"
    assert manifest["evaluation"]["evaluator_gate"] == "PASS"
    assert manifest["compare"]["status"] == "COMPLETE"
    assert manifest["source"]["archive_sha256"] == "d303d719cebaf0238c54b9e27f2a40b4414b26e3189b49cb84fbad4086b3f3d7"
    assert manifest["lineage"]["run_digest"]
    assert manifest["lineage"]["evaluation_digest"]
    assert manifest["lineage"]["compare_digest"] is None
    assert manifest["lineage"]["compare_digest_unavailable_reason"]
    assert manifest_path.stat().st_size < 10_000


def test_acceptance_harness_accepts_only_scoped_provenanced_dimension_registry(
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

    assert outcome.status is HistoricalAcceptanceStatus.PASS
    assert outcome.case_outcome is not None and outcome.case_outcome.case is not None
    assert outcome.case_outcome.case.reference_actor.dimensions_provenance.startswith("explicit:")
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
