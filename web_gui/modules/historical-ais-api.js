export class HistoricalAISApiError extends Error {
  constructor(code, message, status = null) {
    super(message);
    this.name = 'HistoricalAISApiError';
    this.code = code;
    this.status = status;
  }
}
async function responseJson(fetchImpl, url, options = {}) {
  if (typeof fetchImpl !== 'function') {
    throw new HistoricalAISApiError('API_UNAVAILABLE', 'Historical AIS API unavailable');
  }
  const response = await fetchImpl(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail;
    const code = typeof detail === 'object' && detail?.status ? detail.status : `HTTP_${response.status}`;
    const message = typeof detail === 'string' ? detail : detail?.reason;
    throw new HistoricalAISApiError(code, message || `Historical AIS API ${response.status}`, response.status);
  }
  return body;
}

export function createHistoricalAISApi({ fetchImpl = globalThis.fetch } = {}) {
  return {
    async listScenarios() {
      const body = await responseJson(fetchImpl, '/api/historical/scenarios');
      return Array.isArray(body) ? body : [];
    },
    async getScenario(scenarioId) {
      return responseJson(fetchImpl, `/api/historical/scenarios/${encodeURIComponent(scenarioId)}`);
    },
    async createWorkflow(scenarioId, mode) {
      return responseJson(fetchImpl, `/api/historical/scenarios/${encodeURIComponent(scenarioId)}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
    },
    async runWorkflow(workflowId) {
      return responseJson(fetchImpl, `/api/historical/workflows/${encodeURIComponent(workflowId)}/run`, {
        method: 'POST',
      });
    },
    async getWorkflow(workflowId) {
      return responseJson(fetchImpl, `/api/historical/workflows/${encodeURIComponent(workflowId)}`);
    },
    async createActiveSession({ validationRuleId, scenarioId, algorithmId, trackerId }) {
      return responseJson(fetchImpl, '/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          validation_rule_id: validationRuleId,
          scenario_id: scenarioId,
          algorithm_id: algorithmId,
          tracker_id: trackerId,
        }),
      });
    },
  };
}
