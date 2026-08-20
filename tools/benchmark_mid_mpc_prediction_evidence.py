#!/usr/bin/env python3
"""Benchmark the synchronous Mid-MPC Prediction Evidence critical tail."""

from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import statistics
import time
from pathlib import Path

import numpy as np

from colav_simulator.core.colav.prediction_evidence import (
    EvidenceEvent,
    EvidenceEventType,
    EvidenceTrackKey,
    OccurrenceId,
    OptimizationIntervalReference,
    OwnshipPrediction,
    PredictionEvidenceRecord,
    PredictionGrid,
    PredictionPurpose,
    RuntimeAppliedReference,
    TargetPredictionEvidence,
    TerminalOutcome,
    inline_projection,
    reduce_evidence,
    render_snapshot,
)


def _record(target_count: int, *, accepted: bool) -> PredictionEvidenceRecord:
    grid = PredictionGrid()
    headings = np.linspace(0.0, 0.08, grid.intervals)
    speeds = np.linspace(8.0, 7.8, grid.intervals)
    north = np.concatenate(([0.0], np.cumsum(speeds * np.cos(headings) * grid.dt_s)))
    east = np.concatenate(([0.0], np.cumsum(speeds * np.sin(headings) * grid.dt_s)))
    references = tuple(
        OptimizationIntervalReference(
            interval_index=index,
            start_s=index * grid.dt_s,
            end_s=(index + 1) * grid.dt_s,
            heading_rad=float(headings[index]),
            speed_mps=float(speeds[index]),
            heading_raw_index=index,
            speed_raw_index=grid.intervals + index,
        )
        for index in range(grid.intervals)
    )
    ownship = OwnshipPrediction(
        grid=grid,
        north_m=north,
        east_m=east,
        heading_rad=np.concatenate(([0.0], headings)),
        speed_mps=np.concatenate(([8.0], speeds)),
        state_sources=("MEASURED", *(["IPOPT_INTEGRATED"] * grid.intervals)),
        interval_references=references,
    )
    targets = []
    times = np.asarray(grid.times_s)
    for target_id in range(target_count):
        target_north = 1000.0 + target_id * 100.0 - 2.0 * times
        target_east = np.full(grid.state_samples, 50.0 * target_id)
        common = {
            "key": EvidenceTrackKey(target_id + 1, 1),
            "reference_time_s": 0.0,
            "model": "constant_velocity",
            "north_m": target_north,
            "east_m": target_east,
            "admitted_to_nlp": True,
            "solver_slot": target_id,
            "observation_time_s": 0.0,
            "generated_at_s": 0.0,
            "health": "NOMINAL",
            "source": "benchmark",
            "state_enu": np.array([target_north[0], target_east[0], -2.0, 0.0]),
            "covariance": np.zeros((4, 4)),
            "length_m": 15.0,
            "width_m": 4.0,
            "lifecycle": {"risk": "ACTIVE", "commitment": "COMMITTED"},
        }
        targets.extend(
            (
                TargetPredictionEvidence(purpose=PredictionPurpose.NLP, **common),
                TargetPredictionEvidence(purpose=PredictionPurpose.L4_SAFETY, **common),
            )
        )
    failures = [] if accepted else [{"code": "SAFETY_SWEPT_CLEARANCE", "target_key": [1, 1]}]
    return PredictionEvidenceRecord(
        algorithm_id="mid_mpc_ipopt",
        candidate_hash="candidate-benchmark",
        acceptance_hash="acceptance-benchmark",
        ownship=ownship,
        target_predictions=tuple(targets),
        acceptance={"accepted": accepted, "mandatory_failures": failures},
        solver={"backend": "ipopt", "return_status": "Solve_Succeeded"},
    )


