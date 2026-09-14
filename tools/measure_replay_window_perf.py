"""Measure Sealed Run Replay window/late-seek latency (ticket #71 evidence).

Builds one synthetic Decision Trace whose per-tick record size matches the
#70 Mid-MPC measurement (~150 KB/tick raw / ~35 KB/tick gzipped), then times
descriptor and bounded window reads through the same ``RunReplayStore`` seam
the HTTP router uses. The trace lives in a caller-supplied (or temporary)
directory and is the caller's responsibility to delete.

Read path only: this tool imports the stdlib-only replay reader, never the
simulator.

Usage:
    python tools/measure_replay_window_perf.py [--ticks 600] [--seeks 20]
        [--keep-dir DIR]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui_server.replay import RunReplayStore  # noqa: E402

TICKS = 600
BYTES_PER_TICK = 150_000  # #70 measured Mid-MPC: 150 791 raw / 34 753 gz bytes per tick
WINDOW_SPAN_S = 6.0
DT = 0.1
RUN_ID = "a60fe100-0000-4000-8000-000000060000"  # UUID-shaped; #70 confinement requires canonical UUIDs


def build_filler_payload(target_bytes: int) -> dict:
    """Deterministic semi-compressible numeric evidence (~Mid-MPC bytes/tick).

    Numeric arrays with varied digits approximate the real planner audit
    payloads' compression ratio; decode cost scales with decompressed size,
    which is what the O(file) per-frame seek pays.
    """
    state = 0x2BE417
    values = []
    while sum(len(v) for v in values) < target_bytes:
        state = (state * 1103515245 + 12345) % (1 << 31)
        values.append(f"{state / 1e4:.4f}")
    audit = [float(v) for v in values]
    return {
        "Ship0": {"state": [1.0, 2.0, 0.3, 2.0, 0.0, 0.0], "colav": {"planner": {"solve_id": 1, "audit": audit}}},
        "Ship1": {"state": [3.0, 4.0, 1.0, 1.0, 0.0, 0.0]},
    }


def write_trace(run_dir: Path, ticks: int, payload: dict) -> None:
    """Write the sealed v1 trace artifacts for the measurement run."""
    decision = run_dir / "decision"
    decision.mkdir(parents=True)
    frames_path = decision / "frames.jsonl"
    digest = hashlib.sha256()
    t_start = None
    t_end = None
    with frames_path.open("wb") as handle:
        for sequence in range(1, ticks + 1):
            sim_time = DT * sequence
            record = json.dumps(
                {
                    "sequence": sequence,
                    "sim_time": sim_time,
                    "step_time_ms": 160.0,
                    "state": "RUNNING",
                    "payload": payload,
                    "events": [],
                }
            ).encode("utf-8")
            handle.write(record + b"\n")
            digest.update(record + b"\n")
            t_end = sim_time
            if t_start is None:
                t_start = sim_time
    gz_path = decision / "frames.jsonl.gz"
    raw = frames_path.read_bytes()
    with gzip.GzipFile(str(gz_path), "wb", mtime=0) as gz:
        gz.write(raw)
    frames_path.unlink()
    index = {
        "trace_schema": "colav.decision-replay.v1",
        "tick_count": ticks,
        "t_start": t_start,
        "t_end": t_end,
        "frames_sha256": digest.hexdigest(),
        "truncated": False,
        "state": "READY",
    }
    (decision / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": run_dir.name, "state": "FINISHED", "spec": {"scenario_id": "perf_probe"}}),
        encoding="utf-8",
    )


def main() -> int:
    """Build (once), then exercise the replay window seam and print numbers."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=TICKS)
    parser.add_argument("--seeks", type=int, default=20)
    parser.add_argument("--keep-dir", type=Path, default=None, help="reuse/write a trace under this root (not deleted)")
    args = parser.parse_args()

    root = Path(args.keep_dir) if args.keep_dir else Path(tempfile.mkdtemp(prefix="replay-perf-")) / "runs"
    root.mkdir(parents=True, exist_ok=True)
    run_id = RUN_ID
    run_dir = root / run_id
    if not (run_dir / "decision" / "index.json").is_file():
        run_dir.mkdir(parents=True, exist_ok=True)
        write_trace(run_dir, args.ticks, build_filler_payload(BYTES_PER_TICK))

    gz = run_dir / "decision" / "frames.jsonl.gz"
    t_end = DT * args.ticks
    print(json.dumps({"trace": {"ticks": args.ticks, "gz_bytes": gz.stat().st_size}}))

    store = RunReplayStore(root)
    facts = store.classify(run_dir)
    if facts["state"] != "READY":
        raise SystemExit(f"fixture trace is not READY: {facts}")

    # Descriptor/classify cost (integrity re-verification included).
    started = time.perf_counter()
    store.descriptor(run_id)
    descriptor_ms = (time.perf_counter() - started) * 1000.0

    # Direct LATE seek: window at the end of the trace, no earlier frames.
    late_from = t_end - WINDOW_SPAN_S
    started = time.perf_counter()
    document = store.window(run_id, late_from, t_end)
    cold_late_ms = (time.perf_counter() - started) * 1000.0
    late_frames = len(document["frames"])
    if late_frames <= 0:
        raise SystemExit("late window returned no frames")

    late_samples = []
    mid_samples = []
    for index in range(args.seeks):
        mark = time.perf_counter()
        start = max(0.0, (t_end - WINDOW_SPAN_S) - (index % 7) * 3.1)
        store.window(run_id, start, start + WINDOW_SPAN_S)
        late_samples.append((time.perf_counter() - mark) * 1000.0)
        mark = time.perf_counter()
        mid = args.ticks * DT / 2
        store.window(run_id, mid, mid + WINDOW_SPAN_S)
        mid_samples.append((time.perf_counter() - mark) * 1000.0)

    def stats(values: list[float]) -> dict:
        ordered = sorted(values)
        return {
            "n": len(values),
            "median_ms": round(statistics.median(ordered), 2),
            "p95_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 2),
            "max_ms": round(ordered[-1], 2),
        }

    print(
        json.dumps(
            {
                "descriptor_ms": round(descriptor_ms, 2),
                "cold_late_seek_ms": round(cold_late_ms, 2),
                "late_seek_frames": late_frames,
                "late_seek": stats(late_samples),
                "mid_trace_seek": stats(mid_samples),
            },
            indent=1,
        )
    )
    if args.keep_dir is None:
        shutil.rmtree(root.parent, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
