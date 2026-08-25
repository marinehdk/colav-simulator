"""Unified offline, replay, batch, and Web experiment preparation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from collections.abc import Mapping
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
from colav_simulator.core.colav.encounter_lifecycle import EncounterLifecycle
from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.core.models import KinematicCSOGParams
from colav_simulator.evaluation import Evaluator, EvaluatorResult
from colav_simulator.experiment.capabilities import CapabilityCatalog
from colav_simulator.experiment.contracts import (
    InternalExecutionPurpose,
    RunManifest,
    RunOutcome,
    RunSpec,
    SessionState,
    content_hash,
)
from colav_simulator.experiment.persistence import (
    BoundedArtifactSink,
    EvidenceWriter,
    trajectory_artifact_semantic_hash,
    trajectory_semantic_hash,
)
from colav_simulator.experiment.session import SimulationSession
from colav_simulator.historical_replay import (
    HistoricalActorShip,
    HistoricalCounterfactualActorShip,
    HistoricalReplayRequest,
)
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


@dataclass(frozen=True)
class HistoricalRuntimeNavigationMargin:
    """Typed margin derived from sealed dimensions and runtime dynamics."""

    policy_id: str
    hull_extent_m: float
    one_step_displacement_m: float
    value_m: float
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "hull_extent_m": self.hull_extent_m,
            "one_step_displacement_m": self.one_step_displacement_m,
            "value_m": self.value_m,
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class HistoricalRuntimeMapProof:
    """Proof that a Historical runtime map is bounded and profile-contained."""

    origin_enu: tuple[float, float]
    size_m: tuple[float, float]
    qualified_profile_extent_projected: tuple[float, float, float, float]
    actor_state_count: int
    nominal_route_point_count: int
    reachable_radius_m: float
    run_duration_s: float
    post_t0_duration_s: float
    speed_bound_mps: float
    speed_bound_sources: tuple[str, ...]
    navigation_margin: HistoricalRuntimeNavigationMargin
    rounding_grid_m: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": "historical-runtime-map.v2",
            "origin_enu": list(self.origin_enu),
            "size_m": list(self.size_m),
            "qualified_profile_extent_projected": list(self.qualified_profile_extent_projected),
            "actor_state_count": self.actor_state_count,
            "nominal_route_point_count": self.nominal_route_point_count,
            "reachable_radius_m": self.reachable_radius_m,
            "run_duration_s": self.run_duration_s,
            "post_t0_duration_s": self.post_t0_duration_s,
            "speed_bound_mps": self.speed_bound_mps,
            "speed_bound_sources": list(self.speed_bound_sources),
            "navigation_margin": self.navigation_margin.to_dict(),
            "rounding_grid_m": self.rounding_grid_m,
        }


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
        scenarios.extend(
            self.capabilities.annotate_scenario(document)
            for document in self._historical_scenario_documents()
        )
        return scenarios

    def _historical_scenario_documents(self) -> list[dict[str, Any]]:
        """List bounded Historical AIS scenes through the same catalog seam.

        Listing uses a cheap source-presence check; archive content identity
        stays fail-closed at Counterfactual binding time (prepare path).
        """
        from colav_simulator.historical_scenario_catalog import (  # noqa: PLC0415
            HAIS_ARCHIVE_ENV_VAR,
            HistoricalAISScenarioCatalog,
        )

        raw_path = os.environ.get(HAIS_ARCHIVE_ENV_VAR, "").strip()
        source_present = bool(raw_path) and Path(raw_path).expanduser().is_file()
        documents = []
        for entry in HistoricalAISScenarioCatalog().list():
            window = entry["current_window"]
            documents.append(
                {
                    "id": entry["id"],
                    "name": entry["display_name"],
                    "type": str(entry.get("kind", "HISTORICAL_AIS")),
                    "dt": 1.0,
                    "t_start": 0.0,
                    "t_end": float(window.get("duration_s", 60.0)),
                    "ships": int(window.get("runtime_actor_count", 0)),
                    "provenance": {
                        "source": "HistoricalAISScenarioCatalog",
                        "reconstructed": True,
                        "confidence": "source_presence_only",
                    },
                    "valid": source_present,
                    "reason": None if source_present else f"{HAIS_ARCHIVE_ENV_VAR} is not configured",
                    "historical_ais": {
                        "start_utc": window["start_utc"],
                        "end_utc": window["end_utc"],
                        "t0_utc": window["t0_utc"],
                        "bbox": list(window["bbox"]),
                        "reference_mmsi": window["reference_mmsi"],
                        "target_mmsi": list(window["target_mmsi"]),
                        "runtime_actor_count": int(window.get("runtime_actor_count", 0)),
                        "modes": list(entry.get("modes", ())),
                        "limitations": list(entry.get("limitations", ())),
                        "source_present": source_present,
                    },
                }
            )
        return documents

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

    def prepare(self, spec: RunSpec) -> PreparedRun:
        """Prepare one product run through the published exact-tuple policy."""
        self.capabilities.policy.require_integrations(spec.algorithm_id, spec.tracker_id)
        self.capabilities.policy.validate_domain_profile(spec.algorithm_id, spec.domain_profile)
        historical_mode = str((spec.historical_replay or {}).get("mode", "")).upper()
        if historical_mode == "COUNTERFACTUAL":
            capability_tuple = spec.capability_tuple
            if capability_tuple is None:
                raise ColavExecutionError(
                    PlanStatus.INVALID_INPUT,
                    "Counterfactual product run requires an explicit exact capability tuple",
                )
            cross_scene_capability_evidence = (
                spec.historical_scenario_id is not None
                and isinstance(spec.algorithm_capability_evidence, dict)
                and spec.algorithm_capability_evidence.get("binding_role") == "ALGORITHM_CAPABILITY_ONLY"
                and spec.algorithm_capability_evidence.get("geometry_equivalence") is False
            )
            if capability_tuple[1] != spec.scenario_id and not cross_scene_capability_evidence:
                raise ColavExecutionError(
                    PlanStatus.INVALID_INPUT,
                    "Counterfactual capability tuple scenario differs from RunSpec",
                )
            if capability_tuple[2] != spec.algorithm_id or capability_tuple[3] != spec.tracker_id:
                raise ColavExecutionError(
                    PlanStatus.INVALID_INPUT,
                    "Counterfactual capability tuple integration differs from RunSpec",
                )
            capability_profile_id = self.capabilities.validate(*capability_tuple)
            normalized_spec = (
                spec
                if spec.validation_rule_id is not None
                else replace(spec, validation_rule_id=capability_tuple[0])
            )
            return self._prepare(normalized_spec, capability_profile_id=capability_profile_id)
        if spec.validation_rule_id is None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Product RunSpec requires an explicit validation_rule_id and exact capability tuple",
            )
        if spec.historical_replay is not None or spec.historical_scenario_id is not None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Historical Replay requires the explicit prepare_internal seam",
            )
        capability_profile_id = self.capabilities.validate(
            spec.validation_rule_id,
            spec.scenario_id,
            spec.algorithm_id,
            spec.tracker_id,
        )
        return self._prepare(spec, capability_profile_id=capability_profile_id)

    def prepare_internal(self, spec: RunSpec, *, purpose: InternalExecutionPurpose) -> PreparedRun:
        """Prepare one explicitly typed internal Replay or evaluator baseline run."""
        if not isinstance(purpose, InternalExecutionPurpose):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Internal execution requires a typed InternalExecutionPurpose",
            )
        capability_tuple = spec.capability_tuple
        if capability_tuple is None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Historical internal execution requires an exact internal capability tuple",
            )
        historical_mode = str((spec.historical_replay or {}).get("mode", "")).upper()
        if purpose is InternalExecutionPurpose.HISTORICAL_REPLAY and historical_mode != "HISTORICAL_REPLAY":
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "HISTORICAL_REPLAY purpose requires a sealed Historical Replay request",
            )
        if purpose is InternalExecutionPurpose.EVALUATOR_BASELINE and spec.historical_replay is not None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "EVALUATOR_BASELINE purpose cannot carry Historical runtime actors",
            )
        capability_profile_id = self.capabilities.validate_internal(
            *capability_tuple,
            purpose=purpose,
        )
        return self._prepare(spec, capability_profile_id=capability_profile_id)

    def _prepare(  # noqa: C901, PLR0912, PLR0915
        self,
        spec: RunSpec,
        *,
        capability_profile_id: str,
    ) -> PreparedRun:
        historical_request = (
            HistoricalReplayRequest.from_dict(spec.historical_replay) if spec.historical_replay is not None else None
        )
        if spec.historical_scenario_id is not None and historical_request is None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Historical scenario identity requires a sealed Historical Replay request",
            )
        scenario_path = None if spec.historical_scenario_id is not None else self.resolve_scenario(spec.scenario_id)
        counterfactual_mode = historical_request is not None and historical_request.mode == "COUNTERFACTUAL"
        runtime_map_proof: HistoricalRuntimeMapProof | None = None
        if historical_request is not None and not counterfactual_mode and spec.algorithm_id != "nominal":
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Historical Replay is non-counterfactual and cannot execute a COLAV algorithm",
            )
        if spec.historical_scenario_id is not None:
            runtime_map_proof = _historical_runtime_map_proof(historical_request)
            config = _historical_runtime_config(
                spec,
                historical_request,
                runtime_map_proof=runtime_map_proof,
            )
            source_version = content_hash(config.to_dict())
        elif spec.scenario_override is None:
            if scenario_path is None:  # pragma: no cover - guarded by Historical branch
                raise RuntimeError("scenario source path is unavailable")
            config = cp.extract(scenario_config.ScenarioConfig, scenario_path, paths.scenario_schema)
            source_version = scenario_path.stat().st_mtime_ns
        else:
            override_document = copy.deepcopy(spec.scenario_override)
            cp.validate(override_document, futils.read_yaml_into_dict(paths.scenario_schema))
            config = scenario_config.ScenarioConfig.from_dict(override_document)
            source_version = content_hash(override_document)
        config.filename = (
            f"{spec.historical_scenario_id}.historical"
            if spec.historical_scenario_id is not None
            else scenario_path.name  # type: ignore[union-attr]
        )
        if spec.dt is not None:
            config.dt_sim = spec.dt
        if spec.t_end is not None:
            config.t_end = spec.t_end
        if historical_request is not None:
            if spec.dt is None and historical_request.dt_sim is not None:
                config.dt_sim = historical_request.dt_sim
            if spec.t_end is None and historical_request.t_end_s is not None:
                config.t_end = historical_request.t_end_s
        if spec.reload_enc:
            config.new_load_of_map_data = True
        if (
            historical_request is None
            and spec.algorithm_id == "nominal"
            and config.ship_list
            and config.ship_list[0].colav is not None
        ):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "nominal requires scenario guidance; the selected scenario embeds an onboard COLAV algorithm",
            )
        scenario_document = config.to_dict()
        if historical_request is not None:
            scenario_document["historical_replay"] = historical_request.to_dict()
        generator = ScenarioGenerator(seed=spec.seeds.scenario)
        episode_count = max(1, spec.episode_index + 1)
        enc_cache_key = (
            spec.historical_scenario_id or str(scenario_path.resolve()),  # type: ignore[union-attr]
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
        if historical_request is not None:
            if counterfactual_mode:
                episode["ship_list"] = [
                    (
                        HistoricalCounterfactualActorShip(
                            actor,
                            historical_request.actor_set.profile,
                            t0_s=float(historical_request.counterfactual_t0_s),
                            nominal_intent=historical_request.nominal_intent or {},
                            handoff_tolerance_m=historical_request.handoff_tolerance_m,
                            handoff_tolerance_mps=historical_request.handoff_tolerance_mps,
                            handoff_tolerance_rad=historical_request.handoff_tolerance_rad,
                            simulation_end_s=float(episode["config"].t_end),
                        )
                        if actor.actor_id == historical_request.ownship_actor_id
                        else HistoricalActorShip(
                            actor,
                            historical_request.actor_set.profile,
                        )
                    )
                    for actor in historical_request.actor_set.actors
                ]
            else:
                episode["ship_list"] = [
                    HistoricalActorShip(
                        actor,
                        historical_request.actor_set.profile,
                    )
                    for actor in historical_request.actor_set.actors
                ]
            episode["config"].name = historical_request.scenario_name
            episode["config"].t_start = 0.0
            episode["config"].dt_sim = config.dt_sim
            episode["config"].t_end = config.t_end
            episode["config"].ship_list = []
        episode_document = episode["config"].to_dict()
        if historical_request is not None:
            episode_document["historical_replay"] = historical_request.to_dict()
            if counterfactual_mode and runtime_map_proof is None:
                runtime_map_proof = _historical_runtime_map_proof(historical_request)
            if runtime_map_proof is not None:
                episode_document["historical_runtime_map"] = runtime_map_proof.to_dict()

        manifest = RunManifest.create(spec, self.registry.dependency_manifest())
        manifest.scenario_hash = content_hash(scenario_document)
        manifest.episode_hash = content_hash(episode_document)
        manifest.enc_hash = _enc_hash(tuple(episode["config"].map_data_files))
        manifest.scenario_provenance = (
            {
                "source": "HistoricalAISScenarioCatalog",
                "reconstructed": True,
                "confidence": "content_addressed",
                "historical_scenario_id": spec.historical_scenario_id,
                "algorithm_capability_evidence": spec.algorithm_capability_evidence,
            }
            if spec.historical_scenario_id is not None
            else self._scenario_provenance(spec.scenario_id)
        )
        manifest.executed_tracker = self._executed_tracker_id(spec, config)
        manifest.scenario_readiness_grade = self.capabilities._scenario_capability(
            spec.scenario_id,
            True,
        ).readiness_grade
        manifest.algorithm_readiness_grade = self.capabilities.grade("algorithm", spec.algorithm_id)
        manifest.tracker_readiness_grade = self.capabilities.grade("tracker", spec.tracker_id)
        manifest.capability_profile_id = capability_profile_id
        if historical_request is not None:
            manifest.historical_replay_evidence = historical_request.evidence.to_dict()
            manifest.historical_execution_mode = historical_request.mode
            manifest.historical_case_digest = historical_request.case_digest
            manifest.historical_scenario_id = spec.historical_scenario_id
            if not counterfactual_mode:
                manifest.diagnostic_only = True
                manifest.diagnostic_only_reasons = [
                    *manifest.diagnostic_only_reasons,
                    "HISTORICAL_REPLAY/non-counterfactual",
                ]
        output_root = Path(spec.output_root)
        if not output_root.is_absolute():
            output_root = self.project_root / output_root
        writer = EvidenceWriter(output_root / manifest.run_id)
        writer.write_manifest(manifest)
        writer.write_episode(
            {
                "schema_version": spec.schema_version,
                "scenario_id": spec.scenario_id,
                "source": (
                    "historical-runtime-template"
                    if spec.historical_scenario_id is not None
                    else self._scenario_source(scenario_path)  # type: ignore[arg-type]
                ),
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
            threat_management_coordinator = ThreatManagementCoordinator(
                lifecycle=EncounterLifecycle(event_sink=writer.append_lifecycle_event),
                domain_profile=spec.domain_profile,
            )
            algorithm_config = copy.deepcopy(spec.algorithm_config)
            if spec.algorithm_id == "rrt":
                algorithm_config.setdefault("seed", spec.seeds.algorithm)
            factory_context = FactoryContext(
                requested_algorithm=spec.algorithm_id,
                algorithm_seed=spec.seeds.algorithm,
                strict_no_fallback=spec.strict_no_fallback,
                scenario_id=spec.scenario_id,
                tracker_id=manifest.executed_tracker,
                scenario_target_count=_scenario_target_count(spec, episode=episode),
                solve_period_override_s=spec.solve_period_s,
                deadline_mode=DeadlineMode(spec.deadline_mode),
                event_sink=writer.append_lifecycle_event,
                artifact_sink=artifact_sink,
                threat_management_coordinator=threat_management_coordinator,
                domain_profile=spec.domain_profile,
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
            tracker_id_for_build = (
                manifest.executed_tracker
                if historical_request is not None and spec.tracker_id == "scenario_default"
                else spec.tracker_id
            )
            tracker = self.registry.build_tracker(tracker_id_for_build, spec.tracker_config)
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
                threat_management_coordinator=threat_management_coordinator,
            )
            manifest.executed_algorithm = self._executed_algorithm_id(session)
            if counterfactual_mode:
                manifest.executed_algorithm = spec.algorithm_id
                manifest.fallback_used = spec.algorithm_id != "nominal" and algorithm is None
            elif historical_request is not None:
                manifest.executed_algorithm = "historical_replay"
                manifest.fallback_used = False
            else:
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
        prepared.manifest.trajectory_artifact_hash = _file_hash(trajectory_path)
        prepared.manifest.trajectory_semantic_hash = trajectory_semantic_hash(prepared.session.frames)
        prepared.manifest.trajectory_hash = prepared.manifest.trajectory_semantic_hash
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
        return self._run_prepared(self.prepare(spec))

    def run_internal(self, spec: RunSpec, *, purpose: InternalExecutionPurpose) -> RunResult:
        """Execute one explicitly typed internal Replay or evaluator baseline run."""
        return self._run_prepared(self.prepare_internal(spec, purpose=purpose))

    def _run_prepared(self, prepared: PreparedRun) -> RunResult:
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
        historical_mode = str((replay_spec.historical_replay or {}).get("mode", "")).upper()
        result = (
            self.run_internal(replay_spec, purpose=InternalExecutionPurpose.HISTORICAL_REPLAY)
            if historical_mode == "HISTORICAL_REPLAY"
            else self.run(replay_spec)
        )
        expected_episode_hash = source_episode["episode_hash"]
        source_trajectory_hash = manifest_document.get("trajectory_semantic_hash") or trajectory_artifact_semantic_hash(
            source_run_dir / "trajectory.parquet"
        )
        result.manifest.replay_verified = (
            result.manifest.episode_hash == expected_episode_hash
            and result.manifest.trajectory_semantic_hash == source_trajectory_hash
        )
        result.writer.write_manifest(result.manifest)
        if not result.manifest.replay_verified:
            raise RuntimeError(
                "Replay mismatch: "
                f"episode {result.manifest.episode_hash} != {expected_episode_hash} or "
                f"trajectory semantic hash {result.manifest.trajectory_semantic_hash} != {source_trajectory_hash}"
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
        manifest.trajectory_artifact_hash = _file_hash(trajectory_path)
        manifest.trajectory_semantic_hash = trajectory_semantic_hash(frames)
        manifest.trajectory_hash = manifest.trajectory_semantic_hash
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


def _historical_runtime_config(
    spec: RunSpec,
    request: HistoricalReplayRequest | None,
    *,
    runtime_map_proof: HistoricalRuntimeMapProof | None = None,
) -> scenario_config.ScenarioConfig:
    """Build a bounded loader config; Historical Actors replace its placeholder ship.

    The chart qualification profile remains the authority for source, coverage,
    and hazards. Runtime ENC loading only needs a bounded window containing the
    sealed actor samples and, for Counterfactual, the sealed nominal route plus
    its reachable post-T0 envelope. Loading the former 30 x 40 km rectangle made
    ``seacharts`` preprocess an unnecessarily large chart and made constrained
    triangulation dominate every run.
    """
    if request is None:
        raise ColavExecutionError(PlanStatus.INVALID_INPUT, "Historical scenario has no sealed actor request")
    proof = runtime_map_proof or _historical_runtime_map_proof(request)
    ownship = request.actor_set.actor(request.ownship_actor_id)
    sample = ownship.samples[0]
    north, east, velocity_north, velocity_east = sample.state_vxvy
    speed = math.hypot(velocity_north, velocity_east)
    course_deg = math.degrees(math.atan2(velocity_east, velocity_north)) % 360.0
    duration = float(request.t_end_s or spec.t_end or max(actor.last_time_s for actor in request.actor_set.actors) + 1.0)
    step = float(request.dt_sim or spec.dt or request.actor_set.profile.time_step_s)
    map_origin_enu, map_size = _historical_runtime_map(request, runtime_map_proof=proof)
    document = {
        "name": spec.historical_scenario_id,
        "save_scenario": False,
        "t_start": 0.0,
        "t_end": duration,
        "dt_sim": step,
        "type": "MS",
        "utm_zone": request.utm_zone,
        "map_data_files": ["More_og_Romsdal_utm33.gdb"],
        "map_size": list(map_size),
        "map_origin_enu": list(map_origin_enu),
        "new_load_of_map_data": True,
        "n_episodes": 1,
        "n_random_ships": 0,
        "ship_list": [
            {
                "csog_state": [north, east, speed, course_deg],
                "waypoints": [[north, north + 1.0], [east, east]],
                "speed_plan": [speed, speed],
                "id": ownship.actor_id,
                "mmsi": ownship.mmsi,
                "guidance": {
                    "los": {
                        "pass_angle_threshold": 80.0,
                        "R_a": 40.0,
                        "K_p": 0.015,
                        "K_i": 0.0,
                        "max_cross_track_error_int": 200.0,
                        "cross_track_error_int_threshold": 30.0,
                    }
                },
                "controller": {"pass_through_cs": ""},
                "model": {
                    "csog": {
                        "draft": 3.0,
                        "length": ownship.length_m,
                        "width": ownship.width_m,
                        "T_chi": 3.0,
                        "T_U": 5.0,
                        "r_max": 4.0,
                        "U_min": 0.0,
                        "U_max": proof.speed_bound_mps,
                    }
                },
            }
        ],
    }
    return scenario_config.ScenarioConfig.from_dict(document)


def _historical_runtime_map(
    request: HistoricalReplayRequest,
    *,
    runtime_map_proof: HistoricalRuntimeMapProof | None = None,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return the profile-contained map derived by :func:`_historical_runtime_map_proof`."""
    proof = runtime_map_proof or _historical_runtime_map_proof(request)
    return proof.origin_enu, proof.size_m


