#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

#include "ship_interfaces/msg/avoidance_plan.hpp"
#include "ship_interfaces/msg/velocity_intent.hpp"
#include "ship_interfaces/msg/geo_position.hpp"
#include "ship_interfaces/msg/route_execution_status.hpp"
#include "ship_interfaces/msg/route_plan.hpp"
#include "ship_interfaces/msg/route_plan_status.hpp"

#include "ship_guidance/route_arbitration_policy.hpp"
#include "ship_guidance/route_contract.hpp"
#include "ship_guidance/planner_trajectory_contract.hpp"
#include "ship_guidance/geodesy.hpp"

namespace {

constexpr double kDegToRad = M_PI / 180.0;
constexpr double kRadToDeg = 180.0 / M_PI;

std::string normalize_mode(std::string mode)
{
    std::transform(mode.begin(), mode.end(), mode.begin(), [](unsigned char ch) {
        if (ch == '-' || ch == ' ') {
            return '_';
        }
        return static_cast<char>(std::tolower(ch));
    });
    return mode;
}

bool time_is_zero(const builtin_interfaces::msg::Time& stamp)
{
    return stamp.sec == 0 && stamp.nanosec == 0;
}

double clamp_angle_deg(double angle)
{
    while (angle >= 360.0) {
        angle -= 360.0;
    }
    while (angle < 0.0) {
        angle += 360.0;
    }
    return angle;
}

struct LocalPoint {
    double x{0.0};  // north, m
    double y{0.0};  // east, m
};

struct FeasibilityResult {
    bool accepted{false};
    bool executing{false};
    bool degraded{false};
    bool rejected{true};
    std::string state{"REJECTED"};
    std::string reason{"not_checked"};
    std::string suggested_action{"check_plan"};
    double requested_speed_mps{0.0};
    double applied_speed_mps{0.0};
    double requested_heading_deg{std::numeric_limits<double>::quiet_NaN()};
    double applied_heading_deg{std::numeric_limits<double>::quiet_NaN()};
    double required_turn_radius_m{0.0};
    double estimated_available_turn_radius_m{std::numeric_limits<double>::infinity()};
    double required_decel_distance_m{0.0};
    double available_decel_distance_m{std::numeric_limits<double>::infinity()};
    double suggested_max_speed_mps{0.0};
    double suggested_min_distance_m{0.0};
    std::vector<double> admitted_speed_limits_mps;
};

}  // namespace

class ActiveRouteManagerNode : public rclcpp::Node
{
public:
    ActiveRouteManagerNode()
        : Node("active_route_manager_node")
    {
        declare_parameter("nominal_route_topic", "/route_planning/route_plan");
        declare_parameter("avoidance_plan_topic", "/colav/avoidance_plan");
        declare_parameter("active_route_topic", "/gnc/active_route");
        declare_parameter("execution_status_topic", "/gnc/route_execution_status");
        declare_parameter("route_plan_status_topic", "/route_planning/route_plan_status");
        declare_parameter("ship_state_topic", "/ship/geo_position");
        declare_parameter("max_command_speed_mps", 8.0);
        declare_parameter("min_segment_length_m", 30.0);
        declare_parameter("emergency_min_segment_length_m", 15.0);
        declare_parameter("planner_route_min_segment_skip", true);
        declare_parameter("min_turn_radius_m", 80.0);
        declare_parameter("emergency_min_turn_radius_m", 45.0);
        declare_parameter("max_lateral_accel_mps2", 0.25);
        declare_parameter("max_yaw_rate_deg_s", 1.2);
        declare_parameter("emergency_max_yaw_rate_deg_s", 2.0);
        declare_parameter("max_decel_mps2", 0.08);
        declare_parameter("default_avoidance_hold_s", 60.0);
        declare_parameter("max_heading_path_error_deg", 20.0);
        declare_parameter("publish_nominal_status", true);
        declare_parameter("enable_berthing_arbitration", false);
        declare_parameter("enable_berthing_arbitration_launch_override", false);
        declare_parameter("berthing_candidate_route_topic", "/mission/berthing_task/candidate_route");
        declare_parameter("berthing_state_topic", "/mission/berthing_task/state");
        declare_parameter("berthing_candidate_timeout_s", 10.0);
        declare_parameter("max_berthing_speed_mps", 2.0);
        declare_parameter("berthing_handover_entry_speed_mps", 0.8);
        declare_parameter("berthing_handover_min_lookahead_m", 45.0);
        declare_parameter("berthing_handover_max_intercept_angle_deg", 15.0);
        declare_parameter("berthing_handover_ramp_accel_mps2", 0.02);
        declare_parameter("berthing_handover_ramp_spacing_m", 45.0);

        nominal_route_topic_ = get_parameter("nominal_route_topic").as_string();
        avoidance_plan_topic_ = get_parameter("avoidance_plan_topic").as_string();
        active_route_topic_ = get_parameter("active_route_topic").as_string();
        execution_status_topic_ = get_parameter("execution_status_topic").as_string();
        route_plan_status_topic_ = get_parameter("route_plan_status_topic").as_string();
        ship_state_topic_ = get_parameter("ship_state_topic").as_string();
        max_command_speed_mps_ = std::max(0.1, get_parameter("max_command_speed_mps").as_double());
        min_segment_length_m_ = std::max(1.0, get_parameter("min_segment_length_m").as_double());
        emergency_min_segment_length_m_ = std::max(1.0, get_parameter("emergency_min_segment_length_m").as_double());
        planner_route_min_segment_skip_ = get_parameter("planner_route_min_segment_skip").as_bool();
        min_turn_radius_m_ = std::max(1.0, get_parameter("min_turn_radius_m").as_double());
        emergency_min_turn_radius_m_ = std::max(1.0, get_parameter("emergency_min_turn_radius_m").as_double());
        max_lateral_accel_mps2_ = std::max(0.01, get_parameter("max_lateral_accel_mps2").as_double());
        max_yaw_rate_deg_s_ = std::max(0.1, get_parameter("max_yaw_rate_deg_s").as_double());
        emergency_max_yaw_rate_deg_s_ = std::max(
            max_yaw_rate_deg_s_, get_parameter("emergency_max_yaw_rate_deg_s").as_double());
        max_decel_mps2_ = std::max(0.01, get_parameter("max_decel_mps2").as_double());
        default_avoidance_hold_s_ = std::max(1.0, get_parameter("default_avoidance_hold_s").as_double());
        max_heading_path_error_deg_ = std::clamp(
            get_parameter("max_heading_path_error_deg").as_double(), 0.1, 180.0);
        publish_nominal_status_ = get_parameter("publish_nominal_status").as_bool();
        const bool launch_enables_berthing_arbitration =
            get_parameter("enable_berthing_arbitration_launch_override").as_bool();
        enable_berthing_arbitration_ =
            get_parameter("enable_berthing_arbitration").as_bool() ||
            launch_enables_berthing_arbitration;
        berthing_candidate_route_topic_ = get_parameter("berthing_candidate_route_topic").as_string();
        berthing_state_topic_ = get_parameter("berthing_state_topic").as_string();
        berthing_candidate_timeout_s_ = std::max(1.0, get_parameter("berthing_candidate_timeout_s").as_double());
        max_berthing_speed_mps_ = std::max(0.1, get_parameter("max_berthing_speed_mps").as_double());
        berthing_handover_entry_speed_mps_ = std::max(
            0.1, get_parameter("berthing_handover_entry_speed_mps").as_double());
        berthing_handover_min_lookahead_m_ = std::max(
            1.0, get_parameter("berthing_handover_min_lookahead_m").as_double());
        berthing_handover_max_intercept_angle_deg_ = std::clamp(
            get_parameter("berthing_handover_max_intercept_angle_deg").as_double(),
            1.0, 45.0);
        berthing_handover_ramp_accel_mps2_ = std::max(
            0.001, get_parameter("berthing_handover_ramp_accel_mps2").as_double());
        berthing_handover_ramp_spacing_m_ = std::max(
            5.0, get_parameter("berthing_handover_ramp_spacing_m").as_double());

        auto route_qos = rclcpp::QoS(10).transient_local().reliable();
        active_route_pub_ = create_publisher<ship_interfaces::msg::RoutePlan>(
            active_route_topic_, route_qos);
        status_pub_ = create_publisher<ship_interfaces::msg::RouteExecutionStatus>(
            execution_status_topic_, 10);

        nominal_route_sub_ = create_subscription<ship_interfaces::msg::RoutePlan>(
            nominal_route_topic_, route_qos,
            std::bind(&ActiveRouteManagerNode::nominal_route_callback, this, std::placeholders::_1));
        if (enable_berthing_arbitration_) {
            berthing_candidate_sub_ = create_subscription<ship_interfaces::msg::RoutePlan>(
                berthing_candidate_route_topic_, route_qos,
                std::bind(&ActiveRouteManagerNode::berthing_candidate_callback, this, std::placeholders::_1));
            berthing_state_sub_ = create_subscription<std_msgs::msg::String>(
                berthing_state_topic_, 10,
                std::bind(&ActiveRouteManagerNode::berthing_state_callback, this, std::placeholders::_1));
        }
        avoidance_plan_sub_ = create_subscription<ship_interfaces::msg::AvoidancePlan>(
            avoidance_plan_topic_, 10,
            std::bind(&ActiveRouteManagerNode::avoidance_plan_callback, this, std::placeholders::_1));
        velocity_intent_pub_ = create_publisher<ship_interfaces::msg::VelocityIntent>("/gnc/velocity_intent", 10);
        velocity_intent_sub_ = create_subscription<ship_interfaces::msg::VelocityIntent>(
            "/colav/velocity_intent", 10,
            std::bind(&ActiveRouteManagerNode::velocity_intent_callback, this, std::placeholders::_1));
        ship_state_sub_ = create_subscription<ship_interfaces::msg::GeoPosition>(
            ship_state_topic_, 10,
            std::bind(&ActiveRouteManagerNode::ship_state_callback, this, std::placeholders::_1));
        route_plan_status_sub_ = create_subscription<ship_interfaces::msg::RoutePlanStatus>(
            route_plan_status_topic_, 10,
            std::bind(&ActiveRouteManagerNode::route_plan_status_callback, this, std::placeholders::_1));
        maintenance_timer_ = create_wall_timer(
            std::chrono::milliseconds(500),
            std::bind(&ActiveRouteManagerNode::maintenance_callback, this));

        RCLCPP_INFO(
            get_logger(),
            "[ActiveRouteManager] nominal=%s avoidance=%s berthing=%s active=%s status=%s berthing_arbitration=%s",
            nominal_route_topic_.c_str(), avoidance_plan_topic_.c_str(),
            berthing_candidate_route_topic_.c_str(), active_route_topic_.c_str(),
            execution_status_topic_.c_str(), enable_berthing_arbitration_ ? "enabled" : "disabled");
    }

private:
    void ship_state_callback(const ship_interfaces::msg::GeoPosition::SharedPtr msg)
    {
        latest_ship_state_ = *msg;
        has_ship_state_ = true;
    }

