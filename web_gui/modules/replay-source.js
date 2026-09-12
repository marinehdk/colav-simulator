/**
 * Replay source adapter (ticket #71, Technical Design §8.2).
 *
 * Converts sealed Decision Trace window documents + immutable static context
 * into the versioned Telemetry Envelope input the EXISTING
 * telemetry-projection.js interprets. This is a transport/source adapter
 * only: risk, planner, lifecycle and outcome interpretation stay in the
 * canonical projection — nothing here derives, recomputes or interpolates
 * discrete facts. Continuous kinematics interpolate strictly between two
 * sealed frames and never extrapolate.
 */

import { interpolateVesselKinematics } from './kinematics.js';

export const REPLAY_PRESENTATION_MODE = 'HISTORICAL_REPLAY';

// Transport bounds mirroring the live envelope publication policy: the raw
// stored evidence keeps the complete audit; the envelope carries the recent
// window and explicit truncation markers.
const EVIDENCE_RECENT_EVENTS = 32;
const MAX_TRAIL_POINTS = 120;

const SHIP_KEYS = Object.keys;

function localShips(payload, context) {
  const origin = context?.enc ?? {};
  const originN = Number.isFinite(origin.origin_north_m) ? origin.origin_north_m : 0;
  const originE = Number.isFinite(origin.origin_east_m) ? origin.origin_east_m : 0;
  const staticShips = Array.isArray(context?.ships) ? context.ships : [];
  const ships = [];
  for (const key of SHIP_KEYS(payload ?? {}).sort((a, b) => Number(a.replace('Ship', '')) - Number(b.replace('Ship', '')))) {
    const raw = payload[key];
    if (!raw || typeof raw !== 'object') continue;
    const state = Array.isArray(raw.state) ? raw.state : [];
    const csog = Array.isArray(raw.csog_state) ? raw.csog_state : [];
    const north = Number(state[0]);
    const east = Number(state[1]);
    const staticShip = staticShips.find(ship => String(ship?.id) === String(raw.id));
    const colav = raw.colav && typeof raw.colav === 'object' ? boundedColav(raw.colav) : {};
    ships.push({
      id: raw.id,
      mmsi: raw.mmsi ?? null,
      length: staticShip?.length_m ?? null,
      width: staticShip?.width_m ?? null,
      x: Number.isFinite(north) ? north - originN : null,
      y: Number.isFinite(east) ? east - originE : null,
      north,
      east,
      psi: state[2] ?? null,
      u: state[3] ?? null,
      v: state[4] ?? null,
      r: raw.turn_rate ?? state[5] ?? null,
      sog: csog[2] ?? null,
      cog: csog[3] ?? null,
      trajectory: [],
      active: raw.active ?? true,
      historical_sample_kind: String(raw.historical_actor_truth?.sample_kind ?? '').toUpperCase() || null,
      dimensions_provenance: raw.historical_actor_dimensions?.provenance ?? null,
      measurements: raw.sensor_measurements ?? null,
      tracks: localTracks(raw, originN, originE),
      colav,
    });
  }
  return { ships, originN, originE };
}

function localTracks(raw, originN, originE) {
  const states = (Array.isArray(raw.do_estimates) ? raw.do_estimates : []).map((state) => {
    const local = [...state];
    if (local.length >= 2) {
      if (Number.isFinite(local[0])) local[0] -= originN;
      if (Number.isFinite(local[1])) local[1] -= originE;
    }
    return local;
  });
  return {
    labels: raw.do_labels ?? [],
    generations: raw.do_generations ?? [],
    states,
    covariances: raw.do_covariances ?? [],
    nis: raw.do_NISes ?? [],
  };
}

function boundedColav(colav) {
  const planner = colav?.planner;
  const timeline = planner && typeof planner === 'object' ? planner.evidence_timeline : null;
  if (!timeline || !Array.isArray(timeline.events)) return colav;
  return {
    ...colav,
    planner: {
      ...planner,
      evidence_timeline: {
        ...timeline,
        events: timeline.events.slice(-EVIDENCE_RECENT_EVENTS),
        events_total: timeline.events.length,
        events_truncated: timeline.events.length > EVIDENCE_RECENT_EVENTS,
      },
    },
  };
}

