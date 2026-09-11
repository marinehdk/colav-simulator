"""Compare extracted policy with independently evaluated original-source cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from colav_simulator.original_gnc.policy import NativePolicy


def validate(build: Path, vector_path: Path, output: Path) -> dict:
    """Require exact publications, state and clock-read counts, with source binding."""
    vector = json.loads(vector_path.read_text())
    extraction = json.loads((build / "extraction.json").read_text())["python_policy"]
    if vector["source_sha256"] != extraction["source_sha256"]:
        raise ValueError("Reference policy uses another source revision")
    clocks = [vector["initial_clock_ns"]] + [ns for c in vector["calls"] for ns in c["clock_reads"]]
    policy = NativePolicy(
        build,
        vector["config"],
        vector["initial_clock_ns"],
        config_file=vector["config_file"],
        scenario=vector["scenario"],
        scenario_file=vector["scenario_file"],
        shadow_mode=vector["shadow_mode"],
        publish_rate_hz=vector["publish_rate_hz"],
        replay_clocks=clocks,
    )
    difference = None
    publications = 0
    for i, call in enumerate(vector["calls"]):
        before = policy.clock_reads
        actual = policy.invoke(call["callback"], call["input"], call["time_ns"])
        publications += len(actual)
        if (
            actual != call["outputs"]
            or policy.snapshot() != call["state"]
            or policy.clock_reads - before != len(call["clock_reads"])
        ):
            difference = {"index": i, "callback": call["callback"], "kind": "policy_output_state_or_clock"}
            break
    if policy.clock_reads != len(clocks) and difference is None:
        difference = {"kind": "clock_coverage"}
    result = {
        "schema": "original-gnc.policy-validation.v1",
        "passed": difference is None,
        "calls_checked": i + 1,
        "publications_checked": publications,
        "clock_reads_checked": policy.clock_reads,
        "first_difference": difference,
        "vector_sha256": hashlib.sha256(vector_path.read_bytes()).hexdigest(),
        "reference_source_sha256": vector["source_sha256"],
        "native_source_sha256": extraction["native_sha256"],
        "scope": "single-module original-source equivalence; not full closed-loop acceptance",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["build", "vectors", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    r = validate(a.build, a.vectors, a.output)
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["passed"] else 1)
