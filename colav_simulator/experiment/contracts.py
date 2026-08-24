"""Versioned contracts for reproducible COLAV experiments."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np

from colav_simulator.core.colav.threat_assessment import ShipDomainProfile

SCHEMA_VERSION = "1.0"


class SessionState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


class ReproductionLevel(StrEnum):
    FUNCTIONAL = "functional_reproduction"
    NUMERICAL = "numerical_reproduction"
    ALGORITHM_VALIDATION = "algorithm_validation"


class RunOutcome(StrEnum):
    """Machine-readable execution result independent of evaluator status."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class InternalExecutionPurpose(StrEnum):
    """Narrow reasons allowed to use retained non-product integrations."""

    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    EVALUATOR_BASELINE = "EVALUATOR_BASELINE"


@dataclass(frozen=True)
class SeedBundle:
    """Independent random streams derived from one user-facing seed."""

    base: int
    scenario: int
    sensor: int
    tracker: int
    algorithm: int

    @classmethod
    def derive(cls, seed: int) -> SeedBundle:
        if seed < 0:
            raise ValueError("seed must be non-negative")
        children = np.random.SeedSequence(seed).spawn(4)
        values = [int(child.generate_state(1, dtype=np.uint32)[0]) for child in children]
        return cls(seed, *values)


