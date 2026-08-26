function setText(documentRef, id, value, fallback = '—') {
  const node = documentRef.getElementById(id);
  if (node) node.textContent = value === undefined || value === null || value === '' ? fallback : String(value);
}

function formatNumber(value) {
  return typeof value === 'number' ? value.toLocaleString('en-US') : null;
}

function formatBbox(value) {
  return Array.isArray(value) && value.length === 4 ? `${value[0]}, ${value[1]} → ${value[2]}, ${value[3]}` : null;
}

function formatList(value) {
  return Array.isArray(value) && value.length ? value.join(', ') : null;
}

function createModeChoice(documentRef, mode, selectedMode) {
  const button = documentRef.createElement('button');
  button.type = 'button';
  button.className = 'historical-ais-mode-choice';
  button.dataset.historicalMode = mode.id;
  button.setAttribute('aria-pressed', String(mode.id === selectedMode));
  button.classList.toggle('active', mode.id === selectedMode);
  const title = documentRef.createElement('strong');
  title.textContent = mode.label;
  const description = documentRef.createElement('small');
  description.textContent = mode.description;
  button.append(title, description);
  return button;
}

function renderWorkflow(documentRef, state) {
  const workflow = state.workflow;
  const available = workflow.status === 'AVAILABLE';
  const presentation = available ? workflow.presentation : null;
  const threat = presentation?.threat;
  const leakage = presentation?.leakage;
  const determinism = presentation?.determinism;
  const compare = presentation?.compare;
  const runtime = presentation?.runtime;
  const qualification = presentation?.qualification;
  const replay = presentation?.evidence?.replay;
  const workflowDigests = presentation?.evidence?.digests;

  setText(documentRef, 'historicalAISWorkflowAuthority', available && workflow.workflowId ? `Historical workflow · ${workflow.workflowId}` : null);
  setText(documentRef, 'historicalAISWorkflowStatus', available ? workflow.lifecycle : workflow.error?.code);
  const stages = available ? workflow.stages : null;
  for (const stage of ['dataset', 'case', 'replay', 'counterfactual', 'evaluation', 'compare']) {
    setText(documentRef, `historicalAISStage-${stage}`, stages?.[stage]);
  }
  setText(documentRef, 'historicalAISEvidenceFallback', runtime?.fallback_used);
  setText(documentRef, 'historicalAISEvidenceThreat', threat
    && threat.vector_count !== null && threat.schedule_entry_count !== null && threat.cluster_count !== null
    ? `${threat.vector_count}/${threat.schedule_entry_count}/${threat.cluster_count}`
    : null);
  setText(documentRef, 'historicalAISEvidenceLeakage', leakage?.status);
  setText(documentRef, 'historicalAISEvidenceDeterminism', determinism?.status
    ? `${determinism.status}${determinism.mismatch_count === null ? '' : ` · ${determinism.mismatch_count} mismatches`}`
    : null);
  setText(documentRef, 'historicalAISEvidenceVerdict', compare?.overall_assurance_verdict);
  setText(documentRef, 'historicalAISRuntimeQualification', qualification
    ? `${qualification.execution_mode ?? '—'} · ${qualification.status ?? '—'}`
    : null);
  setText(documentRef, 'historicalAISQualificationDeterminism', qualification?.determinism?.status);
  setText(documentRef, 'historicalAISQualificationThreatGraph', qualification?.threat_graph
    ? `${qualification.threat_graph.vector_count}/${qualification.threat_graph.schedule_entry_count}/${qualification.threat_graph.cluster_count}`
    : null);
  const domains = compare?.domain_statuses;
  for (const domain of ['safety', 'colreg', 'maneuver', 'efficiency', 'human_similarity']) {
    setText(documentRef, `historicalAISCompare-${domain}`, domains?.[domain]);
  }
  setText(documentRef, 'historicalAISReplayStatus', replay?.status);
  setText(documentRef, 'historicalAISReplayMode', replay?.mode);
  setText(documentRef, 'historicalAISReplayFactory', replay?.factory);
  setText(documentRef, 'historicalAISReplayDataset', replay?.dataset_digest);
  setText(documentRef, 'historicalAISReplayActorSet', replay?.runtime_actor_set_digest);
  setText(documentRef, 'historicalAISReplayTrajectory', replay?.trajectory_digest);
  setText(documentRef, 'historicalAISReplayManifest', replay?.manifest_digest);
  setText(documentRef, 'historicalAISReplayDimensionRegistry', replay?.dimension_registry_digest);
  setText(documentRef, 'historicalAISReplayDimensionSource', replay?.dimension_source_digest);
  setText(documentRef, 'historicalAISWorkflowDigestArchive', workflowDigests?.archive_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestEntry', workflowDigests?.entry_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestSchema', workflowDigests?.schema_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestSelection', workflowDigests?.selection_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestNormalized', workflowDigests?.normalized_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestDescriptor', workflowDigests?.descriptor_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestEncProfile', workflowDigests?.enc_profile_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestEncCache', workflowDigests?.enc_cache_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestEncSource', workflowDigests?.enc_source_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestDimensionRegistry', workflowDigests?.dimension_registry_sha256);
  setText(documentRef, 'historicalAISWorkflowDigestDimensionSource', workflowDigests?.dimension_source_sha256);
}

function renderBenchmark(documentRef, state) {
  const scenario = state.scenario;
  setText(documentRef, 'historicalAISBenchmarkScenario', scenario?.title);
  setText(documentRef, 'historicalAISBenchmarkWindow', scenario?.identity);
  setText(documentRef, 'historicalAISBenchmarkSource', scenario ? `${scenario.operability.status} · ${scenario.operability.scope}` : state.detail.status);
  setText(documentRef, 'historicalAISBenchmarkLimitation', scenario?.limitations.join(' · '));
  setText(documentRef, 'historicalAISSceneOperability', scenario ? `${scenario.operability.status} · ${scenario.operability.scope}` : null);
  setText(documentRef, 'historicalAISPredictiveQualification', scenario
    ? [scenario.qualification.status, scenario.qualification.code].filter(Boolean).join(' · ')
    : null);
  setText(documentRef, 'historicalAISFutureGate', scenario?.qualification.future_gate);
  const modes = documentRef.getElementById('historicalAISModeChoices');
  if (modes) modes.replaceChildren(...(scenario?.modes || []).map(mode => createModeChoice(documentRef, mode, state.selectedMode)));
  setText(documentRef, 'historicalAISModeDescription', scenario?.modes.find(mode => mode.id === state.selectedMode)?.description);
  const run = documentRef.getElementById('historicalAISRun');
  if (run) {
    run.disabled = !scenario?.readiness.canRun || state.busy;
    run.textContent = state.busy ? 'RUNNING' : 'Run Historical Workflow';
    run.title = scenario?.readiness.canRun ? '' : 'Canonical source readiness is not READY';
  }
  const deploy = documentRef.getElementById('historicalAISDeploy');
  if (deploy) {
    deploy.disabled = !scenario?.readiness.canRun || state.busy || state.deploying;
    deploy.textContent = state.deploying ? 'CREATING' : 'Open in Deployment';
    deploy.title = scenario?.readiness.canRun ? '' : 'Canonical source readiness is not READY';
  }
  setText(documentRef, 'historicalAISDeployStatus', state.deployError
    ? `Deploy failed · ${state.deployError.code}: ${state.deployError.message}`
    : 'Interactive Counterfactual session on the AIS scene — the bound algorithm takes over ownship at T0. Full tuple choice lives in Config.');
  renderWorkflow(documentRef, state);
}

export function renderHistoricalAISWorkbench(documentRef, state) {
  renderBenchmark(documentRef, state);
  const catalogStatus = documentRef.getElementById('historicalAISCatalogStatus');
  if (catalogStatus) {
    catalogStatus.textContent = state.catalog.error
      ? `${state.catalog.error.code}: ${state.catalog.error.message}`
      : state.catalog.status;
    catalogStatus.dataset.state = state.catalog.status === 'READY' ? 'ready' : state.catalog.status === 'ERROR' ? 'error' : 'info';
  }

}
