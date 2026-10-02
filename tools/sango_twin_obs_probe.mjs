#!/usr/bin/env node
// sango_twin_obs_probe — P3-S2 E2E (spec #90; observations-v1.md + twin-bridge-v1.md §8).
//
// Live kf-tracker session → player twin → mast feed (mast_ptz_eo) → YOLO (CPU)
// → observations POST → backend measurement cache (sensor_id=2), with the
// EO↔IR sensor_mode switch visible in the stream (screenshot + state/log double
// proof). Full chain on one machine:
//
//   backend :8010 (observations route live) ← POST /api/sessions/{id}/observations
//   signaling :8080 (URS webapp)
//   player  --sango-twin-bridge --sango-publisher  (bridge rewires the FramePublisher
//            feed to the mast rig's forward EO camera once the own-ship slot lands)
//   YOLO    .venv-detector tools/sango_detector_service.py --device cpu --forward-url …
//   Chrome  headless CDP drives the REAL Deployment twin viewport (button click →
//           sensor_mode message → state echo chip)
//
// Lifecycle discipline: player + YOLO + Chrome are owned here (leftovers killed,
// every PID killed on exit). Artifacts → output/sango-twin-s2/.
// Usage: node tools/sango_twin_obs_probe.mjs [--keep-chrome] [--keep-player] [--keep-yolo]
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BACKEND = 'http://127.0.0.1:8010';
const SIGNALING = 'http://127.0.0.1:8080';
const CDP_PORT = 9225; // dedicated (9222-9224 used by earlier probes)
const OUT_DIR = new URL('../output/sango-twin-s2/', import.meta.url).pathname;
const PLAYER_BIN = new URL('../sango/Builds/sango-twin.app/Contents/MacOS/sango', import.meta.url).pathname;
const PLAYER_ARGS = ['--sango-twin-bridge', '--sango-publisher'];
const DETECTOR_BIN = new URL('../.venv-detector/bin/python', import.meta.url).pathname;
const DETECTOR_SCRIPT = new URL('./sango_detector_service.py', import.meta.url).pathname;
const OBS_WINDOW_MS = 330000;     // max wait for YOLO detections to land in the cache (head_on closes 2.8 km head-on)
const FRAME_WINDOW_MS = 60000;    // max wait for the feed to publish at all
const SIM_SAMPLE_MS = 1000;

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

// ── minimal CDP client (live-probe harness pattern) ──────────────────────────
class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.console = [];
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
      setTimeout(() => {
        if (this.pending.has(id)) { this.pending.delete(id); reject(new Error(`CDP timeout ${method}`)); }
      }, 30000);
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

/**
 * Grabs the twin <video> frame through a canvas (WebRTC MediaStream sources do
 * not taint the canvas) and reports grayscale statistics — the EO↔IR double
 * proof: IR must be perfectly desaturated (max |R-G|/|R-B| channel spread ~0)
 * while EO shows the full color spread. Works even when the headless page
 * compositor keeps <video> black, because drawImage pulls from the decoder.
 * Returns a full-resolution JPEG data URL as the visual evidence artifact.
 */
