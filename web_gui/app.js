import { activeSessionRuntime, telemetryProjection } from './modules/session-runtime-instance.js?v=20260819-candidate3-projection';
import {
  createSituationDisplay,
  targetsForDisplay,
  plannerSurfaceType,
  wrapRadians,
  voCandidateColor,
  drawVelocityArrow,
  simplifiedMpcFanGeometry,
} from './modules/situation-display.js?v=20260819-c4-situation-2';

/**
 * Colav-Simulator Web GUI — app.js
 * Deployment adapter/host: owns the Situation Display instance, the planner
 * surface panel, target-edit panel, catalogs, and runtime control wiring.
 * ENC situation canvas rendering lives in modules/situation-display.js.
 */

/* ══════════════════════════════════════════════
   CONSTANTS
══════════════════════════════════════════════ */
const SAFETY_MARGIN_DEFAULT = 150;
const PERF_HISTORY_LEN      = 60;
const DCPA_SAFE  = 300;   // m – green
const DCPA_WARN  = 100;   // m – amber/red
const TCPA_SAFE  = 120;   // s
const TCPA_WARN  = 40;    // s
const VO_DECISION_FETCH_INTERVAL_MS = 200;
const METERS_PER_KNOT = 0.514444;

const SCENARIO_GROUPS = {
  rule13: { types: ['OT_ing', 'OT_en'], defaultScenario: 'overtaking' },
  rule14: { types: ['HO'], defaultScenario: 'head_on' },
  rule15: { types: ['CR_GW', 'CR_SO'], defaultScenario: 'crossing_give_way' },
  multiship: { types: ['MS'], defaultScenario: 'paper_ccta2023_multiship' },
};

const SCENARIO_TYPE_DESCRIPTIONS = {
  HO: '对遇场景',
  OT_ing: '本船追越',
  OT_en: '本船被追越',
  CR_GW: '交叉让路',
  CR_SO: '交叉直航',
  MS: '多船综合遭遇',
  SS: '单船航路规划',
};

const ENCOUNTER_LABELS = {
  head_on: 'Rule 14-HO',
  overtaking: 'Rule 13-OT',
  overtaken: 'Rule 13-OT',
  crossing_give_way: 'Rule 15-CS',
  crossing_stand_on: 'Rule 15-CS',
  clear: 'Clear',
};

const SCENARIO_LABELS = {
  aalesund_random1: 'Ålesund 随机对遇',
  boknafjorden_generation_test: 'Boknafjorden 交叉',
  crossing_give_way: '标准交叉 · 让路',
  crossing_stand_on: '标准交叉 · 直航',
  head_on: '标准对遇',
  head_on_sbmpc: 'SB-MPC 对遇验证',
  overtaken: '标准被追越',
  overtaking: '标准追越',
  paper_ccta2023_head_on: '论文复现 · 对遇',
  paper_ccta2023_multiship: '论文复现 · 四船',
  romsdal_busy_water_16: 'Romsdal 多船可配置',
  rl_scenario: 'RL',
  rl_scenario_smaller: 'RL',
  rlmpc_scenario: 'RLMPC',
  rlmpc_scenario_ms_channel: 'RLMPC',
  rlmpc_scenario_ms_channel_vimmjipda: 'RLMPC + VIMMJIPDA',
  rogaland_random_rl: 'RL Rogaland',
  rrt_test: 'RRT*',
  'saved/rlmpc_scenario_ms_channel/rlmpc_scenario_ms_channel_ep001_27072026_040243': 'RLMPC 回放',
};

const ENC_CHARTS = {
  romsdal: { label: 'Romsdal' },
  rogaland: { label: 'Rogaland' },
};

let scenarioCatalog = [];
let capabilityCatalog = null;
let ruleCatalog = [];
let solveTimeline = [];
let lastDisplayedSolveId = null;
let lastRuntimeState = 'CREATED';
let lastSolveSimTime = null;

/* ══════════════════════════════════════════════
   ADAPTER STATE (view/ENC/layer state lives in the Display module)
══════════════════════════════════════════════ */
const perfHistory = [];
let currentData = null;
let logCount    = 0;
let renderedTimelineEvents = 0;
let deploymentRuntimeSnapshot = activeSessionRuntime.snapshot();
let handledTelemetryRevision = 0;
let handledOutcomeKey = '';
let reportedFailureSessionId = null;
let voDecisionSpace = null;
let voDecisionSpaceKey = null;
let voDecisionSpaceRequestKey = null;
let voDecisionSpaceAttemptedKey = null;
let voDecisionSpaceController = null;
let voDecisionSpacePending = null;
let voDecisionSpaceRetryTimer = null;
let lastVODecisionRequestAt = 0;
let lastVORenderKey = null;
let voRenderGeometry = null;
let selectedTargetId = null;
let targetEditorKey = null;
let busyWaterDocument = null;
let busyWaterSeed = 20250731;
let busyWaterMix = { crossing: 0.6, head_on: 0.2, overtaking: 0.2 };

function currentRunId() {
  return deploymentRuntimeSnapshot.session?.session_id || null;
}

/* ══════════════════════════════════════════════
   SITUATION DISPLAY (adapter wiring only)
══════════════════════════════════════════════ */
function plannerResponseRange() {
  const planner = telemetryProjection.snapshot().planner;
  const algorithmId = planner.algorithmId;
  const constraints = planner.display?.constraints || {};
  if (algorithmId === 'sbmpc') {
    const configuredRange = Number(constraints.activation_distance_m);
    const distanceM = Number.isFinite(configuredRange) && configuredRange > 0
      ? configuredRange
      : 1000;
    return {
      distanceM,
      label: `避碰响应圈（${(distanceM / 1000).toFixed(1)} km）`,
      threatActivation: true,
    };
  }
  if (['potocnik_simplified_mpc', 'potocnik_colreg_fan_mpc'].includes(algorithmId)) {
    const distanceM = Number(constraints.planning_zone?.distance_m);
    if (Number.isFinite(distanceM) && distanceM > 0) {
      return {
        distanceM,
        label: `论文 COLREG 区（${(distanceM / 1852).toFixed(1)} nm）`,
        threatActivation: false,
      };
    }
  }
  return null;
}

function setEncStatus(state) {
  const badge = document.getElementById('encStatusBadge');
  if (!badge) return;
  const labels = { loading: '加载中', ready: '已加载', error: '加载失败' };
  badge.textContent = labels[state] || labels.loading;
  badge.classList.toggle('ready', state === 'ready');
  badge.classList.toggle('error', state === 'error');
}

const situationDisplay = createSituationDisplay({
  canvas: document.getElementById('simCanvas'),
  wrapper: document.getElementById('canvasWrapper'),
  getResponseRange: () => plannerResponseRange(),
  getScenarioId: () => document.getElementById('scenarioSelect')?.value || null,
  getPlannerSurface: () => {
    const type = plannerSurfaceType(currentDiagnosticPlanner());
    if (type === 'vo') {
      const sessionId = currentRunId();
      const snapshot = voDecisionSpaceKey?.startsWith(`${sessionId}:`) ? voDecisionSpace : null;
      return snapshot ? { type: 'vo', vo: snapshot } : null;
    }
    if (type === 'fan') return { type: 'fan', fan: currentDiagnosticPlanner() };
    return null;
  },
  onEncStatus: setEncStatus,
  onLog: pushLog,
  onScaleLabel: text => {
    const label = document.getElementById('scaleBarLabel');
    if (label) label.textContent = text;
  },
  onLayerStateChange: syncLayerControls,
  onSelectionChange: target => {
    selectedTargetId = target?.id ?? null;
    updateTargetDetails(target || null, currentData).catch(error => {
      document.getElementById('busyWaterStatus').textContent = error.message;
    });
  },
});

/* ══════════════════════════════════════════════
   OPENBRIDGE THEME (C5 #4 — full prototype behavior, P:2849-2870 / P:3179-3204)
   Palette chrome only: html dataset, top-bar dimming state, persistence, and
   the situation-display palette re-read. No validation/runtime truth here.
══════════════════════════════════════════════ */
const OPENBRIDGE_COMPONENT_BASE = 'https://cdn.jsdelivr.net/npm/@oicl/openbridge-webcomponents@1.0.1/dist';
const PALETTE_NAMES = { day: true, dusk: true, night: true, bright: true };
const mainTopBar = document.getElementById('mainTopBar');
const brillianceMenu = document.getElementById('brillianceMenu');

// Same pinned CDN base config-shell.js already uses for icons (P:11); failure
// degrades like every other best-effort OpenBridge piece (menu stays inert).
import(`${OPENBRIDGE_COMPONENT_BASE}/components/brilliance-menu/brilliance-menu.js/+esm`).catch(() => {});

function applyPalette(palette, persist = true) {
  const nextPalette = PALETTE_NAMES[palette] ? palette : 'day';
  document.documentElement.dataset.obcTheme = nextPalette;
  brillianceMenu.palette = nextPalette;
  mainTopBar.dimmingButtonActivated = nextPalette === 'dusk' || nextPalette === 'night';
  if (persist) {
    try { localStorage.setItem('colav-openbridge-palette', nextPalette); } catch (error) { /* storage may be unavailable */ }
  }
  situationDisplay.refreshPalette();
  return nextPalette;
}

// Compact palette-only menu (P:2864-2869).
brillianceMenu.showBrightness = false;
brillianceMenu.showPalette = true;

mainTopBar.addEventListener('dimming-button-clicked', (event) => {
  event.stopPropagation();
  brillianceMenu.hidden = !brillianceMenu.hidden;
});
brillianceMenu.addEventListener('palette-changed', (event) => {
  applyPalette(event.detail?.value || brillianceMenu.palette);
});
brillianceMenu.addEventListener('click', (event) => event.stopPropagation());

// Outside-click and Escape close the menu (P:3293 pattern, adapted: production
// settingsBtn has no popover, so there is no system menu to close).
document.addEventListener('click', (event) => {
  if (!brillianceMenu.hidden && !brillianceMenu.contains(event.target) && !event.composedPath().includes(mainTopBar)) {
    brillianceMenu.hidden = true;
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  if (brillianceMenu.hidden) return;
  brillianceMenu.hidden = true;
  const dimmingButton = mainTopBar.shadowRoot?.querySelector('.dimming-button');
  (dimmingButton?.shadowRoot?.querySelector('button') || dimmingButton)?.focus();
});

let initialPalette = 'day';
try {
  const savedPalette = localStorage.getItem('colav-openbridge-palette');
  if (PALETTE_NAMES[savedPalette]) initialPalette = savedPalette;
} catch (error) { /* storage may be unavailable */ }
applyPalette(initialPalette, false);

function syncLayerControls(state) {
  for (const [id, layer] of Object.entries(state)) {
    const input = document.querySelector(`[data-layer="${id}"]`);
    const status = document.querySelector(`[data-layer-state="${id}"]`);
    if (input) {
      const wasDisabled = input.disabled;
      input.disabled = !layer.available;
      if (!layer.available) input.checked = false;
      if (layer.available && wasDisabled) input.checked = true;
      if (input.checked !== layer.userVisible) situationDisplay.setLayerVisible(id, input.checked);
    }
    if (status) {
      status.textContent = layer.available ? '可用' : '数据未提供';
      status.classList.toggle('available', layer.available);
    }
  }
  updateLegendVisibility();
}

function updateLegendVisibility(state = situationDisplay.getLayerState()) {
  document.querySelectorAll('[data-legend-layer]').forEach(item => {
    item.hidden = state[item.dataset.legendLayer]?.visible === false;
  });
  document.querySelectorAll('[data-legend-group]').forEach(group => {
    group.hidden = !group.querySelector('[data-legend-layer]:not([hidden])');
  });
}

document.getElementById('zoomIn').addEventListener('click', () => situationDisplay.zoomIn());
document.getElementById('zoomOut').addEventListener('click', () => situationDisplay.zoomOut());
document.getElementById('zoomReset').addEventListener('click', () => situationDisplay.fitView());
document.getElementById('toggleENC').addEventListener('click', function () {
  const visible = !situationDisplay.isEncVisible();
  situationDisplay.setEncVisible(visible);
  this.classList.toggle('enc-on', visible);
  this.setAttribute('aria-pressed', String(visible));
});
document.querySelectorAll('[data-layer]').forEach(input => {
  input.addEventListener('change', () => {
    situationDisplay.setLayerVisible(input.dataset.layer, input.checked);
    updateLegendVisibility();
  });
});

function startRoutePointPick(mode) {
  situationDisplay.setClickMode({
    id: 'route-pick',
    onPick: async point => {
      const suffix = mode === 'start' ? '1' : '2';
      try {
        const coordinate = await utmToWgs84(point.north, point.east);
        document.getElementById(`targetRouteLat${suffix}`).value = coordinate.latitude.toFixed(6);
        document.getElementById(`targetRouteLon${suffix}`).value = coordinate.longitude.toFixed(6);
      } finally {
        situationDisplay.setClickMode(null);
      }
    },
  });
}

async function utmToWgs84(north, east) {
  const params = new URLSearchParams({ north: String(north), east: String(east), utm_zone: '33' });
  return apiRequest(`/api/coordinates/to-wgs84?${params}`);
}

async function wgs84ToUtm(latitude, longitude) {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    utm_zone: '33',
  });
  return apiRequest(`/api/coordinates/to-utm?${params}`);
}

