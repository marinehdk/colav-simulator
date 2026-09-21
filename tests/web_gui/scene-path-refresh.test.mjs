import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// Exercise the renderer's actual line boundary with the bundled Cesium engine.
// DOM types are only needed for Cesium's material type checks; no WebGL is used.
const sandbox = {
  console, setTimeout, clearTimeout, atob, btoa, TextDecoder, TextEncoder, URL,
  TransformStream, ReadableStream, WritableStream, AbortController,
  HTMLCanvasElement: class {}, HTMLVideoElement: class {}, HTMLImageElement: class {},
  ImageBitmap: class {}, OffscreenCanvas: class {},
};
sandbox.global = sandbox;
vm.createContext(sandbox);
vm.runInContext(readFileSync(new URL('../../web_gui/vendor/cesium/Cesium.js', import.meta.url), 'utf8'), sandbox);
const C = sandbox.Cesium;
const source = readFileSync(new URL('../../web_gui/modules/scene-3d.js', import.meta.url), 'utf8');
const lineSource = source.slice(source.indexOf('  function line('), source.indexOf('  // A sampled UTM mesh'));

function harness() {
  const viewer = { entities: new C.EntityCollection() };
  const geometry = new Map(), linePoints = new Map();
  const position = (n, e, h) => C.Cartesian3.fromDegrees(6 + e / 100000, 62 + n / 100000, h);
  const line = new Function('C', 'viewer', 'geometry', 'linePoints', 'position', `${lineSource}\nreturn line;`)(C, viewer, geometry, linePoints, position);
  const scene = {
    frameState: { context: { depthTexture: true } }, ellipsoid: C.Ellipsoid.WGS84,
    primitives: new C.PrimitiveCollection(), groundPrimitives: new C.PrimitiveCollection(),
  };
  return { viewer, geometry, linePoints, position, line, scene };
}

test('successive predictions reach rendered Cesium polyline on each update without waiting for static geometry rebuilds', () => {
  const h = harness();
  h.line('prediction', [[0, 0], [100, 100]], '#e99819', 3);
  const entity = h.geometry.get('prediction');
  const updater = new C.PolylineGeometryUpdater(entity, h.scene);
  assert.equal(updater.isDynamic, true, 'streamed predictions must not enter Cesium asynchronous static geometry batches');
  const dynamic = updater.createDynamicUpdater(h.scene.primitives, h.scene.groundPrimitives);
  const time = C.JulianDate.now();
  for (let frame = 1; frame <= 120; frame++) {
    const points = [[frame, frame], [100 + frame, 100 - frame], [200, frame * 2]];
    h.line('prediction', points, '#e99819', 3);
    dynamic.update(time);
    assert.equal(h.geometry.get('prediction'), entity);
    assert.equal(h.scene.primitives.length, 1);
    const rendered = h.scene.primitives.get(0).get(0).positions;
    assert.equal(rendered.length, points.length);
    points.forEach((p, i) => assert.ok(C.Cartesian3.equals(rendered[i], h.position(...p, 0.8))));
  }
  dynamic.destroy(); updater.destroy();
});

test('missing or invalid replacement predictions remove the previous line and cached points', () => {
  for (const invalid of [[], [[NaN, 0], [0, NaN]], [[0, 0], [NaN, NaN]]]) {
    const h = harness();
    h.line('prediction', [[0, 0], [100, 100]], '#e99819');
    h.line('prediction', invalid, '#e99819');
    assert.equal(h.viewer.entities.values.length, 0);
    assert.equal(h.geometry.has('prediction'), false);
    assert.equal(h.linePoints.has('prediction'), false);
    h.line('prediction', [[1, 2], [3, 4]], '#e99819');
    assert.equal(h.viewer.entities.values.length, 1);
  }
});
