from __future__ import annotations

import numpy as np
from conftest import P1RunHarness


def test_multiship_vo_keeps_fifty_metre_continuous_hull_clearance(
    p1_run_harness: P1RunHarness,
) -> None:
    result = p1_run_harness.run("paper_ccta2023_multiship", "vo")
    own_radius = 0.5 * np.hypot(
        result.session.ship_info["Ship0"]["length"],
        result.session.ship_info["Ship0"]["width"],
    )
    clearances = {}
    for target_key, target_info in result.session.ship_info.items():
        if target_key == "Ship0":
            continue
        center_distances = []
        for first, second in zip(
            result.session.frames,
            result.session.frames[1:],
            strict=False,
        ):
            if not first[target_key].get("active", True):
                continue
            relative_start = (
                np.asarray(first[target_key]["state"][:2])
                - np.asarray(first["Ship0"]["state"][:2])
            )
            relative_end = (
                np.asarray(second[target_key]["state"][:2])
                - np.asarray(second["Ship0"]["state"][:2])
            )
            relative_delta = relative_end - relative_start
            denominator = float(relative_delta @ relative_delta)
            fraction = (
                np.clip(-float(relative_start @ relative_delta) / denominator, 0.0, 1.0)
                if denominator > 0.0
                else 0.0
            )
            center_distances.append(
                float(np.linalg.norm(relative_start + fraction * relative_delta))
            )
        target_radius = 0.5 * np.hypot(
            target_info["length"], target_info["width"]
        )
        clearances[target_key] = min(center_distances) - own_radius - target_radius

    assert set(clearances) == {"Ship1", "Ship2", "Ship3"}
    assert min(clearances.values()) >= 50.0, clearances
    solve_details = [
        frame["Ship0"]["colav"]["planner"]["algorithm_details"]
        for frame in result.session.frames
        if frame["Ship0"]["colav"]["planner"].get("solver_executed")
    ]
    assert solve_details
    assert all(item["dynamics_prediction_active"] for item in solve_details)
