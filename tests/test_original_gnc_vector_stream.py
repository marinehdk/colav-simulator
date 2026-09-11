"""Guard bounded-memory reference evidence against lost or extra callbacks."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from tools.original_gnc.stream_vectors import convert
from tools.original_gnc.trace_io import archive_trace
from tools.original_gnc.validate_native_vectors import validate


@pytest.fixture
def stream_case(tmp_path) -> Any:
    config = OriginalGncConfig.from_dict({})
    if not (config.build_directory / "build-manifest.json").exists():
        pytest.skip("Optional original GNC native build unavailable")
    source = Path(__file__).parent / "fixtures/original_gnc/reference_route_contract_vectors"
    manifest = json.loads((source / "manifest.json").read_text())
    name = "coordinate_transform_node"
    entry = manifest["modules"][name]
    compact = tmp_path / "compact"
    compact.mkdir()
    filename = entry.get("file", f"{name}.json.gz")
    (compact / filename).write_bytes((source / filename).read_bytes())
    manifest["modules"] = {name: entry}
    (compact / "manifest.json").write_text(json.dumps(manifest))
    stream = tmp_path / "stream"
    convert(compact, stream)
    return config, stream, name


def test_stream_keeps_independently_recorded_source_outputs(stream_case, tmp_path):
    config, stream, name = stream_case
    result = validate(config.build_directory, stream, config.source_root, tmp_path / "result")
    assert result["passed"]
    assert result["modules"][name]["calls_checked"] > 100


@pytest.mark.parametrize("corruption", ["missing_record", "extra_record", "wrong_count"])
def test_reference_stream_corruption_never_passes(stream_case, tmp_path, corruption):
    config, stream, name = stream_case
    manifest = json.loads((stream / "manifest.json").read_text())
    entry = manifest["modules"][name]
    path = stream / entry["file"]
    lines = gzip.decompress(path.read_bytes()).splitlines()
    if corruption == "missing_record":
        lines.pop()
    elif corruption == "extra_record":
        lines.append(lines[-1])
    else:
        metadata = json.loads(lines[0])
        metadata["call_count"] += 1
        lines[0] = json.dumps(metadata).encode()
    path.write_bytes(gzip.compress(b"\n".join(lines) + b"\n", mtime=0))
    # Re-sign the intentionally malformed test bundle to exercise stream
    # completeness beyond the separate byte-identity guard.
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (stream / "manifest.json").write_text(json.dumps(manifest))
    result = validate(config.build_directory, stream, config.source_root, tmp_path / "result")
    assert not result["passed"]
    assert result["modules"][name]["first_difference"] is not None


def test_stopped_trace_archival_preserves_bytes_and_retains_broken_copy(tmp_path):
    """An interrupted compressed copy must not cause source evidence loss."""
    source = tmp_path / "trace.jsonl"
    raw = bytes(range(256)) * 4096
    source.write_bytes(raw)
    target = tmp_path / "trace.jsonl.gz"
    target.write_bytes(b"interrupted gzip")
    result = archive_trace(source)
    assert not source.exists()
    assert gzip.decompress(target.read_bytes()) == raw
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    retained = list(tmp_path.glob("trace.jsonl.gz.incomplete-*"))
    assert len(retained) == 1 and retained[0].read_bytes() == b"interrupted gzip"
