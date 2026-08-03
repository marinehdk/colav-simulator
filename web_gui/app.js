/**
 * Colav-Simulator Web GUI — app.js
 * Canvas rendering, ENC chart overlay, WebSocket telemetry, controls
 */

'use strict';

/* ══════════════════════════════════════════════
   CONSTANTS
══════════════════════════════════════════════ */
const SAFETY_MARGIN_DEFAULT = 150;
const PERF_HISTORY_LEN      = 60;
const DCPA_SAFE  = 300;   // m – green
const DCPA_WARN  = 100;   // m – amber/red
const TCPA_SAFE  = 120;   // s
const TCPA_WARN  = 40;    // s
const FCB45_LENGTH_M = 45;
const FCB45_WIDTH_M = 8;
const MOTION_VECTOR_SECONDS = 60;
const MOTION_TICK_SECONDS = 10;
const PREDICTION_MARKER_SECONDS = 10;
const PREDICTION_LABEL_SECONDS = 60;
const SBMPC_SOLVE_PERIOD_SECONDS = 5;
const RADAR_DETECTION_RANGE_M = 2000;
const SBMPC_RESPONSE_RANGE_M = 1000;
const VO_DECISION_FETCH_INTERVAL_MS = 200;
const TELEMETRY_RENDER_INTERVAL_MS = 100;
const THREAT_STYLES = {
  UNKNOWN: { color: '#4F5B60', fill: 'rgba(104,116,122,0.72)', rank: 0 },
  CLEAR: { color: '#AAB4BA', fill: 'rgba(170,180,186,0.66)', rank: 1 },
  LOW: { color: '#F5A524', fill: 'rgba(245,165,36,0.76)', rank: 2 },
  HIGH: { color: '#FF4D5A', fill: 'rgba(255,77,90,0.82)', rank: 3 },
};

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
  romsdal_busy_water_16: 'Romsdal 繁忙水域 · 16船',
  romsdal_busy_water_80_stress: 'Romsdal 交通压力 · 80船',
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
   ENC STATE
══════════════════════════════════════════════ */
let encInfo   = null;   // {origin_e, origin_n, width, height, utm_zone}
let encImage  = null;   // HTMLImageElement (PNG tile)
let encReady  = false;
let showENC   = true;   // user toggle
const visibleLayers = {
  safeWater: true,
  ships: true,
  corridor: true,
  route: true,
  waypoints: true,
  history: true,
  motionVectors: true,
  radarRange: true,
  responseRange: true,
  prediction: true,
  previousPrediction: false,
  executionPoint: true,
  risk: true,
  truth: false,
  measurements: false,
  tracks: false,
  covariance: false,
};

/* ══════════════════════════════════════════════
   MAP VIEW STATE
══════════════════════════════════════════════ */
let viewScale = 0.45;   // px/m
let panX      = 0;
let panY      = 0;
let isPanning = false;
let lastPanX  = 0, lastPanY = 0;

/* ══════════════════════════════════════════════
   PERF / DATA
══════════════════════════════════════════════ */
const perfHistory = [];
let ws          = null;
let currentData = null;
let logCount    = 0;
let lastColregs = '', lastDcpaLevel = '';
const seenEventKeys = new Set();
let activeSessionId = null;
let activeSessionKey = null;
let resultLoaded = false;
let sessionConnectionState = 'connecting';
let sessionRecoveryPending = false;
let sessionCreationPromise = null;
let pendingSessionKey = null;
let sessionCreateRevision = 0;
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
let renderFromData = null;
let renderToData = null;
let renderStartedAt = 0;
let renderFrameId = null;
const missionRoutes = new Map();
let targetHitRegions = [];
let selectedTargetId = null;
let pointerDown = null;
let busyWaterDocument = null;
let busyWaterBaseScenario = null;
let busyWaterSeed = 20250731;
let busyWaterMix = { crossing: 0.6, head_on: 0.2, overtaking: 0.2 };
let busyWaterRevision = 0;
let routePointEditMode = null;

/* ══════════════════════════════════════════════
   CANVAS SETUP
══════════════════════════════════════════════ */
const canvas  = document.getElementById('simCanvas');
const ctx     = canvas.getContext('2d');
const wrapper = document.getElementById('canvasWrapper');

function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  const w   = wrapper.clientWidth;
  const h   = wrapper.clientHeight;
  canvas.width  = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width  = `${w}px`;
  canvas.style.height = `${h}px`;
  ctx.scale(dpr, dpr);
  if (encInfo && encReady) fitENCView();
  updateScaleBar();
  if (currentData) renderCanvas(currentData);
}

const ro = new ResizeObserver(resizeCanvas);
ro.observe(wrapper);
resizeCanvas();

/* ══════════════════════════════════════════════
   COORDINATE UTILITIES
══════════════════════════════════════════════ */
/** Simulation world [North, East] → canvas pixel */
function worldToCanvas(north, east) {
  const cx = wrapper.clientWidth  / 2 + panX;
  const cy = wrapper.clientHeight / 2 + panY;
  return { x: cx + east * viewScale, y: cy - north * viewScale };
}

function fitENCView() {
  if (!encInfo) {
    viewScale = 0.45;
    panX = 0;
    panY = 0;
    return;
  }
  viewScale = Math.max(
    0.005,
    Math.max(wrapper.clientWidth / encInfo.width, wrapper.clientHeight / encInfo.height),
  );
  panX = -encInfo.width * viewScale / 2;
  panY = encInfo.height * viewScale / 2;
}

/**
 * ENC UTM (Easting, Northing) → canvas pixel.
 * seacharts renders with origin at lower-left; Y axis flipped.
 */
function utmToCanvas(easting, northing) {
  if (!encInfo) return { x: 0, y: 0 };
  // Offset from ENC origin (lower-left corner)
  const de = easting  - encInfo.origin_e;
  const dn = northing - encInfo.origin_n;
  // Sim world uses the ENC origin as (0,0), North = dn, East = de
  return worldToCanvas(dn, de);
}

function canvasToUtm(x, y) {
  if (!encInfo) return null;
  const cx = wrapper.clientWidth / 2 + panX;
  const cy = wrapper.clientHeight / 2 + panY;
  return {
    north: encInfo.origin_n + (cy - y) / viewScale,
    east: encInfo.origin_e + (x - cx) / viewScale,
  };
}

function updateScaleBar() {
  const fixedBarPx = 72;
  const representedM = fixedBarPx / viewScale;
  document.getElementById('scaleBarLabel').textContent = representedM >= 1000
    ? `${(representedM / 1000).toFixed(1)} km`
    : `${Math.round(representedM)} m`;
}

/* ══════════════════════════════════════════════
   ZOOM & PAN
══════════════════════════════════════════════ */
canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.15 : 0.87;
  viewScale = Math.max(0.005, Math.min(5.0, viewScale * factor));
  updateScaleBar();
  if (currentData) renderCanvas(currentData);
}, { passive: false });

canvas.addEventListener('mousedown', e => {
  isPanning = true; lastPanX = e.clientX; lastPanY = e.clientY;
  pointerDown = { x: e.clientX, y: e.clientY };
});
window.addEventListener('mousemove', e => {
  if (!isPanning) return;
  panX += e.clientX - lastPanX; panY += e.clientY - lastPanY;
  lastPanX = e.clientX; lastPanY = e.clientY;
  if (currentData) renderCanvas(currentData);
});
window.addEventListener('mouseup', () => { isPanning = false; });
canvas.addEventListener('click', event => {
  if (pointerDown && Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 4) return;
  const bounds = canvas.getBoundingClientRect();
  const x = event.clientX - bounds.left;
  const y = event.clientY - bounds.top;
  if (routePointEditMode) {
    const point = canvasToUtm(x, y);
    if (!point) return;
    const suffix = routePointEditMode === 'start' ? '1' : '2';
    document.getElementById(`targetRouteN${suffix}`).value = point.north.toFixed(1);
    document.getElementById(`targetRouteE${suffix}`).value = point.east.toFixed(1);
    routePointEditMode = null;
    canvas.classList.remove('route-pick-mode');
    return;
  }
  const hit = [...targetHitRegions].reverse().find(item => Math.hypot(x - item.x, y - item.y) <= item.radius);
  selectedTargetId = hit?.target.id ?? null;
  updateTargetDetails(hit?.target ?? null, currentData);
  if (currentData) renderCanvas(currentData);
});

document.getElementById('targetDetailsClose').addEventListener('click', () => {
  selectedTargetId = null;
  updateTargetDetails(null, currentData);
  if (currentData) renderCanvas(currentData);
});

document.getElementById('zoomIn').addEventListener('click', () => {
  viewScale = Math.min(5.0, viewScale * 1.25); updateScaleBar();
  if (currentData) renderCanvas(currentData);
});
document.getElementById('zoomOut').addEventListener('click', () => {
  viewScale = Math.max(0.005, viewScale / 1.25); updateScaleBar();
  if (currentData) renderCanvas(currentData);
});
document.getElementById('zoomReset').addEventListener('click', () => {
  fitENCView(); updateScaleBar();
  if (currentData) renderCanvas(currentData);
});
document.getElementById('toggleENC').addEventListener('click', function () {
  showENC = !showENC;
  this.classList.toggle('enc-on', showENC);
  this.setAttribute('aria-pressed', showENC);
  if (currentData) renderCanvas(currentData);
});
document.querySelectorAll('[data-layer]').forEach(input => {
  input.addEventListener('change', () => {
    visibleLayers[input.dataset.layer] = input.checked;
    updateLegendVisibility();
    if (currentData) renderCanvas(currentData);
  });
});

/* ══════════════════════════════════════════════
   ENC INITIALISATION
══════════════════════════════════════════════ */
async function initENC() {
  setEncStatus('loading');
  try {
    const res  = await fetch('/api/enc_info');
    const info = await res.json();

    if (!info.ready) {
      // Poll every 5 s until ENC is ready
      setTimeout(initENC, 5000);
      return;
    }

    encInfo = info;

    // Load PNG tile
    const img = new Image();
    img.onload = () => {
      encImage = img;
      encReady = true;
      fitENCView();
      updateScaleBar();
      setEncStatus('ready');
      document.getElementById('toggleENC').classList.add('enc-on');
      pushLog(`ENC chart loaded — UTM${info.utm_zone} origin (${info.origin_e.toFixed(0)}, ${info.origin_n.toFixed(0)})`, 'log-ok');
      if (currentData) renderCanvas(currentData);
    };
    img.onerror = () => {
      setEncStatus('error');
      pushLog('ENC PNG tile failed to load.', 'log-danger');
    };
    img.src = `/api/enc_tile?t=${Date.now()}`;  // cache-bust

  } catch (e) {
    setTimeout(initENC, 8000);
  }
}

