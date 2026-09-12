"""Colleague-proposal reference patches applied on top of the frozen extraction.

Each proposal is a reviewed semantic change discussed with the colleague
(register docs/research/2026-09-11-colleague-structural-issues-register.md).
Patches run AFTER the mechanical extraction, fail loudly when the frozen
anchor text is absent, and are recorded in extraction.json with a
"colleague-proposal" edit kind so the extraction ledger stays self-describing.
The frozen source itself is never modified.
"""

from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

# P-C1 (register R3): avoidance speed-policy differentiation.
#
# The guidance surge cap (emergency_avoidance_speed_cap_mps) engages on ANY
# avoidance-tagged leg. Two links in the executed chain force that:
#   1) coordinate_transform_node navigation_mode_code() collapses ALL
#      avoidance-family strings ("emergency_avoidance", "emergency_avoid",
#      "collision_avoidance", "avoidance") onto path protocol code 6, and
#   2) ship_guidance_node navigation_mode_from_code() decodes code 6 back as
#      the literal string "emergency_avoidance", and the cap gate keys off it.
# The proposal therefore carries the colleague's own arbitration distinction
# (route_arbitration_policy.hpp emergency_behavior: only "emergency_avoidance"
# / "emergency_avoid" are emergency) across the code boundary: genuine
# emergency tags keep code 6; non-emergency tags ("collision_avoidance",
# "avoidance") take new code 10 and decode to their real tier. The surge cap
# then engages only for emergency tags; non-emergency "avoidance" legs follow
# the commanded/route speed. Every other avoidance interlock keeps the
# original behavior: is_emergency_avoidance_mode still accepts "avoidance",
# and the coordinate_transform guard/FAP predicate accepts codes 6 and 10.
_PC1_COORDINATE_TRANSFORM_EDITS = (
    {
        "anchor": '''    if (mode == "emergency_avoidance" ||
        mode == "emergency_avoid" ||
        mode == "collision_avoidance" ||
        mode == "avoidance") return 6;
''',
        "replacement": '''    // Colleague-proposal-s1 (P-C1): keep the emergency-tier distinction
    // alive across the path protocol. Genuine emergency tags stay code 6;
    // non-emergency avoidance tags ("collision_avoidance", "avoidance")
    // become code 10 so ship_guidance can decode the true tier.
    if (mode == "emergency_avoidance" ||
        mode == "emergency_avoid") return 6;
    if (mode == "collision_avoidance" ||
        mode == "avoidance") return 10;
''',
    },
    {
        "anchor": '''        [](const NedPoint& pt) { return pt.navigation_mode_code == 6; });
''',
        "replacement": '''        // Colleague-proposal-s1 (P-C1): code 10 is the non-emergency
        // avoidance tier; guard relaxation and FAP handling keep covering
        // every avoidance-tagged route exactly as before.
        [](const NedPoint& pt) {
            return pt.navigation_mode_code == 6 || pt.navigation_mode_code == 10;
        });
''',
    },
)

