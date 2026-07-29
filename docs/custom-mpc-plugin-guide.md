# Custom MPC Plugin Guide

## Minimal Package

```text
my_mpc/
  plugin.py
  algorithm.py
  config.yaml
  requirements.lock
```

P2 executes plugins in-process. Native libraries that may abort, require an
incompatible ABI, or need an isolated environment must wait for the P5 Worker.

## Factory

Expose one `module:callable`. The callable receives a platform-owned
`FactoryContext` and returns `CustomMPCAdapter`.

```python
from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    CustomMPCAdapter,
    ExecutionProfile,
    FactoryContext,
    MPCSolution,
    PlannerInput,
)


def create(*, context: FactoryContext, config_path: str) -> CustomMPCAdapter:
    solver = MyPaperMPC.from_yaml(config_path, seed=context.algorithm_seed)
    descriptor = AlgorithmDescriptor(
        algorithm_id=context.requested_algorithm,
        version="paper-implementation-sha",
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="documented-model-name",
        horizon_dt=1.0,
        horizon_steps=31,
        objective_terms=("tracking", "collision", "control_effort"),
        constraint_terms=("dynamics", "actuator", "collision"),
        solver="ipopt",
        seed_policy="seeded",
        execution_profile=ExecutionProfile(
            solve_period_s=5.0,
            deadline_s=5.0,
            requires_enc=False,
        ),
    )
    return CustomMPCAdapter(
        descriptor=descriptor,
        solve=solver.solve,
        reset=solver.reset,
        context=context,
    )
```

`solve(PlannerInput) -> MPCSolution` is the only algorithm callback. Do not
subclass Simulator, call `Simulator.step()`, or return another planner as a
fallback.

## Coordinate Contract

- local position: ENU metres;
- ownship: `[x,y,psi,u,v,r]`;
- target track: `[x,y,Vx,Vy]` plus `4x4` covariance;
- angles: radians;
- trajectory: `9xN=[x,y,psi,u,v,r,x_ddot,y_ddot,psi_dot]`;
- trajectory column 0: solve-time ownship state;
- `control_reference`: finite `9x1`;
- full Custom G3 requires `N>=2`.

Invalid input, infeasible solve, numerical failure, timeout, and missing
dependencies must remain distinct. Formal runs forbid fallback.
`deadline_mode=OFF` is diagnostic-only and cannot pass the Custom G3 gate.

## Algorithm Config

```yaml
factory: my_mpc.plugin:create
dependency_lock: ./requirements.lock
kwargs:
  config_path: ./paper_config.yaml
```

Paths to `dependency_lock` are resolved relative to this YAML file.

## Conformance

```bash
uv run colav-sim plugin-check \
  --algorithm my_paper_mpc \
  --algorithm-config path/to/plugin.yaml
```

Expected JSON:

- status `SUCCESS`;
- `fallback_used=false`;
- complete build identity;
- `control_reference_shape=[9,1]`;
- prediction shape matching Descriptor;
- `solve_id=1`.

Contract failures also return JSON with a non-zero exit code, normalized
`status`, and non-empty `reasons`.

## Scenario Smoke

```bash
uv run colav-sim run \
  --scenario head_on \
  --algorithm my_paper_mpc \
  --tracker god \
  --seed 0 \
  --algorithm-config path/to/plugin.yaml
```

Passing one smoke is not Phase 2 qualification. Promotion requires raw evidence
for head-on, both overtaking roles, both crossing roles, and multi-ship, with
the exact nominal comparison tuple and footprint collision oracle.
