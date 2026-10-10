"""Session-bound ownership of the local Deployment twin services."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class TwinRuntimeError(RuntimeError):
    """The local twin services could not start or stop."""


class TwinRuntime:
    """Serialize launchd commands off the simulation thread; never own its clock."""

    def __init__(self, project_root: Path) -> None:
        self._control = project_root / "deploy" / "twin" / "twinctl"
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="colav-twin")
        self._lock = threading.Lock()
        self._session_id: str | None = None
        self._revision = 0
        self._state = "STOPPED"
        self._error: str | None = None
        self._managed = False
        self._start_future: Future[dict[str, Any]] | None = None

    def describe(self) -> dict[str, Any]:
        with self._lock:
            result = {"session_id": self._session_id, "state": self._state, "error": self._error}
        config = self._control.parent / "remote-runtime.json"
        if config.is_file():
            remote = json.loads(config.read_text())
            result["renderer_backend_base"] = remote["renderer_backend_base"]
            result["signaling_url"] = remote["signaling_url"]
        return result

    def start(self, session_id: str) -> Future[dict[str, Any]]:
        with self._lock:
            if self._session_id == session_id and self._state == "STARTING" and self._start_future is not None:
                return self._start_future
            self._session_id = session_id
            self._revision += 1
            self._state, self._error = "STARTING", None
            self._start_future = self._executor.submit(self._start, self._revision)
            return self._start_future

    def stop(self, session_id: str | None = None) -> Future[dict[str, Any]] | None:
        with self._lock:
            # Delayed completion/failure of an old session cannot stop a new one.
            if self._session_id is None or (session_id is not None and session_id != self._session_id):
                return None
            self._session_id = None
            self._revision += 1
            self._state = "STOPPING"
            return self._executor.submit(self._stop, self._revision)

    def _invoke(self, action: str) -> None:
        if sys.platform != "darwin" or not self._control.is_file():
            raise TwinRuntimeError("Local DT services require the installed macOS twin runtime")
        try:
            result = subprocess.run(
                [str(self._control), action],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TwinRuntimeError(f"Twin runtime {action} failed: {exc}") from exc
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise TwinRuntimeError(f"Twin runtime {action} failed: {detail}")

    def _start(self, revision: int) -> dict[str, Any]:
        with self._lock:
            cancelled = revision != self._revision
        if cancelled:
            return self.describe()
        try:
            # Also own partial startup, so terminal cleanup releases both services.
            self._managed = True
            self._invoke("start")
        except TwinRuntimeError as exc:
            try:
                self._invoke("stop")
                self._managed = False
            except TwinRuntimeError:
                log.exception("Twin partial-start cleanup failed")
            with self._lock:
                if revision == self._revision:
                    self._state, self._error = "ERROR", str(exc)
            raise
        with self._lock:
            if revision == self._revision:
                self._state = "RUNNING"
        return self.describe()

    def _stop(self, revision: int) -> dict[str, Any]:
        try:
            if self._managed:
                self._invoke("stop")
                self._managed = False
        except TwinRuntimeError as exc:
            log.exception("Twin shutdown failed")
            with self._lock:
                if revision == self._revision:
                    self._state, self._error = "ERROR", str(exc)
            return self.describe()
        with self._lock:
            if revision == self._revision:
                self._state, self._error = "STOPPED", None
        return self.describe()