_PC1_SHIP_GUIDANCE_EDITS = (
    {
        "anchor": '''        case 6: return "emergency_avoidance";
''',
        "replacement": '''        case 6: return "emergency_avoidance";
        // Colleague-proposal-s1 (P-C1): non-emergency avoidance tier
        // (coordinate_transform code 10) decodes to its real tag.
        case 10: return "avoidance";
''',
    },
    {
        "anchor": '''static bool is_emergency_avoidance_mode(const std::string& mode)
{
    const std::string normalized = normalize_navigation_mode(mode);
    return normalized == "emergency_avoidance" ||
           normalized == "emergency_avoid" ||
           normalized == "collision_avoidance" ||
           normalized == "avoidance";
}
''',
        "replacement": '''static bool is_emergency_avoidance_mode(const std::string& mode)
{
    const std::string normalized = normalize_navigation_mode(mode);
    return normalized == "emergency_avoidance" ||
           normalized == "emergency_avoid" ||
           normalized == "collision_avoidance" ||
           normalized == "avoidance";
}

// Colleague-proposal-s1 (P-C1): emergency-tier scope for the avoidance surge
// cap. Mirrors the existing route_arbitration_policy.hpp emergency_behavior()
// definition: only genuine emergency tags qualify. Non-emergency avoidance
// tags ("avoidance", "collision_avoidance") stay covered by
// is_emergency_avoidance_mode for every other interlock.
static bool is_emergency_avoidance_speed_cap_mode(const std::string& mode)
{
    const std::string normalized = normalize_navigation_mode(mode);
    return normalized == "emergency_avoidance" ||
           normalized == "emergency_avoid";
}
''',
    },
    {
        "anchor": '''    const bool emergency_avoidance_active =
        target_is_emergency_avoidance || previous_is_emergency_avoidance;
''',
        "replacement": '''    const bool emergency_avoidance_active =
        target_is_emergency_avoidance || previous_is_emergency_avoidance;
    // Colleague-proposal-s1 (P-C1): cap-scoped predicate; see the surge-cap
    // gate below for the policy rationale.
    const bool emergency_avoidance_speed_cap_active =
        is_emergency_avoidance_speed_cap_mode(target_navigation_mode) ||
        is_emergency_avoidance_speed_cap_mode(previous_navigation_mode);
''',
    },
    {
        "anchor": '''    if (emergency_avoidance_active && !dp_mode_active_ && !final_speed_coupling_blocked) {
''',
        "replacement": '''    // Colleague-proposal-s1 (P-C1) avoidance speed policy: the emergency
    // surge cap engages ONLY when the target or predecessor waypoint carries
    // a genuine emergency tag ("emergency_avoidance"/"emergency_avoid").
    // Non-emergency "avoidance" legs follow the commanded/route speed so a
    // deviation segment transits at cruise pace instead of the 3.2 m/s cap.
    // Safety interlocks are untouched: every other emergency_avoidance_active
    // check (wheel-over, switch radius, cruise floor, corridor, manager
    // gates) keeps the original any-avoidance leg scope, and emergency
    // behavior is byte-identical because an emergency tag still satisfies
    // both predicates.
    if (emergency_avoidance_speed_cap_active && !dp_mode_active_ && !final_speed_coupling_blocked) {
''',
    },
)