function renderBusyTargetList() {
  const list = document.getElementById('busyTargetList');
  list.replaceChildren();
  for (const ship of busyWaterDocument?.ship_list?.slice(1) || []) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.targetId = String(ship.id);
    button.textContent = `TS${ship.id}`;
    button.setAttribute('role', 'option');
    button.classList.toggle('selected', String(ship.id) === String(selectedTargetId));
    button.setAttribute('aria-selected', String(ship.id) === String(selectedTargetId));
    list.appendChild(button);
  }
}

function colregsEditorValue(role) {
  if (role === 'head_on') return 'HO';
  if (String(role).startsWith('crossing_')) return 'CS';
  if (role === 'overtaking' || role === 'overtaken') return 'OT';
  return 'UNKNOWN';
}

function encounterRoleFromEditor(value) {
  return { HO: 'head_on', CS: 'crossing_give_way', OT: 'overtaking', UNKNOWN: 'unknown' }[value];
}

async function updateTargetDetails(target, data) {
  const form = document.getElementById('targetEditForm');
  if (!target) {
    form.hidden = true;
    targetEditorKey = null;
    renderBusyTargetList();
    return;
  }
  const ship = busyWaterDocument?.ship_list?.find(item => String(item.id) === String(target.id));
  const editable = Boolean(ship && data?.state !== 'RUNNING');
  form.hidden = !editable;
  if (editable) {
    const key = JSON.stringify([ship.id, ship.csog_state[2], ship.waypoints, ship.encounter_role]);
    if (targetEditorKey !== key) {
      targetEditorKey = key;
      let start;
      let end;
      try {
        [start, end] = await Promise.all([
          utmToWgs84(ship.waypoints[0][0], ship.waypoints[1][0]),
          utmToWgs84(ship.waypoints[0][1], ship.waypoints[1][1]),
        ]);
      } catch (error) {
        targetEditorKey = null;
        throw error;
      }
      if (String(selectedTargetId) !== String(ship.id)) return;
      document.getElementById('targetIdentifier').value = `TS${ship.id}`;
      document.getElementById('targetSpeed').value = (Number(ship.csog_state[2]) / METERS_PER_KNOT).toFixed(1);
      document.getElementById('targetRouteLat1').value = start.latitude.toFixed(6);
      document.getElementById('targetRouteLon1').value = start.longitude.toFixed(6);
      document.getElementById('targetRouteLat2').value = end.latitude.toFixed(6);
      document.getElementById('targetRouteLon2').value = end.longitude.toFixed(6);
      document.getElementById('targetColregs').value = colregsEditorValue(ship.encounter_role);
    }
  }
  renderBusyTargetList();
}

function selectedBusyWaterShip() {
  return busyWaterDocument?.ship_list?.find(item => String(item.id) === String(selectedTargetId));
}

/* ══════════════════════════════════════════════
   UI TELEMETRY UPDATE
══════════════════════════════════════════════ */
function updateUI(proj) {
  const data = proj.raw;
  const navigation = proj.navigation;
  const os = data?.os;
  if (selectedTargetId !== null) {
    const target = targetsForDisplay(data).find(item => String(item.id) === String(selectedTargetId));
    updateTargetDetails(target || null, data).catch(error => {
      document.getElementById('busyWaterStatus').textContent = error.message;
    });
  }

  const previousRuntimeState = lastRuntimeState;
  if (proj.state === 'RUNNING' && previousRuntimeState !== 'RUNNING') {
    setRuntimePanelsExpanded(true);
  }
  lastRuntimeState = proj.state || lastRuntimeState;

  // Response-range layer label (P1 fix-round): the module only knows the
  // range object injected via getResponseRange; the layer-control and legend
  // labels are host-side DOM and refreshed here, per telemetry frame, exactly
  // as the pre-C4 updateLayerAvailability pass did.
  const responseRangeLabel = plannerResponseRange()?.label || '规划/响应范围';
  setText('response-range-control-label', responseRangeLabel);
  setText('response-range-legend-label', responseRangeLabel);

  // Header time
  setText('val-sim-time', `${(navigation?.simTime ?? 0).toFixed(1)} s`);
  setText('val-run-state', proj.state || 'CREATED');
  setText('val-reproduction', proj.outcome.reproductionStatus || 'not evaluated');
  syncPlaybackStatus(proj.raw?.playback, proj.state === 'RUNNING');

  // Primary encounter, DCPA / TCPA
  const primary = proj.risk.primary;
  setText('val-primary-target', primary?.targetLabel || '无目标');
  const dcpa = proj.risk.dcpaM;
  const tcpa = proj.risk.tcpaS;
  const dcpaEl = document.getElementById('val-dcpa');
  dcpaEl.textContent = dcpa === null ? '--- m' : `${dcpa.toFixed(1)} m`;
  setRiskClass(dcpaEl, dcpa, DCPA_SAFE, DCPA_WARN, true);
  const dcpaPct = dcpa === null ? 0 : Math.max(0, Math.min(100, (1 - dcpa / (DCPA_SAFE * 2)) * 100));
  setRiskBar('dcpaBar', dcpaPct,
    dcpa === null ? 'safe' : dcpa > DCPA_SAFE ? 'safe' : dcpa > DCPA_WARN ? 'warn' : 'danger');

  const tcpaEl = document.getElementById('val-tcpa');
  tcpaEl.textContent = tcpa === null ? '--- s' : `${tcpa.toFixed(1)} s`;
  setRiskClass(tcpaEl, tcpa, TCPA_SAFE, TCPA_WARN, true);
  const tcpaPct = tcpa === null ? 0 : Math.max(0, Math.min(100, (1 - tcpa / (TCPA_SAFE * 2)) * 100));
  setRiskBar('tcpaBar', tcpaPct,
    tcpa === null ? 'safe' : tcpa > TCPA_SAFE ? 'safe' : tcpa > TCPA_WARN ? 'warn' : 'danger');

  updateColregsBadge(proj.risk.colregs);

  const primaryDistance = primary?.distanceM ?? null;
  setText('val-dist', primaryDistance === null ? '--- m' : `${primaryDistance.toFixed(1)} m`);

  // OS telemetry
  setText('val-os-latitude', formatCoordinate(navigation?.latitude, 'N', 'S'));
  setText('val-os-longitude', formatCoordinate(navigation?.longitude, 'E', 'W'));
  setText('val-os-sog', Number.isFinite(navigation?.sog) ? `${navigation.sog.toFixed(2)} m/s` : '-- m/s');
  setText('val-os-cog', formatCourse(navigation?.cog));
  setText('val-os-heading', formatCourse(navigation?.psi));
  setText('val-os-yaw', `${(os?.r || 0).toFixed(1)} rad/s`);
  updatePlannerPanel(proj);

  // Performance
  const stepMs = Number.isFinite(navigation?.stepTimeMs) ? navigation.stepTimeMs : 0;
  setText('val-step-time', `${stepMs.toFixed(2)} ms`);
  perfHistory.push(stepMs);
  if (perfHistory.length > PERF_HISTORY_LEN) perfHistory.shift();
  const avg = perfHistory.reduce((a, b) => a + b, 0) / perfHistory.length;
  setText('val-avg-time', `${avg.toFixed(2)} ms`);
  drawPerfChart();

}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function syncPlaybackStatus(playback, running = false) {
  if (!playback) return;
  const requested = Number(playback.requested_multiplier);
  const effective = typeof playback.effective_multiplier === 'number'
    ? playback.effective_multiplier
    : NaN;
  document.querySelectorAll('.speed-preset').forEach(button => {
    button.classList.toggle('active', Number(button.dataset.speed) === requested);
  });
  const status = document.getElementById('speedStatus');
  if (!status) return;
  status.classList.toggle('limited', Boolean(playback.realtime_limited));
  if (!running) {
    status.textContent = Number.isFinite(effective) ? `最近 ${effective.toFixed(1)}×` : '实际 --';
  } else if (!Number.isFinite(effective)) {
    status.textContent = '测量中';
  } else {
    status.textContent = playback.realtime_limited
      ? `受限 ${effective.toFixed(1)}×`
      : `实际 ${effective.toFixed(1)}×`;
  }
}

function formatCoordinate(value, positiveHemisphere, negativeHemisphere) {
  if (!Number.isFinite(value)) return '--';
  const hemisphere = value >= 0 ? positiveHemisphere : negativeHemisphere;
  return `${Math.abs(value).toFixed(4)}° ${hemisphere}`;
}

function formatCourse(value) {
  if (!Number.isFinite(value)) return '--°';
  const degrees = ((value * 180 / Math.PI) % 360 + 360) % 360;
  return `${degrees.toFixed(1)}°`;
}

function setRiskClass(el, value, safe, warn, invert) {
  el.classList.remove('safe', 'warn', 'danger');
  if (!Number.isFinite(value)) return;
  if (invert) {
    if (value > safe) el.classList.add('safe');
    else if (value > warn) el.classList.add('warn');
    else el.classList.add('danger');
  }
}

function setRiskBar(id, pct, level) {
  const bar = document.getElementById(id);
  if (!bar) return;
  bar.style.width      = `${pct}%`;
  bar.style.background = level === 'safe' ? 'var(--risk-safe)'
                       : level === 'warn' ? 'var(--risk-warn)'
                                          : 'var(--risk-danger)';
}

function updateColregsBadge(rule) {
  const badge     = document.getElementById('val-colregs');
  const label = ENCOUNTER_LABELS[rule] || rule || 'Clear';
  badge.textContent = label;
  badge.className   = 'colregs-badge';
  if      (rule === 'head_on')          badge.classList.add('rule-14');
  else if (rule === 'crossing_give_way') badge.classList.add('rule-15-giveway');
  else if (rule === 'crossing_stand_on') badge.classList.add('rule-15-standon');
  else if (rule === 'overtaking')        badge.classList.add('rule-13');
  else                                   badge.classList.add('clear');
}

function updatePlannerPanel(proj) {
  const state = proj.planner;
  const diagnosticPlanner = state.display || {};
  const details = diagnosticPlanner.algorithm_details || {};
  syncPlannerSurfaceMode(diagnosticPlanner);
  const solveId = Number(state.solveId || 0);
  const realSolve = state.phase === 'SOLVE';
  const mode = document.getElementById('val-solver-executed');
  mode.textContent = realSolve ? 'SOLVE' : 'HOLD';
  mode.classList.toggle('solve', realSolve);
  mode.classList.toggle('hold', !realSolve);

  setText('val-solve-id', `#${solveId}`);
  const solverSuccessful = state.feasible !== false
    && ['SUCCESS', 'TIMEOUT_FEASIBLE'].includes(state.status || 'SUCCESS');
  setText('val-solver-state', solverSuccessful ? '成功' : '失败');

  const horizonLength = state.horizonLength;
  const horizonIntervals = details.control_intervals ?? horizonLength;
  const gridShape = Array.isArray(details.grid_shape) ? details.grid_shape : [];
  const horizonTime = diagnosticPlanner.algorithm_id === 'vo' && gridShape.length === 2
    ? `决策网格 ${gridShape[0]}×${gridShape[1]}`
    : horizonLength && Number.isFinite(diagnosticPlanner.horizon_dt_s)
      ? `${horizonIntervals} × ${diagnosticPlanner.horizon_dt_s.toFixed(1)}s`
      : `${horizonLength} points`;
  setText('val-planner-horizon', horizonTime);

  const course = state.appliedCourseRefRad;
  const speed = state.appliedSpeedRefMps;
  setText('val-command-course', Number.isFinite(course) ? `${(course * 180 / Math.PI).toFixed(1)}°` : '--°');
  setText('val-command-speed', Number.isFinite(speed) ? `${speed.toFixed(2)} m/s` : '-- m/s');

  const solvedNow = state.latestSolve?.solver_executed === true || state.current?.solver_executed === true;
  if ((state.latestSolve?.solver_executed && Number(state.latestSolve.solve_id || 0) !== lastDisplayedSolveId)
    || solvedNow) {
    lastSolveSimTime = Number(diagnosticPlanner.sim_time || proj.simTime || 0);
  }
  const prediction = proj.raw?.plans?.prediction_horizon || [];
  const predictionIndex = Number.isFinite(diagnosticPlanner.horizon_dt_s) && lastSolveSimTime !== null
    ? Math.min(prediction.length - 1, Math.max(0, Math.round(
      (Number(proj.simTime || 0) - lastSolveSimTime) / diagnosticPlanner.horizon_dt_s,
    )))
    : 0;
  const predictedExecution = prediction[predictionIndex];
  const executionError = predictedExecution && proj.raw?.os
    ? Math.hypot(predictedExecution[0] - proj.raw.os.x, predictedExecution[1] - proj.raw.os.y)
    : null;
  setText('val-prediction-error', Number.isFinite(executionError) ? `${executionError.toFixed(2)} m` : '-- m');
  drawPlannerSurface(diagnosticPlanner);
  ensureVODecisionSpace(diagnosticPlanner);
  const configuredSolvePeriod = Number(state.solvePeriodS);
  setText(
    'val-solve-period',
    Number.isFinite(configuredSolvePeriod)
      ? `${configuredSolvePeriod.toFixed(1)} s`
      : '按算法触发',
  );

  const timelineTrace = solvedNow ? state.display : null;
  if (timelineTrace && Number(timelineTrace.solve_id) !== lastDisplayedSolveId) {
    lastDisplayedSolveId = Number(timelineTrace.solve_id);
    solveTimeline.push({
      solveId: lastDisplayedSolveId,
      simTime: Number(timelineTrace.sim_time || proj.simTime || 0),
      status: timelineTrace.status || 'SUCCESS',
      objective: Number(timelineTrace.objective ?? timelineTrace.algorithm_details?.objective),
    });
    solveTimeline = solveTimeline.slice(-60);
    renderSolveTimeline();
  }
}

