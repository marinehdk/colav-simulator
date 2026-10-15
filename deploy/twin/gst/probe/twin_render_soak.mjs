// 长泡复测:用户形态 = head_on+potocnik_colreg_fan_mpc,attach→观看→拖到 overlook→暂停→静置 7min
// 用法: node m5_soak_mpc.mjs [algorithmId]
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const ALGO = process.argv[2] ?? 'potocnik_colreg_fan_mpc';
const CAM = process.argv[3] ?? 'overlook';
const PAUSE = process.argv[4] !== 'nopause';
const CDP_PORT = 9229;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const t0 = Date.now();
const stamp = () => `[${Math.round((Date.now() - t0) / 1000)}s]`;
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--disable-background-timer-throttling', '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
  '--no-first-run', `--user-data-dir=${join(tmpdir(), `m5-soak-${Date.now()}`)}`, '--window-size=1920,1080', 'about:blank',
], { stdio: 'ignore' });
process.on('exit', () => { try { chrome.kill('SIGKILL'); } catch {} });
await sleep(6000);
const tab = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent('http://127.0.0.1:8010/')}`, { method: 'PUT' })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0; const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const { resolve } = pending.get(m.id); pending.delete(m.id); resolve(m.error ? null : m.result); }
});
const send = (method, params = {}) => new Promise(resolve => {
  const i = ++id; pending.set(i, { resolve }); ws.send(JSON.stringify({ id: i, method, params }));
  setTimeout(() => { if (pending.has(i)) { pending.delete(i); resolve(null); } }, 25000);
});
const evaluate = async expression => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }))?.result?.value;
await send('Runtime.enable');
const current = await fetch('http://127.0.0.1:8010/api/sessions/current').then(r => (r.ok ? r.json() : null)).catch(() => null);
if (current?.session_id) await fetch(`http://127.0.0.1:8010/api/sessions/${current.session_id}/reset`, { method: 'POST' });
const created = await (await fetch('http://127.0.0.1:8010/api/sessions', {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: ALGO, tracker_id: 'god' }),
})).json();
const sid = created.session_id ?? created.id;
console.log(`${stamp()} session ${sid} algo=${ALGO}`);
await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/start`, { method: 'POST' });
await send('Page.reload'); await sleep(2500);
await evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
for (let i = 0; i < 40; i++) {
  if (await evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`)) break;
  await sleep(1500);
}
await evaluate(`(() => { document.getElementById('twinViewportBtn')?.click(); return true; })()`);
await sleep(15000);
const hudA = await evaluate(`document.getElementById('deploymentTwinHud')?.textContent`);
console.log(`${stamp()} attached, hud=${hudA}`);

// 相机拖到 overlook(高远视角,画面含海峡大部)后停手
await evaluate(`window.__deploymentTwin?.client?.sendCamera(CAM)`);
await sleep(20000);

if (PAUSE) {
  const pauseResp = await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/pause`, { method: 'POST' }).then(r => r.status).catch(e => `err ${e}`);
  console.log(`${stamp()} paused (http ${pauseResp})`);
} else console.log(`${stamp()} NOT pausing (control arm)`);
console.log(`${stamp()} soaking`);
for (let i = 0; i < 6; i++) {
  await sleep(30000);
  const hud = await evaluate(`document.getElementById('deploymentTwinHud')?.textContent`);
  const v = await evaluate(`(() => { const el = document.getElementById('deploymentTwinVideo'); return el?.dataset?.receivedFps ?? ''; })()`);
  console.log(`${stamp()} hud=${hud} browserFps=${v}`);
}
console.log(`${stamp()} done`);
try { await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/reset`, { method: 'POST' }); } catch {}
process.exit(0);
