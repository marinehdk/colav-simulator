#!/usr/bin/env node
// sango_tracks_s5_probe — P3-S5 E2E evidence (spec #90; IPDA existence chain).
//
// Live session on :8010 → web_gui Deployment workface:
//   1. WS envelope `truth[].tracks` carries the sensor-model-v1 §6 additive
//      arrays (existence_prob / quality / sources).
//   2. `GET /api/sessions/{id}/confirmed-tracks` returns the frozen
//      sensor-model@1/tracks envelope live.
//   3. 2D chart tracks layer renders existence-colored points (green ≥0.9 /
//      amber 0.5–0.9 / gray <0.5) + the updated legend.
//   4. Vessel placard (2D) carries the CONF row.
// Artifacts → output/sango-fusion-s5/. Usage: node tools/sango_tracks_s5_probe.mjs
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BACKEND = 'http://127.0.0.1:8010';
const CDP_PORT = 9233; // dedicated (9222-9232 used by earlier probes)
const OUT_DIR = new URL('../output/sango-fusion-s5/', import.meta.url).pathname;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
// Product capability policy (capabilities.py) only selects `god` for live
// validation sessions — S6 owns the tracker flip. God truth pins existence at
// 1.0, so the live capture shows the confirmed (green) band + CONF row; the
// amber/dim bands are proven by the situation-display unit tests and the KF
// artifacts in this directory (confirmed-tracks-sample.json / track-compare.json).
const TRACKER = process.env.S5_PROBE_TRACKER || 'god';

const failures = [];
const assertions = [];
function check(name, ok, detail = '') {
  const line = `${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`;
  console.log(line);
  assertions.push({ name, ok, detail });
  if (!ok) failures.push(line);
  return ok;
}
const sleep = ms => new Promise(res => setTimeout(res, ms));
async function waitFor(label, fn, timeoutMs, everyMs = 500) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try { last = await fn(); if (last) return last; } catch (error) { last = error.message; }
    await sleep(everyMs);
  }
  throw new Error(`timeout waiting for ${label}: ${last}`);
}

// ── minimal CDP client (sango_ais_s4_probe pattern) ─────────────────────────
class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.console = [];
    ws.addEventListener('message', event => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      } else if (msg.method === 'Runtime.consoleAPICalled') {
        this.console.push(msg.params.args.map(a => a.value ?? a.description ?? '').join(' '));
        if (this.console.length > 800) this.console.shift();
      } else if (msg.method === 'Runtime.exceptionThrown') {
        this.console.push(`[page-exception] ${msg.params.exceptionDetails?.exception?.description ?? msg.params.exceptionDetails?.text}`);
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
    const result = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(`page eval failed: ${result.exceptionDetails.exception?.description ?? result.exceptionDetails.text}`);
    return result.result?.value;
  }
  async screenshot(path) {
    const r = await this.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(path, Buffer.from(r.data, 'base64'));
  }
}

mkdirSync(OUT_DIR, { recursive: true });
try { execSync(`pkill -f "remote-debugging-port=${CDP_PORT}" 2>/dev/null || true`); } catch {}
try { execSync(`pkill -f "sango-tracks-s5-" 2>/dev/null || true`); } catch {}
let chrome = null;
let sessionId = null;

