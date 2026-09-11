"""Woerner-style COLREG compliance scoring for product campaign bundles.

Scores per-cell encounter behavior from a campaign run directory:
collision-avoidance success, rule compliance per encounter class, path
deviation efficiency and speed-profile admissibility, following the metric
families of Woerner et al. 2019 (Autonomous Robots 43(4):967-991) adapted to
the local bundle schema (see docs/research/2026-09-11-gnc-colav-integration-survey.md
section on metrics and the CRI-weighted engineering variants).

Encounter classes are reused from the planner event stream when present
(Kuwata VO rule labels, Potocnik fan-MPC encounter records); otherwise they
fall back to the scenario/validation-rule mapping and, for multi-target cells,
to a geometric classifier at detection time.

This module is a pure function of the bundle inputs: it reads only JSON and
Parquet artifacts and imports neither the simulator nor the network. Run it in
a clean interpreter (pyarrow here, no colav_simulator import) per the
Arrow/GDAL registry-conflict precedent (commit d40d786f).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

# ---------------------------------------------------------------------------
# Thresholds. Woerner 2019 leaves several quantities to scenario design; each
# non-derivable value below is an explicit local assumption (see report).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringThresholds:
    """Thresholds for encounter detection and compliance verdicts."""

    detection_range_m: float = 3000.0
    risk_threshold_m: float = 1000.0
    collision_threshold_m: float = 50.0
    alteration_threshold_rad: float = math.radians(10.0)
    alteration_sustain_samples: int = 3
    alteration_baseline_s: float = 10.0
    magnitude_window_after_cpa_s: float = 300.0
    in_extremis_tcpa_s: float = 120.0
    in_extremis_range_m: float = 500.0
    speed_reduction_compliant: float = 0.10
    cruise_window_s: float = 60.0
    path_ratio_good: float = 1.10
    path_ratio_partial: float = 1.25
    final_xte_good_m: float = 50.0


HEAD_ON = "HEAD_ON"
CROSSING_GIVE_WAY = "CROSSING_GIVE_WAY"
CROSSING_STAND_ON = "CROSSING_STAND_ON"
OVERTAKING = "OVERTAKING"

VO_LABELS = {
    "HO": HEAD_ON,
    "CR_SS": CROSSING_GIVE_WAY,
    "CR_PS": CROSSING_STAND_ON,
    "OT_ing": OVERTAKING,
    "OT_en": OVERTAKING,
}
POTOCNIK_LABELS = {
    "head_on": HEAD_ON,
    "crossing_give_way": CROSSING_GIVE_WAY,
    "crossing_stand_on": CROSSING_STAND_ON,
    "overtaking": OVERTAKING,
}
SCENARIO_CLASSES = {
    "head_on": HEAD_ON,
    "crossing_give_way": CROSSING_GIVE_WAY,
    "overtaking": OVERTAKING,
}
RULE_IDS = {
    HEAD_ON: "rule14",
    CROSSING_GIVE_WAY: "rule15+16",
    CROSSING_STAND_ON: "rule17",
    OVERTAKING: "rule13+16",
}
# Deterministic tie-break order for modal classification.
CLASS_PRIORITY = (HEAD_ON, CROSSING_GIVE_WAY, CROSSING_STAND_ON, OVERTAKING)

VERDICT_COMPLIANT = "COMPLIANT"
VERDICT_PARTIAL = "PARTIAL"
VERDICT_NON_COMPLIANT = "NON_COMPLIANT"
VERDICT_NOT_EVALUABLE = "NOT_EVALUABLE"


def wrap_angle(angle_rad: float) -> float:
    """Wrap an angle to (-pi, pi]."""
    wrapped = (angle_rad + math.pi) % (2.0 * math.pi) - math.pi
    return wrapped + 2.0 * math.pi if wrapped <= -math.pi else wrapped


# ---------------------------------------------------------------------------
# Trajectory loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Track:
    """Per-ship trajectory arrays sampled on a shared time base."""

    ship_id: int
    times_s: np.ndarray
    east_m: np.ndarray
    north_m: np.ndarray
    sog_mps: np.ndarray
    psi_rad: np.ndarray


def _track_from_rows(ship_id: int, rows: list[dict]) -> Track:
    rows = sorted(rows, key=lambda row: row["sim_time"])
    return Track(
        ship_id=ship_id,
        times_s=np.array([row["sim_time"] for row in rows], dtype=float),
        east_m=np.array([row["east_m"] for row in rows], dtype=float),
        north_m=np.array([row["north_m"] for row in rows], dtype=float),
        sog_mps=np.array([row["sog_mps"] for row in rows], dtype=float),
        psi_rad=np.array([row["psi_rad"] for row in rows], dtype=float),
    )


def load_tracks(run_dir: Path) -> tuple[Track, dict[int, Track], str | None]:
    """Load ownship and target tracks from trajectory.parquet."""
    columns = ["ship_id", "sim_time", "east_m", "north_m", "sog_mps", "psi_rad"]
    table = pq.read_table(run_dir / "trajectory.parquet", columns=columns)
    grouped: dict[int, list[dict]] = {}
    for row in table.to_pylist():
        grouped.setdefault(int(row["ship_id"]), []).append(row)
    ownship_id = min(grouped)
    ownship = _track_from_rows(ownship_id, grouped.pop(ownship_id))
    targets = {ship_id: _track_from_rows(ship_id, rows) for ship_id, rows in sorted(grouped.items())}
    waypoints = _nominal_route_from_rows(
        pq.read_table(run_dir / "trajectory.parquet", columns=["ship_id", "waypoints_json"]).to_pylist(),
        ownship_id,
    )
    return ownship, targets, waypoints


def _nominal_route_from_rows(rows: list[dict], ownship_id: int) -> str | None:
    for row in rows:
        if int(row["ship_id"]) == ownship_id and row.get("waypoints_json"):
            return row["waypoints_json"]
    return None


def parse_nominal_route(waypoints_json: str | None) -> np.ndarray | None:
    """Parse the ownship route into an (N, 2) polyline of east/north points."""
    if not waypoints_json:
        return None
    try:
        raw = json.loads(waypoints_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, list) or len(raw) != 2:
        return None
    norths, easts = raw
    if len(norths) < 2 or len(norths) != len(easts):
        return None
    # Bundle convention stores [[north_0, ..., north_T], [east_0, ..., east_T]].
    if abs(norths[0]) > abs(easts[0]):
        pairs = zip(easts, norths, strict=True)
    else:
        # Magnitude heuristic failed: the first list is already eastings.
        pairs = zip(norths, easts, strict=True)
    return np.array([(float(east), float(north)) for east, north in pairs])


# ---------------------------------------------------------------------------
# Path deviation metrics
# ---------------------------------------------------------------------------


def path_metrics(ownship: Track, route: np.ndarray | None) -> dict:
    """Path length ratio and cross-track extent against the nominal route polyline."""
    delta_e = np.diff(ownship.east_m)
    delta_n = np.diff(ownship.north_m)
    path_length_m = float(np.hypot(delta_e, delta_n).sum())
    if route is None:
        return {
            "path_ratio": None,
            "nominal_length_m": None,
            "path_length_m": path_length_m,
            "max_xte_m": None,
            "final_xte_m": None,
        }
    nominal_length_m = float(np.hypot(*np.diff(route, axis=0).T).sum())
    cross_track = np.full(len(ownship.times_s), np.inf)
    for start, end in zip(route[:-1], route[1:], strict=True):
        segment = end - start
        segment_norm_sq = float(segment @ segment)
        points = np.stack([ownship.east_m, ownship.north_m], axis=1) - start
        fractions = np.clip((points @ segment) / segment_norm_sq, 0.0, 1.0)
        projections = fractions[:, None] * segment[None, :]
        leg_xte = np.hypot(points[:, 0] - projections[:, 0], points[:, 1] - projections[:, 1])
        cross_track = np.minimum(cross_track, leg_xte)
    return {
        "path_ratio": path_length_m / nominal_length_m if nominal_length_m > 0.0 else None,
        "nominal_length_m": nominal_length_m,
        "path_length_m": path_length_m,
        "max_xte_m": float(cross_track.max()),
        "final_xte_m": float(cross_track[-1]),
    }


# ---------------------------------------------------------------------------
# Encounter classification (reuse planner events, then scenario, then geometry)
# ---------------------------------------------------------------------------


def _modal_class(counter: Counter) -> str | None:
    if not counter:
        return None
    best = max(counter.values())
    candidates = sorted(name for name, count in counter.items() if count == best)
    for klass in CLASS_PRIORITY:
        if klass in candidates:
            return klass
    return candidates[0]


def classify_from_events(events: list[dict]) -> tuple[dict[int, tuple[str, str]], dict[int, float]]:
    """Reuse planner encounter labels and threat detection times from events."""
    label_counters: dict[int, Counter] = {}
    detection_times: dict[int, float] = {}
    for event in events:
        event_type = event.get("type")
        details = event.get("details") or {}
        if event_type == "threat_entered":
            target_id = details.get("target_id")
            if target_id is not None:
                target_id = int(target_id)
                if target_id not in detection_times:
                    detection_times[target_id] = float(event.get("sim_time", 0.0))
        if event_type != "planner_solved":
            continue
        algorithm_details = (details.get("planner") or {}).get("algorithm_details") or {}
        active_rules = algorithm_details.get("active_rules")
        if isinstance(active_rules, dict):
            for target_key, labels in active_rules.items():
                counter = label_counters.setdefault(int(target_key), Counter())
                for label in labels or []:
                    mapped = VO_LABELS.get(label)
                    if mapped is not None:
                        counter[mapped] += 1
        for record in algorithm_details.get("encounter_records") or []:
            mapped = POTOCNIK_LABELS.get(record.get("encounter"))
            if mapped is not None:
                target_id = int(record["target_id"])
                label_counters.setdefault(target_id, Counter())[mapped] += 1
    classified = {
        target_id: (_modal_class(counter), "planner_events") for target_id, counter in sorted(label_counters.items())
    }
    return {tid: entry for tid, entry in classified.items() if entry[0] is not None}, detection_times


def classify_geometry(ownship: Track, target: Track, index: int) -> str:
    """Geometric COLREG classification at one sample (detection time)."""
    relative_e = target.east_m[index] - ownship.east_m[index]
    relative_n = target.north_m[index] - ownship.north_m[index]
    bearing_rad = math.atan2(relative_e, relative_n)
    relative_bearing = wrap_angle(bearing_rad - ownship.psi_rad[index])
    heading_delta = wrap_angle(target.psi_rad[index] - ownship.psi_rad[index])
    ahead = abs(relative_bearing) <= math.radians(67.5)
    if ahead and abs(heading_delta) >= math.radians(150.0):
        return HEAD_ON
    if abs(heading_delta) <= math.radians(30.0):
        if ahead:
            return OVERTAKING
        if abs(relative_bearing) >= math.radians(112.5):
            return CROSSING_STAND_ON  # target overtaking ownship: overtaken vessel holds
    if 0.0 < relative_bearing <= math.radians(112.5):
        return CROSSING_GIVE_WAY
    return CROSSING_STAND_ON


def expected_class_from_scenario(scenario_id: str | None, validation_rule_id: str | None) -> str | None:
    """Fallback mapping from the cell scenario spec."""
    if scenario_id in SCENARIO_CLASSES:
        return SCENARIO_CLASSES[scenario_id]
    rule_map = {"rule14": HEAD_ON, "rule15": CROSSING_GIVE_WAY, "rule17": CROSSING_STAND_ON, "rule13": OVERTAKING}
    return rule_map.get(validation_rule_id or "")


# ---------------------------------------------------------------------------
# Encounter kinematics
# ---------------------------------------------------------------------------


def _index_at_time(track: Track, time_s: float) -> int:
    return int(np.searchsorted(track.times_s, time_s, side="left"))


def _velocity(track: Track, index: int) -> tuple[float, float]:
    lo = max(index - 3, 0)
    hi = min(index + 4, len(track.times_s))
    if hi - lo < 2:
        return 0.0, 0.0
    window = slice(lo, hi)
    dt = track.times_s[window] - track.times_s[index]
    ve = float(np.sum((track.east_m[window] - track.east_m[index]) * dt) / np.sum(dt * dt))
    vn = float(np.sum((track.north_m[window] - track.north_m[index]) * dt) / np.sum(dt * dt))
    return ve, vn


def cpa_estimate(ownship: Track, target: Track, index: int) -> tuple[float, float]:
    """Constant-velocity DCPA (m) and TCPA (s) from the state at one index."""
    relative_e = target.east_m[index] - ownship.east_m[index]
    relative_n = target.north_m[index] - ownship.north_m[index]
    ve_own, vn_own = _velocity(ownship, index)
    ve_t, vn_t = _velocity(target, index)
    ve = ve_t - ve_own
    vn = vn_t - vn_own
    speed_sq = ve * ve + vn * vn
    if speed_sq <= 1.0e-9:
        return math.hypot(relative_e, relative_n), math.inf
    tcpa = -(relative_e * ve + relative_n * vn) / speed_sq
    dcpa = math.hypot(relative_e + ve * tcpa, relative_n + vn * tcpa)
    return dcpa, tcpa


def range_series(ownship: Track, target: Track) -> np.ndarray:
    """Center-to-center range (m) between ownship and one target over time."""
    return np.hypot(ownship.east_m - target.east_m, ownship.north_m - target.north_m)


def first_alteration(ownship: Track, index_detect: int, thresholds: ScoringThresholds) -> dict:
    """First sustained course alteration after detection (heading baseline)."""
    n = len(ownship.times_s)
    baseline_end = min(n, index_detect + max(1, int(round(thresholds.alteration_baseline_s / _median_dt(ownship)))))
    baseline_lo = max(0, index_detect)
    window = ownship.psi_rad[baseline_lo:baseline_end]
    # Circular mean: headings live on the circle and may straddle +/-pi.
    baseline = float(math.atan2(float(np.sin(window).mean()), float(np.cos(window).mean())))
    sustain = thresholds.alteration_sustain_samples
    for index in range(index_detect, n - sustain + 1):
        deviation = wrap_angle(ownship.psi_rad[index] - baseline)
        if abs(deviation) < thresholds.alteration_threshold_rad:
            continue
        window = ownship.psi_rad[index : index + sustain]
        if np.all(np.abs(_wrap_array(window - baseline)) >= thresholds.alteration_threshold_rad * 0.5):
            direction = "starboard" if deviation > 0.0 else "port"
            return {
                "index": index,
                "time_s": float(ownship.times_s[index]),
                "direction": direction,
                "deviation_rad": float(deviation),
                "baseline_rad": baseline,
                "sustained": True,
            }
    final_deviation = wrap_angle(float(ownship.psi_rad[-1]) - baseline)
    return {
        "index": None,
        "time_s": None,
        "direction": "starboard" if final_deviation > 0.0 else "port",
        "deviation_rad": float(final_deviation),
        "baseline_rad": baseline,
        "sustained": False,
    }


def _wrap_array(values: np.ndarray) -> np.ndarray:
    wrapped = (values + math.pi) % (2.0 * math.pi) - math.pi
    return wrapped


def _median_dt(track: Track) -> float:
    if len(track.times_s) < 2:
        return 1.0
    return float(np.median(np.diff(track.times_s)))


# ---------------------------------------------------------------------------
# Encounter scoring
# ---------------------------------------------------------------------------


@dataclass
class EncounterScore:
    """One target's scored encounter, with trajectory-index evidence."""

    target_id: int
    encounter_class: str | None
    classification_source: str
    role: str
    rule_id: str | None
    detected_time_s: float | None
    detection_index: int | None
    dcpa_at_detection_m: float | None
    tcpa_at_detection_s: float | None
    min_distance_m: float | None
    min_distance_time_s: float | None
    min_distance_index: int | None
    release_time_s: float | None
    release_before_cpa: bool
    first_alteration_time_s: float | None
    first_alteration_direction: str | None
    first_alteration_magnitude_deg: float | None
    first_alteration_index: int | None
    astern_pass: bool | None
    pass_completed: bool | None
    cruise_speed_mps: float | None
    min_speed_mps: float | None
    speed_reduction_fraction: float | None
    reversed: bool
    collision_avoidance_ok: bool | None
    verdict: str
    reason: str
    incomplete: bool = False
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(vars(self))


