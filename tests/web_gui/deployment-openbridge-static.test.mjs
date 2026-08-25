import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const situationDisplay = await readFile(new URL('../../web_gui/modules/situation-display.js', import.meta.url), 'utf8');
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

test('Deployment top-bar menu and apps buttons collapse the matching sidebars', () => {
  assert.match(html, /id="liveInfoSidebar"/);
  assert.match(html, /id="liveOperationsSidebar"/);
  assert.match(app, /addEventListener\('menu-button-clicked'/);
  assert.match(app, /addEventListener\('apps-button-clicked'/);
  assert.match(app, /left-sidebar-collapsed/);
  assert.match(app, /right-sidebar-collapsed/);
  assert.match(app, /'aria-controls': controls/);
  assert.match(styles, /\.live-layout\.left-sidebar-collapsed\s*\{/);
  assert.match(styles, /\.live-layout\.right-sidebar-collapsed\s*\{/);
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

test('risk cards use the projected threat level for card and COLREGs colors', () => {
  assert.match(app, /function riskThreatLevel\(target\)/);
  assert.match(app, /data-threat="\$\{threatLevel\}"/);
  assert.match(styles, /\.risk-target-card\[data-threat="safe"\]/);
  assert.match(styles, /\.risk-target-card\[data-threat="warn"\]/);
  assert.match(styles, /\.risk-target-card\[data-threat="danger"\]/);
  assert.match(styles, /\.risk-target-facts \.colreg-value \{[^}]*color: var\(--risk-card-color\)/);
});

test('monitor event list grows into the remaining right-sidebar space', () => {
  assert.match(styles, /\.operations-info-page \{[^}]*overflow: hidden;/s);
  assert.match(styles, /\.operations-monitor-page \{[^}]*gap: 0;[^}]*padding-bottom: 0;/s);
  assert.match(styles, /\.monitor-safety-panel \{[^}]*flex: 0 1 auto;/s);
  assert.match(styles, /\.risk-target-list \{[^}]*flex: 0 1 auto;/s);
  assert.match(styles, /\.monitor-event-strip \{[^}]*flex: 1 1 240px;[^}]*min-height: 240px;/s);
  assert.match(styles, /\.operations-card-switcher \{ margin-top: 0;/);
});

test('EVENT LIST uses OpenBridge event-list with projected timeline data', () => {
  assert.match(html, /id="monitor-event-heading">EVENT LIST</);
  assert.match(html, /<obc-event-list[^>]*id="liveEvents"/);
  assert.match(vendorEntry, /components\/event-list\/event-list\.js/);
  assert.match(app, /renderMonitorEventList\(proj\.timeline\?\.events \|\| \[\]\)/);
  assert.match(app, /MONITOR_HIDDEN_EVENT_TYPES = new Set\(\['planner_solved'\]\)/);
  assert.match(app, /filter\(\(event\) => !MONITOR_HIDDEN_EVENT_TYPES\.has\(event\?\.type\)\)/);
  assert.match(app, /case 'goal_reached':/);
  assert.match(app, /function monitorEventTone\(event\)/);
  assert.match(app, /item\.dataset\.eventTone = tone/);
  assert.match(app, /item\.dataset\.eventStatusTone = statusTone/);
  assert.match(app, /header\.className = 'event-title-line'/);
  assert.match(app, /body\.className = 'event-body-line'/);
  assert.match(app, /eventItemType: 'doubleLine'/);
  assert.match(app, /description: startTime/);
  assert.match(app, /decorateMonitorEventItems\(eventList, visibleEvents\)/);
  assert.match(styles, /overflow-y: scroll/);
  assert.match(styles, /--global-typography-ui-label-font-size: 12px/);
  assert.match(app, /colorCoded/);
  assert.doesNotMatch(app, /eventList\.innerHTML/);
});

test('海图显示 restores the pre-OpenBridge legend and layer controls in an OpenBridge popover', () => {
  assert.match(html, /id="chartLayersBtn"[^>]*aria-label="海图显示"[^>]*aria-controls="chartDisplayPopover"/);
  assert.match(html, /<section[^>]*class="chart-display-popover"[^>]*id="chartDisplayPopover"[^>]*role="dialog"/);
  assert.doesNotMatch(html, /id="toggleENC"/);
  assert.match(html, /id="closeChartDisplayBtn"/);
  assert.match(html, /data-legend-group="perception"[\s\S]*data-legend-group="risk"/);
  assert.match(html, /data-legend-group="risk"[\s\S]*<span class="legend-category-title">目标<\/span>/);
  assert.doesNotMatch(html, /<span class="legend-category-title">目标状态<\/span>/);
  assert.match(html, /<legend>感知<\/legend>[\s\S]*<legend>算法<\/legend>/);
  assert.doesNotMatch(html, /<legend>感知调试<\/legend>/);
  assert.match(html, />探测圈<\/span>/);
  assert.match(html, /id="response-range-legend-label">安全区</);
  assert.match(html, /id="response-range-control-label">安全区</);
  assert.doesNotMatch(html, /雷达探测圈（2 km）|雷达探测圈 2 km/);
  for (const layer of ['safeWater', 'ships', 'route', 'motionVectors', 'prediction', 'previousPrediction', 'radarRange', 'responseRange']) {
    assert.match(html, new RegExp(`data-layer="${layer}"`));
  }
  assert.match(app, /function setupChartDisplayPopover\(/);
  assert.match(app, /chartDisplayPopover/);
  assert.match(styles, /\.chart-display-popover\s*\{/);
  assert.match(styles, /width: min\(360px, calc\(100vw - 24px\)\)/);
  assert.match(styles, /bottom: calc\(100% \+ var\(--s-2\) \+ var\(--s-3\)\)/);
  assert.match(styles, /var\(--ob-surface\) 74%, transparent/);
  assert.match(styles, /grid-template-rows: 16px repeat\(2, minmax\(20px, 1fr\)\)/);
});

test('situation display uses black target motion vectors and risk-driven ship outlines', () => {
  assert.match(situationDisplay, /drawMotionVector\(target, '#111817', true\)/);
  assert.match(situationDisplay, /drawDoubleChevron\(ctx, end, course\);/);
  assert.doesNotMatch(situationDisplay, /drawArrowHead/);
  assert.doesNotMatch(situationDisplay, /drawThreatRings/);
  assert.match(situationDisplay, /const OWNSHIP_OUTLINE_COLOR = '#123C70'/);
  assert.match(situationDisplay, /setTargetThreatLevels\(levels\)/);
  assert.match(situationDisplay, /threat\?\.outlineColor \|\| threat\?\.color/);
  assert.match(app, /situationDisplay\.setTargetThreatLevels\(targetThreatLevels\)/);
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
