"""Read-only state observation contracts shared by the two trace formats.

These are field accessors, not expected values or algorithm implementations.
The reference and embedded builds use their independently compiled objects.
"""

SNAPSHOTS = {
    "coordinate_transform_node": """
return {{"origin_locked",node.origin_locked_}, {"origin_lat",node.origin_lat_}, {"origin_lon",node.origin_lon_},
        {"last_route_id",node.last_route_id_}, {"has_route",node.has_last_route_},
        {"first_waypoints_published",node.first_waypoints_published_},
        {"pending_initial_waypoints",node.has_pending_initial_waypoints_},
        {"has_odom",node.has_odom_}, {"north_m",node.current_x_}, {"east_m",node.current_y_}};
""",
    "active_route_manager_node": """
return {{"has_nominal_route",node.has_nominal_route_}, {"active_avoidance",node.has_active_avoidance_},
        {"active_avoidance_plan_id",node.active_avoidance_plan_id_}, {"active_route_id",node.active_route_id_},
        {"active_command_source",node.active_command_source_}, {"generated_route_sequence",node.generated_route_sequence_},
        {"active_avoidance_until_ns",node.active_avoidance_until_.nanoseconds()},
        {"nominal_route_id",node.latest_nominal_route_.route_id},
        {"nominal_route_revision",node.latest_nominal_route_.route_revision}};
""",
    "ship_dynamics_node": """
Json result = {{"eta", std::vector<double>(node.eta_.data(), node.eta_.data()+4)},
               {"nu", std::vector<double>(node.nu_.data(), node.nu_.data()+4)},
               {"tau_thruster", std::vector<double>(node.tau_thruster_.data(), node.tau_thruster_.data()+4)},
               {"tau_env", std::vector<double>(node.tau_env_.data(), node.tau_env_.data()+4)},
               {"last_time_ns", node.last_time_.nanoseconds()},
               {"f_mass", node.f_mass_cached_}, {"f_drag", node.f_drag_cached_}};
result["actuators"] = Json::array();
for (const auto& t : node.thrusters_) result["actuators"].push_back({
    {"name",t.name}, {"cmd_force_n",t.cmd_thrust}, {"actual_force_n",t.actual_thrust},
    {"cmd_angle_rad",t.cmd_angle}, {"actual_angle_rad",t.actual_angle}});
return result;
""",
    "ship_control_node": """
return {{"integrals", {node.integral_surge_,node.integral_sway_,node.integral_yaw_,node.integral_speed_}},
        {"previous_errors", {node.prev_error_surge_,node.prev_error_sway_,node.prev_error_yaw_,node.prev_error_speed_}},
        {"previous_derivatives", {node.prev_deriv_surge_,node.prev_deriv_sway_,node.prev_deriv_yaw_}},
        {"mode",static_cast<int>(node.active_mode_)}, {"last_time_ns",node.last_time_.nanoseconds()},
        {"quiet_zone",node.autopilot_quiet_zone_active_}, {"dp_deadband",node.dp_position_deadband_active_}};
""",
    "ship_guidance_node": """
return {{"integral_e",node.integral_e_}, {"previous_e",node.prev_e_}, {"previous_heading",node.psi_cmd_prev_},
        {"segment_index",node.current_wp_idx_}, {"dp_mode",node.dp_mode_active_},
        {"final_dp_latched",node.final_dp_latched_}, {"last_time_ns",node.last_time_.nanoseconds()}};
""",
    "thrust_allocation_node": """
Json result = {{"previous_tau",std::vector<double>(node.tau_des_prev_.data(),node.tau_des_prev_.data()+3)},
               {"policy_speed_mps",node.side_thruster_policy_speed_mps_},
               {"side_thruster_allowed",node.side_thruster_speed_allowed_state_},
               {"previous_rudder_rad",node.last_rudder_cmd_}};
result["actuators"] = Json::array();
for (const auto& s : node.states_) result["actuators"].push_back({
    {"last_force_n",s.last_thrust_N},{"last_angle_rad",s.last_angle_rad},
    {"healthy",s.is_healthy},{"health_score",s.health_score}});
return result;
""",
}

SNAPSHOTS.update(
    {
        "wind_engine_node": """
auto engine = node.rng_;
Json rng = Json::array();
for (int i=0; i<624; ++i) rng.push_back(engine());
Json result = {{"rng_next_uint32",rng}, {"sim_time_s",node.sim_time_}, {"calc_count",node.calc_count_},
               {"effective_source",static_cast<int>(node.effective_wind_source_)},
               {"direction_fluctuation_deg",node.wind_direction_fluctuation_deg_},
               {"u_avg_mps",node.u_avg_z_}, {"target_sigma_mps",node.target_sigma_}};
result["components"] = Json::array();
for (const auto& c : node.components_) result["components"].push_back(
    {{"frequency_hz",c.freq}, {"amplitude_mps",c.amplitude}, {"phase_rad",c.phase}});
return result;
""",
        "current_engine_node": """
auto engine = node.current_rng_;
Json rng = Json::array();
for (int i=0; i<624; ++i) rng.push_back(engine());
return {{"rng_next_uint32",rng}, {"calc_count",node.calc_count_},
        {"fluctuation_u_mps",node.current_fluctuation_u_}, {"fluctuation_v_mps",node.current_fluctuation_v_},
        {"depth_correction_ratio",node.last_depth_correction_factor_},
        {"last_update_ns",node.last_update_time_.nanoseconds()}, {"coeff_table_loaded",node.coeff_table_loaded_}};
""",
        "wave_engine_node": """
auto engine = node.wave_rng_;
Json rng = Json::array();
for (int i=0; i<624; ++i) rng.push_back(engine());
Json result = {{"rng_next_uint32",rng}, {"sim_time_s",node.sim_time_}, {"calc_count",node.calc_count_},
               {"spectrum_initialized",node.spectrum_initialized_},
               {"spectrum_hs_m",node.spectrum_hs_}, {"spectrum_tz_s",node.spectrum_tz_},
               {"spectrum_depth_m",node.spectrum_depth_}, {"last_update_ns",node.last_update_time_.nanoseconds()},
               {"drift_limited",node.last_drift_output_limited_.load()},
               {"nonfinite_guarded",node.last_drift_nonfinite_guarded_.load()}};
result["components"] = Json::array();
for (const auto& c : node.wave_components_) result["components"].push_back(
    {{"amplitude_m",c.amplitude}, {"omega_radps",c.omega}, {"k_per_m",c.k}, {"phase_rad",c.phase}});
return result;
""",
        "force_aggregator_node": """
return {{"received",{node.wave_received_.load(),node.current_received_.load(),node.wind_received_.load()}},
        {"health_received",{node.wave_health_received_.load(),node.current_health_received_.load(),node.wind_health_received_.load()}},
        {"receipt_ns",{node.last_wave_time_.nanoseconds(),node.last_current_time_.nanoseconds(),node.last_wind_time_.nanoseconds()}},
        {"sample_ns",{node.last_wave_sample_stamp_.nanoseconds(),node.last_current_sample_stamp_.nanoseconds(),node.last_wind_sample_stamp_.nanoseconds()}},
        {"rejected_counts",{node.rejected_wave_load_count_,node.rejected_current_load_count_,node.rejected_wind_load_count_}},
        {"publish_count",node.publish_count_}, {"first_wait",node.first_wait_}};
""",
    }
)
