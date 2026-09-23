import test from 'node:test';
import assert from 'node:assert/strict';
import { drawVODecisionDisc } from '../../web_gui/modules/situation-display.js';
import { voDiscRadiusM } from '../../web_gui/modules/scene-3d.js';

function recordingContext() {
  const fills = [];
  const context = {
    fillStyle: '', strokeStyle: '',
    save() {}, restore() {}, beginPath() {}, arc() {}, clip() {}, fillRect() {},
    moveTo() {}, lineTo() {}, closePath() {}, stroke() {}, fillText() {},
    fill() { fills.push(this.fillStyle); },
  };
  return { context, fills };
}

test('shared VO disc uses the solver candidate states and rejects incomplete grids', () => {
  const snapshot = {
    shape: [2, 4],
    speed_candidates_mps: [0, 4],
    heading_candidates_rad: [-Math.PI, -Math.PI / 2, 0, Math.PI / 2],
    candidate_state_bits: [1, 2, 4, 8, 0, 0, 0, 0],
    total_costs: [null, null, null, null, 1, 2, 3, 4],
    ownship_heading_rad: 0,
    current_velocity_ne_mps: [2, 0],
    reference_velocity_ne_mps: [4, 0],
    selected: { speed_mps: 4, heading_rad: 0 },
  };
  const { context, fills } = recordingContext();
  assert.equal(drawVODecisionDisc(context, snapshot, 120, 120, 110, 0, 0), true);
  assert.ok(fills.some(color => color.startsWith('rgba(227,78,89,')), 'hard constraint cells are red');
  assert.ok(fills.some(color => color.startsWith('rgba(240,201,77,')), 'WVO cells are yellow');
  assert.ok(fills.some(color => color.startsWith('rgba(217,107,255,')), 'COLREG cells are purple');
  assert.ok(fills.some(color => color.startsWith('rgba(47,191,113,')), 'available cells are green');
  const invalid = { ...snapshot, candidate_state_bits: [1] };
  assert.equal(drawVODecisionDisc(context, invalid, 120, 120, 110, 0, 0), false);
});

test('3D VO surface has vessel-scaled metres, independent of camera zoom', () => {
  assert.equal(voDiscRadiusM(44.1), 132.3);
  assert.equal(voDiscRadiusM(60), 180);
  assert.equal(voDiscRadiusM(null), null);
});
