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

function renderScenarioList(documentRef, state) {
  const list = documentRef.getElementById('historicalAISScenarioList');
  if (!list) return;
  list.replaceChildren(...state.scenarios.map(scenario => {
    const button = documentRef.createElement('button');
    button.type = 'button';
    button.className = 'historical-ais-scenario-choice';
    button.dataset.historicalScenarioId = scenario.scenarioId;
    button.setAttribute('aria-pressed', String(scenario.scenarioId === state.selectedId));
    const title = documentRef.createElement('strong');
    title.textContent = scenario.title;
    const meta = documentRef.createElement('small');
    meta.textContent = [
      scenario.identity,
      scenario.selection?.runtimeActorCount === null ? null : `${scenario.selection.runtimeActorCount} runtime actors`,
      scenario.enc?.profileId,
    ].filter(Boolean).join(' · ');
    button.append(title, meta);
    return button;
  }));
}

function clearScenario(documentRef, state) {
  const error = state.detail.error || state.catalog.error;
  setText(documentRef, 'historicalAISScenarioName', error ? 'SCENARIO ERROR' : 'SCENARIO UNAVAILABLE');
  setText(documentRef, 'historicalAISScenarioDescription', error ? `${error.code}: ${error.message}` : null);
  setText(documentRef, 'historicalAISScenarioSourceStatus', state.detail.status);
  setText(documentRef, 'historicalAISScenarioHeaderStatus', state.detail.status);
  for (const id of [
    'historicalAISScenarioIdentity', 'historicalAISScenarioWindow', 'historicalAISScenarioDuration',
    'historicalAISSceneOperability', 'historicalAISPredictiveQualification', 'historicalAISFutureGate',
    'historicalAISScenarioActors', 'historicalAISScenarioSource', 'historicalAISScenarioArchive',
    'historicalAISScenarioEntry', 'historicalAISScenarioFilter', 'historicalAISScenarioBbox',
    'historicalAISScenarioReference', 'historicalAISScenarioT0', 'historicalAISScenarioTargets',
    'historicalAISScenarioEnc', 'historicalAISScenarioRows', 'historicalAISScenarioQuality',
    'historicalAISScenarioQualificationThreat', 'historicalAISScenarioCapability',
    'historicalAISDigestArchive', 'historicalAISDigestEntry', 'historicalAISDigestSchema',
    'historicalAISDigestSelection', 'historicalAISDigestNormalized', 'historicalAISDigestDescriptor',
    'historicalAISDigestEncProfile', 'historicalAISDigestEncCache', 'historicalAISDigestEncSource',
    'historicalAISDigestDimensionRegistry', 'historicalAISDigestDimensionSource',
    'historicalAISScenarioLimitation',
  ]) setText(documentRef, id, null);
  const preview = documentRef.getElementById('historicalAISScenePreview');
  if (preview) preview.hidden = true;
}

