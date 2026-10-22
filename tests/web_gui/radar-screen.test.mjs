import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import {
  DEFAULT_PALETTE,
  FURUNO_RANGE_TABLE,
  PALETTES,
  PALETTE_NAMES,
  PALETTE_TOKENS,
  PRESENTATION_MODES,
  TRAIL_STEPS,
  VECTOR_TIME_MINUTES,
  activeAlerts,
  bcrBct,
  buildScreenTargets,
  clutterSuppressionFactor,
  cpaTcpa,
  formatBearing,
  formatEbl,
  formatLatLon,
  formatRangeBox,
  formatUtcStamp,
  formatVrm,
  paletteVars,
  rangeEntry,
  relativeBearing,
  stepPresentationMode,
  stepRangeNm,
  stepTrails,
  stepVectorTime,
  syncControlsFromDescriptor,
  targetSymbolState,
  threatLevel,
} from '../../web_gui/modules/radar-screen.js?v=20261022-radar-screen-v1';

const N_METERS_PER_NM = 1852;

function almostEqual(actual, expected, epsilon = 1e-6) {
  assert.ok(Math.abs(actual - expected) < epsilon, `expected ${actual} ~ ${expected} (±${epsilon})`);
}

/* ── Furuno 17-scale range table (decision doc Q9 / contract 20) ── */

test('FURUNO_RANGE_TABLE matches the frozen 17-scale contract', () => {
  const contractNm = [0.125, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 96];
  const contractRing = [0.025, 0.05, 0.1, 0.25, 0.25, 0.25, 0.5, 0.5, 1, 1, 2, 2, 4, 4, 8, 8, 16];
  const contractRings = [5, 5, 5, 3, 4, 6, 4, 6, 4, 6, 4, 6, 4, 6, 4, 6, 6];
  assert.equal(FURUNO_RANGE_TABLE.length, 17);
  FURUNO_RANGE_TABLE.forEach((entry, index) => {
    assert.equal(entry.nm, contractNm[index], `scale #${index}`);
    assert.equal(entry.ringNm, contractRing[index], `ring spacing #${index}`);
    assert.equal(entry.rings, contractRings[index], `ring count #${index}`);
  });
  for (let index = 1; index < FURUNO_RANGE_TABLE.length; index += 1) {
    assert.ok(FURUNO_RANGE_TABLE[index].nm > FURUNO_RANGE_TABLE[index - 1].nm, 'strictly increasing');
  }
  // Ring spacing times ring count equals the full scale.
  for (const entry of FURUNO_RANGE_TABLE) {
    almostEqual(entry.ringNm * entry.rings, entry.nm, 1e-9);
  }
  // Legacy 6-scale set stays a subset (zero break for old configs).
  for (const legacy of [0.75, 1.5, 3, 6, 12, 24]) {
    assert.ok(rangeEntry(legacy), `legacy scale ${legacy} present`);
  }
});

test('rangeEntry resolves table rows and rejects off-table scales', () => {
  assert.equal(rangeEntry(6)?.ringNm, 1);
  assert.equal(rangeEntry(96)?.rings, 6);
  assert.equal(rangeEntry(5), null);
  assert.equal(rangeEntry(Number.NaN), null);
});

test('stepRangeNm walks the table and clamps at both ends', () => {
  assert.equal(stepRangeNm(6, 1), 8);
  assert.equal(stepRangeNm(6, -1), 4);
  assert.equal(stepRangeNm(0.125, -1), 0.125);
  assert.equal(stepRangeNm(96, 1), 96);
  assert.equal(stepRangeNm(99, 1), 6, 'off-table current falls back to the default 6 NM');
});

/* ── cyclic tool steps (Q10) ── */

test('trails step cycles OFF..CONT and wraps', () => {
  assert.deepEqual(TRAIL_STEPS.map(step => step.key), ['OFF', '15s', '30s', '1m', '3m', '6m', 'CONT']);
  assert.equal(stepTrails('OFF').key, '15s');
  assert.equal(stepTrails('15s').seconds, 30);
  assert.equal(stepTrails('6m').key, 'CONT');
  assert.equal(stepTrails('CONT').key, 'OFF');
});

