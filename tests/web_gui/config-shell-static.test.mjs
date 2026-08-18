import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
const legacy = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const runtime = await readFile(new URL('../../web_gui/modules/active-session-runtime.js', import.meta.url), 'utf8');
const instance = await readFile(new URL('../../web_gui/modules/session-runtime-instance.js', import.meta.url), 'utf8');

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
  const legacyImport = legacy.match(/import \{ activeSessionRuntime \} from ['"]\.\/modules\/session-runtime-instance\.js(\?v=[^'"]*)?['"]/);
  const shellImport = shell.match(/import \{ activeSessionRuntime \} from ['"]\.\/session-runtime-instance\.js(\?v=[^'"]*)?['"]/);
  const runtimeImport = instance.match(/import \{ createActiveSessionRuntime \} from ['"]\.\/active-session-runtime\.js(\?v=[^'"]*)?['"]/);
  assert.ok(legacyImport, 'Deployment imports the singleton');
  assert.ok(shellImport, 'Config imports the singleton');
  assert.ok(legacyImport[1], 'Deployment singleton import carries a cache-bust token');
  assert.equal(legacyImport[1], shellImport[1], 'singleton specifiers must be byte-identical or the module splits');
  assert.ok(runtimeImport?.[1], 'instance import of the runtime carries a cache-bust token');
  assert.match(instance, /export const activeSessionRuntime = createActiveSessionRuntime/);
  assert.doesNotMatch(instance, /\.bootstrap\(/);
  assert.match(html, /<script type="module" src="\/static\/app\.js/);
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
  assert.match(legacy, /future Scenario surface/);
});

test('ENC loading is replacement-bound and stale fetch/image callbacks are inert', () => {
  assert.match(legacy, /encLoadGeneration/);
  assert.match(legacy, /encInfoController\.abort\(\)/);
  assert.match(legacy, /info\.run_id !== sessionId/);
  assert.match(legacy, /generation !== encLoadGeneration \|\| sessionId !== currentRunId\(\)/);
  assert.match(legacy, /encPendingImage\.onload = null/);
  assert.match(legacy, /encRetryTimer/);
});
