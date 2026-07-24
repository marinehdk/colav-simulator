/**
 * Colav-Simulator Web GUI — app.js
 * Canvas rendering, ENC chart overlay, WebSocket telemetry, controls
 */

'use strict';

/* ══════════════════════════════════════════════
   CONSTANTS
══════════════════════════════════════════════ */
const SAFETY_MARGIN_DEFAULT = 150;
const PERF_HISTORY_LEN      = 60;
const DCPA_SAFE  = 300;   // m – green
const DCPA_WARN  = 100;   // m – amber/red
const TCPA_SAFE  = 120;   // s
const TCPA_WARN  = 40;    // s

/* ══════════════════════════════════════════════
   ENC STATE
══════════════════════════════════════════════ */
let encInfo   = null;   // {origin_e, origin_n, width, height, utm_zone}
let encImage  = null;   // HTMLImageElement (PNG tile)
let encReady  = false;
let showENC   = true;   // user toggle

/* ══════════════════════════════════════════════
   MAP VIEW STATE
══════════════════════════════════════════════ */
let viewScale = 0.45;   // px/m
let panX      = 0;
let panY      = 0;
let isPanning = false;
let lastPanX  = 0, lastPanY = 0;

/* ══════════════════════════════════════════════
   PERF / DATA
══════════════════════════════════════════════ */
const perfHistory = [];
let ws          = null;
let currentData = null;
let logCount    = 0;
let lastColregs = '', lastDcpaLevel = '';

/* ══════════════════════════════════════════════
   CANVAS SETUP
══════════════════════════════════════════════ */
const canvas  = document.getElementById('simCanvas');
const ctx     = canvas.getContext('2d');
const wrapper = document.getElementById('canvasWrapper');

function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  const w   = wrapper.clientWidth;
  const h   = wrapper.clientHeight;
  canvas.width  = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width  = `${w}px`;
  canvas.style.height = `${h}px`;
  ctx.scale(dpr, dpr);
  updateScaleBar();
  if (currentData) renderCanvas(currentData);
}

const ro = new ResizeObserver(resizeCanvas);
ro.observe(wrapper);
resizeCanvas();

/* ══════════════════════════════════════════════
   COORDINATE UTILITIES
══════════════════════════════════════════════ */
/** Simulation world [North, East] → canvas pixel */
function worldToCanvas(north, east) {
  const cx = wrapper.clientWidth  / 2 + panX;
  const cy = wrapper.clientHeight / 2 + panY;
  return { x: cx + east * viewScale, y: cy - north * viewScale };
}

/**
 * ENC UTM (Easting, Northing) → canvas pixel.
 * seacharts renders with origin at lower-left; Y axis flipped.
 */
function utmToCanvas(easting, northing) {
  if (!encInfo) return { x: 0, y: 0 };
  // Offset from ENC origin (lower-left corner)
  const de = easting  - encInfo.origin_e;
  const dn = northing - encInfo.origin_n;
  // Sim world uses the ENC origin as (0,0), North = dn, East = de
  return worldToCanvas(dn, de);
}

function updateScaleBar() {
  const w          = wrapper.clientWidth;
  const targetPx   = w * 0.15;
  const targetM    = targetPx / viewScale;
  const magnitude  = Math.pow(10, Math.floor(Math.log10(targetM)));
  const nice       = [1, 2, 5, 10].map(f => f * magnitude)
                                   .find(v => v * viewScale >= targetPx * 0.6) || magnitude;
  const barPx      = nice * viewScale;
  document.getElementById('scaleBarLine').style.width   = `${barPx}px`;
  document.getElementById('scaleBarLabel').textContent  =
    `${nice >= 1000 ? (nice / 1000) + ' km' : nice + ' m'}`;
}

/* ══════════════════════════════════════════════
   ZOOM & PAN
══════════════════════════════════════════════ */
canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.15 : 0.87;
  viewScale = Math.max(0.05, Math.min(5.0, viewScale * factor));
  updateScaleBar();
  if (currentData) renderCanvas(currentData);
}, { passive: false });

canvas.addEventListener('mousedown', e => {
  isPanning = true; lastPanX = e.clientX; lastPanY = e.clientY;
});
window.addEventListener('mousemove', e => {
  if (!isPanning) return;
  panX += e.clientX - lastPanX; panY += e.clientY - lastPanY;
  lastPanX = e.clientX; lastPanY = e.clientY;
  if (currentData) renderCanvas(currentData);
});
window.addEventListener('mouseup', () => { isPanning = false; });

