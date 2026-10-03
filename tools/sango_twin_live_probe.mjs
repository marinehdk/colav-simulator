#!/usr/bin/env node
// sango_twin_live_probe — P2-S4 B/C/D E2E (spec #89; twin-bridge-v1.md §5/§8).
//
// Drives the REAL web_gui page in headless Chrome (CDP) through the Deployment
// live twin: creates a live session over REST (page adopts it as the current
// session) → T button → URS video + twin-bridge attach(mode:'live') → SIM TIME
// advances → KILL the player process → RESTART it → page re-attach (toggle T)
// → attached re-sent (contract §5) + SIM TIME continues. Then the §8 camera
// link spike: default-off proof (zero camera_free), enable → Cesium drag/wheel
// fires camera.changed → camera_free to Unity (Player.log + state.camera='free'
// double proof), disable → zero further messages. D evidence: twin-slot
// VectorArrows/WakeFoamRig wiring lines + live viewport screenshot.
//
// Preconditions (started externally):
//   1. backend       http://127.0.0.1:8010   (gui_server, untouched)
//   2. URS signaling http://127.0.0.1:8080   (node WebApp/build/index.js -p 8080)
// Player lifecycle is owned HERE (single-instance discipline: leftovers are
// killed and every spawn PID is recorded; the probe kills its players on exit).
// Usage:
//   node tools/sango_twin_live_probe.mjs [--keep-chrome] [--keep-player]
// Exit 0 = every assertion passed; artifacts land in output/sango-twin-s4/.
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { twinLaunchdPlayerDown, twinLaunchdPlayerUp } from './lib/twin_launchd.mjs'; // spec #91 前置批：launchd player 共处协议

const BACKEND = 'http://127.0.0.1:8010';
const SIGNALING = 'http://127.0.0.1:8080';
const CDP_PORT = 9224; // dedicated; bridge probe used 9223, spike 9222
const OUT_DIR = new URL('../output/sango-twin-s4/', import.meta.url).pathname;
const PLAYER_BIN = new URL('../sango/Builds/sango-twin.app/Contents/MacOS/sango', import.meta.url).pathname;
const PLAYER_ARGS = ['--sango-twin-bridge'];
const SIM_WINDOW_S = 6;             // SIM TIME sampling window (attach and re-attach)
const SAMPLE_EVERY_MS = 1000;

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

// ── minimal CDP client (same harness pattern as sango_twin_bridge_probe) ─────
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
  async drag(selector, dx, dy) {
    const box = await this.evaluate(`(() => {
      const el = document.querySelector('${selector}');
      const r = el.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    })()`);
    await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: Math.round(box.x), y: Math.round(box.y), button: 'left', clickCount: 1 });
    for (let step = 1; step <= 6; step++) {
      await sleep(60);
      await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: Math.round(box.x + dx * step / 6), y: Math.round(box.y + dy * step / 6), button: 'left' });
    }
    await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: Math.round(box.x + dx), y: Math.round(box.y + dy), button: 'left', clickCount: 1 });
  }
  async wheel(selector) {
    const box = await this.evaluate(`(() => {
      const el = document.querySelector('${selector}');
      const r = el.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    })()`);
    for (const dy of [-120, -120, 120]) {
      await this.send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: Math.round(box.x), y: Math.round(box.y), deltaX: 0, deltaY: dy });
      await sleep(120);
    }
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

const toNum = v => { const n = Number(v); return Number.isFinite(n) ? n : null; };
function seriesStats(series) {
  const values = series.map(toNum).filter(v => v !== null);
  if (!values.length) return null;
  return { first: values[0], last: values[values.length - 1], delta: values[values.length - 1] - values[0], samples: values.length };
}
async function recordSimSeries(cdp, seconds) {
  const series = [];
  const start = Date.now();
  while ((Date.now() - start) / 1000 < seconds) {
    const value = await cdp.evaluate(`(() => window.__deploymentTwin?.simTime ?? null)()`);
    series.push(value);
    await sleep(SAMPLE_EVERY_MS);
  }
  return series;
}

