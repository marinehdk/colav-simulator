import test from 'node:test';
import assert from 'node:assert/strict';
import { chooseTwinStreamProfile, sampleTwinVideoStats } from '../../web_gui/modules/twin-stream-quality.js?v=20261008-dt-quality-v1';
import { createTwinBridgeClient } from '../../web_gui/modules/twin-view.js?v=20261010-dt-situation-v1';

test('viewport selects 1080p or 1440p using contained physical video pixels', () => {
  assert.equal(chooseTwinStreamProfile(1800, 1000, 1), '1440p');
  assert.equal(chooseTwinStreamProfile(2464, 1153, 1), '1440p');
  assert.equal(chooseTwinStreamProfile(1280, 720, 2), '1440p');
  assert.equal(chooseTwinStreamProfile(3840, 540, 1), '1080p', 'letterboxes do not inflate capture demand');
  assert.equal(chooseTwinStreamProfile(0, 0, 1), '1080p');
});

test('metrics use received video counters, never Unity render FPS or configured bitrate', () => {
  const video = (timestamp, frames, bytes, extra = {}) => [
    { id: 'in', type: 'inbound-rtp', kind: 'video', timestamp, framesDecoded: frames, bytesReceived: bytes,
      frameWidth: 2560, frameHeight: 1440, codecId: 'c', ...extra },
    { id: 'c', type: 'codec', mimeType: 'video/H264' },
  ];
  const first = sampleTwinVideoStats(video(1000, 10, 1000000));
  assert.equal(first.fps, null);
  const next = sampleTwinVideoStats(video(2000, 40, 2500000), first);
  assert.equal(next.fps, 30);
  assert.equal(next.bitrateMbps, 12);
  assert.equal(next.width, 2560);
  assert.equal(next.codec, 'video/H264');
  const reconnect = sampleTwinVideoStats(video(3000, 5, 100), next);
  assert.equal(reconnect.fps, null, 'counter reset cannot invent a rate');
  assert.equal(reconnect.bitrateMbps, null);
});

test('stream profile command is feature-negotiated and rejects unknown profiles', () => {
  const sent = [];
  const client = createTwinBridgeClient({ channel: { isOpen: () => true, send: json => sent.push(JSON.parse(json)) } });
  client.onMessage(JSON.stringify({ type: 'ready', video_profiles: ['1080p', '1440p'] }));
  client.sendStreamProfile('1440p');
  assert.deepEqual(sent.at(-1), { type: 'stream_profile', value: '1440p' });
  assert.throws(() => client.sendStreamProfile('4k'), /profile/i);
});


test('network and decode metrics separate transport loss from codec/render blur', () => {
  const rows = (timestamp, framesDecoded, packetsReceived, packetsLost, totalDecodeTime, jitterBufferDelay, jitterBufferEmittedCount) => [
    { id: 'in', type: 'inbound-rtp', kind: 'video', timestamp, framesDecoded, bytesReceived: timestamp * 1000,
      packetsReceived, packetsLost, totalDecodeTime, jitterBufferDelay, jitterBufferEmittedCount, jitter: 0.003,
      framesDropped: 0, freezeCount: 0 },
    { type: 'candidate-pair', state: 'succeeded', nominated: true, currentRoundTripTime: 0.004 },
  ];
  const previous = sampleTwinVideoStats(rows(1000, 10, 100, 1, 0.1, 0.3, 10));
  const current = sampleTwinVideoStats(rows(2000, 40, 200, 2, 0.16, 0.9, 40), previous);
  assert.equal(current.lossRatio, 1 / 101);
  assert.ok(Math.abs(current.decodeMs - 2) < 1e-8);
  assert.ok(Math.abs(current.jitterBufferMs - 20) < 1e-8);
  assert.equal(current.jitterMs, 3);
  assert.equal(current.rttMs, 4);
  const missing = sampleTwinVideoStats([{ id: 'x', type: 'inbound-rtp', kind: 'video', timestamp: 1 }]);
  assert.equal(missing.lossRatio, null); assert.equal(missing.decodeMs, null);
});
