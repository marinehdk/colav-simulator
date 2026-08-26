import assert from 'node:assert/strict';
import test from 'node:test';

import { createValidationAssembly } from '../../web_gui/modules/validation-assembly.js';

const catalog = {
  schema_version: 'capability-catalog.v1',
  product_capability_policy: {
    policy_id: 'synthetic-reducer-policy',
    algorithm_ids: ['nominal', 'vo'],
    tracker_ids: ['god', 'kf'],
    default_algorithm_id: 'nominal',
    default_tracker_id: 'god',
    constraints: {
      requires_explicit_validation_rule_id: true,
      requires_exact_tuple: true,
      algorithms: {
        nominal: { requires_domain_profile: false },
        vo: { requires_domain_profile: false },
      },
    },
  },
  defaults: {
    validation_rule_id: 'rule14',
    scenario_id: 'head_on',
    algorithm_id: 'nominal',
    tracker_id: 'god',
  },
  rules: [
    { id: 'rule13', selectable: true },
    { id: 'rule14', selectable: true },
  ],
  scenarios: [
    { id: 'head_on', name: 'Head on', dt: 0.1, t_end: 600, selectable: true },
    { id: 'overtaking', name: 'Overtaking', dt: 0.2, t_end: 500, selectable: true },
    { id: 'busy', name: 'Busy water', dt: 0.1, t_end: 900, selectable: true },
  ],
  algorithms: [
    { id: 'nominal', selectable: true },
    { id: 'vo', selectable: true },
  ],
  trackers: [
    { id: 'god', selectable: true },
    { id: 'kf', selectable: true },
  ],
  verified_combinations: [
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'nominal', tracker_id: 'god' },
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'god' },
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'kf' },
    { validation_rule_id: 'rule13', scenario_id: 'overtaking', algorithm_id: 'nominal', tracker_id: 'god' },
    { validation_rule_id: 'rule13', scenario_id: 'overtaking', algorithm_id: 'vo', tracker_id: 'god' },
  ],
  experimental_combinations: [
    { validation_rule_id: 'rule14', scenario_id: 'busy', algorithm_id: 'vo', tracker_id: 'kf' },
  ],
};
catalog.selectable_combinations = [
  ...catalog.verified_combinations,
  ...catalog.experimental_combinations,
];

const productionCatalog = {
  schema_version: 'capability-catalog.v1',
  product_capability_policy: {
    policy_id: 'colav-product-v1',
    algorithm_ids: ['vo', 'potocnik_colreg_fan_mpc', 'mid_mpc_ipopt'],
    tracker_ids: ['god'],
    default_algorithm_id: 'vo',
    default_tracker_id: 'god',
    constraints: {
      requires_explicit_validation_rule_id: true,
      requires_exact_tuple: true,
      algorithms: {
        vo: { requires_domain_profile: false },
        potocnik_colreg_fan_mpc: { requires_domain_profile: false },
        mid_mpc_ipopt: {
          requires_domain_profile: true,
          required_domain_qualification: 'QUALIFIED',
        },
      },
    },
  },
  defaults: {
    validation_rule_id: 'rule14',
    scenario_id: 'head_on',
    algorithm_id: 'legacy-default',
    tracker_id: 'legacy-tracker',
  },
  rules: [{ id: 'rule14', selectable: true }],
  scenarios: [{ id: 'head_on', name: 'Head on', dt: 0.1, t_end: 600, selectable: true }],
  algorithms: [
    { id: 'mid_mpc_ipopt', selectable: true },
    { id: 'vo', selectable: true },
    { id: 'potocnik_colreg_fan_mpc', selectable: true },
  ],
  trackers: [{ id: 'god', selectable: true }],
  verified_combinations: [
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'mid_mpc_ipopt', tracker_id: 'god' },
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'god' },
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'potocnik_colreg_fan_mpc', tracker_id: 'god' },
  ],
  experimental_combinations: [],
};
productionCatalog.selectable_combinations = [...productionCatalog.verified_combinations];
productionCatalog.selectable_combinations[1].latest_evidence = { source: 'catalog-only' };

