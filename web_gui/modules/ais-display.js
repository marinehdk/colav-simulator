/**
 * AIS target display layer (P3-S4, spec #90).
 *
 * Pure seams for the 2D chart + 3D Cesium AIS symbol layer. The backend is
 * the authority for AIS report age and the active/sleeping/lost judgment
 * (`truth[].ais = {age_s, state}` — colav_simulator/core/ais_display.py);
 * this module never recomputes them. What is display-side here:
 * - the "dangerous" composition (IMO SN.1/Circ.243/Rev.1 Annex 1 §3.3:
 *   dangerous = activated target meeting the collision-alarm criteria), from
 *   the existing risk projection rank;
 * - AIS-to-track/radar association labeling for the target card;
 * - the symbol renderer (self-drawn per IMO 243, SVG assets mirrored by
 *   canvas fallback so the chart renders before images load).
 */

export const AIS_LAYER_ID = 'aisTargets';

/** Self-drawn SVG symbol assets (web_gui/assets/), IMO 243 geometry. */
export const AIS_SYMBOL_ASSETS = Object.freeze({
  sleeping: '/static/assets/ais-sleeping.svg',
  active: '/static/assets/ais-active.svg',
  dangerous: '/static/assets/ais-dangerous.svg',
  lost: '/static/assets/ais-lost.svg',
});

/** Draw sizes in CSS px per state (sleeping < activated per IMO 243 §3.1). */
export const AIS_SYMBOL_SIZES = Object.freeze({
  sleeping: 20,
  active: 26,
  dangerous: 30,
  lost: 24,
});

export const AIS_STATE_COLORS = Object.freeze({
  sleeping: '#2FBFA8',
  active: '#4FE0C6',
  dangerous: '#FF4D5A',
  lost: '#8C979D',
});

/** Card/legend labels per symbol state (shared by 2D + 3D cards). */
export const AIS_STATE_LABELS = Object.freeze({
  sleeping: '睡眠（小三角）',
  active: '激活（矢量）',
  dangerous: '危险（红闪）',
  lost: '丢失（×）',
});

/**
 * Association gates (hardcoded config, P3-S4): nearest fused-track state /
 * radar measurement within this radius of the AIS reported position counts
 * as the same physical target for the card label. Both channels have ~10 m
 * class accuracy; 150 m absorbs maneuver smearing between report instants.
 */
export const AIS_TRACK_ASSOCIATION_RADIUS_M = 150;
export const AIS_RADAR_ASSOCIATION_RADIUS_M = 150;

/** IMO 243 §3.3/§3.4: dangerous/lost symbols flash until acknowledged. */
export const AIS_BLINK_PERIOD_MS = 1000;

/** True during the "on" half-period of the blink (pure, testable). */
export function aisBlinkOn(timestampMs, periodMs = AIS_BLINK_PERIOD_MS) {
  const period = Number(periodMs);
  if (!Number.isFinite(period) || period <= 0) return true;
  return ((Number(timestampMs) || 0) % period) < period / 2;
}

/**
 * Symbol state composition. `ais.state` comes from the backend
 * (active|sleeping|lost); `riskRank` is the existing threat rank
 * (situation-display THREAT_STYLES rank, 3 = HIGH). A lost target keeps the
 * lost symbol; danger only upgrades activated targets (IMO 243 §3.3).
 */
export function aisSymbolState(ais, riskRank = 0) {
  const state = ais && typeof ais === 'object' ? String(ais.state || '') : '';
  if (state === 'lost') return 'lost';
  if (state === 'active' && Number(riskRank) >= 3) return 'dangerous';
  if (state === 'active') return 'active';
  return 'sleeping';
}

/**
 * Nearest-target association between AIS targets and the fused track set +
 * radar measurement points (all positions local NE meters, one frame).
 *
 * Returns a Map keyed by String(target.id):
 *   { trackId: number|null, generation: number|null, radar: boolean }
 * Track association uses the nearest track state within
 * AIS_TRACK_ASSOCIATION_RADIUS_M; radar association is true when any
 * measurement point lies within AIS_RADAR_ASSOCIATION_RADIUS_M.
 */
