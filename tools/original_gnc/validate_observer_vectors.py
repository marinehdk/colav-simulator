"""Check local observation modules against independent original-source vectors."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from colav_simulator.original_gnc.observers import NativeObserver, portable
from colav_simulator.original_gnc.output_comparison import compare_outputs


def validate(build: Path, source: Path, vector_path: Path, output: Path) -> dict:
    """Compare extracted observer publications and clock consumption to source vectors."""
    vector = json.loads(vector_path.read_text())
    extraction = json.loads((build / "extraction.json").read_text())["python_observers"]
    result = {}
    for name, data in vector["modules"].items():
        if data["source_sha256"] != extraction[name]["source_sha256"]:
            raise ValueError(f"Original observer source mismatch: {name}")
        for relative, digest in data["helper_sources"].items():
            if hashlib.sha256((source / relative).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Original observer helper mismatch: {relative}")
        params = copy.deepcopy(data["parameters"])
        if params.get("config_file"):
            relative = params["config_file"].split("/frozen/", 1)[1]
            file = source / relative
            if hashlib.sha256(file.read_bytes()).hexdigest() != data["configuration_sha256"]:
                raise ValueError(f"Original observer config mismatch: {file}")
            params["config_file"] = str(file)
        clocks = data["initial_clock_reads"] + [n for c in data["calls"] for n in c["clock_reads"]]
        steady = data["initial_steady_reads"] + [n for c in data["calls"] for n in c["steady_reads"]]
        observer = NativeObserver(build, name, params, vector["epoch_ns"], replay_clocks=clocks, replay_steady=steady)
        difference = None
        publications = 0
        for index, call in enumerate(data["calls"]):
            before = observer.clock_reads, observer.steady_reads
            actual = observer.invoke(call["callback"], call["input"], call["time_ns"])
            expected = [
                {"port": o["topic"], "message": {"type": o["type"], "fields": portable(o["fields"])}}
                for o in call["outputs"]
            ]
            outputs = [{"port": o["topic"], "message": {"type": o["type"], "fields": o["fields"]}} for o in actual]
            compared = compare_outputs(expected, outputs)
            if not compared["passed"]:
                difference = {"index": index, "callback": call["callback"], **compared}
                break
            if (observer.clock_reads - before[0], observer.steady_reads - before[1]) != (
                len(call["clock_reads"]),
                len(call["steady_reads"]),
            ):
                difference = {"index": index, "kind": "clock_coverage"}
                break
            publications += len(actual)
        if (observer.clock_reads, observer.steady_reads) != (len(clocks), len(steady)) and difference is None:
            difference = {"kind": "remaining_clock_reads"}
        result[name] = {
            "passed": difference is None,
            "calls_checked": index + 1,
            "publications_checked": publications,
            "clock_reads": observer.clock_reads,
            "steady_reads": observer.steady_reads,
            "first_difference": difference,
        }
    report = {
        "schema": "original-gnc.observer-validation.v1",
        "passed": all(r["passed"] for r in result.values()),
        "modules": result,
        "vector_sha256": hashlib.sha256(vector_path.read_bytes()).hexdigest(),
        "scope": "original source observer output and clock equivalence; not control safety acceptance",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ["build", "source", "vectors", "output"]:
        p.add_argument("--" + n, type=Path, required=True)
    a = p.parse_args()
    r = validate(a.build, a.source, a.vectors, a.output)
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["passed"] else 1)
