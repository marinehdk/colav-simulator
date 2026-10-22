"""P3 first-batch RadarXBand detection-physics tests (00-REPORT §6 P3; 20 §3).

Covers the three effects added to the data-layer detection chain in
``colav_simulator/core/sensing.py`` (shadow RadarVideo untouched):
RCS aspect modulation (20 §3-3, 25 dB beam-on/bow-stern span), Swerling-1
fluctuation (constant within a revolution, redrawn per revolution, isolated
seed stream), and ITU-R P.838 two-way rain attenuation (20 §3-2) — plus the
rain=0 bitwise regression: with the default dry atmosphere the attenuation is
exactly 0.0 dB and the legacy SNR formula and its composition stay
bit-identical (aspect/SW1 are new always-on physics per the task, so the
identity is asserted on the rain/SNR path they compose into).
"""

import math

import numpy as np
import pytest

from colav_simulator.core.sensing import (
    RAIN_ATTENUATION_ALPHA_H,
    RAIN_ATTENUATION_K_H,
    RCS_ASPECT_SPAN_DB,
    RadarXBand,
    RadarXParams,
)


def make_sensor(**overrides) -> RadarXBand:
    params = RadarXParams(range_scale_nm=overrides.pop("range_scale_nm", 6.0), shadow_video=False, **overrides)
    sensor = RadarXBand(params)
    sensor.reset(seed=1234)
    return sensor


def target(do_idx: int, north: float, east: float, vn: float = 0.0, ve: float = 0.0) -> tuple:
    return (do_idx, np.array([north, east, vn, ve]), 20.0, 6.0)


def detect(sensor: RadarXBand, tgt: tuple, distance: float, bearing: float, t_cross: float) -> dict:
    record = sensor._detect(  # noqa: SLF001
        tgt[0], tgt[1], tgt[2], tgt[3], np.array([0.0, 0.0]), distance, bearing, 0.0, t_cross
    )
    assert record is not None, "2000 m / 60 m2 target stays far above the PD knee"
    return record


class TestRcsAspectModulation:
    def test_gain_bounds_bow_trough_beam_peak(self) -> None:
        sensor = make_sensor()
        assert sensor.rcs_aspect_gain_db(0.0) == -0.5 * RCS_ASPECT_SPAN_DB  # bow-on trough
        assert sensor.rcs_aspect_gain_db(math.pi) == -0.5 * RCS_ASPECT_SPAN_DB  # stern-on trough
        assert sensor.rcs_aspect_gain_db(0.5 * math.pi) == +0.5 * RCS_ASPECT_SPAN_DB  # beam-on peak
        sweep = np.linspace(0.0, math.pi, 721)
        gains = np.array([sensor.rcs_aspect_gain_db(float(a)) for a in sweep])
        assert gains.min() >= -0.5 * RCS_ASPECT_SPAN_DB
        assert gains.max() <= +0.5 * RCS_ASPECT_SPAN_DB
        assert float(gains.max() - gains.min()) == pytest.approx(RCS_ASPECT_SPAN_DB, abs=1e-9)

    def test_detect_snr_beam_minus_bow_equals_span(self) -> None:
        sensor = make_sensor()
        bow = detect(sensor, target(0, 2000.0, 0.0, vn=1.0), 2000.0, 0.0, 1.25)  # heading = bearing = north
        beam = detect(sensor, target(0, 2000.0, 0.0, ve=1.0), 2000.0, 0.0, 1.25)  # heading east, bearing north
        assert beam["snr_db"] - bow["snr_db"] == pytest.approx(RCS_ASPECT_SPAN_DB, rel=1e-9)
        ratio = 10.0 ** (0.1 * (beam["snr_db"] - bow["snr_db"]))
        assert ratio == pytest.approx(10.0 ** (RCS_ASPECT_SPAN_DB / 10.0), rel=1e-9)  # ~316x peak/trough

    def test_effective_rcs_respects_floor(self) -> None:
        sensor = make_sensor()
        skiff = (0, np.array([900.0, 0.0, 1.0, 0.0]), 4.0, 2.0)  # rcs_m2 = 4 (== rcs_min)
        record = sensor._detect(  # noqa: SLF001
            skiff[0], skiff[1], skiff[2], skiff[3], np.array([0.0, 0.0]), 900.0, 0.0, 0.0, 1.25
        )
        assert record is not None
        assert record["snr_db"] > 0.0, "floor + modulation must keep the minimum-scale target detectable"


