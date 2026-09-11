"""Independently replay completed reference cases and export verified streams."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from export_streaming_vectors import export
from replay_native_trace import replay_run
from trace_io import archive_trace

CORE = [
    "ship_dynamics_node",
    "ship_control_node",
    "ship_guidance_node",
    "thrust_allocation_node",
    "coordinate_transform_node",
    "active_route_manager_node",
]
ENVIRONMENT = ["wind_engine_node", "current_engine_node", "wave_engine_node", "force_aggregator_node"]


def archive(directory: Path) -> None:
    """Retain replay evidence losslessly after comparison and vector export."""
    index = directory / "archive-manifest.json"
    identity = json.loads(index.read_text()) if index.exists() else {}
    for path in directory.rglob("*.jsonl"):
        identity[str(path.relative_to(directory))] = archive_trace(path)
        index.write_text(json.dumps(identity, indent=2))


def run(root: Path, output: Path, drivers: Path, selection: list[str] | None = None, domain: int = 174) -> None:
    """Process complete E0/E4 cases; never export a failed reference replay."""
    output.mkdir(parents=True, exist_ok=True)
    cases = {}
    for name in (
        "reference-campaign",
        "reference-parallel",
        "reference-tail",
        "reference-middle",
        "reference-last",
        "reference-repeat04",
    ):
        for marker in sorted((root / name).glob("*/campaign-result.json")):
            result = json.loads(marker.read_text())
            case = result["case_id"]
            if case.endswith(("-E0", "-E4")) and result["exit_code"] == 0:
                cases.setdefault(case, marker.parent)
    reference_index = root / "current-reference-index.json"
    if reference_index.exists():
        for case, directory in json.loads(reference_index.read_text()).items():
            if case in cases:
                cases[case] = Path(directory)
    if selection is not None:
        known = {item["case_id"] for item in json.loads((root / "cases/manifest.json").read_text())["cases"]}
        if set(selection) - known:
            raise ValueError("Unknown reference case selection")
        cases = {case: path for case, path in cases.items() if case in selection}
    invocation = {
        "domain_id": domain,
        "requested_cases": selection,
        "completed_references": {k: str(v) for k, v in cases.items()},
    }
    (output / f"invocation-{time.time_ns()}.json").write_text(json.dumps(invocation, indent=2))
    for case, native in sorted(cases.items(), key=lambda item: (not item[0].endswith("-E0"), item[0])):
        target = output / case
        if target.exists():
            continue
        nodes = CORE + (ENVIRONMENT if case.endswith("-E4") else [])
        try:
            report = replay_run(native, drivers, target, nodes, domain=domain)
            if report["passed"]:
                export(native, target, output / f"{case}-vectors-v3", nodes)
            archive(target)
            event = {"case_id": case, "reference_passed": report["passed"]}
        except Exception as error:
            event = {"case_id": case, "failure": repr(error)}
        with (output / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        print(json.dumps(event), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "output", "drivers"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--case-ids", nargs="+")
    parser.add_argument("--domain", type=int, default=174)
    args = parser.parse_args()
    run(args.root, args.output, args.drivers, args.case_ids, args.domain)
