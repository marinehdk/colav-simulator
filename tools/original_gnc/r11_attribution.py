#!/usr/bin/env python3
"""R11 attribution: are the multiship give-way NON_COMPLIANT port alterations
real COLREG violations, or actions serving the concurrent overtaking target?

Offline replay of recorded P4 bundles only (no simulator import, no episode
reruns). For each flagged encounter it reconstructs:
  1. the planner primary-target timeline (primary_switched / lifecycle events),
  2. the ownship course-command / heading / speed timeline around the scored
     first alteration, with both targets' geometry,
  3. counterfactual tracks integrated from the recorded ownship state at the
     alteration index: (a) hold the pre-alteration heading, (b) mirror the
     recorded post-alteration heading profile to starboard, both at recorded
     SOG -- then scores clearance to every target with the same center-to-
     center range logic the scorer uses (50 m collision / 1000 m risk).

Pure function of the bundle artifacts: JSON + Parquet in, JSON text out.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

WORKTREE = Path(__file__).resolve().parents[2]
BRIDGE = WORKTREE / "build/original_gnc-glibc-v8/product-campaign-p4-bridge"

RUNS = {
    "fan-MS-E0": BRIDGE / "potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E0/de40b477-8b91-4a47-9bb7-bed625548ccb",
    "fan-MS-E4": BRIDGE / "potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E4/a84e1fc7-0b3d-4b27-9c69-a2278cbf4b7d",
    "vo-MS-E4": BRIDGE / "vo-paper_ccta2023_multiship-E4/7ceef4f5-9658-4bc4-b4ca-fa79be617e7a",
}
# Scored first-alteration indices from build/original_gnc-glibc-v8/colreg-scoring-p4/.
FLAGGED = {
    "fan-MS-E0": [2, 3],
    "fan-MS-E4": [2],
    "vo-MS-E4": [2],
}
ALTERATION_IDX = {  # scorer evidence: first_alteration_index per (run, target)
    ("fan-MS-E0", 2): 5599,
    ("fan-MS-E0", 3): 11286,
    ("fan-MS-E4", 2): 5047,
    ("vo-MS-E4", 2): 3966,
}
COLLISION_M = 50.0
RISK_M = 1000.0


def wrap(a: float) -> float:
    w = (a + math.pi) % (2.0 * math.pi) - math.pi
    return w + 2.0 * math.pi if w <= -math.pi else w


def load_tracks(run_dir: Path):
    cols = ["ship_id", "sim_time", "east_m", "north_m", "sog_mps", "psi_rad",
            "applied_course_ref_rad", "applied_speed_ref_mps"]
    rows = pq.read_table(run_dir / "trajectory.parquet", columns=cols).to_pylist()
    ships: dict[int, dict[str, np.ndarray]] = {}
    for r in rows:
        d = ships.setdefault(int(r["ship_id"]), {k: [] for k in cols})
        for k in cols:
            d[k].append(r[k])
    return {s: {k: np.array(v) for k, v in d.items()} for s, d in sorted(ships.items())}


def integrate(own, i0: int, psi_alt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Dead-reckon positions from recorded state at i0 using alternative headings + recorded SOG."""
    n = len(own["sim_time"])
    e = np.array(own["east_m"], dtype=float)
    nn = np.array(own["north_m"], dtype=float)
    for i in range(i0 + 1, n):
        dt = own["sim_time"][i] - own["sim_time"][i - 1]
        sog = 0.5 * (own["sog_mps"][i] + own["sog_mps"][i - 1])
        psi = 0.5 * (psi_alt[i] + psi_alt[i - 1])
        e[i] = e[i - 1] + sog * math.sin(psi) * dt
        nn[i] = nn[i - 1] + sog * math.cos(psi) * dt
    return e, nn


def min_dist_series(e, n, tgt) -> tuple[float, float]:
    r = np.hypot(e - tgt["east_m"], n - tgt["north_m"])
    k = int(np.argmin(r))
    return float(r[k]), float(tgt["sim_time"][k])


