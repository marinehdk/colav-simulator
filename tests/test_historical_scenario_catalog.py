from __future__ import annotations

import json
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_enc import ENCRegionProfile
from colav_simulator.historical_scenario_assembly import HistoricalAISSceneAssembler
from colav_simulator.historical_scenario_catalog import (
    HISTORICAL_AIS_SCENARIO_ID,
    HistoricalAISScenarioCatalog,
    HistoricalAISScenarioError,
    HistoricalAISScenarioReadiness,
    HistoricalAISScenarioSourceReadiness,
)
from gui_server.main import app


def test_catalog_publishes_one_independent_bounded_ais_scene(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    descriptor = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)

    assert descriptor.scenario_id == "hais_romsdal_20260701_120000_120100"
    assert descriptor.kind == "HISTORICAL_AIS"
    assert descriptor.modes == ("HISTORICAL_REPLAY", "COUNTERFACTUAL")
    assert descriptor.archive_scope["day_count"] == 23
    assert descriptor.archive_scope["row_count"] == 51_522_509
    assert descriptor.archive_scope["union_mmsi_count"] == 1_226
    assert descriptor.current_window["source_row_count"] == 24
    assert descriptor.current_window["selection_filter_mmsi_count"] == 4
    assert descriptor.current_window["runtime_actor_count"] == 3
    assert descriptor.current_window["target_mmsi"] == (257252000, 258764000)
    assert descriptor.current_window["reference_mmsi"] == 259189000
    assert "CURRENT_WINDOW_ONLY" in descriptor.limitations
    assert "CURRENT_ACTOR_SET_ONLY" in descriptor.limitations
    assert "ARCHIVE_NOT_FULLY_ENC_QUALIFIED" in descriptor.limitations
    assert descriptor.readiness().status is HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING

    document = descriptor.to_dict()
    assert descriptor.descriptor_sha256 == descriptor.to_dict()["descriptor_sha256"]
    assert "/Users/" not in json.dumps(document)
    assert "Downloads" not in json.dumps(document)


def test_descriptor_is_deeply_immutable_and_separates_capability_evidence() -> None:
    descriptor = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)

    assert descriptor.runtime_binding["historical_scenario_id"] == HISTORICAL_AIS_SCENARIO_ID
    assert "paper_ccta2023_multiship" not in json.dumps(descriptor.to_dict()["runtime_binding"])
    evidence = descriptor.algorithm_capability_evidence
    assert evidence["binding_role"] == "ALGORITHM_CAPABILITY_ONLY"
    assert evidence["geometry_equivalence"] is False
    assert evidence["exact_tuple"] == (
        "multiship",
        "paper_ccta2023_multiship",
        "mid_mpc_ipopt",
        "god",
    )

    with pytest.raises(TypeError):
        descriptor.current_window["bbox"][0] = 0.0
    with pytest.raises(TypeError):
        descriptor.dimensions["records"][0]["length_m"] = 1.0
    with pytest.raises(TypeError):
        descriptor.runtime_binding["domain_profile"]["fore_m"] = 1.0


def test_descriptor_digest_covers_nested_facts(tmp_path) -> None:
    original = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)
    source = Path(__file__).parents[1] / "colav_simulator" / "data" / "historical_ais_scenarios.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    document["dimensions"]["records"][0]["length_m"] = 84.7
    changed_path = tmp_path / "historical_ais_scenarios.json"
    changed_path.write_text(json.dumps(document), encoding="utf-8")

    changed = HistoricalAISScenarioCatalog(changed_path).get(HISTORICAL_AIS_SCENARIO_ID)

    assert changed.descriptor_sha256 != original.descriptor_sha256


