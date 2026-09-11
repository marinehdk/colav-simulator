"""Product identity for the independent original-source GNC backend."""

from __future__ import annotations

import hashlib
import json

from colav_simulator.original_gnc.configuration import BASELINE, SOURCE_MANIFEST_SHA256, OriginalGncConfig
from colav_simulator.original_gnc.native import NativeModule

ENVIRONMENT_DESCRIPTION = (
    "Original models · wind U10 6 m/s from 45° · current 0.3 m/s from 90° · waves Hs 0.5 m / Tz 6 s from 90°"
)


def original_catalog() -> tuple[list[dict], dict]:
    """Expose dependency availability separately from unaccepted scenario compatibility."""
    available = True
    reason = None
    try:
        config = OriginalGncConfig.from_dict({})
        roots, assets, _ = config.source_assets()
        with NativeModule(
            config.build_directory,
            "ship_dynamics_node",
            config.parameters()["ship_dynamics_node"],
            {"time_ns": 2_000_000_000_000_000_000, "package_roots": roots, "asset_paths": assets},
        ):
            pass
        extraction = json.loads((config.build_directory / "extraction.json").read_text())
        if (
            not {"navigation_mode_observer_node", "operational_risk_observer_node", "operator_command_interpreter"}
            <= extraction.get("python_observers", {}).keys()
        ):
            raise ValueError("Original observation modules are not built; rebuild the source backend")
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        available = False
        reason = str(error)
    entries = []
    for enabled in (False, True):
        selection = OriginalGncConfig.from_dict({"environment": enabled})
        identity = {
            "backend": "original_gnc",
            "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "baseline_sha256": hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
            "environment": enabled,
            "response_approximation_sha256": hashlib.sha256(
                BASELINE.with_name("response_approximation.json").read_bytes()
            ).hexdigest(),
            "bridge_contract": "original-gnc-route-authority.v1",
        }
        entries.append(
            {
                "schema_version": 1,
                "backend_kind": "original_gnc",
                "stack_id": selection.stack_id,
                "display_name": "Original GNC 2026-08-24" + (" · environment ON" if enabled else " · environment OFF"),
                "config_hash": hashlib.sha256(
                    json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "fidelity_profile": "frozen_original_source_port",
                "supported_tasks": ["TRANSIT"],
                "modules": [
                    {
                        "role": role,
                        "identity": name,
                        "interface_version": "original-20260824-v2",
                        "acceptance_evidence": "Independent original-source replay; full scenario acceptance separate",
                    }
                    for role, name in [
                        ("plant", "ship_dynamics_node"),
                        ("guidance", "ship_guidance_node"),
                        ("controller", "ship_control_node"),
                        ("allocation", "thrust_allocation_node"),
                    ]
                ],
                "asset_trust": [
                    {"asset_id": "L4-5_source_only_20260824_v2", "trust_level": "source hash pinned; design parameters"}
                ],
                "acceptance_level": "EXPERIMENTAL_ORIGINAL_SOURCE",
                "available": available,
                "unavailable_reason": reason,
                "config": identity,
            }
        )
    preset = {
        "id": "original_gnc",
        "display_name": "Original GNC · 2026-08-24",
        "description": "Frozen colleague GNC · independent local C++ backend",
        "input": "Original route / avoidance contract",
        "available": available,
        "unavailable_reason": reason,
        "variants": {"off": entries[0]["stack_id"], "on": entries[1]["stack_id"]},
        "environment_description": ENVIRONMENT_DESCRIPTION,
        "note": (
            "Original guards and PGD degradation retained. Ordinary route updates require 500 m lookahead; "
            "short avoidance intents can be rejected. Source equivalence and scenario safety are separate results."
        ),
        "fields": {
            "Plant": "Original 4DOF · 44.1 × 8 × 2 m",
            "Guidance": "Original ILOS/ALOS · route guards · terminal DP",
            "Controller": "Original PID/SMC and source mode logic",
            "Actuation": "Original PGD · actuator dynamics and limits",
        },
    }
    return entries, preset
