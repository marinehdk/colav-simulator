"""Evidence bundle persistence for experiment runs."""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import math
import queue
import subprocess
import sys
import threading
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from colav_simulator.evaluation.evaluator import EvaluatorResult
from colav_simulator.experiment.contracts import RunManifest, canonical_json

TRAJECTORY_COLUMNS = [
    "sim_time",
    "ship_key",
    "ship_id",
    "mmsi",
    "north_m",
    "east_m",
    "sog_mps",
    "cog_rad",
    "psi_rad",
    "surge_mps",
    "sway_mps",
    "yaw_rate_radps",
    "active",
    "control_json",
    "references_json",
    "waypoints_json",
    "tracks_json",
    "measurements_json",
    "colav_json",
    "planner_solve_id",
    "planner_solver_executed",
    "applied_course_ref_rad",
    "applied_speed_ref_mps",
    "control_0",
    "control_1",
    "control_2",
]


def jsonable(value: Any) -> Any:
    """Convert nested project values into stable JSON-compatible values."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (Path, Enum)):
        return value.value if isinstance(value, Enum) else str(value)
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if hasattr(value, "to_dict"):
        return jsonable(value.to_dict())
    return {"type": type(value).__name__, "repr": repr(value)}


class EvidenceWriter:
    """Write one complete, machine-readable evidence directory."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=False)

    def write_manifest(self, manifest: RunManifest) -> Path:
        return self._write_json("manifest.json", manifest.to_dict())

    def write_episode(self, episode: dict[str, Any]) -> Path:
        return self._write_json("episode.json", episode)

    def write_run_metrics(self, metrics: dict[str, Any]) -> Path:
        """Write separated Ship0, global-world, and traffic-load evidence."""
        return self._write_json("run_metrics.json", metrics)

    def write_events(self, events: list[dict[str, Any]]) -> Path:
        path = self.run_dir / "events.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(canonical_json(jsonable(event)))
                stream.write("\n")
        return path

    def append_lifecycle_event(self, event: Any) -> Path:
        """Durably append one planner lifecycle transition."""
        path = self.run_dir / "lifecycle_events.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(jsonable(event)))
            stream.write("\n")
            stream.flush()
        return path

    def write_mid_mpc_artifact(self, document: Any) -> dict[str, Any]:
        """Persist one canonical content-addressed Mid-MPC replay artifact."""
        payload = canonical_json(jsonable(document)).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        return self.write_mid_mpc_payload(payload, digest)

    def write_mid_mpc_payload(self, payload: bytes, digest: str) -> dict[str, Any]:
        """Persist pre-serialized Mid-MPC evidence with a verified digest."""
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError("Mid-MPC payload digest mismatch")
        directory = self.run_dir / "artifacts" / "mid_mpc"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{digest}.json.gz"
        if not path.exists():
            staging = directory / f".{digest}.tmp"
            staging.write_bytes(gzip.compress(payload, mtime=0))
            staging.replace(path)
        return {
            "schema_version": "1.0",
            "sha256": digest,
            "relative_path": str(path.relative_to(self.run_dir)),
            "compressed_bytes": path.stat().st_size,
        }

    def write_trajectory(self, frames: list[dict[str, Any]]) -> Path:
        rows: list[dict[str, Any]] = []
        for frame in frames:
            ship_keys = sorted(key for key in frame if key.startswith("Ship"))
            for ship_key in ship_keys:
                ship = frame[ship_key]
                if not ship:
                    continue
                csog = np.asarray(ship.get("csog_state", np.full(4, np.nan)), dtype=float)
                state = np.asarray(ship.get("state", np.full(6, np.nan)), dtype=float)
                control = np.asarray(ship.get("input", np.full(3, np.nan)), dtype=float)
                references = np.asarray(ship.get("references", np.full(9, np.nan)), dtype=float)
                colav_summary = _trajectory_colav_summary(ship.get("colav"))
                planner = colav_summary.get("planner", {})
                row = {
                    "sim_time": float(ship.get("timestamp", np.nan)),
                    "ship_key": ship_key,
                    "ship_id": int(ship.get("id", -1)),
                    "mmsi": int(ship.get("mmsi", -1)),
                    "north_m": float(csog[0]),
                    "east_m": float(csog[1]),
                    "sog_mps": float(csog[2]),
                    "cog_rad": float(csog[3]),
                    "psi_rad": float(state[2]),
                    "surge_mps": float(state[3]),
                    "sway_mps": float(state[4]),
                    "yaw_rate_radps": float(state[5]),
                    "active": bool(ship.get("active", False)),
                    "control_json": canonical_json(jsonable(control)),
                    "references_json": canonical_json(jsonable(references)),
                    "waypoints_json": canonical_json(jsonable(ship.get("waypoints"))),
                    "tracks_json": canonical_json(
                        jsonable(
                            {
                                "labels": ship.get("do_labels"),
                                "states": ship.get("do_estimates"),
                                "covariances": ship.get("do_covariances"),
                                "nis": ship.get("do_NISes"),
                            }
                        )
                    ),
                    "measurements_json": canonical_json(jsonable(ship.get("sensor_measurements"))),
                    "colav_json": canonical_json(jsonable(colav_summary)),
                    "planner_solve_id": int(planner.get("solve_id", 0)),
                    "planner_solver_executed": bool(planner.get("solver_executed", False)),
                    "applied_course_ref_rad": float(references[2]) if references.size > 2 else np.nan,
                    "applied_speed_ref_mps": float(references[3]) if references.size > 3 else np.nan,
                }
                for index in range(min(control.size, 3)):
                    row[f"control_{index}"] = float(control[index])
                rows.append(row)
        path = self.run_dir / "trajectory.parquet"
        staging = self.run_dir / ".trajectory.rows.jsonl"
        with staging.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(canonical_json(row))
                stream.write("\n")
        script = (
            "import json, pandas as pd, pathlib, sys; "
            "source=pathlib.Path(sys.argv[1]); "
            "df=(pd.read_json(source, lines=True) if source.stat().st_size "
            "else pd.DataFrame(columns=json.loads(sys.argv[3]))); "
            "df.to_parquet(sys.argv[2], index=False, engine='pyarrow')"
        )
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    script,
                    str(staging),
                    str(path),
                    json.dumps(TRAJECTORY_COLUMNS),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Parquet writer failed: {exc.stderr.strip()}") from exc
        finally:
            staging.unlink(missing_ok=True)
        return path

    def write_evaluation(self, result: EvaluatorResult) -> Path:
        return self._write_json("evaluation.json", result.to_dict())

    def write_failed_evaluation(self, reason: str, status: str) -> Path:
        return self._write_json(
            "evaluation.json",
            {
                "schema_version": "2.0",
                "evaluation_status": "NOT_EVALUATED",
                "failure_status": status,
                "failure_reason": reason,
                "hard_gate": {
                    "outcome": "FAIL",
                    "checks": [
                        {
                            "check_id": "run_completion",
                            "outcome": "FAIL",
                            "reason": reason,
                            "evidence": {"failure_status": status},
                        }
                    ],
                },
                "scores": {"status": "NOT_EVALUATED"},
                "diagnostics": {"execution": {"failure_status": status, "failure_reason": reason}},
            },
        )

    def write_report(self, manifest: RunManifest, evaluation: EvaluatorResult) -> Path:
        aggregate_rows = "".join(
            f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
            for key, value in evaluation.aggregate.items()
        )
        pair_rows = "".join(
            "<tr>"
            f"<td>{pair.ownship_id}</td><td>{pair.target_id}</td>"
            f"<td>{html.escape(pair.encounter)}</td>"
            f"<td>{pair.minimum_distance_m:.2f}</td><td>{pair.initial_tcpa_s:.2f}</td>"
            f"<td>{'yes' if pair.collision else 'no'}</td>"
            "</tr>"
            for pair in evaluation.pair_results
        )
        warning_items = "".join(f"<li>{html.escape(warning)}</li>" for warning in evaluation.warnings)
        gate_rows = "".join(
            "<tr>"
            f"<td>{html.escape(check.check_id)}</td>"
            f"<td>{html.escape(check.outcome.value)}</td>"
            f"<td>{html.escape(check.reason)}</td>"
            "</tr>"
            for check in evaluation.hard_gate.checks
        )
        score_rows = "".join(
            "<tr>"
            f"<td>{pair.ownship_id}->{pair.target_id}</td>"
            f"<td>{html.escape(str(pair.metrics.get('S_safety')))}</td>"
            f"<td>{html.escape(str(pair.metrics.get('S13')))}</td>"
            f"<td>{html.escape(str(pair.metrics.get('S14')))}</td>"
            f"<td>{html.escape(str(pair.metrics.get('S15')))}</td>"
            f"<td>{html.escape(str(pair.metrics.get('S16')))}</td>"
            f"<td>{html.escape(str(pair.metrics.get('S17')))}</td>"
            "</tr>"
            for pair in evaluation.pair_results
        )
        document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>COLAV Run {manifest.run_id}</title>
