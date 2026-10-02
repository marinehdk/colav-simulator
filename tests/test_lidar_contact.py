"""P3-S3 LidarContactSensor tests (spec #90).

Covers the sensor_id=4 bypass channel (contract sensor-model-v1 §1/§2):
bypass semantics (measurements ride the cache but never update the KF main
chain), the 100 m range gate + tilted-install blind ring, the 10 Hz cadence,
noise statistics (AWSIM range Gaussian + VIMM sigma_c cross-range), the VIMM
visibility chain, landmask occlusion (S1 TerrainGrid tool), and the suite
config wiring. Mount geometry parity with the Unity table is pinned in
``tests/test_observations_endpoint.py`` (single backend-authoritative copy in
``colav_simulator/core/mast_cameras.py``).
"""

import numpy as np
import pytest

from colav_simulator.core.sensing import (
    Config,
    ExternalCameraSensor,
    ISensor,
    LidarContactSensor,
    LidarParams,
    RadarXBand,
    RadarXParams,
    SensorSuiteBuilder,
)
from colav_simulator.core.radar_occlusion import TerrainGrid
from colav_simulator.core.tracking.trackers import KF
from colav_simulator.schemas.sensor_model_v1 import FUSION_SENSOR_IDS, SensorId

MOUNT_HEIGHT_M = 11.0
MOUNT_PITCH_DEG = -10.0


def make_sensor(**overrides) -> LidarContactSensor:
    params = LidarParams(**overrides)
    sensor = LidarContactSensor(params)
    sensor.reset(seed=1234)
    return sensor


def static_target(do_idx: int, north: float, east: float, length: float = 20.0, width: float = 6.0) -> tuple:
    return (do_idx, np.array([north, east, 0.0, 0.0]), length, width)


def ownship_at(north: float = 0.0, east: float = 0.0) -> np.ndarray:
    return np.array([north, east, 0.0, 0.0])


def collect(sensor: LidarContactSensor, target: tuple, steps: int = 40, dt: float = 0.5) -> list[np.ndarray]:
    """Runs one deterministic timeline (fresh 1234-seeded reset) and returns the contacts."""
    sensor.reset(1234)
    points = []
    for k in range(1, steps + 1):
        t = k * dt
        measurement = sensor.generate_measurements(t, [target], ownship_at())[0][1]
        if not np.isnan(measurement).any():
            points.append(np.asarray(measurement, dtype=float))
    return points


class TestBypassSemantics:
    def test_bypass_flag_is_on_for_lidar_only(self) -> None:
        assert ISensor.bypass_fusion is False, "default ISensor = fusing channel"
        assert RadarXBand.bypass_fusion is False, "radar_x fuses (contract §2)"
        assert ExternalCameraSensor.bypass_fusion is False, "camera_eo/ir fuse (contract §2)"
        assert LidarContactSensor.bypass_fusion is True, "lidar = 旁路通道（契约 §1/§2 硬边界）"

    def test_lidar_absent_from_fusion_vocabulary(self) -> None:
        assert SensorId.LIDAR not in FUSION_SENSOR_IDS
        assert SensorId.LIDAR == 4

    def test_kf_main_chain_excludes_bypass_channel(self) -> None:
        """The KF trajectory must be bit-identical with and without the bypass sensor.

        Both trackers see the same targets; only the fusing radar updates the
        filter. Any lidar contribution would diverge xs/P.
        """
        target_a = static_target(0, 60.0, 25.0)
        target_b = static_target(1, -40.0, 10.0)

        def make_radar() -> RadarXBand:
            radar = RadarXBand(RadarXParams(range_scale_nm=0.75, drop_probability=0.0))
            radar.reset(seed=7)
            return radar

        with_lidar = KF([make_radar(), make_sensor()])
        without_lidar = KF([make_radar()])
        own = ownship_at()
        cache_with = None
        for k in range(1, 60):
            t = k * 0.5
            tracks_with, cache_with = with_lidar.track(t, 0.5, [target_a, target_b], own)
            tracks_without, _ = without_lidar.track(t, 0.5, [target_a, target_b], own)
            assert [s.state.tolist() for s in tracks_with] == [s.state.tolist() for s in tracks_without], (
                f"KF main chain moved differently at t={t}: bypass channel leaked into the update"
            )
            assert [s.covariance.tolist() for s in tracks_with] == [
                s.covariance.tolist() for s in tracks_without
            ], f"KF covariance diverged at t={t}: bypass channel leaked into the update"

        # The cache still carries the lidar suite entry (bypass rides the cache).
        lidar_entry = cache_with[1]
        assert len(lidar_entry) == 2, "one cache slot per true target"
        assert any(not np.isnan(z).any() for _idx, z in lidar_entry), "lidar contacts must reach the measurement cache"

    def test_lidar_only_suite_coasts_forever_while_fusing_control_moves(self) -> None:
        sensor = make_sensor()
        tracker = KF([sensor])
        states = []
        for k in range(1, 30):
            t = k * 0.5
            target = static_target(0, 60.0 + k, 0.0)  # moving truth
            tracks, _ = tracker.track(t, 0.5, [target], ownship_at())
            states.append(tracks[0].state.copy())
        for a, b in zip(states[1:], states[2:], strict=False):
            assert np.allclose(a, b), "bypass-only suite: coasting predictions must be identical (no measurement update)"

        # Cross-check: a fusing sensor with the same cache flow does move the state.
        class _FusingRadar(ISensor):
            type = "radar"
            bypass_fusion = False
            max_range = 1000.0

            def R(self, xs):
                return np.diag([1.0, 1.0])

            def H(self, xs):
                return np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])

            def h(self, xs):
                return self.H(xs) @ xs

            def reset(self, seed):
                pass

            def seed(self, seed):
                pass

            def generate_measurements(self, t, true_do_states, ownship_state):
                return [(do[0], self.h(do[1])) for do in true_do_states]

        fusing = KF([_FusingRadar()])
        moved = None
        for k in range(1, 30):
            t = k * 0.5
            target = static_target(0, 60.0 + k, 0.0)
            tracks, _ = fusing.track(t, 0.5, [target], ownship_at())
            moved = tracks[0].state.copy()
        assert not np.allclose(moved, states[-1]), "fusing control: perfect radar must track the mover (sanity)"

    def test_no_clutter_entries_from_bypass_sensor(self) -> None:
        sensor = make_sensor()
        target = static_target(0, 60.0, 0.0)
        clutter_hits = 0
        for k in range(1, 40):
            t = k * 0.5
            for idx, z in sensor.generate_measurements(t, [target], ownship_at()):
                if idx == -1:
                    clutter_hits += 1
        assert clutter_hits == 0, "contact model emits no clutter rows (v1: 视景侧才做逐点 dropoff)"


