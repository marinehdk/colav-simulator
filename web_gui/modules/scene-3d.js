import { chooseVesselAsset, vesselModelMatrix, VESSEL_ASSETS } from './vessel-models.js?v=20260921-fcb-v1';
import { createGeography, NM, targetKey, riskForTarget, targetAlert, frameIdentity, predictionMarkers, offscreenDirection } from './scene-geography.js?v=20260923-follow-v1';
import { targetsForDisplay, RADAR_DETECTION_RANGE_M, drawVODecisionDisc } from './situation-display.js?v=20260923-vo-disc-v1';
import { createRoute3D } from './route-3d.js?v=20260921-route-ar-v1';
import { createSceneCompass } from './scene-compass.js?v=20260923-follow-v1';
import { targetPresentation, applyTargetAppearance, updateTargetPoi, renderTargetCard } from './scene-target.js?v=20260923-follow-v1';

let enginePromise;
export function voDiscRadiusM(length) {
  // Display scale for velocity space; it is not a safety or detection radius.
  return Number.isFinite(length) && length > 0 ? length * 3 : null;
}

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
      const timer = setTimeout(() => { script.remove(); enginePromise = null; reject(new Error('三维引擎加载超时，可重试')); }, 15000);
      script.onload = () => { clearTimeout(timer); resolve(window.Cesium); };
      script.onerror = () => { clearTimeout(timer); script.remove(); enginePromise = null; reject(new Error('三维引擎加载失败，可重试')); };
      document.head.append(script);
    });
  }
  return enginePromise;
}

const metric = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : '—';
const degrees = value => Number.isFinite(value) ? (value * 180 / Math.PI + 360) % 360 : null;

function waitForAsset(promise, signal, label) {
  return new Promise((resolve, reject) => {
    const cancel = () => finish(reject, new DOMException('已取消三维加载', 'AbortError'));
    const timer = setTimeout(() => finish(reject, new Error(`${label} 加载超时，可重试`)), 15000);
    function finish(action, value) { clearTimeout(timer); signal?.removeEventListener('abort', cancel); action(value); }
    if (signal?.aborted) { cancel(); return; }
    signal?.addEventListener('abort', cancel, { once: true });
    promise.then(value => finish(resolve, value), error => finish(reject, error));
  });
}

