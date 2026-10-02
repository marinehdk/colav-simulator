"""P3-S2 observations endpoint + mast camera calibration tests (spec #90).

Covers (contract sango/Docs/contracts/observations-v1.md, frozen):
- the backend-authoritative mast mount calibration table (milliampere-ch5 §4.2
  anchors; the Unity rig table mirrors these literals);
- the pixel-box georef numeric chain (bearing, box-height ranging, radial
  covariance) with synthetic intrinsics and known ownship poses;
- the endpoint gates (404 / 409 SESSION_NOT_ACCEPTING / 409 FRAME_SEQ_REGRESSION
  / 422) over the FastAPI layer with the session manager replaced by a fake;
- the ExternalCameraSensor measurement-cache integration (KF tracker consuming
  external records must not explode; sensor-model-v1 shaped records carry the
  sensor_id 2|3 vocabulary).
"""

from __future__ import annotations

import math
import threading
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.core.mast_cameras import (
    FEED_MOUNT_ID,
    MAST_MOUNTS,
    MAST_MOUNTS_BY_ID,
    SENSOR_ID_EO,
    SENSOR_ID_IR,
    SENSOR_ID_LIDAR,
    focal_px,
    georeference_box,
)
from colav_simulator.core.sensing import ExternalCameraSensor
from colav_simulator.core.tracking.trackers import KF, KFParams
from colav_simulator.experiment.contracts import SessionState
from colav_simulator.schemas.observations_v1 import ObservationFrame

FRAME_SAMPLE = {
    "schema_version": "observations@1",
    "frame_seq": 41,
    "frame_time_s": 12.402,
    "sensor_id": 2,
    "mount_id": "mast_ptz_eo",
    "source": "yolo-detector",
    "detections": [
        {"box_xyxy": [100.0, 120.0, 340.0, 260.0], "class_id": 8, "class_name": "boat", "confidence": 0.87}
    ],
}


def make_frame(**overrides) -> ObservationFrame:
    return ObservationFrame(**{**FRAME_SAMPLE, **overrides})


def fake_manager(state: SessionState = SessionState.CREATED) -> SimpleNamespace:
    manager = gui_main.WebSessionManager.__new__(gui_main.WebSessionManager)
    manager.lock = threading.RLock()
    manager.observation_sensor = None
    manager._observation_seq_gate = {}
    manager._observation_totals = {}
    session = SimpleNamespace(
        state=state,
        ship_list=[SimpleNamespace(state=np.array([6955000.0, 37000.0, math.pi / 2, 0.0, 0.0, 0.0]))],
        simulator=SimpleNamespace(t=12.4),
    )
    manager.prepared = SimpleNamespace(session=session, manifest=SimpleNamespace(run_id="s1"))
    return manager


# ── calibration table (backend-authoritative; Unity MastCameraTable mirrors) ──


