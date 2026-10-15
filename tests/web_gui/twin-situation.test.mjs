import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeFrameMarker, containedVideoRect, matchedSituationFrame, buildTwinPresentation, layoutTwinLabels,
  pickTwinTarget, toggleYoloKey, latestDetectionForTrack } from '../../web_gui/modules/twin-situation.js?v=20261011-dt-sensor-overlay-v1';
import { createTwinBridgeClient } from '../../web_gui/modules/twin-view.js?v=20261015-bridge-look';

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

test('target camera command preserves selected run and generation identity', () => {
  const sent = [], client = createTwinBridgeClient({ channel: { isOpen: () => true, send: x => sent.push(JSON.parse(x)) } });
  client.sendCameraTarget('run-a', 'run-a:8:3');
  assert.deepEqual(sent[0], { type: 'camera_target', run_id: 'run-a', target_key: 'run-a:8:3' });
});
