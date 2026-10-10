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
  createTwinStreamHealthMonitor,
  probeSignalingReachable,
  STREAM_ENTRY_TIMEOUT_MS,
  cameraFreePose,
  observeTheme,
  projectTwinHud,
  projectSensorMode,
  sensorModeItems,
  themeValue,
  TWIN_SENSOR_MODE_DEFAULT,
  TWIN_SENSOR_MODES,
} from './twin-view.js?v=20261010-dt-camera-v4';
import { createGeography } from './scene-geography.js?v=20261004-token-cleanup-v1';
import { chooseTwinStreamProfile, sampleTwinVideoStats } from './twin-stream-quality.js?v=20261009-dt-quality-v3';

import { createTwinCameraControls } from './twin-camera-controls.js?v=20261010-dt-camera-v6';
import { createTwinSituationOverlay } from './twin-situation.js?v=20261010-dt-landscape-v1';

// HUD refresh cadence (Unity state echo is ~1Hz; same as the Evaluation twin).
const HUD_INTERVAL_MS = 250;

export function projectTwinLandscape(state) {
  if (!state || state.ready !== false) return null;
  const progress = Number.isFinite(state.progress) ? Math.max(0, Math.min(100, state.progress)) : 0;
  return { visible: true, level: state.state === 'failed' ? 'failed' : 'warming',
    title: state.state === 'failed' ? '地形预热未完成' : '正在预热地形 · ' + progress.toFixed(0) + '%',
    detail: state.state === 'failed' ? '请检查地形服务连接，重新进入 DT 重试。'
      : '正在准备本船周边与航线前方岛屿，完成后显示视景。' };
}

