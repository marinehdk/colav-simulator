import { activeSessionRuntime, telemetryProjection } from './modules/session-runtime-instance.js?v=20260826-chart-view-control-v1';
import './modules/line-graph.js?v=20260826-chart-view-control-v1';
import {
  createSituationDisplay,
  RADAR_DETECTION_RANGE_M,
  plannerSurfaceType,
  wrapRadians,
  voCandidateColor,
  drawVelocityArrow,
  simplifiedMpcFanGeometry,
} from './modules/situation-display.js?v=20260828-ownship-placard-v3';
import { buildRadarModel, createRadarMiniMap } from './modules/radar-mini-map.js?v=20260827-instrument-polish-v1';

/**
 * Colav-Simulator Web GUI — app.js
 * Deployment adapter/host: owns the Situation Display instance, planner
 * surface panel, and runtime projection/control wiring. Validation Assembly
 * owns Config policy, catalog, and Active Session creation.
 * ENC situation canvas rendering lives in modules/situation-display.js.
 */

/* ══════════════════════════════════════════════
   CONSTANTS
══════════════════════════════════════════════ */
const SAFETY_MARGIN_DEFAULT = 150;
const PERF_HISTORY_LEN      = 60;
const VO_DECISION_FETCH_INTERVAL_MS = 200;
const ENCOUNTER_LABELS = {
  head_on: 'Rule 14 Head-on',
  overtaking: 'Rule 13 Overtaking',
  overtaken: 'Rule 13 Overtaken',
  crossing_give_way: 'Rule 15 Give-way (16)',
  crossing_stand_on: 'Rule 15 Stand-on (17)',
  clear: 'Clear',
};

let solveTimeline = [];
let lastDisplayedSolveId = null;
let lastRuntimeState = 'CREATED';
let lastSolveSimTime = null;
let lastDisplayedRotDegSec = 0;

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
let latestMonitorProjection = null;
let latestVesselMarkers = [];
let latestOwnshipMarker = null;
let selectedVesselTarget = null;
let selectedVesselAnchor = null;
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
  if (algorithmId === 'potocnik_colreg_fan_mpc') {
    const distanceM = Number(constraints.planning_zone?.distance_m);
    if (Number.isFinite(distanceM) && distanceM > 0) {
      return {
        distanceM,
        label: '安全区',
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
  // Config owns the draft. Deployment only receives the immutable active
  // session projection; it must not read retired selector DOM.
  getScenarioId: () => deploymentRuntimeSnapshot.session?.spec?.scenario_id || null,
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
  onSelectionChange: showVesselPlacard,
  onTargetMarkersChange: renderVesselMarkers,
});
const radarMiniMap = createRadarMiniMap({ canvas: document.getElementById('liveRadarMiniMap') });

function vesselMarkerElement(id) {
  return document.querySelector(`.vessel-marker[data-target-id="${CSS.escape(String(id))}"]`);
}

function applyVesselMarkerModel(component, marker) {
  Object.assign(component, {
    type: 'flat-large',
    state: 'enabled',
    selected: false,
    heading: marker.headingDeg,
    course: marker.courseDeg,
    speedIndicator: marker.speedIndicator,
    turnRate: marker.turnRateDeg,
    vesselImage: 'cargo-top',
    vesselImageSize: 34,
    number: Number(marker.id),
    name: `TS${marker.id}`,
  });
  component.setAttribute('aria-hidden', 'true');
}

function renderVesselMarkers(markers = [], context = {}) {
  latestVesselMarkers = markers;
  latestOwnshipMarker = context.ownship || null;
  const layer = document.getElementById('vesselMarkerLayer');
  if (!layer) return;
  const activeIds = new Set(markers.map(marker => String(marker.id)));
  layer.querySelectorAll('.vessel-marker').forEach((element) => {
    if (!activeIds.has(element.dataset.targetId)) element.remove();
  });
  markers.forEach((marker) => {
    let host = vesselMarkerElement(marker.id);
    if (!host) {
      host = document.createElement('div');
      host.className = 'vessel-marker';
      host.dataset.targetId = String(marker.id);
      host.setAttribute('role', 'button');
      host.tabIndex = 0;
      const select = (event) => {
        event.stopPropagation();
        situationDisplay.selectTarget(host.dataset.targetId);
      };
      host.addEventListener('click', select);
      host.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') select(event);
      });
      const component = document.createElement('obc-chart-object-vessel-button');
      host.appendChild(component);
      layer.appendChild(host);
    }
    host.style.transform = `translate3d(${marker.anchor.x - 32}px, ${marker.anchor.y - 32}px, 0)`;
    host.hidden = marker.anchor.x < -40
      || marker.anchor.y < -40
      || marker.anchor.x > layer.clientWidth + 40
      || marker.anchor.y > layer.clientHeight + 40;
    host.setAttribute('aria-label', `TS${marker.id}, ${marker.state}, click for vessel details`);
    host.dataset.riskState = marker.state;
    host.dataset.selected = String(marker.selected);
    applyVesselMarkerModel(host.firstElementChild, marker);
  });

  if (selectedVesselTarget) {
    if (String(selectedVesselTarget.id) === '0' && latestOwnshipMarker) {
      selectedVesselTarget = latestOwnshipMarker.vessel;
      positionVesselPlacard(latestOwnshipMarker.anchor);
    } else {
      const selected = markers.find(marker => String(marker.id) === String(selectedVesselTarget.id));
      if (selected) {
        selectedVesselTarget = selected.target;
        positionVesselPlacard(selected.anchor);
      }
    }
  }
}

function hideVesselPlacard() {
  selectedVesselTarget = null;
  selectedVesselAnchor = null;
  const placard = document.getElementById('vesselDetailPlacard');
  if (placard) placard.hidden = true;
}

function placardMetric(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function positionVesselPlacard(anchor) {
  const placard = document.getElementById('vesselDetailPlacard');
  const wrapper = document.getElementById('canvasWrapper');
  if (!placard || !wrapper || !anchor) return;
  selectedVesselAnchor = anchor;
  const above = anchor.y > 220;
  const halfWidth = Math.min(165, Math.max(80, wrapper.clientWidth / 2 - 8));
  const left = Math.min(wrapper.clientWidth - halfWidth, Math.max(halfWidth, anchor.x));
  const top = anchor.y + (above ? -38 : 38);
  placard.dataset.placement = above ? 'above' : 'below';
  placard.pointerDirection = above ? 'bottom' : 'top';
  placard.style.transform = `translate3d(${left}px, ${top}px, 0) translate(-50%, ${above ? '-100%' : '0'})`;
}

function showVesselPlacard(target, context = {}) {
  const placard = document.getElementById('vesselDetailPlacard');
  const wrapper = document.getElementById('canvasWrapper');
  if (!placard || !wrapper || !target) {
    hideVesselPlacard();
    return;
  }
  selectedVesselTarget = target;
  const isOwnship = String(target.id) === '0';
  const marker = latestVesselMarkers.find(item => String(item.id) === String(target.id));
  const anchor = context.anchor || (isOwnship ? latestOwnshipMarker?.anchor : marker?.anchor);
  if (!anchor) {
    placard.hidden = true;
    return;
  }
  const riskTarget = latestMonitorProjection?.risk?.targets
    ?.find(item => String(item.targetId) === String(target.id));
  const ownship = latestMonitorProjection?.raw?.os || currentData?.os;
  const northDelta = Number(target.x) - Number(ownship?.x);
  const eastDelta = Number(target.y) - Number(ownship?.y);
  const geometricRangeM = Math.hypot(northDelta, eastDelta);
  const rangeM = Number.isFinite(riskTarget?.distanceM) ? riskTarget.distanceM : geometricRangeM;
  const bearingDeg = Number.isFinite(northDelta) && Number.isFinite(eastDelta)
    ? (Math.atan2(eastDelta, northDelta) * 180 / Math.PI + 360) % 360
    : NaN;
  const headingDeg = Number.isFinite(target.psi)
    ? (Number(target.psi) * 180 / Math.PI + 360) % 360
    : NaN;
  const speedKnots = Number.isFinite(target.sog) ? Number(target.sog) / 0.514444 : NaN;
  const dcpaNm = Number.isFinite(riskTarget?.dcpaM)
    ? Math.abs(riskTarget.dcpaM) / METERS_PER_NAUTICAL_MILE
    : NaN;
  const tcpaMin = Number.isFinite(riskTarget?.tcpaS) ? riskTarget.tcpaS / 60 : NaN;
  const source = isOwnship
    ? 'OWN'
    : deploymentRuntimeSnapshot.session?.spec?.historical_scenario_id ? 'AIS' : 'TRACK';
  Object.assign(placard, {
    headerVariant: 'condensed',
    index: isOwnship ? 'OS' : String(target.id),
    cardTitle: isOwnship ? 'OWN SHIP' : target.name || `TS${target.id}`,
    description: isOwnship ? 'Controlled ownship' : target.mmsi ? `MMSI ${target.mmsi}` : 'Tracked target vessel',
    source,
    interactive: false,
  });
  positionVesselPlacard(anchor);
  placard.hidden = false;
  placard.setAttribute('aria-label', `${isOwnship ? 'OWN SHIP' : target.name || `TS${target.id}`} vessel details`);

  placardMetric('vesselPlacardBearing', Number.isFinite(bearingDeg) ? Math.round(bearingDeg).toString().padStart(3, '0') : '---');
  placardMetric('vesselPlacardRange', Number.isFinite(rangeM) ? (rangeM / METERS_PER_NAUTICAL_MILE).toFixed(1) : '---');
  placardMetric('vesselPlacardDcpa', Number.isFinite(dcpaNm) ? dcpaNm.toFixed(dcpaNm < 0.1 ? 3 : 2) : '---');
  placardMetric('vesselPlacardTcpa', Number.isFinite(tcpaMin) ? tcpaMin.toFixed(1) : '---');
  placardMetric('vesselPlacardHeading', Number.isFinite(headingDeg) ? Math.round(headingDeg).toString().padStart(3, '0') : '---');
  placardMetric('vesselPlacardSpeed', Number.isFinite(speedKnots) ? speedKnots.toFixed(1) : '---');
  const symbol = document.getElementById('vesselPlacardSymbol');
  if (symbol) Object.assign(symbol, {
    type: 'flat-large',
    heading: Number.isFinite(headingDeg) ? headingDeg : 0,
    course: Number.isFinite(headingDeg) ? headingDeg : 0,
    state: marker?.state || 'enabled',
    vesselImage: 'cargo-top',
    vesselImageSize: 28,
  });
}

/* ══════════════════════════════════════════════
   OPENBRIDGE THEME (C5 #4 — full prototype behavior, P:2849-2870 / P:3179-3204)
   Palette chrome only: html dataset, top-bar dimming state, persistence, and
   the situation-display palette re-read. No validation/runtime truth here.
══════════════════════════════════════════════ */
const PALETTE_NAMES = { day: true, dusk: true, night: true, bright: true };
const mainTopBar = document.getElementById('mainTopBar');
const brillianceMenu = document.getElementById('brillianceMenu');

let leftSidebarCollapsed = false;
let rightSidebarCollapsed = false;

function syncDeploymentSidebarControls() {
  const layout = document.querySelector('.live-layout');
  const leftSidebar = document.getElementById('liveInfoSidebar');
  const rightSidebar = document.getElementById('liveOperationsSidebar');
  if (!layout) return;

  layout.classList.toggle('left-sidebar-collapsed', leftSidebarCollapsed);
  layout.classList.toggle('right-sidebar-collapsed', rightSidebarCollapsed);
  leftSidebar?.setAttribute('aria-hidden', String(leftSidebarCollapsed));
  rightSidebar?.setAttribute('aria-hidden', String(rightSidebarCollapsed));

  if (mainTopBar) {
    mainTopBar.menuButtonActivated = leftSidebarCollapsed;
    mainTopBar.appsButtonActivated = rightSidebarCollapsed;
    const applyToggleMetadata = () => {
      const leftToggle = mainTopBar.shadowRoot?.querySelector('.menu-button > obc-icon-button');
      const rightToggle = mainTopBar.shadowRoot?.querySelector('.apps-button');
      const toggles = [
        [leftToggle, leftSidebarCollapsed, '左侧栏', 'liveInfoSidebar'],
        [rightToggle, rightSidebarCollapsed, '右侧栏', 'liveOperationsSidebar'],
      ];
      toggles.forEach(([button, collapsed, label, controls]) => {
        if (!button) return;
        const action = collapsed ? '展开' : '收起';
        const attributes = {
          'aria-label': `${action}${label}`,
          title: `${action}${label}`,
          'aria-expanded': String(!collapsed),
          'aria-controls': controls,
        };
        [button, button.shadowRoot?.querySelector('button')].filter(Boolean).forEach((element) => {
          Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
        });
      });
    };
    applyToggleMetadata();
    mainTopBar.updateComplete?.then(applyToggleMetadata);
  }
}

function setupDeploymentSidebarToggles() {
  if (!mainTopBar || mainTopBar.dataset.sidebarTogglesBound === 'true') {
    syncDeploymentSidebarControls();
    return;
  }
  mainTopBar.dataset.sidebarTogglesBound = 'true';
  mainTopBar.addEventListener('menu-button-clicked', () => {
    leftSidebarCollapsed = !leftSidebarCollapsed;
    syncDeploymentSidebarControls();
  });
  mainTopBar.addEventListener('apps-button-clicked', () => {
    rightSidebarCollapsed = !rightSidebarCollapsed;
    syncDeploymentSidebarControls();
  });
  syncDeploymentSidebarControls();
}

setupDeploymentSidebarToggles();
customElements.whenDefined('obc-top-bar').then(syncDeploymentSidebarControls);

// Brilliance-menu ships inside the same locally-bundled module config-shell.js
// loads (vendor/openbridge/entry-source.mjs); re-import is a cache no-op and
// failure degrades like every other best-effort OpenBridge piece.
import('/static/vendor/openbridge/openbridge-components.mjs?v=20260827-vessel-placard-v1').catch(() => {});

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

document.getElementById('zoomIn')?.addEventListener('click', () => situationDisplay.zoomIn());
document.getElementById('zoomOut')?.addEventListener('click', () => situationDisplay.zoomOut());
document.getElementById('zoomReset')?.addEventListener('click', () => situationDisplay.fitView());
document.getElementById('zoomInBtn')?.addEventListener('click', () => situationDisplay.zoomIn());
document.getElementById('zoomOutBtn')?.addEventListener('click', () => situationDisplay.zoomOut());
function syncChartDisplayPopoverState() {
  const button = document.getElementById('chartLayersBtn');
  const panel = document.getElementById('chartDisplayPopover');
  if (button && panel) button.setAttribute('aria-expanded', String(!panel.hidden));
}

function setupChartDisplayPopover() {
  const button = document.getElementById('chartLayersBtn');
  const panel = document.getElementById('chartDisplayPopover');
  const closeButton = document.getElementById('closeChartDisplayBtn');
  if (!button || !panel || button.dataset.bound === 'true') return;
  button.dataset.bound = 'true';
  const close = () => {
    panel.hidden = true;
    syncChartDisplayPopoverState();
  };
  button.addEventListener('click', event => {
    event.stopPropagation();
    panel.hidden = !panel.hidden;
    syncChartDisplayPopoverState();
  });
  closeButton?.addEventListener('click', close);
  panel.addEventListener('click', event => event.stopPropagation());
  document.addEventListener('click', event => {
    if (!panel.hidden && !panel.contains(event.target) && !event.composedPath().includes(button)) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || panel.hidden) return;
    close();
    (button.shadowRoot?.querySelector('button') || button).focus();
  });
  syncChartDisplayPopoverState();
}

