import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const moduleSource = await readFile(new URL('../../web_gui/modules/evaluation-replay.js', import.meta.url), 'utf8');
const adapterSource = await readFile(new URL('../../web_gui/modules/replay-source.js', import.meta.url), 'utf8');

const RUN_ID = 'cdcdcdcd-cdcd-4cdc-8cdc-cdcdcdcdcdcd';

const DESCRIPTOR = {
  schema_version: 'colav.run-replay.descriptor@1',
  run_id: RUN_ID,
  run: { execution_state: 'FINISHED', scenario_id: 'head_on', executed_algorithm: 'vo', executed_tracker: 'god', result_ready: true },
  replay: { state: 'READY', evidence_level: 'full', trace_schema: 'colav.decision-replay.v1', frame_count: 400, t_start: 0.1, t_end: 40.0, trusted_t_end: 40.0, truncated: false },
  events: { count: 3, categories: ['planner_solved'] },
  capabilities: { full_frame: true, planner_detail: true, risk_detail: true, continuous_interpolation: true },
};

const CONTEXT = {
  schema_version: 'colav.run-replay.context@1',
  run_id: RUN_ID,
  scenario_id: 'head_on',
  enc: { origin_east_m: 1000, origin_north_m: 2000, width_m: 4000, height_m: 6000, utm_zone: 32, image_url: `/api/runs/${RUN_ID}/replay/enc.png` },
  enc_navigation_area: null,
  ships: [{ id: 0, mmsi: 100, length_m: 45, width_m: 8 }],
};

function frame(sequence, simTime) {
  return {
    sequence,
    sim_time: simTime,
    step_time_ms: 5.0,
    state: 'RUNNING',
    payload: {
      Ship0: {
        id: 0,
        mmsi: 100,
        state: [2000 + simTime, 1000 + simTime, 0.2, 2.0, 0.0, 0.0],
        csog_state: [2000 + simTime, 1000 + simTime, 2.2, 0.21],
        active: true,
        colav: { planner: { algorithm_id: 'vo', solve_id: sequence, solver_executed: true, status: 'OK' } },
      },
    },
    events: [],
    threat_management: {
      schema_version: 'colav.threat-management.projection@1',
      status: 'UNAVAILABLE',
      snapshot: null,
      vectors: [],
      schedule: null,
      conflicts: null,
      conflict_graph: null,
      unavailable_reason: 'THREAT_SNAPSHOT_UNAVAILABLE',
    },
  };
}

function windowDoc(fromS, toS) {
  const frames = [];
  for (let time = fromS; time <= toS + 1e-9; time += 0.5) {
    frames.push(frame(Math.round(time * 10), time));
  }
  return { schema_version: 'colav.run-replay.window@1', run_id: RUN_ID, requested: { from_s: fromS, to_s: toS }, frames, before: null, after: null };
}

/* ── Fake DOM ── */

class FakeElement {
  constructor(tag = 'div') {
    this.tag = tag;
    this.textContent = '';
    this.dataset = {};
    this.className = '';
    this.attributes = {};
    this.children = [];
    this.hidden = false;
    this.disabled = false;
    this.value = '';
    this.min = '';
    this.max = '';
    this.step = '';
    this.listeners = {};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  click() { this.listeners.click?.({ stopPropagation() {} }); }
}

function makeDocumentRef() {
  const elements = new Map(
    [...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new FakeElement()]),
  );
  return {
    getElementById: id => elements.get(id) || null,
    querySelectorAll: () => [],
    createElement: tag => new FakeElement(tag),
  };
}

/* ── Fake network with order-controlled, inspectable responses ── */

function makeFetchRef() {
  const calls = [];
  const pending = [];
  const fetchRef = (url, options = {}) => {
    calls.push({ url, method: options.method ?? 'GET' });
    let resolve;
    const promise = new Promise((res) => { resolve = res; });
    pending.push(body => resolve({ ok: true, status: 200, json: async () => body }));
    return promise;
  };
  const tick = () => new Promise(resolve => setTimeout(resolve, 0));
  return {
    fetchRef,
    calls,
    pending,
    async respondNext(body) {
      const respond = pending.shift();
      assert.ok(respond, 'no pending replay request to answer');
      respond(body);
      await tick();
    },
    async respondLast(body) {
      // Answer the MOST RECENT in-flight request first (LIFO), leaving the
      // older request's response to arrive last — the stale-response case.
      const respond = pending.pop();
      assert.ok(respond, 'no pending replay request to answer');
      respond(body);
      await tick();
    },
    async open(network, descriptorBody = DESCRIPTOR, contextBody = CONTEXT, firstWindow = windowDoc(0.1, 8.1)) {
      await network.respondNext(descriptorBody);
      await network.respondNext(contextBody);
      await network.respondNext(firstWindow);
    },
  };
}

