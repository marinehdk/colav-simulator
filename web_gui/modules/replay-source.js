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
import { createGeography } from './scene-geography.js?v=20261004-token-cleanup-v1';

export const REPLAY_PRESENTATION_MODE = 'HISTORICAL_REPLAY';

/* ── Replay AIS display-state reconstruction (P3-9, spec #91 batch-2b) ──
 *
 * Live envelopes carry the backend-authoritative `truth[].ais =
 * {age_s, state}` (gui_server/main.py::_record_ais_reports +
 * colav_simulator/core/ais_display.py). A sealed replay has no live
 * transponder clock, so the report age is REBUILT on the web from the
 * recorded frames: the functions below are the web mirror of the backend
 * formulas — SAME constants, SAME M.1371 table, SAME clock walk (the
 * backend remains the authority; a divergence here is a bug to fix on both
 * sides together). The replay playhead is the display clock, which makes
 * the rebuilt age deterministic under seek / playback rate / pause.
 */

const MPS_PER_KNOT = 1852.0 / 3600.0;

/** Display policy mirrors of core/ais_display.py (same values, same meaning). */
export const AIS_ACTIVE_SOG_MPS = 0.5;
export const AIS_LOST_AGE_FACTOR = 3.0;

const AIS_CLASS_A_SOG_KN_ANCHORED = 0.001;
const AIS_CLASS_A_SOG_KN_MODERATE = 14.0;
const AIS_CLASS_A_SOG_KN_FAST = 23.0;
const AIS_CLASS_B_SOG_KN_SLOW = 2.0;

/** Web mirror of `ais_reporting_interval_s` (core/ais_display.py):
 *  ITU-R M.1371 autonomous-mode position-report interval in seconds. */
export function aisReportingIntervalS(sogMps, aisClass = 'A') {
  const sogKnots = Number(sogMps) / MPS_PER_KNOT;
  if (String(aisClass).toUpperCase() === 'B') {
    return sogKnots <= AIS_CLASS_B_SOG_KN_SLOW ? 180.0 : 30.0;
  }
  if (sogKnots <= AIS_CLASS_A_SOG_KN_ANCHORED) return 180.0;
  if (sogKnots <= AIS_CLASS_A_SOG_KN_MODERATE) return 10.0;
  if (sogKnots <= AIS_CLASS_A_SOG_KN_FAST) return 6.0;
  return 2.0;
}

/** Web mirror of `ais_target_state` (core/ais_display.py): lost/active/sleeping. */
export function aisTargetState(sogMps, ageS, aisClass = 'A') {
  const age = Number(ageS);
  if (!Number.isFinite(Number(sogMps)) || !Number.isFinite(age)
    || age > AIS_LOST_AGE_FACTOR * aisReportingIntervalS(sogMps, aisClass)) {
    return 'lost';
  }
  if (Number(sogMps) >= AIS_ACTIVE_SOG_MPS) return 'active';
  return 'sleeping';
}

/**
 * Replay mirror of the backend report clock (`AisReportClock.advance` walked
 * by main.py::_record_ais_reports over the recorded frames).
 *
 * `reportSamples` is one sample per recorded FULL frame carrying the ship,
 * in ascending `t_s` order: `{t_s, sog_mps, inactive}` (`inactive` mirrors
 * the historical-replay data-gap kind: no transponder report arrives, the
 * age keeps growing). A new report emits when the elapsed sim time reaches
 * the speed-dependent expected interval; the returned age is
 * `playheadS - lastReport` and grows continuously between reports, exactly
 * like the live display clock.
 *
 * Reconstruction boundary: the window `history` strip carries positions
 * only (no SOG, no sample kind), so the clock starts at the first full
 * frame at or before the playhead — ages near a window start read as a
 * fresh report. The live page loads a bounded recent window the same way.
 */
export function replayAisReportAge(reportSamples, playheadS) {
  const playhead = Number(playheadS);
  let lastReport = null;
  for (const sample of Array.isArray(reportSamples) ? reportSamples : []) {
    const t = Number(sample?.t_s);
    if (!Number.isFinite(t) || t > playhead) break; // samples are ascending
    if (sample.inactive) continue; // data gap: hold the clock, age grows
    const interval = aisReportingIntervalS(sample.sog_mps);
    if (lastReport === null || t < lastReport || t - lastReport >= interval) {
      lastReport = t;
    }
  }
  return lastReport === null ? 0.0 : Math.max(0.0, playhead - lastReport);
}

