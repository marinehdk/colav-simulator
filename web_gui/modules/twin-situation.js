import { targetsForDisplay, RADAR_DETECTION_RANGE_M, drawVODecisionDisc } from './situation-display.js?v=20261004-token-cleanup-v1';
import { routeRibbonQuads } from './route-3d.js?v=20260921-route-ar-v1';
import { predictionMarkers, targetKey, offscreenDirection } from './scene-geography.js?v=20261004-token-cleanup-v1';
import { targetPresentation, updateTargetPoi, applyTargetAppearance, renderTargetCard } from './scene-target.js?v=20260923-follow-v1';
import { createSceneCompass } from './scene-compass.js?v=20260923-follow-v1';
import { AIS_SYMBOL_ASSETS, AIS_SYMBOL_SIZES, aisSymbolState } from './ais-display.js';

export const FRAME_MARKER = Object.freeze({ width: 256, height: 16 });

export function decodeFrameMarker(pixels) {
  if (!pixels || pixels.length !== 128) return null;
  let bits = 0;
  for (let i = 0; i < 32; i++) {
    const level = (pixels[i * 4] + pixels[i * 4 + 1] + pixels[i * 4 + 2]) / 3;
    // Ambiguous compression samples fail closed instead of selecting another frame.
    if (level > 80 && level < 175) return null;
    bits = ((bits << 1) | (level >= 175 ? 1 : 0)) >>> 0;
  }
  if ((bits >>> 24) !== 0xd3) return null;
  const frame = (bits >>> 8) & 65535;
  return (bits & 255) === (((frame >>> 8) ^ frame ^ 0x5a) & 255) ? frame : null;
}

export function containedVideoRect(width, height, videoWidth, videoHeight) {
  if (![width, height, videoWidth, videoHeight].every(value => Number.isFinite(value) && value > 0)) return null;
  const scale = Math.min(width / videoWidth, height / videoHeight);
  const w = videoWidth * scale, h = videoHeight * scale;
  return { left: (width - w) / 2, top: (height - h) / 2, width: w, height: h, scale };
}

export function matchedSituationFrame(client, frameId, runId, width, height) {
  const frame = client?.situationFrame?.(frameId);
  return frame?.run_id === runId && frame.width === width && frame.height === height ? frame : null;
}

// OpenBridge's offset POI keeps its pointer at the vessel while moving its head.
// Its auto-group layout assumes one shared horizon row and ignores buttonY.
export function layoutTwinLabels(items, width, topInset = 20) {
  const placed = [], result = new Map();
  for (const item of [...items].sort((a, b) => b.priority - a.priority || a.key.localeCompare(b.key))) {
    let chosen = null;
    for (const compact of [false, true]) {
      const height = compact ? 48 : item.height;
      const maxLift = item.y - topInset - height;
      if (maxLift < 0) continue;
      const base = Math.min(72, maxLift);
      const preferredX = Math.max(36, Math.min(width - 36, item.x));
      for (let lift = base; lift <= maxLift + 0.1 && !chosen; lift += height + 12) {
        for (const offset of [0, 72, -72, 144, -144, 216, -216, 288, -288, 360, -360, 432, -432]) {
          const x = preferredX + offset, top = item.y - lift - height, bottom = item.y - lift;
          if (x < 36 || x > width - 36) continue;
          if (placed.some(p => Math.abs(p.x - x) < 72 && top < p.bottom + 12 && bottom > p.top - 12)) continue;
          chosen = { x, lift, top, bottom, compact }; break;
        }
      }
      if (chosen) break;
    }
    // Retain even a tightly clipped contact as a compact selectable head.
    chosen ||= { x: Math.max(36, Math.min(width - 36, item.x)), lift: 0, top: item.y - 48, bottom: item.y, compact: true };
    placed.push(chosen); result.set(item.key, chosen);
  }
  return result;
}