function setEncStatus(state) {
  const badge = document.getElementById('encStatusBadge');
  if (!badge) return;
  const labels = { loading: '加载中', ready: '已加载', error: '加载失败' };
  badge.textContent = labels[state] || labels.loading;
  badge.classList.toggle('ready', state === 'ready');
  badge.classList.toggle('error', state === 'error');
}

/* ══════════════════════════════════════════════
   RENDERING
══════════════════════════════════════════════ */
function renderCanvas(data) {
  const W = wrapper.clientWidth;
  const H = wrapper.clientHeight;
  ctx.clearRect(0, 0, W, H);
  targetHitRegions = [];

  ctx.fillStyle = '#101615';
  ctx.fillRect(0, 0, W, H);
  if (showENC && encReady && encImage && encInfo) drawENCTile(W, H);
  if (!encReady || !showENC) drawGrid(W, H);

  const route = frozenMissionRoute(data);
  const navigationArea = data.enc_navigation_area || data.navigation_area;
  updateLayerAvailability(data, navigationArea, route);

  if (visibleLayers.safeWater) drawNavigationArea(navigationArea);
  if (visibleLayers.corridor) drawRouteCorridor(route, Number(data.route_corridor_half_width_m));
  if (visibleLayers.route) drawInitialRoute(route);
  if (visibleLayers.waypoints) drawWaypoints(route, data.os);
  if (visibleLayers.history) drawHistory(data);
  if (visibleLayers.measurements) drawMeasurements(data.measurements?.[0]);
  if (visibleLayers.tracks && !denseTrafficMode(data)) drawTracks(data.tracks?.[0]);
  if (visibleLayers.motionVectors) drawMotionVectors(data);
  drawDetectionZones(data);

  const plans = data.plans || {};
  if (visibleLayers.previousPrediction && plans.previous_prediction_horizon?.length > 0)
    drawHorizon(plans.previous_prediction_horizon, true, data.planner);
  (plans.target_prediction_horizons || []).forEach((horizon, index) =>
    drawTargetHorizon(horizon, targetThreat(data, data.obstacles?.[index])));
  if (visibleLayers.prediction && plans.prediction_horizon?.length > 0)
    drawHorizon(plans.prediction_horizon, false, data.planner);
  if (visibleLayers.executionPoint && plans.prediction_horizon?.length > 0)
    drawExecutionPoint(plans.prediction_horizon);
  if (visibleLayers.risk) drawCPARisk(data);
  drawTargetRoutes(data);
  if (visibleLayers.ships) drawShips(data);
  if (data.os) drawRelativeCompass(data.os, W, H);
}