def _role_for(encounter_class: str, geometry_role: str | None = None) -> str:
    if geometry_role is not None:
        return geometry_role
    if encounter_class == CROSSING_STAND_ON:
        return "stand_on"
    return "give_way"


def score_encounter(
    ownship: Track,
    target: Track,
    encounter_class: str | None,
    classification_source: str,
    detection_time_s: float | None,
    release_time_s: float | None,
    thresholds: ScoringThresholds,
) -> EncounterScore:
    """Score one ownship-target encounter from raw tracks."""
    ranges = range_series(ownship, target)
    if detection_time_s is not None:
        index_detect = _index_at_time(ownship, detection_time_s)
    else:
        close = np.nonzero(ranges <= thresholds.detection_range_m)[0]
        index_detect = int(close[0]) if close.size else 0
        detection_time_s = float(ownship.times_s[index_detect])
    # The encounter is scored over the full post-detection window. Lifecycle
    # release events are recorded as evidence but do not clip the window:
    # multiship runs have released targets before their true CPA.
    index_release = len(ownship.times_s) - 1
    release_time_observed_s = float(release_time_s) if release_time_s is not None else None
    release_index = _index_at_time(ownship, release_time_s) if release_time_s is not None else None
    cpa_index = index_detect + int(np.argmin(ranges[index_detect:]))
    release_before_cpa = bool(release_index is not None and release_index < cpa_index)

    window = ranges[index_detect:]
    min_distance_m = float(window.min())
    min_distance_index = index_detect + int(window.argmin())
    min_distance_time_s = float(ownship.times_s[min_distance_index])
    dcpa_detect, tcpa_detect = cpa_estimate(ownship, target, index_detect)
    incomplete = min_distance_index >= len(ownship.times_s) - 1

    alteration = first_alteration(ownship, index_detect, thresholds)
    magnitude_index_end = min(
        len(ownship.times_s) - 1,
        min_distance_index + int(round(thresholds.magnitude_window_after_cpa_s / _median_dt(ownship))),
    )
    magnitude_deg, first_alteration_direction, first_alteration_time_s, first_alteration_index = _alteration_summary(
        ownship, alteration, magnitude_index_end
    )

    relative_bearing_at_cpa = wrap_angle(
        float(
            math.atan2(
                target.east_m[min_distance_index] - ownship.east_m[min_distance_index],
                target.north_m[min_distance_index] - ownship.north_m[min_distance_index],
            )
            - float(ownship.psi_rad[min_distance_index])
        )
    )
    astern_pass = bool(abs(relative_bearing_at_cpa) <= math.pi / 2.0)

    cruise_speed_mps, min_speed_mps, speed_reduction_fraction, reversed_speed = _speed_profile(
        ownship, index_detect, index_release, thresholds
    )

    pass_completed = None
    if encounter_class == OVERTAKING:
        final_bearing = wrap_angle(
            float(
                math.atan2(
                    target.east_m[-1] - ownship.east_m[-1],
                    target.north_m[-1] - ownship.north_m[-1],
                )
                - float(ownship.psi_rad[-1])
            )
        )
        pass_completed = bool(abs(final_bearing) > math.pi / 2.0)

    collision_avoidance_ok = min_distance_m >= thresholds.collision_threshold_m
    role = _role_for(encounter_class) if encounter_class else "unknown"
    evidence = (
        f"min_dist={min_distance_m:.1f}m@t={min_distance_time_s:.1f}s(idx {min_distance_index}); "
        f"detect t={detection_time_s:.1f}s(idx {index_detect}); "
        f"dcpa_detect={dcpa_detect:.1f}m/tcpa={tcpa_detect:.1f}s; "
        f"alt(idx {first_alteration_index if first_alteration_index is not None else 'none'})"
    )
    if release_before_cpa:
        evidence += f"; lifecycle release t={release_time_observed_s:.1f}s before CPA"
    if first_alteration_index is not None and first_alteration_index > min_distance_index:
        evidence += f"; post-CPA course change at idx {first_alteration_index} treated as recovery"
    if encounter_class is None:
        encounter_class = classify_geometry(ownship, target, index_detect)
        classification_source = "geometry"

    verdict, reason, role = _rule_verdict(
        encounter_class=encounter_class,
        dcpa_detect=dcpa_detect,
        min_distance_m=min_distance_m,
        min_distance_index=min_distance_index,
        alteration_index=first_alteration_index,
        alteration_direction=first_alteration_direction,
        alteration_magnitude_deg=magnitude_deg,
        alteration=alteration,
        ownship=ownship,
        target=target,
        index_detect=index_detect,
        index_release=index_release,
        thresholds=thresholds,
        speed_reduction_fraction=speed_reduction_fraction,
        collision_avoidance_ok=collision_avoidance_ok,
        pass_completed=pass_completed,
        incomplete=incomplete,
        evidence=evidence,
        astern_pass=astern_pass,
    )
    if verdict == VERDICT_COMPLIANT and incomplete and encounter_class != OVERTAKING:
        verdict = VERDICT_PARTIAL
        reason += "; encounter unresolved: min distance at run end"
    return EncounterScore(
        target_id=int(target.ship_id),
        encounter_class=encounter_class,
        classification_source=classification_source,
        role=role,
        rule_id=RULE_IDS.get(encounter_class),
        detected_time_s=float(detection_time_s),
        detection_index=int(index_detect),
        dcpa_at_detection_m=float(dcpa_detect),
        tcpa_at_detection_s=(None if math.isinf(tcpa_detect) else float(tcpa_detect)),
        min_distance_m=min_distance_m,
        min_distance_time_s=min_distance_time_s,
        min_distance_index=int(min_distance_index),
        release_time_s=release_time_observed_s,
        release_before_cpa=release_before_cpa,
        first_alteration_time_s=first_alteration_time_s,
        first_alteration_direction=first_alteration_direction,
        first_alteration_magnitude_deg=magnitude_deg,
        first_alteration_index=first_alteration_index,
        astern_pass=astern_pass,
        pass_completed=pass_completed,
        cruise_speed_mps=cruise_speed_mps,
        min_speed_mps=min_speed_mps,
        speed_reduction_fraction=float(speed_reduction_fraction),
        reversed=reversed_speed,
        collision_avoidance_ok=collision_avoidance_ok,
        verdict=verdict,
        reason=reason,
        incomplete=incomplete,
    )


