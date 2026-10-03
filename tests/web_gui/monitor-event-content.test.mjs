import assert from 'node:assert/strict';
import test from 'node:test';
import {
  eventDisplayContent as format,
  renderMonitorEventItems,
  visibleMonitorEvents,
} from '../../web_gui/modules/monitor-event-presentation.js?v=20260924-replay-events-v1';

test('Deployment and Replay share the operational event filter and card rows', () => {
  const events = [
    { type: 'session_started', simTime: 0, details: {} },
    ...Array.from({ length: 20 }, (_, index) => ({ type: 'planner_solved', simTime: index + 1, details: {} })),
    { type: 'primary_challenger', simTime: 21, details: {} },
    { type: 'target_transition', simTime: 22, details: { target_id: 2, to_state: 'ACTIVE/COMMITTED/NONE', display_class: 'HIGH' } },
  ];
  assert.equal(visibleMonitorEvents(events).length, 2);
  const list = { shadowRoot: null };
  const count = renderMonitorEventItems(list, events, seconds => `00:00:${String(seconds).padStart(2, '0')}`, {});
  assert.equal(count, 2);
  assert.equal(list.events.length, 2);
  assert.match(list.events[0].title, /Risk state AVOIDING/);
  assert.equal(list.events[0].description, '00:00:22');
  assert.doesNotMatch(list.events.map(item => item.title).join(' '), /Planner solution/);
});

for (const [state, display, status, tone] of [
  ['ACTIVE/COMMITTED/NONE', 'LOW', 'MONITOR', 'warning'],
  ['ACTIVE/COMMITTED/NONE', 'HIGH', 'AVOIDING', 'danger'],
  ['PAST_CLEAR/COMMITTED/NONE', 'CLEAR', 'CLEARING', 'safe'],
  ['RELEASED/ACHIEVED/NONE', 'CLEAR', 'RELEASED', 'safe'],
]) {
  test(`event state ${state}/${display} agrees with the threat card`, () => {
    const output = format({type: 'target_transition', details: {to_state: state, display_class: display, target_id: 1}});
    assert.equal(output.status, status);
    assert.equal(output.cardTone, tone);
  });
}
