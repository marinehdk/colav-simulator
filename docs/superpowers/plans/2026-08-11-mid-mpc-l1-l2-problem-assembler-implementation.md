# Mid-MPC L1/L2 Problem Assembler Implementation Plan

> **Base**: `marine/main@b94148c`
> **Branch**: `codex/mid-mpc-l1-l2-assembler`
> **Method**: `implement` + `tdd`, vertical slices only
> **Review fixed point**: `b94148c`

## Confirmed Test Seams

1. `MidMpcProblemAssembler.assemble(request)->AssemblyOutcome`.
2. `MidMpcIpoptSolver.solve(problem)->MidMpcResult`.
3. `CustomMPCAdapter.plan(PlannerInput)->MPCSolution`.
4. `P1RunHarness` and real 8010 planner event.

These seams were accepted through CARD-01..03 and the solution package. Tests must not bind private stages or numerical offsets.

## Vertical Slices

### Slice 1: Atomic Request/Outcome

- RED: valid Candidate 2 snapshot returns immutable success with identity/problem hash; mismatched cycle returns typed failure and no partial problem.
- GREEN: add request, success/failure and stateless Assembler facade around migrated bridge logic.
- Verify: focused assembler contract tests, Ruff.
- Commit intent: `feat: establish atomic Mid-MPC assembly contract`.

### Slice 2: Deterministic Binding and Prediction

- RED: input permutation produces identical slots/hash; required target missing or >16 fails; prediction has 81 points at 0..1200s.
- GREEN: canonical TrackKey binding, required/eligible admission, CV prediction bundle and profile hash.
- Verify: assembler tests plus existing Candidate 2 contract tests.
- Commit intent: `feat: make target assembly deterministic and replayable`.

### Slice 3: Safety and Activation Semantics

- RED: node floor uses target one-step displacement, not own max speed; schedule evidence is physical-time typed; first swept segment remains externally checkable.
- GREEN: safety plan and activation plan; remove `TCPA/dt-2` and own-step bridge formula.
- Verify: worked geometry literals, mirrored OT/HO/CS public-seam fixtures.
- Commit intent: `fix: compile physical Mid-MPC safety semantics`.

### Slice 4: Profile and Private Numerical Preparation

- RED: parity profile still matches all eight records; strict profile fixes CPA/direction slack bounds to zero without changing layout identity.
- GREEN: explicit profile enum, named preparation semantics, one private numerical layout authority.
- Verify: parity suite, strict bounds diagnostics, no expected fixture edits.
- Commit intent: `feat: separate Mid-MPC parity and strict profiles`.

### Slice 5: Failure and Evidence Chain

- RED: expected assembly failures survive Adapter/HTTP as typed details; compact evidence is finite JSON and hash-linked; full artifact round-trips gzip/hash.
- GREEN: failure mapping, versioned assembly namespace, artifact writer and typed render projection.
- Verify: adapter tests, web API tests, ≤8KiB gate, artifact tamper test.
- Commit intent: `feat: publish replayable Mid-MPC assembly evidence`.

### Slice 6: Closed Loop and Runtime

- RED/GREEN only for defects found at public seams; do not add scenario-ID branches or reduce thresholds.
- Run HO, CS-GW, CS-SO, OT starboard, OT port, overtaken/Rule17 and multiship.
- Prove real IPOPT, no fallback, Ship0 hull clearance≥50m, correct side/commit/recovery.
- Start candidate backend on 8011 first; after merge-ready evidence, validate fixed 8010 without overwriting dirty main checkout.
- Commit intent: `test: close Mid-MPC assembler runtime evidence`.

### Slice 7: Regression and Review

- Run scoped Ruff, format check, `git diff --check`, full pytest.
- Commit all intentional work to current branch.
- Run `code-review` twice in parallel: Standards and Spec, fixed point `b94148c`.
- Resolve high/medium findings with new RED/GREEN slices; rerun affected gates.
- Push branch and publish final evidence to the originating issue.

## Acceptance Commands

```bash
uv run pytest tests/test_mid_mpc_problem_assembler.py -q
uv run pytest tests/test_mid_mpc_ipopt_core.py tests/test_mid_mpc_parity_fixtures.py -q
uv run pytest tests/test_mid_mpc_ipopt_integration.py -q
uv run pytest tests/test_mid_mpc_single_encounter.py tests/test_mid_mpc_multiship_runtime.py -q
uv run ruff check <changed-python-files>
uv run ruff format --check <changed-python-files>
git diff --check
uv run pytest -q
```

## Stop Conditions

- Any oracle expected-value change.
- Candidate 2 lifecycle behavior must be duplicated or altered to make assembly pass.
- Strict profile requires graph topology change rather than bounds-only semantics.
- HO/CS/OT requires scenario-ID logic, fallback or reduced 50m gate.
- Full target/GNC facts needed but absent; record capability limitation instead of fabricating data.
