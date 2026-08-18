import { createValidationAssembly } from './validation-assembly.js?v=20260818-candidate2-runtime-final';
import { activeSessionRuntime, telemetryProjection } from './session-runtime-instance.js?v=20260819-candidate3-projection';

const OPENBRIDGE_VERSION = '1.0.1';
const OPENBRIDGE_BASE = 'https://cdn.jsdelivr.net/npm/@oicl/openbridge-webcomponents@1.0.1/dist';
const RULE_IMAGES = {
  rule13: ['/static/assets/openbridge/Rule13.png'],
  rule14: ['/static/assets/openbridge/Rule14.png'],
  rule15: ['/static/assets/openbridge/Rule15.png'],
  multiship: ['/static/assets/openbridge/Rule16.png', '/static/assets/openbridge/Rule17.png'],
};

let assembly = null;
let multishipRuleImageIndex = 0;
let lastRuntimeSyncKey = null;

class ApiError extends Error {
  constructor(response, detail) {
    const backend = typeof detail === 'object'
      ? `${detail.status || 'ERROR'}: ${detail.reason || JSON.stringify(detail)}`
      : detail || `HTTP ${response.status}`;
    super(backend);
    this.name = 'ApiError';
    this.status = response.status;
    this.detail = detail;
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response, body.detail ?? body);
  return body;
}

function showOpenBridgeError(error) {
  const banner = document.getElementById('openbridgeLoadError');
  banner.hidden = false;
  banner.textContent = `OpenBridge ${OPENBRIDGE_VERSION} failed to load: ${error.message}. Check CDN/network access and retry the page.`;
}

async function loadOpenBridge() {
  const stylesheet = document.getElementById('openbridgeStyles');
  stylesheet.addEventListener('error', () => showOpenBridgeError(new Error('stylesheet request failed')), { once: true });
  if (stylesheet.dataset.failed === 'true') showOpenBridgeError(new Error('stylesheet request failed'));
  try {
    await Promise.all([
      import(`${OPENBRIDGE_BASE}/components/top-bar/top-bar.js/+esm`),
      import(`${OPENBRIDGE_BASE}/components/card/card.js/+esm`),
    ]);
    await Promise.all([
      customElements.whenDefined('obc-top-bar'),
      customElements.whenDefined('obc-card'),
    ]);
    document.documentElement.dataset.openbridge = OPENBRIDGE_VERSION;
  } catch (error) {
    showOpenBridgeError(error);
  }
}

function switchWorkface(name) {
  document.querySelectorAll('[data-workface-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.workfacePanel !== name;
  });
  document.querySelectorAll('[data-workface]').forEach((button) => {
    const selected = button.dataset.workface === name;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-selected', String(selected));
  });
  if (name === 'deployment') window.dispatchEvent(new Event('resize'));
}

function optionLabel(item) {
  return item.name || item.display_name || item.id;
}

function populateSelect(id, items, selected) {
  const select = document.getElementById(id);
  select.replaceChildren(...items.map((item) => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = optionLabel(item);
    option.disabled = !item.enabled;
    option.title = item.incompatibility_reason || item.known_failure || '';
    return option;
  }));
  select.value = selected || '';
}

function renderRuleChoices(snapshot) {
  const container = document.getElementById('validationRuleChoices');
  const selected = snapshot.draft?.validation_rule_id;
  const visibleRules = new Set(['rule13', 'rule14', 'rule15', 'multiship']);
  container.replaceChildren(...(snapshot.options.validation_rule_id || []).filter((item) => visibleRules.has(item.id)).map((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'choice-card';
    button.dataset.ruleId = item.id;
    button.disabled = snapshot.readOnly || snapshot.creating || !item.enabled;
    button.setAttribute('role', 'radio');
    button.setAttribute('aria-checked', String(item.id === selected));
    const title = document.createElement('strong');
    title.textContent = item.id.toUpperCase();
    const detail = document.createElement('span');
    detail.textContent = `${item.readiness_grade || 'G0'} · ${item.enabled ? 'Selectable' : 'Unavailable'}`;
    button.append(title, detail);
    return button;
  }));
}

