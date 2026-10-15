#!/usr/bin/env node
// twin_eye_attach — 旁路采集用户手动操作的 DT 视口(不建会话/不点按钮/不 reload)。
// 等待 DT 视口出流后幂等注入 rVFC 逐呈现帧探针,持续追加落盘,每 10s 打一行滚动摘要。
// 用法: node twin_eye_attach.mjs [--tag user1] [--max-min 30]
import { appendFileSync, writeFileSync } from 'node:fs';

const argOf = k => { const i = process.argv.indexOf(`--${k}`); return i < 0 ? undefined : process.argv[i + 1]; };
const TAG = argOf('tag') ?? 'user';
const MAX_MIN = Number(argOf('max-min') ?? 30);
const PORT = 9222;
const OUT = `/tmp/dt-monitor/eye-${TAG}.jsonl`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const t0 = Date.now();
const stamp = () => `[${Math.round((Date.now() - t0) / 1000)}s]`;
writeFileSync(OUT, '');

const HOSTS = ['127.0.0.1', '[::1]'];
let base = null;
const resolveBase = async () => {
  for (const h of HOSTS) {
    try { await fetch(`http://${h}:${PORT}/json/version`, { signal: AbortSignal.timeout(1000) }); return `http://${h}:${PORT}`; } catch {}
  }
  return null;
};

let ws = null, wsTarget = null, id = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise(resolve => {
  if (!ws || ws.readyState !== 1) return resolve(null);
  const i = ++id; pending.set(i, { resolve }); ws.send(JSON.stringify({ id: i, method, params }));
  setTimeout(() => { if (pending.has(i)) { pending.delete(i); resolve(null); } }, 20000);
});
const evaluate = async expression => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }))?.result?.value;

const INJECT = `(() => {
  if (window.__eye && document.getElementById('deploymentTwinVideo')) return 'ok';
  window.__eye = { log: [], n0: 0 };
  const state = window.__eye;
  const cv = document.createElement('canvas'); cv.width = 160; cv.height = 90;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  let prev = null;
  const onFrame = (now, meta) => {
    try {
      const vid = document.getElementById('deploymentTwinVideo');
      if (vid && vid.videoWidth && vid.readyState >= 2) {
        cx.drawImage(vid, 0, 0, 160, 90);
        const d = cx.getImageData(0, 0, 160, 90).data;
        let md = -1, fc = -1;
        if (prev) {
          let s = 0, cnt = 0;
          for (let i = 0; i < d.length; i += 8) {
            let df = d[i] - prev[i]; if (df < 0) df = -df;
            if (df > 2) cnt++;
            s += df;
          }
          md = s / (d.length / 8); fc = cnt / (d.length / 8);
        }
        state.log.push({ k: 'f', t: Math.round(now * 10) / 10, mt: +meta.mediaTime.toFixed(4),
          pt: Math.round(meta.presentationTime * 10) / 10, pf: meta.presentedFrames,
          md: Math.round(md * 1000) / 1000, fc: Math.round(fc * 10000) / 10000 });
        prev = d;
        if (state.log.length > 60000) state.log.splice(0, 20000);
        vid.requestVideoFrameCallback(onFrame);
      } else {
        prev = null;
        setTimeout(() => { const v2 = document.getElementById('deploymentTwinVideo'); v2 && v2.requestVideoFrameCallback(onFrame); }, 500);
      }
    } catch (e) {}
  };
  const v0 = document.getElementById('deploymentTwinVideo');
  v0 && v0.requestVideoFrameCallback(onFrame);
  return v0 ? 'ok' : 'no-video-yet';
})()`;

