#!/usr/bin/env python3
"""P3-S5 (spec #90) god vs VIMMJIPDA tracker head-to-head on one scenario.

Runs the same scenario truth through two trackers with identically seeded
radar sensors (same measurement stream), and writes a track-difference
statistics JSON to output/sango-fusion-s5/.

Truth model: every scenario ship dead-reckons along its waypoints at
``speed_plan`` (constant-speed path following). This is a tracker-level
harness — guidance/controller/planner are deliberately out of the loop so the
only difference between the two runs is the tracker.

Tolerances (written into the JSON, no hidden gates):
- ``god_position_rmse_tolerance_m`` (1e-6): GodTracker copies truth, so its
  per-target RMSE must be numerically zero.
- VIMMJIPDA accuracy is reported, not gated: the external IPDA runs its own
  confirmation/termination logic, and the harness has no oracle for it. The
  report records RMSE plus existence-probability distribution and the
  confirmed-track fraction so future regression sweeps have a baseline.
- Target association for the fusion tracker is per-frame nearest-neighbour
  within ``association_gate_m`` (vimmjipda assigns its own track indexes, not
  the simulator do_idx).

Usage:
    .venv/bin/python tools/sango_track_compare_s5.py \
        --scenario scenarios/crossing_stand_on.yaml \
        --output output/sango-fusion-s5/track-compare.json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from colav_simulator.core.sensing import Radar, RadarParams
from colav_simulator.core.tracking.trackers import GodTracker
from colav_simulator.integrations.registry import IntegrationRegistry

#: GodTracker truth copy: position RMSE must stay numerically zero.
GOD_POSITION_RMSE_TOLERANCE_M = 1.0e-6
#: Per-frame nearest-neighbour gate for associating fusion tracks to targets.
ASSOCIATION_GATE_M = 200.0
#: Existence gate for the confirmed-track fraction (sensor-model-v1 §4 anchor).
CONFIRM_THRESHOLD = 0.999
#: Default caps so ad-hoc scenario files cannot explode the runtime.
DEFAULT_DURATION_S = 600.0
DEFAULT_DT_S = 0.5


def _load_ships(scenario_path: Path) -> list[dict[str, Any]]:
    with open(scenario_path, "r") as stream:
        scenario = yaml.safe_load(stream)
    ships = scenario.get("ship_list") or []
    if len(ships) < 2:
        raise SystemExit("scenario needs at least an ownship and one obstacle")
    return ships


def _waypoint_path(ship: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Start pose and waypoint list (north/east, closed over the plan)."""
    state = np.asarray(ship["csog_state"], dtype=float)[:4]
    waypoints = np.asarray(ship.get("waypoints") or [], dtype=float)
    if waypoints.ndim != 2 or waypoints.shape[0] < 2 or waypoints.shape[1] != 2:
        raise SystemExit("scenario ship needs waypoints [[north...], [east...]]")
    waypoints = np.column_stack((waypoints[0], waypoints[1]))
    speed_plan = ship.get("speed_plan") or [7.0]
    speed = float(speed_plan[0]) if np.ndim(speed_plan) else 7.0
    return state, waypoints, speed


def _advance_along_waypoints(state: np.ndarray, waypoints: np.ndarray, speed: float, dt: float) -> np.ndarray:
    """One constant-speed step toward the active waypoint (loops the path)."""
    position = state[:2].copy()
    target = waypoints[0]
    for candidate in waypoints:
        if np.linalg.norm(candidate - position) > 1.0e-6:
            target = candidate
            break
    else:
        target = waypoints[0]
    direction = target - position
    distance = float(np.linalg.norm(direction))
    if distance <= 1.0e-6:
        return state
    step = min(speed * dt, distance)
    heading_unit = direction / distance
    next_position = position + heading_unit * step
    return np.array([next_position[0], next_position[1], heading_unit[0] * speed, heading_unit[1] * speed])


