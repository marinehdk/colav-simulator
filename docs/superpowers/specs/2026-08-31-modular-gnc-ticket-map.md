# Modular GNC implementation ticket map

Parent: #41

Pinned G6 baseline: `8968f31b982d48773d08f814439827328bf4b35d`

## Tickets

- [#42](https://github.com/marinehdk/colav-simulator/issues/42) — [GNC S1.1] Pin legacy commit and capture G6 regression baseline
- [#43](https://github.com/marinehdk/colav-simulator/issues/43) — [GNC S1.2] Define typed modular GNC contracts and navigation-source seam
- [#44](https://github.com/marinehdk/colav-simulator/issues/44) — [GNC S1.3] Pin CommandInput authority, tick latching, and ZOH semantics
- [#45](https://github.com/marinehdk/colav-simulator/issues/45) — [GNC S1.4] Add opt-in ship_modules configuration and minimal registry v1
- [#46](https://github.com/marinehdk/colav-simulator/issues/46) — [GNC S1.5] Implement atomic ModularShipStack lifecycle and scheduler shell
- [#47](https://github.com/marinehdk/colav-simulator/issues/47) — [GNC S1.6] Bridge ModularShipStack through IShip and map facade failures
- [#48](https://github.com/marinehdk/colav-simulator/issues/48) — [GNC S1.7] Build content-addressed C++ characterization fixture pipeline
- [#49](https://github.com/marinehdk/colav-simulator/issues/49) — [GNC S2.1] Implement deterministic EnvironmentField and separated truth/observation outputs
- [#50](https://github.com/marinehdk/colav-simulator/issues/50) — [GNC S2.2] Implement vessel environmental loads, asset validation, and current de-duplication
- [#51](https://github.com/marinehdk/colav-simulator/issues/51) — [GNC S2.3] Implement explicit first-order wave and mean-drift load modes
- [#52](https://github.com/marinehdk/colav-simulator/issues/52) — [GNC S3.1] Add external RK4 scheduler wiring and generic 3DOF plant
- [#53](https://github.com/marinehdk/colav-simulator/issues/53) — [GNC S3.2] Add restoring-dominated roll-4DOF plant and input-domain capability checks
- [#54](https://github.com/marinehdk/colav-simulator/issues/54) — [GNC Checkpoint] Profile environment and plants; record Python go/no-go
- [#55](https://github.com/marinehdk/colav-simulator/issues/55) — [GNC S4.1] Implement transparent marine_pid under ideal generalized-load fidelity
- [#56](https://github.com/marinehdk/colav-simulator/issues/56) — [GNC S4.2] Add control tasks and legacy-equivalent G8 attribution profile
- [#57](https://github.com/marinehdk/colav-simulator/issues/57) — [GNC S5] Implement clean ILOS with explicit route and lifecycle semantics
- [#58](https://github.com/marinehdk/colav-simulator/issues/58) — [GNC S6.1] Add data-driven allocator and achieved-load diagnostics
- [#59](https://github.com/marinehdk/colav-simulator/issues/59) — [GNC S6.2] Add resolved actuator dynamics and separate fidelity profile
- [#60](https://github.com/marinehdk/colav-simulator/issues/60) — [GNC UI] Filter compatible stacks and expose evidence labels before A3 demo
- [#61](https://github.com/marinehdk/colav-simulator/issues/61) — [GNC A3] Produce generalized-simulation evidence and controlled demo
- [#62](https://github.com/marinehdk/colav-simulator/issues/62) — [GNC S7.0] Audit planner route outputs before tracked-route integration
- [#63](https://github.com/marinehdk/colav-simulator/issues/63) — [GNC S7.1] Connect Mid-MPC accepted rolling routes to modular ILOS
- [#64](https://github.com/marinehdk/colav-simulator/issues/64) — [GNC S8] Add optional ROS 2 adapter and simulation-time SIL harness

## Binding sequencing notes

- Contracts-only slice precedes physics kernels.
- Environment and plants precede mandatory performance GO/NO-GO checkpoint.
- `marine_pid` and later slices require checkpoint GO or an approved remediation ticket.
- Planner audit blocks tracked-route integration.
- UI compatibility/evidence labels block A3 demonstration.
- ROS adapter remains optional and does not imply A6/SIL/HIL acceptance.
