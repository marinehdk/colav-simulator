"""Capture and compare the pinned legacy G6 regression baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
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


def _execution_commit(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise BaselineMismatchError("execution identity is not a pinned git checkout") from exc


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
        "baseline_full_pytest_observation": {
            "status": "externally_observed_not_reproduced_by_capture_cli",
            "passed": 815,
            "skipped": 8,
            "failed": 3,
        },
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


def _run_reference_scenario(config: dict[str, Any]) -> dict[str, Any]:
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
    execution_chain = {
        "ship_type": type(vessel).__name__,
        "model_type": type(vessel._model).__name__,
        "controller_type": type(vessel._controller).__name__,
        "modular_path_selected": False,
    }
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
    invalid_state_error = None
    try:
        vessel.set_initial_state(np.zeros(3))
    except ValueError as exc:
        invalid_state_error = {"type": type(exc).__name__, "message": str(exc)}
    return {
        "per_tick_sha256": tick_hashes,
        "execution_chain": execution_chain,
        "error_semantics": {"invalid_initial_state": invalid_state_error},
    }


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


def current_baseline(*, execution_identity: dict[str, str] | None = None) -> dict[str, Any]:
    """Build characterization from currently imported code for comparison only."""
    scenario = _scenario_config()
    scenario_evidence = _run_reference_scenario(scenario)
    document = {
        "schema_version": SCHEMA_VERSION,
        "pinned_commit": PINNED_BASELINE_COMMIT,
        "execution_identity": execution_identity or {"commit": PINNED_BASELINE_COMMIT, "isolation": "git_archive"},
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
                "seed": scenario["seed"],
                **scenario_evidence,
            }
        ],
    }
    document["expected_output_sha256"] = _expected_output_hash(document)
    return document


def _capture_from_pinned_archive(output: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gnc-g6-pinned-") as directory:
        archive_root = Path(directory)
        archive = subprocess.Popen(
            ["git", "-C", str(_REPOSITORY_ROOT), "archive", PINNED_BASELINE_COMMIT],
            stdout=subprocess.PIPE,
        )
        if archive.stdout is None:
            raise BaselineMismatchError("failed to open pinned git archive stream")
        extracted = subprocess.run(
            ["tar", "-x", "-C", str(archive_root)],
            stdin=archive.stdout,
            capture_output=True,
            check=False,
        )
        archive.stdout.close()
        archive_status = archive.wait()
        if archive_status != 0 or extracted.returncode != 0:
            raise BaselineMismatchError("failed to create isolated pinned git archive")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(archive_root)
        script = """
import hashlib
import json
import sys
import numpy as np
from colav_simulator.core import controllers, models, ship

scenario = json.loads(sys.argv[1])
model = models.KinematicCSOG(models.KinematicCSOGParams(
    length=10.0, width=3.0, draft=0.5, T_chi=3.0, T_U=5.0,
    r_max=0.4, U_min=0.0, U_max=15.0,
))
controller = controllers.PassThroughCS()
vessel = ship.Ship(mmsi=42042, identifier=0, model=model, controller=controller)
vessel.set_initial_state(np.asarray(scenario["initial_csog"], dtype=np.float64))
schedule = {item["tick"]: item for item in scenario["reference_schedule"]}
references = np.zeros(9, dtype=np.float64)
tick_hashes = []
for tick in range(scenario["ticks"]):
    if tick in schedule:
        references[2] = schedule[tick]["course_rad"]
        references[3] = schedule[tick]["speed_mps"]
        vessel.set_references(references)
    state, inputs, applied_references = vessel.forward(float(scenario["dt_s"]))
    trace = {
        "tick": tick,
        "state": np.asarray(state, dtype=np.float64).tolist(),
        "inputs": np.asarray(inputs, dtype=np.float64).tolist(),
        "references": np.asarray(applied_references, dtype=np.float64).tolist(),
    }
    encoded = json.dumps(trace, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    tick_hashes.append(hashlib.sha256(encoded).hexdigest())
invalid_state_error = None
try:
    vessel.set_initial_state(np.zeros(3))
except ValueError as exc:
    invalid_state_error = {"type": type(exc).__name__, "message": str(exc)}
evidence = {
    "per_tick_sha256": tick_hashes,
    "execution_chain": {
        "ship_type": type(vessel).__name__,
        "model_type": type(vessel._model).__name__,
        "controller_type": type(vessel._controller).__name__,
        "modular_path_selected": False,
    },
    "error_semantics": {"invalid_initial_state": invalid_state_error},
}
print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
"""
        scenario = _scenario_config()
        result = subprocess.run(
            [sys.executable, "-c", script, json.dumps(scenario, sort_keys=True)],
            cwd=archive_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise BaselineMismatchError(f"isolated pinned capture failed: {result.stderr.strip()}")
    evidence = json.loads(result.stdout)
    document = current_baseline(execution_identity={"commit": PINNED_BASELINE_COMMIT, "isolation": "git_archive"})
    document["reference_scenarios"] = [
        {
            "scenario_id": scenario["scenario_id"],
            "config_sha256": _sha256_bytes(json.dumps(scenario, sort_keys=True, separators=(",", ":")).encode()),
            "seed": scenario["seed"],
            **evidence,
        }
    ]
    document["expected_output_sha256"] = _expected_output_hash(document)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def capture_baseline(
    output: Path,
    *,
    execution_root: Path | None = None,
) -> dict[str, Any]:
    """Write characterization only from isolated pinned code or verified pinned identity."""
    if execution_root is None:
        return _capture_from_pinned_archive(output)
    root = execution_root.resolve()
    observed_commit = _execution_commit(root)
    if observed_commit != PINNED_BASELINE_COMMIT:
        raise BaselineMismatchError(
            f"execution identity mismatch: expected {PINNED_BASELINE_COMMIT}, observed {observed_commit}"
        )
    if Path(__file__).resolve().parents[1] != root:
        raise BaselineMismatchError("execution identity root does not match imported pinned code")
    baseline = current_baseline(execution_identity={"commit": observed_commit, "isolation": "git_archive"})
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
    capture.add_argument("--execution-root", type=Path)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--baseline", type=Path, default=_DEFAULT_BASELINE)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run baseline capture or comparison CLI."""
    args = _parser().parse_args(argv)
    if args.command == "capture":
        capture_baseline(args.output, execution_root=args.execution_root)
    else:
        compare_baseline(args.baseline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
