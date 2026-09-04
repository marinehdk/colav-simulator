"""IMO MSC.137(76) zigzag anchor tests for the FCB45 preset (Issue #67 slice 7).

Emulation at the ModularShipStack facade seam: the classic zigzag reverses the
rudder when the heading deviation reaches the rudder angle; this stack's
command interface is a heading reference, so the equivalent emulation steps the
DirectReference heading to the opposite deviation at each trigger crossing and
measures the heading overshoot beyond the trigger level.

Gates (IMO MSC.137(76) indicative overshoot values, as mandated for Issue #67):
- 10/10: first overshoot <= 10 deg, second overshoot <= 25 deg
- 20/20: first overshoot <= 25 deg

Motion-sanity guards keep the gates honest: every leg must complete in bounded
time, the yaw rate must stay near the configured rate limit (no ROT starvation
— the Issue #67 symptom), and surge must be maintained.

Measured with the shipped preset (seed 11, dt 0.1, service speed 7.8 m/s):
tier1 == tier2: 10/10 -> 0.12/0.09 deg; 20/20 -> 0.14/0.31 deg; legs ~19 s.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import CommandInput, DirectReference, NavigationState
from colav_simulator.modular_gnc.stack import ModularShipStack

SERVICE_SPEED_MPS = 7.8
SETTLE_S = 100.0
RATE_LIMIT_RAD_S = 0.05
MAX_LEG_S = 60.0  # 20 deg at the 2.9 deg/s rate limit takes ~7 s plus ramps


def _stack(stack_id: str) -> ModularShipStack:
    for entry in list_stack_catalog()["stacks"]:
        if entry["stack_id"] == stack_id:
            return ModularShipStack.from_config(normalize_ship_modules(entry["config"]), dt_s=0.1)
    raise AssertionError(f"stack {stack_id!r} not listed")


def _run_zigzag(stack: ModularShipStack, delta_deg: float) -> dict[str, float]:
    """Run one settled zigzag; return first two overshoots and motion indicators."""
    delta = math.radians(delta_deg)
    stack.reset(NavigationState(0.0, 0.0, 0.0, SERVICE_SPEED_MPS, 0.0, 0.0), seed=11)
    values = np.zeros(9)
    values[3] = SERVICE_SPEED_MPS

    settle_ticks = int(SETTLE_S / 0.1)
    for tick in range(settle_ticks):
        out = stack.step(CommandInput.direct(tick, DirectReference(values, tick)), dt_s=0.1)
    assert out.failure is None
    assert abs(out.navigation.heading_rad) < math.radians(1.0), "settle phase must end on the straight course"

    target = +delta
    reversal_ticks: list[int] = []
    overshoots: list[float] = []
    directions: list[int] = []
    armed_up, armed_down = True, False
    last_heading = out.navigation.heading_rad
    max_yaw_rate = 0.0
    min_surge = SERVICE_SPEED_MPS

    for tick in range(settle_ticks, settle_ticks + 12000):
        values[2] = target
        out = stack.step(CommandInput.direct(tick, DirectReference(values, tick)), dt_s=0.1)
        assert out.failure is None, f"facade failure at tick {tick}: {out.failure}"
        heading = out.navigation.heading_rad
        max_yaw_rate = max(max_yaw_rate, abs(out.navigation.yaw_rate_radps))
        min_surge = min(min_surge, out.navigation.surge_mps)

        if armed_up and heading >= delta and last_heading < delta:
            reversal_ticks.append(tick)
            overshoots.append(0.0)
            directions.append(+1)
            target = -delta
            armed_up, armed_down = False, True
        elif armed_down and heading <= -delta and last_heading > -delta:
            reversal_ticks.append(tick)
            overshoots.append(0.0)
            directions.append(-1)
            target = +delta
            armed_up, armed_down = True, False
        elif overshoots:
            k = len(overshoots) - 1
            overshoots[k] = max(overshoots[k], (heading - delta) if directions[k] > 0 else (-delta - heading))
        last_heading = heading
        if len(overshoots) >= 3:
            break

    assert len(overshoots) >= 2, "zigzag must complete at least two reversals"
    leg_times = [
        (reversal_ticks[i + 1] - reversal_ticks[i]) * 0.1
        for i in range(min(len(reversal_ticks) - 1, 2))
    ]
    return {
        "first_overshoot_deg": math.degrees(overshoots[0]),
        "second_overshoot_deg": math.degrees(overshoots[1]),
        "max_leg_s": max(leg_times),
        "max_yaw_rate_radps": max_yaw_rate,
        "min_surge_mps": min_surge,
    }


@pytest.mark.parametrize(
    "stack_id",
    [
        "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
        "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
    ],
)
class TestImoZigzagAnchors:
    def test_zigzag_10_10_first_and_second_overshoot(self, stack_id: str) -> None:
        result = _run_zigzag(_stack(stack_id), 10.0)
        assert result["first_overshoot_deg"] <= 10.0
        assert result["second_overshoot_deg"] <= 25.0

    def test_zigzag_20_20_first_overshoot(self, stack_id: str) -> None:
        result = _run_zigzag(_stack(stack_id), 20.0)
        assert result["first_overshoot_deg"] <= 25.0
        assert result["second_overshoot_deg"] <= 25.0

    def test_zigzag_motion_stays_lively_and_on_speed(self, stack_id: str) -> None:
        """Guards against vacuous gate passes (ROT starvation / crawling legs)."""
        for delta_deg in (10.0, 20.0):
            result = _run_zigzag(_stack(stack_id), delta_deg)
            assert result["max_leg_s"] <= MAX_LEG_S
            assert result["max_yaw_rate_radps"] >= 0.8 * RATE_LIMIT_RAD_S
            assert result["max_yaw_rate_radps"] <= 1.5 * RATE_LIMIT_RAD_S
            assert result["min_surge_mps"] >= 5.0