/** Recorded full-frame samples for one ship id (ascending sim time). */
function replayAisSamples(frames, shipId) {
  const samples = [];
  for (const frame of frames) {
    const raw = frame?.payload
      ? Object.values(frame.payload).find(ship => String(ship?.id) === String(shipId))
      : null;
    if (!raw || typeof raw !== 'object') continue;
    const csog = Array.isArray(raw.csog_state) ? raw.csog_state : [];
    const sog = Number(csog[2]);
    samples.push({
      t_s: Number(frame.sim_time),
      sog_mps: Number.isFinite(sog) ? sog : 0.0,
      inactive: String(raw.historical_actor_truth?.sample_kind ?? '').toLowerCase() === 'inactive',
    });
  }
  return samples;
}

// Transport bounds mirroring the live envelope publication policy: the raw
// stored evidence keeps the complete audit; the envelope carries the recent
// window and explicit truncation markers.
const EVIDENCE_RECENT_EVENTS = 32;
const MAX_TRAIL_POINTS = 120;

const SHIP_KEYS = Object.keys;
const geographyByContext = new WeakMap();

function replayGeography(context) {
  if (!context || typeof context !== 'object') return null;
  if (geographyByContext.has(context)) return geographyByContext.get(context);
  const enc = context.enc ?? {};
  const zone = enc.utm_zone;
  let geography = null;
  if ([32, 33].includes(zone) && [enc.origin_east_m, enc.origin_north_m, enc.width_m, enc.height_m]
    .every(value => typeof value === 'number' && Number.isFinite(value))) {
    try {
      geography = createGeography({
        ready: true, run_id: context.run_id,
        utm_zone: zone, horizontal_crs: `EPSG:${25800 + zone}`, hemisphere: 'north',
        display_height_reference: 'ellipsoid-zero-visual-only',
        origin_e: enc.origin_east_m, origin_n: enc.origin_north_m,
        width: enc.width_m, height: enc.height_m,
      });
    } catch { /* Missing chart georeference stays unavailable. */ }
  }
  geographyByContext.set(context, geography);
  return geography;
}

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
    // P3-S5 (spec #90): sensor-model-v1 §6 additive confidence arrays —
    // passthrough only; rendering decisions live in situation-display.
    existence_prob: raw.do_existence_probabilities ?? null,
    quality: raw.do_qualities ?? null,
    sources: raw.do_sources ?? null,
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
    if (Number(frame.sim_time) > playhead) continue;
    const raw = Object.values(frame.payload ?? {}).find(ship => String(ship?.id) === String(sourceIndex));
    const state = Array.isArray(raw?.state) ? raw.state : null;
    if (!state) continue;
    const north = Number(state[0]);
    const east = Number(state[1]);
    if (Number.isFinite(north) && Number.isFinite(east)) trail.push([north - originN, east - originE]);
  }
  if (interpolatedPosition) {
    const point = [interpolatedPosition.x, interpolatedPosition.y];
    const last = trail.at(-1);
    if (!last || last[0] !== point[0] || last[1] !== point[1]) trail.push(point);
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

  const checkpoints = windowDoc.radar_checkpoints ?? {};
  const recordedFrame = frame => {
    if (!frame?.payload?.Ship0?.radar_scans) return frame;
    const scans = frame.payload.Ship0.radar_scans.map(scan => {
      const video = scan.shadow_video;
      const key = video?.checkpoint?.$radar_checkpoint;
      return key ? { ...scan, shadow_video: { ...video, checkpoint: checkpoints[key] ?? null } } : scan;
    });
    return { ...frame, payload: { ...frame.payload, Ship0: { ...frame.payload.Ship0, radar_scans: scans } } };
  };
  const frames = orderedFrames(windowDoc).map(recordedFrame);
  const bracket = [];
  if (windowDoc.before && Number.isFinite(Number(windowDoc.before.sim_time))) bracket.push(recordedFrame(windowDoc.before));
  bracket.push(...frames);
  const afterFrame = windowDoc.after && Number.isFinite(Number(windowDoc.after.sim_time)) ? recordedFrame(windowDoc.after) : null;

  if (!bracket.length) return { ok: false, reason: 'NO_RECORDED_FRAME', playhead };

  let sourceIndex = -1;
  for (let index = 0; index < bracket.length; index += 1) {
    if (Number(bracket[index].sim_time) <= time) sourceIndex = index;
  }
  if (sourceIndex === -1) return { ok: false, reason: 'NO_RECORDED_FRAME', playhead };

  const sourceFrame = bracket[sourceIndex];
  let decisionSpace = windowDoc.decision_space_before ?? null;
  for (const frame of bracket.slice(0, sourceIndex + 1)) {
    if (frame.vo_decision_space) decisionSpace = frame.vo_decision_space;
  }
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
    history: Array.isArray(windowDoc.history) ? windowDoc.history : [],
  });
  return { ok: true, envelope, sourceFrame, upperFrame, interpolated, decisionSpace };
}