function replaceDefinitionRows(element, rows) {
  element.replaceChildren();
  for (const [label, value] of rows) {
    const row = document.createElement('div');
    const term = document.createElement('dt');
    const description = document.createElement('dd');
    term.textContent = label;
    description.textContent = value ?? 'Not exposed';
    row.append(term, description);
    element.append(row);
  }
}

function selectedCatalogItem(snapshot, collection, id) {
  return snapshot.catalog?.[collection]?.find((item) => item.id === id) || null;
}

function scenarioChartId(scenarioId) {
  return /(^|\/)(rl|rrt|planning)|boknafjorden|rogaland/i.test(scenarioId || '')
    ? 'Rogaland'
    : 'Romsdal';
}

function renderRuleGuide(snapshot) {
  const ruleId = snapshot.draft?.validation_rule_id || 'rule14';
  const sources = RULE_IMAGES[ruleId] || RULE_IMAGES.rule14;
  if (ruleId !== 'multiship') multishipRuleImageIndex = 0;
  const index = Math.min(multishipRuleImageIndex, sources.length - 1);
  const image = document.getElementById('validationRuleImage');
  const shownRule = ruleId === 'multiship' ? `rule${16 + index}` : ruleId;
  image.src = sources[index];
  image.alt = `${shownRule.toUpperCase()} reference illustration`;
  document.getElementById('validationRuleImageTitle').textContent = ruleId === 'multiship'
    ? `Multi-ship guide · Rule ${16 + index}`
    : `${ruleId.toUpperCase()} guide`;
  const controls = document.getElementById('validationRuleImageSwitch');
  controls.hidden = ruleId !== 'multiship';
  controls.querySelectorAll('button').forEach((button) => {
    button.classList.toggle('active', Number(button.dataset.ruleImageIndex) === index);
  });
}

function renderScenarioDetail(snapshot) {
  if (!snapshot.draft) return;
  const scenario = selectedCatalogItem(snapshot, 'scenarios', snapshot.draft.scenario_id);
  const chart = scenarioChartId(snapshot.draft.scenario_id);
  const enc = document.getElementById('validationEnc');
  enc.replaceChildren(new Option(`${chart} · derived reference`, chart.toLowerCase(), true, true));
  replaceDefinitionRows(document.getElementById('validationScenarioFacts'), [
    ['Scenario ID', snapshot.draft.scenario_id],
    ['Type', scenario?.type],
    ['Readiness', scenario?.readiness_grade],
    ['Ships', scenario?.ships],
    ['Catalog source', scenario?.provenance?.source || scenario?.source],
  ]);
  const image = document.getElementById('validationScenarioImage');
  image.hidden = chart !== 'Romsdal';
  document.getElementById('validationScenarioPreview').textContent = chart === 'Romsdal'
    ? `${scenario?.name || snapshot.draft.scenario_id} · catalog metadata paired with static Romsdal reference image. Live ENC remains in Deployment.`
    : `${scenario?.name || snapshot.draft.scenario_id} · no production reference image is bundled for ${chart}. Live ENC remains in Deployment.`;
}

function integrationFacts(item) {
  return [
    ['Readiness', item?.readiness_grade],
    ['Dependency', item?.dependency_available === true ? 'Available' : item?.dependency_available === false ? 'Unavailable' : null],
    ['Runtime', item?.runtime_ready === true ? 'Ready' : item?.runtime_ready === false ? 'Not ready' : null],
    ['Source', item?.source],
    ['Version', item?.version],
    ['Commit', item?.commit],
    ['Known failure', item?.known_failure || 'None reported by catalog'],
  ];
}

function renderMetadataFlow(id, item, role) {
  const element = document.getElementById(id);
  const stages = [
    `${item?.source || 'Registered integration'}`,
    item?.runtime_ready ? 'Runtime ready' : 'Runtime blocked',
    `${role} in Exact Tuple`,
  ];
  element.replaceChildren(...stages.flatMap((stage, index) => {
    const node = document.createElement('span');
    node.textContent = stage;
    if (index === stages.length - 1) return [node];
    const arrow = document.createElement('i');
    arrow.textContent = '→';
    return [node, arrow];
  }));
}

