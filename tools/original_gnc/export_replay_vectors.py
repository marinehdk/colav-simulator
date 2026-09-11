"""Decode independent original traces into ROS-free, per-callback vectors."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from replay_native_trace import VALUE_KEYS, decoded
from trace_io import open_trace, trace_sha256


def portable(value: Any) -> Any:
    """Preserve deliberate nonfinite sentinels without invalid JSON numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"$nonfinite": "nan" if math.isnan(value) else "+inf" if value > 0 else "-inf"}
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item) for item in value]
    return value


# Keep source contract branches together for audit against the frozen implementation.
def export(native_run: Path, output: Path, nodes: list[str], reference_replay: Path | None = None) -> dict:  # noqa: C901, PLR0912, PLR0915
    """Retain inputs, clock reads, and expected original emitted fields."""
    output.mkdir(parents=True, exist_ok=True)
    parameters = json.loads((native_run / "effective-parameters.json").read_text())
    run_manifest = json.loads((native_run / "manifest.json").read_text())
    workspace = Path(run_manifest["source_staging"]["workspace"]).resolve()
    source_asset_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in (workspace / "src").rglob("*.csv")}
    if reference_replay:
        reference_report = json.loads((reference_replay / "comparison.json").read_text())
        if not reference_report["passed"] or Path(reference_report["native_run"]).resolve() != native_run.resolve():
            raise ValueError("State vectors require a successful independent replay of this native run")
    results = {}
    for name in nodes:
        trace = native_run / "callback-traces" / f"{name}.jsonl"
        events = [json.loads(line) for line in open_trace(trace)]
        calls = []
        current = None
        depth = 0
        initial_outputs = []
        assets = {}
        for event in events:
            if event["kind"] == "call":
                if depth == 0:
                    current = {
                        "ordinal": event["ordinal"],
                        "function": event["function"],
                        "input": decoded(event["input"]) if event.get("input") else None,
                        "outputs": [],
                    }
                depth += 1
            elif event["kind"] == "publish":
                record = {
                    "port": event["port"],
                    "message": {"type": event["message"]["type"], "fields": decoded(event["message"])},
                }
                statuses = (
                    record["message"]["fields"].get("status", [])
                    if event["message"]["type"].endswith("/DiagnosticArray")
                    else []
                )
                for status in statuses:
                    for value in status.get("values", []):
                        if value.get("key") == "source_csv" and value["value"] not in assets:
                            asset = Path(value["value"]).resolve()
                            if asset.suffix != ".csv" or not asset.is_file():
                                raise ValueError(f"Unrecognized reference asset path: {asset}")
                            digest = hashlib.sha256(asset.read_bytes()).hexdigest()
                            if digest not in source_asset_hashes:
                                raise ValueError(f"Reference asset differs from frozen source: {asset}")
                            assets[value["value"]] = digest
                (current["outputs"] if depth else initial_outputs).append(record)
            elif event["kind"] == "return":
                depth -= 1
                if depth == 0:
                    calls.append(current)
                    current = None
        if depth != 0:
            raise ValueError(f"Incomplete recorded callback in {name}")
        typed = {
            key: {"type": value["type"], "value": value[VALUE_KEYS[value["type"]]]}
            for key, value in parameters[f"/{name}"].items()
            if value["type"] != 0
        }
        for key in (
            "coeffs_csv_path",
            "qtf_csv_path",
            "asset_manifest_path",
            "wave_rao_manifest_path",
            "wave_qtf_manifest_path",
        ):
            location = typed.get(key, {}).get("value", "")
            if location:
                asset = Path(location).resolve()
                if workspace not in asset.parents or not asset.is_file():
                    raise ValueError(f"Missing or unrecognized original asset: {location}")
                assets[location] = hashlib.sha256(asset.read_bytes()).hexdigest()
        vector = {
            "schema": "original-gnc.callback-vectors.v1",
            "module": name,
            "parameters": typed,
            "source_trace_sha256": trace_sha256(trace),
            "clock_reads": [{"site": e["site"], "nanoseconds": e["nanoseconds"]} for e in events if e["kind"] == "clock"],
            "initial_outputs": initial_outputs,
            "calls": calls,
            "assets": assets,
        }
        if reference_replay:
            state_path = reference_replay / f"{name}-states.jsonl"
            state_records = [json.loads(line) for line in open_trace(state_path)]
            states = {record["ordinal"]: record["state"] for record in state_records}
            if set(states) != {-1, *(call["ordinal"] for call in calls)}:
                raise ValueError(f"Reference state coverage differs from callback coverage: {name}")
            vector["initial_state"] = states[-1]
            for call in calls:
                call["state"] = states[call["ordinal"]]
            vector["reference_state_sha256"] = trace_sha256(state_path)
            vector["schema"] = "original-gnc.callback-vectors.v2"
        path = output / f"{name}.json.gz"
        with path.open("wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", mtime=0, compresslevel=3) as zipped:
            zipped.write(json.dumps(portable(vector), separators=(",", ":"), allow_nan=False).encode())
        results[name] = {"calls": len(calls), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (output / "manifest.json").write_text(json.dumps({"native_run": str(native_run), "modules": results}, indent=2))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--nodes",
        nargs="+",
        default=["ship_dynamics_node", "ship_control_node", "ship_guidance_node", "thrust_allocation_node"],
    )
    parser.add_argument("--reference-replay", type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.native_run, args.output, args.nodes, args.reference_replay), indent=2))
