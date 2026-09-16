/**
 * Evaluation > Replay run catalog (ticket #70).
 *
 * Minimal historical-inspection state panel: lists recorded Runs with their
 * backend-owned replay evidence state. No chart rendering, no seek/play —
 * those arrive with the replay timeline tickets. This module is read-only:
 * it only issues GET requests against /api/runs and never touches the
 * Active Session.
 */

const REPLAY_STATE_LABELS = {
  READY: 'COMPLETE',
  CAPTURING: 'INCOMPLETE',
  REDUCED: 'INCOMPLETE',
  INCOMPLETE: 'INCOMPLETE',
  UNAVAILABLE: 'INCOMPLETE',
};

// Set by the Evaluation replay host (evaluation-replay.js): row actions open
// the recorded Run for inspection. Inspection navigation only — never an
// execution action, never an Active Session call.
let replayRunOpener = null;
let lastRenderedCatalog = null;
const PAGE_SIZES = [10, 20, 50];
const paginationStates = new WeakMap();
const paginationBindings = new WeakSet();

function paginationStateFor(documentRef) {
  let state = paginationStates.get(documentRef);
  if (!state) {
    state = { rows: [], page: 1, pageSize: PAGE_SIZES[0] };
    paginationStates.set(documentRef, state);
  }
  return state;
}

function pageCountFor(rows, pageSize) {
  return Math.max(1, Math.ceil(rows.length / pageSize));
}

function renderPagination(documentRef, state) {
  const total = state.rows.length;
  const pageCount = pageCountFor(state.rows, state.pageSize);
  state.page = Math.max(1, Math.min(state.page, pageCount));
  const start = total === 0 ? 0 : (state.page - 1) * state.pageSize + 1;
  const end = total === 0 ? 0 : Math.min(state.page * state.pageSize, total);
  const summary = documentRef.getElementById('replayRunsPaginationSummary');
  if (summary) summary.textContent = `${start}–${end} of ${total}`;
  const indicator = documentRef.getElementById('replayRunsPageIndicator');
  if (indicator) indicator.textContent = `${state.page} / ${pageCount}`;
  const pageSize = documentRef.getElementById('replayRunsPageSize');
  if (pageSize) pageSize.value = String(state.pageSize);
  const previous = documentRef.getElementById('replayRunsPrevBtn');
  if (previous) previous.disabled = state.page <= 1;
  const next = documentRef.getElementById('replayRunsNextBtn');
  if (next) next.disabled = state.page >= pageCount;
}

function bindPaginationControls(documentRef) {
  if (paginationBindings.has(documentRef)) return;
  paginationBindings.add(documentRef);
  const state = paginationStateFor(documentRef);
  documentRef.getElementById('replayRunsPageSize')?.addEventListener('change', event => {
    const candidate = Number(event?.target?.value);
    if (!PAGE_SIZES.includes(candidate)) return;
    state.pageSize = candidate;
    state.page = 1;
    renderReplayRuns(documentRef, state.rows);
  });
  documentRef.getElementById('replayRunsPrevBtn')?.addEventListener('click', () => {
    if (state.page <= 1) return;
    state.page -= 1;
    renderReplayRuns(documentRef, state.rows);
  });
  documentRef.getElementById('replayRunsNextBtn')?.addEventListener('click', () => {
    const pageCount = pageCountFor(state.rows, state.pageSize);
    if (state.page >= pageCount) return;
    state.page += 1;
    renderReplayRuns(documentRef, state.rows);
  });
}

export function setReplayRunOpener(opener) {
  replayRunOpener = typeof opener === 'function' ? opener : null;
  // replay-runs.js boots before evaluation-replay.js in the product shell.
  // Re-render the last catalog when the shared opener registers so an initial
  // refresh cannot permanently lose the Open replay action.
  if (lastRenderedCatalog) {
    renderReplayRuns(lastRenderedCatalog.documentRef, lastRenderedCatalog.rows);
  }
}

export function replayStateLabel(entry) {
  const replay = entry?.replay ?? {};
  const state = String(replay.state ?? 'UNAVAILABLE').toUpperCase();
  return REPLAY_STATE_LABELS[state] ?? 'INCOMPLETE';
}

export function projectReplayRunRows(entries) {
  if (!Array.isArray(entries)) return [];
  return entries
    .filter(entry => entry && typeof entry === 'object' && typeof entry.run_id === 'string' && entry.run_id)
    .map(entry => {
      const replay = entry.replay ?? {};
      const frameCount = Number(replay.frame_count);
      return {
        runId: entry.run_id,
        scenario: entry.scenario_id ?? '—',
        algorithm: entry.executed_algorithm ?? '—',
        tracker: entry.executed_tracker ?? '—',
        createdAt: formatCreatedAt(entry.created_at_utc),
        executionState: entry.execution_state ?? '—',
        replayState: String(replay.state ?? 'UNAVAILABLE').toUpperCase(),
        label: replayStateLabel(entry),
        frameCount: Number.isFinite(frameCount) ? frameCount : null,
        tStart: replay.t_start ?? null,
        tEnd: replay.t_end ?? null,
      };
    })
    .filter(row => row.frameCount !== null && row.frameCount > 0);
}

