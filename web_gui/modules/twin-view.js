/**
 * Evaluation > Digital Twin — sealed-run twin replay over the local Unity pixel
 * stream (P2-S3, spec #89; contract sango/Docs/contracts/twin-bridge-v1.md).
 *
 * Owns ONLY twin presentation state: the selected Run, the URS pixel-stream
 * connection and the twin-bridge control channel. The web page stays the sole
 * UI orchestration authority — Unity pulls its own data from the backend
 * (attach carries backend_base; the browser never relays telemetry) and this
 * module drives it with hello/attach/clock(~10Hz)/camera/theme/detection.
 *
 * Pure seams for node --test (no DOM/WebRTC): createTwinBridgeClient (message
 * construction/parsing == frozen contract literals), createTwinClockDriver
 * (ReplayClock → 10Hz clock messages, throttled), projectTwinHud (HUD render),
 * themeValue + observeTheme (data-obc-theme sync).
 */

import { createReplayClock, ReplayPlayState } from './replay-clock.js?v=20260918-buffering';
import { projectReplayRunRows } from './replay-runs.js?v=20260916-replay-layout-v4';

// Frozen contract constants (twin-bridge-v1.md §1/§2).
export const TWIN_BRIDGE_PROTOCOL = 'twin-bridge@1';
export const TWIN_BRIDGE_CHANNEL_LABEL = 'twin-bridge';
export const TWIN_SIGNALING_URL_DEFAULT = 'ws://127.0.0.1:8080';
export const TWIN_CAMERA_PRESETS = ['bridge', 'bow', 'chase', 'top', 'overlook'];
export const TWIN_THEMES = ['day', 'dusk', 'night'];
export const TWIN_REPLAY_RATES = [0.5, 1, 5, 20];
// P3-S0 sensor_mode 词汇（契约 §2/§8 演进，spec #90）：主视口 eo=可见光（默认）/ ir=黑白热像 /
// lidar=点云视角；雷达 PPI/AIS 为 web 面板态不经此桥。
export const TWIN_SENSOR_MODES = ['eo', 'ir', 'lidar'];
export const TWIN_SENSOR_MODE_DEFAULT = 'eo';
// P3-S3 按钮组标签（spec #90）：lidar 自 S3 起为真实现（Unity LidarViewPass 点云视角），
// S2 的 "LiDAR·S3" pending 徽标移除——三键均可用（契约 §8 台账）。
export const TWIN_SENSOR_MODE_LABELS = { eo: 'EO', ir: 'IR', lidar: 'LiDAR' };
// P2-S4 联动 spike（契约 §8）：Cesium 相机变更上报阈值（camera.changed percentageChanged）。
export const TWIN_LINK_CHANGE_PERCENT = 0.01;

// Clock-message pacing: contract §2 fixes ~10Hz while PLAYING.
const CLOCK_INTERVAL_MS = 100;
// HUD freshness: Unity state is ~1Hz; no message for this long degrades the signal.
const STATE_STALE_MS = 3000;

function formatTime(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : '—';
}

/**
 * data-obc-theme → twin-bridge theme vocabulary (identity map over the frozen
 * set; unknown attributes keep the previous value at the call site).
 */
export function themeValue(attribute) {
  return TWIN_THEMES.includes(attribute) ? attribute : null;
}

/**
 * MutationObserver bridging the OpenBridge theme attribute to the bridge.
 * Returns the observer (callers may disconnect); callback receives the theme
 * value or null for unknown attributes.
 */
export function observeTheme(documentRef, callback) {
  const observer = new MutationObserver(() => {
    callback(themeValue(documentRef.documentElement?.getAttribute?.('data-obc-theme')));
  });
  observer.observe(documentRef.documentElement, { attributes: true, attributeFilter: ['data-obc-theme'] });
  return observer;
}

/**
 * CesiumJS camera pose → twin-bridge `camera_free` payload (P2-S4, contract
 * §8; one-way Cesium master → twin slave spike, default off). Pure fold —
 * `toEastNorth(lonDeg, latDeg)` is the injected projector (proj4 inverse;
 * global UTM metres in the attached.anchor frame). Heading (compass rad,
 * 0 = north, clockwise) maps 1:1 to Unity yaw (scene +z north / +x east);
 * Cesium pitch (negative = down) carries unchanged per the contract
 * "pitch 负 = 俯"; Cesium fov is horizontal radians when the pane is wider
 * than tall (vertical otherwise) → Unity vertical degrees.
 */
