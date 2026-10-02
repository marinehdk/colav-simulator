#!/usr/bin/env node
// sango_twin_bridge_probe — P2-S3 E2E (spec #89, twin-bridge-v1.md §7).
//
// Drives the REAL web_gui page in headless Chrome (CDP) through the Digital
// Twin workface: open run → URS video + twin-bridge DataChannel → play 10 s →
// asserts video frames, SIM TIME advance, attached/state echo, camera preset
// echo, theme switch screenshots; then plays the SAME sealed run in the Replay
// (web 2D) view for 10 s and records both SIM TIME series (对拍).
//
// Preconditions (started externally, see output/sango-twin-s3/report.md):
//   1. backend       http://127.0.0.1:8010   (gui_server, untouched)
//   2. URS signaling http://127.0.0.1:8080   (node WebApp/build/index.js -p 8080)
//   3. twin player   sango/Builds/sango-twin.app --sango-twin-bridge
// Usage:
//   node tools/sango_twin_bridge_probe.mjs [--run <run_id>] [--keep-chrome]
// Exit 0 = every assertion passed; artifacts land in output/sango-twin-s3/.
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BACKEND = 'http://127.0.0.1:8010';
const SIGNALING = 'http://127.0.0.1:8080';
const CDP_PORT = 9223; // dedicated port; the spike used 9222
const OUT_DIR = new URL('../output/sango-twin-s3/', import.meta.url).pathname;
const RUN_ARG_IDX = process.argv.indexOf('--run');
const RUN_ID_ARG = RUN_ARG_IDX > -1 ? process.argv[RUN_ARG_IDX + 1] : null;
const KEEP_CHROME = process.argv.includes('--keep-chrome');
const PLAY_WINDOW_S = 10;          // 对拍 window (both views)
const SAMPLE_EVERY_MS = 1000;
const COMPARE_TOLERANCE_S = 2.5;   // Unity sim echo vs web 2D playhead (fetch+meter lag headroom)

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

// ── minimal CDP client (Node 22 native WebSocket; spike harness pattern) ────
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

// Player log (secondary camera evidence): ~/Library/Logs/DefaultCompany/sango/Player.log
function playerLogTail(bytes = 200000) {
  const candidates = [
    join(process.env.HOME, 'Library/Logs/DefaultCompany/sango/Player.log'),
    join(process.env.HOME, 'Library/Logs/Colav/sango/Player.log'),
  ];
  for (const path of candidates) {
    if (!existsSync(path)) continue;
    const content = readFileSync(path);
    return { path, text: content.subarray(Math.max(0, content.length - bytes)).toString('utf8') };
  }
  return null;
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

async function recordSeries(cdp, kind, seconds, everyMs) {
  const read = kind === 'twin'
    ? `(() => { const d = window.__twinBridge ?? {}; return { sim: d.simTime ?? null, playhead: d.playhead ?? null }; })()`
    : `(() => ({ sim: (document.getElementById('replayTimeCurrent')?.textContent ?? '').replace(' s',''), playhead: null }))()`;
  const series = [];
  const start = Date.now();
  while ((Date.now() - start) / 1000 < seconds) {
    const value = await cdp.evaluate(read);
    series.push({ at: Math.round((Date.now() - start) / 100) / 10, ...value });
    await sleep(everyMs);
  }
  return series;
}

const toNum = v => { const n = Number(v); return Number.isFinite(n) ? n : null; };

function seriesStats(series, key) {
  const values = series.map(row => toNum(row[key])).filter(v => v !== null);
  if (!values.length) return null;
  return { first: values[0], last: values[values.length - 1], delta: values[values.length - 1] - values[0], samples: values.length };
}

// ── main ────────────────────────────────────────────────────────────────────
mkdirSync(OUT_DIR, { recursive: true });

const backendOk = await preflight(`${BACKEND}/api/capabilities`, 'backend 8010');
const signalingOk = await preflight(`${SIGNALING}/config`, 'URS signaling 8080');
if (!backendOk || !signalingOk) {
  console.error('\nPreconditions failed: start the backend and the URS signaling webapp first.');
  process.exit(1);
}

// Pick a sealed, playable run.
let runId = RUN_ID_ARG;
if (!runId) {
  const entries = await (await fetch(`${BACKEND}/api/runs?limit=50&summary=true`)).json();
  for (const entry of entries) {
    try {
      const descriptor = await (await fetch(`${BACKEND}/api/runs/${entry.run_id}/replay`)).json();
      const facts = descriptor?.replay ?? {};
      if (String(facts.state).toUpperCase() === 'READY'
        && descriptor?.capabilities?.seekable !== false
        && Number(facts.t_end) - Number(facts.t_start) >= PLAY_WINDOW_S + 5) {
        runId = entry.run_id;
        break;
      }
    } catch { /* skip */ }
  }
}
if (!runId) {
  console.error('No sealed READY run with a playable range found.');
  process.exit(1);
}
console.log(`run: ${runId}`);

// Headless Chrome (own profile, dedicated CDP port).
const profileDir = join(tmpdir(), `sango-twin-probe-${Date.now()}`);
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', '--no-default-browser-check', `--user-data-dir=${profileDir}`,
  '--window-size=1680,1050', 'about:blank',
], { stdio: 'ignore', detached: false });
process.on('exit', () => { try { chrome.kill(); } catch { /* already gone */ } });

