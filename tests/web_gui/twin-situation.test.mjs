import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeFrameMarker, containedVideoRect, matchedSituationFrame, buildTwinPresentation, layoutTwinLabels,
  pickTwinTarget, toggleYoloKey, latestDetectionForTrack, foldViewportDetections, viewportDetectionsFresh,
  yoloViewportMode, viewportDetectionBoxes, associateViewportDetections, cycleViewportYoloStyle,
  VIEWPORT_DETECTIONS_FRESH_S, VIEWPORT_ASSOCIATION_RADIUS } from '../../web_gui/modules/twin-situation.js?v=20261015-dt-yolo-ts-v4';
import { createTwinBridgeClient } from '../../web_gui/modules/twin-view.js?v=20261015-dt-yolo-tv-v1';

function marker(frame) {
  const value = frame & 65535, check = ((value >>> 8) ^ value ^ 0x5a) & 255;
  const bits = (0xd3000000 | value << 8 | check) >>> 0;
  return Uint8ClampedArray.from(Array.from({ length: 32 }, (_, i) => {
    const color = bits & (1 << (31 - i)) ? 235 : 20; // compressed black/white
    return [color, color, color, 255];
  }).flat());
}
test('frame marker survives video compression and frame counter wrap', () => {
  for (const value of [0, 1, 255, 256, 65535, 65536]) assert.equal(decodeFrameMarker(marker(value)), value & 65535);
});
test('corrupt or ambiguous video markers never use the latest projection', () => {
  const pixels = marker(123); pixels[0] = pixels[1] = pixels[2] = 120;
  assert.equal(decodeFrameMarker(pixels), null);
  const corrupt = marker(123); corrupt[124] = corrupt[125] = corrupt[126] = 255 - corrupt[124];
  assert.equal(decodeFrameMarker(corrupt), null);
  assert.equal(decodeFrameMarker(null), null);
});
test('placements use the actual contained video, including black side bars', () => {
  assert.deepEqual(containedVideoRect(2048, 900, 2560, 1440),
    { left: 224, top: 0, width: 1600, height: 900, scale: 0.625 });
  assert.equal(containedVideoRect(0, 0, 0, 0), null);
});
test('frame matching rejects wrong session and old stream resolution', () => {
  const frame = { run_id: 'current', width: 1920, height: 1080 };
  const client = { situationFrame: id => id === 14 ? frame : null };
  assert.equal(matchedSituationFrame(client, 14, 'current', 1920, 1080), frame);
  assert.equal(matchedSituationFrame(client, 15, 'current', 1920, 1080), null);
  assert.equal(matchedSituationFrame(client, 14, 'old', 1920, 1080), null);
  assert.equal(matchedSituationFrame(client, 14, 'current', 2560, 1440), null);
});
test('bridge buffers frame-specific projections and clears them on reattach', () => {
  const sent = [], client = createTwinBridgeClient({ channel: { isOpen: () => true, send: x => sent.push(JSON.parse(x)) } });
  assert.equal(client.sendPresentation({ run_id: 'a' }), null);
  client.onMessage(JSON.stringify({ type: 'ready', situation_sync: 'frame-marker@1' }));
  client.onMessage(JSON.stringify({ type: 'attached', run_id: 'a' }));
  client.onMessage(JSON.stringify({ type: 'situation_frame', run_id: 'old', frame_id: 1 }));
  assert.equal(client.situationFrame(1), null);
  client.onMessage(JSON.stringify({ type: 'situation_frame', run_id: 'a', frame_id: 1 }));
  assert.equal(client.situationFrame(1).run_id, 'a');
  client.sendPresentation({ run_id: 'a' }); client.sendPick('a', 1, 0.5, 0.4);
  assert.equal(sent[0].type, 'presentation'); assert.equal(sent[1].frame_id, 1);
  client.onMessage(JSON.stringify({ type: 'attached', run_id: 'b' }));
  assert.equal(client.situationFrame(1), null);
});

