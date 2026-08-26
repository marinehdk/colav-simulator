"""Shared deterministic Ship Domain window crossing semantics."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

_DOMAIN_EPSILON = 1.0e-9


@dataclass(frozen=True)
class DomainWindowCrossings:
    """Entry, peak, and exit times derived from one normalized-scale series."""

    entry_time_s: float | None
    peak_time_s: float
    exit_time_s: float | None


def domain_window_crossings(times_s: np.ndarray, domain_scales: np.ndarray) -> DomainWindowCrossings:
    """Interpolate the first strict entry and exit around the scale-one boundary."""
    times = np.asarray(times_s, dtype=float)
    scales = np.asarray(domain_scales, dtype=float)
    if times.ndim != 1 or scales.shape != times.shape or times.size == 0:
        raise ValueError("domain window inputs must be equally sized non-empty vectors")
    if not np.isfinite(times).all() or not np.isfinite(scales).all():
        raise ValueError("domain window inputs must be finite")
    if times[0] < 0.0 or np.any(np.diff(times) <= 0.0) or np.any(scales < 0.0):
        raise ValueError("domain window times must increase and scales must be non-negative")

    entry = _first_entry(times, scales)
    exit_time = _first_exit(times, scales, entry)
    return DomainWindowCrossings(
        entry_time_s=entry,
        peak_time_s=float(times[int(np.argmin(scales))]),
        exit_time_s=exit_time,
    )


def _first_entry(times: np.ndarray, scales: np.ndarray) -> float | None:
    if scales[0] < 1.0 - _DOMAIN_EPSILON:
        return float(times[0])
    for index in range(1, scales.size):
        if scales[index] < 1.0 - _DOMAIN_EPSILON:
            return _crossing_time(times[index - 1], times[index], scales[index - 1], scales[index])
    return None


def _first_exit(times: np.ndarray, scales: np.ndarray, entry: float | None) -> float | None:
    if entry is None:
        return None
    start = max(1, int(np.searchsorted(times, entry, side="left")))
    for index in range(start, scales.size):
        if scales[index] > 1.0 + _DOMAIN_EPSILON:
            return _crossing_time(times[index - 1], times[index], scales[index - 1], scales[index])
    return None


def _crossing_time(t0: float, t1: float, scale0: float, scale1: float) -> float:
    if math.isclose(float(scale1), float(scale0), rel_tol=0.0, abs_tol=1.0e-12):
        return float(t1)
    fraction = (1.0 - float(scale0)) / (float(scale1) - float(scale0))
    return float(t0 + min(max(fraction, 0.0), 1.0) * (t1 - t0))