function drawPlannerSurface(planner) {
  const canvas = document.getElementById('plannerSurface');
  const surface = canvas.getContext('2d');
  const algorithmId = planner.algorithm_id;
  const details = planner.algorithm_details || {};
  const isVO = algorithmId === 'vo';
  const isMidMPC = algorithmId === 'mid_mpc_ipopt';
  const isSimplifiedMPC = ['potocnik_simplified_mpc', 'potocnik_colreg_fan_mpc'].includes(algorithmId);
  const matrix = details.candidate_costs;
  const selectionMatrix = matrix;
  const label = algorithmId === 'vo'
    ? '速度决策空间'
    : isMidMPC
      ? 'Mid-MPC · IPOPT 优化轨迹'
      : algorithmId === 'sbmpc'
      ? 'SB-MPC 候选控制代价'
      : isSimplifiedMPC
        ? (algorithmId === 'potocnik_colreg_fan_mpc'
          ? 'Fan-MPC · 规则与安全筛选'
          : '简化 MPC · 扇形轨迹筛选')
        : '名义 LOS 引导';
  const surfaceExplanation = document.getElementById('val-surface-explanation');
  const surfaceMeta = document.getElementById('val-surface-meta');
  if (surfaceExplanation) surfaceExplanation.hidden = !isVO;
  if (surfaceMeta) surfaceMeta.hidden = isVO;
  setText('val-surface-label', label);
  setText('val-surface-explanation', '');
  const lifecycle = details.lifecycle || {};
  const lifecycleTargets = Array.isArray(lifecycle.targets) ? lifecycle.targets : [];
  const lifecycleSummary = lifecycleTargets
    .map(target => `TS${target.target_id} ${target.risk}/${target.commitment}`)
    .join(' · ');
  const profileShort = typeof lifecycle.profile_hash === 'string'
    ? lifecycle.profile_hash.slice(0, 8)
    : '--';
  setText(
    'val-surface-meta',
    isMidMPC ? `Planner L0 · ${lifecycleSummary || 'CLEAR'} · profile ${profileShort}` : '',
  );
  setText('label-best-cost', isVO ? '最小总 Cost' : '最优 Cost');
  setText('label-best-course-offset', '航向偏移');
  setText('label-best-speed-scale', isVO ? '候选航速' : '速度系数');
  const selectedHeading = Number(details.selected_heading_rad);
  const ownshipHeading = Number(voDecisionSpace?.ownship_heading_rad ?? currentData?.os?.psi);
  const selectedOffset = Number.isFinite(selectedHeading) && Number.isFinite(ownshipHeading)
    ? Math.atan2(Math.sin(selectedHeading - ownshipHeading), Math.cos(selectedHeading - ownshipHeading))
    : NaN;
  setText(
    'val-best-cost',
    isVO || isMidMPC ? formatCost(Number(details.objective ?? planner.objective)) : '--',
  );
  setText(
    'val-best-course-offset',
    isVO && Number.isFinite(selectedOffset) ? `${(selectedOffset * 180 / Math.PI).toFixed(1)}°` : '--°',
  );
  setText(
    'val-best-speed-scale',
    isVO && Number.isFinite(details.selected_speed_mps)
      ? `${Number(details.selected_speed_mps).toFixed(2)} m/s`
      : isVO ? '-- m/s' : '--',
  );
  const objectiveHistoryWrap = document.getElementById('objectiveHistoryWrap');
  if (objectiveHistoryWrap) objectiveHistoryWrap.hidden = !['sbmpc', 'mid_mpc_ipopt'].includes(algorithmId);
  const voLegend = document.getElementById('voSurfaceLegend');
  if (voLegend) voLegend.hidden = !isVO;
  updatePlannerSurfaceAttachControl(plannerSurfaceType(planner), Number(planner.solve_id));
  if (isVO) {
    drawVODecisionSpace(surface, canvas, planner, details);
    return;
  }
  surface.clearRect(0, 0, canvas.width, canvas.height);
  surface.fillStyle = '#0d1211';
  surface.fillRect(0, 0, canvas.width, canvas.height);
  if (isSimplifiedMPC) {
    drawSimplifiedMpcFan(surface, canvas, planner, details);
    return;
  }
  if (!Array.isArray(matrix) || !matrix.length || !Array.isArray(matrix[0])) {
    surface.fillStyle = '#65736f';
    surface.font = '11px SFMono-Regular, monospace';
    surface.fillText(isMidMPC ? 'IPOPT 轨迹见海图' : '暂无候选控制代价', 12, 78);
    return;
  }
  const values = matrix.flat().filter(Number.isFinite);
  const low = values.length ? Math.min(...values) : 0;
  const high = values.length ? Math.max(...values) : 1;
  const rows = matrix.length;
  const columns = Math.max(...matrix.map(row => row.length));
  const courseOffsets = Array.isArray(isVO ? details.heading_offsets_rad : details.course_offsets_rad)
    ? (isVO ? details.heading_offsets_rad : details.course_offsets_rad)
    : [];
  const speedValues = Array.isArray(isVO ? details.speed_offsets_mps : details.speed_scales)
    ? (isVO ? details.speed_offsets_mps : details.speed_scales)
    : [];
  const plot = { left: 42, top: 10, right: canvas.width - 10, bottom: canvas.height - 34 };
  const cellWidth = (plot.right - plot.left) / columns;
  const cellHeight = (plot.bottom - plot.top) / rows;
  let best = { value: Infinity, row: -1, column: -1 };
  matrix.forEach((row, rowIndex) => row.forEach((value, columnIndex) => {
    const normalized = Number.isFinite(value) && high > low ? (value - low) / (high - low) : 0;
    const red = Math.round(70 + normalized * 175);
    const green = Math.round(195 - normalized * 135);
    surface.fillStyle = Number.isFinite(value) ? `rgb(${red},${green},92)` : '#26302d';
    surface.fillRect(
      plot.left + columnIndex * cellWidth,
      plot.top + rowIndex * cellHeight,
      Math.max(1, cellWidth - 0.5),
      Math.max(1, cellHeight - 0.5),
    );
  }));
  if (Array.isArray(selectionMatrix)) {
    selectionMatrix.forEach((row, rowIndex) => {
      if (!Array.isArray(row)) return;
      row.forEach((value, columnIndex) => {
        if (Number.isFinite(value) && value < best.value) {
          best = { value, row: rowIndex, column: columnIndex };
        }
      });
    });
  }
  if (best.row >= 0) {
    surface.strokeStyle = '#FFFFFF';
    surface.lineWidth = 2;
    surface.strokeRect(
      plot.left + best.column * cellWidth + 1,
      plot.top + best.row * cellHeight + 1,
      Math.max(1, cellWidth - 2),
      Math.max(1, cellHeight - 2),
    );
  }

  surface.fillStyle = '#82918c';
  surface.font = '9px SFMono-Regular, monospace';
  surface.textAlign = 'right';
  axisTickIndices(rows, plot.bottom - plot.top, 38).forEach(rowIndex => {
    const value = Number(isVO ? speedValues[rowIndex] : courseOffsets[rowIndex]);
    const text = Number.isFinite(value)
      ? (isVO ? `${value.toFixed(1)}` : `${Math.round(value * 180 / Math.PI)}°`)
      : String(rowIndex + 1);
    surface.fillText(text, plot.left - 5, plot.top + (rowIndex + 0.7) * cellHeight);
  });
  surface.save();
  surface.translate(9, (plot.top + plot.bottom) / 2);
  surface.rotate(-Math.PI / 2);
  surface.textAlign = 'center';
  surface.fillText(isVO ? '候选航速 m/s' : '航向偏移', 0, 0);
  surface.restore();

  surface.textAlign = 'center';
  axisTickIndices(columns, plot.right - plot.left, 46).forEach(columnIndex => {
    const value = Number(isVO ? courseOffsets[columnIndex] : speedValues[columnIndex]);
    const text = Number.isFinite(value)
      ? (isVO ? `${Math.round(value * 180 / Math.PI)}°` : value.toFixed(1))
      : String(columnIndex + 1);
    surface.fillText(text, plot.left + (columnIndex + 0.5) * cellWidth, plot.bottom + 12);
  });
  surface.fillText(isVO ? '航向偏移' : '速度系数', (plot.left + plot.right) / 2, canvas.height - 4);
  if (isVO) {
    const courseDegrees = courseOffsets.map(value => Number(value) * 180 / Math.PI).filter(Number.isFinite);
    const candidateSpeeds = speedValues.map(Number).filter(Number.isFinite);
    if (courseDegrees.length && candidateSpeeds.length) {
      const courseStep = courseDegrees.length > 1 ? Math.abs(courseDegrees[1] - courseDegrees[0]) : 0;
      const speedStep = candidateSpeeds.length > 1 ? Math.abs(candidateSpeeds[1] - candidateSpeeds[0]) : 0;
      setText(
        'val-surface-meta',
        `横轴 航向偏移 ${formatAxisNumber(courseDegrees[0])}°–${formatAxisNumber(courseDegrees.at(-1))}°`
          + `（${formatAxisNumber(courseStep)}°/格） · 纵轴 候选航速 `
          + `${formatAxisNumber(candidateSpeeds[0])}–${formatAxisNumber(candidateSpeeds.at(-1))} m/s`
          + `（${formatAxisNumber(speedStep)} m/s/格）`,
      );
    }
  }

  if (best.row >= 0) {
    const courseRadians = Number(courseOffsets[isVO ? best.column : best.row]);
    const courseDegrees = Number.isFinite(courseRadians) ? courseRadians * 180 / Math.PI : NaN;
    const speedValue = Number(speedValues[isVO ? best.row : best.column]);
    const courseText = Number.isFinite(courseDegrees) ? `${courseDegrees.toFixed(0)}°` : `行 ${best.row + 1}`;
    const speedText = Number.isFinite(speedValue)
      ? (isVO ? `${speedValue.toFixed(1)} m/s` : speedValue.toFixed(1))
      : `列 ${best.column + 1}`;
    setText('val-best-cost', formatCost(best.value));
    setText('val-best-course-offset', courseText);
    setText('val-best-speed-scale', speedText);
  }
}

function ensureVODecisionSpace(planner) {
  const sessionId = currentRunId();
  if (planner.algorithm_id !== 'vo' || !sessionId) return;
  const card = document.getElementById('cardPlanner');
  const solveId = Number(planner.solve_id);
  if ((card?.classList.contains('collapsed') && !situationDisplay.isPlannerSurfaceAttached())
    || !Number.isInteger(solveId) || solveId < 1) return;
  const requestKey = `${sessionId}:${solveId}`;
  if (voDecisionSpaceKey === requestKey || voDecisionSpaceAttemptedKey === requestKey) return;
  voDecisionSpacePending = {
    sessionId,
    solveId,
    planner,
  };
  requestPendingVODecisionSpace();
}

