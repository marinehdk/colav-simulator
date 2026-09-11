"""Freeze observed original parameter sets for the independent local backend."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def export(directories: list[Path], output: Path) -> None:
    """Copy effective typed values only from hash-verified reference vectors."""
    modules = {}
    assets = {}
    evidence = {}
    for directory in directories:
        manifest = json.loads((directory / "manifest.json").read_text())
        for name, identity in manifest["modules"].items():
            path = directory / f"{name}.json.gz"
            if hashlib.sha256(path.read_bytes()).hexdigest() != identity["sha256"]:
                raise ValueError(f"Changed reference vector: {name}")
            vector = json.loads(gzip.decompress(path.read_bytes()))
            modules[name] = vector["parameters"]
            assets.update(vector.get("assets", {}))
            evidence[name] = {
                "native_run": manifest["native_run"],
                "vector_sha256": identity["sha256"],
                "source_trace_sha256": vector["source_trace_sha256"],
            }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema": "original-gnc.observed-baseline.v1",
                "source_manifest_sha256": "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411",
                "parameters": modules,
                "assets": assets,
                "evidence": evidence,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.vectors, args.output)
