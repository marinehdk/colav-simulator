import assert from 'node:assert/strict';
import test from 'node:test';

import { createTelemetryProjection } from '../../web_gui/modules/telemetry-projection.js';

function runtime(envelope) {
  return {
    session: { session_id: envelope.run_id, state: envelope.state },
    sessionState: envelope.state,
    telemetry: { envelope, revision: envelope.seq, receivedAt: 1, staleAgeMs: null },
    outcome: { status: 'idle', result: null, artifacts: null, error: null },
  };
}

function envelope(overrides = {}) {
  return {
    schema_version: '1.0',
    run_id: 'run-threat',
    seq: 1,
    sim_time: 10,
    state: 'RUNNING',
    playback: {},
    os: { north: 1, east: 2, psi: 0, sog: 2, cog: 0 },
    obstacles: [],
    truth: [],
    measurements: [],
    tracks: [],
    planner: null,
    events: [],
    ...overrides,
  };
}

test('canonical threat projection preserves backend vectors, schedule, conflicts, and reasons', () => {
  const projection = createTelemetryProjection();
  const canonical = {
    schema_version: 'colav.threat-management.projection@1',
    status: 'AVAILABLE',
    snapshot: { semantic_hash: 'snapshot-1' },
    vectors: [
      { key: { target_id: 2, generation: 1 }, dcpa_m: 12, predicted_domain: { state: 'INSIDE' } },
      { key: { target_id: 1, generation: 3 }, dcpa_m: 90, predicted_domain: { state: 'UNKNOWN' } },
    ],
    schedule: {
      current_primary: { target_id: 2, generation: 1 },
      concurrent_required: [{ target_id: 1, generation: 3 }],
      next: [],
      monitor: [],
    },
    conflicts: { edges: [{ source: { target_id: 2 }, target: { target_id: 1 }, type: 'DIRECT_WINDOW_OVERLAP' }] },
    unavailable_reason: null,
  };
  const snapshot = projection.project(runtime(envelope({
    threat_management: canonical,
    // Contradictory legacy values must not be consulted by the projection.
    primary_encounter: { target_id: 99, dcpa_m: 999 },
    encounters: [{ target_id: 99, dcpa_m: 999 }],
    dcpa: 999,
    tcpa: 999,
    colregs: 'head_on',
  })));

  assert.equal(snapshot.risk.status, 'AVAILABLE');
  assert.equal(snapshot.risk.primary.targetId, 2);
  assert.deepEqual(snapshot.risk.targets.map(target => target.targetId), [2, 1]);
  assert.equal(snapshot.risk.primary.dcpaM, 12);
  assert.deepEqual(snapshot.risk.schedule.concurrentRequired, [{ target_id: 1, generation: 3 }]);
  assert.deepEqual(snapshot.risk.conflicts, canonical.conflicts);
  assert.equal(snapshot.risk.snapshotHash, 'snapshot-1');
});

test('legacy envelope without canonical threat facts stays explicitly unavailable', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtime(envelope({
    encounters: [{ target_id: 1, dcpa_m: 1, signed_tcpa_s: 1 }],
    primary_encounter: { target_id: 1, dcpa_m: 1 },
    dcpa: 1,
    tcpa: 1,
    colregs: 'head_on',
  })));

  assert.equal(snapshot.risk.status, 'UNAVAILABLE');
  assert.equal(snapshot.risk.unavailableReason, 'THREAT_SNAPSHOT_UNAVAILABLE');
  assert.equal(snapshot.risk.primary, null);
  assert.deepEqual(snapshot.risk.targets, []);
  assert.equal(snapshot.risk.dcpaM, null);
  assert.equal(snapshot.risk.tcpaS, null);
  assert.equal(snapshot.risk.colregs, null);
  assert.equal(snapshot.risk.schedule, null);
  assert.equal(snapshot.risk.conflicts, null);
});

test('canvas threat style reads explicit backend display class and never uses distance fallbacks', async () => {
  const { targetThreatStyle } = await import('../../web_gui/modules/situation-display.js');
  const target = { id: 1, x: 0, y: 0 };
  assert.equal(
    targetThreatStyle({
      threat_management: {
        status: 'AVAILABLE',
        vectors: [{ key: { target_id: 1, generation: 1 }, display_class: 'HIGH' }],
      },
      os: { x: 0, y: 0 },
    }, target),
    'HIGH',
  );
  assert.equal(
    targetThreatStyle({
      threat_management: {
        status: 'AVAILABLE',
        vectors: [{ key: { target_id: 1, generation: 1 } }],
      },
      os: { x: 0, y: 0 },
    }, target),
    'UNKNOWN',
  );
  assert.equal(
    targetThreatStyle({ encounters: [{ target_id: 1, dcpa_m: 1 }], os: { x: 0, y: 0 } }, target),
    'UNKNOWN',
  );
});