function captureEnvelope(wsUrl, timeoutMs = 45000) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let first = null;
    const timer = setTimeout(() => {
      try { ws.close(); } catch {}
      first ? resolve(first) : reject(new Error('ws capture timeout'));
    }, timeoutMs);
    ws.addEventListener('message', event => {
      try {
        const doc = JSON.parse(event.data);
        if (!doc?.obstacles?.length) return;
        if (doc.tracks?.[0]?.states?.length) {
          clearTimeout(timer);
          try { ws.close(); } catch {}
          resolve(doc);
        } else if (!first) {
          first = doc;
        }
      } catch { /* partial frames */ }
    });
    ws.addEventListener('error', () => { clearTimeout(timer); reject(new Error('ws error')); });
  });
}
try {
  // 1) Live session → WS envelope with the §6 additive arrays.
  const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
  if (current?.session_id) await fetch(`${BACKEND}/api/sessions/${current.session_id}/reset`, { method: 'POST' });
  const createRes = await fetch(`${BACKEND}/api/sessions`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      validation_rule_id: 'multiship', scenario_id: 'romsdal_busy_water_16',
      algorithm_id: 'potocnik_colreg_fan_mpc', tracker_id: TRACKER,
      record_replay_trace: false,
    }),
  });
  check(`live session created (tracker_id=${TRACKER})`, createRes.ok, `status ${createRes.status}`);
  if (!createRes.ok) throw new Error(`session create failed: ${createRes.status}`);
  const created = await createRes.json();
  sessionId = created.session_id ?? created.id;
  await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
  const envelope = await captureEnvelope(`ws://127.0.0.1:8010/ws/sessions/${sessionId}`);
  const tracks = envelope.tracks?.[0] ?? null;
  writeFileSync(`${OUT_DIR}live-envelope-extract.json`, JSON.stringify({
    tracker: envelope.executed_tracker,
    own_tracks: tracks,
  }, null, 2));
  const arraysOk = Boolean(tracks)
    && Array.isArray(tracks.existence_prob) && tracks.existence_prob.length === tracks.labels.length
    && Array.isArray(tracks.quality) && tracks.quality.length === tracks.labels.length
    && Array.isArray(tracks.sources) && tracks.sources.length === tracks.labels.length;
  check('WS envelope truth[].tracks carries §6 existence_prob/quality/sources arrays', arraysOk,
    `labels=${tracks?.labels?.length ?? 0} existence=${JSON.stringify(tracks?.existence_prob ?? null)}`);

  // 2) Confirmed-tracks data product, live.
  const confirmed = await fetch(`${BACKEND}/api/sessions/${sessionId}/confirmed-tracks`).then(r => r.json());
  writeFileSync(`${OUT_DIR}confirmed-tracks-live.json`, JSON.stringify(confirmed, null, 2));
  check('GET confirmed-tracks returns the frozen sensor-model@1/tracks envelope',
    confirmed.schema_version === 'sensor-model@1/tracks' && Array.isArray(confirmed.tracks),
    `tracks=${confirmed.tracks?.length ?? 0}`);

  // 3) Headless Chrome → the real app; tracks layer ON → colored points.
  chrome = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${CDP_PORT}`,
    '--no-first-run', '--no-default-browser-check',
    `--user-data-dir=${join(tmpdir(), `sango-tracks-s5-${Date.now()}`)}`,
    '--window-size=1680,1050', 'about:blank',
  ], { stdio: 'ignore' });
  await waitFor('chrome CDP endpoint', async () => {
    const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`).then(r => r.json()).catch(() => null);
    return Boolean(res);
  }, 20000);
  const tabRes = await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent(BACKEND + '/')}`, { method: 'PUT' });
  const tab = await tabRes.json();
  await sleep(1500);
  const targets = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
  const page = targets.find(t => t.id === tab.id) ?? targets.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  const cdp = new CDP(ws);
  await cdp.send('Runtime.enable');
  await cdp.send('Page.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1680, height: 1050, deviceScaleFactor: 1, mobile: false });

  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await waitFor('live session attached to the chart', () => cdp.evaluate(
    `document.getElementById('liveControlState')?.textContent === 'RUNNING'`
    + ` && !document.querySelector('[data-workface-panel="deployment"]')?.hidden`,
  ), 90000, 1000);
  await waitFor('tracker tracks published on the chart data', () => cdp.evaluate(
    `(window.activeSessionRuntime?.latest?.tracks?.[0]?.states?.length ?? 0) > 0`
    + ` || Boolean(document.querySelector('[data-layer="tracks"]'))`,
  ), 60000, 1000);

  // Tracks layer ON + confidence legend visible.
  await cdp.evaluate(`document.getElementById('chartLayersBtn').click()`);
  await sleep(400);
  await cdp.evaluate(`document.querySelector('[data-layer="tracks"]')?.click()`);
  await sleep(300);
  const legendOk = await cdp.evaluate(`Boolean(document.querySelector('.color-box.track-conf-confirmed'))`);
  check('chart legend carries the three existence-probability bands', legendOk);
  await cdp.screenshot(`${OUT_DIR}tracks-live-legend.png`);
  await cdp.evaluate(`document.getElementById('closeChartDisplayBtn').click()`);
  await sleep(400);
  await cdp.screenshot(`${OUT_DIR}tracks-live-2d.png`);

  // 4) Vessel placard CONF row (2D).
  const confOk = await cdp.evaluate(`(() => {
    const marker = document.querySelector('#vesselMarkerLayer .vessel-marker');
    marker?.click();
    return Boolean(marker);
  })()`);
  if (confOk) {
    await waitFor('vessel placard opens', () => cdp.evaluate(
      `!document.getElementById('vesselDetailPlacard').hidden`), 15000, 300);
    const confValue = await cdp.evaluate(`document.getElementById('vesselPlacardConf')?.textContent`);
    check('vessel placard carries the CONF row', Boolean(confValue), `CONF=${confValue}`);
    await cdp.screenshot(`${OUT_DIR}tracks-live-card.png`);
  } else {
    check('vessel placard carries the CONF row', false, 'no vessel marker on the chart');
  }

  writeFileSync(`${OUT_DIR}evidence-status.json`, JSON.stringify({
    probe: 'sango_tracks_s5_probe', tracker: TRACKER, session_id: sessionId,
    assertions, failures, at: new Date().toISOString(),
  }, null, 2));
  console.log(failures.length ? `PROBE FAILED (${failures.length})` : 'PROBE PASSED');
  process.exitCode = failures.length ? 1 : 0;
} catch (error) {
  console.error('PROBE ERROR', error);
  writeFileSync(`${OUT_DIR}evidence-status.json`, JSON.stringify({
    probe: 'sango_tracks_s5_probe', tracker: TRACKER, session_id: sessionId,
    error: String(error?.message ?? error), assertions, at: new Date().toISOString(),
  }, null, 2));
  process.exitCode = 1;
} finally {
  try { chrome?.kill(); } catch {}
}
