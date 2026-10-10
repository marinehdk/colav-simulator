"""Frozen-source configuration for the independent Authoritative MPC backend.

Same execution chain as the baseline original lane (guidance, allocation,
dynamics, environment) with the controller module extracted from the frozen
colleague MPC package ``gnc/mpc_control`` in external-reference mode.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from colav_simulator.environment_settings import original_parameters
from colav_simulator.original_gnc.native import OriginalGncError

# SOURCE_MANIFEST.csv of GNC worktree lane feat/mpc-control-lane (commit d917ed9):
# baseline tree 0bbce06 plus the frozen mpc_control package import.
MPC_SOURCE_MANIFEST_SHA256 = "f7ee193e04b5165444a680b1e774e8b730639aa13dfd9f013face25ee5cc8a8d"
MPC_OFF = "authoritative-mpc-20260921-v1-env-off"
MPC_ON = "authoritative-mpc-20260921-v1-env-on"
BASELINE = Path(__file__).with_name("data") / "baseline.json"


@dataclass(frozen=True)
class AuthoritativeMpcConfig:
    """Select the MPC controller lane's source/build locations and E0/E4 profile."""

    source_root: Path
    build_directory: Path
    environment: bool = False
    environment_settings: dict | None = None

    @classmethod
    def from_dict(cls, value: dict) -> AuthoritativeMpcConfig:
        """Resolve only documented independent-backend options."""
        unknown = set(value) - {"source_root", "build_directory", "environment", "environment_settings"}
        if unknown:
            raise ValueError(f"Unknown Authoritative MPC configuration: {sorted(unknown)}")
        if not isinstance(value.get("environment", False), bool):
            raise ValueError("Authoritative MPC environment must be boolean")
        root = Path(__file__).resolve().parents[2]
        source = (
            value.get("source_root")
            or os.environ.get("COLAV_AUTHORITATIVE_MPC_SOURCE")
            or Path.home() / "Code/GNC-mpc-lane"
        )
        build = (
            value.get("build_directory")
            or os.environ.get("COLAV_AUTHORITATIVE_MPC_BUILD")
            or root / "build/original_mpc-current"
        )
        return cls(
            Path(source).expanduser().resolve(), Path(build).expanduser().resolve(),
            value.get("environment", False), value.get("environment_settings"),
        )

    def to_dict(self) -> dict:
        """Persist explicit locations so task working directories cannot change them."""
        return {
            "source_root": str(self.source_root),
            "build_directory": str(self.build_directory),
            "environment": self.environment,
            **({"environment_settings": self.environment_settings} if self.environment_settings is not None else {}),
        }

    @property
    def stack_id(self) -> str:
        """Versioned identity, separate from every existing Full Stack ID."""
        return MPC_ON if self.environment else MPC_OFF

    @property
    def source_manifest_sha256(self) -> str:
        """Approved manifest identity of this controller lane."""
        return MPC_SOURCE_MANIFEST_SHA256

    @property
    def backend_kind(self) -> str:
        """Catalog backend discriminator for this frozen lane."""
        return "authoritative_mpc"

    def source_assets(self) -> tuple[dict, dict, dict]:
        """Verify all frozen source bytes and map relocated assets by content."""
        manifest = self.source_root / "SOURCE_MANIFEST.csv"
        if not manifest.is_file() or hashlib.sha256(manifest.read_bytes()).hexdigest() != MPC_SOURCE_MANIFEST_SHA256:
            raise OriginalGncError("Approved Authoritative MPC source manifest is unavailable or changed")
        local = {}
        with manifest.open(encoding="utf-8-sig") as stream:
            for entry in csv.DictReader(stream):
                path = (self.source_root / entry["relative_path"]).resolve()
                if (
                    self.source_root not in path.parents
                    or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
                ):
                    raise OriginalGncError(f"Changed Authoritative MPC source/asset: {entry['relative_path']}")
                local[entry["sha256"]] = str(path)
        baseline = json.loads(BASELINE.read_text())
        if baseline["source_manifest_sha256"] != MPC_SOURCE_MANIFEST_SHA256:
            raise OriginalGncError("Authoritative MPC baseline uses a different source revision")
        locations = {}
        for old, digest in baseline["assets"].items():
            if digest not in local:
                raise OriginalGncError(f"Authoritative MPC asset has no byte-identical local file: {old}")
            locations[old] = local[digest]
        roots = {p.parent.name: str(p.parent) for p in (self.source_root / "src").glob("*/*/package.xml")}
        policy = yaml.safe_load(
            (self.source_root / "src/mission/mission_supervisor/config/propulsion_policy.yaml").read_text()
        )
        return roots, locations, policy

    def parameters(self) -> dict:
        """Copy the MPC lane parameter set; caller changes initialization only."""
        return original_parameters(
            json.loads(BASELINE.read_text())["parameters"], self.environment_settings if self.environment else None,
        )

    def response_approximation(self, input_kind: str = "route_plan") -> dict:
        """Return borrowed provisional constants; qualification is computed, not claimed."""
        if input_kind not in {"route_plan", "velocity_intent"}:
            raise OriginalGncError(f"Unsupported GNC response input kind: {input_kind}")
        path = BASELINE.with_name(
            "response_approximation_velocity.json" if input_kind == "velocity_intent" else "response_approximation.json"
        )
        document = json.loads(path.read_text())
        if document["source_manifest_sha256"] != MPC_SOURCE_MANIFEST_SHA256:
            raise OriginalGncError("Response approximation belongs to a different source version")
        document["artifact_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return document
