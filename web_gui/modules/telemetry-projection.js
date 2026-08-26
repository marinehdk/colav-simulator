/**
 * Telemetry Projection — DOM-free interpretation of Telemetry Envelopes.
 *
 * Consumes Active Session Runtime snapshots and derives the six projection
 * sections (navigation, sensor, risk, planner, outcome, timeline) plus a
 * read-only `raw` envelope reference. Never fetches, never opens sockets,
 * never touches the DOM.
 */

// Kept as import-compatible constants for old shell consumers. They are not
// used to classify, rank, or derive any threat state in this projection.
export const DCPA_SAFE = 300;
export const DCPA_WARN = 100;

export const SBMPC_SOLVE_PERIOD_FALLBACK_S = 5;
export const VO_SOLVE_PERIOD_FALLBACK_S = 1;

export const TIMELINE_LIMITATIONS = Object.freeze([
  'Lifecycle events never appear in telemetry; the timeline holds per-step events only.',
  'Timeline history only covers snapshots observed by this projection.',
  'Session Replacement clears the timeline and derived event state.',
]);

const SEEN_EVENT_KEY_CAP = 1000;

function freeze(value) {
  return Object.freeze(value);
}

function emptyProjection() {
  return freeze({
    sessionId: null,
    seq: null,
    simTime: null,
    state: null,
    raw: null,
    navigation: null,
    sensor: freeze({ targets: freeze([]) }),
    risk: freeze({
      status: 'UNAVAILABLE',
      unavailableReason: 'THREAT_SNAPSHOT_UNAVAILABLE',
      snapshot: null,
      snapshotHash: null,
      profileHash: null,
      primary: null,
      targets: freeze([]),
      dcpaM: null,
      tcpaS: null,
      colregs: null,
      schedule: null,
      conflicts: null,
      conflictGraph: null,
    }),
    planner: freeze({
      current: null,
      latestSolve: null,
      phase: 'HOLD',
      display: null,
      algorithmId: null,
      solveId: null,
      status: null,
      feasible: null,
      elapsedMs: null,
      horizonDtS: null,
      horizonLength: 0,
      solvePeriodS: null,
      appliedCourseRefRad: null,
      appliedSpeedRefMps: null,
      selectedCommand: null,
    }),
    outcome: freeze({
      status: 'idle',
      executionOutcome: null,
      evaluationGate: null,
      reproductionStatus: null,
      ship0Safety: null,
      globalSafety: null,
      resultReady: false,
      artifactsCount: 0,
    }),
    timeline: freeze({ events: freeze([]), limitations: TIMELINE_LIMITATIONS }),
  });
}

