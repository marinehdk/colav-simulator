"""Compile source message contracts into ordinary C++ value types, without ROS.

No transport, services, node emulation, or runtime generated-message library is
used. Field layout/defaults come from the reference host's frozen .msg inputs.
"""

from __future__ import annotations

import re
from pathlib import Path

PRIMITIVES = {
    "bool": "bool",
    "byte": "uint8_t",
    "char": "uint8_t",
    "int8": "int8_t",
    "uint8": "uint8_t",
    "int16": "int16_t",
    "uint16": "uint16_t",
    "int32": "int32_t",
    "uint32": "uint32_t",
    "int64": "int64_t",
    "uint64": "uint64_t",
    "float32": "float",
    "float64": "double",
    "string": "std::string",
}


def generate(source: Path, dependencies: Path, output: Path) -> dict:
    """Resolve message dependencies and emit strict JSON value conversions."""
    roots = {path.name: path / "msg" for path in (dependencies / "ros_messages").iterdir() if path.is_dir()}
    roots["ship_interfaces"] = source / "src/interfaces/ship_interfaces/msg"
    declarations = []
    emitted = set()
    required = {
        "nav_msgs/Odometry",
        "nav_msgs/Path",
        "geometry_msgs/TransformStamped",
        "geometry_msgs/WrenchStamped",
        "geometry_msgs/PoseStamped",
        "std_msgs/Bool",
        "std_msgs/Float64",
        "std_msgs/Float64MultiArray",
        "std_msgs/Int32",
        "std_msgs/String",
        "diagnostic_msgs/DiagnosticArray",
        "rcl_interfaces/SetParametersResult",
        "builtin_interfaces/Duration",
        *[f"ship_interfaces/{p.stem}" for p in roots["ship_interfaces"].glob("*.msg")],
    }
    paths = []

    def emit(identity: str):
        if identity in emitted:
            return
        package, name = identity.split("/")
        path = roots[package] / f"{name}.msg"
        fields, constants = [], []
        for raw_line in path.read_text().splitlines():
            line = raw_line.partition("#")[0].strip()
            if not line:
                continue
            match = re.fullmatch(r"(\S+)\s+(\w+)(?:\s*=\s*(.*)|\s+(.*))?", line)
            if match is None:
                raise ValueError(f"Unsupported message field in {path}: {line}")
            token, field, constant, default = match.groups()
            array = re.fullmatch(r"(.+)\[(\d*)\]", token)
            base = array[1] if array else token
            if base in PRIMITIVES:
                cpp = PRIMITIVES[base]
            else:
                dependency = base if "/" in base else f"{package}/{base}"
                emit(dependency)
                dep_package, dep_name = dependency.split("/")
                cpp = f"original_gnc::messages::{dep_package}::{dep_name}"
            if array:
                cpp = f"std::array<{cpp}, {array[2]}>" if array[2] else f"std::vector<{cpp}>"
            if constant is not None:
                constants.append(f"    static constexpr {cpp} {field} = {constant};")
            else:
                initial = "{}"
                if default is not None:
                    initial = "{" + (default.lower() if base == "bool" else default) + "}"
                fields.append((field, f"    {cpp} {field}{initial};"))
        declarations.append(
            f"namespace original_gnc::messages::{package} {{\nstruct {name} {{\n"
            f"    using SharedPtr = std::shared_ptr<{name}>;\n"
            f"    using ConstSharedPtr = std::shared_ptr<const {name}>;\n"
            f'    static constexpr const char* type_name = "{package}/msg/{name}";\n'
            + "\n".join(constants + [text for _, text in fields])
            + "\n};\n"
            + f"inline void to_json(nlohmann::json& j, const {name}& value) {{\n    j = nlohmann::json::object();\n"
            + "\n".join(f'    j["{field}"] = original_gnc::encode_value(value.{field});' for field, _ in fields)
            + "\n}\n"
            + f"inline void from_json(const nlohmann::json& j, {name}& value) {{\n"
            + "\n".join(
                f'    value.{field} = original_gnc::decode_value<decltype(value.{field})>(j.at("{field}"));'
                for field, _ in fields
            )
            + "\n}\n}\n"
        )
        paths.append(str(path))
        emitted.add(identity)

    for identity in sorted(required):
        emit(identity)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "#pragma once\n#include <array>\n#include <cstdint>\n#include <memory>\n"
        '#include <string>\n#include <vector>\n#include <nlohmann/json.hpp>\n#include "value_codec.hpp"\n\n'
        + "\n".join(declarations)
    )
    return {"messages": sorted(emitted), "source_files": paths}
