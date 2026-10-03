#!/usr/bin/env node
// sango_phase3_e2e_probe — P3-S6 full-sensor E2E + phase-3 completion proof (spec #90).
//
// Two live sessions on the radar_x-assembled head_on scenario:
//   Session A (explicit tracker_id="god", the retained fallback channel):
//     the god chain generates measurements from every wired sensor, so the
//     radar_x group reaches the telemetry measurement cache → radar_x cache
//     assertion + live PPI panel + AIS card + existence legend/CONF display
//     legs. (The external vimmjipda interface fuses the legacy Radar channel
//     only — upstream isinstance filter, external repo untouched by design.)
//   Session B (NO tracker_id — the flipped product default vimmjipda answers):
//     flip proof at the session boundary + YOLO → observations sensor_id=2
//     cache + twin sensor_mode loop eo→ir→lidar→eo + WS tracks §6 arrays with
//     measurement-driven existence probability + confirmed-tracks product.
// Chain: backend :8010 ← signaling :8080 ← player --sango-twin-bridge --sango-publisher
//        ← YOLO CPU forward ← headless Chrome CDP.
// Artifacts → output/sango-phase3-e2e/.
// Usage: node tools/sango_phase3_e2e_probe.mjs [--keep-chrome] [--keep-player] [--keep-yolo]
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { twinLaunchdPlayerDown, twinLaunchdPlayerUp } from './lib/twin_launchd.mjs'; // spec #91 前置批：launchd player 共处协议

const BACKEND = 'http://127.0.0.1:8010';
const SIGNALING = 'http://127.0.0.1:8080';
const CDP_PORT = 9234; // dedicated (9222-9233 used by earlier probes)
const OUT_DIR = new URL('../output/sango-phase3-e2e/', import.meta.url).pathname;
const PLAYER_BIN = new URL('../sango/Builds/sango-twin.app/Contents/MacOS/sango', import.meta.url).pathname;
const PLAYER_ARGS = ['--sango-twin-bridge', '--sango-publisher'];
const DETECTOR_BIN = new URL('../.venv-detector/bin/python', import.meta.url).pathname;
const DETECTOR_SCRIPT = new URL('./sango_detector_service.py', import.meta.url).pathname;
const OBS_WINDOW_MS = 240000;    // max wait for YOLO detections to land in the cache
const WS_TRACK_WINDOW_MS = 300000; // max wait for fusion tracks on the WS (radar pickup ~2 min in)
const DEFAULT_TRACKER = 'vimmjipda'; // the flipped product default (capabilities.py)

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

async function preflight(url, name) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    check(`preflight ${name}`, res.ok, `${url} -> ${res.status}`);
    return res.ok;
  } catch (error) {
    check(`preflight ${name}`, false, `${url} -> ${error.message}`);
    return false;
  }
}

// ── minimal CDP client (sango_twin_obs_probe pattern) ────────────────────────
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
async function openTab(url) {
  const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
  return res.json();
}
async function connectCDP() {
  const targets = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
  const page = targets.filter(t => t.type === 'page' && t.url.includes('127.0.0.1:8010')).pop();
  if (!page) throw new Error('no web_gui tab found');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  const cdp = new CDP(ws);
  await cdp.send('Runtime.enable');
  await cdp.send('Page.enable');
  return cdp;
}
async function waitFor(label, fn, timeoutMs, everyMs = 500) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try { last = await fn(); if (last) return last; } catch { /* page mid-transition */ }
    await sleep(everyMs);
  }
  throw new Error(`timeout waiting for ${label} (last=${JSON.stringify(last)?.slice(0, 300)})`);
}

/** Decoded <video> frame stats (obs/lidar-probe technique): grayscale mean/std,
 * channel spread (IR black-and-white proof), dark + lit fractions (lidar
 * point-cloud proof). Returns a JPEG data URL as visual evidence. */