test('product policy owns selector order and defaults without leaking tuple evidence into Run Specification', () => {
  const assembly = createValidationAssembly({ catalog: productionCatalog });
  const snapshot = assembly.snapshot();

  assert.equal(snapshot.draft.algorithm_id, 'vo');
  assert.equal(snapshot.draft.tracker_id, 'god');
  assert.equal(Object.hasOwn(snapshot.draft, 'latest_evidence'), false);
  assert.deepEqual(snapshot.options.algorithm_id.map((item) => item.id), [
    'vo',
    'potocnik_colreg_fan_mpc',
    'mid_mpc_ipopt',
  ]);
  assert.deepEqual(snapshot.options.tracker_id.map((item) => item.id), ['god']);
  assert.equal(snapshot.productPolicyStatus, 'ready');
  assert.deepEqual(snapshot.productCapabilityPolicy.algorithm_ids, [
    'vo',
    'potocnik_colreg_fan_mpc',
    'mid_mpc_ipopt',
  ]);
});

test('algorithm constraint metadata drives a typed domain-profile Create block', () => {
  const assembly = createValidationAssembly({ catalog: productionCatalog });
  assert.equal(assembly.edit('algorithm_id', 'mid_mpc_ipopt'), true);

  const snapshot = assembly.snapshot();
  assert.equal(snapshot.classification, 'verified');
  assert.equal(snapshot.valid, true);
  assert.equal(snapshot.createBlock, 'requires-domain-profile');
  assert.equal(snapshot.canCreate, false);
  assert.deepEqual(snapshot.createConstraint, {
    code: 'requires-domain-profile',
    algorithm_id: 'mid_mpc_ipopt',
    required_domain_qualification: 'QUALIFIED',
    message: 'Selected algorithm requires an explicit QUALIFIED ShipDomainProfile; Config cannot provide one.',
  });
  assert.equal(snapshot.createBlockReason, snapshot.createConstraint.message);
  assert.throws(
    () => assembly.beginCreate(),
    /requires-domain-profile:.*QUALIFIED ShipDomainProfile/,
  );
});

test('domain-profile block follows policy metadata when assigned to a different algorithm', () => {
  const reassigned = structuredClone(productionCatalog);
  reassigned.product_capability_policy.constraints.algorithms.vo = {
    requires_domain_profile: true,
    required_domain_qualification: 'REVIEWED',
  };
  reassigned.product_capability_policy.constraints.algorithms.mid_mpc_ipopt = {
    requires_domain_profile: false,
  };
  const assembly = createValidationAssembly({ catalog: reassigned });

  assert.equal(assembly.snapshot().draft.algorithm_id, 'vo');
  assert.equal(assembly.snapshot().createConstraint.algorithm_id, 'vo');
  assert.match(assembly.snapshot().createBlockReason, /REVIEWED ShipDomainProfile/);

  assert.equal(assembly.edit('algorithm_id', 'mid_mpc_ipopt'), true);
  assert.equal(assembly.snapshot().createConstraint, null);
  assert.equal(assembly.snapshot().createBlock, null);
});

test('catalog-qualified Historical AIS domain profile admits Mid-MPC as experimental', () => {
  const historical = structuredClone(productionCatalog);
  historical.scenarios.push({
    id: 'hais_romsdal_20260701_120007_121007',
    name: 'Historical AIS',
    dt: 1,
    t_end: 600,
    selectable: true,
    domain_profile: { qualification: 'QUALIFIED' },
  });
  const tuples = [
    {
      validation_rule_id: 'rule14',
      scenario_id: 'hais_romsdal_20260701_120007_121007',
      algorithm_id: 'vo',
      tracker_id: 'god',
    },
    {
      validation_rule_id: 'rule14',
      scenario_id: 'hais_romsdal_20260701_120007_121007',
      algorithm_id: 'mid_mpc_ipopt',
      tracker_id: 'god',
    },
  ];
  historical.experimental_combinations = tuples;
  historical.selectable_combinations = [...historical.verified_combinations, ...tuples];
  const assembly = createValidationAssembly({ catalog: historical });

  assert.equal(assembly.edit('scenario_id', 'hais_romsdal_20260701_120007_121007'), true);
  assert.equal(assembly.edit('algorithm_id', 'mid_mpc_ipopt'), true);
  const snapshot = assembly.snapshot();
  assert.equal(snapshot.classification, 'experimental');
  assert.equal(snapshot.createConstraint, null);
  assert.equal(snapshot.createBlock, 'experimental-confirmation');
  assert.equal(snapshot.canCreate, false);
  assert.doesNotThrow(() => assembly.beginCreate({ confirmedExperimental: true }));
});

