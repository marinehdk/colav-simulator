"""Reproducible direct modular GNC performance characterization harness.

The measured path is deliberately limited to EnvironmentField, EnvironmentalLoadModel,
Generic3DOFPlant, and scheduler-owned RK4. Each matrix row/repeat runs in a fresh
worker process. The parent process monitors worker current RSS without entering the
worker timing loop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
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

SCHEMA_VERSION = "gnc-performance.v2"
CLAIM_CEILING = "performance_characterization_and_A2_blocker_evidence_only"
BASE_HZ = 50
RK_STAGES = 4
RHS_PER_SHIP_SECOND = BASE_HZ * RK_STAGES
DEFAULT_HARMONICS = (8, 32, 128)
DEFAULT_SHIPS = (1, 5, 20)
DEFAULT_WARMUP_S = 2.0
DEFAULT_MEASURED_S = 10.0
DEFAULT_REPEATS = 3
STAGE_NAMES = {1: "k1", 2: "k2", 3: "k3", 4: "k4"}


@dataclass(frozen=True)
class BenchmarkConfig:
    """Fixed benchmark configuration and representative matrix."""

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
        """Return exact deterministic warmup tick count."""
        return _whole_ticks(self.warmup_s, self.dt_s, "warmup_s")

    @property
    def measured_ticks(self) -> int:
        """Return exact measured tick count."""
        return _whole_ticks(self.measured_s, self.dt_s, "measured_s")

    @property
    def config_hash(self) -> str:
        """Hash canonical benchmark configuration."""
        return _sha256_json(config_to_dict(self))


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
    """Reject configurations that violate the fixed benchmark contract."""
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
    """Return representative generic-3DOF parameters from modular characterization tests."""
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
    """Return representative BOTH-mode environmental-load parameters."""
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
    """Construct isolated ship states sharing immutable field and load assets."""
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


def _percentile(values: Iterable[int | float], q: float) -> float:
    """Compute a linearly interpolated percentile."""
    vals = sorted(float(v) for v in values)
    if not vals:
        raise ValueError("cannot calculate percentile of empty sequence")
    if len(vals) == 1:
        return vals[0]
    rank = (len(vals) - 1) * q
    lo = int(rank)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (rank - lo)


def _sha256_json(value: Any) -> str:
    """Hash canonical JSON bytes."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def payload_sha256(result: dict[str, Any]) -> str:
    """Hash result payload after nulling the self-referential payload hash field."""
    canonical = json.loads(json.dumps(result))
    canonical.setdefault("provenance", {})["payload_sha256"] = None
    return _sha256_json(canonical)


