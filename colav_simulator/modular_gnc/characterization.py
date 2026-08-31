"""Content-addressed external source characterization fixture producer."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SOURCE_BASELINE_ID = "l45-source-20260824-v2"
_REQUIRED_METADATA = frozenset({"config", "dependencies", "assets", "tests", "seeds"})


class CharacterizationError(RuntimeError):
    """Raised when frozen source fixture production cannot proceed safely."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise CharacterizationError(f"metadata input unavailable: {path}")
    return _sha256(path.read_bytes())


def _verify_source_manifest(source: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    manifest_path = source / "manifest.json"
    observed_hash = _sha256_file(manifest_path)
    if observed_hash != expected_manifest_sha256:
        raise CharacterizationError(
            f"source manifest version mismatch: expected {expected_manifest_sha256}, observed {observed_hash}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("baseline_id") != SOURCE_BASELINE_ID:
        raise CharacterizationError("source baseline identity mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise CharacterizationError("source manifest files unavailable")
    for relative, expected in files.items():
        path = source / relative
        observed = _sha256_file(path)
        if observed != expected:
            raise CharacterizationError(f"source file hash mismatch: {relative}")
    return manifest


def _compiler_identity(compiler: str) -> tuple[str, str]:
    executable = shutil.which(compiler)
    if executable is None:
        raise CharacterizationError(f"compiler unavailable: {compiler}")
    result = subprocess.run([executable, "--version"], check=True, capture_output=True)
    return executable, _sha256(result.stdout + result.stderr)


def build_characterization_fixture(
    source: Path,
    output: Path,
    *,
    compiler: str,
    expected_manifest_sha256: str,
    metadata: Mapping[str, Path],
) -> dict[str, Any]:
    """Execute frozen recipe and hash verified source and actual evidence inputs."""
    if not source.is_dir():
        raise CharacterizationError(f"source-only v2 baseline unavailable: {source}")
    _verify_source_manifest(source, expected_manifest_sha256)
    missing_metadata = _REQUIRED_METADATA - set(metadata)
    extra_metadata = set(metadata) - _REQUIRED_METADATA
    if missing_metadata or extra_metadata:
        raise CharacterizationError(
            f"metadata keys mismatch: missing={sorted(missing_metadata)}, extra={sorted(extra_metadata)}"
        )
    compiler_path, compiler_hash = _compiler_identity(compiler)
    recipe = source / "build_characterization.sh"
    if not recipe.is_file() or not recipe.stat().st_mode & 0o111:
        raise CharacterizationError("frozen source executable build recipe unavailable")
    try:
        subprocess.run([str(recipe), compiler_path], cwd=source, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise CharacterizationError(f"characterization recipe failed: {exc.stderr.decode(errors='replace')}") from exc
    source_output = source / "fixture-output.json"
    if not source_output.is_file():
        raise CharacterizationError("characterization output unavailable")
    payload = json.loads(source_output.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "agx-l45-characterization-output.v1":
        raise CharacterizationError("characterization output version mismatch")

    output.mkdir(parents=True, exist_ok=True)
    characterization_path = output / "characterization.json"
    characterization_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identities = {name: _sha256_file(path) for name, path in metadata.items()}
    identities.update(
        {
            "source": expected_manifest_sha256,
            "compiler": compiler_hash,
            "output": _sha256_file(characterization_path),
        }
    )
    manifest = {
        "schema_version": "agx-l45-characterization-manifest.v1",
        "source_baseline_id": SOURCE_BASELINE_ID,
        "source_manifest_sha256": expected_manifest_sha256,
        "evidence_kind": "SOURCE_BEHAVIOR_CHARACTERIZATION",
        "acceptance_claim": "A2 prerequisite only; not vessel validation",
        "recipe_executed": True,
        "fixture_producer": {
            "owner": "TDL Lead",
            "recovery": "restore verified external source-only v2 archive and declared Linux/AGX/container toolchain",
            "single_point_of_failure": True,
        },
        "sha256": identities,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build frozen AGX L4-5 source characterization fixtures")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--manifest-sha256", required=True)
    for name in sorted(_REQUIRED_METADATA):
        parser.add_argument(f"--{name}", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run verified characterization CLI."""
    args = _parser().parse_args(argv)
    metadata = {name: getattr(args, name) for name in _REQUIRED_METADATA}
    build_characterization_fixture(
        args.source,
        args.output,
        compiler=args.compiler,
        expected_manifest_sha256=args.manifest_sha256,
        metadata=metadata,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