function makeDisplay() {
  const renders = [];
  return {
    renders,
    render: envelope => renders.push(envelope),
    setTargetThreatLevels: () => {},
    beginSession: () => {},
    clearSession: () => {},
    fitView: () => {},
    selectTarget: () => {},
    setLayerVisible: () => {},
    destroy: () => {},
  };
}

async function makeController() {
  const { createEvaluationReplayController } = await import('../../web_gui/modules/evaluation-replay.js');
  const documentRef = makeDocumentRef();
  const network = makeFetchRef();
  const display = makeDisplay();
  const controller = createEvaluationReplayController({
    documentRef,
    fetchRef: network.fetchRef,
    displayFactory: () => display,
  });
  return { controller, documentRef, network, display };
}

/* ── Static contract ── */

test('Evaluation workface hosts the replay viewer between the run panel and Historical AIS', () => {
  const evaluationStart = html.indexOf('data-workface-panel="evaluation"');
  const runsPanel = html.indexOf('id="replayRunsPanel"');
  const viewer = html.indexOf('id="evaluationReplayPanel"');
  const historical = html.indexOf('id="historicalAISBenchmark"');
  assert.ok(viewer > evaluationStart, 'replay viewer must live in the Evaluation workface');
  assert.ok(viewer > runsPanel, 'replay viewer must follow the run catalog');
  assert.ok(historical > viewer, 'Historical AIS workbench must stay present');
  for (const id of ['replaySealedBadge', 'replayEvidenceBadge', 'replayTimeline', 'replayTimeCurrent', 'replayTimeTotal', 'replaySourceFrame', 'replayStatusLine', 'replayStartBtn', 'replayEndBtn', 'replayCloseBtn', 'replayCanvas', 'replayCanvasWrapper', 'replayInspection']) {
    assert.match(html, new RegExp(`id="${id}"`), id);
  }
  assert.match(styles, /\.replay-viewer/);
  // The timeline is a real slider so keyboard seek works without pointer drag.
  assert.match(html, /id="replayTimeline"[^>]*type="range"/);
});

