"""Explicit local boundary around the extracted original propulsion policy."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from colav_simulator.original_gnc.native import OriginalGncError, verify_build


def message_values(value: Any) -> Any:
    """Give source callbacks attribute access to plain typed message values."""
    if isinstance(value, dict):
        return SimpleNamespace(**{key: message_values(item) for key, item in value.items()})
    if isinstance(value, list):
        return [message_values(item) for item in value]
    return value


class NativePolicy:
    """Own independent policy state with explicit time and emitted values."""

    def __init__(
        self,
        build: Path,
        config: dict,
        time_ns: int,
        *,
        scenario: dict | None = None,
        config_file: str = "",
        scenario_file: str = "",
        shadow_mode: bool = True,
        publish_rate_hz: float = 2.0,
        replay_clocks: list[int] | None = None,
    ):
        verify_build(build)
        metadata = json.loads((build / "extraction.json").read_text())["python_policy"]
        self.callbacks = metadata["callbacks"]
        self.time_ns = time_ns
        self._clocks = iter(replay_clocks) if replay_clocks is not None else None
        self.clock_reads = 0
        spec = importlib.util.spec_from_file_location(
            "original_gnc_extracted_policy", build / "original_propulsion_policy.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.core = module.OriginalPropulsionPolicy(
            config, scenario or {}, config_file, scenario_file, shadow_mode, publish_rate_hz, self._read_clock
        )

    def _read_clock(self) -> int:
        self.clock_reads += 1
        if self._clocks is None:
            return self.time_ns
        try:
            return next(self._clocks)
        except StopIteration as error:
            raise OriginalGncError("Original propulsion policy consumed an extra clock read") from error

    def invoke(self, callback: str, fields: dict | None, time_ns: int) -> list[dict]:
        """Apply one source callback; timers return both original publications."""
        if callback not in {*self.callbacks.values(), "_tick"}:
            raise OriginalGncError(f"Unknown original propulsion callback: {callback}")
        if isinstance(time_ns, bool) or not isinstance(time_ns, int) or not 0 <= time_ns < 2**63:
            raise ValueError("time_ns must be a nonnegative int64")
        self.time_ns = time_ns
        if callback == "_tick":
            return self.core._tick()
        getattr(self.core, callback)(message_values(fields))
        return []

    def snapshot(self) -> dict:
        """Observe state used by source speed filtering and side-thruster gates."""
        return {
            "speed_mps": self.core.speed_mps,
            "raw_speed_mps": self.core.raw_speed_mps,
            "side_thruster_speed_allowed": self.core.side_thruster_speed_allowed_state,
        }
