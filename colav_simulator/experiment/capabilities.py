"""Versioned rule, scenario, algorithm, and tracker capability catalog."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from colav_simulator.core.colav.diagnostics import ColavExecutionError, PlanStatus
from colav_simulator.core.colav.threat_assessment import ShipDomainProfile
from colav_simulator.experiment.contracts import InternalExecutionPurpose, _ship_domain_profile_from_mapping
from colav_simulator.experiment.g3_gate import PREDICATE_VERSION

CAPABILITY_SCHEMA_VERSION = "1.0"
ENCOUNTER_PROFILE_ID = "legacy-g3-v1"


@dataclass(frozen=True)
class Capability:
    """Declared readiness and compatibility for one selectable integration."""

    readiness_grade: str
    supported_rules: tuple[str, ...]
    supported_scenarios: tuple[str, ...]
    supported_obstacles: tuple[str, ...]
    known_failure: str | None = None


RULES: dict[str, dict[str, Any]] = {
    "rule13": {
        "label": "Rule 13-OT",
        "encounter_types": ["OT_ing", "OT_en"],
        "readiness_grade": "G3",
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
        "readiness_grade": "G3",
        "default_scenario": "crossing_give_way",
    },
    "multiship": {
        "label": "Multi-ship",
        "encounter_types": ["MS"],
        "readiness_grade": "G3",
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
    "head_on": Capability("G3", ("rule14",), ("head_on",), ("dynamic", "enc")),
    "overtaking": Capability("G3", ("rule13",), ("overtaking",), ("dynamic", "enc")),
    "overtaken": Capability("G3", ("rule13",), ("overtaken",), ("dynamic", "enc")),
    "crossing_give_way": Capability("G3", ("rule15",), ("crossing_give_way",), ("dynamic", "enc")),
    "crossing_stand_on": Capability("G3", ("rule15",), ("crossing_stand_on",), ("dynamic", "enc")),
    "aalesund_random1": Capability(
        "G2",
        ("rule14",),
        ("aalesund_random1",),
        ("dynamic", "enc"),
        "Natural clearance does not reliably exercise every COLAV algorithm.",
    ),
    "paper_ccta2023_head_on": Capability(
        "G2",
        ("rule14",),
        ("paper_ccta2023_head_on",),
        ("dynamic", "enc"),
        "Functional paper reconstruction; numerical reproduction is not confirmed.",
    ),
    "paper_ccta2023_multiship": Capability(
        "G3",
        ("multiship",),
        ("paper_ccta2023_multiship",),
        ("dynamic", "enc"),
    ),
    "romsdal_busy_water_16": Capability(
        "G2",
        ("multiship",),
        ("romsdal_busy_water_16",),
        ("dynamic", "enc"),
        "Experimental 16-ship acceptance scene; raw G3 promotion is pending.",
    ),
    "romsdal_busy_water_80_stress": Capability(
        "G2",
        ("multiship",),
        ("romsdal_busy_water_80_stress",),
        ("dynamic", "enc"),
        "Stress-only 80-ship scene; excluded from algorithm G3 claims.",
    ),
    "rrt_test": Capability(
        "G0",
        ("planning",),
        ("rrt_test",),
        ("static", "enc"),
        "Scenario preparation fails with an empty safe-sea Polygon.",
    ),
}

_P1_RULES = ("rule13", "rule14", "rule15", "multiship")
_P1_SCENARIOS = (
    "head_on",
    "overtaking",
    "overtaken",
    "crossing_give_way",
    "crossing_stand_on",
    "paper_ccta2023_multiship",
)

ALGORITHMS: dict[str, Capability] = {
    "mid_mpc_ipopt": Capability(
        "G3",
        ("rule13", "rule14", "rule15", "multiship"),
        (
            "head_on",
            "overtaking",
            "overtaken",
            "crossing_give_way",
            "crossing_stand_on",
            "paper_ccta2023_multiship",
        ),
        ("dynamic",),
        "Ship0 raw G3 is established; the fixed multiship scene retains three "
        "scenario-intrinsic target-target collisions, so global all-vessel safety is not established.",
    ),
    "nominal": Capability("G2", _P1_RULES, _P1_SCENARIOS, ("none",)),
    "vo": Capability("G3", _P1_RULES, _P1_SCENARIOS, ("dynamic", "static", "enc")),
    "sbmpc": Capability("G3", _P1_RULES, _P1_SCENARIOS, ("dynamic",)),
    "potocnik_simplified_mpc": Capability("G3", _P1_RULES, _P1_SCENARIOS, ("dynamic",)),
    "potocnik_colreg_fan_mpc": Capability(
        "G3",
        _P1_RULES,
        _P1_SCENARIOS,
        ("dynamic", "static", "enc"),
    ),
    "psbmpc": Capability(
        "G1",
        ("rule14", "multiship"),
        ("head_on", "paper_ccta2023_multiship"),
        ("dynamic", "static", "enc"),
        "500 s run aborts in Eigen Block.h:126; native process isolation is not complete.",
    ),
    "rrt": Capability(
        "G1",
        ("planning",),
        ("rrt_test",),
        ("static", "enc"),
        "No successful representative path; dynamic targets are outside this adapter's role.",
    ),
    "rlmpc": Capability(
        "G0",
        ("rule14", "multiship"),
        ("head_on", "rlmpc_scenario"),
        ("dynamic", "static", "enc"),
        "CasADi/Acados solver environment is unavailable.",
    ),
}

TRACKERS: dict[str, Capability] = {
    "scenario_default": Capability(
        "G1",
        (),
        (),
        ("dynamic",),
        "The actual tracker varies by scenario and is not a stable validation identity.",
    ),
    "god": Capability("G2", _P1_RULES, _P1_SCENARIOS, ("dynamic",)),
    "kf": Capability("G2", ("rule14",), ("head_on",), ("dynamic",)),
    "vimmjipda": Capability(
        "G1",
        ("rule14", "multiship"),
        ("head_on", "paper_ccta2023_multiship"),
        ("dynamic", "clutter"),
        "Only a 0.2 s smoke run exists; RMSE, NIS/NEES, and ID-switch gates are open.",
    ),
}

GRADE_VALUE = {"G0": 0, "G1": 1, "G2": 2, "G3": 3, "G4": 4}


@dataclass(frozen=True)
class ProductCapabilityPolicy:
    """Define the integrations exposed by the current product surface.

    The registry intentionally retains legacy builders for internal replay,
    evaluator baselines, and compatibility tests.  This policy is the
    explicit boundary for user-selectable validation sessions; it is not a
    statement that a retained legacy implementation can no longer be built.
    """

    algorithm_ids: tuple[str, ...] = ("vo", "potocnik_colreg_fan_mpc", "mid_mpc_ipopt")
    tracker_ids: tuple[str, ...] = ("god",)
    default_algorithm_id: str = "vo"
    default_tracker_id: str = "god"
    domain_profile_algorithm_ids: tuple[str, ...] = ("mid_mpc_ipopt",)

    def allows_algorithm(self, identifier: str) -> bool:
        return identifier in self.algorithm_ids

    def allows_tracker(self, identifier: str) -> bool:
        return identifier in self.tracker_ids

    def allows_tuple(self, key: tuple[str, str, str, str]) -> bool:
        return self.allows_algorithm(key[2]) and self.allows_tracker(key[3])

    def requires_domain_profile(self, algorithm_id: str) -> bool:
        """Return whether this product algorithm needs an explicit domain profile."""
        return algorithm_id.strip().lower() in self.domain_profile_algorithm_ids

    def parse_domain_profile(
        self,
        value: ShipDomainProfile | Mapping[str, Any] | None,
    ) -> ShipDomainProfile | None:
        """Parse one explicit profile at the product boundary.

        Profile mappings are content-addressed by :class:`ShipDomainProfile`.
        A caller may omit the profile only for algorithms that do not require
        one; Mid-MPC validation is handled by :meth:`validate_domain_profile`.
        """
        if value is None:
            return None
        if isinstance(value, ShipDomainProfile):
            return value
        if not isinstance(value, Mapping):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "domain_profile must be a ShipDomainProfile or mapping",
            )
        try:
            return _ship_domain_profile_from_mapping(value)
        except (TypeError, ValueError) as exc:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, str(exc)) from exc

    def validate_domain_profile(
        self,
        algorithm_id: str,
        value: ShipDomainProfile | Mapping[str, Any] | None,
    ) -> ShipDomainProfile | None:
        """Validate the profile requirement for one product algorithm."""
        profile = self.parse_domain_profile(value)
        if not self.requires_domain_profile(algorithm_id):
            return profile
        if profile is None:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "formal Mid-MPC run requires an explicitly supplied qualified ShipDomainProfile",
            )
        if not profile.qualified:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "formal Mid-MPC run requires a qualified ShipDomainProfile",
            )
        return profile

    def constraints(self, algorithm_id: str | None = None) -> dict[str, Any]:
        """Return the same domain-profile contract consumed by API and UI."""
        documents = {
            identifier: {
                "requires_domain_profile": self.requires_domain_profile(identifier),
                **(
                    {"required_domain_qualification": "QUALIFIED"}
                    if self.requires_domain_profile(identifier)
                    else {}
                ),
            }
            for identifier in self.algorithm_ids
        }
        if algorithm_id is None:
            return documents
        return documents.get(
            algorithm_id.strip().lower(),
            {
                "requires_domain_profile": self.requires_domain_profile(algorithm_id),
            },
        )

    def infer_rule(self, scenario_id: str, algorithm_id: str, tracker_id: str) -> str:
        """Infer one and only one product Rule for an exact scenario tuple."""
        algorithm_id = algorithm_id.strip().lower()
        tracker_id = tracker_id.strip().lower()
        self.require_integrations(algorithm_id, tracker_id)
        candidates = {
            rule_id
            for rule_id, scenario, candidate_algorithm, candidate_tracker in (
                *VERIFIED_COMBINATIONS,
                *EXPERIMENTAL_COMBINATIONS,
            )
            if scenario == scenario_id
            and candidate_algorithm == algorithm_id
            and candidate_tracker == tracker_id
            and self.allows_tuple((rule_id, scenario, candidate_algorithm, candidate_tracker))
        }
        if len(candidates) != 1:
            if not candidates:
                raise ColavExecutionError(
                    PlanStatus.INVALID_INPUT,
                    f"No unique product validation rule for {scenario_id}/{algorithm_id}/{tracker_id}",
                )
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"Multiple product validation rules for {scenario_id}/{algorithm_id}/{tracker_id}: "
                f"{', '.join(sorted(candidates))}",
            )
        return next(iter(candidates))

    def filter_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            item
            for item in documents
            if self.allows_tuple(
                (
                    str(item["validation_rule_id"]),
                    str(item["scenario_id"]),
                    str(item["algorithm_id"]),
                    str(item["tracker_id"]),
                )
            )
        ]

    def rejection_reason(self, kind: str, identifier: str) -> str:
        return f"{kind.capitalize()} {identifier} is not selectable in the current product capability policy."

    def require_integrations(self, algorithm_id: str, tracker_id: str) -> None:
        """Reject retired product identities before tuple/dependency work."""
        if not self.allows_algorithm(algorithm_id):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                self.rejection_reason("algorithm", algorithm_id),
            )
        if not self.allows_tracker(tracker_id):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                self.rejection_reason("tracker", tracker_id),
            )

    def validate(
        self,
        validation_rule_id: str,
        scenario_id: str,
        algorithm_id: str,
        tracker_id: str,
    ) -> tuple[str, str, str, str]:
        """Validate a product-selectable exact tuple without registry concerns."""
        algorithm_id = algorithm_id.strip().lower()
        tracker_id = tracker_id.strip().lower()
        if validation_rule_id not in RULES:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unsupported validation rule: {validation_rule_id}")
        self.require_integrations(algorithm_id, tracker_id)
        key = (validation_rule_id, scenario_id, algorithm_id, tracker_id)
        if key not in VERIFIED_COMBINATIONS and key not in EXPERIMENTAL_COMBINATIONS:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"No product capability tuple for {validation_rule_id}/{scenario_id}/{algorithm_id}/{tracker_id}",
            )
        return key

    def validate_internal(
        self,
        validation_rule_id: str,
        scenario_id: str,
        algorithm_id: str,
        tracker_id: str,
        purpose: InternalExecutionPurpose,
    ) -> tuple[str, str, str, str]:
        """Validate one explicit internal baseline/replay purpose and tuple."""
        if not isinstance(purpose, InternalExecutionPurpose):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                "Internal execution requires a typed InternalExecutionPurpose",
            )
        algorithm_id = algorithm_id.strip().lower()
        tracker_id = tracker_id.strip().lower()
        if algorithm_id != "nominal" or tracker_id != "god":
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"{purpose.value} permits only nominal/god internal baseline tuple",
            )
        key = (validation_rule_id, scenario_id, algorithm_id, tracker_id)
        if key not in VERIFIED_COMBINATIONS and key not in EXPERIMENTAL_COMBINATIONS:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"No internal capability tuple for {validation_rule_id}/{scenario_id}/{algorithm_id}/{tracker_id}",
            )
        return key

    def to_dict(self) -> dict[str, Any]:
        """Publish one machine-readable product selection contract."""
        return {
            "policy_id": "colav-product-v1",
            "algorithm_ids": list(self.algorithm_ids),
            "tracker_ids": list(self.tracker_ids),
            "default_algorithm_id": self.default_algorithm_id,
            "default_tracker_id": self.default_tracker_id,
            "constraints": {
                "requires_explicit_validation_rule_id": True,
                "requires_exact_tuple": True,
                "algorithms": self.constraints(),
            },
        }


PRODUCT_CAPABILITY_POLICY = ProductCapabilityPolicy()


def _evidence(
    *,
    role: str,
    termination: str,
    minimum_clearance_m: float,
    max_heading_delta_deg: float = 0.0,
    max_speed_delta_mps: float = 0.0,
    solve_count: int = 0,
    target_minimum_clearance_m: dict[str, float] | None = None,
) -> dict[str, Any]:
    output = {
        "seed": 0,
        "evidence_role": role,
        "termination": termination,
        "minimum_clearance_m": minimum_clearance_m,
        "max_heading_delta_deg": max_heading_delta_deg,
        "max_speed_delta_mps": max_speed_delta_mps,
        "solve_count": solve_count,
        "encounter_profile_id": ENCOUNTER_PROFILE_ID,
        "predicate_version": PREDICATE_VERSION,
    }
    if target_minimum_clearance_m is not None:
        output["target_minimum_clearance_m"] = target_minimum_clearance_m
    return output


VERIFIED_COMBINATIONS: dict[tuple[str, str, str, str], dict[str, Any]] = {
    ("rule14", "head_on", "nominal", "god"): _evidence(
        role="nominal_threat",
        termination="time_limit",
        minimum_clearance_m=0.427124755721149,
    ),
    ("rule14", "head_on", "mid_mpc_ipopt", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=516.4523357102253,
        max_heading_delta_deg=178.72315287027416,
        max_speed_delta_mps=0.12695987433892952,
        solve_count=120,
    ),
    ("rule14", "head_on", "vo", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=321.3402212235414,
        max_heading_delta_deg=59.66279571556297,
        max_speed_delta_mps=0.5596654215967902,
        solve_count=300,
    ),
    ("rule14", "head_on", "sbmpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=94.17164786336312,
        max_heading_delta_deg=56.64274963391734,
        max_speed_delta_mps=0.03765092218329524,
        solve_count=59,
    ),
    ("rule14", "head_on", "potocnik_simplified_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=177.4664709046381,
        max_heading_delta_deg=33.205243745967415,
        max_speed_delta_mps=0.06276987381857602,
        solve_count=60,
    ),
    ("rule14", "head_on", "potocnik_colreg_fan_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=256.89241390663,
        max_heading_delta_deg=30.27029135425717,
        max_speed_delta_mps=0.08959324840901406,
        solve_count=60,
    ),
    ("rule14", "head_on", "nominal", "kf"): _evidence(
        role="nominal_threat",
        termination="time_limit",
        minimum_clearance_m=0.427124755721149,
    ),
    ("rule14", "head_on", "vo", "kf"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=333.9307091971996,
        max_heading_delta_deg=59.800455141949286,
        max_speed_delta_mps=0.5651259766220909,
        solve_count=300,
    ),
    ("rule14", "head_on", "sbmpc", "kf"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=91.81360285247291,
        max_heading_delta_deg=56.38965423338835,
        max_speed_delta_mps=0.03946077694195971,
        solve_count=59,
    ),
    ("rule13", "overtaking", "nominal", "god"): _evidence(
        role="nominal_threat",
        termination="time_limit",
        minimum_clearance_m=0.6067811791803845,
    ),
    ("rule13", "overtaking", "mid_mpc_ipopt", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=72.48434806293345,
        max_heading_delta_deg=45.78137330358685,
        max_speed_delta_mps=0.12706782139985418,
        solve_count=120,
    ),
    ("rule13", "overtaking", "vo", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=302.0648709157351,
        max_heading_delta_deg=68.13960800400456,
        max_speed_delta_mps=2.678069662510069,
        solve_count=600,
    ),
    ("rule13", "overtaking", "sbmpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=39.10491790513619,
        max_heading_delta_deg=92.6401618894945,
        max_speed_delta_mps=4.284630739430558,
        solve_count=59,
    ),
    ("rule13", "overtaking", "potocnik_simplified_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=198.61436610189946,
        max_heading_delta_deg=24.490676105170024,
        max_speed_delta_mps=0.05206359317906273,
        solve_count=60,
    ),
    ("rule13", "overtaking", "potocnik_colreg_fan_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=395.09535062973606,
        max_heading_delta_deg=24.00048299431012,
        max_speed_delta_mps=0.03334444158001659,
        solve_count=60,
    ),
    ("rule13", "overtaken", "nominal", "god"): _evidence(
        role="nominal_threat",
        termination="time_limit",
        minimum_clearance_m=7.097054495203236,
    ),
    ("rule13", "overtaken", "mid_mpc_ipopt", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=87.35343855602845,
        max_heading_delta_deg=59.26306670218723,
        max_speed_delta_mps=1.5961141199621909,
        solve_count=120,
    ),
    ("rule13", "overtaken", "vo", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=15.62415267419944,
        max_heading_delta_deg=36.527708719921705,
        max_speed_delta_mps=1.5926262975325196,
        solve_count=300,
    ),
    ("rule13", "overtaken", "sbmpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=72.50862802922902,
        max_heading_delta_deg=75.36221900948048,
        max_speed_delta_mps=0.041714044297822994,
        solve_count=59,
    ),
    ("rule13", "overtaken", "potocnik_simplified_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=157.2183233072254,
        max_heading_delta_deg=37.91609720972987,
        max_speed_delta_mps=0.0647649330859057,
        solve_count=60,
    ),
    ("rule13", "overtaken", "potocnik_colreg_fan_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=201.1547081167404,
        max_heading_delta_deg=34.11450624006304,
        max_speed_delta_mps=0.03539953608712132,
        solve_count=60,
    ),
    ("rule15", "crossing_give_way", "nominal", "god"): _evidence(
        role="nominal_threat",
        termination="goal_reached",
        minimum_clearance_m=1.4142135623730951,
    ),
    ("rule15", "crossing_give_way", "mid_mpc_ipopt", "god"): _evidence(
        role="candidate_g3",
        termination="goal_reached",
        minimum_clearance_m=416.3053456088816,
        max_heading_delta_deg=92.55096367282218,
        max_speed_delta_mps=0.11109680276369094,
        solve_count=72,
    ),
    ("rule15", "crossing_give_way", "vo", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=456.96132688520476,
        max_heading_delta_deg=18.265226178983205,
        max_speed_delta_mps=5.23461362646585,
        solve_count=300,
    ),
    ("rule15", "crossing_give_way", "sbmpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=183.48098204305828,
        max_heading_delta_deg=108.86393299415012,
        max_speed_delta_mps=0.045194679263571125,
        solve_count=59,
    ),
    ("rule15", "crossing_give_way", "potocnik_colreg_fan_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=476.03660138642147,
        max_heading_delta_deg=48.34718731841948,
        max_speed_delta_mps=0.024431426407555357,
        solve_count=60,
    ),
    ("rule15", "crossing_stand_on", "nominal", "god"): _evidence(
        role="nominal_threat",
        termination="goal_reached",
        minimum_clearance_m=1.4142135623730951,
    ),
    ("rule15", "crossing_stand_on", "mid_mpc_ipopt", "god"): _evidence(
        role="candidate_g3",
        termination="goal_reached",
        minimum_clearance_m=62.313192874183876,
        max_heading_delta_deg=85.94929931782258,
        max_speed_delta_mps=2.503870044402179,
        solve_count=78,
    ),
    ("rule15", "crossing_stand_on", "vo", "god"): _evidence(
        role="candidate_g3",
        termination="goal_reached",
        minimum_clearance_m=9.814694644867357,
        max_heading_delta_deg=51.15859113997461,
        max_speed_delta_mps=1.0203579647686265,
        solve_count=284,
    ),
    ("rule15", "crossing_stand_on", "sbmpc", "god"): _evidence(
        role="candidate_g3",
        termination="goal_reached",
        minimum_clearance_m=70.29544747759203,
        max_heading_delta_deg=43.272780673026624,
        max_speed_delta_mps=0.046880638656195295,
        solve_count=57,
    ),
    ("rule15", "crossing_stand_on", "potocnik_simplified_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=240.95569916174946,
        max_heading_delta_deg=46.424123232053326,
        max_speed_delta_mps=0.09408005379016071,
        solve_count=60,
    ),
    ("rule15", "crossing_stand_on", "potocnik_colreg_fan_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=217.17081565081025,
        max_heading_delta_deg=10.313606223711929,
        max_speed_delta_mps=4.5795819566781155,
        solve_count=60,
    ),
    ("multiship", "paper_ccta2023_multiship", "nominal", "god"): _evidence(
        role="nominal_threat",
        termination="time_limit",
        minimum_clearance_m=9.313296800157313e-07,
        target_minimum_clearance_m={
            "Ship1": 1.862645149230957e-06,
            "Ship2": 9.313296800157313e-07,
            "Ship3": 9.313296800157313e-07,
        },
    ),
    ("multiship", "paper_ccta2023_multiship", "mid_mpc_ipopt", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=80.0796172203075,
        max_heading_delta_deg=71.69699043721292,
        max_speed_delta_mps=0.588801738684352,
        solve_count=100,
        target_minimum_clearance_m={
            "Ship1": 217.8415627536574,
            "Ship2": 156.51722125513535,
            "Ship3": 80.0796172203075,
        },
    ),
    ("multiship", "paper_ccta2023_multiship", "vo", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=98.75415680498888,
        max_heading_delta_deg=55.288570211446164,
        max_speed_delta_mps=3.991739271877762,
        solve_count=482,
        target_minimum_clearance_m={
            "Ship1": 98.75415680498888,
            "Ship2": 365.82380221179096,
            "Ship3": 282.4573327652142,
        },
    ),
    ("multiship", "paper_ccta2023_multiship", "sbmpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=92.19818057550195,
        max_heading_delta_deg=50.9041934922255,
        max_speed_delta_mps=3.836430355969612,
        solve_count=99,
        target_minimum_clearance_m={
            "Ship1": 94.79658705437517,
            "Ship2": 200.97886849598802,
            "Ship3": 92.19818057550195,
        },
    ),
    ("multiship", "paper_ccta2023_multiship", "potocnik_simplified_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=210.13242210802974,
        max_heading_delta_deg=31.391857617432755,
        max_speed_delta_mps=0.0,
        solve_count=100,
        target_minimum_clearance_m={
            "Ship1": 307.14509710024777,
            "Ship2": 224.2361752925445,
            "Ship3": 210.13242210802974,
        },
    ),
    ("multiship", "paper_ccta2023_multiship", "potocnik_colreg_fan_mpc", "god"): _evidence(
        role="candidate_g3",
        termination="time_limit",
        minimum_clearance_m=259.73073963582544,
        max_heading_delta_deg=21.752881470964397,
        max_speed_delta_mps=1.896361674989417,
        solve_count=100,
        target_minimum_clearance_m={
            "Ship1": 266.7316087706566,
            "Ship2": 549.3389961524218,
            "Ship3": 259.73073963582544,
        },
    ),
}

_BUSY_WATER_ALGORITHMS = PRODUCT_CAPABILITY_POLICY.algorithm_ids[:2]
_BUSY_WATER_EVIDENCE = {
    "romsdal_busy_water_16": {
        "seed": 20250731,
        "evidence_role": "experimental_acceptance_pending",
        "readiness_grade": "G2",
        "promotion_status": "RAW_G3_PENDING",
        "scope": "ship0_algorithm_responsibility",
    },
    "romsdal_busy_water_80_stress": {
        "seed": 20250731,
        "evidence_role": "stress_only_not_g3",
        "readiness_grade": "G2",
        "promotion_status": "NOT_ELIGIBLE_FOR_G3",
        "scope": "runtime_and_interface_load",
    },
}
EXPERIMENTAL_COMBINATIONS: dict[tuple[str, str, str, str], dict[str, Any]] = {
    ("multiship", scenario_id, algorithm_id, "god"): dict(evidence)
    for scenario_id, evidence in _BUSY_WATER_EVIDENCE.items()
    for algorithm_id in _BUSY_WATER_ALGORITHMS
}
EXPERIMENTAL_COMBINATIONS[("multiship", "romsdal_busy_water_16", "mid_mpc_ipopt", "god")] = dict(
    _BUSY_WATER_EVIDENCE["romsdal_busy_water_16"]
)


def _combination_documents(
    *,
    rule_id: str | None = None,
    scenario_id: str | None = None,
    algorithm_id: str | None = None,
    tracker_id: str | None = None,
) -> list[dict[str, Any]]:
    output = []
    for key, evidence in VERIFIED_COMBINATIONS.items():
        rule, scenario, algorithm, tracker = key
        if rule_id is not None and rule != rule_id:
            continue
        if scenario_id is not None and scenario != scenario_id:
            continue
        if algorithm_id is not None and algorithm != algorithm_id:
            continue
        if tracker_id is not None and tracker != tracker_id:
            continue
        output.append(
            {
                "validation_rule_id": rule,
                "scenario_id": scenario,
                "algorithm_id": algorithm,
                "tracker_id": tracker,
                "predicate_version": PREDICATE_VERSION,
                "latest_evidence": dict(evidence),
            }
        )
    return output


def _experimental_combination_documents(
    rule_id: str | None = None,
    scenario_id: str | None = None,
    algorithm_id: str | None = None,
    tracker_id: str | None = None,
) -> list[dict[str, Any]]:
    output = []
    for key, evidence in EXPERIMENTAL_COMBINATIONS.items():
        rule, scenario, algorithm, tracker = key
        if rule_id is not None and rule != rule_id:
            continue
        if scenario_id is not None and scenario != scenario_id:
            continue
        if algorithm_id is not None and algorithm != algorithm_id:
            continue
        if tracker_id is not None and tracker != tracker_id:
            continue
        output.append(
            {
                "validation_rule_id": rule,
                "scenario_id": scenario,
                "algorithm_id": algorithm,
                "tracker_id": tracker,
                "predicate_version": PREDICATE_VERSION,
                "latest_evidence": dict(evidence),
                "experimental": True,
            }
        )
    return output


class CapabilityCatalog:
    """Resolve selectable combinations from exact raw-evidence tuples."""

    def __init__(self, registry: Any, policy: ProductCapabilityPolicy = PRODUCT_CAPABILITY_POLICY) -> None:
        self.registry = registry
        self.policy = policy

    def _product_combination_documents(
        self,
        *,
        rule_id: str | None = None,
        scenario_id: str | None = None,
        algorithm_id: str | None = None,
        tracker_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.policy.filter_documents(
            _combination_documents(
                rule_id=rule_id,
                scenario_id=scenario_id,
                algorithm_id=algorithm_id,
                tracker_id=tracker_id,
            )
        )

    def _product_experimental_combination_documents(
        self,
        *,
        rule_id: str | None = None,
        scenario_id: str | None = None,
        algorithm_id: str | None = None,
        tracker_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.policy.filter_documents(
            _experimental_combination_documents(
                rule_id=rule_id,
                scenario_id=scenario_id,
                algorithm_id=algorithm_id,
                tracker_id=tracker_id,
            )
        )

    @staticmethod
    def _scenario_capability(scenario_id: str, valid: bool) -> Capability:
        if scenario_id in SCENARIOS:
            return SCENARIOS[scenario_id]
        return Capability(
            "G1" if valid else "G0",
            (),
            (scenario_id,),
            (),
            None if valid else "Scenario schema or required input is invalid.",
        )

    def annotate_scenario(self, document: dict[str, Any]) -> dict[str, Any]:
        capability = self._scenario_capability(document["id"], bool(document.get("valid")))
        combinations = self._product_combination_documents(scenario_id=document["id"])
        experimental = self._product_experimental_combination_documents(scenario_id=document["id"])
        selectable_combinations = combinations + experimental
        dependency_available = bool(document.get("valid"))
        runtime_ready = dependency_available and GRADE_VALUE[capability.readiness_grade] >= 2
        selectable = runtime_ready and bool(selectable_combinations)
        failure = capability.known_failure or document.get("reason")
        output = dict(document)
        output.update(
            {
                "readiness_grade": capability.readiness_grade,
                "dependency_available": dependency_available,
                "runtime_ready": runtime_ready,
                "selectable": selectable,
                "supported_rules": sorted({item["validation_rule_id"] for item in selectable_combinations}),
                "supported_scenarios": [document["id"]] if selectable_combinations else [],
                "supported_obstacles": list(capability.supported_obstacles),
                "verified_combinations": combinations,
                "experimental_combinations": experimental,
                "latest_evidence": selectable_combinations[-1]["latest_evidence"] if selectable_combinations else None,
                "known_failure": failure,
                "incompatibility_reason": None
                if selectable
                else failure or "Scenario has no selectable capability tuple.",
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
            annotated_scenarios = [
                item
                for item in annotated_scenarios
                if validation_rule_id in SCENARIOS.get(
                    item["id"],
                    Capability("G0", (), (), ()),
                ).supported_rules
            ]
        default_rule = validation_rule_id or "rule14"
        return {
            "schema_version": CAPABILITY_SCHEMA_VERSION,
            "product_capability_policy": self.policy.to_dict(),
            "rules": [self._rule_document(rule_id) for rule_id in rule_ids],
            "scenarios": annotated_scenarios,
            "algorithms": [
                self._integration_document(
                    identifier,
                    capability,
                    statuses.get(identifier),
                    "algorithm",
                    validation_rule_id,
                )
                for identifier, capability in ALGORITHMS.items()
            ],
            "trackers": [
                self._integration_document(
                    identifier,
                    capability,
                    statuses.get(identifier),
                    "tracker",
                    validation_rule_id,
                )
                for identifier, capability in TRACKERS.items()
            ],
            "verified_combinations": self._product_combination_documents(rule_id=validation_rule_id),
            "experimental_combinations": self._product_experimental_combination_documents(rule_id=validation_rule_id),
            "selectable_combinations": self._product_combination_documents(rule_id=validation_rule_id)
                + self._product_experimental_combination_documents(rule_id=validation_rule_id),
            "defaults": {
                "validation_rule_id": default_rule,
                "scenario_id": RULES[default_rule]["default_scenario"],
                "algorithm_id": self.policy.default_algorithm_id,
                "tracker_id": self.policy.default_tracker_id,
            },
        }

    def _rule_document(self, rule_id: str) -> dict[str, Any]:
        rule = RULES[rule_id]
        combinations = self.policy.filter_documents(_combination_documents(rule_id=rule_id))
        supported_scenarios = sorted({item["scenario_id"] for item in combinations})
        selectable = rule["readiness_grade"] == "G3" and bool(combinations)
        return {
            "id": rule_id,
            **rule,
            "dependency_available": True,
            "runtime_ready": GRADE_VALUE[rule["readiness_grade"]] >= 2,
            "selectable": selectable,
            "supported_rules": [rule_id] if combinations else [],
            "supported_scenarios": supported_scenarios,
            "supported_obstacles": sorted(
                {
                    obstacle
                    for scenario_id in supported_scenarios
                    for obstacle in SCENARIOS[scenario_id].supported_obstacles
                }
            ),
            "verified_combinations": combinations,
            "latest_evidence": combinations[-1]["latest_evidence"] if combinations else None,
            "known_failure": None if selectable else "Rule has no verified G3 capability tuple.",
            "incompatibility_reason": None if selectable else "Rule has no verified G3 capability tuple.",
        }

    def _integration_document(
        self,
        identifier: str,
        capability: Capability,
        status: Any,
        kind: str,
        validation_rule_id: str | None,
    ) -> dict[str, Any]:
        filters = {"rule_id": validation_rule_id}
        filters[f"{kind}_id"] = identifier
        combinations = self.policy.filter_documents(_combination_documents(**filters))
        experimental = self.policy.filter_documents(_experimental_combination_documents(**filters))
        selectable_combinations = combinations + experimental
        dependency_available = bool(status and status.available)
        minimum_grade = 2 if identifier in {"nominal", "god", "kf"} else 3
        grade_ready = GRADE_VALUE[capability.readiness_grade] >= minimum_grade
        runtime_ready = dependency_available and GRADE_VALUE[capability.readiness_grade] >= 2
        selectable = runtime_ready and grade_ready and bool(selectable_combinations)
        if not self.policy.allows_algorithm(identifier) and kind == "algorithm":
            incompatibility = self.policy.rejection_reason(kind, identifier)
        elif not self.policy.allows_tracker(identifier) and kind == "tracker":
            incompatibility = self.policy.rejection_reason(kind, identifier)
        elif not dependency_available:
            incompatibility = status.reason if status else "Integration is not registered."
        elif not grade_ready:
            incompatibility = capability.known_failure or f"{identifier} has not passed its readiness gate."
        elif not selectable_combinations:
            incompatibility = f"{identifier} has no selectable tuple for the selected rule."
        else:
            incompatibility = None
        return {
            "id": identifier,
            "kind": kind,
            "readiness_grade": capability.readiness_grade,
            "dependency_available": dependency_available,
            "runtime_ready": runtime_ready,
            "selectable": selectable,
            "supported_rules": sorted({item["validation_rule_id"] for item in selectable_combinations}),
            "supported_scenarios": sorted({item["scenario_id"] for item in selectable_combinations}),
            "supported_obstacles": list(capability.supported_obstacles),
            "verified_combinations": combinations,
            "experimental_combinations": experimental,
            "latest_evidence": selectable_combinations[-1]["latest_evidence"] if selectable_combinations else None,
            "known_failure": capability.known_failure,
            "incompatibility_reason": incompatibility,
            "source": status.source if status else None,
            "version": status.version if status else None,
            "commit": status.commit if status else None,
        }

    def validate(self, validation_rule_id: str, scenario_id: str, algorithm_id: str, tracker_id: str) -> str:
        """Validate one product-selectable exact tuple for a session run."""
        key = self.policy.validate(validation_rule_id, scenario_id, algorithm_id, tracker_id)
        scenario_combinations = [
            *self._product_combination_documents(rule_id=validation_rule_id, scenario_id=scenario_id),
            *self._product_experimental_combination_documents(
                rule_id=validation_rule_id,
                scenario_id=scenario_id,
            ),
        ]
        if not scenario_combinations:
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                f"{scenario_id} is not a selectable {validation_rule_id} validation scene",
            )
        self._require_available(ALGORITHMS, algorithm_id)
        self._require_available(TRACKERS, tracker_id)
        return ":".join(key)

    def validate_internal(
        self,
        validation_rule_id: str,
        scenario_id: str,
        algorithm_id: str,
        tracker_id: str,
        *,
        purpose: InternalExecutionPurpose,
    ) -> str:
        """Validate a retained legacy tuple for internal Historical AIS evidence.

        This seam is intentionally separate from :meth:`validate`: product
        sessions cannot use legacy integrations, while Historical Replay may
        still seal a Nominal pre-T0 reference and evaluator fixtures.
        """
        key = self.policy.validate_internal(validation_rule_id, scenario_id, algorithm_id, tracker_id, purpose)
        self._require_available(ALGORITHMS, algorithm_id)
        self._require_available(TRACKERS, tracker_id)
        return ":".join(key)

    @staticmethod
    def exact_combination_document(
        key: tuple[str, str, str, str],
        *,
        product_only: bool = True,
    ) -> dict[str, Any]:
        """Return the sealed raw-evidence document for one exact tuple."""
        if product_only and not PRODUCT_CAPABILITY_POLICY.allows_tuple(key):
            raise ColavExecutionError(
                PlanStatus.INVALID_INPUT,
                PRODUCT_CAPABILITY_POLICY.rejection_reason("capability tuple", ":".join(key)),
            )
        if key in VERIFIED_COMBINATIONS:
            evidence = VERIFIED_COMBINATIONS[key]
            document = _combination_documents(
                rule_id=key[0],
                scenario_id=key[1],
                algorithm_id=key[2],
                tracker_id=key[3],
            )
        elif key in EXPERIMENTAL_COMBINATIONS:
            evidence = EXPERIMENTAL_COMBINATIONS[key]
            document = _experimental_combination_documents(
                rule_id=key[0],
                scenario_id=key[1],
                algorithm_id=key[2],
                tracker_id=key[3],
            )
        else:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unknown capability tuple: {':'.join(key)}")
        if not document:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unknown capability tuple: {':'.join(key)}")
        # Keep this lookup explicit so callers cannot accidentally seal a
        # different tuple when the evidence map is extended.
        item = document[0]
        if item["latest_evidence"] != evidence:
            item = dict(item)
            item["latest_evidence"] = dict(evidence)
        return item

    def _require_available(self, capabilities: dict[str, Capability], identifier: str) -> None:
        capability = capabilities.get(identifier)
        status = self.registry.statuses().get(identifier)
        if capability is None or status is None:
            raise ColavExecutionError(PlanStatus.INVALID_INPUT, f"Unsupported integration: {identifier}")
        if not status.available:
            raise ColavExecutionError(
                PlanStatus.DEPENDENCY_UNAVAILABLE,
                f"{identifier} unavailable: {status.reason}",
            )

    @staticmethod
    def grade(kind: str, identifier: str) -> str:
        capabilities = ALGORITHMS if kind == "algorithm" else TRACKERS
        return capabilities.get(identifier, Capability("G0", (), (), ())).readiness_grade