document.getElementById('zoomIn').addEventListener('click', () => {
  viewScale = Math.min(5.0, viewScale * 1.25); updateScaleBar();
  if (currentData) renderCanvas(currentData);
});
document.getElementById('zoomOut').addEventListener('click', () => {
  viewScale = Math.max(0.05, viewScale / 1.25); updateScaleBar();
  if (currentData) renderCanvas(currentData);
});
document.getElementById('zoomReset').addEventListener('click', () => {
  viewScale = 0.45; panX = 0; panY = 0; updateScaleBar();
  if (currentData) renderCanvas(currentData);
});
document.getElementById('toggleENC').addEventListener('click', function () {
  showENC = !showENC;
  this.classList.toggle('enc-on', showENC);
  this.setAttribute('aria-pressed', showENC);
  if (currentData) renderCanvas(currentData);
});

/* ══════════════════════════════════════════════
   ENC INITIALISATION
══════════════════════════════════════════════ */
async function initENC() {
  try {
    const res  = await fetch('/api/enc_info');
    const info = await res.json();

    if (!info.ready) {
      // Poll every 5 s until ENC is ready
      setTimeout(initENC, 5000);
      return;
    }

    encInfo = info;

    // Load PNG tile
    const img = new Image();
    img.onload = () => {
      encImage = img;
      encReady = true;
      document.getElementById('encStatusBadge').textContent = '🗺 ENC Ready';
      document.getElementById('encStatusBadge').classList.add('ready');
      document.getElementById('toggleENC').classList.add('enc-on');
      pushLog(`ENC chart loaded — UTM${info.utm_zone} origin (${info.origin_e.toFixed(0)}, ${info.origin_n.toFixed(0)})`, 'log-ok');
      if (currentData) renderCanvas(currentData);
    };
    img.onerror = () => {
      document.getElementById('encStatusBadge').textContent = '❌ ENC Error';
      document.getElementById('encStatusBadge').classList.add('error');
      pushLog('ENC PNG tile failed to load.', 'log-danger');
    };
    img.src = `/api/enc_tile?t=${Date.now()}`;  // cache-bust

  } catch (e) {
    setTimeout(initENC, 8000);
  }
}

/* ══════════════════════════════════════════════
   RENDERING
══════════════════════════════════════════════ */
function renderCanvas(data) {
  const W = wrapper.clientWidth;
  const H = wrapper.clientHeight;
  ctx.clearRect(0, 0, W, H);

  // ── 1. Background ───────────────────────────────────────────────────────
  const bg = ctx.createRadialGradient(W/2, H/2, 10, W/2, H/2, Math.max(W,H) * 0.8);
  bg.addColorStop(0, '#080e1a');
  bg.addColorStop(1, '#050810');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // ── 2. ENC Chart PNG (bottom layer) ─────────────────────────────────────
  if (showENC && encReady && encImage && encInfo) {
    drawENCTile(W, H);
  }

  // ── 3. Grid & axes (semi-transparent overlay on chart) ──────────────────
  if (!encReady || !showENC) {
    drawGrid(W, H);
  }
  drawAxes(W, H);

  // ── 4. Scenario elements ─────────────────────────────────────────────────
  if (data.waypoints && data.waypoints.length >= 2) drawWaypoints(data.waypoints);
  data.obstacles.forEach(obs =>
    drawObstacle(obs, data.safety_margin || SAFETY_MARGIN_DEFAULT));
  drawOwnshipTrail(data.os);
  if (data.prediction_horizon && data.prediction_horizon.length > 0)
    drawHorizon(data.prediction_horizon);
  drawDCPALine(data);
  drawOwnship(data.os);
}

