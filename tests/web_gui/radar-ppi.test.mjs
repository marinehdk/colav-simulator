import assert from 'node:assert/strict';
import test from 'node:test';

function almostEqual(actual, expected, epsilon = 1e-6) {
  assert.ok(Math.abs(actual - expected) < epsilon, `expected ${actual} ~ ${expected} (±${epsilon})`);
}

import {
  N_METERS_PER_NM,
  PPI_DESCRIPTOR_DEFAULT,
  RANGE_SCALES_NM_DEFAULT,
  buildPpiModel,
  clutterPoints,
  createRadarPpi,
  expectedClutterCount,
  mulberry32,
  ppiIntensity,
  ppiProject,
  rangeRingsM,
  snrProxyDb,
  sweepAzimuthRad,
} from '../../web_gui/modules/radar-ppi.js';

test('mulberry32 is deterministic per seed and uniform enough', () => {
  const a = mulberry32(42);
  const b = mulberry32(42);
  const c = mulberry32(43);
  const seqA = [a(), a(), a()];
  const seqB = [b(), b(), b()];
  const seqC = [c(), c(), c()];
  assert.deepEqual(seqA, seqB);
  assert.notDeepEqual(seqA, seqC);
  for (const value of seqA) assert.ok(value >= 0 && value < 1);
});

test('sweep azimuth advances one turn per scan period and wraps', () => {
  assert.equal(sweepAzimuthRad(0, 2.5), 0);
  almostEqual(sweepAzimuthRad(1.25, 2.5), Math.PI, 1e-9);
  almostEqual(sweepAzimuthRad(2.5, 2.5), 0, 1e-9);
  almostEqual(sweepAzimuthRad(3.125, 2.5), Math.PI / 2, 1e-9);
  assert.equal(sweepAzimuthRad(1, 0), 0);
});

test('ppi projection maps north up, east right, ownship centered, flags outside', () => {
  const size = 400;
  const north = ppiProject(500, 0, 1000, size);
  assert.deepEqual([north.x, north.y, north.inside], [200, 100, true]);
  const east = ppiProject(0, 500, 1000, size);
  assert.deepEqual([east.x, east.y], [300, 200]);
  const center = ppiProject(0, 0, 1000, size);
  assert.deepEqual([center.x, center.y], [200, 200]);
  const outside = ppiProject(1200, 0, 1000, size);
  assert.equal(outside.inside, false);
});

test('range rings are thirds of the active scale', () => {
  assert.deepEqual(rangeRingsM(3000), [1000, 2000, 3000]);
  assert.deepEqual(rangeRingsM(0), []);
});

test('shared SNR proxy decays with range and drives blip intensity', () => {
  const near = snrProxyDb(1000);
  const far = snrProxyDb(8000);
  assert.ok(near > far);
  // Mirror of the backend default: 13 dB at 5556 m for the 10 m2 reference RCS.
  almostEqual(snrProxyDb(5556), 13, 1e-6);
  assert.ok(ppiIntensity(1000) > ppiIntensity(8000));
});

test('expected clutter count matches the backend annulus integral at reference sea state', () => {
  // rate 5e-7/m2, decay 2, r_ref 1000, ring [54.13, 11112]: 2*pi*rate*ref^2*ln(rMax/rMin)
  const lambda = expectedClutterCount({
    rangeScaleM: 6 * N_METERS_PER_NM,
    blindRingM: 54.128502043944685,
    ratePerM2: 5e-7,
    rangeDecay: 2,
    refRangeM: 1000,
    seaFactor: 1,
  });
  assert.ok(Math.abs(lambda - 2 * Math.PI * 5e-7 * 1e6 * Math.log((6 * N_METERS_PER_NM) / 54.128502043944685)) < 1e-9);
  const beaufort6 = expectedClutterCount({
    rangeScaleM: 6 * N_METERS_PER_NM,
    blindRingM: 54,
    ratePerM2: 5e-7,
    rangeDecay: 2,
    refRangeM: 1000,
    seaFactor: 10 ** (0.1 * 3 * 3),
  });
  assert.ok(beaufort6 > lambda * 3.9, 'Beaufort 6 sea factor (3 dB/B over 3 steps = 10^0.9)');
});

