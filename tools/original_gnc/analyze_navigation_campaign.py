"""Produce per-case free-closure comparisons against verified original ROS runs."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path

from compare_navigation import compare
from extract_navigation import extract


def analyze_case(case: str, reference: Path, native: Path, output: Path, cached: Path | None = None) -> dict:
    """Keep full-rate observations and each source's observed clock origin."""
    reduced = cached if cached is not None else output / "embedded" / case
    if cached is None:
        extract(native, reduced, reference / "case.json")
    else:
        metadata = json.loads((reduced / "manifest.json").read_text())
        if Path(metadata["source_directory"]).resolve() != native.resolve():
            raise ValueError("Cached reduction belongs to another native run")
    result = compare(reference, reduced, output / "comparisons" / case)
    return {
        key: result[key]
        for key in (
            "case_id",
            "position_error_m",
            "speed_error_mps",
            "heading_error_rad",
            "nominal_polyline_distance_difference_m",
            "reference_performance",
            "embedded_performance",
            "reference_samples_outside_common_time",
        )
    }


def run(
    reference_nav: Path, reference_index: Path, native: Path, output: Path, workers: int, reduced_native: Path | None = None
) -> dict:
    """Require all 70 complete source and embedded executions before reduction."""
    index = json.loads(reference_index.read_text())
    if len(index) != 70:
        raise ValueError("Expected the frozen 70-case reference matrix")
    for case, original in index.items():
        reference = reference_nav / Path(original).parent.name / case
        if not (reference / "manifest.json").is_file():
            raise FileNotFoundError(reference)
        summary = json.loads((native / case / "summary.json").read_text())
        if summary.get("failure") or not summary.get("full_case_run"):
            raise ValueError(f"Incomplete embedded execution: {case}")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                analyze_case,
                case,
                reference_nav / Path(original).parent.name / case,
                native / case,
                output,
                reduced_native / case if reduced_native is not None else None,
            ): case
            for case, original in sorted(index.items())
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            print(
                json.dumps({"case_id": row["case_id"], "maximum_position_difference_m": row["position_error_m"]["maximum"]}),
                flush=True,
            )
    report = {
        "schema": "original-gnc.free-closure-campaign.v1",
        "case_count": len(rows),
        "reference_index_sha256": hashlib.sha256(reference_index.read_bytes()).hexdigest(),
        "source": str(reference_nav),
        "native": str(native),
        "scope": "Asynchronous original ROS versus deterministic embedded execution; descriptive, not fixed-input parity",
        "alignment": (
            "Observed original plant initialization clock and explicit embedded epoch; no fitted lag or spatial transform"
        ),
        "cases": sorted(rows, key=lambda row: row["case_id"]),
    }
    (output / "campaign.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference-nav", "reference-index", "native", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--reduced-native", type=Path)
    args = parser.parse_args()
    run(args.reference_nav, args.reference_index, args.native, args.output, args.workers, args.reduced_native)
