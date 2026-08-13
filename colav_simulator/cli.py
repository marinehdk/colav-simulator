"""Command-line entry point for reproducible COLAV experiments."""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import uvicorn
import yaml

from colav_simulator import scenario_config
from colav_simulator.common import config_parsing as cp
from colav_simulator.common import paths
from colav_simulator.core.colav.custom_mpc_adapter import CustomMPCAdapter, FactoryContext
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.core.colav.prediction_evidence import verify_evidence_document
from colav_simulator.experiment.batch import BatchRunner
from colav_simulator.experiment.busy_water import (
    DEFAULT_SEED,
    build_busy_water_document,
    preflight_document,
    write_busy_water_scenario,
)
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunner
from colav_simulator.integrations import IntegrationRegistry
from colav_simulator.scenario_generator import ScenarioGenerator


def _run(args: argparse.Namespace) -> int:
    spec = RunSpec(
        scenario_id=args.scenario,
        algorithm_id=args.algorithm,
        tracker_id=args.tracker,
        seed=args.seed,
        dt=args.dt,
        t_end=args.t_end,
        evaluator_profile_id=args.evaluator_profile,
        algorithm_config=_load_algorithm_config(args.algorithm_config),
        output_root=args.output,
    )
    result = ExperimentRunner().run(spec)
    print(
        json.dumps(
            {
                "run_id": result.manifest.run_id,
                "run_dir": str(result.run_dir),
                "state": result.manifest.state.value,
                "execution_outcome": result.manifest.execution_outcome.value,
                "reproduction_status": result.manifest.reproduction_status,
            },
            indent=2,
        )
    )
    return 0


def _list(args: argparse.Namespace) -> int:  # noqa: ARG001
    print(json.dumps(ExperimentRunner().list_scenarios(), indent=2))
    return 0


def _replay(args: argparse.Namespace) -> int:
    result = ExperimentRunner().replay(Path(args.run_dir), Path(args.output))
    print(
        json.dumps(
            {
                "run_id": result.manifest.run_id,
                "run_dir": str(result.run_dir),
                "replay_of_run_id": result.manifest.replay_of_run_id,
                "replay_verified": result.manifest.replay_verified,
            },
            indent=2,
        )
    )
    return 0


def _verify_mid_mpc_evidence(args: argparse.Namespace) -> int:
    artifact_path = Path(args.artifact)
    try:
        payload = artifact_path.read_bytes()
        if artifact_path.suffix == ".gz":
            payload = gzip.decompress(payload)
        document = json.loads(payload)
        if not isinstance(document, dict):
            raise ValueError("artifact root must be an object")
        result = verify_evidence_document(document)
        output = {
            "valid": result.valid,
            "highest_verified_level": result.highest_verified_level.value,
            "failures": list(result.failures),
            "semantic_hash": result.semantic_hash,
            "source_authenticity_verified": False,
            "ipopt_resolve": "NOT_RUN_DIAGNOSTIC_ONLY",
        }
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        output = {
            "valid": False,
            "highest_verified_level": "NONE",
            "failures": [f"ARTIFACT_INVALID: {exc}"],
            "source_authenticity_verified": False,
            "ipopt_resolve": "NOT_RUN_DIAGNOSTIC_ONLY",
        }
    print(json.dumps(output, indent=2, allow_nan=False))
    return 0 if output["valid"] else 1


def _batch(args: argparse.Namespace) -> int:
    seeds = range(args.seed_start, args.seed_start + args.seed_count)
    algorithm_config = _load_algorithm_config(args.algorithm_config)
    if args.default_matrix:
        specs = BatchRunner.default_specs(args.algorithm, seeds, args.tracker)
        specs = [
            replace(
                spec,
                algorithm_config=algorithm_config,
                evaluator_profile_id=args.evaluator_profile,
            )
            for spec in specs
        ]
    else:
        specs = [
            RunSpec(
                scenario_id=scenario,
                algorithm_id=algorithm,
                tracker_id=args.tracker,
                seed=seed,
                evaluator_profile_id=args.evaluator_profile,
                algorithm_config=algorithm_config,
            )
            for algorithm in args.algorithm
            for scenario in args.scenario
            for seed in seeds
        ]
    batch_dir = BatchRunner().run(specs, Path(args.output))
    print(json.dumps({"batch_dir": str(batch_dir), "runs": len(specs)}, indent=2))
    return 0


