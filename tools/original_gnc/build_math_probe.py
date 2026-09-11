"""Probe the actual native shared library or independently compiled original plant math."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from build_reference_replay import PARAMETER_CHECK


def generated(source: Path, native: bool) -> str:
    """Keep component expressions verbatim and call actual RHS/RK4 implementations."""
    text = source.read_text()
    start = text.index("Eigen::Vector4d ShipDynamicsNode::compute_nu_dot")
    component = text[text.index("    Eigen::Vector4d D =", start) : text.index("    return M_inv_", start)]
    start = text.index("Eigen::Vector4d ShipDynamicsNode::runge_kutta4")
    stages = text[text.index("    Eigen::Vector4d k1 =", start) : text.index("    return nu +", start)]
    stages = stages.replace("compute_nu_dot(", "node.compute_nu_dot(")
    include = (
        (
            '#include "native_context.hpp"\n#include "ship_dynamics/ship_dynamics_node.hpp"\n'
            "using DepthMessage = original_gnc::messages::std_msgs::Float64;"
        )
        if native
        else (
            f'#define main unused_original_main\n#include "{source}"\n#undef main\n'
            "using DepthMessage = std_msgs::msg::Float64;"
        )
    )
    create = (
        (
            'original_gnc::Context context("ship_dynamics_node", request.at("parameters"), request.at("options"));\n'
            "ship_dynamics::ShipDynamicsNode node(context);"
        )
        if native
        else (
            'if (argc != 4) throw std::runtime_error("reference needs original parameter YAML");\n'
            'const char* arguments[] = {"math_probe", "--ros-args", "--params-file", argv[3], '
            '"-r", "__node:=ship_dynamics_node", "--log-level", "error"};\n'
            "rclcpp::init(8, arguments);\n"
            "ship_dynamics::ShipDynamicsNode node;\n"
            'check_parameters(&node, std::string(argv[3]) + ".typed.json");'
        )
    )
    return f"""// Test-only observer; native mode links the actual packaged shared library.
{include}
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
using Json = nlohmann::json;
{"" if native else PARAMETER_CHECK}
template<class Derived> Json values(const Eigen::MatrixBase<Derived>& input) {{
    Json result=Json::array();
    for (int row=0;row<input.rows();++row) {{
        if (input.cols()==1) result.push_back(input(row,0));
        else {{
            Json line=Json::array();
            for(int col=0;col<input.cols();++col) line.push_back(input(row,col));
            result.push_back(line);
        }}
    }}
    return result;
}}
int main(int argc,char** argv) {{
    try {{
        if(argc<3) throw std::runtime_error("usage: math-probe request.json result.jsonl [original-parameters.yaml]");
        std::ifstream input(argv[1]); Json request; input >> request;
        std::ofstream output(argv[2]);
        {create}
        for (const auto& item:request.at("cases")) {{
            auto depth=std::make_shared<DepthMessage>(); depth->data=item.at("water_depth_m");
            node.water_depth_callback(depth);
            Eigen::Vector4d nu, tau_total;
            for(int index=0;index<4;++index) {{
                nu[index]=item.at("nu").at(index); tau_total[index]=item.at("tau").at(index);
            }}
            const double current_roll=item.at("roll_rad"),dt=item.at("dt_s");
            const auto& v_config_=node.v_config_;
            const double f_drag_cached_=node.f_drag_cached_,f_mass_cached_=node.f_mass_cached_;
            const double u=nu[0],v=nu[1],p=nu[2],r=nu[3];
{component}
            const Eigen::Vector4d rhs=node.compute_nu_dot(nu,tau_total,current_roll);
            const Eigen::Vector4d reconstruction=node.M_inv_*tau_net;
{stages}
            const Eigen::Vector4d rk=node.runge_kutta4(nu,tau_total,current_roll,dt);
            output << Json({{{{"case_id",item.at("case_id")}},{{"M",values(node.M_)}},{{"M_inverse",values(node.M_inv_)}},
                {{"C",values(C)}},{{"D",values(D)}},{{"C_nu",values(C_vec)}},{{"restoring_roll_nm",tau_restoring_p}},
                {{"rhs",values(rhs)}},{{"decomposition_residual",values(rhs-reconstruction)}},
                {{"k1",values(k1)}},{{"k2",values(k2)}},{{"k3",values(k3)}},{{"k4",values(k4)}},
                {{"nu_k2",values(nu_k2)}},{{"nu_k3",values(nu_k3)}},
                {{"nu_k4",values(nu_k4)}},{{"rk_result",values(rk)}}}}).dump() << '\\n';
        }}
        return 0;
    }} catch(const std::exception& error) {{ std::cerr << error.what() << std::endl; return 1; }}
}}
"""


def build(source: Path, output: Path, native_build: Path | None = None, workspace: Path | None = None) -> None:
    """Identify probe source, compiler and actual linked algorithm provenance."""
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    cpp = output / "math_probe.cpp"
    cpp.write_text(generated(source, native_build is not None))
    if native_build:
        manifest = json.loads((native_build / "build-manifest.json").read_text())
        previous = manifest["command"]
        eigen = previous[previous.index("-isystem") + 1]
        dependencies = previous[previous.index("-isystem", previous.index("-isystem") + 1) + 1]
        command = [
            previous[0],
            "-std=c++17",
            "-O2",
            "-g",
            "-ffp-contract=off",
            "-fno-access-control",
            "-include",
            str(native_build / "reference_arithmetic.hpp"),
            "-I",
            str(native_build / "include"),
            "-isystem",
            eigen,
            "-isystem",
            dependencies,
            str(cpp),
            manifest["library"],
            "-o",
            str(output / "math_probe"),
        ]
        subprocess.run(command, check=True)
        identity = {
            "native_library_sha256": manifest["library_sha256"],
            "native_build": str(native_build),
            "command": command,
        }
    else:
        dependencies = (
            "rclcpp nav_msgs geometry_msgs std_msgs tf2 tf2_ros tf2_geometry_msgs "
            "rcl_interfaces diagnostic_msgs ship_interfaces ament_index_cpp"
        )
        cmake = [
            "cmake_minimum_required(VERSION 3.16)",
            "project(original_math_reference)",
            "set(CMAKE_CXX_STANDARD 17)",
            "find_package(ament_cmake REQUIRED)",
            "find_package(Eigen3 REQUIRED)",
        ]
        cmake += [f"find_package({name} REQUIRED)" for name in dependencies.split()]
        includes = " ".join(str(p) for p in (workspace / "src").glob("*/*/include"))
        cmake += [
            f"include_directories({includes})",
            "add_executable(math_probe math_probe.cpp)",
            "target_compile_options(math_probe PRIVATE -fno-access-control)",
            f"ament_target_dependencies(math_probe {dependencies})",
            "target_link_libraries(math_probe Eigen3::Eigen)",
        ]
        (output / "CMakeLists.txt").write_text("\n".join(cmake) + "\n")
        subprocess.run(
            ["cmake", "-S", str(output), "-B", str(output / "build"), "-DCMAKE_BUILD_TYPE=RelWithDebInfo"], check=True
        )
        subprocess.run(["cmake", "--build", str(output / "build"), "-j", "1"], check=True)
        identity = {"original_source": str(source), "embedded_library_linked": False, "workspace": str(workspace)}
    identity.update(
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        probe_sha256=hashlib.sha256(cpp.read_bytes()).hexdigest(),
        components=(
            "M read directly; C/D/local force expressions observed via verbatim source expressions "
            "and checked against actual RHS; RHS and all RK stages call the executing implementation"
        ),
    )
    (output / "manifest.json").write_text(json.dumps(identity, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--native-build", type=Path)
    group.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    build(
        args.source.resolve(),
        args.output.resolve(),
        args.native_build.resolve() if args.native_build else None,
        args.workspace.resolve() if args.workspace else None,
    )
