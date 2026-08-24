from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from shapely.geometry import MultiPolygon

from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_replay import (
    ENCPreflightEvidence,
    ENCPreflightEvidenceError,
    ENCPreflightEvidenceErrorCode,
    HistoricalActorSampleKind,
    HistoricalActorSet,
    HistoricalActorShip,
    HistoricalAISReconstructionProfile,
    HistoricalAISReconstructor,
    HistoricalCounterfactualActorShip,
    HistoricalReplayFactory,
    HistoricalReplayQualificationError,
    HistoricalReplayQualificationStatus,
    HistoricalReplayRequest,
)
from colav_simulator.simulator import Config as SimulatorConfig
from colav_simulator.simulator import Simulator


def _write_csv(path: Path, rows: str) -> Path:
    path.write_text(rows, encoding="utf-8")
    return path


def _read(path: Path) -> object:
    return HistoricalAISDatasetReader(path).read(HistoricalAISSelection())


def _enc_evidence(actor_set: HistoricalActorSet) -> ENCPreflightEvidence:
    east = [sample.state_vxvy[1] for actor in actor_set.actors for sample in actor.samples]
    north = [sample.state_vxvy[0] for actor in actor_set.actors for sample in actor.samples]
    return ENCPreflightEvidence(
        profile_id="test-enc",
        qualification_state="QUALIFIED",
        supported_extent_projected=(min(east) - 100.0, min(north) - 100.0, max(east) + 100.0, max(north) + 100.0),
        profile_digest="profile-digest",
        cache_digest="cache-digest",
        source_digest="source-digest",
        preflight_status="PASS",
        all_positions_contained=True,
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("tamper", ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE),
        ("unqualified", ENCPreflightEvidenceErrorCode.ENC_UNQUALIFIED),
        ("preflight", ENCPreflightEvidenceErrorCode.PREFLIGHT_FAILED),
        ("outside", ENCPreflightEvidenceErrorCode.OUTSIDE_COVERAGE),
    ),
)
def test_enc_preflight_evidence_uses_structured_error_codes(
    mutation: str,
    expected_code: ENCPreflightEvidenceErrorCode,
) -> None:
    document = ENCPreflightEvidence(
        profile_id="enc",
        qualification_state="QUALIFIED",
        supported_extent_projected=(0.0, 0.0, 10.0, 10.0),
        profile_digest="profile",
        cache_digest="cache",
        source_digest="source",
        preflight_status="PASS",
        all_positions_contained=True,
    ).to_dict()
    if mutation == "tamper":
        document["profile_digest"] = "changed"
    elif mutation == "unqualified":
        document["qualification_state"] = "UNQUALIFIED"
    elif mutation == "preflight":
        document["preflight_status"] = "HAZARD_INTERSECTION"
    else:
        document["all_positions_contained"] = False

    with pytest.raises(ENCPreflightEvidenceError) as raised:
        ENCPreflightEvidence.from_dict(document)

    assert raised.value.code is expected_code
    if mutation == "tamper":
        document["supported_extent_projected"] = None
        with pytest.raises(ENCPreflightEvidenceError) as malformed:
            ENCPreflightEvidence.from_dict(document)
        assert malformed.value.code is ENCPreflightEvidenceErrorCode.QUALITY_INCOMPLETE


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


def test_counterfactual_pre_t0_plan_is_playback_without_planner_or_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _write_csv(
        tmp_path / "pre-t0-playback.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0,4,90,40,8\n",
    )
    profile = HistoricalAISReconstructionProfile(time_step_s=1.0, max_interpolation_gap_s=5.0)
    actor = HistoricalAISReconstructor().reconstruct(_read(source), profile).actors[0]
    ship = HistoricalCounterfactualActorShip(
        actor,
        profile,
        t0_s=1.0,
        nominal_intent={
            "route_points_vxvy": (
                (actor.samples[0].state_vxvy[0], actor.samples[0].state_vxvy[1]),
                (actor.samples[-1].state_vxvy[0], actor.samples[-1].state_vxvy[1]),
            ),
            "speed_mps": 4.0,
        },
        simulation_end_s=2.0,
    )
    monkeypatch.setattr(
        HistoricalActorShip,
        "plan",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("playback called parent plan")),
    )

    references = ship.plan(0.0, 1.0, [])

    assert references.shape == (9, 1)
    assert references[0, 0] == pytest.approx(actor.samples[0].state_vxvy[0])
    assert ship.counterfactual_phase == "HISTORICAL_REFERENCE"


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
        HistoricalReplayRequest(actor_set=actors, t_end_s=2.0, enc_preflight_evidence=_enc_evidence(actors)),
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


def test_replay_factory_fails_before_session_when_actor_dimensions_are_missing(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "missing-hull.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,,\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0,4,90,,\n",
    )
    actors = HistoricalAISReconstructor().reconstruct(_read(source))

    with pytest.raises(HistoricalReplayQualificationError) as error:
        HistoricalReplayFactory.prepare(
            HistoricalReplayRequest(actor_set=actors, enc_preflight_evidence=_enc_evidence(actors)),
            enc=SimpleNamespace(),
            simulator=Simulator(config=SimulatorConfig(verbose=False)),
        )

    assert error.value.status is HistoricalReplayQualificationStatus.DIMENSIONS_UNAVAILABLE


def test_replay_factory_rejects_default_hull_provenance_before_session(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "default-hull.csv",
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,4,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0,4,90,40,8\n",
    )
    actors = HistoricalAISReconstructor().reconstruct(_read(source))
    actors = replace(
        actors,
        actors=(replace(actors.actors[0], dimensions_provenance="silent_default", actor_digest=""),),
        semantic_digest="",
    )

    with pytest.raises(HistoricalReplayQualificationError) as error:
        HistoricalReplayFactory.prepare(
            HistoricalReplayRequest(actor_set=actors, enc_preflight_evidence=_enc_evidence(actors)),
            enc=SimpleNamespace(),
            simulator=Simulator(config=SimulatorConfig(verbose=False)),
        )

    assert error.value.status is HistoricalReplayQualificationStatus.QUALITY_INCOMPLETE


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
        HistoricalReplayRequest(actor_set=actors, t_end_s=11.0, enc_preflight_evidence=_enc_evidence(actors)),
        enc=enc,
        simulator=simulator,
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
    request = HistoricalReplayRequest(
        actor_set=actors,
        t_end_s=2.0,
        enc_preflight_evidence=_enc_evidence(actors),
    )
    restored = HistoricalReplayRequest.from_dict(request.to_dict())

    assert restored.actor_set.semantic_digest == actors.semantic_digest
    assert restored.evidence.digest == request.evidence.digest
    assert restored.to_dict()["evidence"]["mode"] == "HISTORICAL_REPLAY"
    assert restored.evidence.provider == "Kystverket"
    assert restored.evidence.coverage_limitations
