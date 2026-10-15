import { targetsForDisplay, RADAR_DETECTION_RANGE_M, drawVODecisionDisc, trackConfidenceColor } from './situation-display.js?v=20261015-dt-yolo-sd-v2';
import { routeRibbonQuads } from './route-3d.js?v=20260921-route-ar-v1';
import { predictionMarkers, targetKey, offscreenDirection } from './scene-geography.js?v=20261004-token-cleanup-v1';
import { targetPresentation, updateTargetPoi, applyTargetAppearance, renderTargetCard } from './scene-target.js?v=20260923-follow-v1';
import { createSceneCompass } from './scene-compass.js?v=20261013-dt-frame-cost-v1';
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

// ── 本船框抑制（dt-yolo 第4轮）────────────────────────────────────────────
// 追随/俯仰视角里本船自身是画面主体,COCO boat 检出它属真实检测但无情报价值;
// 用 situation 帧 camera_pose 把本船水线中心正向投影到视口,落在投影圈内的框
// 即本船框,渲染前剔除。桥视角本船在相机身后(深度≤近轴)→ 无投影点 → 不抑制。
// 相机基与 CameraRig camera_free 语义同源:yaw 北向东顺时针,pitch 负=俯,
// fov=垂直向度;水平向按 aspect(视口族恒 16:9,由调用方传入)。
export function projectViewportPoint(pose, east, north, height, aspect = 16 / 9) {
  if (!pose || ![pose.east, pose.north, pose.height_m, pose.yaw_deg, pose.pitch_deg, pose.fov_deg].every(Number.isFinite)) return null;
  if (![east, north, height].every(Number.isFinite) || !(aspect > 0)) return null;
  const radians = Math.PI / 180;
  const yaw = pose.yaw_deg * radians, pitch = pose.pitch_deg * radians;
  const de = east - pose.east, dn = north - pose.north, dh = height - pose.height_m;
  const f = [Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch)];
  const r = [Math.cos(yaw), 0, -Math.sin(yaw)];
  const u = [f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0]];
  const depth = de * f[0] + dh * f[1] + dn * f[2];
  if (depth <= 1) return null; // 本船在相机身后/脚下近轴外
  const px = de * r[0] + dh * r[1] + dn * r[2];
  const py = de * u[0] + dh * u[1] + dn * u[2];
  const tv = Math.tan(pose.fov_deg * radians / 2);
  const x = px / (2 * depth * tv * aspect) + 0.5;
  const y = 0.5 - py / (2 * depth * tv);
  if (x < -0.1 || x > 1.1 || y < -0.1 || y > 1.1) return null; // 视口外(留越界容差)
  return { x, y, depth };
}

// 抑制圈(20261015 验收轮扩展):两条几何规则,无屏幕魔法数——
// ① 追随/俯仰:本船水线中心可投影 → 圆圈(半长在该深度的屏幕占比 ×1.3,下限保底);
// ② 舰桥眼位:船中在相机身后投影不出,艏点在前方 → 艏点以下的底半平面(艏甲板/
//    栏杆误检框恒在画面底带;水平线附近目标船 cy ≤ ~0.55 天然安全;瞭望抬头艏点
//    移出下半区(y ≤ 0.5)则不抑制)。floorY/circles 任一命中即剔除。
export function ownShipViewportGuard(pose, own, aspect = 16 / 9) {
  const radians = Math.PI / 180;
  const halfLength = Math.max(Number(own?.length) || 0, 12) / 2;
  const psi = Number(own?.psi) || 0;
  const center = projectViewportPoint(pose, Number(own?.east), Number(own?.north), 0, aspect);
  if (center) {
    const tv = Math.tan((Number(pose?.fov_deg) || 60) * radians / 2);
    const radius = Math.max(halfLength / (2 * center.depth * tv * aspect), 0.04) * 1.3;
    return { circles: [{ x: center.x, y: center.y, radius }], floorY: null };
  }
  const bow = projectViewportPoint(pose,
    Number(own?.east) + Math.sin(psi) * halfLength,
    Number(own?.north) + Math.cos(psi) * halfLength, 0, aspect);
  if (bow && bow.y > 0.5) return { circles: [], floorY: bow.y - 0.06 };
  return null;
}

