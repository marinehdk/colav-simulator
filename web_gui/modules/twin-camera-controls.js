/** Direct orbit/pan/dolly controls for the streamed viewport. Commands use the
 * existing camera_free channel; no second renderer or clock is created. */
export function createTwinCameraControls({ video, getClient, getOwnship, getCameraPose = () => null,
  enabled = () => true, scheduler = globalThis, onSend = () => {} }) {
  let orbit = null, pointer = null, pending = false, destroyed = false;
  const listeners = [];
  const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
  const radians = Math.PI / 180;
  function initialize() {
    if (orbit) return true;
    const ship = getOwnship();
    if (!ship || ![ship.east, ship.north].every(Number.isFinite)) return false;
    const pose = getCameraPose();
    if (pose && [pose.east, pose.north, pose.height_m, pose.yaw_deg, pose.pitch_deg].every(Number.isFinite)) {
      const yaw = pose.yaw_deg * radians, pitch = clamp(pose.pitch_deg, -85, -.1) * radians;
      const range = clamp((pose.height_m - 3) / -Math.sin(pitch), 10, 5000);
      orbit = { east: pose.east + Math.sin(yaw) * Math.cos(pitch) * range,
        north: pose.north + Math.cos(yaw) * Math.cos(pitch) * range,
        height: pose.height_m + Math.sin(pitch) * range, yaw, pitch, range, fov: pose.fov_deg || 60 };
    } else {
      orbit = { east: ship.east, north: ship.north, height: 3,
        yaw: ship.psi || 0, pitch: -26.6 * radians, range: Math.max(80, (ship.length || 45) * 6), fov: 60 };
    }
    return true;
  }
  function canControl() { return !destroyed && enabled() && getClient()?.attached && initialize(); }
  function flush() {
    if (!pending || !canControl()) return;
    pending = false;
    const horizontal = Math.cos(orbit.pitch) * orbit.range;
    const pose = { east: orbit.east - Math.sin(orbit.yaw) * horizontal,
      north: orbit.north - Math.cos(orbit.yaw) * horizontal,
      height_m: clamp(orbit.height - Math.sin(orbit.pitch) * orbit.range, 1, 5000),
      yaw_deg: orbit.yaw / radians, pitch_deg: orbit.pitch / radians, fov_deg: orbit.fov };
    getClient().sendCameraFree(pose); onSend(pose);
  }
  function consume(event) { event.preventDefault?.(); event.stopPropagation?.(); }
  function down(event) {
    if (![0, 1, 2].includes(event.button) || !canControl()) return;
    consume(event);
    pointer = { id: event.pointerId, x: event.clientX, y: event.clientY,
      pan: event.button === 0,
      zoom: event.button === 2, moved: false };
    video.setPointerCapture?.(event.pointerId);
  }
  function move(event) {
    if (!pointer || pointer.id !== event.pointerId || !canControl()) return;
    consume(event);
    const previousX = pointer.x, previousY = pointer.y;
    const dx = event.clientX - previousX, dy = event.clientY - previousY;
    pointer.moved ||= dx !== 0 || dy !== 0;
    pointer.x = event.clientX; pointer.y = event.clientY;
    if (pointer.zoom) orbit.range = clamp(orbit.range * Math.exp(dy * 0.01), 10, 5000);
    else if (pointer.pan) {
      const height = video.getBoundingClientRect?.().height || 900;
      const scale = 2 * orbit.range * Math.tan(orbit.fov * radians / 2) / height;
      // Intersect both cursor rays with the sea plane: the grabbed point follows
      // the cursor even at shallow viewing angles, without overshooting the ship.
      const rect = video.getBoundingClientRect?.() || { width: 1600, height, left: 0, top: 0 };
      const ground = (x, y) => {
        const sx = (x - (rect.left || 0) - rect.width / 2) * 2 * Math.tan(orbit.fov * radians / 2) / height;
        const sy = -(y - (rect.top || 0) - height / 2) * 2 * Math.tan(orbit.fov * radians / 2) / height;
        const rayY = Math.sin(orbit.pitch) + sy * Math.cos(orbit.pitch);
        if (rayY >= -.01) return null;
        const distance = Math.sin(orbit.pitch) * orbit.range / rayY;
        const forward = Math.cos(orbit.pitch) - sy * Math.sin(orbit.pitch);
        return { east: (Math.sin(orbit.yaw) * forward + Math.cos(orbit.yaw) * sx) * distance,
          north: (Math.cos(orbit.yaw) * forward - Math.sin(orbit.yaw) * sx) * distance };
      };
      const from = ground(previousX, previousY), to = ground(event.clientX, event.clientY);
      if (from && to) { orbit.east += from.east - to.east; orbit.north += from.north - to.north; }
      else {
        const groundY = dy / Math.max(.25, -Math.sin(orbit.pitch));
        orbit.east += (-Math.cos(orbit.yaw) * dx + Math.sin(orbit.yaw) * groundY) * scale;
        orbit.north += (Math.sin(orbit.yaw) * dx + Math.cos(orbit.yaw) * groundY) * scale;
      }
    } else {
      orbit.yaw -= dx * 0.005;
      orbit.pitch = clamp(orbit.pitch + dy * 0.005, -85 * radians, -2 * radians);
    }
    pending = true;
  }
  function up(event) {
    if (!pointer || pointer.id !== event.pointerId) return;
    flush();
    if (!pointer.moved) orbit = null; // a click must not cache a moving tracking camera
    try { video.releasePointerCapture?.(pointer.id); } catch { /* capture already lost */ }
    pointer = null;
  }
  function zoom(delta) { if (!canControl()) return; orbit.range = clamp(orbit.range * Math.exp(delta), 10, 5000); pending = true; }
  function wheel(event) {
    if (!canControl()) return;
    consume(event);
    const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 900 : 1);
    zoom(clamp(pixels * 0.0015, -0.5, 0.5));
  }
  function listen(type, callback, options) { video?.addEventListener?.(type, callback, options); listeners.push([type, callback, options]); }
  listen('pointerdown', down); listen('pointermove', move);
  for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) listen(event, up);
  listen('wheel', wheel, { passive: false });
  listen('contextmenu', event => { if (enabled()) consume(event); });
  const timer = scheduler.setInterval(flush, 1000 / 30);
  return {
    zoom: direction => zoom(direction > 0 ? -0.2 : 0.2),
    reset() { pointer = null; orbit = null; pending = false; },
    destroy() { destroyed = true; pending = false; scheduler.clearInterval(timer);
      for (const [type, callback, options] of listeners) video?.removeEventListener?.(type, callback, options);
      if (pointer) { try { video.releasePointerCapture?.(pointer.id); } catch { /* gone */ } }
      pointer = null;
    },
  };
}
