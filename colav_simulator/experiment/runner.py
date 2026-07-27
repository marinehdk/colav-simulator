"""Unified offline, replay, batch, and Web experiment preparation."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import colav_simulator.common.config_parsing as cp
from colav_simulator import scenario_config
from colav_simulator.common import paths
from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.evaluation import Evaluator, EvaluatorResult
from colav_simulator.experiment.capabilities import CapabilityCatalog
from colav_simulator.experiment.contracts import RunManifest, RunSpec, SessionState, content_hash
from colav_simulator.experiment.persistence import EvidenceWriter
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

    def prepare(self, spec: RunSpec) -> PreparedRun:  # noqa: PLR0915
        scenario_path = self.resolve_scenario(spec.scenario_id)
        config = cp.extract(scenario_config.ScenarioConfig, scenario_path, paths.scenario_schema)
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
        episodes, enc = generator.generate(
            config=config,
            n_episodes=episode_count,
            show_plots=False,
            save_scenario=False,
        )
        if spec.episode_index >= len(episodes):
            raise RuntimeError(f"Scenario produced {len(episodes)} episodes; requested index {spec.episode_index}")
        episode = episodes[spec.episode_index]
        episode_document = episode["config"].to_dict()

        manifest = RunManifest.create(spec, self.registry.dependency_manifest())
        manifest.scenario_hash = content_hash(scenario_document)
        manifest.episode_hash = content_hash(episode_document)
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
                "seed": spec.seeds.scenario,
                "provenance": manifest.scenario_provenance,
                "config": episode_document,
            }
        )
        try:
            algorithm_config = copy.deepcopy(spec.algorithm_config)
            if spec.algorithm_id == "rrt":
                algorithm_config.setdefault("seed", spec.seeds.algorithm)
            algorithm = self.registry.build_algorithm(spec.algorithm_id, algorithm_config)
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
            self.persist_failure(manifest, writer, exc, [])
            raise ExperimentRunError(manifest, writer.run_dir) from exc
        return PreparedRun(spec, manifest, session, writer, episode_document)

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
        if prepared.session.state != SessionState.FINISHED:
            raise RuntimeError(f"Cannot finalize session in state {prepared.session.state.value}")
        evaluation = self.evaluator.evaluate(prepared.session.vessel_data(), prepared.session.enc)
        prepared.manifest.state = prepared.session.state
        prepared.manifest.evaluator_id = evaluation.evaluator_id
        prepared.manifest.reproduction_status = evaluation.reproduction_status
        self._enforce_no_fallback(prepared)
        trajectory_path = prepared.writer.write_trajectory(prepared.session.frames)
        prepared.manifest.trajectory_hash = _file_hash(trajectory_path)
        prepared.writer.write_events(prepared.session.events)
        prepared.writer.write_evaluation(evaluation)
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
        manifest.failure_status = status.value
        manifest.failure_reason = str(exc)
        manifest.reproduction_status = "not_evaluated"
        failure_events = list(events or [])
        failure_events.append(
            {
                "sequence": len(frames),
                "sim_time": None,
                "type": "run_failed",
                "details": {"status": status.value, "reason": str(exc)},
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
