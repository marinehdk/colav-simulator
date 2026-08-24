import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  DEFAULT_HISTORICAL_AIS_SCENARIO,
  createHistoricalAISApi,
  createHistoricalAISProjection,
} from '../../web_gui/modules/historical-ais-workbench.js';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');

test('Historical AIS is an additive Scenario and Evaluation workface surface', () => {
  assert.match(html, /id="historicalAISScenarioList"/);
  assert.match(html, /id="historicalAISScenarioDetail"/);
  assert.match(html, /id="historicalAISBenchmark"/);
  assert.match(html, /id="historicalAISModeChoices"/);
  assert.match(html, /id="historicalAISRun"/);
  assert.match(html, /historical-ais-workbench\.js/);

  // Existing COLREG assembly remains the only owner of rule-scoped cards.
  assert.match(html, /id="validationScenarioChoices"/);
  assert.match(html, /data-config-step-panel="scenarios"/);
  assert.match(styles, /\.historical-ais-workbench/);
});

test('browse projection labels the bounded one-minute window and archive limitation', () => {
  const projection = createHistoricalAISProjection(DEFAULT_HISTORICAL_AIS_SCENARIO);

  assert.equal(projection.scenarioId, 'hais_romsdal_20260701_120000_120100');
  assert.equal(projection.selection.durationLabel, '1 min');
  assert.equal(projection.selection.runtimeActorCount, 3);
  assert.equal(projection.source.archiveDays, 23);
  assert.equal(projection.source.archiveRows, 51_522_509);
  assert.equal(projection.source.archiveMmsi, 1_226);
  assert.doesNotMatch(JSON.stringify(DEFAULT_HISTORICAL_AIS_SCENARIO), /Downloads|\/Users\//);
  assert.equal(projection.source.bound, false);
  assert.equal(projection.run.available, false);
  assert.match(projection.limitation, /当前仅验证该窗口\/3船/);
  assert.match(projection.limitation, /全archive未完成ENC资格/);
});

test('completed counterfactual projection exposes typed evidence without calculating risk in the browser', () => {
  const projection = createHistoricalAISProjection(DEFAULT_HISTORICAL_AIS_SCENARIO, {
    workflow_id: 'workflow-1',
    mode: 'COUNTERFACTUAL',
    status: 'COMPLETED',
    stages: {
      dataset: 'SELECTED',
      case: 'PUBLISHED',
      replay: 'NOT_APPLICABLE',
      counterfactual: 'COMPLETED',
      evaluation: 'COMPLETE',
      compare: 'COMPLETE',
    },
    leakage: { status: 'PASS_CONTRACT' },
    evidence: {
      run: { fallback_used: false },
      threat_snapshot: {
        vectors: [{}, {}],
        schedule: { context: [{}, {}] },
        conflicts: { clusters: [{}] },
      },
      evaluation: { evaluation_status: 'COMPLETE', gate: 'PASS' },
    },
    compare: {
      status: 'COMPLETE',
      overall_assurance_verdict: 'PASS',
      domain_statuses: {
        safety: 'COMPLETE',
        colreg: 'COMPLETE',
        maneuver: 'COMPLETE',
        efficiency: 'COMPLETE',
        human_similarity: 'COMPLETE',
      },
    },
  });

  assert.equal(projection.workflowId, 'workflow-1');
  assert.equal(projection.evidence.mode, 'COUNTERFACTUAL');
  assert.equal(projection.evidence.fallback, false);
  assert.deepEqual(projection.evidence.threat, { vectors: 2, schedule: 2, clusters: 1 });
  assert.equal(projection.evidence.leakage, 'PASS_CONTRACT');
  assert.deepEqual(projection.evidence.determinism, []);
  assert.deepEqual(projection.evidence.compareDomains, {
    safety: 'COMPLETE',
    colreg: 'COMPLETE',
    maneuver: 'COMPLETE',
    efficiency: 'COMPLETE',
    human_similarity: 'COMPLETE',
  });
  assert.equal(projection.evidence.verdict, 'PASS');
});

test('Historical AIS API adapter uses the dedicated scenario/workflow contract', async () => {
  const requests = [];
  const fetchImpl = async (url, options = {}) => {
    requests.push({ url, options });
    return {
      ok: true,
      status: 200,
      async json() {
        if (url === '/api/historical/scenarios') return [DEFAULT_HISTORICAL_AIS_SCENARIO];
        if (url.includes('/workflows') && options.method === 'POST' && url.endsWith('/run')) {
          return { workflow_id: 'workflow-1', status: 'COMPLETED' };
        }
        if (url.includes('/workflows') && options.method === 'POST') {
          return { workflow_id: 'workflow-1', status: 'PREPARED' };
        }
        return DEFAULT_HISTORICAL_AIS_SCENARIO;
      },
    };
  };
  const api = createHistoricalAISApi({ fetchImpl, WebSocketImpl: null });

  assert.deepEqual(await api.listScenarios(), [DEFAULT_HISTORICAL_AIS_SCENARIO]);
  await api.getScenario(DEFAULT_HISTORICAL_AIS_SCENARIO.id);
  await api.createWorkflow(DEFAULT_HISTORICAL_AIS_SCENARIO.id, 'COUNTERFACTUAL');
  await api.runWorkflow('workflow-1');

  assert.deepEqual(requests.map(request => request.url), [
    '/api/historical/scenarios',
    `/api/historical/scenarios/${DEFAULT_HISTORICAL_AIS_SCENARIO.id}`,
    `/api/historical/scenarios/${DEFAULT_HISTORICAL_AIS_SCENARIO.id}/workflows`,
    '/api/historical/workflows/workflow-1/run',
  ]);
  assert.equal(JSON.parse(requests[2].options.body).mode, 'COUNTERFACTUAL');
  assert.ok(requests.every(request => !request.url.startsWith('/api/scenarios')));
});

test('scenario projection accepts the published catalog descriptor shape', () => {
  const projection = createHistoricalAISProjection({
    id: 'hais_romsdal_20260701_120000_120100',
    display_name: 'Romsdal AIS 2026-07-01 12:00-12:01 UTC',
    kind: 'HISTORICAL_AIS',
    modes: ['HISTORICAL_REPLAY', 'COUNTERFACTUAL'],
    archive_scope: { source_name: 'HAIS.zip', day_count: 23, row_count: 51_522_509, union_mmsi_count: 1_226 },
    current_window: {
      entry_name: 'hais_2026-07-01.snappy.parquet',
      start_utc: '2026-07-01T12:00:00+00:00',
      end_utc: '2026-07-01T12:01:00+00:00',
      t0_utc: '2026-07-01T12:00:30+00:00',
      bbox: [6.05, 62.44, 6.17, 62.5],
      selection_mmsi: [257252000, 258764000, 259189000, 259197000],
      runtime_mmsi: [257252000, 258764000, 259189000],
      source_row_count: 24,
      normalized_row_count: 24,
      quality_finding_count: 98,
      reference_mmsi: 259189000,
    },
    enc: { profile_id: 'romsdal-expanded', qualification_state: 'QUALIFIED' },
    readiness: { status: 'SOURCE_BINDING_MISSING' },
  });

  assert.equal(projection.source.archiveRows, 51_522_509);
  assert.equal(projection.selection.filterMmsi.length, 4);
  assert.deepEqual(projection.selection.selectedMmsi, [257252000, 258764000, 259189000]);
  assert.equal(projection.selection.referenceMmsi, 259189000);
  assert.deepEqual(projection.modes.map(mode => mode.id), ['HISTORICAL_REPLAY', 'COUNTERFACTUAL']);
  assert.equal(projection.run.available, false);
});