test('missing or malformed product policy is typed unavailable and cannot Create', () => {
  const missingPolicy = structuredClone(productionCatalog);
  delete missingPolicy.product_capability_policy;
  const missing = createValidationAssembly({ catalog: missingPolicy });
  assert.equal(missing.snapshot().productPolicyStatus, 'missing');
  assert.equal(missing.snapshot().createBlock, 'product-capability-policy-missing');
  assert.equal(missing.snapshot().readOnly, true);
  assert.equal(missing.snapshot().canCreate, false);
  assert.deepEqual(missing.snapshot().options.algorithm_id, []);
  assert.deepEqual(missing.snapshot().options.tracker_id, []);
  assert.throws(() => missing.beginCreate(), /product-capability-policy-missing/);

  const invalidPolicy = structuredClone(productionCatalog);
  delete invalidPolicy.product_capability_policy.constraints.algorithms.mid_mpc_ipopt;
  const invalid = createValidationAssembly({ catalog: invalidPolicy });
  assert.equal(invalid.snapshot().productPolicyStatus, 'invalid');
  assert.equal(invalid.snapshot().createBlock, 'product-capability-policy-invalid');
  assert.equal(invalid.snapshot().readOnly, true);
  assert.equal(invalid.snapshot().canCreate, false);
  assert.match(invalid.snapshot().createBlockReason, /mid_mpc_ipopt/);
  assert.throws(() => invalid.beginCreate(), /product-capability-policy-invalid/);
});

test('bootstrap without an active session uses complete catalog defaults', () => {
  const assembly = createValidationAssembly({ catalog });

  assert.deepEqual(assembly.snapshot().draft, {
    validation_rule_id: 'rule14',
    scenario_id: 'head_on',
    algorithm_id: 'nominal',
    tracker_id: 'god',
    seed: 0,
    episode_index: 0,
    dt: null,
    t_end: null,
    strict_no_fallback: true,
    evaluator_profile_id: 'ccta_2023_demo-v1',
    algorithm_config: {},
    tracker_config: {},
    scenario_override: null,
  });
  assert.equal(assembly.snapshot().dirty, false);
  assert.equal(assembly.snapshot().classification, 'verified');
  assert.equal(assembly.snapshot().valid, true);
});

test('active Run Specification becomes the draft and Default clears all overrides', () => {
  const activeSession = {
    state: 'PAUSED',
    spec: {
      validation_rule_id: 'rule13',
      scenario_id: 'overtaking',
      algorithm_id: 'vo',
      tracker_id: 'god',
      seed: 17,
      episode_index: 2,
      dt: 0.25,
      t_end: 480,
      strict_no_fallback: true,
      evaluator_profile_id: 'ccta_2023_demo-v1',
      algorithm_config: { horizon: 21, nested: { weight: 4 } },
      tracker_config: { gate: 7 },
      scenario_override: { name: 'attached' },
    },
  };
  const assembly = createValidationAssembly({ catalog, activeSession });

  assert.deepEqual(assembly.snapshot().draft.algorithm_config, activeSession.spec.algorithm_config);
  assert.equal(assembly.snapshot().dirty, false);

  assembly.edit('seed', 18);
  assert.equal(assembly.snapshot().dirty, true);
  assert.deepEqual(assembly.snapshot().draft.algorithm_config, activeSession.spec.algorithm_config);
  assert.deepEqual(assembly.snapshot().draft.tracker_config, activeSession.spec.tracker_config);

  assembly.resetDefault();
  const reset = assembly.snapshot();
  assert.equal(reset.draft.validation_rule_id, 'rule14');
  assert.equal(reset.draft.scenario_id, 'head_on');
  assert.equal(reset.draft.seed, 0);
  assert.equal(reset.draft.episode_index, 0);
  assert.equal(reset.draft.dt, null);
  assert.equal(reset.draft.t_end, null);
  assert.deepEqual(reset.draft.algorithm_config, {});
  assert.deepEqual(reset.draft.tracker_config, {});
  assert.equal(reset.draft.scenario_override, null);
  assert.deepEqual(activeSession.spec.algorithm_config, { horizon: 21, nested: { weight: 4 } });
});

