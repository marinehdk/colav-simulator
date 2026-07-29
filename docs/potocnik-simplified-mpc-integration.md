# Potočnik Simplified MPC Integration

## Scope and identity

This integration is a functional Python port of the simplified MPC in
Potočnik (2025), Equations (13)-(17), and the reference MATLAB implementation:

- paper: *Model Predictive Control for Autonomous Ship Navigation with COLREG
  Compliance and Chart-Based Path Planning*, JMSE 13(7):1246;
- repository: <https://github.com/ppotoc/MPC-Autonomous-Ship-Navigation>;
- audited source commit:
  `3683e92f9949cf884540d40a7ce096c3785273b3`;
- license: MIT; see `THIRD_PARTY_NOTICES.md`.

The stable Playground ID is `potocnik_simplified_mpc`. It loads only through
the Phase 2 `module:factory -> CustomMPCAdapter(ICOLAV)` path.

This is a functional algorithm reproduction, not a numerical reproduction of
the paper figures. It does not claim to implement the general nonlinear
optimization stated in Equation (12).

## Ported algorithm

Each solve:

1. generates 45 deterministic fan trajectories;
2. applies a first-step heading increment in `[-20, +20] deg`;
3. multiplies that increment by `0.95` at each of 16 prediction steps;
4. predicts every target with constant velocity;
5. rejects a candidate when any synchronous predicted separation is below the
   configured collision distance;
6. selects the feasible candidate whose first heading is closest to the next
   waypoint, or whose terminal point is closest when the waypoint is behind;
7. returns the first selected course and current speed.

No feasible candidate produces `INFEASIBLE`. No nominal, VO, SB-MPC, or
previous-plan fallback exists.

## Coordinate and trajectory mapping

The MATLAB implementation propagates latitude/longitude with a relative
per-iteration speed. The port receives the platform contract directly:

| Paper/source value | Playground value |
|---|---|
| latitude/longitude | north/east ENU metres |
| `theta` | `psi`, radians |
| relative speed | surge/sway speed magnitude, m/s |
| 16 future samples | public `9x17`, column 0 is solve-time state |
| moving ships | `TrackedObstacle` constant-velocity prediction |
| first selected heading | course/speed reference |

`horizon_dt_s=50` is a Playground time-base calibration. The paper and MATLAB
source do not publish an SI prediction timestep, so this value is not a paper
reproduction claim.

## Deliberate Phase 2 boundary

The port covers the local dynamic-collision MPC needed by Phase 2. It does not
port:

- global A*/Theta* chart route construction;
- GSHHG coastline rasterization;
- MATLAB target-ship COLREG behavior rewriting;
- static coast rejection inside each MPC fan.

The Playground supplies the route and evaluates dynamic collision with its own
continuous rectangular-footprint oracle. Static ENC-aware fan feasibility is
therefore not a declared capability.

The paper uses a `0.5 NM = 926 m` collision zone; its MATLAB settings use
`1000 m`. `PotocnikMPCParams` keeps the paper value as its library default.
The six standard Phase 2 scenes use `300 m` in
`config/potocnik_simplified_mpc.yaml`, because both Rule 13 scenes start about
`707 m` apart and are infeasible at solve `t=0` under a `926 m` hard
constraint. This is an explicit functional-profile calibration, not a hidden
change to the paper default.

## Run and verify

```bash
uv run python -m colav_simulator.cli plugin-check \
  --algorithm potocnik_simplified_mpc \
  --algorithm-config config/potocnik_simplified_mpc.yaml

uv run python -m colav_simulator.cli run \
  --scenario head_on \
  --algorithm potocnik_simplified_mpc \
  --tracker god \
  --algorithm-config config/potocnik_simplified_mpc.yaml

uv run pytest tests/test_potocnik_mpc.py tests/test_custom_mpc_g3_matrix.py -q
```

The formal G3 matrix is seed 0, God tracker, strict no fallback, and covers
`head_on`, `overtaking`, `overtaken`, `crossing_give_way`,
`crossing_stand_on`, and `paper_ccta2023_multiship`.
