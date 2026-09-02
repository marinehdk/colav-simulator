"""Translate the accepted Mid-MPC rolling plan receipt into modular TrackedRoutes (Issue #63).

Artifact selection (S7.0 audit issue list #1, pinned): this bridge reads ONLY the
``accepted_plan_receipt`` carried in the planner trace ``algorithm_details``
(the L4-accepted plan: receipt hash, accepted sequence, validity interval, and
the accepted ownship plan states). It never reads the solver prediction grid or
``get_current_plan``; a predicted trajectory is never a route.

Lifecycle mapping (receipt semantics -> TrackedRoute fields):
- accepted receipt                -> TrackedRoute(accepted=True); a rejected or
  missing candidate NEVER becomes a route: the tick fails structurally
  (REJECTED_ROUTE) or holds on the previously accepted receipt (the planner's
  preserved-accepted-plan hold re-reports the same receipt, which this bridge
  re-emits identically — an explicit hold, never a silent one).
- ``valid_until_s``               -> ``valid_until_tick`` (receipt expiry becomes
  route expiry); enforcement lives in the command latch (EXPIRED_ROUTE), reused
  rather than re-created here.
- ``accepted_sequence``           -> monotone receipt order; a regression fails
  with OUT_OF_ORDER_INPUT, a different receipt reusing a sequence fails with
  DUPLICATE_INPUT.
- rolling-plan revision reason    -> route identity. ``CONTINUITY_PRESERVED``
  rolls the geometry under the same (route_id, revision); every other reason
  (INITIAL_PLAN, COLREG_AUTHORITY_CHANGED, MISSION_ROUTE_CHANGED, ...) is a
  reference discontinuity expressed as a revision increment — accepted as a
  revision, never rejected (S7.0 audit issue #8: authority-hash churn is
  lifecycle as designed).
- accepted plan states            -> ``waypoints_ne_m`` / ``speed_mps``;
  ``task`` is TRANSIT (the transit plan the acceptance gated).

Feeding boundary: the planner layer stays environment-truth-fed in both stacks;
DP-19 constrains only the modular guidance/control/allocation internals
downstream of this bridge.

Slice-one policy: every policy violation surfaces as a structured
``FacadeFailure`` for the adapter's failure policy (episode abort); there is no
silent drop, silent accept, or fallback to direct references here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from colav_simulator.core.colav.threat_management import AcceptedPlanReceipt
from colav_simulator.modular_gnc.contracts import (
    ControlTask,
    FacadeFailure,
    FailureCode,
    TrackedRoute,
    _non_bool_int,
)

_SNAPSHOT_SCHEMA_VERSION = "mid-mpc-route-bridge.snapshot.v1"
_FAILURE_PHASE = "route_bridge"
_ROUTE_ID_PREFIX = "mid-mpc-"
_ROUTE_ID_HASH_CHARS = 16
_TICK_EPSILON = 1.0e-9
_CONTINUITY_PRESERVED = "CONTINUITY_PRESERVED"


@dataclass(frozen=True)
class RouteDecision:
    """One tick's route-authority outcome: exactly one of route or failure."""

    tick: int
    route: TrackedRoute | None = None
    failure: FacadeFailure | None = None


@dataclass(frozen=True)
class MidMpcRouteBridgeSnapshot:
    """Deterministic bridge-local translation state."""

    schema_version: str
    route_id: str | None
    revision: int
    last_receipt_hash: str | None
    last_accepted_sequence: int | None
    last_route: TrackedRoute | None

    def __post_init__(self) -> None:
        """Validate pinned snapshot schema."""
        if self.schema_version != _SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot schema_version: {self.schema_version}")


