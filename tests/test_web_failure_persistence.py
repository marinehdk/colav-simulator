"""Failure evidence work must not hold the active-session control lock."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

from colav_simulator.experiment.contracts import SessionState
from gui_server.main import WebSessionManager


def test_slow_failure_writer_does_not_block_session_control(monkeypatch) -> None:
    manager = WebSessionManager()
    started, release = Event(), Event()
    prepared = SimpleNamespace(
        session=SimpleNamespace(state=SessionState.RUNNING, failure_reason=None, frames=[], events=[]),
        artifact_sink=SimpleNamespace(close=lambda **kwargs: None),
        manifest=object(),
        writer=object(),
    )

    def slow_writer(*args):
        started.set()
        release.wait(5)

    monkeypatch.setattr(manager.runner, "persist_failure", slow_writer)

    def fail():
        with manager.lock:
            manager._persist_failure(prepared, RuntimeError("solver failed"))

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fail)
            assert started.wait(2)
            try:
                future.result(timeout=0.5)
                assert prepared.session.state == SessionState.FAILED
                assert prepared.session.failure_reason == "solver failed"
            finally:
                release.set()
    finally:
        release.set()
        manager._result_executor.shutdown(wait=True)
