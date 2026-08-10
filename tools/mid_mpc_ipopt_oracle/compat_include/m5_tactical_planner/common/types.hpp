#ifndef MASS_L3_M5_COMMON_TYPES_HPP_
#define MASS_L3_M5_COMMON_TYPES_HPP_

#include <Eigen/Dense>

#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

#include "m5_tactical_planner/common/units.hpp"

namespace mass_l3::m5 {

struct TrajectoryPoint {
  double x_m{0.0};
  double y_m{0.0};
  double psi_rad{0.0};
  double u_mps{0.0};
  double v_mps{0.0};
  double r_rad_s{0.0};
  double t_s{0.0};
};

inline void propagate_trajectory_positions(std::vector<TrajectoryPoint>& trajectory,
                                           double dt_s,
                                           double x0_m = 0.0,
                                           double y0_m = 0.0) {
  double x_m = x0_m;
  double y_m = y0_m;
  for (auto& point : trajectory) {
    point.x_m = x_m;
    point.y_m = y_m;
    x_m += point.u_mps * std::cos(point.psi_rad) * dt_s;
    y_m += point.u_mps * std::sin(point.psi_rad) * dt_s;
  }
}

struct TargetState {
  std::int32_t id{0};
  double x_m{0.0};
  double y_m{0.0};
  double cog_rad{0.0};
  double sog_mps{0.0};
  double cpa_m{0.0};
  double cpa_sigma_m{0.0};
  double tcpa_s{0.0};
  double confidence{0.0};
};

using Polygon2D = std::vector<Eigen::Vector2d>;

struct ZoneConstraint {
  Polygon2D polygon;
  bool must_stay_inside{true};
  std::string name;
};

struct ConstraintInputs {
  double cpa_safe_m{1852.0};
  double cpa_hard_m{1852.0};
  double terminal_l_min_feasible_m{30.0};
  double terminal_l_max_feasible_m{400.0};
  std::vector<TargetState> targets;
  std::vector<std::uint8_t> applicable_rules;
  double heading_min_rad{-M_PI};
  double heading_max_rad{M_PI};
  double speed_min_mps{0.0};
  double speed_max_mps{15.0};
  double own_ship_psi_rad{0.0};
  std::vector<ZoneConstraint> zone_constraints;
  double heading_box_reachable_from_psi0_deg{0.0};
  double rot_step_deg{0.0};
  double min_alt_required_rad{0.0};
  double earliest_min_alt_k{0.0};
};

enum class ColregsPreferredDirection : std::uint8_t {
  Hold = 0u,
  Starboard = 1u,
  Port = 2u,
  ReduceSpeed = 3u,
};

struct MidMpcInput {
  TrajectoryPoint own_ship;
  std::vector<TargetState> targets;
  ConstraintInputs constraints;
  double planned_route_bearing_rad{0.0};
  double route_xte_m{0.0};
  double route_frame_origin_x_m{0.0};
  double route_frame_origin_y_m{0.0};
  double route_frame_normal_x{0.0};
  double route_frame_normal_y{1.0};
  double route_frame_active_leg_bearing_rad{0.0};
  double lateral_scale_m{400.0};
  double route_weight{0.0};
  std::uint8_t colregs_primary_role{3u};
  ColregsPreferredDirection colregs_preferred_direction{
      ColregsPreferredDirection::Hold};
  double colregs_min_alteration_rad{0.0};
  double planned_speed_mps{5.0};
  double decel_max_mps2{0.08};
  double rot_max_rad_s{0.2094};
  std::int32_t prefix_active_k{0};
  std::vector<double> prefix_psi_rad;
  std::vector<double> prefix_u_mps;
};

struct MidMpcSolution {
  enum class Status : std::uint8_t {
    Converged = 0u,
    Timeout = 1u,
    Infeasible = 2u,
    NumericalFailure = 3u,
    NotInitialized = 4u,
  };
  enum class SolverStatus : std::uint8_t {
    Converged = 0u,
    QpRecovered = 1u,
    Timeout = 2u,
    Infeasible = 3u,
    NumericalFailure = 4u,
    NotInitialized = 5u,
  };
  enum class SafetyStatus : std::uint8_t {
    Nominal = 0u,
    Degraded = 1u,
    Unsafe = 2u,
    Unknown = 3u,
  };

  Status status{Status::NotInitialized};
  SolverStatus solver_status{SolverStatus::NotInitialized};
  SafetyStatus safety_status{SafetyStatus::Unknown};
  std::vector<TrajectoryPoint> trajectory;
  double cost_total{0.0};
  double cost_colreg{0.0};
  double cost_dist{0.0};
  double cost_vel{0.0};
  double cpa_slack{0.0};
  std::array<double, 16> cpa_slack_per_target{};
  double continuous_cpa_min_m{std::numeric_limits<double>::infinity()};
  bool continuous_cpa_violated{false};
  std::int32_t solve_duration_ms{0};
  std::int32_t ipopt_iterations{0};
  std::string rationale;
  std::string ipopt_return_status;
  std::vector<double> applied_heading_box_lo_rad;
  std::vector<double> applied_heading_box_hi_rad;
};

}  // namespace mass_l3::m5

#endif
