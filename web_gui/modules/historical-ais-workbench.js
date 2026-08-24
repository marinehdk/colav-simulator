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

  documentRef.getElementById('historicalAISScenarioList')?.addEventListener('click', event => {
    const button = event.target.closest('[data-historical-scenario-id]');
    if (button) controller.selectScenario(button.dataset.historicalScenarioId);
  });
  documentRef.getElementById('historicalAISModeChoices')?.addEventListener('click', event => {
    const button = event.target.closest('[data-historical-mode]');
    if (button) controller.selectMode(button.dataset.historicalMode);
  });
  documentRef.getElementById('historicalAISRun')?.addEventListener('click', controller.runWorkflow);

  controller.publish();
  controller.load();
  return controller;
}

if (typeof document !== 'undefined') mountHistoricalAISWorkbench();
