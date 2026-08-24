import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const configCss = styles.slice(styles.indexOf('.workface {'), styles.indexOf('.roadmap-workface {'));
const legacy = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const runtime = await readFile(new URL('../../web_gui/modules/active-session-runtime.js', import.meta.url), 'utf8');
const instance = await readFile(new URL('../../web_gui/modules/session-runtime-instance.js', import.meta.url), 'utf8');
const projection = await readFile(new URL('../../web_gui/modules/telemetry-projection.js', import.meta.url), 'utf8');
const ruleGuides = await Promise.all([
  'Rule13-guide.svg',
  'Rule14-guide.svg',
  'Rule15-guide.svg',
  'Multiship-guide.svg',
].map((name) => readFile(new URL(`../../web_gui/assets/openbridge/${name}`, import.meta.url), 'utf8')));

test('Config starts disabled and boot establishes assembly before binding controls', () => {
  for (const id of [
    'validationSeed',
    'validationEpisode',
    'validationDt',
    'validationTEnd',
    'validationDefault',
    'validationCreate',
  ]) {
    assert.match(html, new RegExp(`id="${id}"[^>]*disabled`));
  }
  const boot = shell.slice(shell.indexOf('async function bootConfig()'));
  assert.ok(boot.indexOf('assembly = createValidationAssembly') < boot.indexOf('bindControls();'));
});

