import test from 'node:test';
import assert from 'node:assert/strict';
import { createChartRadarOverlay, N_METERS_PER_NM, radarOverlayAlpha } from '../../web_gui/modules/chart-radar-overlay.js?v=20261023-radar-overlay-v3';

test('radarOverlayAlpha thresholds away clutter and black, keeps strong returns', () => {
  assert.equal(radarOverlayAlpha(0), 0, 'no-return black must be transparent');
  assert.equal(radarOverlayAlpha(90), 0, 'at the cut nothing shows yet');
  assert.equal(radarOverlayAlpha(60), 0, 'sea-clutter speckle is suppressed');
  const faint = radarOverlayAlpha(100);
  const strong = radarOverlayAlpha(200);
  assert.ok(faint > 0 && faint < strong, 'alpha ramps with video value');
  assert.equal(strong, Math.round(255 * 0.85), 'strong returns cap at max alpha');
  assert.ok(radarOverlayAlpha(255) >= strong, 'saturated stays at the cap');
  assert.equal(radarOverlayAlpha('x'), 0, 'non-numeric falls back to transparent');
});

// 桩缓冲:记录 apply/clear,可编程 status/rangeM —— 解码链本体由 radar-video.test 覆盖。
function stubBuffer({ status = 'SHADOW', rangeM = 6000 } = {}) {
  const calls = { apply: 0, clear: 0 };
  return {
    calls,
    status,
    rangeM,
    async apply() { calls.apply++; this.status = status; this.rangeM = rangeM; },
    clear() { calls.clear++; this.status = 'NO_VIDEO'; this.rangeM = undefined; },
  };
}

const video = (seq, sha = 'a'.repeat(64)) => ({
  status: 'SHADOW', range_m: 6000, spokes: 720, spoke_seq_end: seq,
  chunk: { sha256: sha }, rows: [], row_times_s: [], row_bearings_rad: [], row_origins_ne_m: [],
});
const envelope = (runId, seq, sha) => ({ run_id: runId, sim_time: 12, os: { x: 10, y: 20, north: 10, east: 20 },
  radar_scans: [{ sensor_label: 'radar_x', sensor_instance_id: 'r1', sample_seq: seq, shadow_video: video(seq, sha) }] });

test('chart overlay feeds the radar_x scan, dedups chunks and skips incomplete video', async () => {
  const buffer = stubBuffer();
  const overlay = createChartRadarOverlay({ buffer });
  assert.equal(overlay.info().ready, false, 'no video applied yet');
  overlay.update(envelope('run-1', 5));
  await overlay.settled();
  assert.equal(buffer.calls.apply, 1);
  assert.deepEqual(overlay.info(), { ready: true, rangeM: 6000, status: 'SHADOW' });
  overlay.update(envelope('run-1', 5));          // same seq+sha → deduped
  await overlay.settled();
  assert.equal(buffer.calls.apply, 1, 'duplicate chunk must not re-apply');
  overlay.update({ run_id: 'run-1', radar_scans: [{ sensor_label: 'radar_x', sensor_instance_id: 'r1',
    sample_seq: 6, shadow_video: { ...video(6), status: 'INCOMPLETE' } }] });
  await overlay.settled();
  assert.equal(buffer.calls.apply, 1, 'incomplete revolution is skipped');
  assert.ok(overlay.info().ready);
});

test('stream switch rebuilds the buffer and waits for fresh video before ready again', async () => {
  const buffer = stubBuffer();
  const overlay = createChartRadarOverlay({ buffer });
  overlay.update(envelope('run-1', 5));
  await overlay.settled();
  assert.ok(overlay.info().ready);
  const clearsBefore = buffer.calls.clear;   // 首次附着流也会防御性 clear 一次
  overlay.update(envelope('run-2', 5, 'b'.repeat(64)));
  assert.equal(buffer.calls.clear, clearsBefore + 1, 'run switch clears the previous revolution');
  assert.equal(overlay.info().ready, false, 'stale video from the old run must not stay ready');
  await overlay.settled();
  assert.equal(buffer.calls.apply, 2);
  assert.ok(overlay.info().ready, 'fresh run video restores the overlay');
});

test('drawVideo carries range and sweep azimuth; without a DOM canvas it reports drew=false', async () => {
  const overlay = createChartRadarOverlay({ buffer: stubBuffer({ rangeM: 3 * N_METERS_PER_NM }) });
  overlay.update(envelope('run-1', 5));
  await overlay.settled();
  const node = overlay.drawVideo(null, 100, 100, 0.04, 10, 20, 6, 2.5);
  assert.equal(node.drew, false);
  assert.equal(node.rangeM, 3 * N_METERS_PER_NM);
  // sweep azimuth mirrors radar-ppi sweepAzimuthRad(6, 2.5) = 2.4 turns → 0.4 turn.
  assert.ok(Math.abs(node.sweepAzRad - 0.4 * 2 * Math.PI) < 1e-9);
  const noScale = overlay.drawVideo({}, 0, 0, 0, 0, 0, 6, 2.5);
  assert.equal(noScale.drew, false, 'non-positive scale never draws');
});

test('buffer apply failure downgrades to INVALID_VIDEO without throwing', async () => {
  const buffer = { status: 'NO_VIDEO', rangeM: 0, clear() {}, async apply() { throw new Error('boom'); } };
  const overlay = createChartRadarOverlay({ buffer });
  overlay.update(envelope('run-1', 5));
  await overlay.settled();
  assert.deepEqual(overlay.info(), { ready: false, rangeM: 0, status: 'INVALID_VIDEO' });
});