export async function createScene3D({ host, info, camera = 'chase', chart, onSelect, onFailure, onCamera, getPlannerSurface = () => null, requestVODecisionSpace = () => {}, signal, modelOverrides = new Map(), pixelRatio = null }) {
  const C = await waitForAsset(loadCesium(), signal, 'Cesium');
  const geo = createGeography(info);
  // OpenBridge is loaded by the existing shell; no second registration/bundle.
  await waitForAsset(Promise.all(['obc-poi-layer', 'obc-poi-vessel', 'obc-poi-card'].map(name => customElements.whenDefined(name))), signal, 'OpenBridge');
  signal?.throwIfAborted();
  const root = document.createElement('div'); root.className = 'scene3d-root';
  const canvasHost = document.createElement('div'); canvasHost.className = 'scene3d-canvas';
  const toolbar = document.createElement('div'); toolbar.className = 'scene3d-toolbar';
  toolbar.setAttribute('role', 'group'); toolbar.setAttribute('aria-label', '三维机位');
  const layer = document.createElement('obc-poi-layer'); layer.className = 'scene3d-pois'; layer.overlapMode = 'grouping';
  const edges = document.createElement('div'); edges.className = 'scene3d-edges';
  const card = document.createElement('obc-poi-card'); card.className = 'scene3d-card'; card.hidden = true;
  const cardBody = document.createElement('div'); cardBody.className = 'scene3d-card-body'; card.append(cardBody);
  const cardIcon = document.createElement('obi-vessel-generic-default-outlined'); cardIcon.slot = 'poi-icon'; card.append(cardIcon);
  const cardAlert = document.createElement('obc-alert-frame'); cardAlert.className = 'scene3d-card-alert'; cardAlert.type = 'regular'; cardAlert.thickness = 'large'; cardAlert.hidden = true; card.append(cardAlert);
  card.hasCloseButton = true;
  card.addEventListener('close-click', () => choose(null));
  const credits = document.createElement('div'); credits.className = 'scene3d-credits';
  root.append(canvasHost, layer, edges, toolbar, card, credits); host.append(root);
  C.CreditDisplay.cesiumCredit = undefined;
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
  // Camera follows a telemetry-defined eyepoint; scene geometry must not push it away.
  viewer.scene.screenSpaceCameraController.enableCollisionDetection = false;
  viewer.scene.screenSpaceCameraController.minimumZoomDistance = 2;
  viewer.scene.globe.baseColor = C.Color.fromCssColorString('#75aab5');
  viewer.scene.globe.enableLighting = false;
  viewer.scene.globe.depthTestAgainstTerrain = false;
  const applyResolution = () => { viewer.resolutionScale = pixelRatio ?? Math.min(window.devicePixelRatio || 1, 2); };
  applyResolution();
  let disposed = false, projection = null, preset = camera, follow = true;
  let selected = chart.getSelectedTargetId(), selectedKey = null, encPrimitive = null;
  let lastGeometryKey = null, lastRingCenter = null, lastVODiscKey = null, voPrimitive = null, voRadiusM = null, voCenter = null;
  let voMaterial = null, voAnchor = null;
  const vessels = new Map(), pois = new Map(), geometry = new Map(), linePoints = new Map();
  const disposers = [];
  function listen(el, event, fn) { el.addEventListener(event, fn); disposers.push(() => el.removeEventListener(event, fn)); }
  function position(n, e, h = 0) { const [lon, lat] = geo.lonLat(n, e); return C.Cartesian3.fromDegrees(lon, lat, h); }
  const routeDisplay = createRoute3D({ C, viewer, host: root, position });
  const compass = createSceneCompass({ host: root, onSelect: choose });
  // Illustrative daylight, independent of wall-clock sunlight at the scenario longitude.
  const lightFrame = C.Transforms.eastNorthUpToFixedFrame(position(info.height / 2, info.width / 2));
  const lightDirection = C.Matrix4.multiplyByPointAsVector(lightFrame, new C.Cartesian3(-0.6, 0.7, -1), new C.Cartesian3());
  C.Cartesian3.normalize(lightDirection, lightDirection);
  viewer.scene.light = new C.DirectionalLight({ direction: lightDirection, intensity: 2.1 });
  function setOwnshipLighting(model) {
    const dark = ['night', 'dusk'].includes(document.documentElement.getAttribute('data-obc-theme'));
    model.imageBasedLighting.imageBasedLightingFactor = new C.Cartesian2(1, 0.4);
    model.imageBasedLighting.sphericalHarmonicCoefficients = Array.from({length: 9}, (_, index) => {
      const value = index === 0 ? (dark ? 0.25 : 0.8) : 0;
      return new C.Cartesian3(value, value, value);
    });
  }
  function line(id, coordinates, color, width = 2, dashed = false) {
    const points = (coordinates || []).filter(p => p?.length >= 2 && p.slice(0, 2).every(Number.isFinite)).map(p => position(p[0], p[1], 0.8));
    if (points.length < 2) { const old = geometry.get(id); if (old) viewer.entities.remove(old); geometry.delete(id); linePoints.delete(id); return; }
    linePoints.set(id, points);
    let entity = geometry.get(id);
    if (!entity) {
      // Streamed paths must bypass asynchronous static-geometry rebuilds, which
      // can keep displaying an old line while point/label entities already update.
      entity = viewer.entities.add({ polyline: { positions: new C.CallbackProperty(() => linePoints.get(id), false), width,
        material: dashed ? new C.PolylineDashMaterialProperty({ color: C.Color.fromCssColorString(color), dashLength: id === 'route' ? 28 : 16 }) : C.Color.fromCssColorString(color),
        arcType: C.ArcType.NONE } });
      geometry.set(id, entity);
    }
  }
  // A sampled UTM mesh, not a four-corner geographic rectangle.
  function addEnc() {
    const mesh = createEncGeometry(C, geo);
    encPrimitive = viewer.scene.primitives.add(new C.Primitive({
      geometryInstances: new C.GeometryInstance({ geometry: mesh }), asynchronous: false,
      appearance: new C.MaterialAppearance({ material: C.Material.fromType('Image', { image: info.tile_url || `/api/enc_tile?run_id=${encodeURIComponent(info.run_id)}` }),
        translucent: false, closed: false, faceForward: true }),
    }));
  }
  try { addEnc(); } catch (error) { viewer.destroy(); root.remove(); throw error; }
  function vesselMatrix(ship, asset) {
    return vesselModelMatrix(C, position(ship.x, ship.y, 0.1), geo.heading(ship.x, ship.y, ship.psi ?? 0), ship, asset);
  }
  function updateVessels(ships) {
    const wanted = new Set();
    for (const ship of ships) {
      if (ship.active === false || ![ship.x, ship.y].every(Number.isFinite)) continue;
      const key = targetKey(info.run_id, ship); wanted.add(key);
      const choice = chooseVesselAsset(ship, modelOverrides.get(key));
      let record = vessels.get(key);
      if (record && record.asset.id !== choice.asset.id) {
        if (record.model) viewer.scene.primitives.remove(record.model);
        viewer.entities.remove(record.marker); vessels.delete(key); record = null;
      }
      if (!record) {
        record = { ship, model: null, asset: choice.asset, assignment: choice.reason }; vessels.set(key, record);
        C.Model.fromGltfAsync({ upAxis: C.Axis.Y, forwardAxis: C.Axis.X, url: choice.asset.url, modelMatrix: C.Transforms.eastNorthUpToFixedFrame(position(ship.x, ship.y, 0.1)),
          id: { targetId: ship.id }, color: C.Color.WHITE,
        }).then(model => {
          if (disposed || vessels.get(key) !== record) { model.destroy(); return; }
          // Keep assets hidden until their resources and current telemetry transform are ready.
          if (record.asset.id === 'fcb45') setOwnshipLighting(model);
          model.show = false;
          record.model = viewer.scene.primitives.add(model);
          model.readyEvent.addEventListener(() => {
            if (disposed || vessels.get(key) !== record) return;
            model.modelMatrix = vesselMatrix(record.ship, record.asset);
            model.show = chart.getLayerState().ships?.visible !== false && !(preset === 'bridge' && String(record.ship.id) === '0');
            viewer.scene.requestRender();
          });
          viewer.scene.requestRender();
        }).catch(() => { if (!disposed && vessels.get(key) === record) record.failed = true; });
        const marker = String(ship.id) === '0'
          ? { point: { pixelSize: 7, color: C.Color.WHITE } }
          : { billboard: { image: '/static/assets/target-position-marker.svg', width: 32, height: 32,
            disableDepthTestDistance: Infinity } };
        record.marker = viewer.entities.add({ position: position(ship.x, ship.y, 1), ...marker, id: `fallback:${key}` });
        record.marker.addProperty('targetId'); record.marker.targetId = ship.id;
      }
      record.ship = ship;
      record.assignment = choice.reason;
      record.marker.position = position(ship.x, ship.y, 1);
      if (record.marker.billboard) record.marker.billboard.color = C.Color.fromCssColorString(targetAlert(projection, ship).color);
      record.marker.show = chart.getLayerState().ships?.visible !== false
        && (String(ship.id) !== '0' || !record.model?.ready);
      if (record.model?.ready) record.model.modelMatrix = vesselMatrix(ship, record.asset);
    }
    for (const [key, record] of vessels) if (!wanted.has(key)) {
      if (record.model) viewer.scene.primitives.remove(record.model);
      viewer.entities.remove(record.marker); vessels.delete(key);
    }
  }
  function setCamera(value) {
    preset = value; follow = true; lastRingCenter = null; onCamera(value); updateCamera(); updateRings();
    if (voEntity) voEntity.ellipse.material.color = new C.Color(1, 1, 1, value === 'bridge' ? 0.28 : 0.42);
    compass.render(projection, preset, chart.getLayerState().ships?.visible !== false);
    toolbar.querySelectorAll('[data-camera]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.camera === preset)));
    viewer.scene.requestRender();
  }
  for (const [value, text] of [['bridge', '舰桥'], ['chase', '追随'], ['top', '俯视']]) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = text;
    button.dataset.camera = value; button.setAttribute('aria-pressed', String(value === preset));
    listen(button, 'click', () => setCamera(value)); toolbar.append(button);
  }
  const modelLabel = document.createElement('label'); modelLabel.className = 'scene3d-model-choice';
  modelLabel.textContent = '显示外观（不改船型/动力学）';
  const modelChoice = document.createElement('select'); modelChoice.setAttribute('aria-label', '目标船显示外观');
  const automatic = document.createElement('option'); automatic.value = ''; automatic.textContent = '自动 / 通用外观'; modelChoice.append(automatic);
  for (const asset of Object.values(VESSEL_ASSETS)) if (asset.id !== 'fcb45') {
    const option = document.createElement('option'); option.value = asset.id; option.textContent = asset.label; modelChoice.append(option);
  }
  const modelDetails = document.createElement('details'); modelDetails.className = 'scene3d-model-settings';
  const modelSummary = document.createElement('summary'); modelSummary.textContent = '船模外观';
  modelLabel.append(modelChoice); modelDetails.append(modelSummary, modelLabel); card.append(modelDetails);
  listen(modelChoice, 'change', () => {
    if (!selectedKey || !projection) return;
    if (modelChoice.value) modelOverrides.set(selectedKey, modelChoice.value); else modelOverrides.delete(selectedKey);
    updateVessels([projection.raw.os, ...targetsForDisplay(projection.raw)]); updateCard(); viewer.scene.requestRender();
  });
  function updateCamera() {
    const ship = projection?.raw?.os;
    if (!ship || !follow) return;
    const heading = geo.heading(ship.x, ship.y, ship.psi);
    const length = ship.length || 45;
    if (preset === 'bridge') {
      const eye = position(ship.x - Math.cos(ship.psi) * length * 0.2, ship.y - Math.sin(ship.psi) * length * 0.2, Math.max(9, (ship.width || 10) * 1.1));
      viewer.camera.setView({ destination: eye, orientation: { heading, pitch: -0.025, roll: 0 } });
    } else {
      const range = preset === 'top' ? 2500 : Math.max(120, Math.min(700, length * 9));
      const tilt = preset === 'top' ? -Math.PI / 2 + 0.001 : -0.25;
      const lookAhead = preset === 'chase' ? length * 3.4 : 0;
      viewer.camera.lookAt(position(ship.x + Math.cos(ship.psi) * lookAhead,
        ship.y + Math.sin(ship.psi) * lookAhead), new C.HeadingPitchRange(heading, tilt, range));
      viewer.camera.lookAtTransform(C.Matrix4.IDENTITY);
    }
    // The bridge eyepoint is illustrative; hide its hull to avoid a false occlusion.
    const own = vessels.get(targetKey(info.run_id, { id: 0 }));
    if (own?.model) own.model.show = preset !== 'bridge';
  }
  for (const event of ['mousedown', 'pointerdown', 'click', 'wheel']) listen(root, event, event => event.stopPropagation());
  let pointerStart = null;
  listen(viewer.canvas, 'pointerdown', event => { pointerStart = { x: event.clientX, y: event.clientY }; });
  listen(viewer.canvas, 'pointermove', event => { if (pointerStart && Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 4) follow = false; });
  for (const event of ['pointerup', 'pointercancel', 'pointerleave']) listen(viewer.canvas, event, () => { pointerStart = null; });
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
    const value = picked?.id?.targetId;
    const id = typeof value?.getValue === 'function' ? value.getValue(viewer.clock.currentTime) : value;
    if (id !== undefined) choose(id);
  }, C.ScreenSpaceEventType.LEFT_CLICK);
  function updateCard() {
    const record = [...vessels.values()].find(v => String(v.ship.id) === String(selected));
    if (!record || (selectedKey && targetKey(info.run_id, record.ship) !== selectedKey)) {
      card.hidden = true; if (selected !== null) { selected = null; selectedKey = null; onSelect(null); } return;
    }
    const ship = record.ship;
    selectedKey = targetKey(info.run_id, ship);
    const model = targetPresentation(projection, ship);
    card.cardTitle = String(ship.id) === '0' ? 'OWN SHIP' : ship.name || `TS${ship.id}`;
    card.index = String(ship.id); card.source = projection.raw.executed_tracker === 'god' ? 'GOD' : 'TRACK';
    card.description = `${metric(ship.length)} × ${metric(ship.width)} m`; card.headerVariant = 'detailed';
    applyTargetAppearance(card, model.alert);
    cardAlert.status = model.alert.poiState;
    cardAlert.hidden = !['caution', 'alarm'].includes(model.alert.poiState);
    modelDetails.hidden = String(ship.id) === '0';
    modelChoice.value = modelOverrides.get(selectedKey) || '';
    renderTargetCard(cardBody, model);
    card.hidden = false;
  }
  function updateRings() {
    const ship = projection?.raw?.os; if (!ship) return;
    const visible = chart.getLayerState().radarRange?.visible !== false;
    const radius = RADAR_DETECTION_RANGE_M, id = 'detection-ring';
    const needsUpdate = !lastRingCenter || Math.hypot(ship.x - lastRingCenter.x, ship.y - lastRingCenter.y) > 0.25;
    if (visible && needsUpdate) {
      line(id, Array.from({ length: 257 }, (_, i) => [ship.x + radius * Math.cos(i * Math.PI / 128), ship.y + radius * Math.sin(i * Math.PI / 128)]), '#d4e9ee', 1.5);
      lastRingCenter = { x: ship.x, y: ship.y };
    }
    if (geometry.get(id)) geometry.get(id).show = visible;
  }
  function updatePaths() {
    const data = projection.raw, layers = Object.fromEntries(Object.entries(chart.getLayerState()).map(([id, item]) => [id, item.visible]));
    const key = `${data.seq}:${JSON.stringify(layers)}`;
    if (lastGeometryKey === key) return; lastGeometryKey = key;
    const route = chart.getMissionRoute();
    routeDisplay.update(route, layers);
    const mission = route[0].map((north, i) => [north, route[1][i]]);
    line('route', layers.route !== false ? mission : [], '#137fd1', 3, true);
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
  function updateVODecisionSea() {
    const ship = projection?.raw?.os;
    const plannerSurface = getPlannerSurface();
    const vo = plannerSurface?.type === 'vo' ? plannerSurface.vo : null;
    if (!vo || !ship || ![ship.x, ship.y].every(Number.isFinite)) {
      if (voPrimitive) voPrimitive.show = false;
      return;
    }
    const radiusM = voDiscRadiusM(ship.length);
    if (radiusM === null) {
      if (voPrimitive) voPrimitive.show = false;
      return;
    }
    const key = `${info.run_id}:${vo.solve_id}`;
    if (key !== lastVODiscKey || voRadiusM !== radiusM) {
      const texture = document.createElement('canvas');
      texture.width = 720;
      texture.height = 720;
      const surface = texture.getContext('2d');
      surface.setTransform(3, 0, 0, 3, 0, 0);
      surface.clearRect(0, 0, 240, 240);
      const heading = Number(vo.ownship_heading_rad) || 0;
      if (!drawVODecisionDisc(surface, vo, 120, 120, 110, heading, heading)) {
        if (voPrimitive) voPrimitive.show = false;
        return;
      }
      if (!voPrimitive || voRadiusM !== radiusM) {
        if (voPrimitive) viewer.scene.primitives.remove(voPrimitive);
        voAnchor = position(ship.x, ship.y, 0.8);
        voCenter = { x: ship.x, y: ship.y };
        voMaterial = C.Material.fromType('Image', {
          image: texture,
          color: new C.Color(1, 1, 1, preset === 'bridge' ? 0.28 : 0.42),
        });
        // A stable primitive avoids the entity ellipse's asynchronous rebatch
        // on every VO solve; only its texture and transform change afterwards.
        voPrimitive = viewer.scene.primitives.add(new C.Primitive({
          geometryInstances: new C.GeometryInstance({ geometry: new C.EllipseGeometry({
            center: voAnchor, semiMajorAxis: radiusM, semiMinorAxis: radiusM, height: 0.8,
            vertexFormat: C.MaterialAppearance.VERTEX_FORMAT,
          }) }),
          appearance: new C.MaterialAppearance({ material: voMaterial, translucent: true, closed: false }),
          asynchronous: false,
          allowPicking: false,
        }));
        voRadiusM = radiusM;
      } else {
        // Update the primitive's texture without invalidating its geometry.
        voMaterial.uniforms.image = texture;
      }
      lastVODiscKey = key;
    }
    if (!voCenter || voCenter.x !== ship.x || voCenter.y !== ship.y) {
      const delta = C.Cartesian3.subtract(position(ship.x, ship.y, 0.8), voAnchor, new C.Cartesian3());
      voPrimitive.modelMatrix = C.Matrix4.fromTranslation(delta);
      voCenter = { x: ship.x, y: ship.y };
    }
    const opacity = preset === 'bridge' ? 0.28 : 0.42;
    if (voMaterial.uniforms.color.alpha !== opacity) {
      voMaterial.uniforms.color = new C.Color(1, 1, 1, opacity);
    }
    voPrimitive.show = true;
  }
  function projectPois() {
    if (disposed || !projection) return;
    const width = canvasHost.clientWidth, height = canvasHost.clientHeight;
    const layerHeight = layer.getBoundingClientRect().height;
    const wanted = new Set(), edgeLabels = [];
    const frustum = viewer.camera.frustum.computeCullingVolume(viewer.camera.positionWC, viewer.camera.directionWC, viewer.camera.upWC);
    const occluder = new C.EllipsoidalOccluder(C.Ellipsoid.WGS84, viewer.camera.positionWC);
    routeDisplay.project(frustum, occluder, width, height);
    for (const [key, record] of vessels) {
      const ship = record.ship; if (String(ship.id) === '0' || chart.getLayerState().ships?.visible === false) continue;
      const world = position(ship.x, ship.y, 3);
      const delta = C.Cartesian3.subtract(world, viewer.camera.positionWC, new C.Cartesian3());
      const ahead = C.Cartesian3.dot(delta, viewer.camera.directionWC) > viewer.camera.frustum.near;
      const inFrustum = frustum.computeVisibility(new C.BoundingSphere(world, 0)) !== C.Intersect.OUTSIDE;
      const projected = ahead ? C.SceneTransforms.worldToWindowCoordinates(viewer.scene, world) : null;
      const point = ahead && inFrustum && occluder.isPointVisible(world) ? projected : null;
      const visible = point && point.x >= 24 && point.x <= width - 24 && point.y >= 40 && point.y <= height - 16;
      const risk = riskForTarget(projection, ship);
      const primary = projection.risk?.primary;
      const focus = String(selected) === String(ship.id) || (String(primary?.targetId ?? primary?.target_id) === String(ship.id)
        && (primary?.generation ?? null) === (ship.generation ?? null));
      if (!visible) {
        if (focus) {
          const right = C.Cartesian3.dot(delta, viewer.camera.rightWC) >= 0;
          const direction = offscreenDirection(projected, width, height, ahead, right);
          edgeLabels.push({ key, id: ship.id, text: `${direction.arrow} TS${ship.id}`, edge: direction.edge,
            alert: targetPresentation(projection, ship).alert });
        }
        continue;
      }
      wanted.add(key); let poi = pois.get(key);
      if (!poi) {
        poi = document.createElement('obc-poi-vessel'); poi.animatePosition = false;
        const icon = document.createElement('obi-vessel-generic-default-outlined'); poi.append(icon);
        poi.hasHeader = true; poi.headerContent = String(ship.id); poi.hasPointer = true;
        poi.setAttribute('aria-label', `TS${ship.id} 目标详情`); poi.dataset.targetKey = key;
        poi.addEventListener('click', () => choose(ship.id));
        layer.append(poi); pois.set(key, poi);
      }
      const compassElement = root.querySelector('.scene3d-compass');
      const topInset = compassElement && !compassElement.hidden ? compassElement.offsetHeight + 16 : 20;
      const model = targetPresentation(projection, ship);
      const available = point.y - topInset;
      const blocks = available >= 320 ? model.blocks : available >= 180 ? [model.blocks[1]] : [];
      if (updateTargetPoi(poi, { ...model, blocks })) poi.updateComplete.then(() => requestAnimationFrame(() => { if (!disposed) viewer.scene.requestRender(); }));
      const cardHeight = poi.getVisualRect('size').height || (blocks.length ? blocks.length * 64 + 80 : 48);
      const lineLength = Math.min(72, Math.max(0, point.y - topInset - cardHeight - 12));
      // OpenBridge offsets targets by its layer height. Keep the native pointer
      // on the same projected point as the vessel's Cesium position marker.
      poi.x = Math.round(point.x * 2) / 2;
      poi.y = Math.round(lineLength * 2) / 2;
      poi.buttonY = Math.round((point.y - layerHeight - lineLength) * 2) / 2;
      poi.selected = String(selected) === String(ship.id);
      poi.relativeDirection = degrees(ship.psi - projection.raw.os.psi) ?? 0;
      const title = `TS${ship.id} · ${risk?.displayClass || '不可用'} · DCPA ${metric(risk?.dcpaM)} m / TCPA ${metric(risk?.tcpaS)} s`;
      if (poi.title !== title) poi.title = title;
    }
    for (const [key, poi] of pois) if (!wanted.has(key)) { poi.remove(); pois.delete(key); }
    const signature = JSON.stringify(edgeLabels);
    if (edges.dataset.signature !== signature) {
      const counts = {};
      edges.replaceChildren(...edgeLabels.map(item => {
        const button = document.createElement('button'); button.textContent = item.text; button.className = item.edge;
        applyTargetAppearance(button, item.alert); button.style.borderColor = item.alert.color; button.style.color = item.alert.color;
        if (['caution', 'alarm'].includes(item.alert.poiState)) {
          const alertFrame = document.createElement('obc-alert-frame'); alertFrame.type = 'regular'; alertFrame.status = item.alert.poiState;
          alertFrame.style.pointerEvents = 'none'; button.append(alertFrame);
        }
        const index = counts[item.edge] || 0; counts[item.edge] = index + 1;
        button.style.setProperty('--edge-index', index);
        button.addEventListener('click', () => choose(item.id)); return button;
      })); edges.dataset.signature = signature;
    }
  }
  const renderSamples = [];
  let renderStarted = 0, framesTotal = 0, renderP95Ms = 0;
  const removePreRender = viewer.scene.preRender.addEventListener(() => { renderStarted = performance.now(); });
  listen(layer, 'keydown', event => { if (event.key === 'Escape') layer.querySelectorAll('obc-poi-group').forEach(group => { group.expand = false; }); });
  const removePostRender = viewer.scene.postRender.addEventListener(() => {
    projectPois();
    for (const record of vessels.values()) {
      record.marker.show = chart.getLayerState().ships?.visible !== false
        && (String(record.ship.id) !== '0' || !record.model?.ready);
      if (record.model?.ready) record.model.show = chart.getLayerState().ships?.visible !== false && !(preset === 'bridge' && String(record.ship.id) === '0');
    }
    renderSamples.push(performance.now() - renderStarted);
    if (renderSamples.length > 600) renderSamples.shift();
    framesTotal += 1;
    if (framesTotal % 60 === 1) renderP95Ms = [...renderSamples].sort((a,b) => a-b)[Math.floor(renderSamples.length * 0.95)];
    root.dataset.sceneState = JSON.stringify({ models: vessels.size, readyModels: [...vessels.values()].filter(v => v.model?.ready).length,
      pois: pois.size, primitives: viewer.scene.primitives.length, camera: preset, frames: framesTotal,
      cameraRangeM: projection?.raw?.os ? C.Cartesian3.distance(viewer.camera.positionWC, position(projection.raw.os.x, projection.raw.os.y)) : null,
      voDecision: voPrimitive?.show ? { solveId: Number(lastVODiscKey?.split(':').at(-1)), radiusM: voRadiusM } : null,
      modelDimensions: [...vessels.values()].map(v => ({id: v.ship.id, length:v.ship.length, beam:v.ship.width, asset:v.asset.id, radius:v.model?.ready?v.model.boundingSphere.radius:null})),
      renderP95Ms });
  });
  const removeError = viewer.scene.renderError.addEventListener((_scene, error) => onFailure(error));
  listen(viewer.canvas, 'webglcontextlost', () => onFailure(new Error('WebGL 上下文丢失，已恢复海图')));
  const resize = new ResizeObserver(() => { if (!disposed) { applyResolution(); viewer.resize(); viewer.scene.requestRender(); } }); resize.observe(canvasHost);
  function refreshTheme() {
    const name = document.documentElement.getAttribute('data-obc-theme');
    const dark = name === 'night' || name === 'dusk';
    viewer.scene.globe.baseColor = C.Color.fromCssColorString(dark ? '#162c36' : '#75aab5');
    viewer.scene.light.intensity = dark ? 0.7 : 2.1;
    for (const record of vessels.values()) if (record.asset.id === 'fcb45' && record.model) setOwnshipLighting(record.model);
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
      updateVessels(ships); updatePaths(); updateCamera(); updateRings(); updateVODecisionSea(); updateCard();
      requestVODecisionSpace();
      compass.render(value, preset, chart.getLayerState().ships?.visible !== false);
      const frame = frameIdentity(value.raw);
      root.dataset.frame = JSON.stringify(frame);
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
      compass.destroy(); routeDisplay.destroy(); viewer.destroy(); root.remove(); vessels.clear(); geometry.clear(); linePoints.clear();
    },
  };
}

