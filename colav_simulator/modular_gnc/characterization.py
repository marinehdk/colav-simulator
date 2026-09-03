"""Content-addressed external source characterization fixture producer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

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


def _load_source_manifest(manifest_path: Path) -> tuple[str, dict[str, str], str]:
    try:
        raw = manifest_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise CharacterizationError(f"source manifest unavailable: {manifest_path}") from exc

    if manifest_path.suffix.lower() == ".csv":
        rows = csv.DictReader(raw.splitlines())
        if not rows.fieldnames or not {"relative_path", "sha256"}.issubset(rows.fieldnames):
            raise CharacterizationError("source manifest CSV columns unavailable")
        files: dict[str, str] = {}
        for row in rows:
            relative = row.get("relative_path", "")
            expected = row.get("sha256", "")
            if not relative or not expected or relative in files:
                raise CharacterizationError("source manifest CSV contains invalid or duplicate entry")
            files[relative] = expected
        if not files:
            raise CharacterizationError("source manifest files unavailable")
        return SOURCE_BASELINE_ID, files, "csv"

    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CharacterizationError(f"source manifest is not valid JSON or CSV: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise CharacterizationError("source manifest must be an object")
    baseline_id = manifest.get("baseline_id")
    files = manifest.get("files")
    if not isinstance(baseline_id, str) or not isinstance(files, dict) or not files:
        raise CharacterizationError("source manifest files unavailable")
    normalized_files: dict[str, str] = {}
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise CharacterizationError("source manifest contains invalid file identity")
        normalized_files[relative] = expected
    return baseline_id, normalized_files, "json"


def _verify_source_manifest(
    source: Path,
    expected_manifest_sha256: str,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path or source / "manifest.json"
    observed_hash = _sha256_file(manifest_path)
    if observed_hash != expected_manifest_sha256:
        raise CharacterizationError(
            f"source manifest version mismatch: expected {expected_manifest_sha256}, observed {observed_hash}"
        )
    baseline_id, files, manifest_format = _load_source_manifest(manifest_path)
    if baseline_id != SOURCE_BASELINE_ID:
        raise CharacterizationError("source baseline identity mismatch")
    _verify_declared_source_files(source, files)
    return {
        "baseline_id": baseline_id,
        "files": files,
        "format": manifest_format,
    }


def _verify_declared_source_files(source: Path, files: Mapping[str, str]) -> None:
    for relative, expected in files.items():
        path = source / relative
        try:
            path.resolve().relative_to(source.resolve())
        except ValueError as exc:
            raise CharacterizationError(f"source manifest path escapes source: {relative}") from exc
        observed = _sha256_file(path)
        if observed != expected:
            raise CharacterizationError(f"source file hash mismatch: {relative}")


def _compiler_identity(compiler: str, expected_executable_sha256: str) -> tuple[str, str, str]:
    executable = shutil.which(compiler)
    if executable is None:
        raise CharacterizationError(f"compiler unavailable: {compiler}")
    executable_hash = _sha256_file(Path(executable))
    if executable_hash != expected_executable_sha256:
        raise CharacterizationError(
            f"compiler executable hash mismatch: expected {expected_executable_sha256}, observed {executable_hash}"
        )
    result = subprocess.run([executable, "--version"], check=True, capture_output=True)
    return executable, executable_hash, _sha256(result.stdout + result.stderr)


def _validate_fixture_inputs(
    source: Path,
    output: Path,
    metadata: Mapping[str, Path],
    build_inputs: Mapping[str, Path],
) -> None:
    try:
        output.relative_to(source)
    except ValueError:
        pass
    else:
        raise CharacterizationError("fixture output must be outside frozen source")
    missing_metadata = _REQUIRED_METADATA - set(metadata)
    extra_metadata = set(metadata) - _REQUIRED_METADATA
    if missing_metadata or extra_metadata:
        raise CharacterizationError(
            f"metadata keys mismatch: missing={sorted(missing_metadata)}, extra={sorted(extra_metadata)}"
        )
    for name in build_inputs:
        if not name or "/" in name or "\\" in name:
            raise CharacterizationError(f"build input name invalid: {name!r}")


def _input_identities(
    metadata: Mapping[str, Path],
    build_inputs: Mapping[str, Path],
) -> dict[str, str]:
    identities = {name: _sha256_file(Path(path)) for name, path in sorted(metadata.items())}
    identities.update({f"build_input:{name}": _sha256_file(Path(path)) for name, path in sorted(build_inputs.items())})
    return identities


def _validate_npz(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise CharacterizationError("characterization NPZ output is invalid")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
    except zipfile.BadZipFile as exc:
        raise CharacterizationError("characterization NPZ output is invalid") from exc
    if not members or any(not member.endswith(".npy") or member.startswith("/") for member in members):
        raise CharacterizationError("characterization NPZ output is invalid")
    try:
        with zipfile.ZipFile(path) as archive:
            for member in members:
                with archive.open(member) as npy_file:
                    np.lib.format.read_array(npy_file, allow_pickle=False)
    except (EOFError, OSError, TypeError, ValueError, zipfile.BadZipFile) as exc:
        raise CharacterizationError("characterization NPZ output is invalid") from exc


def _publish_fixture(candidate: Path, output: Path) -> None:
    if output.exists() and not output.is_dir():
        raise CharacterizationError("fixture output path must be a directory")
    backup: Path | None = None
    if output.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent))
        backup.rmdir()
        try:
            os.replace(output, backup)
        except OSError as exc:
            backup.rmdir()
            raise CharacterizationError(f"fixture output backup failed: {exc}") from exc
    try:
        os.replace(candidate, output)
    except OSError as exc:
        if backup is not None:
            try:
                os.replace(backup, output)
            except OSError as rollback_exc:
                raise CharacterizationError(f"fixture output publication and rollback failed: {rollback_exc}") from exc
        raise CharacterizationError(f"fixture output publication failed: {exc}") from exc
    if backup is not None:
        shutil.rmtree(backup)


def _recipe_command(
    source: Path,
    staged_source: Path,
    run_root: Path,
    recipe_path: Path,
    compiler_path: str,
    json_output: Path,
    npz_output: Path,
    recipe_is_external: bool,
    staged_build_inputs: Mapping[str, Path],
) -> tuple[list[str], Path]:
    if not recipe_is_external:
        try:
            staged_recipe = recipe_path.relative_to(source)
        except ValueError as exc:
            raise CharacterizationError("source-owned recipe must be inside frozen source") from exc
        return [str(staged_source / staged_recipe), compiler_path], staged_source
    command = [
        str(recipe_path),
        str(staged_source),
        str(json_output),
        str(npz_output),
        compiler_path,
    ]
    command.extend(f"{name}={staged_build_inputs[name]}" for name in sorted(staged_build_inputs))
    return command, run_root


def _stage_external_recipe_and_inputs(
    run_root: Path,
    recipe_path: Path,
    recipe_sha256: str,
    build_inputs: Mapping[str, Path],
    input_identities: Mapping[str, str],
) -> tuple[Path, dict[str, Path]]:
    recipe_root = run_root / "recipe"
    recipe_root.mkdir()
    staged_recipe = recipe_root / recipe_path.name
    shutil.copyfile(recipe_path, staged_recipe)
    shutil.copymode(recipe_path, staged_recipe)
    if _sha256_file(staged_recipe) != recipe_sha256:
        raise CharacterizationError("staged recipe hash mismatch")
    build_input_root = run_root / "build-inputs"
    build_input_root.mkdir()
    staged_build_inputs: dict[str, Path] = {}
    for name, path in sorted(build_inputs.items()):
        suffix = Path(path).suffix
        staged_path = build_input_root / f"{name}{suffix}"
        shutil.copyfile(path, staged_path)
        expected_hash = input_identities[f"build_input:{name}"]
        if _sha256_file(staged_path) != expected_hash:
            raise CharacterizationError(f"staged build input hash mismatch: {name}")
        staged_build_inputs[name] = staged_path
    return staged_recipe, staged_build_inputs


def _execute_recipe(
    source: Path,
    recipe_path: Path,
    compiler_path: str,
    require_npz: bool,
    recipe_is_external: bool,
    build_inputs: Mapping[str, Path],
    source_files: Mapping[str, str],
    recipe_sha256: str,
    input_identities: Mapping[str, str],
) -> tuple[dict[str, Any], bytes | None]:
    with tempfile.TemporaryDirectory(prefix="colav-gnc-characterization-") as temporary:
        run_root = Path(temporary)
        staged_source = run_root / "source"
        shutil.copytree(source, staged_source, symlinks=True)
        _verify_declared_source_files(staged_source, source_files)
        for stale in ("fixture-output.json", "fixture-output.npz"):
            (staged_source / stale).unlink(missing_ok=True)
        staged_recipe = recipe_path
        staged_build_inputs: dict[str, Path] = {}
        if recipe_is_external:
            staged_recipe, staged_build_inputs = _stage_external_recipe_and_inputs(
                run_root,
                recipe_path,
                recipe_sha256,
                build_inputs,
                input_identities,
            )
        run_output_json = run_root / "fixture-output.json"
        run_output_npz = run_root / "fixture-output.npz"
        run_environment = os.environ.copy()
        run_environment.update(
            {
                "COLAV_CHARACTERIZATION_SOURCE": str(staged_source),
                "COLAV_CHARACTERIZATION_JSON": str(run_output_json),
                "COLAV_CHARACTERIZATION_NPZ": str(run_output_npz),
                "COLAV_CHARACTERIZATION_COMPILER": compiler_path,
            }
        )
        command, cwd = _recipe_command(
            source,
            staged_source,
            run_root,
            staged_recipe,
            compiler_path,
            run_output_json,
            run_output_npz,
            recipe_is_external,
            staged_build_inputs,
        )
        try:
            subprocess.run(
                command,
                cwd=cwd,
                env=run_environment,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", "") or getattr(exc, "stdout", "") or str(exc)
            raise CharacterizationError(f"characterization recipe failed: {detail.strip()}") from exc

        if recipe_is_external:
            json_source, npz_source = run_output_json, run_output_npz
        else:
            json_source = staged_source / "fixture-output.json"
            npz_source = staged_source / "fixture-output.npz"
        if not json_source.is_file():
            raise CharacterizationError("new characterization JSON output unavailable")
        if require_npz and not npz_source.is_file():
            raise CharacterizationError("new characterization NPZ output unavailable")
        if npz_source.is_file():
            _validate_npz(npz_source)
        try:
            payload = json.loads(json_source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CharacterizationError("characterization JSON output is invalid") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != "agx-l45-characterization-output.v1":
            raise CharacterizationError("characterization output version mismatch")
        npz_payload = npz_source.read_bytes() if npz_source.is_file() else None
    return payload, npz_payload


def build_characterization_fixture(
    source: Path,
    output: Path,
    *,
    compiler: str,
    expected_manifest_sha256: str,
    metadata: Mapping[str, Path],
    expected_compiler_sha256: str,
    source_manifest: Path | None = None,
    recipe: Path | None = None,
    expected_recipe_sha256: str | None = None,
    build_inputs: Mapping[str, Path] | None = None,
    require_npz: bool = True,
) -> dict[str, Any]:
    """Execute a verified recipe against an isolated copy of frozen source."""
    if not source.is_dir():
        raise CharacterizationError(f"source-only v2 baseline unavailable: {source}")
    source = source.resolve()
    output = output.resolve()
    build_inputs = build_inputs or {}
    _validate_fixture_inputs(source, output, metadata, build_inputs)
    source_manifest = (source_manifest or source / "manifest.json").resolve()
    source_identity = _verify_source_manifest(source, expected_manifest_sha256, source_manifest)
    compiler_path, compiler_executable_hash, compiler_version_hash = _compiler_identity(compiler, expected_compiler_sha256)
    recipe_path = (recipe or source / "build_characterization.sh").resolve()
    if not recipe_path.is_file() or not recipe_path.stat().st_mode & 0o111:
        raise CharacterizationError("characterization executable build recipe unavailable")
    recipe_is_external = recipe is not None
    try:
        relative_recipe = recipe_path.relative_to(source).as_posix()
    except ValueError:
        relative_recipe = None
    if recipe_is_external and relative_recipe is not None:
        raise CharacterizationError("external recipe must be outside frozen source")
    if not recipe_is_external and relative_recipe not in source_identity["files"]:
        raise CharacterizationError("source-owned recipe is not bound by source manifest")
    if recipe_is_external and not build_inputs:
        raise CharacterizationError("external recipe build inputs unavailable")
    recipe_sha256 = _sha256_file(recipe_path)
    if recipe_is_external and expected_recipe_sha256 is None:
        raise CharacterizationError("external recipe identity unavailable")
    if expected_recipe_sha256 is not None and recipe_sha256 != expected_recipe_sha256:
        raise CharacterizationError(f"recipe hash mismatch: expected {expected_recipe_sha256}, observed {recipe_sha256}")
    input_identities = _input_identities(metadata, build_inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not output.is_dir():
        raise CharacterizationError("fixture output path must be a directory")
    with tempfile.TemporaryDirectory(prefix=f".{output.name}.candidate-", dir=output.parent) as candidate_dir:
        candidate = Path(candidate_dir)
        payload, npz_payload = _execute_recipe(
            source,
            recipe_path,
            compiler_path,
            require_npz,
            recipe_is_external,
            build_inputs,
            source_identity["files"],
            recipe_sha256,
            input_identities,
        )
        recipe_mode = "repo_adapter" if recipe_is_external else "source_owned"
        characterization_path = candidate / "characterization.json"
        characterization_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        characterization_npz_path = candidate / "characterization.npz"
        if npz_payload is not None:
            characterization_npz_path.write_bytes(npz_payload)
        identities = dict(input_identities)
        identities.update(
            {
                "source": expected_manifest_sha256,
                "recipe": recipe_sha256,
                "compiler_executable": compiler_executable_hash,
                "compiler_version": compiler_version_hash,
                "output": _sha256_file(characterization_path),
            }
        )
        if characterization_npz_path.is_file():
            identities["output_npz"] = _sha256_file(characterization_npz_path)
        manifest = {
            "schema_version": "agx-l45-characterization-manifest.v1",
            "source_baseline_id": SOURCE_BASELINE_ID,
            "source_manifest_sha256": expected_manifest_sha256,
            "source_manifest_format": source_identity["format"],
            "evidence_kind": "SOURCE_BEHAVIOR_CHARACTERIZATION",
            "acceptance_claim": "A2 prerequisite only; not vessel validation",
            "recipe_mode": recipe_mode,
            "build_inputs": sorted(build_inputs),
            "recipe_executed": True,
            "fixture_artifacts": {
                "json": "characterization.json",
                "npz": "characterization.npz" if characterization_npz_path.is_file() else None,
            },
            "fixture_producer": {
                "owner": "TDL Lead",
                "recovery": "restore verified external source-only v2 archive and declared Linux/AGX/container toolchain",
                "single_point_of_failure": True,
            },
            "sha256": identities,
        }
        (candidate / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _publish_fixture(candidate, output)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build frozen AGX L4-5 source characterization fixtures")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--recipe-sha256")
    parser.add_argument("--build-input", action="append", default=[])
    parser.add_argument("--compiler", default="c++")
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    for name in sorted(_REQUIRED_METADATA):
        parser.add_argument(f"--{name}", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run verified characterization CLI."""
    args = _parser().parse_args(argv)
    metadata = {name: getattr(args, name) for name in _REQUIRED_METADATA}
    try:
        build_inputs = {}
        for item in args.build_input:
            name, separator, path = item.partition("=")
            if not separator or not name or not path:
                raise CharacterizationError("build input must use NAME=PATH")
            build_inputs[name] = Path(path)
        build_characterization_fixture(
            args.source,
            args.output,
            compiler=args.compiler,
            expected_manifest_sha256=args.manifest_sha256,
            metadata=metadata,
            expected_compiler_sha256=args.compiler_sha256,
            source_manifest=args.source_manifest,
            recipe=args.recipe,
            expected_recipe_sha256=args.recipe_sha256,
            build_inputs=build_inputs,
        )
    except CharacterizationError as exc:
        print(f"characterization failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
