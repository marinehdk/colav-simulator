from __future__ import annotations

import json
import threading
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

from colav_simulator.experiment.contracts import SessionState
from gui_server.main import (
    TELEMETRY_MAX_TRAIL_POINTS,
    WebSessionManager,
    _compact_stream_payload,
    _sample_display_trail,
)


def test_display_trail_is_bounded_without_losing_endpoints() -> None:
    trail = [[float(index), float(-index)] for index in range(500)]

    sampled = _sample_display_trail(trail)

    assert len(sampled) == TELEMETRY_MAX_TRAIL_POINTS
    assert sampled[0] == trail[0]
    assert sampled[-1] == trail[-1]
    assert all(left[0] < right[0] for left, right in pairwise(sampled))


def test_telemetry_refresh_is_wall_clock_limited_but_preserves_planner_and_terminal_updates() -> None:
    manager = WebSessionManager.__new__(WebSessionManager)
    manager._telemetry_published_at = 10.0

    ordinary = SimpleNamespace(events=[], state=SessionState.RUNNING)
    planner = SimpleNamespace(events=[{"type": "planner_solved"}], state=SessionState.RUNNING)
    terminal = SimpleNamespace(events=[], state=SessionState.FINISHED)

    assert manager._telemetry_refresh_due(ordinary, now=10.05) is False
    assert manager._telemetry_refresh_due(ordinary, now=10.10) is True
    assert manager._telemetry_refresh_due(planner, now=10.01) is True
    assert manager._telemetry_refresh_due(terminal, now=10.01) is True


def test_telemetry_trails_are_recorded_incrementally_in_local_coordinates() -> None:
    manager = WebSessionManager.__new__(WebSessionManager)
    session = SimpleNamespace(enc=SimpleNamespace(origin=(100.0, 200.0)), ship_list=[object()])
    manager.prepared = SimpleNamespace(session=session)
    manager._telemetry_trails = {}

    for index in range(501):
        manager._record_telemetry_trails({"Ship0": {"state": [203.0 + index, 104.0 + index, 0.0, 0.0, 0.0, 0.0]}})

    trail = list(manager._telemetry_trails[0])
    assert len(trail) == 500
    assert trail[0] == [4.0, 5.0]
    assert trail[-1] == [503.0, 504.0]


def test_stream_document_is_cached_and_json_safe() -> None:
    manager = WebSessionManager.__new__(WebSessionManager)
    manager.latest = {"seq": 7, "dcpa": float("inf")}
    manager._latest_stream_document = ""
    manager.lock = threading.RLock()

    manager._cache_stream_document()
    first = manager.stream_document()
    second = manager.stream_document()

    assert first is second
    assert json.loads(first) == {"seq": 7, "dcpa": None}


def test_compact_stream_payload_removes_wire_duplicates_and_repeated_static_data() -> None:
    payload = {
        "run_id": "run-1",
        "truth": [
            {
                "id": 0,
                "x": 1.0,
                "measurements": [1],
                "tracks": {"states": [2]},
                "colav": {"planner": {"solve_id": 3}},
            },
            {"id": 1, "x": 2.0, "measurements": [], "tracks": {}, "colav": {}},
        ],
        "os": {"id": 0},
        "obstacles": [{"id": 1}],
        "measurements": [[1], []],
        "tracks": [{"states": [2]}, {}],
        "planner": {
            "solve_id": 3,
            "algorithm_details": {"objective": 4.0},
            "evidence_timeline": [1, 2],
            "prediction_render": {"ownship": [3]},
            "predicted_trajectory": [4],
            "target_predictions": [5],
        },
        "latest_planner_solve": {
            "solve_id": 3,
            "evidence_timeline": [1, 2],
            "prediction_render": {"ownship": [3]},
            "predicted_trajectory": [4],
            "target_predictions": [5],
        },
        "active_planner_plan": {"large": "duplicate"},
        "latest_planner_attempt": {"large": "duplicate"},
        "enc_navigation_area": {"safe_water": "large-static-value"},
    }

    initial = _compact_stream_payload(payload, include_static=True)
    update = _compact_stream_payload(payload, include_static=False)

    assert initial["transport"]["schema_version"] == "colav.telemetry.compact@1"
    assert initial["transport"]["static_included"] is True
    assert initial["enc_navigation_area"] == payload["enc_navigation_area"]
    assert "enc_navigation_area" not in update
    assert "os" not in update and "obstacles" not in update
    assert update["measurements"] == payload["measurements"]
    assert update["tracks"] == payload["tracks"]
    assert update["truth"] == [{"id": 0, "x": 1.0}, {"id": 1, "x": 2.0}]
    assert update["planner"] == {"solve_id": 3, "algorithm_details": {"objective": 4.0}}
    assert update["latest_planner_solve"] == {"solve_id": 3}
    assert "active_planner_plan" not in update
    assert "latest_planner_attempt" not in update


def test_browser_uses_shared_runtime_without_reinflating_telemetry() -> None:
    web_gui = Path(__file__).parents[1] / "web_gui"
    script = (web_gui / "app.js").read_text()
    runtime = (web_gui / "modules" / "active-session-runtime.js").read_text()
    instance = (web_gui / "modules" / "session-runtime-instance.js").read_text()

    assert "?transport=compact-v1" not in script
    assert "inflateTelemetryPayload" not in script
    assert "new WebSocket(`${protocol}//${location.host}${path}`)" in instance
    assert "telemetryProjection.project(runtimeSnapshot)" in instance
    assert "envelope = JSON.parse(event.data)" in runtime
