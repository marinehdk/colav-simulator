"""Bound live evidence without modifying the authoritative simulation frames."""
import json
from types import SimpleNamespace

import numpy as np

from colav_simulator.experiment.contracts import SessionState
from gui_server import main


def _manager(monkeypatch, count) -> tuple[main.WebSessionManager, dict, dict]:
    monkeypatch.setattr(main, '_enc_depth_bin_at', lambda *args, **kwargs: None)
    events = [{'seq': i, 'type': 'PLAN_HELD', 'payload': {'semantic_hash': 'a' * 64}} for i in range(count)]
    timeline = {'events': events, 'active_semantic_hash': 'active', 'active_receipt_hash': 'receipt',
                'latest_terminal_outcome': 'HELD', 'last_committed_executable': True}
    planner = {'schema_version': '1.1', 'algorithm_id': 'mid_mpc_ipopt', 'solve_id': 1,
               'solver_executed': True, 'evidence_timeline': timeline,
               'prediction_render': {'schema_version': 'colav.mid_mpc.prediction-render@1', 'executable': True,
                                     'style': 'ACTIVE', 'ownship': {}, 'targets': []},
               'selected_command': {'course_rad': .2, 'speed_mps': 6.}}
    raw = {'id': 0, 'mmsi': 1, 'state': np.array([6955700., 42950., 0., 6., 0., 0.]),
           'csog_state': np.array([6955700., 42950., 6., 0.]), 'references': np.zeros(9),
           'colav': {'planner': planner, 'threat_management': {'status': 'UNAVAILABLE'}}}
    session = SimpleNamespace(
        last_frame={'Ship0': raw}, ship_list=[SimpleNamespace(length=44., width=8.)],
        enc=SimpleNamespace(origin=(42950., 6955700.), utm_zone=32), state=SessionState.RUNNING,
        simulator=SimpleNamespace(t=70., t_end=1800.), sequence=700, operational_events=[],
        baseline_threat_failure_reason=None, failure_reason=None,
    )
    manager = main.WebSessionManager()
    manager.prepared = SimpleNamespace(
        session=session, spec=SimpleNamespace(scenario_id='paper_ccta2023_multiship',
                                              historical_replay=None, validation_rule_id='multiship'),
        manifest=SimpleNamespace(run_id='test', executed_algorithm='mid_mpc_ipopt',
                                 requested_algorithm='mid_mpc_ipopt', requested_tracker='god', executed_tracker='god'),
    )
    return manager, raw, timeline


def test_publication_bounds_all_evidence_aliases_and_preserves_audit(monkeypatch) -> None:
    manager, raw, timeline = _manager(monkeypatch, 5000)
    manager._publish_telemetry(None)
    documents = [manager.latest[name] for name in ('planner', 'latest_planner_solve',
                                                  'active_planner_plan', 'latest_planner_attempt')]
    documents += [manager.latest['os']['colav']['planner'], manager.latest['truth'][0]['colav']['planner']]
    for document in documents:
        display = document['evidence_timeline']
        assert len(display['events']) <= 32
        assert display['events'][-1]['seq'] == 4999
        assert display['events_total'] == 5000
        assert display['events_truncated'] is True
        assert display['active_receipt_hash'] == 'receipt'
        assert document['selected_command'] == raw['colav']['planner']['selected_command']
    assert len(timeline['events']) == 5000
    assert 'events_total' not in timeline
    first = manager.stream_document(static_once=True, include_static=False)
    assert len(first) < 100_000
    assert manager.stream_document(static_once=True, include_static=False) is first
    documents[0]['evidence_timeline']['events'][-1]['seq'] = -1
    assert timeline['events'][-1]['seq'] == 4999


def test_publication_retains_small_histories_and_current_authority(monkeypatch) -> None:
    manager, _, timeline = _manager(monkeypatch, 3)
    manager._publish_telemetry(None)
    display = manager.latest['planner']['evidence_timeline']
    assert display['events'] == timeline['events']
    assert display['events_total'] == 3
    assert display['events_truncated'] is False
    assert display['latest_terminal_outcome'] == 'HELD'
    assert display['last_committed_executable'] is True


def test_hold_and_rejection_preserve_frozen_solve_and_render_authority(monkeypatch) -> None:
    manager, raw, timeline = _manager(monkeypatch, 5000)
    manager._publish_telemetry(None)
    first_solve = manager.latest['latest_planner_solve']
    raw['colav']['planner']['solver_executed'] = False
    timeline['events'].append({'seq': 5000, 'type': 'PLAN_HELD'})
    manager._publish_telemetry(None)
    assert manager.latest['latest_planner_solve'] is first_solve
    assert first_solve['evidence_timeline']['events'][-1]['seq'] == 4999
    assert manager.latest['planner']['evidence_timeline']['events'][-1]['seq'] == 5000
    render = raw['colav']['planner']['prediction_render']
    render.update(style='REJECTED', executable=False)
    manager._publish_telemetry(None)
    assert manager.latest['active_planner_plan'] == {}
    assert manager.latest['planner']['prediction_render']['style'] == 'REJECTED'
    assert manager.latest['latest_planner_solve'] is first_solve
    assert len(timeline['events']) == 5001


def test_shared_transport_sends_current_planner_once_with_explicit_aliases(monkeypatch) -> None:
    manager, _, _ = _manager(monkeypatch, 5000)
    manager._publish_telemetry(None)
    ordinary = manager.stream_document(static_once=True, include_static=False)
    wire = manager.stream_document(shared_planner=True, include_static=False)
    payload = json.loads(wire)
    assert payload['transport']['schema_version'] == 'colav.telemetry.shared-planner@1'
    assert set(payload['transport']['planner_aliases']) == {
        'latest_planner_solve', 'active_planner_plan', 'latest_planner_attempt',
    }
    assert payload['transport']['ship_planner_aliases'] == [0]
    assert 'planner' not in payload['truth'][0]['colav']
    assert 'os' not in payload
    assert payload['transport']['ownship_from_truth'] is True
    assert 'active_planner_plan' not in payload
    assert 'enc_navigation_area' not in payload
    assert len(wire) < len(ordinary) / 2
    assert manager.stream_document(shared_planner=True, include_static=False) is wire
    initial = json.loads(manager.stream_document(shared_planner=True, include_static=True))
    assert 'enc_navigation_area' in initial
    assert manager.latest['os']['colav']['planner'] is manager.latest['planner']


def test_rejected_replan_keeps_plan_audit_but_projects_current_threat(monkeypatch) -> None:
    manager, raw, _ = _manager(monkeypatch, 3)
    frozen = {"sim_time_s": 0.0, "vectors": [{"display_class": "LOW", "avoidance_action_active": False}]}
    current = {"sim_time_s": 70.0, "vectors": [{"display_class": "HIGH", "avoidance_action_active": True}]}
    raw["colav"]["planner"]["algorithm_details"] = {"threat_management": frozen, "candidate_rejected": True}
    manager.prepared.session.threat_management_coordinator = SimpleNamespace(
        last_snapshot=SimpleNamespace(to_dict=lambda: current)
    )
    manager._publish_telemetry(None)
    assert manager.latest["threat_management"]["vectors"][0]["display_class"] == "HIGH"
    assert manager.latest["planner"]["algorithm_details"]["threat_management"] == frozen
