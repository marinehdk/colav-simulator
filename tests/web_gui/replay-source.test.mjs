import assert from 'node:assert/strict';
import test from 'node:test';

import { createTelemetryProjection } from '../../web_gui/modules/telemetry-projection.js';
import { projectReplayFrame } from '../../web_gui/modules/replay-source.js';

/* ── Known-literal recorded evidence (no simulator, no current code paths) ── */

const RUN_ID = 'abababab-abab-4bab-8bab-abababababab';

const CONTEXT = {
  schema_version: 'colav.run-replay.context@1',
  run_id: RUN_ID,
  scenario_id: 'head_on',
  enc: {
    origin_east_m: 1000,
    origin_north_m: 2000,
    width_m: 4000,
    height_m: 6000,
    utm_zone: 32,
    image_url: `/api/runs/${RUN_ID}/replay/enc.png`,
  },
  enc_navigation_area: {
    schema_version: '1.0',
    coordinate_frame: 'local_north_east_m',
    safe_water: { type: 'MultiPolygon', polygons: [[[0, 0], [10, 0], [10, 10]]] },
  },
  ships: [
    { id: 0, mmsi: 100, length_m: 45, width_m: 8 },
    { id: 1, mmsi: 200, length_m: 30, width_m: 6 },
  ],
};

const DESCRIPTOR = {
  schema_version: 'colav.run-replay.descriptor@1',
  run_id: RUN_ID,
  run: {
    execution_state: 'FINISHED',
    scenario_id: 'head_on',
    requested_algorithm: 'vo',
    executed_algorithm: 'vo',
    requested_tracker: 'god',
    executed_tracker: 'god',
    result_ready: true,
  },
  replay: {
    state: 'READY',
    evidence_level: 'full',
    trace_schema: 'colav.decision-replay.v1',
    frame_count: 400,
    t_start: 0.1,
    t_end: 40.0,
    trusted_t_end: 40.0,
    truncated: false,
  },
  events: { count: 3, categories: ['planner_solved'] },
  capabilities: { full_frame: true, planner_detail: true, risk_detail: true, continuous_interpolation: true },
};

/* Frame payloads written as raw simulator-frame literals: Ship0 north 2050 /
   east 2010 -> local x = 2050 - 2000 = 50, y = 2010 - 1000 = 1010 (hand
   computed). Ship1 north 2060 / east 1120 -> x 60, y 120. */
function framePayload({ north0, east0, psi0, north1, east1, psi1 }, { solve } = {}) {
  const planner = solve
    ? {
        algorithm_id: 'vo',
        solve_id: 7,
        solver_executed: true,
        status: 'OK',
        feasible: true,
        elapsed_ms: 12,
        selected_command: { course_rad: 0.19, speed_mps: 2.1 },
        predicted_trajectory: [[2050, 2010], [2100, 2060]],
        threat_management: {
          status: 'AVAILABLE',
          vectors: [{ key: { target_id: 1, generation: 2 }, display_class: 'HIGH', dcpa_m: 150, tcpa_forward_s: 30 }],
          schedule: { current_primary: { target_id: 1, generation: 2 } },
        },
      }
    : {
        algorithm_id: 'vo',
        solve_id: 7,
        solver_executed: false,
        status: 'OK',
      };
  return {
    Ship0: {
      id: 0,
      mmsi: 100,
      state: [north0, east0, psi0, 2.0, 0.1, 0.02],
      csog_state: [north0, east0, 2.2, 0.21],
      turn_rate: 0.02,
      active: true,
      waypoints: [[2050, 2010], [2650, 2610]],
      references: [0.0, 0.0, 0.19, 2.1],
      sensor_measurements: [[1, 2, 3]],
      do_estimates: [[north1, east1, 0.1, 0.2]],
      do_labels: [1],
      do_generations: [2],
      do_covariances: [[1.0, 0.5]],
      do_NISes: [3.5],
      colav: { planner },
    },
    Ship1: {
      id: 1,
      mmsi: 200,
      state: [north1, east1, psi1, 1.0, 0.2, 0.0],
      csog_state: [north1, east1, 1.4, 1.2],
      active: true,
    },
  };
}

