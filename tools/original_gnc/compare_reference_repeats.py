"""Measure observed native ROS repeat spread without trajectory or timing fitting."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
from compare_navigation import clock, load, statistics


def compare(root: Path, output: Path) -> dict:
    """Report each available native pair; fewer than three runs stays incomplete."""
    groups = ("reference-campaign", "reference-repeat02", "reference-repeat03", "reference-repeat04")
    cases = ("R02-plus-E0", "R05-E0", "R06-E0", "R07-E0", "R12-E0", "R06-E4")
    result = {}
    for case_id in cases:
        runs = []
        for group in groups:
            path = root / group / case_id
            if (path / "manifest.json").exists():
                runs.append((group, *load(path)))
        pairs = []
        for left, right in itertools.combinations(runs, 2):
            lname, lmanifest, left_data, lcase = left
            rname, rmanifest, r, rcase = right
            if lcase != rcase:
                raise ValueError("Repeat inputs differ")
            lt, rt = clock(left_data, "navigation"), clock(r, "navigation")
            mask = (lt >= rt[0]) & (lt <= rt[-1])
            time = lt[mask]
            a = left_data["navigation"][mask]
            b = np.empty_like(a)
            for column in range(a.shape[1]):
                values = r["navigation"][:, column]
                b[:, column] = np.interp(time, rt, np.unwrap(values) if column in (2, 6) else values)
            heading = np.arctan2(np.sin(b[:, 2] - a[:, 2]), np.cos(b[:, 2] - a[:, 2]))
            pairs.append(
                {
                    "left": lname,
                    "right": rname,
                    "left_trace_sha256": lmanifest["topic_trace_uncompressed_sha256"],
                    "right_trace_sha256": rmanifest["topic_trace_uncompressed_sha256"],
                    "position_difference_m": statistics(np.linalg.norm(b[:, :2] - a[:, :2], axis=1)),
                    "speed_difference_mps": statistics(np.hypot(b[:, 3], b[:, 4]) - np.hypot(a[:, 3], a[:, 4])),
                    "heading_difference_rad": statistics(heading),
                }
            )
        result[case_id] = {"available_runs": len(runs), "three_run_coverage": len(runs) >= 3, "pairs": pairs}
    report = {
        "scope": "observed asynchronous ROS repeat spread; not a statistical confidence interval",
        "alignment": "original plant last_time_ construction clocks; no optimized lag",
        "cases": result,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compare(args.root, args.output)