def primary_timeline(run_dir: Path) -> list[tuple[float, int, str]]:
    out = []
    for line in (run_dir / "events.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        d = e.get("details") or {}
        if e.get("type") == "primary_switched":
            out.append((float(e["sim_time"]), int(d.get("target_id", -1)), str(d.get("reason"))))
        elif e.get("type") == "avoidance_action_started":
            out.append((float(e["sim_time"]), int(d.get("target_id", -1)), "AVOIDANCE_ACTION_STARTED"))
    return sorted(out)


def primary_at(timeline, t: float) -> int | None:
    cur = None
    for ts, tid, why in timeline:
        if ts > t:
            break
        # before the first primary_switched, the avoidance-action opener is the de-facto primary
        cur = tid
    return cur


def analyze(run_name: str) -> dict:
    run_dir = RUNS[run_name]
    ships = load_tracks(run_dir)
    own = ships[0]
    targets = {t: ships[t] for t in ships if t != 0}
    timeline = primary_timeline(run_dir)
    lifecycle = []
    for line in (run_dir / "lifecycle_events.jsonl").read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            key = e.get("target_key") or {}
            lifecycle.append((float(e["sim_time_s"]), key.get("target_id"), e.get("to_state")))

    result = {"run": run_name, "primary_timeline": [
        {"t": round(ts, 1), "primary": tid, "why": why} for ts, tid, why in timeline]}
    result["lifecycle"] = [{"t": round(ts, 1), "tid": tid, "to": st} for ts, tid, st in lifecycle]

    for tid in FLAGGED[run_name]:
        tgt = targets[tid]
        i0 = ALTERATION_IDX[(run_name, tid)]
        # detection time from the scored JSON, matched by run_id
        scored = json.loads((BRIDGE.parent / "colreg-scoring-p4/product-campaign-p4-bridge.json").read_text())
        detect_t = None
        for cell in scored["cells"]:
            if cell["run_id"] == run_dir.name:
                for enc in cell["encounters"]:
                    if enc["target_id"] == tid:
                        detect_t = enc["detected_time_s"]
        detect_i = int(np.searchsorted(own["sim_time"], detect_t, side="left"))
        # scorer baseline: circular mean over [detect, detect+10s]
        w = own["psi_rad"][detect_i:detect_i + 100]
        base = math.atan2(float(np.sin(w).mean()), float(np.cos(w).mean()))

        def snap(i):
            return {
                "t": round(float(own["sim_time"][i]), 1),
                "psi_deg": round(math.degrees(float(own["psi_rad"][i])), 1),
                "cref_deg": round(math.degrees(float(own["applied_course_ref_rad"][i])), 1),
                "sog": round(float(own["sog_mps"][i]), 2),
                "sref": round(float(own["applied_speed_ref_mps"][i]), 2),
            }

        geom = {}
        for j, other in targets.items():
            r = np.hypot(own["east_m"] - other["east_m"], own["north_m"] - other["north_m"])
            b = np.degrees(np.arctan2(other["east_m"] - own["east_m"], other["north_m"] - own["north_m"]))
            rel = np.array([wrap(math.radians(bb) - pp) for bb, pp in zip(b, own["psi_rad"])])
            geom[j] = {
                "range_m_at_alteration": round(float(r[i0]), 1),
                "bearing_deg_at_alteration": round(float(b[i0]), 1),
                "rel_bearing_deg_at_alteration": round(math.degrees(float(rel[i0])), 1),
                "min_range_m": round(float(r.min()), 1),
            }

        dev0 = wrap(float(own["psi_rad"][i0]) - base)
        n = len(own["sim_time"])
        # (a) hold baseline heading from i0, recorded SOG
        e_hold, n_hold = integrate(own, i0, np.full(n, base))
        # (b) mirror the recorded post-alteration heading profile to starboard
        psi_mirror = np.array([wrap(2.0 * base - p) for p in own["psi_rad"]])
        e_mir, n_mir = integrate(own, i0, psi_mirror)
        e_rec = np.array(own["east_m"])
        n_rec = np.array(own["north_m"])

        cf = {}
        for j, other in targets.items():
            cf[j] = {
                "recorded": min_dist_series(e_rec, n_rec, other),
                "hold_baseline": min_dist_series(e_hold, n_hold, other),
                "starboard_mirror": min_dist_series(e_mir, n_mir, other),
            }

        result[f"target_{tid}"] = {
            "detect_t": detect_t,
            "detect_i": detect_i,
            "alteration_i": i0,
            "alteration_t": round(float(own["sim_time"][i0]), 1),
            "baseline_deg": round(math.degrees(base), 1),
            "deviation_at_alteration_deg": round(math.degrees(dev0), 1),
            "primary_at_alteration": primary_at(timeline, float(own["sim_time"][i0])),
            "state_at_detect": snap(detect_i),
            "state_at_alteration": snap(i0),
            "state_10s_after": snap(min(i0 + 100, n - 1)),
            "geometry": geom,
            "counterfactual_min_ranges_m": {
                str(j): {k: [round(v[0], 1), round(v[1], 1)] for k, v in d.items()} for j, d in cf.items()
            },
        }
    return result


def main() -> None:
    out = {name: analyze(name) for name in RUNS}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
