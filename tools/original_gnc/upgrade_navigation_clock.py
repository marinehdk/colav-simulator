"""Bind previously reduced samples to the observed original integrator epoch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from extract_navigation import integration_epoch


def upgrade(source: Path, output: Path) -> None:
    """Preserve observations and case values while replacing the preliminary clock convention."""
    for marker in sorted(source.rglob("manifest.json")):
        old = json.loads(marker.read_text())
        if "samples_sha256" not in old:
            continue
        destination = output / marker.parent.relative_to(source)
        if (destination / "manifest.json").exists():
            continue
        sample = marker.parent / "samples.npz"
        if hashlib.sha256(sample.read_bytes()).hexdigest() != old["samples_sha256"]:
            raise ValueError("Changed reduced sample evidence")
        epoch = integration_epoch(Path(old["source_directory"]), old["kind"])
        with np.load(sample, allow_pickle=False) as stream:
            data = {k: stream[k].copy() for k in stream.files}
        data["epoch_ns"] = np.asarray(epoch["epoch_ns"], dtype=np.int64)
        destination.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(destination / "samples.npz", **data)
        (destination / "case.json").write_bytes((marker.parent / "case.json").read_bytes())
        old["previous_samples_sha256"] = old["samples_sha256"]
        old["samples_sha256"] = hashlib.sha256((destination / "samples.npz").read_bytes()).hexdigest()
        old["integration_epoch"] = epoch
        (destination / "manifest.json").write_text(json.dumps(old, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    upgrade(args.source, args.output)
