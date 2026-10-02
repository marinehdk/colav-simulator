import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// Pure-canvas stubs: the module must run outside a browser.
globalThis.Path2D = class Path2D {
  moveTo() {}
  lineTo() {}
  bezierCurveTo() {}
  closePath() {}
};

const ais = await import(new URL('../../web_gui/modules/ais-display.js', import.meta.url).href);
const situation = await import(new URL('../../web_gui/modules/situation-display.js', import.meta.url).href);

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
    set(target, prop, value) {
      calls.push([`set:${String(prop)}`, [value]]);
      return true;
    },
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

function createDisplay(overrides = {}) {
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
  const display = situation.createSituationDisplay(options);
  return { display, options };
}

function aisSnapshot(overrides = {}) {
  return {
    run_id: 'run-1',
    seq: 1,
    state: 'RUNNING',
    sim_time: 10,
    playback: { requested_multiplier: 1 },
    executed_tracker: 'god',
    scenario_id: 'head_on',
    os: { id: 0, x: 100, y: 200, psi: 0, cog: 0, sog: 2, trajectory: [] },
    obstacles: [
      { id: 1, x: 400, y: 600, psi: 0.5, cog: 0.5, sog: 3, trajectory: [], ais: { age_s: 0.2, state: 'active' } },
      { id: 2, x: 900, y: 120, psi: 0, cog: 0, sog: 0, trajectory: [], ais: { age_s: 1.0, state: 'sleeping' } },
      { id: 3, x: 1200, y: 700, psi: 1, cog: 1, sog: 4, trajectory: [], ais: { age_s: 61.0, state: 'lost' } },
    ],
    truth: [],
    tracks: [],
    measurements: [],
    plans: { prediction_horizon: [], planner: {}, target_prediction_horizons: [] },
    waypoints: [[], []],
    enc_navigation_area: null,
    encounters: [],
    ...overrides,
  };
}

/* ── state machine composition ── */

test('symbol state composes backend state with the risk rank (danger only when activated)', () => {
  assert.equal(ais.aisSymbolState({ state: 'active' }, 0), 'active');
  assert.equal(ais.aisSymbolState({ state: 'active' }, 2), 'active');
  assert.equal(ais.aisSymbolState({ state: 'active' }, 3), 'dangerous');
  assert.equal(ais.aisSymbolState({ state: 'sleeping' }, 3), 'sleeping');
  assert.equal(ais.aisSymbolState({ state: 'lost' }, 3), 'lost');
  // Missing/degenerate backend objects degrade to sleeping, never to danger.
  assert.equal(ais.aisSymbolState(null, 3), 'sleeping');
  assert.equal(ais.aisSymbolState({}, 3), 'sleeping');
});

test('blink phase is a deterministic half-period square wave', () => {
  assert.equal(ais.AIS_BLINK_PERIOD_MS, 1000);
  assert.equal(ais.aisBlinkOn(0), true);
  assert.equal(ais.aisBlinkOn(499), true);
  assert.equal(ais.aisBlinkOn(500), false);
  assert.equal(ais.aisBlinkOn(999), false);
  assert.equal(ais.aisBlinkOn(1000), true);
  assert.equal(ais.aisBlinkOn(0, 0), true); // degenerate period stays lit
});

/* ── association matching ── */

test('association matches the nearest track within the gate and flags radar echoes', () => {
  assert.equal(ais.AIS_TRACK_ASSOCIATION_RADIUS_M, 150);
  const targets = [{ id: 5, x: 1000, y: 0, ais: { state: 'active' } }];
  const trackSet = {
    labels: [2],
    generations: [1],
    states: [[1100, 0, -3, 0], [5000, 5000, 0, 0]],
  };
  const map = ais.matchAisAssociations(targets, trackSet, [[1050, 30]]);
  assert.equal(map.get('5').trackId, 2);
  assert.equal(map.get('5').generation, 1);
  assert.equal(map.get('5').radar, true);
});

test('association leaves uncorrelated targets independent', () => {
  const map = ais.matchAisAssociations([{ id: 7, x: 0, y: 0, ais: { state: 'active' } }], {
    labels: [1], generations: [0], states: [[400, 0, 0, 0]],
  }, [[900, 900]]);
  const association = map.get('7');
  assert.equal(association.trackId, null);
  assert.equal(association.radar, false);
  assert.equal(ais.associationLabel(association), '独立目标');
});

test('association labels name the fused track and radar echo', () => {
  assert.equal(ais.associationLabel({ trackId: 2, generation: 1, radar: false }), 'TS2（融合）');
  assert.equal(ais.associationLabel({ trackId: null, generation: null, radar: true }), '雷达回波');
  assert.equal(ais.associationLabel({ trackId: 3, generation: null, radar: true }), 'TS3（融合） + 雷达回波');
  assert.equal(ais.associationLabel(null), '独立目标');
});

