# Historical AIS Scene in the Product Catalog

> **Status**: accepted (2026-08-25)

The canonical Historical AIS scene (`hais_romsdal_20260701_120000_120100`) enters
the product scenario catalog and the ordinary Config → Deployment flow. This
revises the 2026-08-21 spec's "independent catalog only" clause; the threat
authority ADRs 0001–0003 are untouched.

## Decision

- The scene is listed through the merged scenario catalog seam
  (`ExperimentRunner.list_scenarios` + `CapabilityCatalog`) with Counterfactual-only
  **EXPERIMENTAL** tuples: `multiship × hais × {vo, potocnik_colreg_fan_mpc, mid_mpc_ipopt} × god`.
  It never appears in `verified_combinations`; verified-tuple evidence stays on
  the paper scene via the descriptor's `ALGORITHM_CAPABILITY_ONLY` cross-scene
  receipt (no geometry-equivalence claim).
- `POST /api/sessions` with the hais scenario binds the scene through
  `HistoricalAISSceneAssembler.bind_counterfactual` and creates an ordinary
  **Active Session** (`WebSessionManager`): normal tick loop, normal telemetry
  envelope on `/ws/sessions/{id}`, normal Deployment playback controls. The
  selected product algorithm takes over ownship at T0 (Counterfactual semantics);
  there is no pure-replay product selection.
- The scene assembler accepts an `algorithm_id` override for Counterfactual
  binding; `HISTORICAL_REPLAY` stays sealed to `nominal`/`god` and reachable only
  through `prepare_internal` with a typed `InternalExecutionPurpose`.
- Archive content identity remains fail-closed at binding time (content-addressed
  dataset/dimension/ENC checks). Catalog listing uses only a cheap source-presence
  check, so `list_scenarios` does not hash the archive.
- The Historical Workflow authority (headless double-run qualification,
  determinism, Compare, `NOT_QUALIFIED` evidence) is unchanged and remains the
  only source of benchmark evidence. An interactive Deployment session is not
  benchmark evidence.

## Consequences

- Config Step 02 offers the AIS scene under the `multiship` rule; Deployment
  plays it like any scenario with zero frontend telemetry changes.
- `tests/test_historical_ais_scene_guard.py` now freezes the merged-catalog
  boundary instead of the separation boundary.
- Product Capability Policy is unchanged: same algorithms, same tracker,
  Experimental classification until predictive qualification succeeds.
