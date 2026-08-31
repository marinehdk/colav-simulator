from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from colav_simulator.core.ship import Config, IShip


def build_modular_ship_adapter(config: Config) -> IShip:
    """Construct opt-in modular adapter through registered deterministic test modules."""
    from colav_simulator.modular_gnc.adapter import ModularShipAdapter  # noqa: PLC0415
    from colav_simulator.modular_gnc.stack import ModularShipStack  # noqa: PLC0415

    stack: Any = ModularShipStack.from_config(config.ship_modules)
    return ModularShipAdapter.from_legacy_config(config, stack)