    void nominal_route_callback(const ship_interfaces::msg::RoutePlan::SharedPtr msg)
    {
        auto route = *msg;
        ensure_route_identity(route, "nominal");
        const auto contract = ship_guidance::route_contract::validate_and_normalize(
            route, ship_guidance::route_contract::RouteKind::Nominal);
        if (!contract.valid) {
            publish_status_for_route(
                route, rejected_result(contract.reason, contract.suggested_action));
            return;
        }
        if (is_stale_nominal_version(route)) {
            publish_status_for_route(
                route, rejected_result("stale_route_version", "increase_header_stamp_or_route_id"));
            return;
        }

        latest_nominal_route_ = route;
        has_nominal_route_ = true;
        if (avoidance_is_active()) {
            auto result = accepted_result();
            result.executing = false;
            result.state = "DEFERRED";
            result.reason = "avoidance_active";
            result.suggested_action = "wait_until_avoidance_complete";
            publish_status_for_route(route, result);
            RCLCPP_INFO_THROTTLE(
                get_logger(), *get_clock(), 3000,
                "[ActiveRouteManager] deferred nominal route_id='%s' while avoidance plan_id='%s' is active",
                route.route_id.c_str(), active_avoidance_plan_id_.c_str());
            return;
        }

        if (berthing_abort_latched_) {
            auto result = accepted_result();
            result.executing = false;
            result.state = "DEFERRED";
            result.reason = "berthing_abort_latched";
            result.suggested_action = "clear_abort_or_send_new_task";
            publish_status_for_route(route, result);
            return;
        }
        if (has_active_berthing_) {
            auto result = accepted_result();
            result.executing = false;
            result.state = "DEFERRED";
            result.reason = "berthing_route_active";
            result.suggested_action = "wait_until_join_route_complete";
            publish_status_for_route(route, result);
            return;
        }
        if (enable_berthing_arbitration_ && route_contains_berthing_segment(route)) {
            awaiting_berthing_candidate_ = true;
            berthing_candidate_deadline_ = now() +
                rclcpp::Duration::from_seconds(berthing_candidate_timeout_s_);
            auto result = accepted_result();
            result.executing = false;
            result.state = "WAITING_FOR_BERTHING_CANDIDATE";
            result.reason = "berthing_segment_detected";
            result.suggested_action = "publish_valid_berthing_candidate";
            publish_status_for_route(route, result);
            if (has_pending_berthing_candidate_) {
                try_activate_berthing_candidate(latest_berthing_candidate_);
            }
            return;
        }

        auto result = accepted_result();
        result.executing = false;
        result.state = "FORWARDED_FOR_VALIDATION";
        result.reason = contract.reason;
        set_active_route_context(route, "route_planner", result);
        active_route_pub_->publish(route);
        if (publish_nominal_status_) {
            publish_status_for_route(route, result);
        }

        RCLCPP_INFO(
            get_logger(), "[ActiveRouteManager] forwarded nominal route_id='%s' points=%zu contract=%s",
            route.route_id.c_str(), route.latitude.size(), contract.reason.c_str());
    }

