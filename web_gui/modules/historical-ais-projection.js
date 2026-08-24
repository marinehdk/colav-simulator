export const HISTORICAL_AIS_SCENARIO_SCHEMA = 'historical-ais-scenario.v1';
export const HISTORICAL_AIS_PRESENTATION_SCHEMA = 'historical-workflow.presentation.v1';

const MODE_LABELS = Object.freeze({
  HISTORICAL_REPLAY: {
    label: 'Historical Replay',
    description: '全船历史 AIS 回放；不运行 COLAV。',
  },
  COUNTERFACTUAL: {
    label: 'Counterfactual',
    description: 'T0 后 Reference Vessel 交给 Mid-MPC；其他船继续历史回放。',
  },
});

function object(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
}

function unavailable(code, message) {
  return {
    status: 'UNAVAILABLE',
    error: { code, message },
    identity: null,
    scenarioId: null,
    title: null,
    description: null,
    source: null,
    selection: null,
    enc: null,
    operability: null,
    readiness: null,
    modes: [],
    limitations: [],
    digests: null,
    algorithmCapability: null,
    qualification: null,
  };
}

function validScenarioDescriptor(value) {
  const archive = object(value?.archive_scope);
  const window = object(value?.current_window);
  const enc = object(value?.enc);
  const readiness = object(value?.readiness);
  const binding = object(value?.runtime_binding);
  const presentation = object(value?.presentation);
  const capability = object(presentation?.runtime?.algorithm_capability_evidence);
  return value?.schema_version === HISTORICAL_AIS_SCENARIO_SCHEMA
    && value?.kind === 'HISTORICAL_AIS'
    && typeof value?.scenario_id === 'string'
    && typeof value?.display_name === 'string'
    && Array.isArray(value?.modes)
    && value.modes.every(mode => typeof mode === 'string' && MODE_LABELS[mode])
    && archive !== null
    && window !== null
    && enc !== null
    && readiness !== null
    && binding !== null
    && capability !== null
    && presentation?.schema_version === 'historical-ais-scenario.presentation.v1'
    && object(presentation.operability) !== null
    && object(presentation.qualification) !== null
    && object(presentation.runtime) !== null
    && object(presentation.digests) !== null
    && Array.isArray(value?.limitations)
    && typeof value?.descriptor_sha256 === 'string';
}

/** Accept only the public versioned Historical AIS descriptor. */
export function projectHistoricalAISScenario(value) {
  if (!validScenarioDescriptor(value)) {
    return unavailable('INVALID_SCENARIO_DESCRIPTOR', 'Historical AIS descriptor is missing or unsupported');
  }
  const archive = value.archive_scope;
  const window = value.current_window;
  const readiness = value.readiness;
  const binding = value.runtime_binding;
  const scenePresentation = value.presentation;
  const capability = scenePresentation.runtime.algorithm_capability_evidence;
  const presentationDigests = scenePresentation.digests;
  const operability = scenePresentation.operability;
  const qualification = scenePresentation.qualification;
  return {
    status: 'AVAILABLE',
    error: null,
    identity: scenePresentation.scenario?.kind ?? null,
    scenarioId: scenePresentation.scenario?.id ?? null,
    title: value.display_name,
    description: null,
    source: {
      archiveName: archive.source_name ?? null,
      archiveDays: archive.day_count ?? null,
      archiveRows: archive.row_count ?? null,
      archiveMmsi: archive.union_mmsi_count ?? null,
      status: qualification.source_readiness ?? null,
      attribution: archive.attribution ?? null,
    },
    selection: {
      entryName: window.entry_name ?? null,
      startUtc: window.start_utc ?? null,
      endUtc: window.end_utc ?? null,
      durationLabel: window.duration_label ?? null,
      bbox: Array.isArray(window.bbox) ? window.bbox : null,
      filterMmsi: Array.isArray(window.selection_mmsi) ? window.selection_mmsi : null,
      selectedMmsi: Array.isArray(window.runtime_mmsi) ? window.runtime_mmsi : null,
      targetMmsi: Array.isArray(window.target_mmsi) ? window.target_mmsi : null,
      runtimeActorCount: window.runtime_actor_count ?? null,
      referenceMmsi: window.reference_mmsi ?? null,
      t0Utc: window.t0_utc ?? null,
      sourceRows: window.source_row_count ?? null,
      normalizedRows: window.normalized_row_count ?? null,
      qualityFindings: window.quality_finding_count ?? null,
    },
    enc: {
      profileId: value.enc.profile_id ?? null,
      qualification: value.enc.qualification_state ?? null,
      preflight: value.enc.preflight_status ?? null,
    },
    operability: {
      status: operability.status ?? null,
      scope: operability.scope ?? null,
    },
    readiness: {
      status: qualification.source_readiness ?? null,
      canRun: operability.status === 'AVAILABLE',
      envVar: readiness.env_var ?? null,
    },
    modes: value.modes.map(id => ({ id, ...MODE_LABELS[id] })),
    limitations: Array.isArray(scenePresentation.qualification?.limitations)
      ? [...scenePresentation.qualification.limitations]
      : [],
    digests: {
      archive: presentationDigests?.archive_sha256 ?? null,
      entry: presentationDigests?.entry_sha256 ?? null,
      selection: presentationDigests?.selection_sha256 ?? null,
      descriptor: presentationDigests?.descriptor_sha256 ?? null,
    },
    algorithmCapability: {
      bindingRole: capability.binding_role ?? null,
      geometryEquivalence: capability.geometry_equivalence ?? null,
      exactTuple: Array.isArray(capability.exact_tuple) ? capability.exact_tuple : null,
      historicalScenarioId: binding.historical_scenario_id ?? null,
      algorithmId: scenePresentation.runtime?.algorithm_id ?? null,
      trackerId: scenePresentation.runtime?.tracker_id ?? null,
    },
    qualification,
  };
}

export function unavailableHistoricalWorkflow(code = 'WORKFLOW_UNAVAILABLE', message = 'Historical workflow unavailable') {
  return {
    status: 'UNAVAILABLE',
    error: { code, message },
    workflowId: null,
    mode: null,
    lifecycle: null,
    stages: null,
    presentation: null,
  };
}

/** Read canonical backend presentation only; never interpret raw evidence. */
export function projectHistoricalAISWorkflow(value) {
  const presentation = object(value?.presentation);
  if (value?.schema_version !== 'historical-workflow.snapshot.v1'
    || presentation?.schema_version !== HISTORICAL_AIS_PRESENTATION_SCHEMA) {
    return unavailableHistoricalWorkflow(
      'INVALID_WORKFLOW_PRESENTATION',
      'Canonical Historical workflow presentation is missing or unsupported',
    );
  }
  return {
    status: 'AVAILABLE',
    error: null,
    workflowId: value.workflow_id ?? null,
    mode: value.mode ?? null,
    lifecycle: value.status ?? null,
    stages: object(value.stages),
    presentation,
  };
}
