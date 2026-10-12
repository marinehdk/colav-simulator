"""dt-sensor-overlay (2026-10-11 contract §8): end-to-end data-chain acceptance.

One RUNNING IPDA session drives the full display pipeline over real
infrastructure, in three links:

1. synthetic YOLO detections ride the observations-v1 HTTP route (pydantic
   body model -> ``georeference_box`` -> display ring cache);
2. the WS projection stream (``/ws/sessions/{id}``, default and compact-v1
   transports) carries the contract §2 ``observations`` array in the local NE
   domain shared with ``tracks[0].states``, with the §1 ``track_key`` spelling;
3. the web layer ``buildTwinPresentation`` (``web_gui/modules/twin-situation.js``)
   consumes the exact WS payload plus real ``/api/enc_info`` output inside a
   node subprocess (the repo web-test import style), proving the B-section
   mapping: ``existence`` on targets, the A->B detection field rename, and the
   cross-layer agreement that the Python ``track_key`` equals the JS
   ``targetKey`` for the same target (the right-click per-target switch keys
   off this equality).

Unity-side JsonUtility compatibility of the B/C messages is owned by the
EditMode suite (``sango/Assets/Scripts/Tests/EditMode/TwinSituationTests.cs``);
this file stops at the browser boundary.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.core.mast_cameras import (
    CLASS_HEIGHT_PRIOR_M,
    DEFAULT_HEIGHT_PRIOR_M,
    MAST_MOUNTS_BY_ID,
    focal_px,
)
from colav_simulator.experiment.contracts import SessionState

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "run-e2e"
ORIGIN_E, ORIGIN_N = 40500.0, 6958000.0
OWN_N, OWN_E, OWN_YAW = ORIGIN_N + 100.0, ORIGIN_E + 50.0, 0.0
MOUNT = MAST_MOUNTS_BY_ID["mast_ptz_eo"]
EXISTENCE = [0.87, 0.61, 0.55]

# Track table (absolute NE estimates; _local_tracks projects to the local
# frame). All bearings sit inside the PTZ's +-30 deg pinhole cone so the
# synthetic pixel boxes keep non-negative, non-degenerate coordinates.
TRACK_5 = (ORIGIN_N + 400.0, ORIGIN_E + 30.0)   # label 5, generation 0 (truth ship -> 50x12)
TRACK_7 = (ORIGIN_N + 460.0, ORIGIN_E - 140.0)  # label 7, generation 1 (no detection this frame)
TRACK_9 = (ORIGIN_N + 700.0, ORIGIN_E - 270.0)  # label 9, generation missing -> literal "none"
FAR_POINT = (ORIGIN_N + 1600.0, ORIGIN_E + 800.0)  # beyond the 50 m display gate -> track_key ""


def pixel_box_for(north_abs: float, east_abs: float, *, class_name: str = "boat") -> list[float]:
    """Inverse pinhole: absolute NE -> a pixel box that georeferences back to it."""
    height_prior = CLASS_HEIGHT_PRIOR_M.get(class_name, DEFAULT_HEIGHT_PRIOR_M)
    fx = focal_px(MOUNT.hfov_deg, MOUNT.frame_width_px)
    north_rel, east_rel = north_abs - OWN_N, east_abs - OWN_E
    range_m = math.hypot(north_rel, east_rel)
    bearing_body = math.atan2(east_rel, north_rel) - OWN_YAW - math.radians(MOUNT.azimuth_deg)
    u_center = MOUNT.frame_width_px / 2.0 + fx * math.tan(bearing_body)
    height_px = fx * height_prior / range_m
    return [u_center - 20.0, 240.0 - height_px / 2.0, u_center + 20.0, 240.0 + height_px / 2.0]


def make_manager(t: float = 42.0) -> gui_main.WebSessionManager:
    """RUNNING vimmjipda session with three IPDA tracks and one truth obstacle."""
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
        "do_existence_probabilities": EXISTENCE,
    }
    ship1_raw = {  # truth obstacle for label 5 only -> truth dimensions on that association
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
        enc=SimpleNamespace(origin=(ORIGIN_E, ORIGIN_N), utm_zone=32, seabed={}, size=(20000.0, 20000.0)),
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


# Node bridge: imports buildTwinPresentation exactly like the repo web tests
# (query-suffixed module specifier) and prints a JSON summary for pytest to
# assert against the payload that produced it.
BRIDGE_SOURCE = """\
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';

const [, , payloadPath, infoPath, modulePath] = process.argv;
const payload = JSON.parse(fs.readFileSync(payloadPath, 'utf8'));
const info = JSON.parse(fs.readFileSync(infoPath, 'utf8'));
const { buildTwinPresentation } = await import(pathToFileURL(modulePath).href + '?v=20261011-dt-sensor-overlay-v1');