def _alteration_summary(
    ownship: Track, alteration: dict, magnitude_index_end: int
) -> tuple[float | None, str | None, float | None, int | None]:
    """Observed first-alteration magnitude/direction, or all-None when absent."""
    if alteration["index"] is None:
        return None, None, None, None
    window = ownship.psi_rad[alteration["index"] : magnitude_index_end + 1]
    deviations = np.abs(_wrap_array(window - alteration["baseline_rad"]))
    magnitude_deg = math.degrees(float(deviations.max()))
    return magnitude_deg, alteration["direction"], alteration["time_s"], alteration["index"]


def _speed_profile(
    ownship: Track, index_detect: int, index_release: int, thresholds: ScoringThresholds
) -> tuple[float, float, float, bool]:
    """Cruise speed, encounter minimum, reduction fraction, and reversing flag."""
    cruise_end = _index_at_time(ownship, ownship.times_s[0] + thresholds.cruise_window_s)
    cruise_end = max(cruise_end, index_detect, 1)
    cruise_speed_mps = float(np.median(ownship.sog_mps[:cruise_end]))
    encounter_speeds = ownship.sog_mps[index_detect : index_release + 1]
    min_speed_mps = float(encounter_speeds.min()) if encounter_speeds.size else float(ownship.sog_mps[-1])
    reduction = max(0.0, 1.0 - min_speed_mps / cruise_speed_mps) if cruise_speed_mps > 0.1 else 0.0
    reversed_speed = bool((encounter_speeds < 0.0).any()) if encounter_speeds.size else False
    return cruise_speed_mps, min_speed_mps, reduction, reversed_speed


