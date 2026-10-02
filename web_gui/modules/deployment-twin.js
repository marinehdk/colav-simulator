/**
 * Deployment live twin viewport (P2-S4, spec #89; contract
 * sango/Docs/contracts/twin-bridge-v1.md). Third display state of the
 * Deployment workface: the center viewport becomes the local Unity pixel
 * stream attached to the ACTIVE live session (mode:'live'). Clock authority
 * stays with the backend — this module never sends `clock` (contract §2) and
 * owns no ReplayClock; the sidebar (OWN SHIP / MONITOR / …) keeps running on
 * the existing live data path untouched.
 *
 * Optional Cesium↔Twin camera link (contract §8 spike, default OFF): the
 * toggle instantiates a companion Cesium scene (split pane, Cesium master) and
 * forwards its camera.changed poses as one-way `camera_free` messages. Off =
 * zero messages, zero subscribers, no companion scene.
 *
 * Pure seams for node --test (no DOM/WebRTC): the URS receiver is injected via
 * `streamClientFactory` (default createTwinStreamClient), the camera fold is
 * twin-view.js#cameraFreePose, HUD projection is twin-view.js#projectTwinHud.
 */

import {
  createTwinStreamClient,
  cameraFreePose,
  observeTheme,
  projectTwinHud,
  projectSensorMode,
  sensorModeItems,
  themeValue,
  TWIN_SENSOR_MODE_DEFAULT,
  TWIN_SENSOR_MODES,
} from './twin-view.js?v=20261002-sensor-mode-v1';
import { createGeography } from './scene-geography.js?v=20261002-sensor-mode-v1';

// HUD refresh cadence (Unity state echo is ~1Hz; same as the Evaluation twin).
const HUD_INTERVAL_MS = 250;

