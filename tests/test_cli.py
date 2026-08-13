import json
from argparse import Namespace

import numpy as np

from colav_simulator.cli import _load_algorithm_config, _plugin_check, _verify_mid_mpc_evidence, build_parser
from colav_simulator.core.colav.prediction_evidence import (
    OptimizationIntervalReference,
    OwnshipPrediction,
    PredictionEvidenceRecord,
    PredictionGrid,
)


def _prediction_record() -> PredictionEvidenceRecord:
    grid = PredictionGrid(intervals=1, dt_s=5.0)
    return PredictionEvidenceRecord(
        algorithm_id="mid_mpc_ipopt",
        candidate_hash="candidate",
        acceptance_hash="acceptance",
        ownship=OwnshipPrediction(
            grid=grid,
            north_m=np.array([0.0, 20.0]),
            east_m=np.array([0.0, 0.0]),
            heading_rad=np.array([0.0, 0.0]),
            speed_mps=np.array([4.0, 4.0]),
            state_sources=("MEASURED", "IPOPT_INTEGRATED"),
            interval_references=(OptimizationIntervalReference(0, 0.0, 5.0, 0.0, 4.0, 0, 1),),
        ),
        target_predictions=(),
        acceptance={"accepted": True, "mandatory_failures": []},
        solver={"backend": "ipopt"},
    )


def test_algorithm_config_resolves_dependency_lock_relative_to_yaml() -> None:
    config = _load_algorithm_config("config/custom_mpc_example.yaml")

    assert config["factory"] == "examples.custom_mpc_plugin:create"
    assert config["dependency_lock"].endswith("/uv.lock")


def test_plugin_check_emits_machine_readable_conformance(capsys) -> None:
    status = _plugin_check(
        Namespace(
            algorithm="custom_mpc_example",
            algorithm_config="config/custom_mpc_example.yaml",
            seed=9,
        )
    )
    output = json.loads(capsys.readouterr().out)

    assert status == 0
    assert output["status"] == "SUCCESS"
    assert output["fallback_used"] is False
    assert output["build_identity_complete"] is True
    assert output["descriptor"]["algorithm_id"] == "custom_mpc_example"
    assert output["control_reference_shape"] == [9, 1]
    assert output["predicted_trajectory_shape"] == [9, 5]
    assert output["solve_id"] == 1
    assert output["reasons"] == []


def test_plugin_check_reports_contract_failure_as_json(capsys, tmp_path) -> None:
    config_path = tmp_path / "missing.yaml"
    config_path.write_text("factory: missing_package.plugin:create\n", encoding="utf-8")

    status = _plugin_check(
        Namespace(
            algorithm="missing_mpc",
            algorithm_config=str(config_path),
            seed=0,
        )
    )
    output = json.loads(capsys.readouterr().out)

    assert status == 1
    assert output["status"] == "DEPENDENCY_UNAVAILABLE"
    assert output["reasons"]


def test_cli_parser_accepts_plugin_check_and_run_algorithm_config() -> None:
    parser = build_parser()
    plugin = parser.parse_args(
        [
            "plugin-check",
            "--algorithm",
            "custom_mpc_example",
            "--algorithm-config",
            "config/custom_mpc_example.yaml",
        ]
    )
    run = parser.parse_args(
        [
            "run",
            "--scenario",
            "head_on",
            "--algorithm",
            "custom_mpc_example",
            "--algorithm-config",
            "config/custom_mpc_example.yaml",
        ]
    )

    assert plugin.command == "plugin-check"
    assert run.algorithm_config == "config/custom_mpc_example.yaml"


def test_cli_verifies_mid_mpc_semantic_artifact_without_claiming_authenticity(capsys, tmp_path) -> None:
    artifact = tmp_path / "evidence.json"
    record = _prediction_record()
    artifact.write_text(json.dumps({"prediction_evidence": record.to_dict()}), encoding="utf-8")

    status = _verify_mid_mpc_evidence(Namespace(artifact=str(artifact)))
    output = json.loads(capsys.readouterr().out)

    assert status == 0
    assert output["valid"] is True
    assert output["highest_verified_level"] == "V5_PROJECTION"
    assert output["source_authenticity_verified"] is False
    parser = build_parser()
    parsed = parser.parse_args(["verify-mid-mpc-evidence", "--artifact", str(artifact)])
    assert parsed.artifact == str(artifact)
