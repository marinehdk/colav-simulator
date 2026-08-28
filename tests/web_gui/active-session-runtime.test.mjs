import assert from 'node:assert/strict';
import test from 'node:test';

import { createActiveSessionRuntime } from '../../web_gui/modules/active-session-runtime.js';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function createHarness() {
  const requests = [];
  const sockets = [];
  const visibilityListeners = new Set();
  const onlineListeners = new Set();
  const timers = new Map();
  let timerId = 0;
  let now = 1_000;
  let visible = true;
  let focused = true;
  let online = true;

  const http = {
    request(options) {
      const pending = deferred();
      requests.push({ ...options, pending });
      return pending.promise;
    },
  };
  const wsFactory = (url) => {
    const socket = {
      url,
      closeCalls: 0,
      close() { this.closeCalls += 1; },
      open() { this.onopen?.(); },
      message(value) {
        this.onmessage?.({ data: typeof value === 'string' ? value : JSON.stringify(value) });
      },
      disconnect() { this.onclose?.(); },
    };
    sockets.push(socket);
    return socket;
  };
  const scheduler = {
    setTimeout(callback, delay) {
      const id = ++timerId;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
  };
  const visibility = {
    isVisible: () => visible,
    hasFocus: () => focused,
    subscribe(listener) {
      visibilityListeners.add(listener);
      return () => visibilityListeners.delete(listener);
    },
  };
  const connectivity = {
    isOnline: () => online,
    subscribe(listener) {
      onlineListeners.add(listener);
      return () => onlineListeners.delete(listener);
    },
  };
  return {
    runtime: createActiveSessionRuntime({
      http,
      wsFactory,
      scheduler,
      clock: { now: () => now },
      visibility,
      online: connectivity,
    }),
    requests,
    sockets,
    timers,
    runTimer(delay) {
      const entry = [...timers.entries()].find(([, timer]) => timer.delay === delay);
      assert.ok(entry, `missing ${delay} ms timer`);
      timers.delete(entry[0]);
      entry[1].callback();
    },
    setFocus(value) { focused = value; for (const listener of visibilityListeners) listener(); },
    setNow(value) { now = value; },
    setOnline(value) { online = value; for (const listener of onlineListeners) listener(); },
    setVisible(value) { visible = value; for (const listener of visibilityListeners) listener(); },
  };
}

function session(id = 'run-1', state = 'CREATED') {
  return {
    active: true,
    session_id: id,
    state,
    spec: { scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'god' },
    playback: { requested_multiplier: 1 },
  };
}

function telemetry(id = 'run-1', state = 'RUNNING', seq = 1) {
  return {
    schema_version: '1.0',
    run_id: id,
    seq,
    sim_time: seq * 0.1,
    state,
    os: { id: 0 },
    events: [],
  };
}

function httpError(status, message, detail = message) {
  return Object.assign(new Error(message), { status, detail });
}

test('a throwing subscriber stays isolated from later subscribers, command resolution, and error state', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  harness.runtime.subscribe(() => { throw new Error('subscriber DOM sync failed'); });
  const received = [];
  harness.runtime.subscribe((snapshot) => received.push(snapshot));

  const start = harness.runtime.start();
  harness.requests[1].pending.resolve(session('run-1', 'RUNNING'));
  await start;
  const snapshot = harness.runtime.snapshot();
  assert.equal(snapshot.sessionState, 'RUNNING');
  assert.equal(snapshot.error, null);
  assert.ok(received.some((published) => published.sessionState === 'RUNNING'));
});

