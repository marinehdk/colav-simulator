import assert from 'node:assert/strict';
import test from 'node:test';

import {
  RADAR_FORWARD_HALF_ANGLE_RAD,
  buildRadarModel,
} from '../../web_gui/modules/radar-mini-map.js';

test('radar model keeps only targets inside the canonical detection circle', () => {
  const snapshot = {
    os: { id: 0, x: 100, y: 200, psi: Math.PI / 4 },
    obstacles: [
      { id: 1, x: 1100, y: 200, cog: 0 },
      { id: 2, x: 100, y: 2200, cog: Math.PI / 2 },
      { id: 3, x: 2201, y: 200, cog: Math.PI },
      { id: 4, x: null, y: 200, cog: 0 },
    ],
  };

  const model = buildRadarModel(snapshot, 2000, { 1: 'danger', 2: 'warn' });

  assert.equal(model.rangeM, 2000);
  assert.equal(model.ownshipHeadingRad, Math.PI / 4);
  assert.equal(model.forwardHalfAngleRad, Math.PI / 3);
  assert.deepEqual(model.targets.map(target => target.id), [1, 2]);
  assert.deepEqual(model.targets[0], {
    id: 1,
    northFraction: 0.5,
    eastFraction: 0,
    headingRad: 0,
    riskLevel: 'danger',
  });
  assert.equal(model.targets[1].eastFraction, 1);
  assert.equal(model.targets[1].riskLevel, 'warn');
});

test('radar model preserves unknown risk instead of inferring a browser threat level', () => {
  const model = buildRadarModel({
    os: { x: 0, y: 0, psi: 0 },
    obstacles: [{ id: 7, x: 100, y: 100, psi: 0.2 }],
  }, 2000, {});

  assert.equal(RADAR_FORWARD_HALF_ANGLE_RAD, Math.PI / 3);
  assert.equal(model.targets[0].riskLevel, 'unknown');
  assert.equal(model.targets[0].headingRad, 0.2);
});
