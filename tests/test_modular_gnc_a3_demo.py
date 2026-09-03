"""A3 generalized-simulation controlled demo: three-state gates, separated evidence classes (Issue #61).

Every gate verdict (passed / failed / not run) is pinned by this file. The demo
is strictly local and deterministic: one pytest run reproduces every number in
docs/evaluation/a3-generalized-simulation-demo.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.modular_gnc.a3_demo import (
    ACCEPTANCE_NON_CLAIMS,
    DEMO_CLAIM_CEILING_LABEL,
    DEMO_CLAIM_CEILING_LEVEL,
    DEMO_PRESETS,
    DEMO_SCHEMA_VERSION,
    EVIDENCE_CLASSES,
    FINAL_CROSS_TRACK_ERROR_TOLERANCE_M,
    FINAL_SPEED_ERROR_TOLERANCE_MPS,
    GATE_IDS,
    A3DemoReport,
    GateResult,
    preset_stack_id,
    run_a3_demo,
    run_preset,
    run_preset_with_restore,
)
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.characterization_report import (
    build_generic_3dof_plant_redesign_decisions,
    build_marine_pid_redesign_decisions,
)
from colav_simulator.modular_gnc.contracts import ControlTask
from colav_simulator.modular_gnc.integrators import rk4_step
from colav_simulator.modular_gnc.plant import Generic3DOFPlant, Generic3DOFPlantParameters

EVIDENCE_DOC = Path(__file__).parent.parent / "docs" / "evaluation" / "a3-generalized-simulation-demo.md"


@pytest.fixture(scope="module")
def report() -> A3DemoReport:
    return run_a3_demo()


class TestDemoPresetsAreDataNotCodeBranches:
    """Issue #61 AC3: two different vessel presets, zero vessel/scenario branching."""

    def test_exactly_two_distinct_presets(self) -> None:
        assert len(DEMO_PRESETS) == 2
        ids = [preset.preset_id for preset in DEMO_PRESETS]
        assert len(set(ids)) == 2

    def test_presets_differ_in_plant_layout_gains_and_scenario_data(self) -> None:
        first, second = DEMO_PRESETS
        first_cfg = first.ship_modules["modules"]
        second_cfg = second.ship_modules["modules"]
        assert first_cfg["plant"]["parameters"]["mass_kg"] != second_cfg["plant"]["parameters"]["mass_kg"]
        assert first_cfg["plant"]["parameters"]["i_z_kgm2"] != second_cfg["plant"]["parameters"]["i_z_kgm2"]
        assert (
            first_cfg["allocator"]["parameters"]["layout_asset_id"]
            != second_cfg["allocator"]["parameters"]["layout_asset_id"]
        )
        assert first_cfg["controller"]["parameters"]["kp"] != second_cfg["controller"]["parameters"]["kp"]
        assert first_cfg["actuator"]["parameters"]["delay_ticks"] != second_cfg["actuator"]["parameters"]["delay_ticks"]
        assert first.initial_navigation != second.initial_navigation
        assert first.waypoints_ne_m != second.waypoints_ne_m
        assert first.route_speed_mps != second.route_speed_mps
        assert first.ticks != second.ticks

    def test_both_presets_use_the_same_module_identities(self) -> None:
        identities = []
        for preset in DEMO_PRESETS:
            roles = preset.ship_modules["modules"]
            identities.append(tuple(sorted((role, sel["identity"]) for role, sel in roles.items())))
        assert identities[0] == identities[1]


class TestCatalogProof:
    """Issue #61 AC1: every demo combination is proven valid by list_stack_catalog()."""

    def test_every_demo_stack_id_is_listed_in_catalog(self, report) -> None:
        catalog_ids = {entry["stack_id"] for entry in list_stack_catalog()["stacks"]}
        for run in report.preset_runs:
            assert run.catalog_proof["listed"] is True
            assert run.catalog_proof["stack_id"] in catalog_ids

    def test_catalog_validity_rule_replays_on_demo_config(self, report) -> None:
        catalog = list_stack_catalog()
        assert catalog["validity_rule"] == (
            "normalize_ship_modules + ModularShipStack.from_config assembly + non-empty supported_tasks"
        )
        for run in report.preset_runs:
            assert run.catalog_proof["validity_rule_replayed"] is True
            assert run.catalog_proof["supported_tasks"] == [ControlTask.TRANSIT.value]

    def test_demo_parameters_are_vessel_data_on_a_listed_combination(self) -> None:
        catalog = list_stack_catalog()
        for preset in DEMO_PRESETS:
            demo_mass = preset.ship_modules["modules"]["plant"]["parameters"]["mass_kg"]
            entry = next(item for item in catalog["stacks"] if item["stack_id"] == preset_stack_id(preset))
            entry_mass = entry["config"]["modules"]["plant"]["parameters"]["mass_kg"]
            assert demo_mass != entry_mass


