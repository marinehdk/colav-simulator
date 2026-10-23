import { targetsForDisplay, RADAR_DETECTION_RANGE_M, drawVODecisionDisc, trackConfidenceColor } from './situation-display.js?v=20261023-radar-overlay-v3';
import { routeRibbonQuads } from './route-3d.js?v=20261023-radar-overlay-v3';
import { predictionMarkers, targetKey, offscreenDirection, NM } from './scene-geography.js?v=20261023-radar-overlay-v3';
import { targetPresentation, updateTargetPoi, applyTargetAppearance, renderTargetCard } from './scene-target.js?v=20260923-follow-v1';
import { createSceneCompass } from './scene-compass.js?v=20261023-radar-overlay-v3';
import { AIS_SYMBOL_ASSETS, AIS_SYMBOL_SIZES, aisSymbolState } from './ais-display.js';

export const FRAME_MARKER = Object.freeze({ width: 256, height: 16 });

export function decodeFrameMarker(pixels) {
  if (!pixels || pixels.length !== 128) return null;
  let bits = 0;
  for (let i = 0; i < 32; i++) {
    const level = (pixels[i * 4] + pixels[i * 4 + 1] + pixels[i * 4 + 2]) / 3;
    // Ambiguous compression samples fail closed instead of selecting another frame.
    if (level > 80 && level < 175) return null;
    bits = ((bits << 1) | (level >= 175 ? 1 : 0)) >>> 0;
  }
  if ((bits >>> 24) !== 0xd3) return null;
  const frame = (bits >>> 8) & 65535;
  return (bits & 255) === (((frame >>> 8) ^ frame ^ 0x5a) & 255) ? frame : null;
}

export function containedVideoRect(width, height, videoWidth, videoHeight) {
  if (![width, height, videoWidth, videoHeight].every(value => Number.isFinite(value) && value > 0)) return null;
  const scale = Math.min(width / videoWidth, height / videoHeight);
  const w = videoWidth * scale, h = videoHeight * scale;
  return { left: (width - w) / 2, top: (height - h) / 2, width: w, height: h, scale };
}

export function matchedSituationFrame(client, frameId, runId, width, height) {
  const frame = client?.situationFrame?.(frameId);
  return frame?.run_id === runId && frame.width === width && frame.height === height ? frame : null;
}

// dt-sensor-overlay 契约 §6.3：右键本地命中，逐句复刻 TwinSituationMath.Pick
// （TwinSituationMessage.cs:102-116）——bounds + 12px pad（归一化域）内、
// 多命中取 depth 最近；只遍历 targets，detections 不参与命中（§4）。
export function pickTwinTarget(frame, x, y) {
  if (!frame || !Array.isArray(frame.targets)) return null;
  if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || x > 1 || y < 0 || y > 1) return null;
  const padX = 12 / Math.max(1, frame.width || 0), padY = 12 / Math.max(1, frame.height || 0);
  let result = null;
  for (const point of frame.targets) {
    if (!point || !point.visible || !(point.depth > 0)) continue;
    if (x < point.left - padX || x > point.left + point.width + padX ||
      y < point.top - padY || y > point.top + point.height + padY) continue;
    if (!result || point.depth < result.depth) result = point;
  }
  return result;
}

// per-target 检测显示模式循环：fused → yolo → fused（Set 存储右键切换集合）。
export function toggleYoloKey(keys, key) {
  if (!keys || !key) return keys;
  if (keys.has(key)) keys.delete(key); else keys.add(key);
  return keys;
}

// det_id = "{sensor_id}:{frame_seq}:{ordinal}"（A 段），frame_seq 单调 → 数值域
// 最大即最新（§6.4：同一 track_key 多条检测取 det_id 最大者）。
function detIdRank(id) {
  const parts = String(id ?? '').split(':');
  if (parts.length !== 3) return null;
  const numbers = parts.map(Number);
  return numbers.every(Number.isFinite) ? numbers : null;
}

export function latestDetectionForTrack(detections, trackKey) {
  let best = null, bestRank = null;
  for (const det of detections || []) {
    if (!det || !det.track_key || det.track_key !== trackKey) continue;
    const rank = detIdRank(det.key);
    if (!rank) continue;
    if (!bestRank || rank[0] > bestRank[0] || (rank[0] === bestRank[0]
      && (rank[1] > bestRank[1] || (rank[1] === bestRank[1] && rank[2] > bestRank[2])))) { best = det; bestRank = rank; }
  }
  return best;
}

// OpenBridge's offset POI keeps its pointer at the vessel while moving its head.
// Its auto-group layout assumes one shared horizon row and ignores buttonY.
export function layoutTwinLabels(items, width, topInset = 20) {
  const placed = [], result = new Map();
  for (const item of [...items].sort((a, b) => b.priority - a.priority || a.key.localeCompare(b.key))) {
    let chosen = null;
    for (const compact of [false, true]) {
      const height = compact ? 48 : item.height;
      const maxLift = item.y - topInset - height;
      if (maxLift < 0) continue;
      const base = Math.min(72, maxLift);
      const preferredX = Math.max(36, Math.min(width - 36, item.x));
      for (let lift = base; lift <= maxLift + 0.1 && !chosen; lift += height + 12) {
        for (const offset of [0, 72, -72, 144, -144, 216, -216, 288, -288, 360, -360, 432, -432]) {
          const x = preferredX + offset, top = item.y - lift - height, bottom = item.y - lift;
          if (x < 36 || x > width - 36) continue;
          if (placed.some(p => Math.abs(p.x - x) < 72 && top < p.bottom + 12 && bottom > p.top - 12)) continue;
          chosen = { x, lift, top, bottom, compact }; break;
        }
      }
      if (chosen) break;
    }
    // Retain even a tightly clipped contact as a compact selectable head.
    chosen ||= { x: Math.max(36, Math.min(width - 36, item.x)), lift: 0, top: item.y - 48, bottom: item.y, compact: true };
    placed.push(chosen); result.set(item.key, chosen);
  }
  return result;
}

// Keep the prediction geometry intact; only thin its screen-space annotations.
// 2026-10-23 初始航线航点照预测时间标注同模式抽稀:保起讫(出发/目的)优先,中段
// 注记填满即止(上限 4 与预测一致);航带与水面航点圈是几何,不受此精简影响。
export function layoutTwinWaypoints(waypoints, timeMarkers, width, height, topInset) {
  const result = new Map();
  const visible = points => points.filter(p => p.visible && Number.isFinite(p.x) && Number.isFinite(p.y)
    && p.x * width >= 36 && p.x * width <= width - 36
    && p.y * height >= topInset && p.y * height <= height - 16);
  const endpointsFirst = points => points.length > 1 ? [points[0], points.at(-1), ...points.slice(1, -1)] : points;
  const times = visible(timeMarkers);
  // Projection order follows the real planner time axis. Reserve the nearest
  // sample and horizon endpoint before considering intermediate annotations.
  const ordered = endpointsFirst(times);
  let timeCount = 0, waypointCount = 0;
  for (const p of [...endpointsFirst(visible(waypoints)), ...ordered]) {
    const timed = p.label.startsWith('+');
    if (timed && timeCount >= 4) continue;
    if (!timed && waypointCount >= 4) continue;
    const x = p.x * width, y = p.y * height;
    const halfWidth = Math.max(32, p.label.length * 4 + 8);
    let chosen = null;
    for (const lift of [56, 96]) {
      for (const offset of [0, 72, -72]) {
        const box = { x, y, lift, offset, left: x + offset - halfWidth, right: x + offset + halfWidth,
          top: y - lift - 42, bottom: y - lift + 18 };
        if (box.left < 8 || box.right > width - 8 || box.top < topInset || box.bottom > height - 8) continue;
        if ([...result.values()].some(q => box.left < q.right + 8 && box.right + 8 > q.left
          && box.top < q.bottom + 8 && box.bottom + 8 > q.top)) continue;
        chosen = box; break;
      }
      if (chosen) break;
    }
    if (!chosen) continue;
    result.set(p.label, chosen);
    if (timed) timeCount++; else waypointCount++;
  }
  return result;
}

// ── DT 视口 YOLO 检测（telemetry WS 文档顶层 viewport_detections@1）──────────
// 后端把像素域检测（720p，左上原点 y 向下）挂在遥测文档顶层；无数据/过期时键
// 缺省。fold 留存最新一条 + 本地接收时刻，乱序旧消息（received_at 回退）不覆盖。
export function foldViewportDetections(state, raw, nowMs) {
  const doc = raw?.viewport_detections;
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.detections)) return state ?? null;
  const receivedAt = Number(doc.received_at), previous = Number(state?.doc?.received_at);
  if (state && Number.isFinite(previous) && Number.isFinite(receivedAt) && receivedAt < previous) return state;
  return { doc, at: nowMs };
}

// 新鲜 = age_s < 1.2 且带 detections 数组（空数组也算活跃：YOLO 模式开着但此刻
// 看不到船 = 视口无标注）。age_s 缺失（旧后端）回退本地接收时刻差。
export const VIEWPORT_DETECTIONS_FRESH_S = 1.2;
export function viewportDetectionsFresh(state, nowMs) {
  if (!state || !Array.isArray(state.doc?.detections)) return false;
  const age = Number(state.doc.age_s);
  if (Number.isFinite(age)) return age >= 0 && age < VIEWPORT_DETECTIONS_FRESH_S;
  return Number.isFinite(state.at) && (nowMs - state.at) / 1000 < VIEWPORT_DETECTIONS_FRESH_S;
}

// YOLO 视口模式 = 海图"YOLO 检测"图层勾选（visible 已并入可用性）且数据新鲜。
export function yoloViewportMode(layerState, state, nowMs) {
  return layerState?.detections?.visible === true && viewportDetectionsFresh(state, nowMs);
}

// box_xyxy（文档 width×height 像素域）→ 根叠层（contained rect）像素坐标，
// 并带归一化中心（cx/cy）供最近邻关联。
export function viewportDetectionBoxes(doc, rectWidth, rectHeight) {
  const w = Number(doc?.width), h = Number(doc?.height);
  if (!(w > 0) || !(h > 0) || !Array.isArray(doc.detections)) return [];
  return doc.detections.flatMap((det, index) => {
    const box = Array.isArray(det?.box_xyxy) ? det.box_xyxy.map(Number) : [];
    if (!box.every(Number.isFinite)) return [];
    return [{ index,
      left: box[0] / w * rectWidth, top: box[1] / h * rectHeight,
      width: Math.max(0, (box[2] - box[0]) / w * rectWidth),
      height: Math.max(0, (box[3] - box[1]) / h * rectHeight),
      cx: (box[0] + box[2]) / 2 / w, cy: (box[1] + box[3]) / 2 / h,
      className: String(det.class_name ?? ''),
      confidence: Number.isFinite(Number(det.confidence)) ? Number(det.confidence) : 0 }];
  });
}

// 检测↔track 最近邻关联（归一化域欧氏距离 < 半径取最近）：style 1/2 的导航
// 数据块由此拿 BRG/RNG/DCPA；关联不到 = 无导航数据。
export const VIEWPORT_ASSOCIATION_RADIUS = 0.12;
export function associateViewportDetections(centers, targets, radius = VIEWPORT_ASSOCIATION_RADIUS) {
  return (centers || []).map(({ cx, cy }) => {
    let best = null, bestDistance = radius;
    for (const target of targets || []) {
      if (!target?.key || !Number.isFinite(target.x) || !Number.isFinite(target.y)) continue;
      const distance = Math.hypot(target.x - cx, target.y - cy);
      if (distance < bestDistance) { bestDistance = distance; best = target.key; }
    }
    return best;
  });
}

