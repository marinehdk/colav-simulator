"""Product identity for the Authoritative MPC controller lane."""

from __future__ import annotations

import hashlib
import json

from colav_simulator.authoritative_mpc.configuration import BASELINE, MPC_SOURCE_MANIFEST_SHA256, AuthoritativeMpcConfig
from colav_simulator.original_gnc.native import NativeModule

ENVIRONMENT_DESCRIPTION = (
    "Original models · wind U10 6 m/s from 45° · current 0.3 m/s from 90° · waves Hs 0.5 m / Tz 6 s from 90°"
)


def _build_identity(manifest: dict) -> dict:
    """Expose the loaded native build lane without changing stack semantics."""
    return {
        "execution_lane": "mpc_controller",
        "candidate": manifest.get("controller_package"),
        "proposal_ids": [],
        "controller_package": manifest.get("controller_package"),
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "library_sha256": manifest["library_sha256"],
    }


def mpc_catalog() -> tuple[list[dict], dict]:
    """Expose dependency availability separately from unaccepted scenario compatibility."""
    available = True
    reason = None
    build_identity = None
    try:
        config = AuthoritativeMpcConfig.from_dict({})
        roots, assets, _ = config.source_assets()
        with NativeModule(
            config.build_directory,
            "ship_dynamics_node",
            config.parameters()["ship_dynamics_node"],
            {"time_ns": 2_000_000_000_000_000_000, "package_roots": roots, "asset_paths": assets},
            approved_manifest_sha256=MPC_SOURCE_MANIFEST_SHA256,
        ) as module:
            build_identity = _build_identity(module.manifest)
        extraction = json.loads((config.build_directory / "extraction.json").read_text())
        if extraction.get("controller_package") != "gnc/mpc_control":
            raise ValueError("Authoritative MPC build is not bound to the mpc_control extraction lane")
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
        selection = AuthoritativeMpcConfig.from_dict({"environment": enabled})
        identity = {
            "backend_kind": "authoritative_mpc",
            "source_manifest_sha256": MPC_SOURCE_MANIFEST_SHA256,
            "baseline_sha256": hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
            "environment": enabled,
            "bridge_contract": "original-gnc-route-authority.v1",
        }
        entries.append(
            {
                "schema_version": 1,
                "backend_kind": "authoritative_mpc",
                "stack_id": selection.stack_id,
                "display_name": "Authoritative MPC 2026-09-21" + (" · environment ON" if enabled else " · environment OFF"),
                "config_hash": hashlib.sha256(
                    json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "fidelity_profile": "frozen_original_source_port_mpc_controller",
                "supported_tasks": ["TRANSIT"],
                "modules": [
                    {
                        "role": role,
                        "identity": name,
                        "interface_version": "mpc-control-20260728",
                        "acceptance_evidence": "Frozen colleague source extraction; full scenario acceptance separate",
                    }
                    for role, name in [
                        ("plant", "ship_dynamics_node"),
                        ("guidance", "ship_guidance_node"),
                        ("controller", "ship_control_node(mpc_control)"),
                        ("allocation", "thrust_allocation_node"),
                    ]
                ],
                "asset_trust": [
                    {"asset_id": "qiao_gnc_sources_20260920", "trust_level": "source hash pinned; colleague config contract"}
                ],
                "acceptance_level": "EXPERIMENTAL_ORIGINAL_SOURCE",
                "available": available,
                "unavailable_reason": reason,
                "build_identity": build_identity,
                "config": identity,
            }
        )
    preset = {
        "id": "authoritative_mpc",
        "display_name": "Authoritative MPC · 2026-09-21",
        "description": "Native C++ · MPC controller lane · course / route input.",
        "input": "Velocity intent (VO/Fan) / timed trajectory (Mid)",
        "available": available,
        "unavailable_reason": reason,
        "variants": {"off": entries[0]["stack_id"], "on": entries[1]["stack_id"]},
        "environment_description": ENVIRONMENT_DESCRIPTION,
        "note": (
            "Same frozen guidance/allocation/plant chain as Authoritative GNC 2026-09-14; "
            "the controller module is extracted from the frozen colleague mpc_control package in "
            "external-reference mode (integrated MPC guidance disabled). "
            "Planner contracts (velocity intent, timed trajectory) are unchanged. "
            "Closed-loop response qualification is pending for this controller; runs are diagnostic "
            "until a lane-specific measurement exists. "
            "PGD degradation retained. Source equivalence and scenario safety are separate results."
        ),
        "build_identity": build_identity,
        "fields": {
            "Plant": "Original 4DOF · 44.1 × 8 × 2 m",
            "Guidance": "Velocity/course tracking · ILOS/ALOS routes · terminal DP",
            "Controller": "Colleague MPC · Riccati 2-state · allocation-aware limits",
            "Actuation": "Original PGD · actuator dynamics and limits",
        },
    }
    return entries, preset
