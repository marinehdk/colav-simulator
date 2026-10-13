#!/usr/bin/env node
// twin_stability_monitor — DT 场景稳定性自动验收(M4 固化自 /tmp,路径仓库相对化)。
// 驱动真实 web_gui 页面(headless Chrome CDP)逐场景建 live session 并进 T 视口,
// 采样 a4000 player 日志:attach→warmup ready 时长、meshes 增量、M0 fps/frame_ms。
// 场景序列:head_on → overtaking → crossing_give_way → crossing_stand_on →
// paper multiship → head_on 回环(验证全场景域缓存命中)。
// 前置:8010 gui_server、8080 信令(转发 a4000)、renderer-ssh.sock 隧道、a4000 player 常驻。
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BACKEND = 'http://127.0.0.1:8010';
const CDP_PORT = 9225;
const REPO = new URL('../../../..', import.meta.url).pathname; // deploy/twin/gst/probe/ → 仓库根
const OUT_DIR = process.env.OUT_DIR || `${REPO}/output/twin-stability-${new Date().toISOString().slice(0, 10)}`;
const SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
  '-S', `${REPO}/deploy/twin/logs/renderer-ssh.sock`, 'a4000'];
const REMOTE_LOG = '/home/marine.huang/.local/share/colav-twin-renderer/logs/unity-player.log';
const RUN_WINDOW_S = 90;

const SCENARIOS = [
  { id: 'head_on', rule: 'rule14', label: 'HO' },
  { id: 'overtaking', rule: 'rule13', label: 'OT' },
  { id: 'crossing_give_way', rule: 'rule15', label: 'CS-GW' },
  { id: 'crossing_stand_on', rule: 'rule15', label: 'CS-SO' },
  { id: 'paper_ccta2023_multiship', rule: 'multiship', label: 'MS' },
  { id: 'head_on', rule: 'rule14', label: 'HO-revisit' },
];

const sleep = ms => new Promise(res => setTimeout(res, ms));
const sh = cmd => { try { return execSync(cmd, { encoding: 'utf8' }); } catch (e) { return e.stdout ?? ''; } };
const remoteLogLines = () => Number(sh(`${SSH.join(' ')} "wc -l < ${REMOTE_LOG}"`).trim() || 0);
const remoteLogSlice = (from, to) => sh(`${SSH.join(' ')} "sed -n '${from},${to}p' ${REMOTE_LOG}"`);

function parseMetrics(logText) {
  const fpsRows = [...logText.matchAll(/\[Sango\.M0\] fps=([\d.]+) frame_ms_avg=([\d.]+) frame_ms_max=([\d.]+)/g)]
    .map(m => ({ fps: +m[1], avg: +m[2], max: +m[3] }));
  const meshes = [...logText.matchAll(/meshes=(\d+)\//g)].map(m => +m[1]);
  const ready = /warmup=ready/.test(logText);
  const cesiumStates = [...logText.matchAll(/state=(\w+) terrain=([\d.]+)%.*warmup=(\w+)/g)].map(m => m[3]);
  const attachLine = /\[Sango\.TwinBridge\] attach run=/.test(logText);
  return {
    fpsRows, meshes, ready,
    warmupFailed: cesiumStates.includes('failed'),
    attachSeen: attachLine,
  };
}

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map();
    ws.addEventListener('message', event => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      }
    });
  }
  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.id;
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error(`CDP timeout ${method}`)); } }, 30000);
    });
  }
  async evaluate(expression) {
    const r = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (r.exceptionDetails) throw new Error(`page eval failed: ${r.exceptionDetails.text}`);
    return r.result?.value;
  }
}

async function waitFor(label, fn, timeoutMs, everyMs = 500) {
  const deadline = Date.now() + timeoutMs; let last;
  while (Date.now() < deadline) {
    try { last = await fn(); if (last) return last; } catch { /* transition */ }
    await sleep(everyMs);
  }
  throw new Error(`timeout: ${label} (last=${JSON.stringify(last)?.slice(0, 200)})`);
}

