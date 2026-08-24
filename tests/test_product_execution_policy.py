from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from colav_simulator.cli import build_parser
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.experiment.batch import BatchRunner
from colav_simulator.experiment.capabilities import (
    PRODUCT_CAPABILITY_POLICY,
    CapabilityCatalog,
)
from colav_simulator.experiment.contracts import InternalExecutionPurpose, RunSpec
from colav_simulator.experiment.runner import ExperimentRunner
from colav_simulator.integrations import IntegrationRegistry
from gui_server.main import app


def test_product_policy_owns_tuple_inference_and_constraints() -> None:
    policy = PRODUCT_CAPABILITY_POLICY

    assert policy.infer_rule("head_on", "vo", "god") == "rule14"
    assert policy.infer_rule("paper_ccta2023_multiship", "vo", "god") == "multiship"
    assert policy.requires_domain_profile("mid_mpc_ipopt") is True
    assert policy.requires_domain_profile("vo") is False
    assert policy.constraints("mid_mpc_ipopt") == {
        "requires_domain_profile": True,
        "required_domain_qualification": "QUALIFIED",
    }


def test_internal_execution_purpose_is_typed_and_restricted() -> None:
    assert tuple(InternalExecutionPurpose) == (
        InternalExecutionPurpose.HISTORICAL_REPLAY,
        InternalExecutionPurpose.EVALUATOR_BASELINE,
    )
    catalog = CapabilityCatalog(IntegrationRegistry())
    assert catalog.validate_internal(
        "rule14",
        "head_on",
        "nominal",
        "god",
        purpose=InternalExecutionPurpose.EVALUATOR_BASELINE,
    )
    with pytest.raises(ColavExecutionError) as raised:
        catalog.validate_internal(
            "rule14",
            "head_on",
            "vo",
            "god",
            purpose=InternalExecutionPurpose.EVALUATOR_BASELINE,
        )
    assert raised.value.status is PlanStatus.INVALID_INPUT


def test_internal_runner_requires_explicit_purpose_and_product_runner_rejects_replay() -> None:
    runner = ExperimentRunner()
    replay_spec = RunSpec(
        "head_on",
        validation_rule_id="rule14",
        algorithm_id="nominal",
        tracker_id="god",
        historical_replay={"mode": "HISTORICAL_REPLAY"},
    )
    with pytest.raises(ColavExecutionError) as missing_purpose:
        runner.prepare_internal(replay_spec, purpose=None)  # type: ignore[arg-type]
    assert missing_purpose.value.status is PlanStatus.INVALID_INPUT
    with pytest.raises(ColavExecutionError) as product_bypass:
        runner.prepare(replay_spec)
    assert product_bypass.value.status is PlanStatus.INVALID_INPUT


def test_counterfactual_product_tuple_rejects_retired_algorithm_and_tracker() -> None:
    runner = ExperimentRunner()
    for algorithm_id, tracker_id in (
        ("sbmpc", "god"),
        ("potocnik_simplified_mpc", "god"),
        ("vo", "kf"),
    ):
        with pytest.raises(ColavExecutionError) as raised:
            runner.prepare(
                RunSpec(
                    "head_on",
                    validation_rule_id="rule14",
                    algorithm_id=algorithm_id,
                    tracker_id=tracker_id,
                    historical_replay={"mode": "COUNTERFACTUAL"},
                )
            )
        assert raised.value.status is PlanStatus.INVALID_INPUT


def test_batch_default_specs_are_product_tuples_with_inferred_rules() -> None:
    specs = BatchRunner.default_specs(["vo"], seeds=[0])
    assert specs
    assert all(spec.algorithm_id == "vo" for spec in specs)
    assert all(spec.tracker_id == "god" for spec in specs)
    assert all(spec.validation_rule_id for spec in specs)


def test_cli_product_defaults_and_legacy_endpoints_are_typed() -> None:
    parser = build_parser()
    parsed = parser.parse_args(["run", "--scenario", "head_on"])
    assert parsed.algorithm == "vo"
    assert parsed.tracker == "god"

    with TestClient(app) as client:
        for path in ("/api/start", "/api/pause", "/api/reset"):
            response = client.post(path)
            assert response.status_code == 410
            assert response.json()["detail"]["status"] == "DEPRECATED_ENDPOINT"


def test_integrations_endpoint_does_not_publish_legacy_as_available() -> None:
    with TestClient(app) as client:
        response = client.get("/api/integrations")
    assert response.status_code == 200
    document = response.json()
    product_ids = {item["id"] for item in document["product"]}
    assert {"vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt", "god"} <= product_ids
    legacy = {item["id"]: item for item in document["internal_legacy"]}
    assert legacy["nominal"]["selectable"] is False
    assert legacy["nominal"]["available"] is False
