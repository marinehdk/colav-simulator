"""dt-sensor-overlay (2026-10-11 contract §2/§8): projection ``observations`` tests.

Synthetic observations-v1 frames are ingested through ``WebSessionManager.
ingest_observations`` (the georeferencing production path) and the resulting
WS projection payload (``_telemetry`` output via ``_publish_telemetry``) is
asserted against the frozen contract:

- the top-level ``observations`` array exists (empty for sessions without
  camera observations) and survives the compact stream transport;
- entries carry local-frame NE in the same domain as ``tracks.states``;
- ``track_key`` matches the web ``scene-geography.js targetKey`` spelling
  character-for-character (``run_id:label:generation``, missing generation →
  ``none``, generation ``0`` → ``"0"``);
- the 5 s age window (4.9 kept / 5.1 dropped) and the 50 m display-only
  association gate hold;
- box dimensions come from the associated label's truth ship, else the
  class default (12 x 5 for boat and unknown classes alike).
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

import gui_server.main as gui_main
from colav_simulator.core.mast_cameras import (
    CLASS_HEIGHT_PRIOR_M,
    DEFAULT_HEIGHT_PRIOR_M,
    MAST_MOUNTS_BY_ID,
    focal_px,
)
from colav_simulator.experiment.contracts import SessionState

ORIGIN_E, ORIGIN_N = 40500.0, 6958000.0
OWN_N, OWN_E, OWN_YAW = ORIGIN_N + 100.0, ORIGIN_E + 50.0, 0.0
RUN_ID = "run-obs"
MOUNT = MAST_MOUNTS_BY_ID["mast_ptz_eo"]

# Track table (absolute NE estimates; _local_tracks projects to the local frame).
# All three bearings sit inside the PTZ's ±30 deg pinhole cone so the synthetic
# boxes keep non-negative pixel coordinates.
TRACK_5 = (ORIGIN_N + 400.0, ORIGIN_E + 30.0)      # label 5, generation 0
TRACK_7 = (ORIGIN_N + 460.0, ORIGIN_E - 140.0)     # label 7, generation 1
TRACK_9 = (ORIGIN_N + 700.0, ORIGIN_E - 270.0)     # label 9, generation missing


def pixel_box_for(north_abs: float, east_abs: float, *, class_name: str = "boat") -> list[float]:
    """Inverse pinhole: absolute NE -> a pixel box that georeferences back to it.

    Mirrors georeference_box exactly (bearing through the box-centre column,
    range from the class height prior), so the georef round-trip is exact up to
    float precision for positions inside the range clamps.
    """
    height_prior = CLASS_HEIGHT_PRIOR_M.get(class_name, DEFAULT_HEIGHT_PRIOR_M)
    fx = focal_px(MOUNT.hfov_deg, MOUNT.frame_width_px)
    north_rel = north_abs - OWN_N
    east_rel = east_abs - OWN_E
    range_m = math.hypot(north_rel, east_rel)
    bearing_body = math.atan2(east_rel, north_rel) - OWN_YAW - math.radians(MOUNT.azimuth_deg)
    u_center = MOUNT.frame_width_px / 2.0 + fx * math.tan(bearing_body)
    height_px = fx * height_prior / range_m
    return [u_center - 20.0, 240.0 - height_px / 2.0, u_center + 20.0, 240.0 + height_px / 2.0]


def make_manager(t: float = 42.0) -> gui_main.WebSessionManager:
    ship0_raw = {
        "id": 0,
        "mmsi": 111111111,
        "state": [OWN_N, OWN_E, OWN_YAW, 3.0, 0.0, 0.0],
        "csog_state": [OWN_N, OWN_E, 3.0, 0.0],
        "waypoints": np.zeros((2, 0)),
        "active": True,
        "do_labels": [5, 7, 9],
        "do_generations": [0, 1],  # index 2 missing -> None -> literal "none"
        "do_estimates": [
            [TRACK_5[0], TRACK_5[1], 0.0, 0.0],
            [TRACK_7[0], TRACK_7[1], 0.0, 0.0],
            [TRACK_9[0], TRACK_9[1], 0.0, 0.0],
        ],
        "do_existence_probabilities": [0.87, 0.61, 0.55],
    }
    # Truth obstacle for label 5 only: label 7/9 associations fall back to the
    # class default dimensions.
    ship1_raw = {
        "id": 5,
        "mmsi": 222222222,
        "state": [TRACK_5[0], TRACK_5[1], 0.0, 2.0, 0.0, 0.0],
        "csog_state": [0.0, 0.0, 2.0, 0.0],
        "active": True,
    }
    session = SimpleNamespace(
        ship_list=[
            SimpleNamespace(
                id=0,
                length=20.0,
                width=6.0,
                state=np.array([OWN_N, OWN_E, OWN_YAW, 0.0, 0.0, 0.0]),
                csog_state=np.array([0.0, 0.0, 3.0, 0.0]),
                waypoints=np.zeros((2, 0)),
            ),
            SimpleNamespace(
                id=5,
                length=50.0,
                width=12.0,
                csog_state=np.array([0.0, 0.0, 2.0, 0.0]),
                waypoints=np.zeros((2, 0)),
            ),
        ],
        last_frame={"Ship0": ship0_raw, "Ship1": ship1_raw},
        enc=SimpleNamespace(origin=(ORIGIN_E, ORIGIN_N), utm_zone=32, seabed={}),
        state=SessionState.RUNNING,
        simulator=SimpleNamespace(t=t, t_end=100.0),
        sequence=7,
        operational_events=[],
        failure_reason=None,
        baseline_threat_failure_reason=None,
    )
    manager = gui_main.WebSessionManager()
    manager.prepared = SimpleNamespace(
        session=session,
        manifest=SimpleNamespace(
            run_id=RUN_ID,
            executed_algorithm="vo",
            requested_algorithm="vo",
            requested_tracker="vimmjipda",
            executed_tracker="vimmjipda",
        ),
        spec=SimpleNamespace(
            scenario_id="head_on",
            validation_rule_id="rule14",
            historical_replay=None,
            environment_settings=None,
        ),
    )
    return manager


def ingest_frame(manager: gui_main.WebSessionManager, *, frame_seq: int, detections: list[dict]) -> None:
    manager.ingest_observations(
        RUN_ID,
        gui_main.ObservationFrame(
            **{
                "schema_version": "observations@1",
                "frame_seq": frame_seq,
                "frame_time_s": float(frame_seq) / 10.0,
                "sensor_id": 2,
                "mount_id": MOUNT.mount_id,
                "source": "yolo-detector",
                "detections": detections,
            }
        ),
    )


def publish(manager: gui_main.WebSessionManager) -> dict:
    manager._publish_telemetry(None)
    return manager.latest


def test_projection_observations_association_domain_and_key_spelling() -> None:
    manager = make_manager(t=42.0)
    ingest_frame(
        manager,
        frame_seq=41,
        detections=[
            # det 0: dead on track 5 (label 5, generation 0, truth ship exists).
            {"box_xyxy": pixel_box_for(*TRACK_5), "class_id": 8, "class_name": "boat", "confidence": 0.87},
            # det 1: dead on track 7 (label 7 -> no truth ship -> class default size).
            {"box_xyxy": pixel_box_for(*TRACK_7), "class_id": 8, "class_name": "boat", "confidence": 0.61},
            # det 2: dead on track 9 (generation missing -> literal "none").
            {"box_xyxy": pixel_box_for(*TRACK_9, class_name="sailboat"), "class_id": 7,
             "class_name": "sailboat", "confidence": 0.55},
            # det 3: far from every track -> no association.
            {"box_xyxy": pixel_box_for(ORIGIN_N + 1600.0, ORIGIN_E + 800.0), "class_id": 8,
             "class_name": "boat", "confidence": 0.9},
        ],
    )
    manager.prepared.session.simulator.t = 42.5
    latest = publish(manager)

    observations = latest["observations"]
    assert len(observations) == 4
    assert [entry["det_id"] for entry in observations] == ["2:41:0", "2:41:1", "2:41:2", "2:41:3"]

    states = latest["truth"][0]["tracks"]["states"]
    near, mid, far = observations[0], observations[1], observations[3]

    # Local-frame domain: observations share the states[] frame (origin-subtracted).
    assert near["north"] == pytest.approx(states[0][0])
    assert near["east"] == pytest.approx(states[0][1])
    assert near["north"] == pytest.approx(TRACK_5[0] - ORIGIN_N)
    assert near["east"] == pytest.approx(TRACK_5[1] - ORIGIN_E)

    # Contract §1 key spelling: run_id:label:generation, 0 stays "0" (no truthiness).
    assert near["track_key"] == f"{RUN_ID}:5:0"
    assert mid["track_key"] == f"{RUN_ID}:7:1"
    assert observations[2]["track_key"] == f"{RUN_ID}:9:none"
    assert far["track_key"] == ""

    # Contract §2.3 dimensions: associated label hits truth -> truth size (50x12);
    # label miss or no association -> class default 12x5.
    assert (near["length_m"], near["width_m"]) == pytest.approx((50.0, 12.0))
    assert (mid["length_m"], mid["width_m"]) == pytest.approx((12.0, 5.0))
    assert (far["length_m"], far["width_m"]) == pytest.approx((12.0, 5.0))

    assert near["confidence"] == pytest.approx(0.87)
    assert near["class_name"] == "boat"
    assert near["sensor_id"] == 2
    assert near["age_s"] == pytest.approx(0.5)


def test_projection_observations_association_gate_is_50m() -> None:
    manager = make_manager(t=42.0)
    ingest_frame(
        manager,
        frame_seq=41,
        detections=[
            # 45 m off track 5 along north -> inside the display gate.
            {"box_xyxy": pixel_box_for(TRACK_5[0] + 45.0, TRACK_5[1]), "class_id": 8,
             "class_name": "boat", "confidence": 0.8},
            # 60 m off -> outside the gate, empty key.
            {"box_xyxy": pixel_box_for(TRACK_5[0] + 60.0, TRACK_5[1]), "class_id": 8,
             "class_name": "boat", "confidence": 0.8},
        ],
    )
    observations = publish(manager)["observations"]
    assert len(observations) == 2
    assert observations[0]["track_key"] == f"{RUN_ID}:5:0"
    assert observations[1]["track_key"] == ""


def test_projection_observations_age_window_boundary() -> None:
    manager = make_manager(t=42.0)
    ingest_frame(
        manager,
        frame_seq=41,
        detections=[{"box_xyxy": pixel_box_for(*TRACK_5), "class_id": 8, "class_name": "boat", "confidence": 0.87}],
    )
    manager.prepared.session.simulator.t = 46.9  # age 4.9 s -> kept
    kept = publish(manager)["observations"]
    assert len(kept) == 1
    assert kept[0]["age_s"] == pytest.approx(4.9)
    manager.prepared.session.simulator.t = 47.1  # age 5.1 s -> dropped
    assert publish(manager)["observations"] == []


def test_projection_observations_key_survives_compact_transport() -> None:
    manager = make_manager(t=42.0)
    ingest_frame(
        manager,
        frame_seq=41,
        detections=[{"box_xyxy": pixel_box_for(*TRACK_5), "class_id": 8, "class_name": "boat", "confidence": 0.87}],
    )
    latest = publish(manager)
    for include_static in (True, False):
        compact = gui_main._compact_stream_payload(latest, include_static=include_static)
        assert compact["observations"] == latest["observations"]


def test_projection_without_camera_observations_is_empty_array() -> None:
    latest = publish(make_manager(t=42.0))
    assert latest["observations"] == []
