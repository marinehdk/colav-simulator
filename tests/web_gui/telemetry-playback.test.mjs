import assert from 'node:assert/strict';
import test from 'node:test';
import { createTelemetryPlayback } from '../../web_gui/modules/telemetry-playback.js';

function harness() {
  let now = 0, id = 0;
  const timers = new Map(), output = [];
  const player = createTelemetryPlayback({
    publish: value => output.push({ at: now, value }), clock: { now: () => now },
    scheduler: {
      setTimeout(cb, ms) { timers.set(++id, { cb, at: now + ms }); return id; },
      clearTimeout(key) { timers.delete(key); },
    },
  });
  return { player, output, advance(to) {
    while (true) {
      const due = [...timers].sort((a,b) => a[1].at - b[1].at)[0];
      if (!due || due[1].at > to) break;
      timers.delete(due[0]); now = due[1].at; due[1].cb();
    }
    now = to;
  } };
}
function snapshot(seq, sim, state = 'RUNNING', run = 'a') {
  return { session: { session_id: run }, sessionState: state, pending: null,
    telemetry: { revision: seq, envelope: { run_id: run, seq, sim_time: sim, state,
      os: { x: sim * 6 }, playback: { requested_multiplier: 5 },
      threat_management: { witness_time: sim } } } };
}

test('three-second real-frame reserve spans an optimizer stall without inventing motion', () => {
  const h = harness(); let seq = 0, sim = 0;
  for (let t = 0; t <= 16000; t += 100) {
    h.advance(t);
    if (t >= 6000 && t < 8800) continue;
    h.player.push(snapshot(++seq, sim)); sim += 0.5;
  }
  const during = h.output.filter(x => x.at >= 6000 && x.at <= 8800);
  assert.ok(during.length > 15, `only ${during.length} updates during solve`);
  for (let i = 1; i < during.length; i++) assert.ok(during[i].at - during[i-1].at <= 250);
  for (const { value } of h.output) {
    const e = value.telemetry.envelope;
    assert.ok(Math.abs(e.os.x - e.sim_time * 6) < 1e-8);
    assert.equal(e.threat_management.witness_time, e.presentation.source_sim_time_s);
    assert.ok(e.threat_management.witness_time <= e.sim_time);
    assert.ok(e.sim_time - e.threat_management.witness_time <= 0.5 + 1e-9);
  }
  assert.ok(Math.max(...h.output.map(x => x.value.telemetry.envelope.presentation?.delay_s || 0)) <= 3.2, JSON.stringify(h.output.map(x => [x.at, x.value.telemetry.envelope.presentation?.delay_s]).filter(x => x[1] > 3.2)));
  h.player.destroy();
});

test('pause and session replacement flush delayed frames immediately', () => {
  const h = harness(); h.player.push(snapshot(1,0)); h.advance(100); h.player.push(snapshot(2,0.5));
  h.player.push(snapshot(3,0.5,'PAUSED'));
  assert.equal(h.output.at(-1).value.telemetry.envelope.state,'PAUSED');
  h.player.push(snapshot(1,0,'CREATED','b')); h.advance(5000);
  assert.equal(h.output.at(-1).value.telemetry.envelope.run_id,'b');
  h.player.destroy();
});

test('terminal status drains real frames, then never replays them', () => {
  const h = harness();
  h.player.push(snapshot(1,0)); h.advance(100); h.player.push(snapshot(2,0.5));
  h.advance(200); h.player.push(snapshot(3,1,'FINISHED'));
  assert.notEqual(h.output.at(-1).value.telemetry.envelope.state,'FINISHED');
  h.advance(5000);
  assert.equal(h.output.at(-1).value.telemetry.envelope.state,'FINISHED');
  const count = h.output.length; h.advance(9000); assert.equal(h.output.length,count);
  h.player.destroy();
});

test('an outage longer than the reserve holds the last real position and exposes buffering', () => {
  const h = harness(); h.player.push(snapshot(1,0)); h.advance(100); h.player.push(snapshot(2,0.5));
  h.advance(12000);
  const e = h.output.at(-1).value.telemetry.envelope;
  assert.equal(e.os.x,3);
  assert.equal(e.sim_time,0.5);
  assert.equal(e.presentation.buffering,true);
  h.player.destroy();
});
