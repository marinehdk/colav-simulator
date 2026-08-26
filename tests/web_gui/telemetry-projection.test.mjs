import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createTelemetryProjection,
  SBMPC_SOLVE_PERIOD_FALLBACK_S,
  VO_SOLVE_PERIOD_FALLBACK_S,
} from '../../web_gui/modules/telemetry-projection.js';

/* ── Fake runtime snapshots (plain object literals, public seam only) ── */

function runtimeSnapshot({ envelope, outcomeStatus = 'idle', result = null, artifacts = null } = {}) {
  return {
    session: envelope?.run_id ? { session_id: envelope.run_id, state: envelope.state } : null,
    sessionState: envelope?.state ?? 'none',
    telemetry: { envelope: envelope ?? null, revision: 1, receivedAt: 1, staleAgeMs: null },
    outcome: { status: outcomeStatus, result, artifacts, error: null },
  };
}

function ownShip(overrides = {}) {
  return {
    id: 0,
    mmsi: 123,
    x: 12.5,
    y: -3.25,
    north: 632_500,
    east: 142_000,
    psi: 0.4,
    u: 2.1,
    v: 0.05,
    r: 0.001,
    sog: 2.2,
    cog: 0.42,
    latitude: 62.7,
    longitude: 6.35,
    active: true,
    trajectory: [],
    ...overrides,
  };
}

function encounter(overrides = {}) {
  return {
    ownship_id: 0,
    target_id: 1,
    encounter: 'head_on',
    validation_rule_id: 'rule14',
    stage: 2,
    distance_m: 900,
    dcpa_m: 800,
    tcpa_s: 300,
    signed_tcpa_s: 300,
    relative_bearing_deg: 1.5,
    fsm_state: 'STAND_ON',
    ...overrides,
  };
}

function envelope(overrides = {}) {
  return {
    schema_version: '1.0',
    run_id: 'run-1',
    seq: 1,
    sim_time: 10,
    state: 'RUNNING',
    playback: { requested_multiplier: 1, effective_multiplier: 1, realtime_limited: false, scheduler_lag_ms: 0.5 },
    os: ownShip(),
    obstacles: [],
    truth: [],
    measurements: [],
    tracks: [],
    encounters: [],
    primary_encounter: null,
    dcpa: null,
    tcpa: null,
    colregs: 'clear',
    planner: null,
    latest_planner_solve: null,
    execution: null,
    events: [],
    plans: null,
    step_time_ms: 12.5,
    reproduction_status: 'running',
    executed_tracker: 'god',
    executed_algorithm: null,
    requested_algorithm: null,
    ...overrides,
  };
}

function stubEnvelope() {
  return { schema_version: '1.0', run_id: null, seq: 0, sim_time: 0.0, state: 'CREATED', events: [] };
}

function countingListener() {
  const calls = [];
  const listener = (snapshot) => calls.push(snapshot);
  return { calls, notifications: () => calls.length, listener };
}

/* ── 1. HOLD vs latest real SOLVE ── */
test('HOLD frame keeps current separate while display selects the latest real SOLVE', () => {
  const projection = createTelemetryProjection();
  const current = {
    algorithm_id: 'sbmpc',
    solve_id: 7,
    solver_executed: false,
    status: 'SUCCESS',
    feasible: true,
    sim_time: 42,
    horizon_dt_s: 2.5,
    selected_command: { course_rad: 0.3, speed_mps: 2 },
    algorithm_details: { solve_period_s: 5 },
  };
  const latestSolve = { ...current, solver_executed: true, sim_time: 35 };
  const first = projection.project(runtimeSnapshot({
    envelope: envelope({ planner: current, latest_planner_solve: latestSolve }),
  }));
  assert.equal(first.planner.phase, 'HOLD');
  assert.equal(first.planner.current, current);
  assert.equal(first.planner.latestSolve, latestSolve);
  assert.equal(first.planner.display, latestSolve);
  assert.equal(first.planner.algorithmId, 'sbmpc');
  assert.equal(first.planner.solveId, 7);
  assert.equal(first.planner.status, 'SUCCESS');
  assert.equal(first.planner.feasible, true);
  assert.equal(first.planner.solvePeriodS, 5);
  assert.equal(first.planner.appliedCourseRefRad, 0.3);
  assert.equal(first.planner.appliedSpeedRefMps, 2);
});