const info = { run_id: 'a', origin_e: 42000, origin_n: 6959450 };
const chart = { getMissionRoute: () => [[0, 1000], [0, 0]], getLayerState: () => ({}) };
const projection = {
  raw: { run_id: 'a', seq: 12, sim_time: 60, executed_tracker: 'god', os: { x: 0, y: 0 },
    obstacles: Array.from({ length: 9 }, (_, i) => ({ id: i + 1, generation: 4, x: i * 10, y: 500, active: true, length: 12, width: 5 })) },
};
test('ten-ship display keeps every active contact and its generation, without threat filtering', () => {
  const value = buildTwinPresentation(projection, chart, info);
  assert.equal(value.targets.length, 9);
  assert.equal(value.targets[0].key, 'a:1:4');
  assert.equal(value.targets[0].east, 42500); assert.equal(value.targets[0].north, 6959450);
  assert.equal(value.targets[0].truth, true);
  assert.equal(Math.abs(value.ribbon[0].east - info.origin_e), 180);
  assert.equal(Math.abs(value.ribbon[0].east - value.ribbon[3].east), 360);
  assert.equal(value.waypoints[1].label, 'WPT2');
  assert.equal(value.lines.find(line => line.id === 'detection-ring').points.length, 129);
  assert.equal('risk' in value, false); assert.equal('clock' in value, false);
});
test('DT world geometry respects shared layers and geography identity', () => {
  const value = buildTwinPresentation(projection, { ...chart, getLayerState: () => ({ route: { visible: false }, waypoints: { visible: false }, radarRange: { visible: false } }) }, info);
  assert.deepEqual(value.ribbon, []); assert.equal(value.waypoints_visible, false);
  assert.equal(value.lines.some(line => line.id === 'detection-ring'), false);
  assert.equal(buildTwinPresentation(projection, chart, { ...info, run_id: 'old' }), null);
});
test('tracked positions keep tracker provenance instead of moving labels to truth', () => {
  const tracked = { raw: { ...projection.raw, executed_tracker: 'vimmjipda', tracks: [{
    labels: [1], generations: [8], states: [[123, 456, 0, 0]],
  }] } };
  const value = buildTwinPresentation(tracked, chart, info);
  assert.equal(value.targets[0].north, info.origin_n + 123);
  assert.equal(value.targets[0].east, info.origin_e + 456);
  assert.equal(value.targets[0].truth, false); assert.equal(value.targets[0].key, 'a:1:8');
});

/* ── dt-sensor-overlay：右键本地命中 / 模式循环 / 检测映射 ── */

