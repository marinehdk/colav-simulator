/**
 * Historical AIS workbench.
 *
 * This module is a read-only projection of the Historical AIS scenario and
 * workflow contracts. It deliberately has no dependency on Active Session
 * Runtime: a Historical workflow is a separate authority and must never be
 * presented as the current ordinary simulation session.
 */

export const HISTORICAL_AIS_SCENARIO_ID = 'hais_romsdal_20260701_120000_120100';

const SOURCE_ARCHIVE_NAME = 'Hais_e716cfac-348c-417b-acbd-04a228732de7.zip';
const ENTRY_NAME = 'hais_2026-07-01.snappy.parquet';

/**
 * Browse-only descriptor used when the scenario catalog endpoint is not yet
 * mounted. It records the bounded acceptance window and its known limits; it
 * intentionally stays UNBOUND so a missing backend source cannot become a
 * silently runnable benchmark.
 */
export const DEFAULT_HISTORICAL_AIS_SCENARIO = Object.freeze({
  id: HISTORICAL_AIS_SCENARIO_ID,
  scenario_id: HISTORICAL_AIS_SCENARIO_ID,
  type: 'HISTORICAL_AIS',
  category: 'MS',
  name: 'Romsdal AIS · 2026-07-01 12:00–12:01 UTC',
  display_name: 'Romsdal AIS · 3-ship acceptance window',
  description: 'One immutable HAIS selection shared by Historical Replay and Counterfactual.',
  source: {
    archive_name: SOURCE_ARCHIVE_NAME,
    archive_days: 23,
    archive_rows: 51_522_509,
    archive_mmsi: 1_226,
    status: 'UNBOUND',
    bound: false,
    attribution: 'Kystverket HAIS · NLOD 2.0',
  },
  selection: {
    entry_name: ENTRY_NAME,
    start_utc: '2026-07-01T12:00:00+00:00',
    end_utc: '2026-07-01T12:01:00+00:00',
    duration_label: '1 min',
    bbox: [6.05, 62.44, 6.17, 62.5],
    filter_mmsi: [257252000, 258764000, 259189000, 259197000],
    selected_mmsi: [257252000, 258764000, 259189000],
    runtime_actor_count: 3,
    reference_mmsi: 259189000,
    t0_utc: '2026-07-01T12:00:30+00:00',
    source_row_count: 24,
    normalized_row_count: 24,
    quality_finding_count: 98,
  },
  enc: {
    profile_id: 'romsdal-expanded',
    qualification_state: 'QUALIFIED',
    preflight_status: 'PASS',
  },
  modes: [
    {
      id: 'HISTORICAL_REPLAY',
      label: 'Historical Replay',
      description: '全船历史 AIS 回放；不运行 COLAV。',
    },
    {
      id: 'COUNTERFACTUAL',
      label: 'Counterfactual',
      description: 'T0 后 Reference Vessel 交给 Mid-MPC；其他船继续历史回放。',
    },
  ],
  limitation: '当前仅验证该窗口/3船；全archive未完成ENC资格。',
});

const SOURCE_BOUND_STATES = new Set(['BOUND', 'READY', 'QUALIFIED', 'PASS', 'AVAILABLE']);
const DEFAULT_MODE = 'HISTORICAL_REPLAY';

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function firstDefined(...values) {
  return values.find(value => value !== undefined && value !== null);
}

