import { createValidationAssembly } from './validation-assembly.js?v=20260818-candidate2-runtime-final';
import { activeSessionRuntime, telemetryProjection } from './session-runtime-instance.js?v=20260819-candidate3-projection';
import { createSituationDisplay } from './situation-display.js?v=20260819-c4-situation-2';

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
  // Config-interior components load best-effort from the same pin; native fallback
  // content keeps the workface usable when any of these requests fails.
  await Promise.allSettled([
    import(`${OPENBRIDGE_BASE}/components/elevated-card/elevated-card.js/+esm`),
    import(`${OPENBRIDGE_BASE}/components/icon-button/icon-button.js/+esm`),
    import(`${OPENBRIDGE_BASE}/components/number-input-field/number-input-field.js/+esm`),
    import(`${OPENBRIDGE_BASE}/components/scrollbar/scrollbar.js/+esm`),
    import(`${OPENBRIDGE_BASE}/components/button/button.js/+esm`),
    import(`${OPENBRIDGE_BASE}/components/clock/clock.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-chevron-left-google.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-chevron-right-google.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-alerts.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-sound-muted.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-settings-user-proposal.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-collision-avoidance-head-on.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-media-play.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-list-alt-check-google.js/+esm`),
    import(`${OPENBRIDGE_BASE}/icons/icon-router-component.js/+esm`),
  ]);
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

const CAROUSEL_CONFIGS = {
  scenario: { scrollbar: 'validationScenarioScrollbar', choices: 'validationScenarioChoices', controls: 'validationScenarioControls', previous: 'previousScenarioBtn', next: 'nextScenarioBtn' },
  enc: { scrollbar: 'validationEncScrollbar', choices: 'validationEncChoices', controls: 'validationEncControls', previous: 'previousEncBtn', next: 'nextEncBtn' },
  algorithm: { scrollbar: 'validationAlgorithmScrollbar', choices: 'validationAlgorithmChoices', controls: 'validationAlgorithmControls', previous: 'previousAlgorithmBtn', next: 'nextAlgorithmBtn' },
};

function carouselViewport(name) {
  const config = CAROUSEL_CONFIGS[name];
  const scrollbar = document.getElementById(config.scrollbar);
  if (!scrollbar) return null;
  return scrollbar.shadowRoot?.querySelector('.wrapper') || scrollbar;
}

function updateCarouselControls(name) {
  const config = CAROUSEL_CONFIGS[name];
  const viewport = carouselViewport(name);
  if (!viewport) return;
  const tolerance = 2;
  document.getElementById(config.previous).disabled = viewport.scrollLeft <= tolerance;
  document.getElementById(config.next).disabled = viewport.scrollLeft + viewport.clientWidth >= viewport.scrollWidth - tolerance;
}

function moveCarousel(name, direction) {
  const config = CAROUSEL_CONFIGS[name];
  const viewport = carouselViewport(name);
  const choices = document.getElementById(config.choices);
  const card = choices?.querySelector('.choice, .choice-card');
  if (!viewport || !card) return;
  const gap = parseFloat(getComputedStyle(choices).columnGap) || 0;
  viewport.scrollBy({ left: direction * (card.getBoundingClientRect().width + gap), behavior: 'smooth' });
  requestAnimationFrame(() => updateCarouselControls(name));
}

// The obc-scrollbar's real scroller is its shadow-DOM `.wrapper`; scroll events there
// do not bubble to the host, so listeners are bound on whichever viewport is live and
// re-bound after the custom element upgrades.
const boundViewports = new Map();
const viewportObservers = new WeakMap();

function bindCarouselScroll(name) {
  const viewport = carouselViewport(name);
  if (!viewport) return;
  if (boundViewports.get(name) === viewport) return;
  boundViewports.set(name, viewport);
  viewport.style.scrollSnapType = 'x mandatory';
  viewport.addEventListener('scroll', () => updateCarouselControls(name), { passive: true });
  // Hidden panels report clientWidth/scrollWidth of 0, so bounds measured at
  // bind time are meaningless; a ResizeObserver re-measures once layout exists
  // (panel shown, window resized).
  if (!viewportObservers.has(viewport)) {
    const observer = new ResizeObserver(() => updateCarouselControls(name));
    viewportObservers.set(viewport, observer);
    observer.observe(viewport);
  }
}

function rebindCarouselScrollers() {
  for (const name of Object.keys(CAROUSEL_CONFIGS)) bindCarouselScroll(name);
  for (const name of Object.keys(CAROUSEL_CONFIGS)) updateCarouselControls(name);
}

