import assert from 'node:assert/strict';
import test from 'node:test';

const {
  interpolateAngle,
  interpolateVesselKinematics,
  lerpScalar,
} = await import(new URL('../../web_gui/modules/kinematics.js', import.meta.url).href);

test('lerpScalar interpolates linearly between known literals', () => {
  assert.equal(lerpScalar(0, 10, 0.5), 5);
  assert.equal(lerpScalar(-4, 6, 0.2), -2);
  assert.equal(lerpScalar(7, 7, 0.7), 7);
  assert.equal(lerpScalar(1, 3, 0), 1);
  assert.equal(lerpScalar(1, 3, 1), 3);
});

test('interpolateAngle takes the shortest angular path across the wrap', () => {
  // 359 deg -> 1 deg in radians must pass through 0 deg (north), not the long way.
  const wrapFrom = (359 * Math.PI) / 180;
  const wrapTo = (361 * Math.PI) / 180;
  const mid = interpolateAngle(wrapFrom, wrapTo, 0.5);
  assert.equal(Math.abs(((mid % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)) < 1e-9, true);

  // Plain increasing angle interpolates directly.
  assert.ok(Math.abs(interpolateAngle(0.1, 0.3, 0.5) - 0.2) < 1e-9);
  // Decreasing through zero: 0.1 -> -0.1 mid is 0.
  assert.ok(Math.abs(interpolateAngle(0.1, -0.1, 0.5)) < 1e-9);
  // Non-finite inputs fall back to the target angle.
  assert.equal(interpolateAngle(Number.NaN, 0.4, 0.5), 0.4);
});

test('interpolateVesselKinematics interpolates shared finite keys only', () => {
  const from = { x: 0, y: 0, psi: 3.0, sog: 2.0, r: 0.01 };
  const to = { x: 6, y: 6, psi: -3.0, sog: 4.0, id: 9 };
  const values = interpolateVesselKinematics(from, to, 0.5);
  // Linear keys are interpolated for keys finite in BOTH frames.
  assert.equal(values.x, 3);
  assert.equal(values.y, 3);
  assert.equal(values.sog, 3);
  // Heading/course take the shortest path: 3.0 -> -3.0 crosses +/-pi.
  assert.ok(Math.abs(Math.abs(values.psi) - Math.PI) < 1e-9);
  // 0.1 -> -0.1 crosses zero.
  assert.ok(Math.abs(interpolateVesselKinematics({ psi: 0.1 }, { psi: -0.1 }, 0.5).psi) < 1e-9);
  // Keys missing from one frame are not invented.
  assert.equal('r' in values, false);
  assert.equal('id' in values, false);
});
