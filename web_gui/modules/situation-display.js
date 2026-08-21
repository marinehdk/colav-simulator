/**
 * Situation Display — ENC situation canvas for the Deployment workface.
 *
 * Extracted from app.js (C4, 2026-08-19). The Canvas rendering internals are
 * relocated verbatim where possible; the module owns view state, ENC loading
 * (with C2 session-generation guards), layer state, hit-testing/selection,
 * and the telemetry interpolation/rAF pacing pipeline.
 *
 * Data boundary (work order ruling 2): the module consumes ONLY
 *   (a) ENC assets via injected fetchers (fetchInfo / fetchTile),
 *   (b) per-frame snapshots pushed through render(snapshot),
 *   (c) layer visibility flags via setLayerVisible / getLayerState,
 *   (d) internally-owned view state.
 * It never imports the runtime/projection modules; telemetry-projection.js
 * stays decoupled (zero imports either way).
 *
 * Render-order contract (ruling 8): LAYER_ORDER below is the single ordered
 * layer table. Every draw pass records the ids it actually drew; the sequence
 * is exposed via getDrawSequence() for deterministic regression tests.
 */

export const TELEMETRY_RENDER_MIN_MS = 100;
export const TELEMETRY_RENDER_MAX_MS = 1000;

const FCB45_LENGTH_M = 45;
const FCB45_WIDTH_M = 8;
const FCB45_SPRITE_CROP = { x: 388, y: 85, width: 240, height: 1313 };
const TARGET_SPRITE_CROP = { x: 640, y: 25, width: 275, height: 945 };
const MOTION_VECTOR_SECONDS = 60;
const MOTION_TICK_SECONDS = 10;
const PREDICTION_MARKER_SECONDS = 10;
const PREDICTION_LABEL_SECONDS = 60;
const RADAR_DETECTION_RANGE_M = 2000;
const BUSY_WATER_SCENARIO_ID = 'romsdal_busy_water_16';

export const THREAT_STYLES = {
  UNKNOWN: { color: '#4F5B60', fill: 'rgba(104,116,122,0.72)', rank: 0 },
  CLEAR: { color: '#AAB4BA', fill: 'rgba(170,180,186,0.66)', rank: 1 },
  LOW: { color: '#F5A524', fill: 'rgba(245,165,36,0.76)', rank: 2 },
  HIGH: { color: '#FF4D5A', fill: 'rgba(255,77,90,0.82)', rank: 3 },
};

/** Ordered layer table — the render-order contract (ruling 8). */
export const LAYER_ORDER = [
  'safeWater',
  'route',
  'waypoints',
  'history',
  'measurements',
  'tracks',
  'motionVectors',
  'detectionZones',
  'previousPrediction',
  'targetPredictions',
  'prediction',
  'executionPoint',
  'targetRoutes',
  'plannerSurface',
  'ships',
  'relativeCompass',
];

const DEFAULT_LAYERS = {
  safeWater: true,
  ships: true,
  route: true,
  waypoints: true,
  history: true,
  motionVectors: true,
  radarRange: true,
  responseRange: true,
  prediction: true,
  previousPrediction: false,
  executionPoint: true,
  truth: false,
  measurements: false,
  tracks: false,
  covariance: false,
};

const PALETTE_DEFAULTS = {
  '--situation-bg': '#101615',
  '--situation-grid': 'rgba(255,255,255,0.035)',
  '--situation-safewater-fill': 'rgba(76,202,209,0.12)',
  '--situation-safewater-stroke': 'rgba(76,202,209,0.55)',
  '--situation-route': '#F4D34E',
  '--situation-route-inactive': '#7F898D',
  '--situation-prediction': '#55D6B7',
  '--situation-prediction-previous': 'rgba(85,214,183,0.20)',
  '--situation-prediction-label': '#9EF0DB',
  '--situation-track': '#37c995',
  '--situation-track-label': '#c9f3e3',
  '--situation-radar-range': 'rgba(245,165,36,0.72)',
  '--situation-response-range': 'rgba(255,77,90,0.82)',
};

/* ══════════════════════════════════════════════
   PURE EXPORTS (directly unit-testable)
══════════════════════════════════════════════ */

export function validRoute(route) {
  return Array.isArray(route) && route.length >= 2
    && Array.isArray(route[0]) && route[0].length >= 2
    && route[0].length === route[1]?.length;
}

export function chooseGridSpacing(worldWidth) {
  const raw = worldWidth / 10;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const opts = [1, 2, 5, 10].map(f => f * mag);
  return opts.find(v => worldWidth / v <= 20) || opts[opts.length - 1];
}

export function clampZoomScale(scale, factor) {
  return Math.max(0.005, Math.min(5.0, scale * factor));
}

export function updateFrozenRoute(store, data) {
  const key = data.run_id || 'unbound';
  if (!store.has(key) && validRoute(data.waypoints)) {
    store.set(key, data.waypoints.map(axis => [...axis]));
  }
  return store.get(key) || [[], []];
}

export function interpolateAngle(from, to, amount) {
  if (!Number.isFinite(from) || !Number.isFinite(to)) return to;
  const delta = Math.atan2(Math.sin(to - from), Math.cos(to - from));
  return from + delta * amount;
}

export function interpolateVessel(from, to, amount) {
  if (!from || !to) return to;
  return {
    ...to,
    x: Number.isFinite(from.x) && Number.isFinite(to.x) ? from.x + (to.x - from.x) * amount : to.x,
    y: Number.isFinite(from.y) && Number.isFinite(to.y) ? from.y + (to.y - from.y) * amount : to.y,
    psi: interpolateAngle(from.psi, to.psi, amount),
    cog: interpolateAngle(from.cog, to.cog, amount),
  };
}

export function interpolateVesselList(fromList, toList, amount) {
  const previous = new Map((fromList || []).map(item => [String(item.id), item]));
  return (toList || []).map(item => interpolateVessel(previous.get(String(item.id)), item, amount));
}

export function interpolateTelemetry(from, to, amount) {
  if (!from || !to || from.run_id !== to.run_id) return to;
  return {
    ...to,
    os: interpolateVessel(from.os, to.os, amount),
    obstacles: interpolateVesselList(from.obstacles, to.obstacles, amount),
    truth: interpolateVesselList(from.truth, to.truth, amount),
  };
}