setupChartDisplayPopover();
document.getElementById('fitTrafficBtn')?.addEventListener('click', () => situationDisplay.fitTraffic());
document.getElementById('recenterChartBtn')?.addEventListener('click', () => situationDisplay.recenterOwnship());
document.querySelectorAll('[data-map-orientation]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-map-orientation]').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-pressed', 'false');
    });
    btn.classList.add('active');
    btn.setAttribute('aria-pressed', 'true');
    const orientation = btn.dataset.mapOrientation;
    if (situationDisplay.setOrientation) situationDisplay.setOrientation(orientation);
  });
});
document.querySelectorAll('[data-layer]').forEach(input => {
  input.addEventListener('change', () => {
    situationDisplay.setLayerVisible(input.dataset.layer, input.checked);
    updateLegendVisibility();
  });
});

/* ══════════════════════════════════════════════
   UI TELEMETRY UPDATE
══════════════════════════════════════════════ */
function updateUI(proj) {
  const data = proj.raw;
  const navigation = proj.navigation;
  const os = data?.os;

  const previousRuntimeState = lastRuntimeState;
  if (proj.state === 'RUNNING' && previousRuntimeState !== 'RUNNING') {
    setRuntimePanelsExpanded(true);
  }
  lastRuntimeState = proj.state || lastRuntimeState;

  const responseRangeLabel = plannerResponseRange()?.label || '安全区';
  setText('response-range-control-label', responseRangeLabel);
  setText('response-range-legend-label', responseRangeLabel);

  // Deployment Display & Playback
  updateDeploymentDisplay(proj);

  // Left Sidebar: Ownship (Page 0: Route / Page 1: Sensor)
  updateOwnshipTelemetry(proj);

  // Right Sidebar: Operations (Page 0: Monitor / Page 1: Algo)
  updateMonitorTelemetry(proj);
  updateAlgoTelemetry(proj);

  // Legacy header & telemetry updates for compatibility
  setText('val-sim-time', `${(navigation?.simTime ?? 0).toFixed(1)} s`);
  setText('val-run-state', proj.state || 'CREATED');
  setText('val-reproduction', proj.outcome.reproductionStatus || 'not evaluated');
  syncPlaybackStatus(proj.raw?.playback, proj.state === 'RUNNING');

  const primary = proj.risk.primary;
  setText('val-primary-target', primary?.targetLabel || '无目标');
  const dcpa = proj.risk.dcpaM;
  const tcpa = proj.risk.tcpaS;
  const dcpaEl = document.getElementById('val-dcpa');
  if (dcpaEl) {
    dcpaEl.textContent = dcpa === null ? '--- m' : `${dcpa.toFixed(1)} m`;
    setThreatClass(dcpaEl, primary?.displayClass);
  }
  setThreatBar('dcpaBar', primary?.displayPercent, primary?.displayClass);

  const tcpaEl = document.getElementById('val-tcpa');
  if (tcpaEl) {
    tcpaEl.textContent = tcpa === null ? '--- s' : `${tcpa.toFixed(1)} s`;
    setThreatClass(tcpaEl, primary?.displayClass);
  }
  setThreatBar('tcpaBar', primary?.displayPercent, primary?.displayClass);

  updateColregsBadge(proj.risk.colregs);

  const primaryDistance = primary?.distanceM ?? null;
  setText('val-dist', primaryDistance === null ? '--- m' : `${primaryDistance.toFixed(1)} m`);

  setText('val-os-latitude', formatCoordinate(navigation?.latitude, 'N', 'S'));
  setText('val-os-longitude', formatCoordinate(navigation?.longitude, 'E', 'W'));
  setText('val-os-sog', Number.isFinite(navigation?.sog) ? `${navigation.sog.toFixed(2)} m/s` : '-- m/s');
  setText('val-os-cog', formatCourse(navigation?.cog));
  setText('val-os-heading', formatCourse(navigation?.psi));
  setText('val-os-yaw', `${(os?.r || 0).toFixed(1)} rad/s`);
  updatePlannerPanel(proj);

  // Performance sparkline
  const stepMs = Number.isFinite(navigation?.stepTimeMs) ? navigation.stepTimeMs : 0;
  setText('val-step-time', `${stepMs.toFixed(2)} ms`);
  setText('liveStepTime', `${stepMs.toFixed(2)}`);
  perfHistory.push(stepMs);
  if (perfHistory.length > PERF_HISTORY_LEN) perfHistory.shift();
  const avg = perfHistory.reduce((a, b) => a + b, 0) / perfHistory.length;
  setText('val-avg-time', `${avg.toFixed(2)} ms`);
  setText('liveAvgTime', `${avg.toFixed(2)}`);
  drawPerfChart();
  updatePerfSparkline();
}

function updateDeploymentDisplay(proj) {
  const simTime = proj.navigation?.simTime ?? 0;
  setText('liveSimulationTime', `${simTime.toFixed(1)} s`);
  const aisUtc = proj.raw?.ais_utc;
  setText('liveAisUtc', aisUtc ? `AIS ${String(aisUtc).slice(11, 19)}Z` : '');
  setText('liveControlState', proj.state || 'NOT CREATED');
  const emptyState = document.getElementById('liveEmptyState');
  if (emptyState) {
    emptyState.hidden = Boolean(proj.sessionId);
  }
}

const METERS_PER_NAUTICAL_MILE = 1852;

function routeLegs(waypoints) {
  const [norths, easts] = Array.isArray(waypoints) ? waypoints : [[], []];
  if (!Array.isArray(norths) || norths.length < 2) return [];
  return norths.slice(0, -1).map((_, index) => ({
    from: { n: norths[index], e: easts[index] },
    to: { n: norths[index + 1], e: easts[index + 1] },
  }));
}

function routeProgress(legs, pos) {
  // Active leg: the first leg the ownship has not fully passed; if all are
  // passed the ownship is on the final approach (remaining distance 0).
  for (let index = 0; index < legs.length; index++) {
    const leg = legs[index];
    const dn = leg.to.n - leg.from.n;
    const de = leg.to.e - leg.from.e;
    const length = Math.hypot(dn, de);
    if (length === 0) continue;
    const t = ((pos.n - leg.from.n) * dn + (pos.e - leg.from.e) * de) / (length * length);
    if (t < 1 || index === legs.length - 1) {
      const remaining = Math.max(0, (1 - Math.max(t, 0))) * length;
      const later = legs.slice(index + 1).reduce((sum, item) => sum + Math.hypot(item.to.n - item.from.n, item.to.e - item.from.e), 0);
      return { index, leg, remaining, total: remaining + later, t };
    }
  }
  return null;
}