function requestPendingVODecisionSpace() {
  if (voDecisionSpaceController || !voDecisionSpacePending) return;
  const pending = voDecisionSpacePending;
  if (pending.sessionId !== currentRunId()) {
    voDecisionSpacePending = null;
    return;
  }
  const requestKey = `${pending.sessionId}:${pending.solveId}`;
  if (voDecisionSpaceKey === requestKey) {
    voDecisionSpacePending = null;
    return;
  }
  const requestTime = performance.now();
  const retryDelay = VO_DECISION_FETCH_INTERVAL_MS - (requestTime - lastVODecisionRequestAt);
  if (retryDelay > 0) {
    if (voDecisionSpaceRetryTimer === null) {
      voDecisionSpaceRetryTimer = window.setTimeout(() => {
        voDecisionSpaceRetryTimer = null;
        requestPendingVODecisionSpace();
      }, retryDelay);
    }
    return;
  }

  voDecisionSpacePending = null;
  lastVODecisionRequestAt = requestTime;
  const controller = new AbortController();
  voDecisionSpaceController = controller;
  voDecisionSpaceRequestKey = requestKey;
  fetch(
    `/api/sessions/${encodeURIComponent(pending.sessionId)}/planner/decision-space?solve_id=${pending.solveId}`,
    { signal: controller.signal },
  ).then(async response => {
    if (response.status === 204 || response.status === 409) {
      voDecisionSpaceAttemptedKey = requestKey;
      return null;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }).then(snapshot => {
    if (!snapshot || controller.signal.aborted || pending.sessionId !== currentRunId()) return;
    voDecisionSpace = snapshot;
    voDecisionSpaceKey = requestKey;
    voDecisionSpaceAttemptedKey = requestKey;
    lastVORenderKey = null;
    drawPlannerSurface(pending.planner);
    updatePlannerSurfaceAttachControl('vo', pending.solveId);
    if (situationDisplay.isPlannerSurfaceAttached()) situationDisplay.rerender();
  }).catch(error => {
    if (error.name !== 'AbortError') {
      setText('val-surface-explanation', '决策空间暂不可用');
    }
  }).finally(() => {
    if (voDecisionSpaceController === controller) voDecisionSpaceController = null;
    if (voDecisionSpaceRequestKey === requestKey) voDecisionSpaceRequestKey = null;
    requestPendingVODecisionSpace();
  });
}

function drawVODecisionSpace(surface, canvas, planner, details) {
  const solveId = Number(planner.solve_id);
  const sessionId = currentRunId();
  const expectedKey = `${sessionId}:${solveId}`;
  const snapshot = voDecisionSpaceKey?.startsWith(`${sessionId}:`) ? voDecisionSpace : null;
  const renderKey = snapshot
    ? `${voDecisionSpaceKey}:${canvas.clientWidth}:${canvas.clientHeight}`
    : `waiting:${expectedKey}`;
  if (lastVORenderKey === renderKey) return;
  lastVORenderKey = renderKey;

  surface.clearRect(0, 0, canvas.width, canvas.height);
  surface.fillStyle = '#0d1211';
  surface.fillRect(0, 0, canvas.width, canvas.height);
  if (!snapshot) {
    surface.fillStyle = '#65736f';
    surface.font = '11px SFMono-Regular, monospace';
    surface.fillText(solveId > 0 ? '加载 VO 决策速度空间…' : '等待 VO 求解', 12, 78);
    setText('val-surface-explanation', '展开后按真实求解编号加载，不进入遥测帧');
    setText('val-surface-meta', '');
    voRenderGeometry = null;
    return;
  }

  const speeds = snapshot.speed_candidates_mps || [];
  const headings = snapshot.heading_candidates_rad || [];
  const bits = snapshot.candidate_state_bits || [];
  const costs = snapshot.total_costs || [];
  const ttc = snapshot.minimum_ttc_s || [];
  const [rows, columns] = snapshot.shape || [];
  if (rows !== speeds.length || columns !== headings.length || bits.length !== rows * columns) {
    surface.fillStyle = '#e35d68';
    surface.font = '11px SFMono-Regular, monospace';
    surface.fillText('VO 决策空间数据无效', 12, 78);
    voRenderGeometry = null;
    return;
  }

  const width = canvas.width;
  const height = canvas.height;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 2 - 27;
  const maxSpeed = Math.max(...speeds, 1);
  const headingStep = 2 * Math.PI / columns;
  const ownshipHeading = Number(snapshot.ownship_heading_rad) || 0;
  const finiteCosts = costs.filter(Number.isFinite);
  const minimumCost = finiteCosts.length ? Math.min(...finiteCosts) : 0;
  const maximumCost = finiteCosts.length ? Math.max(...finiteCosts) : 1;

  for (let speedIndex = 0; speedIndex < rows; speedIndex += 1) {
    const innerSpeed = speedIndex === 0 ? 0 : (speeds[speedIndex - 1] + speeds[speedIndex]) / 2;
    const outerSpeed = speedIndex === rows - 1
      ? maxSpeed
      : (speeds[speedIndex] + speeds[speedIndex + 1]) / 2;
    const innerRadius = innerSpeed / maxSpeed * radius;
    const outerRadius = outerSpeed / maxSpeed * radius;
    for (let headingIndex = 0; headingIndex < columns; headingIndex += 1) {
      const index = speedIndex * columns + headingIndex;
      const relativeHeading = wrapRadians(headings[headingIndex] - ownshipHeading);
      const start = relativeHeading - headingStep / 2 - Math.PI / 2;
      const end = relativeHeading + headingStep / 2 - Math.PI / 2;
      const cost = costs[index] == null ? NaN : Number(costs[index]);
      const normalizedCost = Number.isFinite(cost) && maximumCost > minimumCost
        ? (cost - minimumCost) / (maximumCost - minimumCost)
        : 0;
      surface.fillStyle = voCandidateColor(bits[index], normalizedCost);
      surface.beginPath();
      surface.arc(centerX, centerY, outerRadius, start, end);
      if (innerRadius > 0) {
        surface.arc(centerX, centerY, innerRadius, end, start, true);
      } else {
        surface.lineTo(centerX, centerY);
      }
      surface.closePath();
      surface.fill();
    }
  }

  surface.strokeStyle = 'rgba(221,235,230,0.26)';
  surface.fillStyle = '#8b9b95';
  surface.lineWidth = 0.7;
  surface.font = '8px SFMono-Regular, monospace';
  surface.textAlign = 'center';
  for (let speed = 2; speed <= maxSpeed; speed += 2) {
    const ringRadius = speed / maxSpeed * radius;
    surface.beginPath();
    surface.arc(centerX, centerY, ringRadius, 0, Math.PI * 2);
    surface.stroke();
    surface.fillText(`${speed}`, centerX + 3, centerY - ringRadius + 9);
  }
  for (let degrees = -180; degrees < 180; degrees += 30) {
    const angle = degrees * Math.PI / 180;
    const endX = centerX + radius * Math.sin(angle);
    const endY = centerY - radius * Math.cos(angle);
    surface.beginPath();
    surface.moveTo(centerX, centerY);
    surface.lineTo(endX, endY);
    surface.stroke();
    surface.fillText(
      `${degrees}°`,
      centerX + (radius + 13) * Math.sin(angle),
      centerY - (radius + 13) * Math.cos(angle) + 3,
    );
  }

  drawVelocityArrow(surface, centerX, centerY, radius, maxSpeed, snapshot.current_velocity_ne_mps, ownshipHeading, '#9aa7a2');
  drawVelocityArrow(surface, centerX, centerY, radius, maxSpeed, snapshot.reference_velocity_ne_mps, ownshipHeading, '#f3f6f5');
  const selected = snapshot.selected || {};
  drawVelocityArrow(
    surface,
    centerX,
    centerY,
    radius,
    maxSpeed,
    [
      Number(selected.speed_mps) * Math.cos(Number(selected.heading_rad)),
      Number(selected.speed_mps) * Math.sin(Number(selected.heading_rad)),
    ],
    ownshipHeading,
    '#58a6ff',
    2.5,
  );
  surface.fillStyle = '#dce8e4';
  surface.beginPath();
  surface.arc(centerX, centerY, 2.5, 0, Math.PI * 2);
  surface.fill();

  surface.save();
  surface.font = '8px SFMono-Regular, monospace';
  surface.textAlign = 'left';
  surface.textBaseline = 'middle';
  [
    { color: '#58a6ff', label: '选中速度', width: 2.5 },
    { color: '#f3f6f5', label: '参考速度', width: 1.7 },
    { color: '#9aa7a2', label: '当前速度', width: 1.7 },
  ].forEach((item, index) => {
    const y = 10 + index * 10;
    surface.strokeStyle = item.color;
    surface.lineWidth = item.width;
    surface.beginPath();
    surface.moveTo(8, y);
    surface.lineTo(20, y);
    surface.stroke();
    surface.fillStyle = item.color;
    surface.fillText(item.label, 24, y);
  });
  surface.restore();

  const selectedCost = selected.total_cost == null ? NaN : Number(selected.total_cost);
  setText('val-best-cost', formatCost(selectedCost));
  setText(
    'val-best-course-offset',
    `${(wrapRadians(Number(selected.heading_rad) - ownshipHeading) * 180 / Math.PI).toFixed(1)}°`,
  );
  setText('val-best-speed-scale', `${Number(selected.speed_mps).toFixed(2)} m/s`);
  voRenderGeometry = {
    snapshot,
    centerX,
    centerY,
    radius,
    maxSpeed,
    rows,
    columns,
    bits,
    costs,
    ttc,
  };
}

function voCandidateLabel(stateBits) {
  if (stateBits & 1) return '有限 TTC / 基础 VO';
  if (stateBits & 8) return 'CS 右转承诺禁区';
  if (stateBits & 4) return 'COLREG V1 禁区';
  if (stateBits & 2) return 'WVO 安全缓冲';
  return '安全';
}

function describeVOCandidate(event) {
  if (!voRenderGeometry) return;
  const canvas = document.getElementById('plannerSurface');
  const bounds = canvas.getBoundingClientRect();
  const x = (event.clientX - bounds.left) * canvas.width / bounds.width;
  const y = (event.clientY - bounds.top) * canvas.height / bounds.height;
  const dx = x - voRenderGeometry.centerX;
  const dy = y - voRenderGeometry.centerY;
  const distance = Math.hypot(dx, dy);
  if (distance > voRenderGeometry.radius) return;

  const snapshot = voRenderGeometry.snapshot;
  const speeds = snapshot.speed_candidates_mps;
  const headings = snapshot.heading_candidates_rad;
  const speed = distance / voRenderGeometry.radius * voRenderGeometry.maxSpeed;
  const relativeHeading = Math.atan2(dx, -dy);
  const absoluteHeading = wrapRadians(relativeHeading + snapshot.ownship_heading_rad);
  const speedIndex = speeds.reduce(
    (best, value, index) => Math.abs(value - speed) < Math.abs(speeds[best] - speed) ? index : best,
    0,
  );
  const headingIndex = headings.reduce(
    (best, value, index) => (
      Math.abs(wrapRadians(value - absoluteHeading))
        < Math.abs(wrapRadians(headings[best] - absoluteHeading))
        ? index : best
    ),
    0,
  );
  const index = speedIndex * voRenderGeometry.columns + headingIndex;
  const costValue = voRenderGeometry.costs[index];
  const ttcValue = voRenderGeometry.ttc[index];
  const candidateCost = costValue == null ? NaN : Number(costValue);
  const candidateTTC = ttcValue == null ? NaN : Number(ttcValue);
  setText(
    'val-surface-explanation',
    `${voCandidateLabel(voRenderGeometry.bits[index])} · 候选 #${index} · 相对航向 `
      + `${(wrapRadians(headings[headingIndex] - snapshot.ownship_heading_rad) * 180 / Math.PI).toFixed(1)}°`
      + ` · 绝对航向 ${((headings[headingIndex] * 180 / Math.PI + 360) % 360).toFixed(1)}°`
      + ` · ${speeds[speedIndex].toFixed(2)} m/s`
      + ` · TTC ${Number.isFinite(candidateTTC) ? `${candidateTTC.toFixed(1)} s` : '∞'}`
      + ` · Cost ${formatCost(candidateCost)}`,
  );
}

document.getElementById('plannerSurface').addEventListener('pointermove', describeVOCandidate);
document.getElementById('plannerSurface').addEventListener('pointerdown', describeVOCandidate);
document.getElementById('plannerSurface').addEventListener('pointerleave', () => {
  if (!voRenderGeometry) return;
  const activeRules = Object.values(voRenderGeometry.snapshot.active_rules || {}).flat();
  setText(
    'val-surface-explanation',
    activeRules.length
      ? `活动规则 ${activeRules.join(', ')}`
      : '当前无活动 COLREG 规则；显示本次真实求解决策空间',
  );
});

function currentDiagnosticPlanner() {
  return telemetryProjection.snapshot().planner.display || {};
}

function updatePlannerSurfaceAttachControl(surfaceType, solveId) {
  const button = document.getElementById('plannerSurfaceAttach');
  if (!button) return;
  button.hidden = !surfaceType;
  const planner = currentDiagnosticPlanner();
  const hasContent = surfaceType === 'vo'
    ? Boolean(
      currentRunId()
      && voDecisionSpace
      && voDecisionSpaceKey?.startsWith(`${currentRunId()}:`)
      && Number.isInteger(solveId)
      && solveId > 0
    )
    : surfaceType === 'fan'
      && Array.isArray(planner.algorithm_details?.candidate_heading_increments_rad)
      && planner.algorithm_details.candidate_heading_increments_rad.length > 0;
  const attached = situationDisplay.isPlannerSurfaceAttached();
  button.disabled = !hasContent && !attached;
  button.textContent = attached ? '收起' : hasContent ? '展开' : '加载中';
  button.setAttribute('aria-pressed', String(attached));
}

function syncPlannerSurfaceMode(planner) {
  if (!plannerSurfaceType(planner) && situationDisplay.isPlannerSurfaceAttached()) {
    setPlannerSurfaceAttached(false, { rerender: false });
  }
}

function setPlannerSurfaceAttached(attached, { rerender = true } = {}) {
  const panel = document.getElementById('plannerSurfacePanel');
  if (!panel || attached === situationDisplay.isPlannerSurfaceAttached()) return;
  if (attached && !plannerSurfaceType(currentDiagnosticPlanner())) return;
  situationDisplay.setPlannerSurfaceAttached(attached);
  panel.hidden = attached;
  lastVORenderKey = null;
  updatePlannerSurfaceAttachControl(
    plannerSurfaceType(currentDiagnosticPlanner()),
    Number(currentDiagnosticPlanner().solve_id),
  );
  window.requestAnimationFrame(() => {
    if (currentData) drawPlannerSurface(currentDiagnosticPlanner());
  });
  if (rerender && currentData) situationDisplay.rerender();
}

document.getElementById('plannerSurfaceAttach').addEventListener('click', () => {
  setPlannerSurfaceAttached(!situationDisplay.isPlannerSurfaceAttached());
});

new ResizeObserver(() => {
  lastVORenderKey = null;
  if (currentData) updatePlannerPanel(telemetryProjection.snapshot());
}).observe(document.querySelector('.planner-surface-wrap'));

function axisTickIndices(valueCount, pixelSpan, minimumSpacing) {
  if (valueCount <= 0) return [];
  const tickCount = Math.min(valueCount, Math.max(2, Math.floor(pixelSpan / minimumSpacing) + 1));
  if (tickCount >= valueCount) return Array.from({ length: valueCount }, (_, index) => index);
  return [...new Set(
    Array.from(
      { length: tickCount },
      (_, index) => Math.round(index * (valueCount - 1) / (tickCount - 1)),
    ),
  )];
}

function formatAxisNumber(value) {
  if (!Number.isFinite(value)) return '--';
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1);
}