/* ── 2. Nominal planner is SOLVE ── */
test('nominal guidance frames report SOLVE phase without a solver execution', () => {
  const projection = createTelemetryProjection();
  const planner = {
    algorithm_id: 'nominal',
    solve_id: 0,
    solver_executed: false,
    algorithm_details: { planner_kind: 'nominal_guidance' },
  };
  const snapshot = projection.project(runtimeSnapshot({ envelope: envelope({ planner }) }));
  assert.equal(snapshot.planner.phase, 'SOLVE');
  assert.equal(snapshot.planner.display, planner);
});

/* ── 3. Canonical threat projection ── */
test('risk targets preserve canonical backend order and schedule without browser ranking', () => {
  const projection = createTelemetryProjection();
  const vectors = [
    { key: { target_id: 1, generation: 1 }, dcpa_m: 800, tcpa_forward_s: 300, display_class: 'LOW' },
    { key: { target_id: 2, generation: 1 }, dcpa_m: 150, tcpa_forward_s: 60, display_class: 'HIGH' },
    { key: { target_id: 3, generation: 1 }, dcpa_m: 400, tcpa_forward_s: 120, display_class: 'CLEAR' },
  ];
  const snapshot = projection.project(runtimeSnapshot({
    envelope: envelope({
      threat_management: {
        status: 'AVAILABLE',
        snapshot: { semantic_hash: 'threat-1', profile_hash: 'profile-1', vectors },
        vectors,
        schedule: {
          current_primary: { target_id: 2, generation: 1 },
          entries: [
            { key: { target_id: 1, generation: 1 }, context: 'MONITOR' },
            { key: { target_id: 2, generation: 1 }, context: 'CURRENT_PRIMARY' },
            { key: { target_id: 3, generation: 1 }, context: 'NEXT' },
          ],
        },
        conflict_graph: { edges: [], clusters: [] },
      },
      // Contradictory legacy fields must not affect projection.
      encounters: [encounter({ target_id: 99, dcpa_m: 1 })],
      primary_encounter: encounter({ target_id: 99, dcpa_m: 1 }),
      dcpa: 1,
      tcpa: 1,
    }),
  }));
  assert.deepEqual(snapshot.risk.targets.map((target) => target.targetId), [1, 2, 3]);
  assert.equal(snapshot.risk.primary.targetId, 2);
  assert.equal(snapshot.risk.primary.displayClass, 'HIGH');
  assert.equal(snapshot.risk.primary.scheduleClass, 'CURRENT_PRIMARY');
  assert.equal(snapshot.risk.dcpaM, 150);
  assert.equal(snapshot.risk.tcpaS, 60);
  assert.deepEqual(snapshot.risk.conflictGraph, { edges: [], clusters: [] });
});

test('risk DCPA and TCPA never fall back to legacy root mirrors', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({
    envelope: envelope({ dcpa: 155.3, tcpa: 42.5 }),
  }));
  assert.equal(snapshot.risk.status, 'UNAVAILABLE');
  assert.equal(snapshot.risk.dcpaM, null);
  assert.equal(snapshot.risk.tcpaS, null);
});

/* ── 4. Clear ── */
test('missing canonical facts yields unavailable, not an inferred clear state', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({ envelope: envelope() }));
  assert.equal(snapshot.risk.status, 'UNAVAILABLE');
  assert.equal(snapshot.risk.primary, null);
  assert.equal(snapshot.risk.colregs, null);
  assert.deepEqual(snapshot.risk.targets, []);
  assert.equal(snapshot.risk.dcpaM, null, 'null root mirrors stay null instead of Infinity or zero');
  assert.equal(snapshot.risk.tcpaS, null);
});

/* ── 5. Missing planner ── */
test('absent or empty planner sections degrade to null fields without throwing', () => {
  const projection = createTelemetryProjection();
  const absent = projection.project(runtimeSnapshot({ envelope: envelope() }));
  assert.equal(absent.planner.current, null);
  assert.equal(absent.planner.latestSolve, null);
  assert.equal(absent.planner.display, null);
  assert.equal(absent.planner.phase, 'HOLD');
  assert.equal(absent.planner.algorithmId, null);
  assert.equal(absent.planner.status, null);
  assert.equal(absent.planner.feasible, null);
  assert.equal(absent.planner.solvePeriodS, null);
  assert.equal(absent.planner.horizonLength, 0);
  assert.equal(absent.planner.appliedCourseRefRad, null);

  const empty = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 2, planner: {}, latest_planner_solve: {} }),
  }));
  assert.deepEqual(empty.planner.current, {});
  assert.equal(empty.planner.latestSolve, null);
  assert.equal(empty.planner.algorithmId, null);
  assert.equal(empty.planner.status, null);
});