test('vector time cycles 0.5/1/3/6 minutes', () => {
  assert.deepEqual(VECTOR_TIME_MINUTES, [0.5, 1, 3, 6]);
  assert.equal(stepVectorTime(0.5), 1);
  assert.equal(stepVectorTime(6), 0.5);
});

test('presentation modes cycle HU RM -> CU RM -> NU RM -> NU TM', () => {
  assert.deepEqual(PRESENTATION_MODES.map(mode => mode.key), ['HU_RM', 'CU_RM', 'NU_RM', 'NU_TM']);
  assert.equal(stepPresentationMode('HU_RM').label, 'COURSE UP RM');
  assert.equal(stepPresentationMode('NU_RM').trueMotion, true);
  assert.equal(stepPresentationMode('NU_TM').key, 'HU_RM');
});

/* ── relative motion: CPA/TCPA, BCR/BCT, threat ── */

const OS_STATIONARY = { north: 0, east: 0, cogRad: 0, sogMps: 0 };

test('cpaTcpa: head-on closing target has zero CPA at positive TCPA', () => {
  const solution = cpaTcpa(OS_STATIONARY, { north: 1000, east: 0, cogRad: Math.PI, sogMps: 5 });
  almostEqual(solution.rangeM, 1000);
  almostEqual(solution.bearingRad, 0, 1e-9);
  almostEqual(solution.cpaM, 0, 1e-9);
  almostEqual(solution.tcpaS, 200);
  assert.equal(solution.closing, true);
});

test('cpaTcpa: crossing target keeps its beam offset as CPA', () => {
  // Target 1000 N / 1000 E heading south: passes 1000 m abeam after 200 s.
  const solution = cpaTcpa(OS_STATIONARY, { north: 1000, east: 1000, cogRad: Math.PI, sogMps: 5 });
  almostEqual(solution.cpaM, 1000, 1e-9);
  almostEqual(solution.tcpaS, 200);
});

test('cpaTcpa: opening target reports negative TCPA', () => {
  const solution = cpaTcpa(OS_STATIONARY, { north: -1000, east: 0, cogRad: Math.PI, sogMps: 5 });
  assert.ok(solution.tcpaS < 0);
  assert.equal(solution.closing, false);
});

test('cpaTcpa: identical velocities mean no relative motion', () => {
  const own = { north: 0, east: 0, cogRad: 0.3, sogMps: 4 };
  const solution = cpaTcpa(own, { north: 800, east: 300, cogRad: 0.3, sogMps: 4 });
  almostEqual(solution.cpaM, Math.hypot(800, 300));
  almostEqual(solution.tcpaS, 0);
  assert.equal(solution.closing, false);
});

test('bcrBct: target crossing the bow line ahead reports range and time', () => {
  // Own course east, stationary. Target 500 m starboard, 2000 m ahead,
  // moving south across the course line: crosses after 50 s at 2000 m BCR.
  const own = { north: 0, east: 0, cogRad: Math.PI / 2, sogMps: 0 };
  const { bcrM, bctS } = bcrBct(own, { north: 500, east: 2000, cogRad: Math.PI, sogMps: 10 });
  almostEqual(bctS, 50);
  almostEqual(bcrM, 2000, 1e-9);
});

test('bcrBct: parallel and astern crossings report nulls', () => {
  const own = { north: 0, east: 0, cogRad: Math.PI / 2, sogMps: 0 };
  const parallel = bcrBct(own, { north: 500, east: 2000, cogRad: Math.PI / 2, sogMps: 4 });
  assert.equal(parallel.bcrM, null);
  assert.equal(parallel.bctS, null);
  // Crossing point already passed (target receding north of the line).
  const past = bcrBct(own, { north: 500, east: 2000, cogRad: 0, sogMps: 10 });
  assert.equal(past.bcrM, null);
  assert.equal(past.bctS, null);
});

