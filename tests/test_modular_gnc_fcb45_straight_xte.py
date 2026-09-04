"""Calm-water straight-transit XTE facade test for the FCB45 presets (s9c R2).

The s9c spec's Testing Decisions promise a calm-straight cross-track-error
anchor at the ModularShipStack facade seam, complementing the maneuvering
anchors: a >= 3000 m straight route at the 7.8 m/s service speed in calm water
must complete with the track staying essentially on the intended line.

Gate:全程 max|XTE| <= 10 m (one fifth of the 50 m acceptance gate).  Measured
with the shipped preset (seed 11, dt 0.1): max|XTE| stays in the sub-metre
range on both plant tiers, so the gate carries real margin without being
vacuous (motion-sanity guards below keep completion honest).

Pattern follows tests/test_modular_gnc_fcb45_maneuvering_anchors.py:
settle on the straight course, then run the transit leg.
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
ROUTE_LENGTH_M = 3000.0
MAX_TRANSIT_S = 600.0  # 3000 m at 7.8 m/s takes ~385 s; bound covers spool-up
DT_S = 0.1
MAX_XTE_M = 10.0
MIN_SURGE_MPS = 5.0


def _stack(stack_id: str) -> ModularShipStack:
    for entry in list_stack_catalog()["stacks"]:
        if entry["stack_id"] == stack_id:
            return ModularShipStack.from_config(normalize_ship_modules(entry["config"]), dt_s=DT_S)
    raise AssertionError(f"stack {stack_id!r} not listed")


def _run_straight_transit(stack: ModularShipStack) -> dict[str, float]:
    """Settle, then hold the straight course for a full ROUTE_LENGTH_M leg."""
    stack.reset(NavigationState(0.0, 0.0, 0.0, SERVICE_SPEED_MPS, 0.0, 0.0), seed=11)
    values = np.zeros(9)
    values[3] = SERVICE_SPEED_MPS

    total_ticks = int((SETTLE_S + MAX_TRANSIT_S) / DT_S)
    settle_ticks = int(SETTLE_S / DT_S)
    max_xte = 0.0
    min_surge = SERVICE_SPEED_MPS
    for tick in range(total_ticks):
        out = stack.step(CommandInput.direct(tick, DirectReference(values, tick)), dt_s=DT_S)
        assert out.failure is None, f"facade failure at tick {tick}: {out.failure}"
        nav = out.navigation
        # Intended track: the north axis through the reset origin (heading 0).
        max_xte = max(max_xte, abs(nav.east_m))
        min_surge = min(min_surge, nav.surge_mps)
        if tick == settle_ticks - 1:
            assert abs(nav.heading_rad) < math.radians(1.0), "settle phase must end on the straight course"
            north_start_m = nav.north_m  # the 3000 m leg starts here, not in settle
        elif tick >= settle_ticks and nav.north_m - north_start_m >= ROUTE_LENGTH_M:
            return {
                "max_xte_m": max_xte,
                "min_surge_mps": min_surge,
                "transit_s": (tick + 1 - settle_ticks) * DT_S,
            }
    raise AssertionError(
        f"straight route did not cover {ROUTE_LENGTH_M} m within {MAX_TRANSIT_S} s "
        f"(reached {out.navigation.north_m - north_start_m:.1f} m)"
    )


@pytest.mark.parametrize(
    "stack_id",
    [
        "fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid",
        "fcb45_roll_4dof_plant+pass_through_guidance+fcb45_marine_pid",
    ],
)
class TestCalmStraightTransitXte:
    def test_straight_route_completes_within_xte_gate(self, stack_id: str) -> None:
        result = _run_straight_transit(_stack(stack_id))
        assert result["max_xte_m"] <= MAX_XTE_M

    def test_straight_route_motion_stays_on_service_speed(self, stack_id: str) -> None:
        """Guard against a vacuous XTE pass (crawling or stalled transit)."""
        result = _run_straight_transit(_stack(stack_id))
        assert result["transit_s"] <= MAX_TRANSIT_S
        assert result["min_surge_mps"] >= MIN_SURGE_MPS
