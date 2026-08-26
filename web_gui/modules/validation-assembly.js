const CREATE_FIELDS = [
  'validation_rule_id',
  'scenario_id',
  'algorithm_id',
  'tracker_id',
  'seed',
  'episode_index',
  'dt',
  't_end',
  'strict_no_fallback',
  'evaluator_profile_id',
  'algorithm_config',
  'tracker_config',
  'scenario_override',
];
const TUPLE_FIELDS = [
  'validation_rule_id',
  'scenario_id',
  'algorithm_id',
  'tracker_id',
];
const EDITABLE_FIELDS = [
  ...TUPLE_FIELDS,
  'seed',
  'episode_index',
  'dt',
  't_end',
];

const PRODUCT_POLICY_MISSING = 'product-capability-policy-missing';
const PRODUCT_POLICY_INVALID = 'product-capability-policy-invalid';

function clone(value) {
  return value === undefined ? undefined : structuredClone(value);
}

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  Object.freeze(value);
  for (const child of Object.values(value)) deepFreeze(child);
  return value;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
}

function equalSpec(left, right) {
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

function policyFailure(status, code, message) {
  return { status, code, message, value: null };
}

function orderedIdentifiers(value, field) {
  if (!Array.isArray(value) || !value.length) {
    throw new TypeError(`${field} must be a non-empty array.`);
  }
  if (!value.every((item) => typeof item === 'string' && item.length > 0)) {
    throw new TypeError(`${field} must contain non-empty strings.`);
  }
  if (new Set(value).size !== value.length) {
    throw new TypeError(`${field} must not contain duplicates.`);
  }
  return [...value];
}

function productCapabilityPolicy(catalog) {
  if (!catalog || !Object.hasOwn(catalog, 'product_capability_policy')) {
    return policyFailure(
      'missing',
      PRODUCT_POLICY_MISSING,
      'Capability catalog does not expose product_capability_policy.',
    );
  }
  const raw = catalog.product_capability_policy;
  try {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      throw new TypeError('product_capability_policy must be an object.');
    }
    if (typeof raw.policy_id !== 'string' || !raw.policy_id.length) {
      throw new TypeError('policy_id must be a non-empty string.');
    }
    const algorithmIds = orderedIdentifiers(raw.algorithm_ids, 'algorithm_ids');
    const trackerIds = orderedIdentifiers(raw.tracker_ids, 'tracker_ids');
    if (!algorithmIds.includes(raw.default_algorithm_id)) {
      throw new TypeError('default_algorithm_id must be present in algorithm_ids.');
    }
    if (!trackerIds.includes(raw.default_tracker_id)) {
      throw new TypeError('default_tracker_id must be present in tracker_ids.');
    }
    const constraints = raw.constraints;
    if (!constraints || typeof constraints !== 'object' || Array.isArray(constraints)) {
      throw new TypeError('constraints must be an object.');
    }
    if (constraints.requires_explicit_validation_rule_id !== true) {
      throw new TypeError('constraints.requires_explicit_validation_rule_id must be true.');
    }
    if (constraints.requires_exact_tuple !== true) {
      throw new TypeError('constraints.requires_exact_tuple must be true.');
    }
    if (!constraints.algorithms || typeof constraints.algorithms !== 'object' || Array.isArray(constraints.algorithms)) {
      throw new TypeError('constraints.algorithms must be an object.');
    }
    const algorithmConstraints = Object.fromEntries(algorithmIds.map((algorithmId) => {
      const constraint = constraints.algorithms[algorithmId];
      if (!constraint || typeof constraint !== 'object' || Array.isArray(constraint)) {
        throw new TypeError(`constraints.algorithms.${algorithmId} must be an object.`);
      }
      if (typeof constraint.requires_domain_profile !== 'boolean') {
        throw new TypeError(`constraints.algorithms.${algorithmId}.requires_domain_profile must be boolean.`);
      }
      const normalized = { requires_domain_profile: constraint.requires_domain_profile };
      if (constraint.requires_domain_profile) {
        if (
          typeof constraint.required_domain_qualification !== 'string'
          || !constraint.required_domain_qualification.length
        ) {
          throw new TypeError(
            `constraints.algorithms.${algorithmId}.required_domain_qualification must be a non-empty string.`,
          );
        }
        normalized.required_domain_qualification = constraint.required_domain_qualification;
      }
      return [algorithmId, normalized];
    }));
    const algorithmCatalogIds = new Set((catalog.algorithms || []).map((item) => item.id));
    const trackerCatalogIds = new Set((catalog.trackers || []).map((item) => item.id));
    for (const algorithmId of algorithmIds) {
      if (!algorithmCatalogIds.has(algorithmId)) {
        throw new TypeError(`algorithm_ids references missing catalog algorithm ${algorithmId}.`);
      }
    }
    for (const trackerId of trackerIds) {
      if (!trackerCatalogIds.has(trackerId)) {
        throw new TypeError(`tracker_ids references missing catalog tracker ${trackerId}.`);
      }
    }
    return {
      status: 'ready',
      code: null,
      message: null,
      value: {
        policy_id: raw.policy_id,
        algorithm_ids: algorithmIds,
        tracker_ids: trackerIds,
        default_algorithm_id: raw.default_algorithm_id,
        default_tracker_id: raw.default_tracker_id,
        constraints: {
          requires_explicit_validation_rule_id: true,
          requires_exact_tuple: true,
          algorithms: algorithmConstraints,
        },
      },
    };
  } catch (error) {
    return policyFailure(
      'invalid',
      PRODUCT_POLICY_INVALID,
      `Invalid product_capability_policy: ${String(error.message || error)}`,
    );
  }
}