def _historical_speed_bound_mps(request: HistoricalReplayRequest) -> float:
    """Return the explicit speed bound enforced by the runtime CSOG model."""
    observed_speeds = [
        math.hypot(sample.state_vxvy[2], sample.state_vxvy[3])
        for actor in request.actor_set.actors
        for sample in actor.samples
    ]
    intent_speed = float((request.nominal_intent or {}).get("speed_mps", 0.0))
    model_speed = float(KinematicCSOGParams().U_max)
    candidates = (*observed_speeds, intent_speed, model_speed)
    if not candidates or not all(math.isfinite(value) and value >= 0.0 for value in candidates):
        raise ValueError("Historical runtime speed bound lacks finite source evidence")
    return max(candidates)


def _historical_runtime_map_proof(request: HistoricalReplayRequest) -> HistoricalRuntimeMapProof:
    """Prove a finite runtime window from actor, route, duration, and ENC facts."""
    enc_evidence = request.enc_preflight_evidence
    if enc_evidence is None:
        raise ValueError("qualified ENC projected extent evidence is required for Historical runtime")
    profile_extent = enc_evidence.supported_extent_projected
    profile_min_east, profile_min_north, profile_max_east, profile_max_north = profile_extent
    speed_bound_mps = _historical_speed_bound_mps(request)
    run_duration_s = float(
        request.t_end_s
        if request.t_end_s is not None
        else max(actor.last_time_s for actor in request.actor_set.actors)
        + float(request.dt_sim or request.actor_set.profile.time_step_s)
    )
    if not math.isfinite(run_duration_s) or run_duration_s <= 0.0:
        raise ValueError("Historical runtime duration must be finite and positive")
    dt_sim = float(request.dt_sim or request.actor_set.profile.time_step_s)
    if not math.isfinite(dt_sim) or dt_sim <= 0.0:
        raise ValueError("Historical runtime timestep must be finite and positive")
    post_t0_duration_s = (
        max(0.0, run_duration_s - float(request.counterfactual_t0_s or 0.0))
        if request.mode == "COUNTERFACTUAL"
        else 0.0
    )

    points_enu: list[tuple[float, float]] = [
        (sample.state_vxvy[1], sample.state_vxvy[0])
        for actor in request.actor_set.actors
        for sample in actor.samples
    ]
    actor_state_count = len(points_enu)
    route_points = tuple(
        tuple(float(value) for value in point)
        for point in (request.nominal_intent or {}).get("route_points_vxvy", ())
    )
    points_enu.extend((east, north) for north, east in route_points)
    reachable_radius_m = speed_bound_mps * post_t0_duration_s
    if reachable_radius_m:
        handoff = request.actor_set.actor(request.ownship_actor_id).sample_at(
            float(request.counterfactual_t0_s or 0.0)
        )
        if handoff is None:
            raise ValueError("Historical runtime map lacks an ownship state at Counterfactual T0")
        north, east = handoff.state_vxvy[:2]
        points_enu.extend(
            (
                (east - reachable_radius_m, north),
                (east + reachable_radius_m, north),
                (east, north - reachable_radius_m),
                (east, north + reachable_radius_m),
            )
        )
    if not points_enu:
        raise ValueError("Historical Replay requires at least one finite actor position")
    if not all(math.isfinite(value) for point in points_enu for value in point):
        raise ValueError("Historical Replay actor/map positions must be finite")

    dimensions = [
        max(float(actor.length_m), float(actor.width_m))
        for actor in request.actor_set.actors
        if actor.length_m is not None and actor.width_m is not None
    ]
    if len(dimensions) != len(request.actor_set.actors):
        raise ValueError("Historical runtime navigation margin lacks vessel-dimension evidence")
    hull_extent_m = max(dimensions)
    one_step_displacement_m = speed_bound_mps * dt_sim
    navigation_margin = HistoricalRuntimeNavigationMargin(
        policy_id="historical-runtime-navigation-margin.v1",
        hull_extent_m=hull_extent_m,
        one_step_displacement_m=one_step_displacement_m,
        value_m=max(hull_extent_m, one_step_displacement_m),
        sources=(
            "sealed_actor_dimensions",
            "sealed_runtime_speed_bound",
            "run_spec_dt",
        ),
    )
    grid_m = navigation_margin.value_m
    east_values = [point[0] for point in points_enu]
    north_values = [point[1] for point in points_enu]
    min_east = math.floor((min(east_values) - navigation_margin.value_m) / grid_m) * grid_m
    max_east = math.ceil((max(east_values) + navigation_margin.value_m) / grid_m) * grid_m
    min_north = math.floor((min(north_values) - navigation_margin.value_m) / grid_m) * grid_m
    max_north = math.ceil((max(north_values) + navigation_margin.value_m) / grid_m) * grid_m
    if (
        min_east < profile_min_east
        or min_north < profile_min_north
        or max_east > profile_max_east
        or max_north > profile_max_north
    ):
        raise ValueError("Historical runtime map exceeds the qualified ENC profile extent")
    return HistoricalRuntimeMapProof(
        origin_enu=(min_east, min_north),
        size_m=(max_east - min_east, max_north - min_north),
        qualified_profile_extent_projected=profile_extent,
        actor_state_count=actor_state_count,
        nominal_route_point_count=len(route_points),
        reachable_radius_m=reachable_radius_m,
        run_duration_s=run_duration_s,
        post_t0_duration_s=post_t0_duration_s,
        speed_bound_mps=speed_bound_mps,
        speed_bound_sources=(
            "sealed_actor_sample_velocity",
            "sealed_nominal_intent_speed" if request.nominal_intent else "not_applicable",
            "KinematicCSOGParams.U_max",
        ),
        navigation_margin=navigation_margin,
        rounding_grid_m=grid_m,
    )


