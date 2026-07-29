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

The paper and upstream repository do not assign a dedicated short name such as
`SMPC` to the algorithm. They call it the "simplified MPC formulation". The
Playground therefore displays the paper-faithful short label `简化 MPC`; it
retains the stable internal ID for manifests and API compatibility.

This is a functional algorithm reproduction, not a numerical reproduction of
the paper figures. It does not claim to implement the general nonlinear
optimization stated in Equation (12).

## Ported algorithm

Each solve:

1. generates 45 deterministic fan trajectories;
2. evaluates first-step heading increments in `[-10, +10] deg`;
3. multiplies that increment by `0.95` at each of 20 prediction steps;
4. propagates each candidate through a first-order course response plus yaw-rate
   limit, rather than assuming an instantaneous heading jump;
5. predicts every target with constant velocity;
6. rejects a candidate when any synchronous predicted separation is below the
   configured collision distance, or its footprint-buffered centerline enters
   ENC land, shoreline, or unsafe shallow water;
7. scores feasible candidates by waypoint alignment, command continuity,
   dynamic clearance, and static clearance;
8. enforces a starboard candidate set for detected head-on encounters;
9. penalizes avoidance-side reversal while the straight candidate remains
   unsafe, then releases that penalty after two consecutive safe solves;
10. limits consecutive course-reference changes to `5 deg` when a feasible
   candidate exists inside that bound;
11. holds the selected command through the current `5 s` solve interval, then
    samples later commands from a separate command trajectory.

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
| 20 future samples | public `9x21`, column 0 is solve-time state |
| moving ships | `TrackedObstacle` constant-velocity prediction |
| static obstacles | ENC land + shore + unsafe seabed union |
| first selected heading | course/speed reference |

`M=45` follows Table 3 and the MATLAB settings. The paper and MATLAB source do
not publish an SI prediction timestep: the source advances
`ship_speed=3e-3` in relative geographic units once per simulation iteration.
The executable Playground profile therefore uses explicit engineering
calibration: `H=20`, `horizon_dt_s=5`, a `100 s` horizon, a new solve every
`5 s`, and a `10 deg` first-step fan bound. The public `9x21` trajectory contains
the solve-time state plus 20 future steps. These values are not claimed as
paper-reported timing.

The audited MATLAB source does not define hysteresis, trajectory blending, or
steering-rate smoothing. The Playground profile adds command continuity,
a feasible `5 deg` consecutive course-reference bound, and a soft penalty
against changing maneuver side while the straight fan candidate remains
unsafe. A first-order course-response model (`tau=8 s`) and `3 deg/s` yaw-rate
limit model steering lag inside the fan. The physical prediction and command
trajectory are kept separate, so solve/hold scheduling no longer feeds a
delayed physical heading back as the next command. A `600 m` dynamic influence
gate starts meaningful clearance improvement before the hard `150 m` boundary.
For detected reciprocal head-on geometry, the candidate set is constrained to
starboard turns. These are executable-profile additions, not claims that the
paper reported these values. The downstream FLSC still converts course/speed
references into forces for the Viknes 3-DOF vessel model.

Static feasibility now consumes the simulator ENC already passed to the
adapter. The vessel draft selects unsafe seabed; land, shore, and unsafe seabed
are unioned. Each candidate centerline is checked against that geometry buffered
by the vessel footprint radius plus a `20 m` required clearance. A soft
clearance cost acts inside `200 m`; the speed reference is reduced relative to
planned speed when a selected candidate approaches that influence boundary.
The execution deadline is `250 ms`; cached ENC union construction leaves enough
budget for 45 continuous centerline checks every `5 s`.

## Deliberate Phase 2 boundary

The port covers the local dynamic-collision MPC needed by Phase 2. It does not
port:

- global A*/Theta* chart route construction;
- GSHHG coastline rasterization;
- MATLAB target-ship COLREG behavior rewriting;
- complete Rule 13/15 role-specific maneuver selection;
- the paper's general nonlinear program, CasADi, or IPOPT.

The Playground supplies the route and evaluates dynamic collision with its own
continuous rectangular-footprint oracle. Static hazards use the Playground ENC,
not the paper's GSHHG raster and Theta* global planner. The result is local
ENC-aware fan feasibility, not global chart-based route planning.

The paper uses a `0.5 NM = 926 m` collision zone; its MATLAB settings use
`1000 m`. `PotocnikMPCParams` keeps the paper value as its library default.
The six standard Phase 2 scenes use `150 m` in
`config/potocnik_simplified_mpc.yaml`, because both Rule 13 scenes start about
`707 m` apart and are infeasible at solve `t=0` under a `926 m` hard
constraint. The shorter executable `100 s` horizon also needs maneuver space
in the three-target scene; the prior `300 m` profile could exhaust all 45
candidates before the hydrodynamic vessel completed its turn. This is an
explicit functional-profile calibration, not a hidden change to the paper
default.

The paper's `3 nm = 5556 m` COLREG application zone is declared separately as
`colreg_zone_distance_m` and shown on the map as a paper reference range. It is
not presented as a runtime activation threshold: this functional port does not
include the upstream route-following/MPC mode switch. Algorithms need only
publish such a range when it has defined semantics; the field is not mandatory
for every integration.

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