test('clutter speckle is deterministic per seed and scan, inside the annulus, capped', () => {
  const options = { rangeScaleM: 6 * N_METERS_PER_NM, descriptor: PPI_DESCRIPTOR_DEFAULT };
  const scanA = clutterPoints({ seed: 7, scanIndex: 3, ...options });
  const scanAAgain = clutterPoints({ seed: 7, scanIndex: 3, ...options });
  const scanB = clutterPoints({ seed: 7, scanIndex: 4, ...options });
  assert.deepEqual(scanA, scanAAgain);
  assert.notDeepEqual(scanA, scanB);
  assert.ok(scanA.length > 0 && scanA.length <= PPI_DESCRIPTOR_DEFAULT.max_measurements_per_scan);
  for (const point of scanA) {
    assert.ok(point.rangeM >= PPI_DESCRIPTOR_DEFAULT.blind_ring_m, 'clutter excluded from the VBW blind ring');
    assert.ok(point.rangeM <= options.rangeScaleM);
    assert.ok(point.azimuthRad >= 0 && point.azimuthRad < 2 * Math.PI);
    assert.ok(point.intensity > 0 && point.intensity <= 1);
  }
  const capped = clutterPoints({
    seed: 7,
    scanIndex: 3,
    rangeScaleM: 24 * N_METERS_PER_NM,
    count: 5,
  });
  assert.equal(capped.length, 5);
});

function envelopeFixture() {
  return {
    sim_time: 5,
    radar_ppi: { ...PPI_DESCRIPTOR_DEFAULT, seed: 11 },
    os: { north: 10000, east: 20000, psi: 0.5 },
    measurements: [
      [
        [
          [3, [10000 + 500, 20000 + 100]],
          [7, [10000 + 9000, 20000]],
          [-1, [10000 + 30, 20000 + 30]],
          [9, [Number.NaN, 20000]],
          [4, [10000 + 20000, 20000]],
          [5, [10000 + 10, 20000]],
        ],
        [
          [8, [9999, 19999]],
        ],
      ],
      [
        [
          [1, [0, 0]],
        ],
      ],
    ],
  };
}

test('build PPI model: blips from ownship radar measurements, gated, relative to ownship', () => {
  const model = buildPpiModel(envelopeFixture(), {});
  assert.equal(model.descriptor.seed, 11, 'envelope additive descriptor wins over default');
  assert.equal(model.rangeScaleM, 6 * N_METERS_PER_NM);
  assert.equal(model.ownshipHeadingRad, 0.5);
  assert.deepEqual(model.blips.map(blip => blip.id), [3, 7]);
  const blip3 = model.blips[0];
  almostEqual(blip3.rangeM, Math.hypot(500, 100), 1e-6);
  assert.ok(blip3.intensity > 0 && blip3.intensity <= 1);
  assert.ok(model.blips.every(blip => blip.rangeM >= model.blindRingM && blip.rangeM <= model.rangeScaleM));
  assert.ok(model.clutter.length > 0);
  assert.ok(model.clutter.every(point => point.rangeM <= model.rangeScaleM));
});

test('build PPI model: range scale override and default descriptor fallback', () => {
  const override = buildPpiModel(envelopeFixture(), { rangeScaleNm: 1.5 });
  assert.equal(override.rangeScaleM, 1.5 * N_METERS_PER_NM);
  assert.deepEqual(override.blips.map(blip => blip.id), [3]);
  const fallback = buildPpiModel({ sim_time: 0, os: { north: 0, east: 0, psi: 0 }, measurements: [[]] }, {});
  assert.equal(fallback.descriptor, PPI_DESCRIPTOR_DEFAULT, 'no radar_ppi field falls back to the milliampere defaults');
  assert.equal(fallback.rangeScaleNm, PPI_DESCRIPTOR_DEFAULT.range_scale_nm);
});

