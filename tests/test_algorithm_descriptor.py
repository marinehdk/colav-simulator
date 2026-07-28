from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import (
    AlgorithmDescriptor,
    BuildIdentity,
    ExecutionProfile,
)


def descriptor() -> AlgorithmDescriptor:
    return AlgorithmDescriptor(
        algorithm_id="paper_mpc",
        version="1.0",
        control_form="course_speed_reference",
        state_layout=("x", "y", "psi", "u", "v", "r", "x_ddot", "y_ddot", "psi_dot"),
        predictor_model="3dof",
        horizon_dt=0.5,
        horizon_steps=5,
        objective_terms=("tracking", "collision"),
        constraint_terms=("dynamics", "collision"),
        solver="ipopt",
        seed_policy="seeded",
        execution_profile=ExecutionProfile(solve_period_s=1.0, deadline_s=0.2),
    )


def test_algorithm_descriptor_hash_is_stable_and_envelope_is_complete() -> None:
    first = descriptor()
    second = descriptor()
    identity = BuildIdentity("pkg:create", "a", "b", "c", "1.2.3")

    assert first.hash == second.hash
    assert first.envelope(identity)["descriptor_hash"] == first.hash
    assert first.envelope(identity)["fallback_policy"] == "forbidden"
    assert first.envelope(identity)["build_identity_hash"] == identity.hash
    assert identity.complete is True


def test_algorithm_descriptor_is_frozen_and_rejects_invalid_static_contracts() -> None:
    value = descriptor()
    with pytest.raises(FrozenInstanceError):
        value.version = "2.0"  # type: ignore[misc]
    with pytest.raises(ValueError, match="duplicates"):
        AlgorithmDescriptor(
            **{
                **value.__dict__,
                "objective_terms": ("tracking", "tracking"),
            }
        )
    with pytest.raises(ValueError, match="horizon_steps"):
        AlgorithmDescriptor(**{**value.__dict__, "horizon_steps": 0})


def test_unknown_build_identity_is_not_formal_run_complete() -> None:
    assert BuildIdentity().complete is False
    assert BuildIdentity("", "a", "b", "c", "1").complete is False


def test_descriptor_rejects_nonfinite_execution_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        ExecutionProfile(solve_period_s=np.nan, deadline_s=1.0)
    with pytest.raises(ValueError, match="finite"):
        AlgorithmDescriptor(**{**descriptor().__dict__, "horizon_dt": np.inf})
