import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { createHistoricalAISApi } from '../../web_gui/modules/historical-ais-api.js';
import {
  projectHistoricalAISScenario,
  projectHistoricalAISWorkflow,
} from '../../web_gui/modules/historical-ais-projection.js';
import { renderHistoricalAISWorkbench } from '../../web_gui/modules/historical-ais-render.js';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const runtimeShape = JSON.parse(await readFile(
  new URL('./fixtures/historical-workflow-runtime-shape.json', import.meta.url),
  'utf8',
));
const descriptor = JSON.parse(await readFile(
  new URL('../../colav_simulator/data/historical_ais_scenarios.json', import.meta.url),
  'utf8',
));
const clientSources = await Promise.all([
  'historical-ais-api.js',
  'historical-ais-controller.js',
  'historical-ais-projection.js',
  'historical-ais-render.js',
  'historical-ais-workbench.js',
].map(name => readFile(new URL(`../../web_gui/modules/${name}`, import.meta.url), 'utf8')));

test('Historical AIS benchmark DOM stays additive with no fabricated scene facts', () => {
  assert.match(html, /id="historicalAISBenchmark"/);
  assert.match(html, /id="historicalAISModeChoices"[^>]*><\/div>/);
  assert.match(html, /id="historicalAISRun"[^>]*disabled/);
  assert.match(html, /id="historicalAISDeploy"[^>]*disabled/);
  assert.match(styles, /\.historical-ais-workbench/);

  // C4: the standalone Scenario/Algorithm workfaces are gone; the workface set
  // is the workflow itself and AIS browsing lives in Config + Evaluation.
  assert.doesNotMatch(html, /data-workface-panel="scenario"/);
  assert.doesNotMatch(html, /data-workface-panel="algorithm"/);
  assert.doesNotMatch(html, /data-workface="scenario"/);
  assert.doesNotMatch(html, /data-workface="algorithm"/);

  assert.match(html, /id="validationScenarioChoices"/);
  assert.match(html, /data-config-step-panel="scenarios"/);
});

test('Historical Compare domains stay readable without horizontal overflow on mobile', () => {
  const compareCardRule = styles.match(/\.historical-ais-compare-grid span \{[^}]+\}/)?.[0] || '';
  assert.match(compareCardRule, /min-width:\s*0/);
  assert.match(compareCardRule, /max-width:\s*100%/);
  assert.match(compareCardRule, /width:\s*100%/);
  assert.match(compareCardRule, /overflow-wrap:\s*anywhere/);
  assert.match(styles, /\.historical-ais-compare-grid strong \{[^}]*word-break:\s*break-word/);
  assert.match(styles, /\.historical-ais-compare-grid \{[^}]*min-width:\s*0[^}]*width:\s*100%[^}]*max-width:\s*100%/);
  assert.match(
    styles,
    /@media \(max-width: 760px\) \{[\s\S]*?\.historical-ais-compare-grid \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); overflow-x: visible;/,
  );
  assert.match(
    styles,
    /@media \(max-width: 520px\) \{[\s\S]*?\.historical-ais-compare-grid \{[^}]*grid-template-columns: minmax\(0, 1fr\);/,
  );
});

test('workflow projection reads canonical presentation and ignores raw evidence shape', () => {
  const expected = structuredClone(runtimeShape.presentation);
  const original = projectHistoricalAISWorkflow(runtimeShape);
  const tamperedRaw = structuredClone(runtimeShape);
  tamperedRaw.evidence.threat_snapshot.vectors = [];
  tamperedRaw.evidence.threat_snapshot.schedule.entries = [];
  tamperedRaw.evidence.threat_snapshot.conflict_graph.clusters = [{}, {}, {}];
  tamperedRaw.leakage.human_reference_digest_in_run_spec = true;
  tamperedRaw.compare.domain_statuses.safety = { status: 'FAILED' };
  tamperedRaw.determinism = { status: 'FAIL', mismatches: ['raw-only'] };
  const tampered = projectHistoricalAISWorkflow(tamperedRaw);

  assert.equal(original.status, 'AVAILABLE');
  assert.deepEqual(original.presentation, expected);
  assert.deepEqual(tampered.presentation, expected);
  assert.equal(original.presentation.threat.cluster_count, 0);
  assert.equal(original.presentation.qualification.status, 'NOT_QUALIFIED');
  assert.notEqual(original.presentation.qualification.status, 'QUALIFIED');
  assert.equal(original.presentation.leakage.status, 'PASS_CONTRACT');
  assert.equal(original.presentation.determinism.status, 'PASS');
  assert.equal(original.presentation.compare.domain_statuses.safety, 'COMPLETE');
});

