/** Recorded Replay sidebars. Reuse Deployment's card DOM and CSS, but bind only
 * sealed frame facts and the separate event journal at the current playhead. */
import { buildRadarModel, createRadarMiniMap } from './radar-mini-map.js';
import { RADAR_DETECTION_RANGE_M } from './situation-display.js';

const NM = 1852;
const degrees = value => Number.isFinite(value) ? ((value * 180 / Math.PI) % 360 + 360) % 360 : null;
const fixed = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : '---';
const coordinate = (value, positive, negative) => Number.isFinite(value)
  ? `${Math.abs(value).toFixed(4)}° ${value >= 0 ? positive : negative}` : null;
const duration = value => Number.isFinite(value) && value >= 0
  ? `${String(Math.floor(value / 3600)).padStart(2, '0')}:${String(Math.floor(value % 3600 / 60)).padStart(2, '0')}:${String(Math.floor(value % 60)).padStart(2, '0')}`
  : '--:--:--';

function cloneSidebar(documentRef, id) {
  const source = documentRef.getElementById(id);
  if (!source || typeof source.cloneNode !== 'function') return null;
  const copy = source.cloneNode(true);
  const ids = new Map();
  for (const element of [copy, ...copy.querySelectorAll('[id]')]) {
    if (!element.id) continue;
    const next = `replay-${element.id}`;
    ids.set(element.id, next);
    element.id = next;
  }
  for (const element of copy.querySelectorAll('[aria-labelledby], [aria-controls], [for]')) {
    for (const attr of ['aria-labelledby', 'aria-controls', 'for']) {
      if (!element.hasAttribute(attr)) continue;
      element.setAttribute(attr, element.getAttribute(attr).split(' ').map(part => ids.get(part) ?? part).join(' '));
    }
  }
  copy.querySelectorAll('[data-od-id]').forEach(element => {
    element.dataset.replayOdId = element.dataset.odId;
    element.removeAttribute('data-od-id');
  });
  copy.querySelectorAll('[data-ownship-card-page]').forEach(element => {
    element.dataset.replayOwnshipPage = element.dataset.ownshipCardPage;
    delete element.dataset.ownshipCardPage;
  });
  copy.querySelectorAll('[data-operations-card-page]').forEach(element => {
    element.dataset.replayOperationsPage = element.dataset.operationsCardPage;
    delete element.dataset.operationsCardPage;
  });
  copy.setAttribute('aria-label', id === 'liveInfoSidebar' ? '回放本船信息' : '回放运行信息');
  return copy;
}

