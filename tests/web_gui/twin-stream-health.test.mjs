import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  TWIN_SIGNALING_URL_DEFAULT,
  createTwinStreamHealthMonitor,
  projectTwinStreamHealth,
  probeSignalingReachable,
  signalingHttpUrl,
} from '../../web_gui/modules/twin-view.js?v=20261003-twin-health-v1';

const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const styles = await readFile(new URL('../../web_gui/style.css', import.meta.url), 'utf8');
const moduleSource = await readFile(new URL('../../web_gui/modules/twin-view.js', import.meta.url), 'utf8');
const deploymentSource = await readFile(new URL('../../web_gui/modules/deployment-twin.js', import.meta.url), 'utf8');
const appSource = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');

/* ── spec #91 前置批 B：twin 视口流健康状态卡（用户报障"Deployment 选 T 后视口无
   画面"的可视化）。纯状态机：signaling 可达 × video 状态 × 重试计数 → 文案；
   分层：信令挂 = 提示信令服务，信令通流无 = 提示 player 服务；流恢复 = 隐藏。 ── */

test('projectTwinStreamHealth hides the card while the video is connected', () => {
  const health = projectTwinStreamHealth({ signalingReachable: true, videoConnected: true, retryCount: 3 });
  assert.equal(health.visible, false, '流恢复 → 卡片自动隐藏');
  assert.equal(health.level, 'ok');
});

test('projectTwinStreamHealth layers the signaling-down hint (signaling service)', () => {
  const health = projectTwinStreamHealth({ signalingReachable: false, videoConnected: false, retryCount: 0 });
  assert.equal(health.visible, true);
  assert.equal(health.level, 'signaling-down');
  assert.equal(health.title, '孪生信令未连接');
  assert.match(health.detail, /twin-signaling/, '信令挂 → 提示信令服务（launchd twin-signaling）');
});

test('projectTwinStreamHealth waits without a retry count before the first watchdog retry', () => {
  const health = projectTwinStreamHealth({ signalingReachable: true, videoConnected: false, retryCount: 0 });
  assert.equal(health.visible, true);
  assert.equal(health.level, 'waiting');
  assert.equal(health.title, '孪生流端未连接');
  assert.match(health.detail, /twin-player/, '信令通流无 → 提示 player 服务');
  assert.doesNotMatch(health.title, /重试中/, '未重试前不显示计数');
});

test('projectTwinStreamHealth shows the retry counter while re-connecting (spec copy)', () => {
  const health = projectTwinStreamHealth({ signalingReachable: true, videoConnected: false, retryCount: 4 });
  assert.equal(health.level, 'retrying');
  assert.equal(health.title, '孪生流端未连接 · 重试中（第 4 次）', '任务书冻结文案');
  assert.match(health.detail, /twin-player/);
});

test('projectTwinStreamHealth keeps the player hint while signaling reachability is still unknown', () => {
  // 首个探针在途（reachable=null）不得当成"信令挂"——分层要求只在探针明确 false 时提示信令服务。
  const health = projectTwinStreamHealth({ signalingReachable: null, videoConnected: false, retryCount: 0 });
  assert.equal(health.level, 'waiting');
  assert.match(health.detail, /twin-player/);
});

test('signalingHttpUrl converts ws:// to http:// for the /config probe', () => {
  assert.equal(signalingHttpUrl('ws://127.0.0.1:8080'), 'http://127.0.0.1:8080');
  assert.equal(signalingHttpUrl(TWIN_SIGNALING_URL_DEFAULT), 'http://127.0.0.1:8080');
  assert.equal(signalingHttpUrl('http://x'), 'http://x', 'non-ws passthrough');
});

test('probeSignalingReachable maps ok/not-ok/network-error to true/false, never rejects', async () => {
  assert.equal(await probeSignalingReachable('ws://s:8080', async () => ({ ok: true })), true);
  assert.equal(await probeSignalingReachable('ws://s:8080', async () => ({ ok: false })), false);
  assert.equal(await probeSignalingReachable('ws://s:8080', async () => { throw new Error('ECONNREFUSED'); }), false);
  let probedUrl = null;
  await probeSignalingReachable('ws://s:8080', async url => { probedUrl = url; throw new Error('x'); });
  assert.equal(probedUrl, 'http://s:8080/config', 'probes the webapp /config route over http');
});

