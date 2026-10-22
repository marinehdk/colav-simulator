"""RadarOperatorControls 真接收机控制（2026-10-22 契约 20-API-CONTRACT）。

覆盖：古野 17 档量程表、控制热调校验与 descriptor echo、STBY 停发射门、
GAIN 灵敏度进检测 SNR、RCS 覆盖 seam、A/C 行程→dB 映射。
"""

import numpy as np
import pytest

from colav_simulator.core.sensing import (
    RANGE_SCALES_NM_DEFAULT,
    RadarOperatorControls,
    RadarXBand,
    RadarXParams,
)


class _FixedRng:
    """检测链确定性替身：PD 门恒过、噪声恒零。"""

    def random(self):
        return 0.0

    def normal(self, _loc=0.0, _scale=1.0):
        return 0.0


def _sensor(**params) -> RadarXBand:
    sensor = RadarXBand(RadarXParams(shadow_video=False, **params))
    sensor._rng = _FixedRng()
    return sensor


def test_furuno_range_table_supersedes_legacy_six():
    assert len(RANGE_SCALES_NM_DEFAULT) == 17
    assert RANGE_SCALES_NM_DEFAULT[0] == 0.125 and RANGE_SCALES_NM_DEFAULT[-1] == 96.0
    assert {0.75, 1.5, 3.0, 6.0, 12.0, 24.0} <= set(RANGE_SCALES_NM_DEFAULT)


def test_attenuation_travel_maps_to_db():
    assert RadarOperatorControls.attenuation_db(0.0) == 0.0
    assert RadarOperatorControls.attenuation_db(100.0) == -20.0
    assert RadarOperatorControls.attenuation_db(50.0) == pytest.approx(-10.0)


def test_apply_controls_patches_and_echoes_descriptor():
    sensor = _sensor()
    echo = sensor.apply_operator_controls(gain_db=6.0, sea_suppression=40.0, rain_suppression=80.0)
    assert echo == {"gain_db": 6.0, "sea_suppression": 40.0, "rain_suppression": 80.0, "standby": False}
    descriptor = sensor.ppi_descriptor()
    assert descriptor["operator_controls"] == echo
    assert descriptor["range_scales_nm"] == [float(s) for s in RANGE_SCALES_NM_DEFAULT]


def test_apply_controls_validates_bounds_and_range_table():
    sensor = _sensor()
    with pytest.raises(ValueError, match="gain_db"):
        sensor.apply_operator_controls(gain_db=21.0)
    with pytest.raises(ValueError, match="sea_suppression"):
        sensor.apply_operator_controls(sea_suppression=-1.0)
    with pytest.raises(ValueError, match="range_scale_nm"):
        sensor.apply_operator_controls(range_scale_nm=5.0)  # 不在 17 档表
    # PATCH 语义：前一次合法赋值不被后面的非法请求破坏
    sensor.apply_operator_controls(gain_db=3.0)
    with pytest.raises(ValueError):
        sensor.apply_operator_controls(gain_db=99.0)
    assert sensor.operator_controls.gain_db == 3.0


def test_range_hot_update_moves_active_range_and_noise_cache():
    sensor = _sensor()
    sensor.apply_operator_controls(range_scale_nm=0.5)
    assert sensor.active_range_m == pytest.approx(0.5 * 1852.0)
    # r_mid 随量程 → 方位平均噪声缓存刷新
    r_mid = 0.5 * sensor.active_range_m
    expected = 0.5 * (RadarXParams().sigma_range_m**2 + (r_mid * RadarXParams().sigma_azimuth_rad) ** 2)
    assert sensor._R_ne[0, 0] == pytest.approx(expected)


def test_standby_stops_measurements_and_video():
    sensor = _sensor()
    own = np.array([0.0, 0.0, 3.0, 0.0])
    targets = [(0, np.array([1500.0, 0.0, 0.0, 0.0]), 40.0, 8.0)]
    sensor.generate_measurements(1.0, targets, own)
    assert sensor.scan_document()["status"] != "STANDBY"
    sensor.apply_operator_controls(standby=True)
    measurements = sensor.generate_measurements(2.0, targets, own)
    document = sensor.scan_document()
    assert document["status"] == "STANDBY"
    assert "shadow_video" not in document
    assert all(np.isnan(z).all() for _, z in measurements)


def test_gain_adds_to_detection_snr():
    sensor = _sensor()
    args = (0, np.array([1500.0, 0.0, 0.0, 0.0]), 40.0, 8.0, np.zeros(2), 1500.0, 0.0, 0.0, 1.0)
    base = sensor._detect(*args)
    sensor.apply_operator_controls(gain_db=10.0)
    boosted = sensor._detect(*args)
    assert base is not None and boosted is not None
    assert boosted["snr_db"] == pytest.approx(base["snr_db"] + 10.0)


def test_rcs_override_seam_replaces_dimension_formula():
    sensor = _sensor()
    args = (7, np.array([1500.0, 0.0, 0.0, 0.0]), 40.0, 8.0, np.zeros(2), 1500.0, 0.0, 0.0, 1.0)
    base = sensor._detect(*args)
    sensor._params.rcs_overrides_m2[7] = sensor.rcs_m2(40.0, 8.0) * 10.0
    boosted = sensor._detect(*args)
    assert base is not None and boosted is not None
    assert boosted["snr_db"] == pytest.approx(base["snr_db"] + 10.0)  # RCS ×10 → +10 dB
