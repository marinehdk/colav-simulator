#!/usr/bin/env python3
"""Spec #91 item 1: vimmjipda legacy-Radar vs RadarXBand track comparison.

Runs the same seeded scenario truth through two vimmjipda instances — one
fusing the legacy ``Radar`` channel, one fusing the ``RadarXBand`` spoke-radar
model (the multi-source wiring accepted by the external capability check,
external repo commit 58e4903) — and writes the track-difference statistics
JSON next to the s5 god-vs-vimmjipda report (tools/sango_track_compare_s5.py
harness lineage: same dead-reckoning truth model, same nearest-neighbour
association, report-only fusion policy).

Expectation written into the JSON (``parity_policy``): the two channels are
different noise/clutter models (radar_x: sigma_r = 8 m + 1 deg azimuth vs the
legacy 5 m isotropic R_ne), so per-target RMSE is expected to stay within the
same order of magnitude (``rmse_ratio_max`` = one decade, reported not gated).

Usage:
    .venv/bin/python tools/sango_vimmjipda_sensor_compare_s5.py \
        --scenario scenarios/crossing_stand_on.yaml \
        --output output/sango-fusion-s5/track-compare-radarx.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from sango_track_compare_s5 import (
    ASSOCIATION_GATE_M,
    CONFIRM_THRESHOLD,
    _advance_along_waypoints,
    _load_ships,
    _waypoint_path,
)

from colav_simulator.core.sensing import Radar, RadarParams, RadarXBand
from colav_simulator.integrations.registry import IntegrationRegistry

#: Report-only parity bound: "same order of magnitude" = within one decade.
RMSE_RATIO_MAX = 10.0
#: Default caps mirroring the s5 god-vs-vimmjipda harness.
DEFAULT_DURATION_S = 600.0
DEFAULT_DT_S = 0.5


def _build_sensor(kind: str, seed: int) -> Any:
    if kind == "radar":
        sensor = Radar(RadarParams(max_range=2000.0, generate_clutter=False))
    elif kind == "radar_x":
        sensor = RadarXBand()
    else:
        raise SystemExit(f"unknown sensor kind: {kind}")
    sensor.seed(seed)
    return sensor


def _run_fusion_leg(
    tracker: Any, sensor: Any, ships: list[dict[str, Any]], *, dt: float, duration_s: float
) -> dict[str, Any]:
    """One seeded fusion leg; per-target NN-association stats + acceptance counts."""
    tracker.set_sensor_list([sensor])
    paths = [_waypoint_path(ship) for ship in ships]
    states = [path[0].copy() for path in paths]
    ownship_state = states[0]
    histories: dict[int, dict[str, list[float]]] = {
        target_id: {"error_m": [], "existence": []} for target_id in range(1, len(ships))
    }
    accepted_measurements = 0
    t = 0.0
    steps = int(round(duration_s / dt))
    for _ in range(steps):
        true_do_states = [(target_id, states[target_id], 30.0, 7.0) for target_id in range(1, len(ships))]
        tracks, sensor_measurements = tracker.track(t, dt, true_do_states, ownship_state)
        accepted_measurements += sum(
            1
            for frame in sensor_measurements
            for meas_tup in frame
            if meas_tup[0] >= 0 and not np.any(np.isnan(meas_tup[1]))
        )
        track_states = {int(track[0]): np.asarray(track[1], dtype=float) for track in tracks}
        for track in tracks:
            history = histories.setdefault(int(track[0]), {"error_m": [], "existence": []})
            history["existence"].append(float(getattr(track, "existence_prob", float("nan"))))
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
        finite_existence = existence_values[np.isfinite(existence_values)]
        targets[str(target_id)] = {
            "frames_tracked": int(errors.size),
            "position_rmse_m": float(np.sqrt(np.mean(errors**2))) if errors.size else None,
            "position_max_error_m": float(np.max(errors)) if errors.size else None,
            "existence_mean": float(np.mean(finite_existence)) if finite_existence.size else None,
            "confirmed_fraction": (
                float(np.mean(finite_existence >= CONFIRM_THRESHOLD)) if finite_existence.size else None
            ),
        }
    return {
        "steps": steps,
        "accepted_target_measurements": accepted_measurements,
        "final_track_count": len(tracker.get_track_information(ownship_state)[0]),
        "targets": targets,
    }


def main() -> None:
    """Run both seeded legs and write the comparison JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=Path("scenarios/crossing_stand_on.yaml"))
    parser.add_argument("--output", type=Path, default=Path("output/sango-fusion-s5/track-compare-radarx.json"))
    parser.add_argument("--dt", type=float, default=DEFAULT_DT_S)
    parser.add_argument("--duration-s", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    ships = _load_ships(args.scenario)
    registry = IntegrationRegistry()
    if not registry.statuses()["vimmjipda"].available:
        raise SystemExit("vimmjipda unavailable — COLAV_ECOSYSTEM_ROOT not set?")

    legs = {}
    for kind in ("radar", "radar_x"):
        tracker = registry.build_tracker("vimmjipda")
        sensor = _build_sensor(kind, args.seed)
        legs[kind] = _run_fusion_leg(tracker, sensor, ships, dt=args.dt, duration_s=args.duration_s)
        tracker.reset()

    rmse_ratios: dict[str, float | None] = {}
    for target_id in sorted(set(legs["radar"]["targets"]) | set(legs["radar_x"]["targets"])):
        legacy = legs["radar"]["targets"].get(target_id, {}).get("position_rmse_m")
        radar_x = legs["radar_x"]["targets"].get(target_id, {}).get("position_rmse_m")
        if legacy and radar_x and min(legacy, radar_x) > 0.0:
            rmse_ratios[target_id] = max(legacy, radar_x) / min(legacy, radar_x)
        else:
            rmse_ratios[target_id] = None
    comparable = [value for value in rmse_ratios.values() if value is not None]

    document = {
        "schema_version": "sango-fusion-s5/track-compare-sensors@1",
        "spec": "#91 item 1: vimmjipda legacy-Radar vs RadarXBand track comparison",
        "external_repo_commit": "vimmjipda 58e4903 (capability-based sensor acceptance)",
        "scenario": str(args.scenario),
        "seed": args.seed,
        "truth_model": "constant-speed waypoint following (dead reckoning)",
        "tolerances": {
            "association_gate_m": ASSOCIATION_GATE_M,
            "confirm_threshold": CONFIRM_THRESHOLD,
            "parity_policy": "report-only: per-target RMSE expected within the same order of magnitude",
            "rmse_ratio_max": RMSE_RATIO_MAX,
        },
        "radar": legs["radar"],
        "radar_x": legs["radar_x"],
        "rmse_ratio_legacy_over_radar_x_per_target": rmse_ratios,
        "rmse_ratio_max_observed": max(comparable) if comparable else None,
        "rmse_same_order_of_magnitude": bool(comparable) and max(comparable) <= RMSE_RATIO_MAX,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
    print(
        json.dumps(
            {
                "scenario": str(args.scenario),
                "seed": args.seed,
                "rmse_ratio_max_observed": document["rmse_ratio_max_observed"],
                "rmse_same_order_of_magnitude": document["rmse_same_order_of_magnitude"],
            },
            indent=2,
        )
    )
    print(f"written: {args.output}")


if __name__ == "__main__":
    main()
