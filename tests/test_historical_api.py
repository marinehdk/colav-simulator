from __future__ import annotations

import zlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.historical_acceptance import HistoricalAISDimensionRecord, HistoricalAISDimensionRegistry
from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_enc import ENCRegionProfile
from gui_server import historical_api
from gui_server.main import app

UTC = timezone.utc


def _source(path: Path) -> Path:
    path.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,180,40,8\n"
        "2026-07-01T00:00:30Z,123456789,7.0012,61.9994,10,180,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:30Z,223456789,7.0082,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    return path


def _enc_document(profile: ENCRegionProfile) -> dict[str, object]:
    return {
        **profile.to_dict(),
        "coverage_geometry_wkb_hex": profile.coverage_geometry_wkb.hex(),
        "hazard_geometry_wkb_hex": profile.hazard_geometry_wkb.hex(),
        "navigability_geometry_wkb_hex": profile.navigability_geometry_wkb.hex(),
    }


def _dimension_registry_document(*mmsi: int) -> dict[str, object]:
    registry = HistoricalAISDimensionRegistry(
        registry_id="historical-api-test-dimensions",
        registry_version="1.0.0",
        scope="historical API compact fixture",
        retrieved_at_utc="2026-08-21T00:00:00Z",
        source_note="compact first-party test certificate",
        source_note_sha256="test-note-sha256",
        records=tuple(
            HistoricalAISDimensionRecord(
                mmsi=value,
                length_m=40.0,
                width_m=8.0,
                provenance="test measurement certificate",
                source_digest=f"test-certificate-{value}",
                measurement_date="2020-01-01",
                effective_date="2020-01-02",
                journal_date="2020-01-02",
                retrieved_at_utc="2026-08-21T00:00:00Z",
                effective_as_of_t0=True,
            )
            for value in mmsi
        ),
    )
    return {**registry.to_dict(), "registry_digest": registry.digest}


def _request(tmp_path: Path, profile: ENCRegionProfile) -> dict[str, object]:
    source = _source(tmp_path / "historical-api.csv")
    selection_document = {
        "start_utc": datetime(2026, 7, 1, tzinfo=UTC).isoformat(),
        "end_utc": datetime(2026, 7, 1, 0, 1, tzinfo=UTC).isoformat(),
    }
    descriptor = HistoricalAISDatasetReader(source).read(HistoricalAISSelection(**selection_document)).descriptor
    entry = descriptor.entry_digests[0]
    human_positions = tuple(profile.projection.project_wgs84(point) for point in ((7.0012, 62.0000), (7.0012, 61.9994)))
    return {
        "mode": "COUNTERFACTUAL",
        "source_path": str(source),
        "selection": selection_document,
        "expected_archive_sha256": descriptor.archive_sha256,
        "expected_schema_sha256": descriptor.schema_sha256,
        "expected_selection_sha256": descriptor.selection_sha256,
        "expected_normalized_sha256": descriptor.normalized_sha256,
        "expected_descriptor_sha256": descriptor.descriptor_sha256,
        "expected_entries": [
            {
                "entry_name": entry.entry_name,
                "sha256": entry.sha256,
                "uncompressed_bytes": entry.uncompressed_bytes,
                "crc32": zlib.crc32(source.read_bytes()),
            }
        ],
        "enc_profile": _enc_document(profile),
        "case": {
            "published": True,
            "reference_mmsi": 123456789,
            "t0_utc": datetime(2026, 7, 1, 0, 0, 20, tzinfo=UTC).isoformat(),
            "discovery_profile": {"max_encounter_range_m": 2_000.0, "min_closing_speed_mps": 0.0},
        },
        "run_spec": {
            "scenario_id": "overtaking",
            "validation_rule_id": "rule13",
            "algorithm_id": "nominal",
            "tracker_id": "god",
            "t_end": 30.0,
            "terminate_on_collision_or_grounding": False,
            "output_root": str(tmp_path / "runs"),
        },
        "human_reference": {
            "timestamps_s": [20.0, 30.0],
            "positions_xy": [list(point) for point in human_positions],
            "courses_rad": [1.5707963267948966, 3.141592653589793],
            "speeds_mps": [5.14444, 5.14444],
            "source": "HUMAN_REFERENCE_FIXTURE",
        },
    }


