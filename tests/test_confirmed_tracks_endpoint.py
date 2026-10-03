"""P3-S5 (spec #90) high-confidence track data product tests.

Covers the ``GET /api/sessions/{id}/confirmed-tracks`` route and the
``WebSessionManager.confirmed_tracks`` serializer against the frozen
sensor-model-v1 §5 envelope: existence gating (in/out around the threshold),
schema conformance, god truth source convention, and the error contract.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import gui_server.main as gui_main
from colav_simulator.experiment.contracts import SessionState
from colav_simulator.schemas.sensor_model_v1 import (
    CONFIRMED_TRACKS_DEFAULT_THRESHOLD,
    ConfirmedTrackList,
)


def _raw_frame(*, labels, existences, states=None, covariances=None, generations=None, sources=None, qualities=None):
    count = len(labels)
    return {
        "timestamp": 42.0,
        "do_labels": labels,
        "do_generations": generations if generations is not None else [1] * count,
        "do_estimates": states
        if states is not None
        else [[100.0 * (index + 1), 0.0, -2.0, 0.0] for index in range(count)],
        "do_covariances": covariances
        if covariances is not None
        else [np.diag([49.0, 49.0, 0.5, 0.5]).tolist() for _ in range(count)],
        "do_NISes": [0.0] * count,
        "do_existence_probabilities": existences,
        "do_qualities": qualities if qualities is not None else [0.9] * count,
        "do_sources": sources if sources is not None else [[{"sensor_id": 1, "last_seen_age_s": 0.0}]] * count,
    }


def _manager(raw_frame) -> gui_main.WebSessionManager:
    session = SimpleNamespace(
        last_frame={"Ship0": raw_frame},
        ship_list=[SimpleNamespace(sensors=[])],
        enc=SimpleNamespace(origin=(40500.0, 6958000.0)),
        state=SessionState.RUNNING,
        simulator=SimpleNamespace(t=42.0),
    )
    manager = gui_main.WebSessionManager()
    manager.prepared = SimpleNamespace(
        session=session,
        manifest=SimpleNamespace(run_id="session-s5"),
        spec=SimpleNamespace(historical_replay=None),
    )
    return manager


def test_confirmed_tracks_gate_filters_and_conforms_to_frozen_schema() -> None:
    raw = _raw_frame(
        labels=[1, 2, 3],
        existences=[0.9999, 0.5, 0.02],
        sources=[
            [{"sensor_id": 1, "last_seen_age_s": 0.5}],
            [],
            [{"sensor_id": 5, "last_seen_age_s": None}],
        ],
    )
    document = _manager(raw).confirmed_tracks("session-s5")

    envelope = ConfirmedTrackList.model_validate(document)
    assert envelope.schema_version == "sensor-model@1/tracks"
    assert envelope.t_s == pytest.approx(42.0)
    # Only the >= 0.999 (default threshold) track survives.
    assert [track.target_id for track in envelope.tracks] == [1]
    track = envelope.tracks[0]
    assert track.track_key == "1:1"
    assert track.existence_prob == pytest.approx(0.9999)
    assert track.sources[0].sensor_id == 1
    assert track.sources[0].last_seen_age_s == pytest.approx(0.5)
    # Ownship-NED local frame: world (100, 0) minus origin (40500 E, 6958000 N).
    assert track.position_ne_m == pytest.approx([100.0 - 6958000.0 + 6958000.0 - 6958000.0, 0.0 - 40500.0])
    assert track.velocity_ne_mps == pytest.approx([-2.0, 0.0])
    assert track.heading_rad == pytest.approx(np.arctan2(0.0, -2.0))
    # Lowering the gate admits the mid-band track.
    relaxed = ConfirmedTrackList.model_validate(_manager(raw).confirmed_tracks("session-s5", min_existence_prob=0.4))
    assert [track.target_id for track in relaxed.tracks] == [1, 2]


def test_confirmed_tracks_god_truth_tracks_use_primary_channel_source_convention() -> None:
    raw = _raw_frame(labels=[7], existences=[1.0], sources=[[]])
    document = _manager(raw).confirmed_tracks("session-s5", min_existence_prob=0.999)

    track = ConfirmedTrackList.model_validate(document).tracks[0]
    # God truth snapshots carry no measurement sources; the frozen schema
    # requires >=1 entry, so the primary ranging channel is reported with
    # unknown age (documented data-product convention).
    assert track.sources[0].sensor_id == 1
    assert track.sources[0].last_seen_age_s is None


def test_confirmed_tracks_legacy_frame_without_confidence_fields_defaults_certain() -> None:
    raw = _raw_frame(labels=[2], existences=[])
    del raw["do_existence_probabilities"]
    del raw["do_qualities"]
    del raw["do_sources"]
    document = _manager(raw).confirmed_tracks("session-s5", min_existence_prob=0.999)

    track = ConfirmedTrackList.model_validate(document).tracks[0]
    assert track.existence_prob == pytest.approx(1.0)
    assert track.quality == pytest.approx(1.0)
    assert track.sources[0].sensor_id == 1


def test_confirmed_tracks_route_error_contract(monkeypatch) -> None:
    manager = _manager(_raw_frame(labels=[1], existences=[1.0]))
    monkeypatch.setattr(gui_main, "manager", manager, raising=False)
    client = TestClient(gui_main.app)

    ok = client.get("/api/sessions/session-s5/confirmed-tracks")
    assert ok.status_code == 200
    assert ok.json()["schema_version"] == "sensor-model@1/tracks"

    missing = client.get("/api/sessions/other-session/confirmed-tracks")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "SESSION_NOT_FOUND"

    invalid = client.get("/api/sessions/session-s5/confirmed-tracks", params={"min_existence_prob": 1.5})
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "VALIDATION_ERROR"

    # Default query gate matches the frozen contract anchor.
    assert CONFIRMED_TRACKS_DEFAULT_THRESHOLD == pytest.approx(0.999)


def test_confirmed_track_schema_rejects_asymmetric_covariance_documents() -> None:
    # The endpoint boundary symmetrizes float noise; the frozen schema itself
    # still rejects genuinely asymmetric documents (contract §7 violation face).
    from colav_simulator.schemas.sensor_model_v1 import ConfirmedTrack, TrackSourceContribution

    with pytest.raises(ValidationError):
        ConfirmedTrack(
            track_key="1:1",
            target_id=1,
            generation=1,
            existence_prob=1.0,
            quality=1.0,
            sources=[TrackSourceContribution(sensor_id=1, last_seen_age_s=0.0)],
            position_ne_m=[0.0, 0.0],
            velocity_ne_mps=[0.0, 0.0],
            heading_rad=0.0,
            position_cov_ne_m2=[[49.0, 1.0], [2.0, 49.0]],
        )
