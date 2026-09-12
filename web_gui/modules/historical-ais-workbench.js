import { openReplayForRun } from './evaluation-replay.js';
import { createHistoricalAISApi } from './historical-ais-api.js?v=20260824-canonical-presentation';
import { createHistoricalAISController } from './historical-ais-controller.js?v=20260824-canonical-presentation';
import { renderHistoricalAISWorkbench } from './historical-ais-render.js?v=20260824-canonical-presentation';

export function mountHistoricalAISWorkbench({
  documentRef = globalThis.document,
  api = createHistoricalAISApi(),
} = {}) {
  if (!documentRef?.getElementById('historicalAISBenchmark')) return null;
  const controller = createHistoricalAISController({
    api,
    render: state => renderHistoricalAISWorkbench(documentRef, state),
  });

  documentRef.getElementById('historicalAISModeChoices')?.addEventListener('click', event => {
    const button = event.target.closest('[data-historical-mode]');
    if (button) controller.selectMode(button.dataset.historicalMode);
  });
  documentRef.getElementById('historicalAISRun')?.addEventListener('click', controller.runWorkflow);
  documentRef.getElementById('historicalAISDeploy')?.addEventListener('click', async () => {
    const created = await controller.deployInteractive();
    if (created?.session_id) {
      documentRef.querySelector('[data-workface="deployment"]')?.click();
    }
  });
  // #74 Open Replay: explicit INSPECTION action (never execution) — the
  // completed workflow Run opens in the shared Evaluation > Replay player.
  documentRef.getElementById('historicalAISOpenReplay')?.addEventListener('click', async () => {
    const runId = controller.state.workflow?.runId;
    const status = documentRef.getElementById('historicalAISOpenReplayStatus');
    if (!runId) return;
    let replayable = false;
    try {
      const response = await fetch(`/api/runs/${runId}/replay`, { method: 'GET' });
      if (response.ok) {
        const state = String((await response.json())?.replay?.state ?? '').toUpperCase();
        replayable = state === 'READY' || state === 'INCOMPLETE';
      }
    } catch {
      replayable = false;
    }
    if (replayable && openReplayForRun(runId)) {
      if (status) status.hidden = true;
      return;
    }
    if (status) {
      status.hidden = false;
      status.textContent = 'NO REPLAYABLE EVIDENCE FOR THIS RUN · SEE EVIDENCE VIEW';
    }
  });

  controller.publish();
  controller.load();
  return controller;
}

if (typeof document !== 'undefined') mountHistoricalAISWorkbench();
