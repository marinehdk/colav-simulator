#!/usr/bin/env node
// twin_stream_stats — 真实 DT 视口(web_gui :8010)视频流采样 + 桥链路核验(M4 固化自 /tmp)。
// 用法: node twin_stream_stats.mjs [--seconds N] [--window W,H]
//   A3 回退演练: --seconds 190 --window 1920,1080(1080p 档视口)
// 纪律(handoff/DESIGN §5.3):自建会话后必须 Page.reload 页面才 adopt;结束必 reset。
// 采样口径 = 产品采样器 window.__deploymentTwin.videoStats(W3C 对齐,1s 窗 fps/dropRatio);
// 桥链路 = client.helloed/ready/attached + lastState._receivedAt(~1Hz)+ #twinStatusLine(TWIN LIVE)。
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CDP_PORT = 9226;
const argOf = k => {
  const i = process.argv.indexOf(`--${k}`);
  if (i < 0) return undefined;
  const v = process.argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
};
const DUR_S = Number(typeof argOf('seconds') === 'string' ? argOf('seconds') : 60);
// 视口尺寸决定产品初始档(deployment-twin.js chooseTwinStreamProfile):2560x1440→1440p,
// 1920x1080→1080p。A3「1080p 基线回归」用 1080p 视口,避免 1440p 启动周期混入窗口。
const WIN = typeof argOf('window') === 'string' ? argOf('window') : '2560,1440';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', `--user-data-dir=${join(tmpdir(), `twin-stats-${Date.now()}`)}`,
  `--window-size=${WIN}`, 'about:blank',
], { stdio: 'ignore' });
process.on('exit', () => { try { chrome.kill(); } catch {} });
await sleep(2500);

const tab = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent('http://127.0.0.1:8010/')}`, { method: 'PUT' })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0; const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const { resolve, reject } = pending.get(m.id); pending.delete(m.id); m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result); }
});
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const i = ++id; pending.set(i, { resolve, reject });
  ws.send(JSON.stringify({ id: i, method, params }));
  setTimeout(() => { if (pending.has(i)) { pending.delete(i); reject(new Error('timeout')); } }, 30000);
});
const cdp_reload = () => send('Page.reload').then(() => sleep(2500));
const evaluate = async expression => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.value;

await send('Runtime.enable');
// 自建 head_on 会话(结束清场)
const current = await fetch('http://127.0.0.1:8010/api/sessions/current').then(r => (r.ok ? r.json() : null)).catch(() => null);
if (current?.session_id) await fetch(`http://127.0.0.1:8010/api/sessions/${current.session_id}/reset`, { method: 'POST' });
const created = await (await fetch('http://127.0.0.1:8010/api/sessions', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'god' }),
})).json();
globalThis.sessionId = created.session_id ?? created.id;
await fetch(`http://127.0.0.1:8010/api/sessions/${globalThis.sessionId}/start`, { method: 'POST' });
await cdp_reload();
await evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
for (let i = 0; i < 40; i++) {
  const ok = await evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`);
  if (ok) break;
  await sleep(1500);
}
await evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); if (b && !b.disabled) b.click(); return true; })()`);
await sleep(10000); // 等 SDP/视频/attach

const collect = () => evaluate(`(() => {
  const d = window.__deploymentTwin;
  const v = document.getElementById('deploymentTwinVideo');
  if (!d) return null;
  const c = d.client, ls = c?.lastState ?? null;
  return { videoStats: d.videoStats, connection: d.connectionState,
    sim: d.simTime, videoReady: v ? v.readyState : null,
    videoSize: v && v.videoWidth ? v.videoWidth + 'x' + v.videoHeight : null,
    bridge: { statusLine: document.getElementById('twinStatusLine')?.textContent ?? null,
      // deployment 工作面活 HUD 是 #deploymentTwinHud(renderHud 每 tick 写
      // "SIGNAL · WxH · FPS · Mb/s");#twinStatusLine 在此工作面不被更新(静态初始文本)
      hud: document.getElementById('deploymentTwinHud')?.textContent ?? null,
      helloed: c?.helloed ?? null, ready: c?.ready ?? null,
      attached: c?.attached ? { run_id: c.attached.run_id, mode: c.attached.mode } : null,
      stateReceivedAt: ls?._receivedAt ?? null, stateSimTime: ls?.sim_time ?? null,
      stateStream: ls?.stream?.state ?? null, sent: c?.sent ?? null, received: c?.received ?? null } };
})()`);

