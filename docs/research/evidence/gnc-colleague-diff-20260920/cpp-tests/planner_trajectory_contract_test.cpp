#include "ship_guidance/planner_trajectory_contract.hpp"
#include <cassert>
#include <cmath>
#include <vector>

using namespace ship_guidance::planner_trajectory_contract;

int main() {
    const Limits limits{8.0, 1.2 * 3.141592653589793 / 180.0, 0.08, 0.25, 80.0};
    std::vector<Sample> straight{{0.0, 0.0, 0.0, 4.0}, {20.0, 0.0, 0.0, 4.0}, {40.0, 0.0, 0.0, 4.0}};
    assert(validate(straight, 5.0, limits).empty());
    // A low-speed turn can satisfy yaw rate while violating minimum radius.
    std::vector<Sample> tight_turn{{0.0, 0.0, 0.0, 0.4},
        {2.0 * std::cos(0.05), 2.0 * std::sin(0.05), 0.05, 0.4}};
    assert(validate(tight_turn, 5.0, limits) == "trajectory_turn_radius_exceeded");
    tight_turn[1] = {2.0 * std::cos(0.02), 2.0 * std::sin(0.02), 0.02, 0.4};
    assert(validate(tight_turn, 5.0, limits).empty());
    auto bad = straight;
    bad[1].speed = 8.0;
    assert(!validate(bad, 5.0, limits).empty());
    bad = straight;
    bad[1].course = 0.2;
    assert(!validate(bad, 5.0, limits).empty());
    bad = straight;
    bad[1].east = 1.0;
    assert(validate(bad, 5.0, limits) == "trajectory_position_speed_mismatch");
    assert(!validate(straight, 0.0, limits).empty());
    bad = straight;
    bad[1].speed = NAN;
    assert(!validate(bad, 5.0, limits).empty());
    std::vector<Sample> stop{{0.0, 0.0, 0.0, 0.0}, {0.0, 0.0, 0.0, 0.0}};
    assert(validate(stop, 5.0, limits).empty());
    assert(initial_state_matches(straight.front(), {0.1, 0.0, 0.0, 4.0}));
    assert(!initial_state_matches(straight.front(), {1.0, 0.0, 0.0, 4.0}));
    assert(!initial_state_matches(straight.front(), {0.0, 0.0, 0.1, 4.0}));
    assert(!initial_state_matches(straight.front(), {0.0, 0.0, 0.0, 5.0}));
}
