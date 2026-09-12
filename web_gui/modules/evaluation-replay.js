/**
 * Evaluation > Replay — paused historical inspection host (ticket #71).
 *
 * Owns ONLY replay presentation state (Technical Design §3.3): the selected
 * Run, the sealed evidence descriptor/context/window, the paused playhead and
 * the inspection selection. It renders through the EXISTING
 * telemetry-projection.js + situation-display.js modules (own instances, the
 * same semantics Deployment uses) and issues GET reads against /api/runs/*
 * only. There is no play/pause/rate clock here (ticket #72), no event
 * navigation (ticket #73) and never an Active Session mutation.
 */

import { createSituationDisplay } from './situation-display.js';
import { createTelemetryProjection } from './telemetry-projection.js';
import { projectReplayFrame, REPLAY_PRESENTATION_MODE } from './replay-source.js';
import { createReplayClock, REPLAY_RATES, ReplayPlayState } from './replay-clock.js';
import { setReplayRunOpener } from './replay-runs.js';

// Scrub windows stay small and bounded; the backend enforces the frozen caps.
const SEEK_WINDOW_HALF_SPAN_S = 0.5;
const INITIAL_WINDOW_SPAN_S = 8.0;

// Playback prefetch: bounded frame-count windows ahead of the playhead. The
// span adapts to Replay Speed (so high rates do not refetch every 100 ms) but
// is capped by a frozen frame budget — the whole Run is never loaded.
const PLAYBACK_TICK_MS = 100;
const PREFETCH_FRAME_BUDGET = 240;
const PREFETCH_MIN_SPAN_S = 8.0;

const THREAT_LEVELS = { HIGH: 'danger', LOW: 'warn', CLEAR: 'safe' };