const pickFrame = { run_id: 'a', width: 1920, height: 1080, targets: [
  { key: 'a:1:4', visible: true, depth: 50, left: 0.3, top: 0.3, width: 0.1, height: 0.1 },
  { key: 'a:2:4', visible: true, depth: 20, left: 0.32, top: 0.32, width: 0.1, height: 0.1 },
  { key: 'a:3:none', visible: false, depth: 10, left: 0.05, top: 0.05, width: 0.1, height: 0.1 },
  { key: 'a:4:none', visible: true, depth: 0, left: 0.8, top: 0.8, width: 0.1, height: 0.1 },
] };
test('local right-click pick replicates TwinSituationMath.Pick bounds+pad+depth', () => {
  // 双命中取 depth 最近；不可见与 depth<=0 的点不参与。
  assert.equal(pickTwinTarget(pickFrame, 0.35, 0.35).key, 'a:2:4');
  assert.equal(pickTwinTarget(pickFrame, 0.31, 0.31).key, 'a:1:4');   // 只落在 1 的盒内
  assert.equal(pickTwinTarget(pickFrame, 0.06, 0.06), null);          // invisible 候选被排除
  assert.equal(pickTwinTarget(pickFrame, 0.85, 0.85), null);          // depth 0 在镜头后
  assert.equal(pickTwinTarget(pickFrame, 0.9, 0.9), null);            // 空白处未命中
});
test('pick honors the exact 12px pad boundary in normalized coordinates', () => {
  const padX = 12 / 1920, padY = 12 / 1080;
  assert.equal(pickTwinTarget(pickFrame, 0.3 - padX, 0.3).key, 'a:1:4');      // pad 内沿命中
  assert.equal(pickTwinTarget(pickFrame, 0.3 - padX - 1e-6, 0.3), null);      // pad 外一像素未命中
  assert.equal(pickTwinTarget(pickFrame, 0.3, 0.3 - padY).key, 'a:1:4');
  assert.equal(pickTwinTarget(pickFrame, 0.3, 0.3 - padY - 1e-6), null);
  assert.equal(pickTwinTarget(pickFrame, 0.4 + padX, 0.305).key, 'a:1:4');    // 右沿含 pad（y 避开 a:2:4 盒）
  assert.equal(pickTwinTarget(pickFrame, 0.4 + padX + 1e-6, 0.305), null);
});
test('pick rejects out-of-domain coordinates and missing target arrays', () => {
  for (const [x, y] of [[-0.1, 0.5], [1.1, 0.5], [0.5, -0.1], [0.5, 1.1], [NaN, 0.5], [0.5, Infinity]]) {
    assert.equal(pickTwinTarget(pickFrame, x, y), null);
  }
  assert.equal(pickTwinTarget({ run_id: 'a', width: 1920, height: 1080 }, 0.5, 0.5), null);
  assert.equal(pickTwinTarget(null, 0.5, 0.5), null);
});
test('per-target mode cycles fused → yolo → fused through the key set', () => {
  const keys = new Set();
  toggleYoloKey(keys, 'a:1:4');
  assert.equal(keys.has('a:1:4'), true);
  toggleYoloKey(keys, 'a:1:4');
  assert.equal(keys.has('a:1:4'), false);
  toggleYoloKey(keys, '');   // 空 key 不动作（防御 JsonUtility "" 关联键）
  assert.equal(keys.size, 0);
});
test('latest associated detection wins by numeric det_id, not lexicographic order', () => {
  const detections = [
    { key: '2:9:0', track_key: 'a:1:4', confidence: 0.9 },
    { key: '2:10:0', track_key: 'a:1:4', confidence: 0.7 },   // 字典序 '2:10:0' < '2:9:0'，数值域 10 > 9
    { key: '3:99:0', track_key: '', confidence: 0.99 },       // 无关联（""）不参与
    { key: '2:11:0', track_key: 'a:9:9', confidence: 0.5 },   // 别的 track
  ];
  assert.equal(latestDetectionForTrack(detections, 'a:1:4').key, '2:10:0');
  assert.equal(latestDetectionForTrack(detections, 'a:9:9').key, '2:11:0');
  assert.equal(latestDetectionForTrack(detections, 'a:8:8'), null);
  assert.equal(latestDetectionForTrack(null, 'a:1:4'), null);
});
test('presentation maps existence and observations per contract sections A→B', () => {
  const tracked = { raw: { ...projection.raw, executed_tracker: 'vimmjipda', tracks: [{
    labels: [1], generations: [8], states: [[123, 456, 0, 0]], existence_prob: [0.87],
  }],
  observations: [
    { north: 120, east: 60, length_m: 12, width_m: 5, confidence: 0.87, class_name: 'boat', sensor_id: 2, age_s: 1.2, det_id: '2:41:0', track_key: 'a:1:8' },
    { north: 800, east: -30, length_m: 9, width_m: 4, confidence: 0.42, class_name: 'boat', sensor_id: 3, age_s: 2.0, det_id: '3:41:1', track_key: '' },
    { north: 'x', east: 5, det_id: '2:42:0', track_key: '' },   // 非有限坐标 → 弃
  ] } };
  const layered = { ...chart, getLayerState: () => ({ detections: { visible: true } }) };
  const value = buildTwinPresentation(tracked, layered, info);
  assert.equal(value.targets[0].existence, 0.87);
  assert.equal(value.detections.length, 2);
  assert.deepEqual(value.detections[0], { east: info.origin_e + 60, north: info.origin_n + 120, label: '',
    length: 12, width: 5, confidence: 0.87, class_name: 'boat', sensor_id: 2, key: '2:41:0', track_key: 'a:1:8' });
  assert.equal(value.detections[1].track_key, '');   // 无关联空串（JsonUtility 不可 round-trip null）
  // 图层关：仅 track_key ∈ yoloKeys 的条目；无切换 → 空数组仍发送。
  const off = buildTwinPresentation(tracked, chart, info);
  assert.deepEqual(off.detections, []);
  const yoloOnly = buildTwinPresentation(tracked, chart, info, null, null, new Set(['a:1:8']));
  assert.equal(yoloOnly.detections.length, 1);
  assert.equal(yoloOnly.detections[0].key, '2:41:0');
  // god 无 existence → -1；旧会话无 observations → 空数组（宽容）。
  const god = buildTwinPresentation(projection, layered, info);
  assert.equal(god.targets[0].existence, -1);
  assert.deepEqual(god.detections, []);
  // 存在概率缺失（旧链路）→ -1，不炸。
  const legacy = buildTwinPresentation({ raw: { ...tracked.raw, observations: undefined,
    tracks: [{ labels: [1], generations: [8], states: [[123, 456, 0, 0]] }] } }, layered, info);
  assert.equal(legacy.targets[0].existence, -1);
  assert.deepEqual(legacy.detections, []);
});

