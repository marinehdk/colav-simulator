"""Immutable descriptor/catalog for independent Historical AIS scenes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from colav_simulator.historical_acceptance import HistoricalAISDimensionRecord, HistoricalAISDimensionRegistry
from colav_simulator.historical_ais import HistoricalAISSelection
from colav_simulator.historical_scenario_source import (
    HAIS_ARCHIVE_ENV_VAR,
    HistoricalAISScenarioError,
    HistoricalAISScenarioReadiness,
    HistoricalAISScenarioSourceReadiness,
    HistoricalAISSceneSourceBinder,
)
from colav_simulator.historical_serialization import semantic_hash

if TYPE_CHECKING:
    from colav_simulator.historical_scenario_assembly import BoundHistoricalAISSceneContext

HISTORICAL_AIS_SCENARIO_ID = "hais_romsdal_20260701_120000_120100"
HISTORICAL_AIS_SCENARIO_SCHEMA_VERSION = "historical-ais-scenario.v1"


class HistoricalAISScenarioLimitation(str, Enum):
    """Typed catalog limitations."""

    CURRENT_WINDOW_ONLY = "CURRENT_WINDOW_ONLY"
    CURRENT_ACTOR_SET_ONLY = "CURRENT_ACTOR_SET_ONLY"
    ARCHIVE_NOT_FULLY_ENC_QUALIFIED = "ARCHIVE_NOT_FULLY_ENC_QUALIFIED"
    AIS_COVERAGE_NOT_EXHAUSTIVE = "AIS_COVERAGE_NOT_EXHAUSTIVE"
    DIMENSIONS_ONLY_CURRENT_ACTOR_SET = "DIMENSIONS_ONLY_CURRENT_ACTOR_SET"
    ARCHIVE_SCOPE_IS_NOT_RUNTIME_SELECTION = "ARCHIVE_SCOPE_IS_NOT_RUNTIME_SELECTION"


@dataclass(frozen=True)
class HistoricalAISScenarioDescriptor:
    """Deeply immutable, content-addressed bounded scene descriptor."""

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
    algorithm_capability_evidence: Mapping[str, Any]
    source_binding: Mapping[str, Any]
    limitations: tuple[str, ...]
    descriptor_sha256: str = ""

    def __post_init__(self) -> None:
        """Validate authority boundaries, freeze facts and compute identity."""
        if self.schema_version != HISTORICAL_AIS_SCENARIO_SCHEMA_VERSION:
            raise ValueError("unsupported Historical AIS scenario descriptor schema")
        if self.scenario_id != HISTORICAL_AIS_SCENARIO_ID or self.kind != "HISTORICAL_AIS":
            raise ValueError("unsupported Historical AIS scenario identity")
        if self.runtime_binding.get("historical_scenario_id") != self.scenario_id:
            raise ValueError("runtime binding must retain the Historical AIS scenario identity")
        if tuple(self.modes) != ("HISTORICAL_REPLAY", "COUNTERFACTUAL"):
            raise ValueError("Historical AIS scene must publish Replay and Counterfactual")
        capability = self.algorithm_capability_evidence
        if capability.get("binding_role") != "ALGORITHM_CAPABILITY_ONLY":
            raise ValueError("paper tuple may be used only as Algorithm Capability evidence")
        if capability.get("geometry_equivalence") is not False or len(tuple(capability.get("exact_tuple", ()))) != 4:
            raise ValueError("Algorithm Capability evidence identity is invalid")
        if str(self.source_binding.get("env_var")) != HAIS_ARCHIVE_ENV_VAR:
            raise ValueError("Historical AIS source binding environment variable is invalid")
        expected = str(self.source_binding.get("expected_archive_sha256", ""))
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise ValueError("Historical AIS archive digest must be a lowercase SHA-256")
        object.__setattr__(self, "modes", tuple(self.modes))
        for name in (
            "archive_scope",
            "current_window",
            "enc",
            "dimensions",
            "runtime_binding",
            "algorithm_capability_evidence",
            "source_binding",
        ):
            object.__setattr__(self, name, _deep_freeze(getattr(self, name)))
        limitations = tuple(HistoricalAISScenarioLimitation(value).value for value in self.limitations)
        object.__setattr__(self, "limitations", limitations)
        digest = semantic_hash(self._identity_dict())
        if self.descriptor_sha256 and self.descriptor_sha256 != digest:
            raise ValueError("Historical AIS scenario descriptor digest mismatch")
        object.__setattr__(self, "descriptor_sha256", digest)

    def _identity_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "display_name": self.display_name,
            "kind": self.kind,
            "modes": list(self.modes),
            "archive_scope": _deep_thaw(self.archive_scope),
            "current_window": _deep_thaw(self.current_window),
            "enc": _deep_thaw(self.enc),
            "dimensions": _deep_thaw(self.dimensions),
            "runtime_binding": _deep_thaw(self.runtime_binding),
            "algorithm_capability_evidence": _deep_thaw(self.algorithm_capability_evidence),
            "source_binding": _deep_thaw(self.source_binding),
            "limitations": list(self.limitations),
        }

    @property
    def archive_sha256(self) -> str:
        return str(self.source_binding["expected_archive_sha256"])

    def to_dict(self) -> dict[str, Any]:
        return {**self._identity_dict(), "descriptor_sha256": self.descriptor_sha256}

    def selection(self) -> HistoricalAISSelection:
        window = self.current_window
        return HistoricalAISSelection(
            start_utc=str(window["start_utc"]),
            end_utc=str(window["end_utc"]),
            mmsi=tuple(int(value) for value in window["selection_mmsi"]),
            bbox=tuple(float(value) for value in window["bbox"]),
            entries=(str(window["entry_name"]),),
        )

    def readiness(self, environ: Mapping[str, str] | None = None) -> HistoricalAISScenarioSourceReadiness:
        return HistoricalAISSceneSourceBinder.readiness(self, environ)

    def require_source(self, environ: Mapping[str, str] | None = None) -> Path:
        return HistoricalAISSceneSourceBinder.require_source(self, environ)

    def operability(self, readiness: HistoricalAISScenarioSourceReadiness) -> dict[str, str]:
        runtime_mmsi = {int(value) for value in self.current_window["runtime_mmsi"]}
        dimension_mmsi = {int(record["mmsi"]) for record in self.dimensions["records"]}
        available = (
            readiness.status is HistoricalAISScenarioReadiness.READY
            and self.enc["qualification_state"] == "QUALIFIED"
            and runtime_mmsi <= dimension_mmsi
        )
        return {"status": "AVAILABLE" if available else "UNAVAILABLE", "scope": "BOUNDED"}

    def presentation(self, readiness: HistoricalAISScenarioSourceReadiness) -> dict[str, Any]:
        return {
            "schema_version": "historical-ais-scenario.presentation.v1",
            "scenario": {"id": self.scenario_id, "kind": self.kind},
            "operability": self.operability(readiness),
            "qualification": {
                "status": "NOT_QUALIFIED",
                "code": "THREAT_EVIDENCE_INCOMPLETE",
                "source_readiness": readiness.status.value,
                "future_gate": "NONEMPTY_NATURAL_CLUSTER",
                "limitations": list(self.limitations),
            },
            "runtime": {
                "modes": list(self.modes),
                "historical_scenario_id": self.scenario_id,
                "algorithm_id": self.runtime_binding["algorithm_id"],
                "tracker_id": self.runtime_binding["tracker_id"],
                "algorithm_capability_evidence": _deep_thaw(self.algorithm_capability_evidence),
            },
            "replay_evidence": {
                "entry_name": self.current_window["entry_name"],
                "source_row_count": self.current_window["source_row_count"],
                "normalized_row_count": self.current_window["normalized_row_count"],
                "runtime_actor_count": self.current_window["runtime_actor_count"],
                "reference_mmsi": self.current_window["reference_mmsi"],
                "target_mmsi": list(self.current_window["target_mmsi"]),
                "enc_profile_id": self.enc["profile_id"],
            },
            "digests": {
                "descriptor_sha256": self.descriptor_sha256,
                "archive_sha256": self.archive_sha256,
                "entry_sha256": self.current_window["entry_sha256"],
                "schema_sha256": self.current_window["expected_schema_sha256"],
                "selection_sha256": self.current_window["expected_selection_sha256"],
                "normalized_sha256": self.current_window["expected_normalized_sha256"],
                "enc_profile_sha256": self.enc["profile_digest"],
                "dimension_registry_sha256": self.dimension_registry().digest,
            },
        }

    def dimension_registry(self) -> HistoricalAISDimensionRegistry:
        records = tuple(
            HistoricalAISDimensionRecord(**{**dict(record), "source_urls": tuple(record.get("source_urls", ()))})
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

    def bind_context(
        self,
        *,
        run_spec_overrides: Mapping[str, Any] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> BoundHistoricalAISSceneContext:
        from colav_simulator.historical_scenario_assembly import HistoricalAISSceneAssembler  # noqa: PLC0415

        return HistoricalAISSceneAssembler().bind(self, run_spec_overrides=run_spec_overrides, environ=environ)


class HistoricalAISScenarioCatalog:
    """Repository-owned bounded Historical AIS descriptor catalog."""

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or Path(__file__).with_name("data") / "historical_ais_scenarios.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        descriptor = HistoricalAISScenarioDescriptor(
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
            algorithm_capability_evidence=dict(document["algorithm_capability_evidence"]),
            source_binding=dict(document["source_binding"]),
            limitations=tuple(str(value) for value in document["limitations"]),
            descriptor_sha256=str(document.get("descriptor_sha256", "")),
        )
        self._descriptors = {descriptor.scenario_id: descriptor}

    def get(self, scenario_id: str) -> HistoricalAISScenarioDescriptor:
        try:
            return self._descriptors[str(scenario_id)]
        except KeyError as exc:
            raise KeyError(scenario_id) from exc

    def list(self, environ: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
        return [self.document(descriptor.scenario_id, environ) for descriptor in self._descriptors.values()]

    def document(self, scenario_id: str, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
        descriptor = self.get(scenario_id)
        readiness = descriptor.readiness(environ)
        return {
            **descriptor.to_dict(),
            "id": descriptor.scenario_id,
            "readiness": readiness.to_dict(),
            "operability": descriptor.operability(readiness),
            "presentation": descriptor.presentation(readiness),
        }


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return value


__all__ = [
    "HAIS_ARCHIVE_ENV_VAR",
    "HISTORICAL_AIS_SCENARIO_ID",
    "HistoricalAISScenarioCatalog",
    "HistoricalAISScenarioDescriptor",
    "HistoricalAISScenarioError",
    "HistoricalAISScenarioReadiness",
    "HistoricalAISScenarioSourceReadiness",
]
