"""Normal-run Historical AIS workflow API over public benchmark contracts."""

from __future__ import annotations

import threading
import uuid
import zipfile
import zlib
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel, Field

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.persistence import jsonable
from colav_simulator.experiment.runner import ExperimentRunner, PreparedRun
from colav_simulator.historical_acceptance import (
    HistoricalAcceptanceStatus,
    HistoricalAISAcceptanceHarness,
    HistoricalAISAcceptanceOutcome,
    HistoricalAISAcceptanceRequest,
    HistoricalAISDimensionRecord,
    HistoricalAISDimensionRegistry,
)
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
    apply_dimension_overrides,
)
from colav_simulator.historical_compare import (
    HistoricalBenchmarkAlignmentProfile,
    HistoricalBenchmarkComparator,
    HistoricalBenchmarkCompareRequest,
    HistoricalBenchmarkTrajectory,
)
from colav_simulator.historical_counterfactual import (
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
from colav_simulator.historical_replay import (
    HistoricalActorSet,
    HistoricalAISReconstructionProfile,
    HistoricalAISReconstructor,
    HistoricalReplayFactory,
    HistoricalReplayRequest,
)
from colav_simulator.historical_scenario_catalog import (
    HistoricalAISScenarioCatalog,
    HistoricalAISScenarioError,
)
from colav_simulator.historical_serialization import semantic_hash
from colav_simulator.simulator import Config as SimulatorConfig
from colav_simulator.simulator import Simulator

router = APIRouter()


class HistoricalWorkflowStatus(str, Enum):
    PREPARED = "PREPARED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class HistoricalWorkflowMode(str, Enum):
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    COUNTERFACTUAL = "COUNTERFACTUAL"


class HistoricalWorkflowErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_STATE = "INVALID_STATE"
    CASE_NOT_PUBLISHED = "CASE_NOT_PUBLISHED"
    BINDINGS_UNAVAILABLE = "BINDINGS_UNAVAILABLE"
    ENC_UNQUALIFIED = "ENC_UNQUALIFIED"
    FUTURE_LEAKAGE = "FUTURE_LEAKAGE"
    DATASET_UNAVAILABLE = "DATASET_UNAVAILABLE"
    DIMENSIONS_UNAVAILABLE = "DIMENSIONS_UNAVAILABLE"
    QUALITY_INCOMPLETE = "QUALITY_INCOMPLETE"
    COUNTERFACTUAL_PREPARE_FAILED = "COUNTERFACTUAL_PREPARE_FAILED"
    RUN_FAILED = "RUN_FAILED"
    NO_ENCOUNTER = "NO_ENCOUNTER"
    REFERENCE_VESSEL_UNAVAILABLE = "REFERENCE_VESSEL_UNAVAILABLE"
    INITIAL_SEPARATION_INVALID = "INITIAL_SEPARATION_INVALID"
    TIME_COVERAGE_INSUFFICIENT = "TIME_COVERAGE_INSUFFICIENT"
    INTENT_NOT_ESTABLISHED = "INTENT_NOT_ESTABLISHED"
    SOURCE_QUALITY_UNAVAILABLE = "SOURCE_QUALITY_UNAVAILABLE"
    DATASET_IDENTITY_MISMATCH = "DATASET_IDENTITY_MISMATCH"


class HistoricalExpectedEntry(BaseModel):
    entry_name: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    uncompressed_bytes: int = Field(ge=0)
    crc32: int = Field(ge=0, le=0xFFFFFFFF)


class HistoricalWorkflowCreateRequest(BaseModel):
    """Versioned request for Replay or Dataset → Case → Counterfactual preparation."""

    mode: HistoricalWorkflowMode
    source_path: str = Field(min_length=1)
    selection: dict[str, Any]
    expected_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_entries: list[HistoricalExpectedEntry] = Field(min_length=1)
    expected_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_selection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    enc_profile: dict[str, Any] | None = None
    case: dict[str, Any] = Field(default_factory=dict)
    replay: dict[str, Any] = Field(default_factory=dict)
    run_spec: dict[str, Any]
    human_reference: dict[str, Any] | None = None
    alignment_profile: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "historical-workflow.request.v1"


class HistoricalScenarioWorkflowCreateRequest(BaseModel):
    """Small UI request; source, Dataset, Case and runtime contracts stay server-owned."""

    mode: HistoricalWorkflowMode
    run_spec: dict[str, Any] = Field(default_factory=dict)


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
    mode: HistoricalWorkflowMode
    source_path: Path
    dataset_descriptor: Any
    prepared_run: PreparedRun
    experiment_runner: ExperimentRunner
    case: HistoricalAISCase | None = None
    run_request: HistoricalAISCounterfactualRunRequest | None = None
    replay_request: HistoricalReplayRequest | None = None
    human_reference: HistoricalBenchmarkTrajectory | None = None
    alignment_profile: HistoricalBenchmarkAlignmentProfile | None = None
    status: HistoricalWorkflowStatus = HistoricalWorkflowStatus.PREPARED
    result: Any | None = None
    compare: Any | None = None
    message: str = ""
    lineage: dict[str, Any] = field(default_factory=dict)
    historical_scenario_id: str | None = None
    qualification_request: HistoricalAISAcceptanceRequest | None = None
    qualification_outcome: HistoricalAISAcceptanceOutcome | None = None

    def document(self) -> dict[str, Any]:
        if self.qualification_outcome is not None:
            return _qualified_workflow_document(self)
        evaluation = None if self.result is None else self.result.evaluation.to_dict()
        snapshot = None if self.result is None else self.result.session.threat_management_coordinator.last_snapshot
        final_frame = None
        if self.result is not None and self.result.session.frames:
            final_frame = self.result.session.frames[-1]
        compare_document = None if self.compare is None else self.compare.to_dict()
        qualification = _workflow_qualification(self)
        determinism = {
            "status": "NOT_APPLICABLE"
            if self.mode is HistoricalWorkflowMode.HISTORICAL_REPLAY
            else "NOT_CHECKED",
            "mismatches": [],
        }
        return {
            "schema_version": "historical-workflow.snapshot.v1",
            "workflow_id": self.workflow_id,
            "historical_scenario_id": self.historical_scenario_id,
            "mode": self.mode.value,
            "status": self.status.value,
            "message": self.message,
            "qualification": qualification,
            "determinism": determinism,
            "stages": {
                "dataset": "SELECTED",
                "case": "PUBLISHED" if self.case is not None else "NOT_APPLICABLE",
                "replay": (self.status.value if self.mode is HistoricalWorkflowMode.HISTORICAL_REPLAY else "NOT_APPLICABLE"),
                "counterfactual": (
                    self.status.value if self.mode is HistoricalWorkflowMode.COUNTERFACTUAL else "NOT_APPLICABLE"
                ),
                "evaluation": None if evaluation is None else evaluation["evaluation_status"],
                "compare": None if compare_document is None else compare_document["status"],
            },
            "lineage": {
                **({} if self.historical_scenario_id is None else {"historical_scenario_id": self.historical_scenario_id}),
                **dict(self.lineage),
            },
            "leakage": {
                "human_reference_digest_in_run_spec": (
                    False
                    if self.human_reference is None or self.run_request is None
                    else self.human_reference.trajectory_digest in repr(self.run_request.to_run_spec().to_dict())
                ),
                "reference_runtime_last_time_s": (None if self.run_request is None else self.run_request.t0_s),
            },
            "final_snapshot": jsonable(final_frame),
            "evidence": {
                "dataset_descriptor": self.dataset_descriptor.to_dict(),
                "case": (
                    None
                    if self.case is None
                    else {
                        "build_digest": self.case.build_digest,
                        "runtime_digest": self.case.runtime_digest,
                        "runtime_actor_set_digest": self.case.runtime_actor_set_digest,
                        "enc_preflight": self.case.enc_preflight.to_dict(),
                    }
                ),
                "historical_replay": (None if self.replay_request is None else self.replay_request.evidence.to_dict()),
                "run": (
                    None
                    if self.result is None
                    else {
                        "run_id": self.result.manifest.run_id,
                        "historical_scenario_id": self.result.manifest.historical_scenario_id,
                        "historical_execution_mode": self.result.manifest.historical_execution_mode,
                        "requested_algorithm": self.result.manifest.requested_algorithm,
                        "executed_algorithm": self.result.manifest.executed_algorithm,
                        "fallback_used": self.result.manifest.fallback_used,
                        "session_contract": "SimulationSession",
                        "replay_factory": (
                            "HistoricalReplayFactory" if self.mode is HistoricalWorkflowMode.HISTORICAL_REPLAY else None
                        ),
                        "algorithm_capability_evidence": self.prepared_run.spec.algorithm_capability_evidence,
                    }
                ),
                "threat_snapshot": None if snapshot is None else snapshot.to_dict(),
                "evaluation": jsonable(evaluation),
                "compare_digest": None if self.compare is None else self.compare.compare_digest,
            },
            "compare": compare_document,
            "presentation": _workflow_presentation(
                self,
                qualification=qualification,
                determinism=determinism,
                run=(None if self.result is None else self.result.manifest),
            ),
        }


def _workflow_qualification(workflow: _HistoricalWorkflow) -> dict[str, Any]:
    if workflow.mode is HistoricalWorkflowMode.HISTORICAL_REPLAY:
        return {
            "status": "NOT_APPLICABLE",
            "execution_mode": "HISTORICAL_REPLAY",
            "run_count": 1 if workflow.result is not None else 0,
            "reason": "Historical Replay is playback evidence, not Counterfactual qualification",
        }
    if workflow.qualification_request is not None:
        return {
            "status": "PENDING",
            "execution_mode": "DOUBLE_RUN_ACCEPTANCE",
            "run_count": 0,
            "reason": "qualification requires two independent Run/Evaluation/Compare executions",
        }
    return {
        "status": "NOT_QUALIFIED",
        "execution_mode": "RUN_ONLY",
        "run_count": 1 if workflow.result is not None else 0,
        "reason": "single Counterfactual run is not deterministic qualification evidence",
    }


def _workflow_presentation(
    workflow: _HistoricalWorkflow,
    *,
    qualification: dict[str, Any],
    determinism: dict[str, Any],
    run: Any | None,
) -> dict[str, Any]:
    threat = _presentation_threat(workflow)
    leakage_status = "NOT_APPLICABLE" if workflow.mode is HistoricalWorkflowMode.HISTORICAL_REPLAY else "PASS_CONTRACT"
    compare = _presentation_compare(workflow)
    determinism_presentation = {
        "status": determinism.get("status"),
        "mismatch_count": (
            len(determinism.get("mismatches", ()))
            if determinism.get("status") in {"PASS", "FAIL"}
            else None
        ),
    }
    threat_graph_qualification = None
    if qualification.get("execution_mode") == "DOUBLE_RUN_ACCEPTANCE" and threat["status"] == "AVAILABLE":
        threat_graph_qualification = {
            "status": qualification.get("status"),
            "code": qualification.get("code"),
            "vector_count": threat["vector_count"],
            "schedule_entry_count": threat["schedule_entry_count"],
            "cluster_count": threat["cluster_count"],
        }
    qualification_presentation = {
        **qualification,
        "determinism": determinism_presentation,
        "threat_graph": threat_graph_qualification,
    }
    scene = {
        "id": workflow.historical_scenario_id,
        "kind": "HISTORICAL_AIS" if workflow.historical_scenario_id else "AD_HOC_HISTORICAL_WORKFLOW",
        **(
            {}
            if workflow.historical_scenario_id is None
            else {"status": "AVAILABLE", "scope": "BOUNDED"}
        ),
    }
    return {
        "schema_version": "historical-workflow.presentation.v1",
        "scenario": scene,
        "operability": (
            {"status": "AVAILABLE", "scope": "BOUNDED"}
            if workflow.historical_scenario_id is not None
            else {"status": "AVAILABLE", "scope": "AD_HOC"}
        ),
        "qualification": qualification_presentation,
        "runtime": {
            "mode": workflow.mode.value,
            "status": workflow.status.value,
            "requested_algorithm": _run_value(run, "requested_algorithm"),
            "executed_algorithm": _run_value(run, "executed_algorithm"),
            "fallback_used": _run_value(run, "fallback_used"),
            **(
                {}
                if workflow.prepared_run.spec.algorithm_capability_evidence is None
                else {"algorithm_capability_evidence": workflow.prepared_run.spec.algorithm_capability_evidence}
            ),
        },
        "threat": threat,
        "leakage": {"status": leakage_status},
        "determinism": determinism_presentation,
        "compare": compare,
        "evidence": {
            "lineage": {
                **(
                    {}
                    if workflow.historical_scenario_id is None
                    else {"historical_scenario_id": workflow.historical_scenario_id}
                ),
                **dict(workflow.lineage),
            },
            **(
                {}
                if workflow.historical_scenario_id is None
                else {
                    "source_readiness": "READY",
                    "digests": {
                        "dataset_descriptor_sha256": workflow.dataset_descriptor.descriptor_sha256,
                        "selection_sha256": workflow.dataset_descriptor.selection_sha256,
                        "runtime_actor_set_sha256": workflow.lineage.get("runtime_actor_set_digest"),
                    },
                    "replay": (
                        workflow.replay_request.evidence.to_dict()
                        if workflow.replay_request is not None
                        else {
                            "mode": workflow.mode.value,
                            "historical_scenario_id": workflow.historical_scenario_id,
                            "case_digest": workflow.lineage.get("case_digest"),
                        }
                    ),
                }
            ),
        },
    }


def _presentation_threat(workflow: _HistoricalWorkflow) -> dict[str, Any]:
    if workflow.qualification_outcome is not None:
        threat = dict(workflow.qualification_outcome.manifest.get("threat", {}) or {})
        counts = (
            threat.get("vector_count"),
            threat.get("schedule_context_count"),
            threat.get("cluster_count"),
        )
        if all(isinstance(value, int) and not isinstance(value, bool) for value in counts):
            return {
                "status": "AVAILABLE",
                "vector_count": counts[0],
                "schedule_entry_count": counts[1],
                "cluster_count": counts[2],
            }
    snapshot = None if workflow.result is None else workflow.result.session.threat_management_coordinator.last_snapshot
    if snapshot is None:
        return {
            "status": "UNAVAILABLE",
            "vector_count": None,
            "schedule_entry_count": None,
            "cluster_count": None,
        }
    counts = (
        len(snapshot.vectors) if snapshot.vectors is not None else None,
        len(snapshot.schedule.entries) if snapshot.schedule is not None else None,
        len(snapshot.conflict_graph.clusters) if snapshot.conflict_graph is not None else None,
    )
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in counts):
        return {
            "status": "UNAVAILABLE",
            "vector_count": None,
            "schedule_entry_count": None,
            "cluster_count": None,
        }
    return {
        "status": "AVAILABLE",
        "vector_count": counts[0],
        "schedule_entry_count": counts[1],
        "cluster_count": counts[2],
    }


