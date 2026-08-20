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
    completions = sink.poll_completions()

    assert summary["status"] == "COMPLETE"
    assert summary["written"] == 3
    artifact_dir = writer.run_dir / "artifacts" / "mid_mpc"
    artifacts = sorted(artifact_dir.glob("*.json.gz"))
    assert len(artifacts) == 2
    assert not list(artifact_dir.glob(".*.tmp"))
    assert all(reference["status"] == "QUEUED" for reference in references)
    assert {item["status"] for item in completions} == {"COMPLETE"}
    assert {item["submission_id"] for item in completions} == {reference["submission_id"] for reference in references}


def test_artifact_worker_uses_an_immutable_descriptor_copy(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")
    sink = BoundedArtifactSink(writer, start_worker=False)
    reference = sink({"payload": "accepted"})
    original_submission_id = reference["submission_id"]
    reference["submission_id"] = "caller-mutated"
    sink.close(timeout_s=0.0)
    completion = sink.poll_completions()[0]

    assert completion["submission_id"] == original_submission_id


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
    summary = sink.close(timeout_s=0.0)
    completions = sink.poll_completions()

    assert first["status"] == "QUEUED"
    assert item_backpressure["status"] == "BACKPRESSURE"
    assert item_backpressure["reason"] == "ITEM_CAPACITY"
    assert artifact_too_large["status"] == "INCOMPLETE"
    assert artifact_too_large["reason"] == "ARTIFACT_TOO_LARGE"
    assert completions == [
        {
            **first,
            "status": "INCOMPLETE",
            "reason": "DRAIN_TIMEOUT",
        }
    ]
    assert summary["status"] == "INCOMPLETE"


def test_bounded_artifact_sink_reports_write_failure_without_raising(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path / "run")

    def fail_write(_payload: bytes, _digest: str) -> dict[str, object]:
        raise OSError("disk unavailable")

    writer.write_mid_mpc_payload = fail_write  # type: ignore[method-assign]
    sink = BoundedArtifactSink(writer)
    reference = sink({"payload": "accepted"})

    deadline = time.monotonic() + 2.0
    completions = []
    while not completions and time.monotonic() < deadline:
        completions = sink.poll_completions()
        time.sleep(0.01)
    summary = sink.close(timeout_s=2.0)

    assert reference["status"] == "QUEUED"
    assert completions[0]["status"] == "INCOMPLETE"
    assert "disk unavailable" in str(completions[0]["reason"])
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
    completion = sink.poll_completions()[0]
    release.set()
    time.sleep(0.05)

    assert summary == {
        "status": "INCOMPLETE",
        "written": 0,
        "failures": 1,
        "queued_items": 0,
        "queued_bytes": 0,
    }
    assert reference["status"] == "QUEUED"
    assert completion["status"] == "INCOMPLETE"
    assert completion["reason"] == "DRAIN_TIMEOUT"
    assert sink.poll_completions() == []
