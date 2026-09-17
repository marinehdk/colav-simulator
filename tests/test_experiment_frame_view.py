"""Long native campaigns keep every sample without unpacking all diagnostics."""

import pickle
from types import SimpleNamespace

import numpy as np
import pandas as pd

from colav_simulator.common.miscellaneous_helper_methods import convert_simulation_data_to_vessel_data
from colav_simulator.experiment.persistence import EvidenceWriter, trajectory_semantic_hash
from colav_simulator.experiment.runner import ExperimentRunner, _solver_diagnostics
from colav_simulator.experiment.session import SimulationSession


def test_packed_evidence_preserves_evaluation_and_parquet_without_eager_frames(tmp_path, monkeypatch):
    frames = [
        {
            "Ship0": {
                "id": 0,
                "mmsi": 100,
                "active": True,
                "state": np.array([6958000.0 + k * 7.0, 40500.0, 0.0, 7.0, 0.0, 0.0]),
                "csog_state": np.array([6958000.0 + k * 7.0, 40500.0, 7.0, 0.0]),
                "input": np.zeros(3),
                "references": np.zeros(9),
                "timestamp": float(k),
                "date_time_utc": f"17.09.2026 10:00:0{k}",
                "colav": {
                    "diagnostics": {"fallback_used": False},
                    "planner": {
                        "solver_executed": True,
                        "solve_id": k + 1,
                        "status": "SUCCESS",
                        "elapsed_ms": 2.0,
                        "iterations": 3,
                        "objective": 1.0,
                        "algorithm_details": {"retained_diagnostic": "x" * 100000},
                    },
                },
            }
        }
        for k in range(3)
    ]
    session = SimulationSession.__new__(SimulationSession)
    session._frame_blobs = [pickle.dumps(frame) for frame in frames]
    session._frames_live = []
    session._frames_decoded = None
    session.ship_info = {"Ship0": {"id": 0, "mmsi": 100, "length": 44.1, "width": 8.0, "draft": 2.0}}
    session.config = SimpleNamespace(utm_zone=33)

    def forbidden_eager_frames(_self):
        raise AssertionError("Evidence consumer materialized all packed frames")

    monkeypatch.setattr(SimulationSession, "frames", property(forbidden_eager_frames))
    view = session.frame_view
    assert len(view) == 3
    assert len(list(view)) == len(list(view)) == 3
    expected = convert_simulation_data_to_vessel_data(pd.DataFrame(frames), session.ship_info, 33)
    actual = session.vessel_data()
    np.testing.assert_array_equal(actual[0].xy, expected[0].xy)
    np.testing.assert_array_equal(actual[0].sog, expected[0].sog)
    np.testing.assert_array_equal(actual[0].cog, expected[0].cog)
    assert actual[0].timestamps == expected[0].timestamps
    assert _solver_diagnostics(view) == _solver_diagnostics(frames)
    prepared = SimpleNamespace(session=session, manifest=SimpleNamespace(), spec=SimpleNamespace(strict_no_fallback=True))
    ExperimentRunner._enforce_no_fallback(prepared)
    assert prepared.manifest.fallback_used is False
    assert trajectory_semantic_hash(view) == trajectory_semantic_hash(frames)
    first = EvidenceWriter(tmp_path / "packed").write_trajectory(view)
    second = EvidenceWriter(tmp_path / "plain").write_trajectory(frames)
    assert first.read_bytes() == second.read_bytes()
    assert session._frames_decoded is None
