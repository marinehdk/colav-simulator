"""Captured Three-Ship frame: retain full evidence without Python leaf walks."""

import copy
import gzip
import json
import timeit
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from colav_simulator.core.colav.diagnostics import PlanDiagnostics, PlanStatus
from colav_simulator.decision_replay.sink import TraceSink
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
