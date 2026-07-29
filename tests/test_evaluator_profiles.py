from __future__ import annotations

import dataclasses

import pytest

from colav_simulator.evaluation.profiles import (
    DEFAULT_EVALUATOR_PROFILE_ID,
    available_profiles,
    load_evaluator_profile,
)
from colav_simulator.evaluation.scoring import safety_domain_score


def test_named_profiles_are_frozen_hashable_and_source_traceable() -> None:
    assert {
        "ccta_2023_demo-v1",
        "oe2023_simulated-v1",
        "ship_length_scaled-v1",
    }.issubset(available_profiles())
    profile = load_evaluator_profile(DEFAULT_EVALUATOR_PROFILE_ID)
    assert profile.profile_id == "ccta_2023_demo-v1"
    assert profile.stages.stage2_entry_m == 2500.0
    assert profile.safety.collision_m == 30.0
    assert profile.encounter.alpha_crit_14_deg == 13.0
    assert len(profile.profile_hash) == 64
    assert profile.profile_hash == load_evaluator_profile(profile.profile_id).profile_hash
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.profile_id = "mutated"  # type: ignore[misc]


def test_paper_profiles_are_not_silently_mixed() -> None:
    ccta = load_evaluator_profile("ccta_2023_demo-v1")
    journal = load_evaluator_profile("oe2023_simulated-v1")
    assert ccta.profile_hash != journal.profile_hash
    assert ctta_values(ccta) == (2500.0, 1100.0, 200.0, 190.0, 100.0, 50.0, 30.0)
    assert ctta_values(journal) == (1900.0, 700.0, 200.0, 200.0, 100.0, 50.0, 35.0)


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unknown evaluator profile"):
        load_evaluator_profile("invented-best-profile")


def test_ship_length_profile_uses_sourced_fujii_ellipse() -> None:
    profile = load_evaluator_profile("ship_length_scaled-v1")
    assert profile.safety_domain.model == "fujii_1971"
    assert profile.safety_domain.longitudinal_length_factor == 4.0
    assert profile.safety_domain.transverse_length_factor == 1.6
    assert safety_domain_score(40.0, 0.0, 10.0, profile) == pytest.approx(1.0)
    assert safety_domain_score(16.0, 0.5 * 3.141592653589793, 10.0, profile) == pytest.approx(1.0)
    assert safety_domain_score(8.0, 0.5 * 3.141592653589793, 10.0, profile) == pytest.approx(0.5)


def ctta_values(profile: object) -> tuple[float, ...]:
    value = profile
    return (
        value.stages.stage2_entry_m,
        value.stages.stage3_entry_m,
        value.stages.stage4_entry_m,
        value.safety.preferred_m,
        value.safety.minimum_m,
        value.safety.near_miss_m,
        value.safety.collision_m,
    )