class TestSwerling1:
    def test_constant_within_revolution(self) -> None:
        sensor = make_sensor()
        assert sensor.sw1_fluctuation_db(7, 3) == sensor.sw1_fluctuation_db(7, 3)
        first = detect(sensor, target(3, 1500.0, 0.0, vn=1.0), 1500.0, 0.0, 1.0)
        second = detect(sensor, target(3, 1500.0, 0.0, vn=1.0), 1500.0, 0.0, 1.0)
        assert first["snr_db"] == second["snr_db"], "same (revolution, target) => same amplitude"

    def test_redraws_between_revolutions(self) -> None:
        sensor = make_sensor()
        draws = np.array([sensor.sw1_fluctuation_db(rev, 0) for rev in range(40)])
        assert np.unique(draws).size > 1, "SW1 must redraw each revolution"
        linear = 10.0 ** (0.1 * np.array([sensor.sw1_fluctuation_db(rev, 0) for rev in range(2000)]))
        assert linear.mean() == pytest.approx(1.0, rel=0.1), "unit-mean exponential power draw (SW1/SW2 family)"

    def test_seed_isolation_from_production_rng(self) -> None:
        sensor = make_sensor()
        before = sensor._rng.bit_generator.state  # noqa: SLF001
        draws = [sensor.sw1_fluctuation_db(rev, 5) for rev in range(10)]
        assert sensor._rng.bit_generator.state == before, "SW1 must not consume the production RNG stream"  # noqa: SLF001
        twin = make_sensor()
        assert [twin.sw1_fluctuation_db(rev, 5) for rev in range(10)] == draws, "same seed reproduces the stream"
        other = make_sensor()
        other.reset(seed=4321)
        others = [other.sw1_fluctuation_db(rev, 5) for rev in range(10)]
        assert others != draws, "different sensor seed must change the stream"


class TestRainAttenuation:
    def test_monotone_in_rate_and_range(self) -> None:
        rates = (0.0, 4.0, 25.0, 50.0, 100.0)
        at_fixed_range = [make_sensor(rain_rate_mm_h=rate).rain_attenuation_db(5556.0) for rate in rates]
        assert all(lo < hi for lo, hi in zip(at_fixed_range, at_fixed_range[1:], strict=False))
        rainy = make_sensor(rain_rate_mm_h=25.0)
        distances = (100.0, 1000.0, 5556.0, 11112.0, 22224.0)
        along_range = [rainy.rain_attenuation_db(d) for d in distances]
        assert all(lo < hi for lo, hi in zip(along_range, along_range[1:], strict=False))

    def test_p838_9p4ghz_magnitude_anchors(self) -> None:
        # 20 §3-2 magnitudes from the P.838-3 coefficients: drizzle 4 mm/h ~= 0.05
        # dB/km, heavy rain 25 ~= 0.6, downpour 50 ~= 1.4 (single path).
        def gamma_per_km(rate: float) -> float:
            return make_sensor(rain_rate_mm_h=rate).rain_attenuation_db(1000.0) / 2.0

        assert gamma_per_km(4.0) == pytest.approx(0.05, abs=0.01)
        assert gamma_per_km(25.0) == pytest.approx(0.6, abs=0.1)
        assert gamma_per_km(50.0) == pytest.approx(1.4, abs=0.15)
        assert RAIN_ATTENUATION_K_H * 4.0**RAIN_ATTENUATION_ALPHA_H == pytest.approx(0.0538, abs=5e-4)

    def test_rain_reduces_detection_snr(self) -> None:
        # 700 m: SNR stays far above the PD knee even at 50 mm/h + worst aspect.
        dry = detect(make_sensor(), target(0, 700.0, 0.0, vn=1.0), 700.0, 0.0, 1.25)
        wet = detect(make_sensor(rain_rate_mm_h=50.0), target(0, 700.0, 0.0, vn=1.0), 700.0, 0.0, 1.25)
        loss = dry["snr_db"] - wet["snr_db"]
        assert loss == pytest.approx(2.0 * 0.00914 * 50.0**1.2784 * 0.7, rel=1e-9), "A = 2 gamma R_km"


class TestRainZeroRegression:
    def test_zero_rain_bitwise_legacy_snr(self) -> None:
        sensor = make_sensor()
        params = sensor.params
        for distance in (100.0, 5556.0, 11112.0, 22224.0):
            assert sensor.rain_attenuation_db(distance) == 0.0  # exactly 0.0 dB, no approximation
            for rcs in (1.0, 10.0, 60.0, 5000.0):
                legacy = (
                    params.snr_ref_db
                    + 10.0 * np.log10(rcs / params.rcs_ref_m2)
                    - params.snr_decay_db_per_decade
                    * np.log10(max(distance, sensor.blind_ring_m, 1.0) / params.snr_ref_range_m)
                )
                assert sensor.snr_db(distance, rcs) == legacy, "snr_db stays the untouched pre-rain formula"

    def test_zero_rain_composed_detection_snr_bitwise(self) -> None:
        sensor = make_sensor()
        params = sensor.params
        record = detect(sensor, target(0, 2000.0, 0.0, vn=1.0), 2000.0, 0.0, 1.25)
        fluctuation_db = sensor.rcs_aspect_gain_db(0.0) + sensor.sw1_fluctuation_db(0, 0)
        effective_rcs = max(params.rcs_min_m2, sensor.rcs_m2(20.0, 6.0) * 10.0 ** (0.1 * fluctuation_db))
        assert record["snr_db"] == sensor.snr_db(2000.0, effective_rcs), "dry air must not perturb the SNR bits"

    def test_params_default_roundtrip_and_validation(self) -> None:
        assert RadarXParams().rain_rate_mm_h == 0.0
        params = RadarXParams.from_dict({"rain_rate_mm_h": 12.5})
        assert params.rain_rate_mm_h == 12.5
        assert RadarXParams.from_dict(params.to_dict()).rain_rate_mm_h == 12.5
        with pytest.raises(ValueError, match="rain_rate_mm_h"):
            RadarXParams(rain_rate_mm_h=-1.0)