test('dense ten-ship labels retain every anchor and separate all heads', () => {
  const items = Array.from({ length: 10 }, (_, i) => ({ key: String(i), x: 500 + i, y: 550, height: i === 0 ? 272 : 144, priority: i === 0 ? 3 : 0 }));
  const layout = layoutTwinLabels(items, 1024, 150), values = [...layout.values()];
  assert.equal(layout.size, 10); assert.equal(layout.get('0').compact, false);
  for (let i = 0; i < values.length; i++) {
    const a = values[i]; assert.ok(a.x >= 36 && a.x <= 988); assert.ok(a.top >= 150);
    for (const b of values.slice(i + 1)) assert.ok(Math.abs(a.x - b.x) >= 72 || a.top >= b.bottom + 12 || a.bottom <= b.top - 12);
  }
  assert.deepEqual(items.map(i => i.x), Array.from({ length: 10 }, (_, i) => 500 + i));
});

test('single-click tracking is removed: the bridge offers no camera_target sender', () => {
  const sent = [], client = createTwinBridgeClient({ channel: { isOpen: () => true, send: x => sent.push(JSON.parse(x)) } });
  assert.equal(client.sendCameraTarget, undefined);
  client.sendCamera('chase');   // 预设机位键保留（舰桥/追随/俯视）
  assert.deepEqual(sent[0], { type: 'camera', preset: 'chase' });
});

/* ── dt-yolo 视口检测（遥测文档顶层 viewport_detections@1）─────────────────── */

