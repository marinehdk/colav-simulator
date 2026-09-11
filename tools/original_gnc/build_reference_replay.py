"""Build deterministic drivers around original ROS C++ translation units.

Reference-only: drivers never link the extracted local implementation. Access
control is relaxed by the compiler solely so tests can invoke the original
private callbacks; their compiled bodies are unchanged apart from trace hooks.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from state_fields import SNAPSHOTS

CLASS_NAMES = {
    "ship_dynamics_node.cpp": "ship_dynamics::ShipDynamicsNode",
    "ship_control_node.cpp": "ShipControllerNode",
    "ship_guidance_node.cpp": "ShipGuidanceNode",
    "thrust_allocation_node.cpp": "AutonomousThrustAllocator",
    "coordinate_transform_node.cpp": "CoordinateTransformNode",
    "active_route_manager_node.cpp": "ActiveRouteManagerNode",
    "wind_engine_node.cpp": "env_engines::WindEngineNode",
    "current_engine_node.cpp": "env_engines::CurrentEngineNode",
    "wave_engine_node.cpp": "env_engines::WaveEngineNode",
    "force_aggregator_node.cpp": "env_engines::ForceAggregatorNode",
}

ENV_SOURCES = {
    "wind_engine_node": ["common/env_engine_base.cpp", "common/env_asset_metadata.cpp", "wind/wind_load_model.cpp"],
    "current_engine_node": ["common/env_engine_base.cpp", "common/env_asset_metadata.cpp", "current/current_load_model.cpp"],
    "wave_engine_node": [
        "common/env_engine_base.cpp",
        "common/env_asset_metadata.cpp",
        "wave/wave_spectrum_model.cpp",
        "wave/wave_response_model.cpp",
        "wave/wave_drift_model.cpp",
    ],
}

PARAMETER_CHECK = r"""
void check_parameters(rclcpp::Node* node, const std::string& path) {
    std::ifstream stream(path);
    if (!stream) throw std::runtime_error("Missing typed original parameter expectations");
    nlohmann::json expected; stream >> expected;
    for (const auto& item : expected.items()) {
        const auto parameter = node->get_parameter(item.key());
        const int type = static_cast<int>(parameter.get_type());
        if (type != item.value().at("type")) throw std::runtime_error("Parameter type mismatch: " + item.key());
        nlohmann::json actual;
        switch (type) {
          case 1: actual=parameter.as_bool(); break;
          case 2: actual=parameter.as_int(); break;
          case 3: actual=parameter.as_double(); break;
          case 4: actual=parameter.as_string(); break;
          case 5: actual=parameter.as_byte_array(); break;
          case 6: actual=parameter.as_bool_array(); break;
          case 7: actual=parameter.as_integer_array(); break;
          case 8: actual=parameter.as_double_array(); break;
          case 9: actual=parameter.as_string_array(); break;
          default: throw std::runtime_error("Unsupported parameter type: " + item.key());
        }
        if (actual != item.value().at("value")) throw std::runtime_error("Parameter value mismatch: " + item.key());
    }
}
"""


def driver(source: Path, callbacks: list[dict]) -> str:
    """Dispatch recorded external calls into the original implementation."""
    dispatch = []
    for callback in callbacks:
        name, message = callback["function"], callback["message_type"]
        argument = f'original_reference_trace::decode<{message}>(event.at("input"))' if message else ""
        dispatch.append(f'if (function == "{name}") {{ node->{name}({argument}); }}')
    chain = (
        "\n            else ".join(dispatch)
        + '\n            else { throw std::runtime_error("Unknown original callback: " + function); }'
    )
    return f'''// Reference wrapper around independently compiled original source.
#define main original_node_main_unused
#include "{source}"
#undef main

{PARAMETER_CHECK}

original_reference_trace::Json read_state(const {CLASS_NAMES[source.name]}& node) {{
    using Json = original_reference_trace::Json;
    {SNAPSHOTS.get(source.stem, "return Json::object();")}
}}

int main(int argc, char** argv) {{
    if (argc != 3) {{ std::cerr << "usage: driver node-name effective-parameters.yaml\\n"; return 2; }}
    std::vector<std::string> arguments = {{"reference_replay", "--ros-args", "--params-file",
                                          argv[2], "-r", std::string("__node:=") + argv[1]}};
    std::vector<const char*> pointers;
    for (auto& argument : arguments) pointers.push_back(argument.c_str());
    try {{
        rclcpp::init(static_cast<int>(pointers.size()), pointers.data());
        auto node = std::make_shared<{CLASS_NAMES[source.name]}>();
        check_parameters(node.get(), std::string(argv[2]) + ".typed.json");
        auto& trace = original_reference_trace::store();
        if (!trace.replaying()) throw std::runtime_error("ORIGINAL_GNC_REPLAY_FILE is required");
        const char* state_path = std::getenv("ORIGINAL_GNC_STATE_FILE");
        std::ofstream states;
        if (state_path) {{
            states.open(state_path);
            states << original_reference_trace::Json({{{{"ordinal",-1}},{{"state",read_state(*node)}}}}).dump() << '\\n';
        }}
        while (!trace.finished()) {{
            auto event = trace.next();
            if (event.at("kind") != "call") throw std::runtime_error("Unconsumed event before callback: " + event.dump());
            auto function = event.at("function").get<std::string>();
            {chain}
            trace.check();
            if (states.is_open()) states << original_reference_trace::Json(
                {{{{"ordinal",event.at("ordinal")}},{{"state",read_state(*node)}}}}).dump() << '\\n';
        }}
        std::cout << "REFERENCE_REPLAY_COMPLETE " << trace.index() << std::endl;
        node.reset();
        rclcpp::shutdown();
        return 0;
    }} catch (const std::exception& error) {{
        std::cerr << "REFERENCE_REPLAY_FAILED " << error.what() << std::endl;
        return 1;
    }}
}}
'''


def build(workspace: Path, output: Path, selection: list[str]) -> None:
    """Create and compile dedicated reference replay executables."""
    instrumentation = json.loads((workspace / "instrumentation.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    includes = [p for p in (workspace / "src").glob("*/*/include") if p.is_dir()]
    dependencies = (
        "rclcpp nav_msgs geometry_msgs std_msgs tf2 tf2_ros tf2_geometry_msgs "
        "rcl_interfaces diagnostic_msgs ship_interfaces ament_index_cpp"
    )
    cmake = [
        "cmake_minimum_required(VERSION 3.16)",
        "project(original_gnc_reference_replay)",
        "set(CMAKE_CXX_STANDARD 17)",
        "find_package(ament_cmake REQUIRED)",
        "find_package(Eigen3 REQUIRED)",
    ]
    cmake.extend(f"find_package({name} REQUIRED)" for name in dependencies.split())
    cmake.append("include_directories(" + " ".join(str(p) for p in includes) + ")")
    for item in instrumentation["files"]:
        source = Path(item["file"])
        stem = source.stem
        if stem not in selection:
            continue
        path = output / f"{stem}_replay.cpp"
        path.write_text(driver(source, item["callbacks"]))
        extra = " ".join(str(source.parent.parent / p) for p in ENV_SOURCES.get(stem, []))
        cmake += [
            f"add_executable({stem}_replay {path.name} {extra})",
            f"target_compile_options({stem}_replay PRIVATE -fno-access-control)",
            f"ament_target_dependencies({stem}_replay {dependencies})",
            f"target_link_libraries({stem}_replay Eigen3::Eigen)",
        ]
    (output / "CMakeLists.txt").write_text("\n".join(cmake) + "\n")
    subprocess.run(
        ["cmake", "-S", str(output), "-B", str(output / "build"), "-DCMAKE_BUILD_TYPE=RelWithDebInfo"], check=True
    )
    subprocess.run(["cmake", "--build", str(output / "build"), "-j", "1"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--nodes",
        nargs="+",
        default=["ship_dynamics_node", "ship_control_node", "ship_guidance_node", "thrust_allocation_node"],
    )
    args = parser.parse_args()
    build(args.workspace.resolve(), args.output.resolve(), args.nodes)