def _presentation_compare(workflow: _HistoricalWorkflow) -> dict[str, Any]:
    if workflow.mode is HistoricalWorkflowMode.HISTORICAL_REPLAY:
        return {
            "status": "NOT_APPLICABLE",
            "overall_assurance_verdict": None,
            "domain_statuses": _empty_compare_domains(),
        }
    if workflow.qualification_outcome is not None:
        compare = dict(workflow.qualification_outcome.manifest.get("compare", {}) or {})
    else:
        compare = {} if workflow.compare is None else workflow.compare.to_dict()
    if not compare:
        return {
            "status": "UNAVAILABLE",
            "overall_assurance_verdict": None,
            "domain_statuses": _empty_compare_domains(),
        }
    domains = compare.get("domain_statuses")
    if not isinstance(domains, dict):
        raw_domains = compare.get("domains", {})
        domains = {
            key: (value.get("status") if isinstance(value, dict) else None)
            for key, value in raw_domains.items()
        }
    return {
        "status": compare.get("status"),
        "overall_assurance_verdict": compare.get("overall_assurance_verdict"),
        "domain_statuses": {**_empty_compare_domains(), **domains},
    }


def _empty_compare_domains() -> dict[str, None]:
    return {
        "safety": None,
        "colreg": None,
        "maneuver": None,
        "efficiency": None,
        "human_similarity": None,
    }