function localWaypoints(rawWaypoints, originN, originE) {
  const waypoints = Array.isArray(rawWaypoints) ? rawWaypoints : [];
  if (waypoints.length !== 2 || !Array.isArray(waypoints[0]) || waypoints.length === 0) return [[], []];
  return [
    waypoints[0].map(value => (Number.isFinite(value) ? value - originN : value)),
    waypoints[1].map(value => (Number.isFinite(value) ? value - originE : value)),
  ];
}

function orderedFrames(windowDoc) {
  const frames = [];
  if (Array.isArray(windowDoc?.frames)) frames.push(...windowDoc.frames);
  return frames.filter(frame => frame && typeof frame === 'object' && Number.isFinite(Number(frame.sim_time)))
    .sort((a, b) => Number(a.sim_time) - Number(b.sim_time));
}

function shipPlanner(frame) {
  const colav = frame?.payload?.Ship0?.colav;
  return colav?.planner && typeof colav.planner === 'object' ? colav.planner : null;
}

function interpolateVesselDisplay(from, to, amount) {
  if (!from) return to;
  if (!to) return from;
  return { ...to, ...interpolateVesselKinematics(from, to, amount) };
}

function trailsToPlayhead(orderedUpTo, playhead, interpolatedPosition, sourceIndex, origin) {
  const originN = origin.originN;
  const originE = origin.originE;
  const trail = [];
  for (const frame of orderedUpTo) {
    const raw = frame.payload?.[sourceIndex];
    const state = Array.isArray(raw?.state) ? raw.state : null;
    if (!state) continue;
    const north = Number(state[0]);
    const east = Number(state[1]);
    if (Number.isFinite(north) && Number.isFinite(east)) trail.push([north - originN, east - originE]);
  }
  if (interpolatedPosition) {
    trail.push([interpolatedPosition.x, interpolatedPosition.y]);
  }
  return trail.length > MAX_TRAIL_POINTS ? trail.slice(trail.length - MAX_TRAIL_POINTS) : trail;
}

/**
 * Project one paused playhead onto the recorded evidence.
 *
 * Returns {ok:true, envelope, sourceFrame, upperFrame, interpolated} or
 * {ok:false, reason, playhead}. Never extrapolates beyond sealed frames.
 */
export function projectReplayFrame({ descriptor, context, windowDoc, playhead }) {
  const time = Number(playhead);
  if (!windowDoc || !descriptor) return { ok: false, reason: 'NO_RECORDED_FRAME', playhead };

  const frames = orderedFrames(windowDoc);
  const bracket = [];
  if (windowDoc.before && Number.isFinite(Number(windowDoc.before.sim_time))) bracket.push(windowDoc.before);
  bracket.push(...frames);
  const afterFrame = windowDoc.after && Number.isFinite(Number(windowDoc.after.sim_time)) ? windowDoc.after : null;

  if (!bracket.length) return { ok: false, reason: 'NO_RECORDED_FRAME', playhead };

  let sourceIndex = -1;
  for (let index = 0; index < bracket.length; index += 1) {
    if (Number(bracket[index].sim_time) <= time) sourceIndex = index;
  }
  if (sourceIndex === -1) return { ok: false, reason: 'NO_RECORDED_FRAME', playhead };

  const sourceFrame = bracket[sourceIndex];
  let upperFrame = sourceIndex + 1 < bracket.length ? bracket[sourceIndex + 1] : null;
  if (upperFrame === null && afterFrame !== null && Number(afterFrame.sim_time) >= Number(sourceFrame.sim_time)) {
    upperFrame = afterFrame;
  }

  const trustedEnd = Number(descriptor?.replay?.trusted_t_end);
  if (upperFrame === null && time > Number(sourceFrame.sim_time)) {
    // Strictly beyond the last loaded frame: never extrapolate. Either the
    // evidence itself ends here (incomplete) or the next window is needed.
    if (Number.isFinite(trustedEnd) && time > trustedEnd) {
      return { ok: false, reason: 'BEYOND_TRUSTED_EVIDENCE', playhead };
    }
    return { ok: false, reason: 'BRACKET_UNAVAILABLE', playhead };
  }
  if (upperFrame === null) upperFrame = sourceFrame;

  const upperTime = Number(upperFrame.sim_time);
  const sourceTime = Number(sourceFrame.sim_time);
  const span = upperTime - sourceTime;
  const alpha = span > 0 ? Math.max(0, Math.min(1, (time - sourceTime) / span)) : 0;
  const interpolated = alpha > 0;

  const envelope = buildEnvelope({
    descriptor,
    context,
    sourceFrame,
    upperFrame,
    alpha,
    interpolated,
    playhead: time,
    priorFrames: bracket.slice(0, sourceIndex + 1),
  });
  return { ok: true, envelope, sourceFrame, upperFrame, interpolated };
}

