import assert from 'node:assert/strict';
import test from 'node:test';

import { routeLegs, routeProgress } from '../../web_gui/modules/route-progress.js';

test('route progress exposes a next leg before WPT2 and null on the final leg after WPT2', () => {
  const legs = routeLegs([[0, 100, 200], [0, 0, 0]]);

  const beforeWpt2 = routeProgress(legs, { n: 50, e: 0 });
  const afterWpt2 = routeProgress(legs, { n: 150, e: 0 });

  assert.equal(beforeWpt2.index, 0);
  assert.equal(beforeWpt2.nextLeg, legs[1]);
  assert.equal(afterWpt2.index, 1);
  assert.equal(afterWpt2.nextLeg, null);
});

test('malformed waypoint axes cannot produce partial route legs', () => {
  assert.deepEqual(routeLegs([[0, 100], [0]]), []);
  assert.deepEqual(routeLegs(null), []);
});
