"""Profile-parameterized pairwise COLREG encounter state machine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from colav_simulator.evaluation.profiles import EvaluatorProfile


class EncounterState(StrEnum):
    SF = "SF"
    OT = "OT"
    HO = "HO"
    GW = "GW"
    SO = "SO"
    EM = "EM"


@dataclass(frozen=True)
class EncounterObservation:
    time_s: float
    encounter: str
    stage: int
    range_m: float
    dcpa_m: float
    signed_tcpa_s: float
    relative_bearing_deg: float
    contact_angle_deg: float


@dataclass(frozen=True)
class FSMTransition:
    time_s: float
    previous: EncounterState
    current: EncounterState
    reason: str
    observation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["previous"] = self.previous.value
        output["current"] = self.current.value
        return output


class PairwiseColregFSM:
    """Stable pairwise encounter classification with lock-on and safe exit."""

    def __init__(self, profile: EvaluatorProfile) -> None:
        self.profile = profile
        self.state = EncounterState.SF
        self.locked_state: EncounterState | None = None
        self.transitions: list[FSMTransition] = []

    def update(self, observation: EncounterObservation) -> EncounterState:
        previous = self.state
        reason: str | None = None
        if self.state == EncounterState.SF:
            candidate = _state_for_encounter(observation.encounter)
            if observation.stage >= 2 and observation.signed_tcpa_s > 0.0 and candidate is not None:
                self.state = candidate
                self.locked_state = candidate
                reason = "stage2_entry_and_positive_tcpa"
        elif (
            observation.stage == 1
            and observation.range_m
            > self.profile.stages.stage2_entry_m * self.profile.encounter.exit_range_factor
        ):
            self.state = EncounterState.SF
            self.locked_state = None
            reason = "safe_exit_hysteresis"
        elif (
            self.state in {EncounterState.GW, EncounterState.HO}
            and observation.stage >= 4
            and 0.0 < observation.signed_tcpa_s <= self.profile.encounter.emergency_tcpa_s
        ):
            self.state = EncounterState.EM
            reason = "stage4_positive_tcpa_emergency"
        elif self.state != EncounterState.EM and self.locked_state is not None:
            self.state = self.locked_state

        if reason is not None and self.state != previous:
            self.transitions.append(
                FSMTransition(
                    time_s=observation.time_s,
                    previous=previous,
                    current=self.state,
                    reason=reason,
                    observation=asdict(observation),
                )
            )
        return self.state


def _state_for_encounter(encounter: str) -> EncounterState | None:
    return {
        "overtaking": EncounterState.OT,
        "overtaken": EncounterState.OT,
        "head_on": EncounterState.HO,
        "crossing_give_way": EncounterState.GW,
        "crossing_stand_on": EncounterState.SO,
    }.get(encounter)
