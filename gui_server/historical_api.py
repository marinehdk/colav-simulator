"""Normal-run Historical AIS workflow API over public benchmark contracts."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel, Field

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.persistence import jsonable
from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_case import (
    HistoricalAISAlgorithmBinding,
    HistoricalAISCapabilityReceipt,
    HistoricalAISCase,
    HistoricalAISCaseBuilder,
    HistoricalAISCaseBuildRequest,
    HistoricalAISCompareBinding,
    HistoricalAISDiscoveryProfile,
    HistoricalAISDiscoveryRequest,
    HistoricalAISEvaluationBinding,
    HistoricalAISHumanReferenceBinding,
)
from colav_simulator.historical_compare import (
    HistoricalBenchmarkAlignmentProfile,
    HistoricalBenchmarkComparator,
    HistoricalBenchmarkCompareRequest,
    HistoricalBenchmarkTrajectory,
)
from colav_simulator.historical_counterfactual import (
    HistoricalAISCounterfactualPreparation,
    HistoricalAISCounterfactualRunner,
    HistoricalAISCounterfactualRunRequest,
)
from colav_simulator.historical_enc import (
    ENCCacheIdentity,
    ENCLayerIdentity,
    ENCQualificationState,
    ENCRegionProfile,
    ENCSimulationProjection,
    ENCSourceIdentity,
)
from colav_simulator.historical_serialization import semantic_hash

router = APIRouter()


class HistoricalWorkflowStatus(str, Enum):
    PREPARED = "PREPARED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class HistoricalWorkflowErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_STATE = "INVALID_STATE"
    CASE_NOT_PUBLISHED = "CASE_NOT_PUBLISHED"
    BINDINGS_UNAVAILABLE = "BINDINGS_UNAVAILABLE"
    ENC_UNQUALIFIED = "ENC_UNQUALIFIED"
    FUTURE_LEAKAGE = "FUTURE_LEAKAGE"
    DATASET_UNAVAILABLE = "DATASET_UNAVAILABLE"
    COUNTERFACTUAL_PREPARE_FAILED = "COUNTERFACTUAL_PREPARE_FAILED"
    RUN_FAILED = "RUN_FAILED"
    NO_ENCOUNTER = "NO_ENCOUNTER"
    REFERENCE_VESSEL_UNAVAILABLE = "REFERENCE_VESSEL_UNAVAILABLE"
    DIMENSIONS_UNAVAILABLE = "DIMENSIONS_UNAVAILABLE"
    INITIAL_SEPARATION_INVALID = "INITIAL_SEPARATION_INVALID"
    TIME_COVERAGE_INSUFFICIENT = "TIME_COVERAGE_INSUFFICIENT"
    INTENT_NOT_ESTABLISHED = "INTENT_NOT_ESTABLISHED"
    SOURCE_QUALITY_UNAVAILABLE = "SOURCE_QUALITY_UNAVAILABLE"


class HistoricalWorkflowCreateRequest(BaseModel):
    """Versioned request for Dataset → Case → normal Counterfactual preparation."""

    source_path: str = Field(min_length=1)
    selection: dict[str, Any]
    enc_profile: dict[str, Any]
    case: dict[str, Any]
    run_spec: dict[str, Any]
    human_reference: dict[str, Any] | None = None
    alignment_profile: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "historical-workflow.request.v1"


class HistoricalWorkflowError(ValueError):
    def __init__(
        self,
        status: HistoricalWorkflowErrorCode | str,
        reason: str,
        lineage: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(reason)
        self.status = HistoricalWorkflowErrorCode(status)
        self.lineage = dict(lineage or {})

    def detail(self) -> dict[str, Any]:
        return {"status": self.status.value, "reason": str(self), "lineage": self.lineage}


@dataclass
class _HistoricalWorkflow:
    workflow_id: str
    source_path: Path
    case: HistoricalAISCase
    run_request: HistoricalAISCounterfactualRunRequest
    preparation: HistoricalAISCounterfactualPreparation
    runner: HistoricalAISCounterfactualRunner
    human_reference: HistoricalBenchmarkTrajectory
    alignment_profile: HistoricalBenchmarkAlignmentProfile
    status: HistoricalWorkflowStatus = HistoricalWorkflowStatus.PREPARED
    result: Any | None = None
    compare: Any | None = None
    message: str = ""
    lineage: dict[str, Any] = field(default_factory=dict)

    def document(self) -> dict[str, Any]:
        evaluation = None if self.result is None else self.result.evaluation.to_dict()
        snapshot = (
            None
            if self.result is None
            else self.result.session.threat_management_coordinator.last_snapshot
        )
        final_frame = None
        if self.result is not None and self.result.session.frames:
            final_frame = self.result.session.frames[-1]
        compare_document = None if self.compare is None else self.compare.to_dict()
        return {
            "schema_version": "historical-workflow.snapshot.v1",
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "message": self.message,
            "stages": {
                "dataset": "SELECTED",
                "case": "PUBLISHED",
                "counterfactual": (
                    self.status.value
                    if self.status in {HistoricalWorkflowStatus.PREPARED, HistoricalWorkflowStatus.COMPLETED}
                    else HistoricalWorkflowStatus.FAILED.value
                ),
                "evaluation": None if evaluation is None else evaluation["evaluation_status"],
                "compare": None if compare_document is None else compare_document["status"],
            },
            "lineage": dict(self.lineage),
            "leakage": {
                "human_reference_digest_in_run_spec": (
                    self.human_reference.trajectory_digest
                    in repr(self.run_request.to_run_spec().to_dict())
                ),
                "reference_runtime_last_time_s": self.run_request.t0_s,
            },
            "final_snapshot": jsonable(final_frame),
            "evidence": {
                "dataset_descriptor": self.case.dataset_descriptor.to_dict(),
                "case": {
                    "build_digest": self.case.build_digest,
                    "runtime_digest": self.case.runtime_digest,
                    "runtime_actor_set_digest": self.case.runtime_actor_set_digest,
                    "enc_preflight": self.case.enc_preflight.to_dict(),
                },
                "threat_snapshot": None if snapshot is None else snapshot.to_dict(),
                "evaluation": jsonable(evaluation),
                "compare_digest": None if self.compare is None else self.compare.compare_digest,
            },
            "compare": compare_document,
        }


class HistoricalWorkflowManager:
    """Own typed API workflow state while execution stays in normal sessions."""

    def __init__(self) -> None:
        self._workflows: dict[str, _HistoricalWorkflow] = {}
        self._lock = threading.RLock()

    def create(self, request: HistoricalWorkflowCreateRequest) -> dict[str, Any]:
        with self._lock:
            workflow = _prepare_workflow(request)
            self._workflows[workflow.workflow_id] = workflow
            return workflow.document()

    def run(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            workflow = self._require(workflow_id)
            if workflow.status is not HistoricalWorkflowStatus.PREPARED:
                raise HistoricalWorkflowError("INVALID_STATE", "workflow is not prepared")
            workflow.status = HistoricalWorkflowStatus.RUNNING
            try:
                prepared = workflow.preparation.prepared_run
                prepared.session.run_to_completion()
                result = workflow.runner.runner.finalize(prepared)
                result.manifest.historical_reference_artifact_digest = (
                    workflow.human_reference.trajectory_digest
                )
                result.writer.write_manifest(result.manifest)
                snapshot = result.session.threat_management_coordinator.last_snapshot
                compare_request = HistoricalBenchmarkCompareRequest.from_counterfactual_run(
                    workflow.case,
                    result,
                    human_reference=workflow.human_reference,
                    threat_evidence=None if snapshot is None else snapshot.to_dict(),
                )
                compare = HistoricalBenchmarkComparator().compare(
                    replace(compare_request, alignment_profile=workflow.alignment_profile)
                )
                workflow.result = result
                workflow.compare = compare
                workflow.status = HistoricalWorkflowStatus.COMPLETED
                workflow.lineage.update(
                    {
                        "run_digest": result.manifest.trajectory_hash,
                        "evaluation_digest": semantic_hash(result.evaluation.to_dict()),
                        "compare_digest": compare.compare_digest,
                    }
                )
            except Exception as exc:
                workflow.status = HistoricalWorkflowStatus.FAILED
                workflow.message = str(exc)
                raise HistoricalWorkflowError("RUN_FAILED", str(exc), workflow.lineage) from exc
            return workflow.document()

    def get(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            return self._require(workflow_id).document()

    def _require(self, workflow_id: str) -> _HistoricalWorkflow:
        try:
            return self._workflows[workflow_id]
        except KeyError as exc:
            raise KeyError(workflow_id) from exc


def _prepare_workflow(request: HistoricalWorkflowCreateRequest) -> _HistoricalWorkflow:
    if request.schema_version != "historical-workflow.request.v1":
        raise HistoricalWorkflowError("INVALID_REQUEST", "unsupported Historical workflow schema")
    case_document = dict(request.case)
    if case_document.get("published", True) is not True:
        raise HistoricalWorkflowError("CASE_NOT_PUBLISHED", "Historical API requires a Published Case")
    if request.human_reference is None:
        raise HistoricalWorkflowError("BINDINGS_UNAVAILABLE", "Published Case requires Human Reference binding")
    if request.run_spec.get("historical_replay") is not None or _contains_future_reference(request.run_spec):
        raise HistoricalWorkflowError("FUTURE_LEAKAGE", "client-supplied Historical runtime actor data is forbidden")

    source = Path(request.source_path).expanduser().resolve()
    if not source.is_file():
        raise HistoricalWorkflowError("DATASET_UNAVAILABLE", f"Historical dataset does not exist: {source}")
    try:
        selection = HistoricalAISSelection(**request.selection)
        dataset = HistoricalAISDatasetReader(source).read(selection)
        enc_profile = _enc_profile(request.enc_profile)
        if enc_profile.qualification_state is not ENCQualificationState.QUALIFIED:
            raise HistoricalWorkflowError("ENC_UNQUALIFIED", "Historical workflow requires a qualified ENC profile")
        run_spec = RunSpec.from_dict(dict(request.run_spec))
        if run_spec.validation_rule_id is None:
            raise HistoricalWorkflowError(
                "BINDINGS_UNAVAILABLE",
                "Published Case requires a validation_rule_id for exact capability evidence",
            )
        human_reference = HistoricalBenchmarkTrajectory(**request.human_reference)
        alignment = HistoricalBenchmarkAlignmentProfile(**request.alignment_profile)
        counterfactual_runner = HistoricalAISCounterfactualRunner()
        capability_receipt = HistoricalAISCapabilityReceipt.from_catalog(
            counterfactual_runner.runner.capabilities,
            run_spec.validation_rule_id,
            run_spec.scenario_id,
            run_spec.algorithm_id,
            run_spec.tracker_id,
        )
        discovery_profile = HistoricalAISDiscoveryProfile(**case_document.pop("discovery_profile", {}))
        discovery_request = HistoricalAISDiscoveryRequest(**case_document.pop("discovery_request", {}))
        published = case_document.pop("published", True)
        dimension_overrides = case_document.pop("dimension_overrides", {})
        build_request = HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=enc_profile,
            discovery_profile=discovery_profile,
            discovery_request=discovery_request,
            published=published,
            require_intent=True,
            dimension_overrides=dimension_overrides,
            human_reference_binding=HistoricalAISHumanReferenceBinding(
                artifact_digest=human_reference.trajectory_digest,
                sample_count=len(human_reference.timestamps_s),
            ),
            algorithm_binding=HistoricalAISAlgorithmBinding(
                algorithm_id=run_spec.algorithm_id,
                configuration_digest=semantic_hash(run_spec.algorithm_config),
                capability_evidence_digest=capability_receipt.evidence_hash,
                capability_receipt=capability_receipt,
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
            **case_document,
        )
        case_outcome = HistoricalAISCaseBuilder().build(build_request)
    except HistoricalWorkflowError:
        raise
    except Exception as exc:
        raise HistoricalWorkflowError("INVALID_REQUEST", str(exc)) from exc
    if not case_outcome.success or case_outcome.case is None:
        raise HistoricalWorkflowError(
            case_outcome.status.value,
            case_outcome.reason,
            {
                "dataset_digest": dataset.descriptor.descriptor_sha256,
                "case_build_details": dict(case_outcome.details),
            },
        )
    case = case_outcome.case
    run_request = HistoricalAISCounterfactualRunRequest(
        case=case,
        run_spec=run_spec,
        human_reference_artifact_digest=human_reference.trajectory_digest,
    )
    try:
        preparation = counterfactual_runner.prepare(run_request)
    except Exception as exc:
        raise HistoricalWorkflowError("COUNTERFACTUAL_PREPARE_FAILED", str(exc)) from exc
    workflow_id = str(uuid.uuid4())
    return _HistoricalWorkflow(
        workflow_id=workflow_id,
        source_path=source,
        case=case,
        run_request=run_request,
        preparation=preparation,
        runner=counterfactual_runner,
        human_reference=human_reference,
        alignment_profile=alignment,
        lineage={
            "dataset_digest": dataset.descriptor.descriptor_sha256,
            "case_digest": case.case_digest,
            "runtime_actor_set_digest": case.runtime_actor_set_digest,
            "run_spec_digest": run_request.run_spec_digest,
        },
    )


def _enc_profile(document: dict[str, Any]) -> ENCRegionProfile:
    value = dict(document)
    declared_digest = value.pop("profile_digest", None)
    coverage = bytes.fromhex(str(value.pop("coverage_geometry_wkb_hex", "")))
    hazard = bytes.fromhex(str(value.pop("hazard_geometry_wkb_hex", "")))
    navigability = bytes.fromhex(str(value.pop("navigability_geometry_wkb_hex", "")))
    value.pop("coverage_geometry_sha256", None)
    value.pop("hazard_geometry_sha256", None)
    value.pop("navigability_geometry_sha256", None)
    value["source"] = ENCSourceIdentity(**value["source"])
    value["projection"] = ENCSimulationProjection(**value["projection"])
    value["hazard_layers"] = tuple(ENCLayerIdentity(**item) for item in value["hazard_layers"])
    value["navigability_layers"] = tuple(
        ENCLayerIdentity(**item) for item in value["navigability_layers"]
    )
    cache = dict(value["cache"])
    cache.pop("schema_version", None)
    value["cache"] = ENCCacheIdentity(**cache)
    value["coverage_geometry_wkb"] = coverage
    value["hazard_geometry_wkb"] = hazard
    value["navigability_geometry_wkb"] = navigability
    profile = ENCRegionProfile(**value)
    if declared_digest is not None and str(declared_digest) != profile.profile_digest:
        raise HistoricalWorkflowError("ENC_UNQUALIFIED", "ENC profile digest does not match supplied evidence")
    return profile


def _contains_future_reference(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if any(token in normalized for token in ("human_reference", "future_reference", "post_t0")):
                return True
            if _contains_future_reference(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_future_reference(item) for item in value)
    return False


historical_workflows = HistoricalWorkflowManager()


@router.post("/api/historical/workflows")
def create_historical_workflow(request: HistoricalWorkflowCreateRequest) -> dict[str, Any]:
    """Select a Dataset, publish a bound Case, and prepare a normal session."""
    try:
        return historical_workflows.create(request)
    except HistoricalWorkflowError as exc:
        raise HTTPException(status_code=422, detail=exc.detail()) from exc


@router.post("/api/historical/workflows/{workflow_id}/run")
def run_historical_workflow(workflow_id: str) -> dict[str, Any]:
    """Execute one prepared normal Counterfactual session and Compare."""
    try:
        return historical_workflows.run(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Historical workflow not found") from exc
    except HistoricalWorkflowError as exc:
        raise HTTPException(status_code=422, detail=exc.detail()) from exc


@router.get("/api/historical/workflows/{workflow_id}")
def get_historical_workflow(workflow_id: str) -> dict[str, Any]:
    """Return current or final typed workflow snapshot and evidence."""
    try:
        return historical_workflows.get(workflow_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Historical workflow not found") from exc


@router.websocket("/ws/historical/{workflow_id}")
async def historical_workflow_stream(websocket: WebSocket, workflow_id: str) -> None:
    """Publish one current workflow snapshot over the established WS seam."""
    await websocket.accept()
    try:
        document = historical_workflows.get(workflow_id)
    except KeyError:
        await websocket.send_json({"error": "historical_workflow_not_found"})
    else:
        await websocket.send_json(jsonable(document))
    await websocket.close()
