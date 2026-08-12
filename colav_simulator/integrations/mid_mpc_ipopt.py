"""Colav-native lifecycle facade for the parity-complete Mid-MPC IPOPT core."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, is_dataclass
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
    LifecycleEvent,
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
from colav_simulator.core.colav.mid_mpc import (
    MidMpcConfig,
    MidMpcIpoptSolver,
    MidMpcResult,
    MidMpcStatus,
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
from colav_simulator.core.guidances import LOSGuidance
from colav_simulator.core.tracking.trackers import TrackKey

__version__ = "2.0.0"


@dataclass(frozen=True)
class _FacadeConfig:
    assembly: MidMpcAssemblyConfig
    profile: PlannerOddProfile


class _MidMpcFacade:
    def __init__(
        self,
        config: _FacadeConfig,
        *,
        event_sink: Callable[[LifecycleEvent], object] | None = None,
        artifact_sink: Callable[[object], object] | None = None,
    ) -> None:
        self._config = config
        self._los = LOSGuidance()
        core_config = MidMpcConfig(
            horizon_steps=config.assembly.horizon_steps,
            dt_s=config.assembly.horizon_dt_s,
            strict_slack_bounds=True,
        )
        self._solver = MidMpcIpoptSolver(core_config)
        self._assembler = MidMpcProblemAssembler()
        self._lifecycle = EncounterLifecycle(event_sink=event_sink)
        self._last_guidance_time_s: float | None = None
        self._epoch_number = 1
        self._cycle_sequence = 0
        self._last_cycle_time_s: float | None = None
        self._artifact_sink = artifact_sink

    def reset(self) -> None:
        self._los.reset()
        self._epoch_number += 1
        self._lifecycle.reset(
            epoch=f"mid-mpc-{self._epoch_number}",
            reason="adapter_reset",
            sim_time_s=0.0 if self._last_cycle_time_s is None else self._last_cycle_time_s,
        )
        self._last_guidance_time_s = None
        self._cycle_sequence = 0
        self._last_cycle_time_s = None

    def solve(self, planner_input: PlannerInput) -> MPCSolution:
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
        if self._last_cycle_time_s is not None and planner_input.sim_time_s != self._last_cycle_time_s:
            self._cycle_sequence += 1
        self._last_cycle_time_s = planner_input.sim_time_s
        route_anchor = _nearest_route_anchor(planner_input.waypoints_enu_m, ownship[:2])
        try:
            cycle = self._encounter_cycle(
                planner_input,
                route_bearing_rad=route_bearing,
                planned_speed_mps=float(reference[3, 0]),
            )
            snapshot = self._lifecycle.step(cycle)
            assembly = self._assembler.assemble(
                AssemblyRequest(
                    planner_input=planner_input,
                    snapshot=snapshot,
                    cycle_input_hash=cycle.input_hash,
                    lifecycle_profile_hash=cycle.profile.hash,
                    route=RouteReference(
                        anchor_ne_m=route_anchor,
                        bearing_rad=route_bearing,
                        planned_speed_mps=float(reference[3, 0]),
                    ),
                    capability=CapabilitySnapshot(
                        heading_window_rad=self._config.assembly.heading_window_rad,
                        speed_bounds_mps=self._config.assembly.speed_bounds_mps,
                        rot_max_rad_s=self._config.assembly.rot_max_rad_s,
                        decel_max_mps2=self._config.assembly.decel_max_mps2,
                    ),
                    config=self._config.assembly,
                    profile=AssemblyProfile.COLAV_STRICT,
                )
            )
        except LifecycleError as exc:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"Mid-MPC lifecycle {exc.failure.value}: {exc}",
                source=FailureSource.ALGORITHM,
                details={"failure_code": exc.failure.value, "failure_owner": "lifecycle"},
            ) from exc
        if isinstance(assembly, AssemblyFailure):
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
        result = self._solver.solve(assembly.problem)
        predicted, controls = _native_trajectories(
            result.trajectory,
            ownship,
            self._config.assembly.horizon_dt_s,
        )
        status, feasible = _plan_status(result.status, result.max_constraint_violation)
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
        acceptance_stage = {
            "schema_version": "colav.mid_mpc.acceptance@1",
            "parent_solver_hash": solver_hash,
            "acceptance": replay_artifact["acceptance"],
        }
        acceptance_hash = _document_hash(acceptance_stage)
        replay_artifact["prepared_stage"] = prepared_stage
        replay_artifact["solver_stage"] = solver_stage
        replay_artifact["acceptance_stage"] = acceptance_stage
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
        details = {
            "formulation": "mass-l3-mid-mpc-ipopt-frozen",
            "solver_backend": "ipopt",
            "ipopt_return_status": result.ipopt_return_status,
            "normalized_solver_status": result.status.value,
            "native_solver_status": result.native_status.value,
            "solver_elapsed_ms": result.elapsed_ms,
            "seed_objective_total": result.seed_objective_total,
            "seed_max_constraint_violation": result.seed_max_constraint_violation,
            "objective_improvement": result.objective_improvement,
            "decision_change_norm": result.decision_change_norm,
            "optimization_quality_passed": result.optimization_quality_passed,
            "accepted_by_quality_gate": result.accepted_by_quality_gate,
            "accepted_candidate_source": result.accepted_candidate_source,
            "accepted_iteration": result.accepted_iteration,
            "objective_components": asdict(result.objective_components),
            "warm_start_used": False,
            "target_selection": "lifecycle_required_then_aggregate",
            "decision_intent": "GIVE_WAY" if committed else "HOLD",
            "preferred_side": snapshot.directive.passing_side.value.lower(),
            "starboard_asymmetry_active": assembly.problem.starboard_asymmetry_active,
            "minimum_alteration_active": assembly.problem.lateral_active,
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
            "trajectory_source": "fresh_ipopt_solve",
            "assembly": {
                "schema_version": "1.0",
                "profile": assembly.profile.value,
                "request_hash": assembly.request_hash,
                "problem_hash": assembly.problem_hash,
                "prepared_hash": prepared_hash,
                "solver_hash": solver_hash,
                "acceptance_hash": acceptance_hash,
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
                "artifact": artifact_reference,
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
            "lifecycle": _snapshot_document(snapshot, self._lifecycle),
        }
        decision_by_key = {decision.key: decision for decision in snapshot.targets}
        return MPCSolution(
            control_reference=controls[:, :1],
            predicted_trajectory=predicted,
            control_trajectory=controls,
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
        )

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
            epoch=f"mid-mpc-{self._epoch_number}",
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


def create(  # noqa: PLR0913
    *,
    context: FactoryContext,
    horizon_steps: int = 80,
    horizon_dt_s: float = 15.0,
    solve_period_s: float = 5.0,
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
    config = _FacadeConfig(assembly=assembly, profile=PlannerOddProfile())
    facade = _MidMpcFacade(
        config,
        event_sink=context.event_sink,
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
        context=context,
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


def _nearest_route_anchor(waypoints_enu_m: np.ndarray, position_ne_m: np.ndarray) -> tuple[float, float]:
    """Project current position onto the stable waypoint polyline."""
    points = np.asarray(waypoints_enu_m, dtype=float).T
    position = np.asarray(position_ne_m, dtype=float)
    if len(points) == 1:
        return float(points[0, 0]), float(points[0, 1])
    candidates: list[np.ndarray] = []
    for start, end in zip(points[:-1], points[1:], strict=True):
        delta = end - start
        length_squared = float(delta @ delta)
        fraction = 0.0 if length_squared == 0.0 else float(np.clip((position - start) @ delta / length_squared, 0.0, 1.0))
        candidates.append(start + fraction * delta)
    anchor = min(candidates, key=lambda candidate: float(np.linalg.norm(candidate - position)))
    return float(anchor[0]), float(anchor[1])


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