async function videoFrameStats(cdp) {
  return cdp.evaluate(`(async () => {
    const video = document.getElementById('deploymentTwinVideo');
    if (!video || !video.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const sample = document.createElement('canvas');
    sample.width = 240; sample.height = 135;
    const sctx = sample.getContext('2d', { willReadFrequently: true });
    sctx.drawImage(canvas, 0, 0, sample.width, sample.height);
    const data = sctx.getImageData(0, 0, sample.width, sample.height).data;
    let sum = 0, sumSq = 0, maxSpread = 0, dark = 0, lit = 0, n = 0;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      sum += lum; sumSq += lum * lum; n++;
      maxSpread = Math.max(maxSpread, Math.abs(r - g), Math.abs(r - b), Math.abs(g - b));
      if (lum < 24) dark++;
      if (lum > 90) lit++;
    }
    const mean = sum / n;
    return {
      mean, std: Math.sqrt(Math.max(0, sumSq / n - mean * mean)), maxSpread,
      darkRatio: dark / n, litRatio: lit / n,
      w: video.videoWidth, h: video.videoHeight,
      frame: canvas.toDataURL('image/jpeg', 0.85),
    };
  })()`);
}
function saveFrame(stats, path) {
  if (!stats?.frame) return false;
  writeFileSync(path, Buffer.from(stats.frame.split(',')[1], 'base64'));
  return existsSync(path);
}
const statsText = stats => stats
  ? `mean=${stats.mean?.toFixed(1)} std=${stats.std?.toFixed(1)} spread=${stats.maxSpread} dark=${stats.darkRatio?.toFixed(2)} lit=${stats.litRatio?.toFixed(4)}`
  : 'no frame';

// ── WS envelope sampler (S5 pattern, extended: multi-frame for dynamics) ─────
// Resolves early once `goal(frames)` returns true, else at spanMs.
function sampleEnvelopes(wsUrl, spanMs, goal) {
  return new Promise(resolve => {
    const ws = new WebSocket(wsUrl);
    const frames = [];
    const done = () => { clearTimeout(timer); try { ws.close(); } catch {} resolve(frames); };
    const timer = setTimeout(done, spanMs);
    ws.addEventListener('message', event => {
      try {
        const doc = JSON.parse(event.data);
        if (!doc?.obstacles?.length) return;
        frames.push(doc);
        if (goal?.(frames)) done();
      } catch { /* partial frames */ }
    });
    ws.addEventListener('error', () => { clearTimeout(timer); resolve(frames); });
  });
}
const finiteRadarMeasurements = frames => frames.flatMap(doc =>
  (doc.measurements?.[0] ?? [])
    .filter(group => Array.isArray(group))
    .flatMap(group => group.filter(m => Array.isArray(m) && Number.isInteger(m[0]) && m[0] >= 0
      && Array.isArray(m[1]) && Number.isFinite(m[1][0]))));

// ── process lifecycle (single-instance discipline) ───────────────────────────
let playerPid = null;
let detectorPid = null;
let detector = null;
let player = null;
let chrome = null;
function cleanup() {
  for (const [pid, label] of [[playerPid, 'player'], [detectorPid, 'detector'], [chrome?.pid, 'chrome']]) {
    if (!pid) continue;
    try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ }
    console.log(`${label} killed pid=${pid}`);
  }
}
process.on('exit', () => { try { cleanup(); } finally { twinLaunchdPlayerUp(check); } }); // 末位复位 launchd player（spec #91 前置批）
async function killLeftovers() {
  for (const pattern of ['MacOS/sango', 'sango_detector_service']) {
  twinLaunchdPlayerDown(check); // launchd 常驻 player 先停（KeepAlive 会复活被杀实例）
    try {
      const out = execSync(`pgrep -fl "${pattern}" || true`).toString().trim();
      if (!out) continue;
      for (const line of out.split('\n')) {
        const pid = Number(line.split(/\s+/)[0]);
        if (Number.isFinite(pid) && pid > 0 && pid !== process.pid) { try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ } }
      }
      check(`no leftover ${pattern}`, true, `killed: ${out.replace(/\n/g, '; ')}`);
      await sleep(600);
    } catch { check(`no leftover ${pattern}`, true); }
  }
}
function playerLogTail(bytes = 400000) {
  const candidates = [
    join(process.env.HOME, 'Library/Logs/DefaultCompany/sango-twin/Player.log'),
    join(process.env.HOME, 'Library/Logs/DefaultCompany/sango/Player.log'),
  ];
  for (const path of candidates) {
    if (!existsSync(path)) continue;
    const content = readFileSync(path);
    return { path, text: content.subarray(Math.max(0, content.length - bytes)).toString('utf8') };
  }
  return null;
}

// ── main ────────────────────────────────────────────────────────────────────
mkdirSync(OUT_DIR, { recursive: true });