def _scenario_target_count(spec: RunSpec, *, episode: Mapping[str, Any] | None = None) -> int | None:
    """Derive target-ship count from the generated episode or sealed inputs.

    The generated episode is authoritative for normal YAML scenarios: random
    and fixed multiship generators can materialize actors not represented in
    ``RunSpec.scenario_override``.  Historical inputs remain supported as a
    fallback so the helper is useful before episode materialization too.
    """
    if episode is not None:
        ship_list = episode.get("ship_list")
        if isinstance(ship_list, (list, tuple)) and len(ship_list) > 1:
            return len(ship_list) - 1
    override = spec.scenario_override or {}
    ship_list = override.get("ship_list")
    if isinstance(ship_list, list) and len(ship_list) > 1:
        return len(ship_list) - 1
    historical = spec.historical_replay
    if isinstance(historical, Mapping):
        actor_set = historical.get("actor_set")
        actors = actor_set.get("actors") if isinstance(actor_set, Mapping) else None
        if isinstance(actors, list) and actors:
            try:
                ownship_actor_id = int(historical.get("ownship_actor_id", 0))
                actor_ids = [int(actor["actor_id"]) for actor in actors if isinstance(actor, Mapping)]
            except (KeyError, TypeError, ValueError):
                actor_ids = []
            if len(actor_ids) == len(actors) and ownship_actor_id in actor_ids:
                target_count = sum(actor_id != ownship_actor_id for actor_id in actor_ids)
                if target_count > 0:
                    return target_count
    return None


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