let twinStats = null;
let replayStats = null;
let deltaDiff = Number.NaN;
let cameraLogged = false;
let logTail = null;
try {
  await waitFor('chrome CDP endpoint', async () => {
    const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`).then(r => r.json()).catch(() => null);
    return res?.Browser ?? null;
  }, 30000, 300);
  const tab = await openTab(`${BACKEND}/`);
  console.log(`tab: ${tab.id}`);
  await sleep(1500);
  const cdp = await connectCDP();

  // 1) Navigate: Evaluation workface → Digital Twin view.
  await cdp.evaluate(`(() => {
    document.querySelector('[data-workface="evaluation"]')?.click();
    document.getElementById('evalViewTabTwin')?.click();
    return true;
  })()`);
  await waitFor('twin runs table', () => cdp.evaluate(
    `(() => { const t = document.getElementById('twinRunsTable'); return t && t.data && t.data.length > 0; })()`), 20000);

  // 2) Open the sealed run in the twin viewer (real row button; obc-table
  //    renders row cells into its shadow root, so probe light DOM first).
  await cdp.evaluate(`(() => {
    const table = document.getElementById('twinRunsTable');
    if (!table.data.some(row => row.id === '${runId}')) throw new Error('run row missing');
    return true;
  })()`);
  await cdp.evaluate(`(() => {
    const find = root => root && root.querySelector('[aria-label="Open digital twin ${runId.slice(0, 8)}"]');
    const button = find(document) || find(document.getElementById('twinRunsTable')?.shadowRoot);
    if (!button) throw new Error('twin open button missing');
    button.click();
    return true;
  })()`);

  // 3) Video frames arriving.
  const videoInfo = await waitFor('URS video frame', () => cdp.evaluate(`(() => {
    const video = document.getElementById('twinVideo');
    return video && video.srcObject && video.readyState >= 2 && video.videoWidth > 0
      ? { w: video.videoWidth, h: video.videoHeight, t: video.currentTime } : null;
  })()`), 90000);
  check('video frames arriving (URS pixel stream)', true, `${videoInfo.w}x${videoInfo.h}`);

  // 4) Bridge hello/attach → attached + state echo.
  const attached = await waitFor('bridge attached', () => cdp.evaluate(
    `(() => window.__twinBridge?.attached ?? null)()`), 90000);
  check('bridge attached received', attached?.run_id === runId,
    `mode=${attached?.mode} anchor=(${attached?.anchor?.east},${attached?.anchor?.north})`);

  await waitFor('bridge state echo', () => cdp.evaluate(
    `(() => (window.__twinBridge?.lastState && window.__twinBridge.lastState.frame_seq >= 0) ? window.__twinBridge.lastState : null)()`), 90000);
  check('bridge state echo received (frame_seq >= 0)', true);

  // 5) Play 10 s and record the twin SIM TIME series (Unity echo).
  await cdp.evaluate(`document.getElementById('twinPlayPauseBtn').click()`);
  await waitFor('twin playing', () => cdp.evaluate(
    `(() => window.__twinBridge?.clockState === 'PLAYING' || null)()`), 15000);
  const twinSeries = await recordSeries(cdp, 'twin', PLAY_WINDOW_S, SAMPLE_EVERY_MS);
  twinStats = seriesStats(twinSeries, 'sim');
  check('twin SIM TIME advances (Unity echo)', Boolean(twinStats && twinStats.delta > PLAY_WINDOW_S * 0.5),
    `first=${twinStats?.first?.toFixed(2)} last=${twinStats?.last?.toFixed(2)} delta=${twinStats?.delta?.toFixed(2)}s n=${twinStats?.samples}`);
  await cdp.evaluate(`document.getElementById('twinPlayPauseBtn').click()`); // pause

  // 6) Camera preset switch: web button → bridge message → Unity state.camera echo.
  // Two hops (bridge→top) so the Unity-side transition is real even when a
  // previous session left the rig at TopDown (SetView no-ops on same view).
  await cdp.evaluate(`document.querySelector('[data-twin-camera="bridge"]').click()`);
  await waitFor('camera echo (bridge)', () => cdp.evaluate(
    `(() => (window.__twinBridge?.camera === 'bridge') ? 'bridge' : null)()`), 20000);
  await cdp.evaluate(`document.querySelector('[data-twin-camera="top"]').click()`);
  const cameraEcho = await waitFor('camera echo (state.camera=top)', () => cdp.evaluate(
    `(() => (window.__twinBridge?.camera === 'top') ? 'top' : null)()`), 20000);
  check('camera preset echo (bridge→Unity→state.camera)', cameraEcho === 'top');
  logTail = playerLogTail();
  cameraLogged = (logTail?.text?.includes('camera -> TopDown') || logTail?.text?.includes('camera -> Bridge')) ?? false;
  check('camera switch Unity log evidence', cameraLogged, logTail?.path ?? 'player log not found (secondary evidence)');

  // 7) Theme switch + screenshots (day then night, twin viewport with HUD).
  await cdp.evaluate(`document.documentElement.setAttribute('data-obc-theme','day')`);
  await sleep(2500);
  await cdp.screenshot(join(OUT_DIR, 'twin-day.png'));
  await cdp.evaluate(`document.documentElement.setAttribute('data-obc-theme','night')`);
  await sleep(3500); // theme applies via MutationObserver → bridge → weather
  await cdp.screenshot(join(OUT_DIR, 'twin-night.png'));
  await cdp.evaluate(`document.documentElement.setAttribute('data-obc-theme','day')`);
  check('twin viewport screenshots (day/night)',
    existsSync(join(OUT_DIR, 'twin-day.png')) && existsSync(join(OUT_DIR, 'twin-night.png')));

  // 8) Detection toggle exercises the bridge messages (no error response).
  const detectionBefore = await cdp.evaluate(`(() => window.__twinBridge?.sent ?? 0)()`);
  for (const value of ['yolo', 'truth']) {
    await cdp.evaluate(`(() => {
      const select = document.getElementById('twinDetectionSelect');
      select.value = '${value}';
      select.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()`);
    await sleep(400);
  }
  const detectionAfter = await cdp.evaluate(`(() => window.__twinBridge?.sent ?? 0)()`);
  const bridgeErrors = await cdp.evaluate(`(() => window.__twinBridge?.errorCount ?? 0)()`);
  check('detection toggle sends bridge messages', detectionAfter - detectionBefore >= 2, `sent +${detectionAfter - detectionBefore}`);
  check('no bridge errors during probe', bridgeErrors === 0, `errorCount=${bridgeErrors}`);

  // 8.5) Re-attach on the SAME bridge channel (contract §2/§4): close viewer
  // (web sends detach) → open another run without re-hello — Unity must accept
  // the new attach (hello belongs to the channel lifecycle, not the data plane).
  // Same-channel proof = Player.log 'bridge channel open' count unchanged
  // (no stream rebuild) while run B still gets its `attached`.
  let runBId = null;
  const entries = await (await fetch(`${BACKEND}/api/runs?limit=50&summary=true`)).json();
  for (const entry of entries) {
    if (entry.run_id === runId) continue;
    const descriptor = await (await fetch(`${BACKEND}/api/runs/${entry.run_id}/replay`)).json();
    const facts = descriptor?.replay ?? {};
    if (String(facts.state).toUpperCase() === 'READY' && Number(facts.t_end) - Number(facts.t_start) >= 5) {
      runBId = entry.run_id;
      break;
    }
  }
  check('second sealed READY run available for re-attach step', Boolean(runBId), runBId ?? 'none found');
  const logBefore860 = playerLogTail(2_000_000);
  const channelOpensBefore = (logBefore860?.text?.match(/bridge channel open/g) ?? []).length;
  const countersBefore = await cdp.evaluate(`(() => ({ sent: window.__twinBridge?.sent ?? 0, received: window.__twinBridge?.received ?? 0 }))()`);
  await cdp.evaluate(`document.getElementById('twinCloseBtn')?.click()`);
  await waitFor('viewer closed (runs panel back)', () => cdp.evaluate(
    `(() => { const v = document.getElementById('twinViewerPanel'); const r = document.getElementById('twinRunsPanel'); return v && v.hidden && r && !r.hidden ? true : null; })()`), 15000);
  check('viewer closed, detach sent (runs panel back)', true);
  await cdp.evaluate(`(() => {
    const find = root => root && root.querySelector('[aria-label="Open digital twin ${runBId.slice(0, 8)}"]');
    const button = find(document) || find(document.getElementById('twinRunsTable')?.shadowRoot);
    if (!button) throw new Error('twin open button (run B) missing');
    button.click();
    return true;
  })()`);
  const attachedB = await waitFor('bridge attached for run B (same channel, no re-hello)', () => cdp.evaluate(
    `(() => window.__twinBridge?.attached?.run_id === '${runBId}' ? window.__twinBridge.attached : null)()`), 90000);
  check('attach after detach accepted (幂等重挂)', attachedB?.run_id === runBId,
    `runB=${attachedB?.run_id?.slice(0, 8)} mode=${attachedB?.mode} anchor=(${attachedB?.anchor?.east},${attachedB?.anchor?.north})`);
  const logAfter860 = playerLogTail(2_000_000);
  const channelOpensAfter = (logAfter860?.text?.match(/bridge channel open/g) ?? []).length;
  const runBAttachedLogged = logAfter860?.text?.includes(`attach run=${runBId}`) ?? false;
  check('no channel rebuild on re-attach (Player.log: no new bridge channel open, attach logged)',
    channelOpensAfter === channelOpensBefore && runBAttachedLogged,
    `channel opens ${channelOpensBefore}→${channelOpensAfter}, attach run=${runBId.slice(0, 8)} logged=${runBAttachedLogged}`);
  const countersAfter = await cdp.evaluate(`(() => ({ sent: window.__twinBridge?.sent ?? 0, received: window.__twinBridge?.received ?? 0 }))()`);
  check('same client instance reused (message counters grew)', countersAfter.sent > countersBefore.sent && countersAfter.received > countersBefore.received,
    `sent ${countersBefore.sent}→${countersAfter.sent}, received ${countersBefore.received}→${countersAfter.received}`);

  // 9) 对拍: same run in the Replay (web 2D) view for the same window.
  await cdp.evaluate(`document.getElementById('evalViewTabReplay')?.click()`);
  await sleep(500);
  // The replay table paginates (10/page): walk pages until the run's row shows.
  const replayButton = await waitFor('replay open button (paginated)', () => cdp.evaluate(`(() => {
    const find = root => root && root.querySelector('[aria-label^="Open replay ${runId.slice(0, 8)}"]');
    const table = document.getElementById('replayRunsTable');
    let button = find(document) || find(table?.shadowRoot);
    if (button) return true;
    document.getElementById('replayRunsNextBtn')?.click();
    return null;
  })()`), 20000, 400);
  check('replay row reachable (pagination)', replayButton === true);
  await cdp.evaluate(`(() => {
    const find = root => root && root.querySelector('[aria-label^="Open replay ${runId.slice(0, 8)}"]');
    const button = find(document) || find(document.getElementById('replayRunsTable')?.shadowRoot);
    button.click();
    return true;
  })()`);
  await waitFor('replay viewer open', () => cdp.evaluate(
    `(() => { const p = document.getElementById('evaluationReplayPanel'); return p && !p.hidden ? true : null; })()`), 30000);
  await waitFor('replay controls enabled', () => cdp.evaluate(
    `(() => { const t = document.getElementById('replayTimeline'); return t && Number(t.max) > Number(t.min) ? true : null; })()`), 60000);
  // controls-enabled flag lands after the first window load: the status line
  // flips from LOADING RECORDED EVIDENCE to PAUSED · HISTORICAL REPLAY.
  await waitFor('replay status ready', () => cdp.evaluate(
    `(() => { const s = document.getElementById('replayStatusLine')?.textContent ?? ''; return s.includes('PAUSED') || s.includes('PLAYING') ? s : null; })()`), 60000);
  await cdp.evaluate(`document.getElementById('replayPlayPauseBtn').click()`);
  const replaySeries = await recordSeries(cdp, 'replay', PLAY_WINDOW_S, SAMPLE_EVERY_MS);
  replayStats = seriesStats(replaySeries, 'sim');
  check('replay SIM TIME advances (web 2D)', Boolean(replayStats && replayStats.delta > PLAY_WINDOW_S * 0.5),
    `first=${replayStats?.first?.toFixed(2)} last=${replayStats?.last?.toFixed(2)} delta=${replayStats?.delta?.toFixed(2)}s n=${replayStats?.samples}`);

  // 10) Same-run comparison: both series must cover the same wall window at 1×.
  deltaDiff = Math.abs((twinStats?.delta ?? 0) - (replayStats?.delta ?? 0));
  check('same-run SIM TIME 对拍 within tolerance', deltaDiff <= COMPARE_TOLERANCE_S,
    `|twinΔ ${twinStats?.delta?.toFixed(2)}s − replayΔ ${replayStats?.delta?.toFixed(2)}s| = ${deltaDiff.toFixed(2)}s (tol ${COMPARE_TOLERANCE_S}s)`);

  // Artifacts: raw series + console + report.
  writeFileSync(join(OUT_DIR, 'sim-time-series.json'), JSON.stringify({
    run_id: runId, window_s: PLAY_WINDOW_S, sample_every_ms: SAMPLE_EVERY_MS,
    twin: twinSeries, replay: replaySeries,
    twin_stats: twinStats, replay_stats: replayStats, delta_diff_s: deltaDiff,
    captured_at: new Date().toISOString(),
  }, null, 2));
  const debug = await cdp.evaluate(`(() => JSON.stringify(window.__twinBridge ?? null))()`).then(s => JSON.parse(s));
  writeFileSync(join(OUT_DIR, 'probe-console.log'),
    cdp.console.filter(line => line.includes('[Sango.') || line.includes('[page-exception]')).join('\n'));

  const lines = [];
  lines.push('# P2-S3 Digital Twin E2E — sango_twin_bridge_probe');
  lines.push('');
  lines.push(`- date: ${new Date().toISOString()}`);
  lines.push(`- run: \`${runId}\` (sealed READY, seekable)`);
  lines.push(`- twin SIM TIME (Unity state echo, ${PLAY_WINDOW_S}s @1×): first=${twinStats?.first?.toFixed(2)}s last=${twinStats?.last?.toFixed(2)}s Δ=${twinStats?.delta?.toFixed(2)}s (n=${twinStats?.samples})`);
  lines.push(`- replay SIM TIME (web 2D, same run ${PLAY_WINDOW_S}s @1×): first=${replayStats?.first?.toFixed(2)}s last=${replayStats?.last?.toFixed(2)}s Δ=${replayStats?.delta?.toFixed(2)}s (n=${replayStats?.samples})`);
  lines.push(`- 对拍 |Δtwin − Δreplay| = ${Number.isFinite(deltaDiff) ? deltaDiff.toFixed(2) : '?'}s (tolerance ${COMPARE_TOLERANCE_S}s)`);
  lines.push(`- bridge totals: sent=${debug?.sent} received=${debug?.received} attached=${debug?.attached ? 'yes' : 'no'} stateCameraEcho=${debug?.camera} simTimeEcho=${debug?.simTime}`);
  lines.push(`- camera Unity log evidence: ${cameraLogged ? 'yes' : 'no'} (${logTail?.path ?? 'log not found'})`);
  lines.push('');
  lines.push('## Assertions');
  lines.push('');
  for (const item of assertions) lines.push(`- ${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.detail ? ` — ${item.detail}` : ''}`);
  writeFileSync(join(OUT_DIR, 'report.md'), lines.join('\n') + '\n');

  console.log(`\nartifacts: ${OUT_DIR}`);
} finally {
  if (!KEEP_CHROME) {
    try { chrome.kill(); } catch { /* gone */ }
    await sleep(500);
    try { rmSync(profileDir, { recursive: true, force: true }); } catch { /* best effort */ }
  }
}

if (failures.length) {
  console.error(`\n${failures.length} assertion(s) FAILED`);
  process.exit(1);
}
console.log('\nALL ASSERTIONS PASSED');
process.exit(0);