/* ── 6. Stub / partial envelopes ── */
test('stub envelope without own ship projects a null navigation section and raw facts only', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({ envelope: stubEnvelope() }));
  assert.equal(snapshot.sessionId, null);
  assert.equal(snapshot.seq, 0);
  assert.equal(snapshot.simTime, 0.0);
  assert.equal(snapshot.state, 'CREATED');
  assert.equal(snapshot.raw.run_id, null);
  assert.equal(snapshot.navigation, null);
  assert.deepEqual(snapshot.sensor.targets, []);
  assert.equal(snapshot.risk.primary, null);
  assert.equal(snapshot.planner.algorithmId, null);
  assert.equal(snapshot.outcome.status, 'idle');
  assert.equal(snapshot.outcome.resultReady, false);
});

test('navigation projects raw own ship facts and playback status', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({ envelope: envelope() }));
  assert.equal(snapshot.navigation.north, 632_500);
  assert.equal(snapshot.navigation.east, 142_000);
  assert.equal(snapshot.navigation.psi, 0.4);
  assert.equal(snapshot.navigation.sog, 2.2);
  assert.equal(snapshot.navigation.latitude, 62.7);
  assert.equal(snapshot.navigation.simTime, 10);
  assert.equal(snapshot.navigation.running, true);
  assert.equal(snapshot.navigation.stepTimeMs, 12.5);
  assert.deepEqual(snapshot.navigation.playback, {
    requestedMultiplier: 1,
    effectiveMultiplier: 1,
    realtimeLimited: false,
    schedulerLagMs: 0.5,
  });
});

test('sensor projection preserves tracker generation with the displayed estimate', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({
    envelope: envelope({
      executed_tracker: 'kf',
      obstacles: [{ id: 7, mmsi: 123456789, x: 10, y: 20, active: true }],
      tracks: [{ labels: [7], generations: [3], states: [[11, 21, 2, 1]], covariances: [] }],
    }),
  }));

  assert.equal(snapshot.sensor.targets[0].id, 7);
  assert.equal(snapshot.sensor.targets[0].generation, 3);
  assert.equal(snapshot.sensor.targets[0].positionSource, 'tracker');
});

/* ── 7. Duplicate-snapshot skip ── */
test('duplicate envelope keys return the cached snapshot without notifying subscribers', () => {
  const projection = createTelemetryProjection();
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  const baseline = calls.length;

  const first = projection.project(runtimeSnapshot({ envelope: envelope({ seq: 5 }) }));
  assert.equal(calls.length, baseline + 1);
  const second = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 5, os: ownShip({ x: 999 }) }),
  }));
  assert.equal(second, first, 'duplicate key must return the cached snapshot');
  assert.equal(calls.length, baseline + 1, 'duplicate key must not notify subscribers');
  projection.project(runtimeSnapshot({ envelope: envelope({ seq: 6 }) }));
  assert.equal(calls.length, baseline + 2, 'a new sequence notifies subscribers');
});

/* ── 8. Playback change re-projects ── */
test('playback multiplier changes re-project even at an unchanged sequence', () => {
  const projection = createTelemetryProjection();
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 9, playback: { requested_multiplier: 1, effective_multiplier: 1, realtime_limited: false, scheduler_lag_ms: 0 } }),
  }));
  const next = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 9, playback: { requested_multiplier: 2, effective_multiplier: 1.4, realtime_limited: true, scheduler_lag_ms: 3 } }),
  }));
  assert.equal(next.navigation.playback.requestedMultiplier, 2);
  assert.equal(next.navigation.playback.effectiveMultiplier, 1.4);
  assert.equal(next.navigation.playback.realtimeLimited, true);
  assert.equal(calls[calls.length - 1], next);
});