@pytest.mark.parametrize("tampered_field", ("normalized_sha256", "descriptor_sha256"))
def test_bound_scene_rejects_tampered_derived_dataset_identity(tampered_field: str) -> None:
    descriptor = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)
    window = descriptor.current_window
    values = {
        "archive_sha256": descriptor.archive_sha256,
        "schema_sha256": window["expected_schema_sha256"],
        "selection_sha256": window["expected_selection_sha256"],
        "normalized_sha256": window["expected_normalized_sha256"],
        "descriptor_sha256": window["expected_descriptor_sha256"],
        "entry_digests": (
            SimpleNamespace(
                entry_name=window["entry_name"],
                sha256=window["entry_sha256"],
                uncompressed_bytes=window["entry_uncompressed_bytes"],
            ),
        ),
    }
    values[tampered_field] = "0" * 64

    with pytest.raises(HistoricalAISScenarioError) as raised:
        HistoricalAISSceneAssembler.validate_dataset_identity(
            descriptor,
            SimpleNamespace(descriptor=SimpleNamespace(**values)),
        )

    assert raised.value.status is HistoricalAISScenarioReadiness.DATASET_IDENTITY_MISMATCH
    assert tampered_field in str(raised.value)


def test_replay_binding_succeeds_without_encounter_or_intent_while_counterfactual_fails_typed(
    tmp_path: Path,
    qualified_historical_enc_profile: ENCRegionProfile,
) -> None:
    source = tmp_path / "no-encounter.csv"
    rows = ["date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground"]
    for mmsi, longitude in ((257252000, 7.0), (258764000, 7.1), (259189000, 7.2)):
        for second, offset in ((0, 0.0), (10, 0.001), (20, 0.002)):
            rows.append(f"2026-07-01T00:00:{second:02d}Z,{mmsi},{longitude + offset},62.0,10,90")
    source.write_text("\n".join(rows) + "\n", encoding="utf-8")
    selection = HistoricalAISSelection(
        start_utc="2026-07-01T00:00:00+00:00",
        end_utc="2026-07-01T00:01:00+00:00",
        mmsi=(257252000, 258764000, 259189000),
        bbox=(6.9, 61.9, 7.3, 62.1),
        entries=(source.name,),
    )
    observed = HistoricalAISDatasetReader(source).read(selection).descriptor
    base_path = Path(__file__).parents[1] / "colav_simulator" / "data" / "historical_ais_scenarios.json"
    document = json.loads(base_path.read_text(encoding="utf-8"))
    window = document["current_window"]
    window.update(
        {
            "entry_name": source.name,
            "start_utc": "2026-07-01T00:00:00+00:00",
            "end_utc": "2026-07-01T00:01:00+00:00",
            "t0_utc": "2026-07-01T00:00:10+00:00",
            "bbox": [6.9, 61.9, 7.3, 62.1],
            "selection_mmsi": [257252000, 258764000, 259189000],
            "runtime_mmsi": [257252000, 258764000, 259189000],
            "selected_mmsi": [257252000, 258764000, 259189000],
            "selection_filter_mmsi_count": 3,
            "source_row_count": 9,
            "normalized_row_count": 9,
            "expected_schema_sha256": observed.schema_sha256,
            "expected_selection_sha256": observed.selection_sha256,
            "expected_normalized_sha256": observed.normalized_sha256,
            "expected_descriptor_sha256": observed.descriptor_sha256,
            "entry_sha256": observed.entry_digests[0].sha256,
            "entry_uncompressed_bytes": observed.entry_digests[0].uncompressed_bytes,
            "entry_crc32": zlib.crc32(source.read_bytes()),
        }
    )
    document["archive_scope"]["source_name"] = source.name
    document["archive_scope"]["archive_sha256"] = observed.archive_sha256
    document["source_binding"]["expected_archive_sha256"] = observed.archive_sha256
    document["enc"]["profile_id"] = qualified_historical_enc_profile.profile_id
    document["enc"]["profile_digest"] = qualified_historical_enc_profile.profile_digest
    descriptor_path = tmp_path / "historical_ais_scenarios.json"
    descriptor_path.write_text(json.dumps(document), encoding="utf-8")
    descriptor = HistoricalAISScenarioCatalog(descriptor_path).get(HISTORICAL_AIS_SCENARIO_ID)
    enc_calls = {"count": 0}

    def build_enc() -> ENCRegionProfile:
        enc_calls["count"] += 1
        return qualified_historical_enc_profile

    assembler = HistoricalAISSceneAssembler(enc_builder=build_enc)
    environ = {"COLAV_HAIS_ARCHIVE_PATH": str(source)}

    replay = assembler.bind_replay(descriptor, environ=environ)

    assert replay.dataset.descriptor.descriptor_sha256 == observed.descriptor_sha256
    assert not hasattr(replay, "enc_profile")
    assert not hasattr(replay, "case")
    assert not hasattr(replay, "human_reference")
    assert enc_calls["count"] == 0
    assert replay.replay_workflow_payload()["mode"] == "HISTORICAL_REPLAY"
    with pytest.raises(HistoricalAISScenarioError) as raised:
        assembler.bind_counterfactual(descriptor, environ=environ)
    assert raised.value.status is HistoricalAISScenarioReadiness.CASE_BUILD_FAILED
    assert enc_calls["count"] == 1


