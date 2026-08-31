from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest

from colav_simulator.modular_gnc.characterization import (
    SOURCE_BASELINE_ID,
    CharacterizationError,
    build_characterization_fixture,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_tree(tmp_path: Path) -> tuple[Path, str, dict[str, Path]]:
    source = tmp_path / "l45-source-20260824-v2"
    source.mkdir()
    source_file = source / "source.cpp"
    source_file.write_text("int source_identity = 1;\n", encoding="utf-8")
    manifest = source / "manifest.json"
    manifest.write_text(
        json.dumps({"baseline_id": SOURCE_BASELINE_ID, "files": {"source.cpp": _sha256(source_file)}}),
        encoding="utf-8",
    )
    recipe = source / "build_characterization.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        "printf '%s' "
        "'{\"schema_version\":\"agx-l45-characterization-output.v1\",\"samples\":[1.0,2.0]}' "
        "> fixture-output.json\n",
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    metadata = {}
    for name in ("config", "dependencies", "assets", "tests", "seeds"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({name: "actual-input"}), encoding="utf-8")
        metadata[name] = path
    return source, _sha256(manifest), metadata


def test_pipeline_fails_visibly_when_source_or_toolchain_unavailable(tmp_path: Path) -> None:
    with pytest.raises(CharacterizationError, match="source-only v2 baseline unavailable"):
        build_characterization_fixture(
            tmp_path / "missing",
            tmp_path / "out",
            compiler="c++",
            expected_manifest_sha256="0" * 64,
            metadata={},
        )

    source, manifest_hash, metadata = _source_tree(tmp_path)
    with pytest.raises(CharacterizationError, match="compiler unavailable"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="missing-cxx",
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
        )


def test_pipeline_detects_manifest_and_source_tampering(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    (source / "source.cpp").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(CharacterizationError, match="source file hash mismatch"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
        )


def test_pipeline_executes_recipe_and_hashes_actual_metadata(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    output = tmp_path / "out"

    manifest = build_characterization_fixture(
        source,
        output,
        compiler="c++",
        expected_manifest_sha256=manifest_hash,
        metadata=metadata,
    )

    assert manifest["source_baseline_id"] == SOURCE_BASELINE_ID
    assert manifest["source_manifest_sha256"] == manifest_hash
    assert manifest["evidence_kind"] == "SOURCE_BEHAVIOR_CHARACTERIZATION"
    assert manifest["acceptance_claim"] == "A2 prerequisite only; not vessel validation"
    assert manifest["sha256"]["config"] == _sha256(metadata["config"])
    assert manifest["recipe_executed"] is True
    assert (output / "characterization.json").exists()
    assert not (output / source.name).exists()