/* ── 9. Duplicate event delivery ── */
test('events re-delivered across consecutive envelopes yield a single timeline entry', () => {
  const projection = createTelemetryProjection();
  const event = { type: 'collision', sequence: 4, sim_time: 12, details: { ownship_id: 0, target_id: 2 } };
  projection.project(runtimeSnapshot({ envelope: envelope({ seq: 10, events: [event] }) }));
  projection.project(runtimeSnapshot({ envelope: envelope({ seq: 11, events: [{ ...event }] }) }));
  const collisions = projection.snapshot().timeline.events.filter((entry) => entry.type === 'collision');
  assert.equal(collisions.length, 1);
  assert.equal(collisions[0].sequence, 4);
  assert.equal(collisions[0].simTime, 12);
  assert.equal(collisions[0].source, 'envelope');
});

/* ── 10. Trimmed planner_solved details ── */
test('planner_solved timeline entries store trimmed solve facts without the planner payload', () => {
  const projection = createTelemetryProjection();
  projection.project(runtimeSnapshot({
    envelope: envelope({
      seq: 20,
      events: [{
        type: 'planner_solved',
        sequence: 20,
        sim_time: 20.5,
        details: {
          ship_id: 0,
          planner: {
            solve_id: 4,
            status: 'SUCCESS',
            feasible: true,
            elapsed_ms: 12.5,
            algorithm_id: 'sbmpc',
            predicted_trajectory: [[0, 0], [1, 1]],
            constraints: { activation_distance_m: 1000 },
          },
        },
      }],
    }),
  }));
  const entry = projection.snapshot().timeline.events.find((item) => item.type === 'planner_solved');
  assert.ok(entry);
  assert.deepEqual(entry.details, { ship_id: 0, solve_id: 4, status: 'SUCCESS', feasible: true, elapsed_ms: 12.5 });
  assert.ok(!('planner' in entry.details));
  assert.equal(JSON.stringify(entry.details).includes('predicted_trajectory'), false);
});

/* ── 11. Backend-owned threat events ── */
test('projection does not synthesize COLREG or DCPA events from legacy fields', () => {
  const projection = createTelemetryProjection();

  const first = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 1, primary_encounter: encounter({ target_id: 2, dcpa_m: 800 }), dcpa: 800, colregs: 'head_on' }),
  }));
  assert.equal(first.risk.status, 'UNAVAILABLE');
  assert.equal(first.timeline.events.filter((event) => event.source === 'derived').length, 0);
});

test('backend envelope events remain deduplicated across repeated snapshots', () => {
  const projection = createTelemetryProjection();
  let seq = 1;
  const event = { type: 'threat_schedule_changed', sequence: 1, details: { target_id: 1 } };
  const push = () => projection.project(runtimeSnapshot({
    envelope: envelope({ seq: seq++, events: [event] }),
  }));
  push();
  push();
  const keys = projection.snapshot().timeline.events.filter((item) => item.source === 'envelope').map((item) => item.key);
  assert.equal(new Set(keys).size, keys.length);
  assert.equal(keys.length, 1);
});

/* ── 12. Session replacement ── */
test('a new session id clears history and dedup keys before projecting', () => {
  const projection = createTelemetryProjection();
  const event = { type: 'grounding', sequence: 2, details: { ship_id: 1 } };
  projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 2, events: [event], primary_encounter: encounter(), dcpa: 800, colregs: 'head_on' }),
  }));
  assert.ok(projection.snapshot().timeline.events.length > 0);

  const replacement = projection.project(runtimeSnapshot({
    envelope: envelope({
      run_id: 'run-2',
      seq: 1,
      events: [{ type: 'grounding', sequence: 2, details: { ship_id: 1 } }],
      primary_encounter: encounter(),
      dcpa: 800,
      colregs: 'head_on',
    }),
  }));
  assert.equal(replacement.sessionId, 'run-2');
  const envelopeEvents = replacement.timeline.events.filter((item) => item.source === 'envelope');
  assert.equal(envelopeEvents.length, 1, 'old dedup keys must not suppress the new session event');
  const derived = replacement.timeline.events.filter((item) => item.source === 'derived');
  assert.equal(derived.length, 0, 'browser does not recreate backend threat state machines');
});

