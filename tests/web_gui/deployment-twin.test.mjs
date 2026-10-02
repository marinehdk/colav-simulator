import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { createDeploymentTwinViewport } from '../../web_gui/modules/deployment-twin.js?v=20261002-sensor-mode-v1';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');

/* ── A：Deployment twin 视口壳层（T 钮 + 视口 DOM + view-twin 接线） ─────────── */

test('Deployment display bar gains a T twin button right after 3D with full aria semantics', () => {
  const start = html.indexOf('<div class="map-mode-control" aria-label="海图视角">');
  assert.ok(start >= 0, 'chart view control exists');
  const control = html.slice(start, html.indexOf('</div>', start));
  assert.ok(control.indexOf('id="scene3dBtn"') >= 0 && control.indexOf('id="scene3dBtn"') < control.indexOf('id="twinViewportBtn"'),
    'T follows the 3D action');
  assert.match(control, /id="twinViewportBtn"[^>]*aria-label="数字孪生视景"[^>]*aria-pressed="false"[^>]*title="等待当前会话"[^>]*disabled>T<\/button>/);
});

test('twin viewport mirrors the 3D host substitution pattern (video + HUD + link spike, default hidden)', () => {
  assert.match(html, /<div id="deploymentTwinHost" class="deployment-twin-host" aria-label="数字孪生视景">/);
  assert.match(html, /<video id="deploymentTwinVideo" class="twin-video" autoplay playsinline muted aria-label="数字孪生像素流（当前验证实时视景）"><\/video>/);
  assert.match(html, /<input type="checkbox" id="twinLinkToggle" aria-label="海图↔孪生相机联动（Cesium 主，单向）">/);
  assert.match(html, /<div class="twin-link-pane" id="twinLinkPane" aria-label="联动主视口（Cesium）" hidden><\/div>/);
  assert.match(styles, /\.view-twin > \.deployment-twin-host \{ display: flex;/);
  assert.match(styles, /\.view-twin > #simCanvas, \.view-twin > #replayCanvas/);
});

test('app.js wires the twin button, live session attach and chart-only disabling for the twin state', () => {
  assert.match(app, /getElementById\('twinViewportBtn'\)\?\.addEventListener\('click'/);
  assert.match(app, /createDeploymentTwinViewport\(\{/);
  assert.match(app, /await viewport\.attach\(\)/, 'viewport self-attaches on entry (factory is the await seam)');
  assert.match(app, /sessionId: \(\) => currentRunId\(\)/, 'attach 活动会话 id 取自既有 live 状态');
  assert.match(app, /classList\.toggle\('view-twin', twin\)/);
  assert.match(app, /chartScaleInput'\)\.disabled = active \|\| twin/);
  assert.match(app, /item\.disabled = active \|\| twin \|\|/, 'data-chart-only 族在 twin 态同 3D 态禁用');
  assert.match(app, /createLinkScene: async \(\{ host, signal, onFailure, onCameraMoved \}\)/, '联动 spike 缝');
  assert.match(app, /onCameraMoved,\n/, 'camera.changed 透传（默认 undefined = 关）');
});

// Same ENC contract shape as deployment-view.test.mjs (geography fold needs it).
const info = { ready: true, run_id: 'a', utm_zone: 33, horizontal_crs: 'EPSG:25833', hemisphere: 'north', display_height_reference: 'ellipsoid-zero-visual-only', origin_e: 39000, origin_n: 6956450, width: 6000, height: 6000 };

/* ── fakes ─────────────────────────────────────────────────────────────────── */

function fakeBridgeClient() {
  const client = {
    sent: [],
    ready: false,
    attached: null,
    lastState: null,
    errorCount: 0,
    sendAttach(payload) { client.sent.push({ type: 'attach', ...payload }); },
    sendTheme(value) { client.sent.push({ type: 'theme', value }); },
    sendSensorMode(value) { client.sent.push({ type: 'sensor_mode', value }); },
    sendCameraFree({ east, north, height_m, yaw_deg, pitch_deg, fov_deg }) {
      client.sent.push({ type: 'camera_free', pos: { east, north, height_m }, yaw_deg, pitch_deg, fov_deg });
    },
    sendDetach() { client.sent.push({ type: 'detach' }); },
  };
  return client;
}

/** P3-S2 (spec #90): minimal [data-twin-sensor] group double (classList/aria/dataset). */
function fakeSensorGroup({ initialActive = null } = {}) {
  const buttons = ['eo', 'ir', 'lidar'].map(value => {
    const button = {
      dataset: { twinSensor: value },
      listeners: [],
      ariaPressed: null,
      activeState: value === initialActive,
      classList: {
        toggle(_cls, on) { button.activeState = Boolean(on); },
      },
      setAttribute(_key, value) { button.ariaPressed = value; },
      addEventListener(_type, fn) { button.listeners.push(fn); },
      click() { button.listeners.forEach(fn => fn()); },
    };
    return button;
  });
  return {
    buttons,
    of: value => buttons.find(button => button.dataset.twinSensor === value),
    querySelectorAll(selector) { return selector === '[data-twin-sensor]' ? buttons : []; },
    querySelector(selector) {
      if (String(selector).includes('.active')) return buttons.find(button => button.activeState) ?? null;
      return buttons[0] ?? null;
    },
  };
}

function fakeStreamFactory(client) {
  const calls = [];
  let closed = 0;
  const factory = options => {
    calls.push(options);
    return {
      // The real receiver fires onChannel when the twin-bridge DataChannel opens.
      ensureStream: async () => { options.onChannel?.(client); return { started: true }; },
      close: async () => { closed += 1; },
      get client() { return client; },
      get connectionState() { return 'streaming'; },
      get stream() { return null; },
    };
  };
  factory.calls = calls;
  factory.closedCount = () => closed;
  return factory;
}

function manualScheduler() {
  const timers = new Map();
  let next = 0;
  return {
    setInterval(fn) { const id = ++next; timers.set(id, fn); return id; },
    clearInterval(id) { timers.delete(id); },
    run() { for (const fn of [...timers.values()]) fn(); },
    get pending() { return timers.size; },
  };
}

function fakeCheckbox() {
  const listeners = [];
  return {
    checked: false,
    addEventListener(_type, fn) { listeners.push(fn); },
    set(checked) { this.checked = checked; listeners.forEach(fn => fn()); },
  };
}

function viewportHarness({
  sessionId = () => 'sess-1',
  ready = true,
  attached = null,
  sensorGroup = null,
  sensorModeEl = null,
} = {}) {
  const client = fakeBridgeClient();
  client.ready = ready;
  client.attached = attached;
  const factory = fakeStreamFactory(client);
  const scheduler = manualScheduler();
  const linkToggle = fakeCheckbox();
  const linkPane = { hidden: true };
  const statusEl = { textContent: '' };
  const errorEl = { hidden: true, textContent: '' };
  const linkScenes = [];
  let linkCameraMoved = null;
  const viewport = createDeploymentTwinViewport({
    video: { srcObject: null },
    linkPane,
    linkToggle,
    statusEl,
    errorEl,
    sensorGroup,
    sensorModeEl,
    sessionId,
    backendBase: 'http://127.0.0.1:8010',
    info,
    scheduler,
    streamClientFactory: factory,
    createLinkScene: async ({ host, onCameraMoved }) => {
      linkCameraMoved = onCameraMoved;
      const scene = { host, renders: 0, destroyed: 0, render() { scene.renders += 1; }, destroy() { scene.destroyed += 1; }, recenter() {}, zoom() {} };
      linkScenes.push(scene);
      return scene;
    },
  });
  return {
    viewport, client, factory, scheduler, linkToggle, linkPane, statusEl, errorEl,
    linkScenes, moved: raw => linkCameraMoved?.(raw), sensorGroup, sensorModeEl,
  };
}

/* ── A：live attach 语义（契约 §2：无 clock；时钟权威在后端） ─────────────────── */

test('live attach carries mode=live for the active session and never a clock message', async () => {
  const h = viewportHarness();
  await h.viewport.attach();
  assert.equal(h.factory.calls.length, 1, 'one stream client for the viewport');
  h.scheduler.run(); // attach-when-ready poll fires
  const attach = h.client.sent.find(message => message.type === 'attach');
  assert.ok(attach, 'attach sent once the bridge answers ready');
  assert.equal(attach.mode, 'live');
  assert.equal(attach.runId, 'sess-1');
  assert.equal(attach.backendBase, 'http://127.0.0.1:8010');
  assert.equal('replay' in attach, false, 'live attach has no replay span');
  assert.equal(h.client.sent.filter(message => message.type === 'clock').length, 0,
    'clock authority is the backend: the deployment twin never sends clock (contract §2)');
});

test('attach resolves the session id lazily at attach time', async () => {
  let session = 'first';
  const h = viewportHarness({ sessionId: () => session });
  await h.viewport.attach();
  session = 'second';
  h.scheduler.run();
  const attach = h.client.sent.find(message => message.type === 'attach');
  assert.equal(attach.runId, 'second', 'session id read when the channel opens, not at construction');
});

test('destroy detaches and tears the stream down', async () => {
  const h = viewportHarness();
  await h.viewport.attach();
  h.viewport.destroy();
  assert.equal(h.client.sent.at(-1).type, 'detach');
  assert.equal(h.factory.closedCount(), 1, 'pixel stream closed');
});

test('HUD chip renders from the projected twin state', async () => {
  const h = viewportHarness();
  await h.viewport.attach();
  h.viewport.client.lastState = { _receivedAt: Date.now(), stream: { state: 'ok', latency_ms: 12 }, fps: 60, sim_time: 4.5 };
  h.scheduler.run();
  assert.match(h.statusEl.textContent, /OK/);
  assert.match(h.statusEl.textContent, /60 FPS/);
});

/* ── C：Cesium↔Twin 联动 spike（默认关；单向 Cesium 主→Twin 从） ─────────────── */

test('link defaults to off: no companion scene, no subscribers, zero camera_free', async () => {
  const h = viewportHarness({ ready: true, attached: { run_id: 's', mode: 'live' } });
  await h.viewport.attach();
  assert.equal(h.viewport.linkOn, false);
  assert.equal(h.linkToggle.checked, false, 'switch default unchecked (index.html + state)');
  assert.equal(h.linkScenes.length, 0);
  h.scheduler.run();
  assert.equal(h.client.sent.filter(message => message.type === 'camera_free').length, 0);
});

test('link on creates the split-pane scene and folds camera changes into camera_free only when attached', async () => {
  const h = viewportHarness();
  await h.viewport.attach();
  h.linkToggle.set(true);
  await new Promise(resolve => setTimeout(resolve, 5)); // openLink async
  assert.equal(h.viewport.linkOn, true);
  assert.equal(h.linkScenes.length, 1);
  assert.equal(h.linkPane.hidden, false, 'split pane visible');

  h.moved({ lonDeg: 12.5, latDeg: 55.4, heightM: 100, headingRad: Math.PI, pitchRad: -0.5, fovRad: Math.PI / 3, aspect: 2 });
  assert.equal(h.client.sent.filter(message => message.type === 'camera_free').length, 0,
    'no anchor yet (not attached) → no message');

  h.client.ready = true;
  h.client.attached = { run_id: 'sess-1', mode: 'live', anchor: { east: 39000, north: 6956450 } };
  h.moved({ lonDeg: 12.5, latDeg: 55.4, heightM: 100, headingRad: Math.PI, pitchRad: -0.5, fovRad: Math.PI / 3, aspect: 2 });
  const free = h.client.sent.find(message => message.type === 'camera_free');
  assert.ok(free, 'camera.changed → camera_free once attached');
  assert.ok(Number.isFinite(free.pos.east) && free.pos.east > 30000, 'east folded to global UTM (attached.anchor frame)');
  assert.ok(Number.isFinite(free.pos.north) && free.pos.north > 6000000);
  assert.equal(free.pos.height_m, 100);
  assert.equal(free.yaw_deg, 180, 'compass heading → Unity yaw');
  assert.ok(Math.abs(free.pitch_deg - (-0.5 * 180 / Math.PI)) < 1e-9, 'pitch 负=俯 pass-through');
  assert.ok(Math.abs(free.fov_deg - 2 * Math.atan(Math.tan(Math.PI / 6) / 2) * 180 / Math.PI) < 1e-9,
    'horizontal Cesium fov folded to Unity vertical fov');
});

test('link off destroys the companion scene and stops all messages (零消息零开销)', async () => {
  const h = viewportHarness({ ready: true, attached: { run_id: 's', mode: 'live' } });
  await h.viewport.attach();
  h.linkToggle.set(true);
  await new Promise(resolve => setTimeout(resolve, 5));
  h.moved({ lonDeg: 12.5, latDeg: 55.4, heightM: 100, headingRad: 0, pitchRad: 0, fovRad: 1, aspect: 2 });
  const sentWhileOn = h.client.sent.filter(message => message.type === 'camera_free').length;

  h.linkToggle.set(false);
  assert.equal(h.linkScenes[0].destroyed, 1, 'companion scene destroyed');
  assert.equal(h.linkPane.hidden, true, 'split pane hidden');
  assert.equal(h.linkToggle.checked, false, 'switch reflected back off');
  assert.equal(h.viewport.linkOn, false);

  const after = h.viewport.cameraFreeSent;
  h.scheduler.run();
  assert.equal(h.viewport.cameraFreeSent, after, 'off = zero further camera_free');
  assert.ok(h.client.sent.filter(message => message.type === 'camera_free').length >= sentWhileOn);
});

test('render feeds only the companion scene and only while the link is on', async () => {
  const h = viewportHarness();
  await h.viewport.attach();
  h.linkToggle.set(true);
  await new Promise(resolve => setTimeout(resolve, 5));
  const projection = { raw: { run_id: 'a', seq: 1 } };
  h.viewport.render(projection);
  assert.equal(h.linkScenes[0].renders, 1);
  h.linkToggle.set(false);
  h.viewport.render(projection);
  assert.equal(h.linkScenes[0].renders, 1, 'off = companion gets nothing');
});

test('link scene failure clears the toggle back to off', async () => {
  const client = fakeBridgeClient();
  const scheduler = manualScheduler();
  const linkToggle = fakeCheckbox();
  const linkPane = { hidden: true };
  const viewport = createDeploymentTwinViewport({
    linkPane, linkToggle, scheduler, streamClientFactory: fakeStreamFactory(client),
    sessionId: () => 's', info,
    createLinkScene: async () => { throw new Error('GPU gone'); },
  });
  linkToggle.set(true);
  await new Promise(resolve => setTimeout(resolve, 5));
  assert.equal(viewport.linkOn, false, 'failed companion resets the link');
  assert.equal(linkToggle.checked, false);
  assert.equal(linkPane.hidden, true);
});

/* ── D：P3-S2 sensor_mode 按钮组（spec #90；contract twin-bridge-v1 §2/§8） ──── */

test('deployment twin shell exposes the sensor-mode button group with the frozen vocabulary', () => {
  const group = html.slice(html.indexOf('id="deploymentTwinSensorGroup"'), html.indexOf('id="twinLinkToggleWrap"'));
  assert.ok(group.length > 0, 'sensor group sits between the HUD and the link toggle');
  for (const mode of ['eo', 'ir', 'lidar']) {
    assert.match(group, new RegExp(`data-twin-sensor="${mode}"`), `${mode} button present`);
  }
  assert.match(html, /id="deploymentTwinSensorMode"[^>]*>SENSOR EO</, 'state-echo chip defaults to EO');
  assert.match(styles, /\.deployment-twin-sensor-group \{ position: absolute;/, 'group pinned over the video');
  assert.match(styles, /\.deployment-twin-sensor-mode \{ position: absolute;/, 'chip pinned over the video');
  assert.match(app, /sensorGroup: document\.getElementById\('deploymentTwinSensorGroup'\)/);
  assert.match(app, /sensorModeEl: document\.getElementById\('deploymentTwinSensorMode'\)/);
});

test('sensor-mode click sends the contract literal; §5 realignment rides the attach', async () => {
  const group = fakeSensorGroup({ initialActive: 'eo' });
  const chip = { textContent: '' };
  const h = viewportHarness({ sensorGroup: group, sensorModeEl: chip });
  await h.viewport.attach();
  h.scheduler.run(); // attach-when-ready poll
  const modes = h.client.sent.filter(message => message.type === 'sensor_mode');
  assert.deepEqual(modes, [{ type: 'sensor_mode', value: 'eo' }],
    'attach realignment sends the current group pick (default eo)');

  group.of('ir').click();
  const ir = h.client.sent.filter(message => message.type === 'sensor_mode').at(-1);
  assert.deepEqual(ir, { type: 'sensor_mode', value: 'ir' }, 'click sends the frozen literal');
  assert.equal(group.of('ir').activeState, true, 'optimistic pick flips the group');
  assert.equal(group.of('eo').activeState, false);

  h.viewport.destroy();
});

test('state echo is the authority: chip text and buttons mirror sensor_mode, lidar shows the S3 pending mark', async () => {
  const group = fakeSensorGroup();
  const chip = { textContent: '' };
  const h = viewportHarness({ sensorGroup: group, sensorModeEl: chip });
  await h.viewport.attach();
  h.client.lastState = { _receivedAt: Date.now(), stream: { state: 'ok', latency_ms: 0 }, fps: 60, sensor_mode: 'lidar' };
  h.scheduler.run(); // HUD tick
  assert.match(chip.textContent, /SENSOR LiDAR·S3 · PENDING S3/,
    '占位 UI 明示（契约 §2 注：渲染属 S3，按钮不禁用）');
  assert.equal(group.of('lidar').activeState, true);
  assert.equal(group.of('eo').activeState, false);
  h.client.lastState = { _receivedAt: Date.now(), stream: { state: 'ok', latency_ms: 0 }, sensor_mode: 'ir' };
  h.scheduler.run();
  assert.equal(chip.textContent, 'SENSOR IR', 'ir echo = plain IR chip');
  h.client.lastState = { _receivedAt: Date.now(), stream: { state: 'ok', latency_ms: 0 } };
  h.scheduler.run();
  assert.equal(chip.textContent, 'SENSOR EO', 'old Unity build (no field) falls back to the contract default');
});