function renderChoiceCarousel(name, items, selectedId, locked) {
  const config = CAROUSEL_CONFIGS[name];
  const container = document.getElementById(config.choices);
  if (!container) return;
  container.replaceChildren(...items.map((item) => {
    const card = makeChoiceCard({
      id: item.id,
      name: optionLabel(item),
      desc: item.desc || `${item.readiness_grade || ''}`.trim(),
      grade: item.grade || item.readiness_grade || '',
      reason: item.incompatibility_reason || item.known_failure || '',
    }, {
      enabled: !locked && item.enabled !== false,
      selected: item.id === selectedId,
    });
    card.dataset.choiceId = item.id;
    return card;
  }));
  container.dataset.count = String(items.length);
  const controls = document.getElementById(config.controls);
  controls.hidden = items.length <= 2;
  requestAnimationFrame(() => updateCarouselControls(name));
}

function bindCarousel(name) {
  const config = CAROUSEL_CONFIGS[name];
  document.getElementById(config.previous).addEventListener('click', () => moveCarousel(name, -1));
  document.getElementById(config.next).addEventListener('click', () => moveCarousel(name, 1));
  bindCarouselScroll(name);
}

function elevatedCardAvailable() {
  return Boolean(customElements.get('obc-elevated-card'));
}

function renderNativeChoiceCard(item, { enabled, selected }) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'choice-card';
  button.dataset.choiceId = item.id;
  button.disabled = !enabled;
  button.setAttribute('role', 'radio');
  button.setAttribute('aria-checked', String(selected));
  button.setAttribute('aria-pressed', String(selected));
  if (item.reason && !enabled) button.title = item.reason;
  const title = document.createElement('strong');
  title.textContent = item.name;
  const detail = document.createElement('span');
  detail.textContent = item.desc;
  const grade = document.createElement('em');
  grade.textContent = item.grade || '';
  button.append(title, detail, grade);
  return button;
}

function makeChoiceCard(item, { enabled = true, selected = false } = {}) {
  if (!elevatedCardAvailable()) return renderNativeChoiceCard(item, { enabled, selected });
  const card = document.createElement('obc-elevated-card');
  card.className = 'choice';
  card.size = 'double-line';
  card.hasStatus = true;
  card.dataset.choiceId = item.id;
  card.disabled = !enabled;
  card.activated = selected;
  card.style.pointerEvents = enabled ? '' : 'none';
  card.style.opacity = enabled ? '' : '.56';
  card.setAttribute('aria-pressed', String(selected));
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', enabled ? '0' : '-1');
  card.setAttribute('aria-disabled', String(!enabled));
  if (item.reason && !enabled) card.title = item.reason;
  const label = document.createElement('span');
  label.className = 'choice-name';
  label.slot = 'label';
  label.textContent = item.name;
  const description = document.createElement('span');
  description.className = 'choice-description';
  description.slot = 'description';
  description.textContent = item.desc;
  const grade = document.createElement('span');
  grade.className = 'choice-grade';
  grade.slot = 'status';
  grade.textContent = item.grade || '';
  card.append(label, description, grade);
  card.addEventListener('click', (event) => {
    if (!enabled) event.stopImmediatePropagation();
  });
  card.addEventListener('keydown', (event) => {
    if (enabled && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      card.click();
    }
  });
  return card;
}