// 全局三态样式循环（单击任一检测标签/框切换）：0=框+类别标签，1=+导航数据块，
// 2=无框仅导航数据块。
export function cycleViewportYoloStyle(style) {
  return ((Number.isFinite(Number(style)) ? Number(style) : 0) + 1) % 3;
}

// HUD YOLO 后缀：勾选且数据新鲜='· YOLO ON'(链路在算,空集=没检测到);
// 勾选但不新鲜='· YOLO OFF'(引擎启动中/链路断=没在算);未勾选=''。
export function viewportYoloHudSuffix(layerState, state, nowMs) {
  if (layerState?.detections?.visible !== true) return '';
  return viewportDetectionsFresh(state, nowMs) ? '· YOLO ON' : '· YOLO OFF';
}

// ── P3 viewport_tracks@1（telemetry WS 顶层 confirmed 航迹）──────────────────
// 后端把视口检测 georef 进 observations/IPDA 装配（P1 中继 camera_pose），confirmed
// 航迹（status/existence_prob/滤波后 brg/rng + 绝对 NE）随遥测广播。fold 留存
// 最新一文档 + 本地接收时刻（乱序旧消息不覆盖，照 foldViewportDetections 模式）。
export function foldViewportTracks(state, raw, nowMs) {
  const doc = raw?.viewport_tracks;
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.tracks)) return state ?? null;
  const receivedAt = Number(doc.received_at), previous = Number(state?.doc?.received_at);
  if (state && Number.isFinite(previous) && Number.isFinite(receivedAt) && receivedAt < previous) return state;
  return { doc, at: nowMs };
}

// 新鲜窗与检测通道一致（检测断流 → 两键同缺省 → TRK 回退 DET 即时生效）。
export const VIEWPORT_TRACKS_FRESH_S = VIEWPORT_DETECTIONS_FRESH_S;
export function viewportTracksFresh(state, nowMs) {
  if (!state || !Array.isArray(state.doc?.tracks)) return false;
  const age = Number(state.doc.age_s);
  if (Number.isFinite(age)) return age >= 0 && age < VIEWPORT_TRACKS_FRESH_S;
  return Number.isFinite(state.at) && (nowMs - state.at) / 1000 < VIEWPORT_TRACKS_FRESH_S;
}

// track 数据块（真实延迟语义：brg/rng = 跟踪时刻滤波态，分钟级收敛，不追帧；
// 框级锁帧由 P0 微跟踪器负责，两层解耦——sitaw 调研 §2.3）。行形状与
// targetPresentation.blocks 同构（label/value/unit），CONF 行显示 existence。
const trkMetric = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : '—';
export function viewportTrackBlocks(track) {
  if (!track) return [];
  const bearing = Number(track.bearing_rad), range = Number(track.range_m);
  if (!Number.isFinite(bearing) || !Number.isFinite(range)) return [];
  const existence = Number(track.existence_prob);
  return [
    { label: 'BRG', value: trkMetric((bearing * 180 / Math.PI + 360) % 360, 0), unit: 'DEG' },
    { label: 'RNG', value: trkMetric(range / NM, 2), unit: 'NM' },
    { label: 'CONF', value: trkMetric(existence, 3), unit: '' },
  ];
}

// 数据源裁决：track 可用（产出有效数据块）→ TRK；缺席/无效 → 回退裸检测
// 数据块（DET，P0 前的 truth 关联来源不变）。返回 { source, blocks }。
export function viewportTrackData(track, fallbackBlocks) {
  const blocks = viewportTrackBlocks(track);
  return blocks.length ? { source: 'TRK', blocks } : { source: 'DET', blocks: fallbackBlocks || [] };
}

// 绿框 ↔ track 关联：track 绝对 NE 经当帧相机位姿投影（水线高 0），与锁帧框
// 心最近邻（归一化域 < VIEWPORT_ASSOCIATION_RADIUS）。仅用于“哪个框挂哪条
// 航迹”的显示配对——数据块数值仍取航迹自身滤波态，不对齐到当前帧。
export function associateViewportTrack(tracks, locked, pose, aspect = 16 / 9) {
  if (!locked || !Array.isArray(tracks) || !pose) return null;
  let best = null, bestDistance = VIEWPORT_ASSOCIATION_RADIUS;
  for (const track of tracks) {
    const north = Number(track?.north_m), east = Number(track?.east_m);
    const point = projectViewportPoint(pose, east, north, 0, aspect);
    if (!point) continue;
    const distance = Math.hypot(point.x - locked.cx, point.y - locked.cy);
    if (distance < bestDistance) { bestDistance = distance; best = track; }
  }
  return best;
}

// ── 本船框抑制（dt-yolo 第4轮 → P0 水线多边形升级）────────────────────────
// 追随/俯仰视角里本船自身是画面主体,COCO boat 检出它属真实检测但无情报价值;
// 显示层在渲染前把落在本船水线投影区内的框剔除(纯过滤,不改数据)。做法 = 把
// 本船水线轮廓(沿船长 9 站:艏/艉中线点 + 舯站两舷)正投影到视口,画面内点集
// 取凸包,再按 OWN_SHIP_GUARD_DILATION 外扩(继承旧圆圈 ×1.3 的船楼/框心抖动
// 余量语义)作抑制区。堵旧实现两洞:艏点出画(陡俯视艏出顶/横转艏出侧)时整船
// 放行、艏点出画而甲板中段仍入画时漏抑制。画面内点不足以成面时保留旧底带
// floorY 规则兜底。桥视角本船在相机身后(各站深度≤近轴)→ 无投影点 → 不抑制。
// 相机基与 CameraRig camera_free 语义同源:yaw 北向东顺时针,pitch 负=俯,
// fov=垂直向度;水平向按 aspect(视口族恒 16:9,由调用方传入)。
// 相机正交基(yaw 北向东顺时针,pitch 负=俯):f 前/r 右/u 上,与 CameraRig
// camera_free 语义同源——projectViewportPoint 与自转补偿共用,单一事实源。
function cameraBasis(yawDeg, pitchDeg) {
  const radians = Math.PI / 180;
  const yaw = yawDeg * radians, pitch = pitchDeg * radians;
  const f = [Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch)];
  const r = [Math.cos(yaw), 0, -Math.sin(yaw)];
  const u = [f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0]];
  return { f, r, u };
}

// 无界投影(深度>1 即返回,不做视口边界过滤)——ownShipViewportGuard 用:出画
// 但在相机前方的站,坐标钳回画面边界参与凸包(船体穿越画面边沿的区段由此贴
// 边覆盖,堵站间出画缝);projectViewportPoint 公共契约不变(容差界内才返回)。
function projectUnclampedViewportPoint(pose, east, north, height, aspect) {
  if (!pose || ![pose.east, pose.north, pose.height_m, pose.yaw_deg, pose.pitch_deg, pose.fov_deg].every(Number.isFinite)) return null;
  if (![east, north, height].every(Number.isFinite) || !(aspect > 0)) return null;
  const { f, r, u } = cameraBasis(pose.yaw_deg, pose.pitch_deg);
  const de = east - pose.east, dn = north - pose.north, dh = height - pose.height_m;
  const depth = de * f[0] + dh * f[1] + dn * f[2];
  if (depth <= 1) return null;
  const px = de * r[0] + dh * r[1] + dn * r[2];
  const py = de * u[0] + dh * u[1] + dn * u[2];
  const tv = Math.tan(pose.fov_deg * Math.PI / 180 / 2);
  return { x: px / (2 * depth * tv * aspect) + 0.5, y: 0.5 - py / (2 * depth * tv), depth };
}

export function projectViewportPoint(pose, east, north, height, aspect = 16 / 9) {
  const point = projectUnclampedViewportPoint(pose, east, north, height, aspect);
  if (!point) return null;
  if (point.x < -0.1 || point.x > 1.1 || point.y < -0.1 || point.y > 1.1) return null; // 视口外(留越界容差)
  return point;
}

// 抑制区(20261015 验收轮底带 → P0 水线多边形 → 20261019 评审轮并集):艏/艉/
// 两舷水线角点(9 站×3 点矩形网格)投影,画面内点集取凸包(×1.3 外扩)为本船
// 抑制多边形;艏点(投影容差域内)在下半区时叠加底半平面 floorY——桥眼位近桥
// 栏杆/甲板在水线站间出画的底带(y∈(艏点,1.0])不落在站的凸包内,单多边形对
// 该带覆盖不全(20261019 评审密集扫描:27% 漏抑制),并集恢复旧规则 100% 覆盖;
// 追随视角艏点在上半区(y≤0.5)自然不叠。画面内点不足以成面时退回纯 floorY
// 底带。floorY/polygon/circles 任一命中即剔除(circles 仅向后兼容旧 guard
// 形状,本实现不再产出)。
const OWN_SHIP_HULL_STATIONS = [1, 0.75, 0.5, 0.25, 0, -0.25, -0.5, -0.75, -1];
export const OWN_SHIP_GUARD_DILATION = 1.3;

// Andrew 单调链凸包(≤25 水线点,显示层量级);共线点剔净(严格凸),输出逆时
// 针序;退化(<3 点或全共线)返回不足 3 点,由调用方走兜底。
function convexHull(points) {
  const sorted = [...points].sort((a, b) => a.x - b.x || a.y - b.y);
  if (sorted.length < 3) return sorted;
  const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const chain = source => {
    const stack = [];
    for (const point of source) {
      while (stack.length >= 2 && cross(stack[stack.length - 2], stack[stack.length - 1], point) <= 0) stack.pop();
      stack.push(point);
    }
    return stack;
  };
  const lower = chain(sorted), upper = chain(sorted.reverse());
  lower.pop(); upper.pop();
  return lower.concat(upper);
}

// 凸多边形含边界内判定(顶点逆时针序)。
function inConvexPolygon(cx, cy, hull) {
  for (let i = 0; i < hull.length; i++) {
    const a = hull[i], b = hull[(i + 1) % hull.length];
    if ((b.x - a.x) * (cy - a.y) - (b.y - a.y) * (cx - a.x) < 0) return false;
  }
  return true;
}

