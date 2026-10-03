import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSceneCompass } from '../../web_gui/modules/scene-compass.js?v=20260923-follow-v1';

const rad = value => value * Math.PI / 180;
function projection(heading = 180, targets = []) {
  return { raw: { run_id: 'test', executed_tracker: 'god', os: { x: 0, y: 0, psi: rad(heading) }, obstacles: targets }, risk: { targets: [] } };
}
function target(id, bearing, heading, range = 1000) {
  return { id, generation: 1, x: range * Math.cos(rad(bearing)), y: range * Math.sin(rad(bearing)), psi: rad(heading) };
}

test('ownship heading readout wraps north and matches cardinal directions', () => {
  for (const [angle, label] of [[0, 'N 000°'], [90, 'E 090°'], [180, 'S 180°'], [270, 'W 270°'], [360, 'N 000°'], [-90, 'W 270°'], [359.9, 'N 000°']]) {
    assert.equal(buildSceneCompass(projection(angle)).label, label);
  }
  assert.equal(buildSceneCompass(null), null);
  const p = projection(); p.raw.os.psi = NaN; assert.equal(buildSceneCompass(p), null);
});

test('target compass location is bearing, while arrow rotation independently shows relative heading', () => {
  const model = buildSceneCompass(projection(180, [target(1, 270, 90), target(2, 90, 180), target(3, 0, 0)]));
  assert.equal(model.targets[0].bearing, 90);
  assert.equal(model.targets[0].x, 0.75);
  assert.equal(model.targets[0].heading, -90);
  assert.equal(model.targets[1].x, 0.25);
  assert.equal(model.targets[1].heading, 0);
  assert.equal(model.targets[2].bearing, -180);
  assert.equal(model.targets[2].x, 0, 'rear target stays represented at the compass seam');
  const seam = buildSceneCompass(projection(359, [target(1, 1, 1)])).targets[0];
  assert.ok(Math.abs(seam.bearing - 2) < 1e-10);
  assert.ok(Math.abs(seam.heading - 2) < 1e-10);
});

test('2 km inclusive filter uses displayed positions and excludes inactive or invalid targets', () => {
  const p = projection(0, [target(1, 0, 0, 2000), target(2, 0, 0, 2000.01), {...target(3, 0, 0), active: false}, {...target(4, 0, 0), x: NaN}]);
  assert.deepEqual(buildSceneCompass(p).targets.map(t => t.id), [1]);
  p.raw.executed_tracker = 'kf';
  p.raw.tracks = [{ labels: [2], generations: [1], states: [[100, 0, 0, 1]] }];
  assert.deepEqual(buildSceneCompass(p).targets.map(t => t.id), [2], 'use tracker position, not out-of-range truth');
});

test('canonical risk colors respect generation and unavailable evidence without CPA reclassification', () => {
  const p = projection(0, Array.from({length: 6}, (_, i) => target(i + 1, 45, 90)));
  p.risk.targets = [
    {targetId: 1, generation: 1, displayClass: 'CLEAR', dcpaM: 0},
    {targetId: 2, generation: 1, displayClass: 'LOW'},
    {targetId: 3, generation: 1, displayClass: 'HIGH'},
    {targetId: 4, generation: 2, displayClass: 'CLEAR'},
    {targetId: 5, generation: 1, displayClass: 'CLEAR', observationHealth: 'STALE'},
    {targetId: 6, generation: 1, displayClass: 'CLEAR', unavailableReasons: ['MISSING']},
  ];
  const targets = buildSceneCompass(p).targets;
  assert.deepEqual(targets.map(t => t.state), ['checked', 'caution', 'alarm', 'unchecked', 'unchecked', 'unchecked']);
  assert.deepEqual(targets.slice(0, 3).map(t => t.color), ['#16804B', '#B87800', '#D82828']);
  p.raw.obstacles[0].psi = NaN;
  assert.equal(buildSceneCompass(p).targets[0].heading, null, 'missing target heading is not invented');
});

test('profile qualification does not hide an available threat level and unchecked targets are white', () => {
  const p = projection(0, [target(1, 0, 0), target(2, 45, 0), target(3, 90, 0)]);
  p.risk.targets = [
    {targetId: 1, generation: 1, displayClass: 'CLEAR', unavailableReasons: ['PROFILE_UNQUALIFIED']},
    {targetId: 2, generation: 1, displayClass: 'HIGH', unavailableReasons: ['PROFILE_UNQUALIFIED']},
  ];
  const model = buildSceneCompass(p).targets;
  assert.deepEqual(model.map(item => item.state), ['checked', 'alarm', 'unchecked']);
  assert.deepEqual(model.map(item => item.color), ['#16804B', '#D82828', '#FFFFFF']);
});