def test_historical_api_uses_normal_session_and_publishes_final_evidence(
    tmp_path: Path,
    qualified_historical_enc_profile: ENCRegionProfile,
) -> None:
    with TestClient(app) as client:
        prepared = client.post(
            "/api/historical/workflows",
            json=_request(tmp_path, qualified_historical_enc_profile),
        )
        assert prepared.status_code == 200, prepared.json()
        workflow_id = prepared.json()["workflow_id"]
        assert prepared.json()["status"] == "PREPARED"
        assert prepared.json()["evidence"]["dataset_descriptor"]["descriptor_sha256"]
        assert prepared.json()["evidence"]["case"]["enc_preflight"]["status"] == "PASS"
        assert prepared.json()["presentation"] == {
            "schema_version": "historical-workflow.presentation.v1",
            "scenario": {"id": None, "kind": "AD_HOC_HISTORICAL_WORKFLOW"},
            "operability": {"status": "AVAILABLE", "scope": "AD_HOC"},
            "qualification": {
                **prepared.json()["qualification"],
                "determinism": {"status": "NOT_CHECKED", "mismatch_count": None},
                "threat_graph": None,
            },
            "runtime": {
                "mode": "COUNTERFACTUAL",
                "status": "PREPARED",
                "requested_algorithm": None,
                "executed_algorithm": None,
                "fallback_used": None,
            },
            "threat": {
                "status": "UNAVAILABLE",
                "vector_count": None,
                "schedule_entry_count": None,
                "cluster_count": None,
            },
            "leakage": {"status": "PASS_CONTRACT"},
            "determinism": {"status": "NOT_CHECKED", "mismatch_count": None},
            "compare": {
                "status": "UNAVAILABLE",
                "overall_assurance_verdict": None,
                "domain_statuses": {
                    "safety": None,
                    "colreg": None,
                    "maneuver": None,
                    "efficiency": None,
                    "human_similarity": None,
                },
            },
            "evidence": {
                "lineage": prepared.json()["lineage"],
                "replay": {
                    "status": "NOT_APPLICABLE",
                    "mode": None,
                    "factory": None,
                    "dataset_digest": None,
                    "runtime_actor_set_digest": None,
                    "trajectory_digest": None,
                    "manifest_digest": None,
                    "dimension_registry_digest": None,
                    "dimension_source_digest": None,
                },
            },
        }

        executed = client.post(f"/api/historical/workflows/{workflow_id}/run")
        assert executed.status_code == 200, executed.json()
        final = client.get(f"/api/historical/workflows/{workflow_id}")
        assert final.status_code == 200
        document = final.json()
        assert document["status"] == "COMPLETED"
        assert document["qualification"] == {
            "status": "NOT_QUALIFIED",
            "execution_mode": "RUN_ONLY",
            "run_count": 1,
            "reason": "single Counterfactual run is not deterministic qualification evidence",
        }
        assert document["stages"] == {
            "dataset": "SELECTED",
            "case": "PUBLISHED",
            "replay": "NOT_APPLICABLE",
            "counterfactual": "COMPLETED",
            "evaluation": "COMPLETE",
            "compare": document["compare"]["status"],
        }
        assert all(document["lineage"].values())
        assert document["leakage"]["human_reference_digest_in_run_spec"] is False
        assert document["final_snapshot"]
        assert document["evidence"]["evaluation"]
        assert document["evidence"]["compare_digest"] == document["lineage"]["compare_digest"]
        presentation = document["presentation"]
        assert presentation["runtime"]["fallback_used"] is False
        assert presentation["threat"] == {
            "status": "UNAVAILABLE",
            "vector_count": None,
            "schedule_entry_count": None,
            "cluster_count": None,
        }
        assert presentation["leakage"] == {"status": "PASS_CONTRACT"}
        assert presentation["determinism"] == {"status": "NOT_CHECKED", "mismatch_count": None}
        assert presentation["compare"]["status"] == "COMPLETE"
        assert presentation["compare"]["overall_assurance_verdict"] == document["compare"][
            "overall_assurance_verdict"
        ]
        assert set(presentation["compare"]["domain_statuses"]) == {
            "safety",
            "colreg",
            "maneuver",
            "efficiency",
            "human_similarity",
        }
        assert all(
            value is None or isinstance(value, str)
            for value in presentation["compare"]["domain_statuses"].values()
        )

        with client.websocket_connect(f"/ws/historical/{workflow_id}") as websocket:
            streamed = websocket.receive_json()
        assert streamed["workflow_id"] == workflow_id
        assert streamed["status"] == "COMPLETED"
        assert streamed["lineage"] == document["lineage"]