const vpDoc = {
  schema: 'viewport_detections@1', pts_s: 123.456, width: 1280, height: 720, source: 'twin-viewport',
  detections: [{ box_xyxy: [100, 100, 300, 260], class_id: 8, class_name: 'boat', confidence: 0.89 }],
  received_at: 1760000000.123, age_s: 0.4,
};
test('viewport detections fold keeps the newest document and ignores out-of-order regressions', () => {
  const first = foldViewportDetections(null, { viewport_detections: vpDoc }, 1000);
  assert.equal(first.doc, vpDoc); assert.equal(first.at, 1000);
  const newer = { ...vpDoc, received_at: 1760000001.5, detections: [] };
  const second = foldViewportDetections(first, { viewport_detections: newer }, 1100);
  assert.equal(second.doc, newer); assert.equal(second.at, 1100);
  // 乱序旧文档（received_at 回退）不覆盖，本地接收时刻保持原值。
  assert.equal(foldViewportDetections(second, { viewport_detections: vpDoc }, 1200), second);
  // 键缺省（无数据/过期）= 状态原样保留。
  assert.equal(foldViewportDetections(second, {}, 1300), second);
  assert.equal(foldViewportDetections(null, {}, 0), null);
  // detections 非数组的畸形文档不入状态。
  assert.equal(foldViewportDetections(null, { viewport_detections: { ...vpDoc, detections: 'x' } }, 0), null);
});
test(`viewport detections freshness: age_s < ${VIEWPORT_DETECTIONS_FRESH_S} and a detections array (empty counts as active)`, () => {
  const state = { doc: vpDoc, at: 5000 };
  assert.equal(viewportDetectionsFresh(state, 5100), true);
  assert.equal(viewportDetectionsFresh({ ...state, doc: { ...vpDoc, age_s: 1.2 } }, 5100), false, '边界含首不含尾');
  assert.equal(viewportDetectionsFresh({ ...state, doc: { ...vpDoc, detections: [] } }, 5100), true, '空数组 = YOLO 活跃但无目标');
  assert.equal(viewportDetectionsFresh({ ...state, doc: { ...vpDoc, age_s: -1 } }, 5100), false);
  // age_s 缺失（旧后端）回退本地接收时刻差。
  assert.equal(viewportDetectionsFresh({ doc: { ...vpDoc, age_s: undefined }, at: 5000 }, 5000 + 1199), true);
  assert.equal(viewportDetectionsFresh({ doc: { ...vpDoc, age_s: undefined }, at: 5000 }, 5000 + 1201), false);
  assert.equal(viewportDetectionsFresh(null, 0), false);
});
test('yolo viewport mode needs the layer checked AND fresh data', () => {
  const state = { doc: vpDoc, at: 0 };
  assert.equal(yoloViewportMode({ detections: { visible: true } }, state, 100), true);
  assert.equal(yoloViewportMode({ detections: { visible: false } }, state, 100), false);
  assert.equal(yoloViewportMode({}, state, 100), false);
  assert.equal(yoloViewportMode({ detections: { visible: true } }, null, 100), false);
});
test('box_xyxy pixel domain maps onto the contained rect with normalized centers', () => {
  const doc = { width: 1280, height: 720, detections: [
    { box_xyxy: [640, 360, 896, 540], class_name: 'boat', confidence: 0.89 },
    { box_xyxy: [0, 0, 1280, 720], class_name: 'ship', confidence: 0.5 },
    { box_xyxy: ['x'], class_name: 'bad' },
  ] };
  const boxes = viewportDetectionBoxes(doc, 1600, 900);
  assert.equal(boxes.length, 2);
  assert.deepEqual(boxes[0], { index: 0, left: 800, top: 450, width: 320, height: 225,
    cx: 0.6, cy: 0.625, className: 'boat', confidence: 0.89 });
  assert.equal(boxes[1].width, 1600); assert.equal(boxes[1].confidence, 0.5);
  assert.deepEqual(viewportDetectionBoxes(null, 100, 100), []);
  assert.deepEqual(viewportDetectionBoxes({ width: 0, height: 0, detections: [] }, 100, 100), []);
});
test(`detection→track association takes the nearest target within the ${VIEWPORT_ASSOCIATION_RADIUS} radius`, () => {
  const targets = [
    { key: 'a:1:4', x: 0.30, y: 0.30 },
    { key: 'a:2:4', x: 0.50, y: 0.50 },
  ];
  const keys = associateViewportDetections([{ cx: 0.31, cy: 0.31 }, { cx: 0.55, cy: 0.5 }, { cx: 0.9, cy: 0.9 }], targets);
  assert.deepEqual(keys, ['a:1:4', 'a:2:4', null]);
  assert.deepEqual(associateViewportDetections([], targets), []);
  // 半径边界含首不含尾；缺 key / 非有限坐标的 target 不参与。
  assert.deepEqual(associateViewportDetections([{ cx: 0.30, cy: 0.30 + VIEWPORT_ASSOCIATION_RADIUS }], targets), [null]);
  assert.deepEqual(associateViewportDetections([{ cx: 0.31, cy: 0.31 }], [{ x: 0.31, y: 0.31 }, { key: 'a:1:4', x: NaN, y: 0.3 }]), [null]);
});
test('single click cycles the three global viewport styles and wraps', () => {
  assert.equal(cycleViewportYoloStyle(0), 1);
  assert.equal(cycleViewportYoloStyle(1), 2);
  assert.equal(cycleViewportYoloStyle(2), 0);
  assert.equal(cycleViewportYoloStyle(undefined), 1);   // 非法态按 0 处理
});

