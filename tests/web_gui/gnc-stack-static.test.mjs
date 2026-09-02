import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');

test('GNC stack panel declares a select and four separated evidence groups', () => {
  assert.match(html, /id="gncStackPanel"/);
  assert.match(html, /<select id="gncStackSelect"[^>]*aria-label="Ownship GNC stack"/);
  // AC2: maturity, fidelity, asset trust, and acceptance live in separate fields.
  assert.match(html, /id="gncStackModules"/);
  assert.match(html, /id="gncStackFidelity"/);
  assert.match(html, /id="gncStackAssetTrust"/);
  assert.match(html, /id="gncStackAcceptance"/);
  assert.match(html, /id="gncStackCeilingNote"/);
});

test('Config shell consumes the backend stack catalog endpoint', () => {
  assert.match(shell, /fetchJson\('\/api\/gnc\/stacks'/);
  assert.match(shell, /gncStackSelect/);
});

test('Stack options come only from the backend catalog document', () => {
  const renderSlice = shell.slice(shell.indexOf('function renderGncStackPanel'));
  assert.ok(renderSlice.length > 0, 'renderGncStackPanel exists');
  assert.match(renderSlice, /catalog\.stacks/);
  assert.match(renderSlice, /entry\.stack_id/);
  assert.doesNotMatch(renderSlice, /const STACKS|hardcodedStacks/);
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

test('Client never reimplements stack validation or hardcodes module identity logic', () => {
  assert.doesNotMatch(shell, /GENERALIZED_FORCE|KINEMATIC_REFERENCE|REGISTRY_V1|normalize_ship_modules/);
  assert.doesNotMatch(shell, /marine_pid|integral_line_of_sight|data_driven_allocator|resolved_actuator_dynamics/);
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

test('GNC stack panel has styles', () => {
  assert.match(styles, /\.gnc-stack-layout/);
  assert.match(styles, /\.gnc-stack-detail-grid/);
});
