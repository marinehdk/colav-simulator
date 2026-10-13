#!/usr/bin/env node
// M3 画面比对探针:无头 Chrome 打开 receiver.html,等首帧 decode 后截屏存 PNG。
// 用途:receiver.html 显示内容 与 a4000 Xvfb x11grab 抓屏 的可视化比对(DESIGN M3 验收 1)。
// 用法:node spike_shot.mjs [--out /tmp/m3-receiver.png] [--signaling ws://127.0.0.1:8081]
//       [--url http://127.0.0.1:8090/receiver.html] [--wait-s 4]
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { writeFileSync } from 'node:fs';

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > 0 ? process.argv[i + 1] : d;
};
const URL0 = arg('url', 'http://127.0.0.1:8090/receiver.html');
const SIGNALING = arg('signaling', 'ws://127.0.0.1:8081');
const OUT = arg('out', '/tmp/m3-receiver.png');
const WAIT_S = parseInt(arg('wait-s', '4'), 10);
const CDP_PORT = 9226;
const URL = SIGNALING ? `${URL0}?signaling=${encodeURIComponent(SIGNALING)}` : URL0;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', `--user-data-dir=${join(tmpdir(), `spike-shot-${Date.now()}`)}`,
  '--window-size=2560,1440', '--mute-audio', 'about:blank',
], { stdio: 'ignore' });
process.on('exit', () => { try { chrome.kill(); } catch {} });
// CDP 端口就绪重试(实测:宿主 Chrome 繁忙时 headless 启动可超 2.5s,ECONNREFUSED)
const tab = await (await (async () => {
  for (let i = 0; i < 20; i++) {
    try { return await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent(URL)}`, { method: 'PUT' })).json(); }
    catch { await sleep(1000); }
  }
  throw new Error('CDP /json/new failed after 20 retries');
})());
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
const evaluate = async expression => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.value;

await send('Runtime.enable');
const deadline = Date.now() + 90000;
let s = null;
while (Date.now() < deadline) {
  s = await evaluate(`window.__spike ? { phase: window.__spike.phase, first: window.__spike.firstFrameAt != null,
    size: window.__spike.videoSize, dec: window.__spike.samples.slice(-1)[0]?.framesDecoded ?? null,
    fps: window.__spike.samples.slice(-1)[0]?.fps ?? null } : null`);
  if (s?.first) break;
  await sleep(1000);
}
console.log(`firstFrame snapshot: ${JSON.stringify(s)}`);
if (!s?.first) { console.error('FATAL: no decoded frame within 90s'); process.exit(1); }
await sleep(WAIT_S * 1000); // 多采几帧,避开首帧 IDR
const shot = await send('Page.captureScreenshot', { format: 'png' });
writeFileSync(OUT, Buffer.from(shot.data, 'base64'));
const fin = await evaluate(`window.__spike ? { phase: window.__spike.phase, size: window.__spike.videoSize,
  dec: window.__spike.samples.slice(-1)[0]?.framesDecoded, fps: window.__spike.samples.slice(-1)[0]?.fps,
  w: window.__spike.samples.slice(-1)[0]?.width, h: window.__spike.samples.slice(-1)[0]?.height } : null`);
console.log(`final: ${JSON.stringify(fin)}`);
console.log(`PNG -> ${OUT}`);
