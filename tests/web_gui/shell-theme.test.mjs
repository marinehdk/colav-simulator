import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// C5 work order (2026-08-19): product shell remainder — theme switching (#4),
// typography (#6), global focus/motion (#7), 520 tier (#8), doc-title/view
// persistence (#22). Static contracts only; no pixel automation.
const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const shell = await readFile(new URL('../../web_gui/modules/config-shell.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');

const assetToken = (path) => html.match(new RegExp(`${path}\\?v=([A-Za-z0-9_-]+)`))?.[1];

test('C5 #4: html carries the day palette by default and the hidden brilliance-menu popover (P:2, P:2003)', () => {
  assert.match(html, /<html lang="zh-CN" data-obc-theme="day">/);
  assert.match(html, /<obc-brilliance-menu[^>]*id="brillianceMenu"[^>]*variant="compact"[^>]*aria-label="显示模式"[^>]*hidden[^>]*>/);
});

test('C5 #4: app.js imports the locally-vendored OpenBridge bundle and wires palette state', () => {
  assert.match(app, /vendor\/openbridge\/openbridge-components\.mjs/);
  assert.match(app, /document\.documentElement\.dataset\.obcTheme = nextPalette/);
  assert.match(app, /dimmingButtonActivated = nextPalette === 'dusk' \|\| nextPalette === 'night'/);
  assert.match(app, /situationDisplay\.refreshPalette\(\)/);
});

test('C5 #4: palette persists under the colav-openbridge-palette key and boot restores without persisting', () => {
  assert.match(app, /localStorage\.setItem\('colav-openbridge-palette', nextPalette\)/);
  assert.match(app, /localStorage\.getItem\('colav-openbridge-palette'\)/);
  const boot = app.slice(app.indexOf('let initialPalette'));
  assert.match(boot, /applyPalette\(initialPalette, false\)/);
});

test('C5 #4: dimming button toggles the menu; palette-changed applies; no toast adapter (#9 deleted)', () => {
  assert.match(app, /addEventListener\('dimming-button-clicked'/);
  assert.match(app, /brillianceMenu\.hidden = !brillianceMenu\.hidden/);
  assert.match(app, /addEventListener\('palette-changed', \(event\) => \{\s*applyPalette\(event\.detail\?\.value \|\| brillianceMenu\.palette\)/);
  assert.doesNotMatch(app, /showToast|notify\(|obc-toast/);
});

test('C5 #4: outside-click and Escape close the menu; clicks inside stop propagation (P:3293)', () => {
  assert.match(app, /brillianceMenu\.addEventListener\('click', \(event\) => event\.stopPropagation\(\)\)/);
  assert.match(app, /if \(!brillianceMenu\.hidden && !brillianceMenu\.contains\(event\.target\) && !event\.composedPath\(\)\.includes\(mainTopBar\)\)/);
  const escapeHandler = app.slice(app.indexOf("addEventListener('keydown'"));
  assert.match(escapeHandler, /event\.key !== 'Escape'/);
  assert.match(escapeHandler, /brillianceMenu\.hidden = true/);
});

test('C5 #4: style.css flips color-scheme and applies prototype image filters to the preview image and Deployment canvas (P:280-285)', () => {
  assert.match(styles, /html\[data-obc-theme="dusk"\],\s*html\[data-obc-theme="night"\] \{\s*color-scheme: dark;\s*\}/);
  for (const [theme, filter] of [
    ['dusk', 'brightness\\(\\.48\\) saturate\\(\\.72\\)'],
    ['night', 'brightness\\(\\.24\\) sepia\\(\\.34\\) saturate\\(\\.82\\)'],
    ['bright', 'contrast\\(1\\.18\\) saturate\\(\\.86\\)'],
  ]) {
    assert.match(styles, new RegExp(`html\\[data-obc-theme="${theme}"\\] #validationScenarioImage,\\s*html\\[data-obc-theme="${theme}"\\] #simCanvas \\{[^}]*filter: ${filter};`));
  }
});

test('C5 #4: brilliance popover chrome follows P:278 (fixed, below top bar, right 112px, 304px, z-index 50)', () => {
  assert.match(styles, /\.brilliance-menu-popover \{[^}]*position: fixed;[^}]*right: 112px;[^}]*z-index: 50;[^}]*width: 304px;/s);
});

test('C5 #6: Noto Sans/PingFang stack with --font-display, 14px/1.7 body, display headings, no webfont import (P:86-118)', () => {
  assert.match(styles, /--font-display:\s*"Noto Sans",\s*"PingFang SC",\s*sans-serif;/);
  assert.match(styles, /--font-ui:\s*"Noto Sans",\s*"PingFang SC",\s*sans-serif;/);
  assert.match(styles, /--font-body:\s*"Noto Sans",\s*"PingFang SC",\s*sans-serif;/);
  assert.match(styles, /body \{[^}]*font: 400 14px\/1\.7 var\(--font-body\);[^}]*letter-spacing: 0;/s);
  assert.match(styles, /h1, h2, h3 \{[^}]*font-family: var\(--font-display\);[^}]*letter-spacing: 0;/s);
  assert.doesNotMatch(styles, /@import|@font-face/);
  assert.doesNotMatch(html, /fonts\.googleapis|@font-face/);
});

