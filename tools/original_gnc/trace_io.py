"""Read original trace bytes from either raw or losslessly archived evidence."""

from __future__ import annotations

import gzip
import hashlib
import shutil
import time
from pathlib import Path
from typing import Any


def open_trace(path: Path) -> Any:
    """Open the declared trace or its verified gzip replacement as text."""
    if path.is_file():
        return path.open(encoding="utf-8")
    return gzip.open(path.with_suffix(path.suffix + ".gz"), "rt", encoding="utf-8")


def trace_sha256(path: Path) -> str:
    """Hash original uncompressed bytes, independent of storage container."""
    stream = path.open("rb") if path.is_file() else gzip.open(path.with_suffix(path.suffix + ".gz"), "rb")
    digest = hashlib.sha256()
    with stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_trace(path: Path, destination: Path) -> Path:
    """Provide raw bytes to the independent C++ replay without altering archives."""
    if path.is_file():
        return path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path.with_suffix(path.suffix + ".gz"), "rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    if trace_sha256(path) != trace_sha256(destination):
        raise RuntimeError(f"Archived trace byte identity changed: {path}")
    return destination


def archive_trace(path: Path) -> dict:
    """Replace a stopped trace only after round-trip byte identity is verified."""
    target = path.with_suffix(path.suffix + ".gz")
    original = trace_sha256(path)
    size = path.stat().st_size
    if target.exists():
        try:
            with gzip.open(target, "rb") as stream:
                existing = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    existing.update(chunk)
            valid = existing.hexdigest() == original
        except (OSError, EOFError):
            valid = False
        if not valid:
            target.rename(target.with_name(target.name + f".incomplete-{time.time_ns()}"))
    temporary = target.with_suffix(target.suffix + ".tmp")
    if not target.exists():
        if temporary.exists():
            temporary.rename(temporary.with_name(temporary.name + f".incomplete-{time.time_ns()}"))
        with path.open("rb") as source, temporary.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=3) as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
        restored = hashlib.sha256()
        with gzip.open(temporary, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                restored.update(chunk)
        if restored.hexdigest() != original:
            raise RuntimeError(f"Archive round-trip failed: {path}")
        temporary.rename(target)
    result = {"sha256": original, "bytes": size, "gzip_bytes": target.stat().st_size}
    path.unlink()
    return result
