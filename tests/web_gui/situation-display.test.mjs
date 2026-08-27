import assert from 'node:assert/strict';
import test from 'node:test';

// Pure-canvas stubs: the module must run outside a browser.
globalThis.Path2D = class Path2D {
  moveTo() {}
  lineTo() {}
  bezierCurveTo() {}
  closePath() {}
};

function recordingCtx() {
  const calls = [];
  const ctx = new Proxy({}, {
    get(target, prop) {
      if (prop === 'measureText') return () => ({ width: 10 });
      if (prop === 'calls') return calls;
      if (typeof prop === 'string') {
        return (...args) => { calls.push([prop, args]); };
      }
      return undefined;
    },
    set() { return true; },
  });
  return ctx;
}

function fakeCanvas() {
  const listeners = new Map();
  return {
    width: 0,
    height: 0,
    style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    listeners,
    addEventListener(name, fn) { listeners.set(name, fn); },
    removeEventListener(name) { listeners.delete(name); },
    getContext: () => ctxStub,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600 }),
  };
}

const ctxStub = recordingCtx();

let clockNow = 0;
let rafId = 0;

function fakeWrapper(width = 800, height = 600) {
  return { clientWidth: width, clientHeight: height };
}

const ENC_INFO = {
  ready: true,
  run_id: 'run-1',
  origin_e: 300000,
  origin_n: 7000000,
  width: 4000,
  height: 3000,
  utm_zone: 33,
};

function immediateImage() {
  return {
    decoding: '',
    addEventListener() {},
    set src(value) {
      queueMicrotask(() => this.onload?.());
    },
  };
}

async function createDisplay(overrides = {}) {
  const mod = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const canvas = fakeCanvas();
  const options = {
    canvas,
    wrapper: fakeWrapper(),
    createImage: immediateImage,
    fetchInfo: async () => ({ ...ENC_INFO }),
    fetchTile: () => '/api/enc_tile?t=test',
    getResponseRange: () => null,
    getScenarioId: () => 'head_on',
    getPlannerSurface: () => null,
    onEncStatus: () => {},
    onLog: () => {},
    onLayerStateChange: () => {},
    onSelectionChange: () => {},
    now: () => clockNow,
    raf: cb => { clockNow += 16; cb(clockNow); return ++rafId; },
    cancelRaf: () => {},
    ...overrides,
  };
  const display = mod.createSituationDisplay(options);
  return { display, mod, canvas, options };
}

function sampleSnapshot(overrides = {}) {
  return {
    run_id: 'run-1',
    seq: 1,
    state: 'RUNNING',
    sim_time: 10,
    playback: { requested_multiplier: 1 },
    executed_tracker: 'god',
    scenario_id: 'head_on',
    os: { id: 0, x: 100, y: 200, psi: 0, cog: 0, sog: 2, trajectory: [[0, 0], [100, 200]] },
    obstacles: [
      { id: 1, x: 400, y: 600, psi: Math.PI, cog: Math.PI, sog: 3, trajectory: [[400, 600]] },
      { id: 2, x: 900, y: 900, psi: 0, cog: 0, sog: 1, trajectory: [] },
    ],
    truth: [],
    tracks: [],
    measurements: [],
    plans: {
      prediction_horizon: [[100, 200], [260, 380]],
      planner: { horizon_dt_s: 5 },
      target_prediction_horizons: [],
    },
    waypoints: [[0, 1000], [0, 1000]],
    enc_navigation_area: { safe_water: { polygons: [[[[0, 0], [1000, 0], [1000, 800], [0, 800]]]] } },
    encounters: [],
    ...overrides,
  };
}

/* ── Pure functions ─────────────────────────── */

test('validRoute accepts only well-formed [north[], east[]] routes', async () => {
  const { validRoute } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  assert.equal(validRoute([[0, 100], [0, 100]]), true);
  assert.equal(validRoute([[0, 100], [0]]), false);
  assert.equal(validRoute([[0, 100]]), false);
  assert.equal(validRoute(null), false);
  assert.equal(validRoute([[0, 100, 200], [5, 6, 7]]), true);
});

test('chooseGridSpacing picks 1/2/5×10^n with ≤20 divisions', async () => {
  const { chooseGridSpacing } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  // world width 8000 m → raw 800 → mag 100 → 500 keeps ≤20 divisions
  assert.equal(chooseGridSpacing(8000), 500);
  // world width 2000 m → raw 200 → mag 100 → 100 → 20 divisions exactly
  assert.equal(chooseGridSpacing(2000), 100);
  // huge world → smallest option that still keeps ≤20 divisions
  assert.equal(chooseGridSpacing(2e9), 1e8);
});