export function createReplaySidebars(documentRef = document) {
  const layout = documentRef.getElementById('replayViewerMain');
  if (!layout || typeof layout.prepend !== 'function') return null;
  if (!documentRef.getElementById('replay-liveInfoSidebar')) {
    const left = cloneSidebar(documentRef, 'liveInfoSidebar');
    const right = cloneSidebar(documentRef, 'liveOperationsSidebar');
    if (!left || !right) return null;
    layout.prepend(left);
    layout.append(right);
  }
  const get = id => documentRef.getElementById(`replay-${id}`);
  const set = (id, value) => { const node = get(id); if (node) node.textContent = value; };
  const radarCanvas = get('liveRadarMiniMap');
  const radar = radarCanvas ? createRadarMiniMap({ canvas: radarCanvas }) : null;
  const depthReadout = get('sidebarDepthReadout');
  const depthFallback = documentRef.createElement('span');
  depthFallback.className = 'replay-depth-fallback';
  depthFallback.textContent = '未记录';
  depthReadout?.parentElement?.append(depthFallback);
  const depthInstrument = get('liveDepthActual');
  const instrumentFallback = documentRef.createElement('span');
  instrumentFallback.className = 'replay-depth-instrument-fallback';
  instrumentFallback.textContent = '当前回放未记录船位 ENC 水深';
  depthInstrument?.parentElement?.append(instrumentFallback);
  let displayedBalance = Symbol('initial');
  for (const page of layout.querySelectorAll('[data-replay-ownship-page="4"]')) {
    const notice = documentRef.createElement('section');
    notice.className = 'config-obc-card balance-card';
    const title = documentRef.createElement('div');
    title.className = 'live-detail-title';
    title.textContent = 'AIS';
    const detail = documentRef.createElement('p');
    detail.className = 'balance-note';
    detail.textContent = '此项未写入封存回放';
    notice.append(title, detail);
    page.replaceChildren(notice);
  }
  for (const value of layout.querySelectorAll('.operations-algo-page .algorithm-data-row dd')) value.textContent = '—';

  function renderFactPage(pageNumber, sections) {
    const page = layout.querySelector(`[data-replay-ownship-page="${pageNumber}"]`);
    if (!page) return;
    const cards = sections.map(([heading, facts]) => {
      const card = documentRef.createElement('section');
      card.className = 'config-obc-card balance-card';
      const title = documentRef.createElement('div');
      title.className = 'live-detail-title';
      title.textContent = heading;
      card.append(title);
      for (const [label, value] of facts) {
        const row = documentRef.createElement('div');
        row.className = 'balance-limit';
        const caption = documentRef.createElement('span');
        const reading = documentRef.createElement('strong');
        caption.textContent = label;
        reading.textContent = value;
        row.append(caption, reading);
        card.append(row);
      }
      return card;
    });
    page.replaceChildren(...cards);
  }

  function pagination(kind, selector, positionId, previousId, nextId) {
    const position = get(positionId);
    if (!position) return;
    const pages = [...layout.querySelectorAll(selector)];
    const dots = [...position.children];
    let index = 0;
    const show = () => {
      pages.forEach((page, i) => { page.hidden = i !== index; });
      dots.forEach((dot, i) => {
        if (i === index) dot.setAttribute('aria-current', 'true');
        else dot.removeAttribute('aria-current');
      });
      position.setAttribute('aria-label', `第 ${index + 1} 张，共 ${pages.length} 张`);
    };
    get(previousId)?.addEventListener('click', () => { index = (index + pages.length - 1) % pages.length; show(); });
    get(nextId)?.addEventListener('click', () => { index = (index + 1) % pages.length; show(); });
    dots.forEach((dot, i) => dot.addEventListener('click', () => { index = i; show(); }));
    show();
  }
  pagination('ownship', '[data-replay-ownship-page]', 'ownshipCardPosition', 'previousOwnshipCardBtn', 'nextOwnshipCardBtn');
  pagination('operations', '[data-replay-operations-page]', 'operationsCardPosition', 'previousOperationsCardBtn', 'nextOperationsCardBtn');

  // Live sensor selectors must never imply a recorded sensor source.
  for (const selector of layout.querySelectorAll('.navigation-data-source-select')) selector.hidden = true;

  function render(snapshot, journal, playhead) {
    const nav = snapshot?.navigation ?? {};
    const raw = snapshot?.raw ?? {};
    const own = raw.os ?? {};
    const heading = degrees(nav.psi);
    const cog = degrees(nav.cog);
    const speedKn = Number.isFinite(nav.sog) ? nav.sog * 1.94384 : null;
    const rot = Number.isFinite(own.r) ? own.r * 180 / Math.PI : null;
    const readout = (id, value, unit, digits = 0) => {
      const node = get(id);
      if (node) node.readouts = Number.isFinite(value)
        ? [{ type: 'value', value: Number(value.toFixed(digits)), nDigits: 3, nDecimals: digits, unit }]
        : [];
    };
    readout('sidebarHdgReadout', heading, '°');
    readout('sidebarCogReadout', cog, '°');
    readout('sidebarStwReadout', speedKn, 'kn', 1);
    readout('sidebarDepthReadout', own.floor_depth_m, 'm');
    get('sidebarHdgReadout')?.setAttribute('aria-label', heading === null ? '本船航向未记录' : `本船航向 ${fixed(heading, 0)} 度`);
    get('sidebarCogReadout')?.setAttribute('aria-label', cog === null ? '本船对地航向未记录' : `本船对地航向 ${fixed(cog, 0)} 度`);
    get('sidebarStwReadout')?.setAttribute('aria-label', speedKn === null ? '本船航速未记录' : `本船对水速度 ${fixed(speedKn)} 节`);
    if (depthReadout) depthReadout.hidden = !Number.isFinite(own.floor_depth_m);
    depthFallback.hidden = Number.isFinite(own.floor_depth_m);
    get('sidebarDepthReadout')?.setAttribute('aria-label', Number.isFinite(own.floor_depth_m)
      ? `船位 ENC 水深分层下限 ${own.floor_depth_m} 米` : 'ENC 水深未记录');
    set('sidebarLatReadout', coordinate(nav.latitude, 'N', 'S') ?? '位置未记录');
    set('sidebarLonReadout', coordinate(nav.longitude, 'E', 'W') ?? '');
    set('liveRouteCourse', heading === null ? '---' : `${Math.round(heading)}°`);
    set('liveRouteRot', rot === null ? '---' : `${fixed(rot)}°/s`);
    set('liveRouteRadius', rot !== null && Math.abs(rot) >= 1 / 60 && Number.isFinite(nav.sog)
      ? `${Math.round(nav.sog / Math.abs(own.r))} m` : '---');
    const collision = snapshot?.risk?.status === 'AVAILABLE' && snapshot.risk.primary?.avoidanceActionActive === true;
    set('liveSteeringMode', collision ? 'COLLISION' : 'TRACK');
    const steering = get('liveSteeringMode');
    if (steering) steering.dataset.mode = collision ? 'collision' : 'track';
    const waypoints = raw.waypoints;
    const north = waypoints?.[0] ?? [];
    const east = waypoints?.[1] ?? [];
    const x = own.x; const y = own.y;
    for (const id of ['liveLegCourse', 'liveLegDistance', 'liveLegTime', 'liveNextLegCourse', 'liveNextLegDistance', 'liveNextLegTime', 'liveRouteRemaining', 'liveRouteEta']) set(id, '---');
    if (north.length >= 2 && east.length >= 2 && Number.isFinite(x) && Number.isFinite(y)) {
      const candidate = north.findIndex((n, i) => i < north.length - 1
        && ((north[i + 1] - n) * (x - n) + (east[i + 1] - east[i]) * (y - east[i]))
          < Math.hypot(north[i + 1] - n, east[i + 1] - east[i]) ** 2);
      const leg = candidate < 0 ? north.length - 2 : candidate;
      const remaining = Math.hypot(north[leg + 1] - x, east[leg + 1] - y);
      let total = remaining;
      for (let i = leg + 1; i < north.length - 1; i += 1) total += Math.hypot(north[i + 1] - north[i], east[i + 1] - east[i]);
      const bearing = degrees(Math.atan2(east[leg + 1] - east[leg], north[leg + 1] - north[leg]));
      set('liveLegCourse', `${Math.round(bearing)}°`);
      set('liveLegDistance', `${fixed(remaining / NM)} NM`);
      set('liveLegTime', duration(remaining / nav.sog));
      set('liveRouteRemaining', duration(total / nav.sog));
      set('liveRouteEta', duration(playhead + total / nav.sog));
      const next = leg + 2 < north.length;
      const nextSection = layout.querySelector('#replay-liveNextLegCourse')?.closest('.route-leg');
      if (nextSection) nextSection.hidden = !next;
      if (next) {
        set('liveNextLegCourse', `${Math.round(degrees(Math.atan2(east[leg + 2] - east[leg + 1], north[leg + 2] - north[leg + 1])))}°`);
        set('liveNextLegDistance', `${fixed(Math.hypot(north[leg + 2] - north[leg + 1], east[leg + 2] - east[leg + 1]) / NM)} NM`);
        set('liveNextLegTime', duration(Math.hypot(north[leg + 2] - north[leg + 1], east[leg + 2] - east[leg + 1]) / nav.sog));
      }
    }
    const compass = get('liveCompass');
    if (compass) Object.assign(compass, { heading: heading ?? 0, course: cog ?? heading ?? 0, rotationsPerMinute: (rot ?? 0) / 6, direction: 'northUp' });
    readout('liveHeadingReadout', heading, '°');
    readout('liveCogReadout', cog, '°');
    readout('liveRotReadout', rot, '°/s', 1);
    const gauge = get('liveSpeedGauge');
    if (gauge) Object.assign(gauge, {
      speed: speedKn ?? 0, minSpeed: -5, maxSpeed: 25, needleType: 'full',
      priority: 'regular', showLabels: true, showReadout: true, tickmarkInterval: 5,
      speedAdvices: [
        { minSpeed: 15, maxSpeed: 18, type: 'advice', hinted: false },
        { minSpeed: 20, maxSpeed: 25, type: 'caution', hinted: false },
      ],
    });
    if (gauge) gauge.setAttribute('aria-label', `本船对水速度 ${fixed(speedKn)} 节`);
    if (radar) {
      const levels = Object.fromEntries((snapshot?.risk?.targets ?? [])
        .filter(target => target.targetId !== null && target.targetId !== undefined)
        .map(target => [String(target.targetId), {
          HIGH: 'danger', LOW: 'warn', CLEAR: 'safe',
        }[target.displayClass] ?? 'unknown']));
      radar.render(buildRadarModel(raw, RADAR_DETECTION_RANGE_M, levels));
    }
    readout('liveCurrentDepthReadout', own.floor_depth_m, 'm');
    get('liveCurrentDepthReadout')?.setAttribute('aria-label', Number.isFinite(own.floor_depth_m)
      ? `船位 ENC 水深分层下限 ${own.floor_depth_m} 米` : 'ENC 水深未记录');
    readout('liveDraftReadout', raw.enc_navigation_area?.vessel_draft_m, 'm', 1);
    readout('liveSafeDepthReadout', raw.enc_navigation_area?.minimum_depth_m, 'm');
    const depth = get('liveDepthActual');
    if (depth) {
      depth.hidden = !Number.isFinite(own.floor_depth_m);
      instrumentFallback.hidden = !depth.hidden;
      if (!depth.hidden) {
        const instrumentRange = Math.max(50, 10 ** Math.ceil(Math.log10(Math.max(1, own.floor_depth_m))));
        Object.assign(depth, {
          depth: own.floor_depth_m,
          draft: raw.enc_navigation_area?.vessel_draft_m ?? 0,
          vesselScale: instrumentRange / 100,
          instrumentRange,
          priority: 'enhanced',
        });
      }
    }

    const balance = raw.gnc_balance;
    if (balance !== displayedBalance) {
      displayedBalance = balance;
      if (!balance) {
        renderFactPage(2, [['BALANCE', [['Status', '此项未写入封存回放']]]]);
        renderFactPage(3, [['PROPULSION', [['Status', '此项未写入封存回放']]]]);
      } else {
        const environment = balance.environment ?? {};
        renderFactPage(2, [
          ['ROLL', [['Roll', `${fixed(balance.roll_deg)}°`], ['Rate', `${fixed(balance.roll_rate_deg_s)}°/s`]]],
          ['WIND', [['Speed', `${fixed(environment.wind_speed_mps)} m/s`], ['From', `${fixed(environment.wind_from_deg, 0)}°`]]],
          ['WAVES', [['Height', `${fixed(environment.wave_hs_m)} m`], ['Period', `${fixed(environment.wave_tz_s ?? environment.wave_tp_s)} s`]]],
          ['CURRENT', [['Speed', `${fixed(environment.current_speed_mps)} m/s`], ['To', `${fixed(environment.current_to_deg, 0)}°`]]],
        ]);
        const speed = balance.speed_contract ?? {};
        const execution = [
          ['Admission', balance.route_admission?.status ?? '—'],
          ['Mode', [speed.input_kind, speed.mode, speed.state].filter(Boolean).join(' · ') || '—'],
          ['Mission', `${fixed(speed.mission_speed_mps, 2)} m/s`],
          ['Planner', `${fixed(speed.planner_speed_mps, 2)} m/s`],
          ['Admitted', `${fixed(speed.admitted_speed_mps, 2)} m/s`],
          ['Actual', `${fixed(speed.actual_speed_mps, 2)} m/s`],
        ];
        if (balance.route_admission?.reason) execution.push(['Reason', String(balance.route_admission.reason)]);
        const actuators = (balance.propulsion ?? []).map(item => [
          String(item.id ?? 'Actuator'),
          item.kind === 'rudder' ? `${fixed(item.angle_deg)}°` : `${fixed(Number.isFinite(item.actual_n) ? item.actual_n / 1000 : null)} kN`,
        ]);
        renderFactPage(3, [
          ['GNC EXECUTION', execution],
          ['PROPULSION', actuators.length ? actuators : [['Status', balance.propulsion_status ?? '—']]],
          ['CONSTRAINTS', (balance.constraints ?? []).map(item => [String(item.label), `${fixed(item.value)} ${item.unit ?? ''}`])],
        ]);
      }
    }

    const risk = snapshot?.risk;
    const list = get('liveRiskTargetList');
    if (list) {
      list.replaceChildren();
      const targets = risk?.status === 'AVAILABLE' ? risk.targets ?? [] : [];
      if (!targets.length) {
        const card = documentRef.createElement('article');
        card.className = 'risk-target-card';
        card.dataset.priority = 'none';
        card.textContent = risk?.status === 'AVAILABLE' ? '无记录目标' : 'Threat Management · 不可用';
        list.append(card);
      }
      for (const target of targets) {
        const card = documentRef.createElement('article');
        card.className = 'risk-target-card';
        card.dataset.threat = ({ HIGH: 'danger', LOW: 'warn', CLEAR: 'safe' })[target.displayClass] ?? 'unknown';
        card.dataset.schedule = target.scheduleClass ?? 'UNKNOWN';
        if (target.isPrimary) card.dataset.priority = 'highest';
        const headingRow = documentRef.createElement('div');
        headingRow.className = 'risk-target-heading';
        const label = documentRef.createElement('span');
        label.textContent = ({ CURRENT_PRIMARY: 'PRIMARY', CONCURRENT_REQUIRED: 'REQUIRED', NEXT: 'NEXT', MONITOR: 'MONITOR' })[target.scheduleClass] ?? 'TARGET';
        if (target.isPrimary && risk?.primarySelection?.status) {
          const status = documentRef.createElement('em');
          status.textContent = String(risk.primarySelection.status).replaceAll('_', ' ');
          label.append(status);
        }
        const name = documentRef.createElement('strong');
        name.textContent = target.targetLabel ?? `TS${target.targetId}`;
        headingRow.append(label, name);
        const metrics = documentRef.createElement('div');
        metrics.className = 'risk-target-metrics';
        for (const [title, value, unit] of [['DCPA', target.dcpaM, 'm'], ['TCPA', target.tcpaS, 's']]) {
          const box = documentRef.createElement('div'); box.className = 'risk-target-metric';
          const caption = documentRef.createElement('span'); caption.textContent = title;
          const number = documentRef.createElement('strong'); number.textContent = `${fixed(value)} ${unit}`;
          box.append(caption, number); metrics.append(box);
        }
        const facts = documentRef.createElement('dl'); facts.className = 'risk-target-facts';
        const vessel = (raw.obstacles ?? []).find(item => String(item.id) === String(target.targetId)) ?? {};
        const dimensions = String(vessel.dimensions_provenance ?? '').includes('ASSUMED') ? 'ASSUMED' : vessel.dimensions_provenance ? 'PROVEN' : '—';
        for (const [title, value] of [['COLREGs Rule', target.encounter ?? '--'], ['Risk state', target.avoidanceActionActive ? 'AVOIDING' : target.displayClass === 'LOW' ? 'MONITOR' : target.displayClass === 'CLEAR' ? 'SAFE' : 'UNKNOWN'], ['Target range', Number.isFinite(target.distanceM) ? `${fixed(target.distanceM / NM, 2)} NM` : '---'], ['AIS state', vessel.historical_sample_kind ?? '—'], ['Hull dimensions', dimensions]]) {
          const row = documentRef.createElement('div'); const dt = documentRef.createElement('dt'); const dd = documentRef.createElement('dd');
          dt.textContent = title; dd.textContent = value; row.append(dt, dd); facts.append(row);
        }
        card.append(headingRow, metrics, facts); list.append(card);
      }
    }
    const events = (journal?.events ?? []).filter(event => Number(event.sim_time) <= playhead + 1e-6);
    set('liveEventCount', String(events.length));
    const eventList = get('liveEvents');
    if (eventList) {
      eventList.showHeader = false;
      eventList.events = events.slice(-40).reverse().map(event => ({
        title: `${String(event.type ?? 'Event').replaceAll('_', ' ')}${event.details?.target_id == null ? '' : ` · TS${event.details.target_id}`}`,
        description: duration(Number(event.sim_time)), startTime: duration(Number(event.sim_time)),
        endTime: '', eventItemType: 'doubleLine', hasTime: false, hasEndTime: false, hasArrow: false, colorCoded: false,
      }));
    }
    const planner = snapshot?.planner ?? {};
    set('plannerSolveState', planner.feasible ? 'SUCCESS' : planner.status ?? '—');
    set('topRunState', snapshot?.state ?? '—');
    set('liveSolveStatus', planner.status ?? '—');
    set('liveSolutionId', `#${planner.solveId ?? '—'}`);
    set('liveAlgorithm', planner.algorithmId ?? '—');
    set('liveHorizonSteps', String(planner.horizonLength ?? '—'));
    set('liveStepInterval', fixed(planner.horizonDtS));
    set('liveExecHeading', fixed(degrees(planner.appliedCourseRefRad)));
    set('liveExecSpeed', fixed(planner.appliedSpeedRefMps, 2));
    set('liveStepTime', fixed(planner.elapsedMs, 2));
    set('liveAvgTime', '—');
  }
  render(null, null, 0);
  return { left: get('liveInfoSidebar'), right: get('liveOperationsSidebar'), render };
}