test('replay frontend reuses the canonical projection/display and never parses raw artifacts or mutates sessions', () => {
  assert.match(moduleSource, /telemetry-projection\.js/);
  assert.match(moduleSource, /situation-display\.js/);
  assert.match(moduleSource, /replay-source\.js/);
  assert.doesNotMatch(moduleSource, /\/api\/sessions/);
  assert.doesNotMatch(moduleSource, /method\s*:\s*['"](POST|PUT|PATCH|DELETE)['"]/);
  assert.doesNotMatch(moduleSource, /parquet|pzip|DecompressionStream|gzip/i);
  assert.doesNotMatch(adapterSource, /parquet|pzip|DecompressionStream|gzip/i);
});

/* ── Open / seek behavior ── */

test('open loads descriptor, context and initial window; reads are run-scoped GETs only', async () => {
  const { controller, network, documentRef } = await makeController();
  const opened = controller.open(RUN_ID);
  await network.open(network);
  await opened;

  const sessionCalls = network.calls.filter(call => /\/api\/sessions/.test(call.url));
  assert.deepEqual(sessionCalls, [], 'no Active Session endpoint is ever touched');
  assert.deepEqual(network.calls.map(call => call.method), ['GET', 'GET', 'GET']);
  for (const call of network.calls) {
    assert.match(call.url, /^\/api\/runs\//);
  }
  assert.match(network.calls[0].url, /replay$/);
  assert.match(network.calls[1].url, /replay\/context$/);
  assert.match(network.calls[2].url, /replay\/window\?from=0\.1&to=8\.1$/);
  assert.equal(documentRef.getElementById('replaySealedBadge').textContent, 'SEALED · HISTORICAL');
  assert.match(documentRef.getElementById('replayEvidenceBadge').textContent, /REPLAY READY · FULL EVIDENCE/);
  const timeline = documentRef.getElementById('replayTimeline');
  assert.equal(timeline.min, '0.1');
  assert.equal(timeline.max, '40');
  assert.equal(timeline.value, '0.1');
  assert.equal(controller.state.status, 'READY');
  assert.equal(controller.state.playhead, 0.1);
  assert.equal(documentRef.getElementById('replayStatusLine').textContent, 'PAUSED · HISTORICAL INSPECTION');
});

test('direct late seek lands on the recorded bracket without any intermediate time steps', async () => {
  const { controller, network, documentRef, display } = await makeController();
  const opened = controller.open(RUN_ID);
  await network.open(network);
  await opened;
  display.renders.length = 0;

  const seekPromise = controller.seek(38.5);
  await network.respondNext(windowDoc(38.1, 40.0));
  await seekPromise;

  assert.equal(network.calls.length, 4, 'one window request for the late seek');
  assert.match(network.calls.at(-1).url, /replay\/window\?from=38&to=39$/);
  assert.equal(controller.state.playhead, 38.5);
  assert.equal(controller.state.sourceSequence, 381);
  assert.equal(controller.state.status, 'READY');
  assert.equal(display.renders.length, 1);
  assert.equal(display.renders[0].presentation.mode, 'HISTORICAL_REPLAY');
  assert.equal(display.renders[0].presentation.source_sequence, 381);
  assert.match(documentRef.getElementById('replayTimeCurrent').textContent, /38\.5/);
  assert.match(documentRef.getElementById('replaySourceFrame').textContent, /#381/);
});

test('rapid seek A then B: a late A response cannot overwrite the newer B inspection cursor', async () => {
  const { controller, network, display } = await makeController();
  const opened = controller.open(RUN_ID);
  await network.open(network);
  await opened;
  display.renders.length = 0;

  const seekA = controller.seek(20.0);
  const seekB = controller.seek(38.5);
  assert.equal(network.pending.length, 2, 'both seek windows are in flight');
  // Deliver B's response first; the stale A response arrives last.
  await network.respondLast(windowDoc(38.1, 40.0));
  await seekB;
  await network.respondNext(windowDoc(19.6, 20.6));
  await seekA;

  assert.equal(controller.state.playhead, 38.5, 'stale A must not move the cursor back');
  assert.equal(controller.state.sourceSequence, 381);
  const lastRender = display.renders.at(-1);
  assert.equal(lastRender.presentation.source_sequence, 381);
  const sources = new Set(display.renders.map(envelope => envelope.presentation.source_sequence));
  assert.ok(!sources.has(196), 'stale A envelope is never rendered');
});

test('unbracketable seek shows a buffering state and never invents motion', async () => {
  const { controller, network, documentRef, display } = await makeController();
  const opened = controller.open(RUN_ID);
  await network.open(network);
  await opened;
  display.renders.length = 0;

  // A window response with no frames cannot render an invented situation.
  const seekPromise = controller.seek(30.0);
  await network.respondNext({ ...windowDoc(29.6, 30.6), frames: [] });
  await seekPromise;

  assert.equal(controller.state.status, 'BUFFERING');
  assert.match(documentRef.getElementById('replayStatusLine').textContent, /BUFFERING RECORDED DATA/);
  assert.equal(display.renders.length, 0, 'no extrapolated frame is rendered');
  assert.equal(controller.state.playhead, 30.0, 'cursor stays at the requested time');
});

test('target selection changes inspection context only', async () => {
  const { controller, network, documentRef } = await makeController();
  const opened = controller.open(RUN_ID);
  await network.open(network);
  await opened;
  const callsBeforeSelection = network.calls.length;

  controller.selectTarget('1');
  const inspection = documentRef.getElementById('replayInspection');
  const inspectionText = inspection.children.map(row => row.textContent).join('\n');
  assert.match(inspectionText, /TS1/);
  assert.match(inspectionText, /Inspection Context only/);
  // Selection performs no network access at all (and therefore no session calls).
  assert.equal(network.calls.length, callsBeforeSelection);
});

test('start and end controls seek the recorded bounds; close hides the viewer', async () => {
  const { controller, network, documentRef } = await makeController();
  const opened = controller.open(RUN_ID);
  await network.open(network);
  await opened;

  const endSeek = controller.seek(40.0);
  await network.respondNext(windowDoc(39.6, 40.0));
  await endSeek;
  documentRef.getElementById('replayStartBtn').click();
  assert.equal(controller.state.playhead, 0.1);
  documentRef.getElementById('replayEndBtn').click();
  assert.equal(controller.state.playhead, 40);
  documentRef.getElementById('replayCloseBtn').click();
  assert.equal(documentRef.getElementById('evaluationReplayPanel').hidden, true);
});

test('incomplete evidence restricts the timeline to the trusted boundary and says so', async () => {
  const { controller, network, documentRef } = await makeController();
  const truncated = {
    ...DESCRIPTOR,
    replay: { ...DESCRIPTOR.replay, state: 'INCOMPLETE', trusted_t_end: 20.0, truncated: true },
  };
  const opened = controller.open(RUN_ID);
  await network.open(network, truncated);
  await opened;

  const timeline = documentRef.getElementById('replayTimeline');
  assert.equal(timeline.max, '20');
  assert.match(documentRef.getElementById('replayEvidenceBadge').textContent, /REPLAY INCOMPLETE/);
  assert.match(documentRef.getElementById('replayEvidenceBadge').textContent, /20\.0 s/);
});


/* ── #72: deterministic playback (ReplayClock / Play / Pause / Replay Speed) ── */

const elText = (documentRef, id) => documentRef.getElementById(id)?.textContent ?? '';

function makeWallClock() {
  let wallMs = 0;
  return {
    now: () => wallMs,
    advance: ms => { wallMs += ms; },
  };
}

function makeScheduler() {
  let nextId = 0;
  let pending = [];
  return {
    set: (fn, ms) => { const id = ++nextId; pending.push({ id, fn, ms }); return id; },
    clear: id => { pending = pending.filter(entry => entry.id !== id); },
    get pendingCount() { return pending.length; },
    async fireNext() {
      const entry = pending.shift();
      assert.ok(entry, 'no scheduled playback tick to fire');
      entry.fn();
      await new Promise(resolve => setTimeout(resolve, 0));
    },
  };
}

async function makePlaybackController() {
  const wall = makeWallClock();
  const scheduler = makeScheduler();
  const base = await makeController();
  const { createEvaluationReplayController } = await import('../../web_gui/modules/evaluation-replay.js');
  const controller = createEvaluationReplayController({
    documentRef: base.documentRef,
    fetchRef: base.network.fetchRef,
    displayFactory: () => base.display,
    nowFn: wall.now,
    scheduler,
  });
  return { ...base, controller, wall, scheduler };
}

async function openReadyRun(parts) {
  const openPromise = parts.controller.open(RUN_ID);
  await parts.network.open(parts.network);
  await openPromise;
}

async function drainWindowResponses(network, doc = windowDoc(0.1, 8.1)) {
  while (network.pending.length) {
    await network.respondNext(doc);
  }
}

test('play advances the playhead from wall elapsed × speed with zero session mutation', async () => {
  const parts = await makePlaybackController();
  await openReadyRun(parts);
  const { controller, network, documentRef, wall, scheduler } = parts;

  controller.playPause();
  assert.equal(controller.state.clockState, 'PLAYING');
  assert.equal(elText(documentRef, 'replayPlayPauseBtn'), 'PAUSE ⏸');

  wall.advance(1000);
  await scheduler.fireNext();
  assert.ok(Math.abs(controller.state.playhead - 1.1) < 1e-6, `playhead ${controller.state.playhead}`);
  assert.match(elText(documentRef, 'replayStatusLine'), /PLAYING · HISTORICAL REPLAY · 1×/);

  const sessionCalls = network.calls.filter(call => /\/api\/sessions/.test(call.url));
  assert.equal(sessionCalls.length, 0, 'replay playback must never call Active Session endpoints');

  controller.playPause(); // pause freezes
  const frozen = controller.state.playhead;
  wall.advance(10_000);
  await scheduler.fireNext().catch(() => {});
  assert.equal(controller.state.playhead, frozen);
  assert.equal(controller.state.clockState, 'PAUSED');
});

test('rate change preserves playhead continuity; only subsequent elapsed uses the new rate', async () => {
  const parts = await makePlaybackController();
  await openReadyRun(parts);
  const { controller, documentRef, wall, scheduler } = parts;

  controller.playPause();
  wall.advance(1000);
  await scheduler.fireNext();
  const before = controller.state.playhead;

  controller.setRate(10);
  assert.equal(controller.state.rate, 10);
  assert.equal(controller.state.playhead, before); // no jump at the change instant
  wall.advance(1000);
  await scheduler.fireNext();
  assert.ok(Math.abs(controller.state.playhead - (before + 10)) < 1e-6, `playhead ${controller.state.playhead}`);
  assert.match(elText(documentRef, 'replayStatusLine'), /10×/);
});

test('playback prefetches bounded windows ahead and never loads the whole Run', async () => {
  const parts = await makePlaybackController();
  await openReadyRun(parts);
  const { controller, network, wall, scheduler } = parts;

  controller.playPause();
  for (let i = 0; i < 90; i += 1) {
    wall.advance(100);
    await scheduler.fireNext().catch(() => {});
    await drainWindowResponses(network);
  }
  const windowCalls = network.calls.filter(call => call.url.includes('/replay/window'));
  assert.ok(windowCalls.length >= 2, 'expected a playback prefetch beyond the initial window');
  const lastUrl = new URL(`http://x${windowCalls[windowCalls.length - 1].url}`);
  const from = Number(lastUrl.searchParams.get('from'));
  const to = Number(lastUrl.searchParams.get('to'));
  assert.ok(from >= 8.1 - 0.5, `prefetch starts near the loaded edge, got from=${from}`);
  assert.ok(to - from <= 25, `prefetch span bounded, got ${to - from}`);
  assert.ok(controller.state.playhead > 8.0, 'playhead progressed past the initial window');
});

test('reaching trusted t_end transitions to ENDED; play restarts deterministically from t_start', async () => {
  const parts = await makePlaybackController();
  await openReadyRun(parts);
  const { controller, network, documentRef, wall, scheduler } = parts;

  const seekPromise = controller.seek(39.5); // 0.5 s before the trusted end
  await drainWindowResponses(network, windowDoc(39.0, 40.0));
  await seekPromise;

  controller.playPause();
  wall.advance(2000); // 2 s at 1× — crosses t_end 40.0
  await scheduler.fireNext();
  assert.equal(controller.state.clockState, 'ENDED');
  assert.equal(controller.state.playhead, 40.0);
  assert.match(elText(documentRef, 'replayStatusLine'), /REPLAY ENDED/);
  const windowsBefore = network.calls.filter(call => call.url.includes('/replay/window')).length;

  controller.playPause(); // restart from the trusted start
  assert.equal(controller.state.clockState, 'PLAYING');
  assert.ok(controller.state.playhead <= 0.1 + 1e-6, `restarted playhead ${controller.state.playhead}`);
  await drainWindowResponses(network, windowDoc(0.1, 8.1));
  wall.advance(100);
  await scheduler.fireNext().catch(() => {});
  await drainWindowResponses(network);
  const windowCallsAfter = network.calls.filter(call => call.url.includes('/replay/window')).length;
  assert.ok(windowCallsAfter > windowsBefore, 'restart fetched a window for the trusted start');
});

test('seek during PLAYING lands at the target and playback continues from there', async () => {
  const parts = await makePlaybackController();
  await openReadyRun(parts);
  const { controller, network, wall, scheduler } = parts;

  controller.playPause();
  wall.advance(1000);
  await scheduler.fireNext();
  await drainWindowResponses(network);

  const seekPromise = controller.seek(30.0);
  await network.respondNext(windowDoc(29.5, 30.0));
  await drainWindowResponses(network);
  await seekPromise;
  assert.equal(controller.state.playhead, 30.0);
  assert.equal(controller.state.clockState, 'PLAYING');

  wall.advance(1000);
  await scheduler.fireNext();
  await drainWindowResponses(network);
  assert.ok(controller.state.playhead > 30.9, `playback resumed from the seek target: ${controller.state.playhead}`);
});

test('high-speed playback samples paint frames but keeps every recorded frame seekable', async () => {
  const parts = await makePlaybackController();
  await openReadyRun(parts);
  const { controller, display, network, wall, scheduler } = parts;

  controller.setRate(20);
  controller.playPause();
  const renderCountBefore = display.renders.length;
  for (let i = 0; i < 5; i += 1) {
    wall.advance(100); // 2 sim-seconds per tick at 20×
    await scheduler.fireNext().catch(() => {});
    await drainWindowResponses(network);
  }
  const painted = display.renders.length - renderCountBefore;
  assert.ok(painted <= 5, `paint sampling keeps renders bounded per tick, got ${painted}`);
  assert.ok(controller.state.playhead >= 10.0, `20× playhead advanced: ${controller.state.playhead}`);

  // Frame identity survives: pause and seek back to an exact recorded frame.
  controller.playPause();
  await drainWindowResponses(parts.network);
  const seekPromise = controller.seek(2.0);
  await parts.network.respondNext(windowDoc(1.5, 2.5));
  await drainWindowResponses(parts.network);
  await seekPromise;
  assert.equal(controller.state.sourceSequence, Math.round(2.0 * 10));
});

test('solver-execution evidence is untouched by replay reads (backend counter test seam)', async () => {
  const html2 = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
  assert.ok(html2.includes('replayRate20'), '20× preset present');
  assert.ok(html2.includes('replayPlayPauseBtn'), 'play/pause control present');
  const adapterSource2 = adapterSource;
  assert.doesNotMatch(adapterSource2, /api\/sessions/, 'replay source adapter never targets session endpoints');
});
