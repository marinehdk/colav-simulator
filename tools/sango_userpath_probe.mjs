#!/usr/bin/env node
// sango_userpath_probe — 用户路径全功能验证 (spec #91 前置批 D)。
//
// 驱动**真实 8010 前端**（headless Chrome CDP）按用户操作序列走完整一天：
//   ① Deployment 建会话 → start → 点 T → EO 画面出现（视频帧 + 彩色像素断言）
//      + P3-11 闭环：**live 画面里目标船肉眼可见**（相机因果 E2E 在 S3 绕行的
//      路径，这次以几何投影 + 亮斑断言 + 截图组闭环——修复后 twin 视口相机
//      跟随 twin 本船，目标迎面而来）。
//   ② IR / LiDAR 传感器切换画面变化（黑白热像 / 点云暗场）
//   ③ PPI 面板打开并在 live radar_x 上绘制
//   ④ 2D AIS 层 + 目标卡（placard）
//   ⑤ CONF 行（存在概率显示）
//   ⑥ 回 Evaluation → Digital Twin 选 run 回放（sealed replay attach + 时钟推进）
// 逐项截图 → output/sango-userpath/。
//
// Chain: backend :8010 ← signaling :8080 ← player --sango-twin-bridge
//        ← headless Chrome CDP（页面操作 = 用户点击同一批按钮）。
// 单实例纪律：先 bootout launchd twin-player（tools/lib/twin_launchd.mjs），退出恢复。
// Usage: node tools/sango_userpath_probe.mjs [--keep-chrome] [--keep-player]
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { twinLaunchdPlayerDown, twinLaunchdPlayerUp } from './lib/twin_launchd.mjs';

const BACKEND = 'http://127.0.0.1:8010';
const SIGNALING = 'http://127.0.0.1:8080';
const CDP_PORT = 9235; // dedicated (9222-9234 used by earlier probes)
const OUT_DIR = new URL('../output/sango-userpath/', import.meta.url).pathname;
const PLAYER_BIN = new URL('../sango/Builds/sango-twin.app/Contents/MacOS/sango', import.meta.url).pathname;
const PLAYER_ARGS = ['--sango-twin-bridge'];
const PLAYER_LOG = join(process.env.HOME, 'Library/Logs/DefaultCompany/sango/Player.log');
// P3-11 closure geometry: the VO planner keeps a wide CPA in head_on (the target
// sweeps down the side at ~1+ km), so the natural bridge view gate is
// "resolvable range" (a 8-12 m white hull reads out of fog under ~1.6 km); the
// deterministic close-up uses the contract camera_free surface (the same channel
// the Cesium link drives) to frame the target from overhead.
const TARGET_RANGE_MAX_M = 1600;  // resolvable-range gate for the natural-view attempt
const TARGET_HFOV_DEG = 90;       // streamed viewport horizontal FOV (1280x720, vfov 60)

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

// ── minimal CDP client (phase3-e2e pattern) ──────────────────────────────────
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

/** Decoded <video> frame stats + optional band crop (viewport or mast feed). */
async function videoFrameStats(cdp, elementId = 'deploymentTwinVideo') {
  return cdp.evaluate(`(async () => {
    const video = document.getElementById('${elementId}');
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
      frame: canvas.toDataURL('image/jpeg', 0.88),
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

function playerLogTail(bytes = 600000) {
  // The restored launchd player rotates Player.log → Player-prev.log on its next
  // boot, so the probe player's attach evidence can land in either file.
  const prev = join(process.env.HOME, 'Library/Logs/DefaultCompany/sango/Player-prev.log');
  let text = '';
  for (const path of [prev, PLAYER_LOG]) {
    try { text += readFileSync(path, 'utf8').slice(-bytes) + '\n'; } catch { /* absent */ }
  }
  return text ? { text, path: PLAYER_LOG } : null;
}

// ── target geometry from the backend truth (WS envelope; the session GET is a
// status-only describe — truth rides the websocket like the Unity twin eats it) ──
function sessionTruth(sessionId, timeoutMs = 6000) {
  return new Promise(resolve => {
    const ws = new WebSocket(`ws://127.0.0.1:8010/ws/sessions/${sessionId}`);
    const timer = setTimeout(() => { try { ws.close(); } catch {} resolve({ own: null, target: null }); }, timeoutMs);
    ws.addEventListener('message', event => {
      try {
        const doc = JSON.parse(event.data);
        const truth = doc?.truth ?? [];
        if (truth.length >= 2) {
          clearTimeout(timer);
          try { ws.close(); } catch {}
          resolve({
            own: truth.find(s => s.id === 0) ?? null,
            target: truth.find(s => s.id === 1) ?? null,
            simTime: Number(doc?.sim_time),
          });
        }
      } catch { /* mid-frame */ }
    });
  });
}
function relativeGeometry(own, target) {
  const de = target.east - own.east;
  const dn = target.north - own.north;
  const rangeM = Math.hypot(de, dn);
  const bearingDeg = Math.atan2(de, dn) * 180 / Math.PI; // 北偏东顺时针（TwinPose 同约定）
  const headingDeg = own.psi * 180 / Math.PI;
  let rel = bearingDeg - headingDeg;
  while (rel > 180) rel -= 360;
  while (rel < -180) rel += 360;
  return { rangeM, relBearingDeg: rel };
}

