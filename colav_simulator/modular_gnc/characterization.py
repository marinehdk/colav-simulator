from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SOURCE_BASELINE_ID = "l45-source-20260824-v2"
SOURCE_MANIFEST_SHA256 = "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"


class CharacterizationError(RuntimeError):
    """Raised when frozen source fixture production cannot proceed safely."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


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
    execute: bool = True,
) -> dict[str, Any]:
    """Produce content-addressed outputs without copying external source into repository."""
    if not source.is_dir():
        raise CharacterizationError(f"source-only v2 baseline unavailable: {source}")
    manifest_file = source / "manifest.sha256"
    if not manifest_file.is_file():
        raise CharacterizationError("source manifest unavailable")
    observed_manifest = manifest_file.read_text(encoding="utf-8").strip()
    if observed_manifest != SOURCE_MANIFEST_SHA256:
        raise CharacterizationError(
            f"source version mismatch: expected {SOURCE_MANIFEST_SHA256}, observed {observed_manifest}"
        )
    compiler_path, compiler_hash = _compiler_identity(compiler)
    source_output = source / "fixture-output.json"
    if execute:
        recipe = source / "build_characterization.sh"
        if not recipe.is_file():
            raise CharacterizationError("frozen source build recipe unavailable")
        subprocess.run([str(recipe), compiler_path], cwd=source, check=True)
    if not source_output.is_file():
        raise CharacterizationError("characterization output unavailable")
    payload = json.loads(source_output.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "agx-l45-characterization-output.v1":
        raise CharacterizationError("characterization output version mismatch")

    output.mkdir(parents=True, exist_ok=True)
    characterization_path = output / "characterization.json"
    characterization_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identities = {
        "source": _tree_hash(source),
        "config": _sha256(b"frozen-source-v2-default-config"),
        "compiler": compiler_hash,
        "dependencies": _sha256((sys.version + "\n" + compiler_path).encode()),
        "assets": _sha256(b"no-repository-assets-copied"),
        "tests": _sha256(b"agx-l45-characterization-output.v1"),
        "seeds": _sha256(b"0"),
        "output": _sha256(characterization_path.read_bytes()),
    }
    manifest = {
        "schema_version": "agx-l45-characterization-manifest.v1",
        "source_baseline_id": SOURCE_BASELINE_ID,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "evidence_kind": "SOURCE_BEHAVIOR_CHARACTERIZATION",
        "acceptance_claim": "A2 prerequisite only; not vessel validation",
        "fixture_producer": {
            "owner": "TDL Lead",
            "recovery": "restore frozen external source-only v2 archive and rerun this recipe on Linux/AGX/container",
            "single_point_of_failure": True,
        },
        "sha256": identities,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build frozen AGX L4-5 source characterization fixtures")
    parser.add_argument("--source", type=Path, required=True, help="external frozen source-only v2 directory")
    parser.add_argument("--output", type=Path, required=True, help="fixture output directory")
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--no-execute", action="store_true", help="consume existing frozen output without compiling")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run content-addressed source characterization CLI."""
    args = _parser().parse_args(argv)
    build_characterization_fixture(args.source, args.output, compiler=args.compiler, execute=not args.no_execute)
    return 0


if __name__ == "__main__":
    sys.exit(main())