export function telemetryRenderDurationMs(from, to) {
  const simDelta = Number(to?.sim_time) - Number(from?.sim_time);
  const multiplier = Number(to?.playback?.requested_multiplier) || 1;
  if (!Number.isFinite(simDelta) || simDelta <= 0 || multiplier <= 0) return TELEMETRY_RENDER_MIN_MS;
  return Math.min(
    TELEMETRY_RENDER_MAX_MS,
    Math.max(TELEMETRY_RENDER_MIN_MS, simDelta / multiplier * 1000),
  );
}

export function wrapRadians(value) {
  return Math.atan2(Math.sin(value), Math.cos(value));
}

export function targetsForDisplay(data) {
  const obstacles = data.obstacles || [];
  if (data.executed_tracker === 'god') return obstacles;

  const trackSet = data.tracks?.[0];
  if (trackSet?.states?.length) {
    const truthById = new Map(obstacles.map(target => [String(target.id), target]));
    return trackSet.states.map((state, index) => {
      const id = trackSet.labels?.[index] ?? index + 1;
      const truth = truthById.get(String(id)) || {};
      const velocityNorth = Number(state[2]);
      const velocityEast = Number(state[3]);
      const speed = Math.hypot(velocityNorth, velocityEast);
      const course = Math.atan2(velocityEast, velocityNorth);
      return {
        ...truth,
        id,
        x: Number(state[0]),
        y: Number(state[1]),
        psi: Number.isFinite(course) ? course : truth.psi,
        cog: Number.isFinite(course) ? course : truth.cog,
        sog: Number.isFinite(speed) ? speed : truth.sog,
        source: 'tracker',
      };
    }).filter(target => Number.isFinite(target.x) && Number.isFinite(target.y));
  }
  return [];
}

export function targetThreatStyle(data, target) {
  const source = data?.threat_management;
  if (!target || source?.status !== 'AVAILABLE' || !Array.isArray(source.vectors)) return 'UNKNOWN';
  const vector = source.vectors.find((item) => {
    const key = item?.key ?? item;
    const targetId = key?.target_id ?? key?.targetId ?? item?.target_id ?? item?.targetId;
    return targetId !== null && targetId !== undefined && String(targetId) === String(target.id);
  });
  const explicit = vector?.display_class ?? vector?.displayClass ?? vector?.threat_class ?? vector?.threatClass;
  return ['HIGH', 'LOW', 'CLEAR', 'UNKNOWN'].includes(String(explicit).toUpperCase())
    ? String(explicit).toUpperCase()
    : 'UNKNOWN';
}

export function plannerSurfaceType(planner) {
  if (planner?.algorithm_id === 'vo') return 'vo';
  if (['potocnik_simplified_mpc', 'potocnik_colreg_fan_mpc'].includes(planner?.algorithm_id)) return 'fan';
  return null;
}

export function hexToRgba(hex, alpha) {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) return hex;
  const value = Number.parseInt(hex.slice(1), 16);
  return `rgba(${value >> 16},${(value >> 8) & 255},${value & 255},${alpha})`;
}

export function voCandidateColor(stateBits, normalizedCost) {
  const alpha = Math.max(0.58, Math.min(0.94, 0.58 + normalizedCost * 0.36));
  if (stateBits & 1) return `rgba(227,78,89,${alpha})`;
  if (stateBits & 4 || stateBits & 8) return `rgba(217,107,255,${alpha})`;
  if (stateBits & 2) return `rgba(240,201,77,${alpha})`;
  return `rgba(47,191,113,${alpha})`;
}

export function simplifiedMpcFanGeometry(details) {
  const increments = Array.isArray(details.candidate_heading_increments_rad)
    ? details.candidate_heading_increments_rad.map(Number)
    : [];
  const feasible = Array.isArray(details.candidate_feasible) ? details.candidate_feasible : [];
  const selectedIndex = Number(details.selected_candidate_index);
  const steps = Math.max(1, Number(details.prediction_steps) || 16);
  const decay = Number(details.heading_increment_decay) || 0.95;
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
  return { increments, feasible, selectedIndex, steps, trajectories };
}