export function buildTwinPresentation(projection, chart, info, vo = null, documentRef = null) {
  const raw = projection?.raw;
  if (!raw || !info || raw.run_id !== info.run_id) return null;
  const layers = chart.getLayerState();
  const visible = name => layers[name]?.visible !== false;
  const point = (north, east, label = '') => ({ east: info.origin_e + east, north: info.origin_n + north, label });
  const route = chart.getMissionRoute();
  const targets = targetsForDisplay(raw).filter(ship => ship.active !== false);
  const lines = [
    ['route', visible('route') ? route[0].map((n, i) => [n, route[1][i]]) : [], '#137fd1', 3, true],
    ['history', visible('history') ? raw.os?.trajectory : [], '#7e8991', 2, false],
    ['prediction', visible('prediction') ? raw.plans?.prediction_horizon : [], '#e99819', 3, false],
    ['previous', layers.previousPrediction?.visible ? raw.plans?.previous_prediction_horizon : [], '#a7a7a7', 1, true],
  ].map(([id, points, color, width, dashed]) => ({ id, color, width, dashed,
    points: (points || []).filter(p => p?.length >= 2 && p.slice(0, 2).every(Number.isFinite)).map(p => point(p[0], p[1])) }));
  if (visible('radarRange') && raw.os) {
    lines.push({ id: 'detection-ring', color: '#d4e9ee', width: 1.5, dashed: false,
      points: Array.from({ length: 129 }, (_, i) => point(raw.os.x + RADAR_DETECTION_RANGE_M * Math.cos(i * Math.PI / 64),
        raw.os.y + RADAR_DETECTION_RANGE_M * Math.sin(i * Math.PI / 64))) });
  }
  let disc = null;
  if (vo && raw.os && Number.isFinite(raw.os.length) && raw.os.length > 0 && documentRef) {
    const canvas = documentRef.createElement('canvas'); canvas.width = canvas.height = 240;
    const ctx = canvas.getContext('2d');
    if (drawVODecisionDisc(ctx, vo, 120, 120, 110, Number(vo.ownship_heading_rad) || 0, Number(vo.ownship_heading_rad) || 0)) {
      disc = { ...point(raw.os.x, raw.os.y), radius: raw.os.length * 3, png: canvas.toDataURL('image/png').split(',')[1] };
    }
  }
  return { run_id: raw.run_id, seq: raw.seq, sim_time: raw.sim_time,
    ribbon: visible('route') ? routeRibbonQuads(route).flat().map(p => point(p.north, p.east)) : [],
    waypoints: route[0].map((north, i) => point(north, route[1][i], 'WPT' + (i + 1))),
    waypoints_visible: visible('waypoints'), ships_visible: visible('ships'), lines, vo: disc,
    time_markers: visible('prediction') ? predictionMarkers(raw).map(m => point(...m.point, '+' + m.elapsed.toFixed(0) + 's')) : [],
    targets: targets.map(ship => ({ ...point(ship.x, ship.y), id: String(ship.id), key: targetKey(raw.run_id, ship),
      truth: raw.executed_tracker === 'god', length: ship.length || 12, width: ship.width || 5 })),
  };
}