/* ── 13. Safety fields ── */
test('safety sections derive from live events and prefer the result document', () => {
  const projection = createTelemetryProjection();
  const clean = projection.project(runtimeSnapshot({ envelope: envelope({ seq: 1 }) }));
  assert.equal(clean.outcome.ship0Safety, null);
  assert.equal(clean.outcome.globalSafety, null);

  const grounded = projection.project(runtimeSnapshot({
    envelope: envelope({
      seq: 2,
      events: [
        { type: 'grounding', sequence: 2, details: { ship_id: 0 } },
        { type: 'collision', sequence: 2, details: { ownship_id: 0, target_id: 3 } },
      ],
    }),
  }));
  assert.deepEqual(grounded.outcome.ship0Safety, { grounded: true, groundingDistanceM: null });
  assert.deepEqual(grounded.outcome.globalSafety, { collision: true, grounding: true });

  const finished = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 3, state: 'FINISHED', events: [] }),
    outcomeStatus: 'ready',
    result: {
      manifest: { execution_outcome: 'COMPLETED', evaluation_gate: 'SOFT', reproduction_status: 'CONFIRMED' },
      evaluation: {
        vessel_results: [{ vessel_id: 0, grounded: false, grounding_distance_m: 250.5 }],
        pair_results: [{ collision: false }],
        aggregate: { collision_count: 0 },
      },
    },
    artifacts: [{}, {}],
  }));
  assert.deepEqual(finished.outcome.ship0Safety, { grounded: false, groundingDistanceM: 250.5 });
  assert.deepEqual(finished.outcome.globalSafety, { collision: false, grounding: false });
  assert.equal(finished.outcome.status, 'ready');
  assert.equal(finished.outcome.resultReady, true);
  assert.equal(finished.outcome.artifactsCount, 2);
  const { ship0Safety, globalSafety, executionOutcome, evaluationGate } = finished.outcome;
  assert.deepEqual([ship0Safety, globalSafety], [
    { grounded: false, groundingDistanceM: 250.5 },
    { collision: false, grounding: false },
  ]);
  assert.equal(executionOutcome, 'COMPLETED');
  assert.equal(evaluationGate, 'SOFT');
});

/* ── 14. FINISHED result distinctions ── */
test('terminal snapshots keep reproduction, gate, and execution outcome as distinct fields', () => {
  const projection = createTelemetryProjection();
  const live = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 4, state: 'FINISHED', reproduction_status: 'running' }),
  }));
  assert.equal(live.outcome.reproductionStatus, 'running');
  assert.equal(live.outcome.executionOutcome, null);
  assert.equal(live.outcome.evaluationGate, null);

  const evaluated = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 5, state: 'FINISHED', reproduction_status: 'running' }),
    outcomeStatus: 'ready',
    result: {
      manifest: { execution_outcome: 'FAILED', evaluation_gate: 'FAIL', reproduction_status: 'MISMATCH' },
      evaluation: { vessel_results: [], pair_results: [] },
    },
  }));
  assert.equal(evaluated.outcome.executionOutcome, 'FAILED');
  assert.equal(evaluated.outcome.evaluationGate, 'FAIL');
  assert.equal(evaluated.outcome.reproductionStatus, 'MISMATCH');
  assert.notEqual(evaluated.outcome.reproductionStatus, evaluated.outcome.evaluationGate);
});

/* ── 15. Subscriber isolation ── */
test('a throwing listener cannot break other subscribers or projection state', () => {
  const projection = createTelemetryProjection();
  projection.subscribe(() => {
    throw new Error('broken view');
  });
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  const snapshot = projection.project(runtimeSnapshot({ envelope: envelope({ seq: 30 }) }));
  assert.equal(calls.at(-1), snapshot);
  assert.equal(projection.snapshot().sessionId, 'run-1');
});

/* ── 16. Stub handling and explicit reset ── */
test('null envelopes keep the previous projection and reset clears everything', () => {
  const projection = createTelemetryProjection();
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  const first = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 3, events: [{ type: 'time_limit', sequence: 3, details: {} }] }),
  }));
  assert.ok(first.timeline.events.length === 1);

  const stubUpdate = projection.project(runtimeSnapshot({ envelope: null }));
  assert.equal(stubUpdate, first, 'runtime-only updates return the cache silently');
  assert.equal(calls.at(-1), first);
  assert.equal(projection.snapshot().timeline.events.length, 1, 'a null stub must not reset history');

  const stub = projection.project(runtimeSnapshot({ envelope: stubEnvelope() }));
  assert.equal(stub.sessionId, null);
  assert.equal(stub.timeline.events.length, 1, 'a null-id stub envelope must not reset session history');

  projection.reset();
  const emptied = projection.snapshot();
  assert.equal(emptied.sessionId, null);
  assert.equal(emptied.raw, null);
  assert.equal(emptied.timeline.events.length, 0);
  assert.deepEqual(emptied.timeline.limitations, projection.snapshot().timeline.limitations);
  assert.equal(calls.at(-1), emptied, 'reset notifies subscribers with the empty projection');
});

