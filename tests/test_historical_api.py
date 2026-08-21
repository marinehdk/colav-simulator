from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from colav_simulator.historical_enc import ENCRegionProfile
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


def _request(tmp_path: Path, profile: ENCRegionProfile) -> dict[str, object]:
    human_positions = tuple(
        profile.projection.project_wgs84(point)
        for point in ((7.0012, 62.0000), (7.0012, 61.9994))
    )
    return {
        "source_path": str(_source(tmp_path / "historical-api.csv")),
        "selection": {
            "start_utc": datetime(2026, 7, 1, tzinfo=UTC).isoformat(),
            "end_utc": datetime(2026, 7, 1, 0, 1, tzinfo=UTC).isoformat(),
        },
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

        executed = client.post(f"/api/historical/workflows/{workflow_id}/run")
        assert executed.status_code == 200, executed.json()
        final = client.get(f"/api/historical/workflows/{workflow_id}")
        assert final.status_code == 200
        document = final.json()
        assert document["status"] == "COMPLETED"
        assert document["stages"] == {
            "dataset": "SELECTED",
            "case": "PUBLISHED",
            "counterfactual": "COMPLETED",
            "evaluation": "COMPLETE",
            "compare": document["compare"]["status"],
        }
        assert all(document["lineage"].values())
        assert document["leakage"]["human_reference_digest_in_run_spec"] is False
        assert document["final_snapshot"]
        assert document["evidence"]["evaluation"]
        assert document["evidence"]["compare_digest"] == document["lineage"]["compare_digest"]

        with client.websocket_connect(f"/ws/historical/{workflow_id}") as websocket:
            streamed = websocket.receive_json()
        assert streamed["workflow_id"] == workflow_id
        assert streamed["status"] == "COMPLETED"
        assert streamed["lineage"] == document["lineage"]


@pytest.mark.parametrize(
    ("mutation", "expected_status"),
    (
        ("unpublished", "CASE_NOT_PUBLISHED"),
        ("unbound", "BINDINGS_UNAVAILABLE"),
        ("unqualified_enc", "ENC_UNQUALIFIED"),
        ("future_leakage", "FUTURE_LEAKAGE"),
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
    else:
        request["run_spec"]["historical_replay"] = {"future_reference_samples": [1, 2, 3]}

    with TestClient(app) as client:
        response = client.post("/api/historical/workflows", json=request)

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == expected_status
