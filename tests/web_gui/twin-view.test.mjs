import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  TWIN_BRIDGE_PROTOCOL,
  TWIN_CAMERA_PRESETS,
  TWIN_SENSOR_MODES,
  TWIN_SIGNALING_URL_DEFAULT,
  createTwinBridgeClient,
  createTwinClockDriver,
  projectTwinHud,
  themeValue,
  twinReplayRange,
} from '../../web_gui/modules/twin-view.js?v=20261003-twin-health-v1';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const moduleSource = await readFile(new URL('../../web_gui/modules/twin-view.js', import.meta.url), 'utf8');
const haisSource = await readFile(new URL('../../web_gui/modules/historical-ais-workbench.js', import.meta.url), 'utf8');

const RUN_ID = '3e19f9e6-741c-48b2-84bf-3ec5e90e1ceb';

/* ── frozen contract literals (sango/Docs/contracts/twin-bridge-v1.md §6;
   EditMode TwinBridgeMessageTests parses the same shapes) ── */

function recordingChannel() {
  const sent = [];
  return {
    sent,
    isOpen: () => true,
    send(json) { sent.push(json); },
  };
}

function fakeClock({ playhead = 0, rate = 1, state = 'PAUSED' } = {}) {
  return {
    get playhead() { return playhead; },
    get rate() { return rate; },
    get state() { return state; },
  };
}

/* ── shell wiring ── */

test('Evaluation left column exposes Digital Twin as view 02 with Results/Evidence/HAIS renumbered and disabled', () => {
  assert.match(html, /id="evalViewTabTwin"[^>]*data-eval-view="twin"[^>]*aria-pressed="false"/);
  assert.match(html, /id="evalViewTabTwin"[\s\S]{0,200}?<span class="step-circle">02<\/span><strong>Digital Twin<\/strong>/);
  assert.match(html, /id="evalViewTabReplay"[\s\S]{0,200}?<span class="step-circle">01<\/span><strong>Replay<\/strong>/);
  assert.match(html, /id="evalViewTabResults"[\s\S]{0,200}?<span class="step-circle">03<\/span><strong>Results<\/strong>/);
  assert.match(html, /id="evalViewTabEvidence"[\s\S]{0,200}?<span class="step-circle">04<\/span><strong>Evidence<\/strong>/);
  assert.match(html, /id="evalViewTabHistoricalAIS"[\s\S]{0,200}?<span class="step-circle">05<\/span><strong>Historical AIS<\/strong>/);
  assert.match(html, /id="evalViewTabResults"[^>]*disabled/);
  assert.match(html, /id="evalViewTabHistoricalAIS"[^>]*disabled/);
  assert.equal(html.includes('<strong>2 of 5 available</strong>'), true);
});

