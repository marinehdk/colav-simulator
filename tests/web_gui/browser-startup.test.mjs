import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const projection = await readFile(
  new URL('../../web_gui/modules/telemetry-projection.js', import.meta.url),
  'utf8',
);

const htmlIds = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]));

test('Deployment boot leaves Config catalog and bootstrap to Validation Assembly', () => {
  for (const retiredId of ['scenarioSelect', 'algoSelect', 'trackerSelect', 'scenarioCatalog', 'encChartSelect']) {
    assert.doesNotMatch(app, new RegExp(retiredId), `app.js must not retain retired selector ${retiredId}`);
  }
  assert.doesNotMatch(app, /\/api\/(?:capabilities|scenarios)\b/);
  assert.doesNotMatch(app, /activeSessionRuntime\.bootstrap\(\)/);
  assert.match(app, /activeSessionRuntime\.subscribe\(syncDeploymentRuntime\)/);
  assert.match(app, /Validation Assembly .*sole capability\/catalog and.*bootstrap authority/s);
});

test('browser startup only dereferences DOM nodes that are present or optional', () => {
  for (const requiredId of ['simCanvas', 'canvasWrapper', 'mainTopBar', 'brillianceMenu']) {
    assert.ok(htmlIds.has(requiredId), `index.html must provide ${requiredId} before app.js evaluates`);
  }

  // A direct property dereference on getElementById is an eager boot-time null
  // failure. Optional chaining is valid for deployment controls that are
  // intentionally absent in a particular responsive surface; all other direct
  // dereferences must name an element in the HTML contract.
  const dereferences = [...app.matchAll(
    /document\.getElementById\(['"]([^'"]+)['"]\)(\?\.|\.)/g,
  )];
  for (const match of dereferences) {
    const [, id, operator] = match;
    if (operator === '.') {
      assert.ok(htmlIds.has(id), `direct DOM dereference requires HTML id ${id}`);
    }
  }
  assert.doesNotMatch(app, /document\.querySelector\([^)]*\)\.(?!\.)/);
});

test('active product replay and semantic/profile hash projections remain available', () => {
  assert.match(app, /activeSessionRuntime\.replay\(\)/);
  assert.match(projection, /snapshotHash/);
  assert.match(projection, /profileHash/);
  assert.match(projection, /semantic_hash/);
  assert.match(projection, /profile_hash/);
});

test('Deployment renders only the active algorithm and Truth tracker vocabulary', () => {
  for (const retired of ['nominal', 'sbmpc', 'potocnik_simplified_mpc', 'kf']) {
    assert.doesNotMatch(app, new RegExp(`\\b${retired}\\b`));
  }
  for (const active of ["algorithmId === 'vo'", "algorithmId === 'mid_mpc_ipopt'", "algorithmId === 'potocnik_colreg_fan_mpc'"]) {
    assert.match(app, new RegExp(active.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});