export function cameraFreePose({ lonDeg, latDeg, heightM, headingRad, pitchRad, fovRad, aspect = 1 }, toEastNorth) {
  const [east, north] = toEastNorth(lonDeg, latDeg);
  const yawDeg = ((headingRad * 180 / Math.PI) % 360 + 360) % 360;
  const pitchDeg = pitchRad * 180 / Math.PI;
  const fovDeg = (aspect >= 1
    ? 2 * Math.atan(Math.tan(fovRad / 2) / aspect)
    : fovRad) * 180 / Math.PI;
  return { east, north, height_m: heightM, yaw_deg: yawDeg, pitch_deg: pitchDeg, fov_deg: fovDeg };
}

/**
 * P3-S2 (spec #90): authoritative sensor_mode from a Unity `state` echo.
 * Unknown/missing field (old Unity build) falls back to the contract default.
 */
export function projectSensorMode(state) {
  const echo = state?.sensor_mode;
  return TWIN_SENSOR_MODES.includes(echo) ? echo : TWIN_SENSOR_MODE_DEFAULT;
}

/**
 * P3-S2 (spec #90) sensor-mode button group projection; P3-S3 un-pends lidar
 * (真实现 — contract §8 台账). `active` = the authoritative mode (state echo,
 * or the optimistic local pick before Unity answers).
 */
export function sensorModeItems(active = TWIN_SENSOR_MODE_DEFAULT) {
  const mode = TWIN_SENSOR_MODES.includes(active) ? active : TWIN_SENSOR_MODE_DEFAULT;
  return TWIN_SENSOR_MODES.map(value => ({
    value,
    label: TWIN_SENSOR_MODE_LABELS[value] ?? value.toUpperCase(),
    active: value === mode,
  }));
}

/**
 * URS pixel stream + twin-bridge DataChannel receiver, shared by the
 * Evaluation twin viewport and the Deployment live twin (P2-S4 extraction —
 * identical official-receiver flow; S3 README §4②: the receiver's
 * createDataChannel('input') negotiationneeded is what wakes the Unity side
 * under the public signaling webapp). `onChannel(client)` fires when the
 * twin-bridge DataChannel opens — the page sends hello (here) and re-sends
 * attach/current controls there (contract §5 reconnect semantics);
 * `onState('connecting'|'streaming'|'idle')` mirrors connection transitions.
 * Pure seam: tests inject nothing — the URS imports are dynamic (browser-only)
 * and the bridge client behind `client` is the tested contract seam.
 */
export function createTwinStreamClient({
  video = null,
  signalingUrl = TWIN_SIGNALING_URL_DEFAULT,
  page = 'web_gui',
  now = () => Date.now(),
  onChannel = () => {},
  onState = () => {},
} = {}) {
  let stream = null;
  let client = null;
  let connectionState = 'idle';

  function setState(next) {
    connectionState = next;
    onState(next);
  }

  async function ensureStream() {
    if (stream) return stream;
    setState('connecting');
    const [{ RenderStreaming }, { WebSocketSignaling }] = await Promise.all([
      import('../vendor/urs/renderstreaming.js'),
      import('../vendor/urs/signaling.js'),
    ]);
    const signaling = new WebSocketSignaling(1000, signalingUrl);
    const rs = new RenderStreaming(signaling, { sdpSemantics: 'unified-plan', iceServers: [] });
    rs.onConnect = id => {
      stream.connectionId = id;
      // Official receiver flow (S3 spike page main.js does the same): the
      // receiver creates its data channel on connect — its negotiationneeded
      // is what triggers the SDP offer that wakes the Unity side in the
      // webapp's public signaling mode (connect is only echoed to the sender
      // there). Unity's Broadcast has no 'input' handler in the twin scene, so
      // the channel is a no-op on the far side; camera control goes via
      // twin-bridge.
      try {
        rs.createDataChannel('input');
      } catch { /* peer may be gone during reconnect */ }
      setState('streaming');
    };
    rs.onDisconnect = async () => {
      setState('idle');
      stream = null;
      if (video) video.srcObject = null;
    };
    rs.onTrackEvent = data => {
      if (!video) return;
      video.srcObject = new MediaStream([data.track]);
      video.play?.().catch(() => { /* autoplay policy: element is muted */ });
    };
    rs.onAddChannel = data => {
      if (data.channel?.label !== TWIN_BRIDGE_CHANNEL_LABEL || !stream) return;
      stream.channel = data.channel;
      const channelFacade = {
        send: json => data.channel.send(json),
        isOpen: () => data.channel.readyState === 'open',
      };
      if (!client) client = createTwinBridgeClient({ channel: channelFacade, now, page });
      else client.bindChannel(channelFacade);
      data.channel.onmessage = event => client?.onMessage(event.data);
      client.sendHello(`${page === 'web_gui' ? 'twin' : page}-${now()}`);
      onChannel(client);
    };
    stream = { renderstreaming: rs, connectionId: null, channel: null };
    await rs.start();
    await rs.createConnection();
    return stream;
  }

  /** Tear the pixel stream down (PC stop + video unbind); the channel dies with it. */
  async function close() {
    const current = stream;
    stream = null;
    if (video) video.srcObject = null;
    if (!current) return;
    try { await current.renderstreaming.stop?.(); } catch { /* already gone */ }
  }

  return {
    ensureStream,
    close,
    get client() { return client; },
    get connectionState() { return connectionState; },
    get stream() { return stream; },
  };
}

