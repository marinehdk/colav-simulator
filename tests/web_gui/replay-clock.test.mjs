import assert from 'node:assert/strict';
import test from 'node:test';
import { createReplayClock, REPLAY_RATES, ReplayPlayState } from '../../web_gui/modules/replay-clock.js';
import { interpolateVesselKinematics } from '../../web_gui/modules/kinematics.js';

function drivenClock({ tStart = 0.0, tEnd = 100.0, rate = 1 } = {}) {
  let wallMs = 0;
  const clock = createReplayClock({ now: () => wallMs, tStart, tEnd, rate });
  return {
    clock,
    advance(ms) {
      wallMs += ms;
    },
  };
}

test('rate presets match the frozen #69 set', () => {
  assert.deepEqual(REPLAY_RATES, [0.25, 0.5, 1, 2, 5, 10, 20]);
});

test('playhead advances by wall elapsed × speed and clamps to the trusted range', () => {
  const { clock, advance } = drivenClock({ tEnd: 10.0 });
  clock.play();
  advance(1000);
  assert.equal(clock.tick().playhead, 1.0);
  advance(250);
  assert.equal(clock.tick().playhead, 1.25);
  advance(60_000); // far beyond the trusted end
  assert.equal(clock.tick().playhead, 10.0);
  assert.equal(clock.tick().state, ReplayPlayState.ENDED);
});

test('pause freezes the playhead; ticks while paused are no-ops', () => {
  const { clock, advance } = drivenClock({});
  clock.play();
  advance(2000);
  clock.pause();
  const frozen = clock.playhead;
  advance(5000);
  assert.equal(clock.tick().playhead, frozen);
  assert.equal(clock.state, ReplayPlayState.PAUSED);
});

test('changing rate while playing preserves playhead continuity at the change instant', () => {
  const { clock, advance } = drivenClock({});
  clock.play();
  advance(1000);
  assert.equal(clock.playhead, 1.0);
  clock.setRate(10);
  assert.equal(clock.playhead, 1.0); // no jump at the change instant
  advance(1000);
  assert.equal(clock.tick().playhead, 11.0); // only subsequent elapsed uses 10×
});

test('invalid rate changes are rejected without touching playback', () => {
  const { clock, advance } = drivenClock({});
  clock.play();
  advance(1000);
  assert.equal(clock.setRate(3), 1);
  assert.equal(clock.setRate(0), 1);
  assert.equal(clock.setRate(-5), 1);
  assert.equal(clock.setRate('20x'), 1);
  advance(1000);
  assert.equal(clock.tick().playhead, 2.0);
});

test('reaching trusted t_end transitions to deterministic ENDED; seek backward then play restarts from t_start', () => {
  const { clock, advance } = drivenClock({ tEnd: 2.0 });
  clock.play();
  advance(3000);
  assert.equal(clock.tick().state, ReplayPlayState.ENDED);
  assert.equal(clock.playhead, 2.0);
  advance(1000); // wall time passes while ENDED — nothing moves
  assert.equal(clock.tick().playhead, 2.0);

  clock.seek(1.0);
  assert.equal(clock.state, ReplayPlayState.PAUSED); // seek from ENDED → PAUSED
  clock.play();
  advance(500);
  assert.equal(clock.playhead, 1.5); // resumes from the seeked position
});

test('play from ENDED restarts deterministically from t_start', () => {
  const { clock, advance } = drivenClock({ tStart: 0.5, tEnd: 2.0 });
  clock.play();
  advance(5000);
  assert.equal(clock.tick().state, ReplayPlayState.ENDED);
  clock.play();
  assert.equal(clock.state, ReplayPlayState.PLAYING);
  assert.equal(clock.playhead, 0.5);
  advance(1000);
  assert.equal(clock.playhead, 1.5);
});

test('seek is valid from PLAYING, PAUSED and ENDED and clamps to the trusted range', () => {
  const { clock, advance } = drivenClock({ tEnd: 10.0 });
  clock.play();
  advance(1000);
  clock.seek(5.0);
  assert.equal(clock.playhead, 5.0);
  assert.equal(clock.state, ReplayPlayState.PLAYING); // playback continues at the target
  advance(1000);
  assert.equal(clock.playhead, 6.0);

  clock.seek(-20); // below t_start
  assert.equal(clock.playhead, 0.0);
  clock.seek(99);
  assert.equal(clock.playhead, 10.0);
  clock.seek(Number.NaN); // ignored
  assert.equal(clock.playhead, 10.0);
});

test('hold() freezes wall consumption during BUFFERING; resume() continues without jump', () => {
  const { clock, advance } = drivenClock({});
  clock.play();
  advance(1000);
  clock.hold(); // recorded bracket missing — presentation stops progressing
  advance(4000); // wall time passes while buffering
  assert.equal(clock.playhead, 1.0);
  clock.resume();
  advance(1000);
  assert.equal(clock.tick().playhead, 2.0);
});

test('known literal: (N=0,E=0) → (N=10,E=20) over 2 s shows (5,10) at 1 s of 1× playback', () => {
  const { clock, advance } = drivenClock({ tStart: 0, tEnd: 2, rate: 1 });
  const from = { north: 0, east: 0 };
  const to = { north: 10, east: 20 };
  clock.play();
  advance(1000); // 1 s of wall time at 1× over a 2 s recorded bracket
  const { playhead } = clock.tick();
  const amount = playhead / 2;
  const vessel = interpolateVesselKinematics(from, to, amount);
  assert.equal(vessel.north, 5);
  assert.equal(vessel.east, 10);
});

test('known literal: 359° → 1° playback interpolation passes through north', () => {
  const deg = value => (value * Math.PI) / 180;
  const mid = interpolateVesselKinematics({ psi: deg(359) }, { psi: deg(1) }, 0.5);
  const midDeg = ((mid.psi * 180) / Math.PI + 360) % 360;
  assert.ok(Math.abs(midDeg - 0) < 1e-6, `expected north crossing, got ${midDeg}`);
});
