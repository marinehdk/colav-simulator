"""Phase-accumulated dt semantics for scheduled controller phases (Issue #67 slice 1).

The scheduler runs the controller phase every ``controller_period_ticks`` ticks but
used to hand the single-tick dt to ``MarinePID.compute_control``, so integral and
derivative states advanced at dt while being scheduled at period x dt (dt x 5
mismatch under the legacy_equivalent preset).  The controller phase must now
receive the phase-accumulated dt (period x tick dt).

Behaviour is asserted through the public ``ModularShipStack.step`` seam with a
frozen plant (zero output limits, zero anti-windup gain), which keeps the PID
errors exactly constant so the integral term is independently hand-computable:
after N controller invocations the latched trace integral equals
(N - 1) * ki * e * (period * tick_dt).
"""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import CommandInput, DirectReference, NavigationState
from colav_simulator.modular_gnc.stack import ModularShipStack


def _frozen_stack(controller_period: int) -> ModularShipStack:
    """Assemble a marine_pid stack whose plant state stays exactly frozen.

    Zero min/max output clips every channel to 0 N/N.m (ideal pass-through
    reports the saturated 0), and zero anti-windup gain removes the
    back-calculation path, so the integral increment is exactly dt * ki * e.
    """
    cfg = normalize_ship_modules(
        {
            "preset": "legacy_equivalent",
            "overrides": {"scheduler": {"plant_period_ticks": 1, "controller_period_ticks": controller_period}},
            "modules": {
                "plant": {"identity": "generic_3dof_plant", "parameters": {"mass_kg": 1.6e7, "i_z_kgm2": 3.0e10}},
                "guidance": {"identity": "pass_through_guidance", "parameters": {}},
                "controller": {
                    "identity": "marine_pid",
                    "parameters": {
                        "kp": (0.0, 0.0, 0.0),
                        "ki": (10.0, 10.0, 10.0),
                        "kd": (0.0, 0.0, 0.0),
                        "antiwindup_gain": (0.0, 0.0, 0.0),
                        "min_output": (0.0, 0.0, 0.0),
                        "max_output": (0.0, 0.0, 0.0),
                        "feedforward_gain": (0.0, 0.0, 0.0),
                        "allow_ideal_passthrough": True,
                    },
                },
            },
        }
    )
    return ModularShipStack.from_config(cfg, dt_s=0.2)


def _reference(tick: int) -> DirectReference:
    values = np.zeros(9)
    values[2] = 0.3  # psi_d
    values[3] = 2.0  # u_d
    values[4] = 0.5  # v_d
    return DirectReference(values, tick)


def test_controller_phase_receives_phase_accumulated_dt() -> None:
    """Every due controller invocation carries dt = controller_period x tick dt."""
    stack = _frozen_stack(controller_period=5)
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=1)

    seen_dts: list[float] = []
    for tick in range(25):
        out = stack.step(CommandInput.direct(tick, _reference(tick)), dt_s=0.2)
        assert out.failure is None
        if tick % 5 == 0:
            assert out.controller_trace is not None
            seen_dts.append(out.controller_trace.dt_s)
    assert seen_dts == [1.0] * 5  # 5 ticks x 0.2 s


def test_pid_integral_advances_by_controller_period_not_tick_dt() -> None:
    """Constant errors integrate at ki*e per controller period (independent hand value).

    Hand calculation: period = 5 ticks x 0.2 s = 1.0 s of elapsed control time per
    invocation; errors stay exactly (2.0, 0.5, 0.3) because the plant is frozen.
    The latched trace's i_term is the integral before the current update, so the
    invocation-N trace shows (N - 1) * ki * e * 1.0 s.  After 4 invocations the
    expected integral is 3 * 10 * (2.0, 0.5, 0.3) = (60.0, 15.0, 9.0).
    """
    stack = _frozen_stack(controller_period=5)
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=1)

    last_trace = None
    for tick in range(20):  # 4 controller invocations (ticks 0, 5, 10, 15)
        out = stack.step(CommandInput.direct(tick, _reference(tick)), dt_s=0.2)
        assert out.failure is None
        if out.controller_trace is not None:
            last_trace = out.controller_trace

    assert last_trace is not None
    # wrap_to_pi on the heading channel leaves a ~1e-15 relative artifact; the
    # hand value must hold to float rounding, not bit-exactly.
    assert last_trace.i_term[0] == 60.0
    assert last_trace.i_term[1] == 15.0
    assert last_trace.i_term[2] == pytest.approx(9.0, abs=1e-9)


def test_period_one_controller_keeps_tick_dt_bit_exactly() -> None:
    """controller_period_ticks == 1 keeps receiving the tick dt exactly (legacy parity)."""
    stack = _frozen_stack(controller_period=1)
    stack.reset(NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), seed=1)

    for tick in range(6):
        out = stack.step(CommandInput.direct(tick, _reference(tick)), dt_s=0.2)
        assert out.failure is None
        assert out.controller_trace is not None
        assert out.controller_trace.dt_s == 0.2

    # 6 invocations, trace shows 5 accumulated updates of 0.2 s each.
    assert out.controller_trace.i_term[0] == 20.0
    assert out.controller_trace.i_term[1] == 5.0
    assert out.controller_trace.i_term[2] == pytest.approx(3.0, abs=1e-9)