function formatDuration(totalSeconds) {
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return '--:--:--';
  const seconds = Math.floor(totalSeconds);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function updateRouteCard(proj) {
  const data = proj.raw || {};
  // Steering mode is advisory display only and follows the backend-owned
  // canonical avoidance action; the browser never infers action from geometry.
  const collisionActive = proj.risk?.status === 'AVAILABLE'
    && proj.risk?.primary?.avoidanceActionActive === true;
  const steeringMode = document.getElementById('liveSteeringMode');
  if (steeringMode) {
    steeringMode.textContent = collisionActive ? 'COLLISION' : 'TRACK';
    steeringMode.dataset.mode = collisionActive ? 'collision' : 'track';
  }
  const legs = routeLegs(data.waypoints);
  const os = data.os || {};
  const nextLegSection = document.querySelector('.route-leg[aria-labelledby="next-leg-heading"]');
  // A start→end route has a single leg; "Next leg" only exists with a waypoint in between.
  const hasNextLeg = legs.length >= 2;
  if (nextLegSection) nextLegSection.hidden = !hasNextLeg;
  if (!Number.isFinite(os.x) || !Number.isFinite(os.y) || !legs.length) return;
  const progress = routeProgress(legs, { n: os.x, e: os.y });
  if (!progress) return;
  const legCourseDeg = ((Math.atan2(progress.leg.to.e - progress.leg.from.e, progress.leg.to.n - progress.leg.from.n)
    * 180 / Math.PI) % 360 + 360) % 360;
  setText('liveLegCourse', `${Math.round(legCourseDeg).toString().padStart(3, '0')}°`);
  setHtml('liveLegDistance', `${(progress.remaining / METERS_PER_NAUTICAL_MILE).toFixed(1)}<small> NM</small>`);
  const sog = proj.navigation?.sog;
  const legTimeS = Number.isFinite(sog) && sog > 0.05 ? progress.remaining / sog : null;
  setText('liveLegTime', formatDuration(legTimeS));
  if (hasNextLeg) {
    const next = legs[progress.index + 1];
    const nextCourseDeg = ((Math.atan2(next.to.e - next.from.e, next.to.n - next.from.n)
      * 180 / Math.PI) % 360 + 360) % 360;
    const nextLength = Math.hypot(next.to.n - next.from.n, next.to.e - next.from.e);
    setText('liveNextLegCourse', `${Math.round(nextCourseDeg).toString().padStart(3, '0')}°`);
    setHtml('liveNextLegDistance', `${(nextLength / METERS_PER_NAUTICAL_MILE).toFixed(1)}<small> NM</small>`);
    setText('liveNextLegTime', formatDuration(Number.isFinite(sog) && sog > 0.05 ? nextLength / sog : null));
  }
  const totalTimeS = Number.isFinite(sog) && sog > 0.05 ? progress.total / sog : null;
  setText('liveRouteRemaining', formatDuration(totalTimeS));
  setText('liveRouteEta', totalTimeS === null ? '--:--:--' : formatDuration((proj.navigation?.simTime ?? 0) + totalTimeS));
}

const SENSOR_SOURCE_MOCKS = [
  {
    id: 'sidebarHdgSource',
    value: 'gps1',
    options: [
      { value: 'gyro1', label: 'GYRO 1' },
      { value: 'gyro2', label: 'GYRO 2' },
      { value: 'gps1', label: 'GPS 1' },
    ],
  },
  {
    id: 'sidebarCogSource',
    value: 'log2',
    options: [
      { value: 'gps1', label: 'GPS 1' },
      { value: 'gps2', label: 'GPS 2' },
      { value: 'log2', label: 'LOG 2' },
    ],
  },
  {
    id: 'sidebarStwSource',
    value: 'log1',
    options: [
      { value: 'log1', label: 'LOG 1' },
      { value: 'log2', label: 'LOG 2' },
    ],
  },
  {
    id: 'sidebarDepthSource',
    value: 'enc',
    options: [
      { value: 'enc', label: 'ENC' },
      { value: 'snd1', label: 'SND 1' },
      { value: 'snd2', label: 'SND 2' },
    ],
  },
  {
    id: 'sidebarPositionSource',
    value: 'gps1',
    options: [
      { value: 'gps1', label: 'GPS 1' },
      { value: 'gps2', label: 'GPS 2' },
      { value: 'ins1', label: 'INS 1' },
    ],
  },
];

function setupSensorSourceDropdowns() {
  for (const config of SENSOR_SOURCE_MOCKS) {
    const dropdown = document.getElementById(config.id);
    if (!dropdown) continue;
    Object.assign(dropdown, {
      options: config.options,
      value: dropdown.value || config.value,
      type: 'label',
      fullWidth: true,
      flat: true,
    });
    if (dropdown.dataset.bound === 'true') continue;
    dropdown.dataset.bound = 'true';
    dropdown.addEventListener('dropdown-change', (event) => {
      dropdown.value = event.detail.value;
      dropdown.setAttribute('aria-label', `${config.id}: ${event.detail.label}`);
    });
  }
}

function formatRouteRadius(radiusM) {
  if (!Number.isFinite(radiusM) || radiusM < 0) return null;
  if (radiusM < 1000) return { value: String(Math.round(radiusM)), unit: 'm' };
  const radiusKm = radiusM / 1000;
  const value = radiusKm < 10
    ? radiusKm.toFixed(2)
    : radiusKm < 100 ? radiusKm.toFixed(1) : String(Math.round(radiusKm));
  return { value, unit: 'km' };
}

function updateOwnshipTelemetry(proj) {
  const nav = proj.navigation || {};
  const data = proj.raw;
  const os = data?.os;
  const floorDepth = Number.isFinite(os?.floor_depth_m) ? Number(os.floor_depth_m) : null;
  const vesselDraft = Number.isFinite(data?.enc_navigation_area?.vessel_draft_m)
    ? Number(data.enc_navigation_area.vessel_draft_m)
    : null;
  const safeDepth = Number.isFinite(data?.enc_navigation_area?.minimum_depth_m)
    ? Number(data.enc_navigation_area.minimum_depth_m)
    : null;
  const headingDeg = Number.isFinite(nav.psi) ? ((nav.psi * 180 / Math.PI) % 360 + 360) % 360 : 0;
  const cogDeg = Number.isFinite(nav.cog) ? ((nav.cog * 180 / Math.PI) % 360 + 360) % 360 : headingDeg;
  const sogKnots = Number.isFinite(nav.sog) ? nav.sog * 1.94384 : 0;

  // 1. Page 0: OWN SHIP Card Readouts
  const sbHdg = document.getElementById('sidebarHdgReadout');
  if (sbHdg) sbHdg.readouts = [{ type: 'value', value: Math.round(headingDeg), nDigits: 3, unit: '°' }];
  const sbCog = document.getElementById('sidebarCogReadout');
  if (sbCog) sbCog.readouts = [{ type: 'value', value: Math.round(cogDeg), nDigits: 3, unit: '°' }];
  const sbStw = document.getElementById('sidebarStwReadout');
  if (sbStw) sbStw.readouts = [{ type: 'value', value: Number(sogKnots.toFixed(1)), nDigits: 2, nDecimals: 1, unit: 'kn' }];
  const sbDepth = document.getElementById('sidebarDepthReadout');
  if (sbDepth) {
    sbDepth.readouts = floorDepth === null
      ? []
      : [{ type: 'value', value: floorDepth, nDigits: 3, nDecimals: 0, unit: 'm' }];
    sbDepth.setAttribute('aria-label', floorDepth === null
      ? 'ENC 水深分层数据不可用'
      : `船位 ENC 水深分层下限 ${floorDepth} 米`);
  }

  if (Number.isFinite(nav.latitude)) {
    setText('sidebarLatReadout', formatCoordinate(nav.latitude, 'N', 'S'));
  }
  if (Number.isFinite(nav.longitude)) {
    setText('sidebarLonReadout', formatCoordinate(nav.longitude, 'E', 'W'));
  }

  // 2. Page 0: ROUTE Card
  setText('liveRouteCourse', `${Math.round(headingDeg).toString().padStart(3, '0')}°`);
  const rawRotDegSec = Number.isFinite(os?.r) ? os.r * 180 / Math.PI : null;
  if (rawRotDegSec !== null) {
    const normalizedRotDegSec = Math.abs(rawRotDegSec) < 0.05 ? 0 : rawRotDegSec;
    lastDisplayedRotDegSec = normalizedRotDegSec;
  }
  const rotDegSec = lastDisplayedRotDegSec;
  const rotDegMin = rotDegSec * 60;
  setHtml('liveRouteRot', `${rotDegSec.toFixed(1)}<small>°/s</small>`);
  // Turn radius from ROT: R = v/ω; straight track (|ROT| < 1°/min) has no meaningful radius.
  const yawRate = Math.abs(rotDegSec) * Math.PI / 180;
  const turnRadiusM = Math.abs(rotDegMin) >= 1 && Number.isFinite(nav.sog) && nav.sog > 0.1 && yawRate > 1e-4
    ? nav.sog / yawRate
    : null;
  const routeRadius = formatRouteRadius(turnRadiusM);
  setHtml('liveRouteRadius', routeRadius
    ? `${routeRadius.value}<small> ${routeRadius.unit}</small>`
    : '---');
  updateRouteCard(proj);

  // 3. Page 1: SENSOR Card Instruments
  const liveCompass = document.getElementById('liveCompass');
  if (liveCompass) {
    Object.assign(liveCompass, {
      heading: headingDeg,
      course: cogDeg,
      rotationsPerMinute: rotDegMin / 360,
      direction: document.getElementById('compassMode')?.value || 'northUp',
    });
  }
  const liveHeading = document.getElementById('liveHeadingReadout');
  if (liveHeading) liveHeading.readouts = [{ type: 'value', value: Math.round(headingDeg), nDigits: 3, unit: '°' }];
  const liveCog = document.getElementById('liveCogReadout');
  if (liveCog) liveCog.readouts = [{ type: 'value', value: Math.round(cogDeg), nDigits: 3, unit: '°' }];
  const liveRot = document.getElementById('liveRotReadout');
  if (liveRot) {
    liveRot.readouts = [{ type: 'value', value: Number(rotDegSec.toFixed(1)), nDigits: 2, nDecimals: 1, unit: '°/s' }];
    liveRot.setAttribute('aria-label', `本船转向率 ${rotDegSec.toFixed(1)} 度每秒`);
  }

  const liveSpeedGauge = document.getElementById('liveSpeedGauge');
  if (liveSpeedGauge) {
    Object.assign(liveSpeedGauge, {
      speed: sogKnots,
      minSpeed: -5,
      maxSpeed: 25,
      needleType: 'full',
      priority: 'regular',
      showLabels: true,
      showReadout: true,
      tickmarkInterval: 5,
      speedAdvices: [
        { minSpeed: 15, maxSpeed: 18, type: 'advice', hinted: false },
        { minSpeed: 20, maxSpeed: 25, type: 'caution', hinted: false },
      ],
    });
    liveSpeedGauge.setAttribute('aria-label', `本船对水速度 ${sogKnots.toFixed(1)} 节`);
  }

  const liveDepthActual = document.getElementById('liveDepthActual');
  if (liveDepthActual) {
    liveDepthActual.hidden = floorDepth === null;
    if (floorDepth !== null) {
      const instrumentRange = Math.max(50, 10 ** Math.ceil(Math.log10(Math.max(1, floorDepth))));
      Object.assign(liveDepthActual, {
        depth: floorDepth,
        draft: vesselDraft ?? 0,
        // OpenBridge renders vessel size as vesselScale * 50 / instrumentRange.
        // Compensate the changing range so the on-screen vessel remains stable.
        vesselScale: instrumentRange / 100,
        instrumentRange,
        priority: 'enhanced',
      });
    }
  }
  const liveDraft = document.getElementById('liveDraftReadout');
  if (liveDraft) liveDraft.readouts = vesselDraft === null
    ? []
    : [{ type: 'value', value: vesselDraft, nDigits: 2, nDecimals: 1, unit: 'm' }];
  const liveSafeDepth = document.getElementById('liveSafeDepthReadout');
  if (liveSafeDepth) liveSafeDepth.readouts = safeDepth === null
    ? []
    : [{ type: 'value', value: safeDepth, nDigits: 2, nDecimals: 0, unit: 'm' }];
  const liveCurrentDepth = document.getElementById('liveCurrentDepthReadout');
  if (liveCurrentDepth) {
    liveCurrentDepth.readouts = floorDepth === null
      ? []
      : [{ type: 'value', value: floorDepth, nDigits: 3, nDecimals: 0, unit: 'm' }];
    liveCurrentDepth.title = 'ENC depth-bin lower bound at ownship position';
    liveCurrentDepth.setAttribute('aria-label', floorDepth === null
      ? 'ENC 水深分层数据不可用'
      : `船位 ENC 水深分层下限 ${floorDepth} 米`);
  }

  const livePitchRoll = document.getElementById('livePitchRoll');
  if (livePitchRoll) {
    Object.assign(livePitchRoll, { pitch: 0, roll: 0, priority: 'enhanced' });
  }
  const livePitch = document.getElementById('livePitchReadout');
  if (livePitch) livePitch.readouts = [{ type: 'value', value: 0, nDigits: 1, unit: '°' }];
  const liveRoll = document.getElementById('liveRollReadout');
  if (liveRoll) liveRoll.readouts = [{ type: 'value', value: 0, nDigits: 2, unit: '°' }];
}

let riskDistanceUnit = 'nmi';
let latestMonitorTimelineEvents = [];

function riskThreatLevel(target) {
  return {
    HIGH: 'danger',
    LOW: 'warn',
    CLEAR: 'safe',
  }[String(target?.displayClass || '').toUpperCase()] || 'unknown';
}

function riskStateLabel(target) {
  if (target?.avoidanceActionActive === true) return 'AVOIDING';
  return {
    LOW: 'MONITOR',
    CLEAR: 'SAFE',
    UNKNOWN: 'UNKNOWN',
  }[String(target?.displayClass || '').toUpperCase()] || 'UNKNOWN';
}

const RISK_SCHEDULE_LABELS = {
  CURRENT_PRIMARY: 'PRIMARY',
  CONCURRENT_REQUIRED: 'REQUIRED',
  NEXT: 'NEXT',
  MONITOR: 'MONITOR',
  RELEASED: 'RELEASED',
  HISTORICAL: 'HISTORICAL',
};

function riskScheduleLabel(target) {
  return RISK_SCHEDULE_LABELS[target?.scheduleClass] || (target?.isPrimary ? 'PRIMARY' : 'TARGET');
}

const PRIMARY_SWITCH_STATUS_LABELS = {
  PRIMARY_STABLE: 'STABLE',
  PRIMARY_ACQUIRED: 'ACQUIRED',
  PRIMARY_SWITCH_CONFIRMED: 'SWITCHED',
  PRIMARY_CHALLENGER: 'PENDING',
  HYSTERESIS_PENDING: 'PENDING',
  PREEMPT_CURRENT_DOMAIN_EMERGENCY: 'PREEMPT',
  PREEMPT_RESPONSE_TIME_EMERGENCY: 'PREEMPT',
  PREEMPT_RULE17_MUST_ACT: 'PREEMPT',
};

const PRIMARY_CLASS_LABELS = {
  RESPONSE_TIME_EMERGENCY: 'RESPONSE EMERGENCY',
  RULE17_MUST_ACT: 'RULE 17 MUST ACT',
  COMMITTED_ACTIVE: 'COMMITTED ACTIVE',
  CURRENT_DOMAIN_VIOLATION: 'CURRENT DOMAIN',
  PREDICTED_DOMAIN_VIOLATION: 'PREDICTED DOMAIN',
  FUTURE_SEVERITY: 'FUTURE THREAT',
  CANDIDATE: 'CANDIDATE',
  PAST_CLEAR: 'PAST CLEAR',
};

const PRIMARY_FACTOR_LABELS = {
  HARD_EMERGENCY: 'HARD EMERGENCY',
  RULE17_MUST_ACT: 'RULE 17 PRIORITY',
  COMMITTED_ACTIVE: 'ACTIVE DUTY',
  CURRENT_DOMAIN_VIOLATION: 'CURRENT DOMAIN LEAD',
  PREDICTED_DOMAIN_VIOLATION: 'PREDICTED DOMAIN LEAD',
  FUTURE_SEVERITY: 'SEVERITY LEAD',
  COMPLETENESS: 'EVIDENCE LEAD',
  LIFECYCLE_PHASE: 'LIFECYCLE LEAD',
  TCPA: 'TCPA LEAD',
  DCPA: 'DCPA LEAD',
  RANGE: 'RANGE LEAD',
  TRACK_IDENTITY: 'STABLE TIE-BREAK',
  ONLY_ELIGIBLE_TARGET: 'ONLY TARGET',
  HYSTERESIS_HOLD: 'HYSTERESIS HOLD',
};

function primarySelectionStatus(selection) {
  return PRIMARY_SWITCH_STATUS_LABELS[selection?.switchReason] || 'STATUS UNKNOWN';
}

function primarySelectionExplanation(selection, target) {
  if (selection?.challenger?.target_id !== null && selection?.challenger?.target_id !== undefined) {
    const remaining = Number.isFinite(selection.confirmationRemainingS)
      ? ` · ${selection.confirmationRemainingS.toFixed(1)}s`
      : '';
    return {
      summary: `CHALLENGER TS${selection.challenger.target_id}${remaining}`,
      detail: 'SWITCH PENDING',
    };
  }
  const summary = PRIMARY_CLASS_LABELS[selection?.winningClass]
    || PRIMARY_CLASS_LABELS[target?.priorityClass]
    || 'PRIORITY UNAVAILABLE';
  const detail = PRIMARY_FACTOR_LABELS[selection?.decisiveFactor] || 'BASIS UNAVAILABLE';
  const redundantEmergency = (
    selection?.winningClass === 'RESPONSE_TIME_EMERGENCY'
      && selection?.decisiveFactor === 'HARD_EMERGENCY'
  ) || (
    selection?.winningClass === 'RULE17_MUST_ACT'
      && selection?.decisiveFactor === 'RULE17_MUST_ACT'
  );
  return {
    summary,
    detail: redundantEmergency ? '' : detail,
  };
}

function formatRiskDistance(distanceM, unit = riskDistanceUnit) {
  if (!Number.isFinite(distanceM)) return unit === 'nmi' ? '--- NM' : '--- km';
  return unit === 'nmi'
    ? `${(distanceM / METERS_PER_NAUTICAL_MILE).toFixed(2)} NM`
    : `${(distanceM / 1000).toFixed(2)} km`;
}

function refreshRiskDistanceButtons() {
  document.querySelectorAll('.risk-distance-toggle').forEach((button) => {
    const distanceM = button.dataset.distanceM === '' ? NaN : Number(button.dataset.distanceM);
    button.dataset.unit = riskDistanceUnit;
    button.textContent = formatRiskDistance(distanceM);
    button.disabled = !Number.isFinite(distanceM);
    button.title = riskDistanceUnit === 'nmi' ? 'Click to show kilometres' : 'Click to show nautical miles';
  });
}

function eventDisplayContent(event) {
  const details = event.details || {};
  const target = details.targetLabel || (details.target_id !== undefined ? `TS${details.target_id}` : '');
  const contextLabel = (value) => String(value || '').replaceAll('_', ' ');
  const reasonLabel = (value) => String(value || '').replaceAll('_', ' ');
  const transitionLabel = (from, to) => [from, to].filter(Boolean).map(contextLabel).join(' → ');
  const lifecycleStateLabel = (value) => {
    const state = String(value || '');
    if (state.includes('ACTIVE') || state.includes('COMMITTED')) return 'AVOIDING';
    if (state.includes('PAST_CLEAR')) return 'CLEARING';
    if (state.includes('RELEASED')) return 'RELEASED';
    if (state.includes('CANDIDATE') || state.includes('MONITORING')) return 'MONITOR';
    if (state.includes('CLEAR')) return 'SAFE';
    return contextLabel(state);
  };
  const riskEvidence = () => [
    Number.isFinite(details.dcpa_m) ? `DCPA ${details.dcpa_m.toFixed(1)} m` : '',
    Number.isFinite(details.tcpa_s) ? `TCPA ${details.tcpa_s.toFixed(1)} s` : '',
  ].filter(Boolean).join(' · ');
  const withEvidence = (...parts) => [...parts.filter(Boolean), riskEvidence()].filter(Boolean).join(' · ');
  const content = ({ eventType, status = '', subject = '', detail = '', cardTone = 'info', statusTone = cardTone }) => ({
    title: [eventType, status].filter(Boolean).join(' '),
    description: [subject, detail].filter(Boolean).join('  '),
    eventType,
    status,
    subject,
    detail,
    cardTone,
    statusTone,
  });
  switch (event.type) {
    case 'planner_solved':
      return content({
        eventType: 'Planner solution',
        status: details.status || '',
        subject: `#${details.solve_id ?? '—'}`,
        detail: typeof details.feasible === 'boolean' ? (details.feasible ? 'feasible' : 'infeasible') : '',
      });
    case 'colregs_change': {
      const from = details.from ? (ENCOUNTER_LABELS[details.from] || details.from) : 'Clear';
      const to = details.to ? (ENCOUNTER_LABELS[details.to] || details.to) : 'Clear';
      const cleared = details.to === 'clear';
      return content({
        eventType: 'COLREGs',
        status: cleared ? 'Clear' : 'Hold',
        subject: target,
        detail: cleared ? `${from} → Clear` : to,
        cardTone: 'info',
        statusTone: cleared ? 'safe' : 'warning',
      });
    }
    case 'dcpa_level_change': {
      const status = String(details.level || 'unknown').toUpperCase();
      return content({
        eventType: 'DCPA',
        status,
        subject: target,
        detail: Number.isFinite(details.dcpaM) ? `${details.dcpaM.toFixed(1)} m closest approach` : 'Closest approach updated',
        cardTone: 'info',
        statusTone: status === 'DANGER' ? 'danger' : status === 'WARN' ? 'warning' : 'safe',
      });
    }
    case 'threat_entered':
      return content({
        eventType: 'Threat',
        status: contextLabel(details.to_context || 'ENTERED'),
        subject: target,
        detail: withEvidence(reasonLabel(details.reason)),
        cardTone: details.to_context === 'CURRENT_PRIMARY' ? 'danger' : 'warning',
      });
    case 'threat_escalated':
      return content({
        eventType: 'Threat',
        status: 'ESCALATED',
        subject: target,
        detail: withEvidence(transitionLabel(details.from_context, details.to_context) || reasonLabel(details.reason)),
        cardTone: 'warning',
      });
    case 'threat_clearing':
      return content({
        eventType: 'Threat',
        status: 'CLEARING',
        subject: target,
        detail: transitionLabel(details.from_context, details.to_context),
        cardTone: 'safe',
      });
    case 'threat_released':
      return content({
        eventType: 'Threat',
        status: 'RELEASED',
        subject: target,
        detail: withEvidence(reasonLabel(details.reason)),
        cardTone: 'safe',
      });
    case 'primary_switched': {
      const from = details.from_target_id === undefined ? '--' : `TS${details.from_target_id}`;
      const to = details.to_target_id === undefined ? (target || '--') : `TS${details.to_target_id}`;
      return content({
        eventType: 'Primary',
        status: 'SWITCHED',
        subject: `${from} → ${to}`,
        detail: withEvidence(reasonLabel(details.reason)),
        cardTone: 'warning',
      });
    }
    case 'schedule_reorder':
      return content({
        eventType: 'Threat schedule',
        status: contextLabel(details.to_context || 'UPDATED'),
        subject: target,
        detail: transitionLabel(details.from_context, details.to_context) || reasonLabel(details.reason),
      });
    case 'target_transition': {
      const toState = String(details.to_state || '');
      const fromSummary = lifecycleStateLabel(details.from_state);
      const toSummary = lifecycleStateLabel(toState);
      const sameSummaryChanged = fromSummary && fromSummary === toSummary && details.from_state !== details.to_state;
      const stateTransition = sameSummaryChanged
        ? transitionLabel(
          String(details.from_state || '').replaceAll('/', ' · '),
          String(details.to_state || '').replaceAll('/', ' · '),
        )
        : fromSummary ? `${fromSummary} → ${toSummary}` : '';
      return content({
        eventType: 'Risk state',
        status: toSummary || 'UPDATED',
        subject: target,
        detail: withEvidence(stateTransition),
        cardTone: toSummary === 'AVOIDING' ? 'danger' : ['CLEARING', 'RELEASED', 'SAFE'].includes(toSummary) ? 'safe' : 'warning',
      });
    }
    case 'risk_level_changed': {
      const to = String(details.to_display_class || details.display_class || 'UNKNOWN').toUpperCase();
      return content({
        eventType: 'Risk',
        status: to,
        subject: target,
        detail: withEvidence(transitionLabel(details.from_display_class, details.to_display_class)),
        cardTone: to === 'HIGH' ? 'danger' : to === 'CLEAR' ? 'safe' : 'warning',
      });
    }
    case 'colregs_changed':
      return content({
        eventType: 'COLREGs',
        status: 'UPDATED',
        subject: target,
        detail: transitionLabel(details.from_encounter, details.to_encounter),
        cardTone: details.to_encounter === 'CLEAR' ? 'safe' : 'warning',
      });
    case 'observation_degraded':
      return content({
        eventType: 'Observation',
        status: contextLabel(details.to_health || 'DEGRADED'),
        subject: target,
        detail: transitionLabel(details.from_health, details.to_health),
        cardTone: details.to_health === 'UNUSABLE' ? 'danger' : 'warning',
      });
    case 'observation_recovered':
      return content({
        eventType: 'Observation',
        status: 'RECOVERED',
        subject: target,
        detail: transitionLabel(details.from_health, details.to_health),
        cardTone: 'safe',
      });
    case 'avoidance_action_started':
      return content({
        eventType: 'Avoidance',
        status: 'ACTIVE',
        subject: target,
        detail: withEvidence([contextLabel(details.encounter), contextLabel(details.role)].filter(Boolean).join(' · ')),
        cardTone: 'danger',
      });
    case 'avoidance_action_ended':
      return content({
        eventType: 'Avoidance',
        status: 'RECOVERY',
        subject: target,
        detail: 'Collision-avoidance action released',
        cardTone: 'safe',
      });
    case 'threat_lifecycle_active':
      return content({
        eventType: 'Threat lifecycle',
        status: 'ACTIVE',
        subject: target,
        detail: 'Canonical avoidance duty active',
        cardTone: 'danger',
      });
    case 'algorithm_handoff':
      return content({
        eventType: 'Algorithm handoff',
        status: 'ACTIVE',
        detail: reasonLabel(details.trigger || 'Lifecycle active'),
        cardTone: 'warning',
      });
    case 'historical_recovery_complete':
      return content({ eventType: 'Historical recovery', status: 'COMPLETE', detail: reasonLabel(details.reason), cardTone: 'safe' });
    case 'historical_handoff_not_triggered':
      return content({ eventType: 'Algorithm handoff', status: 'NOT TRIGGERED', detail: reasonLabel(details.reason), cardTone: 'warning' });
    case 'planner_failed':
      return content({
        eventType: 'Planner',
        status: 'FAILED',
        subject: `#${details.solve_id ?? '—'}`,
        detail: details.failure_code || details.reason || details.status || 'Plan unavailable',
        cardTone: 'danger',
      });
    case 'planner_recovered':
      return content({
        eventType: 'Planner',
        status: 'RECOVERED',
        subject: `#${details.solve_id ?? '—'}`,
        detail: details.status || 'Feasible plan restored',
        cardTone: 'safe',
      });
    case 'collision':
      return content({
        eventType: 'Collision',
        status: 'DANGER',
        subject: target || `Ship ${details.ship_id ?? '—'}`,
        detail: 'Collision detected',
        cardTone: 'danger',
        statusTone: 'danger',
      });
    case 'grounding':
      return content({
        eventType: 'Grounding',
        status: 'DANGER',
        subject: `Ship ${details.ship_id ?? '—'}`,
        detail: 'Grounding detected',
        cardTone: 'danger',
        statusTone: 'danger',
      });
    case 'time_limit':
      return content({ eventType: 'Simulation', status: 'Time limit', detail: 'Run stopped at configured duration' });
    case 'goal_reached':
      return content({
        eventType: 'Avoidance',
        status: 'Complete',
        subject: `Ship ${details.ship_id ?? '—'}`,
        detail: 'Mission route reached',
        cardTone: 'safe',
        statusTone: 'safe',
      });
    case 'session_started':
      return content({ eventType: 'Simulation', status: 'Started', detail: 'Session is ready for monitoring' });
    case 'session_resumed':
      return content({ eventType: 'Simulation', status: 'Resumed', detail: 'Execution resumed' });
    case 'session_paused':
      return content({ eventType: 'Simulation', status: 'Paused', detail: 'Manual pause' });
    case 'session_reset':
      return content({ eventType: 'Simulation', status: 'Reset', detail: 'New session created from immutable Run Specification' });
    case 'session_replayed':
      return content({ eventType: 'Simulation', status: 'Replay', detail: 'Replay session created from source run' });
    case 'session_finished':
      return content({ eventType: 'Simulation', status: 'Finished', detail: 'Session completed' });
    case 'session_failed':
      return content({
        eventType: 'Simulation',
        status: 'Failed',
        detail: details.reason || 'Runtime failure',
        cardTone: 'danger',
        statusTone: 'danger',
      });
    default:
      return content({
        eventType: String(event.type || 'simulation_event').replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()),
        subject: target || (details.ship_id !== undefined ? `Ship ${details.ship_id}` : ''),
        detail: 'Simulation event',
      });
  }
}