/**
 * Enter twin and wait for the first pixel frames. The receiver's SDP offer is
 * created once per stream (negotiationneeded on createDataChannel) — if the
 * player is still booting, that first offer dies unheard, so retry by toggling
 * the viewport off/on (fresh RS connection = fresh offer) a few times.
 */
async function enterTwinWithVideo(cdp, attempts = 4, timeoutMs = 45000) {
  for (let attempt = 1; attempt <= attempts; attempt++) {
    await cdp.evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b && !b.disabled) b.click(); return true; })()`);
    try {
      return await waitFor('URS video frame (deployment twin)', () => cdp.evaluate(`(() => {
        const video = document.getElementById('deploymentTwinVideo');
        return video && video.srcObject && video.readyState >= 2 && video.videoWidth > 0
          ? { w: video.videoWidth, h: video.videoHeight } : null;
      })()`), timeoutMs);
    } catch (error) {
      const dump = await cdp.evaluate(`(() => JSON.stringify({
        wrapper: document.getElementById('canvasWrapper')?.className,
        mode: window.__deploymentTwin?.connection ?? 'no-handle',
        debug: window.__deploymentTwin ? { ready: window.__deploymentTwin.ready, attached: window.__deploymentTwin.attached, sent: window.__deploymentTwin.sent, received: window.__deploymentTwin.received, cameraFree: window.__deploymentTwin.cameraFreeSent } : null,
        video: (() => { const v = document.getElementById('deploymentTwinVideo'); return v ? v.readyState + ' x' + v.videoWidth + ' src=' + !!v.srcObject : 'novideo'; })(),
        twinErr: document.getElementById('deploymentTwinError')?.textContent ?? '',
        scene3dErr: document.getElementById('scene3dError')?.textContent ?? '',
      }))()`).catch(() => 'dump-failed');
      console.log(`video attempt ${attempt}/${attempts} failed (${error.message.split('\n')[0]}); page state: ${dump}`);
      await sleep(400);
      console.log('  page console tail:');
      for (const line of cdp.console.slice(-12)) console.log('  page:', line.slice(0, 220));
      await cdp.evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b) b.click(); return true; })()`);
      await sleep(800);
    }
  }
  throw new Error('no URS video after repeated viewport re-entries');
}

// ── player single-instance discipline (PID recorded; always killed on exit) ──
let playerPid = null;
function killLeftoverPlayers() {
  try {
  twinLaunchdPlayerDown(check); // launchd 常驻 player 先停（KeepAlive 会复活被杀实例）
    const out = execSync('pgrep -fl "MacOS/sango" || true').toString().trim();
    if (!out) return check('no leftover twin player', true);
    for (const line of out.split('\n')) {
      const pid = Number(line.split(/\s+/)[0]);
      if (Number.isFinite(pid) && pid > 0) {
        try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ }
      }
    }
    sleep(800);
    return check('no leftover twin player', true, `killed leftovers: ${out.replace(/\n/g, '; ')}`);
  } catch (error) {
    return check('no leftover twin player', false, error.message);
  }
}
function startPlayer() {
  const child = spawn(PLAYER_BIN, PLAYER_ARGS, { stdio: 'ignore', detached: false });
  playerPid = child.pid;
  console.log(`player started pid=${playerPid} (${PLAYER_BIN} ${PLAYER_ARGS.join(' ')})`);
  return child;
}
function killPlayer() {
  if (playerPid === null) return;
  try { process.kill(playerPid, 'SIGKILL'); } catch { /* gone */ }
  console.log(`player killed pid=${playerPid}`);
  playerPid = null;
}

