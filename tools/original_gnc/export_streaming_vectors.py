"""Export verified original callbacks and states directly to bounded-memory v3 vectors."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from export_replay_vectors import portable
from replay_native_trace import VALUE_KEYS, decoded
from trace_io import trace_sha256


@contextmanager
def records(path: Path):
    """Yield original bytes and decoded records from raw or archived evidence."""
    stream = path.open("rb") if path.exists() else gzip.open(path.with_suffix(path.suffix + ".gz"), "rb")
    with stream:
        yield ((raw, json.loads(raw)) for raw in stream)


def file_digest(path: Path) -> str:
    """Hash potentially large compressed vectors in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for raw in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(raw)
    return digest.hexdigest()


def source_assets(fields: dict, assets: dict, allowed: set[str]) -> None:
    """Bind source CSV references to actual frozen file contents."""
    for status in fields.get("status", []):
        for value in status.get("values", []):
            if value.get("key") == "source_csv" and value["value"] not in assets:
                path = Path(value["value"]).resolve()
                if path.suffix != ".csv" or not path.is_file():
                    raise ValueError(f"Unknown source asset: {path}")
                digest = file_digest(path)
                if digest not in allowed:
                    raise ValueError(f"Source asset differs from frozen content: {path}")
                assets[value["value"]] = digest


# Keep paired trace/state transitions together so ordinal validation is auditable.
def export_node(  # noqa: C901, PLR0912, PLR0915
    native: Path, replay: Path, node: str, parameters: dict, workspace: Path, output: Path
) -> dict:
    """Scan clocks once, then emit one validated top-level callback at a time."""
    trace = native / "callback-traces" / f"{node}.jsonl"
    state_path = replay / f"{node}-states.jsonl"
    clocks = []
    initial = []
    assets = {}
    allowed = {file_digest(path) for path in (workspace / "src").rglob("*.csv")}
    digest = hashlib.sha256()
    depth = 0
    count = 0
    with records(trace) as events:
        for raw, event in events:
            digest.update(raw)
            kind = event["kind"]
            if kind == "clock":
                clocks.append({"site": event["site"], "nanoseconds": event["nanoseconds"]})
            elif kind == "call":
                count += depth == 0
                depth += 1
            elif kind == "return":
                depth -= 1
                if depth < 0:
                    raise ValueError("Unmatched source return")
            elif kind == "publish":
                message = event["message"]
                fields = decoded(message) if depth == 0 or message["type"].endswith("/DiagnosticArray") else None
                if fields is not None:
                    source_assets(fields, assets, allowed)
                if depth == 0:
                    if count:
                        raise ValueError("Unexpected publication outside callbacks after initialization")
                    initial.append({"port": event["port"], "message": {"type": message["type"], "fields": fields}})
    if depth or not count:
        raise ValueError("Incomplete or empty source callbacks")
    typed = {
        key: {"type": value["type"], "value": value[VALUE_KEYS[value["type"]]]}
        for key, value in parameters[f"/{node}"].items()
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
            path = Path(location).resolve()
            if workspace not in path.parents or not path.is_file():
                raise ValueError(f"Unknown original parameter asset: {location}")
            assets[location] = file_digest(path)
    header = {
        "schema": "original-gnc.callback-vectors.v3",
        "module": node,
        "parameters": typed,
        "source_trace_sha256": digest.hexdigest(),
        "reference_state_sha256": trace_sha256(state_path),
        "clock_reads": clocks,
        "initial_outputs": initial,
        "assets": assets,
        "call_count": count,
        "export_provenance": "direct streaming of original R0 messages and verified R1 states; no v2 materialization",
    }
    target = output / f"{node}.jsonl.gz"
    with records(state_path) as states, records(trace) as events, target.open("wb") as raw_output:
        first = next(states, None)
        if first is None or first[1]["ordinal"] != -1:
            raise ValueError("Missing original initial state")
        header["initial_state"] = first[1]["state"]
        with gzip.GzipFile(fileobj=raw_output, mode="wb", mtime=0, compresslevel=3) as stream:

            def write(value: Any) -> None:
                stream.write((json.dumps(portable(value), separators=(",", ":"), allow_nan=False) + "\n").encode())

            write(header)
            depth = 0
            emitted = 0
            current = None
            for _, event in events:
                if event["kind"] == "call":
                    if depth == 0:
                        current = {
                            "ordinal": event["ordinal"],
                            "function": event["function"],
                            "input": decoded(event["input"]) if event.get("input") else None,
                            "outputs": [],
                        }
                    depth += 1
                elif event["kind"] == "publish" and depth:
                    current["outputs"].append(
                        {
                            "port": event["port"],
                            "message": {"type": event["message"]["type"], "fields": decoded(event["message"])},
                        }
                    )
                elif event["kind"] == "return":
                    depth -= 1
                    if depth == 0:
                        state = next(states, None)
                        if state is None or state[1]["ordinal"] != current["ordinal"]:
                            raise ValueError("Original state/callback ordinal mismatch")
                        current["state"] = state[1]["state"]
                        write(current)
                        emitted += 1
                        current = None
            if emitted != count or depth or next(states, None) is not None:
                raise ValueError("Incomplete, extra, or mismatched original state coverage")
    return {"calls": count, "file": target.name, "sha256": file_digest(target)}


def export(native: Path, replay: Path, output: Path, nodes: list[str]) -> dict:
    """Require a successful independent replay before publishing any complete manifest."""
    report = json.loads((replay / "comparison.json").read_text())
    if not report["passed"] or Path(report["native_run"]).resolve() != native.resolve():
        raise ValueError("Verified original replay of this run is required")
    output.mkdir(parents=True, exist_ok=False)
    parameters = json.loads((native / "effective-parameters.json").read_text())
    workspace = Path(json.loads((native / "manifest.json").read_text())["source_staging"]["workspace"]).resolve()
    modules = {}
    for node in nodes:
        if not report["nodes"][node]["passed"]:
            raise ValueError(f"Unverified source node: {node}")
        modules[node] = export_node(native, replay, node, parameters, workspace, output)
        print(node, modules[node]["calls"], flush=True)
    result = {
        "native_run": str(native.resolve()),
        "modules": modules,
        "exporter_sha256": file_digest(Path(__file__)),
        "reference_report_sha256": file_digest(replay / "comparison.json"),
    }
    (output / "manifest.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native-run", "reference-replay", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--nodes", nargs="+", required=True)
    args = parser.parse_args()
    export(args.native_run.resolve(), args.reference_replay.resolve(), args.output.resolve(), args.nodes)
