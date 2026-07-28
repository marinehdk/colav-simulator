"""Command-line entry point for reproducible COLAV experiments."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import uvicorn
import yaml

from colav_simulator.core.colav.custom_mpc_adapter import CustomMPCAdapter, FactoryContext
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.experiment.batch import BatchRunner
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunner
from colav_simulator.integrations import IntegrationRegistry


def _run(args: argparse.Namespace) -> int:
    spec = RunSpec(
        scenario_id=args.scenario,
        algorithm_id=args.algorithm,
        tracker_id=args.tracker,
        seed=args.seed,
        dt=args.dt,
        t_end=args.t_end,
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


def _batch(args: argparse.Namespace) -> int:
    seeds = range(args.seed_start, args.seed_start + args.seed_count)
    algorithm_config = _load_algorithm_config(args.algorithm_config)
    if args.default_matrix:
        specs = BatchRunner.default_specs(args.algorithm, seeds, args.tracker)
        specs = [replace(spec, algorithm_config=algorithm_config) for spec in specs]
    else:
        specs = [
            RunSpec(
                scenario_id=scenario,
                algorithm_id=algorithm,
                tracker_id=args.tracker,
                seed=seed,
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
    run_parser.add_argument("--output", default="runs")
    run_parser.set_defaults(handler=_run)

    list_parser = subparsers.add_parser("scenarios", help="list scenario catalog")
    list_parser.set_defaults(handler=_list)

    replay_parser = subparsers.add_parser("replay", help="replay and verify one evidence bundle")
    replay_parser.add_argument("--run-dir", required=True)
    replay_parser.add_argument("--output", default="runs")
    replay_parser.set_defaults(handler=_replay)

    batch_parser = subparsers.add_parser("batch", help="run a failure-preserving experiment matrix")
    batch_parser.add_argument("--scenario", action="append", default=[])
    batch_parser.add_argument("--algorithm", action="append", required=True)
    batch_parser.add_argument("--tracker", default="scenario_default")
    batch_parser.add_argument("--seed-start", type=int, default=0)
    batch_parser.add_argument("--seed-count", type=int, default=30)
    batch_parser.add_argument("--default-matrix", action="store_true")
    batch_parser.add_argument("--algorithm-config")
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
    return parser


def main() -> int:
    """Dispatch the selected command."""
    args = build_parser().parse_args()
    if args.command == "batch" and not args.default_matrix and not args.scenario:
        raise SystemExit("--scenario is required unless --default-matrix is used")
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