const THREAT_A = {
  schema_version: 'colav.threat-management.projection@1',
  status: 'AVAILABLE',
  snapshot: null,
  vectors: [{ key: { target_id: 1, generation: 2 }, display_class: 'HIGH', dcpa_m: 150, tcpa_forward_s: 30 }],
  schedule: { current_primary: { target_id: 1, generation: 2 } },
  conflicts: null,
  conflict_graph: null,
  unavailable_reason: null,
};

const THREAT_B = {
  schema_version: 'colav.threat-management.projection@1',
  status: 'UNAVAILABLE',
  snapshot: null,
  vectors: [],
  schedule: null,
  conflicts: null,
  conflict_graph: null,
  unavailable_reason: 'THREAT_SNAPSHOT_UNAVAILABLE',
};

/* Solve tick A (t=10.0, seq 100) and hold tick B (t=10.5, seq 105).
   Ship0 heading wraps between A (psi 6.2) and B (psi 0.1): shortest path. */
const FRAME_A = {
  sequence: 100,
  sim_time: 10.0,
  step_time_ms: 5.5,
  state: 'RUNNING',
  payload: framePayload({ north0: 2050, east0: 2010, psi0: 6.2, north1: 2060, east1: 1120, psi1: 1.0 }, { solve: true }),
  events: [{ type: 'planner_solved', sim_time: 10.0, details: { solve_id: 7 } }],
  threat_management: THREAT_A,
};

const FRAME_B = {
  sequence: 105,
  sim_time: 10.5,
  step_time_ms: 5.7,
  state: 'RUNNING',
  payload: framePayload({ north0: 2053, east0: 2013, psi0: 0.1, north1: 2062, east1: 1122, psi1: 1.02 }, { solve: false }),
  events: [],
  threat_management: THREAT_B,
};

const WINDOW_DOC = {
  schema_version: 'colav.run-replay.window@1',
  run_id: RUN_ID,
  requested: { from_s: 9.9, to_s: 10.6 },
  frames: [FRAME_A, FRAME_B],
  before: { sequence: 99, sim_time: 9.9, state: 'RUNNING', step_time_ms: 5.0, payload: {}, events: [] },
  after: null,
};

function runtimeSnapshot(envelope) {
  return { session: { session_id: envelope.run_id, state: envelope.state }, telemetry: { envelope } };
}

function projectEnvelope(envelope) {
  const projection = createTelemetryProjection();
  return projection.project(runtimeSnapshot(envelope));
}

/* ── Exact stored source frame: Replay ≡ Live Telemetry Projection ── */