/* ENC tile — mapped from UTM to canvas space */
function drawENCTile(W, H) {
  if (!encInfo || !encImage) return;

  // The ENC image covers encInfo.width × encInfo.height metres (East × North).
  // Sim origin is always (0,0) in North-East which corresponds to
  // UTM (origin_e, origin_n) — i.e. lower-left corner of the ENC tile.
  // Canvas Y is flipped (North is up on canvas).

  const tilePxW = encInfo.width  * viewScale;
  const tilePxH = encInfo.height * viewScale;

  // Lower-left of the ENC tile in canvas space:
  // North=0, East=0  → worldToCanvas(0,0)
  const llPt = worldToCanvas(0, 0);

  // Because seacharts PNG has (0,0) = lower-left (North=0), and canvas Y
  // increases downward, we draw from upper-left canvas corner:
  const drawX = llPt.x;
  const drawY = llPt.y - tilePxH;   // upper-left = lower-left minus tile height

  ctx.save();
  ctx.globalAlpha = 0.72;
  ctx.drawImage(encImage, drawX, drawY, tilePxW, tilePxH);
  ctx.globalAlpha = 1.0;
  ctx.restore();
}

/* Grid lines */
function drawGrid(W, H) {
  const gridWorld = chooseGridSpacing();
  const gridPx    = gridWorld * viewScale;
  const cx = W / 2 + panX, cy = H / 2 + panY;

  ctx.strokeStyle = 'rgba(255,255,255,0.035)';
  ctx.lineWidth   = 1;

  const x0 = Math.floor(-cx / gridPx), x1 = Math.ceil((W - cx) / gridPx);
  for (let i = x0; i <= x1; i++) {
    const x = cx + i * gridPx;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  const y0 = Math.floor(-cy / gridPx), y1 = Math.ceil((H - cy) / gridPx);
  for (let i = y0; i <= y1; i++) {
    const y = cy + i * gridPx;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
}

function chooseGridSpacing() {
  const worldW = wrapper.clientWidth / viewScale;
  const raw    = worldW / 10;
  const mag    = Math.pow(10, Math.floor(Math.log10(raw)));
  const opts   = [1, 2, 5, 10].map(f => f * mag);
  return opts.find(v => worldW / v <= 20) || opts[opts.length - 1];
}

/* Coordinate axes */
function drawAxes(W, H) {
  const cx = W / 2 + panX, cy = H / 2 + panY;
  ctx.strokeStyle = 'rgba(255,255,255,0.10)';
  ctx.lineWidth   = 1;
  ctx.setLineDash([4, 6]);
  ctx.beginPath(); ctx.moveTo(cx, 0); ctx.lineTo(cx, H); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0, cy); ctx.lineTo(W, cy);  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = 'rgba(138,153,173,0.65)';
  ctx.font      = '11px Outfit, sans-serif';
  ctx.fillText('N', cx + 5, 14);
  ctx.fillText('E', W - 18, cy - 5);
}

/* Waypoints */
function drawWaypoints(wps) {
  const pts = [];
  for (let i = 0; i < wps[0].length; i++)
    pts.push(worldToCanvas(wps[0][i], wps[1][i]));

  ctx.strokeStyle = 'rgba(171,71,188,0.55)';
  ctx.lineWidth   = 2;
  ctx.setLineDash([6, 5]);
  ctx.beginPath();
  pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
  ctx.stroke();
  ctx.setLineDash([]);

  pts.forEach((p, i) => {
    ctx.strokeStyle = '#ab47bc'; ctx.fillStyle = 'rgba(171,71,188,0.25)';
    ctx.lineWidth   = 2;
    ctx.beginPath(); ctx.arc(p.x, p.y, 7, 0, 2 * Math.PI);
    ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#ab47bc';
    ctx.font      = '11px JetBrains Mono, monospace';
    ctx.fillText(`WP${i + 1}`, p.x + 10, p.y + 4);
  });
}

/* Obstacle with safety zone */
function drawObstacle(obs, safetyM) {
  const pt    = worldToCanvas(obs.x, obs.y);
  const safeR = safetyM * viewScale;

  ctx.beginPath(); ctx.arc(pt.x, pt.y, safeR, 0, 2 * Math.PI);
  ctx.fillStyle   = 'rgba(255,75,75,0.05)';
  ctx.strokeStyle = 'rgba(255,75,75,0.30)';
  ctx.lineWidth   = 1.5;
  ctx.setLineDash([4, 5]);
  ctx.fill(); ctx.stroke();
  ctx.setLineDash([]);

  if (obs.trajectory && obs.trajectory.length > 1) {
    ctx.strokeStyle = 'rgba(255,75,75,0.35)';
    ctx.lineWidth   = 1.5;
    ctx.beginPath();
    obs.trajectory.forEach((pos, i) => {
      const p = worldToCanvas(pos[0], pos[1]);
      i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
    });
    ctx.stroke();
  }

  drawVessel(pt.x, pt.y, obs.psi, '#ff4b4b', `TS${obs.id}`, 14);
}

/* Ownship trail */
function drawOwnshipTrail(os) {
  if (!os.trajectory || os.trajectory.length < 2) return;
  ctx.strokeStyle = 'rgba(0,242,254,0.38)';
  ctx.lineWidth   = 2;
  ctx.beginPath();
  os.trajectory.forEach((pos, i) => {
    const p = worldToCanvas(pos[0], pos[1]);
    i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
  });
  ctx.stroke();
}

/* MPC Prediction Horizon */
function drawHorizon(horizon) {
  const pts = horizon.map(p => worldToCanvas(p[0], p[1]));
  ctx.strokeStyle = 'rgba(255,215,0,0.75)';
  ctx.lineWidth   = 2.5;
  ctx.beginPath();
  pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
  ctx.stroke();
  pts.forEach((p, i) => {
    ctx.fillStyle = `rgba(255,215,0,${1 - i / pts.length * 0.6})`;
    ctx.beginPath(); ctx.arc(p.x, p.y, 3.5, 0, 2 * Math.PI); ctx.fill();
  });
}

/* DCPA danger line */
function drawDCPALine(data) {
  if (!data.obstacles || data.obstacles.length === 0) return;
  if (!data.dcpa || data.dcpa > DCPA_SAFE * 2) return;
  const obs   = data.obstacles[0];
  const osPt  = worldToCanvas(data.os.x, data.os.y);
  const obsPt = worldToCanvas(obs.x, obs.y);
  const danger = data.dcpa < DCPA_WARN;
  ctx.strokeStyle = danger ? 'rgba(255,75,75,0.7)' : 'rgba(255,179,0,0.55)';
  ctx.lineWidth   = 1.5;
  ctx.setLineDash([5, 4]);
  ctx.beginPath(); ctx.moveTo(osPt.x, osPt.y); ctx.lineTo(obsPt.x, obsPt.y); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = danger ? '#ff4b4b' : '#ffb300';
  ctx.font      = '11px JetBrains Mono, monospace';
  ctx.fillText(`${Math.round(data.dcpa)}m`,
    (osPt.x + obsPt.x) / 2 + 6, (osPt.y + obsPt.y) / 2 - 4);
}

/* Ownship */
function drawOwnship(os) {
  const pt      = worldToCanvas(os.x, os.y);
  const headLen = Math.max(20, os.u * viewScale * 8);
  ctx.strokeStyle = 'rgba(0,242,254,0.5)';
  ctx.lineWidth   = 1.5;
  ctx.beginPath();
  ctx.moveTo(pt.x, pt.y);
  ctx.lineTo(pt.x + Math.sin(os.psi) * headLen, pt.y - Math.cos(os.psi) * headLen);
  ctx.stroke();
  drawVessel(pt.x, pt.y, os.psi, '#00f2fe', 'OS', 18);
}

/* Generic triangle vessel */
function drawVessel(cx, cy, heading, color, label, size = 14) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(heading);
  ctx.shadowColor = color; ctx.shadowBlur = 10;
  ctx.fillStyle   = color;
  ctx.beginPath();
  ctx.moveTo(0, -size);
  ctx.lineTo(size * 0.5, size * 0.6);
  ctx.lineTo(-size * 0.5, size * 0.6);
  ctx.closePath(); ctx.fill();
  ctx.shadowBlur = 0;
  ctx.restore();
  ctx.fillStyle = '#ffffff';
  ctx.font      = '11px Outfit, sans-serif';
  ctx.fillText(label, cx + size + 4, cy + 4);
}