def _rule_verdict(
    *,
    encounter_class: str,
    dcpa_detect: float,
    min_distance_m: float,
    min_distance_index: int,
    alteration_index: int | None,
    alteration_direction: str | None,
    alteration_magnitude_deg: float | None,
    alteration: dict,
    ownship: Track,
    target: Track,
    index_detect: int,
    index_release: int,
    thresholds: ScoringThresholds,
    speed_reduction_fraction: float,
    collision_avoidance_ok: bool,
    pass_completed: bool | None,
    incomplete: bool,
    evidence: str,
    astern_pass: bool,
) -> tuple[str, str, str]:
    """Map encounter-class obligations onto the observed alteration evidence."""
    # Only a course change on approach (at or before CPA) counts as the
    # avoidance action; post-CPA course changes are recovery legs.
    if alteration_index is not None and alteration_index > min_distance_index:
        alteration_index = None
        alteration_direction = None
    if encounter_class == HEAD_ON:
        return _verdict_head_on(
            dcpa_detect=dcpa_detect,
            min_distance_m=min_distance_m,
            alteration_index=alteration_index,
            alteration_direction=alteration_direction,
            alteration=alteration,
            alteration_magnitude_deg=alteration_magnitude_deg,
            collision_avoidance_ok=collision_avoidance_ok,
            thresholds=thresholds,
            evidence=evidence,
        )
    if encounter_class == CROSSING_GIVE_WAY:
        return _verdict_crossing_give_way(
            dcpa_detect=dcpa_detect,
            alteration_index=alteration_index,
            alteration_direction=alteration_direction,
            alteration=alteration,
            alteration_magnitude_deg=alteration_magnitude_deg,
            astern_pass=astern_pass,
            min_distance_m=min_distance_m,
            speed_reduction_fraction=speed_reduction_fraction,
            thresholds=thresholds,
            evidence=evidence,
        )
    if encounter_class == CROSSING_STAND_ON:
        return _verdict_crossing_stand_on(
            ownship=ownship,
            target=target,
            index_detect=index_detect,
            index_release=index_release,
            alteration_index=alteration_index,
            alteration=alteration,
            collision_avoidance_ok=collision_avoidance_ok,
            thresholds=thresholds,
            evidence=evidence,
        )
    if encounter_class == OVERTAKING:
        return _verdict_overtaking(
            collision_avoidance_ok=collision_avoidance_ok,
            pass_completed=pass_completed,
            incomplete=incomplete,
            alteration=alteration,
            alteration_magnitude_deg=alteration_magnitude_deg,
            evidence=evidence,
        )
    return VERDICT_NOT_EVALUABLE, f"unclassified encounter; {evidence}", "unknown"


