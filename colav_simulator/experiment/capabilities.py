"""Versioned rule, scenario, algorithm, and tracker capability catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus

CAPABILITY_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Capability:
    """Declared readiness and compatibility for one selectable integration."""

    readiness_grade: str
    supported_rules: tuple[str, ...]
    supported_scenarios: tuple[str, ...]
    supported_obstacles: tuple[str, ...]
    known_failure: str | None = None
    latest_evidence: dict[str, Any] | None = None


RULES: dict[str, dict[str, Any]] = {
    "rule13": {
        "label": "Rule 13-OT",
        "encounter_types": ["OT_ing", "OT_en"],
        "readiness_grade": "G1",
        "default_scenario": "overtaking",
    },
    "rule14": {
        "label": "Rule 14-HO",
        "encounter_types": ["HO"],
        "readiness_grade": "G3",
        "default_scenario": "head_on",
    },
    "rule15": {
        "label": "Rule 15-CS",
        "encounter_types": ["CR_GW", "CR_SO"],
        "readiness_grade": "G1",
        "default_scenario": "crossing_give_way",
    },
    "multiship": {
        "label": "Multi-ship",
        "encounter_types": ["MS"],
        "readiness_grade": "G1",
        "default_scenario": "paper_ccta2023_multiship",
    },
    "planning": {
        "label": "Static ENC planning",
        "encounter_types": ["SS"],
        "readiness_grade": "G1",
        "default_scenario": "rrt_test",
    },
}

SCENARIOS: dict[str, Capability] = {
    "head_on": Capability(
        readiness_grade="G3",
        supported_rules=("rule14",),
        supported_scenarios=("head_on",),
        supported_obstacles=("dynamic", "enc"),
        latest_evidence={
            "seed": 0,
            "tracker_ids": ["god", "kf"],
            "termination_policy": "collision terminates the nominal Web baseline",
            "nominal_minimum_distance_m": 7.43,
            "vo_minimum_distance_m": {"god": 43.36, "kf": 43.70},
            "sbmpc_minimum_distance_m": {"god": 94.17, "kf": 91.81},
        },
    ),
    "aalesund_random1": Capability(
        readiness_grade="G2",
        supported_rules=("rule14",),
        supported_scenarios=("aalesund_random1",),
        supported_obstacles=("dynamic", "enc"),
        known_failure="Natural clearance does not reliably exercise every COLAV algorithm.",
    ),
    "paper_ccta2023_head_on": Capability(
        readiness_grade="G2",
        supported_rules=("rule14",),
        supported_scenarios=("paper_ccta2023_head_on",),
        supported_obstacles=("dynamic", "enc"),
        known_failure="Functional paper reconstruction; numerical reproduction is not confirmed.",
    ),
    "paper_ccta2023_multiship": Capability(
        readiness_grade="G1",
        supported_rules=("multiship",),
        supported_scenarios=("paper_ccta2023_multiship",),
        supported_obstacles=("dynamic", "enc"),
        known_failure="Only short external-integration smoke evidence is available.",
    ),
    "rrt_test": Capability(
        readiness_grade="G0",
        supported_rules=("planning",),
        supported_scenarios=("rrt_test",),
        supported_obstacles=("static", "enc"),
        known_failure="Scenario preparation fails with an empty safe-sea Polygon.",
    ),
}

ALGORITHMS: dict[str, Capability] = {
    "nominal": Capability(
        readiness_grade="G2",
        supported_rules=("rule14",),
        supported_scenarios=("head_on",),
        supported_obstacles=("none",),
        latest_evidence={
            "scenario_id": "head_on",
            "seed": 0,
            "collision": {"god": True, "kf": True},
        },
    ),
    "vo": Capability(
        readiness_grade="G3",
        supported_rules=("rule14",),
        supported_scenarios=("head_on",),
        supported_obstacles=("dynamic",),
        latest_evidence={
            "scenario_id": "head_on",
            "seed": 0,
            "minimum_distance_m": {"god": 43.36, "kf": 43.70},
        },
    ),
    "sbmpc": Capability(
        readiness_grade="G3",
        supported_rules=("rule14",),
        supported_scenarios=("head_on",),
        supported_obstacles=("dynamic",),
        latest_evidence={
            "scenario_id": "head_on",
            "seed": 0,
            "minimum_distance_m": {"god": 94.17, "kf": 91.81},
        },
    ),
    "psbmpc": Capability(
        readiness_grade="G1",
        supported_rules=("rule14", "multiship"),
        supported_scenarios=("head_on", "paper_ccta2023_multiship"),
        supported_obstacles=("dynamic", "static", "enc"),
        known_failure="500 s run aborts in Eigen Block.h:126; native process isolation is not complete.",
    ),
    "rrt": Capability(
        readiness_grade="G1",
        supported_rules=("planning",),
        supported_scenarios=("rrt_test",),
        supported_obstacles=("static", "enc"),
        known_failure="No successful representative path; dynamic targets are outside this adapter's role.",
    ),
    "rlmpc": Capability(
        readiness_grade="G0",
        supported_rules=("rule14", "multiship"),
        supported_scenarios=("head_on", "rlmpc_scenario"),
        supported_obstacles=("dynamic", "static", "enc"),
        known_failure="CasADi/Acados solver environment is unavailable.",
    ),
}

TRACKERS: dict[str, Capability] = {
    "scenario_default": Capability(
        readiness_grade="G1",
        supported_rules=(),
        supported_scenarios=(),
        supported_obstacles=("dynamic",),
        known_failure="The actual tracker varies by scenario and is not a stable validation identity.",
    ),
    "god": Capability(
        readiness_grade="G2",
        supported_rules=("rule14",),
        supported_scenarios=("head_on",),
        supported_obstacles=("dynamic",),
        latest_evidence={"scenario_id": "head_on", "seed": 0, "algorithms": ["nominal", "vo", "sbmpc"]},
    ),
    "kf": Capability(
        readiness_grade="G2",
        supported_rules=("rule14",),
        supported_scenarios=("head_on",),
        supported_obstacles=("dynamic",),
        latest_evidence={"scenario_id": "head_on", "seed": 0, "algorithms": ["nominal", "vo", "sbmpc"]},
    ),
    "vimmjipda": Capability(
        readiness_grade="G1",
        supported_rules=("rule14", "multiship"),
        supported_scenarios=("head_on", "paper_ccta2023_multiship"),
        supported_obstacles=("dynamic", "clutter"),
        known_failure="Only a 0.2 s smoke run exists; RMSE, NIS/NEES, and ID-switch gates are open.",
    ),
}

GRADE_VALUE = {"G0": 0, "G1": 1, "G2": 2, "G3": 3, "G4": 4}


class CapabilityCatalog:
    """Resolve selectable combinations without confusing import status with readiness."""

    def __init__(self, registry: Any) -> None:
        self.registry = registry

    @staticmethod
    def _scenario_capability(scenario_id: str, valid: bool) -> Capability:
        if scenario_id in SCENARIOS:
            return SCENARIOS[scenario_id]
        return Capability(
            readiness_grade="G1" if valid else "G0",
            supported_rules=(),
            supported_scenarios=(scenario_id,),
            supported_obstacles=(),
            known_failure=None if valid else "Scenario schema or required input is invalid.",
        )

    def annotate_scenario(self, document: dict[str, Any]) -> dict[str, Any]:
        capability = self._scenario_capability(document["id"], bool(document.get("valid")))
        dependency_available = bool(document.get("valid"))
        runtime_ready = dependency_available and GRADE_VALUE[capability.readiness_grade] >= 2
        selectable = runtime_ready and capability.readiness_grade == "G3"
        failure = capability.known_failure or document.get("reason")
        output = dict(document)
        output.update(
            {
                "readiness_grade": capability.readiness_grade,
                "dependency_available": dependency_available,
                "runtime_ready": runtime_ready,
                "selectable": selectable,
                "supported_rules": list(capability.supported_rules),
                "supported_scenarios": list(capability.supported_scenarios),
                "supported_obstacles": list(capability.supported_obstacles),
                "verified_combinations": [
                    {"scenario_id": document["id"], "validation_rule_id": rule_id}
                    for rule_id in capability.supported_rules
                    if selectable
                ],
                "latest_evidence": capability.latest_evidence,
                "known_failure": failure,
                "incompatibility_reason": None if selectable else failure or "Scenario has not passed the G3 display gate.",
            }
        )
        return output

    def document(self, scenarios: list[dict[str, Any]], validation_rule_id: str | None = None) -> dict[str, Any]:
        statuses = self.registry.statuses()
        rule_ids = [validation_rule_id] if validation_rule_id else list(RULES)
        unknown = [rule_id for rule_id in rule_ids if rule_id not in RULES]
        if unknown:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unsupported validation rule: {unknown[0]}")
        annotated_scenarios = [self.annotate_scenario(item) for item in scenarios]
        if validation_rule_id:
            annotated_scenarios = [item for item in annotated_scenarios if validation_rule_id in item["supported_rules"]]
        return {
            "schema_version": CAPABILITY_SCHEMA_VERSION,
            "rules": [self._rule_document(rule_id) for rule_id in rule_ids],
            "scenarios": annotated_scenarios,
            "algorithms": [
                self._integration_document(identifier, capability, statuses.get(identifier), "algorithm", validation_rule_id)
                for identifier, capability in ALGORITHMS.items()
            ],
            "trackers": [
                self._integration_document(identifier, capability, statuses.get(identifier), "tracker", validation_rule_id)
                for identifier, capability in TRACKERS.items()
            ],
            "defaults": {
                "validation_rule_id": "rule14",
                "scenario_id": "head_on",
                "algorithm_id": "nominal",
                "tracker_id": "god",
            },
        }

    @staticmethod
    def _rule_document(rule_id: str) -> dict[str, Any]:
        rule = RULES[rule_id]
        selectable = rule["readiness_grade"] == "G3"
        supported_scenarios = [
            scenario_id for scenario_id, capability in SCENARIOS.items() if rule_id in capability.supported_rules
        ]
        return {
            "id": rule_id,
            **rule,
            "dependency_available": True,
            "runtime_ready": GRADE_VALUE[rule["readiness_grade"]] >= 2,
            "selectable": selectable,
            "supported_rules": [rule_id],
            "supported_scenarios": supported_scenarios,
            "supported_obstacles": sorted(
                {obstacle for scenario_id in supported_scenarios for obstacle in SCENARIOS[scenario_id].supported_obstacles}
            ),
            "verified_combinations": [
                {"validation_rule_id": rule_id, "scenario_id": scenario_id}
                for scenario_id in supported_scenarios
                if SCENARIOS[scenario_id].readiness_grade == "G3"
            ],
            "latest_evidence": SCENARIOS.get(rule["default_scenario"], Capability("G0", (), (), ())).latest_evidence,
            "known_failure": None if selectable else "Rule display template has not passed the G3 gate.",
            "incompatibility_reason": None if selectable else "Rule display template has not passed the G3 gate.",
        }

    @staticmethod
    def _integration_document(
        identifier: str,
        capability: Capability,
        status: Any,
        kind: str,
        validation_rule_id: str | None,
    ) -> dict[str, Any]:
        dependency_available = bool(status and status.available)
        rule_compatible = validation_rule_id is None or validation_rule_id in capability.supported_rules
        grade_ready = (
            GRADE_VALUE[capability.readiness_grade] >= 2
            if identifier in {"nominal", "god", "kf"}
            else GRADE_VALUE[capability.readiness_grade] >= 3
        )
        runtime_ready = dependency_available and GRADE_VALUE[capability.readiness_grade] >= 2
        selectable = runtime_ready and rule_compatible and grade_ready
        incompatibility = None
        if not dependency_available:
            incompatibility = status.reason if status else "Integration is not registered."
        elif not rule_compatible:
            incompatibility = f"{identifier} does not support {validation_rule_id}."
        elif not grade_ready:
            incompatibility = capability.known_failure or f"{identifier} has not passed its readiness gate."
        return {
            "id": identifier,
            "kind": kind,
            "readiness_grade": capability.readiness_grade,
            "dependency_available": dependency_available,
            "runtime_ready": runtime_ready,
            "selectable": selectable,
            "supported_rules": list(capability.supported_rules),
            "supported_scenarios": list(capability.supported_scenarios),
            "supported_obstacles": list(capability.supported_obstacles),
            "verified_combinations": [
                {
                    "scenario_id": scenario_id,
                    "validation_rule_id": rule_id,
                }
                for scenario_id in capability.supported_scenarios
                for rule_id in capability.supported_rules
                if rule_id in SCENARIOS.get(scenario_id, Capability("G0", (), (), ())).supported_rules
            ],
            "latest_evidence": capability.latest_evidence,
            "known_failure": capability.known_failure,
            "incompatibility_reason": incompatibility,
            "source": status.source if status else None,
            "version": status.version if status else None,
            "commit": status.commit if status else None,
        }

    def validate(self, validation_rule_id: str, scenario_id: str, algorithm_id: str, tracker_id: str) -> str:
        if validation_rule_id not in RULES:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unsupported validation rule: {validation_rule_id}")
        scenario = self._scenario_capability(scenario_id, True)
        if validation_rule_id not in scenario.supported_rules or scenario.readiness_grade != "G3":
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"{scenario_id} is not a selectable {validation_rule_id} validation scene",
            )
        self._validate_integration(ALGORITHMS, algorithm_id, validation_rule_id, scenario_id, baseline=True)
        self._validate_integration(TRACKERS, tracker_id, validation_rule_id, scenario_id, baseline=False)
        return f"{validation_rule_id}:{scenario_id}:{algorithm_id}:{tracker_id}"

    def _validate_integration(
        self,
        capabilities: dict[str, Capability],
        identifier: str,
        rule_id: str,
        scenario_id: str,
        baseline: bool,
    ) -> None:
        capability = capabilities.get(identifier)
        status = self.registry.statuses().get(identifier)
        if capability is None or status is None:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unsupported integration: {identifier}")
        if not status.available:
            raise ColavExecutionError(
                PlanStatus.DEPENDENCY_UNAVAILABLE,
                f"{identifier} unavailable: {status.reason}",
            )
        minimum = 2 if baseline and identifier == "nominal" else (2 if identifier in {"god", "kf"} else 3)
        if (
            GRADE_VALUE[capability.readiness_grade] < minimum
            or rule_id not in capability.supported_rules
            or scenario_id not in capability.supported_scenarios
        ):
            reason = capability.known_failure or f"{identifier} is not verified for {rule_id}/{scenario_id}"
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, reason)

    @staticmethod
    def grade(kind: str, identifier: str) -> str:
        capabilities = ALGORITHMS if kind == "algorithm" else TRACKERS
        return capabilities.get(identifier, Capability("G0", (), (), ())).readiness_grade
