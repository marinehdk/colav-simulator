#!/usr/bin/env node
// M2 spike CDP 驱动:无头 Chrome 打开 receiver.html,按验收点采集。
// 用法:node spike_cdp.mjs --phase main|suppress [--sample-seconds 190] [--url http://127.0.0.1:8090/receiver.html]
//   main:    两轮协商验证 + twin-bridge echo + ≥3min 同口径采样 + Page.reload PLI 恢复计时
//   suppress:重复 offer 容错(需 sender 以 --suppress-answer-ms 6000 启动)
// 输出:stdout 摘要 + JSON 全量(--out 路径,默认 /tmp/spike-cdp-<phase>.json)
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { writeFileSync } from 'node:fs';

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > 0 ? process.argv[i + 1] : d;
};
const PHASE = arg('phase', 'main');
const SAMPLE_S = parseInt(arg('sample-seconds', PHASE === 'main' ? 190 : 40), 10);
const URL = arg('url', 'http://127.0.0.1:8090/receiver.html');
const CDP_PORT = 9226;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', `--remote-debugging-port=${CDP_PORT}`, '--autoplay-policy=no-user-gesture-required',
  '--no-first-run', `--user-data-dir=${join(tmpdir(), `spike-cdp-${Date.now()}`)}`,
  '--window-size=2560,1440', '--mute-audio', 'about:blank',
], { stdio: 'ignore' });
process.on('exit', () => { try { chrome.kill(); } catch {} });
await sleep(2500);