def _alteration_text(alteration: dict, alteration_magnitude_deg: float | None) -> str:
    """One-clause description of the observed first alteration."""
    if alteration["index"] is None:
        return "no sustained alteration"
    return f"first alteration {alteration['direction']} {alteration_magnitude_deg:.1f}deg at t={alteration['time_s']:.1f}s"


def _verdict_head_on(
    *,
    dcpa_detect: float,
    min_distance_m: float,
    alteration_index: int | None,
    alteration_direction: str | None,
    alteration: dict,
    alteration_magnitude_deg: float | None,
    collision_avoidance_ok: bool,
    thresholds: ScoringThresholds,
    evidence: str,
) -> tuple[str, str, str]:
    """Rule 14: head-on vessels alter to starboard so each passes port side to port side.

    COLREG Rule 14 is explicit ("each shall alter her course to starboard"); the
    scorer therefore reads a port turn as non-compliant and a starboard turn as
    the compliant port-to-port pass.
    """
    alter = _alteration_text(alteration, alteration_magnitude_deg)
    action_required = dcpa_detect < thresholds.risk_threshold_m or min_distance_m < thresholds.risk_threshold_m
    if not action_required:
        note = f"no action required (predicted DCPA {dcpa_detect:.1f}m, min {min_distance_m:.1f}m); {evidence}"
        return VERDICT_COMPLIANT, note, "give_way"
    if alteration_index is None:
        state = "unsafe CPA" if not collision_avoidance_ok else "close-quarters pass"
        return (
            VERDICT_NON_COMPLIANT,
            f"head-on risk without starboard alteration ({alter}, {state}); {evidence}",
            "give_way",
        )
    if alteration_direction == "starboard":
        return VERDICT_COMPLIANT, f"head-on starboard alteration, port-to-port pass ({alter}); {evidence}", "give_way"
    return (
        VERDICT_NON_COMPLIANT,
        f"head-on alteration to port, Rule 14 expects starboard ({alter}); {evidence}",
        "give_way",
    )


