const SESSION_STATES = new Set(['CREATED', 'RUNNING', 'PAUSED', 'FINISHED', 'FAILED']);
const RECONNECT_DELAYS_MS = [500, 1_000, 2_000, 5_000];

class RuntimeTimeoutError extends Error {
  constructor(path, timeoutMs) {
    super(`${path} timed out after ${timeoutMs} ms.`);
    this.name = 'TimeoutError';
  }
}

class StaleOperationError extends Error {
  constructor(command) {
    super(`${command} response was ignored because Active Session authority advanced.`);
    this.name = 'StaleOperationError';
  }
}

function clone(value) {
  return value === undefined ? undefined : structuredClone(value);
}

function initialState() {
  return {
    authority: { status: 'loading', error: null },
    connection: { status: 'disconnected', staleSince: null },
    session: null,
    sessionState: 'none',
    sessionRevision: 0,
    lifecycleRevision: 0,
    telemetry: { envelope: null, revision: 0, receivedAt: null, staleAgeMs: null },
    pending: null,
    error: null,
    outcome: { status: 'idle', result: null, artifacts: null, error: null },
  };
}

export function createActiveSessionRuntime({ http, wsFactory, scheduler, clock, visibility, online }) {
  const listeners = new Set();
  let state = initialState();
  let bootstrapPromise = null;
  let socket = null;
  let socketGeneration = 0;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  let destroyed = false;
  let pendingOperation = null;
  let outcomeSessionId = null;
  let authorityPromise = null;
  let environmentBound = false;
  let unsubscribeVisibility = null;
  let unsubscribeOnline = null;
  const requestControllers = new Set();

  function normalizeError(error, fallbackKind = 'request') {
    const status = Number.isInteger(error?.status) ? error.status : null;
    const kind = error?.name === 'TimeoutError'
      ? 'timeout'
      : error?.name === 'StaleOperationError'
        ? 'stale'
      : status === 404
        ? 'not_found'
        : status === 409
          ? 'conflict'
          : status === 422
            ? 'validation'
            : status !== null && status >= 500
              ? 'server'
              : fallbackKind;
    return {
      kind,
      message: String(error?.message || error),
      status,
      detail: error?.detail ?? null,
    };
  }

  function request({ method, path, body, timeoutMs }) {
    const controller = new AbortController();
    requestControllers.add(controller);
    let timeoutId = null;
    const timeout = new Promise((_, reject) => {
      timeoutId = scheduler.setTimeout(() => {
        controller.abort();
        reject(new RuntimeTimeoutError(path, timeoutMs));
      }, timeoutMs);
    });
    return Promise.race([
      Promise.resolve(http.request({ method, path, body, signal: controller.signal, timeoutMs })),
      timeout,
    ]).finally(() => {
      if (timeoutId !== null) scheduler.clearTimeout(timeoutId);
      requestControllers.delete(controller);
    });
  }

  function snapshot() {
    const next = clone(state);
    if (next.telemetry.receivedAt !== null && next.connection.status !== 'connected') {
      next.telemetry.staleAgeMs = Math.max(0, clock.now() - next.telemetry.receivedAt);
    }
    return next;
  }

  function publish() {
    const next = snapshot();
    // Listener failures are isolated so one broken view cannot corrupt
    // command resolution or starve the remaining subscribers.
    for (const listener of listeners) {
      try {
        listener(next);
      } catch {
        /* swallowed by design: core runtime avoids console output */
      }
    }
  }

  function setConnection(status) {
    const staleSince = status === 'connected' || state.telemetry.receivedAt === null
      ? null
      : (state.connection.staleSince ?? clock.now());
    state = { ...state, connection: { status, staleSince } };
    publish();
  }

  function stopSocket() {
    socketGeneration += 1;
    if (reconnectTimer !== null) scheduler.clearTimeout(reconnectTimer);
    reconnectTimer = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
    }
    socket = null;
  }

  function suspendTransport() {
    stopSocket();
    state = {
      ...state,
      connection: {
        status: 'disconnected',
        staleSince: state.telemetry.receivedAt === null
          ? null
          : (state.connection.staleSince ?? clock.now()),
      },
    };
    publish();
  }

  function canConnect() {
    return !destroyed
      && Boolean(state.session?.session_id)
      && online.isOnline()
      && visibility.isVisible();
  }

  function scheduleReconnect(sessionId, generation) {
    if (!canConnect() || reconnectTimer !== null) return;
    const delay = RECONNECT_DELAYS_MS[Math.min(reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)];
    reconnectAttempt += 1;
    reconnectTimer = scheduler.setTimeout(() => {
      reconnectTimer = null;
      if (generation !== socketGeneration || sessionId !== state.session?.session_id) return;
      connectSocket(true);
    }, delay);
  }

  function validTelemetry(envelope, sessionId) {
    return envelope
      && typeof envelope === 'object'
      && envelope.schema_version === '1.0'
      && envelope.run_id === sessionId
      && SESSION_STATES.has(envelope.state)
      && Number.isInteger(envelope.seq)
      && envelope.seq >= 0
      && Number.isFinite(envelope.sim_time);
  }

  function applyTelemetry(envelope, sessionId) {
    if (!validTelemetry(envelope, sessionId)) {
      state = {
        ...state,
        error: { kind: 'telemetry', message: 'Invalid Telemetry Envelope.', status: null, detail: null },
      };
      publish();
      return;
    }
    const receivedAt = clock.now();
    const lifecycleChanged = envelope.state !== state.sessionState;
    state = {
      ...state,
      session: { ...state.session, state: envelope.state },
      sessionState: envelope.state,
      lifecycleRevision: state.lifecycleRevision + (lifecycleChanged ? 1 : 0),
      telemetry: {
        envelope: clone(envelope),
        revision: state.telemetry.revision + 1,
        receivedAt,
        staleAgeMs: null,
      },
      error: null,
    };
    publish();
    if (envelope.state === 'FINISHED' || envelope.state === 'FAILED') {
      loadOutcome(sessionId, envelope.state);
    }
  }

  function loadOutcome(sessionId, terminalState, { retry = false } = {}) {
    if (outcomeSessionId === sessionId && !(retry && state.outcome.status === 'error')) return;
    outcomeSessionId = sessionId;
    state = {
      ...state,
      outcome: { status: 'loading', result: null, artifacts: null, error: null },
    };
    publish();
    const resultPromise = terminalState === 'FINISHED'
      ? request({ method: 'GET', path: `/api/sessions/${encodeURIComponent(sessionId)}/result`, timeoutMs: 30_000 })
      : Promise.resolve(null);
    const artifactsPromise = request({
      method: 'GET',
      path: `/api/sessions/${encodeURIComponent(sessionId)}/artifacts`,
      timeoutMs: 30_000,
    });
    Promise.all([resultPromise, artifactsPromise]).then(([result, artifacts]) => {
      if (destroyed || outcomeSessionId !== sessionId || state.session?.session_id !== sessionId) return;
      state = {
        ...state,
        outcome: { status: 'ready', result: clone(result), artifacts: clone(artifacts), error: null },
      };
      publish();
    }).catch((error) => {
      if (destroyed || outcomeSessionId !== sessionId || state.session?.session_id !== sessionId) return;
      const normalized = normalizeError(error, 'outcome');
      // Retries stay passive: recovery refreshes are only driven by the
      // initial load so a persistently failing outcome cannot loop.
      if (!retry) {
        if (normalized.kind === 'not_found') {
          markAuthorityUnknown(error);
          refreshAuthority({ preserveUnknown: true }).catch(() => {});
        } else if (normalized.kind === 'conflict') {
          refreshAuthority().catch(() => {});
        }
      }
      state = {
        ...state,
        outcome: {
          status: 'error',
          result: null,
          artifacts: null,
          error: normalized,
        },
      };
      publish();
    });
  }

  function acceptTelemetry(envelope, sessionId, generation) {
    if (generation !== socketGeneration || socket === null || state.session?.session_id !== sessionId) return;
    applyTelemetry(envelope, sessionId);
  }

  function connectSocket(isReconnect = false) {
    if (!canConnect()) {
      setConnection('disconnected');
      return;
    }
    stopSocket();
    const sessionId = state.session.session_id;
    const generation = socketGeneration;
    setConnection(isReconnect ? 'reconnecting' : 'connecting');
    const nextSocket = wsFactory(`/ws/sessions/${encodeURIComponent(sessionId)}`);
    socket = nextSocket;
    nextSocket.onopen = () => {
      if (nextSocket !== socket || generation !== socketGeneration || sessionId !== state.session?.session_id) return;
      reconnectAttempt = 0;
      setConnection('connected');
    };
    nextSocket.onmessage = (event) => {
      if (nextSocket !== socket || generation !== socketGeneration || sessionId !== state.session?.session_id) return;
      let envelope;
      try {
        envelope = JSON.parse(event.data);
      } catch {
        acceptTelemetry(null, sessionId, generation);
        return;
      }
      if (envelope?.error === 'session_not_found') {
        handleSessionNotFound(sessionId, generation);
        return;
      }
      acceptTelemetry(envelope, sessionId, generation);
    };
    nextSocket.onclose = () => {
      if (nextSocket !== socket || generation !== socketGeneration || sessionId !== state.session?.session_id) return;
      socket = null;
      setConnection(canConnect() ? 'reconnecting' : 'disconnected');
      scheduleReconnect(sessionId, generation);
    };
    nextSocket.onerror = () => {
      if (nextSocket !== socket || generation !== socketGeneration) return;
      state = { ...state, error: { kind: 'telemetry', message: 'Telemetry connection error.', status: null, detail: null } };
      publish();
    };
  }

  function markAuthorityUnknown(error) {
    stopSocket();
    const normalized = normalizeError(error, 'authority');
    state = {
      ...state,
      connection: {
        status: 'disconnected',
        staleSince: state.telemetry.receivedAt === null
          ? null
          : (state.connection.staleSince ?? clock.now()),
      },
      authority: {
        status: 'unknown',
        error: normalized,
      },
    };
    publish();
  }

  function handleSessionNotFound(sessionId, generation) {
    if (generation !== socketGeneration || sessionId !== state.session?.session_id) return;
    if (pendingOperation && ['create', 'reset', 'replay'].includes(pendingOperation.command)) {
      suspendTransport();
      return;
    }
    if (!visibility.isVisible() || !visibility.hasFocus()) {
      markAuthorityUnknown(new Error('Background tab observed a missing Active Session.'));
      return;
    }
    markAuthorityUnknown(new Error('Active Session identity is no longer authoritative.'));
    refreshAuthority({ preserveUnknown: true }).catch(() => {});
  }

  function applyAuthoritySession(session) {
    const currentId = state.session?.session_id || null;
    const nextId = session?.session_id || null;
    if (currentId !== nextId) {
      adoptSession(session);
      return;
    }
    const lifecycleChanged = (session?.state || 'none') !== state.sessionState;
    state = {
      ...state,
      authority: { status: 'known', error: null },
      session: session ? { ...state.session, ...clone(session) } : null,
      sessionState: session?.state || 'none',
      sessionRevision: state.sessionRevision + 1,
      lifecycleRevision: state.lifecycleRevision + (lifecycleChanged ? 1 : 0),
      error: null,
    };
    publish();
    if (session && !socket && canConnect()) connectSocket(false);
    if (
      session
      && (session.state === 'FINISHED' || session.state === 'FAILED')
      && state.outcome.status === 'error'
    ) {
      loadOutcome(session.session_id, session.state, { retry: true });
    }
  }

  function refreshAuthority({ preserveUnknown = false } = {}) {
    if (destroyed) return Promise.reject(new Error('Active Session Runtime is destroyed.'));
    if (authorityPromise) return authorityPromise;
    if (!preserveUnknown) {
      state = { ...state, authority: { status: 'loading', error: null } };
      publish();
    }
    authorityPromise = request({ method: 'GET', path: '/api/sessions/current', timeoutMs: 15_000 })
      .then((session) => {
        if (!destroyed) applyAuthoritySession(session);
        return snapshot();
      })
      .catch((error) => {
        if (!destroyed) markAuthorityUnknown(error);
        throw error;
      })
      .finally(() => {
        authorityPromise = null;
      });
    return authorityPromise;
  }

  function handleEnvironmentChange() {
    if (destroyed || !bootstrapPromise) return;
    if (!online.isOnline() || !visibility.isVisible()) {
      suspendTransport();
      return;
    }
    if (state.authority.status === 'unknown') {
      refreshAuthority({ preserveUnknown: true }).catch(() => {});
      return;
    }
    if (state.authority.status === 'known' && state.session && !socket) connectSocket(false);
  }

  function bindEnvironment() {
    if (environmentBound) return;
    environmentBound = true;
    unsubscribeVisibility = visibility.subscribe(handleEnvironmentChange);
    unsubscribeOnline = online.subscribe(handleEnvironmentChange);
  }

  function adoptSession(session) {
    stopSocket();
    reconnectAttempt = 0;
    outcomeSessionId = null;
    state = {
      ...state,
      authority: { status: 'known', error: null },
      session: session ? clone(session) : null,
      sessionState: session?.state || 'none',
      sessionRevision: state.sessionRevision + 1,
      lifecycleRevision: state.lifecycleRevision + 1,
      connection: { status: session ? 'connecting' : 'disconnected', staleSince: null },
      telemetry: { envelope: null, revision: 0, receivedAt: null, staleAgeMs: null },
      error: null,
      outcome: { status: 'idle', result: null, artifacts: null, error: null },
    };
    publish();
    if (session) connectSocket(false);
  }

  function bootstrap() {
    if (destroyed) return Promise.reject(new Error('Active Session Runtime is destroyed.'));
    if (bootstrapPromise) return bootstrapPromise;
    bindEnvironment();
    bootstrapPromise = request({ method: 'GET', path: '/api/sessions/current', timeoutMs: 15_000 })
      .then((session) => {
        if (!destroyed) adoptSession(session);
        return snapshot();
      })
      .catch((error) => {
        if (!destroyed) markAuthorityUnknown(error);
        bootstrapPromise = null;
        throw error;
      });
    return bootstrapPromise;
  }

  function requireCommand(command) {
    if (destroyed) throw new Error('Active Session Runtime is destroyed.');
    if (state.authority.status !== 'known') throw new Error('Session Authority is unknown.');
    if (!state.session?.session_id) throw new Error(`No Active Session for ${command}.`);
  }

  function recoverMutationAuthority(error, { ambiguousReplacement = false } = {}) {
    const normalized = normalizeError(error);
    if (
      normalized.kind === 'timeout'
      || normalized.kind === 'not_found'
      || (ambiguousReplacement && normalized.kind === 'request' && normalized.status === null)
    ) {
      markAuthorityUnknown(error);
      refreshAuthority({ preserveUnknown: true }).catch(() => {});
    } else if (normalized.kind === 'conflict') {
      refreshAuthority().catch(() => {});
    }
    return normalized;
  }

  function mutate(command, { path, timeoutMs = 15_000, body, apply, duplicate = false }) {
    try {
      requireCommand(command);
    } catch (error) {
      return Promise.reject(error);
    }
    if (pendingOperation) {
      return pendingOperation.command === command
        ? pendingOperation.promise
        : Promise.reject(new Error(`${pendingOperation.command} is already in progress.`));
    }
    if (duplicate) return Promise.resolve(snapshot());
    const sessionId = state.session.session_id;
    const revision = state.sessionRevision;
    const token = {
      command,
      sessionId,
      revision,
      lifecycleRevision: state.lifecycleRevision,
      telemetrySequence: Number(state.telemetry.envelope?.seq ?? state.session?.sequence ?? 0),
    };
    state = { ...state, pending: token, error: null };
    publish();
    const promise = request({ method: 'POST', path, body, timeoutMs })
      .then((response) => {
        if (
          destroyed
          || pendingOperation?.token !== token
          || state.session?.session_id !== sessionId
        ) throw new StaleOperationError(command);
        if (
          (command === 'start' || command === 'pause')
          && (state.sessionRevision !== revision || state.lifecycleRevision !== token.lifecycleRevision)
        ) throw new StaleOperationError(command);
        if (command === 'step') {
          const currentSequence = Number(state.telemetry.envelope?.seq ?? state.session?.sequence ?? 0);
          const responseSequence = Number(response?.seq ?? 0);
          if (state.sessionRevision !== revision || currentSequence > responseSequence) {
            throw new StaleOperationError(command);
          }
        }
        apply(response, sessionId);
        return snapshot();
      })
      .catch((error) => {
        if (pendingOperation?.token === token && state.session?.session_id === sessionId) {
          const normalized = error?.name === 'StaleOperationError'
            ? normalizeError(error)
            : recoverMutationAuthority(error);
          state = { ...state, error: normalized };
          publish();
        }
        throw error;
      })
      .finally(() => {
        if (pendingOperation?.token !== token) return;
        pendingOperation = null;
        state = { ...state, pending: null };
        publish();
      });
    pendingOperation = { command, promise, token };
    return promise;
  }

  function applyDescription(description, sessionId) {
    if (!description || description.session_id !== sessionId) return;
    const lifecycleChanged = description.state !== state.sessionState;
    state = {
      ...state,
      session: clone(description),
      sessionState: description.state,
      sessionRevision: state.sessionRevision + 1,
      lifecycleRevision: state.lifecycleRevision + (lifecycleChanged ? 1 : 0),
      error: null,
    };
    publish();
  }

  function replaceSession(command, { path, body }) {
    if (destroyed) return Promise.reject(new Error('Active Session Runtime is destroyed.'));
    if (state.authority.status !== 'known') return Promise.reject(new Error('Session Authority is unknown.'));
    // Reset is backend-legal from any lifecycle state; Create and Replay stay blocked while RUNNING.
    if (command !== 'reset' && state.sessionState === 'RUNNING') {
      return Promise.reject(new Error('Active Session is RUNNING.'));
    }
    if (pendingOperation) {
      return pendingOperation.command === command
        ? pendingOperation.promise
        : Promise.reject(new Error(`${pendingOperation.command} is already in progress.`));
    }
    const sessionId = state.session?.session_id || null;
    const revision = state.sessionRevision;
    const token = { command, sessionId, revision };
    state = { ...state, pending: token, error: null };
    publish();
    const promise = request({ method: 'POST', path, body, timeoutMs: 180_000 })
      .then((description) => {
        const currentId = state.session?.session_id || null;
        if (
          destroyed
          || pendingOperation?.token !== token
          || currentId !== sessionId
          || state.sessionRevision !== revision
        ) throw new StaleOperationError(command);
        if (!description?.session_id) throw new Error(`${command} returned no replacement session identity.`);
        adoptSession(description);
        return snapshot();
      })
      .catch((error) => {
        if (pendingOperation?.token === token && (state.session?.session_id || null) === sessionId) {
          const normalized = error?.name === 'StaleOperationError'
            ? normalizeError(error)
            : recoverMutationAuthority(error, { ambiguousReplacement: true });
          state = { ...state, error: normalized };
          publish();
          // A locally failed replacement keeps the old session, whose transport
          // was suspended for the swap. Reconnect it through the existing
          // backoff machinery without retrying the mutation itself; recovery
          // paths above already run their own authority refresh.
          if (!socket && !authorityPromise && canConnect()) {
            scheduleReconnect(sessionId, socketGeneration);
          }
        }
        throw error;
      })
      .finally(() => {
        if (pendingOperation?.token !== token) return;
        pendingOperation = null;
        state = { ...state, pending: null };
        publish();
      });
    pendingOperation = { command, promise, token };
    return promise;
  }

  return {
    bootstrap,
    refreshAuthority,
    create(runSpecification) {
      if (!runSpecification || typeof runSpecification !== 'object') {
        return Promise.reject(new TypeError('Run Specification is required.'));
      }
      return replaceSession('create', { path: '/api/sessions', body: clone(runSpecification) });
    },
    start() {
      const sessionId = state.session?.session_id;
      if (state.sessionState !== 'CREATED' && state.sessionState !== 'PAUSED' && state.sessionState !== 'RUNNING') {
        return Promise.reject(new Error('Start requires CREATED or PAUSED state.'));
      }
      return mutate('start', {
        path: `/api/sessions/${encodeURIComponent(sessionId || '')}/start`,
        duplicate: state.sessionState === 'RUNNING',
        apply: applyDescription,
      });
    },
    pause() {
      const sessionId = state.session?.session_id;
      return mutate('pause', {
        path: `/api/sessions/${encodeURIComponent(sessionId || '')}/pause`,
        duplicate: state.sessionState !== 'RUNNING',
        apply: applyDescription,
      });
    },
    step() {
      const sessionId = state.session?.session_id;
      if (state.sessionState !== 'CREATED' && state.sessionState !== 'PAUSED') {
        return Promise.reject(new Error('Step requires CREATED or PAUSED state.'));
      }
      return mutate('step', {
        path: `/api/sessions/${encodeURIComponent(sessionId || '')}/step`,
        apply: (envelope, expectedSessionId) => applyTelemetry(envelope, expectedSessionId),
      });
    },
    setSpeed(multiplier) {
      const sessionId = state.session?.session_id;
      const speed = Number(multiplier);
      if (!Number.isFinite(speed) || speed <= 0) return Promise.reject(new TypeError('Speed multiplier must be positive.'));
      return mutate('speed', {
        path: `/api/sessions/${encodeURIComponent(sessionId || '')}/speed?multiplier=${encodeURIComponent(speed)}`,
        apply: (playback) => {
          state = {
            ...state,
            session: { ...state.session, playback: clone(playback) },
            telemetry: state.telemetry.envelope
              ? { ...state.telemetry, envelope: { ...state.telemetry.envelope, playback: clone(playback) } }
              : state.telemetry,
          };
          publish();
        },
      });
    },
    reset() {
      const sessionId = state.session?.session_id;
      if (!sessionId) return Promise.reject(new Error('No Active Session for reset.'));
      return replaceSession('reset', { path: `/api/sessions/${encodeURIComponent(sessionId)}/reset` });
    },
    replay() {
      const sessionId = state.session?.session_id;
      if (!sessionId) return Promise.reject(new Error('No Active Session for replay.'));
      if (state.sessionState !== 'FINISHED') return Promise.reject(new Error('Replay requires FINISHED state.'));
      if (state.outcome.status !== 'ready' || !state.outcome.result) {
        return Promise.reject(new Error('Replay requires a ready FINISHED result.'));
      }
      return replaceSession('replay', { path: `/api/sessions/${encodeURIComponent(sessionId)}/replay` });
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      stopSocket();
      for (const controller of requestControllers) controller.abort();
      requestControllers.clear();
      unsubscribeVisibility?.();
      unsubscribeOnline?.();
      unsubscribeVisibility = null;
      unsubscribeOnline = null;
      pendingOperation = null;
      state = {
        ...state,
        authority: {
          status: 'unknown',
          error: { kind: 'destroyed', message: 'Active Session Runtime is destroyed.', status: null, detail: null },
        },
        connection: { status: 'disconnected', staleSince: state.connection.staleSince },
        pending: null,
      };
      publish();
      listeners.clear();
    },
    snapshot,
    subscribe(listener) {
      listeners.add(listener);
      try {
        listener(snapshot());
      } catch {
        /* isolated exactly like publish() */
      }
      return () => listeners.delete(listener);
    },
  };
}
