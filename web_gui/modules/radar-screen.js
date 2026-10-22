import { RadarVideoBuffer } from './radar-video.js?v=20261008-radar-v1';
import {
  N_METERS_PER_NM,
  PPI_DESCRIPTOR_DEFAULT,
  clutterPoints,
  sweepAzimuthRad,
} from './radar-ppi.js?v=20261022-radar-screen-v1';

/**
 * Standalone Furuno FAR-2xx8 style shipborne radar screen (radar.html).
 *
 * Three-zone layout per docs/research/2026-10-22-radar-screen/
 * 11-furuno-far2xx8-digest.md §1: left InstantAccess bar, center PPI with
 * function boxes, right information column. Consumes the same WS telemetry
 * envelope as the main app (radar_scans / radar_ppi / truth[].ais /
 * truth[].tracks) plus the frozen radar_controls POST contract
 * (20-API-CONTRACT.md); the backend owns the true receiver controls, this
 * page mirrors them from the radar_ppi descriptor readback.
 *
 * Pure functions (range table, CPA/TCPA/BCR/BCT, threat state machine,
 * palettes, formatting) are exported for node:test; the boot()/draw code
 * owns DOM, WebSocket and canvas only. No build step, no CDN, no global
 * hotkeys — every control is a real button/slider reachable by keyboard.
 */

const TWO_PI = Math.PI * 2;

function wrapAngle(angle) {
  return ((angle % TWO_PI) + TWO_PI) % TWO_PI;
}

/* ══════════════════════════════════════════════
   PURE DATA TABLES (decision doc Q9/Q10/Q13/Q14)
══════════════════════════════════════════════ */

/** Furuno FAR-2xx8 17 range scales: nm, ring spacing (nm), ring count. */
export const FURUNO_RANGE_TABLE = Object.freeze([
  Object.freeze({ nm: 0.125, ringNm: 0.025, rings: 5 }),
  Object.freeze({ nm: 0.25, ringNm: 0.05, rings: 5 }),
  Object.freeze({ nm: 0.5, ringNm: 0.1, rings: 5 }),
  Object.freeze({ nm: 0.75, ringNm: 0.25, rings: 3 }),
  Object.freeze({ nm: 1, ringNm: 0.25, rings: 4 }),
  Object.freeze({ nm: 1.5, ringNm: 0.25, rings: 6 }),
  Object.freeze({ nm: 2, ringNm: 0.5, rings: 4 }),
  Object.freeze({ nm: 3, ringNm: 0.5, rings: 6 }),
  Object.freeze({ nm: 4, ringNm: 1, rings: 4 }),
  Object.freeze({ nm: 6, ringNm: 1, rings: 6 }),
  Object.freeze({ nm: 8, ringNm: 2, rings: 4 }),
  Object.freeze({ nm: 12, ringNm: 2, rings: 6 }),
  Object.freeze({ nm: 16, ringNm: 4, rings: 4 }),
  Object.freeze({ nm: 24, ringNm: 4, rings: 6 }),
  Object.freeze({ nm: 32, ringNm: 8, rings: 4 }),
  Object.freeze({ nm: 48, ringNm: 8, rings: 6 }),
  Object.freeze({ nm: 96, ringNm: 16, rings: 6 }),
]);

/** Table entry for one scale, or null when off-table. */
export function rangeEntry(nm) {
  const value = Number(nm);
  return FURUNO_RANGE_TABLE.find(entry => Math.abs(entry.nm - value) < 1e-9) ?? null;
}

/** Range stepper over the 17-scale table; clamps at both ends. */
export function stepRangeNm(currentNm, direction) {
  const index = FURUNO_RANGE_TABLE.findIndex(entry => Math.abs(entry.nm - Number(currentNm)) < 1e-9);
  if (index < 0) return FURUNO_RANGE_TABLE[Math.min(9, FURUNO_RANGE_TABLE.length - 1)].nm;
  const next = Math.max(0, Math.min(FURUNO_RANGE_TABLE.length - 1, index + Math.sign(direction)));
  return FURUNO_RANGE_TABLE[next].nm;
}

/** Trails time steps (digest §4, web subset). */
export const TRAIL_STEPS = Object.freeze([
  Object.freeze({ key: 'OFF', label: 'OFF', seconds: 0 }),
  Object.freeze({ key: '15s', label: '15s', seconds: 15 }),
  Object.freeze({ key: '30s', label: '30s', seconds: 30 }),
  Object.freeze({ key: '1m', label: '1m', seconds: 60 }),
  Object.freeze({ key: '3m', label: '3m', seconds: 180 }),
  Object.freeze({ key: '6m', label: '6m', seconds: 360 }),
  Object.freeze({ key: 'CONT', label: 'CONT', seconds: 3600 }),
]);

export function stepTrails(currentKey) {
  const index = TRAIL_STEPS.findIndex(step => step.key === currentKey);
  return TRAIL_STEPS[(Math.max(0, index) + 1) % TRAIL_STEPS.length];
}

/** TT/AIS vector time presets (minutes). */
export const VECTOR_TIME_MINUTES = Object.freeze([0.5, 1, 3, 6]);

export function stepVectorTime(currentMin) {
  const index = VECTOR_TIME_MINUTES.findIndex(value => Math.abs(value - Number(currentMin)) < 1e-9);
  return VECTOR_TIME_MINUTES[(Math.max(0, index) + 1) % VECTOR_TIME_MINUTES.length];
}

/** Presentation modes: HU/CU/NU x RM/TM (digest §1 function box 1). */
export const PRESENTATION_MODES = Object.freeze([
  Object.freeze({ key: 'HU_RM', label: 'HEAD UP RM', headingUp: true, courseUp: false, trueMotion: false }),
  Object.freeze({ key: 'CU_RM', label: 'COURSE UP RM', headingUp: false, courseUp: true, trueMotion: false }),
  Object.freeze({ key: 'NU_RM', label: 'NORTH UP RM', headingUp: false, courseUp: false, trueMotion: false }),
  Object.freeze({ key: 'NU_TM', label: 'NORTH UP TM', headingUp: false, courseUp: false, trueMotion: true }),
]);

export function stepPresentationMode(currentKey) {
  const index = PRESENTATION_MODES.findIndex(mode => mode.key === currentKey);
  return PRESENTATION_MODES[(Math.max(0, index) + 1) % PRESENTATION_MODES.length];
}

/* ══════════════════════════════════════════════
   PURE GEOMETRY: CPA/TCPA, BCR/BCT, threat
══════════════════════════════════════════════ */

/**
 * Relative-motion solution between ownship and one target.
 * Positions NE (m), cog rad compass-from-north, sog m/s.
 * tcpaS < 0 means the pair is opening (closest approach already passed).
 */
export function cpaTcpa(ownship, target) {
  const dN = target.north - ownship.north;
  const dE = target.east - ownship.east;
  const rangeM = Math.hypot(dN, dE);
  const bearingRad = wrapAngle(Math.atan2(dE, dN));
  const relN = target.sogMps * Math.cos(target.cogRad) - ownship.sogMps * Math.cos(ownship.cogRad);
  const relE = target.sogMps * Math.sin(target.cogRad) - ownship.sogMps * Math.sin(ownship.cogRad);
  const relSpeed2 = relN * relN + relE * relE;
  if (relSpeed2 < 1e-9) return { rangeM, bearingRad, cpaM: rangeM, tcpaS: 0, closing: false };
  const tcpaS = -(dN * relN + dE * relE) / relSpeed2;
  const cpaN = dN + relN * tcpaS;
  const cpaE = dE + relE * tcpaS;
  return {
    rangeM,
    bearingRad,
    cpaM: Math.hypot(cpaN, cpaE),
    tcpaS,
    closing: tcpaS > 0,
  };
}

/**
 * Bow crossing prediction: when the target's relative motion crosses the
 * ownship's course line. bcrM is measured along the own course (positive =
 * ahead of the bow); both fields are null when the courses never cross or
 * the crossing lies in the past.
 */
export function bcrBct(ownship, target) {
  const dN = target.north - ownship.north;
  const dE = target.east - ownship.east;
  const relN = target.sogMps * Math.cos(target.cogRad) - ownship.sogMps * Math.cos(ownship.cogRad);
  const relE = target.sogMps * Math.sin(target.cogRad) - ownship.sogMps * Math.sin(ownship.cogRad);
  const courseN = Math.cos(ownship.cogRad);
  const courseE = Math.sin(ownship.cogRad);
  const dPerp = dN * -courseE + dE * courseN;
  const vPerp = relN * -courseE + relE * courseN;
  if (Math.abs(vPerp) < 1e-9) return { bcrM: null, bctS: null };
  const bctS = -dPerp / vPerp;
  if (!(bctS > 0)) return { bcrM: null, bctS: null };
  const alongN = dN + relN * bctS;
  const alongE = dE + relE * bctS;
  return { bcrM: alongN * courseN + alongE * courseE, bctS };
}

/** Furuno CPA/TCPA intrusion test (digest §6: CPA within limit AND 0<=TCPA<=limit). */
export function threatLevel(solution, limits) {
  const cpaOk = solution.cpaM <= limits.cpaLimitM;
  const tcpaOk = solution.tcpaS >= 0 && solution.tcpaS <= limits.tcpaLimitS;
  return cpaOk && tcpaOk ? 'dangerous' : 'safe';
}

/**
 * IEC 62288 symbol state machine (digest §6). Precedence: lost > dangerous >
 * selected > tracked. Acknowledged danger stops flashing but stays red.
 */
export function targetSymbolState({ threat = 'safe', selected = false, lost = false, acknowledged = false } = {}) {
  if (lost) return { kind: 'lost', flashing: !acknowledged, color: 'alarm' };
  if (threat === 'dangerous') return { kind: 'dangerous', flashing: !acknowledged, color: 'alarm' };
  if (selected) return { kind: 'selected', flashing: false, color: 'selection' };
  return { kind: 'tracked', flashing: false, color: 'target' };
}

/* ══════════════════════════════════════════════
   PURE FORMATTING (digest §1 readout styles)
══════════════════════════════════════════════ */

