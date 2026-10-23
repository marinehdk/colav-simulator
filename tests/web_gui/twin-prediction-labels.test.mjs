import test from 'node:test';
import assert from 'node:assert/strict';
import { buildTwinPresentation, layoutTwinWaypoints } from '../../web_gui/modules/twin-situation.js?v=20261019-p3-trk-v2';

const marker = (label, x = 0.6, y = 0.45) => ({ label, x, y, visible: true });
const markers = [60, 120, 180, 240, 300, 360, 400].map(t => marker(`+${t}s`));

function assertNoOverlap(layout, width, height, inset) {
  const boxes = [...layout.values()];
  for (const a of boxes) {
    assert.ok(a.left >= 8 && a.right <= width - 8 && a.top >= inset && a.bottom <= height - 8);
    for (const b of boxes) if (a !== b) {
      assert.ok(a.right + 8 <= b.left || b.right + 8 <= a.left || a.bottom + 8 <= b.top || b.bottom + 8 <= a.top,
        'label/icon bounds must not overlap');
    }
  }
}

test('compressed 400-second horizon keeps near and terminal labels without a tower', () => {
  const layout = layoutTwinWaypoints([], markers, 1600, 900, 80);
  assert.ok(layout.has('+60s'));
  assert.ok(layout.has('+400s'));
  assert.ok(layout.size >= 2 && layout.size <= 4);
  assert.ok([...layout.values()].every(p => p.lift <= 96 && Math.abs(p.offset) <= 72));
  assertNoOverlap(layout, 1600, 900, 80);
});

// 2026-10-23 初始航线航点照预测时间标注同模式抽稀:保起讫优先、上限 4;
// 航点与时间标注各自计数,互不挤占名额。
const wptSpread = count => Array.from({ length: count }, (_, i) => marker('WPT' + (i + 1), 0.08 + i * 0.06));

test('initial route waypoints thin to endpoints first then intermediates, capped at four', () => {
  const layout = layoutTwinWaypoints(wptSpread(14), [], 1600, 900, 80);
  assert.deepEqual([...layout.keys()], ['WPT1', 'WPT14', 'WPT2', 'WPT3']);
  assertNoOverlap(layout, 1600, 900, 80);
});

test('short routes keep every waypoint annotation', () => {
  assert.deepEqual([...layoutTwinWaypoints(wptSpread(2), [], 1600, 900, 80).keys()], ['WPT1', 'WPT2']);
  assert.deepEqual([...layoutTwinWaypoints(wptSpread(4), [], 1600, 900, 80).keys()], ['WPT1', 'WPT4', 'WPT2', 'WPT3']);
});

test('waypoint and prediction annotations stay capped independently', () => {
  // 分行排布:验证的是计数名额互不挤占,不是共线几何冲突下的放置。
  const timed = markers.map((p, i) => ({ ...p, x: 0.1 + i * 0.12, y: 0.2 }));
  const layout = layoutTwinWaypoints(wptSpread(10), timed, 1600, 900, 80);
  assert.ok([...layout.keys()].filter(key => key.startsWith('WPT')).length <= 4);
  assert.ok([...layout.keys()].filter(key => key.startsWith('+')).length <= 4);
  assert.ok(layout.has('WPT1') && layout.has('WPT10'));
  assert.ok(layout.has('+60s') && layout.has('+400s'));
  assertNoOverlap(layout, 1600, 900, 80);
});

test('open view shows at most four labels and prioritizes near, endpoint, then next near', () => {
  const spread = markers.map((p, i) => ({ ...p, x: 0.1 + i * 0.12 }));
  const layout = layoutTwinWaypoints([], spread, 1600, 900, 80);
  assert.deepEqual([...layout.keys()], ['+60s', '+400s', '+120s', '+180s']);
  assertNoOverlap(layout, 1600, 900, 80);
});

test('screen clipping, route waypoint collisions and camera changes cannot revive overlapping labels', () => {
  for (const [width, height, inset] of [[1600, 900, 80], [640, 360, 40], [320, 180, 24]]) {
    for (const y of [0.15, 0.45, 0.9]) {
      const points = markers.map(p => ({ ...p, y }));
      const layout = layoutTwinWaypoints([marker('WPT2', 0.6, y)], points, width, height, inset);
      assertNoOverlap(layout, width, height, inset);
      assert.ok([...layout.keys()].filter(key => key.startsWith('+')).length <= 4);
    }
  }
  const layout = layoutTwinWaypoints([], [marker('+60s', 0.5), marker('+400s', 0.5, 0.45),
    marker('+120s', -0.1), { ...marker('+180s'), visible: false }, marker('+240s', NaN)], 640, 360, 40);
  assert.deepEqual([...layout.keys()], ['+60s', '+400s']);
});

test('DT labels include actual terminal sample while the full prediction line stays intact', () => {
  const path = Array.from({ length: 81 }, (_, i) => [i * 12, i * 2]);
  const raw = { run_id: 'labels', seq: 1, sim_time: 10, plans: { prediction_horizon: path }, planner: { horizon_dt_s: 5 } };
  const chart = { getMissionRoute: () => [[], []], getLayerState: () => ({}) };
  const info = { run_id: 'labels', origin_e: 0, origin_n: 0 };
  const value = buildTwinPresentation({ raw }, chart, info);
  assert.equal(value.time_markers.at(-1).label, '+400s');
  assert.deepEqual(value.lines.find(line => line.id === 'prediction').points,
    path.map(([north, east]) => ({ east, north, label: '' })));
  assert.deepEqual(raw.plans.prediction_horizon, path);
  raw.plans.prediction_render = { style: 'ACTIVE', ownship: { time_s: path.map((_, i) => 37 + i * 4.5) } };
  assert.equal(buildTwinPresentation({ raw }, chart, info).time_markers.at(-1).label, '+360s');
  raw.plans.prediction_render.style = 'STALE';
  assert.deepEqual(buildTwinPresentation({ raw }, chart, info).time_markers, []);
  delete raw.plans.prediction_render;
  delete raw.planner.horizon_dt_s;
  assert.deepEqual(buildTwinPresentation({ raw }, chart, info).time_markers, []);
});