export function ownShipViewportGuard(pose, own, aspect = 16 / 9) {
  const halfLength = Math.max(Number(own?.length) || 0, 12) / 2;
  const beam = Number(own?.beam);   // beam 缺省 length/4(船型常识比,无传感字段)
  const halfBeam = ((Number.isFinite(beam) && beam > 0) ? beam : halfLength / 2) / 2;
  const psi = Number(own?.psi) || 0;
  const east0 = Number(own?.east), north0 = Number(own?.north);
  const ahead = [Math.sin(psi), Math.cos(psi)], aside = [Math.cos(psi), -Math.sin(psi)];
  const bow = projectViewportPoint(pose, east0 + ahead[0] * halfLength,
    north0 + ahead[1] * halfLength, 0, aspect);
  // 桥眼位叠加底带(20261020 二轮记录仪:2862 个泄漏框集中在 pitch +1~+3° 微仰
  // ——凸包存在但盖不住底带,bow.y≤0.5 又令 floorY 失效;本船水线中心在相机
  // 身后 → 俯/平/微仰(≤5°)时下方恒属本船甲板带,与凸包叠加而非二选一)。
  const centerBehind = !projectUnclampedViewportPoint(pose, east0, north0, 0, aspect);
  const pitchNow = Number(pose?.pitch_deg);
  const bridgeBand = centerBehind && Number.isFinite(pitchNow) && pitchNow <= 5 ? 0.62 : null;
  let floorY = bow && bow.y > 0.5 ? bow.y - 0.06 : null;
  if (bridgeBand != null) floorY = Math.max(floorY ?? 0, bridgeBand);
  // 矩形水线网格(艏艉站同样带两舷角点——密集扫描对拍口径,27 点 O(27) 可忽略)。
  // 有站在画面内(船体真实穿越画面边沿)时,出画但在相机前方的站坐标钳回画面边
  // 界入样——穿越区段贴边覆盖,堵站间出画缝(20261019 评审密集扫描的泄漏带);
  // 无站在画面内(船体整体出画,如仰视)则不造面,走下方 floorY 兜底/放行;身后
  // 站(深度≤近轴)恒弃。
  const unclamped = [];
  for (const station of OWN_SHIP_HULL_STATIONS) {
    const along = station * halfLength;
    for (const side of [-halfBeam, 0, halfBeam]) {
      const point = projectUnclampedViewportPoint(pose, east0 + ahead[0] * along + aside[0] * side,
        north0 + ahead[1] * along + aside[1] * side, 0, aspect);
      if (point) unclamped.push(point);
    }
  }
  const inFrame = unclamped.filter(p => p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1);
  const hull = convexHull(inFrame.length ? unclamped.map(p =>
    ({ x: Math.max(0, Math.min(1, p.x)), y: Math.max(0, Math.min(1, p.y)) })) : inFrame);
  if (hull.length >= 3) {
    const cx = hull.reduce((sum, p) => sum + p.x, 0) / hull.length;
    const cy = hull.reduce((sum, p) => sum + p.y, 0) / hull.length;
    const polygon = hull.map(p =>
      ({ x: cx + (p.x - cx) * OWN_SHIP_GUARD_DILATION, y: cy + (p.y - cy) * OWN_SHIP_GUARD_DILATION }));
    return { circles: [], polygons: [polygon], floorY };
  }
  if (floorY != null) return { circles: [], polygons: [], floorY };
  // 桥眼位近距兜底(20261020 记录仪:47% 快照 guard=null 且底带本船框泄漏——
  // 艏部水线站投到画面底边以下 y>1,inFrame 空+bow.y>1 → poly/floorY 双缺席,
  // 而本船甲板正铺满底带):俯/平视(pitch≤2°)且有站在底边以下时给保守底带。
  const belowFrame = unclamped.some(p => p.y > 1.02 && p.x >= 0 && p.x <= 1);
  const pitchDeg = Number(pose?.pitch_deg);
  if (belowFrame && Number.isFinite(pitchDeg) && pitchDeg <= 2) {
    return { circles: [], polygons: [], floorY: 0.62 };
  }
  return null;
}

export function suppressOwnShipBoxes(boxes, guard) {
  if (!guard) return boxes || [];
  return (boxes || []).filter(box =>
    !(guard.floorY != null && box.cy > guard.floorY)
    && !(guard.polygons || []).some(polygon => inConvexPolygon(box.cx, box.cy, polygon))
    && !(guard.circles || []).some(g => Math.hypot(box.cx - g.x, box.cy - g.y) <= g.radius));
}

// ── P0 检测框锁帧:web 微跟踪器 + 逐帧位姿自转补偿 ──────────────────────────
// 检测链端到端 ~0.3-0.5s:检测坐标直接画在当前显示帧上,pan/tilt 下相机已转,
// 框相对视频错位(sitaw 调研 §2.2/§3.2:链路延迟作用于整幅画面,不作用于框相对
// 视频的几何;真实系统框与帧同源同传)。web 侧两层补偿:
//   ① 自转补偿:检出时刻位姿 = 逐 situation 帧 camera_pose 历史(本地接收时刻
//     轴)在采集时刻处插值;采集时刻 ≈ received_at − DETECTION_CAPTURE_INFERENCE_MS
//     − DETECTION_CAPTURE_TAP_MS(gui_server 在 POST 收到时盖 time.time(),常量
//     集中定义可调)。Δyaw/Δpitch × 焦距把框中心平移到显示帧位姿域。
//   ② 匀速外推:检测文档间最近邻关联赋稳定 id,速度 EMA,外推到显示帧时刻。
// 已关联 track 的框默认同走本路径;truth 投影吸附(situation 真值包围盒零滞后
// 贴皮)降级为 debug 开关,默认关。
export const DETECTION_CAPTURE_INFERENCE_MS = 150;  // YOLO 推理(a4000 实测 ~141ms)
export const DETECTION_CAPTURE_TAP_MS = 120;        // 分流 tap/隧道/POST(20261020 记录仪校准:总延迟 ~270ms,原 130ms 低估致 pan 下补偿欠转)
export const POSE_HISTORY_SPAN_S = 3;              // 位姿历史窗(秒)
// 时钟轴假设(20261019 评审轮):位姿历史键 = 浏览器 Date.now()(twin-view 给
// situation 帧盖 _receivedAt),doc.received_at = gui_server 同机 time.time()——
// 本部署(gui_server 静态服务+遥测与浏览器同机)两钟同源无偏差。跨机无 NTP 时
// 采集时刻会落出历史窗:越窗超出 POSE_HISTORY_MAX_SKEW_S 即弃补偿(返 null,
// 退化为无补偿关联+匀速外推,误差有界不发散),不再静默 clamp 到错误位姿。
export const POSE_HISTORY_MAX_SKEW_S = 1;
export const VIEWPORT_TRACK_GATE_N = 0.15;         // 帧间最近邻关联门(归一化域)
export const VIEWPORT_TRACK_MAX_MISSES = 5;        // 连续丢失容忍(10Hz×5=0.5s)
export const VIEWPORT_TRACK_VELOCITY_ALPHA = 0.5;  // 速度 EMA 系数(新观测权重)
export const VIEWPORT_EXTRAPOLATION_MAX_S = 0.8;   // 外推上限(断流防飞框)

// 角差归一到 (−180, 180](yaw 插值/补偿跨 0°/360° 用)。
function wrapDegDelta(deg) {
  return ((deg + 180) % 360 + 360) % 360 - 180;
}

export function detectionCaptureTimeSec(receivedAtSec) {
  const received = Number(receivedAtSec);
  return Number.isFinite(received)
    ? received - (DETECTION_CAPTURE_INFERENCE_MS + DETECTION_CAPTURE_TAP_MS) / 1000 : null;
}

// 位姿历史插值(east/north/height/fov 线性;yaw/pitch 最短角)。越界在
// POSE_HISTORY_MAX_SKEW_S 容差内取最近端(3s 窗 >> 采集回看 ~0.5s,仅开局几帧
// 会 clamp);超出即返 null(时钟轴偏移防护,见常量注释)。条目 = { tSec, pose }。
export function poseAtCapture(poseHistory, tSec) {
  const history = Array.isArray(poseHistory)
    ? poseHistory.filter(sample => Number.isFinite(sample?.tSec) && sample?.pose) : [];
  if (!history.length || !Number.isFinite(tSec)) return null;
  const first = history[0], last = history[history.length - 1];
  if (tSec <= first.tSec) return first.tSec - tSec > POSE_HISTORY_MAX_SKEW_S ? null : first.pose;
  if (tSec >= last.tSec) return tSec - last.tSec > POSE_HISTORY_MAX_SKEW_S ? null : last.pose;
  let upper = 1;
  while (history[upper].tSec < tSec) upper++;
  const a = history[upper - 1], b = history[upper];
  const k = (tSec - a.tSec) / (b.tSec - a.tSec);
  const lerp = (x, y) => x + (y - x) * k;
  return { east: lerp(a.pose.east, b.pose.east), north: lerp(a.pose.north, b.pose.north),
    height_m: lerp(a.pose.height_m, b.pose.height_m), fov_deg: lerp(a.pose.fov_deg, b.pose.fov_deg),
    yaw_deg: a.pose.yaw_deg + wrapDegDelta(b.pose.yaw_deg - a.pose.yaw_deg) * k,
    pitch_deg: a.pose.pitch_deg + wrapDegDelta(b.pose.pitch_deg - a.pose.pitch_deg) * k };
}

// 自转补偿:框中心从 fromPose 采集帧平移到 toPose 显示帧——"Δyaw/Δpitch × 焦
// 距"的精确实现:把框心解回像面射线(fromPose 内参),经共享相机基旋转到
// toPose 系再回投(toPose 内参)。相机不平移时任意角差精确(含 yaw/pitch 轴
// 耦合与变焦);平移视差无深度不可补,属本显示层近似残余。射线转到 toPose
// 前向背面(depth≤0)时放弃补偿,退回原坐标。
export function compensateViewportShift(fromPose, toPose, cx, cy, aspect = 16 / 9) {
  if (!fromPose || !toPose) return { cx, cy };
  if (![fromPose.yaw_deg, fromPose.pitch_deg, fromPose.fov_deg,
    toPose.yaw_deg, toPose.pitch_deg, toPose.fov_deg].every(Number.isFinite) || !(aspect > 0)) return { cx, cy };
  const radians = Math.PI / 180;
  const tvFrom = Math.tan(fromPose.fov_deg * radians / 2), tvTo = Math.tan(toPose.fov_deg * radians / 2);
  if (!(tvFrom > 0) || !(tvTo > 0)) return { cx, cy };
  const from = cameraBasis(fromPose.yaw_deg, fromPose.pitch_deg);
  const to = cameraBasis(toPose.yaw_deg, toPose.pitch_deg);
  const planeX = (cx - 0.5) * 2 * tvFrom * aspect, planeY = (0.5 - cy) * 2 * tvFrom;   // 焦距=1 像面坐标
  const ray = [0, 1, 2].map(i => from.f[i] + from.r[i] * planeX + from.u[i] * planeY);
  const depth = ray[0] * to.f[0] + ray[1] * to.f[1] + ray[2] * to.f[2];
  if (!(depth > 1e-3)) return { cx, cy };
  const px = ray[0] * to.r[0] + ray[1] * to.r[1] + ray[2] * to.r[2];
  const py = ray[0] * to.u[0] + ray[1] * to.u[1] + ray[2] * to.u[2];
  return { cx: 0.5 + px / (depth * 2 * tvTo * aspect), cy: 0.5 - py / (depth * 2 * tvTo) };
}

// 文档域归一化观测(供微跟踪器;viewportDetectionBoxes 是显示像素域,并存)。
export function viewportDetectionObservations(doc) {
  const w = Number(doc?.width), h = Number(doc?.height);
  if (!(w > 0) || !(h > 0) || !Array.isArray(doc.detections)) return [];
  return doc.detections.flatMap(det => {
    const box = Array.isArray(det?.box_xyxy) ? det.box_xyxy.map(Number) : [];
    if (!box.every(Number.isFinite) || box[2] <= box[0] || box[3] <= box[1]) return [];
    return [{ cx: (box[0] + box[2]) / 2 / w, cy: (box[1] + box[3]) / 2 / h,
      nw: (box[2] - box[0]) / w, nh: (box[3] - box[1]) / h,
      className: String(det.class_name ?? ''),
      confidence: Number.isFinite(Number(det.confidence)) ? Number(det.confidence) : 0 }];
  });
}