const MONITOR_HIDDEN_EVENT_TYPES = new Set(['planner_solved']);

function visibleMonitorEvents(events) {
  return (Array.isArray(events) ? events : []).filter((event) => (
    !MONITOR_HIDDEN_EVENT_TYPES.has(event?.type)
    && event?.type !== 'primary_challenger'
    && !(event?.type === 'schedule_reorder'
      && event?.details?.reason === 'deterministic_track_key_order_changed')
  ));
}

function monitorEventTone(event) {
  return eventDisplayContent(event).cardTone;
}

function monitorToneColor(tone) {
  return tone === 'danger'
    ? 'var(--alert-alarm-color, #d82828)'
    : tone === 'warning'
      ? 'var(--alert-warning-color, #b87800)'
      : tone === 'safe'
        ? 'var(--alert-success-color, #16804b)'
        : 'var(--ob-accent-mid, #5d8fd5)';
}

function decorateMonitorEventItems(eventList, events) {
  const eventItems = [...(eventList.shadowRoot?.querySelectorAll('obc-event-item') || [])];
  eventItems.forEach((item, index) => {
    const event = events[index];
    const presentation = event ? eventDisplayContent(event) : null;
    const tone = event ? monitorEventTone(event) : 'info';
    const statusTone = presentation?.statusTone || 'info';
    const accent = monitorToneColor(tone);
    const statusAccent = monitorToneColor(statusTone);
    const background = `color-mix(in srgb, ${accent} 8%, var(--ob-surface, #ffffff))`;
    const border = `color-mix(in srgb, ${accent} 38%, var(--ob-border, #dddddd))`;
    item.dataset.eventTone = tone;
    item.dataset.eventStatusTone = statusTone;
    item.style.setProperty('--flat-enabled-background-color', background);
    item.style.setProperty('--flat-enabled-border-color', border);
    item.style.setProperty('--flat-hover-background-color', background);
    item.style.setProperty('--flat-hover-border-color', border);
    const shadow = item.shadowRoot;
    const wrapper = shadow?.querySelector('.wrapper');
    const visibleWrapper = shadow?.querySelector('.visible-wrapper');
    const content = shadow?.querySelector('.event-content');
    const title = shadow?.querySelector('.title');
    const description = shadow?.querySelector('.description');
    if (wrapper) wrapper.classList.remove('type-color-coded');
    if (visibleWrapper) {
      visibleWrapper.style.background = background;
      visibleWrapper.style.borderColor = border;
      visibleWrapper.style.borderLeft = `3px solid ${accent}`;
      visibleWrapper.style.padding = '8px 10px 6px';
      visibleWrapper.style.minHeight = '64px';
    }
    if (content) content.style.justifyContent = 'space-between';
    if (title) {
      title.style.color = 'var(--ob-text, #1f1f1f)';
      title.style.fontSize = '12px';
      title.style.fontWeight = '650';
      title.style.lineHeight = '17px';
      title.style.whiteSpace = 'normal';
      title.style.overflow = 'visible';
      title.style.textOverflow = 'clip';
      title.style.display = 'block';
      if (presentation) {
        const header = document.createElement('span');
        header.className = 'event-title-line';
        header.style.display = 'block';
        header.style.whiteSpace = 'nowrap';
        const eventType = document.createElement('span');
        eventType.className = 'event-type';
        eventType.textContent = presentation.eventType;
        header.append(eventType);
        if (presentation.status) {
          const status = document.createElement('span');
          status.className = 'event-status';
          status.textContent = ` ${presentation.status}`;
          status.style.color = statusAccent;
          status.style.fontWeight = '750';
          header.append(status);
        }
        const body = document.createElement('span');
        body.className = 'event-body-line';
        body.style.display = 'flex';
        body.style.flexWrap = 'wrap';
        body.style.columnGap = '10px';
        body.style.rowGap = '2px';
        body.style.marginTop = '3px';
        body.style.fontSize = '11px';
        body.style.fontWeight = '500';
        body.style.lineHeight = '15px';
        if (presentation.subject) {
          const subject = document.createElement('span');
          subject.className = 'event-subject';
          subject.textContent = presentation.subject;
          subject.style.fontWeight = '700';
          body.append(subject);
        }
        if (presentation.detail) {
          const detail = document.createElement('span');
          detail.className = 'event-detail';
          detail.textContent = presentation.detail;
          body.append(detail);
        }
        title.replaceChildren(header, body);
      }
    }
    if (description) {
      description.style.color = 'var(--ob-subtle, #707070)';
      description.style.fontFamily = 'var(--font-mono)';
      description.style.fontSize = '9px';
      description.style.lineHeight = '13px';
      description.style.textAlign = 'right';
      description.style.whiteSpace = 'nowrap';
    }
  });
}

