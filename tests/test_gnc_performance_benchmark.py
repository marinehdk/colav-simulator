"""Focused contract tests for corrected Issue #54 benchmark harness."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from tools.gnc_performance.benchmark import (
    BenchmarkConfig,
    _percentile,
    config_to_dict,
    payload_sha256,
    run_benchmark,
    validate_config,
)
from tools.gnc_performance.report import render_report


def _small_config(**overrides: object) -> BenchmarkConfig:
    values: dict[str, object] = {
        "ships": (1, 5, 20),
        "harmonics": (1, 5, 20),
        "warmup_s": 0.02,
        "measured_s": 0.04,
        "repeats": 3,
    }
    values.update(overrides)
    return BenchmarkConfig(**values)  # type: ignore[arg-type]


def test_config_is_deterministic_and_hashable() -> None:
    config = _small_config()
    assert config_to_dict(config)["base_hz"] == 50
    assert config_to_dict(config)["rk_stages"] == 4
    assert config.config_hash == _small_config().config_hash


def test_run_benchmark_has_corrected_schema_and_rows() -> None:
    result = run_benchmark(_small_config())
    assert result["schema_version"] == "gnc-performance.v2"
    assert result["claim_ceiling"] == "performance_characterization_and_A2_blocker_evidence_only"
    assert len(result["rows"]) == 9
    assert all(row["stage_count_identity"] for row in result["rows"])
    assert all(row["pooled_rhs_count_identity"] for row in result["rows"])
    assert result["threshold_proposal"]["status"] == "PROPOSED_NOT_APPROVED"
    assert result["threshold_proposal"]["representative_operating_row"] == {"ships": 20, "harmonics": 32}
    assert result["decisions"]["made"] is False


def test_direct_stage_samples_have_four_counts_and_no_synthetic_field() -> None:
    result = run_benchmark(_small_config(ships=(1,), harmonics=(1,)))
    row = result["rows"][0]
    repeat = row["repeats"][0]
    assert repeat["stage_counts"] == {"k1": 2, "k2": 2, "k3": 2, "k4": 2}
    assert len(repeat["stage_samples_ns"]["k1"]) == 2
    assert len(repeat["stage_samples_ns"]["k4"]) == 2
    assert "rhs_latency_ns" not in repeat
    assert "output_digest" not in row
    assert row["output_trajectory_digest"]
    assert row["repeats"][0]["trajectory_vector_count"] == 2
    assert (
        "every measured post-RK4 trajectory state, ordered tick-major then ship-index"
        in row["repeats"][0]["trajectory_digest_scope"]
    )


def test_repeated_digest_is_deterministic() -> None:
    result = run_benchmark(_small_config(ships=(1,), harmonics=(8,)))
    row = result["rows"][0]
    assert row["deterministic_output_trajectory_digest"] is True
    assert row["output_trajectory_digest"]


def test_rtf_semantics_and_variation() -> None:
    row = run_benchmark(_small_config(ships=(5,), harmonics=(1,)))["rows"][0]
    assert set(row["scenario_rtf"]) >= {"min", "median", "max", "cv", "relative_spread"}
    assert row["aggregate_ship_seconds_per_wall_second"] == pytest.approx(row["scenario_rtf"]["median"] * 5)
    assert row["simulated_seconds"] == pytest.approx(0.04)


def test_percentile_linear_interpolation() -> None:
    assert _percentile((1, 2, 3, 4), 0.5) == pytest.approx(2.5)
    assert _percentile((9,), 0.95) == 9
    with pytest.raises(ValueError, match="empty"):
        _percentile((), 0.5)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"wave_mode": "first_order"}, "wave_mode"),
        ({"repeats": 2}, "at least 3"),
        ({"dt_s": 0.1}, "exactly"),
        ({"ships": (0,)}, "positive integers"),
        ({"harmonics": ()}, "positive integers"),
        ({"measured_s": 0.03}, "exact multiple"),
    ],
)
def test_invalid_args_are_rejected(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_config(_small_config(**kwargs))


def test_payload_hash_recomputes_and_file_hash_is_separate() -> None:
    result = run_benchmark(_small_config(ships=(1,), harmonics=(1,)))
    assert result["provenance"]["payload_sha256"] == payload_sha256(result)
    assert "result_sha256" not in result["provenance"]
    file_bytes = json.dumps(result, sort_keys=True, indent=2).encode()
    assert hashlib.sha256(file_bytes).hexdigest() != result["provenance"]["payload_sha256"]


def test_json_round_trip_and_renderer_labels() -> None:
    result = run_benchmark(_small_config(ships=(1,), harmonics=(1,)))
    decoded = json.loads(json.dumps(result, sort_keys=True))
    assert decoded["benchmark"]["constants"]["rhs_evaluations_per_ship_second"] == 200
    assert np.isfinite(decoded["rows"][0]["scenario_rtf"]["median"])
    rendered = render_report(result, "file-sha")
    assert "Scenario RTF" in rendered
    assert "Aggregate ship-s/s" in rendered
    assert "result_file_sha256" in rendered
    assert "payload_sha256" in rendered
    assert "PROPOSED_NOT_APPROVED" in rendered


def test_default_duration_contract_is_full_10_second_run() -> None:
    config = BenchmarkConfig()
    assert config.warmup_s == 2.0
    assert config.measured_s == 10.0
    assert config.repeats == 3