def test_historical_replay_api_uses_replay_factory_without_counterfactual_claims(
    tmp_path: Path,
    qualified_historical_enc_profile: ENCRegionProfile,
) -> None:
    request = _request(tmp_path, qualified_historical_enc_profile)
    request["mode"] = "HISTORICAL_REPLAY"
    request["replay"] = {
        "reference_mmsi": 123456789,
        "reconstruction_profile": {"time_step_s": 1.0, "max_interpolation_gap_s": 15.0},
        "dimension_registry": _dimension_registry_document(123456789, 223456789),
        "dimension_effective_at_utc": "2026-07-01T00:00:00+00:00",
    }
    request.pop("enc_profile")
    request.pop("human_reference")
    request["case"] = {}

    with TestClient(app) as client:
        prepared = client.post("/api/historical/workflows", json=request)
        assert prepared.status_code == 200, prepared.json()
        workflow_id = prepared.json()["workflow_id"]
        executed = client.post(f"/api/historical/workflows/{workflow_id}/run")
        assert executed.status_code == 200, executed.json()
        document = executed.json()

    assert document["mode"] == "HISTORICAL_REPLAY"
    assert document["stages"]["replay"] == "COMPLETED"
    assert document["stages"]["counterfactual"] == "NOT_APPLICABLE"
    assert document["stages"]["case"] == "NOT_APPLICABLE"
    assert document["compare"] is None
    assert document["evidence"]["historical_replay"]["mode"] == "HISTORICAL_REPLAY"
    assert document["evidence"]["historical_replay"]["dimension_registry_digest"]
    assert len(document["evidence"]["historical_replay"]["dimension_record_digests"]) == 2
    assert document["evidence"]["run"]["historical_execution_mode"] == "HISTORICAL_REPLAY"
    assert document["evidence"]["run"]["executed_algorithm"] == "historical_replay"
    assert document["evidence"]["run"]["replay_factory"] == "HistoricalReplayFactory"
    assert document["evidence"]["evaluation"]
    assert document["final_snapshot"]
    assert document["presentation"]["leakage"] == {"status": "NOT_APPLICABLE"}
    assert document["presentation"]["determinism"] == {
        "status": "NOT_APPLICABLE",
        "mismatch_count": None,
    }
    assert document["presentation"]["compare"]["status"] == "NOT_APPLICABLE"
    replay = document["presentation"]["evidence"]["replay"]
    assert replay["status"] == "AVAILABLE"
    assert replay["mode"] == "HISTORICAL_REPLAY"
    assert replay["factory"] == "HistoricalReplayFactory"
    assert replay["dataset_digest"] == document["evidence"]["historical_replay"]["dataset_digest"]
    assert replay["runtime_actor_set_digest"]
    assert len(replay["trajectory_digest"]) == 64
    assert len(replay["manifest_digest"]) == 64
    assert replay["dimension_registry_digest"]
    assert len(replay["dimension_source_digest"]) == 64


