"""Red tests for the S10 repair round."""

from __future__ import annotations

import json
from pathlib import Path

from colav_simulator.modular_gnc.catalog import list_stack_catalog


def test_pre_s10_snapshot_contains_canonical_evidence_documents() -> None:
    snapshot = json.loads((Path(__file__).parent / "fixtures" / "stack_catalog_pre_s10.json").read_text())
    assert len(snapshot["evidence_documents"]) == len(snapshot["stack_ids"]) == 82
    assert all(isinstance(value, str) and value for value in snapshot["evidence_documents"].values())


def test_snapshot_evidence_documents_match_catalog_byte_for_byte() -> None:
    snapshot = json.loads((Path(__file__).parent / "fixtures" / "stack_catalog_pre_s10.json").read_text())
    catalog = {entry["stack_id"]: entry for entry in list_stack_catalog()["stacks"]}
    for stack_id, expected in snapshot["evidence_documents"].items():
        assert json.dumps(catalog[stack_id], sort_keys=True, ensure_ascii=True) == expected


def test_standard_load_and_rudder_provenance_have_structured_deviation_ledgers() -> None:

    catalog = list_stack_catalog()
    env_entry = next(entry for entry in catalog["stacks"] if "analytic_environment_field" in entry["stack_id"])
    load_provenance = next(
        module["parameter_provenance"]
        for module in env_entry["modules"]
        if module["identity"] == "standard_environmental_load"
    )
    assert isinstance(load_provenance["deviation_ledger"], list)
    required = ("6 m/s", "7.8 m/s", "sigma", "stall", "bow tunnel", "synchron", "200 kN/s", "1.55", "OCIMF")
    ledger_text = " ".join(load_provenance["deviation_ledger"])
    assert all(token.lower() in ledger_text.lower() for token in required)

    rudder_entry = next(
        entry for entry in catalog["stacks"] if "fcb45_main_rudder_actuator_layout_v1" in entry["stack_id"]
    )
    asset = next(item for item in rudder_entry["asset_trust"] if item["asset_type"] == "actuator_layout")
    assert asset["trust_level"] != "validated_for_vessel"