export function drawVelocityArrow(
  surface,
  centerX,
  centerY,
  radius,
  maxSpeed,
  velocity,
  ownshipHeading,
  color,
  width = 1.7,
  displayRotation = 0,
) {
  const north = Number(velocity?.[0]);
  const east = Number(velocity?.[1]);
  if (!Number.isFinite(north) || !Number.isFinite(east)) return;
  const speed = Math.hypot(north, east);
  const relativeHeading = wrapRadians(Math.atan2(east, north) - ownshipHeading) + displayRotation;
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

/* ══════════════════════════════════════════════
   FACTORY
══════════════════════════════════════════════ */

export function createSituationDisplay(options) {
  const {
    canvas,
    wrapper,
    fetchInfo = defaultFetchInfo,
    fetchTile = defaultFetchTile,
    createImage = defaultCreateImage,
    now = () => performance.now(),
    raf = defaultRaf,
    cancelRaf = defaultCancelRaf,
    getResponseRange = () => null,
    getScenarioId = () => null,
    getPlannerSurface = () => null,
    backgroundMode = 'opaque',
    loadSprites = true,
    onScaleLabel = null,
    onEncStatus = () => {},
    onLog = () => {},
    onLayerStateChange = () => {},
    onSelectionChange = () => {},
  } = options;
  if (!canvas || !wrapper) throw new Error('situation-display requires canvas and wrapper');

  const ctx = canvas.getContext('2d');

  /* ── palette (ruling 10 / M5) ── */
  let palette = { ...PALETTE_DEFAULTS };
  function refreshPalette() {
    if (typeof document === 'undefined' || typeof getComputedStyle !== 'function') return palette;
    const computed = getComputedStyle(document.documentElement);
    for (const token of Object.keys(PALETTE_DEFAULTS)) {
      const value = computed.getPropertyValue(token).trim();
      if (value) palette[token] = value;
    }
    return palette;
  }
  refreshPalette();

  /* ── ENC state ── */
  let encInfo = null;
  let encImage = null;
  let encReady = false;
  let showENC = true;
  let encLoadGeneration = 0;
  let encInfoController = null;
  let encRetryTimer = null;
  let encPendingImage = null;
  let encStatus = 'idle';

  /* ── view state (ruling 3/4) ── */
  let viewScale = 0.45;
  let panX = 0;
  let panY = 0;
  let isPanning = false;
  let lastPanX = 0, lastPanY = 0;
  let userAdjusted = false;
  let pointerDown = null;

  /* ── map orientation: 'north' (north up) or 'heading' (ownship heading up) ──
     Heading-up rotates the whole drawn frame about the viewport center by
     -psi; pointer input is mapped back through the same rotation. */
  let mapOrientation = 'north';
  let headingRotation = 0;

  function screenToDrawn(x, y) {
    if (!headingRotation) return { x, y };
    const w = wrapper.clientWidth;
    const h = wrapper.clientHeight;
    const dx = x - w / 2;
    const dy = y - h / 2;
    const cos = Math.cos(headingRotation);
    const sin = Math.sin(headingRotation);
    return { x: w / 2 + dx * cos - dy * sin, y: h / 2 + dx * sin + dy * cos };
  }

  /* ── layers (ruling 6) ── */
  const visibleLayers = { ...DEFAULT_LAYERS };
  const layerAvailability = {};
  let lastLayerStateKey = null;
  let layerStateSink = onLayerStateChange;

  /* ── selection & click routing (ruling 7) ── */
  let targetHitRegions = [];
  let selectedTargetId = null;
  let clickMode = null;
  let selectionCallback = onSelectionChange;

  /* ── interpolation pipeline (moved from app.js per M3) ── */
  let currentData = null;
  let lastRenderedData = null;
  let renderFromData = null;
  let renderToData = null;
  let renderStartedAt = 0;
  let renderDurationMs = TELEMETRY_RENDER_MIN_MS;
  let renderFrameId = null;

  /* ── route freeze per run ── */
  const missionRoutes = new Map();

  /* ── planner surface attach ── */
  let plannerSurfaceAttached = false;

  /* ── draw sequence (render-order contract, ruling 8) ── */
  let drawSequence = [];

  /* ── sprites ── */
  // Sprites load only when the adapter asks for them (Deployment); the Config
  // preview adapter passes loadSprites: false and gets the vector hull
  // fallback — no network requests, no image elements.
  const ownshipSprite = loadSprites ? createImage() : { complete: false, naturalWidth: 0 };
  const targetSprite = loadSprites ? createImage() : { complete: false, naturalWidth: 0 };
  if (loadSprites) {
    if (ownshipSprite.addEventListener) ownshipSprite.addEventListener('load', () => { rerender(); });
    setSpriteSrc(ownshipSprite, '/static/assets/fcb45-top.png');
    if (targetSprite.addEventListener) targetSprite.addEventListener('load', () => { rerender(); });
    setSpriteSrc(targetSprite, '/static/assets/target-vessel-top.png');
  }

  /* ════════════ sizing / transforms ════════════ */

  function resize() {
    if (typeof document !== 'undefined') {
      const dpr = window.devicePixelRatio || 1;
      const w = wrapper.clientWidth;
      const h = wrapper.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      if (canvas.style) {
        canvas.style.width = `${w}px`;
        canvas.style.height = `${h}px`;
      }
      ctx.scale(dpr, dpr);
    }
    // Ruling 4: refit only while the user has not adjusted the view; a
    // user-adjusted view keeps its pan/zoom anchored on the new backing store.
    if (!userAdjusted && encInfo && encReady) fitENCView();
    updateScaleBar();
    rerender();
  }

  let resizeObserver = null;
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(wrapper);
  }

  function worldToCanvas(north, east) {
    const cx = wrapper.clientWidth / 2 + panX;
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

  function fitView() {
    userAdjusted = false;
    fitENCView();
    updateScaleBar();
    rerender();
  }

  function utmToCanvas(easting, northing) {
    if (!encInfo) return { x: 0, y: 0 };
    const de = easting - encInfo.origin_e;
    const dn = northing - encInfo.origin_n;
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
    // Scale-label DOM updates are injected by the adapter (Deployment passes a
    // sink writing #scaleBarLabel); other adapters pass nothing → no-op.
    if (!onScaleLabel) return;
    const fixedBarPx = 72;
    const representedM = fixedBarPx / viewScale;
    onScaleLabel(representedM >= 1000
      ? `${(representedM / 1000).toFixed(1)} km`
      : `${Math.round(representedM)} m`);
  }

  function zoomAtCanvasPoint(x, y, factor) {
    const previousScale = viewScale;
    const nextScale = clampZoomScale(previousScale, factor);
    if (nextScale === previousScale) return;
    const centerX = wrapper.clientWidth / 2 + panX;
    const centerY = wrapper.clientHeight / 2 + panY;
    const scaleRatio = nextScale / previousScale;
    panX = x - wrapper.clientWidth / 2 - (x - centerX) * scaleRatio;
    panY = y - wrapper.clientHeight / 2 - (y - centerY) * scaleRatio;
    viewScale = nextScale;
  }

  /* ════════════ ENC loading (C2 generation guards) ════════════ */

  function cancelENCLoad() {
    encLoadGeneration += 1;
    if (encInfoController) encInfoController.abort();
    if (encRetryTimer !== null) clearTimer(encRetryTimer);
    if (encPendingImage) {
      encPendingImage.onload = null;
      encPendingImage.onerror = null;
    }
    encInfoController = null;
    encRetryTimer = null;
    encPendingImage = null;
  }

  async function initENC(sessionId) {
    cancelENCLoad();
    const generation = encLoadGeneration;
    setEncStatus('loading');
    if (!sessionId) return;
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    encInfoController = controller;
    try {
      const res = controller
        ? await fetchInfo({ signal: controller.signal })
        : await fetchInfo({});
      // Accept either a Response-like ({ json() }) or a pre-parsed info object.
      const info = typeof res?.json === 'function' ? await res.json() : res;
      if (generation !== encLoadGeneration || sessionId !== currentRunId()) return;
      if (info.ready && info.run_id !== sessionId) return;

      if (!info.ready) {
        encRetryTimer = setTimer(() => {
          if (generation === encLoadGeneration && sessionId === currentRunId()) initENC(sessionId);
        }, 5000);
        return;
      }

      encInfo = info;

      await new Promise((resolve, reject) => {
        const img = createImage();
        encPendingImage = img;
        img.onload = () => {
          if (generation !== encLoadGeneration || sessionId !== currentRunId()) {
            resolve();
            return;
          }
          encPendingImage = null;
          encImage = img;
          encReady = true;
          fitENCView();
          updateScaleBar();
          setEncStatus('ready');
          onLog(`ENC chart loaded — UTM${info.utm_zone} origin (${info.origin_e.toFixed(0)}, ${info.origin_n.toFixed(0)})`, 'log-ok');
          resolve();
        };
        img.onerror = () => {
          if (generation !== encLoadGeneration || sessionId !== currentRunId()) {
            resolve();
            return;
          }
          encPendingImage = null;
          setEncStatus('error');
          onLog('ENC PNG tile failed to load.', 'log-danger');
          resolve();
        };
        setSpriteSrc(img, fetchTile());
      });
      rerender();
    } catch (error) {
      if (error?.name === 'AbortError' || generation !== encLoadGeneration || sessionId !== currentRunId()) return;
      encRetryTimer = setTimer(() => {
        if (generation === encLoadGeneration && sessionId === currentRunId()) initENC(sessionId);
      }, 8000);
    } finally {
      if (encInfoController === controller) encInfoController = null;
    }
  }

  function setEncStatus(state) {
    encStatus = state;
    onEncStatus(state);
  }

  /* ════════════ interpolation pipeline ════════════ */

  function renderTelemetryFrame(timestamp) {
    if (!renderToData) {
      renderFrameId = null;
      return;
    }
    const amount = renderFromData === renderToData
      ? 1
      : Math.min(1, Math.max(0, (timestamp - renderStartedAt) / renderDurationMs));
    renderCanvas(interpolateTelemetry(renderFromData, renderToData, amount));
    if (amount < 1 && renderToData.state === 'RUNNING') {
      const handle = raf(renderTelemetryFrame);
      // Only keep the new handle if a synchronous callback chain has not
      // already advanced/finished the animation.
      if (renderFrameId !== null) renderFrameId = handle;
    } else {
      renderFromData = renderToData;
      renderFrameId = null;
    }
  }

  function queueTelemetryRender(data) {
    const timestamp = now();
    if (!renderToData || renderToData.run_id !== data.run_id) {
      renderFromData = data;
      renderToData = data;
      renderDurationMs = TELEMETRY_RENDER_MIN_MS;
    } else if (Number.isFinite(data.seq) && data.seq === renderToData.seq) {
      renderToData = data;
      if (data.state === 'RUNNING') return;
      renderFromData = data;
    } else {
      const amount = Math.min(1, Math.max(0, (timestamp - renderStartedAt) / renderDurationMs));
      renderFromData = interpolateTelemetry(renderFromData, renderToData, amount);
      renderDurationMs = telemetryRenderDurationMs(renderToData, data);
      renderToData = data;
    }
    renderStartedAt = timestamp;
    if (renderFrameId === null) {
      // Guard against synchronous rAF implementations: the callback may run
      // (and null renderFrameId) before raf() returns, and the assignment
      // must not clobber that with a stale handle.
      const pending = {};
      renderFrameId = pending;
      const handle = raf(renderTelemetryFrame);
      if (renderFrameId === pending) renderFrameId = handle;
    }
  }

  function resetAnimation() {
    if (renderFrameId !== null) cancelRaf(renderFrameId);
    renderFromData = null;
    renderToData = null;
    renderStartedAt = 0;
    renderFrameId = null;
    currentData = null;
    lastRenderedData = null;
  }

  /* ════════════ rendering ════════════ */

  function rerender() {
    if (lastRenderedData) renderCanvas(lastRenderedData);
  }

  function renderCanvas(data) {
    lastRenderedData = data;
    drawSequence = ['base'];
    const W = wrapper.clientWidth;
    const H = wrapper.clientHeight;
    ctx.save();
    headingRotation = mapOrientation === 'heading' && Number.isFinite(currentData?.os?.psi) ? currentData.os.psi : 0;
    if (headingRotation) {
      ctx.translate(W / 2, H / 2);
      ctx.rotate(-headingRotation);
      ctx.translate(-W / 2, -H / 2);
    }
    ctx.clearRect(0, 0, W, H);
    targetHitRegions = [];

    // backgroundMode 'transparent' (Config preview adapter): the opaque map
    // fill is skipped so the reference image beneath stays visible.
    if (backgroundMode !== 'transparent') {
      ctx.fillStyle = palette['--situation-bg'];
      ctx.fillRect(0, 0, W, H);
    }
    if (showENC && encReady && encImage && encInfo) {
      drawSequence.push('enc');
      drawENCTile(W, H);
    }
    if (!encReady || !showENC) {
      drawSequence.push('grid');
      drawGrid(W, H);
    }

    const route = updateFrozenRoute(missionRoutes, data);
    const navigationArea = data.enc_navigation_area;
    updateLayerAvailability(data, navigationArea);

    if (visibleLayers.safeWater && layerAvailability.safeWater) drawNavigationArea(navigationArea);
    if (visibleLayers.route) drawInitialRoute(route);
    if (visibleLayers.waypoints) drawWaypoints(route, data.os);
    if (visibleLayers.history) drawHistory(data);
    if (visibleLayers.measurements) drawMeasurements(data.measurements?.[0]);
    if (visibleLayers.tracks && !denseTrafficMode(data) && data.tracks?.[0]?.states) drawTracks(data.tracks[0]);
    if (visibleLayers.motionVectors) drawMotionVectors(data);
    drawDetectionZones(data);

    const plans = data.plans || {};
    if (visibleLayers.previousPrediction && plans.previous_prediction_horizon?.length > 0)
      drawHorizon(plans.previous_prediction_horizon, true, data.planner);
    // Push 'targetPredictions' only when at least one horizon actually drew
    // (a horizon shorter than 2 points draws nothing).
    let drewTargetHorizon = false;
    (plans.target_prediction_horizons || []).forEach((horizon, index) => {
      if (drawTargetHorizon(horizon, targetThreat(data, data.obstacles?.[index]))) drewTargetHorizon = true;
    });
    if (drewTargetHorizon) drawSequence.push('targetPredictions');
    if (visibleLayers.prediction && plans.prediction_horizon?.length > 0)
      drawHorizon(plans.prediction_horizon, false, data.planner);
    if (visibleLayers.executionPoint && plans.prediction_horizon?.length > 0)
      drawExecutionPoint(plans.prediction_horizon);
    drawTargetRoutes(data);
    const surface = getPlannerSurface();
    if (data.os && plannerSurfaceAttached && surface) drawPlannerSurfaceOnMap(data.os, surface);
    if (visibleLayers.ships) drawShips(data);
    if (data.os && !plannerSurfaceAttached) drawRelativeCompass(data.os, W, H);
    ctx.restore();
  }

  function drawENCTile(W, H) {
    if (!encInfo || !encImage) return;
    const tilePxW = encInfo.width * viewScale;
    const tilePxH = encInfo.height * viewScale;
    const llPt = worldToCanvas(0, 0);
    const drawX = llPt.x;
    const drawY = llPt.y - tilePxH;
    ctx.save();
    ctx.globalAlpha = 0.92;
    ctx.drawImage(encImage, drawX, drawY, tilePxW, tilePxH);
    ctx.globalAlpha = 1.0;
    ctx.restore();
  }

  function drawGrid(W, H) {
    const gridWorld = chooseGridSpacing(W / viewScale);
    const gridPx = gridWorld * viewScale;
    const cx = W / 2 + panX, cy = H / 2 + panY;
    ctx.strokeStyle = palette['--situation-grid'];
    ctx.lineWidth = 1;
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

  function routePoints(route) {
    if (!validRoute(route)) return [];
    return route[0].map((north, index) => worldToCanvas(north, route[1][index]));
  }

  function drawNavigationArea(area) {
    drawPolygonCollection(area?.safe_water?.polygons,
      palette['--situation-safewater-fill'], palette['--situation-safewater-stroke']);
    drawSequence.push('safeWater');
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

  function drawInitialRoute(route) {
    const points = routePoints(route);
    if (points.length < 2) return;
    ctx.save();
    ctx.strokeStyle = palette['--situation-route'];
    ctx.lineWidth = 2;
    ctx.setLineDash([10, 8]);
    strokePolyline(points);
    ctx.restore();
    drawSequence.push('route');
  }

  function drawWaypoints(route, os) {
    const points = routePoints(route);
    if (!points.length) return;
    const current = currentWaypointIndex(route, os);
    points.forEach((point, index) => {
      const passed = index < current;
      const active = index === current;
      ctx.strokeStyle = passed ? palette['--situation-route-inactive'] : palette['--situation-route'];
      ctx.fillStyle = active ? 'rgba(244,211,78,0.28)' : 'rgba(10,16,15,0.70)';
      ctx.lineWidth = active ? 2.5 : 1.5;
      ctx.beginPath();
      ctx.arc(point.x, point.y, active ? 7 : 5, 0, 2 * Math.PI);
      ctx.fill();
      ctx.stroke();
      drawMapLabel(`WPT${index + 1}`, point.x + 9, point.y - 7, passed ? '#9AA3A7' : palette['--situation-route']);
    });
    drawSequence.push('waypoints');
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
    drawSequence.push('history');
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
    let drew = false;
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
      drew = true;
    });
    if (drew) drawSequence.push('measurements');
  }

  function drawTracks(trackSet) {
    if (!trackSet || !Array.isArray(trackSet.states)) return;
    let drew = false;
    trackSet.states.forEach((state, index) => {
      if (!Array.isArray(state) || state.length < 2) return;
      const point = worldToCanvas(state[0], state[1]);
      if (visibleLayers.covariance) {
        drawCovariance(point, trackSet.covariances?.[index]);
      }
      ctx.fillStyle = palette['--situation-track'];
      ctx.beginPath();
      ctx.arc(point.x, point.y, 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = palette['--situation-track-label'];
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.fillText(`T${trackSet.labels?.[index] ?? index}`, point.x + 6, point.y - 6);
      drew = true;
    });
    if (drew) drawSequence.push('tracks');
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

  function drawHorizon(horizon, previous = false, planner = {}) {
    const pts = horizon.map(p => worldToCanvas(p[0], p[1]));
    if (pts.length < 2) return; // nothing drawable — do not claim the layer slot
    ctx.strokeStyle = previous ? palette['--situation-prediction-previous'] : palette['--situation-prediction'];
    ctx.lineWidth = previous ? 1.5 : 2.5;
    ctx.setLineDash(previous ? [6, 6] : []);
    strokePolyline(pts);
    ctx.setLineDash([]);
    if (previous) {
      drawSequence.push('previousPrediction');
      return;
    }
    drawSequence.push('prediction');
    const dt = Number(planner?.horizon_dt_s);
    if (!Number.isFinite(dt) || dt <= 0) return;
    const markerInterval = Math.max(1, Math.round(PREDICTION_MARKER_SECONDS / dt));
    const labelInterval = Math.max(1, Math.round(PREDICTION_LABEL_SECONDS / dt));
    pts.forEach((point, index) => {
      if (index === 0 || index % markerInterval !== 0) return;
      const keyPoint = index % labelInterval === 0;
      ctx.fillStyle = keyPoint ? palette['--situation-prediction-label'] : 'rgba(11,18,17,0.72)';
      ctx.strokeStyle = keyPoint ? '#D2FFF3' : 'rgba(85,214,183,0.92)';
      ctx.lineWidth = keyPoint ? 1.5 : 1.1;
      ctx.beginPath();
      ctx.arc(point.x, point.y, keyPoint ? 4 : 2.4, 0, 2 * Math.PI);
      ctx.fill();
      ctx.stroke();
      if (!keyPoint) return;
      drawMapLabel(`${Math.round(index * dt)}s`, point.x + 5, point.y - 5, palette['--situation-prediction-label']);
    });
  }

  function drawTargetHorizon(horizon, threat = THREAT_STYLES.UNKNOWN) {
    if (!Array.isArray(horizon) || horizon.length < 2) return false;
    const pts = horizon.map(p => worldToCanvas(p[0], p[1]));
    ctx.strokeStyle = hexToRgba(threat.color, 0.6);
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 5]);
    strokePolyline(pts);
    ctx.setLineDash([]);
    return true;
  }

  function drawExecutionPoint(horizon) {
    const index = horizon.length > 1 ? 1 : 0;
    const point = worldToCanvas(horizon[index][0], horizon[index][1]);
    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(Math.PI / 4);
    ctx.fillStyle = palette['--situation-prediction'];
    ctx.strokeStyle = '#0B0F0E';
    ctx.lineWidth = 1.5;
    ctx.fillRect(-5, -5, 10, 10);
    ctx.strokeRect(-5, -5, 10, 10);
    ctx.restore();
    drawSequence.push('executionPoint');
  }

  function drawMotionVectors(data) {
    let drew = false;
    if (data.os) {
      drawMotionVector(data.os, '#FFFFFF', false);
      drew = true;
    }
    targetsForDisplay(data).forEach(target => {
      const threat = targetThreat(data, target);
      if (denseTrafficMode(data) && threat.rank < 3 && target.id !== selectedTargetId) return;
      drawMotionVector(target, threat.color, true);
      drew = true;
    });
    if (drew) drawSequence.push('motionVectors');
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

  function targetThreat(data, target) {
    return THREAT_STYLES[targetThreatStyle(data, target)] || THREAT_STYLES.UNKNOWN;
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
      drawTargetSprite(point, target.psi, target.length || 30, target.width || 7, threat, compact);
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
      drawOwnshipSprite(point, data.os.psi, FCB45_LENGTH_M, FCB45_WIDTH_M);
      labels.push({ text: 'OS', point, color: '#FFFFFF' });
    }
    drawAvoidingLabels(labels);
    drawSequence.push('ships');
  }

  function drawOwnshipSprite(point, heading, lengthM, widthM) {
    if (!ownshipSprite.complete || ownshipSprite.naturalWidth === 0) {
      drawHull(point, heading, lengthM, widthM, null, true);
      return;
    }
    const lengthPx = Math.max(18, lengthM * viewScale);
    const widthPx = Math.max(4, lengthPx * widthM / lengthM);
    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(Number.isFinite(heading) ? heading : 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.shadowColor = 'rgba(0, 0, 0, 0.45)';
    ctx.shadowBlur = 2;
    ctx.drawImage(
      ownshipSprite,
      FCB45_SPRITE_CROP.x,
      FCB45_SPRITE_CROP.y,
      FCB45_SPRITE_CROP.width,
      FCB45_SPRITE_CROP.height,
      -widthPx / 2,
      -lengthPx / 2,
      widthPx,
      lengthPx,
    );
    ctx.restore();
  }

  function drawTargetSprite(point, heading, lengthM, widthM, threat, compact = false) {
    if (!targetSprite.complete || targetSprite.naturalWidth === 0) {
      drawHull(point, heading, lengthM, widthM, threat, false, compact);
      return;
    }
    const lengthPx = Math.max(compact ? 7 : 22, lengthM * viewScale);
    const widthPx = Math.max(5, lengthPx * widthM / lengthM);
    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(Number.isFinite(heading) ? heading : 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.shadowColor = threat?.color || 'rgba(0, 0, 0, 0.45)';
    ctx.shadowBlur = compact ? 1 : 3;
    ctx.drawImage(
      targetSprite,
      TARGET_SPRITE_CROP.x,
      TARGET_SPRITE_CROP.y,
      TARGET_SPRITE_CROP.width,
      TARGET_SPRITE_CROP.height,
      -widthPx / 2,
      -lengthPx / 2,
      widthPx,
      lengthPx,
    );
    ctx.restore();
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

  function drawDetectionZones(data) {
    if (!data.os) return;
    const center = worldToCanvas(data.os.x, data.os.y);
    let drew = false;
    ctx.save();
    if (visibleLayers.radarRange) {
      ctx.beginPath();
      ctx.arc(center.x, center.y, RADAR_DETECTION_RANGE_M * viewScale, 0, Math.PI * 2);
      ctx.strokeStyle = palette['--situation-radar-range'];
      ctx.lineWidth = 1.4;
      ctx.setLineDash([12, 8]);
      ctx.stroke();
      drew = true;
    }
    const responseRange = getResponseRange();
    if (visibleLayers.responseRange && responseRange) {
      ctx.beginPath();
      ctx.arc(center.x, center.y, responseRange.distanceM * viewScale, 0, Math.PI * 2);
      ctx.strokeStyle = palette['--situation-response-range'];
      ctx.lineWidth = 1.7;
      ctx.setLineDash([8, 6]);
      ctx.stroke();
      drew = true;
    }
    ctx.restore();
    if (drew) drawSequence.push('detectionZones');
  }

  function drawTargetRoutes(data) {
    const routes = data.plans?.target_routes || [];
    const scenarioId = data.scenario_id || getScenarioId();
    if (!routes.length || scenarioId !== BUSY_WATER_SCENARIO_ID) return;
    let drewRoute = false;
    routes.forEach(route => {
      const north = route.waypoints?.[0] || [];
      const east = route.waypoints?.[1] || [];
      if (north.length < 2 || east.length < 2) return;
      drewRoute = true;
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
    if (drewRoute) drawSequence.push('targetRoutes');
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
    drawSequence.push('relativeCompass');
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

  function drawPlannerSurfaceOnMap(os, surface) {
    const surfaceType = surface.type;
    if (surfaceType === 'vo' && surface.vo) drawVODecisionSpaceOnMap(os, surface.vo);
    if (surfaceType === 'fan' && surface.fan) drawSimplifiedMpcFanOnMap(os, surface.fan);
    drawSequence.push('plannerSurface');
  }

  function drawVODecisionSpaceOnMap(os, snapshot) {
    if (!snapshot || !Number.isFinite(os?.x) || !Number.isFinite(os?.y)) return;
    const speeds = snapshot.speed_candidates_mps || [];
    const headings = snapshot.heading_candidates_rad || [];
    const bits = snapshot.candidate_state_bits || [];
    const costs = snapshot.total_costs || [];
    const [rows, columns] = snapshot.shape || [];
    if (!rows || !columns || rows !== speeds.length || columns !== headings.length
      || bits.length !== rows * columns) return;

    const point = worldToCanvas(os.x, os.y);
    const centerX = point.x;
    const centerY = point.y;
    const radius = 110;
    const maxSpeed = Math.max(...speeds, 1);
    const headingStep = 2 * Math.PI / columns;
    const ownshipHeading = Number(snapshot.ownship_heading_rad) || Number(os.psi) || 0;
    const displayRotation = Number(os.psi) || ownshipHeading;
    const finiteCosts = costs.filter(Number.isFinite);
    const minimumCost = finiteCosts.length ? Math.min(...finiteCosts) : 0;
    const maximumCost = finiteCosts.length ? Math.max(...finiteCosts) : 1;

    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = 'rgba(8,18,20,0.34)';
    ctx.fillRect(centerX - radius, centerY - radius, radius * 2, radius * 2);

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
        const displayedHeading = relativeHeading + displayRotation;
        const start = displayedHeading - headingStep / 2 - Math.PI / 2;
        const end = displayedHeading + headingStep / 2 - Math.PI / 2;
        const cost = costs[index] == null ? NaN : Number(costs[index]);
        const normalizedCost = Number.isFinite(cost) && maximumCost > minimumCost
          ? (cost - minimumCost) / (maximumCost - minimumCost)
          : 0;
        ctx.fillStyle = voCandidateColor(bits[index], normalizedCost);
        ctx.beginPath();
        ctx.arc(centerX, centerY, outerRadius, start, end);
        if (innerRadius > 0) ctx.arc(centerX, centerY, innerRadius, end, start, true);
        else ctx.lineTo(centerX, centerY);
        ctx.closePath();
        ctx.fill();
      }
    }
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(232,244,240,0.38)';
    ctx.fillStyle = 'rgba(232,244,240,0.82)';
    ctx.lineWidth = 0.8;
    ctx.font = '8px SFMono-Regular, monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let speed = 2; speed <= maxSpeed; speed += 2) {
      const ringRadius = speed / maxSpeed * radius;
      ctx.beginPath();
      ctx.arc(centerX, centerY, ringRadius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillText(`${speed}`, centerX + 3, centerY - ringRadius + 8);
    }
    for (let degrees = -180; degrees < 180; degrees += 30) {
      const angle = degrees * Math.PI / 180 + displayRotation;
      const endX = centerX + radius * Math.sin(angle);
      const endY = centerY - radius * Math.cos(angle);
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(endX, endY);
      ctx.stroke();
      if (degrees % 60 === 0) {
        ctx.fillText(
          `${degrees}°`,
          centerX + (radius - 10) * Math.sin(angle),
          centerY - (radius - 10) * Math.cos(angle),
        );
      }
    }

    drawVelocityArrow(
      ctx, centerX, centerY, radius, maxSpeed,
      snapshot.current_velocity_ne_mps, ownshipHeading, '#9aa7a2', 1.7, displayRotation,
    );
    drawVelocityArrow(
      ctx, centerX, centerY, radius, maxSpeed,
      snapshot.reference_velocity_ne_mps, ownshipHeading, '#f3f6f5', 1.7, displayRotation,
    );
    const selected = snapshot.selected || {};
    drawVelocityArrow(
      ctx,
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
      displayRotation,
    );
    ctx.strokeStyle = 'rgba(232,244,240,0.72)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function drawSimplifiedMpcFanOnMap(os, planner) {
    if (!Number.isFinite(os?.x) || !Number.isFinite(os?.y)) return;
    const details = planner?.algorithm_details || {};
    const { feasible, selectedIndex, steps, trajectories } = simplifiedMpcFanGeometry(details);
    if (!trajectories.length) return;

    const center = worldToCanvas(os.x, os.y);
    const radius = wrapper.clientWidth <= 520 ? 64 : 110;
    const scale = radius / steps;
    const heading = Number(os.psi) || 0;
    const mapPoint = point => ({
      x: center.x + (point.y * Math.sin(heading) + point.x * Math.cos(heading)) * scale,
      y: center.y - (point.y * Math.cos(heading) - point.x * Math.sin(heading)) * scale,
    });

    ctx.save();
    ctx.beginPath();
    ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = 'rgba(8,18,20,0.34)';
    ctx.fillRect(center.x - radius, center.y - radius, radius * 2, radius * 2);
    [-Math.PI / 2, 0, Math.PI / 2].forEach(relativeHeading => {
      const end = mapPoint({
        x: Math.sin(relativeHeading) * steps,
        y: Math.cos(relativeHeading) * steps,
      });
      ctx.strokeStyle = 'rgba(232,244,240,0.32)';
      ctx.lineWidth = 0.8;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(center.x, center.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
    });
    ctx.setLineDash([]);
    const targetOffset = Number(details.target_bearing_offset_rad);
    if (Number.isFinite(targetOffset)) {
      const target = mapPoint({ x: Math.sin(targetOffset) * steps, y: Math.cos(targetOffset) * steps });
      ctx.strokeStyle = '#D96BFF';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(center.x, center.y);
      ctx.lineTo(target.x, target.y);
      ctx.stroke();
    }
    trajectories.forEach((points, index) => {
      if (index === selectedIndex) return;
      ctx.strokeStyle = feasible[index] ? 'rgba(74,191,132,0.62)' : 'rgba(225,86,91,0.58)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      points.forEach((point, pointIndex) => {
        const mapped = mapPoint(point);
        if (pointIndex === 0) ctx.moveTo(mapped.x, mapped.y);
        else ctx.lineTo(mapped.x, mapped.y);
      });
      ctx.stroke();
    });
    if (Number.isInteger(selectedIndex) && trajectories[selectedIndex]) {
      ctx.strokeStyle = '#58A6FF';
      ctx.lineWidth = 2.6;
      ctx.beginPath();
      trajectories[selectedIndex].forEach((point, pointIndex) => {
        const mapped = mapPoint(point);
        if (pointIndex === 0) ctx.moveTo(mapped.x, mapped.y);
        else ctx.lineTo(mapped.x, mapped.y);
      });
      ctx.stroke();
    }
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(232,244,240,0.72)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  /* ════════════ layer availability ════════════ */

  function updateLayerAvailability(data, navigationArea) {
    layerAvailability.safeWater = normalizePolygons(navigationArea?.safe_water?.polygons).length > 0;
    layerAvailability.radarRange = true;
    layerAvailability.responseRange = Boolean(getResponseRange());
    emitLayerState();
  }

  function emitLayerState() {
    const state = getLayerState();
    const key = JSON.stringify(state);
    if (key === lastLayerStateKey) return;
    lastLayerStateKey = key;
    layerStateSink(state);
  }

  function getLayerState() {
    const state = {};
    for (const id of Object.keys(DEFAULT_LAYERS)) {
      state[id] = {
        visible: visibleLayers[id] && (layerAvailability[id] !== false),
        userVisible: visibleLayers[id],
        available: layerAvailability[id] !== false,
      };
    }
    return state;
  }

  function setLayerVisible(id, visible) {
    visibleLayers[id] = Boolean(visible);
    emitLayerState();
    rerender();
  }

  /* ════════════ pointer / click routing ════════════ */

  function handleClickAt(x, y) {
    const p = screenToDrawn(x, y);
    if (clickMode) {
      const point = canvasToUtm(p.x, p.y);
      if (point) clickMode.onPick(point);
      return;
    }
    const hit = [...targetHitRegions].reverse().find(item => Math.hypot(p.x - item.x, p.y - item.y) <= item.radius);
    selectTarget(hit?.target?.id ?? null, hit?.target ?? null);
  }

  function selectTarget(id, target = null) {
    selectedTargetId = id === undefined || id === null ? null : id;
    const resolved = target
      || (selectedTargetId === null ? null
        : targetsForDisplay(currentData || lastRenderedData || {}).find(item => String(item.id) === String(selectedTargetId))
        || (Number.isFinite(Number(selectedTargetId)) ? { id: selectedTargetId } : null));
    selectionCallback(resolved);
    rerender();
  }

  function onCanvasClick(event) {
    if (pointerDown
      && Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 4) return;
    const bounds = canvas.getBoundingClientRect();
    handleClickAt(event.clientX - bounds.left, event.clientY - bounds.top);
  }

  function setClickMode(mode) {
    clickMode = mode || null;
    canvas.classList?.toggle?.('route-pick-mode', Boolean(clickMode));
  }

  /* ── event wiring ── */
  const disposers = [];
  function listen(target, name, handler, capture) {
    target.addEventListener(name, handler, capture);
    disposers.push(() => target.removeEventListener(name, handler, capture));
  }

  listen(canvas, 'wheel', e => {
    e.preventDefault();
    userAdjusted = true;
    const bounds = canvas.getBoundingClientRect();
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    const p = screenToDrawn(e.clientX - bounds.left, e.clientY - bounds.top);
    zoomAtCanvasPoint(p.x, p.y, factor);
    updateScaleBar();
    rerender();
  }, { passive: false });
  listen(canvas, 'mousedown', e => {
    isPanning = true; lastPanX = e.clientX; lastPanY = e.clientY;
    pointerDown = { x: e.clientX, y: e.clientY };
  });
  if (typeof window !== 'undefined') {
    listen(window, 'mousemove', e => {
      if (!isPanning) return;
      userAdjusted = true;
      const d = screenToDrawn(e.clientX, e.clientY);
      const dPrev = screenToDrawn(lastPanX, lastPanY);
      panX += d.x - dPrev.x; panY += d.y - dPrev.y;
      lastPanX = e.clientX; lastPanY = e.clientY;
      rerender();
    });
    listen(window, 'mouseup', () => { isPanning = false; });
  }
  listen(canvas, 'click', onCanvasClick);

  resize();

  /* ════════════ session lifecycle ════════════ */

  let activeRunId = null;
  function currentRunId() {
    return activeRunId;
  }

  function beginSession(runId) {
    activeRunId = runId || null;
    resetAnimation();
    // Ruling 3: a new session generation resets the view (fit ENC).
    userAdjusted = false;
    encReady = false;
    encInfo = null;
    encImage = null;
    return initENC(activeRunId);
  }

  function clearSession() {
    activeRunId = null;
    cancelENCLoad();
    resetAnimation();
    encInfo = null;
    encImage = null;
    encReady = false;
    setEncStatus('idle');
  }

  /* ════════════ public seam ════════════ */

  const display = {
    render(snapshot) {
      if (!snapshot) return;
      currentData = snapshot;
      queueTelemetryRender(snapshot);
    },
    rerender,
    beginSession,
    clearSession,
    setLayerVisible,
    getLayerState,
    onLayerStateChange(cb) { layerStateSink = cb; },
    setClickMode,
    onSelectionChange(cb) { selectionCallback = cb; },
    selectTarget(id) { selectTarget(id); },
    getSelectedTargetId: () => (selectedTargetId === undefined ? null : selectedTargetId),
    fitView,
    zoomIn() {
      zoomAtCanvasPoint(wrapper.clientWidth / 2, wrapper.clientHeight / 2, 1.25);
      userAdjusted = true;
      updateScaleBar();
      rerender();
    },
    zoomOut() {
      zoomAtCanvasPoint(wrapper.clientWidth / 2, wrapper.clientHeight / 2, 1 / 1.25);
      userAdjusted = true;
      updateScaleBar();
      rerender();
    },
    zoomAt(x, y, factor) {
      zoomAtCanvasPoint(x, y, factor);
      userAdjusted = true;
      updateScaleBar();
      rerender();
    },
    setEncVisible(visible) {
      showENC = Boolean(visible);
      rerender();
    },
    isEncVisible: () => showENC,
    setOrientation(orientation) {
      mapOrientation = orientation === 'heading' ? 'heading' : 'north';
      rerender();
    },
    getOrientation: () => mapOrientation,
    setPlannerSurfaceAttached(attached) {
      plannerSurfaceAttached = Boolean(attached);
      rerender();
    },
    isPlannerSurfaceAttached: () => plannerSurfaceAttached,
    refreshPalette,
    getPalette: () => ({ ...palette }),
    resize,
    // transform accessors (also used by characterization tests)
    worldToCanvas,
    utmToCanvas,
    canvasToUtm,
    getViewScale: () => viewScale,
    getPan: () => ({ x: panX, y: panY }),
    getDrawSequence: () => [...drawSequence],
    getEncStatus: () => encStatus,
    getEncInfo: () => encInfo,
    // exposed for adapter-side click synthesis / tests
    handleClickAt,
    destroy() {
      cancelENCLoad();
      resetAnimation();
      resizeObserver?.disconnect();
      resizeObserver = null;
      while (disposers.length) disposers.pop()();
      if (typeof window !== 'undefined' && isPanning) isPanning = false;
    },
  };

  return display;

  /* local helpers defined after return for hoisting clarity */
  function defaultFetchInfo({ signal } = {}) {
    return fetch('/api/enc_info', { signal });
  }
  function defaultFetchTile() {
    return `/api/enc_tile?t=${Date.now()}`;
  }
  function defaultCreateImage() {
    if (typeof Image === 'undefined') return { complete: false, naturalWidth: 0 };
    return new Image();
  }
  function defaultRaf(cb) {
    if (typeof requestAnimationFrame === 'function') return requestAnimationFrame(cb);
    return setTimeout(() => cb(now() + 16), 16);
  }
  function defaultCancelRaf(id) {
    if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(id);
    else clearTimeout(id);
  }
  function setSpriteSrc(img, src) {
    img.decoding = 'async';
    img.src = src;
  }
  function setTimer(fn, ms) {
    if (typeof window !== 'undefined') return window.setTimeout(fn, ms);
    return setTimeout(fn, ms);
  }
  function clearTimer(id) {
    if (typeof window !== 'undefined') window.clearTimeout(id);
    else clearTimeout(id);
  }
}