function buildEnvelope({ descriptor, context, sourceFrame, upperFrame, alpha, interpolated, playhead, priorFrames }) {
  const payload = sourceFrame.payload ?? {};
  const { ships, originN, originE } = localShips(payload, context);
  const upperPayload = upperFrame?.payload ?? {};

  const upperShips = localShips(upperPayload, context).ships;
  const upperById = new Map(upperShips.map(ship => [String(ship.id), ship]));
  ships.forEach((ship, index) => {
    const upper = upperById.get(String(ship.id));
    if (interpolated && upper) {
      const kinematics = interpolateVesselKinematics(ship, upper, alpha);
      Object.assign(ship, kinematics);
    }
    ship.trajectory = trailsToPlayhead(priorFrames, playhead, ship, `Ship${index}`, { originN, originE });
  });

  const own = ships[0] ?? null;
  const obstacles = ships.slice(1);
  const ownRaw = payload.Ship0 ?? {};
  const planner = ownRaw.colav?.planner ?? null;

  // Discrete alias reconstruction (Transport-Bookkeeping): the recorded
  // source of the planner display policy is the latest RECORDED solve at or
  // before the playhead. Solved only from loaded frames; when the loaded
  // window predates the last solve, the display falls back to the current
  // frame's recorded planner document — facts are never recomputed.
  let latestSolvePlanner = null;
  for (const frame of priorFrames) {
    const candidate = shipPlanner(frame);
    if (candidate?.solver_executed === true) latestSolvePlanner = candidate;
  }
  const render = planner?.prediction_render ?? null;
  const typedRender = render !== null && typeof render === 'object' && render.schema_version === 'colav.mid_mpc.prediction-render@1';
  const executable = typedRender ? render.executable === true : planner?.solver_executed === true;
  const activePlan = executable ? planner : {};
  const latestAttempt = latestSolvePlanner ?? (planner ? planner : null);

  const prediction = typedRender
    ? horizonFromRender(render, originN, originE)
    : horizonFromPlanner(planner, originN, originE);

  const targetRoutes = [];
  for (const key of SHIP_KEYS(payload).sort((a, b) => Number(a.replace('Ship', '')) - Number(b.replace('Ship', ''))).slice(1)) {
    const raw = payload[key];
    const route = Array.isArray(raw?.waypoints) ? raw.waypoints : null;
    if (!route || route.length !== 2) continue;
    targetRoutes.push({
      target_id: raw.id,
      waypoints: [
        (route[0] ?? []).map(value => (Number.isFinite(value) ? value - originN : value)),
        (route[1] ?? []).map(value => (Number.isFinite(value) ? value - originE : value)),
      ],
      speed_mps: raw.csog_state?.[2] ?? null,
    });
  }

  const run = descriptor?.run ?? {};
  const envelope = {
    schema_version: '1.0',
    run_id: descriptor?.run_id ?? null,
    scenario_id: run.scenario_id ?? context?.scenario_id ?? null,
    seq: sourceFrame.sequence,
    sim_time: playhead,
    state: sourceFrame.state ?? null,
    truth: ships,
    measurements: ships.map(ship => ship.measurements),
    tracks: ships.map(ship => ship.tracks),
    plans: {
      waypoints: localWaypoints(ownRaw.waypoints, originN, originE),
      prediction_horizon: prediction.current,
      previous_prediction_horizon: [],
      rejected_prediction_horizon: typedRender && render.style === 'REJECTED' ? prediction.current : [],
      target_prediction_horizons: typedRender ? prediction.targets : [],
      rejected_target_prediction_horizons: typedRender && render.style === 'REJECTED' ? prediction.targets : [],
      target_routes: targetRoutes,
      prediction_render: typedRender ? render : null,
    },
    enc_navigation_area: context?.enc_navigation_area ?? null,
    threat_management: sourceFrame.threat_management,
    planner,
    latest_planner_solve: latestSolvePlanner,
    active_planner_plan: activePlan,
    latest_planner_attempt: latestAttempt,
    execution: {
      solve_id: planner?.solve_id ?? 0,
      applied_course_ref_rad: ownRaw.references?.[2] ?? null,
      applied_speed_ref_mps: ownRaw.references?.[3] ?? null,
      selected_command: planner?.selected_command ?? {},
    },
    events: sourceFrame.events ?? [],
    operational_events: [],
    step: sourceFrame.sequence,
    scenario_time: playhead,
    running: sourceFrame.state === 'RUNNING',
    os: own,
    obstacles,
    waypoints: localWaypoints(ownRaw.waypoints, originN, originE),
    prediction_horizon: prediction.current,
    target_routes: targetRoutes,
    selected_algorithm: run.executed_algorithm ?? null,
    requested_algorithm: run.requested_algorithm ?? null,
    executed_algorithm: run.executed_algorithm ?? null,
    requested_tracker: run.requested_tracker ?? null,
    executed_tracker: run.executed_tracker ?? null,
    selected_rule: run.validation_rule_id ?? null,
    selected_scenario: run.scenario_id ?? null,
    step_time_ms: sourceFrame.step_time_ms ?? 0.0,
    presentation: {
      mode: REPLAY_PRESENTATION_MODE,
      source_sequence: sourceFrame.sequence,
      source_sim_time_s: Number(sourceFrame.sim_time),
      source_upper_sequence: upperFrame === sourceFrame ? null : upperFrame.sequence,
      interpolated,
      buffered: false,
    },
    // Replay never presents live transport/session connectivity state: the
    // `playback` live field is deliberately absent, and navigation.latitude /
    // longitude (live UTM geodesy) stay unavailable rather than being
    // re-derived by a second geodesy implementation in the browser.
  };
  return envelope;
}

