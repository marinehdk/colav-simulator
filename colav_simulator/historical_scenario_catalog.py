"""Bounded Historical AIS scenario catalog and source binding.

The catalog is deliberately separate from the legacy YAML scenario catalog.
Its descriptor is an immutable content-addressed declaration of the currently
qualified benchmark window; the external archive is opened only through the
explicit ``COLAV_HAIS_ARCHIVE_PATH`` binding.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from colav_simulator.historical_acceptance import HistoricalAISDimensionRecord, HistoricalAISDimensionRegistry
from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_compare import HistoricalBenchmarkTrajectory
from colav_simulator.historical_enc import build_expanded_romsdal_profile
from colav_simulator.historical_serialization import semantic_hash

HISTORICAL_AIS_SCENARIO_ID = "hais_romsdal_20260701_120000_120100"
HISTORICAL_AIS_SCENARIO_SCHEMA_VERSION = "historical-ais-scenario.v1"
HAIS_ARCHIVE_ENV_VAR = "COLAV_HAIS_ARCHIVE_PATH"


class HistoricalAISScenarioReadiness(str, Enum):
    """Typed source readiness; only ``READY`` may create a workflow."""

    READY = "READY"
    SOURCE_BINDING_MISSING = "SOURCE_BINDING_MISSING"
    SOURCE_BINDING_NOT_FOUND = "SOURCE_BINDING_NOT_FOUND"
    SOURCE_ARCHIVE_UNREADABLE = "SOURCE_ARCHIVE_UNREADABLE"
    SOURCE_ARCHIVE_DIGEST_MISMATCH = "SOURCE_ARCHIVE_DIGEST_MISMATCH"


class HistoricalAISScenarioLimitation(str, Enum):
    """Typed boundaries shown by the scene catalog and workbench."""

    CURRENT_WINDOW_ONLY = "CURRENT_WINDOW_ONLY"
    CURRENT_ACTOR_SET_ONLY = "CURRENT_ACTOR_SET_ONLY"
    ARCHIVE_NOT_FULLY_ENC_QUALIFIED = "ARCHIVE_NOT_FULLY_ENC_QUALIFIED"
    AIS_COVERAGE_NOT_EXHAUSTIVE = "AIS_COVERAGE_NOT_EXHAUSTIVE"
    DIMENSIONS_ONLY_CURRENT_ACTOR_SET = "DIMENSIONS_ONLY_CURRENT_ACTOR_SET"
    ARCHIVE_SCOPE_IS_NOT_RUNTIME_SELECTION = "ARCHIVE_SCOPE_IS_NOT_RUNTIME_SELECTION"


class HistoricalAISScenarioError(ValueError):
    """Fail-closed scenario catalog error with a machine-readable status."""

    def __init__(self, status: HistoricalAISScenarioReadiness | str, reason: str) -> None:
        super().__init__(reason)
        self.status = HistoricalAISScenarioReadiness(status)

    def detail(self) -> dict[str, Any]:
        return {"status": self.status.value, "reason": str(self)}


@dataclass(frozen=True)
class HistoricalAISScenarioSourceReadiness:
    """Public readiness evidence that never exposes the configured local path."""

    status: HistoricalAISScenarioReadiness
    expected_archive_sha256: str
    observed_archive_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "env_var": HAIS_ARCHIVE_ENV_VAR,
            "expected_archive_sha256": self.expected_archive_sha256,
            "observed_archive_sha256": self.observed_archive_sha256,
        }


@dataclass(frozen=True)
class HistoricalAISScenarioDescriptor:
    """Immutable public descriptor for one bounded Historical AIS scene."""

    schema_version: str
    scenario_id: str
    display_name: str
    kind: str
    modes: tuple[str, ...]
    archive_scope: Mapping[str, Any]
    current_window: Mapping[str, Any]
    enc: Mapping[str, Any]
    dimensions: Mapping[str, Any]
    runtime_binding: Mapping[str, Any]
    source_binding: Mapping[str, Any]
    limitations: tuple[str, ...]
    descriptor_sha256: str = ""

    def __post_init__(self) -> None:
        """Validate descriptor identity and compute its content digest."""
        if self.schema_version != HISTORICAL_AIS_SCENARIO_SCHEMA_VERSION:
            raise ValueError("unsupported Historical AIS scenario descriptor schema")
        if self.scenario_id != HISTORICAL_AIS_SCENARIO_ID:
            raise ValueError("unsupported Historical AIS scenario ID")
        if self.kind != "HISTORICAL_AIS":
            raise ValueError("Historical AIS scenario kind is required")
        if tuple(self.modes) != ("HISTORICAL_REPLAY", "COUNTERFACTUAL"):
            raise ValueError("Historical AIS scenario must publish Replay and Counterfactual modes")
        if str(self.source_binding.get("env_var")) != HAIS_ARCHIVE_ENV_VAR:
            raise ValueError("Historical AIS source binding must use COLAV_HAIS_ARCHIVE_PATH")
        expected = str(self.source_binding.get("expected_archive_sha256", ""))
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise ValueError("Historical AIS archive digest must be a lowercase SHA-256")
        object.__setattr__(self, "modes", tuple(self.modes))
        object.__setattr__(self, "archive_scope", dict(self.archive_scope))
        object.__setattr__(self, "current_window", dict(self.current_window))
        object.__setattr__(self, "enc", dict(self.enc))
        object.__setattr__(self, "dimensions", dict(self.dimensions))
        object.__setattr__(self, "runtime_binding", dict(self.runtime_binding))
        object.__setattr__(self, "source_binding", dict(self.source_binding))
        limitations = tuple(HistoricalAISScenarioLimitation(value).value for value in self.limitations)
        object.__setattr__(self, "limitations", limitations)
        if not self.descriptor_sha256:
            object.__setattr__(self, "descriptor_sha256", semantic_hash(self._identity_dict()))
        elif self.descriptor_sha256 != semantic_hash(self._identity_dict()):
            raise ValueError("Historical AIS scenario descriptor digest mismatch")

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "display_name": self.display_name,
            "kind": self.kind,
            "modes": list(self.modes),
            "archive_scope": dict(self.archive_scope),
            "current_window": dict(self.current_window),
            "enc": dict(self.enc),
            "dimensions": dict(self.dimensions),
            "runtime_binding": dict(self.runtime_binding),
            "source_binding": dict(self.source_binding),
            "limitations": list(self.limitations),
        }

    @property
    def archive_sha256(self) -> str:
        return str(self.source_binding["expected_archive_sha256"])

    def to_dict(self) -> dict[str, Any]:
        document = self._identity_dict()
        document["descriptor_sha256"] = self.descriptor_sha256
        return document

    def readiness(self, environ: Mapping[str, str] | None = None) -> HistoricalAISScenarioSourceReadiness:
        """Check configured source identity without exposing its local path."""
        environ = os.environ if environ is None else environ
        raw_path = str(environ.get(HAIS_ARCHIVE_ENV_VAR, "")).strip()
        if not raw_path:
            return HistoricalAISScenarioSourceReadiness(
                HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING,
                self.archive_sha256,
            )
        source = Path(raw_path).expanduser()
        if not source.is_file():
            return HistoricalAISScenarioSourceReadiness(
                HistoricalAISScenarioReadiness.SOURCE_BINDING_NOT_FOUND,
                self.archive_sha256,
            )
        try:
            observed = _sha256_file(source)
        except OSError:
            return HistoricalAISScenarioSourceReadiness(
                HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_UNREADABLE,
                self.archive_sha256,
            )
        return HistoricalAISScenarioSourceReadiness(
            HistoricalAISScenarioReadiness.READY
            if observed == self.archive_sha256
            else HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_DIGEST_MISMATCH,
            self.archive_sha256,
            observed,
        )

    def require_source(self, environ: Mapping[str, str] | None = None) -> Path:
        """Resolve and verify the explicit archive binding before any workflow work."""
        environ = os.environ if environ is None else environ
        raw_path = str(environ.get(HAIS_ARCHIVE_ENV_VAR, "")).strip()
        readiness = self.readiness(environ)
        if readiness.status is not HistoricalAISScenarioReadiness.READY:
            raise HistoricalAISScenarioError(readiness.status, _readiness_reason(readiness, raw_path))
        return Path(raw_path).expanduser().resolve()

    def selection(self) -> HistoricalAISSelection:
        """Return the immutable current-window selection contract."""
        window = self.current_window
        return HistoricalAISSelection(
            start_utc=str(window["start_utc"]),
            end_utc=str(window["end_utc"]),
            mmsi=tuple(int(value) for value in window["selection_mmsi"]),
            bbox=tuple(float(value) for value in window["bbox"]),
            entries=(str(window["entry_name"]),),
        )

    def build_workflow_payload(
        self,
        mode: str,
        *,
        run_spec_overrides: Mapping[str, Any] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build a complete normal Historical workflow request from this descriptor."""
        normalized_mode = str(mode).strip().upper()
        if normalized_mode not in self.modes:
            raise HistoricalAISScenarioError(
                HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING,
                f"unsupported Historical AIS workflow mode: {mode}",
            )
        source = self.require_source(environ)
        selection = self.selection()
        window = self.current_window
        dataset = HistoricalAISDatasetReader(source).read(selection)
        observed = dataset.descriptor
        if observed.archive_sha256 != self.archive_sha256:
            raise HistoricalAISScenarioError(
                HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_DIGEST_MISMATCH,
                "Historical AIS archive identity changed during request preparation",
            )
        expected_entry = {
            "entry_name": str(window["entry_name"]),
            "sha256": str(window["entry_sha256"]),
            "uncompressed_bytes": int(window["entry_uncompressed_bytes"]),
            "crc32": int(window["entry_crc32"]),
        }
        selection_document = selection.to_dict()
        selection_document.pop("schema_version", None)
        if normalized_mode == "HISTORICAL_REPLAY":
            return {
                "mode": normalized_mode,
                "source_path": str(source),
                "selection": selection_document,
                "expected_archive_sha256": self.archive_sha256,
                "expected_entries": [expected_entry],
                "expected_schema_sha256": str(window["expected_schema_sha256"]),
                "expected_selection_sha256": str(window["expected_selection_sha256"]),
                "replay": self._replay_document(),
                "run_spec": self._run_spec("HISTORICAL_REPLAY", run_spec_overrides),
            }

        enc_profile = build_expanded_romsdal_profile()
        if enc_profile.profile_digest != str(self.enc["profile_digest"]):
            raise HistoricalAISScenarioError(
                HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_UNREADABLE,
                "Romsdal ENC profile digest differs from the published scene descriptor",
            )
        human_reference = _historical_reference(dataset, enc_profile, int(window["reference_mmsi"]))
        return {
            "mode": normalized_mode,
            "source_path": str(source),
            "selection": selection_document,
            "expected_archive_sha256": self.archive_sha256,
            "expected_entries": [expected_entry],
            "expected_schema_sha256": str(window["expected_schema_sha256"]),
            "expected_selection_sha256": str(window["expected_selection_sha256"]),
            "enc_profile": _enc_document(enc_profile),
            "case": self._case_document(),
            "human_reference": human_reference.to_dict(),
            "alignment_profile": {},
            "run_spec": self._run_spec("COUNTERFACTUAL", run_spec_overrides),
        }

    def _run_spec(self, mode: str, overrides: Mapping[str, Any] | None) -> dict[str, Any]:
        binding = self.runtime_binding
        if mode == "HISTORICAL_REPLAY":
            result: dict[str, Any] = {
                "scenario_id": str(binding["execution_scenario_id"]),
                "validation_rule_id": str(binding["validation_rule_id"]),
                "algorithm_id": "nominal",
                "tracker_id": str(binding["tracker_id"]),
                "t_end": 60.0,
                "terminate_on_collision_or_grounding": False,
                "strict_no_fallback": True,
                "evaluator_profile_id": str(binding["evaluator_profile_id"]),
            }
        else:
            result = {
                "scenario_id": str(binding["execution_scenario_id"]),
                "validation_rule_id": str(binding["validation_rule_id"]),
                "algorithm_id": str(binding["algorithm_id"]),
                "tracker_id": str(binding["tracker_id"]),
                "t_end": 60.0,
                "terminate_on_collision_or_grounding": False,
                "strict_no_fallback": True,
                "evaluator_profile_id": str(binding["evaluator_profile_id"]),
                "domain_profile": dict(binding["domain_profile"]),
            }
        if overrides:
            allowed = {
                "algorithm_config",
                "tracker_config",
                "dt",
                "t_end",
                "evaluator_profile_id",
                "domain_profile",
            }
            unknown = sorted(set(overrides).difference(allowed))
            if unknown:
                raise ValueError(f"unsupported Historical AIS run options: {unknown}")
            result.update(dict(overrides))
            if mode == "HISTORICAL_REPLAY" and result.get("algorithm_id") != "nominal":
                raise ValueError("Historical Replay cannot execute a COLAV algorithm")
        return result

    def _replay_document(self) -> dict[str, Any]:
        return {
            "reference_mmsi": int(self.current_window["reference_mmsi"]),
            "reconstruction_profile": {
                "profile_id": "historical-actor-reconstruction.v1",
                "time_step_s": 1.0,
                "max_interpolation_gap_s": 300.0,
                "projection_crs": "EPSG:32633",
                "source_crs": "EPSG:4326",
                "coordinate_axis_order": "longitude_latitude",
                "gap_policy": "terminate_without_ghost_extrapolation",
            },
            "dimension_registry": {
                **self._dimension_registry().to_dict(),
                "registry_digest": self._dimension_registry().digest,
            },
            "dimension_effective_at_utc": str(self.current_window["t0_utc"]),
            "dt_sim": 1.0,
            "t_end_s": 60.0,
            "scenario_name": self.scenario_id,
            "utm_zone": 33,
        }

    def _case_document(self) -> dict[str, Any]:
        return {
            "published": True,
            "reference_mmsi": int(self.current_window["reference_mmsi"]),
            "t0_utc": str(self.current_window["t0_utc"]),
            "discovery_profile": {
                "max_encounter_range_m": 10_000.0,
                "min_closing_speed_mps": 0.0,
                "min_pre_t0_samples": 2,
                "min_pre_t0_duration_s": 1.0,
            },
            "dimension_overrides": {
                str(record["mmsi"]): {
                    "length_m": record["length_m"],
                    "width_m": record["width_m"],
                    "provenance": record["provenance"],
                    "source_digest": record["source_digest"],
                }
                for record in self.dimensions["records"]
            },
        }

    def _dimension_registry(self) -> HistoricalAISDimensionRegistry:
        records = tuple(
            HistoricalAISDimensionRecord(
                **{
                    **dict(record),
                    "source_urls": tuple(record.get("source_urls", ())),
                }
            )
            for record in self.dimensions["records"]
        )
        return HistoricalAISDimensionRegistry(
            registry_id=str(self.dimensions["registry_id"]),
            registry_version=str(self.dimensions["registry_version"]),
            scope=str(self.dimensions["scope"]),
            retrieved_at_utc=str(self.dimensions["retrieved_at_utc"]),
            source_note=str(self.dimensions["source_note"]),
            source_note_sha256=str(self.dimensions["source_note_sha256"]),
            records=records,
        )


