import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
const legacy = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');

test('Config starts disabled and boot establishes assembly before binding controls', () => {
  for (const id of [
    'validationScenario',
    'validationAlgorithm',
    'validationTracker',
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

test('only Config shell may POST the session collection endpoint', () => {
  assert.doesNotMatch(legacy, /apiRequest\(['"]\/api\/sessions['"]/);
  assert.match(shell, /fetchJson\(['"]\/api\/sessions['"]/);
});

test('background recovery revokes Config authority until manual dual-authority retry', () => {
  assert.match(legacy, /validation-session-authority-unknown/);
  assert.match(shell, /addEventListener\('validation-session-authority-unknown'/);
  assert.match(shell, /markCurrentSessionUnknown/);
  assert.match(shell, /Promise\.allSettled\(\[\s*fetchJson\('\/api\/capabilities'\),\s*fetchCurrentSession\(\)/);
});

test('legacy Deployment configuration is hidden and cannot imply it applies to Validation Draft', () => {
  assert.match(legacy, /LEGACY_CONFIG_CARD_IDS/);
  assert.match(legacy, /Configuration moved to Config/);
  assert.doesNotMatch(legacy, /Create from Config to apply it/);
  assert.match(legacy, /future Scenario surface/);
});
