"""Opt-in modular GNC contracts and execution stack."""

from colav_simulator.modular_gnc.characterization_report import (
    CharacterizationEvidenceKind,
    CharacterizationParityReport,
    RedesignDecision,
    ReferenceComparison,
    build_generic_3dof_plant_redesign_decisions,
    build_generic_roll_4dof_plant_redesign_decisions,
)
from colav_simulator.modular_gnc.contracts import (
    CommandInput,
    DirectReference,
    FacadeFailure,
    NavigationState,
    PlantInputSemantics,
    PlantState,
    StackOutput,
    StackSnapshot,
    TrackedRoute,
    canonicalize_plant_input_semantics,
)
from colav_simulator.modular_gnc.integrators import rk4_step
from colav_simulator.modular_gnc.plant import (
    Generic3DOFPlant,
    Generic3DOFPlantParameters,
    GenericRoll4DOFPlant,
    GenericRoll4DOFPlantParameters,
)

__all__ = [
    "CharacterizationEvidenceKind",
    "CharacterizationParityReport",
    "CommandInput",
    "DirectReference",
    "FacadeFailure",
    "Generic3DOFPlant",
    "Generic3DOFPlantParameters",
    "GenericRoll4DOFPlant",
    "GenericRoll4DOFPlantParameters",
    "NavigationState",
    "PlantInputSemantics",
    "PlantState",
    "RedesignDecision",
    "ReferenceComparison",
    "StackOutput",
    "StackSnapshot",
    "TrackedRoute",
    "build_generic_3dof_plant_redesign_decisions",
    "build_generic_roll_4dof_plant_redesign_decisions",
    "canonicalize_plant_input_semantics",
    "rk4_step",
]