def _qualified_workflow_document(workflow: _HistoricalWorkflow) -> dict[str, Any]:
    outcome = workflow.qualification_outcome
    if outcome is None:  # pragma: no cover - guarded by caller
        raise RuntimeError("qualification outcome is unavailable")
    manifest = dict(outcome.manifest)
    qualified = outcome.status is HistoricalAcceptanceStatus.PASS
    qualification_incomplete = _qualification_incomplete(outcome)
    completed = qualified or qualification_incomplete
    runs = list(manifest.get("runs", ()))
    run_count = len(runs) if runs else int(bool(manifest.get("run")))
    threat = dict(manifest.get("threat", {}) or {})
    qualification = {
        "status": "QUALIFIED" if qualified else "NOT_QUALIFIED",
        "code": None if qualified else (outcome.blocker_codes[0] if outcome.blocker_codes else "QUALIFICATION_FAILED"),
        "execution_mode": "DOUBLE_RUN_ACCEPTANCE",
        "run_count": run_count,
        "reason": "" if qualified else "; ".join(outcome.blocker_messages),
        "actual_counts": {
            "vector_count": threat.get("vector_count"),
            "schedule_context_count": threat.get("schedule_context_count"),
            "cluster_count": threat.get("cluster_count"),
        },
        "future_gate": "NONEMPTY_NATURAL_CLUSTER" if qualification_incomplete else None,
    }
    determinism = dict(manifest.get("determinism", {"status": "NOT_CHECKED", "mismatches": []}))
    run = dict(manifest.get("run", {}))
    evaluation = manifest.get("evaluation")
    compare = manifest.get("compare")
    status = HistoricalWorkflowStatus.COMPLETED if completed else HistoricalWorkflowStatus.FAILED
    lineage = {"historical_scenario_id": workflow.historical_scenario_id, **dict(manifest.get("lineage", {}))}
    return {
        "schema_version": "historical-workflow.snapshot.v1",
        "workflow_id": workflow.workflow_id,
        "historical_scenario_id": workflow.historical_scenario_id,
        "mode": workflow.mode.value,
        "status": status.value,
        "message": workflow.message,
        "qualification": qualification,
        "determinism": determinism,
        "stages": {
            "dataset": "SELECTED",
            "case": "PUBLISHED" if manifest.get("case") else "NOT_APPLICABLE",
            "replay": "NOT_APPLICABLE",
            "counterfactual": status.value,
            "evaluation": None if evaluation is None else evaluation.get("evaluation_status"),
            "compare": None if compare is None else compare.get("status"),
        },
        "lineage": lineage,
        "leakage": manifest.get("leakage", {}),
        "final_snapshot": None,
        "evidence": {
            "dataset_descriptor": outcome.dataset_descriptor,
            "case": manifest.get("case"),
            "historical_replay": None,
            "run": run or None,
            "threat": threat,
            "threat_snapshot": None,
            "evaluation": evaluation,
            "compare_digest": None if compare is None else compare.get("compare_digest"),
            "determinism": determinism,
        },
        "compare": compare,
        "presentation": _workflow_presentation(
            workflow,
            qualification=qualification,
            determinism=determinism,
            run=run,
        ),
    }


