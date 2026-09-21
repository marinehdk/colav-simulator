#pragma once

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstddef>
#include <limits>
#include <string>

#include "ship_interfaces/msg/route_plan.hpp"

namespace ship_guidance::route_contract {

enum class RouteKind {
    Nominal,
    Temporary,
};

struct ContractResult {
    bool valid{false};
    bool normalized{false};
    std::string reason{"not_checked"};
    std::string suggested_action{"check_route_contract"};
};

inline std::string normalize_token(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        if (ch == '-' || ch == ' ') {
            return '_';
        }
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

inline std::string canonical_navigation_mode(const std::string& raw_mode)
{
    const std::string mode = normalize_token(raw_mode);
    if (mode == "cruise" || mode == "open_water_cruise" ||
        mode == "post_turn_cruise" || mode == "transit" ||
        mode == "normal_route" || mode == "route") {
        return "cruise";
    }
    if (mode == "narrow_channel" || mode == "narrow") {
        return "narrow_channel";
    }
    if (mode == "harbor" || mode == "port") {
        return "harbor";
    }
    if (mode == "approach" || mode == "dp_approach") {
        return "approach";
    }
    if (mode == "dp_hold" || mode == "dp" ||
        mode == "station_keeping" || mode == "position_hold") {
        return "dp_hold";
    }
    if (mode == "avoidance" || mode == "collision_avoidance" ||
        mode == "emergency_avoidance" || mode == "emergency_avoid") {
        return mode == "emergency_avoidance" || mode == "emergency_avoid"
            ? "emergency_avoidance"
            : "avoidance";
    }
    if (mode == "berth_departure" || mode == "departure" ||
        mode == "undocking") {
        return "berth_departure";
    }
    if (mode == "join_route" || mode == "route_join") {
        return "join_route";
    }
    if (mode == "berthing" || mode == "docking" ||
        mode == "berth_approach") {
        return "berthing";
    }
    return {};
}

inline std::string default_temporary_mode(const std::string& raw_route_type)
{
    const std::string route_type = normalize_token(raw_route_type);
    if (route_type == "dp_hold" || route_type == "dp" ||
        route_type == "station_keeping" || route_type == "position_hold") {
        return "dp_hold";
    }
    if (route_type == "return_to_route") {
        return "cruise";
    }
    if (route_type == "emergency_avoidance" || route_type == "emergency_avoid") {
        return "emergency_avoidance";
    }
    return "avoidance";
}

inline std::string default_mode_at(
    RouteKind kind,
    const std::string& route_type,
    std::size_t index,
    std::size_t count)
{
    if (kind == RouteKind::Nominal) {
        return index + 1 == count ? "dp_hold" : "cruise";
    }

    const std::string temporary_mode = default_temporary_mode(route_type);
    if (temporary_mode == "dp_hold") {
        return index + 1 == count ? "dp_hold" : "approach";
    }
    return temporary_mode;
}

inline ContractResult validate_and_normalize(
    ship_interfaces::msg::RoutePlan& route,
    RouteKind kind)
{
    ContractResult result;
    if (kind == RouteKind::Nominal && normalize_token(route.route_type) == "planner_trajectory_v1") {
        result.reason = "planner_trajectory_requires_avoidance_admission";
        return result;
    }
    const std::size_t count = route.latitude.size();
    if (count < 2) {
        result.reason = "waypoint_count_less_than_two";
        result.suggested_action = "provide_at_least_two_waypoints";
        return result;
    }
    if (route.longitude.size() != count) {
        result.reason = "latitude_longitude_length_mismatch";
        result.suggested_action = "make_coordinate_arrays_equal_length";
        return result;
    }

    for (std::size_t index = 0; index < count; ++index) {
        const double latitude = route.latitude[index];
        const double longitude = route.longitude[index];
        if (!std::isfinite(latitude) || !std::isfinite(longitude) ||
            std::abs(latitude) > 90.0 || std::abs(longitude) > 180.0) {
            result.reason = "invalid_wgs84_coordinate";
            result.suggested_action =
                "provide_finite_latitude_in_[-90,90]_and_longitude_in_[-180,180]";
            return result;
        }
    }

    if (route.speed_limit_mps.empty()) {
        route.speed_limit_mps.assign(count, 0.0);
        result.normalized = true;
    } else if (route.speed_limit_mps.size() != count) {
        result.reason = "speed_limit_length_mismatch";
        result.suggested_action = "provide_empty_or_equal_length_speed_array";
        return result;
    }
    for (double speed_limit : route.speed_limit_mps) {
        if (!std::isfinite(speed_limit) || speed_limit < 0.0) {
            result.reason = "invalid_speed_limit";
            result.suggested_action = "use_finite_nonnegative_speed_limits";
            return result;
        }
    }

    if (route.navigation_mode.empty()) {
        route.navigation_mode.resize(count);
        result.normalized = true;
    } else if (route.navigation_mode.size() != count) {
        result.reason = "navigation_mode_length_mismatch";
        result.suggested_action = "provide_empty_or_equal_length_navigation_mode_array";
        return result;
    }

    for (std::size_t index = 0; index < count; ++index) {
        const std::string fallback =
            default_mode_at(kind, route.route_type, index, count);
        std::string canonical;
        const std::string raw_mode = normalize_token(route.navigation_mode[index]);
        if (raw_mode.empty()) {
            canonical = fallback;
        } else if (raw_mode == "initial" && index == 0) {
            // L1-2 uses "initial" as a non-executing P0 marker. Resolve it
            // from the first actual segment so the planner stays independent
            // from the internal L4-5 mode enum.
            canonical = count > 1
                ? canonical_navigation_mode(route.navigation_mode[1])
                : std::string{};
            if (canonical.empty()) {
                canonical = fallback;
            }
        } else {
            canonical = canonical_navigation_mode(route.navigation_mode[index]);
        }
        if (canonical.empty()) {
            result.reason = "unsupported_navigation_mode";
            result.suggested_action =
                "use_supported_route_avoidance_or_berthing_navigation_mode";
            return result;
        }
        if (route.navigation_mode[index] != canonical) {
            result.normalized = true;
            route.navigation_mode[index] = canonical;
        }
    }

    const std::string normalized_route_type = normalize_token(route.route_type);
    const bool nominal_transit_terminal =
        kind == RouteKind::Nominal &&
        (normalized_route_type.empty() || normalized_route_type == "transit" ||
         normalized_route_type == "nominal" || normalized_route_type == "normal_route" ||
         normalized_route_type == "route");
    if (nominal_transit_terminal && route.navigation_mode.back() == "cruise") {
        // L1-2 legacy publishers may explicitly fill every mode with cruise.
        // A nominal transit destination is terminal, so normalize only that
        // final cruise point to DP hold. Temporary/avoidance routes are not
        // affected because they use RouteKind::Temporary.
        route.navigation_mode.back() = "dp_hold";
        result.normalized = true;
    }
    if (route.route_type != normalized_route_type) {
        route.route_type = normalized_route_type;
        result.normalized = true;
    }
    if (route.header.frame_id.empty()) {
        route.header.frame_id = "wgs84";
        result.normalized = true;
    }

    result.valid = true;
    result.reason = result.normalized ? "route_contract_normalized" : "route_contract_valid";
    result.suggested_action = "none";
    return result;
}

inline double local_distance_m(
    double latitude_a,
    double longitude_a,
    double latitude_b,
    double longitude_b)
{
    constexpr double meters_per_degree = 111320.0;
    const double mean_latitude_rad =
        0.5 * (latitude_a + latitude_b) * M_PI / 180.0;
    const double north =
        (latitude_b - latitude_a) * meters_per_degree;
    const double east =
        (longitude_b - longitude_a) * meters_per_degree *
        std::cos(mean_latitude_rad);
    return std::hypot(north, east);
}

inline bool build_return_route(
    const ship_interfaces::msg::RoutePlan& nominal_input,
    double current_latitude,
    double current_longitude,
    const std::string& return_route_id,
    ship_interfaces::msg::RoutePlan& output,
    double entry_speed_cap_mps = std::numeric_limits<double>::infinity(),
    double min_intercept_lookahead_m = 0.0,
    double max_intercept_angle_deg = 90.0,
    double speed_ramp_accel_mps2 = std::numeric_limits<double>::infinity(),
    double speed_ramp_sample_spacing_m = 0.0)
{
    if (!std::isfinite(current_latitude) || !std::isfinite(current_longitude) ||
        std::abs(current_latitude) > 90.0 || std::abs(current_longitude) > 180.0) {
        return false;
    }

    auto nominal = nominal_input;
    const auto contract_result =
        validate_and_normalize(nominal, RouteKind::Nominal);
    if (!contract_result.valid) {
        return false;
    }

    constexpr double meters_per_degree = 111320.0;
    const double cosine_latitude =
        std::max(1e-6, std::abs(std::cos(current_latitude * M_PI / 180.0)));
    std::size_t best_segment = 0;
    double best_fraction = 0.0;
    double best_distance_sq = std::numeric_limits<double>::infinity();

    for (std::size_t index = 0; index + 1 < nominal.latitude.size(); ++index) {
        const double ax =
            (nominal.latitude[index] - current_latitude) * meters_per_degree;
        const double ay =
            (nominal.longitude[index] - current_longitude) *
            meters_per_degree * cosine_latitude;
        const double bx =
            (nominal.latitude[index + 1] - current_latitude) * meters_per_degree;
        const double by =
            (nominal.longitude[index + 1] - current_longitude) *
            meters_per_degree * cosine_latitude;
        const double dx = bx - ax;
        const double dy = by - ay;
        const double length_sq = dx * dx + dy * dy;
        if (length_sq < 1e-6) {
            continue;
        }
        const double fraction =
            std::clamp(-(ax * dx + ay * dy) / length_sq, 0.0, 1.0);
        const double projected_x = ax + fraction * dx;
        const double projected_y = ay + fraction * dy;
        const double distance_sq =
            projected_x * projected_x + projected_y * projected_y;
        if (distance_sq < best_distance_sq) {
            best_distance_sq = distance_sq;
            best_segment = index;
            best_fraction = fraction;
        }
    }

    output = ship_interfaces::msg::RoutePlan{};
    output.header = nominal.header;
    output.route_id = return_route_id;
    output.route_revision = nominal.route_revision;
    output.route_type = "internal_return_to_route";

    auto append_point = [&](double latitude, double longitude, double speed, const std::string& mode) {
        if (!output.latitude.empty() &&
            local_distance_m(
                output.latitude.back(), output.longitude.back(),
                latitude, longitude) < 1.0) {
            return;
        }
        output.latitude.push_back(latitude);
        output.longitude.push_back(longitude);
        output.speed_limit_mps.push_back(speed);
        output.navigation_mode.push_back(mode);
    };

    const double segment_speed = nominal.speed_limit_mps[best_segment];
    const double entry_speed = std::min(segment_speed, entry_speed_cap_mps);
    append_point(current_latitude, current_longitude, entry_speed, "cruise");

    const double segment_length_m = std::sqrt(
        std::pow(
            (nominal.latitude[best_segment + 1] - nominal.latitude[best_segment]) *
                meters_per_degree,
            2.0) +
        std::pow(
            (nominal.longitude[best_segment + 1] - nominal.longitude[best_segment]) *
                meters_per_degree * cosine_latitude,
            2.0));
    const double bounded_intercept_angle_deg =
        std::clamp(max_intercept_angle_deg, 1.0, 90.0);
    const double lateral_distance_m = std::sqrt(best_distance_sq);
    double forward_lookahead_m = std::max(0.0, min_intercept_lookahead_m);
    if (bounded_intercept_angle_deg < 89.999) {
        forward_lookahead_m = std::max(
            forward_lookahead_m,
            lateral_distance_m /
                std::tan(bounded_intercept_angle_deg * M_PI / 180.0));
    }
    const double intercept_fraction = segment_length_m > 1e-6
        ? std::clamp(
            best_fraction + forward_lookahead_m / segment_length_m,
            best_fraction,
            1.0)
        : best_fraction;
    const double projection_latitude =
        nominal.latitude[best_segment] +
        intercept_fraction *
        (nominal.latitude[best_segment + 1] - nominal.latitude[best_segment]);
    const double projection_longitude =
        nominal.longitude[best_segment] +
        intercept_fraction *
        (nominal.longitude[best_segment + 1] - nominal.longitude[best_segment]);
    append_point(
        projection_latitude, projection_longitude,
        entry_speed, "cruise");

    double distance_after_intercept_m = 0.0;
    double previous_latitude = projection_latitude;
    double previous_longitude = projection_longitude;
    for (std::size_t index = best_segment + 1;
         index < nominal.latitude.size(); ++index) {
        const double segment_distance_m = local_distance_m(
            previous_latitude, previous_longitude,
            nominal.latitude[index], nominal.longitude[index]);
        const double ramp_limit_at_segment_start =
            std::isfinite(speed_ramp_accel_mps2) &&
            speed_ramp_accel_mps2 > 0.0 && std::isfinite(entry_speed)
            ? std::sqrt(std::max(
                0.0,
                entry_speed * entry_speed +
                    2.0 * speed_ramp_accel_mps2 * distance_after_intercept_m))
            : std::numeric_limits<double>::infinity();
        if (std::isfinite(speed_ramp_accel_mps2) &&
            speed_ramp_accel_mps2 > 0.0 &&
            speed_ramp_sample_spacing_m > 1.0 &&
            nominal.speed_limit_mps[index] > ramp_limit_at_segment_start + 1e-6) {
            for (double offset_m = speed_ramp_sample_spacing_m;
                 offset_m < segment_distance_m - 1.0;
                 offset_m += speed_ramp_sample_spacing_m) {
                const double ratio = offset_m / segment_distance_m;
                const double ramp_limit = std::sqrt(std::max(
                    0.0,
                    entry_speed * entry_speed +
                        2.0 * speed_ramp_accel_mps2 *
                            (distance_after_intercept_m + offset_m)));
                if (ramp_limit >= nominal.speed_limit_mps[index] - 1e-6) {
                    break;
                }
                append_point(
                    previous_latitude + ratio *
                        (nominal.latitude[index] - previous_latitude),
                    previous_longitude + ratio *
                        (nominal.longitude[index] - previous_longitude),
                    std::min(nominal.speed_limit_mps[index], ramp_limit),
                    nominal.navigation_mode[index]);
            }
        }
        distance_after_intercept_m += segment_distance_m;
        double speed = nominal.speed_limit_mps[index];
        if (std::isfinite(speed_ramp_accel_mps2) &&
            speed_ramp_accel_mps2 > 0.0 && std::isfinite(entry_speed)) {
            const double ramp_limit = std::sqrt(std::max(
                0.0,
                entry_speed * entry_speed +
                    2.0 * speed_ramp_accel_mps2 * distance_after_intercept_m));
            speed = std::min(speed, ramp_limit);
        }
        append_point(
            nominal.latitude[index],
            nominal.longitude[index],
            speed,
            nominal.navigation_mode[index]);
        previous_latitude = nominal.latitude[index];
        previous_longitude = nominal.longitude[index];
    }

    if (output.latitude.size() < 2) {
        return false;
    }
    output.navigation_mode.back() = nominal.navigation_mode.back();
    return true;
}

}  // namespace ship_guidance::route_contract
