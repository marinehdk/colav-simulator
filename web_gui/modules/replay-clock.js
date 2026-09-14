/**
 * ReplayClock — deterministic historical presentation clock (ticket #72).
 *
 * Pure presentation state for Sealed Run Replay: advances recorded simulation
 * time from monotonic wall-clock elapsed time × Replay Speed, clamped to the
 * selected Run's trusted [t_start, t_end]. It never touches the Active
 * Session, never calls setSpeed/step/advance, and shares nothing with the
 * live telemetry buffer's delay/reserve/adaptive-rate semantics.
 *
 * `now` is injected (monotonic wall milliseconds) so tests drive known
 * literals instead of implementation-coupled timers.
 */

export const REPLAY_RATES = [0.25, 0.5, 1, 2, 5, 10, 20];

export const ReplayPlayState = {
  PAUSED: 'PAUSED',
  PLAYING: 'PLAYING',
  ENDED: 'ENDED',
};

const DEFAULT_RATE = 1;
const EPSILON_S = 1e-9;

export function createReplayClock({ now, tStart, tEnd, rate: initialRate = DEFAULT_RATE } = {}) {
  const start = Number.isFinite(Number(tStart)) ? Number(tStart) : 0.0;
  const end = Number.isFinite(Number(tEnd)) ? Number(tEnd) : start;

  let playhead = start;
  let rate = REPLAY_RATES.includes(Number(initialRate)) ? Number(initialRate) : DEFAULT_RATE;
  let state = ReplayPlayState.PAUSED;
  let lastWallMs = null;

  function consumeWall() {
    if (state !== ReplayPlayState.PLAYING || lastWallMs === null) return;
    const elapsedS = Math.max(0, (now() - lastWallMs)) / 1000;
    lastWallMs = now();
    if (elapsedS <= 0) return;
    playhead = Math.min(end, playhead + elapsedS * rate);
    if (playhead >= end - EPSILON_S) {
      playhead = end;
      state = ReplayPlayState.ENDED;
      lastWallMs = null;
    }
  }

  return {
    get state() {
      return state;
    },
    get playhead() {
      consumeWall(); // "current playhead" means consumed to now
      return playhead;
    },
    get rate() {
      return rate;
    },
    get trustedRange() {
      return { tStart: start, tEnd: end };
    },

    play() {
      if (state === ReplayPlayState.ENDED || playhead >= end - EPSILON_S) {
        // Deterministic restart: ENDED play returns to the trusted start.
        playhead = start;
      }
      state = ReplayPlayState.PLAYING;
      lastWallMs = now();
      return playhead;
    },

    pause() {
      consumeWall();
      state = ReplayPlayState.PAUSED;
      lastWallMs = null;
      return playhead;
    },

    setRate(nextRate) {
      const candidate = Number(nextRate);
      if (!REPLAY_RATES.includes(candidate)) return rate;
      consumeWall(); // continuity: only elapsed time AFTER the change uses the new rate
      rate = candidate;
      if (state === ReplayPlayState.PLAYING) lastWallMs = now();
      return rate;
    },

    /** Direct seek from any state; a seek out of ENDED returns to PAUSED. */
    seek(simTime) {
      const target = Number(simTime);
      playhead = Number.isFinite(target) ? Math.max(start, Math.min(end, target)) : playhead;
      if (state === ReplayPlayState.PLAYING) {
        lastWallMs = now(); // the seek instant is the new wall-time origin
      } else {
        state = ReplayPlayState.PAUSED;
        lastWallMs = null;
      }
      return playhead;
    },

    /** Hold wall-time consumption while recorded data is missing (BUFFERING). */
    hold() {
      consumeWall();
      lastWallMs = null;
      return playhead;
    },

    /** Resume consumption after a hold without changing play/state. */
    resume() {
      if (state === ReplayPlayState.PLAYING) lastWallMs = now();
      return playhead;
    },

    tick() {
      if (state === ReplayPlayState.PLAYING) consumeWall();
      return { playhead, state };
    },
  };
}
