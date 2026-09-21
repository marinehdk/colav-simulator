#pragma once

#include <string>

namespace ship_guidance::avoidance_mode_policy {

// Inputs are normalized by the route/guidance boundary. Code 6 retains the
// established emergency protocol; ordinary avoidance has its own code.
inline bool emergency(const std::string& mode)
{
    return mode == "emergency_avoidance" || mode == "emergency_avoid";
}

inline bool ordinary(const std::string& mode)
{
    return mode == "avoidance" || mode == "collision_avoidance";
}

inline bool any(const std::string& mode)
{
    return ordinary(mode) || emergency(mode);
}

inline bool velocity(const std::string& mode)
{
    return mode == "cruise" || any(mode);
}

inline int encode(const std::string& mode)
{
    return emergency(mode) ? 6 : (ordinary(mode) ? 10 : 0);
}

inline bool is_avoidance_code(int code)
{
    return code == 6 || code == 10;
}

}  // namespace ship_guidance::avoidance_mode_policy
