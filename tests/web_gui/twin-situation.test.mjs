import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeFrameMarker, containedVideoRect, matchedSituationFrame, buildTwinPresentation, layoutTwinLabels,
  pickTwinTarget, toggleYoloKey, latestDetectionForTrack, foldViewportDetections, viewportDetectionsFresh,
  yoloViewportMode, viewportDetectionBoxes, associateViewportDetections, cycleViewportYoloStyle,
  VIEWPORT_DETECTIONS_FRESH_S, VIEWPORT_ASSOCIATION_RADIUS, projectViewportPoint, ownShipViewportGuard,
  suppressOwnShipBoxes, OWN_SHIP_GUARD_DILATION, viewportDetectionObservations, detectionCaptureTimeSec,
  poseAtCapture, compensateViewportShift, createViewportDetectionTracker, viewportTrackPlacement,
  viewportBoxPlacement, setViewportTruthSnapDebug, viewportTruthSnapDebugEnabled,
  DETECTION_CAPTURE_INFERENCE_MS, DETECTION_CAPTURE_TAP_MS, VIEWPORT_TRACK_GATE_N, VIEWPORT_TRACK_MAX_MISSES,
  foldViewportTracks, viewportTracksFresh, viewportTrackBlocks, viewportTrackData, associateViewportTrack,
  VIEWPORT_TRACKS_FRESH_S, VIEWPORT_TRACK_MAX_AGE_S, buildTwinTopbarReadouts }
  from '../../web_gui/modules/twin-situation.js?v=20261023-dt-topbar-hud-v1';