# P-C2 (register R13): corner-degradation per-segment scoping.
#
# evaluate_avoidance_plan's corner loop min-accumulated a route-GLOBAL speed
# cap from EVERY interior vertex and apply_speed_degradation overwrote the
# whole speed_limit_mps array with it: one sharp kink degraded the entire
# avoidance route to the corner speed (p5 fan-HO ratchet 7.0 -> 0.89215 m/s,
# 42.597 m kink; R13). The proposal scopes the degradation per segment:
#   - a kink vertex caps only its two ADJACENT segments (i-1 and i); other
#     segments keep the requested speed (per-segment caps ride on
#     FeasibilityResult and apply_speed_degradation applies them one by one),
#   - vertices behind the vessel are skipped (passed-vertex heuristic: the
#     vessel is closer to vertex k+1 than to k), so a plan recovers once the
#     kink is behind the ship,
#   - safe speeds are floored at minimum_steerage_speed (the guidance
#     parameter name; declared with guidance's own 2.5 default so the bringup
#     yaml value, 3.0, applies unchanged once the key is added for this node).
# Param sanity note carried for the colleague, NOT changed here: the 1.2 deg/s
# default max_yaw_rate_deg_s dominates the corner cap on gentle kinks
# (required radius v/omega = 372 m at 7.8 m/s) and is worth a tuning pass.
_PC2_MANAGER_EDITS = (
    {
        "anchor": '''    double suggested_max_speed_mps{0.0};
    double suggested_min_distance_m{0.0};
};
''',
        "replacement": '''    double suggested_max_speed_mps{0.0};
    double suggested_min_distance_m{0.0};
    // Colleague-proposal-s1 (P-C2): per-vertex speed caps aligned with
    // speed_limit_mps; infinity means "keep the requested speed". Only
    // vertices bounding a segment adjacent to a tight kink carry a cap.
    std::vector<double> segment_speed_limit_mps{};
};
''',
    },
    {
        "anchor": '''        parameters_.declare_value("max_decel_mps2", 0.08);
''',
        "replacement": '''        parameters_.declare_value("max_decel_mps2", 0.08);
        // Colleague-proposal-s1 (P-C2): same key as ship_guidance; declared
        // with guidance's own default so the bringup yaml (3.0 for
        // ship_guidance_node) governs once the key is shared for this node.
        parameters_.declare_value("minimum_steerage_speed", 2.5);
''',
    },
    {
        "anchor": '''        max_decel_mps2_ = std::max(0.01, parameters_.get("max_decel_mps2").as_double());
''',
        "replacement": '''        max_decel_mps2_ = std::max(0.01, parameters_.get("max_decel_mps2").as_double());
        minimum_steerage_speed_ = std::max(0.1, parameters_.get("minimum_steerage_speed").as_double());
''',
    },
    {
        "anchor": '''        apply_speed_degradation(route, result.suggested_max_speed_mps);
''',
        "replacement": '''        // Colleague-proposal-s1 (P-C2): degradation is per segment now.
        apply_speed_degradation(route, result);
''',
    },
    {
        "anchor": '''        for (size_t i = 1; i + 1 < points.size(); ++i) {
            const double available_radius = available_turn_radius(points[i - 1], points[i], points[i + 1]);
            const double speed = requested_speed_at(route, i);
            const double dynamic_required_radius = speed * speed / max_lateral_accel_mps2_;
            const double yaw_required_radius =
                yaw_rate_limit_rad_s > 1e-6 ? speed / yaw_rate_limit_rad_s : std::numeric_limits<double>::infinity();
            const double required_radius =
                std::max({static_min_turn_radius, dynamic_required_radius, yaw_required_radius});

            result.estimated_available_turn_radius_m =
                std::min(result.estimated_available_turn_radius_m, available_radius);
            result.required_turn_radius_m =
                std::max(result.required_turn_radius_m, required_radius);

            if (available_radius + 1e-6 < required_radius) {
                const double safe_speed_by_lateral_accel =
                    std::sqrt(std::max(0.0, available_radius * max_lateral_accel_mps2_));
                const double safe_speed_by_yaw_rate =
                    std::max(0.0, available_radius * yaw_rate_limit_rad_s);
                const double safe_speed =
                    std::min(safe_speed_by_lateral_accel, safe_speed_by_yaw_rate);
                const bool yaw_rate_is_dominant =
                    yaw_required_radius >= dynamic_required_radius &&
                    yaw_required_radius >= static_min_turn_radius;
                result.suggested_max_speed_mps =
                    std::min(result.suggested_max_speed_mps, safe_speed);
                if (plan.require_exact_speed || !plan.allow_degraded_execution) {
                    auto rejected = rejected_result(
                        yaw_rate_is_dominant ? "yaw_rate_too_high" : "turn_radius_too_small",
                        yaw_rate_is_dominant ? "slow_down_or_smooth_turn" : "slow_down_or_enlarge_turn_radius");
                    rejected.requested_speed_mps = speed;
                    rejected.suggested_max_speed_mps = safe_speed;
                    rejected.required_turn_radius_m = required_radius;
                    rejected.estimated_available_turn_radius_m = available_radius;
                    return rejected;
                }
                result.degraded = true;
                result.state = "EXECUTING_WITH_LIMIT";
                result.reason = yaw_rate_is_dominant ? "yaw_rate_limited" : "turn_speed_limited";
                result.suggested_action = yaw_rate_is_dominant ? "slow_down_or_smooth_turn" : "slow_down";
            }
        }
''',
        "replacement": '''        // Colleague-proposal-s1 (P-C2) corner-degradation scoping: a tight
        // kink degrades ONLY the two segments adjacent to the offending
        // vertex (segments i-1 and i, i.e. the vertex entries bounding them:
        // i-1, i, i+1); every other entry keeps the requested speed instead
        // of inheriting a route-global cap. Vertices behind the vessel are
        // skipped (passed-vertex test), so the plan recovers once the vessel
        // moves past the kink, and safe speeds are floored at
        // minimum_steerage_speed so degradation never commands below
        // steerage way. suggested_max_speed_mps keeps reporting the
        // tightest upcoming cap for the status telemetry.
        // Tuning note for the colleague (unchanged here): the 1.2 deg/s
        // max_yaw_rate_deg_s default dominates the required radius on gentle
        // kinks (v/omega = 372 m at 7.8 m/s) and is worth a tuning pass.
        result.segment_speed_limit_mps.assign(
            points.size(), std::numeric_limits<double>::infinity());
        for (size_t i = 1; i + 1 < points.size(); ++i) {
            if (ship_passed_vertex(route, points, i)) {
                continue;  // recovery: the kink is behind the vessel
            }
            const double available_radius = available_turn_radius(points[i - 1], points[i], points[i + 1]);
            const double speed = requested_speed_at(route, i);
            const double dynamic_required_radius = speed * speed / max_lateral_accel_mps2_;
            const double yaw_required_radius =
                yaw_rate_limit_rad_s > 1e-6 ? speed / yaw_rate_limit_rad_s : std::numeric_limits<double>::infinity();
            const double required_radius =
                std::max({static_min_turn_radius, dynamic_required_radius, yaw_required_radius});

            result.estimated_available_turn_radius_m =
                std::min(result.estimated_available_turn_radius_m, available_radius);
            result.required_turn_radius_m =
                std::max(result.required_turn_radius_m, required_radius);

            if (available_radius + 1e-6 < required_radius) {
                const double safe_speed_by_lateral_accel =
                    std::sqrt(std::max(0.0, available_radius * max_lateral_accel_mps2_));
                const double safe_speed_by_yaw_rate =
                    std::max(0.0, available_radius * yaw_rate_limit_rad_s);
                // P-C2 floor: never degrade below the steerage floor.
                const double safe_speed =
                    std::max(
                        minimum_steerage_speed_,
                        std::min(safe_speed_by_lateral_accel, safe_speed_by_yaw_rate));
                const bool yaw_rate_is_dominant =
                    yaw_required_radius >= dynamic_required_radius &&
                    yaw_required_radius >= static_min_turn_radius;
                for (size_t vertex = i - 1; vertex <= i + 1; ++vertex) {
                    result.segment_speed_limit_mps[vertex] =
                        std::min(result.segment_speed_limit_mps[vertex], safe_speed);
                }
                result.suggested_max_speed_mps =
                    std::min(result.suggested_max_speed_mps, safe_speed);
                if (plan.require_exact_speed || !plan.allow_degraded_execution) {
                    auto rejected = rejected_result(
                        yaw_rate_is_dominant ? "yaw_rate_too_high" : "turn_radius_too_small",
                        yaw_rate_is_dominant ? "slow_down_or_smooth_turn" : "slow_down_or_enlarge_turn_radius");
                    rejected.requested_speed_mps = speed;
                    rejected.suggested_max_speed_mps = safe_speed;
                    rejected.required_turn_radius_m = required_radius;
                    rejected.estimated_available_turn_radius_m = available_radius;
                    return rejected;
                }
                result.degraded = true;
                result.state = "EXECUTING_WITH_LIMIT";
                result.reason = yaw_rate_is_dominant ? "yaw_rate_limited" : "turn_speed_limited";
                result.suggested_action = yaw_rate_is_dominant ? "slow_down_or_smooth_turn" : "slow_down";
            }
        }
''',
    },
    {
        "anchor": '''        return points;
    }

    static double distance(const LocalPoint& a, const LocalPoint& b)
    {
        return std::hypot(b.x - a.x, b.y - a.y);
    }
''',
        "replacement": '''        return points;
    }

    bool ship_local_point(
        const original_gnc::messages::ship_interfaces::RoutePlan& route,
        LocalPoint& ship) const
    {
        if (!has_ship_state_ || route.latitude.empty()) {
            return false;
        }
        const double meters_per_deg_lat = 111320.0;
        const double meters_per_deg_lon =
            111320.0 * std::cos(route.latitude.front() * kDegToRad);
        ship = LocalPoint{
            (latest_ship_state_.latitude - route.latitude.front()) * meters_per_deg_lat,
            (latest_ship_state_.longitude - route.latitude.front()) * meters_per_deg_lon};
        return true;
    }

    // Colleague-proposal-s1 (P-C2): passed-vertex heuristic. The manager has
    // no clean along-track state, so "vertex k is behind the vessel" is
    // approximated by: the vessel is closer to vertex k+1 than to k. Without
    // ship state nothing is skipped (conservative).
    bool ship_passed_vertex(
        const original_gnc::messages::ship_interfaces::RoutePlan& route,
        const std::vector<LocalPoint>& points,
        size_t vertex) const
    {
        LocalPoint ship{0.0, 0.0};
        if (!ship_local_point(route, ship) || vertex + 1 >= points.size()) {
            return false;
        }
        return distance(ship, points[vertex + 1]) < distance(ship, points[vertex]);
    }

    static double distance(const LocalPoint& a, const LocalPoint& b)
    {
        return std::hypot(b.x - a.x, b.y - a.y);
    }
''',
    },
    {
        "anchor": '''    void apply_speed_degradation(
        original_gnc::messages::ship_interfaces::RoutePlan& route,
        double suggested_max_speed_mps) const
    {
        if (!std::isfinite(suggested_max_speed_mps) || suggested_max_speed_mps <= 0.0) {
            return;
        }
        const double cap = std::min(suggested_max_speed_mps, max_command_speed_mps_);
        if (route.speed_limit_mps.empty()) {
            route.speed_limit_mps.assign(route.latitude.size(), cap);
            return;
        }
        for (double& speed : route.speed_limit_mps) {
            if (!std::isfinite(speed) || speed <= 0.0) {
                speed = cap;
            } else {
                speed = std::min(speed, cap);
            }
        }
    }
''',
        "replacement": '''    // Colleague-proposal-s1 (P-C2): per-vertex degradation. Vertices whose
    // cap is infinity keep the requested speed (clamped by the command limit
    // exactly as before); only the vertices bounding the segments adjacent
    // to a tight kink take the corner cap. An unscoped result (cap vector
    // absent or size-mismatched) degrades exactly like the original.
    void apply_speed_degradation(
        original_gnc::messages::ship_interfaces::RoutePlan& route,
        const FeasibilityResult& result) const
    {
        if (!std::isfinite(result.suggested_max_speed_mps) || result.suggested_max_speed_mps <= 0.0) {
            return;
        }
        if (route.speed_limit_mps.empty()) {
            route.speed_limit_mps.assign(route.latitude.size(), max_command_speed_mps_);
        }
        const bool scoped =
            result.segment_speed_limit_mps.size() == route.speed_limit_mps.size();
        for (size_t i = 0; i < route.speed_limit_mps.size(); ++i) {
            double& speed = route.speed_limit_mps[i];
            double segment_cap = max_command_speed_mps_;
            if (scoped && std::isfinite(result.segment_speed_limit_mps[i])) {
                segment_cap =
                    std::min(result.segment_speed_limit_mps[i], max_command_speed_mps_);
            }
            if (!std::isfinite(speed) || speed <= 0.0) {
                speed = segment_cap;
            } else {
                speed = std::min(speed, segment_cap);
            }
        }
    }
''',
    },
    {
        "anchor": '''    double max_decel_mps2_{0.08};
''',
        "replacement": '''    double max_decel_mps2_{0.08};
    double minimum_steerage_speed_{2.5};
''',
    },
)