    void avoidance_plan_callback(const ship_interfaces::msg::AvoidancePlan::SharedPtr msg)
    {
        const std::string behavior_mode = normalize_mode(msg->behavior_mode);
        const std::string command_source =
            msg->command_source.empty() ? "collision_avoidance" : msg->command_source;
        if (behavior_mode == "return_to_route") {
            publish_return_to_preempted_route(
                msg->plan_id.empty() ? "return_request" : msg->plan_id,
                command_source,
                "return_requested");
            return;
        }

        const bool emergency =
            ship_guidance::route_arbitration_policy::emergency_behavior(behavior_mode);
        if (!has_nominal_route_ ||
            !ship_guidance::route_arbitration_policy::parent_binding_matches(
                msg->parent_route_id,
                msg->parent_route_revision,
                latest_nominal_route_.route_id,
                latest_nominal_route_.route_revision)) {
            publish_status_for_avoidance(
                *msg,
                rejected_result(
                    "avoidance_parent_route_version_mismatch",
                    "bind_plan_to_active_nominal_route_revision"));
            return;
        }
        if (enable_berthing_arbitration_ && !emergency &&
            ship_guidance::route_arbitration_policy::ordinary_avoidance_blocked(
                normalize_mode(latest_berthing_state_))) {
            publish_status_for_avoidance(
                *msg,
                rejected_result(
                    "ordinary_avoidance_blocked_during_berthing_transition",
                    "wait_for_clear_ahead_or_send_emergency_avoidance"));
            return;
        }

        const auto now = get_clock()->now();
        if (time_is_zero(msg->valid_until)) {
            publish_status_for_avoidance(
                *msg,
                rejected_result("plan_valid_until_required", "send_plan_with_valid_until"));
            return;
        }
        if (rclcpp::Time(msg->valid_until) <= now) {
            auto result = rejected_result("plan_expired", "send_fresh_plan");
            publish_status_for_avoidance(*msg, result);
            RCLCPP_WARN(get_logger(), "[ActiveRouteManager] rejected expired avoidance plan_id='%s'",
                msg->plan_id.c_str());
            return;
        }

        auto route = to_route_plan(*msg);
        ensure_route_identity(route, "avoidance");
        const auto contract = ship_guidance::route_contract::validate_and_normalize(
            route, ship_guidance::route_contract::RouteKind::Temporary);
        if (!contract.valid) {
            auto result = rejected_result(contract.reason, contract.suggested_action);
            publish_status_for_avoidance(*msg, result);
            return;
        }

        auto result = evaluate_avoidance_plan(*msg, route);
        if (!result.accepted) {
            publish_status_for_avoidance(*msg, result);
            RCLCPP_WARN(
                get_logger(),
                "[ActiveRouteManager] rejected avoidance plan_id='%s' reason=%s",
                msg->plan_id.c_str(), result.reason.c_str());
            return;
        }

        clear_velocity_intent();
        apply_speed_degradation(route, result.admitted_speed_limits_mps);
        set_active_route_context(route, command_source, result);
        active_route_pub_->publish(route);
        mark_avoidance_active(*msg);
        publish_status_for_avoidance(*msg, result);

        RCLCPP_INFO(
            get_logger(),
            "[ActiveRouteManager] accepted avoidance plan_id='%s' points=%zu state=%s reason=%s speed_cap=%.2f",
            msg->plan_id.c_str(), route.latitude.size(), result.state.c_str(),
            result.reason.c_str(), result.suggested_max_speed_mps);
    }

    void clear_velocity_intent()
    {
        if (!has_active_velocity_intent_) return;
        auto clear = active_velocity_intent_;
        clear.header.stamp = now();
        clear.behavior_mode = "return_to_route";
        velocity_intent_pub_->publish(clear);
        has_active_velocity_intent_ = false;
        velocity_expiry_reported_ = false;
    }

    void velocity_intent_callback(const ship_interfaces::msg::VelocityIntent::SharedPtr msg)
    {
        ship_interfaces::msg::AvoidancePlan identity;
        identity.plan_id = msg->intent_id;
        identity.parent_route_id = msg->parent_route_id;
        identity.parent_route_revision = msg->parent_route_revision;
        identity.command_source = msg->command_source;
        identity.valid_until = msg->valid_until;
        const std::string mode = normalize_mode(msg->behavior_mode);
        identity.behavior_mode = mode;
        auto reject = [&](const std::string& reason) {
            publish_status_for_avoidance(identity, rejected_result(reason, "send_valid_velocity_intent"));
        };
        if (!has_nominal_route_ || !ship_guidance::route_arbitration_policy::parent_binding_matches(
                msg->parent_route_id, msg->parent_route_revision,
                latest_nominal_route_.route_id, latest_nominal_route_.route_revision)) {
            reject("velocity_parent_route_version_mismatch"); return;
        }
        if (mode == "return_to_route") {
            publish_return_to_preempted_route(msg->intent_id, msg->command_source, "velocity_return_requested");
            return;
        }
        const bool emergency = ship_guidance::route_arbitration_policy::emergency_behavior(mode);
        if (!ship_guidance::avoidance_mode_policy::velocity(mode) || msg->intent_id.empty() ||
            msg->speed_reference != "SOG" || !std::isfinite(msg->course_rad) ||
            !std::isfinite(msg->speed_mps) || msg->speed_mps < 0.0 || msg->speed_mps > max_command_speed_mps_) {
            reject("invalid_velocity_intent"); return;
        }
        if (time_is_zero(msg->valid_until) || rclcpp::Time(msg->valid_until) <= now() ||
            rclcpp::Time(msg->header.stamp) > now()) {
            reject("velocity_intent_expired_or_future"); return;
        }
        if (has_active_velocity_intent_ && rclcpp::Time(msg->header.stamp) < rclcpp::Time(active_velocity_intent_.header.stamp)) {
            reject("velocity_intent_out_of_order"); return;
        }
        if (enable_berthing_arbitration_ && !emergency &&
            ship_guidance::route_arbitration_policy::ordinary_avoidance_blocked(normalize_mode(latest_berthing_state_))) {
            reject("ordinary_velocity_blocked_during_berthing_transition"); return;
        }
        active_velocity_intent_ = *msg;
        has_active_velocity_intent_ = true;
        velocity_expiry_reported_ = false;
        mark_avoidance_active(identity);
        velocity_intent_pub_->publish(*msg);
        FeasibilityResult result;
        result.accepted = true;
        result.executing = true;
        result.rejected = false;
        result.suggested_action = "none";
        result.state = "VELOCITY_INTENT_ACCEPTED";
        result.reason = "velocity_intent_authorized";
        result.requested_speed_mps = msg->speed_mps;
        result.applied_speed_mps = msg->speed_mps;
        result.suggested_max_speed_mps = max_command_speed_mps_;
        publish_status_for_avoidance(identity, result);
    }

    static bool route_contains_berthing_segment(
        const ship_interfaces::msg::RoutePlan& route)
    {
        return std::any_of(
            route.navigation_mode.begin(), route.navigation_mode.end(),
            [](const std::string& mode) {
                const auto normalized = normalize_mode(mode);
                return normalized == "berth_departure" ||
                    normalized == "departure" || normalized == "undocking" ||
                    normalized == "berthing";
            });
    }

    static bool berthing_state_allows_route(const std::string& state)
    {
        const auto normalized = normalize_mode(state);
        return ship_guidance::route_arbitration_policy::candidate_state_authorized(
            normalized);
    }

    bool berthing_candidate_matches_nominal(
        const ship_interfaces::msg::RoutePlan& route) const
    {
        if (!has_nominal_route_) {
            return false;
        }
        const std::string prefix = latest_nominal_route_.route_id + ":berthing:";
        return route.route_id.rfind(prefix, 0) == 0 &&
            route.route_revision == latest_nominal_route_.route_revision;
    }

    FeasibilityResult validate_berthing_candidate(
        ship_interfaces::msg::RoutePlan& route) const
    {
        const auto contract = ship_guidance::route_contract::validate_and_normalize(
            route, ship_guidance::route_contract::RouteKind::Temporary);
        if (!contract.valid) {
            return rejected_result(contract.reason, contract.suggested_action);
        }
        if (!berthing_candidate_matches_nominal(route)) {
            return rejected_result(
                "berthing_parent_route_mismatch",
                "bind_candidate_route_id_to_active_nominal_route");
        }
        if (!time_is_zero(route.header.stamp)) {
            const double age_s = (now() - rclcpp::Time(route.header.stamp)).seconds();
            if (age_s < -1.0 || age_s > berthing_candidate_timeout_s_) {
                return rejected_result("berthing_candidate_stale", "publish_fresh_candidate");
            }
        }
        bool has_departure = false;
        bool has_join = false;
        bool has_nominal_tail = false;
        bool tail_started = false;
        for (size_t index = 0; index < route.latitude.size(); ++index) {
            const auto mode = normalize_mode(route.navigation_mode[index]);
            const bool low_speed_phase =
                mode == "berth_departure" || mode == "join_route";
            const bool nominal_tail_mode =
                ship_guidance::route_arbitration_policy::nominal_tail_mode_allowed(mode);
            if (mode == "berth_departure") {
                if (tail_started) {
                    return rejected_result(
                        "berthing_phase_after_nominal_tail",
                        "keep_berthing_phases_before_nominal_tail");
                }
                has_departure = true;
            } else if (mode == "join_route") {
                if (tail_started) {
                    return rejected_result(
                        "join_phase_after_nominal_tail",
                        "keep_join_phase_before_nominal_tail");
                }
                has_join = true;
            } else if (nominal_tail_mode) {
                tail_started = true;
                has_nominal_tail = true;
            } else {
                return rejected_result(
                    "unsupported_berthing_candidate_mode",
                    "use_berthing_join_and_nominal_modes_only");
            }
            const double speed = route.speed_limit_mps[index];
            if (!std::isfinite(speed) || speed < 0.0 ||
                (low_speed_phase && speed > max_berthing_speed_mps_ + 1e-9)) {
                auto result = rejected_result(
                    "berthing_speed_exceeds_limit",
                    "reduce_berthing_candidate_speed");
                result.requested_speed_mps = speed;
                result.suggested_max_speed_mps = max_berthing_speed_mps_;
                return result;
            }
        }
        if (!has_departure || !has_join || !has_nominal_tail) {
            return rejected_result(
                "berthing_candidate_phase_incomplete",
                "include_departure_join_and_nominal_tail_segments");
        }
        auto result = accepted_result();
        result.state = "BERTHING_ROUTE_ACCEPTED";
        result.reason = contract.reason;
        result.requested_speed_mps = max_requested_speed(route);
        result.applied_speed_mps = result.requested_speed_mps;
        result.suggested_max_speed_mps = max_berthing_speed_mps_;
        return result;
    }