class TestMastMountTable:
    def test_family_counts_match_the_task_layout(self) -> None:
        eo_ring = [m for m in MAST_MOUNTS if m.sensor_id == SENSOR_ID_EO and not m.mount_id.startswith("mast_ptz")]
        ir_ring = [m for m in MAST_MOUNTS if m.sensor_id == SENSOR_ID_IR and not m.mount_id.startswith("mast_ptz")]
        ptz = [m for m in MAST_MOUNTS if m.mount_id.startswith("mast_ptz")]
        lidar = [m for m in MAST_MOUNTS if m.sensor_id == SENSOR_ID_LIDAR]
        assert len(eo_ring) == 5, "EO ring is 5 fixed cameras"
        assert len(ir_ring) == 4, "IR ring is 4 fixed cameras"
        assert len(ptz) == 2, "dual-spectrum PTZ = white + LWIR channel mounts"
        assert len(lidar) == 1, "LiDAR depth camera row (P3-S3 point-cloud view / contact model)"

    def test_mount_ids_unique_and_contract_vocabulary(self) -> None:
        ids = [m.mount_id for m in MAST_MOUNTS]
        assert len(ids) == len(set(ids))
        assert "mast_ir_bow" in ids, "contract observations-v1 §3 sample vocabulary"
        assert FEED_MOUNT_ID in ids
        assert "mast_lidar" in ids, "sensor-model-v1 §3 mount vocabulary (P3-S3)"

    def test_ring_layout_matches_task_azimuths(self) -> None:
        azimuths = {m.mount_id: m.azimuth_deg for m in MAST_MOUNTS}
        assert azimuths["mast_eo_bow_stbd"] == 60.0
        assert azimuths["mast_eo_bow_port"] == 300.0
        assert azimuths["mast_eo_stbd"] == 90.0
        assert azimuths["mast_eo_port"] == 270.0
        assert azimuths["mast_eo_quarter"] == 180.0
        assert azimuths["mast_ir_bow"] == 0.0
        assert azimuths["mast_ptz_eo"] == 0.0, "PTZ white channel is the forward EO role"
        assert azimuths["mast_lidar"] == 0.0, "LiDAR flange on the mast centreline (milliampere §4.2)"

    def test_heights_anchor_on_fbx_mast_measurements(self) -> None:
        for mount in MAST_MOUNTS:
            if mount.mount_id.startswith("mast_ptz"):
                assert mount.height_m == pytest.approx(11.5)
                assert mount.forward_offset_m == pytest.approx(2.5)
                assert mount.pitch_deg == pytest.approx(0.0)
            elif mount.sensor_id == SENSOR_ID_LIDAR:
                assert mount.height_m == pytest.approx(11.0), "mast-top flange 11 m (milliampere §4.2 LiDAR row)"
                assert mount.forward_offset_m == pytest.approx(2.1), "mast centreline +2.1 m"
                assert mount.pitch_deg == pytest.approx(-10.0), "install downtilt (Unity table mirrors)"
            else:
                assert mount.height_m == pytest.approx(10.5), "mast rail ring (milliampere §4.2)"
                assert mount.forward_offset_m == pytest.approx(2.1), "FBX mast at +2.1 m"
                assert mount.pitch_deg == pytest.approx(0.0)

    def test_lidar_row_is_the_bypass_depth_camera(self) -> None:
        """P3-S3: pixel intrinsics = the Unity depth-capture pinhole (90x32 deg)."""
        mount = MAST_MOUNTS_BY_ID["mast_lidar"]
        assert mount.channel == "lidar"
        assert mount.sensor_id == 4
        assert mount.hfov_deg == 90.0
        assert mount.reference_width_px == 640 and mount.reference_height_px == 184
        expected_aspect = math.tan(math.radians(45.0)) / math.tan(math.radians(16.0))
        assert mount.reference_width_px / mount.reference_height_px == pytest.approx(expected_aspect, rel=0.01)
        assert mount.fx_reference_px == pytest.approx(focal_px(90.0, 640))

    def test_feed_mount_publishes_640x480(self) -> None:
        feed = MAST_MOUNTS_BY_ID[FEED_MOUNT_ID]
        assert feed.frame_width_px == 640 and feed.frame_height_px == 480
        assert feed.hfov_deg == 60.0

    def test_sensor_ids_restricted_to_contract_vocabulary(self) -> None:
        assert {m.sensor_id for m in MAST_MOUNTS} == {SENSOR_ID_EO, SENSOR_ID_IR, SENSOR_ID_LIDAR}

    def test_eo_ring_dead_ahead_sector_is_the_ptz_role(self) -> None:
        """Documented S2 deviation: with 90 deg HFOV the EO ring covers 15-345 deg.

        The forward 30 deg sector belongs to the PTZ (milliAmpere rationale).
        """
        for mount in MAST_MOUNTS:
            if mount.sensor_id == SENSOR_ID_EO and not mount.mount_id.startswith("mast_ptz"):
                half = mount.hfov_deg / 2.0
                lo = (mount.azimuth_deg - half) % 360.0
                hi = (mount.azimuth_deg + half) % 360.0
                if lo < hi:
                    assert not (lo <= 0.0 <= hi), "no ring camera may own dead ahead (PTZ role)"


# ── georef numeric chain ──────────────────────────────────────────────────────