test('clampZoomScale bounds viewScale into [0.005, 5.0]', async () => {
  const { clampZoomScale } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  assert.equal(clampZoomScale(2, 1000), 5.0);
  assert.equal(clampZoomScale(2, 0.0001), 0.005);
  assert.ok(Math.abs(clampZoomScale(0.45, 1.25) - 0.5625) < 1e-12);
});

test('planner surface routing distinguishes VO, Fan-MPC, and Mid-MPC', async () => {
  const { plannerSurfaceType } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  assert.equal(plannerSurfaceType({ algorithm_id: 'vo' }), 'vo');
  assert.equal(plannerSurfaceType({ algorithm_id: 'potocnik_colreg_fan_mpc' }), 'fan');
  assert.equal(plannerSurfaceType({ algorithm_id: 'mid_mpc_ipopt' }), null);
});

test('Deployment renders FCB and default SOV OpenBridge ship-type icons without sprite cropping', async () => {
  const sources = [];
  function loadedShipTypeImage() {
    return {
      complete: true,
      naturalWidth: 343,
      naturalHeight: 346,
      addEventListener() {},
      set src(value) { sources.push(value); },
    };
  }
  ctxStub.calls.length = 0;
  const { display } = await createDisplay({ createImage: loadedShipTypeImage });
  assert.deepEqual(sources.slice(0, 2), [
    '/static/assets/openbridge/ship-types/fcb45.svg',
    '/static/assets/openbridge/ship-types/sov.svg',
  ]);

  display.render(sampleSnapshot());
  const shipDraws = ctxStub.calls.filter(([name]) => name === 'drawImage');
  assert.equal(shipDraws.length, 3);
  shipDraws.forEach(([, args]) => {
    assert.equal(args.length, 5);
    assert.equal(args[3], args[4]);
  });
});

test('COLAV threat plot derives directional pressure only from approaching stage 2-4 encounters', async () => {
  const { LAYER_ORDER, threatEnvelopeBins } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const bins = threatEnvelopeBins([
    { relative_bearing_deg: 0, stage: 4, signed_tcpa_s: 30 },
    { relative_bearing_deg: 90, stage: 2, signed_tcpa_s: 120 },
    { relative_bearing_deg: 180, stage: 4, signed_tcpa_s: -10 },
    { relative_bearing_deg: -90, stage: 1, signed_tcpa_s: 300 },
  ]);
  assert.equal(bins.length, 16);
  assert.equal(bins[0], 1);
  assert.equal(bins[4], 0.5);
  assert.equal(bins[8], 0);
  assert.equal(bins[12], 0);
  assert.ok(!LAYER_ORDER.includes('relativeCompass'));
  assert.ok(LAYER_ORDER.indexOf('threatPlot') < LAYER_ORDER.indexOf('ships'));
});

test('ownship threat plot uses a transparent 4L outer radius with labels outside and no SOG', async () => {
  const {
    THREAT_PLOT_BACKGROUND,
    THREAT_PLOT_RANGE_M,
    threatPlotLayout,
  } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const fitted = threatPlotLayout(0.06);
  const zoomedIn = threatPlotLayout(0.12);
  assert.equal(THREAT_PLOT_RANGE_M, 180);
  assert.equal(THREAT_PLOT_BACKGROUND, 'rgba(0,0,0,0)');
  assert.ok(Math.abs(fitted.radius - 10.8) < 1e-9);
  assert.ok(Math.abs(zoomedIn.radius - fitted.radius * 2) < 1e-9);
  assert.ok(fitted.labelRadius > fitted.radius);

  ctxStub.calls.length = 0;
  const { display } = await createDisplay();
  const snapshot = sampleSnapshot({ encounters: [
    { relative_bearing_deg: 0, stage: 3, signed_tcpa_s: 90 },
  ] });
  const ownshipPoint = display.worldToCanvas(snapshot.os.x, snapshot.os.y);
  display.render(snapshot);
  const textCalls = ctxStub.calls.filter(([name]) => name === 'fillText').map(([, args]) => args);
  assert.equal(textCalls.some(([text]) => text === 'OS'), false);
  assert.equal(textCalls.some(([text]) => String(text).startsWith('SOG ')), false);
  assert.ok(ownshipPoint);
});

