import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { RADAR_DETECTION_RANGE_M } from '../../web_gui/modules/situation-display.js';
const source = readFileSync(new URL('../../web_gui/modules/scene-3d.js', import.meta.url), 'utf8');
const body = source.slice(source.indexOf('  function updateRings() {'), source.indexOf('  function updatePaths() {'));
function harness() {
  const geometry = new Map(), updates = [];
  const projection = {raw: {os: {x: 3000, y: 2200}}};
  const layers = {radarRange: {visible: true}};
  const chart = {getLayerState: () => layers};
  const line = (id, points) => {updates.push(points); geometry.set(id, {show: true});};
  const api = new Function('projection', 'chart', 'geometry', 'line', 'RADAR_DETECTION_RANGE_M', `
    let lastRingCenter = null;
    ${body}
    return { update: updateRings };
  `)(projection, chart, geometry, line, RADAR_DETECTION_RANGE_M);
  return {api, geometry, projection, layers, updates};
}

test('3D detection ring is one closed 2000 m circle with no bearing or range label entities', () => {
  const h = harness(); h.api.update();
  assert.equal(h.geometry.size, 1);
  const points = h.updates[0], os = h.projection.raw.os;
  points.forEach(([n,e]) => assert.ok(Math.abs(Math.hypot(n-os.x,e-os.y)-2000) < 1e-9));
  assert.ok(Math.hypot(points[0][0]-points.at(-1)[0],points[0][1]-points.at(-1)[1]) < 1e-9);
});

test('ring follows ownship and respects the shared chart radar layer', () => {
  const h = harness(); h.api.update(); h.api.update(); assert.equal(h.updates.length, 1);
  h.projection.raw.os.x += 100; h.api.update(); assert.equal(h.updates.length, 2);
  h.layers.radarRange.visible = false; h.api.update(); assert.equal(h.geometry.get('detection-ring').show, false);
  h.layers.radarRange.visible = true; h.api.update(); assert.equal(h.geometry.get('detection-ring').show, true);
});