function formatCreatedAt(value) {
  const match = String(value ?? '').match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  return match ? `${match[1]} ${match[2]}` : '—';
}

function regularCell(text, { noWrap = true, align = 'center' } = {}) {
  return { type: 'regular', text: String(text ?? '—'), noWrap, align };
}

function projectTableRows(rows) {
  return rows.map(row => ({
    id: row.runId,
    run: regularCell(row.runId.slice(0, 8)),
    scenario: regularCell(row.scenario),
    algorithm: regularCell(row.algorithm),
    tracker: regularCell(row.tracker),
    frames: regularCell(row.frameCount === null ? '—' : row.frameCount),
    simTime: regularCell(
      row.tEnd === null ? '—' : Number(row.tEnd).toFixed(1),
    ),
    replayEvidence: regularCell(row.label),
    created: regularCell(row.createdAt),
    action: { type: 'regular', text: '' },
  }));
}

function createReplayActionCell(documentRef, rowId) {
  const container = documentRef.createElement('div');
  container.style.cssText = 'display:flex;align-items:center;justify-content:center;gap:8px;width:100%;';
  for (const [label, action] of [['Open', 'open'], ['Delete', 'delete']]) {
    const button = documentRef.createElement('obc-button');
    button.setAttribute('variant', 'normal');
    button.setAttribute('fullwidth', '');
    button.setAttribute('aria-label', `${label} replay ${rowId.slice(0, 8)}`);
    button.style.cssText = 'flex:1 1 0;min-width:0;width:100%;';
    button.textContent = label;
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      if (action === 'open' && replayRunOpener !== null) replayRunOpener(rowId);
    });
    container.append(button);
  }
  return container;
}

function createReplayTableColumns(documentRef) {
  return [
    { key: 'run', label: 'Run' },
    { key: 'scenario', label: 'Scenario' },
    { key: 'algorithm', label: 'Algorithm' },
    { key: 'tracker', label: 'Tracker' },
    { key: 'frames', label: 'Frames' },
    { key: 'simTime', label: 'Sim time (s)' },
    { key: 'replayEvidence', label: 'Replay Status' },
    { key: 'created', label: 'Created' },
    { key: 'action', label: 'Action', headerType: 'Narrow', renderCell: (_value, _row, rowId) => createReplayActionCell(documentRef, rowId) },
  ];
}

export function renderReplayRuns(documentRef, rows) {
  const table = documentRef.getElementById('replayRunsTable');
  if (!table) return;
  bindPaginationControls(documentRef);
  const state = paginationStateFor(documentRef);
  if (state.rows !== rows) {
    state.rows = rows;
    state.page = 1;
  }
  const pageCount = pageCountFor(rows, state.pageSize);
  state.page = Math.max(1, Math.min(state.page, pageCount));
  const pageStart = (state.page - 1) * state.pageSize;
  lastRenderedCatalog = { documentRef, rows };
  table.columns = createReplayTableColumns(documentRef);
  table.data = projectTableRows(rows.slice(pageStart, pageStart + state.pageSize));
  table.rowDivider = true;
  table.narrowHeader = true;
  table.showHeader = true;
  const status = documentRef.getElementById('replayRunsStatus');
  if (status) status.textContent = `${rows.length} RUNS`;
  renderPagination(documentRef, state);
}

export function createReplayRunsClient({ documentRef = globalThis.document, fetchRef = globalThis.fetch } = {}) {
  async function refresh() {
    const status = documentRef.getElementById('replayRunsStatus');
    try {
      const response = await fetchRef('/api/runs?limit=50');
      if (!response.ok) throw new Error(`status ${response.status}`);
      const entries = await response.json();
      renderReplayRuns(documentRef, projectReplayRunRows(entries));
    } catch {
      renderReplayRuns(documentRef, []);
      if (status) status.textContent = 'UNAVAILABLE';
    }
  }

  bindPaginationControls(documentRef);
  documentRef.getElementById('replayRunsRefreshBtn')?.addEventListener('click', refresh);
  return { refresh };
}

if (typeof document !== 'undefined') {
  const panel = document.getElementById('replayRunsPanel');
  if (panel) {
    const client = createReplayRunsClient();
    client.refresh();
  }
}