// web 微跟踪器:检测文档(received_at 去重由调用方负责)间最近邻关联赋稳定 id;
// 速度按“采集位姿补偿后的帧间位移”测EMA(剔除相机自转视差,只留目标自身运动),
// 连续丢失 MAX_MISSES 个文档后丢弃。评审 Q4:misses 只在新文档到达时增长——
// 长断流期间旧 track 不过期,恢复瞬间按旧速度关联会瞬跳/换 id;expire() 以
// track.t 墙龄(与 update 同一 received_at 时间域)独立过期,渲染循环逐帧调用。
export const VIEWPORT_TRACK_MAX_AGE_S = (VIEWPORT_TRACK_MAX_MISSES + 1) / 10;  // 10Hz 文档节拍 × misses 容忍
export function createViewportDetectionTracker({
  gate = VIEWPORT_TRACK_GATE_N, maxMisses = VIEWPORT_TRACK_MAX_MISSES,
  velocityAlpha = VIEWPORT_TRACK_VELOCITY_ALPHA, maxAgeS = VIEWPORT_TRACK_MAX_AGE_S } = {}) {
  let tracks = [], nextId = 1;
  return {
    get size() { return tracks.length; },
    tracks() { return [...tracks]; },
    reset() { tracks = []; nextId = 1; },
    expire(nowSec) {
      if (!Number.isFinite(nowSec)) return tracks.length;
      tracks = tracks.filter(track => !Number.isFinite(track.t) || nowSec - track.t <= maxAgeS);
      return tracks.length;
    },
    update(observations, tSec, capturePose) {
      if (!Number.isFinite(tSec)) return;
      const incoming = (observations || []).filter(o => Number.isFinite(o.cx) && Number.isFinite(o.cy));
      const pairs = [];
      tracks.forEach((track, ti) => {
        if (!Number.isFinite(track.t) || tSec <= track.t) return;
        const dt = tSec - track.t;
        // 门限随文档间隔自适应:2Hz 文档 0.5s 间隔下目标位移大,固定 0.15 会翻新
        // id(20261020 记录仪:315s 494 个 id)。按 dt/0.3 线性放大,上限 ×2.5。
        const gateEff = gate * Math.min(Math.max(dt / 0.3, 1), 2.5);
        const anchor = compensateViewportShift(track.pose, capturePose, track.cx, track.cy);
        incoming.forEach((obs, oi) => {
          const distance = Math.hypot(obs.cx - (anchor.cx + (track.vx || 0) * dt),
            obs.cy - (anchor.cy + (track.vy || 0) * dt));
          if (distance < gateEff) pairs.push({ ti, oi, distance, anchor, dt });
        });
      });
      pairs.sort((a, b) => a.distance - b.distance);
      const takenTracks = new Set(), takenObs = new Set(), matches = new Map();
      for (const pair of pairs) {
        if (takenTracks.has(pair.ti) || takenObs.has(pair.oi)) continue;
        takenTracks.add(pair.ti); takenObs.add(pair.oi); matches.set(pair.ti, pair);
      }
      tracks = tracks.map((track, ti) => {
        if (!takenTracks.has(ti)) return { ...track, misses: (track.misses || 0) + 1 };
        const { oi, anchor, dt } = matches.get(ti), obs = incoming[oi];
        const blend = (previous, inst) => Number.isFinite(previous)
          ? (1 - velocityAlpha) * previous + velocityAlpha * inst : inst;
        return { id: track.id, misses: 0, pose: capturePose, t: tSec,
          cx: obs.cx, cy: obs.cy, nw: obs.nw, nh: obs.nh,
          vx: blend(track.vx, (obs.cx - anchor.cx) / dt), vy: blend(track.vy, (obs.cy - anchor.cy) / dt),
          className: obs.className ?? track.className, confidence: obs.confidence ?? track.confidence };
      });
      for (const [oi, obs] of incoming.entries()) {
        if (takenObs.has(oi)) continue;
        tracks.push({ id: 'vt' + nextId++, misses: 0, pose: capturePose, t: tSec,
          cx: obs.cx, cy: obs.cy, nw: obs.nw, nh: obs.nh, vx: 0, vy: 0,
          className: obs.className, confidence: obs.confidence });
      }
      tracks = tracks.filter(track => (track.misses || 0) <= maxMisses);
    },
  };
}

// 显示帧放置:自转补偿到显示位姿 + 匀速外推(上限 VIEWPORT_EXTRAPOLATION_MAX_S,
// dt 负值/缺时刻钳 0)。返回归一化域 { cx, cy, nw, nh },由调用方乘 contained rect。
export function viewportTrackPlacement(track, displayPose, displaySec, aspect = 16 / 9) {
  if (!track || !Number.isFinite(track.cx) || !Number.isFinite(track.cy)) return null;
  const shifted = compensateViewportShift(track.pose, displayPose, track.cx, track.cy, aspect);
  const dt = Number.isFinite(displaySec) && Number.isFinite(track.t)
    ? Math.min(Math.max(displaySec - track.t, 0), VIEWPORT_EXTRAPOLATION_MAX_S) : 0;
  return { cx: shifted.cx + (track.vx || 0) * dt, cy: shifted.cy + (track.vy || 0) * dt,
    nw: track.nw, nh: track.nh };
}

// truth 吸附 debug 开关(默认关):开 = 已关联 track 的框改用 situation 真值投影
// 包围盒(零滞后,但属真值贴皮,非传感器语义)。
let viewportTruthSnapDebug = false;
export function setViewportTruthSnapDebug(enabled) { viewportTruthSnapDebug = enabled === true; }
export function viewportTruthSnapDebugEnabled() { return viewportTruthSnapDebug; }

// 检测框显示位置(P0 锁帧):默认 = 微跟踪器补偿/外推坐标(box 由调用方取
// viewportTrackPlacement 乘 rect 构造);snap=true(debug)且 track 带有效投影
// 包围盒时吸附 truth。
export function viewportBoxPlacement(box, track, rectWidth, rectHeight, snap = false) {
  if (snap && track && [track.left, track.top, track.width, track.height].every(Number.isFinite)
    && track.width > 0 && track.height > 0) {
    return { left: track.left * rectWidth, top: track.top * rectHeight,
      width: track.width * rectWidth, height: track.height * rectHeight, snapped: true };
  }
  return { left: box.left, top: box.top, width: box.width, height: box.height, snapped: false };
}

export function buildTwinPresentation(projection, chart, info, vo = null, documentRef = null, yoloKeys = null) {
  const raw = projection?.raw;
  if (!raw || !info || raw.run_id !== info.run_id) return null;
  const layers = chart.getLayerState();
  const visible = name => layers[name]?.visible !== false;
  // 契约 §3 裁剪门槛：图层开（=== true）发全部窗口内检测；关则只发
  // track_key ∈ yoloKeys 的条目（per-target 切换不依赖图层状态）。
  const detectionsLayerOn = layers.detections?.visible === true;
  const point = (north, east, label = '') => ({ east: info.origin_e + east, north: info.origin_n + north, label });
  const route = chart.getMissionRoute();
  const targets = targetsForDisplay(raw).filter(ship => ship.active !== false);
  const lines = [
    ['route', visible('route') ? route[0].map((n, i) => [n, route[1][i]]) : [], '#137fd1', 3, true],
    ['history', visible('history') ? raw.os?.trajectory : [], '#7e8991', 2, false],
    ['prediction', visible('prediction') ? raw.plans?.prediction_horizon : [], '#e99819', 3, false],
    ['previous', layers.previousPrediction?.visible ? raw.plans?.previous_prediction_horizon : [], '#a7a7a7', 1, true],
  ].map(([id, points, color, width, dashed]) => ({ id, color, width, dashed,
    points: (points || []).filter(p => p?.length >= 2 && p.slice(0, 2).every(Number.isFinite)).map(p => point(p[0], p[1])) }));
  if (visible('radarRange') && raw.os) {
    lines.push({ id: 'detection-ring', color: '#d4e9ee', width: 1.5, dashed: false,
      points: Array.from({ length: 129 }, (_, i) => point(raw.os.x + RADAR_DETECTION_RANGE_M * Math.cos(i * Math.PI / 64),
        raw.os.y + RADAR_DETECTION_RANGE_M * Math.sin(i * Math.PI / 64))) });
  }
  let disc = null;
  if (vo && raw.os && Number.isFinite(raw.os.length) && raw.os.length > 0 && documentRef) {
    const canvas = documentRef.createElement('canvas'); canvas.width = canvas.height = 240;
    const ctx = canvas.getContext('2d');
    if (drawVODecisionDisc(ctx, vo, 120, 120, 110, Number(vo.ownship_heading_rad) || 0, Number(vo.ownship_heading_rad) || 0)) {
      disc = { ...point(raw.os.x, raw.os.y), radius: raw.os.length * 3, png: canvas.toDataURL('image/png').split(',')[1] };
    }
  }
  // B 段（契约 §3）：A 段 raw.observations → Unity 检测数组。length_m/width_m
  // 改名 length/width（JsonUtility 按字段名逐字匹配）；key = det_id 原样；
  // track_key 原样（"" = 无关联，JsonUtility 不可 round-trip null）。
  const finite = (value, fallback) => Number.isFinite(value) ? value : fallback;
  const detections = (Array.isArray(raw.observations) ? raw.observations : [])
    .filter(o => o && Number.isFinite(o.north) && Number.isFinite(o.east))
    .map(o => ({ ...point(o.north, o.east), length: finite(o.length_m, 12), width: finite(o.width_m, 5),
      confidence: finite(o.confidence, 0), class_name: String(o.class_name ?? ''),
      sensor_id: finite(o.sensor_id, 0), key: String(o.det_id ?? ''), track_key: String(o.track_key ?? '') }))
    .filter(det => detectionsLayerOn || (det.track_key && yoloKeys?.has(det.track_key)));
  // DT 红区 = 不安全水域补集三角(后端 shapely CDT 一次性算好,local [north,east]);
  // 海图 safeWater 图层门控(2D 画布路径不消费 hazard_triangles,仅 DT 视景转发)。
  // 传输形态 = 平铺绝对 [east,north]×0.1m 数组:hazard 量大,对象数组(全精度 UTM)
  // 会把 presentation 推过 WebRTC 数据通道 ~256KB 消息上限并打死通道(20261016 实证)。
  const hazardSource = Array.isArray(raw.enc_navigation_area?.hazard_triangles)
    ? raw.enc_navigation_area.hazard_triangles : [];
  const hazardVisible = visible('safeWater') && hazardSource.length > 0;
  const hazardXy = hazardVisible
    ? hazardSource.flat().flatMap(v => [Math.round((info.origin_e + v[1]) * 10) / 10,
      Math.round((info.origin_n + v[0]) * 10) / 10]) : [];
  return { run_id: raw.run_id, seq: raw.seq, sim_time: raw.sim_time,
    ribbon: visible('route') ? routeRibbonQuads(route).flat().map(p => point(p.north, p.east)) : [],
    hazard_xy: hazardXy, hazard_count: hazardVisible ? hazardSource.length : 0, hazard_visible: hazardVisible,
    waypoints: route[0].map((north, i) => point(north, route[1][i], 'WPT' + (i + 1))),
    waypoints_visible: visible('waypoints'), ships_visible: visible('ships'), lines, vo: disc,
    time_markers: visible('prediction') ? predictionMarkers(raw, { includeEndpoint: true }).map(m => point(...m.point, '+' + m.elapsed.toFixed(0) + 's')) : [],
    targets: targets.map(ship => ({ ...point(ship.x, ship.y), id: String(ship.id), key: targetKey(raw.run_id, ship),
      truth: raw.executed_tracker === 'god', length: ship.length || 12, width: ship.width || 5,
      existence: Number.isFinite(ship.existence) ? ship.existence : -1 })),
    detections,
  };
}

