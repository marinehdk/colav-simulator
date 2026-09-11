"""Compare free closed-loop observations without fitting away trajectory differences."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load(directory: Path) -> tuple[dict, dict, dict]:
    """Verify compact observations against their full-evidence reduction manifest."""
    manifest = json.loads((directory / "manifest.json").read_text())
    path = directory / "samples.npz"
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["samples_sha256"]:
        raise ValueError(f"Changed observation samples: {path}")
    with np.load(path, allow_pickle=False) as archive:
        data = {k: archive[k].copy() for k in archive.files}
    return manifest, data, json.loads((directory / "case.json").read_text())


def clock(data: dict, name: str) -> np.ndarray:
    """Use the recorded plant initialization clock, without estimating a time shift."""
    return (data[name + "_time_ns"] - data["epoch_ns"]) / 1e9


def statistics(values: np.ndarray) -> dict:
    """Use every finite sample; explicitly count unavailable observations."""
    finite = np.isfinite(values)
    valid = values[finite]
    if not len(valid):
        return {"sample_count": 0, "missing_count": len(values), "maximum": None, "rmse": None, "p95": None}
    return {
        "sample_count": len(valid),
        "missing_count": int((~finite).sum()),
        "maximum": float(np.max(np.abs(valid))),
        "rmse": float(np.sqrt(np.mean(valid**2))),
        "p95": float(np.quantile(np.abs(valid), 0.95)),
        "last": float(valid[-1]),
    }


def route_distance(points: np.ndarray, route: np.ndarray) -> np.ndarray:
    """Distance to the nearest nominal segment, explicitly distinct from active-segment XTE."""
    result = np.full(len(points), np.inf)
    for start, end in zip(route[:-1], route[1:], strict=True):
        delta = end - start
        length2 = float(delta @ delta)
        if length2 <= 0:
            continue
        fraction = np.clip((points - start) @ delta / length2, 0, 1)
        result = np.minimum(result, np.linalg.norm(points - (start + fraction[:, None] * delta), axis=1))
    return result


def performance(data: dict, case: dict) -> dict:
    """Report task observations independently of any migration-equivalence result."""
    nav = data["navigation"]
    t = clock(data, "navigation")
    route = np.array([[p["north_m"], p["east_m"]] for p in case["waypoints"]])
    distance = route_distance(nav[:, :2], route)
    goal = np.linalg.norm(nav[:, :2] - route[-1], axis=1)
    speed = np.hypot(nav[:, 3], nav[:, 4])
    joint = (goal <= 15) & (speed <= 0.3)
    durations = np.diff(t, append=t[-1])
    allocation = data["allocation"]
    at = clock(data, "allocation")
    weights = np.diff(at, append=at[-1]) if len(at) else np.array([])
    if len(weights) and np.any(weights < 0):
        raise ValueError("Nonmonotonic allocation clock")
    total = float(weights.sum())

    def fraction(mask: np.ndarray) -> float | None:
        return float(weights[mask].sum() / total) if total > 0 else None

    commands = data["commands"]
    changes = np.sum(np.abs(np.diff(commands, axis=0)), axis=0) if len(commands) > 1 else None
    dp = data["dp_hold"]
    dt = clock(data, "dp_hold")
    transitions = []
    last = None
    for time, value in zip(dt, dp[:, 0], strict=True):
        if value != last:
            transitions.append({"time_s": float(time), "active": bool(value)})
            last = value
    return {
        "duration_s": float(t[-1]),
        "allocation_observed_span_s": float(at[-1] - at[0]) if len(at) else None,
        "allocation_last_sample_minus_navigation_last_s": float(at[-1] - t[-1]) if len(at) else None,
        "navigation_samples": len(nav),
        "nominal_polyline_distance_m": statistics(distance),
        "active_segment_xte": (
            statistics(data["guidance"][:, 1]) if len(data.get("guidance", [])) else "unavailable in shared R0 topic capture"
        ),
        "end_position_m": nav[-1, :2].tolist(),
        "end_goal_distance_m": float(goal[-1]),
        "end_speed_mps": float(speed[-1]),
        "joint_position15m_speed0_3mps_observed_s": float(durations[joint].sum()),
        "joint_criterion_scope": "uniform observation criterion, not a replacement for original arrival semantics",
        "allocation_level2_fraction": fraction(allocation[:, 0] == 2),
        "allocation_level3_fraction": fraction(allocation[:, 0] == 3),
        "allocation_saturated_fraction": fraction(allocation[:, 2] == 1),
        "command_total_variation_force_n": changes[0::2].tolist() if changes is not None else None,
        "command_total_variation_angle_rad": changes[1::2].tolist() if changes is not None else None,
        "dp_hold_transitions": transitions,
    }


def compare(reference: Path, embedded: Path, output: Path, *, common_schedule: bool = False) -> dict:  # noqa: PLR0915
    """Interpolate at native sample times using only the declared startup clock origin."""
    rm, r, case = load(reference)
    em, e, ecase = load(embedded)
    if case != ecase:
        raise ValueError("Closed-loop case inputs differ")
    rt, et = clock(r, "navigation"), clock(e, "navigation")
    if np.any(np.diff(rt) <= 0) or np.any(np.diff(et) <= 0):
        raise ValueError("Nonmonotonic navigation clock")
    if common_schedule and (rm["kind"] != "original_source_coupled" or em["kind"] != "embedded"):
        raise ValueError("Common-schedule gate requires independently compiled source and embedded runs")
    common = (rt >= et[0]) & (rt <= et[-1])
    t = rt[common]
    rn = r["navigation"][common]
    en = np.empty_like(rn)
    for index in range(rn.shape[1]):
        values = e["navigation"][:, index]
        en[:, index] = np.interp(t, et, np.unwrap(values) if index in (2, 6) else values)
    delta = en - rn
    for index in (2, 6):
        delta[:, index] = np.arctan2(np.sin(delta[:, index]), np.cos(delta[:, index]))
    position = np.linalg.norm(delta[:, :2], axis=1)
    speed = np.hypot(en[:, 3], en[:, 4]) - np.hypot(rn[:, 3], rn[:, 4])
    route = np.array([[p["north_m"], p["east_m"]] for p in case["waypoints"]])
    xte = route_distance(en[:, :2], route) - route_distance(rn[:, :2], route)
    result = {
        "case_id": case["case_id"],
        "reference": rm,
        "embedded": em,
        "scope": "free closed-loop descriptive comparison; asynchronous ROS variation is not strict replay parity",
        "alignment": (
            "recorded plant last_time_ construction clock versus explicit embedded epoch; no fitted lag or spatial transform"
        ),
        "startup_uncertainty": (
            "clock origin is observed; ROS startup ordering and subsequent jitter remain part of the comparison"
        ),
        "interpolation": "linear on common native odometry times; angles unwrapped before interpolation",
        "reference_samples_outside_common_time": int((~common).sum()),
        "position_error_m": statistics(position),
        "speed_error_mps": statistics(speed),
        "heading_error_rad": statistics(delta[:, 2]),
        "nominal_polyline_distance_difference_m": statistics(xte),
        "reference_performance": performance(r, case),
        "embedded_performance": performance(e, case),
    }
    if common_schedule:
        gates = {
            "navigation_schedule_equal": np.array_equal(rt, et),
            "navigation_finite": bool(np.all(np.isfinite(r["navigation"])) and np.all(np.isfinite(e["navigation"]))),
            "position_within_0_10m": bool(result["position_error_m"]["maximum"] <= 0.10),
            "speed_within_0_01mps": bool(result["speed_error_mps"]["maximum"] <= 0.01),
            "heading_within_0_05deg": bool(result["heading_error_rad"]["maximum"] <= np.deg2rad(0.05)),
        }
        for name, column in [("dp_hold", 0), ("guidance", 0)]:
            available = len(r.get(name, [])) > 0 and len(e.get(name, [])) > 0
            gates[name + "_sequence_equal"] = bool(
                available
                and np.array_equal(clock(r, name), clock(e, name))
                and np.array_equal(r[name][:, column], e[name][:, column])
            )

        def mode_events(manifest: dict) -> list:
            keys = (
                "plan_id",
                "route_id",
                "active_route_id",
                "active_route_revision",
                "accepted",
                "rejected",
                "degraded",
                "execution_state",
                "current_navigation_mode",
                "current_segment_index",
                "current_target_waypoint_index",
            )
            return [
                (event["time_ns"], event["topic"], {key: event["message"].get(key) for key in keys})
                for event in manifest["route_events"]
            ]

        gates["route_mode_events_equal"] = bool(rm["route_events"] and em["route_events"]) and mode_events(
            rm
        ) == mode_events(em)
        result.update(
            scope="independent original-source and embedded autonomous closure under a common scheduler",
            startup_uncertainty="same explicit initialization epoch and scheduler",
            common_schedule_gates=gates,
            passed=all(gates.values()),
        )
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(json.dumps(result, indent=2))
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    ax = axes[0, 0]
    ax.plot(route[:, 1], route[:, 0], "k--", label="Nominal route")
    reference_label = "Original source / common schedule" if common_schedule else "Original ROS"
    ax.plot(r["navigation"][:, 1], r["navigation"][:, 0], label=reference_label)
    ax.plot(e["navigation"][:, 1], e["navigation"][:, 0], label="Embedded")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.legend()
    axes[0, 1].plot(t, position)
    axes[0, 1].set_ylabel("Position difference (m)")
    axes[1, 0].plot(t, np.degrees(delta[:, 2]))
    axes[1, 0].set_ylabel("Heading difference (deg)")
    axes[1, 1].plot(rt, np.hypot(r["navigation"][:, 3], r["navigation"][:, 4]), label=reference_label)
    axes[1, 1].plot(et, np.hypot(e["navigation"][:, 3], e["navigation"][:, 4]), label="Embedded")
    axes[1, 1].set_ylabel("Speed (m/s)")
    axes[1, 1].legend()
    for ax in (axes[0, 1], *axes[1, :]):
        ax.set_xlabel("Time since plant initialization (s)")
        ax.grid(alpha=0.3)
    fig.suptitle(case["case_id"] + (" — common-schedule closure" if common_schedule else " — free closed-loop observations"))
    fig.savefig(output / "comparison.png", dpi=160)
    plt.close(fig)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "embedded", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--common-schedule", action="store_true")
    args = parser.parse_args()
    compare(args.reference, args.embedded, args.output, common_schedule=args.common_schedule)
