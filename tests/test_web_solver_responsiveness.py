"""A slow planner must not hold the WebSocket asyncio event loop."""

import asyncio
import threading
from types import SimpleNamespace

from gui_server import main


def test_stream_lock_wait_does_not_block_asyncio(monkeypatch) -> None:
    entered = threading.Event()
    released = threading.Event()
    sent = threading.Event()

    def slow_document(**kwargs) -> str:
        entered.set()
        released.wait(timeout=0.3)
        return "{}"

    class Socket:
        async def accept(self):
            pass

        async def receive(self):
            await asyncio.sleep(10)

        async def send_text(self, value):
            sent.set()
            raise ConnectionError("test disconnect")

    monkeypatch.setattr(main, "manager", SimpleNamespace(stream_document=slow_document))

    async def exercise():
        task = asyncio.create_task(main._stream(Socket()))
        while not entered.is_set():
            await asyncio.sleep(0.001)
        try:
            assert not sent.is_set(), "stream lock stalled all asyncio work until solver completed"
        finally:
            released.set()
            await task

    asyncio.run(exercise())


def test_terminal_frame_is_published_before_slow_result_generation(monkeypatch) -> None:
    manager = main.WebSessionManager()
    entered = threading.Event()
    release = threading.Event()
    session = SimpleNamespace(state=main.SessionState.RUNNING, simulator=SimpleNamespace(t=270.0))
    prepared = SimpleNamespace(session=session, manifest=SimpleNamespace(run_id="terminal"))
    manager.prepared = prepared

    def advance() -> SimpleNamespace:
        session.state = main.SessionState.FINISHED
        return SimpleNamespace(payload={})

    def finalize(_prepared, _expected=None):
        entered.set()
        release.wait(timeout=1.0)

    session.advance = advance
    monkeypatch.setattr(manager, "_finalize", finalize)
    monkeypatch.setattr(manager, "_record_telemetry_trails", lambda payload: None)
    monkeypatch.setattr(manager, "_telemetry_refresh_due", lambda *a, **kw: True)
    monkeypatch.setattr(manager, "_publish_telemetry", lambda snapshot: manager.latest.update(state=session.state.value))
    worker = threading.Thread(target=manager.tick)
    worker.start()
    try:
        assert entered.wait(timeout=1.0)
        assert manager.latest.get("state") == "FINISHED"
        assert manager.lock.acquire(timeout=0.05), "result generation holds the session control lock"
        manager.lock.release()
    finally:
        release.set()
        worker.join(timeout=2.0)


def test_old_result_cannot_replace_a_new_session_result(monkeypatch) -> None:
    manager = main.WebSessionManager()
    old = SimpleNamespace()
    new = SimpleNamespace()
    result = object()
    manager.prepared = old

    def finalize(prepared) -> object:
        assert prepared is old
        manager.prepared = new
        return result

    monkeypatch.setattr(manager.runner, "finalize", finalize)
    manager._finalize(old)
    assert manager.prepared is new
    assert manager.result is None