def _digest_states(states: list[np.ndarray]) -> str:
    """Hash every measured post-RK4 state in tick-major, then ship-index order."""
    digest = hashlib.sha256()
    for state in states:
        digest.update(np.asarray(state, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    """Hash a file with SHA-256."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_capture(argv: tuple[str, ...], *, required: bool = True) -> dict[str, Any]:
    """Run provenance command and fail closed on execution or nonzero status."""
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        if required:
            raise RuntimeError(f"required command unavailable: {argv!r}: {exc}") from exc
        return {"argv": list(argv), "returncode": None, "stdout": "", "stderr": str(exc)}
    result = {
        "argv": list(argv),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if required and completed.returncode != 0:
        raise RuntimeError(f"required command failed: {result!r}")
    return result


def _dependency_capture() -> dict[str, Any]:
    """Capture a non-empty dependency freeze using pip or verified uv fallback."""
    pip_argv = (sys.executable, "-m", "pip", "freeze")
    try:
        result = _run_capture(pip_argv)
        if not result["stdout"].strip():
            raise RuntimeError("dependency freeze command returned empty stdout")
        return result
    except RuntimeError as pip_error:
        uv_path = shutil.which("uv")
        if uv_path is None:
            raise RuntimeError(f"pip freeze failed and verified uv executable not found: {pip_error}") from pip_error
        uv_result = _run_capture((uv_path, "pip", "freeze", "--python", sys.executable))
        if not uv_result["stdout"].strip():
            raise RuntimeError("uv pip freeze returned empty stdout") from pip_error
        return uv_result


def _git_head() -> str | None:
    """Read current Git HEAD with strict command status."""
    result = _run_capture(("git", "rev-parse", "HEAD"))
    value = result["stdout"].strip()
    return value or None


def _current_process_rss() -> int | None:
    """Return current worker RSS for READY protocol diagnostics."""
    if psutil is not None:
        try:
            return int(psutil.Process().memory_info().rss)
        except (psutil.Error, OSError):
            return None
    status = Path(f"/proc/{os.getpid()}/status")
    if status.exists():
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return None


def _invocation_argv() -> list[str]:
    """Return replayable module-form invocation from Python's original argv."""
    raw = list(getattr(sys, "orig_argv", []))
    try:
        module_index = raw.index("tools.gnc_performance")
        if module_index <= 0 or raw[module_index - 1] != "-m":
            raise ValueError
        return raw
    except (ValueError, IndexError):
        return [sys.executable, "-m", "tools.gnc_performance", *sys.argv[1:]]


def _worker_result(
    ships: int,
    harmonics: int,
    config: BenchmarkConfig,
    repeat: int,
    output_path: Path,
    control_path: Path,
) -> None:
    """Execute one isolated worker repeat and write direct stage samples."""
    field = _make_field(harmonics, config.seed + harmonics * 1009, config.dt_s)
    load_model = _make_load_model()
    stacks = _make_ships(ships, field, load_model)
    stage_samples: dict[str, list[int]] = {name: [] for name in STAGE_NAMES.values()}
    warmup_ticks = config.warmup_ticks
    measured_ticks = config.measured_ticks

    for tick in range(warmup_ticks):
        for ship in stacks:
            ship["state"] = rk4_step(ship["plant"], tick, config.dt_s, ship["state"], ship["control"], field, load_model)

    ready_payload = {"event": "READY_FOR_MEASUREMENT", "pid": os.getpid(), "rss_bytes": _current_process_rss()}
    control_path.write_text(json.dumps(ready_payload), encoding="utf-8")
    start_deadline = time.monotonic() + 30.0
    while True:
        if control_path.exists() and "START_MEASUREMENT" in control_path.read_text(encoding="utf-8"):
            break
        if time.monotonic() > start_deadline:
            raise TimeoutError("timed out waiting for START_MEASUREMENT")
        time.sleep(0.001)

    step_samples: list[int] = []
    final_states: list[np.ndarray] = []
    wall_start = time.perf_counter_ns()
    for offset in range(measured_ticks):
        tick = warmup_ticks + offset
        for ship in stacks:

            def record_stage(stage_number: int, elapsed_ns: int) -> None:
                stage_samples[STAGE_NAMES[stage_number]].append(int(elapsed_ns))

            step_start = time.perf_counter_ns()
            next_state = rk4_step(
                ship["plant"],
                tick,
                config.dt_s,
                ship["state"],
                ship["control"],
                field,
                load_model,
                stage_timing_sink=record_stage,
            )
            step_samples.append(time.perf_counter_ns() - step_start)
            ship["state"] = next_state
            final_states.append(next_state)
    wall_ns = time.perf_counter_ns() - wall_start
    expected_stage_count = measured_ticks * ships
    expected_rhs_count = expected_stage_count * RK_STAGES
    actual_stage_counts = {name: len(values) for name, values in stage_samples.items()}
    if any(count != expected_stage_count for count in actual_stage_counts.values()):
        raise AssertionError(f"stage count identity failed: {actual_stage_counts} != {expected_stage_count}")
    result = {
        "repeat": repeat,
        "ships": ships,
        "harmonics": harmonics,
        "stage_sample_digests": {
            "per_stage_sha256": {name: _sha256_json(values) for name, values in stage_samples.items()},
            "step_sha256": _sha256_json(step_samples),
        },
        "warmup_ticks": warmup_ticks,
        "measured_ticks": measured_ticks,
        "simulated_seconds": measured_ticks * config.dt_s,
        "wall_seconds": wall_ns / 1e9,
        "stage_samples_ns": stage_samples,
        "direct_stage_measurement": (
            "Each sample is directly timed with perf_counter_ns around environment query, load model, and plant RHS."
        ),
        "step_samples_ns": step_samples,
        "stage_counts": actual_stage_counts,
        "pooled_rhs_count": sum(actual_stage_counts.values()),
        "expected_stage_count_per_stage": expected_stage_count,
        "expected_pooled_rhs_count": expected_rhs_count,
        "stage_count_identity": all(count == expected_stage_count for count in actual_stage_counts.values()),
        "pooled_rhs_count_identity": sum(actual_stage_counts.values()) == expected_rhs_count,
        "output_trajectory_digest": _digest_states(final_states),
        "trajectory_digest_scope": (
            "every measured post-RK4 trajectory state, ordered tick-major then ship-index, "
            "encoded as float64 little-endian vectors"
        ),
        "trajectory_vector_count": measured_ticks * ships,
        "process_lifetime_peak_rss_bytes": _process_lifetime_peak_rss_bytes(),
    }
    output_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    control_path.write_text(
        json.dumps({"event": "DONE", "pid": os.getpid(), "rss_bytes": _current_process_rss()}), encoding="utf-8"
    )


def _process_lifetime_peak_rss_bytes() -> int:
    """Return child process lifetime peak RSS, separately from parent current RSS."""
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _current_rss(pid: int) -> tuple[int | None, str]:
    """Read worker current RSS using psutil or Linux procfs fallback."""
    if psutil is not None:
        try:
            return int(psutil.Process(pid).memory_info().rss), "psutil.Process.memory_info().rss"
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass
    proc_status = Path(f"/proc/{pid}/status")
    if proc_status.exists():
        for line in proc_status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1]) * 1024, "/proc/<pid>/status VmRSS"
    return None, "unavailable"