def _qualification_incomplete(outcome: HistoricalAISAcceptanceOutcome) -> bool:
    manifest = outcome.manifest
    run = manifest.get("run", {})
    evaluation = manifest.get("evaluation", {})
    compare = manifest.get("compare", {})
    leakage = manifest.get("leakage", {})
    determinism = manifest.get("determinism", {})
    threat = manifest.get("threat", {})
    return (
        outcome.blocker_codes == ("THREAT_EVIDENCE_INCOMPLETE",)
        and run.get("fallback_used") is False
        and run.get("requested_algorithm") == run.get("executed_algorithm")
        and evaluation.get("evaluation_status") == "COMPLETE"
        and evaluation.get("gate") == "PASS"
        and compare.get("status") == "COMPLETE"
        and leakage.get("status") == "PASS_CONTRACT"
        and determinism.get("status") == "PASS"
        and not determinism.get("mismatches")
        and threat.get("cluster_count") == 0
    )


def _run_value(run: Any | None, field_name: str) -> Any:
    if run is None:
        return None
    if isinstance(run, dict):
        return run.get(field_name)
    return getattr(run, field_name, None)


class HistoricalWorkflowManager:
    """Own typed API workflow state while execution stays in normal sessions."""

    def __init__(self) -> None:
        self._workflows: dict[str, _HistoricalWorkflow] = {}
        self._lock = threading.RLock()

    def create(
        self,
        request: HistoricalWorkflowCreateRequest,
        *,
        qualification_request: HistoricalAISAcceptanceRequest | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            workflow = _prepare_workflow(request)
            workflow.historical_scenario_id = workflow.prepared_run.spec.historical_scenario_id
            workflow.qualification_request = qualification_request
            self._workflows[workflow.workflow_id] = workflow
            return workflow.document()

    def run(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            workflow = self._require(workflow_id)
            if workflow.status is not HistoricalWorkflowStatus.PREPARED:
                raise HistoricalWorkflowError("INVALID_STATE", "workflow is not prepared")
            workflow.status = HistoricalWorkflowStatus.RUNNING
            if workflow.qualification_request is not None:
                try:
                    workflow.prepared_run.artifact_sink.close(timeout_s=2.0)
                    outcome = HistoricalAISAcceptanceHarness().run(workflow.qualification_request)
                except Exception as exc:
                    workflow.status = HistoricalWorkflowStatus.FAILED
                    workflow.message = str(exc)
                    raise HistoricalWorkflowError("RUN_FAILED", str(exc), workflow.lineage) from exc
                workflow.qualification_outcome = outcome
                workflow.status = (
                    HistoricalWorkflowStatus.COMPLETED
                    if outcome.status is HistoricalAcceptanceStatus.PASS or _qualification_incomplete(outcome)
                    else HistoricalWorkflowStatus.FAILED
                )
                workflow.message = "; ".join(outcome.blocker_messages)
                return workflow.document()
            try:
                prepared = workflow.prepared_run
                prepared.session.run_to_completion()
                result = workflow.experiment_runner.finalize(prepared)
                if workflow.human_reference is not None:
                    result.manifest.historical_reference_artifact_digest = workflow.human_reference.trajectory_digest
                result.writer.write_manifest(result.manifest)
                snapshot = result.session.threat_management_coordinator.last_snapshot
                compare = None
                if workflow.mode is HistoricalWorkflowMode.COUNTERFACTUAL:
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
                        **({} if compare is None else {"compare_digest": compare.compare_digest}),
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
    if request.run_spec.get("historical_replay") is not None or _contains_future_reference(request.run_spec):
        raise HistoricalWorkflowError("FUTURE_LEAKAGE", "client-supplied Historical runtime actor data is forbidden")
    source = Path(request.source_path).expanduser().resolve()
    if not source.is_file():
        raise HistoricalWorkflowError("DATASET_UNAVAILABLE", f"Historical dataset does not exist: {source}")
    try:
        selection = HistoricalAISSelection(**request.selection)
        dataset = HistoricalAISDatasetReader(source).read(selection)
        _validate_dataset_identity(request, source, dataset.descriptor)
        run_spec = RunSpec.from_dict(dict(request.run_spec))
    except HistoricalWorkflowError:
        raise
    except Exception as exc:
        raise HistoricalWorkflowError("INVALID_REQUEST", str(exc)) from exc
    if request.mode is HistoricalWorkflowMode.HISTORICAL_REPLAY:
        return _prepare_replay_workflow(request, source, dataset, run_spec)
    return _prepare_counterfactual_workflow(request, source, dataset, selection, run_spec)


def _prepare_counterfactual_workflow(
    request: HistoricalWorkflowCreateRequest,
    source: Path,
    dataset: Any,
    selection: HistoricalAISSelection,
    run_spec: RunSpec,
) -> _HistoricalWorkflow:
    if request.replay:
        raise HistoricalWorkflowError("INVALID_REQUEST", "Counterfactual mode cannot accept Replay configuration")
    case_document = dict(request.case)
    if case_document.get("published", True) is not True:
        raise HistoricalWorkflowError("CASE_NOT_PUBLISHED", "Historical API requires a Published Case")
    if request.human_reference is None:
        raise HistoricalWorkflowError("BINDINGS_UNAVAILABLE", "Published Case requires Human Reference binding")
    if request.enc_profile is None:
        raise HistoricalWorkflowError("ENC_UNQUALIFIED", "Counterfactual mode requires ENC profile evidence")
    try:
        enc_profile = _enc_profile(request.enc_profile)
        if enc_profile.qualification_state is not ENCQualificationState.QUALIFIED:
            raise HistoricalWorkflowError("ENC_UNQUALIFIED", "Historical workflow requires a qualified ENC profile")
        capability_tuple = run_spec.capability_tuple
        if capability_tuple is None:
            raise HistoricalWorkflowError(
                "BINDINGS_UNAVAILABLE",
                "Published Case requires exact Algorithm Capability evidence",
            )
        human_reference = HistoricalBenchmarkTrajectory(**request.human_reference)
        alignment = HistoricalBenchmarkAlignmentProfile(**request.alignment_profile)
        counterfactual_runner = HistoricalAISCounterfactualRunner()
        capability_receipt = HistoricalAISCapabilityReceipt.from_catalog(
            counterfactual_runner.runner.capabilities,
            *capability_tuple,
        )
        discovery_profile = HistoricalAISDiscoveryProfile(**case_document.pop("discovery_profile", {}))
        discovery_request = HistoricalAISDiscoveryRequest(**case_document.pop("discovery_request", {}))
        published = case_document.pop("published", True)
        dimension_overrides = case_document.pop("dimension_overrides", {})
        historical_scenario_id = case_document.pop("historical_scenario_id", run_spec.historical_scenario_id)
        if historical_scenario_id != run_spec.historical_scenario_id:
            raise HistoricalWorkflowError(
                "INVALID_REQUEST",
                "Case Historical scenario identity differs from RunSpec",
            )
        build_request = HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=enc_profile,
            discovery_profile=discovery_profile,
            discovery_request=discovery_request,
            historical_scenario_id=historical_scenario_id,
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
        mode=HistoricalWorkflowMode.COUNTERFACTUAL,
        source_path=source,
        dataset_descriptor=dataset.descriptor,
        prepared_run=preparation.prepared_run,
        experiment_runner=counterfactual_runner.runner,
        case=case,
        run_request=run_request,
        human_reference=human_reference,
        alignment_profile=alignment,
        lineage={
            "dataset_digest": dataset.descriptor.descriptor_sha256,
            "case_digest": case.case_digest,
            "runtime_actor_set_digest": case.runtime_actor_set_digest,
            "run_spec_digest": run_request.run_spec_digest,
        },
    )


def _dimension_registry_from_document(document: dict[str, Any]) -> HistoricalAISDimensionRegistry:
    payload = dict(document)
    expected_digest = str(payload.pop("registry_digest", ""))
    records_document = payload.pop("records", None)
    if not isinstance(records_document, list) or not records_document:
        raise HistoricalWorkflowError("DIMENSIONS_UNAVAILABLE", "dimension registry records are required")
    try:
        registry = HistoricalAISDimensionRegistry(
            **payload,
            records=tuple(HistoricalAISDimensionRecord(**dict(record)) for record in records_document),
        )
    except (TypeError, ValueError) as exc:
        raise HistoricalWorkflowError("QUALITY_INCOMPLETE", str(exc)) from exc
    if not expected_digest or expected_digest != registry.digest:
        raise HistoricalWorkflowError("QUALITY_INCOMPLETE", "dimension registry digest mismatch")
    return registry


def _prepare_replay_workflow(
    request: HistoricalWorkflowCreateRequest,
    source: Path,
    dataset: Any,
    run_spec: RunSpec,
) -> _HistoricalWorkflow:
    if request.human_reference is not None or _contains_future_reference(request.replay):
        raise HistoricalWorkflowError("FUTURE_LEAKAGE", "Historical Replay cannot accept Human Reference evidence")
    if request.enc_profile is not None or request.case:
        raise HistoricalWorkflowError("INVALID_REQUEST", "Historical Replay cannot accept Counterfactual Case/ENC fields")
    replay_document = dict(request.replay)
    reference_mmsi = replay_document.pop("reference_mmsi", None)
    if reference_mmsi is None:
        raise HistoricalWorkflowError("INVALID_REQUEST", "Historical Replay requires reference_mmsi")
    if run_spec.algorithm_id != "nominal":
        raise HistoricalWorkflowError("INVALID_REQUEST", "Historical Replay cannot execute a COLAV algorithm")
    try:
        profile = HistoricalAISReconstructionProfile(**replay_document.pop("reconstruction_profile", {}))
        actor_set = HistoricalAISReconstructor().reconstruct(dataset, profile)
        registry_document = replay_document.pop("dimension_registry", None)
        effective_at = replay_document.pop("dimension_effective_at_utc", None)
        if not isinstance(registry_document, dict):
            raise HistoricalWorkflowError(
                "DIMENSIONS_UNAVAILABLE",
                "Historical Replay requires a versioned source-provenanced dimension registry",
            )
        registry = _dimension_registry_from_document(registry_document)
        errors = registry.validation_errors(
            str(effective_at) if effective_at is not None else None, tuple(a.mmsi for a in actor_set.actors)
        )
        if errors:
            raise HistoricalWorkflowError("QUALITY_INCOMPLETE", "; ".join(errors))
        actor_set = apply_dimension_overrides(
            actor_set,
            {record.mmsi: record.to_dict() for record in registry.records},
        )
        actor_set = _reference_first_actor_set(actor_set, int(reference_mmsi))
        replay_request = HistoricalReplayRequest(
            actor_set=actor_set,
            ownship_actor_id=0,
            dt_sim=replay_document.pop("dt_sim", run_spec.dt),
            t_end_s=replay_document.pop("t_end_s", run_spec.t_end),
            scenario_name=str(replay_document.pop("scenario_name", "historical_replay")),
            utm_zone=int(replay_document.pop("utm_zone", 33)),
            mode=HistoricalWorkflowMode.HISTORICAL_REPLAY.value,
            dataset_digest=dataset.descriptor.descriptor_sha256,
            dataset_descriptor_digest=dataset.descriptor.descriptor_sha256,
            runtime_actor_set_digest=actor_set.semantic_digest,
            dimension_registry_digest=registry.digest,
            dimension_effective_at_utc=str(effective_at),
            dimension_record_digests=tuple((record.mmsi, record.source_digest) for record in registry.records),
        )
        if replay_document:
            raise ValueError(f"unsupported Replay fields: {sorted(replay_document)}")
        experiment_runner = ExperimentRunner()
        replay_spec = replace(
            run_spec,
            historical_replay=replay_request.to_dict(),
            t_end=replay_request.t_end_s,
            dt=replay_request.dt_sim,
        )
        prepared_run = experiment_runner.prepare(replay_spec)
        simulator_config = SimulatorConfig(verbose=False)
        simulator_config.visualizer.show_liveplot = False
        simulator_config.visualizer.show_results = False
        replay_preparation = HistoricalReplayFactory.prepare(
            replay_request,
            enc=prepared_run.session.enc,
            simulator=Simulator(config=simulator_config),
            sensor_seed=replay_spec.seeds.sensor,
            terminate_on_collision_or_grounding=replay_spec.terminate_on_collision_or_grounding,
        )
        prepared_run.session = replay_preparation.session
    except HistoricalWorkflowError:
        raise
    except Exception as exc:
        raise HistoricalWorkflowError("INVALID_REQUEST", str(exc)) from exc
    return _HistoricalWorkflow(
        workflow_id=str(uuid.uuid4()),
        mode=HistoricalWorkflowMode.HISTORICAL_REPLAY,
        source_path=source,
        dataset_descriptor=dataset.descriptor,
        prepared_run=prepared_run,
        experiment_runner=experiment_runner,
        replay_request=replay_request,
        lineage={
            "dataset_digest": dataset.descriptor.descriptor_sha256,
            "runtime_actor_set_digest": actor_set.semantic_digest,
            "run_spec_digest": semantic_hash(replay_spec.to_dict()),
        },
    )


def _validate_dataset_identity(request: HistoricalWorkflowCreateRequest, source: Path, descriptor: Any) -> None:
    expected_entries = {item.entry_name: item for item in request.expected_entries}
    observed_entries = {item.entry_name: item for item in descriptor.entry_digests}
    crc_by_name = _entry_crc32(source)
    mismatches: list[str] = []
    if descriptor.archive_sha256 != request.expected_archive_sha256:
        mismatches.append("archive_sha256")
    if descriptor.schema_sha256 != request.expected_schema_sha256:
        mismatches.append("schema_sha256")
    if descriptor.selection_sha256 != request.expected_selection_sha256:
        mismatches.append("selection_sha256")
    if set(observed_entries) != set(expected_entries):
        mismatches.append("selected_entry_names")
    for name in sorted(set(observed_entries).intersection(expected_entries)):
        expected = expected_entries[name]
        observed = observed_entries[name]
        if observed.sha256 != expected.sha256:
            mismatches.append(f"entry:{name}:sha256")
        if observed.uncompressed_bytes != expected.uncompressed_bytes:
            mismatches.append(f"entry:{name}:uncompressed_bytes")
        if crc_by_name.get(name) != expected.crc32:
            mismatches.append(f"entry:{name}:crc32")
    if mismatches:
        raise HistoricalWorkflowError(
            "DATASET_IDENTITY_MISMATCH",
            "Historical Dataset identity differs from expected archive/entry contract",
            {
                "mismatches": mismatches,
                "observed_archive_sha256": descriptor.archive_sha256,
                "observed_schema_sha256": descriptor.schema_sha256,
                "observed_selection_sha256": descriptor.selection_sha256,
            },
        )


def _entry_crc32(source: Path) -> dict[str, int]:
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            return {item.filename: int(item.CRC) for item in archive.infolist() if not item.is_dir()}
    return {source.name: zlib.crc32(source.read_bytes())}


def _reference_first_actor_set(actor_set: HistoricalActorSet, reference_mmsi: int) -> HistoricalActorSet:
    try:
        reference = next(actor for actor in actor_set.actors if actor.mmsi == reference_mmsi)
    except StopIteration as exc:
        raise HistoricalWorkflowError(
            "REFERENCE_VESSEL_UNAVAILABLE",
            f"Historical Replay reference_mmsi {reference_mmsi} is not selected",
        ) from exc
    ordered = (reference, *(actor for actor in actor_set.actors if actor.mmsi != reference_mmsi))
    actors = []
    for actor_id, actor in enumerate(ordered):
        remapped = replace(actor, actor_id=actor_id, actor_digest="")
        object.__setattr__(remapped, "_configured_max_gap_s", actor_set.profile.max_interpolation_gap_s)
        actors.append(remapped)
    return HistoricalActorSet(
        dataset_digest=actor_set.dataset_digest,
        selection_digest=actor_set.selection_digest,
        profile=actor_set.profile,
        time_origin_utc=actor_set.time_origin_utc,
        actors=tuple(actors),
        provider=actor_set.provider,
        attribution=actor_set.attribution,
        coverage_limitations=actor_set.coverage_limitations,
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
    value["navigability_layers"] = tuple(ENCLayerIdentity(**item) for item in value["navigability_layers"])
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
historical_scenario_catalog = HistoricalAISScenarioCatalog()


@router.get("/api/historical/scenarios")
def list_historical_scenarios() -> list[dict[str, Any]]:
    """List independent Historical AIS scene descriptors."""
    return historical_scenario_catalog.list()


@router.get("/api/historical/scenarios/{scenario_id}")
def get_historical_scenario(scenario_id: str) -> dict[str, Any]:
    """Return one bounded Historical AIS descriptor and source readiness."""
    try:
        return historical_scenario_catalog.document(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Historical AIS scenario not found") from exc


@router.post("/api/historical/scenarios/{scenario_id}/workflows")
def create_historical_scenario_workflow(
    scenario_id: str,
    request: HistoricalScenarioWorkflowCreateRequest,
) -> dict[str, Any]:
    """Build and prepare a complete normal Historical Replay/Counterfactual workflow."""
    try:
        descriptor = historical_scenario_catalog.get(scenario_id)
        payload = descriptor.build_workflow_payload(
            request.mode.value,
            run_spec_overrides=request.run_spec,
        )
        qualification_request = (
            descriptor.build_acceptance_request(run_spec_overrides=request.run_spec)
            if request.mode is HistoricalWorkflowMode.COUNTERFACTUAL
            else None
        )
        return historical_workflows.create(
            HistoricalWorkflowCreateRequest(**payload),
            qualification_request=qualification_request,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Historical AIS scenario not found") from exc
    except HistoricalAISScenarioError as exc:
        raise HTTPException(status_code=422, detail=exc.detail()) from exc
    except HistoricalWorkflowError as exc:
        raise HTTPException(status_code=422, detail=exc.detail()) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"status": "INVALID_REQUEST", "reason": str(exc)}) from exc


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