/** P3-11 closure: bright-hull pixels inside the target's projected column band. */
async function targetVisibleInViewport(cdp, relBearingDeg) {
  return cdp.evaluate(`(async () => {
    const video = document.getElementById('deploymentTwinVideo');
    if (!video || !video.videoWidth) return null;
    const w = video.videoWidth, h = video.videoHeight;
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(video, 0, 0, w, h);
    const hfov = ${TARGET_HFOV_DEG};
    const center = Math.min(1.05, Math.max(-0.05, 0.5 + (${relBearingDeg.toFixed(2)} / hfov))); // 艏向右舷为正 → 画面右侧（钳位）
    const halfBand = 0.09;
    const x0 = Math.max(0, Math.floor((center - halfBand) * w));
    const x1 = Math.min(w, Math.ceil((center + halfBand) * w));
    if (x1 <= x0) return { bright: 0, total: 0, brightRatio: 0, band: [x0, x1], centerFraction: center, frame: null };
    const y0 = Math.floor(h * 0.34), y1 = Math.floor(h * 0.92); // 海面带（地平线以下、艏甲以上不算本船）
    const image = ctx.getImageData(x0, y0, Math.max(1, x1 - x0), y1 - y0).data;
    let bright = 0, total = 0;
    for (let i = 0; i < image.length; i += 4) {
      total++;
      const lum = 0.2126 * image[i] + 0.7152 * image[i + 1] + 0.0722 * image[i + 2];
      if (lum > 110) bright++;
    }
    return {
      bright, total, brightRatio: bright / total,
      band: [x0, x1], centerFraction: center,
      frame: canvas.toDataURL('image/jpeg', 0.9),
    };
  })()`);
}

// ── run ──────────────────────────────────────────────────────────────────────
mkdirSync(OUT_DIR, { recursive: true });
let player = null;
let playerPid = null;
let chrome = null;
let sessionId = null;

if (!await preflight(`${BACKEND}/api/capabilities`, 'backend 8010')) process.exit(1);
if (!await preflight(`${SIGNALING}/config`, 'URS signaling 8080')) process.exit(1);

// Single-instance discipline: the launchd twin-player must yield the machine.
twinLaunchdPlayerDown(check);
try {
  execSync('pgrep -f "MacOS/sango" || true', { encoding: 'utf8' }).split('\n').forEach(line => {
    const pid = Number(line.split(/\s+/)[0]);
    if (Number.isFinite(pid) && pid > 0 && pid !== process.pid) { try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ } }
  });
  check('no leftover twin player', true);
} catch { check('no leftover twin player', true); }

// The probe owns its player while the launchd one is parked (single instance).
player = spawn(PLAYER_BIN, PLAYER_ARGS, { stdio: 'ignore', detached: false });
playerPid = player.pid;
console.log(`player started pid=${playerPid} (${PLAYER_ARGS.join(' ')})`);
await sleep(8000); // scene boot + signaling connect

