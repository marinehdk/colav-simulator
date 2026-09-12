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