test('radar measurement points drop clutter and need an ENC origin', () => {
  const groups = [
    [[0, [7000100, 300200]], [1, [7000500, 300500]]],
    [[-1, [7000900, 300900]]], // clutter (do_idx -1)
    [[2, [NaN, 1]]], // non-finite dropped
  ];
  const points = ais.localRadarMeasurementPoints(groups, { origin_n: 7000000, origin_e: 300000 });
  assert.deepEqual(points, [[100, 200], [500, 500]]);
  assert.deepEqual(ais.localRadarMeasurementPoints(groups, null), []);
});

/* ── symbol renderer ── */

test('symbol renderer draws the SVG asset when loaded and falls back to vectors', () => {
  const surface = recordingCtx();
  const loaded = { complete: true, naturalWidth: 32 };
  ais.drawAisSymbol(surface, 40, 50, 0.7, 'active', { images: { active: loaded } });
  const draw = surface.calls.find(([name]) => name === 'drawImage');
  assert.ok(draw, 'asset path draws the image');
  assert.deepEqual(draw[1], [loaded, -13, -13, 26, 26]);

  const fallback = recordingCtx();
  ais.drawAisSymbol(fallback, 10, 10, 0, 'sleeping', { images: null });
  assert.ok(fallback.calls.some(([name]) => name === 'fill'), 'fallback fills the triangle');
  assert.ok(!fallback.calls.some(([name]) => name === 'drawImage'));

  const lost = recordingCtx();
  ais.drawAisSymbol(lost, 10, 10, 0, 'lost', {});
  assert.ok(lost.calls.some(([name, args]) => name === 'moveTo' && args[0] < 0 && args[1] < 0), 'lost fallback draws the cross');
});

test('flashing states dim while the blink phase is off', () => {
  const surface = recordingCtx();
  ais.drawAisSymbol(surface, 0, 0, 0, 'dangerous', { blinkOn: false });
  const alpha = surface.calls.filter(([name]) => name === 'set:globalAlpha').map(([, args]) => args[0]);
  assert.equal(alpha[0], 0.25, 'off-phase flashing state dims (stub *= reads give NaN afterwards)');
  const lit = recordingCtx();
  ais.drawAisSymbol(lit, 0, 0, 0, 'dangerous', { blinkOn: true });
  assert.equal(lit.calls.some(([name, args]) => name === 'set:globalAlpha' && args[0] === 0.25), false);
});

/* ── 2D layer integration (draw order, toggle, hit-test) ── */

test('aisTargets layer draws last, toggles off, and its symbols win the shared hit-test', () => {
  const { display } = createDisplay();
  display.render(aisSnapshot());
  assert.equal(situation.LAYER_ORDER.at(-1), 'aisTargets');
  assert.equal(display.getDrawSequence().at(-1), 'aisTargets');
  assert.equal(display.getLayerState().aisTargets.available, true);

  // AIS symbol hit region is pushed after the ships regions → wins, and the
  // selection context carries viaAis so the adapter opens the AIS card.
  const point = display.worldToCanvas(400, 600);
  const selections = [];
  display.onSelectionChange((target, context) => selections.push({ target, context }));
  display.handleClickAt(point.x, point.y);
  assert.equal(String(selections.at(-1)?.target.id), '1');
  assert.equal(selections.at(-1)?.target.ais.state, 'active');
  assert.equal(selections.at(-1)?.context.viaAis, true);
  // Plain programmatic selection (vessel-marker path) carries no viaAis.
  display.selectTarget('2');
  assert.equal(String(selections.at(-1)?.target.id), '2');
  assert.equal(selections.at(-1)?.context.viaAis, undefined);

  display.setLayerVisible('aisTargets', false);
  display.render(aisSnapshot({ seq: 2 }));
  assert.equal(display.getDrawSequence().includes('aisTargets'), false);
  assert.equal(display.getLayerState().aisTargets.available, true);
});

test('AIS DOM markers carry anchors, rotations and states for the deployment layer', () => {
  const sinks = [];
  const { display } = createDisplay({ onAisMarkersChange: markers => sinks.push(markers) });
  display.render(aisSnapshot());
  const markers = sinks.at(-1);
  assert.equal(markers.length, 3);
  const active = markers.find(marker => String(marker.id) === '1');
  assert.equal(active.state, 'active');
  assert.ok(Number.isFinite(active.anchor.x) && Number.isFinite(active.anchor.y));
  assert.equal(active.rotationDeg, 29); // heading 0.5 rad minus headingRotation 0
  assert.equal(markers.find(marker => String(marker.id) === '2').state, 'sleeping');
  assert.equal(markers.find(marker => String(marker.id) === '3').state, 'lost');

  // Clearing the session empties the DOM marker layer.
  display.clearSession();
  assert.deepEqual(sinks.at(-1), []);
});

