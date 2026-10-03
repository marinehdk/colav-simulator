/**
 * Module import specifier uniqueness guard (P3-6, spec #91 batch-2b).
 *
 * Generalization of the twin-view.js guard (twin-view.test.mjs) to every
 * local ES module: native ESM treats each distinct resolved specifier
 * (path + `?v=` token) as a separate module instance. Two tokens for one
 * file mean the page evaluates that module twice with duplicated module
 * state (the situation-display.js bug: four tokens -> four evaluations per
 * page load). The guard scans EVERY literal import edge across
 * index.html + app.js + web_gui/modules/*.js + tests/web_gui/*.{html,mjs}
 * and asserts each module file is imported through exactly one specifier
 * token. Relative specifiers are normalized like a browser would
 * (`./modules/x.js?v=T` from app.js ≡ `./x.js?v=T` from a module ≡
 * `/static/modules/x.js?v=T` from the shell). Non-literal specifiers
 * (template strings) cannot be checked statically and are skipped.
 */

import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const WEB_GUI_ROOT = path.resolve(fileURLToPath(import.meta.url), '../../../web_gui');
const TESTS_ROOT = path.resolve(fileURLToPath(import.meta.url), '..');

/** Justified multi-token exemptions — MUST stay empty; add with a written
 *  reason only when a module genuinely needs two instances in one page. */
const EXEMPT_SPECIFIERS = Object.freeze({});

function sourceFiles() {
  const files = [];
  for (const name of ['index.html', 'app.js']) {
    files.push(path.join(WEB_GUI_ROOT, name));
  }
  for (const name of readdirSync(path.join(WEB_GUI_ROOT, 'modules')).sort()) {
    if (name.endsWith('.js')) files.push(path.join(WEB_GUI_ROOT, 'modules', name));
  }
  for (const name of readdirSync(TESTS_ROOT).sort()) {
    if (name.endsWith('.html') || name.endsWith('.test.mjs')) {
      files.push(path.join(TESTS_ROOT, name));
    }
  }
  return files;
}

// Import edges: static/dynamic `from '…'` / `import('…')` / `import '…'` plus
// `<script type="module" src="…">` in HTML (the second alternative covers it).
const IMPORT_EDGE = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+|src\s*=\s*)["']([^"']+\.js)(?:\?([^"'?]*))?["']/g;

/** Canonical module key relative to web_gui/ for one import edge. */
function resolveModuleKey(fromFile, specifier) {
  if (specifier.startsWith('/static/')) {
    return specifier.slice('/static/'.length);
  }
  const resolved = path.resolve(path.dirname(fromFile), specifier.split('?')[0]);
  return path.relative(WEB_GUI_ROOT, resolved);
}

test('every web module is imported through exactly one specifier (single ES module instance)', () => {
  const specifiersByModule = new Map();
  for (const file of sourceFiles()) {
    const text = readFileSync(file, 'utf8');
    for (const match of text.matchAll(IMPORT_EDGE)) {
      const specifier = match[1];
      const token = match[2] ?? '';
      const key = resolveModuleKey(file, specifier);
      if (!/^(?:modules\/[a-z0-9-]+\.js|app\.js)$/.test(key)) continue;
      const label = path.relative(path.dirname(WEB_GUI_ROOT), file);
      if (!specifiersByModule.has(key)) specifiersByModule.set(key, new Map());
      const byToken = specifiersByModule.get(key);
      if (!byToken.has(token)) byToken.set(token, []);
      byToken.get(token).push(label);
    }
  }

  const violations = [];
  for (const [key, byToken] of [...specifiersByModule].sort()) {
    if (byToken.size <= 1 || Object.hasOwn(EXEMPT_SPECIFIERS, key)) continue;
    const exempt = EXEMPT_SPECIFIERS[key] ?? [];
    const detail = [...byToken.entries()]
      .filter(([token]) => !exempt.includes(token))
      .map(([token, files]) => `${token ? `?${token}` : '(unversioned)'} <- ${files.join(', ')}`);
    if (detail.length > 1) {
      violations.push(`${key}\n    ${detail.join('\n    ')}`);
    }
  }
  assert.deepEqual(violations, [],
    `modules imported through multiple specifiers evaluate once per token\n  ${violations.join('\n  ')}`);
});
