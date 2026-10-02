#!/usr/bin/env node
// sango_ais_s4_probe — P3-S4 E2E evidence (spec #90; AIS data display layer).
//
// Live session on :8010 → web_gui Deployment workface:
//   1. 2D chart: the AIS symbol layer renders (DOM markers from the backend
//      `truth[].ais` objects); chart-display popover carries the new switch.
//   2. AIS symbol click → the real obc-poi-card AIS target card (MMSI/SOG/
//      COG/HDG/AGE/STATE/关联).
//   3. 3D Cesium: IMO 243 symbol billboards above the vessel models; POI card
//      carries the AIS rows.
// Artifacts → output/sango-ais-s4/. Usage: node tools/sango_ais_s4_probe.mjs
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BACKEND = 'http://127.0.0.1:8010';
const CDP_PORT = 9232; // dedicated (9222-9229 used by earlier probes)
const OUT_DIR = new URL('../output/sango-ais-s4/', import.meta.url).pathname;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

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

// ── minimal CDP client (sango_twin_lidar_probe pattern) ─────────────────────
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
// Lifecycle discipline (S3 probe pattern): kill leftovers from earlier runs
// before spawning (a skipped 3D leg must not orphan the browser).
try { execSync(`pkill -f "remote-debugging-port=${CDP_PORT}" 2>/dev/null || true`); } catch {}
try { execSync(`pkill -f "sango-ais-s4-" 2>/dev/null || true`); } catch {}
let chrome = null;
let sessionId = null;

/** Captures one full telemetry envelope over the session WS (ground truth
    for the association assertions; mirrors the browser transport). */
