"""Unified offline, replay, batch, and Web experiment preparation."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

import colav_simulator.common.config_parsing as cp
import colav_simulator.common.file_utils as futils
from colav_simulator import scenario_config
from colav_simulator.common import paths
from colav_simulator.core.colav.custom_mpc_adapter import (
    CustomMPCAdapter,
    DeadlineMode,
    FactoryContext,
)
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.evaluation import Evaluator, EvaluatorResult
from colav_simulator.experiment.capabilities import CapabilityCatalog
from colav_simulator.experiment.contracts import RunManifest, RunOutcome, RunSpec, SessionState, content_hash
from colav_simulator.experiment.persistence import BoundedArtifactSink, EvidenceWriter
from colav_simulator.experiment.session import SimulationSession
from colav_simulator.integrations import IntegrationRegistry
from colav_simulator.scenario_generator import ScenarioGenerator
from colav_simulator.simulator import Config as SimulatorConfig
from colav_simulator.simulator import Simulator


@dataclass
class PreparedRun:
    spec: RunSpec
    manifest: RunManifest
    session: SimulationSession
    writer: EvidenceWriter
    episode_document: dict[str, Any]
    artifact_sink: BoundedArtifactSink

    @property
    def run_dir(self) -> Path:
        return self.writer.run_dir


@dataclass
class RunResult:
    manifest: RunManifest
    evaluation: EvaluatorResult
    run_dir: Path
    session: SimulationSession
    writer: EvidenceWriter


class ExperimentRunError(RuntimeError):
    """Run failure with a persisted evidence directory."""

    def __init__(self, manifest: RunManifest, run_dir: Path) -> None:
        super().__init__(manifest.failure_reason or "Experiment failed")
        self.manifest = manifest
        self.run_dir = run_dir


class ExperimentRunner:
    """Execute every surface through the same generator and simulator objects."""

    def __init__(
        self,
        project_root: Path | None = None,
        registry: IntegrationRegistry | None = None,
        evaluator: Evaluator | None = None,
    ) -> None:
        source_root = Path(__file__).resolve().parents[2]
        if project_root is not None:
            self.project_root = project_root.resolve()
        elif (source_root / "scenarios").is_dir():
            self.project_root = source_root
        else:
            self.project_root = Path.cwd().resolve()
        local_scenarios = self.project_root / "scenarios"
        self.scenarios_root = local_scenarios if local_scenarios.is_dir() else paths.scenarios
        self.registry = registry or IntegrationRegistry()
        self.capabilities = CapabilityCatalog(self.registry)
        self.evaluator = evaluator or Evaluator()
        self._enc_cache: dict[tuple[str, int | str, int, int], Any] = {}

    def list_scenarios(self) -> list[dict[str, Any]]:
        scenarios = []
        for path in sorted(self.scenarios_root.rglob("*.yaml")):
            try:
                config = cp.extract(scenario_config.ScenarioConfig, path, paths.scenario_schema)
            except Exception as exc:
                scenarios.append(
                    self.capabilities.annotate_scenario(
                        {
                            "id": str(path.relative_to(self.scenarios_root).with_suffix("")),
                            "path": str(path),
                            "valid": False,
                            "reason": str(exc),
                        }
                    )
                )
                continue
            scenarios.append(
                self.capabilities.annotate_scenario(
                    {
                        "id": str(path.relative_to(self.scenarios_root).with_suffix("")),
                        "name": config.name,
                        "type": config.type.name,
                        "dt": config.dt_sim,
                        "t_start": config.t_start,
                        "t_end": config.t_end,
                        "ships": max(len(config.ship_list), 1 + (config.n_random_ships or 0)),
                        "provenance": self._scenario_provenance(str(path.relative_to(self.scenarios_root).with_suffix(""))),
                        "valid": True,
                    }
                )
            )
        return scenarios

    def list_capabilities(self, validation_rule_id: str | None = None) -> dict[str, Any]:
        """Return the selection catalog with readiness distinct from import status."""
        return self.capabilities.document(self.list_scenarios(), validation_rule_id)

    def resolve_scenario(self, scenario_id: str) -> Path:
        direct = self.scenarios_root / f"{scenario_id}.yaml"
        if direct.is_file():
            return direct
        matches = list(self.scenarios_root.rglob(f"{scenario_id}.yaml"))
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise FileNotFoundError(f"Unknown scenario: {scenario_id}")
        raise ValueError(f"Ambiguous scenario ID {scenario_id}: {matches}")

    def prepare(self, spec: RunSpec) -> PreparedRun:  # noqa: PLR0912, PLR0915
        scenario_path = self.resolve_scenario(spec.scenario_id)
        if spec.scenario_override is None:
            config = cp.extract(scenario_config.ScenarioConfig, scenario_path, paths.scenario_schema)
            source_version = scenario_path.stat().st_mtime_ns
        else:
            override_document = copy.deepcopy(spec.scenario_override)
            cp.validate(override_document, futils.read_yaml_into_dict(paths.scenario_schema))
            config = scenario_config.ScenarioConfig.from_dict(override_document)
            source_version = content_hash(override_document)
        config.filename = scenario_path.name
        if spec.dt is not None:
            config.dt_sim = spec.dt
        if spec.t_end is not None:
            config.t_end = spec.t_end
        if spec.reload_enc:
            config.new_load_of_map_data = True
        capability_profile_id = None
        if spec.validation_rule_id:
            capability_profile_id = self.capabilities.validate(
                spec.validation_rule_id,
                spec.scenario_id,
                spec.algorithm_id,
                spec.tracker_id,
            )
        if spec.algorithm_id == "nominal" and config.ship_list and config.ship_list[0].colav is not None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "nominal requires scenario guidance; the selected scenario embeds an onboard COLAV algorithm",
            )
        scenario_document = config.to_dict()
        generator = ScenarioGenerator(seed=spec.seeds.scenario)
        episode_count = max(1, spec.episode_index + 1)
        enc_cache_key = (
            str(scenario_path.resolve()),
            source_version,
            spec.seeds.scenario,
            episode_count,
        )
        cached_enc = None if spec.reload_enc else self._enc_cache.get(enc_cache_key)
        episodes, enc = generator.generate(
            config=config,
            enc=cached_enc,
            n_episodes=episode_count,
            show_plots=False,
            save_scenario=False,
        )
        self._enc_cache[enc_cache_key] = copy.deepcopy(enc)
        if spec.episode_index >= len(episodes):
            raise RuntimeError(f"Scenario produced {len(episodes)} episodes; requested index {spec.episode_index}")
        episode = episodes[spec.episode_index]
        episode_document = episode["config"].to_dict()

        manifest = RunManifest.create(spec, self.registry.dependency_manifest())
        manifest.scenario_hash = content_hash(scenario_document)
        manifest.episode_hash = content_hash(episode_document)
        manifest.enc_hash = _enc_hash(tuple(episode["config"].map_data_files))
        manifest.scenario_provenance = self._scenario_provenance(spec.scenario_id)
        manifest.executed_tracker = self._executed_tracker_id(spec, config)
        manifest.scenario_readiness_grade = self.capabilities._scenario_capability(
            spec.scenario_id,
            True,
        ).readiness_grade
        manifest.algorithm_readiness_grade = self.capabilities.grade("algorithm", spec.algorithm_id)
        manifest.tracker_readiness_grade = self.capabilities.grade("tracker", spec.tracker_id)
        manifest.capability_profile_id = capability_profile_id
        output_root = Path(spec.output_root)
        if not output_root.is_absolute():
            output_root = self.project_root / output_root
        writer = EvidenceWriter(output_root / manifest.run_id)
        writer.write_manifest(manifest)
        writer.write_episode(
            {
                "schema_version": spec.schema_version,
                "scenario_id": spec.scenario_id,
                "source": self._scenario_source(scenario_path),
                "source_hash": manifest.scenario_hash,
                "episode_hash": manifest.episode_hash,
                "enc_hash": manifest.enc_hash,
                "seed": spec.seeds.scenario,
                "provenance": manifest.scenario_provenance,
                "config": episode_document,
            }
        )
        artifact_sink = BoundedArtifactSink(writer)
        try:
            algorithm_config = copy.deepcopy(spec.algorithm_config)
            if spec.algorithm_id == "rrt":
                algorithm_config.setdefault("seed", spec.seeds.algorithm)
            factory_context = FactoryContext(
                requested_algorithm=spec.algorithm_id,
                algorithm_seed=spec.seeds.algorithm,
                strict_no_fallback=spec.strict_no_fallback,
                scenario_id=spec.scenario_id,
                tracker_id=manifest.executed_tracker,
                solve_period_override_s=spec.solve_period_s,
                deadline_mode=DeadlineMode(spec.deadline_mode),
                event_sink=writer.append_lifecycle_event,
                artifact_sink=artifact_sink,
            )
            algorithm = self.registry.build_algorithm(
                spec.algorithm_id,
                algorithm_config,
                factory_context=factory_context,
            )
            if isinstance(algorithm, CustomMPCAdapter):
                descriptor_document = algorithm.descriptor_document()
                manifest.algorithm_descriptor = descriptor_document
                manifest.algorithm_build_identity = descriptor_document["build_identity"]
            tracker = self.registry.build_tracker(spec.tracker_id, spec.tracker_config)
            colav_systems = [(0, algorithm)] if algorithm is not None else None
            trackers = [(0, tracker)] if tracker is not None else None

            simulator_config = SimulatorConfig.from_file(paths.simulator_config)
            simulator_config.verbose = False
            simulator_config.visualizer.show_liveplot = False
            simulator_config.visualizer.show_results = False
            simulator_config.visualizer.save_result_figures = False
            simulator_config.visualizer.save_liveplot_animation = False
            simulator_config.visualizer.matplotlib_backend = "Agg"
            manifest.ccd_step_tolerance_m = simulator_config.ccd_step_tolerance_m
            simulator = Simulator(config=simulator_config)
            session = SimulationSession(
                simulator=simulator,
                ship_list=episode["ship_list"],
                config=episode["config"],
                enc=enc,
                disturbance=episode["disturbance"],
                colav_systems=colav_systems,
                trackers=trackers,
                seed=spec.seeds.sensor,
                terminate_on_collision_or_grounding=spec.terminate_on_collision_or_grounding,
            )
            manifest.executed_algorithm = self._executed_algorithm_id(session)
            manifest.fallback_used = manifest.executed_algorithm != manifest.requested_algorithm
            if manifest.fallback_used and spec.strict_no_fallback:
                raise ColavExecutionError(
                    PlanStatus.INVALID_INPUT,
                    f"Requested algorithm {manifest.requested_algorithm} resolved to {manifest.executed_algorithm}",
                )
            writer.write_manifest(manifest)
        except Exception as exc:
            artifact_sink.close(timeout_s=2.0)
            self.persist_failure(manifest, writer, exc, [])
            raise ExperimentRunError(manifest, writer.run_dir) from exc
        return PreparedRun(spec, manifest, session, writer, episode_document, artifact_sink)

    @staticmethod
    def _executed_tracker_id(spec: RunSpec, config: scenario_config.ScenarioConfig) -> str:
        if spec.tracker_id != "scenario_default":
            return spec.tracker_id
        if not config.ship_list:
            return "kf"
        tracker_config = config.ship_list[0].tracker
        return "god" if tracker_config and tracker_config.god_tracker else "kf"

    @staticmethod
    def _executed_algorithm_id(session: SimulationSession) -> str:
        ship = session.ship_list[0]
        planner = ship.get_colav_data().get("planner", {})
        return str(planner.get("algorithm_id") or "nominal").lower()

    def _scenario_source(self, scenario_path: Path) -> str:
        try:
            return str(scenario_path.relative_to(self.project_root))
        except ValueError:
            return str(scenario_path)

    def _scenario_provenance(self, scenario_id: str) -> dict[str, Any]:
        provenance_path = self.scenarios_root / "paper" / "provenance.json"
        if not provenance_path.is_file():
            return {"source": "repository", "reconstructed": False, "confidence": "not_assessed"}
        entries = json.loads(provenance_path.read_text(encoding="utf-8"))
        return entries.get(
            scenario_id,
            {"source": "repository", "reconstructed": False, "confidence": "not_assessed"},
        )

    def finalize(self, prepared: PreparedRun) -> RunResult:
        prepared.artifact_sink.close(timeout_s=2.0)
        if prepared.session.state != SessionState.FINISHED:
            raise RuntimeError(f"Cannot finalize session in state {prepared.session.state.value}")
        prepared.manifest.state = prepared.session.state
        prepared.manifest.execution_outcome = RunOutcome.COMPLETED
        self._enforce_no_fallback(prepared)
        evaluator = (
            self.evaluator
            if self.evaluator.profile.profile_id == prepared.spec.evaluator_profile_id
            else Evaluator(prepared.spec.evaluator_profile_id)
        )
        evaluation = evaluator.evaluate(
            prepared.session.vessel_data(),
            prepared.session.enc,
            execution_context={
                "requested_algorithm": prepared.manifest.requested_algorithm,
                "executed_algorithm": prepared.manifest.executed_algorithm,
                "fallback_used": prepared.manifest.fallback_used,
                "run_completed": True,
                "solver": _solver_diagnostics(prepared.session.frames),
                "stress_only": prepared.session.config.name.startswith("romsdal_busy_water_80_stress"),
            },
        )
        prepared.manifest.evaluator_id = evaluation.evaluator_id
        prepared.manifest.evaluator_version = evaluation.schema_version
        prepared.manifest.evaluator_profile_id = evaluation.evaluator_profile_id
        prepared.manifest.evaluator_profile_hash = evaluation.evaluator_profile_hash
        prepared.manifest.formula_set_id = evaluation.formula_set_id
        prepared.manifest.formula_set_hash = evaluation.formula_set_hash
        prepared.manifest.evaluation_collision_oracle_id = evaluation.collision_oracle_id
        prepared.manifest.grounding_policy_id = str(evaluation.evidence["grounding_policy_id"])
        prepared.manifest.evaluation_schema_version = evaluation.schema_version
        prepared.manifest.evaluation_gate = evaluation.hard_gate.outcome.value
        prepared.manifest.reproduction_status = evaluation.reproduction_status
        trajectory_path = prepared.writer.write_trajectory(prepared.session.frames)
        prepared.manifest.trajectory_hash = _file_hash(trajectory_path)
        prepared.writer.write_events(prepared.session.events)
        prepared.writer.write_evaluation(evaluation)
        prepared.writer.write_run_metrics(_run_metrics(evaluation, prepared.session, prepared.manifest.fallback_used))
        prepared.writer.write_report(prepared.manifest, evaluation)
        prepared.writer.write_manifest(prepared.manifest)
        return RunResult(
            prepared.manifest,
            evaluation,
            prepared.run_dir,
            prepared.session,
            prepared.writer,
        )

    def run(self, spec: RunSpec) -> RunResult:
        prepared = self.prepare(spec)
        try:
            prepared.session.run_to_completion()
            return self.finalize(prepared)
        except Exception as exc:
            prepared.artifact_sink.close(timeout_s=2.0)
            self.persist_failure(
                prepared.manifest,
                prepared.writer,
                exc,
                prepared.session.frames,
                prepared.session.events,
            )
            raise ExperimentRunError(prepared.manifest, prepared.run_dir) from exc

    def replay(self, source_run_dir: Path, output_root: Path | None = None) -> RunResult:
        """Re-execute a recorded RunSpec and verify episode and trajectory hashes."""
        source_run_dir = source_run_dir.resolve()
        manifest_document = json.loads((source_run_dir / "manifest.json").read_text(encoding="utf-8"))
        source_episode = json.loads((source_run_dir / "episode.json").read_text(encoding="utf-8"))
        source_spec = RunSpec.from_dict(manifest_document["spec"])
        replay_spec = replace(
            source_spec,
            output_root=str(output_root or source_spec.output_root),
            replay_of_run_id=manifest_document["run_id"],
        )
        result = self.run(replay_spec)
        expected_episode_hash = source_episode["episode_hash"]
        source_trajectory_hash = manifest_document.get("trajectory_hash") or _file_hash(
            source_run_dir / "trajectory.parquet"
        )
        result.manifest.replay_verified = (
            result.manifest.episode_hash == expected_episode_hash
            and result.manifest.trajectory_hash == source_trajectory_hash
        )
        result.writer.write_manifest(result.manifest)
        if not result.manifest.replay_verified:
            raise RuntimeError(
                "Replay mismatch: "
                f"episode {result.manifest.episode_hash} != {expected_episode_hash} or "
                f"trajectory {result.manifest.trajectory_hash} != {source_trajectory_hash}"
            )
        return result

    @staticmethod
    def persist_failure(
        manifest: RunManifest,
        writer: EvidenceWriter,
        exc: Exception,
        frames: list[dict[str, Any]],
        events: list[dict[str, Any]] | None = None,
    ) -> None:
        status = exc.status if isinstance(exc, ColavExecutionError) else PlanStatus.NUMERICAL_FAILURE
        manifest.state = SessionState.FAILED
        manifest.execution_outcome = RunOutcome.SKIPPED if status == PlanStatus.DEPENDENCY_UNAVAILABLE else RunOutcome.FAILED
        manifest.failure_status = status.value
        manifest.failure_reason = str(exc)
        manifest.reproduction_status = "not_evaluated"
        failure_events = list(events or [])
        failure_events.append(
            {
                "sequence": len(frames),
                "sim_time": None,
                "type": "run_skipped" if manifest.execution_outcome == RunOutcome.SKIPPED else "run_failed",
                "details": {
                    "status": status.value,
                    "reason": str(exc),
                    "source": exc.source.value if isinstance(exc, ColavExecutionError) and exc.source is not None else None,
                },
            }
        )
        trajectory_path = writer.write_trajectory(frames)
        manifest.trajectory_hash = _file_hash(trajectory_path)
        writer.write_events(failure_events)
        writer.write_failed_evaluation(str(exc), status.value)
        writer.write_failure_report(manifest)
        writer.write_manifest(manifest)

    @staticmethod
    def _enforce_no_fallback(prepared: PreparedRun) -> None:
        fallback = False
        for frame in prepared.session.frames:
            for key, ship in frame.items():
                if not key.startswith("Ship") or not ship:
                    continue
                diagnostics = ship.get("colav", {}).get("diagnostics", {})
                fallback = fallback or bool(diagnostics.get("fallback_used", False))
        prepared.manifest.fallback_used = fallback
        if fallback and prepared.spec.strict_no_fallback:
            raise RuntimeError("Fallback detected in strict run")


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _solver_diagnostics(frames: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for frame in frames:
        for key, ship in frame.items():
            if not key.startswith("Ship") or not isinstance(ship, dict):
                continue
            planner = ship.get("colav", {}).get("planner", {})
            if isinstance(planner, dict) and planner.get("solver_executed"):
                records.append(planner)
    if not records:
        return {"status": "NOT_AVAILABLE", "solve_count": 0}
    elapsed = np.array(
        [float(item["elapsed_ms"]) for item in records if item.get("elapsed_ms") is not None],
        dtype=float,
    )
    iterations = [int(item["iterations"]) for item in records if item.get("iterations") is not None]
    objectives = [float(item["objective"]) for item in records if item.get("objective") is not None]
    statuses: dict[str, int] = {}
    for item in records:
        status = str(item.get("status", "UNKNOWN"))
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "status": "AVAILABLE",
        "solve_count": len(records),
        "status_counts": statuses,
        "elapsed_ms_mean": float(np.mean(elapsed)) if elapsed.size else None,
        "elapsed_ms_p95": float(np.percentile(elapsed, 95)) if elapsed.size else None,
        "iterations_mean": float(np.mean(iterations)) if iterations else None,
        "objective_last": objectives[-1] if objectives else None,
    }


def _run_metrics(evaluation: Any, session: SimulationSession, fallback_used: bool) -> dict[str, Any]:
    ship_info = {
        int(info["id"]): {
            "length_m": float(info["length"]),
            "width_m": float(info["width"]),
        }
        for info in session.ship_info.values()
    }
    ship0_pairs = []
    global_pairs = []
    for pair in evaluation.pair_results:
        first = ship_info[pair.ownship_id]
        second = ship_info[pair.target_id]
        radius_sum = 0.5 * np.hypot(first["length_m"], first["width_m"]) + 0.5 * np.hypot(
            second["length_m"],
            second["width_m"],
        )
        document = {
            "ship_ids": [pair.ownship_id, pair.target_id],
            "minimum_center_distance_m": pair.minimum_distance_m,
            "conservative_footprint_clearance_lower_bound_m": pair.minimum_distance_m - radius_sum,
            "collision": pair.collision,
            "collision_toc_s": pair.collision_toc_s,
            "collision_oracle_id": pair.collision_oracle_id,
        }
        global_pairs.append(document)
        if 0 in {pair.ownship_id, pair.target_id}:
            ship0_pairs.append(document)
    vessel_results = {item.vessel_id: item for item in evaluation.vessel_results}
    ship0_grounding = vessel_results.get(0)
    nearest = min(global_pairs, key=lambda item: item["minimum_center_distance_m"], default=None)
    active_counts = [
        sum(
            1
            for key, ship in frame.items()
            if key.startswith("Ship") and isinstance(ship, dict) and ship and ship.get("active", True)
        )
        for frame in session.frames
    ]
    risk_counts = [
        len(
            [
                item
                for item in (
                    frame.get("Ship0", {})
                    .get("colav", {})
                    .get("planner", {})
                    .get("algorithm_details", {})
                    .get("encounter_records", [])
                )
                if str(item.get("encounter", "clear")).lower() != "clear"
            ]
        )
        for frame in session.frames
        if frame.get("Ship0")
    ]
    step_times = np.asarray(session.step_times_ms, dtype=float)
    maneuver_samples = []
    phase_transitions = []
    last_phase = None
    for frame in session.frames:
        ship0 = frame.get("Ship0", {})
        planner = ship0.get("colav", {}).get("planner", {})
        if not planner.get("solver_executed"):
            continue
        details = planner.get("algorithm_details", {})
        phase = details.get("maneuver_phase")
        if phase and phase != last_phase:
            phase_transitions.append({"sim_time_s": float(planner.get("sim_time", 0.0)), "phase": phase})
            last_phase = phase
        maneuver_samples.append(
            {
                "heading_increment_rad": details.get("selected_heading_increment_rad"),
                "cross_track_error_m": details.get("cross_track_error_m"),
                "selected_speed_scale": details.get("selected_speed_scale"),
            }
        )
    signed_actions = [
        int(np.sign(float(item["heading_increment_rad"])))
        for item in maneuver_samples
        if item["heading_increment_rad"] is not None and abs(float(item["heading_increment_rad"])) >= np.deg2rad(0.5)
    ]
    steering_reversals = sum(
        current != previous for previous, current in zip(signed_actions, signed_actions[1:], strict=False)
    )
    cross_track_errors = [
        abs(float(item["cross_track_error_m"])) for item in maneuver_samples if item["cross_track_error_m"] is not None
    ]
    speed_scales = [
        float(item["selected_speed_scale"]) for item in maneuver_samples if item["selected_speed_scale"] is not None
    ]
    return {
        "schema_version": "busy_water_metrics.v1",
        "ship0_safety": {
            "fallback_used": bool(fallback_used),
            "collision_count": sum(item["collision"] for item in ship0_pairs),
            "grounded": ship0_grounding.grounded if ship0_grounding else None,
            "grounding_clearance_m": ship0_grounding.grounding_distance_m if ship0_grounding else None,
            "targets": ship0_pairs,
        },
        "global_world_events": {
            "collision_count": sum(item["collision"] for item in global_pairs),
            "grounding_count": sum(item.grounded is True for item in evaluation.vessel_results),
            "nearest_pair": nearest,
            "colliding_pairs": [item for item in global_pairs if item["collision"]],
            "grounded_ship_ids": [item.vessel_id for item in evaluation.vessel_results if item.grounded is True],
        },
        "traffic_load": {
            "configured_ship_count": len(session.ship_list),
            "maximum_active_ship_count": max(active_counts, default=0),
            "maximum_risk_target_count": max(risk_counts, default=0),
            "step_count": len(session.frames),
            "step_time_ms_p50": float(np.percentile(step_times, 50)) if step_times.size else None,
            "step_time_ms_p95": float(np.percentile(step_times, 95)) if step_times.size else None,
            "step_time_ms_max": float(np.max(step_times)) if step_times.size else None,
            "solver": _solver_diagnostics(session.frames),
        },
        "maneuver_quality_observations": {
            "phase_transitions": phase_transitions,
            "steering_reversal_count": steering_reversals,
            "maximum_absolute_cross_track_error_m": max(cross_track_errors, default=None),
            "final_absolute_cross_track_error_m": cross_track_errors[-1] if cross_track_errors else None,
            "minimum_selected_speed_scale": min(speed_scales, default=None),
            "final_selected_speed_scale": speed_scales[-1] if speed_scales else None,
            "astern_passing": "NOT_EVALUATED",
            "legal_colreg_compliance": "NOT_EVALUATED",
        },
    }


@lru_cache(maxsize=8)
def _enc_hash(sources: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for source_value in sorted(sources):
        source = Path(source_value).resolve()
        if not source.exists():
            raise FileNotFoundError(f"ENC source not found: {source}")
        try:
            source_id = source.relative_to(paths.enc_data.resolve()).as_posix()
        except ValueError:
            source_id = source.as_posix()
        digest.update(source_id.encode("utf-8"))
        files = [source] if source.is_file() else sorted(path for path in source.rglob("*") if path.is_file())
        for path in files:
            relative = path.name if source.is_file() else path.relative_to(source).as_posix()
            digest.update(relative.encode("utf-8"))
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()