// 20261023 DT HUD 顶栏信息柱取值：与左栏 OWN SHIP 卡同源同算（app.js#
// updateOwnshipTelemetry 消费同一份 projection：STW=nav.sog、COG=nav.cog
// （缺席回退 nav.psi）、DEPTH=os.floor_depth_m），避免双来源显示矛盾。
// ROLL 左栏没有对应读数，取 Unity motion 回显 = 画面实际横摇（后端横摇在场
// 时 twinRollDeg 即后端值，两路同源）；motion 缺席回退 os.roll_rad。
export function buildTwinTopbarReadouts(projection, motion = null) {
  const nav = projection?.navigation || {}, os = projection?.raw?.os || {};
  const toDeg = rad => rad * 180 / Math.PI;
  const normalize = deg => ((deg % 360) + 360) % 360;
  const headingDeg = Number.isFinite(nav.psi) ? normalize(toDeg(nav.psi)) : null;
  const cogDeg = Number.isFinite(nav.cog) ? normalize(toDeg(nav.cog)) : headingDeg;
  const rollDeg = Number.isFinite(motion?.roll_deg) ? motion.roll_deg
    : os.has_roll && Number.isFinite(os.roll_rad) ? toDeg(os.roll_rad) : null;
  return {
    stw: Number.isFinite(nav.sog) ? (nav.sog * 1.94384).toFixed(1) : '—',
    cog: cogDeg === null ? '—' : String(Math.round(cogDeg)).padStart(3, '0'),
    depth: Number.isFinite(os.floor_depth_m) ? String(Math.round(os.floor_depth_m)) : '—',
    roll: rollDeg === null ? '—' : (rollDeg > 0 ? '+' : '') + rollDeg.toFixed(1),
  };
}