def _run_isolated_repeat(ships: int, harmonics: int, config: BenchmarkConfig, repeat: int) -> dict[str, Any]:
    """Run one row/repeat in a fresh worker while parent monitors current RSS."""
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="gnc-performance-worker-") as temp_dir:
        output_path = Path(temp_dir) / "worker.json"
        control_path = Path(temp_dir) / "control.json"
        command = [
            sys.executable,
            "-m",
            "tools.gnc_performance.benchmark",
            "--worker",
            "--worker-output",
            str(output_path),
            "--worker-control",
            str(control_path),
            "--worker-ships",
            str(ships),
            "--worker-harmonics",
            str(harmonics),
            "--worker-warmup-s",
            str(config.warmup_s),
            "--worker-measured-s",
            str(config.measured_s),
            "--worker-repeats",
            str(config.repeats),
            "--worker-seed",
            str(config.seed),
            "--worker-repeat",
            str(repeat),
        ]
        process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        startup_rss_samples: list[int] = []
        measured_rss_samples: list[int] = []
        methods: set[str] = set()
        ready_seen = False
        unavailable_since = time.monotonic()
        baseline_rss: int | None = None
        while process.poll() is None:
            current, method = _current_rss(process.pid)
            if current is not None:
                methods.add(method)
                unavailable_since = time.monotonic()
            elif time.monotonic() - unavailable_since > 5.0:
                process.terminate()
                process.wait(timeout=5)
                raise RuntimeError("no valid current-RSS monitoring method available")
            if not ready_seen and control_path.exists():
                ready = json.loads(control_path.read_text(encoding="utf-8"))
                if ready.get("event") == "READY_FOR_MEASUREMENT":
                    ready_seen = True
                    baseline_rss = current
                    if baseline_rss is None:
                        raise RuntimeError("no valid current-RSS baseline at READY_FOR_MEASUREMENT")
                    startup_rss_samples.append(baseline_rss)
                    control_path.write_text(json.dumps({"event": "START_MEASUREMENT"}), encoding="utf-8")
                    measured_rss_samples.append(baseline_rss)
            elif ready_seen and current is not None:
                measured_rss_samples.append(current)
            time.sleep(0.01)
        if not ready_seen or baseline_rss is None:
            raise RuntimeError("worker exited before READY_FOR_MEASUREMENT baseline")
        if not measured_rss_samples:
            raise RuntimeError("worker exited before measured-interval RSS sample")
        if process.returncode is not None and process.returncode != 0:
            measured_rss_samples.append(baseline_rss)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"isolated worker failed with code {process.returncode}: {stderr or stdout}")
        if not output_path.exists():
            raise RuntimeError("isolated worker completed without a result payload")
        result = json.loads(output_path.read_text(encoding="utf-8"))
        result.update(
            {
                "startup_peak_current_rss_bytes": max(startup_rss_samples),
                "baseline_current_rss_bytes": baseline_rss,
                "peak_current_rss_bytes": max(measured_rss_samples),
                "delta_current_rss_bytes": max(measured_rss_samples) - baseline_rss,
                "rss_monitor_methods": sorted(methods),
                "rss_monitor_sample_count": len(measured_rss_samples),
                "worker_command": command,
                "rss_protocol": (
                    "READY_FOR_MEASUREMENT -> parent baseline capture -> START_MEASUREMENT -> measured samples -> DONE"
                ),
            }
        )
        return result