test('at an exact stored frame the replay projection equals the live projection (except enumerated metadata)', () => {
  const result = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: WINDOW_DOC, playhead: 10.0 });
  assert.equal(result.ok, true);
  assert.equal(result.interpolated, false);
  assert.equal(result.sourceFrame.sequence, 100);

  const replayProjection = projectEnvelope(result.envelope);

  /* Canonical live Telemetry Envelope for the SAME captured frame, written
     literally from the live envelope conventions (hand computed): */
  const ship0 = {
    id: 0, mmsi: 100, length: 45, width: 8,
    x: 50, y: 1010, north: 2050, east: 2010, psi: 6.2,
    u: 2.0, v: 0.1, r: 0.02, sog: 2.2, cog: 0.21,
    trajectory: [[50, 1010]], active: true,
    measurements: [[1, 2, 3]],
    tracks: { labels: [1], generations: [2], states: [[60, 120, 0.1, 0.2]], covariances: [[1.0, 0.5]], nis: [3.5] },
    colav: FRAME_A.payload.Ship0.colav,
  };
  const ship1 = {
    id: 1, mmsi: 200, x: 60, y: 120, north: 2060, east: 1120, psi: 1.0,
    u: 1.0, v: 0.2, r: 0.0, sog: 1.4, cog: 1.2, trajectory: [[60, 120]], active: true,
  };
  const liveEnvelope = {
    schema_version: '1.0',
    run_id: RUN_ID,
    scenario_id: 'head_on',
    seq: 100,
    sim_time: 10.0,
    state: 'RUNNING',
    truth: [ship0, ship1],
    measurements: [ship0.measurements, undefined],
    tracks: [ship0.tracks, undefined],
    plans: {
      waypoints: [[50, 650], [10, 610]],
      prediction_horizon: [[50, 1010], [100, 1060]],
      previous_prediction_horizon: [],
      rejected_prediction_horizon: [],
      target_prediction_horizons: [],
      rejected_target_prediction_horizons: [],
      target_routes: [],
      prediction_render: null,
    },
    enc_navigation_area: CONTEXT.enc_navigation_area,
    threat_management: THREAT_A,
    planner: FRAME_A.payload.Ship0.colav.planner,
    latest_planner_solve: FRAME_A.payload.Ship0.colav.planner,
    active_planner_plan: FRAME_A.payload.Ship0.colav.planner,
    latest_planner_attempt: FRAME_A.payload.Ship0.colav.planner,
    execution: { solve_id: 7, applied_course_ref_rad: 0.19, applied_speed_ref_mps: 2.1, selected_command: { course_rad: 0.19, speed_mps: 2.1 } },
    events: FRAME_A.events,
    operational_events: [],
    os: ship0,
    obstacles: [ship1],
    waypoints: [[50, 650], [10, 610]],
    step_time_ms: 5.5,
    executed_algorithm: 'vo',
    requested_algorithm: 'vo',
    executed_tracker: 'god',
    requested_tracker: 'god',
    selected_rule: 'rule14',
    selected_scenario: 'head_on',
  };

  const liveProjection = projectEnvelope(liveEnvelope);

  // navigation: equal except enumerated live-transport/geodesy metadata.
  for (const field of ['north', 'east', 'psi', 'sog', 'cog', 'u', 'v', 'simTime', 'state', 'running']) {
    assert.deepEqual(replayProjection.navigation[field], liveProjection.navigation[field], `navigation.${field}`);
  }
  // sensor: identical targets.
  assert.deepEqual(replayProjection.sensor.targets, liveProjection.sensor.targets);
  // risk: identical canonical interpretation.
  assert.deepEqual(replayProjection.risk, liveProjection.risk);
  // planner: identical display selection (the recorded solve).
  assert.deepEqual(replayProjection.planner.display, liveProjection.planner.display);
  assert.equal(replayProjection.planner.algorithmId, 'vo');
  assert.equal(replayProjection.planner.solveId, 7);
  assert.equal(replayProjection.planner.phase, liveProjection.planner.phase);
  assert.equal(replayProjection.planner.appliedCourseRefRad, liveProjection.planner.appliedCourseRefRad);
  assert.deepEqual(replayProjection.planner.selectedCommand, liveProjection.planner.selectedCommand);
});

test('playhead between two sealed frames interpolates kinematics only and keeps discrete facts on the source frame', () => {
  const result = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: WINDOW_DOC, playhead: 10.25 });
  assert.equal(result.ok, true);
  assert.equal(result.interpolated, true);
  assert.equal(result.sourceFrame.sequence, 100);
  assert.equal(result.upperFrame.sequence, 105);

  const envelope = result.envelope;
  // Hand-computed midpoint: x (50 -> 53)/2 = 51.5, y (1010 -> 1013)/2 = 1011.5.
  assert.ok(Math.abs(envelope.os.x - 51.5) < 1e-9);
  assert.ok(Math.abs(envelope.os.y - 1011.5) < 1e-9);
  // Heading wraps 6.2 -> 0.1 the short way: +0.182 rad. Hand-computed
  // midpoint 6.2 + 0.182/2 = 6.2916 (the same angle as 0.0084 mod 2*pi).
  const angularDiff = (a, b) => Math.atan2(Math.sin(a - b), Math.cos(a - b));
  const midPsi = 6.2915926535897935;
  assert.ok(Math.abs(angularDiff(envelope.os.psi, midPsi)) < 1e-9);
  // Discrete facts are NEVER interpolated: risk/planner stay on frame A.
  assert.deepEqual(envelope.threat_management, THREAT_A);
  assert.equal(envelope.planner.solver_executed, true);
  assert.equal(envelope.planner.solve_id, 7);
  // Presentation namespace identifies the source evidence.
  assert.equal(envelope.presentation.mode, 'HISTORICAL_REPLAY');
  assert.equal(envelope.presentation.source_sequence, 100);
  assert.equal(envelope.presentation.source_sim_time_s, 10.0);
  assert.equal(envelope.presentation.interpolated, true);
  assert.equal(envelope.sim_time, 10.25);
});

