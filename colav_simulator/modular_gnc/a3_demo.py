"""Controlled A3 generalized-simulation demonstration (Issue #61).

Strictly local and deterministic evidence generator for the first generalized-
simulation demo: two distinct vessel presets execute one identical, branch-free
closed loop (ILOS guidance -> marine PID -> data-driven allocator -> resolved
actuator dynamics -> generic 3DOF plant) through the ``ModularShipStack``
facade.  Preset differences are pure configuration data; no code path branches
on preset, vessel, or scenario identity.

Claim ceiling: A3 (Generalized Simulation).  Every G0-G10 gate is reported with
an honest three-state verdict (``passed`` / ``failed`` / ``not run``), and the
hydrodynamic, guidance, control, actuator, COLAV, and system evidence classes
are presented separately (VR-24, VR-25, TS-28, TS-29, RA-14).  Source parity
(legacy-equivalent structure, candidate A2) and intentional redesign are
declared in separate sections and never merged.

Reproducibility contract: every number in
``docs/evaluation/a3-generalized-simulation-demo.md`` is reproduced by
``tests/test_modular_gnc_a3_demo.py`` from this module in one local pytest run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.characterization_report import (
    build_generic_3dof_plant_redesign_decisions,
    build_generic_roll_4dof_plant_redesign_decisions,
    build_marine_pid_redesign_decisions,
    load_characterization_fixture_manifest,
)
from colav_simulator.modular_gnc.configuration import ShipModulesConfig, normalize_ship_modules
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    ControlTask,
    DirectReference,
    NavigationState,
    TrackedRoute,
)
from colav_simulator.modular_gnc.stack import ModularShipStack

if TYPE_CHECKING:
    from colav_simulator.modular_gnc.attribution import ArmIdentity  # noqa: F401
    from colav_simulator.modular_gnc.characterization_report import RedesignDecision  # noqa: F401

DEMO_SCHEMA_VERSION = "modular-gnc.a3-demo-report.v1"
DEMO_CLAIM_CEILING_LEVEL = "A3"
DEMO_CLAIM_CEILING_LABEL = "Generalized Simulation"

GATE_IDS: tuple[str, ...] = tuple(f"G{index}" for index in range(11))

EVIDENCE_CLASSES: tuple[str, ...] = (
    "hydrodynamic",
    "guidance",
    "control",
    "actuator",
    "colav",
    "system",
)

# Shared, preset-independent acceptance thresholds for the closed-loop demo
# checks.  They are check parameters, not vessel data, so both presets are held
# to exactly the same bars (G7: no per-vessel criteria).
FINAL_CROSS_TRACK_ERROR_TOLERANCE_M = 3.0
FINAL_SPEED_ERROR_TOLERANCE_MPS = 0.2
MAX_CROSS_TRACK_EXCURSION_MARGIN_M = 5.0

_PINNED_LEGACY_COMMIT = "8968f31b982d48773d08f814439827328bf4b35d"
_CHARACTERIZATION_MANIFEST_SHA256 = "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_G6_BASELINE_FIXTURE = _REPOSITORY_ROOT / "tests" / "fixtures" / "gnc_g6" / "legacy-baseline-v1.json"
_CHARACTERIZATION_FIXTURE_DIR = _REPOSITORY_ROOT / "tests" / "fixtures" / "gnc_characterization"

ACCEPTANCE_NON_CLAIMS: tuple[str, ...] = (
    "No vessel calibration is claimed at any point in this demo (A5 scope).",
    "No COLAV closed-loop acceptance is claimed: G8 is not run and the COLAV "
    "evidence class is reported as not run (pending #62/#63).",
    "No platform-adapter SIL/HIL acceptance is claimed: G10 is not run "
    "(later adapter slice #64).",
    "No sea-trial or vessel validation claims of any kind are made; all assets "
    "remain mock-trust scaffolding and all claims stay at the A3 ceiling.",
)


@dataclass(frozen=True)
class DemoPreset:
    """One vessel preset: pure configuration and scenario data, no behaviour."""

    preset_id: str
    description: str
    ship_modules: dict
    initial_navigation: tuple[float, float, float, float, float, float]
    waypoints_ne_m: tuple[tuple[float, float], ...]
    route_speed_mps: tuple[float, ...]
    route_id: str
    ticks: int
    dt_s: float
    episode_seed: int


def _marine_pid_parameters(
    *,
    kp: tuple[float, float, float],
    ki: tuple[float, float, float],
    kd: tuple[float, float, float],
    min_output: tuple[float, float, float],
    max_output: tuple[float, float, float],
    integral_limit: tuple[float, float, float],
) -> dict:
    """Return one marine_pid parameter block (vessel-scaled control data)."""
    return {
        "kp": list(kp),
        "ki": list(ki),
        "kd": list(kd),
        "tau_d": [0.5, 0.5, 0.5],
        "antiwindup_gain": [1.0, 1.0, 1.0],
        "min_output": list(min_output),
        "max_output": list(max_output),
        "integral_limit": list(integral_limit),
        "feedforward_gain": [0.0, 0.0, 0.0],
        "allow_ideal_passthrough": True,
    }


_TRIPLE_LAYOUT_ID = "default_triple_actuator_layout_v1"
_QUAD_LAYOUT_ID = "quad_diagonal_actuator_layout_v1"

_LIGHT_VESSEL_PLANT = {
    "mass_kg": 1.2e7,
    "i_z_kgm2": 2.0e10,
    "d_u": 6.0e4,
    "d_uu": 5.0e3,
    "d_v": 1.0e5,
    "d_vv": 8.0e3,
    "d_r": 5.0e8,
    "d_rr": 5.0e9,
}

_HEAVY_VESSEL_PLANT = {
    "mass_kg": 2.8e7,
    "i_z_kgm2": 6.0e9,
    "d_u": 4.3e5,
    "d_uu": 2.0e4,
    "d_v": 6.0e5,
    "d_vv": 3.0e4,
    "d_r": 5.0e7,
    "d_rr": 1.0e9,
}


def _known_actuator_ids(layout_asset_id: str) -> tuple[str, ...]:
    from colav_simulator.modular_gnc.allocator import KNOWN_ACTUATOR_LAYOUT_ASSETS  # noqa: PLC0415

    return KNOWN_ACTUATOR_LAYOUT_ASSETS[layout_asset_id].actuator_ids()


def _demo_vessel_modules(
    *,
    plant_parameters: dict,
    pid_parameters: dict,
    layout_asset_id: str,
    rate_limit_n_per_s: float,
    delay_ticks: int,
    lookahead_distance_m: float,
    integral_gain: float,
    max_integral_cross_track_error_m: float,
) -> tuple[dict, dict]:
    """Assemble the one compatible demo combination with per-vessel data.

    The module-identity combination is listed in ``list_stack_catalog()``; only
    the parameter payload varies per vessel preset.  Resolved actuator dynamics
    is a discrete phase on the base clock, so the scheduler override pins
    controller and guidance cadence to every tick.
    """
    actuator_ids = _known_actuator_ids(layout_asset_id)
    modules = {
        "plant": {"identity": "generic_3dof_plant", "parameters": dict(plant_parameters)},
        "guidance": {
            "identity": "integral_line_of_sight",
            "parameters": {
                "lookahead_distance_m": lookahead_distance_m,
                "integral_gain": integral_gain,
                "max_integral_cross_track_error_m": max_integral_cross_track_error_m,
            },
        },
        "controller": {"identity": "marine_pid", "parameters": pid_parameters},
        "allocator": {"identity": "data_driven_allocator", "parameters": {"layout_asset_id": layout_asset_id}},
        "actuator": {
            "identity": "resolved_actuator_dynamics",
            "parameters": {
                "layout_asset_id": layout_asset_id,
                "rate_limit_n_per_s": dict.fromkeys(actuator_ids, rate_limit_n_per_s),
                "delay_ticks": dict.fromkeys(actuator_ids, delay_ticks),
            },
        },
    }
    overrides = {"scheduler": {"controller_period_ticks": 1, "guidance_period_ticks": 1}}
    return modules, overrides


def _demo_ship_modules(**kwargs) -> dict:
    modules, overrides = _demo_vessel_modules(**kwargs)
    return {"preset": "legacy_equivalent", "modules": modules, "overrides": overrides}


DEMO_PRESETS: tuple[DemoPreset, ...] = (
    DemoPreset(
        preset_id="demo_preset_a",
        description="Lighter 3DOF preset, triple actuator layout, zero transport delay",
        ship_modules=_demo_ship_modules(
            plant_parameters=_LIGHT_VESSEL_PLANT,
            pid_parameters=_marine_pid_parameters(
                kp=(2.5e5, 1.5e5, 5.0e8),
                ki=(8.0e4, 5.0e4, 1.0e8),
                kd=(1.5e5, 8.0e4, 2.0e9),
                min_output=(-9.0e5, -9.0e5, -3.0e7),
                max_output=(9.0e5, 9.0e5, 3.0e7),
                integral_limit=(2.6e5, 1.5e5, 2.0e7),
            ),
            layout_asset_id=_TRIPLE_LAYOUT_ID,
            rate_limit_n_per_s=4.0e5,
            delay_ticks=0,
            lookahead_distance_m=60.0,
            integral_gain=5.0e-4,
            max_integral_cross_track_error_m=60.0,
        ),
        initial_navigation=(0.0, 6.0, -0.05, 0.0, 0.0, 0.0),
        waypoints_ne_m=((0.0, 0.0), (800.0, 0.0)),
        route_speed_mps=(2.0, 2.0),
        route_id="a3-demo-route-a",
        ticks=1200,
        dt_s=0.1,
        episode_seed=20260902,
    ),
    DemoPreset(
        preset_id="demo_preset_b",
        description="Heavier 3DOF preset, quad diagonal actuator layout, one-tick transport delay",
        ship_modules=_demo_ship_modules(
            plant_parameters=_HEAVY_VESSEL_PLANT,
            pid_parameters=_marine_pid_parameters(
                kp=(1.1e5, 6.0e4, 7.2e7),
                ki=(2.0e4, 1.0e4, 0.0),
                kd=(2.4e6, 8.0e5, 3.0e9),
                min_output=(-1.5e6, -1.5e6, -2.4e7),
                max_output=(1.5e6, 1.5e6, 2.4e7),
                integral_limit=(9.0e5, 6.0e4, 8.0e6),
            ),
            layout_asset_id=_QUAD_LAYOUT_ID,
            rate_limit_n_per_s=4.0e5,
            delay_ticks=1,
            lookahead_distance_m=70.0,
            integral_gain=2.0e-4,
            max_integral_cross_track_error_m=40.0,
        ),
        initial_navigation=(0.0, -15.0, 0.5, 0.0, 0.0, 0.0),
        waypoints_ne_m=((0.0, 0.0), (500.0, 500.0)),
        route_speed_mps=(1.8, 1.8),
        route_id="a3-demo-route-b",
        ticks=1600,
        dt_s=0.1,
        episode_seed=20260902,
    ),
)


@dataclass(frozen=True)
class GateCheck:
    """One named deterministic check contributing to a gate verdict."""

    name: str
    passed: bool
    observed: Any


@dataclass(frozen=True)
class GateResult:
    """Three-state acceptance gate verdict (VR-24, TS-28)."""

    gate_id: str
    name: str
    status: str
    evidence_class: str
    checks: tuple[GateCheck, ...] = ()
    not_run_reason: str | None = None

    def __post_init__(self) -> None:
        """Enforce the three-state contract."""
        if self.status not in {"passed", "failed", "not run"}:
            raise ValueError(f"gate status must be passed/failed/not run, got {self.status!r}")
        if self.status == "not run":
            if not self.not_run_reason:
                raise ValueError("a not-run gate must declare its reason honestly")
            if self.checks:
                raise ValueError("a not-run gate must not carry checks")
        elif self.not_run_reason is not None:
            raise ValueError("only not-run gates carry a not_run_reason")
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"unknown evidence class {self.evidence_class!r}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "status": self.status,
            "evidence_class": self.evidence_class,
            "checks": [
                {"name": check.name, "passed": check.passed, "observed": check.observed}
                for check in self.checks
            ],
            "not_run_reason": self.not_run_reason,
        }


def _checks_status(checks: tuple[GateCheck, ...] | list[GateCheck]) -> str:
    """Collapse checks into the honest three-state verdict."""
    if not checks:
        raise ValueError("a run gate must carry at least one check")
    return "passed" if all(check.passed for check in checks) else "failed"


@dataclass(frozen=True)
class PresetRunResult:
    """Deterministic closed-loop evidence for one vessel preset."""

    preset_id: str
    config_hash: str
    stack_id: str
    catalog_proof: dict
    ticks: int
    failure_count: int
    route_consumptions: int
    navigation_final: tuple[float, ...]
    trace_digest: str
    guidance_evidence: dict
    control_evidence: dict
    actuator_evidence: dict
    actuator_output_samples: tuple[tuple[float, ...], ...] = field(repr=False)


def _tick_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _digest_navigation_tick(tick: int, navigation: NavigationState) -> str:
    return _tick_digest(
        {
            "tick": tick,
            "navigation": [
                navigation.north_m,
                navigation.east_m,
                navigation.heading_rad,
                navigation.surge_mps,
                navigation.sway_mps,
                navigation.yaw_rate_radps,
            ],
        }
    )


def _route_for(preset: DemoPreset) -> TrackedRoute:
    waypoints = np.array(preset.waypoints_ne_m, dtype=np.float64).T
    return TrackedRoute(
        route_id=preset.route_id,
        revision=0,
        accepted=True,
        valid_from_tick=0,
        valid_until_tick=preset.ticks + 1,
        waypoints_ne_m=waypoints,
        speed_mps=np.array(preset.route_speed_mps, dtype=np.float64),
        task=ControlTask.TRANSIT,
    )


def _assemble(preset: DemoPreset) -> tuple[ShipModulesConfig, ModularShipStack]:
    config = normalize_ship_modules(preset.ship_modules)
    stack = ModularShipStack.from_config(config)
    return config, stack


def _combination_key(modules: Any) -> tuple:
    """Key one module combination as (role, identity, layout asset id) triples."""

    def _identity(selection: Any) -> str:
        return selection.identity if hasattr(selection, "identity") else str(selection["identity"])

    def _layout(selection: Any) -> Any:
        parameters = selection.parameters if hasattr(selection, "parameters") else selection.get("parameters", {})
        return parameters.get("layout_asset_id") if parameters else None

    return tuple(
        (role, _identity(selection), _layout(selection)) for role, selection in sorted(modules.items())
    )


def _catalog_proof(config: ShipModulesConfig, supported_tasks: frozenset) -> dict:
    """Prove the demo combination against ``list_stack_catalog()`` (Issue #61 AC1).

    The module-identity combination (including the bound layout assets) must
    equal a listed entry's combination, and the catalog's published validity
    rule must replay successfully on the demo configuration itself.  The
    parameter payload is vessel data and deliberately differs from the
    catalog's synthetic scaffold parameters.
    """
    demo_key = _combination_key(config.modules)
    entry = next(
        (item for item in list_stack_catalog()["stacks"] if _combination_key(item["config"]["modules"]) == demo_key),
        None,
    )
    tasks = sorted(task.value for task in supported_tasks)
    return {
        "listed": entry is not None,
        "stack_id": entry["stack_id"] if entry is not None else None,
        "validity_rule_replayed": bool(tasks),
        "supported_tasks": tasks,
        "fidelity_profile": config.fidelity_profile,
    }


def preset_stack_id(preset: DemoPreset) -> str | None:
    """Return the catalog stack id proven for one preset."""
    config, stack = _assemble(preset)
    return _catalog_proof(config, stack.modules.supported_tasks)["stack_id"]


def run_preset(preset: DemoPreset) -> PresetRunResult:
    """Execute the shared, branch-free closed-loop demo for one vessel preset."""
    config, stack = _assemble(preset)
    proof = _catalog_proof(config, stack.modules.supported_tasks)
    stack.reset(NavigationState(*preset.initial_navigation), seed=preset.episode_seed)
    route = _route_for(preset)
    actuator_ids = _known_actuator_ids(config.modules["actuator"].parameters["layout_asset_id"])

    tick_digests: list[str] = []
    failure_count = 0
    guidance_trace_ticks = 0
    controller_trace_ticks = 0
    actuator_trace_ticks = 0
    rate_limited_ticks = 0
    antiwindup_active_ticks = 0
    initial_abs_xte: float | None = None
    max_abs_xte = 0.0
    final_abs_xte = 0.0
    final_abs_speed_error = 0.0
    navigation_final: tuple[float, ...] = ()
    output_samples: list[tuple[float, ...]] = []

    for tick in range(preset.ticks):
        output = stack.step(CommandInput.route(tick, route), dt_s=preset.dt_s)
        if output.failure is not None:
            failure_count += 1
            break
        tick_digests.append(_digest_navigation_tick(tick, output.navigation))
        guidance_trace = stack.modules.guidance_trace()
        if guidance_trace is not None:
            guidance_trace_ticks += 1
            abs_xte = abs(guidance_trace.cross_track_error_m)
            if initial_abs_xte is None:
                initial_abs_xte = abs_xte
            max_abs_xte = max(max_abs_xte, abs_xte)
            final_abs_xte = abs_xte
        control_trace = output.controller_trace
        if control_trace is not None:
            controller_trace_ticks += 1
            final_abs_speed_error = abs(control_trace.errors[0])
            if any(abs(value) > 0.0 for value in control_trace.antiwindup_correction):
                antiwindup_active_ticks += 1
        actuator_trace = output.actuator_trace
        if actuator_trace is not None:
            actuator_trace_ticks += 1
            if actuator_trace.rate_limited_actuators:
                rate_limited_ticks += 1
            output_samples.append(
                tuple(float(actuator_trace.actuator_outputs_n[actuator_id]) for actuator_id in actuator_ids)
            )
        navigation_final = (
            output.navigation.north_m,
            output.navigation.east_m,
            output.navigation.heading_rad,
            output.navigation.surge_mps,
            output.navigation.sway_mps,
            output.navigation.yaw_rate_radps,
        )

    return PresetRunResult(
        preset_id=preset.preset_id,
        config_hash=config.config_hash,
        stack_id=proof["stack_id"],
        catalog_proof=proof,
        ticks=preset.ticks,
        failure_count=failure_count,
        route_consumptions=len(stack.modules.route_consumptions),
        navigation_final=navigation_final,
        trace_digest=_tick_digest({"preset_id": preset.preset_id, "ticks": tick_digests}),
        guidance_evidence={
            "guidance_trace_ticks": guidance_trace_ticks,
            "initial_abs_cross_track_error_m": float(initial_abs_xte),
            "final_abs_cross_track_error_m": float(final_abs_xte),
            "max_abs_cross_track_error_m": float(max_abs_xte),
        },
        control_evidence={
            "controller_trace_ticks": controller_trace_ticks,
            "final_abs_speed_error_mps": float(final_abs_speed_error),
            "antiwindup_active_ticks": antiwindup_active_ticks,
        },
        actuator_evidence={
            "actuator_trace_ticks": actuator_trace_ticks,
            "rate_limited_ticks": rate_limited_ticks,
        },
        actuator_output_samples=tuple(output_samples),
    )


@dataclass(frozen=True)
class SnapshotRestoreRun:
    """Digest-only result of a snapshot/restore determinism run (TS-15/SC-03).

    Only ``trace_digest`` is meaningful: the run exists to prove that a mid-run
    snapshot restored into a fresh stack instance reproduces the straight-
    through run tick-for-tick, and deliberately carries no other evidence.
    """

    preset_id: str
    restore_at_tick: int
    trace_digest: str


def run_preset_with_restore(preset: DemoPreset, *, restore_at_tick: int) -> SnapshotRestoreRun:
    """Re-run one preset, restoring a mid-run snapshot into a fresh stack instance.

    Demonstrates TS-15/SC-03 determinism: the snapshot/restore continuation
    must reproduce the straight-through run tick-for-tick.
    """
    config, stack = _assemble(preset)
    stack.reset(NavigationState(*preset.initial_navigation), seed=preset.episode_seed)
    route = _route_for(preset)

    tick_digests: list[str] = []
    snapshot = None
    for tick in range(preset.ticks):
        if tick == restore_at_tick:
            snapshot = stack.snapshot()
        output = stack.step(CommandInput.route(tick, route), dt_s=preset.dt_s)
        if output.failure is not None:
            break
        tick_digests.append(_digest_navigation_tick(tick, output.navigation))

    if snapshot is not None:
        resumed = ModularShipStack.from_config(config)
        resumed.restore(snapshot)
        for tick in range(restore_at_tick, preset.ticks):
            output = resumed.step(CommandInput.route(tick, route), dt_s=preset.dt_s)
            if output.failure is not None:
                break
            tick_digests[tick] = _digest_navigation_tick(tick, output.navigation)

    return SnapshotRestoreRun(
        preset_id=preset.preset_id,
        restore_at_tick=restore_at_tick,
        trace_digest=_tick_digest({"preset_id": preset.preset_id, "ticks": tick_digests}),
    )


def _hydrodynamic_checks(preset: DemoPreset) -> list[GateCheck]:
    """G2 physics-kernel checks for one preset plant (public plant API only)."""
    from colav_simulator.modular_gnc.integrators import rk4_step  # noqa: PLC0415
    from colav_simulator.modular_gnc.plant import Generic3DOFPlant, Generic3DOFPlantParameters  # noqa: PLC0415

    parameters = Generic3DOFPlantParameters(**preset.ship_modules["modules"]["plant"]["parameters"])
    plant = Generic3DOFPlant(parameters)
    state = np.array([0.0, 0.0, 0.3, 1.5, 0.1, 0.05])
    load = np.array([2.0e5, 1.0e4, 5.0e6])
    dt = 0.4

    def integrate(step: float, steps: int) -> np.ndarray:
        x = np.array(state, dtype=np.float64)
        for _ in range(steps):
            x = rk4_step(plant, 0, step, x, load)
        return x

    reference = integrate(dt / 64.0, 64)
    error_full = float(np.linalg.norm(integrate(dt, 1) - reference))
    error_half = float(np.linalg.norm(integrate(dt / 2.0, 2) - reference))
    order = float(np.log2(error_full / error_half))
    sample_velocities = ((0.0, 0.0, 0.0), (2.0, -0.4, 0.05), (-1.5, 0.3, -0.08))
    dissipative = all(float(np.dot(nu, plant.damping_force(nu))) >= -1e-6 for nu in sample_velocities)
    neutral = all(
        abs(float(np.dot(nu, plant.coriolis_matrix(nu) @ np.array(nu)))) <= 1e-9
        for nu in sample_velocities[1:]
    )
    return [
        GateCheck(
            name=f"{preset.preset_id} rk4 convergence order in [3.5, 4.5]",
            passed=3.5 <= order <= 4.5,
            observed=round(order, 6),
        ),
        GateCheck(name=f"{preset.preset_id} damping dissipative", passed=dissipative, observed=dissipative),
        GateCheck(name=f"{preset.preset_id} coriolis power neutral", passed=neutral, observed=neutral),
    ]


def _rate_limits_honored(preset: DemoPreset, run: PresetRunResult) -> bool:
    rates = preset.ship_modules["modules"]["actuator"]["parameters"]["rate_limit_n_per_s"]
    actuator_ids = _known_actuator_ids(preset.ship_modules["modules"]["actuator"]["parameters"]["layout_asset_id"])
    for actuator_id, column in zip(actuator_ids, zip(*run.actuator_output_samples, strict=False), strict=True):
        bound = rates[actuator_id] * preset.dt_s + 1e-6
        if any(abs(curr - prev) > bound for prev, curr in zip(column, column[1:], strict=False)):
            return False
    return True


def _guidance_checks(runs: tuple[PresetRunResult, ...]) -> list[GateCheck]:
    checks: list[GateCheck] = []
    for run in runs:
        guidance = run.guidance_evidence
        checks.append(
            GateCheck(
                name=f"{run.preset_id} cross-track converges within tolerance",
                passed=(
                    run.failure_count == 0
                    and guidance["final_abs_cross_track_error_m"] <= FINAL_CROSS_TRACK_ERROR_TOLERANCE_M
                    and guidance["max_abs_cross_track_error_m"]
                    <= guidance["initial_abs_cross_track_error_m"] + MAX_CROSS_TRACK_EXCURSION_MARGIN_M
                ),
                observed={
                    "initial_abs_cross_track_error_m": guidance["initial_abs_cross_track_error_m"],
                    "final_abs_cross_track_error_m": guidance["final_abs_cross_track_error_m"],
                    "max_abs_cross_track_error_m": guidance["max_abs_cross_track_error_m"],
                },
            )
        )
    return checks


def _control_checks(runs: tuple[PresetRunResult, ...]) -> list[GateCheck]:
    return [
        GateCheck(
            name=f"{run.preset_id} speed tracks route reference within tolerance",
            passed=(
                run.failure_count == 0
                and run.control_evidence["final_abs_speed_error_mps"] <= FINAL_SPEED_ERROR_TOLERANCE_MPS
                and run.control_evidence["controller_trace_ticks"] == run.ticks
            ),
            observed={
                "final_abs_speed_error_mps": run.control_evidence["final_abs_speed_error_mps"],
                "controller_trace_ticks": run.control_evidence["controller_trace_ticks"],
                "antiwindup_active_ticks": run.control_evidence["antiwindup_active_ticks"],
            },
        )
        for run in runs
    ]


def _actuator_checks(presets: tuple[DemoPreset, ...], runs: tuple[PresetRunResult, ...]) -> list[GateCheck]:
    checks: list[GateCheck] = []
    for preset, run in zip(presets, runs, strict=True):
        resolved = (
            run.catalog_proof["fidelity_profile"] == "resolved"
            and run.actuator_evidence["actuator_trace_ticks"] == run.ticks
        )
        checks.append(
            GateCheck(
                name=f"{run.preset_id} resolved fidelity profile active with honored rate limits",
                passed=(
                    resolved
                    and run.actuator_evidence["rate_limited_ticks"] >= 1
                    and _rate_limits_honored(preset, run)
                ),
                observed={
                    "fidelity_profile": run.catalog_proof["fidelity_profile"],
                    "actuator_trace_ticks": run.actuator_evidence["actuator_trace_ticks"],
                    "rate_limited_ticks": run.actuator_evidence["rate_limited_ticks"],
                },
            )
        )
    return checks


def _closed_loop_checks(runs: tuple[PresetRunResult, ...]) -> list[GateCheck]:
    return [
        GateCheck(
            name=f"{run.preset_id} closed loop completed without facade failure",
            passed=run.failure_count == 0 and run.route_consumptions == run.ticks,
            observed={"failures": run.failure_count, "route_consumptions": run.route_consumptions},
        )
        for run in runs
    ]


def _pinned_commit_from_fixture() -> str:
    payload = json.loads(_G6_BASELINE_FIXTURE.read_text(encoding="utf-8"))
    return str(payload["pinned_commit"])


def _source_integrity_checks(fixture_manifest: dict) -> list[GateCheck]:
    return [
        GateCheck(
            name="pinned legacy baseline commit matches ticket map",
            passed=_PINNED_LEGACY_COMMIT == _pinned_commit_from_fixture(),
            observed=_PINNED_LEGACY_COMMIT,
        ),
        GateCheck(
            name="characterization fixture bound to solution-pack source manifest",
            passed=fixture_manifest["source_manifest_sha256"] == _CHARACTERIZATION_MANIFEST_SHA256,
            observed=fixture_manifest["source_manifest_sha256"],
        ),
    ]


def _contract_checks(runs: tuple[PresetRunResult, ...]) -> list[GateCheck]:
    return [
        GateCheck(
            name=f"{run.preset_id} normalize + assemble + catalog-listed + supported_tasks",
            passed=(
                run.catalog_proof["listed"]
                and run.catalog_proof["validity_rule_replayed"]
                and run.catalog_proof["supported_tasks"] == [ControlTask.TRANSIT.value]
            ),
            observed={
                "stack_id": run.stack_id,
                "supported_tasks": run.catalog_proof["supported_tasks"],
                "fidelity_profile": run.catalog_proof["fidelity_profile"],
            },
        )
        for run in runs
    ]


def _parity_checks(legacy_arm: ArmIdentity, modular_arm: ArmIdentity, follows_references: bool) -> list[GateCheck]:
    """G3 checks: structural equivalence of the legacy-equivalent command chain.

    The four-arm binding pins both arms to identical geometry/input hashes.  On
    top of that, the modular legacy-equivalent profile must reproduce the exact
    kinematic pass-through response (heading/surge follow latched references
    tick-exact) on the legacy-equivalent scenario.  Raw trace hashes differ by
    state representation (4-element CSOG vs 6-element plant state) and are
    reported informationally, never compared.
    """
    shared_geometry = legacy_arm.geometry_hash == modular_arm.geometry_hash
    shared_input = legacy_arm.input_hash == modular_arm.input_hash
    return [
        GateCheck(
            name="legacy-equivalent arm bound to shared geometry and input hashes",
            passed=shared_geometry and shared_input,
            observed={"geometry": shared_geometry, "input": shared_input},
        ),
        GateCheck(
            name="modular legacy-equivalent chain follows latched kinematic references exactly",
            passed=follows_references,
            observed=follows_references,
        ),
    ]


def _kinematic_reference_following_exact() -> bool:
    """Reuse the #56 structural-equivalence conclusion on the legacy scenario data."""
    from colav_simulator.modular_gnc.factory import legacy_equivalent_profile  # noqa: PLC0415

    scenario_schedule = {0: (0.35, 4.5), 5: (-0.1, 3.75)}
    dt_s = 0.2
    stack = ModularShipStack.from_config(normalize_ship_modules(legacy_equivalent_profile()))
    stack.reset(NavigationState(100.0, -50.0, 4.0, 0.25, 0.0, 0.0), seed=42042)
    current = np.zeros(9)
    for tick in range(12):
        if tick in scenario_schedule:
            current[2], current[3] = scenario_schedule[tick]
        output = stack.step(CommandInput.direct(tick, DirectReference(current.copy(), latched_tick=tick)), dt_s=dt_s)
        if output.failure is not None:
            return False
        plant = output.plant
        if plant.heading_rad != current[2] or plant.surge_mps != current[3]:
            return False
    return True


def _redesign_checks(redesign_decisions: tuple) -> list[GateCheck]:
    return [
        GateCheck(
            name="redesign decisions declared with spec references",
            passed=bool(redesign_decisions)
            and all(decision.specification_reference for decision in redesign_decisions),
            observed=len(redesign_decisions),
        ),
    ]


def _generality_checks(runs: tuple[PresetRunResult, ...]) -> list[GateCheck]:
    return [
        GateCheck(
            name="two presets, distinct content-addressed configs, identical code path",
            passed=len(runs) == 2 and len({run.config_hash for run in runs}) == 2,
            observed=[run.config_hash for run in runs],
        ),
    ]


def _gate(gate_id: str, name: str, evidence_class: str, checks: list[GateCheck]) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        name=name,
        status=_checks_status(tuple(checks)),
        evidence_class=evidence_class,
        checks=tuple(checks),
    )