function drawTargetRoutes(data) {
  const routes = data.target_routes || data.plans?.target_routes || [];
  const scenarioId = data.scenario_id || document.getElementById('scenarioSelect').value;
  if (!routes.length || !isBusyWaterScenario(scenarioId)) return;
  routes.forEach(route => {
    const north = route.waypoints?.[0] || [];
    const east = route.waypoints?.[1] || [];
    if (north.length < 2 || east.length < 2) return;
    const selected = String(route.target_id) === String(selectedTargetId);
    const first = worldToCanvas(north[0], east[0]);
    const second = worldToCanvas(north[1], east[1]);
    ctx.save();
    ctx.strokeStyle = selected ? '#62D2BD' : 'rgba(255,255,255,0.24)';
    ctx.lineWidth = selected ? 2 : 1;
    ctx.setLineDash(selected ? [] : [5, 5]);
    ctx.beginPath();
    ctx.moveTo(first.x, first.y);
    ctx.lineTo(second.x, second.y);
    ctx.stroke();
    ctx.fillStyle = selected ? '#62D2BD' : 'rgba(255,255,255,0.55)';
    [first, second].forEach(point => {
      ctx.beginPath();
      ctx.arc(point.x, point.y, selected ? 4 : 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  });
}

function interpolateAngle(from, to, amount) {
  if (!Number.isFinite(from) || !Number.isFinite(to)) return to;
  const delta = Math.atan2(Math.sin(to - from), Math.cos(to - from));
  return from + delta * amount;
}

function interpolateVessel(from, to, amount) {
  if (!from || !to) return to;
  return {
    ...to,
    x: Number.isFinite(from.x) && Number.isFinite(to.x) ? from.x + (to.x - from.x) * amount : to.x,
    y: Number.isFinite(from.y) && Number.isFinite(to.y) ? from.y + (to.y - from.y) * amount : to.y,
    psi: interpolateAngle(from.psi, to.psi, amount),
    cog: interpolateAngle(from.cog, to.cog, amount),
  };
}

function interpolateVesselList(fromList, toList, amount) {
  const previous = new Map((fromList || []).map(item => [String(item.id), item]));
  return (toList || []).map(item => interpolateVessel(previous.get(String(item.id)), item, amount));
}

function interpolateTelemetry(from, to, amount) {
  if (!from || !to || from.run_id !== to.run_id) return to;
  return {
    ...to,
    os: interpolateVessel(from.os, to.os, amount),
    obstacles: interpolateVesselList(from.obstacles, to.obstacles, amount),
    truth: interpolateVesselList(from.truth, to.truth, amount),
  };
}

function renderTelemetryFrame(timestamp) {
  if (!renderToData) {
    renderFrameId = null;
    return;
  }
  const amount = renderFromData === renderToData
    ? 1
    : Math.min(1, Math.max(0, (timestamp - renderStartedAt) / TELEMETRY_RENDER_INTERVAL_MS));
  renderCanvas(interpolateTelemetry(renderFromData, renderToData, amount));
  if (amount < 1 && renderToData.state === 'RUNNING') {
    renderFrameId = requestAnimationFrame(renderTelemetryFrame);
  } else {
    renderFromData = renderToData;
    renderFrameId = null;
  }
}

function queueTelemetryRender(data) {
  const now = performance.now();
  if (!renderToData || renderToData.run_id !== data.run_id) {
    renderFromData = data;
    renderToData = data;
  } else {
    const amount = Math.min(1, Math.max(0, (now - renderStartedAt) / TELEMETRY_RENDER_INTERVAL_MS));
    renderFromData = interpolateTelemetry(renderFromData, renderToData, amount);
    renderToData = data;
  }
  renderStartedAt = now;
  if (renderFrameId === null) renderFrameId = requestAnimationFrame(renderTelemetryFrame);
}

/* ENC tile — mapped from UTM to canvas space */
function drawENCTile(W, H) {
  if (!encInfo || !encImage) return;

  // The ENC image covers encInfo.width × encInfo.height metres (East × North).
  // Sim origin is always (0,0) in North-East which corresponds to
  // UTM (origin_e, origin_n) — i.e. lower-left corner of the ENC tile.
  // Canvas Y is flipped (North is up on canvas).

  const tilePxW = encInfo.width  * viewScale;
  const tilePxH = encInfo.height * viewScale;

  // Lower-left of the ENC tile in canvas space:
  // North=0, East=0  → worldToCanvas(0,0)
  const llPt = worldToCanvas(0, 0);

  // Because seacharts PNG has (0,0) = lower-left (North=0), and canvas Y
  // increases downward, we draw from upper-left canvas corner:
  const drawX = llPt.x;
  const drawY = llPt.y - tilePxH;   // upper-left = lower-left minus tile height

  ctx.save();
  ctx.globalAlpha = 0.92;
  ctx.drawImage(encImage, drawX, drawY, tilePxW, tilePxH);
  ctx.globalAlpha = 1.0;
  ctx.restore();
}

/* Grid lines */
function drawGrid(W, H) {
  const gridWorld = chooseGridSpacing();
  const gridPx    = gridWorld * viewScale;
  const cx = W / 2 + panX, cy = H / 2 + panY;

  ctx.strokeStyle = 'rgba(255,255,255,0.035)';
  ctx.lineWidth   = 1;

  const x0 = Math.floor(-cx / gridPx), x1 = Math.ceil((W - cx) / gridPx);
  for (let i = x0; i <= x1; i++) {
    const x = cx + i * gridPx;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  const y0 = Math.floor(-cy / gridPx), y1 = Math.ceil((H - cy) / gridPx);
  for (let i = y0; i <= y1; i++) {
    const y = cy + i * gridPx;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
}

function chooseGridSpacing() {
  const worldW = wrapper.clientWidth / viewScale;
  const raw    = worldW / 10;
  const mag    = Math.pow(10, Math.floor(Math.log10(raw)));
  const opts   = [1, 2, 5, 10].map(f => f * mag);
  return opts.find(v => worldW / v <= 20) || opts[opts.length - 1];
}

function frozenMissionRoute(data) {
  const key = data.run_id || data.selected_scenario || 'unbound';
  if (!missionRoutes.has(key) && validRoute(data.waypoints)) {
    missionRoutes.set(key, data.waypoints.map(axis => [...axis]));
  }
  return missionRoutes.get(key) || [[], []];
}

function validRoute(route) {
  return Array.isArray(route) && route.length >= 2
    && Array.isArray(route[0]) && route[0].length >= 2
    && route[0].length === route[1]?.length;
}

function routePoints(route) {
  if (!validRoute(route)) return [];
  return route[0].map((north, index) => worldToCanvas(north, route[1][index]));
}

function drawNavigationArea(area) {
  const safeWater = area?.safe_water?.polygons || area?.safe_water || area?.safe_water_polygons;
  drawPolygonCollection(safeWater, 'rgba(76,202,209,0.12)', 'rgba(76,202,209,0.55)');
}

function drawPolygonCollection(collection, fill, stroke) {
  const polygons = normalizePolygons(collection);
  polygons.forEach(polygon => {
    const rings = Array.isArray(polygon[0]?.[0]) ? polygon : [polygon];
    ctx.beginPath();
    rings.forEach(ring => {
      ring.forEach((coordinate, index) => {
        const point = worldToCanvas(Number(coordinate[0]), Number(coordinate[1]));
        index === 0 ? ctx.moveTo(point.x, point.y) : ctx.lineTo(point.x, point.y);
      });
      ctx.closePath();
    });
    ctx.fillStyle = fill;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1;
    ctx.fill('evenodd');
    ctx.stroke();
  });
}

function normalizePolygons(value) {
  if (!value) return [];
  if (value.type === 'FeatureCollection') return value.features.flatMap(feature => normalizePolygons(feature.geometry));
  if (value.type === 'Feature') return normalizePolygons(value.geometry);
  if (value.type === 'Polygon') return [value.coordinates];
  if (value.type === 'MultiPolygon') return value.coordinates;
  if (!Array.isArray(value) || value.length === 0) return [];
  const depth = arrayDepth(value);
  if (depth === 2) return [value];
  if (depth === 3) return [value];
  return value;
}

function arrayDepth(value) {
  let depth = 0;
  let cursor = value;
  while (Array.isArray(cursor)) {
    depth += 1;
    cursor = cursor[0];
  }
  return depth;
}

function drawRouteCorridor(route, halfWidthM) {
  if (!validRoute(route) || !Number.isFinite(halfWidthM) || halfWidthM <= 0) return;
  const points = routePoints(route);
  ctx.save();
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(76,202,209,0.14)';
  ctx.lineWidth = Math.max(2, halfWidthM * 2 * viewScale);
  strokePolyline(points);
  const offsets = offsetPolyline(route, halfWidthM);
  ctx.strokeStyle = 'rgba(76,202,209,0.52)';
  ctx.lineWidth = 1;
  offsets.forEach(line => strokePolyline(line.map(point => worldToCanvas(point[0], point[1]))));
  ctx.restore();
}

function offsetPolyline(route, distance) {
  const source = route[0].map((north, index) => [north, route[1][index]]);
  const offset = sign => source.map((point, index) => {
    const previous = source[Math.max(0, index - 1)];
    const next = source[Math.min(source.length - 1, index + 1)];
    const dn = next[0] - previous[0];
    const de = next[1] - previous[1];
    const length = Math.hypot(dn, de) || 1;
    return [point[0] - sign * de / length * distance, point[1] + sign * dn / length * distance];
  });
  return [offset(-1), offset(1)];
}

function drawInitialRoute(route) {
  const points = routePoints(route);
  if (points.length < 2) return;
  ctx.save();
  ctx.strokeStyle = '#F4D34E';
  ctx.lineWidth = 2;
  ctx.setLineDash([10, 8]);
  strokePolyline(points);
  ctx.restore();
}

function drawWaypoints(route, os) {
  const points = routePoints(route);
  if (!points.length) return;
  const current = currentWaypointIndex(route, os);
  points.forEach((point, index) => {
    const passed = index < current;
    const active = index === current;
    ctx.strokeStyle = passed ? '#7F898D' : '#F4D34E';
    ctx.fillStyle = active ? 'rgba(244,211,78,0.28)' : 'rgba(10,16,15,0.70)';
    ctx.lineWidth = active ? 2.5 : 1.5;
    ctx.beginPath();
    ctx.arc(point.x, point.y, active ? 7 : 5, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
    drawMapLabel(`WPT${index + 1}`, point.x + 9, point.y - 7, passed ? '#9AA3A7' : '#F4D34E');
  });
}

function currentWaypointIndex(route, os) {
  if (!os || !validRoute(route)) return 0;
  const distances = route[0].map((north, index) => Math.hypot(north - os.x, route[1][index] - os.y));
  const nearest = distances.indexOf(Math.min(...distances));
  return distances[nearest] < 20 ? Math.min(nearest + 1, distances.length - 1) : nearest;
}

function strokePolyline(points) {
  if (points.length < 2) return;
  ctx.beginPath();
  points.forEach((point, index) =>
    index === 0 ? ctx.moveTo(point.x, point.y) : ctx.lineTo(point.x, point.y));
  ctx.stroke();
}

function drawHistory(data) {
  drawFadingTrail(data.os?.trajectory, '#FFFFFF');
  if (data.executed_tracker === 'god') {
    (data.obstacles || []).forEach(target => {
      if (denseTrafficMode(data) && targetThreat(data, target).rank < 3 && target.id !== selectedTargetId) return;
      drawFadingTrail(target.trajectory, targetThreat(data, target).color);
    });
  }
}

function drawFadingTrail(trajectory, color) {
  if (!Array.isArray(trajectory) || trajectory.length < 2) return;
  const recent = trajectory.slice(-500);
  for (let index = 1; index < recent.length; index++) {
    const start = worldToCanvas(recent[index - 1][0], recent[index - 1][1]);
    const end = worldToCanvas(recent[index][0], recent[index][1]);
    ctx.strokeStyle = hexToRgba(color, 0.08 + 0.52 * index / recent.length);
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
  }
}

function drawMeasurements(sensorGroups) {
  if (!Array.isArray(sensorGroups) || !encInfo) return;
  sensorGroups.filter(Array.isArray).flat().forEach(measurement => {
    if (!Array.isArray(measurement) || !Array.isArray(measurement[1])) return;
    const value = measurement[1];
    if (value.length < 2 || !Number.isFinite(value[0]) || !Number.isFinite(value[1])) return;
    const point = worldToCanvas(value[0] - encInfo.origin_n, value[1] - encInfo.origin_e);
    ctx.strokeStyle = measurement[0] === -1 ? '#ff6f61' : '#f3b33d';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(point.x - 4, point.y);
    ctx.lineTo(point.x + 4, point.y);
    ctx.moveTo(point.x, point.y - 4);
    ctx.lineTo(point.x, point.y + 4);
    ctx.stroke();
  });
}

function drawTracks(trackSet) {
  if (!trackSet || !Array.isArray(trackSet.states)) return;
  trackSet.states.forEach((state, index) => {
    if (!Array.isArray(state) || state.length < 2) return;
    const point = worldToCanvas(state[0], state[1]);
    if (visibleLayers.covariance) {
      drawCovariance(point, trackSet.covariances?.[index]);
    }
    ctx.fillStyle = '#37c995';
    ctx.beginPath();
    ctx.arc(point.x, point.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#c9f3e3';
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.fillText(`T${trackSet.labels?.[index] ?? index}`, point.x + 6, point.y - 6);
  });
}

function drawCovariance(point, covariance) {
  if (!Array.isArray(covariance) || covariance.length < 2) return;
  const varN = Number(covariance[0]?.[0]);
  const varE = Number(covariance[1]?.[1]);
  const covNE = Number(covariance[0]?.[1]);
  if (![varN, varE, covNE].every(Number.isFinite)) return;
  const a = Math.max(varE, 0);
  const d = Math.max(varN, 0);
  const b = -covNE;
  const root = Math.sqrt(Math.max(0, ((a - d) / 2) ** 2 + b ** 2));
  const major = Math.max((a + d) / 2 + root, 0);
  const minor = Math.max((a + d) / 2 - root, 0);
  const angle = 0.5 * Math.atan2(2 * b, a - d);
  ctx.save();
  ctx.translate(point.x, point.y);
  ctx.rotate(angle);
  ctx.strokeStyle = 'rgba(55,201,149,0.65)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(
    0,
    0,
    Math.max(3, 2 * Math.sqrt(major) * viewScale),
    Math.max(3, 2 * Math.sqrt(minor) * viewScale),
    0,
    0,
    Math.PI * 2,
  );
  ctx.stroke();
  ctx.restore();
}

/* Planner prediction horizon */
function drawHorizon(horizon, previous = false, planner = {}) {
  const pts = horizon.map(p => worldToCanvas(p[0], p[1]));
  ctx.strokeStyle = previous ? 'rgba(85,214,183,0.20)' : '#55D6B7';
  ctx.lineWidth   = previous ? 1.5 : 2.5;
  ctx.setLineDash(previous ? [6, 6] : []);
  strokePolyline(pts);
  ctx.setLineDash([]);
  if (previous) return;
  const dt = Number(planner?.horizon_dt_s);
  if (!Number.isFinite(dt) || dt <= 0) return;
  const markerInterval = Math.max(1, Math.round(PREDICTION_MARKER_SECONDS / dt));
  const labelInterval = Math.max(1, Math.round(PREDICTION_LABEL_SECONDS / dt));
  pts.forEach((point, index) => {
    if (index === 0 || index % markerInterval !== 0) return;
    const keyPoint = index % labelInterval === 0;
    ctx.fillStyle = keyPoint ? '#9EF0DB' : 'rgba(11,18,17,0.72)';
    ctx.strokeStyle = keyPoint ? '#D2FFF3' : 'rgba(85,214,183,0.92)';
    ctx.lineWidth = keyPoint ? 1.5 : 1.1;
    ctx.beginPath();
    ctx.arc(point.x, point.y, keyPoint ? 4 : 2.4, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
    if (!keyPoint) return;
    drawMapLabel(`${Math.round(index * dt)}s`, point.x + 5, point.y - 5, '#9EF0DB');
  });
}

function drawTargetHorizon(horizon, threat = THREAT_STYLES.UNKNOWN) {
  if (!Array.isArray(horizon) || horizon.length < 2) return;
  const pts = horizon.map(p => worldToCanvas(p[0], p[1]));
  ctx.strokeStyle = hexToRgba(threat.color, 0.6);
  ctx.lineWidth = 1.5;
  ctx.setLineDash([5, 5]);
  strokePolyline(pts);
  ctx.setLineDash([]);
}

function drawExecutionPoint(horizon) {
  const index = horizon.length > 1 ? 1 : 0;
  const point = worldToCanvas(horizon[index][0], horizon[index][1]);
  ctx.save();
  ctx.translate(point.x, point.y);
  ctx.rotate(Math.PI / 4);
  ctx.fillStyle = '#55D6B7';
  ctx.strokeStyle = '#0B0F0E';
  ctx.lineWidth = 1.5;
  ctx.fillRect(-5, -5, 10, 10);
  ctx.strokeRect(-5, -5, 10, 10);
  ctx.restore();
}

function drawMotionVectors(data) {
  if (data.os) drawMotionVector(data.os, '#FFFFFF', false);
  targetsForDisplay(data).forEach(target => {
    const threat = targetThreat(data, target);
    if (denseTrafficMode(data) && threat.rank < 3 && target.id !== selectedTargetId) return;
    drawMotionVector(target, threat.color, true);
  });
}

function denseTrafficMode(data) {
  return Math.max(data.obstacles?.length || 0, data.tracks?.[0]?.states?.length || 0) >= 40;
}

function drawMotionVector(ship, color, dashed) {
  const speed = Number.isFinite(ship.sog) ? ship.sog : Math.hypot(ship.u || 0, ship.v || 0);
  const course = Number.isFinite(ship.cog) ? ship.cog : ship.psi;
  if (![ship.x, ship.y, speed, course].every(Number.isFinite) || speed < 0.01) return;
  const start = worldToCanvas(ship.x, ship.y);
  const end = worldToCanvas(
    ship.x + Math.cos(course) * speed * MOTION_VECTOR_SECONDS,
    ship.y + Math.sin(course) * speed * MOTION_VECTOR_SECONDS,
  );
  ctx.save();
  ctx.strokeStyle = hexToRgba(color, 0.85);
  ctx.fillStyle = color;
  ctx.lineWidth = 1.8;
  ctx.setLineDash(dashed ? [7, 5] : []);
  ctx.beginPath();
  ctx.moveTo(start.x, start.y);
  ctx.lineTo(end.x, end.y);
  ctx.stroke();
  ctx.setLineDash([]);
  for (let seconds = MOTION_TICK_SECONDS; seconds <= MOTION_VECTOR_SECONDS; seconds += MOTION_TICK_SECONDS) {
    const ratio = seconds / MOTION_VECTOR_SECONDS;
    const point = { x: start.x + (end.x - start.x) * ratio, y: start.y + (end.y - start.y) * ratio };
    const length = Math.hypot(end.x - start.x, end.y - start.y) || 1;
    const nx = -(end.y - start.y) / length;
    const ny = (end.x - start.x) / length;
    ctx.beginPath();
    ctx.moveTo(point.x - nx * 3, point.y - ny * 3);
    ctx.lineTo(point.x + nx * 3, point.y + ny * 3);
    ctx.stroke();
  }
  drawArrowHead(end, course, color);
  ctx.restore();
}

function drawArrowHead(point, heading, color) {
  ctx.save();
  ctx.translate(point.x, point.y);
  ctx.rotate(heading);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(0, -7);
  ctx.lineTo(4, 2);
  ctx.lineTo(-4, 2);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function targetsForDisplay(data) {
  const obstacles = data.obstacles || [];
  const trackSet = data.tracks?.[0];
  if (trackSet?.states?.length) {
    return trackSet.states.map((state, index) => {
      const truth = obstacles[index] || {};
      const velocityNorth = Number(state[2]);
      const velocityEast = Number(state[3]);
      const speed = Math.hypot(velocityNorth, velocityEast);
      const course = Math.atan2(velocityEast, velocityNorth);
      return {
        ...truth,
        id: trackSet.labels?.[index] ?? truth.id ?? index + 1,
        x: Number(state[0]),
        y: Number(state[1]),
        psi: Number.isFinite(course) ? course : truth.psi,
        cog: Number.isFinite(course) ? course : truth.cog,
        sog: Number.isFinite(speed) ? speed : truth.sog,
        source: 'tracker',
      };
    }).filter(target => Number.isFinite(target.x) && Number.isFinite(target.y));
  }
  return data.executed_tracker === 'god' ? obstacles : [];
}

function targetThreat(data, target) {
  if (!target || !data.os) return THREAT_STYLES.UNKNOWN;
  const distance = Math.hypot(target.x - data.os.x, target.y - data.os.y);
  const responseRange = plannerResponseRange(data);
  if (responseRange?.threatActivation && distance <= responseRange.distanceM) return THREAT_STYLES.HIGH;
  if (distance <= RADAR_DETECTION_RANGE_M) return THREAT_STYLES.LOW;
  return THREAT_STYLES.CLEAR;
}

function encounterForTarget(data, targetId) {
  return (data.encounters || []).find(item => String(item.target_id) === String(targetId))
    || ((data.encounters || []).length === 1 ? data.encounters[0] : null);
}

function drawShips(data) {
  const targets = targetsForDisplay(data);
  const dense = denseTrafficMode(data);
  const labels = [];
  targets.forEach(target => {
    const threat = targetThreat(data, target);
    const point = worldToCanvas(target.x, target.y);
    if (threat.rank >= 2) drawThreatRings(point, threat, target.id === selectedTargetId);
    const compact = dense && threat.rank < 3 && target.id !== selectedTargetId;
    drawHull(point, target.psi, target.length || 30, target.width || 7, threat, false, compact);
    targetHitRegions.push({ x: point.x, y: point.y, radius: 14, target });
    if ((!dense && threat.rank >= 2) || threat.rank >= 3 || target.id === selectedTargetId) {
      labels.push({ text: `TS${target.id}`, point, color: threat.color });
    }
  });
  if (visibleLayers.truth && data.executed_tracker !== 'god') {
    (data.obstacles || []).forEach(target => {
      const point = worldToCanvas(target.x, target.y);
      drawTruthOutline(point, target.psi, target.length || 30, target.width || 7);
    });
  }
  if (data.os) {
    const point = worldToCanvas(data.os.x, data.os.y);
    drawHull(point, data.os.psi, FCB45_LENGTH_M, FCB45_WIDTH_M, null, true);
    labels.push({ text: 'OS', point, color: '#FFFFFF' });
  }
  drawAvoidingLabels(labels);
}

function drawHull(point, heading, lengthM, widthM, threat, ownship, compact = false) {
  const lengthPx = Math.max(ownship ? 18 : compact ? 7 : 22, lengthM * viewScale);
  const widthPx = Math.max(ownship ? 4 : 5, lengthPx * widthM / lengthM);
  ctx.save();
  ctx.translate(point.x, point.y);
  ctx.rotate(Number.isFinite(heading) ? heading : 0);
  const path = new Path2D();
  path.moveTo(0, -lengthPx / 2);
  path.bezierCurveTo(widthPx * 0.34, -lengthPx * 0.40, widthPx / 2, -lengthPx * 0.18, widthPx / 2, lengthPx * 0.38);
  path.lineTo(widthPx * 0.42, lengthPx / 2);
  path.lineTo(-widthPx * 0.42, lengthPx / 2);
  path.lineTo(-widthPx / 2, lengthPx * 0.38);
  path.bezierCurveTo(-widthPx / 2, -lengthPx * 0.18, -widthPx * 0.34, -lengthPx * 0.40, 0, -lengthPx / 2);
  path.closePath();
  ctx.fillStyle = ownship ? '#F7FAFA' : threat.fill;
  ctx.strokeStyle = ownship ? '#111817' : threat.color;
  ctx.lineWidth = ownship ? 1.5 : 2;
  ctx.fill(path);
  ctx.stroke(path);
  ctx.strokeStyle = ownship ? '#65706F' : hexToRgba(threat.color, 0.75);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, -lengthPx * 0.36);
  ctx.lineTo(0, lengthPx * 0.35);
  ctx.stroke();
  if (ownship) {
    ctx.fillStyle = '#75817F';
    ctx.fillRect(-widthPx * 0.34, -lengthPx * 0.04, widthPx * 0.68, lengthPx * 0.10);
  }
  ctx.restore();
}

function drawTruthOutline(point, heading, lengthM, widthM) {
  const lengthPx = Math.max(12, lengthM * viewScale);
  const widthPx = Math.max(2.5, lengthPx * widthM / lengthM);
  ctx.save();
  ctx.translate(point.x, point.y);
  ctx.rotate(Number.isFinite(heading) ? heading : 0);
  ctx.strokeStyle = 'rgba(207,112,255,0.65)';
  ctx.setLineDash([3, 3]);
  ctx.strokeRect(-widthPx / 2, -lengthPx / 2, widthPx, lengthPx);
  ctx.restore();
}

function drawThreatRings(point, threat, selected) {
  const radii = threat === THREAT_STYLES.HIGH ? [22, 31] : [23];
  radii.forEach((radius, index) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.strokeStyle = hexToRgba(threat.color, selected ? 0.9 : 0.45 - index * 0.12);
    ctx.lineWidth = selected ? 2 : 1.2;
    ctx.setLineDash(threat === THREAT_STYLES.LOW ? [5, 4] : []);
    ctx.stroke();
  });
  ctx.setLineDash([]);
}

function drawCPARisk(data) {
  const ranked = (data.encounters || [])
    .map(encounter => ({ encounter, threat: THREAT_STYLES[String(encounter.threat_level || 'UNKNOWN').toUpperCase()] }))
    .filter(item => item.threat?.rank >= 2)
    .sort((a, b) => b.threat.rank - a.threat.rank);
  const item = ranked.find(entry => String(entry.encounter.target_id) === String(selectedTargetId)) || ranked[0];
  if (!item) return;
  const own = cpaPoint(item.encounter.own_cpa_position);
  const target = cpaPoint(item.encounter.target_cpa_position);
  if (!own || !target) return;
  const ownPoint = worldToCanvas(own[0], own[1]);
  const targetPoint = worldToCanvas(target[0], target[1]);
  ctx.strokeStyle = hexToRgba(item.threat.color, 0.9);
  ctx.lineWidth = 1.7;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(ownPoint.x, ownPoint.y);
  ctx.lineTo(targetPoint.x, targetPoint.y);
  ctx.stroke();
  ctx.setLineDash([]);
  [ownPoint, targetPoint].forEach(point => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = item.threat.color;
    ctx.fill();
  });
  drawMapLabel(`CPA ${formatDistance(item.encounter.dcpa_m)}`,
    (ownPoint.x + targetPoint.x) / 2 + 6, (ownPoint.y + targetPoint.y) / 2 - 6, item.threat.color);
}

function drawDetectionZones(data) {
  if (!data.os) return;
  const center = worldToCanvas(data.os.x, data.os.y);
  ctx.save();
  if (visibleLayers.radarRange) {
    ctx.beginPath();
    ctx.arc(center.x, center.y, RADAR_DETECTION_RANGE_M * viewScale, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(245,165,36,0.72)';
    ctx.lineWidth = 1.4;
    ctx.setLineDash([12, 8]);
    ctx.stroke();
  }

  const responseRange = plannerResponseRange(data);
  if (visibleLayers.responseRange && responseRange) {
    ctx.beginPath();
    ctx.arc(center.x, center.y, responseRange.distanceM * viewScale, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,77,90,0.82)';
    ctx.lineWidth = 1.7;
    ctx.setLineDash([8, 6]);
    ctx.stroke();
  }
  ctx.restore();
}

function plannerResponseRange(data) {
  const planner = data.latest_planner_solve?.solver_executed
    ? data.latest_planner_solve
    : (data.planner || {});
  const algorithmId = planner.algorithm_id || data.executed_algorithm || data.requested_algorithm;
  if (algorithmId === 'sbmpc') {
    const configuredRange = Number(planner.constraints?.activation_distance_m);
    const distanceM = Number.isFinite(configuredRange) && configuredRange > 0
      ? configuredRange
      : SBMPC_RESPONSE_RANGE_M;
    return {
      distanceM,
      label: `避碰响应圈（${(distanceM / 1000).toFixed(1)} km）`,
      threatActivation: true,
    };
  }
  if (['potocnik_simplified_mpc', 'potocnik_colreg_fan_mpc'].includes(algorithmId)) {
    const distanceM = Number(planner.constraints?.planning_zone?.distance_m);
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

function cpaPoint(value) {
  if (Array.isArray(value) && value.length >= 2 && value.slice(0, 2).every(Number.isFinite)) return value;
  if (value && Number.isFinite(value.north) && Number.isFinite(value.east)) return [value.north, value.east];
  if (value && Number.isFinite(value.x) && Number.isFinite(value.y)) return [value.x, value.y];
  return null;
}

function drawRelativeCompass(os, W, H) {
  if (!Number.isFinite(os.psi)) return;
  const mobile = W <= 520;
  const center = mobile ? { x: W - 58, y: 150 } : worldToCanvas(os.x, os.y);
  const radius = mobile ? 42 : 110;
  ctx.save();
  ctx.strokeStyle = 'rgba(223,244,242,0.22)';
  ctx.fillStyle = 'rgba(9,15,14,0.13)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  for (let bearing = 0; bearing < 360; bearing += 10) {
    const relative = bearing * Math.PI / 180;
    const angle = relative + os.psi - Math.PI / 2;
    const major = bearing % 20 === 0;
    const outer = radius;
    const inner = radius - (major ? 8 : 4);
    ctx.beginPath();
    ctx.moveTo(center.x + Math.cos(angle) * inner, center.y + Math.sin(angle) * inner);
    ctx.lineTo(center.x + Math.cos(angle) * outer, center.y + Math.sin(angle) * outer);
    ctx.stroke();
    if (major && (!mobile || bearing % 40 === 0)) {
      ctx.fillStyle = 'rgba(235,250,248,0.62)';
      ctx.font = `${mobile ? 8 : 9}px JetBrains Mono, monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const labelRadius = radius - (mobile ? 12 : 15);
      ctx.fillText(String(bearing), center.x + Math.cos(angle) * labelRadius, center.y + Math.sin(angle) * labelRadius);
    }
  }
  const bowAngle = os.psi - Math.PI / 2;
  ctx.strokeStyle = 'rgba(255,255,255,0.72)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(center.x, center.y);
  ctx.lineTo(center.x + Math.cos(bowAngle) * radius, center.y + Math.sin(bowAngle) * radius);
  ctx.stroke();
  ctx.restore();
}

function drawAvoidingLabels(labels) {
  const boxes = [];
  labels.forEach(label => {
    let x = label.point.x + 12;
    let y = label.point.y - 10;
    const width = ctx.measureText(label.text).width + 10;
    const height = 18;
    for (let attempt = 0; attempt < 6; attempt++) {
      const box = { x, y: y - height + 4, width, height };
      if (!boxes.some(other => rectanglesOverlap(box, other))) {
        boxes.push(box);
        drawMapLabel(label.text, x, y, label.color);
        return;
      }
      y += height + 3;
    }
  });
}

function rectanglesOverlap(a, b) {
  return a.x < b.x + b.width && a.x + a.width > b.x
    && a.y < b.y + b.height && a.y + a.height > b.y;
}

function drawMapLabel(text, x, y, color) {
  ctx.font = '10px JetBrains Mono, monospace';
  const width = ctx.measureText(text).width;
  ctx.fillStyle = 'rgba(8,13,12,0.78)';
  ctx.fillRect(x - 3, y - 11, width + 6, 15);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

function updateLayerAvailability(data, navigationArea, route) {
  setLayerAvailability('safeWater', normalizePolygons(
    navigationArea?.safe_water?.polygons || navigationArea?.safe_water || navigationArea?.safe_water_polygons,
  ).length > 0);
  setLayerAvailability('corridor', validRoute(route)
    && Number.isFinite(Number(data.route_corridor_half_width_m))
    && Number(data.route_corridor_half_width_m) > 0);
  setLayerAvailability('radarRange', true);
  const responseRange = plannerResponseRange(data);
  setText('response-range-control-label', responseRange?.label || '规划/响应范围');
  setText('response-range-legend-label', responseRange?.label || '规划/响应范围');
  setLayerAvailability('responseRange', Boolean(responseRange));
}

function setLayerAvailability(layer, available) {
  const input = document.querySelector(`[data-layer="${layer}"]`);
  const state = document.querySelector(`[data-layer-state="${layer}"]`);
  if (input) {
    const wasDisabled = input.disabled;
    input.disabled = !available;
    if (!available) input.checked = false;
    if (available && wasDisabled) input.checked = true;
    visibleLayers[layer] = input.checked;
  }
  if (state) {
    state.textContent = available ? '可用' : '数据未提供';
    state.classList.toggle('available', available);
  }
  updateLegendVisibility();
}

function updateLegendVisibility() {
  document.querySelectorAll('[data-legend-layer]').forEach(item => {
    item.hidden = visibleLayers[item.dataset.legendLayer] === false;
  });
  document.querySelectorAll('[data-legend-group]').forEach(group => {
    group.hidden = !group.querySelector('[data-legend-layer]:not([hidden])');
  });
}

function updateTargetDetails(target, data) {
  const panel = document.getElementById('targetDetails');
  const form = document.getElementById('targetEditForm');
  if (!target) {
    panel.hidden = true;
    form.hidden = true;
    return;
  }
  const encounter = encounterForTarget(data || {}, target.id) || {};
  const own = data?.os;
  const dn = own ? target.x - own.x : NaN;
  const de = own ? target.y - own.y : NaN;
  const bearing = Number.isFinite(dn) && Number.isFinite(de)
    ? (Math.atan2(de, dn) * 180 / Math.PI + 360) % 360
    : NaN;
  document.getElementById('targetDetailsTitle').textContent = `目标船 TS${target.id}`;
  const rows = [
    ['MMSI', target.mmsi ?? '--'],
    ['距离', Number.isFinite(encounter.distance_m) ? formatDistance(encounter.distance_m) : formatDistance(Math.hypot(dn, de))],
    ['相对方位', Number.isFinite(bearing) ? `${bearing.toFixed(1)}°` : '--'],
    ['航向', Number.isFinite(target.psi) ? `${(target.psi * 180 / Math.PI).toFixed(1)}°` : '--'],
    ['航速', Number.isFinite(target.sog) ? `${target.sog.toFixed(1)} m/s` : '--'],
    ['DCPA', formatDistance(encounter.dcpa_m)],
    ['TCPA', Number.isFinite(encounter.tcpa_s) ? `${encounter.tcpa_s.toFixed(1)} s` : '--'],
    ['COLREGs', encounter.validation_rule_id || encounter.encounter || '--'],
    ['阶段', encounter.stage || '--'],
    ['威胁', encounter.threat_level || 'UNKNOWN'],
  ];
  document.getElementById('targetDetailsBody').innerHTML = rows
    .map(([term, value]) => `<div><dt>${term}</dt><dd>${value}</dd></div>`).join('');
  const ship = busyWaterDocument?.ship_list?.find(item => String(item.id) === String(target.id));
  const editable = Boolean(ship && data?.state !== 'RUNNING');
  form.hidden = !editable;
  if (editable) {
    document.getElementById('targetSpeed').value = Number(ship.csog_state[2]).toFixed(1);
    document.getElementById('targetRouteN1').value = Number(ship.waypoints[0][0]).toFixed(1);
    document.getElementById('targetRouteE1').value = Number(ship.waypoints[1][0]).toFixed(1);
    document.getElementById('targetRouteN2').value = Number(ship.waypoints[0][1]).toFixed(1);
    document.getElementById('targetRouteE2').value = Number(ship.waypoints[1][1]).toFixed(1);
  }
  panel.hidden = false;
}

function selectedBusyWaterShip() {
  return busyWaterDocument?.ship_list?.find(item => String(item.id) === String(selectedTargetId));
}

function formatDistance(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)} m` : '--';
}

function hexToRgba(hex, alpha) {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) return hex;
  const value = Number.parseInt(hex.slice(1), 16);
  return `rgba(${value >> 16},${(value >> 8) & 255},${value & 255},${alpha})`;
}

/* Retained for compatibility with older test fixtures. */
function drawVessel(cx, cy, heading, color, label, size = 14) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(heading);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(0, -size);
  ctx.lineTo(size * 0.5, size * 0.6);
  ctx.lineTo(-size * 0.5, size * 0.6);
  ctx.closePath(); ctx.fill();
  ctx.restore();
  drawMapLabel(label, cx + size + 4, cy + 4, '#FFFFFF');
}

/* ══════════════════════════════════════════════
   UI TELEMETRY UPDATE
══════════════════════════════════════════════ */
function updateUI(data) {
  const os = data.os;
  if (selectedTargetId !== null) {
    const target = targetsForDisplay(data).find(item => String(item.id) === String(selectedTargetId));
    updateTargetDetails(target || null, data);
  }

  if (data.state === 'RUNNING' && lastRuntimeState !== 'RUNNING') {
    setRuntimePanelsExpanded(true);
  }
  lastRuntimeState = data.state || lastRuntimeState;

  // Header time
  setText('val-sim-time', `${(data.scenario_time ?? data.step * 0.5).toFixed(1)} s`);
  setText('val-run-state', data.state || 'CREATED');
  setText('val-reproduction', data.reproduction_status || 'not evaluated');
  syncPlaybackStatus(data.playback, data.state === 'RUNNING');

  // DCPA / TCPA
  const dcpa = Number.isFinite(data.dcpa) ? data.dcpa : null;
  const tcpa = Number.isFinite(data.tcpa) ? data.tcpa : null;
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

  updateColregsBadge(data.colregs);

  if (data.obstacles && data.obstacles.length > 0) {
    const obs  = data.obstacles[0];
    const dist = Math.hypot(os.x - obs.x, os.y - obs.y);
    setText('val-dist', `${dist.toFixed(1)} m`);
  }

  // OS telemetry
  setText('val-os-latitude', formatCoordinate(os.latitude, 'N', 'S'));
  setText('val-os-longitude', formatCoordinate(os.longitude, 'E', 'W'));
  setText('val-os-sog', Number.isFinite(os.sog) ? `${os.sog.toFixed(2)} m/s` : '-- m/s');
  setText('val-os-cog', formatCourse(os.cog));
  setText('val-os-heading', formatCourse(os.psi));
  setText('val-os-yaw', `${(os.r || 0).toFixed(1)} rad/s`);
  updatePlannerPanel(data);

  // Performance
  const stepMs = Number.isFinite(data.step_time_ms) ? data.step_time_ms : 0;
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

function updatePlannerPanel(data) {
  const planner = data.planner || {};
  const latestSolve = data.latest_planner_solve || {};
  const diagnosticPlanner = planner.solver_executed || !latestSolve.solver_executed
    ? planner
    : latestSolve;
  const execution = data.execution || {};
  const details = diagnosticPlanner.algorithm_details || {};
  const solveId = Number(planner.solve_id || 0);
  const realSolve = Boolean(planner.solver_executed);
  const mode = document.getElementById('val-solver-executed');
  mode.textContent = realSolve ? 'SOLVE' : 'HOLD';
  mode.classList.toggle('solve', realSolve);
  mode.classList.toggle('hold', !realSolve);

  setText('val-solve-id', `#${solveId}`);
  const solverSuccessful = planner.feasible !== false
    && ['SUCCESS', 'TIMEOUT_FEASIBLE'].includes(planner.status || 'SUCCESS');
  setText('val-solver-state', solverSuccessful ? '成功' : '失败');

  const horizonLength = data.plans?.prediction_horizon?.length || 0;
  const gridShape = Array.isArray(details.grid_shape) ? details.grid_shape : [];
  const horizonTime = diagnosticPlanner.algorithm_id === 'vo' && gridShape.length === 2
    ? `决策网格 ${gridShape[0]}×${gridShape[1]}`
    : horizonLength && Number.isFinite(diagnosticPlanner.horizon_dt_s)
      ? `${horizonLength} × ${diagnosticPlanner.horizon_dt_s.toFixed(1)}s`
      : `${horizonLength} points`;
  setText('val-planner-horizon', horizonTime);

  const course = execution.applied_course_ref_rad ?? planner.selected_command?.course_rad;
  const speed = execution.applied_speed_ref_mps ?? planner.selected_command?.speed_mps;
  setText('val-command-course', Number.isFinite(course) ? `${(course * 180 / Math.PI).toFixed(1)}°` : '--°');
  setText('val-command-speed', Number.isFinite(speed) ? `${speed.toFixed(2)} m/s` : '-- m/s');

  if (Number(latestSolve.solve_id || 0) !== lastDisplayedSolveId && latestSolve.solver_executed) {
    lastSolveSimTime = Number(latestSolve.sim_time || data.sim_time || 0);
  } else if (realSolve) {
    lastSolveSimTime = Number(planner.sim_time || data.sim_time || 0);
  }
  const prediction = data.plans?.prediction_horizon || [];
  const predictionIndex = Number.isFinite(diagnosticPlanner.horizon_dt_s) && lastSolveSimTime !== null
    ? Math.min(prediction.length - 1, Math.max(0, Math.round(
      (Number(data.sim_time || 0) - lastSolveSimTime) / diagnosticPlanner.horizon_dt_s,
    )))
    : 0;
  const predictedExecution = prediction[predictionIndex];
  const executionError = predictedExecution
    ? Math.hypot(predictedExecution[0] - data.os.x, predictedExecution[1] - data.os.y)
    : null;
  setText('val-prediction-error', Number.isFinite(executionError) ? `${executionError.toFixed(2)} m` : '-- m');
  drawPlannerSurface(diagnosticPlanner);
  ensureVODecisionSpace(diagnosticPlanner);
  const configuredSolvePeriod = Number(details.solve_period_s);
  setText(
    'val-solve-period',
    Number.isFinite(configuredSolvePeriod)
      ? `${configuredSolvePeriod.toFixed(1)} s`
      : diagnosticPlanner.algorithm_id === 'sbmpc'
        ? `${SBMPC_SOLVE_PERIOD_SECONDS.toFixed(1)} s`
        : diagnosticPlanner.algorithm_id === 'vo'
          ? '1.0 s'
        : '按算法触发',
  );

  const timelineTrace = latestSolve.solver_executed ? latestSolve : (realSolve ? planner : null);
  if (timelineTrace && Number(timelineTrace.solve_id) !== lastDisplayedSolveId) {
    lastDisplayedSolveId = Number(timelineTrace.solve_id);
    solveTimeline.push({
      solveId: lastDisplayedSolveId,
      simTime: Number(timelineTrace.sim_time || data.sim_time || 0),
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
  const isSimplifiedMPC = ['potocnik_simplified_mpc', 'potocnik_colreg_fan_mpc'].includes(algorithmId);
  const matrix = details.candidate_costs;
  const selectionMatrix = matrix;
  const label = algorithmId === 'vo'
    ? '速度决策空间'
    : algorithmId === 'sbmpc'
      ? 'SB-MPC 候选控制代价'
      : isSimplifiedMPC
        ? (algorithmId === 'potocnik_colreg_fan_mpc'
          ? 'COLREG 扇形 MPC · 规则与安全筛选'
          : '简化 MPC · 扇形轨迹筛选')
        : '名义 LOS 引导';
  const surfaceExplanation = document.getElementById('val-surface-explanation');
  const surfaceMeta = document.getElementById('val-surface-meta');
  if (surfaceExplanation) surfaceExplanation.hidden = isVO;
  if (surfaceMeta) surfaceMeta.hidden = isVO;
  setText('val-surface-label', label);
  setText('val-surface-explanation', '');
  setText('val-surface-meta', '');
  setText('label-best-cost', isVO ? '最小总 Cost' : '最优 Cost');
  setText('label-best-course-offset', '航向偏移');
  setText('label-best-speed-scale', isVO ? '候选航速' : '速度系数');
  const selectedHeading = Number(details.selected_heading_rad);
  const ownshipHeading = Number(voDecisionSpace?.ownship_heading_rad ?? currentData?.os?.psi);
  const selectedOffset = Number.isFinite(selectedHeading) && Number.isFinite(ownshipHeading)
    ? Math.atan2(Math.sin(selectedHeading - ownshipHeading), Math.cos(selectedHeading - ownshipHeading))
    : NaN;
  setText('val-best-cost', isVO ? formatCost(Number(details.objective ?? planner.objective)) : '--');
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
  if (objectiveHistoryWrap) objectiveHistoryWrap.hidden = algorithmId !== 'sbmpc';
  const voLegend = document.getElementById('voSurfaceLegend');
  if (voLegend) voLegend.hidden = !isVO;
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
    surface.fillText('暂无候选控制代价', 12, 78);
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
  if (planner.algorithm_id !== 'vo' || !activeSessionId) return;
  const card = document.getElementById('cardPlanner');
  const solveId = Number(planner.solve_id);
  if (card?.classList.contains('collapsed') || !Number.isInteger(solveId) || solveId < 1) return;
  const requestKey = `${activeSessionId}:${solveId}`;
  if (voDecisionSpaceKey === requestKey || voDecisionSpaceAttemptedKey === requestKey) return;
  voDecisionSpacePending = {
    sessionId: activeSessionId,
    solveId,
    planner,
  };
  requestPendingVODecisionSpace();
}

function requestPendingVODecisionSpace() {
  if (voDecisionSpaceController || !voDecisionSpacePending) return;
  const pending = voDecisionSpacePending;
  if (pending.sessionId !== activeSessionId) {
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
    if (!snapshot || controller.signal.aborted || pending.sessionId !== activeSessionId) return;
    voDecisionSpace = snapshot;
    voDecisionSpaceKey = requestKey;
    voDecisionSpaceAttemptedKey = requestKey;
    lastVORenderKey = null;
    drawPlannerSurface(pending.planner);
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
  const expectedKey = `${activeSessionId}:${solveId}`;
  const snapshot = voDecisionSpaceKey?.startsWith(`${activeSessionId}:`) ? voDecisionSpace : null;
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

function voCandidateColor(stateBits, normalizedCost) {
  const alpha = Math.max(0.58, Math.min(0.94, 0.58 + normalizedCost * 0.36));
  if (stateBits & 1) return `rgba(227,78,89,${alpha})`;
  if (stateBits & 4 || stateBits & 8) return `rgba(217,107,255,${alpha})`;
  if (stateBits & 2) return `rgba(240,201,77,${alpha})`;
  return `rgba(47,191,113,${alpha})`;
}

function voCandidateLabel(stateBits) {
  if (stateBits & 1) return '有限 TTC / 基础 VO';
  if (stateBits & 8) return 'CS 右转承诺禁区';
  if (stateBits & 4) return 'COLREG V1 禁区';
  if (stateBits & 2) return 'WVO 安全缓冲';
  return '安全';
}

function drawVelocityArrow(surface, centerX, centerY, radius, maxSpeed, velocity, ownshipHeading, color, width = 1.7) {
  const north = Number(velocity?.[0]);
  const east = Number(velocity?.[1]);
  if (!Number.isFinite(north) || !Number.isFinite(east)) return;
  const speed = Math.hypot(north, east);
  const relativeHeading = wrapRadians(Math.atan2(east, north) - ownshipHeading);
  const length = Math.min(speed, maxSpeed) / maxSpeed * radius;
  const endX = centerX + length * Math.sin(relativeHeading);
  const endY = centerY - length * Math.cos(relativeHeading);
  surface.strokeStyle = color;
  surface.fillStyle = color;
  surface.lineWidth = width;
  surface.beginPath();
  surface.moveTo(centerX, centerY);
  surface.lineTo(endX, endY);
  surface.stroke();
  const head = 5;
  surface.beginPath();
  surface.moveTo(endX, endY);
  surface.lineTo(endX - head * Math.sin(relativeHeading - 0.55), endY + head * Math.cos(relativeHeading - 0.55));
  surface.lineTo(endX - head * Math.sin(relativeHeading + 0.55), endY + head * Math.cos(relativeHeading + 0.55));
  surface.closePath();
  surface.fill();
}

function wrapRadians(value) {
  return Math.atan2(Math.sin(value), Math.cos(value));
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

new ResizeObserver(() => {
  lastVORenderKey = null;
  if (currentData) updatePlannerPanel(currentData);
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
  const increments = Array.isArray(details.candidate_heading_increments_rad)
    ? details.candidate_heading_increments_rad.map(Number)
    : [];
  const feasible = Array.isArray(details.candidate_feasible) ? details.candidate_feasible : [];
  const selectedIndex = Number(details.selected_candidate_index);
  const steps = Math.max(1, Number(details.prediction_steps) || 16);
  const decay = Number(details.heading_increment_decay) || 0.95;
  const targetOffset = Number(details.target_bearing_offset_rad);
  const trajectories = increments.map(increment => {
    const points = [{ x: 0, y: 0 }];
    let heading = 0;
    let turn = increment;
    let x = 0;
    let y = 0;
    for (let step = 0; step < steps; step += 1) {
      heading += turn;
      x += Math.sin(heading);
      y += Math.cos(heading);
      points.push({ x, y });
      turn *= decay;
    }
    return points;
  });

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
  const mapPoint = point => ({
    x: plot.left + (point.x - minX) * scale,
    y: plot.bottom - (point.y - minY) * scale,
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

function checkLogEvents(data) {
  const col = data.colregs;
  if (col !== lastColregs) {
    const cls = col === 'head_on'           ? 'log-warn'   :
                col === 'crossing_give_way' ? 'log-danger' :
                col === 'clear'             ? 'log-ok'     : 'log-info';
    pushLog(`COLREGs → ${ENCOUNTER_LABELS[col] || col}`, cls);
    lastColregs = col;
  }
  const dcpa = Number.isFinite(data.dcpa) ? data.dcpa : null;
  const lvl = dcpa === null ? null : dcpa > DCPA_SAFE ? 'safe' : dcpa > DCPA_WARN ? 'warn' : 'danger';
  if (lvl && lvl !== lastDcpaLevel) {
    pushLog(`DCPA ${lvl.toUpperCase()} — ${dcpa.toFixed(0)} m`,
            lvl === 'safe' ? 'log-ok' : lvl === 'warn' ? 'log-warn' : 'log-danger');
    lastDcpaLevel = lvl;
  }
  (data.events || []).forEach(event => {
    const planner = event.details?.planner || {};
    const eventKey = [
      data.run_id || activeSessionId || 'run',
      event.sequence ?? data.seq ?? '',
      event.type,
      event.details?.ship_id ?? '',
      planner.solve_id ?? '',
    ].join(':');
    if (seenEventKeys.has(eventKey)) return;
    seenEventKeys.add(eventKey);
    if (seenEventKeys.size > 1000) {
      const oldestKey = seenEventKeys.values().next().value;
      seenEventKeys.delete(oldestKey);
    }
    if (event.type === 'planner_solved') {
      const algorithm = String(planner.algorithm_id || data.executed_algorithm || 'planner').toUpperCase();
      const simTime = Number(event.sim_time ?? planner.sim_time);
      const solveId = Number(planner.solve_id);
      const solveLabel = Number.isFinite(solveId) && solveId > 0 ? ` #${solveId}` : '';
      const timeLabel = Number.isFinite(simTime) ? ` · 仿真 ${simTime.toFixed(1)}s` : '';
      pushLog(`${algorithm} 求解成功${solveLabel}${timeLabel}`, 'log-ok');
      return;
    }
    const detail = event.details && event.details.reason ? `: ${event.details.reason}` : '';
    pushLog(`${event.type}${detail}`, event.type.includes('fail') ? 'log-danger' : 'log-info');
  });
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
    reset: { text: '会话: 重置', logClass: 'log-warn' },
    disconnected: { text: '会话: 断连', logClass: 'log-danger' },
  };
  const next = states[state];
  if (!next) return;

  const indicator = document.getElementById('status-dot').closest('.status-indicator');
  const dot = document.getElementById('status-dot');
  indicator.classList.remove('connected', 'connecting', 'reset', 'disconnected');
  indicator.classList.add(state);
  dot.classList.toggle('active', state === 'connected');
  dot.classList.toggle('reset', state === 'reset' || state === 'connecting');
  document.getElementById('conn-status').textContent = next.text;

  if (logEvent && state !== sessionConnectionState) pushLog(next.text, next.logClass);
  sessionConnectionState = state;
}

function connectWebSocket() {
  if (!activeSessionId) return;
  if (ws) {
    ws.onclose = null;
    ws.close();
  }
  const sessionId = activeSessionId;
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${proto}//${location.host}/ws/sessions/${sessionId}`);
  ws = socket;

  socket.onopen = () => {
    if (socket !== ws || sessionId !== activeSessionId) return;
    setSessionConnectionState('connected', true);
  };

  socket.onmessage = event => {
    if (socket !== ws || sessionId !== activeSessionId) return;
    const data = JSON.parse(event.data);
    if (data.error === 'session_not_found') {
      socket.onclose = null;
      socket.close();
      recoverMissingSession(sessionId);
      return;
    }
    if (!data.os) return;
    currentData = data;
    updateUI(data);
    queueTelemetryRender(data);
    checkLogEvents(data);
    if (data.state === 'FINISHED' && !resultLoaded) loadResult();
    if (data.state === 'FAILED') pushLog(data.failure_reason || 'Simulation failed.', 'log-danger');
  };

  socket.onclose = () => {
    if (socket !== ws || sessionId !== activeSessionId) return;
    setSessionConnectionState('disconnected', true);
    setTimeout(() => {
      if (sessionId === activeSessionId && socket === ws) connectWebSocket();
    }, 2500);
  };

  socket.onerror = () => {
    if (socket === ws && sessionId === activeSessionId) pushLog('WebSocket error.', 'log-danger');
  };
}

async function recoverMissingSession(missingSessionId) {
  if (
    missingSessionId !== activeSessionId
    || sessionRecoveryPending
    || sessionCreationPromise
  ) return;
  if (document.visibilityState !== 'visible' || !document.hasFocus()) {
    activeSessionId = null;
    activeSessionKey = null;
    setSessionConnectionState('disconnected', true);
    pushLog('Session replaced in another tab. Select a configuration or reset to reconnect.', 'log-danger');
    return;
  }
  sessionRecoveryPending = true;
  activeSessionId = null;
  activeSessionKey = null;
  try {
    await createSession({ force: true });
  } catch (error) {
    setSessionConnectionState('disconnected', true);
    pushLog(`Session recovery failed: ${error.message}`, 'log-danger');
  } finally {
    sessionRecoveryPending = false;
  }
}

function isBusyWaterScenario(scenarioId) {
  return scenarioId === 'romsdal_busy_water_16' || scenarioId === 'romsdal_busy_water_80_stress';
}

function syncBusyWaterSetupVisibility(scenarioId = document.getElementById('scenarioSelect').value) {
  document.getElementById('busyWaterSetup').hidden = !isBusyWaterScenario(scenarioId);
}

function busyWaterProfile(scenarioId) {
  return scenarioId === 'romsdal_busy_water_80_stress' ? 'stress' : 'acceptance';
}

async function generateBusyWaterDocument({ scenarioId, targetCount, seed, crossing, headOn, overtaking }) {
  const params = new URLSearchParams({
    profile: busyWaterProfile(scenarioId),
    target_count: String(targetCount),
    seed: String(seed),
    crossing_ratio: String(crossing),
    head_on_ratio: String(headOn),
    overtaking_ratio: String(overtaking),
  });
  const payload = await apiRequest(`/api/busy-water/generate?${params}`);
  busyWaterDocument = payload.document;
  busyWaterBaseScenario = scenarioId;
  busyWaterSeed = Number(seed);
  busyWaterMix = {
    crossing: Number(payload.encounter_mix.crossing),
    head_on: Number(payload.encounter_mix.head_on),
    overtaking: Number(payload.encounter_mix.overtaking),
  };
  busyWaterRevision += 1;
  return payload;
}

async function ensureBusyWaterDocument(scenarioId) {
  syncBusyWaterSetupVisibility(scenarioId);
  if (!isBusyWaterScenario(scenarioId)) {
    busyWaterDocument = null;
    busyWaterBaseScenario = null;
    return;
  }
  if (busyWaterDocument && busyWaterBaseScenario === scenarioId) return;
  const targetCount = scenarioId === 'romsdal_busy_water_80_stress' ? 79 : 15;
  await generateBusyWaterDocument({
    scenarioId,
    targetCount,
    seed: 20250731,
    crossing: 0.6,
    headOn: 0.2,
    overtaking: 0.2,
  });
  document.getElementById('busyTargetCount').value = String(targetCount);
  document.getElementById('busySeed').value = String(busyWaterSeed);
}

function selectedSessionRequest() {
  const scenarioId = document.getElementById('scenarioSelect').value;
  return {
    validation_rule_id: document.querySelector('.qtab.active')?.dataset.group || 'rule14',
    scenario_id: scenarioId,
    algorithm_id: document.getElementById('algoSelect').value,
    tracker_id: document.getElementById('trackerSelect').value,
    seed: isBusyWaterScenario(scenarioId) ? busyWaterSeed : 0,
    strict_no_fallback: true,
    ...(isBusyWaterScenario(scenarioId) && busyWaterDocument
      ? { scenario_override: busyWaterDocument }
      : {}),
  };
}

function sessionKey(request) {
  return JSON.stringify([
    request.validation_rule_id,
    request.scenario_id,
    request.algorithm_id,
    request.tracker_id,
    request.seed,
    request.strict_no_fallback,
    isBusyWaterScenario(request.scenario_id) ? busyWaterRevision : 0,
  ]);
}

async function createSession({ force = false } = {}) {
  await ensureBusyWaterDocument(document.getElementById('scenarioSelect').value);
  const request = selectedSessionRequest();
  const requestKey = sessionKey(request);
  if (!force && activeSessionId && activeSessionKey === requestKey) {
    return { session_id: activeSessionId };
  }
  if (!force && sessionCreationPromise && pendingSessionKey === requestKey) {
    return sessionCreationPromise;
  }
  const revision = ++sessionCreateRevision;
  const previousCreation = sessionCreationPromise;
  const creation = (async () => {
    if (previousCreation) await previousCreation.catch(() => {});
    if (!force && revision !== sessionCreateRevision) return null;
    setSessionConnectionState('connecting');
    if (activeSessionId && currentData && currentData.state === 'RUNNING') {
      await apiRequest(`/api/sessions/${activeSessionId}/pause`, { method: 'POST' });
    }
    const data = await apiRequest('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (revision !== sessionCreateRevision) return data;
    activateSession(data, requestKey);
    pushLog(`Session created: ${request.scenario_id} / ${request.algorithm_id} / ${request.tracker_id}`, 'log-info');
    return data;
  })();
  sessionCreationPromise = creation;
  pendingSessionKey = requestKey;
  try {
    return await creation;
  } finally {
    if (sessionCreationPromise === creation) {
      sessionCreationPromise = null;
      pendingSessionKey = null;
    }
  }
}

function activateSession(data, requestKey = null) {
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
  if (renderFrameId !== null) cancelAnimationFrame(renderFrameId);
  renderFromData = null;
  renderToData = null;
  renderStartedAt = 0;
  renderFrameId = null;
  activeSessionId = data.session_id;
  activeSessionKey = requestKey || sessionKey(data.spec || selectedSessionRequest());
  resultLoaded = false;
  currentData = null;
  perfHistory.length = 0;
  solveTimeline = [];
  lastDisplayedSolveId = null;
  lastSolveSimTime = null;
  lastRuntimeState = 'CREATED';
  setRuntimePanelsExpanded(false);
  renderSolveTimeline();
  lastColregs = '';
  lastDcpaLevel = '';
  seenEventKeys.clear();
  encReady = false;
  encInfo = null;
  encImage = null;
  setEncStatus('loading');
  syncPlaybackStatus(data.playback, false);
  syncEncChartSelect(document.getElementById('scenarioSelect').value);
  connectWebSocket();
  initENC();
}

async function loadResult() {
  if (!activeSessionId || resultLoaded) return;
  resultLoaded = true;
  try {
    const result = await apiRequest(`/api/sessions/${activeSessionId}/result`);
    const artifacts = await apiRequest(`/api/sessions/${activeSessionId}/artifacts`);
    pushLog(
      `Evaluation ready: ${result.manifest.reproduction_status} · ${artifacts.length} artifacts.`,
      'log-ok',
    );
  } catch (error) {
    resultLoaded = false;
    pushLog(`Result load failed: ${error.message}`, 'log-danger');
  }
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
  scenarioCatalog = catalog.scenarios;
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
  const items = scenarioCatalog.filter(item => group.types.includes(item.type));
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

async function refreshBusyWaterDrafts() {
  const drafts = await apiRequest('/api/busy-water/drafts');
  const select = document.getElementById('busyDraftSelect');
  select.replaceChildren(new Option('选择草稿', ''));
  drafts.forEach(item => select.add(new Option(`${item.name} · ${item.target_count}艘`, item.id)));
}

document.getElementById('busyWaterSetup').addEventListener('click', async () => {
  const dialog = document.getElementById('busyWaterDialog');
  document.getElementById('busyWaterStatus').textContent = '';
  try {
    await refreshBusyWaterDrafts();
  } catch (error) {
    document.getElementById('busyWaterStatus').textContent = error.message;
  }
  dialog.showModal();
});

document.getElementById('closeBusyWaterDialog').addEventListener('click', () => {
  document.getElementById('busyWaterDialog').close();
});

document.getElementById('busyWaterForm').addEventListener('submit', async event => {
  event.preventDefault();
  const scenarioId = document.getElementById('scenarioSelect').value;
  const status = document.getElementById('busyWaterStatus');
  status.textContent = '生成中…';
  try {
    const payload = await generateBusyWaterDocument({
      scenarioId,
      targetCount: Number(document.getElementById('busyTargetCount').value),
      seed: Number(document.getElementById('busySeed').value),
      crossing: Number(document.getElementById('busyCrossingRatio').value),
      headOn: Number(document.getElementById('busyHeadOnRatio').value),
      overtaking: Number(document.getElementById('busyOvertakingRatio').value),
    });
    status.textContent = `已生成 ${payload.preflight.target_count} 艘目标船`;
    await createSession({ force: true });
    document.getElementById('busyWaterDialog').close();
  } catch (error) {
    status.textContent = error.message;
  }
});

document.getElementById('saveBusyWaterDraft').addEventListener('click', async () => {
  const status = document.getElementById('busyWaterStatus');
  const name = document.getElementById('busyDraftName').value.trim();
  if (!name || !busyWaterDocument) {
    status.textContent = '请填写草稿名称并先生成场景';
    return;
  }
  try {
    const payload = await apiRequest('/api/busy-water/drafts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        base_scenario_id: busyWaterBaseScenario,
        seed: busyWaterSeed,
        encounter_mix: busyWaterMix,
        document: busyWaterDocument,
      }),
    });
    status.textContent = `已保存 ${payload.name}`;
    await refreshBusyWaterDrafts();
    document.getElementById('busyDraftSelect').value = payload.id;
  } catch (error) {
    status.textContent = error.message;
  }
});

document.getElementById('loadBusyWaterDraft').addEventListener('click', async () => {
  const status = document.getElementById('busyWaterStatus');
  const identifier = document.getElementById('busyDraftSelect').value;
  if (!identifier) {
    status.textContent = '请选择草稿';
    return;
  }
  try {
    const payload = await apiRequest(`/api/busy-water/drafts/${encodeURIComponent(identifier)}`);
    busyWaterDocument = payload.document;
    busyWaterBaseScenario = payload.base_scenario_id;
    busyWaterSeed = Number(payload.seed);
    busyWaterMix = payload.encounter_mix;
    busyWaterRevision += 1;
    document.getElementById('scenarioSelect').value = busyWaterBaseScenario;
    syncExactCombinationAvailability('scenarioSelect');
    document.getElementById('busyTargetCount').value = String(payload.document.ship_list.length - 1);
    document.getElementById('busySeed').value = String(busyWaterSeed);
    document.getElementById('busyCrossingRatio').value = String(busyWaterMix.crossing);
    document.getElementById('busyHeadOnRatio').value = String(busyWaterMix.head_on);
    document.getElementById('busyOvertakingRatio').value = String(busyWaterMix.overtaking);
    await createSession({ force: true });
    document.getElementById('busyWaterDialog').close();
  } catch (error) {
    status.textContent = error.message;
  }
});

function startRoutePointPick(mode) {
  routePointEditMode = mode;
  canvas.classList.add('route-pick-mode');
}

document.getElementById('pickTargetRouteStart').addEventListener('click', () => startRoutePointPick('start'));
document.getElementById('pickTargetRouteEnd').addEventListener('click', () => startRoutePointPick('end'));
document.getElementById('cancelTargetEdit').addEventListener('click', () => {
  routePointEditMode = null;
  canvas.classList.remove('route-pick-mode');
  document.getElementById('targetEditForm').hidden = true;
});

document.getElementById('targetEditForm').addEventListener('submit', async event => {
  event.preventDefault();
  const ship = selectedBusyWaterShip();
  if (!ship || currentData?.state === 'RUNNING') return;
  const speed = Number(document.getElementById('targetSpeed').value);
  const n1 = Number(document.getElementById('targetRouteN1').value);
  const e1 = Number(document.getElementById('targetRouteE1').value);
  const n2 = Number(document.getElementById('targetRouteN2').value);
  const e2 = Number(document.getElementById('targetRouteE2').value);
  if (![speed, n1, e1, n2, e2].every(Number.isFinite) || Math.hypot(n2 - n1, e2 - e1) < 100) {
    pushLog('目标船航线至少需要 100 m，坐标与航速必须有效。', 'log-danger');
    return;
  }
  const candidate = structuredClone(busyWaterDocument);
  const edited = candidate.ship_list.find(item => String(item.id) === String(ship.id));
  const course = (Math.atan2(e2 - e1, n2 - n1) * 180 / Math.PI + 360) % 360;
  edited.csog_state = [n1, e1, speed, course];
  edited.waypoints = [[n1, n2], [e1, e2]];
  edited.speed_plan = [speed, speed];
  const previous = busyWaterDocument;
  busyWaterDocument = candidate;
  busyWaterRevision += 1;
  try {
    await createSession({ force: true });
    pushLog(`TS${ship.id} 航线与航速已更新。`, 'log-ok');
  } catch (error) {
    busyWaterDocument = previous;
    busyWaterRevision += 1;
    pushLog(`目标船更新失败: ${error.message}`, 'log-danger');
  }
});

document.getElementById('btnStart').addEventListener('click', async () => {
  try {
    await apiRequest(`/api/sessions/${activeSessionId}/start`, { method: 'POST' });
    setRuntimePanelsExpanded(true);
    pushLog('Simulation started.', 'log-ok');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnPause').addEventListener('click', async () => {
  try {
    await apiRequest(`/api/sessions/${activeSessionId}/pause`, { method: 'POST' });
    pushLog('Simulation paused.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnStep').addEventListener('click', async () => {
  try {
    await apiRequest(`/api/sessions/${activeSessionId}/step`, { method: 'POST' });
    pushLog('Single simulation step executed.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnReset').addEventListener('click', async () => {
  setSessionConnectionState('reset', true);
  try {
    await createSession({ force: true });
  } catch (error) {
    setSessionConnectionState('disconnected', true);
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnReplay').addEventListener('click', async () => {
  try {
    const data = await apiRequest(`/api/sessions/${activeSessionId}/replay`, { method: 'POST' });
    activateSession(data);
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
  try {
    await createSession();
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
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
    try {
      await createSession();
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });
});

document.querySelectorAll('.qtab').forEach(tab => {
  tab.addEventListener('click', async () => {
    if (tab.disabled) return;
    try {
      await populateCatalogs(tab.dataset.group);
      await createSession();
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });
});

document.querySelectorAll('.speed-preset').forEach(button => {
  button.addEventListener('click', async () => {
    if (!activeSessionId) return;
    const speed = parseFloat(button.dataset.speed);
    const controls = [...document.querySelectorAll('.speed-preset')];
    controls.forEach(item => { item.disabled = true; });
    try {
      const playback = await apiRequest(
        `/api/sessions/${encodeURIComponent(activeSessionId)}/speed?multiplier=${speed}`,
        { method: 'POST' },
      );
      syncPlaybackStatus(playback, currentData?.state === 'RUNNING');
      if (currentData) currentData.playback = playback;
    } catch (error) {
      pushLog(`Speed change failed: ${error.message}`, 'log-danger');
      syncPlaybackStatus(currentData?.playback, currentData?.state === 'RUNNING');
    } finally {
      controls.forEach(item => { item.disabled = false; });
    }
  });
});

const RUNTIME_PANEL_IDS = ['cardSafety', 'cardTelemetry', 'cardPlanner', 'cardPerf'];

function setCardCollapsed(card, collapsed) {
  card.classList.toggle('collapsed', collapsed);
  const button = card.querySelector('.card-toggle');
  if (!button) return;
  button.textContent = collapsed ? '展开' : '收起';
  button.setAttribute('aria-expanded', String(!collapsed));
  if (!collapsed && card.id === 'cardPlanner' && currentData) {
    updatePlannerPanel(currentData);
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
  ['cardIntegrations', 'cardRules', 'cardControl', 'cardTracker'].forEach(id => {
    const card = document.getElementById(id);
    if (card) controls.appendChild(card);
  });
  sidebar.prepend(controls);
  RUNTIME_PANEL_IDS.forEach(id => {
    const card = document.getElementById(id);
    if (card) {
      insights.appendChild(card);
      initializeCollapsibleCard(card, true);
    }
  });
  initializeCollapsibleCard(document.getElementById('cardIntegrations'), true);
  initializeCollapsibleCard(document.getElementById('cardRules'), false);
  initializeCollapsibleCard(document.getElementById('cardControl'), false);
  initializeCollapsibleCard(document.getElementById('cardTracker'), true);
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
  try {
    await populateCatalogs();
    await createSession();
  } catch (error) {
    pushLog(`Initialization failed: ${error.message}`, 'log-danger');
  }
}

boot();
