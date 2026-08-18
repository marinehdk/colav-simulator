from __future__ import annotations

from fastapi.testclient import TestClient

from gui_server.main import app


def test_config_seam_reads_global_capabilities_and_creates_strict_created_session() -> None:
    request = {
        "validation_rule_id": "rule14",
        "scenario_id": "head_on",
        "algorithm_id": "vo",
        "tracker_id": "god",
        "seed": 9,
        "episode_index": 0,
        "dt": None,
        "t_end": None,
        "strict_no_fallback": True,
        "evaluator_profile_id": "ccta_2023_demo-v1",
        "algorithm_config": {},
        "tracker_config": {},
        "scenario_override": None,
    }

    with TestClient(app) as client:
        catalog_response = client.get("/api/capabilities")
        assert catalog_response.status_code == 200
        catalog = catalog_response.json()
        assert {item["validation_rule_id"] for item in catalog["selectable_combinations"]} == {
            "rule13",
            "rule14",
            "rule15",
            "multiship",
        }

        created_response = client.post("/api/sessions", json=request)
        assert created_response.status_code == 200, created_response.text
        created = created_response.json()
        assert created["state"] == "CREATED"
        assert created["spec"]["strict_no_fallback"] is True
        assert created["spec"]["scenario_override"] is None

        current_response = client.get("/api/sessions/current")
        assert current_response.status_code == 200
        current = current_response.json()
        assert current["session_id"] == created["session_id"]
        assert current["spec"]["validation_rule_id"] == "rule14"
        assert current["spec"]["algorithm_config"] == {}
        assert current["spec"]["tracker_config"] == {}