function drawSimplifiedMpcFan(surface, canvas, planner, details) {
  const geometry = simplifiedMpcFanGeometry(details);
  const { increments, feasible, selectedIndex, steps, trajectories } = geometry;
  const targetOffset = Number(details.target_bearing_offset_rad);

  setText('label-best-cost', details.selection_mode === 'terminal_distance'
    ? '选择指标·终点距离'
    : '选择指标·航向差');
  setText('label-best-course-offset', '首步转角');
  setText('label-best-speed-scale', '速度策略');
  const score = Number(details.selection_score ?? planner.objective);
  const scoreValue = details.selection_score_unit === 'm'
    ? (Number.isFinite(score) ? `${score.toFixed(1)} m` : '--')
    : (Number.isFinite(score) ? `${(score * 180 / Math.PI).toFixed(2)}°` : '--°');
  const selectedTurn = Number(details.selected_heading_increment_rad);
  setText('val-best-cost', scoreValue);
  setText(
    'val-best-course-offset',
    Number.isFinite(selectedTurn) ? `${(selectedTurn * 180 / Math.PI).toFixed(1)}°` : '--°',
  );
  setText('val-best-speed-scale', '恒速');
  setText(
    'val-surface-explanation',
    details.selection_mode === 'terminal_distance'
      ? '目标在 ±90° 外，按终点距离选择路径'
      : '目标在 ±90° 内，按首段航向差选择路径',
  );
  setText(
    'val-surface-meta',
    `已选 #${Number.isInteger(selectedIndex) ? selectedIndex + 1 : '--'} · 可行 ${Number(details.feasible_candidate_count) || 0}/${increments.length}`,
  );

  if (!trajectories.length) {
    surface.fillStyle = '#65736f';
    surface.font = '11px SFMono-Regular, monospace';
    surface.fillText('等待扇形轨迹数据', 12, 78);
    return;
  }

  const guideLength = steps;
  const guidePoints = [
    { x: -guideLength, y: 0 },
    { x: guideLength, y: 0 },
    { x: 0, y: guideLength },
  ];
  if (Number.isFinite(targetOffset)) {
    guidePoints.push({
      x: Math.sin(targetOffset) * guideLength,
      y: Math.cos(targetOffset) * guideLength,
    });
  }
  const allPoints = [...trajectories.flat(), ...guidePoints, { x: 0, y: 0 }];
  const minX = Math.min(...allPoints.map(point => point.x));
  const maxX = Math.max(...allPoints.map(point => point.x));
  const minY = Math.min(...allPoints.map(point => point.y));
  const maxY = Math.max(...allPoints.map(point => point.y));
  const plot = { left: 6, top: 6, right: canvas.width - 6, bottom: canvas.height - 6 };
  const scale = Math.min(
    (plot.right - plot.left) / Math.max(1, maxX - minX),
    (plot.bottom - plot.top) / Math.max(1, maxY - minY),
  );
  const scaledWidth = (maxX - minX) * scale;
  const scaledHeight = (maxY - minY) * scale;
  const offsetX = plot.left + ((plot.right - plot.left) - scaledWidth) / 2;
  const offsetY = plot.top + ((plot.bottom - plot.top) - scaledHeight) / 2;
  const mapPoint = point => ({
    x: offsetX + (point.x - minX) * scale,
    y: offsetY + scaledHeight - (point.y - minY) * scale,
  });
  const origin = mapPoint({ x: 0, y: 0 });
  const drawGuide = (angle, color, dashed = true) => {
    const end = mapPoint({
      x: Math.sin(angle) * guideLength,
      y: Math.cos(angle) * guideLength,
    });
    surface.strokeStyle = color;
    surface.lineWidth = 1;
    surface.setLineDash(dashed ? [4, 4] : []);
    surface.beginPath();
    surface.moveTo(origin.x, origin.y);
    surface.lineTo(end.x, end.y);
    surface.stroke();
    surface.setLineDash([]);
  };
  drawGuide(-Math.PI / 2, 'rgba(130,145,140,0.45)');
  drawGuide(0, 'rgba(130,145,140,0.45)');
  drawGuide(Math.PI / 2, 'rgba(130,145,140,0.45)');
  if (Number.isFinite(targetOffset)) drawGuide(targetOffset, '#D96BFF', false);

  trajectories.forEach((points, index) => {
    if (index === selectedIndex) return;
    surface.strokeStyle = feasible[index] ? 'rgba(74,191,132,0.52)' : 'rgba(225,86,91,0.48)';
    surface.lineWidth = 1;
    surface.beginPath();
    points.forEach((point, pointIndex) => {
      const mapped = mapPoint(point);
      if (pointIndex === 0) surface.moveTo(mapped.x, mapped.y);
      else surface.lineTo(mapped.x, mapped.y);
    });
    surface.stroke();
  });
  if (Number.isInteger(selectedIndex) && trajectories[selectedIndex]) {
    surface.strokeStyle = '#58A6FF';
    surface.lineWidth = 2.6;
    surface.beginPath();
    trajectories[selectedIndex].forEach((point, pointIndex) => {
      const mapped = mapPoint(point);
      if (pointIndex === 0) surface.moveTo(mapped.x, mapped.y);
      else surface.lineTo(mapped.x, mapped.y);
    });
    surface.stroke();
  }

  surface.fillStyle = '#58A6FF';
  surface.beginPath();
  surface.arc(origin.x, origin.y, 3.5, 0, Math.PI * 2);
  surface.fill();
}

function renderSolveTimeline() {
  const timeline = document.getElementById('solveTimeline');
  timeline.replaceChildren();
  drawObjectiveHistory();
}

function formatCost(value) {
  if (!Number.isFinite(value)) return '--';
  if (Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < 0.01)) {
    return value.toExponential(2);
  }
  return value.toFixed(2);
}

function drawObjectiveHistory() {
  const canvas = document.getElementById('objectiveHistory');
  if (!canvas) return;
  const chart = canvas.getContext('2d');
  chart.clearRect(0, 0, canvas.width, canvas.height);
  chart.fillStyle = '#0d1211';
  chart.fillRect(0, 0, canvas.width, canvas.height);
  const history = solveTimeline.filter(item => Number.isFinite(item.objective));
  if (!history.length) {
    chart.fillStyle = '#65736f';
    chart.font = '11px SFMono-Regular, monospace';
    chart.fillText('等待有效 Cost', 12, 46);
    return;
  }
  const plot = { left: 38, top: 8, right: canvas.width - 8, bottom: canvas.height - 19 };
  const times = history.map(item => item.simTime);
  const costs = history.map(item => item.objective);
  const timeLow = Math.min(...times);
  const timeHigh = Math.max(...times);
  const costLow = Math.min(...costs);
  const costHigh = Math.max(...costs);
  const xAt = time => plot.left + (time - timeLow) / Math.max(1, timeHigh - timeLow) * (plot.right - plot.left);
  const yAt = cost => plot.bottom - (cost - costLow) / Math.max(1e-9, costHigh - costLow) * (plot.bottom - plot.top);

  chart.strokeStyle = 'rgba(130,145,140,0.35)';
  chart.lineWidth = 1;
  chart.beginPath();
  chart.moveTo(plot.left, plot.top);
  chart.lineTo(plot.left, plot.bottom);
  chart.lineTo(plot.right, plot.bottom);
  chart.stroke();

  chart.strokeStyle = '#55D6B7';
  chart.lineWidth = 1.8;
  chart.beginPath();
  history.forEach((item, index) => {
    const x = xAt(item.simTime);
    const y = yAt(item.objective);
    if (index === 0) chart.moveTo(x, y);
    else chart.lineTo(x, y);
  });
  chart.stroke();
  history.forEach(item => {
    chart.fillStyle = '#9EF0DB';
    chart.beginPath();
    chart.arc(xAt(item.simTime), yAt(item.objective), 2, 0, Math.PI * 2);
    chart.fill();
  });

  chart.fillStyle = '#82918c';
  chart.font = '8px SFMono-Regular, monospace';
  chart.textAlign = 'right';
  chart.fillText(formatCost(costHigh), plot.left - 4, plot.top + 3);
  chart.fillText(formatCost(costLow), plot.left - 4, plot.bottom);
  chart.textAlign = 'left';
  chart.fillText(`${timeLow.toFixed(0)}s`, plot.left, canvas.height - 5);
  chart.textAlign = 'right';
  chart.fillText(`${timeHigh.toFixed(0)}s`, plot.right, canvas.height - 5);
}

/* ══════════════════════════════════════════════
   PERFORMANCE SPARKLINE
══════════════════════════════════════════════ */
function drawPerfChart() {
  const pc   = document.getElementById('perfChart');
  if (!pc) return;
  const pctx = pc.getContext('2d');
  const cw   = pc.clientWidth || 288;
  const ch   = 70;
  if (pc.width !== cw) pc.width = cw;
  pctx.clearRect(0, 0, cw, ch);
  pctx.fillStyle = 'rgba(0,0,0,0.15)';
  pctx.fillRect(0, 0, cw, ch);
  if (perfHistory.length < 2) return;

  const maxVal  = Math.max(...perfHistory, 1);
  const range   = maxVal || 1;
  const pad     = 6;
  const xStep   = (cw - pad * 2) / (PERF_HISTORY_LEN - 1);

  const gy = ch - pad - (maxVal / 2 / range) * (ch - pad * 2);
  pctx.strokeStyle = 'rgba(255,255,255,0.07)';
  pctx.lineWidth   = 1;
  pctx.setLineDash([3, 4]);
  pctx.beginPath(); pctx.moveTo(pad, gy); pctx.lineTo(cw - pad, gy); pctx.stroke();
  pctx.setLineDash([]);

  pctx.fillStyle   = 'rgba(98,210,189,0.18)';
  pctx.strokeStyle = 'rgba(98,210,189,0.9)';
  pctx.lineWidth   = 1.5;

  pctx.beginPath();
  perfHistory.forEach((v, i) => {
    const x = pad + i * xStep;
    const y = ch - pad - (v / range) * (ch - pad * 2);
    i === 0 ? pctx.moveTo(x, y) : pctx.lineTo(x, y);
  });
  const lastX = pad + (perfHistory.length - 1) * xStep;
  pctx.lineTo(lastX, ch - pad); pctx.lineTo(pad, ch - pad);
  pctx.closePath(); pctx.fill();

  pctx.beginPath();
  perfHistory.forEach((v, i) => {
    const x = pad + i * xStep;
    const y = ch - pad - (v / range) * (ch - pad * 2);
    i === 0 ? pctx.moveTo(x, y) : pctx.lineTo(x, y);
  });
  pctx.stroke();

  pctx.fillStyle = 'rgba(138,153,173,0.65)';
  pctx.font      = '9px JetBrains Mono, monospace';
  pctx.fillText(`${maxVal.toFixed(1)}ms`, pad + 2, pad + 9);
}