const backendOk = await preflight(`${BACKEND}/api/capabilities`, 'backend 8010');
const signalingOk = await preflight(`${SIGNALING}/config`, 'URS signaling 8080');
if (!backendOk || !signalingOk) {
  console.error('\nPreconditions failed: backend 8010 + URS signaling 8080 required.');
  process.exit(1);
}

// 0) Product-boundary flip proof BEFORE any session exists: the published
//    policy selects vimmjipda as default and keeps god selectable alongside.
const capabilities = await fetch(`${BACKEND}/api/capabilities`).then(r => r.json()).catch(() => null);
const policy = capabilities?.product_capability_policy ?? null;
check('product policy default tracker flipped to vimmjipda (capabilities boundary)',
  policy?.default_tracker_id === DEFAULT_TRACKER,
  `default_tracker_id=${policy?.default_tracker_id} tracker_ids=${JSON.stringify(policy?.tracker_ids ?? [])}`);
check('god retained alongside the flipped default (fallback channel kept)',
  Array.isArray(policy?.tracker_ids) && policy.tracker_ids.includes('god') && policy.tracker_ids.includes(DEFAULT_TRACKER),
  JSON.stringify(policy?.tracker_ids ?? []));
const algoStatus = await fetch(`${BACKEND}/api/algo_status`).then(r => r.json()).catch(() => null);
const selectableTrackers = new Set((algoStatus?.trackers ?? []).filter(t => t.selectable).map(t => t.integration_id));
check('vimmjipda selectable in the live product catalog (algo_status)',
  selectableTrackers.has(DEFAULT_TRACKER) && selectableTrackers.has('god'),
  `selectable=${JSON.stringify([...selectableTrackers])}`);

await killLeftovers();

async function createSession(body) {
  const res = await fetch(`${BACKEND}/api/sessions`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`session create failed: ${res.status} ${await res.text()}`);
  const doc = await res.json();
  return { id: doc.session_id ?? doc.id, doc };
}

// ── Session A: the god FALLBACK chain on the radar_x-assembled scenario ──────
// The external vimmjipda interface consumes the legacy Radar channel only
// (upstream isinstance filter, external repo stays untouched), so the radar_x
// measurement group reaches the telemetry measurement cache through the god
// diagnostic chain, which generates measurements from every wired sensor.
// Radar/PPI/display legs run here; the fusion legs run on session B below.
const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
if (current?.session_id) await fetch(`${BACKEND}/api/sessions/${current.session_id}/reset`, { method: 'POST' });
let sessionId = null;
{
  const { id } = await createSession({
    validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'god',
  });
  sessionId = id;
  await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
  check('fallback session created with EXPLICIT tracker_id=god (revert path live)', true, `session=${sessionId}`);
}