test('bootstrap is idempotent, publishes loading immediately, and confirms no Active Session', async () => {
  const harness = createHarness();
  const published = [];
  const unsubscribe = harness.runtime.subscribe((snapshot) => published.push(snapshot));

  const first = harness.runtime.bootstrap();
  const second = harness.runtime.bootstrap();

  assert.equal(first, second);
  assert.equal(harness.requests.length, 1);
  assert.equal(harness.requests[0].path, '/api/sessions/current');
  assert.equal(published[0].authority.status, 'loading');
  harness.requests[0].pending.resolve(null);
  await first;

  const snapshot = harness.runtime.snapshot();
  assert.equal(snapshot.authority.status, 'known');
  assert.equal(snapshot.session, null);
  assert.equal(snapshot.sessionState, 'none');
  assert.equal(snapshot.connection.status, 'disconnected');
  unsubscribe();
});

test('adopting an Active Session keeps authority, connection, and lifecycle independent', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;

  assert.equal(harness.runtime.snapshot().authority.status, 'known');
  assert.equal(harness.runtime.snapshot().sessionState, 'CREATED');
  assert.equal(harness.runtime.snapshot().connection.status, 'connecting');
  assert.equal(harness.sockets.length, 1);

  harness.sockets[0].open();
  assert.equal(harness.runtime.snapshot().connection.status, 'connected');
  harness.setNow(1_250);
  harness.sockets[0].message(telemetry());
  const live = harness.runtime.snapshot();
  assert.equal(live.authority.status, 'known');
  assert.equal(live.connection.status, 'connected');
  assert.equal(live.sessionState, 'RUNNING');
  assert.equal(live.telemetry.revision, 1);
  assert.equal(live.telemetry.receivedAt, 1_250);

  harness.sockets[0].disconnect();
  const stale = harness.runtime.snapshot();
  assert.equal(stale.authority.status, 'known');
  assert.equal(stale.connection.status, 'reconnecting');
  assert.equal(stale.sessionState, 'RUNNING');
  assert.deepEqual(stale.telemetry.envelope, telemetry());
  assert.equal(stale.telemetry.staleAgeMs, 0);
});

test('commands are single-flight, skip duplicate lifecycle mutations, and remain revision-bound', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;

  const start = harness.runtime.start();
  const duplicateStart = harness.runtime.start();
  assert.equal(start, duplicateStart);
  assert.equal(harness.requests.length, 2);
  assert.equal(harness.requests[1].path, '/api/sessions/run-1/start');
  assert.equal(harness.runtime.snapshot().pending.command, 'start');
  await assert.rejects(() => harness.runtime.pause(), /in progress/i);

  harness.requests[1].pending.resolve(session('run-1', 'RUNNING'));
  await start;
  assert.equal(harness.runtime.snapshot().sessionState, 'RUNNING');
  assert.equal(harness.runtime.snapshot().pending, null);

  await harness.runtime.start();
  assert.equal(harness.requests.length, 2);

  const pause = harness.runtime.pause();
  harness.requests[2].pending.resolve(session('run-1', 'PAUSED'));
  await pause;
  assert.equal(harness.runtime.snapshot().sessionState, 'PAUSED');

  const step = harness.runtime.step();
  harness.requests[3].pending.resolve(telemetry('run-1', 'PAUSED', 2));
  await step;
  assert.equal(harness.runtime.snapshot().telemetry.revision, 1);

  const speed = harness.runtime.setSpeed(5);
  assert.equal(harness.requests[4].path, '/api/sessions/run-1/speed?multiplier=5');
  harness.requests[4].pending.resolve({ requested_multiplier: 5, effective_multiplier: 4.8 });
  await speed;
  assert.equal(harness.runtime.snapshot().session.playback.requested_multiplier, 5);
});

