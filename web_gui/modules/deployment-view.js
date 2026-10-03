import { targetsForDisplay } from './situation-display.js?v=20261004-token-cleanup-v1';
import { geographyProblem, frameIdentity, targetKey } from './scene-geography.js?v=20261004-token-cleanup-v1';

// One display boundary. No session control, network telemetry or physics clock lives here.
// P2-S4: three display states — '2d' chart, '3d' Cesium scene, 'twin' live pixel-stream
// viewport (createTwin factory, mirror of the createScene seam). The twin state owns no
// clock and no telemetry: Unity pulls the live compact-v1 stream itself (contract §2) and
// the sidebar keeps running on the existing live data path.
export function createDeploymentView({ chart, createScene, createTwin = null, onState = () => {}, onError = () => {}, now = () => performance.now() }) {
  let mode = '2d', scene = null, twinViewer = null, projection = null, runId = null, generation = 0;
  let identities = new Map();
  const modelOverrides = new Map();
  let lastEntryMs = null, loadingController = null;
  let loading = false, savedView = null, camera = 'chase', destroyed = false;
  function reason() {
    if (!projection?.raw?.os || ![projection.raw.os.x, projection.raw.os.y, projection.raw.os.psi].every(Number.isFinite)) return '等待有效本船状态';
    return geographyProblem(chart.getEncInfo(), runId);
  }
  function state() { return { mode, loading, camera, lastEntryMs, unavailable: reason(), orientation: chart.getOrientation(), frame: projection ? frameIdentity(projection.raw) : null }; }
  function notify() { onState(state()); }
  function exit(orientation) {
    generation += 1;
    loading = false;
    loadingController?.abort(); loadingController = null;
    scene?.destroy(); scene = null;
    twinViewer?.destroy(); twinViewer = null;
    mode = '2d';
    if (savedView) chart.restoreView(savedView);
    savedView = null;
    if (orientation) chart.setOrientation(orientation);
    if (projection) chart.renderFrame(projection.raw);
    notify();
  }
  async function enter() {
    if (destroyed || loading || mode === '3d' || reason()) return;
    camera = 'chase';
    const token = ++generation;
    const started = now();
    loadingController = new AbortController();
    loading = true; notify();
    try {
      const next = await createScene({ info: chart.getEncInfo(), camera, modelOverrides, signal: loadingController.signal,
        onFailure: error => { if (token === generation) { exit(); onError(error); } },
        onCamera: value => { camera = value; notify(); },
      });
      if (destroyed || token !== generation) { next.destroy(); return; }
      savedView = chart.captureView();
      scene = next; mode = '3d'; loading = false; lastEntryMs = now() - started;
      notify();
      scene.render(projection);
    } catch (error) {
      if (token !== generation || destroyed) return;
      exit(); onError(error);
    }
  }
  // Twin entry mirrors the 3D factory seam: an async factory returns a viewer with
  // destroy(); the view only forwards projections and guards generations. Any twin
  // error exits back to the chart through the same path as a failed 3D entry.
  async function enterTwin() {
    if (destroyed || loading || mode !== '2d' || !createTwin || reason()) return;
    const token = ++generation;
    const started = now();
    loadingController = new AbortController();
    loading = true; notify();
    try {
      const next = await createTwin({ info: chart.getEncInfo(), signal: loadingController.signal,
        onFailure: error => { if (token === generation) { exit(); onError(error); } },
      });
      if (destroyed || token !== generation) { next.destroy(); return; }
      savedView = chart.captureView();
      twinViewer = next; mode = 'twin'; loading = false; lastEntryMs = now() - started;
      notify();
      twinViewer.render(projection);
    } catch (error) {
      if (token !== generation || destroyed) return;
      exit(); onError(error);
    }
  }
  return {
    state,
    refresh: notify,
    beginSession(id) {
      exit(); projection = null; identities.clear(); modelOverrides.clear(); runId = id; camera = 'chase'; notify();
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
      const keys = new Set(targetsForDisplay(value.raw).map(target => targetKey(runId, target)));
      for (const key of modelOverrides.keys()) if (!keys.has(key)) modelOverrides.delete(key);
      projection = value;
      chart.renderFrame(value.raw, mode === '2d');
      scene?.render(value); twinViewer?.render(value); notify();
    },
    toggle() { if (mode !== '2d' || loading) exit(); else return enter(); },
    toggleTwin() { if (mode !== '2d' || loading) exit(); else return enterTwin(); },
    orientation(value) { exit(value); },
    recenter() { if (mode === 'twin') twinViewer?.recenter?.(); else if (mode === '3d') scene.recenter(); else chart.recenterOwnship(); },
    zoom(direction) { if (mode === 'twin') twinViewer?.zoom?.(direction); else if (mode === '3d') scene.zoom(direction); else chart[direction > 0 ? 'zoomIn' : 'zoomOut'](); },
    select(id) { chart.selectTarget(id); scene?.select(id); },
    layers() { scene?.render(projection); },
    destroy() { exit(); destroyed = true; projection = null; },
  };
}