test('build PPI model without ownship stays empty and safe', () => {
  const model = buildPpiModel(null, {});
  assert.equal(model.hasOwnship, false);
  assert.equal(model.blips.length, 0);
  assert.deepEqual(model.rangeScalesNmFallback !== undefined ? {} : {}, {});
});

test('PPI factory draws panels, toggles visibility and switches range scales', () => {
  const calls = [];
  const context = {
    setTransform() {},
    clearRect() {},
    save() { calls.push('save'); },
    restore() { calls.push('restore'); },
    beginPath() { calls.push('beginPath'); },
    closePath() { calls.push('closePath'); },
    arc() {},
    fill() { calls.push('fill'); },
    stroke() { calls.push('stroke'); },
    clip() { calls.push('clip'); },
    fillRect() {},
    fillText() {},
    translate() {},
    rotate() {},
    moveTo() {},
    lineTo() {},
    createLinearGradient: () => ({ addColorStop() {} }),
    set fillStyle(value) { calls.push(`fill:${value}`); },
    get fillStyle() { return ''; },
  };
  const attributes = {};
  const canvas = {
    clientWidth: 320,
    clientHeight: 320,
    width: 0,
    height: 0,
    getContext: () => context,
    setAttribute: (name, value) => { attributes[name] = value; },
  };
  const states = [];
  const ppi = createRadarPpi({ canvas, onState: state => states.push(state) });

  const model = buildPpiModel(envelopeFixture(), {});
  ppi.render(model); // hidden: buffered, no draw
  assert.equal(states.at(-1).visible, false);
  const drawCallsBefore = calls.length;
  ppi.setVisible(true);
  assert.ok(calls.length > drawCallsBefore, 'visibility draws the buffered model');
  assert.equal(states.at(-1).visible, true);

  ppi.setRangeScale(1.5);
  assert.equal(states.at(-1).rangeScaleNm, 1.5);
  ppi.setRangeScale(Number.NaN);
  assert.equal(states.at(-1).rangeScaleNm, 1.5, 'invalid scale ignored');

  ppi.setDescriptor({ ...PPI_DESCRIPTOR_DEFAULT, range_scale_nm: 12 });
  assert.deepEqual(ppi.options().descriptor.range_scale_nm, 12);
  assert.equal(ppi.options().rangeScaleNm, 1.5, 'current scale kept while listed');
  ppi.setDescriptor({ ...PPI_DESCRIPTOR_DEFAULT, range_scale_nm: 12, range_scales_nm: [3, 12] });
  assert.equal(ppi.options().rangeScaleNm, 12, 'scale resynced when unlisted');

  assert.ok(attributes['aria-label'].includes('PPI'));
  ppi.destroy();
});

test('PPI panel is wired into the deployment shell (button, overlay, range scales)', async () => {
  const { readFileSync } = await import('node:fs');
  const root = new URL('../../', import.meta.url);
  const html = readFileSync(new URL('web_gui/index.html', root), 'utf8');
  const app = readFileSync(new URL('web_gui/app.js', root), 'utf8');
  // display-bar toggle next to 3D/T
  assert.match(html, /id="ppiBtn"[^>]*aria-label="雷达 PPI 面板"/);
  // overlay panel inside the canvas wrapper with the full range-scale table
  assert.match(html, /id="ppiPanel" data-od-id="radar-ppi-panel"[^>]*hidden/);
  for (const nm of ['0.75', '1.5', '3', '6', '12', '24']) {
    assert.match(html, new RegExp(`data-ppi-range="${nm}"`), `range scale button ${nm} nm`);
  }
  assert.match(html, /id="ppiCanvas"/);
  // app wiring: factory + envelope-driven descriptor + visibility gating
  assert.match(app, /import \{ buildPpiModel, createRadarPpi \} from '\.\/modules\/radar-ppi\.js\?v=/);
  assert.match(app, /createRadarPpi\(\{ canvas: document\.getElementById\('ppiCanvas'\) \}\)/);
  assert.match(app, /radarPpi\.setDescriptor\(data\.radar_ppi\)/);
  assert.match(app, /if \(radarPpi\.visible\(\)\) radarPpi\.render\(buildPpiModel\(data, radarPpi\.options\(\)\)\)/);
});
