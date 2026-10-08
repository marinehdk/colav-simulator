"""Radar evidence fan-out must not perturb legacy seeded measurements."""

import hashlib

import numpy as np
import pytest

from colav_simulator.core.sensing import RadarXBand, RadarXParams

GOLDEN = {
    0.0: "97dbea10e1c82a5507e4cdc58555863e9c0304d8bb0a517dce56521ea21b89b9",
    3.0: "37351c03ba2200fec59410e418deee455b0bcdce88d629813a43cb67975054ad",
    6.0: "b6f4e5a35eab50b26e174e0fe97de84c1b3e3cb91c4af1511dc7ae6d44eec7bc",
}


@pytest.mark.parametrize("sea", GOLDEN)
def test_measurement_rng_parity_with_sfd_and_display_consumers(sea):
    sensor = RadarXBand(RadarXParams(sea_state_beaufort=sea))
    sensor.reset(731)
    digest = hashlib.sha256()
    for k in range(81):
        t = k * 0.25
        own = np.array([20 * t, 5 * t, 20.0, 5.0])
        targets = [(i, np.array([800 + i * 500 - t, 300 + i * 200 + 2 * t, -1.0, 2.0]), 35.0, 8.0) for i in range(3)]
        measurements = sensor.generate_measurements(t, targets, own)
        packet = sensor.scan_document()
        sfd = sensor.generate_sfd_frame(t, targets, own)
        assert len(sfd["measurements"]) == len(packet["returns"])
        assert packet == sensor.scan_document()
        for label, position in measurements:
            digest.update(np.array([label, *position], dtype="<f8").tobytes())
        assert all("do_idx" not in item and "target_hint" not in item for item in packet["returns"])
    assert digest.hexdigest() == GOLDEN[sea]


def test_scan_read_is_detached_and_time_reversal_requires_reset():
    sensor = RadarXBand()
    sensor.reset(5)
    own = np.array([400.0, 900.0, 0.0, 0.0])
    sensor.set_mount_yaw(1.2)
    sensor.generate_measurements(0, [], own)
    sensor.generate_measurements(2.5, [], own)
    first = sensor.scan_document()
    first["descriptor"]["rpm"] = -1
    assert "rpm" not in sensor.scan_document()["descriptor"]
    assert sensor.last_scan.yaw_rad == 1.2
    with pytest.raises(ValueError, match="increasing time"):
        sensor.generate_measurements(1.0, [], own)
    sensor.reset(5)
    sensor.generate_measurements(0, [], own)
    assert sensor.last_scan.sample_seq == 1