class TestRangeGates:
    def test_blind_ring_follows_tilted_install(self) -> None:
        sensor = make_sensor()
        expected = MOUNT_HEIGHT_M / np.tan(np.radians(abs(MOUNT_PITCH_DEG) + 15.0))
        assert sensor.blind_ring_m == pytest.approx(expected, rel=1e-9)
        assert sensor.blind_ring_m == pytest.approx(23.59, abs=0.05), "milliampere §4.3 近端盲环 ≈23.6 m（下倾 10° 后）"

    def test_near_ring_targets_yield_no_contacts(self) -> None:
        sensor = make_sensor()
        points = collect(sensor, static_target(0, sensor.blind_ring_m * 0.5, 0.0))
        assert points == [], "targets inside the tilted blind ring must not produce contacts"

    def test_range_gate_100m(self) -> None:
        sensor = make_sensor()
        far = collect(sensor, static_target(0, 150.0, 0.0), steps=60)
        assert far == [], "targets beyond the 100 m nominal range must not produce contacts"
        near = collect(sensor, static_target(0, 80.0, 0.0), steps=60)
        assert len(near) > 10, "targets inside 100 m must be contacted regularly"


class TestCadence:
    def test_10hz_rate_gate(self) -> None:
        # Always-visible configuration isolates the rate gate from the visibility chain.
        gate_off = dict(visibility_w11=1.0, visibility_w01=1.0, detection_probability=1.0)
        target = static_target(0, 60.0, 0.0)
        own = ownship_at()
        coarse = make_sensor(**gate_off)
        fresh_coarse = sum(
            1
            for k in range(1, 40)
            if not np.isnan(coarse.generate_measurements(k * 0.5, [target], own)[0][1]).any()
        )
        assert fresh_coarse == 38, "0.5 s steps (float-exact) must pass the 10 Hz gate every call after init"
        fine = make_sensor(**gate_off)
        fresh_fine = sum(
            1
            for k in range(1, 41)
            if not np.isnan(fine.generate_measurements(k * 0.05, [target], own)[0][1]).any()
        )
        assert fresh_fine <= 20, f"50 ms steps must be rate-held to the 10 Hz budget (got {fresh_fine}/39)"