/* ══════════════════════════════════════════════
   EVENT LOG
══════════════════════════════════════════════ */
const BEIJING_TIME_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
});

function formatSystemTime(date = new Date()) {
  return BEIJING_TIME_FORMATTER.format(date);
}

function updateBeijingClock() {
  setText('val-beijing-time', formatSystemTime());
  const topbarClock = document.getElementById('topbarBeijingClock');
  if (topbarClock) topbarClock.date = new Date();
  const snapshot = activeSessionRuntime.snapshot();
  if (snapshot.connection.status !== 'connected' && snapshot.telemetry.receivedAt !== null) {
    const labels = { connecting: '初始化', reconnecting: '重连', disconnected: '断连' };
    const ageSeconds = Math.floor((snapshot.telemetry.staleAgeMs || 0) / 1000);
    setText('conn-status', `会话: ${labels[snapshot.connection.status] || '断连'} · STALE ${ageSeconds}s`);
  }
}

function pushLog(msg, cls = 'log-info') {
  const terminal = document.getElementById('logTerminal');
  if (!terminal) return;
  const entry = document.createElement('div');
  entry.className = `log-entry ${cls}`;
  entry.textContent = `[${formatSystemTime()}] ${msg}`;
  terminal.appendChild(entry);
  while (terminal.children.length > 120) terminal.removeChild(terminal.firstChild);
  terminal.scrollTop = terminal.scrollHeight;
}

function renderTimelineLog(proj) {
  const events = proj.timeline.events;
  if (events.length < renderedTimelineEvents) renderedTimelineEvents = 0;
  for (; renderedTimelineEvents < events.length; renderedTimelineEvents += 1) {
    const event = events[renderedTimelineEvents];
    if (event.type === 'colregs_change') {
      const { from, to, targetLabel } = event.details;
      if (to === 'clear') {
        const previousRule = ENCOUNTER_LABELS[from] || from;
        const previousTarget = targetLabel ? ` / ${targetLabel}` : '';
        pushLog(`COLREGs → ${ENCOUNTER_LABELS.clear}（结束 ${previousRule}${previousTarget}）`, 'log-ok');
        continue;
      }
      const cls = to === 'head_on'           ? 'log-warn'   :
                  to === 'crossing_give_way' ? 'log-danger' :
                                                'log-info';
      const ruleLabel = ENCOUNTER_LABELS[to] || to;
      const targetSuffix = targetLabel ? ` / ${targetLabel}` : '';
      pushLog(`COLREGs → ${ruleLabel}${targetSuffix}`, cls);
      continue;
    }
    if (event.type === 'dcpa_level_change') {
      const { level: lvl, dcpaM, targetLabel } = event.details;
      const targetSuffix = targetLabel ? ` / ${targetLabel}` : '';
      pushLog(`DCPA ${lvl.toUpperCase()}${targetSuffix} — ${dcpaM.toFixed(0)} m`,
              lvl === 'safe' ? 'log-ok' : lvl === 'warn' ? 'log-warn' : 'log-danger');
      continue;
    }
    if (event.type === 'planner_solved') {
      const algorithm = String(proj.planner.algorithmId || 'planner').toUpperCase();
      const simTime = Number(event.simTime);
      const solveId = Number(event.details.solve_id);
      const solveLabel = Number.isFinite(solveId) && solveId > 0 ? ` #${solveId}` : '';
      const timeLabel = Number.isFinite(simTime) ? ` · 仿真 ${simTime.toFixed(1)}s` : '';
      pushLog(`${algorithm} 求解成功${solveLabel}${timeLabel}`, 'log-ok');
      continue;
    }
    const detail = event.details && event.details.reason ? `: ${event.details.reason}` : '';
    pushLog(`${event.type}${detail}`, event.type.includes('fail') ? 'log-danger' : 'log-info');
  }
}

function renderProjection(proj) {
  const data = proj.raw;
  if (!data) return;
  currentData = data;
  if (data.os) {
    updateUI(proj);
    situationDisplay.render(data);
    renderTimelineLog(proj);
  }
}

/* ══════════════════════════════════════════════
   WEBSOCKET
══════════════════════════════════════════════ */
async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === 'object'
      ? `${detail.status || 'ERROR'}: ${detail.reason || JSON.stringify(detail)}`
      : detail || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

function setSessionConnectionState(state, logEvent = false) {
  const states = {
    connected: { text: '会话: 连通', logClass: 'log-ok' },
    connecting: { text: '会话: 初始化', logClass: 'log-warn' },
    reconnecting: { text: '会话: 重连', logClass: 'log-warn' },
    disconnected: { text: '会话: 断连', logClass: 'log-danger' },
  };
  const next = states[state];
  if (!next) return;

  const indicator = document.getElementById('status-dot').closest('.status-indicator');
  const dot = document.getElementById('status-dot');
  indicator.classList.remove('connected', 'connecting', 'reset', 'reconnecting', 'disconnected');
  indicator.classList.add(state);
  dot.classList.toggle('active', state === 'connected');
  dot.classList.toggle('reset', state === 'reconnecting' || state === 'connecting');
  document.getElementById('conn-status').textContent = next.text;
  if (logEvent) pushLog(next.text, next.logClass);
}

function isBusyWaterScenario(scenarioId) {
  return scenarioId === 'romsdal_busy_water_16';
}

function syncBusyWaterSetupVisibility(scenarioId = document.getElementById('scenarioSelect').value) {
  const visible = isBusyWaterScenario(scenarioId);
  document.getElementById('cardBusyWater').hidden = !visible;
  if (visible) renderBusyTargetList();
}

async function generateBusyWaterDocument({ scenarioId, targetCount, seed, crossing, headOn, overtaking }) {
  const params = new URLSearchParams({
    profile: 'acceptance',
    target_count: String(targetCount),
    seed: String(seed),
    crossing_ratio: String(crossing),
    head_on_ratio: String(headOn),
    overtaking_ratio: String(overtaking),
  });
  const payload = await apiRequest(`/api/busy-water/generate?${params}`);
  busyWaterDocument = payload.document;
  busyWaterSeed = Number(seed);
  busyWaterMix = {
    crossing: Number(payload.encounter_mix.crossing),
    head_on: Number(payload.encounter_mix.head_on),
    overtaking: Number(payload.encounter_mix.overtaking),
  };
  selectedTargetId = null;
  targetEditorKey = null;
  document.getElementById('targetEditForm').hidden = true;
  renderBusyTargetList();
  return payload;
}

async function persistBusyWaterDocument() {
  if (!busyWaterDocument) return;
  await apiRequest('/api/busy-water/drafts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'Current Multiship',
      base_scenario_id: 'romsdal_busy_water_16',
      seed: busyWaterSeed,
      encounter_mix: busyWaterMix,
      document: busyWaterDocument,
    }),
  });
}

function resetDeploymentForSession(data) {
  setPlannerSurfaceAttached(false, { rerender: false });
  if (voDecisionSpaceController) voDecisionSpaceController.abort();
  if (voDecisionSpaceRetryTimer !== null) window.clearTimeout(voDecisionSpaceRetryTimer);
  voDecisionSpace = null;
  voDecisionSpaceKey = null;
  voDecisionSpaceRequestKey = null;
  voDecisionSpaceAttemptedKey = null;
  voDecisionSpaceController = null;
  voDecisionSpacePending = null;
  voDecisionSpaceRetryTimer = null;
  lastVODecisionRequestAt = 0;
  lastVORenderKey = null;
  voRenderGeometry = null;
  // Animation/ENC teardown lives in the situation-display module
  // (beginSession/clearSession call resetAnimation internally).
  currentData = null;
  perfHistory.length = 0;
  solveTimeline = [];
  lastDisplayedSolveId = null;
  lastSolveSimTime = null;
  lastRuntimeState = 'CREATED';
  setRuntimePanelsExpanded(false);
  renderSolveTimeline();
  renderedTimelineEvents = 0;
  setEncStatus('loading');
  syncPlaybackStatus(data.playback, false);
  syncEncChartSelect(document.getElementById('scenarioSelect').value);
  situationDisplay.beginSession(data.session_id || currentRunId());
}

function syncRuntimeControls(snapshot) {
  const state = snapshot.sessionState;
  const locked = snapshot.authority.status !== 'known' || !snapshot.session || Boolean(snapshot.pending);
  document.getElementById('btnStart').disabled = locked || state === 'RUNNING' || state === 'FINISHED' || state === 'FAILED';
  document.getElementById('btnPause').disabled = locked || state !== 'RUNNING';
  document.getElementById('btnStep').disabled = locked || (state !== 'CREATED' && state !== 'PAUSED');
  document.getElementById('btnReset').disabled = locked;
  document.getElementById('btnReplay').disabled = locked
    || state !== 'FINISHED'
    || snapshot.outcome.status !== 'ready'
    || !snapshot.outcome.result;
  document.querySelectorAll('.speed-preset').forEach((button) => { button.disabled = locked; });
}

function syncDeploymentRuntime(snapshot) {
  const previous = deploymentRuntimeSnapshot;
  const previousSessionId = previous.session?.session_id || null;
  const sessionId = snapshot.session?.session_id || null;
  deploymentRuntimeSnapshot = snapshot;

  if (previous.connection.status !== snapshot.connection.status) {
    setSessionConnectionState(snapshot.connection.status, previousSessionId !== null);
  }
  if (previous.authority.status !== snapshot.authority.status && snapshot.authority.status === 'unknown') {
    pushLog(snapshot.authority.error?.message || 'Active Session authority is unknown.', 'log-danger');
  }
  if (sessionId !== previousSessionId) {
    handledTelemetryRevision = 0;
    handledOutcomeKey = '';
    reportedFailureSessionId = null;
    if (snapshot.session) {
      restoreSessionSelection(snapshot.session.spec || {});
      resetDeploymentForSession(snapshot.session);
      pushLog(
        `Active Session: ${snapshot.session.spec?.scenario_id} / ${snapshot.session.spec?.algorithm_id} / ${snapshot.session.spec?.tracker_id}`,
        'log-info',
      );
    } else {
      situationDisplay.clearSession();
      currentData = null;
      setText('val-run-state', 'NO SESSION');
      setText('val-sim-time', '0.0 s');
      setSessionConnectionState('disconnected');
    }
  }

  if (snapshot.telemetry.revision !== handledTelemetryRevision && snapshot.telemetry.envelope) {
    handledTelemetryRevision = snapshot.telemetry.revision;
    const data = snapshot.telemetry.envelope;
    if (data.state === 'FAILED' && reportedFailureSessionId !== sessionId) {
      reportedFailureSessionId = sessionId;
      pushLog(data.failure_reason || 'Simulation failed.', 'log-danger');
    }
  }

  const outcomeKey = `${sessionId || 'none'}:${snapshot.outcome.status}`;
  if (outcomeKey !== handledOutcomeKey) {
    handledOutcomeKey = outcomeKey;
    if (snapshot.outcome.status === 'ready') {
      const artifactCount = snapshot.outcome.artifacts?.length || 0;
      if (snapshot.sessionState === 'FAILED') {
        const reason = snapshot.telemetry.envelope?.failure_reason || snapshot.session?.failure_reason || 'unknown failure';
        pushLog(`FAILED artifacts ready: ${artifactCount} · ${reason}`, 'log-danger');
      } else {
        const reproduction = snapshot.outcome.result?.manifest?.reproduction_status || 'not evaluated';
        pushLog(`Evaluation ready: ${reproduction} · ${artifactCount} artifacts.`, 'log-ok');
      }
    } else if (snapshot.outcome.status === 'error') {
      pushLog(`Outcome load failed: ${snapshot.outcome.error?.message || 'unknown error'}`, 'log-danger');
    }
  }
  syncRuntimeControls(snapshot);
}