function finiteOrNull(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function projectNavigation(envelope) {
  const os = envelope.os ?? null;
  if (os === null || typeof os !== 'object') return null;
  const playback = envelope.playback ?? {};
  return freeze({
    north: os.north ?? null,
    east: os.east ?? null,
    psi: os.psi ?? null,
    sog: os.sog ?? null,
    cog: os.cog ?? null,
    u: os.u ?? null,
    v: os.v ?? null,
    latitude: os.latitude ?? null,
    longitude: os.longitude ?? null,
    simTime: envelope.sim_time ?? null,
    state: envelope.state ?? null,
    running: envelope.state === 'RUNNING',
    stepTimeMs: envelope.step_time_ms ?? null,
    playback: freeze({
      requestedMultiplier: playback.requested_multiplier ?? null,
      effectiveMultiplier: playback.effective_multiplier ?? null,
      realtimeLimited: Boolean(playback.realtime_limited),
      schedulerLagMs: playback.scheduler_lag_ms ?? null,
    }),
  });
}

/**
 * Tracker-vs-truth merge, moved from the Deployment canvas adapter: when a
 * non-god tracker ran and own-ship tracker estimates exist, display the
 * estimate positions; otherwise display truth positions.
 */
function projectSensor(envelope) {
  const truth = envelope.obstacles ?? [];
  const truthById = new Map(truth.map((ship) => [String(ship.id), ship]));
  const trackSet = envelope.tracks?.[0];
  const generationById = new Map((trackSet?.labels || []).map((id, index) => [
    String(id),
    trackSet?.generations?.[index] ?? null,
  ]));
  if (envelope.executed_tracker === 'god') {
    return freeze({
      targets: freeze(truth.map((ship) => freeze(sensorTarget(
        ship,
        ship.x,
        ship.y,
        'truth',
        ship.generation ?? generationById.get(String(ship.id)) ?? null,
      )))),
    });
  }
  const states = trackSet?.states;
  if (!Array.isArray(states) || states.length === 0) return freeze({ targets: freeze([]) });
  const targets = [];
  states.forEach((state, index) => {
    if (!Array.isArray(state)) return;
    const id = trackSet.labels?.[index] ?? index + 1;
    const ship = truthById.get(String(id)) || null;
    const displayNorth = state[0];
    const displayEast = state[1];
    const velocityNorth = Number(state[2]);
    const velocityEast = Number(state[3]);
    const course = Number.isFinite(velocityNorth) && Number.isFinite(velocityEast)
      ? Math.atan2(velocityEast, velocityNorth)
      : null;
    const speed = Number.isFinite(velocityNorth) && Number.isFinite(velocityEast)
      ? Math.hypot(velocityNorth, velocityEast)
      : null;
    const target = freeze({
      id,
      generation: trackSet.generations?.[index] ?? null,
      mmsi: ship?.mmsi ?? null,
      north: ship?.x ?? null,
      east: ship?.y ?? null,
      psi: course ?? ship?.psi ?? null,
      sog: speed ?? ship?.sog ?? null,
      cog: course ?? ship?.cog ?? null,
      active: ship?.active ?? null,
      positionSource: 'tracker',
      displayNorth: Number.isFinite(displayNorth) ? displayNorth : null,
      displayEast: Number.isFinite(displayEast) ? displayEast : null,
    });
    if (target.displayNorth === null || target.displayEast === null) return;
    targets.push(target);
  });
  return freeze({ targets: freeze(targets) });
}

function sensorTarget(ship, displayNorth, displayEast, positionSource, generation = null) {
  return {
    id: ship.id,
    generation,
    mmsi: ship.mmsi ?? null,
    north: ship.x ?? null,
    east: ship.y ?? null,
    psi: ship.psi ?? null,
    sog: ship.sog ?? null,
    cog: ship.cog ?? null,
    active: ship.active ?? null,
    positionSource,
    displayNorth: Number.isFinite(Number(displayNorth)) ? Number(displayNorth) : null,
    displayEast: Number.isFinite(Number(displayEast)) ? Number(displayEast) : null,
  };
}

function threatKey(value) {
  const key = value?.key ?? value;
  if (!key || typeof key !== 'object') return null;
  const targetId = key.target_id ?? key.targetId ?? null;
  const generation = key.generation ?? null;
  return targetId === null ? null : { target_id: targetId, generation };
}

function sameThreatKey(left, right) {
  const a = threatKey(left);
  const b = threatKey(right);
  return a !== null && b !== null
    && String(a.target_id) === String(b.target_id)
    && ((a.generation === null && b.generation === null)
      || (a.generation !== null && b.generation !== null && String(a.generation) === String(b.generation)));
}

function projectThreatVector(vector, lifecycleFact = null) {
  const key = threatKey(vector);
  const currentDomain = vector?.current_domain ?? vector?.currentDomain ?? null;
  const predictedDomain = vector?.predicted_domain ?? vector?.predictedDomain ?? null;
  const lifecycle = vector?.lifecycle ?? lifecycleFact ?? null;
  const rangeM = finiteOrNull(vector?.range_m ?? vector?.rangeM ?? vector?.distanceM);
  return freeze({
    key,
    targetId: key?.target_id ?? vector?.target_id ?? vector?.targetId ?? null,
    generation: key?.generation ?? vector?.generation ?? null,
    targetLabel: key === null ? null : `TS${key.target_id}`,
    encounter: lifecycle?.encounter ?? vector?.encounter ?? null,
    role: lifecycle?.role ?? vector?.role ?? null,
    commitment: lifecycle?.commitment ?? vector?.commitment ?? null,
    observationHealth: vector?.observation_health ?? vector?.observationHealth ?? null,
    claimCompleteness: vector?.claim_completeness ?? vector?.claimCompleteness ?? null,
    predictionBasis: vector?.prediction_basis ?? vector?.predictionBasis ?? null,
    displayClass: vector?.display_class ?? vector?.displayClass ?? null,
    displayPercent: finiteOrNull(vector?.display_percent ?? vector?.displayPercent),
    scheduleClass: vector?.schedule_class ?? vector?.scheduleClass ?? null,
    priorityClass: vector?.priority_class ?? vector?.priorityClass ?? null,
    priorityReason: vector?.priority_reason ?? vector?.priorityReason ?? null,
    lifecycleRole: vector?.lifecycle_role ?? vector?.lifecycleRole ?? lifecycle?.role ?? null,
    lifecycleRisk: vector?.lifecycle_risk ?? vector?.lifecycleRisk ?? lifecycle?.risk ?? null,
    lifecycleCommitment: vector?.lifecycle_commitment
      ?? vector?.lifecycleCommitment
      ?? lifecycle?.commitment
      ?? null,
    window: vector?.window ?? null,
    unavailableReasons: freeze(Array.isArray(vector?.unavailable_reasons)
      ? [...vector.unavailable_reasons]
      : Array.isArray(vector?.unavailableReasons) ? [...vector.unavailableReasons] : []),
    rangeM,
    distanceM: rangeM,
    closingSpeedMps: finiteOrNull(vector?.closing_speed_mps ?? vector?.closingSpeedMps),
    dcpaM: finiteOrNull(vector?.dcpa_m ?? vector?.dcpaM),
    tcpaS: finiteOrNull(vector?.tcpa_forward_s ?? vector?.tcpaS),
    signedTcpaS: finiteOrNull(vector?.tcpa_signed_s ?? vector?.signedTcpaS),
    hullClearanceM: finiteOrNull(vector?.hull_clearance_m ?? vector?.hullClearanceM),
    uncertaintyRadiusM: finiteOrNull(vector?.uncertainty_radius_m ?? vector?.uncertaintyRadiusM),
    currentDomain: currentDomain && typeof currentDomain === 'object' ? freeze({
      state: currentDomain.state ?? null,
      normalizedScale: finiteOrNull(currentDomain.normalized_scale ?? currentDomain.normalizedScale),
      uncertaintyRadiusM: finiteOrNull(currentDomain.uncertainty_radius_m ?? currentDomain.uncertaintyRadiusM),
      unavailableReason: currentDomain.unavailable_reason ?? currentDomain.unavailableReason ?? null,
    }) : null,
    predictedDomain: predictedDomain && typeof predictedDomain === 'object' ? freeze({
      state: predictedDomain.state ?? null,
      normalizedScale: finiteOrNull(predictedDomain.normalized_scale ?? predictedDomain.normalizedScale),
      horizonMinScale: finiteOrNull(predictedDomain.horizon_min_scale ?? predictedDomain.horizonMinScale),
      tdvS: finiteOrNull(predictedDomain.tdv_s ?? predictedDomain.tdvS),
      tdeS: finiteOrNull(predictedDomain.tde_s ?? predictedDomain.tdeS),
      unavailableReason: predictedDomain.unavailable_reason ?? predictedDomain.unavailableReason ?? null,
    }) : null,
  });
}

function projectThreatSchedule(schedule) {
  if (!schedule || typeof schedule !== 'object') return null;
  return freeze({
    currentPrimary: schedule.current_primary ?? schedule.currentPrimary ?? schedule.primary ?? null,
    concurrentRequired: freeze(Array.isArray(schedule.concurrent_required)
      ? [...schedule.concurrent_required]
      : Array.isArray(schedule.concurrentRequired) ? [...schedule.concurrentRequired] : []),
    next: freeze(Array.isArray(schedule.next)
      ? [...schedule.next]
      : Array.isArray(schedule.next_threats) ? [...schedule.next_threats] : []),
    monitor: freeze(Array.isArray(schedule.monitor) ? [...schedule.monitor] : []),
    released: freeze(Array.isArray(schedule.released) ? [...schedule.released] : []),
    entries: freeze(Array.isArray(schedule.entries) ? [...schedule.entries] : []),
    events: freeze(Array.isArray(schedule.events) ? [...schedule.events] : []),
  });
}

function projectRisk(envelope) {
  const source = envelope.threat_management;
  if (!source || typeof source !== 'object') {
    return freeze({
      status: 'UNAVAILABLE',
      unavailableReason: 'THREAT_SNAPSHOT_UNAVAILABLE',
      snapshot: null,
      snapshotHash: null,
      profileHash: null,
      primary: null,
      targets: freeze([]),
      dcpaM: null,
      tcpaS: null,
      colregs: null,
      schedule: null,
      conflicts: null,
      conflictGraph: null,
    });
  }
  const snapshot = source.snapshot && typeof source.snapshot === 'object' ? source.snapshot : null;
  const rawVectors = Array.isArray(source.vectors)
    ? source.vectors
    : Array.isArray(snapshot?.vectors) ? snapshot.vectors : [];
  const lifecycleTargets = Array.isArray(snapshot?.lifecycle_snapshot?.targets)
    ? snapshot.lifecycle_snapshot.targets
    : Array.isArray(snapshot?.lifecycleSnapshot?.targets) ? snapshot.lifecycleSnapshot.targets : [];
  const targets = rawVectors.map((vector) => projectThreatVector(
    vector,
    lifecycleTargets.find((fact) => sameThreatKey(vector, fact?.key)) ?? null,
  ));
  const schedule = projectThreatSchedule(source.schedule ?? snapshot?.schedule);
  const primaryRef = schedule?.currentPrimary ?? source.primary ?? snapshot?.primary ?? null;
  const primaryIndex = targets.findIndex(target => sameThreatKey(target.key, primaryRef));
  const scheduleEntry = (target) => schedule?.entries?.find(entry => sameThreatKey(target.key, entry?.key));
  const markedTargets = targets.map((target, index) => {
    const entry = scheduleEntry(target);
    return freeze({
      ...target,
      isPrimary: index === primaryIndex,
      scheduleClass: target.scheduleClass ?? entry?.context ?? null,
      priorityClass: target.priorityClass ?? entry?.priority_class ?? null,
      priorityReason: target.priorityReason ?? entry?.priority_reason ?? null,
    });
  });
  const primary = primaryIndex >= 0 ? markedTargets[primaryIndex] : null;
  const available = source.status === 'AVAILABLE' || snapshot !== null;
  return freeze({
    status: available ? 'AVAILABLE' : 'UNAVAILABLE',
    unavailableReason: available ? null : (source.unavailable_reason ?? 'THREAT_SNAPSHOT_UNAVAILABLE'),
    snapshot,
    snapshotHash: snapshot?.semantic_hash ?? snapshot?.semanticHash ?? null,
    profileHash: snapshot?.profile_hash ?? snapshot?.profileHash ?? null,
    primary,
    targets: freeze(markedTargets),
    dcpaM: primary?.dcpaM ?? null,
    tcpaS: primary?.tcpaS ?? null,
    colregs: primary?.encounter ?? null,
    schedule,
    conflicts: source.conflicts ?? source.conflict_graph ?? snapshot?.conflicts ?? snapshot?.conflict_graph ?? null,
    conflictGraph: source.conflict_graph ?? source.conflicts ?? snapshot?.conflict_graph ?? snapshot?.conflicts ?? null,
  });
}

function projectPlanner(envelope) {
  const current = envelope.planner ?? null;
  const latestSolveRaw = envelope.latest_planner_solve ?? null;
  const latestSolve = latestSolveRaw !== null && Object.keys(latestSolveRaw).length > 0
    ? latestSolveRaw
    : null;
  const display = latestSolve?.solver_executed === true ? latestSolve : current;
  const details = display?.algorithm_details ?? null;
  const phase = current?.solver_executed === true
    || current?.algorithm_details?.planner_kind === 'nominal_guidance'
    ? 'SOLVE'
    : 'HOLD';
  const displayAlgorithmId = display?.algorithm_id ?? null;
  const configuredSolvePeriod = finiteOrNull(details?.solve_period_s);
  const fallbackSolvePeriod = displayAlgorithmId === 'sbmpc'
    ? SBMPC_SOLVE_PERIOD_FALLBACK_S
    : displayAlgorithmId === 'vo'
      ? VO_SOLVE_PERIOD_FALLBACK_S
      : null;
  const execution = envelope.execution ?? null;
  const selectedCommand = display?.selected_command ?? null;
  return freeze({
    current,
    latestSolve,
    phase,
    display,
    // Spec D8: only the canonical planner.algorithm_id is projected; the
    // executed/requested envelope mirrors are never used as a fallback chain.
    algorithmId: display?.algorithm_id ?? null,
    solveId: current?.solve_id ?? null,
    status: current?.status ?? null,
    feasible: current?.feasible ?? null,
    elapsedMs: current?.elapsed_ms ?? null,
    horizonDtS: display?.horizon_dt_s ?? null,
    horizonLength: envelope.plans?.prediction_horizon?.length ?? 0,
    solvePeriodS: configuredSolvePeriod ?? fallbackSolvePeriod,
    appliedCourseRefRad: execution?.applied_course_ref_rad ?? selectedCommand?.course_rad ?? null,
    appliedSpeedRefMps: execution?.applied_speed_ref_mps ?? selectedCommand?.speed_mps ?? null,
    selectedCommand: selectedCommand ?? null,
  });
}

function trimEventDetails(type, details) {
  if (type !== 'planner_solved') return details ?? null;
  const planner = details?.planner ?? {};
  return {
    ship_id: details?.ship_id ?? null,
    solve_id: planner.solve_id ?? null,
    status: planner.status ?? null,
    feasible: planner.feasible ?? null,
    elapsed_ms: planner.elapsed_ms ?? null,
  };
}

function recordEnvelopeEvents(envelope, sessionId, state) {
  const events = Array.isArray(envelope.events) ? envelope.events : [];
  const recorded = [];
  events.forEach((event) => {
    if (!event || typeof event !== 'object') return;
    const key = [
      sessionId,
      event.sequence ?? envelope.seq ?? '',
      event.type,
      event.details?.ship_id ?? '',
      event.details?.planner?.solve_id ?? '',
    ].join(':');
    if (state.seenEventKeys.has(key)) return;
    state.seenEventKeys.add(key);
    if (state.seenEventKeys.size > SEEN_EVENT_KEY_CAP) {
      state.seenEventKeys.delete(state.seenEventKeys.values().next().value);
    }
    if (event.type === 'grounding' && event.details?.ship_id === 0) state.ship0Grounded = true;
    if (event.type === 'grounding') state.anyGrounding = true;
    if (event.type === 'collision') state.anyCollision = true;
    recorded.push(freeze({
      key,
      sequence: event.sequence ?? envelope.seq ?? null,
      simTime: event.sim_time ?? envelope.sim_time ?? null,
      type: event.type,
      source: 'envelope',
      details: freeze(trimEventDetails(event.type, event.details)),
    }));
  });
  return recorded;
}

function projectOutcome(runtimeOutcome, envelope, state) {
  const result = runtimeOutcome?.result ?? null;
  const manifest = result?.manifest ?? null;
  const evaluation = result?.evaluation ?? null;
  const vesselResults = Array.isArray(evaluation?.vessel_results) ? evaluation.vessel_results : [];
  const pairResults = Array.isArray(evaluation?.pair_results) ? evaluation.pair_results : [];
  // Own ship is vessel 0 in the result doc; entries for other vessels never
  // stand in for it — absence falls back to live-event inference.
  const resultShip0 = vesselResults.find((entry) => entry?.vessel_id === 0) ?? null;
  const ship0Safety = resultShip0
    ? freeze({
      grounded: Boolean(resultShip0.grounded),
      groundingDistanceM: resultShip0.grounding_distance_m ?? null,
    })
    : state.ship0Grounded
      ? freeze({ grounded: true, groundingDistanceM: null })
      : null;
  const resultCollision = pairResults.length > 0
    ? pairResults.some((pair) => pair?.collision === true)
    : null;
  const resultGrounding = vesselResults.length > 0
    ? vesselResults.some((entry) => entry?.grounded === true)
    : null;
  const globalSafety = resultCollision === null && resultGrounding === null && !state.anyCollision && !state.anyGrounding
    ? null
    : freeze({
      collision: resultCollision ?? state.anyCollision ?? false,
      grounding: resultGrounding ?? state.anyGrounding ?? false,
    });
  return freeze({
    status: runtimeOutcome?.status ?? 'idle',
    executionOutcome: manifest?.execution_outcome ?? null,
    evaluationGate: manifest?.evaluation_gate ?? null,
    reproductionStatus: manifest?.reproduction_status ?? envelope.reproduction_status ?? null,
    ship0Safety,
    globalSafety,
    resultReady: result !== null,
    artifactsCount: runtimeOutcome?.artifacts?.length ?? 0,
  });
}

function envelopeKey(envelope) {
  const playback = envelope.playback ?? {};
  return [
    envelope.run_id ?? '',
    envelope.seq ?? '',
    envelope.state ?? '',
    playback.requested_multiplier ?? '',
    playback.effective_multiplier ?? '',
    playback.realtime_limited ?? '',
    playback.scheduler_lag_ms ?? '',
    envelope.reproduction_status ?? '',
    envelope.threat_management?.snapshot?.semantic_hash
      ?? envelope.threat_management?.snapshot?.semanticHash
      ?? envelope.threat_management?.status
      ?? '',
  ].join('|');
}

/**
 * Small observable signature of the runtime outcome: the skip decision must
 * re-project when a post-terminal publish changes what the outcome section
 * would show, without deep-comparing the whole result payload.
 */
function outcomeSignature(runtimeOutcome) {
  return [
    runtimeOutcome?.status ?? 'idle',
    runtimeOutcome?.result != null ? 'result' : 'no-result',
    runtimeOutcome?.artifacts?.length ?? 0,
  ].join('|');
}

function freshState() {
  return {
    seenEventKeys: new Set(),
    timelineEvents: [],
    ship0Grounded: false,
    anyCollision: false,
    anyGrounding: false,
  };
}

export function createTelemetryProjection() {
  const listeners = new Set();
  const state = freshState();
  let current = null;
  let lastSessionId = null;
  let lastProjectedKey = null;
  let lastOutcomeSig = outcomeSignature(null);

  function publish(snapshot) {
    // Listener failures are isolated exactly like the Active Session Runtime
    // publish(): one broken view cannot corrupt projection state or starve
    // the remaining subscribers.
    for (const listener of listeners) {
      try {
        listener(snapshot);
      } catch {
        /* swallowed by design: projection avoids console output */
      }
    }
  }

  function resetHistory() {
    Object.assign(state, freshState());
  }

  function build(envelope, runtimeSnapshot) {
    const sessionId = envelope.run_id ?? null;
    const derived = [];
    const navigation = projectNavigation(envelope);
    derived.push(...recordEnvelopeEvents(envelope, sessionId ?? 'run', state));
    const risk = projectRisk(envelope);
    const combinedEvents = [...state.timelineEvents, ...derived];
    if (combinedEvents.length > SEEN_EVENT_KEY_CAP) {
      combinedEvents.splice(0, combinedEvents.length - SEEN_EVENT_KEY_CAP);
    }
    const timeline = freeze({
      events: freeze(combinedEvents),
      limitations: TIMELINE_LIMITATIONS,
    });
    state.timelineEvents = combinedEvents;
    return freeze({
      sessionId,
      seq: envelope.seq ?? null,
      simTime: envelope.sim_time ?? null,
      state: envelope.state ?? null,
      raw: envelope,
      navigation,
      sensor: projectSensor(envelope),
      risk,
      planner: projectPlanner(envelope),
      outcome: projectOutcome(runtimeSnapshot?.outcome, envelope, state),
      timeline,
    });
  }

  function project(runtimeSnapshot) {
    const envelope = runtimeSnapshot?.telemetry?.envelope ?? null;
    if (envelope === null || typeof envelope !== 'object') {
      if (current !== null) return current;
      current = emptyProjection();
      lastProjectedKey = null;
      lastOutcomeSig = outcomeSignature(null);
      publish(current);
      return current;
    }
    const key = envelopeKey(envelope);
    const outcomeSig = outcomeSignature(runtimeSnapshot?.outcome);
    if (current !== null && key === lastProjectedKey && outcomeSig === lastOutcomeSig) return current;

    const sessionId = envelope.run_id ?? null;
    if (sessionId !== null && lastSessionId !== null && sessionId !== lastSessionId) {
      resetHistory();
    }
    if (sessionId !== null) lastSessionId = sessionId;

    current = build(envelope, runtimeSnapshot);
    lastProjectedKey = key;
    lastOutcomeSig = outcomeSig;
    publish(current);
    return current;
  }

  return {
    project,
    snapshot() {
      return current ?? emptyProjection();
    },
    subscribe(listener) {
      listeners.add(listener);
      try {
        listener(current ?? emptyProjection());
      } catch {
        /* isolated exactly like publish() */
      }
      return () => listeners.delete(listener);
    },
    reset() {
      resetHistory();
      lastSessionId = null;
      lastProjectedKey = null;
      lastOutcomeSig = outcomeSignature(null);
      current = emptyProjection();
      publish(current);
    },
  };
}
