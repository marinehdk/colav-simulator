from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from colav_simulator.core.colav.custom_mpc_adapter import DeadlineMode, FactoryContext
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.core.colav.threat_assessment import (
    DomainQualification,
    ShipDomainProfile,
)
from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.experiment import ExperimentRunner, RunSpec
from colav_simulator.integrations import mid_mpc_ipopt
from gui_server.main import app


def _qualified_profile() -> ShipDomainProfile:
    return ShipDomainProfile(
        profile_id="test-domain",
        version="v1",
        fore_m=300.0,
        aft_m=100.0,
        port_m=120.0,
        starboard_m=180.0,
        parameter_source="test-fixture",
        assumptions=("engineering-envelope-only",),
        qualification=DomainQualification.QUALIFIED,
    )


def test_run_spec_round_trips_versioned_ship_domain_profile() -> None:
    profile = _qualified_profile()
    spec = RunSpec("head_on", domain_profile=profile)

    document = spec.to_dict()
    restored = RunSpec.from_dict(document)

    assert document["domain_profile"]["profile_id"] == "test-domain"
    assert document["domain_profile"]["version"] == "v1"
    assert document["domain_profile"]["profile_hash"] == profile.profile_hash
    assert restored.domain_profile == profile


def test_default_threat_coordinator_remains_unqualified() -> None:
    assert ThreatManagementCoordinator().domain_profile.qualified is False


def test_factory_injects_qualified_profile_into_mid_mpc_threat_snapshot() -> None:
    profile = _qualified_profile()
    adapter = mid_mpc_ipopt.create(
        context=FactoryContext(
            requested_algorithm="mid_mpc_ipopt",
            algorithm_seed=0,
            scenario_id="profile-injection",
            tracker_id="god",
            deadline_mode=DeadlineMode.OFF,
            domain_profile=profile,
        ),
        horizon_steps=2,
        horizon_dt_s=5.0,
        solve_period_s=5.0,
        deadline_s=20.0,
    )

    adapter.plan(
        0.0,
        np.array([[0.0, 500.0], [0.0, 0.0]]),
        np.array([4.0, 4.0]),
        np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        [],
        dt=1.0,
        os_length=15.0,
        os_model_name="Viknes",
        os_controller_name="FLSC",
        os_max_turn_rate_radps=np.deg2rad(3.0),
    )

    threat = adapter.get_colav_data()["planner"]["algorithm_details"]["threat_management"]
    assert threat["profile_hash"] == profile.profile_hash


def test_api_rejects_invalid_ship_domain_profile_with_typed_status() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": "paper_ccta2023_multiship",
                "algorithm_id": "mid_mpc_ipopt",
                "tracker_id": "god",
                "domain_profile": {
                    "profile_id": "invalid",
                    "version": "v1",
                    "fore_m": 300.0,
                    "aft_m": 100.0,
                    "port_m": 120.0,
                    "starboard_m": 180.0,
                    "parameter_source": "test-fixture",
                    "assumptions": [],
                    "qualification": "QUALIFIED",
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "INVALID_INPUT"
    assert "ShipDomainProfile" in response.json()["detail"]["reason"]

    with TestClient(app) as client:
        malformed = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": "head_on",
                "algorithm_id": "mid_mpc_ipopt",
                "tracker_id": "god",
                "domain_profile": ["not", "a", "profile"],
            },
        )
    assert malformed.status_code == 422
    assert malformed.json()["detail"]["status"] == "INVALID_INPUT"


def test_formal_mid_run_requires_explicit_qualified_profile(tmp_path) -> None:
    with pytest.raises(ColavExecutionError) as missing:
        ExperimentRunner().prepare(
            RunSpec(
                "overtaking",
                validation_rule_id="rule13",
                algorithm_id="mid_mpc_ipopt",
                tracker_id="god",
                t_end=0.2,
                output_root=str(tmp_path),
            )
        )
    assert missing.value.status is PlanStatus.INVALID_INPUT
    assert "qualified ShipDomainProfile" in str(missing.value)

    unqualified = replace(_qualified_profile(), qualification=DomainQualification.UNQUALIFIED)
    with pytest.raises(ColavExecutionError) as rejected:
        ExperimentRunner().prepare(
            RunSpec(
                "overtaking",
                validation_rule_id="rule13",
                algorithm_id="mid_mpc_ipopt",
                tracker_id="god",
                domain_profile=unqualified,
                t_end=0.2,
                output_root=str(tmp_path),
            )
        )
    assert rejected.value.status is PlanStatus.INVALID_INPUT
    assert "qualified ShipDomainProfile" in str(rejected.value)


def test_api_description_preserves_qualified_domain_profile_identity() -> None:
    profile = _qualified_profile()
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "multiship",
                "scenario_id": "paper_ccta2023_multiship",
                "algorithm_id": "mid_mpc_ipopt",
                "tracker_id": "god",
                "domain_profile": profile.to_dict(),
                "t_end": 0.2,
            },
        )

    assert response.status_code == 200, response.json()
    serialized = response.json()["spec"]["domain_profile"]
    assert serialized["profile_id"] == profile.profile_id
    assert serialized["version"] == profile.version
    assert serialized["qualification"] == "QUALIFIED"
    assert serialized["profile_hash"] == profile.profile_hash