def _latency_summary(samples: Iterable[int | float]) -> dict[str, Any]:
    """Summarize direct timing samples with explicit units and count."""
    values = list(samples)
    return {
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "sample_count": len(values),
        "unit": "ns",
    }


def _aggregate_row(config: BenchmarkConfig, ships: int, harmonics: int) -> dict[str, Any]:
    """Execute and aggregate one matrix row across isolated repeats."""
    repeats = [_run_isolated_repeat(ships, harmonics, config, index + 1) for index in range(config.repeats)]
    expected_stage_count = config.measured_ticks * ships
    expected_rhs_count = expected_stage_count * RK_STAGES
    for item in repeats:
        item["scenario_rtf"] = item["simulated_seconds"] / item["wall_seconds"]
        item["aggregate_ship_seconds_per_wall_second"] = ships * item["simulated_seconds"] / item["wall_seconds"]
        item["stage_latency_ns"] = {name: _latency_summary(item["stage_samples_ns"][name]) for name in STAGE_NAMES.values()}
        pooled_samples = [sample for name in STAGE_NAMES.values() for sample in item["stage_samples_ns"][name]]
        item["pooled_rhs_latency_ns"] = _latency_summary(pooled_samples)
        item["rk4_step_latency_ns"] = _latency_summary(item["step_samples_ns"])
        item["stage_count_identity"] = item["stage_counts"] == dict.fromkeys(STAGE_NAMES.values(), expected_stage_count)
        item["pooled_rhs_count_identity"] = item["pooled_rhs_count"] == expected_rhs_count

    pooled_stage_samples = {
        name: [sample for item in repeats for sample in item["stage_samples_ns"][name]] for name in STAGE_NAMES.values()
    }
    pooled_rhs_samples = [sample for name in STAGE_NAMES.values() for sample in pooled_stage_samples[name]]
    pooled_step_samples = [sample for item in repeats for sample in item["step_samples_ns"]]
    rtf_values = [item["scenario_rtf"] for item in repeats]
    digest_values = {item["output_trajectory_digest"] for item in repeats}
    return {
        "ships": ships,
        "harmonics": harmonics,
        "measured_ticks": config.measured_ticks,
        "duration_contract": {
            "warmup_seconds": config.warmup_s,
            "measured_seconds": config.measured_s,
            "repeats": config.repeats,
        },
        "simulated_seconds": config.measured_ticks * config.dt_s,
        "expected_stage_count_per_stage": expected_stage_count,
        "expected_pooled_rhs_count": expected_rhs_count,
        "repeats": repeats,
        "scenario_rtf": {
            "min": min(rtf_values),
            "median": statistics.median(rtf_values),
            "max": max(rtf_values),
            "cv": statistics.pstdev(rtf_values) / statistics.mean(rtf_values) if len(rtf_values) > 1 else 0.0,
            "relative_spread": (max(rtf_values) - min(rtf_values)) / statistics.median(rtf_values),
            "unit": "scenario_simulated_seconds/wall_seconds",
        },
        "aggregate_ship_seconds_per_wall_second": statistics.median(
            item["aggregate_ship_seconds_per_wall_second"] for item in repeats
        ),
        "direct_stage_latency_ns_pooled_across_repeats": {
            name: _latency_summary(pooled_stage_samples[name]) for name in STAGE_NAMES.values()
        },
        "direct_pooled_rhs_latency_ns_pooled_across_repeats": _latency_summary(pooled_rhs_samples),
        "rk4_step_latency_ns_pooled_across_repeats": _latency_summary(pooled_step_samples),
        "direct_pooled_rhs_latency_ns_median_of_repeat_p95": statistics.median(
            item["pooled_rhs_latency_ns"]["p95"] for item in repeats
        ),
        "rk4_step_latency_ns_median_of_repeat_p95": statistics.median(
            item["rk4_step_latency_ns"]["p95"] for item in repeats
        ),
        "peak_current_rss_bytes": max(item["peak_current_rss_bytes"] for item in repeats),
        "max_delta_current_rss_bytes": max(item["delta_current_rss_bytes"] for item in repeats),
        "startup_peak_current_rss_bytes": max(item["startup_peak_current_rss_bytes"] for item in repeats),
        "rss_monitor_methods": sorted({method for item in repeats for method in item["rss_monitor_methods"]}),
        "rss_monitor_sample_counts": [item["rss_monitor_sample_count"] for item in repeats],
        "stage_count_identity": all(item["stage_count_identity"] for item in repeats),
        "pooled_rhs_count_identity": all(item["pooled_rhs_count_identity"] for item in repeats),
        "deterministic_output_trajectory_digest": len(digest_values) == 1,
        "output_trajectory_digest": sorted(digest_values)[0] if len(digest_values) == 1 else None,
    }