test('Create, Reset, and Replay replace atomically and stale callbacks cannot cross session identity', async () => {
  const emptyHarness = createHarness();
  const emptyBoot = emptyHarness.runtime.bootstrap();
  emptyHarness.requests[0].pending.resolve(null);
  await emptyBoot;
  const specification = { scenario_id: 'head_on', strict_no_fallback: true };
  const create = emptyHarness.runtime.create(specification);
  assert.equal(emptyHarness.requests[1].path, '/api/sessions');
  assert.equal(emptyHarness.requests[1].timeoutMs, 180_000);
  assert.deepEqual(emptyHarness.requests[1].body, specification);
  emptyHarness.requests[1].pending.resolve(session('created-run'));
  await create;
  assert.equal(emptyHarness.runtime.snapshot().session.session_id, 'created-run');

  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;
  const oldSocket = harness.sockets[0];
  oldSocket.open();
  oldSocket.message(telemetry('run-1', 'PAUSED'));
  const staleMessage = oldSocket.onmessage;

  const reset = harness.runtime.reset();
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-1');
  harness.requests[1].pending.resolve(session('run-2'));
  await reset;
  const replaced = harness.runtime.snapshot();
  assert.equal(replaced.session.session_id, 'run-2');
  assert.equal(replaced.sessionState, 'CREATED');
  assert.equal(replaced.telemetry.envelope, null);
  assert.equal(replaced.outcome.status, 'idle');
  assert.equal(oldSocket.closeCalls, 1);
  assert.equal(harness.sockets.length, 2);

  staleMessage({ data: JSON.stringify(telemetry('run-1', 'FAILED', 99)) });
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-2');
  assert.equal(harness.runtime.snapshot().telemetry.envelope, null);

  harness.sockets[1].message(telemetry('run-2', 'FINISHED', 2));
  const requestCount = harness.requests.length;
  await assert.rejects(() => harness.runtime.replay(), /result/i);
  assert.equal(harness.requests.length, requestCount);
  harness.requests[2].pending.resolve({ manifest: { reproduction_status: 'behavior-compatible' } });
  harness.requests[3].pending.resolve([{ name: 'result.json' }]);
  await new Promise((resolve) => setImmediate(resolve));
  const replay = harness.runtime.replay();
  harness.requests.at(-1).pending.resolve(session('run-3'));
  await replay;
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-3');
});

test('terminal telemetry loads raw outcomes once per session and ignores replacement-stale responses', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;
  harness.sockets[0].message(telemetry('run-1', 'FINISHED'));
  assert.equal(harness.runtime.snapshot().outcome.status, 'loading');
  assert.deepEqual(harness.requests.slice(1).map((request) => request.path), [
    '/api/sessions/run-1/result',
    '/api/sessions/run-1/artifacts',
  ]);
  assert.equal(harness.requests[1].timeoutMs, 30_000);
  assert.equal(harness.requests[2].timeoutMs, 30_000);
  harness.sockets[0].message(telemetry('run-1', 'FINISHED'));
  assert.equal(harness.requests.length, 3);

  const reset = harness.runtime.reset();
  harness.requests[3].pending.resolve(session('run-2'));
  await reset;
  harness.requests[1].pending.resolve({ manifest: { reproduction_status: 'behavior-compatible' } });
  harness.requests[2].pending.resolve([{ name: 'result.json' }]);
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-2');
  assert.equal(harness.runtime.snapshot().outcome.status, 'idle');

  harness.sockets[1].message(telemetry('run-2', 'FAILED'));
  assert.equal(harness.requests.at(-1).path, '/api/sessions/run-2/artifacts');
  const requestCount = harness.requests.length;
  harness.sockets[1].message(telemetry('run-2', 'FAILED'));
  assert.equal(harness.requests.length, requestCount);
  harness.requests.at(-1).pending.resolve([{ name: 'failure.json' }]);
  await new Promise((resolve) => setImmediate(resolve));
  const failed = harness.runtime.snapshot();
  assert.equal(failed.outcome.status, 'ready');
  assert.equal(failed.outcome.result, null);
  assert.deepEqual(failed.outcome.artifacts, [{ name: 'failure.json' }]);
});

