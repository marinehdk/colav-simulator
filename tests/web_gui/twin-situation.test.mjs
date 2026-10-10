import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeFrameMarker, containedVideoRect, matchedSituationFrame, buildTwinPresentation, layoutTwinLabels } from '../../web_gui/modules/twin-situation.js';
import { createTwinBridgeClient } from '../../web_gui/modules/twin-view.js';

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