/**
 * twin-bridge-v1 message client over an injected channel. The channel is
 * `{ send(json), isOpen() }` — in the page it wraps the URS RTCDataChannel;
 * tests inject a recording fake. Inbound messages go through `onMessage`.
 */
export function createTwinBridgeClient({ channel = null, now = () => Date.now(), page = 'web_gui' } = {}) {
  let sent = 0;
  let received = 0;
  let helloed = false;
  let ready = false;
  let attached = null; // last attached message
  let lastState = null; // last state message
  let lastError = null;
  let errorCount = 0;
  let lastClockSentMs = null;
  let lastClockState = null;
  const samples = []; // { at, playhead, sim } — state echoes (E2E 对拍 recording)

  function send(payload) {
    const json = JSON.stringify(payload);
    if (!channel || !channel.isOpen()) return null;
    channel.send(json);
    sent += 1;
    return json;
  }

  return {
    get sent() { return sent; },
    get received() { return received; },
    get ready() { return ready; },
    get attached() { return attached; },
    get lastState() { return lastState; },
    get lastError() { return lastError; },
    get errorCount() { return errorCount; },
    get samples() { return samples; },
    get helloed() { return helloed; },

    bindChannel(nextChannel) {
      channel = nextChannel;
    },

    sendHello(nonce = page) {
      helloed = true;
      return send({ type: 'hello', protocol: TWIN_BRIDGE_PROTOCOL, page: nonce });
    },

    sendAttach({ runId, backendBase, tStart, tEnd, trustedTEnd, mode = 'replay' }) {
      const payload = { type: 'attach', run_id: runId, mode, backend_base: backendBase };
      if (mode === 'replay') {
        payload.replay = { t_start: tStart, t_end: tEnd, trusted_t_end: trustedTEnd };
      }
      return send(payload);
    },

    sendDetach() {
      return send({ type: 'detach' });
    },

    /**
     * Contract §2: ~10Hz while PLAYING; PAUSED/ENDED at least once per
     * transition; rate changes go out immediately (`force`). Returns the sent
     * json (or null when throttled/closed).
     */
    sendClock(playhead, rate, state, { force = false } = {}) {
      if (!channel || !channel.isOpen()) return null;
      const at = now();
      const transition = state !== lastClockState;
      if (!force && !transition && state !== 'PLAYING') return null;
      if (!force && !transition && state === 'PLAYING' && lastClockSentMs !== null && at - lastClockSentMs < CLOCK_INTERVAL_MS) {
        return null;
      }
      lastClockSentMs = at;
      lastClockState = state;
      return send({ type: 'clock', playhead_s: playhead, rate, state });
    },

    sendCamera(preset) {
      return send({ type: 'camera', preset });
    },

    /**
     * P2-S4 演进（契约 §8，只加字段）：联动 spike 的自由位姿——单向 Cesium 主→Twin 从，
     * web 侧默认关（Deployment twin 态专属）。pos 为全域 UTM 米（attached.anchor 同框架）。
     */
    sendCameraFree({ east, north, height_m, yaw_deg, pitch_deg, fov_deg }) {
      return send({ type: 'camera_free', pos: { east, north, height_m }, yaw_deg, pitch_deg, fov_deg });
    },

    sendTheme(value) {
      return send({ type: 'theme', value });
    },

    sendDetection(enabled, source) {
      return send({ type: 'detection', enabled, source });
    },

    /**
     * P3-S0 演进（契约 §8，只加 type）：主视口传感器模式。词汇 = TWIN_SENSOR_MODES；
     * Unity 侧 state.sensor_mode 回显（默认 eo）。接线（工具条按钮组）属 S2。
     */
    sendSensorMode(value) {
      return send({ type: 'sensor_mode', value });
    },

    /** Inbound Unity→web frame. Returns the parsed message; unknown/malformed tolerated. */
    onMessage(data) {
      received += 1;
      let message;
      try {
        message = JSON.parse(data);
      } catch {
        return null;
      }
      switch (message?.type) {
        case 'ready':
          ready = true;
          break;
        case 'attached':
          attached = message;
          break;
        case 'state':
          message._receivedAt = now(); // HUD staleness (projectTwinHud)
          lastState = message;
          samples.push({ at: now(), sim: Number(message.sim_time) });
          if (samples.length > 600) samples.shift();
          break;
        case 'error':
          lastError = message;
          errorCount += 1;
          break;
        default:
          break; // 演进只加字段：未知 type 宽松忽略（契约 §1）
      }
      return message;
    },
  };
}