def _verdict_crossing_give_way(
    *,
    dcpa_detect: float,
    alteration_index: int | None,
    alteration_direction: str | None,
    alteration: dict,
    alteration_magnitude_deg: float | None,
    astern_pass: bool,
    min_distance_m: float,
    speed_reduction_fraction: float,
    thresholds: ScoringThresholds,
    evidence: str,
) -> tuple[str, str, str]:
    """Rule 15/16: give-way keeps clear - starboard alteration or speed reduction, astern pass preferred."""
    alter = _alteration_text(alteration, alteration_magnitude_deg)
    action_required = dcpa_detect < thresholds.risk_threshold_m or min_distance_m < thresholds.risk_threshold_m
    if not action_required:
        note = f"no action required (predicted DCPA {dcpa_detect:.1f}m, min {min_distance_m:.1f}m); {evidence}"
        return VERDICT_COMPLIANT, note, "give_way"
    if alteration_index is not None and alteration_direction == "port":
        return (
            VERDICT_NON_COMPLIANT,
            f"give-way alteration to port, Rule 15 expects starboard or speed reduction ({alter}); {evidence}",
            "give_way",
        )
    if alteration_index is not None and alteration_direction == "starboard":
        verdict = VERDICT_COMPLIANT
        note = f"give-way starboard alteration ({alter}); astern_pass={astern_pass}; {evidence}"
    elif speed_reduction_fraction >= thresholds.speed_reduction_compliant:
        verdict = VERDICT_COMPLIANT
        note = (
            f"give-way action by speed reduction {speed_reduction_fraction:.0%} ({alter});"
            f" astern_pass={astern_pass}; {evidence}"
        )
    else:
        return (
            VERDICT_NON_COMPLIANT,
            f"give-way risk without admissible action ({alter}, speed reduction {speed_reduction_fraction:.0%}); {evidence}",
            "give_way",
        )
    if verdict == VERDICT_COMPLIANT and not astern_pass and min_distance_m < thresholds.risk_threshold_m:
        return VERDICT_PARTIAL, f"compliant action but head-on-side pass (astern_pass=false); {note}", "give_way"
    return verdict, note, "give_way"


def _verdict_crossing_stand_on(
    *,
    ownship: Track,
    target: Track,
    index_detect: int,
    index_release: int,
    alteration_index: int | None,
    alteration: dict,
    collision_avoidance_ok: bool,
    thresholds: ScoringThresholds,
    evidence: str,
) -> tuple[str, str, str]:
    """Rule 17: stand-on holds course/speed until in-extremis, then may act."""
    extremis_index = _in_extremis_index(ownship, target, index_detect, index_release, thresholds)
    extremis_time = float(ownship.times_s[extremis_index]) if extremis_index is not None else None
    extremis_text = "in-extremis not reached" if extremis_time is None else f"in-extremis from t={extremis_time:.1f}s"
    if alteration_index is None:
        if collision_avoidance_ok:
            return VERDICT_COMPLIANT, f"stand-on held course/speed ({extremis_text}); {evidence}", "stand_on"
        return (
            VERDICT_NON_COMPLIANT,
            f"stand-on held into unsafe CPA without in-extremis action ({extremis_text}); {evidence}",
            "stand_on",
        )
    if extremis_index is not None and alteration_index >= extremis_index:
        return (
            VERDICT_COMPLIANT,
            f"stand-on acted at in-extremis (alt t={alteration['time_s']:.1f}s >= {extremis_time:.1f}s); {evidence}",
            "stand_on",
        )
    return (
        VERDICT_NON_COMPLIANT,
        f"stand-on altered before in-extremis (alt t={alteration['time_s']:.1f}s, {extremis_text}); {evidence}",
        "stand_on",
    )


def _verdict_overtaking(
    *,
    collision_avoidance_ok: bool,
    pass_completed: bool | None,
    incomplete: bool,
    alteration: dict,
    alteration_magnitude_deg: float | None,
    evidence: str,
) -> tuple[str, str, str]:
    """Rule 13/16: the overtaking vessel keeps clear; either side is admissible."""
    alter = _alteration_text(alteration, alteration_magnitude_deg)
    if not collision_avoidance_ok:
        return VERDICT_NON_COMPLIANT, f"overtaking with unsafe CPA ({alter}); {evidence}", "give_way"
    if pass_completed is None:
        return VERDICT_NOT_EVALUABLE, f"overtaking pass completion not observable; {evidence}", "give_way"
    if not pass_completed:
        if incomplete:
            return VERDICT_NOT_EVALUABLE, f"run ended before pass completion; {evidence}", "give_way"
        return VERDICT_PARTIAL, f"clearance kept but pass not completed by run end ({alter}); {evidence}", "give_way"
    return VERDICT_COMPLIANT, f"overtaking completed with clearance ({alter}); {evidence}", "give_way"


def _in_extremis_index(
    ownship: Track, target: Track, index_detect: int, index_release: int, thresholds: ScoringThresholds
) -> int | None:
    """First index where TCPA <= threshold or range <= threshold (in-extremis)."""
    dt = _median_dt(ownship)
    for index in range(index_detect, index_release + 1, max(1, int(round(2.0 * dt)))):
        _, tcpa = cpa_estimate(ownship, target, index)
        if abs(tcpa) <= thresholds.in_extremis_tcpa_s:
            return index
        if float(range_series(ownship, target)[index]) <= thresholds.in_extremis_range_m:
            return index
    return None


# ---------------------------------------------------------------------------
# Cell scoring
# ---------------------------------------------------------------------------


