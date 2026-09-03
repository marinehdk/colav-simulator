"""Valid modular stack catalog: Python-side single source of stack validity (Issue #60).

A candidate stack is listed only when ``normalize_ship_modules`` accepts it,
``ModularShipStack.from_config`` assembles it, and its ``supported_tasks``
intersection is non-empty.  UI consumers only render the resulting document;
no validation is reimplemented on the client.

Evidence identity is exposed as separated fields (Issue #60 AC2): per-module
maturity (registry interface version), stack fidelity profile, per-asset trust
level, and acceptance level.  Acceptance claims record only accepted facts
(interface/module contracts, candidate-A2 migration parity) and never imply
vessel validation or any level beyond the phase ceiling.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import lru_cache
from types import MappingProxyType
from typing import Any

from colav_simulator.modular_gnc.allocator import KNOWN_ACTUATOR_LAYOUT_ASSETS
from colav_simulator.modular_gnc.configuration import (
    KNOWN_ACTUATOR_LAYOUT_ASSET_IDS,
    REGISTRY_V1,
    ShipModulesConfig,
    normalize_ship_modules,
)
from colav_simulator.modular_gnc.contracts import ControlTask
from colav_simulator.modular_gnc.stack import ModularShipStack

STACK_CATALOG_SCHEMA_VERSION = "modular-gnc.stack-catalog.v1"
STACK_EVIDENCE_SCHEMA_VERSION = "modular-gnc.stack-evidence.v1"

# Declaration ceiling for this phase (solution-pack A1-A3): entries may only
# claim their accepted module evidence; higher levels are never claimed.
ACCEPTANCE_CEILING_LEVEL = "A3"
ACCEPTANCE_CEILING_LABEL = "Generalized Simulation"

# Accepted evidence facts per module identity (Issue #60 AC2/AC3/AC5).  These
# strings are claims vocabulary, not grades: they never assert vessel
# validation or any acceptance level beyond the phase ceiling.
ACCEPTANCE_EVIDENCE_BY_IDENTITY: Mapping[str, str] = MappingProxyType(
    {
        "pass_through_plant": "interface_contract",
        "pass_through_guidance": "interface_contract",
        "pass_through_controller": "interface_contract",
        "generic_3dof_plant": "candidate_a2_migration_parity",
        "generic_roll_4dof_plant": "candidate_a2_migration_parity",
        "integral_line_of_sight": "module_closed_loop_contract",
        "marine_pid": "controller_contract",
        "data_driven_allocator": "module_closed_loop_contract",
        "resolved_actuator_dynamics": "module_closed_loop_contract",
    }
)

_ACCEPTANCE_RANK: Mapping[str, int] = MappingProxyType(
    {
        "interface_contract": 0,
        "controller_contract": 1,
        "module_closed_loop_contract": 1,
        "candidate_a2_migration_parity": 2,
    }
)

_DISPLAY_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "pass_through_plant": "Kinematic pass-through plant",
        "generic_3dof_plant": "Generic 3DOF plant",
        "generic_roll_4dof_plant": "Generic 4DOF Plant",
        "pass_through_guidance": "Pass-through guidance",
        "integral_line_of_sight": "Integral LOS guidance",
        "pass_through_controller": "Pass-through controller",
        "marine_pid": "Marine PID controller",
        "data_driven_allocator": "Data-driven allocator",
        "resolved_actuator_dynamics": "Resolved actuator dynamics",
    }
)

_ROLE_ORDER: tuple[str, ...] = ("plant", "guidance", "controller", "environment", "load_model", "allocator", "actuator")

_CANDIDATE_PLANT_IDENTITIES: tuple[str, ...] = ("pass_through_plant", "generic_3dof_plant", "generic_roll_4dof_plant")
_CANDIDATE_GUIDANCE_IDENTITIES: tuple[str, ...] = ("pass_through_guidance", "integral_line_of_sight")
_CANDIDATE_CONTROLLER_IDENTITIES: tuple[str, ...] = ("pass_through_controller", "marine_pid")
_CANDIDATE_ALLOCATOR_LAYOUTS: tuple[str, ...] = tuple(sorted(KNOWN_ACTUATOR_LAYOUT_ASSET_IDS))

# Config step 04: per-axis fidelity ladders.  Array order is the ladder order
# (simpler first); ``tier`` is the machine-readable form of the same order.
# Copy is backend-authored and honest: scaffold/mock assets are declared as
# such and no fidelity beyond this phase is claimed.
_MODULE_AXIS_COPY: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "pass_through_plant": MappingProxyType(
            {
                "models": (
                    "Kinematic pass-through: reference heading and speed are written directly into the state, "
                    "no dynamics."
                ),
                "expected_effect": "Zero dynamic lag; control commands act immediately. Serves as the algorithm baseline.",
            }
        ),
        "generic_3dof_plant": MappingProxyType(
            {
                "models": (
                    "3DOF hydrodynamics: mass plus added mass, Coriolis, damping, and restoration "
                    "(catalog parameters are a synthetic scaffold with zero default damping)."
                ),
                "expected_effect": (
                    "Maneuvers evolve with inertia and coupling; scaffold parameters are not a real vessel scale."
                ),
            }
        ),
        "generic_roll_4dof_plant": MappingProxyType(
            {
                "models": "3DOF plus roll restoration (the roll degree of freedom is uncontrolled).",
                "expected_effect": "Roll participates in the response; allocator and actuator modules stay strictly 3DOF.",
            }
        ),
        "pass_through_guidance": MappingProxyType(
            {
                "models": "Pass-through: adopts the planner reference directly.",
                "expected_effect": "No additional guidance behavior; the reference is followed as given.",
            }
        ),
        "integral_line_of_sight": MappingProxyType(
            {
                "models": "Integral LOS: cross-track-error-gated integral action, progress, and speed limiting.",
                "expected_effect": "Smooths path following and bounds cross-track error on top of the planner reference.",
            }
        ),
        "pass_through_controller": MappingProxyType(
            {
                "models": "Pass-through: forwards the guidance command unchanged.",
                "expected_effect": "No control-loop dynamics between guidance and the plant.",
            }
        ),
        "marine_pid": MappingProxyType(
            {
                "models": (
                    "Transparent marine PID producing generalized forces "
                    "(configurable only with a hydrodynamic plant)."
                ),
                "expected_effect": (
                    "Closed-loop tracking of heading and speed references; requires plant dynamics to act on."
                ),
            }
        ),
        "resolved_actuator_dynamics": MappingProxyType(
            {
                "models": "Actuator rate limits and delay.",
                "expected_effect": "During hard maneuvers actuators lag the command; response bandwidth is limited.",
            }
        ),
    }
)

# Allocator layout assets are synthetic mock scaffolds; the drive nature is the
# honest statement of what each layout can and cannot achieve.
_ACTUATION_LAYOUT_TIER = 1
_ACTUATION_LAYOUTS: tuple[Mapping[str, str], ...] = (
    MappingProxyType(
        {
            "layout_asset_id": "default_triple_actuator_layout_v1",
            "display_name": "Triple thruster layout",
            "drive_nature": "fully actuated",
            "expected_effect": (
                "Requested surge, sway, and yaw generalized forces are achievable within actuator limits."
            ),
        }
    ),
    MappingProxyType(
        {
            "layout_asset_id": "quad_diagonal_actuator_layout_v1",
            "display_name": "Quad diagonal layout",
            "drive_nature": "overactuated",
            "expected_effect": "More actuators than degrees of freedom; allocation carries redundancy margin.",
        }
    ),
    MappingProxyType(
        {
            "layout_asset_id": "main_only_actuator_layout_v1",
            "display_name": "Main thruster only",
            "drive_nature": "underactuated",
            "expected_effect": (
                "Lateral force and yaw authority are limited; requested forces are only partially achievable."
            ),
        }
    ),
)
_ALLOCATOR_MODELS_COPY = (
    "Allocation of generalized forces to actuators by minimum norm; the layout asset is a synthetic mock asset."
)


def _axis_entry(identity: str, tier: int, display_name: str | None = None) -> dict[str, Any]:
    copy = _MODULE_AXIS_COPY[identity]
    return {
        "identity": identity,
        "display_name": display_name or _DISPLAY_NAMES[identity],
        "tier": tier,
        "models": copy["models"],
        "expected_effect": copy["expected_effect"],
    }


def _module_axes() -> dict[str, Any]:
    """Return the per-axis option ladders consumed by the Config step 04 UI."""
    return {
        "plant": [
            _axis_entry("pass_through_plant", 0),
            _axis_entry("generic_3dof_plant", 1),
            _axis_entry("generic_roll_4dof_plant", 2),
        ],
        "guidance": [
            _axis_entry("pass_through_guidance", 0),
            _axis_entry("integral_line_of_sight", 1),
        ],
        "controller": [
            _axis_entry("pass_through_controller", 0),
            _axis_entry("marine_pid", 1),
        ],
        "actuation": {
            "none": {
                "identity": None,
                "display_name": "No allocator (ideal generalized forces)",
                "tier": 0,
                "models": "No allocator module; generalized forces are applied as-is.",
                "expected_effect": "No allocation or actuator limits; the same command chain as the scenario default.",
            },
            "layouts": [
                {
                    "identity": "data_driven_allocator",
                    "layout_asset_id": layout["layout_asset_id"],
                    "display_name": layout["display_name"],
                    "drive_nature": layout["drive_nature"],
                    "tier": _ACTUATION_LAYOUT_TIER,
                    "models": _ALLOCATOR_MODELS_COPY,
                    "expected_effect": layout["expected_effect"],
                }
                for layout in _ACTUATION_LAYOUTS
            ],
            "resolved": _axis_entry("resolved_actuator_dynamics", 2),
        },
    }

# Synthetic scaffold parameters for identities whose registry schema requires
# values.  Same synthetic values as the modular contract tests; they are demo
# scaffolding, not measured vessel data.
_CANONICAL_MODULE_PARAMETERS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        "generic_3dof_plant": MappingProxyType({"mass_kg": 1.6e7, "i_z_kgm2": 3.0e10}),
        "generic_roll_4dof_plant": MappingProxyType({"mass_kg": 1.6e7, "i_x_kgm2": 2.0e10, "i_z_kgm2": 3.0e10}),
        "marine_pid": MappingProxyType(
            {
                # Closed-loop baseline scaled to the canonical synthetic plant
                # mass/inertia above. These are simulation scaffolding values,
                # not gains identified for a physical vessel.
                "kp": (1.6e6, 1.6e6, 1.92e8),
                "ki": (1.0e5, 1.0e5, 2.0e6),
                "kd": (0.0, 0.0, 3.84e9),
                "tau_d": (0.1, 0.1, 0.1),
                "antiwindup_gain": (1.0, 1.0, 1.0),
                "min_output": (-5.0e6, -5.0e6, -6.0e8),
                "max_output": (5.0e6, 5.0e6, 6.0e8),
                "feedforward_gain": (0.0, 0.0, 0.0),
                "integral_limit": (50.0, 50.0, 5.0),
                "allow_ideal_passthrough": True,
            }
        ),
    }
)


def _module_selections(config: ShipModulesConfig) -> list[dict[str, Any]]:
    """Return per-role module records with registry maturity and accepted evidence."""
    records = []
    for role in _ROLE_ORDER:
        selection = config.modules.get(role)
        if selection is None:
            continue
        entry = REGISTRY_V1[selection.identity]
        records.append(
            {
                "role": role,
                "identity": selection.identity,
                "implementation_version": entry.implementation_version,
                "interface_version": entry.interface_version,
                "available": bool(entry.available),
                "acceptance_evidence": ACCEPTANCE_EVIDENCE_BY_IDENTITY[selection.identity],
            }
        )
    return records


def _layout_asset_ids(config: ShipModulesConfig) -> list[str]:
    """Return the known actuator layout asset ids bound by this stack (deduplicated)."""
    layouts: list[str] = []
    for role in ("allocator", "actuator"):
        selection = config.modules.get(role)
        if selection is None:
            continue
        layout_id = selection.parameters.get("layout_asset_id")
        if layout_id is not None and layout_id not in layouts:
            layouts.append(str(layout_id))
    return layouts


def _asset_trust(config: ShipModulesConfig) -> list[dict[str, str]]:
    """Return per-asset trust records for the assets this stack binds (AC3).

    Trust values come verbatim from the immutable asset metadata; mock and
    inferred assets are therefore never presented as vessel-validated.
    """
    records: list[dict[str, str]] = []
    for layout_id in _layout_asset_ids(config):
        metadata = KNOWN_ACTUATOR_LAYOUT_ASSETS[layout_id].metadata
        records.append(
            {
                "asset_id": metadata.asset_id,
                "asset_type": metadata.asset_type,
                "trust_level": metadata.trust_level.value,
            }
        )
    return records


def _acceptance_level(config: ShipModulesConfig) -> str:
    """Return the weakest accepted-evidence claim across selected modules."""
    claims = [
        ACCEPTANCE_EVIDENCE_BY_IDENTITY[selection.identity] for selection in config.modules.values()
    ]
    return min(claims, key=lambda claim: (_ACCEPTANCE_RANK[claim], claim))


def _stack_id(config: ShipModulesConfig) -> str:
    parts = []
    for role in _ROLE_ORDER:
        selection = config.modules.get(role)
        if selection is None:
            continue
        layout = selection.parameters.get("layout_asset_id")
        parts.append(
            f"{selection.identity}[{layout}]" if layout is not None else selection.identity
        )
    return "+".join(parts)


def _display_name(config: ShipModulesConfig) -> str:
    parts = []
    for role in _ROLE_ORDER:
        selection = config.modules.get(role)
        if selection is None:
            continue
        parts.append(_DISPLAY_NAMES[selection.identity])
    name = " + ".join(parts)
    layouts = _layout_asset_ids(config)
    if layouts:
        name = f"{name} ({layouts[0]})"
    return name


def stack_evidence_document(
    config: ShipModulesConfig,
    *,
    supported_tasks: Iterable[ControlTask] | None = None,
) -> dict[str, Any]:
    """Return the separated evidence-label document for a normalized stack config.

    ``supported_tasks`` must come from an assembled stack (e.g.
    ``ModularShipStack.modules.supported_tasks``); when omitted the document
    assembles the stack itself to compute the task intersection.
    """
    if supported_tasks is None:
        stack = ModularShipStack.from_config(config)
        supported_tasks = stack.modules.supported_tasks
    return {
        "schema_version": STACK_EVIDENCE_SCHEMA_VERSION,
        "stack_id": _stack_id(config),
        "display_name": _display_name(config),
        "config_hash": config.config_hash,
        "fidelity_profile": config.fidelity_profile,
        "supported_tasks": sorted(task.value for task in supported_tasks),
        "modules": _module_selections(config),
        "asset_trust": _asset_trust(config),
        "acceptance_level": _acceptance_level(config),
        "config": config.to_dict(),
    }


def _resolved_actuator_parameters(layout: str) -> dict[str, Any]:
    """Return full-coverage synthetic scaffold parameters for one known layout.

    Rate limits and delays are declared per actuator id so no ideal pass-through
    assumption is hidden (no silent fallback, TS-22); the values are the same
    neutral scaffold used by the actuator-dynamics contract tests.
    """
    actuator_ids = KNOWN_ACTUATOR_LAYOUT_ASSETS[layout].actuator_ids()
    return {
        "layout_asset_id": layout,
        "rate_limit_n_per_s": dict.fromkeys(actuator_ids, 1000000000.0),
        "delay_ticks": dict.fromkeys(actuator_ids, 0),
    }


def _candidate_configs() -> Iterable[Mapping[str, Any]]:
    """Yield the deterministic candidate configuration space for enumeration."""
    for plant in _CANDIDATE_PLANT_IDENTITIES:
        for guidance in _CANDIDATE_GUIDANCE_IDENTITIES:
            for controller in _CANDIDATE_CONTROLLER_IDENTITIES:
                for layout in (None, *_CANDIDATE_ALLOCATOR_LAYOUTS):
                    for with_actuator in (False, True):
                        if with_actuator and layout is None:
                            continue
                        modules: dict[str, dict[str, Any]] = {
                            "plant": {
                                "identity": plant,
                                "parameters": dict(_CANONICAL_MODULE_PARAMETERS.get(plant, {})),
                            },
                            "guidance": {
                                "identity": guidance,
                                "parameters": dict(_CANONICAL_MODULE_PARAMETERS.get(guidance, {})),
                            },
                            "controller": {
                                "identity": controller,
                                "parameters": dict(_CANONICAL_MODULE_PARAMETERS.get(controller, {})),
                            },
                        }
                        candidate: dict[str, Any] = {"preset": "legacy_equivalent", "modules": modules}
                        if layout is not None:
                            modules["allocator"] = {
                                "identity": "data_driven_allocator",
                                "parameters": {"layout_asset_id": layout},
                            }
                            if with_actuator:
                                modules["actuator"] = {
                                    "identity": "resolved_actuator_dynamics",
                                    "parameters": _resolved_actuator_parameters(layout),
                                }
                                # Resolved actuator dynamics is a discrete phase on the base clock.
                                candidate["overrides"] = {"scheduler": {"controller_period_ticks": 1}}
                        yield candidate


def _product_transit_compatible(config: ShipModulesConfig, supported_tasks: Iterable[ControlTask]) -> bool:
    """Apply product-level command/load semantics on top of module assembly."""
    if ControlTask.TRANSIT not in supported_tasks:
        return False
    plant = config.modules["plant"].identity
    controller = config.modules["controller"].identity
    return not (
        plant in {"generic_3dof_plant", "generic_roll_4dof_plant"}
        and controller == "pass_through_controller"
    )


@lru_cache(maxsize=1)
def _cached_stack_catalog() -> tuple[dict[str, Any], ...]:
    """Validate every candidate through the assembly seam; keep only valid stacks."""
    entries: list[dict[str, Any]] = []
    for candidate in _candidate_configs():
        try:
            config = normalize_ship_modules(candidate)
            stack = ModularShipStack.from_config(config)
            supported_tasks = stack.modules.supported_tasks
        except (
            ValueError,
            TypeError,
            RuntimeError,
        ):  # UnsupportedModuleCombinationError / CapabilityMismatchError / DependencyUnavailableError
            continue
        if not _product_transit_compatible(config, supported_tasks):
            continue
        entries.append(stack_evidence_document(config, supported_tasks=supported_tasks))
    return tuple(entries)


def _recommended_stack_ids_by_plant(stacks: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Choose the first deterministic executable stack for each Plant option."""
    recommendations: dict[str, str] = {}
    for entry in stacks:
        plant_id = next(
            (module["identity"] for module in entry["modules"] if module["role"] == "plant"),
            None,
        )
        if plant_id is not None:
            recommendations.setdefault(plant_id, entry["stack_id"])
    return recommendations


def list_stack_catalog() -> dict[str, Any]:
    """Return the catalog document listing only backend-validated modular stacks."""
    stacks = list(_cached_stack_catalog())
    return {
        "schema_version": STACK_CATALOG_SCHEMA_VERSION,
        "acceptance_ceiling": {
            "level": ACCEPTANCE_CEILING_LEVEL,
            "label": ACCEPTANCE_CEILING_LABEL,
            "note": "Entries carry only their accepted module evidence; higher acceptance levels are not claimed.",
        },
        "validity_rule": (
            "normalize_ship_modules + ModularShipStack.from_config assembly + "
            "TRANSIT support + control-semantics compatibility"
        ),
        "default_stack_id": stacks[0]["stack_id"] if stacks else None,
        "recommended_stack_ids_by_plant": _recommended_stack_ids_by_plant(stacks),
        "module_axes": _module_axes(),
        "stacks": stacks,
    }
