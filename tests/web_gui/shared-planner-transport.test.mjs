import assert from 'node:assert/strict';
import test from 'node:test';
import { expandSharedPlannerEnvelope } from '../../web_gui/modules/active-session-runtime.js';

function wire() {
  return {
    schema_version: '1.0', run_id: 'run', seq: 2,
    planner: { solve_id: 1, selected_command: { speed_mps: 6 }, evidence_timeline: { events: [] } },
    latest_planner_solve: { solve_id: 0 },
    truth: [{ id: 0, colav: { diagnostics: { status: 'SUCCESS' } } }, { id: 1 }],
    transport: {
      schema_version: 'colav.telemetry.shared-planner@1', static_included: false,
      planner_aliases: ['active_planner_plan', 'latest_planner_attempt'],
      ship_planner_aliases: [0], ownship_from_truth: true, obstacles_from_truth: true,
    },
  };
}

test('expansion restores all current aliases without mutating the received frame or old solve', () => {
  const encoded = wire();
  const original = structuredClone(encoded);
  const decoded = expandSharedPlannerEnvelope(encoded);
  assert.equal(decoded.active_planner_plan, decoded.planner);
  assert.equal(decoded.latest_planner_attempt, decoded.planner);
  assert.equal(decoded.os, decoded.truth[0]);
  assert.equal(decoded.os.colav.planner, decoded.planner);
  assert.equal(decoded.obstacles[0], decoded.truth[1]);
  assert.equal(decoded.latest_planner_solve.solve_id, 0);
  assert.deepEqual(encoded, original);
});

test('each frame is self-contained across reconnect and session replacement', () => {
  const first = wire(); first.enc_navigation_area = { safe_water: 'map' };
  first.transport.static_included = true;
  const a = expandSharedPlannerEnvelope(first);
  const next = wire(); next.run_id = 'new-run'; next.planner.solve_id = 12;
  const b = expandSharedPlannerEnvelope(next);
  assert.equal(b.os.colav.planner.solve_id, 12);
  assert.equal(a.os.colav.planner.solve_id, 1);
  assert.deepEqual(a.enc_navigation_area, { safe_water: 'map' });
  assert.equal('enc_navigation_area' in b, false);
});

test('legacy packets pass through and malformed alias paths cannot write arbitrary properties', () => {
  const legacy = { planner: {}, transport: { schema_version: 'colav.telemetry.static-once@1' } };
  assert.equal(expandSharedPlannerEnvelope(legacy), legacy);
  const bad = wire(); bad.transport.planner_aliases = ['__proto__'];
  assert.equal(expandSharedPlannerEnvelope(bad), null);
  const invalid = wire(); invalid.transport.ship_planner_aliases = [99];
  assert.equal(expandSharedPlannerEnvelope(invalid), null);
});