    bool try_activate_berthing_candidate(
        ship_interfaces::msg::RoutePlan route)
    {
        ensure_route_identity(route, "berthing");
        if (!enable_berthing_arbitration_) {
            return false;
        }
        if (!has_nominal_route_) {
            publish_status_for_route(
                route,
                rejected_result("nominal_route_unavailable", "publish_parent_route_first"),
                "berthing_task");
            return false;
        }
        if (!berthing_state_allows_route(latest_berthing_state_)) {
            publish_status_for_route(
                route,
                rejected_result("berthing_state_not_authorized", "enter_bow_out_state_first"),
                "berthing_task");
            return false;
        }
        if (berthing_abort_latched_) {
            publish_status_for_route(
                route,
                rejected_result("berthing_abort_latched", "clear_abort_or_send_new_task"),
                "berthing_task");
            return false;
        }
        auto result = validate_berthing_candidate(route);
        if (!result.accepted) {
            publish_status_for_route(route, result, "berthing_task");
            return false;
        }
        latest_berthing_candidate_ = route;
        has_pending_berthing_candidate_ = true;
        if (avoidance_is_active()) {
            result.executing = false;
            result.state = "DEFERRED";
            result.reason = "avoidance_active";
            result.suggested_action = "wait_until_avoidance_complete";
            publish_status_for_route(route, result, "berthing_task");
            return false;
        }
        awaiting_berthing_candidate_ = false;
        has_active_berthing_ = true;
        set_active_route_context(route, "berthing_task", result);
        active_route_pub_->publish(route);
        publish_status_for_route(route, result, "berthing_task");
        RCLCPP_INFO(
            get_logger(),
            "[ActiveRouteManager] activated berthing route_id='%s' points=%zu state=%s",
            route.route_id.c_str(), route.latitude.size(), latest_berthing_state_.c_str());
        return true;
    }

    void berthing_candidate_callback(
        const ship_interfaces::msg::RoutePlan::SharedPtr msg)
    {
        latest_berthing_candidate_ = *msg;
        has_pending_berthing_candidate_ = true;
        try_activate_berthing_candidate(*msg);
    }

    void berthing_state_callback(const std_msgs::msg::String::SharedPtr msg)
    {
        latest_berthing_state_ = normalize_mode(msg->data);
        if (latest_berthing_state_ == "berthed" && !has_active_berthing_) {
            berthing_abort_latched_ = false;
        }
        if (latest_berthing_state_ == "task_aborted" ||
            latest_berthing_state_ == "abort") {
            awaiting_berthing_candidate_ = false;
            berthing_abort_latched_ = true;
            if (has_active_berthing_) {
                auto result = accepted_result();
                result.executing = false;
                result.state = "BERTHING_ABORTED_ROUTE_LATCHED";
                result.reason = "berthing_abort_requested";
                result.suggested_action = "safety_stop_and_operator_review";
                publish_status_for_route(active_route_, result, "berthing_task");
            }
            has_active_berthing_ = false;
            return;
        }
        if (berthing_state_allows_route(latest_berthing_state_) &&
            has_pending_berthing_candidate_ && !has_active_berthing_ &&
            !avoidance_is_active()) {
            try_activate_berthing_candidate(latest_berthing_candidate_);
        }
        if ((latest_berthing_state_ == "handover_complete" ||
             latest_berthing_state_ == "cruise") && has_active_berthing_) {
            const std::string completed_route_id = active_route_id_;
            if (publish_return_to_nominal(
                    completed_route_id, "berthing_task", "berthing_join_complete")) {
                has_active_berthing_ = false;
                has_pending_berthing_candidate_ = false;
                berthing_abort_latched_ = false;
            } else {
                RCLCPP_ERROR(
                    get_logger(),
                    "[ActiveRouteManager] berthing handover return failed; "
                    "keeping candidate route active route_id='%s'",
                    completed_route_id.c_str());
            }
        }
    }

    void ensure_route_identity(
        ship_interfaces::msg::RoutePlan& route,
        const std::string& prefix)
    {
        if (time_is_zero(route.header.stamp)) {
            route.header.stamp = now();
        }
        if (route.route_id.empty()) {
            route.route_id = prefix + "-" + std::to_string(++generated_route_sequence_);
        }
    }

    bool is_stale_nominal_version(const ship_interfaces::msg::RoutePlan& route) const
    {
        if (!has_nominal_route_ || route.route_id != latest_nominal_route_.route_id) {
            return false;
        }
        if (route.route_revision > 0 || latest_nominal_route_.route_revision > 0) {
            if (route.route_revision == 0 && latest_nominal_route_.route_revision > 0) {
                return true;
            }
            return route.route_revision <= latest_nominal_route_.route_revision;
        }
        if (time_is_zero(route.header.stamp) ||
            time_is_zero(latest_nominal_route_.header.stamp)) {
            return false;
        }
        return rclcpp::Time(route.header.stamp) <
            rclcpp::Time(latest_nominal_route_.header.stamp);
    }

    void set_active_route_context(
        const ship_interfaces::msg::RoutePlan& route,
        const std::string& command_source,
        const FeasibilityResult& result)
    {
        active_route_ = route;
        active_route_id_ = route.route_id;
        active_command_source_ = command_source;
        last_active_result_ = result;
    }

    void route_plan_status_callback(
        const ship_interfaces::msg::RoutePlanStatus::SharedPtr msg)
    {
        if (active_route_id_.empty() || msg->route_id != active_route_id_) {
            return;
        }

        auto result = last_active_result_;
        result.accepted = msg->accepted;
        result.executing = msg->accepted;
        result.rejected = !msg->accepted;
        if (msg->accepted) {
            admitted_route_ = active_route_;
            result.state = msg->status == "IGNORED_DUPLICATE"
                ? "EXECUTING"
                : msg->status;
            result.reason = msg->reason;
            result.suggested_action = "none";
        } else {
            result.state = "REJECTED_BY_ROUTE_INGRESS";
            result.reason = msg->reason;
            result.suggested_action = "fix_or_resend_route";
        }
        last_active_result_ = result;
        publish_status_for_route(
            active_route_, result, active_command_source_);
    }

