import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const moduleSource = await readFile(new URL('../../web_gui/modules/replay-runs.js', import.meta.url), 'utf8');

const { createReplayRunsClient, projectReplayRunRows, replayStateLabel, renderReplayRuns, setReplayRunOpener } = await import(
  '../../web_gui/modules/replay-runs.js'
);

const evaluationStart = html.indexOf('data-workface-panel="evaluation"');
const replayPanel = html.indexOf('id="replayRunsPanel"');
const historicalPanel = html.indexOf('id="historicalAISBenchmark"');

const sampleEntry = {
  run_id: '11111111-1111-4111-8111-111111111111',
  created_at_utc: '2026-09-11T10:00:00Z',
  scenario_id: 'head_on',
  executed_algorithm: 'mid_mpc_ipopt',
  executed_tracker: 'god',
  execution_state: 'FINISHED',
  replay: { state: 'READY', evidence_level: 'full', reason: null, frame_count: 601, t_start: 0.0, t_end: 60.0 },
};

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
    this.listeners = {};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
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

test('Evaluation workface hosts a Replay run panel before the Historical AIS workbench', () => {
  assert.ok(evaluationStart >= 0);
  assert.ok(replayPanel > evaluationStart, 'Replay panel must live in the Evaluation workface');
  assert.ok(historicalPanel > replayPanel, 'Historical AIS workbench must stay present after the Replay panel');
  for (const id of ['replayRunsBody', 'replayRunsStatus', 'replayRunsRefreshBtn']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(styles, /\.replay-runs-card/);
});

test('run rows carry only backend facts and reject malformed payloads', () => {
  const rows = projectReplayRunRows([sampleEntry, null, { nope: true }, { ...sampleEntry, run_id: undefined }]);
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0], {
    runId: '11111111-1111-4111-8111-111111111111',
    scenario: 'head_on',
    algorithm: 'mid_mpc_ipopt',
    tracker: 'god',
    createdAt: '2026-09-11T10:00:00Z',
    executionState: 'FINISHED',
    replayState: 'READY',
    label: 'REPLAY READY · FULL EVIDENCE',
    frameCount: 601,
    tStart: 0,
    tEnd: 60,
  });
  assert.deepEqual(projectReplayRunRows(undefined), []);
  assert.deepEqual(projectReplayRunRows('nope'), []);
});

test('evidence labels stay truthful for degraded states without inventing detail', () => {
  assert.equal(replayStateLabel({ replay: { state: 'CAPTURING' } }), 'CAPTURING');
  assert.equal(replayStateLabel({ replay: { state: 'REDUCED' } }), 'REDUCED EVIDENCE');
  assert.equal(
    replayStateLabel({ replay: { state: 'INCOMPLETE', reason: 'TRACE_GAP' } }),
    'INCOMPLETE EVIDENCE · TRACE_GAP',
  );
  assert.equal(replayStateLabel({ replay: { state: 'UNAVAILABLE', reason: 'TRACE_CAPTURE_DISABLED' } }), 'UNAVAILABLE · TRACE_CAPTURE_DISABLED');
  assert.equal(replayStateLabel(undefined), 'UNAVAILABLE');
});

test('render writes textual state pills (non-color-only readiness) and facts into the table', () => {
  const documentRef = makeDocumentRef();
  const rows = projectReplayRunRows([sampleEntry]);
  renderReplayRuns(documentRef, rows);

  const body = documentRef.getElementById('replayRunsBody');
  assert.equal(body.children.length, 1);
  const row = body.children[0];
  const text = row.children.map(cell => cell.textContent).join('|');
  assert.match(text, /head_on/);
  assert.match(text, /mid_mpc_ipopt/);
  assert.match(text, /601/);
  assert.match(text, /REPLAY READY · FULL EVIDENCE/);

  const status = documentRef.getElementById('replayRunsStatus');
  assert.equal(status.textContent, '1 RUNS');
});

test('run rows offer an Open replay inspection action wired to the registered opener', () => {
  const documentRef = makeDocumentRef();
  const opened = [];
  renderReplayRuns(documentRef, projectReplayRunRows([sampleEntry]));
  assert.equal(documentRef.getElementById('replayRunsBody').children[0].children.length, 8, 'no action cell until a replay host registers');

  setReplayRunOpener(runId => opened.push(runId));
  renderReplayRuns(documentRef, projectReplayRunRows([sampleEntry]));
  const action = documentRef.getElementById('replayRunsBody').children[0].children.at(-1);
  assert.equal(action.textContent, 'Open replay');
  action.listeners.click({ stopPropagation() {} });
  assert.deepEqual(opened, ['11111111-1111-4111-8111-111111111111']);
  setReplayRunOpener(null);
});

test('replay client reads the backend catalog with GET only and never touches session endpoints', () => {
  assert.doesNotMatch(moduleSource, /method\s*:\s*['"](POST|PUT|PATCH|DELETE)['"]/);
  assert.doesNotMatch(moduleSource, /\/api\/sessions/);
  assert.match(moduleSource, /\/api\/runs/);
});

test('client refresh projects the catalog into the panel and reports failures truthfully', async () => {
  const documentRef = makeDocumentRef();
  const requests = [];
  const fetchRef = async (url, options = {}) => {
    requests.push({ url, method: options.method ?? 'GET' });
    if (requests.length === 1) {
      return { ok: true, status: 200, json: async () => [sampleEntry] };
    }
    return { ok: false, status: 503, json: async () => ({}) };
  };

  const client = createReplayRunsClient({ documentRef, fetchRef });
  await client.refresh();
  assert.equal(documentRef.getElementById('replayRunsBody').children.length, 1);
  assert.equal(documentRef.getElementById('replayRunsStatus').textContent, '1 RUNS');

  await client.refresh();
  assert.equal(documentRef.getElementById('replayRunsStatus').textContent, 'UNAVAILABLE');
  assert.deepEqual(requests.map(request => request.method), ['GET', 'GET']);
});
