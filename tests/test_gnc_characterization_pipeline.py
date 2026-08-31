from __future__ import annotations

import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.modular_gnc.characterization import (
    SOURCE_BASELINE_ID,
    CharacterizationError,
    build_characterization_fixture,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compiler_hash() -> str:
    return _sha256(Path(shutil.which("c++") or ""))


def _source_tree(tmp_path: Path) -> tuple[Path, str, dict[str, Path]]:
    source = tmp_path / "l45-source-20260824-v2"
    source.mkdir()
    source_file = source / "source.cpp"
    source_file.write_text("int source_identity = 1;\n", encoding="utf-8")
    recipe = source / "build_characterization.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        "printf '%s' "
        '\'{"schema_version":"agx-l45-characterization-output.v1","samples":[1.0,2.0]}\' '
        "> fixture-output.json\n"
        "python3 -c 'import sys,numpy as np; "
        "np.savez(sys.argv[1],source_values=np.array([1.0]))' "
        "fixture-output.npz\n",
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    manifest = source / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "baseline_id": SOURCE_BASELINE_ID,
                "files": {
                    "build_characterization.sh": _sha256(recipe),
                    "source.cpp": _sha256(source_file),
                },
            }
        ),
        encoding="utf-8",
    )
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
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256="0" * 64,
            metadata={},
        )

    source, manifest_hash, metadata = _source_tree(tmp_path)
    with pytest.raises(CharacterizationError, match="compiler unavailable"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="missing-cxx",
            expected_compiler_sha256="0" * 64,
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
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
        )


def test_pipeline_detects_recipe_tampering(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = source / "build_characterization.sh"
    recipe.write_text(recipe.read_text(encoding="utf-8") + "# tampered\n", encoding="utf-8")

    with pytest.raises(CharacterizationError, match="source file hash mismatch: build_characterization.sh"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
        )


def test_pipeline_detects_compiler_wrapper_tampering(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    compiler = tmp_path / "compiler-wrapper"
    compiler.write_text('#!/bin/sh\nexec c++ "$@"\n', encoding="utf-8")
    compiler.chmod(compiler.stat().st_mode | stat.S_IXUSR)
    compiler_hash = _sha256(compiler)
    compiler.write_text('#!/bin/sh\n# tampered\nexec c++ "$@"\n', encoding="utf-8")

    with pytest.raises(CharacterizationError, match="compiler executable hash mismatch"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler=str(compiler),
            expected_compiler_sha256=compiler_hash,
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
        )


def test_pipeline_rejects_stale_preexisting_output(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = source / "build_characterization.sh"
    recipe.write_text("#!/bin/sh\nset -eu\n# intentionally produce no output\n", encoding="utf-8")
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    manifest = source / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "baseline_id": SOURCE_BASELINE_ID,
                "files": {
                    "build_characterization.sh": _sha256(recipe),
                    "source.cpp": _sha256(source / "source.cpp"),
                },
            }
        ),
        encoding="utf-8",
    )
    (source / "fixture-output.json").write_text(
        '{"schema_version":"agx-l45-characterization-output.v1","samples":[99.0]}',
        encoding="utf-8",
    )

    with pytest.raises(CharacterizationError, match="new characterization JSON output unavailable"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=_sha256(manifest),
            metadata=metadata,
        )

    assert (source / "fixture-output.json").exists()


def test_readme_cli_recipe_declares_compiler_executable_identity() -> None:
    readme = Path("tools/gnc_characterization/README.md").read_text(encoding="utf-8")

    assert "--compiler-sha256 <independently-recorded-compiler-executable-sha256>" in readme
    assert "python -m colav_simulator.modular_gnc.characterization" in readme
    assert all(f"--{name} " in readme for name in ("source", "source-manifest", "output", "compiler", "manifest-sha256"))
    assert "--recipe " in readme
    assert "--recipe-sha256 " in readme
    assert "--build-input " in readme
    assert all(f"--{name} " in readme for name in ("config", "dependencies", "assets", "tests", "seeds"))