/** 045.3-style bearing text. */
export function formatBearing(deg) {
  const normalized = ((Number(deg) % 360) + 360) % 360;
  const text = normalized.toFixed(1);
  return text === '360.0' ? '000.0' : text.padStart(5, '0');
}

/** Relative bearing 0..360 from a true bearing plus the reference (deg). */
export function relativeBearing(trueDeg, referenceDeg = 0) {
  return ((Number(trueDeg) - Number(referenceDeg)) % 360 + 360) % 360;
}

/** EBL readout in the digest style `045.3°R` / `287.1°T`. */
export function formatEbl(trueDeg, referenceDeg = 0, relative = false) {
  const value = relative ? relativeBearing(trueDeg, referenceDeg) : ((Number(trueDeg) % 360) + 360) % 360;
  return `${formatBearing(value)}${relative ? '°R' : '°T'}`;
}

/** VRM readout in the digest style `28.11NM`. */
export function formatVrm(nm) {
  return `${Number(nm).toFixed(2)}NM`;
}

/** Range box label in the digest style `6.0 NM 1.0NM`. */
export function formatRangeBox(nm) {
  const entry = rangeEntry(nm);
  const scale = entry ? entry.nm : Number(nm);
  const ringText = entry ? ` ${entry.ringNm}NM` : '';
  return `${scale} NM${ringText}`;
}

/** Furuno POSN style `34°41.2'N 135°18.7'E`; `***` fields when invalid. */
export function formatLatLon(lat, lon) {
  const hemisphere = (value, positive, negative) => {
    const abs = Math.abs(value);
    const degrees = Math.floor(abs);
    const minutes = ((abs - degrees) * 60).toFixed(1).padStart(4, '0');
    return `${degrees}°${minutes}'${value >= 0 ? positive : negative}`;
  };
  if (!Number.isFinite(Number(lat)) || !Number.isFinite(Number(lon))) return '***°**.*\'*';
  return `${hemisphere(Number(lat), 'N', 'S')} ${hemisphere(Number(lon), 'E', 'W')}`;
}

/** Envelope ais_utc (ISO) -> `DD.MM.YYYY  HH:MM:SS` (UTC); null when invalid. */
export function formatUtcStamp(isoString, fallbackDate = null) {
  const date = isoString ? new Date(isoString) : fallbackDate;
  if (!date || Number.isNaN(date.getTime())) return null;
  const pad = value => String(value).padStart(2, '0');
  return `${pad(date.getUTCDate())}.${pad(date.getUTCMonth() + 1)}.${date.getUTCFullYear()}  `
    + `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}:${pad(date.getUTCSeconds())}`;
}

/* ══════════════════════════════════════════════
   PURE PALETTES (Q14: DAY-GRY / DUSK-BLU / NIGHT-GRY)
══════════════════════════════════════════════ */

/** Canonical token set shared by every palette (CSS mirrors as --rs-*). */
export const PALETTE_TOKENS = Object.freeze([
  'surface', 'surfaceAlt', 'border', 'text', 'textMuted', 'textDim', 'accent',
  'alarm', 'warning', 'target', 'targetVector', 'ais', 'selection', 'vrm', 'ebl',
  'ppiGrid', 'ppiText', 'echo', 'sweep', 'cursor',
]);

export const PALETTES = Object.freeze({
  'day-gry': Object.freeze({
    surface: '#d4d7d8', surfaceAlt: '#c3c7c9', border: '#969c9e',
    text: '#1c1f20', textMuted: '#4a5052', textDim: '#6b7274',
    accent: '#0f7a3d', alarm: '#d0011b', warning: '#a06a00',
    target: '#0069c0', targetVector: '#0069c0', ais: '#a05a00',
    selection: '#b0006d', vrm: '#a07000', ebl: '#a07000',
    ppiGrid: '#1e4d3a', ppiText: '#2b2f30', echo: '#2fd06f', sweep: '#0f9d58', cursor: '#007a8a',
  }),
  'dusk-blu': Object.freeze({
    surface: '#1d2c44', surfaceAlt: '#16233a', border: '#3c5478',
    text: '#d8e4f4', textMuted: '#8fa4c4', textDim: '#5d7396',
    accent: '#4f9de0', alarm: '#ff4b5c', warning: '#ffc857',
    target: '#6fc2ff', targetVector: '#6fc2ff', ais: '#ffcf6f',
    selection: '#ff77c8', vrm: '#ffd36d', ebl: '#ffd36d',
    ppiGrid: '#33547a', ppiText: '#a9bede', echo: '#52e08c', sweep: '#86ffb0', cursor: '#5fd6e8',
  }),
  'night-gry': Object.freeze({
    surface: '#1b1e1d', surfaceAlt: '#141615', border: '#333836',
    text: '#cfd6d2', textMuted: '#8b958f', textDim: '#5a625e',
    accent: '#39d98a', alarm: '#ff3b47', warning: '#ffb300',
    target: '#6ec6ff', targetVector: '#6ec6ff', ais: '#ffd36d',
    selection: '#ff6ad5', vrm: '#e6b94d', ebl: '#e6b94d',
    ppiGrid: '#1e4d3a', ppiText: '#9fb8ad', echo: '#39d98a', sweep: '#7dffb8', cursor: '#55c8dc',
  }),
});

export const PALETTE_NAMES = Object.freeze(Object.keys(PALETTES));
export const DEFAULT_PALETTE = 'night-gry';

/** Token map for one palette; unknown names fall back to NIGHT-GRY. */
export function paletteVars(name) {
  return PALETTES[PALETTE_NAMES.includes(name) ? name : DEFAULT_PALETTE];
}

/** Local clutter re-render strength after A/C SEA + A/C RAIN suppression. */
export function clutterSuppressionFactor(rangeM, sea = 0, rain = 0) {
  const suppression = (Number(sea) / 100) * 0.85 * Math.exp(-Math.max(0, rangeM) / 1800)
    + (Number(rain) / 100) * 0.5;
  return Math.max(0.05, 1 - suppression);
}

/* ══════════════════════════════════════════════
   PURE MODEL: descriptor readback + envelope targets
══════════════════════════════════════════════ */

/**
 * Descriptor readback (20-API-CONTRACT.md operator_controls). Lenient:
 * missing keys keep the previous value; unknown shapes return null.
 */
export function syncControlsFromDescriptor(descriptor, previous = { gainDb: 0, sea: 0, rain: 0, standby: false }) {
  const controls = descriptor?.operator_controls;
  if (!controls || typeof controls !== 'object') return null;
  return {
    gainDb: Number.isFinite(Number(controls.gain_db)) ? Number(controls.gain_db) : previous.gainDb,
    sea: Number.isFinite(Number(controls.sea_suppression)) ? Number(controls.sea_suppression) : previous.sea,
    rain: Number.isFinite(Number(controls.rain_suppression)) ? Number(controls.rain_suppression) : previous.rain,
    standby: typeof controls.standby === 'boolean' ? controls.standby : previous.standby,
  };
}

/**
 * Projects one telemetry envelope into the screen target list.
 * TT targets come from envelope.tracks[0] (ownship tracker, local NE
 * [n, e, vn, ve]); AIS targets from truth[1..] entries carrying an `ais`
 * display-state block. CPA/TCPA/BCR/BCT are computed client-side against
 * the envelope ownship (os) per the decision doc Q12.
 */
export function buildScreenTargets(envelope, limits = { cpaLimitNm: 1, tcpaLimitMin: 12 }) {
  const os = envelope?.os;
  if (!os || !(Number.isFinite(os.x) || Number.isFinite(os.north))) return [];
  const own = {
    north: Number.isFinite(os.north) ? os.north : os.x,
    east: Number.isFinite(os.east) ? os.east : os.y,
    cogRad: Number.isFinite(os.cog) ? os.cog : (Number.isFinite(os.psi) ? os.psi : 0),
    sogMps: Number.isFinite(os.sog) ? os.sog : Math.hypot(Number(os.u) || 0, Number(os.v) || 0),
  };
  const limitsM = {
    cpaLimitM: limits.cpaLimitNm * N_METERS_PER_NM,
    tcpaLimitS: limits.tcpaLimitMin * 60,
  };
  const targets = [];

  const trackSet = envelope?.tracks?.[0];
  if (envelope?.executed_tracker !== 'god' && Array.isArray(trackSet?.states)) {
    trackSet.states.forEach((trackState, index) => {
      if (!Array.isArray(trackState) || !Number.isFinite(trackState[0]) || !Number.isFinite(trackState[1])) return;
      const vn = Number.isFinite(trackState[2]) ? trackState[2] : 0;
      const ve = Number.isFinite(trackState[3]) ? trackState[3] : 0;
      const sog = Math.hypot(vn, ve);
      const target = {
        type: 'tt',
        id: String(trackSet.labels?.[index] ?? index + 1),
        label: `T${trackSet.labels?.[index] ?? index + 1}`,
        north: trackState[0],
        east: trackState[1],
        cogRad: sog > 0.05 ? wrapAngle(Math.atan2(ve, vn)) : own.cogRad,
        sogMps: sog,
      };
      const solution = cpaTcpa(own, target);
      targets.push({
        ...target,
        ...solution,
        bcrBct: bcrBct(own, target),
        threat: threatLevel(solution, limitsM),
        lost: false,
      });
    });
  }

  const ships = Array.isArray(envelope?.truth) ? envelope.truth : [];
  for (const ship of ships.slice(1)) {
    const north = Number.isFinite(ship?.north) ? ship.north : ship?.x;
    const east = Number.isFinite(ship?.east) ? ship.east : ship?.y;
    if (!Number.isFinite(north) || !Number.isFinite(east)) continue;
    const ais = ship?.ais ?? null;
    const target = {
      type: 'ais',
      id: String(ship?.mmsi ?? ship?.id ?? ''),
      label: String(ship?.label ?? ship?.mmsi ?? ''),
      north,
      east,
      cogRad: Number.isFinite(ship?.cog) ? ship.cog : 0,
      sogMps: Number.isFinite(ship?.sog) ? ship.sog : 0,
      headingRad: Number.isFinite(ship?.psi) ? ship.psi : null,
      aisState: ais?.state ?? null,
    };
    const solution = cpaTcpa(own, target);
    targets.push({
      ...target,
      ...solution,
      bcrBct: bcrBct(own, target),
      threat: threatLevel(solution, limitsM),
      lost: ais?.state === 'lost',
    });
  }
  return targets;
}