function renderMonitorEventList(events) {
  latestMonitorTimelineEvents = Array.isArray(events) ? events : [];
  const visibleEvents = visibleMonitorEvents(latestMonitorTimelineEvents).slice().reverse();
  setText('liveEventCount', String(visibleEvents.length));
  const eventList = document.getElementById('liveEvents');
  if (!eventList || !customElements.get('obc-event-list')) return;
  eventList.showHeader = false;
  eventList.events = visibleEvents.length
    ? visibleEvents.map((event) => {
        const content = eventDisplayContent(event);
        const startTime = Number.isFinite(event.simTime) ? formatDuration(event.simTime) : '--:--:--';
        return {
          title: [content.title, content.description].filter(Boolean).join(' · '),
          description: startTime,
          startTime,
          endTime: '',
          eventItemType: 'doubleLine',
          hasTime: false,
          hasEndTime: false,
          hasArrow: false,
          colorCoded: false,
        };
      })
    : [{
        title: 'Waiting for simulation events',
        description: '--:--:--',
        startTime: '--:--:--',
        endTime: '',
        eventItemType: 'doubleLine',
        hasTime: false,
        hasEndTime: false,
        hasArrow: false,
        disabled: true,
      }];
  const decorate = () => decorateMonitorEventItems(eventList, visibleEvents);
  decorate();
  eventList.updateComplete?.then(() => {
    const itemUpdates = [...(eventList.shadowRoot?.querySelectorAll('obc-event-item') || [])]
      .map((item) => item.updateComplete)
      .filter(Boolean);
    Promise.all(itemUpdates).then(decorate);
  });
}

function renderNotificationCenter(events) {
  const visibleEvents = visibleMonitorEvents(events);
  const button = document.getElementById('alertBtn');
  const items = document.getElementById('notificationItems');
  setText('notificationPanelCount', String(visibleEvents.length));
  if (button && customElements.get('obc-notification-button')) {
    button.count = Math.min(visibleEvents.length, 99);
    button.showCount = visibleEvents.length > 0;
  }
  if (!items || !customElements.get('obc-notification-message-item')) return;
  const recentEvents = visibleEvents.slice(-6).reverse();
  if (!recentEvents.length) {
    const empty = document.createElement('obc-notification-message-item');
    Object.assign(empty, {
      type: 'inactive',
      emptyText: 'No current-session notifications',
    });
    empty.setAttribute('role', 'listitem');
    items.replaceChildren(empty);
    return;
  }
  items.replaceChildren(...recentEvents.map((event) => {
    const content = eventDisplayContent(event);
    const item = document.createElement('obc-notification-message-item');
    Object.assign(item, {
      type: 'simple',
      size: 'regular',
      title: content.title,
      description: content.description,
      time: Number.isFinite(event.simTime) ? formatDuration(event.simTime) : '--:--:--',
      showTitle: true,
      showDescription: true,
      showTimestamp: true,
    });
    item.setAttribute('role', 'listitem');
    return item;
  }));
}