def _run_tracker(tracker: Any, ships: list[dict[str, Any]], *, dt: float, duration_s: float, seed: int) -> dict[str, Any]:
    radar = Radar(RadarParams(max_range=2000.0, generate_clutter=False))
    radar.seed(seed)
    tracker.set_sensor_list([radar])

    paths = [_waypoint_path(ship) for ship in ships]
    states = [path[0].copy() for path in paths]
    ownship_state = states[0]
    histories: dict[int, dict[str, list[float]]] = {
        target_id: {"error_m": [], "existence": [], "generation": []} for target_id in range(1, len(ships))
    }
    t = 0.0
    steps = int(round(duration_s / dt))
    last_tracks: list[Any] = []
    for _ in range(steps):
        true_do_states = [
            (target_id, states[target_id], 30.0, 7.0) for target_id in range(1, len(ships))
        ]
        tracks, _ = tracker.track(t, dt, true_do_states, ownship_state)
        last_tracks = list(tracks)
        track_states = {}
        for track in tracks:
            target_id = int(track[0])
            track_states[target_id] = np.asarray(track[1], dtype=float)
            existence = getattr(track, "existence_prob", None)
            history = histories.setdefault(
                target_id, {"error_m": [], "existence": [], "generation": []}
            )
            if existence is not None:
                history["existence"].append(float(existence))
            history["generation"].append(int(getattr(track, "key").generation))
        # Nearest-neighbour association for index-shifting trackers (vimmjipda).
        assigned: set[int] = set()
        for target_id in range(1, len(ships)):
            truth = states[target_id]
            best_id, best_range = None, ASSOCIATION_GATE_M
            for tracked_id, estimate in track_states.items():
                if tracked_id in assigned:
                    continue
                rng = float(np.linalg.norm(estimate[:2] - truth[:2]))
                if rng <= best_range:
                    best_id, best_range = tracked_id, rng
            if best_id is None:
                continue
            assigned.add(best_id)
            estimate = track_states[best_id]
            histories[target_id]["error_m"].append(best_range)
        for ship_index in range(len(ships)):
            states[ship_index] = _advance_along_waypoints(
                states[ship_index], paths[ship_index][1], paths[ship_index][2], dt
            )
        ownship_state = states[0]
        t += dt

    targets: dict[str, Any] = {}
    for target_id, history in sorted(histories.items()):
        errors = np.asarray(history["error_m"], dtype=float)
        existence_values = np.asarray(history["existence"], dtype=float)
        rmse = float(np.sqrt(np.mean(errors**2))) if errors.size else None
        targets[str(target_id)] = {
            "frames_tracked": int(errors.size),
            "position_rmse_m": rmse,
            "position_mean_error_m": float(np.mean(errors)) if errors.size else None,
            "position_max_error_m": float(np.max(errors)) if errors.size else None,
            "existence_frames": int(existence_values.size),
            "existence_min": float(np.min(existence_values)) if existence_values.size else None,
            "existence_mean": float(np.mean(existence_values)) if existence_values.size else None,
            "existence_max": float(np.max(existence_values)) if existence_values.size else None,
            "existence_final": float(existence_values[-1]) if existence_values.size else None,
            "confirmed_fraction": (
                float(np.mean(existence_values >= CONFIRM_THRESHOLD)) if existence_values.size else None
            ),
        }
    return {
        "steps": steps,
        "dt_s": dt,
        "targets": targets,
        "rmse_tolerance_m": GOD_POSITION_RMSE_TOLERANCE_M if isinstance(tracker, GodTracker) else None,
    }, last_tracks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=Path("scenarios/crossing_stand_on.yaml"))
    parser.add_argument("--output", type=Path, default=Path("output/sango-fusion-s5/track-compare.json"))
    parser.add_argument("--dt", type=float, default=DEFAULT_DT_S)
    parser.add_argument("--duration-s", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    ships = _load_ships(args.scenario)
    fusion = IntegrationRegistry().build_tracker("vimmjipda")
    if fusion is None:
        raise SystemExit("vimmjipda unavailable — COLAV_ECOSYSTEM_ROOT not set?")

    god_report, _ = _run_tracker(GodTracker([]), ships, dt=args.dt, duration_s=args.duration_s, seed=args.seed)
    fusion_report, fusion_last_tracks = _run_tracker(
        fusion, ships, dt=args.dt, duration_s=args.duration_s, seed=args.seed
    )

    god_rmse = [value["position_rmse_m"] for value in god_report["targets"].values()]
    document = {
        "schema_version": "sango-fusion-s5/track-compare@1",
        "spec": "#90 P3-S5 god vs vimmjipda track comparison",
        "scenario": str(args.scenario),
        "seed": args.seed,
        "truth_model": "constant-speed waypoint following (dead reckoning)",
        "tolerances": {
            "god_position_rmse_tolerance_m": GOD_POSITION_RMSE_TOLERANCE_M,
            "fusion_association_gate_m": ASSOCIATION_GATE_M,
            "confirm_threshold": CONFIRM_THRESHOLD,
            "fusion_policy": "report-only (no oracle gate for the external IPDA)",
        },
        "god": god_report,
        "vimmjipda": fusion_report,
        "god_rmse_within_tolerance": all(
            value is not None and value <= GOD_POSITION_RMSE_TOLERANCE_M for value in god_rmse
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
    print(json.dumps({key: document[key] for key in ("scenario", "seed", "god_rmse_within_tolerance")}, indent=2))
    print(f"written: {args.output}")

    sample_path = args.output.parent / "confirmed-tracks-sample.json"
    write_confirmed_sample(fusion_last_tracks, final_t=args.duration_s, output=sample_path)
    print(f"written: {sample_path}")


def write_confirmed_sample(tracks: list[Any], *, final_t: float, output: Path) -> None:
    """Emit one genuine vimmjipda confirmed-tracks envelope (sensor-model-v1 §5).

    Reuses the endpoint serializer against a synthetic session frame holding the
    harness's final fusion-tracker snapshot set — the same code path the
    ``GET /api/sessions/{id}/confirmed-tracks`` route uses.
    """
    from types import SimpleNamespace

    from gui_server.main import WebSessionManager

    raw = {
        "timestamp": final_t,
        "do_labels": [track.target_id for track in tracks],
        "do_generations": [track.key.generation for track in tracks],
        "do_estimates": [track.state.tolist() for track in tracks],
        "do_covariances": [track.covariance.tolist() for track in tracks],
        "do_NISes": [0.0 for _ in tracks],
        "do_existence_probabilities": [track.existence_prob for track in tracks],
        "do_qualities": [track.quality for track in tracks],
        "do_sources": [
            [{"sensor_id": source.sensor_id, "last_seen_age_s": source.last_seen_age_s} for source in track.sources]
            for track in tracks
        ],
    }
    session = SimpleNamespace(
        last_frame={"Ship0": raw},
        ship_list=[SimpleNamespace(sensors=[])],
        enc=SimpleNamespace(origin=(40500.0, 6958000.0)),
        simulator=SimpleNamespace(t=final_t),
    )
    manager = WebSessionManager()
    manager.prepared = SimpleNamespace(
        session=session,
        manifest=SimpleNamespace(run_id="s5-sample"),
    )
    document = manager.confirmed_tracks("s5-sample")
    with open(output, "w") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