# P-C3 (register R14): decel-check executed-speed awareness.
#
# The decel loop compared a PLANNED-profile braking distance
# (v0^2 - v1^2) / (2 * 0.08) against the FULL segment length: it fired while
# the vessel was stationary (executed speed 0.0 still demanded 242 m inside a
# 165 m segment; p6 vo-CS-E0 flat 0.3208 m/s command array, final SOG
# 0.399 m/s vs 3.2 reference; R14). The proposal makes the check aware of
# execution:
#   - v0 is the EXECUTED speed (status GeoPosition speed_mps) when the manager
#     has ship state, falling back to the requested speed at the segment
#     start; a stationary vessel can no longer demand a braking distance,
#   - the budget is measured over the distance REMAINING to the speed step
#     (vessel projected onto the incoming segment, clamped), and steps behind
#     the vessel are skipped (P-C2 passed-vertex heuristic),
#   - the decel floor is mode-aware: dp_hold/berthing keep the configured
#     max_decel_mps2 (0.08, param unchanged), cruise/avoidance transits brake
#     with at least max(max_decel_mps2_, 0.2),
#   - soft hysteresis: EXECUTING_WITH_LIMIT/decel_distance_tight is not
#     re-flagged while the route revision is unchanged since the last flag
#     (the hard reject path stays unconditional).
# Depends on P-C2 (reuses ship_local_point / ship_passed_vertex).
_PC3_MANAGER_EDITS = (
    {
        "anchor": '''    FeasibilityResult evaluate_avoidance_plan(
        const original_gnc::messages::ship_interfaces::AvoidancePlan& plan,
        const original_gnc::messages::ship_interfaces::RoutePlan& route) const
''',
        "replacement": '''    // Colleague-proposal-s1 (P-C3): no longer const — the decel check below
    // latches the last flagged route revision for hysteresis.
    FeasibilityResult evaluate_avoidance_plan(
        const original_gnc::messages::ship_interfaces::AvoidancePlan& plan,
        const original_gnc::messages::ship_interfaces::RoutePlan& route)
''',
    },
    {
        "anchor": '''        for (size_t i = 0; i + 1 < points.size(); ++i) {
            const double v0 = requested_speed_at(route, i);
            const double v1 = requested_speed_at(route, i + 1);
            if (v0 <= v1) {
                continue;
            }
            const double required_decel = (v0 * v0 - v1 * v1) / (2.0 * max_decel_mps2_);
            const double available = distance(points[i], points[i + 1]);
            result.required_decel_distance_m =
                std::max(result.required_decel_distance_m, required_decel);
            result.available_decel_distance_m =
                std::min(result.available_decel_distance_m, available);
            if (available + 1e-6 < required_decel) {
                if (plan.require_exact_speed || !plan.allow_degraded_execution) {
                    auto rejected = rejected_result("decel_distance_not_enough", "send_points_earlier");
                    rejected.required_decel_distance_m = required_decel;
                    rejected.available_decel_distance_m = available;
                    rejected.suggested_min_distance_m = required_decel;
                    return rejected;
                }
                result.degraded = true;
                result.state = "EXECUTING_WITH_LIMIT";
                result.reason = "decel_distance_tight";
                result.suggested_action = "send_points_earlier";
            }
        }
''',
        "replacement": '''        // Colleague-proposal-s1 (P-C3) decel-check executed-speed awareness:
        // the braking budget starts from the EXECUTED speed (status
        // GeoPosition speed when the manager has ship state, else the
        // requested speed at the segment start), runs to the step target over
        // the distance REMAINING to the speed step, skips steps behind the
        // vessel, uses a mode-aware decel floor, and hysteresis-suppresses
        // the soft flag while the route revision is unchanged. A stationary
        // vessel can no longer fire decel_distance_tight on a fresh plan.
        const double decel_floor = decel_floor_for(route);
        for (size_t i = 0; i + 1 < points.size(); ++i) {
            double v0 = requested_speed_at(route, i);
            const double v1 = requested_speed_at(route, i + 1);
            if (has_ship_state_ && std::isfinite(latest_ship_state_.speed_mps) &&
                latest_ship_state_.speed_mps >= 0.0) {
                v0 = latest_ship_state_.speed_mps;  // 0.0 (stationary) counts
            }
            if (v0 <= v1) {
                continue;
            }
            if (ship_passed_vertex(route, points, i + 1)) {
                continue;  // the speed step is behind the vessel
            }
            const double remaining = remaining_distance_to_vertex(route, points, i + 1);
            const double required_decel = (v0 * v0 - v1 * v1) / (2.0 * decel_floor);
            result.required_decel_distance_m =
                std::max(result.required_decel_distance_m, required_decel);
            result.available_decel_distance_m =
                std::min(result.available_decel_distance_m, remaining);
            if (remaining + 1e-6 < required_decel) {
                if (plan.require_exact_speed || !plan.allow_degraded_execution) {
                    auto rejected = rejected_result("decel_distance_not_enough", "send_points_earlier");
                    rejected.required_decel_distance_m = required_decel;
                    rejected.available_decel_distance_m = remaining;
                    rejected.suggested_min_distance_m = required_decel;
                    return rejected;
                }
                if (has_decel_flag_revision_ &&
                    route.route_revision == last_decel_flag_revision_) {
                    continue;  // hysteresis: this revision was already flagged
                }
                result.degraded = true;
                result.state = "EXECUTING_WITH_LIMIT";
                result.reason = "decel_distance_tight";
                result.suggested_action = "send_points_earlier";
                last_decel_flag_revision_ = route.route_revision;
                has_decel_flag_revision_ = true;
            }
        }
''',
    },
    {
        "anchor": '''        return distance(ship, points[vertex + 1]) < distance(ship, points[vertex]);
    }
''',
        "replacement": '''        return distance(ship, points[vertex + 1]) < distance(ship, points[vertex]);
    }

    // Colleague-proposal-s1 (P-C3): distance still to run before the speed
    // step at `vertex`. The vessel is projected onto the incoming segment
    // (ratio clamped to [0, 1]); with no ship state the full segment length
    // is used, matching the original check.
    double remaining_distance_to_vertex(
        const original_gnc::messages::ship_interfaces::RoutePlan& route,
        const std::vector<LocalPoint>& points,
        size_t vertex) const
    {
        const double full = distance(points[vertex - 1], points[vertex]);
        LocalPoint ship{0.0, 0.0};
        if (!ship_local_point(route, ship) || vertex - 1 >= points.size()) {
            return full;
        }
        const LocalPoint& start = points[vertex - 1];
        const double dx = points[vertex].x - start.x;
        const double dy = points[vertex].y - start.y;
        const double length_sq = dx * dx + dy * dy;
        double ratio = 0.0;
        if (length_sq > 1e-9) {
            ratio = std::clamp(
                ((ship.x - start.x) * dx + (ship.y - start.y) * dy) / length_sq,
                0.0, 1.0);
        }
        return (1.0 - ratio) * full;
    }

    // Colleague-proposal-s1 (P-C3): mode-aware decel floor. Terminal
    // low-speed contexts (dp hold, berthing family) keep the configured
    // max_decel_mps2; transit contexts (cruise/avoidance) may brake with at
    // least 0.2 m/s^2. The max_decel_mps2 parameter itself is unchanged.
    double decel_floor_for(const original_gnc::messages::ship_interfaces::RoutePlan& route) const
    {
        for (const std::string& mode : route.navigation_mode) {
            const std::string normalized = normalize_mode(mode);
            if (normalized == "dp_hold" || normalized == "dp" ||
                normalized == "station_keeping" || normalized == "berthing" ||
                normalized == "docking" || normalized == "berth_approach") {
                return max_decel_mps2_;
            }
        }
        if (normalize_mode(route.route_type) == "berthing") {
            return max_decel_mps2_;
        }
        return std::max(max_decel_mps2_, 0.2);
    }
''',
    },
    {
        "anchor": '''    double minimum_steerage_speed_{2.5};
''',
        "replacement": '''    double minimum_steerage_speed_{2.5};
    // Colleague-proposal-s1 (P-C3): last route revision that raised the soft
    // decel_distance_tight flag (hysteresis against re-flag storms).
    uint32_t last_decel_flag_revision_{0};
    bool has_decel_flag_revision_{false};
''',
    },
)