function buildEnvelope({ descriptor, context, sourceFrame, upperFrame, alpha, interpolated, playhead, priorFrames, history }) {
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
    ship.trajectory = trailsToPlayhead([...history, ...priorFrames], playhead, ship, ship.id, { originN, originE });
    if (index >= 1) {
      // P3-9 replay AIS backfill: additive display field on obstacles only
      // (ownship carries no AIS object), same shape as the live transport.
      // Age is rebuilt from the recorded full frames at/before the playhead
      // with the mirror clock; the state judgment uses the displayed
      // (interpolated) SOG — the playhead analog of the live current SOG.
      const ageS = replayAisReportAge(replayAisSamples(priorFrames, ship.id), playhead);
      ship.ais = { age_s: ageS, state: aisTargetState(ship.sog, ageS) };
    }
  });

  const own = ships[0] ?? null;
  const geography = replayGeography(context);
  if (own && geography && Number.isFinite(own.x) && Number.isFinite(own.y)) {
    const [longitude, latitude] = geography.lonLat(own.x, own.y);
    own.latitude = latitude;
    own.longitude = longitude;
  }
  const depth = sourceFrame.ownship_navigation ?? {};
  if (own) {
    own.floor_depth_m = Number.isFinite(depth.floor_depth_m) ? depth.floor_depth_m : null;
    own.floor_depth_source = depth.source ?? 'ENC_DEPTH_BIN_UNAVAILABLE';
  }
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
    radar_scans: ownRaw.radar_scans ?? [],
    ais_reports: ownRaw.ais_reports ?? [],
    radar_ppi: ownRaw.radar_scans?.[0]?.descriptor ?? null,
    radar_video_history: priorFrames.filter(frame => Number(frame.sim_time) <= Number(sourceFrame.sim_time))
      .map(frame => frame.payload?.Ship0?.radar_scans?.[0])
      .filter(scan => scan?.shadow_video && Number(sourceFrame.sim_time) - Number(scan.t_s) <= 3),
    tracks: ships.map(ship => ship.tracks),
    plans: {
      waypoints: localWaypoints(ownRaw.waypoints, originN, originE),
      prediction_horizon: typedRender && !executable ? [] : prediction.current,
      previous_prediction_horizon: typedRender ? prediction.history : [],
      rejected_prediction_horizon: typedRender && render.style === 'REJECTED' ? prediction.current : [],
      target_prediction_horizons: !typedRender || render.style === 'ACTIVE' ? prediction.targets : [],
      rejected_target_prediction_horizons: typedRender && render.style === 'REJECTED' ? prediction.targets : [],
      target_routes: targetRoutes,
      prediction_render: typedRender ? render : null,
    },
    enc_navigation_area: context?.enc_navigation_area ?? null,
    threat_management: sourceFrame.threat_management,
    gnc_balance: sourceFrame.gnc_balance ?? null,
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
    prediction_horizon: typedRender && !executable ? [] : prediction.current,
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
    // The live `playback` transport field is deliberately absent. Position
    // uses the shared chart geodesy; depth comes only from matched ENC evidence.
  };
  return envelope;
}

function localHorizon(north, east, originN, originE) {
  if (!Array.isArray(north) || !Array.isArray(east) || north.length !== east.length) return [];
  if (!north.every(Number.isFinite) || !east.every(Number.isFinite)) return [];
  return north.map((value, index) => [value - originN, east[index] - originE]);
}

function horizonFromPlanner(planner, originN, originE) {
  const projected = planner?.algorithm_details?.render_projection;
  const predicted = planner?.predicted_trajectory ?? [];
  const current = projected?.frame === 'ENU'
    ? localHorizon(projected.ownship?.north_m, projected.ownship?.east_m, originN, originE)
    : localHorizon(predicted[0], predicted[1], originN, originE);
  const targets = (planner?.target_predictions ?? []).map(target =>
    localHorizon(target.north_m ?? target.x, target.east_m ?? target.y, originN, originE)
  ).filter(points => points.length > 0);
  return { current, targets };
}

function horizonFromRender(render, originN, originE) {
  if (render.frame !== 'ENU') return { current: [], targets: [], history: [] };
  const horizon = points => localHorizon(points?.north_m, points?.east_m, originN, originE);
  const current = horizon(render.ownship);
  const targets = (Array.isArray(render.targets) ? render.targets : [])
    .filter(target => target?.purpose === 'L4_SAFETY')
    .map(horizon)
    .filter(points => points.length > 0);
  const previous = horizon(render.history?.ownship);
  return { current, targets, history: previous.length ? previous : render.style === 'INVALID_HISTORY' ? current : [] };
}