function policyEntries(catalog, policy, field) {
  if (policy.status !== 'ready') return [];
  const collection = field === 'algorithm_id' ? catalog.algorithms || [] : catalog.trackers || [];
  const identifiers = field === 'algorithm_id'
    ? policy.value.algorithm_ids
    : policy.value.tracker_ids;
  return identifiers.map((id) => collection.find((entry) => entry.id === id)).filter(Boolean);
}

function defaultSpec(catalog) {
  const policy = productCapabilityPolicy(catalog);
  if (policy.status !== 'ready') return null;
  return {
    validation_rule_id: catalog.defaults.validation_rule_id,
    scenario_id: catalog.defaults.scenario_id,
    algorithm_id: policy.value.default_algorithm_id,
    tracker_id: policy.value.default_tracker_id,
    seed: 0,
    episode_index: 0,
    dt: null,
    t_end: null,
    strict_no_fallback: true,
    evaluator_profile_id: 'ccta_2023_demo-v1',
    algorithm_config: {},
    tracker_config: {},
    scenario_override: null,
  };
}

function normalizeSpec(spec, catalog) {
  const normalized = (catalog ? defaultSpec(catalog) : null) || {
    validation_rule_id: null,
    scenario_id: null,
    algorithm_id: null,
    tracker_id: null,
    seed: 0,
    episode_index: 0,
    dt: null,
    t_end: null,
    strict_no_fallback: true,
    evaluator_profile_id: 'ccta_2023_demo-v1',
    algorithm_config: {},
    tracker_config: {},
    scenario_override: null,
  };
  for (const field of CREATE_FIELDS) {
    if (Object.hasOwn(spec || {}, field)) normalized[field] = clone(spec[field]);
  }
  normalized.strict_no_fallback = true;
  return normalized;
}

function tupleKey(spec) {
  return [
    spec.validation_rule_id,
    spec.scenario_id,
    spec.algorithm_id,
    spec.tracker_id,
  ].join('\u0000');
}

function classify(catalog, spec) {
  if (!catalog || !spec) return 'unavailable';
  const key = tupleKey(spec);
  if (!selectableTuples(catalog).some((tuple) => tupleKey(tuple) === key)) return 'unavailable';
  if (catalog.verified_combinations.some((tuple) => tupleKey(tuple) === key)) return 'verified';
  if (catalog.experimental_combinations.some((tuple) => tupleKey(tuple) === key)) return 'experimental';
  return 'unavailable';
}

function entryExecutionReady(entry) {
  return Boolean(entry)
    && entry.selectable !== false
    && entry.runtime_ready !== false
    && entry.dependency_available !== false;
}

function selectableTuples(catalog) {
  const policy = productCapabilityPolicy(catalog);
  if (policy.status !== 'ready') return [];
  const collections = {
    validation_rule_id: catalog.rules || [],
    scenario_id: catalog.scenarios || [],
    algorithm_id: policyEntries(catalog, policy, 'algorithm_id'),
    tracker_id: policyEntries(catalog, policy, 'tracker_id'),
  };
  return (catalog.selectable_combinations || []).filter((tuple) => TUPLE_FIELDS.every((field) => {
    const entry = collections[field].find((item) => item.id === tuple[field]);
    return entryExecutionReady(entry);
  }));
}