// Chrome drives the real app for the whole probe; session A is current first.
chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', '--no-default-browser-check', `--user-data-dir=${join(tmpdir(), `sango-phase3-e2e-${Date.now()}`)}`,
  '--window-size=1680,1050', 'about:blank',
], { stdio: 'ignore', detached: false });
await waitFor('chrome CDP endpoint', async () => {
  const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`).then(r => r.json()).catch(() => null);
  return res?.Browser ?? null;
}, 30000, 300);
const tab = await openTab(`${BACKEND}/`);
await sleep(1500);
const cdp = await connectCDP();
await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1680, height: 1050, deviceScaleFactor: 1, mobile: false });

try {
  // A1) radar_x measurement cache + PPI on the god session (WS + real panel).
  const framesA = await sampleEnvelopes(
    `ws://127.0.0.1:8010/ws/sessions/${sessionId}`, 120000,
    frames => finiteRadarMeasurements(frames).length >= 3);
  writeFileSync(join(OUT_DIR, 'ws-envelope-god-extract.json'), JSON.stringify({
    frames_captured: framesA.length,
    executed_tracker: framesA[0]?.executed_tracker ?? null,
    first_track_document: framesA.find(doc => doc.tracks?.[0]?.states?.length)?.tracks?.[0] ?? null,
    finite_radar_measurements: finiteRadarMeasurements(framesA).length,
    radar_ppi: framesA.find(doc => doc.radar_ppi)?.radar_ppi ?? null,
  }, null, 2));
  const ppiDoc = framesA.find(doc => doc.radar_ppi && Number.isFinite(Number(doc.radar_ppi.scan_period_s)));
  check('radar_ppi descriptor live on the envelope (radar_x assembled in scenario)',
    Boolean(ppiDoc?.radar_ppi),
    ppiDoc?.radar_ppi
      ? `scale=${ppiDoc.radar_ppi.range_scale_nm}nm scan=${ppiDoc.radar_ppi.scan_period_s}s blind_ring=${Number(ppiDoc.radar_ppi.blind_ring_m).toFixed(1)}m`
      : 'no radar_ppi');
  const blips = finiteRadarMeasurements(framesA);
  check('measurement cache holds finite radar_x measurements (god chain consumes every sensor)',
    blips.length >= 3, `finite_radar_measurements=${blips.length} sample=${JSON.stringify(blips.at(-1)?.[1]?.map(v => Math.round(v)))}`);
  await waitFor('deployment chart adopted the live session', () => cdp.evaluate(
    `document.getElementById('liveControlState')?.textContent === 'RUNNING'`), 90000, 1000);
  await cdp.evaluate(`document.getElementById('ppiBtn')?.click()`);
  await sleep(1500);
  const ppiVisible = await cdp.evaluate(
    `(() => { const p = document.getElementById('ppiPanel'); return p && !p.hidden
      && (() => { const c = document.getElementById('ppiCanvas'); if (!c) return false;
        const ctx = c.getContext('2d'); const d = ctx.getImageData(0, 0, c.width, Math.min(160, c.height)).data;
        for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return true; return false; })(); })()`);
  check('PPI panel opens and draws on live radar_x data (rings/sweep/blips)', Boolean(ppiVisible));
  await cdp.screenshot(`${OUT_DIR}ppi-panel.png`);
  await cdp.evaluate(`document.getElementById('ppiBtn')?.click()`);
  await sleep(400);

  // A2) AIS layer + target card (backend-authoritative ais fields).
  await waitFor('AIS symbols rendered on the live 2D chart', () => cdp.evaluate(
    `document.querySelectorAll('#aisMarkerLayer .ais-marker').length > 0`), 60000);
  const aisInfo = await cdp.evaluate(`(() => JSON.stringify({
    count: document.querySelectorAll('#aisMarkerLayer .ais-marker').length,
    layerChecked: document.querySelector('[data-layer="aisTargets"]')?.checked ?? null,
  }))()`);
  check('AIS symbol layer renders on the live chart (IMO SN.1/Circ.243)', JSON.parse(aisInfo).count > 0, aisInfo);
  await cdp.evaluate(`document.querySelector('#aisMarkerLayer .ais-marker').click()`);
  await waitFor('AIS target card opens', () => cdp.evaluate(
    `!document.getElementById('aisDetailPlacard').hidden`), 15000, 300);
  const aisCard = await cdp.evaluate(`JSON.stringify((() => {
    const metric = id => document.getElementById(id)?.textContent;
    return {
      hidden: document.getElementById('aisDetailPlacard').hidden,
      source: document.getElementById('aisDetailPlacard')?.source ?? null,
      mmsi: metric('aisPlacardMmsi'), sog: metric('aisPlacardSog'),
      age: metric('aisPlacardAge'), state: metric('aisPlacardState'),
      assoc: metric('aisPlacardAssociation'),
    };
  })())`);
  const card = JSON.parse(aisCard ?? '{}');
  check('AIS target card opens with backend-authoritative fields',
    !card.hidden && card.source === 'AIS' && card.state !== '---' && card.assoc !== '---', aisCard);
  await cdp.screenshot(`${OUT_DIR}ais-card.png`);
  await cdp.evaluate(`document.body.click()`);
  await sleep(400);

  // A3) Existence legend + CONF placard row (display channel; tracker-agnostic).
  await cdp.evaluate(`document.getElementById('chartLayersBtn')?.click()`);
  await sleep(400);
  await cdp.evaluate(`document.querySelector('[data-layer="tracks"]')?.click()`);
  await sleep(300);
  const legendOk = await cdp.evaluate(`Boolean(document.querySelector('.color-box.track-conf-confirmed'))`);
  check('existence-probability legend bands present (confirmed/amber/dim)', legendOk);
  await cdp.screenshot(`${OUT_DIR}tracks-legend.png`);
  await cdp.evaluate(`document.getElementById('closeChartDisplayBtn')?.click()`);
  await sleep(400);
  const markerClicked = await cdp.evaluate(`(() => {
    const marker = document.querySelector('#vesselMarkerLayer .vessel-marker');
    marker?.click();
    return Boolean(marker);
  })()`);
  if (markerClicked) {
    await waitFor('vessel placard opens', () => cdp.evaluate(
      `!document.getElementById('vesselDetailPlacard').hidden`), 15000, 300);
    const confValue = await cdp.evaluate(`document.getElementById('vesselPlacardConf')?.textContent`);
    check('vessel placard carries the CONF row (existence probability)', Boolean(confValue), `CONF=${confValue}`);
    await cdp.screenshot(`${OUT_DIR}placard-conf.png`);
  } else {
    check('vessel placard carries the CONF row', false, 'no vessel marker on the chart');
  }
  await cdp.screenshot(`${OUT_DIR}chart-god-session.png`);

  // ── Session B: the FLIPPED DEFAULT tracker owns the fusion legs ─────────────
  await fetch(`${BACKEND}/api/sessions/${sessionId}/reset`, { method: 'POST' });
  const { id: defaultSessionId } = await createSession({
    validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo',
    record_replay_trace: true,
  });
  sessionId = defaultSessionId;
  const described = await fetch(`${BACKEND}/api/sessions/${sessionId}`).then(r => r.json()).catch(() => null);
  check('new session created with the request-level DEFAULT tracker (no tracker_id sent)',
    described?.spec?.tracker_id === DEFAULT_TRACKER,
    `spec.tracker_id=${described?.spec?.tracker_id}`);
  check('capabilities catalog carries the fusion tracker readiness grade',
    (capabilities?.trackers ?? []).some(t => t.id === DEFAULT_TRACKER && Boolean(t.readiness_grade)),
    `trackers=${JSON.stringify((capabilities?.trackers ?? []).map(t => ({ id: t.id, grade: t.readiness_grade })))}`);
  await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
  check('flipped-default session started (vimmjipda fusion chain)', true, `session=${sessionId}`);

  // B1) YOLO detector with the observations forward branch (CPU).
  const detectorLog = '/tmp/sango-e2e-detector.log';
  const FEED_DUMP = join(OUT_DIR, 'mast-feed-frame.jpg');
  detector = spawn(DETECTOR_BIN, [
    DETECTOR_SCRIPT, '--device', 'cpu',
    '--forward-url', `${BACKEND}/api/sessions/${sessionId}/observations`,
    '--forward-mount', 'mast_ptz_eo',
    '--dump-frame', FEED_DUMP,
  ], { stdio: ['ignore', 'pipe', 'pipe'], detached: false });
  detectorPid = detector.pid;
  detector.stdout.on('data', chunk => writeFileSync(detectorLog, chunk, { flag: 'a' }));
  detector.stderr.on('data', chunk => writeFileSync(detectorLog, chunk, { flag: 'a' }));
  writeFileSync(detectorLog, '');
  console.log(`detector started pid=${detectorPid} -> ${detectorLog}`);
  await waitFor('detector ready (model loaded + forward on)', () => {
    const text = readFileSync(detectorLog, 'utf8');
    return text.includes('model loaded') && text.includes('forward branch ON') ? text : null;
  }, 90000);
  check('YOLO detector up (CPU) with forward branch', true, detectorLog);

  // B2) Player (bridge + publisher; mast rig rewires the feed to mast_ptz_eo).
  player = spawn(PLAYER_BIN, PLAYER_ARGS, { stdio: 'ignore', detached: false });
  playerPid = player.pid;
  console.log(`player started pid=${playerPid} (${PLAYER_ARGS.join(' ')})`);
  await sleep(8000);

  // B3) Twin viewport attach (the tab already rides the new current session).
  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await waitFor('T twin button enabled (live session adopted)', () => cdp.evaluate(
    `(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`), 90000);

  let attached = null;
  for (let attempt = 1; attempt <= 4 && !attached; attempt++) {
    await cdp.evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b && !b.disabled) b.click(); return true; })()`);
    try {
      await waitFor('URS video frame (deployment twin)', () => cdp.evaluate(`(() => {
        const video = document.getElementById('deploymentTwinVideo');
        return video && video.srcObject && video.readyState >= 2 && video.videoWidth > 0
          ? { w: video.videoWidth, h: video.videoHeight } : null;
      })()`), 60000);
      attached = await waitFor('bridge attached (mode live)', () => cdp.evaluate(
        `(() => { const d = window.__deploymentTwin; return d?.attached?.mode === 'live' ? d.attached : null; })()`), 45000);
    } catch (error) {
      console.log(`  twin entry attempt ${attempt}/4 failed: ${error.message.split('\n')[0]}`);
      await cdp.evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b) b.click(); return true; })()`);
      await sleep(1000);
    }
  }
  if (!attached) throw new Error('no live attach after repeated viewport re-entries');
  check('twin viewport attached to the flipped-tracker session (live pixel stream)', true,
    `run=${attached?.run_id?.slice(0, 8)} ships=${attached?.ships}`);
  await cdp.evaluate(`(() => { window.__deploymentTwin?.client?.sendTheme('day'); return true; })()`);
  await sleep(1500);

  // 5) Mast rig + feed rewire, YOLO consuming frames.
  await waitFor('mast rig attached + feed rewired (Player.log)', () => {
    const log = playerLogTail();
    const text = log?.text ?? '';
    return text.includes('mast rig attached') && text.includes('frame feed rewired -> mast_ptz_eo') ? log : null;
  }, 60000);
  check('mast rig attached; FramePublisher feed rewired to mast_ptz_eo (P3-S2 rig family)', true, 'Player.log');
  await waitFor('YOLO consuming feed frames', () => {
    const text = readFileSync(detectorLog, 'utf8');
    const match = text.match(/rx=(\d+)/);
    return match && Number(match[1]) > 0 ? { rx: Number(match[1]) } : null;
  }, 60000, 1000);
  check('YOLO consuming published feed frames (rx > 0)', true, 'detector log');

  // 6) sensor_mode full loop eo→ir→lidar→eo (00-PLAN §0 item 7).
  // 6a. EO baseline.
  const eoBase = await videoFrameStats(cdp);
  check('EO baseline frame captured (visible light)', Boolean(eoBase && eoBase.std > 0.5), statsText(eoBase));
  saveFrame(eoBase, join(OUT_DIR, 'mode-eo.jpg'));
  // 6b. IR = black-and-white thermal.
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="ir"]'); if (b) b.click(); return true; })()`);
  const echoIr = await waitFor('state.sensor_mode echo ir', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'ir' ? 'ir' : null)()`), 30000);
  check('IR switch: state echo sensor_mode=ir (contract §3)', echoIr === 'ir');
  const chipIr = await cdp.evaluate(`document.getElementById('deploymentTwinSensorMode')?.textContent ?? ''`);
  check('sensor-mode chip mirrors IR echo', chipIr.includes('SENSOR IR'), chipIr);
  let grayIr = null;
  for (let poll = 0; poll < 10 && !(grayIr && grayIr.std > 0.5); poll++) { await sleep(1200); grayIr = await videoFrameStats(cdp); }
  check('IR stream frame captured (grayscale stats)', Boolean(grayIr && grayIr.std > 0.5), statsText(grayIr));
  check('IR = black-and-white thermal (max channel spread ~0)', Boolean(grayIr && grayIr.maxSpread <= 12),
    grayIr ? `maxSpread=${grayIr.maxSpread}` : 'no frame');
  saveFrame(grayIr, join(OUT_DIR, 'mode-ir.jpg'));
  await cdp.screenshot(`${OUT_DIR}mode-ir.png`);
  // 6c. LiDAR = point cloud on dark backdrop.
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="lidar"]'); if (b) b.click(); return true; })()`);
  const echoLidar = await waitFor('state.sensor_mode echo lidar', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'lidar' ? 'lidar' : null)()`), 30000);
  check('LiDAR switch: state echo sensor_mode=lidar', echoLidar === 'lidar');
  let statsLidar = null;
  const lidarDeadline = Date.now() + 120000;
  while (Date.now() < lidarDeadline) {
    statsLidar = await videoFrameStats(cdp);
    if (statsLidar && statsLidar.std > 1.5 && statsLidar.litRatio > 0.0003) break;
    await sleep(1500);
  }
  check('LiDAR frame captured', Boolean(statsLidar && statsLidar.std > 0.5), statsText(statsLidar));
  check('LiDAR = point-cloud view (dark backdrop vs EO)',
    Boolean(statsLidar && eoBase && statsLidar.darkRatio > 0.6 && statsLidar.darkRatio > eoBase.darkRatio + 0.25),
    `lidar dark=${statsLidar?.darkRatio?.toFixed(2)} vs eo dark=${eoBase?.darkRatio?.toFixed(2)}`);
  check('LiDAR point cloud sparse lit points present',
    Boolean(statsLidar && statsLidar.litRatio > 0.0003 && statsLidar.litRatio < 0.5),
    `lit=${statsLidar?.litRatio?.toFixed(4)}`);
  saveFrame(statsLidar, join(OUT_DIR, 'mode-lidar.jpg'));
  await cdp.screenshot(`${OUT_DIR}mode-lidar.png`);
  // 6d. Back to EO — color returns.
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="eo"]'); if (b) b.click(); return true; })()`);
  const echoEo = await waitFor('state.sensor_mode echo eo', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'eo' ? 'eo' : null)()`), 30000);
  check('EO restore: state echo sensor_mode=eo (full loop closed)', echoEo === 'eo');
  await sleep(2500);
  const eoRestored = await videoFrameStats(cdp);
  check('EO restore = visible light returns (channel spread back)', Boolean(eoRestored && eoRestored.maxSpread > 24),
    statsText(eoRestored));
  saveFrame(eoRestored, join(OUT_DIR, 'mode-eo-restored.jpg'));

  const logFinal = playerLogTail();
  const modeLoopLog = Boolean(logFinal?.text?.includes('sensor_mode -> ir') && logFinal?.text?.includes('sensor_mode -> lidar'));
  check('Player.log double proof (sensor_mode -> ir / lidar + mast rig)', modeLoopLog, logFinal?.path ?? 'not found');
  if (logFinal) writeFileSync(join(OUT_DIR, 'player-log-excerpt.txt'), logFinal.text);

  // 7) Observations cache: YOLO detections landed with sensor_id=2.
  const obsDeadline = Date.now() + OBS_WINDOW_MS;
  let cacheStatus = null;
  while (Date.now() < obsDeadline) {
    const status = await fetch(`${BACKEND}/api/sessions/${sessionId}/observations`).then(r => (r.ok ? r.json() : null)).catch(() => null);
    const channel = status?.channels?.find(c => c.sensor_id === 2);
    if (status && status.accepted_frames_total > 0 && channel?.detections > 0) { cacheStatus = status; break; }
    await sleep(2000);
  }
  cacheStatus = cacheStatus ?? await fetch(`${BACKEND}/api/sessions/${sessionId}/observations`).then(r => r.json()).catch(() => null);
  writeFileSync(join(OUT_DIR, 'observations-status.json'), JSON.stringify(cacheStatus, null, 2));
  check('observations accepted (YOLO → POST → backend measurement cache)',
    Boolean(cacheStatus && cacheStatus.accepted_frames_total > 0),
    `accepted_frames=${cacheStatus?.accepted_frames_total ?? 0}`);
  check('measurement cache holds sensor_id=2 camera_eo entries (georeferenced detections)',
    Boolean(cacheStatus?.channels?.some(c => c.sensor_id === 2 && c.detections > 0 && c.mount_id === 'mast_ptz_eo')),
    cacheStatus ? JSON.stringify(cacheStatus.channels) : 'no status');

  // B4) WS §6 assertions on the fusion session. The sampler waits for tracks:
  // the external vimmjipda interface fuses the legacy radar channel, which
  // picks the target up once it closes under the 2 km radar range (~2 min in).
  const envelopes = await sampleEnvelopes(
    `ws://127.0.0.1:8010/ws/sessions/${sessionId}`, WS_TRACK_WINDOW_MS,
    frames => frames.filter(doc => doc.tracks?.[0]?.states?.length).length >= 5);
  check('WS envelope stream captured (live frames)', envelopes.length > 0, `frames=${envelopes.length}`);
  const withTracks = envelopes.filter(doc => doc.tracks?.[0]?.states?.length);
  const firstTracks = withTracks[0]?.tracks?.[0] ?? null;
  writeFileSync(join(OUT_DIR, 'ws-envelope-extract.json'), JSON.stringify({
    frames_captured: envelopes.length, frames_with_tracks: withTracks.length,
    first_track_document: firstTracks,
    executed_tracker: envelopes[0]?.executed_tracker ?? null,
  }, null, 2));
  const arraysOk = Boolean(firstTracks)
    && Array.isArray(firstTracks.existence_prob) && firstTracks.existence_prob.length === firstTracks.labels.length
    && Array.isArray(firstTracks.quality) && firstTracks.quality.length === firstTracks.labels.length
    && Array.isArray(firstTracks.sources) && firstTracks.sources.length === firstTracks.labels.length;
  check('WS tracks carry §6 existence_prob/quality/sources arrays (P3-S5 channel)', arraysOk,
    `labels=${firstTracks?.labels?.length ?? 0} existence=${JSON.stringify(firstTracks?.existence_prob ?? null)}`);
  // Existence dynamics: sampled values across the window must not be the pinned
  // constant 1.0 of the retired god default; fallback = confirmed-tracks data
  // product non-empty with the existence field present (00-PLAN §0 item 1/5).
  const sampled = withTracks.flatMap(doc => (doc.tracks?.[0]?.existence_prob ?? []).filter(Number.isFinite));
  const dynamic = sampled.length > 0 && sampled.some(v => v < 0.999);
  const confirmed = await fetch(`${BACKEND}/api/sessions/${sessionId}/confirmed-tracks`).then(r => r.json()).catch(() => null);
  writeFileSync(join(OUT_DIR, 'confirmed-tracks-live.json'), JSON.stringify(confirmed, null, 2));
  const confirmedOk = confirmed?.schema_version === 'sensor-model@1/tracks' && Array.isArray(confirmed.tracks)
    && confirmed.tracks.length > 0
    && confirmed.tracks.every(t => Number.isFinite(t.existence_prob));
  check('vimmjipda existence probability is measurement-driven (not the pinned god 1.0)',
    dynamic || confirmedOk,
    `samples=${sampled.length} min=${sampled.length ? Math.min(...sampled).toFixed(4) : 'n/a'} max=${sampled.length ? Math.max(...sampled).toFixed(4) : 'n/a'} confirmed=${confirmed?.tracks?.length ?? 0}`);
  check('confirmed-tracks data product live (frozen sensor-model@1/tracks envelope)', confirmedOk,
    `tracks=${confirmed?.tracks?.length ?? 0}`);
  const aisDoc = envelopes.find(doc => doc.obstacles?.some(o => o.ais && Number.isFinite(Number(o.ais.age_s))));
  check('backend-authoritative ais fields present on obstacles of the fusion session (age_s/state)', Boolean(aisDoc),
    aisDoc ? `sample=${JSON.stringify(aisDoc.obstacles.find(o => o.ais)?.ais)}` : 'no ais field');
  await cdp.screenshot(`${OUT_DIR}chart-final.png`);
} finally {
  if (!process.argv.includes('--keep-chrome')) { try { chrome?.kill('SIGKILL'); } catch { /* gone */ } }
  if (!process.argv.includes('--keep-yolo')) { try { detector?.kill('SIGKILL'); } catch { /* gone */ } }
  if (!process.argv.includes('--keep-player')) { try { player?.kill('SIGKILL'); } catch { /* gone */ } }
}