def test_scene_counterfactual_double_run_stays_operable_with_unqualified_cluster_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene_id = "hais_romsdal_20260701_120000_120100"
    manifest = {
        "historical_scenario_id": scene_id,
        "lineage": {
            "historical_scenario_id": scene_id,
            "dataset_digest": "dataset",
            "case_digest": "case",
            "run_digest": "run",
            "evaluation_digest": "evaluation",
            "compare_digest": "compare",
        },
        "case": {"historical_scenario_id": scene_id, "case_digest": "case"},
        "run": {
            "historical_scenario_id": scene_id,
            "mode": "COUNTERFACTUAL",
            "requested_algorithm": "nominal",
            "executed_algorithm": "nominal",
            "fallback_used": False,
        },
        "threat": {"vector_count": 2, "schedule_context_count": 2, "cluster_count": 0},
        "evaluation": {"evaluation_status": "COMPLETE", "gate": "PASS"},
        "compare": {
            "status": "COMPLETE",
            "overall_assurance_verdict": "PASS",
            "compare_digest": "compare",
            "domain_statuses": {
                "safety": "COMPLETE",
                "colreg": "COMPLETE",
                "maneuver": "COMPLETE",
                "efficiency": "COMPLETE",
                "human_similarity": "COMPLETE",
            },
        },
        "leakage": {"status": "PASS_CONTRACT"},
        "runs": [{"run_id": "first"}, {"run_id": "second"}],
        "determinism": {"status": "PASS", "mismatches": []},
    }
    outcome = historical_api.HistoricalAISAcceptanceOutcome(
        status=historical_api.HistoricalAcceptanceStatus.FAIL,
        blocker_codes=("THREAT_EVIDENCE_INCOMPLETE",),
        blocker_messages=("observed cluster_count=0 does not qualify predictive conflict clustering",),
        manifest=manifest,
        dataset_descriptor={"descriptor_sha256": "dataset"},
    )
    monkeypatch.setattr(historical_api.HistoricalAISAcceptanceHarness, "run", lambda _self, _request: outcome)
    workflow_id = "bounded-unqualified-workflow"
    workflow = historical_api._HistoricalWorkflow(
        workflow_id=workflow_id,
        mode=historical_api.HistoricalWorkflowMode.COUNTERFACTUAL,
        source_path=tmp_path / "unused.zip",
        dataset_descriptor=SimpleNamespace(descriptor_sha256="dataset", selection_sha256="selection"),
        prepared_run=SimpleNamespace(
            artifact_sink=SimpleNamespace(close=lambda **_kwargs: None),
            spec=SimpleNamespace(
                algorithm_capability_evidence={
                    "binding_role": "ALGORITHM_CAPABILITY_ONLY",
                    "geometry_equivalence": False,
                }
            ),
        ),
        experiment_runner=SimpleNamespace(),
        lineage={"dataset_digest": "dataset", "runtime_actor_set_digest": "actors"},
        historical_scenario_id=scene_id,
        qualification_request=object(),
    )
    historical_api.historical_workflows._workflows[workflow_id] = workflow
    try:
        with TestClient(app) as client:
            completed = client.post(f"/api/historical/workflows/{workflow_id}/run")
    finally:
        historical_api.historical_workflows._workflows.pop(workflow_id, None)

    document = completed.json()
    assert document["status"] == "COMPLETED"
    assert document["historical_scenario_id"] == scene_id
    qualification = document["qualification"]
    assert qualification["status"] == "NOT_QUALIFIED"
    assert qualification["code"] == "THREAT_EVIDENCE_INCOMPLETE"
    assert qualification["execution_mode"] == "DOUBLE_RUN_ACCEPTANCE"
    assert qualification["run_count"] == 2
    assert qualification["actual_counts"] == {
        "vector_count": 2,
        "schedule_context_count": 2,
        "cluster_count": 0,
    }
    assert qualification["future_gate"] == "NONEMPTY_NATURAL_CLUSTER"
    assert document["determinism"] == {"status": "PASS", "mismatches": []}
    assert document["evidence"]["threat"] == {
        "vector_count": 2,
        "schedule_context_count": 2,
        "cluster_count": 0,
    }
    presentation = document["presentation"]
    assert presentation["scenario"] == {
        "id": scene_id,
        "kind": "HISTORICAL_AIS",
        "status": "AVAILABLE",
        "scope": "BOUNDED",
    }
    assert presentation["runtime"]["status"] == "COMPLETED"
    assert presentation["runtime"]["fallback_used"] is False
    assert presentation["threat"] == {
        "status": "AVAILABLE",
        "vector_count": 2,
        "schedule_entry_count": 2,
        "cluster_count": 0,
    }
    assert presentation["qualification"]["status"] == "NOT_QUALIFIED"
    assert presentation["qualification"]["code"] == "THREAT_EVIDENCE_INCOMPLETE"
    assert presentation["qualification"]["determinism"] == {"status": "PASS", "mismatch_count": 0}
    assert presentation["qualification"]["threat_graph"] == {
        "status": "NOT_QUALIFIED",
        "code": "THREAT_EVIDENCE_INCOMPLETE",
        "vector_count": 2,
        "schedule_entry_count": 2,
        "cluster_count": 0,
    }
    assert presentation["compare"]["status"] == "COMPLETE"
    assert presentation["compare"]["overall_assurance_verdict"] == "PASS"


