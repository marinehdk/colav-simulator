import assert from 'node:assert/strict';
import test from 'node:test';

import {
  RADAR_FORWARD_HALF_ANGLE_RAD,
  buildRadarModel,
  createRadarMiniMap,
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

test('radar draws ownship solid and labels the 1 km and 2 km rings', () => {
  const calls = [];
  const attributes = {};
  const context = {
    setTransform() {},
    clearRect() {},
    save() { calls.push(['save']); },
    restore() { calls.push(['restore']); },
    beginPath() { calls.push(['beginPath']); },
    closePath() { calls.push(['closePath']); },
    moveTo() {},
    lineTo() {},
    arc() {},
    fill() {},
    stroke() { calls.push(['stroke']); },
    clip() {},
    translate(x, y) { calls.push(['translate', x, y]); },
    rotate(value) { calls.push(['rotate', value]); },
    setLineDash(values) { calls.push(['dash', ...values]); },
    fillText(value) { calls.push(['text', value]); },
  };
  const canvas = {
    clientWidth: 240,
    clientHeight: 240,
    width: 0,
    height: 0,
    getContext: () => context,
    setAttribute: (name, value) => { attributes[name] = value; },
  };
  const radar = createRadarMiniMap({ canvas });

  radar.render(buildRadarModel({ os: { x: 0, y: 0, psi: 0 }, obstacles: [] }, 2000));

  assert.deepEqual(calls.filter(([name]) => name === 'text').map(([, value]) => value).slice(-6), [
    'N', 'E', 'S', 'W', '1 km', '2 km',
  ]);
  const ownshipRotation = calls.findLastIndex(([name]) => name === 'rotate');
  const ownshipSolidDash = calls.findIndex((call, index) => index > ownshipRotation && call[0] === 'dash' && call.length === 1);
  assert.ok(ownshipSolidDash > ownshipRotation, 'ownship outline must clear the dashed heading-vector style');
  assert.match(attributes['aria-label'], /探测范围 2\.0 km/);
});