/* ══════════════════════════════════════════════
   UI TELEMETRY UPDATE
══════════════════════════════════════════════ */
function updateUI(data) {
  const os = data.os;

  // Overlay
  setText('val-step',        data.step);
  setText('val-sim-time',    `${(data.scenario_time ?? data.step * 0.5).toFixed(1)} s`);
  setText('val-algo-active', data.selected_algorithm || '—');

  // DCPA / TCPA
  const dcpa = data.dcpa, tcpa = data.tcpa;
  const dcpaEl = document.getElementById('val-dcpa');
  dcpaEl.textContent = `${dcpa.toFixed(1)} m`;
  setRiskClass(dcpaEl, dcpa, DCPA_SAFE, DCPA_WARN, true);
  const dcpaPct = Math.max(0, Math.min(100, (1 - dcpa / (DCPA_SAFE * 2)) * 100));
  setRiskBar('dcpaBar', dcpaPct, dcpa > DCPA_SAFE ? 'safe' : dcpa > DCPA_WARN ? 'warn' : 'danger');

  const tcpaEl = document.getElementById('val-tcpa');
  tcpaEl.textContent = `${tcpa.toFixed(1)} s`;
  setRiskClass(tcpaEl, tcpa, TCPA_SAFE, TCPA_WARN, true);
  const tcpaPct = Math.max(0, Math.min(100, (1 - tcpa / (TCPA_SAFE * 2)) * 100));
  setRiskBar('tcpaBar', tcpaPct, tcpa > TCPA_SAFE ? 'safe' : tcpa > TCPA_WARN ? 'warn' : 'danger');

  updateColregsBadge(data.colregs);

  if (data.obstacles && data.obstacles.length > 0) {
    const obs  = data.obstacles[0];
    const dist = Math.hypot(os.x - obs.x, os.y - obs.y);
    setText('val-dist', `${dist.toFixed(1)} m`);
  }

  // OS telemetry
  setText('val-os-x',     `${os.x.toFixed(1)} m`);
  setText('val-os-y',     `${os.y.toFixed(1)} m`);
  setText('val-os-psi',   `${(os.psi * 180 / Math.PI).toFixed(1)}°`);
  setText('val-os-speed', `${os.u.toFixed(2)} m/s`);
  setText('val-os-v',     `${(os.v || 0).toFixed(2)} m/s`);
  setText('val-os-r',     `${(os.r || 0).toFixed(3)} rad/s`);
  setText('val-horizon-len',
    data.prediction_horizon ? `${data.prediction_horizon.length} steps` : '— steps');

  // Compass
  const headDeg = os.psi * 180 / Math.PI;
  document.getElementById('compassNeedle').setAttribute('transform', `rotate(${headDeg} 40 40)`);
  setText('val-compass-deg', `${((headDeg % 360 + 360) % 360).toFixed(0).padStart(3, '0')}°`);

  // Performance
  const stepMs = data.step_time_ms;
  setText('val-step-time', `${stepMs.toFixed(2)} ms`);
  perfHistory.push(stepMs);
  if (perfHistory.length > PERF_HISTORY_LEN) perfHistory.shift();
  const avg = perfHistory.reduce((a, b) => a + b, 0) / perfHistory.length;
  setText('val-avg-time', `${avg.toFixed(2)} ms`);
  drawPerfChart();

  // Algorithm status pills (first telemetry frame)
  if (data.algo_status) renderAlgoStatus(data.algo_status);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function setRiskClass(el, value, safe, warn, invert) {
  el.classList.remove('safe', 'warn', 'danger');
  if (invert) {
    if (value > safe) el.classList.add('safe');
    else if (value > warn) el.classList.add('warn');
    else el.classList.add('danger');
  }
}

function setRiskBar(id, pct, level) {
  const bar = document.getElementById(id);
  if (!bar) return;
  bar.style.width      = `${pct}%`;
  bar.style.background = level === 'safe' ? 'var(--risk-safe)'
                       : level === 'warn' ? 'var(--risk-warn)'
                                          : 'var(--risk-danger)';
}

function updateColregsBadge(rule) {
  const badge     = document.getElementById('val-colregs');
  badge.textContent = rule;
  badge.className   = 'colregs-badge';
  if      (rule.includes('14'))        badge.classList.add('rule-14');
  else if (rule.includes('Give-Way'))  badge.classList.add('rule-15-giveway');
  else if (rule.includes('Stand-on'))  badge.classList.add('rule-15-standon');
  else if (rule.includes('13'))        badge.classList.add('rule-13');
  else if (rule.includes('Clear'))     badge.classList.add('clear');
}

let _algoStatusRendered = false;
function renderAlgoStatus(status) {
  if (_algoStatusRendered) return;
  _algoStatusRendered = true;
  const row = document.getElementById('algoStatusRow');
  if (!row) return;
  const labels = { CustomMPC: 'CustomMPC', PSBMPC: 'PSB-MPC', RLMPC: 'RL-MPC', 'RRT-Star': 'RRT*' };
  Object.entries(status).forEach(([key, available]) => {
    const pill = document.createElement('span');
    pill.className   = `algo-pill ${available ? 'available' : 'unavailable'}`;
    pill.textContent = `${available ? '✓' : '✗'} ${labels[key] || key}`;
    row.appendChild(pill);
  });
}

/* ══════════════════════════════════════════════
   PERFORMANCE SPARKLINE
══════════════════════════════════════════════ */
function drawPerfChart() {
  const pc   = document.getElementById('perfChart');
  if (!pc) return;
  const pctx = pc.getContext('2d');
  const cw   = pc.clientWidth || 288;
  const ch   = 70;
  if (pc.width !== cw) pc.width = cw;
  pctx.clearRect(0, 0, cw, ch);
  pctx.fillStyle = 'rgba(0,0,0,0.15)';
  pctx.fillRect(0, 0, cw, ch);
  if (perfHistory.length < 2) return;

  const maxVal  = Math.max(...perfHistory, 1);
  const range   = maxVal || 1;
  const pad     = 6;
  const xStep   = (cw - pad * 2) / (PERF_HISTORY_LEN - 1);

  const gy = ch - pad - (maxVal / 2 / range) * (ch - pad * 2);
  pctx.strokeStyle = 'rgba(255,255,255,0.07)';
  pctx.lineWidth   = 1;
  pctx.setLineDash([3, 4]);
  pctx.beginPath(); pctx.moveTo(pad, gy); pctx.lineTo(cw - pad, gy); pctx.stroke();
  pctx.setLineDash([]);

  const grad = pctx.createLinearGradient(0, pad, 0, ch - pad);
  grad.addColorStop(0, 'rgba(0,242,254,0.4)');
  grad.addColorStop(1, 'rgba(0,242,254,0.0)');

  pctx.fillStyle   = grad;
  pctx.strokeStyle = 'rgba(0,242,254,0.9)';
  pctx.lineWidth   = 1.5;

  pctx.beginPath();
  perfHistory.forEach((v, i) => {
    const x = pad + i * xStep;
    const y = ch - pad - (v / range) * (ch - pad * 2);
    i === 0 ? pctx.moveTo(x, y) : pctx.lineTo(x, y);
  });
  const lastX = pad + (perfHistory.length - 1) * xStep;
  pctx.lineTo(lastX, ch - pad); pctx.lineTo(pad, ch - pad);
  pctx.closePath(); pctx.fill();

  pctx.beginPath();
  perfHistory.forEach((v, i) => {
    const x = pad + i * xStep;
    const y = ch - pad - (v / range) * (ch - pad * 2);
    i === 0 ? pctx.moveTo(x, y) : pctx.lineTo(x, y);
  });
  pctx.stroke();

  pctx.fillStyle = 'rgba(138,153,173,0.65)';
  pctx.font      = '9px JetBrains Mono, monospace';
  pctx.fillText(`${maxVal.toFixed(1)}ms`, pad + 2, pad + 9);
}

/* ══════════════════════════════════════════════
   EVENT LOG
══════════════════════════════════════════════ */
function pushLog(msg, cls = 'log-info') {
  const terminal = document.getElementById('logTerminal');
  if (!terminal) return;
  const entry = document.createElement('div');
  entry.className = `log-entry ${cls}`;
  const t   = new Date();
  const ts  = `${String(t.getMinutes()).padStart(2,'0')}:${String(t.getSeconds()).padStart(2,'0')}`;
  entry.textContent = `[${ts}] ${msg}`;
  terminal.appendChild(entry);
  while (terminal.children.length > 120) terminal.removeChild(terminal.firstChild);
  terminal.scrollTop = terminal.scrollHeight;
}

function checkLogEvents(data) {
  const col = data.colregs;
  if (col !== lastColregs) {
    const cls = col.includes('14')       ? 'log-warn'   :
                col.includes('Give-Way') ? 'log-danger' :
                col.includes('Clear')    ? 'log-ok'     : 'log-info';
    pushLog(`COLREGs → ${col}`, cls);
    lastColregs = col;
  }
  const lvl = data.dcpa > DCPA_SAFE ? 'safe' : data.dcpa > DCPA_WARN ? 'warn' : 'danger';
  if (lvl !== lastDcpaLevel) {
    pushLog(`DCPA ${lvl.toUpperCase()} — ${data.dcpa.toFixed(0)} m`,
            lvl === 'safe' ? 'log-ok' : lvl === 'warn' ? 'log-warn' : 'log-danger');
    lastDcpaLevel = lvl;
  }
}

/* ══════════════════════════════════════════════
   WEBSOCKET
══════════════════════════════════════════════ */
function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    document.getElementById('conn-status').textContent = 'Connected';
    document.getElementById('status-dot').classList.add('active');
    document.getElementById('status-dot').closest('.status-indicator').classList.add('connected');
    pushLog('WebSocket connected to simulation engine.', 'log-ok');
  };

  ws.onmessage = e => {
    const data = JSON.parse(e.data);
    if (!data.os) return;    // heartbeat without full state
    currentData = data;
    updateUI(data);
    renderCanvas(data);
    checkLogEvents(data);
  };

  ws.onclose = () => {
    document.getElementById('conn-status').textContent = 'Reconnecting…';
    document.getElementById('status-dot').classList.remove('active');
    document.getElementById('status-dot').closest('.status-indicator').classList.remove('connected');
    setTimeout(connectWebSocket, 2500);
  };

  ws.onerror = () => pushLog('WebSocket error — retrying…', 'log-danger');
}