const LIMITS = { cpaLimitM: 1 * N_METERS_PER_NM, tcpaLimitS: 12 * 60 };

test('threatLevel fires only inside both CPA and TCPA limits', () => {
  assert.equal(threatLevel({ cpaM: 0.5 * N_METERS_PER_NM, tcpaS: 300 }, LIMITS), 'dangerous');
  assert.equal(threatLevel({ cpaM: 0, tcpaS: 0 }, LIMITS), 'dangerous');
  assert.equal(threatLevel({ cpaM: 0.5 * N_METERS_PER_NM, tcpaS: 12 * 60 + 1 }, LIMITS), 'safe', 'TCPA above limit');
  assert.equal(threatLevel({ cpaM: 0.5 * N_METERS_PER_NM, tcpaS: -30 }, LIMITS), 'safe', 'TCPA negative (opening)');
  assert.equal(threatLevel({ cpaM: 1.1 * N_METERS_PER_NM, tcpaS: 300 }, LIMITS), 'safe', 'CPA above limit');
});

test('targetSymbolState precedence: lost > dangerous > selected > tracked', () => {
  assert.deepEqual(targetSymbolState({ lost: true }), { kind: 'lost', flashing: true, color: 'alarm' });
  assert.equal(targetSymbolState({ lost: true, acknowledged: true }).flashing, false, 'acked lost stops flashing');
  assert.equal(targetSymbolState({ threat: 'dangerous' }).kind, 'dangerous');
  assert.equal(targetSymbolState({ threat: 'dangerous', selected: true }).kind, 'dangerous');
  assert.equal(targetSymbolState({ threat: 'dangerous', acknowledged: true }).flashing, false, 'acked danger stays red, stops flashing');
  assert.equal(targetSymbolState({ selected: true }).color, 'selection');
  assert.deepEqual(targetSymbolState({}), { kind: 'tracked', flashing: false, color: 'target' });
});

/* ── palettes (Q14) ── */

