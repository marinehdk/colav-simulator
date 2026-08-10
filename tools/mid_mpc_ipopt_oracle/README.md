# Frozen Mid-MPC IPOPT oracle

This exporter compiles the frozen MASS-L3 C++ IPOPT path directly and emits one
JSONL record. It does not compile or call ROS2, M4/M6/M7, the node, acados, or
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
logging needed to compile those files without ROS2. `oracle_main.cpp` constructs
the target-free input, calls the public frozen solver, and exports public solver
status, trajectory, objective reconstructed from public output, and diagnostics.

## Dependency and provenance boundary

The checked-in record was generated on arm64 macOS with CasADi 3.7.2 and its
bundled Ipopt 3.14.11. Both versions are serialized in the record. MASS-L3 pins
CasADi 3.7.2 and Ipopt 3.14.19; reproducing against that exact Ipopt build is a
separate dependency-build task. Numerical tolerances, not byte equality, are
therefore the comparison contract.

CasADi is LGPL-3.0 and Ipopt is EPL-2.0. The frozen MASS-L3 tree has no root
license granting redistribution; this repository links to and compiles a
separately checked-out tree instead of copying the algorithm source.

## Deferred corpus

This first vertical slice freezes cold target-free route/speed tracking. Target
CPA, COLREG direction, stand-on/HOLD, overtaking, non-zero slack, committed
prefix, and multi-target row-order fixtures remain deferred until the Python
reference consumes this first record.
