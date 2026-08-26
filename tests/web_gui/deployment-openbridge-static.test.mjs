import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
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

test('three Workfaces occupy three equal centered columns', () => {
  assert.equal((html.match(/class="workface-tab(?: active)?" data-workface=/g) || []).length, 3);
  assert.match(styles, /\.workface-tabs \{[^}]*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(styles, /@media \(max-width: 520px\)[\s\S]*\.workface-tabs \{[^}]*grid-template-columns: repeat\(3, minmax\(88px, 1fr\)\)/);
});

test('AIS comparison is the third left information page, not a monitor panel', () => {
  assert.match(
    html,
    /class="ownship-info-page ownship-ais-page"[^>]*data-ownship-card-page="2"[\s\S]*?id="shadowComparisonPanel"/,
  );
  assert.match(html, /id="ownshipCardPosition" aria-label="第 1 张，共 3 张"[\s\S]*?aria-label="AIS"/);
  const monitorPage = html.match(/data-operations-card-page="0"[\s\S]*?<!-- Page 1: ALGO -->/)?.[0] || '';
  assert.doesNotMatch(monitorPage, /id="shadowComparisonPanel"/);
  assert.match(app, /shadowPanel\.hidden = false/);
  assert.doesNotMatch(app, /shadowPanel\.hidden = !shadowAvailable/);
});