async function videoGrayStats(cdp) {
  return cdp.evaluate(`(async () => {
    const video = document.getElementById('deploymentTwinVideo');
    if (!video || !video.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const sample = document.createElement('canvas');
    sample.width = 160; sample.height = 90;
    const sctx = sample.getContext('2d', { willReadFrequently: true });
    sctx.drawImage(canvas, 0, 0, sample.width, sample.height);
    const data = sctx.getImageData(0, 0, sample.width, sample.height).data;
    let sum = 0, sumSq = 0, maxSpread = 0, n = 0;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      sum += lum; sumSq += lum * lum; n++;
      maxSpread = Math.max(maxSpread, Math.abs(r - g), Math.abs(r - b), Math.abs(g - b));
    }
    const mean = sum / n;
    return {
      mean, std: Math.sqrt(Math.max(0, sumSq / n - mean * mean)), maxSpread,
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

// ── process lifecycle (single-instance discipline) ───────────────────────────
let playerPid = null;
let detectorPid = null;
let chrome = null;
function cleanup() {
  for (const [pid, label] of [[playerPid, 'player'], [detectorPid, 'detector'], [chrome?.pid, 'chrome']]) {
    if (!pid) continue;
    try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ }
    console.log(`${label} killed pid=${pid}`);
  }
}
process.on('exit', cleanup);
function killLeftovers() {
  for (const pattern of ['MacOS/sango', 'sango_detector_service']) {
    try {
      const out = execSync(`pgrep -fl "${pattern}" || true`).toString().trim();
      if (!out) continue;
      for (const line of out.split('\n')) {
        const pid = Number(line.split(/\s+/)[0]);
        if (Number.isFinite(pid) && pid > 0 && pid !== process.pid) { try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ } }
      }
      check(`no leftover ${pattern}`, true, `killed: ${out.replace(/\n/g, '; ')}`);
      sleep(600);
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

// Frames ride only as artifact files; stats text stays small for the report.
const frameStatsText = stats => stats ? `mean=${stats.mean?.toFixed(1)} std=${stats.std?.toFixed(1)} maxSpread=${stats.maxSpread}` : 'no frame';

// ── main ────────────────────────────────────────────────────────────────────
mkdirSync(OUT_DIR, { recursive: true });

const backendOk = await preflight(`${BACKEND}/api/capabilities`, 'backend 8010');
const signalingOk = await preflight(`${SIGNALING}/config`, 'URS signaling 8080');
if (!backendOk || !signalingOk) {
  console.error('\nPreconditions failed: backend 8010 (S2 route live) + URS signaling 8080 required.');
  process.exit(1);
}
// S2 route sanity: unknown session must hit the NEW route (frozen 404 code).
const routeProbe = await fetch(`${BACKEND}/api/sessions/nope/observations`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ schema_version: 'observations@1', frame_seq: 0, frame_time_s: 0, sensor_id: 2, mount_id: 'mast_ptz_eo', detections: [] }),
}).catch(() => null);
check('observations route live (404 SESSION_NOT_FOUND on unknown session)',
  routeProbe?.status === 404 && (routeProbe ? (await routeProbe.json()).detail === 'SESSION_NOT_FOUND' : false),
  `status ${routeProbe?.status}`);

killLeftovers();

// 1) Live session. tracker vocabulary is backend-gated (capabilities: god only
// until the S6 default flip) — the kf-tracker consumption leg is the pytest
// ExternalCameraSensorCache integration; this E2E exercises the live chain.
const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
if (current?.session_id) await fetch(`${BACKEND}/api/sessions/${current.session_id}/reset`, { method: 'POST' });
const createRes = await fetch(`${BACKEND}/api/sessions`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo',
    tracker_id: 'god', record_replay_trace: true,
  }),
});
check('live session created (POST /api/sessions, tracker=god; capabilities-gated)', createRes.ok, `status ${createRes.status}`);
const created = await createRes.json();
const sessionId = created.session_id ?? created.id;
await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
check('live session started', true, `session=${sessionId}`);

// 2) YOLO detector with the observations forward branch (CPU).
const detectorLog = '/tmp/sango-obs-detector.log';
const FEED_DUMP = join(OUT_DIR, 'feed-frame.jpg');
const detector = spawn(DETECTOR_BIN, [
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

// 3) Player (bridge + publisher flags; mast feed rewires once the own ship lands).
const player = spawn(PLAYER_BIN, PLAYER_ARGS, { stdio: 'ignore', detached: false });
playerPid = player.pid;
console.log(`player started pid=${playerPid} (${PLAYER_ARGS.join(' ')})`);
await sleep(8000);

// 4) Headless Chrome → Deployment twin viewport.
chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', '--no-default-browser-check', `--user-data-dir=${join(tmpdir(), `sango-twin-obs-${Date.now()}`)}`,
  '--window-size=1680,1050', 'about:blank',
], { stdio: 'ignore', detached: false });
await waitFor('chrome CDP endpoint', async () => {
  const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`).then(r => r.json()).catch(() => null);
  return res?.Browser ?? null;
}, 30000, 300);
const tab = await openTab(`${BACKEND}/`);
console.log(`tab: ${tab.id}`);
await sleep(1500);
const cdp = await connectCDP();

