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
  READY: 'REPLAY READY · FULL EVIDENCE',
  CAPTURING: 'CAPTURING',
  REDUCED: 'REDUCED EVIDENCE',
  INCOMPLETE: 'INCOMPLETE EVIDENCE',
  UNAVAILABLE: 'UNAVAILABLE',
};

// Set by the Evaluation replay host (evaluation-replay.js): row actions open
// the recorded Run for inspection. Inspection navigation only — never an
// execution action, never an Active Session call.
let replayRunOpener = null;

export function setReplayRunOpener(opener) {
  replayRunOpener = typeof opener === 'function' ? opener : null;
}

export function replayStateLabel(entry) {
  const replay = entry?.replay ?? {};
  const state = String(replay.state ?? 'UNAVAILABLE').toUpperCase();
  const base = REPLAY_STATE_LABELS[state] ?? state;
  return replay.reason ? `${base} · ${String(replay.reason)}` : base;
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
        createdAt: entry.created_at_utc ?? '—',
        executionState: entry.execution_state ?? '—',
        replayState: String(replay.state ?? 'UNAVAILABLE').toUpperCase(),
        label: replayStateLabel(entry),
        frameCount: Number.isFinite(frameCount) ? frameCount : null,
        tStart: replay.t_start ?? null,
        tEnd: replay.t_end ?? null,
      };
    });
}

function cell(documentRef, text, className = '') {
  const element = documentRef.createElement('td');
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

export function renderReplayRuns(documentRef, rows) {
  const body = documentRef.getElementById('replayRunsBody');
  if (!body) return;
  const tableRows = rows.map(row => {
    const tr = documentRef.createElement('tr');
    tr.setAttribute('data-replay-state', row.replayState);
    tr.append(
      cell(documentRef, row.runId.slice(0, 8)),
      cell(documentRef, row.scenario),
      cell(documentRef, row.algorithm),
      cell(documentRef, row.tracker),
      cell(documentRef, row.frameCount === null ? '—' : String(row.frameCount)),
      cell(
        documentRef,
        row.tStart === null || row.tEnd === null ? '—' : `${Number(row.tStart).toFixed(1)} – ${Number(row.tEnd).toFixed(1)}`,
      ),
      cell(documentRef, row.label, 'replay-runs-state'),
      cell(documentRef, row.createdAt),
    );
    if (replayRunOpener !== null) {
      const action = documentRef.createElement('button');
      action.type = 'button';
      action.className = 'ob-button ob-button--flat replay-runs-open';
      action.textContent = 'Open replay';
      action.setAttribute('aria-label', `Open replay for run ${row.runId.slice(0, 8)}`);
      action.addEventListener('click', event => {
        event.stopPropagation();
        replayRunOpener(row.runId);
      });
      tr.append(action);
    }
    return tr;
  });
  body.replaceChildren(...tableRows);
  const status = documentRef.getElementById('replayRunsStatus');
  if (status) status.textContent = `${rows.length} RUNS`;
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
      if (status) status.textContent = 'UNAVAILABLE';
      const body = documentRef.getElementById('replayRunsBody');
      if (body) body.replaceChildren();
    }
  }

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
