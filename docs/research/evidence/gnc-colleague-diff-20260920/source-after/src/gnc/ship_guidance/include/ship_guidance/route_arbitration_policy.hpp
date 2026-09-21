#pragma once

#include <cstdint>
#include <string>
#include "ship_guidance/avoidance_mode_policy.hpp"

namespace ship_guidance::route_arbitration_policy {

inline bool candidate_state_authorized(const std::string& normalized_state)
{
    return normalized_state == "bow_out" ||
        normalized_state == "clear_side" ||
        normalized_state == "clear_ahead" ||
        normalized_state == "join_route" ||
        normalized_state == "approach_berth" ||
        normalized_state == "berthing";
}

inline bool ordinary_avoidance_blocked(const std::string& normalized_state)
{
    return normalized_state == "berthed" ||
        normalized_state == "bow_out" ||
        normalized_state == "clear_side" ||
        normalized_state == "approach_berth" ||
        normalized_state == "berthing";
}

inline bool emergency_behavior(const std::string& normalized_mode)
{
    return ship_guidance::avoidance_mode_policy::emergency(normalized_mode);
}

inline bool nominal_tail_mode_allowed(const std::string& normalized_mode)
{
    return normalized_mode == "cruise" ||
        normalized_mode == "narrow_channel" ||
        normalized_mode == "harbor" ||
        normalized_mode == "approach" ||
        normalized_mode == "berthing" ||
        normalized_mode == "dp_hold";
}

inline bool parent_binding_matches(
    const std::string& parent_route_id,
    std::uint32_t parent_route_revision,
    const std::string& nominal_route_id,
    std::uint32_t nominal_route_revision)
{
    return !parent_route_id.empty() &&
        parent_route_id == nominal_route_id &&
        parent_route_revision == nominal_route_revision;
}

}  // namespace ship_guidance::route_arbitration_policy