export function createDeploymentTwinViewport({
  host = null, // #deploymentTwinHost (video + HUD + link controls)
  video = null, // <video> pixel-stream target
  linkPane = null, // split-pane host for the companion Cesium scene (hidden by default)
  linkToggle = null, // <input type="checkbox"> 联动 switch (default unchecked)
  statusEl = null, // HUD chip
  errorEl = null, // error slot
  sensorGroup = null, // P3-S2 sensor-mode button group ([data-twin-sensor] buttons)
  sensorModeEl = null, // P3-S2 current sensor-mode chip (state echo)
  signalingUrl = undefined, // default from twin-view
  backendBase = globalThis.location?.origin ?? 'http://127.0.0.1:8010',
  sessionId = () => null, // () => active live session id (deployment state)
  createLinkScene = null, // async ({ host, signal, onFailure, onCameraMoved }) => scene-like
  info = null, // ENC contract (geography for the camera fold)
  documentRef = globalThis.document,
  scheduler = globalThis,
  now = () => Date.now(),
  streamClientFactory = createTwinStreamClient,
  onDebug = () => {},
} = {}) {
  let streamCtl = null;
  let linkScene = null;
  let linkOn = false;
  let linkStarting = false;
  let latestProjection = null;
  let cameraFreeSent = 0;
  let destroyed = false;
  let themeObserver = null;
  let hudTimer = null;
  let generation = 0;
  const geography = info ? createGeography(info) : null;

  function publishDebug() {
    onDebug({
      connection: streamCtl?.connectionState ?? 'idle',
      ready: streamCtl?.client?.ready ?? false,
      attached: streamCtl?.client?.attached ?? null,
      lastState: streamCtl?.client?.lastState ?? null,
      errorCount: streamCtl?.client?.errorCount ?? 0,
      sent: streamCtl?.client?.sent ?? 0,
      received: streamCtl?.client?.received ?? 0,
      simTime: streamCtl?.client?.lastState?.sim_time ?? null,
      camera: streamCtl?.client?.lastState?.camera ?? null,
      sensorMode: streamCtl?.client?.lastState?.sensor_mode ?? null,
      cameraFreeSent,
      linkOn,
    });
  }

  // Contract §2 live semantics: hello → attach(mode live) and NOTHING else —
  // the backend owns the clock, so no ReplayClock and no clock messages ever.
  function attachLiveWhenReady(timeoutMs = 15000) {
    const gen = generation;
    const deadline = Date.now() + timeoutMs;
    const timer = scheduler.setInterval(() => {
      const client = streamCtl?.client;
      if (destroyed || gen !== generation) { scheduler.clearInterval(timer); return; }
      if (client?.ready) {
        scheduler.clearInterval(timer);
        client.sendAttach({ runId: sessionId(), backendBase, mode: 'live' });
        const theme = themeValue(documentRef?.documentElement?.getAttribute?.('data-obc-theme'));
        if (theme) client.sendTheme(theme);
        // P3-S2 (spec #90): §5 realignment — the current sensor mode rides along.
        const sensorActive = sensorGroup?.querySelector('[data-twin-sensor].active');
        client.sendSensorMode(sensorActive?.dataset.twinSensor ?? TWIN_SENSOR_MODE_DEFAULT);
        publishDebug();
      } else if (Date.now() > deadline) {
        scheduler.clearInterval(timer);
      }
    }, 100);
  }

  async function ensureStream() {
    if (streamCtl) return streamCtl.ensureStream();
    if (errorEl) errorEl.hidden = true;
    streamCtl = streamClientFactory({
      video,
      signalingUrl,
      page: 'deployment-twin',
      now,
      onChannel: () => attachLiveWhenReady(),
      onState: () => { renderHud(); publishDebug(); },
    });
    return streamCtl.ensureStream();
  }

  // ── Cesium↔Twin camera link spike (contract §8; single direction, default off) ──

  function sendCameraFreeFromCesium(rawPose) {
    const client = streamCtl?.client;
    if (!linkOn || !client?.attached || !geography) return; // 关 = 零消息；未 attach（无锚）不发
    const pose = cameraFreePose(rawPose, geography.eastNorth);
    client.sendCameraFree(pose);
    cameraFreeSent += 1;
    publishDebug();
  }

  async function openLink(signal) {
    if (!createLinkScene || linkScene || linkStarting) return;
    linkStarting = true;
    try {
      if (linkPane) linkPane.hidden = false;
      linkScene = await createLinkScene({
        host: linkPane,
        signal,
        onFailure: () => { if (!destroyed) closeLink(); },
        onCameraMoved: sendCameraFreeFromCesium,
      });
      if (destroyed || !linkOn) { linkScene?.destroy?.(); linkScene = null; return; }
      if (latestProjection) linkScene?.render?.(latestProjection);
    } catch {
      linkScene = null;
      if (linkPane) linkPane.hidden = true;
      setLinkChecked(false);
      linkOn = false;
    } finally {
      linkStarting = false;
      publishDebug();
    }
  }

  function closeLink() {
    generation += 1;
    linkOn = false;
    const scene = linkScene;
    linkScene = null;
    scene?.destroy?.();
    if (linkPane) linkPane.hidden = true;
    setLinkChecked(false);
    publishDebug();
  }

  function setLinkChecked(checked) {
    if (linkToggle && linkToggle.checked !== checked) linkToggle.checked = checked;
  }

  function onLinkToggle() {
    if (destroyed || !createLinkScene) return;
    if (linkToggle?.checked) {
      linkOn = true;
      const controller = new AbortController();
      void openLink(controller.signal);
    } else {
      closeLink(); // 关 = 零消息零开销：撤观察者 + 撤从视口
    }
  }

  // ── HUD ────────────────────────────────────────────────────────────────────

  function renderHud() {
    if (!statusEl) return;
    const hud = projectTwinHud({ connection: streamCtl?.connectionState ?? 'idle', client: streamCtl?.client ?? null, playhead: null, nowMs: now() });
    statusEl.textContent = `${hud.signal.toUpperCase()} · ${hud.fps === null ? '—' : `${hud.fps.toFixed(0)} FPS`} · ${hud.latencyMs === null ? '—' : `${hud.latencyMs.toFixed(0)} MS`}`;
    // P3-S2 (spec #90): state echo is the authority for the sensor mode UI.
    const mode = projectSensorMode(streamCtl?.client?.lastState);
    if (sensorGroup) {
      sensorGroup.querySelectorAll('[data-twin-sensor]').forEach(button => {
        const on = button.dataset.twinSensor === mode;
        button.classList.toggle('active', on);
        button.setAttribute('aria-pressed', String(on));
      });
    }
    if (sensorModeEl) {
      const item = sensorModeItems(mode).find(entry => entry.value === mode);
      sensorModeEl.textContent = `SENSOR ${item?.label ?? mode.toUpperCase()}`;
    }
    publishDebug();
  }

  function bind() {
    linkToggle?.addEventListener('change', onLinkToggle);
    // P3-S2 (spec #90): sensor-mode buttons — optimistic pick + send; the ~1Hz
    // state echo reasserts the authoritative mode (renderHud).
    sensorGroup?.querySelectorAll('[data-twin-sensor]').forEach(button => {
      button.addEventListener('click', () => {
        const value = button.dataset.twinSensor;
        if (!TWIN_SENSOR_MODES.includes(value)) return;
        const mode = value;
        if (sensorGroup) {
          sensorGroup.querySelectorAll('[data-twin-sensor]').forEach(other => {
            const on = other.dataset.twinSensor === mode;
            other.classList.toggle('active', on);
            other.setAttribute('aria-pressed', String(on));
          });
        }
        const client = streamCtl?.client;
        if (client?.ready) client.sendSensorMode(value);
        publishDebug();
      });
    });
    if (themeObserver === null && typeof MutationObserver !== 'undefined') {
      themeObserver = observeTheme(documentRef, value => {
        // §5 re-attach alignment: theme rides along whenever the page theme flips.
        if (value && streamCtl?.client?.ready) streamCtl.client.sendTheme(value);
      });
    }
    hudTimer = scheduler.setInterval(renderHud, HUD_INTERVAL_MS);
  }

  bind();

  return {
    /** Live-view projection forward: the companion Cesium pane consumes it; the
     * twin stream itself ignores it (Unity pulls live telemetry itself). */
    render(projection) {
      latestProjection = projection;
      if (linkOn) linkScene?.render?.(projection);
    },
    async attach() {
      try {
        await ensureStream();
      } catch (error) {
        if (errorEl) {
          errorEl.textContent = `Twin stream unreachable at ${signalingUrl} — start the local URS webapp and the sango-twin player.`;
          errorEl.hidden = false;
        }
        throw error;
      }
    },
    recenter() { linkScene?.recenter?.(); },
    zoom(direction) { linkScene?.zoom?.(direction); },
    destroy() {
      destroyed = true;
      generation += 1;
      if (hudTimer !== null) scheduler.clearInterval(hudTimer);
      themeObserver?.disconnect?.();
      themeObserver = null;
      closeLink();
      streamCtl?.client?.sendDetach();
      void streamCtl?.close();
      streamCtl = null;
    },
    get linkOn() { return linkOn; },
    get cameraFreeSent() { return cameraFreeSent; },
    get client() { return streamCtl?.client ?? null; },
    get connectionState() { return streamCtl?.connectionState ?? 'idle'; },
    publishDebug,
  };
}