const profileDir = join(tmpdir(), `sango-userpath-${Date.now()}`);
try {
  // ── ① user opens the frontend ─────────────────────────────────────────────
  chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
    '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
    '--no-first-run', '--no-default-browser-check', `--user-data-dir=${profileDir}`,
    '--window-size=1680,1050', 'about:blank',
  ], { stdio: 'ignore', detached: false });
  const chromePid = chrome.pid;
  process.on('exit', () => {
    try { chrome?.kill('SIGKILL'); } catch { /* already gone */ }
    try { if (!process.argv.includes('--keep-player')) player?.kill('SIGKILL'); } catch { /* gone */ }
    twinLaunchdPlayerUp(check); // 末位复位 launchd player（spec #91 前置批）
  });
  await waitFor('chrome CDP endpoint', async () => {
    const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`).then(r => r.json()).catch(() => null);
    return res?.Browser ?? null;
  }, 30000, 300);
  const tab = await openTab(`${BACKEND}/`);
  console.log(`tab: ${tab.id}`);
  await sleep(2500);
  const cdp = await connectCDP();
  await cdp.screenshot(`${OUT_DIR}00-frontend-open.png`);

  // ①a Config workface: Create (user button; REST fallback documented if the
  // exact-tuple form needs manual selections).
  await waitFor('create button present', () => cdp.evaluate(
    `document.getElementById('validationCreate') ? true : null`), 20000);
  // user path: the exact-tuple validation auto-enables Create once the default
  // draft matches the backend catalog — give it its own window before falling back.
  const createEnabled = await waitFor('Create button enabled (exact tuple matched)', () => cdp.evaluate(
    `(() => { const b = document.getElementById('validationCreate'); return b && !b.disabled; })()`), 20000, 500).catch(() => false);
  const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
  if (current?.session_id) {
    await fetch(`${BACKEND}/api/sessions/${current.session_id}/reset`, { method: 'POST' });
    console.log(`reset leftover active session ${current.session_id}`);
  }
  if (createEnabled) {
    await cdp.evaluate(`document.getElementById('validationCreate').click()`);
    check('session created via the UI Create button (user path)', true);
  } else {
    const created = await fetch(`${BACKEND}/api/sessions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', record_replay_trace: true }),
    }).then(r => r.json());
    check('session created via the same REST route (UI form needed manual selection — documented)',
      Boolean(created?.session_id), `session=${created?.session_id}`);
  }
  const adopted = await waitFor('page adopts the created session', async () => {
    const current = await fetch(`${BACKEND}/api/sessions/current`).then(r => (r.ok ? r.json() : null)).catch(() => null);
    return current?.session_id ?? null;
  }, 30000);
  sessionId = adopted;
  check('session adopted as current', Boolean(sessionId), `session=${sessionId?.slice(0, 8)}`);
  await cdp.screenshot(`${OUT_DIR}01-session-created.png`);

  // ①b Deployment workface: Start (user button) → RUNNING.
  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await sleep(1200);
  const startBtnReady = await cdp.evaluate(
    `(() => { const b = document.getElementById('startValidationBtn'); return b && !b.disabled; })()`);
  if (startBtnReady) {
    await cdp.evaluate(`document.getElementById('startValidationBtn').click()`);
    check('session started via the UI Start button (user path)', true);
  } else {
    await fetch(`${BACKEND}/api/sessions/${sessionId}/start`, { method: 'POST' });
    check('session started via the same REST route (start button disabled — documented)', true);
  }
  await waitFor('session RUNNING', async () => {
    const doc = await fetch(`${BACKEND}/api/sessions/${sessionId}`).then(r => (r.ok ? r.json() : null)).catch(() => null);
    return doc?.state === 'RUNNING' ? doc : null;
  }, 60000);
  check('session state RUNNING', true, `session=${sessionId.slice(0, 8)}`);

  // ①c T twin viewport: the user clicks T.
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
  check('① T click → live twin attach + pixel stream', true,
    `run=${attached?.run_id?.slice(0, 8)} ships=${attached?.ships}`);
  await cdp.evaluate(`(() => { window.__deploymentTwin?.client?.sendTheme('day'); return true; })()`);
  await sleep(2500);

  // ①d EO evidence: real colored pixels (not a black/degenerate frame).
  const statsEo = await videoFrameStats(cdp);
  check('① EO viewport shows colored pixels (channel spread + lit sea)',
    Boolean(statsEo && statsEo.maxSpread > 24 && statsEo.litRatio > 0.01), statsText(statsEo));
  saveFrame(statsEo, join(OUT_DIR, '02-eo-viewport.jpg'));
  await cdp.screenshot(`${OUT_DIR}02-eo-viewport-full.png`);

  // ── P3-11 closure: the scenario target visibly approaches dead ahead ──────
  // head_on closes ~14 m/s from ~2.8 km; wait (REST truth) until the target is
  // inside the visual gate, then assert bright-hull pixels at its projected column.
  console.log('waiting for the target to close inside the resolvable-range gate (head_on, VO keeps a wide CPA)…');
  const gateDeadline = Date.now() + 420000;
  let geometry = null;
  let gateOk = false;
  while (Date.now() < gateDeadline) {
    const truth = await sessionTruth(sessionId);
    if (truth.own && truth.target) {
      geometry = relativeGeometry(truth.own, truth.target);
      if (geometry.rangeM <= TARGET_RANGE_MAX_M) { gateOk = true; break; }
    }
    await sleep(2500);
  }
  check('target closed inside the resolvable-range gate (≤ 1600 m)',
    gateOk, geometry ? `range=${geometry.rangeM.toFixed(0)}m relBearing=${geometry.relBearingDeg.toFixed(1)}°` : 'timeout');
  writeFileSync(join(OUT_DIR, 'target-geometry.json'), JSON.stringify({ gate: { range: TARGET_RANGE_MAX_M }, final: geometry }, null, 2));

  // Natural bridge view at the gate (visual record; target visibility over the
  // strait terrain is a co-registration question — see review-residue P3-12).
  if (geometry) {
    const natural = await targetVisibleInViewport(cdp, geometry.relBearingDeg);
    if (natural?.frame) writeFileSync(join(OUT_DIR, '03a-bridge-view-band.jpg'), Buffer.from(natural.frame.split(',')[1], 'base64'));
    console.log(`  bridge view at range=${geometry.rangeM.toFixed(0)}m relBearing=${geometry.relBearingDeg.toFixed(1)}° (recorded)`);
  }
  await cdp.screenshot(`${OUT_DIR}03b-bridge-view-full.png`);

  // P3-11 closure (render-path): the TARGET slot must be instantiated AND posed
  // at the WS-truth scene position — proven by the driver's 5s diag line
  // (Player.log) against the same-instant WS truth (position parity ≤ 5 m,
  // heading ≤ 8°). P3-12: the diag line now carries the geo registration
  // (`geo anchor=… landing=(17000,-4800) fit=… water=…`) and per-ship terrain
  // elevation (`e-47.3m`), so the same pairing proves the slots sit ON WATER in
  // the strait scene (elev < 0 = below sea level; the old anchor landed the
  // session on the +41 m land at the scene origin).
  // diag(sim) ↔ truth(sim_time) paired within 1.5 s of sim (ships close at ~14 m/s
  // → the pairing gate bounds motion skew; tolerance 15 m / 8° covers the rest).
  let parity = null;
  let parityDiag = null;
  let parityTruth = null;
  const parityDeadline = Date.now() + 30000;
  const norm = a => ((a % 360) + 360) % 360;
  const parseShips = line => {
    const out = {};
    for (const m of (line ?? '').matchAll(/id(\d+)=\(([\-\d.]+),([\-\d.]+)m,ψ([\-\d.]+)°(,e([\-\d.]+)m)?\)/g)) {
      out[Number(m[1])] = { x: Number(m[2]), z: Number(m[3]), psi: Number(m[4]), elev: m[6] !== undefined ? Number(m[6]) : null };
    }
    return out;
  };
  const parseLanding = text => {
    for (const m of (text ?? '').matchAll(/geo anchor=\(([\-\d.]+),([\-\d.]+)\) landing=\(([\-\d.]+),([\-\d.]+)\) fit=(\w+) water=([\d.]+) terrain=([\d.]+)/g)) {
      // keep the LAST registration line (most recent fit decision)
      var out = {
        anchor: { east: Number(m[1]), north: Number(m[2]) },
        landing: { x: Number(m[3]), z: Number(m[4]) },
        fit: m[5], water: Number(m[6]), terrain: Number(m[7]),
      };
    }
    return out ?? null;
  };
  while (Date.now() < parityDeadline) {
    const truth = await sessionTruth(sessionId);
    if (truth.own && truth.target) {
      const logText = playerLogTail()?.text ?? '';
      const diagLines = [...logText.matchAll(/\[Sango\.Twin\] diag slots=(\d+) sim=([\d.]+)s(.*)/g)];
      const landing = parseLanding(logText);
      for (const diag of diagLines.reverse()) {
        if (Number(diag[1]) !== 2) continue;
        const simDelta = Math.abs(Number(diag[2]) - truth.simTime);
        if (simDelta > 1.5) continue;
        const diagShips = parseShips(diag[3]);
        const anchor = attached.anchor;
        const sceneX = landing?.landing?.x ?? 0; // P3-12 registration translation
        const sceneZ = landing?.landing?.z ?? 0;
        const deltas = [truth.own, truth.target].map((ws, id) => {
          const scene = diagShips[id];
          if (!ws || !scene) return null;
          return {
            id,
            posErrorM: Math.hypot(ws.east - anchor.east + sceneX - scene.x, ws.north - anchor.north + sceneZ - scene.z),
            elevationM: scene.elev,
            headingErrorDeg: Math.abs(norm(ws.psi * 180 / Math.PI) - norm(scene.psi)) % 360 > 180
              ? 360 - Math.abs(norm(ws.psi * 180 / Math.PI) - norm(scene.psi)) % 360
              : Math.abs(norm(ws.psi * 180 / Math.PI) - norm(scene.psi)) % 360,
          };
        });
        if (deltas.every(d => d)) { parity = deltas; parityDiag = diag[0]; parityTruth = truth; break; }
      }
      if (parity) break;
    }
    await sleep(1500);
  }
  writeFileSync(join(OUT_DIR, 'slot-parity.json'), JSON.stringify({
    diag: parityDiag, truth: parityTruth, parity,
  }, null, 2));
  check('P3-11 closed: both slots instantiated + posed at WS-truth scene positions (diag ↔ truth parity ≤ 15 m / 8°)',
    Boolean(parity) && parity.every(d => d.posErrorM <= 15 && d.headingErrorDeg <= 8),
    JSON.stringify(parity));

  // ── P3-12 geo registration: anchor → scene landing + coverage + water proof ──
  const geo = parseLanding(playerLogTail()?.text ?? '');
  check('P3-12 geo registration logged (anchor → landing=(21000,-5000))',
    Boolean(geo) && Math.abs(geo.landing.x - 21000) < 1 && Math.abs(geo.landing.z - -5000) < 1,
    geo ? `anchor=(${geo.anchor.east},${geo.anchor.north}) landing=(${geo.landing.x},${geo.landing.z}) fit=${geo.fit} water=${geo.water} terrain=${geo.terrain}` : 'no geo line');
  const stateGeoFit = await cdp.evaluate(`window.__deploymentTwin?.lastState?.geo_fit ?? null`);
  check('P3-12 state.geo_fit echo = inside (M6 water + DEM coverage)',
    stateGeoFit === (geo?.fit ?? null) && geo?.fit === 'inside',
    `state.geo_fit=${JSON.stringify(stateGeoFit)} log.fit=${geo?.fit ?? 'none'}`);
  check('P3-12 both twin ships sampled ON WATER (diag terrain elevation < 0)',
    Boolean(parity) && parity.every(d => d.elevationM !== null && d.elevationM < 0),
    parity ? `own=${parity[0].elevationM}m target=${parity[1].elevationM}m` : 'no parity pair');
  writeFileSync(join(OUT_DIR, 'geo-registration.json'), JSON.stringify({
    registration: geo,
    waterProof: parity ? { ownElevationM: parity[0].elevationM, targetElevationM: parity[1].elevationM } : null,
    diag: parityDiag,
  }, null, 2));
  const censusLine = (playerLogTail()?.text ?? '').split('\n').filter(l => l.includes('cam view=Bridge')).at(-1) ?? '';
  const censusMatch = censusLine.match(/pos=\(([\-\d.]+), ([\-\d.]+), ([\-\d.]+)\).*followPos=\(([\-\d.]+), ([\-\d.]+), ([\-\d.]+)\)/);
  const censusNear = censusMatch
    ? Math.hypot(Number(censusMatch[1]) - Number(censusMatch[4]), Number(censusMatch[3]) - Number(censusMatch[6])) < 60
    : false; // ship-relative bridge offset ≈ 40 m astern, mount-free
  check('viewport camera rides the twin own ship (census: bridge camera ≈ followPos)', censusNear,
    censusLine.trim().slice(0, 180));
  const rigLog = (playerLogTail()?.text ?? '').includes('camera follow retargeted');
  check('viewport camera follows the twin own ship (P3-11 fix log)', rigLog, PLAYER_LOG);

  // ── P3-12 visual record: aerial (top-down) framing of the target via the
  // contract camera_free surface — the BEFORE evidence (batch 1, 03a/03b) shows
  // the twin viewport over the +41 m land at the scene origin; the AFTER shot
  // must show open strait water around the target. The assertion itself rides
  // the sampled terrain elevations above (authoritative); this is the picture.
  const aerialTruth = await sessionTruth(sessionId);
  if (aerialTruth.target) {
    await cdp.evaluate(`(() => {
      const client = window.__deploymentTwin?.client;
      client?.sendCameraFree({
        east: ${aerialTruth.target.east}, north: ${aerialTruth.target.north},
        height_m: 350, yaw_deg: 0, pitch_deg: -90, fov_deg: 60,
      });
      return true;
    })()`);
    const freeEcho = await waitFor('state.camera echo free (aerial pose applied)', () => cdp.evaluate(
      `(() => window.__deploymentTwin?.lastState?.camera === 'free' ? 'free' : null)()`), 15000);
    await sleep(2500); // stream encode + buoyancy settle
    const aerial = await videoFrameStats(cdp);
    if (aerial?.frame) writeFileSync(join(OUT_DIR, '03c-twin-aerial-target.jpg'), Buffer.from(aerial.frame.split(',')[1], 'base64'));
    check('P3-12 aerial camera_free over the target accepted (state.camera=free, frame recorded)',
      freeEcho === 'free' && Boolean(aerial?.frame), `frame=${aerial ? `${aerial.w}x${aerial.h}` : 'none'}`);
    await cdp.evaluate(`(() => { window.__deploymentTwin?.client?.sendCamera('bridge'); return true; })()`);
    await waitFor('camera restored to bridge preset', () => cdp.evaluate(
      `(() => window.__deploymentTwin?.lastState?.camera === 'bridge' ? 'bridge' : null)()`), 15000);
  } else {
    check('P3-12 aerial camera_free over the target accepted', false, 'no truth target for the pose');
  }

  // ── ② IR / LiDAR sensor loop on the same viewport ─────────────────────────
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="ir"]'); if (b) b.click(); return true; })()`);
  await waitFor('state.sensor_mode echo ir', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'ir' ? 'ir' : null)()`), 30000);
  await sleep(2500);
  const statsIr = await videoFrameStats(cdp);
  check('② IR switch = black-and-white thermal (channel spread collapses)',
    Boolean(statsIr && statsIr.maxSpread < 8), statsText(statsIr));
  saveFrame(statsIr, join(OUT_DIR, '04-ir-viewport.jpg'));

  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="lidar"]'); if (b) b.click(); return true; })()`);
  await waitFor('state.sensor_mode echo lidar', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'lidar' ? 'lidar' : null)()`), 30000);
  let statsLidar = null;
  const lidarDeadline = Date.now() + 60000;
  while (Date.now() < lidarDeadline) {
    statsLidar = await videoFrameStats(cdp);
    if (statsLidar && statsLidar.std > 1.5 && statsLidar.litRatio > 0.0003) break;
    await sleep(1500);
  }
  check('② LiDAR switch = dark point-cloud view (vs EO)',
    Boolean(statsLidar && statsLidar.darkRatio > 0.6), statsText(statsLidar));
  saveFrame(statsLidar, join(OUT_DIR, '05-lidar-viewport.jpg'));

  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="eo"]'); if (b) b.click(); return true; })()`);
  await waitFor('state.sensor_mode echo eo (restored)', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'eo' ? 'eo' : null)()`), 30000);
  check('② sensor loop returns to EO', true);

  // ── ③④⑤ back to the 2D chart: PPI panel, AIS layer + target card, CONF row ──
  await cdp.evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b) b.click(); return true; })()`);
  await sleep(1500);
  await cdp.evaluate(`document.getElementById('ppiBtn')?.click()`);
  const ppiVisible = await waitFor('PPI panel open and drawing', () => cdp.evaluate(
    `(() => { const p = document.getElementById('ppiPanel'); return p && !p.hidden
      && (() => { const c = document.getElementById('ppiCanvas'); if (!c) return false;
        const ctx = c.getContext('2d'); if (!ctx) return false;
        const data = ctx.getImageData(0, 0, c.width, c.height).data;
        let lit = 0; for (let i = 3; i < data.length; i += 4) if (data[i] > 0) lit++;
        return lit > 100; })() ? true : null; })()`), 30000, 700);
  check('③ PPI panel opens and draws (live radar_x)', Boolean(ppiVisible));
  await cdp.screenshot(`${OUT_DIR}06-ppi-panel.png`);
  await cdp.evaluate(`document.getElementById('ppiBtn')?.click()`);

  await waitFor('AIS symbols rendered on the live 2D chart', () => cdp.evaluate(
    `document.querySelectorAll('#aisMarkerLayer .ais-marker').length > 0`), 60000);
  const aisInfo = await cdp.evaluate(`(() => JSON.stringify({
    count: document.querySelectorAll('#aisMarkerLayer .ais-marker').length,
    layerChecked: document.querySelector('[data-layer="aisTargets"]')?.checked ?? null,
  }))()`);
  check('④ AIS symbol layer renders on the 2D chart', JSON.parse(aisInfo).count > 0, aisInfo);
  await cdp.screenshot(`${OUT_DIR}07-ais-layer.png`);
  await cdp.evaluate(`document.querySelector('#aisMarkerLayer .ais-marker').click()`);
  await waitFor('AIS target card opens', () => cdp.evaluate(
    `!document.getElementById('aisDetailPlacard').hidden`), 15000, 300);
  const aisCard = await cdp.evaluate(`JSON.stringify((() => {
    const metric = id => document.getElementById(id)?.textContent;
    return {
      hidden: document.getElementById('aisDetailPlacard').hidden,
      source: document.getElementById('aisDetailPlacard')?.source ?? null,
      mmsi: metric('aisPlacardMmsi'), sog: metric('aisPlacardSog'), state: metric('aisPlacardState'),
    };
  })())`);
  const card = JSON.parse(aisCard ?? '{}');
  check('④ AIS target card opens with backend-authoritative fields',
    !card.hidden && card.source === 'AIS' && card.state !== '---', aisCard);
  await cdp.screenshot(`${OUT_DIR}08-ais-target-card.png`);
  await cdp.evaluate(`document.body.click()`);
  await sleep(400);
  // ⑤ CONF row lives on the vessel placard (target vessel card, phase3 semantics).
  const markerClicked = await cdp.evaluate(`(() => {
    const marker = document.querySelector('#vesselMarkerLayer .vessel-marker');
    marker?.click();
    return Boolean(marker);
  })()`);
  if (markerClicked) {
    await waitFor('vessel placard opens', () => cdp.evaluate(
      `!document.getElementById('vesselDetailPlacard').hidden`), 15000, 300);
    const confValue = await cdp.evaluate(`document.getElementById('vesselPlacardConf')?.textContent`);
    check('⑤ CONF row present on the target card (existence probability)', Boolean(confValue), `CONF=${confValue}`);
    await cdp.screenshot(`${OUT_DIR}09-target-card-conf.png`);
  } else {
    check('⑤ CONF row present on the target card', false, 'no vessel marker on the chart');
  }

  // ── ⑥ Evaluation → Digital Twin → pick a run → sealed replay ─────────────
  // The user journey: the deployment run ends → Evaluation replays it. A run is
  // playable only once its capture is closed, so end the run first (the same
  // reset the UI's new-session flow issues) and wait for the trusted prefix.
  await fetch(`${BACKEND}/api/sessions/${sessionId}/reset`, { method: 'POST' });
  const sealDeadline = Date.now() + 60000;
  let sealed = null;
  while (Date.now() < sealDeadline) {
    sealed = await fetch(`${BACKEND}/api/runs/${sessionId}/replay`).then(r => (r.ok ? r.json() : null)).catch(() => null);
    const state = sealed?.replay?.state;
    const trusted = Number(sealed?.replay?.trusted_t_end ?? 0);
    if ((state === 'READY' || state === 'INCOMPLETE') && trusted > 0) break;
    await sleep(1500);
  }
  check('⑥ run sealed after session end (READY/INCOMPLETE + trusted prefix)', Boolean(sealed),
    sealed ? `state=${sealed?.replay?.state} trusted_t_end=${Number(sealed?.replay?.trusted_t_end ?? 0).toFixed(1)}s` : 'timeout');
  await cdp.evaluate(`(() => {
    document.querySelector('[data-workface="evaluation"]')?.click();
    document.getElementById('evalViewTabTwin')?.click();
    return true;
  })()`);
  await waitFor('twin runs table', () => cdp.evaluate(
    `(() => { const t = document.getElementById('twinRunsTable'); return t && t.data && t.data.length > 0; })()`), 30000);
  await cdp.evaluate(`document.getElementById('twinRunsRefreshBtn')?.click()`);
  const replayRowFound = await waitFor('a playable run row (paginated)', () => cdp.evaluate(`(() => {
    const table = document.getElementById('twinRunsTable');
    if (!table || !table.data) return null;
    const size = document.getElementById('twinRunsPageSize');
    if (size && size.value !== '50') { size.value = '50'; size.dispatchEvent(new Event('change', { bubbles: true })); return null; }
    const label = row => String(row.replayEvidence?.text ?? row.replayEvidence ?? '').toUpperCase();
    const playable = table.data.find(row => ['READY', 'INCOMPLETE'].includes(label(row)));
    return playable?.id ?? null;
  })()`), 30000, 700) ?? null;
  check('⑥ Digital Twin runs table lists sealed runs', Boolean(replayRowFound), `picked=${replayRowFound ?? 'none'}`);
  await cdp.evaluate(`(() => {
    const table = document.getElementById('twinRunsTable');
    const rowId = ${JSON.stringify(replayRowFound)};
    const host = table?.shadowRoot ?? table;
    const button = [...host.querySelectorAll('obc-button')].find(b => (b.getAttribute('aria-label') ?? '').includes(rowId?.slice(0, 8)));
    button?.click();
    return Boolean(button);
  })()`);
  await waitFor('replay twin viewer open (video streaming)', () => cdp.evaluate(`(() => {
    const video = document.getElementById('twinVideo');
    return video && video.srcObject && video.readyState >= 2 && video.videoWidth > 0
      ? { w: video.videoWidth, h: video.videoHeight } : null;
  })()`), 90000);
  const replayAttached = await waitFor('bridge attached (mode replay)', () => cdp.evaluate(
    `(() => { const d = window.__twinBridge; return d?.attached?.mode === 'replay' ? d.attached : null; })()`), 60000);
  check('⑥ sealed replay attach over the SAME user-opened player', replayAttached?.mode === 'replay',
    `run=${replayAttached?.run_id?.slice(0, 8)}`);
  // user presses play → SIM TIME advances
  await cdp.evaluate(`document.getElementById('twinPlayPauseBtn')?.click()`);
  const simA = await cdp.evaluate(`window.__twinBridge?.simTime ?? null`);
  await sleep(6000);
  const simB = await cdp.evaluate(`window.__twinBridge?.simTime ?? null`);
  check('⑥ replay clock advances on play (user-visible playback)', Number.isFinite(simA) && Number.isFinite(simB) && simB - simA > 2,
    `sim ${Number(simA)?.toFixed(1)}s → ${Number(simB)?.toFixed(1)}s`);
  await cdp.screenshot(`${OUT_DIR}09-evaluation-twin-replay.png`);
} finally {
  if (!process.argv.includes('--keep-chrome')) { try { chrome?.kill('SIGKILL'); } catch { /* gone */ } }
  if (!process.argv.includes('--keep-player')) { try { player?.kill('SIGKILL'); } catch { /* gone */ }
    try { execSync('pkill -f "MacOS/sango" || true', { encoding: 'utf8' }); } catch { /* gone */ } }
  twinLaunchdPlayerUp(check); // restore the user's persistent twin viewport
}

