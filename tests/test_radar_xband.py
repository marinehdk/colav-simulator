"""P3-S1 RadarXBand X-band radar model tests (spec #90).

Covers the milliampere-ch5 §5.1 parameter table as implemented in
``colav_simulator/core/sensing.py`` (RadarXBand/RadarXParams): VBW blind ring,
mast blind sectors, radar horizon, terrain occlusion (synthetic DEM), async
beam-crossing sampling, PD(SNR) anchors, Poisson clutter statistics, the
sensor-model-v1 frame contract, tracker compatibility, and the per-scan cap.
Evidence artifacts (PD-range curve, clutter statistics, occlusion cases) are
written to ``output/sango-radar-s1/``.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.radar_occlusion import TerrainGrid, load_occlusion_grid
from colav_simulator.core.sensing import (
    Config,
    RadarXBand,
    RadarXParams,
    SensorSuiteBuilder,
    detection_probability_swerling0,
)
from colav_simulator.core.tracking.trackers import KF, KFParams
from colav_simulator.schemas.sensor_model_v1 import SfdMeasurementFrame

EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "output" / "sango-radar-s1"
NM = 1852.0


def make_sensor(**overrides) -> RadarXBand:
    params = RadarXParams(range_scale_nm=overrides.pop("range_scale_nm", 3.0), **overrides)
    sensor = RadarXBand(params)
    sensor.reset(seed=1234)
    return sensor


def static_target(do_idx: int, north: float, east: float, length: float = 20.0, width: float = 6.0) -> tuple:
    return (do_idx, np.array([north, east, 0.0, 0.0]), length, width)


def ownship_at(north: float = 0.0, east: float = 0.0, vn: float = 10.0, ve: float = 0.0) -> np.ndarray:
    return np.array([north, east, vn, ve])


class TestDetectionGeometry:
    def test_blind_ring_gates_near_targets(self) -> None:
        sensor = make_sensor()
        assert sensor.blind_ring_m == pytest.approx(54.13, abs=0.1)  # 12 m / tan(12.5 deg), milliampere §4.3
        inside = static_target(0, sensor.blind_ring_m * 0.5, 0.0)
        hits = 0
        for k in range(1, 40):
            t = k * 0.5
            measurements = sensor.generate_measurements(t, [inside], ownship_at())
            if not np.isnan(measurements[0][1]).any():
                hits += 1
        assert hits == 0, "targets inside the VBW blind ring must yield no measurement"

    def test_mast_blind_sector_relative_to_bow(self) -> None:
        blocked_sensor = make_sensor(blind_sectors_deg=((0.0, 5.0),))
        ahead = static_target(0, 2000.0, 0.0)  # bearing 0 deg = dead ahead (ownship steers north)
        beam = static_target(1, 0.0, 2000.0)  # bearing 90 deg = starboard beam
        hits_ahead, hits_beam = 0, 0
        for k in range(1, 40):
            t = k * 0.5
            measurements = blocked_sensor.generate_measurements(t, [ahead, beam], ownship_at())
            if not np.isnan(measurements[0][1]).any():
                hits_ahead += 1
            if not np.isnan(measurements[1][1]).any():
                hits_beam += 1
        assert hits_ahead == 0, "target dead ahead inside the (0 deg, +-5 deg) sector must be masked"
        assert hits_beam >= 8, "target abeam outside the sector must be swept regularly"

    def test_radar_horizon_gates_beyond_geometric_range(self) -> None:
        sensor = make_sensor(range_scale_nm=24.0)
        target_height = 2.0
        horizon = sensor.horizon_range_m(target_height)
        assert horizon == pytest.approx(4120.0 * (math.sqrt(12.0) + math.sqrt(target_height)), rel=1e-9)
        beyond = static_target(0, horizon * 1.2, 0.0)  # within 24 nm scale, beyond the horizon
        hits = 0
        for k in range(1, 60):
            t = k * 0.5
            measurements = sensor.generate_measurements(t, [beyond], ownship_at(vn=0.0))
            if not np.isnan(measurements[0][1]).any():
                hits += 1
        assert hits == 0, "targets beyond the radar horizon must yield no measurement"

    def test_active_range_scale_gates(self) -> None:
        sensor = make_sensor(range_scale_nm=0.75)
        far = static_target(0, 2.0 * NM, 0.0)
        hits = 0
        for k in range(1, 40):
            t = k * 0.5
            measurements = sensor.generate_measurements(t, [far], ownship_at())
            if not np.isnan(measurements[0][1]).any():
                hits += 1
        assert hits == 0


class TestPdModel:
    def test_pd_swerling0_anchors_and_monotonicity(self) -> None:
        pd_low = float(detection_probability_swerling0(-20.0))
        pd_mid = float(detection_probability_swerling0(0.0))
        pd_anchor = float(detection_probability_swerling0(11.67))  # Albersheim PD=0.9 @ Pfa=1e-4
        pd_high = float(detection_probability_swerling0(30.0))
        assert pd_low < pd_mid < pd_anchor < pd_high <= 1.0
        assert 0.87 <= pd_anchor <= 0.93, "erfc approximation must hold the Albersheim anchor"
        assert pd_mid < 0.05, "PD at zero SNR must sit near Pfa"

    def test_pd_range_curve_evidence(self) -> None:
        sensor = make_sensor(range_scale_nm=24.0)
        ranges_nm = [0.5, 1.0, 2.0, 3.0, 6.0, 9.0, 12.0, 18.0, 24.0]
        trials = 400
        curve = []
        own = ownship_at(vn=0.0)
        for range_nm in ranges_nm:
            sensor.reset(seed=99)
            distance = range_nm * NM
            target = static_target(0, distance, 0.0, length=10.0, width=4.0)
            detections = 0
            scans = 0
            for k in range(1, trials + 1):
                t = k * 2.5  # one antenna revolution per call (24 rpm, 2.5 s scan)
                records, _clutter, _swept = sensor._scan(t, [target], own)  # noqa: SLF001
                scans += 1
                detections += len(records)
            analytic = float(
                detection_probability_swerling0(sensor.snr_db(distance, sensor.rcs_m2(10.0, 4.0)), sensor.params.pfa)
            )
            curve.append(
                {
                    "range_nm": range_nm,
                    "range_m": distance,
                    "snr_db": float(sensor.snr_db(distance, sensor.rcs_m2(10.0, 4.0))),
                    "pd_analytic": analytic,
                    "pd_measured": detections / scans,
                    "note": "per-revolution Monte-Carlo (400 scans, seed 99): beam crossing + PD(SNR) draw",
                }
            )
        for lo, hi in zip(curve, curve[1:], strict=False):
            assert lo["snr_db"] >= hi["snr_db"], "SNR must be monotone decreasing in range"
        assert curve[0]["pd_analytic"] > 0.99
        assert curve[-1]["snr_db"] < -20.0
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "artifact": "pd-range-curve",
            "sensor": "RadarXBand",
            "params": {
                "snr_ref_db": sensor.params.snr_ref_db,
                "snr_ref_range_m": sensor.params.snr_ref_range_m,
                "rcs_ref_m2": sensor.params.rcs_ref_m2,
                "decay_db_per_decade": sensor.params.snr_decay_db_per_decade,
                "pfa": sensor.params.pfa,
                "target_length_m": 10.0,
                "target_width_m": 4.0,
            },
            "curve": curve,
        }
        (EVIDENCE_DIR / "pd-range-curve.json").write_text(json.dumps(payload, indent=2))


class TestAsyncSampling:
    def test_measurements_only_on_beam_crossings(self) -> None:
        sensor = make_sensor()
        target = static_target(0, 2000.0, 500.0)
        timestamps = []
        for k in range(1, 121):
            t = k * 0.5
            measurements = sensor.generate_measurements(t, [target], ownship_at())
            if not np.isnan(measurements[0][1]).any():
                timestamps.append(t)
        assert len(timestamps) >= 10, "a 2.5 s antenna must sweep the target repeatedly in 60 s"
        gaps = np.diff(timestamps)
        assert np.all(gaps >= 1.9), "no two measurements within one antenna revolution"
        assert abs(float(np.mean(gaps)) - 2.5) < 0.6, "mean refresh interval ~= scan period (24 rpm)"

    def test_sfd_frame_timestamps_precede_frame_time(self) -> None:
        sensor = make_sensor()
        target = static_target(0, 1500.0, -700.0)
        for k in range(1, 30):
            t = k * 0.5
            frame = sensor.generate_sfd_frame(t, [target], ownship_at(), ownship_yaw=0.2)
            for record in frame["measurements"]:
                assert record["t_s"] <= frame["t_s"] + 1e-9
                assert 0.0 <= record["confidence"] <= 1.0


class TestClutter:
    def test_poisson_statistics_and_radial_decay(self) -> None:
        sensor = make_sensor(range_scale_nm=6.0)  # rate 5e-7/m2, decay 2, Beaufort 3
        expected = sensor.expected_clutter_count()
        analytic = (
            2.0
            * math.pi
            * sensor.params.clutter_rate_per_m2
            * sensor.params.clutter_ref_range_m**2
            * math.log(sensor.active_range_m / sensor.blind_ring_m)
        )
        assert expected == pytest.approx(analytic, rel=1e-9)
        counts = []
        radii = []
        for k in range(1, 600):  # 0.5 s steps -> one revolution every 5 calls
            t = k * 0.5
            _records, clutter, _swept = sensor._scan(t, [], ownship_at())  # noqa: SLF001
            counts.append(len(clutter))
            for point in clutter:
                radii.append(float(np.linalg.norm(point["position_world"] - np.array([0.0, 0.0]))))
        scan_counts = np.asarray([c for c in counts if c > 0])  # revolutions only (between-scan calls emit none)
        assert scan_counts.size >= 100, "600 calls at 0.5 s must contain >= 100 completed revolutions"
        assert abs(scan_counts.mean() - expected) < 0.1 * expected, "empirical Poisson mean tracks the analytic intensity"
        assert 0.4 < scan_counts.var() / scan_counts.mean() < 2.2, "cardinality dispersion consistent with Poisson"
        radii = np.asarray(radii)
        assert radii.min() >= sensor.blind_ring_m - 1e-6, "clutter excluded from the VBW blind ring"
        inner = radii[radii < 0.5 * sensor.active_range_m]
        outer = radii[radii >= 0.5 * sensor.active_range_m]
        inner_area = math.pi * (0.5 * sensor.active_range_m) ** 2 - math.pi * sensor.blind_ring_m**2
        outer_area = math.pi * (sensor.active_range_m**2 - (0.5 * sensor.active_range_m) ** 2)
        assert inner.size / inner_area > outer.size / outer_area, "range-decay 2 keeps clutter near-dominant"
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "artifact": "clutter-statistics",
            "expected_count_per_scan": expected,
            "empirical_mean": float(scan_counts.mean()),
            "empirical_variance": float(scan_counts.var()),
            "scans": int(scan_counts.size),
            "sea_state_beaufort": sensor.params.sea_state_beaufort,
            "clutter_rate_per_m2": sensor.params.clutter_rate_per_m2,
            "clutter_range_decay": sensor.params.clutter_range_decay,
            "min_radius_m": float(radii.min()),
            "blind_ring_m": sensor.blind_ring_m,
        }
        (EVIDENCE_DIR / "clutter-statistics.json").write_text(json.dumps(payload, indent=2))

    def test_sea_state_scales_intensity(self) -> None:
        calm = make_sensor(range_scale_nm=6.0, sea_state_beaufort=1.0)
        rough = make_sensor(range_scale_nm=6.0, sea_state_beaufort=6.0)
        assert rough.expected_clutter_count() > calm.expected_clutter_count() * 3.0  # 3 dB/B over 5 B = x31

    def test_deterministic_given_seed(self) -> None:
        first, second = make_sensor(), make_sensor()
        points = []
        for sensor in (first, second):
            sensor.reset(seed=777)
            run = []
            for k in range(1, 40):
                _records, clutter, _swept = sensor._scan(k * 0.5, [], ownship_at())  # noqa: SLF001
                run.append([p["position_world"].tolist() for p in clutter])
            points.append(run)
        assert points[0] == points[1], "same seed must reproduce identical clutter realizations"

    def test_per_scan_measurement_cap(self) -> None:
        sensor = make_sensor(range_scale_nm=24.0, sea_state_beaufort=8.0, max_measurements_per_scan=25)
        total = 0
        for k in range(1, 60):
            t = k * 0.5
            records, clutter, _swept = sensor._scan(t, [], ownship_at())  # noqa: SLF001
            total = max(total, len(records) + len(clutter))
        assert total <= 25, "per-scan output cap must hold"


class TestTerrainOcclusion:
    @pytest.fixture()
    def dem_ridge(self, tmp_path: Path) -> Path:
        """Synthetic DEM: 120x120 cells @ 10 m with a 40 m ridge across the middle."""
        cells = 120
        cell = 10.0
        elevation = np.zeros((cells, cells))
        elevation[55:65, :] = 40.0  # east-west ridge band across north 550-650
        path = tmp_path / "ridge_dem.tif"
        from osgeo import gdal, osr  # noqa: PLC0415

        gdal.UseExceptions()
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(str(path), cells, cells, 1, gdal.GDT_Float32)
        dataset.SetGeoTransform((37000.0, cell, 0.0, 6957000.0, 0.0, -cell))
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(32648)
        dataset.SetProjection(srs.ExportToWkt())
        dataset.GetRasterBand(1).WriteArray(elevation.astype(np.float32))
        dataset.GetRasterBand(1).SetNoDataValue(-9999.0)
        dataset = None
        return path

    def test_elevation_grid_blocks_behind_ridge(self, dem_ridge: Path) -> None:
        grid = TerrainGrid.from_geotiff(dem_ridge, downsample=1, mode="elevation")
        blocked = grid.line_of_sight_blocked(
            antenna_e=37060.0,
            antenna_n=6956300.0,
            target_e=37060.0,
            target_n=6956800.0,
            antenna_height_m=12.0,
            target_height_m=2.0,
        )
        assert blocked, "40 m ridge between antenna (12 m) and low target must block the sight line"
        clear = grid.line_of_sight_blocked(
            antenna_e=37060.0,
            antenna_n=6956300.0,
            target_e=37060.0,
            target_n=6956100.0,
            antenna_height_m=12.0,
            target_height_m=2.0,
        )
        assert not clear, "target before the ridge must stay visible"

    def test_landmask_mode_blocks_on_any_land_cell(self, tmp_path: Path) -> None:
        mask = np.zeros((50, 50))
        mask[25, :] = 1.0
        grid = TerrainGrid(mask, origin_e=0.0, origin_n=500.0, cell_size=10.0, mode="landmask")
        assert grid.line_of_sight_blocked(0.0, 400.0, 0.0, 0.0, 12.0, 2.0)
        assert not grid.line_of_sight_blocked(0.0, 400.0, 0.0, 480.0, 12.0, 2.0)

    def test_radarxband_occulted_target_yields_no_measurement(self, dem_ridge: Path) -> None:
        sensor = make_sensor(range_scale_nm=3.0, occlusion_dem_path=str(dem_ridge), occlusion_downsample=1)
        behind = static_target(0, 6956800.0, 37060.0)  # 500 m north of the antenna, ridge in between
        own = ownship_at(north=6956300.0, east=37060.0, vn=0.0, ve=0.0)
        hits = 0
        for k in range(1, 40):
            t = k * 0.5
            measurements = sensor.generate_measurements(t, [behind], own)
            if not np.isnan(measurements[0][1]).any():
                hits += 1
        assert hits == 0, "DEM-blocked target must yield no measurement"
        assert sensor.ppi_descriptor()["occlusion"] is True

    def test_missing_dem_degrades_to_no_occlusion(self) -> None:
        assert load_occlusion_grid(None) is None
        assert load_occlusion_grid("/nonexistent/path/dem.tif") is None
        sensor = make_sensor(occlusion_dem_path="/nonexistent/path/dem.tif")
        target = static_target(0, 2000.0, 0.0)
        hits = 0
        for k in range(1, 40):
            t = k * 0.5
            measurements = sensor.generate_measurements(t, [target], ownship_at())
            if not np.isnan(measurements[0][1]).any():
                hits += 1
        assert hits > 0, "sensor must stay functional (unoccluded) when the DEM is unavailable"
        assert sensor.ppi_descriptor()["occlusion"] is False

    def test_occlusion_case_evidence(self, dem_ridge: Path) -> None:
        grid = TerrainGrid.from_geotiff(dem_ridge, downsample=1, mode="elevation")
        cases = []
        for name, args, expect in [
            ("behind_ridge", (37060.0, 6956300.0, 37060.0, 6956800.0), True),
            ("before_ridge", (37060.0, 6956300.0, 37060.0, 6956100.0), False),
            ("tall_target_over_ridge", (37060.0, 6956300.0, 37060.0, 6956800.0), None),
        ]:
            target_height = 60.0 if name == "tall_target_over_ridge" else 2.0
            blocked = grid.line_of_sight_blocked(*args, antenna_height_m=12.0, target_height_m=target_height)
            if expect is not None:
                assert blocked is expect
            cases.append({"case": name, "blocked": bool(blocked), "target_height_m": target_height})
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        (EVIDENCE_DIR / "occlusion-cases.json").write_text(
            json.dumps({"artifact": "occlusion-cases", "dem": "synthetic ridge 40 m @ 10 m cells", "cases": cases}, indent=2)
        )


class TestContractAndWiring:
    def test_sfd_frame_validates_against_frozen_schema(self) -> None:
        sensor = make_sensor()
        target = static_target(0, 1500.0, 400.0)
        frames = []
        for k in range(1, 16):
            frame = sensor.generate_sfd_frame(k * 0.5, [target], ownship_at(), ownship_yaw=0.35)
            frames.append(frame)
        validated = [SfdMeasurementFrame.model_validate(frame) for frame in frames]
        assert all(v.sensor_id == 1 and v.sensor_label == "radar_x" for v in validated)
        assert all(v.frame_id == "ownship_ned" for v in validated)
        assert all(v.mount_id == "mast_top_xband" for v in validated)
        assert all(v.epoch_unix_ns is None for v in validated)
        with_measurements = [v for v in validated if v.measurements]
        assert with_measurements, "3 nm target must be swept at least once in 7 s of simulated warmup"
        for v in with_measurements:
            for measurement in v.measurements:
                assert measurement.position_cov_ne_m2[0][1] == measurement.position_cov_ne_m2[1][0]
                assert measurement.class_name is None and measurement.class_confidence is None
                assert measurement.t_s <= v.t_s + 1e-9

    def test_suite_builder_and_legacy_tracker_compat(self) -> None:
        config = Config.from_dict(
            [
                {
                    "radar_x": {
                        "range_scale_nm": 3.0,
                        "rpm": 24.0,
                        "antenna_height_m": 12.0,
                        "vbw_deg": 25.0,
                        "sigma_range_m": 8.0,
                        "sigma_azimuth_rad": math.radians(1.0),
                        "clutter_rate_per_m2": 5e-7,
                        "sea_state_beaufort": 3.0,
                        "blind_sectors_deg": [[0.0, 0.0]],
                    }
                }
            ]
        )
        sensors = SensorSuiteBuilder.construct_sensors(config)
        assert [sensor.type for sensor in sensors] == ["radar_x"]
        assert isinstance(sensors[0], RadarXBand)
        sensor = sensors[0]
        sensor.reset(seed=5)
        tracker = KF(sensor_list=sensors, params=KFParams())
        target = static_target(0, 2000.0, 300.0, length=30.0, width=8.0)
        own = ownship_at()
        updates = 0
        for k in range(1, 120):
            t = k * 0.5
            tracks, measurements = tracker.track(t, 0.5, [target], own)
            for _do_idx, z in measurements[0]:
                assert len(z) == 2, "legacy ISensor shape must stay 2-D NE for the tracker"
            updates += sum(1 for _do_idx, z in measurements[0] if not np.any(np.isnan(z)))
        assert updates >= 15, "KF must receive regular radar_x updates through the beam-crossing stream"
        round_trip = config.to_dict_list()
        assert round_trip[0]["radar_x"]["range_scale_nm"] == 3.0
        rebuilt = Config.from_dict(round_trip)
        assert rebuilt.sensor_list[0].range_scale_nm == 3.0

    def test_legacy_radar_class_untouched(self) -> None:
        from colav_simulator.core.sensing import Radar, RadarParams  # noqa: PLC0415

        radar = Radar(RadarParams())
        radar.reset(seed=1)
        measurements = radar.generate_measurements(0.4, [static_target(0, 500.0, 0.0)], ownship_at())
        assert len(measurements) == 1  # rate-gated placeholder, legacy behavior unchanged