class HistoricalAISScenarioCatalog:
    """Read the repository-owned bounded Historical AIS descriptor."""

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or Path(__file__).with_name("data") / "historical_ais_scenarios.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        self._descriptors = {
            str(document["scenario_id"]): HistoricalAISScenarioDescriptor(
                schema_version=str(document["schema_version"]),
                scenario_id=str(document["scenario_id"]),
                display_name=str(document["display_name"]),
                kind=str(document["kind"]),
                modes=tuple(str(value) for value in document["modes"]),
                archive_scope=dict(document["archive_scope"]),
                current_window=dict(document["current_window"]),
                enc=dict(document["enc"]),
                dimensions=dict(document["dimensions"]),
                runtime_binding=dict(document["runtime_binding"]),
                source_binding=dict(document["source_binding"]),
                limitations=tuple(str(value) for value in document["limitations"]),
                descriptor_sha256=str(document.get("descriptor_sha256", "")),
            )
        }

    def list(self, environ: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
        return [
            {
                **descriptor.to_dict(),
                "id": descriptor.scenario_id,
                "readiness": descriptor.readiness(environ).to_dict(),
            }
            for descriptor in self._descriptors.values()
        ]

    def get(self, scenario_id: str) -> HistoricalAISScenarioDescriptor:
        try:
            return self._descriptors[str(scenario_id)]
        except KeyError as exc:
            raise KeyError(scenario_id) from exc

    def document(self, scenario_id: str, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
        descriptor = self.get(scenario_id)
        return {**descriptor.to_dict(), "readiness": descriptor.readiness(environ).to_dict()}


def _historical_reference(dataset: Any, enc_profile: Any, reference_mmsi: int) -> HistoricalBenchmarkTrajectory:
    timestamps: list[float] = []
    positions: list[tuple[float, float]] = []
    courses: list[float] = []
    speeds: list[float] = []
    observations = [
        observation
        for observation in dataset.observations
        if observation.normalized.mmsi == reference_mmsi and observation.normalized.timestamp_utc is not None
    ]
    if not observations:
        raise ValueError(f"reference MMSI {reference_mmsi} has no selected AIS observations")
    origin = min(
        observation.normalized.timestamp_utc
        for observation in dataset.observations
        if observation.normalized.timestamp_utc
    )
    for observation in sorted(observations, key=lambda item: item.normalized.timestamp_utc):
        normalized = observation.normalized
        if normalized.longitude_deg is None or normalized.latitude_deg is None:
            continue
        timestamps.append((normalized.timestamp_utc - origin).total_seconds())
        positions.append(enc_profile.projection.project_wgs84((normalized.longitude_deg, normalized.latitude_deg)))
        courses.append(float(normalized.cog_rad or 0.0))
        speeds.append(float(normalized.sog_mps or 0.0))
    return HistoricalBenchmarkTrajectory(
        tuple(timestamps),
        tuple(positions),
        tuple(courses),
        tuple(speeds),
        source="HAIS_HUMAN_REFERENCE_POST_T0_COMPARE_ONLY",
    )


def _enc_document(profile: Any) -> dict[str, Any]:
    return {
        **profile.to_dict(),
        "coverage_geometry_wkb_hex": profile.coverage_geometry_wkb.hex(),
        "hazard_geometry_wkb_hex": profile.hazard_geometry_wkb.hex(),
        "navigability_geometry_wkb_hex": profile.navigability_geometry_wkb.hex(),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readiness_reason(readiness: HistoricalAISScenarioSourceReadiness, raw_path: str) -> str:
    if readiness.status is HistoricalAISScenarioReadiness.SOURCE_BINDING_MISSING:
        return f"{HAIS_ARCHIVE_ENV_VAR} is not configured"
    if readiness.status is HistoricalAISScenarioReadiness.SOURCE_BINDING_NOT_FOUND:
        return f"{HAIS_ARCHIVE_ENV_VAR} does not point to a readable archive"
    if readiness.status is HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_UNREADABLE:
        return f"Historical AIS archive bound by {HAIS_ARCHIVE_ENV_VAR} is unreadable"
    if readiness.status is HistoricalAISScenarioReadiness.SOURCE_ARCHIVE_DIGEST_MISMATCH:
        return "Historical AIS archive digest does not match the published scene descriptor"
    return f"Historical AIS source binding is ready: {raw_path}"