// dt-yolo 收编轮:HUD 后缀——勾选+新鲜=ON(在算,空集=没检测到);勾选+不新鲜=OFF(没在算);未勾=无。
test('viewportYoloHudSuffix covers compute/no-compute/off states', async () => {
  const { viewportYoloHudSuffix, foldViewportDetections } = await import('../../web_gui/modules/twin-situation.js?v=20261015-dt-yolo-ts-v4');
  const checked = { detections: { visible: true } };
  const unchecked = { detections: { visible: false } };
  const doc = { detections: [], received_at: 100, age_s: 0.1 };
  const state = foldViewportDetections(null, { viewport_detections: doc }, 0);
  assert.equal(viewportYoloHudSuffix(checked, state, 0), '· YOLO ON');
  assert.equal(viewportYoloHudSuffix(unchecked, state, 0), '');
  const stale = foldViewportDetections(null, { viewport_detections: { ...doc, age_s: 1.9 } }, 0);
  assert.equal(viewportYoloHudSuffix(checked, stale, 0), '· YOLO OFF');
  assert.equal(viewportYoloHudSuffix(checked, null, 0), '· YOLO OFF');
});

// dt-yolo 第4轮:本船框抑制——camera_pose 正向投影本船点,圈内框剔除。
test('projectViewportPoint maps chase camera onto own ship at frame center', async () => {
  const { projectViewportPoint } = await import('../../web_gui/modules/twin-situation.js?v=20261015-dt-yolo-ts-v4');
  // 相机在船正后方 130m、高 60m、正北俯视(-25°) → 本船投影应落在画面中央带
  const chase = { east: 0, north: -130, height_m: 60, yaw_deg: 0, pitch_deg: -25, fov_deg: 60 };
  const point = projectViewportPoint(chase, 0, 0, 0);
  assert.ok(point, 'own ship in front of camera projects');
  assert.ok(Math.abs(point.x - 0.5) < 0.02 && point.y > 0.45 && point.y < 0.62,
    `centered: got x=${point.x?.toFixed(3)} y=${point.y?.toFixed(3)}`);
  // 偏航 90°(向东看) → 正北的船应落在画面左侧之外
  const east = { ...chase, yaw_deg: 90 };
  assert.equal(projectViewportPoint(east, 0, 0, 0), null, 'off-axis own ship out of viewport');
  // 桥视角:相机在本船桥位,船体中心在身后 → 无投影点(桥视角不抑制)
  const bridge = { east: 0, north: 10, height_m: 12, yaw_deg: 0, pitch_deg: -8, fov_deg: 60 };
  assert.equal(projectViewportPoint(bridge, 0, 0, 0), null, 'own hull behind bridge camera');
  assert.equal(projectViewportPoint(null, 0, 0, 0), null, 'missing pose is inert');
});

test('ownShipViewportGuard + suppressOwnShipBoxes drop own hull, keep distant contacts', async () => {
  const { ownShipViewportGuard, suppressOwnShipBoxes } = await import('../../web_gui/modules/twin-situation.js?v=20261015-dt-yolo-ts-v4');
  const chase = { east: 0, north: -130, height_m: 60, yaw_deg: 0, pitch_deg: -25, fov_deg: 60 };
  const guard = ownShipViewportGuard(chase, { east: 0, north: 0, psi: 0, length: 45 });
  assert.ok(guard && guard.circles.length === 1 && guard.circles[0].radius > 0.04, '追随=单圆圈');
  assert.equal(guard.floorY, null, '追随不启用底半平面');
  const circle = guard.circles[0];
  const boxes = [
    { index: 0, cx: circle.x, cy: circle.y, confidence: 0.9 },            // 本船自身
    { index: 1, cx: circle.x + 0.05, cy: circle.y + 0.03, confidence: 0.8 }, // 本船船楼框(框心偏移)
    { index: 2, cx: 0.2, cy: 0.3, confidence: 0.4 },                    // 远处目标船
  ];
  const kept = suppressOwnShipBoxes(boxes, guard);
  assert.deepEqual(kept.map(box => box.index), [2], 'own hull boxes suppressed, distant contact kept');
  assert.deepEqual(suppressOwnShipBoxes(boxes, null).map(box => box.index), [0, 1, 2],
    'no guard (behind) = no suppression');
});

