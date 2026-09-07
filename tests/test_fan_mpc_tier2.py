"""Closed-loop Fan-MPC recovery using the product Tier2 stack and original scenes."""
from dataclasses import replace

import numpy as np
import pytest
from conftest import PROJECT_ROOT

from colav_simulator.experiment.runner import ExperimentRunner
from gui_server.main import SessionCreateRequest


@pytest.mark.parametrize('scenario,rule', [
    ('head_on', 'rule14'), ('crossing_give_way', 'rule15'), ('paper_ccta2023_multiship', 'multiship'),
])
def test_fan_tier2_passes_and_recovers(tmp_path, scenario, rule) -> None:
    spec = SessionCreateRequest(scenario_id=scenario, validation_rule_id=rule,
                                algorithm_id='potocnik_colreg_fan_mpc', tracker_id='god',
                                gnc_stack_id='fcb45_3dof_plant+pass_through_guidance+fcb45_marine_pid').to_spec()
    prepared = ExperimentRunner(PROJECT_ROOT).prepare(replace(spec, output_root=str(tmp_path / 'runs')))
    try:
        prepared.session.run_to_completion()
    finally:
        prepared.artifact_sink.close(timeout_s=2.0)
    frames = prepared.session.frames
    events = {event['type'] for event in prepared.session.events}
    assert not events & {'collision', 'grounding', 'run_failed', 'session_failed'}
    assert not prepared.manifest.fallback_used
    own = np.array([frame['Ship0']['state'] for frame in frames])
    assert own[:, 3].min() > 1.0
    for name in frames[0]:
        if name == 'Ship0':
            continue
        target = np.array([frame[name]['state'] for frame in frames])
        assert np.linalg.norm(own[:, :2] - target[:, :2], axis=1).min() > 190.0
    solves = [frame['Ship0']['colav']['planner'] for frame in frames
              if frame['Ship0']['colav']['planner']['solver_executed']]
    assert solves
    for solve in solves:
        assert solve['algorithm_id'] == 'potocnik_colreg_fan_mpc'
        assert solve['selected_command']['speed_mps'] > 1.0
        assert not solve['constraints']['colreg_policy']['relaxations']
    crossing_id = 2 if scenario == 'paper_ccta2023_multiship' else 1
    if scenario != 'head_on':
        target = np.array([frame[f'Ship{crossing_id}']['state'] for frame in frames])
        relative = own[:, :2] - target[:, :2]
        unit = np.column_stack((np.cos(target[:, 2]), np.sin(target[:, 2])))
        lateral = unit[:, 0] * relative[:, 1] - unit[:, 1] * relative[:, 0]
        longitudinal = np.sum(unit * relative, axis=1)
        crossings = np.flatnonzero(lateral[:-1] * lateral[1:] < 0.0)
        assert crossings.size
        assert np.all(longitudinal[crossings] < 0.0), "Crossed ahead of the give-way target"
    first_action = next(
        frame['Ship0'] for frame in frames
        if crossing_id in (
            frame['Ship0']['colav']['planner']['constraints']['colreg_policy']['give_way_targets']
        )
    )
    command = first_action['colav']['planner']['selected_command']['course_rad']
    difference = command - first_action['state'][2]
    assert np.arctan2(np.sin(difference), np.cos(difference)) > 0.0
    if scenario == 'paper_ccta2023_multiship':
        _assert_three_target_recovery(frames, solves, events)


def _assert_three_target_recovery(frames: list[dict], solves: list[dict], events: set[str]) -> None:
    kinds = {target_id: set() for target_id in (1, 2, 3)}
    for solve in solves:
        for record in solve['algorithm_details']['encounter_records']:
            if record['encounter'] != 'clear':
                kinds[record['target_id']].add(record['encounter'])
    assert kinds == {1: {'overtaking'}, 2: {'crossing_give_way'}, 3: {'head_on'}}
    head_on = [frame for frame in frames
               if 'head_on' in frame['Ship0']['colav']['planner']['algorithm_details']['active_encounters']]
    assert min(frame['Ship0']['state'][3] for frame in head_on) > 4.0
    last_time = head_on[-1]['Ship0']['timestamp']
    released = next(frame for frame in frames if frame['Ship0']['timestamp'] > last_time)
    state = released['Ship0']['state']
    relative = released['Ship3']['state'][:2] - state[:2]
    assert relative @ np.array([np.cos(state[2]), np.sin(state[2])]) < 0.0
    assert 'goal_reached' in events
    at600 = min(frames, key=lambda frame: abs(frame['Ship0']['timestamp'] - 600.0))
    assert abs(at600['Ship0']['colav']['planner']['algorithm_details']['cross_track_error_m']) < 150.0
    end = frames[-1]['Ship0']['timestamp']
    assert end < 1800.0
    assert max(abs(frame['Ship0']['colav']['planner']['algorithm_details']['cross_track_error_m'])
               for frame in frames if frame['Ship0']['timestamp'] >= end - 30.0) < 30.0