/* ══════════════════════════════════════════════
   CONTROLS
══════════════════════════════════════════════ */
document.getElementById('btnStart').addEventListener('click', async () => {
  await fetch('/api/start', { method: 'POST' });
  pushLog('▶ Simulation started.', 'log-ok');
});

document.getElementById('btnPause').addEventListener('click', async () => {
  await fetch('/api/pause', { method: 'POST' });
  pushLog('⏸ Simulation paused.', 'log-info');
});

document.getElementById('btnReset').addEventListener('click', async () => {
  const scenario = document.getElementById('scenarioSelect').value;
  await fetch(`/api/reset?scenario=${encodeURIComponent(scenario)}`, { method: 'POST' });
  currentData = null;
  perfHistory.length = 0;
  lastColregs = ''; lastDcpaLevel = '';
  _algoStatusRendered = false;
  document.getElementById('algoStatusRow').innerHTML = '';
  pushLog(`⟳ Reset → ${scenario}`, 'log-warn');
});

document.getElementById('algoSelect').addEventListener('change', async e => {
  const algo = e.target.value;
  const res  = await fetch(`/api/select_algorithm?algorithm=${encodeURIComponent(algo)}`, { method: 'POST' });
  const data = await res.json();
  pushLog(`Algorithm → ${data.algorithm}`, 'log-info');
});

