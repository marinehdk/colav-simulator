import test from 'node:test';
import assert from 'node:assert/strict';
import { createTwinCameraControls } from '../../web_gui/modules/twin-camera-controls.js';

function harness(yaw) {
  const events = new Map(), poses = [];
  const radians = Math.PI / 180;
  const pose = { east: -Math.sin(yaw * radians) * 200, north: -Math.cos(yaw * radians) * 200,
    height_m: 103, yaw_deg: yaw, pitch_deg: -30, fov_deg: 60 };
  const video = { addEventListener: (type, fn) => events.set(type, fn), removeEventListener() {},
    getBoundingClientRect: () => ({ width: 1600, height: 900 }) };
  const controls = createTwinCameraControls({ video, getClient: () => ({ attached: true, sendCameraFree: p => poses.push(p) }),
    getOwnship: () => ({ east: 0, north: 0, length: 45 }), getCameraPose: () => pose,
    scheduler: { setInterval: () => 1, clearInterval() {} } });
  const emit = (type, x, y) => events.get(type)({ pointerId: 1, button: 0, clientX: x, clientY: y });
  let x = 800, y = 450;
  return { pose, controls, click() { emit('pointerdown', x, y); emit('pointerup', x, y); }, drag(dx, dy) { emit('pointerdown', x, y); x += dx; y += dy; emit('pointermove', x, y); emit('pointerup', x, y); return poses.at(-1); } };
}
// Independent pinhole projection of a stationary sea-level landmark.
function project(p) {
  const yaw = p.yaw_deg * Math.PI / 180, pitch = p.pitch_deg * Math.PI / 180;
  const e = -p.east, n = -p.north, h = 3 - p.height_m;
  const forward = (e * Math.sin(yaw) + n * Math.cos(yaw)) * Math.cos(pitch) + h * Math.sin(pitch);
  const up = -(e * Math.sin(yaw) + n * Math.cos(yaw)) * Math.sin(pitch) + h * Math.cos(pitch);
  const right = e * Math.cos(yaw) - n * Math.sin(yaw);
  return { x: right / forward, y: -up / forward };
}
for (const yaw of [0, 90, 270]) {
  test(`left drag grabs the sea in screen direction at heading ${yaw}`, () => {
    const h = harness(yaw), initial = project(h.pose);
    const down = project(h.drag(0, 60));
    assert.ok(down.y > initial.y, 'drag down must move visible sea down, not up');
    const back = project(h.drag(0, -60));
    assert.ok(Math.abs(back.y - initial.y) < 1e-8, 'reverse drag restores framing');
    const right = project(h.drag(60, 0));
    assert.ok(right.x > initial.x, 'drag right moves visible sea right');
    h.controls.destroy();
  });
}

test('preset reset starts the next gesture at the latest rendered camera without a jump', () => {
  const h = harness(0);
  h.drag(80, 30);
  h.pose.east = 1000; h.pose.north = -900; h.pose.height_m = 150;
  h.controls.reset();
  const next = h.drag(0, 0);
  for (const field of ['east', 'north', 'height_m', 'yaw_deg', 'pitch_deg'])
    assert.ok(Math.abs(next[field] - h.pose[field]) < 1e-8, field);
  h.controls.destroy();
});

test('shallow overview sea grab moves the landmark by the requested pixels without crossing it', () => {
  const h = harness(0);
  Object.assign(h.pose, { north: -360, height_m: 82.2, pitch_deg: -8 });
  const initial = project(h.pose);
  const focal = 900 / (2 * Math.tan(Math.PI / 6));
  // Begin exactly over the landmark, as a user grabbing the ownship does.
  const events = new Map(), poses = [];
  const controls = createTwinCameraControls({
    video: { addEventListener: (t, f) => events.set(t, f), removeEventListener() {},
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 1600, height: 900 }) },
    getClient: () => ({ attached: true, sendCameraFree: p => poses.push(p) }),
    getOwnship: () => ({ east: 0, north: 0 }), getCameraPose: () => h.pose,
    scheduler: { setInterval() {}, clearInterval() {} },
  });
  const startY = 450 + initial.y * focal;
  for (const [type, y] of [['pointerdown', startY], ['pointermove', startY + 120], ['pointerup', startY + 120]])
    events.get(type)({ pointerId: 1, button: 0, clientX: 800, clientY: y });
  assert.ok(poses[0].north < 0, 'camera stays behind the grabbed landmark');
  assert.ok(Math.abs((project(poses[0]).y - initial.y) * focal - 120) < 1e-6);
  controls.destroy(); h.controls.destroy();
});

test('plain clicks do not freeze the pose of a moving tracked target', () => {
  const h = harness(0);
  h.click();
  h.pose.east += 100; h.pose.north += 200;
  const current = h.drag(0, 0);
  assert.ok(Math.abs(current.east - h.pose.east) < 1e-8);
  assert.ok(Math.abs(current.north - h.pose.north) < 1e-8);
  h.controls.destroy();
});
