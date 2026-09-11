"""Honest qualification gate and original-backend capability tuple contracts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from colav_simulator.core.colav.mid_mpc_acceptance import PlanAcceptancePolicy
from colav_simulator.integrations.mid_mpc_ipopt import _active_capability
from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput
from colav_simulator.core.colav.mid_mpc_assembler import MidMpcAssemblyConfig
from colav_simulator.original_gnc import qualification

REPO_ROOT = Path(__file__).resolve().parents[1]
RESPONSE_ARTIFACT = (
    REPO_ROOT / "colav_simulator" / "original_gnc" / "data" / "response_approximation.json"
)
ORIGINAL_MODEL = "original_gnc_20260824_v2"
ORIGINAL_CONTROLLER = "original_ship_control_20260824_v2"
ORIGINAL_TUPLE = "original-gnc:first_order_lag:source_control"


def _planner_input(model: str, controller: str) -> PlannerInput:
    return PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=5.0,
        waypoints_enu_m=np.array([[0.0, 100.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([2.0, 2.0]),
        ownship_state=np.zeros(6),
        tracks=(),
        enc=None,
        goal_state=None,
        disturbance=None,
        algorithm_seed=0,
        ownship_model=model,
        ownship_controller=controller,
    )


def _facade_config() -> object:
    class _Config:
        assembly = MidMpcAssemblyConfig()
        total_deadline_s = 20.0

    return _Config()


# ---- explicit qualification rule ----


def test_trajectory_threshold_is_explicit() -> None:
    assert qualification.TRAJECTORY_R_SQUARED_THRESHOLD == 0.90


def test_channel_requires_trajectory_basis() -> None:
    assert qualification.channel_qualified({"trajectory_r_squared": 0.911})
    assert not qualification.channel_qualified({"trajectory_r_squared": 0.899})
    assert not qualification.channel_qualified({"r_squared": 0.99})
    assert not qualification.channel_qualified({})


def test_packaged_response_artifact_qualifies() -> None:
    document = qualification.load_document()
    qualified, failures = qualification.evaluate(document)
    assert qualified, failures
    assert failures == ()
    assert qualification.verdict_string(document) == "QUALIFIED_FIRST_ORDER_TRAJECTORY_APPROXIMATION"


def test_artifact_label_matches_computed_verdict() -> None:
    document = json.loads(RESPONSE_ARTIFACT.read_text())
    assert document["schema"] == "original-gnc.response-approximation.v2"
    assert document["qualification"] == qualification.verdict_string(document)


def test_artifact_keeps_legacy_derivative_evidence() -> None:
    document = json.loads(RESPONSE_ARTIFACT.read_text())
    for channel in ("course", "speed"):
        derivative = document[channel]["derivative"]
        assert "r_squared" in derivative and "time_constant_s" in derivative
    # The speed channel's legacy derivative basis is the historical blocker: it
    # stays below the threshold even though the trajectory basis qualifies.
    assert document["speed"]["derivative"]["r_squared"] < qualification.TRAJECTORY_R_SQUARED_THRESHOLD


def test_below_threshold_channel_fails_evaluation() -> None:
    document = qualification.load_document()
    document["speed"]["trajectory_r_squared"] = 0.5
    qualified, failures = qualification.evaluate(document)
    assert not qualified
    assert failures == ("speed",)
    assert qualification.verdict_string(document) == "UNQUALIFIED_TRAJECTORY_APPROXIMATION"


# ---- capability tuple mapping and policy ----


def test_original_backend_emits_qualified_tuple() -> None:
    capability = _active_capability(_planner_input(ORIGINAL_MODEL, ORIGINAL_CONTROLLER), _facade_config())
    assert capability.exact_tuple == ORIGINAL_TUPLE
    assert capability.limitations == ()


def test_original_backend_reverts_to_unsupported_when_unqualified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = qualification.load_document()
    document["speed"]["trajectory_r_squared"] = 0.5
    monkeypatch.setattr(qualification, "load_document", lambda: document)
    capability = _active_capability(_planner_input(ORIGINAL_MODEL, ORIGINAL_CONTROLLER), _facade_config())
    assert capability.exact_tuple == "unsupported:originalgnc20260824v2:originalshipcontrol20260824v2"
    assert capability.limitations == ("UNSUPPORTED_ACTIVE_TUPLE",)


def test_known_tuples_keep_their_existing_mapping() -> None:
    viknes = _active_capability(_planner_input("viknes", "flsc"), _facade_config())
    assert viknes.exact_tuple == "single-encounter:viknes:flsc"
    multiship = _active_capability(_planner_input("kinematic_csog", "pass_through_cs"), _facade_config())
    assert multiship.exact_tuple == "multiship:kinematic_csog:pass_through_cs"


def test_policy_allows_qualified_original_tuple() -> None:
    assert ORIGINAL_TUPLE in PlanAcceptancePolicy().allowed_capability_tuples
