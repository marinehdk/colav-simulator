"""Command surface for the decision-replay harness: ``python -m colav_simulator.decision_replay``."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from colav_simulator.decision_replay import probes
from colav_simulator.decision_replay.bundle import TraceBundle
from colav_simulator.decision_replay.recorder import record


def _build_spec(args: argparse.Namespace) -> Any:
    from colav_simulator.experiment.contracts import RunSpec  # noqa: PLC0415

    algorithm_config = json.loads(args.algorithm_config) if args.algorithm_config else {}
    if args.scenario.startswith("hais_"):
        from colav_simulator.historical_scenario_assembly import HistoricalAISSceneAssembler  # noqa: PLC0415
        from colav_simulator.historical_scenario_catalog import HistoricalAISScenarioCatalog  # noqa: PLC0415

        descriptor = HistoricalAISScenarioCatalog().get(args.scenario)
        overrides: dict[str, Any] = {
            "algorithm_id": args.algorithm,
            "algorithm_config": algorithm_config,
            "evaluator_profile_id": args.evaluator_profile,
        }
        if args.t_end is not None:
            overrides["t_end"] = args.t_end
        if args.dt is not None:
            overrides["dt"] = args.dt
        lifecycle_spec = HistoricalAISSceneAssembler().bind_lifecycle_counterfactual(
            descriptor,
            run_spec_overrides=overrides,
        )
        return replace(
            lifecycle_spec,
            validation_rule_id=args.validation_rule_id,
            seed=args.seed,
            strict_no_fallback=True,
        )
    return RunSpec(
        scenario_id=args.scenario,
        validation_rule_id=args.validation_rule_id,
        algorithm_id=args.algorithm,
        tracker_id=args.tracker,
        seed=args.seed,
        dt=args.dt,
        t_end=args.t_end,
        evaluator_profile_id=args.evaluator_profile,
        algorithm_config=algorithm_config,
        output_root=args.output,
    )


def _cmd_record(args: argparse.Namespace) -> int:
    result = record(_build_spec(args))
    print(
        json.dumps(
            {
                "run_dir": str(result.run_dir),
                "trace_dir": str(result.trace_dir),
                "state": result.state,
            },
            indent=2,
        )
    )
    return 0


def _open(args: argparse.Namespace) -> TraceBundle:
    """Open the run directory named by parsed args."""
    return TraceBundle(Path(args.run_dir))


def _emit(payload: Any) -> None:
    """Print one report as strict JSON."""
    print(json.dumps(payload, indent=2, allow_nan=False))


def _cmd_summary(args: argparse.Namespace) -> int:
    _emit(_open(args).summary())
    return 0


def _cmd_startup(args: argparse.Namespace) -> int:
    _emit(probes.startup_timeline(_open(args), seconds=args.seconds))
    return 0


def _cmd_primary(args: argparse.Namespace) -> int:
    _emit(probes.why_primary(_open(args), at=args.at))
    return 0


def _cmd_chain(args: argparse.Namespace) -> int:
    _emit(probes.target_chain(_open(args), args.target_id, t0=args.t0, t1=args.t1))
    return 0


def _cmd_solves(args: argparse.Namespace) -> int:
    _emit(probes.planner_timeline(_open(args)))
    return 0


def _cmd_risk(args: argparse.Namespace) -> int:
    _emit(probes.risk_transitions(_open(args), target_id=args.target_id))
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    _emit(probes.explain_tick(_open(args), args.at))
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    _emit(probes.compare_runs(TraceBundle(Path(args.run_a)), TraceBundle(Path(args.run_b))))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the decision-replay CLI parser."""
    parser = argparse.ArgumentParser(prog="decision_replay", description="Offline decision-replay harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="run one headless simulation with full decision trace")
    record_parser.add_argument("--scenario", required=True)
    record_parser.add_argument("--algorithm", default="mid_mpc_ipopt")
    record_parser.add_argument("--tracker", default="god")
    record_parser.add_argument("--validation-rule-id")
    record_parser.add_argument("--seed", type=int, default=0)
    record_parser.add_argument("--dt", type=float)
    record_parser.add_argument("--t-end", type=float)
    record_parser.add_argument("--algorithm-config")
    record_parser.add_argument("--evaluator-profile", default="ccta_2023_demo-v1")
    record_parser.add_argument("--output", default="runs")
    record_parser.set_defaults(fn=_cmd_record)

    def with_run_dir(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("run_dir")
        return sub

    summary_parser = with_run_dir(subparsers.add_parser("summary", help="bundle overview"))
    summary_parser.set_defaults(fn=_cmd_summary)

    startup_parser = with_run_dir(subparsers.add_parser("startup", help="tick-by-tick startup reconstruction"))
    startup_parser.add_argument("--seconds", type=float, default=30.0)
    startup_parser.set_defaults(fn=_cmd_startup)

    primary_parser = with_run_dir(subparsers.add_parser("primary", help="who is primary at T and why"))
    primary_parser.add_argument("--at", type=float, default=None)
    primary_parser.set_defaults(fn=_cmd_primary)

    chain_parser = with_run_dir(subparsers.add_parser("chain", help="per-tick evidence rows for one target"))
    chain_parser.add_argument("target_id", type=int)
    chain_parser.add_argument("--t0", type=float)
    chain_parser.add_argument("--t1", type=float)
    chain_parser.set_defaults(fn=_cmd_chain)

    solves_parser = with_run_dir(subparsers.add_parser("solves", help="planner solve timeline"))
    solves_parser.set_defaults(fn=_cmd_solves)

    risk_parser = with_run_dir(subparsers.add_parser("risk", help="risk/lifecycle transition journal"))
    risk_parser.add_argument("--target-id", type=int, default=None)
    risk_parser.set_defaults(fn=_cmd_risk)

    explain_parser = with_run_dir(subparsers.add_parser("explain", help="full crosshair of tick at T"))
    explain_parser.add_argument("at", type=float)
    explain_parser.set_defaults(fn=_cmd_explain)

    compare_parser = subparsers.add_parser("compare", help="first divergence between two recorded runs")
    compare_parser.add_argument("run_a")
    compare_parser.add_argument("run_b")
    compare_parser.set_defaults(fn=_cmd_compare)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