function makeMonitorHarness({ probeResult = true } = {}) {
  let clockMs = 1_000;
  const now = () => clockMs;
  const probeUrls = [];
  const healths = [];
  const retries = [];
  const monitor = createTwinStreamHealthMonitor({
    signalingUrl: 'ws://s:8080',
    now,
    probeEveryMs: 3_000,
    retryAfterMs: 5_000,
    probe: async url => { probeUrls.push(url); return probeResult; },
    onHealth: health => healths.push(health),
    onRetry: () => retries.push(clockMs),
    fetchRef: async () => { throw new Error('fetch must not be used (probe injected)'); },
  });
  return {
    monitor,
    healths,
    retries,
    probeUrls,
    advance: ms => { clockMs += ms; },
  };
}

test('monitor: healthy video emits a hidden card and resets the retry counter', () => {
  const harness = makeMonitorHarness();
  harness.monitor.tick(true);
  harness.monitor.tick(true);
  assert.deepEqual(harness.healths.map(h => h.visible), [false, false]);
  assert.equal(harness.monitor.retryCount, 0);
  assert.deepEqual(harness.retries, [], 'video up → no retry');
});

test('monitor: counts retries only after the retry timeout while signaling is reachable', () => {
  const harness = makeMonitorHarness();
  harness.monitor.tick(false);            // t=1s: first wait (probe fires)
  assert.equal(harness.monitor.retryCount, 0, 'timeout not yet elapsed — no retry');
  harness.advance(3_000);
  harness.monitor.tick(false);            // t=4s: probe resolved true; still waiting
  assert.equal(harness.monitor.retryCount, 0);
  harness.advance(2_000);
  harness.monitor.tick(false);            // t=6s: video down > 5s → retry #1
  assert.equal(harness.monitor.retryCount, 1);
  assert.equal(harness.retries.length, 1);
  const last = harness.healths.at(-1);
  assert.equal(last.level, 'retrying');
  assert.match(last.title, /重试中（第 1 次）/);
  harness.advance(1_000);
  harness.monitor.tick(false);            // t=7s: inside the retry spacing — no double fire
  assert.equal(harness.monitor.retryCount, 1);
  harness.advance(5_000);
  harness.monitor.tick(false);            // t=12s: retry #2
  assert.equal(harness.monitor.retryCount, 2);
  harness.monitor.tick(true);             // video recovers
  assert.equal(harness.monitor.retryCount, 0, 'recovery clears the counter');
  assert.deepEqual(harness.healths.at(-1), { visible: false, level: 'ok', title: '', detail: '' });
});

test('monitor: signaling down layers the signaling hint and suppresses retries', async () => {
  const harness = makeMonitorHarness({ probeResult: false });
  harness.advance(10_000);
  harness.monitor.tick(false);            // probe fires now (first tick)
  await new Promise(resolve => setImmediate(resolve)); // let the probe answer (microtask drain)
  harness.advance(10_000);
  harness.monitor.tick(false);
  assert.equal(harness.monitor.retryCount, 0, 'dead signaling cannot carry a retry');
  const last = harness.healths.at(-1);
  assert.equal(last.level, 'signaling-down');
  assert.match(last.detail, /twin-signaling/);
});

test('both twin viewports wire the health card markup and the watchdog', () => {
  // Deployment live twin host carries the card.
  assert.match(html, /id="deploymentTwinHealth"[^>]*hidden/, 'deployment twin viewport has the health card');
  assert.match(html, /id="twinHealth"[^>]*hidden/, 'evaluation twin viewer has the health card');
  assert.match(styles, /\.twin-health-card \{/, 'OpenBridge-style status card styles present');
  assert.match(styles, /twin-health-card\[data-level="signaling-down"\]/, 'signaling-down accent variant');
  // Evaluation controller drives the watchdog off the HUD cadence, viewer-open only.
  assert.match(moduleSource, /healthMonitor\.tick\(videoConnectedNow\(\)\)/);
  assert.match(moduleSource, /renderHealthCard/);
  // Deployment viewport drives it off its own HUD tick and the attach() failure path.
  assert.match(deploymentSource, /healthMonitor\.tick\(Boolean\(/, 'deployment HUD tick feeds the watchdog');
  assert.match(appSource, /healthEl: document\.getElementById\('deploymentTwinHealth'\)/, 'card element wired in app.js');
  assert.match(deploymentSource, /healthProbe = probeSignalingReachable/, 'probe injectable for hermetic tests');
});