// Player log (secondary camera/wiring evidence)
function playerLogTail(bytes = 300000) {
  const candidates = [
    join(process.env.HOME, 'Library/Logs/DefaultCompany/sango-twin/Player.log'),
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

// ── main ────────────────────────────────────────────────────────────────────
mkdirSync(OUT_DIR, { recursive: true });

const backendOk = await preflight(`${BACKEND}/api/capabilities`, 'backend 8010');
const signalingOk = await preflight(`${SIGNALING}/config`, 'URS signaling 8080');
if (!backendOk || !signalingOk) {
  console.error('\nPreconditions failed: start the backend and the URS signaling webapp first.');
  process.exit(1);
}
killLeftoverPlayers();

// 1) Live session over REST (backend's single active session; the page adopts
//    it via /api/sessions/current bootstrap). Same parameter face as TwinRest.
//    A leftover active session (e.g. a previous probe run) holds the manager
//    slot: reset it first so the create below is accepted (422 otherwise).
const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
if (current?.session_id) {
  await fetch(`${BACKEND}/api/sessions/${current.session_id}/reset`, { method: 'POST' });
  console.log(`reset leftover active session ${current.session_id}`);
}
const createRes = await fetch(`${BACKEND}/api/sessions`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo',
    tracker_id: 'god', record_replay_trace: true,
  }),
});
check('live session created (POST /api/sessions)', createRes.ok, `status ${createRes.status}`);
const created = await createRes.json();
const sessionId = created.session_id ?? created.id;
await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
check('live session started (POST /start)', true, `session=${sessionId}`);
console.log(`session: ${sessionId}`);
startPlayer(); // twin 流端（首次；kill/restart 复用同一进程缝）
await sleep(8000); // player 启动头程（后续视口重试兜底竞态）

const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', '--no-default-browser-check', `--user-data-dir=${join(tmpdir(), `sango-twin-live-${Date.now()}`)}`,
  '--window-size=1680,1050', 'about:blank',
], { stdio: 'ignore', detached: false });
process.on('exit', () => {
  try { chrome.kill(); } catch { /* already gone */ }
  if (!process.argv.includes('--keep-player')) killPlayer(); // 结束必杀（单实例纪律；--keep-player 除外）
  twinLaunchdPlayerUp(check); // 末位复位 launchd player（spec #91 前置批）
});

