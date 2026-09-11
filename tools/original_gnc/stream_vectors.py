"""Convert verified reference vectors to bounded-memory per-callback JSONL."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def convert(source: Path, output: Path) -> dict:
    """Preserve every value and bind the stream to its original vector hash."""
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    manifest = json.loads((source / "manifest.json").read_text())
    for name, identity in manifest["modules"].items():
        path = source / identity.get("file", f"{name}.json.gz")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != identity["sha256"]:
            raise ValueError(f"Changed reference vector: {path}")
        vector = json.loads(gzip.decompress(raw))
        calls = vector.pop("calls")
        vector["schema"] = "original-gnc.callback-vectors.v3"
        vector["call_count"] = len(calls)
        vector["original_vector_sha256"] = identity["sha256"]
        target = output / f"{name}.jsonl.gz"
        with target.open("wb") as file, gzip.GzipFile(fileobj=file, mode="wb", mtime=0, compresslevel=3) as stream:
            stream.write((json.dumps(vector, separators=(",", ":"), allow_nan=False) + "\n").encode())
            for call in calls:
                stream.write((json.dumps(call, separators=(",", ":"), allow_nan=False) + "\n").encode())
        identity["file"] = target.name
        identity["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.output), indent=2))