test('three palettes define the identical canonical token set', () => {
  assert.deepEqual([...PALETTE_NAMES].sort(), ['dusk-blu', 'day-gry', 'night-gry'].sort());
  for (const name of PALETTE_NAMES) {
    const palette = PALETTES[name];
    assert.deepEqual(Object.keys(palette).sort(), [...PALETTE_TOKENS].sort(), `${name} token parity`);
    for (const token of PALETTE_TOKENS) {
      assert.match(palette[token], /^#[0-9a-f]{6}$/, `${name}.${token} is a hex color`);
    }
  }
  assert.equal(DEFAULT_PALETTE, 'night-gry');
});

test('paletteVars falls back to NIGHT-GRY for unknown names', () => {
  assert.equal(paletteVars('solar-flare'), PALETTES['night-gry']);
  assert.equal(paletteVars('dusk-blu'), PALETTES['dusk-blu']);
});

test('every palette token is mirrored as a --rs-* custom property for all three palettes in CSS', async () => {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const css = readFileSync(path.join(root, 'web_gui/radar-screen.css'), 'utf8');
  const kebab = token => token.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`);
  for (const name of PALETTE_NAMES) {
    assert.ok(css.includes(`data-palette="${name}"`), `palette block ${name}`);
  }
  for (const token of PALETTE_TOKENS) {
    const occurrences = css.split(`--rs-${kebab(token)}:`).length - 1;
    assert.equal(occurrences, PALETTE_NAMES.length, `--rs-${kebab(token)} defined once per palette`);
  }
});

/* ── clutter suppression (Q5 local re-render) ── */

test('clutterSuppressionFactor decreases with SEA/RAIN and keeps a floor', () => {
  almostEqual(clutterSuppressionFactor(500, 0, 0), 1);
  const sea = clutterSuppressionFactor(500, 50, 0);
  assert.ok(sea < 1 && sea > 0);
  assert.ok(clutterSuppressionFactor(500, 80, 0) < sea, 'more SEA suppresses more');
  assert.ok(clutterSuppressionFactor(5000, 100, 0) > clutterSuppressionFactor(500, 100, 0), 'SEA decays with range');
  assert.ok(clutterSuppressionFactor(500, 0, 100) < 0.6, 'RAIN suppression is range-flat');
  assert.equal(clutterSuppressionFactor(0, 100, 100), 0.05, 'floor at 5%');
});

/* ── descriptor readback (contract 20 operator_controls) ── */

test('syncControlsFromDescriptor reads back all four operator controls', () => {
  const previous = { gainDb: 3, sea: 10, rain: 20, standby: false };
  const readback = syncControlsFromDescriptor({
    operator_controls: { gain_db: -6, sea_suppression: 40, rain_suppression: 0, standby: true },
  }, previous);
  assert.deepEqual(readback, { gainDb: -6, sea: 40, rain: 0, standby: true });
});

test('syncControlsFromDescriptor keeps previous values for missing keys and null shapes', () => {
  const previous = { gainDb: 3, sea: 10, rain: 20, standby: false };
  const partial = syncControlsFromDescriptor({ operator_controls: { gain_db: 1 } }, previous);
  assert.deepEqual(partial, { gainDb: 1, sea: 10, rain: 20, standby: false });
  assert.equal(syncControlsFromDescriptor(null, previous), null);
  assert.equal(syncControlsFromDescriptor({}, previous), null);
  assert.equal(syncControlsFromDescriptor({ operator_controls: 'garbage' }, previous), null);
});

/* ── envelope -> targets + alerts (Q4/Q12) ── */

function envelopeFixture() {
  return {
    sim_time: 120,
    executed_tracker: 'kf',
    os: { x: 1000, y: 2000, north: 1000, east: 2000, psi: 0.1, cog: 0.1, sog: 3, latitude: 34.5, longitude: 135.2 },
    tracks: [{ labels: ['7'], states: [[1500, 2000, -8, 0]] }],
    truth: [
      { id: 0, mmsi: 1 },
      { id: 2, mmsi: 5678, label: 'MUJI', north: 1000, east: 4000, cog: Math.PI / 2, sog: 2, psi: Math.PI / 2, ais: { age_s: 1, state: 'active' } },
      { id: 3, mmsi: 9012, label: 'GHOST', north: 500, east: 2500, cog: 0, sog: 0, psi: 0, ais: { age_s: 400, state: 'lost' } },
    ],
  };
}

test('buildScreenTargets merges TT tracks and AIS truth with client-side CPA/TCPA', () => {
  const targets = buildScreenTargets(envelopeFixture(), { cpaLimitNm: 1, tcpaLimitMin: 12 });
  assert.equal(targets.length, 3);
  const tt = targets.find(target => target.type === 'tt');
  assert.equal(tt.label, 'T7');
  almostEqual(tt.north, 1500);
  almostEqual(tt.east, 2000);
  assert.ok(tt.tcpaS > 0);
  assert.equal(tt.threat, 'dangerous', 'head-on 8 m/s target 500 m ahead intrudes CPA+TCPA');
  const ais = targets.find(target => target.label === 'MUJI');
  assert.equal(ais.threat, 'safe', 'opening crossing target outside limits');
  const lost = targets.find(target => target.label === 'GHOST');
  assert.equal(lost.lost, true);
});

test('buildScreenTargets skips TT in god mode and envelopes without ownship', () => {
  const god = buildScreenTargets({ ...envelopeFixture(), executed_tracker: 'god' }, {});
  assert.equal(god.filter(target => target.type === 'tt').length, 0);
  assert.equal(god.filter(target => target.type === 'ais').length, 2);
  assert.deepEqual(buildScreenTargets(null, {}), []);
  assert.deepEqual(buildScreenTargets({ truth: [] }, {}), []);
});

test('activeAlerts lists CPA/TCPA intrusions and lost AIS targets', () => {
  const targets = buildScreenTargets(envelopeFixture(), { cpaLimitNm: 1, tcpaLimitMin: 12 });
  const alerts = activeAlerts(targets);
  assert.equal(alerts.length, 2);
  const cpa = alerts.find(alert => alert.kind === 'CPA/TCPA');
  assert.equal(cpa.level, 'alarm');
  assert.match(cpa.label, /TT T7 TAKE EVASIVE ACTION/);
  const lost = alerts.find(alert => alert.kind === 'TARGET LOST');
  assert.equal(lost.level, 'warning');
  assert.match(lost.label, /AIS GHOST LOST/);
});

/* ── readout formatting (digest §1 styles) ── */

test('formatBearing renders zero-padded 045.3 style with 000.0 wrap', () => {
  assert.equal(formatBearing(45.34), '045.3');
  assert.equal(formatBearing(0), '000.0');
  assert.equal(formatBearing(359.97), '000.0');
  assert.equal(formatBearing(-90), '270.0');
});

test('formatEbl appends the relative/true suffix from the display mode', () => {
  assert.equal(formatEbl(45.34, 0, false), '045.3°T');
  assert.equal(formatEbl(90, 44.7, true), '045.3°R');
  assert.equal(relativeBearing(10, 20), 350);
});

test('formatVrm and formatRangeBox follow the digest readout styles', () => {
  assert.equal(formatVrm(28.113), '28.11NM');
  assert.equal(formatRangeBox(6), '6 NM 1NM');
  assert.equal(formatRangeBox(0.125), '0.125 NM 0.025NM');
  assert.equal(formatRangeBox(0.5), '0.5 NM 0.1NM');
  assert.equal(formatRangeBox(24), '24 NM 4NM');
});

test('formatLatLon renders Furuno POSN style and star fields for invalid data', () => {
  assert.equal(formatLatLon(34.6869, 135.312), '34°41.2\'N 135°18.7\'E');
  assert.equal(formatLatLon(-0.5, 12), '0°30.0\'S 12°00.0\'E');
  assert.equal(formatLatLon(Number.NaN, 12), '***°**.*\'*');
});

test('formatUtcStamp renders DD.MM.YYYY HH:MM:SS in UTC', () => {
  assert.equal(formatUtcStamp('2026-10-22T08:09:10Z'), '22.10.2026  08:09:10');
  assert.equal(formatUtcStamp(null, new Date(Date.UTC(2026, 0, 2, 3, 4, 5))), '02.01.2026  03:04:05');
  assert.equal(formatUtcStamp('not-a-date'), null);
});

/* ── static page skeleton checks ── */

test('radar.html carries the three-zone skeleton ids the module wires', async () => {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const html = readFileSync(path.join(root, 'web_gui/radar.html'), 'utf8');
  for (const id of [
    'rsRoot', 'rsPpi', 'rsStbyOverlay', 'rsTx', 'rsTxRing', 'rsTxLabel',
    'rsBtnGain', 'rsBtnSea', 'rsBtnRain', 'rsAdjustPanel', 'rsAdjustSlider',
    'rsBtnTrails', 'rsBtnHl', 'rsBtnReset', 'rsBtnMarks', 'rsBtnBrill',
    'rsModeButton', 'rsModeLabel', 'rsRangeLabel', 'rsRangeUp', 'rsRangeDown',
    'rsCursorText', 'rsEbl1', 'rsEbl2', 'rsVrm1', 'rsVrm2',
    'rsDateTime', 'rsOsHdg', 'rsOsCog', 'rsOsSog', 'rsOsPosn',
    'rsTargetBox', 'rsCpaValue', 'rsTcpaValue', 'rsVecTime', 'rsVecMode',
    'rsAlertList', 'rsAlertCount', 'rsGuidance',
  ]) {
    assert.ok(html.includes(`id="${id}"`), `#${id}`);
  }
  assert.match(html, /modules\/radar-screen\.js\?v=/);
  assert.match(html, /aria-label="InstantAccess 工具条"/);
  assert.ok(html.includes('RADAR STBY'));
});