document.getElementById('scenarioSelect').addEventListener('change', async e => {
  const s = e.target.value;
  await fetch(`/api/reset?scenario=${encodeURIComponent(s)}`, { method: 'POST' });
  document.querySelectorAll('.qtab').forEach(t => t.classList.toggle('active', t.dataset.scenario === s));
  pushLog(`Scenario → ${s}`, 'log-info');
});

document.querySelectorAll('.qtab').forEach(tab => {
  tab.addEventListener('click', async () => {
    const s = tab.dataset.scenario;
    document.getElementById('scenarioSelect').value = s;
    document.querySelectorAll('.qtab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    await fetch(`/api/reset?scenario=${encodeURIComponent(s)}`, { method: 'POST' });
    pushLog(`Scenario (tab) → ${s}`, 'log-info');
  });
});

document.getElementById('speedSlider').addEventListener('input', async e => {
  const speed = parseFloat(e.target.value);
  document.getElementById('speedLabel').textContent = `${speed.toFixed(1)}×`;
  await fetch(`/api/set_speed?multiplier=${speed}`, { method: 'POST' }).catch(() => {});
});

const logSection = document.querySelector('.log-section');
const logToggle  = document.getElementById('logToggle');
logToggle.addEventListener('click', () => {
  logSection.classList.toggle('collapsed');
  logToggle.setAttribute('aria-expanded', !logSection.classList.contains('collapsed'));
});
logToggle.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); logToggle.click(); }
});

/* ── Boot ─────────────────────────────────────── */
document.getElementById('toggleENC').classList.add('enc-on');
connectWebSocket();
initENC();       // start polling ENC status in background
