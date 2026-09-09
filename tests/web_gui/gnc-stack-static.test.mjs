import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { presetBinding, presetStackId } from '../../web_gui/modules/gnc-presets.js';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
const catalog = { product_presets: [
  { id: 'legacy', variants: { off: 'legacy-binding' } },
  { id: 'ideal', variants: { off: 'a', on: 'b' } },
  { id: 'direct', variants: { off: 'c', on: 'd' } },
  { id: 'full', variants: { off: 'e', on: 'f' } },
] };

test('every preset environment variant round trips exact backend binding', () => {
  for (const preset of catalog.product_presets) {
    for (const [environment, stackId] of Object.entries(preset.variants)) {
      assert.equal(presetStackId(catalog, preset.id, environment), stackId);
      assert.deepEqual(presetBinding(catalog, stackId), { preset, environment });
    }
  }
});

test('unsupported environment and old custom bindings never silently select another stack', () => {
  assert.equal(presetStackId(catalog, 'legacy', 'on'), null);
  assert.equal(presetStackId(catalog, 'unknown', 'off'), null);
  assert.equal(presetBinding(catalog, 'old-stack'), null);
  assert.equal(presetBinding(null, 'a'), null);
});

test('GNC page offers complete presets and accessible environment switch with two read-only tables', () => {
  assert.match(html, /id="gncPresetChoices"[^>]*role="radiogroup"/);
  assert.match(html, /role="switch" id="gncEnvironmentToggle"/);
  assert.match(html, /aria-label="Selected stack fields"/);
  assert.match(html, /aria-label="Four preset stacks"/);
  for (const field of ['Plant', 'Guidance', 'Controller', 'Actuation', 'Environment']) {
    assert.ok(html.includes(`<th>${field}</th>`));
  }
  assert.doesNotMatch(html, /id="gnc(?:Plant|Guidance|Controller|Actuation)Choices"/);
  assert.match(shell, /catalog\.product_presets/);
  assert.match(shell, /toggle\.disabled = locked/);
});

test('evidence stays separate and draft uses backend identities without parsing', () => {
  for (const id of ['gncStackModules', 'gncStackFidelity', 'gncStackAssetTrust', 'gncStackAcceptance']) {
    assert.ok(html.includes(`id="${id}"`));
  }
  assert.match(shell, /edit\('gnc_stack_id'/);
  assert.doesNotMatch(shell, /stack_id\.(split|replace|match|startsWith|includes)/);
  assert.doesNotMatch(shell, /marine_pid|integral_line_of_sight|data_driven_allocator|resolved_actuator_dynamics/);
});
