"""Combine independently verified node replays of the same recorded source run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def combine(base: Path, replacement: Path, output: Path, nodes: list[str]) -> dict:
    """Preserve each node's original report and files; never invent missing coverage."""
    old = json.loads((base / "comparison.json").read_text())
    new = json.loads((replacement / "comparison.json").read_text())
    if not new["passed"] or Path(old["native_run"]).resolve() != Path(new["native_run"]).resolve():
        raise ValueError("Replacement must be a verified replay of the same original run")
    output.mkdir(parents=True, exist_ok=False)
    (output / "callback-traces").mkdir()
    results = {}
    origins = {}
    for node in nodes:
        directory, report = (replacement, new) if node in new["nodes"] else (base, old)
        result = report["nodes"][node]
        if not result["passed"]:
            raise ValueError(f"No successful original replay for {node}")
        for name in (f"{node}-states.jsonl", f"callback-traces/{node}.jsonl"):
            source = directory / name
            if not source.exists():
                source = source.with_suffix(source.suffix + ".gz")
            if not source.is_file():
                raise FileNotFoundError(source)
            target = output / name
            if source.suffix == ".gz":
                target = target.with_suffix(target.suffix + ".gz")
            target.symlink_to(source.resolve())
        results[node] = result
        origins[node] = {
            "report": str(directory / "comparison.json"),
            "sha256": hashlib.sha256((directory / "comparison.json").read_bytes()).hexdigest(),
        }
    report = {
        "schema": "original-gnc.reference-self-replay.v1",
        "native_run": str(Path(old["native_run"]).resolve()),
        "passed": bool(nodes) and len(results) == len(nodes),
        "nodes": results,
        "requested_nodes": nodes,
        "node_source_reports": origins,
        "embedded_code_executed": False,
        "scope": "Per-node reference replays; source evidence linked unchanged from the identified attempts",
    }
    (output / "comparison.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base", "replacement", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--nodes", nargs="+", required=True)
    args = parser.parse_args()
    combine(args.base.resolve(), args.replacement.resolve(), args.output.resolve(), args.nodes)
