import { routeCorridorBoundaries, validRoute, waypointLabel } from './situation-display.js?v=20261004-token-cleanup-v1';

export function routeRibbonQuads(route) {
  if (!validRoute(route) || !route[0].every(Number.isFinite) || !route[1].every(Number.isFinite)) return [];
  const { port, starboard } = routeCorridorBoundaries(route);
  return port.slice(1).flatMap((point, i) => {
    if (route[0][i] === route[0][i + 1] && route[1][i] === route[1][i + 1]) return [];
    return [[port[i], point, starboard[i + 1], starboard[i]]];
  });
}

// Route areas live in world space; waypoint heads and leaders live in screen space.
export function createRoute3D({ C, viewer, host, position }) {
  const overlay = document.createElement('div'); overlay.className = 'scene3d-waypoints'; host.append(overlay);
  let signature = null, showWaypoints = false;
  const surfaces = [], waypoints = [];
  function clear() {
    surfaces.splice(0).forEach(entity => viewer.entities.remove(entity));
    waypoints.splice(0).forEach(item => { viewer.entities.remove(item.ground); item.element.remove(); });
  }
  return {
    update(route, layers) {
      const key = JSON.stringify(route);
      showWaypoints = layers.waypoints !== false;
      if (key !== signature) {
        clear(); signature = key;
        const quads = routeRibbonQuads(route);
        for (const quad of quads) surfaces.push(viewer.entities.add({ polygon: {
          hierarchy: new C.PolygonHierarchy(quad.map(p => position(p.north, p.east))),
          height: 0.6, granularity: 50 / C.Ellipsoid.WGS84.maximumRadius,
          material: C.Color.fromCssColorString('#77bdff').withAlpha(0.30),
        } }));
        if (quads.length) route[0].forEach((north, i) => {
          const world = position(north, route[1][i], 1.2);
          const ground = viewer.entities.add({ position: world, ellipse: {
            semiMajorAxis: 12, semiMinorAxis: 12, height: 1.2,
            material: C.Color.fromCssColorString('#006bd6').withAlpha(0.30),
            outline: true, outlineColor: C.Color.fromCssColorString('#006bd6'),
          } });
          const element = document.createElement('div'); element.className = 'scene3d-waypoint'; element.hidden = true;
          element.setAttribute('aria-label', `${waypointLabel(i)} 航点`);
          const leader = document.createElement('div'); leader.className = 'scene3d-waypoint-leader';
          const head = document.createElement('div'); head.className = 'scene3d-waypoint-head';
          const label = document.createElement('span'); label.className = 'scene3d-waypoint-label'; label.textContent = waypointLabel(i);
          const icon = document.createElement('span'); icon.className = 'scene3d-waypoint-icon';
          head.append(label, icon); element.append(leader, head); overlay.append(element);
          waypoints.push({ world, ground, element });
        });
      }
      surfaces.forEach(entity => { entity.show = layers.route !== false; });
      waypoints.forEach(item => { item.ground.show = showWaypoints; if (!showWaypoints) item.element.hidden = true; });
    },
    project(frustum, occluder, width, height) {
      const placed = [];
      for (const item of waypoints) {
        const delta = C.Cartesian3.subtract(item.world, viewer.camera.positionWC, new C.Cartesian3());
        const ahead = C.Cartesian3.dot(delta, viewer.camera.directionWC) > viewer.camera.frustum.near;
        const inView = ahead && showWaypoints && occluder.isPointVisible(item.world)
          && frustum.computeVisibility(new C.BoundingSphere(item.world, 0)) !== C.Intersect.OUTSIDE;
        const point = inView ? C.SceneTransforms.worldToWindowCoordinates(viewer.scene, item.world) : null;
        const visible = point && point.x >= 36 && point.x <= width - 36 && point.y >= 64 && point.y <= height - 8;
        item.element.hidden = !visible;
        if (!visible) continue;
        let lift = 92;
        // Stagger heads when several waypoints converge near the horizon.
        while (placed.some(p => Math.abs(p.x - point.x) < 64 && Math.abs(p.y - (point.y - lift)) < 52)
          && point.y - lift > 112) lift += 52;
        lift = Math.min(lift, point.y - 48);
        placed.push({ x: point.x, y: point.y - lift });
        item.element.style.left = `${Math.round(point.x * 2) / 2}px`;
        item.element.style.top = `${Math.round(point.y * 2) / 2}px`;
        item.element.style.setProperty('--waypoint-lift', `${lift}px`);
      }
    },
    destroy() { clear(); overlay.remove(); },
  };
}
