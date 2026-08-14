# Collision Avoidance Planning

Colav-Simulator separates mission-following intent from temporary collision-avoidance intent across a rolling prediction horizon.

## Language

**Mission Route**:
The intended voyage route that remains authoritative before and after an encounter.
_Avoid_: Committed route, avoidance route

**Avoidance Corridor**:
A temporary passing-side course commitment used while an encounter remains active.
_Avoid_: Mission route, return route

**Horizon Encounter Plan**:
An immutable projection of alter, pass, and recover phases over one MPC prediction horizon. It predicts future phases without changing the authoritative encounter lifecycle.
_Avoid_: Current encounter state, solver trajectory

**Hard Row Window**:
A half-open control-interval range compiled from encounter phases into `lbg`/`ubg`. Windows change constraint activation without changing CasADi graph shape or decision dimension.
_Avoid_: Solver graph topology, lifecycle state