/**
 * Maps a ReplayClock-like object onto the bridge clock channel at contract
 * cadence. `clock` needs `{ playhead, rate, state }`; scheduler is injectable
 * `{ setInterval, clearInterval }` for deterministic tests.
 */
export function createTwinClockDriver({ clock, client, scheduler = globalThis, intervalMs = CLOCK_INTERVAL_MS } = {}) {
  let timerId = null;
  let bridge = client; // rebound by the page once the channel opens (`client` setter)
  function tick({ force = false } = {}) {
    if (!clock || !bridge) return;
    bridge.sendClock(clock.playhead, clock.rate, clock.state, { force });
  }
  return {
    get running() { return timerId !== null; },
    set client(next) { bridge = next; },
    get client() { return bridge; },
    start() {
      if (timerId !== null) return;
      tick(); // state transitions (PLAYING) go out immediately
      timerId = scheduler.setInterval(() => tick(), intervalMs);
    },
    stop() {
      if (timerId === null) return;
      scheduler.clearInterval(timerId);
      timerId = null;
      tick(); // PAUSED/ENDED transition message
    },
    /** Immediate send after seek/rate changes (bypasses the PLAYING throttle). */
    pulse() {
      tick({ force: true });
    },
  };
}

/**
 * Pure HUD projection for the twin viewport status chip.
 * `connection`: 'idle' | 'connecting' | 'streaming' (URS PC up)
 * `nowMs`: wall clock for staleness; falls back to the web playhead when no
 * Unity state has arrived (stream-only mode).
 */
export function projectTwinHud({ connection = 'idle', client = null, playhead = null, nowMs = Date.now() } = {}) {
  const state = client?.lastState ?? null;
  const attached = client?.attached ?? null;
  const error = client?.lastError ?? null;
  const stale = !state || (nowMs - (state._receivedAt ?? nowMs)) > STATE_STALE_MS;
  let signal = 'idle';
  if (error || state?.stream?.state === 'down') signal = 'down';
  else if (state && !stale && state.stream?.state === 'degraded') signal = 'degraded';
  else if (state && !stale) signal = 'ok';
  else if (state || attached) signal = 'degraded';

  const sim = state && !stale && Number.isFinite(Number(state.sim_time)) ? Number(state.sim_time) : null;
  const fps = state && !stale && Number.isFinite(Number(state.fps)) ? Number(state.fps) : null;
  const latency = state && !stale && Number.isFinite(Number(state.stream?.latency_ms)) ? Number(state.stream.latency_ms) : null;

  let statusLine = 'TWIN IDLE';
  if (error) statusLine = `TWIN ERROR · ${error.code}`;
  else if (connection === 'connecting') statusLine = 'TWIN CONNECTING…';
  else if (connection === 'streaming' && !attached) statusLine = 'TWIN ATTACHING…';
  else if (attached && !state) statusLine = 'TWIN ATTACHED · AWAITING STATE';
  else if (attached && state) statusLine = `TWIN LIVE · SIGNAL ${signal.toUpperCase()}`;
  return { signal, fps, latencyMs: latency, simTime: sim ?? playhead, statusLine };
}

// ── DOM wiring (page shell only; tests drive the pure seams above) ──────────

function twinTableColumns(documentRef) {
  return [
    { key: 'run', label: 'Run' },
    { key: 'scenario', label: 'Scenario' },
    { key: 'algorithm', label: 'Algorithm' },
    { key: 'frames', label: 'Frames' },
    { key: 'simTime', label: 'Sim time (s)' },
    { key: 'replayEvidence', label: 'Replay Status' },
    {
      key: 'action', label: 'Action', headerType: 'Narrow', renderCell: (_value, _row, rowId) => {
        const container = documentRef.createElement('div');
        container.style.cssText = 'display:flex;align-items:center;justify-content:center;gap:8px;width:100%;';
        const button = documentRef.createElement('obc-button');
        button.setAttribute('variant', 'normal');
        button.setAttribute('fullwidth', '');
        button.setAttribute('aria-label', `Open digital twin ${rowId.slice(0, 8)}`);
        button.style.cssText = 'flex:1 1 0;min-width:0;width:100%;';
        button.textContent = 'Twin';
        button.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          controller?.openRun(rowId);
        });
        container.append(button);
        return container;
      },
    },
  ];
}

function regularCell(text) {
  return { type: 'regular', text: String(text ?? '—'), noWrap: true, align: 'center' };
}

