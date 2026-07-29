"""Versioned, source-traceable evaluator profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_EVALUATOR_PROFILE_ID = "ccta_2023_demo-v1"
FORMULA_SET_ID = "ocean-engineering-2023-v1"
PROFILE_SCHEMA_VERSION = "evaluator-profile-v1"


@dataclass(frozen=True)
class StageParameters:
    stage2_entry_m: float
    stage3_entry_m: float
    stage4_entry_m: float


@dataclass(frozen=True)
class SafetyParameters:
    preferred_m: float
    minimum_m: float
    near_miss_m: float
    collision_m: float


@dataclass(frozen=True)
class SafetyDomainParameters:
    model: str = "disabled"
    longitudinal_length_factor: float = 0.0
    transverse_length_factor: float = 0.0


@dataclass(frozen=True)
class EncounterParameters:
    alpha_crit_13_deg: float
    alpha_crit_14_deg: float
    alpha_crit_15_deg: float
    overtaking_min_deg: float
    overtaking_max_deg: float
    emergency_tcpa_s: float
    exit_range_factor: float


@dataclass(frozen=True)
class ManeuverParameters:
    moving_speed_mps: float
    acceleration_mps2: float
    course_rate_deg_s: float
    detectable_turn_deg: float
    apparent_turn_deg: float
    detectable_relative_speed: float
    apparent_relative_speed: float
    starboard_turn_min_deg: float


@dataclass(frozen=True)
class WeightParameters:
    range_minimum: float
    range_near_miss: float
    range_collision: float
    pose_contact: float
    pose_relative_bearing: float
    apparent_course: float
    apparent_speed: float
    head_on_non_starboard: float
    head_on_starboard_to_starboard: float
    ahead_overtaking: float
    ahead_crossing: float


@dataclass(frozen=True)
class EvaluatorProfile:
    schema_version: str
    profile_id: str
    profile_kind: str
    source_refs: tuple[str, ...]
    sample_interval_s: float
    gaussian_sigma_samples: float
    stages: StageParameters
    safety: SafetyParameters
    encounter: EncounterParameters
    maneuver: ManeuverParameters
    weights: WeightParameters
    safety_domain: SafetyDomainParameters = SafetyDomainParameters()
    reconstruction_assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject profiles with inconsistent units, ranges, or weights."""
        if self.schema_version != PROFILE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported evaluator profile schema: {self.schema_version}")
        if not self.profile_id.strip():
            raise ValueError("profile_id is required")
        if self.profile_kind not in {"paper_compatible", "ship_length_scaled"}:
            raise ValueError(f"Unsupported evaluator profile kind: {self.profile_kind}")
        if self.sample_interval_s <= 0.0 or self.gaussian_sigma_samples < 0.0:
            raise ValueError("sampling parameters must be non-negative and interval must be positive")
        stage_values = (
            self.stages.stage2_entry_m,
            self.stages.stage3_entry_m,
            self.stages.stage4_entry_m,
        )
        if not stage_values[0] > stage_values[1] > stage_values[2] > 0.0:
            raise ValueError("stage ranges must satisfy stage2 > stage3 > stage4 > 0")
        safety_values = (
            self.safety.preferred_m,
            self.safety.minimum_m,
            self.safety.near_miss_m,
            self.safety.collision_m,
        )
        if not safety_values[0] > safety_values[1] > safety_values[2] > safety_values[3] >= 0.0:
            raise ValueError("safety ranges must satisfy preferred > minimum > near_miss > collision >= 0")
        range_weights = (
            self.weights.range_minimum,
            self.weights.range_near_miss,
            self.weights.range_collision,
        )
        pose_weights = (self.weights.pose_contact, self.weights.pose_relative_bearing)
        if abs(sum(range_weights) - 1.0) > 1e-9:
            raise ValueError("range weights must sum to one")
        if abs(sum(pose_weights) - 1.0) > 1e-9:
            raise ValueError("pose weights must sum to one")
        if abs(self.weights.apparent_course + self.weights.apparent_speed - 1.0) > 1e-9:
            raise ValueError("apparent maneuver weights must sum to one")
        if self.safety_domain.model not in {"disabled", "fujii_1971"}:
            raise ValueError(f"Unsupported safety-domain model: {self.safety_domain.model}")
        factors = (
            self.safety_domain.longitudinal_length_factor,
            self.safety_domain.transverse_length_factor,
        )
        if self.safety_domain.model == "disabled" and factors != (0.0, 0.0):
            raise ValueError("disabled safety domain must use zero length factors")
        if self.safety_domain.model != "disabled" and not factors[0] > factors[1] > 0.0:
            raise ValueError("safety-domain factors must satisfy longitudinal > transverse > 0")

    @property
    def profile_hash(self) -> str:
        document = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(document.encode("utf-8")).hexdigest()

    @property
    def formula_set_id(self) -> str:
        return FORMULA_SET_ID

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["profile_hash"] = self.profile_hash
        output["formula_set_id"] = self.formula_set_id
        return output


def available_profiles() -> tuple[str, ...]:
    """Return profile IDs available in the packaged configuration."""
    return tuple(path.stem for path in _profile_root().glob("*.yaml"))


@lru_cache(maxsize=16)
def load_evaluator_profile(profile_id: str = DEFAULT_EVALUATOR_PROFILE_ID) -> EvaluatorProfile:
    """Load and validate one immutable named profile."""
    path = _profile_root() / f"{profile_id}.yaml"
    if not path.is_file():
        available = ", ".join(available_profiles())
        raise ValueError(f"Unknown evaluator profile {profile_id!r}; available: {available}")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"Evaluator profile {profile_id!r} must be a mapping")
    if document.get("profile_id") != profile_id:
        raise ValueError(f"Evaluator profile filename/id mismatch for {profile_id!r}")
    return _parse_profile(document)


def _parse_profile(value: dict[str, Any]) -> EvaluatorProfile:
    return EvaluatorProfile(
        schema_version=str(value["schema_version"]),
        profile_id=str(value["profile_id"]),
        profile_kind=str(value["profile_kind"]),
        source_refs=tuple(str(item) for item in value.get("source_refs", [])),
        sample_interval_s=float(value["sampling"]["interval_s"]),
        gaussian_sigma_samples=float(value["sampling"]["gaussian_sigma_samples"]),
        stages=StageParameters(**_float_values(value["stages"])),
        safety=SafetyParameters(**_float_values(value["safety"])),
        encounter=EncounterParameters(**_float_values(value["encounter"])),
        maneuver=ManeuverParameters(**_float_values(value["maneuver"])),
        weights=WeightParameters(**_float_values(value["weights"])),
        safety_domain=SafetyDomainParameters(
            model=str(value.get("safety_domain", {}).get("model", "disabled")),
            longitudinal_length_factor=float(
                value.get("safety_domain", {}).get("longitudinal_length_factor", 0.0)
            ),
            transverse_length_factor=float(
                value.get("safety_domain", {}).get("transverse_length_factor", 0.0)
            ),
        ),
        reconstruction_assumptions=tuple(str(item) for item in value.get("reconstruction_assumptions", [])),
    )


def _float_values(value: dict[str, Any]) -> dict[str, float]:
    return {str(key): float(item) for key, item in value.items()}


def _profile_root() -> Path:
    source = Path(__file__).resolve()
    candidates = (
        source.parents[2] / "config" / "evaluator",
        source.parents[1] / "config" / "evaluator",
    )
    return next((path for path in candidates if path.is_dir()), candidates[0])
