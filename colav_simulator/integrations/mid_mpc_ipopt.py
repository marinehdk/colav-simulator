"""Colav-native lifecycle facade for the parity-complete Mid-MPC IPOPT core."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum

import numpy as np

from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    CustomMPCAdapter,
    ExecutionProfile,
    FactoryContext,
    MPCSolution,
    PlannerInput,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, FailureSource, PlanStatus
from colav_simulator.core.colav.encounter_lifecycle import (
    CommitmentPhase,
    DecisionSnapshot,
    EncounterCycle,
    EncounterKind,
    EncounterLifecycle,
    LifecycleError,
    LifecycleFailure,
    Maneuverability,
    ObservationHealth,
    OwnshipObservation,
    OwnshipRole,
    PlannerOddProfile,
    RiskPhase,
    TargetDecision,
    TargetObservation,
)
from colav_simulator.core.colav.horizon_encounter_plan import horizon_encounter_plan_document
from colav_simulator.core.colav.mid_mpc import (
    MidMpcConfig,
    MidMpcIpoptSolver,
    MidMpcPrimalWarmStart,
    MidMpcResult,
    MidMpcStatus,
)
from colav_simulator.core.colav.mid_mpc_acceptance import (
    AcceptanceMode,
    AcceptanceProfile,
    AcceptanceRequest,
    AcceptanceResult,
    AuthorityEvidence,
    AuthorityTarget,
    CandidateEvidence,
    ExecutionEvidence,
    ExecutionTarget,
    MidMpcPlanAcceptance,
    NumericalEvidence,
    PlanAcceptancePolicy,
    PlantCapabilityEvidence,
    PriorEvidence,
)
from colav_simulator.core.colav.mid_mpc_assembler import (
    AssemblyFailure,
    AssemblyProfile,
    AssemblyRequest,
    AssemblySuccess,
    CapabilitySnapshot,
    MidMpcAssemblyConfig,
    MidMpcProblemAssembler,
    RouteReference,
    TargetPrediction,
    problem_hash_document,
)
from colav_simulator.core.colav.prediction_evidence import (
    EvidenceEnvelope,
    EvidenceTrackKey,
    OptimizationIntervalReference,
    OwnshipPrediction,
    PredictionEvidenceRecord,
    PredictionGrid,
    PredictionPhaseEvidence,
    PredictionPurpose,
    TargetPredictionEvidence,
)
from colav_simulator.core.colav.rolling_plan import (
    RollingPlan,
    RollingPlanAssessment,
    RollingPlanIdentity,
    RollingPlanReference,
)
from colav_simulator.core.colav.threat_assessment import (
    OwnshipThreatPrediction,
    PredictionBasis,
    ThreatManagementSnapshot,
)
from colav_simulator.core.colav.threat_assessment import (
    ThreatPrediction as ThreatTargetPrediction,
)
from colav_simulator.core.colav.threat_management import (
    AcceptedPlanReceipt,
    ThreatManagementCoordinator,
)
from colav_simulator.core.guidances import LOSGuidance
from colav_simulator.core.tracking.trackers import TrackKey

__version__ = "2.0.0"
_TOTAL_DEADLINE_S = 20.0
_ACCEPTANCE_RESERVATION_S = 0.25
_WARM_START_ELIGIBLE_TUPLES = frozenset({"single-encounter:viknes:flsc"})
_ACCEPTANCE_P99_MS = 35.046
_ACCEPTANCE_CALIBRATION_ID = "m3-macos26-python3.11-20260812-1000x-0-1-16"
_CRITICAL_TAIL_P99_MS = 42.597
_CRITICAL_TAIL_CALIBRATION_ID = "m3-macos26-python3.11-20260813-l4-evidence-1000x-0-1-16-fresh-hold-rejected"


@dataclass(frozen=True)
class _FacadeConfig:
    assembly: MidMpcAssemblyConfig
    profile: PlannerOddProfile
    total_deadline_s: float
    acceptance_reservation_s: float
    scenario_id: str
    algorithm_seed: int
    tracker_id: str
    prewarm_targets: int | None = None


class _MidMpcFacade:
    def __init__(
        self,
        config: _FacadeConfig,
        *,
        threat_management_coordinator: ThreatManagementCoordinator,
        artifact_sink: Callable[[object], object] | None = None,
    ) -> None:
        self._config = config
        self._los = LOSGuidance()
        core_config = MidMpcConfig(
            horizon_steps=config.assembly.horizon_steps,
            dt_s=config.assembly.horizon_dt_s,
            strict_slack_bounds=True,
            max_wall_time_s=config.total_deadline_s - config.acceptance_reservation_s,
        )
        self._solver = MidMpcIpoptSolver(core_config)
        if config.prewarm_targets and config.prewarm_targets > 1:
            # One graph at the scenario's full capacity serves the first
            # multiship cycle and every smaller track count afterwards; the
            # capacity-one prewarm is subsumed by it.
            self._solver.prewarm_capacity(config.prewarm_targets)
        else:
            self._solver.prewarm()
        self._assembler = MidMpcProblemAssembler()
        self._acceptance = MidMpcPlanAcceptance()
        if not isinstance(threat_management_coordinator, ThreatManagementCoordinator):
            raise TypeError("threat_management_coordinator must be ThreatManagementCoordinator")
        self._threat_management_coordinator = threat_management_coordinator
        self._last_guidance_time_s: float | None = None
        self._epoch_number = 1
        self._cycle_epoch = f"mid-mpc-{self._epoch_number}"
        self._cycle_sequence = 0
        self._last_cycle_time_s: float | None = None
        self._artifact_sink = artifact_sink
        self._accepted_primal: tuple[float, np.ndarray, np.ndarray, str, str] | None = None
        self._accepted_request: AcceptanceRequest | None = None
        self._accepted_trajectory: np.ndarray | None = None
        self._accepted_acceptance_hash: str | None = None
        self._rolling_plan = RollingPlan()
        self._unresolved_streak = 0
        self._unresolved_streak_token: str | None = None

    def reset(self) -> None:
        self._los.reset()
        self._epoch_number += 1
        self._cycle_epoch = f"mid-mpc-{self._epoch_number}"
        self._threat_management_coordinator.reset(
            epoch=self._cycle_epoch,
            reason="adapter_reset",
            sim_time_s=0.0 if self._last_cycle_time_s is None else self._last_cycle_time_s,
        )
        self._last_guidance_time_s = None
        self._cycle_sequence = 0
        self._last_cycle_time_s = None
        self._accepted_primal = None
        self._accepted_request = None
        self._accepted_trajectory = None
        self._accepted_acceptance_hash = None
        self._rolling_plan.reset()

    def validate_hold(
        self,
        planner_input: PlannerInput,
        solution: MPCSolution,
        elapsed_s: float,
    ) -> dict[str, object]:
        context = solution.algorithm_details.get("acceptance_context")
        acceptance = solution.algorithm_details.get("plan_acceptance")
        receipt = solution.algorithm_details.get("accepted_plan_receipt")
        if (
            not isinstance(context, dict)
            or not isinstance(acceptance, dict)
            or not isinstance(receipt, dict)
            or acceptance.get("accepted") is not True
            or self._accepted_request is None
        ):
            raise _hold_rejection("HOLD_RECEIPT_MISSING", "held plan has no accepted L4 receipt")
        if planner_input.sim_time_s > float(receipt.get("valid_until_s", -math.inf)) + 1.0e-9:
            raise _hold_rejection("HOLD_RECEIPT_EXPIRED", "held plan receipt expired on its original timeline")
        if _document_hash(asdict(self._accepted_request.policy)) != context.get("policy_hash"):
            raise _hold_rejection("HOLD_POLICY_CHANGED", "held plan acceptance policy changed")
        current_keys = sorted((track.target_id, track.generation) for track in planner_input.tracks)
        expected_keys = sorted(tuple(item) for item in context.get("target_keys", []))
        if current_keys != expected_keys:
            raise _hold_rejection("HOLD_TARGET_SET_CHANGED", "held target identity set changed")
        if _planner_route_hash(planner_input) != context.get("route_hash"):
            raise _hold_rejection("HOLD_ROUTE_CHANGED", "held route or speed plan changed")
        capability = _active_capability(planner_input, self._config)
        if (
            capability.exact_tuple != context.get("capability_tuple")
            or _capability_contract_hash(capability) != context.get("capability_hash")
            or capability.limitations
            or self._config.scenario_id != context.get("scenario_id")
            or self._config.algorithm_seed != context.get("algorithm_seed")
            or self._config.tracker_id != context.get("tracker_id")
        ):
            raise _hold_rejection("HOLD_CAPABILITY_CHANGED", "active plant/controller capability changed")
        prediction_error_m, velocity_error_mps = _held_target_prediction_error(
            planner_input,
            solution,
            elapsed_s=elapsed_s,
        )
        if prediction_error_m > 1.0 or velocity_error_mps > 0.1:
            raise _hold_rejection(
                "HOLD_TARGET_PREDICTION_CHANGED",
                "held target prediction no longer matches current tracker evidence",
            )
        expected = _trajectory_state_at(solution.predicted_trajectory, solution.horizon_dt_s, elapsed_s)
        position_error_m = float(np.linalg.norm(planner_input.ownship_state[:2] - expected[:2]))
        heading_delta = float(planner_input.ownship_state[2] - expected[2])
        heading_error_rad = abs(math.atan2(math.sin(heading_delta), math.cos(heading_delta)))
        speed_error_mps = abs(float(np.hypot(*planner_input.ownship_state[3:5]) - np.hypot(*expected[3:5])))
        if position_error_m > 50.0:
            raise _hold_rejection("OWN_STATE_DEVIATION", "held plan position deviation exceeds 50 m")
        validation_window_s = max(0.0, elapsed_s) + self._config.assembly.horizon_dt_s
        capability_heading_allowance = capability.rot_max_rad_s * validation_window_s
        capability_speed_allowance = max(capability.accel_max_mps2, capability.decel_max_mps2) * validation_window_s
        if (
            heading_error_rad > capability_heading_allowance + 1.0e-6
            or speed_error_mps > capability_speed_allowance + 1.0e-6
        ):
            raise _hold_rejection("OWN_STATE_DEVIATION", "held plan motion-state deviation exceeds active-prefix limit")
        remaining_s = max(0.0, self._config.assembly.decision_period_s - elapsed_s)
        clearance = _held_prefix_clearance(
            planner_input,
            solution,
            elapsed_s=elapsed_s,
            remaining_s=remaining_s,
        )
        if clearance < self._config.assembly.cpa_hard_m:
            raise _hold_rejection("HOLD_SAFETY_REJECTED", "held plan active prefix violates swept hull clearance")
        held_request = _held_acceptance_request(
            self._accepted_request,
            planner_input,
            solution.predicted_trajectory,
            elapsed_s=elapsed_s,
            capability=capability,
            previous_acceptance_hash=str(acceptance["acceptance_hash"]),
        )
        held_result = self._acceptance.evaluate(held_request)
        if not held_result.accepted:
            failure_codes = [
                finding.code
                for finding in held_result.findings
                if finding.mandatory and finding.outcome.value in {"FAIL", "UNKNOWN"}
            ]
            raise _hold_rejection(
                "HOLD_L4_REJECTED",
                f"held plan failed L4 revalidation: {', '.join(failure_codes)}",
            )
        return {
            "accepted": True,
            "mode": AcceptanceMode.HELD_ACCEPTED_PLAN.value,
            "checked_at_s": planner_input.sim_time_s,
            "elapsed_s": elapsed_s,
            "previous_acceptance_hash": acceptance["acceptance_hash"],
            "position_error_m": position_error_m,
            "heading_error_rad": heading_error_rad,
            "speed_error_mps": speed_error_mps,
            "target_prediction_error_m": prediction_error_m,
            "target_velocity_error_mps": velocity_error_mps,
            "minimum_prefix_hull_clearance_m": clearance,
            "acceptance_hash": held_result.acceptance_hash,
            "layers": [asdict(layer) for layer in held_result.layers],
        }

    def solve(self, planner_input: PlannerInput) -> MPCSolution:  # noqa: C901, PLR0912, PLR0915
        if len(planner_input.tracks) > self._config.assembly.max_targets:
            self._accepted_primal = None
            self._accepted_request = None
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Mid-MPC L4 CAPACITY_EXCEEDED before solver execution",
                source=FailureSource.ALGORITHM,
                details={
                    "failure_code": "CAPACITY_EXCEEDED",
                    "failure_owner": "plan_acceptance",
                    "target_count": len(planner_input.tracks),
                    "capacity": self._config.assembly.max_targets,
                },
            )
        ownship = planner_input.ownship_state
        guidance_dt_s = (
            planner_input.dt_sim_s
            if self._last_guidance_time_s is None
            else planner_input.sim_time_s - self._last_guidance_time_s
        )
        reference = self._los.compute_references(
            planner_input.waypoints_enu_m,
            planner_input.speed_plan_mps,
            None,
            ownship,
            guidance_dt_s,
        )
        self._last_guidance_time_s = planner_input.sim_time_s
        route_bearing = _unwrap_near(float(reference[2, 0]), float(ownship[2]))
        canonical_snapshot = self._canonical_snapshot_at(planner_input)
        if canonical_snapshot is not None:
            self._cycle_epoch = canonical_snapshot.epoch
            self._cycle_sequence = canonical_snapshot.sequence
        elif self._last_cycle_time_s is not None and planner_input.sim_time_s != self._last_cycle_time_s:
            self._cycle_sequence += 1
        self._last_cycle_time_s = planner_input.sim_time_s
        route_anchor, mission_leg_bearing = _nearest_route_projection(
            planner_input.waypoints_enu_m,
            ownship[:2],
        )
        capability = _active_capability(planner_input, self._config)
        try:
            cycle = self._encounter_cycle(
                planner_input,
                route_bearing_rad=route_bearing,
                planned_speed_mps=float(reference[3, 0]),
            )
            for target in cycle.targets:
                if target.health is ObservationHealth.UNUSABLE:
                    raise LifecycleError(
                        LifecycleFailure.UNUSABLE_OBSERVATION,
                        f"target {target.key} observation is unusable",
                    )
                if target.age_s > cycle.profile.usable_age_s:
                    raise LifecycleError(
                        LifecycleFailure.UNUSABLE_OBSERVATION,
                        f"target {target.key} observation is stale",
                    )
            threat_snapshot = canonical_snapshot
            if threat_snapshot is None:
                threat_snapshot = self._threat_management_coordinator.cycle(
                    cycle,
                    profile=self._threat_management_coordinator.domain_profile,
                    predictions=self._threat_target_predictions(planner_input),
                    baseline_prediction=self._threat_baseline_prediction(planner_input),
                )
            snapshot = threat_snapshot.lifecycle_snapshot
            if not isinstance(snapshot, DecisionSnapshot):
                raise RuntimeError("Threat Management Coordinator did not publish a Lifecycle snapshot")
            rolling_identity, rolling_reference, prior_plan_safe, prior_revalidation_codes = self._rolling_reference(
                planner_input, snapshot, capability
            )
            assembly = self._assembler.assemble(
                AssemblyRequest(
                    planner_input=planner_input,
                    snapshot=snapshot,
                    cycle_input_hash=snapshot.input_hash,
                    lifecycle_profile_hash=cycle.profile.hash,
                    route=RouteReference(
                        anchor_ne_m=route_anchor,
                        bearing_rad=route_bearing,
                        mission_leg_bearing_rad=mission_leg_bearing,
                        planned_speed_mps=float(reference[3, 0]),
                    ),
                    capability=CapabilitySnapshot(
                        heading_window_rad=self._config.assembly.heading_window_rad,
                        speed_bounds_mps=self._config.assembly.speed_bounds_mps,
                        rot_max_rad_s=self._config.assembly.rot_max_rad_s,
                        decel_max_mps2=self._config.assembly.decel_max_mps2,
                    ),
                    config=self._config.assembly,
                    rolling_plan=rolling_reference,
                    profile=AssemblyProfile.COLAV_STRICT,
                )
            )
        except LifecycleError as exc:
            self._accepted_primal = None
            self._accepted_request = None
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"Mid-MPC lifecycle {exc.failure.value}: {exc}",
                source=FailureSource.ALGORITHM,
                details={"failure_code": exc.failure.value, "failure_owner": "lifecycle"},
            ) from exc
        if isinstance(assembly, AssemblyFailure):
            self._accepted_primal = None
            self._accepted_request = None
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"Mid-MPC assembly {assembly.code.value}: {assembly.message}",
                source=FailureSource.ALGORITHM,
                details={
                    "failure_code": assembly.code.value,
                    "failure_owner": assembly.owner.lower(),
                    "recoverability": assembly.recoverability,
                    "identity": assembly.identity,
                },
            )
        warm_semantic_token = _warm_semantic_token(snapshot, assembly)
        warm_start = self._primal_warm_start(planner_input, capability, warm_semantic_token)
        try:
            retry_budget_s = 2.0 if self._unresolved_streak >= 1 else None
            result = self._solver.solve(
                assembly.problem,
                primal_warm_start=warm_start,
                wall_time_s=retry_budget_s,
            )
        except Exception:
            self._accepted_primal = None
            self._accepted_request = None
            raise
        predicted, controls = _native_trajectories(
            result.trajectory,
            ownship,
            self._config.assembly.horizon_dt_s,
        )
        status, feasible = _plan_status(result.status, result.max_constraint_violation)
        if status not in {PlanStatus.SUCCESS, PlanStatus.TIMEOUT_FEASIBLE}:
            if warm_semantic_token == self._unresolved_streak_token:
                self._unresolved_streak += 1
            else:
                self._unresolved_streak = 1
                self._unresolved_streak_token = warm_semantic_token
            raise ColavExecutionError(
                status,
                f"Mid-MPC optimizer returned {status.value} without a feasible candidate",
                source=FailureSource.ALGORITHM,
                details={
                    "failure_code": "OPTIMIZER_UNRESOLVED",
                    "failure_owner": "solver",
                    "ipopt_return_status": result.ipopt_return_status,
                    "max_constraint_violation": result.max_constraint_violation,
                    "preserve_accepted_plan": True,
                    "revision_reason": "OPTIMIZER_UNRESOLVED",
                },
            )
        continuous_cpa = result.continuous_cpa_min_m if math.isfinite(result.continuous_cpa_min_m) else None
        replay_artifact = _replay_artifact_document(assembly, result)
        if _document_hash(replay_artifact["problem_stage"]) != assembly.problem_hash:
            raise RuntimeError("Mid-MPC problem evidence does not match assembled problem hash")
        prepared_stage = {
            "schema_version": "colav.mid_mpc.prepared@1",
            "parent_problem_hash": assembly.problem_hash,
            "prepared": replay_artifact["solver"]["prepared"],
        }
        prepared_hash = _document_hash(prepared_stage)
        solver_stage = {
            "schema_version": "colav.mid_mpc.solver@1",
            "parent_prepared_hash": prepared_hash,
            "solver": replay_artifact["solver"],
        }
        solver_hash = _document_hash(solver_stage)
        acceptance_request = _acceptance_request(
            planner_input=planner_input,
            snapshot=snapshot,
            assembly=assembly,
            result=result,
            predicted=predicted,
            capability=capability,
            hard_hull_clearance_m=self._config.assembly.cpa_hard_m,
            stand_on_course_tolerance_rad=self._config.assembly.stand_on_course_tolerance_rad,
            prepared_hash=prepared_hash,
            solver_hash=solver_hash,
            total_deadline_s=self._config.total_deadline_s,
            scenario_id=self._config.scenario_id,
            algorithm_seed=self._config.algorithm_seed,
            tracker_id=self._config.tracker_id,
        )
        acceptance_started = time.perf_counter()
        acceptance_result = self._acceptance.evaluate(acceptance_request)
        acceptance_elapsed_ms = (time.perf_counter() - acceptance_started) * 1_000.0
        acceptance_inline = _acceptance_inline_projection(
            acceptance_result,
            limit_bytes=acceptance_request.policy.inline_limit_bytes,
        )
        acceptance_stage = {
            "schema_version": "colav.mid_mpc.acceptance@1",
            "parent_solver_hash": solver_hash,
            "acceptance": acceptance_result.to_dict(),
        }
        acceptance_hash = _document_hash(acceptance_stage)
        replay_artifact["prepared_stage"] = prepared_stage
        replay_artifact["solver_stage"] = solver_stage
        replay_artifact["acceptance_stage"] = acceptance_stage
        replay_artifact["acceptance"] = acceptance_result.to_dict()
        prediction_evidence = _prediction_evidence(
            predicted=predicted,
            controls=controls,
            assembly=assembly,
            acceptance_request=acceptance_request,
            acceptance_result=acceptance_result,
            result=result,
            candidate_hash=solver_hash,
            acceptance_hash=acceptance_hash,
            planner_input=planner_input,
            snapshot=snapshot,
        )
        replay_artifact["prediction_evidence"] = prediction_evidence.to_dict()
        replay_artifact["prediction_evidence_hash"] = prediction_evidence.semantic_hash
        if not acceptance_result.accepted:
            self._accepted_primal = None
            self._accepted_request = None
            failure_codes = [
                finding.code
                for finding in acceptance_result.findings
                if finding.outcome.value in {"FAIL", "UNKNOWN"} and finding.mandatory
            ]
            replay_artifact["hashes"] = {
                "request": assembly.request_hash,
                "problem": assembly.problem_hash,
                "prepared": prepared_hash,
                "solver": solver_hash,
                "acceptance": acceptance_hash,
            }
            replay_artifact["hash_chain"] = {
                "request": {"hash": assembly.request_hash, "parent_hash": None},
                "problem": {"hash": assembly.problem_hash, "parent_hash": assembly.request_hash},
                "prepared": {"hash": prepared_hash, "parent_hash": assembly.problem_hash},
                "solver": {"hash": solver_hash, "parent_hash": prepared_hash},
                "acceptance": {"hash": acceptance_hash, "parent_hash": solver_hash},
            }
            artifact_reference: object = {"status": "NOT_CONFIGURED"}
            if self._artifact_sink is not None:
                try:
                    artifact_reference = self._artifact_sink(replay_artifact)
                except Exception as exc:  # evidence failure must not alter control authority
                    artifact_reference = {
                        "status": "INCOMPLETE",
                        "error_type": type(exc).__name__,
                    }
            raise ColavExecutionError(
                PlanStatus.INFEASIBLE,
                f"Mid-MPC L4 plan acceptance rejected the candidate: {', '.join(failure_codes)}",
                source=FailureSource.ALGORITHM,
                details={
                    "failure_code": "L4_PLAN_REJECTED",
                    "failure_owner": "plan_acceptance",
                    "plan_acceptance": acceptance_inline,
                    "artifact": artifact_reference,
                    "preserve_accepted_plan": True,
                    "revision_reason": "L4_PLAN_REJECTED",
                },
                evidence=EvidenceEnvelope(prediction_evidence),
            )
        rolling_assessment = self._rolling_plan.assess(
            rolling_reference,
            north_m=predicted[0],
            east_m=predicted[1],
            course_rad=predicted[2],
            passing_side=snapshot.directive.passing_side.value,
            recovery_at_s=_recovery_at_s(acceptance_request),
            prior_plan_safe=prior_plan_safe,
        )
        replay_artifact["rolling_plan"] = _rolling_plan_document(
            rolling_reference,
            rolling_assessment,
            prior_revalidation_codes=prior_revalidation_codes,
        )
        if not rolling_assessment.accepted:
            raise ColavExecutionError(
                PlanStatus.INFEASIBLE,
                f"Mid-MPC Rolling Plan rejected candidate revision: {rolling_assessment.revision_reason.value}",
                source=FailureSource.ALGORITHM,
                details={
                    "failure_code": "ROLLING_PLAN_REVISION_REJECTED",
                    "failure_owner": "rolling_plan",
                    "revision_reason": rolling_assessment.revision_reason.value,
                    "preserve_accepted_plan": True,
                    "rolling_plan": replay_artifact["rolling_plan"],
                },
                evidence=EvidenceEnvelope(prediction_evidence),
            )
        self._unresolved_streak = 0
        self._unresolved_streak_token = None
        warm_start_eligible = capability.exact_tuple in _WARM_START_ELIGIBLE_TUPLES
        accepted_prediction = OwnshipThreatPrediction.from_prediction_evidence(
            prediction_evidence,
            reference_time_s=planner_input.sim_time_s,
            target_keys=tuple(TrackKey(track.target_id, track.generation or 1) for track in planner_input.tracks),
        )
        receipt = {
            "schema_version": "colav.mid_mpc.receipt@1",
            "parent_acceptance_hash": acceptance_hash,
            "semantic_acceptance_hash": acceptance_result.acceptance_hash,
            "profile": acceptance_result.profile.value,
            "epoch": snapshot.epoch,
            "sequence": snapshot.sequence,
            "accepted_at_s": planner_input.sim_time_s,
            "valid_until_s": planner_input.sim_time_s + self._config.assembly.decision_period_s,
            "capability_tuple": capability.exact_tuple,
            "capability_hash": _capability_contract_hash(capability),
            "policy_hash": _document_hash(asdict(acceptance_request.policy)),
            "scenario_id": self._config.scenario_id,
            "algorithm_seed": self._config.algorithm_seed,
            "tracker_id": self._config.tracker_id,
            "accepted_prediction": accepted_prediction.to_dict(),
            "prediction_hash": accepted_prediction.semantic_hash,
            "evidence_semantic_hash": prediction_evidence.semantic_hash,
            "domain_profile_hash": self._threat_management_coordinator.domain_profile.profile_hash,
            "target_keys": [
                {"target_id": track.target_id, "generation": track.generation} for track in planner_input.tracks
            ],
            "warm_start_eligible": warm_start_eligible,
            "dual_warm_start": False,
        }
        issued_receipt = AcceptedPlanReceipt.issue(
            accepted_sequence=snapshot.sequence,
            accepted_at_s=planner_input.sim_time_s,
            valid_until_s=planner_input.sim_time_s + self._config.assembly.decision_period_s,
            accepted_prediction=accepted_prediction,
            target_keys=tuple(
                TrackKey(track.target_id, track.generation or 1)
                for track in planner_input.tracks
            ),
            prediction_hash=accepted_prediction.semantic_hash,
            acceptance_hash=acceptance_result.acceptance_hash,
            domain_profile_hash=self._threat_management_coordinator.domain_profile.profile_hash,
            evidence_semantic_hash=prediction_evidence.semantic_hash,
        )
        receipt_hash = issued_receipt.receipt_hash
        receipt_stage = issued_receipt.canonical_payload
        accepted_plan_receipt = {**receipt, "receipt_hash": receipt_hash}
        n = self._config.assembly.horizon_steps
        next_accepted_primal = (
            (
                planner_input.sim_time_s,
                result.raw_x[:n].copy(),
                result.raw_x[n : 2 * n].copy(),
                capability.exact_tuple,
                warm_semantic_token,
            )
            if warm_start_eligible
            else None
        )
        replay_artifact["receipt_stage"] = receipt_stage
        replay_artifact["accepted_plan_receipt"] = accepted_plan_receipt
        replay_artifact["hashes"] = {
            "request": assembly.request_hash,
            "problem": assembly.problem_hash,
            "prepared": prepared_hash,
            "solver": solver_hash,
            "acceptance": acceptance_hash,
            "receipt": receipt_hash,
        }
        replay_artifact["hash_chain"] = {
            "request": {"hash": assembly.request_hash, "parent_hash": None},
            "problem": {"hash": assembly.problem_hash, "parent_hash": assembly.request_hash},
            "prepared": {"hash": prepared_hash, "parent_hash": assembly.problem_hash},
            "solver": {"hash": solver_hash, "parent_hash": prepared_hash},
            "acceptance": {"hash": acceptance_hash, "parent_hash": solver_hash},
            "receipt": {"hash": receipt_hash, "parent_hash": acceptance_hash},
        }
        artifact_reference: dict[str, object] = {"status": "NOT_CONFIGURED"}

        def persist_after_commit() -> dict[str, object]:
            self._accepted_primal = next_accepted_primal
            self._accepted_request = acceptance_request
            self._accepted_trajectory = predicted.copy()
            self._accepted_acceptance_hash = acceptance_result.acceptance_hash
            self._threat_management_coordinator.publish_accepted_plan(
                AcceptedPlanReceipt.from_mapping(accepted_plan_receipt)
            )
            self._rolling_plan.commit(
                accepted_at_s=planner_input.sim_time_s,
                dt_s=self._config.assembly.horizon_dt_s,
                north_m=predicted[0],
                east_m=predicted[1],
                course_rad=predicted[2],
                speed_mps=np.hypot(predicted[3], predicted[4]),
                identity=rolling_identity,
                passing_side=snapshot.directive.passing_side.value,
                recovery_at_s=_recovery_at_s(acceptance_request),
            )
            if self._artifact_sink is None:
                return artifact_reference
            try:
                artifact_reference.clear()
                artifact_reference.update(self._artifact_sink(replay_artifact))
            except Exception as exc:  # evidence failure must not alter control authority
                artifact_reference.clear()
                artifact_reference.update(
                    {
                        "status": "INCOMPLETE",
                        "error_type": type(exc).__name__,
                    }
                )
            return artifact_reference

        if self._artifact_sink is not None:
            artifact_reference["status"] = "PENDING_COMMIT"
        constraints = {
            "row_layout": result.row_layout.to_dict(),
            "active_row_indices": list(result.active_row_indices),
            "tight_row_indices": list(result.tight_row_indices),
            "max_constraint_violation": result.max_constraint_violation,
            "max_decision_bound_violation": result.max_decision_bound_violation,
            "cpa_slack": result.cpa_slack,
            "direction_slack": max(0.0, result.raw_dir_slack),
            "continuous_cpa_min_m": continuous_cpa,
            "continuous_cpa_violated": result.continuous_cpa_violated,
            "row_schedule": asdict(assembly.problem.row_schedule),
            "configured_hull_clearance_m": self._config.assembly.cpa_hard_m,
            "effective_node_cpa_hard_m": assembly.effective_cpa_hard_m,
            "slack_bounds_mode": "fixed_zero",
            "slack_bounds": {
                "cpa": [float(result.prepared.lbx[-2]), float(result.prepared.ubx[-2])],
                "direction": [float(result.prepared.lbx[-1]), float(result.prepared.ubx[-1])],
            },
        }
        committed = any(
            decision.commitment is CommitmentPhase.COMMITTED and decision.risk in {RiskPhase.ACTIVE, RiskPhase.PAST_CLEAR}
            for decision in snapshot.targets
        )
        threat_snapshot_document = threat_snapshot.to_dict()
        details = {
            "formulation": "mass-l3-mid-mpc-ipopt-frozen",
            "solver_backend": "ipopt",
            "ipopt_return_status": result.ipopt_return_status,
            "normalized_solver_status": result.status.value,
            "native_solver_status": result.native_status.value,
            "solver_elapsed_ms": result.elapsed_ms,
            "optimizer_total_elapsed_ms": result.elapsed_ms,
            "graph_build_elapsed_ms": result.graph_build_elapsed_ms,
            "solver_preparation_elapsed_ms": result.preparation_elapsed_ms,
            "ipopt_elapsed_ms": result.ipopt_elapsed_ms,
            "ipopt_iterations": result.ipopt_iterations,
            "graph_cache_hit": result.graph_cache_hit,
            "total_deadline_s": self._config.total_deadline_s,
            "strict_total_deadline": True,
            "solver_cutoff_s": self._config.total_deadline_s - self._config.acceptance_reservation_s,
            "acceptance_reservation_s": self._config.acceptance_reservation_s,
            "acceptance_elapsed_ms": acceptance_elapsed_ms,
            "acceptance_calibration_id": _ACCEPTANCE_CALIBRATION_ID,
            "acceptance_calibrated_p99_ms": _ACCEPTANCE_P99_MS,
            "critical_tail_calibration_id": _CRITICAL_TAIL_CALIBRATION_ID,
            "critical_tail_calibrated_p99_ms": _CRITICAL_TAIL_P99_MS,
            "seed_objective_total": result.seed_objective_total,
            "seed_max_constraint_violation": result.seed_max_constraint_violation,
            "objective_improvement": result.objective_improvement,
            "decision_change_norm": result.decision_change_norm,
            "optimization_quality_passed": result.optimization_quality_passed,
            "accepted_by_quality_gate": result.accepted_by_quality_gate,
            "accepted_candidate_source": result.accepted_candidate_source,
            "accepted_iteration": result.accepted_iteration,
            "objective_components": asdict(result.objective_components),
            "warm_start_used": warm_start is not None,
            "target_selection": "lifecycle_required_then_aggregate",
            "decision_intent": "GIVE_WAY" if committed else "HOLD",
            "preferred_side": snapshot.directive.passing_side.value.lower(),
            "starboard_asymmetry_active": assembly.problem.starboard_asymmetry_active,
            "minimum_alteration_active": assembly.problem.min_alteration_rad > 0.0,
            "overtaking_course_commitment_active": any(
                decision.encounter is EncounterKind.OVERTAKING and decision.commitment is CommitmentPhase.COMMITTED
                for decision in snapshot.targets
            ),
            "route_reference_mode": "lifecycle_commitment" if committed else "los",
            "direction_constraint_mode": "hard" if assembly.problem.lateral_active else "disabled",
            "selected_target_ids": [key.target_id for key in assembly.selected_target_keys],
            "los_guidance_dt_s": guidance_dt_s,
            "control_intervals": self._config.assembly.horizon_steps,
            "state_samples": self._config.assembly.horizon_steps + 1,
            "horizon_duration_s": self._config.assembly.horizon_steps * self._config.assembly.horizon_dt_s,
            "solve_period_s": self._config.assembly.decision_period_s,
            "trajectory_source": "fresh_ipopt_solve",
            "rolling_plan": _rolling_plan_document(
                rolling_reference,
                rolling_assessment,
                prior_revalidation_codes=prior_revalidation_codes,
            ),
            "assembly": {
                "schema_version": "1.0",
                "profile": assembly.profile.value,
                "request_hash": assembly.request_hash,
                "problem_hash": assembly.problem_hash,
                "prepared_hash": prepared_hash,
                "solver_hash": solver_hash,
                "acceptance_hash": acceptance_hash,
                "receipt_hash": receipt_hash,
                "structural_signature": assembly.preparation.structural_signature,
                "selected_targets": [
                    {"target_id": key.target_id, "generation": key.generation} for key in assembly.selected_target_keys
                ],
                "route_anchor_ne_m": list(route_anchor),
                "activation": {
                    "cpa_hard_from_k": assembly.activation_plan.global_cpa_hard_from_k,
                    "direction_hard_from_k": assembly.activation_plan.global_direction_hard_from_k,
                    "min_alt_hard_from_k": assembly.activation_plan.global_min_alt_hard_from_k,
                },
                "route_objective": (
                    {
                        "mode": "staged",
                        "mission_bearing_rad": assembly.problem.route_objective.mission_bearing_rad,
                        "avoidance_corridor_bearing_rad": (assembly.problem.route_objective.avoidance_corridor_bearing_rad),
                        "avoidance_active_until_k": assembly.problem.route_objective.avoidance_active_until_k,
                    }
                    if assembly.problem.route_objective is not None
                    else {"mode": "frozen_scalar"}
                ),
                "horizon_encounter_plan": horizon_encounter_plan_document(assembly.horizon_encounter_plan),
                "artifact": artifact_reference,
            },
            "plan_acceptance": acceptance_inline,
            "accepted_plan_receipt": accepted_plan_receipt,
            "acceptance_context": {
                "target_keys": [[track.target_id, track.generation] for track in planner_input.tracks],
                "route_hash": _planner_route_hash(planner_input),
                "capability_tuple": _active_capability(
                    planner_input,
                    self._config,
                ).exact_tuple,
                "capability_hash": _capability_contract_hash(capability),
                "scenario_id": self._config.scenario_id,
                "algorithm_seed": self._config.algorithm_seed,
                "tracker_id": self._config.tracker_id,
                "policy_hash": _document_hash(asdict(acceptance_request.policy)),
            },
            "render_projection": {
                "schema_version": "colav.mid_mpc.render@1",
                "frame": "ENU",
                "axis_order": ["sample"],
                "time_axis": {
                    "state_samples": assembly.grid.state_samples,
                    "dt_s": assembly.grid.dt_s,
                    "duration_s": assembly.grid.duration_s,
                },
                "ownship_fields": ["north_m", "east_m", "heading_rad", "speed_mps"],
                "ownship": {
                    "north_m": predicted[0].tolist(),
                    "east_m": predicted[1].tolist(),
                    "heading_rad": predicted[2].tolist(),
                    "speed_mps": np.hypot(predicted[3], predicted[4]).tolist(),
                },
                "target_fields": ["north_m", "east_m", "generation", "reference_time_s"],
                "trajectory_source": "fresh_ipopt_solve",
            },
            "lifecycle": _snapshot_document(snapshot, self._threat_management_coordinator.lifecycle),
            "threat_management": {
                "schema_version": threat_snapshot.schema_version,
                "status": "AVAILABLE",
                "semantic_hash": threat_snapshot.semantic_hash,
                "input_hash": threat_snapshot.input_hash,
                "lifecycle_input_hash": snapshot.input_hash,
                "profile_hash": threat_snapshot.profile_hash,
                "vector_count": len(threat_snapshot.vectors),
                "snapshot": threat_snapshot_document,
                "vectors": threat_snapshot_document["vectors"],
                "schedule": threat_snapshot_document["schedule"],
                "conflict_graph": threat_snapshot.conflict_graph.to_dict()
                if threat_snapshot.conflict_graph is not None
                else None,
                "unavailable_reason": None,
            },
        }
        decision_by_key = {decision.key: decision for decision in snapshot.targets}
        return MPCSolution(
            control_reference=controls[:, :1],
            predicted_trajectory=predicted,
            control_trajectory=_execution_control_knots(controls),
            status=status,
            horizon_dt_s=self._config.assembly.horizon_dt_s,
            objective=result.objective_total,
            iterations=result.ipopt_iterations,
            feasible=feasible,
            constraints=constraints,
            target_predictions=tuple(
                self._target_prediction(decision_by_key[prediction.key], prediction)
                for prediction in assembly.target_predictions
            ),
            algorithm_details=details,
            evidence=EvidenceEnvelope(prediction_evidence),
            post_commit=persist_after_commit,
        )

    def _primal_warm_start(
        self,
        planner_input: PlannerInput,
        capability: PlantCapabilityEvidence,
        semantic_token: str,
    ) -> MidMpcPrimalWarmStart | None:
        if capability.exact_tuple != "single-encounter:viknes:flsc":
            self._accepted_primal = None
            return None
        if self._accepted_primal is None:
            return None
        accepted_at_s, course, speed, capability_tuple, accepted_semantic_token = self._accepted_primal
        if (
            capability_tuple != capability.exact_tuple
            or semantic_token != accepted_semantic_token
            or planner_input.sim_time_s < accepted_at_s
        ):
            self._accepted_primal = None
            return None
        return MidMpcPrimalWarmStart(
            accepted_at_s=accepted_at_s,
            current_time_s=planner_input.sim_time_s,
            dt_s=self._config.assembly.horizon_dt_s,
            course_rad=course,
            speed_mps=speed,
        )

    def _rolling_reference(
        self,
        planner_input: PlannerInput,
        snapshot: DecisionSnapshot,
        capability: PlantCapabilityEvidence,
    ) -> tuple[RollingPlanIdentity, RollingPlanReference, bool, tuple[str, ...]]:
        identity = _rolling_plan_identity(planner_input, snapshot, capability)
        prior_plan_safe = False
        failure_codes: tuple[str, ...] = ()
        if (
            self._accepted_request is not None
            and self._accepted_trajectory is not None
            and self._accepted_acceptance_hash is not None
        ):
            elapsed_s = planner_input.sim_time_s - self._accepted_request.authority.sim_time_s
            if elapsed_s >= -1.0e-9:
                held_request = _held_acceptance_request(
                    self._accepted_request,
                    planner_input,
                    self._accepted_trajectory,
                    elapsed_s=max(0.0, elapsed_s),
                    capability=capability,
                    previous_acceptance_hash=self._accepted_acceptance_hash,
                )
                held_result = self._acceptance.evaluate(held_request)
                trackable = _rolling_plan_trackable(
                    planner_input,
                    self._accepted_trajectory,
                    elapsed_s=max(0.0, elapsed_s),
                    dt_s=self._config.assembly.horizon_dt_s,
                    heading_allowance_rad=(
                        capability.rot_max_rad_s * (max(0.0, elapsed_s) + self._config.assembly.horizon_dt_s)
                    ),
                )
                prior_plan_safe = held_result.accepted and trackable
                failure_codes = tuple(
                    finding.code
                    for finding in held_result.findings
                    if finding.mandatory and finding.outcome.value in {"FAIL", "UNKNOWN"}
                ) + (() if trackable else ("ROLLING_PLAN_STATE_DEVIATION",))
        reference = self._rolling_plan.reference(
            current_time_s=planner_input.sim_time_s,
            horizon_steps=self._config.assembly.horizon_steps,
            dt_s=self._config.assembly.horizon_dt_s,
            identity=identity,
            prior_plan_safe=prior_plan_safe,
        )
        return identity, reference, prior_plan_safe, failure_codes

    def _encounter_cycle(
        self,
        planner_input: PlannerInput,
        *,
        route_bearing_rad: float,
        planned_speed_mps: float,
    ) -> EncounterCycle:
        ownship = planner_input.ownship_state
        own_velocity = np.array(
            [
                ownship[3] * math.cos(ownship[2]) - ownship[4] * math.sin(ownship[2]),
                ownship[3] * math.sin(ownship[2]) + ownship[4] * math.cos(ownship[2]),
            ]
        )
        targets = tuple(self._target_observation(track) for track in planner_input.tracks)
        return EncounterCycle(
            epoch=self._cycle_epoch,
            sequence=self._cycle_sequence,
            sim_time_s=planner_input.sim_time_s,
            ownship=OwnshipObservation(
                position_ne_m=ownship[:2],
                velocity_ne_mps=own_velocity,
                heading_rad=float(ownship[2]),
                length_m=planner_input.ownship_length_m,
                width_m=planner_input.ownship_width_m,
                maneuverability=Maneuverability(
                    turn_rate_rad_s=self._config.assembly.rot_max_rad_s,
                    deceleration_mps2=self._config.assembly.decel_max_mps2,
                    speed_bounds_mps=self._config.assembly.speed_bounds_mps,
                ),
            ),
            targets=targets,
            route_bearing_rad=route_bearing_rad,
            planned_speed_mps=planned_speed_mps,
            profile=self._config.profile,
        )

    def _canonical_snapshot_at(
        self,
        planner_input: PlannerInput,
    ) -> ThreatManagementSnapshot | None:
        """Consume a same-time runtime snapshot instead of recycling Lifecycle."""
        snapshot = self._threat_management_coordinator.last_snapshot
        if snapshot is None or not math.isclose(
            snapshot.sim_time_s,
            planner_input.sim_time_s,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        ):
            return None
        lifecycle = snapshot.lifecycle_snapshot
        if not isinstance(lifecycle, DecisionSnapshot) or lifecycle.profile_hash != self._config.profile.hash:
            return None
        planner_keys = {TrackKey(track.target_id, track.generation) for track in planner_input.tracks}
        lifecycle_keys = {target.key for target in lifecycle.targets}
        if planner_keys != lifecycle_keys:
            return None
        return snapshot

    def _threat_target_predictions(
        self,
        planner_input: PlannerInput,
    ) -> tuple[ThreatTargetPrediction, ...]:
        """Project tracker states on the declared Mid-MPC constant-velocity basis."""
        times = np.arange(self._config.assembly.horizon_steps + 1, dtype=float) * self._config.assembly.horizon_dt_s
        predictions = []
        for track in planner_input.tracks:
            generation = track.generation or 1
            positions = track.state_enu[:2] + times[:, None] * track.state_enu[2:4]
            velocities = np.repeat(track.state_enu[None, 2:4], times.size, axis=0)
            predictions.append(
                ThreatTargetPrediction(
                    key=TrackKey(track.target_id, generation),
                    times_s=times,
                    states_enu=np.column_stack((positions, velocities)),
                    basis=PredictionBasis.CONSTANT_VELOCITY,
                    model="mid_mpc_constant_velocity_targets",
                )
            )
        return tuple(predictions)

    def _threat_baseline_prediction(self, planner_input: PlannerInput) -> OwnshipThreatPrediction:
        """Declare the current-motion ownship baseline without invoking solver authority."""
        times = np.arange(self._config.assembly.horizon_steps + 1, dtype=float) * self._config.assembly.horizon_dt_s
        ownship = planner_input.ownship_state
        velocity = np.array(
            [
                ownship[3] * math.cos(ownship[2]) - ownship[4] * math.sin(ownship[2]),
                ownship[3] * math.sin(ownship[2]) + ownship[4] * math.cos(ownship[2]),
            ]
        )
        positions = ownship[:2] + times[:, None] * velocity
        velocities = np.repeat(velocity[None, :], times.size, axis=0)
        return OwnshipThreatPrediction(
            times_s=times,
            states_enu=np.column_stack((positions, velocities)),
            basis="CURRENT_MOTION_BASELINE",
            model="mid_mpc_current_motion_baseline",
            source="PLANNER_INPUT",
            target_keys=tuple(TrackKey(track.target_id, track.generation or 1) for track in planner_input.tracks),
            reference_time_s=planner_input.sim_time_s,
        )

    def _target_observation(self, track: object) -> TargetObservation:
        if not track.identity_known:
            raise LifecycleError(
                LifecycleFailure.UNUSABLE_OBSERVATION,
                f"target {track.target_id} has no tracker-owned generation",
            )
        generation = track.generation
        status = track.status.upper()
        if status == "TERMINATED":
            health = ObservationHealth.UNUSABLE
        elif status == "COASTING":
            health = ObservationHealth.COASTING
        elif track.age_s <= self._config.profile.fresh_age_s and track.identity_known:
            health = ObservationHealth.UPDATED
        elif track.age_s <= self._config.profile.usable_age_s:
            health = ObservationHealth.DEGRADED
        else:
            health = ObservationHealth.UNUSABLE
        return TargetObservation(
            key=TrackKey(track.target_id, generation),
            state_enu=track.state_enu,
            covariance=track.covariance,
            length_m=track.length_m,
            width_m=track.width_m,
            observed_at_s=track.observed_at_s,
            generated_at_s=float(track.generated_at_s),
            health=health,
            source=track.source,
        )

    def _target_prediction(
        self,
        decision: TargetDecision,
        prediction: TargetPrediction,
    ) -> dict[str, object]:
        north = prediction.north_m.tolist()
        east = prediction.east_m.tolist()
        return {
            "target_id": decision.key.target_id,
            "generation": decision.key.generation,
            "encounter": _encounter_name(decision),
            "optimizer_intent": ("GIVE_WAY" if decision.commitment is CommitmentPhase.COMMITTED else "HOLD"),
            "policy_committed": decision.commitment is CommitmentPhase.COMMITTED,
            "route_recovery_allowed": decision.route_recovery_allowed,
            "preferred_side": decision.passing_side.value.lower(),
            "dcpa_m": decision.geometry.dcpa_m,
            "tcpa_s": max(0.0, decision.geometry.signed_tcpa_s),
            "signed_tcpa_s": _finite_or_none(decision.geometry.signed_tcpa_s),
            "relative_bearing_deg": math.degrees(decision.geometry.relative_bearing_rad),
            "north_m": north,
            "east_m": east,
            "x": north,
            "y": east,
            "velocity_ne_mps": list(prediction.velocity_ne_mps),
            "prediction_model": "constant_velocity",
            "degraded": decision.health is not ObservationHealth.UPDATED,
            "ownship_reference_time_s": prediction.reference_time_s,
        }


def _prediction_evidence(
    *,
    predicted: np.ndarray,
    controls: np.ndarray,
    assembly: AssemblySuccess,
    acceptance_request: AcceptanceRequest,
    acceptance_result: AcceptanceResult,
    result: MidMpcResult,
    candidate_hash: str,
    acceptance_hash: str,
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
) -> PredictionEvidenceRecord:
    grid = PredictionGrid(
        intervals=assembly.grid.control_intervals,
        dt_s=assembly.grid.dt_s,
    )
    control_speed = np.hypot(controls[3], controls[4])
    references = tuple(
        OptimizationIntervalReference(
            interval_index=index,
            start_s=index * grid.dt_s,
            end_s=(index + 1) * grid.dt_s,
            heading_rad=float(controls[2, index]),
            speed_mps=float(control_speed[index]),
            heading_raw_index=index,
            speed_raw_index=grid.intervals + index,
        )
        for index in range(grid.intervals)
    )
    ownship = OwnshipPrediction(
        grid=grid,
        north_m=predicted[0],
        east_m=predicted[1],
        heading_rad=predicted[2],
        speed_mps=np.hypot(predicted[3], predicted[4]),
        state_sources=("MEASURED", *("IPOPT_INTEGRATED" for _ in range(grid.intervals))),
        interval_references=references,
    )
    selected_keys = set(assembly.selected_target_keys)
    target_predictions: list[TargetPredictionEvidence] = []
    slot_by_key = {key: index for index, key in enumerate(assembly.selected_target_keys)}
    track_by_key = {TrackKey(track.target_id, track.generation): track for track in planner_input.tracks}
    decision_by_key = {decision.key: decision for decision in snapshot.targets}

    def metadata(key: TrackKey) -> dict[str, object]:
        track = track_by_key[key]
        decision = decision_by_key[key]
        return {
            "observation_time_s": track.observed_at_s,
            "generated_at_s": track.generated_at_s,
            "health": decision.health.value,
            "source": track.source,
            "state_enu": track.state_enu,
            "covariance": track.covariance,
            "length_m": track.length_m,
            "width_m": track.width_m,
            "lifecycle": {
                "encounter": decision.encounter.value,
                "role": decision.role.value,
                "risk": decision.risk.value,
                "commitment": decision.commitment.value,
                "passing_side": decision.passing_side.value,
                "route_recovery_allowed": decision.route_recovery_allowed,
            },
        }

    for prediction in assembly.target_predictions:
        if prediction.key not in selected_keys:
            continue
        target_predictions.append(
            TargetPredictionEvidence(
                key=EvidenceTrackKey(prediction.key.target_id, prediction.key.generation),
                purpose=PredictionPurpose.NLP,
                reference_time_s=prediction.reference_time_s,
                model="constant_velocity",
                north_m=prediction.north_m,
                east_m=prediction.east_m,
                admitted_to_nlp=True,
                solver_slot=slot_by_key[prediction.key],
                admission_disposition="SELECTED",
                **metadata(prediction.key),
            )
        )
    for prediction in acceptance_request.execution.targets:
        admitted = prediction.key in selected_keys
        target_predictions.append(
            TargetPredictionEvidence(
                key=EvidenceTrackKey(prediction.key.target_id, prediction.key.generation),
                purpose=PredictionPurpose.L4_SAFETY,
                reference_time_s=acceptance_request.execution.sim_time_s,
                model="constant_velocity",
                north_m=prediction.north_m,
                east_m=prediction.east_m,
                admitted_to_nlp=admitted,
                solver_slot=slot_by_key.get(prediction.key),
                admission_disposition="SELECTED" if admitted else "EXCLUDED_FROM_FROZEN_GRAPH",
                **metadata(prediction.key),
            )
        )
    acceptance_document = acceptance_result.to_dict()
    mandatory_failures = [
        finding
        for finding in acceptance_document["findings"]
        if finding["mandatory"] and finding["outcome"] in {"FAIL", "UNKNOWN"}
    ]
    acceptance_document["mandatory_failures"] = mandatory_failures
    if acceptance_result.target_safety:
        acceptance_document["worst_safety"] = min(
            (asdict(value) for value in acceptance_result.target_safety),
            key=lambda value: value["clearance_lower_bound_m"],
        )
    return PredictionEvidenceRecord(
        algorithm_id="mid_mpc_ipopt",
        candidate_hash=candidate_hash,
        acceptance_hash=acceptance_hash,
        ownship=ownship,
        target_predictions=tuple(target_predictions),
        acceptance=acceptance_document,
        solver={
            "backend": "ipopt",
            "return_status": result.ipopt_return_status,
            "normalized_status": result.status.value,
            "iterations": result.ipopt_iterations,
            "objective": result.objective_total,
            "trajectory_source": "IPOPT_PRIMAL",
        },
    )


def create(  # noqa: PLR0913
    *,
    context: FactoryContext,
    horizon_steps: int = 80,
    horizon_dt_s: float = 5.0,
    solve_period_s: float = 10.0,
    deadline_s: float = 20.0,
    heading_window_deg: float = 45.0,
    speed_min_mps: float = 0.0,
    speed_max_mps: float = 8.0,
    cpa_safe_m: float = 150.0,
    cpa_hard_m: float = 50.0,
    rot_max_deg_s: float = 3.0,
    decel_max_mps2: float = 0.3,
    min_alteration_deg: float | None = None,
    route_lateral_scale_m: float = 1000.0,
    route_weight: float = 1.0,
) -> CustomMPCAdapter:
    """Build Mid-MPC under the strict native adapter contract."""
    del min_alteration_deg
    if not math.isclose(deadline_s, _TOTAL_DEADLINE_S, abs_tol=1.0e-9, rel_tol=0.0):
        raise ValueError("Mid-MPC production deadline_s is frozen at 20 s")
    assembly = MidMpcAssemblyConfig(
        horizon_steps=horizon_steps,
        horizon_dt_s=horizon_dt_s,
        heading_window_rad=float(np.deg2rad(heading_window_deg)),
        speed_bounds_mps=(speed_min_mps, speed_max_mps),
        cpa_safe_m=cpa_safe_m,
        cpa_hard_m=cpa_hard_m,
        rot_max_rad_s=float(np.deg2rad(rot_max_deg_s)),
        decel_max_mps2=decel_max_mps2,
        route_lateral_scale_m=route_lateral_scale_m,
        route_weight=route_weight,
        decision_period_s=solve_period_s,
    )
    config = _FacadeConfig(
        assembly=assembly,
        profile=PlannerOddProfile(),
        total_deadline_s=deadline_s,
        acceptance_reservation_s=_ACCEPTANCE_RESERVATION_S,
        scenario_id=context.scenario_id,
        algorithm_seed=context.algorithm_seed,
        tracker_id=context.tracker_id,
        prewarm_targets=(
            context.scenario_target_count if context.scenario_target_count and context.scenario_target_count > 1 else None
        ),
    )
    threat_management_coordinator = context.threat_management_coordinator
    if threat_management_coordinator is None:
        threat_management_coordinator = ThreatManagementCoordinator(
            lifecycle=EncounterLifecycle(event_sink=context.event_sink),
            domain_profile=context.domain_profile,
        )
    if not isinstance(threat_management_coordinator, ThreatManagementCoordinator):
        raise TypeError("FactoryContext.threat_management_coordinator must be ThreatManagementCoordinator")
    if (
        context.domain_profile is not None
        and threat_management_coordinator.domain_profile.profile_hash != context.domain_profile.profile_hash
    ):
        raise ValueError("FactoryContext domain_profile does not match ThreatManagementCoordinator profile")
    facade = _MidMpcFacade(
        config,
        threat_management_coordinator=threat_management_coordinator,
        artifact_sink=context.artifact_sink,
    )
    descriptor = AlgorithmDescriptor(
        algorithm_id=context.requested_algorithm,
        version=__version__,
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="heading_speed_point_mass_constant_velocity_targets",
        horizon_dt=assembly.horizon_dt_s,
        horizon_steps=assembly.horizon_steps,
        state_samples=assembly.horizon_steps + 1,
        objective_terms=(
            "colreg_barrier",
            "heading_tracking",
            "speed_tracking",
            "route_tracking",
            "starboard_asymmetry",
            "terminal_lateral",
            "cpa_slack",
            "direction_slack",
        ),
        constraint_terms=(
            "yaw_rate",
            "deceleration",
            "cpa_distance",
            "preferred_side",
            "minimum_alteration",
        ),
        solver="casadi-3.7.2-ipopt",
        seed_policy="deterministic_cold_start",
        execution_profile=ExecutionProfile(
            solve_period_s=solve_period_s,
            deadline_s=deadline_s,
            requires_enc=False,
        ),
    )
    return CustomMPCAdapter(
        descriptor=descriptor,
        solve=facade.solve,
        reset=facade.reset,
        validate_hold=facade.validate_hold,
        context=context,
        capture_evidence=True,
    )


def _snapshot_document(
    snapshot: DecisionSnapshot,
    lifecycle: EncounterLifecycle,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "source": "planner",
        "epoch": snapshot.epoch,
        "sequence": snapshot.sequence,
        "input_hash": snapshot.input_hash,
        "profile_hash": snapshot.profile_hash,
        "primary_target": (
            None
            if snapshot.primary_target is None
            else {
                "target_id": snapshot.primary_target.target_id,
                "generation": snapshot.primary_target.generation,
            }
        ),
        "evidence_persisted": snapshot.evidence_persisted,
        "event_buffer": {
            "capacity": 1024,
            "size": len(lifecycle.live_events),
            "overflow_count": lifecycle.event_overflow_count,
        },
        "events": [
            {
                "schema_version": event.schema_version,
                "event_id": event.event_id,
                "sim_time_s": event.sim_time_s,
                "source": event.source,
                "event_type": event.event_type,
                "target_id": None if event.target_key is None else event.target_key.target_id,
                "generation": None if event.target_key is None else event.target_key.generation,
                "from_state": event.from_state,
                "to_state": event.to_state,
                "reason": event.reason,
            }
            for event in snapshot.events
        ],
        "targets": [
            {
                "target_id": decision.key.target_id,
                "generation": decision.key.generation,
                "episode": decision.episode,
                "encounter": decision.encounter.value,
                "role": decision.role.value,
                "risk": decision.risk.value,
                "commitment": decision.commitment.value,
                "passing_side": decision.passing_side.value,
                "rule17": decision.rule17.value,
                "rule17_basis": decision.rule17_basis,
                "health": decision.health.value,
                "route_recovery_allowed": decision.route_recovery_allowed,
                "recovery_guard_active": decision.recovery_guard_active,
                "action_achieved": decision.action_achieved,
                "required_course_change_rad": decision.required_course_change_rad,
                "candidate_since_s": decision.candidate_since_s,
                "committed_at_s": decision.committed_at_s,
                "action_start_deadline_s": decision.action_start_deadline_s,
                "action_achievement_deadline_s": decision.action_achievement_deadline_s,
                "actual_course_change_rad": decision.actual_course_change_rad,
            }
            for decision in snapshot.targets
        ],
        "aggregate": {
            "required_target_ids": [key.target_id for key in snapshot.directive.required_targets],
            "passing_side": snapshot.directive.passing_side.value,
            "minimum_course_change_rad": snapshot.directive.minimum_course_change_rad,
            "speed_bounds_mps": list(snapshot.directive.speed_bounds_mps),
            "stop_required": snapshot.directive.stop_required,
        },
    }


def _replay_artifact_document(
    assembly: AssemblySuccess,
    result: MidMpcResult,
) -> dict[str, object]:
    problem_stage = problem_hash_document(
        assembly.problem,
        assembly.target_predictions,
        assembly.horizon_encounter_plan,
        assembly.activation_plan,
        assembly.grid,
        assembly.preparation,
        parent_request_hash=assembly.request_hash,
    )
    return _artifact_value(
        {
            "schema_version": "colav.mid_mpc.replay@1",
            "request_stage": json.loads(assembly.request_stage_json),
            "problem_stage": problem_stage,
            "assembly": {
                "request_hash": assembly.request_hash,
                "problem_hash": assembly.problem_hash,
                "profile": assembly.profile,
                "problem": assembly.problem,
                "selected_target_keys": assembly.selected_target_keys,
                "target_predictions": assembly.target_predictions,
                "horizon_encounter_plan": assembly.horizon_encounter_plan,
                "activation_plan": assembly.activation_plan,
                "grid": assembly.grid,
                "preparation": assembly.preparation,
            },
            "solver": {
                "prepared": result.prepared,
                "prepared_hash_basis": "canonical prepared vectors",
                "raw": {
                    "x": result.raw_x,
                    "f": result.raw_f,
                    "g": result.raw_g,
                },
                "status": result.status,
                "native_status": result.native_status,
                "ipopt_return_status": result.ipopt_return_status,
                "iterations": result.ipopt_iterations,
                "timing": {
                    "optimizer_total_elapsed_ms": result.elapsed_ms,
                    "graph_build_elapsed_ms": result.graph_build_elapsed_ms,
                    "preparation_elapsed_ms": result.preparation_elapsed_ms,
                    "ipopt_elapsed_ms": result.ipopt_elapsed_ms,
                    "graph_cache_hit": result.graph_cache_hit,
                },
                "seed_objective_total": result.seed_objective_total,
                "seed_max_constraint_violation": result.seed_max_constraint_violation,
                "objective_improvement": result.objective_improvement,
                "decision_change_norm": result.decision_change_norm,
                "optimization_quality_passed": result.optimization_quality_passed,
                "accepted_by_quality_gate": result.accepted_by_quality_gate,
                "accepted_candidate_source": result.accepted_candidate_source,
                "accepted_iteration": result.accepted_iteration,
                "objective_components": result.objective_components,
                "row_layout": result.row_layout.to_dict(),
                "active_row_indices": result.active_row_indices,
                "tight_row_indices": result.tight_row_indices,
                "max_constraint_violation": result.max_constraint_violation,
                "max_decision_bound_violation": result.max_decision_bound_violation,
            },
            "terminal_solver_output": {
                "x": result.terminal_raw_x,
                "f": result.terminal_raw_f,
                "g": result.terminal_raw_g,
            },
            "acceptance": {
                "schema_version": "1.0",
                "owner": "L4",
                "status": "NOT_EVALUATED_BY_ASSEMBLER",
            },
        }
    )


def _active_capability(
    planner_input: PlannerInput,
    facade_config: _FacadeConfig,
) -> PlantCapabilityEvidence:
    config = facade_config.assembly
    plant = planner_input.ownship_model.strip()
    controller = planner_input.ownship_controller.strip()
    identity = (_identity_token(plant), _identity_token(controller))
    limitations: tuple[str, ...] = ()
    if identity == ("viknes", "flsc"):
        exact_tuple = "single-encounter:viknes:flsc"
        if len(planner_input.tracks) > 1:
            limitations = ("SINGLE_ENCOUNTER_TARGET_COUNT_EXCEEDED",)
    elif identity == ("kinematiccsog", "passthroughcs"):
        exact_tuple = "multiship:kinematic_csog:pass_through_cs"
    else:
        exact_tuple = f"unsupported:{identity[0]}:{identity[1]}"
        limitations = ("UNSUPPORTED_ACTIVE_TUPLE",)
    return PlantCapabilityEvidence(
        plant=plant,
        controller=controller,
        valid_at_s=planner_input.sim_time_s,
        heading_window_rad=config.heading_window_rad,
        speed_bounds_mps=config.speed_bounds_mps,
        rot_max_rad_s=planner_input.ownship_max_turn_rate_rad_s or config.rot_max_rad_s,
        accel_max_mps2=config.decel_max_mps2,
        decel_max_mps2=config.decel_max_mps2,
        exact_tuple=exact_tuple,
        limitations=limitations,
    )


def _capability_contract_hash(capability: PlantCapabilityEvidence) -> str:
    return _document_hash({**asdict(capability), "valid_at_s": 0.0})


def _acceptance_request(  # noqa: PLR0913
    *,
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    assembly: AssemblySuccess,
    result: MidMpcResult,
    predicted: np.ndarray,
    capability: PlantCapabilityEvidence,
    hard_hull_clearance_m: float,
    stand_on_course_tolerance_rad: float,
    prepared_hash: str,
    solver_hash: str,
    total_deadline_s: float,
    scenario_id: str,
    algorithm_seed: int,
    tracker_id: str,
) -> AcceptanceRequest:
    grid = assembly.grid
    cpa_span = result.row_layout.cpa
    numerical = NumericalEvidence(
        normalized_status=result.status.value,
        return_status=result.ipopt_return_status,
        objective_total=result.objective_total,
        raw_f=result.raw_f,
        raw_x=result.raw_x,
        raw_g=result.raw_g,
        lbx=result.prepared.lbx,
        ubx=result.prepared.ubx,
        lbg=result.prepared.lbg,
        ubg=result.prepared.ubg,
        heading_count=grid.control_intervals,
        speed_count=grid.control_intervals,
        cpa_row_indices=tuple(range(cpa_span.start, cpa_span.start + cpa_span.count)),
        strict_slack_bounds=True,
        cpa_slack=result.raw_cpa_slack,
        direction_slack=result.raw_dir_slack,
        preparation_profile=assembly.profile.value,
        preparation_hash=prepared_hash,
        solver_hash=solver_hash,
        preparation_parent_problem_hash=assembly.problem_hash,
        solver_parent_preparation_hash=prepared_hash,
    )
    authority_targets = tuple(
        AuthorityTarget(
            key=decision.key,
            encounter=decision.encounter.value,
            role=decision.role.value,
            risk=decision.risk.value,
            commitment=decision.commitment.value,
            passing_side=decision.passing_side.value,
            baseline_course_rad=decision.baseline_course_rad,
            required_course_change_rad=decision.required_course_change_rad,
            action_achieved=decision.action_achieved,
            route_recovery_allowed=decision.route_recovery_allowed,
            reachability_verified=_decision_reachable(decision, capability, grid.duration_s),
            committed_at_s=decision.committed_at_s,
            action_start_deadline_s=decision.action_start_deadline_s,
            action_achievement_deadline_s=decision.action_achievement_deadline_s,
            actual_course_change_rad=decision.actual_course_change_rad,
            rule17=decision.rule17.value,
        )
        for decision in snapshot.targets
    )
    execution_targets = tuple(_execution_target(track, grid.state_samples, grid.dt_s) for track in planner_input.tracks)
    return AcceptanceRequest(
        schema_version="colav.mid_mpc.acceptance.request@1",
        candidate=CandidateEvidence(
            profile=AcceptanceProfile(assembly.profile.value),
            times_s=np.arange(grid.state_samples, dtype=float) * grid.dt_s,
            north_m=predicted[0],
            east_m=predicted[1],
            course_rad=predicted[2],
            speed_mps=np.hypot(predicted[3], predicted[4]),
            numerical=numerical,
            parent_problem_hash=assembly.problem_hash,
            phase_evidence=_prediction_phase_evidence(assembly),
        ),
        authority=AuthorityEvidence(
            epoch=snapshot.epoch,
            sequence=snapshot.sequence,
            sim_time_s=snapshot.sim_time_s,
            profile_hash=snapshot.profile_hash,
            targets=authority_targets,
        ),
        execution=ExecutionEvidence(
            sim_time_s=planner_input.sim_time_s,
            ownship_length_m=planner_input.ownship_length_m,
            ownship_width_m=planner_input.ownship_width_m,
            targets=execution_targets,
            capability=capability,
            tracker_id=tracker_id,
        ),
        prior=PriorEvidence(mode=AcceptanceMode.FRESH_CANDIDATE),
        policy=PlanAcceptancePolicy(
            control_intervals=grid.control_intervals,
            state_samples=grid.state_samples,
            horizon_dt_s=grid.dt_s,
            hard_hull_clearance_m=hard_hull_clearance_m,
            stand_on_course_tolerance_rad=stand_on_course_tolerance_rad,
            advisory_hull_clearance_m=assembly.problem.cpa_safe_m,
            total_deadline_s=total_deadline_s,
            scenario_id=scenario_id,
            algorithm_seed=algorithm_seed,
            tracker_id=tracker_id,
        ),
    )


def _prediction_phase_evidence(assembly: AssemblySuccess) -> PredictionPhaseEvidence:
    plan = assembly.horizon_encounter_plan
    phases = tuple(phase.value for phase in plan.phases)
    return PredictionPhaseEvidence(
        times_s=plan.times_s,
        phases=phases,
        mission_bearing_rad=plan.mission_route_bearing_rad,
        avoidance_corridor_bearing_rad=plan.avoidance_corridor_bearing_rad,
        recovery_from_k=plan.recovery_from_k if "RECOVER" in phases else None,
        target_keys=tuple(EvidenceTrackKey(window.key.target_id, window.key.generation) for window in plan.target_windows),
        solver_consumed=plan.solver_consumed,
    )


def _shift_phase_evidence(evidence: PredictionPhaseEvidence, elapsed_s: float) -> PredictionPhaseEvidence:
    dt_s = float(evidence.times_s[1] - evidence.times_s[0])
    offset = min(int(math.floor(max(0.0, elapsed_s) / dt_s)), len(evidence.phases) - 1)
    phases = evidence.phases[offset:] + (evidence.phases[-1],) * offset
    recovery_from_k = next((index for index, phase in enumerate(phases) if phase == "RECOVER"), None)
    return replace(evidence, phases=phases, recovery_from_k=recovery_from_k)


def _held_acceptance_request(
    accepted: AcceptanceRequest,
    planner_input: PlannerInput,
    predicted_trajectory: np.ndarray,
    *,
    elapsed_s: float,
    capability: PlantCapabilityEvidence,
    previous_acceptance_hash: str,
) -> AcceptanceRequest:
    sample_times = accepted.candidate.times_s
    absolute_offsets = np.minimum(sample_times + elapsed_s, sample_times[-1])

    def shifted(values: np.ndarray, *, angle: bool = False) -> np.ndarray:
        source = np.unwrap(values) if angle else values
        return np.interp(absolute_offsets, sample_times, source)

    candidate = replace(
        accepted.candidate,
        north_m=shifted(predicted_trajectory[0]),
        east_m=shifted(predicted_trajectory[1]),
        course_rad=shifted(predicted_trajectory[2], angle=True),
        speed_mps=shifted(np.hypot(predicted_trajectory[3], predicted_trajectory[4])),
        phase_evidence=(
            _shift_phase_evidence(accepted.candidate.phase_evidence, elapsed_s)
            if accepted.candidate.phase_evidence is not None
            else None
        ),
    )
    execution = replace(
        accepted.execution,
        sim_time_s=planner_input.sim_time_s,
        targets=tuple(
            _execution_target(track, accepted.policy.state_samples, accepted.policy.horizon_dt_s)
            for track in planner_input.tracks
        ),
        capability=capability,
        tracker_id=_tracker_identity(planner_input),
    )
    return replace(
        accepted,
        candidate=candidate,
        authority=replace(accepted.authority, sim_time_s=planner_input.sim_time_s),
        execution=execution,
        prior=PriorEvidence(
            mode=AcceptanceMode.HELD_ACCEPTED_PLAN,
            previous_acceptance_hash=previous_acceptance_hash,
            previous_course_rad=accepted.candidate.course_rad,
        ),
    )


def _acceptance_inline_projection(result: AcceptanceResult, *, limit_bytes: int) -> dict[str, object]:
    document = result.to_dict()
    mandatory_failures = [
        {
            "layer": finding["layer"],
            "code": finding["code"],
            "target_key": finding.get("target_key"),
            "witness": finding.get("witness"),
        }
        for finding in document["findings"]
        if finding["mandatory"] and finding["outcome"] in {"FAIL", "UNKNOWN"}
    ]
    target_safety = document["target_safety"]
    primary_witness = min(target_safety, key=lambda item: item["clearance_lower_bound_m"]) if target_safety else None
    projection: dict[str, object] = {
        "schema_version": "colav.mid_mpc.acceptance.inline@1",
        "accepted": document["accepted"],
        "aggregate": document["aggregate"],
        "profile": document["profile"],
        "request_hash": document["request_hash"],
        "acceptance_hash": document["acceptance_hash"],
        "layers": document["layers"],
        "mandatory_failures": mandatory_failures,
        "primary_safety_witness": primary_witness,
    }
    payload = json.dumps(projection, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > limit_bytes:
        for failure in mandatory_failures:
            failure["witness"] = None
        projection["primary_safety_witness"] = None
        projection["projection_truncated"] = True
        payload = json.dumps(projection, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > limit_bytes:
        raise RuntimeError("mandatory Mid-MPC acceptance summary exceeds inline evidence limit")
    projection["inline_bytes"] = 0
    projection["inline_bytes"] = len(
        json.dumps(projection, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    )
    if projection["inline_bytes"] > limit_bytes:
        raise RuntimeError("Mid-MPC acceptance summary exceeds inline evidence limit")
    return projection


def _execution_target(
    track: object,
    state_samples: int,
    dt_s: float,
) -> ExecutionTarget:
    times = np.arange(state_samples, dtype=float) * dt_s
    north = float(track.state_enu[0]) + times * float(track.state_enu[2])
    east = float(track.state_enu[1]) + times * float(track.state_enu[3])
    position_covariance = np.asarray(track.covariance, dtype=float)[:2, :2]
    largest_variance = max(0.0, float(np.max(np.linalg.eigvalsh(position_covariance))))
    uncertainty = np.full(state_samples, math.sqrt(9.210340371976184 * largest_variance))
    return ExecutionTarget(
        key=TrackKey(track.target_id, track.generation),
        length_m=track.length_m,
        width_m=track.width_m,
        north_m=north,
        east_m=east,
        uncertainty_m=uncertainty,
    )


def _decision_reachable(
    decision: TargetDecision,
    capability: PlantCapabilityEvidence,
    horizon_duration_s: float,
) -> bool:
    if decision.commitment is not CommitmentPhase.COMMITTED:
        return True
    if decision.baseline_course_rad is None:
        return False
    available_change = capability.rot_max_rad_s * horizon_duration_s
    return decision.required_course_change_rad <= available_change + 1.0e-9


def _tracker_identity(planner_input: PlannerInput) -> str:
    sources = sorted({track.source for track in planner_input.tracks})
    return "none" if not sources else "+".join(sources)


def _warm_semantic_token(snapshot: DecisionSnapshot, assembly: AssemblySuccess) -> str:
    route_objective = assembly.problem.route_objective
    return _document_hash(
        {
            "profile": assembly.profile.value,
            "mission_bearing_rad": (
                route_objective.mission_bearing_rad if route_objective is not None else assembly.problem.route_bearing_rad
            ),
            "avoidance_corridor_bearing_rad": (
                route_objective.avoidance_corridor_bearing_rad
                if route_objective is not None and assembly.problem.lateral_active
                else None
            ),
            "planned_speed_mps": assembly.problem.planned_speed_mps,
            "selected_target_keys": [[key.target_id, key.generation] for key in assembly.selected_target_keys],
            "directive": {
                "passing_side": snapshot.directive.passing_side.value,
                "minimum_course_change_rad": snapshot.directive.minimum_course_change_rad,
                "speed_bounds_mps": snapshot.directive.speed_bounds_mps,
                "stop_required": snapshot.directive.stop_required,
            },
            "targets": [
                {
                    "key": [decision.key.target_id, decision.key.generation],
                    "risk": decision.risk.value,
                    "commitment": decision.commitment.value,
                    "rule17": decision.rule17.value,
                    "route_recovery_allowed": decision.route_recovery_allowed,
                }
                for decision in snapshot.targets
            ],
        }
    )


def _identity_token(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _rolling_plan_identity(
    planner_input: PlannerInput,
    snapshot: DecisionSnapshot,
    capability: PlantCapabilityEvidence,
) -> RollingPlanIdentity:
    authority = {
        "directive": {
            "required_targets": [[key.target_id, key.generation] for key in snapshot.directive.required_targets],
            "passing_side": snapshot.directive.passing_side.value,
            "minimum_course_change_rad": snapshot.directive.minimum_course_change_rad,
            "speed_bounds_mps": snapshot.directive.speed_bounds_mps,
            "stop_required": snapshot.directive.stop_required,
        },
        "targets": [
            {
                "key": [decision.key.target_id, decision.key.generation],
                "encounter": decision.encounter.value,
                "role": decision.role.value,
                "risk": decision.risk.value,
                "commitment": decision.commitment.value,
                "passing_side": decision.passing_side.value,
                "rule17": decision.rule17.value,
                "route_recovery_allowed": decision.route_recovery_allowed,
                "action_achieved": decision.action_achieved,
                "required_course_change_rad": decision.required_course_change_rad,
            }
            for decision in snapshot.targets
        ],
    }
    return RollingPlanIdentity(
        route_hash=_planner_route_hash(planner_input),
        target_keys=tuple(sorted((track.target_id, int(track.generation)) for track in planner_input.tracks)),
        capability_hash=_capability_contract_hash(capability),
        authority_hash=_document_hash(authority),
    )


def _recovery_at_s(request: AcceptanceRequest) -> float | None:
    phases = request.candidate.phase_evidence
    if phases is None or phases.recovery_from_k is None:
        return None
    return request.authority.sim_time_s + float(phases.times_s[phases.recovery_from_k])


def _rolling_plan_document(
    reference: RollingPlanReference,
    assessment: RollingPlanAssessment,
    *,
    prior_revalidation_codes: tuple[str, ...],
) -> dict[str, object]:
    reference_document = asdict(reference)
    reference_document["revision_reason"] = reference.revision_reason.value
    assessment_document = asdict(assessment)
    assessment_document["revision_reason"] = assessment.revision_reason.value
    return {
        "schema_version": "colav.mid_mpc.rolling-plan@1",
        "reference": reference_document,
        "assessment": assessment_document,
        "prior_revalidation_codes": list(prior_revalidation_codes),
    }


def _planner_route_hash(planner_input: PlannerInput) -> str:
    return _document_hash(
        {
            "waypoints_enu_m": planner_input.waypoints_enu_m.tolist(),
            "speed_plan_mps": planner_input.speed_plan_mps.tolist(),
        }
    )


def _trajectory_state_at(trajectory: np.ndarray, dt_s: float, elapsed_s: float) -> np.ndarray:
    position = min(max(elapsed_s / dt_s, 0.0), trajectory.shape[1] - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, trajectory.shape[1] - 1)
    fraction = position - lower
    state = (1.0 - fraction) * trajectory[:, lower] + fraction * trajectory[:, upper]
    heading_delta = float(trajectory[2, upper] - trajectory[2, lower])
    state[2] = trajectory[2, lower] + fraction * math.atan2(math.sin(heading_delta), math.cos(heading_delta))
    return state


def _rolling_plan_trackable(
    planner_input: PlannerInput,
    trajectory: np.ndarray,
    *,
    elapsed_s: float,
    dt_s: float,
    heading_allowance_rad: float,
) -> bool:
    expected = _trajectory_state_at(trajectory, dt_s, elapsed_s)
    position_error_m = float(np.linalg.norm(planner_input.ownship_state[:2] - expected[:2]))
    heading_delta = float(planner_input.ownship_state[2] - expected[2])
    heading_error_rad = abs(math.atan2(math.sin(heading_delta), math.cos(heading_delta)))
    return position_error_m <= 50.0 and heading_error_rad <= heading_allowance_rad + 1.0e-6


def _held_prefix_clearance(
    planner_input: PlannerInput,
    solution: MPCSolution,
    *,
    elapsed_s: float,
    remaining_s: float,
) -> float:
    if not planner_input.tracks:
        return math.inf
    own_start = np.asarray(planner_input.ownship_state[:2], dtype=float)
    own_end = _trajectory_state_at(
        solution.predicted_trajectory,
        solution.horizon_dt_s,
        elapsed_s + remaining_s,
    )[:2]
    own_radius = 0.5 * math.hypot(planner_input.ownship_length_m, planner_input.ownship_width_m)
    minimum = math.inf
    for track in planner_input.tracks:
        target_start = np.asarray(track.state_enu[:2], dtype=float)
        target_end = target_start + remaining_s * np.asarray(track.state_enu[2:4], dtype=float)
        relative_start = target_start - own_start
        relative_delta = (target_end - own_end) - relative_start
        denominator = float(relative_delta @ relative_delta)
        fraction = (
            0.0
            if denominator <= 1.0e-18
            else float(np.clip(-float(relative_start @ relative_delta) / denominator, 0.0, 1.0))
        )
        center_distance = float(np.linalg.norm(relative_start + fraction * relative_delta))
        target_radius = 0.5 * math.hypot(track.length_m, track.width_m)
        position_covariance = np.asarray(track.covariance, dtype=float)[:2, :2]
        variance = max(0.0, float(np.max(np.linalg.eigvalsh(position_covariance))))
        uncertainty = math.sqrt(9.210340371976184 * variance)
        minimum = min(minimum, center_distance - own_radius - target_radius - uncertainty)
    return minimum


def _held_target_prediction_error(
    planner_input: PlannerInput,
    solution: MPCSolution,
    *,
    elapsed_s: float,
) -> tuple[float, float]:
    predictions = {(int(item["target_id"]), int(item["generation"])): item for item in solution.target_predictions}
    maximum_position_error = 0.0
    maximum_velocity_error = 0.0
    for track in planner_input.tracks:
        prediction = predictions[(track.target_id, track.generation)]
        if prediction.get("route_recovery_allowed") is True:
            continue
        start = np.array([prediction["north_m"][0], prediction["east_m"][0]], dtype=float)
        velocity = np.asarray(prediction["velocity_ne_mps"], dtype=float)
        expected = start + elapsed_s * velocity
        maximum_position_error = max(
            maximum_position_error,
            float(np.linalg.norm(np.asarray(track.state_enu[:2], dtype=float) - expected)),
        )
        maximum_velocity_error = max(
            maximum_velocity_error,
            float(np.linalg.norm(np.asarray(track.state_enu[2:4], dtype=float) - velocity)),
        )
    return maximum_position_error, maximum_velocity_error


def _hold_rejection(code: str, message: str) -> ColavExecutionError:
    return ColavExecutionError(
        PlanStatus.INFEASIBLE,
        message,
        source=FailureSource.ALGORITHM,
        details={"failure_code": code, "failure_owner": "plan_acceptance"},
    )


def _artifact_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isinf(value):
            return "Infinity" if value > 0.0 else "-Infinity"
        if math.isnan(value):
            raise ValueError("Mid-MPC replay evidence cannot contain NaN")
        return value
    if isinstance(value, np.ndarray):
        return _artifact_value(value.tolist())
    if isinstance(value, np.generic):
        return _artifact_value(value.item())
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _artifact_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _artifact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_artifact_value(item) for item in value]
    raise TypeError(f"unsupported Mid-MPC evidence value: {type(value).__name__}")


def _document_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _encounter_name(decision: TargetDecision) -> str:
    if decision.encounter is EncounterKind.HEAD_ON:
        return "head_on"
    if decision.encounter is EncounterKind.CROSSING:
        return "crossing_give_way" if decision.role is OwnshipRole.GIVE_WAY else "crossing_stand_on"
    if decision.encounter is EncounterKind.OVERTAKING:
        return "overtaking" if decision.role is OwnshipRole.OVERTAKING else "overtaken"
    if decision.encounter is EncounterKind.UNKNOWN:
        return "unknown"
    return "clear"


def _nearest_route_projection(
    waypoints_enu_m: np.ndarray,
    position_ne_m: np.ndarray,
) -> tuple[tuple[float, float], float]:
    """Project onto the stable waypoint polyline and retain its tangent."""
    points = np.asarray(waypoints_enu_m, dtype=float).T
    position = np.asarray(position_ne_m, dtype=float)
    if len(points) == 1:
        return (float(points[0, 0]), float(points[0, 1])), 0.0
    candidates: list[tuple[np.ndarray, float]] = []
    for start, end in zip(points[:-1], points[1:], strict=True):
        delta = end - start
        length_squared = float(delta @ delta)
        fraction = 0.0 if length_squared == 0.0 else float(np.clip((position - start) @ delta / length_squared, 0.0, 1.0))
        tangent = 0.0 if length_squared == 0.0 else math.atan2(float(delta[1]), float(delta[0]))
        candidates.append((start + fraction * delta, tangent))
    anchor, tangent = min(
        candidates,
        key=lambda candidate: float(np.linalg.norm(candidate[0] - position)),
    )
    return (float(anchor[0]), float(anchor[1])), tangent


def _unwrap_near(angle: float, reference: float) -> float:
    return reference + math.atan2(math.sin(angle - reference), math.cos(angle - reference))


def _finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None


def _plan_status(status: MidMpcStatus, max_violation: float) -> tuple[PlanStatus, bool]:
    if status in {MidMpcStatus.CONVERGED, MidMpcStatus.FEASIBLE_NONOPTIMAL}:
        return PlanStatus.SUCCESS, True
    if status is MidMpcStatus.TIMEOUT and max_violation <= 1.0e-3:
        return PlanStatus.TIMEOUT_FEASIBLE, True
    if status is MidMpcStatus.INFEASIBLE:
        return PlanStatus.INFEASIBLE, False
    return PlanStatus.NUMERICAL_FAILURE, False


def _native_trajectories(
    points: tuple,
    ownship: np.ndarray,
    dt_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    interval_count = len(points)
    predicted = np.zeros((9, interval_count + 1), dtype=float)
    controls = np.zeros((9, interval_count), dtype=float)
    north0, east0 = map(float, ownship[:2])
    headings = np.array([point.psi_rad for point in points], dtype=float)
    speeds = np.array([point.u_mps for point in points], dtype=float)
    north = north0 + np.cumsum(speeds * np.cos(headings) * dt_s)
    east = east0 + np.cumsum(speeds * np.sin(headings) * dt_s)
    yaw_rate = np.zeros(interval_count, dtype=float)
    acceleration_ne = np.zeros((2, interval_count), dtype=float)
    yaw_rate[0] = (headings[0] - float(ownship[2])) / dt_s
    velocity_ne_mps = np.vstack((speeds * np.cos(headings), speeds * np.sin(headings)))
    own_velocity_ne_mps = np.array(
        [
            ownship[3] * math.cos(ownship[2]) - ownship[4] * math.sin(ownship[2]),
            ownship[3] * math.sin(ownship[2]) + ownship[4] * math.cos(ownship[2]),
        ]
    )
    acceleration_ne[:, 0] = 2.0 * (velocity_ne_mps[:, 0] - own_velocity_ne_mps) / dt_s
    if interval_count > 1:
        yaw_rate[1:] = np.diff(headings) / dt_s
        acceleration_ne[:, 1:] = np.diff(velocity_ne_mps, axis=1) / dt_s
    controls[0] = north
    controls[1] = east
    controls[2] = headings
    controls[3] = speeds
    controls[5] = yaw_rate
    controls[6:8] = acceleration_ne
    controls[8] = yaw_rate
    predicted[:, 1:] = controls
    predicted[:6, 0] = ownship
    predicted[8, 0] = ownship[5]
    return predicted, controls


def _execution_control_knots(controls: np.ndarray) -> np.ndarray:
    """Encode interval controls as knots without anticipating the next interval."""
    knots = controls.copy()
    if knots.shape[1] > 1:
        knots[:, 1:] = controls[:, :-1]
    return knots
