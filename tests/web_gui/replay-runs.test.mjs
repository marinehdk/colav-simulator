import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const moduleSource = await readFile(new URL('../../web_gui/modules/replay-runs.js', import.meta.url), 'utf8');
const entrySource = await readFile(new URL('../../web_gui/vendor/openbridge/entry-source.mjs', import.meta.url), 'utf8');
const bundleSource = await readFile(new URL('../../web_gui/vendor/openbridge/openbridge-components.mjs', import.meta.url), 'utf8');

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
    this.style = { cssText: '' };
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
  for (const id of ['replayRunsTable', 'replayRunsStatus', 'replayRunsRefreshBtn', 'replayRunsPaginationSummary', 'replayRunsPageSize', 'replayRunsPrevBtn', 'replayRunsPageIndicator', 'replayRunsNextBtn']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /<div class="replay-runs-card config-obc-card"[^>]*id="replayRunsPanel"/);
  assert.match(html, /<header class="config-card-title replay-runs-title-bar">\s*<span class="step">01<\/span>[\s\S]*<strong>REPLAY<\/strong>/);
  assert.match(html, /<obc-icon-button id="replayRunsRefreshBtn"[^>]*aria-label="Refresh"[^>]*>\s*<obi-refresh-google>/);
  assert.match(html, /<obc-table[^>]*id="replayRunsTable"[^>]*rowdivider[^>]*narrowheader/);
  assert.match(moduleSource, /key: 'replayEvidence', label: 'Replay Status'/);
  assert.match(moduleSource, /key: 'action', label: 'Action'/);
  assert.match(moduleSource, /\['Open', 'open'\], \['Delete', 'delete'\]/);
  assert.match(entrySource, /components\/table\/table\.js/);
  assert.match(entrySource, /icons\/icon-refresh-google\.js/);
  assert.match(html, /id="replayRunsPageSize"[^>]*>[\s\S]*value="10"[\s\S]*value="20"[\s\S]*value="50"/);
  assert.match(moduleSource, /PAGE_SIZES = \[10, 20, 50\]/);
  assert.match(styles, /--menu-navigation-components-table-item-touch-target-size: 56px/);
  assert.match(styles, /--menu-navigation-components-table-header-item-label-align: center/);
  assert.match(bundleSource, /text-align: var\(--menu-navigation-components-table-header-item-label-align, left\)/);
  assert.doesNotMatch(html, /<table class="replay-runs-table">/);
  assert.match(styles, /\.replay-runs-header \{[^}]*align-items: center;/);
  assert.match(styles, /\.replay-runs-card/);
  assert.match(styles, /\.replay-runs-pagination/);
});

test('run rows carry only backend facts and reject malformed payloads', () => {
  const rows = projectReplayRunRows([sampleEntry, null, { nope: true }, { ...sampleEntry, run_id: undefined }]);
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0], {
    runId: '11111111-1111-4111-8111-111111111111',
    scenario: 'head_on',
    algorithm: 'mid_mpc_ipopt',
    tracker: 'god',
    createdAt: '2026-09-11 10:00:00',
    executionState: 'FINISHED',
    replayState: 'READY',
    label: 'COMPLETE',
    frameCount: 601,
    tStart: 0,
    tEnd: 60,
  });
  assert.equal(projectReplayRunRows([{ ...sampleEntry, run_id: '22222222-2222-4222-8222-222222222222', replay: { ...sampleEntry.replay, frame_count: 0 } }]).length, 0);
  assert.deepEqual(projectReplayRunRows(undefined), []);
  assert.deepEqual(projectReplayRunRows('nope'), []);
});

test('evidence labels stay truthful for degraded states without inventing detail', () => {
  assert.equal(replayStateLabel({ replay: { state: 'READY' } }), 'COMPLETE');
  assert.equal(replayStateLabel({ replay: { state: 'CAPTURING' } }), 'INCOMPLETE');
  assert.equal(replayStateLabel({ replay: { state: 'REDUCED' } }), 'INCOMPLETE');
  assert.equal(replayStateLabel({ replay: { state: 'INCOMPLETE', reason: 'TRACE_GAP' } }), 'INCOMPLETE');
  assert.equal(replayStateLabel({ replay: { state: 'UNAVAILABLE', reason: 'TRACE_CAPTURE_DISABLED' } }), 'INCOMPLETE');
  assert.equal(replayStateLabel(undefined), 'INCOMPLETE');
});

