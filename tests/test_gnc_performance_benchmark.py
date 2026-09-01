"""Focused contract tests for Issue #54 benchmark harness."""

from __future__ import annotations

import json

import numpy as np
import pytest

from tools.gnc_performance.benchmark import (
    BenchmarkConfig,
    _percentile,
    config_to_dict,
    run_benchmark,
    run_repeat,
    validate_config,
)


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


def test_rhs_count_identity_for_required_ship_counts() -> None:
    config = _small_config(harmonics=(1,))
    for ships in (1, 5, 20):
        result = run_repeat(ships, 1, config, repeat=1)
        assert result["rhs_count"] == result["expected_rhs_count"]
        assert result["rhs_count"] == 2 * ships * 4
        assert result["rhs_count_identity"] is True


def test_run_benchmark_has_required_schema_and_rows() -> None:
    result = run_benchmark(_small_config())
    assert result["schema_version"] == "gnc-performance.v1"
    assert result["claim_ceiling"] == "performance_characterization_and_A2_blocker_evidence_only"
    assert len(result["rows"]) == 9
    assert all(row["rhs_count_identity"] for row in result["rows"])
    assert result["threshold_proposal"]["status"] == "PROPOSED_NOT_APPROVED"
    assert result["decisions"]["made"] is False


def test_repeated_digest_is_deterministic() -> None:
    config = _small_config(ships=(1,), harmonics=(8,))
    result = run_benchmark(config)
    row = result["rows"][0]
    assert row["deterministic_output_digest"] is True
    assert row["output_digest"]


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


def test_json_round_trip_is_machine_readable() -> None:
    result = run_benchmark(_small_config(ships=(1,), harmonics=(1,)))
    encoded = json.dumps(result, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["benchmark"]["constants"]["rhs_evaluations_per_ship_second"] == 200
    assert np.isfinite(decoded["rows"][0]["median_rtf_per_ship"])
