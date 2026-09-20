import { createGeography, NM, targetKey, riskForTarget, poiState, frameIdentity, predictionMarkers } from './scene-geography.js';
import { targetsForDisplay } from './situation-display.js?v=20260920-3d-v1';

let enginePromise;
export function loadCesium() {
  if (!enginePromise) {
    enginePromise = new Promise((resolve, reject) => {
      window.CESIUM_BASE_URL = '/static/vendor/cesium/';
      if (!document.getElementById('cesiumStyles')) {
        const link = document.createElement('link');
        link.id = 'cesiumStyles'; link.rel = 'stylesheet'; link.href = '/static/vendor/cesium/Widgets/widgets.css';
        document.head.append(link);
      }
      const script = document.createElement('script');
      script.src = '/static/vendor/cesium/Cesium.js';
      script.onload = () => resolve(window.Cesium);
      script.onerror = () => { script.remove(); enginePromise = null; reject(new Error('三维引擎加载失败，可重试')); };
      document.head.append(script);
    });
  }
  return enginePromise;
}

const metric = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : '—';
const degrees = value => Number.isFinite(value) ? (value * 180 / Math.PI + 360) % 360 : null;

export async function createScene3D({ host, info, camera = 'bridge', chart, onSelect, onFailure, onCamera }) {
  const C = await loadCesium();
  const geo = createGeography(info);
  // OpenBridge is loaded by the existing shell; no second registration/bundle.
  await Promise.all(['obc-poi-layer', 'obc-poi-vessel', 'obc-poi-card'].map(name => customElements.whenDefined(name)));
  const root = document.createElement('div'); root.className = 'scene3d-root';
  const canvasHost = document.createElement('div'); canvasHost.className = 'scene3d-canvas';
  const toolbar = document.createElement('div'); toolbar.className = 'scene3d-toolbar';
  toolbar.setAttribute('role', 'group'); toolbar.setAttribute('aria-label', '三维机位');
  const status = document.createElement('div'); status.className = 'scene3d-status'; status.setAttribute('role', 'status');
  const layer = document.createElement('obc-poi-layer'); layer.className = 'scene3d-pois'; layer.overlapMode = 'grouping';
  const edges = document.createElement('div'); edges.className = 'scene3d-edges';
  const card = document.createElement('obc-poi-card'); card.className = 'scene3d-card'; card.hidden = true;
  const cardBody = document.createElement('div'); cardBody.className = 'scene3d-card-body'; card.append(cardBody);
  const credits = document.createElement('div'); credits.className = 'scene3d-credits';
  root.append(canvasHost, layer, edges, toolbar, status, card, credits); host.append(root);
  let viewer;
  try {
    viewer = new C.Viewer(canvasHost, {
      animation: false, timeline: false, baseLayerPicker: false, baseLayer: false,
      geocoder: false, homeButton: false, sceneModePicker: false, navigationHelpButton: false,
      fullscreenButton: false, infoBox: false, selectionIndicator: false,
      terrainProvider: new C.EllipsoidTerrainProvider(), shouldAnimate: false,
      requestRenderMode: true, maximumRenderTimeChange: Infinity,
      creditContainer: credits,
    });
  } catch (error) { root.remove(); throw error; }
  viewer.clock.shouldAnimate = false;
  viewer.scene.globe.baseColor = C.Color.fromCssColorString('#75aab5');
  viewer.scene.globe.enableLighting = false;
  viewer.scene.globe.depthTestAgainstTerrain = false;
  viewer.resolutionScale = 1;
  let disposed = false, projection = null, preset = camera, follow = true, showRings = true;
  let selected = chart.getSelectedTargetId(), selectedKey = null, encPrimitive = null;
  let lastGeometryKey = null, lastRoute = null, lastRingCenter = null;
  const vessels = new Map(), pois = new Map(), geometry = new Map();
  const disposers = [];
  function listen(el, event, fn) { el.addEventListener(event, fn); disposers.push(() => el.removeEventListener(event, fn)); }
  function position(n, e, h = 0) { const [lon, lat] = geo.lonLat(n, e); return C.Cartesian3.fromDegrees(lon, lat, h); }
  function line(id, coordinates, color, width = 2, dashed = false) {
    if (!coordinates?.length || coordinates.length < 2) { const old = geometry.get(id); if (old) viewer.entities.remove(old); geometry.delete(id); return; }
    const points = coordinates.filter(p => p?.length >= 2 && p.slice(0, 2).every(Number.isFinite)).map(p => position(p[0], p[1], 0.8));
    if (points.length < 2) return;
    let entity = geometry.get(id);
    if (!entity) {
      entity = viewer.entities.add({ polyline: { positions: points, width,
        material: dashed ? new C.PolylineDashMaterialProperty({ color: C.Color.fromCssColorString(color) }) : C.Color.fromCssColorString(color),
        arcType: C.ArcType.NONE } });
      geometry.set(id, entity);
    } else entity.polyline.positions = points;
  }
  // A sampled UTM mesh, not a four-corner geographic rectangle.
  function addEnc() {
    const count = 32, vertices = [], normals = [], st = [], indices = [];
    for (let row = 0; row <= count; row++) for (let col = 0; col <= count; col++) {
      const p = position(info.height * row / count, info.width * col / count, 0.1);
      vertices.push(p.x, p.y, p.z);
      const normal = C.Ellipsoid.WGS84.geodeticSurfaceNormal(p);
      normals.push(normal.x, normal.y, normal.z); st.push(col / count, row / count);
      if (row < count && col < count) {
        const i = row * (count + 1) + col;
        indices.push(i, i + 1, i + count + 1, i + 1, i + count + 2, i + count + 1);
      }
    }
    const mesh = new C.Geometry({ attributes: {
      position: new C.GeometryAttribute({ componentDatatype: C.ComponentDatatype.DOUBLE, componentsPerAttribute: 3, values: new Float64Array(vertices) }),
      normal: new C.GeometryAttribute({ componentDatatype: C.ComponentDatatype.FLOAT, componentsPerAttribute: 3, values: new Float32Array(normals) }),
      st: new C.GeometryAttribute({ componentDatatype: C.ComponentDatatype.FLOAT, componentsPerAttribute: 2, values: new Float32Array(st) }),
    }, indices: new Uint16Array(indices), primitiveType: C.PrimitiveType.TRIANGLES, boundingSphere: C.BoundingSphere.fromVertices(vertices) });
    encPrimitive = viewer.scene.primitives.add(new C.Primitive({
      geometryInstances: new C.GeometryInstance({ geometry: mesh }), asynchronous: false,
      appearance: new C.MaterialAppearance({ material: C.Material.fromType('Image', { image: `/api/enc_tile?run_id=${encodeURIComponent(info.run_id)}` }),
        translucent: false, closed: false, faceForward: true }),
    }));
  }
  try { addEnc(); } catch (error) { viewer.destroy(); root.remove(); throw error; }
  function vesselMatrix(ship) {
    const pos = position(ship.x, ship.y, 0.6);
    const angle = geo.heading(ship.x, ship.y, ship.psi ?? 0);
    const matrix = C.Transforms.headingPitchRollToFixedFrame(pos, new C.HeadingPitchRoll(angle - Math.PI / 2, 0, 0));
    const length = Number.isFinite(ship.length) && ship.length > 0 ? ship.length : 20;
    const width = Number.isFinite(ship.width) && ship.width > 0 ? ship.width : 5;
    return C.Matrix4.multiplyByScale(matrix, new C.Cartesian3(length, width, Math.max(4, width * 0.8)), matrix);
  }
  function updateVessels(ships) {
    const wanted = new Set();
    for (const ship of ships) {
      if (ship.active === false || ![ship.x, ship.y].every(Number.isFinite)) continue;
      const key = targetKey(info.run_id, ship); wanted.add(key);
      let record = vessels.get(key);
      if (!record) {
        record = { ship, model: null }; vessels.set(key, record);
        C.Model.fromGltfAsync({ url: '/static/assets/3d/vessel.gltf', modelMatrix: vesselMatrix(ship),
          id: { targetId: ship.id }, color: String(ship.id) === '0' ? C.Color.WHITE : C.Color.LIGHTSTEELBLUE,
        }).then(model => {
          if (disposed || vessels.get(key) !== record) { model.destroy(); return; }
          record.model = viewer.scene.primitives.add(model); viewer.scene.requestRender();
        }).catch(() => { if (!disposed) { record.failed = true; status.textContent = '船模加载失败 · 使用位置标记'; } });
        record.marker = viewer.entities.add({ position: position(ship.x, ship.y, 1), point: { pixelSize: 7, color: C.Color.WHITE }, id: `fallback:${key}` });
      }
      record.ship = ship;
      record.marker.position = position(ship.x, ship.y, 1);
      record.marker.show = !record.model || !record.model.ready;
      if (record.model) record.model.modelMatrix = vesselMatrix(ship);
    }
    for (const [key, record] of vessels) if (!wanted.has(key)) {
      if (record.model) viewer.scene.primitives.remove(record.model);
      viewer.entities.remove(record.marker); vessels.delete(key);
    }
  }
  function setCamera(value) {
    preset = value; follow = true; lastRingCenter = null; onCamera(value); updateCamera(); updateRings();
    toolbar.querySelectorAll('[data-camera]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.camera === preset)));
    viewer.scene.requestRender();
  }
  for (const [value, text] of [['bridge', '驾驶台'], ['chase', '追随'], ['top', '俯视']]) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = text;
    button.dataset.camera = value; button.setAttribute('aria-pressed', String(value === preset));
    listen(button, 'click', () => setCamera(value)); toolbar.append(button);
  }
  const ringsButton = document.createElement('button'); ringsButton.textContent = '距离环'; ringsButton.type = 'button'; ringsButton.setAttribute('aria-pressed', 'true');
  listen(ringsButton, 'click', () => { showRings = !showRings; lastRingCenter = null; ringsButton.setAttribute('aria-pressed', String(showRings)); updateRings(); viewer.scene.requestRender(); }); toolbar.append(ringsButton);
  const close = document.createElement('button'); close.textContent = '关闭详情'; close.type = 'button';
  listen(close, 'click', () => choose(null)); card.append(close);
  function updateCamera() {
    const ship = projection?.raw?.os;
    if (!ship || !follow) return;
    const heading = geo.heading(ship.x, ship.y, ship.psi);
    const length = ship.length || 45;
    if (preset === 'bridge') {
      const eye = position(ship.x - Math.cos(ship.psi) * length * 0.2, ship.y - Math.sin(ship.psi) * length * 0.2, Math.max(9, (ship.width || 10) * 1.1));
      viewer.camera.setView({ destination: eye, orientation: { heading, pitch: -0.025, roll: 0 } });
    } else {
      const range = preset === 'top' ? 2500 : 700;
      const tilt = preset === 'top' ? -Math.PI / 2 + 0.001 : -0.38;
      viewer.camera.lookAt(position(ship.x, ship.y), new C.HeadingPitchRange(heading, tilt, range));
      viewer.camera.lookAtTransform(C.Matrix4.IDENTITY);
    }
    // The bridge eyepoint is illustrative; hide its hull to avoid a false occlusion.
    const own = vessels.get(targetKey(info.run_id, { id: 0 }));
    if (own?.model) own.model.show = preset !== 'bridge';
  }
  for (const event of ['mousedown', 'pointerdown', 'click', 'wheel']) listen(root, event, event => event.stopPropagation());
  listen(viewer.canvas, 'pointerdown', () => { follow = false; });
  listen(viewer.canvas, 'wheel', () => { follow = false; });
  function choose(id) {
    selected = id;
    const ship = [...vessels.values()].find(v => String(v.ship.id) === String(id))?.ship;
    selectedKey = ship ? targetKey(info.run_id, ship) : null;
    onSelect(id); updateCard(); viewer.scene.requestRender();
  }
  const handler = new C.ScreenSpaceEventHandler(viewer.canvas);
  handler.setInputAction(event => {
    const picked = viewer.scene.pick(event.position);
    const id = picked?.id?.targetId;
    if (id !== undefined) choose(id);
  }, C.ScreenSpaceEventType.LEFT_CLICK);
  function updateCard() {
    const record = [...vessels.values()].find(v => String(v.ship.id) === String(selected));
    if (!record || (selectedKey && targetKey(info.run_id, record.ship) !== selectedKey)) {
      card.hidden = true; if (selected !== null) { selected = null; selectedKey = null; onSelect(null); } return;
    }
    const ship = record.ship, risk = riskForTarget(projection, ship);
    selectedKey = targetKey(info.run_id, ship);
    const source = projection.raw.executed_tracker === 'god' ? 'God / 仿真真值' : 'Tracker';
    card.cardTitle = String(ship.id) === '0' ? 'OWN SHIP' : ship.name || `TS${ship.id}`;
    card.index = String(ship.id); card.source = source;
    card.description = '示意船模 · 无真实视频配准'; card.headerVariant = 'condensed';
    const health = risk?.unavailableReasons?.join(' / ') || risk?.observationHealth || '不可用';
    const entries = [
      ['BRG', metric(risk?.bearingDeg, 0), 'DEG'], ['RNG', metric(Number.isFinite(risk?.rangeM) ? risk.rangeM / NM : null, 2), 'NM'],
      ['DCPA', metric(Number.isFinite(risk?.dcpaM) ? risk.dcpaM / NM : null, 2), 'NM'],
      ['TCPA', metric(Number.isFinite(risk?.tcpaS) ? risk.tcpaS / 60 : null), 'min'],
      ['HDG', metric(projection.raw.executed_tracker === 'god' || String(ship.id) === '0' ? degrees(ship.psi) : null, 0), 'DEG'],
      ['SOG', metric(Number.isFinite(ship.sog) ? ship.sog * 3600 / NM : null), 'kn'],
      ['职责', risk?.role || risk?.lifecycleRole || '不可用', ''], ['质量', health, ''],
      ['证据', metric(projection.raw.presentation?.source_sim_time_s ?? projection.raw.sim_time, 2), 's'],
    ];
    const signature = JSON.stringify(entries);
    if (cardBody.dataset.signature !== signature) {
      cardBody.replaceChildren(...entries.map(([name, value, unit]) => {
        const row = document.createElement('div'); const label = document.createElement('span'); const output = document.createElement('strong');
        label.textContent = name; output.textContent = `${value} ${unit}`.trim(); row.append(label, output); return row;
      })); cardBody.dataset.signature = signature;
    }
    card.hidden = false;
  }
  function updateRings() {
    const ship = projection?.raw?.os; if (!ship) return;
    const visible = showRings && preset !== 'bridge';
    for (const radius of [NM / 2, NM]) {
      const id = `ring:${radius}`;
      if (visible && (!lastRingCenter || Math.hypot(ship.x - lastRingCenter.x, ship.y - lastRingCenter.y) > 0.25)) {
        line(id, Array.from({ length: 129 }, (_, i) => [ship.x + radius * Math.cos(i * Math.PI / 64), ship.y + radius * Math.sin(i * Math.PI / 64)]), '#b5e3e8', 1);
      }
      if (geometry.get(id)) geometry.get(id).show = visible;
    }
    if (visible) {
      for (let bearing = 0; bearing < 360; bearing += 30) {
        const angle = bearing * Math.PI / 180;
        const id = `bearing:${bearing}`;
        let entity = geometry.get(id);
        if (!entity) { entity = viewer.entities.add({ label: { text: `${bearing}°`, font: '12px sans-serif', fillColor: C.Color.WHITE, showBackground: true, disableDepthTestDistance: Infinity } }); geometry.set(id, entity); }
        entity.position = position(ship.x + NM * Math.cos(angle), ship.y + NM * Math.sin(angle), 2); entity.show = true;
      }
      for (const [radius, text] of [[NM / 2, '0.50 NM'], [NM, '1.00 NM']]) {
        const id = `range:${radius}`; let entity = geometry.get(id);
        if (!entity) { entity = viewer.entities.add({ label: { text, font: '13px sans-serif', fillColor: C.Color.WHITE, showBackground: true } }); geometry.set(id, entity); }
        entity.position = position(ship.x + radius, ship.y, 2); entity.show = true;
      }
      lastRingCenter = { x: ship.x, y: ship.y };
    } else for (const [id, entity] of geometry) if (/^(bearing|range):/.test(id)) entity.show = false;
  }
  function updatePaths() {
    const data = projection.raw, layers = Object.fromEntries(Object.entries(chart.getLayerState()).map(([id, item]) => [id, item.visible]));
    const key = `${data.seq}:${JSON.stringify(layers)}`;
    if (lastGeometryKey === key) return; lastGeometryKey = key;
    if (!lastRoute && data.waypoints?.length === 2) lastRoute = data.waypoints[0].map((n, i) => [n, data.waypoints[1][i]]);
    line('route', layers.route !== false ? lastRoute : [], '#137fd1', 3, true);
    line('history', layers.history !== false ? data.os?.trajectory : [], '#7e8991', 2);
    line('prediction', layers.prediction !== false ? data.plans?.prediction_horizon : [], '#e99819', 3);
    line('previous', layers.previousPrediction ? data.plans?.previous_prediction_horizon : [], '#a7a7a7', 1, true);
    const markers = layers.prediction !== false ? predictionMarkers(data) : [];
    for (const [id, entity] of geometry) if (id.startsWith('time:')) { viewer.entities.remove(entity); geometry.delete(id); }
    for (const marker of markers) {
      const id = `time:${marker.elapsed}`;
      geometry.set(id, viewer.entities.add({ position: position(...marker.point, 2),
        point: { pixelSize: 5, color: C.Color.ORANGE },
        label: { text: `+${marker.elapsed.toFixed(0)}s`, font: '12px sans-serif', fillColor: C.Color.WHITE, showBackground: true, pixelOffset: new C.Cartesian2(0, -15) } }));
    }
  }
  function projectPois() {
    if (disposed || !projection) return;
    const width = canvasHost.clientWidth, height = canvasHost.clientHeight;
    const wanted = new Set(), edgeLabels = [];
    for (const [key, record] of vessels) {
      const ship = record.ship; if (String(ship.id) === '0' || chart.getLayerState().ships?.visible === false) continue;
      const world = position(ship.x, ship.y, 3);
      const delta = C.Cartesian3.subtract(world, viewer.camera.positionWC, new C.Cartesian3());
      const ahead = C.Cartesian3.dot(delta, viewer.camera.directionWC) > viewer.camera.frustum.near;
      const point = ahead ? C.SceneTransforms.worldToWindowCoordinates(viewer.scene, world) : null;
      const visible = point && point.x >= 24 && point.x <= width - 24 && point.y >= 40 && point.y <= height - 16;
      const risk = riskForTarget(projection, ship);
      const primary = projection.risk?.primary;
      const focus = String(selected) === String(ship.id) || (String(primary?.targetId ?? primary?.target_id) === String(ship.id)
        && (primary?.generation ?? null) === (ship.generation ?? null));
      if (!visible) {
        if (focus) {
          const right = C.Cartesian3.dot(delta, viewer.camera.rightWC) >= 0;
          edgeLabels.push({ key, id: ship.id, text: `${ahead ? right ? '→' : '←' : '↶ 后方'} TS${ship.id}`, right });
        }
        continue;
      }
      wanted.add(key); let poi = pois.get(key);
      if (!poi) {
        poi = document.createElement('obc-poi-vessel'); poi.animatePosition = false;
        poi.hasHeader = true; poi.headerContent = String(ship.id); poi.hasPointer = true;
        poi.setAttribute('aria-label', `TS${ship.id} 目标详情`); poi.dataset.targetKey = key;
        poi.addEventListener('click', () => choose(ship.id));
        layer.append(poi); pois.set(key, poi);
      }
      const top = Math.max(72, Math.min(point.y - 65, height * 0.22));
      poi.x = point.x; poi.y = Math.max(20, point.y - top); poi.buttonY = top;
      poi.selected = String(selected) === String(ship.id); poi.vesselState = poiState(risk);
      poi.relativeDirection = degrees(ship.psi - projection.raw.os.psi) ?? 0;
      poi.title = `TS${ship.id} · ${risk?.displayClass || '不可用'} · DCPA ${metric(risk?.dcpaM)} m / TCPA ${metric(risk?.tcpaS)} s`;
    }
    for (const [key, poi] of pois) if (!wanted.has(key)) { poi.remove(); pois.delete(key); }
    const signature = JSON.stringify(edgeLabels);
    if (edges.dataset.signature !== signature) {
      edges.replaceChildren(...edgeLabels.map(item => {
        const button = document.createElement('button'); button.textContent = item.text; button.className = item.right ? 'right' : 'left';
        button.addEventListener('click', () => choose(item.id)); return button;
      })); edges.dataset.signature = signature;
    }
  }
  const renderSamples = [];
  let renderStarted = 0, framesTotal = 0, renderP95Ms = 0;
  const removePreRender = viewer.scene.preRender.addEventListener(() => { renderStarted = performance.now(); });
  const removePostRender = viewer.scene.postRender.addEventListener(() => {
    projectPois();
    for (const record of vessels.values()) {
      record.marker.show = chart.getLayerState().ships?.visible !== false && !record.model?.ready;
      if (record.model) record.model.show = chart.getLayerState().ships?.visible !== false && !(preset === 'bridge' && String(record.ship.id) === '0');
    }
    renderSamples.push(performance.now() - renderStarted);
    if (renderSamples.length > 600) renderSamples.shift();
    framesTotal += 1;
    if (framesTotal % 60 === 1) renderP95Ms = [...renderSamples].sort((a,b) => a-b)[Math.floor(renderSamples.length * 0.95)];
    root.dataset.sceneState = JSON.stringify({ models: vessels.size, readyModels: [...vessels.values()].filter(v => v.model?.ready).length,
      pois: pois.size, primitives: viewer.scene.primitives.length, camera: preset, frames: framesTotal,
      renderP95Ms });
  });
  const removeError = viewer.scene.renderError.addEventListener((_scene, error) => onFailure(error));
  listen(viewer.canvas, 'webglcontextlost', () => onFailure(new Error('WebGL 上下文丢失，已恢复海图')));
  const resize = new ResizeObserver(() => { if (!disposed) { viewer.resize(); viewer.scene.requestRender(); } }); resize.observe(canvasHost);
  function refreshTheme() {
    const name = document.documentElement.getAttribute('data-obc-theme');
    const dark = name === 'night' || name === 'dusk';
    viewer.scene.globe.baseColor = C.Color.fromCssColorString(dark ? '#162c36' : '#75aab5');
    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.brightnessShift = dark ? -0.65 : 0;
    viewer.scene.requestRender();
  }
  refreshTheme();
  const theme = new MutationObserver(refreshTheme); theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-obc-theme'] });
  return {
    render(value) {
      if (disposed || !value || value.raw.run_id !== info.run_id) return;
      projection = value;
      const ships = [value.raw.os, ...targetsForDisplay(value.raw)];
      updateVessels(ships); updatePaths(); updateCamera(); updateRings(); updateCard();
      const frame = frameIdentity(value.raw);
      root.dataset.frame = JSON.stringify(frame);
      const outside = !geo.contains(value.raw.os.x, value.raw.os.y);
      const planTime = value.raw.planner?.sim_time;
      const age = Number.isFinite(planTime) ? ` · 预测龄期 ${metric(Math.max(0, value.raw.sim_time - planTime))}s` : '';
      const failedModel = [...vessels.values()].some(v => v.failed);
      status.textContent = `仿真三维视景 · 示意眼点/船模 · ${metric(frame.renderTime, 1)} s${value.raw.presentation?.buffering ? ' · 缓冲中' : ''}${outside ? ' · 无海图覆盖' : ''}${failedModel ? ' · 船模不可用（位置标记）' : ''}${age} · 蓝虚线任务 / 橙线预测（非执行保证）`;
      if (encPrimitive) encPrimitive.show = chart.isEncVisible();
      viewer.scene.requestRender();
    },
    select(id) { selected = id; selectedKey = null; updateCard(); viewer.scene.requestRender(); },
    recenter() { follow = true; updateCamera(); viewer.scene.requestRender(); },
    zoom(direction) { follow = false; direction > 0 ? viewer.camera.zoomIn(50) : viewer.camera.zoomOut(50); viewer.scene.requestRender(); },
    destroy() {
      if (disposed) return; disposed = true;
      resize.disconnect(); theme.disconnect(); removePreRender(); removePostRender(); removeError(); handler.destroy();
      disposers.forEach(dispose => dispose()); pois.forEach(poi => poi.remove()); pois.clear();
      viewer.destroy(); root.remove(); vessels.clear(); geometry.clear();
    },
  };
}