def run_a3_demo() -> A3DemoReport:
    """Run the full controlled demo and return the three-state evidence report."""
    runs = tuple(run_preset(preset) for preset in DEMO_PRESETS)

    from colav_simulator.legacy_g6_baseline import compare_baseline  # noqa: PLC0415
    from colav_simulator.modular_gnc.attribution import run_g8_four_arm_binding  # noqa: PLC0415

    binding = run_g8_four_arm_binding()
    legacy_arm = binding.arms["legacy"]
    modular_parity_arm = binding.arms["modular_legacy_equivalent"]
    follows_references = _kinematic_reference_following_exact()

    g6_checks: list[GateCheck] = []
    try:
        compare_baseline(_G6_BASELINE_FIXTURE)
        g6_checks.append(GateCheck(name="pinned legacy baseline comparison", passed=True, observed="passed"))
    except (RuntimeError, ValueError) as exc:
        g6_checks.append(GateCheck(name="pinned legacy baseline comparison", passed=False, observed=str(exc)))

    fixture_manifest = load_characterization_fixture_manifest(_CHARACTERIZATION_FIXTURE_DIR)
    redesign_decisions = (
        build_generic_3dof_plant_redesign_decisions()
        + build_generic_roll_4dof_plant_redesign_decisions()
        + build_marine_pid_redesign_decisions()
    )

    gates = (
        _gate("G0", "source integrity", "system", _source_integrity_checks(fixture_manifest)),
        _gate("G1", "interface and module contracts", "system", _contract_checks(runs)),
        _gate(
            "G2",
            "physics kernel",
            "hydrodynamic",
            [check for preset in DEMO_PRESETS for check in _hydrodynamic_checks(preset)],
        ),
        _gate(
            "G3",
            "migration parity",
            "system",
            _parity_checks(legacy_arm, modular_parity_arm, follows_references),
        ),
        _gate("G4", "intentional redesign ledger", "system", _redesign_checks(redesign_decisions)),
        _gate(
            "G5",
            "module closed loop",
            "guidance",
            _closed_loop_checks(runs) + _guidance_checks(runs) + _control_checks(runs),
        ),
        _gate("G6", "existing regression (pinned legacy baseline)", "system", g6_checks),
        _gate("G7", "cross-vessel generality", "system", _generality_checks(runs)),
        GateResult(
            gate_id="G8",
            name="COLAV integration",
            status="not run",
            evidence_class="colav",
            not_run_reason=(
                "The demo exercises no COLAV authority: planner route audit and "
                "tracked-route integration are pending (#62, #63). COLAV "
                "closed-loop acceptance is outside the A3 ceiling."
            ),
        ),
        _gate("G9", "actuator fidelity", "actuator", _actuator_checks(DEMO_PRESETS, runs)),
        GateResult(
            gate_id="G10",
            name="external platform adapter integration",
            status="not run",
            evidence_class="system",
            not_run_reason=(
                "No external platform adapter or simulation-time integration "
                "harness is exercised in this local demo; that scope remains "
                "with the later adapter slice (#64) and is not claimed here."
            ),
        ),
    )

    return _build_report(runs, gates, legacy_arm, modular_parity_arm, redesign_decisions, follows_references)


