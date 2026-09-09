/** BALANCE instruments consume backend facts; no client-side physical model. */
const KNOTS_PER_MPS = 3600 / 1852;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const number = (value, digits = 1) => finite(value) ? value.toFixed(digits) : '—';
const names = {
  main_thruster_port: 'Port', main_thruster_center: 'Centre', main_thruster_starboard: 'Starboard',
  rudder_port: 'Port', rudder_starboard: 'Starboard',
  bow_tunnel_thruster_forward: 'Forward', bow_tunnel_thruster_aft: 'Aft',
};
const environmentRows = [
  { id: 'wind', label: 'WIND', key: 'wind_speed_mps', unit: 'kn', scale: KNOTS_PER_MPS },
  { id: 'wave', label: 'WAVES', key: 'wave_hs_m', unit: 'm', scale: 1 },
  { id: 'current', label: 'CURRENT', key: 'current_speed_mps', unit: 'kn', scale: KNOTS_PER_MPS },
];
let sessionKey = null;
let rollPeak = null;
let layoutKey = null;
let pending = null;
let awaitingComponents = false;
let lastRenderKey = null;

export function thrustPercent(actual, minForce, maxForce) {
  if (!finite(actual)) return null;
  const capacity = actual < 0 ? Math.abs(minForce) : maxForce;
  return finite(capacity) && capacity > 0 ? actual / capacity * 100 : null;
}

export function environmentDirectionTo(id, environment) {
  const key = { wind: 'wind_from_deg', wave: 'wave_to_deg', current: 'current_to_deg' }[id];
  const direction = environment?.[key];
  if (!finite(direction)) return null;
  return ((direction + (id === 'wind' ? 180 : 0)) % 360 + 360) % 360;
}

function renderEnvironmentDial(row, environment, ownship) {
  const dial = document.getElementById(`balance-${row.id}-dial`);
  const direction = environmentDirectionTo(row.id, environment);
  const magnitude = environment?.[row.key];
  const available = finite(direction) && finite(magnitude) && magnitude > 0;
  dial.hidden = !available;
  const empty = document.getElementById(`balance-${row.id}-unavailable`);
  empty.hidden = available;
  empty.textContent = environment?.status === 'OFF' ? 'Off' : magnitude === 0 ? 'Calm' : 'Unavailable';
  if (!available) return;
  // Same native Watch configuration used by obc-wind, without a history histogram.
  Object.assign(dial, {
    watchCircleType: 'double', northArrow: true, crosshairEnabled: true, tickmarksInside: true,
    vessels: finite(ownship?.psi) ? [{ size: 'small', vesselImage: 'generic-top', transform: `rotate(${ownship.psi * 180 / Math.PI}deg)` }] : [],
    wind: null, windFromDirectionDeg: null,
    needles: [{ angle: direction, fillColor: 'var(--instrument-enhanced-secondary-color)', strokeColor: 'var(--instrument-enhanced-secondary-color)' }],
  });
  dial.setAttribute('aria-label', `${row.label} to ${number(direction, 0)} degrees true, north up`);
}

export function resetBalance() {
  sessionKey = null;
  rollPeak = null;
  layoutKey = null;
  lastRenderKey = null;
  renderBalance({});
}

function readout(id, value, unit, decimals = 1, showUnit = false) {
  const element = document.getElementById(id);
  if (!element) return;
  // The pinned OpenBridge value readout rounds to integers; state text preserves SI precision.
  element.readouts = [{ type: 'state-on', value: `${number(value, decimals)}${showUnit ? unit : ''}`, hasIcon: false }];
  element.setAttribute('aria-label', `${number(value, decimals)} ${unit}`);
}