def _plugin_check(args: argparse.Namespace) -> int:
    try:
        config = _load_algorithm_config(args.algorithm_config)
        context = FactoryContext(
            requested_algorithm=args.algorithm,
            algorithm_seed=args.seed,
        )
        algorithm = IntegrationRegistry().build_algorithm(
            args.algorithm,
            config,
            factory_context=context,
        )
        if not isinstance(algorithm, CustomMPCAdapter):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "plugin-check requires CustomMPCAdapter",
            )
        algorithm.reset()
        plan = algorithm.plan(
            0.0,
            np.array([[0.0, 100.0], [0.0, 0.0]]),
            np.array([4.0, 4.0]),
            np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
            [],
            dt=0.5,
        )
        planner = algorithm.get_colav_data()["planner"]
        payload = {
            "algorithm_id": algorithm.descriptor.algorithm_id,
            "status": algorithm.get_diagnostics().status.value,
            "fallback_used": algorithm.get_diagnostics().fallback_used,
            "descriptor": algorithm.descriptor.to_dict(),
            "descriptor_hash": algorithm.descriptor.hash,
            "build_identity": algorithm.build_identity.to_dict(),
            "build_identity_complete": algorithm.build_identity.complete,
            "control_reference_shape": list(plan.shape),
            "predicted_trajectory_shape": list(np.asarray(planner["predicted_trajectory"]).shape),
            "solve_id": planner["solve_id"],
            "reasons": [],
        }
        exit_code = 0
    except ColavExecutionError as exc:
        payload = {
            "algorithm_id": args.algorithm,
            "status": exc.status.value,
            "fallback_used": False,
            "reasons": [str(exc)],
        }
        exit_code = 1
    except Exception as exc:
        payload = {
            "algorithm_id": args.algorithm,
            "status": PlanStatus.INVALID_INPUT.value,
            "fallback_used": False,
            "reasons": [str(exc)],
        }
        exit_code = 1
    print(json.dumps(payload, indent=2))
    return exit_code


def _load_algorithm_config(path_value: str | None) -> dict:
    if path_value is None:
        return {}
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"algorithm config not found: {path}")
    with path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream) if path.suffix.lower() in {".yaml", ".yml"} else json.load(stream)
    if not isinstance(document, dict):
        raise ValueError("algorithm config must contain a mapping")
    dependency_lock = document.get("dependency_lock")
    if dependency_lock:
        lock_path = Path(dependency_lock).expanduser()
        if not lock_path.is_absolute():
            lock_path = (path.parent / lock_path).resolve()
        document["dependency_lock"] = str(lock_path)
    return document


