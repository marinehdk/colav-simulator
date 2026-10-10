"""Deployment DT runtime belongs to its active session, independently of the browser."""

import json
import os
import subprocess
import threading
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import gui_server.main as gui_main
from colav_simulator.experiment.contracts import SessionState
from gui_server.twin_runtime import TwinRuntime, TwinRuntimeError


class FakeRuntime:
    def __init__(self):
        self.started = []
        self.stopped = []

    def start(self, session_id: str) -> Future[dict[str, Any]]:
        self.started.append(session_id)
        result = Future()
        result.set_result({"session_id": session_id, "state": "RUNNING", "error": None})
        return result

    def stop(self, session_id=None):
        self.stopped.append(session_id)


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> gui_main.WebSessionManager:
    manager = gui_main.WebSessionManager()
    manager.twin_runtime = FakeRuntime()
    manager.prepared = SimpleNamespace(
        manifest=SimpleNamespace(run_id="active"),
        session=SimpleNamespace(state=SessionState.PAUSED, events=[], enable_pickle_frames=lambda: None),
        artifact_sink=SimpleNamespace(close=lambda **kwargs: None),
        run_dir=tmp_path,
    )
    manager._result_executor = SimpleNamespace(submit=lambda *args: None)
    for name in (
        "_record_telemetry_trails",
        "_record_ais_reports",
        "_append_trace_capture",
        "_publish_telemetry",
        "_open_trace_capture",
        "_persist_static_context",
    ):
        monkeypatch.setattr(manager, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(gui_main, "manager", manager)
    return manager


def test_dt_start_is_bound_to_the_current_nonterminal_session(manager):
    client = TestClient(gui_main.app)
    response = client.post("/api/sessions/active/twin/start")
    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == "active"
    assert manager.twin_runtime.started == ["active"]
    assert client.post("/api/sessions/old/twin/start").status_code == 404
    manager.prepared.session.state = SessionState.FINISHED
    assert client.post("/api/sessions/active/twin/start").status_code == 409
    assert manager.twin_runtime.started == ["active"]


@pytest.mark.parametrize("method", ["step", "tick"])
def test_completion_stops_twin_without_waiting_for_evaluation(manager, method):
    def advance() -> SimpleNamespace:
        manager.prepared.session.state = SessionState.FINISHED
        return SimpleNamespace(payload={})

    manager.prepared.session.step_once = advance
    manager.prepared.session.advance = advance
    manager.prepared.session.simulator = SimpleNamespace(t=10.0)
    manager.prepared.session.state = SessionState.RUNNING
    if method == "step":
        manager.step("active")
    else:
        manager.tick()
    assert manager.twin_runtime.stopped == ["active"]


def test_failure_stops_twin_and_preserves_the_session_failure(manager):
    def fail():
        raise RuntimeError("solver failed")

    manager.prepared.session.step_once = fail
    with pytest.raises(RuntimeError, match="solver failed"):
        manager.step("active")
    assert manager.prepared.session.state == SessionState.FAILED
    assert manager.prepared.session.failure_reason == "solver failed"
    assert manager.twin_runtime.stopped == ["active"]


def test_session_replacement_stops_the_old_twin(manager, monkeypatch, tmp_path):
    monkeypatch.setattr(gui_main, "render_enc", lambda *args: None)
    monkeypatch.setattr(manager, "_enc_navigation_area", lambda: {})
    monkeypatch.setattr(manager, "describe", lambda: {})
    replacement = SimpleNamespace(
        session=SimpleNamespace(enable_pickle_frames=lambda: None),
        manifest=SimpleNamespace(run_id="replacement"),
        run_dir=Path(tmp_path),
    )
    manager._activate(replacement)
    assert manager.twin_runtime.stopped == ["active"]


def test_inflight_start_and_stop_are_serialized_and_old_completion_cannot_stop_new_session(tmp_path):
    runtime = TwinRuntime(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    commands = []

    def invoke(action):
        commands.append(action)
        if len(commands) == 1:
            entered.set()
            assert release.wait(5)

    runtime._invoke = invoke
    try:
        first = runtime.start("old")
        assert entered.wait(5)
        assert runtime.start("old") is first, "concurrent entry reuses in-flight startup"
        stopped = runtime.stop("old")
        assert not stopped.done(), "terminal cleanup queues without blocking the simulation"
        second = runtime.start("new")
        assert runtime.stop("old") is None, "a delayed old-session event cannot stop the new owner"
        release.set()
        first.result(timeout=5)
        stopped.result(timeout=5)
        assert second.result(timeout=5)["session_id"] == "new"
        assert commands == ["start", "stop", "start"]
        runtime.stop("new").result(timeout=5)
        assert runtime.describe()["state"] == "STOPPED"
        assert commands == ["start", "stop", "start", "stop"]
    finally:
        release.set()
        runtime._executor.shutdown(wait=True)


def test_start_failure_cleans_partial_services_and_can_retry(tmp_path):
    runtime = TwinRuntime(tmp_path)
    commands = []

    def invoke(action):
        commands.append(action)
        if len(commands) == 1:
            raise TwinRuntimeError("signaling failed")

    runtime._invoke = invoke
    try:
        with pytest.raises(TwinRuntimeError, match="signaling failed"):
            runtime.start("active").result(timeout=5)
        assert commands == ["start", "stop"]
        assert runtime.describe()["state"] == "ERROR"
        assert runtime.start("active").result(timeout=5)["state"] == "RUNNING"
        runtime.stop("active").result(timeout=5)
        assert commands == ["start", "stop", "start", "stop"]
    finally:
        runtime._executor.shutdown(wait=True)


def test_native_start_failure_is_a_service_error(manager, monkeypatch):
    def start(session_id: str) -> Future[dict[str, Any]]:
        result = Future()
        result.set_exception(TwinRuntimeError("player unavailable"))
        return result

    monkeypatch.setattr(manager.twin_runtime, "start", start)
    response = TestClient(gui_main.app).post("/api/sessions/active/twin/start")
    assert response.status_code == 503
    assert response.json()["detail"] == "player unavailable"


@pytest.mark.parametrize("action", ["start", "stop"])
def test_twinctl_reports_failures_and_never_starts_player_after_signaling_failure(tmp_path, action):
    commands = tmp_path / "commands"
    launchctl = tmp_path / "launchctl"
    launchctl.write_text(
        "#!/bin/bash\n"
        f'echo "$*" >> "{commands}"\n'
        'if [[ "$1" == kickstart && "$2" == *twin-signaling ]]; then exit 1; fi\n'
        'if [[ "$1" == bootout && "$2" == *twin-player ]]; then exit 1; fi\n'
        "exit 0\n"
    )
    launchctl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(tmp_path) + os.pathsep + env["PATH"]
    # Keep machine-specific remote configuration out of the shell failure test.
    source = Path(__file__).resolve().parents[1] / "deploy/twin/twinctl"
    control = tmp_path / "repo/deploy/twin/twinctl"
    control.parent.mkdir(parents=True)
    control.write_bytes(source.read_bytes())
    control.chmod(0o755)
    result = subprocess.run([str(control), action], env=env, capture_output=True, timeout=5, check=False)
    assert result.returncode != 0
    issued = commands.read_text()
    if action == "start":
        assert "kickstart" in issued
        assert not any("kickstart" in line and "twin-player" in line for line in issued.splitlines())
    else:
        assert any("bootout" in line and "twin-signaling" in line for line in issued.splitlines()), "stop both on error"


def test_remote_runtime_exposes_renderer_endpoint_without_changing_session_owner(tmp_path):
    runtime = TwinRuntime(tmp_path)
    config = tmp_path / "deploy/twin/remote-runtime.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps({"renderer_backend_base": "http://127.0.0.1:18010", "signaling_url": "ws://127.0.0.1:8080"})
    )
    runtime._invoke = lambda action: None
    try:
        value = runtime.start("same-session").result(timeout=5)
        assert value["session_id"] == "same-session"
        assert value["renderer_backend_base"] == "http://127.0.0.1:18010"
        runtime.stop("same-session").result(timeout=5)
    finally:
        runtime._executor.shutdown(wait=True)
