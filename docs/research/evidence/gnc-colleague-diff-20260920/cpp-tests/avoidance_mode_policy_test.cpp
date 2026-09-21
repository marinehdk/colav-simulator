#include "ship_guidance/avoidance_mode_policy.hpp"
#include "ship_guidance/route_arbitration_policy.hpp"
#include <cassert>

int main()
{
    namespace mode = ship_guidance::avoidance_mode_policy;
    namespace route = ship_guidance::route_arbitration_policy;
    assert(mode::encode("avoidance") == 10);
    assert(mode::encode("collision_avoidance") == 10);
    assert(mode::encode("emergency_avoidance") == 6);
    assert(mode::encode("emergency_avoid") == 6);
    assert(mode::encode("cruise") == 0);
    assert(mode::velocity("cruise"));
    assert(!mode::velocity("dp_hold"));
    assert(mode::is_avoidance_code(6) && mode::is_avoidance_code(10));
    assert(!mode::is_avoidance_code(1));
    assert(!route::emergency_behavior("avoidance"));
    assert(route::emergency_behavior("emergency_avoidance"));
    assert(route::ordinary_avoidance_blocked("berthed"));
}