    bool publish_return_to_berthing(
        const std::string& request_id,
        const std::string& command_source,
        const std::string& trigger_reason)
    {
        has_active_avoidance_ = false;
        active_avoidance_plan_id_.clear();
        if (!has_active_berthing_ || !has_pending_berthing_candidate_ || !has_ship_state_) {
            return false;
        }
        ship_interfaces::msg::RoutePlan return_route;
        const std::string return_route_id =
            latest_berthing_candidate_.route_id + ":resume:" +
            std::to_string(++generated_route_sequence_);
        if (!ship_guidance::route_contract::build_return_route(
                latest_berthing_candidate_, latest_ship_state_.latitude,
                latest_ship_state_.longitude, return_route_id, return_route)) {
            return false;
        }
        return_route.header.stamp = now();
        auto result = accepted_result();
        result.state = "RETURNING_TO_BERTHING_ROUTE";
        result.reason = trigger_reason;
        result.suggested_action = "monitor_berthing_rejoin";
        set_active_route_context(return_route, command_source, result);
        active_route_pub_->publish(return_route);
        publish_status_for_route(return_route, result, command_source);
        RCLCPP_INFO(
            get_logger(),
            "[ActiveRouteManager] resume berthing request='%s' active='%s' points=%zu",
            request_id.c_str(), return_route.route_id.c_str(), return_route.latitude.size());
        return true;
    }

    bool publish_return_to_preempted_route(
        const std::string& request_id,
        const std::string& command_source,
        const std::string& trigger_reason)
    {
        clear_velocity_intent();
        if (has_active_berthing_ && berthing_state_allows_route(latest_berthing_state_) &&
            publish_return_to_berthing(request_id, command_source, trigger_reason)) {
            return true;
        }
        return publish_return_to_nominal(request_id, command_source, trigger_reason);
    }

    bool publish_return_to_nominal(
        const std::string& request_id,
        const std::string& command_source,
        const std::string& trigger_reason)
    {
        const std::string previous_avoidance_id = active_avoidance_plan_id_;
        has_active_avoidance_ = false;
        active_avoidance_plan_id_.clear();

        if (!has_nominal_route_) {
            ship_interfaces::msg::RoutePlan failed_route;
            failed_route.route_id = request_id;
            publish_status_for_route(
                failed_route,
                rejected_result("no_nominal_route_for_return", "publish_nominal_route_first"),
                command_source);
            return false;
        }
        if (!has_ship_state_) {
            ship_interfaces::msg::RoutePlan failed_route;
            failed_route.route_id = request_id;
            publish_status_for_route(
                failed_route,
                rejected_result("ship_state_unavailable_for_return", "wait_for_fresh_ship_state"),
                command_source);
            return false;
        }

        ship_interfaces::msg::RoutePlan return_route;
        const std::string return_route_id =
            latest_nominal_route_.route_id + ":return:" +
            std::to_string(++generated_route_sequence_);
        const bool berthing_handover =
            command_source == "berthing_task" &&
            trigger_reason == "berthing_join_complete";
        if (!ship_guidance::route_contract::build_return_route(
                latest_nominal_route_,
                latest_ship_state_.latitude,
                latest_ship_state_.longitude,
                return_route_id,
                return_route,
                berthing_handover
                    ? berthing_handover_entry_speed_mps_
                    : std::numeric_limits<double>::infinity(),
                berthing_handover
                    ? berthing_handover_min_lookahead_m_
                    : 0.0,
                berthing_handover
                    ? berthing_handover_max_intercept_angle_deg_
                    : 90.0,
                berthing_handover
                    ? berthing_handover_ramp_accel_mps2_
                    : std::numeric_limits<double>::infinity(),
                berthing_handover
                    ? berthing_handover_ramp_spacing_m_
                    : 0.0)) {
            ship_interfaces::msg::RoutePlan failed_route;
            failed_route.route_id = request_id;
            publish_status_for_route(
                failed_route,
                rejected_result("return_route_generation_failed", "publish_new_nominal_route"),
                command_source);
            return false;
        }

        return_route.header.stamp = now();
        auto result = accepted_result();
        result.state = berthing_handover
            ? "BERTHING_HANDOVER_TO_NOMINAL"
            : "RETURNING_TO_NOMINAL";
        result.reason = trigger_reason;
        result.suggested_action = "monitor_rejoin";
        set_active_route_context(return_route, command_source, result);
        active_route_pub_->publish(return_route);
        publish_status_for_route(return_route, result, command_source);
        RCLCPP_INFO(
            get_logger(),
            "[ActiveRouteManager] return route published request='%s' avoidance='%s' "
            "active='%s' points=%zu berthing_handover=%s first_speed=%.2f",
            request_id.c_str(), previous_avoidance_id.c_str(),
            return_route.route_id.c_str(), return_route.latitude.size(),
            berthing_handover ? "true" : "false",
            return_route.speed_limit_mps.empty() ? 0.0 : return_route.speed_limit_mps.front());
        return true;
    }

    void maintenance_callback()
    {
        if (has_active_velocity_intent_ && now() > active_avoidance_until_) {
            if (!velocity_expiry_reported_) {
                ship_interfaces::msg::AvoidancePlan identity;
                identity.plan_id = active_velocity_intent_.intent_id;
                identity.parent_route_id = active_velocity_intent_.parent_route_id;
                identity.parent_route_revision = active_velocity_intent_.parent_route_revision;
                publish_status_for_avoidance(identity,
                    rejected_result("velocity_intent_expired", "send_fresh_intent_or_explicit_return"));
                velocity_expiry_reported_ = true;
            }
        } else if (has_active_avoidance_ && now() > active_avoidance_until_) {
            publish_return_to_preempted_route(
                active_avoidance_plan_id_,
                "collision_avoidance",
                "avoidance_validity_expired");
        }
        if (awaiting_berthing_candidate_ && now() > berthing_candidate_deadline_) {
            awaiting_berthing_candidate_ = false;
            if (has_nominal_route_) {
                publish_status_for_route(
                    latest_nominal_route_,
                    rejected_result(
                        "berthing_candidate_timeout",
                        "keep_stopped_and_publish_valid_candidate"));
            }
        }
    }

    bool basic_route_valid(const ship_interfaces::msg::RoutePlan& route) const
    {
        return route.latitude.size() >= 2 &&
            route.latitude.size() == route.longitude.size() &&
            (route.speed_limit_mps.empty() || route.speed_limit_mps.size() == route.latitude.size()) &&
            (route.navigation_mode.empty() || route.navigation_mode.size() == route.latitude.size());
    }

    bool avoidance_is_active() const
    {
        return has_active_avoidance_ && now() <= active_avoidance_until_;
    }

    void mark_avoidance_active(const ship_interfaces::msg::AvoidancePlan& plan)
    {
        has_active_avoidance_ = true;
        active_avoidance_plan_id_ = plan.plan_id;
        if (!time_is_zero(plan.valid_until)) {
            active_avoidance_until_ = rclcpp::Time(plan.valid_until);
        } else {
            active_avoidance_until_ = now() + rclcpp::Duration::from_seconds(default_avoidance_hold_s_);
        }
    }

    ship_interfaces::msg::RoutePlan to_route_plan(
        const ship_interfaces::msg::AvoidancePlan& plan) const
    {
        ship_interfaces::msg::RoutePlan route;
        route.header = plan.header;
        route.route_id = plan.plan_id.empty() ? "avoidance_plan" : plan.plan_id;
        route.route_revision = plan.parent_route_revision;
        route.route_type = plan.behavior_mode.empty() ? "avoidance" : normalize_mode(plan.behavior_mode);
        route.latitude = plan.latitude;
        route.longitude = plan.longitude;
        route.speed_limit_mps = plan.command_speed_mps;
        route.navigation_mode = plan.navigation_mode;
        if (normalize_mode(plan.behavior_mode) == "planner_trajectory_v1") {
            route.trajectory_dt_s = plan.trajectory_dt_s;
            route.trajectory_reference_id = plan.trajectory_reference_id;
            route.trajectory_course_deg = plan.command_heading_deg;
            route.trajectory_valid_for_s =
                (rclcpp::Time(plan.valid_until) - rclcpp::Time(plan.header.stamp)).seconds();
        }

        return route;
    }