function text(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function buildEnvironment() {
  for (const row of environmentRows) {
    const host = document.getElementById(`balance-${row.id}-readings`);
    if (host.children.length) continue;
    const section = document.createElement('div');
    section.className = 'balance-environment-row';
    section.innerHTML = `<div class="balance-env-reading"><small>● Actual</small><div class="balance-env-number"><obc-automation-button-readout-stack id="balance-${row.id}" size="enhanced"></obc-automation-button-readout-stack><small>${row.unit}</small></div><div class="balance-env-detail" id="balance-${row.id}-detail">To -</div></div>
      <div class="balance-env-forecast"><small>○ Forecast</small><div class="balance-env-number"><span>-</span><small>${row.unit}</small></div><div class="balance-env-detail">To -</div></div>`;
    host.append(section);
  }
}

export function groupedConstraints(balance) {
  const limits = new Map((balance?.constraints || []).map(row => [row.label, row]));
  const rows = [];
  const take = label => {
    const row = limits.get(label);
    limits.delete(label);
    return row;
  };
  const value = row => `${number(row.value)} ${row.unit}`;
  const range = (low, high, unit) => finite(low) && finite(high) && low === -high
    ? `±${number(high)} ${unit}` : `${number(low)} … ${number(high)} ${unit}`;
  const add = (group, label, display, sources = []) => rows.push({
    group, label, display, source: sources.filter(Boolean).map(row => row.source).join('; '),
  });
  const rot = take('Heading reference ROT');
  if (rot) add('NAVIGATION', 'Reference ROT', value(rot), [rot]);
  const angle = take('Max rudder angle');
  const rudderRate = take('Max rudder rate');
  if (angle || rudderRate) add('NAVIGATION', 'Rudder',
    [angle && `±${value(angle)}`, rudderRate && `${value(rudderRate)} max`].filter(Boolean).join(' · '), [angle, rudderRate]);
  for (const axis of ['Surge', 'Sway', 'Yaw']) {
    const low = take(`PID ${axis} min`);
    const high = take(`PID ${axis} max`);
    if (low || high) add('CONTROL LOADS', axis, range(low?.value, high?.value, (low || high).unit), [low, high]);
  }
  for (const [kind, name, rateName] of [['main', 'Main', 'Main thrust rate'], ['tunnel_thruster', 'Bow', 'Bow thrust rate']]) {
    const rate = take(rateName);
    const groups = new Map();
    for (const item of balance?.propulsion || []) {
      if (item.kind !== kind) continue;
      // Merge only identical bounds, preserving per-device differences.
      const key = `${item.min_force_n}:${item.max_force_n}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    for (const items of groups.values()) {
      const first = items[0];
      const label = groups.size === 1 ? `${items.length} × ${name}` : `${name} ${items.map(item => names[item.id] || item.id).join('/')}`;
      add('THRUST LIMITS', label,
        `${range(first.min_force_n / 1000, first.max_force_n / 1000, 'kN')} each${rate ? ` · ${value(rate)}` : ''}`, [rate]);
    }
    if (!groups.size && rate) add('THRUST LIMITS', rateName, value(rate), [rate]);
  }
  const bowRules = [
    ['Bow derating starts', 'Derate ≥'], ['Bow lockout', 'Lock ≥'], ['Bow unlock below', 'Unlock <'],
  ].map(([key, label]) => ({ row: take(key), label })).filter(item => item.row);
  if (bowRules.length) {
    const sameUnit = bowRules.every(item => item.row.unit === bowRules[0].row.unit);
    const display = bowRules.map(({ row, label }) => `${label}${number(row.value)}${sameUnit ? '' : ` ${row.unit}`}`).join(' · ');
    add('BOW SPEED RULES', 'STW', `${display}${sameUnit ? ` ${bowRules[0].row.unit.replace(' STW', '')}` : ''}`, bowRules.map(item => item.row));
  }
  for (const row of limits.values()) add('OTHER', row.label, value(row), [row]);
  return rows;
}

function buildPropulsion(balance) {
  const host = document.getElementById('balancePropulsionRows');
  host.replaceChildren();
  for (const [kind, title] of [['main', 'MAIN THRUSTERS'], ['rudder', 'RUDDERS'], ['tunnel_thruster', 'BOW THRUSTERS']]) {
    const items = (balance?.propulsion || []).filter(item => item.kind === kind);
    if (!items.length) continue;
    const section = document.createElement('section');
    section.className = 'balance-propulsion-group';
    const heading = document.createElement('h4');
    heading.textContent = title;
    section.append(heading);
    const grid = document.createElement('div');
    grid.className = 'balance-propulsion-grid';
    for (const item of items) {
      const cell = document.createElement('div');
      cell.className = 'balance-propulsion-cell';
      cell.dataset.actuatorId = item.id;
      const label = document.createElement('strong');
      label.textContent = names[item.id] || item.id;
      const instrument = document.createElement(kind === 'rudder' ? 'obc-rudder' : 'obc-thruster');
      instrument.className = 'balance-actuator-instrument';
      instrument.setAttribute('aria-label', `${title} ${label.textContent}`);
      if (kind === 'rudder') {
        instrument.maxAngle = item.max_angle_deg ?? 90;
      } else {
        instrument.tunnel = kind === 'tunnel_thruster';
        instrument.topPropeller = 'single';
      }
      const value = document.createElement('span');
      value.className = 'balance-actuator-value';
      const status = document.createElement('small');
      status.className = 'balance-actuator-status';
      cell.append(label, instrument, value, status);
      grid.append(cell);
    }
    section.append(grid);
    host.append(section);
  }
  if (!host.children.length) {
    const empty = document.createElement('p');
    empty.className = 'balance-note';
    empty.textContent = balance?.propulsion_status === 'IDEAL' ? 'Ideal generalized forces · no physical actuators' : 'Physical actuator data unavailable';
    host.append(empty);
  }
  const constraints = document.getElementById('balanceConstraints');
  constraints.replaceChildren();
  const rows = groupedConstraints(balance);
  let group = null;
  for (const row of rows) {
    if (row.group !== group) {
      const heading = document.createElement('h4');
      heading.textContent = row.group;
      constraints.append(heading);
      group = row.group;
    }
    const line = document.createElement('div');
    line.className = 'balance-limit';
    line.title = row.source;
    const label = document.createElement('span');
    label.textContent = row.label;
    const value = document.createElement('strong');
    value.textContent = row.display;
    line.append(label, value);
    constraints.append(line);
  }
  if (!rows.length) constraints.textContent = 'GNC limits unavailable';
}

export function renderBalance(envelope) {
  if (!document.getElementById('ownshipBalancePage')) return;
  if (!customElements.get('obc-roll')) {
    pending = envelope;
    if (!awaitingComponents) {
      awaitingComponents = true;
      customElements.whenDefined('obc-roll').then(() => {
        awaitingComponents = false;
        renderBalance(pending || {});
      });
    }
    return;
  }
  const balance = envelope.gnc_balance;
  const key = `${envelope.session_id ?? envelope.run_id ?? ''}:${balance?.config_hash ?? ''}`;
  const renderKey = `${key}:${balance?.tick ?? 'none'}:${envelope.state ?? ''}`;
  // Buffered map animation repeats an authoritative physics tick; keep instrument
  // updates at telemetry cadence instead of rebuilding Lit readouts every frame.
  if (renderKey === lastRenderKey) return;
  lastRenderKey = renderKey;
  if (key !== sessionKey) {
    sessionKey = key;
    rollPeak = null;
    layoutKey = null;
  }
  if (finite(balance?.roll_deg)) rollPeak = Math.max(rollPeak ?? 0, Math.abs(balance.roll_deg));
  const roll = document.getElementById('balanceRoll');
  roll.hidden = !finite(balance?.roll_deg);
  document.getElementById('balanceRollUnavailable').hidden = !roll.hidden;
  if (!roll.hidden) roll.roll = balance.roll_deg;
  readout('balanceRollValue', balance?.roll_deg, '°', 1, true);
  readout('balanceRollPeak', rollPeak, '°', 1, true);
  buildEnvironment();
  const env = balance?.environment;
  for (const row of environmentRows) {
    const value = finite(env?.[row.key]) ? env[row.key] * row.scale : null;
    readout(`balance-${row.id}`, value, row.unit);
    renderEnvironmentDial(row, env, envelope.os);
  }
  text('balance-wind-detail', finite(env?.wind_speed_mps) && env.wind_speed_mps > 0 ? `To ${number(environmentDirectionTo('wind', env), 0)}°` : 'To -');
  text('balance-wave-detail', finite(env?.wave_hs_m) && env.wave_hs_m > 0 ? `To ${number(environmentDirectionTo('wave', env), 0)}°` : 'To -');
  text('balance-current-detail', finite(env?.current_speed_mps) && env.current_speed_mps > 0 ? `To ${number(environmentDirectionTo('current', env), 0)}°` : 'To -');
  if (layoutKey !== key) {
    buildPropulsion(balance);
    layoutKey = key;
  }
  for (const item of balance?.propulsion || []) {
    const cell = [...document.querySelectorAll('[data-actuator-id]')].find(element => element.dataset.actuatorId === item.id);
    if (!cell) continue;
    const instrument = cell.querySelector('.balance-actuator-instrument');
    const rudder = item.kind === 'rudder';
    const actual = rudder ? item.angle_deg : finite(item.actual_n) ? item.actual_n / 1000 : null;
    const command = rudder ? item.command_angle_deg : finite(item.command_n) ? item.command_n / 1000 : null;
    instrument.hidden = !finite(actual);
    if (finite(actual)) {
      if (rudder) Object.assign(instrument, { angle: actual, setpoint: command ?? undefined });
      else Object.assign(instrument, {
        thrust: thrustPercent(item.actual_n, item.min_force_n, item.max_force_n),
        setpoint: thrustPercent(item.command_n, item.min_force_n, item.max_force_n) ?? undefined,
      });
    }
    cell.querySelector('.balance-actuator-value').textContent = `${number(actual)} / ${number(command)}`;
    const status = !finite(actual) ? 'Waiting'
      : item.health === 0 ? 'Unavailable'
        : item.kind === 'tunnel_thruster' && balance.bow_authority === 0 ? 'Speed lockout'
          : item.health < 1 ? `Health ${number(item.health * 100, 0)}%`
            : item.rate_limited ? 'Rate limited' : 'Delivered';
    cell.querySelector('.balance-actuator-status').textContent = `${status} ${rudder ? '°' : 'kN'}`;
  }

}

if (typeof document !== 'undefined') renderBalance({});
