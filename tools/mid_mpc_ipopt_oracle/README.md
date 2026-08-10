# Frozen Mid-MPC IPOPT oracle

This exporter compiles the frozen MASS-L3 C++ IPOPT path directly and emits a
JSONL corpus. It does not compile or call ROS2, M4/M6/M7, the node, acados, or
fallback orchestration.

## Reproduce

Create a detached MASS-L3 worktree at the frozen commit, then run:

```sh
git -C "/path/to/MASS-L3-Tactical Layer" worktree add --detach \
  "/path/to/MASS-L3-Tactical Layer/.worktrees/mid-mpc-parity-oracle-frozen" \
  ced58f8576f3772ef7c1bc72bb0f8b0368688b5a

sh tools/mid_mpc_ipopt_oracle/export_oracle.sh \
  "/path/to/MASS-L3-Tactical Layer/.worktrees/mid-mpc-parity-oracle-frozen" \
  /tmp/mid_mpc_ipopt_v1.jsonl
```

The script refuses any other MASS-L3 commit. Build output stays under `$TMPDIR`.
It compiles these frozen files without copying them into Colav-Simulator:

- `mid_mpc_nlp_formulation.cpp`
- `mid_mpc_solver.cpp`
- `constraint_compiler.cpp`

`compat_include` supplies only the optimizer-facing data shapes and no-op
logging needed to compile those files without ROS2. The build mechanically adds
two read-only trace calls to a temporary copy of `mid_mpc_solver.cpp`, immediately
before and after its existing `nlpsol` call. This exposes prepared arrays and raw
results without changing the frozen source or production API.

`oracle_main.cpp` constructs every input, calls the public frozen solver, and
exports `p/x0/lbx/ubx/lbg/ubg`, raw `x/f/g`, row layout, both slacks, public
status/trajectory, and continuous-CPA diagnostics.

## Dependency and provenance boundary

The checked-in record was generated on arm64 macOS with CasADi 3.7.2 and its
bundled Ipopt 3.14.11. Both versions are serialized in the record. MASS-L3 pins
CasADi 3.7.2 and Ipopt 3.14.19; reproducing against that exact Ipopt build is a
separate dependency-build task. Numerical tolerances, not byte equality, are
therefore the comparison contract.

CasADi is LGPL-3.0 and Ipopt is EPL-2.0. The frozen MASS-L3 tree has no root
license granting redistribution; this repository links to and compiles a
separately checked-out tree instead of copying the algorithm source.

## Corpus

The corpus covers cold target-free tracking, head-on and crossing starboard
give-way, stand-on/HOLD row disabling, port-preference overtaking, forced
non-zero CPA slack, committed prefix `K=2`, and two-target CPA row ordering.