    FeasibilityResult evaluate_planner_trajectory(
        const ship_interfaces::msg::AvoidancePlan& plan,
        const ship_interfaces::msg::RoutePlan& route) const
    {
        namespace contract = ship_guidance::planner_trajectory_contract;
        if (plan.command_source != "mid_mpc_ipopt" || !has_ship_state_ ||
            !latest_ship_state_.origin_locked || time_is_zero(plan.header.stamp)) {
            return rejected_result("trajectory_source_or_state_invalid", "provide_current_planner_state");
        }
        if (route.trajectory_course_deg.size() != route.latitude.size() ||
            route.speed_limit_mps.size() != route.latitude.size() ||
            !std::isfinite(route.trajectory_valid_for_s) || route.trajectory_valid_for_s <= 0.0 ||
            route.trajectory_valid_for_s > (route.latitude.size() - 1) * route.trajectory_dt_s ||
            rclcpp::Time(plan.header.stamp) > get_clock()->now()) {
            return rejected_result("trajectory_metadata_invalid", "provide_aligned_timed_samples");
        }
        const bool renewal = route.route_id == admitted_route_.route_id;
        if (renewal) {
            if (route.latitude != admitted_route_.latitude || route.longitude != admitted_route_.longitude ||
                route.speed_limit_mps != admitted_route_.speed_limit_mps ||
                route.navigation_mode != admitted_route_.navigation_mode ||
                route.trajectory_course_deg != admitted_route_.trajectory_course_deg ||
                route.trajectory_dt_s != admitted_route_.trajectory_dt_s ||
                rclcpp::Time(route.header.stamp) != rclcpp::Time(admitted_route_.header.stamp)) {
                return rejected_result("trajectory_identity_changed", "issue_a_new_plan_identity");
            }
        } else if (route.trajectory_reference_id.empty() ||
                   route.trajectory_reference_id != admitted_route_.route_id) {
            return rejected_result("trajectory_reference_stale", "bind_to_admitted_route");
        }
        std::vector<contract::Sample> samples;
        samples.reserve(route.latitude.size());
        for (std::size_t i = 0; i < route.latitude.size(); ++i) {
            double north = 0.0, east = 0.0;
            if (!ship_guidance::geodesy::wgs84_to_ned(latest_ship_state_.origin_lat,
                    latest_ship_state_.origin_lon, route.latitude[i], route.longitude[i], north, east)) {
                return rejected_result("trajectory_projection_failed", "provide_local_WGS84_trajectory");
            }
            samples.push_back({north, east, route.trajectory_course_deg[i] * kDegToRad, route.speed_limit_mps[i]});
        }
        if (!renewal && !contract::initial_state_matches(samples.front(),
                {latest_ship_state_.x_ned, latest_ship_state_.y_ned, latest_ship_state_.course_deg * kDegToRad, latest_ship_state_.speed_mps})) {
            return rejected_result("trajectory_initial_state_mismatch", "replan_from_current_state");
        }
        const auto reason = contract::validate(samples, route.trajectory_dt_s,
            {max_command_speed_mps_, max_yaw_rate_deg_s_ * kDegToRad, max_decel_mps2_,
             max_lateral_accel_mps2_, min_turn_radius_m_});
        if (!reason.empty()) return rejected_result(reason, "replan_with_source_motion_limits");
        auto result = accepted_result();
        result.reason = "planner_trajectory_validated";
        result.admitted_speed_limits_mps = route.speed_limit_mps;
        result.requested_speed_mps = max_requested_speed(route);
        result.applied_speed_mps = result.requested_speed_mps;
        result.requested_heading_deg = route.trajectory_course_deg.front();
        result.applied_heading_deg = result.requested_heading_deg;
        return result;
    }