def test_bound_scene_registration_keeps_one_case_without_disposable_prepared_run(tmp_path: Path) -> None:
    scene_id = "hais_romsdal_20260701_120000_120100"
    run_spec = RunSpec(
        scenario_id=scene_id,
        historical_scenario_id=scene_id,
        algorithm_id="nominal",
        tracker_id="god",
        algorithm_capability_evidence={
            "binding_role": "ALGORITHM_CAPABILITY_ONLY",
            "geometry_equivalence": False,
            "exact_tuple": ["rule14", "head_on", "nominal", "god"],
        },
    )
    descriptor = SimpleNamespace(
        archive_sha256="archive",
        entry_digests=(SimpleNamespace(sha256="entry"),),
        schema_sha256="schema",
        descriptor_sha256="dataset",
        selection_sha256="selection",
        normalized_sha256="normalized",
        to_dict=lambda: {"descriptor_sha256": "dataset"},
    )
    case = SimpleNamespace(
        build_digest="build",
        runtime_digest="case",
        runtime_actor_set_digest="actors",
        enc_preflight=SimpleNamespace(to_dict=lambda: {"status": "PASS"}),
    )
    acceptance_request = object()
    context = SimpleNamespace(
        source=tmp_path / "bound.zip",
        dataset=SimpleNamespace(descriptor=descriptor),
        run_spec=run_spec,
        case=case,
        human_reference=SimpleNamespace(),
        historical_scenario_id=scene_id,
        case_identity={
            "dataset_digest": "dataset",
            "case_digest": "case",
            "runtime_actor_set_digest": "actors",
            "enc_profile_digest": "enc-profile",
            "enc_cache_digest": "enc-cache",
            "enc_source_digest": "enc-source",
            "dimension_registry_digest": "dimensions",
            "dimension_source_digest": "dimension-sources",
        },
        acceptance_request=lambda: acceptance_request,
    )
    manager = historical_api.HistoricalWorkflowManager()

    document = manager.create_bound_counterfactual(context)
    workflow = manager._require(document["workflow_id"])

    assert document["status"] == "PREPARED"
    assert workflow.bound_context is context
    assert workflow.case is case
    assert workflow.qualification_request is acceptance_request
    assert workflow.prepared_run is None
    assert document["lineage"]["enc_profile_digest"] == "enc-profile"
    assert document["lineage"]["enc_cache_digest"] == "enc-cache"
    assert document["lineage"]["enc_source_digest"] == "enc-source"
    assert document["lineage"]["dimension_registry_digest"] == "dimensions"
    assert document["lineage"]["dimension_source_digest"] == "dimension-sources"
    assert document["presentation"]["evidence"]["digests"] == {
        "archive_sha256": "archive",
        "entry_sha256": "entry",
        "schema_sha256": "schema",
        "selection_sha256": "selection",
        "normalized_sha256": "normalized",
        "descriptor_sha256": "dataset",
        "dataset_descriptor_sha256": "dataset",
        "runtime_actor_set_sha256": "actors",
        "enc_profile_sha256": "enc-profile",
        "enc_cache_sha256": "enc-cache",
        "enc_source_sha256": "enc-source",
        "dimension_registry_sha256": "dimensions",
        "dimension_source_sha256": "dimension-sources",
    }


