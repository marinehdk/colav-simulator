"""Run the frozen native-reference matrix with isolated, bounded concurrency."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from compress_reference_evidence import compress_completed


# Keep source contract branches together for audit against the frozen implementation.
def run(  # noqa: C901, PLR0915
    cases: Path,
    workspace: Path,
    output: Path,
    domains: list[int],
    selection: list[str] | None = None,
    completed_roots: list[Path] | None = None,
    longest_first: bool = False,
    archive: bool = False,
) -> dict:
    """Use one fresh recorder/ROS graph per case and a separate domain per slot."""
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((cases / "manifest.json").read_text())
    priority = ["R05-E0", "R06-E0", "R12-E0", "R07-E0", "R02-plus-E0", "R02-minus-E0", "R03-plus-E0", "R03-minus-E0"]
    indexed = {c["case_id"]: c for c in manifest["cases"]}
    ordered = priority + [c for c in indexed if c.endswith("-E0") and c not in priority]
    ordered += [c for c in indexed if c not in ordered]
    if selection is not None:
        if set(selection) - set(indexed):
            raise ValueError("Unknown frozen reference case selection")
        ordered = [case for case in ordered if case in selection]
    if longest_first:
        ordered.sort(
            key=lambda case: json.loads((cases / indexed[case]["file"]).read_text())["max_duration_s"], reverse=True
        )
    pending = queue.Queue()
    for case in ordered:
        if not (output / case / "campaign-result.json").exists():
            pending.put(case)
    lock = threading.Lock()
    archive_lock = threading.Lock()
    results = {}
    events = (output / "campaign-events.jsonl").open("a", buffering=1)

    def record(event: Any):
        with lock:
            events.write(json.dumps({"wall_time": time.time(), **event}) + "\n")

    def worker(domain: Any):
        while True:
            try:
                case_id = pending.get_nowait()
            except queue.Empty:
                return
            already_completed = False
            for root in completed_roots or []:
                marker = root / case_id / "campaign-result.json"
                if marker.exists() and json.loads(marker.read_text()).get("exit_code") == 0:
                    prior = json.loads((marker.parent / "manifest.json").read_text())
                    if prior["case_sha256"] == indexed[case_id]["sha256"]:
                        record(
                            {"event": "covered_by_existing_reference", "case_id": case_id, "directory": str(marker.parent)}
                        )
                        already_completed = True
                        break
            if already_completed:
                pending.task_done()
                continue
            directory = output / case_id
            if directory.exists():
                # Preserve interrupted evidence; a retry is a new run directory.
                number = 1
                while directory.with_name(directory.name + f"-retry{number}").exists():
                    number += 1
                directory = directory.with_name(directory.name + f"-retry{number}")
            path = cases / indexed[case_id]["file"]
            case = json.loads(path.read_text())
            env = {**os.environ, "ROS_DOMAIN_ID": str(domain), "ROS_LOCALHOST_ONLY": "1"}
            command = [
                sys.executable,
                str(Path(__file__).with_name("run_native_reference.py")),
                "--case",
                str(path),
                "--workspace",
                str(workspace),
                "--output",
                str(directory),
                "--domain",
                str(domain),
            ]
            record({"event": "started", "case_id": case_id, "domain": domain, "directory": str(directory)})
            # The child owns and terminates its launch process group. A timeout
            # here is a campaign failure, never a synthetic successful case.
            log = output / f"{directory.name}-recorder.log"
            started = time.monotonic()
            with log.open("w") as stream:
                process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env, check=False)
            result = {
                "case_id": case_id,
                "domain": domain,
                "exit_code": process.returncode,
                "elapsed_wall_s": time.monotonic() - started,
                "directory": str(directory),
                "configured_duration_s": case["max_duration_s"],
            }
            directory.mkdir(exist_ok=True)
            (directory / "campaign-result.json").write_text(json.dumps(result, indent=2))
            results[case_id] = result
            record({"event": "finished", **result})
            if archive:
                with archive_lock:
                    compress_completed(output)
            pending.task_done()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(domains)) as executor:
        list(executor.map(worker, domains))
    events.close()
    report = {
        "case_count": len(ordered),
        "executed_this_invocation": results,
        "scope": "native reference execution only; no embedded or algorithm acceptance implied",
    }
    (output / "campaign-summary.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domains", type=int, nargs="+", default=[175, 176])
    parser.add_argument("--case-ids", nargs="+")
    parser.add_argument("--completed-roots", type=Path, nargs="*", default=[])
    parser.add_argument("--longest-first", action="store_true")
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    if len(set(args.domains)) != len(args.domains):
        raise ValueError("Each campaign worker needs a unique DDS domain")
    print(
        json.dumps(
            run(
                args.cases,
                args.workspace,
                args.output,
                args.domains,
                args.case_ids,
                args.completed_roots,
                args.longest_first,
                args.archive,
            )
        )
    )