test('aisTargets layer is unavailable when the transport carries no AIS objects', () => {
  const { display } = createDisplay();
  const snapshot = aisSnapshot();
  snapshot.obstacles = snapshot.obstacles.map(({ ais: omitted, ...target }) => target);
  display.render(snapshot);
  assert.equal(display.getLayerState().aisTargets.available, false);
});

test('dangerous/lost targets drive the blink timer and stop it when cleared', () => {
  const realSetTimeout = globalThis.setTimeout;
  const realClearTimeout = globalThis.clearTimeout;
  const timers = [];
  globalThis.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  globalThis.clearTimeout = id => { delete timers[id - 1]; };
  try {
    const { display } = createDisplay();
    display.render(aisSnapshot());
    assert.equal(timers.filter(Boolean).length, 1, 'lost target schedules the blink timer');
    display.render(aisSnapshot({ seq: 2 }));
    assert.equal(timers.filter(Boolean).length, 1, 'timer stays single');
    const snapshot = aisSnapshot({ seq: 3 });
    snapshot.obstacles = snapshot.obstacles.map(({ ais: omitted, ...target }) => target);
    display.render(snapshot);
    assert.equal(timers.filter(Boolean).length, 0, 'no flashing targets stops the timer');
  } finally {
    globalThis.setTimeout = realSetTimeout;
    globalThis.clearTimeout = realClearTimeout;
  }
});

/* ── static integration (shell + 3D seam) ── */

test('shell, module and 3D scene wire the AIS layer end to end', async () => {
  const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
  const [html, app, scene3d, sceneTarget, sleeping, active, dangerous, lost] = await Promise.all([
    readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8'),
    readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../../web_gui/modules/scene-3d.js', import.meta.url), 'utf8'),
    readFile(new URL('../../web_gui/modules/scene-target.js', import.meta.url), 'utf8'),
    readFile(new URL('../../web_gui/assets/ais-sleeping.svg', import.meta.url), 'utf8'),
    readFile(new URL('../../web_gui/assets/ais-active.svg', import.meta.url), 'utf8'),
    readFile(new URL('../../web_gui/assets/ais-dangerous.svg', import.meta.url), 'utf8'),
    readFile(new URL('../../web_gui/assets/ais-lost.svg', import.meta.url), 'utf8'),
  ]);
  // Chart display popover: layer switch coexisting with the ships layer.
  assert.match(html, /<input type="checkbox" data-layer="aisTargets" checked> AIS 目标</);
  assert.match(html, /data-legend-layer="aisTargets"[^<]*<span class="color-box ais-target"><\/span>AIS 目标/);
  // AIS target card placard.
  assert.match(html, /id="aisDetailPlacard"/);
  assert.match(html, /id="aisPlacardSymbol" src="\/static\/assets\/ais-active\.svg"/);
  for (const id of ['aisPlacardMmsi', 'aisPlacardSog', 'aisPlacardCog', 'aisPlacardHdg', 'aisPlacardAge', 'aisPlacardState', 'aisPlacardAssociation']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  // App adapter: card routing (AIS symbol clicks only) + DOM marker layer.
  assert.match(app, /from '\.\/modules\/ais-display\.js/);
  assert.match(app, /function showAisPlacard\(target/);
  assert.match(app, /onAisMarkersChange: renderAisMarkers/);
  assert.match(app, /function renderAisMarkers\(markers = \[\]\)/);
  assert.match(app, /getElementById\('aisMarkerLayer'\)/);
  assert.match(app, /situationDisplay\.selectTarget\(host\.dataset\.targetId, \{ viaAis: true \}\)/);
  assert.match(app, /if \(context\.viaAis\) \{/);
  assert.match(app, /aisSymbolState\(ais, riskRankForAisTarget\(target\)\)/);
  assert.match(html, /id="aisMarkerLayer"/);
  assert.match(styles, /\.ais-marker\.flashing img/);
  // 3D: billboards follow the layer switch; card rows include AIS fields.
  assert.match(scene3d, /updateAisMarkers\(ships\)/);
  assert.match(scene3d, /chart\.getLayerState\(\)\.aisTargets\?\.visible !== false/);
  assert.match(scene3d, /image: AIS_SYMBOL_ASSETS\[state\]/);
  assert.match(sceneTarget, /aisCardRows\(projection, ship, encInfo\)/);
  // SVG assets carry the IMO SN.1/Circ.243 symbol semantics.
  for (const [svg, clause] of [
    [sleeping, 'sleeping AIS target is an acute'],
    [active, 'activated AIS target enlarges'],
    [dangerous, 'bold red filled triangle'],
    [lost, 'lost AIS target'],
  ]) {
    assert.match(svg, /SN\.1\/Circ\.243\/Rev\.1/);
    assert.match(svg, new RegExp(clause));
  }
});
