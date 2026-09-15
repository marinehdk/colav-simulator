"""Decimal simulation steps must not create gaps in a live native intent lease."""

from types import SimpleNamespace

import numpy as np
import pytest

from colav_simulator.core.colav.kuwata_vo_alg.kuwata_vo import VO
from colav_simulator.original_gnc.native import OriginalGncError
from colav_simulator.original_gnc.plan_bridge import OriginalPlanBridge


@pytest.mark.parametrize("origin", [0.0, 1024.0])
def test_decimal_steps_keep_vo_on_its_declared_one_second_cadence(origin):
    vo = VO()
    t = origin
    executed = []
    for tick in range(121):
        vo.plan(t, np.array([4.0, 0.0]), np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]), [])
        if vo.plan_executed:
            executed.append(tick)
        t += 0.1
    assert executed == list(range(0, 121, 10))


def test_native_lease_uses_native_issue_time_and_held_ticks_do_not_renew():
    epoch = 2_000_000_000_000_000_000
    ship = SimpleNamespace(
        stack=SimpleNamespace(time_ns=epoch + 1_050_000_000_000, epoch_ns=epoch),
        _nominal_id="mission",
        _nominal_revision=1,
        _planner_time_origin=0.0,
        _legacy=SimpleNamespace(),
    )
    bridge = OriginalPlanBridge(ship, 0.1)
    published = []

    def deliver(request, identity, *, kind):
        published.append(request)
        bridge.last_outcome = {"rejected": False}

    bridge._deliver = deliver
    planner = {"algorithm_id": "vo", "solve_id": 1051, "solver_executed": True}
    details = {
        "solve_period_s": 1.0,
        "hard_constraint_count": 0,
        "active_rules": {},
        "give_way_commitment_active": False,
        "stand_on_hold_active": False,
        "static_hazard_count": 0,
    }
    bridge._submit_velocity(1049.9999999, planner, details, 1.0, 4.0)
    assert published[0]["valid_until"] == {"sec": 2000001051, "nanosec": 0}
    planner["solver_executed"] = False
    ship.stack.time_ns += 900_000_000
    bridge._submit_velocity(1050.8999999, planner, details, 1.0, 4.0)
    assert len(published) == 1
    ship.stack.time_ns += 100_000_000
    with pytest.raises(OriginalGncError, match="Expired"):
        bridge._submit_velocity(1050.9999999, planner, details, 1.0, 4.0)
