"""Deterministic, direct modular GNC benchmark implementation.

This module intentionally measures only EnvironmentField + EnvironmentalLoadModel +
generic 3DOF plant + scheduler-owned RK4. It does not enter Simulator, GUI, legacy
ship, COLAV, or adapter paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

try:
    import psutil
except ImportError:  # pragma: no cover - exercised on minimal environments
    psutil = None

from colav_simulator.modular_gnc.contracts import VesselLoad
from colav_simulator.modular_gnc.environment import AnalyticEnvironmentField
from colav_simulator.modular_gnc.integrators import rk4_step
from colav_simulator.modular_gnc.load_model import EnvironmentalLoadModel
from colav_simulator.modular_gnc.plant import Generic3DOFPlant, Generic3DOFPlantParameters

SCHEMA_VERSION = "gnc-performance.v1"
CLAIM_CEILING = "performance_characterization_and_A2_blocker_evidence_only"
BASE_HZ = 50
RK_STAGES = 4
RHS_PER_SHIP_SECOND = BASE_HZ * RK_STAGES
DEFAULT_HARMONICS = (8, 32, 128)
DEFAULT_SHIPS = (1, 5, 20)
DEFAULT_WARMUP_S = 2.0
DEFAULT_MEASURED_S = 10.0
DEFAULT_REPEATS = 3


@dataclass(frozen=True)
class BenchmarkConfig:
    ships: tuple[int, ...] = DEFAULT_SHIPS
    harmonics: tuple[int, ...] = DEFAULT_HARMONICS
    warmup_s: float = DEFAULT_WARMUP_S
    measured_s: float = DEFAULT_MEASURED_S
    repeats: int = DEFAULT_REPEATS
    dt_s: float = 1.0 / BASE_HZ
    seed: int = 5400
    wave_mode: str = "both"
    cpu_affinity: tuple[int, ...] = ()

    @property
    def warmup_ticks(self) -> int:
        return _whole_ticks(self.warmup_s, self.dt_s, "warmup_s")

    @property
    def measured_ticks(self) -> int:
        return _whole_ticks(self.measured_s, self.dt_s, "measured_s")

    @property
    def config_hash(self) -> str:
        payload = json.dumps(config_to_dict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


def _whole_ticks(seconds: float, dt_s: float, name: str) -> int:
    """Convert an exact duration to a positive integer tick count."""
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
        raise ValueError(f"{name} must be positive")
    ticks = round(float(seconds) / dt_s)
    if ticks <= 0 or not np.isclose(ticks * dt_s, seconds, rtol=0.0, atol=1e-12):
        raise ValueError(f"{name} must be an exact multiple of dt_s={dt_s}")
    return ticks


def config_to_dict(config: BenchmarkConfig) -> dict[str, Any]:
    """Serialize benchmark configuration into canonical JSON-compatible values."""
    return {
        "ships": list(config.ships),
        "harmonics": list(config.harmonics),
        "warmup_s": config.warmup_s,
        "measured_s": config.measured_s,
        "repeats": config.repeats,
        "dt_s": config.dt_s,
        "base_hz": BASE_HZ,
        "rk_stages": RK_STAGES,
        "seed": config.seed,
        "wave_mode": config.wave_mode,
        "cpu_affinity": list(config.cpu_affinity),
    }


def validate_config(config: BenchmarkConfig) -> None:
    """Reject configurations that would violate the fixed benchmark contract."""
    if config.wave_mode != "both":
        raise ValueError("wave_mode must be 'both' for the representative benchmark")
    if not config.ships or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in config.ships):
        raise ValueError("ships must contain positive integers")
    if not config.harmonics or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in config.harmonics):
        raise ValueError("harmonics must contain positive integers")
    if config.repeats < 3:
        raise ValueError("repeats must be at least 3")
    if config.dt_s != 1.0 / BASE_HZ:
        raise ValueError(f"dt_s must be exactly 1/{BASE_HZ} for this benchmark")
    _ = config.warmup_ticks
    _ = config.measured_ticks
    if config.cpu_affinity and any(cpu < 0 for cpu in config.cpu_affinity):
        raise ValueError("cpu_affinity values must be non-negative")


def default_plant_params() -> Generic3DOFPlantParameters:
    """Return representative generic-3DOF parameters from the modular tests."""
    return Generic3DOFPlantParameters(
        mass_kg=1.6e7,
        i_z_kgm2=3.0e10,
        x_g_m=0.0,
        x_dot_u_kg=-5.0e6,
        y_dot_v_kg=-3.5e7,
        n_dot_r_kgm2=-2.0e10,
        y_dot_r_kgm=1.0e6,
        n_dot_v_kgm=1.0e6,
        d_u=5.0e4,
        d_uu=2.0e5,
        d_v=3.0e5,
        d_vv=1.5e6,
        d_r=8.0e7,
        d_rr=2.5e9,
    )


def default_load_params() -> dict[str, Any]:
    """Return representative BOTH-mode wave load parameters."""
    return {
        "length_between_perpendiculars_m": 44.1,
        "beam_m": 8.0,
        "draft_m": 1.55,
        "wind_frontal_area_m2": 50.0,
        "wind_lateral_area_m2": 150.0,
        "wind_z_center_m": 3.0,
        "water_depth_m": 50.0,
        "kg_m": 2.0,
        "gm_t_m": 1.5,
        "enable_wind": False,
        "enable_current": False,
        "wave_mode": "both",
        "wave_first_order_asset_id": "default_inferred_wave_response_v1",
        "wave_mean_drift_asset_id": "default_inferred_diagonal_drift_v1",
    }


def _make_field(harmonics: int, seed: int, dt_s: float) -> AnalyticEnvironmentField:
    """Construct a representative deterministic BOTH-mode wave field."""
    return AnalyticEnvironmentField(
        dt_s=dt_s,
        field_seed=seed,
        wave_significant_height_m=1.5,
        wave_peak_period_s=8.0,
        wave_direction_to_rad=0.4,
        wave_num_components=harmonics,
        wave_directional_spread_rad=0.25,
    )


def _make_load_model() -> EnvironmentalLoadModel:
    """Construct the accepted modular environmental load model."""
    return EnvironmentalLoadModel.from_params(default_load_params())


def _make_ships(count: int, field: AnalyticEnvironmentField, load_model: EnvironmentalLoadModel) -> list[dict[str, Any]]:
    """Construct isolated ship plant states sharing immutable field and load assets."""
    plant = default_plant_params()
    return [
        {
            "plant": Generic3DOFPlant(plant),
            "field": field,
            "load_model": load_model,
            "state": np.array([float(i * 10), float(i * 3), 0.1, 1.5, 0.0, 0.0], dtype=np.float64),
            "control": VesselLoad.zero(),
        }
        for i in range(count)
    ]


def _rss_bytes() -> int:
    """Return process peak resident set size in bytes for the current platform."""
    if sys.platform == "darwin":
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _percentile(values: Iterable[int], q: float) -> float:
    """Compute a linearly interpolated percentile in nanoseconds."""
    vals = sorted(float(v) for v in values)
    if not vals:
        raise ValueError("cannot calculate percentile of empty sequence")
    if len(vals) == 1:
        return vals[0]
    rank = (len(vals) - 1) * q
    lo = int(rank)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (rank - lo)


def _digest_states(states: list[np.ndarray]) -> str:
    """Hash final state vectors using canonical little-endian float64 bytes."""
    digest = hashlib.sha256()
    for state in states:
        digest.update(np.asarray(state, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


def run_repeat(ships: int, harmonics: int, config: BenchmarkConfig, repeat: int) -> dict[str, Any]:
    """Run one warmup and measured repeat for one ships/harmonics matrix row."""
    field = _make_field(harmonics, config.seed + harmonics * 1009, config.dt_s)
    load_model = _make_load_model()
    stacks = _make_ships(ships, field, load_model)
    warmup_ticks = config.warmup_ticks
    measured_ticks = config.measured_ticks
    for tick in range(warmup_ticks):
        for ship in stacks:
            ship["state"] = rk4_step(ship["plant"], tick, config.dt_s, ship["state"], ship["control"], field, load_model)

    rhs_latencies_ns: list[int] = []
    step_latencies_ns: list[int] = []
    final_states: list[np.ndarray] = []
    rss_before = _rss_bytes()
    wall_start = time.perf_counter_ns()
    for offset in range(measured_ticks):
        tick = warmup_ticks + offset
        for ship in stacks:
            state = ship["state"]
            step_start = time.perf_counter_ns()
            next_state = rk4_step(ship["plant"], tick, config.dt_s, state, ship["control"], field, load_model)
            step_elapsed = time.perf_counter_ns() - step_start
            step_latencies_ns.append(step_elapsed)
            rhs_latencies_ns.extend([step_elapsed // RK_STAGES] * RK_STAGES)
            ship["state"] = next_state
            final_states.append(next_state)
    wall_ns = time.perf_counter_ns() - wall_start
    rss_after = _rss_bytes()
    expected_rhs = measured_ticks * ships * RK_STAGES
    actual_rhs = len(rhs_latencies_ns)
    if actual_rhs != expected_rhs:
        raise AssertionError(f"RHS identity failed: actual={actual_rhs}, expected={expected_rhs}")
    simulated_s = measured_ticks * config.dt_s * ships
    # Per-ship simulated seconds drives RTF. Aggregate CPU wall time is reported separately.
    rtf = (measured_ticks * config.dt_s) / (wall_ns / 1e9)
    return {
        "repeat": repeat,
        "ships": ships,
        "harmonics": harmonics,
        "warmup_ticks": warmup_ticks,
        "measured_ticks": measured_ticks,
        "simulated_seconds_per_ship": measured_ticks * config.dt_s,
        "simulated_ship_seconds": simulated_s,
        "wall_seconds": wall_ns / 1e9,
        "rtf_per_ship": rtf,
        "rhs_count": actual_rhs,
        "expected_rhs_count": expected_rhs,
        "rhs_count_identity": actual_rhs == expected_rhs,
        "rhs_latency_ns": {
            "p50": _percentile(rhs_latencies_ns, 0.50),
            "p95": _percentile(rhs_latencies_ns, 0.95),
            "sample_count": len(rhs_latencies_ns),
            "unit": "ns",
            "measurement": ("RK4 step wall time divided by 4; per-stage attribution is estimated, not independently timed"),
        },
        "rk4_step_latency_ns": {
            "p50": _percentile(step_latencies_ns, 0.50),
            "p95": _percentile(step_latencies_ns, 0.95),
            "sample_count": len(step_latencies_ns),
            "unit": "ns",
        },
        "rss_before_bytes": rss_before,
        "rss_after_bytes": rss_after,
        "peak_rss_bytes": max(rss_before, rss_after),
        "delta_rss_bytes": rss_after - rss_before,
        "output_digest": _digest_states(final_states),
    }


def _run_one(config: BenchmarkConfig, ships: int, harmonics: int) -> dict[str, Any]:
    repeats = [run_repeat(ships, harmonics, config, i + 1) for i in range(config.repeats)]
    digests = {r["output_digest"] for r in repeats}
    return {
        "ships": ships,
        "harmonics": harmonics,
        "repeats": repeats,
        "deterministic_output_digest": len(digests) == 1,
        "output_digest": sorted(digests)[0] if len(digests) == 1 else None,
        "median_rtf_per_ship": statistics.median(r["rtf_per_ship"] for r in repeats),
        "median_rhs_latency_ns": {
            "p50": statistics.median(r["rhs_latency_ns"]["p50"] for r in repeats),
            "p95": statistics.median(r["rhs_latency_ns"]["p95"] for r in repeats),
            "unit": "ns",
        },
        "median_rk4_step_latency_ns": {
            "p50": statistics.median(r["rk4_step_latency_ns"]["p50"] for r in repeats),
            "p95": statistics.median(r["rk4_step_latency_ns"]["p95"] for r in repeats),
            "unit": "ns",
        },
        "peak_rss_bytes": max(r["peak_rss_bytes"] for r in repeats),
        "max_delta_rss_bytes": max(r["delta_rss_bytes"] for r in repeats),
        "rhs_count_identity": all(r["rhs_count_identity"] for r in repeats),
    }


def platform_provenance(config: BenchmarkConfig, result_path: Path | None = None) -> dict[str, Any]:
    """Collect platform, dependency, source, and configuration provenance."""
    uv_lock = Path(__file__).resolve().parents[2] / "uv.lock"
    git_head = _command(("git", "rev-parse", "HEAD"))
    dependency_freeze = _command((sys.executable, "-m", "pip", "freeze"))
    dep_hash = hashlib.sha256(dependency_freeze.encode()).hexdigest()
    uv_hash = hashlib.sha256(uv_lock.read_bytes()).hexdigest() if uv_lock.exists() else None
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timezone": time.tzname,
        "os": platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu": platform.processor(),
        "gpu": "not queried; no GPU kernel invoked",
        "memory_bytes": _physical_memory_bytes(),
        "rss_measurement": "resource.RUSAGE_SELF.ru_maxrss; bytes on macOS, KiB converted to bytes on Linux",
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "uv_lock_sha256": uv_hash,
        "commit_head": git_head.strip() or None,
        "dependency_freeze_sha256": dep_hash,
        "dependency_freeze": dependency_freeze.splitlines(),
        "harness_config_hash": config.config_hash,
        "tracked_archive_sha256": os.environ.get("GNC_TRACKED_ARCHIVE_SHA256"),
        "source_archive_note": (
            "Set GNC_TRACKED_ARCHIVE_SHA256 when executed from a staged content-addressed archive on AGX."
        ),
        "result_sha256": _sha256_file(result_path) if result_path and result_path.exists() else None,
        "cpu_affinity": list(config.cpu_affinity),
        "cpu_affinity_status": "uncontrolled" if not config.cpu_affinity else "requested_not_applied_by_harness",
        "compiler": "none; no native code invoked",
    }


def _command(cmd: tuple[str, ...]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
    except OSError:
        return ""


def _physical_memory_bytes() -> int | None:
    """Return physical memory size when psutil is installed."""
    return int(psutil.virtual_memory().total) if psutil is not None else None


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_benchmark(config: BenchmarkConfig) -> dict[str, Any]:
    """Execute all configured matrix rows and return aggregate evidence."""
    validate_config(config)
    rows = [_run_one(config, ships, harmonics) for ships in config.ships for harmonics in config.harmonics]
    scaling: list[dict[str, Any]] = []
    for ships in config.ships:
        baseline = next((r for r in rows if r["ships"] == ships and r["harmonics"] == config.harmonics[0]), None)
        if baseline is None:
            continue
        for row in rows:
            if row["ships"] == ships:
                scaling.append(
                    {
                        "ships": ships,
                        "from_harmonics": config.harmonics[0],
                        "to_harmonics": row["harmonics"],
                        "rhs_p95_ratio": row["median_rhs_latency_ns"]["p95"] / baseline["median_rhs_latency_ns"]["p95"],
                        "rtf_ratio": baseline["median_rtf_per_ship"] / row["median_rtf_per_ship"],
                    }
                )
    return {
        "schema_version": SCHEMA_VERSION,
        "claim_ceiling": CLAIM_CEILING,
        "benchmark": {
            "name": "modular_gnc_environment_load_generic_3dof_rk4",
            "scope": "direct EnvironmentField + EnvironmentalLoadModel + Generic3DOFPlant + rk4_step",
            "config": config_to_dict(config),
            "constants": {
                "base_hz": BASE_HZ,
                "rk_stages": RK_STAGES,
                "rhs_evaluations_per_ship_second": RHS_PER_SHIP_SECOND,
                "rhs_count_identity": "measured_ticks * ships * 4 == rhs_count",
            },
            "plant": "generic_3dof_required",
            "wave_mode": "BOTH",
            "harmonics": list(config.harmonics),
            "warmup_and_measurement": "deterministic warmup followed by measured ticks; no wall-clock in simulation state",
        },
        "rows": rows,
        "harmonic_scaling": scaling,
        "provenance": platform_provenance(config),
        "threshold_proposal": {
            "status": "PROPOSED_NOT_APPROVED",
            "options": [
                "Python GO",
                "approved remediation/vectorization",
                "optional same-contract native adapter",
            ],
            "required_20_ship_representative_row_rtf_floor": None,
            "rhs_p95_budget_relative_to_5ms": {
                "per_ship_serial_budget_ms": 5.0,
                "accounting": (
                    "200 RHS evaluations per ship per simulated second; aggregate multi-ship wall load must also be reviewed"
                ),
                "proposed_budget_ms": None,
            },
            "memory_ceiling_bytes": None,
            "harmonic_scaling_guard": None,
            "note": "Numeric thresholds require later issue approval; absent thresholds are NO-GO for subsequent slices.",
        },
        "decisions": {
            "made": False,
            "a2_parity": "BLOCKED_PENDING_PERFORMANCE_DECISION",
            "issue_55": "BLOCKED",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the benchmark command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ships", type=int, nargs="+", default=list(DEFAULT_SHIPS))
    parser.add_argument("--harmonics", type=int, nargs="+", default=list(DEFAULT_HARMONICS))
    parser.add_argument("--warmup-s", type=float, default=DEFAULT_WARMUP_S)
    parser.add_argument("--measured-s", type=float, default=DEFAULT_MEASURED_S)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--seed", type=int, default=5400)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-affinity", type=int, nargs="*", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI benchmark and write its JSON evidence artifact."""
    args = build_parser().parse_args(argv)
    config = BenchmarkConfig(
        ships=tuple(args.ships),
        harmonics=tuple(args.harmonics),
        warmup_s=args.warmup_s,
        measured_s=args.measured_s,
        repeats=args.repeats,
        seed=args.seed,
        cpu_affinity=tuple(args.cpu_affinity),
    )
    result = run_benchmark(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["provenance"]["result_sha256"] = _sha256_file(args.output)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sha256": _sha256_file(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
