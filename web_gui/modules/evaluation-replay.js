/**
 * Evaluation > Replay — paused historical inspection host (ticket #71).
 *
 * Owns ONLY replay presentation state (Technical Design §3.3): the selected
 * Run, the sealed evidence descriptor/context/window and the paused playhead.
 * It renders through the EXISTING
 * telemetry-projection.js + situation-display.js modules (own instances, the
 * same semantics Deployment uses) and issues GET reads against /api/runs/*
 * only and never mutates an Active Session.
 */

import { createSituationDisplay } from './situation-display.js';
import { createTelemetryProjection } from './telemetry-projection.js';
import { projectReplayFrame, REPLAY_PRESENTATION_MODE } from './replay-source.js';
import { createReplayClock, ReplayPlayState } from './replay-clock.js?v=20260918-buffering';
// Keep the URL identical to the shell's standalone module tag. Native ESM
// treats query-string variants as different module instances; without this
// pin the catalog and replay host would own different opener registries.
import { setReplayRunOpener } from './replay-runs.js?v=20260916-replay-layout-v4';

// Scrub windows stay small and bounded; the backend enforces the frozen caps.
const SEEK_WINDOW_HALF_SPAN_S = 0.5;
const INITIAL_WINDOW_SPAN_S = 24.0;

// Playback prefetch: bounded frame-count windows ahead of the playhead. The
// span adapts to Replay Speed (so high rates do not refetch every 100 ms) but
// is capped by a frozen frame budget — the whole Run is never loaded.
const PLAYBACK_TICK_MS = 100;
const PREFETCH_FRAME_BUDGET = 240;
const PREFETCH_MIN_SPAN_S = 8.0;

const THREAT_LEVELS = { HIGH: 'danger', LOW: 'warn', CLEAR: 'safe' };
const REPLAY_UI_RATES = [0.5, 1, 5, 20];

function formatTime(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : '—';
}