test('mission route corridor offsets port and starboard boundaries by 4L', async () => {
  const {
    ROUTE_CORRIDOR_HALF_WIDTH_M,
    routeCorridorBoundaries,
  } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const corridor = routeCorridorBoundaries([[0, 1000], [0, 0]]);
  assert.equal(ROUTE_CORRIDOR_HALF_WIDTH_M, 180);
  assert.deepEqual(corridor.port, [{ north: 0, east: 180 }, { north: 1000, east: 180 }]);
  assert.deepEqual(corridor.starboard, [{ north: 0, east: -180 }, { north: 1000, east: -180 }]);
});

test('ownship future motion uses a black double-chevron arrow', async () => {
  const { drawDoubleChevron } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const surface = recordingCtx();
  drawDoubleChevron(surface, { x: 10, y: 20 }, 0);
  assert.equal(surface.calls.filter(([name]) => name === 'stroke').length, 4);
  assert.equal(surface.calls.some(([name]) => name === 'fill'), false);
});

test('COLAV threat plot is hidden by default and toggles only from the ownship hit region', async () => {
  const { display } = await createDisplay();
  const snapshot = sampleSnapshot({ encounters: [
    { relative_bearing_deg: 0, stage: 3, signed_tcpa_s: 90 },
  ] });
  display.render(snapshot);
  assert.equal(display.isOwnshipThreatPlotVisible(), false);
  assert.equal(display.getDrawSequence().includes('threatPlot'), false);
  const ownship = display.worldToCanvas(snapshot.os.x, snapshot.os.y);
  display.handleClickAt(ownship.x, ownship.y);
  assert.equal(display.isOwnshipThreatPlotVisible(), true);
  assert.equal(display.getDrawSequence().includes('threatPlot'), true);
  display.handleClickAt(ownship.x, ownship.y);
  assert.equal(display.isOwnshipThreatPlotVisible(), false);
});

test('interpolateTelemetry interpolates positions and wraps angles per vessel id', async () => {
  const { interpolateTelemetry } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const from = {
    run_id: 'a', sim_time: 0,
    os: { id: 0, x: 0, y: 0, psi: 0.1, cog: 0.1 },
    obstacles: [{ id: 1, x: 0, y: 0, psi: 3.0, cog: 3.0 }],
    truth: [],
  };
  const to = {
    run_id: 'a', sim_time: 1,
    os: { id: 0, x: 10, y: -4, psi: -0.1, cog: -0.1 },
    obstacles: [{ id: 1, x: 6, y: 6, psi: -3.0, cog: -3.0 }, { id: 2, x: 5, y: 5, psi: 0, cog: 0 }],
    truth: [],
  };
  const mid = interpolateTelemetry(from, to, 0.5);
  assert.equal(mid.os.x, 5);
  assert.equal(mid.os.y, -2);
  assert.ok(Math.abs(mid.os.psi) < 1e-9); // shortest-way angle wrap
  assert.equal(mid.obstacles[0].x, 3);
  // new target in `to` passes through unchanged at its own coordinates
  assert.equal(mid.obstacles[1].x, 5);
  // run mismatch → passthrough of `to`
  assert.equal(interpolateTelemetry(from, { ...to, run_id: 'b' }, 0.5).os.x, 10);
});

test('telemetryRenderDurationMs clamps to [100, 1000] ms scaled by playback multiplier', async () => {
  const { telemetryRenderDurationMs } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  assert.equal(telemetryRenderDurationMs(null, null), 100);
  assert.equal(telemetryRenderDurationMs({ sim_time: 0 }, { sim_time: 1, playback: { requested_multiplier: 1 } }), 1000);
  assert.equal(telemetryRenderDurationMs({ sim_time: 0 }, { sim_time: 1, playback: { requested_multiplier: 10 } }), 100);
  assert.equal(telemetryRenderDurationMs({ sim_time: 5 }, { sim_time: 5.01, playback: { requested_multiplier: 1 } }), 100);
});