test('render writes OpenBridge table rows with textual state and action cells', () => {
  const documentRef = makeDocumentRef();
  const rows = projectReplayRunRows([sampleEntry]);
  renderReplayRuns(documentRef, rows);

  const table = documentRef.getElementById('replayRunsTable');
  assert.equal(table.data.length, 1);
  assert.equal(table.columns.length, 9);
  const row = table.data[0];
  const text = Object.values(row).map(value => typeof value === 'object' ? value.text ?? value.type : value).join('|');
  assert.match(text, /head_on/);
  assert.match(text, /mid_mpc_ipopt/);
  assert.match(text, /601/);
  assert.match(text, /COMPLETE/);
  assert.equal(row.action.type, 'regular');

  const status = documentRef.getElementById('replayRunsStatus');
  assert.equal(status.textContent, '1 RUNS');
});

test('run rows offer an Open replay inspection action wired to the registered opener', () => {
  const documentRef = makeDocumentRef();
  const opened = [];
  renderReplayRuns(documentRef, projectReplayRunRows([sampleEntry]));
  const table = documentRef.getElementById('replayRunsTable');
  const actionColumn = table.columns.find(column => column.key === 'action');
  const actionCell = actionColumn.renderCell(table.data[0].action, table.data[0], sampleEntry.run_id);
  assert.equal(actionCell.children.length, 2);
  assert.equal(actionCell.children.map(button => button.textContent).join('|'), 'Open|Delete');

  setReplayRunOpener(runId => opened.push(runId));
  actionCell.children[0].listeners.click({ preventDefault() {}, stopPropagation() {} });
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
  assert.equal(documentRef.getElementById('replayRunsTable').data.length, 1);
  assert.equal(documentRef.getElementById('replayRunsStatus').textContent, '1 RUNS');

  await client.refresh();
  assert.equal(documentRef.getElementById('replayRunsStatus').textContent, 'UNAVAILABLE');
  assert.equal(documentRef.getElementById('replayRunsTable').data.length, 0);
  assert.deepEqual(requests.map(request => request.method), ['GET', 'GET']);
});

test('replay pagination renders 10 rows by default and supports 20 and 50 row pages', async () => {
  const documentRef = makeDocumentRef();
  const entries = Array.from({ length: 25 }, (_, index) => ({
    ...sampleEntry,
    run_id: `${String(index + 1).padStart(8, '0')}-1111-4111-8111-111111111111`,
  }));
  const fetchRef = async () => ({ ok: true, status: 200, json: async () => entries });
  const client = createReplayRunsClient({ documentRef, fetchRef });
  await client.refresh();

  const table = documentRef.getElementById('replayRunsTable');
  const summary = documentRef.getElementById('replayRunsPaginationSummary');
  const pageSize = documentRef.getElementById('replayRunsPageSize');
  const previous = documentRef.getElementById('replayRunsPrevBtn');
  const indicator = documentRef.getElementById('replayRunsPageIndicator');
  const next = documentRef.getElementById('replayRunsNextBtn');
  assert.equal(table.data.length, 10);
  assert.equal(summary.textContent, '1–10 of 25');
  assert.equal(indicator.textContent, '1 / 3');
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, false);

  pageSize.value = '20';
  pageSize.listeners.change({ target: pageSize });
  assert.equal(table.data.length, 20);
  assert.equal(summary.textContent, '1–20 of 25');
  assert.equal(indicator.textContent, '1 / 2');

  next.listeners.click();
  assert.equal(table.data.length, 5);
  assert.equal(summary.textContent, '21–25 of 25');
  assert.equal(indicator.textContent, '2 / 2');
  assert.equal(next.disabled, true);
  assert.equal(previous.disabled, false);

  pageSize.value = '50';
  pageSize.listeners.change({ target: pageSize });
  assert.equal(table.data.length, 25);
  assert.equal(summary.textContent, '1–25 of 25');
  assert.equal(indicator.textContent, '1 / 1');
  assert.equal(previous.disabled, true);
  assert.equal(next.disabled, true);
});
