// Repository-owned probe for the frozen source-only v2 pure-model seam.
// It intentionally emits source behavior evidence, not vessel validation.

#include "env_engines/current_load_model.hpp"
#include "env_engines/wave_drift_model.hpp"
#include "env_engines/wave_response_model.hpp"
#include "env_engines/wind_load_model.hpp"

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {

void number(std::ostream& output, double value)
{
    if (std::isfinite(value)) {
        output << std::setprecision(17) << value;
    } else {
        output << "null";
    }
}

void boolean(std::ostream& output, bool value)
{
    output << (value ? "true" : "false");
}

void current_case(std::ostream& output,
                  const env_engines::CurrentEarthFixedResult& velocity,
                  const env_engines::CurrentModelDepthAveraged& averaged,
                  const env_engines::CurrentModelHorizontal& horizontal,
                  const env_engines::CurrentModelLoadResult& load)
{
    output << "{\"name\":\"current_source_models\",\"values\":[";
    number(output, velocity.world_x);
    output << ",";
    number(output, velocity.world_y);
    output << ",";
    number(output, velocity.speed);
    output << ",";
    number(output, velocity.direction_to_deg);
    output << ",";
    boolean(output, velocity.valid);
    output << ",";
    number(output, averaged.v_tide_avg);
    output << ",";
    number(output, averaged.v_wind_avg);
    output << ",";
    number(output, averaged.v_circ_avg);
    output << ",";
    number(output, horizontal.vx);
    output << ",";
    number(output, horizontal.vy);
    output << ",";
    number(output, load.force_x);
    output << ",";
    number(output, load.force_y);
    output << ",";
    number(output, load.torque_x);
    output << ",";
    number(output, load.torque_z);
    output << "]}";
}

void wind_case(std::ostream& output,
               const env_engines::WindModelSpeedProfile& profile,
               const env_engines::WindModelTrueWindResult& true_wind,
               const env_engines::WindModelLoadResult& load)
{
    output << "{\"name\":\"wind_source_models\",\"values\":[";
    number(output, profile.mean_speed_at_z);
    output << ",";
    number(output, profile.target_sigma);
    output << ",";
    number(output, true_wind.speed);
    output << ",";
    number(output, true_wind.direction_to_deg);
    output << ",";
    boolean(output, true_wind.valid);
    output << ",";
    number(output, load.force_x);
    output << ",";
    number(output, load.force_y);
    output << ",";
    number(output, load.torque_x);
    output << ",";
    number(output, load.torque_z);
    output << ",";
    number(output, load.apparent_speed);
    output << ",";
    number(output, load.apparent_direction_deg);
    output << "]}";
}

void wave_case(std::ostream& output,
               const env_engines::WaveModelLoadsSeparated& first_order,
               const env_engines::WaveModelDriftResult& drift)
{
    output << "{\"name\":\"wave_source_models\",\"values\":[";
    number(output, first_order.Fx_1st);
    output << ",";
    number(output, first_order.Fy_1st);
    output << ",";
    number(output, first_order.Mx_1st);
    output << ",";
    number(output, first_order.Mz_1st);
    output << ",";
    number(output, drift.loads.Fx_2nd);
    output << ",";
    number(output, drift.loads.Fy_2nd);
    output << ",";
    number(output, drift.loads.Mx_2nd);
    output << ",";
    number(output, drift.loads.Mz_2nd);
    output << ",";
    boolean(output, drift.output_limited);
    output << ",";
    boolean(output, drift.nonfinite_guarded);
    output << "]}";
}

} // namespace