<style>body{{font:14px system-ui;margin:32px;color:#17202a}}table{{border-collapse:collapse;width:100%;margin:16px 0}}
th,td{{border:1px solid #ccd1d1;padding:7px;text-align:left}}th{{background:#eef2f3}}code{{font-family:ui-monospace}}</style>
</head><body><h1>COLAV Experiment Report</h1>
<p>Run <code>{manifest.run_id}</code> · scenario <code>{html.escape(manifest.spec["scenario_id"])}</code>
 · algorithm <code>{html.escape(manifest.executed_algorithm)}</code></p>
<p>Reproduction status: <strong>{html.escape(evaluation.reproduction_status)}</strong></p>
<p>Evaluator profile: <code>{html.escape(evaluation.evaluator_profile_id)}</code>
 · formula set <code>{html.escape(evaluation.formula_set_id)}</code>
 · collision oracle <code>{html.escape(evaluation.collision_oracle_id)}</code></p>
<h2>Hard gate: {html.escape(evaluation.hard_gate.outcome.value)}</h2>
<table><thead><tr><th>Check</th><th>Outcome</th><th>Reason</th></tr></thead><tbody>{gate_rows}</tbody></table>
<h2>Aggregate</h2><table>{aggregate_rows}</table>
<h2>Vessel pairs</h2><table><thead><tr><th>OS</th><th>TS</th><th>Encounter</th>
<th>Minimum distance (m)</th><th>Initial TCPA (s)</th><th>Collision</th></tr></thead><tbody>{pair_rows}</tbody></table>
<h2>COLREG scores</h2><table><thead><tr><th>Pair</th><th>Safety</th><th>R13</th><th>R14</th>
<th>R15</th><th>R16</th><th>R17</th></tr></thead><tbody>{score_rows}</tbody></table>
<h2>Limitations</h2><ul>{warning_items}</ul></body></html>"""
        path = self.run_dir / "report.html"
        path.write_text(document, encoding="utf-8")
        return path

    def write_failure_report(self, manifest: RunManifest) -> Path:
        document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Failed COLAV Run {manifest.run_id}</title>
<style>body{{font:14px system-ui;margin:32px;color:#17202a}}code{{font-family:ui-monospace}}</style>
</head><body><h1>COLAV Experiment Failed</h1>
<p>Run <code>{manifest.run_id}</code></p>
<p>Status: <strong>{html.escape(manifest.failure_status or "UNKNOWN")}</strong></p>
<p>{html.escape(manifest.failure_reason or "No failure reason recorded.")}</p>
<p>No algorithm fallback was used.</p></body></html>"""
        path = self.run_dir / "report.html"
        path.write_text(document, encoding="utf-8")
        return path

    def _write_json(self, filename: str, value: Any) -> Path:
        path = self.run_dir / filename
        path.write_text(json.dumps(jsonable(value), indent=2, sort_keys=True), encoding="utf-8")
        return path


class BoundedArtifactSink:
    """Bounded asynchronous Mid-MPC artifact persistence."""

    def __init__(
        self,
        writer: EvidenceWriter,
        *,
        max_artifact_bytes: int = 16 * 1024 * 1024,
        max_items: int = 32,
        max_bytes: int = 64 * 1024 * 1024,
        retention: int = 256,
        start_worker: bool = True,
    ) -> None:
        if min(max_artifact_bytes, max_items, max_bytes, retention) <= 0:
            raise ValueError("artifact sink limits must be positive")
        self._writer = writer
        self._max_artifact_bytes = max_artifact_bytes
        self._max_bytes = max_bytes
        self._retention = retention
        self._queue: queue.Queue[tuple[bytes, str, dict[str, Any]]] = queue.Queue(maxsize=max_items)
        self._lock = threading.Lock()
        self._queued_bytes = 0
        self._closed = False
        self._written = 0
        self._failures = 0
        self._active: tuple[int, int, dict[str, Any]] | None = None
        self._timed_out_references: set[int] = set()
        self._worker = threading.Thread(target=self._run, name="mid-mpc-artifacts", daemon=True) if start_worker else None
        if self._worker is not None:
            self._worker.start()

    def __call__(self, document: Any) -> dict[str, Any]:
        payload = canonical_json(jsonable(document)).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        reference: dict[str, Any] = {
            "schema_version": "1.0",
            "sha256": digest,
            "relative_path": f"artifacts/mid_mpc/{digest}.json.gz",
            "uncompressed_bytes": len(payload),
            "status": "QUEUED",
        }
        if len(payload) > self._max_artifact_bytes:
            reference.update(status="INCOMPLETE", reason="ARTIFACT_TOO_LARGE")
            self._failures += 1
            return reference
        with self._lock:
            if self._closed:
                reference.update(status="INCOMPLETE", reason="SINK_CLOSED")
                self._failures += 1
                return reference
            if self._queue.full():
                reference.update(status="BACKPRESSURE", reason="ITEM_CAPACITY")
                self._failures += 1
                return reference
            if self._queued_bytes + len(payload) > self._max_bytes:
                reference.update(status="BACKPRESSURE", reason="BYTE_CAPACITY")
                self._failures += 1
                return reference
            self._queued_bytes += len(payload)
            self._queue.put_nowait((payload, digest, reference))
        return reference

    def close(self, *, timeout_s: float = 2.0) -> dict[str, Any]:
        """Stop admission and drain queued work for at most timeout_s."""
        with self._lock:
            self._closed = True
        deadline = time.monotonic() + max(0.0, timeout_s)
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.005)
        if self._queue.unfinished_tasks:
            with self._lock:
                if self._active is not None:
                    reference_id, payload_size, reference = self._active
                    if reference_id not in self._timed_out_references:
                        reference.update(status="INCOMPLETE", reason="DRAIN_TIMEOUT")
                        self._timed_out_references.add(reference_id)
                        self._queued_bytes -= payload_size
                        self._failures += 1
                while True:
                    try:
                        payload, _digest, reference = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    reference.update(status="INCOMPLETE", reason="DRAIN_TIMEOUT")
                    self._queued_bytes -= len(payload)
                    self._failures += 1
                    self._queue.task_done()
        if self._worker is not None:
            self._worker.join(timeout=max(0.0, deadline - time.monotonic()))
        return {
            "status": "COMPLETE" if self._failures == 0 else "INCOMPLETE",
            "written": self._written,
            "failures": self._failures,
            "queued_items": self._queue.qsize(),
            "queued_bytes": self._queued_bytes,
        }

    def _run(self) -> None:
        while True:
            with self._lock:
                if self._closed and self._queue.empty():
                    return
                try:
                    payload, digest, reference = self._queue.get_nowait()
                except queue.Empty:
                    payload = b""
                else:
                    self._active = (id(reference), len(payload), reference)
            if not payload:
                time.sleep(0.05)
                continue
            persisted: dict[str, Any] | None = None
            failure_reason: str | None = None
            try:
                persisted = self._writer.write_mid_mpc_payload(payload, digest)
            except Exception as exc:
                failure_reason = str(exc)
            finally:
                with self._lock:
                    reference_id = id(reference)
                    timed_out = reference_id in self._timed_out_references
                    if timed_out:
                        self._timed_out_references.remove(reference_id)
                    else:
                        self._queued_bytes -= len(payload)
                        if failure_reason is None:
                            reference.update(persisted or {})
                            reference["status"] = "COMPLETE"
                            self._written += 1
                        else:
                            reference.update(status="INCOMPLETE", reason=failure_reason)
                            self._failures += 1
                    self._active = None
                self._queue.task_done()
            if failure_reason is None and not timed_out:
                self._enforce_retention()

    def _enforce_retention(self) -> None:
        directory = self._writer.run_dir / "artifacts" / "mid_mpc"
        artifacts = sorted(directory.glob("*.json.gz"), key=lambda path: (path.stat().st_mtime_ns, path.name))
        for path in artifacts[: -self._retention]:
            path.unlink(missing_ok=True)


def _trajectory_colav_summary(value: Any) -> dict[str, Any]:
    document = jsonable(value) or {}
    if not isinstance(document, dict):
        return {}
    planner = document.get("planner")
    if not isinstance(planner, dict):
        return document
    document["planner"] = {
        key: planner.get(key)
        for key in (
            "schema_version",
            "algorithm_id",
            "solve_id",
            "sim_time",
            "solver_executed",
            "status",
            "feasible",
            "reason",
            "elapsed_ms",
            "iterations",
            "objective",
            "horizon_dt_s",
            "selected_command",
        )
    }
    return document