test('DOM separates bounded scene operability from incomplete predictive qualification', () => {
  class FakeElement {
    constructor() {
      this.textContent = '';
      this.dataset = {};
      this.classList = { toggle() {} };
      this.children = [];
      this.hidden = false;
      this.disabled = false;
      this.title = '';
    }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this[name] = value; }
  }
  const elements = new Map(
    [...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new FakeElement()]),
  );
  const documentRef = {
    getElementById: id => elements.get(id) || null,
    querySelectorAll: () => [],
    createElement: () => new FakeElement(),
  };
  const descriptorSha = 'b'.repeat(64);
  const scenarioDocument = {
    ...descriptor,
    id: descriptor.scenario_id,
    descriptor_sha256: descriptorSha,
    readiness: { status: 'READY', env_var: 'COLAV_HAIS_ARCHIVE_PATH' },
    presentation: {
      schema_version: 'historical-ais-scenario.presentation.v1',
      scenario: { id: descriptor.scenario_id, kind: 'HISTORICAL_AIS' },
      operability: { status: 'AVAILABLE', scope: 'BOUNDED' },
      qualification: {
        status: 'NOT_QUALIFIED',
        code: 'THREAT_EVIDENCE_INCOMPLETE',
        source_readiness: 'READY',
        future_gate: 'NONEMPTY_NATURAL_CLUSTER',
        limitations: descriptor.limitations,
      },
      runtime: {
        modes: descriptor.modes,
        historical_scenario_id: descriptor.scenario_id,
        algorithm_id: 'mid_mpc_ipopt',
        tracker_id: 'god',
        algorithm_capability_evidence: descriptor.algorithm_capability_evidence,
      },
      digests: {
        descriptor_sha256: descriptorSha,
        archive_sha256: descriptor.archive_scope.archive_sha256,
        entry_sha256: descriptor.current_window.entry_sha256,
        schema_sha256: descriptor.current_window.expected_schema_sha256,
        selection_sha256: descriptor.current_window.expected_selection_sha256,
        normalized_sha256: descriptor.current_window.expected_normalized_sha256,
        enc_profile_sha256: descriptor.enc.profile_digest,
        enc_cache_sha256: 'c'.repeat(64),
        enc_source_sha256: 'd'.repeat(64),
        dimension_registry_sha256: 'e'.repeat(64),
        dimension_source_sha256: 'f'.repeat(64),
      },
    },
  };
  const scenario = projectHistoricalAISScenario(scenarioDocument);
  const workflow = projectHistoricalAISWorkflow(runtimeShape);

  renderHistoricalAISWorkbench(documentRef, {
    catalog: { status: 'READY', error: null },
    detail: { status: 'READY', error: null },
    scenarios: [scenario],
    scenario,
    selectedId: scenario.scenarioId,
    selectedMode: 'COUNTERFACTUAL',
    workflow,
    busy: false,
  });

  assert.equal(elements.get('historicalAISSceneOperability').textContent, 'AVAILABLE · BOUNDED');
  assert.equal(
    elements.get('historicalAISPredictiveQualification').textContent,
    'NOT_QUALIFIED · THREAT_EVIDENCE_INCOMPLETE',
  );
  assert.equal(elements.get('historicalAISFutureGate').textContent, 'NONEMPTY_NATURAL_CLUSTER');
  assert.equal(elements.get('historicalAISEvidenceThreat').textContent, '2/2/0');
  assert.equal(elements.get('historicalAISEvidenceDeterminism').textContent, 'PASS · 0 mismatches');
  assert.equal(elements.get('historicalAISQualificationThreatGraph').textContent, '2/2/0');
  assert.equal(elements.get('historicalAISWorkflowStatus').textContent, 'COMPLETED');
  assert.equal(elements.get('historicalAISEvidenceVerdict').textContent, 'PASS');
  assert.equal(elements.get('historicalAISReplayStatus').textContent, 'NOT_APPLICABLE');
  assert.equal(elements.get('historicalAISWorkflowDigestArchive').textContent, 'workflow-archive');
  assert.equal(elements.get('historicalAISWorkflowDigestEntry').textContent, 'workflow-entry');
  assert.equal(elements.get('historicalAISWorkflowDigestSchema').textContent, 'workflow-schema');
  assert.equal(elements.get('historicalAISWorkflowDigestSelection').textContent, 'workflow-selection');
  assert.equal(elements.get('historicalAISWorkflowDigestNormalized').textContent, 'workflow-normalized');
  assert.equal(elements.get('historicalAISWorkflowDigestDescriptor').textContent, 'workflow-descriptor');
  assert.equal(elements.get('historicalAISWorkflowDigestEncProfile').textContent, 'workflow-enc-profile');
  assert.equal(elements.get('historicalAISWorkflowDigestEncCache').textContent, 'workflow-enc-cache');
  assert.equal(elements.get('historicalAISWorkflowDigestEncSource').textContent, 'workflow-enc-source');
  assert.equal(
    elements.get('historicalAISWorkflowDigestDimensionRegistry').textContent,
    'workflow-dimension-registry',
  );
  assert.equal(elements.get('historicalAISWorkflowDigestDimensionSource').textContent, 'workflow-dimension-source');
  assert.notEqual(elements.get('historicalAISWorkflowStatus').textContent, 'FAILED');

  const replayShape = structuredClone(runtimeShape);
  replayShape.mode = 'HISTORICAL_REPLAY';
  replayShape.presentation.evidence.replay = {
    status: 'AVAILABLE',
    mode: 'HISTORICAL_REPLAY',
    factory: 'HistoricalReplayFactory',
    dataset_digest: 'dataset-digest',
    runtime_actor_set_digest: 'actor-set-digest',
    trajectory_digest: 'trajectory-digest',
    manifest_digest: 'manifest-digest',
    dimension_registry_digest: 'dimension-registry-digest',
    dimension_source_digest: 'dimension-source-digest',
  };
  const replayWorkflow = projectHistoricalAISWorkflow(replayShape);
  renderHistoricalAISWorkbench(documentRef, {
    catalog: { status: 'READY', error: null },
    detail: { status: 'READY', error: null },
    scenarios: [scenario],
    scenario,
    selectedId: scenario.scenarioId,
    selectedMode: 'HISTORICAL_REPLAY',
    workflow: replayWorkflow,
    busy: false,
  });
  assert.equal(elements.get('historicalAISReplayStatus').textContent, 'AVAILABLE');
  assert.equal(elements.get('historicalAISReplayMode').textContent, 'HISTORICAL_REPLAY');
  assert.equal(elements.get('historicalAISReplayFactory').textContent, 'HistoricalReplayFactory');
  assert.equal(elements.get('historicalAISReplayDataset').textContent, 'dataset-digest');
  assert.equal(elements.get('historicalAISReplayActorSet').textContent, 'actor-set-digest');
  assert.equal(elements.get('historicalAISReplayTrajectory').textContent, 'trajectory-digest');
  assert.equal(elements.get('historicalAISReplayManifest').textContent, 'manifest-digest');
  assert.equal(elements.get('historicalAISReplayDimensionRegistry').textContent, 'dimension-registry-digest');
  assert.equal(elements.get('historicalAISReplayDimensionSource').textContent, 'dimension-source-digest');
});

