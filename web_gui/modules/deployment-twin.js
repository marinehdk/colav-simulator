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
  nextSensorMode,
  themeValue,
  TWIN_SENSOR_MODE_DEFAULT,
  TWIN_SENSOR_MODES,
  TWIN_SENSOR_IR_MODES,
  TWIN_SENSOR_ECHO_GUARD_MS,
} from './twin-view.js?v=20261022-radar-screen-v1';
import { createGeography } from './scene-geography.js?v=20261016-qingdao-v2';
import { chooseTwinStreamProfile, sampleTwinVideoStats } from './twin-stream-quality.js?v=20261013-dt-diagnostics-v11';

import { createTwinCameraControls } from './twin-camera-controls.js?v=20261010-dt-camera-v6';
import { createTwinSituationOverlay } from './twin-situation.js?v=20261023-wpt-thin-v1';

// HUD refresh cadence (Unity state echo is ~1Hz; same as the Evaluation twin).
const HUD_INTERVAL_MS = 250;

function landscapeIsDisplayable(state) {
  return state?.ready !== false || state?.displayable === true;
}

export function projectTwinLandscape(state) {
  if (!state || landscapeIsDisplayable(state)) return null;
  if (state.state === 'waiting-session') return { visible: true, level: 'warming',
    title: '正在同步仿真会话', detail: '正在等待当前会话的视景数据，然后检查地形。' };
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
  const staticRegion = info?.scene_mode === 'GEOGRAPHIC_STATIC';
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
  // P2 IR realism: 当前 sensor_mode（含极性值）——IR 键再点循环基 + §5 重发值。
  let currentSensorMode = TWIN_SENSOR_MODE_DEFAULT;
  // P2 race fix: pick 后的 stale-echo 护窗（twin-view.js#TWIN_SENSOR_ECHO_GUARD_MS）。
  let sensorEchoGuard = { value: null, until: 0 };
  const attachTimers = new Set();
  let requestedProfile = '1080p';
  let sentProfile = null;
  let measuredVideo = null;
  let statsPending = false;
  let lastStatsAt = -Infinity;
  let slowSamples = 0;
  let goodSamples = 0;
  let downgraded = false;
  let settleSamples = 0;
  let viewportSizeKey = null;
  let resizeObserver = null;
  let videoFrameCallback = null;
  let lastVideoFrameAt = null;
  if (video?.dataset) for (const key of ['landscape', 'sourceVideo', 'motion', 'unityCameraPose', 'streamDiagnostics']) delete video.dataset[key];
  let lastVideoMetadata = null;
  let videoCallbacks = 0, skippedVideoCallbacks = 0, videoGapCount = 0, videoGapMaxMs = 0;
  let animationFrame = null, lastAnimationAt = null, animationGapMaxMs = 0;
  let longTaskObserver = null, longTasks = 0, longTaskMaxMs = 0;
  let longFrameObserver = null;
  const longFrames = [];
  const viewportOpenedAt = now();
  let landscapeReadyMs = null;
  const sourceCadence = { matched: 0, consecutive: 0, repeated: 0, advanced: 0 };
  let lastSourceFrame = null;
  // 本船真值(east/north ENU + 船长):situation 本船框抑制与 cameraControls
  // 初始化同源(相机控件 getOwnship 原getter上提共用)。
  const twinOwnship = () => {
    if (staticRegion) return { east: info.origin_e+info.width/2, north: info.origin_n+info.height/2 };
    const ship = latestProjection?.raw?.os;
    if (!ship || !info) return null;
    return { east: info.origin_e + ship.y, north: info.origin_n + ship.x,
      psi: ship.psi, length: ship.length };
  };
  const situation = !staticRegion && chart && host?.ownerDocument && video ? createTwinSituationOverlay({
    host, video, chart, info, client: () => streamCtl?.client, onSelect, onCameraChange: () => cameraControls.reset(), getPlannerSurface, requestVODecisionSpace, getOwnship: twinOwnship,
  }) : null;
  const videoFrameIntervals = [];
  function observeVideoFrame(timestamp, metadata = {}) {
    if (destroyed) return;
    const sourceFrame = streamCtl?.client?.videoFrameId?.(metadata.rtpTimestamp) ?? null;
    if (sourceFrame !== null) {
      sourceCadence.matched++;
      if (lastSourceFrame !== null && metadata.presentedFrames === lastVideoMetadata?.presentedFrames + 1) {
        const advance = (sourceFrame - lastSourceFrame + 65536) % 65536;
        sourceCadence.consecutive++;
        if (advance === 0) sourceCadence.repeated++;
        // Advancing by two is expected when rendering at 60 and capturing at 30.
        if (advance < 240) sourceCadence.advanced += advance;
      }
    }
    lastSourceFrame = sourceFrame;
    situation?.videoFrame(timestamp, metadata);
    if (lastVideoFrameAt !== null) {
      const gap = timestamp - lastVideoFrameAt;
      videoFrameIntervals.push(gap);
      if (documentRef?.visibilityState !== 'hidden') {
        videoGapMaxMs = Math.max(videoGapMaxMs, gap);
        if (gap > 100) videoGapCount++;
      }
      if (videoFrameIntervals.length > 120) videoFrameIntervals.shift();
    }
    if (lastVideoMetadata && Number.isFinite(metadata.presentedFrames))
      skippedVideoCallbacks += Math.max(0, metadata.presentedFrames - lastVideoMetadata.presentedFrames - 1);
    lastVideoMetadata = metadata;
    videoCallbacks++;
    lastVideoFrameAt = timestamp;
    videoFrameCallback = video.requestVideoFrameCallback(observeVideoFrame);
  }
  function observeAnimationFrame(timestamp) {
    if (destroyed) return;
    if (lastAnimationAt !== null && documentRef?.visibilityState !== 'hidden')
      animationGapMaxMs = Math.max(animationGapMaxMs, timestamp - lastAnimationAt);
    lastAnimationAt = documentRef?.visibilityState === 'hidden' ? null : timestamp;
    animationFrame = scheduler.requestAnimationFrame(observeAnimationFrame);
  }
  const geography = info ? createGeography(info) : null;

  // 20261015 舰桥瞭望（契约 §8 演进）：Bridge 玻璃眼预设下，视口拖拽 = 船长瞭望
  // （前方 180°，俯仰受玻璃限制），走 camera_look；其他预设维持原轨道控件——旧路径
  // 任何拖拽都发 camera_free 把预设顶成自由静态机位（用户观感"单击退出到静态相机"）。
  // 预设离开 Bridge 再回来时累积量归零（Unity SetView 同步归零）；双击在 Bridge = 回正
  // 视线（不切预设）。单监听器契约（测试桩 listeners.set 每类型一槽）：pointer 事件由
  // 分发 hub 统一持有，controls 经 controlsVideo 原型链包装注册进 hub，共用每类型一槽。
  const bridgeLook = { yaw: 0, pitch: 0, sentAt: 0, preset: '' };
  // 预设权威源 = Unity 状态回显(state.camera:'bridge'/'chase'/'free'…);DOM data-camera
  // 仅兜底(视频元素不必然是 situation 根的后代——实测 closest 常落空,拖拽瞭望失灵根因)。
  // 回显延迟竞态(20261015 chase"固定"实证):点预设按钮后 ~1s 内回显未达,拖拽被旧预设
  // 的处理器吃掉(chase 下瞭望偏移不可见=视觉无反应)。捕获期监听按钮点击,本地即时记
  // 预设,5s 内以本地为准;回显追平或超时后回到权威源。
  let presetClickOverride = null;
  let presetClickAt = 0;
  const onPresetButtonClick = event => {
    const btn = event.target?.closest?.('button[data-camera]');
    if (!btn || !btn.dataset.camera) return;
    presetClickOverride = btn.dataset.camera;
    presetClickAt = performance.now();
  };
  documentRef?.addEventListener?.('click', onPresetButtonClick, true);
  const currentPreset = () => {
    const echo = streamCtl?.client?.lastState?.camera;
    if (presetClickOverride !== null) {
      if (echo === presetClickOverride || performance.now() - presetClickAt > 5000) presetClickOverride = null;
      else return presetClickOverride;
    }
    return echo || video?.closest?.('[data-camera]')?.dataset.camera || '';
  };
  const clampBridgeLook = () => {
    bridgeLook.yaw = Math.max(-90, Math.min(90, bridgeLook.yaw));
    bridgeLook.pitch = Math.max(-25, Math.min(15, bridgeLook.pitch));
  };
  const syncBridgeLookPreset = () => {
    const preset = currentPreset();
    if (bridgeLook.preset !== preset) {
      bridgeLook.preset = preset;
      bridgeLook.yaw = 0;
      bridgeLook.pitch = 0;
    }
    return preset;
  };
  const sendBridgeLook = () => {
    clampBridgeLook();
    streamCtl?.client?.sendCameraLook?.(bridgeLook.yaw, bridgeLook.pitch);
  };

  const pointerHubs = { pointerdown: [], pointermove: [], pointerup: [], pointercancel: [] };
  const dispatchPointer = type => event => { for (const fn of pointerHubs[type]) fn(event); };
  for (const type of Object.keys(pointerHubs)) video?.addEventListener?.(type, dispatchPointer(type));
  const controlsVideo = video ? Object.assign(Object.create(video), {
    addEventListener(type, fn) {
      if (pointerHubs[type]) pointerHubs[type].push(fn);
      else video?.addEventListener?.(type, fn);
    },
    removeEventListener(type, fn) {
      if (pointerHubs[type]) {
        const at = pointerHubs[type].indexOf(fn);
        if (at >= 0) pointerHubs[type].splice(at, 1);
      } else video?.removeEventListener?.(type, fn);
    },
    // 原生 DOM 方法以 Object.create 包装器为 receiver 会抛 Illegal invocation
    // (20261016 追随左键平移失灵真根因:down 的 setPointerCapture 与 move 平移分支
    // 的 getBoundingClientRect 双双抛出——左键全死,中/右键(旋转/缩放)不碰这两
    // 调用故正常;Node 测试桩无这些方法,?. 跳过=测试全绿测不出)。闭包直转真 video。
    setPointerCapture(id) { video.setPointerCapture?.(id); },
    releasePointerCapture(id) { video.releasePointerCapture?.(id); },
    getBoundingClientRect() { return video.getBoundingClientRect?.(); },
  }) : video;

  const cameraControls = createTwinCameraControls({
    video: controlsVideo, scheduler,
    getClient: () => streamCtl?.client,
    enabled: () => !destroyed && !linkOn && syncBridgeLookPreset() !== 'bridge'
      && landscapeIsDisplayable(streamCtl?.client?.lastState?.landscape || situation?.landscape),
    getCameraPose: () => situation?.cameraPose || streamCtl?.client?.lastState?.camera_pose,
    getOwnship: twinOwnship,
    onSend: pose => {
      cameraFreeSent += 1;
      if (video?.dataset) video.dataset.cameraPose = JSON.stringify(pose);
      publishDebug();
    },
  });
  if (video?.style) { video.style.touchAction = 'none'; video.style.visibility = 'hidden'; }
  // 左键拖拽守卫:流 <video> 默认可拖拽,真实左键拖会先触发原生 dragstart 抢走
  // pointermove(合成事件不触发——harness/CDP 复现不出来的根因),相机控件左键
  // 平移因此"失灵"而中/右键正常。禁拖 + 阻断 dragstart,拖拽事件链回归 video。
  if (video?.setAttribute) video.setAttribute('draggable', 'false');
  const swallowDragStart = event => event.preventDefault();
  video?.addEventListener?.('dragstart', swallowDragStart);
  if (video?.setAttribute) video.setAttribute('title', '舰桥：拖拽瞭望 · 双击回正 · 其他视角：左键平移 · 中键旋转 · 右键/滚轮缩放 · 双击回到本船');
  let lookPointer = null;
  pointerHubs.pointerdown.push(event => {
    if (event.button !== 0 || syncBridgeLookPreset() !== 'bridge') return;
    lookPointer = { id: event.pointerId, x: event.clientX, y: event.clientY };
    video.setPointerCapture?.(event.pointerId);
    event.preventDefault?.();
  });
  pointerHubs.pointermove.push(event => {
    if (!lookPointer || lookPointer.id !== event.pointerId) return;
    if (syncBridgeLookPreset() !== 'bridge') { lookPointer = null; return; }
    bridgeLook.yaw += (event.clientX - lookPointer.x) * 0.25;   // 拖右=向右舷看
    bridgeLook.pitch -= (event.clientY - lookPointer.y) * 0.2;  // 拖上=抬头（玻璃内限位）
    lookPointer.x = event.clientX; lookPointer.y = event.clientY;
    clampBridgeLook();
    const now = performance.now();
    if (now - bridgeLook.sentAt > 80) { bridgeLook.sentAt = now; sendBridgeLook(); }
  });
  const endLookPointer = event => {
    if (!lookPointer || lookPointer.id !== event.pointerId) return;
    lookPointer = null;
    sendBridgeLook();
  };
  pointerHubs.pointerup.push(endLookPointer);
  pointerHubs.pointercancel.push(endLookPointer);
  function recenterCamera(event) {
    if (event && event.button !== 0) return;
    if (syncBridgeLookPreset() === 'bridge') {
      bridgeLook.yaw = 0; bridgeLook.pitch = 0;
      sendBridgeLook();
      return;
    }
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
      : staticRegion && landscape ? '正在准备青岛海岸、地形与真实影像，完成后显示视景。'
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
  // Attach watchdog (2026-10-21): the player echoes `attached`, but the first
  // hello/attach races the player-side channel wiring (~100 ms window — three
  // Qingdao outages today: black terrain, then 6 fps + frozen LOD). Re-send the
  // idempotent trio until the echo lands or the confirm budget runs out.
  function attachLiveWhenReady(timeoutMs = 15000, confirmBudgetMs = 45000) {
    for (const pending of attachTimers) clearAttachTimer(pending);
    const gen = generation;
    const readyDeadline = now() + timeoutMs;
    const confirmDeadline = now() + confirmBudgetMs;
    let lastSend = 0;
    let announced = false;
    const timer = scheduler.setInterval(() => {
      const client = streamCtl?.client;
      if (destroyed || gen !== generation || sessionId() !== runtimeRunId) { clearAttachTimer(timer); return; }
      if (client?.attached) { clearAttachTimer(timer); return; }
      if (client?.ready) {
        if (!lastSend || now() - lastSend >= 3000) {
          lastSend = Date.now();
          client.sendHello?.();
          client.sendAttach({ runId: runtimeRunId, backendBase, mode: staticRegion ? 'static' : 'live' });
          const theme = themeValue(documentRef?.documentElement?.getAttribute?.('data-obc-theme'));
          if (theme) client.sendTheme(theme);
          // P3-S2 (spec #90): §5 realignment — the current sensor mode rides along
          // (P2: tracked value carries the IR polarity; dataset only says 'ir').
          client.sendSensorMode(currentSensorMode);
        }
        if (!announced) {
          announced = true;
          updateViewportProfile();
          sendStreamProfile();
        }
        publishDebug();
        if (now() > confirmDeadline) clearAttachTimer(timer);
      } else if (now() > readyDeadline) {
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
      onChannel: () => {
        sentProfile = null; measuredVideo = null; lastVideoFrameAt = null; lastVideoMetadata = null;
        if (video?.dataset) { video.dataset.sourceVideo = ''; delete video.dataset.landscape; }
        attachLiveWhenReady();
      },
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
    goodSamples = 0;
    settleSamples = 0;
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
      if (video?.dataset) {
        const intervals = [...videoFrameIntervals].sort((a, b) => a - b);
        if (intervals.length) {
          video.dataset.frameIntervalP95Ms = intervals[Math.floor((intervals.length - 1) * 0.95)].toFixed(1);
          video.dataset.frameIntervalMaxMs = intervals.at(-1).toFixed(1);
        }
        // One compact sample per second. Browser probes read DOM data without
        // opening another peer or injecting a second rendering loop.
        const metadata = lastVideoMetadata;
        const quality = video.getVideoPlaybackQuality?.();
        video.dataset.streamDiagnostics = JSON.stringify({
          at: now(), visibility: documentRef?.visibilityState ?? null, landscapeReadyMs,
          ...measuredVideo, videoCallbacks, skippedVideoCallbacks, videoGapCount, videoGapMaxMs,
          animationGapMaxMs, longTasks, longTaskMaxMs, longFrames, sourceCadence,
          presentedFrames: metadata?.presentedFrames ?? null,
          displayDelayMs: Number.isFinite(metadata?.receiveTime) ? metadata.expectedDisplayTime - metadata.receiveTime : null,
          callbackLateMs: Number.isFinite(metadata?.expectedDisplayTime) ? lastVideoFrameAt - metadata.expectedDisplayTime : null,
          totalVideoFrames: quality?.totalVideoFrames ?? null, droppedVideoFrames: quality?.droppedVideoFrames ?? null,
          situation: situation?.diagnostics ?? null,
          frameCosts: situation?.frameCosts ?? null,
        });
      }
      // The stream's first seconds ramp the encoder/bitrate up; judging there
      // downgraded a healthy 1440p stream to 1080p on startup and never came
      // back. Settle for ~15 one-second samples before evaluating, then allow
      // recovery once the stream sustains full-rate frames again.
      const settled = ++settleSamples > 15;
      const bad = settled && (measuredVideo?.fps !== null && measuredVideo?.fps < 26
        || measuredVideo?.dropRatio > 0.03);
      slowSamples = bad ? slowSamples + 1 : 0;
      if (!downgraded && requestedProfile === '1440p' && slowSamples >= 5) {
        requestedProfile = '1080p';
        downgraded = true;
        goodSamples = 0;
        sendStreamProfile();
      } else if (downgraded && settled && measuredVideo?.fps !== null && measuredVideo.fps >= 50
                 && measuredVideo.dropRatio !== null && measuredVideo.dropRatio <= 0.03) {
        if (++goodSamples >= 20 && viewportSizeKey !== null) {
          const [vpWidth, vpHeight, vpDpr] = viewportSizeKey.split(':').map(Number);
          requestedProfile = chooseTwinStreamProfile(vpWidth, vpHeight, vpDpr);
          downgraded = false;
          goodSamples = 0;
          sendStreamProfile();
        }
      } else {
        goodSamples = 0;
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
    const presentationBuffering = Boolean(streamCtl?.client?.lastState?.presentation_buffering);
    // 流在出帧时 presentation_buffering 只剩"仿真未开始"一种来源（CREATED 会话 sim_time 不动，player 端 Buffering 恒真）——如实标注待启动，不误导为网络缓冲
    const bufferingLabel = !presentationBuffering ? '' : (measuredVideo?.fps ?? 0) > 0 ? ' · 待启动' : ' · 缓冲中';
    statusEl.textContent = `${hud.signal.toUpperCase()} · ${width && height ? `${width}×${height}` : '—'} · ${measuredVideo?.fps == null ? '—' : measuredVideo.fps.toFixed(0)} FPS · ${measuredVideo?.bitrateMbps == null ? '—' : measuredVideo.bitrateMbps.toFixed(1)} Mb/s${bufferingLabel}`;
    const landscapeInfo = streamCtl?.client?.lastState?.landscape;
    if (staticRegion && landscapeInfo?.displayable && landscapeInfo.state === 'failed')
      statusEl.textContent += ' · 地形服务不可用 · 本地地形';
    else if (staticRegion && (landscapeInfo?.refining || (landscapeInfo?.displayable && !landscapeInfo.ready)))
      statusEl.textContent += ` · 细节加载 ${Math.round(landscapeInfo.progress)}%`;
    // dt-yolo:左上 HUD 拼 YOLO 状态(在算=ON 绿字;勾了没数据=OFF;未勾=无后缀)。
    const yoloSuffix = situation?.yoloStatus?.() ?? '';
    if (yoloSuffix) {
      const chip = document.createElement('span');
      chip.className = 'twin-yolo-hud' + (yoloSuffix.endsWith('ON') ? ' twin-yolo-hud--on' : '');
      chip.textContent = ' ' + yoloSuffix;
      statusEl.append(chip);
    }
    const ms = value => Number.isFinite(value) ? value.toFixed(1) + ' ms' : '—';
    statusEl.title = [
      `视频冻结 ${measuredVideo?.freezeCount ?? '—'} 次；最长帧间隔 ${ms(videoGapMaxMs)}`,
      `标牌隐藏 ${situation?.diagnostics?.hiddenEvents ?? 0} 次；最长 ${ms(situation?.diagnostics?.hiddenMaxMs)}`,
      `丢包 ${measuredVideo?.packetsLost ?? '—'}；NACK ${measuredVideo?.nackCount ?? '—'}；重传 ${measuredVideo?.retransmittedPacketsReceived ?? '—'}`,
      `解码 ${ms(measuredVideo?.decodeMs)}；缓冲 ${ms(measuredVideo?.jitterBufferMs)}；接收至解码完成 ${ms(measuredVideo?.processingMs)}`,
      `主线程长任务 ${longTasks} 次；最长 ${ms(longTaskMaxMs)}；地形加载 ${ms(landscapeReadyMs)}`,
    ].join('\n');
    if (staticRegion && landscapeInfo) {
      const mib = bytes => Number.isFinite(bytes) ? (bytes / 1048576).toFixed(1) + ' MiB' : '—';
      statusEl.title += '\n' + [
        `区域 ${(landscapeInfo.extent_m / 1000).toFixed(0)} × ${(landscapeInfo.extent_m / 1000).toFixed(0)} km`,
        `瓦片缓存预算 ${mib(landscapeInfo.cache_budget_bytes)}（非实际占用）`,
        `Unity 网格 ${mib(landscapeInfo.mesh_memory_bytes)}；纹理 ${mib(landscapeInfo.texture_memory_bytes)}（不含 SDK 全部原生缓存）`,
        `Unity 进程内存 ${mib(landscapeInfo.process_rss_bytes)}；驻留网格 ${landscapeInfo.meshes_resident}`,
      ].join('\n');
    }
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
      if (landscapeReadyMs === null && landscape?.ready && video?.readyState >= 2) landscapeReadyMs = now() - viewportOpenedAt;
      if (video.style) video.style.visibility = !streamCtl?.client?.lastState || !landscapeIsDisplayable(landscape) ? 'hidden' : '';
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
    // dt-yolo 收编轮:左下"SENSOR EO"角标移除(右上 EO/IR/LD 按钮已表意)。
    // P2: IR 单键承载极性家族——ir/ir_whitehot/ir_blackhot 均点亮 IR 键；
    // pick 护窗内与 pick 不一致的 stale echo 被忽略（race fix），护窗超时或
    // echo 追上 pick 后恢复 echo 权威（Unity 拒值时自愈）。
    // P2 评审修复（极性竞态，与 twin-view.js 同款）：无 echo（§5 重连轮询窗口
    // 新 client 的 lastState=null）≠ 'eo' echo——不折回，保住极性 pick 供
    // attachLiveWhenReady 的重发；真 echo 仍恢复权威。
    if (streamCtl?.client?.lastState) {
      const echoed = projectSensorMode(streamCtl.client.lastState);
      if (sensorEchoGuard.value !== null && echoed !== sensorEchoGuard.value && now() < sensorEchoGuard.until) {
        // stale pre-pick echo — keep the optimistic pick.
      } else {
        sensorEchoGuard = { value: null, until: 0 };
        currentSensorMode = echoed;
      }
    }
    const mode = currentSensorMode;
    if (sensorGroup) {
      sensorGroup.querySelectorAll('[data-twin-sensor]').forEach(button => {
        const value = button.dataset.twinSensor;
        const on = value === 'ir' ? TWIN_SENSOR_IR_MODES.includes(mode) : value === mode;
        button.classList.toggle('active', on);
        button.setAttribute('aria-pressed', String(on));
      });
    }
    publishDebug();
  }

  function bind() {
    linkToggle?.addEventListener('change', onLinkToggle);
    // P3-S2 (spec #90): sensor-mode buttons — optimistic pick + send; the ~1Hz
    // state echo reasserts the authoritative mode (renderHud). P2: IR 键再点
    // 循环白热/黑热（nextSensorMode 展开极性家族）。
    sensorGroup?.querySelectorAll('[data-twin-sensor]').forEach(button => {
      button.addEventListener('click', () => {
        const value = nextSensorMode(currentSensorMode, button.dataset.twinSensor);
        if (!TWIN_SENSOR_MODES.includes(value)) return;
        const mode = value;
        currentSensorMode = mode;
        sensorEchoGuard = { value: mode, until: now() + TWIN_SENSOR_ECHO_GUARD_MS }; // P2 race fix
        if (sensorGroup) {
          sensorGroup.querySelectorAll('[data-twin-sensor]').forEach(other => {
            const otherValue = other.dataset.twinSensor;
            const on = otherValue === 'ir' ? TWIN_SENSOR_IR_MODES.includes(mode) : otherValue === mode;
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
    if (scheduler.requestAnimationFrame) animationFrame = scheduler.requestAnimationFrame(observeAnimationFrame);
    if (globalThis.PerformanceObserver?.supportedEntryTypes?.includes('longtask')) {
      longTaskObserver = new PerformanceObserver(list => {
        if (documentRef?.visibilityState === 'hidden') return;
        for (const entry of list.getEntries()) { longTasks++; longTaskMaxMs = Math.max(longTaskMaxMs, entry.duration); }
      });
      longTaskObserver.observe({ type: 'longtask' });
    }
    if (globalThis.PerformanceObserver?.supportedEntryTypes?.includes('long-animation-frame')) {
      longFrameObserver = new PerformanceObserver(list => {
        if (documentRef?.visibilityState === 'hidden') return;
        for (const entry of list.getEntries()) {
          longFrames.push({ start: entry.startTime, duration: entry.duration, blocking: entry.blockingDuration,
            scripts: entry.scripts.map(script => ({ duration: script.duration, source: script.sourceURL,
              function: script.sourceFunctionName, invoker: script.invoker, layout: script.forcedStyleAndLayoutDuration })) });
          if (longFrames.length > 5) longFrames.shift();
        }
      });
      longFrameObserver.observe({ type: 'long-animation-frame' });
    }
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
    if (animationFrame !== null) scheduler.cancelAnimationFrame?.(animationFrame);
    longTaskObserver?.disconnect();
    longFrameObserver?.disconnect();
    themeObserver = null;
    closeLink();
    cameraControls.destroy();
    if (video?.style) video.style.visibility = '';
    situation?.destroy();
    for (const type of Object.keys(pointerHubs)) video?.removeEventListener?.(type, dispatchPointer(type));
    documentRef?.removeEventListener?.('click', onPresetButtonClick, true);
    video?.removeEventListener?.('dblclick', recenterCamera);
    video?.removeEventListener?.('dragstart', swallowDragStart);
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
        const startPath = staticRegion ? '/api/geography/qingdao/twin/start' : `/api/sessions/${encodeURIComponent(runId)}/twin/start`;
        const response = await fetchRef(`${backendBase}${startPath}`, {
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
