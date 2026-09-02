"""Characterization parity vs intentional redesign reporting (Issue #52, VR-24, TS-27, TS-28, G3, G4)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from colav_simulator.modular_gnc.contracts import _deep_freeze, _non_empty_str


class CharacterizationEvidenceKind(str, Enum):
    """Categorization distinguishing external source characterization from intentional redesign."""

    SOURCE_CHARACTERIZATION_REFERENCE = "SOURCE_CHARACTERIZATION_REFERENCE"
    INTENTIONAL_REDESIGN = "INTENTIONAL_REDESIGN"


@dataclass(frozen=True)
class RedesignDecision:
    """Explicit record of an intentional redesign deviation from source C++ implementation (VR-24, G4)."""

    decision_id: str
    topic: str
    source_behavior: str
    redesign_behavior: str
    specification_reference: str
    kind: CharacterizationEvidenceKind = CharacterizationEvidenceKind.INTENTIONAL_REDESIGN

    def __post_init__(self) -> None:
        """Validate non-empty strings and kind."""
        object.__setattr__(self, "decision_id", _non_empty_str("decision_id", self.decision_id))
        object.__setattr__(self, "topic", _non_empty_str("topic", self.topic))
        object.__setattr__(self, "source_behavior", _non_empty_str("source_behavior", self.source_behavior))
        object.__setattr__(self, "redesign_behavior", _non_empty_str("redesign_behavior", self.redesign_behavior))
        object.__setattr__(
            self, "specification_reference", _non_empty_str("specification_reference", self.specification_reference)
        )
        object.__setattr__(self, "kind", CharacterizationEvidenceKind(self.kind))


@dataclass(frozen=True)
class ReferenceComparison:
    """Comparison item against external source characterization fixture (TS-27, TS-28, G3)."""

    quantity: str
    source_value: Any
    evaluated_value: Any
    status: str
    kind: CharacterizationEvidenceKind = CharacterizationEvidenceKind.SOURCE_CHARACTERIZATION_REFERENCE
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate non-empty fields and freeze."""
        object.__setattr__(self, "quantity", _non_empty_str("quantity", self.quantity))
        object.__setattr__(self, "status", _non_empty_str("status", self.status))
        object.__setattr__(self, "kind", CharacterizationEvidenceKind(self.kind))
        object.__setattr__(self, "notes", str(self.notes))