function formatTime(value) {
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
  let lastSourceSequence = null;
  let lastSourceSimTime = null;
  let display = null;
  let clock = null;
  let timerId = null;
  let prefetchInFlight = false;

  function setStatus(next) {
    status = next;
  }

  function statusLineFor(clockState) {
    if (clockState === ReplayPlayState.PLAYING) {
      return `PLAYING · HISTORICAL REPLAY · ${clock.rate}×`;
    }
    if (clockState === ReplayPlayState.ENDED) {
      return 'REPLAY ENDED · SEEK BACKWARD OR PRESS PLAY TO RESTART';
    }
    return 'PAUSED · HISTORICAL INSPECTION';
  }

  function evidenceLabel(facts) {
    const state = String(facts?.state ?? 'UNAVAILABLE').toUpperCase();
    if (state === 'READY') return 'REPLAY READY · FULL EVIDENCE';
    if (state === 'INCOMPLETE') return `REPLAY INCOMPLETE · TRUSTED THROUGH ${formatTime(facts?.trusted_t_end)} s`;
    if (state === 'REDUCED') return 'REDUCED EVIDENCE';
    if (state === 'CAPTURING') return 'CAPTURING';
    return 'REPLAY UNAVAILABLE';
  }

  function trustedEnd() {
    const facts = descriptor?.replay ?? {};
    if (String(facts.state).toUpperCase() === 'INCOMPLETE' && Number.isFinite(Number(facts.trusted_t_end))) {
      return Number(facts.trusted_t_end);
    }
    return Number(facts.t_end);
  }

  async function fetchJson(url) {
    const response = await fetchRef(url, { method: 'GET' });
    if (!response.ok) throw new Error(`replay read failed: ${response.status} ${url}`);
    return response.json();
  }

  function readouts() {
    el('replayTimeCurrent').textContent = `${formatTime(playhead)} s`;
    el('replayTimeTotal').textContent = `${formatTime(trustedEnd())} s`;
    el('replaySourceFrame').textContent = lastSourceSequence === null
      ? 'source frame —'
      : `source frame #${lastSourceSequence} @ ${formatTime(lastSourceSimTime)} s`;
    const timeline = el('replayTimeline');
    if (timeline) timeline.value = String(playhead);
  }

  function renderInspection() {
    const inspection = el('replayInspection');
    if (!inspection) return;
    const snapshot = projection.snapshot();
    const target = selectedTargetId === null
      ? null
      : (snapshot.risk?.targets ?? []).find(entry => String(entry.targetId) === String(selectedTargetId));
    const lines = [
      selectedTargetId === null ? 'INSPECTION: scenario overview' : `INSPECTION: TS${selectedTargetId}`,
      target ? [
        target.displayClass ? `recorded threat class ${target.displayClass}` : null,
        target.dcpaM !== null && target.dcpaM !== undefined ? `DCPA ${Number(target.dcpaM).toFixed(0)} m` : null,
        target.rangeM !== null && target.rangeM !== undefined ? `range ${Number(target.rangeM).toFixed(0)} m` : null,
      ].filter(Boolean).join(' · ') : (selectedTargetId === null ? null : 'no recorded threat vector for this target'),
      lastSourceSequence === null ? null : `evidence: source frame #${lastSourceSequence} @ ${formatTime(lastSourceSimTime)} s`,
      'selection changes Inspection Context only',
    ];
    inspection.replaceChildren(...lines.filter(Boolean).map(line => {
      const row = documentRef.createElement('p');
      row.textContent = line;
      return row;
    }));
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
      renderInspection();
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
    renderInspection();
    return true;
  }

  /** Bounded prefetch span: adapts to rate, capped by a frozen frame budget. */
  function prefetchSpanS() {
    const start = Number(descriptor?.replay?.t_start) || 0.0;
    const end = trustedEnd();
    const density = (Number(descriptor?.replay?.frame_count) || 0) / Math.max(end - start, 1e-6);
    const spanByRate = Math.max(PREFETCH_MIN_SPAN_S, PREFETCH_MIN_SPAN_S * (clock?.rate ?? 1));
    const spanByFrames = density > 0 ? PREFETCH_FRAME_BUDGET / density : spanByRate;
    return Math.min(spanByRate, spanByFrames);
  }

  async function prefetchAhead(fromS, gen) {
    prefetchInFlight = true;
    const toS = Math.min(trustedEnd(), fromS + prefetchSpanS());
    try {
      const document_ = await fetchJson(
        `/api/runs/${runId}/replay/window?from=${fromS}&to=${toS}`,
      );
      if (gen !== generation) return; // a newer seek/cursor owns the Inspection Cursor
      windowDoc = document_;
      clock?.resume();
      renderCurrent();
    } catch {
      if (gen === generation) {
        if (clock?.state === ReplayPlayState.PLAYING) {
          clock.pause();
          stopPlaybackTimer();
          el('replayPlayPauseBtn').textContent = 'PLAY ▶';
        }
        setStatus('ERROR');
        el('replayStatusLine').textContent = 'RECORDED DATA UNAVAILABLE · RETRY FROM THE TIMELINE';
      }
    } finally {
      prefetchInFlight = false;
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
    if (!clock || clock.state !== ReplayPlayState.PLAYING) return;
    const ticked = clock.tick();
    playhead = ticked.playhead;
    if (ticked.state === ReplayPlayState.ENDED) {
      stopPlaybackTimer();
      renderCurrent();
      return;
    }
    const start = Number(descriptor.replay.t_start) || 0.0;
    const end = trustedEnd();
    const from = windowDoc ? Number(windowDoc.requested?.from_s) : Number.NaN;
    const to = windowDoc ? Number(windowDoc.requested?.to_s) : Number.NaN;
    const covered = Number.isFinite(from) && Number.isFinite(to)
      && playhead >= from - 1e-6 && playhead <= to + 1e-6;
    if (!covered) {
      if (!prefetchInFlight) {
        clock.hold(); // stop playhead progression until trustworthy data exists
        void prefetchAhead(Math.min(end, Math.max(start, playhead)), generation);
      }
      readouts();
      return;
    }
    renderCurrent();
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
    if (!descriptor || !['READY', 'INCOMPLETE'].includes(String(descriptor.replay.state).toUpperCase())) return;
    if (clock.state === ReplayPlayState.PLAYING) {
      clock.pause();
      stopPlaybackTimer();
      renderCurrent();
      el('replayPlayPauseBtn').textContent = 'PLAY ▶';
      return;
    }
    if (clock.state === ReplayPlayState.ENDED) {
      generation += 1; // obsolete windows/prefetches for the restarted cursor
      windowDoc = null;
    }
    clock.play();
    el('replayPlayPauseBtn').textContent = 'PAUSE ⏸';
    playbackTick();
    if (clock.state === ReplayPlayState.PLAYING) startPlaybackLoop();
  }

  function setRate(rateValue) {
    if (!clock) return;
    clock.setRate(Number(rateValue));
    for (const rate of REPLAY_RATES) {
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
    prefetchInFlight = false;
    descriptor = null;
    context = null;
    windowDoc = null;
    playhead = null;
    lastSourceSequence = null;
    lastSourceSimTime = null;
    selectedTargetId = null;
    setStatus('LOADING');
    const panel = el('evaluationReplayPanel');
    if (panel) panel.hidden = false;
    // Persistent, non-color-only historical state. Replay never presents a
    // recorded frame as LIVE, whatever the evidence state degrades to.
    el('replaySealedBadge').textContent = 'SEALED · HISTORICAL';
    el('replayStatusLine').textContent = 'LOADING RECORDED EVIDENCE';
    el('replayEvidenceBadge').textContent = 'LOADING';

    descriptor = await fetchJson(`/api/runs/${runId}/replay`);
    if (gen !== generation) return;
    context = await fetchJson(`/api/runs/${runId}/replay/context`);
    if (gen !== generation) return;

    el('replayRunTitle').textContent = `EVALUATION / REPLAY · ${descriptor.run_id.slice(0, 8)} · ${descriptor.run?.scenario_id ?? ''} · ${descriptor.run?.executed_algorithm ?? ''}`;
    el('replayEvidenceBadge').textContent = evidenceLabel(descriptor.replay);
    const timeline = el('replayTimeline');
    const start = Number(descriptor.replay.t_start) || 0.0;
    const end = trustedEnd();
    if (timeline) {
      timeline.min = String(start);
      timeline.max = String(end);
      timeline.step = '0.1';
      timeline.value = String(start);
    }
    if (!['READY', 'INCOMPLETE'].includes(String(descriptor.replay.state).toUpperCase())) {
      setStatus('UNAVAILABLE');
      el('replayStatusLine').textContent = `REPLAY ${evidenceLabel(descriptor.replay)}`;
      readouts();
      return;
    }

    playhead = start;
    clock = createReplayClock({ now: nowFn, tStart: start, tEnd: end });
    ensureDisplay();
    display?.beginSession?.(runId);
    readouts();
    await loadWindow(start, Math.min(end, start + INITIAL_WINDOW_SPAN_S), gen);
  }

  function ensureDisplay() {
    if (display) return display;
    const canvas = el('replayCanvas');
    const wrapper = el('replayCanvasWrapper');
    if (displayFactory) {
      display = displayFactory({ canvas, wrapper, context, runId });
    } else if (canvas && wrapper) {
      display = createSituationDisplay({
        canvas,
        wrapper,
        fetchInfo: async () => context?.enc ?? {},
        fetchTile: () => context?.enc?.image_url ?? '',
        getScenarioId: () => context?.scenario_id ?? null,
        getResponseRange: () => null,
        getPlannerSurface: () => null,
      });
    }
    return display;
  }

  function seek(simTime) {
    if (!descriptor || !Number.isFinite(Number(simTime))) return Promise.resolve();
    const start = Number(descriptor.replay.t_start) || 0.0;
    const end = trustedEnd();
    const target = Math.max(start, Math.min(end, Number(simTime)));
    const wasPlaying = clock?.state === ReplayPlayState.PLAYING;
    clock?.seek(target); // valid from PLAYING/PAUSED/BUFFERING/ENDED
    playhead = target;
    generation += 1;
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
      if (gen !== generation || !wasPlaying || !clock) return;
      clock.resume();
      playbackTick();
      if (clock.state === ReplayPlayState.PLAYING) startPlaybackLoop();
    }).catch(() => {
      if (gen !== generation) return;
      if (wasPlaying) {
        clock?.pause();
        stopPlaybackTimer();
        el('replayPlayPauseBtn').textContent = 'PLAY ▶';
      }
      setStatus('ERROR');
      el('replayStatusLine').textContent = 'RECORDED DATA UNAVAILABLE · RETRY FROM THE TIMELINE';
    });
  }

  function selectTarget(targetId) {
    selectedTargetId = targetId === null || targetId === undefined ? null : String(targetId);
    renderInspection();
  }

  function close() {
    generation += 1;
    stopPlaybackTimer();
    clock?.pause();
    const panel = el('evaluationReplayPanel');
    if (panel) panel.hidden = true;
  }

  el('replayTimeline')?.addEventListener('input', event => {
    seek(Number(event?.target?.value ?? 0));
  });
  el('replayStartBtn')?.addEventListener('click', () => {
    seek(Number(descriptor?.replay?.t_start) || 0.0);
  });
  el('replayEndBtn')?.addEventListener('click', () => {
    seek(trustedEnd());
  });
  el('replayPlayPauseBtn')?.addEventListener('click', playPause);
  for (const rate of REPLAY_RATES) {
    el(`replayRate${String(rate).replace('.', '')}`)?.addEventListener('click', () => {
      setRate(rate);
    });
  }
  el('replayCloseBtn')?.addEventListener('click', close);

  return {
    open,
    seek,
    selectTarget,
    close,
    playPause,
    setRate,
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
      };
    },
  };
}

if (typeof document !== 'undefined' && document.getElementById('evaluationReplayPanel')) {
  const controller = createEvaluationReplayController();
  setReplayRunOpener(runId => {
    controller.open(runId);
  });
}