def _events(record: PredictionEvidenceRecord, mode: str) -> tuple[EvidenceEvent, ...]:
    specs: list[tuple[EvidenceEventType, TerminalOutcome | None, dict[str, object]]] = []
    if mode == "hold":
        specs.extend(
            (
                (EvidenceEventType.CYCLE_STARTED, None, {}),
                (EvidenceEventType.PLAN_COMMITTED, TerminalOutcome.COMMITTED, {"receipt_hash": "receipt"}),
                (EvidenceEventType.COMMAND_APPLIED, None, {}),
                (EvidenceEventType.CYCLE_STARTED, None, {}),
                (EvidenceEventType.PLAN_HELD, TerminalOutcome.HELD, {"elapsed_s": 7.5}),
                (EvidenceEventType.COMMAND_APPLIED, None, {}),
            )
        )
    else:
        terminal = TerminalOutcome.COMMITTED if mode == "fresh" else TerminalOutcome.REJECTED
        terminal_event = EvidenceEventType.PLAN_COMMITTED if mode == "fresh" else EvidenceEventType.PLAN_REJECTED
        terminal_payload = {"receipt_hash": "receipt"} if mode == "fresh" else {}
        specs.extend(
            (
                (EvidenceEventType.CYCLE_STARTED, None, {}),
                (EvidenceEventType.INPUT_VALIDATED, None, {}),
                (EvidenceEventType.SOLVE_ATTEMPTED, None, {}),
                (EvidenceEventType.CANDIDATE_PRODUCED, None, {}),
                (EvidenceEventType.L4_EVALUATED, None, {}),
                (terminal_event, terminal, terminal_payload),
            )
        )
        if mode == "fresh":
            specs.append((EvidenceEventType.COMMAND_APPLIED, None, {}))
    events = []
    previous = None
    for seq, (kind, outcome, payload) in enumerate(specs):
        occurrence = OccurrenceId("benchmark", 0, seq)
        events.append(
            EvidenceEvent(
                occurrence_id=occurrence,
                event_type=kind,
                sim_time_s=float(seq),
                semantic_hash=record.semantic_hash,
                terminal_outcome=outcome,
                caused_by=previous,
                payload=payload,
            )
        )
        previous = occurrence
    return tuple(events)


def _sample(target_count: int, mode: str) -> tuple[float, int]:
    started = time.perf_counter_ns()
    record = _record(target_count, accepted=mode != "rejected")
    events = _events(record, mode)
    timeline = reduce_evidence(events)
    inline = inline_projection(record)
    runtime = None
    if mode == "hold":
        runtime = RuntimeAppliedReference.linear(
            elapsed_s=7.5,
            dt_s=record.ownship.grid.dt_s,
            heading_rad=record.ownship.heading_rad,
            speed_mps=record.ownship.speed_mps,
        )
    render_snapshot(record, timeline, runtime_reference=runtime)
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
    return elapsed_ms, len(json.dumps(inline, separators=(",", ":")).encode())


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def main() -> int:
    """Run the fixed target-count and control-outcome benchmark matrix."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.samples < 1:
        raise SystemExit("--samples must be positive")
    for _ in range(10):
        _sample(16, "fresh")
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    results = []
    for target_count in (0, 1, 16):
        for mode in ("fresh", "hold", "rejected"):
            timings = []
            inline_sizes = []
            for _ in range(args.samples):
                elapsed_ms, inline_size = _sample(target_count, mode)
                timings.append(elapsed_ms)
                inline_sizes.append(inline_size)
            results.append(
                {
                    "target_count": target_count,
                    "mode": mode,
                    "samples": args.samples,
                    "p50_ms": statistics.median(timings),
                    "p95_ms": _percentile(timings, 0.95),
                    "p99_ms": _percentile(timings, 0.99),
                    "max_ms": max(timings),
                    "max_inline_bytes": max(inline_sizes),
                }
            )
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_to_kib = 1024 if platform.system() == "Darwin" else 1
    document = {
        "schema_version": "colav.mid_mpc.prediction-evidence-benchmark@1",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "samples_per_case": args.samples,
        "results": results,
        "max_rss_delta_kib": max(0, rss_after - rss_before) / rss_to_kib,
        "deadline_s": 20.0,
    }
    encoded = json.dumps(document, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
