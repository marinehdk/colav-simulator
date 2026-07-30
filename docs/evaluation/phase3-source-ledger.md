# Phase 3 Evaluator Source Ledger

> Status: implemented
> Evaluator: `behavior-compatible-evaluator-v2`
> Formula set: `ocean-engineering-2023-v1`
> Default profile: `ccta_2023_demo-v1`

## Reproduction Boundary

Original `trymte/colav_evaluation_tool` source is not publicly recoverable. Phase 3
is a behavior-compatible reconstruction, not an original-source restoration.

`NUMERICALLY_VERIFIED` is reserved for formula cells with complete published
inputs. Complete Ocean Engineering AIS trajectories are confidential; Tables 9
and 11 remain reference outputs, not executable end-to-end golden trajectories.

## Sources

| Priority | Source | Use |
|---|---|---|
| 1 | Ocean Engineering 288 (2023), DOI `10.1016/j.oceaneng.2023.115991` | Rules 8/13-17, Eqs. 2-32, Stage 1-4, weights |
| 2 | Hagen thesis, Chapter 5, handle `11250/3030310` | Formula and boundary cross-check |
| 3 | Historical `colav-simulator@844718b4` | Evaluator API and CCTA profile |
| 4 | CCTA 2023 framework paper | Simulator cases and reported output structure |
| 5 | Tang/Kim/Manocha ICRA 2009 | Controlled conservative advancement/first TOC |
| 6 | Ocean Engineering 308 (2024), DOI `10.1016/j.oceaneng.2024.118204` | Grounding extension boundary |

## Formula Mapping

| Metric | Formula ID | Implementation | Test |
|---|---|---|---|
| Range safety | `oe2023-eq3` | `evaluation/scoring.py:range_safety_score` | `test_colreg_paper_scores.py` |
| Pose safety | `oe2023-eq4-6` | `evaluation/scoring.py:pose_score` | `test_colreg_paper_scores.py` |
| Total safety | `oe2023-eq2` | `evaluation/scoring.py:total_safety_score` | `test_colreg_paper_scores.py` |
| Give-way | `oe2023-eq7-14` | `evaluation/scoring.py:score_pair` | `test_colreg_paper_scores.py` |
| Stand-on | `oe2023-eq15-24` | `evaluation/scoring.py:score_pair` | `test_colreg_paper_scores.py` |
| Rule 13 | `oe2023-eq25-26` | `evaluation/scoring.py:score_pair` | matrix tests |
| Rule 14 | `oe2023-eq27-30` | `evaluation/scoring.py:score_pair` | matrix tests |
| Rule 15 | `oe2023-eq31-32` | `evaluation/scoring.py:score_pair` | matrix tests |

Every serialized metric includes its formula ID, raw components, evaluation
status, and assumptions.

## Profiles

| Profile | Stage 2/3/4 m | Preferred/minimum/near-miss/collision m | Status |
|---|---|---|---|
| `ccta_2023_demo-v1` | 2500/1100/200 | 190/100/50/30 | Historical project default |
| `oe2023_simulated-v1` | 1900/700/200 | 200/100/50/35 | Paper Table 6 |
| `ship_length_scaled-v1` | 2500/1100/200 | Fixed `S_r` plus Fujii 4L/1.6L `S_domain` | Independent diagnostic; not paper reproduction |

Profiles are immutable and SHA-256 identified. CCTA and journal values are never
merged silently.

## Truth and Scope

- Physical collision: synchronized rectangle footprint C2A, zero safety buffer.
- Physical grounding: vessel footprint against per-vessel typed chart hazards.
- Hard collision gate: Ship0-vs-target scope.
- Hard grounding gate: Ship0 scope.
- Global all-vessel collision count: reported separately. Target-target collisions
  cannot be attributed to the tested Ship0 algorithm.
- Global all-vessel grounding count: reported separately. Target grounding cannot
  be attributed to the tested Ship0 algorithm.
- Multi-ship COLREG scores: pairwise. No invented target priority.
- Safety domain, chart geometric clearance, and operational UKC remain separate.
- `S_domain` is an ownship-centered target-center diagnostic. It does not replace
  physical footprint collision or the fixed paper-compatible `S_r`.
- Operational UKC: `NOT_EVALUATED`.
- 2024 grounding compensation: `NOT_EVALUATED`; V1 does not replace its
  alternative-path/tactical-diameter method with a clearance heuristic.

## Known Reconstruction Assumptions

- Historical `epsilon_d_course` numeric value `0.3 deg/s` is retained despite its
  conflicting inline comment.
- CCTA profile uses the published Ocean Engineering 2023 formulas.
- Simulator COG is used as footprint heading when evaluator input lacks independent
  heading samples.
- A C2A distance tolerance is numerical convergence metadata, not a safety buffer.

## VO Algorithm Source Note

This evaluator ledger does not promote the Kuwata VO reconstruction to a
numerical paper reproduction. The VO source boundary remains
`docs/kuwata_vo_reconstruction.md`.

Kuwata et al. IROS 2011 Eq. 7 prints CPA time without the leading negative
sign. With its relative-position and relative-velocity definitions, forward
closest approach requires
`t_cpa = -(p_r dot v_r) / (v_r dot v_r)`. The implementation retains this
signed physical projection: approaching encounters have positive TCPA and
past encounters negative TCPA. Tests freeze the zero-relative-speed,
approaching, horizon-boundary, and past-CPA cases.
