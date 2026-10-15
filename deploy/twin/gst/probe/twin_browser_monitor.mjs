#!/usr/bin/env node
// twin_browser_monitor — CDP attach 式采样用户真实 Chrome(调试端口)里的 DT 视口。
// 与 twin_stream_stats.mjs(自建 headless)互补:本脚本不建会话、不点按钮、不 reload,
// 只旁路 1Hz 读数,复现"用户手动操作"时间线(暂停/切视角/关页)与三层 fps 的对齐。
// 用法: node twin_browser_monitor.mjs [--port 9222] [--out /tmp/dt-monitor/samples.jsonl]
// 采样面:W3C 帧质量增量(解码 fps/丢帧)+ 产品 HUD dataset(码率/抖动/RTT/freeze)+
//         facade/桥状态 + 主线程 rAF fps + visibility + 8010 会话态(HTTP,暂停事件入轨)。
import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';

const argOf = k => { const i = process.argv.indexOf(`--${k}`); return i < 0 ? undefined : process.argv[i + 1]; };
const PORT = Number(argOf('port') ?? 9222);
const OUT = argOf('out') ?? '/tmp/dt-monitor/samples.jsonl';
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT.slice(0, OUT.lastIndexOf('/')), { recursive: true });

const wall = () => new Date().toTimeString().slice(0, 8);
let ws = null, wsTarget = null, msgId = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((resolve, reject) => {
  if (!ws || ws.readyState !== 1) return reject(new Error('ws closed'));
  const i = ++msgId; pending.set(i, { resolve, reject });
  ws.send(JSON.stringify({ id: i, method, params }));
  setTimeout(() => { if (pending.has(i)) { pending.delete(i); reject(new Error('timeout ' + method)); } }, 15000);
});

// macOS 新版 Chrome DevTools 可能只绑 [::1](IPv4 bind 失败回退),启动时探测一次定 host
const HOSTS = ['[::1]', '127.0.0.1'];
let cdpBase = null;
const resolveBase = async () => {
  if (cdpBase) return cdpBase;
  for (const h of HOSTS) {
    try { await fetch(`http://${h}:${PORT}/json/version`, { signal: AbortSignal.timeout(1000) }); cdpBase = `http://${h}:${PORT}`; return cdpBase; } catch {}
  }
  return null;
};

const findTab = async () => {
  try {
    const base = await resolveBase();
    if (!base) return null;
    const tabs = await fetch(`${base}/json`, { signal: AbortSignal.timeout(1500) }).then(r => r.json());
    return tabs.find(t => t.type === 'page' && /(?:localhost|127\.0\.0\.1):8010/.test(t.url)) ?? null;
  } catch { return null; }
};

const connect = async tab => {
  ws = new WebSocket(tab.webSocketDebuggerUrl); wsTarget = tab.id;
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; setTimeout(() => rej(new Error('ws open timeout')), 5000); });
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { const { resolve, reject } = pending.get(m.id); pending.delete(m.id); m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result); }
  });
  ws.addEventListener('close', () => { ws = null; });
  await send('Runtime.enable');
};

// 幂等注入 rAF 探针(主线程健康度);读数与注入同表达式,刷新后自动重装。
// getStats 深挖:framesReceived/decoded/presented 三本账 + packetsLost/PLI/NACK,
// 深跌秒一次读数即可钉死丢失层(输入 / 解码排队 / 合成呈现)。
const collectExpr = `(async () => {
  if (!window.__dtMon) { window.__dtMon = { raf: 0 };
    const loop = () => { window.__dtMon.raf++; requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }
  const d = window.__deploymentTwin, v = document.getElementById('deploymentTwinVideo');
  const ds = (v && v.dataset) || {};
  const q = v && v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : null;
  const c = d && d.client, ls = c && c.lastState || null;
  const num = x => (x != null && x !== '' ? Number(x) : null);
  let rtp = null;
  try {
    const rx = window.__twinVideoReceiver;
    if (rx && rx.getStats) {
      const stats = await rx.getStats();
      stats.forEach(rep => {
        if (rep.type === 'inbound-rtp' && (rep.kind === 'video' || rep.mediaType === 'video')) rtp = {
          recv: rep.framesReceived ?? null, dec: rep.framesDecoded ?? null,
          dr: rep.framesDropped ?? null, fps: rep.framesPerSecond ?? null,
          lost: rep.packetsLost ?? null, pli: rep.pliCount ?? null, nack: rep.nackCount ?? null,
          jbDelayMs: rep.jitterBufferDelay != null && rep.jitterBufferEmittedCount
            ? Math.round(rep.jitterBufferDelay / rep.jitterBufferEmittedCount * 1000) : null,
          keyDec: rep.keyFramesDecoded ?? null,
        };
      });
    } else rtp = { err: 'no receiver exposed' };
  } catch (e) { rtp = { err: String(e).slice(0, 60) }; }
  return { ts: Date.now(), vis: document.visibilityState, raf: window.__dtMon.raf, rtp,
    video: v ? { ready: v.readyState, w: v.videoWidth, h: v.videoHeight, t: v.currentTime,
      total: q ? q.totalVideoFrames : null, dropped: q ? q.droppedVideoFrames : null,
      fps: num(ds.receivedFps), bitrate: num(ds.bitrateMbps), dropRatio: num(ds.dropRatio),
      jitterMs: num(ds.jitterMs), jitterBufMs: num(ds.jitterBufferMs), rttMs: num(ds.rttMs),
      decodeMs: num(ds.decodeMs), freezes: num(ds.freezeCount) } : null,
    hud: document.getElementById('deploymentTwinHud')?.textContent ?? null,
    facade: d ? { conn: d.connectionState, simTime: d.simTime,
      helloed: c ? c.helloed : null, ready: c ? c.ready : null,
      attachedRun: c && c.attached ? c.attached.run_id : null,
      stream: ls ? ls.stream?.state ?? null : null, sent: c ? c.sent : null, received: c ? c.received : null } : null };
})()`;