def _input_hash(config: BenchmarkConfig) -> str:
    """Hash all representative field, load, plant, and scheduler inputs."""
    return _sha256_json(
        {
            "config": config_to_dict(config),
            "plant": asdict(default_plant_params()),
            "load_model": default_load_params(),
            "field": {
                "significant_height_m": 1.5,
                "peak_period_s": 8.0,
                "direction_to_rad": 0.4,
                "directional_spread_rad": 0.25,
            },
        }
    )


def _source_hashes() -> dict[str, str]:
    """Hash harness and production surfaces used by the direct benchmark."""
    root = Path(__file__).resolve().parents[2]
    paths = {
        "harness_benchmark": Path(__file__),
        "harness_report": root / "tools/gnc_performance/report.py",
        "integrator": root / "colav_simulator/modular_gnc/integrators.py",
        "environment": root / "colav_simulator/modular_gnc/environment.py",
        "load_model": root / "colav_simulator/modular_gnc/load_model.py",
        "plant": root / "colav_simulator/modular_gnc/plant.py",
    }
    return {name: _sha256_file(path) for name, path in paths.items() if path.exists()}


def _git_head() -> str | None:
    """Read current Git HEAD when available."""
    value = _run_capture(("git", "rev-parse", "HEAD"))["stdout"].strip()
    return value or None