test('rule selection repairs only its dependent scenario and keeps algorithm plus tracker', () => {
  const rankingCatalog = structuredClone(catalog);
  rankingCatalog.rules.push({ id: 'rule15', selectable: true });
  rankingCatalog.scenarios.push(
    { id: 'crossing_give_way', name: 'Give-way', dt: 0.1, t_end: 600, selectable: true },
    { id: 'crossing_stand_on', name: 'Stand-on', dt: 0.1, t_end: 600, selectable: true },
  );
  rankingCatalog.verified_combinations = [
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'nominal', tracker_id: 'god' },
    { validation_rule_id: 'rule15', scenario_id: 'crossing_give_way', algorithm_id: 'nominal', tracker_id: 'god' },
    { validation_rule_id: 'rule15', scenario_id: 'crossing_stand_on', algorithm_id: 'nominal', tracker_id: 'god' },
  ];
  rankingCatalog.experimental_combinations = [];
  rankingCatalog.selectable_combinations = [...rankingCatalog.verified_combinations];
  const assembly = createValidationAssembly({ catalog: rankingCatalog });

  assembly.edit('validation_rule_id', 'rule15');
  assert.deepEqual(
    Object.fromEntries(Object.entries(assembly.snapshot().draft).filter(([key]) => [
      'validation_rule_id', 'scenario_id', 'algorithm_id', 'tracker_id',
    ].includes(key))),
    { validation_rule_id: 'rule15', scenario_id: 'crossing_give_way', algorithm_id: 'nominal', tracker_id: 'god' },
  );
  assert.ok(assembly.snapshot().notices.some((notice) => /repaired/i.test(notice.message)));
});

test('tuple options never repair a sibling algorithm or tracker behind the user', () => {
  const coupledCatalog = structuredClone(catalog);
  coupledCatalog.defaults = {
    validation_rule_id: 'rule14',
    scenario_id: 'head_on',
    algorithm_id: 'vo',
    tracker_id: 'god',
  };
  coupledCatalog.product_capability_policy.default_algorithm_id = 'vo';
  coupledCatalog.verified_combinations = [
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'god' },
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'nominal', tracker_id: 'kf' },
  ];
  coupledCatalog.experimental_combinations = [];
  coupledCatalog.selectable_combinations = [...coupledCatalog.verified_combinations];
  const assembly = createValidationAssembly({ catalog: coupledCatalog });

  assert.equal(assembly.snapshot().options.tracker_id.find((item) => item.id === 'kf').enabled, false);
  assembly.edit('tracker_id', 'kf');
  assert.equal(assembly.snapshot().draft.algorithm_id, 'vo');
  assert.equal(assembly.snapshot().draft.tracker_id, 'god');
});

test('scenario changes clear scenario-specific contracts and clock overrides', () => {
  const activeSession = {
    state: 'PAUSED',
    spec: {
      ...catalog.defaults,
      seed: 0,
      episode_index: 0,
      dt: 1,
      t_end: 700,
      strict_no_fallback: true,
      evaluator_profile_id: 'ccta_2023_demo-v1',
      algorithm_config: { private_algorithm_key: 3 },
      tracker_config: { private_tracker_key: 4 },
      scenario_override: { name: 'future-scenario-attachment' },
    },
  };
  const assembly = createValidationAssembly({ catalog, activeSession });

  assembly.edit('algorithm_id', 'vo');
  assert.deepEqual(assembly.snapshot().draft.algorithm_config, {});
  assert.deepEqual(assembly.snapshot().draft.tracker_config, { private_tracker_key: 4 });
  assert.deepEqual(assembly.snapshot().draft.scenario_override, { name: 'future-scenario-attachment' });

  assembly.edit('tracker_id', 'kf');
  assert.deepEqual(assembly.snapshot().draft.tracker_config, {});

  assembly.edit('scenario_id', 'busy');
  assert.equal(assembly.snapshot().draft.scenario_override, null);
  assert.equal(assembly.snapshot().draft.dt, null);
  assert.equal(assembly.snapshot().draft.t_end, null);
  assert.ok(assembly.snapshot().notices.some((notice) => /override/i.test(notice.message)));
});