const route = () => [[0, 1000], [0, 0]];
const layerOn = buildTwinPresentation(
  { raw: payload },
  { getMissionRoute: route, getLayerState: () => ({ detections: { visible: true } }) },
  info,
);
const toggled = new Set([payload.observations[0].track_key]);
const layerOff = buildTwinPresentation(
  { raw: payload },
  { getMissionRoute: route, getLayerState: () => ({}) },
  info, null, null, toggled,
);
if (!layerOn || !layerOff) {
  console.error('buildTwinPresentation returned null (run_id mismatch)');
  process.exit(1);
}
console.log(JSON.stringify({
  run_id: layerOn.run_id,
  targets: layerOn.targets.map(target => ({
    id: target.id, key: target.key, existence: target.existence, truth: target.truth,
    east: target.east, north: target.north, length: target.length, width: target.width,
  })),
  detections: layerOn.detections,
  layerOffDetectionKeys: layerOff.detections.map(detection => detection.key),
}));
"""


def _node_binary() -> str:
    """A node new enough for the repo's query-specifier ESM web modules.

    The web suite (``node --test tests/web_gui/*.test.mjs``) imports
    ``web_gui/modules/*.js`` through ``?v=...`` specifiers, which relies on
    Node's ESM syntax detection for .js files without a package.json (default
    since Node 22). PATH order alone is not trustworthy on this dev box: a
    legacy v16 ``/usr/local/bin/node`` shadows the nvm install under
    ``bash -lc``, so the newest nvm install is the fallback candidate.
    """
    candidates = [shutil.which("node")]
    nvm_root = Path.home() / ".nvm" / "versions" / "node"
    candidates += sorted(nvm_root.glob("v*/bin/node"), reverse=True, key=lambda path: tuple(
        int(part) for part in re.findall(r"\d+", path.parent.name)
    ))
    for candidate in candidates:
        if not candidate:
            continue
        probed = subprocess.run(
            [str(candidate), "--version"], capture_output=True, text=True, timeout=30, close_fds=False, check=False
        )
        major = re.match(r"v(\d+)\.", probed.stdout.strip() or "")
        if probed.returncode == 0 and major and int(major.group(1)) >= 22:
            return str(candidate)
    pytest.fail("node >= 22 is required (same dependency as tests/web_gui/*.test.mjs); none found on PATH or under ~/.nvm")


def run_node_bridge(tmp_path: Path, payload: dict, info: dict) -> dict:
    bridge_path = tmp_path / "dt_sensor_overlay_bridge.mjs"
    payload_path = tmp_path / "ws_payload.json"
    info_path = tmp_path / "enc_info.json"
    bridge_path.write_text(BRIDGE_SOURCE, encoding="utf-8")
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    info_path.write_text(json.dumps(info), encoding="utf-8")
    # After the TestClient websocket rounds the pytest process is multithreaded;
    # on macOS subprocess then forks and the forked child can segfault before
    # exec (crash reports show python3.11, not node). An absolute executable,
    # no cwd and close_fds=False keep subprocess on its posix_spawn path, which
    # never forks. Every path below is absolute, so no cwd is needed.
    node = _node_binary()
    completed = subprocess.run(
        [node, str(bridge_path), str(payload_path), str(info_path), str(REPO_ROOT / "web_gui" / "modules" / "twin-situation.js")],
        capture_output=True,
        text=True,
        timeout=120,
        close_fds=False,
        check=False,
    )
    assert completed.returncode == 0, f"node bridge failed:\n{completed.stderr}"
    return json.loads(completed.stdout)