def score_cell(
    ownship: Track,
    targets: dict[int, Track],
    *,
    scenario_id: str | None,
    validation_rule_id: str | None,
    events: list[dict] | None = None,
    waypoints_json: str | None = None,
    release_times_s: dict[int, float] | None = None,
    thresholds: ScoringThresholds | None = None,
) -> dict:
    """Pure per-cell scoring: classification, per-encounter records, summary."""
    thresholds = thresholds or ScoringThresholds()
    release_times_s = release_times_s or {}
    event_classes, detection_times = classify_from_events(events or [])
    scenario_expected = expected_class_from_scenario(scenario_id, validation_rule_id)
    multi_target = len(targets) > 1

    encounters: list[EncounterScore] = []
    for target_id, target in targets.items():
        ranges = range_series(ownship, target)
        min_range = float(ranges.min())
        if target_id in event_classes:
            klass, source = event_classes[target_id]
        elif multi_target:
            if min_range > thresholds.risk_threshold_m:
                continue
            klass, source = None, "geometry"
        else:
            klass, source = scenario_expected, "scenario_fallback" if scenario_expected else "geometry"
        detection_time_s = detection_times.get(target_id)
        if detection_time_s is None and klass is None and source == "geometry":
            close = np.nonzero(ranges <= thresholds.detection_range_m)[0]
            detection_time_s = float(ownship.times_s[close[0]]) if close.size else float(ownship.times_s[0])
        encounters.append(
            score_encounter(
                ownship,
                target,
                klass,
                source,
                detection_time_s,
                release_times_s.get(target_id),
                thresholds,
            )
        )

    route = parse_nominal_route(waypoints_json)
    metrics = path_metrics(ownship, route)

    min_distances = [enc.min_distance_m for enc in encounters if enc.min_distance_m is not None]
    safety_ok = all(dist >= thresholds.collision_threshold_m for dist in min_distances) if min_distances else None
    safety_score = _safety_score(min_distances, thresholds)
    rule_score = _rule_score(encounters)
    mission_score = _mission_score(metrics, thresholds)
    summary = {
        "encounter_count": len(encounters),
        "collision_avoidance_ok": safety_ok,
        "min_distance_m": min(min_distances) if min_distances else None,
        "safety_score": safety_score,
        "rule_score": rule_score,
        "mission_score": mission_score,
        "composite_score": round((safety_score + rule_score + mission_score) / 3.0, 3),
        "any_reversing": any(enc.reversed for enc in encounters),
        "max_speed_reduction_fraction": max((enc.speed_reduction_fraction for enc in encounters), default=None),
    }
    return {
        "encounters": encounters,
        "path": metrics,
        "summary": summary,
        "thresholds": vars(thresholds),
    }


def _safety_score(min_distances: list[float], thresholds: ScoringThresholds) -> float:
    if not min_distances:
        return 0.0
    worst = min(min_distances)
    if worst >= thresholds.collision_threshold_m:
        return 1.0
    if worst >= thresholds.collision_threshold_m / 2.0:
        return 0.5
    return 0.0


def _rule_score(encounters: list[EncounterScore]) -> float:
    if not encounters:
        return 0.0
    verdicts = [enc.verdict for enc in encounters]
    if VERDICT_NON_COMPLIANT in verdicts:
        return 0.0
    if VERDICT_NOT_EVALUABLE in verdicts or VERDICT_PARTIAL in verdicts:
        return 0.5
    return 1.0


def _mission_score(metrics: dict, thresholds: ScoringThresholds) -> float:
    ratio = metrics.get("path_ratio")
    if ratio is None:
        return 0.0
    final_xte = metrics.get("final_xte_m") or 0.0
    if ratio <= thresholds.path_ratio_good and final_xte <= thresholds.final_xte_good_m:
        return 1.0
    if ratio <= thresholds.path_ratio_partial:
        return 0.5
    return 0.0


# ---------------------------------------------------------------------------
# Bundle I/O
# ---------------------------------------------------------------------------


def load_events(run_dir: Path) -> list[dict]:
    """Parse events.jsonl into a list of event dicts (empty when absent)."""
    events_path = run_dir / "events.jsonl"
    if not events_path.exists():
        return []
    events = []
    for raw_line in events_path.read_text().splitlines():
        stripped = raw_line.strip()
        if stripped:
            events.append(json.loads(stripped))
    return events


def load_lifecycle_releases(run_dir: Path) -> dict[int, float]:
    """Target release times from lifecycle_events.jsonl (PAST_CLEAR/RELEASED)."""
    path = run_dir / "lifecycle_events.jsonl"
    if not path.exists():
        return {}
    releases: dict[int, float] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        to_state = event.get("to_state") or ""
        if to_state.startswith("PAST_CLEAR") or to_state.startswith("RELEASED"):
            key = event.get("target_key") or {}
            target_id = key.get("target_id")
            if target_id is not None:
                releases[int(target_id)] = float(event.get("sim_time_s", 0.0))
    return releases


