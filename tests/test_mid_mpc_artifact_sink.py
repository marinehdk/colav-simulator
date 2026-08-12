import json
import threading
import time
from pathlib import Path

from colav_simulator.experiment.persistence import BoundedArtifactSink, EvidenceWriter


def test_bounded_artifact_sink_writes_atomically_and_enforces_retention(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")
    sink = BoundedArtifactSink(writer, max_items=4, max_bytes=1_000_000, retention=2)

    references = [sink({"sequence": sequence}) for sequence in range(3)]
    summary = sink.close(timeout_s=2.0)

    assert summary["status"] == "COMPLETE"
    assert summary["written"] == 3
    artifact_dir = writer.run_dir / "artifacts" / "mid_mpc"
    artifacts = sorted(artifact_dir.glob("*.json.gz"))
    assert len(artifacts) == 2
    assert not list(artifact_dir.glob(".*.tmp"))
    assert all(reference["status"] == "COMPLETE" for reference in references)


def test_bounded_artifact_sink_reports_item_byte_and_artifact_limits(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")
    sink = BoundedArtifactSink(
        writer,
        max_artifact_bytes=100,
        max_items=1,
        max_bytes=200,
        retention=2,
        start_worker=False,
    )

    first = sink({"payload": "a" * 50})
    item_backpressure = sink({"payload": "b" * 50})
    artifact_too_large = sink({"payload": "c" * 200})
    first_status = first["status"]
    summary = sink.close(timeout_s=0.0)

    assert first_status == "QUEUED"
    assert first["status"] == "INCOMPLETE"
    assert item_backpressure["status"] == "BACKPRESSURE"
    assert item_backpressure["reason"] == "ITEM_CAPACITY"
    assert artifact_too_large["status"] == "INCOMPLETE"
    assert artifact_too_large["reason"] == "ARTIFACT_TOO_LARGE"
    assert summary["status"] == "INCOMPLETE"


def test_bounded_artifact_sink_reports_write_failure_without_raising(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")

    def fail_write(_payload: bytes, _digest: str) -> dict[str, object]:
        raise OSError("disk unavailable")

    writer.write_mid_mpc_payload = fail_write  # type: ignore[method-assign]
    sink = BoundedArtifactSink(writer)
    reference = sink({"payload": "accepted"})

    deadline = time.monotonic() + 2.0
    while reference["status"] == "QUEUED" and time.monotonic() < deadline:
        time.sleep(0.01)
    summary = sink.close(timeout_s=2.0)

    assert reference["status"] == "INCOMPLETE"
    assert "disk unavailable" in str(reference["reason"])
    assert summary["status"] == "INCOMPLETE"
    json.dumps(reference, allow_nan=False)


def test_bounded_artifact_sink_close_timeout_freezes_inflight_reference(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")
    entered = threading.Event()
    release = threading.Event()
    original_write = writer.write_mid_mpc_payload

    def slow_write(payload: bytes, digest: str) -> dict[str, object]:
        entered.set()
        release.wait(timeout=2.0)
        return original_write(payload, digest)

    writer.write_mid_mpc_payload = slow_write  # type: ignore[method-assign]
    sink = BoundedArtifactSink(writer)
    reference = sink({"payload": "accepted"})
    assert entered.wait(timeout=1.0)

    summary = sink.close(timeout_s=0.0)
    frozen = dict(reference)
    release.set()
    time.sleep(0.05)

    assert summary == {
        "status": "INCOMPLETE",
        "written": 0,
        "failures": 1,
        "queued_items": 0,
        "queued_bytes": 0,
    }
    assert frozen["status"] == "INCOMPLETE"
    assert frozen["reason"] == "DRAIN_TIMEOUT"
    assert reference == frozen