export function suppressOwnShipBoxes(boxes, guard) {
  if (!guard) return boxes || [];
  return (boxes || []).filter(box =>
    !(guard.floorY != null && box.cy > guard.floorY)
    && !guard.circles.some(g => Math.hypot(box.cx - g.x, box.cy - g.y) <= g.radius));
}

// 检测框显示位置(20261015 验收轮):检测链端到端 ~0.3-0.5s 时延,检测坐标画在
// 实时视频帧上恒滞后/错位(相机跟随转动时尤甚)。已关联 track 的框改用 track
// 实时投影包围盒(situation 帧与视频帧 marker 对齐,零滞后),检测框仅贡献类别
// 标签+置信度;未关联(无 track 的真实检出)保持检测原坐标。
export function viewportBoxPlacement(box, track, rectWidth, rectHeight) {
  if (track && [track.left, track.top, track.width, track.height].every(Number.isFinite)
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
  return { run_id: raw.run_id, seq: raw.seq, sim_time: raw.sim_time,
    ribbon: visible('route') ? routeRibbonQuads(route).flat().map(p => point(p.north, p.east)) : [],
    waypoints: route[0].map((north, i) => point(north, route[1][i], 'WPT' + (i + 1))),
    waypoints_visible: visible('waypoints'), ships_visible: visible('ships'), lines, vo: disc,
    time_markers: visible('prediction') ? predictionMarkers(raw).map(m => point(...m.point, '+' + m.elapsed.toFixed(0) + 's')) : [],
    targets: targets.map(ship => ({ ...point(ship.x, ship.y), id: String(ship.id), key: targetKey(raw.run_id, ship),
      truth: raw.executed_tracker === 'god', length: ship.length || 12, width: ship.width || 5,
      existence: Number.isFinite(ship.existence) ? ship.existence : -1 })),
    detections,
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
  const sample = doc.createElement('canvas'); sample.width = 32; sample.height = 1;
  const sampleContext = sample.getContext('2d', { willReadFrequently: true }); sampleContext.imageSmoothingEnabled = false;
  const models = new Map(), pois = new Map(), waypointNodes = new Map(), aisNodes = new Map();
  // 20261014:航点引线/标签在可见性边界(p.visible 翻转/屏幕边缘裁剪)附近逐帧增删
  // = 静态视角下白线"时隐时现"。连续缺席 3 个 situation 帧才移除节点(迟滞)。
  const waypointAbsent = new Map();
  const detectionNodes = new Map(), badgeNodes = new Map(), yoloKeys = new Set();
  const viewportDetectionNodes = new Map();
  let latest = null, frame = null, frameId = null, selectedKey = null, disposed = false;
  // dt-yolo 视口检测：最新 viewport_detections 文档 + 本地接收时刻（fold 防乱序
  // 回退）；全局三态样式与 per-run 清空照 yoloKeys 模式。
  let viewportDetectionsState = null, viewportYoloRunId = null, viewportYoloStyle = 0;
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
    if (!rect) { root.hidden = true; return; }
    rect.left += videoBox.left - hostBox.left; rect.top += videoBox.top - hostBox.top;
    const projection = frame && models.get(frame.source_seq);
    if (!projection || projection.raw.run_id !== frame.run_id) { root.hidden = true; return; }
    Object.assign(root.style, { left: rect.left + 'px', top: rect.top + 'px', width: rect.width + 'px', height: rect.height + 'px' });
    if (frame.landscape?.ready === false) {
      // A heartbeat can release the video if hidden-video callbacks are throttled.
      if (!client()?.lastState?.landscape?.ready) video.style.visibility = 'hidden';
      root.hidden = true; return;
    }
    video.style.visibility = '';
    root.hidden = false;
    root.dataset.camera = frame.camera;
    if (frame.camera_pose) root.dataset.cameraPose = JSON.stringify(frame.camera_pose);
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
    if (yoloMode) {
      // 本船框剔除(ownShipViewportGuard):框心落在本船投影圈内 = 本船自身检出。
      const guard = ownShipViewportGuard(frame?.camera_pose, getOwnship(),
        (frame?.width || 16) / (frame?.height || 9));
      const boxes = suppressOwnShipBoxes(viewportDetectionBoxes(viewportDetectionsState.doc, rect.width, rect.height), guard);
      const associated = associateViewportDetections(boxes, frame.targets || []);
      for (let position = 0; position < boxes.length; position++) {
        const box = boxes[position];   // associated 按过滤后 boxes 位置对齐（box.index 是文档原始序号）
        const key = 'vp' + box.index;
        viewportWanted.add(key);
        let node = viewportDetectionNodes.get(key);
        if (!node) {
          node = doc.createElement('button'); node.type = 'button'; node.className = 'twin-vp-detection';
          const tag = doc.createElement('span'); tag.className = 'twin-vp-detection-tag';
          const data = doc.createElement('span'); data.className = 'twin-vp-detection-data';
          node.append(tag, data);
          node.addEventListener('click', () => { viewportYoloStyle = cycleViewportYoloStyle(viewportYoloStyle); renderFrame(); });
          viewportDetectionNodes.set(key, node); detectionsLayer.append(node);
        }
        const ship = byKey.get(associated[position] || '');
        const blocks = ship ? targetPresentation(projection, ship, info).blocks : [];
        node.hidden = viewportYoloStyle === 2 && blocks.length === 0;   // 无关联 track 的 style2 = 完全无标注
        const placement = viewportBoxPlacement(box, ship, rect.width, rect.height);
        node.style.left = placement.left + 'px'; node.style.top = placement.top + 'px';
        node.style.width = placement.width + 'px'; node.style.height = placement.height + 'px';
        node.querySelector('.twin-vp-detection-tag').textContent =
          box.className + ' : ' + Math.round(box.confidence * 100) + '%';
        node.querySelector('.twin-vp-detection-data').textContent =
          blocks.map(block => [block.label, block.value, block.unit].filter(Boolean).join(' ')).join(' · ');
      }
    }
    for (const [key, node] of viewportDetectionNodes) if (!viewportWanted.has(key)) { node.remove(); viewportDetectionNodes.delete(key); }
    for (const [key, node] of badgeNodes) if (!badgeWanted.has(key)) { node.remove(); badgeNodes.delete(key); }
    edges.replaceChildren(...edgeRecords.map(({ p, model, edge, arrow }, index) => {
      const button = doc.createElement('button'); button.className = edge; button.textContent = arrow + ' TS' + p.id;
      button.style.setProperty('--edge-index', index); applyTargetAppearance(button, model.alert);
      button.addEventListener('click', () => choose(p.id, p.key)); return button;
    }));
    const waypointWanted = new Set(), placed = [];
    for (const p of [...(frame.waypoints || []), ...(frame.time_markers || [])]) {
      if (!p.visible) continue;
      const x = p.x * rect.width, y = p.y * rect.height;
      if (x < 36 || x > rect.width - 36 || y < topInset || y > rect.height - 16) continue;
      waypointWanted.add(p.label); let node = waypointNodes.get(p.label);
      if (!node) {
        node = doc.createElement('div'); node.className = 'scene3d-waypoint' + (p.label.startsWith('+') ? ' twin-time-marker' : '');
        const leader = doc.createElement('div'); leader.className = 'scene3d-waypoint-leader';
        const head = doc.createElement('div'); head.className = 'scene3d-waypoint-head';
        const label = doc.createElement('span'); label.className = 'scene3d-waypoint-label'; label.textContent = p.label;
        const icon = doc.createElement('span'); icon.className = 'scene3d-waypoint-icon'; head.append(label, icon);
        node.append(leader, head); waypoints.append(node); waypointNodes.set(p.label, node);
      }
      let lift = 92;
      while (placed.some(q => Math.abs(q.x - x) < 64 && Math.abs(q.y - (y - lift)) < 52) && y - lift > topInset + 52) lift += 52;
      lift = Math.min(lift, y - topInset); placed.push({ x, y: y - lift });
      node.style.left = x + 'px'; node.style.top = y + 'px'; node.style.setProperty('--waypoint-lift', lift + 'px');
    }
    for (const [key, node] of waypointNodes) {
      if (waypointWanted.has(key)) { waypointAbsent.delete(key); continue; }
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
      }
      viewportDetectionsState = foldViewportDetections(viewportDetectionsState, projection.raw, performance.now());
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
      viewportDetectionsState = null; viewportYoloRunId = null; viewportYoloStyle = 0;
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
    destroy() { disposed = true; video.style.visibility = ''; video.removeEventListener('pointerdown', down); video.removeEventListener('pointerup', up); video.removeEventListener('contextmenu', contextMenu); compass.destroy(); root.remove(); toolbar.remove(); },
  };
}
