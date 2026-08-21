from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from shapely.geometry import MultiPolygon

from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_replay import (
    HistoricalActorSampleKind,
    HistoricalAISReconstructionProfile,
    HistoricalAISReconstructor,
    HistoricalReplayFactory,
    HistoricalReplayRequest,
)
from colav_simulator.simulator import Config as SimulatorConfig
from colav_simulator.simulator import Simulator


def _write_csv(path: Path, rows: str) -> Path:
    path.write_text(rows, encoding="utf-8")
    return path


def _read(path: Path) -> object:
    return HistoricalAISDatasetReader(path).read(HistoricalAISSelection())


def test_reconstruction_profile_is_versioned_and_semantically_stable() -> None:
    first = HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0)
    second = HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0)

    assert first.profile_id == "historical-actor-reconstruction.v1"
    assert first.digest == second.digest
    assert first.to_dict()["projection_crs"] == "EPSG:32633"


def test_reconstructor_separates_observed_and_interpolated_samples(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "replay.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0,4,90,40,8\n",
    )

    actors = HistoricalAISReconstructor().reconstruct(
        _read(source),
        HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0),
    )
    actor = actors.actors[0]

    assert actor.observed_source_points == 2
    assert actor.derived_world_samples >= 1
    assert [sample.kind for sample in actor.samples] == [
        HistoricalActorSampleKind.OBSERVED,
        HistoricalActorSampleKind.INTERPOLATED,
        HistoricalActorSampleKind.OBSERVED,
    ]
    assert actor.sample_at(1.0).kind is HistoricalActorSampleKind.INTERPOLATED
    assert actor.sample_at(1.0).source_observation_refs


def test_long_gap_terminates_actor_and_reappearance_is_new_generation(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "gaps.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.001,62.0,4,90,40,8\n"
        "2026-07-01T00:00:11Z,123456789,7.0011,62.0,4,90,40,8\n",
    )

    actors = HistoricalAISReconstructor().reconstruct(
        _read(source),
        HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0),
    )
    actor = actors.actors[0]

    assert actor.sample_at(5.0) is None
    assert actor.sample_at(10.0).kind is HistoricalActorSampleKind.OBSERVED
    assert actor.active_intervals == ((0.0, 0.0), (10.0, 11.0))
    assert (
        actors.semantic_digest
        == HistoricalAISReconstructor()
        .reconstruct(_read(source), HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0))
        .semantic_digest
    )


def test_reconstruction_does_not_expose_future_sample_from_current_lookup(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "future.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0,4,90,40,8\n",
    )
    actors = HistoricalAISReconstructor().reconstruct(
        _read(source), HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0)
    )

    assert actors.world_states_at(0.0)[0].sample.timestamp_utc.isoformat().startswith("2026-07-01T00:00:00")
    with pytest.raises(ValueError, match="future"):
        actors.current_observations_at(0.0, knowledge_cutoff_s=0.0, include_future=True)


def test_replay_uses_normal_session_sensor_tracker_chain(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "session.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0,4,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.01,62.0,4,270,40,8\n"
        "2026-07-01T00:00:02Z,223456789,7.0099,62.0,4,270,40,8\n",
    )
    dataset = _read(source)
    actors = HistoricalAISReconstructor().reconstruct(
        dataset, HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0)
    )
    enc = SimpleNamespace(
        seabed=[],
        land=SimpleNamespace(geometry=MultiPolygon()),
        shore=SimpleNamespace(geometry=MultiPolygon()),
    )
    simulator_config = SimulatorConfig(verbose=False)
    simulator_config.visualizer.show_liveplot = False
    simulator = Simulator(config=simulator_config)
    prepared = HistoricalReplayFactory.prepare(
        HistoricalReplayRequest(actor_set=actors, t_end_s=2.0),
        enc=enc,
        simulator=simulator,
    )

    snapshot = prepared.session.step_once()
    ownship = snapshot.payload["Ship0"]
    target = snapshot.payload["Ship1"]
    assert prepared.session.simulator is simulator
    assert ownship["historical_actor_truth"]["sample_kind"] == "observed"
    assert target["historical_actor_truth"]["sample_kind"] == "observed"
    assert ownship["do_estimates"]
    assert target["historical_actor_truth"]["trajectory_digest"] == actors.actors[1].actor_digest
    assert prepared.evidence.mode == "HISTORICAL_REPLAY"
    assert prepared.evidence.counterfactual is False


def test_replay_reappearance_rearms_tracker_generation(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "reappearance.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0002,62.0,4,90,40,8\n"
        "2026-07-01T00:00:04Z,123456789,7.0004,62.0,4,90,40,8\n"
        "2026-07-01T00:00:06Z,123456789,7.0006,62.0,4,90,40,8\n"
        "2026-07-01T00:00:08Z,123456789,7.0008,62.0,4,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.001,62.0,4,90,40,8\n"
        "2026-07-01T00:00:11Z,123456789,7.0011,62.0,4,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.01,62.0,4,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.009,62.0,4,270,40,8\n"
        "2026-07-01T00:00:11Z,223456789,7.0089,62.0,4,270,40,8\n",
    )
    actors = HistoricalAISReconstructor().reconstruct(
        _read(source), HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0)
    )
    enc = SimpleNamespace(
        seabed=[],
        land=SimpleNamespace(geometry=MultiPolygon()),
        shore=SimpleNamespace(geometry=MultiPolygon()),
    )
    simulator = Simulator(config=SimulatorConfig(verbose=False))
    prepared = HistoricalReplayFactory.prepare(
        HistoricalReplayRequest(actor_set=actors, t_end_s=11.0), enc=enc, simulator=simulator
    )

    first_generation = None
    reappeared_generation = None
    for _ in range(11):
        snapshot = prepared.session.step_once()
        tracks, _ = prepared.ships[0].get_do_track_information()
        if snapshot.sim_time == 0.0:
            first_generation = tracks[0].key.generation
        if snapshot.sim_time == 10.0:
            reappeared_generation = tracks[0].key.generation

    assert first_generation == 1
    assert reappeared_generation == 2


def test_replay_request_round_trip_preserves_sealed_lineage(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "round-trip.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0,4,90,40,8\n",
    )
    actors = HistoricalAISReconstructor().reconstruct(
        _read(source), HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0)
    )
    request = HistoricalReplayRequest(actor_set=actors, t_end_s=2.0)
    restored = HistoricalReplayRequest.from_dict(request.to_dict())

    assert restored.actor_set.semantic_digest == actors.semantic_digest
    assert restored.evidence.digest == request.evidence.digest
    assert restored.to_dict()["evidence"]["mode"] == "HISTORICAL_REPLAY"
    assert restored.evidence.provider == "Kystverket"
    assert restored.evidence.coverage_limitations
