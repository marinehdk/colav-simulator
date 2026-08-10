#include <casadi/casadi.hpp>
#include <coin-or/IpoptConfig.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include "m5_tactical_planner/mid_mpc/mid_mpc_nlp_formulation.hpp"
#include "m5_tactical_planner/mid_mpc/mid_mpc_solver.hpp"

namespace {
casadi::DMDict g_prepared;
casadi::DMDict g_result;
}  // namespace

void oracle_capture_prepared(const casadi::DMDict& prepared) {
  g_prepared = prepared;
}

void oracle_capture_result(const casadi::DMDict& result) {
  g_result = result;
}

namespace {

using mass_l3::m5::ColregsPreferredDirection;
using mass_l3::m5::MidMpcInput;
using mass_l3::m5::MidMpcSolution;
using mass_l3::m5::TargetState;
using mass_l3::m5::mid_mpc::MidMpcNlpFormulation;
using mass_l3::m5::mid_mpc::MidMpcSolver;
using mass_l3::m5::mid_mpc::RowRegistry;

struct Scenario {
  std::string id;
  MidMpcNlpFormulation::Config config;
  MidMpcInput input;
};

struct ObjectiveComponents {
  double colreg = 0.0;
  double heading = 0.0;
  double speed = 0.0;
  double route = 0.0;
  double asymmetry = 0.0;
  double terminal = 0.0;
  double cpa_slack = 0.0;
  double direction_slack = 0.0;
};

const char* status_name(MidMpcSolution::Status status) {
  switch (status) {
    case MidMpcSolution::Status::Converged:
      return "Converged";
    case MidMpcSolution::Status::Timeout:
      return "Timeout";
    case MidMpcSolution::Status::Infeasible:
      return "Infeasible";
    case MidMpcSolution::Status::NumericalFailure:
      return "NumericalFailure";
    case MidMpcSolution::Status::NotInitialized:
      return "NotInitialized";
  }
  return "Unknown";
}

const char* direction_name(ColregsPreferredDirection direction) {
  switch (direction) {
    case ColregsPreferredDirection::Starboard:
      return "Starboard";
    case ColregsPreferredDirection::Port:
      return "Port";
    case ColregsPreferredDirection::ReduceSpeed:
      return "ReduceSpeed";
    case ColregsPreferredDirection::Hold:
      return "Hold";
  }
  return "Hold";
}

void write_number(double value) {
  if (std::isfinite(value)) {
    std::cout << value;
  } else if (value > 0.0) {
    std::cout << "\"Infinity\"";
  } else {
    std::cout << "\"-Infinity\"";
  }
}

void write_dm(const casadi::DM& value) {
  std::cout << '[';
  for (casadi_int index = 0; index < value.numel(); ++index) {
    if (index != 0) {
      std::cout << ',';
    }
    write_number(static_cast<double>(value(index)));
  }
  std::cout << ']';
}

void write_trajectory(const MidMpcSolution& solution) {
  std::cout << '[';
  for (std::size_t index = 0; index < solution.trajectory.size(); ++index) {
    if (index != 0u) {
      std::cout << ',';
    }
    const auto& point = solution.trajectory[index];
    std::cout << "{\"x_m\":";
    write_number(point.x_m);
    std::cout << ",\"y_m\":";
    write_number(point.y_m);
    std::cout << ",\"psi_rad\":";
    write_number(point.psi_rad);
    std::cout << ",\"u_mps\":";
    write_number(point.u_mps);
    std::cout << ",\"t_s\":";
    write_number(point.t_s);
    std::cout << '}';
  }
  std::cout << ']';
}

void write_targets(const std::vector<TargetState>& targets) {
  std::cout << '[';
  for (std::size_t index = 0; index < targets.size(); ++index) {
    if (index != 0u) {
      std::cout << ',';
    }
    const auto& target = targets[index];
    std::cout << "{\"id\":" << target.id << ",\"x_m\":";
    write_number(target.x_m);
    std::cout << ",\"y_m\":";
    write_number(target.y_m);
    std::cout << ",\"cog_rad\":";
    write_number(target.cog_rad);
    std::cout << ",\"sog_mps\":";
    write_number(target.sog_mps);
    std::cout << ",\"cpa_m\":";
    write_number(target.cpa_m);
    std::cout << ",\"tcpa_s\":";
    write_number(target.tcpa_s);
    std::cout << '}';
  }
  std::cout << ']';
}

void write_span(const char* name, int32_t start, int32_t count, bool comma) {
  if (comma) {
    std::cout << ',';
  }
  std::cout << '\"' << name << "\":{\"start\":" << start
            << ",\"count\":" << count << '}';
}

double dm_at(const casadi::DM& value, casadi_int index) {
  return static_cast<double>(value(index));
}

double softplus(double value) {
  if (value > 0.0) {
    return value + std::log1p(std::exp(-value));
  }
  return std::log1p(std::exp(value));
}

ObjectiveComponents calculate_objective_components(
    const MidMpcNlpFormulation::Config& config, const casadi::DM& raw_x,
    const casadi::DM& p) {
  constexpr int32_t kX0 = 2;
  constexpr int32_t kY0 = 3;
  constexpr int32_t kRouteBearing = 4;
  constexpr int32_t kPlannedSpeed = 5;
  constexpr int32_t kCpaSafe = 10;
  constexpr int32_t kAsymmetryActive = 13;
  constexpr int32_t kRouteOriginX = 14;
  constexpr int32_t kRouteOriginY = 15;
  constexpr int32_t kRouteNormalX = 16;
  constexpr int32_t kRouteNormalY = 17;
  constexpr int32_t kLateralScale = 19;
  constexpr int32_t kRouteWeight = 20;
  constexpr int32_t kPreferredSide = 22;
  constexpr int32_t kLateralActive = 24;
  constexpr int32_t kTargetStart = 62;
  constexpr int32_t kTargetStride = 5;

  ObjectiveComponents values;
  const int32_t N = config.n_horizon;
  const double route_bearing = dm_at(p, kRouteBearing);
  const double planned_speed = dm_at(p, kPlannedSpeed);
  const double lateral_scale = dm_at(p, kLateralScale);
  double own_x = dm_at(p, kX0);
  double own_y = dm_at(p, kY0);
  double route_cost = 0.0;
  double terminal_cross_track = 0.0;

  for (int32_t k = 0; k < N; ++k) {
    const double psi = dm_at(raw_x, k);
    const double speed = dm_at(raw_x, N + k);
    const double heading_error = psi - route_bearing;
    const double speed_error = speed - planned_speed;
    values.heading += config.w_dist * heading_error * heading_error;
    values.speed += config.w_vel * speed_error * speed_error;
    values.asymmetry +=
        dm_at(p, kAsymmetryActive) * config.k_asym * config.asym_tau *
        softplus((route_bearing - psi) / config.asym_tau);

    const double cross_track =
        (own_x - dm_at(p, kRouteOriginX)) * dm_at(p, kRouteNormalX) +
        (own_y - dm_at(p, kRouteOriginY)) * dm_at(p, kRouteNormalY);
    const double scaled = cross_track / lateral_scale;
    route_cost += scaled * scaled;
    terminal_cross_track = cross_track;
    own_x += speed * config.dt_s * std::cos(psi);
    own_y += speed * config.dt_s * std::sin(psi);
  }
  const double terminal_scaled = terminal_cross_track / lateral_scale;
  values.route = config.w_route * dm_at(p, kRouteWeight) *
                 (route_cost + 2.0 * terminal_scaled * terminal_scaled);

  const double preferred_side = dm_at(p, kPreferredSide);
  const double wrong_side =
      -preferred_side * terminal_cross_track / lateral_scale;
  const double terminal_lower =
      config.terminal_tau * softplus(wrong_side / config.terminal_tau);
  const double z_pos =
      (terminal_cross_track - config.terminal_l_max_feasible_m) / lateral_scale;
  const double z_neg =
      (-terminal_cross_track - config.terminal_l_max_feasible_m) /
      lateral_scale;
  const double terminal_upper = config.terminal_tau *
      (softplus(z_pos / config.terminal_tau) +
       softplus(z_neg / config.terminal_tau));
  values.terminal = dm_at(p, kLateralActive) * terminal_lower +
                    dm_at(p, kLateralActive) * preferred_side *
                        preferred_side * terminal_upper;

  own_x = dm_at(p, kX0);
  own_y = dm_at(p, kY0);
  double colreg_cost = 0.0;
  for (int32_t k = 0; k < N; ++k) {
    const double psi = dm_at(raw_x, k);
    const double speed = dm_at(raw_x, N + k);
    own_x += speed * config.dt_s * std::cos(psi);
    own_y += speed * config.dt_s * std::sin(psi);
    const double time_s = k * config.dt_s;
    for (int32_t target_index = 0; target_index < config.max_targets;
         ++target_index) {
      const int32_t base = kTargetStart + target_index * kTargetStride;
      const double target_cog = dm_at(p, base + 2);
      const double target_sog = dm_at(p, base + 3);
      const double target_x =
          dm_at(p, base) + target_sog * std::cos(target_cog) * time_s;
      const double target_y =
          dm_at(p, base + 1) + target_sog * std::sin(target_cog) * time_s;
      const double dx = own_x - target_x;
      const double dy = own_y - target_y;
      const double distance = std::sqrt(dx * dx + dy * dy + 1.0);
      colreg_cost +=
          dm_at(p, base + 4) * std::exp(-time_s / config.t_discount_s) *
          std::exp(-config.zeta * (distance - dm_at(p, kCpaSafe)));
    }
  }
  values.colreg = config.w_colreg * colreg_cost /
                  std::max(1, config.max_targets * config.n_horizon);

  const double cpa_slack = dm_at(raw_x, 2 * N);
  const double direction_slack = dm_at(raw_x, 2 * N + 1);
  values.cpa_slack = config.w_slack_l1 * cpa_slack +
                     config.w_slack_l2 * cpa_slack * cpa_slack;
  values.direction_slack =
      config.w_dir_slack_l1 * direction_slack +
      config.w_dir_slack_l2 * direction_slack * direction_slack;
  return values;
}

void write_objective_components(const ObjectiveComponents& values) {
  std::cout << "{\"colreg\":";
  write_number(values.colreg);
  std::cout << ",\"heading\":";
  write_number(values.heading);
  std::cout << ",\"speed\":";
  write_number(values.speed);
  std::cout << ",\"route\":";
  write_number(values.route);
  std::cout << ",\"asymmetry\":";
  write_number(values.asymmetry);
  std::cout << ",\"terminal\":";
  write_number(values.terminal);
  std::cout << ",\"cpa_slack\":";
  write_number(values.cpa_slack);
  std::cout << ",\"direction_slack\":";
  write_number(values.direction_slack);
  std::cout << '}';
}

MidMpcNlpFormulation::Config base_config() {
  MidMpcNlpFormulation::Config config;
  config.n_horizon = 8;
  config.dt_s = 5.0;
  config.max_targets = 16;
  config.continuous_cpa_enabled = false;
  return config;
}

MidMpcInput base_input() {
  MidMpcInput input;
  input.own_ship.psi_rad = 0.0;
  input.own_ship.u_mps = 4.0;
  input.planned_route_bearing_rad = 0.0;
  input.planned_speed_mps = 4.0;
  input.constraints.heading_min_rad = -0.8;
  input.constraints.heading_max_rad = 0.8;
  input.constraints.speed_min_mps = 1.0;
  input.constraints.speed_max_mps = 7.0;
  input.constraints.cpa_safe_m = 150.0;
  input.constraints.cpa_hard_m = 40.0;
  input.constraints.own_ship_psi_rad = input.own_ship.psi_rad;
  input.rot_max_rad_s = 0.05;
  input.decel_max_mps2 = 0.2;
  input.route_frame_origin_x_m = 0.0;
  input.route_frame_origin_y_m = 0.0;
  input.route_frame_normal_x = 0.0;
  input.route_frame_normal_y = 1.0;
  input.route_frame_active_leg_bearing_rad = 0.0;
  input.lateral_scale_m = 400.0;
  input.route_weight = 1.0;
  return input;
}

TargetState target(int32_t id, double x_m, double y_m, double cog_rad,
                   double sog_mps, double cpa_m, double tcpa_s) {
  TargetState value;
  value.id = id;
  value.x_m = x_m;
  value.y_m = y_m;
  value.cog_rad = cog_rad;
  value.sog_mps = sog_mps;
  value.cpa_m = cpa_m;
  value.tcpa_s = tcpa_s;
  return value;
}

void activate_lateral_give_way(MidMpcInput& input,
                               ColregsPreferredDirection direction,
                               uint8_t rule) {
  input.colregs_primary_role = 1u;
  input.colregs_preferred_direction = direction;
  input.colregs_min_alteration_rad = 0.08;
  input.constraints.applicable_rules = {rule};
}

std::vector<Scenario> scenarios() {
  std::vector<Scenario> values;

  MidMpcInput route = base_input();
  route.planned_route_bearing_rad = 0.15;
  route.route_frame_active_leg_bearing_rad = 0.15;
  route.planned_speed_mps = 4.5;
  values.push_back({"route_speed_cold", base_config(), route});

  MidMpcInput head_on = base_input();
  head_on.targets = {target(101, 300.0, 0.0, M_PI, 4.0, 0.0, 37.5)};
  activate_lateral_give_way(head_on, ColregsPreferredDirection::Starboard, 14u);
  values.push_back({"head_on_starboard", base_config(), head_on});

  MidMpcInput crossing = base_input();
  crossing.targets = {
      target(102, 150.0, 100.0, -M_PI / 2.0, 2.6666666667, 0.0, 37.5)};
  activate_lateral_give_way(crossing, ColregsPreferredDirection::Starboard, 15u);
  values.push_back({"crossing_starboard", base_config(), crossing});

  MidMpcInput stand_on = crossing;
  stand_on.colregs_primary_role = 0u;
  stand_on.colregs_preferred_direction = ColregsPreferredDirection::Hold;
  stand_on.colregs_min_alteration_rad = 0.0;
  values.push_back({"stand_on_hold", base_config(), stand_on});

  MidMpcInput overtaking = base_input();
  overtaking.targets = {target(103, 80.0, 0.0, 0.0, 2.0, 0.0, 40.0)};
  activate_lateral_give_way(overtaking, ColregsPreferredDirection::Port, 13u);
  values.push_back({"overtaking_port", base_config(), overtaking});

  MidMpcInput slack = base_input();
  slack.targets = {target(104, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0)};
  slack.constraints.cpa_hard_m = 100.0;
  slack.constraints.heading_min_rad = -0.001;
  slack.constraints.heading_max_rad = 0.001;
  slack.constraints.speed_min_mps = 3.999;
  slack.constraints.speed_max_mps = 4.001;
  values.push_back({"close_target_cpa_slack", base_config(), slack});

  MidMpcInput prefix = base_input();
  prefix.prefix_active_k = 2;
  prefix.prefix_psi_rad = {0.05, 0.10};
  prefix.prefix_u_mps = {4.0, 4.0};
  values.push_back({"active_prefix_k2", base_config(), prefix});

  MidMpcInput multi = base_input();
  multi.targets = {
      target(105, 900.0, 200.0, M_PI, 2.0, 300.0, 120.0),
      target(106, 700.0, -250.0, 0.2, 3.0, 280.0, 100.0),
  };
  values.push_back({"multi_target_row_order", base_config(), multi});

  for (auto& scenario : values) {
    scenario.input.constraints.targets = scenario.input.targets;
  }
  return values;
}

void write_config(const MidMpcNlpFormulation::Config& config) {
  std::cout << "{\"N\":" << config.n_horizon << ",\"dt\":";
  write_number(config.dt_s);
  std::cout << ",\"w_colreg\":";
  write_number(config.w_colreg);
  std::cout << ",\"w_dist\":";
  write_number(config.w_dist);
  std::cout << ",\"w_vel\":";
  write_number(config.w_vel);
  std::cout << ",\"w_route\":";
  write_number(config.w_route);
  std::cout << ",\"w_slack_l1\":";
  write_number(config.w_slack_l1);
  std::cout << ",\"w_slack_l2\":";
  write_number(config.w_slack_l2);
  std::cout << ",\"w_dir_slack_l1\":";
  write_number(config.w_dir_slack_l1);
  std::cout << ",\"w_dir_slack_l2\":";
  write_number(config.w_dir_slack_l2);
  std::cout << ",\"zeta\":";
  write_number(config.zeta);
  std::cout << ",\"pwt_outer_m\":";
  write_number(config.pwt_outer_m);
  std::cout << ",\"t_discount_s\":";
  write_number(config.t_discount_s);
  std::cout << ",\"cpa_slack_enabled\":true,\"dir_slack_enabled\":true,"
            << "\"continuous_cpa_enabled\":false}";
}

bool row_is_active(const casadi::DM& lbg, const casadi::DM& ubg,
                   int32_t row) {
  return std::isfinite(dm_at(lbg, row)) || std::isfinite(dm_at(ubg, row));
}

int32_t first_active_step(const casadi::DM& lbg, const casadi::DM& ubg,
                          int32_t start, int32_t count) {
  for (int32_t step = 0; step < count; ++step) {
    if (row_is_active(lbg, ubg, start + step)) {
      return step;
    }
  }
  return 0;
}

void write_normalized_problem(const MidMpcInput& input, const casadi::DM& p,
                              const casadi::DM& lbg,
                              const casadi::DM& ubg,
                              const RowRegistry& rows, int32_t N) {
  const int32_t cpa_hard_from_k = input.targets.empty()
                                      ? 0
                                      : first_active_step(
                                            lbg, ubg, rows.cpa_row(0, 0), N);
  const int32_t direction_hard_from_k =
      first_active_step(lbg, ubg, rows.direction_row(0), N);
  const int32_t min_alt_hard_from_k =
      first_active_step(lbg, ubg, rows.min_alt_row(0), N);
  bool terminal_rows_enabled = false;
  for (int32_t row = 0; row < 3; ++row) {
    terminal_rows_enabled = terminal_rows_enabled ||
                            row_is_active(lbg, ubg,
                                          rows.terminal_row(row));
  }

  std::cout << "{\"lateral_active\":"
            << (dm_at(p, 24) != 0.0 ? "true" : "false")
            << ",\"preferred_side\":" << static_cast<int>(dm_at(p, 22))
            << ",\"starboard_asymmetry_active\":"
            << (dm_at(p, 13) != 0.0 ? "true" : "false")
            << ",\"row_schedule\":{\"prefix_softening\":"
            << (input.prefix_active_k > 0 ? "true" : "false")
            << ",\"cpa_hard_from_k\":" << cpa_hard_from_k
            << ",\"direction_hard_from_k\":" << direction_hard_from_k
            << ",\"min_alt_hard_from_k\":" << min_alt_hard_from_k
            << ",\"terminal_rows_enabled\":"
            << (terminal_rows_enabled ? "true" : "false")
            << "},\"audit_row_count\":"
            << input.constraints.applicable_rules.size() << '}';
}

void write_problem(const MidMpcInput& input, const casadi::DM& p,
                   const casadi::DM& lbg, const casadi::DM& ubg,
                   const RowRegistry& rows, int32_t N) {
  std::cout << "{\"own_ship\":{\"psi_rad\":";
  write_number(input.own_ship.psi_rad);
  std::cout << ",\"u_mps\":";
  write_number(input.own_ship.u_mps);
  std::cout << "},\"route_bearing_rad\":";
  write_number(input.planned_route_bearing_rad);
  std::cout << ",\"planned_speed_mps\":";
  write_number(input.planned_speed_mps);
  std::cout << ",\"heading_bounds_rad\":[";
  write_number(input.constraints.heading_min_rad);
  std::cout << ',';
  write_number(input.constraints.heading_max_rad);
  std::cout << "],\"speed_bounds_mps\":[";
  write_number(input.constraints.speed_min_mps);
  std::cout << ',';
  write_number(input.constraints.speed_max_mps);
  std::cout << "],\"cpa_safe_m\":";
  write_number(input.constraints.cpa_safe_m);
  std::cout << ",\"cpa_hard_m\":";
  write_number(input.constraints.cpa_hard_m);
  std::cout << ",\"rot_max_rad_s\":";
  write_number(input.rot_max_rad_s);
  std::cout << ",\"decel_max_mps2\":";
  write_number(input.decel_max_mps2);
  std::cout << ",\"primary_role\":" << static_cast<int>(input.colregs_primary_role)
            << ",\"preferred_direction\":\""
            << direction_name(input.colregs_preferred_direction)
            << "\",\"min_alteration_rad\":";
  write_number(input.colregs_min_alteration_rad);
  std::cout << ",\"prefix_active_k\":" << input.prefix_active_k
            << ",\"prefix_psi_rad\":[";
  for (std::size_t index = 0; index < input.prefix_psi_rad.size(); ++index) {
    if (index != 0u) std::cout << ',';
    write_number(input.prefix_psi_rad[index]);
  }
  std::cout << "],\"prefix_u_mps\":[";
  for (std::size_t index = 0; index < input.prefix_u_mps.size(); ++index) {
    if (index != 0u) std::cout << ',';
    write_number(input.prefix_u_mps[index]);
  }
  std::cout << "],\"route_frame\":{\"origin_m\":[";
  write_number(input.route_frame_origin_x_m);
  std::cout << ',';
  write_number(input.route_frame_origin_y_m);
  std::cout << "],\"normal\":[";
  write_number(input.route_frame_normal_x);
  std::cout << ',';
  write_number(input.route_frame_normal_y);
  std::cout << "],\"bearing_rad\":";
  write_number(input.route_frame_active_leg_bearing_rad);
  std::cout << ",\"lateral_scale_m\":";
  write_number(input.lateral_scale_m);
  std::cout << ",\"weight\":";
  write_number(input.route_weight);
  std::cout << "},\"normalized\":";
  write_normalized_problem(input, p, lbg, ubg, rows, N);
  std::cout << ",\"targets\":";
  write_targets(input.targets);
  std::cout << '}';
}

void write_row_layout(const RowRegistry& rows, int32_t N, int32_t target_count,
                      int32_t rule_count) {
  const int32_t rot_start = rows.rot_row_start();
  const int32_t speed_start = rows.rot_row_end();
  const int32_t prefix_psi_start = rows.prefix_psi_eq_row(0);
  const int32_t prefix_u_start = rows.prefix_u_eq_row(0);
  const int32_t cpa_start = target_count > 0 ? rows.cpa_row(0, 0)
                                              : prefix_u_start + N;
  const int32_t direction_start = rows.direction_row(0);
  const int32_t min_alt_start = rows.min_alt_row(0);
  const int32_t terminal_start = rows.terminal_row(0);
  const int32_t rule_start = rows.rule_row_start();
  const int32_t zone_start = rows.zone_row_start();
  std::cout << '{';
  write_span("rot", rot_start, 2 * N, false);
  write_span("speed_rate", speed_start, N, true);
  write_span("prefix_psi", prefix_psi_start, N, true);
  write_span("prefix_u", prefix_u_start, N, true);
  write_span("cpa", cpa_start, N * target_count, true);
  write_span("direction", direction_start, N, true);
  write_span("min_alt", min_alt_start, N, true);
  write_span("terminal", terminal_start, 3, true);
  write_span("rule", rule_start, rule_count, true);
  write_span("zone", zone_start, rows.total_rows() - zone_start, true);
  std::cout << '}';
}

bool run_scenario(const Scenario& scenario) {
  g_prepared.clear();
  g_result.clear();
  MidMpcNlpFormulation formulation(scenario.config);
  formulation.set_constraint_inputs(scenario.input.constraints);
  formulation.set_prefix_K(scenario.input.prefix_active_k);
  formulation.build_symbolic_graph();
  MidMpcSolver solver(formulation, MidMpcSolver::IpoptOptions{});
  const MidMpcSolution solution = solver.solve(scenario.input, nullptr);
  if (solution.status != MidMpcSolution::Status::Converged ||
      g_prepared.empty() || g_result.empty()) {
    std::cerr << scenario.id << " failed: " << solution.ipopt_return_status << '\n';
    return false;
  }

  const int32_t N = scenario.config.n_horizon;
  const casadi::DM& raw_x = g_result.at("x");
  const casadi::DM& prepared_p = g_prepared.at("p");
  const casadi::DM& prepared_lbg = g_prepared.at("lbg");
  const casadi::DM& prepared_ubg = g_prepared.at("ubg");
  const double raw_cpa_slack = static_cast<double>(raw_x(2 * N));
  const double raw_dir_slack = static_cast<double>(raw_x(2 * N + 1));
  const ObjectiveComponents objective_components =
      calculate_objective_components(scenario.config, raw_x, prepared_p);

  std::cout << "{\"schema\":\"colav.mid_mpc_ipopt_parity.v1\","
            << "\"fixture_id\":\"" << scenario.id << "\","
            << "\"provenance\":{"
            << "\"source_repository\":\"https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation\","
            << "\"source_commit\":\"ced58f8576f3772ef7c1bc72bb0f8b0368688b5a\","
            << "\"oracle\":\"mass_l3_mid_mpc_cpp_test_trace\","
            << "\"optimizer\":\"CasADi/IPOPT\","
            << "\"casadi_version\":\"" << casadi::CasadiMeta::version() << "\","
            << "\"ipopt_version\":\"" << IPOPT_VERSION << "\","
            << "\"exporter\":\"tools/mid_mpc_ipopt_oracle/export_oracle.sh\"},"
            << "\"tolerances\":{\"objective_abs\":1e-5,"
            << "\"trajectory_abs\":1e-6,\"diagnostic_abs\":1e-6},"
            << "\"input\":{\"config\":";
  write_config(scenario.config);
  std::cout << ",\"problem\":";
  write_problem(scenario.input, prepared_p, prepared_lbg, prepared_ubg,
                formulation.row_registry(), N);
  std::cout << "},\"output\":{\"status\":\"" << status_name(solution.status)
            << "\",\"ipopt_return_status\":\"" << solution.ipopt_return_status
            << "\",\"ipopt_iterations\":" << solution.ipopt_iterations
            << ",\"objective_total\":";
  write_number(static_cast<double>(g_result.at("f")));
  std::cout << ",\"cpa_slack\":";
  write_number(solution.cpa_slack);
  std::cout << ",\"continuous_cpa_min_m\":";
  write_number(solution.continuous_cpa_min_m);
  std::cout << ",\"continuous_cpa_violated\":"
            << (solution.continuous_cpa_violated ? "true" : "false")
            << ",\"trajectory\":";
  write_trajectory(solution);
  std::cout << ",\"objective_components\":";
  write_objective_components(objective_components);
  std::cout << ",\"prepared\":{\"p\":";
  write_dm(g_prepared.at("p"));
  std::cout << ",\"x0\":";
  write_dm(g_prepared.at("x0"));
  std::cout << ",\"lbx\":";
  write_dm(g_prepared.at("lbx"));
  std::cout << ",\"ubx\":";
  write_dm(g_prepared.at("ubx"));
  std::cout << ",\"lbg\":";
  write_dm(g_prepared.at("lbg"));
  std::cout << ",\"ubg\":";
  write_dm(g_prepared.at("ubg"));
  std::cout << "},\"raw\":{\"x\":";
  write_dm(raw_x);
  std::cout << ",\"f\":";
  write_number(static_cast<double>(g_result.at("f")));
  std::cout << ",\"g\":";
  write_dm(g_result.at("g"));
  std::cout << ",\"cpa_slack\":";
  write_number(raw_cpa_slack);
  std::cout << ",\"dir_slack\":";
  write_number(raw_dir_slack);
  std::cout << "},\"row_layout\":";
  write_row_layout(formulation.row_registry(), N,
                   static_cast<int32_t>(scenario.input.targets.size()),
                   static_cast<int32_t>(scenario.input.constraints.applicable_rules.size()));
  std::cout << "}}\n";
  return true;
}

}  // namespace

int main() {
  std::cout << std::setprecision(std::numeric_limits<double>::max_digits10);
  for (const auto& scenario : scenarios()) {
    if (!run_scenario(scenario)) {
      return 2;
    }
  }
  return 0;
}
