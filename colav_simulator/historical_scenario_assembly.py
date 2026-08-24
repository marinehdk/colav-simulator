"""Bind one Historical AIS scene once and assemble all workflow authorities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from colav_simulator.experiment.capabilities import CapabilityCatalog
from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.historical_acceptance import (
    HistoricalAISDimensionRegistry,
    HistoricalAISPublishedCaseAcceptanceRequest,
    decode_dimension_registry,
)
from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISReadResult, HistoricalAISSelection
from colav_simulator.historical_case import (
    HistoricalAISAlgorithmBinding,
    HistoricalAISCapabilityReceipt,
    HistoricalAISCase,
    HistoricalAISCaseBuilder,
    HistoricalAISCaseBuildRequest,
    HistoricalAISCompareBinding,
    HistoricalAISDiscoveryProfile,
    HistoricalAISEvaluationBinding,
    HistoricalAISHumanReferenceBinding,
)
from colav_simulator.historical_compare import HistoricalBenchmarkAlignmentProfile, HistoricalBenchmarkTrajectory
from colav_simulator.historical_enc import (
    ENCPreflightResult,
    ENCPreflightStatus,
    ENCQualificationState,
    ENCRegionProfile,
    build_expanded_romsdal_profile,
)
from colav_simulator.historical_scenario_source import (
    HistoricalAISScenarioError,
    HistoricalAISScenarioReadiness,
    HistoricalAISSceneSourceBinder,
)
from colav_simulator.historical_serialization import semantic_hash
from colav_simulator.integrations import IntegrationRegistry


class HistoricalSceneDescriptor(Protocol):
    """Descriptor facts consumed by the assembly deep module."""

    scenario_id: str
    archive_sha256: str
    archive_scope: Mapping[str, Any]
    current_window: Mapping[str, Any]
    enc: Mapping[str, Any]
    dimensions: Mapping[str, Any]
    runtime_binding: Mapping[str, Any]
    algorithm_capability_evidence: Mapping[str, Any]

    def selection(self) -> HistoricalAISSelection: ...


@dataclass(frozen=True)
class BoundHistoricalAISReplayContext:
    """Lightweight Replay authority with no Counterfactual-only facts."""

    descriptor: HistoricalSceneDescriptor
    source: Path
    selection: HistoricalAISSelection
    dataset: HistoricalAISReadResult
    dimension_registry: HistoricalAISDimensionRegistry
    enc_profile: ENCRegionProfile
    enc_preflight: ENCPreflightResult

    @property
    def historical_scenario_id(self) -> str:
        return self.descriptor.scenario_id

    @property
    def authority_digests(self) -> dict[str, str | None]:
        """Expose only bound ENC/dimension identities; absent authorities remain null."""
        dimension_sources = tuple(
            (record.mmsi, record.source_digest) for record in self.dimension_registry.records
        )
        return {
            "enc_profile_digest": self.enc_profile.profile_digest,
            "enc_cache_digest": self.enc_profile.cache.artifact_digest,
            "enc_source_digest": self.enc_profile.source.source_digest,
            "dimension_registry_digest": self.dimension_registry.digest,
            "dimension_source_digest": semantic_hash(dimension_sources) if dimension_sources else None,
        }

    @property
    def enc_evidence(self) -> dict[str, Any]:
        return {
            "profile_id": self.enc_profile.profile_id,
            "profile_digest": self.enc_profile.profile_digest,
            "cache_digest": self.enc_profile.cache.artifact_digest,
            "source_digest": self.enc_profile.source.source_digest,
            "preflight_status": self.enc_preflight.status.value,
            "all_positions_contained": self.enc_preflight.all_positions_contained,
        }

    def replay_workflow_payload(self) -> dict[str, Any]:
        """Serialize Replay preparation without reopening the archive."""
        selection_document = self.selection.to_dict()
        selection_document.pop("schema_version", None)
        window = self.descriptor.current_window
        payload = {
            "mode": "HISTORICAL_REPLAY",
            "source_path": str(self.source),
            "selection": selection_document,
            "expected_archive_sha256": self.descriptor.archive_sha256,
            "expected_entries": [_expected_entry(window)],
            "expected_schema_sha256": str(window["expected_schema_sha256"]),
            "expected_selection_sha256": str(window["expected_selection_sha256"]),
            "expected_normalized_sha256": str(window["expected_normalized_sha256"]),
            "expected_descriptor_sha256": str(window["expected_descriptor_sha256"]),
        }
        payload.update(
            {
                "replay": _replay_document(self),
                "run_spec": _run_spec(self.descriptor, "HISTORICAL_REPLAY", None),
            }
        )
        return payload


@dataclass(frozen=True)
class BoundHistoricalAISSceneContext(BoundHistoricalAISReplayContext):
    """Full Counterfactual authority reusing one Published Case."""

    human_reference: HistoricalBenchmarkTrajectory
    run_spec: RunSpec
    case: HistoricalAISCase

    @property
    def case_identity(self) -> dict[str, str]:
        return {
            "historical_scenario_id": self.historical_scenario_id,
            "dataset_digest": self.dataset.descriptor.descriptor_sha256,
            "case_digest": self.case.case_digest,
            "runtime_actor_set_digest": self.case.runtime_actor_set_digest,
            **self.authority_digests,
        }

    def acceptance_request(self) -> HistoricalAISPublishedCaseAcceptanceRequest:
        """Return two-run qualification over this exact Published Case object."""
        return HistoricalAISPublishedCaseAcceptanceRequest(
            case=self.case,
            run_spec=self.run_spec,
            human_reference=self.human_reference,
            human_reference_artifact_digest=self.human_reference.trajectory_digest,
        )


class HistoricalAISSceneAssembler:
    """Perform source/Dataset/ENC/dimension/Human/Case binding exactly once."""

    def __init__(
        self,
        *,
        dataset_reader_type: type[HistoricalAISDatasetReader] = HistoricalAISDatasetReader,
        enc_builder: Any = build_expanded_romsdal_profile,
        capability_catalog: CapabilityCatalog | None = None,
    ) -> None:
        self._dataset_reader_type = dataset_reader_type
        self._enc_builder = enc_builder
        self._capability_catalog = capability_catalog

    def bind_replay(
        self,
        descriptor: HistoricalSceneDescriptor,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> BoundHistoricalAISReplayContext:
        source = HistoricalAISSceneSourceBinder.require_source(descriptor, environ)
        selection = descriptor.selection()
        dataset = self._dataset_reader_type(source).read(selection)
        self.validate_dataset_identity(descriptor, dataset)
        enc_profile = self._qualified_enc_profile(descriptor)
        enc_preflight = enc_profile.preflight_historical_ais(dataset)
        if not enc_preflight.qualified:
            status = (
                HistoricalAISScenarioReadiness.OUTSIDE_COVERAGE
                if enc_preflight.status is ENCPreflightStatus.OUTSIDE_COVERAGE
                else HistoricalAISScenarioReadiness.ENC_UNQUALIFIED
            )
            raise HistoricalAISScenarioError(
                status,
                f"Historical Replay ENC preflight failed: {enc_preflight.status.value}",
            )
        return BoundHistoricalAISReplayContext(
            descriptor=descriptor,
            source=source,
            selection=selection,
            dataset=dataset,
            dimension_registry=decode_dimension_registry(descriptor.dimensions),
            enc_profile=enc_profile,
            enc_preflight=enc_preflight,
        )

    def bind_counterfactual(
        self,
        descriptor: HistoricalSceneDescriptor,
        *,
        run_spec_overrides: Mapping[str, Any] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> BoundHistoricalAISSceneContext:
        replay = self.bind_replay(descriptor, environ=environ)
        human_reference = _historical_reference(
            replay.dataset,
            replay.enc_profile,
            int(descriptor.current_window["reference_mmsi"]),
        )
        run_spec = RunSpec.from_dict(_run_spec(descriptor, "COUNTERFACTUAL", run_spec_overrides))
        case = self._publish_case(
            descriptor,
            replay.dataset,
            replay.selection,
            replay.enc_profile,
            replay.dimension_registry,
            human_reference,
            run_spec,
        )
        return BoundHistoricalAISSceneContext(
            descriptor=replay.descriptor,
            source=replay.source,
            selection=replay.selection,
            dataset=replay.dataset,
            dimension_registry=replay.dimension_registry,
            enc_profile=replay.enc_profile,
            enc_preflight=replay.enc_preflight,
            human_reference=human_reference,
            run_spec=run_spec,
            case=case,
        )

    def _qualified_enc_profile(self, descriptor: HistoricalSceneDescriptor) -> ENCRegionProfile:
        profile = self._enc_builder()
        if (
            profile.profile_digest != str(descriptor.enc["profile_digest"])
            or profile.qualification_state is not ENCQualificationState.QUALIFIED
        ):
            raise HistoricalAISScenarioError(
                HistoricalAISScenarioReadiness.ENC_UNQUALIFIED,
                "Romsdal ENC identity/qualification differs from the scene descriptor",
            )
        return profile

    @staticmethod
    def validate_dataset_identity(
        descriptor: HistoricalSceneDescriptor,
        dataset: HistoricalAISReadResult,
    ) -> None:
        """Validate every derived and raw identity before publishing a Case."""
        observed = dataset.descriptor
        window = descriptor.current_window
        expected_entry = _expected_entry(window)
        entries = {entry.entry_name: entry for entry in observed.entry_digests}
        selected = entries.get(expected_entry["entry_name"])
        mismatches = []
        expected = {
            "archive_sha256": descriptor.archive_sha256,
            "schema_sha256": str(window["expected_schema_sha256"]),
            "selection_sha256": str(window["expected_selection_sha256"]),
            "normalized_sha256": str(window["expected_normalized_sha256"]),
            "descriptor_sha256": str(window["expected_descriptor_sha256"]),
        }
        for field_name, expected_value in expected.items():
            if getattr(observed, field_name) != expected_value:
                mismatches.append(field_name)
        if selected is None:
            mismatches.append("selected_entry")
        else:
            if selected.sha256 != expected_entry["sha256"]:
                mismatches.append("entry_sha256")
            if selected.uncompressed_bytes != expected_entry["uncompressed_bytes"]:
                mismatches.append("entry_uncompressed_bytes")
        if mismatches:
            raise HistoricalAISScenarioError(
                HistoricalAISScenarioReadiness.DATASET_IDENTITY_MISMATCH,
                f"Historical Dataset identity mismatch: {', '.join(sorted(mismatches))}",
            )

    def _publish_case(
        self,
        descriptor: HistoricalSceneDescriptor,
        dataset: HistoricalAISReadResult,
        selection: HistoricalAISSelection,
        enc_profile: ENCRegionProfile,
        registry: HistoricalAISDimensionRegistry,
        human_reference: HistoricalBenchmarkTrajectory,
        run_spec: RunSpec,
    ) -> HistoricalAISCase:
        capability_tuple = run_spec.capability_tuple
        if capability_tuple is None:
            raise HistoricalAISScenarioError(
                HistoricalAISScenarioReadiness.CASE_BUILD_FAILED,
                "Published Case lacks exact Algorithm Capability evidence",
            )
        catalog = self._capability_catalog or CapabilityCatalog(IntegrationRegistry())
        receipt = HistoricalAISCapabilityReceipt.from_catalog(catalog, *capability_tuple)
        alignment = HistoricalBenchmarkAlignmentProfile()
        outcome = HistoricalAISCaseBuilder().build(
            HistoricalAISCaseBuildRequest(
                dataset=dataset,
                selection=selection,
                enc_profile=enc_profile,
                discovery_profile=HistoricalAISDiscoveryProfile(
                    max_encounter_range_m=10_000.0,
                    min_closing_speed_mps=0.0,
                    min_pre_t0_samples=2,
                    min_pre_t0_duration_s=1.0,
                ),
                reference_mmsi=int(descriptor.current_window["reference_mmsi"]),
                historical_scenario_id=descriptor.scenario_id,
                t0_utc=str(descriptor.current_window["t0_utc"]),
                published=True,
                dimension_overrides={record.mmsi: record.to_dict() for record in registry.records},
                human_reference_binding=HistoricalAISHumanReferenceBinding(
                    artifact_digest=human_reference.trajectory_digest,
                    sample_count=len(human_reference.timestamps_s),
                ),
                algorithm_binding=HistoricalAISAlgorithmBinding(
                    algorithm_id=run_spec.algorithm_id,
                    configuration_digest=semantic_hash(run_spec.algorithm_config),
                    capability_evidence_digest=receipt.evidence_hash,
                    capability_receipt=receipt,
                ),
                evaluation_binding=HistoricalAISEvaluationBinding(
                    "colav-independent-evaluator",
                    run_spec.evaluator_profile_id,
                    semantic_hash({"profile_id": run_spec.evaluator_profile_id}),
                ),
                compare_binding=HistoricalAISCompareBinding(
                    alignment_profile=alignment.to_dict(),
                    alignment_profile_digest=alignment.digest,
                ),
            )
        )
        if not outcome.success or outcome.case is None:
            raise HistoricalAISScenarioError(
                HistoricalAISScenarioReadiness.CASE_BUILD_FAILED,
                outcome.reason,
            )
        return outcome.case


def _run_spec(
    descriptor: HistoricalSceneDescriptor,
    mode: str,
    overrides: Mapping[str, Any] | None,
) -> dict[str, Any]:
    binding = descriptor.runtime_binding
    capability = _thaw(descriptor.algorithm_capability_evidence)
    algorithm_id = "nominal" if mode == "HISTORICAL_REPLAY" else str(binding["algorithm_id"])
    capability["exact_tuple"][2] = algorithm_id
    result = {
        "scenario_id": descriptor.scenario_id,
        "historical_scenario_id": descriptor.scenario_id,
        "algorithm_capability_evidence": capability,
        "algorithm_id": algorithm_id,
        "tracker_id": str(binding["tracker_id"]),
        "t_end": 60.0,
        "terminate_on_collision_or_grounding": False,
        "strict_no_fallback": True,
        "evaluator_profile_id": str(binding["evaluator_profile_id"]),
    }
    if mode != "HISTORICAL_REPLAY":
        result["domain_profile"] = _thaw(binding["domain_profile"])
    if overrides:
        allowed = {"algorithm_config", "tracker_config", "dt", "t_end", "evaluator_profile_id", "domain_profile"}
        unknown = sorted(set(overrides).difference(allowed))
        if unknown:
            raise ValueError(f"unsupported Historical AIS run options: {unknown}")
        result.update(dict(overrides))
    return result


def _historical_reference(
    dataset: HistoricalAISReadResult,
    enc_profile: ENCRegionProfile,
    reference_mmsi: int,
) -> HistoricalBenchmarkTrajectory:
    observations = [
        observation
        for observation in dataset.observations
        if observation.normalized.mmsi == reference_mmsi and observation.normalized.timestamp_utc is not None
    ]
    origin = min(
        observation.normalized.timestamp_utc
        for observation in dataset.observations
        if observation.normalized.timestamp_utc is not None
    )
    timestamps, positions, courses, speeds = [], [], [], []
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


def _replay_document(context: BoundHistoricalAISReplayContext) -> dict[str, Any]:
    registry = context.dimension_registry
    return {
        "reference_mmsi": int(context.descriptor.current_window["reference_mmsi"]),
        "reconstruction_profile": {
            "profile_id": "historical-actor-reconstruction.v1",
            "time_step_s": 1.0,
            "max_interpolation_gap_s": 300.0,
            "projection_crs": "EPSG:32633",
            "source_crs": "EPSG:4326",
            "coordinate_axis_order": "longitude_latitude",
            "gap_policy": "terminate_without_ghost_extrapolation",
        },
        "dimension_registry": {**registry.to_dict(), "registry_digest": registry.digest},
        "dimension_effective_at_utc": str(context.descriptor.current_window["t0_utc"]),
        "dt_sim": 1.0,
        "t_end_s": 60.0,
        "scenario_name": context.historical_scenario_id,
        "utm_zone": 33,
    }


def _expected_entry(window: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "entry_name": str(window["entry_name"]),
        "sha256": str(window["entry_sha256"]),
        "uncompressed_bytes": int(window["entry_uncompressed_bytes"]),
        "crc32": int(window["entry_crc32"]),
    }


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


__all__ = [
    "BoundHistoricalAISReplayContext",
    "BoundHistoricalAISSceneContext",
    "HistoricalAISSceneAssembler",
]
