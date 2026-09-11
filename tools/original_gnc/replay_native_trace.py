"""Replay recorded original callbacks and verify independently decoded outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
from contextlib import nullcontext
from itertools import zip_longest
from pathlib import Path
from typing import Any

import yaml
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.convert import message_to_ordereddict
from rosidl_runtime_py.utilities import get_message
from trace_io import archive_trace, materialize_trace, open_trace

VALUE_KEYS = {
    1: "bool_value",
    2: "integer_value",
    3: "double_value",
    4: "string_value",
    5: "byte_array_value",
    6: "bool_array_value",
    7: "integer_array_value",
    8: "double_array_value",
    9: "string_array_value",
}


def decoded(record: dict) -> dict:
    """Decode ROS CDR into fields so irrelevant wire padding is not compared."""
    message = deserialize_message(bytes.fromhex(record["cdr_hex"]), get_message(record["type"]))
    return message_to_ordereddict(message)


def first_difference(left: Any, right: Any, path: str = "") -> dict | None:  # noqa: PLR0911
    """Find an exact reference self-replay difference, preserving field paths."""
    if type(left) is not type(right):
        return {"path": path, "reference": repr(left), "replay": repr(right)}
    if left is right:
        return None
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return {"path": path, "kind": "field_set"}
        for key in left:
            difference = first_difference(left[key], right[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(left, (list, tuple)):
        if len(left) != len(right):
            return {"path": path, "kind": "array_length"}
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            difference = first_difference(a, b, f"{path}[{index}]")
            if difference:
                return difference
        return None
    # An identical native optional NaN sentinel is preserved as a sentinel,
    # never replaced by zero. Physical core fields are separately required
    # finite by the unit-aware acceptance comparator.
    if isinstance(left, float) and math.isnan(left) and math.isnan(right):
        return None
    if left != right:
        return {"path": path, "reference": left, "replay": right}
    return None


def compare(reference: Path, replay: Path) -> dict:
    """Compare every event; decode identical wire messages once, differing ones twice."""
    result = {
        "reference_events": 0,
        "replay_events": 0,
        "publications_checked": 0,
        "calls_checked": 0,
        "wire_identical_messages": 0,
        "passed": False,
        "first_difference": None,
    }
    right_context = (
        open_trace(replay)
        if replay.exists() or replay.with_suffix(replay.suffix + ".gz").exists()
        else nullcontext(iter(()))
    )
    with open_trace(reference) as left, right_context as right:
        for index, (left_line, right_line) in enumerate(zip_longest(left, right)):
            result["reference_events"] += left_line is not None
            result["replay_events"] += right_line is not None
            if left_line is None or right_line is None:
                if result["first_difference"] is None:
                    result["first_difference"] = {"kind": "record_count", "event_index": index}
                continue
            a, b = json.loads(left_line), json.loads(right_line)
            for key in ("input", "message"):
                if a.get(key) is not None and "cdr_hex" in a[key] and first_difference(a[key], b.get(key)) is None:
                    # Validate identical wire data once; share the decoded fields.
                    # Malformed identical payloads must still fail decoding.
                    shared = {"type": a[key]["type"], "fields": decoded(a[key])}
                    a, b = {**a, key: shared}, {**b, key: shared}
                    result["wire_identical_messages"] += 1
                    continue
                if a.get(key) is not None and "cdr_hex" in a[key]:
                    a = {**a, key: {"type": a[key]["type"], "fields": decoded(a[key])}}
                if b.get(key) is not None and "cdr_hex" in b[key]:
                    b = {**b, key: {"type": b[key]["type"], "fields": decoded(b[key])}}
            difference = first_difference(a, b)
            if difference and result["first_difference"] is None:
                result["first_difference"] = {"event_index": index, **difference}
            result["publications_checked"] += a["kind"] == "publish"
            result["calls_checked"] += a["kind"] == "call"
    result["passed"] = (
        result["first_difference"] is None and result["publications_checked"] > 0 and result["calls_checked"] > 0
    )
    return result


def replay_run(
    native_run: Path, drivers: Path, output: Path, nodes: list[str], *, domain: int = 174, timeout_s: float = 600.0
) -> dict:
    """Run each original node in a fresh process with its recorded clock reads."""
    if not nodes or not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("Replay needs nodes and a positive finite process timeout")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite replay evidence: {output}")
    output.mkdir(parents=True)
    parameters = json.loads((native_run / "effective-parameters.json").read_text())
    results = {}
    for node in nodes:
        values = {
            name: value[VALUE_KEYS[value["type"]]] for name, value in parameters[f"/{node}"].items() if value["type"] != 0
        }
        # Filesystem destinations are not numerical inputs. Preserve the R0
        # output directory instead of letting an original CSV writer alter it.
        for key in ("log_dir", "feedback_log_dir"):
            if key in values:
                values[key] = str(output / f"{node}-native-logs")
        config = output / f"{node}-parameters.yaml"
        # ROS YAML cannot encode the type of an empty array. Keep the original
        # declaration for those entries, then verify EVERY resulting typed
        # parameter in the C++ driver before invoking any callback.
        yaml_values = {key: value for key, value in values.items() if value != []}
        config.write_text(yaml.safe_dump({node: {"ros__parameters": yaml_values}}, sort_keys=False))
        typed = {name: {"type": parameters[f"/{node}"][name]["type"], "value": value} for name, value in values.items()}
        Path(str(config) + ".typed.json").write_text(json.dumps(typed, indent=2))
        reference = native_run / "callback-traces" / f"{node}.jsonl"
        replay_input = materialize_trace(reference, output / "archived-inputs" / reference.name)
        replay_dir = output / "callback-traces"
        command = [str(drivers / f"{node}_replay"), node, str(config)]
        env = {
            **os.environ,
            "ORIGINAL_GNC_REPLAY_FILE": str(replay_input),
            "ORIGINAL_GNC_TRACE_DIR": str(replay_dir),
            "ROS_DOMAIN_ID": str(domain),
            "ROS_LOCALHOST_ONLY": "1",
            "ROS_LOG_DIR": str(output / "ros-log"),
            "ORIGINAL_GNC_STATE_FILE": str(output / f"{node}-states.jsonl"),
        }
        try:
            with (output / f"{node}.log").open("w") as log:
                process = subprocess.run(
                    command, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=timeout_s, check=False
                )
            result = compare(reference, replay_dir / f"{node}.jsonl")
            result["exit_code"] = process.returncode
            result["passed"] = result["passed"] and process.returncode == 0
        except Exception as error:
            result = {"passed": False, "execution_or_comparison_error": repr(error)}
        finally:
            archived = {}
            for path in (
                output / "archived-inputs" / f"{node}.jsonl",
                replay_dir / f"{node}.jsonl",
                output / f"{node}-states.jsonl",
            ):
                if path.exists():
                    archived[str(path.relative_to(output))] = archive_trace(path)
        result["driver"] = str((drivers / f"{node}_replay").resolve())
        result["driver_sha256"] = hashlib.sha256((drivers / f"{node}_replay").read_bytes()).hexdigest()
        result["archived_files"] = archived
        results[node] = result
        (output / "partial-comparison.json").write_text(json.dumps({"complete": False, "nodes": results}, indent=2))
        if result.get("execution_or_comparison_error"):
            break
    report = {
        "schema": "original-gnc.reference-self-replay.v1",
        "domain_id": domain,
        "native_run": str(native_run),
        "passed": len(results) == len(nodes) and all(r["passed"] for r in results.values()),
        "requested_nodes": nodes,
        "process_timeout_s": timeout_s,
        "comparison_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "nodes": results,
        "embedded_code_executed": False,
    }
    archives = {name: identity for result in results.values() for name, identity in result["archived_files"].items()}
    (output / "archive-manifest.json").write_text(json.dumps(archives, indent=2))
    (output / "comparison.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-run", type=Path, required=True)
    parser.add_argument("--drivers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--nodes",
        nargs="+",
        default=["ship_dynamics_node", "ship_control_node", "ship_guidance_node", "thrust_allocation_node"],
    )
    parser.add_argument("--domain", type=int, default=174)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    report = replay_run(args.native_run, args.drivers, args.output, args.nodes, domain=args.domain, timeout_s=args.timeout)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
