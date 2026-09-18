"""Import a sealed Run using compact chart capture, with full-frame round-trip verification."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import orjson

from colav_simulator.decision_replay.bundle import TraceBundle
from colav_simulator.decision_replay.chart import CHART_PROFILE, chart_events, chart_payload
from colav_simulator.decision_replay.sink import TraceSink, TraceSinkPolicy


def compact(source: Path, output_root: Path) -> dict:
    """Preserve Run identity and audit artifacts; never overwrite the source or destination."""
    source = source.resolve()
    destination = output_root.resolve() / source.name
    staging = output_root.resolve() / f".{source.name}-compact"
    if destination.exists() or staging.exists():
        raise FileExistsError(destination)
    bundle = TraceBundle(source)
    original_index = bundle.index()
    if original_index.get("state") != "READY" or original_index.get("truncated"):
        raise ValueError("a complete sealed source is required; missing frames cannot be reconstructed")
    shutil.copytree(source, staging, ignore=lambda path, _names: ["decision"] if Path(path) == source else [])
    sink = TraceSink.open(
        staging, policy=TraceSinkPolicy(capture_profile="chart", max_total_bytes=2 * 1024**3, events_gzip=True)
    )
    expected = hashlib.sha256()
    source_digest = hashlib.sha256()
    # Read the sealed bytes exactly once, checking the original artifact digest.
    with gzip.open(source / "decision/frames.jsonl.gz", "rb") as stream:
        for line in stream:
            source_digest.update(line)
            row = orjson.loads(line)
            if "storage_schema" in row:
                raise ValueError("source is already block encoded")
            expected_row = {
                **row,
                "payload": chart_payload(row["payload"]),
                "events": chart_events(row["events"]),
                "capture_profile": CHART_PROFILE,
            }
            expected.update(orjson.dumps(expected_row, option=orjson.OPT_SORT_KEYS))
            sink.append(SimpleNamespace(**row))
            if sink.state != "CAPTURING":
                raise RuntimeError(sink.reason)
    index = sink.close(events=bundle.events())
    if source_digest.hexdigest() != original_index["frames_sha256"]:
        raise ValueError("source artifact digest mismatch")
    if index["state"] != "READY":
        raise RuntimeError(f"capture incomplete: {index}")
    if index["tick_count"] != original_index["tick_count"]:
        raise ValueError("frame count changed")
    actual = hashlib.sha256()
    for row in TraceBundle(staging).frames():
        actual.update(orjson.dumps(row, option=orjson.OPT_SORT_KEYS))
    if actual.digest() != expected.digest():
        raise ValueError("per-frame chart data changed during round trip")
    summary = {
        "run_id": source.name,
        "source": str(source),
        "destination": str(destination),
        "source_frames_sha256": original_index["frames_sha256"],
        "chart_semantic_sha256": actual.hexdigest(),
        "frame_count": index["tick_count"],
        "t_end": index["t_end"],
        "source_capture_bytes": original_index["capture_bytes"],
        "capture_bytes": index["capture_bytes"],
        "source_gzip_bytes": (source / "decision/frames.jsonl.gz").stat().st_size,
        "gzip_bytes": (staging / "decision/frames.jsonl.gz").stat().st_size,
        "state": index["state"],
        "profile": CHART_PROFILE,
    }
    (staging / "decision/compaction.json").write_text(json.dumps(summary, indent=2))
    staging.rename(destination)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compact(args.source, args.output_root), indent=2), flush=True)