test('reconnect uses capped backoff, suspends offline/background, and resumes immediately', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;
  harness.sockets[0].disconnect();
  assert.deepEqual([...harness.timers.values()].map((timer) => timer.delay), [500]);
  harness.runTimer(500);
  assert.equal(harness.sockets.length, 2);
  harness.sockets[1].disconnect();
  assert.deepEqual([...harness.timers.values()].map((timer) => timer.delay), [1_000]);
  harness.runTimer(1_000);
  assert.equal(harness.sockets.length, 3);
  harness.sockets[2].disconnect();
  assert.deepEqual([...harness.timers.values()].map((timer) => timer.delay), [2_000]);
  harness.runTimer(2_000);
  assert.equal(harness.sockets.length, 4);
  harness.sockets[3].disconnect();
  assert.deepEqual([...harness.timers.values()].map((timer) => timer.delay), [5_000]);
  harness.runTimer(5_000);
  assert.equal(harness.sockets.length, 5);
  harness.sockets[4].disconnect();
  assert.deepEqual([...harness.timers.values()].map((timer) => timer.delay), [5_000]);
  harness.runTimer(5_000);
  assert.equal(harness.sockets.length, 6);
  harness.sockets[5].open();

  harness.setOnline(false);
  assert.equal(harness.runtime.snapshot().connection.status, 'disconnected');
  assert.equal(harness.timers.size, 0);
  harness.setOnline(true);
  assert.equal(harness.sockets.length, 7);
  harness.sockets[6].open();
  harness.sockets[6].disconnect();
  assert.deepEqual([...harness.timers.values()].map((timer) => timer.delay), [500]);

  harness.setVisible(false);
  assert.equal(harness.timers.size, 0);
  harness.setVisible(true);
  assert.equal(harness.sockets.length, 8);
});

test('session_not_found refreshes only in foreground and focus adopts authoritative replacement', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;
  harness.setFocus(false);
  harness.sockets[0].message({ error: 'session_not_found' });
  assert.equal(harness.runtime.snapshot().authority.status, 'unknown');
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-1');
  assert.equal(harness.requests.length, 1);

  harness.setFocus(true);
  harness.setVisible(false);
  harness.setVisible(true);
  const adoption = harness.runtime.refreshAuthority();
  assert.equal(harness.requests[1].path, '/api/sessions/current');
  harness.requests[1].pending.resolve(session('run-2', 'PAUSED'));
  await adoption;
  const adopted = harness.runtime.snapshot();
  assert.equal(adopted.authority.status, 'known');
  assert.equal(adopted.session.session_id, 'run-2');
  assert.equal(adopted.sessionState, 'PAUSED');

  harness.sockets[1].message({ error: 'session_not_found' });
  assert.equal(harness.runtime.snapshot().authority.status, 'unknown');
  const requestCount = harness.requests.length;
  await assert.rejects(() => harness.runtime.start(), /authority/i);
  assert.equal(harness.requests.length, requestCount);
  harness.requests.at(-1).pending.resolve(session('run-2', 'PAUSED'));
  await harness.runtime.refreshAuthority();

  const refreshed = harness.runtime.refreshAuthority();
  harness.requests.at(-1).pending.resolve(null);
  await refreshed;
  assert.equal(harness.runtime.snapshot().authority.status, 'known');
  assert.equal(harness.runtime.snapshot().session, null);
  assert.equal(harness.runtime.snapshot().sessionState, 'none');
});

test('raw telemetry rejects malformed JSON, wrong identity, and schema gaps without sequence dedup', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;
  const socket = harness.sockets[0];

  socket.message('{bad json');
  assert.equal(harness.runtime.snapshot().telemetry.revision, 0);
  assert.equal(harness.runtime.snapshot().error.kind, 'telemetry');
  socket.message({ schema_version: '1.0', run_id: 'wrong', state: 'RUNNING' });
  assert.equal(harness.runtime.snapshot().telemetry.revision, 0);
  socket.message({ run_id: 'run-1', state: 'RUNNING' });
  assert.equal(harness.runtime.snapshot().telemetry.revision, 0);
  socket.message({ schema_version: '1.0', run_id: 'run-1', state: 'RUNNING' });
  assert.equal(harness.runtime.snapshot().telemetry.revision, 0);
  socket.message({ ...telemetry(), schema_version: '2.0' });
  assert.equal(harness.runtime.snapshot().telemetry.revision, 0);

  socket.message(telemetry('run-1', 'RUNNING', 7));
  socket.message(telemetry('run-1', 'RUNNING', 7));
  assert.equal(harness.runtime.snapshot().telemetry.revision, 2);
});