// 20261015 验收轮:舰桥眼位——船中在相机身后投影不出,艏点投影产出底半平面,
// 艏甲板误检框(画面底带)剔除,水平线附近目标船保留。
test('bridge eye guard: bow-point floor suppresses deck boxes, keeps horizon contacts', async () => {
  const { ownShipViewportGuard, suppressOwnShipBoxes } = await import('../../web_gui/modules/twin-situation.js?v=20261015-dt-yolo-ts-v4');
  // 舰桥眼位:相机在本船中后部上方 12m,朝北俯 8°;船 45m(艏在相机前方 ~30m)
  const bridge = { east: 0, north: -8, height_m: 12, yaw_deg: 0, pitch_deg: -8, fov_deg: 60 };
  const own = { east: 0, north: 0, psi: 0, length: 45 };
  const guard = ownShipViewportGuard(bridge, own);
  assert.ok(guard, '艏点可投影 → guard 存在');
  assert.equal(guard.circles.length, 0, '桥视角无圆圈(船中不可投影)');
  assert.ok(guard.floorY > 0.5 && guard.floorY < 0.9, `艏点以下底半平面, got ${guard.floorY?.toFixed(3)}`);
  const boxes = [
    { index: 0, cx: 0.5, cy: 0.85, confidence: 0.92 },  // 本船艏甲板大框(画面底带)
    { index: 1, cx: 0.35, cy: 0.4, confidence: 0.6 },   // 水平线附近目标船
  ];
  const kept = suppressOwnShipBoxes(boxes, guard);
  assert.deepEqual(kept.map(box => box.index), [1], 'deck box suppressed, horizon contact kept');
  // 瞭望明显抬头(仰 20°):艏点俯角 21° 超出画面下缘(30°-20°=10°)→投影出画,不抑制
  const lookingUp = { ...bridge, pitch_deg: 20 };
  assert.equal(ownShipViewportGuard(lookingUp, own), null, '仰视时甲板出画,不抑制');
});

// 20261015 验收轮:关联吸附——已关联 track 的检测框改用 track 实时投影包围盒
// (消除检测链 ~0.5s 时延造成的滞后错位);未关联框保持检测原坐标。
test('viewportBoxPlacement snaps associated boxes to live track projection', async () => {
  const { viewportBoxPlacement } = await import('../../web_gui/modules/twin-situation.js?v=20261015-dt-yolo-ts-v4');
  const box = { left: 100, top: 50, width: 40, height: 20 };
  const track = { left: 0.3, top: 0.2, width: 0.05, height: 0.03, x: 0.325, y: 0.215 };
  const snapped = viewportBoxPlacement(box, track, 1280, 720);
  assert.equal(snapped.snapped, true, '有包围盒的 track 触发吸附');
  assert.deepEqual([snapped.left, snapped.top, snapped.width, snapped.height],
    [0.3 * 1280, 0.2 * 720, 0.05 * 1280, 0.03 * 720], '位置/尺寸=track 投影×rect');
  const plain = viewportBoxPlacement(box, null, 1280, 720);
  assert.equal(plain.snapped, false, '无关联=检测原坐标');
  assert.equal(plain.left, 100, '未关联框保持检测坐标');
  const degenerate = viewportBoxPlacement(box, { left: 0.1, top: 0.1, width: 0, height: 0 }, 1280, 720);
  assert.equal(degenerate.snapped, false, '零尺寸 track(越界投影)不吸附');
});