function catalogOptions(catalog, draft) {
  if (!catalog) return {};
  const policy = productCapabilityPolicy(catalog);
  const tuples = selectableTuples(catalog);
  const collections = {
    validation_rule_id: catalog.rules || [],
    scenario_id: catalog.scenarios || [],
    algorithm_id: policyEntries(catalog, policy, 'algorithm_id'),
    tracker_id: policyEntries(catalog, policy, 'tracker_id'),
  };
  return Object.fromEntries(Object.entries(collections).map(([field, entries]) => [
    field,
    entries.map((entry) => ({
      ...clone(entry),
      enabled: tuples.some((tuple) => {
        if (tuple[field] !== entry.id) return false;
        const fixedFields = field === 'validation_rule_id'
          ? ['algorithm_id', 'tracker_id']
          : TUPLE_FIELDS.filter((tupleField) => tupleField !== field);
        return fixedFields.every((tupleField) => tuple[tupleField] === draft?.[tupleField]);
      }),
    })),
  ]));
}

function executionPlan(catalog, draft) {
  const scenario = catalog?.scenarios?.find((item) => item.id === draft?.scenario_id);
  const clock = (field) => ({
    source: draft?.[field] == null ? 'scenario-default' : 'explicit-override',
    requested: draft?.[field] ?? null,
    effective: draft?.[field] ?? scenario?.[field] ?? null,
  });
  return { dt: clock('dt'), t_end: clock('t_end') };
}

function validationErrors(draft) {
  const errors = {};
  if (!draft) return errors;
  if (!Number.isInteger(draft?.seed) || draft.seed < 0) errors.seed = 'Seed must be a non-negative integer.';
  if (!Number.isInteger(draft?.episode_index) || draft.episode_index < 0) {
    errors.episode_index = 'Episode index must be a non-negative integer.';
  }
  if (draft?.dt !== null && (!(draft.dt > 0) || !Number.isFinite(draft.dt))) {
    errors.dt = 'dt must be null or greater than zero.';
  }
  if (draft?.t_end !== null && (!(draft.t_end > 0) || !Number.isFinite(draft.t_end))) {
    errors.t_end = 't_end must be null or greater than zero.';
  }
  return errors;
}

function createConstraint(draft, policy, catalog) {
  if (!draft || policy.status !== 'ready') return null;
  const constraint = policy.value.constraints.algorithms[draft.algorithm_id];
  if (!constraint?.requires_domain_profile) return null;
  const qualification = constraint.required_domain_qualification;
  const scenario = (catalog?.scenarios || []).find((item) => item.id === draft.scenario_id);
  if (scenario?.domain_profile?.qualification === qualification) return null;
  return {
    code: 'requires-domain-profile',
    algorithm_id: draft.algorithm_id,
    required_domain_qualification: qualification,
    message: `Selected algorithm requires an explicit ${qualification} ShipDomainProfile; Config cannot provide one.`,
  };
}

function repairTuple(catalog, draft, latestField = null) {
  if (classify(catalog, draft) !== 'unavailable') return null;
  const policyDefaults = defaultSpec(catalog);
  const candidates = selectableTuples(catalog)
    .map((tuple, index) => ({ tuple, index }))
    .filter(({ tuple }) => latestField === null || tuple[latestField] === draft[latestField]);
  if (!candidates.length) return null;
  const otherFields = TUPLE_FIELDS.filter((field) => field !== latestField);
  candidates.sort((left, right) => {
    const changedLeft = otherFields.filter((field) => left.tuple[field] !== draft[field]).length;
    const changedRight = otherFields.filter((field) => right.tuple[field] !== draft[field]).length;
    if (changedLeft !== changedRight) return changedLeft - changedRight;
    const defaultsLeft = otherFields.filter((field) => left.tuple[field] === policyDefaults?.[field]).length;
    const defaultsRight = otherFields.filter((field) => right.tuple[field] === policyDefaults?.[field]).length;
    return defaultsRight - defaultsLeft || left.index - right.index;
  });
  return candidates[0].tuple;
}

