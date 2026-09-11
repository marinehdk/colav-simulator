"""Optional local C++ boundary for the frozen original GNC.

No ROS imports, background execution, or alternate-stack fallback. Calls own
explicit time and a per-module native instance; the facade owns scheduling.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import threading
from pathlib import Path
from typing import Any


class OriginalGncError(RuntimeError):
    """A source, dependency, input, or native execution failure."""


def verify_build(build_directory: Path) -> dict:
    """Reject changed code or library before loading either native component."""
    manifest_path = build_directory / "build-manifest.json"
    if not manifest_path.is_file():
        raise OriginalGncError(f"Original GNC is not built: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    extraction = build_directory / "extraction.json"
    if not extraction.is_file() or hashlib.sha256(extraction.read_bytes()).hexdigest() != manifest["extraction_sha256"]:
        raise OriginalGncError("Original GNC extraction changed after compilation")
    for relative, expected in manifest["source_fingerprints"].items():
        path = build_directory / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise OriginalGncError(f"Original GNC build is stale: {relative}")
    library = Path(manifest["library"])
    if not library.is_file() or hashlib.sha256(library.read_bytes()).hexdigest() != manifest["library_sha256"]:
        raise OriginalGncError("Original GNC native library does not match its build identity")
    return manifest


class NativeModule:
    """Own one original module instance behind a narrow local C ABI."""

    def __init__(self, build_directory: Path, module: str, parameters: dict, options: dict | None = None):
        self._lock = threading.RLock()
        self._handle = None
        self.manifest = verify_build(build_directory)
        library = Path(self.manifest["library"])
        self._library = ctypes.CDLL(str(library))
        self._library.original_gnc_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._library.original_gnc_create.restype = ctypes.c_void_p
        self._library.original_gnc_describe.argtypes = [ctypes.c_void_p]
        self._library.original_gnc_describe.restype = ctypes.c_char_p
        self._library.original_gnc_invoke.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int64]
        self._library.original_gnc_invoke.restype = ctypes.c_char_p
        self._library.original_gnc_error.restype = ctypes.c_char_p
        self._library.original_gnc_destroy.argtypes = [ctypes.c_void_p]
        self._library.original_gnc_destroy.restype = None
        self.module = module
        self._handle = self._library.original_gnc_create(
            module.encode(),
            json.dumps(parameters, allow_nan=False).encode(),
            json.dumps(options or {}, allow_nan=False).encode(),
        )
        if not self._handle:
            raise self._error()

    def _error(self) -> OriginalGncError:
        message = self._library.original_gnc_error()
        return OriginalGncError(f"{self.module}: {message.decode() if message else 'native call failed'}")

    def describe(self) -> dict[str, Any]:
        """Return actual declared parameters, port types and original periods."""
        with self._lock:
            if not self._handle:
                raise OriginalGncError("Original GNC module has been closed")
            result = self._library.original_gnc_describe(self._handle)
            if result is None:
                raise self._error()
            return json.loads(result)

    def invoke(self, callback: str, message: dict | None, time_ns: int) -> dict[str, Any]:
        """Execute one original input callback or scheduled update, synchronously."""
        if isinstance(time_ns, bool) or not isinstance(time_ns, int) or not 0 <= time_ns < 2**63:
            raise ValueError("time_ns must be a nonnegative int64")
        with self._lock:
            if not self._handle:
                raise OriginalGncError("Original GNC module has been closed")
            result = self._library.original_gnc_invoke(
                self._handle, callback.encode(), json.dumps(message, allow_nan=False).encode(), time_ns
            )
            if result is None:
                raise self._error()
            return json.loads(result)

    def close(self) -> None:
        """Destroy only this instance; no process-global simulation state reset."""
        with self._lock:
            if self._handle:
                self._library.original_gnc_destroy(self._handle)
                self._handle = None

    def __enter__(self) -> NativeModule:
        """Enter the owned native-kernel scope."""
        return self

    def __exit__(self, *_: object) -> None:
        """Release native handles on scope exit."""
        self.close()

    def __del__(self) -> None:
        """Release opaque kernels when an unused episode template is collected."""
        try:
            self.close()
        except Exception:
            pass
