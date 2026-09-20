import { targetsForDisplay } from './situation-display.js?v=20260920-3d-v1';
import { geographyProblem, frameIdentity } from './scene-geography.js';

// One display boundary. No session control, network telemetry or physics clock lives here.
export function createDeploymentView({ chart, createScene, onState = () => {}, onError = () => {} }) {
  let mode = '2d', scene = null, projection = null, runId = null, generation = 0;
  let identities = new Map();
  let loading = false, savedView = null, camera = 'bridge', destroyed = false;
  function reason() {
    if (!projection?.raw?.os || ![projection.raw.os.x, projection.raw.os.y, projection.raw.os.psi].every(Number.isFinite)) return '等待有效本船状态';
    return geographyProblem(chart.getEncInfo(), runId);
  }
  function state() { return { mode, loading, camera, unavailable: reason(), orientation: chart.getOrientation(), frame: projection ? frameIdentity(projection.raw) : null }; }
  function notify() { onState(state()); }
  function exit(orientation) {
    generation += 1;
    loading = false;
    scene?.destroy(); scene = null;
    mode = '2d';
    if (savedView) chart.restoreView(savedView);
    savedView = null;
    if (orientation) chart.setOrientation(orientation);
    if (projection) chart.renderFrame(projection.raw);
    notify();
  }
  async function enter() {
    if (destroyed || loading || mode === '3d' || reason()) return;
    const token = ++generation;
    loading = true; notify();
    try {
      const next = await createScene({ info: chart.getEncInfo(), camera,
        onFailure: error => { if (token === generation) { exit(); onError(error); } },
        onCamera: value => { camera = value; notify(); },
      });
      if (destroyed || token !== generation) { next.destroy(); return; }
      savedView = chart.captureView();
      scene = next; mode = '3d'; loading = false;
      notify();
      scene.render(projection);
    } catch (error) {
      if (token !== generation || destroyed) return;
      exit(); onError(error);
    }
  }
  return {
    state,
    refresh: notify,
    beginSession(id) {
      exit(); projection = null; identities.clear(); runId = id; camera = 'bridge'; notify();
    },
    render(value) {
      if (destroyed || !value?.raw || value.raw.run_id !== runId) return;
      const selected = chart.getSelectedTargetId?.();
      const next = new Map(targetsForDisplay(value.raw).map(target => [String(target.id), target.generation ?? null]));
      if (selected != null && identities.has(String(selected))
        && (!next.has(String(selected)) || next.get(String(selected)) !== identities.get(String(selected)))) {
        chart.selectTarget(null); scene?.select(null);
      }
      identities = next;
      projection = value;
      chart.renderFrame(value.raw, mode === '2d');
      scene?.render(value); notify();
    },
    toggle() { if (mode === '3d' || loading) exit(); else return enter(); },
    orientation(value) { exit(value); },
    recenter() { if (mode === '3d') scene.recenter(); else chart.recenterOwnship(); },
    zoom(direction) { if (mode === '3d') scene.zoom(direction); else chart[direction > 0 ? 'zoomIn' : 'zoomOut'](); },
    select(id) { chart.selectTarget(id); scene?.select(id); },
    layers() { scene?.render(projection); },
    destroy() { exit(); destroyed = true; projection = null; },
  };
}
