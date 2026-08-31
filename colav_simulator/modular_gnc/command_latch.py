from __future__ import annotations

from dataclasses import dataclass

from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    DirectReference,
    FacadeFailure,
    FailureCode,
    TrackedRoute,
)


@dataclass(frozen=True)
class LatchedCommand:
    """Command visible to scheduler after tick-boundary latching."""

    tick: int
    direct_reference: DirectReference | None = None
    tracked_route: TrackedRoute | None = None
    failure: FacadeFailure | None = None


class CommandLatch:
    """Apply per-tick authority validation and controller-rate direct ZOH."""

    def __init__(self, controller_period_ticks: int) -> None:
        if controller_period_ticks <= 0:
            raise ValueError("controller_period_ticks must be positive")
        self._controller_period_ticks = controller_period_ticks
        self._last_input_tick = -1
        self._last_direct_source_tick = -1
        self._pending_direct: DirectReference | None = None
        self._held_direct: DirectReference | None = None

    def _failure(self, command: CommandInput, code: FailureCode, message: str) -> LatchedCommand:
        return LatchedCommand(
            tick=command.tick,
            failure=FacadeFailure(code=code, message=message, phase="command_latch", tick=command.tick),
        )

    def consume(self, command: CommandInput) -> LatchedCommand:
        """Latch one command exactly at its simulation-tick boundary."""
        if command.tick == self._last_input_tick:
            return self._failure(command, FailureCode.DUPLICATE_INPUT, "duplicate simulation tick")
        if command.tick < self._last_input_tick:
            return self._failure(command, FailureCode.OUT_OF_ORDER_INPUT, "out-of-order simulation tick")
        self._last_input_tick = command.tick

        if command.direct_reference is not None:
            if command.direct_reference.latched_tick < self._last_direct_source_tick:
                return self._failure(command, FailureCode.STALE_INPUT, "stale direct reference")
            self._last_direct_source_tick = command.direct_reference.latched_tick
            self._pending_direct = command.direct_reference
            if self._held_direct is None or command.tick % self._controller_period_ticks == 0:
                self._held_direct = self._pending_direct
        elif command.tracked_route is not None:
            route = command.tracked_route
            self._pending_direct = None
            self._held_direct = None
            if not route.accepted:
                return self._failure(command, FailureCode.REJECTED_ROUTE, "tracked route was not accepted")
            if not route.valid_from_tick <= command.tick <= route.valid_until_tick:
                return self._failure(command, FailureCode.EXPIRED_ROUTE, "tracked route is outside validity interval")
            return LatchedCommand(tick=command.tick, tracked_route=route)
        elif command.tick % self._controller_period_ticks == 0 and self._pending_direct is not None:
            self._held_direct = self._pending_direct

        return LatchedCommand(tick=command.tick, direct_reference=self._held_direct)

    def snapshot(self) -> tuple[int, int, DirectReference | None, DirectReference | None]:
        """Return complete latch state."""
        return self._last_input_tick, self._last_direct_source_tick, self._pending_direct, self._held_direct

    def restore(self, state: tuple[int, int, DirectReference | None, DirectReference | None]) -> None:
        """Restore complete latch state."""
        self._last_input_tick, self._last_direct_source_tick, self._pending_direct, self._held_direct = state