class TestNoiseStatistics:
    def test_contacts_center_on_truth_with_vimm_cross_range_spread(self) -> None:
        sensor = make_sensor()
        truth_n, truth_e = 60.0, 25.0
        truth_range = float(np.hypot(truth_n, truth_e))
        points = collect(sensor, static_target(0, truth_n, truth_e), steps=400, dt=0.1)
        assert len(points) > 250, "10 Hz over 40 s must yield a usable sample"
        cloud = np.array(points)
        mean = cloud.mean(axis=0)
        # Statistical mean: the visibility chain keeps ~77% of frames; the polar
        # noise is zero-mean so the mean recovers the truth within a few sigma_c/sqrt(n).
        bound = 6 * 6.6 / np.sqrt(len(points))
        assert abs(mean[0] - truth_n) < bound and abs(mean[1] - truth_e) < bound
        # Cross-range: bearing error (measured from the origin, wrapped) × range ≈ sigma_c.
        bearing = np.arctan2(cloud[:, 1], cloud[:, 0])
        bearing_error = (bearing - np.arctan2(truth_e, truth_n) + np.pi) % (2.0 * np.pi) - np.pi
        cross = np.std(bearing_error) * truth_range
        assert cross == pytest.approx(6.6, rel=0.25), "cross-range spread ≈ VIMM lidar_sigma_c (6.6 m)"
        # Radial: slant-range error stays at the AWSIM Gaussian scale.
        range_error = np.hypot(cloud[:, 0], cloud[:, 1]) - truth_range
        assert abs(float(range_error.mean())) < 0.5, "range noise is zero-mean at the AWSIM scale"
        assert float(range_error.std()) < 0.5, "radial spread ≈ sigma_r(65 m) = 0.15 m (AWSIM), far below sigma_c"

    def test_covariance_isotropic_projection_uses_vimm_sigma_c(self) -> None:
        sensor = make_sensor()
        cov = sensor.position_cov_ne(65.0)
        expected = 0.5 * (sensor.range_sigma_m(65.0) ** 2 + 6.6**2)
        assert cov[0, 0] == pytest.approx(expected, rel=1e-9)
        assert cov[1, 1] == pytest.approx(expected, rel=1e-9)
        assert cov[0, 1] == 0.0 and cov[1, 0] == 0.0

    def test_deterministic_given_seed(self) -> None:
        first, second = LidarContactSensor(LidarParams()), LidarContactSensor(LidarParams())
        first.reset(seed=99)
        second.reset(seed=99)
        target = static_target(0, 60.0, 0.0)
        for k in range(1, 40):
            t = k * 0.5
            a = first.generate_measurements(t, [target], ownship_at())[0][1]
            b = second.generate_measurements(t, [target], ownship_at())[0][1]
            assert np.array_equal(a, b, equal_nan=True), f"seeded runs must coincide at t={t}"


class TestVisibilityAndOcclusion:
    def test_visibility_chain_drops_some_frames(self) -> None:
        sensor = make_sensor()
        target = static_target(0, 60.0, 0.0)
        points = collect(sensor, target, steps=400, dt=0.1)
        detection_rate = len(points) / 400
        # w11 = 0.9 chain × PD = 0.92 stationary detection rate ≈ 0.83.
        assert 0.6 <= detection_rate <= 0.95, f"VIMM visibility chain should thin frames (got {detection_rate:.2f})"

    def test_landmask_occlusion_blocks_contacts(self) -> None:
        mask = np.zeros((50, 50))
        mask[25, :] = 1.0  # east-west land band across north 240-250 m
        grid = TerrainGrid(mask, origin_e=0.0, origin_n=500.0, cell_size=10.0, mode="landmask")
        sensor = make_sensor(occlusion_grid=grid)
        own = ownship_at(north=300.0)
        target = static_target(0, 220.0, 0.0)  # 80 m away (inside the range gate), band in between
        points = []
        for k in range(1, 60):
            t = k * 0.5
            z = sensor.generate_measurements(t, [target], own)[0][1]
            if not np.isnan(z).any():
                points.append(z)
        assert points == [], "landmask-blocked target must yield no contacts"


class TestSuiteWiring:
    def test_config_roundtrip_and_builder(self) -> None:
        config = Config.from_dict([{"lidar": {"max_range_m": 100.0, "measurement_rate_hz": 10.0}}])
        assert len(config.sensor_list) == 1
        sensors = SensorSuiteBuilder.construct_sensors(config)
        assert len(sensors) == 1
        sensor = sensors[0]
        assert isinstance(sensor, LidarContactSensor)
        assert sensor.max_range == 100.0
        assert sensor.bypass_fusion is True
        assert sensor.params.mount_height_m == pytest.approx(11.0), "mount geometry from the mast table"
        assert sensor.params.mount_pitch_deg == pytest.approx(-10.0)
        dumped = config.to_dict_list()
        assert "lidar" in dumped[0]
        roundtrip = SensorSuiteBuilder.construct_sensors(Config.from_dict(dumped))
        assert isinstance(roundtrip[0], LidarContactSensor)
        assert roundtrip[0].params == config.sensor_list[0]

    def test_default_mount_derived_from_mast_table(self) -> None:
        from colav_simulator.core.mast_cameras import MAST_MOUNTS_BY_ID

        mount = MAST_MOUNTS_BY_ID["mast_lidar"]
        sensor = make_sensor()
        assert sensor.params.mount_id == mount.mount_id
        assert sensor.params.mount_height_m == mount.height_m
        assert sensor.params.mount_pitch_deg == mount.pitch_deg