test('updateFrozenRoute freezes first valid route per run and re-freezes per new run', async () => {
  const { updateFrozenRoute } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const routes = new Map();
  const first = updateFrozenRoute(routes, { run_id: 'r1', waypoints: [[0, 100], [0, 100]] });
  const changed = updateFrozenRoute(routes, { run_id: 'r1', waypoints: [[9, 9], [9, 9]] });
  assert.deepEqual(changed, first);
  assert.deepEqual([...changed[0]], [0, 100]); // frozen copy, not live reference
  const next = updateFrozenRoute(routes, { run_id: 'r2', waypoints: [[1, 2], [3, 4]] });
  assert.deepEqual(next, [[1, 2], [3, 4]]);
  assert.deepEqual(updateFrozenRoute(routes, { run_id: 'r2', waypoints: null }), next);
  assert.deepEqual(updateFrozenRoute(routes, { waypoints: [[7, 7], [7, 7]] }), [[7, 7], [7, 7]], 'unbound run has its own key');
});

test('Historical AIS reference route uses normal waypoint labels', async () => {
  const { waypointLabel } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);

  assert.equal(waypointLabel(1, 'hais_romsdal_20260701_120007_121007'), 'WPT2');
  assert.equal(waypointLabel(1, 'head_on'), 'WPT2');
});

/* ── Instance seam ──────────────────────────── */

test('utmToCanvas / canvasToUtm round-trip through the ENC origin mapping', async () => {
  const { display } = await createDisplay();
  await display.beginSession('run-1');
  const utm = { east: ENC_INFO.origin_e + 500, north: ENC_INFO.origin_n + 250 };
  const px = display.utmToCanvas(utm.east, utm.north);
  const back = display.canvasToUtm(px.x, px.y);
  assert.ok(Math.abs(back.east - utm.east) < 1e-6);
  assert.ok(Math.abs(back.north - utm.north) < 1e-6);
  // North must point up on canvas: larger northing → smaller canvas y
  const furtherNorth = display.utmToCanvas(utm.east, utm.north + 100);
  assert.ok(furtherNorth.y < px.y);
});

test('fitView sizes the ENC tile to the wrapper without user adjustment, and resize refits until the user pans/zooms', async () => {
  const wrapper = fakeWrapper(800, 600);
  const { display } = await createDisplay({ wrapper });
  await display.beginSession('run-1');
  display.fitView();
  const scaleAfterFit = display.getViewScale();
  assert.ok(scaleAfterFit > 0);
  // wrapper grows, user never adjusted → refit
  wrapper.clientWidth = 1200;
  display.resize();
  assert.notEqual(display.getViewScale(), scaleAfterFit);
  // user zooms once → resize preserves pan/zoom exactly
  display.zoomAt(400, 300, 1.25);
  const userScale = display.getViewScale();
  const userPan = display.getPan();
  wrapper.clientWidth = 1600;
  display.resize();
  assert.equal(display.getViewScale(), userScale);
  assert.deepEqual(display.getPan(), userPan);
  // explicit fitView resets and clears the user-adjusted flag again
  wrapper.clientWidth = 800;
  display.fitView();
  display.resize();
  assert.notEqual(display.getViewScale(), userScale);
});

test('recenterOwnship places ownship at the viewport centre for every scenario', async () => {
  const wrapper = fakeWrapper(800, 600);
  const { display } = await createDisplay({ wrapper });
  const snapshot = sampleSnapshot({ scenario_id: 'head_on' });
  display.render(snapshot);

  assert.notDeepEqual(display.worldToCanvas(snapshot.os.x, snapshot.os.y), { x: 400, y: 300 });
  display.recenterOwnship();
  assert.deepEqual(display.worldToCanvas(snapshot.os.x, snapshot.os.y), { x: 400, y: 300 });
});

test('render draws the documented LAYER_ORDER sequence and layer toggles filter it', async () => {
  const { display, mod } = await createDisplay();
  display.render(sampleSnapshot());
  const full = display.getDrawSequence();
  const order = full.filter(id => mod.LAYER_ORDER.includes(id));
  // sample has no tracker track states, no busy-water target routes, no planner
  // surface attach, and previousPrediction defaults off
  const skip = new Set([
    'tracks',
    'targetRoutes',
    'plannerSurface',
    'threatPlot',
    'shadowOwnship',
    'previousPrediction',
    'targetPredictions',
    'measurements',
  ]);
  const expected = mod.LAYER_ORDER.filter(id => !skip.has(id));
  assert.deepEqual(order, expected);
  assert.ok(full.includes('base'));
  assert.ok(full.includes('grid'), 'grid drawn when ENC-less');
  // default-off layers stay off
  const state = display.getLayerState();
  assert.equal(state.previousPrediction.visible, false);
  assert.equal(state.truth.visible, false);
  // toggling a layer removes exactly its entry
  display.setLayerVisible('route', false);
  display.setLayerVisible('waypoints', false);
  display.render(sampleSnapshot({ seq: 2 }));
  const filtered = display.getDrawSequence();
  assert.equal(filtered.includes('route'), false);
  assert.equal(filtered.includes('waypoints'), false);
  assert.ok(filtered.includes('history'));
  // layer visibility survives across renders (view preference)
  assert.equal(display.getLayerState().route.visible, false);
});