class TestThreeStateGateReport:
    """Issue #61 AC2: G0-G10 reported as passed / failed / not run, never merged."""

    def test_report_schema_version(self, report) -> None:
        assert report.schema_version == DEMO_SCHEMA_VERSION

    def test_every_gate_reported_exactly_once_with_three_state_status(self, report) -> None:
        by_id = {gate.gate_id: gate for gate in report.gates}
        assert tuple(sorted(by_id)) == tuple(sorted(GATE_IDS))
        for gate in report.gates:
            assert isinstance(gate, GateResult)
            assert gate.status in {"passed", "failed", "not run"}

    def test_expected_gate_verdicts(self, report) -> None:
        by_id = {gate.gate_id: gate for gate in report.gates}
        not_run = {"G8", "G10"}
        for gate_id in GATE_IDS:
            expected = "not run" if gate_id in not_run else "passed"
            assert by_id[gate_id].status == expected, (gate_id, by_id[gate_id].status)

    def test_not_run_gates_declare_reason_and_run_no_checks(self, report) -> None:
        for gate in report.gates:
            if gate.status == "not run":
                assert gate.not_run_reason
                assert gate.checks == ()

    def test_failed_verdict_is_representable(self) -> None:
        gate = GateResult(
            gate_id="GX",
            name="sample gate",
            status="failed",
            evidence_class="system",
            checks=(),
            not_run_reason=None,
        )
        assert gate.status == "failed"


class TestSeparatedEvidenceClasses:
    """Issue #61 AC2: hydrodynamic, guidance, control, actuator, COLAV, system evidence separated."""

    def test_all_six_classes_present(self, report) -> None:
        assert tuple(sorted(report.evidence_classes)) == tuple(sorted(EVIDENCE_CLASSES))

    def test_each_gate_maps_to_exactly_one_class(self, report) -> None:
        for gate in report.gates:
            assert gate.evidence_class in EVIDENCE_CLASSES
        assert len(report.gates) == len(GATE_IDS)

    def test_colav_class_is_not_run(self, report) -> None:
        colav = report.evidence_classes["colav"]
        assert colav["status"] == "not run"
        assert colav["gate_ids"] == ["G8"]

    def test_expected_class_statuses(self, report) -> None:
        expected = {
            "hydrodynamic": "passed",
            "guidance": "passed",
            "control": "passed",
            "actuator": "passed",
            "colav": "not run",
            "system": "passed",
        }
        for name, status in expected.items():
            assert report.evidence_classes[name]["status"] == status, name

    def test_per_class_records_carry_their_own_module_evidence(self, report) -> None:
        for run in report.preset_runs:
            assert set(run.guidance_evidence) >= {
                "initial_abs_cross_track_error_m",
                "final_abs_cross_track_error_m",
                "max_abs_cross_track_error_m",
            }
            assert set(run.control_evidence) >= {"final_abs_speed_error_mps", "controller_trace_ticks"}
            assert set(run.actuator_evidence) >= {"rate_limited_ticks", "actuator_trace_ticks"}


class TestClosedLoopDemo:
    """Issue #61 AC3: the controlled demo actually closes the loop on both presets."""

    def test_no_facade_failures_anywhere(self, report) -> None:
        for run in report.preset_runs:
            assert run.failure_count == 0
            assert run.route_consumptions == run.ticks

    def test_guidance_converges_on_both_presets(self, report) -> None:
        for run in report.preset_runs:
            assert run.guidance_evidence["final_abs_cross_track_error_m"] <= FINAL_CROSS_TRACK_ERROR_TOLERANCE_M
            assert (
                run.guidance_evidence["max_abs_cross_track_error_m"]
                <= run.guidance_evidence["initial_abs_cross_track_error_m"] + 5.0
            )

    def test_speed_tracking_on_both_presets(self, report) -> None:
        for run in report.preset_runs:
            assert run.control_evidence["final_abs_speed_error_mps"] <= FINAL_SPEED_ERROR_TOLERANCE_MPS
            assert run.control_evidence["controller_trace_ticks"] == run.ticks


