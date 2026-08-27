import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const index = readFileSync(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const app = readFileSync(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const display = readFileSync(new URL('../../web_gui/modules/situation-display.js', import.meta.url), 'utf8');
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
  assert.match(display, /markerSink\?\.\(markers\)/);
  assert.doesNotMatch(display, /document\.createElement\(['"]obc-poi-card/);
});

test('Deployment adapter renders marker components and canonical target metrics', () => {
  assert.match(app, /function renderVesselMarkers/);
  assert.match(app, /function showVesselPlacard/);
  assert.match(app, /obc-chart-object-vessel-button/);
  assert.match(app, /proj\.risk\?\.targets/);
  assert.match(app, /situationDisplay\.selectTarget/);
});
