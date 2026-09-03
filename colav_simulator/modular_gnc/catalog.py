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
        "generic_roll_4dof_plant": "Generic roll-4DOF plant",
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

# Synthetic scaffold parameters for identities whose registry schema requires
# values.  Same synthetic values as the modular contract tests; they are demo
# scaffolding, not measured vessel data.
_CANONICAL_MODULE_PARAMETERS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        "generic_3dof_plant": MappingProxyType({"mass_kg": 1.6e7, "i_z_kgm2": 3.0e10}),
        "generic_roll_4dof_plant": MappingProxyType({"mass_kg": 1.6e7, "i_x_kgm2": 2.0e10, "i_z_kgm2": 3.0e10}),
        "marine_pid": MappingProxyType(
            {
                "kp": (1000.0, 500.0, 2000.0),
                "ki": (100.0, 50.0, 200.0),
                "kd": (200.0, 100.0, 400.0),
                "tau_d": (0.1, 0.1, 0.1),
                "antiwindup_gain": (1.0, 1.0, 1.0),
                "min_output": (-10000.0, -5000.0, -20000.0),
                "max_output": (10000.0, 5000.0, 20000.0),
                "feedforward_gain": (0.0, 0.0, 0.0),
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
        if not supported_tasks:
            continue
        entries.append(stack_evidence_document(config, supported_tasks=supported_tasks))
    return tuple(entries)


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
        "validity_rule": "normalize_ship_modules + ModularShipStack.from_config assembly + non-empty supported_tasks",
        "default_stack_id": stacks[0]["stack_id"] if stacks else None,
        "stacks": stacks,
    }