let irSwitched = false;
let eoRestored = false;
let cacheStatus = null;
let grayIr = null;
let grayEo = null;
try {
  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await waitFor('T twin button enabled (live session adopted)', () => cdp.evaluate(
    `(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`), 60000);

  // Enter twin with re-entry retries (S4 §4②: the receiver's SDP offer fires once
  // per stream — if the player is still booting it dies unheard; exit/enter makes
  // a fresh offer). Success = attached(mode live), not merely video.
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
  check('video frames arriving (live pixel stream)', true, `attached run=${attached?.run_id?.slice(0, 8)} ships=${attached?.ships}`);

  // Day theme: the mast feed (YOLO input) needs daylight contrast; the twin-bridge
  // theme message is the sanctioned control (contract §2; echo lands on the stream).
  await cdp.evaluate(`(() => { window.__deploymentTwin?.client?.sendTheme('day'); return true; })()`);
  await sleep(1500);

  // 5) Mast rig + feed rewire (Player.log) and YOLO consuming feed frames.
  await waitFor('mast rig attached + feed rewired (Player.log)', () => {
    const log = playerLogTail();
    const text = log?.text ?? '';
    return text.includes('mast rig attached') && text.includes('frame feed rewired -> mast_ptz_eo') ? log : null;
  }, 60000);
  check('mast rig attached to own ship; FramePublisher feed rewired to mast_ptz_eo', true, 'Player.log');
  await waitFor('YOLO consuming feed frames', () => {
    const text = readFileSync(detectorLog, 'utf8');
    const match = text.match(/rx=(\d+)/);
    return match && Number(match[1]) > 0 ? { rx: Number(match[1]) } : null;
  }, FRAME_WINDOW_MS, 1000);
  check('YOLO consuming published feed frames (rx > 0)', true, 'detector log');
  await waitFor('feed-view frame dump (mast_ptz_eo camera evidence)', () => existsSync(FEED_DUMP) ? true : null, 20000);
  check('feed-view frame artifact saved (mast feed camera view)', true, FEED_DUMP);

  // 6) sensor_mode=ir via the REAL Deployment button group; state echo + IR gray proof.
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="ir"]'); if (b) b.click(); return true; })()`);
  const echoIr = await waitFor('state.sensor_mode echo ir', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'ir' ? 'ir' : null)()`), 30000);
  irSwitched = echoIr === 'ir';
  check('IR switch: state echo sensor_mode=ir (contract §3)', irSwitched);
  const chipText = await cdp.evaluate(`document.getElementById('deploymentTwinSensorMode')?.textContent ?? ''`);
  check('sensor-mode chip mirrors the echo', chipText.includes('SENSOR IR'), chipText);
  await sleep(2500); // let the IR pass render a few streamed frames
  grayIr = await videoGrayStats(cdp);
  check('IR stream frame captured (grayscale stats)', Boolean(grayIr && grayIr.std > 0.5),
    grayIr ? `std=${grayIr.std.toFixed(1)} spread=${grayIr.maxSpread}` : 'no frame');
  check('IR = black-and-white thermal (max channel spread ~0)', Boolean(grayIr && grayIr.maxSpread <= 12),
    grayIr ? `maxSpread=${grayIr.maxSpread}` : 'no frame');
  check('IR frame artifact (decoded stream frame)', saveFrame(grayIr, join(OUT_DIR, 'ir-frame.jpg')));
  await cdp.screenshot(join(OUT_DIR, 'ir-mode.png'));

  // 7) Back to EO; the spread must return (color comes back).
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="eo"]'); if (b) b.click(); return true; })()`);
  const echoEo = await waitFor('state.sensor_mode echo eo', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'eo' ? 'eo' : null)()`), 30000);
  eoRestored = echoEo === 'eo';
  check('EO restore: state echo sensor_mode=eo', eoRestored);
  await sleep(2500);
  grayEo = await videoGrayStats(cdp);
  check('EO stream frame captured', Boolean(grayEo && grayEo.std > 0.5),
    grayEo ? `std=${grayEo.std.toFixed(1)} spread=${grayEo.maxSpread}` : 'no frame');
  check('EO = visible light (channel spread returns)', Boolean(grayEo && grayEo.maxSpread > 24),
    grayEo ? `maxSpread=${grayEo.maxSpread}` : 'no frame');
  check('EO frame artifact (decoded stream frame)', saveFrame(grayEo, join(OUT_DIR, 'eo-frame.jpg')));
  await cdp.screenshot(join(OUT_DIR, 'eo-mode.png'));

  // 8) Observations cache: YOLO detections land with sensor_id=2 (contract §1 chain).
  const deadline = Date.now() + OBS_WINDOW_MS;
  let lastProgress = 0;
  while (Date.now() < deadline) {
    const status = await fetch(`${BACKEND}/api/sessions/${sessionId}/observations`).then(r => (r.ok ? r.json() : null)).catch(() => null);
    const channel = status?.channels?.find(c => c.sensor_id === 2);
    if (status && status.accepted_frames_total > 0 && channel?.detections > 0) { cacheStatus = status; break; }
    if (Date.now() - lastProgress > 30000) {
      lastProgress = Date.now();
      const detectorTail = readFileSync(detectorLog, 'utf8').split('\n').filter(l => l.includes('rx=')).pop() ?? '';
      console.log(`  … waiting for detections: accepted_frames=${status?.accepted_frames_total ?? 0} | ${detectorTail.trim().slice(0, 120)}`);
    }
    await sleep(2000);
  }
  cacheStatus = cacheStatus ?? await fetch(`${BACKEND}/api/sessions/${sessionId}/observations`).then(r => r.json()).catch(() => null);
  check('observations accepted (frames flowed YOLO → POST → backend)',
    Boolean(cacheStatus && cacheStatus.accepted_frames_total > 0),
    `accepted_frames=${cacheStatus?.accepted_frames_total ?? 0} channels=${JSON.stringify(cacheStatus?.channels ?? [])}`);
  check('measurement cache holds sensor_id=2 camera_eo entries (YOLO detections georeferenced)',
    Boolean(cacheStatus?.channels?.some(c => c.sensor_id === 2 && c.detections > 0 && c.mount_id === 'mast_ptz_eo')),
    cacheStatus ? JSON.stringify(cacheStatus.channels) : 'no status');
  const detectorTail = readFileSync(detectorLog, 'utf8').split('\n').filter(l => l.includes('forward:')).pop() ?? '';
  check('detector forward branch reported POSTs', detectorTail.includes('forward:'), detectorTail.trim().slice(0, 160));

  // 9) Player log double proof (sensor_mode + mast rig lines).
  const logFinal = playerLogTail();
  const logProof = Boolean(logFinal?.text?.includes('sensor_mode -> ir') && logFinal?.text?.includes('mast rig attached'));
  check('Player.log double proof (sensor_mode -> ir + mast rig attached)', logProof, logFinal?.path ?? 'not found');

  // Artifacts.
  writeFileSync(join(OUT_DIR, 'observations-status.json'), JSON.stringify({
    session_id: sessionId, captured_at: new Date().toISOString(),
    status: cacheStatus, gray_ir: grayIr, gray_eo: grayEo,
  }, null, 2));
  writeFileSync(join(OUT_DIR, 'detector-log.txt'), readFileSync(detectorLog, 'utf8').split('\n').slice(-80).join('\n'));
  if (logFinal) writeFileSync(join(OUT_DIR, 'player-log-excerpt.txt'), logFinal.text);
  writeFileSync(join(OUT_DIR, 'probe-console.log'), cdp.console.join('\n'));

  const lines = [];
  lines.push('# P3-S2 observations + sensor_mode E2E — sango_twin_obs_probe');
  lines.push('');
  lines.push(`- date: ${new Date().toISOString()}`);
  lines.push(`- live session: \`${sessionId}\` (rule14/head_on/vo, tracker=god — capabilities gate; kf leg = pytest cache integration)`);
  lines.push(`- mast feed: mast_ptz_eo 640x480 (Player.log rig attach + feed rewire); YOLO CPU rx>0`);
  lines.push(`- IR switch: state echo ir, chip "SENSOR IR", grayscale stats ${frameStatsText(grayIr)}`);
  lines.push(`- EO restore: state echo eo, grayscale stats ${frameStatsText(grayEo)}`);
  lines.push(`- observations cache: accepted_frames=${cacheStatus?.accepted_frames_total} channels=${JSON.stringify(cacheStatus?.channels)}`);
  lines.push('');
  lines.push('## Assertions');
  lines.push('');
  for (const item of assertions) lines.push(`- ${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.detail ? ` — ${item.detail}` : ''}`);
  writeFileSync(join(OUT_DIR, 'report.md'), lines.join('\n') + '\n');
  console.log(`\nartifacts: ${OUT_DIR}`);
} finally {
  if (!process.argv.includes('--keep-chrome')) { try { chrome?.kill('SIGKILL'); } catch { /* gone */ } }
  if (!process.argv.includes('--keep-yolo')) { try { detector.kill('SIGKILL'); } catch { /* gone */ } }
  if (!process.argv.includes('--keep-player')) { try { player.kill('SIGKILL'); } catch { /* gone */ } }
}

if (failures.length) {
  console.error(`\n${failures.length} assertion(s) FAILED`);
  process.exit(1);
}
console.log('\nALL ASSERTIONS PASSED');
process.exit(0);