test('mutation timeout unlocks command, marks authority unknown, and reconciles without retrying mutation', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'RUNNING'));
  await boot;
  const pause = harness.runtime.pause();
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/pause')).length, 1);
  harness.runTimer(15_000);
  await assert.rejects(pause, /timed out/i);
  assert.equal(harness.requests[1].signal.aborted, true);
  assert.equal(harness.runtime.snapshot().pending, null);
  assert.equal(harness.runtime.snapshot().authority.status, 'unknown');
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/pause')).length, 1);
  assert.equal(harness.requests.at(-1).path, '/api/sessions/current');
  harness.requests.at(-1).pending.resolve(session('run-2', 'PAUSED'));
  await harness.runtime.refreshAuthority();
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-2');
});

test('destroy cancels transport/timers/listeners and ignores late callbacks', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;
  const socket = harness.sockets[0];
  const staleMessage = socket.onmessage;
  socket.disconnect();
  assert.equal(harness.timers.size, 1);

  harness.runtime.destroy();
  assert.equal(harness.timers.size, 0);
  assert.equal(harness.runtime.snapshot().connection.status, 'disconnected');
  staleMessage({ data: JSON.stringify(telemetry('run-1', 'FAILED')) });
  assert.equal(harness.runtime.snapshot().telemetry.revision, 0);
  await assert.rejects(() => harness.runtime.start(), /destroyed/i);
  await assert.rejects(() => harness.runtime.bootstrap(), /destroyed/i);
  harness.setOnline(false);
  harness.setOnline(true);
  assert.equal(harness.sockets.length, 1);
});

test('422 stays local while 409 and 404 reconcile authority without mutation retry', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  const invalid = harness.runtime.start();
  harness.requests[1].pending.reject(httpError(422, 'invalid command', { status: 'INVALID', reason: 'bad input' }));
  await assert.rejects(invalid, /invalid command/);
  assert.equal(harness.runtime.snapshot().error.kind, 'validation');
  assert.equal(harness.runtime.snapshot().authority.status, 'known');
  assert.equal(harness.requests.length, 2);

  const conflict = harness.runtime.start();
  harness.requests[2].pending.reject(httpError(409, 'stale lifecycle'));
  await assert.rejects(conflict, /stale lifecycle/);
  assert.equal(harness.runtime.snapshot().error.kind, 'conflict');
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/start')).length, 2);
  assert.equal(harness.requests[3].path, '/api/sessions/current');
  harness.requests[3].pending.resolve(session('run-1', 'RUNNING'));
  await harness.runtime.refreshAuthority();

  const missing = harness.runtime.pause();
  harness.requests[4].pending.reject(httpError(404, 'missing session'));
  await assert.rejects(missing, /missing session/);
  assert.equal(harness.runtime.snapshot().authority.status, 'unknown');
  assert.equal(harness.requests[5].path, '/api/sessions/current');
  harness.requests[5].pending.resolve(session('run-2', 'PAUSED'));
  await harness.runtime.refreshAuthority();
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-2');
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/pause')).length, 1);
});

