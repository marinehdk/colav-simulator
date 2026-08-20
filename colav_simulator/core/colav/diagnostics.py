"""Shared execution diagnostics for collision-avoidance planners."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np


class PlanStatus(StrEnum):
    """Normalized outcome of one planner invocation."""

    SUCCESS = "SUCCESS"
    TIMEOUT_FEASIBLE = "TIMEOUT_FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    INVALID_INPUT = "INVALID_INPUT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


class FailureSource(StrEnum):
    """Owner of an invalid input or planner failure."""

    SCENARIO = "SCENARIO"
    ADAPTER = "ADAPTER"
    ALGORITHM = "ALGORITHM"


@dataclass
class PlanDiagnostics:
    """Planner-neutral diagnostic payload stored with every run."""

    status: PlanStatus = PlanStatus.SUCCESS
    elapsed_ms: float = 0.0
    iterations: int | None = None
    feasible: bool | None = True
    objective: float | None = None
    reason: str | None = None
    requested_algorithm: str | None = None
    executed_algorithm: str | None = None
    fallback_used: bool = False
    algorithm_descriptor: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["status"] = self.status.value
        return output


@dataclass
class PlannerTrace:
    """Versioned observable state for one planner invocation or hold-last step."""

    algorithm_id: str
    solve_id: int
    sim_time: float
    solver_executed: bool
    status: PlanStatus = PlanStatus.SUCCESS
    feasible: bool | None = True
    reason: str | None = None
    elapsed_ms: float = 0.0
    iterations: int | None = None
    objective: float | None = None
    predicted_trajectory: np.ndarray = field(default_factory=lambda: np.zeros((9, 1)))
    horizon_dt_s: float | None = None
    selected_command: dict[str, Any] = field(default_factory=dict)
    target_predictions: list[dict[str, Any]] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    algorithm_details: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] | None = None
    evidence_timeline: dict[str, Any] | None = None
    prediction_render: dict[str, Any] | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        trajectory = validate_plan(self.predicted_trajectory)
        output = {
            "schema_version": self.schema_version,
            "algorithm_id": self.algorithm_id,
            "solve_id": self.solve_id,
            "sim_time": self.sim_time,
            "solver_executed": self.solver_executed,
            "status": self.status.value,
            "feasible": self.feasible,
            "reason": self.reason,
            "elapsed_ms": self.elapsed_ms,
            "iterations": self.iterations,
            "objective": self.objective,
            "predicted_trajectory": trajectory.tolist(),
            "horizon_dt_s": self.horizon_dt_s,
            "selected_command": _json_value(self.selected_command),
            "target_predictions": _json_value(self.target_predictions),
            "constraints": _json_value(self.constraints),
            "algorithm_details": _json_value(self.algorithm_details),
        }
        if self.schema_version != "1.0" or self.evidence is not None:
            output["evidence"] = _json_value(self.evidence)
            output["evidence_timeline"] = _json_value(self.evidence_timeline)
            output["prediction_render"] = _json_value(self.prediction_render)
        return output


class ColavExecutionError(RuntimeError):
    """Planner failure carrying a normalized diagnostic status."""

    def __init__(
        self,
        status: PlanStatus,
        message: str,
        *,
        source: FailureSource | None = None,
        details: dict[str, Any] | None = None,
        evidence: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.source = source
        self.details = details or {}
        self.evidence = evidence


def validate_plan(plan: np.ndarray) -> np.ndarray:
    """Validate the public ICOLAV 9xN trajectory contract."""
    array = np.asarray(plan, dtype=float)
    if array.ndim != 2 or array.shape[0] != 9 or array.shape[1] < 1:
        raise ColavExecutionError(
            PlanStatus.NUMERICAL_FAILURE,
            f"ICOLAV plan must have shape (9, N>=1), got {array.shape}",
        )
    if not np.isfinite(array).all():
        raise ColavExecutionError(PlanStatus.NUMERICAL_FAILURE, "ICOLAV plan contains non-finite values")
    return array


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