const tab = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent(URL)}`, { method: 'PUT' })).json();
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
const snapshot = () => evaluate(`(() => { const s = window.__spike; if (!s) return null;
  return { phase: s.phase, connectionId: s.connectionId, offersSent: s.offersSent.length, offersReceived: s.offersReceived,
    answersSent: s.answersSent, answersReceived: s.answersReceived, candidatesSent: s.candidatesSent,
    candidatesReceived: s.candidatesReceived, offerTimes: s.offerTimes.slice(), trackAdded: s.trackAdded,
    channelOpen: s.channelOpen, echoRtts: s.echoRtts.slice(), firstFrameAt: s.firstFrameAt,
    videoSize: s.videoSize, nSamples: s.samples.length, lastSample: s.samples[s.samples.length-1] || null,
    errors: s.errors.slice(0,5), startedAt: s.startedAt, netPath: s.netPath || null }; })()`);
const samples = () => evaluate(`window.__spike ? window.__spike.samples.slice() : []`);

await send('Runtime.enable');
const result = { phase: PHASE, url: URL, startedAt: new Date().toISOString(), events: [] };
const note = (k, v) => { result.events.push({ t: Date.now(), k, v }); console.log(`[${new Date().toISOString().slice(11, 23)}] ${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`); };

// 1) 等两轮协商完成(首帧 decode)
let s = null;
const deadline = Date.now() + 90000;
while (Date.now() < deadline) {
  s = await snapshot();
  if (s?.firstFrameAt != null) break;
  await sleep(1000);
}
note('negotiation-snapshot', s);
if (!s || s.firstFrameAt == null) {
  console.error('FATAL: no decoded frame within 90s');
  writeFileSync(arg('out', `/tmp/spike-cdp-${PHASE}.json`), JSON.stringify(result, null, 2));
  process.exit(1);
}
const firstFrameT = s.firstFrameAt; // 本页会话首帧 decode 时刻(performance.now 域)

// 2) suppress 相位:offer 重发时间线(500ms 粒度,前 15s)
if (PHASE === 'suppress') {
  const t0 = Date.now();
  const tl = [];
  let last = 0;
  while (Date.now() - t0 < 15000) {
    const cur = (await snapshot()) || { offersSent: 0 };
    if (cur.offersSent !== last) { tl.push({ tMs: Date.now() - t0, offersSent: cur.offersSent, phase: cur.phase }); last = cur.offersSent; }
    if (cur.phase === 'streaming') break;
    await sleep(500);
  }
  result.offerTimeline = tl;
  note('offer-timeline', tl);
}

// 3) 采样窗口
const sampleStart = Date.now();
let lastN = 0;
while ((Date.now() - sampleStart) / 1000 < SAMPLE_S) {
  await sleep(5000);
  const all = await samples();
  const fresh = all.slice(lastN); lastN = all.length;
  const last = fresh[fresh.length - 1] || (await snapshot())?.lastSample;
  console.log(`tick +${Math.round((Date.now() - sampleStart) / 1000)}s n=${all.length} fps=${last?.fps?.toFixed(1)} drop=${last?.dropRatio?.toFixed(3)} bitrate=${last?.bitrateMbps?.toFixed(1)} size=${last?.width}x${last?.height}`);
}
const all = await samples();
const win = all.filter(x => x.t >= firstFrameT); // 口径窗口:首帧 decode 起的 1s 样本(启动 ramp 前 0-1s 不计入)
result.samples = win;
const valid = win.filter(x => x.fps != null);
const ge29 = valid.filter(x => x.fps >= 29).length;
const totDec = win.length ? (win[win.length - 1].framesDecoded - win.find(x => x.framesDecoded != null).framesDecoded) : 0;
const totDrop = win.length ? ((win[win.length - 1].framesDropped ?? 0) - (win.find(x => x.framesDropped != null)?.framesDropped ?? 0)) : 0;
const fpsVals = valid.map(x => x.fps);
result.summary = {
  nValid: valid.length, nSamples: all.length, windowS: Math.round((Date.now() - sampleStart) / 1000),
  fpsGe29Frac: valid.length ? ge29 / valid.length : null,
  fpsMin: fpsVals.length ? Math.min(...fpsVals) : null,
  fpsP05: fpsVals.length ? fpsVals.slice().sort((a, b) => a - b)[Math.floor(fpsVals.length * 0.05)] : null,
  dropRatioAggregate: totDec + totDrop > 0 ? totDrop / (totDec + totDrop) : null,
  freezeCountLast: all.length ? all[all.length - 1].freezeCount : null,
  videoSize: s.videoSize, codec: all.find(x => x.codec)?.codec ?? null,
  echoRtts: (await snapshot()).echoRtts,
};
note('sampling-summary', result.summary);

// 4) PLI→force-keyunit:Page.reload 后恢复计时(main 相位)
if (PHASE === 'main') {
  await sleep(3000);
  const preReload = await snapshot();
  note('pre-reload', { framesDecoded: preReload.lastSample?.framesDecoded });
  const reloadT0 = Date.now();
  await send('Page.reload');
  let fresh = null;
  while (Date.now() - reloadT0 < 30000) {
    await sleep(200);
    fresh = await snapshot();
    if (fresh?.firstFrameAt != null) break;
  }
  const recoverMs = fresh?.firstFrameAt != null ? Date.now() - reloadT0 : null;
  result.reloadTest = { reloadAt: reloadT0, recoveredAt: recoverMs != null ? Date.now() : null, recoverMs, snapshot: fresh };
  note('reload-recovery', { recoverMs, phase: fresh?.phase, offers: fresh?.offersSent, answers: fresh?.answersReceived });
}

// 4b) PLI→force-keyunit 直证(pli 相位):srcObject 重挂触发 Chrome 解码器重起→PLI;
//     FKU/IDR 证据在 sender 日志(monotonic 时间戳,事后对齐)。
if (PHASE === 'pli') {
  await sleep(3000);
  const before = await snapshot();
  note('pre-detach', { framesDecoded: before.lastSample?.framesDecoded, tWall: Date.now() });
  const detachT0 = Date.now();
  await evaluate(`(() => { const v = document.getElementById('spikeVideo'); const ms = v.srcObject; v.srcObject = null; setTimeout(() => { v.srcObject = ms; v.play?.().catch(()=>{}); }, 800); return true; })()`);
  // 观察 8s 内 framesDecoded 是否继续增长(恢复)并记录时刻
  const marks = [];
  let lastDec = before.lastSample?.framesDecoded ?? 0;
  for (let i = 0; i < 16; i++) {
    await sleep(500);
    const s = await snapshot();
    const dec = s?.lastSample?.framesDecoded ?? lastDec;
    if (dec > lastDec) { marks.push({ tMs: Date.now() - detachT0, framesDecoded: dec }); lastDec = dec; }
  }
  result.pliTest = { detachAt: detachT0, decodeProgressMarks: marks, finalDecoded: lastDec };
  note('pli-reattach', { finalDecoded: lastDec, marks: marks.slice(-3) });
}

// 5) 终态
result.final = await snapshot();
note('final', { phase: result.final?.phase, samples: result.final?.nSamples, errors: result.final?.errors });
const outPath = arg('out', `/tmp/spike-cdp-${PHASE}.json`);
writeFileSync(outPath, JSON.stringify(result, null, 2));
console.log(`\nJSON -> ${outPath}`);
console.log(`RESULT phase=${PHASE} ok=${result.final?.phase === 'streaming'}`);