test('twin-view.js import specifier is unified across shell, deployment-twin and this file (one ES module instance)', async () => {
  const deploymentTwinSource = await readFile(new URL('../../web_gui/modules/deployment-twin.js', import.meta.url), 'utf8');
  const selfSource = await readFile(new URL('./twin-view.test.mjs', import.meta.url), 'utf8');
  const pattern = /twin-view\.js\?v=([^'"<>()\s]+)/g;
  const found = [];
  for (const [label, source] of [['index.html', html], ['deployment-twin.js', deploymentTwinSource], ['twin-view.test.mjs', selfSource]]) {
    const hits = [...source.matchAll(pattern)].map(match => match[1]);
    assert.ok(hits.length > 0, `${label} must reference twin-view.js`);
    found.push(...hits);
  }
  assert.equal(new Set(found).size, 1,
    `every twin-view.js import must share one ?v= specifier (ES module identity), got: ${[...new Set(found)].map(v => `?v=${v}`).join(', ')}`);
});

test('Digital Twin view section mirrors the replay viewer skeleton', () => {
  assert.match(html, /<section class="evaluation-view" id="evalViewTwin" aria-label="Digital Twin local view" hidden>/);
  for (const id of [
    'twinRunsPanel', 'twinRunsTable', 'twinRunsStatus', 'twinRunsRefreshBtn',
    'twinViewerPanel', 'twinVideo', 'twinHud', 'twinError', 'twinRunTitle', 'twinCloseBtn',
    'twinTimeline', 'twinTimeStart', 'twinTimeTotal', 'twinTimeCurrent',
    'twinPlayPauseBtn', 'twinStartBtn', 'twinRate05', 'twinRate1', 'twinRate5', 'twinRate20',
    'twinCameraGroup', 'twinDetectionSelect', 'twinStatusLine',
  ]) {
    assert.equal(html.includes(`id="${id}"`), true, `missing #${id}`);
  }
  // Camera preset vocabulary = frozen contract §2 (twin-only controls).
  for (const preset of TWIN_CAMERA_PRESETS) {
    assert.match(html, new RegExp(`data-twin-camera="${preset}"`));
  }
  // Playback rate group = contract clock rates offered by the UI (0.5–20×).
  for (const id of ['twinRate05', 'twinRate1', 'twinRate5', 'twinRate20']) {
    assert.equal(html.includes(`id="${id}"`), true);
  }
});

test('twin-view module is registered in the shell with the evaluation view registry including twin', async () => {
  assert.match(html, /src="\/static\/modules\/twin-view\.js\?v=/);
  assert.match(html, /src="\/static\/modules\/evaluation-replay\.js\?v=20261002-eval-twin-v1"><\/script>/);
  const replayModule = await readFile(new URL('../../web_gui/modules/evaluation-replay.js', import.meta.url), 'utf8');
  assert.equal(replayModule.includes("const evaluationViews = ['replay', 'twin', 'results', 'evidence', 'hais']"), true);
  // HAIS Open Replay keeps the SAME module URL as the shell (shared instance identity).
  assert.equal(haisSource.includes("from './evaluation-replay.js?v=20261002-eval-twin-v1'"), true);
});

test('twin styles: viewport height + pixel-stream video + HUD chip', () => {
  assert.match(styles, /#evalViewTwin\s*\{\s*height:\s*100%/);
  assert.match(styles, /\.twin-video\s*\{[^}]*object-fit:\s*contain/);
  assert.match(styles, /\.twin-hud\s*\{[^}]*position:\s*absolute/);
});

test('URS receiver modules are vendored locally (no CDN, one documented signaling patch)', async () => {
  const signaling = await readFile(new URL('../../web_gui/vendor/urs/signaling.js', import.meta.url), 'utf8');
  const readme = await readFile(new URL('../../web_gui/vendor/urs/README.md', import.meta.url), 'utf8');
  assert.equal(signaling.includes('explicitUrl = null'), true);
  assert.match(readme, /3\.1\.0-exp\.9/);
  assert.match(moduleSource, /import\('\.\.\/vendor\/urs\/renderstreaming\.js'\)/);
  assert.equal(/src\s*=\s*["']https?:\/\//.test(moduleSource), false, 'no CDN/http script sources in module');
  assert.equal(moduleSource.includes(TWIN_SIGNALING_URL_DEFAULT), true);
});

/* ── bridge client: message construction == frozen contract §6 literals ── */

test('bridge client builds hello/attach exactly as the frozen contract samples', () => {
  const channel = recordingChannel();
  const client = createTwinBridgeClient({ channel, now: () => 1000, page: 's3-probe' });

  const hello = client.sendHello('s3-probe');
  assert.equal(hello, JSON.stringify({ type: 'hello', protocol: TWIN_BRIDGE_PROTOCOL, page: 's3-probe' }));

  const attach = client.sendAttach({
    runId: RUN_ID,
    backendBase: 'http://127.0.0.1:8010',
    tStart: 0.1,
    tEnd: 40,
    trustedTEnd: 40,
  });
  assert.equal(attach, JSON.stringify({
    type: 'attach',
    run_id: RUN_ID,
    mode: 'replay',
    backend_base: 'http://127.0.0.1:8010',
    replay: { t_start: 0.1, t_end: 40, trusted_t_end: 40 },
  }));

  assert.equal(client.sent, 2);
  assert.equal(channel.sent.length, 2);
});

test('bridge client control messages: camera/theme/detection/detach match contract vocabulary', () => {
  const channel = recordingChannel();
  const client = createTwinBridgeClient({ channel });

  assert.equal(client.sendCamera('top'), '{"type":"camera","preset":"top"}');
  assert.equal(client.sendTheme('night'), '{"type":"theme","value":"night"}');
  assert.equal(client.sendDetection(true, 'truth'), '{"type":"detection","enabled":true,"source":"truth"}');
  assert.equal(client.sendDetection(false, 'truth'), '{"type":"detection","enabled":false,"source":"truth"}');
  assert.equal(client.sendDetach(), '{"type":"detach"}');
});

/* ── P3-S0 sensor_mode（契约 §8 演进，spec #90；EditMode TwinBridgeMessageTests 同源对拍） ── */

test('sensor_mode message matches the frozen contract §8 literal (只加 type 演进)', () => {
  assert.deepEqual(TWIN_SENSOR_MODES, ['eo', 'ir', 'lidar']);
  const channel = recordingChannel();
  const client = createTwinBridgeClient({ channel });
  assert.equal(client.sendSensorMode('ir'), '{"type":"sensor_mode","value":"ir"}');
  assert.equal(client.sendSensorMode('eo'), '{"type":"sensor_mode","value":"eo"}');
  assert.equal(client.sendSensorMode('lidar'), '{"type":"sensor_mode","value":"lidar"}');
  // Closed channel no-op, like every other message.
  const closed = createTwinBridgeClient({ channel: { ...recordingChannel(), isOpen: () => false } });
  assert.equal(closed.sendSensorMode('ir'), null);
});

test('bridge client clock: ~10Hz throttle while PLAYING, transitions always sent, force bypasses', () => {
  let now = 10_000;
  const channel = recordingChannel();
  const client = createTwinBridgeClient({ channel, now: () => now });

  // PAUSED with no prior state = transition, sent once.
  assert.match(client.sendClock(0.1, 1, 'PAUSED'), /"type":"clock"/);
  // PAUSED again (no transition) throttled.
  assert.equal(client.sendClock(0.1, 1, 'PAUSED'), null);
  // PLAYING transition sent immediately.
  assert.match(client.sendClock(0.2, 1, 'PLAYING'), /"state":"PLAYING"/);
  // 50 ms later: inside the 100 ms window -> throttled.
  now += 50;
  assert.equal(client.sendClock(0.25, 1, 'PLAYING'), null);
  // 101 ms later: cadence allows the next tick.
  now += 51;
  assert.match(client.sendClock(0.35, 1, 'PLAYING'), /"playhead_s":0.35/);
  // Rate change is sent immediately (force), even inside the window.
  now += 10;
  assert.match(client.sendClock(0.4, 5, 'PLAYING', { force: true }), /"rate":5/);
  // ENDED transition always sent.
  now += 200;
  assert.match(client.sendClock(40, 5, 'ENDED'), /"state":"ENDED"/);
  // Closed channel: no send.
  channel.isOpen = () => false;
  assert.equal(client.sendClock(40, 5, 'PLAYING', { force: true }), null);
});

test('clock driver maps a ReplayClock onto the bridge at the contract cadence', () => {
  let now = 0;
  const sent = [];
  const scheduler = {
    setInterval(fn, ms) { sent.push(`interval:${ms}`); return 7; },
    clearInterval() { sent.push('clear'); },
  };
  const channel = recordingChannel();
  const client = createTwinBridgeClient({ channel, now: () => now });
  const clock = fakeClock({ playhead: 1.5, rate: 2, state: 'PLAYING' });
  const driver = createTwinClockDriver({ clock, client, scheduler });

  driver.start();
  assert.deepEqual(sent, ['interval:100'], '10Hz contract cadence');
  assert.match(channel.sent.at(-1), /"type":"clock".*"playhead_s":1.5.*"rate":2.*"state":"PLAYING"/);

  // Rebound client (page binds after the channel opens) is picked up.
  const channel2 = recordingChannel();
  const client2 = createTwinBridgeClient({ channel: channel2, now: () => now });
  driver.client = client2;
  driver.pulse();
  assert.match(channel2.sent.at(-1), /"type":"clock"/);

  driver.stop();
  assert.equal(sent.includes('clear'), true);
});

/* ── bridge client: inbound Unity→web frames ── */

test('bridge client parses ready/attached/state and records HUD samples', () => {
  let now = 500;
  const client = createTwinBridgeClient({ channel: recordingChannel(), now: () => now });

  client.onMessage('{"type":"ready","protocol":"twin-bridge@1","build":"1.0","scene":"SangoTwin","modes_supported":["live","replay"]}');
  assert.equal(client.ready, true);

  client.onMessage(`{"type":"attached","run_id":"${RUN_ID}","mode":"replay","anchor":{"east":544302.5,"north":6323000.25},"ships":3,"camera":"bridge"}`);
  assert.equal(client.attached.run_id, RUN_ID);
  assert.equal(client.attached.anchor.east, 544302.5);
  assert.equal(client.attached.ships, 3);

  now = 600;
  client.onMessage('{"type":"state","fps":30.5,"frame_seq":41,"sim_time":12.4,"clock_skew_ms":35,"stream":{"state":"ok","latency_ms":35},"detection":{"source":"truth","enabled":true,"live":false},"camera":"bridge","sensor_mode":"eo"}');
  assert.equal(client.lastState.fps, 30.5);
  assert.equal(client.lastState.sim_time, 12.4);
  assert.equal(client.lastState.camera, 'bridge');
  assert.equal(client.lastState.detection.enabled, true, 'P3 演进只加字段（contract §8）：detection.enabled 宽松透传');
  assert.equal(client.lastState.sensor_mode, 'eo', 'P3-S0 演进只加字段（contract §8）：sensor_mode 回显默认 eo');
  assert.equal(client.samples.length, 1);
  assert.equal(client.samples[0].sim, 12.4);
  assert.equal(client.received, 3);

  // Malformed frame tolerated; REBUILD error recorded as non-fatal count.
  assert.equal(client.onMessage('not-json'), null);
  client.onMessage('{"type":"error","code":"REBUILD","message":"seq regression"}');
  assert.equal(client.errorCount, 1);
  assert.equal(client.lastError.code, 'REBUILD');
});

test('state frames without sensor_mode (old Unity build) still parse — only-additive evolution', () => {
  const client = createTwinBridgeClient({ channel: recordingChannel() });
  client.onMessage('{"type":"state","fps":30,"frame_seq":1,"sim_time":0.1,"clock_skew_ms":0,"camera":"bridge"}');
  assert.equal(client.lastState.sensor_mode, undefined, '缺字段 = 宽松消费默认（契约 §1 只加不减）');
});

/* ── HUD projection ── */

test('projectTwinHud: idle → attached-awaiting → live ok → degraded → down', () => {
  const fresh = nowMs => ({ _receivedAt: nowMs, stream: { state: 'ok', latency_ms: 35 }, fps: 30, sim_time: 12.4 });

  const idle = projectTwinHud({ connection: 'idle', client: null, nowMs: 1000 });
  assert.equal(idle.signal, 'idle');
  assert.equal(idle.statusLine, 'TWIN IDLE');

  const attaching = projectTwinHud({ connection: 'connecting', client: null, nowMs: 1000 });
  assert.equal(attaching.statusLine, 'TWIN CONNECTING…');
  const awaiting = projectTwinHud({ connection: 'streaming', client: null, nowMs: 1000 });
  assert.equal(awaiting.statusLine, 'TWIN ATTACHING…');

  const client = {
    attached: { run_id: RUN_ID },
    lastState: fresh(900),
  };
  const live = projectTwinHud({ connection: 'streaming', client, nowMs: 1000 });
  assert.equal(live.signal, 'ok');
  assert.equal(live.fps, 30);
  assert.equal(live.latencyMs, 35);
  assert.equal(live.simTime, 12.4);
  assert.match(live.statusLine, /TWIN LIVE · SIGNAL OK/);

  const degraded = projectTwinHud({
    connection: 'streaming',
    client: { attached: {}, lastState: { ...fresh(900), stream: { state: 'degraded', latency_ms: 400 } } },
    nowMs: 1000,
  });
  assert.equal(degraded.signal, 'degraded');

  const down = projectTwinHud({
    connection: 'streaming',
    client: { attached: {}, lastState: { ...fresh(900), stream: { state: 'down', latency_ms: 0 } } },
    nowMs: 1000,
  });
  assert.equal(down.signal, 'down');
  assert.match(down.statusLine, /TWIN ERROR|TWIN LIVE/);

  const stale = projectTwinHud({ connection: 'streaming', client, nowMs: 9000 });
  assert.equal(stale.signal, 'degraded', 'state older than 3s degrades the signal');
});

/* ── replay range (twin subset of the descriptor semantics) ── */

test('twinReplayRange mirrors Replay readiness semantics', () => {
  assert.deepEqual(twinReplayRange({ state: 'READY', t_start: 0.1, t_end: 40 }), { start: 0.1, end: 40 });
  assert.deepEqual(
    twinReplayRange({ state: 'INCOMPLETE', t_start: 0, t_end: 20, trusted_t_end: 12.5, seekable: true }),
    { start: 0, end: 12.5 },
  );
  assert.equal(twinReplayRange({ state: 'INCOMPLETE', t_start: 0, t_end: 20, trusted_t_end: 12.5, seekable: false }), null);
  assert.equal(twinReplayRange({ state: 'UNAVAILABLE', t_start: null, t_end: null }), null);
  assert.equal(twinReplayRange({ state: 'READY', t_start: 5, t_end: 1 }), null, 'end < start rejected');
});

/* ── theme sync ── */

test('themeValue maps the OpenBridge theme attribute onto the contract vocabulary', () => {
  assert.equal(themeValue('day'), 'day');
  assert.equal(themeValue('night'), 'night');
  assert.equal(themeValue('dusk'), 'dusk');
  assert.equal(themeValue('contrast'), null, 'unknown attribute ignored by the caller');
});

/* ── P2-S4：camera_free（契约 §8 演进记录）+ cameraFreePose 折算 + 流客户端抽取 ── */

import { cameraFreePose, createTwinStreamClient, TWIN_LINK_CHANGE_PERCENT } from '../../web_gui/modules/twin-view.js?v=20261003-twin-health-v1';

test('camera_free message matches the frozen contract §8 literal (只加字段演进)', () => {
  const channel = recordingChannel();
  const client = createTwinBridgeClient({ channel, page: 'deployment-twin' });
  client.sendHello('t4');
  const sent = client.sendCameraFree({
    east: 37012.5, north: 6955012.25, height_m: 120, yaw_deg: 45, pitch_deg: -35, fov_deg: 60,
  });
  assert.ok(sent, 'message handed to an open channel');
  assert.equal(channel.sent.at(-1),
    '{"type":"camera_free","pos":{"east":37012.5,"north":6955012.25,"height_m":120},"yaw_deg":45,"pitch_deg":-35,"fov_deg":60}');
});

test('camera_free send on a closed channel is a no-op like every other message', () => {
  const channel = recordingChannel();
  channel.isOpen = () => false;
  const client = createTwinBridgeClient({ channel });
  assert.equal(client.sendCameraFree({ east: 1, north: 2, height_m: 3, yaw_deg: 0, pitch_deg: 0, fov_deg: 60 }), null);
  assert.equal(channel.sent.length, 0);
});

test('cameraFreePose folds the Cesium camera into the contract payload (pure)', () => {
  const projectorCalls = [];
  const pose = cameraFreePose({
    lonDeg: 12.5, latDeg: 55.4, heightM: 120.5,
    headingRad: Math.PI / 2, pitchRad: -35 * Math.PI / 180, fovRad: Math.PI / 3, aspect: 16 / 9,
  }, (lon, lat) => { projectorCalls.push([lon, lat]); return [37012.5, 6955012.25]; });
  assert.deepEqual(projectorCalls, [[12.5, 55.4]], 'E/N come from the injected proj4 inverse');
  assert.equal(pose.east, 37012.5);
  assert.equal(pose.north, 6955012.25);
  assert.equal(pose.height_m, 120.5);
  assert.equal(pose.yaw_deg, 90, 'compass heading maps 1:1 to Unity yaw');
  assert.ok(Math.abs(pose.pitch_deg - -35) < 1e-9, 'pitch 负=俯 passes through');
  const expectedFov = 2 * Math.atan(Math.tan(Math.PI / 6) / (16 / 9)) * 180 / Math.PI;
  assert.ok(Math.abs(pose.fov_deg - expectedFov) < 1e-9, 'horizontal Cesium fov → vertical Unity fov');
});

test('cameraFreePose wraps yaw and keeps the fov vertical on tall panes', () => {
  const pose = cameraFreePose({
    lonDeg: 0, latDeg: 0, heightM: 0, headingRad: 3 * Math.PI, pitchRad: 0, fovRad: Math.PI / 3, aspect: 0.5,
  }, () => [0, 0]);
  assert.equal(pose.yaw_deg, 180, '540° wraps to 180°');
  assert.ok(Math.abs(pose.fov_deg - 60) < 1e-9, 'aspect < 1: Cesium fov already vertical');
  assert.deepEqual(Object.keys(pose), ['east', 'north', 'height_m', 'yaw_deg', 'pitch_deg', 'fov_deg']);
});

test('createTwinStreamClient extraction keeps the official receiver flow (source contract)', () => {
  assert.match(moduleSource, /export function createTwinStreamClient\(/);
  assert.match(moduleSource, /import\('\.\.\/vendor\/urs\/renderstreaming\.js'\)/);
  assert.match(moduleSource, /import\('\.\.\/vendor\/urs\/signaling\.js'\)/);
  assert.match(moduleSource, /rs\.createDataChannel\('input'\)/, 'S3 README §4②: receiver-side offer trigger');
  assert.match(moduleSource, /data\.channel\?\.label !== TWIN_BRIDGE_CHANNEL_LABEL/);
  assert.match(moduleSource, /sendHello\(`\$\{page === 'web_gui' \? 'twin' : page\}-\$\{now\(\)\}`\)/,
    'Evaluation hello nonce unchanged; deployment twin gets its own page tag');
  assert.match(moduleSource, /await current\.renderstreaming\.stop\?\.\(\)/, 'close() tears the PC down');
  assert.equal(TWIN_LINK_CHANGE_PERCENT, 0.01, 'camera.changed threshold per spike spec');
});

/* ── P3 残留清零批（spec #89 收尾）：channelOpen 失真修复 + twin 表翻页 ── */

test('debug.channelOpen reads the raw RTCDataChannel readyState (was always false via the client-only isOpen facade)', () => {
  // stream.channel 是裸 RTCDataChannel；isOpen() 门面只在桥客户端内部——旧实现
  // `channel.isOpen?.()` 恒 undefined → channelOpen 恒 false（诊断/探针失真）。
  assert.match(moduleSource, /debug\.channelOpen = streamCtl\?\.stream\?\.channel\?\.readyState === 'open'/);
  assert.doesNotMatch(moduleSource, /channelOpen = Boolean\(streamCtl\?\.stream\?\.channel\?\.isOpen/);
});

test('twin runs table paginates with the same footer controls and page sizes as replay (P3: target run on page 2 reachable)', () => {
  for (const id of ['twinRunsPaginationSummary', 'twinRunsPageSize', 'twinRunsPrevBtn', 'twinRunsPageIndicator', 'twinRunsNextBtn']) {
    assert.equal(html.includes(`id="${id}"`), true, `missing #${id}`);
  }
  assert.match(html, /<footer class="replay-runs-pagination" aria-label="Digital Twin pagination">/,
    'twin footer reuses the replay pagination controls/classes');
  const twinSelect = html.match(/id="twinRunsPageSize"[\s\S]*?<\/select>/)?.[0] ?? '';
  for (const size of ['10', '20', '50']) {
    assert.match(twinSelect, new RegExp(`<option value="${size}"`), `page size ${size} offered`);
  }
  assert.match(moduleSource, /slice\(pageStart, pageStart \+ twinRunsPageSize\)/,
    'table.data carries the current page slice (replay-runs.js renderReplayRuns semantics)');
  assert.match(moduleSource, /twinRunsNextBtn/, 'footer next control wired in twin-view.js');
  assert.match(moduleSource, /twinRunsPageSize/, 'page-size control wired in twin-view.js');
});

/* ── P3-S2 sensor_mode 按钮组（spec #90；contract §2/§8；Deployment twin 侧见 deployment-twin.test.mjs） ── */

test('sensorModeItems projects the frozen vocabulary; S3 un-pends lidar (pure)', async () => {
  const { sensorModeItems, TWIN_SENSOR_MODE_DEFAULT, projectSensorMode } = await import(
    '../../web_gui/modules/twin-view.js?v=20261003-twin-health-v1'
  );
  assert.deepEqual(TWIN_SENSOR_MODES, ['eo', 'ir', 'lidar']);
  assert.equal(TWIN_SENSOR_MODE_DEFAULT, 'eo');
  const items = sensorModeItems('ir');
  assert.deepEqual(items.map(item => [item.value, item.active]), [
    ['eo', false],
    ['ir', true],
    ['lidar', false],
  ], 'ir active; S3 起 lidar 无 pending 徽标（契约 §8 台账）');
  assert.equal(items.find(item => item.value === 'ir').label, 'IR');
  assert.equal(items.find(item => item.value === 'lidar').label, 'LiDAR', 'S2 的 "LiDAR·S3" 徽标移除（真实现）');
  assert.equal(items.find(item => item.value === 'lidar').pending, undefined, 'pending 字段不复存在');
  assert.deepEqual(sensorModeItems('bogus').find(item => item.active).value, 'eo', 'unknown mode falls back to the contract default');
  assert.equal(projectSensorMode({ sensor_mode: 'ir' }), 'ir', 'state echo is the authority');
  assert.equal(projectSensorMode({}), 'eo', 'old Unity build (missing field) = default');
  assert.equal(projectSensorMode({ sensor_mode: 'thermal' }), 'eo', 'out-of-vocabulary echo = default');
});

test('Evaluation twin footer wires the sensor-mode group, chip and echo path', () => {
  assert.match(moduleSource, /id="twinSensorGroup"|el\('twinSensorGroup'\)/, 'controller addresses the group');
  assert.match(html, /<div class="map-mode-control"[^>]*aria-label="Sensor mode \(main twin viewport\)" id="twinSensorGroup">/);
  const group = html.slice(html.indexOf('id="twinSensorGroup"'), html.indexOf('id="twinSensorMode"'));
  assert.match(group, /data-twin-sensor="eo"[^>]*aria-pressed="true"/);
  assert.match(group, /data-twin-sensor="ir"/);
  assert.match(group, /data-twin-sensor="lidar"/);
  assert.match(html, /<span class="deployment-control-state" id="twinSensorMode"[^>]*>SENSOR EO<\/span>/);
  assert.match(moduleSource, /requireClient\(\)\?\.sendSensorMode\(value\)/, 'click path sends the contract message');
  assert.match(moduleSource, /applySensorMode\(projectSensorMode\(client\?\.lastState\)\)/, 'HUD reasserts the authoritative echo');
  assert.match(moduleSource, /bridge\.sendSensorMode\(sensorActive\?\.dataset\.twinSensor \?\? TWIN_SENSOR_MODE_DEFAULT\)/,
    '§5 reconnect realignment re-sends the current mode');
  assert.match(moduleSource, /debug\.sensorMode = client\?\.lastState\?\.sensor_mode \?\? null/, 'probe debug seam carries the echo');
});