    FeasibilityResult evaluate_avoidance_plan(
        const ship_interfaces::msg::AvoidancePlan& plan,
        const ship_interfaces::msg::RoutePlan& route) const
    {
        if (!basic_route_valid(route)) {
            return rejected_result("invalid_avoidance_route", "fix_route_plan");
        }
        if (normalize_mode(plan.behavior_mode) == "planner_trajectory_v1") {
            return evaluate_planner_trajectory(plan, route);
        }
        if (!plan.command_heading_deg.empty() &&
            plan.command_heading_deg.size() != route.latitude.size()) {
            return rejected_result("heading_length_mismatch", "fix_heading_array");
        }
        if (std::any_of(
                plan.command_heading_deg.begin(),
                plan.command_heading_deg.end(),
                [](double heading) { return !std::isfinite(heading); })) {
            return rejected_result("invalid_command_heading", "use_finite_heading_degrees");
        }
        if (!plan.command_speed_mps.empty() &&
            plan.command_speed_mps.size() != route.latitude.size()) {
            return rejected_result("speed_length_mismatch", "fix_speed_array");
        }

        const bool emergency = is_emergency_mode(plan.behavior_mode) ||
            std::any_of(route.navigation_mode.begin(), route.navigation_mode.end(), is_emergency_mode);
        const double min_segment = emergency ? emergency_min_segment_length_m_ : min_segment_length_m_;
        const double static_min_turn_radius =
            emergency ? emergency_min_turn_radius_m_ : min_turn_radius_m_;
        const double yaw_rate_limit_rad_s =
            (emergency ? emergency_max_yaw_rate_deg_s_ : max_yaw_rate_deg_s_) * kDegToRad;

        auto points = route_to_local_points(route);
        if (points.size() < 2) {
            return rejected_result("projection_failed", "check_coordinates");
        }

        FeasibilityResult result = accepted_result();
        result.reason = "feasible";
        result.suggested_action = "none";
        result.requested_speed_mps = max_requested_speed(route);
        result.applied_speed_mps = std::min(result.requested_speed_mps, max_command_speed_mps_);
        result.suggested_max_speed_mps = result.applied_speed_mps;
        result.admitted_speed_limits_mps.reserve(points.size());
        for (size_t i = 0; i < points.size(); ++i) {
            result.admitted_speed_limits_mps.push_back(requested_speed_at(route, i));
        }
        if (!plan.command_heading_deg.empty()) {
            result.requested_heading_deg = clamp_angle_deg(plan.command_heading_deg.front());
            result.applied_heading_deg = result.requested_heading_deg;
        }

        for (double requested_speed : route.speed_limit_mps) {
            if (requested_speed > max_command_speed_mps_) {
                if (plan.require_exact_speed) {
                    auto rejected = rejected_result(
                        "speed_exceeds_vessel_limit",
                        "reduce_command_speed");
                    rejected.requested_speed_mps = requested_speed;
                    rejected.suggested_max_speed_mps = max_command_speed_mps_;
                    return rejected;
                }
                result.degraded = true;
                result.state = "EXECUTING_WITH_LIMIT";
                result.reason = "speed_limited_by_vessel";
                result.suggested_action = "reduce_command_speed";
            }
        }

        if (plan.require_exact_heading && !plan.command_heading_deg.empty()) {
            for (size_t i = 0; i + 1 < points.size(); ++i) {
                const double path_heading_deg = clamp_angle_deg(
                    std::atan2(
                        points[i + 1].y - points[i].y,
                        points[i + 1].x - points[i].x) * kRadToDeg);
                double error_deg = std::abs(
                    clamp_angle_deg(plan.command_heading_deg[i]) - path_heading_deg);
                error_deg = std::min(error_deg, 360.0 - error_deg);
                if (error_deg > max_heading_path_error_deg_) {
                    auto rejected = rejected_result(
                        "heading_path_conflict",
                        "align_heading_command_with_route_geometry");
                    rejected.requested_heading_deg =
                        clamp_angle_deg(plan.command_heading_deg[i]);
                    rejected.applied_heading_deg = path_heading_deg;
                    return rejected;
                }
            }
        }

        // Planner-owned dense stitch geometry must reach the guidance chain
        // point-for-point: rejecting it here would expire the previous plan
        // into the 3-point internal return route and collapse the route
        // mirror. Every other admission gate below still applies, emergency
        // plans keep the 15 m floor, and operator/collision-avoidance plans
        // keep the legacy reject.
        const bool planner_owned_plan =
            planner_route_min_segment_skip_ && !emergency &&
            plan.command_source == "mid_mpc_ipopt";
        bool tolerated_short_segment_logged = false;
        for (size_t i = 0; i + 1 < points.size(); ++i) {
            const double seg_len = distance(points[i], points[i + 1]);
            if (seg_len < min_segment) {
                if (planner_owned_plan) {
                    if (!tolerated_short_segment_logged) {
                        RCLCPP_WARN(
                            get_logger(),
                            "[ActiveRouteManager] plan_id='%s' planner-owned segment %.3fm < %.1fm tolerated; dense stitch geometry kept point-for-point",
                            plan.plan_id.c_str(),
                            seg_len,
                            min_segment);
                        tolerated_short_segment_logged = true;
                    }
                    continue;
                }
                auto rejected = rejected_result("segment_too_short", "increase_segment_length");
                rejected.available_decel_distance_m = seg_len;
                rejected.suggested_min_distance_m = min_segment;
                return rejected;
            }
        }

        for (size_t i = 1; i + 1 < points.size(); ++i) {
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
                result.admitted_speed_limits_mps[i] =
                    std::min(result.admitted_speed_limits_mps[i], safe_speed);
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

        for (size_t i = 0; i + 1 < points.size(); ++i) {
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

        result.rejected = false;
        result.accepted = true;
        result.executing = true;
        if (!result.degraded) {
            result.state = "ACCEPTED";
        }
        // A local turn limit is not a permanent cruise limit. Propagate only
        // the necessary braking envelope upstream; keep later requested speeds.
        for (size_t i = points.size() - 1; i > 0; --i) {
            const double next = result.admitted_speed_limits_mps[i];
            const double upstream = std::sqrt(next * next +
                2.0 * max_decel_mps2_ * distance(points[i - 1], points[i]));
            result.admitted_speed_limits_mps[i - 1] =
                std::min(result.admitted_speed_limits_mps[i - 1], upstream);
        }
        result.applied_speed_mps = *std::max_element(
            result.admitted_speed_limits_mps.begin(), result.admitted_speed_limits_mps.end());
        return result;
    }

    std::vector<LocalPoint> route_to_local_points(const ship_interfaces::msg::RoutePlan& route) const
    {
        std::vector<LocalPoint> points;
        if (route.latitude.empty() || route.latitude.size() != route.longitude.size()) {
            return points;
        }
        const double lat0 = route.latitude.front();
        const double lon0 = route.longitude.front();
        const double meters_per_deg_lat = 111320.0;
        const double meters_per_deg_lon = 111320.0 * std::cos(lat0 * kDegToRad);
        points.reserve(route.latitude.size());
        for (size_t i = 0; i < route.latitude.size(); ++i) {
            if (!std::isfinite(route.latitude[i]) || !std::isfinite(route.longitude[i])) {
                points.clear();
                return points;
            }
            points.push_back(LocalPoint{
                (route.latitude[i] - lat0) * meters_per_deg_lat,
                (route.longitude[i] - lon0) * meters_per_deg_lon});
        }
        return points;
    }

    static double distance(const LocalPoint& a, const LocalPoint& b)
    {
        return std::hypot(b.x - a.x, b.y - a.y);
    }

    static double available_turn_radius(
        const LocalPoint& a, const LocalPoint& b, const LocalPoint& c)
    {
        const double v1x = b.x - a.x;
        const double v1y = b.y - a.y;
        const double v2x = c.x - b.x;
        const double v2y = c.y - b.y;
        const double len1 = std::hypot(v1x, v1y);
        const double len2 = std::hypot(v2x, v2y);
        if (len1 < 1e-6 || len2 < 1e-6) {
            return 0.0;
        }
        const double dot = (v1x * v2x + v1y * v2y) / (len1 * len2);
        const double angle = std::acos(std::clamp(dot, -1.0, 1.0));
        if (angle < 1.0 * kDegToRad) {
            return std::numeric_limits<double>::infinity();
        }
        return std::min(len1, len2) / std::tan(angle * 0.5);
    }

    static bool is_emergency_mode(const std::string& raw_mode)
    {
        const std::string mode = normalize_mode(raw_mode);
        return ship_guidance::route_arbitration_policy::emergency_behavior(mode);
    }

    double requested_speed_at(const ship_interfaces::msg::RoutePlan& route, size_t index) const
    {
        if (index < route.navigation_mode.size() &&
            route.navigation_mode[index] == "dp_hold") {
            return 0.0;
        }
        if (index < route.speed_limit_mps.size() &&
            std::isfinite(route.speed_limit_mps[index]) &&
            route.speed_limit_mps[index] > 0.0) {
            return std::min(route.speed_limit_mps[index], max_command_speed_mps_);
        }
        return max_command_speed_mps_;
    }

    double max_requested_speed(const ship_interfaces::msg::RoutePlan& route) const
    {
        double max_speed = 0.0;
        for (size_t i = 0; i < route.latitude.size(); ++i) {
            max_speed = std::max(max_speed, requested_speed_at(route, i));
        }
        return max_speed;
    }

    void apply_speed_degradation(
        ship_interfaces::msg::RoutePlan& route,
        const std::vector<double>& admitted_speed_limits_mps) const
    {
        if (admitted_speed_limits_mps.size() == route.latitude.size()) {
            route.speed_limit_mps = admitted_speed_limits_mps;
        }
    }

    static FeasibilityResult accepted_result()
    {
        FeasibilityResult result;
        result.accepted = true;
        result.executing = true;
        result.degraded = false;
        result.rejected = false;
        result.state = "ACCEPTED";
        result.reason = "accepted";
        result.suggested_action = "none";
        return result;
    }

    static FeasibilityResult rejected_result(
        const std::string& reason,
        const std::string& suggested_action)
    {
        FeasibilityResult result;
        result.accepted = false;
        result.executing = false;
        result.degraded = false;
        result.rejected = true;
        result.state = "REJECTED";
        result.reason = reason;
        result.suggested_action = suggested_action;
        return result;
    }

    void fill_route_stage_snapshot(
        ship_interfaces::msg::RouteExecutionStatus& status,
        const ship_interfaces::msg::RoutePlan& route) const
    {
        status.stage_snapshot_valid = false;
        status.current_segment_index = 0;
        status.current_target_waypoint_index = 0;
        status.current_navigation_mode.clear();
        status.current_speed_limit_mps = 0.0;

        if (!has_ship_state_ || route.latitude.empty() ||
            route.latitude.size() != route.longitude.size()) {
            return;
        }

        const auto points = route_to_local_points(route);
        if (points.empty()) {
            return;
        }

        const double meters_per_deg_lat = 111320.0;
        const double meters_per_deg_lon =
            111320.0 * std::cos(route.latitude.front() * kDegToRad);
        const LocalPoint ship{
            (latest_ship_state_.latitude - route.latitude.front()) * meters_per_deg_lat,
            (latest_ship_state_.longitude - route.longitude.front()) * meters_per_deg_lon};

        size_t segment_index = 0;
        double nearest_distance_sq = std::numeric_limits<double>::infinity();
        if (points.size() >= 2) {
            for (size_t index = 0; index + 1 < points.size(); ++index) {
                const double dx = points[index + 1].x - points[index].x;
                const double dy = points[index + 1].y - points[index].y;
                const double length_sq = dx * dx + dy * dy;
                double ratio = 0.0;
                if (length_sq > 1e-9) {
                    ratio = std::clamp(
                        ((ship.x - points[index].x) * dx +
                         (ship.y - points[index].y) * dy) / length_sq,
                        0.0, 1.0);
                }
                const double nearest_x = points[index].x + ratio * dx;
                const double nearest_y = points[index].y + ratio * dy;
                const double error_x = ship.x - nearest_x;
                const double error_y = ship.y - nearest_y;
                const double distance_sq = error_x * error_x + error_y * error_y;
                if (distance_sq < nearest_distance_sq) {
                    nearest_distance_sq = distance_sq;
                    segment_index = index;
                }
            }
        }

        const size_t target_index =
            std::min(segment_index + 1, route.latitude.size() - 1);
        status.stage_snapshot_valid = true;
        status.current_segment_index = static_cast<uint32_t>(segment_index);
        status.current_target_waypoint_index = static_cast<uint32_t>(target_index);
        if (target_index < route.navigation_mode.size()) {
            status.current_navigation_mode = route.navigation_mode[target_index];
        }
        status.current_speed_limit_mps = requested_speed_at(route, target_index);
    }

    void publish_status_for_route(
        const ship_interfaces::msg::RoutePlan& route,
        const FeasibilityResult& result,
        const std::string& command_source = "route_planner")
    {
        ship_interfaces::msg::RouteExecutionStatus status;
        status.header.stamp = now();
        status.header.frame_id = "map";
        status.plan_id = route.route_id;
        status.active_route_id = route.route_id;
        status.active_route_revision = route.route_revision;
        status.command_source = command_source;
        fill_status_common(status, result);
        fill_route_stage_snapshot(status, route);
        status_pub_->publish(status);
    }

    void publish_status_for_avoidance(
        const ship_interfaces::msg::AvoidancePlan& plan,
        const FeasibilityResult& result)
    {
        ship_interfaces::msg::RouteExecutionStatus status;
        status.header.stamp = now();
        status.header.frame_id = "map";
        status.plan_id = plan.plan_id;
        status.active_route_id = plan.parent_route_id;
        status.active_route_revision = plan.parent_route_revision;
        status.command_source = plan.command_source.empty() ? "collision_avoidance" : plan.command_source;
        fill_status_common(status, result);
        status_pub_->publish(status);
    }

    void fill_status_common(
        ship_interfaces::msg::RouteExecutionStatus& status,
        const FeasibilityResult& result) const
    {
        status.accepted = result.accepted;
        status.executing = result.executing;
        status.degraded = result.degraded;
        status.rejected = result.rejected;
        status.execution_state = result.state;
        status.reason = result.reason;
        status.suggested_action = result.suggested_action;
        status.requested_speed_mps = result.requested_speed_mps;
        status.applied_speed_mps = result.applied_speed_mps;
        status.requested_heading_deg = result.requested_heading_deg;
        status.applied_heading_deg = result.applied_heading_deg;
        status.required_turn_radius_m = result.required_turn_radius_m;
        status.estimated_available_turn_radius_m = result.estimated_available_turn_radius_m;
        status.required_decel_distance_m = result.required_decel_distance_m;
        status.available_decel_distance_m = result.available_decel_distance_m;
        status.suggested_max_speed_mps = result.suggested_max_speed_mps;
        status.suggested_min_distance_m = result.suggested_min_distance_m;

        if (has_ship_state_) {
            status.current_latitude = latest_ship_state_.latitude;
            status.current_longitude = latest_ship_state_.longitude;
            status.current_heading_deg = latest_ship_state_.heading_deg;
            status.current_course_deg = latest_ship_state_.course_deg;
            status.current_speed_mps = latest_ship_state_.speed_mps;
            status.cross_track_error_m = latest_ship_state_.cross_track_error_m;
        }
    }

    std::string nominal_route_topic_;
    std::string avoidance_plan_topic_;
    std::string berthing_candidate_route_topic_;
    std::string berthing_state_topic_;
    std::string active_route_topic_;
    std::string execution_status_topic_;
    std::string route_plan_status_topic_;
    std::string ship_state_topic_;

    double max_command_speed_mps_{8.0};
    double min_segment_length_m_{30.0};
    double emergency_min_segment_length_m_{15.0};
    // The 30 m floor is a hand-route admission contract. Dense planner-owned
    // (mid_mpc_ipopt) stitch geometry is mirrored point-for-point downstream,
    // and a re-spliced boundary leg can sit marginally below the floor, so a
    // hard reject would collapse the route into the 3-point internal return
    // route. Such plans keep every other admission gate (speed, turn radius,
    // decel distance); emergency plans always keep the 15 m floor.
    bool planner_route_min_segment_skip_{true};
    const int planner_trajectory_contract_version_{1};
    ship_interfaces::msg::RoutePlan admitted_route_;
    double min_turn_radius_m_{80.0};
    double emergency_min_turn_radius_m_{45.0};
    double max_lateral_accel_mps2_{0.25};
    double max_yaw_rate_deg_s_{1.2};
    double emergency_max_yaw_rate_deg_s_{2.0};
    double max_decel_mps2_{0.08};
    double default_avoidance_hold_s_{60.0};
    double max_heading_path_error_deg_{20.0};
    bool publish_nominal_status_{true};
    bool enable_berthing_arbitration_{false};
    double berthing_candidate_timeout_s_{10.0};
    double max_berthing_speed_mps_{2.0};
    double berthing_handover_entry_speed_mps_{0.8};
    double berthing_handover_min_lookahead_m_{45.0};
    double berthing_handover_max_intercept_angle_deg_{15.0};
    double berthing_handover_ramp_accel_mps2_{0.02};
    double berthing_handover_ramp_spacing_m_{45.0};
    bool awaiting_berthing_candidate_{false};
    bool has_active_berthing_{false};
    bool has_pending_berthing_candidate_{false};
    bool berthing_abort_latched_{false};
    std::string latest_berthing_state_{"inactive"};
    rclcpp::Time berthing_candidate_deadline_{0, 0, RCL_ROS_TIME};
    bool has_active_avoidance_{false};
    bool has_active_velocity_intent_{false};
    bool velocity_expiry_reported_{false};
    ship_interfaces::msg::VelocityIntent active_velocity_intent_;
    rclcpp::Publisher<ship_interfaces::msg::VelocityIntent>::SharedPtr velocity_intent_pub_;
    rclcpp::Subscription<ship_interfaces::msg::VelocityIntent>::SharedPtr velocity_intent_sub_;
    std::string active_avoidance_plan_id_;
    rclcpp::Time active_avoidance_until_{0, 0, RCL_ROS_TIME};

    rclcpp::Subscription<ship_interfaces::msg::RoutePlan>::SharedPtr nominal_route_sub_;
    rclcpp::Subscription<ship_interfaces::msg::RoutePlan>::SharedPtr berthing_candidate_sub_;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr berthing_state_sub_;
    rclcpp::Subscription<ship_interfaces::msg::AvoidancePlan>::SharedPtr avoidance_plan_sub_;
    rclcpp::Subscription<ship_interfaces::msg::GeoPosition>::SharedPtr ship_state_sub_;
    rclcpp::Subscription<ship_interfaces::msg::RoutePlanStatus>::SharedPtr route_plan_status_sub_;
    rclcpp::Publisher<ship_interfaces::msg::RoutePlan>::SharedPtr active_route_pub_;
    rclcpp::Publisher<ship_interfaces::msg::RouteExecutionStatus>::SharedPtr status_pub_;

    ship_interfaces::msg::RoutePlan latest_nominal_route_;
    ship_interfaces::msg::RoutePlan latest_berthing_candidate_;
    ship_interfaces::msg::RoutePlan active_route_;
    ship_interfaces::msg::GeoPosition latest_ship_state_;
    FeasibilityResult last_active_result_;
    std::string active_route_id_;
    std::string active_command_source_{"route_planner"};
    uint64_t generated_route_sequence_{0};
    bool has_nominal_route_{false};
    bool has_ship_state_{false};
    rclcpp::TimerBase::SharedPtr maintenance_timer_;
};

int main(int argc, char** argv)
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<ActiveRouteManagerNode>());
    rclcpp::shutdown();
    return 0;
}
