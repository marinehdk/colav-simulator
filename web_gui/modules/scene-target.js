import { NM, riskForTarget, targetAlert } from './scene-geography.js?v=20260923-follow-v1';
import {
  AIS_STATE_LABELS,
  aisSymbolState,
  associationLabel,
  localRadarMeasurementPoints,
  matchAisAssociations,
  trackExistenceForTarget,
} from './ais-display.js';

const metric = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : '—';
const degrees = value => Number.isFinite(value) ? (value * 180 / Math.PI + 360) % 360 : null;
const ROLES = { GIVE_WAY: '让路船', STAND_ON: '直航船', OVERTAKING: '追越船', OVERTAKEN: '被追越船' };

/* P3-S4 (spec #90): AIS rows for the 3D target card. Age/state are backend
   authoritative; the dangerous composition and the association label are
   display-side (see ais-display.js). */
function aisCardRows(projection, ship, encInfo) {
  if (ship?.ais == null) return [];
  const rank = { alarm: 3, caution: 2, checked: 1 }[targetAlert(projection, ship).state] || 0;
  const state = aisSymbolState(ship.ais, rank);
  const associations = matchAisAssociations(
    [ship],
    projection?.raw?.tracks?.[0],
    localRadarMeasurementPoints(projection?.raw?.measurements?.[0], encInfo),
  );
  const association = associations.get(String(ship.id)) || null;
  return [
    { label: 'MMSI', value: ship.mmsi != null ? String(ship.mmsi) : '—', unit: '' },
    { label: 'AIS AGE', value: metric(Number(ship.ais.age_s), 0), unit: 'S' },
    { label: 'AIS STATE', value: AIS_STATE_LABELS[state] || String(ship.ais.state || '—'), unit: '' },
    { label: 'AIS ASSOC', value: associationLabel(association), unit: '' },
  ];
}

export function targetPresentation(projection, ship, encInfo = null) {
  const risk = riskForTarget(projection, ship), alert = targetAlert(projection, ship);
  const os = projection?.raw?.os;
  const located = [os?.x, os?.y, ship.x, ship.y].every(Number.isFinite);
  const range = located ? Math.hypot(ship.x - os.x, ship.y - os.y) : null;
  const bearing = located && range > 0 ? degrees(Math.atan2(ship.y - os.y, ship.x - os.x)) : null;
  const role = risk?.role || risk?.lifecycleRole;
  let relation = null;
  if (alert.state !== 'unchecked') {
    if (risk?.encounter === 'HEAD_ON') relation = { icon: 'obi-collision-avoidance-head-on', label: '对遇' };
    if (risk?.encounter === 'OVERTAKING') relation = { icon: 'obi-collision-avoidance-overtaking', label: role === 'OVERTAKEN' ? '被追越' : '追越' };
    if (risk?.encounter === 'CROSSING' && ['GIVE_WAY', 'STAND_ON'].includes(role)) relation = {
      icon: role === 'GIVE_WAY' ? 'obi-collision-avoidance-starboard-side' : 'obi-collision-avoidance-port-side', label: '交叉相遇',
    };
  }
  const assessed = alert.state !== 'unchecked';
  const dcpa = assessed && Number.isFinite(risk?.dcpaM) ? risk.dcpaM / NM : null;
  const tcpa = assessed && Number.isFinite(risk?.tcpaS) ? risk.tcpaS / 60 : null;
  const blocks = [
    { label: 'BRG', value: metric(bearing, 0), unit: 'DEG' },
    { label: 'RNG', value: metric(range === null ? null : range / NM, 2), unit: 'NM' },
    { label: 'DCPA', value: metric(dcpa, 2), unit: 'NM' },
  ];
  const aisRows = aisCardRows(projection, ship, encInfo);
  // P3-S5: obstacles always carry the CONF row (— when no track sits on the
  // target); the ownship has no tracker track and omits the row entirely.
  const confRow = ship?.ais == null
    ? []
    : [{ label: 'CONF', value: metric(trackExistenceForTarget(ship, projection?.raw?.tracks?.[0]), 3), unit: '' }];
  return { alert, relation, role: ROLES[role] || '职责未知', blocks,
    metrics: [...aisRows, ...confRow, ...blocks, { label: 'TCPA', value: metric(tcpa), unit: 'MIN' },
      { label: projection?.raw?.executed_tracker === 'god' ? 'HDG' : 'COG', value: metric(degrees(ship.psi), 0), unit: 'DEG' },
      { label: 'SOG', value: metric(Number.isFinite(ship.sog) ? ship.sog * 3600 / NM : null), unit: 'KN' }],
    note: assessed ? (risk?.lifecycleCommitment || risk?.commitment || '') : '当前无有效 COLAV 评估；CPA / TCPA 不可用',
  };
}

export function applyTargetAppearance(element, alert) {
  element.dataset.risk = alert.state;
  element.style.setProperty('--scene-target-color', alert.color);
  element.style.setProperty('--overlay-border-outline-color', alert.color);
  element.style.setProperty('--element-active-color', alert.color);
  for (const severity of ['caution', 'warning', 'alarm']) {
    element.style.setProperty(`--alert-${severity}-color`, alert.color);
    element.style.setProperty(`--alert-${severity}-outline-color`, alert.color);
  }
}

export function updateTargetPoi(poi, model) {
  const signature = JSON.stringify(model);
  if (poi.dataset.presentation === signature) return false;
  poi.dataset.presentation = signature;
  applyTargetAppearance(poi, model.alert);
  poi.state = model.alert.poiState;
  poi.vesselState = model.alert.state === 'unchecked' ? 'unchecked' : 'checked';
  poi.hasRelation = Boolean(model.relation);
  poi.data = model.blocks;
  const previous = poi.querySelector('[slot="relation"]');
  if (previous?.tagName.toLowerCase() !== model.relation?.icon) {
    previous?.remove();
    if (model.relation) {
      const icon = document.createElement(model.relation.icon); icon.slot = 'relation';
      icon.setAttribute('aria-label', `${model.relation.label} · ${model.role}`); icon.title = `${model.relation.label} · ${model.role}`;
      poi.append(icon);
    }
  } else if (previous) previous.setAttribute('aria-label', `${model.relation.label} · ${model.role}`);
  return true;
}

export function renderTargetCard(body, model) {
  const signature = JSON.stringify(model);
  if (body.dataset.presentation === signature) return;
  body.dataset.presentation = signature;
  const status = document.createElement('div'); status.className = 'scene3d-target-status';
  const badge = document.createElement('strong'); badge.textContent = model.alert.name;
  status.append(badge);
  if (model.relation) {
    const icon = document.createElement(model.relation.icon); icon.setAttribute('aria-label', model.relation.label); status.append(icon);
  }
  const role = document.createElement('span'); role.textContent = `${model.relation?.label || '会遇信息不可用'} · ${model.role}`; status.append(role);
  const grid = document.createElement('dl'); grid.className = 'scene3d-target-metrics';
  for (const item of model.metrics) {
    const cell = document.createElement('div'), label = document.createElement('dt'), value = document.createElement('dd'), unit = document.createElement('small');
    label.textContent = item.label; value.append(document.createTextNode(item.value)); unit.textContent = item.unit; value.append(unit); cell.append(label, value); grid.append(cell);
  }
  const note = document.createElement('p'); note.className = 'scene3d-target-note'; note.textContent = model.note;
  body.replaceChildren(status, grid, note);
}
