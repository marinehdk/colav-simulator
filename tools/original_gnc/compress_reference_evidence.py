"""Losslessly compact finished reference traces, retaining verified byte hashes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def compress_completed(campaign: Path) -> dict:
    """Only replace completed-run traces after a full decompression hash check."""
    results = {}
    for marker in sorted(campaign.glob("*/campaign-result.json")):
        directory = marker.parent
        index = directory / "compressed-evidence.json"
        records = json.loads(index.read_text()) if index.exists() else {}
        for path in sorted(directory.rglob("*.jsonl")):
            if path.name == "campaign-events.jsonl":
                continue
            compressed = path.with_suffix(path.suffix + ".gz")
            if compressed.exists():
                raise FileExistsError(compressed)
            temporary = compressed.with_suffix(".gz.tmp")
            original = hashlib.sha256()
            with (
                path.open("rb") as src,
                temporary.open("wb") as raw,
                gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=3) as dst,
            ):
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    original.update(chunk)
                    dst.write(chunk)
            restored = hashlib.sha256()
            with gzip.open(temporary, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    restored.update(chunk)
            if original.digest() != restored.digest():
                raise RuntimeError(f"Compression verification failed: {path}")
            record = {
                "original_sha256": original.hexdigest(),
                "original_bytes": path.stat().st_size,
                "gzip_bytes": temporary.stat().st_size,
                "gzip_sha256": hashlib.sha256(temporary.read_bytes()).hexdigest(),
            }
            temporary.rename(compressed)
            records[str(path.relative_to(directory))] = record
            index.write_text(json.dumps(records, indent=2))
            path.unlink()
        results[directory.name] = len(records)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    args = parser.parse_args()
    print(json.dumps(compress_completed(args.campaign), indent=2))