PROPOSALS = {
    "P-C1": {
        "id": "P-C1",
        "title": "avoidance speed-policy differentiation",
        "register": "R3",
        "branch": "codex/colleague-proposal-s1",
        "files": {
            "coordinate_transform_node.cpp": {
                "source_relative_path": "src/gnc/ship_guidance/src/coordinate_transform_node.cpp",
                "edits": _PC1_COORDINATE_TRANSFORM_EDITS,
            },
            "ship_guidance_node.cpp": {
                "source_relative_path": "src/gnc/ship_guidance/src/ship_guidance_node.cpp",
                "edits": _PC1_SHIP_GUIDANCE_EDITS,
            },
        },
    },
    "P-C2": {
        "id": "P-C2",
        "title": "corner-degradation per-segment scoping",
        "register": "R13",
        "branch": "codex/colleague-proposal-s1",
        "depends_on": [],
        "files": {
            "active_route_manager_node.cpp": {
                "source_relative_path": "src/gnc/ship_guidance/src/active_route_manager_node.cpp",
                "edits": _PC2_MANAGER_EDITS,
            },
        },
    },
    "P-C3": {
        "id": "P-C3",
        "title": "decel-check executed-speed awareness",
        "register": "R14",
        "branch": "codex/colleague-proposal-s1",
        "depends_on": ["P-C2"],
        "files": {
            "active_route_manager_node.cpp": {
                "source_relative_path": "src/gnc/ship_guidance/src/active_route_manager_node.cpp",
                "edits": _PC3_MANAGER_EDITS,
            },
        },
    },
}