@dataclass
class RunSpec:
    """Complete input needed to generate or replay one simulation episode."""

    scenario_id: str
    validation_rule_id: str | None = None
    algorithm_id: str = "nominal"
    tracker_id: str = "scenario_default"
    seed: int = 0
    episode_index: int = 0
    dt: float | None = None
    t_end: float | None = None
    reload_enc: bool = False
    terminate_on_collision_or_grounding: bool = True
    strict_no_fallback: bool = True
    solve_period_s: float | None = None
    deadline_mode: str = "ENFORCE"
    evaluator_profile_id: str = "ccta_2023_demo-v1"
    reproduction_level: ReproductionLevel = ReproductionLevel.FUNCTIONAL
    algorithm_config: dict[str, Any] = field(default_factory=dict)
    tracker_config: dict[str, Any] = field(default_factory=dict)
    domain_profile: ShipDomainProfile | Mapping[str, Any] | None = None
    scenario_override: dict[str, Any] | None = None
    output_root: str = "runs"
    replay_of_run_id: str | None = None
    historical_replay: dict[str, Any] | None = None
    historical_scenario_id: str | None = None
    algorithm_capability_evidence: dict[str, Any] | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Normalize IDs and reject invalid execution inputs."""
        self.scenario_id = self.scenario_id.strip()
        self.validation_rule_id = self.validation_rule_id.strip().lower() if self.validation_rule_id else None
        self.algorithm_id = self.algorithm_id.strip().lower()
        self.tracker_id = self.tracker_id.strip().lower()
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        if self.episode_index < 0:
            raise ValueError("episode_index must be non-negative")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.dt is not None and self.dt <= 0:
            raise ValueError("dt must be positive")
        if self.t_end is not None and self.t_end <= 0:
            raise ValueError("t_end must be positive")
        if self.solve_period_s is not None and self.solve_period_s <= 0:
            raise ValueError("solve_period_s must be positive")
        self.deadline_mode = self.deadline_mode.strip().upper()
        self.evaluator_profile_id = self.evaluator_profile_id.strip()
        if self.deadline_mode not in {"ENFORCE", "OFF"}:
            raise ValueError("deadline_mode must be ENFORCE or OFF")
        if not self.evaluator_profile_id:
            raise ValueError("evaluator_profile_id is required")
        if self.historical_replay is not None and not isinstance(self.historical_replay, dict):
            raise ValueError("historical_replay must be a serialized replay request mapping")
        self.historical_scenario_id = _normalize_historical_scenario_id(self)
        if self.algorithm_capability_evidence is not None:
            self.algorithm_capability_evidence = _normalize_algorithm_capability_evidence(self)
        if isinstance(self.reproduction_level, str):
            self.reproduction_level = ReproductionLevel(self.reproduction_level)
        if self.domain_profile is not None and not isinstance(self.domain_profile, ShipDomainProfile):
            self.domain_profile = _ship_domain_profile_from_mapping(self.domain_profile)

    @property
    def seeds(self) -> SeedBundle:
        return SeedBundle.derive(self.seed)

    @property
    def capability_tuple(self) -> tuple[str, str, str, str] | None:
        """Return execution capability evidence without changing scenario identity."""
        if self.algorithm_capability_evidence is not None:
            return tuple(self.algorithm_capability_evidence["exact_tuple"])  # type: ignore[return-value]
        if self.validation_rule_id is None:
            return None
        return (self.validation_rule_id, self.scenario_id, self.algorithm_id, self.tracker_id)

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["reproduction_level"] = self.reproduction_level.value
        if self.domain_profile is not None:
            output["domain_profile"] = {
                **self.domain_profile.to_dict(),
                "profile_hash": self.domain_profile.profile_hash,
            }
        return output

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RunSpec:
        return cls(**value)


def _ship_domain_profile_from_mapping(value: Mapping[str, Any]) -> ShipDomainProfile:
    """Decode one versioned profile while preserving its public hash identity."""
    if not isinstance(value, Mapping):
        raise ValueError("domain_profile must be a ShipDomainProfile or mapping")
    payload = dict(value)
    model = payload.pop("model", "OFF_CENTRED_ELLIPSE")
    if model != "OFF_CENTRED_ELLIPSE":
        raise ValueError("ShipDomainProfile model must be OFF_CENTRED_ELLIPSE")
    declared_hash = payload.pop("profile_hash", None)
    try:
        profile = ShipDomainProfile(**payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid ShipDomainProfile: {exc}") from exc
    if declared_hash is not None and str(declared_hash) != profile.profile_hash:
        raise ValueError("ShipDomainProfile profile_hash does not match profile parameters")
    return profile


def _normalize_algorithm_capability_evidence(spec: RunSpec) -> dict[str, Any]:
    if spec.historical_scenario_id is None:
        raise ValueError("Algorithm Capability evidence requires historical_scenario_id")
    evidence = dict(spec.algorithm_capability_evidence or {})
    exact_tuple = tuple(evidence.get("exact_tuple", ()))
    if evidence.get("binding_role") != "ALGORITHM_CAPABILITY_ONLY":
        raise ValueError("Algorithm Capability evidence binding_role is invalid")
    if evidence.get("geometry_equivalence") is not False:
        raise ValueError("Algorithm Capability evidence cannot claim geometry equivalence")
    if len(exact_tuple) != 4:
        raise ValueError("Algorithm Capability evidence requires one exact tuple")
    if exact_tuple[2:] != (spec.algorithm_id, spec.tracker_id):
        raise ValueError("Algorithm Capability evidence algorithm/tracker differs from RunSpec")
    evidence["exact_tuple"] = list(exact_tuple)
    return evidence


def _normalize_historical_scenario_id(spec: RunSpec) -> str | None:
    if spec.historical_scenario_id is None:
        return None
    historical_scenario_id = spec.historical_scenario_id.strip()
    if not historical_scenario_id or historical_scenario_id != spec.scenario_id:
        raise ValueError("historical_scenario_id must equal the authoritative scenario_id")
    return historical_scenario_id


@dataclass
class RunManifest:
    """Immutable run identity plus mutable execution outcome."""

    run_id: str
    created_at_utc: str
    spec: dict[str, Any]
    seeds: dict[str, int]
    code_commit: str
    code_dirty: bool
    python_version: str
    platform: str
    dependencies: dict[str, Any]
    spec_hash: str = ""
    simulation_config_hash: str = ""
    scenario_hash: str = ""
    episode_hash: str = ""
    enc_hash: str = ""
    trajectory_hash: str = ""
    trajectory_semantic_hash: str = ""
    trajectory_artifact_hash: str = ""
    scenario_provenance: dict[str, Any] = field(default_factory=dict)
    requested_algorithm: str = "nominal"
    executed_algorithm: str = "nominal"
    requested_tracker: str = "scenario_default"
    executed_tracker: str = "scenario_default"
    validation_rule_id: str | None = None
    scenario_readiness_grade: str = "G0"
    algorithm_readiness_grade: str = "G0"
    tracker_readiness_grade: str = "G0"
    capability_profile_id: str | None = None
    encounter_profile_id: str = "legacy-g3-v1"
    fallback_used: bool = False
    execution_outcome: RunOutcome | None = None
    diagnostic_only: bool = False
    diagnostic_only_reasons: list[str] = field(default_factory=list)
    algorithm_descriptor: dict[str, Any] | None = None
    algorithm_build_identity: dict[str, Any] | None = None
    collision_oracle_id: str = "footprint-adaptive-v1"
    ccd_step_tolerance_m: float = 0.25
    state: SessionState = SessionState.CREATED
    failure_reason: str | None = None
    failure_status: str | None = None
    evaluator_id: str | None = None
    evaluator_version: str | None = None
    evaluator_profile_id: str | None = None
    evaluator_profile_hash: str | None = None
    formula_set_id: str | None = None
    formula_set_hash: str | None = None
    evaluation_collision_oracle_id: str | None = None
    grounding_policy_id: str | None = None
    evaluation_schema_version: str | None = None
    evaluation_gate: str | None = None
    reproduction_status: str = "not_evaluated"
    replay_of_run_id: str | None = None
    replay_verified: bool | None = None
    historical_replay_evidence: dict[str, Any] | None = None
    historical_case_digest: str | None = None
    historical_reference_artifact_digest: str | None = None
    historical_execution_mode: str | None = None
    historical_scenario_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def create(cls, spec: RunSpec, dependencies: dict[str, Any] | None = None) -> RunManifest:
        commit, dirty = git_identity()
        spec_document = spec.to_dict()
        simulation_document = {
            key: value for key, value in spec_document.items() if key not in {"output_root", "replay_of_run_id"}
        }
        return cls(
            run_id=str(uuid.uuid4()),
            created_at_utc=datetime.now(UTC).isoformat(),
            spec=spec_document,
            seeds=asdict(spec.seeds),
            code_commit=commit,
            code_dirty=dirty,
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            dependencies=dependencies or {},
            spec_hash=content_hash(spec_document),
            simulation_config_hash=content_hash(simulation_document),
            requested_algorithm=spec.algorithm_id,
            executed_algorithm=spec.algorithm_id,
            requested_tracker=spec.tracker_id,
            executed_tracker=spec.tracker_id,
            validation_rule_id=spec.validation_rule_id,
            replay_of_run_id=spec.replay_of_run_id,
            historical_replay_evidence=(
                dict(spec.historical_replay.get("evidence", {})) if spec.historical_replay is not None else None
            ),
            diagnostic_only=spec.deadline_mode == "OFF",
            diagnostic_only_reasons=["deadline_mode=OFF"] if spec.deadline_mode == "OFF" else [],
        )

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["state"] = self.state.value
        output["execution_outcome"] = self.execution_outcome.value if self.execution_outcome else None
        return output


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically for hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=json_default)


def content_hash(value: Any) -> str:
    """Return the SHA-256 of a canonical JSON value."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def json_default(value: Any) -> Any:
    """Convert project and NumPy values into JSON-compatible values."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def git_identity(cwd: Path | None = None) -> tuple[str, bool]:
    """Read the current commit without invoking a Git subprocess."""
    root = cwd or Path(__file__).resolve().parents[2]
    try:
        git_dir = root / ".git"
        if git_dir.is_file():
            marker = git_dir.read_text(encoding="utf-8").strip()
            git_dir = (root / marker.removeprefix("gitdir:").strip()).resolve()
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            reference = head.removeprefix("ref: ")
            ref_path = git_dir / reference
            if not ref_path.is_file() and (git_dir / "commondir").is_file():
                common = (git_dir / (git_dir / "commondir").read_text(encoding="utf-8").strip()).resolve()
                ref_path = common / reference
            commit = ref_path.read_text(encoding="utf-8").strip()
        else:
            commit = head
        dirty_env = os.environ.get("COLAV_CODE_DIRTY")
        dirty = dirty_env != "0" if dirty_env is not None else True
        return commit, dirty
    except OSError:
        return "unknown", True