const first = await collect();
if (!first || !first.videoStats) { console.log('no videoStats yet (is twin viewport on?):', JSON.stringify(first)); process.exit(1); }
console.log('first:', JSON.stringify(first));
let freezes = first.videoStats.freezeCount ?? 0;
const samples = [];
const bridges = [];
const t0 = Date.now();
while ((Date.now() - t0) / 1000 < DUR_S) {
  await sleep(3000);
  const s = await collect();
  if (s?.videoStats) { samples.push(s.videoStats); bridges.push(s.bridge); }
  console.log('tick:', JSON.stringify(s));
}
const last = await collect();
console.log('last:', JSON.stringify(last));
const v = last?.videoStats;
if (v) {
  const f = samples.map(x => x.fps);
  const ge29 = f.filter(x => x >= 29).length;
  const dec0 = first.videoStats.framesDecoded ?? null, dec1 = v.framesDecoded ?? null;
  const drop0 = first.videoStats.framesDropped ?? 0, drop1 = v.framesDropped ?? 0;
  const aggDrop = dec0 != null && dec1 != null && dec1 + drop1 - dec0 - drop0 > 0
    ? (drop1 - drop0) / (dec1 - dec0 + drop1 - drop0) : null;
  console.log(`\n=== summary: window ${DUR_S}s samples=${samples.length} fpsGe29=${ge29}/${samples.length} (${(100 * ge29 / samples.length).toFixed(1)}%)`);
  console.log(`=== fps min ${(Math.min(...f)).toFixed(2)} p05 ${f.slice().sort((a, b) => a - b)[Math.floor(f.length * 0.05)]?.toFixed(2)} dropRatioTickMax ${Math.max(...samples.map(x => x.dropRatio ?? 0)).toFixed(3)} dropRatioAggregate ${aggDrop == null ? 'n/a' : aggDrop.toFixed(4)} freeze Δ${(v.freezeCount ?? 0) - freezes}`);
  console.log(`=== jitterMs ${samples.map(x => x.jitterMs).join(',')} jitterBufMs ${samples.map(x => x.jitterBufferMs?.toFixed(1)).join(',')} rtt ${samples.map(x => x.rttMs?.toFixed(0)).join(',')}`);
  console.log(`=== bitrateMbps ${samples.map(x => x.bitrateMbps?.toFixed(1)).join(',')} codec ${v.codec} size ${v.width}x${v.height}`);
  // 桥链路(A3):hello→ready→attach + state 心跳 + HUD
  const b0 = bridges[0], b1 = bridges[bridges.length - 1];
  const stateAdvanceMs = b0?.stateReceivedAt && b1?.stateReceivedAt ? b1.stateReceivedAt - b0.stateReceivedAt : null;
  console.log(`=== bridge: helloed=${b0?.helloed} ready=${b0?.ready} attached=${JSON.stringify(b0?.attached)} stateStream=${b1?.stateStream} stateReceivedAtΔ=${stateAdvanceMs == null ? 'n/a' : stateAdvanceMs.toFixed(0) + 'ms/' + ((bridges.length - 1) * 3) + 's'} receivedΔ=${(b1?.received ?? 0) - (b0?.received ?? 0)} simTimeΔ=${((b1?.stateSimTime ?? 0) - (b0?.stateSimTime ?? 0)).toFixed(1)}`);
  console.log(`=== statusLine(first)=${b0?.statusLine} hud(first)=${b0?.hud} hud(last)=${b1?.hud}`);
}
// cleanup
try { await fetch(`http://127.0.0.1:8010/api/sessions/${globalThis.sessionId}/reset`, { method: 'POST' }); console.log('session reset (cleanup)'); } catch {}
process.exit(0); // WS 连接会吊住事件循环(/tmp 原版遗留坑,固化版修)