export function matchAisAssociations(targets, trackSet, measurementPoints) {
  const associations = new Map();
  const states = trackSet && Array.isArray(trackSet.states) ? trackSet.states : [];
  const labels = Array.isArray(trackSet?.labels) ? trackSet.labels : [];
  const generations = Array.isArray(trackSet?.generations) ? trackSet.generations : [];
  const points = (Array.isArray(measurementPoints) ? measurementPoints : [])
    .filter(point => Array.isArray(point) && [point[0], point[1]].every(Number.isFinite));
  (Array.isArray(targets) ? targets : []).forEach(target => {
    if (!target || target.ais == null || ![target.x, target.y].every(Number.isFinite)) return;
    let trackId = null;
    let generation = null;
    let bestRange = AIS_TRACK_ASSOCIATION_RADIUS_M;
    states.forEach((state, index) => {
      if (!Array.isArray(state) || [state[0], state[1]].some(v => !Number.isFinite(v))) return;
      const range = Math.hypot(state[0] - target.x, state[1] - target.y);
      if (range <= bestRange) {
        bestRange = range;
        trackId = labels[index] ?? index + 1;
        generation = generations[index] ?? null;
      }
    });
    const radar = points.some(point => Math.hypot(point[0] - target.x, point[1] - target.y) <= AIS_RADAR_ASSOCIATION_RADIUS_M);
    associations.set(String(target.id), { trackId, generation, radar });
  });
  return associations;
}

/**
 * Flattens the full-transport measurement groups to local-frame radar points
 * (world NE meters minus ENC origin), dropping clutter (do_idx === -1).
 * `origin` = {origin_n, origin_e} from the ENC info document.
 */
export function localRadarMeasurementPoints(sensorGroups, origin) {
  const originN = Number(origin?.origin_n);
  const originE = Number(origin?.origin_e);
  if (![originN, originE].every(Number.isFinite)) return [];
  const groups = Array.isArray(sensorGroups) ? sensorGroups.filter(Array.isArray) : [];
  const points = [];
  groups.flat().forEach(measurement => {
    if (!Array.isArray(measurement) || measurement[0] === -1) return;
    const value = measurement[1];
    if (!Array.isArray(value) || ![value[0], value[1]].every(Number.isFinite)) return;
    points.push([value[0] - originN, value[1] - originE]);
  });
  return points;
}

/** Human label for the association row of the AIS target card. */
export function associationLabel(association) {
  if (!association) return '独立目标';
  const parts = [];
  if (association.trackId !== null && association.trackId !== undefined) {
    parts.push(`TS${association.trackId}（融合）`);
  }
  if (association.radar) parts.push('雷达回波');
  return parts.length ? parts.join(' + ') : '独立目标';
}

/**
 * Canvas renderer for one AIS symbol (mirrors the SVG assets). `rotation`
 * is the screen-space orientation in radians (heading already composed with
 * the map rotation by the caller). `blinkOn=false` renders the flashing
 * states (dangerous/lost) at low alpha — IMO 243 §3.3/§3.4 flash semantics.
 * Falls back to a plain triangle before the SVG images load.
 */
export function drawAisSymbol(surface, x, y, rotation, state, options = {}) {
  const symbol = AIS_SYMBOL_ASSETS[state] ? state : 'sleeping';
  const size = Number(options.size) || AIS_SYMBOL_SIZES[symbol];
  const blinkOn = options.blinkOn !== false;
  const flashing = symbol === 'dangerous' || symbol === 'lost';
  const image = options.images?.[symbol];
  surface.save();
  surface.translate(x, y);
  surface.rotate(Number.isFinite(rotation) ? rotation : 0);
  surface.globalAlpha = flashing && !blinkOn ? 0.25 : 1;
  if (image && image.complete && image.naturalWidth > 0) {
    surface.imageSmoothingEnabled = true;
    surface.imageSmoothingQuality = 'high';
    surface.drawImage(image, -size / 2, -size / 2, size, size);
  } else {
    // Vector fallback: acute isosceles triangle (+ thick cross when lost).
    const half = size / 2;
    surface.beginPath();
    surface.moveTo(0, -half);
    surface.lineTo(half * 0.62, half);
    surface.lineTo(0, half * 0.3);
    surface.lineTo(-half * 0.62, half);
    surface.closePath();
    surface.fillStyle = AIS_STATE_COLORS[symbol];
    surface.globalAlpha *= 0.85;
    surface.fill();
    if (symbol === 'lost') {
      surface.strokeStyle = AIS_STATE_COLORS.lost;
      surface.lineWidth = Math.max(2, size * 0.11);
      surface.beginPath();
      surface.moveTo(-half * 0.7, -half * 0.7);
      surface.lineTo(half * 0.7, half * 0.7);
      surface.moveTo(half * 0.7, -half * 0.7);
      surface.lineTo(-half * 0.7, half * 0.7);
      surface.stroke();
    }
  }
  surface.restore();
}