def _expand_proposals(proposal_ids: list[str]) -> list[str]:
    """Order proposals so dependencies apply first, without duplicates."""
    ordered: list[str] = []
    for proposal_id in proposal_ids:
        if proposal_id not in PROPOSALS:
            raise KeyError(f"Unknown colleague proposal: {proposal_id}")
        for dependency in _expand_proposals(PROPOSALS[proposal_id].get("depends_on", [])):
            if dependency not in ordered:
                ordered.append(dependency)
        if proposal_id not in ordered:
            ordered.append(proposal_id)
    return ordered


def apply_proposals(proposal_ids: list[str], source: Path, output: Path) -> dict:
    """Apply composed colleague proposals (dependencies first) to one build."""
    applied = [
        apply_proposal(proposal_id, source, output) for proposal_id in _expand_proposals(proposal_ids)
    ]
    composed = {"proposals": applied}
    extraction_path = output / "extraction.json"
    extraction = json.loads(extraction_path.read_text())
    extraction["colleague_proposal"] = composed
    extraction_path.write_text(json.dumps(extraction, indent=2))
    return composed


def apply_proposal(proposal_id: str, source: Path, output: Path) -> dict:
    """Apply one reviewed proposal to the extracted outputs and its ledger."""
    proposal = PROPOSALS[proposal_id]
    extraction_path = output / "extraction.json"
    extraction = json.loads(extraction_path.read_text())
    entries = {entry["file"]: entry for entry in extraction["files"]}
    patched = {}
    for file_name, spec in proposal["files"].items():
        if file_name not in entries:
            raise ValueError(f"Proposal {proposal_id}: no extraction ledger entry for {file_name}")
        target = output / file_name
        text = target.read_text()
        ledger = []
        for index, edit in enumerate(spec["edits"]):
            anchor, replacement = edit["anchor"], edit["replacement"]
            occurrences = text.count(anchor)
            if occurrences != 1:
                raise ValueError(
                    f"Proposal {proposal_id} anchor {index} matches {occurrences} times in "
                    f"{file_name}; frozen source layout changed"
                )
            text = text.replace(anchor, replacement)
            ledger.append(
                {
                    "kind": f"colleague-proposal-{proposal['branch']}:{proposal_id}",
                    "before": anchor,
                    "after": replacement,
                }
            )
        target.write_text(text)
        entry = entries[file_name]
        entry["edits"].extend(ledger)
        entry["native_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        original_path = source / spec["source_relative_path"]
        entry["complete_diff"] = "".join(
            difflib.unified_diff(
                original_path.read_text().splitlines(keepends=True),
                text.splitlines(keepends=True),
                fromfile=f"original/{entry['source_path']}",
                tofile=f"native/{entry['source_path']}",
            )
        )
        patched[file_name] = {
            "edit_count": len(ledger),
            "native_sha256": entry["native_sha256"],
        }
    extraction["colleague_proposal"] = {
        "id": proposal["id"],
        "title": proposal["title"],
        "register": proposal["register"],
        "branch": proposal["branch"],
        "patched_files": sorted(patched),
    }
    extraction_path.write_text(json.dumps(extraction, indent=2))
    return {
        "id": proposal["id"],
        "title": proposal["title"],
        "register": proposal["register"],
        "branch": proposal["branch"],
        "patched_files": patched,
    }