/* ── 17. Post-terminal content changes at an unchanged key ── */
test('a FINISHED rebuild at the same sequence with a final reproduction status re-projects', () => {
  const projection = createTelemetryProjection();
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  const buildOne = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 40, state: 'FINISHED', reproduction_status: 'running' }),
  }));
  const baseline = calls.length;

  const buildTwo = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 40, state: 'FINISHED', reproduction_status: 'behavior_compatible_reconstruction' }),
  }));
  assert.notEqual(buildTwo, buildOne, 'final reproduction status must rebuild the snapshot');
  assert.equal(calls.length, baseline + 1, 'the rebuild notifies subscribers');
  assert.equal(buildTwo.outcome.reproductionStatus, 'behavior_compatible_reconstruction');
  assert.equal(calls.at(-1).outcome.reproductionStatus, 'behavior_compatible_reconstruction');
});

test('outcome-only updates re-project at an unchanged envelope key', () => {
  const projection = createTelemetryProjection();
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  const terminal = envelope({ seq: 41, state: 'FINISHED', reproduction_status: 'running' });
  const idle = projection.project(runtimeSnapshot({ envelope: terminal, outcomeStatus: 'idle' }));
  const baseline = calls.length;

  const loading = projection.project(runtimeSnapshot({ envelope: terminal, outcomeStatus: 'loading' }));
  assert.notEqual(loading, idle, 'idle→loading must rebuild even at an identical envelope key');
  assert.equal(loading.outcome.status, 'loading');

  const ready = projection.project(runtimeSnapshot({
    envelope: terminal,
    outcomeStatus: 'ready',
    result: {
      manifest: { execution_outcome: 'COMPLETED', evaluation_gate: 'SOFT', reproduction_status: 'CONFIRMED' },
      evaluation: { vessel_results: [], pair_results: [] },
    },
    artifacts: [{}],
  }));
  assert.notEqual(ready, loading);
  assert.equal(calls.length, baseline + 2, 'each outcome transition notifies subscribers');
  assert.equal(ready.outcome.status, 'ready');
  assert.equal(ready.outcome.reproductionStatus, 'CONFIRMED');
  assert.equal(ready.outcome.evaluationGate, 'SOFT');
  assert.equal(ready.outcome.executionOutcome, 'COMPLETED');
  assert.equal(ready.outcome.resultReady, true);
});

test('genuinely identical repeats stay suppressed after terminal content tracking', () => {
  const projection = createTelemetryProjection();
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  const terminal = envelope({ seq: 42, state: 'PAUSED', reproduction_status: 'running' });
  const first = projection.project(runtimeSnapshot({
    envelope: terminal,
    outcomeStatus: 'ready',
    result: null,
    artifacts: [{}, {}],
  }));
  const baseline = calls.length;
  const churn = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 42, state: 'PAUSED', reproduction_status: 'running' }),
    outcomeStatus: 'ready',
    result: null,
    artifacts: [{}, {}],
  }));
  assert.equal(churn, first, 'identical envelope and outcome return the cached snapshot');
  assert.equal(calls.length, baseline, 'identical repeats do not notify');
});

/* ── 18. Canonical algorithm identity ── */
test('planner algorithmId uses only the canonical algorithm_id and never falls back to executed or requested', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({
    envelope: envelope({
      seq: 43,
      planner: { solve_id: 3, solver_executed: true },
      executed_algorithm: 'sbmpc',
      requested_algorithm: 'vo',
    }),
  }));
  assert.equal(snapshot.planner.algorithmId, null, 'no algorithm_id on the planner dict means no identity, never an invented chain');
});

