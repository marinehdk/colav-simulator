"""Verify the frozen colleague export and stage build-only installation repairs.

This script runs with Python's standard library on the reference host. It never
writes the frozen source or changes numerical/behavioural C++ or configuration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

SOURCE_MANIFEST_SHA256 = "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"


def sha256(path: Path) -> str:
    """Hash the exact file bytes, including the original line endings."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source: Path, workspace: Path) -> dict:
    """Stage a verified source tree and record only missing-document repairs."""
    source, workspace = source.resolve(), workspace.resolve()
    manifest = source / "SOURCE_MANIFEST.csv"
    if sha256(manifest) != SOURCE_MANIFEST_SHA256:
        raise ValueError("The source manifest is not the approved 2026-08-24 v2 export")
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.DictReader(stream))
    for record in records:
        path = (source / record["relative_path"]).resolve()
        if source not in path.parents or sha256(path) != record["sha256"]:
            raise ValueError(f"Frozen source verification failed: {record['relative_path']}")
    if source == workspace or source in workspace.parents:
        raise ValueError("Build workspace must be outside the frozen source")
    target = workspace / "src"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing source staging: {target}")
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "src", target)
    repairs = []
    replacements = {
        "src/environment/env_engines/CMakeLists.txt": (
            "install(FILES ENVIRONMENT_DATA_CONTRACT.md\n  DESTINATION share/${PROJECT_NAME})\n",
            "# Source-only export excludes documentation; no executable change.\n",
        ),
        "src/mission/mission_supervisor/setup.py": (
            "['package.xml', 'README.md']",
            "['package.xml']",
        ),
        "src/safety/safety_supervisor/setup.py": (
            "['package.xml', 'README.md']",
            "['package.xml']",
        ),
    }
    for relative, (before, after) in replacements.items():
        path = workspace / relative
        text = path.read_text()
        if text.count(before) != 1:
            raise ValueError(f"Expected one exact build-only repair at {relative}")
        old_hash = sha256(path)
        path.write_text(text.replace(before, after))
        repairs.append(
            {
                "path": relative,
                "before_sha256": old_hash,
                "after_sha256": sha256(path),
                "removed": before,
                "added": after,
                "reason": "export excludes documentation",
            }
        )
    repaired_paths = set(replacements)
    for record in records:
        relative = record["relative_path"]
        if relative not in repaired_paths and sha256(workspace / relative) != record["sha256"]:
            raise ValueError(f"Unexpected staged-source change: {relative}")
    result = {
        "schema": "original-gnc.reference-staging.v1",
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "source_files_checked": len(records),
        "source": str(source),
        "workspace": str(workspace),
        "build_only_repairs": repairs,
        "numerical_or_configuration_changes": [],
    }
    (workspace / "source-staging.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.workspace), indent=2))