test('classification controls confirmation, active matching, and RUNNING replacement block', () => {
  const experimental = createValidationAssembly({ catalog });
  experimental.edit('algorithm_id', 'vo');
  experimental.edit('tracker_id', 'kf');
  experimental.edit('scenario_id', 'busy');
  assert.equal(experimental.snapshot().classification, 'experimental');
  assert.equal(experimental.snapshot().canCreate, false);
  assert.equal(experimental.snapshot().createBlock, 'experimental-confirmation');
  assert.throws(() => experimental.beginCreate(), /confirmation/i);
  const confirmed = experimental.beginCreate({ confirmedExperimental: true });
  experimental.rejectCreate(confirmed.token, new Error('cancel test'));

  const matching = createValidationAssembly({
    catalog,
    activeSession: { state: 'CREATED', spec: { ...catalog.defaults } },
  });
  assert.equal(matching.snapshot().matchesActive, true);
  assert.equal(matching.snapshot().canCreate, false);
  assert.equal(matching.snapshot().createBlock, 'matches-active');

  const running = createValidationAssembly({
    catalog,
    activeSession: { state: 'RUNNING', spec: { ...catalog.defaults } },
  });
  running.edit('algorithm_id', 'vo');
  assert.equal(running.snapshot().createBlock, 'active-running');
  assert.throws(() => running.beginCreate(), /running/i);
});

test('create freezes one immutable snapshot and ignores stale completion tokens', () => {
  const assembly = createValidationAssembly({ catalog });
  assembly.edit('algorithm_id', 'vo');
  assembly.edit('seed', 41);
  const pending = assembly.beginCreate();

  assert.equal(assembly.snapshot().creating, true);
  assert.equal(Object.isFrozen(pending.spec), true);
  assert.throws(() => assembly.edit('seed', 42), /creating/i);
  assert.throws(() => assembly.resetDefault(), /creating/i);
  assert.equal(pending.spec.seed, 41);
  assert.equal(assembly.resolveCreate('stale-token', { state: 'CREATED' }), false);
  assert.equal(assembly.snapshot().creating, true);

  assert.equal(assembly.resolveCreate(pending.token, { state: 'CREATED' }), true);
  assert.equal(assembly.snapshot().creating, false);
  assert.equal(assembly.snapshot().dirty, false);
  assert.equal(assembly.snapshot().draft.seed, 41);
  assert.equal(assembly.snapshot().activeState, 'CREATED');
});

test('strict no-fallback is immutable through the public draft interface', () => {
  const assembly = createValidationAssembly({ catalog });

  assert.throws(() => assembly.edit('strict_no_fallback', false), /strict_no_fallback/i);
  assert.equal(assembly.snapshot().draft.strict_no_fallback, true);
});

test('public edit accepts only tuple fields and four user-editable parameters', () => {
  const assembly = createValidationAssembly({ catalog });
  for (const field of ['algorithm_config', 'tracker_config', 'scenario_override', 'evaluator_profile_id', 'strict_no_fallback']) {
    assert.throws(() => assembly.edit(field, {}), /not user-editable/i);
  }

  for (const [field, value] of [
    ['validation_rule_id', 'rule13'],
    ['scenario_id', 'overtaking'],
    ['algorithm_id', 'vo'],
    ['tracker_id', 'god'],
    ['seed', 3],
    ['episode_index', 1],
    ['dt', 0.2],
    ['t_end', 400],
  ]) {
    assert.doesNotThrow(() => assembly.edit(field, value));
  }
});

test('catalog failure leaves Active Spec read-only and replacement repairs stale tuple without retrying', () => {
  const activeSession = {
    state: 'PAUSED',
    spec: {
      validation_rule_id: 'rule14',
      scenario_id: 'head_on',
      algorithm_id: 'vo',
      tracker_id: 'god',
      seed: 3,
      strict_no_fallback: true,
      algorithm_config: { keep: true },
    },
  };
  const assembly = createValidationAssembly({
    catalog: null,
    activeSession,
    catalogError: new Error('catalog offline'),
  });

  assert.equal(assembly.snapshot().catalogStatus, 'error');
  assert.equal(assembly.snapshot().readOnly, true);
  assert.equal(assembly.snapshot().draft.algorithm_config.keep, true);
  assert.throws(() => assembly.edit('seed', 4), /catalog/i);
  assert.throws(() => assembly.beginCreate(), /catalog/i);

  const refreshed = structuredClone(catalog);
  refreshed.verified_combinations = [
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'nominal', tracker_id: 'god' },
  ];
  refreshed.experimental_combinations = [];
  refreshed.selectable_combinations = [...refreshed.verified_combinations];
  assembly.replaceCatalog(refreshed, { reason: 'stale-capability-rejection' });
  const repaired = assembly.snapshot();
  assert.equal(repaired.catalogStatus, 'ready');
  assert.equal(repaired.draft.algorithm_id, 'nominal');
  assert.equal(repaired.draft.seed, 3);
  assert.ok(repaired.notices.some((notice) => /catalog refreshed/i.test(notice.message)));
  assert.equal(repaired.creating, false);
});