function renderRuleChoices(snapshot) {
  const container = document.getElementById('validationRuleChoices');
  const selected = snapshot.draft?.validation_rule_id;
  const visibleRules = new Set(['rule13', 'rule14', 'rule15', 'multiship']);
  container.replaceChildren(...(snapshot.options.validation_rule_id || []).filter((item) => visibleRules.has(item.id)).map((item) => {
    const card = makeChoiceCard({
      id: item.id,
      name: item.id.toUpperCase(),
      desc: `${item.readiness_grade || 'G0'} · ${item.enabled ? 'Selectable' : 'Unavailable'}`,
      grade: item.readiness_grade || 'G0',
      reason: item.incompatibility_reason || item.known_failure || '',
    }, {
      enabled: !snapshot.readOnly && !snapshot.creating && item.enabled,
      selected: item.id === selected,
    });
    card.dataset.ruleId = item.id;
    return card;
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
  controls.hidden = ruleId !== 'multiship' || sources.length <= 1;
  controls.replaceChildren(...[-1, 1].map((direction) => {
    const nextIndex = index + direction;
    const label = direction < 0 ? '查看上一条规则图片' : '查看下一条规则图片';
    let button;
    if (customElements.get('obc-icon-button')) {
      button = document.createElement('obc-icon-button');
      button.variant = 'normal';
      button.innerHTML = direction < 0
        ? '<obi-chevron-left-google></obi-chevron-left-google>'
        : '<obi-chevron-right-google></obi-chevron-right-google>';
    } else {
      button = document.createElement('button');
      button.type = 'button';
      button.textContent = direction < 0 ? '‹' : '›';
    }
    button.disabled = nextIndex < 0 || nextIndex >= sources.length;
    button.setAttribute('aria-label', label);
    button.title = label;
    button.dataset.ruleImageIndex = String(nextIndex);
    button.dataset.odId = direction < 0 ? 'previous-rule-guide-image' : 'next-rule-guide-image';
    return button;
  }));
}

function renderScenarioDetail(snapshot) {
  if (!snapshot.draft) return;
  const scenario = selectedCatalogItem(snapshot, 'scenarios', snapshot.draft.scenario_id);
  const chart = scenarioChartId(snapshot.draft.scenario_id);
  renderChoiceCarousel('scenario', snapshot.options.scenario_id || [], snapshot.draft.scenario_id, snapshot.readOnly || snapshot.creating);
  renderChoiceCarousel('enc', [{ id: chart.toLowerCase(), name: chart, desc: 'Derived reference', grade: 'ENC' }], chart.toLowerCase(), false);
  replaceDefinitionRows(document.getElementById('validationScenarioFacts'), [
    ['Scenario ID', snapshot.draft.scenario_id],
    ['Type', scenario?.type],
    ['Readiness', scenario?.readiness_grade],
    ['Ships', scenario?.ships],
    ['Catalog source', scenario?.provenance?.source || scenario?.source],
  ]);
  const image = document.getElementById('validationScenarioImage');
  const placeholder = document.getElementById('validationScenarioPlaceholder');
  image.hidden = chart !== 'Romsdal';
  placeholder.hidden = chart === 'Romsdal';
  if (chart !== 'Romsdal') {
    placeholder.replaceChildren();
    const title = document.createElement('strong');
    title.textContent = `${chart} ENC region`;
    const note = document.createElement('span');
    note.textContent = 'No bundled reference image for this region. Reference frame only — no geography is invented; live ENC remains in Deployment.';
    placeholder.append(title, note);
  }
  document.getElementById('validationScenarioPreview').textContent = chart === 'Romsdal'
    ? `${scenario?.name || snapshot.draft.scenario_id} · catalog metadata paired with static Romsdal reference image. Live ENC remains in Deployment.`
    : `${scenario?.name || snapshot.draft.scenario_id} · no production reference image is bundled for ${chart}. Live ENC remains in Deployment.`;
  renderScenarioPreviewCanvas(scenario);
}

// C4 ruling 1/9: the phantom catalog-geometry overlay path is deleted. The scenario
// preview is a second adapter on the situation-display canvas seam: static,
// ENC-less, no live telemetry, and no invented geometry — the frame renders
// the reference grid only. Visual contract (frame colors/labels) unchanged.
let scenarioPreviewDisplay = null;
function renderScenarioPreviewCanvas(scenario) {
  const canvas = document.getElementById('validationScenarioOverlayCanvas');
  if (!canvas) return;
  if (!scenarioPreviewDisplay) {
    scenarioPreviewDisplay = createSituationDisplay({
      canvas,
      wrapper: canvas.parentElement || canvas,
      // Static adapter: never fetches ENC assets or telemetry.
      fetchInfo: async () => ({ ready: false }),
      backgroundMode: 'transparent', // keep the reference image visible beneath
      loadSprites: false,             // no sprite network requests
      fetchTile: () => 'about:blank',
      getResponseRange: () => null,
      getScenarioId: () => null,
      getPlannerSurface: () => null,
      onEncStatus: () => {},
      onLog: () => {},
      onLayerStateChange: () => {},
      onSelectionChange: () => {},
    });
  }
  scenarioPreviewDisplay.render({
    run_id: `config-preview:${scenario?.id || 'none'}`,
    seq: 0,
    state: 'CREATED',
    os: null,
    obstacles: [],
    truth: [],
    tracks: [],
    measurements: [],
    plans: {},
    waypoints: null,
    encounters: [],
  });
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
  renderChoiceCarousel('algorithm', snapshot.options.algorithm_id || [], draft.algorithm_id, snapshot.readOnly || snapshot.creating);
  const trackerLocked = snapshot.readOnly || snapshot.creating;
  document.getElementById('validationTrackerChoices').replaceChildren(...(snapshot.options.tracker_id || []).map((item) => {
    const card = makeChoiceCard({
      id: item.id,
      name: optionLabel(item),
      desc: item.readiness_grade || '',
      grade: item.readiness_grade || '',
      reason: item.incompatibility_reason || item.known_failure || '',
    }, {
      enabled: !trackerLocked && item.enabled,
      selected: item.id === draft.tracker_id,
    });
    card.dataset.choiceId = item.id;
    return card;
  }));
  document.getElementById('validationAlgorithmName').textContent = optionLabel(algorithm || { id: draft.algorithm_id });
  document.getElementById('validationTrackerName').textContent = optionLabel(tracker || { id: draft.tracker_id });
  document.getElementById('validationAlgorithmGrade').textContent = `${algorithm?.readiness_grade || 'G0'} · ${algorithm?.runtime_ready === false ? 'BLOCKED' : 'AVAILABLE'}`;
  document.getElementById('validationTrackerGrade').textContent = `${tracker?.readiness_grade || 'G0'} · ${tracker?.runtime_ready === false ? 'BLOCKED' : 'AVAILABLE'}`;
  document.getElementById('validationAlgorithmSummary').textContent = algorithm?.known_failure
    ? `Known failure reported by catalog: ${algorithm.known_failure}`
    : 'Registered integration; no failure reported by the catalog.';
  document.getElementById('validationTrackerSummary').textContent = tracker?.known_failure
    ? `Known failure reported by catalog: ${tracker.known_failure}`
    : 'Registered integration; no failure reported by the catalog.';
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

const PARAM_FIELD_IDS = {
  seed: 'validationSeed',
  episode_index: 'validationEpisode',
  dt: 'validationDt',
  t_end: 'validationTEnd',
};

function setNumberFieldValue(id, value) {
  const field = document.getElementById(id);
  if (!field) return;
  const text = value ?? '';
  if (field.tagName === 'INPUT' || 'value' in field) field.value = String(text);
  else field.setAttribute('value', String(text));
}

function renderParamErrors(snapshot) {
  // Lazy-rebind hook: params render every pass, so any binding missed due to
  // upgrade timing (shadow input created after the last bind pass) is repaired
  // here; the WeakSet guard makes this a no-op once correctly bound.
  rebindNumberFields();
  for (const [name, id] of Object.entries(PARAM_FIELD_IDS)) {
    const message = snapshot.validationErrors?.[name] || '';
    const field = document.getElementById(id);
    if (!field) continue;
    const invalid = Boolean(message);
    if (field.tagName === 'OBC-NUMBER-INPUT-FIELD' && 'error' in field) {
      field.error = invalid;
      field.errorText = invalid ? message : '';
      field.classList.remove('field-error');
      field.removeAttribute('aria-invalid');
      field.title = '';
    } else {
      field.setAttribute('aria-invalid', String(invalid));
      field.classList.toggle('field-error', invalid);
      field.title = invalid ? message : '';
    }
  }
}

// Progressive fallback: if the CDN number-input component never defines, swap in
// native inputs with the same ids so the params step stays usable.
function ensureNumberFields() {
  if (customElements.get('obc-number-input-field')) return;
  for (const id of Object.values(PARAM_FIELD_IDS)) {
    const field = document.getElementById(id);
    if (!field || field.tagName !== 'OBC-NUMBER-INPUT-FIELD') continue;
    const input = document.createElement('input');
    input.type = 'number';
    input.min = '0';
    input.step = (id === 'validationSeed' || id === 'validationEpisode') ? '1' : 'any';
    input.id = id;
    if (field.hasAttribute('disabled')) input.disabled = true;
    field.replaceWith(input);
  }
  rebindNumberFields();
}

const NUMERIC_PARAMS = [
  ['validationSeed', 'seed', false],
  ['validationEpisode', 'episode_index', false],
  ['validationDt', 'dt', true],
  ['validationTEnd', 't_end', true],
];
const lastParamCommit = new Map();
const boundNumberTargets = new WeakSet();

function commitParamEdit(field, nullable, event) {
  // Read from the event target itself: the host element's value property can be
  // stale when the keystroke happened inside the component's shadow input.
  const value = String(event.target.value ?? '');
  const committed = nullable && value === '' ? null : Number(value);
  if (lastParamCommit.get(field) === String(committed)) return;
  lastParamCommit.set(field, String(committed));
  edit(field, committed);
}

// obc-number-input-field@1.0.1 only updates this.value from an internal @input
// handler and emits no `change`; worse, shadow-origin input events do not reliably
// bubble/retarget to light-DOM listeners in every environment. So — same pattern
// as the carousel scroller rebind — listeners are bound DIRECTLY on the inner
// shadow input once the component upgrades. Without a shadowRoot (component
// failed / native fallback input) the host element itself is the target.
function bindNumberField(id, field, nullable) {
  const element = document.getElementById(id);
  if (!element) return;
  const target = element.shadowRoot?.querySelector('input') || element;
  if (boundNumberTargets.has(target)) return;
  boundNumberTargets.add(target);
  target.addEventListener('input', (event) => commitParamEdit(field, nullable, event));
  target.addEventListener('change', (event) => commitParamEdit(field, nullable, event));
}

function rebindNumberFields() {
  for (const [id, field, nullable] of NUMERIC_PARAMS) bindNumberField(id, field, nullable);
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
  document.getElementById('validationTimelineStart').textContent = Number.isFinite(tStart) ? `${tStart} s` : '--';
  document.getElementById('validationTimelineEnd').textContent = Number.isFinite(tEnd) ? `${tEnd} s` : '--';
  document.getElementById('validationSeedRoot').textContent = Number.isInteger(draft.seed) && draft.seed >= 0 ? String(draft.seed) : '--';
  // No derived seed-stream values are exposed client-side; the stream grid stays
  // omitted rather than populated with invented values (same ruling as gap #17).
  document.getElementById('validationSeedStreams').hidden = true;
  const planState = document.getElementById('validationPlanState');
  planState.textContent = snapshot.valid ? 'READY' : 'INVALID';
  planState.dataset.valid = String(snapshot.valid);
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
  const stepStates = [
    ['rules', ready && Boolean(snapshot.draft.validation_rule_id), ready ? snapshot.draft.validation_rule_id : 'Loading'],
    ['scenarios', ready && Boolean(snapshot.draft.scenario_id), ready ? snapshot.draft.scenario_id : 'Loading'],
    ['algorithms', ready && Boolean(snapshot.draft.algorithm_id) && Boolean(snapshot.draft.tracker_id), ready
      ? `${snapshot.draft.algorithm_id} + ${snapshot.draft.tracker_id}`
      : 'Loading'],
    ['params', ready && snapshot.valid, ready ? (snapshot.valid ? 'Valid' : 'Needs attention') : 'Loading'],
  ];
  for (const [step, complete, label] of stepStates) {
    const button = document.querySelector(`.assembly-step[data-config-step="${step}"]`);
    if (!button) continue;
    button.dataset.complete = String(complete);
    document.getElementById(`configStep${step.charAt(0).toUpperCase()}${step.slice(1)}State`).textContent = label;
  }
  const readyCount = stepStates.filter(([, complete]) => complete).length;
  document.getElementById('configProgressLabel').textContent = ready ? `${readyCount} of 4 ready` : 'Loading authority';
  document.getElementById('configProgressBar').style.width = `${readyCount * 25}%`;
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
    setNumberFieldValue('validationSeed', draft.seed);
    setNumberFieldValue('validationEpisode', draft.episode_index);
    setNumberFieldValue('validationDt', draft.dt ?? '');
    setNumberFieldValue('validationTEnd', draft.t_end ?? '');
    renderScenarioDetail(snapshot);
    renderAlgorithmDetail(snapshot);
    renderExecutionPlan(snapshot);
  }
  renderParamErrors(snapshot);

  for (const id of Object.values(PARAM_FIELD_IDS)) {
    const field = document.getElementById(id);
    if (field) field.disabled = snapshot.readOnly || snapshot.creating;
  }
  const classification = document.getElementById('validationClassification');
  classification.className = `classification-card ${snapshot.classification}`;
  classification.textContent = snapshot.classification === 'verified'
    ? 'Verified Exact Tuple · normal Create'
    : snapshot.classification === 'experimental'
      ? 'Experimental Exact Tuple · amber confirmation required'
      : 'Unavailable · Create blocked';
  renderSummary(snapshot);
  const assemblyStatus = document.getElementById('validationAssemblyStatus');
  const cleanMatch = !snapshot.dirty && snapshot.matchesActive && !snapshot.creating;
  assemblyStatus.textContent = snapshot.valid ? (cleanMatch ? 'CREATED' : 'READY') : 'DRAFT';
  assemblyStatus.dataset.ready = String(snapshot.valid);
  assemblyStatus.dataset.created = String(cleanMatch);
  document.getElementById('validationContract').textContent = draft ? JSON.stringify(draft, null, 2) : 'No catalog and no Active Run Specification.';
  const messages = snapshot.notices.map((notice) => notice.message);
  document.getElementById('validationNotices').replaceChildren(...messages.map((message) => {
    const item = document.createElement('div');
    item.textContent = message;
    return item;
  }));
  document.getElementById('validationDefault').disabled = snapshot.readOnly || snapshot.creating;
  const create = document.getElementById('validationCreate');
  create.dataset.mode = cleanMatch ? 'open-deployment' : 'create';
  create.textContent = snapshot.creating ? 'CREATING' : (cleanMatch ? 'Open Deployment' : 'Create');
  create.classList.toggle('experimental', snapshot.classification === 'experimental' && !cleanMatch);
  create.disabled = cleanMatch
    ? snapshot.readOnly
    : ![null, 'experimental-confirmation'].includes(snapshot.createBlock);
  create.title = cleanMatch ? 'Draft matches the active session · jump to Deployment' : createStatusText(snapshot);
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
      document.querySelectorAll('[data-config-step]').forEach((item) => {
        const selected = item === button;
        item.classList.toggle('active', selected);
        item.setAttribute('aria-pressed', String(selected));
      });
      document.querySelectorAll('[data-config-step-panel]').forEach((panel) => {
        panel.hidden = panel.dataset.configStepPanel !== button.dataset.configStep;
      });
      // Carousel bounds measured while a panel was hidden are 0-width; re-measure
      // after the newly visible panel has laid out.
      requestAnimationFrame(() => rebindCarouselScrollers());
    });
  });
  document.getElementById('validationRuleChoices').addEventListener('click', (event) => {
    const button = event.target.closest('[data-rule-id]');
    if (button && !button.disabled) edit('validation_rule_id', button.dataset.ruleId);
  });
  document.getElementById('validationRuleImageSwitch').addEventListener('click', (event) => {
    const button = event.target.closest('[data-rule-image-index]');
    if (!button || button.disabled) return;
    multishipRuleImageIndex = Number(button.dataset.ruleImageIndex);
    renderRuleGuide(assembly.snapshot());
  });
  bindCarousel('scenario');
  bindCarousel('enc');
  bindCarousel('algorithm');
  document.getElementById('validationScenarioChoices').addEventListener('click', (event) => {
    const card = event.target.closest('[data-choice-id]');
    if (!card || card.disabled) return;
    edit('scenario_id', card.dataset.choiceId);
  });
  document.getElementById('validationAlgorithmChoices').addEventListener('click', (event) => {
    const card = event.target.closest('[data-choice-id]');
    if (!card || card.disabled) return;
    edit('algorithm_id', card.dataset.choiceId);
  });
  document.getElementById('validationTrackerChoices').addEventListener('click', (event) => {
    const card = event.target.closest('[data-choice-id]');
    if (!card || card.disabled) return;
    edit('tracker_id', card.dataset.choiceId);
  });
  rebindNumberFields();
  document.getElementById('validationDefault').addEventListener('click', () => {
    assembly.resetDefault();
    render();
  });
  document.getElementById('retryCapabilityCatalog').addEventListener('click', refreshValidationAuthority);
  document.getElementById('validationCreate').addEventListener('click', () => {
    if (document.getElementById('validationCreate').dataset.mode === 'open-deployment') {
      switchWorkface('deployment');
      return;
    }
    createSessionFromDraft();
  });
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
  loadOpenBridge().then(() => {
    ensureNumberFields();
    render();
  });
  customElements.whenDefined('obc-scrollbar').then(rebindCarouselScrollers);
  // whenDefined resolves at DEFINITION time, which can precede Lit's first render —
  // the shadow <input> may not exist yet on either bind pass. Chain past the first
  // render (rAF + task) so the direct binding lands on the real inner input.
  customElements.whenDefined('obc-number-input-field').then(() => {
    requestAnimationFrame(() => setTimeout(rebindNumberFields, 0));
  });
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