int main(int argc, char** argv)
{
    if (argc != 2) {
        std::cerr << "usage: frozen_source_probe OUTPUT_JSON\n";
        return 2;
    }

    env_engines::CurrentModelTotalInput current_total;
    current_total.speed = 1.4;
    current_total.direction_deg = 35.0;
    current_total.measurement_depth = 4.0;
    const auto current_components =
        env_engines::CurrentLoadModel::components_from_total(current_total);
    env_engines::CurrentModelDepthAveraged current_averaged;
    const bool current_depth_ok =
        env_engines::CurrentLoadModel::calculate_depth_averaged_currents(
            current_components, 1.55, 30.0, current_averaged);
    env_engines::CurrentModelHorizontal current_horizontal;
    const bool current_horizontal_ok =
        env_engines::CurrentLoadModel::calculate_horizontal_components(
            current_components, current_averaged, current_horizontal);
    const auto current_velocity =
        env_engines::CurrentLoadModel::recover_earth_fixed_velocity(
            1.4,
            35.0,
            false,
            false,
            env_engines::CurrentVelocityReference::EarthFixed,
            42.0,
            3.7,
            -0.25);
    const auto current_coefficients =
        env_engines::CurrentLoadModel::inferred_coefficients(90.0);
    env_engines::CurrentModelLoadInput current_load_input;
    current_load_input.v_total_apparent = 1.4;
    current_load_input.apparent_direction_deg = 90.0;
    current_load_input.draft = 1.55;
    current_load_input.depth = 30.0;
    current_load_input.lpp = 44.1;
    current_load_input.beam = 8.0;
    current_load_input.kg = 7.0;
    const auto current_load =
        env_engines::CurrentLoadModel::calculate_load(
            current_load_input, current_coefficients);

    const auto wind_table = env_engines::WindLoadModel::ocimf_coefficient_table();
    const auto wind_profile =
        env_engines::WindLoadModel::update_wind_speed(12.0, 20.0);
    const auto true_wind = env_engines::WindLoadModel::recover_true_wind(
        8.0, 120.0, true, false, 42.0, 3.7, -0.25);
    env_engines::WindModelLoadInput wind_input;
    wind_input.wind_speed = 15.0;
    wind_input.wind_direction_deg = 270.0;
    wind_input.ship_heading_deg = 42.0;
    wind_input.ship_u = 3.7;
    wind_input.ship_v = -0.25;
    wind_input.frontal_area = 200.0;
    wind_input.lateral_area = 400.0;
    wind_input.lpp = 44.1;
    wind_input.z_center = 10.0;
    const auto wind_load =
        env_engines::WindLoadModel::calculate_load(wind_input, wind_table);

    env_engines::WaveModelVesselParams vessel;
    vessel.Lpp = 44.1;
    vessel.Los = 46.0;
    vessel.B = 8.0;
    vessel.T = 1.55;
    vessel.KG = 7.0;
    vessel.GM_T = 1.5;
    vessel.displacement_ton = 8000.0;
    const std::vector<env_engines::WaveModelComponent> waves = {
        {0.7, 0.8, 0.04, 0.1},
        {0.35, 1.2, 0.10, -0.4},
    };
    const std::vector<env_engines::WaveModelDirectionalSample> directions = {
        {0.0, 1.0},
        {0.3, 0.5},
        {-0.25, 0.5},
    };
    env_engines::WaveResponseConfig response_config;
    const double heave_natural_frequency =
        env_engines::WaveResponseModel::update_heave_natural_freq(
            vessel, response_config.water_density, response_config.gravity);
    const double roll_natural_frequency =
        env_engines::WaveResponseModel::update_roll_natural_freq(
            vessel, response_config.gravity);
    const auto first_order =
        env_engines::WaveResponseModel::calculate_first_order_loads(
            0.4,
            12.5,
            vessel,
            waves,
            directions,
            4.2,
            -0.3,
            heave_natural_frequency,
            roll_natural_frequency,
            response_config);
    env_engines::WaveDriftModelConfig drift_config;
    env_engines::WaveModelDriftLimits drift_limits;
    const auto drift =
        env_engines::WaveDriftModelCalculator::calculate_inferred_drift_loads(
            0.4, vessel, waves, directions, drift_config, drift_limits);

    std::ofstream output(argv[1], std::ios::binary | std::ios::trunc);
    if (!output) {
        std::cerr << "unable to open output JSON: " << argv[1] << "\n";
        return 1;
    }
    output << "{\"schema_version\":\"agx-l45-characterization-output.v1\","
              "\"evidence_kind\":\"SOURCE_BEHAVIOR_CHARACTERIZATION\","
              "\"claim_ceiling\":\"not_vessel_validation\","
              "\"source_kernel_seam\":\"env_engines_pure_load_models\","
              "\"seed\":20260824,"
              "\"checks\":{";
    output << "\"current_depth_ok\":";
    boolean(output, current_depth_ok);
    output << ",\"current_horizontal_ok\":";
    boolean(output, current_horizontal_ok);
    output << "},\"natural_frequencies\":{";
    output << "\"heave\":";
    number(output, heave_natural_frequency);
    output << ",\"roll\":";
    number(output, roll_natural_frequency);
    output << "},\"cases\":[";
    current_case(output, current_velocity, current_averaged, current_horizontal, current_load);
    output << ",";
    wind_case(output, wind_profile, true_wind, wind_load);
    output << ",";
    wave_case(output, first_order, drift);
    output << "]}\n";
    if (!output) {
        std::cerr << "unable to write output JSON\n";
        return 1;
    }
    return 0;
}
