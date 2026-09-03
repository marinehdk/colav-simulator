"""Create the clean execution-source manifest required for Issue #54 AGX runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def _run(root: Path, *args: str) -> str:
    return subprocess.run(("git", *args), cwd=root, check=True, capture_output=True, text=True).stdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    """Write manifest for clean commit H and deterministic git archive."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    status = _run(root, "status", "--porcelain=v1")
    if status:
        raise SystemExit(f"source must be clean before manifest creation: {status!r}")
    commit = _run(root, "rev-parse", args.commit).strip()
    archive_sha = _sha256(args.archive)
    inventory = []
    for line in _run(root, "ls-tree", "-r", commit).splitlines():
        # `ls-tree -r` output is `<mode> <type> <blob>\t<path>`.
        left, path = line.split("\t", 1)
        mode, kind, blob = left.split()
        inventory.append({"mode": mode, "type": kind, "blob": blob, "path": path})
    harness_paths = [
        "tools/gnc_performance/benchmark.py",
        "tools/gnc_performance/report.py",
        "tools/gnc_performance/__main__.py",
        "colav_simulator/modular_gnc/integrators.py",
        "colav_simulator/modular_gnc/environment.py",
        "colav_simulator/modular_gnc/load_model.py",
        "colav_simulator/modular_gnc/plant.py",
    ]
    blob_by_path = {item["path"]: item["blob"] for item in inventory}
    manifest = {
        "schema_version": "gnc-performance.execution-source.v1",
        "execution_source_commit": commit,
        "clean_status": True,
        "archive_sha256": archive_sha,
        "archive_path": str(args.archive),
        "creation_command": f"git archive --format=tar {commit} | gzip -1 -n > {args.archive}",
        "inventory": inventory,
        "harness_and_production_file_blobs": {path: blob_by_path[path] for path in harness_paths if path in blob_by_path},
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(args.output), "manifest_sha256": _sha256(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
