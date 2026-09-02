"""Characterization parity vs redesign reporting and claim boundaries (Issue #52, VR-24, TS-27, G3, G4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from colav_simulator.modular_gnc.characterization_report import (
    CharacterizationEvidenceKind,
    CharacterizationParityReport,
    RedesignDecision,
    ReferenceComparison,
    build_generic_3dof_plant_redesign_decisions,
    build_generic_roll_4dof_plant_redesign_decisions,
    build_marine_pid_redesign_decisions,
    load_characterization_fixture_manifest,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gnc_characterization"


def test_characterization_report_schema_and_claim_ceiling() -> None:
    redesigns = build_generic_3dof_plant_redesign_decisions()
    report = CharacterizationParityReport(
        redesigns=redesigns,
    )

    assert report.schema_version == "characterization-parity-report.v1"
    assert report.claim_ceiling == "candidate_A2_migration_verified_only"
    assert report.source_baseline_id == "l45-source-20260824-v2"
    assert len(report.redesigns) == 6

    # Rejects invalid or upgraded claim ceiling
    with pytest.raises(ValueError, match="candidate A2 only"):
        CharacterizationParityReport(
            claim_ceiling="A5_vessel_validated",  # Illegal claim upgrade!
            redesigns=redesigns,
        )


def test_characterization_report_distinguishes_reference_from_redesign() -> None:
    comparison = ReferenceComparison(
        quantity="heave_natural_frequency",
        source_value=0.6139389597101653,
        evaluated_value=0.6139389597101653,
        status="EXACT_MATCH",
        kind=CharacterizationEvidenceKind.SOURCE_CHARACTERIZATION_REFERENCE,
        notes="Source C++ env_engines pure model reference",
    )
    redesign = RedesignDecision(
        decision_id="REDESIGN-PLANT-01",
        topic="pure_rhs_vs_internal_integrator",
        source_behavior="C++ owned internal Euler integration",
        redesign_behavior="Generic3DOFPlant pure RHS with scheduler RK4",
        specification_reference="VR-11, TS-13",
        kind=CharacterizationEvidenceKind.INTENTIONAL_REDESIGN,
    )

    assert comparison.kind is CharacterizationEvidenceKind.SOURCE_CHARACTERIZATION_REFERENCE
    assert redesign.kind is CharacterizationEvidenceKind.INTENTIONAL_REDESIGN

    report = CharacterizationParityReport(
        comparisons=(comparison,),
        redesigns=(redesign,),
    )
    d = report.to_dict()
    assert d["comparisons"][0]["kind"] == "SOURCE_CHARACTERIZATION_REFERENCE"
    assert d["redesigns"][0]["kind"] == "INTENTIONAL_REDESIGN"


def test_characterization_report_binds_to_fixture_manifest_sha256() -> None:
    manifest = load_characterization_fixture_manifest(FIXTURE_DIR)
    assert manifest["schema_version"] == "agx-l45-characterization-manifest.v1"
    assert manifest["source_baseline_id"] == "l45-source-20260824-v2"
    assert manifest["source_manifest_sha256"] == "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"

    # Read characterization.json fixture
    char_json_path = FIXTURE_DIR / "characterization.json"
    with char_json_path.open("r", encoding="utf-8") as f:
        char_data = json.load(f)

    assert char_data["schema_version"] == "agx-l45-characterization-output.v1"
    assert char_data["claim_ceiling"] == "not_vessel_validation"
    assert char_data["evidence_kind"] == "SOURCE_BEHAVIOR_CHARACTERIZATION"

    # Build report with bound manifest hash
    report = CharacterizationParityReport(
        manifest_sha256=manifest["source_manifest_sha256"],
        redesigns=build_generic_3dof_plant_redesign_decisions(),
        comparisons=(
            ReferenceComparison(
                quantity="natural_frequencies.heave",
                source_value=char_data["natural_frequencies"]["heave"],
                evaluated_value=char_data["natural_frequencies"]["heave"],
                status="EXACT_MATCH",
                kind=CharacterizationEvidenceKind.SOURCE_CHARACTERIZATION_REFERENCE,
                notes="Bound to characterization.json fixture",
            ),
        ),
    )
    assert report.manifest_sha256 == "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"
    assert len(report.comparisons) == 1
    assert len(report.redesigns) == 6


def test_characterization_report_generic_roll_4dof_plant_redesigns() -> None:
    redesigns_4dof = build_generic_roll_4dof_plant_redesign_decisions()
    assert len(redesigns_4dof) == 6
    decision_ids = {r.decision_id for r in redesigns_4dof}
    assert "REDESIGN-ROLL4DOF-01" in decision_ids
    assert "REDESIGN-ROLL4DOF-02" in decision_ids
    assert "REDESIGN-ROLL4DOF-03" in decision_ids
    assert "REDESIGN-ROLL4DOF-04" in decision_ids
    assert "REDESIGN-ROLL4DOF-05" in decision_ids
    assert "REDESIGN-ROLL4DOF-06" in decision_ids

    report = CharacterizationParityReport(redesigns=redesigns_4dof)
    assert report.claim_ceiling == "candidate_A2_migration_verified_only"
    assert len(report.redesigns) == 6


def test_characterization_report_marine_pid_redesigns() -> None:
    redesigns_pid = build_marine_pid_redesign_decisions()
    assert len(redesigns_pid) == 6
    decision_ids = {r.decision_id for r in redesigns_pid}
    assert "REDESIGN-PID-01" in decision_ids
    assert "REDESIGN-PID-02" in decision_ids
    assert "REDESIGN-PID-03" in decision_ids
    assert "REDESIGN-PID-04" in decision_ids
    assert "REDESIGN-PID-05" in decision_ids
    assert "REDESIGN-PID-06" in decision_ids

    report = CharacterizationParityReport(redesigns=redesigns_pid)
    assert report.claim_ceiling == "candidate_A2_migration_verified_only"
    assert len(report.redesigns) == 6