class TestGeoref:
    def test_centered_box_bears_down_the_mount_axis(self) -> None:
        mount = MAST_MOUNTS_BY_ID["mast_ptz_eo"]
        width = mount.frame_width_px
        box = (width / 2 - 40.0, 200.0, width / 2 + 40.0, 280.0)
        georef = georeference_box(mount, box, width, 480, 0.0, 0.0, own_yaw_rad=0.0, class_name="boat")
        assert georef.east_m == pytest.approx(0.0, abs=1e-9)
        assert georef.north_m > 0.0
        fx = focal_px(mount.hfov_deg, width)
        assert georef.range_m == pytest.approx(fx * 2.5 / 80.0), "range = fx * prior / box height"

    def test_ownship_yaw_rotates_the_bearing(self) -> None:
        mount = MAST_MOUNTS_BY_ID["mast_ptz_eo"]
        width = mount.frame_width_px
        box = (width / 2 - 40.0, 200.0, width / 2 + 40.0, 280.0)
        georef = georeference_box(mount, box, width, 480, 10.0, 20.0, own_yaw_rad=math.pi / 2, class_name="boat")
        assert georef.east_m == pytest.approx(20.0 + georef.range_m, abs=1e-6)
        assert georef.north_m == pytest.approx(10.0, abs=1e-6)

    def test_off_center_box_bearing_offset(self) -> None:
        mount = MAST_MOUNTS_BY_ID["mast_ptz_eo"]
        width = mount.frame_width_px
        offset_px = 100.0
        box = (width / 2 + offset_px - 40.0, 200.0, width / 2 + offset_px + 40.0, 280.0)
        georef = georeference_box(mount, box, width, 480, 0.0, 0.0, own_yaw_rad=0.0, class_name="boat")
        fx = focal_px(mount.hfov_deg, width)
        assert georef.bearing_rad == pytest.approx(math.atan(offset_px / fx), abs=1e-9)

    def test_covariance_is_radially_elongated_along_the_bearing(self) -> None:
        mount = MAST_MOUNTS_BY_ID["mast_ptz_eo"]
        width = mount.frame_width_px
        box = (width / 2 - 40.0, 200.0, width / 2 + 40.0, 280.0)
        georef = georeference_box(mount, box, width, 480, 0.0, 0.0, own_yaw_rad=0.0, class_name="boat")
        cov = np.array(georef.cov_ne_m2)
        assert cov[0][0] > 1.5 * cov[1][1], "radial variance > cross variance along bearing 0 (contract §3 E5 form)"

    def test_range_clamps(self) -> None:
        mount = MAST_MOUNTS_BY_ID["mast_ptz_eo"]
        width = mount.frame_width_px
        tiny_box = (width / 2 - 1.0, 10.0, width / 2 + 1.0, 12.0)
        georef = georeference_box(mount, tiny_box, width, 480, 0.0, 0.0, own_yaw_rad=0.0, class_name="boat")
        assert georef.range_m <= 2.0 * 1852.0
        huge_box = (0.0, 0.0, float(width), 479.0)
        near = georeference_box(mount, huge_box, width, 480, 0.0, 0.0, own_yaw_rad=0.0, class_name="boat")
        assert near.range_m >= 5.0


# ── endpoint HTTP layer ───────────────────────────────────────────────────────


@pytest.fixture()
def client(monkeypatch) -> tuple[TestClient, SimpleNamespace]:
    manager = fake_manager()
    monkeypatch.setattr(gui_main, "manager", manager)
    return TestClient(gui_main.app), manager


class TestObservationsEndpoint:
    def test_unknown_session_is_404(self, client) -> None:
        http, _manager = client
        response = http.post("/api/sessions/does-not-exist/observations", json=FRAME_SAMPLE)
        assert response.status_code == 404
        assert response.json()["detail"] == "SESSION_NOT_FOUND"

    def test_created_session_accepts_and_echoes_contract_response(self, client) -> None:
        http, manager = client
        response = http.post("/api/sessions/s1/observations", json=FRAME_SAMPLE)
        assert response.status_code == 200
        assert response.json() == {"accepted": True, "frame_seq": 41, "detections_accepted": 1}
        assert manager.observation_sensor is not None

    def test_empty_detections_is_an_authoritative_no_seeing(self, client) -> None:
        http, _manager = client
        body = {**FRAME_SAMPLE, "detections": []}
        response = http.post("/api/sessions/s1/observations", json=body)
        assert response.status_code == 200
        assert response.json()["detections_accepted"] == 0

    def test_frame_seq_regression_is_409(self, client) -> None:
        http, _manager = client
        first = http.post("/api/sessions/s1/observations", json=FRAME_SAMPLE)
        assert first.status_code == 200
        repeat = http.post("/api/sessions/s1/observations", json=FRAME_SAMPLE)
        assert repeat.status_code == 409
        assert repeat.json()["detail"] == "FRAME_SEQ_REGRESSION"
        backwards = http.post("/api/sessions/s1/observations", json={**FRAME_SAMPLE, "frame_seq": 40})
        assert backwards.status_code == 409

    def test_sequence_gate_is_per_sensor_and_mount(self, client) -> None:
        http, _manager = client
        assert http.post("/api/sessions/s1/observations", json=FRAME_SAMPLE).status_code == 200
        ir_frame = {**FRAME_SAMPLE, "sensor_id": 3, "mount_id": "mast_ir_bow", "frame_seq": 1}
        assert http.post("/api/sessions/s1/observations", json=ir_frame).status_code == 200
        assert http.post("/api/sessions/s1/observations", json=ir_frame).status_code == 409

    def test_paused_session_is_409_not_accepting(self, client) -> None:
        http, manager = client
        manager.prepared.session.state = SessionState.PAUSED
        response = http.post("/api/sessions/s1/observations", json=FRAME_SAMPLE)
        assert response.status_code == 409
        assert response.json()["detail"] == "SESSION_NOT_ACCEPTING"

    def test_unknown_mount_id_is_422(self, client) -> None:
        http, _manager = client
        body = {**FRAME_SAMPLE, "mount_id": "mast_nonexistent", "frame_seq": 5}
        response = http.post("/api/sessions/s1/observations", json=body)
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "mutate",
        [
            {"schema_version": "observations@2"},
            {"frame_seq": -1},
            {"sensor_id": 1},  # radar never rides this endpoint (contract §1/§2)
            {"extra_key": True},  # extra=forbid
            {"mount_id": ""},
        ],
    )
    def test_schema_violations_are_422(self, client, mutate: dict) -> None:
        http, _manager = client
        response = http.post("/api/sessions/s1/observations", json={**FRAME_SAMPLE, **mutate})
        assert response.status_code == 422

    def test_degenerate_and_negative_boxes_are_422(self, client) -> None:
        http, _manager = client
        bad_box = {"box_xyxy": [10.0, 10.0, 10.0, 20.0], "class_id": 8, "class_name": "boat", "confidence": 0.5}
        bad_zero_area = {**FRAME_SAMPLE, "detections": [bad_box]}
        assert http.post("/api/sessions/s1/observations", json=bad_zero_area).status_code == 422
        bad_negative = {**FRAME_SAMPLE, "detections": [{**bad_box, "box_xyxy": [-10.0, 10.0, 30.0, 20.0]}]}
        assert http.post("/api/sessions/s1/observations", json=bad_negative).status_code == 422

    def test_status_hook_reports_channel_counters_and_sensor_id(self, client) -> None:
        http, _manager = client
        assert http.post("/api/sessions/s1/observations", json=FRAME_SAMPLE).status_code == 200
        status = http.get("/api/sessions/s1/observations")
        assert status.status_code == 200
        document = status.json()
        assert document["accepted_frames_total"] == 1
        assert document["channels"] == [
            {"sensor_id": 2, "mount_id": "mast_ptz_eo", "frames": 1, "detections": 1, "last_frame_seq": 41}
        ]
        pending = document["pending_measurements"]
        assert len(pending) == 1
        assert pending[0]["sensor_id"] == 2, "E2E assertion key: the measurement cache carries sensor_id"
        assert pending[0]["mount_id"] == "mast_ptz_eo"

    def test_status_hook_404(self, client) -> None:
        http, _manager = client
        assert http.get("/api/sessions/nope/observations").status_code == 404


