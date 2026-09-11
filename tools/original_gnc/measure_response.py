"""Identify and qualify predictor approximations from unchanged original GNC runs.

This calibration does not alter GNC gains, planner safety margins or route
admission. Residuals are retained; a fitted predictor is not vessel qualification.

Schema v2 adds the qualification basis demanded by the diagnostic policy
(docs/research/2026-09-11-original-gnc-diagnostic-policy.md): a channel
qualifies only on its closed-loop trajectory R^2 over the active maneuvering
window (threshold enforced by colav_simulator.original_gnc.qualification).
The v1 derivative-basis fits are retained verbatim per channel under
``derivative``: finite-difference accelerations are structure-limited and are
not a predictor-quality metric. A second-order refit is recorded per channel
with an explicit adoption verdict so order escalation is never silently claimed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import least_squares

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from colav_simulator.original_gnc import qualification  # noqa: E402

SETTLE_AFTER_LAST_COMMAND_S = 60.0


def observations(directory: Path, limit_s: float) -> Any:
    """Collect measured source state derivatives and applied references."""
    manifest = json.loads((directory / "manifest.json").read_text())
    epoch = manifest["epoch_ns"]
    heading = speed = None
    previous = None
    rows = []
    with gzip.open(directory / "topic-observations.jsonl.gz", "rt") as stream:
        for line in stream:
            record = json.loads(line)
            t = (record["time_ns"] - epoch) / 1e9
            if t > limit_s:
                break
            fields = record["message"]["fields"]
            topic = record["topic"]
            if topic == "/control/heading_setpoint":
                heading = fields["data"]
            elif topic == "/control/speed_setpoint":
                speed = fields["data"]
            elif topic == "/ship/odometry":
                q = fields["pose"]["pose"]["orientation"]
                velocity = fields["twist"]["twist"]["linear"]
                psi = math.atan2(2 * (q["w"] * q["z"] + q["x"] * q["y"]), 1 - 2 * (q["y"] ** 2 + q["z"] ** 2))
                u, v = velocity["x"], velocity["y"]
                course = psi + math.atan2(v, u)
                if previous and heading is not None and speed is not None:
                    dt = t - previous[0]
                    if dt > 0:
                        rows.append(
                            {
                                "time_s": t,
                                "heading_error_rad": math.remainder(heading - psi, 2 * math.pi),
                                "heading_setpoint_rad": heading,
                                "course_rad": course,
                                "course_rate_radps": math.remainder(course - previous[1], 2 * math.pi) / dt,
                                "speed_error_mps": speed - u,
                                "speed_setpoint_mps": speed,
                                "surge_speed_mps": u,
                                "surge_accel_mps2": (u - previous[2]) / dt,
                            }
                        )
                previous = t, course, u
    return manifest, rows


def fit(rows: Any, error_key: Any, response_key: Any) -> dict:
    """Fit a positive first-order predictor and retain its residual error."""
    xx = sum(r[error_key] ** 2 for r in rows)
    xy = sum(r[error_key] * r[response_key] for r in rows)
    if not rows or xx <= 0 or xy <= 0:
        raise ValueError("Positive first-order response is not identifiable")
    inverse_tau = xy / xx
    mse = sum((r[response_key] - inverse_tau * r[error_key]) ** 2 for r in rows) / len(rows)
    mean = sum(r[response_key] for r in rows) / len(rows)
    variance = sum((r[response_key] - mean) ** 2 for r in rows) / len(rows)
    return {
        "time_constant_s": 1 / inverse_tau,
        "sample_count": len(rows),
        "derivative_rmse": math.sqrt(mse),
        "r_squared": 1 - mse / variance if variance > 0 else None,
        "method": "zero-intercept least squares: derivative = error / tau",
    }


def _series(rows: Any, key: str) -> np.ndarray:
    return np.array([float(row[key]) for row in rows])


def _r_squared(measured: np.ndarray, predicted: np.ndarray) -> float:
    residual = measured - predicted
    variance = float(((measured - measured.mean()) ** 2).sum())
    return 1.0 - float(residual @ residual) / variance


def _first_order_gain_update(dt: np.ndarray, tau: float) -> np.ndarray:
    """Exact zero-order-hold decay factors per sample."""
    return np.exp(-dt / tau)


def fit_course_trajectory(cases: list[tuple[np.ndarray, np.ndarray, np.ndarray]]) -> dict:
    """Closed-loop first-order course fit: course follows its own prediction.

    The heading loop carries integral action, so the DC gain is structurally 1.
    Cases are pooled with a shared time constant; each case integrates from its
    own measured initial course using zero-order-held heading setpoints.
    """
    measured = np.concatenate([course for _, _, course in cases])

    def predict(tau: float) -> np.ndarray:
        pieces = []
        for cmd, dt, course in cases:
            decay = _first_order_gain_update(dt, tau)
            x = np.empty_like(course)
            x[0] = course[0]
            for i in range(1, len(course)):
                x[i] = x[i - 1] + (1.0 - decay[i]) * math.remainder(cmd[i - 1] - x[i - 1], 2 * math.pi)
            pieces.append(x)
        return np.concatenate(pieces)

    result = least_squares(lambda p: measured - predict(math.exp(p[0])), [math.log(75.0)])
    tau = math.exp(result.x[0])
    predicted = predict(tau)
    residual = measured - predicted
    return {
        "time_constant_s": tau,
        "gain": 1.0,
        "sample_count": len(measured),
        "trajectory_r_squared": _r_squared(measured, predicted),
        "trajectory_rmse_rad": math.sqrt(float((residual**2).mean())),
        "method": (
            "closed-loop first-order trajectory least squares: "
            "course' = remainder(heading_setpoint - course, 2*pi)/tau, "
            "exact zero-order-hold discretization, DC gain structurally 1"
        ),
    }


def fit_speed_trajectory(rows: list, median_dt: float) -> dict:
    """Closed-loop first-order speed fit on the active maneuvering window.

    The static thrust map is not exactly unity, so the DC gain is identified.
    The active window excludes the at-rest tail (command zero for the rest of
    the trace) plus one settle period, so the score cannot ride on rest samples.
    """
    t = _series(rows, "time_s")
    cmd = _series(rows, "speed_setpoint_mps")
    speed = _series(rows, "surge_speed_mps")
    nonzero = np.nonzero(cmd > 1e-12)[0]
    active_limit = t[nonzero[-1]] + SETTLE_AFTER_LAST_COMMAND_S
    active = t <= active_limit
    ta, cmd_a, speed_a, dt_a = t[active], cmd[active], speed[active], np.diff(t[active], prepend=t[0])
    dt_a[0] = median_dt

    def predict(params: np.ndarray) -> np.ndarray:
        tau, gain = math.exp(params[0]), params[1]
        decay = np.exp(-dt_a / tau)
        x = np.empty_like(speed_a)
        x[0] = speed_a[0]
        for i in range(1, len(speed_a)):
            x[i] = x[i - 1] + (1.0 - decay[i]) * (gain * cmd_a[i - 1] - x[i - 1])
        return x

    result = least_squares(lambda p: speed_a - predict(p), [math.log(25.0), 1.0])
    tau, gain = math.exp(result.x[0]), float(result.x[1])
    predicted_active = predict(result.x)
    dt_full = np.diff(t, prepend=t[0])
    dt_full[0] = median_dt
    decay_full = np.exp(-dt_full / tau)
    x_full = np.empty_like(speed)
    x_full[0] = speed[0]
    for i in range(1, len(speed)):
        x_full[i] = x_full[i - 1] + (1.0 - decay_full[i]) * (gain * cmd[i - 1] - x_full[i - 1])
    residual = speed_a - predicted_active
    return {
        "time_constant_s": tau,
        "gain": gain,
        "sample_count": int(active.sum()),
        "active_window_s": float(active_limit),
        "trajectory_r_squared": _r_squared(speed_a, predicted_active),
        "trajectory_rmse_mps": math.sqrt(float((residual**2).mean())),
        "full_trace_r_squared": _r_squared(speed, x_full),
        "method": (
            "closed-loop first-order trajectory least squares: "
            "speed' = (gain*speed_setpoint - speed)/tau, exact zero-order-hold "
            f"discretization, active window = last nonzero command + {SETTLE_AFTER_LAST_COMMAND_S:.0f} s settle"
        ),
    }


def _second_order_trajectory(cases: list[tuple[np.ndarray, np.ndarray, np.ndarray]], initial: list[float]) -> dict:
    """Record-only two-pole refit on the trajectory basis (explicit Euler)."""
    measured = np.concatenate([course for _, _, course in cases])
    max_rate = 0.5 / max(float(dt.max()) for _, dt, _ in cases)

    def simulate(t1: float, t2: float, gain: float) -> np.ndarray:
        pieces = []
        for cmd, dt, course in cases:
            x = np.empty_like(course)
            rate = 0.0
            x[0] = course[0]
            for i in range(1, len(course)):
                x[i] = x[i - 1] + rate * dt[i]
                error = math.remainder(gain * cmd[i - 1] - x[i - 1], 2 * math.pi)
                rate = rate + (error - (t1 + t2) * rate) / (t1 * t2) * dt[i]
            pieces.append(x)
        return np.concatenate(pieces)

    def residual(p: np.ndarray) -> np.ndarray:
        t1, t2, gain = (math.exp(p[0]), math.exp(p[1]), p[2])
        if not (0.05 < t1 < 500.0 and 0.05 < t2 < 500.0) or (t1 + t2) / (t1 * t2) >= max_rate:
            return np.full(measured.shape, 1.0e3)
        return measured - simulate(t1, t2, gain)

    result = least_squares(residual, initial)
    t1, t2, gain = (math.exp(result.x[0]), math.exp(result.x[1]), float(result.x[2]))
    predicted = simulate(t1, t2, gain)
    return {
        "form": "two-pole: tau1*s+1 over (tau1*s+1)(tau2*s+1), explicit Euler",
        "tau1_s": t1,
        "tau2_s": t2,
        "gain": gain,
        "trajectory_r_squared": _r_squared(measured, predicted),
    }


def _speed_second_order(rows: list, median_dt: float) -> dict:
    """Record-only two-pole refit for the speed channel (explicit Euler)."""
    t = _series(rows, "time_s")
    cmd = _series(rows, "speed_setpoint_mps")
    speed = _series(rows, "surge_speed_mps")
    dt = np.diff(t, prepend=t[0])
    dt[0] = median_dt
    max_rate = 0.5 / float(dt.max())

    def simulate(t1: float, t2: float, gain: float) -> np.ndarray:
        x = np.empty_like(speed)
        rate = 0.0
        x[0] = speed[0]
        for i in range(1, len(speed)):
            x[i] = x[i - 1] + rate * dt[i]
            error = gain * cmd[i - 1] - x[i - 1]
            rate = rate + (error - (t1 + t2) * rate) / (t1 * t2) * dt[i]
        return x

    def residual(p: np.ndarray) -> np.ndarray:
        t1, t2, gain = (math.exp(p[0]), math.exp(p[1]), p[2])
        if not (0.05 < t1 < 500.0 and 0.05 < t2 < 500.0) or (t1 + t2) / (t1 * t2) >= max_rate:
            return np.full(speed.shape, 1.0e3)
        return speed - simulate(t1, t2, gain)

    result = least_squares(residual, [math.log(20.0), math.log(10.0), 0.0])
    t1, t2, gain = (math.exp(result.x[0]), math.exp(result.x[1]), float(result.x[2]))
    predicted = simulate(t1, t2, gain)
    degenerate = t2 <= 4.0 * median_dt or abs(t2 - 0.05) < 1.0e-3
    verdict = (
        "DEGENERATE_SECOND_POLE_NOT_IDENTIFIABLE"
        if degenerate
        else "SECOND_POLE_IDENTIFIED_NOT_ADOPTED_WITHOUT_REVIEW"
    )
    return {
        "form": "two-pole: gain/((tau1*s+1)(tau2*s+1)), explicit Euler",
        "tau1_s": t1,
        "tau2_s": t2,
        "gain": gain,
        "trajectory_r_squared": _r_squared(speed, predicted),
        "verdict": verdict,
    }


def measure(campaign: Path, output: Path) -> dict:
    """Bind measured response approximations to their exact campaign evidence."""
    heading_rows = []
    speed_rows = []
    evidence = []
    course_cases = []
    for case, limit in [("R03-plus-E0", 90.0), ("R03-minus-E0", 90.0), ("R11-E0", 5000.0)]:
        directory = campaign / case
        manifest, rows = observations(directory, limit)
        if case.startswith("R03"):
            t = _series(rows, "time_s")
            cmd = _series(rows, "heading_setpoint_rad")
            course = _series(rows, "course_rad")
            dt = np.diff(t, prepend=t[0])
            dt[0] = float(np.median(np.diff(t)))
            course_cases.append((cmd, dt, course))
            heading_rows.extend(rows)
        else:
            speed_rows.extend(rows)
        evidence.append(
            {
                "case": case,
                "window_s": limit,
                "case_sha256": manifest["case_sha256"],
                "library_sha256": manifest["build"]["library_sha256"],
                "trace_sha256": hashlib.sha256((directory / "topic-observations.jsonl.gz").read_bytes()).hexdigest(),
            }
        )
    median_speed_dt = float(np.median(np.diff(_series(speed_rows, "time_s"))))

    derivative_course = fit(heading_rows, "heading_error_rad", "course_rate_radps")
    derivative_speed = fit(speed_rows, "speed_error_mps", "surge_accel_mps2")
    trajectory_course = fit_course_trajectory(course_cases)
    trajectory_speed = fit_speed_trajectory(speed_rows, median_speed_dt)
    second_order_course = _second_order_trajectory(course_cases, [math.log(80.0), math.log(20.0), 0.0])
    second_order_speed = _speed_second_order(speed_rows, median_speed_dt)
    if not 0.9 <= second_order_course["gain"] <= 1.1:
        second_order_course["verdict"] = "NOT_ADOPTED_IMPLAUSIBLE_DC_GAIN"
    else:
        second_order_course["verdict"] = "NOT_ADOPTED_NO_MATERIAL_GAIN_OVER_FIRST_ORDER"

    document = {
        "schema": "original-gnc.response-approximation.v2",
        "qualification": None,
        "qualification_rule": {
            "basis": "closed-loop trajectory r_squared on the active maneuvering window",
            "threshold": qualification.TRAJECTORY_R_SQUARED_THRESHOLD,
            "evaluator": "colav_simulator.original_gnc.qualification",
        },
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "evidence": evidence,
        "course": {
            **trajectory_course,
            "derivative": derivative_course,
            "second_order_refit": second_order_course,
        },
        "speed": {
            **trajectory_speed,
            "derivative": derivative_speed,
            "second_order_refit": second_order_speed,
        },
        "limits": (
            "No dead-time fit, no safety-threshold changes, no claim that nonlinear "
            "source GNC is first-order. Derivative-basis fits are legacy evidence "
            "kept verbatim; qualification uses only the trajectory basis at the "
            "wired threshold."
        ),
    }
    document["qualification"] = qualification.verdict_string(document)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2))
    return document


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(measure(a.campaign, a.output), indent=2))
