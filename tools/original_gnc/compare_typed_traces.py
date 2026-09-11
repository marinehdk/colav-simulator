"""Locate the first semantic divergence between equal-clock coupled executions."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from itertools import zip_longest
from pathlib import Path

from colav_simulator.original_gnc.output_comparison import compare_outputs


def compare(reference: Path, native: Path, fixtures: Path, source: Path, output: Path, physical_only: bool = False) -> dict:
    """Preserve event order; optional physical focus excludes passive display strings only."""
    assets = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (source / "src").rglob("*.csv")}
    for path in fixtures.glob("reference*/*.json.gz"):
        vector = json.loads(gzip.decompress(path.read_bytes()))
        assets.update(vector.get("assets", {}))

    def records(path: Path):
        with gzip.open(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if physical_only and (
                    row["topic"].startswith(("/diagnostics/", "/navigation/", "/safety/", "/operator/"))
                    or row["topic"] == "/propulsion/policy"
                ):
                    continue
                yield row

    count = 0
    difference = None
    for index, (ref, value) in enumerate(zip_longest(records(reference), records(native))):
        if ref is None or value is None:
            difference = {"kind": "record_count", "index": index}
            break
        count += 1
        if (ref["time_ns"], ref["topic"], ref["node"]) != (value["time_ns"], value["topic"], value["node"]):
            difference = {"kind": "event_identity", "index": index, "reference": ref, "native": value}
            break
        expected = {"port": ref.get("port", ref["topic"]), "message": ref["message"]}
        actual = {"port": value.get("port", value["topic"]), "message": value["message"]}
        result = compare_outputs([expected], [actual], assets)
        if not result["passed"]:
            difference = {
                "index": index,
                "time_s": (ref["time_ns"] - 2_000_000_000_000_000_000) / 1e9,
                "reference": ref,
                "native": value,
                "comparison": result,
            }
            break
    report = {
        "passed": count > 0 and difference is None,
        "records_checked": count,
        "physical_focus": physical_only,
        "first_difference": difference,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "native", "fixtures", "source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--physical-only", action="store_true")
    args = parser.parse_args()
    r = compare(args.reference, args.native, args.fixtures, args.source, args.output, args.physical_only)
    d = r["first_difference"]
    print(
        json.dumps(
            {
                "passed": r["passed"],
                "count": r["records_checked"],
                "time_s": d.get("time_s") if d else None,
                "comparison": d.get("comparison") if d else None,
            },
            indent=2,
        )
    )
