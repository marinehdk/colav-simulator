"""Freeze plant matrix, RHS and RK4 probes before observing their numerical results."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

from colav_simulator.original_gnc.configuration import OriginalGncConfig


def make(output: Path) -> dict:
    """Use SI inputs and distinguish baseline 20 ms from numerical-sensitivity 10 ms."""
    if output.exists():
        raise FileExistsError(output)
    config = OriginalGncConfig.from_dict({})
    roots, assets, _ = config.source_assets()
    speeds = (
        [-2.0, 0.0, 0.3] + [threshold + epsilon for threshold in (1.5, 2.7, 3.2) for epsilon in (-1e-6, 0.0, 1e-6)] + [7.8]
    )
    cases = []
    for index, (depth, speed, roll, sign, tau, dt) in enumerate(
        itertools.product(
            (2.2, 4.4, 50.0),
            speeds,
            (-math.radians(10.0), 0.0, math.radians(10.0)),
            (-1.0, 1.0),
            ((0.0, 0.0, 0.0, 0.0), (100000.0, 20000.0, 1000.0, 500000.0)),
            (0.02, 0.01),
        )
    ):
        cases.append(
            {
                "case_id": index,
                "water_depth_m": depth,
                "nu": [speed, sign * 0.4, sign * 0.03, sign * 0.02],
                "roll_rad": roll,
                "tau": list(tau),
                "dt_s": dt,
            }
        )
    data = {
        "source_manifest_sha256": "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411",
        "parameters": config.parameters()["ship_dynamics_node"],
        "options": {"time_ns": 2_000_000_000_000_000_000, "package_roots": roots, "asset_paths": assets},
        "cases": cases,
        "comparison_rules": {
            "M": {"absolute_by_angular_indices": [1e-6, 1e-5, 1e-4], "relative": 1e-10, "units": ["kg", "kg.m", "kg.m^2"]},
            "M_inverse": {"absolute": 1e-15, "relative": 1e-10},
            "C": {
                "absolute_by_angular_indices": [1e-3, 1e-3, 1e-2],
                "relative": 1e-10,
                "units": ["kg/s", "kg.m/s", "kg.m^2/s"],
            },
            "forces": {"absolute": [1e-3, 1e-3, 1e-2, 1e-2], "relative": 1e-8},
            "acceleration": {"absolute": [1e-8, 1e-8, 1e-9, 1e-9], "relative": 1e-9},
            "velocity": {"absolute": [1e-8, 1e-8, 1e-9, 1e-9], "relative": 1e-9},
            "decomposition_residual": {"absolute": 1e-10, "relative": 0.0},
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2))
    output.with_suffix(".sha256").write_text(hashlib.sha256(output.read_bytes()).hexdigest() + "\n")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(len(make(args.output)["cases"]))