test('C5 #7: focus-visible and reduced-motion are global, scoped duplicates removed (P:120, P:1558-1560)', () => {
  assert.match(styles, /:focus-visible \{ outline: 3px solid var\(--ob-accent-mid\); outline-offset: 2px; \}/);
  assert.doesNotMatch(styles, /\.config-workface :focus-visible/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\) \{\s*\*, \*::before, \*::after \{[^}]*scroll-behavior: auto !important;[^}]*transition: none !important;/s);
  assert.doesNotMatch(styles, /\.config-workface \*/);
  assert.match(styles, /\.choice:focus-visible::part\(wrapper\)/);
});

test('C5 #8: 520 tier degrades top bar, turns Assembly Steps into a horizontal snap strip, stacks Deployment sidebars (P:1499-1557)', () => {
  const tier = styles.slice(styles.indexOf('@media (max-width: 520px)'));
  assert.ok(tier.length > 0, '520px media tier exists');
  assert.match(tier, /\.topbar-actions \.topbar-time,[\s\S]{0,120}#alertBtn,[\s\S]{0,120}#soundBtn \{[^}]*display: none/);
  assert.match(tier, /\.config-workface \{[^}]*grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(tier, /\.assembly-step-list \{[^}]*grid-auto-flow: column;[^}]*overflow-x: auto;[^}]*scroll-snap-type: x/);
  assert.match(tier, /\.assembly-step \{[^}]*scroll-snap-align: start/);
  // Deployment sidebar stacking at narrow widths is delivered by the pre-existing
  // ≤900px flex-column rule; the 520 tier needs no .main-workspace override.
  assert.match(styles, /@media \(max-width: 900px\)[\s\S]{0,2000}\.main-workspace \{[^}]*display: flex;[^}]*flex-direction: column/);
  // Existing tiers survive untouched.
  assert.match(styles, /@media \(max-width: 1400px\)/);
  assert.match(styles, /@media \(max-width: 1050px\)/);
  assert.match(styles, /@media \(max-width: 820px\)/);
});

test('C5 #22: switchWorkface sets the per-view document title and persists the workface (P:2776, P:3398-3402)', () => {
  assert.match(shell, /document\.title = `综合避碰仿真器 · \$\{WORKFACE_TITLES\[workface\]\}`/);
  assert.match(shell, /localStorage\.setItem\('colav-workface', workface\)/);
  for (const view of ['Config', 'Deployment', 'Evaluation', 'Scenario', 'Algorithm']) {
    assert.match(shell, new RegExp(`:\\s*'${view}'`));
  }
});

test('C5 #22: boot restores the persisted workface through switchWorkface (single panel authority)', () => {
  assert.match(shell, /localStorage\.getItem\('colav-workface'\)/);
  const restore = shell.slice(shell.indexOf('function restorePersistedWorkface()'));
  assert.ok(restore.indexOf('switchWorkface(workface)') > -1, 'restore routes through switchWorkface');
  const boot = shell.slice(shell.indexOf('async function bootConfig()'));
  assert.ok(boot.indexOf('restorePersistedWorkface()') > -1, 'bootConfig restores the persisted workface');
  // No session-gating on restore: the call is unconditional, not guarded by session state.
  assert.doesNotMatch(shell, /restorePersistedWorkface\(\)[^;]*\n[^}]*session/);
});

test('C5: cache-bust token bumped for every changed browser-served asset', () => {
  const tokens = [
    assetToken('/static/style.css'),
    assetToken('/static/app.js'),
    assetToken('/static/modules/config-shell.js'),
  ];
  assert.ok(tokens.every(Boolean), `all three changed assets carry a token: ${tokens}`);
  assert.ok(new Set(tokens).size === 1, `tokens match across assets: ${tokens}`);
  assert.notEqual(tokens[0], '20260819-c4-situation-2', 'token must differ from the C4 baseline');
});

test('C5: frozen Active Session Runtime stays byte-identical while projection wiring may evolve', async () => {
  const { execFile } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const run = promisify(execFile);
  for (const file of [
    'web_gui/modules/active-session-runtime.js',
  ]) {
    const { stdout } = await run('git', ['status', '--porcelain', file], { cwd: new URL('../..', import.meta.url).pathname });
    assert.equal(stdout.trim(), '', `${file} must have zero diff`);
  }
});
