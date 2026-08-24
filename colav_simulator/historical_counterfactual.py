"""Counterfactual handoff contracts over the normal experiment runner.

This module owns the information boundary around T0.  It creates a derived
runtime actor set whose Reference Vessel contains only history through T0;
post-T0 human reference data is represented, when available, by an external
artifact digest and never enters ``RunSpec``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Any

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.historical_case import HistoricalAISCase
from colav_simulator.historical_serialization import semantic_hash

if TYPE_CHECKING:
    from pathlib import Path

    from colav_simulator.experiment.runner import PreparedRun, RunResult


COUNTERFACTUAL_MODE = "COUNTERFACTUAL"


@dataclass(frozen=True)
class HistoricalAISCounterfactualRunRequest:
    """Immutable request for one normal-simulator Counterfactual Run."""

    case: HistoricalAISCase
    run_spec: RunSpec
    human_reference_artifact_digest: str | None = None
    handoff_tolerance_m: float = 1e-6
    handoff_tolerance_mps: float = 1e-6
    handoff_tolerance_rad: float = 1e-6

    def __post_init__(self) -> None:
        """Validate that the case contains a sealed T0 and safe intent boundary."""
        if not self.case.published:
            raise ValueError("Counterfactual Run requires a Published HistoricalAISCase")
        if self.case.t0_candidate is None or self.case.nominal_intent is None:
            raise ValueError("Counterfactual Run requires frozen T0 and Nominal Intent")
        if not self.case.nominal_intent.strict_pre_t0_only:
            raise ValueError("Counterfactual Run requires strict pre-T0 Nominal Intent")
        if not isinstance(self.run_spec, RunSpec):
            raise TypeError("run_spec must be RunSpec")
        if self.case.algorithm_binding.algorithm_id != self.run_spec.algorithm_id:
            raise ValueError("Counterfactual algorithm differs from frozen Case binding")
        if not self.case.algorithm_binding.bound:
            raise ValueError("Counterfactual Case lacks a verified CapabilityCatalog receipt")
        receipt = self.case.algorithm_binding.capability_receipt
        if receipt is None or receipt.exact_tuple != self.run_spec.capability_tuple:
            raise ValueError("Counterfactual exact tuple differs from frozen CapabilityCatalog receipt")
        if self.case.historical_scenario_id != self.run_spec.historical_scenario_id:
            raise ValueError("Counterfactual Historical scenario identity differs from frozen Case binding")
        if self.case.algorithm_binding.configuration_digest != semantic_hash(self.run_spec.algorithm_config):
            raise ValueError("Counterfactual algorithm configuration differs from frozen Case binding")
        if self.case.evaluation_binding.profile_id != self.run_spec.evaluator_profile_id:
            raise ValueError("Counterfactual Evaluator profile differs from frozen Case binding")
        frozen_digest = self.case.human_reference_binding.artifact_digest
        requested_digest = self.human_reference_artifact_digest
        if requested_digest is not None:
            requested_digest = str(requested_digest).strip() or None
        if requested_digest is not None and requested_digest != frozen_digest:
            raise ValueError("Counterfactual Human Reference differs from frozen Human Reference binding")
        object.__setattr__(self, "human_reference_artifact_digest", frozen_digest)

    @property
    def t0_s(self) -> float:
        return self.case.t0_candidate.time_s  # type: ignore[union-attr]

    @property
    def nominal_intent_digest(self) -> str:
        return self.case.nominal_intent.intent_digest  # type: ignore[union-attr]

    @property
    def run_spec_digest(self) -> str:
        from colav_simulator.experiment.contracts import content_hash  # noqa: PLC0415

        return content_hash(self.to_run_spec().to_dict())

    def to_run_spec(self) -> RunSpec:
        """Return a RunSpec with no post-T0 Reference Vessel samples."""
        actor_set = self.case.runtime_actor_set()
        dt_sim = float(self.run_spec.dt or self.case.reconstruction_profile.time_step_s)
        t_end = self.run_spec.t_end
        if t_end is None:
            t_end = max(actor.last_time_s for actor in actor_set.actors) + dt_sim
        historical_replay = {
            "actor_set": actor_set.to_dict(),
            "ownship_actor_id": 0,
            "dt_sim": dt_sim,
            "t_end_s": float(t_end),
            "scenario_name": "historical_counterfactual",
            "utm_zone": self.case.enc_profile.projection.utm_zone,
            "mode": COUNTERFACTUAL_MODE,
            "counterfactual_t0_s": self.t0_s,
            "nominal_intent": self.case.nominal_intent.to_dict(),
            "case_digest": self.case.runtime_digest,
            "dataset_digest": self.case.dataset_digest,
            "dataset_descriptor_digest": self.case.dataset_descriptor_digest,
            "runtime_actor_set_digest": self.case.runtime_actor_set_digest,
            "case_runtime_digest": self.case.case_runtime_digest,
            "selection_digest": self.case.selection.digest,
            "reconstruction_profile_digest": self.case.reconstruction_digest,
            "enc_profile_digest": self.case.enc_profile_digest,
            "handoff_tolerance_m": self.handoff_tolerance_m,
            "handoff_tolerance_mps": self.handoff_tolerance_mps,
            "handoff_tolerance_rad": self.handoff_tolerance_rad,
        }
        return replace(self.run_spec, historical_replay=historical_replay, t_end=float(t_end))


class HistoricalAISCounterfactualRunStatus(str, Enum):
    """Typed preparation/execution outcome for one Counterfactual Run."""

    COMPLETED = "COMPLETED"
    INVALID_REQUEST = "INVALID_REQUEST"
    CASE_NOT_PUBLISHED = "CASE_NOT_PUBLISHED"
    T0_UNAVAILABLE = "T0_UNAVAILABLE"
    INTENT_NOT_ESTABLISHED = "INTENT_NOT_ESTABLISHED"
    ENC_UNQUALIFIED = "ENC_UNQUALIFIED"
    REFERENCE_STATE_MISMATCH = "REFERENCE_STATE_MISMATCH"
    ALGORITHM_UNAVAILABLE = "ALGORITHM_UNAVAILABLE"
    HANDOFF_FAILED = "HANDOFF_FAILED"
    RUN_FAILED = "RUN_FAILED"


@dataclass(frozen=True)
class HistoricalAISCounterfactualPreparation:
    """Prepared normal ExperimentRunner session at the T0 handoff boundary."""

    request: HistoricalAISCounterfactualRunRequest
    prepared_run: PreparedRun

    @property
    def session(self) -> Any:
        return self.prepared_run.session

    @property
    def manifest(self) -> Any:
        return self.prepared_run.manifest

    @property
    def run_spec_digest(self) -> str:
        return self.request.run_spec_digest


@dataclass(frozen=True)
class HistoricalAISCounterfactualRunOutcome:
    """Typed result retaining normal RunResult and Human Reference availability."""

    status: HistoricalAISCounterfactualRunStatus
    result: RunResult | None = None
    message: str = ""
    human_reference_available: bool = False

    @property
    def success(self) -> bool:
        return self.status is HistoricalAISCounterfactualRunStatus.COMPLETED

    @property
    def failure_code(self) -> str | None:
        return None if self.success else self.status.value

    @property
    def human_reference_status(self) -> str:
        return "AVAILABLE" if self.human_reference_available else "NOT_AVAILABLE"


class HistoricalAISCounterfactualRunner:
    """Run a Published HistoricalAISCase through the existing ExperimentRunner."""

    def __init__(self, runner: Any | None = None, project_root: Path | None = None) -> None:
        if runner is None:
            from colav_simulator.experiment.runner import ExperimentRunner  # noqa: PLC0415

            runner = ExperimentRunner(project_root)
        self.runner = runner

    def prepare(self, request: HistoricalAISCounterfactualRunRequest) -> HistoricalAISCounterfactualPreparation:
        """Prepare normal Session/Simulator state without executing a run."""
        from colav_simulator.experiment.runner import PreparedRun  # noqa: PLC0415

        if not isinstance(request, HistoricalAISCounterfactualRunRequest):
            raise TypeError("request must be HistoricalAISCounterfactualRunRequest")
        prepared = self.runner.prepare(request.to_run_spec())
        if not isinstance(prepared, PreparedRun):
            raise TypeError("ExperimentRunner returned an invalid PreparedRun")
        return HistoricalAISCounterfactualPreparation(request=request, prepared_run=prepared)

    def run(self, request: HistoricalAISCounterfactualRunRequest) -> HistoricalAISCounterfactualRunOutcome:
        """Execute and finalize one normal simulator Counterfactual Run."""
        try:
            prepared = self.prepare(request)
        except Exception as exc:
            return HistoricalAISCounterfactualRunOutcome(
                status=_handoff_status(exc),
                message=str(exc),
            )
        try:
            prepared.session.run_to_completion()
            result = self.runner.finalize(prepared.prepared_run)
        except Exception as exc:
            try:
                prepared.prepared_run.artifact_sink.close(timeout_s=2.0)
                self.runner.persist_failure(
                    prepared.manifest,
                    prepared.prepared_run.writer,
                    exc,
                    prepared.session.frames,
                    prepared.session.events,
                )
            except Exception:
                pass
            return HistoricalAISCounterfactualRunOutcome(
                status=HistoricalAISCounterfactualRunStatus.RUN_FAILED,
                message=str(exc),
                human_reference_available=request.human_reference_artifact_digest is not None,
            )
        result.manifest.historical_reference_artifact_digest = request.human_reference_artifact_digest
        result.writer.write_manifest(result.manifest)
        return HistoricalAISCounterfactualRunOutcome(
            status=HistoricalAISCounterfactualRunStatus.COMPLETED,
            result=result,
            human_reference_available=request.human_reference_artifact_digest is not None,
        )


def _handoff_status(error: Exception) -> HistoricalAISCounterfactualRunStatus:
    message = str(error)
    if isinstance(error, TypeError):
        return HistoricalAISCounterfactualRunStatus.INVALID_REQUEST
    if "REFERENCE_STATE_MISMATCH" in message:
        return HistoricalAISCounterfactualRunStatus.REFERENCE_STATE_MISMATCH
    if "Published" in message:
        return HistoricalAISCounterfactualRunStatus.CASE_NOT_PUBLISHED
    if "Nominal Intent" in message or "intent" in message.lower():
        return HistoricalAISCounterfactualRunStatus.INTENT_NOT_ESTABLISHED
    if "T0" in message or "t0" in message:
        return HistoricalAISCounterfactualRunStatus.T0_UNAVAILABLE
    if "algorithm" in message.lower() or "fallback" in message.lower():
        return HistoricalAISCounterfactualRunStatus.ALGORITHM_UNAVAILABLE
    if "ENC" in message or "enc" in message:
        return HistoricalAISCounterfactualRunStatus.ENC_UNQUALIFIED
    return HistoricalAISCounterfactualRunStatus.HANDOFF_FAILED


__all__ = [
    "COUNTERFACTUAL_MODE",
    "HistoricalAISCounterfactualPreparation",
    "HistoricalAISCounterfactualRunRequest",
    "HistoricalAISCounterfactualRunOutcome",
    "HistoricalAISCounterfactualRunStatus",
    "HistoricalAISCounterfactualRunner",
]
