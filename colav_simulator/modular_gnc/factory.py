"""Opt-in modular ship composition factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from colav_simulator.core.ship import Config, IShip


def legacy_equivalent_profile() -> dict[str, Any]:
    """Return the canonical legacy-equivalent modular profile (Issue #56, AC3).

    Structural equivalent of the legacy kinematic command chain: a kinematic-reference
    pass-through plant driven by a pass-through controller under legacy-equivalent
    scheduler defaults.
    """
    return {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {"identity": "pass_through_plant", "parameters": {}},
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
            "controller": {"identity": "pass_through_controller", "parameters": {}},
        },
    }


def build_modular_ship_adapter(
    config: Config,
    *,
    dt_s: float | None = None,
    episode_seed: int | None = None,
) -> IShip:
    """Construct an opt-in modular adapter using contracts-only pass-through modules.

    ``dt_s`` (the scenario ``dt_sim``) and ``episode_seed`` are forwarded to the
    stack so environment/load modules are constructed on the simulation clock;
    omitted values keep the historical from_config defaults.
    """
    from colav_simulator.modular_gnc.adapter import ModularShipAdapter  # noqa: PLC0415
    from colav_simulator.modular_gnc.stack import ModularShipStack  # noqa: PLC0415

    stack: Any = ModularShipStack.from_config(
        config.ship_modules,
        episode_seed=0 if episode_seed is None else episode_seed,
        dt_s=0.1 if dt_s is None else dt_s,
    )
    return ModularShipAdapter.from_legacy_config(config, stack)