test('hit-testing resolves the topmost (last drawn) target and reports selection changes', async () => {
  const selections = [];
  const { display } = await createDisplay({ onSelectionChange: t => selections.push(t) });
  await display.beginSession('run-1');
  // Both targets near the same canvas point; later obstacle (id 2) is drawn last → wins.
  display.render(sampleSnapshot({ obstacles: [
    { id: 1, x: 100, y: 100, psi: 0, cog: 0, sog: 1 },
    { id: 2, x: 101, y: 101, psi: 0, cog: 0, sog: 1 },
  ] }));
  const px = display.worldToCanvas(101, 101);
  display.handleClickAt(px.x, px.y);
  assert.equal(selections.at(-1)?.id, 2);
  assert.equal(display.getSelectedTargetId(), 2);
  // programmatic selection mirrors the same channel
  display.selectTarget(1);
  assert.equal(display.getSelectedTargetId(), 1);
  display.handleClickAt(5, 5); // empty water clears selection
  assert.equal(display.getSelectedTargetId(), null);
  assert.equal(selections.at(-1), null);
});

test('OpenBridge target markers receive rotated screen anchors and selection context', async () => {
  const markerFrames = [];
  const selections = [];
  const { display } = await createDisplay({
    onTargetMarkersChange: markers => markerFrames.push(markers),
    onSelectionChange: (target, context) => selections.push({ target, context }),
  });
  const snapshot = sampleSnapshot();
  display.render(snapshot);

  const markers = markerFrames.at(-1);
  assert.equal(markers.length, 2);
  assert.deepEqual(markers.map(marker => marker.id), [1, 2]);
  assert.ok(markers.every(marker => Number.isFinite(marker.anchor.x) && Number.isFinite(marker.anchor.y)));
  assert.equal(markers[0].headingDeg, 180);

  const first = markers[0];
  display.handleClickAt(first.anchor.x, first.anchor.y);
  assert.equal(selections.at(-1).target.id, 1);
  assert.deepEqual(selections.at(-1).context.anchor, first.anchor);

  const headingFrames = [];
  const { display: headingDisplay } = await createDisplay({
    onTargetMarkersChange: markers => headingFrames.push(markers),
  });
  headingDisplay.setOrientation('heading');
  headingDisplay.render({ ...snapshot, os: { ...snapshot.os, psi: Math.PI / 2 } });
  const headingUp = headingFrames.at(-1).find(marker => marker.id === 1);
  assert.equal(headingUp.headingDeg, 90);
});

test('registered click mode intercepts clicks with UTM coords and is mutually exclusive with selection', async () => {
  const picks = [];
  const selections = [];
  const { display } = await createDisplay({ onSelectionChange: t => selections.push(t) });
  await display.beginSession('run-1');
  display.render(sampleSnapshot());
  display.setClickMode({
    id: 'route-pick',
    onPick: point => picks.push(point),
  });
  const target = display.utmToCanvas(ENC_INFO.origin_e + 300, ENC_INFO.origin_n + 300);
  display.handleClickAt(target.x, target.y);
  assert.equal(picks.length, 1);
  assert.ok(Math.abs(picks[0].east - (ENC_INFO.origin_e + 300)) < 1e-6);
  assert.ok(Math.abs(picks[0].north - (ENC_INFO.origin_n + 300)) < 1e-6);
  assert.equal(display.getSelectedTargetId(), null, 'no selection while a click mode is registered');
  display.setClickMode(null);
  display.handleClickAt(target.x, target.y); // resumes default selection behaviour
  assert.ok(selections.length > 0);
});

test('ENC generation guards: a new session generation cancels in-flight loads and refits the view', async () => {
  const wrapper = fakeWrapper(800, 600);
  const resolvers = [];
  const { display } = await createDisplay({
    wrapper,
    fetchInfo: () => new Promise(resolve => { resolvers.push(resolve); }),
  });
  const first = display.beginSession('run-1');
  const second = display.beginSession('run-2');
  // resolve every in-flight fetch; only the newest generation may act on it
  for (const resolve of resolvers) resolve({ ...ENC_INFO, run_id: 'run-2' });
  await second;
  assert.equal(display.getEncStatus(), 'ready');
  assert.equal(display.getEncInfo().run_id, 'run-2');
  await first.catch(() => {});
  assert.equal(display.getViewScale(), Math.max(800 / ENC_INFO.width, 600 / ENC_INFO.height));
});

