#!/usr/bin/env node
// sango_twin_lidar_probe — P3-S3 E2E (spec #90; twin-bridge-v1.md §8 sensor_mode=lidar 真实现).
//
// Live kf-vocabulary session → player twin → sensor_mode cycle eo→ir→lidar→eo through
// the REAL Deployment twin button group, with the lidar frame proven as a point-cloud
// view by decoded-stream statistics (deep-dark backdrop + sparse lit points vs the
// eo color frame — the S2 maxSpread technique extended with a dark/lit ratio) and the
// Player.log double proof (sensor_mode -> lidar + lidar point-cloud view active).
//
//   backend :8010        live session (observations S2 routes untouched)
//   signaling :8080      URS webapp
//   player               --sango-twin-bridge (bridge + mast rig + lidar passes)
//   Chrome headless CDP  drives web_gui Deployment twin viewport
//
// Lifecycle discipline: player + Chrome owned here (leftovers killed, every PID killed
// on exit; probe-session cleanup is same-day per repo discipline). Artifacts →
// output/sango-twin-s3-lidar/.
// Usage: node tools/sango_twin_lidar_probe.mjs [--keep-chrome] [--keep-player]
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BACKEND = 'http://127.0.0.1:8010';
const SIGNALING = 'http://127.0.0.1:8080';
const CDP_PORT = 9226; // dedicated (9222-9225 used by earlier probes)
const OUT_DIR = new URL('../output/sango-twin-s3-lidar/', import.meta.url).pathname;
const PLAYER_BIN = new URL('../sango/Builds/sango-twin.app/Contents/MacOS/sango', import.meta.url).pathname;
const PLAYER_ARGS = ['--sango-twin-bridge'];

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

// ── minimal CDP client (obs-probe harness pattern) ───────────────────────────
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
 * Decoded <video> frame statistics (obs-probe technique, extended for the
 * point-cloud double proof): grayscale mean/std, channel spread, the DARK
 * fraction (backdrop coverage) and the LIT fraction (sparse lidar points).
 */
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