function renderAlgorithmDetail(snapshot) {
  if (!snapshot.draft) return;
  const draft = snapshot.draft;
  const algorithm = selectedCatalogItem(snapshot, 'algorithms', draft.algorithm_id);
  const tracker = selectedCatalogItem(snapshot, 'trackers', draft.tracker_id);
  document.getElementById('validationAlgorithmName').textContent = draft.algorithm_id;
  document.getElementById('validationTrackerName').textContent = draft.tracker_id;
  document.getElementById('validationTupleId').textContent = [
    draft.validation_rule_id,
    draft.scenario_id,
    draft.algorithm_id,
    draft.tracker_id,
  ].join(' / ');
  renderMetadataFlow('validationAlgorithmFlow', algorithm, 'Algorithm');
  renderMetadataFlow('validationTrackerFlow', tracker, 'Tracker');
  replaceDefinitionRows(document.getElementById('validationAlgorithmFacts'), integrationFacts(algorithm));
  replaceDefinitionRows(document.getElementById('validationTrackerFacts'), integrationFacts(tracker));
  const combinations = snapshot.classification === 'verified'
    ? snapshot.catalog?.verified_combinations
    : snapshot.catalog?.experimental_combinations;
  const exact = combinations?.find((item) => [
    item.validation_rule_id,
    item.scenario_id,
    item.algorithm_id,
    item.tracker_id,
  ].every((value, index) => value === [draft.validation_rule_id, draft.scenario_id, draft.algorithm_id, draft.tracker_id][index]));
  const evidence = exact?.latest_evidence;
  document.getElementById('validationEvidenceDetail').textContent = evidence
    ? `Latest catalog evidence · seed ${evidence.seed ?? 'not exposed'} · termination ${evidence.termination ?? 'not exposed'} · predicate ${exact.predicate_version || 'not exposed'}`
    : `${snapshot.classification} tuple · no latest_evidence payload exposed for this selection.`;
}

function renderExecutionPlan(snapshot) {
  if (!snapshot.draft) return;
  const draft = snapshot.draft;
  const scenario = selectedCatalogItem(snapshot, 'scenarios', draft.scenario_id);
  const dt = snapshot.executionPlan.dt.effective;
  const tEnd = snapshot.executionPlan.t_end.effective;
  const tStart = Number(scenario?.t_start ?? 0);
  const stepBudget = Number.isFinite(dt) && dt > 0 && Number.isFinite(tEnd)
    ? Math.max(0, Math.ceil((tEnd - tStart) / dt))
    : null;
  const metrics = [
    ['Duration', Number.isFinite(tEnd) ? `${tEnd - tStart} s` : 'Unknown'],
    ['Step', Number.isFinite(dt) ? `${dt} s` : 'Unknown'],
    ['Step budget', stepBudget ?? 'Unknown'],
    ['Initial state', 'CREATED'],
  ];
  document.getElementById('validationPlanMetrics').replaceChildren(...metrics.map(([label, value]) => {
    const card = document.createElement('article');
    const name = document.createElement('span');
    const output = document.createElement('strong');
    name.textContent = label;
    output.textContent = String(value);
    card.append(name, output);
    return card;
  }));
  replaceDefinitionRows(document.getElementById('validationExecutionPlan'), [
    ['Clock source', `dt ${snapshot.executionPlan.dt.source}; t_end ${snapshot.executionPlan.t_end.source}`],
    ['Seed', draft.seed],
    ['Episode', draft.episode_index],
    ['Evaluator', draft.evaluator_profile_id],
    ['Fallback', draft.strict_no_fallback ? 'Strict no-fallback' : 'Invalid policy'],
    ['Scenario override', draft.scenario_override ? 'Explicitly attached' : 'None'],
    ['Capability expectation', snapshot.classification],
    ['Algorithm config', Object.keys(draft.algorithm_config).length ? 'Opaque config preserved' : 'Empty'],
    ['Tracker config', Object.keys(draft.tracker_config).length ? 'Opaque config preserved' : 'Empty'],
  ]);
}