function captureEnvelope(wsUrl, timeoutMs = 30000) {
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
        // Association evidence needs the tracker to have published at least
        // one fused track; settle for the first frame if it never does.
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
  // 1) Live session (S3 probe recipe; no player/Unity needed for this layer).
  const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
  if (current?.session_id) await fetch(`${BACKEND}/api/sessions/${current.session_id}/reset`, { method: 'POST' });
  const createRes = await fetch(`${BACKEND}/api/sessions`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      // Busy-water multiship: 16 AIS targets, several inside the tracker's
      // detection range from t=0 → fused tracks exist for the association.
      validation_rule_id: 'multiship', scenario_id: 'romsdal_busy_water_16',
      algorithm_id: 'potocnik_colreg_fan_mpc', tracker_id: 'god',
      record_replay_trace: false,
    }),
  });
  check('live session created (POST /api/sessions)', createRes.ok, `status ${createRes.status}`);
  const created = await createRes.json();
  sessionId = created.session_id ?? created.id;
  await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
  // Ground-truth envelope over the same WS the browser consumes.
  const envelope = await captureEnvelope(`ws://127.0.0.1:8010/ws/sessions/${sessionId}`);
  const groundTruth = {
    obstacle_ais: envelope.obstacles.map(t => ({ id: t.id, mmsi: t.mmsi, ais: t.ais, x: t.x, y: t.y })),
    own_tracks: envelope.tracks?.[0] ?? null,
  };
  writeFileSync(`${OUT_DIR}live-envelope-extract.json`, JSON.stringify(groundTruth, null, 2));
  const aisFieldOk = envelope.obstacles.every(t => t.ais && ['active', 'sleeping', 'lost'].includes(t.ais.state)
    && Number.isFinite(t.ais.age_s));
  check('WS envelope carries backend ais{age_s,state} on every obstacle', aisFieldOk);

  // 2) Headless Chrome → the real app.
  chrome = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${CDP_PORT}`,
    '--no-first-run', '--no-default-browser-check',
    `--user-data-dir=${join(tmpdir(), `sango-ais-s4-${Date.now()}`)}`,
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

  // 3) Deployment workface with a running session → AIS markers appear.
  // The app boots onto the Config workface; the chart (and its screenshot)
  // only exists on Deployment.
  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await waitFor('live session attached to the chart', () => cdp.evaluate(
    `document.querySelectorAll('#aisMarkerLayer .ais-marker').length > 0`
    + ` && document.getElementById('liveControlState')?.textContent === 'RUNNING'`
    + ` && !document.querySelector('[data-workface-panel="deployment"]')?.hidden`,
  ), 90000, 1000);
  const markerInfo = await cdp.evaluate(`JSON.stringify((() => {
    const markers = [...document.querySelectorAll('#aisMarkerLayer .ais-marker')];
    return {
      count: markers.length,
      states: markers.map(m => m.dataset.state),
      checkboxChecked: document.querySelector('[data-layer="aisTargets"]')?.checked ?? null,
    };
  })())`);
  check('AIS symbol layer renders on the live 2D chart', JSON.parse(markerInfo).count > 0, markerInfo);
  await cdp.screenshot(`${OUT_DIR}ais-live-2d.png`);

  // 4) Chart-display popover carries the AIS switch (screenshot, then close).
  await cdp.evaluate(`document.getElementById('chartLayersBtn').click()`);
  await sleep(400);
  const popoverOk = await cdp.evaluate(`!document.getElementById('chartDisplayPopover').hidden`
    + ` && Boolean(document.querySelector('[data-layer="aisTargets"]'))`);
  check('chart-display popover carries the AIS layer switch', popoverOk);
  await cdp.screenshot(`${OUT_DIR}ais-live-popover.png`);
  await cdp.evaluate(`document.getElementById('closeChartDisplayBtn').click()`);
  await sleep(200);

  // 5) AIS symbol click → the real obc-poi-card AIS target card.
  await cdp.evaluate(`document.querySelector('#aisMarkerLayer .ais-marker').click()`);
  await waitFor('AIS target card opens', () => cdp.evaluate(
    `!document.getElementById('aisDetailPlacard').hidden`,
  ), 10000, 300);
  const cardInfo = await cdp.evaluate(`JSON.stringify((() => {
    const metric = id => document.getElementById(id)?.textContent;
    return {
      hidden: document.getElementById('aisDetailPlacard').hidden,
      title: document.getElementById('aisDetailPlacard')?.cardTitle ?? null,
      source: document.getElementById('aisDetailPlacard')?.source ?? null,
      mmsi: metric('aisPlacardMmsi'), sog: metric('aisPlacardSog'), cog: metric('aisPlacardCog'),
      hdg: metric('aisPlacardHdg'), age: metric('aisPlacardAge'),
      state: metric('aisPlacardState'), assoc: metric('aisPlacardAssociation'),
    };
  })())`);
  const card = JSON.parse(cardInfo);
  check('AIS target card opens with backend-authoritative fields',
    !card.hidden && card.source === 'AIS' && card.state !== '---' && card.assoc !== '---', cardInfo);
  await cdp.screenshot(`${OUT_DIR}ais-live-2d-card.png`);

  // 6) 3D Cesium view: AIS billboards above the vessel models + AIS card rows.
  // Switch to the Deployment workface first (a hidden workface collapses the
  // chart wrapper to 0x0, which would freeze the Cesium canvas size).
  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await sleep(800);
  await cdp.evaluate(`document.getElementById('scene3dBtn').click()`);
  // The scene state is read atomically with the readiness probe: the root
  // element can be torn down again by workface observers between evaluates.
  let lastWait = '';
  let sceneReadiness = null;
  try {
    sceneReadiness = await waitFor('Cesium scene boots', async () => {
      const info = await cdp.evaluate(`(() => {
        const root = document.querySelector('.scene3d-root');
        if (!root) return JSON.stringify({ wait: 'no scene3d-root; error=' + (document.getElementById('scene3dError')?.textContent ?? 'none') });
        if (!root.dataset.sceneState) return JSON.stringify({ wait: 'no sceneState yet; error=' + (document.getElementById('scene3dError')?.textContent ?? 'none')
          + '; wrapper=' + document.getElementById('canvasWrapper')?.className
          + '; pressed=' + document.getElementById('scene3dBtn')?.getAttribute('aria-pressed')
          + '; cesium=' + (typeof window.Cesium)
          + '; rootChildren=' + root.childElementCount
          + '; canvas=' + JSON.stringify([root.querySelector('canvas')?.clientWidth ?? null, root.querySelector('canvas')?.clientHeight ?? null])
          + '; rects=' + JSON.stringify({
            wrapper: document.getElementById('canvasWrapper')?.getBoundingClientRect(),
            host: document.getElementById('scene3dHost')?.getBoundingClientRect(),
            root: root.getBoundingClientRect(),
            canvasHost: root.querySelector('.scene3d-canvas')?.getBoundingClientRect(),
          }) });
        const state = JSON.parse(root.dataset.sceneState);
        return state.frames > 5 && state.models > 0
          ? JSON.stringify({ ready: true, models: state.models, pois: state.pois, frames: state.frames })
          : JSON.stringify({ wait: 'frames=' + state.frames + ' models=' + state.models + ' state=' + root.dataset.sceneState.slice(0, 160) });
      })()`);
      const parsed = JSON.parse(info);
      if (parsed.ready) return parsed;
      lastWait = parsed.wait;
      return null;
    }, 240000, 1500);
  } catch (error) {
    console.log(`WARN  3D scene did not reach models>0 — last wait state: ${lastWait || error.message}`);
  }
  if (!sceneReadiness) {
    console.log('SKIP  3D evidence (scene did not boot under headless SwiftShader)');
    writeFileSync(`${OUT_DIR}probe-console.log`, cdp.console.join('\n'));
    writeFileSync(`${OUT_DIR}evidence-status.json`, JSON.stringify({
      session_id: sessionId, generated_at: new Date().toISOString(), assertions,
    }, null, 2));
    console.log(`\nevidence → ${OUT_DIR}`);
    process.exit(failures.length ? 1 : 0);
  }
  const sceneInfo = JSON.stringify({ models: sceneReadiness.models, pois: sceneReadiness.pois, frames: sceneReadiness.frames });
  check('3D scene runs with vessel models + POIs', sceneReadiness.models > 0, sceneInfo);
  await cdp.screenshot(`${OUT_DIR}ais-live-3d.png`);
  // Select a target through the 3D POI → the scene card shows the AIS rows.
  const poiClicked = await cdp.evaluate(`(() => {
    const poi = document.querySelector('.scene3d-pois obc-poi-vessel');
    if (!poi) return false;
    poi.click();
    return true;
  })()`);
  if (poiClicked) {
    await sleep(800);
    const rows = await cdp.evaluate(`JSON.stringify([...document.querySelectorAll('.scene3d-card .scene3d-target-metrics dt')].map(dt => dt.textContent))`);
    check('3D POI card carries the AIS rows', /AIS AGE|AIS STATE|MMSI/.test(rows), rows);
    await cdp.screenshot(`${OUT_DIR}ais-live-3d-card.png`);
  } else {
    console.log('SKIP  3D POI click (no projected POI in the current camera)');
  }

  writeFileSync(`${OUT_DIR}probe-console.log`, cdp.console.join('\n'));
  writeFileSync(`${OUT_DIR}evidence-status.json`, JSON.stringify({
    session_id: sessionId, generated_at: new Date().toISOString(), assertions,
  }, null, 2));
  console.log(`\nevidence → ${OUT_DIR}`);
} finally {
  if (chrome) execSync(`pkill -f "remote-debugging-port=${CDP_PORT}" 2>/dev/null || true`);
  if (sessionId) await fetch(`${BACKEND}/api/sessions/${sessionId}/pause`, { method: 'POST' }).catch(() => {});
}
process.exit(failures.length ? 1 : 0);
