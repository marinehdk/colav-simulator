import test from 'node:test';
import assert from 'node:assert/strict';
import { createDeploymentView } from '../../web_gui/modules/deployment-view.js';

const info = { ready: true, run_id: 'a', utm_zone: 33, horizontal_crs: 'EPSG:25833', hemisphere: 'north', display_height_reference: 'ellipsoid-zero-visual-only', origin_e: 39000, origin_n: 6956450, width: 6000, height: 6000 };
function harness(factory) {
  const frames = [], states = [], destroyed = [], sceneFrames = [];
  let orientation = 'north', selected = null, pan = 17;
  const chart = {
    getEncInfo: () => info, getOrientation: () => orientation,
    setOrientation(value) { orientation = value; },
    renderFrame(data, visible = true) { frames.push({ data, visible }); },
    captureView: () => ({ pan, orientation }), restoreView(view) { pan = view.pan; orientation = view.orientation; },
    recenterOwnship() { pan = 0; }, zoomIn() {}, zoomOut() {}, selectTarget(id) { selected = id; },
  };
  const makeScene = () => ({ render(p) { sceneFrames.push(p.raw); }, destroy() { destroyed.push(true); }, recenter() {}, zoom() {}, select() {} });
  const errors = [];
  const view = createDeploymentView({ chart, createScene: factory || (async () => makeScene()), onState: s => states.push(s), onError: e => errors.push(e) });
  view.beginSession('a');
  const push = (seq = 1, t = 0, run = 'a') => view.render({ raw: { run_id: run, seq, sim_time: t, os: { x: t, y: 4, psi: 0 }, presentation: { render_time_s: t } } });
  return { view, push, frames, sceneFrames, states, destroyed, errors, makeScene, get pan() { return pan; }, get selected() { return selected; } };
}

test('H/N/C/3D changes only display state and preserves chart framing over 20 switches', async () => {
  const h = harness(); h.push();
  for (let i = 0; i < 20; i++) { await h.view.toggle(); assert.equal(h.view.state().mode, '3d'); h.view.toggle(); assert.equal(h.pan, 17); }
  assert.equal(h.destroyed.length, 20);
  await h.view.toggle(); h.view.orientation('heading');
  assert.equal(h.view.state().orientation, 'heading'); assert.equal(h.view.state().mode, '2d');
  h.view.recenter(); assert.equal(h.pan, 0);
});

test('same sequence motion frames reach both display boundaries with the identical immutable data', async () => {
  const h = harness(); h.push(); await h.view.toggle();
  h.push(1, 0.025); h.push(1, 0.05);
  assert.equal(h.frames.at(-1).data, h.sceneFrames.at(-1));
  assert.equal(h.frames.at(-1).visible, false);
  assert.equal(h.view.state().frame.renderTime, 0.05);
  h.push(500, 10, 'previous-run'); assert.equal(h.view.state().frame.renderTime, 0.05);
});

test('cancelling pending entry destroys its late viewer and prevents duplicate creation', async () => {
  let resolve, count = 0;
  const h = harness(() => { count++; return new Promise(r => { resolve = r; }); });
  h.push(); const pending = h.view.toggle(); h.view.orientation('north');
  resolve(h.makeScene()); await pending;
  assert.equal(count, 1); assert.equal(h.destroyed.length, 1); assert.equal(h.view.state().mode, '2d');
});

test('replacement invalidates pending resources, frames and camera state', async () => {
  let resolve;
  const h = harness(() => new Promise(r => { resolve = r; })); h.push();
  const pending = h.view.toggle(); h.view.beginSession('b'); resolve(h.makeScene()); await pending;
  assert.equal(h.destroyed.length, 1); assert.equal(h.view.state().camera, 'bridge');
  h.push(); assert.equal(h.view.state().frame, null);
  assert.ok(h.view.state().unavailable);
});

test('initialization failure restores chart and exposes retry; destroy is safe for late resolution', async () => {
  const h = harness(async () => { throw new Error('GPU unavailable'); }); h.push(); await h.view.toggle();
  assert.equal(h.view.state().mode, '2d'); assert.equal(h.errors[0].message, 'GPU unavailable');
  assert.equal(h.pan, 17); h.view.destroy();
});

test('missing current geographic contract keeps 3D unavailable without invoking factory', async () => {
  let calls = 0; const h = harness(async () => { calls++; });
  await h.view.toggle(); assert.equal(calls, 0);
});