def _serve(args: argparse.Namespace) -> int:
    uvicorn.run("gui_server.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _busy_water_generate(args: argparse.Namespace) -> int:
    encounter_mix = {
        "crossing": args.crossing_ratio,
        "head_on": args.head_on_ratio,
        "overtaking": args.overtaking_ratio,
    }
    output = write_busy_water_scenario(
        args.profile,
        Path(args.output),
        seed=args.seed,
        target_count=args.target_count,
        encounter_mix=encounter_mix,
    )
    result = preflight_document(
        build_busy_water_document(
            args.profile,
            seed=args.seed,
            target_count=args.target_count,
            encounter_mix=encounter_mix,
        ),
        seed=args.seed,
    )
    print(json.dumps({"output": str(output.resolve()), **result}, indent=2))
    return 0


def _busy_water_preflight(args: argparse.Namespace) -> int:
    scenario_path = Path(args.scenario)
    with scenario_path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    result = preflight_document(document, seed=args.seed)
    if args.with_enc:
        config = cp.extract(scenario_config.ScenarioConfig, scenario_path, paths.scenario_schema)
        episodes, enc = ScenarioGenerator(seed=args.seed).generate(
            config=config,
            n_episodes=1,
            show_plots=False,
            save_scenario=False,
        )
        generated_count = len(episodes[0]["ship_list"])
        if generated_count != result["ship_count"]:
            raise ValueError(f"ENC preflight retained {generated_count}/{result['ship_count']} ships")
        result["enc_preflight"] = {
            "status": "PASS",
            "bbox": list(enc.bbox),
            "ship_count": generated_count,
        }
    print(json.dumps(result, indent=2))
    return 0


def _add_busy_water_parsers(subparsers: argparse._SubParsersAction) -> None:
    generate_parser = subparsers.add_parser("busy-water-generate", help="generate a deterministic busy-water YAML")
    generate_parser.add_argument("--profile", choices=("acceptance", "stress"), required=True)
    generate_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    generate_parser.add_argument("--target-count", type=int)
    generate_parser.add_argument("--crossing-ratio", type=float, default=0.6)
    generate_parser.add_argument("--head-on-ratio", type=float, default=0.2)
    generate_parser.add_argument("--overtaking-ratio", type=float, default=0.2)
    generate_parser.add_argument("--output", required=True)
    generate_parser.set_defaults(handler=_busy_water_generate)

    preflight_parser = subparsers.add_parser("busy-water-preflight", help="preflight a busy-water YAML")
    preflight_parser.add_argument("scenario")
    preflight_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    preflight_parser.add_argument("--with-enc", action="store_true")
    preflight_parser.set_defaults(handler=_busy_water_preflight)


def build_parser() -> argparse.ArgumentParser:
    """Build the experiment command-line parser."""
    parser = argparse.ArgumentParser(prog="colav-sim")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run one experiment")
    run_parser.add_argument("--scenario", required=True)
    run_parser.add_argument("--algorithm", default="nominal")
    run_parser.add_argument("--tracker", default="scenario_default")
    run_parser.add_argument("--seed", type=int, default=0)
    run_parser.add_argument("--dt", type=float)
    run_parser.add_argument("--t-end", type=float)
    run_parser.add_argument("--algorithm-config")
    run_parser.add_argument("--evaluator-profile", default="ccta_2023_demo-v1")
    run_parser.add_argument("--output", default="runs")
    run_parser.set_defaults(handler=_run)

    list_parser = subparsers.add_parser("scenarios", help="list scenario catalog")
    list_parser.set_defaults(handler=_list)

    replay_parser = subparsers.add_parser("replay", help="replay and verify one evidence bundle")
    replay_parser.add_argument("--run-dir", required=True)
    replay_parser.add_argument("--output", default="runs")
    replay_parser.set_defaults(handler=_replay)

    verify_parser = subparsers.add_parser(
        "verify-mid-mpc-evidence",
        help="verify a Mid-MPC Prediction Evidence artifact through deterministic V0-V6 checks",
    )
    verify_parser.add_argument("--artifact", required=True)
    verify_parser.set_defaults(handler=_verify_mid_mpc_evidence)

    batch_parser = subparsers.add_parser("batch", help="run a failure-preserving experiment matrix")
    batch_parser.add_argument("--scenario", action="append", default=[])
    batch_parser.add_argument("--algorithm", action="append", required=True)
    batch_parser.add_argument("--tracker", default="scenario_default")
    batch_parser.add_argument("--seed-start", type=int, default=0)
    batch_parser.add_argument("--seed-count", type=int, default=30)
    batch_parser.add_argument("--default-matrix", action="store_true")
    batch_parser.add_argument("--algorithm-config")
    batch_parser.add_argument("--evaluator-profile", default="ccta_2023_demo-v1")
    batch_parser.add_argument("--output", default="runs")
    batch_parser.set_defaults(handler=_batch)

    plugin_parser = subparsers.add_parser("plugin-check", help="validate one Custom MPC plugin contract")
    plugin_parser.add_argument("--algorithm", required=True)
    plugin_parser.add_argument("--algorithm-config", required=True)
    plugin_parser.add_argument("--seed", type=int, default=0)
    plugin_parser.set_defaults(handler=_plugin_check)

    serve_parser = subparsers.add_parser("serve", help="start the Web control surface")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.set_defaults(handler=_serve)

    _add_busy_water_parsers(subparsers)
    return parser


def main() -> int:
    """Dispatch the selected command."""
    args = build_parser().parse_args()
    if args.command == "batch" and not args.default_matrix and not args.scenario:
        raise SystemExit("--scenario is required unless --default-matrix is used")
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
