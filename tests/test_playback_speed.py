from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gui_server.main import _bounded_playback_deadline, app


def test_playback_deadline_recovers_after_one_slow_step() -> None:
    deadline, lag = _bounded_playback_deadline(0.0, 0.24, 0.1)
    assert deadline == pytest.approx(0.1)
    assert lag == pytest.approx(0.14)

    deadline, lag = _bounded_playback_deadline(deadline, 0.24, 0.1)
    assert deadline == pytest.approx(0.2)
    assert lag == pytest.approx(0.04)

    deadline, lag = _bounded_playback_deadline(deadline, 0.24, 0.1)
    assert deadline == pytest.approx(0.3)
    assert lag == 0.0


def test_playback_deadline_bounds_unrecoverable_backlog() -> None:
    deadline, lag = _bounded_playback_deadline(0.0, 5.0, 0.1)
    assert deadline == pytest.approx(4.2)
    assert lag == pytest.approx(0.8)


def test_session_speed_is_authoritative_and_resets_with_session() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "scenario_id": "head_on",
                "validation_rule_id": "rule14",
                "algorithm_id": "vo",
                "tracker_id": "god",
                "t_end": 1.0,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        assert created.json()["playback"]["requested_multiplier"] == 1.0

        changed = client.post(
            f"/api/sessions/{session_id}/speed",
            params={"multiplier": 5.0},
        )
        assert changed.status_code == 200
        assert changed.json() == {
            "requested_multiplier": 5.0,
            "effective_multiplier": None,
            "realtime_limited": False,
            "scheduler_lag_ms": 0.0,
        }
        described = client.get(f"/api/sessions/{session_id}")
        assert described.json()["playback"]["requested_multiplier"] == 5.0

        telemetry = client.post(f"/api/sessions/{session_id}/step")
        assert telemetry.status_code == 200
        assert telemetry.json()["playback"]["requested_multiplier"] == 5.0

        reset = client.post(f"/api/sessions/{session_id}/reset")
        assert reset.status_code == 200
        assert reset.json()["playback"]["requested_multiplier"] == 1.0


def test_session_speed_rejects_replaced_session() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions/not-a-session/speed",
            params={"multiplier": 2.0},
        )
        assert response.status_code == 404


def test_playback_ui_uses_server_state_and_frame_interpolation() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/app.js")
        runtime = client.get("/static/modules/active-session-runtime.js")
        situation_display = client.get("/static/modules/situation-display.js")

    assert 'id="speedStatus"' in page.text
    assert "/speed?multiplier=${encodeURIComponent(speed)}" in runtime.text
    assert "syncPlaybackStatus(playback" in script.text
    assert situation_display.status_code == 200
    assert "queueTelemetryRender(data)" in situation_display.text
    assert "raf(renderTelemetryFrame)" in situation_display.text
    assert "function telemetryRenderDurationMs(from, to)" in situation_display.text
    assert "renderDurationMs = telemetryRenderDurationMs(renderToData, data);" in situation_display.text
    assert "data.seq === renderToData.seq" in situation_display.text
    assert "TELEMETRY_RENDER_INTERVAL_MS = 100" not in situation_display.text
    assert "VO_DECISION_FETCH_INTERVAL_MS = 200" in script.text
    assert "voDecisionSpacePending" in script.text
    assert "voDecisionSpaceAttemptedKey" in script.text
    assert "requestPendingVODecisionSpace();" in script.text
    assert "voDecisionSpaceKey?.startsWith(`${currentRunId()}:`)" in script.text
    assert "if (voDecisionSpaceController) voDecisionSpaceController.abort();" not in script.text[
        script.text.index("function ensureVODecisionSpace(") : script.text.index("function drawVODecisionSpace(")
    ]
    assert "/api/set_speed?multiplier=" not in script.text


def test_ownship_uses_fcb45_top_view_sprite() -> None:
    with TestClient(app) as client:
        situation_display = client.get("/static/modules/situation-display.js")
        sprite = client.get("/static/assets/fcb45-top.png")

    assert situation_display.status_code == 200
    assert sprite.status_code == 200
    assert sprite.headers["content-type"] == "image/png"
    assert sprite.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert "setSpriteSrc(ownshipSprite, '/static/assets/fcb45-top.png');" in situation_display.text
    assert "drawOwnshipSprite(point, data.os.psi, FCB45_LENGTH_M, FCB45_WIDTH_M);" in situation_display.text