function setupNotificationCenter() {
  const button = document.getElementById('alertBtn');
  const panel = document.getElementById('notificationPanel');
  if (!button || !panel || button.dataset.bound === 'true') return;
  button.dataset.bound = 'true';
  Object.assign(button, {
    buttonStyle: 'normal',
    ariaLabel: 'Notifications',
    isActive: false,
  });
  const close = () => {
    panel.hidden = true;
    button.isActive = false;
  };
  button.addEventListener('obc-click', (event) => {
    event.stopPropagation();
    const open = panel.hidden;
    panel.hidden = !open;
    button.isActive = open;
  });
  panel.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('click', (event) => {
    if (!panel.hidden && !panel.contains(event.target) && !event.composedPath().includes(button)) close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || panel.hidden) return;
    close();
    (button.shadowRoot?.querySelector('button') || button).focus();
  });
  renderNotificationCenter(latestMonitorTimelineEvents);
}

function updateMonitorTelemetry(proj) {
  latestMonitorProjection = proj;
  if (selectedVesselTarget) {
    const isOwnship = String(selectedVesselTarget.id) === '0';
    const freshVessel = isOwnship
      ? proj.raw?.os
      : (proj.raw?.obstacles || []).find(vessel => String(vessel.id) === String(selectedVesselTarget.id));
    const anchor = isOwnship
      ? latestOwnshipMarker?.anchor
      : latestVesselMarkers.find(marker => String(marker.id) === String(selectedVesselTarget.id))?.anchor;
    if (freshVessel && anchor) showVesselPlacard(freshVessel, { anchor });
  }
  const historicalContext = proj.raw?.historical_context;
  setText(
    'liveContextCount',
    historicalContext
      ? `${historicalContext.active_actor_count}/${historicalContext.total_actor_count} ACTIVE`
      : '',
  );
  const container = document.getElementById('liveRiskTargetList');
  if (container) {
    const targets = proj.risk?.targets || [];
    if (proj.risk?.status !== 'AVAILABLE') {
      container.innerHTML = `
        <article class="risk-target-card" data-priority="none">
          <div class="risk-target-heading"><span>Threat Management</span><strong>不可用</strong></div>
          <p style="margin:0;font-size:10px;color:var(--ob-subtle);">${proj.risk?.unavailableReason || '等待后端威胁事实。'}</p>
        </article>
      `;
    } else if (!targets.length) {
      container.innerHTML = `
        <article class="risk-target-card" data-priority="none">
          <div class="risk-target-heading"><span>Threat Management</span><strong>无目标</strong></div>
          <p style="margin:0;font-size:10px;color:var(--ob-subtle);">后端未发布当前威胁向量。</p>
        </article>
      `;
    } else {
      const historicalById = new Map((proj.raw?.obstacles || []).map(target => [String(target.id), target]));
      container.innerHTML = targets.map((t) => {
        const isHighest = t.isPrimary === true;
        const threatLevel = riskThreatLevel(t);
        const riskState = riskStateLabel(t);
        const dcpaText = t.dcpaM !== null ? `${t.dcpaM.toFixed(1)}` : '---';
        const tcpaText = t.tcpaS !== null ? `${t.tcpaS.toFixed(1)}` : '---';
        const colregLabel = t.encounter ? (ENCOUNTER_LABELS[t.encounter] || t.encounter) : '--';
        const priorityLabel = riskScheduleLabel(t);
        const primaryStatus = isHighest ? primarySelectionStatus(proj.risk.primarySelection) : '';
        const explanation = isHighest
          ? primarySelectionExplanation(proj.risk.primarySelection, t)
          : t.scheduleClass === 'CONCURRENT_REQUIRED'
            ? { summary: 'ACTIVE COLREG OBLIGATION', detail: '' }
            : null;
        const explanationMarkup = explanation
          ? `<div class="risk-target-explanation"><span>${explanation.summary}</span>${explanation.detail ? `<strong>${explanation.detail}</strong>` : ''}</div>`
          : '';
        const historical = historicalById.get(String(t.targetId)) || {};
        const sampleKind = historical.historical_sample_kind || '--';
        const dimensions = String(historical.dimensions_provenance || '').includes('ASSUMED') ? 'ASSUMED' : 'PROVEN';
        return `
          <article class="risk-target-card" data-threat="${threatLevel}" data-schedule="${t.scheduleClass || 'UNKNOWN'}" ${isHighest ? 'data-priority="highest"' : ''}>
            <div class="risk-target-heading"><span>${priorityLabel}${primaryStatus ? `<em>${primaryStatus}</em>` : ''}</span><strong>${t.targetLabel || (t.targetId === null ? '--' : `TS${t.targetId}`)}</strong></div>
            ${explanationMarkup}
            <div class="risk-target-metrics">
              <div class="risk-target-metric"><span>DCPA</span><strong>${dcpaText}<small>m</small></strong></div>
              <div class="risk-target-metric"><span>TCPA</span><strong>${tcpaText}<small>s</small></strong></div>
            </div>
            <dl class="risk-target-facts">
              <div><dt>COLREGs Rule</dt><dd class="colreg-value">${colregLabel}</dd></div>
              <div><dt>Risk state</dt><dd>${riskState}</dd></div>
              <div><dt>Target range</dt><dd><button type="button" class="risk-distance-toggle" data-distance-m="${t.distanceM ?? ''}" data-unit="${riskDistanceUnit}" ${Number.isFinite(t.distanceM) ? '' : 'disabled'}>${formatRiskDistance(t.distanceM)}</button></dd></div>
              <div><dt>AIS state</dt><dd>${sampleKind}</dd></div>
              <div><dt>Hull dimensions</dt><dd>${dimensions}</dd></div>
            </dl>
          </article>
        `;
      }).join('');
    }
  }

  const shadow = proj.raw?.shadow_comparison;
  const shadowPanel = document.getElementById('shadowComparisonPanel');
  const shadowValues = document.getElementById('shadowComparisonValues');
  const shadowEmpty = document.getElementById('shadowComparisonEmpty');
  const shadowStatus = document.getElementById('shadowComparisonStatus');
  const sessionSpec = deploymentRuntimeSnapshot.session?.spec;
  const isHistoricalAisScenario = Boolean(sessionSpec?.historical_scenario_id);
  const shadowMetricsAvailable = isHistoricalAisScenario
    && ['AVAILABLE', 'INACTIVE / DATA GAP'].includes(shadow?.status)
    && [
      shadow?.deviation_m,
      shadow?.maximum_deviation_m,
      shadow?.delta_cog_rad,
      shadow?.delta_sog_mps,
    ].every(Number.isFinite);
  if (shadowPanel) shadowPanel.hidden = false;
  if (shadowValues) shadowValues.hidden = !shadowMetricsAvailable;
  if (shadowEmpty) {
    shadowEmpty.hidden = shadowMetricsAvailable;
    shadowEmpty.textContent = isHistoricalAisScenario
      ? 'Waiting for historical AIS comparison data.'
      : 'Available in AIS Historical sessions only.';
  }
  if (shadowStatus) {
    shadowStatus.dataset.state = shadowMetricsAvailable
      ? (shadow.status === 'AVAILABLE' ? 'available' : 'data-gap')
      : 'unavailable';
  }
  if (shadowMetricsAvailable) {
    setText('shadowComparisonStatus', shadow.status === 'AVAILABLE' ? 'COMPARISON ONLY' : shadow.status);
    setText('shadowDeviation', Number(shadow.deviation_m).toFixed(1));
    setText('shadowMaximumDeviation', Number(shadow.maximum_deviation_m).toFixed(1));
    setText('shadowDeltaCog', (Number(shadow.delta_cog_rad) * 180 / Math.PI).toFixed(1));
    setText('shadowDeltaSog', (Number(shadow.delta_sog_mps) / 0.514444).toFixed(1));
    setText('shadowRecovery', shadow.recovery?.status || 'NOT STARTED');
  } else {
    setText('shadowComparisonStatus', isHistoricalAisScenario ? 'WAITING' : 'NOT APPLICABLE');
    setText('shadowDeviation', '');
    setText('shadowMaximumDeviation', '');
    setText('shadowDeltaCog', '');
    setText('shadowDeltaSog', '');
    setText('shadowRecovery', '');
  }

  renderMonitorEventList(proj.timeline?.events || []);
  renderNotificationCenter(proj.timeline?.events || []);
}

function updateAlgoTelemetry(proj) {
  const planner = proj.planner || {};
  const statusBadge = document.getElementById('plannerSolveState');
  if (statusBadge) {
    const isRunning = proj.state === 'RUNNING';
    statusBadge.textContent = isRunning ? (planner.feasible ? 'SUCCESS' : 'RUNNING') : (proj.state || '待运行');
    statusBadge.style.color = planner.feasible ? 'var(--alert-success-color, #16804b)' : 'var(--alert-warning-color, #b87800)';
    statusBadge.style.borderColor = planner.feasible ? 'var(--alert-success-color, #16804b)' : 'var(--alert-warning-color, #b87800)';
  }
  setText('topRunState', proj.state || '未创建');
  setText('liveSolveStatus', planner.status || (planner.feasible ? 'SUCCESS' : 'IDLE'));
  setText('liveSolutionId', `#${planner.solveId || 0}`);
  setText('liveAlgorithm', planner.algorithmId || '--');

  setText('liveHorizonSteps', planner.horizonLength || 0);
  setText('liveStepInterval', `${(planner.horizonDtS || 5.0).toFixed(1)}`);
  const previewSog = proj.navigation?.sog;
  setText('liveTrajectoryKnots', Number.isFinite(previewSog) ? (previewSog * 1.94384).toFixed(1) : '--');
  setText('liveExecHeading', planner.appliedCourseRefRad ? `${(planner.appliedCourseRefRad * 180 / Math.PI).toFixed(1)}` : '0.0');
  setText('liveExecSpeed', planner.appliedSpeedRefMps ? `${planner.appliedSpeedRefMps.toFixed(2)}` : '0.00');
  setText('liveTrackingError', '0.11');

  setText('liveOptimalCost', planner.display?.cost ? planner.display.cost.toFixed(2) : (planner.feasible ? '12.20' : '--'));
  setText('liveSolutionPeriod', `${(planner.solvePeriodS || 10.0).toFixed(1)}`);
  setText('liveLateralOffset', planner.display?.lateral_offset ? `${planner.display.lateral_offset.toFixed(2)}` : '0.00');
  setText('liveRollingPlan', 'KEEP');
  setText('liveReturnDrift', '0.0');

}

function updateCostSparkline() {
  const graph = document.getElementById('liveCostGraph');
  if (!graph) return;
  const history = solveTimeline.filter(item => Number.isFinite(item.objective));
  graph.setSeries(
    history.map(item => item.objective),
    history.map(item => item.solveId),
  );
}

