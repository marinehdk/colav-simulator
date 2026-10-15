#!/usr/bin/env node
// twin_eye_probe — DT 视口「人眼级」端到端帧探针(CDP 有头 Chrome,呈现路径真实)。
// 在页面内用 requestVideoFrameCallback 逐呈现帧采集:
//   mediaTime/presentationTime/presentedFrames + 160x90 水面全幅内容差分(md/fchg)
// 离线分类 dup(顿)/skip(跳)/torn(拉扯) 与呈现节拍均匀性 — 不依赖任何 FPS 指标。
// 用法: node twin_eye_probe.mjs --tag base --seconds 90 [--keep] [--cam overlook]
//   --keep 会话保留(默认测完 reset);--cam 附加相机移动段
import { appendFileSync, writeFileSync } from 'node:fs';

const argOf = k => { const i = process.argv.indexOf(`--${k}`); return i < 0 ? undefined : process.argv[i + 1]; };
const TAG = argOf('tag') ?? 'base';
const SECONDS = Number(argOf('seconds') ?? 90);
const KEEP = process.argv.includes('--keep');
const CAM = argOf('cam');
const PORT = 9222;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const t0 = Date.now();
const stamp = () => `[${Math.round((Date.now() - t0) / 1000)}s]`;

const HOSTS = ['127.0.0.1', '[::1]'];
let base = null;
for (const h of HOSTS) { try { await fetch(`http://${h}:${PORT}/json/version`, { signal: AbortSignal.timeout(1000) }); base = `http://${h}:${PORT}`; break; } catch {} }
if (!base) { console.error('CDP 9222 不可达 — 先启动 Chrome'); process.exit(1); }

const tabs = await fetch(`${base}/json`).then(r => r.json());
let tab = tabs.find(t => t.type === 'page' && /:8010/.test(t.url));
if (!tab) {
  tab = await (await fetch(`${base}/json/new?${encodeURIComponent('http://127.0.0.1:8010/')}`, { method: 'PUT' })).json();
  await sleep(3000);
}
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; setTimeout(() => rej(new Error('ws timeout')), 5000); });
let id = 0; const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const { resolve } = pending.get(m.id); pending.delete(m.id); resolve(m.error ? null : m.result); }
});
const send = (method, params = {}) => new Promise(resolve => {
  const i = ++id; pending.set(i, { resolve }); ws.send(JSON.stringify({ id: i, method, params }));
  setTimeout(() => { if (pending.has(i)) { pending.delete(i); resolve(null); } }, 30000);
});
const evaluate = async expression => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }))?.result?.value;
await send('Runtime.enable');
console.log(`${stamp()} attached ${tab.url.slice(0, 50)}`);

// 会话:复用 current(测过)或新建 rule14/head_on/fan_mpc/god
const current = await fetch('http://127.0.0.1:8010/api/sessions/current').then(r => (r.ok ? r.json() : null)).catch(() => null);
let sid = current?.session_id ?? null;
let sessState = current?.state ?? null;
if (!sid || !['RUNNING', 'PAUSED', 'PENDING'].includes(sessState)) {
  if (sid) await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/reset`, { method: 'POST' }).catch(() => {});
  const created = await (await fetch('http://127.0.0.1:8010/api/sessions', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ validation_rule_id: 'rule14', scenario_id: 'head_on',
      algorithm_id: 'potocnik_colreg_fan_mpc', tracker_id: 'vimmjipda',
      ownship_gnc_stack_id: 'original-gnc-20260914-v1-env-on' }),
  })).json();
  sid = created.session_id ?? created.id;
  console.log(`${stamp()} session ${sid}`);
  await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/start`, { method: 'POST' });
  await send('Page.reload'); await sleep(2500);
} else {
  console.log(`${stamp()} reuse session ${sid} (${sessState})`);
  if (sessState === 'PAUSED') await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/resume`, { method: 'POST' }).catch(async () => {
    await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/unpause`, { method: 'POST' });
  });
}

await evaluate(`document.querySelector('[data-workface="deployment"]')?.click()`);
for (let i = 0; i < 60; i++) {
  if (await evaluate(`(() => { const b = document.getElementById('twinViewportBtn'); return b && !b.disabled; })()`)) break;
  await sleep(1500);
}
await evaluate(`(() => { document.getElementById('twinViewportBtn')?.click(); return true; })()`);
// 等流:video ready + 尺寸有效
for (let i = 0; i < 60; i++) {
  const ok = await evaluate(`(() => { const v = document.getElementById('deploymentTwinVideo'); return v && v.readyState >= 2 && v.videoWidth > 0; })()`);
  if (ok) break;
  await sleep(1000);
}
const hud = await evaluate(`document.getElementById('deploymentTwinHud')?.textContent`);
console.log(`${stamp()} stream up, hud=${hud}`);

