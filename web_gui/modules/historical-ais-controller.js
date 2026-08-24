import {
  projectHistoricalAISScenario,
  projectHistoricalAISWorkflow,
  unavailableHistoricalWorkflow,
} from './historical-ais-projection.js?v=20260824-canonical-presentation';

function typedError(error, fallbackCode) {
  return {
    code: error?.code || fallbackCode,
    message: error?.message || String(error || fallbackCode),
  };
}
function initialState() {
  return {
    catalog: { status: 'LOADING', error: null },
    detail: { status: 'UNAVAILABLE', error: null },
    scenarios: [],
    scenario: null,
    selectedId: null,
    selectedMode: null,
    workflow: unavailableHistoricalWorkflow(),
    busy: false,
  };
}

/** Network-independent Historical AIS state authority. */
export function createHistoricalAISController({ api, render }) {
  const state = initialState();

  function publish() {
    render(state);
  }

  async function selectScenario(scenarioId) {
    state.selectedId = scenarioId;
    state.selectedMode = null;
    state.scenario = null;
    state.detail = { status: 'LOADING', error: null };
    state.workflow = unavailableHistoricalWorkflow();
    publish();
    try {
      const projected = projectHistoricalAISScenario(await api.getScenario(scenarioId));
      if (projected.status !== 'AVAILABLE') {
        state.detail = { status: 'ERROR', error: projected.error };
        publish();
        return;
      }
      state.scenario = projected;
      state.selectedMode = projected.modes[0]?.id ?? null;
      state.detail = { status: 'READY', error: null };
    } catch (error) {
      state.scenario = null;
      state.detail = { status: 'ERROR', error: typedError(error, 'DETAIL_UNAVAILABLE') };
    }
    publish();
  }

  async function load() {
    state.catalog = { status: 'LOADING', error: null };
    state.scenarios = [];
    state.scenario = null;
    publish();
    try {
      const documents = await api.listScenarios();
      const projected = documents.map(projectHistoricalAISScenario);
      const invalid = projected.find(item => item.status !== 'AVAILABLE');
      if (invalid) throw Object.assign(new Error(invalid.error.message), invalid.error);
      if (!projected.length) throw Object.assign(new Error('No Historical AIS scenarios published'), { code: 'CATALOG_EMPTY' });
      state.scenarios = projected;
      state.catalog = { status: 'READY', error: null };
      publish();
      await selectScenario(projected[0].scenarioId);
    } catch (error) {
      state.catalog = { status: 'ERROR', error: typedError(error, 'CATALOG_UNAVAILABLE') };
      state.detail = { status: 'UNAVAILABLE', error: null };
      state.scenarios = [];
      state.scenario = null;
      state.selectedId = null;
      state.selectedMode = null;
      publish();
    }
  }

  function selectMode(mode) {
    if (!state.scenario?.modes.some(item => item.id === mode)) return;
    state.selectedMode = mode;
    publish();
  }

  async function runWorkflow() {
    if (state.detail.status !== 'READY' || !state.scenario?.readiness.canRun || !state.selectedMode) return;
    state.busy = true;
    publish();
    try {
      let document = await api.createWorkflow(state.scenario.scenarioId, state.selectedMode);
      state.workflow = projectHistoricalAISWorkflow(document);
      publish();
      if (document?.workflow_id) {
        document = await api.runWorkflow(document.workflow_id);
        state.workflow = projectHistoricalAISWorkflow(document);
      }
    } catch (error) {
      state.workflow = unavailableHistoricalWorkflow(error?.code || 'WORKFLOW_ERROR', error?.message || String(error));
    } finally {
      state.busy = false;
      publish();
    }
  }

  return { state, load, selectScenario, selectMode, runWorkflow, publish };
}
