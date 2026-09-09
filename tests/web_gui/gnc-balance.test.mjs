import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { thrustPercent, groupedConstraints, environmentDirectionTo } from '../../web_gui/modules/gnc-balance.js';

test('signed thrust uses its own ahead/astern capacity and keeps missing data unavailable', () => {
  assert.equal(thrustPercent(-5000, -10000, 20000), -50);
  assert.equal(thrustPercent(5000, -10000, 20000), 25);
  assert.equal(thrustPercent(0, -10000, 20000), 0);
  assert.equal(thrustPercent(null, -10000, 20000), null);
  assert.equal(thrustPercent(5000, -10000, 0), null);
});

test('SENSOR retains four instruments; BALANCE precedes AIS and uses native OpenBridge instruments', async () => {
  const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
  const sensor = html.slice(html.indexOf('id="ownshipSensorPage"'), html.indexOf('<!-- Page 2: BALANCE -->'));
  assert.equal((sensor.match(/class="config-obc-card sensor-card"/g) || []).length, 4);
  assert.doesNotMatch(sensor, /pitch|roll/i);
  assert.match(html, /ownshipBalancePage" data-ownship-card-page="2"/);
  assert.match(html, /ownship-ais-page" data-ownship-card-page="4"/);
  const entry = await readFile(new URL('../../web_gui/vendor/openbridge/entry-source.mjs', import.meta.url), 'utf8');
  for (const component of ['roll', 'rudder', 'thruster', 'graph-mini']) {
    assert.ok(entry.includes(`/navigation-instruments/${component}/${component}.js`));
  }
});


test('constraint aggregation preserves asymmetric PID and distinct actuator limits', () => {
  const rows = groupedConstraints({
    constraints: [
      { label: 'PID Surge min', value: -100, unit: 'kN', source: 'min' },
      { label: 'PID Surge max', value: 200, unit: 'kN', source: 'max' },
      { label: 'Extra bound', value: 7, unit: 'm', source: 'extra' },
    ],
    propulsion: [
      { id: 'main_thruster_port', kind: 'main', min_force_n: -10000, max_force_n: 10000 },
      { id: 'main_thruster_center', kind: 'main', min_force_n: -10000, max_force_n: 10000 },
      { id: 'main_thruster_starboard', kind: 'main', min_force_n: -10000, max_force_n: 20000 },
    ],
  });
  assert.equal(rows.find(row => row.label === 'Surge').display, '-100.0 … 200.0 kN');
  const thrusts = rows.filter(row => row.group === 'THRUST LIMITS');
  assert.equal(thrusts.length, 2);
  assert.match(thrusts[0].label, /Port\/Centre/);
  assert.equal(thrusts[1].display, '-10.0 … 20.0 kN each');
  assert.ok(rows.some(row => row.label === 'Extra bound' && row.display === '7.0 m'));
});


test('five-page layout keeps environmental cards separate from propulsion', async () => {
  const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
  const balance = html.slice(html.indexOf('id="ownshipBalancePage"'), html.indexOf('<!-- Page 3: PROPULSION -->'));
  assert.equal((balance.match(/<section /g) || []).length, 4);
  for (const id of ['wind', 'wave', 'current']) assert.ok(balance.includes(`id="balance-${id}-dial"`));
  assert.ok(!balance.includes('balancePropulsionRows'));
  const propulsion = html.slice(html.indexOf('id="ownshipPropulsionPage"'), html.indexOf('<!-- Page 4: AIS -->'));
  assert.ok(propulsion.includes('balancePropulsionRows'));
  assert.ok(propulsion.includes('balanceConstraints'));
  assert.equal((html.match(/class="ownship-card-dot"/g) || []).length, 5);
});

test('environment dials use To bearings consistently, converting wind From by 180 degrees', () => {
  assert.equal(environmentDirectionTo('wind', { wind_from_deg: 198 }), 18);
  assert.equal(environmentDirectionTo('wave', { wave_to_deg: 0 }), 0);
  assert.equal(environmentDirectionTo('current', { current_to_deg: 333 }), 333);
  assert.equal(environmentDirectionTo('wind', { wind_from_deg: 180 }), 0);
  assert.equal(environmentDirectionTo('wind', {}), null);
});