export function createEncGeometry(C, geo) {
  const info = geo.info;
    const count = 32, vertices = [], normals = [], st = [], indices = [];
    for (let row = 0; row <= count; row++) for (let col = 0; col <= count; col++) {
      const p = C.Cartesian3.fromDegrees(...geo.lonLat(info.height * row / count, info.width * col / count), 0.1);
      vertices.push(p.x, p.y, p.z);
      const normal = C.Ellipsoid.WGS84.geodeticSurfaceNormal(p);
      normals.push(normal.x, normal.y, normal.z); st.push(col / count, row / count);
      if (row < count && col < count) {
        const i = row * (count + 1) + col;
        indices.push(i, i + 1, i + count + 1, i + 1, i + count + 2, i + count + 1);
      }
    }
    return new C.Geometry({ attributes: {
      position: new C.GeometryAttribute({ componentDatatype: C.ComponentDatatype.DOUBLE, componentsPerAttribute: 3, values: new Float64Array(vertices) }),
      normal: new C.GeometryAttribute({ componentDatatype: C.ComponentDatatype.FLOAT, componentsPerAttribute: 3, values: new Float32Array(normals) }),
      st: new C.GeometryAttribute({ componentDatatype: C.ComponentDatatype.FLOAT, componentsPerAttribute: 2, values: new Float32Array(st) }),
    }, indices: new Uint16Array(indices), primitiveType: C.PrimitiveType.TRIANGLES, boundingSphere: C.BoundingSphere.fromVertices(vertices) });
}