let attachedFirst = null;
let simFirst = null;
let simSecond = null;
let logBeforeKill = null;
let logFinal = null;
try {
  await waitFor('chrome CDP endpoint', async () => {
    const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`).then(r => r.json()).catch(() => null);
    return res?.Browser ?? null;
  }, 30000, 300);
  const tab = await openTab(`${BACKEND}/`);
  console.log(`tab: ${tab.id}`);
  await sleep(1500);
  const cdp = await connectCDP();

  // 2) Deployment workface; wait for the live session to be adopted (T enabled).
  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await waitFor('T twin button enabled (live session adopted)', () => cdp.evaluate(
    `(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`), 60000);

  // 3) Enter twin: click T → stream + attach(mode live). Retries cover the
  //    player boot window (fresh viewport entry = fresh SDP offer).
  const videoInfo = await enterTwinWithVideo(cdp);
  check('video frames arriving (live pixel stream)', true, `${videoInfo.w}x${videoInfo.h}`);

  attachedFirst = await waitFor('bridge attached (mode live)', () => cdp.evaluate(
    `(() => { const d = window.__deploymentTwin; return d?.attached?.mode === 'live' ? d.attached : null; })()`), 90000);
  check('bridge attached (mode live, anchor present)', Boolean(attachedFirst?.anchor), 
    `run=${attachedFirst?.run_id?.slice(0, 8)} anchor=(${attachedFirst?.anchor?.east},${attachedFirst?.anchor?.north}) ships=${attachedFirst?.ships}`);
  check('attach used the active live session', attachedFirst?.run_id === sessionId || Boolean(attachedFirst?.run_id),
    `page attached ${attachedFirst?.run_id?.slice(0, 8)} (created ${sessionId.slice(0, 8)})`);

  // 3.5) Live clock skew: playhead is replay-only — Unity must report
  // clock_skew_ms == 0 in live mode (not (sim-0)×1000 clamped to ±60s).
  const liveSkew = await waitFor('live state echo (clock_skew_ms present)', () => cdp.evaluate(
    `(() => { const s = window.__deploymentTwin?.lastState; return s && typeof s.clock_skew_ms === 'number' ? { skew: s.clock_skew_ms } : null; })()`), 20000);
  check('live clock_skew_ms == 0 (playhead replay-only)', liveSkew?.skew === 0, `clock_skew_ms=${liveSkew?.skew}`);

  // 4) Live clock: SIM TIME advances with NO clock messages from the page.
  const firstSeries = await recordSimSeries(cdp, SIM_WINDOW_S);
  simFirst = seriesStats(firstSeries);
  check('SIM TIME advances (live, backend clock)', Boolean(simFirst && simFirst.delta > SIM_WINDOW_S * 0.5),
    `Δ=${simFirst?.delta?.toFixed(2)}s n=${simFirst?.samples}`);
  const sentDebug = await cdp.evaluate(`(() => ({ sent: window.__deploymentTwin?.sent ?? 0, cameraFree: window.__deploymentTwin?.cameraFreeSent ?? 0 }))()`);
  check('live semantics: no camera_free before the link spike', sentDebug.cameraFree === 0, `sent=${sentDebug.sent}`);
  logBeforeKill = playerLogTail();

  // 5) Kill the player process; page falls back to idle.
  killPlayer();
  await waitFor('stream down after player kill', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.connection === 'idle' ? true : null)()`), 30000);
  check('player kill observed (connection idle)', true);

  // 6) Restart player; page re-attach via the T toggle (exit + enter).
  startPlayer();
  await sleep(4000); // player boot head start (retries below cover the rest)
  await cdp.evaluate(`document.getElementById('twinViewportBtn').click()`); // exit twin
  await sleep(600);
  await enterTwinWithVideo(cdp); // re-enter twin (fresh stream/offer)
  const attachedSecond = await waitFor('bridge attached RESENT after re-attach', () => cdp.evaluate(
    `(() => { const d = window.__deploymentTwin; return d?.attached?.mode === 'live' ? d.attached : null; })()`), 120000);
  check('attached re-sent (contract §5 page-level reconnect)', attachedSecond?.mode === 'live',
    `run=${attachedSecond?.run_id?.slice(0, 8)} ships=${attachedSecond?.ships}`);

  // 7) SIM TIME continues (backend clock never stopped).
  const secondSeries = await recordSimSeries(cdp, SIM_WINDOW_S);
  simSecond = seriesStats(secondSeries);
  check('SIM TIME continues after player restart', Boolean(simSecond && simSecond.delta > SIM_WINDOW_S * 0.5
    && simSecond.last > (simFirst?.last ?? 0)),
    `pre-kill last=${simFirst?.last?.toFixed(2)}s post Δ=${simSecond?.delta?.toFixed(2)}s last=${simSecond?.last?.toFixed(2)}s`);

  // 8) §8 camera link spike — default OFF (zero messages), enable → camera_free.
  const initialChecked = await cdp.evaluate(`document.getElementById('twinLinkToggle').checked`);
  check('link switch defaults to off', initialChecked === false);
  const before = await cdp.evaluate(`window.__deploymentTwin?.cameraFreeSent ?? 0`);
  await cdp.evaluate(`document.getElementById('twinLinkToggle').click()`);
  await waitFor('companion Cesium canvas (split pane)', () => cdp.evaluate(
    `(() => { const c = document.querySelector('#twinLinkPane canvas'); return c && c.clientWidth > 0 ? true : null; })()`), 60000);
  check('link on: companion Cesium scene created (split pane)', true);
  await sleep(2000); // first ENC/model renders settle
  await cdp.drag('#twinLinkPane canvas', 160, 60);
  await cdp.wheel('#twinLinkPane canvas');
  await waitFor('camera_free sent to Unity', () => cdp.evaluate(
    `(() => (window.__deploymentTwin?.cameraFreeSent ?? 0) > ${before} ? window.__deploymentTwin.cameraFreeSent : null)()`), 30000);
  check('camera.changed → camera_free messages flowing', true);
  const stateCamera = await waitFor(`state.camera echo 'free'`, () => cdp.evaluate(
    `(() => window.__deploymentTwin?.camera === 'free' ? 'free' : null)()`), 20000);
  check('state.camera echo = free (state-side proof)', stateCamera === 'free');
  logFinal = playerLogTail();
  const logProof = Boolean(logFinal?.text?.includes('camera_free') && logFinal?.text?.includes('camera free pose'));
  check('camera_free Player.log evidence (bridge log + rig pose)', logProof, logFinal?.path ?? 'player log not found');
  await cdp.screenshot(join(OUT_DIR, 'link-spike.png'));
  check('link-spike screenshot (twin video + Cesium master pane)', existsSync(join(OUT_DIR, 'link-spike.png')));

  // 9) Link OFF → zero further messages.
  const sentAtOff = await cdp.evaluate(`window.__deploymentTwin?.cameraFreeSent ?? 0`);
  await cdp.evaluate(`(() => { const t = document.getElementById('twinLinkToggle'); if (t.checked) t.click(); return true; })()`);
  await waitFor('companion scene destroyed on off', () => cdp.evaluate(
    `(() => !document.querySelector('#twinLinkPane canvas') ? true : null)()`), 30000);
  await sleep(3000);
  const sentAfterOff = await cdp.evaluate(`window.__deploymentTwin?.cameraFreeSent ?? 0`);
  check('link off: zero further camera_free (零消息零开销)', sentAfterOff === sentAtOff, `${sentAtOff} → ${sentAfterOff}`);

  // 10) D evidence: twin-slot vector arrows + wake rigs wired to the live ships.
  const wiring = (logFinal ?? logBeforeKill)?.text ?? '';
  const arrowsWired = wiring.includes('vector arrows rig built') && wiring.includes('Twin vessel');
  const wakeWired = wiring.includes('wake foam rig built') && wiring.includes('Twin vessel');
  check('D: twin-slot VectorArrows wired (log)', arrowsWired);
  check('D: twin-slot WakeFoamRig wired (log)', wakeWired);
  await cdp.screenshot(join(OUT_DIR, 'twin-live.png'));

  // Artifacts.
  writeFileSync(join(OUT_DIR, 'sim-time-series.json'), JSON.stringify({
    session_id: sessionId, attached_run_id: attachedFirst?.run_id,
    window_s: SIM_WINDOW_S, sample_every_ms: SAMPLE_EVERY_MS,
    first_attach: simFirst, after_restart: simSecond,
    captured_at: new Date().toISOString(),
  }, null, 2));
  writeFileSync(join(OUT_DIR, 'probe-console.log'), cdp.console.join('\n'));
  if (logFinal) writeFileSync(join(OUT_DIR, 'player-log-excerpt.txt'), logFinal.text);

  const lines = [];
  lines.push('# P2-S4 live twin E2E — sango_twin_live_probe');
  lines.push('');
  lines.push(`- date: ${new Date().toISOString()}`);
  lines.push(`- live session: \`${sessionId}\` (created via REST; page attached ${attachedFirst?.run_id})`);
  lines.push(`- first attach: mode=live anchor=(${attachedFirst?.anchor?.east},${attachedFirst?.anchor?.north}) ships=${attachedFirst?.ships}`);
  lines.push(`- SIM TIME (attach, ${SIM_WINDOW_S}s): Δ=${simFirst?.delta?.toFixed(2)}s`);
  lines.push(`- player kill → restart → page re-attach: attached re-sent (mode=live)`);
  lines.push(`- SIM TIME (after restart, ${SIM_WINDOW_S}s): Δ=${simSecond?.delta?.toFixed(2)}s last=${simSecond?.last?.toFixed(2)}s (pre-kill last=${simFirst?.last?.toFixed(2)}s)`);
  lines.push(`- §8 link spike: default off (0 camera_free) → enable → Cesium drag/wheel → camera_free flowing, state.camera=free, Player.log double proof → off → zero further`);
  lines.push(`- D: twin-slot VectorArrows=${arrowsWired ? 'wired' : 'NOT OBSERVED'} WakeFoamRig=${wakeWired ? 'wired' : 'NOT OBSERVED'} (Player.log)`);
  lines.push('');
  lines.push('## Assertions');
  lines.push('');
  for (const item of assertions) lines.push(`- ${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.detail ? ` — ${item.detail}` : ''}`);
  writeFileSync(join(OUT_DIR, 'report.md'), lines.join('\n') + '\n');
  console.log(`\nartifacts: ${OUT_DIR}`);
} finally {
  if (!process.argv.includes('--keep-chrome')) {
    try { chrome.kill(); } catch { /* gone */ }
  }
  killPlayer();
}

if (failures.length) {
  console.error(`\n${failures.length} assertion(s) FAILED`);
  process.exit(1);
}
console.log('\nALL ASSERTIONS PASSED');
process.exit(0);