class TestResolvedActuatorFidelity:
    """Issue #61 G9: rate limiting active and honored, never a silent pass-through."""

    def test_fidelity_profile_is_resolved(self, report) -> None:
        for run in report.preset_runs:
            assert run.catalog_proof["fidelity_profile"] == "resolved"
            assert run.actuator_evidence["actuator_trace_ticks"] == run.ticks

    def test_rate_limits_honored_per_actuator_per_tick(self, report) -> None:
        for preset, run in zip(DEMO_PRESETS, report.preset_runs, strict=True):
            rates = preset.ship_modules["modules"]["actuator"]["parameters"]["rate_limit_n_per_s"]
            dt = preset.dt_s
            columns = list(zip(*run.actuator_output_samples, strict=False))
            assert len(columns) == len(rates)
            for actuator_id, column in zip(rates, columns, strict=True):
                for prev, curr in zip(column, column[1:], strict=False):
                    assert abs(curr - prev) <= rates[actuator_id] * dt + 1e-6

    def test_rate_limiting_is_active_not_silent(self, report) -> None:
        for run in report.preset_runs:
            assert run.actuator_evidence["rate_limited_ticks"] >= 1


class TestHydrodynamicKernel:
    """Issue #61 G2: physics-kernel evidence per preset plant, separated class."""

    def test_rk4_convergence_order_on_both_preset_plants(self) -> None:
        for preset in DEMO_PRESETS:
            params = Generic3DOFPlantParameters(**preset.ship_modules["modules"]["plant"]["parameters"])
            plant = Generic3DOFPlant(params)
            state = np.array([0.0, 0.0, 0.3, 1.5, 0.1, 0.05])
            load = np.array([2.0e5, 1.0e4, 5.0e6])
            dt = 0.4
            reference = _integrate(plant, state, load, dt / 64.0, 64)
            error_full = float(np.linalg.norm(_integrate(plant, state, load, dt, 1) - reference))
            error_half = float(np.linalg.norm(_integrate(plant, state, load, dt / 2.0, 2) - reference))
            order = float(np.log2(error_full / error_half))
            assert 3.5 <= order <= 4.5

    def test_damping_dissipative_and_coriolis_power_neutral(self) -> None:
        for preset in DEMO_PRESETS:
            params = Generic3DOFPlantParameters(**preset.ship_modules["modules"]["plant"]["parameters"])
            plant = Generic3DOFPlant(params)
            for nu in ((0.0, 0.0, 0.0), (2.0, -0.4, 0.05), (-1.5, 0.3, -0.08)):
                assert float(np.dot(nu, plant.damping_force(nu))) >= -1e-6
                coriolis_power = float(np.dot(nu, plant.coriolis_matrix(nu) @ np.array(nu)))
                assert abs(coriolis_power) <= 1e-9


def _integrate(plant, state, load, step: float, steps: int) -> np.ndarray:
    x = np.array(state, dtype=np.float64)
    for _ in range(steps):
        x = rk4_step(plant, 0, step, x, load)
    return x


class TestSourceParityAndIntentionalRedesignSeparated:
    """Issue #61 AC4: parity vs redesign declared separately, never merged."""

    def test_parity_arm_is_structurally_equivalent_to_legacy(self, report) -> None:
        parity = report.source_parity
        assert parity["claim"] == "candidate_A2_migration_verified_only"
        assert parity["legacy_arm"] == "legacy"
        assert parity["modular_arm"] == "modular_legacy_equivalent"
        assert parity["shared_geometry_hash"] is True
        assert parity["shared_input_hash"] is True
        assert parity["kinematic_reference_following_exact"] is True

    def test_parity_scope_is_not_extended_to_new_factory_modules(self, report) -> None:
        assert "legacy-equivalent structure only" in report.source_parity["scope"]

    def test_redesign_ledger_is_separate_and_non_empty(self, report) -> None:
        ledger = report.intentional_redesign
        expected_count = (
            len(build_generic_3dof_plant_redesign_decisions())
            + len(build_marine_pid_redesign_decisions())
            + 6  # generic roll-4DOF plant redesign catalog
        )
        assert ledger["decision_count"] == expected_count
        assert all(decision["specification_reference"] for decision in ledger["decisions"])

    def test_parity_and_redesign_kinds_never_merge(self, report) -> None:
        assert report.source_parity["evidence_kind"] == "SOURCE_CHARACTERIZATION_REFERENCE"
        assert report.intentional_redesign["evidence_kind"] == "INTENTIONAL_REDESIGN"


