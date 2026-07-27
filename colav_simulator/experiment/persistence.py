"""Evidence bundle persistence for experiment runs."""

from __future__ import annotations

import html
import json
import math
import subprocess
import sys
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

    def write_events(self, events: list[dict[str, Any]]) -> Path:
        path = self.run_dir / "events.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(canonical_json(jsonable(event)))
                stream.write("\n")
        return path

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
                "schema_version": "1.0",
                "status": "not_evaluated",
                "failure_status": status,
                "failure_reason": reason,
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
        document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>COLAV Run {manifest.run_id}</title>
<style>body{{font:14px system-ui;margin:32px;color:#17202a}}table{{border-collapse:collapse;width:100%;margin:16px 0}}
th,td{{border:1px solid #ccd1d1;padding:7px;text-align:left}}th{{background:#eef2f3}}code{{font-family:ui-monospace}}</style>
</head><body><h1>COLAV Experiment Report</h1>
<p>Run <code>{manifest.run_id}</code> · scenario <code>{html.escape(manifest.spec["scenario_id"])}</code>
 · algorithm <code>{html.escape(manifest.executed_algorithm)}</code></p>
<p>Reproduction status: <strong>{html.escape(evaluation.reproduction_status)}</strong></p>
<h2>Aggregate</h2><table>{aggregate_rows}</table>
<h2>Vessel pairs</h2><table><thead><tr><th>OS</th><th>TS</th><th>Encounter</th>
<th>Minimum distance (m)</th><th>Initial TCPA (s)</th><th>Collision</th></tr></thead><tbody>{pair_rows}</tbody></table>
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