@pytest.mark.parametrize(
    ("mutation", "expected_status"),
    (
        ("missing", "DIMENSIONS_UNAVAILABLE"),
        ("partial", "QUALITY_INCOMPLETE"),
        ("tamper", "QUALITY_INCOMPLETE"),
        ("naked_numbers", "DIMENSIONS_UNAVAILABLE"),
    ),
)
def test_historical_replay_api_rejects_unprovenanced_dimension_inputs(
    tmp_path: Path,
    qualified_historical_enc_profile: ENCRegionProfile,
    mutation: str,
    expected_status: str,
) -> None:
    request = _request(tmp_path, qualified_historical_enc_profile)
    registry = _dimension_registry_document(123456789, 223456789)
    replay = {
        "reference_mmsi": 123456789,
        "dimension_registry": registry,
        "dimension_effective_at_utc": "2026-07-01T00:00:00+00:00",
    }
    if mutation in {"missing", "naked_numbers"}:
        replay.pop("dimension_registry")
    if mutation == "partial":
        replay["dimension_registry"] = _dimension_registry_document(123456789)
    if mutation == "tamper":
        replay["dimension_registry"]["registry_digest"] = "0" * 64
    if mutation == "naked_numbers":
        replay.update({"simulation_length_m": 40.0, "simulation_width_m": 8.0})
    request.update({"mode": "HISTORICAL_REPLAY", "replay": replay, "case": {}})
    request.pop("enc_profile")
    request.pop("human_reference")

    with TestClient(app) as client:
        response = client.post("/api/historical/workflows", json=request)

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == expected_status


@pytest.mark.parametrize(
    ("mutation", "expected_status"),
    (
        ("unpublished", "CASE_NOT_PUBLISHED"),
        ("unbound", "BINDINGS_UNAVAILABLE"),
        ("unqualified_enc", "ENC_UNQUALIFIED"),
        ("future_leakage", "FUTURE_LEAKAGE"),
        ("archive_tamper", "DATASET_IDENTITY_MISMATCH"),
        ("entry_tamper", "DATASET_IDENTITY_MISMATCH"),
        ("normalized_tamper", "DATASET_IDENTITY_MISMATCH"),
        ("descriptor_tamper", "DATASET_IDENTITY_MISMATCH"),
    ),
)
def test_historical_api_rejects_unsealed_inputs(
    tmp_path: Path,
    qualified_historical_enc_profile: ENCRegionProfile,
    mutation: str,
    expected_status: str,
) -> None:
    request = _request(tmp_path, qualified_historical_enc_profile)
    if mutation == "unpublished":
        request["case"]["published"] = False
    elif mutation == "unbound":
        request.pop("human_reference")
    elif mutation == "unqualified_enc":
        request["enc_profile"]["qualification_state"] = "UNQUALIFIED"
        request["enc_profile"].pop("profile_digest", None)
    elif mutation == "future_leakage":
        request["run_spec"]["historical_replay"] = {"future_reference_samples": [1, 2, 3]}
    elif mutation == "archive_tamper":
        request["expected_archive_sha256"] = "0" * 64
    elif mutation == "entry_tamper":
        request["expected_entries"][0]["crc32"] += 1
    elif mutation == "normalized_tamper":
        request["expected_normalized_sha256"] = "0" * 64
    else:
        request["expected_descriptor_sha256"] = "0" * 64

    with TestClient(app) as client:
        response = client.post("/api/historical/workflows", json=request)

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == expected_status