def test_yolo_ingest_reaches_ws_projection_and_twin_presentation(monkeypatch, tmp_path) -> None:
    manager = make_manager(t=42.0)
    monkeypatch.setattr(gui_main, "manager", manager)
    # No lifespan context: keeps the app's background simulation loop away
    # from the synthetic session (test_observations_endpoint precedent).
    http = TestClient(gui_main.app)

    # ── link 1: observations-v1 injection over the real HTTP route ──
    frame = {
        "schema_version": "observations@1",
        "frame_seq": 41,
        "frame_time_s": 12.402,
        "sensor_id": 2,
        "mount_id": MOUNT.mount_id,
        "source": "yolo-detector",
        "detections": [
            # det 0: dead on track 5 (label 5, generation 0, truth ship exists).
            {"box_xyxy": pixel_box_for(*TRACK_5), "class_id": 8, "class_name": "boat", "confidence": 0.87},
            # det 1: dead on track 9 (generation missing -> "none"; sailboat -> class default size).
            {"box_xyxy": pixel_box_for(*TRACK_9, class_name="sailboat"), "class_id": 7,
             "class_name": "sailboat", "confidence": 0.55},
            # det 2: far from every track -> no association.
            {"box_xyxy": pixel_box_for(*FAR_POINT), "class_id": 8, "class_name": "boat", "confidence": 0.9},
        ],
    }
    accepted = http.post(f"/api/sessions/{RUN_ID}/observations", json=frame)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {"accepted": True, "frame_seq": 41, "detections_accepted": 3}

    # Sim clock moves on (age 0.5 s stays inside the contract §2.2 5 s window).
    manager.prepared.session.simulator.t = 42.5

    # ── link 2: WS projection payload ──
    with http.websocket_connect(f"/ws/sessions/{RUN_ID}") as websocket:
        payload = websocket.receive_json()
    assert "error" not in payload, payload
    assert payload["state"] == "RUNNING"
    assert payload["executed_tracker"] == "vimmjipda", "IPDA branch (not god) drives the display mapping"

    observations = payload["observations"]
    assert [entry["det_id"] for entry in observations] == ["2:41:0", "2:41:1", "2:41:2"]

    # Georef NE domain: same local frame as the web consumer's tracks[0].states
    # (situation-display targetsForDisplay reads data.tracks[0]).
    states = payload["tracks"][0]["states"]
    assert observations[0]["north"] == pytest.approx(states[0][0])
    assert observations[0]["east"] == pytest.approx(states[0][1])
    assert observations[0]["north"] == pytest.approx(TRACK_5[0] - ORIGIN_N)

    # Association keys (contract §1 spelling; "" = no association).
    assert observations[0]["track_key"] == f"{RUN_ID}:5:0"
    assert observations[1]["track_key"] == f"{RUN_ID}:9:none"
    assert observations[2]["track_key"] == ""

    # Existence probabilities ride the same payload (the §6.1 badge source).
    assert payload["tracks"][0]["existence_prob"] == pytest.approx(EXISTENCE)
    assert observations[0]["age_s"] == pytest.approx(0.5)
    assert observations[0]["confidence"] == pytest.approx(0.87)
    assert observations[0]["class_name"] == "boat"
    assert observations[0]["sensor_id"] == 2

    # Dimensions: label 5 hits its truth ship (50x12); label 9 misses -> class default.
    assert (observations[0]["length_m"], observations[0]["width_m"]) == pytest.approx((50.0, 12.0))
    assert (observations[1]["length_m"], observations[1]["width_m"]) == pytest.approx((12.0, 5.0))

    # The compact wire transport keeps the top-level key byte-identical.
    with http.websocket_connect(f"/ws/sessions/{RUN_ID}?transport=compact-v1") as websocket:
        compact = websocket.receive_json()
    assert compact["observations"] == payload["observations"]

    # ── link 3: web layer buildTwinPresentation over the exact WS payload ──
    info = http.get("/api/enc_info").json()
    assert info["run_id"] == RUN_ID and info["ready"] is True

    bridge = run_node_bridge(tmp_path, payload, info)
    assert bridge["run_id"] == RUN_ID
    targets = bridge["targets"]
    assert [target["key"] for target in targets] == [f"{RUN_ID}:5:0", f"{RUN_ID}:7:1", f"{RUN_ID}:9:none"]
    for target, expected in zip(targets, EXISTENCE):
        assert target["existence"] == pytest.approx(expected), "B-section existence flows raw -> presentation"
        assert target["truth"] is False, "vimmjipda targets are tracker estimates, not truth"
    for index, target in enumerate(targets):
        assert target["north"] == pytest.approx(info["origin_n"] + states[index][0])
        assert target["east"] == pytest.approx(info["origin_e"] + states[index][1])

    detections = {detection["key"]: detection for detection in bridge["detections"]}
    assert set(detections) == {"2:41:0", "2:41:1", "2:41:2"}
    near = detections["2:41:0"]
    # The cross-layer link: Python's A-section track_key equals the JS targetKey
    # of the same target, so the per-target YOLO switch (yoloKeys) can match.
    assert near["track_key"] == f"{RUN_ID}:5:0" == targets[0]["key"]
    assert near["east"] == pytest.approx(info["origin_e"] + observations[0]["east"])
    assert near["north"] == pytest.approx(info["origin_n"] + observations[0]["north"])
    assert near["confidence"] == pytest.approx(0.87)
    assert near["class_name"] == "boat" and near["sensor_id"] == 2
    # A->B rename for the Unity DTO (JsonUtility matches field names literally).
    assert "length" in near and "length_m" not in near
    assert (near["length"], near["width"]) == pytest.approx((50.0, 12.0))

    sail = detections["2:41:1"]
    assert sail["track_key"] == f"{RUN_ID}:9:none" == targets[2]["key"]
    assert (sail["length"], sail["width"]) == pytest.approx((12.0, 5.0)), "class default box for labelless tracks"
    assert detections["2:41:2"]["track_key"] == "", "no association -> JsonUtility-safe empty string"

    # Layer off (contract §3): only the right-click-toggled track's detection ships.
    assert bridge["layerOffDetectionKeys"] == ["2:41:0"]
