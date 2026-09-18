import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const app = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const html = await readFile(new URL('../../web_gui/index.html', import.meta.url), 'utf8');
const source = app.slice(app.indexOf('function syncPlaybackStatus('), app.indexOf('\nfunction formatCoordinate('));

test('actual speed is server measured and missing measurements clear the previous value', () => {
  const displayed = {};
  const rate = {};
  const context = vm.createContext({
    setText: (id, text) => { displayed[id] = text; },
    document: { querySelectorAll: () => [], getElementById: () => rate },
  });
  vm.runInContext(source, context);
  context.syncPlaybackStatus({ requested_multiplier: 5, effective_multiplier: 4.876 });
  assert.equal(displayed.speedStatus, 'Actual 4.88×');
  assert.equal(rate.value, '5');
  for (const value of [null, undefined, NaN, Infinity, -1, '5']) {
    context.syncPlaybackStatus({ requested_multiplier: 5, effective_multiplier: value });
    assert.equal(displayed.speedStatus, 'Actual —');
  }
  context.syncPlaybackStatus({ requested_multiplier: 5, effective_multiplier: 0 });
  assert.equal(displayed.speedStatus, 'Actual 0.00×');
  context.syncPlaybackStatus(null);
  assert.equal(displayed.speedStatus, 'Actual —');
});

test('actual speed is immediately after the rate selector and before cache delay', () => {
  assert.match(html, /id="livePlaybackRate"[\s\S]*?<\/obc-toggle-button-group>\s*<span[^>]*id="speedStatus"[^>]*>Actual —<\/span>\s*<span[^>]*id="telemetryDelay"/);
});