import { createTwinBridgeClient } from '../../web_gui/modules/twin-view.js?v=20261022-radar-screen-v1';

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
test('oversized presentations are sharded; small ones stay single-message', () => {
  const sent = [], client = createTwinBridgeClient({ channel: { isOpen: () => true, send: x => sent.push(JSON.parse(x)) } });
  client.onMessage(JSON.stringify({ type: 'ready', situation_sync: 'frame-marker@1' }));
  client.onMessage(JSON.stringify({ type: 'attached', run_id: 'a' }));
  // 小包:单条 presentation(通道消息有界前的原路径)。
  const small = client.sendPresentation({ run_id: 'a', seq: 1, ribbon: [] });
  assert.equal(sent.at(-1).type, 'presentation'); assert.ok(small);
  // 大包(>46KB):拆 presentation_shard,part 按序拼回原文,Unity 侧 (run,seq) 重组。
  const big = { run_id: 'a', seq: 2, pad: 'x'.repeat(120000) };
  const inner = JSON.stringify(big);
  const result = client.sendPresentation(big);
  const shards = sent.filter(m => m.type === 'presentation_shard');
  assert.ok(shards.length >= 3, `至少 3 片,得 ${shards.length}`);
  assert.equal(shards[0].run_id, 'a'); assert.equal(shards[0].seq, 2);
  assert.deepEqual(shards.map(s => s.index), shards.map((_, i) => i));
  assert.ok(shards.every(s => s.total === shards.length && s.part.length <= 46000));
  assert.equal(shards.map(s => s.part).join(''), inner);
  assert.equal(result, inner);
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
test('DT unsafe-water zone forwards flat absolute triangles behind the safe-water layer', () => {
  const hazardProjection = { raw: { ...projection.raw, enc_navigation_area: { hazard_triangles:
    [[[10, 20], [30, 40], [50, 60]], [[1, 2], [3, 4], [5, 6]]] } } };
  const value = buildTwinPresentation(hazardProjection, chart, info);
  assert.equal(value.hazard_visible, true);
  assert.equal(value.hazard_count, 2);
  // 平铺绝对 [east,north]×0.1m,6 数/三角形(通道消息上限:对象数组会超限)。
  assert.deepEqual(value.hazard_xy, [
    info.origin_e + 20, info.origin_n + 10, info.origin_e + 40, info.origin_n + 30, info.origin_e + 60, info.origin_n + 50,
    info.origin_e + 2, info.origin_n + 1, info.origin_e + 4, info.origin_n + 3, info.origin_e + 6, info.origin_n + 5,
  ]);
  const hidden = buildTwinPresentation(hazardProjection,
    { ...chart, getLayerState: () => ({ safeWater: { visible: false } }) }, info);
  assert.equal(hidden.hazard_visible, false); assert.deepEqual(hidden.hazard_xy, []); assert.equal(hidden.hazard_count, 0);
  // 无 hazard_triangles(旧后端/旧会话)= 空集且不声明可见。
  const legacy = buildTwinPresentation(projection, chart, info);
  assert.equal(legacy.hazard_visible, false); assert.deepEqual(legacy.hazard_xy, []);
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

test('DT topbar readouts mirror the sidebar OWN SHIP math from the same projection', () => {
  const proj = { navigation: { psi: 0.92, cog: 0.905, sog: 4.11 },
    raw: { os: { floor_depth_m: 26.8, has_roll: true, roll_rad: 0.0192 } } };
  // STW=nav.sog*1.94384 toFixed(1)、COG=Math.round 归一化、DEPTH=floor 取整——
  // 与 app.js#updateOwnshipTelemetry 同款；ROLL 优先 motion 回显，缺席回退 os。
  assert.deepEqual(buildTwinTopbarReadouts(proj, null),
    { stw: '8.0', cog: '052', depth: '27', roll: '+1.1' });
  assert.equal(buildTwinTopbarReadouts(proj, { roll_deg: -2.34 }).roll, '-2.3');
  // COG 缺席回退航向（左栏同款兜底）；整组缺失显示占位符。
  assert.equal(buildTwinTopbarReadouts({ navigation: { psi: Math.PI }, raw: { os: {} } }, null).cog, '180');
  assert.deepEqual(buildTwinTopbarReadouts(null, null), { stw: '—', cog: '—', depth: '—', roll: '—' });
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
  const { viewportYoloHudSuffix, foldViewportDetections } = await import('../../web_gui/modules/twin-situation.js?v=20261023-dt-topbar-hud-v1');
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

// dt-yolo 第4轮(保留):camera_pose 正向投影本船点,框抑制与自转补偿共用此几何。
test('projectViewportPoint maps chase camera onto own ship at frame center', async () => {
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

// dt-yolo 第4轮 → P0 水线多边形:艏/艉/两舷水线角点投影取凸包(×1.3 外扩)。
test('ownShipViewportGuard + suppressOwnShipBoxes drop own hull, keep distant contacts', async () => {
  const guard = ownShipViewportGuard(
    { east: 0, north: -130, height_m: 60, yaw_deg: 0, pitch_deg: -25, fov_deg: 60 },
    { east: 0, north: 0, psi: 0, length: 45 });
  assert.ok(guard && guard.circles.length === 0 && guard.polygons.length === 1, '追随=水线凸包多边形');
  assert.equal(guard.floorY, null, '追随不启用底半平面');
  assert.ok(guard.polygons[0].length >= 3, '凸包成面');
  const boxes = [
    { index: 0, cx: 0.5, cy: 0.52, confidence: 0.9 },    // 本船船体(水线投影带内)
    { index: 1, cx: 0.5, cy: 0.47, confidence: 0.8 },    // 本船艏甲板(投影带前缘)
    { index: 2, cx: 0.2, cy: 0.3, confidence: 0.4 },     // 远处目标船(左上,带外)
    { index: 3, cx: 0.8, cy: 0.55, confidence: 0.4 },    // 远处目标船(右侧,带外)
  ];
  const kept = suppressOwnShipBoxes(boxes, guard);
  assert.deepEqual(kept.map(box => box.index), [2, 3], 'own hull boxes suppressed, distant contacts kept');
  assert.deepEqual(suppressOwnShipBoxes(boxes, null).map(box => box.index), [0, 1, 2, 3],
    'no guard (behind) = no suppression');
});

// P0 场景①:陡俯视艏点出画(出顶缘),甲板中段仍入画——旧艏点规则 bow=null 整船
// 放行漏抑制;水线多边形仍给出甲板抑制区。
test('P0 guard: bow out of frame still guards the visible deck (old bow rule leaked)', async () => {
  const top = { east: 0, north: -50, height_m: 80, yaw_deg: 0, pitch_deg: -75, fov_deg: 60 };
  const own = { east: 0, north: 0, psi: 0, length: 150 };
  assert.equal(projectViewportPoint(top, 0, 75, 0), null, '艏点(dn=125)仰出画面顶缘');
  const guard = ownShipViewportGuard(top, own);
  assert.ok(guard && guard.polygons.length === 1, '甲板舯段入画 → 多边形抑制区');
  const boxes = [
    { index: 0, cx: 0.5, cy: 0.5, confidence: 0.9 },    // 本船甲板中段大框
    { index: 1, cx: 0.55, cy: 0.75, confidence: 0.7 },  // 本船艉段甲板
    { index: 2, cx: 0.15, cy: 0.3, confidence: 0.5 },   // 侧带外远处目标船
  ];
  assert.deepEqual(suppressOwnShipBoxes(boxes, guard).map(box => box.index), [2],
    'deck boxes suppressed, off-deck contact kept');
  // psi≠0:船首向东、相机在西侧向东看——同一几何旋转后仍成面(psi 路径不退化)。
  const east = ownShipViewportGuard({ east: -100, north: 0, height_m: 60, yaw_deg: 90, pitch_deg: -25, fov_deg: 60 },
    { east: 0, north: 0, psi: Math.PI / 2, length: 45 });
  assert.ok(east && east.polygons.length === 1, '横船位姿同样投影成面');
});

// 20261015 验收轮(保留语义)+20261019 评审轮(并集):舰桥眼位俯 8°——前甲板
// 入画成水线多边形,且艏点在下半区时叠加底半平面(站间出画的近桥底带单多边
// 形覆盖不全);水平线附近目标船保留;明显抬头(仰 20°)甲板整体出画 → 不抑制。
test('bridge eye guard: deck polygon plus floor band suppress deck boxes, keep horizon contacts', async () => {
  const bridge = { east: 0, north: -8, height_m: 12, yaw_deg: 0, pitch_deg: -8, fov_deg: 60 };
  const own = { east: 0, north: 0, psi: 0, length: 45 };
  const guard = ownShipViewportGuard(bridge, own);
  assert.ok(guard, '前甲板入画 → guard 存在');
  assert.equal(guard.circles.length, 0, '桥视角无圆圈(船中不可投影)');
  assert.equal(guard.polygons.length, 1, '桥视角=前甲板水线多边形');
  assert.ok(guard.floorY > 0.6 && guard.floorY < 0.7, `艏点以下底半平面叠加, got ${guard.floorY?.toFixed(3)}`);
  const boxes = [
    { index: 0, cx: 0.5, cy: 0.85, confidence: 0.92 },  // 本船艏甲板大框(画面底带)
    { index: 1, cx: 0.5, cy: 0.95, confidence: 0.9 },   // 近桥栏杆框(站间出画的更深底带)
    { index: 2, cx: 0.35, cy: 0.4, confidence: 0.6 },   // 水平线附近目标船
  ];
  assert.deepEqual(suppressOwnShipBoxes(boxes, guard).map(box => box.index), [2],
    'deck boxes suppressed (polygon ∪ floor), horizon contact kept');
  const lookingUp = { ...bridge, pitch_deg: 20 };
  assert.equal(ownShipViewportGuard(lookingUp, own), null, '仰视时甲板出画,不抑制');
});

// 20261019 评审轮:65×5 密集水线扫描(评审同规格)——桥位姿并集后画面内本船点
// 覆盖必须 100%(评审测得单多边形 27% 漏抑制的底带被 floorY 兜住);全可见追随
// 视角矩形角点入样后透视保凸 → 100%;陡俯视艏出顶场景 ≥95%(出画边沿站间缝
// 容差)。远距目标船(60-300m 水平线带)三视角零误抑制。
test('dense 65x5 waterline scan: full own-ship coverage restored, zero distant false hits', () => {
  const scenarios = [
    { name: 'chase', pose: { east: 0, north: -130, height_m: 60, yaw_deg: 0, pitch_deg: -25, fov_deg: 60 },
      own: { east: 0, north: 0, psi: 0, length: 45 }, coverage: 1 },
    { name: 'bridge', pose: { east: 0, north: -8, height_m: 12, yaw_deg: 0, pitch_deg: -8, fov_deg: 60 },
      own: { east: 0, north: 0, psi: 0, length: 45 }, coverage: 1 },
    { name: 'top', pose: { east: 0, north: -50, height_m: 80, yaw_deg: 0, pitch_deg: -75, fov_deg: 60 },
      own: { east: 0, north: 0, psi: 0, length: 150 }, coverage: 0.95 },
  ];
  for (const { name, pose, own, coverage } of scenarios) {
    const guard = ownShipViewportGuard(pose, own);
    assert.ok(guard, `${name}: guard 存在`);
    const points = [];
    for (let i = 0; i < 65; i++) for (let j = 0; j < 5; j++) {
      const point = projectViewportPoint(pose,
        own.east + (-0.5 + j / 4) * (own.length / 4),          // beam 向(psi=0 → east)
        own.north + (-0.5 + i / 64) * own.length, 0);          // 艏艉向(north)
      if (point && point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1)
        points.push({ cx: point.x, cy: point.y });
    }
    assert.ok(points.length > 20, `${name}: 画面内有密集水线点(${points.length})`);
    const leaked = suppressOwnShipBoxes(points, guard);
    assert.ok(1 - leaked.length / points.length >= coverage,
      `${name}: 密集覆盖 ${(1 - leaked.length / points.length).toFixed(3)} ≥ ${coverage}`);
    const distant = [];
    for (const range of [60, 120, 180, 240, 300]) {
      const point = projectViewportPoint(pose, 0, own.north + range, 0);
      if (point) distant.push({ cx: point.x, cy: point.y });
    }
    if (distant.length) assert.deepEqual(suppressOwnShipBoxes(distant, guard), distant,
      `${name}: 远距目标零误抑制`);
  }
});

// P0 兜底:无任何水线站在画面内、但艏点仍在投影容差域内(艏点刚出下缘)——保留
// 旧底带 floorY 规则;艏点也出容差 → 不抑制。
test('fallback floor band when no waterline station is visible but bow is within tolerance', async () => {
  const bridge = { east: 0, north: -8, height_m: 12, yaw_deg: 0, pitch_deg: 10, fov_deg: 60 };
  const own = { east: 0, north: 0, psi: 0, length: 45 };
  const guard = ownShipViewportGuard(bridge, own);
  assert.ok(guard, '艏点容差内可投影 → 兜底 guard');
  assert.deepEqual([guard.circles.length, guard.polygons.length], [0, 0], '无面 → 底带');
  assert.ok(guard.floorY > 0.9 && guard.floorY < 1.0, `艏点刚出下缘的底半平面, got ${guard.floorY?.toFixed(3)}`);
  assert.deepEqual(suppressOwnShipBoxes([
    { index: 0, cx: 0.5, cy: 0.98 }, { index: 1, cx: 0.35, cy: 0.4 }], guard).map(box => box.index),
    [1], '底带框剔除,上半区保留');
  assert.equal(ownShipViewportGuard({ ...bridge, pitch_deg: 20 }, own), null, '艏点出容差 → 不抑制');
});

// 20261015 验收轮 truth 吸附 → P0:吸附降级为 debug 开关,默认关(默认走微跟踪
// 器补偿/外推坐标——真值贴皮不是传感器语义)。
test('viewportBoxPlacement: truth snap is debug-only and off by default', async () => {
  const box = { left: 100, top: 50, width: 40, height: 20 };
  const track = { left: 0.3, top: 0.2, width: 0.05, height: 0.03, x: 0.325, y: 0.215 };
  const plain = viewportBoxPlacement(box, track, 1280, 720);
  assert.equal(plain.snapped, false, '默认不吸附');
  assert.equal(plain.left, 100, '默认=传入(微跟踪器)坐标');
  setViewportTruthSnapDebug(true);
  try {
    assert.equal(viewportTruthSnapDebugEnabled(), true, 'debug 开关可开');
    const snapped = viewportBoxPlacement(box, track, 1280, 720, viewportTruthSnapDebugEnabled());
    assert.equal(snapped.snapped, true, '开=有包围盒的 track 触发吸附');
    assert.deepEqual([snapped.left, snapped.top, snapped.width, snapped.height],
      [0.3 * 1280, 0.2 * 720, 0.05 * 1280, 0.03 * 720], '位置/尺寸=track 投影×rect');
    const degenerate = viewportBoxPlacement(box, { left: 0.1, top: 0.1, width: 0, height: 0 }, 1280, 720, true);
    assert.equal(degenerate.snapped, false, '零尺寸 track(越界投影)不吸附');
  } finally { setViewportTruthSnapDebug(false); }
  assert.equal(viewportTruthSnapDebugEnabled(), false, '开关复位');
});

/* ── P0 检测框锁帧:采集时刻估计 / 位姿历史插值 / 自转补偿 / 微跟踪器 ─────── */

test('detection capture time subtracts the centralized inference+tap constants', () => {
  assert.ok(DETECTION_CAPTURE_INFERENCE_MS > 0 && DETECTION_CAPTURE_TAP_MS > 0, '常量为正');
  const total = (DETECTION_CAPTURE_INFERENCE_MS + DETECTION_CAPTURE_TAP_MS) / 1000;
  assert.ok(Math.abs(detectionCaptureTimeSec(1760000000.123) - (1760000000.123 - total)) < 1e-9);
  assert.equal(detectionCaptureTimeSec(undefined), null);
  assert.equal(detectionCaptureTimeSec('x'), null);
});

test('poseAtCapture interpolates linearly, wraps yaw across north, clamps or rejects outside history', () => {
  const history = [
    { tSec: 10, pose: { east: 0, north: 0, height_m: 10, fov_deg: 60, yaw_deg: 350, pitch_deg: -10 } },
    { tSec: 12, pose: { east: 2, north: 4, height_m: 14, fov_deg: 62, yaw_deg: 10, pitch_deg: -6 } },
  ];
  const mid = poseAtCapture(history, 11);
  assert.equal(mid.east, 1); assert.equal(mid.north, 2); assert.equal(mid.height_m, 12);
  assert.ok(Math.abs(mid.fov_deg - 61) < 1e-9);
  assert.ok(Math.abs(mid.yaw_deg - 360) < 1e-9, '350→10 走最短角(过北绕 360)');
  assert.equal(mid.pitch_deg, -8);
  // 越界在 POSE_HISTORY_MAX_SKEW_S 容差内 → 取最近端(开局历史短的正常 clamp)。
  assert.equal(poseAtCapture(history, 9).yaw_deg, 350, '越界取最近端(前)');
  assert.equal(poseAtCapture(history, 13).yaw_deg, 10, '越界取最近端(后)');
  // 越界超出容差 → null(跨机时钟偏移防护:弃补偿退化为无补偿关联,不 clamp 到
  // 错误位姿)。
  assert.equal(poseAtCapture(history, 8.5), null, '越窗超容差(前)→ null');
  assert.equal(poseAtCapture(history, 13.5), null, '越窗超容差(后)→ null');
  assert.equal(poseAtCapture([], 11), null);
  assert.equal(poseAtCapture(history, NaN), null);
});

test('compensateViewportShift: exact for in-place rotation, signed, inert on bad poses', () => {
  const pose = (yaw, pitch, fov = 60) => ({ east: 0, north: -130, height_m: 60, yaw_deg: yaw, pitch_deg: pitch, fov_deg: fov });
  // 纯自转(定点,yaw+pitch 同时变):补偿=把像面射线转到显示位姿系回投 → 与
  // 直接投影同几何,任意角差精确。
  const from = pose(0, -25), to = pose(24, -12);
  const captured = projectViewportPoint(from, 25, 250, 0);
  const truth = projectViewportPoint(to, 25, 250, 0);
  const shifted = compensateViewportShift(from, to, captured.x, captured.y);
  assert.ok(Math.abs(shifted.cx - truth.x) < 1e-9 && Math.abs(shifted.cy - truth.y) < 1e-9,
    `exact: got (${shifted.cx.toFixed(4)}, ${shifted.cy.toFixed(4)}) want (${truth.x.toFixed(4)}, ${truth.y.toFixed(4)})`);
  // 符号:相机右转 → 框心左移;上仰 → 框心下移。
  assert.ok(compensateViewportShift(pose(0, 0), pose(10, 0), 0.5, 0.5).cx < 0.5, '右转内容左移');
  assert.ok(Math.abs(compensateViewportShift(pose(0, 0), pose(10, 0), 0.5, 0.5).cy - 0.5) < 1e-9);
  assert.ok(compensateViewportShift(pose(0, 0), pose(0, 8), 0.5, 0.5).cy > 0.5, '上仰内容下移');
  // 变焦:内参变化同样精确(from 解码/to 编码)。
  const zoomed = compensateViewportShift(pose(0, -25), pose(0, -25, 40), captured.x, captured.y);
  const zoomTruth = projectViewportPoint(pose(0, -25, 40), 25, 250, 0);
  assert.ok(Math.abs(zoomed.cx - zoomTruth.x) < 1e-9 && Math.abs(zoomed.cy - zoomTruth.y) < 1e-9, '变焦精确');
  // 畸形位姿 → 原样返回(退化为不补偿)。
  assert.deepEqual(compensateViewportShift(null, to, 0.3, 0.4), { cx: 0.3, cy: 0.4 });
  assert.deepEqual(compensateViewportShift(from, { ...to, fov_deg: NaN }, 0.3, 0.4), { cx: 0.3, cy: 0.4 });
});

test('viewportDetectionObservations normalizes the doc domain and drops degenerate boxes', () => {
  const doc = { width: 1280, height: 720, detections: [
    { box_xyxy: [320, 180, 640, 360], class_name: 'boat', confidence: 0.9 },
    { box_xyxy: [500, 200, 500, 300], class_name: 'zero-width' },   // 零宽弃
    { box_xyxy: ['x'], class_name: 'bad' },
  ] };
  assert.deepEqual(viewportDetectionObservations(doc),
    [{ cx: 0.375, cy: 0.375, nw: 0.25, nh: 0.25, className: 'boat', confidence: 0.9 }]);
  assert.deepEqual(viewportDetectionObservations({ width: 0, height: 720, detections: [] }), []);
  assert.deepEqual(viewportDetectionObservations(null), []);
});

test('micro tracker keeps stable ids across doc order swaps and drops after max misses', () => {
  const tracker = createViewportDetectionTracker();
  const pose = { east: 0, north: -130, height_m: 60, yaw_deg: 0, pitch_deg: -25, fov_deg: 60 };
  const obs = (cx, cy) => ({ cx, cy, nw: 0.1, nh: 0.08, className: 'boat', confidence: 0.9 });
  tracker.update([obs(0.3, 0.4)], 100.0, pose);
  tracker.update([obs(0.3, 0.4), { ...obs(0.7, 0.4), confidence: 0.8 }], 100.1, pose);
  assert.equal(tracker.size, 2);
  const [first, second] = tracker.tracks();
  // 文档数组顺序对调 → id 仍按几何最近邻关联保持(不随数组序号漂移)。
  tracker.update([{ ...obs(0.7, 0.4), confidence: 0.8 }, obs(0.3, 0.4)], 100.2, pose);
  const [first2, second2] = tracker.tracks();
  assert.equal(first2.id, first.id); assert.ok(Math.abs(first2.cx - 0.3) < 1e-9);
  assert.equal(second2.id, second.id); assert.ok(Math.abs(second2.cx - 0.7) < 1e-9);
  // 连续丢失 VIEWPORT_TRACK_MAX_MISSES 个文档仍在册,超出即丢弃。
  for (let i = 1; i <= VIEWPORT_TRACK_MAX_MISSES; i++) tracker.update([obs(0.3, 0.4)], 100.2 + i * 0.1, pose);
  assert.equal(tracker.size, 2, '容忍窗内不丢');
  tracker.update([obs(0.3, 0.4)], 100.2 + (VIEWPORT_TRACK_MAX_MISSES + 1) * 0.1, pose);
  assert.equal(tracker.size, 1, '丢失超限丢弃');
});

test('constant-velocity extrapolation advances static-camera tracks to display time', () => {
  const tracker = createViewportDetectionTracker();
  const pose = { east: 0, north: -130, height_m: 60, yaw_deg: 0, pitch_deg: -25, fov_deg: 60 };
  for (let k = 0; k <= 6; k++) {
    tracker.update([{ cx: 0.3 + 0.005 * k, cy: 0.4, nw: 0.06, nh: 0.05, className: 'boat', confidence: 0.9 }],
      100 + k * 0.1, pose);   // 目标匀速 0.05 归一化/s 横穿画面
  }
  const track = tracker.tracks()[0];
  const locked = viewportTrackPlacement(track, pose, 101.0);   // 显示帧晚最后检出 0.4s
  assert.ok(Math.abs(locked.cx - 0.35) < 2e-3, `外推到显示时刻: got ${locked.cx.toFixed(4)} want ~0.35`);
  assert.ok(Math.abs(locked.cy - 0.4) < 1e-9);
  // 外推上限:断流时位置冻结在 VIEWPORT_EXTRAPOLATION_MAX_S 内的推进量。
  const capped = viewportTrackPlacement(track, pose, 103.0);
  assert.ok(capped.cx < 0.331 + 0.05 * 0.8 + 1e-9, '外推封顶,断流不飞框');
  assert.equal(viewportTrackPlacement(null, pose, 101.0), null);
});

// P0 场景④:快速转动下锁帧偏差收敛——相机原地 30°/s 右转,固定世界目标,检测
// 10Hz,显示帧滞后检出 0.45s。原始坐标直画错位 ~0.15(可见甩尾);采集位姿补偿
// +匀速外推后误差收敛到 ~0(纯自转下补偿精确,残余只剩数值噪声)。
test('fast pan: pose-compensated lock converges where raw boxes smear', () => {
  // 合成链路真实延迟 = 校准常量(20261020 记录仪:总 ~270ms);估计与真实一致才收敛。
  const LAT = (DETECTION_CAPTURE_INFERENCE_MS + DETECTION_CAPTURE_TAP_MS) / 1000;
  const poseAt = t => ({ east: 0, north: -130, height_m: 60, yaw_deg: 30 * (t - 200), pitch_deg: -25, fov_deg: 60 });
  const history = [], tracker = createViewportDetectionTracker();
  let lastObs = null;
  for (let k = 0; k <= 9; k++) {
    const t = 200 + k * 0.1;                       // 文档 received_at = t + LAT
    history.push({ tSec: t, pose: poseAt(t) });
    const truth = projectViewportPoint(poseAt(t), 25, 250, 0);
    lastObs = { cx: truth.x, cy: truth.y, nw: 0.06, nh: 0.05, className: 'boat', confidence: 0.9 };
    tracker.update([lastObs], detectionCaptureTimeSec(t + LAT), poseAtCapture(history, detectionCaptureTimeSec(t + LAT)));
  }
  const displayT = 200.9 + 0.45, displayPose = poseAt(displayT);
  const truth = projectViewportPoint(displayPose, 25, 250, 0);
  const locked = viewportTrackPlacement(tracker.tracks()[0], displayPose, displayT);
  const rawError = Math.abs(lastObs.cx - truth.x);
  const lockedError = Math.hypot(locked.cx - truth.x, locked.cy - truth.y);
  assert.ok(rawError > 0.1, `原始坐标错位可见: ${rawError.toFixed(3)}`);
  assert.ok(lockedError < 0.02, `补偿后锁帧收敛: ${lockedError.toFixed(5)}`);
  assert.ok(lockedError < rawError / 5, `误差压到原始 1/5 以下: ${lockedError.toFixed(5)} vs ${rawError.toFixed(3)}`);
});

// P0 场景②/③:追随本船居中——相机平移追随时本船居中静止,目标船在像面移动;
// 微跟踪器按补偿后坐标关联,目标船 id 稳定、位置连续(不被相机平移视差打断)。
test('chase-follow: moving contact keeps one stable id while camera translates', () => {
  const poseAt = t => ({ east: 0, north: -130 + 6 * (t - 300), height_m: 60, yaw_deg: 0, pitch_deg: -25, fov_deg: 60 });
  const tracker = createViewportDetectionTracker();
  const history = [];
  for (let k = 0; k <= 5; k++) {
    const t = 300 + k * 0.1;
    history.push({ tSec: t, pose: poseAt(t) });
    const truth = projectViewportPoint(poseAt(t), 25, 400 - 6 * (t - 300), 0);   // 目标静止,相机前移 → 视差运动
    tracker.update([{ cx: truth.x, cy: truth.y, nw: 0.06, nh: 0.05, className: 'boat', confidence: 0.9 }],
      t, poseAtCapture(history, t));
  }
  assert.equal(tracker.size, 1, '相机平移视差不炸关联(补偿后位移在门内,单一 id)');
  const track = tracker.tracks()[0];
  const displayT = 300.5 + 0.4;
  const locked = viewportTrackPlacement(track, poseAt(displayT), displayT);
  const truth = projectViewportPoint(poseAt(displayT), 25, 400 - 6 * 0.5, 0);
  const raw = projectViewportPoint(poseAt(300.5), 25, 400 - 6 * 0.5, 0);
  assert.ok(Math.abs(locked.cx - truth.x) < Math.abs(raw.x - truth.x),
    `追随平移下外推不劣化: lockedΔ=${Math.abs(locked.cx - truth.x).toFixed(4)} rawΔ=${Math.abs(raw.x - truth.x).toFixed(4)}`);
});

// ── P3 viewport_tracks@1:fold / 新鲜窗 / 数据块 TRK 优先 DET 回退 / 框↔航迹关联 ──
const TRACK_DOC = { schema: 'viewport_tracks@1', t_s: 6, received_at: 2, tracks: [
  { track_id: 1, status: 'confirmed', existence_prob: 0.95, bearing_rad: 0.0727,
    range_m: 413.06, north_m: 412, east_m: 30 } ] };
test('foldViewportTracks keeps the latest doc and ignores out-of-order messages', () => {
  assert.equal(foldViewportTracks(null, {}, 0), null, '无键透传原状态');
  assert.equal(foldViewportTracks(null, TRACK_DOC, 1), null, 'raw 无 viewport_tracks 键不建状态');
  const first = foldViewportTracks(null, { viewport_tracks: TRACK_DOC }, 10);
  assert.equal(first.doc, TRACK_DOC);
  const older = foldViewportTracks(first, { viewport_tracks: { ...TRACK_DOC, received_at: 1 } }, 11);
  assert.equal(older, first, '乱序旧消息(received_at 回退)不覆盖');
  const newer = foldViewportTracks(first, { viewport_tracks: { ...TRACK_DOC, received_at: 3, tracks: [] } }, 12);
  assert.equal(newer.doc.received_at, 3);
});
test('viewportTracksFresh mirrors the detection freshness window', () => {
  assert.equal(VIEWPORT_TRACKS_FRESH_S, VIEWPORT_DETECTIONS_FRESH_S);
  assert.equal(viewportTracksFresh({ doc: { tracks: [], age_s: 0.5 } }, 0), true);
  assert.equal(viewportTracksFresh({ doc: { tracks: [], age_s: 5 } }, 0), false);
  assert.equal(viewportTracksFresh({ doc: { tracks: [] }, at: Date.now() - 100 }, Date.now()), true);
  assert.equal(viewportTracksFresh({ doc: { tracks: [] }, at: Date.now() - 5000 }, Date.now()), false);
  assert.equal(viewportTracksFresh(null, 0), false);
});
test('viewportTrackBlocks renders filtered brg/rng/conf rows (frozen at track time)', () => {
  const blocks = viewportTrackBlocks(TRACK_DOC.tracks[0]);
  assert.deepEqual(blocks.map(b => b.label), ['BRG', 'RNG', 'CONF']);
  assert.equal(blocks[0].value, String(Math.round(0.0727 * 180 / Math.PI)));          // 4 DEG
  assert.equal(blocks[1].value, (413.06 / 1852).toFixed(2));                          // 0.22 NM
  assert.equal(blocks[2].value, (0.95).toFixed(3));                                   // CONF 0.950
  assert.deepEqual(viewportTrackBlocks(null), []);
  assert.deepEqual(viewportTrackBlocks({ bearing_rad: NaN, range_m: 10 }), [], '无效滤波态不出块');
});
test('viewportTrackData prefers TRK and falls back to the raw-detection blocks', () => {
  const detBlocks = [{ label: 'BRG', value: '5', unit: 'DEG' }];
  const trk = viewportTrackData(TRACK_DOC.tracks[0], detBlocks);
  assert.equal(trk.source, 'TRK');
  assert.deepEqual(trk.blocks.map(b => b.label), ['BRG', 'RNG', 'CONF']);
  const det = viewportTrackData(null, detBlocks);
  assert.equal(det.source, 'DET');
  assert.equal(det.blocks, detBlocks, '回退透传裸检测数据块(不改写)');
  const invalid = viewportTrackData({ bearing_rad: NaN, range_m: 1, existence_prob: 1 }, detBlocks);
  assert.equal(invalid.source, 'DET', 'track 无效 = 缺席,回退 DET');
});
test('associateViewportTrack pairs a locked box with the nearest projected track', () => {
  const pose = { east: 0, north: 0, height_m: 12, yaw_deg: 0, pitch_deg: 0, fov_deg: 60 };
  const track = TRACK_DOC.tracks[0];   // 绝对 NE (412, 30),水线高 0
  const projected = projectViewportPoint(pose, track.east_m, track.north_m, 0);
  assert.ok(projected, '前置:track 可投影进视口');
  const locked = { cx: projected.x, cy: projected.y };
  assert.equal(associateViewportTrack([track], locked, pose), track);
  // 投影远离锁帧框心(> VIEWPORT_ASSOCIATION_RADIUS)→ 无关联 → 渲染层走 DET 回退。
  assert.equal(associateViewportTrack([track], { cx: 0.9, cy: 0.9 }, pose), null);
  // 相机身后的航迹不可投影 → null;空集/无位姿同 null。
  assert.equal(associateViewportTrack([{ north_m: -400, east_m: 0 }], locked, pose), null);
  assert.equal(associateViewportTrack(null, locked, pose), null);
  assert.equal(associateViewportTrack([track], locked, null), null);
});

// 评审 Q4:断流期间 update 不被调、misses 不增长——expire() 按 track.t 墙龄独立
// 过期(与 detectionCaptureTimeSec 同一 received_at 时间域),恢复瞬间不再按陈旧
// 速度关联/瞬跳。
test('detection tracker expires stale tracks by wall age without new documents', () => {
  const tracker = createViewportDetectionTracker();
  const pose = { east: 0, north: 0, height_m: 12, yaw_deg: 0, pitch_deg: 0, fov_deg: 60 };
  tracker.update([{ cx: 0.5, cy: 0.5, nw: 0.06, nh: 0.05, className: 'boat', confidence: 0.9 }], 300.0, pose);
  assert.equal(tracker.size, 1);
  assert.equal(tracker.expire(300.0 + VIEWPORT_TRACK_MAX_AGE_S - 0.01), 1, '窗内保留(文档节拍容忍期)');
  assert.equal(tracker.expire(300.0 + VIEWPORT_TRACK_MAX_AGE_S + 0.01), 0, '越窗过期:断流期间不再挂旧速度');
  // 新文档刷新 t 后,expire 不误杀活跃 track。
  tracker.update([{ cx: 0.5, cy: 0.5, nw: 0.06, nh: 0.05, className: 'boat', confidence: 0.9 }], 301.0, pose);
  assert.equal(tracker.expire(301.0 + 0.1), 1);
  assert.equal(tracker.expire(Number.NaN), 1, '无效时刻不动状态');
  assert.equal(VIEWPORT_TRACK_MAX_AGE_S, (VIEWPORT_TRACK_MAX_MISSES + 1) / 10, '10Hz 节拍 × misses 容忍');
});