def test_pipeline_executes_recipe_and_hashes_actual_metadata(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    output = tmp_path / "out"
    compiler = Path(shutil.which("c++") or "")

    manifest = build_characterization_fixture(
        source,
        output,
        compiler="c++",
        expected_compiler_sha256=_sha256(compiler),
        expected_manifest_sha256=manifest_hash,
        metadata=metadata,
    )

    assert manifest["source_baseline_id"] == SOURCE_BASELINE_ID
    assert manifest["source_manifest_sha256"] == manifest_hash
    assert manifest["evidence_kind"] == "SOURCE_BEHAVIOR_CHARACTERIZATION"
    assert manifest["acceptance_claim"] == "A2 prerequisite only; not vessel validation"
    assert manifest["sha256"]["config"] == _sha256(metadata["config"])
    assert manifest["sha256"]["recipe"] == _sha256(source / "build_characterization.sh")
    assert manifest["sha256"]["compiler_executable"]
    assert manifest["recipe_executed"] is True
    assert (output / "characterization.json").exists()
    assert (output / "characterization.npz").exists()
    assert not (output / source.name).exists()


def test_pipeline_runs_external_recipe_without_touching_source(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = tmp_path / "repo-owned-recipe.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        "source_root=$1\njson_output=$2\nnpz_output=$3\ncompiler=$4\n"
        'test -d "$source_root"\n'
        'test -x "$compiler"\n'
        'printf \'%s\' \'{"schema_version":"agx-l45-characterization-output.v1","samples":[3.0]}\' > "$json_output"\n'
        "python3 -c 'import sys,numpy as np; "
        "np.savez(sys.argv[1],source_values=np.array([1.0]))' "
        '"$npz_output"\n',
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    probe = tmp_path / "probe.cpp"
    probe.write_text("int probe_identity = 1;\n", encoding="utf-8")
    source_output = source / "fixture-output.json"
    source_npz = source / "fixture-output.npz"
    source_snapshot = (source_output.exists(), source_npz.exists())

    manifest = build_characterization_fixture(
        source,
        tmp_path / "out",
        compiler="c++",
        expected_compiler_sha256=_compiler_hash(),
        expected_manifest_sha256=manifest_hash,
        metadata=metadata,
        recipe=recipe,
        expected_recipe_sha256=_sha256(recipe),
        build_inputs={"probe": probe},
    )

    assert manifest["recipe_mode"] == "repo_adapter"
    assert manifest["sha256"]["build_input:probe"] == _sha256(probe)
    assert manifest["sha256"]["output_npz"] == _sha256(tmp_path / "out" / "characterization.npz")
    assert (source_output.exists(), source_npz.exists()) == source_snapshot


def test_pipeline_accepts_source_only_csv_manifest(tmp_path: Path) -> None:
    source, _, metadata = _source_tree(tmp_path)
    source_manifest = source / "SOURCE_MANIFEST.csv"
    source_manifest.write_text(
        "relative_path,kind,size_bytes,lines,sha256\n"
        f"source.cpp,code,0,0,{_sha256(source / 'source.cpp')}\n"
        f"build_characterization.sh,build_or_runtime_asset,0,0,{_sha256(source / 'build_characterization.sh')}\n",
        encoding="utf-8",
    )
    recipe = tmp_path / "repo-owned-recipe.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\' \'{"schema_version":"agx-l45-characterization-output.v1","samples":[4.0]}\' > "$2"\n'
        "python3 -c 'import sys,numpy as np; "
        "np.savez(sys.argv[1],source_values=np.array([1.0]))' "
        '"$3"\n',
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    probe = tmp_path / "probe.cpp"
    probe.write_text("int probe_identity = 2;\n", encoding="utf-8")

    manifest = build_characterization_fixture(
        source,
        tmp_path / "out",
        compiler="c++",
        expected_compiler_sha256=_compiler_hash(),
        expected_manifest_sha256=_sha256(source_manifest),
        source_manifest=source_manifest,
        metadata=metadata,
        recipe=recipe,
        expected_recipe_sha256=_sha256(recipe),
        build_inputs={"probe": probe},
    )

    assert manifest["source_manifest_format"] == "csv"
    assert manifest["source_baseline_id"] == SOURCE_BASELINE_ID


def test_pipeline_rejects_external_recipe_hash_mismatch(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = tmp_path / "repo-owned-recipe.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\' \'{"schema_version":"agx-l45-characterization-output.v1","samples":[5.0]}\' > "$2"\n'
        "printf '%s' 'hash-npz' > \"$3\"\n",
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    probe = tmp_path / "probe.cpp"
    probe.write_text("int probe_identity = 3;\n", encoding="utf-8")

    with pytest.raises(CharacterizationError, match="recipe hash mismatch"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
            recipe=recipe,
            expected_recipe_sha256="0" * 64,
            build_inputs={"probe": probe},
        )


def test_pipeline_rejects_explicit_recipe_inside_frozen_source(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = source / "build_characterization.sh"
    probe = tmp_path / "probe.cpp"
    probe.write_text("int probe_identity = 5;\n", encoding="utf-8")

    with pytest.raises(CharacterizationError, match="external recipe must be outside frozen source"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
            recipe=recipe,
            expected_recipe_sha256=_sha256(recipe),
            build_inputs={"probe": probe},
        )


def test_pipeline_rejects_source_owned_recipe_not_bound_by_manifest(tmp_path: Path) -> None:
    source, _, metadata = _source_tree(tmp_path)
    manifest = source / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "baseline_id": SOURCE_BASELINE_ID,
                "files": {"source.cpp": _sha256(source / "source.cpp")},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CharacterizationError, match="source-owned recipe is not bound by source manifest"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=_sha256(manifest),
            metadata=metadata,
        )


def test_failed_run_preserves_existing_fixture_directory(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = tmp_path / "failing-recipe.sh"
    recipe.write_text("#!/bin/sh\nset -eu\nexit 1\n", encoding="utf-8")
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    probe = tmp_path / "probe.cpp"
    probe.write_text("int probe_identity = 6;\n", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    expected_files = {
        "characterization.json": b"old-json",
        "characterization.npz": b"old-npz",
        "manifest.json": b"old-manifest",
    }
    for name, contents in expected_files.items():
        (output / name).write_bytes(contents)

    with pytest.raises(CharacterizationError, match="characterization recipe failed"):
        build_characterization_fixture(
            source,
            output,
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
            recipe=recipe,
            expected_recipe_sha256=_sha256(recipe),
            build_inputs={"probe": probe},
        )

    assert {name: (output / name).read_bytes() for name in expected_files} == expected_files


def test_recipe_consumes_the_hashed_staged_build_input(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = tmp_path / "bound-input-recipe.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        "bound=$5\n"
        'case "$bound" in probe=*) probe=${bound#probe=} ;; *) exit 3 ;; esac\n'
        'test "$(cat "$probe")" = bound-probe\n'
        'printf \'%s\' \'{"schema_version":"agx-l45-characterization-output.v1","samples":[7.0]}\' > "$2"\n'
        "python3 -c 'import sys,numpy as np; np.savez(sys.argv[1],source_values=np.array([1.0]))' \"$3\"\n",
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    bound_probe = tmp_path / "bound-probe.cpp"
    bound_probe.write_text("bound-probe", encoding="utf-8")
    unrelated_probe = tmp_path / "unrelated-probe.cpp"
    unrelated_probe.write_text("unrelated-probe", encoding="utf-8")

    manifest = build_characterization_fixture(
        source,
        tmp_path / "out",
        compiler="c++",
        expected_compiler_sha256=_compiler_hash(),
        expected_manifest_sha256=manifest_hash,
        metadata=metadata,
        recipe=recipe,
        expected_recipe_sha256=_sha256(recipe),
        build_inputs={"probe": bound_probe},
    )

    assert manifest["sha256"]["build_input:probe"] == _sha256(bound_probe)
    assert _sha256(bound_probe) != _sha256(unrelated_probe)


def test_pipeline_rejects_invalid_npz_output(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = tmp_path / "repo-owned-recipe.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\' \'{"schema_version":"agx-l45-characterization-output.v1","samples":[6.0]}\' > "$2"\n'
        "printf '%s' 'not-an-npz' > \"$3\"\n",
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    probe = tmp_path / "probe.cpp"
    probe.write_text("int probe_identity = 4;\n", encoding="utf-8")

    with pytest.raises(CharacterizationError, match="NPZ output is invalid"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
            recipe=recipe,
            expected_recipe_sha256=_sha256(recipe),
            build_inputs={"probe": probe},
        )


def test_pipeline_rejects_zip_with_invalid_npy_member(tmp_path: Path) -> None:
    source, manifest_hash, metadata = _source_tree(tmp_path)
    recipe = tmp_path / "invalid-npy-recipe.sh"
    recipe.write_text(
        "#!/bin/sh\nset -eu\n"
        'printf \'%s\' \'{"schema_version":"agx-l45-characterization-output.v1","samples":[8.0]}\' > "$2"\n'
        "python3 -c 'import sys,zipfile; "
        'z=zipfile.ZipFile(sys.argv[1],"w"); '
        'z.writestr("source_values.npy",b"x"); z.close()\' '
        '"$3"\n',
        encoding="utf-8",
    )
    recipe.chmod(recipe.stat().st_mode | stat.S_IXUSR)
    probe = tmp_path / "probe.cpp"
    probe.write_text("int probe_identity = 7;\n", encoding="utf-8")

    with pytest.raises(CharacterizationError, match="NPZ output is invalid"):
        build_characterization_fixture(
            source,
            tmp_path / "out",
            compiler="c++",
            expected_compiler_sha256=_compiler_hash(),
            expected_manifest_sha256=manifest_hash,
            metadata=metadata,
            recipe=recipe,
            expected_recipe_sha256=_sha256(recipe),
            build_inputs={"probe": probe},
        )


def test_repository_recipe_and_probe_are_executable_and_documented() -> None:
    recipe = Path("tools/gnc_characterization/build_frozen_source_fixture.sh")
    probe = Path("tools/gnc_characterization/frozen_source_probe.cpp")

    assert recipe.is_file()
    assert recipe.stat().st_mode & stat.S_IXUSR
    assert probe.is_file()
    readme = Path("tools/gnc_characterization/README.md").read_text(encoding="utf-8")
    assert "build_frozen_source_fixture.sh" in readme
    assert "frozen_source_probe.cpp" in readme


def test_committed_agx_fixture_is_content_addressed_and_source_only() -> None:
    fixture_dir = Path("tests/fixtures/gnc_characterization")
    manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))
    characterization = fixture_dir / manifest["fixture_artifacts"]["json"]
    npz = fixture_dir / manifest["fixture_artifacts"]["npz"]

    assert manifest["evidence_kind"] == "SOURCE_BEHAVIOR_CHARACTERIZATION"
    assert manifest["acceptance_claim"] == "A2 prerequisite only; not vessel validation"
    assert manifest["source_baseline_id"] == SOURCE_BASELINE_ID
    assert manifest["recipe_mode"] == "repo_adapter"
    assert manifest["build_inputs"] == ["probe"]
    assert manifest["source_manifest_format"] == "csv"
    assert manifest["sha256"]["source"] == "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"
    assert manifest["sha256"]["config"] == "d2ce10e1576bf06dd29ffc707d9ef5e1b5ad9ce399c8292a14f20bc5ab6eb789"
    assert manifest["sha256"]["dependencies"] == "3781c60585a21a877d7bddd4d5c5e898eb6413fed004c6e49c2fe489e6a500cf"
    assert manifest["sha256"]["assets"] == "4af679cfd7d1e1008588f8ee2434f289c12ffbc08027acfcc8aa1aec2e49b20f"
    assert manifest["sha256"]["tests"] == "5f7acc3ee1496927b74b81a1a4d65d301c2ef3b169c59550a3706e86395960dc"
    assert manifest["sha256"]["seeds"] == "1fbb532fd2bbfa179537dadf2b7b8ddbc216ae8e16caad62ebcd557aedd72a67"
    assert manifest["sha256"]["compiler_executable"] == "2aafdb1e153fc490fbd510d352572eee55ecdd29dd95eca239b4460c1afe3a12"
    assert manifest["sha256"]["recipe"] == "8910cab2472d61429e47e9d8d323df5af321a8c9ddd46d77acb017265f3ac96c"
    assert manifest["sha256"]["build_input:probe"] == "894efd8f0f808740405eda34cdda1c1d758fcdf76e9f8aed012d9638117248f3"
    assert manifest["sha256"]["output"] == "a6a4bd18132499edc0753b9e2a0867d50056a129e15f32495322fde5bdffb56e"
    assert manifest["sha256"]["output_npz"] == "899b42efa0669af6b36ce578db437ebedba388e45e8520edcd4b861983ba4c49"
    for name in ("config", "dependencies", "assets", "tests", "seeds"):
        assert _sha256(fixture_dir / f"{name}.json") == manifest["sha256"][name]
    assert _sha256(characterization) == manifest["sha256"]["output"]
    assert _sha256(npz) == manifest["sha256"]["output_npz"]
    with zipfile.ZipFile(npz) as archive:
        assert archive.namelist() == ["source_values.npy", "source_value_count.npy"]
    payload = json.loads(characterization.read_text(encoding="utf-8"))
    assert payload["evidence_kind"] == "SOURCE_BEHAVIOR_CHARACTERIZATION"
    assert payload["claim_ceiling"] == "not_vessel_validation"
    expected_values = np.asarray([value for case in payload["cases"] for value in case["values"]], dtype=np.float64)
    with np.load(npz, allow_pickle=False) as arrays:
        np.testing.assert_array_equal(arrays["source_values"], expected_values)
        assert int(arrays["source_value_count"][0]) == expected_values.size
