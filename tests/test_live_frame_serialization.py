"""Captured Three-Ship frame: retain full evidence without Python leaf walks."""

import copy
import gzip
import hashlib
import json
import timeit
import tracemalloc
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from colav_simulator.core.colav.diagnostics import PlanDiagnostics, PlanStatus
from colav_simulator.decision_replay.sink import TraceSink, TraceSinkPolicy
from colav_simulator.experiment.contracts import SessionState
from colav_simulator.experiment.persistence import jsonable


def test_captured_three_ship_trace_serialization_preserves_evidence_and_budget(tmp_path):
    path = Path(__file__).parent / "fixtures/mid_mpc_ipopt/three_ship_frame.json.gz"
    record = json.loads(gzip.decompress(path.read_bytes()))
    snapshot = SimpleNamespace(**{**record, "state": SessionState(record["state"])})
    sink = TraceSink.open(tmp_path)
    try:
        encoded = sink._serialize(snapshot)
        assert json.loads(encoded) == record

        def old() -> bytes:
            return json.dumps(jsonable(record), allow_nan=False).encode("utf-8")

        def new() -> bytes | None:
            return sink._serialize(snapshot)

        old_s = min(timeit.repeat(old, number=10, repeat=3))
        new_s = min(timeit.repeat(new, number=10, repeat=3))
        assert new_s < old_s * 0.6, (new_s, old_s)
        frozen = copy.deepcopy(record)
        snapshot.payload["Ship0"]["state"][0] += 100
        assert json.loads(encoded) == frozen
    finally:
        sink.close()


def test_planner_diagnostic_snapshot_preserves_nested_values_without_asdict_leaf_cost():
    path = Path(__file__).parent / "fixtures/mid_mpc_ipopt/three_ship_frame.json.gz"
    record = json.loads(gzip.decompress(path.read_bytes()))
    values = record["payload"]["Ship0"]["colav"]["diagnostics"]
    diagnostics = PlanDiagnostics(**{**values, "status": PlanStatus(values["status"])})
    expected = asdict(diagnostics)
    actual = diagnostics.to_dict()
    assert actual == expected
    old_s = min(timeit.repeat(lambda: asdict(diagnostics), number=10, repeat=3))
    new_s = min(timeit.repeat(diagnostics.to_dict, number=10, repeat=3))
    assert new_s < old_s * 0.6, (new_s, old_s)
    diagnostics.details.clear()
    assert actual == expected


def test_trace_sealing_has_bounded_memory_and_preserves_all_frames(tmp_path):
    sink = TraceSink.open(tmp_path, policy=TraceSinkPolicy(worker=False, max_total_bytes=32 * 1024**2))
    for sequence in range(16):
        sink.append(
            SimpleNamespace(
                sequence=sequence,
                sim_time=float(sequence),
                step_time_ms=1.0,
                state=SessionState.RUNNING,
                payload={"data": "0123456789" * 65536},
                events=[],
            )
        )
    tracemalloc.start()
    try:
        index = sink.close(events=[])
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert index["state"] == "READY"
    assert index["tick_count"] == 16
    assert peak < 4 * 1024**2, f"Trace sealing allocated {peak} bytes for a 10 MiB file"
    digest = hashlib.sha256()
    with gzip.open(tmp_path / "decision/frames.jsonl.gz", "rb") as stream:
        for sequence, line in enumerate(stream):
            digest.update(line)
            record = json.loads(line)
            assert record["sequence"] == sequence
            assert record["payload"]["data"] == "0123456789" * 65536
    assert sequence == 15
    assert digest.hexdigest() == index["frames_sha256"]