# ── measurement cache integration (KF tracker + external records) ─────────────


class TestExternalCameraSensorCache:
    def test_kf_tracker_consumes_external_measurements_without_exploding(self) -> None:
        sensor = ExternalCameraSensor()
        tracker = KF(sensor_list=[sensor], params=KFParams())
        target = (0, np.array([500.0, 120.0, 0.0, 0.0]), 20.0, 6.0)
        own = np.array([0.0, 0.0, 5.0, 0.0])
        sensor.submit(
            [
                {
                    "position_ne_m": [500.0, 120.0],
                    "position_cov_ne_m2": [[36.0, 0.0], [0.0, 121.0]],
                    "confidence": 0.8,
                    "class_name": "boat",
                    "t_s": 0.5,
                }
            ],
            frame_seq=1,
        )
        tracks, measurements = tracker.track(0.5, 0.5, [target], own)
        assert tracks is not None
        external = measurements[0]
        assert any(do_idx == -1 for do_idx, _z in external), "external records ride the clutter do_idx slot"
        assert any(not np.isnan(z).any() for _do_idx, z in external)
        # Drain repeats must not raise on an empty inbox.
        for k in range(1, 4):
            tracker.track(0.5 + k * 0.5, 0.5, [target], own)
        assert not sensor.pending_records(), "the tracker drain empties the cache"

    def test_sensor_id_vocabulary_and_sfd_shape(self) -> None:
        eo = ExternalCameraSensor()
        assert eo.type == "camera_eo"
        ir = ExternalCameraSensor(params=__import__(
            "colav_simulator.core.sensing", fromlist=["ExternalCameraParams"]
        ).ExternalCameraParams(sensor_id=3))
        assert ir.type == "camera_ir"
        eo.submit(
            [{"position_ne_m": [10.0, -5.0], "position_cov_ne_m2": [[36.0, 0.0], [0.0, 121.0]],
              "confidence": 0.7, "class_name": "boat", "t_s": 2.0}],
            frame_seq=9,
        )
        frame = eo.sfd_records(t_s=2.5, ownship_pose={"p_n": 0.0, "p_e": 0.0, "yaw": 0.0, "pitch": 0.0, "roll": 0.0})
        assert frame["sensor_id"] == 2 and frame["sensor_label"] == "camera_eo"
        assert frame["measurements"][0]["confidence"] == pytest.approx(0.7)
        assert frame["measurements"][0]["position_ne_m"] == [10.0, -5.0]
        assert ir.sfd_records(t_s=0.0)["measurements"] == []
