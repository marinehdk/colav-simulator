"""Extract frozen original C++ algorithms onto explicit native interfaces.

The transformation removes ROS wiring and filesystem/log presentation, keeps
the original state and numerical/strategy expressions, and records every edit.
It never consumes reference-driver generated code or changes the frozen source.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from extract_observers import extract as extract_observers
from extract_policy import extract_policy
from instrument_reference import closing, code_mask
from native_messages import generate as generate_messages
from prepare_reference import SOURCE_MANIFEST_SHA256

MODULES = {
    "ship_dynamics_node": ("simulation/ship_dynamics", "ship_dynamics::ShipDynamicsNode", "ShipDynamicsNode"),
    "ship_control_node": ("gnc/ship_control", "ShipControllerNode", "ShipControllerNode"),
    "ship_guidance_node": ("gnc/ship_guidance", "ShipGuidanceNode", "ShipGuidanceNode"),
    "thrust_allocation_node": ("gnc/thrust_allocation", "AutonomousThrustAllocator", "AutonomousThrustAllocator"),
    "coordinate_transform_node": ("gnc/ship_guidance", "CoordinateTransformNode", "CoordinateTransformNode"),
    "active_route_manager_node": ("gnc/ship_guidance", "ActiveRouteManagerNode", "ActiveRouteManagerNode"),
    "wind_engine_node": ("environment/env_engines", "env_engines::WindEngineNode", "WindEngineNode"),
    "current_engine_node": ("environment/env_engines", "env_engines::CurrentEngineNode", "CurrentEngineNode"),
    "wave_engine_node": ("environment/env_engines", "env_engines::WaveEngineNode", "WaveEngineNode"),
    "force_aggregator_node": ("environment/env_engines", "env_engines::ForceAggregatorNode", "ForceAggregatorNode"),
}
MESSAGE_PACKAGES = (
    "builtin_interfaces",
    "std_msgs",
    "geometry_msgs",
    "nav_msgs",
    "diagnostic_msgs",
    "ship_interfaces",
    "rcl_interfaces",
)


def blank(text: str) -> str:
    """Keep source line positions stable while removing an interface statement."""
    return "".join("\n" if c == "\n" else " " for c in text)


# Keep source contract branches together for audit against the frozen implementation.
def source_edits(text: str, name: str, class_name: str | None) -> tuple[str, dict]:  # noqa: C901, PLR0912, PLR0915
    """Apply reviewed interface categories, rejecting overlapping removals."""
    before = text
    ledger = []
    omitted_clocks = set()
    removed_fields = set()
    output_fields = set()
    callbacks = []
    timers = []
    timer_fields = set()

    def apply(edits: Any):
        nonlocal text
        for start, end, replacement, kind in sorted(edits, reverse=True):
            ledger.append({"kind": kind, "before": text[start:end], "after": replacement})
            text = text[:start] + replacement + text[end:]

    mask = code_mask(text)
    edits = []
    for match in re.finditer(r"(?:this->)?get_clock\(\)->now\(\)|this->now\(\)|(?<![\w:>.])now\(\)", mask):
        line = text.count("\n", 0, match.start()) + 1
        edits.append((match.start(), match.end(), f'clock_.read("{name}:{line}")', "explicit_clock"))
    apply(edits)

    if name == "force_aggregator_node.cpp":
        # GCC evaluates these function arguments right-to-left. Make that
        # observed source clock-consumption order explicit across compilers.
        mask = code_mask(text)
        edits = []
        for match in re.finditer(r"(?m)^    append_source\(", mask):
            end = closing(mask, mask.index("(", match.start())) + 2
            call = text[match.start() : end]
            ages = list(re.finditer(r"source_age_s\((\w+)\)", call))
            if len(ages) != 3:
                raise ValueError("Unknown original environment age evaluation")
            declarations = [f"const double native_age_{i} = {age[0]};" for i, age in reversed(list(enumerate(ages)))]
            for i, age in reversed(list(enumerate(ages))):
                call = call[: age.start()] + f"native_age_{i}" + call[age.end() :]
            replacement = "{ " + " ".join(declarations) + call + " }"
            edits.append((match.start(), end, replacement, "reference_argument_clock_order"))
        apply(edits)

    # Process scheduling belongs to the host, outside the extracted equations.
    if name == "env_engine_base.cpp":
        match = re.search(r"bool EnvEngineBase::set_realtime_priority\(\)\s*\{", text)
        end = closing(code_mask(text), text.index("{", match.start()), "{", "}") + 1
        apply(
            [
                (
                    match.start(),
                    end,
                    "bool EnvEngineBase::set_realtime_priority() { return false; }"
                    + "\n" * text[match.start() : end].count("\n"),
                    "external_process_scheduling",
                )
            ]
        )

    # Native diagnostics are collected by the embedding boundary. Remove log
    # presentation while tracking clock reads that existed ONLY in log args.
    mask = code_mask(text)
    edits = []
    for match in re.finditer(r"\bRCLCPP_[A-Z_]+\s*\(", mask):
        start = mask.index("(", match.start())
        end = closing(mask, start) + 1
        while end < len(mask) and mask[end].isspace():
            end += 1
        if end < len(mask) and mask[end] == ";":
            end += 1
        omitted_clocks.update(re.findall(r'clock_\.read\("([^"]+)"\)', text[match.start() : end]))
        edits.append((match.start(), end, ";" + blank(text[match.start() : end]), "log_presentation"))
    apply(edits)

    # Standalone ROS main and CSV presentation are not algorithm entry points.
    mask = code_mask(text)
    edits = []
    for pattern in (
        r"\bint\s+main\s*\(",
        r"\bvoid\s+ShipDynamicsNode::(?:initialize_csv_file|record_to_csv)\s*\(",
        r"\bvoid\s+CoordinateTransformNode::(?:init_feedback_log|write_feedback_log)\s*\(",
    ):
        for match in re.finditer(pattern, mask):
            end_args = closing(mask, mask.index("(", match.start()))
            body = mask.find("{", end_args)
            end = closing(mask, body, "{", "}") + 1
            omitted_clocks.update(re.findall(r'clock_\.read\("([^"]+)"\)', text[match.start() : end]))
            edits.append((match.start(), end, blank(text[match.start() : end]), "external_process_or_csv"))
    apply(edits)
    # Calls/declarations to removed CSV functions; their output will instead
    # be the embedding trace. No physical state update is removed.
    text = re.sub(r"(?m)^\s*(?:void\s+)?(?:initialize_csv_file|record_to_csv)\(\)\s*;", lambda m: blank(m[0]), text)
    text = re.sub(r"(?m)^\s*(?:void\s+)?(?:init_feedback_log|write_feedback_log)\([^;]*\)\s*;", lambda m: blank(m[0]), text)

    # Remember the exact callbacks registered by the original constructor.
    mask = code_mask(text)
    bindings = set(re.findall(r"std::bind\s*\(\s*&([\w:]+)::(\w+)", mask))
    for klass, callback in sorted(bindings):
        for match in re.finditer(rf"\bvoid\s+(?:{re.escape(klass)}::)?{re.escape(callback)}\s*\(", mask):
            opening = mask.index("(", match.start())
            args_end = closing(mask, opening)
            body = args_end + 1
            while body < len(mask) and mask[body].isspace():
                body += 1
            if body >= len(mask) or mask[body] != "{":
                continue
            arguments = text[opening + 1 : args_end].strip()
            message = re.fullmatch(r"(?:const\s+)?([\w:]+)::(?:ConstSharedPtr|SharedPtr)\s+(\w+)", arguments)
            if not arguments or message:
                callbacks.append({"function": callback, "message_type": message[1] if message else None})

    # Pure typed outputs replace publisher ownership, not a fake publisher.
    mask = code_mask(text)
    edits = []
    latched_qos = {m[1] for m in re.finditer(r"auto\s+(\w+)\s*=\s*rclcpp::QoS\([^;]+;", mask) if "transient_local" in m[0]}
    publisher = r"rclcpp::Publisher\s*<([^>]+)>\s*::SharedPtr\s+(\w+)\s*;"
    for match in re.finditer(publisher, mask):
        output_fields.add(match[2])
        edits.append((match.start(), match.end(), f"original_gnc::Output<{match[1]}> {match[2]};", "typed_output_field"))
    for pattern in (
        r"rclcpp::Subscription\s*<[^>]+>\s*::SharedPtr\s+(\w+)\s*;",
        r"rclcpp::TimerBase::SharedPtr\s+(\w+)\s*;",
        r"rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr\s+(\w+)\s*;",
        r"std::unique_ptr<tf2_ros::TransformBroadcaster>\s+(\w+)\s*;",
    ):
        for match in re.finditer(pattern, mask):
            removed_fields.add(match[1])
            edits.append((match.start(), match.end(), blank(text[match.start() : match.end()]), "transport_field"))
    apply(edits)

    # Replace constructor wiring by output bindings and explicit period data.
    mask = code_mask(text)
    edits = []
    pattern = (
        r"\b(\w+)\s*=\s*(?:this->)?(create_subscription|create_publisher|create_wall_timer|"
        r"add_on_set_parameters_callback)(?:<[^>]+>)?\s*\("
    )
    for match in re.finditer(pattern, mask):
        opening = mask.index("(", match.start())
        end_args = closing(mask, opening)
        end = end_args + 1
        while end < len(mask) and mask[end].isspace():
            end += 1
        if mask[end] != ";":
            raise ValueError(f"Unrecognized original wiring expression at {name}")
        end += 1
        arguments = text[opening + 1 : end_args]
        kind = match[2]
        latched = (
            "true"
            if "transient_local()" in arguments or any(re.search(rf"\b{qos}\b", arguments) for qos in latched_qos)
            else "false"
        )
        if kind == "create_subscription":
            callback = re.search(r"std::bind\s*\(\s*&[\w:]+::(\w+)", code_mask(arguments))
            if callback is None:
                raise ValueError(f"Input requires an explicit callback at {name}")
            message_type = re.search(r"create_subscription<([^>]+)>", match[0])[1]
            topic = arguments.split(",", 1)[0].strip()
            replacement = f'context_.bind_input("{callback[1]}", {topic}, {message_type}::type_name, {latched});'
        elif kind == "create_publisher":
            output_fields.add(match[1])
            topic = arguments.split(",", 1)[0].strip()
            replacement = f'{match[1]}.bind(context_, "{match[1]}", {topic}, {latched});'
        elif kind == "add_on_set_parameters_callback":
            replacement = f"parameters_.set_validator({arguments});"
        else:
            binding = re.search(r"std::bind\s*\(\s*&[\w:]+::(\w+)", code_mask(arguments))
            if not binding:
                raise ValueError(f"Timer needs an explicit native callback at {name}")
            period = arguments[: binding.start()].rstrip().rstrip(",").strip()
            callback = binding[1]
            timer_fields.add(match[1])
            replacement = (
                f'context_.set_timer("{match[1]}", "{callback}", '
                f"std::chrono::duration_cast<std::chrono::nanoseconds>({period}).count());"
            )
            timers.append(callback)
        edits.append((match.start(), end, replacement + "\n" * text[match.start() : end].count("\n"), "explicit_interface"))
    apply(edits)
    for field in timer_fields:
        text = re.sub(rf"\b{field}->cancel\(\)", f'context_.cancel_timer("{field}")', text)
        text = re.sub(rf"if\s*\(\s*{field}\s*\)", f'if (context_.timer_active("{field}"))', text)
    # Transport QoS variables have no numerical meaning. Delivery/latch
    # policy is explicit in the native port contract above.
    text = re.sub(r"(?m)^\s*auto\s+\w*qos\w*\s*=\s*rclcpp::QoS\([^;]+;", lambda m: blank(m[0]), text)
    text = re.sub(
        r"(?m)^\s*tf_broadcaster_\s*=\s*std::make_unique<tf2_ros::TransformBroadcaster>\([^;]+;", lambda m: blank(m[0]), text
    )
    text = re.sub(r"(?m)^\s*tf_broadcaster_->sendTransform\([^;]+;", lambda m: blank(m[0]), text)
    for field in (
        removed_fields
        | output_fields
        | {
            "timer_",
            "odom_sub_",
            "heading_cmd_sub_",
            "env_force_sub_",
            "thruster_cmd_sub_",
            "waypoint_path_sub_",
            "initial_route_yaw_sub_",
            "depth_sub_",
            "fault_inject_sub_",
        }
    ):
        text = re.sub(rf"\b{field}\.reset\(\)\s*;", lambda m: blank(m[0]), text)

    # Mechanical type/interface renames only. No numerical expressions here.
    if name == "thrust_allocation_node.cpp":
        text = text.replace("std::exp(", "original_gnc::reference_exp(")
    text = text.replace("std::normal_distribution<double>", "original_gnc::ReferenceNormalDistribution<double>")
    if name in {"current_engine_node.cpp", "wave_engine_node.cpp", "wind_engine_node.cpp"}:
        for operation in ("hydro_parser_.load_1d_csv", "hydro_parser_.load_2d_csv", "load_env_asset_metadata"):
            mask = code_mask(text)
            edits = []
            for match in re.finditer(re.escape(operation) + r"\(", mask):
                start = mask.index("(", match.start()) + 1
                end = closing(mask, start - 1)
                edits.append((start, end, "context_.asset_path(" + text[start:end] + ")", "asset_location_boundary"))
            apply(edits)
    if name == "force_aggregator_node.cpp":
        text = text.replace(
            "load_source_metadata(rclcpp::Node* node,", "load_source_metadata(original_gnc::Parameters* node,"
        )
        text = text.replace("node->get_parameter(", "node->get(")
        text = text.replace("load_source_metadata(this,", "load_source_metadata(&parameters_,")
    for package in MESSAGE_PACKAGES:
        text = text.replace(f"{package}::msg::", f"original_gnc::messages::{package}::")
    for old, new in {
        "rclcpp::Time": "original_gnc::Time",
        "rclcpp::Duration": "original_gnc::Duration",
        "rclcpp::ParameterType": "original_gnc::ParameterType",
        "rclcpp::Parameter": "original_gnc::Parameter",
        "RCL_ROS_TIME": "original_gnc::ClockType::Ros",
        "RCL_SYSTEM_TIME": "original_gnc::ClockType::System",
        "tf2::toMsg": "original_gnc::to_message",
        "tf2::fromMsg": "original_gnc::from_message",
        "ament_index_cpp::get_package_share_directory": "context_.package_root",
    }.items():
        text = text.replace(old, new)
    for old, new in {
        "declare_parameter": "declare_value",
        "get_parameter_or": "get_or",
        "get_parameter": "get",
        "has_parameter": "has",
    }.items():
        text = re.sub(rf"(?:this->)?\b{old}(?=[<(])", f"parameters_.{new}", text)
    text = re.sub(r"\b(\w+)->publish\(", r"\1.emit(", text)
    text = re.sub(r"this->get_name\(\)|(?<![\w:>.])get_name\(\)", "context_.name.c_str()", text)

    if class_name:
        text = re.sub(
            rf"\bclass\s+{class_name}\s*:\s*public\s+rclcpp::Node\s*\{{",
            f"class {class_name} : public original_gnc::ModuleBase {{\n"
            "    template<class> friend struct original_gnc::Kernel;",
            text,
        )
        text = re.sub(
            rf"(?<!~)\b{class_name}\((?:const rclcpp::NodeOptions& options(?: = rclcpp::NodeOptions\(\))?)?\)",
            f"{class_name}(original_gnc::Context& context)",
            text,
        )
        text = re.sub(r":\s*(?:rclcpp::)?Node\([^\n]+\)(?=\s*[,{{\n])", ": original_gnc::ModuleBase(context)", text)
        text = re.sub(
            rf"\bclass\s+{class_name}\s*:\s*public\s+EnvEngineBase\s*\{{",
            f"class {class_name} : public EnvEngineBase {{\n    template<class> friend struct original_gnc::Kernel;",
            text,
        )
        text = re.sub(r':\s*EnvEngineBase\("[^"\n]+", true\)', ": EnvEngineBase(context, true)", text)
    if name in {"env_engine_base.cpp", "env_engine_base.hpp"}:
        text = text.replace(
            "const std::string& node_name, bool enable_realtime", "original_gnc::Context& context, bool enable_realtime"
        )
        text = text.replace(": Node(node_name)", ": original_gnc::ModuleBase(context)")

    # One original executable had one process-local instance. Preserve that
    # lifetime for ALL mutable method statics, including diagnostics clocks.
    static_fields = []
    if class_name and name.endswith(".cpp"):
        edits = []
        mask = code_mask(text)
        for index, match in enumerate(
            re.finditer(r"\bstatic\s+(int|double|original_gnc::Time)\s+(\w+)\s*([={][^;]*);", mask)
        ):
            field = f"native_static_{match[2]}_{index}_"
            initializer = text[match.start(3) : match.end(3)]
            static_fields.append(f"{match[1]} {field} {initializer};")
            edits.append((match.start(), match.end(), f"auto& {match[2]} = {field};", "per_instance_state"))
        apply(edits)
        if f"class {class_name} :" in text and static_fields:
            text = text.replace("private:", "private:\n    " + "\n    ".join(static_fields), 1)
    # Pure tf2 LinearMath headers are retained; all ROS transport includes go.
    transport = (
        r"(?:rclcpp|rcl_interfaces|nav_msgs|geometry_msgs|std_msgs|diagnostic_msgs|"
        r"ship_interfaces/msg|tf2_ros|tf2_geometry_msgs|ament_index_cpp)/"
    )
    text = re.sub(rf"(?m)^\s*#include\s*[<\"]{transport}[^\n]*", lambda m: blank(m[0]), text)
    text = '#include "native_context.hpp"\n' + text
    if re.search(r"\brclcpp::|\bcreate_subscription\b|\bcreate_publisher\b|\bcreate_wall_timer\b", code_mask(text)):
        raise ValueError(f"Unextracted ROS operation remains in {name}")
    return text, {
        "file": name,
        "edits": ledger,
        "callbacks": callbacks,
        "omitted_log_clock_sites": sorted(omitted_clocks),
        "timers": timers,
        "static_fields": static_fields,
        "normalized_source_sha256": hashlib.sha256(before.encode()).hexdigest(),
        "native_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "complete_diff": "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                text.splitlines(keepends=True),
                fromfile=f"original/{name}",
                tofile=f"native/{name}",
            )
        ),
    }


# Keep source contract branches together for audit against the frozen implementation.
def extract(source: Path, dependencies: Path, output: Path, support: Path) -> dict:  # noqa: PLR0915
    """Generate a reproducible local source port from the approved export."""
    if hashlib.sha256((source / "SOURCE_MANIFEST.csv").read_bytes()).hexdigest() != SOURCE_MANIFEST_SHA256:
        raise ValueError("Unapproved original source manifest")
    records = list(csv.DictReader((source / "SOURCE_MANIFEST.csv").open(encoding="utf-8-sig")))
    hashes = {r["relative_path"]: r["sha256"] for r in records}
    for relative, expected in hashes.items():
        path = (source / relative).resolve()
        if source not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Changed original source or asset: {relative}")
    output.mkdir(parents=True, exist_ok=True)
    include = output / "include"
    include.mkdir(exist_ok=True)
    shutil.copyfile(support / "native_context.hpp", include / "native_context.hpp")
    shutil.copyfile(support / "value_codec.hpp", include / "value_codec.hpp")
    shutil.copyfile(support / "reference_random.hpp", include / "reference_random.hpp")
    shutil.copyfile(support / "reference_exp.hpp", include / "reference_exp.hpp")
    messages = generate_messages(source, dependencies, include / "native_messages.hpp")
    manifest = {
        "schema": "original-gnc.native-extraction.v1",
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "messages": messages,
        "files": [],
        "modules": {},
    }
    for module, (package, qualified, klass) in MODULES.items():
        root = source / "src" / package
        module_static_fields = []
        node_path = root / "src" / ("nodes" if package == "environment/env_engines" else "") / f"{module}.cpp"
        for path in [node_path] + sorted((root / "include").glob("*/*.hpp")):
            if path.name.endswith("_node.hpp") and path.name != f"{module}.hpp":
                continue
            relative = str(path.relative_to(source))
            if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[relative]:
                raise ValueError(f"Changed original source: {relative}")
            owner = (
                klass
                if path.name in {f"{module}.cpp", f"{module}.hpp"}
                else "EnvEngineBase"
                if path.name == "env_engine_base.hpp"
                else None
            )
            native, entry = source_edits(path.read_text(), path.name, owner)
            if path.suffix == ".cpp":
                module_static_fields = entry["static_fields"]
            elif owner and module_static_fields:
                native = native.replace("private:", "private:\n    " + "\n    ".join(module_static_fields), 1)
                entry["native_sha256"] = hashlib.sha256(native.encode()).hexdigest()
            target = include / path.relative_to(root / "include") if path.suffix == ".hpp" else output / f"{module}.cpp"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(native)
            entry.update({"source_path": relative, "source_sha256": hashes[relative], "output_path": str(target)})
            entry["complete_diff"] = "".join(
                difflib.unified_diff(
                    path.read_text().splitlines(keepends=True),
                    native.splitlines(keepends=True),
                    fromfile=f"original/{relative}",
                    tofile=f"native/{relative}",
                )
            )
            manifest["files"].append(entry)
            if path.suffix == ".cpp":
                manifest["modules"][module] = {
                    "class": qualified,
                    "callbacks": entry["callbacks"],
                    "omitted_log_clock_sites": entry["omitted_log_clock_sites"],
                }
    manifest["support_sources"] = []
    env_root = source / "src/environment/env_engines"
    for path in sorted((env_root / "src").glob("*/*.cpp")):
        if path.parent.name == "nodes":
            continue
        native, entry = source_edits(
            path.read_text(), path.name, "EnvEngineBase" if path.name == "env_engine_base.cpp" else None
        )
        relative = str(path.relative_to(source))
        target = output / path.name
        target.write_text(native)
        entry.update({"source_path": relative, "source_sha256": hashes[relative], "output_path": str(target)})
        manifest["files"].append(entry)
        manifest["support_sources"].append(str(target))
    manifest["python_policy"] = extract_policy(source, output)
    manifest["python_observers"] = extract_observers(source, dependencies, output)
    (output / "extraction.json").write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--support", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.source.resolve(), args.dependencies.resolve(), args.output.resolve(), args.support.resolve())
    print(json.dumps({"files": len(result["files"]), "modules": sorted(result["modules"])}))
