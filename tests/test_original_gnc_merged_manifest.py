"""Merged MPC sources must preserve PID identity and source tamper detection."""

import csv
import shutil
from dataclasses import replace

import pytest

from colav_simulator.original_gnc.configuration import OriginalGncConfig
from colav_simulator.original_gnc.native import OriginalGncError


def test_original_gnc_merged_manifest_preserves_identity_and_rejects_tampering(tmp_path):
    config = OriginalGncConfig.from_dict({})
    manifest = config.source_root / "SOURCE_MANIFEST.csv"
    if not manifest.exists():
        pytest.skip("Optional original GNC source is unavailable")
    shutil.copyfile(manifest, tmp_path / manifest.name)
    with manifest.open(encoding="utf-8-sig") as stream:
        entries = list(csv.DictReader(stream))
    for entry in entries:
        target = tmp_path / entry["relative_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.source_root / entry["relative_path"], target)
    relocated = replace(config, source_root=tmp_path)
    relocated.source_assets()
    assert relocated.source_manifest_sha256 == config.source_manifest_sha256
    assert relocated.parameters() == config.parameters()
    source = tmp_path / next(e["relative_path"] for e in entries if "ship_control_node.cpp" in e["relative_path"])
    original = source.read_bytes()
    source.write_bytes(original + b"\n// changed\n")
    with pytest.raises(OriginalGncError, match="Changed original GNC source/asset"):
        relocated.source_assets()
    source.write_bytes(original)
    (tmp_path / manifest.name).write_bytes(manifest.read_bytes() + b"\n")
    with pytest.raises(OriginalGncError, match="manifest is unavailable or changed"):
        relocated.source_assets()
