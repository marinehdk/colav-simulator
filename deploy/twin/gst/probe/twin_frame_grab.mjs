#!/usr/bin/env node
// twin_frame_grab — 运动工况下抓取 DT 视口实际呈现帧(CDP 截屏),供像素级伪影分析。
// 用法: node twin_frame_grab.mjs --seconds 40 --out /tmp/dt-monitor/frames
//   前提:CDP Chrome 已打开 8010 且 DT 视口出流(配合 twin_eye_probe 或用户手动)
import { mkdirSync, writeFileSync } from 'node:fs';

const argOf = k => { const i = process.argv.indexOf(`--${k}`); return i < 0 ? undefined : process.argv[i + 1]; };
const SECONDS = Number(argOf('seconds') ?? 40);
const OUT = argOf('out') ?? '/tmp/dt-monitor/frames';
mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

const HOSTS = ['127.0.0.1', '[::1]'];
let base = null;
for (const h of HOSTS) { try { await fetch(`http://${h}:9222/json/version`, { signal: AbortSignal.timeout(1000) }); base = `http://${h}:9222`; break; } catch {} }
if (!base) { console.error('CDP 9222 不可达'); process.exit(1); }
const tabs = await fetch(`${base}/json`).then(r => r.json());
const tab = tabs.find(t => t.type === 'page' && /:8010/.test(t.url));
if (!tab) { console.error('无 8010 tab'); process.exit(1); }
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0; const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const { resolve } = pending.get(m.id); pending.delete(m.id); resolve(m.error ? null : m.result); }
});
const send = (method, params = {}) => new Promise(resolve => {
  const i = ++id; pending.set(i, { resolve }); ws.send(JSON.stringify({ id: i, method, params }));
  setTimeout(() => { if (pending.has(i)) { pending.delete(i); resolve(null); } }, 20000);
});
const evaluate = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true }))?.result?.value;
await send('Runtime.enable');
await send('Page.enable');

const up = await evaluate(`(() => { const v = document.getElementById('deploymentTwinVideo'); return !!(v && v.videoWidth && v.readyState >= 2); })()`);
if (!up) { console.error('DT 视口未出流'); process.exit(1); }
const rect = await evaluate(`(() => { const v = document.getElementById('deploymentTwinVideo'); const r = v.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; })()`);
console.log(`video rect=${JSON.stringify(rect)} — grabbing ${SECONDS}s`);
const t0 = Date.now();
let n = 0;
while (Date.now() - t0 < SECONDS * 1000) {
  const r = await send('Page.captureScreenshot', { format: 'png', clip: { x: rect.x, y: rect.y, width: rect.w, height: rect.h, scale: 1 } });
  if (r && r.data) {
    writeFileSync(`${OUT}/f${String(n).padStart(4, '0')}_${Date.now() - t0}.png`, Buffer.from(r.data, 'base64'));
    n++;
  }
  await sleep(60);
}
console.log(`saved ${n} frames → ${OUT}`);
process.exit(0);
