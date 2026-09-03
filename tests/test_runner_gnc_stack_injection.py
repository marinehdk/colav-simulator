"""Runner-level GNC stack binding: validation and ownship injection (Config step 04)."""

from __future__ import annotations

import pytest

from colav_simulator.core.colav.diagnostics import ColavExecutionError
from colav_simulator.experiment.contracts import InternalExecutionPurpose, RunSpec
from colav_simulator.experiment.runner import ExperimentRunner
from colav_simulator.modular_gnc.adapter import ModularShipAdapter
from colav_simulator.modular_gnc.catalog import list_stack_catalog
from colav_simulator.modular_gnc.configuration import normalize_ship_modules


def _a_stack_id() -> str:
    return list_stack_catalog()["stacks"][0]["stack_id"]


def test_prepare_rejects_unknown_gnc_stack_id() -> None:
    runner = ExperimentRunner()
    spec = RunSpec(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        ownship_gnc_stack_id="not-a-catalog-stack",
    )

    with pytest.raises(ColavExecutionError, match="Unknown ownship GNC stack id"):
        runner.prepare(spec)


def test_prepare_rejects_gnc_stack_for_historical_replay_spec() -> None:
    runner = ExperimentRunner()
    spec = RunSpec(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        ownship_gnc_stack_id=_a_stack_id(),
        historical_replay={"mode": "HISTORICAL_REPLAY"},
    )

    with pytest.raises(ColavExecutionError, match="GNC stack binding is not supported"):
        runner.prepare(spec)


def test_prepare_internal_rejects_gnc_stack_id() -> None:
    runner = ExperimentRunner()
    spec = RunSpec(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        ownship_gnc_stack_id=_a_stack_id(),
        historical_replay={"mode": "HISTORICAL_REPLAY"},
    )

    with pytest.raises(ColavExecutionError, match="GNC stack binding is not supported"):
        runner.prepare_internal(spec, purpose=InternalExecutionPurpose.HISTORICAL_REPLAY)


def test_prepare_injects_selected_stack_into_ownship_ship_modules() -> None:
    stack_id = _a_stack_id()
    runner = ExperimentRunner()
    spec = RunSpec(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        t_end=1.0,
        ownship_gnc_stack_id=stack_id,
    )

    prepared = runner.prepare(spec)

    ownship = prepared.session.ship_list[0]
    assert isinstance(ownship, ModularShipAdapter)
    expected = next(
        normalize_ship_modules(entry["config"])
        for entry in list_stack_catalog()["stacks"]
        if entry["stack_id"] == stack_id
    )
    assert ownship.modular_stack_config.config_hash == expected.config_hash

    replacement = runner.prepare_reset(prepared)
    replacement_ownship = replacement.session.ship_list[0]
    assert replacement.manifest.run_id != prepared.manifest.run_id
    assert replacement.manifest.episode_hash == prepared.manifest.episode_hash
    assert replacement.manifest.enc_hash == prepared.manifest.enc_hash
    assert isinstance(replacement_ownship, ModularShipAdapter)
    assert replacement_ownship is not ownship
    assert replacement_ownship.modular_stack_config.config_hash == expected.config_hash


def test_prepare_without_gnc_stack_keeps_legacy_ownship() -> None:
    runner = ExperimentRunner()
    spec = RunSpec(
        scenario_id="head_on",
        validation_rule_id="rule14",
        algorithm_id="vo",
        tracker_id="god",
        t_end=1.0,
    )

    prepared = runner.prepare(spec)
    replacement = runner.prepare_reset(prepared)

    assert not isinstance(prepared.session.ship_list[0], ModularShipAdapter)
    assert not isinstance(replacement.session.ship_list[0], ModularShipAdapter)
