import { createActiveSessionRuntime } from './active-session-runtime.js?v=20260818-candidate2-runtime-final';

class SessionHttpError extends Error {
  constructor(response, detail) {
    const message = typeof detail === 'object'
      ? `${detail.status || 'ERROR'}: ${detail.reason || JSON.stringify(detail)}`
      : detail || `HTTP ${response.status}`;
    super(message);
    this.name = 'SessionHttpError';
    this.status = response.status;
    this.detail = detail;
  }
}

const http = {
  async request({ method, path, body, signal }) {
    const options = { method, signal };
    if (body !== undefined) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    if (path === '/api/sessions/current' && response.status === 404) return null;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new SessionHttpError(response, payload.detail ?? payload);
    return payload;
  },
};

const visibility = {
  isVisible: () => document.visibilityState === 'visible',
  hasFocus: () => document.hasFocus(),
  subscribe(listener) {
    document.addEventListener('visibilitychange', listener);
    window.addEventListener('focus', listener);
    window.addEventListener('blur', listener);
    return () => {
      document.removeEventListener('visibilitychange', listener);
      window.removeEventListener('focus', listener);
      window.removeEventListener('blur', listener);
    };
  },
};

const online = {
  isOnline: () => navigator.onLine !== false,
  subscribe(listener) {
    window.addEventListener('online', listener);
    window.addEventListener('offline', listener);
    return () => {
      window.removeEventListener('online', listener);
      window.removeEventListener('offline', listener);
    };
  },
};

export const activeSessionRuntime = createActiveSessionRuntime({
  http,
  wsFactory(path) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return new WebSocket(`${protocol}//${location.host}${path}`);
  },
  scheduler: {
    setTimeout: (callback, delay) => window.setTimeout(callback, delay),
    clearTimeout: (id) => window.clearTimeout(id),
  },
  clock: { now: () => Date.now() },
  visibility,
  online,
});