function horizonFromPlanner(planner, originN, originE) {
  const predicted = Array.isArray(planner?.predicted_trajectory) ? planner.predicted_trajectory : [];
  if (predicted.length === 0 || predicted.every(row => !Array.isArray(row))) return { current: [], targets: [] };
  return {
    current: [
      (predicted[0] ?? []).map(value => (Number.isFinite(value) ? value - originN : value)),
      (predicted[1] ?? []).map(value => (Number.isFinite(value) ? value - originE : value)),
    ],
    targets: [],
  };
}

function horizonFromRender(render, originN, originE) {
  const horizon = (points) => {
    const north = Array.isArray(points?.north_m) ? points.north_m : null;
    const east = Array.isArray(points?.east_m) ? points.east_m : null;
    if (!north || !east || north.length !== east.length || north.length === 0) return [];
    return [
      north.map(value => (Number.isFinite(value) ? value - originN : value)),
      east.map(value => (Number.isFinite(value) ? value - originE : value)),
    ];
  };
  const current = render.frame === 'ENU' ? horizon(render.ownship) : [];
  const targets = (Array.isArray(render.targets) ? render.targets : [])
    .filter(target => target?.purpose !== 'L4_SAFETY')
    .map(horizon)
    .filter(horizonPoints => horizonPoints.length > 0);
  return { current, targets };
}