/** Active alert rows (digest §6/§8): CPA/TCPA intrusions + lost AIS targets. */
export function activeAlerts(targets) {
  const alerts = [];
  for (const target of targets) {
    if (target.lost) {
      alerts.push({
        id: `lost:${target.type}:${target.id}`,
        kind: 'TARGET LOST',
        level: 'warning',
        label: `${target.type === 'tt' ? 'TT' : 'AIS'} ${target.label} LOST`,
      });
    } else if (target.threat === 'dangerous') {
      alerts.push({
        id: `cpa:${target.type}:${target.id}`,
        kind: 'CPA/TCPA',
        level: 'alarm',
        label: `${target.type === 'tt' ? 'TT' : 'AIS'} ${target.label} TAKE EVASIVE ACTION`,
      });
    }
  }
  return alerts;
}

/* ══════════════════════════════════════════════
   PAGE LOGIC (DOM, WS, canvas)
══════════════════════════════════════════════ */

const TEXT = {
  noSession: 'URL ?session=<id> 指定会话',
  standby: 'TX 钮启动发射',
  tx: 'TX 发射中',
  connecting: '连接遥测流…',
  disconnected: '遥测连接断开，重连中…',
};

function ownshipFromEnvelope(envelope) {
  const os = envelope?.os ?? {};
  return {
    north: Number.isFinite(os.north) ? os.north : (Number(os.x) || 0),
    east: Number.isFinite(os.east) ? os.east : (Number(os.y) || 0),
    headingRad: Number.isFinite(os.psi) ? os.psi : (Number(os.cog) || 0),
    courseRad: Number.isFinite(os.cog) ? os.cog : (Number(os.psi) || 0),
  };
}

function relativePos(envelope, target) {
  const os = ownshipFromEnvelope(envelope);
  return { northRel: target.north - os.north, eastRel: target.east - os.east };
}