export function createValidationAssembly({
  catalog: initialCatalog,
  activeSession = null,
  catalogError = null,
  currentSessionStatus = 'known',
  currentSessionError = null,
}) {
  let catalog = clone(initialCatalog);
  let draft = activeSession?.spec
    ? normalizeSpec(activeSession.spec, catalog)
    : (catalog ? defaultSpec(catalog) : null);
  let baseline = clone(draft);
  let activeSpec = activeSession?.spec ? clone(draft) : null;
  let activeState = activeSession?.state || null;
  let sessionStatus = currentSessionStatus;
  let creating = false;
  let createSequence = 0;
  let pendingToken = null;
  let pendingSpec = null;
  let runtimePending = null;
  const notices = [];
  if (catalogError) notices.push({ kind: 'catalog-error', message: String(catalogError.message || catalogError) });
  if (currentSessionError) {
    notices.push({ kind: 'session-error', message: String(currentSessionError.message || currentSessionError) });
  }

  function requireEditableAuthority(action) {
    if (runtimePending) {
      throw new Error(`${runtimePending} is in progress; ${action} is disabled.`);
    }
    if (sessionStatus !== 'known') {
      throw new Error(`Current session authority is ${sessionStatus}; ${action} is disabled.`);
    }
  }

  function requireProductPolicy() {
    const policy = productCapabilityPolicy(catalog);
    if (policy.status !== 'ready') throw new Error(`${policy.code}: ${policy.message}`);
    return policy;
  }

  return {
    edit(field, value) {
      if (creating) throw new Error('Validation Assembly is creating; controls are frozen.');
      requireEditableAuthority('editing');
      if (!catalog) throw new Error('Capability catalog unavailable; Active Spec is read-only.');
      requireProductPolicy();
      if (!EDITABLE_FIELDS.includes(field)) {
        throw new TypeError(`${field} is not user-editable through Validation Assembly.`);
      }
      if (TUPLE_FIELDS.includes(field)) {
        const option = catalogOptions(catalog, draft)[field]?.find((item) => item.id === value);
        if (!option?.enabled) return false;
      }
      const previous = clone(draft);
      draft[field] = clone(value);
      if (TUPLE_FIELDS.includes(field)) {
        const repair = field === 'validation_rule_id' ? repairTuple(catalog, draft, field) : null;
        if (repair) {
          for (const tupleField of TUPLE_FIELDS) draft[tupleField] = repair[tupleField];
          notices.push({
            kind: 'repair',
            message: `Exact Tuple repaired after ${field} changed; latest field preserved.`,
          });
        }
        if (draft.algorithm_id !== previous.algorithm_id) {
          draft.algorithm_config = {};
          notices.push({ kind: 'config-cleared', message: 'Algorithm config cleared after Algorithm changed.' });
        }
        if (draft.tracker_id !== previous.tracker_id) {
          draft.tracker_config = {};
          notices.push({ kind: 'config-cleared', message: 'Tracker config cleared after Tracker changed.' });
        }
        if (draft.scenario_id !== previous.scenario_id) {
          draft.scenario_override = null;
          draft.dt = null;
          draft.t_end = null;
          notices.push({
            kind: 'override-cleared',
            message: 'Scenario override and clock overrides cleared after Scenario changed.',
          });
        }
      }
      return true;
    },
    resetDefault() {
      if (creating) throw new Error('Validation Assembly is creating; controls are frozen.');
      requireEditableAuthority('Default');
      if (!catalog) throw new Error('Capability catalog unavailable; Default is disabled.');
      requireProductPolicy();
      draft = defaultSpec(catalog);
      notices.length = 0;
    },
    beginCreate({ confirmedExperimental = false } = {}) {
      if (creating) throw new Error('Validation Assembly is already creating.');
      requireEditableAuthority('Create');
      if (!catalog) throw new Error('Capability catalog unavailable; Create is disabled.');
      const policy = requireProductPolicy();
      const classification = classify(catalog, draft);
      if (Object.keys(validationErrors(draft)).length) throw new Error('Validation Draft is invalid.');
      if (activeState === 'RUNNING') throw new Error('Active Session is RUNNING; pause it before Create.');
      if (activeSpec && equalSpec(draft, activeSpec)) throw new Error('Validation Draft matches active session.');
      if (classification === 'unavailable') throw new Error('Exact Tuple is unavailable.');
      const constraint = createConstraint(draft, policy, catalog);
      if (constraint) throw new Error(`${constraint.code}: ${constraint.message}`);
      if (classification === 'experimental' && !confirmedExperimental) {
        throw new Error('Experimental tuple requires confirmation before Create.');
      }
      creating = true;
      pendingToken = `create-${++createSequence}`;
      pendingSpec = deepFreeze(clone(draft));
      return { token: pendingToken, spec: pendingSpec };
    },
    resolveCreate(token, session) {
      if (!creating || token !== pendingToken) return false;
      draft = clone(pendingSpec);
      baseline = clone(pendingSpec);
      activeSpec = clone(pendingSpec);
      activeState = session?.state || 'CREATED';
      sessionStatus = 'known';
      creating = false;
      pendingToken = null;
      pendingSpec = null;
      notices.length = 0;
      return true;
    },
    syncActiveSession(session, { reason = 'session-sync' } = {}) {
      const wasDirty = draft ? !equalSpec(draft, baseline) : false;
      const nextActiveSpec = session?.spec ? normalizeSpec(session.spec, catalog) : null;
      const activeChanged = !equalSpec(activeSpec, nextActiveSpec) || activeState !== (session?.state || null);
      activeSpec = clone(nextActiveSpec);
      activeState = session?.state || null;
      sessionStatus = 'known';
      if (!wasDirty) {
        draft = nextActiveSpec
          ? clone(nextActiveSpec)
          : (catalog ? defaultSpec(catalog) : null);
        baseline = clone(draft);
      } else if (activeChanged) {
        notices.push({
          kind: 'active-session-changed',
          message: `Active Session changed (${reason}); unsaved Validation Draft preserved.`,
        });
      }
    },
    markCurrentSessionUnknown(error) {
      sessionStatus = 'unknown';
      notices.push({
        kind: 'session-error',
        message: `Current session authority unavailable: ${String(error?.message || error)}`,
      });
    },
    markCurrentSessionLoading() {
      sessionStatus = 'loading';
    },
    setRuntimePending(command) {
      runtimePending = command || null;
    },
    rejectCreate(token, error) {
      if (!creating || token !== pendingToken) return false;
      creating = false;
      pendingToken = null;
      pendingSpec = null;
      notices.push({ kind: 'create-error', message: String(error?.message || error) });
      return true;
    },
    replaceCatalog(nextCatalog, { reason = 'retry' } = {}) {
      if (creating) throw new Error('Validation Assembly is creating; catalog replacement is deferred.');
      catalog = clone(nextCatalog);
      if (!draft) {
        draft = defaultSpec(catalog);
        baseline = clone(draft);
      }
      const previous = clone(draft);
      const repair = repairTuple(catalog, draft);
      if (repair) {
        for (const field of TUPLE_FIELDS) draft[field] = repair[field];
        if (draft.algorithm_id !== previous.algorithm_id) draft.algorithm_config = {};
        if (draft.tracker_id !== previous.tracker_id) draft.tracker_config = {};
        if (draft.scenario_id !== previous.scenario_id) draft.scenario_override = null;
      }
      notices.push({
        kind: 'catalog-refreshed',
        message: repair
          ? `Capability catalog refreshed (${reason}); stale Exact Tuple repaired visibly.`
          : `Capability catalog refreshed (${reason}); current Exact Tuple remains valid.`,
      });
    },
    markCatalogFailure(error) {
      if (creating) throw new Error('Validation Assembly is creating; catalog failure update is deferred.');
      catalog = null;
      notices.push({
        kind: 'catalog-error',
        message: `Capability catalog unavailable: ${String(error?.message || error)}`,
      });
    },
    snapshot() {
      const policy = productCapabilityPolicy(catalog);
      const classification = classify(catalog, draft);
      const errors = validationErrors(draft);
      const constraint = createConstraint(draft, policy, catalog);
      const matchesActive = Boolean(activeSpec && equalSpec(draft, activeSpec));
      let createBlock = null;
      if (creating) createBlock = 'creating';
      else if (runtimePending) createBlock = 'runtime-pending';
      else if (sessionStatus === 'loading') createBlock = 'current-session-loading';
      else if (sessionStatus !== 'known') createBlock = 'current-session-unknown';
      else if (catalog && policy.status !== 'ready') createBlock = policy.code;
      else if (activeState === 'RUNNING') createBlock = 'active-running';
      else if (matchesActive) createBlock = 'matches-active';
      else if (classification === 'unavailable') createBlock = 'unavailable';
      else if (constraint) createBlock = constraint.code;
      else if (Object.keys(errors).length) createBlock = 'invalid-draft';
      else if (classification === 'experimental') createBlock = 'experimental-confirmation';
      return clone({
        draft,
        dirty: draft ? !equalSpec(draft, baseline) : false,
        classification,
        valid: policy.status === 'ready' && classification !== 'unavailable' && Object.keys(errors).length === 0,
        validationErrors: errors,
        catalogStatus: catalog ? 'ready' : 'error',
        productPolicyStatus: policy.status,
        productCapabilityPolicy: policy.value,
        readOnly: !catalog || policy.status !== 'ready' || sessionStatus !== 'known' || Boolean(runtimePending),
        sessionStatus,
        creating,
        runtimePending,
        activeState,
        activeSpec,
        matchesActive,
        createBlock,
        createBlockReason: policy.status !== 'ready' ? policy.message : constraint?.message || null,
        createConstraint: constraint,
        canCreate: createBlock === null,
        catalog,
        options: catalogOptions(catalog, draft),
        executionPlan: executionPlan(catalog, draft),
        notices,
      });
    },
  };
}

export { CREATE_FIELDS };
