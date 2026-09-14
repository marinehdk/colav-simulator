"""Product identity for the independent original-source GNC backend."""

from __future__ import annotations

import hashlib
import json

from colav_simulator.original_gnc.configuration import BASELINE, SOURCE_MANIFEST_SHA256, OriginalGncConfig
from colav_simulator.original_gnc.native import NativeModule

ENVIRONMENT_DESCRIPTION = (
    "Original models · wind U10 6 m/s from 45° · current 0.3 m/s from 90° · waves Hs 0.5 m / Tz 6 s from 90°"
)


def _build_identity(manifest: dict) -> dict:
    """Expose the loaded native build lane without changing stack semantics."""
    proposal_rows = (manifest.get("colleague_proposal") or {}).get("proposals") or []
    proposal_ids = [
        item.get("id") if isinstance(item, dict) else item
        for item in proposal_rows
        if (item.get("id") if isinstance(item, dict) else item)
    ]
    return {
        "execution_lane": "candidate" if proposal_ids else "baseline",
        "candidate": "colleague_proposal" if proposal_ids else None,
        "proposal_ids": proposal_ids,
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "library_sha256": manifest["library_sha256"],
    }


def _build_note(identity: dict | None) -> str:
    """Render build provenance in the existing Original preset note."""
    if identity is None:
        return "Loaded native build identity is unavailable until the approved Original GNC build is installed."
    lane = identity["execution_lane"]
    candidate = (
        f"candidate {identity['candidate']} ({', '.join(identity['proposal_ids'])})"
        if identity["candidate"]
        else "baseline"
    )
    qualification = (
        "Baseline fidelity evidence does not automatically cover this candidate; "
        "scenario safety is separate and Original GNC acceptance remains diagnostic."
        if identity["execution_lane"] == "candidate"
        else "Scenario safety is separate and Original GNC acceptance remains diagnostic."
    )
    return (
        f"Loaded execution {lane}: {candidate}; native library SHA-256 {identity['library_sha256']}; "
        f"approved source manifest SHA-256 {identity['source_manifest_sha256']}. {qualification}"
    )


def original_catalog() -> tuple[list[dict], dict]:
    """Expose dependency availability separately from unaccepted scenario compatibility."""
    available = True
    reason = None
    build_identity = None
    try:
        config = OriginalGncConfig.from_dict({})
        roots, assets, _ = config.source_assets()
        with NativeModule(
            config.build_directory,
            "ship_dynamics_node",
            config.parameters()["ship_dynamics_node"],
            {"time_ns": 2_000_000_000_000_000_000, "package_roots": roots, "asset_paths": assets},
        ) as module:
            build_identity = _build_identity(module.manifest)
        extraction = json.loads((config.build_directory / "extraction.json").read_text())
        if (
            not {"navigation_mode_observer_node", "operational_risk_observer_node", "operator_command_interpreter"}
            <= extraction.get("python_observers", {}).keys()
        ):
            raise ValueError("Original observation modules are not built; rebuild the source backend")
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        available = False
        reason = str(error)
    preset_description = "Authoritative GNC · ordinary/emergency speed policy · independent C++ backend"
    if build_identity and build_identity["execution_lane"] == "candidate":
        preset_description = (
            "Original GNC candidate · "
            + ", ".join(build_identity["proposal_ids"])
            + " · independent local C++ backend"
        )
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
                "display_name": "Authoritative GNC 2026-09-14" + (" · environment ON" if enabled else " · environment OFF"),
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
                "build_identity": build_identity,
                "config": identity,
            }
        )
    preset = {
        "id": "original_gnc",
        "display_name": "Authoritative GNC · 2026-09-14",
        "description": preset_description,
        "input": "Velocity intent (VO/Fan) / path (Mid)",
        "available": available,
        "unavailable_reason": reason,
        "variants": {"off": entries[0]["stack_id"], "on": entries[1]["stack_id"]},
        "environment_description": ENVIRONMENT_DESCRIPTION,
        "note": (
            "VO/Fan velocity intents require a valid parent route, mode and unexpired lease. "
            "Mid path updates retain original route guards, including 500 m ordinary lookahead. "
            "PGD degradation retained. Source equivalence and scenario safety are separate results. "
            + _build_note(build_identity)
        ),
        "build_identity": build_identity,
        "fields": {
            "Plant": "Original 4DOF · 44.1 × 8 × 2 m",
            "Guidance": "Velocity/course tracking · ILOS/ALOS routes · terminal DP",
            "Controller": "Original PID/SMC and source mode logic",
            "Actuation": "Original PGD · actuator dynamics and limits",
        },
    }
    return entries, preset