function renderScenarioDetail(documentRef, state) {
  const scenario = state.scenario;
  if (!scenario) {
    clearScenario(documentRef, state);
    return;
  }
  const selection = scenario.selection;
  setText(documentRef, 'historicalAISScenarioName', scenario.title);
  setText(documentRef, 'historicalAISScenarioDescription', scenario.description);
  setText(documentRef, 'historicalAISScenarioSourceStatus', scenario.readiness.status);
  setText(documentRef, 'historicalAISScenarioHeaderStatus', `${scenario.operability.status} · ${scenario.operability.scope}`);
  setText(documentRef, 'historicalAISScenarioIdentity', scenario.identity);
  setText(documentRef, 'historicalAISSceneOperability', `${scenario.operability.status} · ${scenario.operability.scope}`);
  setText(documentRef, 'historicalAISPredictiveQualification', [scenario.qualification.status, scenario.qualification.code].filter(Boolean).join(' · '));
  setText(documentRef, 'historicalAISFutureGate', scenario.qualification.future_gate);
  setText(documentRef, 'historicalAISScenarioWindow', selection.startUtc && selection.endUtc ? `${selection.startUtc} → ${selection.endUtc}` : null);
  setText(documentRef, 'historicalAISScenarioDuration', selection.durationLabel);
  setText(documentRef, 'historicalAISScenarioActors', selection.runtimeActorCount === null ? null : `${selection.runtimeActorCount} runtime actors`);
  setText(documentRef, 'historicalAISScenarioSource', scenario.source.archiveName);
  const archiveFacts = [
    scenario.source.archiveDays === null ? null : `${scenario.source.archiveDays} days`,
    formatNumber(scenario.source.archiveRows) ? `${formatNumber(scenario.source.archiveRows)} rows` : null,
    formatNumber(scenario.source.archiveMmsi) ? `${formatNumber(scenario.source.archiveMmsi)} MMSI` : null,
  ].filter(Boolean);
  setText(documentRef, 'historicalAISScenarioArchive', archiveFacts.length ? archiveFacts.join(' · ') : null);
  setText(documentRef, 'historicalAISScenarioEntry', selection.entryName);
  setText(documentRef, 'historicalAISScenarioFilter', Array.isArray(selection.filterMmsi) ? `${selection.filterMmsi.length} MMSI filter` : null);
  setText(documentRef, 'historicalAISScenarioBbox', formatBbox(selection.bbox));
  setText(documentRef, 'historicalAISScenarioReference', selection.referenceMmsi);
  setText(documentRef, 'historicalAISScenarioT0', selection.t0Utc);
  setText(documentRef, 'historicalAISScenarioTargets', formatList(selection.targetMmsi));
  setText(documentRef, 'historicalAISScenarioEnc', [scenario.enc.profileId, scenario.enc.qualification].filter(Boolean).join(' · '));
  setText(documentRef, 'historicalAISScenarioRows', selection.sourceRows === null || selection.normalizedRows === null ? null : `${selection.sourceRows} source / ${selection.normalizedRows} normalized`);
  setText(documentRef, 'historicalAISScenarioQuality', selection.qualityFindings === null ? null : `${selection.qualityFindings} quality findings`);
  setText(documentRef, 'historicalAISScenarioCapability', scenario.algorithmCapability
    ? `${scenario.algorithmCapability.bindingRole === 'ALGORITHM_CAPABILITY_ONLY' && scenario.algorithmCapability.geometryEquivalence === false ? 'algorithm-only/not geometry' : '—'} · ${formatList(scenario.algorithmCapability.exactTuple) || '—'}`
    : null);
  setText(documentRef, 'historicalAISDigestArchive', scenario.digests.archive);
  setText(documentRef, 'historicalAISDigestEntry', scenario.digests.entry);
  setText(documentRef, 'historicalAISDigestSchema', scenario.digests.schema);
  setText(documentRef, 'historicalAISDigestSelection', scenario.digests.selection);
  setText(documentRef, 'historicalAISDigestNormalized', scenario.digests.normalized);
  setText(documentRef, 'historicalAISDigestDescriptor', scenario.digests.descriptor);
  setText(documentRef, 'historicalAISDigestEncProfile', scenario.digests.encProfile);
  setText(documentRef, 'historicalAISDigestEncCache', scenario.digests.encCache);
  setText(documentRef, 'historicalAISDigestEncSource', scenario.digests.encSource);
  setText(documentRef, 'historicalAISDigestDimensionRegistry', scenario.digests.dimensionRegistry);
  setText(documentRef, 'historicalAISDigestDimensionSource', scenario.digests.dimensionSource);
  setText(documentRef, 'historicalAISScenarioLimitation', scenario.limitations.length ? scenario.limitations.join(' · ') : null);
  const qualification = scenario.qualification;
  setText(documentRef, 'historicalAISScenarioQualificationThreat', [qualification?.status, qualification?.code].filter(Boolean).join(' · '));
  const preview = documentRef.getElementById('historicalAISScenePreview');
  if (preview) preview.hidden = false;
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
  renderWorkflow(documentRef, state);
}

export function renderHistoricalAISWorkbench(documentRef, state) {
  renderScenarioList(documentRef, state);
  renderScenarioDetail(documentRef, state);
  renderBenchmark(documentRef, state);
  const catalogStatus = documentRef.getElementById('historicalAISCatalogStatus');
  if (catalogStatus) {
    catalogStatus.textContent = state.catalog.error
      ? `${state.catalog.error.code}: ${state.catalog.error.message}`
      : state.catalog.status;
    catalogStatus.dataset.state = state.catalog.status === 'READY' ? 'ready' : state.catalog.status === 'ERROR' ? 'error' : 'info';
  }
  setText(documentRef, 'historicalAISScenarioCatalogStatus', state.catalog.status);
}
