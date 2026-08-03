# Kuwata VO behavior-compatible reconstruction

Implementation label:
`kuwata_2011_behavior_compatible_reconstruction`.

## Normative boundary

Primary public specification:

- Y. Kuwata et al., “Safe Maritime Autonomous Navigation With COLREGS,
  Using Velocity Obstacles,” IROS 2011:
  <https://robotics.jpl.nasa.gov/media/documents/Kuwata11IROS_final_v3.pdf>

Cross-checks:

- 2014 IEEE Journal of Oceanic Engineering record:
  <https://doi.org/10.1109/JOE.2013.2254214>
- NASA patent record:
  <https://ntrs.nasa.gov/citations/20150003430>
- NTNU upstream implementation:
  <https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/blob/main/colav_simulator/core/colav/kuwata_vo_alg/kuwata_vo.py>
- `asv_path_planner`, geometry and test comparison only:
  <https://github.com/egreuel/asv_path_planner>

No external implementation code was copied. The reconstruction was written
from the published equations and independently tested. The 2014 article body
was not available as an open normative source; this implementation therefore
does not claim numerical reproduction of the journal version.

## Capability matrix

| Capability | Status | Evidence boundary |
|---|---|---|
| Moving-vessel VO | Implemented | Constant-velocity target; rectangular footprints |
| Zero-speed static hazard VO | Implemented | Local physical ENC geometry only |
| Multiple hazards | Implemented | Union of hard constraints; minimum TTC |
| Bounded velocity uncertainty `W_B` | Implemented | Convex velocity set; `WVO = VO (+) W_B` |
| Base VO | Hard constraint | Never selected |
| WVO-only region | Soft cost | Reduced TTC weight |
| Head-on | Implemented subset | V1 forbidden; not full Rule 14 legal semantics |
| Ownship overtaking | Implemented subset | V1 forbidden |
| Crossing, target on starboard | Implemented subset | V1 forbidden |
| Crossing, target on port | Stand-on treatment | No direction constraint; base VO remains |
| Ownship being overtaken | Stand-on treatment | No direction constraint; base VO remains |
| Rule hysteresis | Implemented | Per `(track_id, rule)` consecutive misses |
| Ship dynamics in optimization | Not implemented | Controller and ship model execute reference afterward |
| Global island routing | Not implemented | Local velocity selection only |
| Depth, UKC, CATZOC reasoning | Not implemented | Excluded from static VO adapter |
| Complete COLREG Rules 2-19 | Not implemented | No legal-compliance claim |

## Parameter provenance

| Parameter or behavior | Default | Provenance |
|---|---:|---|
| Planning frequency | `1 Hz` | `paper_explicit` |
| Velocity grid | `32 x 128` | `paper_explicit` |
| Absolute speed range | `0..10 m/s` | `inferred_reconstruction` |
| Base VO admissibility | hard | `paper_structural` |
| WVO-only admissibility | soft | `paper_structural` |
| COLREG V1 admissibility | hard | `paper_structural` |
| TTC plus reference-velocity cost | enabled | `paper_structural` |
| `W_B` vertices | square, `+/-1.2 m/s` per axis | `inferred_reconstruction` |
| TTC weight | `500` | `inferred_reconstruction` |
| Local-island validation profile | `w_ttc=100`, `W_B=+/-1 m/s` per axis | `inferred_reconstruction` |
| Dual-VO head-on validation profile | `w_ttc=1000`, WVO scale `1`, `W_B=+/-2 m/s` per axis | `inferred_reconstruction` |
| Reference-velocity weight | `1` | `inferred_reconstruction` |
| WVO TTC scale | `0.25` | `inferred_reconstruction` |
| CPA horizon | `120 s` | `project_profile`, earlier warning for standard simulator geometry |
| CPA distance | `100 m` | `project_profile`, not a paper parameter |
| CPA ownship velocity | current measured earth-fixed velocity | `physical_correction`, rule gate describes the current encounter |
| Rule heading tolerance | `15 deg` | `inferred_reconstruction` |
| Crossing heading sector | `15..165 deg` | `inferred_reconstruction` |
| Relative bearing sector | `0..112.5 deg` | `inferred_reconstruction` |
| Rule hysteresis | `3 solves` | `inferred_reconstruction` |
| Give-way commitment | HO, ownship-overtaking, and starboard crossing retain the entry-side maneuver | `project_profile` |
| Give-way release | `150 m`, moving apart, CPA gate clear for `3 solves` | `project_profile` |
| Low-speed classification cutoff | `0.5 m/s` | `inferred_reconstruction` |
| Static layers | `LAND, SHORE, OBSTRN, UWTROC` | `project_adapter` |
| Static local query range | `1000 m` | `project_adapter` |
| Infeasible wrapper command | current heading, zero speed | `project_adapter` |
| Infeasible label | `stop_nonpaper_wrapper` | `project_adapter` |

Closed-loop artifact acceptance uses separate `project_acceptance` thresholds:
minimum sampled hull clearance `1 m`, stop speed `0.3 m/s`, at most `5`
consecutive feasible stop solves, course-error tolerance `45 deg` with at most
`10` consecutive violations, and at most `20` significant active-encounter
turn reversals. These values are not Kuwata paper parameters.

Removed configuration keys `safety_buffer`, `vo_violation_cost`,
`grounding_cost`, and `colregs_violation_cost` raise migration errors. Their
dimensions or finite-penalty semantics cannot be silently converted to
velocity uncertainty or hard admissibility.

## Give-way commitment and stand-on boundary

Head-on, ownship-overtaking, and crossing give-way encounters use a stateful
commitment after the first CPA-gated rule match. The rule remains locked when
an initial starboard action moves the target outside the narrow body-frame
classification corridor. While committed, candidates that move materially to
port, reverse longitudinal direction, or reverse past the previous selected
course are inadmissible. The lock releases only after the CPA gate clears and
the target is at least `150 m` away and moving apart for three solves. The same
contact cannot immediately retrigger a new rule; it first must clear the wider
re-arm range. If no candidate survives only because of this project rule, the solver exposes
`emergency_rule_relaxation=true`; it does not silently call another planner.

`CR_PS` remains a stand-on role. Before the current measured velocity enters
the base VO, the closest grid point to the measured velocity is retained. A
base-VO conflict can still trigger the existing safety action. This is a
project behavior policy, not complete Rule 17 semantics.

## Figures and decision-space data

Paper Fig. 2 demonstrates that the same relative geometry can produce a
different COLREG classification when vessel velocities change. Paper Fig. 6
is the colored velocity decision space shown during a crossing encounter.
The web interface reconstructs the Fig. 6 concept from the real `32 x 128`
solve grid; it is not a pixel or numerical reproduction of the paper figure.

Dense grid data uses the optional `vo_velocity_space.v1` snapshot and
`GET /api/sessions/{session_id}/planner/decision-space?solve_id=N`. It is
cached only after a real VO solve and is deliberately excluded from 10 Hz
telemetry, planner evidence frames, and server-side Matplotlib.

## Validation interpretation

Three conclusions must be reported separately:

1. **Raw safety:** continuous vessel-footprint collision and grounding truth.
2. **COLREG action quality:** encounter classification, first maneuver in the
   ownship body frame, rule release, stopping, oscillation, and task recovery.
3. **Paper-structure reproduction:** VO, WVO, TTC cost, rule regions,
   hysteresis, and deterministic `32 x 128` search.

For multi-vessel runs, Ship0-to-target safety and global all-vessel safety are
separate results. A Ship0-only planner cannot establish global fleet safety.