def score_run_dir(run_dir: Path, case_meta: dict, thresholds: ScoringThresholds | None = None) -> dict:
    """Score one cell run directory into the JSON-serializable record."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    ownship, targets, waypoints_json = load_tracks(run_dir)
    events = load_events(run_dir)
    releases = load_lifecycle_releases(run_dir)
    spec = manifest.get("spec") or {}
    scenario_id = spec.get("scenario_id") or case_meta.get("scenario_id")
    validation_rule_id = spec.get("validation_rule_id") or case_meta.get("validation_rule_id")
    scoring = score_cell(
        ownship,
        targets,
        scenario_id=scenario_id,
        validation_rule_id=validation_rule_id,
        events=events,
        waypoints_json=waypoints_json,
        release_times_s=releases,
        thresholds=thresholds,
    )
    evaluation_path = run_dir / "evaluation.json"
    evaluation_min_distance = None
    evaluation_gate = None
    if evaluation_path.exists():
        evaluation = json.loads(evaluation_path.read_text())
        evaluation_gate = (evaluation.get("hard_gate") or {}).get("outcome")
        evaluation_min_distance = (evaluation.get("aggregate") or {}).get("minimum_distance_m")

    record = {
        "case_id": case_meta.get("case_id") or run_dir.parent.name,
        "algorithm_id": spec.get("algorithm_id") or case_meta.get("algorithm_id"),
        "scenario_id": scenario_id,
        "validation_rule_id": validation_rule_id,
        "episode_index": spec.get("episode_index"),
        "run_id": manifest.get("run_id"),
        "run_state": manifest.get("state"),
        "execution_outcome": manifest.get("execution_outcome"),
        "failure_reason": manifest.get("failure_reason"),
        "evaluation_gate": evaluation_gate,
        "evaluation_min_distance_m": evaluation_min_distance,
        "t_end_s": float(ownship.times_s[-1]),
        "sample_count": int(len(ownship.times_s)),
        "target_count": len(targets),
        "path": scoring["path"],
        "summary": scoring["summary"],
        "thresholds": scoring["thresholds"],
        "encounters": [enc.to_dict() for enc in scoring["encounters"]],
    }
    return record


def discover_cells(bundle_dir: Path) -> list[dict]:
    """Enumerate case records from a campaign bundle directory."""
    cells = []
    for cell_path in sorted(Path(bundle_dir).glob("*.json")):
        payload = json.loads(cell_path.read_text())
        if not isinstance(payload, dict) or "run_dir" not in payload:
            continue
        cells.append(payload)
    return cells


def score_bundle(bundle_dir: Path, thresholds: ScoringThresholds | None = None) -> dict:
    """Score every cell of one campaign bundle."""
    cells = [score_run_dir(cell["run_dir"], cell, thresholds) for cell in discover_cells(bundle_dir)]
    return {
        "bundle": str(bundle_dir),
        "cell_count": len(cells),
        "cells": cells,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _fmt(value: object, digits: int = 1, suffix: str = "") -> str:
    """Compact deterministic cell rendering for markdown tables."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return str(value)


def render_cell_markdown(cell: dict) -> str:
    """Per-cell markdown section with the per-encounter evidence table."""
    lines = [
        f"### {cell['case_id']}",
        "",
        f"- run: state={cell['run_state']} outcome={cell['execution_outcome']} gate={cell['evaluation_gate']}"
        f" t_end={_fmt(cell['t_end_s'])}s targets={cell['target_count']}",
        f"- path: ratio={_fmt(cell['path']['path_ratio'], 3)} max_xte={_fmt(cell['path']['max_xte_m'])}m"
        f" final_xte={_fmt(cell['path']['final_xte_m'])}m",
        f"- scores: safety={cell['summary']['safety_score']} rule={cell['summary']['rule_score']}"
        f" mission={cell['summary']['mission_score']} composite={cell['summary']['composite_score']}",
        "",
        "| tgt | class | src | detect t | dcpa | min_dist | alt | mag | verdict | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for enc in cell["encounters"]:
        alt_text = (
            "-"
            if enc["first_alteration_time_s"] is None
            else f"{enc['first_alteration_direction']}@{_fmt(enc['first_alteration_time_s'])}s"
        )
        lines.append(
            "| {tgt} | {klass} | {src} | {detect} | {dcpa} | {mind} | {alt} | {mag} | {verdict} | {reason} |".format(
                tgt=enc["target_id"],
                klass=enc["encounter_class"] or "-",
                src=enc["classification_source"],
                detect=_fmt(enc["detected_time_s"]),
                dcpa=_fmt(enc["dcpa_at_detection_m"]),
                mind=_fmt(enc["min_distance_m"]),
                alt=alt_text,
                mag=_fmt(enc["first_alteration_magnitude_deg"]),
                verdict=enc["verdict"],
                reason=enc["reason"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_bundle_markdown(bundle: dict) -> str:
    """Cross-cell markdown table plus per-cell evidence sections."""
    lines = [
        f"# COLREG compliance scoring - {Path(bundle['bundle']).name}",
        "",
        "Woerner-style per-encounter scoring (safety / rule / mission, composite = mean).",
        "",
        "| cell | alg | scenario | ep | state | gate | enc | classes | min_dist | verdicts "
        "| S_safe | S_rule | S_mission | S_comp | ratio | XTE |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cell in bundle["cells"]:
        classes = ",".join(f"{enc['target_id']}:{enc['encounter_class'] or '?'}" for enc in cell["encounters"]) or "-"
        verdicts = ",".join(f"{enc['target_id']}:{enc['verdict']}" for enc in cell["encounters"]) or "-"
        row = (
            "| {cell} | {alg} | {scen} | {ep} | {state} | {gate} | {n} | {classes} "
            "| {mind} | {verdicts} | {ss} | {sr} | {sm} | {sc} | {ratio} | {xte} |"
        ).format(
            cell=cell["case_id"],
            alg=cell["algorithm_id"],
            scen=cell["scenario_id"],
            ep=cell["episode_index"],
            state=cell["run_state"],
            gate=cell["evaluation_gate"],
            n=cell["summary"]["encounter_count"],
            classes=classes,
            mind=_fmt(cell["summary"]["min_distance_m"]),
            verdicts=verdicts,
            ss=cell["summary"]["safety_score"],
            sr=cell["summary"]["rule_score"],
            sm=cell["summary"]["mission_score"],
            sc=cell["summary"]["composite_score"],
            ratio=_fmt(cell["path"]["path_ratio"], 3),
            xte=_fmt(cell["path"]["max_xte_m"]),
        )
        lines.append(row)
    lines.append("")
    for cell in bundle["cells"]:
        lines.append(render_cell_markdown(cell))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Score one or more campaign bundles into JSON + markdown reports."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bundles", nargs="+", type=Path, help="campaign bundle directories")
    parser.add_argument("--out", type=Path, required=True, help="output directory for JSON + markdown")
    args = parser.parse_args(argv)
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    for bundle in args.bundles:
        scored = score_bundle(bundle)
        stem = Path(bundle).name
        json_path = out_dir / f"{stem}.json"
        md_path = out_dir / f"{stem}.md"
        json_path.write_text(json.dumps(scored, indent=2, sort_keys=True) + "\n")
        md_path.write_text(render_bundle_markdown(scored) + "\n")
        print(f"scored {scored['cell_count']} cells: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
