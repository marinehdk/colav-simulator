from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from colav_simulator.core import controllers, models, ship

PINNED_BASELINE_COMMIT = "8968f31b982d48773d08f814439827328bf4b35d"
SCHEMA_VERSION = "gnc-g6-legacy-baseline.v1"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BASELINE = _REPOSITORY_ROOT / "tests" / "fixtures" / "gnc_g6" / "legacy-baseline-v1.json"


class BaselineMismatchError(RuntimeError):
    """Raised when current legacy characterization differs from a baseline."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(_REPOSITORY_ROOT), *args],
        check=True,
        capture_output=True,
    ).stdout


def _git_file(commit: str, path: str) -> bytes:
    return _git_bytes("show", f"{commit}:{path}")


def _tree_hash(commit: str, path: str | None = None) -> str:
    args = ["ls-tree", "-r", commit]
    if path is not None:
        args.extend(["--", path])
    return _sha256_bytes(_git_bytes(*args))


def _test_identity() -> dict[str, Any]:
    names = _git_bytes("ls-tree", "-r", "--name-only", PINNED_BASELINE_COMMIT, "--", "tests").decode().splitlines()
    test_files = sorted(name for name in names if name.endswith(".py"))
    return {
        "tree_sha256": _tree_hash(PINNED_BASELINE_COMMIT, "tests"),
        "file_count": len(test_files),
        "files_sha256": _sha256_bytes("\n".join(test_files).encode()),
        "known_preexisting_failures": [
            {
                "nodeid": (
                    "tests/test_historical_ais_scene_guard.py::"
                    "test_existing_verified_exact_tuples_remain_unchanged_and_independent"
                ),
                "reason": "extra mid_mpc_ipopt Historical AIS experimental tuple",
            },
            {
                "nodeid": "tests/test_playback_speed.py::test_playback_ui_uses_server_state_and_frame_interpolation",
                "reason": "moved VO key assertion",
            },
            {
                "nodeid": "tests/test_playback_speed.py::test_ownship_uses_fcb45_top_view_sprite",
                "reason": "moved sprite code",
            },
        ],
        "baseline_full_pytest": {"passed": 815, "skipped": 8, "failed": 3},
    }


def _dependency_identity() -> dict[str, str]:
    return {
        "pyproject_sha256": _sha256_bytes(_git_file(PINNED_BASELINE_COMMIT, "pyproject.toml")),
        "uv_lock_sha256": _sha256_bytes(_git_file(PINNED_BASELINE_COMMIT, "uv.lock")),
    }


def _scenario_config() -> dict[str, Any]:
    return {
        "scenario_id": "legacy_kinematic_direct_reference_v1",
        "dt_s": 0.2,
        "ticks": 12,
        "seed": 42042,
        "model": "KinematicCSOG",
        "controller": "PassThroughCS",
        "initial_csog": [100.0, -50.0, 4.0, 0.25],
        "reference_schedule": [
            {"tick": 0, "course_rad": 0.35, "speed_mps": 4.5},
            {"tick": 5, "course_rad": -0.1, "speed_mps": 3.75},
        ],
    }


def _run_reference_scenario(config: dict[str, Any]) -> list[str]:
    model = models.KinematicCSOG(
        models.KinematicCSOGParams(
            length=10.0,
            width=3.0,
            draft=0.5,
            T_chi=3.0,
            T_U=5.0,
            r_max=0.4,
            U_min=0.0,
            U_max=15.0,
        )
    )
    controller = controllers.PassThroughCS()
    vessel = ship.Ship(mmsi=42042, identifier=0, model=model, controller=controller)
    vessel.set_initial_state(np.asarray(config["initial_csog"], dtype=np.float64))
    schedule = {item["tick"]: item for item in config["reference_schedule"]}
    references = np.zeros(9, dtype=np.float64)
    tick_hashes = []
    for tick in range(config["ticks"]):
        if tick in schedule:
            references[2] = schedule[tick]["course_rad"]
            references[3] = schedule[tick]["speed_mps"]
            vessel.set_references(references)
        state, inputs, applied_references = vessel.forward(float(config["dt_s"]))
        trace = {
            "tick": tick,
            "state": np.asarray(state, dtype=np.float64).tolist(),
            "inputs": np.asarray(inputs, dtype=np.float64).tolist(),
            "references": np.asarray(applied_references, dtype=np.float64).tolist(),
        }
        encoded = json.dumps(trace, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        tick_hashes.append(_sha256_bytes(encoded))
    return tick_hashes


def _without_expected_hash(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "expected_output_sha256"}


def _expected_output_hash(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        _without_expected_hash(document),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return _sha256_bytes(encoded)


def current_baseline() -> dict[str, Any]:
    """Build current characterization against pinned legacy source identity."""
    scenario = _scenario_config()
    document = {
        "schema_version": SCHEMA_VERSION,
        "pinned_commit": PINNED_BASELINE_COMMIT,
        "main_checkout_dirty_work_included": False,
        "acceptance_claim": "G6 legacy regression characterization; A1 only",
        "source_sha256": _tree_hash(PINNED_BASELINE_COMMIT),
        "test_suite": _test_identity(),
        "dependencies": _dependency_identity(),
        "reference_scenarios": [
            {
                "scenario_id": scenario["scenario_id"],
                "config_sha256": _sha256_bytes(
                    json.dumps(scenario, sort_keys=True, separators=(",", ":")).encode()
                ),
                "test_sha256": _sha256_file(Path(__file__).resolve()),
                "seed": scenario["seed"],
                "per_tick_sha256": _run_reference_scenario(scenario),
            }
        ],
    }
    document["expected_output_sha256"] = _expected_output_hash(document)
    return document


def capture_baseline(output: Path) -> dict[str, Any]:
    """Write reproducible pinned-commit legacy characterization."""
    baseline = current_baseline()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return baseline


def compare_baseline(path: Path) -> None:
    """Compare current legacy characterization with content-addressed fixture."""
    expected = json.loads(path.read_text(encoding="utf-8"))
    if expected.get("expected_output_sha256") != _expected_output_hash(expected):
        raise BaselineMismatchError("baseline expected_output_sha256 is invalid")
    actual = current_baseline()
    if actual != expected:
        differing = sorted(key for key in set(actual) | set(expected) if actual.get(key) != expected.get(key))
        raise BaselineMismatchError(f"legacy G6 baseline mismatch: {', '.join(differing)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture or compare pinned legacy G6 characterization")
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--output", type=Path, default=_DEFAULT_BASELINE)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--baseline", type=Path, default=_DEFAULT_BASELINE)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run baseline capture or comparison CLI."""
    args = _parser().parse_args(argv)
    if args.command == "capture":
        capture_baseline(args.output)
    else:
        compare_baseline(args.baseline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