def platform_provenance(
    config: BenchmarkConfig,
    result_path: Path | None = None,
    execution_source: dict[str, Any] | None = None,
    execution_command: list[str] | None = None,
) -> dict[str, Any]:
    """Collect platform, dependency, source, and configuration provenance."""
    uv_lock = Path(__file__).resolve().parents[2] / "uv.lock"
    dependency_capture = _dependency_capture()
    dependency_freeze = dependency_capture["stdout"]
    provenance = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timezone": time.tzname,
        "os": platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu": platform.processor(),
        "gpu": "not queried; no GPU kernel invoked",
        "memory_bytes": _physical_memory_bytes(),
        "rss_measurement": "parent current RSS via psutil or Linux /proc VmRSS; worker ru_maxrss is separate",
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "uv_lock_sha256": _sha256_file(uv_lock) if uv_lock.exists() else None,
        "dependency_freeze_sha256": hashlib.sha256(dependency_freeze.encode()).hexdigest(),
        "dependency_freeze": dependency_freeze.splitlines(),
        "dependency_capture": dependency_capture,
        "harness_config_hash": config.config_hash,
        "input_hash": _input_hash(config),
        "source_hashes": _source_hashes(),
        "execution_source_commit": _git_head(),
        "execution_source_archive_sha256": None,
        "execution_source_manifest_sha256": None,
        "execution_source_manifest_path": None,
        "execution_source_dirty": None,
        "execution_command": execution_command,
        "execution_command_shell": shlex.join(execution_command) if execution_command else None,
        "result_file_sha256": _sha256_file(result_path) if result_path and result_path.exists() else None,
        "payload_sha256": None,
        "cpu_affinity": list(config.cpu_affinity),
        "cpu_affinity_status": "uncontrolled" if not config.cpu_affinity else "requested_not_applied_by_harness",
        "compiler": "none; no native code invoked",
    }
    if execution_source:
        provenance.update(execution_source)
    return provenance


def _physical_memory_bytes() -> int | None:
    """Return physical memory size when psutil is installed."""
    return int(psutil.virtual_memory().total) if psutil is not None else None