// OpenBridge DOM stays outside the video. All placements are taken from a decoded
// frame, never from the newest camera heartbeat or a second Cesium camera.
export function createTwinSituationOverlay({ host, video, chart, info, client, onSelect, onCameraChange = () => {}, getPlannerSurface, requestVODecisionSpace }) {
  const doc = host.ownerDocument;
  const root = doc.createElement('div'); root.className = 'twin-situation-overlay'; root.hidden = true;
  const layer = doc.createElement('div'); layer.className = 'scene3d-pois';
  const waypoints = doc.createElement('div'); waypoints.className = 'scene3d-waypoints';
  const edges = doc.createElement('div'); edges.className = 'scene3d-edges';
  const aisLayer = doc.createElement('div'); aisLayer.className = 'twin-ais-markers';
  const card = doc.createElement('obc-poi-card'); card.className = 'scene3d-card'; card.hidden = true; card.hasCloseButton = true;
  const cardBody = doc.createElement('div'); cardBody.className = 'scene3d-card-body'; card.append(cardBody);
  const cardIcon = doc.createElement('obi-vessel-generic-default-outlined'); cardIcon.slot = 'poi-icon'; card.append(cardIcon);
  const cardAlert = doc.createElement('obc-alert-frame'); cardAlert.className = 'scene3d-card-alert'; cardAlert.type = 'regular'; cardAlert.thickness = 'large'; cardAlert.hidden = true; card.append(cardAlert);
  const markerCover = doc.createElement('div'); markerCover.className = 'twin-frame-cover'; markerCover.textContent = 'DT';
  markerCover.hidden = true;
  const toolbar = doc.createElement('div'); toolbar.className = 'scene3d-toolbar';
  for (const [preset, label] of [['bridge', '舰桥'], ['chase', '追随'], ['top', '俯视'], ['target', '目标跟踪']]) {
    const button = doc.createElement('button'); button.textContent = label; button.dataset.camera = preset;
    button.addEventListener('click', () => {
      onCameraChange();
      if (preset === 'target') trackSelected(); else client()?.sendCamera?.(preset);
    }); toolbar.append(button);
  }
  root.append(layer, waypoints, edges, aisLayer, card, toolbar); host.append(root, markerCover);
  const compass = createSceneCompass({ host: root, onSelect: id => choose(id) });
  const sample = doc.createElement('canvas'); sample.width = 32; sample.height = 1;
  const sampleContext = sample.getContext('2d', { willReadFrequently: true }); sampleContext.imageSmoothingEnabled = false;
  const models = new Map(), pois = new Map(), waypointNodes = new Map(), aisNodes = new Map();
  let latest = null, frame = null, frameId = null, selectedKey = null, disposed = false;
  let lastSent = null, lastPick = null, lastVideoAt = 0, pointer = null;
  let presentationClient = null, presentationAttachment = null;
  let matched = 0, unmatched = 0;
  function choose(id, key = null) {
    const projection = models.get(frame?.source_seq) || latest;
    const ship = targetsForDisplay(projection?.raw || {}).find(ship => String(ship.id) === String(id));
    const previous = selectedKey;
    selectedKey = key || (ship ? targetKey(projection.raw.run_id, ship) : null);
    if (onSelect) onSelect(id); else chart.selectTarget(id);
    if (selectedKey !== previous) {
      onCameraChange();
      if (selectedKey) trackSelected(); else client()?.sendCamera?.('chase');
    }
    renderFrame();
  }
  function trackSelected() {
    const projection = models.get(frame?.source_seq) || latest;
    if (selectedKey && projection) client()?.sendCameraTarget?.(projection.raw.run_id, selectedKey);
  }
  card.addEventListener('close-click', () => choose(null));
  const down = event => { pointer = { x: event.clientX, y: event.clientY }; };
  const up = event => {
    if (!pointer || Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) > 4) { pointer = null; return; }
    pointer = null;
    if (!frame || root.hidden) return;
    const rect = root.getBoundingClientRect(), x = (event.clientX - rect.left) / rect.width, y = (event.clientY - rect.top) / rect.height;
    if (x >= 0 && x <= 1 && y >= 0 && y <= 1) client()?.sendPick?.(frame.run_id, frame.frame_id, x, y);
  };
  video.addEventListener('pointerdown', down); video.addEventListener('pointerup', up);

  function renderFrame() {
    const videoBox = video.getBoundingClientRect(), hostBox = host.getBoundingClientRect();
    const rect = containedVideoRect(videoBox.width, videoBox.height, video.videoWidth, video.videoHeight);
    if (!rect) { root.hidden = true; return; }
    rect.left += videoBox.left - hostBox.left; rect.top += videoBox.top - hostBox.top;
    markerCover.hidden = client()?.situationSync !== 'frame-marker@1';
    Object.assign(markerCover.style, { left: rect.left + 'px', top: rect.top + 'px',
      width: FRAME_MARKER.width * rect.scale + 'px', height: Math.max(18, FRAME_MARKER.height * rect.scale) + 'px' });
    const projection = frame && models.get(frame.source_seq);
    if (!projection || projection.raw.run_id !== frame.run_id) { root.hidden = true; return; }
    markerCover.textContent = 'DT · ' + (frame.targets?.length || 0) + ' 个目标';
    Object.assign(root.style, { left: rect.left + 'px', top: rect.top + 'px', width: rect.width + 'px', height: rect.height + 'px' });
    if (frame.landscape?.ready === false) {
      // A heartbeat can release the video if hidden-video callbacks are throttled.
      if (!client()?.lastState?.landscape?.ready) video.style.visibility = 'hidden';
      root.hidden = true; markerCover.hidden = true; return;
    }
    video.style.visibility = '';
    root.hidden = false;
    root.dataset.camera = frame.camera;
    if (frame.camera_pose) root.dataset.cameraPose = JSON.stringify(frame.camera_pose);
    toolbar.querySelectorAll('button').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.camera === frame.camera));
      button.disabled = button.dataset.camera === 'target' && !selectedKey;
    });
    const ships = targetsForDisplay(projection.raw), byKey = new Map(ships.map(ship => [targetKey(frame.run_id, ship), ship]));
    const selected = chart.getSelectedTargetId();
    if (selectedKey && !byKey.has(selectedKey)) { selectedKey = null; chart.selectTarget(null); onSelect?.(null); }
    compass.render(projection, frame.camera, chart.getLayerState().ships?.visible !== false);
    const compassHeight = root.querySelector('.scene3d-compass')?.offsetHeight || 0;
    const visibleY = (frame.targets || []).filter(p => p.visible).map(p => p.y * rect.height);
    const lowHorizon = visibleY.length > 0 && Math.min(...visibleY) < compassHeight + 80;
    root.classList.toggle('twin-low-horizon', lowHorizon);
    const topInset = lowHorizon ? 24 : Math.min(rect.height / 3, compassHeight + 12);
    const wanted = new Set(), edgeRecords = [], aisWanted = new Set();
    const contacts = (frame.targets || []).flatMap(p => {
      const ship = byKey.get(p.key); if (!ship) return [];
      const model = targetPresentation(projection, ship, info), x = p.x * rect.width, y = p.y * rect.height;
      const selectedContact = String(selected) === p.id;
      const primary = String(projection.risk?.primary?.targetId ?? projection.risk?.primary?.target_id) === p.id
        && (projection.risk?.primary?.generation ?? null) === (ship.generation ?? null);
      const available = y - topInset;
      const blocks = (selectedContact || primary) && available >= 300 ? model.blocks : available >= 170 ? [model.blocks[1]] : [];
      return [{ p, ship, model, x, y, blocks, focus: selectedContact || primary,
        key: p.key, height: blocks.length ? blocks.length * 64 + 80 : 48,
        priority: selectedContact ? 3 : primary ? 2 : model.alert.state === 'alarm' ? 1 : 0 }];
    });
    const layout = layoutTwinLabels(contacts.filter(c => c.p.visible && c.x >= 24 && c.x <= rect.width - 24 && c.y >= topInset),
      rect.width - (selected !== null && selected !== undefined ? 340 : 0), topInset);
    for (const { p, ship, model, x, y, blocks, focus } of contacts) {
      if (!p.visible || x < 24 || x > rect.width - 24 || y < topInset || y > rect.height - 16) {
        if (focus) edgeRecords.push({ p, model, ...offscreenDirection({ x, y }, rect.width, rect.height, p.depth > 0, p.x >= 0.5) });
        continue;
      }
      wanted.add(p.key);
      let record = pois.get(p.key);
      if (!record) {
        const target = doc.createElement('obc-poi'); target.animatePosition = false;
        const poi = doc.createElement('obc-poi-button-vessel'); poi.slot = 'button';
        poi.append(doc.createElement('obi-vessel-generic-default-outlined'));
        target.hasHeader = true; target.headerContent = p.id; target.hasPointer = true;
        poi.dataset.targetKey = p.key; poi.setAttribute('aria-label', 'TS' + p.id + ' 目标详情');
        target.addEventListener('click', () => choose(p.id, p.key)); target.append(poi); layer.append(target);
        record = { target, poi }; pois.set(p.key, record);
      }
      const { target, poi } = record;
      const placement = layout.get(p.key);
      updateTargetPoi(poi, { ...model, blocks: placement?.compact ? [] : blocks });
      applyTargetAppearance(target, model.alert);
      target.state = model.alert.poiState; target.value = model.alert.state === 'unchecked' ? 'unchecked' : 'checked';
      target.data = placement?.compact ? [] : blocks;
      if (model.alert.state === 'unchecked') {
        target.style.setProperty('--element-active-color', 'inherit');
        poi.style.setProperty('--element-active-color', 'inherit');
      }
      const lift = placement?.lift ?? 0;
      target.x = placement?.x ?? x; target.y = lift; target.buttonY = y - lift;
      target.buttonOffsetX = 0; target.targetOffsetX = x - target.x;
      target.type = target.targetOffsetX ? 'offset' : 'line';
      target.selected = String(selected) === p.id;
      target.relativeDirection = (ship.psi * 180 / Math.PI - frame.camera_yaw + 360) % 360;
      poi.relativeDirection = target.relativeDirection;
      poi.title = 'TS' + p.id + ' · ' + model.alert.name;
      if (ship.ais && chart.getLayerState().aisTargets?.visible !== false) {
        aisWanted.add(p.key); let button = aisNodes.get(p.key);
        if (!button) {
          button = doc.createElement('button'); button.className = 'twin-ais-marker'; button.append(doc.createElement('img'));
          button.addEventListener('click', () => choose(p.id, p.key)); aisLayer.append(button); aisNodes.set(p.key, button);
        }
        const rank = { alarm: 3, caution: 2, checked: 1 }[model.alert.state] || 0;
        const state = aisSymbolState(ship.ais, rank), img = button.firstElementChild;
        img.src = AIS_SYMBOL_ASSETS[state]; img.style.width = (AIS_SYMBOL_SIZES[state] || 24) + 'px';
        img.style.transform = 'rotate(' + ((ship.psi * 180 / Math.PI - frame.camera_yaw + 360) % 360) + 'deg)';
        button.style.left = x + 'px'; button.style.top = y + 'px'; button.setAttribute('aria-label', 'TS' + p.id + ' AIS 详情');
      }
    }
    for (const [key, record] of pois) if (!wanted.has(key)) { record.target.remove(); pois.delete(key); }
    for (const [key, node] of aisNodes) if (!aisWanted.has(key)) { node.remove(); aisNodes.delete(key); }
    edges.replaceChildren(...edgeRecords.map(({ p, model, edge, arrow }, index) => {
      const button = doc.createElement('button'); button.className = edge; button.textContent = arrow + ' TS' + p.id;
      button.style.setProperty('--edge-index', index); applyTargetAppearance(button, model.alert);
      button.addEventListener('click', () => choose(p.id, p.key)); return button;
    }));
    const waypointWanted = new Set(), placed = [];
    for (const p of [...(frame.waypoints || []), ...(frame.time_markers || [])]) {
      if (!p.visible) continue;
      const x = p.x * rect.width, y = p.y * rect.height;
      if (x < 36 || x > rect.width - 36 || y < topInset || y > rect.height - 16) continue;
      waypointWanted.add(p.label); let node = waypointNodes.get(p.label);
      if (!node) {
        node = doc.createElement('div'); node.className = 'scene3d-waypoint' + (p.label.startsWith('+') ? ' twin-time-marker' : '');
        const leader = doc.createElement('div'); leader.className = 'scene3d-waypoint-leader';
        const head = doc.createElement('div'); head.className = 'scene3d-waypoint-head';
        const label = doc.createElement('span'); label.className = 'scene3d-waypoint-label'; label.textContent = p.label;
        const icon = doc.createElement('span'); icon.className = 'scene3d-waypoint-icon'; head.append(label, icon);
        node.append(leader, head); waypoints.append(node); waypointNodes.set(p.label, node);
      }
      let lift = 92;
      while (placed.some(q => Math.abs(q.x - x) < 64 && Math.abs(q.y - (y - lift)) < 52) && y - lift > topInset + 52) lift += 52;
      lift = Math.min(lift, y - topInset); placed.push({ x, y: y - lift });
      node.style.left = x + 'px'; node.style.top = y + 'px'; node.style.setProperty('--waypoint-lift', lift + 'px');
    }
    for (const [key, node] of waypointNodes) if (!waypointWanted.has(key)) { node.remove(); waypointNodes.delete(key); }
    const ship = ships.find(ship => String(ship.id) === String(chart.getSelectedTargetId()));
    card.hidden = !ship;
    if (ship) {
      const model = targetPresentation(projection, ship, info);
      card.cardTitle = ship.name || 'TS' + ship.id; card.index = String(ship.id);
      card.source = projection.raw.executed_tracker === 'god' ? 'GOD' : 'TRACK'; card.headerVariant = 'detailed';
      card.description = (ship.length ?? '—') + ' × ' + (ship.width ?? '—') + ' m';
      applyTargetAppearance(card, model.alert); cardAlert.status = model.alert.poiState;
      if (model.alert.state === 'unchecked') card.style.setProperty('--element-active-color', 'inherit');
      cardAlert.hidden = !['caution', 'alarm'].includes(model.alert.poiState); renderTargetCard(cardBody, model);
    }
    root.dataset.frameId = String(frame.frame_id); root.dataset.sourceSeq = String(frame.source_seq);
    root.dataset.targets = String(wanted.size); root.dataset.sync = 'matched';
    root.dataset.pickTargets = JSON.stringify(frame.targets);
  }
  return {
    render(projection) {
      if (!projection?.raw) return;
      const bridge = client();
      if (bridge !== presentationClient || bridge?.attached !== presentationAttachment) {
        lastSent = null; presentationClient = bridge; presentationAttachment = bridge?.attached;
      }
      latest = projection; models.set(projection.raw.seq, projection);
      if (models.size > 120) models.delete(models.keys().next().value);
      const surface = getPlannerSurface?.();
      if (surface?.type === 'vo') requestVODecisionSpace?.();
      const presentation = buildTwinPresentation(projection, chart, info, surface?.type === 'vo' ? surface.vo : null, doc);
      const signature = JSON.stringify(presentation);
      if (signature !== lastSent && bridge?.attached?.run_id === presentation?.run_id && bridge?.sendPresentation?.(presentation)) lastSent = signature;
    },
    videoFrame(timestamp) {
      if (disposed || video.videoWidth < FRAME_MARKER.width || video.videoHeight < FRAME_MARKER.height) return;
      try {
        sampleContext.drawImage(video, 0, 8, FRAME_MARKER.width, 1, 0, 0, 32, 1);
        frameId = decodeFrameMarker(sampleContext.getImageData(0, 0, 32, 1).data);
      } catch { frameId = null; }
      frame = matchedSituationFrame(client(), frameId, info.run_id, video.videoWidth, video.videoHeight);
      lastVideoAt = timestamp; renderFrame();
      if (!root.hidden) matched++; else unmatched++;
      host.dataset.situationFrames = JSON.stringify({ decoded: frameId, matched, unmatched, sourceSeq: frame?.source_seq ?? null,
        projectionSeq: latest?.raw?.seq ?? null, sync: root.hidden ? 'waiting' : 'matched' });
    },
    tick(timestamp) {
      // DataChannel and video can arrive in either order.
      if (frameId !== null && timestamp - lastVideoAt < 500) {
        frame = matchedSituationFrame(client(), frameId, info.run_id, video.videoWidth, video.videoHeight); renderFrame();
      } else root.hidden = true;
      const pick = client()?.lastPick;
      if (pick && pick !== lastPick) { lastPick = pick; host.dataset.situationPick = JSON.stringify(pick); choose(pick.id, pick.key); }
      if (latest) this.render(latest);
    },
    reset() { lastSent = null; frame = null; frameId = null; root.hidden = true; markerCover.hidden = true; models.clear(); },
    select(id) { choose(id); },
    get cameraPose() { return frame?.camera_pose; },
    get landscape() { return frame?.landscape; },
    destroy() { disposed = true; video.style.visibility = ''; video.removeEventListener('pointerdown', down); video.removeEventListener('pointerup', up); compass.destroy(); root.remove(); markerCover.remove(); },
  };
}
