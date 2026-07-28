from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from colav_simulator.experiment.contracts import RunSpec
from colav_simulator.experiment.runner import ExperimentRunner, RunResult, _enc_hash


def test_enc_hash_is_order_independent_recursive_and_content_sensitive(tmp_path: Path) -> None:
    first = tmp_path / "first.gdb"
    second = tmp_path / "second.gdb"
    (first / "nested").mkdir(parents=True)
    second.mkdir()
    (first / "nested" / "a.bin").write_bytes(b"alpha")
    (second / "b.bin").write_bytes(b"beta")

    _enc_hash.cache_clear()
    forward = _enc_hash((str(first), str(second)))
    reverse = _enc_hash((str(second), str(first)))

    assert forward == reverse
    (first / "nested" / "a.bin").write_bytes(b"changed")
    _enc_hash.cache_clear()
    assert _enc_hash((str(first), str(second))) != forward


def test_short_comparison_uses_one_clock_and_enc_identity(tmp_path: Path) -> None:
    runner = ExperimentRunner()
    nominal = _run_short(runner, tmp_path, "nominal")
    candidate = _run_short(runner, tmp_path, "vo")

    assert nominal.manifest.scenario_hash == candidate.manifest.scenario_hash
    assert nominal.manifest.episode_hash == candidate.manifest.episode_hash
    assert nominal.manifest.enc_hash == candidate.manifest.enc_hash
    assert nominal.manifest.enc_hash
    assert nominal.manifest.seeds == candidate.manifest.seeds
    assert nominal.manifest.encounter_profile_id == candidate.manifest.encounter_profile_id == "legacy-g3-v1"

    for result in (nominal, candidate):
        episode = json.loads((result.run_dir / "episode.json").read_text(encoding="utf-8"))
        manifest = json.loads((result.run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert episode["enc_hash"] == manifest["enc_hash"] == result.manifest.enc_hash
        _assert_frame_clock(result)

    frame_solve_times = [
        float(frame["Ship0"]["colav"]["planner"]["sim_time"])
        for frame in candidate.session.frames
        if frame["Ship0"]["colav"]["planner"]["solver_executed"]
    ]
    event_solve_times = [
        float(event["sim_time"])
        for event in candidate.session.events
        if event["type"] == "planner_solved"
    ]
    frame_times = {float(frame["Ship0"]["timestamp"]) for frame in candidate.session.frames}

    assert frame_solve_times
    assert event_solve_times == frame_solve_times
    assert set(event_solve_times) <= frame_times


def _run_short(runner: ExperimentRunner, output_root: Path, algorithm_id: str) -> RunResult:
    return runner.run(
        RunSpec(
            scenario_id="head_on",
            algorithm_id=algorithm_id,
            tracker_id="god",
            seed=0,
            t_end=1.0,
            terminate_on_collision_or_grounding=False,
            strict_no_fallback=True,
            output_root=str(output_root / algorithm_id),
        )
    )


def _assert_frame_clock(result: RunResult) -> None:
    times = np.asarray([frame["Ship0"]["timestamp"] for frame in result.session.frames], dtype=float)
    assert times.size > 1
    assert np.all(np.diff(times) > 0.0)
    assert np.allclose(np.diff(times), result.session.config.dt_sim, rtol=0.0, atol=1e-9)