export function createDeploymentTwinViewport({
  host = null, // #deploymentTwinHost (video + HUD + link controls)
  video = null, // <video> pixel-stream target
  linkPane = null, // split-pane host for the companion Cesium scene (hidden by default)
  linkToggle = null, // <input type="checkbox"> 联动 switch (default unchecked)
  statusEl = null, // HUD chip
  errorEl = null, // error slot
  healthEl = null, // spec #91 前置批 B: stream-health status card (hidden when healthy)
  sensorGroup = null, // P3-S2 sensor-mode button group ([data-twin-sensor] buttons)
  sensorModeEl = null, // P3-S2 current sensor-mode chip (state echo)
  signalingUrl = undefined, // default from twin-view
  backendBase = globalThis.location?.origin ?? 'http://127.0.0.1:8010',
  fetchRef = globalThis.fetch,
  signal = null,
  sessionId = () => null, // () => active live session id (deployment state)
  createLinkScene = null, // async ({ host, signal, onFailure, onCameraMoved }) => scene-like
  info = null, // ENC contract (geography for the camera fold)
  documentRef = globalThis.document,
  scheduler = globalThis,
  now = () => Date.now(),
  streamClientFactory = createTwinStreamClient,
  healthProbe = probeSignalingReachable, // injectable for hermetic tests (spec #91 前置批 B)
  onDebug = () => {},
  chart = null,
  onSelect = () => {},
  getPlannerSurface = () => null,
  requestVODecisionSpace = () => {},
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
  let runtimeRunId = null;
  let runtimeStarting = false;
  const attachTimers = new Set();
  let requestedProfile = '1080p';
  let sentProfile = null;
  let measuredVideo = null;
  let statsPending = false;
  let lastStatsAt = -Infinity;
  let slowSamples = 0;
  let downgraded = false;
  let viewportSizeKey = null;
  let resizeObserver = null;
  let videoFrameCallback = null;
  let lastVideoFrameAt = null;
  const situation = chart && host?.ownerDocument && video ? createTwinSituationOverlay({
    host, video, chart, info, client: () => streamCtl?.client, onSelect, onCameraChange: () => cameraControls.reset(), getPlannerSurface, requestVODecisionSpace,
  }) : null;
  const videoFrameIntervals = [];
  function observeVideoFrame(timestamp) {
    if (destroyed) return;
    situation?.videoFrame(timestamp);
    if (lastVideoFrameAt !== null) {
      videoFrameIntervals.push(timestamp - lastVideoFrameAt);
      if (videoFrameIntervals.length > 120) videoFrameIntervals.shift();
      const sorted = [...videoFrameIntervals].sort((a, b) => a - b);
      if (video?.dataset) {
        video.dataset.frameIntervalP95Ms = sorted[Math.floor((sorted.length - 1) * 0.95)].toFixed(1);
        video.dataset.frameIntervalMaxMs = sorted.at(-1).toFixed(1);
      }
    }
    lastVideoFrameAt = timestamp;
    videoFrameCallback = video.requestVideoFrameCallback(observeVideoFrame);
  }
  const geography = info ? createGeography(info) : null;

  const cameraControls = createTwinCameraControls({
    video, scheduler,
    getClient: () => streamCtl?.client,
    enabled: () => !destroyed && !linkOn && (streamCtl?.client?.lastState?.landscape || situation?.landscape)?.ready !== false,
    getCameraPose: () => situation?.cameraPose || streamCtl?.client?.lastState?.camera_pose,
    getOwnship: () => {
      const ship = latestProjection?.raw?.os;
      if (!ship || !info) return null;
      return { east: info.origin_e + ship.y, north: info.origin_n + ship.x,
        psi: ship.psi, length: ship.length };
    },
    onSend: pose => {
      cameraFreeSent += 1;
      if (video?.dataset) video.dataset.cameraPose = JSON.stringify(pose);
      publishDebug();
    },
  });
  if (video?.style) { video.style.touchAction = 'none'; video.style.visibility = 'hidden'; }
  if (video?.setAttribute) video.setAttribute('title', '左键平移 · 中键旋转 · 右键/滚轮缩放 · 左键双击回到本船');
  function recenterCamera(event) {
    if (event && event.button !== 0) return;
    cameraControls.reset();
    streamCtl?.client?.sendCamera?.('chase');
  }
  video?.addEventListener?.('dblclick', recenterCamera);

  // spec #91 前置批 B: stream health watchdog — 分层状态卡（信令挂→信令服务提示；
  // 信令通流无→player 服务提示+重试计数），流恢复自动隐藏。onRetry = 真·重连
  // （close→re-ensure→re-attach），用户手点 T 的等效动作由监视器自动做。
  const healthMonitor = createTwinStreamHealthMonitor({
    signalingUrl,
    now,
    probe: healthProbe,
    onHealth: renderHealthCard,
    onRetry: () => {
      if (destroyed) return;
      generation += 1; // 在途 attachLiveWhenReady 定时器全部作废
      situation?.reset();
      const ctl = streamCtl;
      streamCtl = null;
      try { void ctl?.close(); } catch { /* retry again on the next tick */ }
      void reensureStream();
    },
  });

  async function reensureStream() {
    try {
      await ensureStream();
      attachLiveWhenReady();
    } catch {
      /* healthMonitor 卡片已在报；下一 tick 重试 */
    }
  }

  function renderHealthCard(health) {
    if (destroyed || !healthEl) return;
    const landscape = projectTwinLandscape(streamCtl?.client?.lastState?.landscape || situation?.landscape);
    if (!runtimeStarting && landscape) health = landscape;
    if (!health.visible) {
      healthEl.hidden = true;
      return;
    }
    const title = healthEl.querySelector('.twin-health-title');
    const detail = healthEl.querySelector('.twin-health-detail');
    if (title) title.textContent = runtimeStarting ? '正在启动数字孪生' : health.title;
    if (detail) detail.textContent = runtimeStarting
      ? '正在启动数字孪生并建立数据流连接…'
      : landscape?.detail || '正在连接数字孪生数据流，连接恢复后自动显示。';
    healthEl.dataset.level = health.level;
    healthEl.hidden = false;
  }

  function publishDebug() {
    situation?.tick(globalThis.performance?.now?.() ?? now());
    onDebug({
      connection: streamCtl?.connectionState ?? 'idle',
      ready: streamCtl?.client?.ready ?? false,
      // spec #91 前置批 D: the twin-bridge client itself on the debug facade —
      // probes drive client.sendCameraFree/sendTheme through it (the old
      // `__deploymentTwin?.client?.…` calls silently no-op'd on a facade
      // without the client; the theme only rode attach realignment).
      client: streamCtl?.client ?? null,
      attached: streamCtl?.client?.attached ?? null,
      lastState: streamCtl?.client?.lastState ?? null,
      errorCount: streamCtl?.client?.errorCount ?? 0,
      sent: streamCtl?.client?.sent ?? 0,
      received: streamCtl?.client?.received ?? 0,
      simTime: streamCtl?.client?.lastState?.sim_time ?? null,
      videoStats: measuredVideo,
      streamProfile: requestedProfile,
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
      if (destroyed || gen !== generation || sessionId() !== runtimeRunId) { clearAttachTimer(timer); return; }
      if (client?.ready) {
        clearAttachTimer(timer);
        client.sendAttach({ runId: runtimeRunId, backendBase, mode: 'live' });
        const theme = themeValue(documentRef?.documentElement?.getAttribute?.('data-obc-theme'));
        if (theme) client.sendTheme(theme);
        // P3-S2 (spec #90): §5 realignment — the current sensor mode rides along.
        const sensorActive = sensorGroup?.querySelector('[data-twin-sensor].active');
        client.sendSensorMode(sensorActive?.dataset.twinSensor ?? TWIN_SENSOR_MODE_DEFAULT);
        updateViewportProfile();
        sendStreamProfile();
        publishDebug();
      } else if (Date.now() > deadline) {
        clearAttachTimer(timer);
      }
    }, 100);
    attachTimers.add(timer);
  }

  function clearAttachTimer(timer) {
    scheduler.clearInterval(timer);
    attachTimers.delete(timer);
  }

  async function ensureStream() {
    if (streamCtl) return streamCtl.ensureStream();
    if (errorEl) errorEl.hidden = true;
    streamCtl = streamClientFactory({
      video,
      signalingUrl,
      page: 'deployment-twin',
      now,
      onChannel: () => { sentProfile = null; measuredVideo = null; if (video?.dataset) video.dataset.sourceVideo = ''; attachLiveWhenReady(); },
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
      cameraControls.reset();
      linkOn = true;
      const controller = new AbortController();
      void openLink(controller.signal);
    } else {
      closeLink(); // 关 = 零消息零开销：撤观察者 + 撤从视口
    }
  }

  // ── HUD ────────────────────────────────────────────────────────────────────

  function sendStreamProfile() {
    const client = streamCtl?.client;
    if (!client?.ready || !client.videoProfiles?.includes(requestedProfile) || sentProfile === requestedProfile) return;
    client.sendStreamProfile(requestedProfile);
    sentProfile = requestedProfile;
  }

  function updateViewportProfile() {
    if (destroyed) return;
    const rect = video?.getBoundingClientRect?.();
    if (!rect || !(rect.width > 0 && rect.height > 0)) return;
    const dpr = documentRef?.defaultView?.devicePixelRatio ?? globalThis.devicePixelRatio ?? 1;
    const key = `${rect.width}:${rect.height}:${dpr}`;
    if (key === viewportSizeKey) return;
    viewportSizeKey = key;
    downgraded = false;
    slowSamples = 0;
    requestedProfile = chooseTwinStreamProfile(rect.width, rect.height, dpr);
    sendStreamProfile();
  }

  function pollVideoStats() {
    if (statsPending || now() - lastStatsAt < 1000 || typeof streamCtl?.getStats !== 'function') return;
    lastStatsAt = now();
    statsPending = true;
    const ctl = streamCtl;
    void ctl.getStats().then(report => {
      if (destroyed || ctl !== streamCtl) return;
      measuredVideo = sampleTwinVideoStats(report, measuredVideo);
      const bad = measuredVideo?.fps !== null && measuredVideo?.fps < 26
        || measuredVideo?.dropRatio > 0.03;
      slowSamples = bad ? slowSamples + 1 : 0;
      if (!downgraded && requestedProfile === '1440p' && slowSamples >= 5) {
        requestedProfile = '1080p';
        downgraded = true;
        sendStreamProfile();
      }
      publishDebug();
    }).catch(() => {}).finally(() => { statsPending = false; });
  }

  function renderHud() {
    if (destroyed || !statusEl) return;
    updateViewportProfile();
    pollVideoStats();
    const hud = projectTwinHud({ connection: streamCtl?.connectionState ?? 'idle', client: streamCtl?.client ?? null, playhead: null, nowMs: now() });
    const width = measuredVideo?.width || video?.videoWidth;
    const height = measuredVideo?.height || video?.videoHeight;
    statusEl.textContent = `${hud.signal.toUpperCase()} · ${width && height ? `${width}×${height}` : '—'} · ${measuredVideo?.fps == null ? '—' : measuredVideo.fps.toFixed(0)} FPS · ${measuredVideo?.bitrateMbps == null ? '—' : measuredVideo.bitrateMbps.toFixed(1)} Mb/s${streamCtl?.client?.lastState?.presentation_buffering ? ' · 缓冲中' : ''}`;
    if (video?.dataset) {
      video.dataset.receivedFps = measuredVideo?.fps == null ? '' : measuredVideo.fps.toFixed(2);
      video.dataset.bitrateMbps = measuredVideo?.bitrateMbps == null ? '' : measuredVideo.bitrateMbps.toFixed(3);
      video.dataset.codec = measuredVideo?.codec ?? '';
      for (const key of ['lossRatio', 'decodeMs', 'jitterBufferMs', 'jitterMs', 'rttMs', 'dropRatio', 'freezeCount'])
        video.dataset[key] = measuredVideo?.[key] == null ? '' : String(measuredVideo[key]);
      if (streamCtl?.client?.lastState?.video) video.dataset.sourceVideo = JSON.stringify(streamCtl.client.lastState.video);
      video.dataset.streamProfile = requestedProfile;
      video.dataset.presentationBuffering = String(Boolean(streamCtl?.client?.lastState?.presentation_buffering));
      const landscape = streamCtl?.client?.lastState?.landscape || situation?.landscape;
      if (video.style) video.style.visibility = !streamCtl?.client?.lastState || landscape?.ready === false ? 'hidden' : '';
      if (landscape) video.dataset.landscape = JSON.stringify(landscape);
      const cameraPose = streamCtl?.client?.lastState?.camera_pose;
      if (cameraPose) video.dataset.unityCameraPose = JSON.stringify(cameraPose);
      if (streamCtl?.client?.lastState?.motion) video.dataset.motion = JSON.stringify(streamCtl.client.lastState.motion);
    }
    // spec #91 前置批 B: health watchdog tick — video readiness is the DOM-side boolean.
    healthMonitor.tick(Boolean(
      streamCtl?.connectionState === 'streaming'
      && video?.readyState >= 2
      && (video?.videoWidth ?? 0) > 0,
    ));
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
    if (video?.requestVideoFrameCallback) videoFrameCallback = video.requestVideoFrameCallback(observeVideoFrame);
    if (typeof ResizeObserver !== 'undefined' && video) {
      resizeObserver = new ResizeObserver(updateViewportProfile);
      resizeObserver.observe(video);
    }
  }

  bind();

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    generation += 1;
    if (hudTimer !== null) scheduler.clearInterval(hudTimer);
    for (const timer of attachTimers) clearAttachTimer(timer);
    themeObserver?.disconnect?.();
    resizeObserver?.disconnect();
    if (videoFrameCallback !== null) video?.cancelVideoFrameCallback?.(videoFrameCallback);
    themeObserver = null;
    closeLink();
    cameraControls.destroy();
    if (video?.style) video.style.visibility = '';
    situation?.destroy();
    video?.removeEventListener?.('dblclick', recenterCamera);
    streamCtl?.client?.sendDetach();
    void streamCtl?.close();
    streamCtl = null;
  }

  return {
    /** Live-view projection forward: the companion Cesium pane consumes it; the
     * twin stream itself ignores it (Unity pulls live telemetry itself). */
    render(projection) {
      if (destroyed) return;
      latestProjection = projection;
      situation?.render(projection);
      if (['FINISHED', 'FAILED'].includes(projection?.raw?.state)) {
        destroy();
        if (statusEl) statusEl.textContent = `${projection.raw.state} · DT STOPPED`;
        if (healthEl) {
          healthEl.hidden = false;
          healthEl.dataset.level = 'stopped';
          const title = healthEl.querySelector('.twin-health-title');
          const detail = healthEl.querySelector('.twin-health-detail');
          if (title) title.textContent = '数字孪生已停止';
          if (detail) detail.textContent = '会话已结束，数据流已断开。';
        }
        return;
      }
      if (linkOn) linkScene?.render?.(projection);
    },
    async attach() {
      const runId = sessionId();
      if (!runId) throw new Error('当前无可连接的仿真会话');
      runtimeStarting = true;
      renderHealthCard({ visible: true, level: 'starting' });
      try {
        const response = await fetchRef(`${backendBase}/api/sessions/${encodeURIComponent(runId)}/twin/start`, {
          method: 'POST', signal,
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || '数字孪生启动失败');
        backendBase = result.renderer_backend_base || backendBase;
        signalingUrl = result.signaling_url || signalingUrl;
        if (destroyed || signal?.aborted || sessionId() !== runId) throw new Error('数字孪生连接已取消');
        runtimeRunId = runId;
      } finally {
        runtimeStarting = false;
      }
      try {
        // spec #91 前置批 B: the URS receiver retries a dead signaling forever —
        // bound the entry so the health card shows instead of an eternal "connecting".
        await Promise.race([
          ensureStream(),
          new Promise((_, reject) => setTimeout(() => reject(new Error('stream entry timeout')), STREAM_ENTRY_TIMEOUT_MS)),
        ]);
      } catch (error) {
        // spec #91 前置批 B: the health card owns stream-unreachable UX now —
        // the viewport stays open ("孪生流端未连接 · 重试中"), the watchdog
        // probes signaling (分层提示) and retries; no more dead-end error text.
        if (errorEl) errorEl.hidden = true;
        healthMonitor.tick(false);
        return;
      }
      healthMonitor.tick(Boolean(
        streamCtl?.connectionState === 'streaming'
        && video?.readyState >= 2
        && (video?.videoWidth ?? 0) > 0,
      ));
    },
    recenter() { if (linkOn) linkScene?.recenter?.(); else recenterCamera(); },
    select(id) { situation?.select(id); },
    zoom(direction) { if (linkOn) linkScene?.zoom?.(direction); else cameraControls.zoom(direction); },
    destroy,
    get linkOn() { return linkOn; },
    get cameraFreeSent() { return cameraFreeSent; },
    get client() { return streamCtl?.client ?? null; },
    get connectionState() { return streamCtl?.connectionState ?? 'idle'; },
    publishDebug,
  };
}