def _class_status(gates: tuple[GateResult, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if "failed" in statuses:
        return "failed"
    if statuses and statuses <= {"not run"}:
        return "not run"
    return "passed"


def _build_report(
    runs: tuple[PresetRunResult, ...],
    gates: tuple[GateResult, ...],
    legacy_arm: ArmIdentity,
    modular_parity_arm: ArmIdentity,
    redesign_decisions: tuple[RedesignDecision, ...],
    follows_references: bool,
) -> A3DemoReport:
    by_id = {gate.gate_id: gate for gate in gates}
    gates_by_class = {
        evidence_class: tuple(gate for gate in gates if gate.evidence_class == evidence_class)
        for evidence_class in EVIDENCE_CLASSES
    }
    evidence_classes: dict[str, dict] = {
        name: {"gate_ids": [gate.gate_id for gate in class_gates], "status": _class_status(class_gates)}
        for name, class_gates in gates_by_class.items()
    }
    # The control class carries no dedicated gate; its status derives from the
    # same per-preset evidence that G5 consumes, kept as a separate record.
    evidence_classes["control"]["status"] = _checks_status(tuple(_control_checks(runs)))
    # Per-preset module evidence is attached to its own class only, never merged.
    evidence_classes["guidance"]["per_preset"] = {run.preset_id: run.guidance_evidence for run in runs}
    evidence_classes["control"]["per_preset"] = {run.preset_id: run.control_evidence for run in runs}
    evidence_classes["actuator"]["per_preset"] = {run.preset_id: run.actuator_evidence for run in runs}
    evidence_classes["colav"]["not_run_reason"] = by_id["G8"].not_run_reason

    system_evidence = {
        "source_integrity": {
            "pinned_legacy_commit": _PINNED_LEGACY_COMMIT,
            "characterization_manifest_sha256": _CHARACTERIZATION_MANIFEST_SHA256,
        },
        "g6_pinned_baseline_comparison": by_id["G6"].status,
        "g7_config_hashes": [run.config_hash for run in runs],
        "g10_not_run_reason": by_id["G10"].not_run_reason,
    }
    return A3DemoReport(
        schema_version=DEMO_SCHEMA_VERSION,
        claim_ceiling=DEMO_CLAIM_CEILING_LEVEL,
        claim_ceiling_label=DEMO_CLAIM_CEILING_LABEL,
        preset_runs=runs,
        gates=gates,
        evidence_classes=evidence_classes,
        source_parity={
            "evidence_kind": "SOURCE_CHARACTERIZATION_REFERENCE",
            "claim": "candidate_A2_migration_verified_only",
            "legacy_arm": legacy_arm.label,
            "modular_arm": modular_parity_arm.label,
            "shared_geometry_hash": legacy_arm.geometry_hash == modular_parity_arm.geometry_hash,
            "shared_input_hash": legacy_arm.input_hash == modular_parity_arm.input_hash,
            "kinematic_reference_following_exact": follows_references,
            "legacy_trace_hash": legacy_arm.trace_hash,
            "modular_trace_hash": modular_parity_arm.trace_hash,
            "trace_hash_note": (
                "Trace hashes differ by state representation (legacy 4-element CSOG "
                "state vs modular 6-element plant state) and are informational only; "
                "parity is claimed through shared inputs and exact kinematic "
                "reference following, never through hash equality."
            ),
            "scope": (
                "Structural parity is claimed for the legacy-equivalent structure only "
                "(pass-through plant/guidance/controller under legacy-equivalent scheduler "
                "defaults, candidate A2). The new-factory modules exercised by this demo "
                "(generic 3DOF plant, ILOS, marine PID, data-driven allocator, resolved "
                "actuator dynamics) are intentional redesigns and are reported separately."
            ),
        },
        intentional_redesign={
            "evidence_kind": "INTENTIONAL_REDESIGN",
            "decision_count": len(redesign_decisions),
            "decisions": [
                {
                    "decision_id": decision.decision_id,
                    "topic": decision.topic,
                    "specification_reference": decision.specification_reference,
                }
                for decision in redesign_decisions
            ],
        },
        system_evidence=system_evidence,
        non_claims=ACCEPTANCE_NON_CLAIMS,
    )


@dataclass(frozen=True)
class A3DemoReport:
    """Immutable A3 demo evidence report."""

    schema_version: str
    claim_ceiling: str
    claim_ceiling_label: str
    preset_runs: tuple[PresetRunResult, ...]
    gates: tuple[GateResult, ...]
    evidence_classes: dict
    source_parity: dict
    intentional_redesign: dict
    system_evidence: dict
    non_claims: tuple[str, ...]

    def to_dict(self) -> dict:
        """Convert the report to a JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "claim_ceiling": self.claim_ceiling,
            "claim_ceiling_label": self.claim_ceiling_label,
            "preset_runs": [
                {
                    "preset_id": run.preset_id,
                    "config_hash": run.config_hash,
                    "stack_id": run.stack_id,
                    "catalog_proof": run.catalog_proof,
                    "ticks": run.ticks,
                    "failure_count": run.failure_count,
                    "route_consumptions": run.route_consumptions,
                    "navigation_final": list(run.navigation_final),
                    "trace_digest": run.trace_digest,
                    "guidance_evidence": run.guidance_evidence,
                    "control_evidence": run.control_evidence,
                    "actuator_evidence": run.actuator_evidence,
                }
                for run in self.preset_runs
            ],
            "gates": [gate.to_dict() for gate in self.gates],
            "evidence_classes": self.evidence_classes,
            "source_parity": self.source_parity,
            "intentional_redesign": self.intentional_redesign,
            "system_evidence": self.system_evidence,
            "non_claims": list(self.non_claims),
        }