test('public lifecycle gates reject invalid states without network mutations', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'RUNNING'));
  await boot;
  const initialRequests = harness.requests.length;
  await harness.runtime.start();
  await assert.rejects(() => harness.runtime.step(), /CREATED or PAUSED/i);
  await assert.rejects(() => harness.runtime.create({ scenario_id: 'head_on' }), /RUNNING/i);
  await assert.rejects(() => harness.runtime.replay(), /FINISHED/i);
  assert.equal(harness.requests.length, initialRequests);

  const pause = harness.runtime.pause();
  harness.requests.at(-1).pending.resolve(session('run-1', 'PAUSED'));
  await pause;
  const pausedRequests = harness.requests.length;
  await harness.runtime.pause();
  await assert.rejects(() => harness.runtime.replay(), /FINISHED/i);
  assert.equal(harness.requests.length, pausedRequests);

  harness.sockets[0].message(telemetry('run-1', 'FAILED'));
  const failedRequests = harness.requests.length;
  await assert.rejects(() => harness.runtime.start(), /CREATED or PAUSED/i);
  await assert.rejects(() => harness.runtime.step(), /CREATED or PAUSED/i);
  assert.equal(harness.requests.length, failedRequests);
});

test('reset is permitted while RUNNING but Create remains blocked', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'RUNNING'));
  await boot;

  await assert.rejects(() => harness.runtime.create({ scenario_id: 'head_on' }), /RUNNING/i);
  assert.equal(harness.requests.length, 1);

  const reset = harness.runtime.reset();
  assert.equal(harness.requests[1].path, '/api/sessions/run-1/reset');
  harness.requests[1].pending.resolve(session('run-2', 'CREATED'));
  await reset;
  const replaced = harness.runtime.snapshot();
  assert.equal(replaced.session.session_id, 'run-2');
  assert.equal(replaced.sessionState, 'CREATED');
});

test('bootstrap failure exposes unknown authority and permits a clean authority retry', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.reject(httpError(503, 'service unavailable'));
  await assert.rejects(boot, /service unavailable/);
  const failed = harness.runtime.snapshot();
  assert.equal(failed.authority.status, 'unknown');
  assert.equal(failed.authority.error.kind, 'server');

  const retry = harness.runtime.refreshAuthority();
  harness.requests[1].pending.resolve(session('recovered'));
  await retry;
  assert.equal(harness.runtime.snapshot().authority.status, 'known');
  assert.equal(harness.runtime.snapshot().session.session_id, 'recovered');

  const idempotent = harness.runtime.bootstrap();
  assert.notEqual(idempotent, boot);
  harness.requests[2].pending.resolve(session('recovered'));
  await idempotent;
});

test('command responses are bound to session identity and authority revision', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  const start = harness.runtime.start();
  const refresh = harness.runtime.refreshAuthority();
  harness.requests[2].pending.resolve({ ...session('run-1', 'PAUSED'), sequence: 9 });
  await refresh;
  harness.requests[1].pending.resolve(session('run-1', 'RUNNING'));
  await assert.rejects(start, /ignored/i);

  assert.equal(harness.runtime.snapshot().sessionState, 'PAUSED');
  assert.equal(harness.runtime.snapshot().session.sequence, 9);
  assert.equal(harness.runtime.snapshot().pending, null);
});

test('telemetry keeps flowing while the window is unfocused but visible', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'RUNNING'));
  await boot;
  assert.equal(harness.sockets.length, 1);
  harness.sockets[0].open();

  // User clicks into another application: window blurs but stays visible.
  harness.setFocus(false);
  assert.equal(harness.sockets[0].closeCalls, 0);
  assert.equal(harness.runtime.snapshot().connection.status, 'connected');

  harness.sockets[0].message(telemetry('run-1', 'RUNNING', 1));
  assert.equal(harness.runtime.snapshot().telemetry.envelope.seq, 1);

  harness.sockets[0].message(telemetry('run-1', 'RUNNING', 2));
  assert.equal(harness.runtime.snapshot().telemetry.envelope.seq, 2);
});

test('late REST lifecycle response cannot overwrite a newer terminal WebSocket state', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  const start = harness.runtime.start();
  harness.sockets[0].message(telemetry('run-1', 'FINISHED', 8));
  harness.requests[1].pending.resolve(session('run-1', 'RUNNING'));
  await assert.rejects(start, /ignored/i);

  assert.equal(harness.runtime.snapshot().sessionState, 'FINISHED');
  assert.equal(harness.runtime.snapshot().telemetry.envelope.seq, 8);
});