function projectTwinTableRows(rows) {
  return rows.map(row => ({
    id: row.runId,
    run: regularCell(row.runId.slice(0, 8)),
    scenario: regularCell(row.scenario),
    algorithm: regularCell(row.algorithm),
    frames: regularCell(row.frameCount === null ? '—' : row.frameCount),
    simTime: regularCell(row.tEnd === null ? '—' : Number(row.tEnd).toFixed(1)),
    replayEvidence: regularCell(row.label),
    action: { type: 'regular', text: '' },
  }));
}

/** Replay descriptor → playable range (mirrors evaluation-replay.replayRange semantics, twin subset). */
export function twinReplayRange(facts = {}) {
  const state = String(facts.state ?? 'UNAVAILABLE').toUpperCase();
  const rawStart = facts.t_start;
  const rawEnd = state === 'INCOMPLETE' ? facts.trusted_t_end : facts.t_end;
  if (rawStart === null || rawStart === undefined || rawEnd === null || rawEnd === undefined) return null;
  const start = Number(rawStart);
  const end = Number(rawEnd);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
  if (state === 'READY') return { start, end };
  return state === 'INCOMPLETE' && facts.seekable !== false ? { start, end } : null;
}

let controller = null;

export function createTwinViewController({
  documentRef = globalThis.document,
  fetchRef = globalThis.fetch,
  signalingUrl = TWIN_SIGNALING_URL_DEFAULT,
  nowFn = () => Date.now(),
  scheduler = globalThis,
} = {}) {
  const el = id => documentRef.getElementById(id);
  let client = null; // twin-bridge client (bound once the channel opens)
  let clock = null; // ReplayClock (shared semantics with the Replay view)
  let clockDriver = null;
  let themeObserver = null;
  let streamCtl = null; // createTwinStreamClient (shared URS receiver, P2-S4 extraction)
  let connectionState = 'idle';
  let runId = null;
  let range = null;
  let generation = 0;
  let debug = null;
  // Twin runs pagination (same vocabulary as replay-runs.js: 10/20/50 rows per page).
  const TWIN_PAGE_SIZES = [10, 20, 50];
  let twinRunsRows = [];
  let twinRunsPage = 1;
  let twinRunsPageSize = TWIN_PAGE_SIZES[0];

  function setConnectionState(next) {
    connectionState = next;
    publishDebug();
  }

  function publishDebug() {
    if (!debug) return;
    debug.connection = connectionState;
    // P3 fix: stream.channel is the RAW RTCDataChannel (the isOpen() facade lives
    // only inside the bridge client), so channelOpen must read readyState — the
    // old `channel.isOpen?.()` resolved to undefined and always reported false.
    debug.channelOpen = streamCtl?.stream?.channel?.readyState === 'open';
    debug.ready = client?.ready ?? false;
    debug.attached = client?.attached ?? null;
    debug.lastState = client?.lastState ?? null;
    debug.sent = client?.sent ?? 0;
    debug.received = client?.received ?? 0;
    debug.runId = runId;
    debug.playhead = clock?.playhead ?? null;
    debug.rate = clock?.rate ?? null;
    debug.clockState = clock?.state ?? null;
    debug.simTime = client?.lastState?.sim_time ?? null;
    debug.camera = client?.lastState?.camera ?? null;
    debug.sensorMode = client?.lastState?.sensor_mode ?? null;
  }

  function ensureDebugHandle() {
    if (debug) return debug;
    debug = { samples: [] };
    globalThis.__twinBridge = debug;
    return debug;
  }

  // ── URS pixel stream + bridge channel (shared receiver, P2-S4 extraction) ──

  function ensureStream() {
    if (!streamCtl) {
      streamCtl = createTwinStreamClient({
        video: el('twinVideo'),
        signalingUrl,
        page: 'web_gui-twin',
        now: nowFn,
        onChannel: bound => {
          client = bound;
          bindClockClient();
          // Re-attach after a page-level reconnect (contract §5: hello + attach
          // + current controls; the hello itself went out inside the receiver).
          if (runId && range) queueAttachWhenReady();
          publishDebug();
        },
        onState: setConnectionState,
      });
    }
    return streamCtl.ensureStream();
  }

  function requireClient() {
    return client && client.ready ? client : null;
  }

  /**
   * Contract order is hello → ready → attach; the URS channel can open after
   * openRun resolved, so park the attach until Unity answers `ready`.
   */
  function queueAttachWhenReady(timeoutMs = 15000) {
    const deadline = Date.now() + timeoutMs;
    const timer = setInterval(() => {
      if (client?.ready) {
        clearInterval(timer);
        sendAttach();
        sendCurrentControls(); // align Unity with the page state (camera/theme/detection)
      } else if (Date.now() > deadline) {
        clearInterval(timer);
      }
    }, 100);
  }

  function sendAttach() {
    const bridge = requireClient();
    if (!bridge || !runId || !range) return;
    bridge.sendAttach({
      runId,
      backendBase: globalThis.location?.origin ?? 'http://127.0.0.1:8010',
      tStart: range.start,
      tEnd: range.end,
      trustedTEnd: range.end,
    });
    publishDebug();
  }

  function sendCurrentControls() {
    const bridge = requireClient();
    if (!bridge) return;
    const theme = themeValue(documentRef.documentElement?.getAttribute?.('data-obc-theme'));
    if (theme) bridge.sendTheme(theme);
    const detection = el('twinDetectionSelect')?.value ?? 'truth';
    if (detection !== 'off') bridge.sendDetection(true, detection);
    else bridge.sendDetection(false, 'truth');
    const active = el('twinCameraGroup')?.querySelector('[data-twin-camera].active');
    if (active) bridge.sendCamera(active.dataset.twinCamera);
    // P3-S2 (spec #90): sensor_mode rides the §5 reconnect realignment too.
    const sensorActive = el('twinSensorGroup')?.querySelector('[data-twin-sensor].active');
    bridge.sendSensorMode(sensorActive?.dataset.twinSensor ?? TWIN_SENSOR_MODE_DEFAULT);
  }

  // ── P3-S2 sensor-mode button group (spec #90; contract §2/§8) ─────────────

  /**
   * Reflects a mode onto the button group + HUD chip. The state echo is the
   * authority (renderHud); the click handler calls this optimistically with
   * the picked value so the UI answers immediately.
   */
  function applySensorMode(mode, { chipEl } = {}) {
    const group = el('twinSensorGroup');
    if (group) {
      group.querySelectorAll('[data-twin-sensor]').forEach(button => {
        const on = button.dataset.twinSensor === mode;
        button.classList.toggle('active', on);
        button.setAttribute('aria-pressed', String(on));
      });
    }
    const chip = chipEl ?? el('twinSensorMode');
    if (chip) {
      const item = sensorModeItems(mode).find(entry => entry.value === mode);
      chip.textContent = `SENSOR ${item?.label ?? mode.toUpperCase()}`;
    }
  }

  // ── run selection + viewer flow ───────────────────────────────────────────

  async function refreshRuns() {
    const status = el('twinRunsStatus');
    const table = el('twinRunsTable');
    if (!table) return;
    if (status) status.textContent = 'LOADING';
    let rows = [];
    try {
      const response = await fetchRef('/api/runs?limit=50&summary=true');
      if (!response.ok) throw new Error(`status ${response.status}`);
      const entries = await response.json();
      rows = projectReplayRunRows(entries, null); // same source/semantics as the Replay list
    } catch {
      rows = [];
    }
    // P3: twin runs paginate like the Replay list (same footer controls and page
    // sizes) — probe/backlog "target run pushed to page 2" no longer hides rows.
    twinRunsRows = rows;
    renderTwinRunsPage();
    if (status) status.textContent = rows.length ? `${rows.length} RUNS` : 'NO RUNS';
  }

  // ── twin runs pagination (mirrors replay-runs.js semantics; P2 P3 residue) ──

  function twinPageCount() {
    return Math.max(1, Math.ceil(twinRunsRows.length / twinRunsPageSize));
  }

  function renderTwinRunsPage() {
    twinRunsPage = Math.max(1, Math.min(twinRunsPage, twinPageCount()));
    const table = el('twinRunsTable');
    if (table) {
      const pageStart = (twinRunsPage - 1) * twinRunsPageSize;
      table.columns = twinTableColumns(documentRef);
      table.data = projectTwinTableRows(twinRunsRows.slice(pageStart, pageStart + twinRunsPageSize));
      table.rowDivider = true;
      table.narrowHeader = true;
      table.showHeader = true;
    }
    const total = twinRunsRows.length;
    const first = total === 0 ? 0 : (twinRunsPage - 1) * twinRunsPageSize + 1;
    const last = total === 0 ? 0 : Math.min(twinRunsPage * twinRunsPageSize, total);
    const summary = el('twinRunsPaginationSummary');
    if (summary) summary.textContent = `${first}–${last} of ${total}`;
    const indicator = el('twinRunsPageIndicator');
    if (indicator) indicator.textContent = `${twinRunsPage} / ${twinPageCount()}`;
    const pageSize = el('twinRunsPageSize');
    if (pageSize) pageSize.value = String(twinRunsPageSize);
    const previous = el('twinRunsPrevBtn');
    if (previous) previous.disabled = twinRunsPage <= 1;
    const next = el('twinRunsNextBtn');
    if (next) next.disabled = twinRunsPage >= twinPageCount();
  }

  async function openRun(nextRunId) {
    const gen = ++generation;
    const descriptor = await fetchRef(`/api/runs/${nextRunId}/replay`).then(r => r.json()).catch(() => null);
    if (gen !== generation) return;
    range = twinReplayRange({ ...(descriptor?.replay ?? {}), seekable: descriptor?.capabilities?.seekable });
    if (!range || !descriptor?.run_id) {
      const errorSlot = el('twinError');
      if (errorSlot) {
        errorSlot.textContent = 'This run has no playable twin replay range.';
        errorSlot.hidden = false;
      }
      return;
    }
    runId = descriptor.run_id;
    clock = createReplayClock({ now: nowFn, tStart: range.start, tEnd: range.end });
    clockDriver = createTwinClockDriver({ clock, client, scheduler });
    const runsPanel = el('twinRunsPanel');
    if (runsPanel) runsPanel.hidden = true;
    const viewer = el('twinViewerPanel');
    if (viewer) viewer.hidden = false;
    const cameraGroup = el('twinCameraGroup'); // presets bind to viewer open state
    if (cameraGroup) cameraGroup.hidden = false;
    el('twinRunTitle').textContent = `DIGITAL TWIN · ${runId.slice(0, 8)} · ${descriptor.run?.scenario_id ?? ''} · ${descriptor.run?.executed_algorithm ?? ''}`;
    const timeline = el('twinTimeline');
    timeline.min = String(range.start);
    timeline.max = String(range.end);
    timeline.step = '0.1';
    timeline.value = String(range.start);
    el('twinTimeStart').textContent = `${formatTime(range.start)} s`;
    el('twinTimeTotal').textContent = `${formatTime(range.end)} s`;
    el('twinTimeCurrent').textContent = `${formatTime(range.start)} s`;
    syncPlayButton();
    ensureDebugHandle();
    try {
      await ensureStream();
      if (gen !== generation) return;
      queueAttachWhenReady();
      bindThemeObserver();
    } catch (error) {
      const errorSlot = el('twinError');
      if (errorSlot) {
        errorSlot.textContent = `Twin stream unreachable at ${signalingUrl} — start the local URS webapp and the sango-twin player.`;
        errorSlot.hidden = false;
      }
      setConnectionState('idle');
    }
  }

  function closeViewer() {
    generation += 1;
    const driver = clockDriver;
    clockDriver = null;
    clock?.pause();
    driver?.stop(); // final PAUSED clock message
    client?.sendDetach();
    clock = null;
    const viewer = el('twinViewerPanel');
    if (viewer) viewer.hidden = true;
    const cameraGroup = el('twinCameraGroup'); // presets bind to viewer open state
    if (cameraGroup) cameraGroup.hidden = true;
    const runs = el('twinRunsPanel');
    if (runs) runs.hidden = false;
    const errorSlot = el('twinError');
    if (errorSlot) errorSlot.hidden = true;
  }

  function bindThemeObserver() {
    if (themeObserver || typeof MutationObserver === 'undefined') return;
    themeObserver = observeTheme(documentRef, value => {
      if (value) requireClient()?.sendTheme(value);
    });
  }

  // ── playback controls ─────────────────────────────────────────────────────

  function syncPlayButton() {
    const button = el('twinPlayPauseBtn');
    if (!button) return;
    const playing = clock?.state === ReplayPlayState.PLAYING;
    button.setAttribute('aria-pressed', String(playing));
    button.textContent = playing ? '❚❚' : '▶';
  }

  function bindClockClient() {
    if (clockDriver && client) clockDriver.client = client;
  }

  function playPause() {
    if (!clock) return;
    if (clock.state === ReplayPlayState.PLAYING) clock.pause();
    else clock.play();
    bindClockClient();
    clockDriver?.start(); // start() emits the transition tick; timer only while playing
    if (clock.state !== ReplayPlayState.PLAYING) clockDriver?.stop();
    syncPlayButton();
    publishDebug();
  }

  function seekTo(simTime) {
    if (!clock || !Number.isFinite(Number(simTime))) return;
    clock.seek(Number(simTime));
    bindClockClient();
    clockDriver?.pulse();
    const timeline = el('twinTimeline');
    if (timeline) timeline.value = String(clock.playhead);
    publishDebug();
  }

  function setRate(rate) {
    if (!clock) return;
    clock.setRate(Number(rate));
    bindClockClient();
    clockDriver?.pulse();
    publishDebug();
  }

  function renderHud() {
    const hud = projectTwinHud({ connection: connectionState, client, playhead: clock?.playhead ?? null, nowMs: nowFn() });
    const chip = el('twinHud');
    if (chip) chip.textContent = `${hud.signal.toUpperCase()} · ${hud.fps === null ? '—' : `${hud.fps.toFixed(0)} FPS`} · ${hud.latencyMs === null ? '—' : `${hud.latencyMs.toFixed(0)} MS`}`;
    const status = el('twinStatusLine');
    if (status) status.textContent = hud.statusLine;
    // P3-S2 (spec #90): state echo is the authority for the sensor mode UI.
    applySensorMode(projectSensorMode(client?.lastState));
    const simSlot = el('twinTimeCurrent');
    if (simSlot && hud.simTime !== null && hud.simTime !== undefined) simSlot.textContent = `${formatTime(hud.simTime)} s`;
    if (clock) {
      const timeline = el('twinTimeline');
      if (timeline && clock.state === ReplayPlayState.PLAYING) timeline.value = String(clock.playhead);
    }
    publishDebug();
  }

  function bindControls() {
    el('twinRunsRefreshBtn')?.addEventListener('click', () => void refreshRuns());
    el('twinRunsPageSize')?.addEventListener('change', event => {
      const candidate = Number(event?.target?.value);
      if (!TWIN_PAGE_SIZES.includes(candidate)) return;
      twinRunsPageSize = candidate;
      twinRunsPage = 1;
      renderTwinRunsPage();
    });
    el('twinRunsPrevBtn')?.addEventListener('click', () => {
      if (twinRunsPage <= 1) return;
      twinRunsPage -= 1;
      renderTwinRunsPage();
    });
    el('twinRunsNextBtn')?.addEventListener('click', () => {
      if (twinRunsPage >= twinPageCount()) return;
      twinRunsPage += 1;
      renderTwinRunsPage();
    });
    el('twinCloseBtn')?.addEventListener('click', closeViewer);
    el('twinPlayPauseBtn')?.addEventListener('click', playPause);
    el('twinStartBtn')?.addEventListener('click', () => seekTo(range?.start ?? 0));
    el('twinTimeline')?.addEventListener('input', event => seekTo(Number(event?.target?.value ?? 0)));
    for (const rate of TWIN_REPLAY_RATES) {
      el(`twinRate${String(rate).replace('.', '')}`)?.addEventListener('click', () => setRate(rate));
    }
    el('twinCameraGroup')?.querySelectorAll('[data-twin-camera]').forEach(button => {
      button.addEventListener('click', () => {
        el('twinCameraGroup')?.querySelectorAll('[data-twin-camera]').forEach(other => {
          other.classList.toggle('active', other === button);
          other.setAttribute('aria-pressed', String(other === button));
        });
        requireClient()?.sendCamera(button.dataset.twinCamera);
        publishDebug();
      });
    });
    // P3-S2 (spec #90): sensor-mode buttons — optimistic pick + send; the ~1Hz
    // state echo reasserts the authoritative mode (renderHud).
    el('twinSensorGroup')?.querySelectorAll('[data-twin-sensor]').forEach(button => {
      button.addEventListener('click', () => {
        const value = button.dataset.twinSensor;
        if (!TWIN_SENSOR_MODES.includes(value)) return;
        applySensorMode(value);
        requireClient()?.sendSensorMode(value);
        publishDebug();
      });
    });
    el('twinDetectionSelect')?.addEventListener('change', event => {
      const value = event?.target?.value ?? 'truth';
      if (value === 'off') requireClient()?.sendDetection(false, 'truth');
      else requireClient()?.sendDetection(true, value);
      publishDebug();
    });
    // Leaving the twin view holds the presentation clock (Unity keeps last state).
    el('evalViewTabReplay')?.addEventListener('click', () => { clockDriver?.stop(); clock?.pause(); syncPlayButton(); });
    el('evalViewTabResults')?.addEventListener('click', () => { clockDriver?.stop(); clock?.pause(); syncPlayButton(); });
    el('evalViewTabEvidence')?.addEventListener('click', () => { clockDriver?.stop(); clock?.pause(); syncPlayButton(); });
    el('evalViewTabHistoricalAIS')?.addEventListener('click', () => { clockDriver?.stop(); clock?.pause(); syncPlayButton(); });
    // HUD refresh (state echo + playhead) at the clock cadence.
    scheduler.setInterval(renderHud, 250);
  }

  bindControls();
  void refreshRuns();

  return {
    openRun,
    closeViewer,
    playPause,
    seekTo,
    setRate,
    refreshRuns,
    renderHud,
    ensureStream,
    publishDebug,
    get debug() { return debug; },
    get client() { return client; },
    get runId() { return runId; },
    get range() { return range; },
    get connectionState() { return connectionState; },
  };
}

// Shell boot: same guard pattern as evaluation-replay.js (absent in tests).
if (typeof document !== 'undefined' && document.getElementById('evalViewTwin')) {
  controller = createTwinViewController();
}
