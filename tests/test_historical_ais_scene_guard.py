"""Compatibility guards for the first independent Historical AIS catalog scene.

These tests keep the scripted scenario corpus and the verified exact tuples as
characterization baselines.  Per ADR-0004 the Historical AIS scene is merged
into the product catalog as Counterfactual-only EXPERIMENTAL tuples; verified
tuples and the YAML corpus stay unchanged.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from gui_server.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_ROOT = PROJECT_ROOT / "scenarios"
HISTORICAL_AIS_SCENE_ID = "hais_romsdal_20260701_120007_121007"

# Byte-level characterization of the committed scripted scenario corpus.  A
# new independent Historical AIS descriptor may be added, but existing files
# must not be rewritten or re-identified as that descriptor.
EXPECTED_SCENARIO_YAML_SHA256 = {
    "aalesund_random1": "febd4c30503cdb559204eca026bbbd5cd8489f88e8d499fd0637c274ac539252",
    "ais_scenario1": "aa2383d9efc987e2845ba1dada7580a384255f51c7557bdf28aa7feb30ad8503",
    "ais_scenario_west_coast": "ec9a7045541d70478b2539f27d6ec22f1ea7008c5ca0810b502922d60b62f7c2",
    "boknafjorden_generation_test": "ddce6bb026b82c5ac2fe2401dc44de295a9d06500f47940662fbd5301d7354ba",
    "crossing_give_way": "3fa4a46b1bf3d0b9bcf20ef878edcbfdb9cc9b975d653b8adf2b051763e2ba72",
    "crossing_stand_on": "83485565d21030a46a2e36920746d32a2720a357ce7db1c20b93de1ca86f3f91",
    "head_on": "0005ab9993afd8d0de4d408865ed6729c5cfab9bf8585d3876c4772e55df90a9",
    "head_on_sbmpc": "cee9a5dfc968d170c3a870c17f71bfd76585352bc5c28ec87c00b573485c5ffb",
    "imazu_cases/imazu01": "496d45a1e8432067c2429d72ec49476b1a8b43cef2c5f7c9cbd2805815c7fd6f",
    "imazu_cases/imazu02": "ff3690622f07585eca318d9681ac91e2335126915e2b6cbec23b29d333807aa6",
    "imazu_cases/imazu03": "92500c183a2d3c8dc896f40eb219a68d7b86cc707f5f0afb0b03a0b85a4a5ead",
    "imazu_cases/imazu04": "e91863ea9f0de050f5e52def78df1fda26b0f0fd3cf1249ca4f8603341a0286f",
    "imazu_cases/imazu05": "ec4d85c41ed0f202378b6162686943256c78c1c2413a1d3c7af5276da3cdbc69",
    "imazu_cases/imazu06": "a5c230f0f41935f4fcb82f0b5c69bee4771338171c475577584254c5620025b4",
    "imazu_cases/imazu07": "cd767e776b7a21831a07f957aa798965c1b3fcee1a77b0b120bd1d0d6b12d4cb",
    "imazu_cases/imazu08": "c92ad9733e56d77178928ee06626ac0563182e685d413b922be0ecd9809190e8",
    "imazu_cases/imazu09": "9047e92d86282941ef4a8ea17c34898366f4ddd63259753dd2a73d71642a869e",
    "imazu_cases/imazu10": "a212956aefed2c77155721328df078cf0f481f1b3bab3f71b12dd3f6caed204f",
    "imazu_cases/imazu11": "0802e532a191b9d2bf5463f14e694a37c94e67ffc721891561f606c6244396f7",
    "imazu_cases/imazu12": "dd2eac86eec2d25217a820de6601885c01cb000cedd1411e85888ecb8c755ae3",
    "imazu_cases/imazu13": "46ce51b38119970af4811e2838cea243b103bd630035189f0594290c98079781",
    "imazu_cases/imazu14": "a62038b70e0deb2bc489b5b0727f289674235baf6a905c3fce72e6c042e5b9ab",
    "imazu_cases/imazu15": "19df748746af1d114b84be62ce9b559b7ddf64f3db36ca2e8b878bc8bc481b67",
    "imazu_cases/imazu16": "fb890f7edc41f49785d19b6cab081015e010c309f40a3f64f6019ec0e12d04f4",
    "imazu_cases/imazu17": "a144cad5e5f56f7cd1edc173544faad82236440b459ac8bc4947f1f02988bcf7",
    "imazu_cases/imazu18": "8aa623f0a2310fb1a0d813cbf6247be53c1ccf0238281ed5827d185944abb0b9",
    "imazu_cases/imazu19": "15e604829de65c406667f2cdf731ea6fd4921b18ee2063a59a1983751ae350b0",
    "imazu_cases/imazu20": "1bf2d75a64c3b3af6774e7f730b445ab2f1c8683bb45f9ff50edcfd4d1adb97f",
    "imazu_cases/imazu21": "0d355160a53511a6ad357fce5b0107597690dfe02f6604c58363900320fb75f3",
    "imazu_cases/imazu22": "f45570b8f01e4dce91a61df9366ca14d38f6a96348b6fe004266d8bbe1067e5a",
    "overtaken": "443ae23c7a2f39b4d83875d39624020ffdc41f3e1b8a4faa83f1b06caa0a2dea",
    "overtaking": "bb7c7a103cea3d513d530837d1c5fd9d8ac24d58123642998189bec5c32a619d",
    "overtaking_port_corridor": "aa71ae94abe31f572428caa5ac7c5f4ee6c381e73ae5dbbafd749ed85ee27cc1",
    "paper_ccta2023_head_on": "65268eb4e5fc43072974e7654aee6a8b5be148e969e0277b226c8d2903d3ff9b",
    "paper_ccta2023_multiship": "5dfdb3d5c95b2fb0b565386ac818a6c1a75f2a8cbab1854a7c8a7c13c1007486",
    "planning_example": "9edecccb4650166cefddcc293d57e6370075d531f026cece1b1c39af80921fd3",
    "rl_scenario": "2c0d06e758a2bfd8efd7e388d2adce93806fce7402aac186caa5666db8b0e979",
    "rl_scenario_smaller": "8214092112da7307bbfccc73fb9d93d19bd11361ccbdd89fb4bb3760ec65ab98",
    "rlmpc_scenario": "30795e63a6c6d9448aa981c195268a37196ae77d66db663833d666f1fa1752ba",
    "rlmpc_scenario_ms_channel": "efc9c69858b6d17f15812eaa1afc2bf5cc0b9fb1ce755be468a9e4c6b532b19f",
    "rlmpc_scenario_ms_channel_vimmjipda": "a21c0375e727c0bc54237398f790bce4aafb9a1ceaae622eefbea9ae16224ead",
    "rogaland_random_rl": "564d37589880dd50c38d5e5c345ecb16a88cd39f87748b11f215b2599eb7da4c",
    "romsdal_busy_water_16": "851a238d1e6b84ad623d720c1dc02fe2acee17688df4176b46ec4f57aea43e38",
    "romsdal_busy_water_80_stress": "d614c32314bc1e2a7ab540d1fd298f80bfdb0cc0aefbaa015e591ae3b5ed350b",
    "rrt_test": "ea62d5ba5c1b0182bebbc1d6c9c46d3c8baa38991d3b270fc27edf9e0be5a4b2",
    "simple_planning_example": "cfeda84231b6b19812e66f91a8cd4e4df6bb802fc23441df1ddb1083e16caa27",
}

EXPECTED_VERIFIED_TUPLES = frozenset(
    {
        ("rule14", "head_on", "mid_mpc_ipopt", "god"),
        ("rule14", "head_on", "vo", "god"),
        ("rule14", "head_on", "potocnik_colreg_fan_mpc", "god"),
        ("rule13", "overtaking", "mid_mpc_ipopt", "god"),
        ("rule13", "overtaking", "vo", "god"),
        ("rule13", "overtaking", "potocnik_colreg_fan_mpc", "god"),
        ("rule13", "overtaken", "mid_mpc_ipopt", "god"),
        ("rule13", "overtaken", "vo", "god"),
        ("rule13", "overtaken", "potocnik_colreg_fan_mpc", "god"),
        ("rule15", "crossing_give_way", "mid_mpc_ipopt", "god"),
        ("rule15", "crossing_give_way", "vo", "god"),
        ("rule15", "crossing_give_way", "potocnik_colreg_fan_mpc", "god"),
        ("rule15", "crossing_stand_on", "mid_mpc_ipopt", "god"),
        ("rule15", "crossing_stand_on", "vo", "god"),
        ("rule15", "crossing_stand_on", "potocnik_colreg_fan_mpc", "god"),
        ("multiship", "paper_ccta2023_multiship", "mid_mpc_ipopt", "god"),
        ("multiship", "paper_ccta2023_multiship", "vo", "god"),
        ("multiship", "paper_ccta2023_multiship", "potocnik_colreg_fan_mpc", "god"),
    }
)


def test_existing_scenario_yaml_files_are_byte_stable() -> None:
    observed = {
        scenario_id: hashlib.sha256((SCENARIOS_ROOT / f"{scenario_id}.yaml").read_bytes()).hexdigest()
        for scenario_id in EXPECTED_SCENARIO_YAML_SHA256
    }

    assert observed == EXPECTED_SCENARIO_YAML_SHA256


def test_existing_scenario_ids_remain_in_api_catalog() -> None:
    with TestClient(app) as client:
        response = client.get("/api/scenarios")

    assert response.status_code == 200
    observed_ids = {item["id"] for item in response.json()}
    assert set(EXPECTED_SCENARIO_YAML_SHA256) <= observed_ids
    # ADR-0004: the Historical AIS scene is listed through the merged catalog seam.
    assert HISTORICAL_AIS_SCENE_ID in observed_ids


def test_existing_verified_exact_tuples_remain_unchanged_and_independent() -> None:
    with TestClient(app) as client:
        catalog = client.get("/api/capabilities").json()
        filtered_catalogs = {
            rule_id: client.get("/api/capabilities", params={"validation_rule_id": rule_id}).json()
            for rule_id in ("rule13", "rule14", "rule15", "multiship")
        }

    tuple_fields = ("validation_rule_id", "scenario_id", "algorithm_id", "tracker_id")
    observed = {
        tuple(item[field] for field in tuple_fields)
        for item in catalog["verified_combinations"]
    }
    assert observed == EXPECTED_VERIFIED_TUPLES

    for rule_id, filtered in filtered_catalogs.items():
        observed_filtered = {
            tuple(item[field] for field in tuple_fields)
            for item in filtered["verified_combinations"]
        }
        assert observed_filtered == {item for item in EXPECTED_VERIFIED_TUPLES if item[0] == rule_id}

    # ADR-0004: the Historical AIS scene is Counterfactual-only EXPERIMENTAL —
    # never verified, never nominal-selectable, and confined to the multiship rule.
    hais_experimental = {
        tuple(item[field] for field in tuple_fields)
        for item in catalog["experimental_combinations"]
        if item["scenario_id"] == HISTORICAL_AIS_SCENE_ID
    }
    assert hais_experimental == {
        ("multiship", HISTORICAL_AIS_SCENE_ID, "vo", "god"),
        ("multiship", HISTORICAL_AIS_SCENE_ID, "potocnik_colreg_fan_mpc", "god"),
    }
    hais_scenarios = [item for item in catalog["scenarios"] if item["id"] == HISTORICAL_AIS_SCENE_ID]
    assert len(hais_scenarios) == 1
    assert hais_scenarios[0]["supported_rules"] == ["multiship"]
    assert hais_scenarios[0]["historical_ais"]["reference_mmsi"] == 259189000


def test_independent_historical_ais_catalog_publishes_current_scene() -> None:
    """The dedicated catalog publishes the bounded independent AIS scene."""
    with TestClient(app) as client:
        response = client.get("/api/historical/scenarios")

    assert response.status_code == 200
    assert [item["scenario_id"] for item in response.json()] == [HISTORICAL_AIS_SCENE_ID]
