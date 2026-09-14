# Original GNC matrix truth

This report reads the completed matrix JSON manifests/evaluations/events only.
COLREG verdicts come from the separate `colreg-scoring-v2` reconstruction and are included only for completed, evaluated cells.

## Counts

- Cases: **24**; completed **18**; failed **6**.
- Hard gate PASS: **18**; ownship hard gate PASS: **18**.
- Goal reached among completed cells: **4**; not reached: **14**.
- Ownship safety among completed cells: collision counts {'0': 18}; grounding counts {'0': 18}; failed cells unassessed **6**.
- Global safety among completed cells: collision counts {'0': 18}; grounding counts {'1': 6, '0': 12}; failed cells unassessed **6**.
- COLREG: **18** completed cells, **23** encounters; verdicts {'PARTIAL': 6, 'COMPLIANT': 17}.

## Build identity

- Library SHA256: `6da7998cf7ec55dedb4a8fe493478b40522e6c7e272a3706297ac84fc5c5069f`
- Source manifest SHA256: `2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`
- Stack IDs: `original-gnc-20260824-v2-env-off`, `original-gnc-20260824-v2-env-on`
- Response qualification: `QUALIFIED_FIRST_ORDER_TRAJECTORY_APPROXIMATION`
- Runtime-source snapshot: 21 files; missing 0; hash mismatches 0.

## Per-cell truth

| Case | Outcome / failure | Failure layer | Raw failure reason | Gate | Ownship gate | Own C/G | Global C/G | Goal | COLREG |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `mid_mpc_ipopt-crossing_give_way-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/1 | N | PARTIAL |
| `mid_mpc_ipopt-crossing_give_way-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/1 | N | PARTIAL |
| `mid_mpc_ipopt-head_on-E0` | FAILED / NUMERICAL_FAILURE | OPTIMIZER | Mid-MPC optimizer returned NUMERICAL_FAILURE without a feasible candidate | FAIL | UNASSESSED | — | — | — | UNASSESSED |
| `mid_mpc_ipopt-head_on-E4` | FAILED / INFEASIBLE | OPTIMIZER | Mid-MPC optimizer returned INFEASIBLE without a feasible candidate | FAIL | UNASSESSED | — | — | — | UNASSESSED |
| `mid_mpc_ipopt-overtaking-E0` | FAILED / INFEASIBLE | L4_ACCEPTANCE | Mid-MPC L4 plan acceptance rejected the candidate: SAFETY_SWEPT_CLEARANCE | FAIL | UNASSESSED | — | — | — | UNASSESSED |
| `mid_mpc_ipopt-overtaking-E4` | FAILED / INFEASIBLE | L4_ACCEPTANCE | Mid-MPC L4 plan acceptance rejected the candidate: SAFETY_SWEPT_CLEARANCE, QUALITY_CPA_RELEASE | FAIL | UNASSESSED | — | — | — | UNASSESSED |
| `mid_mpc_ipopt-paper_ccta2023_multiship-E0` | FAILED / NUMERICAL_FAILURE | OPTIMIZER | Mid-MPC optimizer returned NUMERICAL_FAILURE without a feasible candidate | FAIL | UNASSESSED | — | — | — | UNASSESSED |
| `mid_mpc_ipopt-paper_ccta2023_multiship-E4` | FAILED / NUMERICAL_FAILURE | OPTIMIZER | Mid-MPC optimizer returned NUMERICAL_FAILURE without a feasible candidate | FAIL | UNASSESSED | — | — | — | UNASSESSED |
| `potocnik_colreg_fan_mpc-crossing_give_way-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/1 | Y | COMPLIANT |
| `potocnik_colreg_fan_mpc-crossing_give_way-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/1 | Y | COMPLIANT |
| `potocnik_colreg_fan_mpc-head_on-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | Y | COMPLIANT |
| `potocnik_colreg_fan_mpc-head_on-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | Y | COMPLIANT |
| `potocnik_colreg_fan_mpc-overtaking-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | PARTIAL |
| `potocnik_colreg_fan_mpc-overtaking-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | PARTIAL |
| `potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | COMPLIANT, COMPLIANT, COMPLIANT |
| `potocnik_colreg_fan_mpc-paper_ccta2023_multiship-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | COMPLIANT, COMPLIANT, PARTIAL |
| `vo-crossing_give_way-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/1 | N | COMPLIANT |
| `vo-crossing_give_way-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/1 | N | COMPLIANT |
| `vo-head_on-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | COMPLIANT |
| `vo-head_on-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | COMPLIANT |
| `vo-overtaking-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | PARTIAL |
| `vo-overtaking-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | COMPLIANT |
| `vo-paper_ccta2023_multiship-E0` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | COMPLIANT |
| `vo-paper_ccta2023_multiship-E4` | COMPLETED | — | — | PASS | PASS | 0/0 | 0/0 | N | COMPLIANT, COMPLIANT |

## Failure breakdown

| Environment | Failure type | Layer | Count |
| --- | --- | --- | ---: |
| E0 | `INFEASIBLE` | L4_ACCEPTANCE | 1 |
| E0 | `NUMERICAL_FAILURE` | OPTIMIZER | 2 |
| E4 | `INFEASIBLE` | L4_ACCEPTANCE | 1 |
| E4 | `INFEASIBLE` | OPTIMIZER | 1 |
| E4 | `NUMERICAL_FAILURE` | OPTIMIZER | 1 |

Failed cells remain unassessed for ownship/global safety and COLREG. Any COLREG verdict shown is a behavior-scoring result, not formal D3 acceptance.