test('step rejects older sequence while repeated telemetry does not invalidate speed response', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  const step = harness.runtime.step();
  harness.sockets[0].message(telemetry('run-1', 'PAUSED', 4));
  harness.requests[1].pending.resolve(telemetry('run-1', 'PAUSED', 3));
  await assert.rejects(step, /ignored/i);
  assert.equal(harness.runtime.snapshot().telemetry.envelope.seq, 4);

  const speed = harness.runtime.setSpeed(2);
  harness.sockets[0].message(telemetry('run-1', 'PAUSED', 4));
  harness.sockets[0].message(telemetry('run-1', 'PAUSED', 4));
  harness.requests[2].pending.resolve({ requested_multiplier: 2 });
  await speed;
  assert.equal(harness.runtime.snapshot().session.playback.requested_multiplier, 2);
});

test('errored outcome retries through authority refresh and unblocks replay', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1'));
  await boot;
  harness.sockets[0].message(telemetry('run-1', 'FINISHED', 1));
  harness.requests[1].pending.reject(httpError(503, 'result temporarily unavailable'));
  harness.requests[2].pending.resolve([]);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(harness.runtime.snapshot().outcome.status, 'error');

  const refreshed = harness.runtime.refreshAuthority();
  harness.requests[3].pending.resolve(session('run-1', 'FINISHED'));
  await refreshed;
  assert.equal(harness.requests[4].path, '/api/sessions/run-1/result');
  harness.requests[4].pending.resolve({ manifest: { reproduction_status: 'behavior-compatible' } });
  harness.requests[5].pending.resolve([{ name: 'result.json' }]);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(harness.runtime.snapshot().outcome.status, 'ready');

  const replay = harness.runtime.replay();
  harness.requests[6].pending.resolve(session('run-2'));
  await replay;
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-2');
});

test('persistently failing outcome retry sticks until the next authority refresh', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1'));
  await boot;
  harness.sockets[0].message(telemetry('run-1', 'FINISHED', 1));
  harness.requests[1].pending.reject(httpError(503, 'result unavailable'));
  harness.requests[2].pending.resolve([]);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(harness.runtime.snapshot().outcome.status, 'error');

  const refreshed = harness.runtime.refreshAuthority();
  harness.requests[3].pending.resolve(session('run-1', 'FINISHED'));
  await refreshed;
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/result')).length, 2);
  harness.requests[4].pending.reject(httpError(503, 'result unavailable'));
  harness.requests[5].pending.resolve([]);
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));

  const stuck = harness.runtime.snapshot();
  assert.equal(stuck.outcome.status, 'error');
  assert.equal(stuck.authority.status, 'known');
  assert.equal(harness.requests.filter((request) => request.path === '/api/sessions/current').length, 2);
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/result')).length, 2);

  const secondRefresh = harness.runtime.refreshAuthority();
  harness.requests[6].pending.resolve(session('run-1', 'FINISHED'));
  await secondRefresh;
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/result')).length, 3);
});

test('terminal outcome conflict refreshes authority once without retrying outcome reads', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session());
  await boot;
  harness.sockets[0].message(telemetry('run-1', 'FINISHED'));
  harness.requests[1].pending.reject(httpError(409, 'result not ready'));
  harness.requests[2].pending.resolve([]);
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(harness.runtime.snapshot().outcome.status, 'error');
  assert.equal(harness.runtime.snapshot().outcome.error.kind, 'conflict');
  assert.equal(harness.requests[3].path, '/api/sessions/current');
  const resultReads = harness.requests.filter((request) => request.path.endsWith('/result')).length;
  harness.sockets[0].message(telemetry('run-1', 'FINISHED'));
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/result')).length, resultReads);
  harness.requests[3].pending.resolve(session('run-1', 'FINISHED'));
  await harness.runtime.refreshAuthority();
});

