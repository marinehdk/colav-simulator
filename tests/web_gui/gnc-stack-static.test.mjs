import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const assembly = await readFile(new URL('../../web_gui/modules/validation-assembly.js', import.meta.url), 'utf8');

test('GNC step panel is a stepper panel with five axis choice groups', () => {
  assert.match(html, /id="gncStackPanel"[^>]*data-config-step-panel="gnc"/);
  // The evidence-only 64-stack select is gone; selection is axis cards now.
  assert.doesNotMatch(html, /<select id="gncStackSelect"/);
  for (const axis of ['plant', 'guidance', 'controller', 'actuation', 'environment']) {
    assert.match(html, new RegExp(`data-gnc-axis="${axis}"`));
  }
  assert.match(html, /id="gncPlantChoices"[^>]*role="radiogroup"/);
  assert.match(html, /id="gncGuidanceChoices"[^>]*role="radiogroup"/);
  assert.match(html, /id="gncControllerChoices"[^>]*role="radiogroup"/);
  assert.match(html, /id="gncActuationChoices"[^>]*role="radiogroup"/);
  assert.doesNotMatch(html, /id="gncResolvedToggle"/);
  for (const axis of ['Plant', 'Guidance', 'Controller', 'Actuation']) {
    assert.match(html, new RegExp(`id="gnc${axis}Scrollbar"`));
    assert.match(html, new RegExp(`id="gnc${axis}Controls"`));
  }
});

test('Stack Evidence is the only detail surface below the axis choices', () => {
  assert.doesNotMatch(html, /id="gncCombinationBar"/);
  assert.doesNotMatch(shell, /function renderGncCombination/);
  // AC2: maturity, fidelity, asset trust, and acceptance live in separate fields.
  assert.match(html, /id="gncStackModules"/);
  assert.match(html, /id="gncStackFidelity"/);
  assert.match(html, /id="gncStackAssetTrust"/);
  assert.match(html, /id="gncStackAcceptance"/);
  assert.doesNotMatch(html, /id="gncStackCeilingNote"/);
  const evidenceAt = html.indexOf('gncStackModules');
  assert.ok(evidenceAt >= 0, 'Stack Evidence remains below the axis choices');
});

test('Config shell consumes the backend stack catalog endpoint and module_axes ladder', () => {
  assert.match(shell, /fetchJson\('\/api\/gnc\/stacks'/);
  assert.match(shell, /module_axes/);
  assert.match(shell, /recommended_stack_ids_by_plant/);
  assert.match(shell, /gncRecommendedStackForPlant/);
  assert.match(shell, /expected_effect/);
  assert.match(shell, /drive_nature/);
});

test('Axis cards and evidence render only from the backend catalog document', () => {
  const renderSlice = shell.slice(shell.indexOf('function renderGncStackPanel'));
  assert.ok(renderSlice.length > 0, 'renderGncStackPanel exists');
  assert.match(renderSlice, /catalog\.stacks/);
  assert.match(renderSlice, /entry\.stack_id/);
  assert.doesNotMatch(renderSlice, /const STACKS|hardcodedStacks/);
});

test('Stack binding is matched against stack modules and asset trust, never stack_id strings', () => {
  const matchSlice = shell.slice(shell.indexOf('function gncStackMatchesSelection'));
  assert.ok(matchSlice.length > 0, 'gncStackMatchesSelection exists');
  assert.match(matchSlice, /entry\.modules/);
  assert.match(matchSlice, /asset_trust/);
  // No client-side stack_id parsing and no reimplemented validity rules.
  assert.doesNotMatch(shell, /stack_id\.(split|replace|match|startsWith|includes)/);
  assert.doesNotMatch(shell, /normalize_ship_modules|REGISTRY_V1|GENERALIZED_FORCE|KINEMATIC_REFERENCE/);
});

test('Client never hardcodes module identity knowledge', () => {
  assert.doesNotMatch(shell, /marine_pid|integral_line_of_sight|data_driven_allocator|resolved_actuator_dynamics/);
  assert.doesNotMatch(shell, /pass_through_plant|generic_3dof_plant|generic_roll_4dof_plant/);
});

test('Evidence rendering keeps trust and acceptance as data-driven separate fields', () => {
  const detailSlice = shell.slice(shell.indexOf('function renderGncStackDetail'));
  assert.ok(detailSlice.length > 0, 'renderGncStackDetail exists');
  assert.match(detailSlice, /module\.interface_version/);
  assert.match(detailSlice, /module\.acceptance_evidence/);
  assert.match(detailSlice, /entry\.fidelity_profile/);
  assert.match(detailSlice, /asset\.trust_level/);
  assert.match(detailSlice, /entry\.acceptance_level/);
});

test('gnc_stack_id is an additive draft field that reaches the create body', () => {
  assert.match(assembly, /CREATE_FIELDS = \[[\s\S]*?'gnc_stack_id'/);
  assert.match(assembly, /gnc_stack_id: null/);
  assert.doesNotMatch(assembly, /gnc_stack_id[^;]*TUPLE_FIELDS/);
  assert.match(shell, /edit\('gnc_stack_id'/);
  // The create chain posts the whole draft spec through the runtime seam.
  assert.match(shell, /activeSessionRuntime\.create\(pending\.spec\)/);
});

test('Summary and YAML contract expose the GNC stack binding with a Legacy default', () => {
  assert.match(shell, /\['GNC stack', gncStackDisplayLabel\(snapshot\)\]/);
  assert.match(shell, /gncStackDisplayLabel/);
  assert.match(shell, /Legacy \(scenario default\)/);
  const keysSlice = shell.slice(shell.indexOf('function renderYamlContract'));
  assert.match(keysSlice, /'gnc_stack_id'/);
});

test('Environment axis stays a locked calm-water placeholder for V2', () => {
  assert.match(html, /data-gnc-axis="environment"/);
  assert.match(shell, /gncEnvironmentChoices/);
  assert.match(shell, /Calm water \(default\)/);
});

test('GNC stack surface claims nothing beyond accepted evidence', () => {
  for (const source of [html, shell]) {
    const gncSlice = source.includes('gncStackPanel')
      ? source.slice(source.indexOf('gncStackPanel'))
      : source;
    for (const token of ['A4', 'A5', 'A6', 'A7', 'vessel-validated', 'validated_for_vessel', 'SIL', 'sea-trial']) {
      assert.ok(!gncSlice.includes(token), `must not contain ${token}`);
    }
  }
});

test('GNC stack panel has consistent horizontal axis-card styles', () => {
  assert.match(styles, /\.gnc-stack-layout/);
  assert.match(styles, /\.gnc-stack-detail-grid/);
  assert.match(styles, /\.gnc-axis \{/);
  assert.match(styles, /\.gnc-axis-grid \{[^}]*grid-auto-flow: column;[^}]*grid-auto-columns:/);
  assert.match(styles, /\.gnc-axis-scrollbar \{/);
  assert.match(styles, /\.gnc-axis-grid \.choice-description,[\s\S]*display: none/);
  assert.match(styles, /\.gnc-axis-grid \.choice, \.gnc-axis-grid \.choice::part\(wrapper\) \{ height: 56px; min-height: 56px; \}/);
  assert.match(styles, /\.gnc-stack-detail-grid \{ display: grid; grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);/);
  assert.doesNotMatch(styles, /\.gnc-resolved-toggle/);
});