async function populateCatalogs(ruleId = 'rule14') {
  const [catalog, allCapabilities] = await Promise.all([
    apiRequest(`/api/capabilities?validation_rule_id=${encodeURIComponent(ruleId)}`),
    ruleCatalog.length ? Promise.resolve(null) : apiRequest('/api/capabilities'),
  ]);
  capabilityCatalog = catalog;
  if (allCapabilities) ruleCatalog = allCapabilities.rules;

  const scenarioSelect = document.getElementById('scenarioSelect');
  const selectedScenario = scenarioSelect.value;
  scenarioCatalog = catalog.scenarios.filter(item => item.id !== 'romsdal_busy_water_80_stress');
  populateScenarioOptions(ruleId, selectedScenario);

  document.querySelectorAll('.qtab').forEach(tab => {
    const rule = ruleCatalog.find(item => item.id === tab.dataset.group);
    const selectable = Boolean(rule?.selectable);
    tab.disabled = !selectable;
    tab.classList.toggle('available', selectable);
    tab.classList.toggle('unavailable', !selectable);
    tab.querySelector('.selection-state').textContent =
      `${rule?.readiness_grade || 'G0'} · ${selectable ? '可选' : '禁选'}`;
    tab.title = rule?.incompatibility_reason || `${rule?.readiness_grade || 'G0'} display ready`;
  });

  const integrations = [...catalog.algorithms, ...catalog.trackers];
  const statusMap = Object.fromEntries(integrations.map(item => [item.id, item]));
  document.querySelectorAll('[data-integration]').forEach(chip => {
    const status = statusMap[chip.dataset.integration];
    const selectable = Boolean(status?.selectable);
    chip.classList.toggle('available', selectable);
    chip.classList.toggle('unavailable', !selectable);
    chip.querySelector('.integration-state').textContent = status?.dependency_available
      ? `${status.readiness_grade} · ${selectable ? '可选' : '禁选'}`
      : '缺依赖';
    chip.title = status?.incompatibility_reason
      || `${status?.source || '内置接口'}${status?.version ? ` · v${status.version}` : ''}`;
  });

  ensureSelectableValue(
    document.getElementById('algoSelect'),
    catalog.algorithms,
    catalog.defaults.algorithm_id,
  );
  ensureSelectableValue(
    document.getElementById('trackerSelect'),
    catalog.trackers,
    catalog.defaults.tracker_id,
  );
  document.querySelectorAll('#algoSelect option').forEach(option => {
    const status = statusMap[option.value];
    option.disabled = !status?.selectable;
    option.title = status?.incompatibility_reason || `${status?.readiness_grade || 'G0'} ready`;
  });
  document.querySelectorAll('#trackerSelect option').forEach(option => {
    const status = statusMap[option.value];
    option.disabled = !status?.selectable;
    option.title = status?.incompatibility_reason || `${status?.readiness_grade || 'G0'} ready`;
  });
  document.querySelectorAll('[data-algorithm]').forEach(card => {
    setSelectionAvailability(card, statusMap[card.dataset.algorithm]);
  });
  document.querySelectorAll('[data-tracker]').forEach(card => {
    setSelectionAvailability(card, statusMap[card.dataset.tracker]);
  });
  syncExactCombinationAvailability();
  syncSelectionCards('algorithm', document.getElementById('algoSelect').value);
  syncSelectionCards('tracker', document.getElementById('trackerSelect').value);
}

function syncExactCombinationAvailability(changedSelectId = null) {
  if (!capabilityCatalog) return;
  const ruleId = document.querySelector('.qtab.active')?.dataset.group || 'rule14';
  const combinations = (capabilityCatalog.selectable_combinations
    || capabilityCatalog.verified_combinations
    || [])
    .filter(item => item.validation_rule_id === ruleId);
  const scenarioSelect = document.getElementById('scenarioSelect');
  const algorithmSelect = document.getElementById('algoSelect');
  const trackerSelect = document.getElementById('trackerSelect');
  const current = {
    scenario_id: scenarioSelect.value,
    algorithm_id: algorithmSelect.value,
    tracker_id: trackerSelect.value,
  };
  const exact = combinations.find(item => (
    item.scenario_id === current.scenario_id
    && item.algorithm_id === current.algorithm_id
    && item.tracker_id === current.tracker_id
  ));
  let preferred = null;
  if (changedSelectId === 'scenarioSelect') {
    preferred = combinations.find(item => (
      item.scenario_id === current.scenario_id
      && item.tracker_id === current.tracker_id
    )) || combinations.find(item => item.scenario_id === current.scenario_id);
  } else if (changedSelectId === 'algoSelect') {
    preferred = combinations.find(item => (
      item.algorithm_id === current.algorithm_id
      && item.scenario_id === current.scenario_id
    )) || combinations.find(item => item.algorithm_id === current.algorithm_id);
  } else if (changedSelectId === 'trackerSelect') {
    preferred = combinations.find(item => (
      item.tracker_id === current.tracker_id
      && item.scenario_id === current.scenario_id
      && item.algorithm_id === current.algorithm_id
    )) || combinations.find(item => item.tracker_id === current.tracker_id);
  }
  const selected = exact
    || preferred
    || combinations.find(item => (
      item.scenario_id === current.scenario_id
      && item.algorithm_id === capabilityCatalog.defaults.algorithm_id
      && item.tracker_id === capabilityCatalog.defaults.tracker_id
    ))
    || combinations[0];
  if (!selected) return;
  scenarioSelect.value = selected.scenario_id;
  algorithmSelect.value = selected.algorithm_id;
  trackerSelect.value = selected.tracker_id;

  const selectedIds = {
    scenario_id: scenarioSelect.value,
    algorithm_id: algorithmSelect.value,
    tracker_id: trackerSelect.value,
  };
  const permits = (kind, value) => combinations.some(item => {
    if (item[kind] !== value) return false;
    if (kind === 'scenario_id') return true;
    return (
      (kind === 'algorithm_id' || item.algorithm_id === selectedIds.algorithm_id)
      && (kind === 'tracker_id' || item.tracker_id === selectedIds.tracker_id)
      && item.scenario_id === selectedIds.scenario_id
    );
  });
  document.querySelectorAll('#scenarioSelect option').forEach(option => {
    option.disabled = !permits('scenario_id', option.value);
    if (option.disabled) option.title = '当前规则下无可用算法组合';
  });
  document.querySelectorAll('#algoSelect option').forEach(option => {
    option.disabled = !permits('algorithm_id', option.value);
    if (option.disabled) option.title = '未通过当前场景与跟踪器的精确 G3 组合门';
  });
  document.querySelectorAll('#trackerSelect option').forEach(option => {
    option.disabled = !permits('tracker_id', option.value);
    if (option.disabled) option.title = '未通过当前场景与算法的精确 G3 组合门';
  });

  const statusById = Object.fromEntries(
    [...capabilityCatalog.scenarios, ...capabilityCatalog.algorithms, ...capabilityCatalog.trackers]
      .map(item => [item.id, item]),
  );
  document.querySelectorAll('[data-scenario]').forEach(card => {
    setExactSelectionAvailability(card, statusById[card.dataset.scenario], permits('scenario_id', card.dataset.scenario));
  });
  document.querySelectorAll('[data-algorithm]').forEach(card => {
    setExactSelectionAvailability(card, statusById[card.dataset.algorithm], permits('algorithm_id', card.dataset.algorithm));
  });
  document.querySelectorAll('[data-tracker]').forEach(card => {
    setExactSelectionAvailability(card, statusById[card.dataset.tracker], permits('tracker_id', card.dataset.tracker));
  });
  syncScenarioCards(scenarioSelect.value);
  syncSelectionCards('algorithm', algorithmSelect.value);
  syncSelectionCards('tracker', trackerSelect.value);
  syncBusyWaterSetupVisibility(scenarioSelect.value);
}

function setExactSelectionAvailability(card, status, selectable) {
  setSelectionAvailability(card, {
    ...(status || {}),
    selectable,
    incompatibility_reason: selectable
      ? null
      : '该选项不属于当前 rule/scenario/algorithm/tracker 可用组合',
  });
}

function ensureSelectableValue(select, entries, preferredId) {
  const current = entries.find(item => item.id === select.value && item.selectable);
  const fallback = entries.find(item => item.id === preferredId && item.selectable)
    || entries.find(item => item.selectable);
  select.value = (current || fallback)?.id || '';
}

function setSelectionAvailability(card, status) {
  const selectable = Boolean(status?.selectable);
  card.hidden = !selectable;
  card.classList.toggle('available', selectable);
  card.classList.toggle('unavailable', !selectable);
  card.disabled = !selectable;
  card.querySelector('.selection-state').textContent = status?.dependency_available
    ? `${status.readiness_grade} · ${selectable ? '可选' : '禁选'}`
    : '缺依赖';
  card.title = status?.incompatibility_reason || `${status?.readiness_grade || 'G0'} ready`;
}

function syncSelectionCards(kind, value) {
  document.querySelectorAll(`[data-${kind}]`).forEach(card => {
    const selected = card.dataset[kind] === value;
    card.classList.toggle('selected', selected);
    card.setAttribute('aria-pressed', String(selected));
  });
}

function restoreSessionSelection(spec = {}) {
  const ruleId = spec.validation_rule_id || 'rule14';
  setActiveQuickGroup(ruleId);
  const values = [
    ['scenarioSelect', spec.scenario_id],
    ['algoSelect', spec.algorithm_id],
    ['trackerSelect', spec.tracker_id],
  ];
  values.forEach(([id, value]) => {
    const select = document.getElementById(id);
    if (value && select.querySelector(`option[value="${CSS.escape(value)}"]`)) select.value = value;
  });
  syncExactCombinationAvailability();
}

/* ══════════════════════════════════════════════
   CONTROLS
══════════════════════════════════════════════ */
function scenarioDisplayName(item) {
  const fallback = (item.name || item.id.split('/').pop())
    .replaceAll('_', ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
  return `${SCENARIO_LABELS[item.id] || fallback} · ${item.readiness_grade} · ${Math.round(item.t_end)}s`;
}

function scenarioChart(scenarioId) {
  return /(^|\/)(rl|rrt|planning)|boknafjorden|rogaland/i.test(scenarioId)
    ? 'rogaland'
    : 'romsdal';
}

function syncEncChartSelect(scenarioId) {
  const select = document.getElementById('encChartSelect');
  if (!select) return;
  const availableCharts = new Set(
    scenarioCatalog.filter(item => item.selectable).map(item => scenarioChart(item.id)),
  );
  Object.keys(ENC_CHARTS).forEach(chartId => {
    const option = select.querySelector(`option[value="${chartId}"]`);
    if (option) option.disabled = !availableCharts.has(chartId);
  });
  const chartId = scenarioChart(scenarioId);
  if (select.querySelector(`option[value="${chartId}"]`)) select.value = chartId;
}

function setActiveQuickGroup(groupId) {
  document.querySelectorAll('.qtab').forEach(tab => {
    const selected = tab.dataset.group === groupId;
    tab.classList.toggle('active', selected);
    tab.classList.toggle('selected', selected);
    tab.setAttribute('aria-pressed', String(selected));
  });
}

function renderScenarioCards(items, selectedScenario) {
  const catalog = document.getElementById('scenarioCatalog');
  catalog.replaceChildren();
  items.forEach(item => {
    const card = document.createElement('button');
    const selectable = Boolean(item.selectable);
    card.type = 'button';
    card.className = 'selection-card';
    card.dataset.scenario = item.id;
    card.disabled = !selectable;
    card.classList.toggle('available', selectable);
    card.classList.toggle('unavailable', !selectable);
    card.classList.toggle('selected', item.id === selectedScenario);
    card.setAttribute('aria-pressed', String(item.id === selectedScenario));
    card.title = item.incompatibility_reason || `${item.readiness_grade} ready`;
    const name = document.createElement('span');
    name.className = 'selection-name';
    name.textContent = SCENARIO_LABELS[item.id] || item.name || item.id.split('/').pop().replaceAll('_', ' ');
    const description = document.createElement('span');
    description.className = 'selection-description';
    description.textContent =
      `${SCENARIO_TYPE_DESCRIPTIONS[item.type] || item.type} · ${Math.round(item.t_end)}s`;
    const state = document.createElement('span');
    state.className = 'selection-state';
    state.textContent = `${item.readiness_grade} · ${selectable ? '可选' : '禁选'}`;
    card.append(name, description, state);
    catalog.appendChild(card);
  });
}

function syncScenarioCards(scenarioId) {
  document.querySelectorAll('[data-scenario]').forEach(card => {
    const selected = card.dataset.scenario === scenarioId;
    card.classList.toggle('selected', selected);
    card.setAttribute('aria-pressed', String(selected));
  });
}

function populateScenarioOptions(groupId, preferredScenario) {
  const group = SCENARIO_GROUPS[groupId] || SCENARIO_GROUPS.rule14;
  const items = scenarioCatalog.filter(item => group.types.includes(item.type) && item.selectable);
  const scenarioSelect = document.getElementById('scenarioSelect');
  scenarioSelect.replaceChildren();
  items.forEach(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = scenarioDisplayName(item);
    option.disabled = !item.selectable;
    option.title = item.incompatibility_reason || `${item.readiness_grade} ready`;
    scenarioSelect.appendChild(option);
  });
  const selectableItems = items.filter(item => item.selectable);
  const selectedScenario = selectableItems.some(item => item.id === preferredScenario)
    ? preferredScenario
    : selectableItems.some(item => item.id === group.defaultScenario)
      ? group.defaultScenario
      : selectableItems[0]?.id;
  if (selectedScenario) scenarioSelect.value = selectedScenario;
  setActiveQuickGroup(groupId);
  renderScenarioCards(items, selectedScenario);
  syncEncChartSelect(selectedScenario);
  return selectedScenario;
}

