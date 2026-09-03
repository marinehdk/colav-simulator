"""Deterministic local G8 four-arm attribution binding (Issue #56, AC4).

Strictly local and deterministic: four execution arms (legacy; modular
legacy-equivalent; new plant + pass-through; new plant + marine_pid) consume the
identical local geometry and reference schedule. Attribution decisions are
content-addressed (source/config/trace hashes); decisions based only on arm
labels are rejected.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np

from colav_simulator.modular_gnc.configuration import REGISTRY_V1, normalize_ship_modules
from colav_simulator.modular_gnc.contracts import CommandInput, ControlTask, DirectReference, NavigationState
from colav_simulator.modular_gnc.factory import legacy_equivalent_profile
from colav_simulator.modular_gnc.stack import ModularShipStack

G8_ARM_LABELS: tuple[str, ...] = (
    "legacy",
    "modular_legacy_equivalent",
    "modular_new_plant_passthrough",
    "modular_new_plant_marine_pid",
)

_DT_S = 0.2
_TICKS = 12
_SEED = 42042
_INITIAL_STATE = (100.0, -50.0, 4.0, 0.25)
_REFERENCE_SCHEDULE = {0: (0.35, 4.5), 5: (-0.1, 3.75)}


class AttributionError(ValueError):
    """Raised when an attribution record or decision lacks content-addressed identity."""


def _sha256_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_identity_hash(name: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or not all(c in "0123456789abcdef" for c in value):
        raise AttributionError(f"{name} must be content-addressed SHA-256 hex, got {value!r}")
    return value


@dataclass(frozen=True)
class ArmIdentity:
    """Content-addressed execution identity of one G8 arm; the label is descriptive only."""

    label: str
    geometry_hash: str
    input_hash: str
    source_hash: str
    config_hash: str
    trace_hash: str

    def __post_init__(self) -> None:
        """Validate label presence and content-addressed hashes."""
        if not isinstance(self.label, str) or not self.label:
            raise AttributionError("arm label must be a non-empty string")
        for name in ("geometry_hash", "input_hash", "source_hash", "config_hash", "trace_hash"):
            object.__setattr__(self, name, _validate_identity_hash(name, getattr(self, name)))


@dataclass(frozen=True)
class FourArmBinding:
    """Shared-input binding of the four canonical G8 arms."""

    geometry_hash: str
    input_hash: str
    arms: Mapping[str, ArmIdentity]

    def __post_init__(self) -> None:
        """Enforce the exact canonical arm set bound to the shared inputs."""
        unknown = set(self.arms) - set(G8_ARM_LABELS)
        if unknown:
            raise AttributionError(f"unknown G8 arm labels: {sorted(unknown)} (canonical: {list(G8_ARM_LABELS)})")
        missing = set(G8_ARM_LABELS) - set(self.arms)
        if missing:
            raise AttributionError(f"missing G8 arm labels: {sorted(missing)}")
        for label, arm in self.arms.items():
            if arm.geometry_hash != self.geometry_hash or arm.input_hash != self.input_hash:
                raise AttributionError(f"arm {label} is not bound to the shared geometry/input hashes")
        object.__setattr__(self, "arms", MappingProxyType(dict(self.arms)))

    def attributes_to(self, observed: ArmIdentity, claimed: ArmIdentity) -> bool:
        """Decide attribution strictly from content hashes; labels are never consulted."""
        return all(
            getattr(observed, field) == getattr(claimed, field)
            for field in ("geometry_hash", "input_hash", "source_hash", "config_hash", "trace_hash")
        )

    def attributes_to_label_only(self, observed_label: str, claimed_label: str) -> None:
        """Reject label-only attribution attempts (G8: labels never decide attribution)."""
        raise AttributionError(
            "label-only attribution is rejected (G8): arm labels "
            f"{observed_label!r}/{claimed_label!r} carry no content-addressed identity; "
            "use FourArmBinding.attributes_to with matching source/config/trace hashes"
        )


def _reference_schedule_payload() -> list[list[float]]:
    return [[float(tick), course, speed] for tick, (course, speed) in sorted(_REFERENCE_SCHEDULE.items())]


def _shared_hashes() -> tuple[str, str]:
    geometry_hash = _sha256_payload({"initial_state": list(_INITIAL_STATE), "frame": "NE/body-forward-starboard-down"})
    input_hash = _sha256_payload({"dt_s": _DT_S, "ticks": _TICKS, "reference_schedule": _reference_schedule_payload()})
    return geometry_hash, input_hash


def _tick_digest(payload: Mapping[str, Any]) -> str:
    return _sha256_payload(payload)


def _trace_hash(tick_hashes: Sequence[str]) -> str:
    return _sha256_payload(list(tick_hashes))


def _run_legacy_arm(geometry_hash: str, input_hash: str) -> ArmIdentity:
    """Run the legacy arm: Ship + KinematicCSOG + PassThroughCS on the shared inputs."""
    from colav_simulator.core import controllers, models, ship  # noqa: PLC0415

    plant_params = {
        "length": 10.0,
        "width": 3.0,
        "draft": 0.5,
        "T_chi": 3.0,
        "T_U": 5.0,
        "r_max": 0.4,
        "U_min": 0.0,
        "U_max": 15.0,
    }
    model = models.KinematicCSOG(models.KinematicCSOGParams(**plant_params))
    controller = controllers.PassThroughCS()
    vessel = ship.Ship(mmsi=_SEED, identifier=0, model=model, controller=controller)
    vessel.set_initial_state(np.asarray(_INITIAL_STATE, dtype=np.float64))
    references = np.zeros(9, dtype=np.float64)
    tick_hashes = []
    for tick in range(_TICKS):
        if tick in _REFERENCE_SCHEDULE:
            references[2], references[3] = _REFERENCE_SCHEDULE[tick]
            vessel.set_references(references)
        state, inputs, applied_references = vessel.forward(_DT_S)
        tick_hashes.append(
            _tick_digest(
                {
                    "tick": tick,
                    "state": np.asarray(state, dtype=np.float64).tolist(),
                    "inputs": np.asarray(inputs, dtype=np.float64).tolist(),
                    "references": np.asarray(applied_references, dtype=np.float64).tolist(),
                }
            )
        )
    source_hash = _sha256_payload({"ship": "Ship", "plant": "KinematicCSOG", "controller": "PassThroughCS"})
    config_hash = _sha256_payload({"plant": plant_params, "dt_s": _DT_S, "ticks": _TICKS, "seed": _SEED})
    return ArmIdentity(
        label="legacy",
        geometry_hash=geometry_hash,
        input_hash=input_hash,
        source_hash=source_hash,
        config_hash=config_hash,
        trace_hash=_trace_hash(tick_hashes),
    )


def _modular_arm_config(arm: str) -> dict[str, Any]:
    if arm == "modular_legacy_equivalent":
        return legacy_equivalent_profile()
    config: dict[str, Any] = {
        "preset": "legacy_equivalent",
        "modules": {
            "plant": {
                "identity": "generic_3dof_plant",
                "parameters": {"mass_kg": 1.6e7, "i_z_kgm2": 3.0e10},
            },
            "guidance": {"identity": "pass_through_guidance", "parameters": {}},
        },
    }
    if arm == "modular_new_plant_passthrough":
        config["modules"]["controller"] = {"identity": "pass_through_controller", "parameters": {}}
    elif arm == "modular_new_plant_marine_pid":
        config["modules"]["controller"] = {
            "identity": "marine_pid",
            "parameters": {
                "kp": [1000.0, 500.0, 2000.0],
                "ki": [100.0, 50.0, 200.0],
                "kd": [200.0, 100.0, 400.0],
                "tau_d": [0.1, 0.1, 0.1],
                "antiwindup_gain": [1.0, 1.0, 1.0],
                "min_output": [-10000.0, -5000.0, -20000.0],
                "max_output": [10000.0, 5000.0, 20000.0],
                "feedforward_gain": [0.0, 0.0, 0.0],
                "allow_ideal_passthrough": True,
            },
        }
    else:
        raise AttributionError(f"unknown modular G8 arm: {arm}")
    return config


def _run_modular_arm(arm: str, geometry_hash: str, input_hash: str) -> ArmIdentity:
    """Run one modular arm on the shared inputs through the contracts-only facade."""
    config = _modular_arm_config(arm)
    normalized = normalize_ship_modules(config)
    stack = ModularShipStack.from_config(normalized)
    stack.reset(NavigationState(*_INITIAL_STATE, 0.0, 0.0), seed=_SEED)
    tick_hashes = []
    for tick in range(_TICKS):
        values = np.zeros(9, dtype=np.float64)
        if tick in _REFERENCE_SCHEDULE:
            values[2], values[3] = _REFERENCE_SCHEDULE[tick]
        command = CommandInput.direct(tick, DirectReference(values, latched_tick=tick, task=ControlTask.TRANSIT))
        output = stack.step(command, dt_s=_DT_S)
        if output.failure is not None:
            raise AttributionError(f"G8 arm {arm} failed at tick {tick}: {output.failure.message}")
        tick_hashes.append(
            _tick_digest(
                {
                    "tick": tick,
                    "state": output.plant.values.tolist(),
                    "applied_reference": (
                        output.applied_reference.values.tolist() if output.applied_reference is not None else None
                    ),
                }
            )
        )
    source_hash = _sha256_payload(
        {
            role: {
                "identity": selection.identity,
                "implementation_version": REGISTRY_V1[selection.identity].implementation_version,
                "interface_version": REGISTRY_V1[selection.identity].interface_version,
            }
            for role, selection in normalized.modules.items()
        }
    )
    return ArmIdentity(
        label=arm,
        geometry_hash=geometry_hash,
        input_hash=input_hash,
        source_hash=source_hash,
        config_hash=normalized.config_hash,
        trace_hash=_trace_hash(tick_hashes),
    )


def run_g8_four_arm_binding() -> FourArmBinding:
    """Run the four canonical G8 arms locally on identical deterministic inputs."""
    geometry_hash, input_hash = _shared_hashes()
    arms = {
        "legacy": _run_legacy_arm(geometry_hash, input_hash),
        "modular_legacy_equivalent": _run_modular_arm(
            "modular_legacy_equivalent", geometry_hash, input_hash
        ),
        "modular_new_plant_passthrough": _run_modular_arm(
            "modular_new_plant_passthrough", geometry_hash, input_hash
        ),
        "modular_new_plant_marine_pid": _run_modular_arm(
            "modular_new_plant_marine_pid", geometry_hash, input_hash
        ),
    }
    return FourArmBinding(geometry_hash=geometry_hash, input_hash=input_hash, arms=arms)
