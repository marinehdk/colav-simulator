"""Reduce full topic evidence to comparable navigation and actuation samples."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from trace_io import open_trace


def integration_epoch(directory: Path, kind: str) -> dict:
    """Read the actual initialization clock used by the original plant integrator."""
    if kind in {"embedded", "original_source_coupled"}:
        return {
            "epoch_ns": json.loads((directory / "manifest.json").read_text())["epoch_ns"],
            "source": "common scheduler explicit construction epoch",
        }
    with open_trace(directory / "callback-traces/ship_dynamics_node.jsonl") as stream:
        for line in stream:
            record = json.loads(line)
            if record.get("kind") == "clock" and record.get("site") == "ship_dynamics_node.cpp:120":
                return {
                    "epoch_ns": record["nanoseconds"],
                    "source": "original last_time_ construction clock",
                    "clock_record": record,
                }
            if record.get("kind") == "call":
                break
    raise ValueError("Missing original plant initialization clock; cannot align free-run time")


# Keep source contract branches together for audit against the frozen implementation.
def extract(directory: Path, output: Path, case: Path | None = None) -> dict:  # noqa: PLR0912, PLR0915
    """Keep source timestamps and full-rate observations; perform no trajectory fit."""
    path = directory / "topic-observations.jsonl"
    if not path.exists():
        path = path.with_suffix(".jsonl.gz")
    if not path.exists():
        raise FileNotFoundError(path)
    opener = gzip.open if path.suffix == ".gz" else open
    arrays = {
        name: []
        for name in ("navigation", "commands", "allocation", "dp_hold", "speed_reference", "heading_reference", "guidance")
    }
    times = {name: [] for name in arrays}
    modes = []
    counts = {}
    digest = hashlib.sha256()
    source_kind = None
    manifest_path = directory / "manifest.json"
    runtime_kind = json.loads(manifest_path.read_text()).get("runtime_kind") if manifest_path.exists() else None
    with opener(path, "rb") as stream:
        for raw in stream:
            digest.update(raw)
            row = json.loads(raw)
            topic = row["topic"]
            counts[topic] = counts.get(topic, 0) + 1
            embedded = "event" in row
            source_kind = (runtime_kind or "embedded") if embedded else "native_ros"
            fields = row["message"]["fields"] if embedded else row["message"]
            stamp = fields.get("header", {}).get("stamp")
            ns = (
                (stamp["sec"] * 10**9 + stamp["nanosec"])
                if stamp
                else (row["time_ns"] if embedded else row["receipt_ros_time_ns"])
            )
            name = None
            value = None
            if topic == "/ship/odometry":
                name = "navigation"
                pose = fields["pose"]["pose"]
                twist = fields["twist"]["twist"]
                q = pose["orientation"]
                yaw = math.atan2(2 * (q["w"] * q["z"] + q["x"] * q["y"]), 1 - 2 * (q["y"] ** 2 + q["z"] ** 2))
                roll = math.atan2(2 * (q["w"] * q["x"] + q["y"] * q["z"]), 1 - 2 * (q["x"] ** 2 + q["y"] ** 2))
                value = [
                    pose["position"]["x"],
                    pose["position"]["y"],
                    yaw,
                    twist["linear"]["x"],
                    twist["linear"]["y"],
                    twist["angular"]["z"],
                    roll,
                ]
            elif topic == "/thruster/commands":
                name = "commands"
                value = fields["data"]
            elif topic == "/allocation/status":
                name = "allocation"
                entry = next(x for x in fields["status"] if x["name"] == "thrust_allocation/solution")
                values = {x["key"]: x["value"] for x in entry["values"]}
                value = [
                    float(values["degradation_level"]),
                    float(values["normalized_error"]),
                    float(entry["message"] == "allocation_saturated"),
                ]
            elif topic == "/guidance/dp_hold_active":
                name = "dp_hold"
                value = [int(fields["data"])]
            elif topic == "/control/speed_setpoint":
                name = "speed_reference"
                value = [fields["data"]]
            elif topic == "/control/heading_setpoint":
                name = "heading_reference"
                value = [fields["data"]]
            elif topic == "/diagnostics/ilos_guidance":
                guidance = json.loads(fields["data"])
                name = "guidance"
                value = [guidance["waypoint_index"], guidance["xte_m"], guidance["path_heading_deg"]]
            elif topic in ("/gnc/route_execution_status", "/route_planning/route_plan_status"):
                modes.append({"time_ns": ns, "topic": topic, "message": fields})
            if name is not None:
                times[name].append(ns)
                arrays[name].append(value)
    if not times["navigation"]:
        raise ValueError("No observed navigation samples")
    output.mkdir(parents=True, exist_ok=True)
    data = {}
    epoch = integration_epoch(directory, source_kind)
    data["epoch_ns"] = np.asarray(epoch["epoch_ns"], dtype=np.int64)
    for name, values in arrays.items():
        data[name] = np.asarray(values, dtype=float)
        data[name + "_time_ns"] = np.asarray(times[name], dtype=np.int64)
    np.savez_compressed(output / "samples.npz", **data)
    case_path = case or directory / "case.json"
    case_doc = json.loads(case_path.read_text())
    (output / "case.json").write_text(json.dumps(case_doc, indent=2))
    metadata = {
        "source_directory": str(directory),
        "kind": source_kind,
        "integration_epoch": epoch,
        "case_id": case_doc["case_id"],
        "topic_trace_uncompressed_sha256": digest.hexdigest(),
        "topic_counts": counts,
        "columns": {
            "navigation": ["north_m", "east_m", "heading_rad", "surge_mps", "sway_mps", "yaw_rate_radps", "roll_rad"],
            "allocation": ["degradation_level", "normalized_error", "allocation_saturated"],
            "guidance": ["waypoint_index", "active_segment_xte_m", "path_heading_deg"],
        },
        "time_basis": "message header where present, otherwise native receipt or embedded publication timestamp",
        "samples_sha256": hashlib.sha256((output / "samples.npz").read_bytes()).hexdigest(),
        "route_events": modes,
    }
    (output / "manifest.json").write_text(json.dumps(metadata, indent=2))
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", type=Path)
    args = parser.parse_args()
    extract(args.directory, args.output, args.case)