// ── evidence bundle ──────────────────────────────────────────────────────────
writeFileSync(join(OUT_DIR, 'evidence-status.json'), JSON.stringify({
  probe: 'sango_phase3_e2e_probe', default_tracker: DEFAULT_TRACKER, session_id: sessionId,
  assertions, failures, at: new Date().toISOString(),
}, null, 2));
writeFileSync(join(OUT_DIR, 'probe-console.log'), cdp.console.join('\n'));
const lines = [];
lines.push('# P3-S6 全传感器 E2E — sango_phase3_e2e_probe');
lines.push('');
lines.push(`- date: ${new Date().toISOString()}`);
lines.push(`- live session: \`${sessionId}\`（rule14/head_on/vo，请求未带 tracker_id —— 翻转后默认 ${DEFAULT_TRACKER} 应答）`);
lines.push('- 链路：8010 后端 ← 8080 信令 ← sango player（twin-bridge + mast rig）← YOLO CPU 前向 ← headless Chrome CDP');
lines.push('');
lines.push('## 断言');
lines.push('');
for (const item of assertions) lines.push(`- ${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.detail ? ` — ${item.detail}` : ''}`);
writeFileSync(join(OUT_DIR, 'README.md'), lines.join('\n') + '\n');

if (failures.length) {
  console.error(`\n${failures.length} assertion(s) FAILED`);
  process.exitCode = 1;
} else {
  console.log('\nALL ASSERTIONS PASSED');
  console.log(`artifacts: ${OUT_DIR}`);
}
process.exit(process.exitCode ?? 0);
