import { targetsForDisplay, RADAR_DETECTION_RANGE_M } from './situation-display.js?v=20260920-3d-v1';
import { targetAlert, targetKey } from './scene-geography.js?v=20260923-follow-v1';

const DEG = 180 / Math.PI;
const normalize = value => ((value % 360) + 360) % 360;
const relative = value => normalize(value + 180) - 180;
const DIRECTIONS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];


export function buildSceneCompass(projection) {
  const data = projection?.raw, os = data?.os;
  if (![os?.x, os?.y, os?.psi].every(Number.isFinite)) return null;
  const heading = normalize(os.psi * DEG), rounded = Math.round(heading) % 360;
  const targets = targetsForDisplay(data).flatMap(ship => {
    if (String(ship.id) === '0' || ship.active === false || ![ship.x, ship.y].every(Number.isFinite)) return [];
    const dn = ship.x - os.x, de = ship.y - os.y, rangeM = Math.hypot(dn, de);
    if (rangeM > RADAR_DETECTION_RANGE_M || rangeM === 0) return [];
    const bearing = relative(Math.atan2(de, dn) * DEG - heading);
    const alert = targetAlert(projection, ship);
    return [{ id: ship.id, key: targetKey(data.run_id, ship), bearing, rangeM,
      x: (bearing + 180) / 360,
      heading: Number.isFinite(ship.psi) ? relative(ship.psi * DEG - heading) : null,
      ...alert }];
  });
  return { heading, label: `${DIRECTIONS[Math.round(heading / 45) % 8]} ${String(rounded).padStart(3, '0')}°`, targets };
}

function arrow(solid = false) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 28'); svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(svg.namespaceURI, 'path');
  path.setAttribute('d', 'M12 3 L20 24 L12 19 L4 24 Z');
  path.setAttribute('fill', solid ? 'currentColor' : 'none');
  path.setAttribute('stroke', 'currentColor'); path.setAttribute('stroke-width', '2');
  path.setAttribute('stroke-linejoin', 'round'); svg.append(path); return svg;
}

export function createSceneCompass({ host, onSelect }) {
  const root = document.createElement('section'); root.className = 'scene3d-compass'; root.hidden = true;
  root.setAttribute('aria-label', '航向罗盘与 2 km 内目标');
  const heading = document.createElement('strong'); heading.className = 'scene3d-compass-heading';
  const range = document.createElement('span'); range.className = 'scene3d-compass-range'; range.textContent = '360° · 2 km';
  const axis = document.createElement('div'); axis.className = 'scene3d-compass-axis'; axis.setAttribute('aria-hidden', 'true');
  const ticks = Array.from({ length: 73 }, () => { const tick = document.createElement('span'); axis.append(tick); return tick; });
  const own = document.createElement('div'); own.className = 'scene3d-compass-own'; own.title = '本船航向'; own.append(arrow(true));
  const targets = document.createElement('div'); targets.className = 'scene3d-compass-targets';
  root.append(heading, range, axis, own, targets); host.append(root);
  const records = new Map();
  return {
    render(projection, camera, shipsVisible = true) {
      const model = buildSceneCompass(projection);
      root.hidden = camera === 'top' || !model;
      if (!model) { records.forEach(r => r.button.remove()); records.clear(); return; }
      heading.textContent = model.label;
      const start = Math.ceil((model.heading - 180) / 5) * 5;
      ticks.forEach((tick, index) => {
        const degree = start + index * 5, delta = degree - model.heading, value = normalize(degree);
        tick.hidden = delta > 180;
        tick.style.left = `${(delta + 180) / 360 * 100}%`;
        tick.className = value % 30 === 0 ? 'major' : 'minor';
        tick.textContent = value % 30 === 0 && Math.abs(delta) > 12
          ? (value % 90 === 0 ? DIRECTIONS[value / 45] : String(value).padStart(3, '0')) : '';
      });
      const wanted = new Set(), lanes = [], width = Math.max(1, root.clientWidth - 48);
      for (const target of shipsVisible ? model.targets : []) {
        wanted.add(target.key);
        let record = records.get(target.key);
        if (!record) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'scene3d-compass-target';
          const icon = arrow(), label = document.createElement('span'); label.textContent = `TS${target.id}`;
          button.append(icon, label); button.addEventListener('click', () => onSelect(target.id));
          targets.append(button); record = { button, icon }; records.set(target.key, record);
        }
        const { button, icon } = record;
        let lane = lanes.findIndex(xs => xs.every(x => Math.abs(x - target.x * width) >= 46));
        if (lane < 0) { lane = lanes.length; lanes.push([]); }
        lanes[lane].push(target.x * width);
        button.style.left = `calc(${20 - target.x * 40}px + ${target.x * 100}%)`; button.style.top = `${lane * 45}px`;
        button.style.color = target.color; button.dataset.risk = target.state;
        icon.style.transform = `rotate(${target.heading ?? 0}deg)`;
        icon.style.visibility = target.heading === null ? 'hidden' : 'visible';
        const description = `TS${target.id} · ${target.name} · 距离 ${target.rangeM.toFixed(0)} m · 相对方位 ${target.bearing.toFixed(0)}° · ${target.heading === null ? '航向未知' : `相对航向 ${target.heading.toFixed(0)}°`}`;
        button.title = description; button.setAttribute('aria-label', description);
      }
      for (const [key, record] of records) if (!wanted.has(key)) { record.button.remove(); records.delete(key); }
      targets.style.height = `${Math.max(1, lanes.length) * 45}px`;
    },
    destroy() { records.clear(); root.remove(); },
  };
}