test('destroy removes canvas listeners and is idempotent', async () => {
  const { display, canvas } = await createDisplay();
  await display.beginSession('run-1');
  assert.ok(canvas.listeners.size > 0);
  display.destroy();
  assert.equal(canvas.listeners.size, 0);
  display.destroy();
});

test('targetsForDisplay prefers tracker states unless executed_tracker is god', async () => {
  const { targetsForDisplay } = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);
  const obstacle = { id: 1, x: 0, y: 0, psi: 1, cog: 1, sog: 5 };
  const data = {
    executed_tracker: 'ekf',
    obstacles: [obstacle],
    tracks: [{ states: [[10, 20, 3, 4]], labels: [7], generations: [4], covariances: [] }],
  };
  const [fromTracker] = targetsForDisplay(data);
  assert.equal(fromTracker.id, 7);
  assert.equal(fromTracker.generation, 4);
  assert.equal(fromTracker.x, 10);
  assert.equal(fromTracker.source, 'tracker');
  const [fromGod] = targetsForDisplay({ ...data, executed_tracker: 'god' });
  assert.equal(fromGod.id, 1);
  assert.equal(fromGod.generation, null);
  assert.equal(fromGod.x, 0);
});

/* ── Fix-round regressions ──────────────────── */

test('app.js never references the module-closure animation pipeline vars (P0 regression)', async () => {
  const { readFile } = await import('node:fs/promises');
  const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
  for (const name of ['renderFrameId', 'renderFromData', 'renderToData', 'renderStartedAt', 'renderDurationMs']) {
    assert.doesNotMatch(
      app,
      new RegExp(`\\b${name}\\b`),
      `app.js must not reference situation-display closure var ${name}; the module resets its own animation state`,
    );
  }
});

test('Config preview adapter is transparent, sprite-less, and side-effect free (P2 fix-round)', async () => {
  const { readFile } = await import('node:fs/promises');
  const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
  assert.match(shell, /backgroundMode: 'transparent'/);
  assert.match(shell, /loadSprites: false/);
  // module: no document access; scale-label DOM writes go through the
  // injected onScaleLabel sink only
  const mod = await readFile(new URL('../../web_gui/modules/situation-display.js', import.meta.url), 'utf8');
  assert.doesNotMatch(mod, /getElementById/);
  assert.match(mod, /onScaleLabel/);
  assert.match(mod, /backgroundMode !== 'transparent'/);
});

test('LAYER_ORDER sequence claims a slot only when something drew (fix-round tightening)', async () => {
  const { display } = await createDisplay();
  display.render(sampleSnapshot({
    plans: {
      prediction_horizon: [[100, 200]], // single point — not drawable
      target_prediction_horizons: [[[5, 5]]], // single point — not drawable
      planner: { horizon_dt_s: 5 },
    },
  }));
  const seq = display.getDrawSequence();
  assert.equal(seq.includes('prediction'), false);
  assert.equal(seq.includes('targetPredictions'), false);
  display.render(sampleSnapshot({ seq: 2 })); // two-point horizons draw again
  assert.ok(display.getDrawSequence().includes('prediction'));
});

test('Historical AIS follows Ownship at 6NM span and draws comparison-only Shadow', async () => {
  const wrapper = fakeWrapper(800, 600);
  const { display } = await createDisplay({ wrapper });
  const snapshot = sampleSnapshot({
    scenario_id: 'hais_romsdal_20260701_120007_121007',
    os: { id: 0, x: 100, y: 200, psi: 0, cog: 0, sog: 4, trajectory: [] },
    shadow_ownship: {
      id: 'shadow-ownship', label: 'AIS SHADOW', x: 130, y: 250,
      psi: 0.1, cog: 0.1, sog: 4, trajectory: [[110, 220], [130, 250]], comparison_only: true,
    },
  });

  display.render(snapshot);

  assert.equal(display.getViewScale(), 800 / (6 * 1852));
  assert.deepEqual(display.worldToCanvas(100, 200), { x: 400, y: 300 });
  assert.ok(display.getDrawSequence().includes('shadowOwnship'));
});