test('only Active Session Runtime owns lifecycle REST and WebSocket construction', () => {
  for (const consumer of [legacy, shell]) {
    assert.doesNotMatch(consumer, /\/api\/sessions\/current|\/api\/sessions\b[^\n]*(?:\/start|\/pause|\/step|\/reset|\/replay|\/speed|\/result|\/artifacts)/);
    assert.doesNotMatch(consumer, /(?:fetchJson|apiRequest)\(['"]\/api\/sessions['"]/);
    assert.doesNotMatch(consumer, /new WebSocket/);
    assert.doesNotMatch(consumer, /activeSessionId|sessionRecoveryPending|validation-session-/);
  }
  assert.match(runtime, /\/api\/sessions/);
  assert.match(instance, /new WebSocket/);
});

test('Config and Deployment import the same inert singleton and app is delivered as ESM', () => {
  const legacyImport = legacy.match(/import \{ activeSessionRuntime, telemetryProjection \} from ['"]\.\/modules\/session-runtime-instance\.js(\?v=[^'"]*)?['"]/);
  const shellImport = shell.match(/import \{ activeSessionRuntime, telemetryProjection \} from ['"]\.\/session-runtime-instance\.js(\?v=[^'"]*)?['"]/);
  const runtimeImport = instance.match(/import \{ createActiveSessionRuntime \} from ['"]\.\/active-session-runtime\.js(\?v=[^'"]*)?['"]/);
  assert.ok(legacyImport, 'Deployment imports the runtime and projection singletons');
  assert.ok(shellImport, 'Config imports the runtime and projection singletons');
  assert.ok(legacyImport[1], 'Deployment singleton import carries a cache-bust token');
  assert.equal(legacyImport[1], shellImport[1], 'singleton specifiers must be byte-identical or the module splits');
  assert.ok(runtimeImport?.[1], 'instance import of the runtime carries a cache-bust token');
  assert.match(instance, /export const activeSessionRuntime = createActiveSessionRuntime/);
  assert.doesNotMatch(instance, /\.bootstrap\(/);
  assert.match(html, /<script type="module" src="\/static\/app\.js/);
});

test('composition root wires the runtime into the projection singleton and exports both', () => {
  assert.match(instance, /export const telemetryProjection = createTelemetryProjection\(\)/);
  assert.match(instance, /activeSessionRuntime\.subscribe\(\(runtimeSnapshot\) => telemetryProjection\.project\(runtimeSnapshot\)\)/);
  assert.match(instance, /import \{ createTelemetryProjection \} from ['"]\.\/telemetry-projection\.js\?v=/);
});

test('Deployment consumes the projection and no longer interprets raw envelopes inline', () => {
  assert.match(legacy, /telemetryProjection\.subscribe\(renderProjection\)/);
  assert.doesNotMatch(legacy, /latest_planner_solve/);
  assert.doesNotMatch(legacy, /data\.navigation_area/);
  assert.doesNotMatch(legacy, /safe_water_polygons/);
  assert.doesNotMatch(legacy, /threat_level/);
  assert.doesNotMatch(legacy, /drawCPARisk/);
  assert.doesNotMatch(legacy, /checkLogEvents/);
  assert.doesNotMatch(legacy, /route_corridor_half_width_m/);
});

test('telemetry projection stays DOM-free and transport-free', () => {
  assert.doesNotMatch(projection, /fetch\(|new WebSocket|document\.|window\./);
  assert.match(projection, /export function createTelemetryProjection/);
  assert.match(projection, /export const DCPA_SAFE = 300/);
  assert.match(projection, /export const DCPA_WARN = 100/);
});

test('Deployment treats the shared envelope as read-only and never mutates it in place', () => {
  assert.doesNotMatch(legacy, /currentData\.\w+\s*=[^=]/);
});

test('Config delegates Create and authority refresh through runtime public seam', () => {
  assert.match(shell, /activeSessionRuntime\.create\(pending\.spec\)/);
  assert.match(shell, /activeSessionRuntime\.refreshAuthority\(\)/);
  assert.match(shell, /activeSessionRuntime\.subscribe/);
  assert.match(shell, /assembly\.markCurrentSessionLoading\(\)/);
  assert.match(shell, /assembly\.markCurrentSessionUnknown\(/);
  assert.match(shell, /assembly\.setRuntimePending\(runtimeSnapshot\.pending\?\.command \|\| null\)/);
});

test('legacy Deployment configuration is hidden and cannot imply it applies to Validation Draft', () => {
  assert.match(legacy, /LEGACY_CONFIG_CARD_IDS/);
  assert.match(legacy, /Configuration moved to Config/);
  assert.doesNotMatch(legacy, /Create from Config to apply it/);
  assert.match(legacy, /Validation Assembly .*sole capability\/catalog and.*bootstrap authority/s);
});

test('ENC loading is replacement-bound and stale fetch/image callbacks are inert', async () => {
  // C4: the situation canvas (incl. ENC loading) moved from app.js into the
  // situation-display module; the guards live there now.
  const situation = legacy.match(/from ['"]\.\/modules\/situation-display\.js\?v=/)
    ? await readFile(new URL('../../web_gui/modules/situation-display.js', import.meta.url), 'utf8')
    : legacy;
  assert.match(situation, /encLoadGeneration/);
  assert.match(situation, /encInfoController\.abort\(\)/);
  assert.match(situation, /info\.run_id !== sessionId/);
  assert.match(situation, /generation !== encLoadGeneration \|\| sessionId !== currentRunId\(\)/);
  assert.match(situation, /encPendingImage\.onload = null/);
  assert.match(situation, /encRetryTimer/);
});

test('Config token layer ports the OpenBridge palette sheet (gap #3 part)', () => {
  for (const token of [
    '--ob-app-bg: var(--container-section-color',
    '--ob-surface: var(--normal-enabled-background-color',
    '--ob-text: var(--element-active-color',
    '--ob-muted: var(--element-neutral-color',
    '--ob-border: var(--border-divider-color',
    '--ob-accent: var(--instrument-enhanced-secondary-color',
    '--ob-accent-soft: color-mix(in srgb, var(--ob-accent) 22%, var(--ob-surface))',
    '--ob-accent-pale: color-mix(in srgb, var(--ob-accent) 12%, var(--ob-surface))',
    '--ob-danger: var(--alert-alarm-color',
    '--s-1: 4px',
    '--s-6: 32px',
    '--radius: 6px',
    '--shadow: 0 1px 2px var(--ob-overlay-strong)',
  ]) {
    assert.ok(styles.includes(token), `style.css must define OpenBridge token ${token.split(':')[0]}`);
  }
  // P:305-311 base: borderless 3-column grid on the app background; user ruling
  // 2026-08-19: side rails share one width (236px) instead of 236/clamp(344-392).
  assert.match(styles, /\.config-workface[^{]*\{[^}]*grid-template-columns: 236px minmax\(0, 1fr\) 236px;[^}]*background: var\(--ob-app-bg\)/);
  // C5 ruling 5: focus-visible promoted to a global rule (was .config-workface-scoped).
  assert.match(styles, /:focus-visible \{ outline: 3px solid var\(--ob-accent-mid\); outline-offset: 2px; \}/);
  assert.match(styles, /prefers-reduced-motion: reduce/);
});

test('Config-scope selectors consume tokens instead of hardcoded hex (gap #3 part)', () => {
  assert.ok(configCss.length > 4000, 'Config CSS slice extracted');
  const hexColors = configCss.match(/#[0-9a-fA-F]{3,8}\b/g) || [];
  assert.deepEqual(hexColors, [], `Config CSS must not hardcode hex colors, found: ${hexColors.join(', ')}`);
  assert.match(configCss, /\.choice-card\[aria-checked="true"\] \{[^}]*border: 2px solid var\(--ob-accent-mid\);[^}]*background: var\(--ob-accent-pale\)/);
  // P:359-366 card chrome owned by the shell (plain sections): obc-card's shadow
  // DOM centers its title slot and shrinks centered content, so cards style themselves.
  assert.match(configCss, /\.config-obc-card \{[^}]*border: 1px solid color-mix\(in srgb, var\(--ob-text\) 26%, transparent\);[^}]*background: var\(--ob-work-bg\)/);
});

test('Stepper chrome shows circular numbers, completion dots, and 25%-per-ready-step progress (gap #19)', () => {
  for (const step of ['rules', 'scenarios', 'algorithms', 'params']) {
    assert.match(html, new RegExp(`data-config-step="${step}"[^>]*data-complete="(?:true|false)"`));
    assert.match(html, new RegExp(`data-config-step="${step}"[^>]*aria-pressed="(?:true|false)"`));
    assert.doesNotMatch(html, new RegExp(`data-config-step="${step}"[^>]*aria-selected`));
  }
  assert.match(html, /class="step-circle"/);
  assert.match(html, /class="step-state-dot"/);
  assert.match(shell, /readyCount \* 25/);
  assert.match(shell, /of 4 ready/);
  assert.match(shell, /dataset\.complete = String\(complete\)/);
  assert.match(configCss, /\.assembly-step\.active \{[^}]*box-shadow: inset 3px 0 0 var\(--ob-accent\)/);
  assert.match(configCss, /\.step-circle \{[^}]*border-radius: 50%/);
  assert.match(configCss, /\.assembly-step\[data-complete="true"\] \.step-state-dot \{[^}]*background: var\(--ob-accent\)/);
});

test('Stepper and Config Summary render tuple business labels instead of raw ids', () => {
  for (const [id, label] of [
    ['overtaking', 'Overtaking'],
    ['head_on', 'Head-on'],
    ['crossing_give_way', 'Give-way'],
    ['crossing_stand_on', 'Stand-on'],
  ]) {
    assert.match(shell, new RegExp(`${id}: '${label}'`));
  }
  for (const helper of ['ruleDisplayLabel', 'scenarioDisplayLabel', 'algorithmDisplayLabel', 'trackerDisplayLabel']) {
    assert.match(shell, new RegExp(`function ${helper}\\(snapshot\\)`));
  }
  assert.match(shell, /rule13: 'Rule 13 Overtaking'/);
  assert.match(shell, /rule14: 'Rule 14 Head-on'/);
  assert.match(shell, /mid_mpc_ipopt: 'Mid-MPC'/);
  assert.match(shell, /god: 'Truth'/);
  const stepper = shell.slice(shell.indexOf('function renderStepper('), shell.indexOf('function renderSummary('));
  const summary = shell.slice(shell.indexOf('function renderSummary('), shell.indexOf('function createStatusText('));
  for (const helper of ['ruleDisplayLabel', 'scenarioDisplayLabel', 'algorithmDisplayLabel', 'trackerDisplayLabel']) {
    assert.match(stepper, new RegExp(`${helper}\\(snapshot\\)`));
    assert.match(summary, new RegExp(`${helper}\\(snapshot\\)`));
  }
});

test('COLREGS naming is consistent across step, card, and summary', () => {
  assert.match(html, /data-config-step="rules"[^>]*>[\s\S]*?<strong>COLREGS<\/strong>/);
  assert.match(html, /class="config-card-title"[^>]*>[\s\S]*?<strong>COLREGS<\/strong>/);
  assert.match(shell, /\['COLREGS', ruleDisplayLabel\(snapshot\)\]/);
  assert.doesNotMatch(html, /COLREG Rules/);
});

test('Config Contract renders YAML semantics without key-value color coding', () => {
  assert.match(html, /id="validationContract"[^>]*aria-label="YAML Config Contract"/);
  assert.match(shell, /function renderYamlContract\(draft\)/);
  assert.match(shell, /className = 'yaml-key'/);
  assert.match(shell, /className = 'yaml-value'/);
  assert.match(shell, /JSON\.stringify\(value\)/);
  assert.match(configCss, /\.yaml-key,[\s\S]*?\.yaml-value \{[^}]*color: inherit/);
});

test('Inspector has assembly-status pill, compact-header sections, and obc-button actions (gap #18; 32px ruling 2026-08-19: 236px rail must fit without inner scroll)', () => {
  assert.match(html, /id="validationAssemblyStatus"/);
  assert.match(html, /class="assembly-card-content"/);
  assert.match(html, /<section class="assembly-section">/);
  assert.match(html, /<obc-button id="validationDefault"/);
  assert.match(html, /<obc-button[^>]*id="validationCreate"/);
  assert.match(configCss, /\.assembly-section > h2 \{[^}]*min-height: 32px/);
  assert.match(configCss, /\.assembly-status \{[^}]*border-radius: 999px/);
  assert.match(shell, /validationAssemblyStatus/);
});

test('Create swaps to Open jump when draft is clean and matches the active session (gap #20)', () => {
  assert.match(shell, /dataset\.mode = cleanMatch/);
  assert.match(shell, /cleanMatch \? 'Open' : 'Create'/);
  assert.match(shell, /mode === 'open-deployment'/);
  assert.match(shell, /switchWorkface\('deployment'\)/);
});

test('Rule choices render as OpenBridge elevated cards in a 4-column grid (gap #10)', () => {
  assert.match(shell, /vendor\/openbridge\/openbridge-components\.mjs/);
  assert.match(shell, /function makeChoiceCard\(/);
  assert.match(shell, /obc-elevated-card/);
  assert.match(shell, /setAttribute\('aria-pressed', String\(selected\)\)/);
  assert.match(shell, /opacity = enabled \? '' : '\.56'/);
  assert.match(shell, /event\.key === 'Enter' \|\| event\.key === ' '/);
  assert.match(shell, /renderNativeChoiceCard\(/);
  assert.match(configCss, /#validationRuleChoices \{[^}]*grid-template-columns: repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(configCss, /\.choice\[aria-pressed="true"\]::part\(wrapper\) \{[^}]*outline: 3px solid var\(--ob-accent\); outline-offset: -3px/);
});

test('Rule guide uses floating prev/next icon buttons over the media (gap #21)', () => {
  assert.match(configCss, /\.rule-guide-actions \{[^}]*position: absolute/);
  assert.match(html, /class="rule-guide-actions"/);
  assert.match(shell, /obi-chevron-left-google/);
  assert.match(shell, /obi-chevron-right-google/);
  assert.match(shell, /查看上一条规则图片|previous-rule-guide-image/);
});

test('four rule choices use one consistent vector guide system', () => {
  for (const name of ['Rule13', 'Rule14', 'Rule15', 'Multiship']) {
    assert.match(shell, new RegExp(`${name}-guide\\.svg\\?v=20260821-guide-3`));
  }
  assert.doesNotMatch(shell.slice(shell.indexOf('const RULE_IMAGES'), shell.indexOf('let assembly')), /Rule1[3-7]\.png/);
  for (const svg of ruleGuides) {
    assert.match(svg, /width="1600" height="1000" viewBox="0 0 1600 1000"/);
    assert.match(svg, /Noto Sans SC/);
    assert.match(svg, /避碰操作流程 · 从识别到恢复/);
    assert.match(svg, /统一评估基线/);
  }
});

test('Scenario and ENC selection render as horizontal snap carousels (gap #11)', () => {
  for (const id of [
    'validationScenarioScrollbar',
    'validationScenarioChoices',
    'validationScenarioControls',
    'previousScenarioBtn',
    'nextScenarioBtn',
    'validationEncScrollbar',
    'validationEncChoices',
    'previousEncBtn',
    'nextEncBtn',
  ]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(shell, /function updateCarouselControls\(/);
  assert.match(shell, /scrollLeft <= tolerance/);
  assert.match(shell, /scrollLeft \+ viewport\.clientWidth >= viewport\.scrollWidth - tolerance/);
  assert.match(shell, /function moveCarousel\(/);
  assert.match(configCss, /grid-auto-columns: calc\(\(100% - var\(--s-2\)\) \/ 2\)/);
  assert.match(configCss, /scroll-snap-align: start/);
  assert.match(shell, /incompatibility_reason \|\| item\.known_failure/);
});

test('Scenario preview draws through the situation-display canvas seam; the phantom overlay_geometry path is gone (C4 rulings 1/9)', () => {
  assert.match(html, /id="validationScenarioOverlayCanvas"/);
  assert.doesNotMatch(html, /validationScenarioOverlay"/);
  assert.doesNotMatch(html, /validationScenarioMarkers/);
  assert.match(shell, /createSituationDisplay/);
  assert.match(shell, /renderScenarioPreviewCanvas\(/);
  assert.doesNotMatch(shell, /overlay_geometry/);
  assert.doesNotMatch(shell, /renderScenarioOverlay/);
  assert.doesNotMatch(shell, /route-corridor|route-centerline|route-boundary/);
  assert.match(configCss, /\.scenario-preview-canvas \{/);
});

test('Rogaland scenarios get a styled placeholder frame instead of a hidden image (gap #12a)', () => {
  assert.match(html, /id="validationScenarioPlaceholder"/);
  assert.match(configCss, /\.scenario-placeholder \{[^}]*border: 1px dashed var\(--ob-border\)/);
  assert.match(shell, /validationScenarioPlaceholder/);
});

test('Algorithm selection is a carousel and tracker a 2-column choice grid (gap #13)', () => {
  for (const id of [
    'validationAlgorithmScrollbar',
    'validationAlgorithmChoices',
    'validationAlgorithmControls',
    'previousAlgorithmBtn',
    'nextAlgorithmBtn',
    'validationTrackerChoices',
  ]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(shell, /renderChoiceCarousel\('algorithm'/);
  assert.match(shell, /validationTrackerChoices/);
  assert.match(configCss, /\.tracker-choice-grid \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
});

test('production Config takes ordered algorithm and tracker choices only from product policy projection', () => {
  assert.doesNotMatch(shell, /ALGORITHM_ORDER|TRACKER_ORDER/);
  assert.match(shell, /snapshot\.options\.algorithm_id/);
  assert.match(shell, /snapshot\.options\.tracker_id/);
  assert.match(shell, /snapshot\.productCapabilityPolicy/);
  assert.match(shell, /potocnik_colreg_fan_mpc: 'Fan-MPC'/);
  assert.match(shell, /god: 'Truth'/);
  assert.doesNotMatch(shell, /potocnik_simplified_mpc/);
  assert.doesNotMatch(shell, /\bnominal\b/);
  assert.doesNotMatch(shell, /\bsbmpc\b/);
  assert.doesNotMatch(shell, /\bkf\b/);
});

test('Create constraint rendering consumes typed policy projection without algorithm-specific requirement hardcodes', () => {
  assert.match(shell, /snapshot\.createConstraint/);
  assert.match(shell, /snapshot\.createBlockReason/);
  assert.match(shell, /create\.disabled =/);
  assert.match(shell, /create\.title = .*createStatusText\(snapshot\)/);
  assert.doesNotMatch(shell, /requires-qualified-ship-domain-profile/);
  assert.doesNotMatch(shell, /requires a qualified ShipDomainProfile/);
  assert.doesNotMatch(shell, /fallback.*Mid-MPC|Mid-MPC.*fallback/i);
});

test('Algorithm detail chrome: role eyebrow, grade pill, 20px heading, binding footer (gap #14)', () => {
  assert.match(html, /class="algorithm-detail-eyebrow"/);
  assert.match(html, /id="validationAlgorithmGrade"/);
  assert.match(html, /id="validationTrackerGrade"/);
  assert.doesNotMatch(html, /algorithm-binding/);
  assert.doesNotMatch(html, /id="validationClassification"/);
  assert.doesNotMatch(html, /id="validationEvidenceDetail"/);
  assert.match(configCss, /\.algorithm-detail-grade \{[^}]*border-radius: 999px/);
  assert.match(configCss, /\.algorithm-detail-header h2 \{[^}]*font-size: 20px/);
  assert.match(shell, /readiness_grade/);
  assert.match(shell, /renderMetadataFlow\('validationAlgorithmFlow'/);
});

test('Params use obc-number-input-field with inline field errors and retained notices (gap #15)', () => {
  for (const id of ['validationSeed', 'validationEpisode', 'validationDt', 'validationTEnd']) {
    assert.match(html, new RegExp(`<obc-number-input-field id="${id}"`));
  }
  assert.match(shell, /field\.error = invalid/);
  assert.match(shell, /field\.errorText = invalid \? message : ''/);
  assert.match(shell, /ensureNumberFields/);
  // User ruling 2026-08-19: only *-error notices render in the inspector rail;
  // informational notices (repair/config-cleared/catalog-refreshed) stay silent.
  assert.match(shell, /notices[\s\S]{0,120}filter\(\(notice\) => typeof notice\.kind === 'string' && notice\.kind\.endsWith\('-error'\)\)/);
  assert.match(shell, /\.map\(\(notice\) => notice\.message\)/);
  assert.doesNotMatch(shell, /Object\.entries\(snapshot\.validationErrors\)\.map/);
  assert.match(html, /id="validationNotices"/);
});

test('Execution plan has metric strip, session clock timeline, seed root, and READY/INVALID footer (gap #16)', () => {
  assert.match(html, /id="validationSessionClock"/);
  assert.match(html, /id="validationTimelineStart"/);
  assert.match(html, /id="validationTimelineEnd"/);
  assert.match(html, /id="validationSeedRoot"/);
  assert.match(html, /id="validationSeedStreams"/);
  assert.match(html, /id="validationPlanState"/);
  assert.match(shell, /'READY' : 'INVALID'/);
  assert.match(shell, /dataset\.valid = String\(snapshot\.valid\)/);
  assert.match(configCss, /\.session-timeline-track \{[^}]*border-radius: 4px/);
  assert.match(configCss, /\.plan-metrics strong \{[^}]*font-size: 25px/);
  assert.match(configCss, /\.execution-plan-state\[data-valid="false"\] \{[^}]*color: var\(--ob-danger\)/);
  assert.match(html, /contract-boundary/);
});

test('Review fixes F1/F2: params bind directly to inner inputs; carousel scrollers rebind after upgrade', () => {
  assert.match(shell, /function bindNumberField\(/);
  assert.match(shell, /element\.shadowRoot\?\.querySelector\('input'\) \|\| element/);
  assert.match(shell, /boundNumberTargets/);
  assert.match(shell, /whenDefined\('obc-number-input-field'\)[\s\S]{0,120}requestAnimationFrame\(\(\) => setTimeout\(rebindNumberFields, 0\)\)/);
  assert.match(shell, /function renderParamErrors\(snapshot\) \{\s*\/\/ Lazy-rebind[\s\S]{0,320}rebindNumberFields\(\);/);
  assert.match(shell, /function rebindNumberFields\(/);
  assert.match(shell, /event\.target\.value \?\? ''/);
  assert.match(shell, /lastParamCommit/);
  assert.doesNotMatch(shell, /validationParamsFields'\)\.addEventListener/);
  assert.match(shell, /customElements\.whenDefined\('obc-scrollbar'\)\.then\(rebindCarouselScrollers\)/);
  assert.match(shell, /function rebindCarouselScrollers\(/);
  assert.match(shell, /function bindCarouselScroll\(/);
  assert.match(shell, /boundViewports\.get\(name\) === viewport/);
  assert.match(shell, /scrollSnapType = 'x mandatory'/);
  assert.match(shell, /requestAnimationFrame\(\(\) => updateCarouselControls\(name\)\)/);
  assert.match(shell, /new ResizeObserver\(\(\) => updateCarouselControls\(name\)\)/);
  assert.match(shell, /data-config-step-panel[\s\S]{0,400}requestAnimationFrame\(\(\) => rebindCarouselScrollers\(\)\)/);
});

test('Review fix F3: scroll-snap-type engaged on the fallback host scroller', () => {
  assert.match(configCss, /\.scenario-scrollbar \{[^}]*scroll-snap-type: x mandatory/);
});

test('Review fix F4: CREATED pill is keyed off clean-match, not merely !dirty', () => {
  assert.match(shell, /cleanMatch \? 'CREATED' : 'READY'/);
  assert.doesNotMatch(shell, /snapshot\.dirty \? 'READY' : 'CREATED'/);
});

test('Review fix F5: Create accent reaches the obc-button surface via palette var override', () => {
  assert.match(configCss, /\.assembly-actions \.create-action \{[^}]*--normal-enabled-background-color: var\(--ob-accent\)/);
  assert.match(configCss, /--on-normal-neutral-color: var\(--ob-surface\)/);
  assert.doesNotMatch(configCss, /\.assembly-actions obc-button::part\(button\)/);
});

test('Review P3 fixes: single-card centering, inert ENC cards, dead rules removed', () => {
  assert.match(configCss, /\.scenario-choice-grid\[data-count="1"\] \{[^}]*justify-content: center/);
  assert.match(configCss, /#validationEncChoices[^{]*\{[^}]*pointer-events: none/);
  assert.doesNotMatch(configCss, /\.config-step-panel select/);
  assert.match(html, /<h2 id="validationAlgorithmName">/);
  assert.match(html, /<h2 id="validationTrackerName">/);
  assert.doesNotMatch(html, /<h3 id="validationAlgorithmName">/);
  assert.doesNotMatch(configCss, /\.roadmap-workface \{[^}]*var\(--ob/);
});

test('C5 pull-forward: shell background maps onto OpenBridge tokens (no dark base)', () => {
  assert.match(styles, /body \{[^}]*background(?:-color)?: var\(--ob-app-bg\)/);
  assert.match(styles, /body \{[^}]*color: var\(--ob-text\)/);
  assert.match(styles, /\.product-shell-header \{[^}]*background: var\(--ob-topbar\)/);
  assert.match(styles, /\.workface-tab\.active \{[^}]*background: var\(--ob-accent-pale\)/);
  assert.doesNotMatch(styles, /\.product-shell-header \{[^}]*#f7f8f8/);
  assert.doesNotMatch(styles, /body \{[^}]*var\(--bg-dark\)/);
});

test('C5 pull-forward: top bar populated with app icon, Beijing clock, and action buttons (gap #1)', () => {
  assert.match(html, /slot="app-icon"/);
  assert.match(html, /obi-collision-avoidance-head-on/);
  assert.match(html, /<obc-clock[^>]*showseconds[^>]*timezoneoffsethours="8"/);
  assert.match(html, /id="topbarBeijingClock"/);
  for (const id of ['alertBtn', 'soundBtn', 'settingsBtn']) assert.match(html, new RegExp(`id="${id}"`));
  assert.match(html, /showappsbutton showdimmingbutton showappicon showuserbutton/);
  assert.match(shell, /vendor\/openbridge\/openbridge-components\.mjs/);
  assert.match(shell, /vendor\/openbridge\/openbridge-components\.mjs/);
  assert.doesNotMatch(styles, /\.openbridge-topbar \{[^}]*pointer-events: none/);
  assert.match(styles, /obc-clock:not\(:defined\)/);
  // Session-state chip removed 2026-08-19 (overlapped topbar alert/sound buttons).
  assert.doesNotMatch(html, /id="shellSessionState"/);
  assert.doesNotMatch(shell, /shellSessionState/);
  assert.doesNotMatch(styles, /\.shell-session-state/);
});

test('C5 pull-forward: workface tabs carry icons and pressed-pill chrome (gap #2)', () => {
  const tabIcons = {
    config: 'obi-settings-user-proposal',
    deployment: 'obi-media-play',
    evaluation: 'obi-list-alt-check-google',
    scenario: 'obi-collision-avoidance-head-on',
    algorithm: 'obi-router-component',
  };
  for (const [workface, icon] of Object.entries(tabIcons)) {
    assert.match(html, new RegExp(`data-workface="${workface}"[^>]*>\\s*<${icon}`));
  }
  assert.match(styles, /\.workface-tab \{[^}]*min-height: 40px/);
  assert.match(styles, /\.workface-tab > obi-\[a-z-\] \{[^}]*width: 18px/);
});