/* ── 19. Solve period fallbacks ── */
test('solve period falls back per algorithm family using exported constants', () => {
  assert.equal(SBMPC_SOLVE_PERIOD_FALLBACK_S, 5);
  assert.equal(VO_SOLVE_PERIOD_FALLBACK_S, 1);
  const projection = createTelemetryProjection();
  const sbmpc = projection.project(runtimeSnapshot({
    envelope: envelope({
      seq: 44,
      latest_planner_solve: { solver_executed: true, algorithm_id: 'sbmpc', algorithm_details: {} },
    }),
  }));
  assert.equal(sbmpc.planner.algorithmId, 'sbmpc');
  assert.equal(sbmpc.planner.solvePeriodS, 5);
  const vo = projection.project(runtimeSnapshot({
    envelope: envelope({
      seq: 45,
      latest_planner_solve: { solver_executed: true, algorithm_id: 'vo', algorithm_details: {} },
    }),
  }));
  assert.equal(vo.planner.algorithmId, 'vo');
  assert.equal(vo.planner.solvePeriodS, 1);
  const unknown = projection.project(runtimeSnapshot({
    envelope: envelope({
      seq: 46,
      latest_planner_solve: { solver_executed: true, algorithm_id: 'lattice', algorithm_details: {} },
    }),
  }));
  assert.equal(unknown.planner.algorithmId, 'lattice');
  assert.equal(unknown.planner.solvePeriodS, null, 'unknown families get no invented period');
});

/* ── 20. ship0 result attribution ── */
test('ship0 safety never borrows another vessel result entry', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({
    envelope: envelope({ seq: 50, state: 'FINISHED' }),
    outcomeStatus: 'ready',
    result: {
      manifest: { execution_outcome: 'COMPLETED', evaluation_gate: 'SOFT', reproduction_status: 'CONFIRMED' },
      evaluation: { vessel_results: [{ vessel_id: 2, grounded: true }], pair_results: [] },
    },
  }));
  assert.equal(snapshot.outcome.ship0Safety, null, 'no vessel 0 entry → live-event inference only, never vessel 2');
  assert.deepEqual(snapshot.outcome.globalSafety, { collision: false, grounding: true }, 'the vessel 2 grounding still surfaces globally');
});

/* ── 21. FAILED with artifacts handoff ── */
test('a FAILED run with artifacts but no result document stays honest about live values', () => {
  const projection = createTelemetryProjection();
  const snapshot = projection.project(runtimeSnapshot({
    envelope: envelope({
      seq: 60,
      state: 'FAILED',
      failure_reason: 'ownship grounding',
      reproduction_status: 'running',
      events: [{ type: 'grounding', sequence: 60, details: { ship_id: 0 } }],
    }),
    outcomeStatus: 'ready',
    result: null,
    artifacts: [{ name: 'a' }, { name: 'b' }, { name: 'c' }],
  }));
  assert.equal(snapshot.state, 'FAILED');
  assert.equal(snapshot.outcome.artifactsCount, 3);
  // Honest contract: without a result document the raw envelope value is the
  // live value — the projection does not invent a terminal reproduction status.
  assert.equal(snapshot.outcome.reproductionStatus, 'running');
  assert.deepEqual(snapshot.outcome.ship0Safety, { grounded: true, groundingDistanceM: null });
  assert.deepEqual(snapshot.outcome.globalSafety, { collision: false, grounding: true });
  assert.equal(snapshot.outcome.resultReady, false);
});

/* ── 22. Bounded timeline history ── */
test('timeline history is capped at the dedup budget with the oldest events dropped first', () => {
  const projection = createTelemetryProjection();
  const total = 1005;
  for (let seq = 1; seq <= total; seq += 1) {
    projection.project(runtimeSnapshot({
      envelope: envelope({ seq, events: [{ type: 'time_limit', sequence: seq, sim_time: seq, details: {} }] }),
    }));
  }
  const events = projection.snapshot().timeline.events;
  assert.equal(events.length, 1000, 'the timeline array honors the same 1000-entry budget as the dedup set');
  assert.equal(events[0].sequence, 6, 'oldest events beyond the cap are dropped');
  assert.equal(events.at(-1).sequence, total, 'newest events are present');
});

test('first projection without any envelope emits the empty snapshot once', () => {
  const projection = createTelemetryProjection();
  const { calls, listener } = countingListener();
  projection.subscribe(listener);
  assert.equal(calls[0].sessionId, null);
  const baseline = calls.length;
  const empty = projection.project(runtimeSnapshot({ envelope: null }));
  assert.equal(empty.sessionId, null);
  assert.equal(calls.length, baseline + 1);
  const again = projection.project(runtimeSnapshot({ envelope: null }));
  assert.equal(again, empty);
  assert.equal(calls.length, baseline + 1);
});