class MidMpcRouteBridge:
    """Emit one accepted-route decision per tick from the Mid-MPC receipt stream."""

    def __init__(self, *, dt_s: float) -> None:
        """Initialize with the simulation tick period used for time-to-tick mapping."""
        dt = float(dt_s)
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt_s must be finite and positive")
        self._dt_s = dt
        self._reset_state()

    @property
    def dt_s(self) -> float:
        """Return the configured tick period."""
        return self._dt_s

    def reset(self) -> None:
        """Idempotently clear translation state (episode reset)."""
        self._reset_state()

    def current_route(self, *, tick: int, planner_data: Mapping[str, Any] | None) -> RouteDecision:
        """Translate the planner's current accepted receipt for one simulation tick."""
        tick_int = _non_bool_int("tick", tick)
        details = self._algorithm_details(planner_data)
        if details is None:
            return self._failure(
                tick_int,
                FailureCode.REJECTED_ROUTE,
                "planner trace carries no algorithm details; tracked-route authority requires "
                "an accepted Mid-MPC plan receipt",
            )
        receipt_document = details.get("accepted_plan_receipt")
        if not isinstance(receipt_document, Mapping):
            return self._failure(
                tick_int,
                FailureCode.REJECTED_ROUTE,
                "no accepted Mid-MPC plan receipt; unaccepted planner output never becomes a route",
            )
        if receipt_document.get("receipt_hash") == self._last_receipt_hash:
            return self._hold_tick(tick_int)
        return self._translate_new_receipt(tick_int, details, receipt_document)

    def _hold_tick(self, tick: int) -> RouteDecision:
        """Re-emit the already-translated accepted route for a held receipt (explicit hold)."""
        if self._last_route is None:
            return self._failure(
                tick,
                FailureCode.REJECTED_ROUTE,
                "held receipt has no translated accepted route",
                {"receipt_hash": str(self._last_receipt_hash)},
            )
        return RouteDecision(tick=tick, route=self._last_route)

    def _translate_new_receipt(
        self,
        tick: int,
        details: Mapping[str, Any],
        receipt_document: Mapping[str, Any],
    ) -> RouteDecision:
        """Validate, order, and translate one newly observed accepted receipt."""
        try:
            receipt = AcceptedPlanReceipt.from_mapping(dict(receipt_document))
        except (TypeError, ValueError) as exc:
            return self._failure(
                tick,
                FailureCode.REJECTED_ROUTE,
                f"accepted plan receipt failed canonical validation: {exc}",
                {"receipt_hash": str(receipt_document.get("receipt_hash"))},
            )
        if self._last_accepted_sequence is not None:
            if receipt.accepted_sequence < self._last_accepted_sequence:
                return self._failure(
                    tick,
                    FailureCode.OUT_OF_ORDER_INPUT,
                    "accepted receipt sequence regressed",
                    {
                        "observed_sequence": receipt.accepted_sequence,
                        "last_accepted_sequence": self._last_accepted_sequence,
                    },
                )
            if receipt.accepted_sequence == self._last_accepted_sequence:
                return self._failure(
                    tick,
                    FailureCode.DUPLICATE_INPUT,
                    "new receipt reuses the last accepted sequence",
                    {"accepted_sequence": receipt.accepted_sequence},
                )
        valid_from_tick = self._tick_floor(receipt.accepted_at_s)
        valid_until_tick = self._tick_floor(receipt.valid_until_s)
        if valid_until_tick < valid_from_tick:
            return self._failure(
                tick,
                FailureCode.REJECTED_ROUTE,
                "receipt validity interval does not cover any simulation tick",
                {
                    "valid_from_tick": valid_from_tick,
                    "valid_until_tick": valid_until_tick,
                },
            )
        prediction = receipt.accepted_prediction
        if prediction is None:
            return self._failure(
                tick,
                FailureCode.REJECTED_ROUTE,
                "accepted receipt carries no accepted plan prediction; the accepted plan is "
                "the only routeable artifact",
                {"receipt_hash": receipt.receipt_hash},
            )

        if self._route_id is None or self._last_receipt_hash is None:
            route_id = f"{_ROUTE_ID_PREFIX}{receipt.receipt_hash[:_ROUTE_ID_HASH_CHARS]}"
            revision = 0
        elif self._continuity_preserved(details):
            route_id = self._route_id
            revision = self._revision
        else:
            route_id = self._route_id
            revision = self._revision + 1
        route = TrackedRoute(
            route_id=route_id,
            revision=revision,
            accepted=True,
            valid_from_tick=valid_from_tick,
            valid_until_tick=valid_until_tick,
            waypoints_ne_m=np.column_stack((prediction.states_enu[:, 0], prediction.states_enu[:, 1])).T,
            speed_mps=np.hypot(prediction.states_enu[:, 2], prediction.states_enu[:, 3]),
            task=ControlTask.TRANSIT,
        )
        self._route_id = route_id
        self._revision = revision
        self._last_receipt_hash = receipt.receipt_hash
        self._last_accepted_sequence = receipt.accepted_sequence
        self._last_route = route
        return RouteDecision(tick=tick, route=route)

    def snapshot(self) -> MidMpcRouteBridgeSnapshot:
        """Capture complete translation state for deterministic restoration."""
        return MidMpcRouteBridgeSnapshot(
            schema_version=_SNAPSHOT_SCHEMA_VERSION,
            route_id=self._route_id,
            revision=self._revision,
            last_receipt_hash=self._last_receipt_hash,
            last_accepted_sequence=self._last_accepted_sequence,
            last_route=self._last_route,
        )

    def restore(self, snapshot: MidMpcRouteBridgeSnapshot) -> None:
        """Restore exact translation state from a snapshot."""
        if not isinstance(snapshot, MidMpcRouteBridgeSnapshot):
            raise TypeError(f"snapshot must be MidMpcRouteBridgeSnapshot, got {type(snapshot).__name__}")
        if snapshot.schema_version != _SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot schema_version: {snapshot.schema_version}")
        self._route_id = snapshot.route_id
        self._revision = snapshot.revision
        self._last_receipt_hash = snapshot.last_receipt_hash
        self._last_accepted_sequence = snapshot.last_accepted_sequence
        self._last_route = snapshot.last_route

    def _reset_state(self) -> None:
        """Reset all mutable translation state to deterministic defaults."""
        self._route_id: str | None = None
        self._revision = 0
        self._last_receipt_hash: str | None = None
        self._last_accepted_sequence: int | None = None
        self._last_route: TrackedRoute | None = None

    @staticmethod
    def _algorithm_details(planner_data: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        """Extract the planner trace algorithm_details mapping, if present."""
        if not isinstance(planner_data, Mapping):
            return None
        planner = planner_data.get("planner")
        if not isinstance(planner, Mapping):
            return None
        details = planner.get("algorithm_details")
        return details if isinstance(details, Mapping) else None

    @staticmethod
    def _continuity_preserved(details: Mapping[str, Any]) -> bool:
        """Return whether the committed solve rolled the accepted plan continuously.

        A missing rolling-plan document is treated as an explicit discontinuity:
        only a declared CONTINUITY_PRESERVED roll may keep route identity.
        """
        rolling_plan = details.get("rolling_plan")
        if not isinstance(rolling_plan, Mapping):
            return False
        reference = rolling_plan.get("reference")
        if not isinstance(reference, Mapping):
            return False
        return reference.get("revision_reason") == _CONTINUITY_PRESERVED

    def _tick_floor(self, time_s: float) -> int:
        """Map an absolute plan time to its simulation tick (floor at the tick boundary)."""
        return int(math.floor(time_s / self._dt_s + _TICK_EPSILON))

    def _failure(
        self,
        tick: int,
        code: FailureCode,
        message: str,
        details: dict[str, int | str] | None = None,
    ) -> RouteDecision:
        """Return a structured route-authority failure (slice-one abort policy)."""
        return RouteDecision(
            tick=tick,
            failure=FacadeFailure(
                code=code,
                message=message,
                phase=_FAILURE_PHASE,
                tick=tick,
                details={} if details is None else details,
            ),
        )