function renderStepper(snapshot) {
  const ready = Boolean(snapshot.draft) && snapshot.catalogStatus === 'ready' && snapshot.sessionStatus === 'known';
  document.getElementById('configStepRulesState').textContent = ready ? snapshot.draft.validation_rule_id : 'Loading';
  document.getElementById('configStepScenariosState').textContent = ready ? snapshot.draft.scenario_id : 'Loading';
  document.getElementById('configStepAlgorithmsState').textContent = ready
    ? `${snapshot.draft.algorithm_id} + ${snapshot.draft.tracker_id}`
    : 'Loading';
  document.getElementById('configStepParamsState').textContent = ready
    ? (snapshot.valid ? 'Valid' : 'Needs attention')
    : 'Loading';
  document.getElementById('configProgressLabel').textContent = ready ? '4 of 4 assembled' : 'Loading authority';
  document.getElementById('configProgressBar').style.width = ready ? '100%' : '18%';
}

function renderSummary(snapshot) {
  const summary = document.getElementById('validationSummary');
  summary.replaceChildren();
  if (!snapshot.draft) return;
  const rows = [
    ['Rule', snapshot.draft.validation_rule_id],
    ['Scenario', snapshot.draft.scenario_id],
    ['Algorithm', snapshot.draft.algorithm_id],
    ['Tracker', snapshot.draft.tracker_id],
    ['Evidence', snapshot.classification],
    ['Draft', snapshot.dirty ? 'Unsaved changes' : (snapshot.matchesActive ? 'Matches active session' : 'Default')],
  ];
  for (const [label, value] of rows) {
    const term = document.createElement('dt');
    term.textContent = label;
    const description = document.createElement('dd');
    description.textContent = value ?? '—';
    summary.append(term, description);
  }
}

function createStatusText(snapshot) {
  const labels = {
    'active-running': 'Active Session RUNNING · pause before Create',
    'matches-active': 'Matches active session',
    unavailable: 'Unavailable Exact Tuple',
    'invalid-draft': 'Invalid parameters',
    'experimental-confirmation': 'Experimental · confirmation required',
    creating: 'CREATING · immutable snapshot in flight',
    'runtime-pending': 'Active Session command in progress · controls frozen',
    'current-session-loading': 'Loading current-session authority…',
    'current-session-unknown': 'Current-session authority unknown · read-only',
  };
  if (snapshot.sessionStatus === 'loading' || snapshot.catalogStatus === 'error') {
    return snapshot.sessionStatus === 'loading'
      ? 'Loading capabilities and current session…'
      : 'Catalog unavailable · Active Spec read-only';
  }
  return labels[snapshot.createBlock] || (snapshot.dirty ? 'Unsaved changes' : 'Ready');
}

