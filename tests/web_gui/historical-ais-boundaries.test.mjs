import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { createHistoricalAISController } from '../../web_gui/modules/historical-ais-controller.js';
import { projectHistoricalAISScenario } from '../../web_gui/modules/historical-ais-projection.js';

const descriptor = JSON.parse(await readFile(
  new URL('../../colav_simulator/data/historical_ais_scenarios.json', import.meta.url),
  'utf8',
));
const canonicalDescriptor = {
  ...descriptor,
  id: descriptor.scenario_id,
  descriptor_sha256: 'b'.repeat(64),
  readiness: { status: 'SOURCE_BINDING_MISSING' },
  presentation: {
    schema_version: 'historical-ais-scenario.presentation.v1',
    scenario: { id: descriptor.scenario_id, kind: 'HISTORICAL_AIS' },
    operability: { status: 'UNAVAILABLE', scope: 'BOUNDED' },
    qualification: {
      status: 'NOT_READY',
      source_readiness: 'SOURCE_BINDING_MISSING',
      limitations: descriptor.limitations,
    },
    runtime: {
      modes: descriptor.modes,
      historical_scenario_id: descriptor.scenario_id,
      algorithm_id: 'mid_mpc_ipopt',
      tracker_id: 'god',
      algorithm_capability_evidence: descriptor.algorithm_capability_evidence,
    },
    digests: {
      descriptor_sha256: 'b'.repeat(64),
      archive_sha256: descriptor.archive_scope.archive_sha256,
      entry_sha256: descriptor.current_window.entry_sha256,
      selection_sha256: descriptor.current_window.expected_selection_sha256,
      enc_profile_sha256: descriptor.enc.profile_digest,
    },
  },
};
const workbenchSource = await readFile(
  new URL('../../web_gui/modules/historical-ais-workbench.js', import.meta.url),
  'utf8',
);

test('scenario projection accepts only the canonical versioned descriptor', () => {
  const available = projectHistoricalAISScenario(canonicalDescriptor);

  assert.equal(available.status, 'AVAILABLE');
  assert.equal(available.identity, 'HISTORICAL_AIS');
  assert.deepEqual(available.operability, { status: 'UNAVAILABLE', scope: 'BOUNDED' });
  assert.equal(available.scenarioId, 'hais_romsdal_20260701_120000_120100');
  assert.equal(available.source.archiveRows, 51_522_509);
  assert.equal(available.selection.runtimeActorCount, 3);
  assert.equal(available.digests.archive, canonicalDescriptor.presentation.digests.archive_sha256);
  assert.equal(available.digests.entry, canonicalDescriptor.presentation.digests.entry_sha256);
  assert.equal(available.digests.selection, canonicalDescriptor.presentation.digests.selection_sha256);
  assert.equal(available.digests.descriptor, canonicalDescriptor.descriptor_sha256);

  const invalidAliasShape = projectHistoricalAISScenario({
    id: descriptor.scenario_id,
    source: descriptor.archive_scope,
    selection: descriptor.current_window,
  });
  assert.equal(invalidAliasShape.status, 'UNAVAILABLE');
  assert.equal(invalidAliasShape.error.code, 'INVALID_SCENARIO_DESCRIPTOR');
  assert.equal(invalidAliasShape.scenarioId, null);
  assert.equal(invalidAliasShape.source, null);
  assert.equal(invalidAliasShape.selection, null);
});

test('catalog failure produces typed ERROR without a fabricated scenario', async () => {
  const states = [];
  const controller = createHistoricalAISController({
    api: {
      async listScenarios() { throw new Error('catalog offline'); },
    },
    render: state => states.push(structuredClone(state)),
  });

  await controller.load();

  const final = states.at(-1);
  assert.equal(final.catalog.status, 'ERROR');
  assert.equal(final.catalog.error.code, 'CATALOG_UNAVAILABLE');
  assert.deepEqual(final.scenarios, []);
  assert.equal(final.detail.status, 'UNAVAILABLE');
  assert.equal(final.scenario, null);
  assert.doesNotMatch(workbenchSource, /DEFAULT_HISTORICAL_AIS_SCENARIO/);
});

test('detail failure clears scene facts and exposes typed ERROR', async () => {
  const states = [];
  const controller = createHistoricalAISController({
    api: {
      async listScenarios() {
        return [{ ...canonicalDescriptor, readiness: { status: 'READY' } }];
      },
      async getScenario() { throw new Error('detail unavailable'); },
    },
    render: state => states.push(structuredClone(state)),
  });

  await controller.load();

  const final = states.at(-1);
  assert.equal(final.catalog.status, 'READY');
  assert.equal(final.detail.status, 'ERROR');
  assert.equal(final.detail.error.code, 'DETAIL_UNAVAILABLE');
  assert.equal(final.scenario, null);
  assert.equal(final.scenarios.length, 1);
});