class TestSystemEvidence:
    """Issue #61 G0/G1/G6/G7: identity, regression, and generality evidence."""

    def test_source_integrity_pinned(self, report) -> None:
        integrity = report.system_evidence["source_integrity"]
        assert integrity["pinned_legacy_commit"] == "8968f31b982d48773d08f814439827328bf4b35d"
        assert (
            integrity["characterization_manifest_sha256"]
            == "2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411"
        )

    def test_g6_pinned_baseline_comparison_passes(self, report) -> None:
        assert report.system_evidence["g6_pinned_baseline_comparison"] == "passed"

    def test_g7_generality_from_two_distinct_config_hashes(self, report) -> None:
        hashes = {run.config_hash for run in report.preset_runs}
        assert len(hashes) == 2

    def test_report_is_json_safe(self, report) -> None:
        assert json.loads(json.dumps(report.to_dict())) == report.to_dict()


class TestDeterminism:
    """Issue #61: every number reproducible from a local pytest run."""

    def test_preset_rerun_is_bit_identical(self) -> None:
        preset = DEMO_PRESETS[0]
        first = run_preset(preset)
        second = run_preset(preset)
        assert first.trace_digest == second.trace_digest
        assert first.navigation_final == second.navigation_final

    def test_snapshot_restore_continuation_is_identical(self) -> None:
        preset = DEMO_PRESETS[1]
        straight = run_preset(preset)
        restored = run_preset_with_restore(preset, restore_at_tick=preset.ticks // 2)
        assert restored.preset_id == preset.preset_id
        assert restored.restore_at_tick == preset.ticks // 2
        assert straight.trace_digest == restored.trace_digest


class TestClaimCeiling:
    """Issue #61 AC5: A3 ceiling; no calibration, A4-closure, SIL/HIL, or sea-trial claims."""

    def test_claim_ceiling_is_a3(self, report) -> None:
        assert DEMO_CLAIM_CEILING_LEVEL == "A3"
        assert DEMO_CLAIM_CEILING_LABEL == "Generalized Simulation"
        assert report.claim_ceiling == "A3"
        assert report.claim_ceiling_label == "Generalized Simulation"

    def test_explicit_non_claims_are_declared(self, report) -> None:
        assert len(ACCEPTANCE_NON_CLAIMS) >= 4
        assert report.non_claims == ACCEPTANCE_NON_CLAIMS
        rendered = " ".join(ACCEPTANCE_NON_CLAIMS).lower()
        for scope in ("calibration", "colav", "sil", "sea-trial", "vessel validation"):
            assert scope in rendered

    def test_claim_vocabulary_never_exceeds_ceiling(self, report) -> None:
        rendered = report.claim_ceiling + report.claim_ceiling_label
        rendered += "".join(gate.status for gate in report.gates)
        rendered += "".join(entry["status"] for entry in report.evidence_classes.values())
        for token in ("A4", "A5", "A6", "A7", "validated", "calibrated"):
            assert token not in rendered


class TestEvidenceDocumentConsistency:
    """The human-readable document is a verified projection of the report."""

    def test_document_exists(self) -> None:
        assert EVIDENCE_DOC.is_file()

    def test_gate_table_matches_report(self, report) -> None:
        rows = {}
        for line in EVIDENCE_DOC.read_text(encoding="utf-8").splitlines():
            if line.startswith("| G") and line.count("|") >= 4:
                cells = [cell.strip() for cell in line.split("|")]
                rows[cells[1]] = cells[2]
        for gate in report.gates:
            assert rows[gate.gate_id] == gate.status, gate.gate_id

    def test_pinned_numbers_match_report(self, report) -> None:
        document = EVIDENCE_DOC.read_text(encoding="utf-8")
        for run in report.preset_runs:
            assert run.config_hash in document
            assert run.trace_digest in document
            assert f"{run.guidance_evidence['final_abs_cross_track_error_m']:.4f}" in document
            assert f"{run.control_evidence['final_abs_speed_error_mps']:.4f}" in document
