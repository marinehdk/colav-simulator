import test from 'node:test';
import assert from 'node:assert/strict';
import { createDeploymentView } from '../../web_gui/modules/deployment-view.js?v=20261004-token-cleanup-v1';

const info = { ready: true, run_id: 'a', utm_zone: 33, horizontal_crs: 'EPSG:25833', hemisphere: 'north', display_height_reference: 'ellipsoid-zero-visual-only', origin_e: 39000, origin_n: 6956450, width: 6000, height: 6000 };
function harness(factory, twinFactory = null) {
  const frames = [], states = [], destroyed = [], sceneFrames = [], twinFrames = [], destroyedTwins = [], twinCalls = [], twinViewers = [];
  let orientation = 'north', selected = null, pan = 17;
  const chart = {
    getEncInfo: () => info, getOrientation: () => orientation,
    setOrientation(value) { orientation = value; },
    renderFrame(data, visible = true) { frames.push({ data, visible }); },
    captureView: () => ({ pan, orientation }), restoreView(view) { pan = view.pan; orientation = view.orientation; },
    recenterOwnship() { pan = 0; }, zoomIn() {}, zoomOut() {}, selectTarget(id) { selected = id; },
  };
  const makeScene = () => ({ render(p) { sceneFrames.push(p.raw); }, destroy() { destroyed.push(true); }, recenter() {}, zoom() {}, select() {} });
  const makeTwin = () => {
    const viewer = {
      renders: 0, zooms: [], recenters: 0,
      render(p) { viewer.renders += 1; twinFrames.push(p.raw); },
      destroy() { destroyedTwins.push(true); },
      recenter() { viewer.recenters += 1; },
      zoom(d) { viewer.zooms.push(d); },
    };
    twinViewers.push(viewer);
    return viewer;
  };
  const errors = [];
  const view = createDeploymentView({
    chart,
    createScene: factory || (async () => makeScene()),
    createTwin: twinFactory === null ? null : async options => { twinCalls.push(options); return twinFactory(options, makeTwin); },
    onState: s => states.push(s),
    onError: e => errors.push(e),
  });
  view.beginSession('a');
  const push = (seq = 1, t = 0, run = 'a') => view.render({ raw: { run_id: run, seq, sim_time: t, os: { x: t, y: 4, psi: 0 }, presentation: { render_time_s: t } } });
  return { view, push, frames, sceneFrames, twinFrames, states, destroyed, destroyedTwins, twinCalls, twinViewers, errors, makeScene, makeTwin, get pan() { return pan; }, get selected() { return selected; } };
}

test('H/N/C/3D changes only display state and preserves chart framing over 20 switches', async () => {
  const h = harness(); h.push();
  for (let i = 0; i < 20; i++) { await h.view.toggle(); assert.equal(h.view.state().mode, '3d'); h.view.toggle(); assert.equal(h.pan, 17); }
  assert.equal(h.destroyed.length, 20);
  await h.view.toggle(); h.view.orientation('heading');
  assert.equal(h.view.state().orientation, 'heading'); assert.equal(h.view.state().mode, '2d');
  h.view.recenter(); assert.equal(h.pan, 0);
});

test('each session enters 3D from the chase camera', async () => {
  const cameras = [];
  let selectCamera;
  const h = harness(async options => {
    cameras.push(options.camera); selectCamera = options.onCamera;
    return h.makeScene();
  });
  assert.equal(h.view.state().camera, 'chase');
  h.push(); await h.view.toggle();
  selectCamera('bridge'); h.view.toggle(); await h.view.toggle();
  assert.deepEqual(cameras, ['chase', 'chase']);
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
  assert.equal(h.destroyed.length, 1); assert.equal(h.view.state().camera, 'chase');
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

test('H/N aborts the factory before delayed engine assets can construct a viewer', async () => {
 let signal;
 const h=harness(options=>{signal=options.signal;return new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('cancelled'))));});
 h.push();const pending=h.view.toggle();h.view.orientation('heading');await pending;
 assert.equal(signal.aborted,true);assert.equal(h.errors.length,0);assert.equal(h.view.state().mode,'2d');
});

/* ── P2-S4 A：第三态 twin（live 像素流视口，createTwin 工厂缝） ──────────────── */

test('toggleTwin enters the twin state, forwards projections and exits restore the chart', async () => {
  const h = harness(null, (_options, makeTwin) => makeTwin());
  h.push();
  await h.view.toggleTwin();
  assert.equal(h.view.state().mode, 'twin');
  assert.equal(h.twinCalls.length, 1, 'twin factory called with enc info');
  assert.ok(h.twinCalls[0].info);
  h.push(2, 0.5);
  assert.equal(h.twinFrames.at(-1).seq, 2, 'projections reach the twin viewer');
  h.view.toggleTwin();
  assert.equal(h.view.state().mode, '2d');
  assert.equal(h.destroyedTwins.length, 1, 'exit destroys the twin viewer');
  assert.equal(h.frames.at(-1).visible, true, 'chart rendering resumes visible');
});

test('twin forwards zoom and recenter actions to the twin viewer, chart untouched', async () => {
  const h = harness(null, (_options, makeTwin) => makeTwin());
  h.push();
  await h.view.toggleTwin();
  h.view.zoom(1); h.view.zoom(-1); h.view.recenter();
  assert.deepEqual(h.twinViewers[0].zooms, [1, -1], 'zoom reaches the twin viewer');
  assert.equal(h.twinViewers[0].recenters, 1, 'recenter reaches the twin viewer');
  h.view.toggleTwin();
  assert.equal(h.pan, 17, 'chart pan untouched while twin was active');
});

test('3D and twin are mutually exclusive through the public toggles', async () => {
  const h = harness(null, (_options, makeTwin) => makeTwin());
  h.push();
  await h.view.toggleTwin();
  assert.equal(h.view.state().mode, 'twin');
  await h.view.toggle();
  assert.equal(h.view.state().mode, '2d', '3D toggle exits twin first');
  await h.view.toggle();
  assert.equal(h.view.state().mode, '3d');
  h.view.toggleTwin();
  assert.equal(h.view.state().mode, '2d', 'twin toggle exits 3D');
});

test('orientation and session replacement exit the twin viewport', async () => {
  const h = harness(null, (_options, makeTwin) => makeTwin());
  h.push();
  await h.view.toggleTwin();
  h.view.orientation('heading');
  assert.equal(h.view.state().mode, '2d');
  assert.equal(h.destroyedTwins.length, 1);
  await h.view.toggleTwin();
  h.view.beginSession('b');
  assert.equal(h.destroyedTwins.length, 2, 'beginSession exits twin');
});

test('twin state is unavailable without a factory and before a valid chart contract', async () => {
  const h = harness(); // no createTwin injected
  await h.view.toggleTwin();
  assert.equal(h.view.state().mode, '2d');
  const noChart = harness(null, (_options, makeTwin) => makeTwin());
  await noChart.view.toggleTwin(); // no projection yet → reason() gates entry
  assert.equal(noChart.view.state().mode, '2d');
  assert.equal(noChart.twinCalls.length, 0, 'factory not invoked');
});

test('late twin resolution after exit is destroyed instead of adopted', async () => {
  let resolve;
  const h = harness(null, () => new Promise(r => { resolve = r; }));
  h.push();
  const pending = h.view.toggleTwin();
  h.view.orientation('north'); // aborts the pending entry
  resolve(h.makeTwin());
  await pending;
  assert.equal(h.destroyedTwins.length, 1, 'late viewer destroyed');
  assert.equal(h.view.state().mode, '2d');
  assert.equal(h.errors.length, 0);
});
