"""Measure real WebSessionManager throughput, including replay and shared telemetry.

Run from the repository root with its active virtualenv. This measures uncapped
production capacity; a live requested-speed test is still needed for playback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from colav_simulator.experiment.contracts import RunSpec, SessionState
from colav_simulator.experiment.persistence import jsonable
from gui_server.main import WebSessionManager


def main() -> None:  # noqa: PLR0915 - keep the measured path and its gates visible together
    """Benchmark an exact RunSpec without replacing the running Web session."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True, help="RunSpec JSON or a run manifest containing spec")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration-s", type=float, default=3000.0)
    parser.add_argument("--solve-period-s", type=float, default=10.0)
    parser.add_argument("--minimum-multiplier", type=float, default=5.0)
    parser.add_argument("--capture-budget-bytes", type=int, default=8 * 1024**3)
    args = parser.parse_args()
    os.environ["COLAV_REPLAY_CAPTURE_BUDGET_BYTES"] = str(args.capture_budget_bytes)
    document = json.loads(args.spec.read_text())
    spec = RunSpec.from_dict(document.get("spec", document))
    spec = replace(spec, solve_period_s=args.solve_period_s, output_root=str(args.output / "runs"))
    args.output.mkdir(parents=True, exist_ok=True)
    manager = WebSessionManager()
    manager.create(spec)
    session = manager.prepared.session
    manager.start(manager.session_id)
    rows = []
    digest = hashlib.sha256()
    started = time.perf_counter()
    try:
        while session.state == SessionState.RUNNING and session.simulator.t < args.duration_s:
            before = time.perf_counter()
            manager.tick()
            tick_s = time.perf_counter() - before
            before = time.perf_counter()
            manager.stream_document(shared_planner=True, include_static=False)
            stream_s = time.perf_counter() - before
            frame = session.last_frame
            planner = frame["Ship0"]["colav"]["planner"]
            digest.update(
                json.dumps(
                    jsonable(
                        {
                            name: {key: ship[key] for key in ("state", "input", "references") if key in ship}
                            for name, ship in frame.items()
                            if name.startswith("Ship")
                        }
                    ),
                    sort_keys=True,
                ).encode()
            )
            rows.append(
                {
                    "sim_time_s": session.simulator.t,
                    "wall_s": time.perf_counter() - started,
                    "tick_s": tick_s,
                    "stream_s": stream_s,
                    "planner_ms": planner.get("elapsed_ms"),
                    "solver_executed": planner.get("solver_executed"),
                    "fallback_used": frame["Ship0"]["colav"]["diagnostics"]["fallback_used"],
                }
            )
        wall_s = time.perf_counter() - started
    finally:
        manager.pause(manager.session_id)
        manager.prepared.artifact_sink.close(timeout_s=5.0)
    ship = session.ship_list[0]
    leg = ship.waypoints[:, -1] - ship.waypoints[:, -2]
    normal = np.array([-leg[1], leg[0]]) / np.linalg.norm(leg)
    summary = {
        "run_dir": str(manager.prepared.run_dir),
        "state": session.state.value,
        "sim_time_s": session.simulator.t,
        "wall_s": wall_s,
        "effective_multiplier": session.simulator.t / wall_s,
        "state_control_sha256": digest.hexdigest(),
        "goal_distance_m": float(np.linalg.norm(ship.state[:2] - ship.waypoints[:, -1])),
        "final_leg_cross_track_m": float((ship.state[:2] - ship.waypoints[:, -2]) @ normal),
        "fallback_used": any(row["fallback_used"] for row in rows),
    }
    (args.output / "timing.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    if session.state == SessionState.FINISHED:
        manager._result_executor.shutdown(wait=True)
        if manager.result is None:
            raise RuntimeError(session.failure_reason or "Evaluation did not complete")
        (args.output / "evaluation.json").write_text(json.dumps(manager.result.evaluation.to_dict(), indent=2))
    else:
        manager._finalize_replay_capture(manager.prepared)
    summary["replay"] = manager.replay_status_for(manager.session_id)
    (args.output / "timing.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    if summary["replay"]["state"] != "READY":
        raise SystemExit(f"Full recording failed: {summary['replay']}")
    if session.state == SessionState.FAILED or summary["fallback_used"]:
        raise SystemExit(session.failure_reason or "Unexpected fallback")
    if summary["effective_multiplier"] < args.minimum_multiplier:
        raise SystemExit(f"Throughput FAIL: {summary['effective_multiplier']:.3f}x < {args.minimum_multiplier}x")


if __name__ == "__main__":
    main()