// OpenBridge DOM stays outside the video. All placements are taken from a decoded
// frame, never from the newest camera heartbeat or a second Cesium camera.
export function createTwinSituationOverlay({ host, video, chart, info, client, onSelect, onCameraChange = () => {}, getPlannerSurface, requestVODecisionSpace, getOwnship = () => null }) {
  const doc = host.ownerDocument;
  const root = doc.createElement('div'); root.className = 'twin-situation-overlay'; root.hidden = true;
  const layer = doc.createElement('div'); layer.className = 'scene3d-pois';
  const waypoints = doc.createElement('div'); waypoints.className = 'scene3d-waypoints';
  const edges = doc.createElement('div'); edges.className = 'scene3d-edges';
  const aisLayer = doc.createElement('div'); aisLayer.className = 'twin-ais-markers';
  const detectionsLayer = doc.createElement('div'); detectionsLayer.className = 'twin-detections';
  const badges = doc.createElement('div'); badges.className = 'twin-existence-badges';
  const card = doc.createElement('obc-poi-card'); card.className = 'scene3d-card'; card.hidden = true; card.hasCloseButton = true;
  const cardBody = doc.createElement('div'); cardBody.className = 'scene3d-card-body'; card.append(cardBody);
  const cardIcon = doc.createElement('obi-vessel-generic-default-outlined'); cardIcon.slot = 'poi-icon'; card.append(cardIcon);
  const cardAlert = doc.createElement('obc-alert-frame'); cardAlert.className = 'scene3d-card-alert'; cardAlert.type = 'regular'; cardAlert.thickness = 'large'; cardAlert.hidden = true; card.append(cardAlert);
  // dt-yolo 收编轮:markerCover("DT · N 个目标"角标)移除;相机预设 toolbar 迁出
  // overlay 根、挂 host 与"联动"同排右上角(视口 letterbox 不再牵动预设按钮位置)。
  const toolbar = doc.createElement('div'); toolbar.className = 'scene3d-toolbar';
  // dt-yolo：'目标跟踪' 预设随单击跟踪一并移除——预设只留跟随相机的三键。
  for (const [preset, label] of [['bridge', '舰桥'], ['chase', '追随'], ['top', '俯视']]) {
    const button = doc.createElement('button'); button.textContent = label; button.dataset.camera = preset;
    button.addEventListener('click', () => {
      onCameraChange();
      client()?.sendCamera?.(preset);
    }); toolbar.append(button);
  }
  root.append(detectionsLayer, badges, layer, waypoints, edges, aisLayer, card); host.append(root, toolbar);
  const compass = createSceneCompass({ host: root, onSelect: id => choose(id) });
  const compassRoot = root.querySelector('.scene3d-compass');
  // 20261023 DT HUD 顶栏信息柱：罗盘由 CSS 收窄至中央 50%，左右各 1/4 放圆角
  // 矩形信息框（与罗盘条带同款半透明材质、内容居中）。左组 STW/COG，右组
  // DEPTH/ROLL；数值=buildTwinTopbarReadouts（与左栏同源）；与罗盘同显隐
  // （俯视/无本船数据时一并收起）。
  const topbar = doc.createElement('div'); topbar.className = 'twin-topbar-info'; topbar.hidden = true;
  topbar.setAttribute('aria-label', '本船航行读数');
  const topbarGroups = {};
  for (const side of ['left', 'right']) {
    const group = doc.createElement('div'); group.className = `twin-topbar-group twin-topbar-group--${side}`;
    topbar.append(group); topbarGroups[side] = group;
  }
  const topbarNumber = (side, name, unit, title) => {
    const box = doc.createElement('div'); box.className = 'twin-topbar-box'; box.title = title;
    const label = doc.createElement('span'); label.className = 'twin-topbar-box-label'; label.textContent = name;
    const value = doc.createElement('span'); value.className = 'twin-topbar-box-value';
    const number = doc.createElement('strong'); number.className = 'twin-topbar-box-number'; number.textContent = '—';
    const unitNode = doc.createElement('small'); unitNode.className = 'twin-topbar-box-unit'; unitNode.textContent = unit;
    value.append(number, unitNode); box.append(label, value); topbarGroups[side].append(box);
    return number;
  };
  const topbarStw = topbarNumber('left', 'STW', 'kn', '对水航速（与左栏 STW 同源）');
  const topbarCog = topbarNumber('left', 'COG', '°', '对地航向（与左栏 COG 同源）');
  const topbarDepth = topbarNumber('right', 'DEPTH', 'm', '船位 ENC 水深分层下限（与左栏 DPTH 同源）');
  const topbarRoll = topbarNumber('right', 'ROLL', '°', '横摇（画面实际值）');
  let topbarSignature = null;
  const renderTopbar = projection => {
    topbar.hidden = compassRoot?.hidden ?? true;
    if (topbar.hidden) return;
    const readouts = buildTwinTopbarReadouts(projection, client()?.lastState?.motion ?? null);
    const signature = readouts.stw + readouts.cog + readouts.depth + readouts.roll;
    if (signature === topbarSignature) return;
    topbarSignature = signature;
    topbarStw.textContent = readouts.stw;
    topbarCog.textContent = readouts.cog;
    topbarDepth.textContent = readouts.depth;
    topbarRoll.textContent = readouts.roll;
  };
  root.append(topbar);
  const sample = doc.createElement('canvas'); sample.width = 32; sample.height = 1;
  const sampleContext = sample.getContext('2d', { willReadFrequently: true }); sampleContext.imageSmoothingEnabled = false;
  const models = new Map(), pois = new Map(), waypointNodes = new Map(), aisNodes = new Map();
  // Keep absent nodes cached for three frames, but hide rejected placements immediately.
  const waypointAbsent = new Map();
  const detectionNodes = new Map(), badgeNodes = new Map(), yoloKeys = new Set();
  const viewportDetectionNodes = new Map();
  let latest = null, frame = null, frameId = null, selectedKey = null, disposed = false;
  // dt-yolo 视口检测：最新 viewport_detections 文档 + 本地接收时刻（fold 防乱序
  // 回退）；全局三态样式与 per-run 清空照 yoloKeys 模式。P3 另存 viewport_tracks
  // （confirmed 航迹，数据块优先挂它，缺席回退裸检测 + TRK/DET 角标）。
  let viewportDetectionsState = null, viewportTracksState = null, viewportYoloRunId = null, viewportYoloStyle = 0;
  // P0 锁帧:逐帧位姿历史({tSec,frameId,pose}) + 检测微跟踪器 + 已喂跟踪器的
  // 文档 received_at(renderFrame 高频重入,按 received_at 去重喂一次)。
  const poseHistory = [];
  const detectionTracker = createViewportDetectionTracker();
  // 验收诊断记录仪:逐帧采样渲染态(guard/track/DOM),15s 批量 POST
  // /api/viewport-box-log;fetch/window 缺席(单测环境)时静默关闭。只读渲染态。
  const vpBoxLog = [];
  const vpKeepUntil = new Map();
  let vpLastGuard = null, vpLastGuardAt = 0;
  const noteVp = entry => { if (vpBoxLog.length < 6000) vpBoxLog.push({ t: Math.round(performance.now()), ...entry }); };
  const flushVp = () => {
    const lines = vpBoxLog.splice(0, vpBoxLog.length);
    if (!lines.length) return;
    fetch('/api/viewport-box-log', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client: { href: typeof location !== 'undefined' ? location.href : '' }, lines }) })
      .catch(() => { for (const line of lines.slice(-500)) if (vpBoxLog.length < 6000) vpBoxLog.push(line); });
  };
  if (typeof fetch === 'function' && typeof window !== 'undefined') {
    noteVp({ boot: 1 });
    let vpTicks = 0;
    setInterval(() => {
      vpTicks++;
      if (vpBoxLog.length) flushVp();
      else if (vpTicks % 4 === 0) vpBoxLog.push({ t: Math.round(performance.now()), beat: 1 });
    }, 15000);
    setTimeout(flushVp, 2000);   // boot 行 2s 即上报,端到端自证
    window.addEventListener('pagehide', () => {   // 关页/切走兜底:sendBeacon 不怕页面卸载
      if (!vpBoxLog.length || typeof navigator.sendBeacon !== 'function') return;
      navigator.sendBeacon('/api/viewport-box-log', new Blob([JSON.stringify(
        { client: { href: location.href, beacon: 1 }, lines: vpBoxLog.splice(0, vpBoxLog.length) })],
        { type: 'application/json' }));
    });
    window.__dtVpLogInfo = () => ({ buffered: vpBoxLog.length, kept: vpKeepUntil.size });
  }
  // 检测文档 SSE(到达即推):全量文档车随仿真步 ~2Hz 重建、PAUSED 冻结(20261020
  // 记录仪裁决);检测属显示层,独立通道 6-10Hz 直供,renderFrame 合并取新者。
  let viewportDetectionsLive = null;
  let vpEventSource = null;
  if (typeof EventSource !== 'undefined') {
    vpEventSource = new EventSource('/api/viewport-detections/stream');
    vpEventSource.onmessage = event => {
      try {
        viewportDetectionsLive = foldViewportDetections(viewportDetectionsLive,
          { viewport_detections: JSON.parse(event.data) }, performance.now());
      } catch { /* 断流重连由 EventSource 自理 */ }
    };
  }
  let trackedDetectionsReceivedAt;
  let lastSent = null, lastPick = null, lastVideoAt = 0, pointer = null, yoloRunId = null;
  let presentationClient = null, presentationAttachment = null;
  let matched = 0, unmatched = 0;
  const frameCosts = { count: 0, rtpMatched: 0, pixelReads: 0, markerMs: 0, overlayMs: 0, markerMaxMs: 0, overlayMaxMs: 0 };
  let wasVisible = false, hiddenSince = null, hiddenEvents = 0, hiddenTotalMs = 0, hiddenMaxMs = 0;
  let diagnostics = null, lastHidden = null;
  function observeVisibility(timestamp) {
    const reason = !root.hidden ? null : timestamp - lastVideoAt >= 500 ? 'video-stale'
      : frameId === null ? 'marker-invalid' : !frame ? 'frame-missing'
        : frame.landscape?.ready === false ? 'landscape' : 'projection-missing';
    if (root.hidden && wasVisible && hiddenSince === null) {
      hiddenSince = timestamp; hiddenEvents++;
      lastHidden = { at: Date.now(), reason, decoded: frameId, sourceSeq: frame?.source_seq ?? null,
        available: client()?.situationFrameRange ?? null,
        receivedFrame: client()?.situationFrame?.(frameId) ? { width: client().situationFrame(frameId).width,
          height: client().situationFrame(frameId).height, run: client().situationFrame(frameId).run_id } : null };
    }
    const hiddenMs = hiddenSince === null ? 0 : Math.max(0, timestamp - hiddenSince);
    hiddenMaxMs = Math.max(hiddenMaxMs, hiddenMs);
    if (!root.hidden) { wasVisible = true; hiddenTotalMs += hiddenMs; hiddenSince = null; }
    diagnostics = { decoded: frameId, matched, unmatched, sourceSeq: frame?.source_seq ?? null,
      projectionSeq: latest?.raw?.seq ?? null, sync: root.hidden ? 'waiting' : 'matched',
      reason, lastHidden,
      hiddenEvents, hiddenTotalMs: hiddenTotalMs + (root.hidden ? hiddenMs : 0), hiddenMaxMs };
  }
  function choose(id, key = null) {
    const projection = models.get(frame?.source_seq) || latest;
    const ship = targetsForDisplay(projection?.raw || {}).find(ship => String(ship.id) === String(id));
    // dt-yolo：选中只驱动详情卡/高亮，不再跟踪相机（trackSelected/camera_target 已移除）。
    selectedKey = key || (ship ? targetKey(projection.raw.run_id, ship) : null);
    if (onSelect) onSelect(id); else chart.selectTarget(id);
    renderFrame();
  }
  card.addEventListener('close-click', () => choose(null));
  // 契约 §6.3：右键不再送 Unity pick（button !== 0 直接置空 pointer）。
  const down = event => {
    if (event.button !== 0) { pointer = null; return; }
    pointer = { x: event.clientX, y: event.clientY };
  };
  const up = event => {
    if (!pointer || Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) > 4) { pointer = null; return; }
    pointer = null;
    if (!frame || root.hidden) return;
    const rect = root.getBoundingClientRect(), x = (event.clientX - rect.left) / rect.width, y = (event.clientY - rect.top) / rect.height;
    if (x >= 0 && x <= 1 && y >= 0 && y <= 1) client()?.sendPick?.(frame.run_id, frame.frame_id, x, y);
  };
  // 右键目标：per-key 检测模式循环（fused → yolo → fused）。未命中不拦截，
  // 保留相机右键缩放拖拽原行为（契约 §6.3.2）。
  const contextMenu = event => {
    if (!frame || root.hidden) return;
    const rect = root.getBoundingClientRect(), x = (event.clientX - rect.left) / rect.width, y = (event.clientY - rect.top) / rect.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    const hit = pickTwinTarget(frame, x, y);
    if (!hit) return;
    event.preventDefault();
    toggleYoloKey(yoloKeys, hit.key);
  };
  video.addEventListener('pointerdown', down); video.addEventListener('pointerup', up);
  video.addEventListener('contextmenu', contextMenu);

  function renderFrame() {
    const videoBox = video.getBoundingClientRect(), hostBox = host.getBoundingClientRect();
    const rect = containedVideoRect(videoBox.width, videoBox.height, video.videoWidth, video.videoHeight);
    if (!rect) { root.hidden = true; noteVp({ r: 'norect', hid: 1 }); return; }
    rect.left += videoBox.left - hostBox.left; rect.top += videoBox.top - hostBox.top;
    const projection = frame && models.get(frame.source_seq);
    if (!projection || projection.raw.run_id !== frame.run_id) { root.hidden = true; noteVp({ r: 'noproj', hid: 1 }); return; }
    Object.assign(root.style, { left: rect.left + 'px', top: rect.top + 'px', width: rect.width + 'px', height: rect.height + 'px' });
    if (frame.landscape?.ready === false) {
      // A heartbeat can release the video if hidden-video callbacks are throttled.
      if (!client()?.lastState?.landscape?.ready) video.style.visibility = 'hidden';
      root.hidden = true; noteVp({ r: 'landscape', hid: 1 }); return;
    }
    video.style.visibility = '';
    root.hidden = false;
    root.dataset.camera = frame.camera;
    if (frame.camera_pose) root.dataset.cameraPose = JSON.stringify(frame.camera_pose);
    // P0 锁帧:位姿历史按 frame_id 去重追帧(renderFrame 可对同一帧重入),3s 窗
    // 修剪;检测文档按 received_at 去重喂微跟踪器(采集位姿 = 历史插值)。
    if (frame.camera_pose && Number.isFinite(frame._receivedAt)
      && poseHistory[poseHistory.length - 1]?.frameId !== frame.frame_id) {
      poseHistory.push({ tSec: frame._receivedAt / 1000, frameId: frame.frame_id, pose: frame.camera_pose });
      const cutoff = frame._receivedAt / 1000 - POSE_HISTORY_SPAN_S;
      while (poseHistory.length > 1 && poseHistory[0].tSec < cutoff) poseHistory.shift();
    }
    // 评审 Q4:断流期间 update 不再被调、misses 不增长——按 track.t 墙龄独立
    // 过期(与 detectionCaptureTimeSec 同一 received_at 时间域),恢复瞬间旧
    // track 已出窗,不再按陈旧速度关联/瞬跳。renderFrame 逐帧调用,开销 O(n)。
    detectionTracker.expire(Date.now() / 1000);
    const trackedDoc = viewportDetectionsState?.doc;
    if (trackedDoc && trackedDoc.received_at !== trackedDetectionsReceivedAt) {
      trackedDetectionsReceivedAt = trackedDoc.received_at;
      const captureSec = detectionCaptureTimeSec(trackedDoc.received_at);
      if (captureSec !== null) detectionTracker.update(viewportDetectionObservations(trackedDoc),
        captureSec, poseAtCapture(poseHistory, captureSec));
    }
    toolbar.querySelectorAll('button').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.camera === frame.camera));
    });
    // dt-yolo：YOLO 视口模式 = "YOLO 检测"图层勾选且 viewport_detections 新鲜。
    // 激活时整帧抑制 contacts（标牌/IPDA 徽标/AIS 符号/离屏边钮随 contacts=[]
    // 自然清场），旧 NE 域 .twin-detections 层同样跳过（避免双框）。
    const yoloMode = yoloViewportMode(chart.getLayerState(), viewportDetectionsState, performance.now());
    const ships = targetsForDisplay(projection.raw), byKey = new Map(ships.map(ship => [targetKey(frame.run_id, ship), ship]));
    const selected = chart.getSelectedTargetId();
    if (selectedKey && !byKey.has(selectedKey)) { selectedKey = null; chart.selectTarget(null); onSelect?.(null); }
    compass.render(projection, frame.camera, chart.getLayerState().ships?.visible !== false);
    renderTopbar(projection);
    const compassHeight = root.querySelector('.scene3d-compass')?.offsetHeight || 0;
    const visibleY = (frame.targets || []).filter(p => p.visible).map(p => p.y * rect.height);
    const lowHorizon = visibleY.length > 0 && Math.min(...visibleY) < compassHeight + 80;
    root.classList.toggle('twin-low-horizon', lowHorizon);
    const topInset = lowHorizon ? 24 : Math.min(rect.height / 3, compassHeight + 12);
    // 契约 §6.4：C 段帧回包检测投影（旧 Unity 无 detections → 空数组）；
    // YOLO 视口模式下跳过（该层无数据时本来就不画，加 gate 明确防双框）。
    const frameDetections = yoloMode ? [] : (Array.isArray(frame.detections) ? frame.detections : []);
    const visibleDetections = frameDetections.filter(det => det && det.visible
      && [det.left, det.top, det.width, det.height].every(Number.isFinite));
    // yoloKeys 内目标且当前帧存在可见关联检测 → POI 隐藏（保留节点/选择态），
    // 画检测框；无关联检测 → 回退融合显示（契约 §6.4）。
    const yoloByKey = new Map();
    for (const p of frame.targets || []) {
      if (yoloKeys.has(p.key)) {
        const det = latestDetectionForTrack(visibleDetections, p.key);
        if (det) yoloByKey.set(p.key, det);
      }
    }
    const wanted = new Set(), edgeRecords = [], aisWanted = new Set(), badgeWanted = new Set();
    // YOLO 视口模式：contacts 置空 → 下方 POI/徽标/AIS/离屏边钮整段跳过，
    // 且末尾按 wanted 空集清场（保留节点创建代码路径不重入）。
    const contacts = yoloMode ? [] : (frame.targets || []).flatMap(p => {
      const ship = byKey.get(p.key); if (!ship) return [];
      const model = targetPresentation(projection, ship, info), x = p.x * rect.width, y = p.y * rect.height;
      const selectedContact = String(selected) === p.id;
      const primary = String(projection.risk?.primary?.targetId ?? projection.risk?.primary?.target_id) === p.id
        && (projection.risk?.primary?.generation ?? null) === (ship.generation ?? null);
      const available = y - topInset;
      const blocks = (selectedContact || primary) && available >= 300 ? model.blocks : available >= 170 ? [model.blocks[1]] : [];
      return [{ p, ship, model, x, y, blocks, focus: selectedContact || primary,
        key: p.key, height: blocks.length ? blocks.length * 64 + 80 : 48,
        priority: selectedContact ? 3 : primary ? 2 : model.alert.state === 'alarm' ? 1 : 0 }];
    });
    const layout = layoutTwinLabels(contacts.filter(c => c.p.visible && c.x >= 24 && c.x <= rect.width - 24 && c.y >= topInset),
      rect.width - (selected !== null && selected !== undefined ? 340 : 0), topInset);
    for (const { p, ship, model, x, y, blocks, focus } of contacts) {
      if (!p.visible || x < 24 || x > rect.width - 24 || y < topInset || y > rect.height - 16) {
        if (focus) edgeRecords.push({ p, model, ...offscreenDirection({ x, y }, rect.width, rect.height, p.depth > 0, p.x >= 0.5) });
        continue;
      }
      wanted.add(p.key);
      let record = pois.get(p.key);
      if (!record) {
        const target = doc.createElement('obc-poi'); target.animatePosition = false;
        const poi = doc.createElement('obc-poi-button-vessel'); poi.slot = 'button';
        poi.append(doc.createElement('obi-vessel-generic-default-outlined'));
        target.hasHeader = true; target.headerContent = p.id; target.hasPointer = true;
        poi.dataset.targetKey = p.key; poi.setAttribute('aria-label', 'TS' + p.id + ' 目标详情');
        target.addEventListener('click', () => choose(p.id, p.key)); target.append(poi); layer.append(target);
        record = { target, poi }; pois.set(p.key, record);
      }
      const { target, poi } = record;
      const yoloDet = yoloByKey.get(p.key) || null;
      // 契约 §6.4：yolo 模式且有关联检测 → POI 置 hidden（不删除，保留选择态）。
      target.hidden = Boolean(yoloDet);
      const existence = Number.isFinite(ship.existence) ? ship.existence
        : Number.isFinite(p.existence) ? p.existence : null;   // 帧 echo 仅作回退（§6.1）
      if (!yoloDet && Number.isFinite(existence) && existence > 0) {
        badgeWanted.add(p.key);
        let chip = badgeNodes.get(p.key);
        if (!chip) {
          chip = doc.createElement('span'); chip.className = 'twin-existence-badge';
          badges.append(chip); badgeNodes.set(p.key, chip);
        }
        chip.textContent = 'IPDA ' + Math.round(existence * 100) + '%';
        chip.style.color = trackConfidenceColor(existence);
        chip.style.left = x + 'px'; chip.style.top = y + 'px';
      }
      const placement = layout.get(p.key);
      if (updateTargetPoi(poi, { ...model, blocks: placement?.compact ? [] : blocks }))
        target.data = placement?.compact ? [] : blocks;
      applyTargetAppearance(target, model.alert);
      target.state = model.alert.poiState; target.value = model.alert.state === 'unchecked' ? 'unchecked' : 'checked';
      if (model.alert.state === 'unchecked') {
        target.style.setProperty('--element-active-color', 'inherit');
        poi.style.setProperty('--element-active-color', 'inherit');
      }
      const lift = placement?.lift ?? 0;
      target.x = placement?.x ?? x; target.y = lift; target.buttonY = y - lift;
      target.buttonOffsetX = 0; target.targetOffsetX = x - target.x;
      target.type = target.targetOffsetX ? 'offset' : 'line';
      target.selected = String(selected) === p.id;
      target.relativeDirection = (ship.psi * 180 / Math.PI - frame.camera_yaw + 360) % 360;
      poi.relativeDirection = target.relativeDirection;
      poi.title = 'TS' + p.id + ' · ' + model.alert.name;
      if (ship.ais && chart.getLayerState().aisTargets?.visible !== false) {
        aisWanted.add(p.key); let button = aisNodes.get(p.key);
        if (!button) {
          button = doc.createElement('button'); button.className = 'twin-ais-marker'; button.append(doc.createElement('img'));
          button.addEventListener('click', () => choose(p.id, p.key)); aisLayer.append(button); aisNodes.set(p.key, button);
        }
        const rank = { alarm: 3, caution: 2, checked: 1 }[model.alert.state] || 0;
        const state = aisSymbolState(ship.ais, rank), img = button.firstElementChild;
        img.src = AIS_SYMBOL_ASSETS[state]; img.style.width = (AIS_SYMBOL_SIZES[state] || 24) + 'px';
        img.style.transform = 'rotate(' + ((ship.psi * 180 / Math.PI - frame.camera_yaw + 360) % 360) + 'deg)';
        button.style.left = x + 'px'; button.style.top = y + 'px'; button.setAttribute('aria-label', 'TS' + p.id + ' AIS 详情');
      }
    }
    for (const [key, record] of pois) if (!wanted.has(key)) { record.target.remove(); pois.delete(key); }
    for (const [key, node] of aisNodes) if (!aisWanted.has(key)) { node.remove(); aisNodes.delete(key); }
    // 检测框渲染（契约 §6.2/§6.4）：图层开 → 全量半透明叠加；yolo 切换目标 →
    // 青色识别框+置信度标签（同一检测同时服务两模式时 yolo 样式优先）。
    const detectionsLayerOn = chart.getLayerState().detections?.visible === true;
    const detectionWanted = new Set();
    for (const det of visibleDetections) {
      const asYolo = [...yoloByKey.values()].some(d => d.key === det.key);
      if (!detectionsLayerOn && !asYolo) continue;
      detectionWanted.add(det.key);
      let node = detectionNodes.get(det.key);
      if (!node) {
        node = doc.createElement('div'); node.className = 'twin-detection';
        for (const corner of ['tl', 'tr', 'bl', 'br']) {
          const mark = doc.createElement('i'); mark.className = 'twin-detection-corner twin-detection-corner--' + corner;
          node.append(mark);
        }
        const label = doc.createElement('span'); label.className = 'twin-detection-label';
        node.append(label);
        detectionNodes.set(det.key, node); detectionsLayer.append(node);
      }
      node.classList.toggle('twin-detection--yolo', asYolo);
      node.classList.toggle('twin-detection--overlay', !asYolo);
      node.style.left = det.left * rect.width + 'px'; node.style.top = det.top * rect.height + 'px';
      node.style.width = det.width * rect.width + 'px'; node.style.height = det.height * rect.height + 'px';
      node.querySelector('.twin-detection-label').textContent =
        String(det.class_name ?? '') + ' : ' + Math.round((Number(det.confidence) || 0) * 100) + '%';
    }
    for (const [key, node] of detectionNodes) if (!detectionWanted.has(key)) { node.remove(); detectionNodes.delete(key); }
    // dt-yolo 视口检测层（viewport_detections@1）：绿框 + `class : NN%` 标签，
    // 坐标 = box_xyxy / 文档 width×height 归一化 × contained rect。单击任一框
    // 循环全局三态（0=框+标签，1=+导航数据块，2=无框仅数据块）；数据块导航量
    // 与 POI 同源（targetPresentation.blocks），关联不到 track 的检测无导航数据。
    detectionsLayer.dataset.yoloStyle = String(viewportYoloStyle);
    const viewportWanted = new Set();
    let vpSnap = null;
    if (yoloMode) {
      // P0 锁帧渲染:跟踪器位置(自转补偿+匀速外推)× contained rect;本船抑制
      // (水线多边形 guard)与 track↔导航数据关联都在渲染中心上判定(显示层
      // 过滤);truth 吸附仅 debug 开关(默认关)。
      const aspect = (frame?.width || 16) / (frame?.height || 9);
      // guard 缓存:pose/ownship 瞬时缺席不再闪放本船框(0.5s 内复用上次 guard)。
      let guard = ownShipViewportGuard(frame?.camera_pose, getOwnship(), aspect);
      if (!guard && vpLastGuard && performance.now() - vpLastGuardAt < 500) guard = vpLastGuard;
      else if (guard) { vpLastGuard = guard; vpLastGuardAt = performance.now(); }
      const displaySec = Number.isFinite(frame?._receivedAt) ? frame._receivedAt / 1000 : null;
      // 记录仪采样:guard 形态/pose/ownship/逐 track 放置与抑制判定。
      vpSnap = { cam: frame.camera,
        pose: frame.camera_pose ? [frame.camera_pose.yaw_deg, frame.camera_pose.pitch_deg, frame.camera_pose.fov_deg] : null,
        own: getOwnship() ? 1 : 0,
        guard: guard ? (guard.polygons?.length ? 'poly' : (guard.floorY != null ? 'floor' : 'none')) : 'null',
        ds: Number.isFinite(displaySec) ? +displaySec.toFixed(3) : null,
        doc: viewportDetectionsState?.doc
          ? { n: (viewportDetectionsState.doc.detections || []).length, ra: viewportDetectionsState.doc.received_at,
              om: viewportDetectionsState.doc.ownship_mask ?? null } : null,
        tracks: [] };
      // 渲染前重叠去重(20261020 二轮记录仪:同一目标多框并存——本船甲板多点
      // 检出/目标结构双检/保活换帧交叠):IoU>0.4 或中心落入他框只留强者(置信
      // 度优先,同置信留 id 较小=更早 track)。
      const vpCandidates = [];
      for (const track of detectionTracker.tracks()) {
        const locked = viewportTrackPlacement(track, frame?.camera_pose, displaySec, aspect);
        if (!locked || !Number.isFinite(locked.cx) || !Number.isFinite(locked.cy)) continue;
        const suppressed = suppressOwnShipBoxes([{ cx: locked.cx, cy: locked.cy }], guard).length === 0;
        vpSnap.tracks.push([track.id, +locked.cx.toFixed(3), +locked.cy.toFixed(3),
          +(track.confidence || 0).toFixed(2), suppressed ? 1 : 0, +track.t.toFixed(3)]);
        if (suppressed) continue;
        vpCandidates.push({ track, locked });
      }
      vpCandidates.sort((a, b) => (b.track.confidence || 0) - (a.track.confidence || 0)
        || a.track.id.localeCompare(b.track.id, undefined, { numeric: true }));
      const vpAccepted = [];
      const vpIou = (a, b) => {
        const ix = Math.max(0, Math.min(a.cx + a.nw / 2, b.cx + b.nw / 2) - Math.max(a.cx - a.nw / 2, b.cx - b.nw / 2));
        const iy = Math.max(0, Math.min(a.cy + a.nh / 2, b.cy + b.nh / 2) - Math.max(a.cy - a.nh / 2, b.cy - b.nh / 2));
        const inter = ix * iy, uni = a.nw * a.nh + b.nw * b.nh - inter;
        return uni > 0 ? inter / uni : 0;
      };
      for (const cand of vpCandidates) {
        const dup = vpAccepted.some(acc => vpIou(acc.locked, cand.locked) > 0.4
          || (cand.locked.cx > acc.locked.cx - acc.locked.nw / 2 && cand.locked.cx < acc.locked.cx + acc.locked.nw / 2
            && cand.locked.cy > acc.locked.cy - acc.locked.nh / 2 && cand.locked.cy < acc.locked.cy + acc.locked.nh / 2));
        if (dup) { vpSnap.dedup = (vpSnap.dedup || 0) + 1; continue; }
        vpAccepted.push(cand);
      }
      for (const { track, locked } of vpAccepted) {
        const key = track.id;
        viewportWanted.add(key);
        let node = viewportDetectionNodes.get(key);
        if (!node) {
          node = doc.createElement('button'); node.type = 'button'; node.className = 'twin-vp-detection';
          const tag = doc.createElement('span'); tag.className = 'twin-vp-detection-tag';
          const src = doc.createElement('span'); src.className = 'twin-vp-detection-src';
          const data = doc.createElement('span'); data.className = 'twin-vp-detection-data';
          node.append(tag, src, data);
          node.addEventListener('click', () => { viewportYoloStyle = cycleViewportYoloStyle(viewportYoloStyle); renderFrame(); });
          viewportDetectionNodes.set(key, node); detectionsLayer.append(node);
        }
        const ship = byKey.get(associateViewportDetections([locked], frame.targets || [])[0] || '');
        // P3 数据源裁决：viewport_tracks confirmed 航迹优先（滤波后 brg/rng/conf，
        // 跟踪时刻冻结不追帧）；track 缺席/关联不上 → 回退裸检测数据块（truth
        // 关联来源不变）；角标 TRK/DET 标示来源。
        const vtrack = associateViewportTrack(
          viewportTracksFresh(viewportTracksState, performance.now()) ? viewportTracksState.doc.tracks : null,
          locked, frame?.camera_pose, aspect);
        const { source, blocks } = viewportTrackData(vtrack, ship ? targetPresentation(projection, ship, info).blocks : []);
        node.hidden = viewportYoloStyle === 2 && blocks.length === 0;   // 无导航数据的 style2 = 完全无标注
        const placement = viewportBoxPlacement(
          { left: (locked.cx - track.nw / 2) * rect.width, top: (locked.cy - track.nh / 2) * rect.height,
            width: track.nw * rect.width, height: track.nh * rect.height },
          ship, rect.width, rect.height, viewportTruthSnapDebug);
        node.style.left = placement.left + 'px'; node.style.top = placement.top + 'px';
        node.style.width = placement.width + 'px'; node.style.height = placement.height + 'px';
        node.querySelector('.twin-vp-detection-tag').textContent =
          track.className + ' : ' + Math.round((track.confidence || 0) * 100) + '%';
        node.querySelector('.twin-vp-detection-src').textContent = source;
        node.querySelector('.twin-vp-detection-src').classList.toggle('twin-vp-detection-src--trk', source === 'TRK');
        node.querySelector('.twin-vp-detection-data').textContent =
          blocks.map(block => [block.label, block.value, block.unit].filter(Boolean).join(' ')).join(' · ');
      }
    }
    if (vpSnap) { vpSnap.dom = viewportDetectionNodes.size; noteVp(vpSnap); }
    // 框保活 0.35s:抑制/放置的逐帧抖动不再即时删建 DOM(闪动来源),过期才真删。
    const vpNowMs = performance.now();
    for (const [key, node] of viewportDetectionNodes) {
      if (viewportWanted.has(key)) { vpKeepUntil.set(key, vpNowMs + 350); continue; }
      if (vpNowMs > (vpKeepUntil.get(key) || 0)) { node.remove(); viewportDetectionNodes.delete(key); vpKeepUntil.delete(key); }
    }
    for (const [key, node] of badgeNodes) if (!badgeWanted.has(key)) { node.remove(); badgeNodes.delete(key); }
    edges.replaceChildren(...edgeRecords.map(({ p, model, edge, arrow }, index) => {
      const button = doc.createElement('button'); button.className = edge; button.textContent = arrow + ' TS' + p.id;
      button.style.setProperty('--edge-index', index); applyTargetAppearance(button, model.alert);
      button.addEventListener('click', () => choose(p.id, p.key)); return button;
    }));
    const waypointLayout = layoutTwinWaypoints(frame.waypoints || [], frame.time_markers || [], rect.width, rect.height, topInset);
    for (const [label, placement] of waypointLayout) {
      let node = waypointNodes.get(label);
      if (!node) {
        node = doc.createElement('div'); node.className = 'scene3d-waypoint' + (label.startsWith('+') ? ' twin-time-marker' : '');
        const leader = doc.createElement('div'); leader.className = 'scene3d-waypoint-leader';
        const head = doc.createElement('div'); head.className = 'scene3d-waypoint-head';
        const text = doc.createElement('span'); text.className = 'scene3d-waypoint-label'; text.textContent = label;
        const icon = doc.createElement('span'); icon.className = 'scene3d-waypoint-icon'; head.append(text, icon);
        node.append(leader, head); waypoints.append(node); waypointNodes.set(label, node);
      }
      const { x, y, lift, offset } = placement;
      node.hidden = false;
      node.style.left = x + 'px'; node.style.top = y + 'px'; node.style.setProperty('--waypoint-lift', lift + 'px');
      node.style.setProperty('--waypoint-offset', offset + 'px');
      node.style.setProperty('--waypoint-leader-length', Math.max(0, Math.hypot(lift, offset) - 18) + 'px');
      node.style.setProperty('--waypoint-leader-angle', Math.atan2(offset, lift) + 'rad');
    }
    for (const [key, node] of waypointNodes) {
      if (waypointLayout.has(key)) { waypointAbsent.delete(key); continue; }
      // Cached nodes must disappear immediately when spacing rejects them;
      // retaining an old placement for three frames would reintroduce overlap.
      node.hidden = true;
      const streak = (waypointAbsent.get(key) ?? 0) + 1;
      if (streak >= 3) { node.remove(); waypointNodes.delete(key); waypointAbsent.delete(key); }
      else waypointAbsent.set(key, streak);
    }
    const ship = ships.find(ship => String(ship.id) === String(chart.getSelectedTargetId()));
    card.hidden = !ship;
    if (ship) {
      const model = targetPresentation(projection, ship, info);
      card.cardTitle = ship.name || 'TS' + ship.id; card.index = String(ship.id);
      card.source = projection.raw.executed_tracker === 'god' ? 'GOD' : 'TRACK'; card.headerVariant = 'detailed';
      card.description = (ship.length ?? '—') + ' × ' + (ship.width ?? '—') + ' m';
      applyTargetAppearance(card, model.alert); cardAlert.status = model.alert.poiState;
      if (model.alert.state === 'unchecked') card.style.setProperty('--element-active-color', 'inherit');
      cardAlert.hidden = !['caution', 'alarm'].includes(model.alert.poiState); renderTargetCard(cardBody, model);
    }
    root.dataset.frameId = String(frame.frame_id); root.dataset.sourceSeq = String(frame.source_seq);
    root.dataset.targets = String(wanted.size); root.dataset.sync = 'matched';
    root.dataset.pickTargets = JSON.stringify(frame.targets);
  }
  return {
    render(projection) {
      if (!projection?.raw) return;
      // 契约 §6.3.3：run_id 变化清空 per-target 切换集合（防跨 run key 碰撞）。
      if (projection.raw.run_id !== yoloRunId) { yoloRunId = projection.raw.run_id; yoloKeys.clear(); }
      // dt-yolo：run 切换同样重置视口检测状态与全局样式（照 yoloKeys 清空模式）。
      if (projection.raw.run_id !== viewportYoloRunId) {
        viewportYoloRunId = projection.raw.run_id; viewportYoloStyle = 0; viewportDetectionsState = null;
        viewportTracksState = null;   // P3:航迹与检测文档同 run 生命周期清场
        // P0 锁帧:跨 run 位姿/检测不可延续,跟踪器与位姿历史一并清场。
        poseHistory.length = 0; trackedDetectionsReceivedAt = undefined; detectionTracker.reset();
      }
      viewportDetectionsState = foldViewportDetections(viewportDetectionsState, projection.raw, performance.now());
      // SSE 直供文档与全量文档车取新者(received_at 单调,fold 语义同源)。
      if (viewportDetectionsLive?.doc && (!viewportDetectionsState?.doc
        || Number(viewportDetectionsLive.doc.received_at) >= Number(viewportDetectionsState.doc.received_at))) {
        viewportDetectionsState = viewportDetectionsLive;
      }
      viewportTracksState = foldViewportTracks(viewportTracksState, projection.raw, performance.now());
      const bridge = client();
      if (bridge !== presentationClient || bridge?.attached !== presentationAttachment) {
        lastSent = null; presentationClient = bridge; presentationAttachment = bridge?.attached;
      }
      latest = projection; models.set(projection.raw.seq, projection);
      if (models.size > 120) models.delete(models.keys().next().value);
      const surface = getPlannerSurface?.();
      if (surface?.type === 'vo') requestVODecisionSpace?.();
      const presentation = buildTwinPresentation(projection, chart, info, surface?.type === 'vo' ? surface.vo : null, doc, yoloKeys);
      const signature = JSON.stringify(presentation);
      if (signature !== lastSent && bridge?.attached?.run_id === presentation?.run_id && bridge?.sendPresentation?.(presentation)) lastSent = signature;
    },
    videoFrame(timestamp, metadata = {}) {
      if (disposed || video.videoWidth < FRAME_MARKER.width || video.videoHeight < FRAME_MARKER.height) return;
      const started = performance.now();
      frameId = client()?.videoFrameId?.(metadata.rtpTimestamp) ?? null;
      if (frameId !== null) frameCosts.rtpMatched++;
      else {
        // Legacy URS senders do not provide RTP mappings. Keep their exact
        // marker contract; never place overlays using an unrelated newer frame.
        frameCosts.pixelReads++;
        try {
          sampleContext.drawImage(video, 0, 8, FRAME_MARKER.width, 1, 0, 0, 32, 1);
          frameId = decodeFrameMarker(sampleContext.getImageData(0, 0, 32, 1).data);
        } catch { frameId = null; }
      }
      const markerDone = performance.now();
      frame = matchedSituationFrame(client(), frameId, info.run_id, video.videoWidth, video.videoHeight);
      lastVideoAt = timestamp; renderFrame();
      const finished = performance.now();
      frameCosts.count++; frameCosts.markerMs += markerDone - started; frameCosts.overlayMs += finished - markerDone;
      frameCosts.markerMaxMs = Math.max(frameCosts.markerMaxMs, markerDone - started);
      frameCosts.overlayMaxMs = Math.max(frameCosts.overlayMaxMs, finished - markerDone);
      if (!root.hidden) matched++; else unmatched++;
      observeVisibility(timestamp);
    },
    tick(timestamp) {
      // DataChannel and video can arrive in either order.
      if (frameId !== null && timestamp - lastVideoAt < 500) {
        frame = matchedSituationFrame(client(), frameId, info.run_id, video.videoWidth, video.videoHeight); renderFrame();
      } else root.hidden = true;
      observeVisibility(timestamp);
      const pick = client()?.lastPick;
      if (pick && pick !== lastPick) { lastPick = pick; host.dataset.situationPick = JSON.stringify(pick); choose(pick.id, pick.key); }
      if (latest) this.render(latest);
    },
    reset() {
      lastSent = null; frame = null; frameId = null; root.hidden = true;
      models.clear(); yoloKeys.clear(); yoloRunId = null;
      viewportDetectionsState = null; viewportTracksState = null; viewportYoloRunId = null; viewportYoloStyle = 0;
      poseHistory.length = 0; trackedDetectionsReceivedAt = undefined; detectionTracker.reset();
      for (const node of detectionNodes.values()) node.remove(); detectionNodes.clear();
      for (const node of viewportDetectionNodes.values()) node.remove(); viewportDetectionNodes.clear();
      for (const node of badgeNodes.values()) node.remove(); badgeNodes.clear();
    },
    select(id) { choose(id); },
    get cameraPose() { return frame?.camera_pose; },
    get landscape() { return frame?.landscape; },
    get diagnostics() { return diagnostics; },
    get frameCosts() { return frameCosts; },
    // dt-yolo:HUD 后缀(deployment-twin renderHud 消费)——'· YOLO ON'(绿,链路在算)/
    // '· YOLO OFF'(勾了但数据不新鲜:引擎启动中或链路断)/''(未勾选)。
    yoloStatus() { return viewportYoloHudSuffix(chart.getLayerState(), viewportDetectionsState, performance.now()); },
    destroy() { disposed = true; vpEventSource?.close(); video.style.visibility = ''; video.removeEventListener('pointerdown', down); video.removeEventListener('pointerup', up); video.removeEventListener('contextmenu', contextMenu); compass.destroy(); root.remove(); toolbar.remove(); },
  };
}
