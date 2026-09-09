"""Back-calculation must compare physical feedback to the command it executed."""

import numpy as np
import pytest

from colav_simulator.modular_gnc.contracts import (
    AchievedGeneralizedLoad,
    AchievedLoadStatus,
    DirectReference,
    NavigationState,
    VesselLoad,
)
from colav_simulator.modular_gnc.controller import MarinePID, MarinePIDConfig


@pytest.mark.parametrize("delivered,expected_correction", [(100.0, 0.0), (80.0, -20.0)])
def test_previous_tick_feedback_does_not_treat_new_reference_as_saturation(delivered, expected_correction):
    controller = MarinePID(
        MarinePIDConfig(align_previous_actuator_feedback=True, kp=(100.0, 0.0, 0.0), ki=(0.0, 0.0, 0.0), kd=(0.0, 0.0, 0.0))
    )
    state = NavigationState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    values = np.zeros(9)
    values[3] = 1.0
    controller.compute_control(state, DirectReference(values, 0), 0.1, tick=0)
    feedback = AchievedGeneralizedLoad.from_vessel_load(
        VesselLoad(surge_n=delivered),
        status=AchievedLoadStatus.AVAILABLE,
        source="RESOLVED_ACTUATOR_DYNAMICS",
        tick=0,
        time_s=0.0,
    )
    values[3] = 2.0
    _, trace = controller.compute_control(state, DirectReference(values, 1), 0.1, tick=1, achieved_load=feedback)
    assert trace.raw_request[0] == 200.0
    assert trace.antiwindup_correction[0] == expected_correction
