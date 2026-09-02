"""Legacy-equivalent modular profile and G8 four-arm local attribution binding (Issue #56, AC3/AC4)."""

from __future__ import annotations

import numpy as np
import pytest

from colav_simulator.modular_gnc.attribution import (
    ArmIdentity,
    AttributionError,
    FourArmBinding,
    run_g8_four_arm_binding,
)
from colav_simulator.modular_gnc.configuration import normalize_ship_modules
from colav_simulator.modular_gnc.contracts import CommandInput, DirectReference, NavigationState
from colav_simulator.modular_gnc.factory import legacy_equivalent_profile
from colav_simulator.modular_gnc.stack import ModularShipStack

G8_ARM_LABELS = frozenset(
    {
        "legacy",
        "modular_legacy_equivalent",
        "modular_new_plant_passthrough",
        "modular_new_plant_marine_pid",
    }
)


class TestLegacyEquivalentProfile:
    """Canonical modular profile: kinematic-reference plant + pass-through controller (AC3)."""

    def test_profile_pairs_kinematic_pass_through_plant_with_pass_through_controller(self) -> None:
        profile = legacy_equivalent_profile()
        normalized = normalize_ship_modules(profile)

        assert normalized.modules["plant"].identity == "pass_through_plant"
        assert normalized.modules["controller"].identity == "pass_through_controller"
        assert normalized.modules["guidance"].identity == "pass_through_guidance"

    def test_profile_is_deterministic_and_content_addressed(self) -> None:
        first = normalize_ship_modules(legacy_equivalent_profile())
        second = normalize_ship_modules(legacy_equivalent_profile())

        assert first.config_hash == second.config_hash

    def test_profile_executes_kinematic_reference_schedule_deterministically(self) -> None:
        stack = ModularShipStack.from_config(normalize_ship_modules(legacy_equivalent_profile()))
        stack.reset(NavigationState(100.0, -50.0, 4.0, 0.25, 0.0, 0.0), seed=42042)

        schedule = {0: (0.35, 4.5), 5: (-0.1, 3.75)}
        states = []
        current = np.zeros(9)
        for tick in range(12):
            if tick in schedule:
                current[2], current[3] = schedule[tick]
            command = CommandInput.direct(tick, DirectReference(current.copy(), latched_tick=tick))
            output = stack.step(command, dt_s=0.2)
            assert output.failure is None
            states.append(output.plant)

        # Kinematic pass-through contract: heading and surge follow the latched reference exactly.
        assert states[0].heading_rad == pytest.approx(0.35)
        assert states[0].surge_mps == pytest.approx(4.5)
        assert states[4].heading_rad == pytest.approx(0.35)
        assert states[4].surge_mps == pytest.approx(4.5)
        assert states[5].heading_rad == pytest.approx(-0.1)
        assert states[5].surge_mps == pytest.approx(3.75)
        assert states[11].heading_rad == pytest.approx(-0.1)
        assert states[11].surge_mps == pytest.approx(3.75)


class TestG8FourArmBinding:
    """Four arms on identical deterministic local inputs with content-addressed identity (AC4)."""

    @pytest.fixture(scope="class")
    def binding(self) -> FourArmBinding:
        return run_g8_four_arm_binding()

    def test_binding_contains_exactly_the_four_canonical_arms(self, binding: FourArmBinding) -> None:
        assert frozenset(binding.arms) == G8_ARM_LABELS

    def test_all_arms_share_geometry_and_input_hash(self, binding: FourArmBinding) -> None:
        for arm in binding.arms.values():
            assert arm.geometry_hash == binding.geometry_hash
            assert arm.input_hash == binding.input_hash

    def test_each_arm_has_independent_source_config_trace_identity(self, binding: FourArmBinding) -> None:
        identities = {(arm.source_hash, arm.config_hash, arm.trace_hash) for arm in binding.arms.values()}

        assert len(identities) == 4
        for arm in binding.arms.values():
            assert len(arm.source_hash) == 64
            assert len(arm.config_hash) == 64
            assert len(arm.trace_hash) == 64

    def test_binding_is_reproducible(self, binding: FourArmBinding) -> None:
        assert run_g8_four_arm_binding() == binding

    def test_attribution_follows_content_not_labels(self, binding: FourArmBinding) -> None:
        legacy = binding.arms["legacy"]
        modular = binding.arms["modular_legacy_equivalent"]

        # Same label with tampered content must not attribute.
        assert not binding.attributes_to(legacy, ArmIdentity(
            label="legacy",
            geometry_hash=legacy.geometry_hash,
            input_hash=legacy.input_hash,
            source_hash=legacy.source_hash,
            config_hash=legacy.config_hash,
            trace_hash="0" * 64,
        ))
        # Different label with identical content is attributable: labels never decide.
        relabeled = ArmIdentity(
            label="some_other_label",
            geometry_hash=modular.geometry_hash,
            input_hash=modular.input_hash,
            source_hash=modular.source_hash,
            config_hash=modular.config_hash,
            trace_hash=modular.trace_hash,
        )
        assert binding.attributes_to(modular, relabeled)

    def test_label_only_attribution_claim_is_rejected(self, binding: FourArmBinding) -> None:
        with pytest.raises(AttributionError, match="label-only"):
            binding.attributes_to_label_only("legacy", "legacy")

    def test_arm_identity_rejects_missing_content_hashes(self) -> None:
        with pytest.raises(AttributionError, match="source_hash"):
            ArmIdentity(
                label="legacy",
                geometry_hash="a" * 64,
                input_hash="b" * 64,
                source_hash="not-a-hash",
                config_hash="c" * 64,
                trace_hash="d" * 64,
            )

    def test_binding_rejects_unknown_arm_labels(self) -> None:
        binding = run_g8_four_arm_binding()
        tampered_arms = dict(binding.arms)
        tampered_arms["rogue_arm"] = tampered_arms["legacy"]

        with pytest.raises(AttributionError, match="rogue_arm"):
            FourArmBinding(
                geometry_hash=binding.geometry_hash,
                input_hash=binding.input_hash,
                arms=tampered_arms,
            )