@dataclass(frozen=True)
class CharacterizationParityReport:
    """Content-addressed report separating source characterization parity from intentional redesign.

    Strict claim boundary: candidate A2 (migration verified) only. Does NOT claim vessel validation.
    """

    schema_version: str = "characterization-parity-report.v1"
    claim_ceiling: str = "candidate_A2_migration_verified_only"
    source_baseline_id: str = "l45-source-20260824-v2"
    manifest_sha256: str = "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"
    comparisons: tuple[ReferenceComparison, ...] = ()
    redesigns: tuple[RedesignDecision, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate schema, ceiling, and freeze sequences."""
        if self.claim_ceiling != "candidate_A2_migration_verified_only":
            raise ValueError(f"unsupported claim_ceiling {self.claim_ceiling}: candidate A2 only")
        object.__setattr__(self, "comparisons", tuple(self.comparisons))
        object.__setattr__(self, "redesigns", tuple(self.redesigns))
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "claim_ceiling": self.claim_ceiling,
            "source_baseline_id": self.source_baseline_id,
            "manifest_sha256": self.manifest_sha256,
            "comparisons": [
                {
                    "quantity": c.quantity,
                    "source_value": c.source_value,
                    "evaluated_value": c.evaluated_value,
                    "status": c.status,
                    "kind": c.kind.value,
                    "notes": c.notes,
                }
                for c in self.comparisons
            ],
            "redesigns": [
                {
                    "decision_id": r.decision_id,
                    "topic": r.topic,
                    "source_behavior": r.source_behavior,
                    "redesign_behavior": r.redesign_behavior,
                    "specification_reference": r.specification_reference,
                    "kind": r.kind.value,
                }
                for r in self.redesigns
            ],
            "metadata": dict(self.metadata),
        }


def build_generic_3dof_plant_redesign_decisions() -> tuple[RedesignDecision, ...]:
    """Return explicit catalog of intentional redesigns for generic 3DOF plant vs source C++."""
    return (
        RedesignDecision(
            decision_id="REDESIGN-PLANT-01",
            topic="pure_rhs_vs_internal_integrator",
            source_behavior="C++ ShipDynamicsNode owned an internal numerical integrator and wall timer",
            redesign_behavior="Generic3DOFPlant exposes a pure stateless RHS; integrator is owned by scheduler",
            specification_reference="VR-11, TS-13",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PLANT-02",
            topic="no_silent_clipping_or_reset",
            source_behavior="C++ ShipDynamicsNode silently clamped speeds (max_u, max_r) and abnormal_reset_u/r",
            redesign_behavior="Generic3DOFPlant never silently clips or resets velocities or applied loads",
            specification_reference="VR-12, TS-17",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PLANT-03",
            topic="fail_closed_on_nonfinite",
            source_behavior="C++ ShipDynamicsNode caught NaN state and returned Vector4d::Zero() (silent repair)",
            redesign_behavior="Generic3DOFPlant rejects non-finite states/loads with structured exception",
            specification_reference="VR-12, TS-17",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PLANT-04",
            topic="generic_3dof_vs_vessel_specific_4dof",
            source_behavior="C++ source coupled 4DOF (surge, sway, roll, yaw) hardcoded for one vessel",
            redesign_behavior="Generic3DOFPlant is a vessel-agnostic 3DOF maneuvering model with typed parameters",
            specification_reference="VR-08, TS-12",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PLANT-05",
            topic="scheduler_owned_fixed_step_rk4",
            source_behavior="C++ source updated state on ROS wall timer without synchronized stage-time field query",
            redesign_behavior="Scheduler owns classical fixed-step RK4 and evaluates stage-time environment at k1..k4",
            specification_reference="VR-11, TS-14",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PLANT-06",
            topic="mass_spd_and_damping_dissipativity",
            source_behavior="C++ source unchecked or soft-warning on negative mass or non-dissipative damping",
            redesign_behavior="Generic3DOFPlant strictly validates mass symmetry/SPD and damping dissipativity up-front",
            specification_reference="VR-08, TS-11",
        ),
    )


def build_generic_roll_4dof_plant_redesign_decisions() -> tuple[RedesignDecision, ...]:
    """Return explicit catalog of intentional redesigns for generic roll-4DOF plant vs source C++."""
    return (
        RedesignDecision(
            decision_id="REDESIGN-ROLL4DOF-01",
            topic="unactuated_roll_actuator_channel",
            source_behavior="C++ source allowed arbitrary roll moment in control wrench container",
            redesign_behavior="GenericRoll4DOFPlant strictly excludes roll moment actuator channel (RA-12)",
            specification_reference="RA-12, VR-16, TS-22",
        ),
        RedesignDecision(
            decision_id="REDESIGN-ROLL4DOF-02",
            topic="restoring_dominated_roll_stability",
            source_behavior="C++ source implemented vessel-specific GM roll moment without stability contract",
            redesign_behavior="GenericRoll4DOFPlant implements restoring stiffness K_phi * phi with dissipative damping",
            specification_reference="RA-12, VR-08, TS-05",
        ),
        RedesignDecision(
            decision_id="REDESIGN-ROLL4DOF-03",
            topic="pure_rhs_vs_internal_integrator",
            source_behavior="C++ ShipDynamicsNode owned internal RK4 and wall timer",
            redesign_behavior="GenericRoll4DOFPlant exposes a pure stateless 8-state RHS integrated by scheduler RK4",
            specification_reference="VR-11, TS-13",
        ),
        RedesignDecision(
            decision_id="REDESIGN-ROLL4DOF-04",
            topic="no_silent_clipping_or_nan_repair",
            source_behavior="C++ source silently clamped velocities and reset state on NaN",
            redesign_behavior="GenericRoll4DOFPlant never silently clamps or repairs non-finite inputs",
            specification_reference="VR-12, TS-17",
        ),
        RedesignDecision(
            decision_id="REDESIGN-ROLL4DOF-05",
            topic="4x4_mass_spd_and_coupling_validation",
            source_behavior="C++ source used fixed 4x4 matrix without formal SPD/coupling guarantees",
            redesign_behavior=(
                "GenericRoll4DOFPlant validates 4x4 symmetry, positive-definiteness, and dissipativity up-front"
            ),
            specification_reference="VR-08, TS-11",
        ),
        RedesignDecision(
            decision_id="REDESIGN-ROLL4DOF-06",
            topic="typed_4dof_truth_and_3dof_navigation_projection",
            source_behavior="C++ published mixed 4DOF odometry directly into ROS topics",
            redesign_behavior=(
                "PlantState retains full 4DOF truth (phi, p); NavigationState projection remains 3DOF (TS-12)"
            ),
            specification_reference="VR-07, TS-12",
        ),
    )


def build_marine_pid_redesign_decisions() -> tuple[RedesignDecision, ...]:
    """Return explicit catalog of intentional redesigns for marine_pid vs source C++ (VR-13..15, TS-19..21)."""
    return (
        RedesignDecision(
            decision_id="REDESIGN-PID-01",
            topic="derivative_on_measurement",
            source_behavior="C++ source computed derivative on error, causing derivative kick on reference jumps",
            redesign_behavior="MarinePID computes derivative strictly on measurement state (no kick on reference step)",
            specification_reference="VR-15, TS-20",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PID-02",
            topic="dt_aware_derivative_filtering",
            source_behavior="C++ source used fixed filter rate assuming hardcoded 10 Hz ROS wall timer",
            redesign_behavior="MarinePID uses continuous-time invariant dt-aware filter alpha = dt / (tau_d + dt)",
            specification_reference="VR-15, TS-20",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PID-03",
            topic="single_tracking_antiwindup_path",
            source_behavior="C++ source combined multi-layer heuristic clamping, decay, and conflicting anti-windup",
            redesign_behavior=(
                "MarinePID enforces exactly one tracking anti-windup path using back-calculation from achieved load"
            ),
            specification_reference="VR-15, TS-20",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PID-04",
            topic="achieved_load_feedback_contract",
            source_behavior=(
                "C++ source lacked explicit achieved-load feedback contract, assuming perfect actuator execution"
            ),
            redesign_behavior="MarinePID defines typed AchievedGeneralizedLoad input without truth leakage from plant",
            specification_reference="VR-15, VR-19, TS-20, TS-21",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PID-05",
            topic="term_level_trace_decomposition",
            source_behavior="C++ source output only aggregated wrench without term-level attribution",
            redesign_behavior=(
                "MarinePID traces P, I, D, feedforward, raw request, saturation, and correction separately every tick"
            ),
            specification_reference="VR-15, VR-18, TS-20",
        ),
        RedesignDecision(
            decision_id="REDESIGN-PID-06",
            topic="clean_pid_identity_exclusion",
            source_behavior="C++ source mixed SMC, NDO, and scenario-specific policies inside a single control_loop()",
            redesign_behavior=(
                "MarinePID strictly excludes SMC, NDO, gain scheduling, and scenario branches from PID identity"
            ),
            specification_reference="VR-13, TS-19",
        ),
    )


def load_characterization_fixture_manifest(fixture_dir: Path | str) -> dict[str, Any]:
    """Load and return parsed characterization fixture manifest JSON."""
    manifest_file = Path(fixture_dir) / "manifest.json"
    if not manifest_file.is_file():
        raise FileNotFoundError(f"characterization manifest not found: {manifest_file}")
    with manifest_file.open("r", encoding="utf-8") as f:
        return json.load(f)
