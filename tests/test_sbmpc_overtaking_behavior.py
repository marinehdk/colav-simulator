from __future__ import annotations

import math

from conftest import P1RunHarness


def test_overtaking_keeps_substantial_starboard_action_until_past(
    p1_run_harness: P1RunHarness,
) -> None:
    result = p1_run_harness.run("overtaking", "sbmpc")

    samples: list[tuple[float, float, float, float, float]] = []
    for frame in result.session.frames:
        ownship = frame.get("Ship0")
        target = frame.get("Ship1")
        if not ownship or not target:
            continue
        planner = ownship["colav"]["planner"]
        if not planner["solver_executed"]:
            continue
        course_offset_deg = math.degrees(
            planner["selected_command"]["course_offset_rad"]
        )
        delta_north = ownship["csog_state"][0] - target["csog_state"][0]
        delta_east = ownship["csog_state"][1] - target["csog_state"][1]
        target_course = target["csog_state"][3]
        along_track_m = delta_north * math.cos(target_course) + delta_east * math.sin(
            target_course
        )
        distance_m = math.hypot(delta_north, delta_east)
        command_course = planner["selected_command"]["course_rad"]
        course_delta_deg = math.degrees(
            math.atan2(
                math.sin(command_course - target_course),
                math.cos(command_course - target_course),
            )
        )
        samples.append(
            (
                float(ownship["timestamp"]),
                course_offset_deg,
                along_track_m,
                distance_m,
                course_delta_deg,
            )
        )

    first_action = next(
        index for index, sample in enumerate(samples) if sample[4] >= 14.0
    )
    clear_index = next(
        index
        for index, sample in enumerate(samples[first_action:], first_action)
        if sample[2] >= 190.0 and sample[3] >= 190.0
    )
    premature_weakening = [
        sample
        for sample in samples[first_action:clear_index]
        if sample[1] < 14.0 or sample[4] < 14.0
    ]
    command_jumps = [
        (previous, current)
        for previous, current in zip(
            samples[first_action:], samples[first_action + 1 :], strict=False
        )
        if abs(current[4] - previous[4]) > 15.1
    ]
    post_clear_reapproach = [
        sample for sample in samples[clear_index:] if sample[3] < 190.0
    ]

    assert not premature_weakening, (
        "SB-MPC weakened its starboard action before finally past and clear: "
        f"{premature_weakening}"
    )
    assert not command_jumps, f"SB-MPC course command still chatters: {command_jumps}"
    assert not post_clear_reapproach, (
        "SB-MPC route recovery re-entered the 190 m clearance domain: "
        f"{post_clear_reapproach}"
    )
