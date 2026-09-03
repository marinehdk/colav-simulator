"""Reproducible modular GNC performance characterization harness."""

from .benchmark import BenchmarkConfig, main, payload_sha256, run_benchmark, validate_config

__all__ = ["BenchmarkConfig", "main", "payload_sha256", "run_benchmark", "validate_config"]

__version__ = "1.0"


if __name__ == "__main__":
    raise SystemExit(main())