def test_published_presentation_keeps_scene_qualification_and_runtime_separate(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    document = HistoricalAISScenarioCatalog().document(HISTORICAL_AIS_SCENARIO_ID)

    assert document["presentation"]["scenario"] == {
        "id": HISTORICAL_AIS_SCENARIO_ID,
        "kind": "HISTORICAL_AIS",
    }
    assert document["presentation"]["operability"] == {"status": "UNAVAILABLE", "scope": "BOUNDED"}
    assert document["presentation"]["qualification"]["status"] == "NOT_QUALIFIED"
    assert document["presentation"]["runtime"]["modes"] == ["HISTORICAL_REPLAY", "COUNTERFACTUAL"]
    assert document["presentation"]["digests"]["descriptor_sha256"] == document["descriptor_sha256"]
    assert document["presentation"]["digests"]["entry_sha256"] == document["current_window"]["entry_sha256"]


def test_ready_bounded_scene_does_not_claim_predictive_cluster_qualification() -> None:
    descriptor = HistoricalAISScenarioCatalog().get(HISTORICAL_AIS_SCENARIO_ID)
    ready = HistoricalAISScenarioSourceReadiness(
        HistoricalAISScenarioReadiness.READY,
        descriptor.archive_sha256,
        descriptor.archive_sha256,
    )

    presentation = descriptor.presentation(ready)

    assert presentation["operability"] == {"status": "AVAILABLE", "scope": "BOUNDED"}
    assert presentation["qualification"]["status"] == "NOT_QUALIFIED"
    assert presentation["qualification"]["code"] == "THREAT_EVIDENCE_INCOMPLETE"
    assert presentation["qualification"]["source_readiness"] == "READY"
    assert presentation["digests"]["enc_profile_sha256"] == descriptor.enc["profile_digest"]
    assert presentation["digests"]["enc_cache_sha256"] is None
    assert presentation["digests"]["enc_source_sha256"] is None
    assert presentation["digests"]["dimension_registry_sha256"]
    assert presentation["digests"]["dimension_source_sha256"]
    serialized = json.dumps(descriptor.to_dict())
    assert "expected_cluster_count" not in serialized
    assert "sealed_expected_cluster" not in serialized


def test_historical_scenario_catalog_api_is_separate_from_legacy_scenarios(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        scenarios = client.get("/api/historical/scenarios")
        descriptor = client.get(f"/api/historical/scenarios/{HISTORICAL_AIS_SCENARIO_ID}")
        legacy = client.get("/api/scenarios")

    assert scenarios.status_code == 200
    assert [item["id"] for item in scenarios.json()] == [HISTORICAL_AIS_SCENARIO_ID]
    assert descriptor.status_code == 200
    assert descriptor.json()["kind"] == "HISTORICAL_AIS"
    assert descriptor.json()["readiness"]["status"] == "SOURCE_BINDING_MISSING"
    assert HISTORICAL_AIS_SCENARIO_ID not in {item["id"] for item in legacy.json()}


def test_historical_scenario_workflow_creation_fails_closed_without_archive_binding(monkeypatch) -> None:
    monkeypatch.delenv("COLAV_HAIS_ARCHIVE_PATH", raising=False)
    with TestClient(app) as client:
        response = client.post(
            f"/api/historical/scenarios/{HISTORICAL_AIS_SCENARIO_ID}/workflows",
            json={"mode": "HISTORICAL_REPLAY"},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "SOURCE_BINDING_MISSING"