export function createEvaluationReplayController({
  documentRef = globalThis.document,
  fetchRef = globalThis.fetch,
  displayFactory = null,
  nowFn = () => Date.now(),
  scheduler = null,
} = {}) {
  const schedule = scheduler ?? {
    set: (fn, ms) => setTimeout(fn, ms),
    clear: id => clearTimeout(id),
  };
  const el = id => documentRef.getElementById(id);
  const projection = createTelemetryProjection();

  let runId = null;
  let descriptor = null;
  let context = null;
  let windowDoc = null;
  let playhead = null;
  let selectedTargetId = null;
  let generation = 0;
  let status = 'EMPTY';
  let replayControlsEnabled = false;
  let lastSourceSequence = null;
  let lastSourceSimTime = null;
  let display = null;
  let clock = null;
  let timerId = null;
  let prefetchInFlight = null;
  let nextWindowDoc = null;
  let buffering = false;
  let replayScaleValue = 0.5;
  // #73 event journal: recorded evidence, loaded once per open. Filtering is
  // presentation state; recorded identity/time/order are never rewritten.
  let eventJournal = null;
  let eventFilter = 'ALL';
  let selectedEventId = null;

  function setStatus(next) {
    status = next;
  }

  const EVENT_GLYPHS = {
    PLANNER: 'P',
    RISK_LIFECYCLE: '▲',
    SAFETY_FAILURE: '✕',
    MISSION: '◎',
    HANDOFF: '⇄',
    RUNTIME: '•',
  };
  const CLUSTER_GLYPH = '≡';
  const CLUSTER_MIN_EVENTS = 3;
  const CLUSTER_BUCKET_PCT = 0.5;

  function visibleEvents() {
    if (!eventJournal) return [];
    const rows = eventJournal.events ?? [];
    if (eventFilter === 'ALL') return rows;
    return rows.filter(event => event.category === eventFilter);
  }

  function markerPct(simTime) {
    const start = Number(descriptor?.replay?.t_start) || 0.0;
    const end = trustedEnd();
    const span = Math.max(end - start, 1e-6);
    return Math.max(0, Math.min(100, ((Number(simTime) - start) / span) * 100));
  }

  function renderEventMarkers() {
    const strip = el('replayEventMarkers');
    if (!strip) return;
    const rows = visibleEvents();
    if (!rows.length) {
      strip.replaceChildren();
      strip.textContent = eventJournal && (eventJournal.events ?? []).length
        ? 'NO EVENTS IN THIS FILTER'
        : 'NO RECORDED EVENTS';
      return;
    }
    strip.textContent = '';
    // Visual aggregation only: dense recorded events share one cluster
    // marker; clicking it exposes every underlying event in recorded order.
    const buckets = new Map();
    for (const event of rows) {
      const bucket = Math.round(markerPct(event.sim_time) / CLUSTER_BUCKET_PCT);
      if (!buckets.has(bucket)) buckets.set(bucket, []);
      buckets.get(bucket).push(event);
    }
    const markers = [];
    for (const [bucket, members] of [...buckets.entries()].sort((a, b) => a[0] - b[0])) {
      const button = documentRef.createElement('button');
      button.type = 'button';
      button.className = 'replay-event-marker';
      const positionPct = bucket * CLUSTER_BUCKET_PCT;
      button.dataset.positionPct = String(positionPct);
      button.style.left = `${positionPct}%`;
      const first = members[0];
      if (members.length >= CLUSTER_MIN_EVENTS) {
        button.textContent = CLUSTER_GLYPH;
        button.setAttribute('aria-label', `${members.length} recorded events near ${formatTime(first.sim_time)} s — open to list`);
        button.dataset.cluster = String(members.length);
      } else {
        const category = first.category ?? 'RUNTIME';
        button.textContent = EVENT_GLYPHS[category] ?? EVENT_GLYPHS.RUNTIME;
        button.setAttribute('aria-label', `${category} ${first.type} at ${formatTime(first.sim_time)} s`);
      }
      button.addEventListener('click', () => {
        inspectEvent(members);
      });
      markers.push(button);
    }
    strip.replaceChildren(...markers);
  }

  function inspectEvent(members) {
    selectedEventId = String(members[0].sequence ?? `${members[0].type}@${members[0].sim_time}`);
  }

  /** Frozen navigation semantics: Previous/Next move over the FILTERED
   * recorded set in recorded order; at the first/last event they stay put
   * (no wraparound) and re-select that boundary event. */
  function stepEvent(direction) {
    const rows = visibleEvents();
    if (!rows.length || playhead === null) return;
    const eps = 1e-6;
    let target = null;
    if (direction > 0) {
      target = rows.find(event => Number(event.sim_time) > Number(playhead) + eps) ?? rows[rows.length - 1];
    } else {
      for (const event of rows) {
        if (Number(event.sim_time) < Number(playhead) - eps) target = event;
      }
      target = target ?? rows[0];
    }
    inspectEvent([target]);
    void seek(Number(target.sim_time));
  }

  function setEventFilter(next) {
    eventFilter = String(next ?? 'ALL');
    renderEventMarkers(); // presentation only — the journal is untouched
  }

  function statusLineFor(clockState) {
    if (buffering && clockState === ReplayPlayState.PLAYING) {
      return `BUFFERING · WAITING FOR RECORDED DATA · ${clock.rate}×`;
    }
    if (clockState === ReplayPlayState.PLAYING) {
      return `PLAYING · HISTORICAL REPLAY · ${clock.rate}×`;
    }
    if (clockState === ReplayPlayState.ENDED) {
      return 'REPLAY ENDED · SEEK BACKWARD OR PRESS PLAY TO RESTART';
    }
    return 'PAUSED · HISTORICAL REPLAY';
  }

  function replayRange(facts = descriptor?.replay) {
    const state = String(facts?.state ?? 'UNAVAILABLE').toUpperCase();
    const rawStart = facts?.t_start;
    const rawEnd = state === 'INCOMPLETE' ? facts?.trusted_t_end : facts?.t_end;
    if (rawStart === null || rawStart === undefined || rawEnd === null || rawEnd === undefined) return null;
    const start = Number(rawStart);
    const end = Number(rawEnd);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
    if (state === 'INCOMPLETE') {
      const completeEnd = Number(facts?.t_end);
      if (Number.isFinite(completeEnd) && end > completeEnd) return null;
    }
    return { start, end };
  }

  function trustedEnd() {
    return replayRange()?.end ?? Number.NaN;
  }

  function replayCanPlay() {
    const facts = descriptor?.replay ?? {};
    const state = String(facts.state ?? 'UNAVAILABLE').toUpperCase();
    const range = replayRange(facts);
    if (!range) return false;
    if (state === 'READY') return descriptor?.capabilities?.seekable !== false;
    return state === 'INCOMPLETE' && descriptor?.capabilities?.seekable === true;
  }

  function replayUnavailableMessage() {
    const facts = descriptor?.replay ?? {};
    const state = String(facts.state ?? 'UNAVAILABLE').toUpperCase();
    if (state === 'REDUCED') {
      return `REDUCED EVIDENCE · TRAJECTORY ONLY · PLAYBACK DISABLED${facts.reason ? ` · ${facts.reason}` : ''}`;
    }
    if (state === 'INCOMPLETE') {
      return `REPLAY INCOMPLETE · PLAYBACK DISABLED · ${String(facts.reason ?? 'TRUSTED_PREFIX_UNAVAILABLE')}`;
    }
    if (state === 'CAPTURING') return 'REPLAY PREPARING · RECORDED EVIDENCE IS STILL CAPTURING';
    return `REPLAY UNAVAILABLE${facts.reason ? ` · ${facts.reason}` : ''}`;
  }

  function setIconButton(button, iconName, label) {
    if (!button) return;
    button.replaceChildren(documentRef.createElement(iconName));
    button.setAttribute('aria-label', label);
    button.setAttribute('title', label);
  }

  function syncPlayButton() {
    const button = el('replayPlayPauseBtn');
    if (!button) return;
    const playing = clock?.state === ReplayPlayState.PLAYING;
    setIconButton(button, playing ? 'obi-media-pause' : 'obi-media-play', playing ? 'Pause replay' : 'Play replay');
    button.setAttribute('aria-pressed', String(playing));
  }

  function syncReplayLayerControls(state = display?.getLayerState?.()) {
    if (!state) return;
    for (const input of documentRef.querySelectorAll?.('[data-replay-layer]') ?? []) {
      const layer = state[input.dataset.replayLayer];
      if (!layer) continue;
      input.disabled = !layer.available;
      input.checked = layer.available && Boolean(layer.userVisible);
    }
  }

  function syncReplayOrientationControls(orientation = display?.getOrientation?.()) {
    if (!orientation) return;
    for (const button of documentRef.querySelectorAll?.('[data-replay-map-orientation]') ?? []) {
      const active = button.dataset.replayMapOrientation === orientation;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    }
  }

  function setupReplayChartControls() {
    const layerButton = el('replayChartLayersBtn');
    const panel = el('replayChartDisplayPopover');
    const closeButton = el('replayCloseChartDisplayBtn');
    const syncPopoverState = () => {
      if (layerButton && panel) layerButton.setAttribute('aria-expanded', String(!panel.hidden));
    };
    const closePopover = () => {
      if (!panel) return;
      panel.hidden = true;
      syncPopoverState();
    };
    layerButton?.addEventListener('click', event => {
      event.stopPropagation();
      if (!panel) return;
      panel.hidden = !panel.hidden;
      syncPopoverState();
    });
    closeButton?.addEventListener('click', closePopover);
    panel?.addEventListener('click', event => event.stopPropagation());
    documentRef.addEventListener?.('click', event => {
      if (!panel?.hidden && !panel.contains(event.target) && !event.composedPath?.().includes(layerButton)) closePopover();
    });
    documentRef.addEventListener?.('keydown', event => {
      if (event.key !== 'Escape' || panel?.hidden) return;
      closePopover();
      (layerButton?.shadowRoot?.querySelector('button') || layerButton)?.focus?.();
    });

    const updateScaleInput = () => {
      const input = el('replayChartScaleInput');
      if (input) input.value = replayScaleValue.toFixed(2);
    };
    const zoom = direction => {
      if (direction > 0) display?.zoomIn?.(); else display?.zoomOut?.();
      replayScaleValue = Math.max(0.15, Math.min(1.0, replayScaleValue + direction * 0.05));
      updateScaleInput();
    };
    el('replayZoomInBtn')?.addEventListener('click', () => zoom(1));
    el('replayZoomOutBtn')?.addEventListener('click', () => zoom(-1));
    el('replayChartScaleInput')?.addEventListener('change', event => {
      const next = Number(event?.target?.value);
      if (!Number.isFinite(next)) return updateScaleInput();
      const clamped = Math.max(0.15, Math.min(1.0, next));
      const direction = clamped >= replayScaleValue ? 1 : -1;
      const steps = Math.min(20, Math.max(1, Math.round(Math.abs(clamped - replayScaleValue) / 0.05)));
      for (let index = 0; index < steps; index += 1) {
        if (direction > 0) display?.zoomIn?.(); else display?.zoomOut?.();
      }
      replayScaleValue = clamped;
      updateScaleInput();
    });
    el('replayFitTrafficBtn')?.addEventListener('click', () => display?.fitTraffic?.());
    el('replayRecenterBtn')?.addEventListener('click', () => display?.recenterOwnship?.());
    for (const button of documentRef.querySelectorAll?.('[data-replay-map-orientation]') ?? []) {
      button.addEventListener('click', () => {
        const orientation = button.dataset.replayMapOrientation;
        display?.setOrientation?.(orientation);
        syncReplayOrientationControls(orientation);
      });
    }
    for (const input of documentRef.querySelectorAll?.('[data-replay-layer]') ?? []) {
      input.addEventListener('change', () => {
        display?.setLayerVisible?.(input.dataset.replayLayer, input.checked);
      });
    }
    syncPopoverState();
    syncReplayOrientationControls('north');
    syncReplayLayerControls();
  }

  function setReplayControlsEnabled(enabled) {
    replayControlsEnabled = enabled;
    for (const id of [
      'replayTimeline',
      'replayPlayPauseBtn',
      'replayPrevEventBtn',
      'replayNextEventBtn',
      'replayStartBtn',
      'replayRate05',
      'replayRate1',
      'replayRate5',
      'replayRate20',
    ]) {
      const control = el(id);
      if (control) control.disabled = !enabled;
    }
  }

  async function fetchJson(url) {
    const response = await fetchRef(url, { method: 'GET' });
    if (!response.ok) throw new Error(`replay read failed: ${response.status} ${url}`);
    return response.json();
  }

  function readouts() {
    const range = replayRange();
    el('replayTimeStart').textContent = `${formatTime(range?.start)} s`;
    el('replayTimeCurrent').textContent = `${formatTime(playhead)} s`;
    el('replayTimeTotal').textContent = `${formatTime(trustedEnd())} s`;
    el('replaySourceFrame').textContent = lastSourceSequence === null
      ? 'source frame —'
      : `source frame #${lastSourceSequence} @ ${formatTime(lastSourceSimTime)} s`;
    const timeline = el('replayTimeline');
    if (timeline) timeline.value = playhead === null || playhead === undefined || !Number.isFinite(Number(playhead))
      ? ''
      : String(playhead);
  }

  function renderCurrent() {
    const result = projectReplayFrame({ descriptor, context, windowDoc, playhead });
    if (!result.ok) {
      if (result.reason === 'BEYOND_TRUSTED_EVIDENCE') {
        setStatus('INCOMPLETE');
        el('replayStatusLine').textContent = `REPLAY INCOMPLETE · NO RECORDED EVIDENCE AT ${formatTime(playhead)} s`;
      } else {
        setStatus('BUFFERING');
        el('replayStatusLine').textContent = 'REPLAY · BUFFERING RECORDED DATA';
      }
      readouts();
      return false;
    }
    const envelope = result.envelope;
    lastSourceSequence = envelope.presentation.source_sequence;
    lastSourceSimTime = envelope.presentation.source_sim_time_s;
    const snapshot = projection.project({
      session: { session_id: envelope.run_id, state: envelope.state },
      sessionState: envelope.state,
      telemetry: { envelope, revision: 1, receivedAt: 1, staleAgeMs: null },
      outcome: { status: 'idle', result: null, artifacts: null, error: null },
    });
    display?.render?.(snapshot.raw);
    const levels = {};
    for (const target of snapshot.risk?.targets ?? []) {
      if (target.targetId === null || target.targetId === undefined) continue;
      levels[String(target.targetId)] = THREAT_LEVELS[target.displayClass] ?? 'unknown';
    }
    display?.setTargetThreatLevels?.(levels);
    setStatus('READY');
    el('replayStatusLine').textContent = statusLineFor(clock?.state ?? ReplayPlayState.PAUSED);
    readouts();
    return true;
  }

  /** Bounded prefetch span: adapts to rate, capped by a frozen frame budget. */
  function prefetchSpanS(minSpan = PREFETCH_MIN_SPAN_S) {
    const start = Number(descriptor?.replay?.t_start) || 0.0;
    const end = trustedEnd();
    const density = (Number(descriptor?.replay?.frame_count) || 0) / Math.max(end - start, 1e-6);
    const spanByRate = Math.max(minSpan, minSpan * (clock?.rate ?? 1));
    const spanByFrames = density > 0 ? PREFETCH_FRAME_BUDGET / density : spanByRate;
    return Math.min(spanByRate, spanByFrames);
  }

  async function prefetchAhead(fromS, gen) {
    prefetchInFlight = gen;
    const toS = Math.min(trustedEnd(), fromS + prefetchSpanS());
    try {
      const document_ = await fetchJson(
        `/api/runs/${runId}/replay/window?from=${fromS}&to=${toS}`,
      );
      if (gen !== generation) return; // a newer seek/cursor owns the replay cursor
      nextWindowDoc = document_;
      if (buffering) {
        windowDoc = nextWindowDoc;
        nextWindowDoc = null;
        buffering = false;
        clock?.resume();
        syncPlayButton();
        renderCurrent();
      }
    } catch {
      if (gen === generation) {
        if (clock?.state === ReplayPlayState.PLAYING) {
          clock.pause();
          stopPlaybackTimer();
          syncPlayButton();
        }
        setStatus('ERROR');
        el('replayStatusLine').textContent = 'RECORDED DATA UNAVAILABLE · RETRY FROM THE TIMELINE';
      }
    } finally {
      if (prefetchInFlight === gen) prefetchInFlight = null;
    }
  }

  function stopPlaybackTimer() {
    if (timerId !== null) {
      schedule.clear(timerId);
      timerId = null;
    }
  }

  /** One deterministic playback step: advance the clock, prefetch when the
   * recorded bracket runs out (holding progression — never extrapolating),
   * otherwise paint the sealed frame at the playhead. */
  function playbackTick() {
    if (!clock || clock.state !== ReplayPlayState.PLAYING || status === 'LOADING') return;
    const ticked = clock.tick();
    playhead = ticked.playhead;
    const start = Number(descriptor.replay.t_start) || 0.0;
    const end = trustedEnd();
    if (nextWindowDoc && playhead >= Number(nextWindowDoc.requested?.from_s)) {
      windowDoc = nextWindowDoc;
      nextWindowDoc = null;
    }
    const from = windowDoc ? Number(windowDoc.requested?.from_s) : Number.NaN;
    const to = windowDoc ? Number(windowDoc.requested?.to_s) : Number.NaN;
    const covered = Number.isFinite(from) && Number.isFinite(to)
      && playhead >= from - 1e-6 && playhead <= to + 1e-6;
    if (!covered) {
      if (!buffering) {
        clock.hold(); // stop playhead progression until trustworthy data exists
        buffering = true;
      }
      if (prefetchInFlight !== generation) {
        void prefetchAhead(Math.min(end, Math.max(start, playhead)), generation);
      }
      setStatus('BUFFERING');
      el('replayStatusLine').textContent = `BUFFERING · WAITING FOR RECORDED DATA · ${clock.rate}×`;
      readouts();
      return;
    }
    if (ticked.state === ReplayPlayState.ENDED) {
      stopPlaybackTimer();
      syncPlayButton();
      renderCurrent();
      return;
    }
    renderCurrent();
    // Retain the current window while the next one loads; never stop the
    // clock or discard a usable bracket just to fetch ahead.
    const lead = Math.max(PREFETCH_MIN_SPAN_S, prefetchSpanS());
    if (to < end && to - playhead <= lead && !nextWindowDoc && prefetchInFlight !== generation) {
      void prefetchAhead(to, generation);
    }
  }

  function startPlaybackLoop() {
    stopPlaybackTimer();
    const step = () => {
      timerId = null;
      playbackTick();
      if (clock?.state === ReplayPlayState.PLAYING && timerId === null) {
        timerId = schedule.set(step, PLAYBACK_TICK_MS);
      }
    };
    timerId = schedule.set(step, PLAYBACK_TICK_MS);
  }

  function playPause() {
    if (!descriptor || !replayControlsEnabled || !replayCanPlay()) return;
    if (clock.state === ReplayPlayState.PLAYING) {
      clock.pause();
      stopPlaybackTimer();
      renderCurrent();
      syncPlayButton();
      return;
    }
    if (clock.state === ReplayPlayState.ENDED) {
      generation += 1; // obsolete windows/prefetches for the restarted cursor
      windowDoc = null;
      nextWindowDoc = null;
      buffering = false;
    }
    clock.play();
    if (buffering) clock.hold();
    syncPlayButton();
    playbackTick();
    if (clock.state === ReplayPlayState.PLAYING) startPlaybackLoop();
  }

  function setRate(rateValue) {
    if (!clock || !replayControlsEnabled || !replayCanPlay()) return;
    clock.setRate(Number(rateValue));
    const rateGroup = el('replayPlaybackRate');
    if (rateGroup) rateGroup.value = String(clock.rate);
    for (const rate of REPLAY_UI_RATES) {
      const button = el(`replayRate${String(rate).replace('.', '')}`);
      if (button) button.setAttribute('aria-pressed', String(rate === clock.rate));
    }
    if (clock.state === ReplayPlayState.PLAYING) {
      el('replayStatusLine').textContent = statusLineFor(clock.state);
    }
  }

  async function loadWindow(fromS, toS, gen) {
    const document_ = await fetchJson(
      `/api/runs/${runId}/replay/window?from=${fromS}&to=${toS}`,
    );
    if (gen !== generation) return; // a newer seek owns the Inspection Cursor
    windowDoc = document_;
    renderCurrent();
  }

  async function open(nextRunId) {
    runId = String(nextRunId);
    generation += 1;
    const gen = generation;
    stopPlaybackTimer();
    clock = null;
    syncPlayButton();
    display?.clearSession?.();
    prefetchInFlight = null;
    nextWindowDoc = null;
    buffering = false;
    descriptor = null;
    context = null;
    windowDoc = null;
    playhead = null;
    lastSourceSequence = null;
    lastSourceSimTime = null;
    selectedTargetId = null;
    replayScaleValue = 0.5;
    const replayScaleInput = el('replayChartScaleInput');
    if (replayScaleInput) replayScaleInput.value = '0.50';
    eventJournal = null;
    eventFilter = 'ALL';
    selectedEventId = null;
    const eventMarkers = el('replayEventMarkers');
    if (eventMarkers) {
      eventMarkers.replaceChildren();
      eventMarkers.textContent = 'LOADING RECORDED EVENTS';
    }
    const eventFilterControl = el('replayEventFilter');
    if (eventFilterControl) eventFilterControl.replaceChildren();
    const timelineReset = el('replayTimeline');
    if (timelineReset) {
      timelineReset.min = '0';
      timelineReset.max = '0';
      timelineReset.value = '';
    }
    for (const id of ['replayResultsFacts', 'replayEvidenceFacts']) {
      el(id)?.replaceChildren();
    }
    for (const id of ['replayResultsStatus', 'replayEvidenceFactsStatus']) {
      const statusPill = el(id);
      if (statusPill) statusPill.textContent = 'LOADING';
    }
    setStatus('LOADING');
    setReplayControlsEnabled(false);
    const panel = el('evaluationReplayPanel');
    if (panel) panel.hidden = false;
    const runsPanel = el('replayRunsPanel');
    if (runsPanel) runsPanel.hidden = true;
    el('replayStatusLine').textContent = 'LOADING RECORDED EVIDENCE';

    descriptor = await fetchJson(`/api/runs/${runId}/replay`);
    if (gen !== generation) return;

    el('replayRunTitle').textContent = `REPLAY · ${descriptor.run_id.slice(0, 8)} · ${descriptor.run?.scenario_id ?? ''} · ${descriptor.run?.executed_algorithm ?? ''}`;
    const timeline = el('replayTimeline');
    const range = replayRange(descriptor.replay);
    if (timeline && range && replayCanPlay()) {
      timeline.min = String(range.start);
      timeline.max = String(range.end);
      timeline.step = '0.1';
      timeline.value = String(range.start);
    }
    if (!replayCanPlay()) {
      setStatus('UNAVAILABLE');
      el('replayStatusLine').textContent = replayUnavailableMessage();
      readouts();
      return;
    }

    context = await fetchJson(`/api/runs/${runId}/replay/context`);
    if (gen !== generation) return;
    // The recorded event journal loads with the run; navigation and markers
    // use it as-is (recorded identity/time/order), independent of paint
    // sampling during high-speed playback.
    eventJournal = await fetchJson(`/api/runs/${runId}/replay/events`).catch(() => null);
    if (gen !== generation) return;
    renderEventMarkers();
    const filter = el('replayEventFilter');
    if (filter) {
      filter.replaceChildren();
      const allOption = documentRef.createElement('option');
      allOption.value = 'ALL';
      allOption.textContent = 'ALL EVENTS';
      filter.append(allOption);
      for (const category of eventJournal?.categories ?? []) {
        const option = documentRef.createElement('option');
        option.value = category;
        option.textContent = category;
        filter.append(option);
      }
    }

    const start = range.start;
    const end = range.end;
    playhead = start;
    display?.setOrientation?.('north');
    clock = createReplayClock({ now: nowFn, tStart: start, tEnd: end });
    ensureDisplay();
    await display?.beginSession?.(runId);
    readouts();
    await loadWindow(start, Math.min(end, start + prefetchSpanS(INITIAL_WINDOW_SPAN_S)), gen);
    if (gen === generation) {
      display?.fitTraffic?.();
      setReplayControlsEnabled(true);
    }
  }

  function ensureDisplay() {
    if (display) return display;
    const canvas = el('replayCanvas');
    const wrapper = el('replayCanvasWrapper');
    const displayOptions = {
      canvas,
      wrapper,
      context,
      runId,
      fetchInfo: async () => {
        const enc = context?.enc ?? {};
        const ready = [
          enc.origin_east_m,
          enc.origin_north_m,
          enc.width_m,
          enc.height_m,
          enc.utm_zone,
        ].every(value => Number.isFinite(Number(value))) && Boolean(enc.image_url);
        return {
          ready,
          run_id: runId,
          origin_e: Number(enc.origin_east_m),
          origin_n: Number(enc.origin_north_m),
          width: Number(enc.width_m),
          height: Number(enc.height_m),
          utm_zone: enc.utm_zone,
        };
      },
      fetchTile: () => context?.enc?.image_url ?? '',
      onLayerStateChange: state => syncReplayLayerControls(state),
    };
    if (displayFactory) {
      display = displayFactory(displayOptions);
    } else if (canvas && wrapper) {
      display = createSituationDisplay({
        ...displayOptions,
        getScenarioId: () => context?.scenario_id ?? null,
        getResponseRange: () => null,
        getPlannerSurface: () => null,
      });
    }
    display?.setLayerVisible?.('history', true);
    syncReplayLayerControls(display?.getLayerState?.());
    syncReplayOrientationControls(display?.getOrientation?.());
    return display;
  }

  function seek(simTime) {
    if (!descriptor || !replayControlsEnabled || !replayCanPlay() || !Number.isFinite(Number(simTime))) return Promise.resolve();
    const range = replayRange(descriptor.replay);
    if (!range) return Promise.resolve();
    const start = range.start;
    const end = range.end;
    const target = Math.max(start, Math.min(end, Number(simTime)));
    const wasPlaying = clock?.state === ReplayPlayState.PLAYING;
    clock?.seek(target); // valid from PLAYING/PAUSED/BUFFERING/ENDED
    playhead = target;
    generation += 1;
    nextWindowDoc = null;
    buffering = false;
    const gen = generation;
    setStatus('LOADING');
    el('replayStatusLine').textContent = 'LOADING RECORDED EVIDENCE';
    readouts();
    if (wasPlaying) clock.hold(); // stop progression while the target window loads
    // Direct historical seek: fetch the recorded neighborhood of the target
    // time only — never sequential frames from zero, never simulation.
    const from = Math.max(start, target - SEEK_WINDOW_HALF_SPAN_S);
    const to = Math.min(end, target + SEEK_WINDOW_HALF_SPAN_S);
    return loadWindow(from, to, gen).then(() => {
      if (gen !== generation || !wasPlaying || !clock) {
        syncPlayButton();
        return;
      }
      clock.resume();
      syncPlayButton();
      playbackTick();
      if (clock.state === ReplayPlayState.PLAYING) startPlaybackLoop();
    }).catch(() => {
      if (gen !== generation) return;
      if (wasPlaying) {
        clock?.pause();
        stopPlaybackTimer();
      }
      syncPlayButton();
      setStatus('ERROR');
      el('replayStatusLine').textContent = 'RECORDED DATA UNAVAILABLE · RETRY FROM THE TIMELINE';
    });
  }

  function selectTarget(targetId) {
    selectedTargetId = targetId === null || targetId === undefined ? null : String(targetId);
  }

  function close() {
    generation += 1;
    stopPlaybackTimer();
    clock?.pause();
    syncPlayButton();
    setReplayControlsEnabled(false);
    const panel = el('evaluationReplayPanel');
    if (panel) panel.hidden = true;
    const runsPanel = el('replayRunsPanel');
    if (runsPanel) runsPanel.hidden = false;
  }

  el('replayTimeline')?.addEventListener('input', event => {
    seek(Number(event?.target?.value ?? 0));
  });
  el('replayStartBtn')?.addEventListener('click', () => {
    seek(Number(descriptor?.replay?.t_start) || 0.0);
  });
  el('replayPlayPauseBtn')?.addEventListener('click', playPause);
  for (const rate of REPLAY_UI_RATES) {
    el(`replayRate${String(rate).replace('.', '')}`)?.addEventListener('click', () => {
      setRate(rate);
    });
  }
  el('replayCloseBtn')?.addEventListener('click', close);

  // ── #74 Evaluation local views: Replay | Results | Evidence | Historical AIS ──
  // Switching a local view changes Inspection Context only — it never
  // creates, replaces or mutates the Active Session.
  const evaluationViews = ['replay', 'results', 'evidence', 'hais'];
  const STALE_RUN_DOCUMENT = Symbol('STALE_RUN_DOCUMENT');
  let selectedEvaluationView = 'replay';

  function renderFacts(targetId, facts) {
    const container = el(targetId);
    if (!container) return;
    container.replaceChildren(...facts.map(([label, value]) => {
      const row = documentRef.createElement('div');
      const dt = documentRef.createElement('dt');
      dt.textContent = label;
      const dd = documentRef.createElement('dd');
      dd.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
      row.append(dt, dd);
      return row;
    }));
  }

  function diagnosticLabel(run) {
    if (run?.diagnostic_only === true) return 'DIAGNOSTIC ONLY';
    if (run?.diagnostic_only === false) return 'STANDARD RUN';
    return null;
  }

  function diagnosticReasons(run) {
    const reasons = run?.diagnostic_only_reasons;
    if (Array.isArray(reasons)) return reasons.join(', ') || null;
    return reasons ?? null;
  }

  function originalGnc(run) {
    const gnc = run?.original_gnc;
    if (!gnc || typeof gnc !== 'object') return {};
    return {
      stack: gnc.stack_id ?? null,
      library: gnc.library_sha256 ?? null,
    };
  }

  function hardGateChecks(gate) {
    if (!Array.isArray(gate?.checks)) return null;
    const checks = gate.checks.map(check => {
      if (!check || typeof check !== 'object') return null;
      const id = check.check_id ?? 'check';
      const outcome = check.outcome ?? '—';
      const scope = check.evidence?.scope;
      return `${id}: ${outcome}${scope ? ` (${scope})` : ''}`;
    }).filter(Boolean);
    return checks.length ? checks.join(' · ') : null;
  }

  async function loadRunDocument() {
    if (!runId) return null;
    const requestedRunId = runId;
    const requestedGeneration = generation;
    try {
      const document_ = await fetchJson(`/api/runs/${requestedRunId}/replay/evidence`);
      if (requestedRunId !== runId || requestedGeneration !== generation) return STALE_RUN_DOCUMENT;
      return document_;
    } catch {
      if (requestedRunId !== runId || requestedGeneration !== generation) return STALE_RUN_DOCUMENT;
      return null;
    }
  }

  async function renderResultsView() {
    const status = el('replayResultsStatus');
    const document_ = await loadRunDocument();
    if (document_ === STALE_RUN_DOCUMENT) return;
    if (!document_) {
      if (status) status.textContent = 'UNAVAILABLE';
      return;
    }
    if (status) status.textContent = document_.result?.result_ready ? 'RESULT READY' : 'RESULT PENDING';
    const result = document_.result ?? {};
    const run = document_.run ?? {};
    const gnc = originalGnc(run);
    renderFacts('replayResultsFacts', [
      ['Run', document_.run_id?.slice(0, 8)],
      ['Scenario', run.scenario_id],
      ['Executed algorithm', run.executed_algorithm],
      ['Execution state', run.execution_state],
      ['Assurance scope', diagnosticLabel(run)],
      ['Diagnostic reasons', diagnosticReasons(run)],
      ['Original GNC stack', gnc.stack],
      ['Original GNC library SHA256', gnc.library],
      ['Result ready', document_.result?.result_ready ? 'YES' : 'NO — result pending (replay readiness is independent)'],
      ['Evaluation status', result.evaluation_status],
      ['Hard gate outcome', result.hard_gate?.outcome],
      ['Hard gate checks', hardGateChecks(result.hard_gate)],
      ['Reproduction status', result.reproduction_status],
      ['Failure', run.failure_status ? `${run.failure_status}${run.failure_reason ? ` · ${run.failure_reason}` : ''}` : null],
      ['Limitations', (document_.limitations ?? []).join(', ') || null],
    ]);
  }

  async function renderEvidenceView() {
    const status = el('replayEvidenceFactsStatus');
    const document_ = await loadRunDocument();
    if (document_ === STALE_RUN_DOCUMENT) return;
    if (!document_) {
      if (status) status.textContent = 'UNAVAILABLE';
      return;
    }
    if (status) status.textContent = String(document_.evidence?.replay?.state ?? '—');
    const replay = document_.evidence?.replay ?? {};
    const run = document_.run ?? {};
    const gnc = originalGnc(run);
    const digests = document_.evidence?.digests ?? {};
    renderFacts('replayEvidenceFacts', [
      ['Run', document_.run_id],
      ['Assurance scope', diagnosticLabel(run)],
      ['Diagnostic reasons', diagnosticReasons(run)],
      ['Original GNC stack', gnc.stack],
      ['Original GNC library SHA256', gnc.library],
      ['Replay state', replay.state],
      ['Evidence level', replay.evidence_level],
      ['Reason', replay.reason],
      ['Trace schema', replay.trace_schema],
      ['Frames', replay.frame_count],
      ['Trusted range', replay.t_start !== null && replay.t_start !== undefined ? `${formatTime(replay.t_start)} – ${formatTime(replay.trusted_t_end ?? replay.t_end)} s` : null],
      ['Frames digest', replay.frames_sha256 ? String(replay.frames_sha256).slice(0, 16) + '…' : null],
      ['Trajectory (reduced)', document_.evidence?.trajectory_present ? 'present' : 'absent'],
      ['ENC raster', document_.evidence?.enc_present ? 'present' : 'absent'],
      ['Mid-MPC solver artifacts', document_.evidence?.mid_mpc_artifact_count],
      ['Event journal entries', document_.evidence?.event_count],
      ['Digests', Object.entries(digests).map(([key, value]) => `${key}:${String(value).slice(0, 12)}…`).join(' ') || null],
      ['Limitations', (document_.limitations ?? []).join(', ') || null],
    ]);
  }

  function switchEvaluationView(next) {
    if (!evaluationViews.includes(next)) return;
    selectedEvaluationView = next;
    for (const view of evaluationViews) {
      const section = el(`evalView${view === 'hais' ? 'HistoricalAIS' : view.charAt(0).toUpperCase() + view.slice(1)}`);
      if (section) section.hidden = view !== next;
      const tab = el(`evalViewTab${view === 'hais' ? 'HistoricalAIS' : view.charAt(0).toUpperCase() + view.slice(1)}`);
      if (tab) tab.setAttribute('aria-pressed', String(view === next));
    }
    if (next === 'results') void renderResultsView();
    if (next === 'evidence') void renderEvidenceView();
  }

  for (const view of evaluationViews) {
    el(`evalViewTab${view === 'hais' ? 'HistoricalAIS' : view.charAt(0).toUpperCase() + view.slice(1)}`)?.addEventListener('click', () => {
      switchEvaluationView(view);
    });
  }
  el('replayPrevEventBtn')?.addEventListener('click', () => stepEvent(-1));
  el('replayNextEventBtn')?.addEventListener('click', () => stepEvent(1));
  el('replayEventFilter')?.addEventListener('change', event => {
    setEventFilter(event?.target?.value ?? 'ALL');
  });
  setupReplayChartControls();

  return {
    open,
    seek,
    selectTarget,
    close,
    playPause,
    setRate,
    switchEvaluationView,
    get state() {
      return {
        runId,
        status,
        playhead,
        sourceSequence: lastSourceSequence,
        sourceSimTime: lastSourceSimTime,
        presentationMode: REPLAY_PRESENTATION_MODE,
        selectedTargetId,
        clockState: clock?.state ?? null,
        rate: clock?.rate ?? null,
        eventCount: eventJournal ? (eventJournal.events ?? []).length : null,
        eventFilter,
        selectedEventId,
        evidenceState: descriptor?.replay?.state ?? null,
        replayPlayable: replayCanPlay(),
      };
    },
  };
}

/**
 * Open a Run in the SHARED Evaluation > Replay player and switch the local
 * view (#74). Historical AIS uses this for its explicit `Open Replay`
 * inspection action — no second player is instantiated anywhere. Safe no-op
 * (returns false) when the player host is absent (tests, other pages).
 */
export function openReplayForRun(runId) {
  if (typeof document === 'undefined' || !document.getElementById('evaluationReplayPanel')) {
    return false;
  }
  replayController?.switchEvaluationView('replay');
  void replayController?.open(runId);
  return true;
}

let replayController = null;
if (typeof document !== 'undefined' && document.getElementById('evaluationReplayPanel')) {
  replayController = createEvaluationReplayController();
  setReplayRunOpener(runId => {
    replayController.open(runId);
  });
}