function render() {
  const snapshot = assembly.snapshot();
  const draft = snapshot.draft;
  document.getElementById('validationDraftState').textContent = createStatusText(snapshot);
  const retryAuthority = document.getElementById('retryCapabilityCatalog');
  retryAuthority.hidden = snapshot.sessionStatus === 'loading'
    || (snapshot.catalogStatus !== 'error' && snapshot.sessionStatus === 'known');
  retryAuthority.disabled = snapshot.sessionStatus === 'loading' || snapshot.creating;
  document.getElementById('shellSessionState').textContent = snapshot.activeState || 'NO SESSION';
  renderRuleChoices(snapshot);
  renderRuleGuide(snapshot);
  renderStepper(snapshot);

  if (draft) {
    populateSelect('validationScenario', snapshot.options.scenario_id || [], draft.scenario_id);
    populateSelect('validationAlgorithm', snapshot.options.algorithm_id || [], draft.algorithm_id);
    populateSelect('validationTracker', snapshot.options.tracker_id || [], draft.tracker_id);
    document.getElementById('validationSeed').value = String(draft.seed);
    document.getElementById('validationEpisode').value = String(draft.episode_index);
    document.getElementById('validationDt').value = draft.dt ?? '';
    document.getElementById('validationTEnd').value = draft.t_end ?? '';
    renderScenarioDetail(snapshot);
    renderAlgorithmDetail(snapshot);
    renderExecutionPlan(snapshot);
  }

  for (const id of ['validationScenario', 'validationAlgorithm', 'validationTracker', 'validationSeed', 'validationEpisode', 'validationDt', 'validationTEnd']) {
    document.getElementById(id).disabled = snapshot.readOnly || snapshot.creating;
  }
  const classification = document.getElementById('validationClassification');
  classification.className = `classification-card ${snapshot.classification}`;
  classification.textContent = snapshot.classification === 'verified'
    ? 'Verified Exact Tuple · normal Create'
    : snapshot.classification === 'experimental'
      ? 'Experimental Exact Tuple · amber confirmation required'
      : 'Unavailable · Create blocked';
  renderSummary(snapshot);
  document.getElementById('validationContract').textContent = draft ? JSON.stringify(draft, null, 2) : 'No catalog and no Active Run Specification.';
  const messages = [
    ...snapshot.notices.map((notice) => notice.message),
    ...Object.entries(snapshot.validationErrors).map(([field, message]) => `${field}: ${message}`),
  ];
  document.getElementById('validationNotices').replaceChildren(...messages.map((message) => {
    const item = document.createElement('div');
    item.textContent = message;
    return item;
  }));
  document.getElementById('validationDefault').disabled = snapshot.readOnly || snapshot.creating;
  const create = document.getElementById('validationCreate');
  create.textContent = snapshot.creating ? 'CREATING' : 'Create';
  create.classList.toggle('experimental', snapshot.classification === 'experimental');
  create.disabled = ![null, 'experimental-confirmation'].includes(snapshot.createBlock);
  create.title = createStatusText(snapshot);
}

function edit(field, value) {
  assembly.edit(field, value);
  render();
}

function bindControls() {
  document.querySelectorAll('[data-workface]').forEach((button) => {
    button.addEventListener('click', () => switchWorkface(button.dataset.workface));
  });
  document.querySelectorAll('[data-config-step]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-config-step]').forEach((item) => item.classList.toggle('active', item === button));
      document.querySelectorAll('[data-config-step-panel]').forEach((panel) => {
        panel.hidden = panel.dataset.configStepPanel !== button.dataset.configStep;
      });
    });
  });
  document.getElementById('validationRuleChoices').addEventListener('click', (event) => {
    const button = event.target.closest('[data-rule-id]');
    if (button && !button.disabled) edit('validation_rule_id', button.dataset.ruleId);
  });
  document.getElementById('validationRuleImageSwitch').addEventListener('click', (event) => {
    const button = event.target.closest('[data-rule-image-index]');
    if (!button) return;
    multishipRuleImageIndex = Number(button.dataset.ruleImageIndex);
    renderRuleGuide(assembly.snapshot());
  });
  document.getElementById('validationScenario').addEventListener('change', (event) => edit('scenario_id', event.target.value));
  document.getElementById('validationAlgorithm').addEventListener('change', (event) => edit('algorithm_id', event.target.value));
  document.getElementById('validationTracker').addEventListener('change', (event) => edit('tracker_id', event.target.value));
  const numeric = [
    ['validationSeed', 'seed', false],
    ['validationEpisode', 'episode_index', false],
    ['validationDt', 'dt', true],
    ['validationTEnd', 't_end', true],
  ];
  for (const [id, field, nullable] of numeric) {
    document.getElementById(id).addEventListener('change', (event) => {
      edit(field, nullable && event.target.value === '' ? null : Number(event.target.value));
    });
  }
  document.getElementById('validationDefault').addEventListener('click', () => {
    assembly.resetDefault();
    render();
  });
  document.getElementById('retryCapabilityCatalog').addEventListener('click', refreshValidationAuthority);
  document.getElementById('validationCreate').addEventListener('click', createSessionFromDraft);
}