test('snapshot exposes catalog-backed disabled options and scenario-default clock sources', () => {
  const withUnavailable = structuredClone(catalog);
  withUnavailable.algorithms.push({ id: 'rlmpc', selectable: false, known_failure: 'solver unavailable' });
  withUnavailable.product_capability_policy.algorithm_ids.push('rlmpc');
  withUnavailable.product_capability_policy.constraints.algorithms.rlmpc = { requires_domain_profile: false };
  const assembly = createValidationAssembly({ catalog: withUnavailable });

  let snapshot = assembly.snapshot();
  assert.equal(snapshot.options.algorithm_id.find((item) => item.id === 'rlmpc').enabled, false);
  assert.deepEqual(snapshot.executionPlan.dt, { source: 'scenario-default', requested: null, effective: 0.1 });
  assert.deepEqual(snapshot.executionPlan.t_end, { source: 'scenario-default', requested: null, effective: 600 });

  assembly.edit('dt', 0.5);
  assembly.edit('t_end', 120);
  snapshot = assembly.snapshot();
  assert.deepEqual(snapshot.executionPlan.dt, { source: 'explicit-override', requested: 0.5, effective: 0.5 });
  assert.deepEqual(snapshot.executionPlan.t_end, { source: 'explicit-override', requested: 120, effective: 120 });
});

test('invalid editable params remain visible but cannot produce a create snapshot', () => {
  const assembly = createValidationAssembly({ catalog });
  assembly.edit('seed', -1);
  assembly.edit('dt', 0);

  assert.equal(assembly.snapshot().valid, false);
  assert.deepEqual(assembly.snapshot().validationErrors, {
    seed: 'Seed must be a non-negative integer.',
    dt: 'dt must be null or greater than zero.',
  });
  assert.equal(assembly.snapshot().createBlock, 'invalid-draft');
  assert.throws(() => assembly.beginCreate(), /invalid/i);
});

test('catalog reload failure discards stale catalog truth and keeps the draft read-only', () => {
  const assembly = createValidationAssembly({ catalog });
  assembly.edit('algorithm_id', 'vo');

  assembly.markCatalogFailure(new Error('reload unavailable'));
  const failed = assembly.snapshot();
  assert.equal(failed.catalogStatus, 'error');
  assert.equal(failed.readOnly, true);
  assert.equal(failed.draft.algorithm_id, 'vo');
  assert.ok(failed.notices.some((notice) => /reload unavailable/.test(notice.message)));
});

test('unknown current-session authority blocks editing and Create until explicitly refreshed', () => {
  const assembly = createValidationAssembly({
    catalog,
    currentSessionStatus: 'unknown',
    currentSessionError: new Error('current endpoint failed'),
  });

  assert.equal(assembly.snapshot().sessionStatus, 'unknown');
  assert.equal(assembly.snapshot().readOnly, true);
  assert.equal(assembly.snapshot().createBlock, 'current-session-unknown');
  assert.throws(() => assembly.edit('seed', 7), /session authority/i);
  assert.throws(() => assembly.beginCreate(), /session authority/i);

  assembly.syncActiveSession(null, { reason: 'manual-retry' });
  assert.equal(assembly.snapshot().sessionStatus, 'known');
  assert.equal(assembly.snapshot().readOnly, false);
});

test('loading authority exposes a safe empty read-only snapshot', () => {
  const assembly = createValidationAssembly({
    catalog: null,
    currentSessionStatus: 'loading',
  });

  assert.deepEqual(assembly.snapshot().validationErrors, {});
  assert.equal(assembly.snapshot().draft, null);
  assert.equal(assembly.snapshot().createBlock, 'current-session-loading');
});

