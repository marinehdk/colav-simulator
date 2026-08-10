#include <casadi/casadi.hpp>
#include <coin-or/IpoptConfig.h>

#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

#include "m5_tactical_planner/mid_mpc/mid_mpc_nlp_formulation.hpp"
#include "m5_tactical_planner/mid_mpc/mid_mpc_solver.hpp"

namespace {

using mass_l3::m5::MidMpcInput;
using mass_l3::m5::MidMpcSolution;
using mass_l3::m5::mid_mpc::MidMpcNlpFormulation;
using mass_l3::m5::mid_mpc::MidMpcSolver;

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

void write_number(double value) {
  if (std::isfinite(value)) {
    std::cout << value;
  } else if (value > 0.0) {
    std::cout << "\"Infinity\"";
  } else {
    std::cout << "\"-Infinity\"";
  }
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

double evaluate_target_free_objective(const MidMpcSolution& solution,
                                      const MidMpcNlpFormulation::Config& config,
                                      const MidMpcInput& input) {
  double heading_cost = 0.0;
  double speed_cost = 0.0;
  double route_cost = 0.0;
  double terminal_lateral = 0.0;
  for (const auto& point : solution.trajectory) {
    const double heading_error = point.psi_rad - input.planned_route_bearing_rad;
    const double speed_error = point.u_mps - input.planned_speed_mps;
    const double lateral =
        (point.x_m - input.route_frame_origin_x_m) * input.route_frame_normal_x +
        (point.y_m - input.route_frame_origin_y_m) * input.route_frame_normal_y;
    const double normalized_lateral = lateral / input.lateral_scale_m;
    heading_cost += heading_error * heading_error;
    speed_cost += speed_error * speed_error;
    route_cost += normalized_lateral * normalized_lateral;
    terminal_lateral = normalized_lateral;
  }
  route_cost += 2.0 * terminal_lateral * terminal_lateral;
  route_cost *= input.route_weight;
  return config.w_dist * heading_cost + config.w_vel * speed_cost +
         config.w_route * route_cost;
}

}  // namespace

int main() {
  MidMpcNlpFormulation::Config config;
  config.n_horizon = 4;
  config.dt_s = 5.0;
  config.max_targets = 16;
  config.continuous_cpa_enabled = false;

  MidMpcInput input;
  input.own_ship.psi_rad = 0.1;
  input.own_ship.u_mps = 4.0;
  input.planned_route_bearing_rad = 0.2;
  input.planned_speed_mps = 4.5;
  input.constraints.heading_min_rad = -0.5;
  input.constraints.heading_max_rad = 0.8;
  input.constraints.speed_min_mps = 0.0;
  input.constraints.speed_max_mps = 8.0;
  input.constraints.cpa_safe_m = 1852.0;
  input.constraints.cpa_hard_m = 360.0;
  input.constraints.own_ship_psi_rad = input.own_ship.psi_rad;
  input.rot_max_rad_s = 0.05;
  input.decel_max_mps2 = 0.08;
  input.route_frame_origin_x_m = 0.0;
  input.route_frame_origin_y_m = 0.0;
  input.route_frame_normal_x = 0.0;
  input.route_frame_normal_y = 1.0;
  input.route_frame_active_leg_bearing_rad = 0.2;
  input.lateral_scale_m = 400.0;
  input.route_weight = 1.0;

  MidMpcNlpFormulation formulation(config);
  formulation.set_constraint_inputs(input.constraints);
  formulation.set_prefix_K(0);
  formulation.build_symbolic_graph();
  MidMpcSolver solver(formulation, MidMpcSolver::IpoptOptions{});
  const MidMpcSolution solution = solver.solve(input, nullptr);
  if (solution.status != MidMpcSolution::Status::Converged) {
    std::cerr << "frozen Mid-MPC did not converge: "
              << solution.ipopt_return_status << '\n';
    return 2;
  }
  const double objective_total =
      evaluate_target_free_objective(solution, config, input);

  std::cout << std::setprecision(std::numeric_limits<double>::max_digits10);
  std::cout
      << "{\"schema\":\"colav.mid_mpc_ipopt_parity.v1\","
      << "\"fixture_id\":\"route_speed_cold\","
      << "\"provenance\":{"
      << "\"source_repository\":\"https://gitlab.sangoai.com/mass_devgroup/01-dynamics/01-simulation\","
      << "\"source_commit\":\"ced58f8576f3772ef7c1bc72bb0f8b0368688b5a\","
      << "\"oracle\":\"mass_l3_mid_mpc_cpp\","
      << "\"optimizer\":\"CasADi/IPOPT\","
      << "\"casadi_version\":\"" << casadi::CasadiMeta::version() << "\","
      << "\"ipopt_version\":\"" << IPOPT_VERSION << "\","
      << "\"exporter\":\"tools/mid_mpc_ipopt_oracle/export_oracle.sh\"},"
      << "\"tolerances\":{\"objective_abs\":1e-5,"
      << "\"trajectory_abs\":1e-6,\"diagnostic_abs\":1e-6},"
      << "\"input\":{\"config\":{\"N\":4,\"dt\":5.0,"
      << "\"cpa_slack_enabled\":true,\"dir_slack_enabled\":true,"
      << "\"continuous_cpa_enabled\":false},"
      << "\"problem\":{\"own_ship\":{\"psi_rad\":0.1,\"u_mps\":4.0},"
      << "\"route_bearing_rad\":0.2,\"planned_speed_mps\":4.5,"
      << "\"heading_bounds_rad\":[-0.5,0.8],\"speed_bounds_mps\":[0.0,8.0],"
      << "\"rot_max_rad_s\":0.05,\"decel_max_mps2\":0.08,"
      << "\"route_frame\":{\"origin_m\":[0.0,0.0],"
      << "\"normal\":[0.0,1.0],\"bearing_rad\":0.2,"
      << "\"lateral_scale_m\":400.0,\"weight\":1.0},"
      << "\"targets\":[]}},"
      << "\"output\":{\"status\":\"" << status_name(solution.status)
      << "\",\"ipopt_return_status\":\"" << solution.ipopt_return_status
      << "\",\"ipopt_iterations\":" << solution.ipopt_iterations
      << ",\"objective_total\":";
  write_number(objective_total);
  std::cout << ",\"cpa_slack\":";
  write_number(solution.cpa_slack);
  std::cout << ",\"continuous_cpa_min_m\":";
  write_number(solution.continuous_cpa_min_m);
  std::cout << ",\"continuous_cpa_violated\":"
            << (solution.continuous_cpa_violated ? "true" : "false")
            << ",\"trajectory\":";
  write_trajectory(solution);
  std::cout << "}}\n";
  return 0;
}