function hexToRgba(hex, alpha) {
  const value = String(hex).replace('#', '');
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function byId(id) {
  return document.getElementById(id);
}

export function createRadarScreen(root, options = {}) {
  const state = {
    session: options.session ?? new URLSearchParams(window.location.search).get('session'),
    descriptor: PPI_DESCRIPTOR_DEFAULT,
    controls: { gainDb: 0, sea: 0, rain: 0, standby: false },
    hasRadar: false,
    envelope: null,
    rangeNm: 6,
    presentation: PRESENTATION_MODES[2],
    trails: TRAIL_STEPS[0],
    hlOff: false,
    palette: DEFAULT_PALETTE,
    vectorTimeMin: 3,
    vectorMode: 'TRUE-G',
    cpaLimitNm: 1,
    tcpaLimitMin: 12,
    marks: {
      vrm: [{ on: false, nm: 0.5 }, { on: false, nm: 1.5 }],
      ebl: [{ on: false, trueDeg: 45, offsetN: 0, offsetE: 0 }, { on: false, trueDeg: 315, offsetN: 0, offsetE: 0 }],
      active: null,
    },
    selected: null,
    acknowledged: new Set(),
    cursor: null,
    centerOffsetN: 0,
    centerOffsetE: 0,
    motionOrigin: null,
    videoStatus: 'NO_VIDEO',
  };

  const canvas = root.querySelector('#rsPpi');
  const ctx = canvas?.getContext('2d');
  const els = {};
  for (const name of [
    'rsTx', 'rsTxRing', 'rsTxLabel', 'rsBtnGain', 'rsBtnSea', 'rsBtnRain',
    'rsAdjustPanel', 'rsAdjustSlider', 'rsAdjustValue', 'rsAdjustTitle', 'rsAdjustClose',
    'rsBtnTrails', 'rsBtnHl', 'rsBtnReset', 'rsBtnMarks', 'rsBtnBrill',
    'rsModeButton', 'rsModeLabel', 'rsRangeLabel', 'rsRangeUp', 'rsRangeDown',
    'rsEchoGainBar', 'rsEchoSeaBar', 'rsEchoRainBar', 'rsEchoGainValue', 'rsEchoSeaValue', 'rsEchoRainValue',
    'rsCursorText', 'rsStbyOverlay', 'rsEbl1', 'rsEbl2', 'rsVrm1', 'rsVrm2',
    'rsEblNudgeL', 'rsEblNudgeR', 'rsVrmNudgeL', 'rsVrmNudgeR',
    'rsTrailsValue', 'rsBrillValue',
    'rsDateTime', 'rsOsHdg', 'rsOsCog', 'rsOsSog', 'rsOsPosn',
    'rsTargetBox', 'rsCpaValue', 'rsTcpaValue', 'rsCpaUp', 'rsCpaDown', 'rsTcpaUp', 'rsTcpaDown',
    'rsVecTime', 'rsVecMode', 'rsAlertList', 'rsAlertCount', 'rsGuidance',
  ]) els[name] = byId(name);

  let socket = null;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  let destroyed = false;
  let drag = null;
  let latestTargets = [];
  let guidanceText = TEXT.connecting;
  const videoBuffer = new RadarVideoBuffer();
  let videoQueue = Promise.resolve();
  let lastVideoKey = null;
  let streamKey = null;
  const trailHistory = [];
  const videoCanvas = typeof document === 'undefined' ? null : document.createElement('canvas');

  /* ── guidance ─────────────────────────── */
  function guidance(text) {
    guidanceText = text;
    if (els.rsGuidance) els.rsGuidance.textContent = text;
  }

  /* ── palette (Q14) ────────────────────── */
  const paletteColors = () => paletteVars(state.palette);
  const PALETTE_SHORT = { 'day-gry': 'D-G', 'dusk-blu': 'D-B', 'night-gry': 'N-G' };
  function applyPalette() {
    root.dataset.palette = state.palette;
    if (els.rsBtnBrill) {
      els.rsBtnBrill.dataset.value = state.palette;
      els.rsBtnBrill.setAttribute('aria-label', `BRILL 调色板 ${state.palette.toUpperCase()}，点击切换`);
    }
    if (els.rsBrillValue) els.rsBrillValue.textContent = PALETTE_SHORT[state.palette] ?? state.palette;
  }
  function cyclePalette() {
    const index = PALETTE_NAMES.indexOf(state.palette);
    state.palette = PALETTE_NAMES[(index + 1) % PALETTE_NAMES.length];
    applyPalette();
    guidance(`BRILL 调色板 ${state.palette.toUpperCase()}`);
  }

  /* ── TX / STBY (Q11) ──────────────────── */
  function isStandby() {
    return !state.session || !state.hasRadar || state.controls.standby;
  }
  function syncTxButton() {
    if (!els.rsTx) return;
    const standby = isStandby();
    els.rsTx.dataset.state = standby ? 'standby' : 'tx';
    els.rsTx.setAttribute('aria-pressed', String(!standby));
    els.rsTx.setAttribute('aria-label', standby ? '雷达待机 STBY，点击发射' : '雷达发射 TX，点击待机');
    if (els.rsTxRing) els.rsTxRing.dataset.state = standby ? 'standby' : 'tx';
    if (els.rsTxLabel) els.rsTxLabel.textContent = standby ? 'STBY' : 'TX';
    if (els.rsStbyOverlay) {
      els.rsStbyOverlay.hidden = !standby;
      els.rsStbyOverlay.textContent = 'RADAR STBY';
    }
  }
  function toggleStandby() {
    if (!state.session) { guidance(TEXT.noSession); return; }
    const next = !state.controls.standby;
    controls.post({ standby: next }, { immediate: true });
    state.controls.standby = next;
    syncTxButton();
    guidance(next ? TEXT.standby : TEXT.tx);
  }

  /* ── radar_controls POST channel (frozen contract) ── */
  let descriptorSink = () => {};
  let pendingPosts = Promise.resolve();
  let coalesceTimer = null;
  let queuedPatch = {};
  function dispatchPost() {
    const body = queuedPatch;
    queuedPatch = {};
    if (!Object.keys(body).length) return pendingPosts;
    pendingPosts = pendingPosts.then(async () => {
      try {
        const response = await fetch(`/api/sessions/${encodeURIComponent(state.session)}/radar_controls`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw new Error(`${response.status}${detail?.detail ? ` ${detail.detail}` : ''}`);
        }
        const payload = await response.json();
        if (payload?.radar_ppi) descriptorSink(payload.radar_ppi);
      } catch (error) {
        guidance(`radar_controls 拒绝：${error.message}`);
      }
    });
    return pendingPosts;
  }
  const controls = {
    /** `immediate` sends now (buttons); otherwise coalesces slider input. */
    post(patch, { immediate = false } = {}) {
      queuedPatch = { ...queuedPatch, ...patch };
      if (immediate) {
        if (coalesceTimer !== null) { clearTimeout(coalesceTimer); coalesceTimer = null; }
        return dispatchPost();
      }
      if (coalesceTimer === null) {
        coalesceTimer = setTimeout(() => { coalesceTimer = null; dispatchPost(); }, 150);
      }
      return pendingPosts;
    },
  };

  /* ── GAIN/SEA/RAIN flyout (Q5/Q10) ────── */
  const ADJUST_CHANNELS = {
    gain: { key: 'gainDb', post: 'gain_db', min: -20, max: 20, step: 1, unit: 'GAIN', label: 'GAIN' },
    sea: { key: 'sea', post: 'sea_suppression', min: 0, max: 100, step: 1, unit: 'SEA MAN', label: 'SEA' },
    rain: { key: 'rain', post: 'rain_suppression', min: 0, max: 100, step: 1, unit: 'RAIN MAN', label: 'RAIN' },
  };
  let adjustChannel = null;
  function syncAdjustExpanded() {
    for (const [button, name] of [[els.rsBtnGain, 'gain'], [els.rsBtnSea, 'sea'], [els.rsBtnRain, 'rain']]) {
      button?.setAttribute('aria-expanded', String(adjustChannel === name && !els.rsAdjustPanel?.hidden));
    }
  }
  function openAdjust(channelName) {
    const channel = ADJUST_CHANNELS[channelName];
    if (!channel || !els.rsAdjustPanel) return;
    if (adjustChannel === channelName && !els.rsAdjustPanel.hidden) {
      els.rsAdjustPanel.hidden = true;
      adjustChannel = null;
      syncAdjustExpanded();
      return;
    }
    adjustChannel = channelName;
    syncAdjustExpanded();
    els.rsAdjustPanel.hidden = false;
    els.rsAdjustTitle.textContent = channel.label;
    els.rsAdjustSlider.min = String(channel.min);
    els.rsAdjustSlider.max = String(channel.max);
    els.rsAdjustSlider.step = String(channel.step);
    els.rsAdjustSlider.value = String(state.controls[channel.key]);
    els.rsAdjustValue.textContent = `${state.controls[channel.key]}${channel.unit}`;
    els.rsAdjustSlider.setAttribute('aria-label', `${channel.label} 调节（${channel.min}..${channel.max}）`);
  }
  function syncAdjustPanel() {
    if (!adjustChannel || !els.rsAdjustPanel || els.rsAdjustPanel.hidden) return;
    const channel = ADJUST_CHANNELS[adjustChannel];
    if (document.activeElement !== els.rsAdjustSlider) {
      els.rsAdjustSlider.value = String(state.controls[channel.key]);
    }
    els.rsAdjustValue.textContent = `${state.controls[channel.key]}${channel.unit}`;
  }
  function onAdjustInput() {
    if (!adjustChannel) return;
    const channel = ADJUST_CHANNELS[adjustChannel];
    const value = Number(els.rsAdjustSlider.value);
    state.controls[channel.key] = value;
    els.rsAdjustValue.textContent = `${value}${channel.unit}`;
    syncEchoBox();
    controls.post({ [channel.post]: value });
    guidance(`${channel.label} ${value}`);
  }
  function syncEchoBox() {
    const bars = [
      [els.rsEchoGainBar, els.rsEchoGainValue, state.controls.gainDb, -20, 20],
      [els.rsEchoSeaBar, els.rsEchoSeaValue, state.controls.sea, 0, 100],
      [els.rsEchoRainBar, els.rsEchoRainValue, state.controls.rain, 0, 100],
    ];
    for (const [bar, valueEl, value, min, max] of bars) {
      if (!bar) continue;
      bar.style.setProperty('--fraction', Math.max(0, Math.min(1, (value - min) / (max - min))).toFixed(3));
      if (valueEl) valueEl.textContent = `${Math.round(value)}`;
    }
  }

  /* ── descriptor readback ──────────────── */
  function onDescriptor(descriptor) {
    if (!descriptor || typeof descriptor !== 'object') return;
    state.descriptor = descriptor;
    const scales = Array.isArray(descriptor.range_scales_nm) && descriptor.range_scales_nm.length
      ? descriptor.range_scales_nm
      : FURUNO_RANGE_TABLE.map(entry => entry.nm);
    state.hasRadar = true;
    const readback = syncControlsFromDescriptor(descriptor, state.controls);
    if (readback) state.controls = readback;
    if (Number.isFinite(Number(descriptor.range_scale_nm)) && scales.includes(Number(descriptor.range_scale_nm))) {
      state.rangeNm = Number(descriptor.range_scale_nm);
    }
    if (!scales.includes(state.rangeNm)) state.rangeNm = Number(descriptor.range_scale_nm ?? scales[0]);
    syncRangeBox();
    syncTxButton();
    syncEchoBox();
    syncAdjustPanel();
  }
  descriptorSink = onDescriptor;

  /* ── range (Q9) ───────────────────────── */
  function syncRangeBox() {
    if (els.rsRangeLabel) els.rsRangeLabel.textContent = formatRangeBox(state.rangeNm);
    if (els.rsRangeUp) els.rsRangeUp.setAttribute('aria-label', `量程增大，当前 ${state.rangeNm} 海里`);
    if (els.rsRangeDown) els.rsRangeDown.setAttribute('aria-label', `量程减小，当前 ${state.rangeNm} 海里`);
  }
  function stepRange(direction) {
    if (!state.session || !state.hasRadar) { guidance(TEXT.standby); return; }
    state.rangeNm = stepRangeNm(state.rangeNm, direction);
    controls.post({ range_nm: state.rangeNm }, { immediate: true });
    syncRangeBox();
    guidance(`量程 ${formatRangeBox(state.rangeNm)}`);
  }

  /* ── trails / HL / reset / marks / brill ─ */
  function cycleTrails() {
    state.trails = stepTrails(state.trails.key);
    if (els.rsBtnTrails) {
      els.rsBtnTrails.dataset.value = state.trails.key;
      els.rsBtnTrails.setAttribute('aria-label', `TRAILS 余辉 ${state.trails.label}，点击切换`);
    }
    if (els.rsTrailsValue) els.rsTrailsValue.textContent = state.trails.label;
    guidance(`TRAILS ${state.trails.label}`);
  }
  function setHlOff(active) {
    state.hlOff = active;
    if (els.rsBtnHl) els.rsBtnHl.setAttribute('aria-pressed', String(active));
    guidance(active ? 'HL OFF：艏线/量程圈/本船符号隐藏' : 'HL 恢复');
  }
  function resetMotion() {
    state.centerOffsetN = 0;
    state.centerOffsetE = 0;
    const own = ownshipFromEnvelope(state.envelope);
    state.motionOrigin = [own.north, own.east];
    guidance('CU/TM RESET：回中');
  }
  function anyMarkOn() {
    return state.marks.vrm.some(mark => mark.on) || state.marks.ebl.some(mark => mark.on);
  }
  function toggleMarks() {
    const anyOn = anyMarkOn();
    for (const mark of state.marks.vrm) mark.on = !anyOn;
    for (const mark of state.marks.ebl) mark.on = !anyOn;
    state.marks.active = anyOn ? null : 'vrm0';
    if (els.rsBtnMarks) els.rsBtnMarks.setAttribute('aria-pressed', String(!anyOn));
    guidance(anyOn ? 'VRM/EBL 全关' : 'VRM/EBL 全开：读数行点选活动标记');
    syncMarkReadouts();
  }
  function activateMark(kind, index) {
    const mark = state.marks[kind]?.[index];
    if (!mark) return;
    mark.on = true;
    state.marks.active = `${kind}${index}`;
    syncMarkReadouts();
    guidance(`${kind.toUpperCase()}${index + 1} 激活：PPI 拖拽或箭头钮调整`);
  }
  function nudgeMark(kind, direction) {
    let index = state.marks.active?.startsWith(kind) ? Number(state.marks.active.slice(kind.length)) : -1;
    if (!(index >= 0) || !state.marks[kind][index].on) {
      index = state.marks[kind].findIndex(mark => mark.on);
    }
    if (index < 0) { guidance(`无活动的 ${kind.toUpperCase()}：读数行点选开启`); return; }
    state.marks.active = `${kind}${index}`;
    const mark = state.marks[kind][index];
    if (kind === 'vrm') {
      mark.nm = Math.max(0.02, Math.min(state.rangeNm * 2, mark.nm + direction * Math.max(0.01, state.rangeNm / 200)));
    } else {
      mark.trueDeg = wrapAngleDeg(mark.trueDeg + direction * 0.5);
    }
    syncMarkReadouts();
  }
  function syncMarkReadouts() {
    const relative = state.presentation.headingUp || state.presentation.courseUp;
    const refDeg = referenceDeg();
    const entries = [
      [els.rsEbl1, state.marks.ebl[0], 'ebl', 0, () => formatEbl(state.marks.ebl[0].trueDeg, refDeg, relative)],
      [els.rsEbl2, state.marks.ebl[1], 'ebl', 1, () => formatEbl(state.marks.ebl[1].trueDeg, refDeg, relative)],
      [els.rsVrm1, state.marks.vrm[0], 'vrm', 0, () => formatVrm(state.marks.vrm[0].nm)],
      [els.rsVrm2, state.marks.vrm[1], 'vrm', 1, () => formatVrm(state.marks.vrm[1].nm)],
    ];
    for (const [element, mark, kind, index, format] of entries) {
      if (!element) continue;
      const text = mark.on ? format() : '---';
      element.textContent = text;
      const active = state.marks.active === `${kind}${index}`;
      element.dataset.active = String(active);
      element.setAttribute('aria-pressed', String(active));
      element.setAttribute('aria-label', `${kind.toUpperCase()}${index + 1} ${text}，点击激活`);
    }
  }

  /* ── presentation mode ────────────────── */
  function referenceDeg() {
    const own = ownshipFromEnvelope(state.envelope);
    const source = state.presentation.courseUp ? own.courseRad : own.headingRad;
    return wrapAngleDeg(source * 180 / Math.PI);
  }
  function cyclePresentation() {
    state.presentation = stepPresentationMode(state.presentation.key);
    if (state.presentation.trueMotion) resetMotion();
    if (els.rsModeLabel) els.rsModeLabel.textContent = state.presentation.label;
    syncMarkReadouts();
    guidance(`PRESENTATION ${state.presentation.label}`);
  }

  /* ── TT/AIS settings (Q12 block 4) ────── */
  function setLimits({ cpaLimitNm, tcpaLimitMin }) {
    state.cpaLimitNm = Math.max(0.5, Math.min(6, cpaLimitNm ?? state.cpaLimitNm));
    state.tcpaLimitMin = Math.max(1, Math.min(15, tcpaLimitMin ?? state.tcpaLimitMin));
    if (els.rsCpaValue) els.rsCpaValue.textContent = `${state.cpaLimitNm.toFixed(1)}NM`;
    if (els.rsTcpaValue) els.rsTcpaValue.textContent = `${state.tcpaLimitMin}MIN`;
    refreshTargets();
    guidance(`CPA ${state.cpaLimitNm.toFixed(1)}NM / TCPA ${state.tcpaLimitMin}MIN`);
  }
  function cycleVectorMode() {
    state.vectorMode = state.vectorMode === 'TRUE-G' ? 'REL' : 'TRUE-G';
    if (els.rsVecMode) els.rsVecMode.textContent = state.vectorMode;
    guidance(`矢量基准 ${state.vectorMode}`);
  }
  function cycleVectorTime() {
    state.vectorTimeMin = stepVectorTime(state.vectorTimeMin);
    if (els.rsVecTime) els.rsVecTime.textContent = `${state.vectorTimeMin}MIN`;
    guidance(`矢量时间 ${state.vectorTimeMin}MIN`);
  }

  /* ── alerts (Q12 block 5) ─────────────── */
  function syncAlerts() {
    if (!els.rsAlertList) return;
    const alerts = activeAlerts(latestTargets);
    els.rsAlertList.textContent = '';
    if (!alerts.length) {
      const empty = document.createElement('p');
      empty.className = 'rs-alert-empty';
      empty.textContent = 'NO ACTIVE ALERTS';
      els.rsAlertList.appendChild(empty);
    }
    for (const alert of alerts) {
      const row = document.createElement('div');
      row.className = `rs-alert-row level-${alert.level}`;
      row.dataset.acked = String(state.acknowledged.has(alert.id));
      const label = document.createElement('span');
      label.className = 'rs-alert-label';
      label.textContent = alert.label;
      const ack = document.createElement('button');
      ack.type = 'button';
      ack.className = 'rs-alert-ack';
      ack.textContent = state.acknowledged.has(alert.id) ? 'ACKED' : 'ACK';
      ack.setAttribute('aria-label', `确认报警 ${alert.label}`);
      ack.addEventListener('click', () => {
        state.acknowledged.add(alert.id);
        syncAlerts();
        guidance(`报警确认：${alert.label}`);
      });
      row.append(label, ack);
      els.rsAlertList.appendChild(row);
    }
    if (els.rsAlertCount) els.rsAlertCount.textContent = `${alerts.length}`;
  }

  /* ── target data box (Q12 block 3) ────── */
  function syncTargetBox() {
    if (!els.rsTargetBox) return;
    const selected = state.selected
      ? latestTargets.find(target => target.type === state.selected.type && target.id === state.selected.id)
      : null;
    els.rsTargetBox.textContent = '';
    if (!selected) {
      const empty = document.createElement('p');
      empty.className = 'rs-target-empty';
      empty.textContent = '点击 PPI 目标显示数据';
      els.rsTargetBox.appendChild(empty);
      return;
    }
    const grid = document.createElement('dl');
    grid.className = 'rs-target-grid';
    const field = (labelText, valueText) => {
      const dt = document.createElement('dt');
      dt.textContent = labelText;
      const dd = document.createElement('dd');
      dd.textContent = valueText;
      grid.append(dt, dd);
    };
    const relative = state.presentation.headingUp || state.presentation.courseUp;
    field('TGT', selected.label);
    field('BRG', `${formatBearing(selected.bearingRad * 180 / Math.PI)}${relative ? 'R' : 'T'}`);
    field('RNG', `${(selected.rangeM / N_METERS_PER_NM).toFixed(2)}NM`);
    field('COG', `${formatBearing(selected.cogRad * 180 / Math.PI)}T`);
    field('SOG', `${(selected.sogMps * 1.943844).toFixed(1)}KT`);
    field('CPA', `${(selected.cpaM / N_METERS_PER_NM).toFixed(2)}NM`);
    field('TCPA', selected.tcpaS >= 0 ? `${(selected.tcpaS / 60).toFixed(1)}MIN` : 'PASSED');
    field('BCR', selected.bcrBct.bcrM === null ? '***.*' : `${(selected.bcrBct.bcrM / N_METERS_PER_NM).toFixed(2)}NM`);
    field('BCT', selected.bcrBct.bctS === null ? '***.*' : `${(selected.bcrBct.bctS / 60).toFixed(1)}MIN`);
    els.rsTargetBox.appendChild(grid);
  }

  /* ── ownship + clock blocks ───────────── */
  function syncInfoBlocks() {
    const os = state.envelope?.os ?? {};
    const deg = rad => `${formatBearing(((rad * 180 / Math.PI) % 360 + 360) % 360)}°`;
    if (els.rsOsHdg) els.rsOsHdg.textContent = Number.isFinite(os.psi) ? deg(os.psi) : '---';
    if (els.rsOsCog) els.rsOsCog.textContent = Number.isFinite(os.cog) ? deg(os.cog) : '---';
    if (els.rsOsSog) els.rsOsSog.textContent = Number.isFinite(os.sog) ? `${(os.sog * 1.943844).toFixed(1)}KT` : '---';
    if (els.rsOsPosn) {
      els.rsOsPosn.textContent = Number.isFinite(os.latitude) ? formatLatLon(os.latitude, os.longitude) : '---';
    }
    if (els.rsDateTime) els.rsDateTime.textContent = formatUtcStamp(state.envelope?.ais_utc ?? null) ?? '---';
  }

  /* ── envelope intake ──────────────────── */
  function handleEnvelope(envelope) {
    if (!envelope || typeof envelope !== 'object') return;
    if (envelope?.error === 'session_not_found') {
      state.envelope = null;
      state.hasRadar = false;
      syncTxButton();
      guidance(TEXT.noSession);
      return;
    }
    state.envelope = envelope;
    onDescriptor(envelope.radar_ppi);
    if (state.motionOrigin === null) {
      const own = ownshipFromEnvelope(envelope);
      state.motionOrigin = [own.north, own.east];
    }
    refreshTargets();
    const scan = (envelope.radar_scans ?? []).find(item => item?.sensor_label === 'radar_x');
    const video = scan?.shadow_video;
    const stream = `${envelope.run_id ?? ''}:${scan?.sensor_instance_id ?? ''}`;
    if (stream !== streamKey) {
      streamKey = stream;
      videoBuffer.clear();
      lastVideoKey = null;
      trailHistory.length = 0;
    }
    if (scan?.status === 'STANDBY') {
      state.controls.standby = true;
      state.videoStatus = 'STANDBY';
      syncTxButton();
    } else if (video) {
      const key = `${streamKey}:${scan?.sample_seq}:${video?.chunk?.sha256}`;
      if (key !== lastVideoKey) {
        lastVideoKey = key;
        // Decode runs detached from the rAF loop so a checkpoint fetch never
        // blocks the 60 fps redraw path.
        videoQueue = videoQueue.then(async () => {
          await videoBuffer.apply(video);
          state.videoStatus = videoBuffer.status;
          if (state.controls.standby) {
            state.controls.standby = false;
            syncTxButton();
          }
        }).catch(() => {
          state.videoStatus = 'INVALID_VIDEO';
          guidance('雷达回波数据异常');
        });
      }
    }
  }

  function refreshTargets() {
    latestTargets = state.envelope
      ? buildScreenTargets(state.envelope, { cpaLimitNm: state.cpaLimitNm, tcpaLimitMin: state.tcpaLimitMin })
      : [];
    syncAlerts();
    syncTargetBox();
    syncInfoBlocks();
  }

  /* ── PPI drawing ──────────────────────── */
  function wrapAngleDeg(deg) {
    return ((deg % 360) + 360) % 360;
  }

  function prepareCanvas() {
    const width = canvas.clientWidth || 640;
    const height = canvas.clientHeight || 640;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { width, height };
  }

  function drawGeometry() {
    const own = ownshipFromEnvelope(state.envelope);
    const rotation = state.presentation.headingUp ? own.headingRad
      : (state.presentation.courseUp ? own.courseRad : 0);
    const rangeM = state.rangeNm * N_METERS_PER_NM;
    let ownToCenterN = 0;
    let ownToCenterE = 0;
    if (state.presentation.trueMotion) {
      ownToCenterN = state.motionOrigin[0] - own.north;
      ownToCenterE = state.motionOrigin[1] - own.east;
      if (Math.hypot(ownToCenterN, ownToCenterE) > rangeM * 0.75) {
        state.motionOrigin = [own.north, own.east];
        ownToCenterN = 0;
        ownToCenterE = 0;
      }
    } else {
      ownToCenterN = state.centerOffsetN;
      ownToCenterE = state.centerOffsetE;
    }
    return { ...own, rotation, rangeM, ownToCenterN, ownToCenterE };
  }

  function screenTransform(geometry, centerX, centerY, bezel) {
    const { rotation, rangeM, ownToCenterN, ownToCenterE } = geometry;
    const cos = Math.cos(rotation);
    const sin = Math.sin(rotation);
    return (northRel, eastRel) => {
      const qN = northRel - ownToCenterN;
      const qE = eastRel - ownToCenterE;
      const rN = qN * cos + qE * sin;
      const rE = -qN * sin + qE * cos;
      return {
        x: centerX + (rE / rangeM) * bezel,
        y: centerY - (rN / rangeM) * bezel,
        inside: Math.hypot(rN, rE) <= rangeM,
      };
    };
  }

  function shipScreenPos(geometry, centerX, centerY, bezel) {
    // Ownship sits opposite the view center: q = (0,0) - ownToCenter.
    const cos = Math.cos(geometry.rotation);
    const sin = Math.sin(geometry.rotation);
    const rN = -(geometry.ownToCenterN * cos + geometry.ownToCenterE * sin);
    const rE = geometry.ownToCenterN * sin - geometry.ownToCenterE * cos;
    return {
      x: centerX + (rE / geometry.rangeM) * bezel,
      y: centerY - (rN / geometry.rangeM) * bezel,
    };
  }

  function bezelRadius(width, height) {
    return Math.min(width || canvas.clientWidth || 640, height || canvas.clientHeight || 640) / 2 - 30;
  }

  function pushTrailHistory(points, simTime) {
    if (state.trails.seconds <= 0) {
      trailHistory.length = 0;
      return;
    }
    trailHistory.push({ simTime, points });
    while (trailHistory.length > 0 && simTime - trailHistory[0].simTime > state.trails.seconds) trailHistory.shift();
    while (trailHistory.length > 240) trailHistory.shift();
  }

  function drawTrailHistory(project, colors, simTime) {
    const maxAgeS = state.trails.seconds;
    if (maxAgeS <= 0) return;
    for (const frame of trailHistory) {
      const age = simTime - frame.simTime;
      if (age < 0 || age > maxAgeS) continue;
      const fade = Math.max(0.08, 1 - age / maxAgeS);
      ctx.fillStyle = hexToRgba(colors.echo, 0.16 + 0.4 * fade);
      for (const point of frame.points) {
        const { northRel, eastRel } = relativePos(state.envelope, point);
        const projected = project(northRel, eastRel);
        if (!projected.inside) continue;
        const size = 1 + 1.4 * point.intensity;
        ctx.fillRect(projected.x, projected.y, size, size);
      }
    }
  }

  function drawOwnshipSymbol(shipX, shipY, screenHeadingRad, colors) {
    ctx.save();
    ctx.translate(shipX, shipY);
    ctx.rotate(screenHeadingRad);
    ctx.fillStyle = colors.text;
    ctx.strokeStyle = colors.border;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, -10);
    ctx.lineTo(4, -2);
    ctx.lineTo(3, 9);
    ctx.lineTo(-3, 9);
    ctx.lineTo(-4, -2);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function drawVector(project, target, colors, fromPoint) {
    const lengthM = state.vectorTimeMin * 60 * target.sogMps;
    if (lengthM <= 0) return;
    let heading = target.cogRad;
    if (state.vectorMode === 'REL') {
      const own = ownshipFromEnvelope(state.envelope);
      const os = state.envelope?.os ?? {};
      const ownSog = Number.isFinite(os.sog) ? os.sog : 0;
      heading = Math.atan2(
        target.sogMps * Math.sin(target.cogRad) - ownSog * Math.sin(own.courseRad),
        target.sogMps * Math.cos(target.cogRad) - ownSog * Math.cos(own.courseRad),
      );
    }
    const { northRel, eastRel } = relativePos(state.envelope, target);
    const end = project(northRel + Math.cos(heading) * lengthM, eastRel + Math.sin(heading) * lengthM);
    ctx.strokeStyle = target.threat === 'dangerous' ? colors.alarm : colors.targetVector;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(fromPoint.x, fromPoint.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
  }

  function drawAisTriangle(point, screenHeadingRad, color, lineWidth, size) {
    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(screenHeadingRad);
    ctx.strokeStyle = color;
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size * 0.8, size);
    ctx.lineTo(-size * 0.8, size);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function drawTargets(project, geometry) {
    const colors = paletteColors();
    const blinkOn = Math.floor(performance.now() / 450) % 2 === 0;
    for (const target of latestTargets) {
      const { northRel, eastRel } = relativePos(state.envelope, target);
      const point = project(northRel, eastRel);
      if (!point.inside) continue;
      const selected = state.selected?.type === target.type && state.selected?.id === target.id;
      const symbol = targetSymbolState({
        threat: target.threat,
        selected,
        lost: Boolean(target.lost),
        acknowledged: state.acknowledged.has(`cpa:${target.type}:${target.id}`)
          || state.acknowledged.has(`lost:${target.type}:${target.id}`),
      });
      if (symbol.flashing && !blinkOn) continue;
      const color = colors[symbol.color] ?? colors.target;
      if (target.type === 'tt') {
        // Furuno TT (digest §6): solid circle = stable track + speed vector.
        ctx.strokeStyle = color;
        ctx.lineWidth = symbol.kind === 'dangerous' ? 2.2 : 1.4;
        ctx.beginPath();
        ctx.arc(point.x, point.y, 7, 0, TWO_PI);
        ctx.stroke();
        drawVector(project, target, colors, point);
        if (selected) {
          // Dashed square = selected target.
          ctx.setLineDash([4, 3]);
          ctx.strokeStyle = colors.selection;
          ctx.strokeRect(point.x - 11, point.y - 11, 22, 22);
          ctx.setLineDash([]);
        }
      } else {
        // AIS (digest §6 + SIMRAD digest §5): small triangle = sleeping,
        // large thick triangle + vector + heading line = active, red thick
        // flashing = dangerous.
        const active = target.aisState === 'active';
        const headingRad = Number.isFinite(target.headingRad) ? target.headingRad : target.cogRad;
        drawAisTriangle(point, headingRad - geometry.rotation, color,
          symbol.kind === 'dangerous' ? 2.4 : (active ? 1.8 : 1), active ? 8 : 5);
        if (active) {
          drawVector(project, target, colors, point);
          ctx.strokeStyle = hexToRgba(colors.ais, 0.8);
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(point.x, point.y);
          const end = project(
            northRel + Math.cos(headingRad) * 26,
            eastRel + Math.sin(headingRad) * 26,
          );
          ctx.lineTo(end.x, end.y);
          ctx.stroke();
        }
        if (selected) {
          ctx.setLineDash([4, 3]);
          ctx.strokeStyle = colors.selection;
          ctx.strokeRect(point.x - 11, point.y - 11, 22, 22);
          ctx.setLineDash([]);
        }
      }
    }
  }

  function drawMarks(project, geometry) {
    const colors = paletteColors();
    for (let i = 0; i < 2; i += 1) {
      const vrm = state.marks.vrm[i];
      const ebl = state.marks.ebl[i];
      const active = state.marks.active === `vrm${i}` || state.marks.active === `ebl${i}`;
      if (vrm.on) {
        // VRM x2 dashed rings (VRM2 segments longer), max = 2x range.
        ctx.setLineDash(i === 0 ? [5, 5] : [9, 4]);
        ctx.strokeStyle = colors.vrm;
        ctx.lineWidth = active ? 2 : 1.2;
        const ship = project(0, 0);
        ctx.beginPath();
        ctx.arc(ship.x, ship.y, bezelRadius() * Math.min(vrm.nm, state.rangeNm * 2) / state.rangeNm, 0, TWO_PI);
        ctx.stroke();
      }
      if (ebl.on) {
        // EBL x2 dashed rays (EBL2 longer) with an offset-capable origin.
        // The stored bearing is always TRUE; the °R readout is display-only.
        ctx.setLineDash(i === 0 ? [5, 5] : [9, 4]);
        ctx.strokeStyle = colors.ebl;
        ctx.lineWidth = active ? 2 : 1.2;
        const bearing = ebl.trueDeg * Math.PI / 180 - geometry.rotation;
        const origin = project(ebl.offsetN, ebl.offsetE);
        const dx = Math.sin(bearing);
        const dy = -Math.cos(bearing);
        ctx.beginPath();
        ctx.moveTo(origin.x, origin.y);
        ctx.lineTo(origin.x + dx * bezelRadius() * 2, origin.y + dy * bezelRadius() * 2);
        ctx.stroke();
        // EBL origin tick = the OFFSET drag handle.
        ctx.setLineDash([]);
        ctx.lineWidth = active ? 2.4 : 1.6;
        ctx.beginPath();
        ctx.moveTo(origin.x - dy * 5, origin.y + dx * 5);
        ctx.lineTo(origin.x + dy * 5, origin.y - dx * 5);
        ctx.stroke();
      }
    }
    ctx.setLineDash([]);
  }

  function radarAriaLabel(standby) {
    if (!state.session) return '雷达屏待机：URL 缺少 session 参数';
    if (standby) return '雷达屏 STANDBY 待机';
    return `船载雷达 PPI，${state.presentation.label}，量程 ${state.rangeNm} 海里，`
      + `TT ${latestTargets.filter(target => target.type === 'tt').length}，`
      + `AIS ${latestTargets.filter(target => target.type === 'ais').length}，视频 ${state.videoStatus}`;
  }

  function draw() {
    if (destroyed || !ctx) return;
    const { width, height } = prepareCanvas();
    const colors = paletteColors();
    const geometry = drawGeometry();
    const centerX = width / 2;
    const centerY = height / 2;
    const bezel = bezelRadius(width, height);
    const project = screenTransform(geometry, centerX, centerY, bezel);
    const ship = shipScreenPos(geometry, centerX, centerY, bezel);
    ctx.clearRect(0, 0, width, height);

    // PPI disc: pure black in every palette (Q14).
    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, centerY, bezel, 0, TWO_PI);
    ctx.fillStyle = '#000';
    ctx.fill();
    ctx.clip();

    const standby = isStandby();
    const simTime = Number.isFinite(Number(state.envelope?.sim_time)) ? Number(state.envelope.sim_time) : 0;
    const scanPeriodS = state.descriptor.scan_period_s ?? 2.5;
    const sweepRad = sweepAzimuthRad(simTime, scanPeriodS) - geometry.rotation;

    if (!standby) {
      // Recorded video raster (decoded checkpoint); trails on when != OFF.
      if (videoBuffer.data && videoBuffer.status === 'SHADOW' && videoCanvas) {
        const pixels = Math.max(64, Math.round(bezel * 2));
        videoCanvas.width = pixels;
        videoCanvas.height = pixels;
        const vctx = videoCanvas.getContext('2d');
        const raster = vctx.createImageData(pixels, pixels);
        raster.data.set(videoBuffer.raster(pixels, {
          rangeScaleM: geometry.rangeM,
          ownshipNorth: geometry.ownNorth + geometry.ownToCenterN,
          ownshipEast: geometry.ownEast + geometry.ownToCenterE,
          simTimeS: simTime,
          scanPeriodS,
          ownshipHeadingRad: geometry.headingRad,
          ownshipCourseRad: geometry.courseRad,
        }, {
          headingUp: state.presentation.headingUp,
          courseUp: state.presentation.courseUp,
          gain: state.controls.gainDb * 2,
          sea: state.controls.sea,
          rain: state.controls.rain,
          trails: state.trails.seconds > 0,
        }));
        vctx.putImageData(raster, 0, 0);
        ctx.drawImage(videoCanvas, centerX - bezel, centerY - bezel, bezel * 2, bezel * 2);
      } else {
        // Deterministic regenerated clutter (radar-ppi.js pure function),
        // dimmed locally by A/C SEA + A/C RAIN (Q5) and trailed.
        const scanIndex = scanPeriodS > 0 ? Math.floor(simTime / scanPeriodS) : 0;
        const clutter = clutterPoints({
          seed: state.descriptor.seed ?? 0,
          scanIndex,
          rangeScaleM: geometry.rangeM,
          descriptor: state.descriptor,
        });
        const points = clutter.map(point => ({
          north: geometry.ownNorth + Math.cos(point.azimuthRad) * point.rangeM,
          east: geometry.ownEast + Math.sin(point.azimuthRad) * point.rangeM,
          intensity: point.intensity
            * clutterSuppressionFactor(point.rangeM, state.controls.sea, state.controls.rain),
        }));
        pushTrailHistory(points, simTime);
        drawTrailHistory(project, colors, simTime);

        // Point blips from the named backend scan when video is absent.
        const scan = (state.envelope?.radar_scans ?? []).find(item => item?.sensor_label === 'radar_x');
        if (Array.isArray(scan?.display_returns)) {
          const blips = [];
          for (const measurement of scan.display_returns) {
            if (!Number.isFinite(measurement?.north_m) || !Number.isFinite(measurement?.east_m)) continue;
            blips.push({
              north: measurement.north_m,
              east: measurement.east_m,
              intensity: Math.max(0.08, Math.min(1, measurement.confidence ?? 0)),
            });
          }
          pushTrailHistory(blips, simTime);
        }

        // CFAR detection crosses when the video layer carries them.
        for (const detection of scan?.shadow_video?.detections ?? []) {
          if (!Number.isFinite(detection?.north_m) || !Number.isFinite(detection?.east_m)) continue;
          const { northRel, eastRel } = relativePos(state.envelope, detection);
          const point = project(northRel, eastRel);
          if (!point.inside) continue;
          ctx.strokeStyle = hexToRgba(colors.echo, 0.9);
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(point.x - 3, point.y);
          ctx.lineTo(point.x + 3, point.y);
          ctx.moveTo(point.x, point.y - 3);
          ctx.lineTo(point.x, point.y + 3);
          ctx.stroke();
        }
      }

      // Sweep afterglow wedge + rotating beam line. sweepRad is a compass
      // bearing; canvas angles run +90 deg off (0 = east), so convert once.
      const sweepCanvasRad = sweepRad - Math.PI / 2;
      const wedge = ctx.createLinearGradient(
        ship.x, ship.y,
        ship.x + Math.cos(sweepCanvasRad) * bezel, ship.y + Math.sin(sweepCanvasRad) * bezel,
      );
      wedge.addColorStop(0, hexToRgba(colors.sweep, 0.35));
      wedge.addColorStop(1, hexToRgba(colors.sweep, 0));
      ctx.beginPath();
      ctx.moveTo(ship.x, ship.y);
      ctx.arc(ship.x, ship.y, bezel, sweepCanvasRad - Math.PI / 5, sweepCanvasRad);
      ctx.closePath();
      ctx.fillStyle = wedge;
      ctx.fill();
      ctx.strokeStyle = colors.sweep;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(ship.x, ship.y);
      ctx.lineTo(ship.x + Math.cos(sweepCanvasRad) * bezel, ship.y + Math.sin(sweepCanvasRad) * bezel);
      ctx.stroke();

      drawTargets(project, geometry);
      drawMarks(project, geometry);

      // Range rings + heading line (hidden while HL OFF is held).
      if (!state.hlOff) {
        ctx.strokeStyle = hexToRgba(colors.ppiGrid, 0.9);
        ctx.lineWidth = 1;
        const entry = rangeEntry(state.rangeNm);
        const rings = entry ? entry.rings : 4;
        const ringNm = entry ? entry.ringNm : state.rangeNm / rings;
        for (let i = 1; i <= rings; i += 1) {
          ctx.beginPath();
          ctx.arc(ship.x, ship.y, bezel * (ringNm * i) / state.rangeNm, 0, TWO_PI);
          ctx.stroke();
        }
        const headingScreen = geometry.headingRad - geometry.rotation;
        ctx.strokeStyle = colors.text;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(ship.x, ship.y);
        ctx.lineTo(ship.x + Math.sin(headingScreen) * bezel, ship.y - Math.cos(headingScreen) * bezel);
        ctx.stroke();
        drawOwnshipSymbol(ship.x, ship.y, headingScreen, colors);
      }

      // Cursor crosshair.
      if (state.cursor) {
        ctx.strokeStyle = colors.cursor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(state.cursor.x - 6, state.cursor.y);
        ctx.lineTo(state.cursor.x + 6, state.cursor.y);
        ctx.moveTo(state.cursor.x, state.cursor.y - 6);
        ctx.lineTo(state.cursor.x, state.cursor.y + 6);
        ctx.stroke();
      }
    }
    ctx.restore();

    // Fixed bearing dial: 000-350 numbers every 10 degrees (digest §1),
    // rotating with the presentation mode (earth-fixed in NU, ship-fixed
    // in HU/CU).
    ctx.fillStyle = colors.ppiText;
    ctx.strokeStyle = hexToRgba(colors.ppiGrid, 0.8);
    ctx.lineWidth = 1;
    ctx.font = '10px "JetBrains Mono", ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.beginPath();
    ctx.arc(centerX, centerY, bezel, 0, TWO_PI);
    ctx.stroke();
    for (let deg = 0; deg < 360; deg += 10) {
      const angle = deg * Math.PI / 180 - geometry.rotation;
      const sin = Math.sin(angle);
      const cos = Math.cos(angle);
      ctx.beginPath();
      ctx.moveTo(centerX + sin * (bezel - (deg % 30 === 0 ? 6 : 3)), centerY - cos * (bezel - (deg % 30 === 0 ? 6 : 3)));
      ctx.lineTo(centerX + sin * (bezel + 2), centerY - cos * (bezel + 2));
      ctx.stroke();
      const labelRadius = bezel + 13;
      ctx.fillText(String(deg).padStart(3, '0'), centerX + sin * labelRadius, centerY - cos * labelRadius);
    }

    canvas.setAttribute('aria-label', radarAriaLabel(standby));
    canvas.setAttribute('data-radar-video-status', state.videoStatus);
    canvas.setAttribute('data-radar-range-nm', String(state.rangeNm));
    canvas.setAttribute('data-radar-mode', state.presentation.key);
  }

  /* ── cursor readout box ───────────────── */
  function cursorReadoutText(point) {
    const rect = canvas.getBoundingClientRect();
    const geometry = drawGeometry();
    const bezel = bezelRadius(rect.width, rect.height);
    const rE = (point.x - rect.width / 2) / bezel * geometry.rangeM;
    const rN = -(point.y - rect.height / 2) / bezel * geometry.rangeM;
    const cos = Math.cos(geometry.rotation);
    const sin = Math.sin(geometry.rotation);
    // Inverse of the screen rotation, then add back the view-center offset.
    const northRel = rN * cos - rE * sin + geometry.ownToCenterN;
    const eastRel = rN * sin + rE * cos + geometry.ownToCenterE;
    const rangeNm = Math.hypot(northRel, eastRel) / N_METERS_PER_NM;
    if (rangeNm > state.rangeNm) return 'OUT OF RANGE';
    const bearingDeg = wrapAngleDeg(Math.atan2(eastRel, northRel) * 180 / Math.PI);
    const relative = state.presentation.headingUp || state.presentation.courseUp;
    const bearingText = formatEbl(bearingDeg, referenceDeg(), relative);
    return `X ${(-eastRel / N_METERS_PER_NM).toFixed(2)}  Y ${(northRel / N_METERS_PER_NM).toFixed(2)}NM  ${bearingText} ${rangeNm.toFixed(2)}NM`;
  }

  /* ── pointer interaction ──────────────── */
  function canvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  function hitTest(point) {
    const rect = canvas.getBoundingClientRect();
    const geometry = drawGeometry();
    const bezel = bezelRadius(rect.width, rect.height);
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const cos = Math.cos(geometry.rotation);
    const sin = Math.sin(geometry.rotation);
    const ship = shipScreenPos(geometry, centerX, centerY, bezel);
    for (const target of latestTargets) {
      const { northRel, eastRel } = relativePos(state.envelope, target);
      const qN = northRel - geometry.ownToCenterN;
      const qE = eastRel - geometry.ownToCenterE;
      const x = centerX + ((-qN * sin + qE * cos) / geometry.rangeM) * bezel;
      const y = centerY - ((qN * cos + qE * sin) / geometry.rangeM) * bezel;
      if (Math.hypot(point.x - x, point.y - y) <= 13) return { kind: 'target', target };
    }
    for (let i = 1; i >= 0; i -= 1) {
      const ebl = state.marks.ebl[i];
      if (ebl.on) {
        const originN = ebl.offsetN - geometry.ownToCenterN;
        const originE = ebl.offsetE - geometry.ownToCenterE;
        const originX = centerX + ((-originN * sin + originE * cos) / geometry.rangeM) * bezel;
        const originY = centerY - ((originN * cos + originE * sin) / geometry.rangeM) * bezel;
        if (Math.hypot(point.x - originX, point.y - originY) <= 10) return { kind: 'eblOffset', index: i };
        const bearing = ebl.trueDeg * Math.PI / 180 - geometry.rotation;
        const dx = Math.sin(bearing);
        const dy = -Math.cos(bearing);
        const along = (point.x - originX) * dx + (point.y - originY) * dy;
        const across = Math.abs((point.x - originX) * dy - (point.y - originY) * dx);
        if (across <= 8 && along >= -10) return { kind: 'ebl', index: i };
      }
      const vrm = state.marks.vrm[i];
      if (vrm.on) {
        const ringRadius = bezel * Math.min(vrm.nm, state.rangeNm * 2) / state.rangeNm;
        if (Math.abs(Math.hypot(point.x - ship.x, point.y - ship.y) - ringRadius) <= 8) {
          return { kind: 'vrm', index: i };
        }
      }
    }
    if (Math.hypot(point.x - ship.x, point.y - ship.y) <= 16) return { kind: 'center' };
    return { kind: 'cursor' };
  }

  function onPointerDown(event) {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    const point = canvasPoint(event);
    const hit = hitTest(point);
    if (hit.kind === 'target') {
      state.selected = { type: hit.target.type, id: hit.target.id };
      state.acknowledged.delete(`cpa:${hit.target.type}:${hit.target.id}`);
      syncTargetBox();
      guidance(`选中 ${hit.target.label}：右侧目标数据框`);
      return;
    }
    if (hit.kind === 'center') {
      drag = { kind: 'center' };
      canvas.setPointerCapture(event.pointerId);
      guidance('OFF CENTER：拖拽偏心（≤75% 半径），CU/TM RESET 回中');
      return;
    }
    if (hit.kind === 'eblOffset') {
      drag = { kind: 'eblOffset', index: hit.index };
      state.marks.active = `ebl${hit.index}`;
      state.marks.ebl[hit.index].on = true;
      canvas.setPointerCapture(event.pointerId);
      guidance(`EBL${hit.index + 1} OFFSET：拖拽原点`);
      syncMarkReadouts();
      return;
    }
    if (hit.kind === 'ebl' || hit.kind === 'vrm') {
      drag = { kind: hit.kind, index: hit.index };
      state.marks.active = `${hit.kind}${hit.index}`;
      state.marks[hit.kind][hit.index].on = true;
      canvas.setPointerCapture(event.pointerId);
      guidance(`${hit.kind.toUpperCase()}${hit.index + 1} 拖拽调整`);
      syncMarkReadouts();
      return;
    }
    state.cursor = point;
    if (els.rsCursorText) els.rsCursorText.textContent = cursorReadoutText(point);
  }

  function onPointerMove(event) {
    const point = canvasPoint(event);
    if (!drag) {
      state.cursor = point;
      if (els.rsCursorText) els.rsCursorText.textContent = cursorReadoutText(point);
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const geometry = drawGeometry();
    const bezel = bezelRadius(rect.width, rect.height);
    if (drag.kind === 'center') {
      const rN = -(point.y - rect.height / 2) / bezel * geometry.rangeM;
      const rE = (point.x - rect.width / 2) / bezel * geometry.rangeM;
      const cos = Math.cos(geometry.rotation);
      const sin = Math.sin(geometry.rotation);
      const centerN = rN * cos - rE * sin;
      const centerE = rN * sin + rE * cos;
      const clamp = 0.75 * geometry.rangeM;
      const magnitude = Math.hypot(centerN, centerE);
      const scale = magnitude > clamp ? clamp / magnitude : 1;
      state.centerOffsetN = centerN * scale;
      state.centerOffsetE = centerE * scale;
      return;
    }
    if (drag.kind === 'vrm') {
      const geometryNow = drawGeometry();
      const rectNow = canvas.getBoundingClientRect();
      const ship = shipScreenPos(geometryNow, rectNow.width / 2, rectNow.height / 2, bezel);
      const nm = Math.hypot(point.x - ship.x, point.y - ship.y) / bezel * state.rangeNm;
      state.marks.vrm[drag.index].nm = Math.max(0.02, Math.min(nm, state.rangeNm * 2));
      syncMarkReadouts();
      return;
    }
    if (drag.kind === 'ebl') {
      const ebl = state.marks.ebl[drag.index];
      const geometryNow = drawGeometry();
      const origin = shipScreenPos(
        { ...geometryNow, ownToCenterN: geometryNow.ownToCenterN - ebl.offsetN, ownToCenterE: geometryNow.ownToCenterE - ebl.offsetE },
        rect.width / 2, rect.height / 2, bezel,
      );
      const bearing = Math.atan2(point.x - origin.x, -(point.y - origin.y)) * 180 / Math.PI;
      ebl.trueDeg = wrapAngleDeg(bearing + geometry.rotation * 180 / Math.PI);
      syncMarkReadouts();
      return;
    }
    if (drag.kind === 'eblOffset') {
      const rN = -(point.y - rect.height / 2) / bezel * geometry.rangeM;
      const rE = (point.x - rect.width / 2) / bezel * geometry.rangeM;
      const cos = Math.cos(geometry.rotation);
      const sin = Math.sin(geometry.rotation);
      const offsetN = rN * cos - rE * sin;
      const offsetE = rN * sin + rE * cos;
      const magnitude = Math.hypot(offsetN, offsetE);
      const scale = magnitude > geometry.rangeM ? geometry.rangeM / magnitude : 1;
      state.marks.ebl[drag.index].offsetN = offsetN * scale;
      state.marks.ebl[drag.index].offsetE = offsetE * scale;
    }
  }

  function onPointerUp(event) {
    if (!drag) return;
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    drag = null;
    guidance('COMPLETED');
  }

  /* ── WebSocket telemetry (same stream as the main app) ── */
  function connect() {
    if (destroyed) return;
    if (!state.session) {
      guidance(TEXT.noSession);
      return;
    }
    if (socket) {
      socket.onclose = null;
      socket.onmessage = null;
      socket.close();
      socket = null;
    }
    const schema = window.location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${schema}://${window.location.host}/ws/sessions/${encodeURIComponent(state.session)}`);
    socket.onmessage = event => {
      let envelope = null;
      try {
        envelope = JSON.parse(event.data);
      } catch {
        return;
      }
      handleEnvelope(envelope);
    };
    socket.onopen = () => {
      reconnectAttempt = 0;
      guidance(TEXT.tx);
    };
    socket.onclose = () => {
      if (destroyed) return;
      const delay = Math.min(5000, 500 * 2 ** reconnectAttempt);
      reconnectAttempt = Math.min(reconnectAttempt + 1, 4);
      guidance(TEXT.disconnected);
      if (reconnectTimer === null) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, delay);
      }
    };
  }

  /* ── render loop (60 fps; decode stays async) ── */
  function loop() {
    if (destroyed) return;
    draw();
    requestAnimationFrame(loop);
  }

  /* ── DOM wiring ───────────────────────── */
  function bind() {
    els.rsTx?.addEventListener('click', toggleStandby);
    els.rsBtnGain?.addEventListener('click', () => openAdjust('gain'));
    els.rsBtnSea?.addEventListener('click', () => openAdjust('sea'));
    els.rsBtnRain?.addEventListener('click', () => openAdjust('rain'));
    els.rsAdjustSlider?.addEventListener('input', onAdjustInput);
    els.rsAdjustClose?.addEventListener('click', () => {
      if (els.rsAdjustPanel) els.rsAdjustPanel.hidden = true;
      adjustChannel = null;
      syncAdjustExpanded();
    });
    els.rsBtnTrails?.addEventListener('click', cycleTrails);
    const hold = element => {
      if (!element) return;
      element.addEventListener('pointerdown', () => setHlOff(true));
      element.addEventListener('pointerup', () => setHlOff(false));
      element.addEventListener('pointerleave', () => { if (state.hlOff) setHlOff(false); });
      element.addEventListener('keydown', event => {
        if ((event.key === 'Enter' || event.key === ' ') && !event.repeat) {
          event.preventDefault();
          setHlOff(true);
        }
      });
      element.addEventListener('keyup', () => setHlOff(false));
    };
    hold(els.rsBtnHl);
    els.rsBtnReset?.addEventListener('click', resetMotion);
    els.rsBtnMarks?.addEventListener('click', toggleMarks);
    els.rsBtnBrill?.addEventListener('click', cyclePalette);
    els.rsModeButton?.addEventListener('click', cyclePresentation);
    els.rsRangeUp?.addEventListener('click', () => stepRange(1));
    els.rsRangeDown?.addEventListener('click', () => stepRange(-1));
    els.rsCpaUp?.addEventListener('click', () => setLimits({ cpaLimitNm: state.cpaLimitNm + 0.5 }));
    els.rsCpaDown?.addEventListener('click', () => setLimits({ cpaLimitNm: state.cpaLimitNm - 0.5 }));
    els.rsTcpaUp?.addEventListener('click', () => setLimits({ tcpaLimitMin: state.tcpaLimitMin + 1 }));
    els.rsTcpaDown?.addEventListener('click', () => setLimits({ tcpaLimitMin: state.tcpaLimitMin - 1 }));
    els.rsVecTime?.addEventListener('click', cycleVectorTime);
    els.rsVecMode?.addEventListener('click', cycleVectorMode);
    for (const [element, kind, index] of [
      [els.rsEbl1, 'ebl', 0], [els.rsEbl2, 'ebl', 1],
      [els.rsVrm1, 'vrm', 0], [els.rsVrm2, 'vrm', 1],
    ]) element?.addEventListener('click', () => activateMark(kind, index));
    els.rsEblNudgeL?.addEventListener('click', () => nudgeMark('ebl', -1));
    els.rsEblNudgeR?.addEventListener('click', () => nudgeMark('ebl', 1));
    els.rsVrmNudgeL?.addEventListener('click', () => nudgeMark('vrm', -1));
    els.rsVrmNudgeR?.addEventListener('click', () => nudgeMark('vrm', 1));
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointerleave', () => { state.cursor = null; });
  }

  function start() {
    applyPalette();
    syncRangeBox();
    syncEchoBox();
    syncMarkReadouts();
    syncAlerts();
    syncTargetBox();
    syncInfoBlocks();
    syncTxButton();
    if (els.rsModeLabel) els.rsModeLabel.textContent = state.presentation.label;
    if (els.rsCpaValue) els.rsCpaValue.textContent = `${state.cpaLimitNm.toFixed(1)}NM`;
    if (els.rsTcpaValue) els.rsTcpaValue.textContent = `${state.tcpaLimitMin}MIN`;
    if (els.rsVecTime) els.rsVecTime.textContent = `${state.vectorTimeMin}MIN`;
    if (els.rsVecMode) els.rsVecMode.textContent = state.vectorMode;
    if (els.rsBtnTrails) {
      els.rsBtnTrails.dataset.value = state.trails.key;
      els.rsBtnTrails.setAttribute('aria-label', `TRAILS 余辉 ${state.trails.label}，点击切换`);
    }
    if (els.rsTrailsValue) els.rsTrailsValue.textContent = state.trails.label;
    bind();
    guidance(!state.session ? TEXT.noSession : TEXT.connecting);
    loop();
    connect();
  }

  function destroy() {
    destroyed = true;
    if (reconnectTimer !== null) clearTimeout(reconnectTimer);
    if (socket) {
      socket.onclose = null;
      socket.onmessage = null;
      socket.close();
      socket = null;
    }
  }

  return { state, start, destroy, handleEnvelope, onDescriptor, guidance, connect };
}

/* ── bootstrap ────────────────────────────── */

function boot() {
  const root = document.getElementById('rsRoot');
  if (!root) return;
  const screen = createRadarScreen(root);
  screen.start();
  window.__radarScreen = screen;
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}