async function enterTwin(cdp, attempts = 4) {
  for (let a = 0; a < attempts; a++) {
    await cdp.evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b && !b.disabled) b.click(); return true; })()`);
    try {
      return await waitFor('video frames', () => cdp.evaluate(
        `(() => { const v = document.getElementById('deploymentTwinVideo'); return v && v.readyState >= 2 && v.videoWidth > 0 ? {w: v.videoWidth} : null; })()`), 45000);
    } catch { /* toggle off and retry */ await sleep(1000); }
  }
  throw new Error('enterTwin: no video after retries');
}

mkdirSync(OUT_DIR, { recursive: true });
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', '--no-default-browser-check', `--user-data-dir=${join(tmpdir(), `twin-stab-${Date.now()}`)}`,
  '--window-size=1680,1050', 'about:blank',
], { stdio: 'ignore' });
process.on('exit', () => { try { chrome.kill(); } catch {} });
await sleep(2500);

const targets = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent(BACKEND + '/')}`, { method: 'PUT' })).json();
const ws = new WebSocket(targets.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
const cdp = new CDP(ws);
await cdp.send('Runtime.enable');

const results = [];
let logCursor = remoteLogLines();
console.log(`log cursor starts at line ${logCursor}`);

for (const scenario of SCENARIOS) {
  const row = { ...scenario, status: 'RUNNING' };
  results.push(row);
  const t0 = Date.now();
  try {
    // leave twin if entered (previous scenario)
    await cdp.evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b) b.click(); return true; })()`).catch(() => {});
    await sleep(1200);

    const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
    if (current?.session_id) await fetch(`${BACKEND}/api/sessions/${current.session_id}/reset`, { method: 'POST' });

    const createRes = await fetch(`${BACKEND}/api/sessions`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ validation_rule_id: scenario.rule, scenario_id: scenario.id, algorithm_id: 'vo', tracker_id: 'god' }),
    });
    if (!createRes.ok) throw new Error(`create session ${createRes.status}`);
    const created = await createRes.json();
    const sessionId = created.session_id ?? created.id;
    await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
    row.session = sessionId.slice(0, 8);

    // fresh page bootstrap so the new session is adopted
    await cdp.send('Page.reload');
    await sleep(2500);
    await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
    await waitFor('T button enabled (session adopted)', () => cdp.evaluate(
      `(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`), 60000);

    logCursor = remoteLogLines(); // segment start (attach comes right after)
    const enterT0 = Date.now();
    await enterTwin(cdp);
    const attached = await waitFor('bridge attached', () => cdp.evaluate(
      `(() => { const d = window.__deploymentTwin; return d?.attached?.mode === 'live' ? d.attached : null; })()`), 90000);
    row.attachMs = Date.now() - enterT0;

    // wait for warmup ready (bounded), then sample the sailing window
    let warmReadyAt = null;
    const warmDeadline = Date.now() + 120000;
    while (Date.now() < warmDeadline) {
      const seg = remoteLogSlice(logCursor, remoteLogLines());
      if (/warmup=ready/.test(seg)) { warmReadyAt = Date.now(); break; }
      await sleep(3000);
    }
    row.warmupMs = warmReadyAt ? warmReadyAt - enterT0 : null;

    const windowStart = Date.now();
    while ((Date.now() - windowStart) / 1000 < RUN_WINDOW_S) {
      await cdp.evaluate(`(() => window.__deploymentTwin?.simTime ?? null)()`).catch(() => {});
      await sleep(5000);
    }
    row.simTime = await cdp.evaluate(`(() => window.__deploymentTwin?.simTime ?? null)()`);

    const logEnd = remoteLogLines();
    const seg = remoteLogSlice(logCursor, logEnd);
    const m = parseMetrics(seg);
    logCursor = logEnd;
    const fps = m.fpsRows.map(r => r.fps);
    row.fpsMin = fps.length ? Math.min(...fps) : null;
    row.fpsAvg = fps.length ? +(fps.reduce((a, b) => a + b, 0) / fps.length).toFixed(1) : null;
    row.spikeMax = m.fpsRows.length ? Math.max(...m.fpsRows.map(r => r.max)) : null;
    row.spikesOver45 = m.fpsRows.filter(r => r.max > 45).length;
    row.meshStart = m.meshes.length ? m.meshes[0] : null;
    row.meshEnd = m.meshes.length ? m.meshes[m.meshes.length - 1] : null;
    row.meshDelta = row.meshStart != null ? row.meshEnd - row.meshStart : null;
    row.ships = attached.ships;
    row.status = 'OK';
  } catch (error) {
    row.status = 'FAIL';
    row.error = String(error.message).slice(0, 200);
  }
  row.wallS = +((Date.now() - t0) / 1000).toFixed(0);
  console.log(`[${row.label}] ${row.status} attach=${row.attachMs ?? '-'}ms warmup=${row.warmupMs ?? 'none'}ms fps=${row.fpsMin ?? '-'}~${row.fpsAvg ?? '-'} spike=${row.spikeMax ?? '-'}ms meshes +${row.meshDelta ?? '-'} sim=${row.simTime ?? '-'} ${row.error ?? ''}`);
}

writeFileSync(join(OUT_DIR, 'stability-report.json'), JSON.stringify(results, null, 2));
const bad = results.filter(r => r.status !== 'OK');
const unstable = results.filter(r => r.status === 'OK' && (r.fpsMin === null || r.fpsMin < 27 || r.spikeMax > 120));
console.log(`\n=== SUMMARY: ${results.length - bad.length}/${results.length} ran, ${unstable.length} unstable ===`);
process.exit(bad.length || unstable.length ? 1 : 0);
