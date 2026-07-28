# Phase 1 SB-MPC / VO Reference Baseline

## 1. Purpose

This baseline separates authoritative implementations from local reproductions:

- `sbmpc_reference`: pinned official native C++ SB-MPC, used as the
  differential oracle.
- `sbmpc`: existing incomplete Python reproduction, retained until behavior is
  reconciled against the oracle.
- `vo`: local Kuwata-style Python implementation, audited against the primary
  paper and the NTNU AutoSea implementation.

The reference ID is not a capability promotion. It becomes selectable only
when the external native binding is available and never falls back.

## 2. Official SB-MPC Identity

| Item | Pinned identity |
|---|---|
| Algorithm repository | <https://github.com/ntnu-itk-autonomous-ship-lab/psbmpc> |
| Native core commit | `8b78d009d173db20af28e1a2a662417c8d893f12` |
| Python binding repository | <https://github.com/ntnu-itk-autonomous-ship-lab/pybind_im_and_psbmpc> |
| Python binding commit | `367dad8809424b21c013512308de2a07bd184464` |
| Primary method paper | Johansen, Perez, Cristofaro (2016), DOI `10.1109/TITS.2016.2551780` |
| Guidance/transitional-cost paper | Hagen et al. (2018), DOI `10.1109/ICRA.2018.8463182` |

`OfficialSBMPCReference` calls the native `SBMPC`, `SBMPCParams`,
`KinematicShip`, `ObstaclePredictor`, and `TrackedObstacle` classes. Native
defaults provide the original 13 course offsets, three speed factors,
transitional cost, first-order ship prediction, and 110 s / 0.5 s horizon.
Simulator vessel dimensions replace only the native demo vessel dimensions.

The pinned binding has a verified argument-label defect: its two final pybind
labels are `disable, new_static_obstacle_data`, while the bound C++ function
accepts `new_static_obstacle_data, disable`. The reference adapter deliberately
uses positional C++ order. Passing the documented Python keywords disables the
solver during the initial call.

Golden case:

```text
own ship: [N=0, E=0, chi=0, U=7]
target:   [N=500, E=0, VN=-7, VE=0]
result:   speed factor 1.0, starboard course offset +15 deg
horizon:  native (4, 220), mapped public (9, 220)
```

`tests/test_sbmpc_reference.py` freezes this behavior and provenance.

## 3. VO Authority

Primary source:

- Kuwata et al., *Safe Maritime Navigation with COLREGS Using Velocity
  Obstacles*, JPL/IROS 2011; journal version DOI
  `10.1109/JOE.2013.2254214`.
- NTNU AutoSea reference source:
  <https://github.com/ntnu-itk-autonomous-ship-lab/psbmpc/tree/main/sbmpc_catkin_ws/ros_asv_system/asv_ctrl_vo>

The AutoSea files contain legacy license text that conflicts with the
repository-level MIT license. They are behavior references only; no source was
copied.

## 4. Confirmed VO Defects

Fixed and regression-tested:

1. Candidate grid values are absolute speeds, not positive offsets added to
   current speed.
2. Pre-collision gate now requires `0 <= TCPA <= t_max`; past CPA is rejected.
3. Later targets cannot reduce an existing higher collision penalty.
4. Crossing side uses target bearing from own ship, not own-ship bearing from
   target.
5. Passed-and-clear distance applies to both heading clauses.
6. Earlier Phase 1 fixes already corrected the candidate east component and
   moving-target relative velocity ray.

Remaining fidelity gaps:

1. Paper cost includes time-to-collision; local code uses fixed violation
   penalties.
2. Paper separates hard VO from soft worst-case velocity uncertainty; local
   code uses one spatially buffered hard test.
3. Paper rule selector uses CPA, speed/heading/bearing/cross-track conditions
   and per-track hysteresis. Local classification remains reduced.
4. Static-hazard checking exists but is disabled.
5. Planner diagnostics cannot yet distinguish no collision-free candidate from
   successful selection.

These gaps prohibit calling `vo` a paper-faithful numerical reproduction. They
do not invalidate raw G3 evidence, but each must be closed before COLREG
compliance or paper-equivalent claims.

## 5. Gates

```bash
MPLBACKEND=Agg uv run pytest \
  tests/test_sbmpc_reference.py \
  tests/test_kuwata_vo_regression.py \
  tests/test_rule14_planner_trace.py -q

MPLBACKEND=Agg uv run pytest \
  tests/test_rule13_15_g3_matrix.py \
  tests/test_multiship_g3.py -q
```