test('REST lifecycle commands complete while the telemetry socket is disconnected', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'RUNNING'));
  await boot;
  harness.sockets[0].open();
  harness.sockets[0].disconnect();
  const severed = harness.runtime.snapshot();
  assert.equal(severed.connection.status, 'reconnecting');
  assert.equal(severed.authority.status, 'known');

  const pause = harness.runtime.pause();
  harness.requests[1].pending.resolve(session('run-1', 'PAUSED'));
  await pause;
  const paused = harness.runtime.snapshot();
  assert.equal(paused.authority.status, 'known');
  assert.equal(paused.session.session_id, 'run-1');
  assert.equal(paused.sessionState, 'PAUSED');
  assert.equal(paused.error, null);
});

test('server 5xx on a lifecycle command retains authority and normalizes the error', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  const start = harness.runtime.start();
  harness.requests[1].pending.reject(httpError(503, 'backend restarting'));
  await assert.rejects(start, /backend restarting/);
  const snapshot = harness.runtime.snapshot();
  assert.equal(snapshot.authority.status, 'known');
  assert.equal(snapshot.session.session_id, 'run-1');
  assert.equal(snapshot.error.kind, 'server');
  assert.equal(snapshot.error.status, 503);
  assert.equal(harness.requests.length, 2);
});

test('expected old-socket not_found waits for pending replacement without competing authority GET', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  const reset = harness.runtime.reset();
  harness.sockets[0].message({ error: 'session_not_found' });
  const waiting = harness.runtime.snapshot();
  assert.equal(waiting.authority.status, 'known');
  assert.equal(waiting.pending.command, 'reset');
  assert.equal(waiting.error, null);
  assert.equal(waiting.connection.status, 'disconnected');
  assert.equal(harness.requests.length, 2);

  harness.requests[1].pending.resolve(session('run-2'));
  await reset;
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-2');
  assert.equal(harness.sockets.length, 2);
});

test('locally failed replacement retains the old session and reconnects its suspended transport', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;
  harness.sockets[0].open();

  const reset = harness.runtime.reset();
  harness.sockets[0].message({ error: 'session_not_found' });
  const suspended = harness.runtime.snapshot();
  assert.equal(suspended.connection.status, 'disconnected');
  assert.equal(suspended.pending.command, 'reset');

  harness.requests[1].pending.reject(httpError(422, 'reset rejected'));
  await assert.rejects(reset, /reset rejected/);
  const retained = harness.runtime.snapshot();
  assert.equal(retained.session.session_id, 'run-1');
  assert.equal(retained.authority.status, 'known');
  assert.equal(retained.error.kind, 'validation');

  harness.runTimer(500);
  assert.equal(harness.sockets.length, 2);
  assert.equal(harness.runtime.snapshot().connection.status, 'reconnecting');
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/reset')).length, 1);
});

test('ambiguous replacement network loss reconciles authority while light-control network loss retains it', async () => {
  const harness = createHarness();
  const boot = harness.runtime.bootstrap();
  harness.requests[0].pending.resolve(session('run-1', 'PAUSED'));
  await boot;

  const start = harness.runtime.start();
  harness.requests[1].pending.reject(new TypeError('network unavailable'));
  await assert.rejects(start, /network unavailable/);
  assert.equal(harness.runtime.snapshot().authority.status, 'known');
  assert.equal(harness.requests.length, 2);

  const reset = harness.runtime.reset();
  harness.requests[2].pending.reject(new TypeError('response lost after submit'));
  await assert.rejects(reset, /response lost/);
  assert.equal(harness.runtime.snapshot().authority.status, 'unknown');
  assert.equal(harness.requests.filter((request) => request.path.endsWith('/reset')).length, 1);
  assert.equal(harness.requests[3].path, '/api/sessions/current');
  harness.requests[3].pending.resolve(session('run-2'));
  await harness.runtime.refreshAuthority();
  assert.equal(harness.runtime.snapshot().session.session_id, 'run-2');
});