function updatePerfSparkline() {
  const graph = document.getElementById('livePerfGraph');
  if (!graph) return;
  graph.setSeries(perfHistory);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function setHtml(id, val) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = val;
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
  const rateGroup = document.getElementById('livePlaybackRate');
  if (rateGroup && Number.isFinite(requested)) rateGroup.value = String(requested);
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

function setThreatClass(el, displayClass) {
  el.classList.remove('safe', 'warn', 'danger');
  const level = String(displayClass || '').toUpperCase();
  if (level === 'HIGH') el.classList.add('danger');
  else if (level === 'LOW') el.classList.add('warn');
  else if (level === 'CLEAR') el.classList.add('safe');
}

function setThreatBar(id, displayPercent, displayClass) {
  const bar = document.getElementById(id);
  if (!bar) return;
  const percent = Number.isFinite(displayPercent) ? Math.max(0, Math.min(100, displayPercent)) : 0;
  const level = String(displayClass || '').toUpperCase();
  bar.style.width = `${percent}%`;
  bar.style.background = level === 'CLEAR' ? 'var(--risk-safe)'
                       : level === 'LOW' ? 'var(--risk-warn)'
                                         : level === 'HIGH' ? 'var(--risk-danger)' : 'var(--ob-subtle)';
}

function updateColregsBadge(rule) {
  const badge     = document.getElementById('val-colregs');
  if (!badge) return;
  const label = rule ? (ENCOUNTER_LABELS[rule] || rule) : '--';
  badge.textContent = label;
  badge.className   = 'colregs-badge';
  if      (rule === 'head_on')          badge.classList.add('rule-14');
  else if (rule === 'crossing_give_way') badge.classList.add('rule-15-giveway');
  else if (rule === 'crossing_stand_on') badge.classList.add('rule-15-standon');
  else if (rule === 'overtaking')        badge.classList.add('rule-13');
  else if (rule)                         badge.classList.add('clear');
  else                                   badge.classList.add('unknown');
}

function updatePlannerPanel(proj) {
  const state = proj.planner;
  const diagnosticPlanner = state.display || {};
  const details = diagnosticPlanner.algorithm_details || {};
  const predictionEvidence = proj.raw?.plans?.prediction_render || null;
  syncPlannerSurfaceMode(diagnosticPlanner);
  const solveId = Number(state.solveId || 0);
  const realSolve = state.phase === 'SOLVE';
  const mode = document.getElementById('val-solver-executed');
  if (mode) {
    mode.textContent = realSolve ? 'SOLVE' : 'HOLD';
    mode.classList.toggle('solve', realSolve);
    mode.classList.toggle('hold', !realSolve);
  }

  setText('val-solve-id', `#${solveId}`);
  const solverSuccessful = state.feasible !== false
    && ['SUCCESS', 'TIMEOUT_FEASIBLE'].includes(state.status || 'SUCCESS');
  setText('val-solver-state', solverSuccessful ? '成功' : '失败');

  const horizonLength = state.horizonLength;
  const horizonIntervals = details.control_intervals ?? horizonLength;
  const gridShape = Array.isArray(details.grid_shape) ? details.grid_shape : [];
  const horizonTime = diagnosticPlanner.algorithm_id === 'vo' && gridShape.length === 2
    ? `决策网格 ${gridShape[0]}×${gridShape[1]}`
    : Number.isFinite(predictionEvidence?.grid?.dt_s)
      ? `${horizonIntervals} × ${predictionEvidence.grid.dt_s.toFixed(1)}s · ${predictionEvidence.grid.state_samples} knots`
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
  setText(
    'val-evidence-source',
    predictionEvidence
      ? `${predictionEvidence.trajectory_source || '--'} · ${predictionEvidence.style || '--'}`
      : '--',
  );
  setText(
    'val-planner-l4',
    predictionEvidence?.planner_l4?.accepted === true
      ? 'PASS'
      : predictionEvidence?.planner_l4?.accepted === false
        ? 'FAIL'
        : '--',
  );
  const evaluator = predictionEvidence?.evaluator_g3;
  setText(
    'val-evaluator-g3',
    evaluator
      ? evaluator.hard_gate_passed === true || evaluator.status === 'PASS'
        ? 'PASS'
        : 'FAIL'
      : '--',
  );
  const quality = predictionEvidence?.quality || {};
  setText(
    'val-course-span',
    Number.isFinite(quality.course_span_rad)
      ? `${(quality.course_span_rad * 180 / Math.PI).toFixed(2)}°`
      : '--°',
  );
  setText(
    'val-speed-span',
    Number.isFinite(quality.speed_span_mps) ? `${quality.speed_span_mps.toFixed(3)} m/s` : '-- m/s',
  );
  setText(
    'val-lateral-deviation',
    Number.isFinite(quality.lateral_deviation_m) ? `${quality.lateral_deviation_m.toFixed(2)} m` : '-- m',
  );
  const rollingPlan = details.rolling_plan || {};
  const rollingReference = rollingPlan.reference || {};
  const rollingAssessment = rollingPlan.assessment || {};
  const prefixContinuity = rollingAssessment.prefix || {};
  setText(
    'val-rolling-plan',
    rollingReference.active && rollingAssessment.accepted
      ? '保持'
      : rollingAssessment.revision_reason || '--',
  );
  setText(
    'val-prefix-continuity',
    Number.isFinite(prefixContinuity.heading_rms_deg) && Number.isFinite(prefixContinuity.position_max_m)
      ? `${prefixContinuity.heading_rms_deg.toFixed(1)}° · ${prefixContinuity.position_max_m.toFixed(1)} m`
      : '--',
  );
  setText(
    'val-recovery-drift',
    Number.isFinite(rollingAssessment.recovery_time_drift_s)
      ? `${rollingAssessment.recovery_time_drift_s.toFixed(1)} s`
      : '-- s',
  );
  setText(
    'val-ipopt-time',
    Number.isFinite(details.ipopt_elapsed_ms)
      ? `${details.ipopt_elapsed_ms.toFixed(2)} ms${Number.isFinite(details.ipopt_iterations) ? ` · ${details.ipopt_iterations} it` : ''}`
      : '-- ms',
  );
  setText(
    'val-graph-build-time',
    Number.isFinite(details.graph_build_elapsed_ms)
      ? `${details.graph_build_elapsed_ms.toFixed(2)} ms`
      : '-- ms',
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
    updateCostSparkline();
  }
}

function drawPlannerSurface(planner) {
  const canvas = document.getElementById('plannerSurface');
  if (!canvas) return;
  const backingW = Math.max(80, Math.round(canvas.clientWidth || 260));
  const backingH = Math.max(60, Math.round(canvas.clientHeight || 148));
  if (canvas.width !== backingW || canvas.height !== backingH) {
    canvas.width = backingW;
    canvas.height = backingH;
  }
  const surface = canvas.getContext('2d');
  const algorithmId = planner.algorithm_id;
  const details = planner.algorithm_details || {};
  const isVO = algorithmId === 'vo';
  const isMidMPC = algorithmId === 'mid_mpc_ipopt';
  const isFanMPC = algorithmId === 'potocnik_colreg_fan_mpc';
  const matrix = details.candidate_costs;
  const selectionMatrix = matrix;
  const label = algorithmId === 'vo'
    ? '速度决策空间'
    : isMidMPC
      ? 'Mid-MPC · IPOPT 优化轨迹'
      : isFanMPC
        ? 'Fan-MPC · 规则与安全筛选'
        : '算法不可用';
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
  if (objectiveHistoryWrap) objectiveHistoryWrap.hidden = !isMidMPC;
  const voLegend = document.getElementById('voSurfaceLegend');
  if (voLegend) voLegend.hidden = !isVO;
  if (isVO) {
    drawVODecisionSpace(surface, canvas, planner, details);
    return;
  }
  surface.clearRect(0, 0, canvas.width, canvas.height);
  surface.fillStyle = '#0d1211';
  surface.fillRect(0, 0, canvas.width, canvas.height);
  // Before the first solve there is nothing meaningful to plot; keep the
  // screen empty instead of a placeholder caption.
  if (!planner.algorithm_id || !Number(planner.solve_id)) return;
  if (isFanMPC) {
    drawSimplifiedMpcFan(surface, canvas, planner, details);
    return;
  }
  if (isMidMPC) {
    drawMidMpcPrediction(surface, canvas);
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

document.getElementById('plannerSurface')?.addEventListener('pointermove', describeVOCandidate);
document.getElementById('plannerSurface')?.addEventListener('pointerdown', describeVOCandidate);
document.getElementById('plannerSurface')?.addEventListener('pointerleave', () => {
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

function syncPlannerSurfaceMode(planner) {
  const attached = Boolean(plannerSurfaceType(planner));
  if (attached === situationDisplay.isPlannerSurfaceAttached()) return;
  situationDisplay.setPlannerSurfaceAttached(attached);
  if (currentData) situationDisplay.rerender();
}

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

function drawMidMpcPrediction(surface, canvas) {
  const horizon = currentData?.plans?.prediction_horizon || [];
  const own = currentData?.os || {};
  const points = [{ n: own.x, e: own.y }, ...horizon]
    .filter(p => p && Number.isFinite(p[0]) && Number.isFinite(p[1]))
    .map(p => ({ n: p[0], e: p[1] }));
  surface.fillStyle = '#0d1211';
  surface.fillRect(0, 0, canvas.width, canvas.height);
  if (points.length < 2) {
    surface.fillStyle = '#65736f';
    surface.font = '11px SFMono-Regular, monospace';
    surface.fillText('等待 Mid-MPC 预测…', 12, canvas.height / 2);
    return;
  }
  const pad = 18;
  const norths = points.map(p => p.n);
  const easts = points.map(p => p.e);
  const minN = Math.min(...norths), maxN = Math.max(...norths);
  const minE = Math.min(...easts), maxE = Math.max(...easts);
  const spanN = Math.max(maxN - minN, 1e-6);
  const spanE = Math.max(maxE - minE, 1e-6);
  const scale = Math.min((canvas.width - pad * 2) / spanE, (canvas.height - pad * 2) / spanN);
  const offsetX = (canvas.width - spanE * scale) / 2;
  const offsetY = (canvas.height - spanN * scale) / 2;
  const toXY = p => ({
    x: offsetX + (p.e - minE) * scale,
    y: canvas.height - offsetY - (p.n - minN) * scale,
  });
  // grid
  surface.strokeStyle = 'rgba(130,145,140,0.18)';
  surface.lineWidth = 1;
  for (let i = 1; i < 4; i++) {
    const x = (canvas.width / 4) * i;
    const y = (canvas.height / 4) * i;
    surface.beginPath(); surface.moveTo(x, 0); surface.lineTo(x, canvas.height); surface.stroke();
    surface.beginPath(); surface.moveTo(0, y); surface.lineTo(canvas.width, y); surface.stroke();
  }
  // trajectory
  surface.strokeStyle = '#7fd0a8';
  surface.lineWidth = 2;
  surface.beginPath();
  points.forEach((p, i) => {
    const { x, y } = toXY(p);
    if (i === 0) surface.moveTo(x, y); else surface.lineTo(x, y);
  });
  surface.stroke();
  // ownship marker + horizon ticks every ~10 points
  const start = toXY(points[0]);
  surface.fillStyle = '#FFFFFF';
  surface.beginPath(); surface.arc(start.x, start.y, 3.5, 0, Math.PI * 2); surface.fill();
  surface.fillStyle = 'rgba(127,208,168,0.85)';
  points.forEach((p, i) => {
    if (i > 0 && i % 10 === 0) {
      const { x, y } = toXY(p);
      surface.beginPath(); surface.arc(x, y, 2, 0, Math.PI * 2); surface.fill();
    }
  });
  const end = toXY(points[points.length - 1]);
  surface.strokeStyle = '#7fd0a8';
  surface.beginPath(); surface.arc(end.x, end.y, 4.5, 0, Math.PI * 2); surface.stroke();
  surface.fillStyle = '#82918c';
  surface.font = '9px SFMono-Regular, monospace';
  surface.fillText(`${(spanN).toFixed(0)}m × ${(spanE).toFixed(0)}m · ${points.length - 1} steps`, 8, canvas.height - 6);
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
  if (!timeline) return;
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
    const targetThreatLevels = Object.fromEntries(
      (proj.risk?.targets || [])
        .filter(target => target.targetId !== null && target.targetId !== undefined)
        .map(target => [String(target.targetId), riskThreatLevel(target)]),
    );
    const radarModel = buildRadarModel(data, RADAR_DETECTION_RANGE_M, targetThreatLevels);
    radarMiniMap.render(radarModel);
    situationDisplay.setTargetThreatLevels(targetThreatLevels);
    situationDisplay.render(data);
    renderTimelineLog(proj);
  }
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

  const indicator = document.getElementById('status-dot')?.closest('.status-indicator');
  const dot = document.getElementById('status-dot');
  if (indicator) indicator.classList.remove('connected', 'connecting', 'reset', 'reconnecting', 'disconnected');
  if (indicator) indicator.classList.add(state);
  if (dot) {
    dot.classList.toggle('active', state === 'connected');
    dot.classList.toggle('reset', state === 'reconnecting' || state === 'connecting');
  }
  const connStatus = document.getElementById('conn-status');
  if (connStatus) connStatus.textContent = next.text;
  if (logEvent) pushLog(next.text, next.logClass);
}

function resetDeploymentForSession(data) {
  situationDisplay.setPlannerSurfaceAttached(false);
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
  latestMonitorProjection = null;
  hideVesselPlacard();
  perfHistory.length = 0;
  solveTimeline = [];
  lastDisplayedSolveId = null;
  lastSolveSimTime = null;
  lastRuntimeState = 'CREATED';
  radarMiniMap.render(buildRadarModel(data, RADAR_DETECTION_RANGE_M, {}));
  setRuntimePanelsExpanded(false);
  renderSolveTimeline();
  renderedTimelineEvents = 0;
  setEncStatus('loading');
  syncPlaybackStatus(data.playback, false);
  situationDisplay.beginSession(data.session_id || currentRunId());
}

function setControlDisabled(id, disabled) {
  const control = document.getElementById(id);
  if (control) control.disabled = disabled;
}

function syncRuntimeControls(snapshot) {
  const state = snapshot.sessionState;
  const locked = snapshot.authority.status !== 'known' || !snapshot.session || Boolean(snapshot.pending);
  setControlDisabled('btnStart', locked || state === 'RUNNING' || state === 'FINISHED' || state === 'FAILED');
  setControlDisabled('btnPause', locked || state !== 'RUNNING');
  setControlDisabled('btnStep', locked || (state !== 'CREATED' && state !== 'PAUSED'));
  setControlDisabled('btnReset', locked);
  setControlDisabled('btnReplay', locked
    || state !== 'FINISHED'
    || snapshot.outcome.status !== 'ready'
    || !snapshot.outcome.result);
  document.querySelectorAll('.speed-preset').forEach((button) => { button.disabled = locked; });
  setControlDisabled('livePlaybackRate', locked);
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
      resetDeploymentForSession(snapshot.session);
      pushLog(
        `Active Session: ${snapshot.session.spec?.scenario_id} / ${snapshot.session.spec?.algorithm_id} / ${snapshot.session.spec?.tracker_id}`,
        'log-info',
      );
    } else {
      situationDisplay.clearSession();
      radarMiniMap.render(buildRadarModel(null, RADAR_DETECTION_RANGE_M, {}));
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

/* ══════════════════════════════════════════════
   CONTROLS
══════════════════════════════════════════════ */
document.getElementById('btnStart')?.addEventListener('click', async () => {
  try {
    await activeSessionRuntime.start();
    setRuntimePanelsExpanded(true);
    pushLog('Simulation started.', 'log-ok');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnPause')?.addEventListener('click', async () => {
  try {
    await activeSessionRuntime.pause();
    pushLog('Simulation paused.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnStep')?.addEventListener('click', async () => {
  try {
    await activeSessionRuntime.step();
    pushLog('Single simulation step executed.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnReset')?.addEventListener('click', async () => {
  try {
    await activeSessionRuntime.reset();
    pushLog('Session reset to CREATED from its immutable Run Specification.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.getElementById('btnReplay')?.addEventListener('click', async () => {
  try {
    await activeSessionRuntime.replay();
    pushLog('Verified replay session created from source manifest.', 'log-info');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

document.querySelectorAll('.speed-preset').forEach(button => {
  button.addEventListener('click', async () => {
    const speed = parseFloat(button.dataset.speed);
    try {
      await activeSessionRuntime.setSpeed(speed);
      const playback = activeSessionRuntime.snapshot().session?.playback;
      syncPlaybackStatus(playback, currentData?.state === 'RUNNING');
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });
});

document.getElementById('livePlaybackRate')?.addEventListener('click', async (event) => {
  const option = event.target.closest('obc-toggle-button-option');
  if (!option) return;
  const speed = parseFloat(option.getAttribute('value'));
  if (!Number.isFinite(speed)) return;
  try {
    await activeSessionRuntime.setSpeed(speed);
    const playback = activeSessionRuntime.snapshot().session?.playback;
    syncPlaybackStatus(playback, currentData?.state === 'RUNNING');
  } catch (error) {
    pushLog(error.message, 'log-danger');
  }
});

let ownshipCardIndex = 0;
let operationsCardIndex = 0;

function setupDeploymentPagination() {
  const previousOwnshipCardBtn = document.getElementById('previousOwnshipCardBtn');
  const nextOwnshipCardBtn = document.getElementById('nextOwnshipCardBtn');
  const ownshipCardPosition = document.getElementById('ownshipCardPosition');

  const renderOwnshipCardPosition = () => {
    if (!ownshipCardPosition) return;
    const dots = [...ownshipCardPosition.children];
    document.querySelectorAll('[data-ownship-card-page]').forEach((page) => {
      page.hidden = Number(page.dataset.ownshipCardPage) !== ownshipCardIndex;
    });
    dots.forEach((dot, index) => {
      if (index === ownshipCardIndex) dot.setAttribute('aria-current', 'true');
      else dot.removeAttribute('aria-current');
    });
    ownshipCardPosition.setAttribute('aria-label', `第 ${ownshipCardIndex + 1} 张，共 ${dots.length} 张`);
  };

  previousOwnshipCardBtn?.addEventListener('click', () => {
    const count = ownshipCardPosition?.children.length || 2;
    ownshipCardIndex = (ownshipCardIndex + count - 1) % count;
    renderOwnshipCardPosition();
  });
  nextOwnshipCardBtn?.addEventListener('click', () => {
    const count = ownshipCardPosition?.children.length || 2;
    ownshipCardIndex = (ownshipCardIndex + 1) % count;
    renderOwnshipCardPosition();
  });
  if (ownshipCardPosition) {
    [...ownshipCardPosition.children].forEach((dot, index) => {
      dot.addEventListener('click', () => {
        ownshipCardIndex = index;
        renderOwnshipCardPosition();
      });
    });
  }
  renderOwnshipCardPosition();

  const previousOperationsCardBtn = document.getElementById('previousOperationsCardBtn');
  const nextOperationsCardBtn = document.getElementById('nextOperationsCardBtn');
  const operationsCardPosition = document.getElementById('operationsCardPosition');

  const renderOperationsCardPosition = () => {
    if (!operationsCardPosition) return;
    const dots = [...operationsCardPosition.children];
    document.querySelectorAll('[data-operations-card-page]').forEach((page) => {
      page.hidden = Number(page.dataset.operationsCardPage) !== operationsCardIndex;
    });
    dots.forEach((dot, index) => {
      if (index === operationsCardIndex) dot.setAttribute('aria-current', 'true');
      else dot.removeAttribute('aria-current');
    });
    operationsCardPosition.setAttribute('aria-label', `第 ${operationsCardIndex + 1} 张，共 ${dots.length} 张`);
  };

  previousOperationsCardBtn?.addEventListener('click', () => {
    const count = operationsCardPosition?.children.length || 2;
    operationsCardIndex = (operationsCardIndex + count - 1) % count;
    renderOperationsCardPosition();
  });
  nextOperationsCardBtn?.addEventListener('click', () => {
    const count = operationsCardPosition?.children.length || 2;
    operationsCardIndex = (operationsCardIndex + 1) % count;
    renderOperationsCardPosition();
  });
  if (operationsCardPosition) {
    [...operationsCardPosition.children].forEach((dot, index) => {
      dot.addEventListener('click', () => {
        operationsCardIndex = index;
        renderOperationsCardPosition();
      });
    });
  }
  renderOperationsCardPosition();
}

function setupDeploymentControls() {
  document.getElementById('vesselDetailPlacard')?.addEventListener('click', event => event.stopPropagation());
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && selectedVesselTarget) situationDisplay.selectTarget(null);
  });
  document.getElementById('liveRiskTargetList')?.addEventListener('click', (event) => {
    const button = event.target.closest('.risk-distance-toggle');
    if (!button || button.disabled) return;
    riskDistanceUnit = riskDistanceUnit === 'nmi' ? 'km' : 'nmi';
    refreshRiskDistanceButtons();
  });

  document.getElementById('startValidationBtn')?.addEventListener('click', async () => {
    try {
      await activeSessionRuntime.start();
      pushLog('Simulation started.', 'log-ok');
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });

  document.getElementById('pauseValidationBtn')?.addEventListener('click', async () => {
    try {
      await activeSessionRuntime.pause();
      pushLog('Simulation paused.', 'log-info');
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });

  document.getElementById('stepValidationBtn')?.addEventListener('click', async () => {
    try {
      await activeSessionRuntime.step();
      pushLog('Single simulation step executed.', 'log-info');
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });

  document.getElementById('resetValidationBtn')?.addEventListener('click', async () => {
    try {
      await activeSessionRuntime.reset();
      pushLog('Session reset to CREATED from its immutable Run Specification.', 'log-info');
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });

  const rateToggle = document.getElementById('livePlaybackRate');
  rateToggle?.addEventListener('value-changed', async (event) => {
    const rate = Number(event.detail?.value || rateToggle.value || 1);
    try {
      await activeSessionRuntime.setSpeed(rate);
      pushLog(`Playback speed set to ${rate}×`, 'log-info');
    } catch (error) {
      pushLog(error.message, 'log-danger');
    }
  });

  document.getElementById('goToConfigBtn')?.addEventListener('click', () => {
    document.querySelector('[data-workface="config"]')?.click();
  });

  const compassMode = document.getElementById('compassMode');
  compassMode?.addEventListener('value-changed', (event) => {
    const liveCompass = document.getElementById('liveCompass');
    if (liveCompass) {
      liveCompass.direction = event.detail?.value || 'northUp';
    }
  });
}

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

function initializeCollapsibleCard(card, collapsed = false) {
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
  if (sidebar) {
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
  }
  if (insights) {
    RUNTIME_PANEL_IDS.forEach(id => {
      const card = document.getElementById(id);
      if (card) {
        insights.appendChild(card);
        initializeCollapsibleCard(card, true);
      }
    });
  }
  const eventLog = document.querySelector('.log-section');
  if (eventLog) {
    initializeCollapsibleCard(eventLog, false);
  }
  const initialLogEntry = document.getElementById('initialLogEntry');
  if (initialLogEntry) {
    initialLogEntry.textContent = `[${formatSystemTime()}] System ready. Waiting for simulation start…`;
  }
  customElements.whenDefined('obc-dropdown-button').then(setupSensorSourceDropdowns);
  customElements.whenDefined('obc-event-list').then(() => renderMonitorEventList(latestMonitorTimelineEvents));
  Promise.all([
    customElements.whenDefined('obc-notification-button'),
    customElements.whenDefined('obc-notification-message-item'),
  ]).then(setupNotificationCenter);
  setupDeploymentPagination();
  setupDeploymentControls();
}

/* ── Boot ─────────────────────────────────────── */
async function boot() {
  prepareWorkspaceLayout();
  updateBeijingClock();
  window.setInterval(updateBeijingClock, 1000);
  updateLegendVisibility();
  activeSessionRuntime.subscribe(syncDeploymentRuntime);
  // Reconcile once in case Config's module evaluated and bootstrapped first;
  // this is a read-only snapshot adoption, not a second bootstrap.
  syncDeploymentRuntime(activeSessionRuntime.snapshot());
  telemetryProjection.subscribe(renderProjection);
  // Validation Assembly (config-shell.js) is the sole capability/catalog and
  // Active Session bootstrap authority. Deployment only subscribes to the
  // shared runtime projection; it must never fetch a legacy catalog or create
  // a second bootstrap race.
}

window.addEventListener('pagehide', () => {
  situationDisplay.destroy();
  activeSessionRuntime.destroy();
}, { once: true });
boot();