function numberOrNull(value) {
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

function normalizeScenario(value) {
  const raw = asObject(value);
  const archiveScope = asObject(raw.archive_scope);
  const currentWindow = asObject(raw.current_window);
  const source = {
    ...DEFAULT_HISTORICAL_AIS_SCENARIO.source,
    ...asObject(raw.source),
    ...asObject(raw.source_readiness),
    ...asObject(raw.readiness),
    ...asObject(raw.source_binding),
    ...asObject(raw.dataset),
    archive_name: firstDefined(raw.source?.archive_name, archiveScope.source_name),
    archive_days: firstDefined(raw.source?.archive_days, archiveScope.day_count),
    archive_rows: firstDefined(raw.source?.archive_rows, archiveScope.row_count),
    archive_mmsi: firstDefined(raw.source?.archive_mmsi, archiveScope.union_mmsi_count),
  };
  const selection = {
    ...DEFAULT_HISTORICAL_AIS_SCENARIO.selection,
    ...asObject(raw.selection),
    ...currentWindow,
    filter_mmsi: firstDefined(raw.selection?.filter_mmsi, currentWindow.selection_mmsi),
    selected_mmsi: firstDefined(raw.selection?.selected_mmsi, currentWindow.runtime_mmsi),
  };
  const enc = {
    ...DEFAULT_HISTORICAL_AIS_SCENARIO.enc,
    ...asObject(raw.enc),
    ...asObject(raw.enc_profile),
  };
  const modeDefaults = Object.fromEntries(DEFAULT_HISTORICAL_AIS_SCENARIO.modes.map(mode => [mode.id, mode]));
  const modeValues = asArray(raw.modes).length ? asArray(raw.modes) : DEFAULT_HISTORICAL_AIS_SCENARIO.modes;
  const modes = modeValues.map(mode => typeof mode === 'string' ? (modeDefaults[mode] || {
    id: mode,
    label: mode,
    description: '',
  }) : mode);
  const scenario = {
    ...DEFAULT_HISTORICAL_AIS_SCENARIO,
    ...raw,
    id: firstDefined(raw.id, raw.scenario_id, DEFAULT_HISTORICAL_AIS_SCENARIO.id),
    scenario_id: firstDefined(raw.scenario_id, raw.id, DEFAULT_HISTORICAL_AIS_SCENARIO.id),
    source,
    selection,
    enc,
    modes,
    limitation: firstDefined(raw.limitation, DEFAULT_HISTORICAL_AIS_SCENARIO.limitation),
  };
  const sourceStatus = String(firstDefined(source.status, source.readiness, 'UNBOUND')).toUpperCase();
  scenario.source = {
    ...source,
    status: sourceStatus,
    bound: source.bound === true || source.ready === true || SOURCE_BOUND_STATES.has(sourceStatus),
  };
  return scenario;
}

function countFrom(value, candidates) {
  const object = asObject(value);
  for (const candidate of candidates) {
    const item = object[candidate];
    if (Array.isArray(item)) return item.length;
    const number = numberOrNull(item);
    if (number !== null) return number;
  }
  return 0;
}

function hasCountField(value, candidates) {
  const object = asObject(value);
  return candidates.some(candidate => Object.prototype.hasOwnProperty.call(object, candidate));
}

function actualCount(primary, candidates, fallback) {
  return hasCountField(primary, candidates) ? countFrom(primary, candidates) : countFrom(fallback, candidates);
}

function normalizeDomainStatuses(value) {
  return Object.fromEntries(Object.entries(asObject(value)).map(([domain, status]) => [
    domain,
    typeof status === 'string' ? status : firstDefined(asObject(status).status, null),
  ]));
}

function normalizeDeterminism(document, evidence, mode) {
  if (mode === 'HISTORICAL_REPLAY') return { status: 'NOT_APPLICABLE', mismatches: [] };
  const rawValue = firstDefined(evidence.determinism, document.determinism);
  const raw = asObject(rawValue);
  const mismatchesValue = firstDefined(raw.mismatches, document.determinism_mismatches);
  const mismatches = asArray(mismatchesValue);
  if (typeof raw.status === 'string' && raw.status) {
    return { status: raw.status, mismatches };
  }
  if (Array.isArray(mismatchesValue)) {
    return { status: mismatches.length ? 'FAIL' : 'PASS', mismatches };
  }
  return { status: 'NOT_CHECKED', mismatches: [] };
}

function normalizeLeakage(leakage, mode) {
  if (typeof leakage.status === 'string' && leakage.status) return leakage.status;
  if (mode === 'HISTORICAL_REPLAY') return 'NOT_APPLICABLE';
  if (Object.prototype.hasOwnProperty.call(leakage, 'human_reference_digest_in_run_spec')) {
    return leakage.human_reference_digest_in_run_spec === false ? 'PASS_CONTRACT' : 'FAIL_CONTRACT';
  }
  return null;
}

function normalizeExpectedThreat(scenario) {
  const sealed = asObject(scenario.sealed_expected);
  const expectedEvidence = asObject(scenario.expected_evidence);
  const expected = asObject(firstDefined(sealed.threat, expectedEvidence.threat));
  const keys = ['vectors', 'vector_count', 'schedule', 'schedule_context_count', 'clusters', 'cluster_count'];
  if (!hasCountField(expected, keys)) return null;
  return {
    vectors: countFrom(expected, ['vectors', 'vector_count']),
    schedule: countFrom(expected, ['schedule', 'schedule_context_count']),
    clusters: countFrom(expected, ['clusters', 'cluster_count']),
  };
}

function normalizeEvidence(workflow) {
  const document = asObject(workflow);
  const evidence = asObject(document.evidence);
  const run = asObject(firstDefined(evidence.run, document.run));
  const snapshot = asObject(firstDefined(evidence.threat_snapshot, document.threat_snapshot));
  const threat = asObject(firstDefined(evidence.threat, document.threat));
  const compare = asObject(firstDefined(document.compare, evidence.compare));
  const evaluation = asObject(firstDefined(evidence.evaluation, document.evaluation));
  const snapshotSchedule = asObject(snapshot.schedule);
  const evidenceSchedule = asObject(threat.schedule);
  const snapshotConflictGraph = asObject(snapshot.conflict_graph);
  const evidenceConflictGraph = asObject(threat.conflict_graph);
  const leakage = asObject(document.leakage);
  const domainStatuses = normalizeDomainStatuses(firstDefined(compare.domain_statuses, compare.domains));
  const mode = firstDefined(document.mode, run.historical_execution_mode, null);

  return {
    mode,
    fallback: firstDefined(run.fallback_used, null),
    threat: {
      vectors: actualCount(snapshot, ['vectors', 'vector_count'], threat),
      schedule: actualCount(snapshotSchedule, ['entries', 'schedule_context_count'], evidenceSchedule),
      clusters: actualCount(snapshotConflictGraph, ['clusters', 'cluster_count'], evidenceConflictGraph),
    },
    leakage: normalizeLeakage(leakage, mode),
    determinism: normalizeDeterminism(document, evidence, mode),
    compareDomains: domainStatuses,
    verdict: firstDefined(compare.overall_assurance_verdict, compare.verdict, null),
    evaluationStatus: firstDefined(evaluation.evaluation_status, null),
    evaluationGate: firstDefined(evaluation.gate, null),
  };
}

/**
 * Project a scenario and optional workflow document into UI-safe facts.
 * Counts and statuses come from backend evidence; no risk calculation occurs
 * in this module.
 */
export function createHistoricalAISProjection(value, workflow = null) {
  const scenario = normalizeScenario(value);
  const selection = scenario.selection;
  const document = asObject(workflow);
  const evidence = normalizeEvidence(document);
  const source = scenario.source;
  return {
    scenarioId: scenario.id,
    title: firstDefined(scenario.display_name, scenario.name, scenario.id),
    description: scenario.description,
    source: {
      archiveName: firstDefined(source.archive_name, SOURCE_ARCHIVE_NAME),
      archiveDays: numberOrNull(firstDefined(source.archive_days, source.days)) || 0,
      archiveRows: numberOrNull(firstDefined(source.archive_rows, source.row_count)) || 0,
      archiveMmsi: numberOrNull(firstDefined(source.archive_mmsi, source.mmsi_count)) || 0,
      status: source.status,
      bound: source.bound === true,
      attribution: source.attribution || '',
    },
    selection: {
      entryName: firstDefined(selection.entry_name, ENTRY_NAME),
      startUtc: selection.start_utc,
      endUtc: selection.end_utc,
      durationLabel: firstDefined(selection.duration_label, '1 min'),
      bbox: asArray(selection.bbox),
      filterMmsi: asArray(selection.filter_mmsi || selection.mmsi),
      selectedMmsi: asArray(selection.selected_mmsi),
      runtimeActorCount: numberOrNull(firstDefined(selection.runtime_actor_count, selection.actor_count)) || 0,
      referenceMmsi: selection.reference_mmsi,
      t0Utc: selection.t0_utc,
      sourceRows: numberOrNull(selection.source_row_count) || 0,
      normalizedRows: numberOrNull(selection.normalized_row_count) || 0,
      qualityFindings: numberOrNull(selection.quality_finding_count) || 0,
    },
    enc: {
      profileId: firstDefined(scenario.enc.profile_id, 'romsdal-expanded'),
      qualification: firstDefined(scenario.enc.qualification_state, scenario.enc.qualification, 'UNKNOWN'),
      preflight: firstDefined(scenario.enc.preflight_status, scenario.enc.status, 'UNKNOWN'),
    },
    qualification: {
      expectedThreat: normalizeExpectedThreat(scenario),
    },
    modes: asArray(scenario.modes),
    limitation: scenario.limitation,
    workflowId: document.workflow_id || null,
    workflowStatus: document.status || null,
    mode: evidence.mode,
    stages: asObject(document.stages),
    run: {
      available: source.bound === true,
      disabledReason: source.bound === true ? '' : 'Source unbound · bind the HAIS archive before Run',
    },
    evidence,
  };
}

async function responseJson(fetchImpl, url, options = {}) {
  if (typeof fetchImpl !== 'function') throw new Error('Historical AIS API unavailable');
  const response = await fetchImpl(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail;
    const reason = typeof detail === 'string' ? detail : detail?.reason;
    throw new Error(reason || `Historical AIS API ${response.status}`);
  }
  return body;
}

/** Network adapter for the dedicated Historical AIS scenario/workflow API. */
export function createHistoricalAISApi({ fetchImpl = globalThis.fetch, WebSocketImpl = globalThis.WebSocket } = {}) {
  return {
    async listScenarios() {
      const body = await responseJson(fetchImpl, '/api/historical/scenarios');
      return Array.isArray(body) ? body : asArray(body.scenarios);
    },
    async getScenario(scenarioId) {
      return responseJson(fetchImpl, `/api/historical/scenarios/${encodeURIComponent(scenarioId)}`);
    },
    async createWorkflow(scenarioId, mode) {
      return responseJson(fetchImpl, `/api/historical/scenarios/${encodeURIComponent(scenarioId)}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
    },
    async runWorkflow(workflowId) {
      return responseJson(fetchImpl, `/api/historical/workflows/${encodeURIComponent(workflowId)}/run`, {
        method: 'POST',
      });
    },
    async getWorkflow(workflowId) {
      return responseJson(fetchImpl, `/api/historical/workflows/${encodeURIComponent(workflowId)}`);
    },
    connectWorkflow(workflowId, onDocument, onError) {
      if (typeof WebSocketImpl !== 'function') return null;
      const location = globalThis.location;
      const protocol = location?.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = location?.host || '127.0.0.1:8012';
      const socket = new WebSocketImpl(`${protocol}//${host}/ws/historical/${encodeURIComponent(workflowId)}`);
      socket.addEventListener?.('message', event => {
        try { onDocument(JSON.parse(event.data)); } catch (error) { onError?.(error); }
      });
      socket.addEventListener?.('error', event => onError?.(event));
      return socket;
    },
  };
}

/**
 * Deterministic fixture adapter for DOM acceptance tests and local shell
 * prototyping. It does not change the production source-boundary default.
 */
export function createHistoricalAISFixtureApi({ scenario = DEFAULT_HISTORICAL_AIS_SCENARIO, workflow = null } = {}) {
  let current = workflow;
  return {
    async listScenarios() { return [scenario]; },
    async getScenario() { return scenario; },
    async createWorkflow(_scenarioId, mode) {
      current = current || {
        workflow_id: 'fixture-historical-workflow',
        mode,
        status: 'PREPARED',
        stages: {
          dataset: 'SELECTED',
          case: mode === 'COUNTERFACTUAL' ? 'PUBLISHED' : 'NOT_APPLICABLE',
          replay: mode === 'HISTORICAL_REPLAY' ? 'PREPARED' : 'NOT_APPLICABLE',
          counterfactual: mode === 'COUNTERFACTUAL' ? 'PREPARED' : 'NOT_APPLICABLE',
          evaluation: null,
          compare: null,
        },
      };
      return current;
    },
    async runWorkflow() { return current; },
    async getWorkflow() { return current; },
    connectWorkflow() { return null; },
  };
}

function setText(documentRef, id, value, fallback = '—') {
  const node = documentRef.getElementById(id);
  if (node) node.textContent = value === undefined || value === null || value === '' ? fallback : String(value);
  return node;
}

function formatMmsi(value) {
  return value === undefined || value === null ? '—' : String(value);
}

function formatBbox(bbox) {
  return bbox.length === 4 ? `${bbox[0]}, ${bbox[1]} → ${bbox[2]}, ${bbox[3]}` : '—';
}

function formatRows(value) {
  return value ? Number(value).toLocaleString('en-US') : '—';
}

function createChoice(documentRef, { id, label, description, active }) {
  const button = documentRef.createElement('button');
  button.type = 'button';
  button.className = 'historical-ais-mode-choice';
  button.dataset.historicalMode = id;
  button.setAttribute('aria-pressed', String(active));
  const title = documentRef.createElement('strong');
  title.textContent = label || id;
  const copy = documentRef.createElement('small');
  copy.textContent = description || '';
  button.append(title, copy);
  return button;
}

function renderScenarioList(documentRef, scenarios, selectedId) {
  const list = documentRef.getElementById('historicalAISScenarioList');
  if (!list) return;
  list.replaceChildren(...scenarios.map(scenario => {
    const projection = createHistoricalAISProjection(scenario);
    const button = documentRef.createElement('button');
    button.type = 'button';
    button.className = 'historical-ais-scenario-choice';
    button.dataset.historicalScenarioId = projection.scenarioId;
    button.setAttribute('aria-pressed', String(projection.scenarioId === selectedId));
    const title = documentRef.createElement('strong');
    title.textContent = projection.title;
    const meta = documentRef.createElement('small');
    meta.textContent = `${projection.selection.durationLabel} · ${projection.selection.runtimeActorCount} runtime actors · ${projection.enc.profileId}`;
    button.append(title, meta);
    return button;
  }));
}

function renderScenarioDetail(documentRef, projection) {
  setText(documentRef, 'historicalAISScenarioName', projection.title);
  setText(documentRef, 'historicalAISScenarioDescription', projection.description);
  setText(documentRef, 'historicalAISScenarioSourceStatus', projection.source.bound ? 'BOUND' : 'UNBOUND');
  setText(documentRef, 'historicalAISScenarioWindow', `${projection.selection.startUtc} → ${projection.selection.endUtc}`);
  setText(documentRef, 'historicalAISScenarioDuration', projection.selection.durationLabel);
  setText(documentRef, 'historicalAISScenarioActors', `${projection.selection.runtimeActorCount} runtime actors`);
  setText(documentRef, 'historicalAISScenarioSource', projection.source.archiveName);
  setText(documentRef, 'historicalAISScenarioArchive', `${projection.source.archiveDays} days · ${formatRows(projection.source.archiveRows)} rows · ~${formatRows(projection.source.archiveMmsi)} MMSI`);
  setText(documentRef, 'historicalAISScenarioEntry', projection.selection.entryName);
  setText(documentRef, 'historicalAISScenarioFilter', `${projection.selection.filterMmsi.length} MMSI filter`);
  setText(documentRef, 'historicalAISScenarioBbox', formatBbox(projection.selection.bbox));
  setText(documentRef, 'historicalAISScenarioReference', formatMmsi(projection.selection.referenceMmsi));
  setText(documentRef, 'historicalAISScenarioT0', projection.selection.t0Utc);
  setText(documentRef, 'historicalAISScenarioTargets', projection.selection.selectedMmsi
    .filter(mmsi => String(mmsi) !== String(projection.selection.referenceMmsi))
    .map(formatMmsi)
    .join(', '));
  setText(documentRef, 'historicalAISScenarioEnc', `${projection.enc.profileId} · ${projection.enc.qualification}`);
  setText(documentRef, 'historicalAISScenarioRows', `${formatRows(projection.selection.sourceRows)} source / ${formatRows(projection.selection.normalizedRows)} normalized`);
  setText(documentRef, 'historicalAISScenarioQuality', `${formatRows(projection.selection.qualityFindings)} quality findings`);
  const expectedThreat = projection.qualification.expectedThreat;
  setText(
    documentRef,
    'historicalAISScenarioQualificationThreat',
    expectedThreat ? `${expectedThreat.vectors}/${expectedThreat.schedule}/${expectedThreat.clusters} sealed expected · not runtime` : 'NOT PUBLISHED',
  );
  setText(documentRef, 'historicalAISScenarioLimitation', projection.limitation);
  const banner = documentRef.getElementById('historicalAISScenarioLimitation');
  banner?.closest('.historical-ais-limitation')?.classList.toggle('is-warning', !projection.source.bound);
  setText(documentRef, 'historicalAISScenarioHeaderStatus', projection.source.bound ? 'BOUND' : 'UNBOUND');
}

function renderBenchmark(documentRef, projection, selectedMode) {
  setText(documentRef, 'historicalAISBenchmarkScenario', projection.title);
  setText(documentRef, 'historicalAISBenchmarkWindow', `${projection.selection.durationLabel} · ${projection.selection.runtimeActorCount} runtime actors`);
  setText(documentRef, 'historicalAISBenchmarkSource', projection.source.bound ? 'SOURCE READY' : 'SOURCE UNBOUND');
  setText(documentRef, 'historicalAISBenchmarkLimitation', projection.limitation);
  setText(documentRef, 'historicalAISModeDescription', projection.modes.find(mode => mode.id === selectedMode)?.description);
  const run = documentRef.getElementById('historicalAISRun');
  if (run) {
    run.disabled = !projection.run.available || Boolean(projection.workflowStatus === 'RUNNING');
    run.textContent = projection.workflowStatus === 'RUNNING' ? 'RUNNING' : 'Run Historical Workflow';
    run.title = projection.run.available ? '' : projection.run.disabledReason;
  }
  documentRef.querySelectorAll('[data-historical-mode]').forEach(button => {
    const active = button.dataset.historicalMode === selectedMode;
    button.setAttribute('aria-pressed', String(active));
    button.classList.toggle('active', active);
  });
  setText(documentRef, 'historicalAISWorkflowAuthority', projection.workflowId ? `Historical workflow · ${projection.workflowId}` : 'No Historical workflow selected');
  setText(documentRef, 'historicalAISWorkflowStatus', projection.workflowStatus || 'BROWSE ONLY');
  const stageIds = ['dataset', 'case', 'replay', 'counterfactual', 'evaluation', 'compare'];
  stageIds.forEach(stage => setText(documentRef, `historicalAISStage-${stage}`, projection.stages[stage] || '—'));
  setText(documentRef, 'historicalAISEvidenceFallback', projection.evidence.fallback === null ? '—' : String(projection.evidence.fallback));
  setText(documentRef, 'historicalAISEvidenceThreat', `${projection.evidence.threat.vectors}/${projection.evidence.threat.schedule}/${projection.evidence.threat.clusters}`);
  setText(documentRef, 'historicalAISEvidenceLeakage', projection.evidence.leakage);
  const determinism = projection.evidence.determinism;
  setText(
    documentRef,
    'historicalAISEvidenceDeterminism',
    ['PASS', 'FAIL'].includes(determinism.status)
      ? `${determinism.status} · ${determinism.mismatches.length} mismatches`
      : determinism.status,
  );
  setText(documentRef, 'historicalAISEvidenceVerdict', projection.evidence.verdict || projection.evidence.evaluationGate);
  const domains = projection.evidence.compareDomains || {};
  ['safety', 'colreg', 'maneuver', 'efficiency', 'human_similarity'].forEach(domain => {
    setText(documentRef, `historicalAISCompare-${domain}`, domains[domain]);
  });
}

function setCatalogStatus(documentRef, message, kind = 'info') {
  const node = documentRef.getElementById('historicalAISCatalogStatus');
  if (!node) return;
  node.textContent = message;
  node.dataset.state = kind;
}

/** Mount the Scenario and Evaluation Historical AIS public DOM seam. */
export function mountHistoricalAISWorkbench({
  documentRef = globalThis.document,
  api = createHistoricalAISApi(),
} = {}) {
  if (!documentRef?.getElementById('historicalAISBenchmark')) return null;

  const state = {
    scenarios: [DEFAULT_HISTORICAL_AIS_SCENARIO],
    selectedId: HISTORICAL_AIS_SCENARIO_ID,
    selectedMode: DEFAULT_MODE,
    selectedScenario: DEFAULT_HISTORICAL_AIS_SCENARIO,
    workflow: null,
    socket: null,
  };

  function render() {
    const projection = createHistoricalAISProjection(state.selectedScenario, state.workflow);
    renderScenarioList(documentRef, state.scenarios, state.selectedId);
    renderScenarioDetail(documentRef, projection);
    renderBenchmark(documentRef, projection, state.selectedMode);
    const modeChoices = documentRef.getElementById('historicalAISModeChoices');
    if (modeChoices) {
      modeChoices.replaceChildren(...projection.modes.map(mode => createChoice(documentRef, {
        ...mode,
        active: mode.id === state.selectedMode,
      })));
    }
  }

  async function selectScenario(scenarioId) {
    state.selectedId = scenarioId;
    const local = state.scenarios.find(item => String(item.id || item.scenario_id) === scenarioId);
    state.selectedScenario = local || DEFAULT_HISTORICAL_AIS_SCENARIO;
    state.workflow = null;
    render();
    if (api.getScenario) {
      try {
        state.selectedScenario = await api.getScenario(scenarioId);
        render();
      } catch (error) {
        setCatalogStatus(documentRef, `Scenario detail unavailable · ${error.message}`, 'warning');
      }
    }
  }

  async function runWorkflow() {
    const projection = createHistoricalAISProjection(state.selectedScenario, state.workflow);
    if (!projection.run.available || !api.createWorkflow) return;
    const run = documentRef.getElementById('historicalAISRun');
    if (run) run.disabled = true;
    try {
      state.workflow = await api.createWorkflow(state.selectedId, state.selectedMode);
      render();
      if (api.connectWorkflow && state.workflow?.workflow_id) {
        state.socket?.close?.();
        state.socket = api.connectWorkflow(
          state.workflow.workflow_id,
          document => { state.workflow = document; render(); },
          () => {},
        );
      }
      if (api.runWorkflow && state.workflow?.workflow_id) {
        state.workflow = await api.runWorkflow(state.workflow.workflow_id);
        render();
      }
    } catch (error) {
      state.workflow = {
        ...(state.workflow || {}),
        status: 'FAILED',
        message: error.message,
      };
      setCatalogStatus(documentRef, `Historical workflow failed · ${error.message}`, 'error');
      render();
    } finally {
      if (run) run.disabled = !createHistoricalAISProjection(state.selectedScenario, state.workflow).run.available;
    }
  }

  documentRef.getElementById('historicalAISScenarioList')?.addEventListener('click', event => {
    const button = event.target.closest('[data-historical-scenario-id]');
    if (button) selectScenario(button.dataset.historicalScenarioId);
  });
  documentRef.getElementById('historicalAISModeChoices')?.addEventListener('click', event => {
    const button = event.target.closest('[data-historical-mode]');
    if (!button) return;
    state.selectedMode = button.dataset.historicalMode;
    render();
  });
  documentRef.getElementById('historicalAISRun')?.addEventListener('click', runWorkflow);

  render();
  (async () => {
    try {
      const scenarios = await api.listScenarios();
      if (!Array.isArray(scenarios) || !scenarios.length) throw new Error('No Historical AIS scenarios published');
      state.scenarios = scenarios;
      const selected = scenarios.find(item => String(item.id || item.scenario_id) === state.selectedId) || scenarios[0];
      state.selectedId = String(selected.id || selected.scenario_id);
      state.selectedScenario = selected;
      setCatalogStatus(documentRef, 'Historical AIS catalog · backend', 'ready');
      render();
    } catch (error) {
      state.scenarios = [DEFAULT_HISTORICAL_AIS_SCENARIO];
      state.selectedId = HISTORICAL_AIS_SCENARIO_ID;
      state.selectedScenario = DEFAULT_HISTORICAL_AIS_SCENARIO;
      setCatalogStatus(documentRef, 'Browse-only fixture · source unbound', 'warning');
      render();
    }
  })();

  return {
    state,
    render,
    selectScenario,
    runWorkflow,
    projection: () => createHistoricalAISProjection(state.selectedScenario, state.workflow),
  };
}

if (typeof document !== 'undefined') {
  mountHistoricalAISWorkbench();
}