test('missing canonical presentation is typed unavailable with null workflow facts', () => {
  const missing = structuredClone(runtimeShape);
  delete missing.presentation;
  const projection = projectHistoricalAISWorkflow(missing);

  assert.equal(projection.status, 'UNAVAILABLE');
  assert.equal(projection.error.code, 'INVALID_WORKFLOW_PRESENTATION');
  assert.equal(projection.workflowId, null);
  assert.equal(projection.presentation, null);
});

test('browser modules do not inspect raw evidence or carry a default scenario', () => {
  const combined = clientSources.join('\n');
  assert.doesNotMatch(combined, /DEFAULT_HISTORICAL_AIS_SCENARIO/);
  assert.doesNotMatch(combined, /threat_snapshot|human_reference_digest_in_run_spec|determinism_mismatches/);
  assert.doesNotMatch(combined, /evidence\.run|evidence\.threat|compare\.domain_statuses/);
  assert.doesNotMatch(combined, /sealed_expected|cluster_count:\s*1/);
  assert.doesNotMatch(combined, /expected_cluster_count|sealed_expected_cluster/);
  assert.ok(clientSources.at(-1).split('\n').length < 80, 'composition root stays shallow');
});

test('Historical AIS API adapter uses only dedicated scenario/workflow routes', async () => {
  const requests = [];
  const fetchImpl = async (url, options = {}) => {
    requests.push({ url, options });
    return {
      ok: true,
      status: 200,
      async json() {
        if (url === '/api/historical/scenarios') return [];
        return runtimeShape;
      },
    };
  };
  const api = createHistoricalAISApi({ fetchImpl, WebSocketImpl: null });

  await api.listScenarios();
  await api.getScenario('hais_romsdal_20260701_120007_121007');
  await api.createWorkflow('hais_romsdal_20260701_120007_121007', 'COUNTERFACTUAL');
  await api.runWorkflow('workflow-browser-regression');
  await api.createActiveSession({
    validationRuleId: 'multiship',
    scenarioId: 'hais_romsdal_20260701_120007_121007',
    algorithmId: 'mid_mpc_ipopt',
    trackerId: 'god',
  });

  assert.deepEqual(requests.map(request => request.url), [
    '/api/historical/scenarios',
    '/api/historical/scenarios/hais_romsdal_20260701_120007_121007',
    '/api/historical/scenarios/hais_romsdal_20260701_120007_121007/workflows',
    '/api/historical/workflows/workflow-browser-regression/run',
    '/api/sessions',
  ]);
  assert.deepEqual(JSON.parse(requests[2].options.body), { mode: 'COUNTERFACTUAL' });
  assert.deepEqual(JSON.parse(requests[4].options.body), {
    validation_rule_id: 'multiship',
    scenario_id: 'hais_romsdal_20260701_120007_121007',
    algorithm_id: 'mid_mpc_ipopt',
    tracker_id: 'god',
  });
  assert.ok(requests.every(request => !request.url.startsWith('/api/scenarios')));
});
