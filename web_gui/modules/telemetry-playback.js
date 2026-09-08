/** Pace received real frames behind execution; never extrapolate vessel motion. */
export function createTelemetryPlayback({ publish, clock, scheduler, delayMs = 3000 }) {
  let queue = [];
  let latest = null;
  let runId = null;
  let timer = null;
  let startedAt = null;
  let tickAt = null;
  let playhead = null;
  let lastEmitted = null;
  let anchor = null;
  let rate = null;
  let samples = [];

  function stop() {
    if (timer !== null) scheduler.clearTimeout(timer);
    timer = null;
  }

  function reset() {
    stop();
    queue = [];
    samples = [];
    startedAt = null;
    tickAt = null;
    playhead = null;
    lastEmitted = null;
    anchor = null;
    rate = null;
  }

  function emit(item, buffering = false, next = item, renderTime = item.snapshot.telemetry.envelope.sim_time) {
    const envelope = item.snapshot.telemetry.envelope;
    const upper = next.snapshot.telemetry.envelope;
    const amount = upper.sim_time > envelope.sim_time
      ? Math.max(0, Math.min(1, (renderTime - envelope.sim_time) / (upper.sim_time - envelope.sim_time))) : 0;
    const delay = Math.max(0, (clock.now() - item.at) / 1000);
    publish({
      ...item.snapshot,
      telemetry: {
        ...item.snapshot.telemetry,
        envelope: {
          ...envelope,
          sim_time: renderTime,
          source_time_s: Number.isFinite(envelope.source_time_s) && Number.isFinite(upper.source_time_s)
            ? envelope.source_time_s + (upper.source_time_s - envelope.source_time_s) * amount : envelope.source_time_s,
          os: interpolateVessel(envelope.os, upper.os, amount),
          obstacles: interpolateVessels(envelope.obstacles, upper.obstacles, amount),
          truth: interpolateVessels(envelope.truth, upper.truth, amount),
          presentation: { buffered: true, buffering, delay_s: delay, interpolation_ms: 25,
            playback_rate: rate, render_time_s: renderTime, source_sim_time_s: envelope.sim_time },
        },
      },
    });
    lastEmitted = item;
  }

  function tick() {
    timer = null;
    if (!latest) return;
    if (!queue.length) {
      if (anchor) emit(anchor, true);
      startedAt = clock.now();
      tickAt = null;
      return;
    }
    const now = clock.now();
    if (now - startedAt < delayMs) {
      timer = scheduler.setTimeout(tick, 25);
      return;
    }
    const requested = Number(latest.telemetry.envelope.playback?.requested_multiplier) || 1;
    const newest = queue.at(-1).snapshot.telemetry.envelope.sim_time;
    const span = samples.length > 1 ? samples.at(-1).at - samples[0].at : 0;
    const measured = span >= 1000
      ? (samples.at(-1).sim - samples[0].sim) / (span / 1000) : requested;
    const baseRate = Math.max(0.1, Math.min(requested, measured || requested));
    const available = Math.max(0, newest - playhead);
    // Gently vary presentation speed to replenish the reserve after a solve.
    // A three-second production gap consumes the reserve rather than freezing
    // the marker every time an optimizer starts.
    const targetReserve = baseRate * delayMs / 1000;
    const desired = Math.max(baseRate * 0.5, Math.min(requested, baseRate + (available - targetReserve) / 4));
    const elapsed = tickAt === null ? 0 : Math.max(0, (now - tickAt) / 1000);
    rate = rate === null ? desired : rate + Math.min(1, elapsed * 2) * (desired - rate);
    const deadlineRate = Math.max(0, ...queue.map(item =>
      Math.max(0, item.snapshot.telemetry.envelope.sim_time - playhead)
        / Math.max(0.025, (item.at + delayMs - now) / 1000)));
    rate = Math.max(rate, deadlineRate);
    tickAt = now;
    playhead = Math.min(newest, playhead + elapsed * rate);
    while (queue.length && queue[0].snapshot.telemetry.envelope.sim_time <= playhead + 1e-9) {
      anchor = queue.shift();
    }
    if (anchor) emit(anchor, false, queue[0] ?? anchor, playhead);
    if (anchor?.snapshot.telemetry.envelope.state === 'FINISHED') {
      reset();
      return;
    }
    timer = scheduler.setTimeout(tick, 25);
  }

  return {
    push(snapshot) {
      latest = snapshot;
      const envelope = snapshot?.telemetry?.envelope;
      const nextRun = snapshot?.session?.session_id ?? envelope?.run_id ?? null;
      if (nextRun !== runId) {
        reset();
        runId = nextRun;
      }
      if (!envelope || !Number.isFinite(envelope.sim_time)) {
        publish(snapshot);
        return;
      }
      const terminalDrain = envelope.state === 'FINISHED' && startedAt !== null;
      const immediate = snapshot.sessionState === 'PAUSED' || snapshot.sessionState === 'FAILED'
        || (!terminalDrain && envelope.state !== 'RUNNING');
      if (immediate) {
        reset();
        publish(snapshot);
        return;
      }
      const now = clock.now();
      const duplicate = queue.at(-1);
      const previous = duplicate ?? lastEmitted;
      if (previous && (envelope.seq < previous.snapshot.telemetry.envelope.seq
        || envelope.sim_time < previous.snapshot.telemetry.envelope.sim_time)) return;
      if (duplicate && duplicate.snapshot.telemetry.envelope.seq === envelope.seq) {
        duplicate.snapshot = snapshot;
        return;
      }
      if (lastEmitted?.snapshot.telemetry.envelope.seq === envelope.seq) {
        if (envelope.state !== lastEmitted.snapshot.telemetry.envelope.state) {
          reset();
          publish(snapshot);
        }
        return;
      }
      const item = { at: now, snapshot };
      if (startedAt === null) {
        startedAt = now;
        playhead = envelope.sim_time;
        anchor = item;
        emit(item, true);
      }
      queue.push(item);
      samples.push({ at: now, sim: envelope.sim_time });
      while (samples.length > 2 && now - samples[0].at > 5000) samples.shift();
      // Hidden tabs/reconnects must not retain an unbounded session history.
      if (queue.length > 120) {
        queue.splice(0, queue.length - 120);
        playhead = Math.max(playhead, queue[0].snapshot.telemetry.envelope.sim_time);
      }
      if (timer === null) timer = scheduler.setTimeout(tick, 25);
    },
    destroy: reset,
  };
}

function interpolateVessel(from, to, amount) {
  if (!from || !to) return from;
  const value = { ...from };
  for (const key of ['x', 'y', 'north', 'east', 'latitude', 'longitude', 'sog', 'u', 'v']) {
    if (Number.isFinite(from[key]) && Number.isFinite(to[key])) value[key] = from[key] + (to[key] - from[key]) * amount;
  }
  for (const key of ['psi', 'cog']) {
    if (Number.isFinite(from[key]) && Number.isFinite(to[key])) {
      value[key] = from[key] + Math.atan2(Math.sin(to[key] - from[key]), Math.cos(to[key] - from[key])) * amount;
    }
  }
  return value;
}

function interpolateVessels(from, to, amount) {
  if (!Array.isArray(from)) return from;
  const next = new Map((to || []).map(vessel => [vessel.id, vessel]));
  return from.map(vessel => interpolateVessel(vessel, next.get(vessel.id), amount));
}
