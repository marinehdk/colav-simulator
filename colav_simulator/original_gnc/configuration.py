"""Frozen-source configuration for the independent original GNC backend."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from colav_simulator.original_gnc.native import APPROVED_SOURCE_MANIFEST_SHA256, OriginalGncError

SOURCE_MANIFEST_SHA256 = APPROVED_SOURCE_MANIFEST_SHA256
ORIGINAL_OFF = "original-gnc-20260914-v1-env-off"
ORIGINAL_ON = "original-gnc-20260914-v1-env-on"
BASELINE = Path(__file__).with_name("data") / "baseline.json"


@dataclass(frozen=True)
class OriginalGncConfig:
    """Select source/build locations and the original E0/E4 environment profile."""

    source_root: Path
    build_directory: Path
    environment: bool = False

    @classmethod
    def from_dict(cls, value: dict) -> OriginalGncConfig:
        """Resolve only documented independent-backend options."""
        unknown = set(value) - {"source_root", "build_directory", "environment"}
        if unknown:
            raise ValueError(f"Unknown original GNC configuration: {sorted(unknown)}")
        if not isinstance(value.get("environment", False), bool):
            raise ValueError("Original GNC environment must be boolean")
        root = Path(__file__).resolve().parents[2]
        source = (
            value.get("source_root")
            or os.environ.get("COLAV_ORIGINAL_GNC_SOURCE")
            or Path.home() / "Code/GNC"
        )
        build = (
            value.get("build_directory") or os.environ.get("COLAV_ORIGINAL_GNC_BUILD") or root / "build/original_gnc-current"
        )
        return cls(Path(source).expanduser().resolve(), Path(build).expanduser().resolve(), value.get("environment", False))

    def to_dict(self) -> dict:
        """Persist explicit locations so task working directories cannot change them."""
        return {
            "source_root": str(self.source_root),
            "build_directory": str(self.build_directory),
            "environment": self.environment,
        }

    @property
    def stack_id(self) -> str:
        """Versioned identity, separate from every existing Full Stack ID."""
        return ORIGINAL_ON if self.environment else ORIGINAL_OFF

    @property
    def backend_kind(self) -> str:
        """Catalog backend discriminator for this frozen lane."""
        return "original_gnc"

    @property
    def source_manifest_sha256(self) -> str:
        """Approved manifest identity of this frozen lane."""
        return SOURCE_MANIFEST_SHA256

    def source_assets(self) -> tuple[dict, dict, dict]:
        """Verify all frozen source bytes and map relocated assets by content."""
        manifest = self.source_root / "SOURCE_MANIFEST.csv"
        if not manifest.is_file() or hashlib.sha256(manifest.read_bytes()).hexdigest() != SOURCE_MANIFEST_SHA256:
            raise OriginalGncError("Approved original GNC source manifest is unavailable or changed")
        local = {}
        with manifest.open(encoding="utf-8-sig") as stream:
            for entry in csv.DictReader(stream):
                path = (self.source_root / entry["relative_path"]).resolve()
                if (
                    self.source_root not in path.parents
                    or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
                ):
                    raise OriginalGncError(f"Changed original GNC source/asset: {entry['relative_path']}")
                local[entry["sha256"]] = str(path)
        baseline = json.loads(BASELINE.read_text())
        if baseline["source_manifest_sha256"] != SOURCE_MANIFEST_SHA256:
            raise OriginalGncError("Original GNC baseline uses a different source revision")
        locations = {}
        for old, digest in baseline["assets"].items():
            if digest not in local:
                raise OriginalGncError(f"Original GNC asset has no byte-identical local file: {old}")
            locations[old] = local[digest]
        roots = {p.parent.name: str(p.parent) for p in (self.source_root / "src").glob("*/*/package.xml")}
        policy = yaml.safe_load(
            (self.source_root / "src/mission/mission_supervisor/config/propulsion_policy.yaml").read_text()
        )
        return roots, locations, policy

    def parameters(self) -> dict:
        """Copy original observed values; caller changes initialization only."""
        return copy.deepcopy(json.loads(BASELINE.read_text())["parameters"])

    def response_approximation(self, input_kind: str = "route_plan") -> dict:
        """Return measured predictor approximations without asserting qualification."""
        if input_kind not in {"route_plan", "velocity_intent"}:
            raise OriginalGncError(f"Unsupported GNC response input kind: {input_kind}")
        path = BASELINE.with_name(
            "response_approximation_velocity.json" if input_kind == "velocity_intent" else "response_approximation.json"
        )
        document = json.loads(path.read_text())
        if document["source_manifest_sha256"] != SOURCE_MANIFEST_SHA256:
            raise OriginalGncError("Response approximation belongs to a different source version")
        document["artifact_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return document
