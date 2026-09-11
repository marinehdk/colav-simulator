"""Exercise local original C++ kernels against independently generated vectors."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

from colav_simulator.original_gnc.native import NativeModule
from colav_simulator.original_gnc.output_comparison import compare_outputs
from colav_simulator.original_gnc.state_comparison import compare_state


@contextmanager
def vector_records(path: Path):
    """Stream large callback sets while retaining legacy compact fixtures."""
    if path.name.endswith(".jsonl.gz"):
        with gzip.open(path, "rt") as stream:
            metadata = json.loads(stream.readline())
            yield metadata, (json.loads(line) for line in stream), metadata["call_count"]
    else:
        metadata = json.loads(gzip.decompress(path.read_bytes()))
        calls = metadata.pop("calls")
        yield metadata, iter(calls), len(calls)


# Keep source contract branches together for audit against the frozen implementation.
def validate(build: Path, vectors: Path, source: Path, output: Path) -> dict:  # noqa: C901, PLR0912, PLR0915
    """Require parameter identity and the frozen dimensional output rules."""
    output.mkdir(parents=True, exist_ok=True)
    package = Path(__file__).resolve().parents[2] / "colav_simulator/original_gnc"
    comparison_sources = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [
            Path(__file__),
            *[package / name for name in ("validation.py", "output_comparison.py", "state_comparison.py")],
        ]
    }
    extraction = json.loads((build / "extraction.json").read_text())
    vector_manifest = json.loads((vectors / "manifest.json").read_text())
    if not vector_manifest.get("modules"):
        raise ValueError("No reference module vectors")
    roots = {p.parent.name: str(p.parent) for p in (source / "src").glob("*/*/package.xml")}
    results = {}
    for name, identity in vector_manifest["modules"].items():
        path = vectors / identity.get("file", f"{name}.json.gz")
        digest = hashlib.sha256()
        with path.open("rb") as compressed:
            for chunk in iter(lambda: compressed.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != identity["sha256"]:
            raise ValueError(f"Reference vector identity changed: {path}")
        with vector_records(path) as (vector, calls, call_count):
            assets = {
                **vector.get("assets", {}),
                **{str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (source / "src").rglob("*.csv")},
            }
            local_assets = {digest: location for location, digest in assets.items() if Path(location).is_file()}
            asset_paths = {}
            for location, digest in vector.get("assets", {}).items():
                if digest not in local_assets:
                    raise ValueError(f"Missing byte-identical local original asset: {location}")
                asset_paths[location] = local_assets[digest]
            options = {
                "replay_clocks": vector["clock_reads"],
                "omitted_log_clock_sites": extraction["modules"][name]["omitted_log_clock_sites"],
                "package_roots": roots,
                "asset_paths": asset_paths,
            }
            result = {
                "passed": False,
                "calls_total": call_count,
                "calls_checked": 0,
                "outputs_checked": 0,
                "fields_checked": 0,
                "parameters_checked": 0,
                "max_error_by_unit": {},
                "first_difference": None,
                "reference_vector_sha256": identity["sha256"],
            }
            result["internal_state_verified"] = "initial_state" in vector
            try:
                with NativeModule(build, name, vector["parameters"], options) as module:
                    description = module.describe()
                    for key, value in description["parameters"].items():
                        if value != vector["parameters"].get(key):
                            raise ValueError(f"Native parameter differs: {key}")
                        result["parameters_checked"] += 1
                    initial = compare_outputs(vector["initial_outputs"], description["initial_outputs"], assets)
                    if not initial["passed"]:
                        raise ValueError(f"Constructor output mismatch: {initial}")
                    if "initial_state" in vector:
                        initial_state = compare_state(name, vector["initial_state"], description["state"])
                        if not initial_state["passed"]:
                            raise ValueError(f"Constructor state mismatch: {initial_state['first_difference']}")
                    result["original_periods_ns"] = description["timers"]
                    for index, call in enumerate(calls):
                        actual = module.invoke(call["function"], call["input"], 0)
                        compared = compare_outputs(call["outputs"], actual["outputs"], assets)
                        result["calls_checked"] += 1
                        result["outputs_checked"] += len(call["outputs"])
                        result["fields_checked"] += compared["fields_checked"]
                        for unit, error in compared["max_error_by_unit"].items():
                            result["max_error_by_unit"][unit] = max(result["max_error_by_unit"].get(unit, 0.0), error)
                        if not compared["passed"]:
                            result["first_difference"] = {
                                "call_index": index,
                                "function": call["function"],
                                **compared["first_difference"],
                            }
                            (output / f"{name}-first-difference.json").write_text(
                                json.dumps({"call": call, "actual": actual, "comparison": compared}, indent=2)
                            )
                            break
                        if result["internal_state_verified"]:
                            state_result = compare_state(name, call["state"], actual["state"])
                            if not state_result["passed"]:
                                result["first_difference"] = {
                                    "call_index": index,
                                    "function": call["function"],
                                    "kind": "internal_state",
                                    "detail": state_result["first_difference"],
                                }
                                break
                    else:
                        final = module.describe()
                        for key, value in final["parameters"].items():
                            if value != vector["parameters"].get(key):
                                raise ValueError(f"Dynamic native parameter differs: {key}")
                        missing = set(vector["parameters"]) - set(final["parameters"])
                        missing = {key for key in missing if key != "use_sim_time" and not key.startswith("qos_overrides.")}
                        if missing:
                            raise ValueError(f"Original parameter declaration missing from native module: {sorted(missing)}")
                        result["parameters_checked"] = len(final["parameters"])
                        if final["required_clock_reads_remaining"] != 0:
                            raise ValueError("Unconsumed original business clock reads")
                        if result["calls_checked"] != call_count:
                            raise ValueError("Reference callback stream is truncated or has extra calls")
                        result["passed"] = result["outputs_checked"] > 0 and result["calls_checked"] > 0
            except Exception as error:
                result["first_difference"] = {"kind": "execution", "message": str(error)}
            results[name] = result
            with (output / "progress.jsonl").open("a") as progress:
                progress.write(
                    json.dumps({"module": name, "passed": result["passed"], "calls_checked": result["calls_checked"]}) + "\n"
                )
    report = {
        "schema": "original-gnc.native-vector-validation.v1",
        "passed": all(r["passed"] for r in results.values()),
        "native_build": json.loads((build / "build-manifest.json").read_text()),
        "comparison_sources_sha256": comparison_sources,
        "modules": results,
        "scope": "per-callback output/parameter parity; not full closed-loop acceptance",
    }
    (output / "comparison.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.build.resolve(), args.vectors.resolve(), args.source.resolve(), args.output.resolve())
    print(json.dumps({"passed": report["passed"], "modules": report["modules"]}, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