function syncRuntimeAuthority(runtimeSnapshot, reason = 'runtime-sync') {
  const key = JSON.stringify([
    runtimeSnapshot.authority.status,
    runtimeSnapshot.session?.session_id || null,
    runtimeSnapshot.sessionState,
    runtimeSnapshot.session?.spec || null,
    runtimeSnapshot.pending?.command || null,
  ]);
  if (key === lastRuntimeSyncKey) return;
  lastRuntimeSyncKey = key;
  assembly.setRuntimePending(runtimeSnapshot.pending?.command || null);
  if (runtimeSnapshot.authority.status === 'known') {
    assembly.syncActiveSession(runtimeSnapshot.session, { reason });
  } else if (runtimeSnapshot.authority.status === 'loading') {
    assembly.markCurrentSessionLoading();
  } else if (runtimeSnapshot.authority.status === 'unknown') {
    assembly.markCurrentSessionUnknown(
      runtimeSnapshot.authority.error?.message || 'Active Session authority is unknown.',
    );
  }
  render();
}

async function refreshValidationAuthority() {
    const retry = document.getElementById('retryCapabilityCatalog');
    retry.disabled = true;
    const [catalogResult, currentResult] = await Promise.allSettled([
      fetchJson('/api/capabilities'),
      activeSessionRuntime.refreshAuthority(),
    ]);
    if (catalogResult.status === 'fulfilled') {
      assembly.replaceCatalog(catalogResult.value, { reason: 'authority-refresh' });
    } else {
      assembly.markCatalogFailure(catalogResult.reason);
    }
    if (currentResult.status === 'fulfilled') {
      syncRuntimeAuthority(currentResult.value, 'authority-refresh');
    } else {
      syncRuntimeAuthority(activeSessionRuntime.snapshot(), 'authority-refresh-failed');
    }
    retry.disabled = false;
    render();
}

async function createSessionFromDraft() {
  const before = assembly.snapshot();
  const confirmedExperimental = before.classification !== 'experimental'
    || window.confirm('Experimental Exact Tuple has no Verified Tuple evidence. Create this session?');
  if (!confirmedExperimental) return;
  let pending;
  try {
    pending = assembly.beginCreate({ confirmedExperimental });
  } catch (error) {
    document.getElementById('validationNotices').textContent = error.message;
    return;
  }
  render();
  try {
    await activeSessionRuntime.create(pending.spec);
    const session = activeSessionRuntime.snapshot().session;
    if (!assembly.resolveCreate(pending.token, session)) return;
    render();
    switchWorkface('deployment');
  } catch (error) {
    if (!assembly.rejectCreate(pending.token, error)) return;
    if (error.status === 422) {
      try {
        const refreshed = await fetchJson('/api/capabilities');
        assembly.replaceCatalog(refreshed, { reason: 'stale-capability-rejection' });
      } catch (catalogError) {
        assembly.markCatalogFailure(catalogError);
      }
    }
    render();
  }
}

async function bootConfig() {
  assembly = createValidationAssembly({
    catalog: null,
    currentSessionStatus: 'loading',
  });
  render();
  bindControls();
  activeSessionRuntime.subscribe((runtimeSnapshot) => syncRuntimeAuthority(runtimeSnapshot));
  loadOpenBridge();
  const [catalogResult, currentResult] = await Promise.allSettled([
    fetchJson('/api/capabilities'),
    activeSessionRuntime.bootstrap(),
  ]);
  if (catalogResult.status === 'fulfilled') {
    assembly.replaceCatalog(catalogResult.value, { reason: 'initial-load' });
  } else {
    assembly.markCatalogFailure(catalogResult.reason);
  }
  if (currentResult.status === 'fulfilled') {
    syncRuntimeAuthority(currentResult.value, 'initial-load');
  } else {
    syncRuntimeAuthority(activeSessionRuntime.snapshot(), 'initial-load-failed');
  }
  render();
}

bootConfig();
