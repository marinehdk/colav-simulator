import test from 'node:test';
import assert from 'node:assert/strict';
import { routeRibbonQuads } from '../../web_gui/modules/route-3d.js';
import { ROUTE_CORRIDOR_HALF_WIDTH_M, routeCorridorBoundaries } from '../../web_gui/modules/situation-display.js';

test('3D ribbon follows both 2D boundaries including the shared join at a turn', () => {
  const route = [[0, 1000, 1000], [0, 0, 1200]];
  const quads = routeRibbonQuads(route), boundaries = routeCorridorBoundaries(route);
  assert.equal(quads.length, 2);
  assert.deepEqual(quads[0], [boundaries.port[0], boundaries.port[1], boundaries.starboard[1], boundaries.starboard[0]]);
  assert.deepEqual(quads[0][1], quads[1][0]);
  assert.deepEqual(quads[0][2], quads[1][3]);
  assert.equal(Math.hypot(quads[0][0].north - quads[0][3].north, quads[0][0].east - quads[0][3].east), 2 * ROUTE_CORRIDOR_HALF_WIDTH_M);
  assert.deepEqual(route, [[0, 1000, 1000], [0, 0, 1200]]);
});

test('invalid coordinates and zero-length legs cannot create invalid world polygons', () => {
  for (const route of [null, [[], []], [[0], [0]], [[0, NaN], [0, 1]], [[0, 1], [0, Infinity]], [[0, 0], [0, 0]]]) assert.deepEqual(routeRibbonQuads(route), []);
  const quads = routeRibbonQuads([[0, 0, 1000], [0, 0, 1000]]);
  assert.equal(quads.length, 1);
  assert.ok(quads.flat().every(p => Number.isFinite(p.north) && Number.isFinite(p.east)));
});