function syncQuickScenarioTab(scenarioId) {
  const scenario = scenarioCatalog.find(item => item.id === scenarioId);
  if (!scenario) return;
  const groupId = Object.entries(SCENARIO_GROUPS)
    .find(([, group]) => group.types.includes(scenario.type))?.[0];
  if (groupId) setActiveQuickGroup(groupId);
}

document.getElementById('busyWaterForm').addEventListener('submit', async event => {
  event.preventDefault();
  const scenarioId = document.getElementById('scenarioSelect').value;
  const status = document.getElementById('busyWaterStatus');
  const targetCount = Number(document.getElementById('busyTargetCount').value);
  if (!Number.isInteger(targetCount) || targetCount < 0 || targetCount > 40) {
    status.textContent = '目标船数量必须为 0–40 的整数';
    return;
  }
  status.textContent = '生成中…';
  try {
    const payload = await generateBusyWaterDocument({
      scenarioId,
      targetCount,
      seed: busyWaterSeed,
      crossing: 0.6,
      headOn: 0.2,
      overtaking: 0.2,
    });
    status.textContent = `已生成 ${payload.preflight.target_count} 艘目标船`;
    await persistBusyWaterDocument();
    pushLog('Legacy busy-water draft saved only. Validation Draft and Active Session are unchanged; explicit attachment belongs to the future Scenario surface.', 'log-info');
  } catch (error) {
    status.textContent = error.message;
  }
});

document.getElementById('busyTargetList').addEventListener('click', event => {
  const button = event.target.closest('[data-target-id]');
  if (!button) return;
  targetEditorKey = null;
  situationDisplay.selectTarget(Number(button.dataset.targetId));
});

document.getElementById('pickTargetRouteStart').addEventListener('click', () => startRoutePointPick('start'));
document.getElementById('pickTargetRouteEnd').addEventListener('click', () => startRoutePointPick('end'));
document.getElementById('cancelTargetEdit').addEventListener('click', () => {
  situationDisplay.setClickMode(null);
  situationDisplay.selectTarget(null);
  targetEditorKey = null;
  document.getElementById('targetEditForm').hidden = true;
  renderBusyTargetList();
});

document.getElementById('targetEditForm').addEventListener('submit', async event => {
  event.preventDefault();
  const ship = selectedBusyWaterShip();
  if (!ship || currentData?.state === 'RUNNING') return;
  const speedKnots = Number(document.getElementById('targetSpeed').value);
  const lat1 = Number(document.getElementById('targetRouteLat1').value);
  const lon1 = Number(document.getElementById('targetRouteLon1').value);
  const lat2 = Number(document.getElementById('targetRouteLat2').value);
  const lon2 = Number(document.getElementById('targetRouteLon2').value);
  if (![speedKnots, lat1, lon1, lat2, lon2].every(Number.isFinite) || speedKnots <= 0) {
    pushLog('经纬度与航速必须有效。', 'log-danger');
    return;
  }
  const [start, end] = await Promise.all([wgs84ToUtm(lat1, lon1), wgs84ToUtm(lat2, lon2)]);
  const { north: n1, east: e1 } = start;
  const { north: n2, east: e2 } = end;
  if (Math.hypot(n2 - n1, e2 - e1) < 100) {
    pushLog('目标船航线至少需要 100 m。', 'log-danger');
    return;
  }
  const speed = speedKnots * METERS_PER_KNOT;
  const candidate = structuredClone(busyWaterDocument);
  const edited = candidate.ship_list.find(item => String(item.id) === String(ship.id));
  const course = (Math.atan2(e2 - e1, n2 - n1) * 180 / Math.PI + 360) % 360;
  edited.csog_state = [n1, e1, speed, course];
  edited.waypoints = [[n1, n2], [e1, e2]];
  edited.speed_plan = [speed, speed];
  edited.encounter_role = encounterRoleFromEditor(document.getElementById('targetColregs').value);
  busyWaterDocument = candidate;
  targetEditorKey = null;
  await updateTargetDetails({ id: ship.id }, currentData || { state: 'CREATED' });
  try {
    await persistBusyWaterDocument();
    document.getElementById('busyWaterStatus').textContent = `TS${ship.id} 仅保存到 legacy draft`;
    pushLog(`TS${ship.id} saved to legacy draft only. Validation Draft and Active Session are unchanged; explicit attachment belongs to the future Scenario surface.`, 'log-ok');
  } catch (error) {
    document.getElementById('busyWaterStatus').textContent = '仅 legacy draft 本地变更；持久化失败；Validation Draft 与 Active Session 未改变';
    pushLog(`目标船配置保存失败: ${error.message}`, 'log-danger');
  }
});

document.getElementById('btnStart').addEventListener('click', async () => {
  try {
    await activeSessionRuntime.start();
    setRuntimePanelsExpanded(true);
    pushLog('Simulation started.', 'log-ok');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnPause').addEventListener('click', async () => {
  try {
    await activeSessionRuntime.pause();
    pushLog('Simulation paused.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnStep').addEventListener('click', async () => {
  try {
    await activeSessionRuntime.step();
    pushLog('Single simulation step executed.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnReset').addEventListener('click', async () => {
  try {
    await activeSessionRuntime.reset();
    pushLog('Session reset to CREATED from its immutable Run Specification.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnReplay').addEventListener('click', async () => {
  try {
    await activeSessionRuntime.replay();
    pushLog('Verified replay session created from source manifest.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.querySelectorAll('[data-algorithm]').forEach(card => {
  card.addEventListener('click', () => {
    if (card.disabled) return;
    const select = document.getElementById('algoSelect');
    if (select.value === card.dataset.algorithm) return;
    select.value = card.dataset.algorithm;
    select.dispatchEvent(new Event('change'));
  });
});

document.querySelectorAll('[data-tracker]').forEach(card => {
  card.addEventListener('click', () => {
    if (card.disabled) return;
    const select = document.getElementById('trackerSelect');
    if (select.value === card.dataset.tracker) return;
    select.value = card.dataset.tracker;
    select.dispatchEvent(new Event('change'));
  });
});

document.getElementById('scenarioCatalog').addEventListener('click', event => {
  const card = event.target.closest('[data-scenario]');
  if (!card || card.disabled) return;
  const select = document.getElementById('scenarioSelect');
  if (select.value === card.dataset.scenario) return;
  select.value = card.dataset.scenario;
  select.dispatchEvent(new Event('change'));
});

document.getElementById('encChartSelect').addEventListener('change', async event => {
  const chartId = event.target.value;
  const activeGroup = document.querySelector('.qtab.active')?.dataset.group || 'rule14';
  const group = SCENARIO_GROUPS[activeGroup] || SCENARIO_GROUPS.rule14;
  const target = scenarioCatalog.find(item => (
    item.selectable
    && group.types.includes(item.type)
    && scenarioChart(item.id) === chartId
  ));
  if (!target) {
    syncEncChartSelect(document.getElementById('scenarioSelect').value);
    return;
  }
  populateScenarioOptions(activeGroup, target.id);
  setEncStatus('loading');
  pushLog('Legacy chart selector changed locally; Validation Draft and Active Session are unchanged.', 'log-info');
});

['algoSelect', 'scenarioSelect', 'trackerSelect'].forEach(id => {
  document.getElementById(id).addEventListener('change', async () => {
    syncExactCombinationAvailability(id);
    if (id === 'scenarioSelect') {
      const scenarioId = document.getElementById(id).value;
      syncBusyWaterSetupVisibility(scenarioId);
      syncQuickScenarioTab(scenarioId);
      syncScenarioCards(scenarioId);
      syncEncChartSelect(scenarioId);
      setEncStatus('loading');
    } else if (id === 'algoSelect') {
      syncSelectionCards('algorithm', document.getElementById(id).value);
    } else {
      syncSelectionCards('tracker', document.getElementById(id).value);
    }
    pushLog('Legacy selection changed locally; active session was not replaced.', 'log-info');
  });
});

document.querySelectorAll('.qtab').forEach(tab => {
  tab.addEventListener('click', async () => {
    if (tab.disabled) return;
    try {
      await populateCatalogs(tab.dataset.group);
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });
});

document.querySelectorAll('.speed-preset').forEach(button => {
  button.addEventListener('click', async () => {
    const speed = parseFloat(button.dataset.speed);
    try {
      await activeSessionRuntime.setSpeed(speed);
      const playback = activeSessionRuntime.snapshot().session?.playback;
      syncPlaybackStatus(playback, currentData?.state === 'RUNNING');
    } catch (error) {
      pushLog(`Speed change failed: ${error.message}`, 'log-danger');
      syncPlaybackStatus(currentData?.playback, currentData?.state === 'RUNNING');
    } finally {
      syncRuntimeControls(activeSessionRuntime.snapshot());
    }
  });
});

const RUNTIME_PANEL_IDS = ['cardSafety', 'cardTelemetry', 'cardPlanner', 'cardPerf'];
const LEGACY_CONFIG_CARD_IDS = ['cardIntegrations', 'cardRules', 'cardControl', 'cardTracker', 'cardBusyWater'];

function setCardCollapsed(card, collapsed) {
  card.classList.toggle('collapsed', collapsed);
  const button = card.querySelector('.card-toggle');
  if (!button) return;
  button.textContent = collapsed ? '展开' : '收起';
  button.setAttribute('aria-expanded', String(!collapsed));
  if (!collapsed && card.id === 'cardPlanner' && currentData) {
    updatePlannerPanel(telemetryProjection.snapshot());
  }
}

function initializeCollapsibleCard(card, collapsed) {
  if (!card || card.classList.contains('collapsible-card')) return;
  card.classList.add('collapsible-card');
  const heading = card.querySelector(':scope > .planner-heading') || card.querySelector(':scope > .card-title');
  if (!heading) return;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'card-toggle';
  button.addEventListener('click', () => setCardCollapsed(card, !card.classList.contains('collapsed')));
  heading.appendChild(button);
  setCardCollapsed(card, collapsed);
}

function setRuntimePanelsExpanded(expanded) {
  RUNTIME_PANEL_IDS.forEach(id => {
    const card = document.getElementById(id);
    if (card) setCardCollapsed(card, id === 'cardPerf' || !expanded);
  });
}

function prepareWorkspaceLayout() {
  const insights = document.querySelector('.insights-column');
  const sidebar = document.querySelector('.sidebar-column');
  const controls = document.createElement('div');
  controls.className = 'sidebar-controls-scroll';
  const movedNotice = document.createElement('div');
  movedNotice.className = 'legacy-config-moved';
  movedNotice.textContent = 'Configuration moved to Config. Deployment controls are read-only runtime controls.';
  controls.appendChild(movedNotice);
  LEGACY_CONFIG_CARD_IDS.forEach(id => {
    const card = document.getElementById(id);
    if (card) {
      card.classList.add('legacy-config-retired');
      card.hidden = true;
      controls.appendChild(card);
    }
  });
  sidebar.prepend(controls);
  RUNTIME_PANEL_IDS.forEach(id => {
    const card = document.getElementById(id);
    if (card) {
      insights.appendChild(card);
      initializeCollapsibleCard(card, true);
    }
  });
  const eventLog = document.querySelector('.log-section');
  if (eventLog) {
    initializeCollapsibleCard(eventLog, false);
  }
  const initialLogEntry = document.getElementById('initialLogEntry');
  if (initialLogEntry) {
    initialLogEntry.textContent = `[${formatSystemTime()}] System ready. Waiting for simulation start…`;
  }
}

/* ── Boot ─────────────────────────────────────── */
async function boot() {
  prepareWorkspaceLayout();
  updateBeijingClock();
  window.setInterval(updateBeijingClock, 1000);
  updateLegendVisibility();
  document.getElementById('toggleENC').classList.add('enc-on');
  activeSessionRuntime.subscribe(syncDeploymentRuntime);
  telemetryProjection.subscribe(renderProjection);
  try {
    const runtimeSnapshot = await activeSessionRuntime.bootstrap();
    const existing = runtimeSnapshot.session;
    if (existing) {
      pushLog(`Session restored: ${existing.spec.scenario_id} / ${existing.spec.algorithm_id} / ${existing.spec.tracker_id}`, 'log-info');
    } else {
      setSessionConnectionState('disconnected');
      pushLog('No active session. Assemble and Create one from Config.', 'log-info');
    }
  } catch (error) {
    pushLog(`Initialization failed: ${error.message}`, 'log-danger');
  }
  try {
    const existing = activeSessionRuntime.snapshot().session;
    await populateCatalogs(existing?.spec?.validation_rule_id || 'rule14');
    if (existing) restoreSessionSelection(existing.spec);
  } catch (error) {
    pushLog(`Capability catalog unavailable; Deployment remains active: ${error.message}`, 'log-danger');
  }
}

window.addEventListener('pagehide', () => {
  situationDisplay.destroy();
  activeSessionRuntime.destroy();
}, { once: true });
boot();
