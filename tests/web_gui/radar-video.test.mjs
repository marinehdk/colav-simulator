import test from 'node:test';
import assert from 'node:assert/strict';
import { deflateSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { RadarVideoBuffer, decodeRadarVideo } from '../../web_gui/modules/radar-video.js?v=20261023-radar-card-v4';

const encode = (bytes, shape) => ({ encoding: 'deflate-base64-u8', shape,
  data: deflateSync(bytes).toString('base64'), sha256: createHash('sha256').update(bytes).digest('hex') });

function fixture() {
  return { spokes: 64, range_m: 1000, spoke_seq_start: 0, spoke_seq_end: 64,
    rows: [0], row_times_s: [1], row_origins_ne_m: [[100, 200]], row_bearings_rad: [0],
    checkpoint: { ...encode(new Uint8Array(64 * 64), [64, 64]), t_s: 0,
      row_times_s: Array(64).fill(-1), row_origins_ne_m: Array.from({ length: 64 }, () => [100, 200]), row_bearings_rad: Array(64).fill(0) },
    chunk: encode(Uint8Array.from({ length: 64 }, (_, i) => i === 32 ? 255 : 0), [1, 64]),
  };
}

test('binary backend evidence verifies length and hash before drawing', async () => {
  const frame = fixture();
  assert.equal((await decodeRadarVideo(frame.chunk))[32], 255);
  await assert.rejects(decodeRadarVideo({ ...frame.chunk, sha256: 'bad' }), /HASH/);
  await assert.rejects(decodeRadarVideo({ ...frame.chunk, shape: [1, 63] }), /LENGTH/);
});

test('recorded checkpoint and spoke origin support motion compensation and heading-up', async () => {
  const buffer = new RadarVideoBuffer();
  await buffer.apply(fixture());
  const model = { hasOwnship: true, ownshipNorth: 100, ownshipEast: 200, ownshipHeadingRad: Math.PI / 2, simTimeS: 1, scanPeriodS: 2.5, rangeScaleM: 1000 };
  const northUp = buffer.raster(128, model);
  assert.ok(northUp.some((v, i) => i % 4 === 1 && v > 0));
  const headingUp = buffer.raster(128, model, { headingUp: true });
  assert.notDeepEqual(headingUp, northUp);
  // 契约钉子:raster 对缺 hasOwnship 的 model 返回空白——独立雷达屏
  // (radar-screen.js) 曾因此黑底无回波,必须显式带 hasOwnship: true。
  const noOwnship = buffer.raster(128, { ...model, hasOwnship: undefined });
  assert.ok(noOwnship.every(v => v === 0), 'missing hasOwnship must yield a blank raster');
  buffer.clear();
  assert.equal(buffer.status, 'NO_VIDEO');
  assert.equal(buffer.data, null);
});

test('standalone radar screen passes hasOwnship to the video raster (black-disc regression)', async () => {
  const { readFile } = await import('node:fs/promises');
  const screen = await readFile(new URL('../../web_gui/modules/radar-screen.js', import.meta.url), 'utf8');
  const rasterCall = screen.slice(screen.indexOf('videoBuffer.raster('));
  assert.match(rasterCall.slice(0, 400), /hasOwnship: true/);
});
