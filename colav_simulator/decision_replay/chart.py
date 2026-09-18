"""Versioned chart capture projection; retain recorded facts, never derive motion."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

CHART_TRACE_SCHEMA = "colav.decision-replay.v2"
CHART_PROFILE = "colav.chart-replay.v1"
SHIP_FIELDS = (
    "id",
    "mmsi",
    "state",
    "csog_state",
    "turn_rate",
    "active",
    "waypoints",
    "references",
    "sensor_measurements",
    "do_labels",
    "do_generations",
    "do_estimates",
    "do_covariances",
    "do_NISes",
    "historical_actor_truth",
    "historical_actor_dimensions",
)
PLANNER_FIELDS = (
    "schema_version",
    "algorithm_id",
    "solve_id",
    "sim_time",
    "solver_executed",
    "status",
    "feasible",
    "reason",
    "elapsed_ms",
    "horizon_dt_s",
    "selected_command",
    "prediction_render",
)


def chart_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy the source adapter's chart inputs; raw audit remains a separate profile."""
    result = {}
    for name, raw in payload.items():
        ship = {key: raw[key] for key in SHIP_FIELDS if key in raw}
        colav = raw.get("colav") or {}
        original = colav.get("planner") or {}
        planner = {key: original[key] for key in PLANNER_FIELDS if key in original}
        details = original.get("algorithm_details") or {}
        planner["algorithm_details"] = {key: details[key] for key in ("planner_kind", "solve_period_s") if key in details}
        render = original.get("prediction_render") or {}
        if render.get("schema_version") != "colav.mid_mpc.prediction-render@1":
            # Legacy/other algorithms still render through their recorded paths.
            for key in ("predicted_trajectory", "target_predictions"):
                if key in original:
                    planner[key] = original[key]
            planner["algorithm_details"] = details
        threat = original.get("threat_management") or details.get("threat_management") or colav.get("threat_management")
        if threat is not None:
            planner["threat_management"] = threat
        ship["colav"] = {"planner": planner}
        result[name] = ship
    return result


def chart_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep event identity/order and transitions; trim only repeated solve dumps."""
    result = []
    for event in events:
        if event.get("type") != "planner_solved":
            result.append(event)
            continue
        details = event.get("details") or {}
        planner = details.get("planner") or {}
        result.append(
            {
                **event,
                "details": {
                    **{key: value for key, value in details.items() if key != "planner"},
                    "planner": {
                        key: planner[key]
                        for key in (
                            "algorithm_id",
                            "solve_id",
                            "status",
                            "feasible",
                            "reason",
                            "elapsed_ms",
                            "solver_executed",
                        )
                        if key in planner
                    },
                },
            }
        )
    return result


CHART_STORAGE_SCHEMA = "colav.chart-blocks.v1"


def pack_chart_record(record: dict[str, Any], known: set[str], encode: Callable[[Any], bytes]) -> set[str]:
    """Intern only immutable display blocks; definitions travel with their first frame."""
    definitions = {}

    def reference(value: Any) -> dict[str, str]:
        digest = hashlib.sha256(encode(value)).hexdigest()
        if digest not in known:
            definitions[digest] = value
        return {"$chart_block": digest}

    for ship in record["payload"].values():
        planner = ship["colav"]["planner"]
        if "threat_management" in planner:
            planner["threat_management"] = reference(planner["threat_management"])
        if isinstance(planner.get("prediction_render"), dict):
            render = dict(planner["prediction_render"])
            for key in ("ownship", "targets", "history", "planner_l4", "authority", "quality"):
                if render.get(key) is not None:
                    render[key] = reference(render[key])
            planner["prediction_render"] = render
    record["storage_schema"] = CHART_STORAGE_SCHEMA
    record["chart_blocks"] = definitions
    return set(definitions)


class ChartBlockDecoder:
    """Expand recorded references without running any planner or modifying blocks."""

    def __init__(self) -> None:
        self.blocks: dict[str, bytes] = {}

    def decode(self, record: Any) -> Any:
        if not isinstance(record, dict) or "storage_schema" not in record:
            return record
        if record["storage_schema"] != CHART_STORAGE_SCHEMA:
            raise ValueError("unsupported chart storage schema")
        definitions = record.get("chart_blocks", {})
        if not isinstance(definitions, dict):
            raise ValueError("invalid chart block definitions")
        for key, value in definitions.items():
            encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if key in self.blocks and self.blocks[key] != encoded:
                raise ValueError("chart block redefinition")
            self.blocks[key] = encoded

        def expand(value: Any) -> Any:
            if isinstance(value, dict):
                if set(value) == {"$chart_block"}:
                    key = value["$chart_block"]
                    if key not in self.blocks:
                        raise ValueError("missing chart block")
                    return json.loads(self.blocks[key])
                return {key: expand(item) for key, item in value.items()}
            if isinstance(value, list):
                return [expand(item) for item in value]
            return value

        return expand({key: value for key, value in record.items() if key not in {"storage_schema", "chart_blocks"}})