const COLLECT = `(async () => {
  if (!window.__eye) return null;
  const st = window.__eye;
  const rows = st.log.slice(st.n0); st.n0 = st.log.length;
  const v = document.getElementById('deploymentTwinVideo');
  const ds = (v && v.dataset) || {};
  let rtp = null;
  try {
    const rx = window.__twinVideoReceiver;
    if (rx && rx.getStats) {
      const s = await rx.getStats();
      s.forEach(rep => { if (rep.type === 'inbound-rtp' && (rep.kind === 'video' || rep.mediaType === 'video')) rtp = {
        lost: rep.packetsLost ?? null, pli: rep.pliCount ?? null, nack: rep.nackCount ?? null,
        jb: rep.jitterBufferDelay != null && rep.jitterBufferEmittedCount ? Math.round(rep.jitterBufferDelay / rep.jitterBufferEmittedCount * 1000) : null }; });
    }
  } catch (e) {}
  return { rows, hud: ds.receivedFps ?? null, cam: ds.camera ?? null, rtp };
})()`;

let carried = null, total = 0;
let stats = { n: 0, dup: 0, skip: 0, big: 0, base: 0, t: 0 };
console.log(`${stamp()} attach 采集 → ${OUT}(等待你打开 DT 视口,最长 ${MAX_MIN}min)`);
const deadline = Date.now() + MAX_MIN * 60000;
while (Date.now() < deadline) {
  const b = base ?? (base = await resolveBase());
  if (!b) { await sleep(2000); continue; }
  try {
    const tabs = await fetch(`${b}/json`, { signal: AbortSignal.timeout(1500) }).then(r => r.json());
    const tab = tabs.find(t => t.type === 'page' && /:8010/.test(t.url));
    if (!tab) { await sleep(2000); continue; }
    if (ws && ws.readyState === 1 && wsTarget !== tab.id) { try { ws.close(); } catch {} ws = null; }
    if (!ws || ws.readyState !== 1) {
      ws = new WebSocket(tab.webSocketDebuggerUrl); wsTarget = tab.id;
      await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; setTimeout(rej, 4000); }).catch(() => { ws = null; });
      if (ws) { ws.addEventListener('message', ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const { resolve } = pending.get(m.id); pending.delete(m.id); resolve(m.error ? null : m.result); } }); await send('Runtime.enable'); }
    }
    const videoUp = await evaluate(`(() => { const v = document.getElementById('deploymentTwinVideo'); return !!(v && v.videoWidth && v.readyState >= 2); })()`);
    if (!videoUp) { await sleep(1500); continue; }
    await evaluate(INJECT);
    const r = await evaluate(COLLECT);
    if (r && r.rows && r.rows.length) {
      appendFileSync(OUT, r.rows.map(x => JSON.stringify(x)).join('\n') + '\n');
      carried = carried || { cam: r.cam };
      total += r.rows.length;
      for (const f of r.rows) {
        if (f.k !== 'f' || f.md < 0) continue;
        if (f.md > 0.02) stats.base = stats.base ? stats.base * 0.98 + f.md * 0.02 : f.md;
        stats.n++;
        if (stats.base > 0.02) {
          if (f.md < 0.15 * stats.base) stats.dup++;
          else if (f.md > 1.8 * stats.base) stats.skip++;
          if (f.md > 2.5 * stats.base) stats.big++;
        }
        stats.t = f.t;
      }
    }
    if (stats.n > 200 && (stats.n % 300) < 60) {
      console.log(`${stamp()} frames=${stats.n} dup=${stats.dup}(${(100 * stats.dup / stats.n).toFixed(1)}%) ` +
        `skip=${stats.skip}(${(100 * stats.skip / stats.n).toFixed(1)}%) 巨跳=${stats.big} base=${stats.base?.toFixed(2)} ` +
        `hud=${r?.hud ?? '-'} cam=${r?.cam ?? '-'} lost=${r?.rtp?.lost ?? '-'} pli=${r?.rtp?.pli ?? '-'} jb=${r?.rtp?.jb ?? '-'}`);
    }
  } catch (e) { /* 重连 */ try { ws && ws.close(); } catch {} ws = null; }
  await sleep(2000);
}
console.log(`${stamp()} 结束: 共 ${total} 帧行 → ${OUT}`);
process.exit(0);
