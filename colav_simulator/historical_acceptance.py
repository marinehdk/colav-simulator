"""Reproducible bounded real-HAIS acceptance harness.

The harness deliberately stops at a typed blocker when a formal Case cannot
be qualified.  It never invents vessel dimensions, substitutes an algorithm,
or reports a blocked run as PASS.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_case import (
    HistoricalAISAlgorithmBinding,
    HistoricalAISCapabilityReceipt,
    HistoricalAISCaseBuilder,
    HistoricalAISCaseBuildOutcome,
    HistoricalAISCaseBuildRequest,
    HistoricalAISCaseBuildStatus,
    HistoricalAISCompareBinding,
    HistoricalAISDiscoveryProfile,
    HistoricalAISEvaluationBinding,
    HistoricalAISHumanReferenceBinding,
)
from colav_simulator.historical_enc import ENCRegionProfile
from colav_simulator.historical_serialization import jsonable as _jsonable
from colav_simulator.historical_serialization import semantic_hash as _sha256_json

if TYPE_CHECKING:
    from colav_simulator.experiment.contracts import RunSpec
    from colav_simulator.historical_compare import HistoricalBenchmarkTrajectory

ACCEPTANCE_SCHEMA_VERSION = "historical-ais-real-acceptance.v1"


class HistoricalAcceptanceStatus(str, Enum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    FAIL = "FAIL"


class HistoricalAcceptanceBlockerCode(str, Enum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_DIGEST_MISMATCH = "SOURCE_DIGEST_MISMATCH"
    WINDOW_SELECTION_INVALID = "WINDOW_SELECTION_INVALID"
    NO_ENCOUNTER = "NO_ENCOUNTER"
    DIMENSIONS_UNAVAILABLE = "DIMENSIONS_UNAVAILABLE"
    DIMENSION_PROVENANCE_INVALID = "DIMENSION_PROVENANCE_INVALID"
    BINDINGS_UNAVAILABLE = "BINDINGS_UNAVAILABLE"
    ENC_UNQUALIFIED = "ENC_UNQUALIFIED"
    INTENT_NOT_ESTABLISHED = "INTENT_NOT_ESTABLISHED"
    TIME_COVERAGE_INSUFFICIENT = "TIME_COVERAGE_INSUFFICIENT"
    INITIAL_SEPARATION_INVALID = "INITIAL_SEPARATION_INVALID"
    SOURCE_QUALITY_UNAVAILABLE = "SOURCE_QUALITY_UNAVAILABLE"
    RUN_FAILED = "RUN_FAILED"
    SOLVER_NO_FALLBACK_FAILED = "SOLVER_NO_FALLBACK_FAILED"
    THREAT_SNAPSHOT_UNAVAILABLE = "THREAT_SNAPSHOT_UNAVAILABLE"
    THREAT_EVIDENCE_INCOMPLETE = "THREAT_EVIDENCE_INCOMPLETE"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    COMPARE_INCOMPLETE = "COMPARE_INCOMPLETE"
    HUMAN_REFERENCE_UNAVAILABLE = "HUMAN_REFERENCE_UNAVAILABLE"
    DETERMINISM_MISMATCH = "DETERMINISM_MISMATCH"


@dataclass(frozen=True)
class HistoricalAISDimensionOverride:
    """Explicit, source-provenanced dimensions; never a silent default."""

    mmsi: int
    length_m: float
    width_m: float
    provenance: str
    source_digest: str
    method: str = "EXPLICIT_TYPED_OVERRIDE"

    def __post_init__(self) -> None:
        """Validate explicit dimensions and their provenance identity."""
        if self.mmsi < 0 or not self.provenance.strip() or not self.source_digest.strip():
            raise ValueError("dimension override requires MMSI and source provenance")
        for name in ("length_m", "width_m"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mmsi": self.mmsi,
            "length_m": self.length_m,
            "width_m": self.width_m,
            "provenance": self.provenance,
            "source_digest": self.source_digest,
            "method": self.method,
        }


@dataclass(frozen=True)
class HistoricalAISDimensionRecord(HistoricalAISDimensionOverride):
    """One benchmark-scoped official measurement record."""

    imo: int = 0
    call_sign: str = ""
    vessel_name: str = ""
    measurement_date: str = ""
    effective_date: str = ""
    journal_date: str = ""
    retrieved_at_utc: str = ""
    effective_as_of_t0: bool = False
    identity_source: str = "Kystdatahuset NSR"
    measurement_source: str = "Sjøfartsdirektoratet measurement certificate"
    source_urls: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "imo": self.imo,
                "call_sign": self.call_sign,
                "vessel_name": self.vessel_name,
                "measurement_date": self.measurement_date,
                "effective_date": self.effective_date,
                "journal_date": self.journal_date,
                "retrieved_at_utc": self.retrieved_at_utc,
                "effective_as_of_t0": self.effective_as_of_t0,
                "identity_source": self.identity_source,
                "measurement_source": self.measurement_source,
                "source_urls": list(self.source_urls),
            }
        )
        return result


@dataclass(frozen=True)
class HistoricalAISDimensionRegistry:
    """Versioned dimensions manifest scoped to one benchmark window."""

    registry_id: str
    registry_version: str
    scope: str
    retrieved_at_utc: str
    source_note: str
    source_note_sha256: str
    records: tuple[HistoricalAISDimensionRecord, ...]

    def __post_init__(self) -> None:
        """Validate scoped registry identity and deterministic record ordering."""
        if not self.registry_id.strip() or not self.registry_version.strip() or not self.scope.strip():
            raise ValueError("dimension registry identity and scope are required")
        object.__setattr__(self, "records", tuple(sorted(self.records, key=lambda item: item.mmsi)))

    def record_for(self, mmsi: int) -> HistoricalAISDimensionRecord | None:
        return next((item for item in self.records if item.mmsi == int(mmsi)), None)

    def validation_errors(self, t0_utc: str | None, selected_mmsi: tuple[int, ...]) -> tuple[str, ...]:
        """Return fail-closed provenance errors for this benchmark T0."""
        if t0_utc is None:
            return ("dimension registry requires a frozen T0",)
        try:
            parsed_t0 = datetime.fromisoformat(t0_utc.replace("Z", "+00:00"))
            if parsed_t0.tzinfo is None:
                raise ValueError
        except ValueError:
            return ("dimension registry T0 must be timezone-aware ISO-8601",)
        errors: list[str] = []
        for mmsi in selected_mmsi:
            record = self.record_for(mmsi)
            if record is None:
                errors.append(f"MMSI {mmsi} has no dimension registry record")
                continue
            if not record.effective_as_of_t0:
                errors.append(f"MMSI {mmsi} is not proven effective as of T0")
            for field_name in ("measurement_date", "effective_date", "journal_date"):
                raw = getattr(record, field_name)
                try:
                    record_date = date.fromisoformat(raw)
                except (TypeError, ValueError):
                    errors.append(f"MMSI {mmsi} has invalid {field_name}")
                    continue
                if record_date > parsed_t0.date():
                    errors.append(f"MMSI {mmsi} {field_name} is after T0")
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "scope": self.scope,
            "retrieved_at_utc": self.retrieved_at_utc,
            "source_note": self.source_note,
            "source_note_sha256": self.source_note_sha256,
            "records": [item.to_dict() for item in self.records],
        }

    @property
    def digest(self) -> str:
        return _sha256_json(self.to_dict())


def decode_dimension_registry(
    document: Mapping[str, Any],
    *,
    require_digest: bool = False,
) -> HistoricalAISDimensionRegistry:
    """Decode and optionally authenticate one shared dimension-registry document."""
    payload = dict(document)
    expected_digest = str(payload.pop("registry_digest", ""))
    records_document = payload.pop("records", None)
    if not isinstance(records_document, (list, tuple)) or not records_document:
        raise ValueError("dimension registry records are required")
    records = tuple(
        HistoricalAISDimensionRecord(
            **{
                **dict(record),
                "source_urls": tuple(record.get("source_urls", ())),
            }
        )
        for record in records_document
    )
    registry = HistoricalAISDimensionRegistry(**payload, records=records)
    if require_digest and not expected_digest:
        raise ValueError("dimension registry digest is required")
    if expected_digest and expected_digest != registry.digest:
        raise ValueError("dimension registry digest mismatch")
    return registry


@dataclass(frozen=True)
class HistoricalRealWindowSelection:
    """Compact external-data selection manifest; no source rows are embedded."""

    source_name: str
    archive_sha256: str
    entry_name: str
    selection: HistoricalAISSelection
    reference_mmsi: int
    selected_mmsi: tuple[int, ...]
    enc_profile_id: str
    dimension_registry_id: str | None = None
    notes: str = ""
    t0_utc: str | None = None

    def __post_init__(self) -> None:
        """Normalize selected MMSIs and require the Reference Vessel."""
        object.__setattr__(self, "selected_mmsi", tuple(sorted({int(value) for value in self.selected_mmsi})))
        if self.reference_mmsi not in self.selected_mmsi:
            raise ValueError("reference_mmsi must be in selected_mmsi")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ACCEPTANCE_SCHEMA_VERSION,
            "source_name": self.source_name,
            "archive_sha256": self.archive_sha256,
            "entry_name": self.entry_name,
            "selection": self.selection.to_dict(),
            "reference_mmsi": self.reference_mmsi,
            "selected_mmsi": list(self.selected_mmsi),
            "enc_profile_id": self.enc_profile_id,
            "dimension_registry_id": self.dimension_registry_id,
            "notes": self.notes,
            "t0_utc": self.t0_utc,
        }


@dataclass(frozen=True)
class HistoricalAISAcceptanceRequest:
    source: Path
    window: HistoricalRealWindowSelection
    enc_profile: ENCRegionProfile
    discovery_profile: HistoricalAISDiscoveryProfile = field(default_factory=HistoricalAISDiscoveryProfile)
    dimension_overrides: tuple[HistoricalAISDimensionOverride, ...] = ()
    dimension_registry: HistoricalAISDimensionRegistry | None = None
    run_spec: RunSpec | None = None
    human_reference: HistoricalBenchmarkTrajectory | None = None
    human_reference_artifact_digest: str | None = None

    def __post_init__(self) -> None:
        """Freeze source and typed dimension override inputs."""
        object.__setattr__(self, "source", Path(self.source))
        object.__setattr__(self, "dimension_overrides", tuple(self.dimension_overrides))
        if self.human_reference is not None:
            trajectory_digest = self.human_reference.trajectory_digest
            if self.human_reference_artifact_digest not in {None, trajectory_digest}:
                raise ValueError("Human Reference artifact digest does not match the sealed trajectory")
            object.__setattr__(self, "human_reference_artifact_digest", trajectory_digest)


@dataclass(frozen=True)
class HistoricalAISPublishedCaseAcceptanceRequest:
    """Qualification request that reuses one already Published Case identity."""

    case: Any
    run_spec: RunSpec
    human_reference: HistoricalBenchmarkTrajectory
    human_reference_artifact_digest: str

    def __post_init__(self) -> None:
        """Require one coherent Published Case and Human Reference binding."""
        if not self.case.published:
            raise ValueError("acceptance requires a Published HistoricalAISCase")
        if self.case.historical_scenario_id != self.run_spec.historical_scenario_id:
            raise ValueError("Published Case and RunSpec Historical scenario identities differ")
        if self.human_reference.trajectory_digest != self.human_reference_artifact_digest:
            raise ValueError("Human Reference digest differs from Published Case acceptance request")
        if self.case.human_reference_binding.artifact_digest != self.human_reference_artifact_digest:
            raise ValueError("Published Case Human Reference binding differs from acceptance request")


@dataclass(frozen=True)
class HistoricalAISAcceptanceOutcome:
    status: HistoricalAcceptanceStatus
    blocker_codes: tuple[str, ...]
    blocker_messages: tuple[str, ...]
    manifest: Mapping[str, Any]
    dataset_descriptor: Mapping[str, Any] | None = None
    case_outcome: HistoricalAISCaseBuildOutcome | None = None

    def __post_init__(self) -> None:
        """Freeze typed blockers and compact manifest evidence."""
        object.__setattr__(self, "status", HistoricalAcceptanceStatus(self.status))
        object.__setattr__(self, "blocker_codes", tuple(self.blocker_codes))
        object.__setattr__(self, "blocker_messages", tuple(self.blocker_messages))
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))

    @property
    def success(self) -> bool:
        return self.status is HistoricalAcceptanceStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "success": self.success,
            "blocker_codes": list(self.blocker_codes),
            "blocker_messages": list(self.blocker_messages),
            "manifest": _jsonable(dict(self.manifest)),
            "dataset_descriptor": _jsonable(self.dataset_descriptor),
            "case_outcome": self.case_outcome.to_dict() if self.case_outcome else None,
        }


class HistoricalAISAcceptanceHarness:
    """Run bounded Dataset → Case preflight and stop at truthful blockers."""

    def run(self, request: HistoricalAISAcceptanceRequest) -> HistoricalAISAcceptanceOutcome:  # noqa: PLR0911
        if not isinstance(request, HistoricalAISAcceptanceRequest):
            return self._blocked(HistoricalAcceptanceBlockerCode.WINDOW_SELECTION_INVALID, "request type is invalid", {})
        source = request.source
        historical_scenario_id = request.run_spec.historical_scenario_id if request.run_spec is not None else None
        base_manifest = {
            "schema_version": ACCEPTANCE_SCHEMA_VERSION,
            "historical_scenario_id": historical_scenario_id,
            "source": request.window.to_dict(),
            "enc_profile": {
                "profile_id": request.enc_profile.profile_id,
                "profile_digest": request.enc_profile.profile_digest,
                "qualification_state": request.enc_profile.qualification_state.value,
            },
            "dimensions": {
                "default_dimensions_used": False,
                "explicit_overrides": [
                    *([item.to_dict() for item in request.dimension_overrides]),
                    *([item.to_dict() for item in request.dimension_registry.records] if request.dimension_registry else []),
                ],
                "registry": request.dimension_registry.to_dict() if request.dimension_registry else None,
                "registry_digest": request.dimension_registry.digest if request.dimension_registry else None,
            },
            "lineage": {
                "historical_scenario_id": historical_scenario_id,
                "dataset_digest": None,
                "case_digest": None,
                "run_digest": None,
                "evaluation_digest": None,
                "compare_digest": None,
            },
        }
        if not source.is_file():
            return self._blocked(HistoricalAcceptanceBlockerCode.SOURCE_UNAVAILABLE, str(source), base_manifest)
        actual_digest = _sha256_file(source)
        if actual_digest != request.window.archive_sha256:
            return self._blocked(
                HistoricalAcceptanceBlockerCode.SOURCE_DIGEST_MISMATCH,
                f"expected {request.window.archive_sha256}, got {actual_digest}",
                base_manifest,
            )
        try:
            dataset = HistoricalAISDatasetReader(source).read(request.window.selection)
        except (OSError, ValueError, TypeError) as exc:
            return self._blocked(HistoricalAcceptanceBlockerCode.WINDOW_SELECTION_INVALID, str(exc), base_manifest)
        descriptor = dataset.descriptor.to_dict()
        base_manifest["lineage"]["dataset_digest"] = dataset.descriptor.descriptor_sha256
        base_manifest["dataset"] = {
            "descriptor_sha256": dataset.descriptor.descriptor_sha256,
            "archive_sha256": dataset.descriptor.archive_sha256,
            "selection_sha256": dataset.descriptor.selection_sha256,
            "schema_sha256": dataset.descriptor.schema_sha256,
            "normalized_sha256": dataset.descriptor.normalized_sha256,
            "entries": list(dataset.descriptor.entries),
            "format": dataset.descriptor.format,
            "source_row_count": dataset.descriptor.source_row_count,
            "normalized_row_count": dataset.descriptor.normalized_row_count,
            "quality_finding_count": len(dataset.descriptor.quality_findings),
            "attribution": dataset.descriptor.attribution.to_dict(),
        }
        enc_preflight = request.enc_profile.preflight_historical_ais(dataset)
        base_manifest["enc_preflight"] = enc_preflight.to_dict()
        if not enc_preflight.qualified:
            return self._blocked(
                HistoricalAcceptanceBlockerCode.ENC_UNQUALIFIED,
                f"ENC preflight status is {enc_preflight.status.value}",
                base_manifest,
                descriptor,
            )
        if request.enc_profile.profile_id != request.window.enc_profile_id:
            return self._blocked(
                HistoricalAcceptanceBlockerCode.ENC_UNQUALIFIED,
                "selection manifest ENC profile does not match supplied profile",
                base_manifest,
                descriptor,
            )
        if request.dimension_registry is not None and request.window.dimension_registry_id not in {
            None,
            request.dimension_registry.registry_id,
        }:
            return self._blocked(
                HistoricalAcceptanceBlockerCode.WINDOW_SELECTION_INVALID,
                "selection manifest dimension registry does not match supplied registry",
                base_manifest,
                descriptor,
            )
        if request.dimension_registry is not None:
            provenance_errors = request.dimension_registry.validation_errors(
                request.window.t0_utc,
                request.window.selected_mmsi,
            )
            if provenance_errors:
                return self._blocked(
                    HistoricalAcceptanceBlockerCode.DIMENSION_PROVENANCE_INVALID,
                    "; ".join(provenance_errors),
                    base_manifest,
                    descriptor,
                )
        registry_overrides = (
            tuple(item.to_dict() for item in request.dimension_registry.records)
            if request.dimension_registry is not None
            else ()
        )
        case_outcome = HistoricalAISCaseBuilder().build(
            HistoricalAISCaseBuildRequest(
                dataset=dataset,
                selection=request.window.selection,
                enc_profile=request.enc_profile,
                discovery_profile=request.discovery_profile,
                reference_mmsi=request.window.reference_mmsi,
                historical_scenario_id=historical_scenario_id,
                t0_utc=request.window.t0_utc,
                require_intent=request.dimension_registry is not None,
                published=True if request.dimension_registry is not None else None,
                dimension_overrides={item["mmsi"]: item for item in registry_overrides},
                human_reference_binding=_human_reference_binding(request),
                algorithm_binding=_algorithm_binding(request),
                evaluation_binding=_evaluation_binding(request),
                compare_binding=_compare_binding(request),
            )
        )
        if not case_outcome.success:
            code = _map_case_blocker(case_outcome.failure_code)
            base_manifest["case"] = {"status": case_outcome.status.value, "details": dict(case_outcome.details)}
            return self._blocked(code, case_outcome.reason, base_manifest, descriptor, case_outcome)
        base_manifest["lineage"]["case_digest"] = case_outcome.case.case_digest  # type: ignore[union-attr]
        built_case = case_outcome.case
        base_manifest["case"] = {
            "status": "SUCCESS",
            "historical_scenario_id": built_case.historical_scenario_id,  # type: ignore[union-attr]
            "case_digest": built_case.case_digest,  # type: ignore[union-attr]
            "runtime_actor_set_digest": built_case.runtime_actor_set_digest,  # type: ignore[union-attr]
            "human_reference_binding": built_case.human_reference_binding.to_dict(),  # type: ignore[union-attr]
            "algorithm_binding": built_case.algorithm_binding.to_dict(),  # type: ignore[union-attr]
            "evaluation_binding": built_case.evaluation_binding.to_dict(),  # type: ignore[union-attr]
            "compare_binding": built_case.compare_binding.to_dict(),  # type: ignore[union-attr]
        }
        if request.run_spec is not None:
            return self._execute_run_and_compare(request, case_outcome, base_manifest, descriptor)
        return HistoricalAISAcceptanceOutcome(
            status=HistoricalAcceptanceStatus.PASS,
            blocker_codes=(),
            blocker_messages=(),
            manifest=base_manifest,
            dataset_descriptor=descriptor,
            case_outcome=case_outcome,
        )

    def run_published_case(
        self,
        request: HistoricalAISPublishedCaseAcceptanceRequest,
    ) -> HistoricalAISAcceptanceOutcome:
        """Run two qualifications over the exact same Published Case object."""
        case = request.case
        descriptor = case.dataset_descriptor.to_dict()
        case_outcome = HistoricalAISCaseBuildOutcome(HistoricalAISCaseBuildStatus.SUCCESS, case=case)
        manifest = {
            "schema_version": ACCEPTANCE_SCHEMA_VERSION,
            "historical_scenario_id": case.historical_scenario_id,
            "source": {
                "archive_sha256": case.dataset_descriptor.archive_sha256,
                "selection": case.selection.to_dict(),
            },
            "dataset": {
                "descriptor_sha256": case.dataset_descriptor.descriptor_sha256,
                "archive_sha256": case.dataset_descriptor.archive_sha256,
                "selection_sha256": case.dataset_descriptor.selection_sha256,
                "schema_sha256": case.dataset_descriptor.schema_sha256,
                "normalized_sha256": case.dataset_descriptor.normalized_sha256,
            },
            "enc_profile": {
                "profile_id": case.enc_profile.profile_id,
                "profile_digest": case.enc_profile.profile_digest,
                "qualification_state": case.enc_profile.qualification_state.value,
            },
            "enc_preflight": case.enc_preflight.to_dict(),
            "dimensions": {
                "default_dimensions_used": False,
                "explicit_overrides": [dict(item) for item in case.dimension_overrides],
            },
            "case": {
                "status": "SUCCESS",
                "historical_scenario_id": case.historical_scenario_id,
                "case_digest": case.case_digest,
                "runtime_actor_set_digest": case.runtime_actor_set_digest,
                "human_reference_binding": case.human_reference_binding.to_dict(),
                "algorithm_binding": case.algorithm_binding.to_dict(),
                "evaluation_binding": case.evaluation_binding.to_dict(),
                "compare_binding": case.compare_binding.to_dict(),
            },
            "lineage": {
                "historical_scenario_id": case.historical_scenario_id,
                "dataset_digest": case.dataset_descriptor.descriptor_sha256,
                "case_digest": case.case_digest,
                "run_digest": None,
                "evaluation_digest": None,
                "compare_digest": None,
            },
        }
        return self._execute_run_and_compare(request, case_outcome, manifest, descriptor)

    def _execute_run_and_compare(  # noqa: PLR0911
        self,
        request: HistoricalAISAcceptanceRequest | HistoricalAISPublishedCaseAcceptanceRequest,
        case_outcome: HistoricalAISCaseBuildOutcome,
        manifest: dict[str, Any],
        descriptor: dict[str, Any],
    ) -> HistoricalAISAcceptanceOutcome:
        from colav_simulator.historical_compare import (  # noqa: PLC0415
            HistoricalBenchmarkComparator,
            HistoricalBenchmarkCompareRequest,
        )
        from colav_simulator.historical_counterfactual import (  # noqa: PLC0415
            HistoricalAISCounterfactualRunner,
            HistoricalAISCounterfactualRunRequest,
        )

        case = case_outcome.case
        if case is None:
            return self._blocked(
                HistoricalAcceptanceBlockerCode.WINDOW_SELECTION_INVALID,
                "successful Case outcome did not include a Case",
                manifest,
                descriptor,
                case_outcome,
            )
        if request.human_reference is None:
            return self._blocked(
                HistoricalAcceptanceBlockerCode.HUMAN_REFERENCE_UNAVAILABLE,
                "formal real-window Compare requires a sealed Human Reference trajectory",
                manifest,
                descriptor,
                case_outcome,
            )
        run_request = HistoricalAISCounterfactualRunRequest(
            case=case,
            run_spec=request.run_spec,
            human_reference_artifact_digest=request.human_reference_artifact_digest,
        )
        run_spec_document = run_request.to_run_spec().to_dict()
        manifest["leakage"] = {
            "human_reference_digest_in_run_spec": bool(
                request.human_reference_artifact_digest
                and request.human_reference_artifact_digest in repr(run_spec_document)
            ),
            "reference_runtime_last_time_s": run_request.t0_s,
            "nominal_intent_strict_pre_t0_only": case.nominal_intent.strict_pre_t0_only,
            "status": "PASS_CONTRACT",
        }
        run_outcome = HistoricalAISCounterfactualRunner().run(run_request)
        if not run_outcome.success or run_outcome.result is None:
            return self._fail(
                HistoricalAcceptanceBlockerCode.RUN_FAILED,
                run_outcome.message or run_outcome.status.value,
                manifest,
                descriptor,
                case_outcome,
            )
        result = run_outcome.result
        run_manifest = result.manifest
        manifest["run"] = {
            "run_id": run_manifest.run_id,
            "historical_scenario_id": request.run_spec.historical_scenario_id,
            "mode": run_manifest.historical_execution_mode,
            "requested_algorithm": run_manifest.requested_algorithm,
            "executed_algorithm": run_manifest.executed_algorithm,
            "fallback_used": run_manifest.fallback_used,
            "spec_hash": run_manifest.spec_hash,
            "trajectory_hash": run_manifest.trajectory_hash,
            "algorithm_capability_evidence": request.run_spec.algorithm_capability_evidence,
        }
        manifest["lineage"]["run_digest"] = run_manifest.trajectory_hash
        if (
            run_manifest.fallback_used
            or run_manifest.requested_algorithm != run_manifest.executed_algorithm
            or run_manifest.historical_execution_mode != "COUNTERFACTUAL"
        ):
            return self._fail(
                HistoricalAcceptanceBlockerCode.SOLVER_NO_FALLBACK_FAILED,
                "Counterfactual requested/executed algorithm or fallback evidence is invalid",
                manifest,
                descriptor,
                case_outcome,
            )
        snapshot = result.session.threat_management_coordinator.last_snapshot
        if snapshot is None:
            return self._fail(
                HistoricalAcceptanceBlockerCode.THREAT_SNAPSHOT_UNAVAILABLE,
                "real Counterfactual Run produced no canonical Threat Management snapshot",
                manifest,
                descriptor,
                case_outcome,
            )
        manifest["threat"] = {
            "semantic_hash": snapshot.semantic_hash,
            "vector_count": len(snapshot.vectors),
            "schedule": _schedule_manifest(snapshot.schedule),
            "conflict_graph": snapshot.conflict_graph.to_dict() if snapshot.conflict_graph else None,
        }
        manifest["threat"]["schedule_context_count"] = _schedule_context_count(snapshot.schedule)
        manifest["threat"]["cluster_count"] = len(snapshot.conflict_graph.clusters) if snapshot.conflict_graph else 0
        expected_target_count = len(case.traffic_actor_ids)
        if (
            len(snapshot.vectors) < expected_target_count
            or manifest["threat"]["schedule_context_count"] < expected_target_count
        ):
            return self._fail(
                HistoricalAcceptanceBlockerCode.THREAT_EVIDENCE_INCOMPLETE,
                "real Counterfactual Threat snapshot lacks mandatory vectors or schedule membership",
                manifest,
                descriptor,
                case_outcome,
            )
        if run_manifest.evaluation_gate != "PASS" or run_manifest.evaluation_schema_version is None:
            return self._fail(
                HistoricalAcceptanceBlockerCode.EVALUATION_FAILED,
                "Independent Evaluator gate/status is "
                f"{run_manifest.evaluation_gate}/{run_manifest.evaluation_schema_version}",
                manifest,
                descriptor,
                case_outcome,
            )
        evaluation = result.evaluation
        manifest["evaluation"] = {
            "evaluator_id": evaluation.evaluator_id,
            "evaluator_profile_id": evaluation.evaluator_profile_id,
            "evaluation_status": evaluation.evaluation_status,
            "gate": run_manifest.evaluation_gate,
            "aggregate": evaluation.aggregate,
        }
        manifest["lineage"]["evaluation_digest"] = _sha256_json(manifest["evaluation"])
        compare_request = HistoricalBenchmarkCompareRequest.from_counterfactual_run(
            case,
            result,
            human_reference=request.human_reference,
        )
        compare_outcome = HistoricalBenchmarkComparator().compare(compare_request)
        manifest["compare"] = compare_outcome.to_dict()
        manifest["lineage"]["compare_digest"] = compare_outcome.compare_digest
        if compare_outcome.status.value != "COMPLETE":
            return self._fail(
                HistoricalAcceptanceBlockerCode.COMPARE_INCOMPLETE,
                "real-window Compare domains are incomplete",
                manifest,
                descriptor,
                case_outcome,
            )
        first_determinism = _determinism_evidence(result, compare_outcome)
        second_outcome = HistoricalAISCounterfactualRunner().run(run_request)
        if not second_outcome.success or second_outcome.result is None:
            return self._fail(
                HistoricalAcceptanceBlockerCode.RUN_FAILED,
                second_outcome.message or second_outcome.status.value,
                manifest,
                descriptor,
                case_outcome,
            )
        second_result = second_outcome.result
        second_manifest = second_result.manifest
        second_snapshot = second_result.session.threat_management_coordinator.last_snapshot
        if (
            second_manifest.fallback_used
            or second_manifest.requested_algorithm != second_manifest.executed_algorithm
            or second_manifest.evaluation_gate != "PASS"
            or second_snapshot is None
        ):
            return self._fail(
                HistoricalAcceptanceBlockerCode.DETERMINISM_MISMATCH,
                "second deterministic Counterfactual Run failed execution/evaluation authority",
                manifest,
                descriptor,
                case_outcome,
            )
        second_compare = HistoricalBenchmarkComparator().compare(
            HistoricalBenchmarkCompareRequest.from_counterfactual_run(
                case,
                second_result,
                human_reference=request.human_reference,
            )
        )
        if second_compare.status.value != "COMPLETE":
            return self._fail(
                HistoricalAcceptanceBlockerCode.COMPARE_INCOMPLETE,
                "second deterministic Counterfactual Compare is incomplete",
                manifest,
                descriptor,
                case_outcome,
            )
        second_determinism = _determinism_evidence(second_result, second_compare)
        compared_fields = tuple(sorted(first_determinism))
        mismatches = tuple(
            field_name for field_name in compared_fields if first_determinism[field_name] != second_determinism[field_name]
        )
        manifest["runs"] = [
            _determinism_run_lineage(result, compare_outcome, first_determinism),
            _determinism_run_lineage(second_result, second_compare, second_determinism),
        ]
        manifest["determinism"] = {
            "status": "PASS" if not mismatches else "FAIL",
            "compared_fields": list(compared_fields),
            "mismatches": list(mismatches),
        }
        if mismatches:
            return self._fail(
                HistoricalAcceptanceBlockerCode.DETERMINISM_MISMATCH,
                f"Counterfactual deterministic semantic mismatch: {', '.join(mismatches)}",
                manifest,
                descriptor,
                case_outcome,
            )
        return self._finish_qualification(manifest, descriptor, case_outcome)

    def _finish_qualification(
        self,
        manifest: dict[str, Any],
        descriptor: dict[str, Any],
        case_outcome: HistoricalAISCaseBuildOutcome,
    ) -> HistoricalAISAcceptanceOutcome:
        if manifest["threat"]["cluster_count"] < 1:
            return self._fail(
                HistoricalAcceptanceBlockerCode.THREAT_EVIDENCE_INCOMPLETE,
                "observed conflict cluster count is empty after deterministic Counterfactual qualification",
                manifest,
                descriptor,
                case_outcome,
            )
        return HistoricalAISAcceptanceOutcome(
            status=HistoricalAcceptanceStatus.PASS,
            blocker_codes=(),
            blocker_messages=(),
            manifest=manifest,
            dataset_descriptor=descriptor,
            case_outcome=case_outcome,
        )

    @staticmethod
    def _blocked(
        code: HistoricalAcceptanceBlockerCode,
        message: str,
        manifest: dict[str, Any],
        descriptor: dict[str, Any] | None = None,
        case_outcome: HistoricalAISCaseBuildOutcome | None = None,
    ) -> HistoricalAISAcceptanceOutcome:
        manifest["acceptance"] = {"status": HistoricalAcceptanceStatus.BLOCKED.value, "blocker_code": code.value}
        return HistoricalAISAcceptanceOutcome(
            status=HistoricalAcceptanceStatus.BLOCKED,
            blocker_codes=(code.value,),
            blocker_messages=(message,),
            manifest=manifest,
            dataset_descriptor=descriptor,
            case_outcome=case_outcome,
        )

    @staticmethod
    def _fail(
        code: HistoricalAcceptanceBlockerCode,
        message: str,
        manifest: dict[str, Any],
        descriptor: dict[str, Any] | None = None,
        case_outcome: HistoricalAISCaseBuildOutcome | None = None,
    ) -> HistoricalAISAcceptanceOutcome:
        manifest["acceptance"] = {"status": HistoricalAcceptanceStatus.FAIL.value, "blocker_code": code.value}
        return HistoricalAISAcceptanceOutcome(
            status=HistoricalAcceptanceStatus.FAIL,
            blocker_codes=(code.value,),
            blocker_messages=(message,),
            manifest=manifest,
            dataset_descriptor=descriptor,
            case_outcome=case_outcome,
        )


def build_hais_2026_07_01_dimension_registry(note_path: Path) -> HistoricalAISDimensionRegistry:
    """Create one window-scoped SDIR registry from the reviewed provenance note."""
    note_path = Path(note_path)
    return HistoricalAISDimensionRegistry(
        registry_id="hais-2026-07-01-sdir-dimensions",
        registry_version="1.0.0",
        scope="HAIS 2026-07-01 benchmark selected MMSIs only",
        retrieved_at_utc="2026-08-21T00:00:00Z",
        source_note=str(note_path),
        source_note_sha256=_sha256_file(note_path),
        records=(
            HistoricalAISDimensionRecord(
                mmsi=257252000,
                length_m=84.6,
                width_m=16.0,
                provenance="SDIR measurement certificate; Kystdatahuset NSR identity bridge",
                source_digest="sdir-vessel-93640-9793662",
                imo=9793662,
                call_sign="LDZS",
                vessel_name="FREYJA",
                measurement_date="2017-06-26",
                effective_date="2017-06-26",
                journal_date="2017-09-15",
                retrieved_at_utc="2026-08-21T00:00:00Z",
                effective_as_of_t0=True,
                source_urls=(
                    "https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/93640?language=no",
                    "https://kystdatahuset.no/ws/api/ship/data/nsr/for-mmsis-imos",
                ),
            ),
            HistoricalAISDimensionRecord(
                mmsi=258764000,
                length_m=59.2,
                width_m=10.8,
                provenance="SDIR measurement certificate; Kystdatahuset NSR identity bridge",
                source_digest="sdir-vessel-106419-9331098",
                imo=9331098,
                call_sign="JXPT",
                vessel_name="PELAGIA HORDAFOR",
                measurement_date="2022-09-21",
                effective_date="2022-09-21",
                journal_date="2022-09-27",
                retrieved_at_utc="2026-08-21T00:00:00Z",
                effective_as_of_t0=True,
                source_urls=(
                    "https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/106419?language=no",
                    "https://kystdatahuset.no/ws/api/ship/data/nsr/for-mmsis-imos",
                ),
            ),
            HistoricalAISDimensionRecord(
                mmsi=259189000,
                length_m=32.0,
                width_m=8.8,
                provenance="SDIR measurement certificate; Kystdatahuset NSR identity bridge",
                source_digest="sdir-vessel-94133-9802619",
                imo=9802619,
                call_sign="LEDI",
                vessel_name="VALDERØY",
                measurement_date="2016-12-20",
                effective_date="2016-12-20",
                journal_date="2017-01-11",
                retrieved_at_utc="2026-08-21T00:00:00Z",
                effective_as_of_t0=True,
                source_urls=(
                    "https://sdir-p-apim-common.azure-api.net/los-vesselsearch-internal/v1/vessel-data/94133?language=no",
                    "https://kystdatahuset.no/ws/api/ship/data/nsr/for-mmsis-imos",
                ),
            ),
        ),
    )


def _map_case_blocker(failure_code: str | None) -> HistoricalAcceptanceBlockerCode:
    mapping = {
        "DIMENSIONS_UNAVAILABLE": HistoricalAcceptanceBlockerCode.DIMENSIONS_UNAVAILABLE,
        "ENC_UNQUALIFIED": HistoricalAcceptanceBlockerCode.ENC_UNQUALIFIED,
        "NO_ENCOUNTER": HistoricalAcceptanceBlockerCode.NO_ENCOUNTER,
        "INTENT_NOT_ESTABLISHED": HistoricalAcceptanceBlockerCode.INTENT_NOT_ESTABLISHED,
        "TIME_COVERAGE_INSUFFICIENT": HistoricalAcceptanceBlockerCode.TIME_COVERAGE_INSUFFICIENT,
        "INITIAL_SEPARATION_INVALID": HistoricalAcceptanceBlockerCode.INITIAL_SEPARATION_INVALID,
        "SOURCE_QUALITY_UNAVAILABLE": HistoricalAcceptanceBlockerCode.SOURCE_QUALITY_UNAVAILABLE,
        "BINDINGS_UNAVAILABLE": HistoricalAcceptanceBlockerCode.BINDINGS_UNAVAILABLE,
    }
    return mapping.get(str(failure_code), HistoricalAcceptanceBlockerCode.WINDOW_SELECTION_INVALID)


def _schedule_context_count(schedule: Any | None) -> int:
    if schedule is None:
        return 0
    return int(schedule.current_primary is not None) + sum(
        len(getattr(schedule, name, ()) or ()) for name in ("concurrent_required", "next_threats", "monitor")
    )


def _determinism_evidence(result: Any, compare_outcome: Any) -> dict[str, str]:
    from colav_simulator.historical_compare import HistoricalBenchmarkTrajectory  # noqa: PLC0415

    trajectory = HistoricalBenchmarkTrajectory.from_session_frames(
        result.session.frames,
        source="COUNTERFACTUAL_REALIZED",
    )
    commands = [frame.get("Ship0", {}).get("planner", {}).get("selected_command") for frame in result.session.frames]
    evaluation = result.evaluation.to_dict()
    evaluation.pop("diagnostics", None)
    snapshot = result.session.threat_management_coordinator.last_snapshot
    schedule = _deterministic_schedule_projection(snapshot.schedule) if snapshot is not None else None
    graph = _deterministic_graph_projection(snapshot.conflict_graph) if snapshot is not None else None
    return {
        "trajectory_semantic_hash": trajectory.trajectory_digest,
        "commands_semantic_hash": _sha256_json(commands),
        "threat_schedule_semantic_hash": _sha256_json(schedule),
        "threat_graph_semantic_hash": _sha256_json(graph),
        "evaluator_semantic_hash": _sha256_json(evaluation),
        "compare_domains_semantic_hash": _sha256_json(compare_outcome.domains.to_dict()),
    }


def _determinism_run_lineage(result: Any, compare_outcome: Any, evidence: Mapping[str, str]) -> dict[str, Any]:
    snapshot = result.session.threat_management_coordinator.last_snapshot
    graph = None if snapshot is None else snapshot.conflict_graph
    return {
        "run_id": result.manifest.run_id,
        "spec_hash": result.manifest.spec_hash,
        "trajectory_artifact_hash": result.manifest.trajectory_hash,
        "evaluation_gate": result.manifest.evaluation_gate,
        "compare_status": compare_outcome.status.value,
        "compare_digest": compare_outcome.compare_digest,
        "threat_graph_evidence_hash": None if graph is None else graph.evidence_hash,
        **dict(evidence),
    }


def _deterministic_graph_projection(graph: Any | None) -> dict[str, Any] | None:
    if graph is None:
        return None
    return graph.semantic_dict()


def _deterministic_schedule_projection(schedule: Any | None) -> dict[str, Any] | None:
    if schedule is None:
        return None
    return {
        "schema_version": schedule.schema_version,
        "current_primary": _track_key_document(schedule.current_primary),
        "concurrent_required": [_track_key_document(item) for item in schedule.concurrent_required],
        "next_threats": [_track_key_document(item) for item in schedule.next_threats],
        "monitor": [_track_key_document(item) for item in schedule.monitor],
        "released": [_track_key_document(item) for item in schedule.released],
        "entries": [
            {
                "key": _track_key_document(entry.key),
                "context": entry.context.value,
                "window": _jsonable(entry.window),
                "priority_class": entry.priority_class.value,
                "priority_reason": entry.priority_reason,
                "unavailable_reason": entry.unavailable_reason.value if entry.unavailable_reason is not None else None,
                "handoff_expectation": entry.handoff_expectation,
            }
            for entry in schedule.entries
        ],
        "events": [
            {
                "event_id": event.event_id,
                "sim_time_s": event.sim_time_s,
                "event_type": event.event_type,
                "key": _track_key_document(event.key),
                "reason": event.reason,
                "from_context": event.from_context.value if event.from_context is not None else None,
                "to_context": event.to_context.value if event.to_context is not None else None,
                "predicted": event.predicted,
                "schema_version": event.schema_version,
            }
            for event in schedule.events
        ],
        "horizon_start_s": schedule.horizon_start_s,
        "horizon_end_s": schedule.horizon_end_s,
        "generated_at_s": schedule.generated_at_s,
        "input_hash": schedule.input_hash,
        "profile_hash": schedule.profile_hash,
    }


def _track_key_document(key: Any | None) -> dict[str, int] | None:
    return None if key is None else {"target_id": int(key.target_id), "generation": int(key.generation)}


def _human_reference_binding(request: HistoricalAISAcceptanceRequest) -> HistoricalAISHumanReferenceBinding:
    sample_count = len(request.human_reference.timestamps_s) if request.human_reference is not None else 0
    return HistoricalAISHumanReferenceBinding(
        artifact_digest=request.human_reference_artifact_digest,
        sample_count=sample_count,
    )


def _algorithm_binding(request: HistoricalAISAcceptanceRequest) -> HistoricalAISAlgorithmBinding:
    if request.run_spec is None:
        return HistoricalAISAlgorithmBinding()
    receipt = None
    capability_tuple = request.run_spec.capability_tuple
    if capability_tuple is not None:
        from colav_simulator.core.colav.diagnostics import ColavExecutionError  # noqa: PLC0415
        from colav_simulator.experiment.capabilities import CapabilityCatalog  # noqa: PLC0415
        from colav_simulator.integrations import IntegrationRegistry  # noqa: PLC0415

        try:
            receipt = HistoricalAISCapabilityReceipt.from_catalog(
                CapabilityCatalog(IntegrationRegistry()),
                *capability_tuple,
            )
        except (ColavExecutionError, KeyError, StopIteration, ValueError):
            receipt = None
    return HistoricalAISAlgorithmBinding(
        algorithm_id=request.run_spec.algorithm_id,
        configuration_digest=_sha256_json(request.run_spec.algorithm_config),
        capability_evidence_digest=receipt.evidence_hash if receipt else None,
        capability_receipt=receipt,
    )


def _evaluation_binding(request: HistoricalAISAcceptanceRequest) -> HistoricalAISEvaluationBinding:
    if request.run_spec is None:
        return HistoricalAISEvaluationBinding()
    profile_id = request.run_spec.evaluator_profile_id
    return HistoricalAISEvaluationBinding(
        evaluator_id="behavior-compatible-evaluator-v2",
        profile_id=profile_id,
        profile_digest=_sha256_json({"profile_id": profile_id}),
    )


def _compare_binding(request: HistoricalAISAcceptanceRequest) -> HistoricalAISCompareBinding:
    if request.run_spec is None:
        return HistoricalAISCompareBinding()
    from colav_simulator.historical_compare import HistoricalBenchmarkAlignmentProfile  # noqa: PLC0415

    profile = HistoricalBenchmarkAlignmentProfile()
    return HistoricalAISCompareBinding(
        alignment_profile=profile.to_dict(),
        alignment_profile_digest=profile.digest,
    )


def _schedule_manifest(schedule: Any | None) -> dict[str, Any] | None:
    if schedule is None:
        return None
    return {
        "current_primary": str(schedule.current_primary) if schedule.current_primary is not None else None,
        "concurrent_required": [str(item) for item in schedule.concurrent_required],
        "next_threats": [str(item) for item in schedule.next_threats],
        "monitor": [str(item) for item in schedule.monitor],
        "released": [str(item) for item in schedule.released],
        "entry_count": len(schedule.entries),
        "event_count": len(schedule.events),
        "input_hash": schedule.input_hash,
        "profile_hash": schedule.profile_hash,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ACCEPTANCE_SCHEMA_VERSION",
    "HistoricalAISAcceptanceHarness",
    "HistoricalAISAcceptanceOutcome",
    "HistoricalAISAcceptanceRequest",
    "HistoricalAISPublishedCaseAcceptanceRequest",
    "HistoricalAISDimensionOverride",
    "HistoricalAISDimensionRecord",
    "HistoricalAISDimensionRegistry",
    "HistoricalAcceptanceBlockerCode",
    "HistoricalAcceptanceStatus",
    "HistoricalRealWindowSelection",
    "build_hais_2026_07_01_dimension_registry",
    "decode_dimension_registry",
]
