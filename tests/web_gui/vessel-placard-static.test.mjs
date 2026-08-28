import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const index = readFileSync(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const app = readFileSync(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const display = readFileSync(new URL('../../web_gui/modules/situation-display.js', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const entry = readFileSync(new URL('../../web_gui/vendor/openbridge/entry-source.mjs', import.meta.url), 'utf8');

test('OpenBridge vessel marker and POI card components are vendored', () => {
  assert.match(entry, /ar\/chart-object-vessel-button\/chart-object-vessel-button\.js/);
  assert.match(entry, /ar\/poi-card\/poi-card\.js/);
});

test('Deployment provides target marker and anchored placard layers', () => {
  assert.match(index, /id="vesselMarkerLayer"/);
  assert.match(index, /<obc-poi-card[^>]*id="vesselDetailPlacard"/);
  assert.match(index, /id="vesselPlacardBearing"/);
  assert.match(index, /id="vesselPlacardRange"/);
  assert.match(index, /id="vesselPlacardDcpa"/);
  assert.match(index, /id="vesselPlacardTcpa"/);
});

test('Situation Display emits screen-space marker anchors without owning DOM cards', () => {
  assert.match(display, /onTargetMarkersChange/);
  assert.match(display, /drawnToScreen/);
  assert.match(display, /markerSink\?\.\(markers, \{ ownship: ownshipMarker \}\)/);
  assert.doesNotMatch(display, /document\.createElement\(['"]obc-poi-card/);
});

test('Deployment adapter renders marker components and canonical target metrics', () => {
  assert.match(app, /function renderVesselMarkers/);
  assert.match(app, /function showVesselPlacard/);
  assert.match(app, /obc-chart-object-vessel-button/);
  assert.match(app, /proj\.risk\?\.targets/);
  assert.match(app, /situationDisplay\.selectTarget/);
});

test('target marker centers the OpenBridge component exactly on the world anchor', () => {
  assert.match(styles, /\.vessel-marker \{[^}]*display: grid;[^}]*place-items: center;/s);
  assert.match(app, /marker\.anchor\.x - 32/);
  assert.match(app, /marker\.anchor\.y - 32/);
});

test('Risk rings are light-DOM one-pixel translucent circles, not native five-pixel alert rings', () => {
  assert.match(app, /state: 'enabled'/);
  assert.match(app, /host\.dataset\.riskState = marker\.state/);
  assert.match(styles, /\.vessel-marker::before[\s\S]*border: 1px solid currentColor/);
  assert.match(styles, /\.vessel-marker::after[\s\S]*opacity: \.28/);
});

test('ownship sprite does not add a second black contour around the icon', () => {
  const ownshipStart = display.indexOf('function drawOwnshipSprite');
  const targetStart = display.indexOf('function drawTargetSprite', ownshipStart);
  const ownshipSource = display.slice(ownshipStart, targetStart);
  assert.ok(ownshipStart >= 0 && targetStart > ownshipStart);
  assert.doesNotMatch(ownshipSource, /strokeShipContour/);
});

test('marker and placard follow interpolated anchors through compositor transforms only', () => {
  assert.match(app, /host\.style\.transform = `translate3d/);
  assert.doesNotMatch(app, /host\.style\.left =/);
  assert.doesNotMatch(app, /host\.style\.top =/);
  assert.match(app, /positionVesselPlacard\(selected\.anchor\)/);
  assert.doesNotMatch(app, /if \(selected\) showVesselPlacard/);
  assert.match(styles, /\.vessel-marker \{[^}]*will-change: transform;/s);
  assert.match(styles, /\.vessel-detail-placard \{[^}]*will-change: transform;/s);
});

test('placard compass symbol is geometrically centered under the N label', () => {
  assert.match(
    styles,
    /\.vessel-placard-dial obc-chart-object-vessel-button \{[^}]*position: absolute;[^}]*left: 50%;[^}]*top: 50%;[^}]*translate\(-50%, -50%\)/s,
  );
});