const sessLine = async () => {
  try {
    const s = await fetch('http://127.0.0.1:8010/api/sessions/current', { signal: AbortSignal.timeout(1500) }).then(r => r.json());
    return { id: s.session_id, state: s.state, algo: s.spec?.algorithm_id, scenario: s.spec?.scenario_id };
  } catch { return null; }
};

let prev = null, n = 0;
const line = o => { appendFileSync(OUT, JSON.stringify(o) + '\n'); };
console.log(`[${wall()}] monitor → ${OUT} (attach :${PORT}, waiting 8010 tab)`);
while (true) {
  const tab = await findTab();
  if (ws && ws.readyState === 1 && (!tab || wsTarget !== tab.id)) {
    try { ws.close(); } catch {} ws = null;
  }
  if (!tab) { await sleep(2000); continue; }
  try {
    if (!ws || ws.readyState !== 1) { await connect(tab); console.log(`[${wall()}] attached to tab ${tab.id.slice(0, 8)} (${tab.url.slice(0, 60)})`); prev = null; }
    const r = await send('Runtime.evaluate', { expression: collectExpr, returnByValue: true, awaitPromise: true });
    const s = r?.result?.value;
    if (!s) { await sleep(1000); continue; }
    const sess = await sessLine();
    const now = Date.now();
    const row = { wall: wall(), ...s, sess };
    if (prev && prev.ts != null) {
      const dt = (now - prev.ts) / 1000;
      const dd = (a, b) => (a != null && b != null ? (a - b) / dt : null);
      row.delta = { decodeFps: dd(s.video?.total, prev.video?.total), dropFps: dd(s.video?.dropped, prev.video?.dropped),
        rafFps: dd(s.raf, prev.raf), videoT: dd(s.video?.t, prev.video?.t), dt,
        recvFps: dd(s.rtp?.recv, prev.rtp?.recv), rtpDecFps: dd(s.rtp?.dec, prev.rtp?.dec),
        lostΔ: s.rtp?.lost != null && prev.rtp?.lost != null ? s.rtp.lost - prev.rtp.lost : null,
        pliΔ: s.rtp?.pli != null && prev.rtp?.pli != null ? s.rtp.pli - prev.rtp.pli : null,
        nackΔ: s.rtp?.nack != null && prev.rtp?.nack != null ? s.rtp.nack - prev.rtp.nack : null };
    }
    prev = { ts: now, video: s.video, raf: s.raf, rtp: s.rtp };
    line(row); n++;
    const dv = row.delta ?? {};
    console.log(`[${row.wall}] dec=${(dv.decodeFps ?? 0).toFixed(1)}/s rtpRecv=${(dv.recvFps ?? 0).toFixed(1)}/s rtpDec=${(dv.rtpDecFps ?? 0).toFixed(1)}/s` +
      ` lostΔ=${dv.lostΔ ?? '-'} pliΔ=${dv.pliΔ ?? '-'} nackΔ=${dv.nackΔ ?? '-'}` +
      ` raf=${(dv.rafFps ?? 0).toFixed(0)}/s hud=${s.video?.fps ?? '-'} vis=${s.vis}` +
      ` sess=${sess ? sess.state : '-'} fz=${s.video?.freezes ?? '-'}`);
  } catch (e) {
    if (ws) { try { ws.close(); } catch {} ws = null; prev = null; }
    console.log(`[${wall()}] reconnecting (${String(e.message).slice(0, 60)})`);
    await sleep(1500);
  }
  await sleep(1000);
}