def _threshold_proposal(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate fixed candidate thresholds without making a decision."""
    representative = next((row for row in rows if row["ships"] == 20 and row["harmonics"] == 32), None)
    row_20_8 = next((row for row in rows if row["ships"] == 20 and row["harmonics"] == 8), None)
    row_20_128 = next((row for row in rows if row["ships"] == 20 and row["harmonics"] == 128), None)
    if not representative or not row_20_8 or not row_20_128:
        return {
            "status": "PROPOSED_NOT_APPROVED",
            "representative_operating_row": {"ships": 20, "harmonics": 32},
            "scenario_rtf_floor": 1.00,
            "direct_pooled_rhs_p95_ceiling_ms": 0.25,
            "per_ship_reference_rhs_budget_ms": 5.0,
            "multi_ship_accounting": "20 ships × 200 RHS evaluations/ship/s = 4000 RHS evaluations/s serial aggregate",
            "peak_current_rss_ceiling_mib": 128.0,
            "per_row_delta_current_rss_ceiling_mib": 64.0,
            "harmonic_p95_ratio_guards": {"8_to_32": 2.00, "8_to_128": 5.25},
            "stress_row": {"ships": 20, "harmonics": 128, "scenario_rtf_floor": 0.25},
            "checks": {},
            "decision_options": ["Python GO", "remediation-vectorization", "same-contract native adapter"],
            "note": "Candidate thresholds require the complete representative matrix for evaluation.",
        }
    rtf = representative["scenario_rtf"]["median"]
    rhs_p95_ms = representative["direct_pooled_rhs_latency_ns_pooled_across_repeats"]["p95"] / 1e6
    peak_rss_mib = representative["peak_current_rss_bytes"] / (1024 * 1024)
    delta_mib = representative["max_delta_current_rss_bytes"] / (1024 * 1024)
    ratio_32 = (
        representative["direct_pooled_rhs_latency_ns_pooled_across_repeats"]["p95"]
        / row_20_8["direct_pooled_rhs_latency_ns_pooled_across_repeats"]["p95"]
    )
    ratio_128 = (
        row_20_128["direct_pooled_rhs_latency_ns_pooled_across_repeats"]["p95"]
        / row_20_8["direct_pooled_rhs_latency_ns_pooled_across_repeats"]["p95"]
    )
    checks = {
        "representative_scenario_rtf_floor": {"observed": rtf, "limit": 1.00, "pass": rtf >= 1.00},
        "representative_direct_pooled_rhs_p95_ms": {"observed": rhs_p95_ms, "limit": 0.25, "pass": rhs_p95_ms <= 0.25},
        "representative_peak_current_rss_mib": {"observed": peak_rss_mib, "limit": 128.0, "pass": peak_rss_mib <= 128.0},
        "representative_delta_current_rss_mib": {"observed": delta_mib, "limit": 64.0, "pass": delta_mib <= 64.0},
        "20_ship_8_to_32_rhs_p95_ratio": {"observed": ratio_32, "limit": 2.00, "pass": ratio_32 <= 2.00},
        "20_ship_8_to_128_rhs_p95_ratio": {"observed": ratio_128, "limit": 5.25, "pass": ratio_128 <= 5.25},
        "stress_20_ship_128_scenario_rtf_floor": {
            "observed": row_20_128["scenario_rtf"]["median"],
            "limit": 0.25,
            "pass": row_20_128["scenario_rtf"]["median"] >= 0.25,
        },
    }
    return {
        "status": "PROPOSED_NOT_APPROVED",
        "representative_operating_row": {"ships": 20, "harmonics": 32},
        "scenario_rtf_floor": 1.00,
        "direct_pooled_rhs_p95_ceiling_ms": 0.25,
        "per_ship_reference_rhs_budget_ms": 5.0,
        "multi_ship_accounting": "20 ships × 200 RHS evaluations/ship/s = 4000 RHS evaluations/s serial aggregate",
        "peak_current_rss_ceiling_mib": 128.0,
        "per_row_delta_current_rss_ceiling_mib": 64.0,
        "harmonic_p95_ratio_guards": {"8_to_32": 2.00, "8_to_128": 5.25},
        "stress_row": {"ships": 20, "harmonics": 128, "scenario_rtf_floor": 0.25},
        "checks": checks,
        "decision_options": ["Python GO", "remediation-vectorization", "same-contract native adapter"],
        "note": "These are candidate numbers for issue-owner approval, not an approval or GO/NO-GO decision.",
    }


def _manifest_execution_source(path: Path | None, commit: str | None, archive_sha: str | None) -> dict[str, Any] | None:
    """Load and validate an externally staged source manifest."""
    if path is None:
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected_commit = manifest.get("execution_source_commit")
    expected_archive = manifest.get("archive_sha256")
    if commit != expected_commit or archive_sha != expected_archive or manifest.get("clean_status") is not True:
        raise ValueError("source provenance arguments do not match clean source manifest")
    return {
        "execution_source_commit": expected_commit,
        "execution_source_archive_sha256": expected_archive,
        "execution_source_manifest_sha256": _sha256_file(path),
        "execution_source_manifest_path": str(path),
        "execution_source_dirty": False,
    }


def run_benchmark(
    config: BenchmarkConfig,
    execution_source: dict[str, Any] | None = None,
    execution_command: list[str] | None = None,
) -> dict[str, Any]:
    """Execute all configured matrix rows and return aggregate evidence."""
    validate_config(config)
    rows = [_aggregate_row(config, ships, harmonics) for ships in config.ships for harmonics in config.harmonics]
    scaling: list[dict[str, Any]] = []
    for ships in config.ships:
        baseline = next(row for row in rows if row["ships"] == ships and row["harmonics"] == config.harmonics[0])
        for row in rows:
            if row["ships"] == ships:
                scaling.append(
                    {
                        "ships": ships,
                        "from_harmonics": config.harmonics[0],
                        "to_harmonics": row["harmonics"],
                        "direct_pooled_rhs_p95_ratio": (
                            row["direct_pooled_rhs_latency_ns_pooled_across_repeats"]["p95"]
                            / baseline["direct_pooled_rhs_latency_ns_pooled_across_repeats"]["p95"]
                        ),
                        "scenario_rtf_ratio": baseline["scenario_rtf"]["median"] / row["scenario_rtf"]["median"],
                    }
                )
    result = {
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
                "rhs_count_identity": "measured_ticks * ships * 4 == pooled_rhs_count",
                "stage_count_identity": "measured_ticks * ships == each k1/k2/k3/k4 count",
            },
            "plant": "generic_3dof_required",
            "wave_mode": "BOTH",
            "harmonics": list(config.harmonics),
            "warmup_and_measurement": (
                "deterministic 2.0s warmup and 10.0s measured by default; no wall-clock in simulation state"
            ),
            "rtf_definition": "scenario_rtf = common-axis simulated_seconds / wall_seconds",
            "aggregate_definition": (
                "aggregate_ship_seconds_per_wall_second = ships * scenario simulated_seconds / wall_seconds"
            ),
            "direct_timing_definition": (
                "each k1/k2/k3/k4 callback times stage-specific environment query + load model + "
                "plant RHS using perf_counter_ns"
            ),
        },
        "rows": rows,
        "harmonic_scaling": scaling,
        "provenance": platform_provenance(config, execution_source=execution_source, execution_command=execution_command),
        "threshold_proposal": _threshold_proposal(rows),
        "traceability": {
            "authoritative_ra03": {
                "path": "docs/superpowers/specs/2026-08-28-agx-l45-gnc-integration-design.md",
                "section": "Review Amendments (2026-08-31, binding), RA-03",
                "quote": (
                    "Performance checkpoint is mandatory immediately after the environment+plant slice; "
                    "record real-time factor, per-RHS and per-stage p50/p95, and wave-harmonic-count "
                    "scaling for at least 1/5/20 ships."
                ),
            },
            "binding_metrics": ["TS-26", "TS-27", "TS-28", "TS-29", "G2", "G3", "A2 blocker"],
        },
        "decisions": {
            "made": False,
            "a2_parity": "BLOCKED_PENDING_PERFORMANCE_DECISION",
            "issue_55": "BLOCKED",
        },
    }
    result["provenance"]["payload_sha256"] = payload_sha256(result)
    return result


def _parser() -> argparse.ArgumentParser:
    """Build CLI parser for parent and isolated worker modes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ships", type=int, nargs="+", default=list(DEFAULT_SHIPS))
    parser.add_argument("--harmonics", type=int, nargs="+", default=list(DEFAULT_HARMONICS))
    parser.add_argument("--warmup-s", type=float, default=DEFAULT_WARMUP_S)
    parser.add_argument("--measured-s", type=float, default=DEFAULT_MEASURED_S)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--seed", type=int, default=5400)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--source-archive-sha256")
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-output", type=Path)
    parser.add_argument("--worker-control", type=Path)
    parser.add_argument("--worker-ships", type=int)
    parser.add_argument("--worker-harmonics", type=int)
    parser.add_argument("--worker-warmup-s", type=float)
    parser.add_argument("--worker-measured-s", type=float)
    parser.add_argument("--worker-repeats", type=int)
    parser.add_argument("--worker-seed", type=int)
    parser.add_argument("--worker-repeat", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run parent benchmark or one internal isolated worker."""
    args = _parser().parse_args(argv)
    if args.worker:
        if (
            args.worker_output is None
            or args.worker_control is None
            or args.worker_ships is None
            or args.worker_harmonics is None
        ):
            raise ValueError("worker mode requires output, control, ships, and harmonics")
        worker_config = BenchmarkConfig(
            ships=(args.worker_ships,),
            harmonics=(args.worker_harmonics,),
            warmup_s=args.worker_warmup_s,
            measured_s=args.worker_measured_s,
            repeats=args.worker_repeats,
            seed=args.worker_seed,
        )
        _worker_result(
            args.worker_ships,
            args.worker_harmonics,
            worker_config,
            args.worker_repeat,
            args.worker_output,
            args.worker_control,
        )
        return 0

    if args.output is None:
        raise ValueError("--output is required")
    config = BenchmarkConfig(
        ships=tuple(args.ships),
        harmonics=tuple(args.harmonics),
        warmup_s=args.warmup_s,
        measured_s=args.measured_s,
        repeats=args.repeats,
        seed=args.seed,
    )
    execution_source = _manifest_execution_source(args.source_manifest, args.source_commit, args.source_archive_sha256)
    result = run_benchmark(config, execution_source=execution_source, execution_command=_invocation_argv())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "file_sha256": _sha256_file(args.output),
                "payload_sha256": result["provenance"]["payload_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
