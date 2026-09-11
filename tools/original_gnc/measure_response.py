"""Identify first-order predictor approximations from unchanged original GNC runs.

This calibration does not alter GNC gains, planner safety margins or route
admission. Residuals are retained; a fitted predictor is not vessel qualification.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any


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
                                "course_rate_radps": math.remainder(course - previous[1], 2 * math.pi) / dt,
                                "speed_error_mps": speed - u,
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


def measure(campaign: Path, output: Path) -> dict:
    """Bind measured response approximations to their exact campaign evidence."""
    heading_rows = []
    speed_rows = []
    evidence = []
    for case, limit in [("R03-plus-E0", 90.0), ("R03-minus-E0", 90.0), ("R11-E0", 5000.0)]:
        directory = campaign / case
        manifest, rows = observations(directory, limit)
        if case.startswith("R03"):
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
    result = {
        "schema": "original-gnc.response-approximation.v1",
        "qualification": "UNQUALIFIED_FIRST_ORDER_APPROXIMATION",
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "evidence": evidence,
        "course": fit(heading_rows, "heading_error_rad", "course_rate_radps"),
        "speed": fit(speed_rows, "speed_error_mps", "surge_accel_mps2"),
        "limits": "No dead-time fit, no safety-threshold changes, no claim that nonlinear source GNC is first-order.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(measure(a.campaign, a.output), indent=2))