test('authority refresh loading locks a dirty draft until known authority returns', () => {
  const assembly = createValidationAssembly({ catalog });
  assembly.edit('seed', 8);

  assembly.markCurrentSessionLoading();
  assert.equal(assembly.snapshot().sessionStatus, 'loading');
  assert.equal(assembly.snapshot().readOnly, true);
  assert.equal(assembly.snapshot().createBlock, 'current-session-loading');
  assert.equal(assembly.snapshot().draft.seed, 8);
  assert.equal(assembly.snapshot().dirty, true);

  assembly.syncActiveSession(null, { reason: 'refresh-complete' });
  assert.equal(assembly.snapshot().sessionStatus, 'known');
  assert.equal(assembly.snapshot().readOnly, false);
  assert.equal(assembly.snapshot().draft.seed, 8);
});

test('a runtime command in flight locks all Validation Assembly mutations', () => {
  const assembly = createValidationAssembly({ catalog });
  assembly.edit('seed', 9);

  assembly.setRuntimePending('reset');
  assert.equal(assembly.snapshot().readOnly, true);
  assert.equal(assembly.snapshot().createBlock, 'runtime-pending');
  assert.throws(() => assembly.edit('seed', 10), /reset.*progress/i);
  assert.throws(() => assembly.resetDefault(), /reset.*progress/i);
  assert.throws(() => assembly.beginCreate(), /reset.*progress/i);

  assembly.setRuntimePending(null);
  assert.equal(assembly.snapshot().readOnly, false);
  assert.equal(assembly.snapshot().draft.seed, 9);
  assert.equal(assembly.snapshot().createBlock, null);
});

test('full Active Session sync replaces a clean draft but preserves and marks a dirty draft', () => {
  const first = {
    state: 'PAUSED',
    spec: { ...catalog.defaults, seed: 1, algorithm_config: { active: 'first' } },
  };
  const replacement = {
    state: 'CREATED',
    spec: {
      ...catalog.defaults,
      algorithm_id: 'vo',
      seed: 2,
      algorithm_config: { active: 'replacement' },
    },
  };

  const clean = createValidationAssembly({ catalog, activeSession: first });
  clean.syncActiveSession(replacement, { reason: 'recovery' });
  assert.equal(clean.snapshot().draft.algorithm_id, 'vo');
  assert.equal(clean.snapshot().draft.seed, 2);
  assert.deepEqual(clean.snapshot().draft.algorithm_config, { active: 'replacement' });
  assert.equal(clean.snapshot().dirty, false);

  const dirty = createValidationAssembly({ catalog, activeSession: first });
  dirty.edit('seed', 99);
  dirty.syncActiveSession(replacement, { reason: 'external-replacement' });
  assert.equal(dirty.snapshot().draft.seed, 99);
  assert.equal(dirty.snapshot().draft.algorithm_id, 'nominal');
  assert.equal(dirty.snapshot().activeSpec.algorithm_id, 'vo');
  assert.equal(dirty.snapshot().dirty, true);
  assert.ok(dirty.snapshot().notices.some((notice) => /active session changed/i.test(notice.message)));
});

test('selectable combinations are final eligibility and metadata readiness is a safety intersection', () => {
  const inconsistent = structuredClone(catalog);
  inconsistent.selectable_combinations = [
    { validation_rule_id: 'rule14', scenario_id: 'head_on', algorithm_id: 'vo', tracker_id: 'god' },
  ];
  const verifiedOnly = createValidationAssembly({ catalog: inconsistent });
  assert.equal(verifiedOnly.snapshot().classification, 'unavailable');
  assert.equal(verifiedOnly.snapshot().valid, false);

  inconsistent.defaults.algorithm_id = 'vo';
  inconsistent.algorithms.find((item) => item.id === 'vo').runtime_ready = false;
  const notRuntimeReady = createValidationAssembly({ catalog: inconsistent });
  assert.equal(notRuntimeReady.snapshot().classification, 'unavailable');
  assert.equal(notRuntimeReady.snapshot().options.algorithm_id.find((item) => item.id === 'vo').enabled, false);
});
