import proj4 from '../vendor/proj4/proj4.mjs';
import { TARGET_RISK_STYLES, RADAR_DETECTION_RANGE_M } from './situation-display.js?v=20261004-token-cleanup-v1';

export const NM = 1852;
const finite = Number.isFinite;

export function geographyProblem(info, runId) {
  if (!info?.ready || info.run_id !== runId) return '等待当前会话的海图基准';
  if (![32, 33].includes(info.utm_zone) || info.horizontal_crs !== `EPSG:${25800 + info.utm_zone}`
    || info.hemisphere !== 'north') return '不支持或缺失水平 CRS';
  if (![info.origin_e, info.origin_n, info.width, info.height].every(finite)
    || info.width <= 0 || info.height <= 0) return '海图原点或范围无效';
  if (info.display_height_reference !== 'ellipsoid-zero-visual-only') return '缺失三维显示高度约定';
  return null;
}

export function createGeography(info) {
  const problem = geographyProblem(info, info?.run_id);
  if (problem) throw new Error(problem);
  const convert = proj4(`+proj=utm +zone=${info.utm_zone} +ellps=GRS80 +units=m +no_defs`, 'EPSG:4326');
  function lonLat(north, east) {
    if (![north, east].every(finite)) throw new Error('无效场景坐标');
    return convert.forward([info.origin_e + east, info.origin_n + north]);
  }
  // P2-S4 联动 spike（twin-bridge-v1.md §8）：Cesium 相机经纬度 → 全域 UTM 东/北米
  // （proj4 逆变换；结果与 attached.anchor 同一全局框架，Unity 侧减锚得场景坐标）。
  function eastNorth(lonDeg, latDeg) {
    if (![lonDeg, latDeg].every(finite)) throw new Error('无效地理坐标');
    return convert.inverse([lonDeg, latDeg]);
  }
  function heading(north, east, gridHeading) {
    if (!finite(gridHeading)) return null;
    // Direction of a short grid-space vector on the ellipsoid, including meridian convergence.
    const a = lonLat(north, east), b = lonLat(north + Math.cos(gridHeading), east + Math.sin(gridHeading));
    const rad = Math.PI / 180;
    return Math.atan2((b[0] - a[0]) * Math.cos(a[1] * rad), b[1] - a[1]);
  }
  return { info, lonLat, eastNorth, heading, contains: (n, e) => n >= 0 && e >= 0 && n <= info.height && e <= info.width };
}

export function targetKey(runId, target) {
  return `${runId}:${target.id ?? target.targetId}:${target.generation ?? 'none'}`;
}

export function riskForTarget(projection, target) {
  return projection?.risk?.targets?.find(risk => String(risk.targetId) === String(target.id)
    && (risk.generation ?? null) === (target.generation ?? null)) ?? null;
}

export function poiState(risk) {
  if (!risk || risk.unavailableReasons?.some(reason => reason !== 'PROFILE_UNQUALIFIED')
    || String(risk.observationHealth).toUpperCase() === 'STALE') return 'unchecked';
  return { HIGH: 'alarm', LOW: 'caution', CLEAR: 'checked' }[risk.displayClass] ?? 'unchecked';
}

const TARGET_ALERTS = {
  checked: { name: '安全', color: TARGET_RISK_STYLES.safe.color, poiState: 'enabled' },
  caution: { name: '监控', color: TARGET_RISK_STYLES.warn.color, poiState: 'caution' },
  alarm: { name: '紧急', color: TARGET_RISK_STYLES.danger.color, poiState: 'alarm' },
  unchecked: { name: '态势未知', color: '#FFFFFF', poiState: 'enabled' },
};

export function targetAlert(projection, ship) {
  const os = projection?.raw?.os;
  const inRange = [os?.x, os?.y, ship?.x, ship?.y].every(finite)
    && Math.hypot(ship.x - os.x, ship.y - os.y) <= RADAR_DETECTION_RANGE_M;
  const state = inRange ? poiState(riskForTarget(projection, ship)) : 'unchecked';
  return { state, ...TARGET_ALERTS[state] };
}

export function frameIdentity(data) {
  return { runId: data.run_id, seq: data.seq, renderTime: data.presentation?.render_time_s ?? data.sim_time };
}

// Only label samples when the planner supplies an actual time axis.
export function predictionMarkers(data) {
  const path = data.plans?.prediction_horizon || [];
  const typed = data.plans?.prediction_render;
  let times = typed?.ownship?.time_s;
  if (typed && typed.style !== 'ACTIVE') return [];
  if (!Array.isArray(times) || times.length !== path.length) {
    const dt = data.planner?.horizon_dt_s;
    if (!Number.isFinite(dt) || dt <= 0 || typed) return [];
    times = path.map((_, i) => i * dt);
  }
  if (!times.every(Number.isFinite)) return [];
  const start = times[0];
  let bucket = 0;
  return path.flatMap((point, index) => {
    const elapsed = times[index] - start, next = Math.floor(elapsed / 60);
    if (next <= bucket || !point.slice(0, 2).every(Number.isFinite)) return [];
    bucket = next;
    return [{ point, elapsed }];
  });
}

export function offscreenDirection(point, width, height, ahead, right) {
  if (!ahead || !point) return { edge: right ? 'right' : 'left', arrow: '↶ 后方' };
  const x = (point.x - width / 2) / (width / 2);
  const y = (point.y - height / 2) / (height / 2);
  if (Math.abs(y) > Math.abs(x)) return y < 0 ? { edge: 'up', arrow: '↑' } : { edge: 'down', arrow: '↓' };
  return x < 0 ? { edge: 'left', arrow: '←' } : { edge: 'right', arrow: '→' };
}