// 注入人眼探针(幂等)
await evaluate(`(() => {
  const state = { log: [], med: null };
  const cv = document.createElement('canvas'); cv.width = 160; cv.height = 90;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  let prev = null;
  const onFrame = (now, meta) => {
    try {
      const vid = document.getElementById('deploymentTwinVideo');
      if (vid && vid.videoWidth && vid.readyState >= 2) {
        cx.drawImage(vid, 0, 0, 160, 90);
        const d = cx.getImageData(0, 0, 160, 90).data;
        let md = -1, fchg = -1, bm = null;
        if (prev) {
          let s = 0, cnt = 0;
          const W = 8, H = 8, hits = new Array(64).fill(0);
          const rowsN = 90, colsN = 80; // 采样步长8字节=每2px一列,160x90 网格
          for (let i = 0, j = 0; i < d.length; i += 8, j++) {
            let df = d[i] - prev[i]; if (df < 0) df = -df;
            if (df > 2) { cnt++; const r = (j / colsN) | 0, c = j % colsN;
              hits[Math.min(7, (r * 8 / rowsN) | 0) * W + Math.min(7, (c * 8 / colsN) | 0)]++; }
            s += df;
          }
          md = s / (d.length / 8); fchg = cnt / (d.length / 8);
          // 滚动基线;跳变帧(md>2.5x中位)才带空间块图(64个0..1)
          if (md > 0.02) {
            state.med = state.med == null ? md : state.med * 0.95 + md * 0.05;
            if (md > 2.5 * state.med) {
              const per = (d.length / 8) / 64;
              bm = hits.map(v => Math.round(Math.min(1, v / per) * 100) / 100);
            }
          }
        }
        state.log.push({ k: 'f', t: Math.round(now * 10) / 10, mt: +meta.mediaTime.toFixed(4),
          pt: Math.round(meta.presentationTime * 10) / 10, pf: meta.presentedFrames,
          pd: meta.processingDuration != null ? Math.round(meta.processingDuration * 100) / 100 : null,
          md: Math.round(md * 1000) / 1000, fc: Math.round(fchg * 10000) / 10000, bm });
        prev = d;
        if (state.log.length > 40000) state.log.splice(0, 8000);
        vid.requestVideoFrameCallback(onFrame);
      } else {
        prev = null;
        setTimeout(() => { const v2 = document.getElementById('deploymentTwinVideo'); v2 && v2.requestVideoFrameCallback(onFrame); }, 500);
      }
    } catch (e) {}
  };
  const vid0 = document.getElementById('deploymentTwinVideo');
  vid0 && vid0.requestVideoFrameCallback(onFrame);
  state.qtimer = setInterval(async () => {
    try {
      const v = document.getElementById('deploymentTwinVideo');
      const q = v && v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality() : null;
      const ds = (v && v.dataset) || {};
      let rtp = null;
      const rx = window.__twinVideoReceiver;
      if (rx && rx.getStats) {
        const st = await rx.getStats();
        st.forEach(rep => { if (rep.type === 'inbound-rtp' && (rep.kind === 'video' || rep.mediaType === 'video')) rtp = {
          lost: rep.packetsLost ?? null, pli: rep.pliCount ?? null, nack: rep.nackCount ?? null,
          jb: rep.jitterBufferDelay != null && rep.jitterBufferEmittedCount ? Math.round(rep.jitterBufferDelay / rep.jitterBufferEmittedCount * 1000) : null,
          fps: rep.framesPerSecond ?? null }; });
      }
      state.log.push({ k: 'q', t: Date.now() % 1e7, total: q ? q.totalVideoFrames : null,
        drop: q ? q.droppedVideoFrames : null, fps: Number(ds.receivedFps) || null,
        lost: rtp ? rtp.lost : null, pli: rtp ? rtp.pli : null, nack: rtp ? rtp.nack : null,
        jb: rtp ? rtp.jb : null, rtpFps: rtp ? rtp.fps : null });
    } catch (e) {}
  }, 1000);
  window.__eye = state;
  return 'installed';
})()`);

if (CAM) {
  await sleep(Math.round(SECONDS * 500));
  await evaluate(`window.__deploymentTwin?.client?.sendCamera(${JSON.stringify(CAM)})`);
  console.log(`${stamp()} camera → ${CAM}`);
}
console.log(`${stamp()} sampling ${SECONDS}s ...`);
await sleep(SECONDS * 1000);

const rows = await evaluate(`window.__eye ? window.__eye.log : []`);
const out = `/tmp/dt-monitor/eye-${TAG}.jsonl`;
writeFileSync(out, rows.map(r => JSON.stringify(r)).join('\n') + '\n');
const fr = rows.filter(r => r.k === 'f').length;
console.log(`${stamp()} saved ${rows.length} rows (${fr} frames) → ${out}`);

if (!KEEP) {
  await fetch(`http://127.0.0.1:8010/api/sessions/${sid}/reset`, { method: 'POST' }).catch(() => {});
  console.log(`${stamp()} session reset`);
}
process.exit(0);