// ── process lifecycle (single-instance discipline) ───────────────────────────
let playerPid = null;
let chrome = null;
function cleanup() {
  for (const [pid, label] of [[playerPid, 'player'], [chrome?.pid, 'chrome']]) {
    if (!pid) continue;
    try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ }
    console.log(`${label} killed pid=${pid}`);
  }
}
process.on('exit', cleanup);
async function killLeftovers() {
  for (const pattern of ['MacOS/sango', 'sango_detector_service']) {
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

const statsText = stats => stats
  ? `mean=${stats.mean?.toFixed(1)} std=${stats.std?.toFixed(1)} spread=${stats.maxSpread} dark=${stats.darkRatio?.toFixed(2)} lit=${stats.litRatio?.toFixed(4)}`
  : 'no frame';

// ── main ────────────────────────────────────────────────────────────────────
mkdirSync(OUT_DIR, { recursive: true });

const backendOk = await preflight(`${BACKEND}/api/capabilities`, 'backend 8010');
const signalingOk = await preflight(`${SIGNALING}/config`, 'URS signaling 8080');
if (!backendOk || !signalingOk) {
  console.error('\nPreconditions failed: backend 8010 + URS signaling 8080 required.');
  process.exit(1);
}

killLeftovers();

// 1) Live session (same recipe as the S2 obs probe; the lidar leg adds no routes).
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

// 2) Player (bridge flag; mast rig + lidar passes ride the twin scene).
const player = spawn(PLAYER_BIN, PLAYER_ARGS, { stdio: 'ignore', detached: false });
playerPid = player.pid;
console.log(`player started pid=${playerPid} (${PLAYER_ARGS.join(' ')})`);
await sleep(8000);

// 3) Headless Chrome → Deployment twin viewport.
chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', '--no-default-browser-check', `--user-data-dir=${join(tmpdir(), `sango-twin-lidar-${Date.now()}`)}`,
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

const stats = { eo: null, ir: null, lidar: null, lidarTop: null, eoRestored: null };
try {
  await cdp.evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
  await waitFor('T twin button enabled (live session adopted)', () => cdp.evaluate(
    `(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`), 60000);

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

  await cdp.evaluate(`(() => { window.__deploymentTwin?.client?.sendTheme('day'); return true; })()`);
  await sleep(1500);

  // 4) EO baseline (color frame).
  await sleep(1500);
  stats.eo = await videoFrameStats(cdp);
  check('EO baseline frame captured', Boolean(stats.eo && stats.eo.std > 0.5), statsText(stats.eo));
  check('EO frame artifact', saveFrame(stats.eo, join(OUT_DIR, 'eo-frame.jpg')));
  await cdp.screenshot(join(OUT_DIR, 'eo-mode.png'));

  // 5) IR still works (S2 path must not regress inside the cycle).
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="ir"]'); if (b) b.click(); return true; })()`);
  const echoIr = await waitFor('state.sensor_mode echo ir', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'ir' ? 'ir' : null)()`), 30000);
  check('IR switch: state echo sensor_mode=ir', echoIr === 'ir');
  await sleep(2500);
  stats.ir = await videoFrameStats(cdp);
  check('IR = black-and-white thermal (max channel spread ~0)', Boolean(stats.ir && stats.ir.maxSpread <= 12),
    stats.ir ? `maxSpread=${stats.ir.maxSpread}` : 'no frame');
  check('IR frame artifact', saveFrame(stats.ir, join(OUT_DIR, 'ir-frame.jpg')));

  // 6) LIDAR: the P3-S3 real implementation. The mast cloud only shows content
  // inside 100 m (HDRP Water is transparent → sea surface absent by design), so
  // wait for the head_on intruder to close into the band before capturing.
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="lidar"]'); if (b) b.click(); return true; })()`);
  const echoLidar = await waitFor('state.sensor_mode echo lidar', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'lidar' ? 'lidar' : null)()`), 30000);
  check('LiDAR switch: state echo sensor_mode=lidar (contract §3)', echoLidar === 'lidar');
  const chipText = await cdp.evaluate(`document.getElementById('deploymentTwinSensorMode')?.textContent ?? ''`);
  check('sensor-mode chip shows the un-pended LiDAR label', chipText.trim() === 'SENSOR LiDAR', chipText);
  await waitFor('mast rig attached + feed rewired (Player.log)', () => {
    const log = playerLogTail();
    return log?.text?.includes('mast rig attached') && log?.text?.includes('frame feed rewired -> mast_ptz_eo') ? log : null;
  }, 60000);
  console.log('  … waiting for point content (intruder closing into the 100 m band; cap 300 s)');
  const lidarDeadline = Date.now() + 300000;
  let polls = 0;
  while (Date.now() < lidarDeadline) {
    await sleep(3000);
    stats.lidar = await videoFrameStats(cdp);
    polls++;
    if (polls % 20 === 0) console.log(`  … ${statsText(stats.lidar)}`);
    if (stats.lidar && stats.lidar.std > 1.5 && stats.lidar.litRatio > 0.0003) break;
  }
  check('LiDAR frame captured', Boolean(stats.lidar && stats.lidar.std > 0.5), statsText(stats.lidar));
  check('LiDAR = deep-dark backdrop (dark fraction dominates EO)',
    Boolean(stats.lidar && stats.eo && stats.lidar.darkRatio > 0.6 && stats.lidar.darkRatio > stats.eo.darkRatio + 0.25),
    `lidar dark=${stats.lidar?.darkRatio?.toFixed(2)} vs eo dark=${stats.eo?.darkRatio?.toFixed(2)}`);
  check('LiDAR = point cloud on the backdrop (sparse lit points present)',
    Boolean(stats.lidar && stats.lidar.litRatio > 0.0003 && stats.lidar.litRatio < 0.5),
    `lit=${stats.lidar?.litRatio?.toFixed(4)}`);
  check('LiDAR mean luminance collapses vs EO (quantified frame diff)',
    Boolean(stats.lidar && stats.eo && stats.lidar.mean < stats.eo.mean * 0.6),
    `lidar mean=${stats.lidar?.mean?.toFixed(1)} vs eo mean=${stats.eo?.mean?.toFixed(1)}`);
  check('LiDAR frame artifact (decoded stream frame)', saveFrame(stats.lidar, join(OUT_DIR, 'lidar-frame.jpg')));
  await cdp.screenshot(join(OUT_DIR, 'lidar-mode.png'));

  // Top-down camera preset over the same lidar mode: own-ship/near-field band
  // as points from above (second viewpoint; presets stay orthogonal, contract §2).
  await cdp.evaluate(`(() => { window.__deploymentTwin?.client?.sendCamera('top'); return true; })()`);
  await sleep(3000);
  stats.lidarTop = await videoFrameStats(cdp);
  check('LiDAR top-preset frame captured (camera/lidar orthogonality)',
    Boolean(stats.lidarTop && stats.lidarTop.std > 0.5), statsText(stats.lidarTop));
  check('LiDAR top-preset frame artifact', saveFrame(stats.lidarTop, join(OUT_DIR, 'lidar-top-frame.jpg')));
  await cdp.screenshot(join(OUT_DIR, 'lidar-top-mode.png'));
  await cdp.evaluate(`(() => { window.__deploymentTwin?.client?.sendCamera('bridge'); return true; })()`);
  await sleep(2000);

  // 7) Back to EO: color returns (mode state machine restores the default render).
  await cdp.evaluate(`(() => { const b = document.querySelector('#deploymentTwinSensorGroup [data-twin-sensor="eo"]'); if (b) b.click(); return true; })()`);
  const echoEo = await waitFor('state.sensor_mode echo eo', () => cdp.evaluate(
    `(() => window.__deploymentTwin?.sensorMode === 'eo' ? 'eo' : null)()`), 30000);
  check('EO restore: state echo sensor_mode=eo', echoEo === 'eo');
  await sleep(2500);
  stats.eoRestored = await videoFrameStats(cdp);
  check('EO restore = visible light (channel spread returns)',
    Boolean(stats.eoRestored && stats.eoRestored.maxSpread > 24),
    stats.eoRestored ? `maxSpread=${stats.eoRestored.maxSpread}` : 'no frame');
  check('EO restored frame artifact', saveFrame(stats.eoRestored, join(OUT_DIR, 'eo-restored-frame.jpg')));

  // 8) Player.log double proof.
  const logFinal = playerLogTail();
  const logProof = Boolean(
    logFinal?.text?.includes('sensor_mode -> lidar')
    && logFinal?.text?.includes('lidar point-cloud view active')
    && logFinal?.text?.includes('mast rig attached'));
  check('Player.log double proof (sensor_mode -> lidar + lidar point-cloud view active + mast rig)', logProof, logFinal?.path ?? 'not found');

  // Artifacts.
  writeFileSync(join(OUT_DIR, 'frame-stats.json'), JSON.stringify({
    session_id: sessionId, captured_at: new Date().toISOString(), stats,
  }, null, 2));
  if (logFinal) writeFileSync(join(OUT_DIR, 'player-log-excerpt.txt'), logFinal.text);
  writeFileSync(join(OUT_DIR, 'probe-console.log'), cdp.console.join('\n'));

  const lines = [];
  lines.push('# P3-S3 LiDAR point-cloud view E2E — sango_twin_lidar_probe');
  lines.push('');
  lines.push(`- date: ${new Date().toISOString()}`);
  lines.push(`- live session: \`${sessionId}\` (rule14/head_on/vo, tracker=god — capabilities gate)`);
  lines.push(`- mode cycle: eo → ir → lidar → eo through the real Deployment button group; state echoes all four`);
  lines.push(`- EO baseline: ${statsText(stats.eo)}`);
  lines.push(`- IR (S2 non-regression): ${statsText(stats.ir)}`);
  lines.push(`- LiDAR: ${statsText(stats.lidar)} — dark backdrop + sparse lit points, mean < 0.6× EO`);
  lines.push(`- LiDAR top-preset (camera orthogonality): ${statsText(stats.lidarTop)}`);
  lines.push(`- EO restore: ${statsText(stats.eoRestored)}`);
  lines.push('');
  lines.push('## 点云管线选型（写档）');
  lines.push('');
  lines.push('- 路线 = HDRP 17 CustomPass 官方 API（survey §2.1）：`LidarViewPass` 全屏 pass 挂流相机');
  lines.push('  BeforePostProcess，逐 5px cell 反投影光线、取流相机自身深度场');
  lines.push('  （`CustomPassLoadCameraDepth`——render-graph 原生同相机通道），按世界仰角 snap 到');
  lines.push('  VLP-16 的 16 通道画点：深色背景 + 噪声点阵。');
  lines.push('- 跨相机方案弃选理由（调试台账，shader 头注）：mast_lidar 深度采集相机 → 流相机 cross-camera');
  lines.push('  纹理采样在 render-graph custom pass 内不绑定（RT 未注册），且 quad/mesh/SV_InstanceID');
  lines.push('  非全屏 draw 全部不可见——仅全屏 DrawProcedural(3,1) 可靠执行；材质属性（矩阵/向量/浮点）');
  lines.push('  可靠、Update 期 shader global 不绑定。最终改为流相机自身深度场的"LiDAR-vision"点阵。');
  lines.push('- v1 偏差（写档）：①点阵锚定流相机视场（"LiDAR-vision"），非桅顶 mast_lidar 的 90°x32° 物理');
  lines.push('  视场——mast_lidar 机位行保留（后端接触模型互钉 + 升级位），跨相机重投影留后续段；');
  lines.push('  ②角度抖动（AWSIM 0.057°）在屏幕锚定实现中不可观测，噪声链保留距离高斯+dropout+衰减；');
  lines.push('  ③HDRP Water 部分写入深度 → 海面点以暗色出现（低矮高程 ramp），船/岸/浮标可辨。');
  lines.push('- 两路独立（硬边界）：Unity 点云只做视景不回传；后端 `LidarContactSensor`（sensor_id=4，');
  lines.push('  旁路）按几何真值自产接触点，两路零数据交换。');
  lines.push('');
  lines.push('## 噪声参数表（survey §2.3 先例照抄）');
  lines.push('');
  lines.push('| 参数 | 值 | 先例 |');
  lines.push('|---|---|---|');
  lines.push('| 距离高斯 σ 基值 | 0.02 m | AWSIM/RGL（survey §2.3） |');
  lines.push('| 距离高斯 σ 斜率 | 0.002 /m（可调项，无先例钉值 → 100 m 处 σ=0.22 m） | AWSIM「rise per meter 可调」 |');
  lines.push('| 角度高斯 σ | 0.057°（方位/俯仰同） | AWSIM/RGL（survey §2.3） |');
  lines.push('| dropoff general rate | 0.45 | CARLA lidar 默认（survey §2.3） |');
  lines.push('| dropoff intensity limit | 0.8 | CARLA lidar 默认 |');
  lines.push('| zero intensity | 0.4（远端亮度下限） | CARLA lidar 默认 |');
  lines.push('| 大气衰减 | 0.004 /m（强度 1−a·d，50 m 触发 dropoff） | CARLA atmosphere_attenuation_rate |');
  lines.push('');
  lines.push('## 降采样说明');
  lines.push('');
  lines.push('- mast_lidar 深度相机：640×184 pinhole（90°×32°，aspect=tan45°/tan16°），far=100 m 量程裁剪；');
  lines.push('- 16 线栅格：VLP-16 通道 -15°…+15°（2° 步距）落在 32° FOV 的 1° 上下边距内 →');
  lines.push('  通道 i 采样深度图 v=(2i+1)/32（精确 texel 中心，point sampling 零插值斜偏）；');
  lines.push('- 每线 640 采样：u=(j+0.5)/640（针孔 tan 域等像素列，方位由像素射线反解）；');
  lines.push('- 10 Hz 帧节拍：噪声/图案种子按 0.1 s 重掷（深度纹理逐帧连续，点云视觉按 10 Hz 刷新）；');
  lines.push('- 16×640 = 10240 点/帧 ≈ 10.2 万点/s（VLP-16 单回波 30 万点/s 同量级）。');
  lines.push('');
  lines.push('## Assertions');
  lines.push('');
  for (const item of assertions) lines.push(`- ${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.detail ? ` — ${item.detail}` : ''}`);
  writeFileSync(join(OUT_DIR, 'report.md'), lines.join('\n') + '\n');
  console.log(`\nartifacts: ${OUT_DIR}`);
} finally {
  if (!process.argv.includes('--keep-chrome')) { try { chrome?.kill('SIGKILL'); } catch { /* gone */ } }
  if (!process.argv.includes('--keep-player')) { try { player.kill('SIGKILL'); } catch { /* gone */ } }
}

if (failures.length) {
  console.error(`\n${failures.length} assertion(s) FAILED`);
  process.exit(1);
}
console.log('\nALL ASSERTIONS PASSED');
process.exit(0);
