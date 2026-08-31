from __future__ import annotations

import json
from pathlib import Path

import pytest

from colav_simulator.modular_gnc.characterization import (
    SOURCE_BASELINE_ID,
    SOURCE_MANIFEST_SHA256,
    CharacterizationError,
    build_characterization_fixture,
    main,
)


def _source_tree(tmp_path: Path) -> Path:
    source = tmp_path / "l45-source-20260824-v2"
    source.mkdir()
    (source / "manifest.sha256").write_text(SOURCE_MANIFEST_SHA256 + "\n", encoding="utf-8")
    (source / "fixture-output.json").write_text(
        json.dumps({"schema_version": "agx-l45-characterization-output.v1", "samples": [1.0, 2.0]}),
        encoding="utf-8",
    )
    return source


def test_pipeline_fails_visibly_when_source_or_toolchain_unavailable(tmp_path: Path) -> None:
    with pytest.raises(CharacterizationError, match="source-only v2 baseline unavailable"):
        build_characterization_fixture(tmp_path / "missing", tmp_path / "out", compiler="c++")

    source = _source_tree(tmp_path)
    with pytest.raises(CharacterizationError, match="compiler unavailable"):
        build_characterization_fixture(source, tmp_path / "out", compiler="missing-cxx")


def test_pipeline_emits_content_addressed_characterization_not_validation(tmp_path: Path) -> None:
    source = _source_tree(tmp_path)
    output = tmp_path / "out"

    manifest = build_characterization_fixture(source, output, compiler="c++", execute=False)

    assert manifest["source_baseline_id"] == SOURCE_BASELINE_ID
    assert manifest["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    assert manifest["evidence_kind"] == "SOURCE_BEHAVIOR_CHARACTERIZATION"
    assert manifest["acceptance_claim"] == "A2 prerequisite only; not vessel validation"
    assert set(manifest["sha256"]) == {"source", "config", "compiler", "dependencies", "assets", "tests", "seeds", "output"}
    assert (output / "characterization.json").exists()
    assert (output / "manifest.json").exists()


def test_cli_requires_external_source_path_and_never_copies_source_tree(tmp_path: Path) -> None:
    source = _source_tree(tmp_path)
    output = tmp_path / "out"

    assert main(["--source", str(source), "--output", str(output), "--compiler", "c++", "--no-execute"]) == 0
    assert not (output / source.name).exists()
