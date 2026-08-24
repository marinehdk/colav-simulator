from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.experiment.capabilities import CapabilityCatalog
from colav_simulator.integrations import IntegrationRegistry
from gui_server.main import app

EXPECTED_COUNTS = {
    "rule13": 6,
    "rule14": 3,
    "rule15": 6,
    "multiship": 3,
}
EXPECTED_SCENARIOS = {
    "rule13": {"overtaking", "overtaken"},
    "rule14": {"head_on"},
    "rule15": {"crossing_give_way", "crossing_stand_on"},
    "multiship": {"paper_ccta2023_multiship"},
}
EVIDENCE_FIELDS = {
    "seed",
    "termination",
    "minimum_clearance_m",
    "max_heading_delta_deg",
    "max_speed_delta_mps",
    "solve_count",
    "encounter_profile_id",
    "predicate_version",
}


@pytest.mark.parametrize("rule_id", EXPECTED_COUNTS)
def test_capability_api_exposes_only_exact_verified_tuples(rule_id: str) -> None:
    with TestClient(app) as client:
        response = client.get("/api/capabilities", params={"validation_rule_id": rule_id})

    assert response.status_code == 200
    catalog = response.json()
    assert catalog["product_capability_policy"] == {
        "policy_id": "colav-product-v1",
        "algorithm_ids": ["vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt"],
        "tracker_ids": ["god"],
        "default_algorithm_id": "vo",
        "default_tracker_id": "god",
    }
    combinations = catalog["verified_combinations"]
    assert len(combinations) == EXPECTED_COUNTS[rule_id]
    assert {item["scenario_id"] for item in combinations} == EXPECTED_SCENARIOS[rule_id]
    for item in combinations:
        assert {
            "validation_rule_id",
            "scenario_id",
            "algorithm_id",
            "tracker_id",
            "predicate_version",
            "latest_evidence",
        } <= item.keys()
        assert item["validation_rule_id"] == rule_id
        assert item["predicate_version"] == "G3DisplayPredicate-v1"
        assert EVIDENCE_FIELDS <= item["latest_evidence"].keys()
        assert item["latest_evidence"]["encounter_profile_id"] == "legacy-g3-v1"

    selectable_trackers = {item["id"] for item in catalog["trackers"] if item["selectable"]}
    assert selectable_trackers == {"god"}
    expected_algorithms = {"vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt"}
    assert {item["id"] for item in catalog["algorithms"] if item["selectable"]} == expected_algorithms
    assert {
        item["id"] for item in catalog["algorithms"] if not item["selectable"]
    } >= {"nominal", "sbmpc", "potocnik_simplified_mpc"}
    assert {item["id"] for item in catalog["trackers"] if not item["selectable"]} >= {"kf", "scenario_default"}
    if rule_id == "multiship":
        mid_mpc = next(item for item in catalog["algorithms"] if item["id"] == "mid_mpc_ipopt")
        assert "global all-vessel safety is not established" in mid_mpc["known_failure"]


@pytest.mark.parametrize(
    ("rule_id", "scenario_id", "algorithm_id", "tracker_id"),
    (
        ("rule13", "crossing_give_way", "vo", "god"),
        ("rule15", "overtaking", "vo", "god"),
        ("rule13", "overtaking", "vo", "kf"),
        ("rule15", "crossing_give_way", "sbmpc", "god"),
        ("rule15", "crossing_give_way", "vo", "scenario_default"),
        ("rule14", "head_on", "nominal", "god"),
        ("rule14", "head_on", "potocnik_simplified_mpc", "god"),
        ("rule15", "crossing_give_way", "potocnik_simplified_mpc", "god"),
        ("multiship", "paper_ccta2023_multiship", "vo", "kf"),
        ("rule14", "head_on", "psbmpc", "god"),
        ("rule14", "paper_ccta2023_head_on", "vo", "god"),
    ),
)
def test_session_api_rejects_every_unverified_tuple(
    rule_id: str,
    scenario_id: str,
    algorithm_id: str,
    tracker_id: str,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": rule_id,
                "scenario_id": scenario_id,
                "algorithm_id": algorithm_id,
                "tracker_id": tracker_id,
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "INVALID_INPUT"


def test_global_g3_grade_cannot_create_a_missing_cross_product() -> None:
    with TestClient(app) as client:
        global_catalog = client.get("/api/capabilities").json()
        vo = next(item for item in global_catalog["algorithms"] if item["id"] == "vo")
        assert vo["readiness_grade"] == "G3"

        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule13",
                "scenario_id": "overtaking",
                "algorithm_id": "vo",
                "tracker_id": "kf",
            },
        )

    assert response.status_code == 422
    assert "Tracker kf is not selectable" in response.json()["detail"]["reason"]


def test_invalid_tuple_precedes_dependency_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = CapabilityCatalog(IntegrationRegistry())
    statuses = catalog.registry.statuses()
    unavailable = replace(statuses["vo"], available=False, reason="missing in test environment")
    monkeypatch.setattr(catalog.registry, "statuses", lambda: {**statuses, "vo": unavailable})

    with pytest.raises(ColavExecutionError) as invalid:
        catalog.validate("rule14", "head_on", "psbmpc", "god")
    assert invalid.value.status is PlanStatus.INVALID_INPUT

    with pytest.raises(ColavExecutionError) as unavailable_dependency:
        catalog.validate("rule14", "head_on", "vo", "god")
    assert unavailable_dependency.value.status is PlanStatus.DEPENDENCY_UNAVAILABLE


def test_product_policy_rejects_legacy_integrations_even_when_registry_can_build_them() -> None:
    catalog = CapabilityCatalog(IntegrationRegistry())

    for algorithm_id in ("nominal", "sbmpc", "potocnik_simplified_mpc"):
        with pytest.raises(ColavExecutionError) as raised:
            catalog.validate("rule14", "head_on", algorithm_id, "god")
        assert raised.value.status is PlanStatus.INVALID_INPUT

    with pytest.raises(ColavExecutionError) as raised:
        catalog.validate("rule14", "head_on", "vo", "kf")
    assert raised.value.status is PlanStatus.INVALID_INPUT
