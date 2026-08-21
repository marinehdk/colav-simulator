import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const lineGraph = await readFile(new URL('../../web_gui/modules/line-graph.js', import.meta.url), 'utf8');
const vendorEntry = await readFile(new URL('../../web_gui/vendor/openbridge/entry-source.mjs', import.meta.url), 'utf8');

test('OWN SHIP exposes five OpenBridge sensor-source dropdowns with mock option wiring', () => {
  for (const id of ['sidebarHdgSource', 'sidebarCogSource', 'sidebarStwSource', 'sidebarDepthSource', 'sidebarPositionSource']) {
    assert.match(html, new RegExp(`<obc-dropdown-button[^>]*id="${id}"`));
    assert.match(app, new RegExp(`id: '${id}'`));
  }
  assert.match(vendorEntry, /components\/dropdown-button\/dropdown-button\.js/);
  assert.match(app, /customElements\.whenDefined\('obc-dropdown-button'\)\.then\(setupSensorSourceDropdowns\)/);
  assert.match(app, /addEventListener\('dropdown-change'/);
});

test('top-bar notifications use OpenBridge controls and projected simulation events', () => {
  assert.match(html, /<obc-notification-button[^>]*id="alertBtn"/);
  assert.match(html, /id="notificationPanel"[^>]*aria-labelledby="notificationPanelHeading"/);
  assert.match(vendorEntry, /components\/notification-button\/notification-button\.js/);
  assert.match(vendorEntry, /components\/notification-message-item\/notification-message-item\.js/);
  assert.match(app, /function setupNotificationCenter\(/);
  assert.match(app, /function renderNotificationCenter\(events\)/);
  assert.match(app, /renderNotificationCenter\(proj\.timeline\?\.events \|\| \[\]\)/);
  assert.match(app, /addEventListener\('obc-click'/);
});

test('DEPTH uses the live ENC depth bin instead of a fixed 15 m value', () => {
  assert.match(html, /id="sidebarDepthSource" value="enc"/);
  assert.match(html, /<strong>FLOOR<\/strong><small>ENC BIN<\/small>/);
  assert.match(app, /\{ value: 'enc', label: 'ENC' \}/);
  assert.match(app, /os\?\.floor_depth_m/);
  assert.match(app, /enc_navigation_area\?\.vessel_draft_m/);
  assert.match(app, /enc_navigation_area\?\.minimum_depth_m/);
  assert.doesNotMatch(app, /\{ depth: 15, draft: 2/);
  assert.doesNotMatch(app, /value: 15, nDigits: 2/);
});

test('ROUTE destination times use the same 12px\/18px value typography as Current leg', () => {
  assert.match(styles, /\.route-value-grid strong \{[^}]*font: 500 12px\/18px var\(--font-mono\)/);
  assert.match(styles, /\.route-destination strong \{[^}]*font: 500 12px\/18px var\(--font-mono\)/);
  assert.match(styles, /\.route-destination span \{[^}]*min-height: 28px;[^}]*font-size: 9px;[^}]*line-height: 13px/);
});

test('DCPA and TCPA render units inline after values', () => {
  assert.match(html, /<strong><span id="riskDcpa">---<\/span><small>m<\/small><\/strong>/);
  assert.match(html, /<strong><span id="riskTcpa">---<\/span><small>s<\/small><\/strong>/);
  assert.match(app, /<strong>\$\{dcpaText\}<small>m<\/small><\/strong>/);
  assert.match(app, /<strong>\$\{tcpaText\}<small>s<\/small><\/strong>/);
  assert.match(styles, /\.risk-target-metric strong \{[^}]*display: flex;[^}]*align-items: baseline/);
});

test('Target range defaults to nautical miles and toggles to kilometres from metres', () => {
  assert.match(app, /let riskDistanceUnit = 'nmi'/);
  assert.match(app, /distanceM \/ METERS_PER_NAUTICAL_MILE/);
  assert.match(app, /distanceM \/ 1000/);
  assert.match(app, /riskDistanceUnit === 'nmi' \? 'km' : 'nmi'/);
  assert.match(html, /class="risk-distance-toggle"[^>]*data-unit="nmi"/);
});

test('EVENT LIST uses OpenBridge event-list with projected timeline data', () => {
  assert.match(html, /id="monitor-event-heading">EVENT LIST</);
  assert.match(html, /<obc-event-list[^>]*id="liveEvents"/);
  assert.match(vendorEntry, /components\/event-list\/event-list\.js/);
  assert.match(app, /renderMonitorEventList\(proj\.timeline\?\.events \|\| \[\]\)/);
  assert.match(app, /eventItemType: 'doubleLine'/);
  assert.match(app, /colorCoded/);
  assert.doesNotMatch(app, /eventList\.innerHTML/);
});

test('planner diagnostics render directly on the chart for each supported algorithm', () => {
  assert.doesNotMatch(html, /Decision Screen/);
  assert.doesNotMatch(html, /id="plannerSurfaceAttach"/);
  assert.doesNotMatch(html, /id="liveAlgorithmPreviewChart"/);
  assert.match(app, /const attached = Boolean\(plannerSurfaceType\(planner\)\)/);
  assert.match(app, /situationDisplay\.setPlannerSurfaceAttached\(attached\)/);
  assert.match(app, /if \(type === 'vo'\)/);
  assert.match(app, /if \(type === 'fan'\)/);
  assert.match(app, /return null;/);
});

test('restored sessions reset planner overlay state without aborting ENC startup', () => {
  const resetStart = app.indexOf('function resetDeploymentForSession(data)');
  const resetEnd = app.indexOf('function setControlDisabled', resetStart);
  const resetSession = app.slice(resetStart, resetEnd);
  assert.doesNotMatch(resetSession, /^\s{2}setPlannerSurfaceAttached\(/m);
  assert.match(resetSession, /situationDisplay\.setPlannerSurfaceAttached\(false\)/);
  assert.ok(
    resetSession.indexOf('situationDisplay.setPlannerSurfaceAttached(false)')
      < resetSession.indexOf('situationDisplay.beginSession('),
  );
});

test('performance charts use reusable Web Component graphs with English axes and legends', () => {
  assert.match(html, /<colav-line-graph[\s\S]*id="livePerfGraph"[\s\S]*caption="Computation Time"[\s\S]*x-label="Recent Step"[\s\S]*y-label="Time \(ms\)"[\s\S]*legend="Computation time"/);
  assert.match(html, /<colav-line-graph[\s\S]*id="liveCostGraph"[\s\S]*caption="Objective Cost"[\s\S]*x-label="Solve"[\s\S]*y-label="Cost"[\s\S]*legend="Objective cost"/);
  assert.doesNotMatch(html, /计算耗时曲线|Cost 曲线/);
  assert.match(app, /import '\.\/modules\/line-graph\.js/);
  assert.match(app, /graph\.setSeries\(perfHistory\)/);
  assert.match(lineGraph, /customElements\.define\('colav-line-graph'/);
  assert.match(lineGraph, /class="grid-lines"/);
  assert.match(lineGraph, /class="tick-labels"/);
  assert.match(lineGraph, /class="axis-label x-label"/);
  assert.match(lineGraph, /class="axis-label y-label"/);
  assert.match(lineGraph, /class="legend"/);
});

test('ownship click error reporting tolerates the removed legacy busy-water status node', () => {
  const start = app.indexOf('onSelectionChange: target =>');
  const selectionHandler = app.slice(start, app.indexOf('\n  },\n});', start));
  assert.doesNotMatch(selectionHandler, /document\.getElementById\('busyWaterStatus'\)\.textContent/);
  assert.match(selectionHandler, /const status = document\.getElementById\('busyWaterStatus'\)/);
  assert.match(selectionHandler, /if \(status\) status\.textContent = error\.message/);
});
