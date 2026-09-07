import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const source = await readFile(new URL('../../web_gui/app.js', import.meta.url), 'utf8');
const start = source.indexOf('function eventDisplayContent(event)');
const end = source.indexOf('const MONITOR_HIDDEN_EVENT_TYPES', start);
assert.ok(start >= 0 && end > start);
const format = vm.runInNewContext(`${source.slice(start, end)}; eventDisplayContent`);

for (const [state, display, status, tone] of [
  ['ACTIVE/COMMITTED/NONE', 'LOW', 'MONITOR', 'warning'],
  ['ACTIVE/COMMITTED/NONE', 'HIGH', 'AVOIDING', 'danger'],
  ['PAST_CLEAR/COMMITTED/NONE', 'CLEAR', 'CLEARING', 'safe'],
  ['RELEASED/ACHIEVED/NONE', 'CLEAR', 'RELEASED', 'safe'],
]) {
  test(`event state ${state}/${display} agrees with the threat card`, () => {
    const output = format({type: 'target_transition', details: {to_state: state, display_class: display, target_id: 1}});
    assert.equal(output.status, status);
    assert.equal(output.cardTone, tone);
  });
}
