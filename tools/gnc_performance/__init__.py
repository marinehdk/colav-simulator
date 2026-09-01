"""Reproducible modular GNC performance characterization harness."""

from .benchmark import BenchmarkConfig, main, run_benchmark, validate_config

__all__ = ["BenchmarkConfig", "main", "run_benchmark", "validate_config"]

__version__ = "1.0"


if __name__ == "__main__":
    raise SystemExit(main())