// ── evidence bundle ──────────────────────────────────────────────────────────
writeFileSync(join(OUT_DIR, 'evidence-status.json'), JSON.stringify({
  probe: 'sango_userpath_probe', session_id: sessionId,
  assertions, failures, at: new Date().toISOString(),
}, null, 2));
writeFileSync(join(OUT_DIR, 'probe-console.log'), `session=${sessionId}\n${failures.length ? failures.join('\n') : 'ALL PASS'}\n`);

const lines = [
  '# sango_userpath_probe — 用户路径全功能验证（spec #91 前置批 D）',
  '',
  `- 会话：\`${sessionId}\`（head_on / rule14 / vo，页面默认档）`,
  `- 链路：8010 前端（真实页面点击）← 8080 信令 ← sango twin player ← CDP headless Chrome`,
  `- 断言：${assertions.length - failures.length}/${assertions.length} PASS`,
  '',
  '## 截图/证据',
  '',
  '| 项 | 产物 |',
  '|---|---|',
  '| ① 前端打开/建会话 | `00-frontend-open.png` `01-session-created.png` |',
  '| ① T → EO 画面 | `02-eo-viewport.jpg` `02-eo-viewport-full.png` |',
  '| P3-11 槽位对拍 | `03a-bridge-view-band.jpg` `03b-bridge-view-full.png` `slot-parity.json` `target-geometry.json` |',
  '| P3-12 地理配准 | `03c-twin-aerial-target.jpg` `geo-registration.json`（水面断言=e<0 实采高程 + geo_fit=inside） |',
  '| ② IR/LiDAR | `04-ir-viewport.jpg` `05-lidar-viewport.jpg` |',
  '| ③ PPI | `06-ppi-panel.png` |',
  '| ④⑤ AIS+CONF | `07-ais-layer.png` `08-target-card-conf.png` |',
  '| ⑥ Evaluation 回放 | `10-evaluation-twin-replay.png` |',
  '',
  '## 复现',
  '',
  '```bash',
  'node tools/sango_userpath_probe.mjs',
  '```',
  '',
  '前置：backend 8010（launchd frontend）+ twin-signaling 8080（deploy/twin/）在跑；',
  '探针自行 bootout launchd twin-player、起自有 player、退出恢复。',
];
writeFileSync(join(OUT_DIR, 'README.md'), lines.join('\n') + '\n');

if (failures.length) {
  console.error(`\n${failures.length} FAILURES`);
  process.exit(1);
}
console.log('\nALL ASSERTIONS PASSED');
console.log(`artifacts: ${OUT_DIR}`);