test('presentation never claims live transport state', () => {
  const result = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: WINDOW_DOC, playhead: 10.0 });
  const envelope = result.envelope;
  assert.equal(envelope.presentation.mode, 'HISTORICAL_REPLAY');
  assert.equal(envelope.presentation.buffered, false);
  assert.equal(envelope.playback, undefined);
});

test('unbracketable playhead is reported instead of extrapolated', () => {
  // Playhead past the last loaded frame with no successor bracket: the
  // successor must be fetched (buffering), never extrapolated.
  const buffering = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: WINDOW_DOC, playhead: 10.55 });
  assert.deepEqual(buffering, { ok: false, reason: 'BRACKET_UNAVAILABLE', playhead: 10.55 });

  // A recorded successor frame IS a sealed bracket: interpolation is allowed.
  const pending = { ...WINDOW_DOC, after: { sequence: 106, sim_time: 10.6, state: 'RUNNING', payload: {}, events: [] } };
  const bracketed = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: pending, playhead: 10.55 });
  assert.equal(bracketed.ok, true);
  assert.equal(bracketed.interpolated, true);
  assert.equal(bracketed.sourceFrame.sequence, 105);
  assert.equal(bracketed.upperFrame.sequence, 106);

  // Playhead beyond the trusted recorded boundary: incomplete, never invented.
  const truncatedDescriptor = {
    ...DESCRIPTOR,
    replay: { ...DESCRIPTOR.replay, t_end: 10.5, trusted_t_end: 10.5, truncated: true },
  };
  const incomplete = projectReplayFrame({
    descriptor: truncatedDescriptor,
    context: CONTEXT,
    windowDoc: { ...WINDOW_DOC, after: null },
    playhead: 10.55,
  });
  assert.deepEqual(incomplete, { ok: false, reason: 'BEYOND_TRUSTED_EVIDENCE', playhead: 10.55 });

  // No frames at all (empty window).
  const empty = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: null, playhead: 10.0 });
  assert.deepEqual(empty, { ok: false, reason: 'NO_RECORDED_FRAME', playhead: 10.0 });
});

test('actual track-to-playhead is clipped to the playhead', () => {
  const result = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: WINDOW_DOC, playhead: 10.25 });
  const trajectory = result.envelope.os.trajectory;
  assert.ok(trajectory.length >= 2);
  for (const point of trajectory) {
    assert.ok(point[0] <= result.envelope.os.x + 1e-9);
  }
  assert.ok(Math.abs(trajectory.at(-1)[0] - result.envelope.os.x) < 1e-9);
});

test('hold-tick planner display falls back to the reconstructed recorded solve', () => {
  const result = projectReplayFrame({ descriptor: DESCRIPTOR, context: CONTEXT, windowDoc: WINDOW_DOC, playhead: 10.5 });
  assert.equal(result.ok, true);
  const envelope = result.envelope;
  // The hold frame itself never executed; the recorded solve from frame A
  // (inside the loaded window) is the display source, as in Live.
  assert.equal(envelope.planner.solver_executed, false);
  assert.equal(envelope.latest_planner_solve.solve_id, 7);
  assert.equal(envelope.latest_planner_solve.solver_executed, true);
  const projection = projectEnvelope(envelope);
  assert.equal(projection.planner.display.solver_executed, true);
  assert.equal(projection.planner.algorithmId, 'vo');
});

test('legacy windows without backend threat documents degrade without invention', () => {
  const legacyFrame = (frame) => {
    const { threat_management: _ignored, ...rest } = frame;
    return rest;
  };
  const result = projectReplayFrame({
    descriptor: DESCRIPTOR,
    context: CONTEXT,
    windowDoc: { ...WINDOW_DOC, frames: [legacyFrame(FRAME_A), legacyFrame(FRAME_B)], before: null },
    playhead: 10.0,
  });
  assert.equal(result.ok, true);
  assert.equal(result.envelope.threat_management, undefined);
  const projection = projectEnvelope(result.envelope);
  assert.equal(projection.risk.status, 'UNAVAILABLE');
  assert.equal(projection.risk.unavailableReason, 'THREAT_SNAPSHOT_UNAVAILABLE');
});
